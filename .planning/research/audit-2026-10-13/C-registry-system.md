# Audit C — system-tier registry entries (26 tools)

**Date:** 2026-10-13 · **Auditor:** registry auditor C (read-only) · **Branch:** `gsd/phase-16-…` @ 7861ced

**Scope:** uv, brew, starship, zsh, oh-my-zsh, gnu-bash, direnv, gum, lazydocker, watch, docker, podman, colima, container, dive, deno, sdkman, java, groovy, springbootcli, gradle, maven, bun, pnpm, volta, fnm.

## What was verified, and how

| Evidence | How |
|---|---|
| **Resolver matrix (live code)** | A read-only probe loaded `installer/registry.toml` through `load_tools` and called `resolve.resolve_methods` and `unavailable_reason` with synthetic `Platform` objects. Cells: macOS arm64/amd64 (with and without brew, plus os_version 15.5 vs 26.0); debian, fedora and arch, each amd64/arm64, with and without brew; fedora-immutable amd64/arm64 with and without brew. Script: `/tmp/claude-1000/auditC/probe.py`. |
| **Live host (Bazzite, fedora-immutable amd64, has_brew)** | A read-only probe called `is_installed`, `read_inventory`, `resolve_ownership` (with the real `run_probe`), `_version_argv` and `_probed_version`, `plan_uninstall`, `classify_tools` (fallback hint, no seam), `removal_hint` and `removal_label` for all 26 tools. Script: `/tmp/claude-1000/auditC/live.py`; output: `live.out`. |
| **github_release assets (live)** | `gh api repos/<repo>/releases/latest` for starship, direnv, gum, lazydocker, dive and deno. Every asset and checksum name was rendered through the real `assets.render_asset` for amd64 and arm64. Tarball layouts were listed with `curl … \| tar -tz` (nothing was extracted to the system). |
| **Homebrew formulae (live)** | `formulae.brew.sh/api/formula/<f>.json`: bottles per platform, `requirements`, caveats, service. |
| **Fedora packages (live)** | `mdapi.fedoraproject.org/f43` for docker, moby-engine, docker-cli, podman, zsh and procps-ng. |
| **Vendor install scripts (downloaded to scratch and read, never run)** | Homebrew install.sh, astral uv, bun, get.pnpm.io, get.volta.sh, fnm, get.sdkman.io (`SDKMAN_VERSION=5.23.2`), ohmyzsh install.sh. |
| **Docs (WebFetch / WebSearch)** | podman.io installation, docs.volta.sh getting-started, Homebrew 7.0.0 Intel Tier-3 news, macOS `/usr/bin/java` stub reports. |
| **Not verified live** | Actual installs/uninstalls (forbidden). Behaviour of `sudo` prompts inside the Textual app was inferred from code (`StreamingRunner` uses `stdin=DEVNULL`; `run_interactive_command` has no callers), not reproduced. |

## Resolver matrix (methods in ladder order; `NONE` = no method)

Linux arm64 cells match amd64 for every tool, so only one arch is shown per distro; "+brew" means `has_brew=True`.

| tool | mac-arm64 | mac-amd64 | debian | debian+brew | fedora | arch | fedora-immutable | fedora-immutable+brew |
|---|---|---|---|---|---|---|---|---|
| uv | script>brew | script>brew | script | script>brew | script | script | script | script>brew |
| brew | script | script (wrong bin_dir) | script | script | script | script | script | script |
| starship / direnv / gum / lazydocker / dive / deno | github_release>brew | github_release>brew | github_release | github_release>brew | github_release | github_release | github_release | github_release>brew |
| zsh / watch / docker / podman | brew (none without brew) | brew (none without brew) | apt | apt>brew | dnf | pacman | **NONE** | brew |
| oh-my-zsh / sdkman | script | script | script | script | script | script | script | script |
| gnu-bash | brew | brew | NONE (by design) | NONE | NONE | NONE | NONE | NONE |
| colima | brew (none without brew) | brew | **NONE** | brew | **NONE** | **NONE** | **NONE** | brew |
| container | brew (needs macOS 26) | NONE (arm64 only) | NONE | NONE | NONE | NONE | NONE | NONE |
| java / groovy / springbootcli / gradle / maven | sdkman | sdkman | sdkman | sdkman | sdkman | sdkman | sdkman | sdkman |
| bun / pnpm | script>brew | script>brew | script | script>brew | script | script | script | script>brew |
| volta / fnm | brew (none without brew) | brew (none without brew) | script | script>brew | script | script | script | script>brew |

