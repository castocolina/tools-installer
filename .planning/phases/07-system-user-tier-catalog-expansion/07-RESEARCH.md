# Phase 7: System & User Tier Catalog Expansion - Research

**Researched:** 2026-09-06
**Domain:** Declarative registry additions (`installer/registry.toml`) for shell/shell-framework/container-runtime (system tier) and terminal emulators (user tier), across macOS + Linux/Bazzite
**Confidence:** HIGH for install-method facts (verified against live registries/scripts this session); MEDIUM for how D-01's "disabled" rendering should work (the exact mechanism CONTEXT.md assumes does not exist in the form assumed — see Open Questions)

## Summary

This phase adds six registry entries — `zsh`, `oh-my-zsh`, `gnu-bash` (macOS), Apple
Containers, `kitty`, `wezterm` — using patterns already proven in
`installer/registry.toml` (the `podman`/`docker`/`colima`/`watch` immutable-Linux-falls-
to-brew shape, the `sdkman`/`detect_path` shape for non-PATH installs, the `codegraph`/
`dive`/`yq` `github_release` shapes, and the `jetbrains-toolbox`/`claude` `cask` shape).
Five of the six have a clean, already-supported path. One (`kitty` on immutable
Bazzite) hits a real gap in `installer/download.py`'s archive extraction that the
planner must decide how to handle — it is not resolvable by registry data alone.

The most consequential finding is on `oh-my-zsh`: its real `install.sh` (read in full
this session, not summarized from marketing docs) auto-detects a non-TTY stdin (which
this project's `curl | sh` `kind="script"` pipeline always produces) and silently sets
`RUNZSH=no`/`CHSH=no` — but **not** `KEEP_ZSHRC`, which still defaults to `no`. Left at
that default, an unattended install **will back up and overwrite the user's `.zshrc`**
with Oh-My-Zsh's own template, no prompt possible (the confirmation prompt is itself
suppressed by the same non-TTY auto-detection, so it falls straight through to
overwrite). CONTEXT.md's open question ("is `kind="script"` safe as-is") resolves to:
**not as a bare script — safe only with `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC
= "yes" }` explicitly set**, which this project's `script` executor already supports
(`installer/executors.py:334-360`, the same mechanism the `brew` entry already uses for
`NONINTERACTIVE=1`).

The second consequential finding is on Apple Containers: Homebrew's own formula
metadata (not marketing copy) declares hard requirements of `arch: arm64` and `macos:
26`, and there genuinely is an install step (`brew install container`) — SC#4's
"doc/version-gate, nothing to install" framing is **wrong** and should be corrected.
Homebrew is the right path per D-02's brew preference, and it already gates on
`arm64`/`macos` at the `brew` layer; this project's existing `Method.arch`/`Method.os`
fields can express the Apple-Silicon half of that gate today, but there is no
mechanism anywhere in `installer/platform.py`/`installer/resolve.py` for an OS
**version** floor (only OS family + arch) — that part of D-01's "disabled" ask cannot
be expressed today without either accepting a live failure at install time or adding
new gating logic, which is outside a registry-only phase.

**Primary recommendation:** Ship all six entries using the exact TOML shapes below;
explicitly set `oh-my-zsh`'s three env vars rather than relying on the script's
non-TTY auto-detection; install Apple Containers via `kind="brew"` (not a script or
.pkg download); accept and document that `kitty` has no method on immutable
Bazzite until `installer/download.py` gains xz/generic-tar support (out of this
phase's scope), and that `chsh`-driven default-shell changes are avoided project-wide
on Bazzite regardless of platform, following the existing `CHSH=no` convention (which,
per the Bazzite KDE-login-failure finding below, is a correctness requirement there,
not just a style choice).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Shell binary (`zsh`) | System / OS package layer | — | A shell is OS-level infrastructure; installed via native pkg manager or brew, no app logic involved. |
| Shell framework (`oh-my-zsh`) | System / user dotfiles | — | Modifies `~/.zshrc`, a user config file, but is itself a system-tier bootstrap step per this project's existing `tier` taxonomy (Phase 1). |
| `gnu-bash` | System / OS package layer | — | Coexists with macOS's ancient system bash 3.2; pure package install, no app logic. |
| Apple Containers (`container` CLI) | System / OS package layer (brew) | — | A container runtime is system-tier infra like `podman`/`docker`; Homebrew is the install channel, not the app itself. |
| Terminal emulators (`kitty`, `wezterm`) | User tier (app) | System tier (Linux native pkg on non-atomic distros) | End-user personal tool choice — matches this project's existing `tier="user"` label for personal-preference apps (`jetbrains-toolbox`, `sublime`). |
| Catalog "disabled/unavailable" rendering | TUI / `installer/catalog_tui.py` + `installer/deps.py` | CLI / `installer/render.py` | Whatever mechanism ends up representing "unavailable here" is a pure rendering concern layered on top of `resolve_methods`/`resolve_dependencies`, never a second source of truth (`.claude/architecture.md` rule 2/tier rule). |

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 (Apple Containers availability gating):** Apple Containers always appears as a
catalog entry (never omitted), regardless of whether research finds a real install
action or confirms it's a doc/version-gate case (native `container` CLI already
present, nothing to install). If it's unavailable on the current machine (wrong macOS
version, non-Apple-Silicon, etc.), it shows in the catalog **disabled** — reusing this
project's existing unmet-requires/unavailable-dependency display pattern rather than
inventing a new one or hiding the entry entirely. This keeps the System-tier bootstrap
checklist visually complete even when one entry is a no-op or unavailable on this
particular machine.

### Claude's Discretion

