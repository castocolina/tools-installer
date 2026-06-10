# Script-Installer Tier & PATH Hygiene — Design

**Date:** 2026-06-10
**Status:** Approved (decomposed into SP1 → SP2 → SP3)

## Goal

Add the JS-runtime/package-manager tools that ship official `curl | sh` installers
(bun, fnm, pnpm) via the ladder-preferred `script` method, and add the PATH-hygiene
needed so their self-wiring does not leave duplicated `PATH` entries: a shell-rc
link-mode preference, duplicate detection/cleaning in `.bashrc`/`.zshrc`, and a
post-install doctor verification pass.

## Motivation

pnpm/bun/fnm all ship official installers, so per the PRD priority ladder they
belong on the top `script` step (priority 10), not as `github_release` entries
needing arch tokens. But these installers self-edit the user's shell rc (bun and
pnpm unconditionally; fnm unless `--skip-shell`). The `_script` executor passes
only `env` + `shell` (no CLI args), so rather than suppress the edits we let the
installers run and then clean the duplicate `PATH` lines they add — keeping
`~/.myshellrc` the single managed source of truth.

## Verification evidence (live, 2026-06-10)

- brew core formulae exist (untapped) for **bun**, **pnpm**, **fnm**
  (`formulae.brew.sh/api/formula/<f>.json` → `tap: homebrew/core`). Brew fallback
  is valid for all three.
- **bun** (`https://bun.sh/install`, `bash`): installs to `$BUN_INSTALL` (default
  `$HOME/.bun`), binary at `~/.bun/bin/bun`. Same dir on Linux and macOS. Self-edits
  `.zshrc`/`.bashrc`/fish (no opt-out env). Uses `unzip` internally.
- **pnpm** (`https://get.pnpm.io/install.sh`, `sh`): downloads the binary then runs
  `pnpm setup --force`, which writes to `PNPM_HOME` — default Linux
  `~/.local/share/pnpm`, macOS `~/Library/pnpm`. Honors `PNPM_VERSION`. `pnpm setup`
  edits the shell rc and needs `SHELL` set (inherited from the parent process).
- **fnm** (`https://fnm.vercel.app/install`, `bash`): Linux default install dir
  `~/.local/share/fnm`; on macOS the installer **delegates to Homebrew** unless
  `--force-install` — so we install via `script` on Linux and `brew` on macOS.
  `--skip-shell`/`--install-dir` are CLI flags (not env), which the executor cannot
  pass — hence the clean-the-duplicates approach.

## Design — three sub-projects

### SP1 — Script-installer tier (registry data only, no code change)

Add three `[[tool]]` entries. Each `bin_dir` flows into `~/.myshellrc` via the
existing platform-aware `collect_bin_dirs`.

- **bun** — `runtime`, cmd `bun`:
  - `script` (no os filter — works on both), `url = https://bun.sh/install`,
    `shell = "bash"`, `bin_dir = "~/.bun/bin"`.
  - `brew` formula `bun`.
- **pnpm** — `pkg-mgr`, cmd `pnpm`:
  - `script` os `[debian, arch, fedora]`, `url = https://get.pnpm.io/install.sh`,
    `shell = "sh"`, `bin_dir = "~/.local/share/pnpm"`.
  - `script` os `[macos]`, same url/shell, `bin_dir = "~/Library/pnpm"`.
  - `brew` formula `pnpm`.
- **fnm** — `runtime`, cmd `fnm`:
  - `script` os `[debian, arch, fedora]`, `url = https://fnm.vercel.app/install`,
    `shell = "bash"`, `bin_dir = "~/.local/share/fnm"`.
  - `brew` formula `fnm` (covers macOS, where the installer brew-delegates anyway).

Registry goes 41 → 44. New resolution tests pin each tool's ladder order
(`script`/`brew`) and per-OS `bin_dir`. No executor change.

### SP2 — Shell-rc link-mode preference

A new select-one preference (with a non-interactive CLI flag) controlling how PATH
reaches the shells:

- **centralized** (default, today's behavior): one `~/.myshellrc` holding the
  managed PATH block, `source`d from both `.zshrc` and `.bashrc`.
- **single-shell**: source `~/.myshellrc` from only the chosen shell (picked, or
  auto-detected from `$SHELL`).
- **split-inline**: write the managed PATH block directly into each rc file, no
  `~/.myshellrc` indirection.

Touches `shellrc.py` (apply per mode), `prompt.py` (add a single-select callback —
today only checkbox/confirm exist), `cli.py` (a `--link-mode` flag), `app.py`
(`configure_path` takes the mode), `setup.py` (prompt + wire).

### SP3 — PATH hygiene (clean duplicates + verify)

- **Duplicate cleaning**: the doctor scans `.bashrc`/`.zshrc` for `export PATH`
  lines that add a directory `~/.myshellrc` already manages (i.e. the blocks
  bun/pnpm/fnm append) and offers to remove those redundant lines — never touching
  unrelated user content. Defined relative to SP2's chosen link model (in
  split-inline mode there is no `~/.myshellrc` to dedupe against, so cleaning keys
  off the managed dir set, not the file).
- **Post-install verify**: after an install run, automatically run the doctor audit
  so the user ends with a clean PATH report (or the specific dups to fix).

## Sequence

SP1 → SP2 → SP3. SP1 is independently shippable (the three tools, brew-backstopped).
SP3's dup-cleaning is defined against SP2's link model, so the model lands first.

## Testing

Each sub-project ships green at 100% coverage with all gates (ruff, pyright strict,
bandit, vulture, shellcheck). SP1 is resolution-test data; SP2/SP3 are unit-tested
against tmp_path rc files with injected prompt/confirm seams, mirroring the existing
doctor/shellrc tests.

## Non-negotiables

English only. No gate bypass. Coherent commits. Commit on `main`; do not push
(standing deferral).