**Cells with no method, and whether that is acceptable:**

- **gnu-bash on Linux; container off macOS-26 arm64.** Acceptable. Linux already ships bash 5, and Apple's runtime requires macOS 26 on arm64.
- **zsh/watch/docker/podman on fedora-immutable without brew.** Acceptable. Bazzite and Silverblue ship zsh, watch and podman in the image (podman.io lists Silverblue as "Built-in"). docker is genuinely unavailable there until brew is present.
- **colima on Linux without brew.** Acceptable as data: Homebrew is the only declared route. The catalog marks it installable because `platform_could_support` assumes brew. It still fails in the same run that installs brew (cross-cutting gap G3).
- **volta/fnm on macOS without brew.** **Not acceptable for volta.** `get.volta.sh` handles Darwin, Volta's docs say the curl command works on macOS, and v2.0.2 publishes `volta-2.0.2-macos.tar.gz`. The registry comment at `registry.toml:2009-2013` ("Homebrew only… do not invent an unpublished macOS script URL") is factually wrong. For fnm it is acceptable: the vendor script delegates to brew on macOS unless `--force-no-brew`.
- **brew on mac-amd64.** It resolves, but `bin_dir=/opt/homebrew/bin` is the Apple Silicon path. The comment is already in the registry; this maps to 999.3.

## Matrix

Verdicts: **OK**, **minor**, **major** (a lifecycle step is missing or wrong, so the tool is non-functional or a wrong or destructive removal instruction is shown), **blocker** (the install cannot happen or the wrong action is taken).

| tool | install coverage (missing cells) | detect / version / owner | uninstall now → correct? | configure needs (met?) | health detectable? | verdict |
|---|---|---|---|---|---|---|
| uv | all | ✓ / ✓ probe, no "latest" (script) / installer direct (live) | managed, "own installer" hint → needs L3 recipe | vendor script edits rc (`. ~/.local/bin/env`), which duplicates the managed PATH (partly met) | no | minor |
| brew | all; Intel bin_dir wrong | ✓ / ✓ / **unknown on Linux (live) and Intel Mac** | managed, generic hint → L3 (`uninstall.sh`), ask | no `brew shellenv` (PATH only, partly met) | no | **major** |
| starship | all | ✓ / ✓ github / installer direct (live) | removable, L2 ✓ (F1 caveat) | **init line never written** (not met) | no | **major** |
| zsh | fedora-immutable without brew (OK) | ✓ / ✓ / brew direct (live), native or os-package elsewhere | managed, `brew uninstall zsh` ✓; native → refuse | login shell handled by OMZ hook ✓ | default-shell check only | minor |
| oh-my-zsh | all | ✓ detect_path / **version always None** / installer by-elimination | managed, "own installer" → L3 `tools/uninstall.sh`; added .zshrc lines not reverted | sourcing repaired by `ensure_zshrc_template` ✓ | no (dangling `source` after removal) | minor |
| gnu-bash | macOS only (OK) | ✓ detect_path / brew inventory / brew by-elimination | L1 `brew uninstall bash` ✓ | not added to `/etc/shells` (not met for chsh) | no | minor |
| direnv | all (no upstream checksums) | ✓ / ✓ (2.37.1 vs 2.38.2 shows outdated) / installer direct | removable, L2 ✓ (F1 caveat) | **hook never written** (not met) | no | **major** |
| gum | all | ✓ / ✓ / os-package on Bazzite (live) | L2 or os-package ✓ | completions in tarball unused | n/a | OK |
| lazydocker | all | ✓ / ✓ / installer direct | removable, L2 ✓ | needs a docker or podman socket (not met on podman hosts) | no | minor |
| watch | fedora-immutable without brew (OK) | ✓ / ✓ / os-package procps-ng (live) | **hint "dnf/apt/pacman remove procps(-ng)" on mutable hosts: destructive** | none | n/a | **major** |
| docker | fedora-immutable without brew | ✓ / ✓ / os-package moby-engine (dnf probe misses) | L1 hint; native refuse | **dnf `docker` = moby-engine daemon, not the CLI; no daemon, group or context setup** | no | **major** |
| podman | fedora-immutable without brew (OK) | ✓ / ✓ / os-package (live) | L1; mac `podman machine rm` missing | **macOS: no `podman machine init/start`; brew discouraged upstream; Intel brew fails** | no | **major** |
| colima | Linux without brew (G3) | ✓ / brew / brew | L1, but should run `colima delete` first (VM disk), ask | `colima start` / service not offered | no | minor |
| container | macOS 26 arm64 only (OK) | ✓ / brew / brew (ownership-only bypass ✓) | L1, plus `container system stop` and data dir, ask | `container system start` + kernel (caveat) not offered | no | minor |
| dive | all | ✓ / ✓ / installer direct | removable, L2 ✓ | podman users need `--source podman` | no | OK |
| deno | all (needs `unzip` on host) | ✓ / ✓ / installer direct | removable, L2 ✓; DENO_DIR left | completions optional | no | minor |
| sdkman | all (needs zip and unzip) | ✓ detect_path / ✓ version_file / installer by-elimination | managed → L3 `rm -rf ~/.sdkman` + rc block, ask (holds 5 candidates) | vendor writes init ✓ | no | minor |
| java | all | **macOS: `/usr/bin/java` stub counts as installed** / readlink version on Linux / sdkman direct | L1 `sdk uninstall java <ver>` (placeholder) | PATH via managed block ✓ | no drift, no stub detection | **blocker** |
| groovy | all | ✓ / readlink, no drift / sdkman or brew (live: brew, off-policy) | L1 ✓ | ✓ | off-policy shown ✓ | minor |
| springbootcli | all | ✓ / ✓ / sdkman direct (live) | L1 ✓ | ✓ | – | minor |
| gradle | all | ✓ / **`gradle --version` first line blank → None** (brew inventory saves it) / brew (live) | L1 ✓ | ✓ | off-policy ✓ | minor |
| maven | all | ✓ / ✓ / brew (live) | L1 ✓ | ✓ | off-policy ✓ | minor |
| bun | all (needs `unzip`) | ✓ / ✓, no latest / installer direct | managed → L3 `rm -rf ~/.bun` + rc lines, ask | vendor edits rc ✓ | no | minor |
| pnpm | all | ✓ / ✓ / **unknown: active path is the installer's own redirect shim; real pnpm is Volta's (live)** | **fallback hint "brew uninstall pnpm" (wrong)** → L3, ask (globals shared) | vendor `pnpm setup` ✓ | broken shim only for node tools | **major** |
| volta | macOS without brew (wrong data) | ✓ / ✓ / installer direct | managed → L3 `rm -rf ~/.volta`, ask (holds pnpm and node CLIs) | brew route lacks `volta setup` (not met) | no | **major** |
| fnm | macOS without brew (OK) | ✓ / ✓ / installer direct | managed → L3, ask | Linux: vendor edits rc ✓; **brew route: no `fnm env`** | no | minor |

