# Registry audit D: user tier, part 1 (23 tools)

Date: 2026-10-13. Auditor D of 7. Read-only. Tools: jq git delta zoxide fzf lazygit gh yq just ruff dust hyperfine bottom glow xh difftastic gitui duf hexyl miller shfmt tealdeer fx.

## What was verified, and how

**Checked live (commands run during this audit):**
- **Resolver matrix.** A probe (`/tmp/claude-1000/auditD/probe.py`) ran `installer.resolve.resolve_methods` and `unavailable_reason` over 20 synthetic `Platform` cells: macOS arm64/amd64 (with and without brew); debian, fedora and arch on amd64/arm64 (with and without brew); and fedora immutable on amd64/arm64 (with and without brew).
- **Upstream assets.** `gh api repos/<repo>/releases/latest` for all 21 github_release repos. Every rendered asset name and checksum name was compared with the real asset list (`/tmp/claude-1000/auditD/assets.py`). I also checked whether each repo was renamed or archived.
- **Archive layouts.** Listed the contents of 18 release archives with `curl | tar -t` to confirm the `member` and `strip` values. Checked the arch of the gitui macOS binaries with `file`, and the glibc floor of the 4 `-gnu` builds with `objdump -T`.
- **Homebrew.** `brew info --json=v2` for all 23 formula names, read-only with `HOMEBREW_NO_AUTO_UPDATE=1`. All exist; none is deprecated or disabled.
- **This host (Bazzite 44, fedora immutable, amd64, has brew).** Ran `resolve_ownership` (with the real `run_probe`), `plan_uninstall`, `classify_tools` and `extract_observed_version` on the 16 tools that are installed (`/tmp/claude-1000/auditD/own.py`).
- **Fake HOME.** A throwaway HOME reproduced three cases: a dangling link, a uv-tool ruff, and a pip-style plain `yq` script.

**Taken from source or docs:** tealdeer's missing-cache behaviour (upstream `src/main.rs`, docs `config_updates.md`). Shell-init, git-config and config/data paths come from vendor documentation knowledge and were not fetched one by one; they are marked "(docs)".

**Not checked:**
- arm64 Linux and macOS cells were never run. They are inferred from asset names that exist upstream.
- Homebrew arm64_linux bottles: the Linux JSON API only shows this host's bottle.

None of the 23 entries has a `# Verified` comment, so all were re-verified here.

## Resolver result per cell

The ladder is the same on every cell where a github_release method exists:
- **Linux** (debian, fedora, arch, fedora immutable): `github_release` first, then `brew` when present.
- **macOS:** `github_release(macos)` first, then `brew`.

Exceptions are listed below. "NONE" means no method applies. `unavailable_reason` returns `None` in these cells: they are treated as "installable once brew is present", not as "not supported".

| Tool | Cells with NO method | Acceptable? |
|---|---|---|
| jq | macOS without brew; fedora immutable without brew | Yes. Bazzite's base image ships `/usr/bin/jq` (live: `rpm -qf` gives `jq-1.8.1-3.fc44`). macOS 15+ is reported to ship `/usr/bin/jq` (not verified here). Either way it shows as installed. |
| git | macOS without brew; fedora immutable without brew | Yes. Every immutable Fedora image ships git, and macOS has `/usr/bin/git`. See the git note about the macOS Command Line Tools stub. |
| gh | macOS without brew | Not needed. Upstream ships `gh_{ver}_macOS_{amd64,arm64}.zip`, covered by the checksums file. See Registry fixes. |
| gitui | macOS without brew | Not needed. `gitui-mac.tar.gz` is a Mach-O arm64 binary and `gitui-mac-x86.tar.gz` is x86_64 (checked with `file`). See Registry fixes. |
| delta | Effectively macOS amd64 without brew | The resolver picks `delta-{ver}-x86_64-apple-darwin.tar.gz`, but upstream dropped it (absent in 0.19.1, 0.19.2, 0.20.0 and 0.20.1). The download gets a 404, then brew is tried; without brew the install FAILS. |
| difftastic | **Every github_release cell** | **No.** The asset was renamed in 0.71.0 (2026-09-18); see the difftastic note. |

