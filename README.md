# tools-installer

One command to provision a fresh **macOS or Linux** machine with a full AI dev
environment — pick what you want from an interactive wizard, install it without
sudo where possible, and end up with a clean, de-duplicated `PATH`.

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | bash
```

> **Status: in development (v1 / MVP).** The design is locked in
> [`docs/prds/ai-dev-tools-installer-v1.0-prd.md`](docs/prds/ai-dev-tools-installer-v1.0-prd.md);
> the implementation is being built. The command above is the target interface,
> not a working endpoint yet.

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

## Quick start

### From the network (target experience)

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | bash
```

### From a clone

```sh
git clone https://github.com/castocolina/tools-installer.git
cd tools-installer
make install                 # uv creates .venv + installs deps
make run                     # launch the wizard
```

### Non-interactive (CI / scripting)

```sh
uv run setup.py --all                       # install everything
uv run setup.py --categories search,git     # only some categories
uv run setup.py --doctor                     # just audit & fix PATH
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
2. **tarball / GitHub release** unpacked into `~/.local` (no sudo) + symlink in `~/.local/bin`.
3. **Native package manager** — `dnf` · `apt` · `pacman` · `rpm-ostree`.
4. **Homebrew** — last resort.

On **immutable** distros, step 3 is skipped by default (userspace or `brew-linux`
instead), because `rpm-ostree install` requires a reboot and breaks atomicity.

Homebrew is **an optional package you can install from the wizard** (`brew-mac`,
`brew-linux`), never a prerequisite — some packages only live there, but if the
author ships an `.sh` that works, that wins.

## PATH doctor

The `doctor` flow keeps your shell PATH correct:

- Writes every required bin dir as `export PATH` into a single managed block in
  `~/.myshellrc` — **no duplicate entries**.
- Ensures `source ~/.myshellrc` exists in `~/.zshrc` (if present) and `~/.bashrc`,
  idempotently (it never adds the `source` line twice).
- Audits the live PATH and reports bin dirs that are **missing**, **broken**
  (directory gone), or **duplicated**, and offers to fix them.

```sh
uv run setup.py --doctor
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
| `make run`       | launch the wizard (`uv run setup.py`)                           |
| `make validate`  | pre-commit gates: `ruff check`, `ruff format --check`, `pyright`, `bandit`, `vulture` |
| `make test`      | `pytest` with coverage                                          |
| `make build`     | build the distributable                                         |
| `make uninstall` | remove installed artifacts                                      |

Quality gates are not optional and must not be bypassed (`# noqa`, `# type: ignore`,
skipped tests, lowered coverage floors). The full contributor rules live in
[`CLAUDE.md`](CLAUDE.md) and [`.claude/`](.claude/): [tooling](.claude/python-tooling.md),
[testing](.claude/testing.md), [git workflow](.claude/git-workflow.md), and
[dev environment](.claude/dev-environment.md).

## Project layout

```
install.sh                 # curl|bash bootstrap: detect OS/arch, ensure uv, run wizard
setup.py                   # wizard entrypoint (inline deps: rich, questionary)
installer/
  registry.toml            # the catalog — single source of truth
  model.py                 # Tool model + tomllib loader
  platform.py              # OS/arch + immutable detection
  strategies.py            # one install strategy per kind, driven by the priority ladder
  paths.py                 # PATH management + the doctor
  ui.py                    # questionary TUI (categories + spacebar multi-select)
tests/                     # pytest suite (offline, deterministic)
Makefile                   # task interface: install, build, run, validate, test, uninstall
pyproject.toml             # deps + tool config (ruff, pyright, pytest, coverage, …)
CLAUDE.md, .claude/        # contributor rules (tooling, testing, git, dev env)
docs/prds/                 # product requirements
```

## Background

This is a standalone, Homebrew-independent evolution of the installer that lived
in `uzkit/tools`. It keeps that project's mature declarative core (registry +
per-kind strategies) and replaces the text-menu UI with a real interactive wizard.
See the [PRD](docs/prds/ai-dev-tools-installer-v1.0-prd.md) for the full design.
