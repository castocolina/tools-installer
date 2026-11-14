# tools-installer

[![CI](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml/badge.svg)](https://github.com/castocolina/tools-installer/actions/workflows/ci.yml)

One command to provision a fresh **macOS or Linux** machine with a full AI dev
environment — pick what you want from an interactive wizard, install it without
sudo where possible, and end up with a clean, de-duplicated `PATH`.

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
# or, with wget:
wget -qO- https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
```

> **Status: in development (v1 / MVP).** The design is locked in
> [`docs/prds/ai-dev-tools-installer-v1.0-prd.md`](docs/prds/ai-dev-tools-installer-v1.0-prd.md);
> the implementation is being built. The install URL resolves once the repo is
> published — see [Publishing](docs/PUBLISHING.md).

---

## What it does

- **Bootstraps itself** — `install.sh` detects your OS/arch, ensures [`uv`](https://docs.astral.sh/uv/)
  is present (via Astral's official installer, *not* Homebrew), fetches this repo,
  and launches the wizard. No Python, no Homebrew required up front; either
  `curl` or `wget` will do.
- **Interactive wizard (TUI)** — one Textual app. The catalog view lists all 49
  tools: switch the grouping (category · priority · audience · status · table) with
  ←/→ or the mouse, toggle with **space**, confirm with **enter**. **Ctrl+P** opens
  an in-app command palette (number keys `1`–`5` switch views too); the catalog,
  doctor, fix, **uninstall**, and **policies** views all live in the same app.
  See [Selecting tools](#selecting-tools).
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

Install the AI dev environment with one command (`curl` and `wget` both work):

```sh
curl -fsSL https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
# or
wget -qO- https://raw.githubusercontent.com/castocolina/tools-installer/main/install.sh | sh
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
make doctor                                  # audit PATH (a report; runs the launch repairs first)
make fix                                     # wire PATH into your shell
```

## Selecting tools

The wizard opens on the catalog view of a single Textual app (keyboard and mouse):

| Key / action | Effect |
| --- | --- |
| Ctrl+P, or 1–5 | open the in-app command palette / jump straight to a view |
| ←/→ or click a tab | switch grouping: Category · Priority · Audience · Status · Table |
| click a column header (Table view) | re-sort by that column |
| ↑/↓ | move; the bottom bar shows the highlighted tool's (or group's) details |
| space / a / i | toggle · select all · invert |
| enter | install the selection (audit + confirm follow) |
| q | abort |

The cursor starts on the first selectable tool, and **enter** with nothing
selected is a guided no-op (it prompts you to pick at least one tool or quit),
never a silent exit. Ctrl+P opens **our** command palette — Textual's default
palette is disabled.

Priorities are color-coded (P0 essential → P3 niche) and every tool shows who
it serves (AI · you · both) plus its install state, with a legend pinned at
the bottom. `--all` and `--categories A,B` skip the screen entirely.

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

1. **Homebrew** (a formula, or a cask on macOS) — wherever Homebrew is installed.
2. **bun** (`kind = "bun"`, `bun add -g`) — the npm-package CLIs (`mmdc`, `puppeteer`, `pi`) install through bun first.
3. **pnpm** (`kind = "node"`, `pnpm add -g`) on the volta-provided Node runtime — the fallback for those same CLIs.
4. **Official `.sh` installer** from the tool's author, when it genuinely resolves
   (`uv`, `volta`, …).
5. **tarball / GitHub release** unpacked into `~/.local/opt/<tool>/` (no sudo) with the
   binary symlinked into `~/.local/bin`; single-file release binaries land in `~/.local/bin` directly.
   Where the release publishes sha256 checksums, the download is verified before
   extraction; a mismatch stops that tool's install (interactively you may retry,
   skip, or fall back — under `--yes` it hard-fails).
   macOS GUI apps (`.app` from a vendor zip) land in `~/Applications` — never
   `/Applications`, zero sudo — with their CLI symlinked into `~/.local/bin`;
   a Homebrew cask for the same app also targets `~/Applications` via `--appdir`.
6. **Native package manager** — `dnf` · `apt` · `pacman` · `rpm-ostree`.

On **immutable** distros, step 6 is skipped by default (userspace or `brew-linux`
instead), because `rpm-ostree install` requires a reboot and breaks atomicity.

Homebrew is **an optional package you can install from the wizard** (`brew-mac`,
`brew-linux`), never a prerequisite — some packages only live there.

**Homebrew first changes some installs.** On a host with Homebrew, the catalog shows
Homebrew as the declared route of every tool whose first method is brew or cask. That
label is display only: a copy's owner still comes from what actually installed it. The
owner-visible changes are:

- macOS: `claude`, `codex` and `kitty` now install from their Homebrew casks.
- Fedora hosts with Linuxbrew: `docker`, `git`, `glab`, `jq`, `podman`, `unzip`, `watch`,
  `zip` and `zsh` now install from Linuxbrew instead of `dnf`.

On a host without Homebrew no Homebrew step applies, and the rest of the order is what it
was before. The one difference is that the three npm-package CLIs try bun first.

Example: `mmdc` declares `kind = "bun"` with `npm_pkg = "@mermaid-js/mermaid-cli"`,
`co_install = ["puppeteer"]` and `versions = { puppeteer = "^25" }`, so one
`bun add -g @mermaid-js/mermaid-cli puppeteer@^25` installs both packages. Its
`requires = ["bun", "puppeteer"]` installs bun first, and its `kind = "node"` method is the
pnpm fallback.

Facts about bun that these installs rely on, all checked against bun 1.3.14:

- Bun-installed CLIs run under node, not under bun. Their bins start with
  `#!/usr/bin/env node`, so a node must be on PATH. Volta stays the Node runtime; there is
  no `volta install` method.
- Bun runs a dependency's lifecycle scripts only for its default allowlist (puppeteer is on
  it) or for packages named in a `trustedDependencies` list the user wrote. That list
  replaces the default allowlist instead of extending it. pnpm also blocks such scripts by
  default, so bun is comparable to pnpm, not stricter.