Native package managers (dnf/apt/pacman) are only declared for jq and git. They are correctly skipped on immutable Fedora (`resolve.py:76-77`).

## Matrix

Cell legend: "all OK" means every cell resolves to an asset that exists today.

| Tool | Install coverage (missing cells) | Detect / version / owner | Uninstall (now, and is it right?) | Configure needs (met?) | Health detectable? | Verdict |
|---|---|---|---|---|---|---|
| jq | native/brew; NONE on mac and immutable without brew (base copy covers it) | OK. Live: brew/direct, version "jq-1.8.2". The `/usr/bin/jq` it shadows is not reported. | MANAGED, hint `brew uninstall jq` (level 1). Right not to delete. | none (optional `~/.jq`) | brew outdated only | **OK** |
| git | native/brew; NONE as for jq | OK on Linux. Live: os-package `git-core`. On macOS the CLT stub counts as installed. | MANAGED, hint only (level 1). Right. | user.name/email; delta/difft integration. **Not offered.** | identity missing: no | **minor** |
| delta | Linux OK (gnu, needs GLIBC_2.34); macOS amd64 asset gone | OK. Live: installer/direct, 0.19.2 vs latest 0.20.1 | REMOVABLE opt+link (level 2). Right only after F1. Leaves `core.pager=delta` in gitconfig. | git pager config. **Not offered.** | broken gitconfig after removal: no | **major** |
| zoxide | all OK (musl); no checksum | OK; not installed on this host | level 2 (name match). Data `~/.local/share/zoxide` kept, which is right. | `eval "$(zoxide init <shell>)"` is **required, not done** | init missing: no | **major** |
| fzf | all OK, with checksum | OK. Live: os-package (Bazzite base 0.74.4) | MANAGED here; level 2 elsewhere | `source <(fzf --zsh)` / `eval "$(fzf --bash)"` keybindings. **Not done.** | no | **minor** |
| lazygit | all OK, with checksum | owner OK. **Version unparseable** (`version=0.63.1,`). Live: latest 0.66.1, outdated shown as None. | level 2. Config `~/.config/lazygit` kept, which is right. | optional delta pager | drift: **no** | **minor** |
| gh | Linux OK, with checksum; mac brew-only | OK. Live: installer/direct 2.101.0 vs 2.102.0 | level 2. Leaves `~/.config/gh/hosts.yml` (auth token). Needs a level 3 "delete all" (`gh auth logout`). | `gh auth login` (interactive), completions. **Not offered.** | auth missing: no (`gh auth status` would work) | **minor** |
| yq | all OK, raw; no standard checksum | OK. A foreign `~/.local/bin/yq` (pip yq) reads as **installer/direct** | REMOVABLE by name. Fake HOME: the pip yq is deleted, and Update would overwrite it. | none | no | **minor** (deepens F1) |
| just | all OK, with checksum | OK. Live: os-package (Bazzite base 1.57.0) | level 2 | completions ship in the tarball under `~/.local/opt/just`, not wired | no | **OK** |
| ruff | all OK, with checksum | **Wrong under `uv run`**: `.venv/bin/ruff` is the active copy, owner unknown, so install answers ALREADY_INSTALLED | uv-tool ruff: REMOVABLE by name (F1); venv ruff: MANAGED "outside" | `~/.config/ruff` optional | no | **blocker** |
| dust | all OK; no checksum | OK. Live: installer/direct 1.2.6 | level 2 | none | drift yes | **OK** |
| hyperfine | all OK (gnu, GLIBC_2.18); no checksum | OK | level 2 | completions in archive, unwired | drift yes | **OK** |
| bottom | all OK (musl); no checksum | OK. Live: installer/direct 0.14.9 | level 2. Config `~/.config/bottom` kept, which is right. | completions unwired | drift yes | **OK** |
| glow | all OK, with checksum | owner OK. Live: os-package glow 2.1.2 (latest 3.0.0) but **no latest shown** | MANAGED (base image) | none | drift on os-package: no; cannot reinstall (999.1b) | **minor** |
| xh | all OK (musl); no checksum | OK | level 2 | optional `xhs` link, completions | drift yes | **OK** |
| difftastic | **all github cells 404** (asset renamed 0.71.0) | owner OK. Live: installer/direct 0.69.0, outdated is **true**, Update gets a 404 | level 2. Leaves `diff.external` / alias in gitconfig. | git difftool/alias. Not offered. | outdated yes; update broken | **blocker** |
| gitui | Linux OK; mac brew-only (assets exist); repo moved | OK. Live: installer/direct 0.28.1 | level 2. Config `~/.config/gitui` kept, which is right. | none | drift yes | **minor** |
| duf | all OK, with checksum | owner OK. Distro build prints "duf (built from source)", so version is None | MANAGED (base image) here | none | n/a | **OK** |
| hexyl | all OK (gnu, GLIBC_2.16); no checksum | OK | level 2 | none | drift yes | **OK** |
| miller | all OK, with checksum | OK. Live: installer/direct 6.21.0 vs 6.22.0 | level 2. `~/.mlrrc` kept, which is right. | none | drift yes | **OK** |
| shfmt | all OK, raw; no checksum | OK (`v3.14.1` parses) | level 2 by name (shfmt-py collision possible) | none | drift yes | **OK** |
| tealdeer | all OK, with checksum; repo moved | OK | level 2 by name (other `tldr` clients collide). Cache `~/.cache/tealdeer`: delete-all is safe. | **`tldr --update` is required before first use. Not done.** | cache missing: no | **major** |
| fx | all OK, raw; no checksum | OK. Live: installer/direct 39.2.0 vs 40.0.0 | level 2 | none (optional `~/.fxrc.js`) | drift yes | **OK** |