**Counts:** OK 2 · minor 15 · major 8 · blocker 1.

## Per-tool notes

### uv (`registry.toml:63`)
- **Install.** The vendor script installs to `~/.local/bin`. It edits shell profiles unless `UV_NO_MODIFY_PATH=1` (uv.sh:51), and the registry passes no `env`. The managed PATH block already owns `~/.local/bin`, so the line it adds (`. "$HOME/.local/bin/env"`) is redundant. `rcclean` only matches `export PATH=` lines (`rcclean.py:501`), so it does not catch this one. After the user deletes `~/.local/bin/env`, every shell errors.
- **Detect.** Live: installer direct, `0.11.28`. `github_repo` reads only `github_release` methods (`version_status.py:141`), so script-owned tools never get a latest version (G7). Updating re-runs the script, which is fine for uv (`uv self update` is the vendor path).
- **Uninstall.** Level 3, per uv docs: `uv cache clean; rm -r "$(uv python dir)" "$(uv tool dir)"; rm ~/.local/bin/{uv,uvx,env,env.fish}`. `uv tool dir` is shared with every `uv-tool` entry (`registry.toml:1590,3370` declare `requires=["uv"]`). Policy: ask.
- **Brew alternative.** No Intel bottle exists (Homebrew Tier 3 since 7.0.0), so it would build from source. Low risk, because the script ranks first.