- Exact disabled-state rendering for Apple Containers when unavailable — reuse
  whatever `catalog_tui.py`/`ui_common.py` mechanism already renders an unmet-`requires`
  or platform-unavailable tool (per D-01's instruction to reuse, not invent).
- Whether `oh-my-zsh`'s `.zshrc`-rewriting behavior, once read, is safe enough to treat
  as a plain `kind="script"` candidate, or needs a narrower/gated install method — a
  research finding, not a locked decision.
- Exact Linux path per tool (distro package manager vs. the existing GitHub-release
  download path) for `kitty`/`wezterm` — per-tool research call, verified live before
  shipping (this project's registry-authoring convention).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 7 scope.

**Research note on D-01's reuse premise:** see Open Question 1 below — the
"existing unmet-requires/unavailable-dependency display pattern" CONTEXT.md refers to
does not exist as a persistent grayed-out catalog **row**; it exists as (a) a
selection-time status-line notice and (b) a resolve-time skip warning. Neither is a
literal "show disabled while merely browsing" mechanism. The planner needs to pick
which of the two real mechanisms satisfies D-01's intent, or treat this as a
discuss-phase follow-up.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-system-tier-shell-container-entries | `zsh`, `oh-my-zsh` (`requires=["zsh"]`), `gnu-bash` (macOS-only, brew), Apple Containers (macOS-only, native `container` CLI) | Standard Stack + Code Examples below give verified TOML for all four; Open Question 4 (macOS-version gating) and the `oh-my-zsh` env-var finding are the load-bearing details. |
| REQ-terminal-emulator-entries | `kitty`, `wezterm` as user-tier — brew on macOS, Linux via distro package or GitHub-release | Standard Stack + Common Pitfalls: `kitty`/`wezterm` are Homebrew **casks**, not `homebrew-core` formulas (correcting the requirement's own parenthetical); native Linux packages exist for `kitty` everywhere, only partially for `wezterm`; the `.txz`/`.tar.xz` archive-format gap is the key risk. |
| REQ-linux-bazzite-shell-parity | `zsh`/`oh-my-zsh` real Linux/Bazzite path; reuse existing `podman` entry for container-runtime story, not a new one | Confirmed `podman`'s existing methods (`installer/registry.toml:850-870`) already resolve correctly on immutable Bazzite via `resolve.py`'s brew-fallback rule; the same shape works unmodified for `zsh`. `oh-my-zsh` on Bazzite carries an extra pitfall (KDE login breakage via `chsh` — see Common Pitfalls). |
</phase_requirements>

## Standard Stack

### Core

| Entry | Method | Verified Facts |
|-------|--------|-----------------|
| `zsh` | `dnf`/`apt`/`pacman` package `zsh`, `brew` formula `zsh` | `[VERIFIED: formulae.brew.sh formula API]` brew formula `zsh`, stable `5.9.2`, no caveats, cross-platform bottle (checked live this session). `zsh` is a standard distro package on Debian/Fedora/Arch — well-established, not re-verified live here beyond the brew fallback (the fallback is what actually matters on Bazzite). |
| `oh-my-zsh` | `kind="script"`, `url="https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"`, `env={RUNZSH="no", CHSH="no", KEEP_ZSHRC="yes"}`, `requires=["zsh"]`, `detect_path="~/.oh-my-zsh/oh-my-zsh.sh"` | `[VERIFIED: raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh, fetched and read in full this session]` — see Code Examples and Common Pitfalls for the exact lines. |
| `gnu-bash` (macOS) | `kind="brew"`, `formula="bash"` (**not** `"gnu-bash"`) | `[VERIFIED: formulae.brew.sh formula API]` the real Homebrew formula name is `bash`; stable `5.3.15`; caveats mention only `DEFAULT_LOADABLE_BUILTINS_PATH`, no PATH-shadowing warning (macOS's SIP-protected `/bin/bash` is untouched — brew's bash lives at `$HOMEBREW_PREFIX/bin/bash`, coexisting as the requirement expects). `keg_only` is unset. |
| Apple Containers (`container`) | `kind="brew"`, `formula="container"`, `os=["macos"]`, `arch=["arm64"]` | `[VERIFIED: formulae.brew.sh formula API]` a real formula named `container` exists, homepage `apple.github.io/container`, i.e. this **is** Apple's `apple/container` project packaged for brew. Its declared `requirements` array: `{"name":"macos","version":"26"}`, `{"name":"arch","version":"arm64"}`, `{"name":"xcode","version":"26.0","contexts":["build"]}` — a **present** version-floor declaration, not an absence. `[CITED: github.com/apple/container README, fetched this session]` confirms macOS 26 + Apple Silicon are hard requirements ("We do not support older versions of macOS") and that the non-brew path is a signed `.pkg` requiring a GUI double-click install with an admin password — brew is clearly the better path here (D-02). |
| `kitty` | `kind="cask"` (macOS); `kind="dnf"`/`"apt"`/`"pacman"` package `kitty` (Linux, non-atomic) | `[VERIFIED: formulae.brew.sh cask API]` cask token `kitty`, name `kitty`, version `0.48.2` — `formula/kitty.json` returns `404`, confirming there is **no** Linux/macOS formula, only the macOS cask. `[CITED: WebSearch — Debian/Fedora/Arch package pages]` `kitty` is natively packaged as `kitty` on Debian, Fedora, and Arch. |
| `wezterm` | `kind="cask"` (macOS); `kind="pacman"` package `wezterm` (Arch only, native); Linux fallback needed for Debian/Fedora — see Common Pitfalls | `[VERIFIED: formulae.brew.sh cask API]` cask token `wezterm`, name `WezTerm`, version `20240203-110809,5046fc22` — `formula/wezterm.json` also `404`. `[CITED: wezterm.org/install/linux.html + WebSearch]` Debian/Ubuntu requires adding WezTerm's own apt repo (not a stock `apt install`); Fedora requires enabling a COPR (`dnf copr enable wez/wezterm`, not a stock `dnf install`); Arch has `wezterm` in the official `[extra]` repo (plain `pacman -S wezterm` works). |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `installer/status.py`'s `detect_path` field | existing | Marks a tool "installed" via a non-PATH marker file | `oh-my-zsh` (no binary on PATH) — same shape as the existing `sdkman` entry's `detect_path="~/.sdkman/bin/sdkman-init.sh"`. |
| `installer/model.py`'s `Method.arch`/`Method.os` | existing | Platform/arch gating of a single method | Apple Containers' `arch=["arm64"]` — the only piece of D-01's "disabled" ask expressible with existing fields. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `oh-my-zsh` via bare `kind="script"` | Explicit `env` vars (chosen) | Relying on the script's own non-TTY auto-detection (`RUNZSH=no CHSH=no OVERWRITE_CONFIRMATION=no`) is fragile and undocumented at the registry level — a future change to `install.sh`'s TTY-detection logic, or a change to how this project invokes `sh` (e.g. adding a pty), would silently reintroduce interactive prompts or a `.zshrc` overwrite. Explicit `env` is self-documenting and matches the `brew` entry's existing `NONINTERACTIVE=1` precedent. |
| Apple Containers via the signed `.pkg` downloaded from `apple/container`'s GitHub Releases | `kind="brew"` (chosen) | The `.pkg` path requires a GUI double-click + admin password prompt per Apple's own README — fundamentally interactive, and this project has no `kind` that drives a macOS Installer.app-style flow. `brew install container` is fully scriptable and already declares the exact version/arch gate. |
| `kitty` Linux via `kind="github_release"` everywhere | Native `dnf`/`apt`/`pacman` packages (chosen for non-atomic Linux) | `kitty`'s GitHub release Linux assets are `.txz` (LZMA/XZ), which `installer/download.py`'s extraction (`tar -xzf`, hardcoded gzip flag) cannot open — see Common Pitfalls. Native packages sidestep this entirely on non-atomic distros. |
| `wezterm` Linux via distro packages everywhere | `kind="github_release"` with the **AppImage** asset, `raw=true` (recommended for the non-Arch case) | Debian/Fedora have no plain native package (repo/COPR setup needed); the AppImage is a single self-contained executable, so it fits this project's existing `raw=true` single-file download shape (used today by `yq`) and **avoids** the `.txz`/`tar -xzf` archive problem entirely, unlike `wezterm`'s per-distro `.tar.xz` release assets. |

**Installation (reference — the registry entries themselves, not a runtime install
command):**
```bash
# macOS
brew install zsh bash container
brew install --cask kitty wezterm
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended --keep-zshrc

# Linux (non-atomic: Debian/Fedora/Arch)
sudo apt install zsh kitty   # or dnf / pacman
# wezterm: apt needs WezTerm's own repo; dnf needs `dnf copr enable wez/wezterm`; pacman: `pacman -S wezterm` works natively

# Linux (Bazzite/immutable) — native pkg managers are skipped by this project's own
# resolve.py; brew (linuxbrew) is the only path that currently resolves for zsh
brew install zsh
```

**Version verification performed this session:**
- `formulae.brew.sh/api/formula/zsh.json` → `5.9.2`, no caveats `[VERIFIED]`
- `formulae.brew.sh/api/formula/bash.json` → `5.3.15`, no keg-only/PATH caveat `[VERIFIED]`
- `formulae.brew.sh/api/formula/container.json` → present, `requirements: macos>=26, arch=arm64` `[VERIFIED]`
- `formulae.brew.sh/api/cask/kitty.json` → `0.48.2` `[VERIFIED]`; `formulae.brew.sh/api/cask/wezterm.json` → `20240203-110809,5046fc22` `[VERIFIED]`
- `formulae.brew.sh/api/formula/kitty.json` and `.../formula/wezterm.json` → both `404` `[VERIFIED]` (no Linux/macOS formula exists for either — cask-only)
- `api.github.com/repos/apple/container/releases/latest` → `1.3.1`, assets are signed `.pkg` files only, no tarball `[VERIFIED]`
- `api.github.com/repos/kovidgoyal/kitty/releases/latest` → `v0.48.2`, Linux assets are `kitty-0.48.2-{arch}.txz` with `.sig` (GPG) but **no** SHA256SUMS-style checksum file `[VERIFIED]`
- `api.github.com/repos/wezterm/wezterm/releases/latest` → `20240203-110809-5046fc22`, ships a Linux AppImage (`WezTerm-{tag}-Ubuntu20.04.AppImage`) plus per-distro `.deb`/`.tar.xz` `[VERIFIED]`

## Package Legitimacy Audit

This phase does not install anything through the npm/PyPI/crates ecosystems the
Package Legitimacy Gate protocol targets — every new entry is either a Homebrew
formula/cask (Homebrew's own review process), a native Linux distro package, or a
`github_release` binary from the tool's own well-established upstream repository.
The `gsd_run query package-legitimacy check` seam has no ecosystem argument for
`brew`/distro packages, so it was not run; instead, source-repo legitimacy was
checked directly:

| Entry | Source | Stars/Maturity (informal) | Verdict | Disposition |
|-------|--------|---------------------------|---------|-------------|
| `zsh` | distro repos / Homebrew | Decades-old, ubiquitous | OK | Approved |
| `oh-my-zsh` | `github.com/ohmyzsh/ohmyzsh` | ~180k+ stars, de facto standard | OK | Approved |
| `gnu-bash` | Homebrew core (`bash` formula) | Homebrew official | OK | Approved |
| Apple Containers | Homebrew core (`container` formula) + `github.com/apple/container` | Official Apple open-source project | OK | Approved |
| `kitty` | `github.com/kovidgoyal/kitty` + Homebrew cask | Long-established, widely packaged by every major distro | OK | Approved |
| `wezterm` | `github.com/wezterm/wezterm` + Homebrew cask | Long-established, official apt/COPR/AUR presence | OK | Approved |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
registry.toml (data)                     resolve.py (pure)               engine.py / executors.py (effectful)
┌──────────────────────┐   load_tools    ┌──────────────────────┐  resolve_methods  ┌───────────────────────────┐
│ [[tool]] zsh          │ ─────────────▶ │ Tool(id, methods,     │ ────────────────▶ │ pick 1st applicable        │
│ [[tool]] oh-my-zsh    │                │      requires, tier)  │  (ranked ladder:   │ Method by _RANK, run its   │
│ [[tool]] gnu-bash     │                │                       │   script>download>  │ kind's executor (_script,  │
│ [[tool]] container    │                │                       │   native>brew)      │  _brew, _dnf, ...)         │
│ [[tool]] kitty        │                └──────────────────────┘                     └──────────┬────────────────┘
│ [[tool]] wezterm      │                          │                                             │
└──────────────────────┘                           │ Platform (os/arch/immutable/has_brew)        │ InstallOutcome
                                                    │  detected once from live system probes       │ (INSTALLED / NO_METHOD /
                                                    ▼                                              ▼  FAILED / ...)
                                          installer/platform.py::detect()              installer/session.py::run_installs
                                          (dnf-before-apt-before-pacman probe,                       │
                                           /run/ostree-booted marker for Bazzite)                    ▼
                                                                                        installer/render.py
                                                                                        (render_summary / render_skipped /
                                                                                         render_dependency_notice — CLI path)

Selection-time (TUI path, browsing before any install runs):
CatalogScreen._row_cells ──▶ shows priority/id/category/audience/✓installed only
                              (NO platform-availability signal rendered here today)
CatalogScreen._announce_requires ──▶ missing_requires() ──▶ status-line notice
                              (only fires for a *missing catalog-tool dependency*,
                               not for "this tool itself has no method here")
```

### Recommended Project Structure

No new files needed — all six entries are additive `[[tool]]` blocks in
`installer/registry.toml`, following the existing sectioning (grouped near `podman`
for the container-runtime entry, near `jetbrains-toolbox`/`sublime` for the terminal
casks, and as new standalone `shell` blocks for `zsh`/`oh-my-zsh`/`gnu-bash`).

### Pattern 1: Immutable-Linux-falls-to-brew (reuse for `zsh`)

**What:** Declare native-manager methods (`dnf`/`apt`/`pacman`) with no `os` field
plus a `brew` method; `resolve.py`'s existing `_applies()` already skips every native
method when `platform.immutable` is true, leaving only `brew`.
**When to use:** Any system-tier tool that is a plain userspace package on every
distro (no compiled-from-source step, no kernel module).
**Example (verified against the real, already-shipped `podman` entry):**
```toml
# Source: installer/registry.toml:850-870 (existing podman entry, read this session)
[[tool]]
id = "podman"
name = "Podman"
category = "docker"
cmd = "podman"
priority = "P1"
audience = "both"
tier = "system"
desc = "Rootless container engine often safer on Linux and immutable desktops than daemon-first workflows."
[[tool.method]]
kind = "dnf"
package = "podman"
[[tool.method]]
kind = "apt"
package = "podman"
[[tool.method]]
kind = "pacman"
package = "podman"
[[tool.method]]
kind = "brew"
formula = "podman"

# New zsh entry — identical shape, verified via resolve_methods against
# Platform(os="fedora", arch="amd64", immutable=True, has_brew=True):
# only the brew method survives, matching podman/colima/watch's already-tested behavior
# (tests/test_registry.py:189-195, 211-214).
[[tool]]
id = "zsh"
name = "Zsh"
category = "shell"
cmd = "zsh"
priority = "P1"
audience = "both"
tier = "system"
desc = "Feature-rich shell; prerequisite for Oh-My-Zsh."
[[tool.method]]
kind = "dnf"
package = "zsh"
[[tool.method]]
kind = "apt"
package = "zsh"
[[tool.method]]
kind = "pacman"
package = "zsh"
[[tool.method]]
kind = "brew"
formula = "zsh"
```

### Pattern 2: `detect_path` for a non-PATH marker (reuse for `oh-my-zsh`, mirrors `sdkman`)

**What:** `installer/status.py::is_installed` checks `shutil.which(tool.cmd)` first,
then falls through to any method's `detect_path` (a file-existence check via
`Path(...).expanduser().exists()`).
**When to use:** Any tool whose successful install leaves no PATH binary (`sdkman`,
now `oh-my-zsh`).
**Example (verified — the real, already-shipped `sdkman` entry):**
```toml
# Source: installer/registry.toml:1314-1328 (existing sdkman entry, read this session)
[[tool]]
id = "sdkman"
...
cmd = "sdkman-init.sh"
[[tool.method]]
kind = "script"
url = "https://get.sdkman.io?ci=true"
shell = "bash"
bin_dir = "~/.sdkman/bin"
detect_path = "~/.sdkman/bin/sdkman-init.sh"

# New oh-my-zsh entry, same shape:
[[tool]]
id = "oh-my-zsh"
name = "Oh My Zsh"
category = "shell"
cmd = "omz"
priority = "P2"
audience = "both"
tier = "system"
requires = ["zsh"]
desc = "Zsh configuration framework; installs into ~/.oh-my-zsh and edits .zshrc."
[[tool.method]]
kind = "script"
url = "https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh"
shell = "sh"
env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }
detect_path = "~/.oh-my-zsh/oh-my-zsh.sh"
```
Note: `cmd = "omz"` will not resolve via `which` for most users (the `omz` CLI wrapper
is a newer Oh-My-Zsh addition, sourced into the shell rather than always symlinked onto
PATH) — `detect_path` is what actually makes `is_installed` true here, exactly as it
is the load-bearing check for `sdkman` today (per that entry's own `# Verified
2026-09-06` comment at `installer/registry.toml:1297-1313`, which explicitly documents
that `detect_path` is how a brownfield pre-existing install is recognized).

### Pattern 3: `raw=true` single-file GitHub release (reuse for `wezterm`'s AppImage)

**What:** `installer/download.py::_resolve_target` + `_install_unverified`/`_place_verified`
skip archive extraction entirely when `method.params["raw"] is True` — the asset is
`chmod +x`'d and symlinked directly.
**When to use:** A release that ships a self-contained single binary or AppImage.
**Example (verified — the real, already-shipped `yq` entry):**
```toml
# Source: installer/registry.toml:423-437 (existing yq entry, read this session)
[[tool.method]]
kind = "github_release"
os = ["debian", "arch", "fedora"]
repo = "mikefarah/yq"
asset = "yq_linux_{arch.deb}"
member = "yq"
raw = true

# Candidate wezterm Linux fallback (Debian/Fedora only — Arch already has a native
# pacman package and does not need this):
[[tool.method]]
kind = "github_release"
os = ["debian", "fedora"]
repo = "wezterm/wezterm"
asset = "WezTerm-{ver}-Ubuntu20.04.AppImage"
member = "wezterm"
raw = true
```
No `checksum` field is set — `wezterm`'s GitHub releases do not publish a
SHA256SUMS-style file for this asset (only per-asset `.sha256` sidecars named
`{asset}.sha256`, which **do** fit this project's `checksum = "{asset}.sha256sum"`-
style templating used by `deno`'s entry — re-verify the exact sidecar naming
(`.sha256` vs `.sha256sum`) live before shipping, since it was not independently
re-confirmed against the templating engine's exact suffix expectations this
session).

### Anti-Patterns to Avoid

- **Treating `oh-my-zsh`'s `install.sh` as safe by default:** Do not ship
  `kind="script"` with no `env` table. The script's own non-TTY auto-detection
  happens to suppress `RUNZSH`/`CHSH`/`OVERWRITE_CONFIRMATION`, but `KEEP_ZSHRC`
  defaults to `no` regardless — an unattended run **will** overwrite `.zshrc` (backed
  up, but still replaced) unless `KEEP_ZSHRC=yes` is set explicitly.
- **Running `chsh`/setting zsh as the login shell on Bazzite:** community reports
  (see Common Pitfalls) tie `chsh`-to-zsh with KDE/SDDM login failures on Bazzite
  specifically. `CHSH=no` is a correctness requirement there, not a style choice.
- **Assuming `kitty`/`wezterm` are "in homebrew-core"** (as REQUIREMENTS.md's own
  phrasing suggests): both are Homebrew **casks** (macOS-only GUI-app bundles), a
  different tap/mechanism from `homebrew-core` formulas. There is no Linux Homebrew
  path for either.
- **Reusing `tar -xzf` for `kitty`'s Linux release assets:** they are `.txz`
  (LZMA/XZ), not gzip; `installer/download.py`'s extraction is hardcoded to `-xzf`
  and will fail on this asset. See Common Pitfalls.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting "already installed" for a tool with no PATH binary | A bespoke marker file / new field | `Method.detect_path` (already exists, already tested for `sdkman`) | One mechanism, one code path, one set of tests (`tests/test_status.py`). |
| Gating Apple Containers to Apple Silicon | A new arch-detection helper | `Method.arch = ["arm64"]` (already exists, already tested via `resolve.py::_applies`) | `resolve_methods` already filters on `method.arch` against `platform.arch`; a bespoke check would duplicate this. |
| Skipping native package managers on Bazzite | A new "is this Bazzite" check on each new tool | Nothing — `resolve.py::_applies` already returns `False` for every native-manager kind when `platform.immutable` is true, for every tool in the registry, unconditionally | This is generic, tool-agnostic logic already in place; the podman/colima/watch tests prove it. |

**Key insight:** Every "problem" this phase's tools present at first glance —
non-PATH detection, arch gating, immutable-distro fallback — already has a
proven, tested mechanism in this codebase. The only genuinely new territory is (a)
oh-my-zsh's non-default-safe script behavior, which needs a **specific set of `env`
values**, not new code, and (b) `kitty`'s Bazzite gap, which is a real limitation
of the current `download.py`, not something a registry entry can work around.

## Common Pitfalls

### Pitfall 1: `oh-my-zsh`'s default unattended behavior still overwrites `.zshrc`

**What goes wrong:** A bare `kind="script"` entry silently replaces the user's
existing `~/.zshrc` with Oh-My-Zsh's own template (backed up to
`.zshrc.pre-oh-my-zsh`, but still replaced — losing any customization not yet backed
up elsewhere) on every unattended run, because `KEEP_ZSHRC` defaults to `no` and is
**not** touched by the script's non-TTY auto-detection.
**Why it happens:** `install.sh`'s `main()` (lines 539-543, read verbatim this
session) only sets `RUNZSH=no; CHSH=no; OVERWRITE_CONFIRMATION=no` when `[ ! -t 0 ]`.
`OVERWRITE_CONFIRMATION=no` then makes `setup_zshrc` (lines 364-369) skip straight
past the "Do you want to overwrite?" prompt and fall through to the unconditional
backup-and-replace block below it — it does not mean "don't overwrite," it means
"don't ask before overwriting."
**How to avoid:** Set `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }`
explicitly on the registry entry (belt-and-suspenders with the auto-detection, and
the only way to actually preserve an existing `.zshrc`).
**Warning signs:** A test or manual verification that installs `oh-my-zsh` against a
`HOME` with a pre-existing non-trivial `.zshrc` and asserts the file is byte-identical
afterward (or explicitly asserts a `.zshrc.pre-oh-my-zsh` backup was NOT created,
proving `KEEP_ZSHRC` took effect) is the concrete check this needs.

### Pitfall 2: `kitty`'s Linux release assets are `.txz`, incompatible with this project's extraction

**What goes wrong:** A `github_release` method for `kitty` on Linux
(`kitty-{ver}-x86_64.txz`) would be silently broken: `installer/download.py`'s
`_install_unverified`/`_place_verified` both hardcode `tar -xzf` (`-z` = gzip only,
`installer/download.py:146` and `:206`), and `.txz`/`.tar.xz` is XZ/LZMA-compressed —
`tar -xzf` on this file fails with a decompression error.
**Why it happens:** No registry entry to date has needed anything but gzip
(`.tar.gz`)/zip archives, so `archive` only special-cases `"zip"`; there is no `"txz"`/
generic-`tar -xf` branch.
**How to avoid:** Do not add a `kitty` `github_release` method until
`installer/download.py` gains xz support (out of a registry-only phase's scope) —
or, since native `kitty` packages already exist on Debian/Fedora/Arch (verified via
distro package pages this session), simply accept that `kitty` has **no** available
method on immutable Bazzite specifically (native managers are skipped there by
design) and document that as a known limitation. REQ-linux-bazzite-shell-parity does
not name `kitty`/`wezterm` — only `zsh`/`oh-my-zsh` — so this gap does not violate
any Phase 7 success criterion, but it should be recorded, not silently absent.
**Warning signs:** A `resolve_methods` call for `kitty` against
`Platform(immutable=True, has_brew=False or True)` returning an empty list (no
`brew` fallback exists for `kitty` on Linux either — confirmed via the `404` on
`formula/kitty.json`).

### Pitfall 3: `chsh`-driven shell changes can break KDE login on Bazzite

**What goes wrong:** Community reports (`ublue-os/bazzite` issue #4159, read this
session) describe `chsh`-ing to zsh, or even just sourcing zsh at the bottom of
`.bashrc`, causing KDE/SDDM to fail to log in after the next reboot.
**Why it happens:** Not fully diagnosed upstream (the reporter did not share
session logs), but it is a real, named risk specific to Bazzite's desktop-session
bootstrap, not a generic Linux zsh issue.
**How to avoid:** `CHSH=no` (already required by Pitfall 1's fix) is a correctness
requirement on Bazzite, not just a"quieter install" preference — never let a future
edit relax it thinking it only affects interactivity.
**Warning signs:** None the installer can detect programmatically; this is a
documentation/comment-level warning (`# Verified {date}: ...`) rather than a
runtime check.

### Pitfall 4: No mechanism exists to gate on a minimum OS **version**

**What goes wrong:** Apple Containers requires macOS 26+ specifically (not just
"macOS" as a family), but `installer/platform.py::Platform` only carries `os`
(`"macos"`/`"debian"`/`"arch"`/`"fedora"`), `arch`, `immutable`, and `has_brew` — no
version field at all. `Method.os`/`Method.arch` can express "macOS + arm64" but not
"macOS 26+."
**Why it happens:** No prior registry entry needed an OS-version floor; every
existing `os=["macos"]` gate is version-agnostic.
**How to avoid:** Accept that this version floor is enforced only by Homebrew itself
at `brew install container` time (Homebrew's own `requirements` metadata already
declares it, confirmed this session) — the failure will be a clear brew error, not a
silent success. Do not attempt to build a new OS-version-detection mechanism inside
this phase; that is a bigger change than a registry-only phase should carry, and
duplicates a check Homebrew already performs correctly.
**Warning signs:** If the planner is tempted to add a `min_os_version` field to
`Method`, treat that as a scope-creep signal — flag it for discuss-phase rather than
slipping it into this phase's plan.

## Code Examples

### Verified `oh-my-zsh` env-var behavior (from the actual script, not docs)

```sh
# Source: raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh
# fetched and read in full this session (603 lines)
CHSH=${CHSH:-yes}
RUNZSH=${RUNZSH:-yes}
KEEP_ZSHRC=${KEEP_ZSHRC:-no}
OVERWRITE_CONFIRMATION=${OVERWRITE_CONFIRMATION:-yes}
...
main() {
  # Run as unattended if stdin is not a tty
  if [ ! -t 0 ]; then
    RUNZSH=no
    CHSH=no
    OVERWRITE_CONFIRMATION=no
  fi
  ...
  if ! command_exists zsh; then
    echo "Zsh is not installed. Please install zsh first."
    exit 1
  fi
  if [ -d "$ZSH" ]; then
    echo "The \$ZSH folder already exists ($ZSH)."
    ... exit 1   # NOT idempotent — a second run against an existing $ZSH fails
  fi
```

### Verified `Method.arch`/`Method.os` gating (existing mechanism, `resolve.py`)

```python
# Source: installer/resolve.py:32-52 (read in full this session)
def _applies(method: Method, platform: Platform) -> bool:
    if method.os and platform.os not in method.os:
        return False
    if method.arch and platform.arch not in method.arch:
        return False
    ...
    if kind == "brew":
        return platform.has_brew
    ...
    if kind == "rpm_ostree":
        return False  # always skipped by default
    # native package managers (dnf/apt/pacman):
    if platform.immutable:
        return False  # skip the native step on immutable distros
    return _NATIVE_OS[kind] == platform.os
```
This is the exact mechanism that already makes `zsh`'s `dnf`/`apt`/`pacman` methods
correctly resolve to only `brew` on Bazzite, with zero new code needed.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| REQUIREMENTS.md's assumption that Apple Containers "may be a version-gate/doc entry with nothing to actually install" | Confirmed: it **does** require a real install step (`brew install container`); the "doc entry" framing is wrong | Corrected this session via Homebrew's own formula metadata + `apple/container`'s README | The plan must include a real `[[tool.method]] kind="brew"` block, not a no-op/doc-only entry — this changes SC#4's resolution. |
| REQUIREMENTS.md's parenthetical "brew on macOS (both in homebrew-core)" for `kitty`/`wezterm` | Both are Homebrew **casks**, a separate tap/mechanism from `homebrew-core` formulas | Corrected this session via the brew formula/cask API (`formula/*.json` → 404, `cask/*.json` → 200) | Registry entries must use `kind="cask"`, not `kind="brew"`, for the macOS methods. |
| "brew doesn't need curl on Bazzite" (an earlier draft's claim, already flagged as wrong in REQUIREMENTS.md itself) | Homebrew's bootstrap is `curl|bash` everywhere, including Bazzite; Bazzite's base image just already ships `curl`/`git` | Already corrected upstream in REQUIREMENTS.md, reaffirmed here — no new finding, just confirming the requirement text is self-consistent with what was found this session. | No registry impact; noted for completeness. |

**Deprecated/outdated:** None — all six tools are current, actively maintained
projects with no legacy-vs-current install-method split.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `wezterm`'s per-asset `.sha256` sidecar naming is compatible with this project's `checksum = "{asset}.sha256sum"`-style templating without modification | Code Examples, Pattern 3 | If the exact suffix differs (`.sha256` vs `.sha256sum` vs a shared `SHA256SUMS`), the `github_release` method's checksum step will raise `ExecutorError("cannot build checksum name...")` at install time rather than resolving silently — caught immediately, not a silent security gap, but should be re-verified live before shipping. |
| A2 | `oh-my-zsh`'s `cmd = "omz"` is a reasonable catalog display command even though `detect_path` (not `which omz`) is what actually drives `is_installed` | Code Examples, Pattern 2 | Low risk — `cmd` only affects the `is_installed` fast-path and catalog display; `detect_path` is a fallback specifically for this case and is exercised by the existing `sdkman` precedent. |
| A3 | D-01's "existing unmet-requires/unavailable-dependency display pattern" refers to the selection-time status-line notice (`_announce_requires`) and/or the resolve-time skip warning (`resolve_dependencies`'s "not available on this platform — skipped"), since no persistent per-row "disabled" render exists in `catalog_tui.py` today | Open Questions #1, User Constraints research note | If the planner (or discuss-phase) intended an actual grayed-out row while merely browsing, this is new UI work, not reuse — could change the phase's plan shape materially. |

## Open Questions

1. **What exactly should "Apple Containers shows disabled" look like, given no
   platform-availability row-render exists today?**
   - What we know: `catalog_tui.py::CatalogScreen._row_cells` renders only
     priority/id/category/audience/installed-checkbox/desc (verified by reading the
     full file this session) — there is no platform-availability signal in any row
     today. The two real "unavailable" surfaces that DO exist are (a)
     `_announce_requires`'s status-line notice, which fires only for a *missing
     catalog-tool dependency* at selection time, and (b)
     `resolve_dependencies`'s "`{tool.id} is not available on this platform —
     skipped`" warning, surfaced via `render_dependency_notice` on the CLI
     (post-selection) path, not inside the TUI's browsing screen at all.
   - What's unclear: Whether D-01 intends a new row-level render (contradicting its
     own "reuse, don't invent" framing) or is satisfied by one of the two existing
     surfaces firing when the user actually selects/attempts Apple Containers on an
     unsupported machine.
   - Recommendation: Surface this explicitly to the planner/discuss-phase before
     committing to a specific UI change; the cheapest correct answer is probably "no
     new render — `Method.arch=["arm64"]` already makes `resolve_methods` return
     empty on Intel, which already produces a `NO_METHOD` outcome exactly like every
     other platform-unavailable tool in this codebase; that IS what D-01's 'reuse'
     language points at, once the specific mechanism is named precisely."

2. **Exact `wezterm` AppImage checksum sidecar naming.**
   - What we know: the GitHub release lists `WezTerm-{tag}-Ubuntu20.04.AppImage.sha256`
     alongside the AppImage asset itself (confirmed via the GitHub API asset list this
     session).
   - What's unclear: whether this project's `checksum` templating (`"{asset}.sha256sum"`
     style, used by `deno`) needs an exact-suffix match or supports arbitrary
     templates — this was read in `download.py` but the templating's suffix
     flexibility was not independently exercised against this specific asset this
     session.
   - Recommendation: Verify live (`checksum = "{asset}.sha256"`) at plan/execution
     time — a one-line registry change either way, not a design question.

3. **Should `kitty`'s Bazzite gap be silently accepted, or should it prompt a
   `installer/download.py` archive-format enhancement in this phase?**
   - What we know: the gap is real and reproducible from the code alone (no live
     Bazzite machine needed to confirm `tar -xzf` can't open a `.txz`).
   - What's unclear: whether the planner considers "no method on immutable Bazzite"
     acceptable for a user-tier personal-preference tool (unlike `zsh`/`oh-my-zsh`,
     which have an explicit Bazzite-parity requirement), or whether it's worth a
     small `download.py` change (e.g., swapping `tar -xzf` for `tar -xf`, which
     auto-detects compression and is a strict superset of the current gzip-only
     behavior) even though it's not explicitly required by REQ-linux-bazzite-shell-parity.
   - Recommendation: Treat as in-scope only if trivial (a one-line `tar -xzf` →
     `tar -xf` change with matching test coverage per Non-Negotiable Rule 7); do not
     let it block shipping the other five entries.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Homebrew (macOS) | `gnu-bash`, Apple Containers, `kitty`, `wezterm` casks | Not probed on this research machine (macOS host, but this phase ships registry data, not a live install) | — | N/A — brew's own presence is already gated by the existing `has_brew`/`brew` system-tier entry; no new fallback needed. |
| Network access to `raw.githubusercontent.com`, `formulae.brew.sh`, `api.github.com` | All live verification performed this session | Available (used successfully throughout this research session) | — | — |

No blocking missing dependencies — this phase is registry-only; nothing in the phase
itself requires a new external tool beyond what `installer/executors.py` already
supports (`brew`, `dnf`, `apt`, `pacman`, `script`, `github_release`, `cask`).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (`uv run pytest --cov`, per `Makefile:47-48`) |
| Config file | `pyproject.toml` (pytest/coverage config) |
| Quick run command | `uv run pytest tests/test_registry.py tests/test_resolve.py tests/test_status.py tests/test_omz.py -q` |
| Full suite command | `make test` (`uv run pytest --cov`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-system-tier-shell-container-entries | `zsh` resolves to native pkg managers on non-atomic Linux and to `brew` on Bazzite | unit | `uv run pytest tests/test_resolve.py -k zsh -x` | ❌ Wave 0 (new test, mirrors `test_container_tools_resolve_on_immutable_linux_without_native_writes`, `tests/test_registry.py:189-195`) |
| REQ-system-tier-shell-container-entries | `oh-my-zsh`'s script method carries `env={RUNZSH:no,CHSH:no,KEEP_ZSHRC:yes}` and `requires=["zsh"]` | unit | `uv run pytest tests/test_registry.py -k oh_my_zsh -x` | ❌ Wave 0 (new test; mirror the shape of `test_java_and_sdkman_entries_record_the_sc2_no_pin_verification`) |
| REQ-system-tier-shell-container-entries | Apple Containers resolves only on `os=macos, arch=arm64` | unit | `uv run pytest tests/test_resolve.py -k container -x` | ❌ Wave 0 (new test — assert empty method list on an Intel-Mac `Platform` fixture) |
| REQ-terminal-emulator-entries | `kitty`/`wezterm` cask methods only apply on macOS; Linux methods resolve per distro | unit | `uv run pytest tests/test_resolve.py -k "kitty or wezterm" -x` | ❌ Wave 0 (new test) |
| REQ-linux-bazzite-shell-parity | `zsh` (and, if kept, `oh-my-zsh`'s brew fallback if ever added) resolve on an immutable-Fedora `Platform` fixture | unit | `uv run pytest tests/test_registry.py -k immutable -x` | ✅ pattern exists (`tests/test_registry.py:189-195`, `211-214`) — extend, don't duplicate |
| Registry-authoring verification checklist compliance | Each new entry's `# Verified {date}: ...` comment contains the load-bearing finding | unit (substring assertion) | `uv run pytest tests/test_registry.py -k verified_comment -x` | ❌ Wave 0 (new test per entry, mirroring `test_mmdc_entry_records_the_brew_rejection_finding`, `test_codegraph_entry_records_the_no_brew_formula_finding`) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_registry.py tests/test_resolve.py tests/test_status.py -q`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_resolve.py` — needs new cases for `zsh`, `container` (Apple
      Containers), `kitty`, `wezterm` resolving correctly per `Platform` fixture
      (macOS/arm64, macOS/amd64 for the container arch-gate negative case,
      immutable-Fedora, non-atomic Debian/Fedora/Arch)