**Counts: 2 blocker (ruff, difftastic), 3 major (delta, zoxide, tealdeer), 7 minor (git, fzf, lazygit, gh, yq, glow, gitui), 11 OK.**

"OK" rows still share the cross-cutting caveats C2, C5 and C6 below.

## Per-tool notes

### jq
- Owner probes are declared (`registry.toml:136`).
- Live on this host:
  - `jq` resolves to `/home/linuxbrew/.linuxbrew/Cellar/jq/1.8.2/bin/jq`, giving owner brew/direct.
  - The base-image `/usr/bin/jq` 1.8.1 is shadowed by that brew copy and never mentioned. It is not a candidate because only declared methods become candidates (`ownership.py:943-1023`).
  - That is harmless for jq, but it is the same blind spot as with any os-package copy.
- `extract_observed_version("jq-1.8.2")` returns the token `jq-1.8.2` with its prefix kept. It compares fine because the brew inventory supplies the version.
- Uninstall: level 1, hint only (`uninstall.py:212-218`).

### git
- Live: owner os-package, package `git-core` (`ownership.py:862-911`). The Uninstall hint is right not to delete it.
- **macOS:** `/usr/bin/git` is the Command Line Tools stub.
  - `is_installed` returns True even when CLT is absent (`status.py:40`).
  - The background version probe runs `/usr/bin/git --version` (`version_status.py:225-239`). On a Mac without CLT, that stub triggers the `xcode-select` install prompt. (docs; not run here)
  - NEW minor: either gate the probe on `xcode-select -p`, or treat a stub that exits non-zero as "not installed".
- Configure: nothing checks or offers `user.name` / `user.email`, and no delta/difftastic integration is offered (see C3).
- Removal policy: never touch `~/.gitconfig`.

### delta
- **Assets:**
  - `delta-{ver}-x86_64-apple-darwin.tar.gz` no longer exists (checked across the last 4 releases). Intel Macs always eat a 404, then brew; without brew the install fails.
  - An installer-owned Intel-Mac copy can never update: `_update_installer_owned` has no fallback (`update.py:320-340`).
  - The registry comment at `registry.toml:293` ("publishes no musl build") is stale: `delta-0.20.1-x86_64-unknown-linux-musl.tar.gz` exists (x86_64 only).
