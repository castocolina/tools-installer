# Tempfile Extraction, `.zip` Support & `make uninstall` — Design

**Date:** 2026-06-10
**Status:** Approved

## Goal

Add `.zip` archive support to the download executor, harden the archive path
against the `curl | tar` pipefail masking bug, and implement `make uninstall` for
userspace artifacts — all without bypassing any quality gate.

## Motivation

The three asks converge on a single architectural change. The archive executor
currently streams `curl -fsSL -- <url> | tar -xz`:

- The pipe **masks curl's exit status** — a 404 yields empty stdin and `tar`
  fails, so it works by accident but is not airtight (POSIX `sh` has no
  `pipefail`).
- `.zip` archives **cannot** be streamed: `unzip` needs a *seekable* file.

Downloading to a temp file first fixes both: curl's failure breaks the `&&`
chain, and the seekable file is exactly what `unzip` requires.

## Design

### 1. Tempfile-based archive extraction (`download.py`)

Replace the streaming pipe with a single, self-cleaning shell command:

```sh
tmp=$(mktemp) && trap 'rm -f "$tmp"' EXIT \
  && curl -fsSL -o "$tmp" -- <url> \
  && tar -xzf "$tmp" -C <opt> --strip-components=<strip>   # tar.gz (default)
```

For zip:

```sh
tmp=$(mktemp) && trap 'rm -f "$tmp"' EXIT \
  && curl -fsSL -o "$tmp" -- <url> \
  && unzip -q -o "$tmp" -d <opt>
```

- `<url>` and `<opt>` are `shlex.quote`d before interpolation, as today.
- The command runs as one `["sh", "-c", cmd]` invocation through the injected
  `Runner` seam — the existing `argv → Runner` pattern, so tests stay offline
  argv-assertions.
- The **`raw`** path is unchanged: it already does `curl -fsSL -o <link>` (a
  file, not a pipe) and has no pipefail bug.

### 2. `.zip` selection rule

A new optional method param **`archive`**:

- absent or `"tar.gz"` ⇒ `tar -xzf` (today's behavior),
- `"zip"` ⇒ `unzip -q -o`.

`unzip` has **no `--strip-components`**, so for zip archives:

- the archive extracts whole into `<opt>`,
- the binary is addressed by its **full internal path** via `member`,
- `strip` is ignored.

To make nested layouts (e.g. `bun-<arch>/bun`) addressable, `member` is rendered
through the **same `{ver}`/`{arch.*}` templating** already used for `asset`.
Literal members (e.g. `rg`, `bin/gh`) contain no templates and are unaffected.

### 3. `make uninstall` — userspace artifacts only

The registry is the manifest. `install_download` always creates exactly two
paths per tool — `opt_dir(binname)` and `bin_dir()/binname`, where
`binname = PurePosixPath(member).name`. Uninstall is the symmetric inverse.

New module `installer/uninstall.py`:

- Walk the registry. For every method whose kind is in `DOWNLOAD_KINDS`, compute
  `binname` and collect `opt_dir(binname)` and `bin_dir()/binname`.
- Remove each path **only if it exists** (an opt dir recursively; a bin entry
  whether it is a symlink or a raw file). A tool that landed via the brew/native
  fallback has no matching paths → safe no-op.
- Present a **dry-run preview** of every path that would be removed, then an
  interactive confirm, reusing the existing `prompt`/`render` seams.
- Optionally strip the managed `~/.myshellrc` PATH block via a new
  `shellrc.remove_managed_block()`.

Out of scope (deliberately left alone — we cannot cleanly own them): brew/native
package installs, `uv`, the cloned repo at `~/.local/share/tools-installer`, and
the `source ~/.myshellrc` lines in `.zshrc`/`.bashrc`.

Wiring: `setup.py --uninstall` (mirrors `--doctor`), routed in `cli.py`/`app.py`;
`make uninstall` calls `uv run setup.py --uninstall`.

### 4. Sequencing

This plan ships the **executor change + uninstall only**. Once green at 100%
coverage, a follow-up **Batch 4** adds the JS-runtime tier (deno, bun, fnm,
pnpm, …) as pure registry data on the proven `.zip` path, each verified against
live releases — exactly the Batch 2/3 method.

## Testing

- `test_download.py`: assert the new tempfile `argv` for both `tar.gz` and
  `zip`; assert `member` templating renders `{ver}`/`{arch.*}`; assert `raw`
  path is unchanged; assert curl failure is no longer masked (the `&&` chain
  shape).
- `test_uninstall.py`: registry-driven path collection; existence-gated removal;
  symlink vs raw vs missing; dry-run preview; managed-block removal.
- `test_shellrc.py`: `remove_managed_block` idempotence.
- `test_cli.py`/`test_app.py`: `--uninstall` flag parsing and routing.
- 100% coverage maintained; `make validate` green (ruff, pyright strict, bandit,
  vulture, shellcheck).

## Non-negotiables

English only. No gate bypass (`# noqa`/`# type: ignore`/`# nosec`/
`# pragma: no cover`/skips/coverage lowering). Coherent commits.