### brew (`registry.toml:151`)
- **Bootstrap needs a cached sudo timestamp. NEW, major.** `env NONINTERACTIVE=1` makes install.sh call `sudo -n` (`have_sudo_access`, brew.sh:297-299). It aborts "Insufficient permissions to install Homebrew to …" when the prefix parent is not user-writable (brew.sh:593-596), which is `/opt` on macOS and `/home` on Linux. This holds in the CLI runner too. In the TUI the runner also has `stdin=DEVNULL` (`run.py:235`). Nothing runs `sudo -v` first.
- **Intel Mac.** `bin_dir=/opt/homebrew/bin` is wrong there (comment at `registry.toml:159`, maps to 999.3). Also, Homebrew 7.0.0 (2026-09-13) moved Intel to Tier 3, so new bottles are not built and formulae such as uv, docker, bun, pnpm, gum and deno will compile from source on Intel.
- **Ownership unknown on Linux. Live, NEW.** `which brew` resolves to `/var/home/linuxbrew/.linuxbrew/Homebrew/bin/brew`, which is outside the declared `bin_dir` `/home/linuxbrew/.linuxbrew/bin`. `attribute_path` yields only `brew`, and no candidate exists, so the result is `unknown`: "the active binary … is not attributable to any candidate". On Bazzite brew comes from the image (ublue `brew-setup`), so "own installer" would be wrong anyway.
- **Configure.** Only PATH is wired. There is no `eval "$(brew shellenv)"`, so `sbin`, `MANPATH`, `INFOPATH` and `HOMEBREW_PREFIX` are missing. Linux also needs build deps (`brew install gcc` per docs).
- **Uninstall.** Level 3: the official `Homebrew/install/HEAD/uninstall.sh`. Policy: ask, and warn that every brew-owned entry dies with it. There is no `requires=["brew"]` edge, so `reverse_dependencies` cannot warn.

### starship (`registry.toml:464`)
- **Install.** Assets and `.sha256` sidecars (bare hash, handled by `checksums.expected_sha256`) are verified against v1.26.0 for all four cells.
- **Configure. Major, NEW.** Starship does nothing until `eval "$(starship init zsh|bash)"` runs. No tweak or `post_install` writes it (`tweaks.py:155-200` lists docker, countdown, claude-skip, codex-skip and apt-upgrade only). Customizations worth offering: a `starship preset` choice for `~/.config/starship.toml`, and ordering relative to an OMZ `ZSH_THEME`.
- **Uninstall.** Level 2: `~/.local/opt/starship` plus the link (live: removable ✓). Keep `~/.config/starship.toml`; delete `~/.cache/starship`. The init line must go too, once it exists.

### zsh (`registry.toml:503`)
- On macOS `/bin/zsh` exists, so the row reads installed (correct per the comment). Live on Bazzite: brew `zsh` 5.9.2 direct, hint `brew uninstall zsh` ✓.
- **Mutable Linux.** Install runs `sudo dnf/apt/pacman` (`executors.py:370-379`) inside the TUI with `stdin=DEVNULL` and no credential preflight (G2).
- **Removal.** Native → refuse (correct). Brew → level 1. Keep `~/.zshrc` and `~/.zsh_history`.

### oh-my-zsh (`registry.toml:540`)
- **Install env.** `KEEP_ZSHRC=yes`, `CHSH=no`, `RUNZSH=no` verified against the current install.sh (omz.sh:30,101-102). The "kept .zshrc never sources OMZ" case is repaired by `omz.ensure_zshrc_template` (`omz.py:378-427`) ✓.
- **Version.** `cmd="omz"` is a zsh function, so `_version_argv` runs `omz --version` and always gets None (live). Better sources: `git -C ~/.oh-my-zsh describe` or `log -1 --format=%cs`.
- **Update or repair is broken. NEW.** Update re-runs the vendor script (`update.py:337`), but install.sh exits 1 when `$ZSH` exists (omz.sh:563-581). The vendor path is `$ZSH/tools/upgrade.sh` (`omz update`).
- **Uninstall.** Level 3: `sh ~/.oh-my-zsh/tools/uninstall.sh`. It restores `.zshrc.pre-oh-my-zsh` when one exists; with `KEEP_ZSHRC` there is none. The `export ZSH` / `plugins=(git)` / `source $ZSH/oh-my-zsh.sh` lines that `ensure_zshrc_template` appended are not recorded, so the sweep (`uninstall._omz_policy`) leaves a dangling `source` line. `~/.oh-my-zsh/custom` holds user themes and plugins: ask.

### gnu-bash (`registry.toml:581`)
- Detection design ✓. Live attribution goes through the `_OWNERSHIP_ONLY_KINDS` brew row ✓.
- The `bash` formula no longer has an Intel bottle (source build).
- **Configure.** To use it with `chsh`, `$(brew --prefix)/bin/bash` must be added to `/etc/shells` (sudo). Nothing offers this.
- **Removal.** Level 1 `brew uninstall bash`.