- **glibc:** the `-gnu` build needs **GLIBC_2.34** (`objdump -T`). On Debian 11 or Ubuntu 20.04 the install reports INSTALLED, but the binary cannot run (C6).
- **Checksum:** none upstream. The GitHub API `digest` field has one (C5).
- **Configure:** delta does nothing until git is configured: `core.pager=delta`, `interactive.diffFilter="delta --color-only"`, `delta.navigate=true`, `merge.conflictStyle=zdiff3` (docs). None of this is offered.
- **Uninstall:** level 2 removes `~/.local/opt/delta` and `~/.local/bin/delta` (live classification). It does not warn when gitconfig still points at delta (C4). Default policy: keep gitconfig, but warn.

### zoxide
- Install OK on all cells: musl, `strip=0`, binary at the archive root (listed).
- The archive's `man/` and `completions/` are extracted into `~/.local/opt/zoxide` and never wired.
- **Configure is required:** without `eval "$(zoxide init zsh|bash)"`, placed at the end of the rc (docs), there is no `z` command, so the tool is non-functional for its human audience. Nothing in `tweaks.py:155-217` or `post_install.py` covers it (C3).
- Data lives in `~/.local/share/zoxide/db.zo` on Linux and `~/Library/Application Support/zoxide` on macOS (docs). Keep it by default.
- Health: "binary present, no init" cannot be detected; neither can "init line present, binary removed".
- zoxide's own `install.sh` also writes `~/.local/bin/zoxide`, as a plain file. That makes it name-proven "ours" (C2).

### fzf
- Install OK with checksum.
- Live: Bazzite base `/usr/bin/fzf` 0.74.4, owner os-package, so install answers already-installed.
- Configure: since 0.48, shell integration is `source <(fzf --zsh)` / `eval "$(fzf --bash)"` (docs; the brew caveat confirms integration is a separate step). It is not offered.
- Legacy `~/.fzf.zsh` / `~/.fzf.bash` files from upstream's install script are not detected.

### lazygit
- `lazygit --version` prints `commit=..., build date=..., version=0.63.1, os=linux, ...`, and `extract_observed_version` returns None (live).
- This was known and accepted in Phase 12 (`12-RESEARCH.md:112-115`). The consequence on this host: the installer-owned copy is 3 releases behind and the UI cannot say so.
- Cheap fix: strip a `key=` prefix and trailing commas in `extract_observed_version`, or add a per-tool `version_regex` param.
- Config: `~/.config/lazygit/config.yml` on Linux, `~/Library/Application Support/lazygit` on macOS (docs). Keep it.

### gh
- Linux: OK. The `bin/gh` member with `strip=1` was verified.
- macOS: brew-only, although `gh_{ver}_macOS_{arch.deb}.zip` exists and `gh_{ver}_checksums.txt` lists both zips (verified). Zip support already exists (`download.py:175-180`; deno uses it).
- Configure: `gh auth login` is interactive, so it can only be a handoff line (the `host_setup`-style handoff mechanism exists in `engine.py:155-161`). `gh completion -s zsh` is not offered.
- Health: `gh auth status` would be a reliable non-interactive probe. It is not used.
- Removal: `~/.config/gh/hosts.yml` may hold the OAuth token (or the keyring does). Default: keep config. "Delete all" should run `gh auth logout` first; this is a level 3 recipe for 999.8. Extensions live in `~/.local/share/gh/extensions`.