- This installer never passes a trust flag and never writes `trustedDependencies`. If a
  user's list leaves puppeteer out, the browser is not downloaded, the smoke check fails,
  and the failure line names the command that trusts it: `bun add -g --trust puppeteer@^25`.

**Existing installs stay with their manager.** A tool that pnpm, volta, Homebrew or a
vendor installer already put on the host keeps that owner. The installer reports it as
already installed and never reinstalls it to reach the new order. To move such a tool to
bun, remove the existing copy, then install it again:

- The **Uninstall view** removes a copy this installer installed itself; its receipt is the
  proof.
- For a copy another manager owns, the view names that manager. It shows the manager's
  removal command (for example `pnpm remove --global @mermaid-js/mermaid-cli`) only when it
  knows the manager and the package. When it knows the manager but not the package, it
  names the manager alone.
- For a copy whose owner it cannot tell, such as one a vendor installer put there, the view
  shows no command. Remove it with whatever installed it.
- A broken copy shows the repair note (reinstall it from the catalog) instead of any removal
  command.

### Tool dependencies (`requires`)

A registry entry can declare `requires = ["<tool-id>", ...]`. When you select a
tool, the installer expands the full transitive dependency set, adds any missing
dependencies to the install list (printing "Added dependencies: …"), and installs
them first in dependency order. A dependency that is unavailable on your platform
is skipped with a warning, and any tool that needs it is skipped too.

The catalog detail bar shows a `requires: …` line for tools that have dependencies.

**Uninstalling** a tool that other tools depend on appends a "required by …" note to
its row in the uninstall view — warn-but-allow: it does not block the removal and
does not cascade to dependents.

## PATH doctor & fix

`make doctor` is a **report**: it audits the live PATH against the bin
dirs the installer manages and reports any that are **missing** from PATH,
**broken** (directory gone), or **duplicated** — then points you at `make fix`.
Only directories that actually exist on disk are managed, so tools you never
installed are never reported. Like every interactive or CLI launch (the TUI, `make doctor`,
`make fix`, `make uninstall`, a headless install), it first repairs installer-owned
leftovers: it strips legacy alias blocks and removes the retired pip/npm guard an earlier
version wrote (the marked `npm`, `npx`, `pnpm`, `pip` and `pip3` shims in the managed bin
dir and the alias block in your shell rc files), naming each file it removes. It prints a
warning naming the file and the fix when its first read of one of those files fails (for
any reason but a missing file), when it cannot delete a shim, or when it cannot rewrite an
rc file. It leaves without a message anything it does not recognize as its own (a symlink,
an unmarked file, a shim over 8 KiB, an rc file over 1 MiB or not valid UTF-8) and any file
that changed or became unreadable after that first read; the next launch checks again.
Scheduled background jobs run no cleanup.

`make fix` applies the wiring:

- Writes every managed bin dir as `export PATH` into a single managed block in
  `~/.myshellrc` — **no duplicate entries**.
- Ensures `source ~/.myshellrc` exists in `~/.zshrc` (if present) and `~/.bashrc`,
  idempotently (it never adds the `source` line twice).
- Lets you choose how PATH is wired (`--link-mode`): **centralized** (one
  `~/.myshellrc` sourced from both rc files), **single** (sourced from your current
  shell only), or **split** (the PATH block written directly into each rc file).

Run interactively, `make doctor` and `make fix` open inside the unified app as
**guided views** (reach any view with `Ctrl+P` or the number keys `1`–`5`). The
**Doctor view** is read-only: every finding is shown with a plain-language meaning
and the exact next step — including when a shell reload is needed and that transient
duplicates clear on a new shell — color-coded by severity. The **Fix view** previews
what will be wired and applies it in place when you press `a`, then tells you to
restart your shell (or `source ~/.myshellrc`). Running without a terminal — or
`make fix ARGS="--link-mode=…"` — keeps the plain console behavior described above.