### direnv (`registry.toml:603`)
- **Install.** Raw assets exist for all four cells. Upstream publishes **no checksums** (asset list for v2.38.2), so this is accepted and stays unverified.
- **Configure. Major, NEW.** The `eval "$(direnv hook zsh|bash)"` hook is never written, so `.envrc` is never loaded. Worth offering: `~/.config/direnv/direnv.toml` (`hide_env_diff`, `[whitelist]`).
- **Uninstall.** Level 2 ✓ (live: removable). Keep `~/.config/direnv` and `~/.local/share/direnv/allow`.
- **F1 (999.8).** `curl direnv.net/install.sh | bash` may also install to the first writable PATH dir, which may be `~/.local/bin`. A name match then counts as proof.

### gum (`registry.toml:769`)
- v2.0.2: assets plus `checksums.txt` ✓. Layout `gum_<v>_<OS>_<arch>/gum` with `strip=1` ✓.
- Live: Bazzite ships `/usr/bin/gum`, so the row reads os-package ✓.
- The tarball's `completions/` and `manpages/` are discarded (optional).

### lazydocker (`registry.toml:902`)
- v0.25.2 ✓ (flat tarball, `strip=0`).
- **Configure.** On podman-only hosts (Bazzite) it needs `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock` and `systemctl --user enable --now podman.socket`. Not offered.
- **Removal.** Level 2. Keep `~/.config/lazydocker` (`~/Library/Application Support/jesseduffield/lazydocker` on macOS).

### watch (`registry.toml:931`)
- Live: os-package `procps-ng` ✓.
- **Removal hint is destructive. NEW.** On a mutable host the dnf/apt/pacman probe confirms the declared package. `removal_hint` then renders `dnf remove procps-ng`, `apt remove procps` or `pacman -R procps-ng` (`ownership.py:1368-1381`). That package also provides ps, top, kill, free and sysctl. Correct rule: level "never — part of a base package". The registry needs a way to say the package is shared (999.8 schema).
- brew `watch` 4.0.7 conflicts with `visionmedia-watch` (harmless).

### docker (`registry.toml:954`)
- **Fedora. NEW.** No package named `docker` exists in Fedora 43. `dnf install docker` resolves through `Provides: docker` to **moby-engine**: daemon plus root service plus `docker` group, not the "Docker CLI" the entry describes. `docker-cli` is the CLI-only package. The `_dnf` ownership probe (`rpm -q docker`) therefore never confirms, and attribution falls to os-package `moby-engine` (works, but labelled "OS package" rather than dnf).
- **Debian / Arch.** `docker.io` and `docker` are engine packages too. Configure needs `systemctl enable --now docker` and `usermod -aG docker` (sudo, re-login). Nothing is offered.
- **macOS / immutable+brew.** brew `docker` is the CLI only (no Intel bottle). It needs an engine (colima, podman socket or Docker Desktop) and a `docker context`. There are no `recommends`, and no context or socket wiring.
- **Removal.** Level 1. Keep `~/.docker` (credentials and contexts). For engine data under `/var/lib/docker`: ask.

### podman (`registry.toml:977`)
- **macOS.** The formula declares `arch: arm64` + `macos: 13` (bottles: `arm64_*`, `x86_64_linux` only), so **Intel Mac `brew install podman` fails while the resolver offers it**. podman.io: "It's not recommended to install via Homebrew because it is a community-maintained package manager". The upstream route is the `.pkg` installer, which needs a new `pkg` kind (999.3).
- **macOS configure.** `podman machine init && podman machine start` is required. The caveat suggests podman-desktop for autostart. Not offered.
- **Removal.** Level 1 plus `podman machine rm` (VM disk). For `~/.local/share/containers` (images and volumes): ask.

### colima (`registry.toml:1000`)
- brew only. Linux bottles exist (needs lima, qemu and KVM).
- **Configure.** `colima start` (sets the docker context automatically), or `brew services start colima` (service=true). Not offered. It needs the `docker` CLI, which is not in `recommends`.
- **Removal.** Run `colima delete` before `brew uninstall colima`, otherwise the VM disk (all images and volumes) stays in `~/.colima`. Policy: ask.

