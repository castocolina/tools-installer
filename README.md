# tools-installer

[![CI](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml/badge.svg)](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml)

One command to provision a fresh **macOS or Linux** machine with a full AI dev
environment — pick what you want from an interactive wizard, install it without
sudo where possible, and end up with a clean, de-duplicated `PATH`.

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

> **Status: in development (v1 / MVP).** The design is locked in
> [`docs/prds/ai-dev-tools-installer-v1.0-prd.md`](docs/prds/ai-dev-tools-installer-v1.0-prd.md);
> the implementation is being built. The install URL resolves once the repo is
> published — see [Publishing](docs/PUBLISHING.md).

---

## What it does

- **Bootstraps itself** — `install.sh` detects your OS/arch, ensures [`uv`](https://docs.astral.sh/uv/)
  is present (via Astral's official installer, *not* Homebrew), fetches this repo,
  and launches the wizard. No Python, no Homebrew required up front.
- **Interactive wizard (TUI)** — browse by category, toggle tools with the
  **spacebar** (arrows to move, space to mark, enter to confirm) — the same feel
  as `sv` or the Claude plugin marketplace.
- **Installs in userspace by default** — `~/.local/bin` for CLIs, `~/Applications`
  for macOS GUIs. No `sudo`, no writing to `/Applications` or system paths, so it
  works on locked-down corporate Macs and atomic/immutable Linux.
- **Manages your PATH** — a single managed `~/.myshellrc` holds every needed
  `export PATH`, sourced from `.zshrc`/`.bashrc`, idempotent and **never duplicated**.
- **Declarative catalog** — every tool is one entry in
  [`installer/registry.toml`](installer/registry.toml). Adding a tool is a data
  change, not code.

## Available tools

The catalog is seeded and growing toward the full set. Today it installs:

| Category    | Tools                                                                         |
| ----------- | ----------------------------------------------------------------------------- |
| pkg-mgr     | `uv`, Homebrew (opt-in), `pnpm`                                               |
| search      | `ripgrep` (rg) ✓, `fd`, `fzf` ✓, `ast-grep`                                  |
| view        | `bat`, `eza`, `glow` ✓, `hexyl`                                               |
| git         | `delta`, `lazygit` ✓, `gh` ✓, `difftastic` (difft), `gitui`                  |
| docker      | `lazydocker` ✓, `dive` ✓                                                      |
| data        | `jq`, `yq`, `miller` (mlr) ✓, `fx`, `dasel`, `gron`, `jless`                 |
| text        | `sd`                                                                          |
| nav         | `zoxide`, `broot`                                                             |
| runtime     | `deno` ✓, `bun`, `fnm`                                                        |
| shell       | `starship` ✓, `direnv`, `gum` ✓                                               |
| dev         | `just` ✓, `ruff` ✓, `hyperfine`, `shfmt`, `tealdeer` (tldr) ✓, `vale` ✓     |
| sysinfo     | `bottom` (btm), `dust`, `duf` ✓, `procs`                                     |
| security    | `gitleaks` ✓                                                                  |
| net         | `xh`                                                                          |
| ai          | `aichat`                                                                      |
| editor      | `vscode` (code), `sublime` (subl)                                             |

`✓` = downloads are sha256-verified against the release's published checksums.

Download-based tools install without sudo: each is unpacked into `~/.local/opt/<tool>/`
with its binary symlinked into `~/.local/bin`. Where a tool ships no asset for your
platform (e.g. an Intel-Mac or macOS-only gap), the install falls through to Homebrew.

Archives may be `.tar.gz` or `.zip` (a method sets `archive = "zip"`); both are
downloaded to a temp file and extracted into `~/.local/opt/<tool>/`. `make uninstall`
reverses this — it removes those opt dirs, the matching `~/.local/bin` symlinks, and
the managed `~/.myshellrc` block, leaving Homebrew/native/uv installs untouched.

## Quick start

Install the AI dev environment with one command:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

Pass wizard flags through `sh -s --`:

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh -s -- --all --yes
```

The bootstrap detects your platform, installs [uv](https://docs.astral.sh/uv/)
if it is missing, clones the repo to `~/.local/share/tools-installer`, and
launches the wizard. Override defaults with `TI_REPO_URL`, `TI_REF`, `TI_DIR`,
or `TI_UV_INSTALL_URL`, or set `TI_NO_RUN=1` to install without launching.

### From a clone

```sh
git clone https://github.com/castocolina/tools-installer.git
cd tools-installer
make install                 # uv creates .venv + installs deps
make setup                   # launch the wizard (make run is an alias)
```

### Non-interactive (CI / scripting)

```sh
make setup ARGS="--all"                      # install everything
make setup ARGS="--categories search,data"   # only some categories
make doctor                                  # audit PATH (read-only report)
make fix                                     # wire PATH into your shell
```

## Supported platforms

| OS / Distro            | Detected via      | Native fallback   | Notes                                  |
| ---------------------- | ----------------- | ----------------- | -------------------------------------- |
| macOS (Apple Silicon + Intel) | `sw_vers`  | Homebrew (opt-in) | GUIs land in `~/Applications`          |
| Ubuntu / Pop!_OS / Debian | `apt-get`      | `apt`             |                                        |
| Manjaro / Arch         | `pacman`          | `pacman`          |                                        |
| Fedora                 | `dnf`             | `dnf`             |                                        |
| Bazzite / Fedora Atomic | `rpm-ostree` + `/run/ostree-booted` | (skipped) | Immutable: stays in userspace, avoids reboots |

Windows is out of scope for v1.

## How installs are decided

When a tool can be installed more than one way, the engine walks a **priority
ladder** (each tool can override it in the registry):

1. **Official `.sh` installer** from the tool's author, when it genuinely resolves
   (`uv`, `volta`, …).
2. **tarball / GitHub release** unpacked into `~/.local/opt/<tool>/` (no sudo) with the
   binary symlinked into `~/.local/bin`; single-file release binaries land in `~/.local/bin` directly.
   Where the release publishes sha256 checksums, the download is verified before
   extraction; a mismatch stops that tool's install (interactively you may retry,
   skip, or fall back — under `--yes` it hard-fails).
   macOS GUI apps (`.app` from a vendor zip) land in `~/Applications` — never
   `/Applications`, zero sudo — with their CLI symlinked into `~/.local/bin`;
   their Homebrew-cask fallback also targets `~/Applications` via `--appdir`.
3. **Native package manager** — `dnf` · `apt` · `pacman` · `rpm-ostree`.
4. **Homebrew** — last resort.

On **immutable** distros, step 3 is skipped by default (userspace or `brew-linux`
instead), because `rpm-ostree install` requires a reboot and breaks atomicity.

Homebrew is **an optional package you can install from the wizard** (`brew-mac`,
`brew-linux`), never a prerequisite — some packages only live there, but if the
author ships an `.sh` that works, that wins.

## PATH doctor & fix

`make doctor` is a **read-only report**: it audits the live PATH against the bin
dirs the installer manages and reports any that are **missing** from PATH,
**broken** (directory gone), or **duplicated** — then points you at `make fix`.
Only directories that actually exist on disk are managed, so tools you never
installed are never reported. It changes nothing.

`make fix` applies the wiring:

- Writes every managed bin dir as `export PATH` into a single managed block in
  `~/.myshellrc` — **no duplicate entries**.
- Ensures `source ~/.myshellrc` exists in `~/.zshrc` (if present) and `~/.bashrc`,
  idempotently (it never adds the `source` line twice).
- Lets you choose how PATH is wired (`--link-mode`): **centralized** (one
  `~/.myshellrc` sourced from both rc files), **single** (sourced from your current
  shell only), or **split** (the PATH block written directly into each rc file).

After an install, the wizard audits your live PATH and — when a tool's own
installer added a duplicate `export PATH` line to `.bashrc`/`.zshrc` for a
directory `~/.myshellrc` already covers — previews those lines and offers to
remove them. Your own content is never touched, and the removal always asks first.

```sh
make doctor   # diagnose
make fix      # apply
```

## What's NOT in v1

- SSH key setup and git configuration (handled by a separate project).
- Claude/Codex registration flows from `uzkit`.
- Windows / WSL.

## Development

Python, managed entirely with [`uv`](https://docs.astral.sh/uv/) — it owns the
Python version, the `.venv`, and dependencies (no `pip`/`poetry`/`conda`). Every
workflow has a `make` target so local runs and CI are identical:

| Command          | Does                                                            |
| ---------------- | -------------------------------------------------------------- |
| `make install`   | `uv sync` — create `.venv`, install runtime + dev deps          |
| `make setup`     | launch the wizard (`uv run setup.py`; flags via `ARGS`; `make run` is an alias) |
| `make doctor`    | audit `PATH` (read-only report)                                 |
| `make fix`       | wire `PATH` into your shell (`~/.myshellrc` + rc files)         |
| `make validate`  | pre-commit gates: `ruff check`, `ruff format --check`, `pyright`, `bandit`, `vulture`, `shellcheck` |
| `make test`      | `pytest` with coverage                                          |
| `make build`     | build the distributable                                         |
| `make uninstall` | remove userspace artifacts: `~/.local/opt/*` dirs, `~/.local/bin` symlinks, and the managed `~/.myshellrc` PATH block (previews, then asks to confirm) |

Quality gates are not optional and must not be bypassed (`# noqa`, `# type: ignore`,
skipped tests, lowered coverage floors). The full contributor rules live in
[`CLAUDE.md`](CLAUDE.md) and [`.claude/`](.claude/): [tooling](.claude/python-tooling.md),
[testing](.claude/testing.md), [git workflow](.claude/git-workflow.md), and
[dev environment](.claude/dev-environment.md).

## Project layout

```
install.sh                 # curl|sh bootstrap: detect OS/arch, ensure uv, clone, run wizard
setup.py                   # wizard entrypoint / composition root (rich, questionary)
installer/
  registry.toml            # the tool catalog — single source of truth
  model.py                 # Tool/Method model + tomllib loader
  platform.py              # OS/arch + immutability detection
  resolve.py               # which methods apply, ordered by the priority ladder
  engine.py                # install a tool by walking its resolved ladder
  executors.py             # native package-manager executors (argv → runner)
  download.py              # github_release / tarball binary executors
  versions.py, assets.py   # GitHub release version + asset-name resolution
  app.py, cli.py           # wizard flow + non-interactive flag parsing
  selection.py, audit.py   # catalog → choices; installed/missing status
  prompt.py, render.py     # injected TUI callbacks + rich output
  session.py               # orchestrate installs, bucket the outcomes
  shellrc.py, doctor.py    # ~/.myshellrc management + PATH audit/fix
  locations.py, status.py, run.py, links.py   # seams: paths, is-installed, runner, URLs
tests/                     # pytest suite (offline, deterministic)
.github/workflows/ci.yml   # CI: make validate + make test on Ubuntu + macOS
Makefile                   # task interface: install, setup, doctor, build, validate, test
pyproject.toml             # deps + tool config (ruff, pyright, pytest, coverage, …)
CLAUDE.md, .claude/        # contributor rules (tooling, testing, git, dev env)
docs/prds/                 # product requirements
```

## Background

This is a standalone, Homebrew-independent evolution of the installer that lived
in `uzkit/tools`. It keeps that project's mature declarative core (registry +
per-kind strategies) and replaces the text-menu UI with a real interactive wizard.
See the [PRD](docs/prds/ai-dev-tools-installer-v1.0-prd.md) for the full design.