After an install, the wizard audits your live PATH and — when a tool's own
installer added a duplicate `export PATH` line to `.bashrc`/`.zshrc` for a
directory `~/.myshellrc` already covers — previews those lines and offers to
remove them. Your own content is never touched, and the removal always asks first.

```sh
make doctor   # diagnose
make fix      # apply
```

### Shell tweak bundles

The policies view also surfaces three curated, independently-toggleable shell-tweak
bundles. Each writes its own marker block into `~/.myshellrc` (already sourced by
bash and zsh) and takes effect in a new shell. Enabling or disabling one never
touches another bundle or your own content.

| Bundle | Available on | What it adds |
| --- | --- | --- |
| **Docker shortcuts** | all | `docker-ps` (live container table via `watch`), `docker-stats`, `docker-memory` |
| **Countdown helper** | all | `wait_time <secs>` — a portable terminal countdown |
| **apt selective upgrade** | Linux | `apt-upgrade` — upgrades only packages that have available updates |

`docker-ps` requires the `watch` command to be on your PATH. The `apt-upgrade`
bundle is offered on Linux only (not macOS).

### Install tuning

Installing claude, codex, opencode, cursor-agent, copilot or VS Code writes that
tool's documented auto-approve, no-attribution and lean keys, only where the key
is absent. Oh-My-Zsh gets its plugins and default theme, and starship, direnv,
zoxide, fzf, fnm and volta get their shell init. All of it happens with no
question, is reverted when the tool is removed, and a tool that is already
installed shows `≈ apply install tuning`.

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
| `make setup`     | launch the wizard (`uv run --isolated --no-dev setup.py`, isolated, without dev dependencies, so the installer sees your real tools (dev ruff never shadows yours); flags via `ARGS`; `make run` is an alias) |
| `make doctor`    | audit `PATH` (a report; runs the launch repairs first)          |
| `make fix`       | wire `PATH` into your shell (`~/.myshellrc` + rc files)         |
| `make verify-registry` | check every release asset, archive member, checksum and pin against upstream; read-only; needs network; uses your gh login for the API rate limit; `ARGS="--write"` is the maintainer bump mode |
| `make audit-catalog` | maintainer tooling for the catalog-audit skill: prints read-only facts about one registry entry and validates and stores its audit report under `.planning/audits/catalog/<date>/`; subcommand via `ARGS="…"` (`status`, `facts`, `write`); never installs anything |
| `make validate`  | pre-commit gates: `ruff check`, `ruff format --check`, `pyright`, `bandit`, `vulture`, `shellcheck` |
| `make test`      | `pytest` with coverage                                          |
| `make build`     | build the distributable                                         |
| `make uninstall` | remove userspace artifacts. Interactively (a TTY) this opens the app on the **uninstall view**: toggle which tools to remove, plus an independent toggle for the managed `~/.myshellrc` PATH wiring, applied live with reload guidance. Non-interactively / `--yes` it runs the unchanged console flow (previews `~/.local/opt/*` dirs, `~/.local/bin` symlinks, and the PATH block, then confirms) |

Quality gates are not optional and must not be bypassed (`# noqa`, `# type: ignore`,
skipped tests, lowered coverage floors). The full contributor rules live in
[`AGENTS.md`](AGENTS.md) and [`.claude/`](.claude/): [tooling](.claude/python-tooling.md),
[testing](.claude/testing.md), [git workflow](.claude/git-workflow.md), and
[dev environment](.claude/dev-environment.md).


### Registry drift

A scheduled GitHub Actions workflow (`verify-registry.yml`) runs weekly (Monday cron) and on manual dispatch — never in the PR gate. It calls `make verify-registry ARGS="--issue"`, which opens or updates a single issue labelled `registry-drift` when drift is confirmed (inconclusive findings are listed beside drift). When GitHub is rate-limited or unreachable and no drift was confirmed, it posts nothing (drift confirmed in an otherwise blocked run is still posted, with a note). The job keeps its digest state between runs via Actions cache restore/save (including when a run hits its time limit, so the next run resumes). A mid-week schedule entry only restores and re-saves that state to make GitHub's 7-day cache eviction unlikely; if the state is lost anyway, the next check downloads every asset once and rebuilds it.

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
AGENTS.md, .claude/        # contributor rules (tooling, testing, git, dev env)
docs/prds/                 # product requirements
```

## Background

This is a standalone, Homebrew-independent evolution of the installer that lived
in `uzkit/tools`. It keeps that project's mature declarative core (registry +
per-kind strategies) and replaces the text-menu UI with a real interactive wizard.
See the [PRD](docs/prds/ai-dev-tools-installer-v1.0-prd.md) for the full design.