### container (`registry.toml:1035`)
- Gating mirrors the formula: macOS 26, arm64 (plus build-only xcode 26). Probe: mac-arm64 os 15.5 → "needs macOS 26+" ✓.
- **Configure.** `container system start` and `container system kernel set --recommended` (formula caveat). Not offered.
- **Removal.** `container system stop`, then `brew uninstall container`; ask about `~/Library/Application Support/com.apple.container`.

### dive (`registry.toml:1051`)
- v0.13.1: assets plus `dive_<v>_checksums.txt` ✓. Upstream's last release is 2025-03.
- **Removal.** Level 2 ✓.

### deno (`registry.toml:1691`)
- v2.9.7: zip plus `.sha256sum` ✓.
- `archive="zip"` shells out to `unzip` (`download.py:390`), and there is no `unzip` registry entry or host check. Minimal Debian or Arch fails with a CommandError rather than a clear prerequisite message.
- **Removal.** Level 2. DENO_DIR (`~/.cache/deno`, `~/Library/Caches/deno`) and `~/.deno/bin` (scripts installed with `deno install`): ask.

### sdkman (`registry.toml:1737`)
- **Script version.** Now 5.23.2 (comment says 5.23.0), with native 0.7.34. The script hard-requires `zip` and `unzip` (sdkman.sh:209-227).
- **Detect.** ✓ (`detect_path`; live version from `version_file` = 5.23.0, so it does not self-update).
- **Update re-run is a silent no-op. NEW.** The script prints "SDKMAN found." and exits 0 (sdkman.sh:174-188), so `update.py` would report `updated`. The vendor path is `sdk selfupdate`.
- **Removal.** Level 3: `rm -rf ~/.sdkman` plus the `#THIS MUST BE AT THE END OF THE FILE FOR SDKMAN TO WORK!!!` block in `.bashrc`/`.zshrc`. Ask. Five registry entries live inside it; `requires` edges exist so the warning works.

### java (`registry.toml:1777`)
- **Blocker on macOS. NEW.** macOS ships a `/usr/bin/java` stub (JavaVM.framework) that prints "Unable to locate a Java Runtime". `is_installed` checks `shutil.which(tool.cmd)` first (`status.py:40`), so a fresh Mac reports java installed. `install_tool` then returns `ALREADY_INSTALLED` (`engine.py:132`) and `sdk install java` never runs. This is the exact collision the gnu-bash comment solves with a probe-name trick. Ownership is unknown there (no macOS package database), and `java --version` exits non-zero, so the version is None. A fix needs a "stub" rule: probe success, or `/usr/libexec/java_home` exit code.
- **Live (Bazzite).** java is brew `openjdk` 26.0.1, off-policy=True, surfaced ✓. With the seam, the hint is `brew uninstall openjdk` ✓. Without it (before the first refresh), the hint is the registry guess "managed by SDKMAN — `sdk uninstall java <version>`", which is wrong (G4).
- **Version and removal.** No latest source for SDKMAN (`resolve_status` sdkman branch returns `outdated=None`, `version_status.py:389-401`). The removal hint carries a `<version>` placeholder even though `_sdkman_current_version` knows it.

### groovy / springbootcli / gradle / maven (`registry.toml:1792/1807/1822/1837`)
- Live: groovy, gradle and maven are brew-owned (off-policy flagged ✓); springboot is SDKMAN direct (`4.1.0`).
- `gradle --version` prints a blank first line, so `_probed_version` returns None. Harmless while brew `current_version` is present; for an SDKMAN-owned gradle, readlink supplies the version.
- **Brownfield.** `sdkman_auto_answer` may be false, so `sdk install` can hit the prompt with stdin closed (documented in the `registry.toml:1755-1776` comments).
- **Data to keep on removal.** `~/.m2`, `~/.gradle`, `~/.groovy`.

### bun (`registry.toml:1938`)
- The script needs `unzip` (bun.sh:56) and edits `.bashrc`/`.zshrc`/fish config plus completions (bun.sh:176-312). There is no opt-out env. brew `bun` is in homebrew-core (1.4.2).
- **Removal.** Level 3: `rm -rf ~/.bun` (holds bun globals and cache) plus the rc lines. Ask.