### yq
- Raw asset, OK on all cells.
- Upstream checksums use a 30-column multi-hash `checksums` file plus `checksums_hashes_order` (SHA-256 is one column). `expected_sha256` cannot parse it, so yq is unverified. The GitHub `digest` field would cover it (C5).
- **Collision (fake-HOME repro):**
  - A plain `~/.local/bin/yq` from `pip install --user yq` (kislyuk's jq wrapper) shows as installed and Uninstall REMOVABLE.
  - Ownership resolves **installer/direct**, because the name-matched artifact creates the installer candidate and `~/.local/bin` is an installer dir (`ownership.py:445`, `958-965`).
  - Its version "3.4.3" against latest 4.54.1 reads as outdated, so Update would `os.replace` the user's file with mikefarah yq (`download.py:285-289`). See C2.

### just
- Install OK with `SHA256SUMS`.
- Live: Bazzite base `/usr/bin/just` 1.57.0, owner os-package.
- Completions ship in the tarball (`completions/just.{bash,zsh,...}`) and land unwired in `~/.local/opt/just`.
- Possible collision: `uv tool install rust-just` also writes `~/.local/bin/just`, which would be F1-exposed.

### ruff — blocker
- **Venv shadowing (NEW, verified live):** `make setup` and `install.sh:88` both run `uv run setup.py`. uv puts `<repo>/.venv/bin` first on PATH, and the dev group includes `ruff>=0.6` (`pyproject.toml:24`). Inside the app:
  - `shutil.which("ruff")` returns `.venv/bin/ruff`.
  - `is_installed` is True, so `install_tool` returns ALREADY_INSTALLED (`engine.py:132-133`). Ruff can never be installed through the shipped entry points.
  - Ownership is "unknown"; Uninstall shows MANAGED "found at …/.venv/bin/ruff".
  - ruff is the only registry cmd shadowed this way (checked against all registry cmds).
- **F1:** a `uv tool install ruff` symlink is REMOVABLE by name (already known; ponytail F1).
- The registry declares no `uv-tool` method for ruff, so a uv-owned ruff is never attributed to uv. Ownership reads as unknown, and the Update/Uninstall hint cannot say "`uv tool uninstall ruff`".

### dust, hyperfine, bottom, xh, hexyl, duf, miller, shfmt, fx
- Assets and `member`/`strip` match the latest releases (archives listed).
- No checksum upstream for dust, hyperfine, bottom, xh, hexyl, shfmt and fx (C5).
- glibc floors: hyperfine-gnu needs GLIBC_2.18 and hexyl-gnu GLIBC_2.16, so both are fine.
- duf: the distro build's version string is unparseable, which only matters for the os-package owner. Upstream builds print `duf <ver>` (goreleaser ldflags).
- Config paths to keep on removal: bottom `~/.config/bottom/bottom.toml`; xh `~/.config/xh` (sessions); miller `~/.mlrrc`; fx `~/.fxrc.js` (docs).

### glow
- Install OK with checksum.
- Live: Bazzite base `/usr/bin/glow` 2.1.2 is os-package-owned. `resolve_status` returns `source="unknown"` with no latest for that owner (`version_status.py:402-414`), so the user never learns that 3.0.0 exists.
- A userspace v3 can't be installed alongside it, because install answers ALREADY_INSTALLED. This is 999.1(b), "no reinstall/repair from the catalog".

### difftastic — blocker
- Upstream renamed its assets in **0.71.0 (2026-09-18)**: `difft-x86_64-unknown-linux-gnu.tar.gz` became `difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz`. 0.70.0 and earlier used the unversioned name (`gh api …/releases`).
- The registry templates `registry.toml:866` and `:873` lack `{ver}`, so all 4 github cells 404.
- Consequences:
  - Fresh installs go to brew; on Linux without brew they FAIL.
  - On this host the installer-owned 0.69.0 shows outdated against 0.71.0, and Update 404s with no fallback (`update.py:329-333`).
- The archive layout is unchanged (`difft` at the root, `strip=0`).
- The `-gnu` build needs **GLIBC_2.34** (C6). An x86_64 musl build exists.
- Configure: `git config alias.dft "-c diff.external=difft diff"` or `diff.external` (docs). Not offered; removal does not check gitconfig (C4).

### gitui
- Linux OK.
- The macOS comment at `registry.toml:889` ("assets don't use our arch tokens") is true, but `Method.arch` gating already exists (`resolve.py:42`; used at `registry.toml:593`, `:1047`). Two arch-gated macOS methods would cover it.
- The repo moved to `gitui-org/gitui`. GitHub redirects for now.

### tealdeer
- Install OK with `{asset}.sha256`.
- The repo moved to `tealdeer-rs/tealdeer`. It still works only because urllib follows the 301 on `api.github.com/repos/dbrgn/tealdeer` (verified 301).
- **Configure is required:** upstream `src/main.rs` prints "Page cache not found. Please run `tldr --update` to download the cache." and `auto_update` defaults to false (`docs/src/config_updates.md`). Without that step the first `tldr foo` fails.
  - `tldr --update` is non-interactive, so it fits the existing postinstall-hook mechanism (`postinstall.py:277`) under REQ-postinstall-noninteractive-only.
- Removal: the cache (`~/.cache/tealdeer`) is regenerable, so delete it. Keep config (`~/.config/tealdeer`; macOS uses XDG since 1.9.0 per the CHANGELOG).
- Collision: Python/npm `tldr` clients can own `~/.local/bin/tldr` (C2).

## Cross-cutting architecture gaps

| # | Gap | Evidence | Maps to |
|---|---|---|---|
| C1 | **The project venv shadows registry tools.** `uv run setup.py` puts `.venv/bin` first on PATH, so ruff reads as installed, can't be installed, and its owner is unknown. Fix: launch with `uv run --no-dev` in `install.sh:88` and the Makefile run targets, or drop `$VIRTUAL_ENV/bin` from PATH at startup. | live probe; `Makefile:15`, `install.sh:88`, `pyproject.toml:24` | **NEW** |
| C2 | **"installer/direct" ownership is name-derived too.** For raw assets (yq, shfmt, tealdeer, fx) and for plain files in `~/.local/bin`, the artifact name match creates the installer candidate and `~/.local/bin` is an installer dir. So F1's proposed interim fix (gate REMOVABLE on `owner=="installer"` with direct confidence) **still deletes** a pip-installed yq, and **Update overwrites** it. For archive kinds a cheap interim proof exists: require `~/.local/bin/<bin>` to be a symlink resolving into `opt_dir(<bin>)`. Raw kinds need 999.2 receipts. | fake HOME repro; `ownership.py:445`, `958-965`; `download.py:285-289` | deepens **F1 / 999.2 / 999.8** |
| C3 | **No per-tool integration/configure capability.** Covers shell init (zoxide, fzf), git config (delta, difftastic), first-run data (`tldr --update`), auth handoff (`gh auth login`), and completions (already extracted under `~/.local/opt/<tool>` for zoxide, just, hyperfine, bottom, glow and xh, but never on `fpath`). Smallest path: `TweakBundle`s with `requires=(cmd,)` and `command -v` guards in `~/.myshellrc` for zoxide/fzf, and postinstall hooks for `tldr --update`. Health then becomes `tweak_present` versus `is_installed`. git config needs a reversible "managed key" writer. | `tweaks.py:155-217` (no tool integrations); `post_install.py` has only `set_login_shell` | **NEW** (removal side: 999.8 level 3) |
| C4 | **Uninstall ignores configs that point at the removed binary:** `core.pager` / `interactive.diffFilter` = delta, `diff.external` = difft, rc lines running `zoxide init` / `fzf --zsh`. After removal, every git diff or shell start errors. | `uninstall.py:56-97` plans files only | **999.8** (removal spec should list "config references") |
| C5 | **12 of 21 github tools install unverified,** even though the GitHub releases API returns `digest: "sha256:…"` per asset (verified on delta). One generic fallback in `download._resolve_target` would cover delta, zoxide, yq, dust, hyperfine, bottom, xh, difftastic, gitui, hexyl, shfmt and fx. | `assets.py` probe; `gh api …/releases/latest` | **NEW** |
| C6 | **No post-install smoke test.** delta-gnu and difft-gnu need GLIBC_2.34; on Debian 11 / Ubuntu 20.04 they install "successfully" but cannot run. The version probe then gives None with no "broken" state (`broken` only covers pnpm shims, `status.py:98-121`). Fix: run `<link> --version` after placing the binary; on failure raise `ExecutorError` so the ladder moves to the next method. | `objdump -T`; `download.py:376-404` | **NEW** |
| C7 | **Platform is frozen per run.** `has_brew` is read once (`execute_screen.py:473-483` uses `self._inputs.platform`), and there is no implicit brew dependency (`deps.py` has none). So brew-only cells (jq/git on macOS or immutable without brew; gh/gitui on macOS; delta on Intel macOS) cannot install in the same run that installs brew. `platform_could_support`'s docstring claims "in this run or a later one" (`resolve.py:177-179`). | code read | **NEW** (related to 999.1 dispositions) |
| C8 | **Catalog and Uninstall disagree on a dangling link.** A dangling `~/.local/bin/dust` reads "not installed" in the catalog but REMOVABLE in Uninstall. | fake HOME repro | **999.6 / F6** |
| C9 | **No reinstall or repair** for an installed copy that is the wrong one: an old base-image glow, a venv ruff. | live | **999.1(b)** |
| C10 | **Registry drift is never detected.** The difftastic rename broke installs and updates for about 4 weeks unnoticed, and none of the 23 entries carries a `# Verified` date. The `assets.py` probe here is about 30 lines, read-only, and could become a scheduled `make verify-registry` check. | this audit | **NEW** (onboarding skill: 999.5) |
| C11 | **Version parsing gaps:** lazygit (`version=` key) and distro duf. | live | known (Phase 12 accepted). Cheap fix suggested. |
| C12 | **macOS git CLT stub** counts as installed, and its version probe can trigger the CLT dialog. | `status.py:40`, `version_status.py:225-239` | **NEW** (minor) |

## Registry fixes (data only)

1. **difftastic** (`registry.toml:866`, `:873`):
   - `asset = "difft-{ver}-{arch.machine}-unknown-linux-gnu.tar.gz"`
   - `asset = "difft-{ver}-{arch.machine}-apple-darwin.tar.gz"`

   Optional: an amd64-only musl method to avoid the GLIBC_2.34 floor.
2. **delta:**
   - Add `arch = ["arm64"]` to the macOS github_release method (`registry.toml:297-303`) so Intel Macs go straight to brew.
   - Fix the stale musl comment (`:293`).
   - Optional: an amd64 method using `delta-{ver}-x86_64-unknown-linux-musl.tar.gz` to drop the glibc 2.34 floor.
3. **gh:** add a macOS github_release method:
   - `asset = "gh_{ver}_macOS_{arch.deb}.zip"`
   - `archive = "zip"`
   - `member = "gh_{ver}_macOS_{arch.deb}/bin/gh"`
   - `checksum = "gh_{ver}_checksums.txt"`

   Not install-tested; the zip path mirrors deno's. Then remove the comment at `:423`.
4. **gitui:**
   - Set `repo = "gitui-org/gitui"`.
   - Add macOS methods `asset = "gitui-mac.tar.gz"` with `arch = ["arm64"]`, and `asset = "gitui-mac-x86.tar.gz"` with `arch = ["amd64"]`. Both use `member = "gitui"` and `strip = 0`.
   - Drop the comment at `:889`.
5. **tealdeer:** `repo = "tealdeer-rs/tealdeer"` (both methods).
6. **ruff:** add a `kind = "uv-tool"` method with `pypi_pkg = "ruff"`, declared after the github_release methods so the ladder order is unchanged (same rank, stable sort). A uv-installed ruff then resolves to owner uv with a correct removal hint. This does not fix C1 or F1 by itself.
7. **Optional:**
   - hyperfine: switch to the musl assets (both arches exist: `hyperfine-v{ver}-{arch.machine}-unknown-linux-musl.tar.gz`).
   - Add `# Verified 2026-10-13: assets/members checked against latest release` to all 23 entries.

Verified unchanged and correct: the assets, members and strips of zoxide, fzf, lazygit, gh (Linux), yq, just, ruff, dust, hyperfine, bottom, glow, xh, duf, hexyl, miller, shfmt, tealdeer and fx, plus all 23 brew formula names (`git-delta` for delta).
