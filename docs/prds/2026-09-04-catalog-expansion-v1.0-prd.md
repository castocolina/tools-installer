# Catalog Expansion: Shell, Terminals, Agent Hosts, and Linux Parity - Product Requirements Document (PRD)

## Requirements Description

### Background

Requested additions surfaced while scoping the tier/dependency work
(`2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`): shell tooling
and a container runtime for macOS system prerequisites, terminal emulators
for the user tier, and new agent-host CLIs plus code-intelligence tools for
the ai tier. None of `zsh`, `oh-my-zsh`, `gnu bash` (as a distinct entry from
macOS's built-in bash), Apple Containers, `kitty`, `wezterm`, `antigravity`,
`cursor-agent`, `codegraph`, `graphify`, or `rtk` exist in the current
catalog. `docker`, `podman`, `colima`, `vscode`, `sublime`, and
`jetbrains-toolbox` already do (added by the doctor/catalog refresh work).

The catalog has also only ever been exercised on macOS. This PRD's Linux/
Bazzite section is about closing that gap for the tools it adds, not a
general Linux audit of the whole catalog.

### Target Users

- Developers bootstrapping macOS, mutable Linux, and immutable Linux
  (Bazzite) machines who want the installer to reach further into shell
  setup and agent-host tooling than it does today.
- Developers who already use `codegraph`/`graphify` for AI-agent code
  intelligence and want them installed without the pnpm bug documented in
  `2026-09-04-package-manager-policy-v1.0-prd.md`.

### Value Proposition

- Extend the "prerequisites before everything else" system tier
  (`2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`) with the
  shell/container tooling the user actually starts from.
- Add the agent-host CLIs and code-intelligence tools this project exists
  to serve, using install methods that avoid the known pnpm data-loss bug.
- Give Bazzite/immutable-Linux users a real container runtime story (podman)
  instead of silence.

## Feature Overview

### Core Features

1. System tier: `zsh`, `oh-my-zsh` (with `git`/`docker` plugins - pending
   the tier PRD's Open Question on how plugins map to the `Tool` model),
   `gnu-bash` (macOS only - Apple ships an ancient bash 3.2 under GPL
   licensing constraints; this is a distinct, newer bash), Apple Containers
   (macOS only, native `container` CLI).
2. User tier: `kitty`, `wezterm`.
3. Ai tier: `antigravity`, `cursor-agent`, `codegraph` (`kind="github_release"`
   per the package-manager-policy PRD's verified finding - a prebuilt
   binary, no npm involved), `graphify` (new `kind="uv-tool"` method, using
   the verified-clean `graphifyy` PyPI package - see below).
4. `rtk` ("Rust Token Killer") - **resolved, 2026-09-04:** repo confirmed
   at `rtk-ai/rtk` (`https://github.com/rtk-ai/rtk`). Verified via the
   GitHub API: pure Rust, `kind="github_release"` (same shape as `rg`/`fd`/
   `codegraph` - prebuilt per-platform tarballs: `rtk-aarch64-apple-darwin.tar.gz`,
   `rtk-x86_64-apple-darwin.tar.gz`, `rtk-aarch64-unknown-linux-gnu.tar.gz`,
   `rtk-x86_64-unknown-linux-musl.tar.gz`) with a `checksums.txt` release
   asset - this project's existing `checksum` registry param
   (checksums-file format, already used by `fzf`/`lazygit`/`gh`/etc.) can
   verify it the same way. Default branch is `develop`, not `main` - only
   matters if anything ever needs to reference the repo's branch directly;
   the release-asset flow used here does not.
5. **Wire `recommends` (per `2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`'s
   new soft-dependency feature):** `claude`, `opencode`, `codex`,
   `cursor-agent`, and `antigravity` each gain
   `recommends = ["codegraph", "graphify", "rtk"]` (adjusted per tool as it
   makes sense) - surfaced, never auto-installed, when one of those is
   selected.
5. Linux/Bazzite parity: where this PRD's new tools have a macOS-specific
   install path (Apple Containers, `gnu-bash` via brew), document or provide
   the Linux equivalent (`podman` already exists in the catalog; `gnu-bash`
   is moot on Linux, which already ships a current bash).

### Feature Boundaries

In scope:

- Registry entries (`id`, `category`, `tier`, `priority`, `audience`,
  `desc`, `requires`, `[[tool.method]]` blocks) for the tools listed above.
- A new `kind="uv-tool"` executor for `graphify` (`uv tool install
  graphifyy` - note the package name is `graphifyy`, double-y, while the CLI
  command is `graphify`; confirmed via research, not assumed).
- Documentation of the Apple-Containers/podman split between macOS and
  Linux.

Out of scope:

- A general audit of every existing catalog tool's Linux/Bazzite install
  path - scoped to the tools this PRD adds.
- `codegraph`'s postinstall MCP registration - covered by
  `2026-09-04-postinstall-hooks-v1.0-prd.md`.
- Re-doing the per-tool internal-dependency verification for tools already
  verified in `2026-09-04-package-manager-policy-v1.0-prd.md` (`codegraph`,
  `graphify`) - this PRD inherits those findings rather than re-researching
  them, but every tool unique to this PRD (`zsh`, `oh-my-zsh`, `gnu-bash`,
  Apple Containers, `kitty`, `wezterm`, `antigravity`, `cursor-agent`, `rtk`)
  still needs the same verification pass before implementation, per the
  mandatory step that PRD establishes.

## Detailed Requirements

### New Executor: uv-tool

- `installer/executors.py` gains a `"uv-tool"` kind, mirroring the existing
  `"node"` kind's shape (`pnpm add -g <npm_pkg>` -> `uv tool install
  <pypi_pkg>`), using this project's own already-trusted `uv` toolchain
  rather than adding a new trust dependency.
- `graphify`'s registry entry: `kind="uv-tool"`, package `graphifyy`,
  `requires = ["uv"]` (uv is already a catalog tool).

### Shell and Container Requirements

- `zsh`: platform-appropriate install (brew on macOS, distro package manager
  on Linux where not already the default shell).
- `oh-my-zsh`: official install script (`kind="script"`, matching the
  `bun`/`pnpm`/`fnm` pattern - note `codegraph` is `kind="github_release"`,
  not `kind="script"`, per the package-manager-policy PRD's verified
  finding), `requires = ["zsh"]`. Verify what `oh-my-zsh`'s installer
  actually does (it is a much larger, more invasive script than
  `bun`/`fnm`'s - it rewrites `.zshrc`) before assuming it is a safe,
  reviewable `kind="script"` candidate.
- `gnu-bash`: macOS only (`os = ["macos"]` per the existing per-method `os`
  filter), via brew; absent on Linux, where the system bash is already
  current GNU bash.
- Apple Containers: macOS only, native `container` CLI (Apple's own tool,
  no separate install needed on a current macOS - registry entry should
  reflect this if there is nothing to actually install, or document the
  minimum OS version requirement if there is).

### Terminal Emulator Requirements

- `kitty`, `wezterm`: brew on macOS (both are in homebrew-core); Linux
  equivalents via each distro's package manager or the project's existing
  `.zip`/GitHub-release download path if no native package exists - verify
  live before adding, per this project's existing registry-authoring
  convention (every prior batch verified assets against live releases).

### Agent Host Requirements

- `antigravity`, `cursor-agent`: verify official install method (brew cask
  for a GUI app, or an official script/binary for a CLI) before adding -
  this PRD does not assume either exists yet; confirm during
  implementation the same way every prior registry batch did.
- `codegraph`: `kind="github_release"` per the package-manager-policy PRD's
  verified finding (prebuilt binary, no npm) - not `kind="node"` or
  `kind="script"`.

### Linux and Bazzite Requirements

- Reuse the existing "Immutable Linux and Bazzite Requirements" precedent
  from the doctor/catalog refresh PRD: prefer containerized, Homebrew
  (linuxbrew), or userspace paths over native package-manager writes on an
  atomic/immutable distro.
- `podman` already exists in the catalog as the container runtime story for
  Linux/Bazzite where Apple Containers/Docker Desktop are not applicable -
  this PRD does not need to add a new container tool, only make sure the
  new system-tier tools (`zsh`, `oh-my-zsh`) have a real Linux/Bazzite
  install path, not just a macOS one.
- **Correction from an earlier draft, per user review:** the framing "brew
  doesn't need curl on Bazzite" is not accurate - Homebrew's own bootstrap
  is `curl\|bash` on every platform it supports, Linux included
  (verified: Bazzite's own docs still point at the standard curl\|bash
  installer). The real distinction is narrower: Bazzite's base image already
  ships `curl`/`git`/build tooling as part of the OS, so this installer does
  not need to bootstrap those first the way a bare macOS setup sometimes
  does (e.g. Xcode Command Line Tools gating many toolchains). Each
  system-tier tool's *actual* OS-conditional prerequisites must be verified
  individually - "Bazzite needs less setup than macOS" is not a blanket
  rule to apply to every tool in this PRD.

## Design Decisions

### Technical Approach

- Every new tool follows this project's established registry-authoring
  convention: verify the exact install method against the live, current
  release/formula before adding, the same discipline every prior "Registry
  Batch N" plan applied.
- Reuse existing method kinds (`script`, `brew`, `cask`) wherever possible;
  the only new kind is `uv-tool` for `graphify`, and it is a narrow mirror
  of the existing `node` kind.

### Risks

- `antigravity` and `cursor-agent` install methods are unverified as of this
  PRD - they may turn out to need a new method kind (e.g. if `cursor-agent`
  ships only as an npm package with no brew formula and no official script,
  it would face the exact pnpm-bug tradeoff this whole effort is trying to
  avoid).
- ~~Oh-My-Zsh plugin representation~~ resolved in the tier PRD (config-array
  edit, not a `Tool` entry) - no longer a risk here.

## Acceptance Criteria

### Functional Acceptance

- [ ] `zsh`, `oh-my-zsh`, `gnu-bash` (macOS), Apple Containers (macOS),
      `kitty`, `wezterm` install cleanly on macOS via verified live methods.
- [ ] `antigravity`, `cursor-agent` install via a verified official method
      (not assumed) with no pnpm-bug exposure.
- [ ] `codegraph` installs via `kind="github_release"`; `graphify` installs via the
      new `kind="uv-tool"`.
- [ ] Linux/Bazzite has a working shell-setup path (`zsh`/`oh-my-zsh`) and
      relies on the existing `podman` entry for containers.
- [ ] `rtk` installs via `kind="github_release"` from `rtk-ai/rtk`, checksum-
      verified against its release's `checksums.txt`.

### Quality Standards

- [ ] Every new registry entry is verified against its live, current
      release/formula before merging, per this project's established
      convention.
- [ ] New and changed behavior is covered by failing tests before
      implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.

### User Acceptance

- [ ] A fresh macOS machine can go from nothing to a working
      zsh+oh-my-zsh+brew+volta+pnpm system-tier baseline through the
      catalog, with agent-host tools dragging in their prerequisites
      automatically.
- [ ] `codegraph` and `graphify` install reliably, with no pnpm
      global-install data loss.

## Open Questions

1. ~~`rtk`'s repo coordinates and install method~~ **resolved above.**
2. What are `antigravity` and `cursor-agent`'s actual, current install
   methods? Neither was verified during this PRD's research - needs the
   same live-verification pass every prior registry batch did before this
   PRD can be considered ready to implement.
3. Do Oh-My-Zsh plugins need their own catalog entries, per the open
   question in the tier PRD? This PRD's `oh-my-zsh` requirement is written
   generically pending that decision.
4. Is there anything to actually *install* for Apple Containers on a current
   macOS, or is the registry entry purely a version-gate/documentation
   entry (the `container` CLI ships with the OS on recent macOS versions)?