### pnpm (`registry.toml:1956`)
- `bin_dir ~/.local/share/pnpm/bin` matches pnpm.sh's v11+ `$PNPM_HOME/bin` layout ✓; brew pnpm is 12.11.2.
- **Ownership defect. Live, NEW.** `which pnpm` returns `~/.local/bin/pnpm`, the installer's own `# tools-installer-redirect-shim` (`guards.py:116`). `resolve_ownership` does not look through it the way `guards.real_pnpm` does, so the result is `unknown`. The real pnpm is `~/.volta/bin/pnpm` (a Volta shim), and **volta is not an owner** at all (`model.py:56-66` `OWNER_PROBES`).
- **Wrong removal command shown.** Because `removal_hint` returns None for `unknown`, the Uninstall row falls back to `_manager_hint`, which renders **"managed by Homebrew — `brew uninstall pnpm` — found at ~/.local/bin/pnpm"**. That is a wrong manager presented as a command. Live `classify_tools` output; the binding is `setup.py:834-837`.
- **Removal.** Level 3: delete `$PNPM_HOME` (all globals and the store, shared with the four `requires=["pnpm"]` entries) plus the `pnpm setup` rc block. Ask.

### volta (`registry.toml:1997`)
- **Upstream is unmaintained. NEW.** The README says "Volta is unmaintained … We recommend migrating to mise" (issue #2080; last push 2025-11-15). The npm-ban policy routes global CLIs to Volta (`registry.toml:1980-1996`), so this is a strategic dependency on a dead project.
- **macOS.** The script works (above), so the "brew only" restriction is wrong data. The brew route needs `volta setup` (`registry.toml:2014-2018` acknowledges it). It is not offered as a `post_install`.
- **Removal.** Level 3: `rm -rf ~/.volta` plus `VOLTA_HOME`/PATH rc lines. This also removes every Volta-managed node, npm, pnpm and global CLI. Live: codex, pi, openspec and pnpm live there. Ask.

### fnm (`registry.toml:2027`)
- **Linux.** The script installs to `~/.local/share/fnm`, but uses `~/.fnm` if that exists, or `$XDG_DATA_HOME/fnm` if set (fnm.sh:12-20). The declared `bin_dir` misses both. It requires `unzip` and writes `eval "$(fnm env)"` to rc unless `--skip-shell`.
- **macOS brew route.** No `fnm env --use-on-cd`, so fnm is inert. Not met.
- **Removal.** Level 3: `rm -rf <install dir>` (holds node-versions) plus the rc block. Ask.

## Cross-cutting architecture gaps

| # | Gap | Evidence | Maps to |
|---|---|---|---|
| G1 | **macOS system stubs defeat `is_installed`.** `which(cmd)` alone counts the `/usr/bin/java` stub, and the same applies to `/usr/bin/python3` and `git` stubs from other auditors' scopes. There is no "stub/broken binary" notion besides the pnpm dangling shim. | `status.py:40`, `engine.py:132` | **NEW** (fold into 999.6 `ToolState`) |
| G2 | **Privilege preflight missing.** Native methods run `sudo …` through `StreamingRunner` (`stdin=DEVNULL`, `run.py:235`). The brew bootstrap needs `sudo -n`. `run_interactive_command` (`run.py:60`) has no callers. A sudo password prompt inside Textual, or brew aborting, is the likely result (not reproduced). | `executors.py:370-379`, brew.sh:297,593 | **NEW** |
| G3 | **`has_brew` frozen at startup.** brew-only tools (colima, container, gnu-bash, docker/podman/zsh/watch on immutable) are dropped as "not available" in the run that installs brew. Data cannot fix it: `requires=["brew"]` would still be blocked by `available()` using the stale platform (`execute_screen.py:482`, `deps.py:92`). | | Known: GPT-6.1-sol review "Platform.has_brew" (state defect) |
| G4 | **Uninstall "managed" hint guesses a manager when ownership is `unknown` or not yet computed.** `_manager_hint` (`uninstall.py:171-225`) picks the first brew or sdkman method. Live wrong outputs: pnpm → `brew uninstall pnpm`; java/groovy/gradle/maven (before refresh) → `sdk uninstall …` while brew owns them; uv/bun/volta/fnm without the seam → `brew uninstall …`. | live `classify_tools` | 999.6 / ponytail F6 (concrete instance, NEW evidence) |
| G5 | **Ownership resolver ignores the installer's own redirect shim, and Volta is not an owner.** | `ownership.py:573`, `guards.py:116,315` | **NEW** (999.6) |
| G6 | **No shell-activation step.** 5 of 6 `POST_INSTALL_ACTIONS` names (`configure_path`, `source_shell_init`, `enable_corepack`, `pnpm_setup`, `write_agent_reference`) are accepted by the schema, but `POST_INSTALL_HOOKS` implements only `set_login_shell`, and `run_post_install` silently skips the rest. starship, direnv, fnm-via-brew and volta-via-brew stay inert. The TweakBundle/Policy machinery (reversible rc blocks) is the existing seam for init lines. | `model.py:47-54`, `post_install.py:67-84` | **NEW** (ponytail F11 noted unused fields, not these) |
| G7 | **No latest-version source for script- and SDKMAN-owned tools.** `github_repo` reads only `github_release`, so uv, bun, pnpm, volta, fnm, sdkman, OMZ, brew and all SDKMAN candidates never show "outdated". A `version_repo` (GitHub) param or the vendor's own check (`sdk outdated`, `omz version`) would cover it. | `version_status.py:141-152,300-338,389-401` | **NEW** |
| G8 | **"Update = re-run the vendor installer" is wrong for some vendors.** OMZ exits 1; SDKMAN no-ops with exit 0 (reported `updated`). The registry cannot declare a per-tool update command. | `update.py:337` | **NEW** (pair with the 999.8 per-method spec: add `update` beside `remove`) |
| G9 | **Vendor rc edits are never tracked or removed**, so dangling lines remain after removal: uv `. ~/.local/bin/env`, bun, pnpm, volta, fnm and SDKMAN blocks, OMZ template lines. `rcclean` handles only PATH exports. | `rcclean.py:1-6,501` | 999.8 ("what config/data it leaves") |
| G10 | **Shared or base packages need a "never remove" level.** watch → procps, and similar. | `ownership.py:1368-1381` | 999.8 schema (NEW sub-case) |
| G11 | **Runtimes need a service/daemon step**: docker engine, podman machine, colima start, container system start. | – | **NEW** (999.8 should also carry `service` start/stop for removal) |
| G12 | **Prerequisite binaries are not modelled**: `unzip` for deno-zip, bun, fnm and SDKMAN; `zip` for SDKMAN. | `download.py:175-180,390` | **NEW** (minor) |
| G13 | **Homebrew Intel Tier 3 (since 7.0.0).** Most brew fallbacks on mac-amd64 now build from source; podman refuses outright. | formulae API | 999.3 (per-arch artifacts) |

Already-known items this audit touches and does not re-report: F1 (name match as proof, which affects direnv, starship and the other level-2 tools) and F7 (999.8); script installs have no removal (999.2/999.8); brew Intel `bin_dir` (999.3); the row-state disagreement (999.6).

## Registry fixes (data only)

1. **volta.** Drop `os=[debian,arch,fedora]` from the script method, or add a macOS script method. `get.volta.sh` supports Darwin and v2.0.2 ships `volta-2.0.2-macos.tar.gz`. Correct the false comment at `registry.toml:2009-2013`. Separately, record "upstream unmaintained, recommends mise" in a `# Verified 2026-10-13` comment.
2. **podman.** Split the brew method: `os=["macos"], arch=["arm64"]` plus a Linux-only brew method. Note podman.io's "not recommended via Homebrew" stance.
3. **docker.** On dnf, use `package = "docker-cli"` if the entry really means "Docker CLI". Otherwise rename/describe it as the engine and keep `docker` (→ moby-engine). On apt, `docker.io` is the engine too; decide and document.
4. **uv.** Add `env = { UV_NO_MODIFY_PATH = "1" }`, since the managed PATH block already owns `~/.local/bin`.
5. **sdkman.** Update the verified-version comment to 5.23.2 and note the `zip`/`unzip` prerequisite.
6. **colima.** Set `recommends = ["docker"]`. Consider `recommends = ["docker"]` or podman for lazydocker and dive.
7. **fnm.** Optionally add a macOS script method with `args = ["--force-no-brew"]` to cover mac-nobrew (installs to `~/Library/Application Support/fnm`).
8. **brew.** Add an arch-split macOS script method (`arch=["amd64"]`, `bin_dir=/usr/local/bin`), mirroring how gnu-bash splits by arch.
9. **Missing `# Verified` dates.** uv, brew, starship, direnv, gum, lazydocker, watch, docker, podman, colima, dive, deno, bun, pnpm, fnm have none. Values re-verified today: starship v1.26.0, direnv v2.38.2 (no checksums upstream), gum v2.0.2, lazydocker v0.25.2, dive v0.13.1, deno v2.9.7. All rendered assets and checksums exist for both arches.