- [ ] `tests/test_registry.py` — needs `# Verified {date}: ...` comment-substring
      assertions for each of the six new entries, per the existing
      `test_mmdc_entry_records_the_brew_rejection_finding` /
      `test_codegraph_entry_records_the_no_brew_formula_finding` pattern
- [ ] `tests/test_status.py` — needs a case confirming `oh-my-zsh`'s `detect_path`
      makes `is_installed` true without a PATH binary, mirroring the existing
      `sdkman` case
- [ ] No framework install needed — pytest is already fully wired

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in this phase. |
| V3 Session Management | no | N/A. |
| V4 Access Control | no | N/A — no privilege boundary introduced beyond `sudo dnf/apt/pacman` (already an existing pattern for every native-package tool in this registry). |
| V5 Input Validation | yes | `installer/model.py::load_tools` already validates every new `[[tool]]`/`[[tool.method]]` block (unknown `kind`, malformed `os`/`arch` lists, etc.) at load time — no new validation code needed, the existing loader covers these entries automatically. |
| V6 Cryptography | yes (partial) | `github_release`-kind entries verify SHA256 checksums when a `checksum` field is present (`installer/checksums.py`); `kitty`'s Linux release has no SHA256SUMS-style file (only GPG `.sig`), so **any** future `kitty` `github_release` method would be unverified by design — flagged in Common Pitfalls #2, not newly introduced here since no such method is being added this phase for the reasons given there. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `curl \| sh` script installs (oh-my-zsh, existing brew/sdkman pattern) fetching over plain HTTPS with no signature/checksum verification of the script itself | Tampering | Already this project's accepted, existing pattern for every `kind="script"` entry (brew, sdkman, claude, codex) — not a new risk introduced by `oh-my-zsh`; `-fsSL` + HTTPS is the existing baseline, no registry-level mitigation beyond what's already standard here. |
| A registry-declared `env` table reaching the shell verbatim | Tampering / Injection | Already mitigated: `installer/executors.py::_env_prefix` shell-quotes every value (`shlex.quote`); keys come only from the trusted registry, not user input. `oh-my-zsh`'s three new env keys (`RUNZSH`/`CHSH`/`KEEP_ZSHRC`) pass through this exact, already-tested path. |
| Unverified binary execution (`kitty`/`wezterm`/Apple Containers via `github_release` with no checksum, or brew/cask without this project's own verification) | Tampering | Brew/cask installs rely on Homebrew's own supply-chain trust (out of this project's threat model, consistent with every existing `brew`/`cask` entry); a `wezterm` AppImage `github_release` fallback should carry its `.sha256` sidecar (see Open Question 2) to stay consistent with this project's existing download-verification bar. |

## Sources

### Primary (HIGH confidence)
- `raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh` — fetched and
  read in full this session (603 lines); env-var defaults, non-TTY auto-detection,
  `.zshrc` overwrite logic, idempotency failure mode all quoted verbatim above.
- `formulae.brew.sh/api/formula/{zsh,bash,container,kitty,wezterm}.json` and
  `formulae.brew.sh/api/cask/{kitty,wezterm}.json` — live Homebrew API queries this
  session (exact JSON fields quoted above).
- `api.github.com/repos/{apple/container,kovidgoyal/kitty,wezterm/wezterm}/releases/latest`
  — live GitHub Releases API queries this session (asset lists quoted above).
- `installer/registry.toml` (this repo) — `podman` (:850-870), `sdkman`
  (:1314-1328), `codegraph` (:1225-1266), `yq` (:423-443), `jetbrains-toolbox`
  (:1737-1750) entries read directly, line numbers cited.
- `installer/resolve.py`, `installer/platform.py`, `installer/status.py`,
  `installer/model.py`, `installer/download.py`, `installer/executors.py`,
  `installer/deps.py`, `installer/catalog_tui.py`, `installer/omz.py`,
  `installer/render.py` (this repo) — read directly, line numbers cited throughout.
- `.claude/architecture.md` (this repo) — read in full; "Registry-authoring
  guidelines" section quoted for the `# Verified {date}: ...` comment convention.
- `tests/test_registry.py`, `tests/test_resolve.py` (this repo) — read for existing
  test shapes to mirror (immutable-Linux resolution, verified-comment assertions).

### Secondary (MEDIUM confidence)
- `github.com/apple/container` README — fetched via WebFetch this session
  (installation method, system requirements quoted).
- WebSearch results confirming `kitty` package availability on Debian/Fedora/Arch,
  and `wezterm`'s per-distro install story (official apt repo, COPR, Arch `[extra]`).
- `github.com/ublue-os/bazzite` issue #4159 — fetched via WebFetch this session
  (KDE login failure report tied to `chsh`/zsh on Bazzite).

### Tertiary (LOW confidence)
- None used as load-bearing claims — every non-obvious factual claim above was
  either read directly from source (script/code) or confirmed via a live API call
  this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every install method was confirmed against a live
  authoritative source this session (brew API, GitHub Releases API, or this
  project's own already-shipped registry entries).
- Architecture: HIGH — every reused pattern (`detect_path`, `Method.arch`/`os`,
  immutable-Linux brew fallback, `raw=true` single-file download) was read directly
  from this repo's source and its existing tests.
- Pitfalls: HIGH for `oh-my-zsh` and the `.txz` archive-format gap (both derived
  directly from source code, not inference); MEDIUM for the Bazzite KDE-login
  report (a single community bug report, not independently reproduced).

**Research date:** 2026-09-06
**Valid until:** 30 days (stable, mature upstream projects; re-verify brew
formula/cask versions and GitHub release asset names if this research is consumed
significantly later than that, per this project's own "re-verify if materially
changed" convention already used in the `codegraph`/`sdkman` comments).
