# Phase 30: Onboard Ghostty - Research

**Researched:** 2026-11-20
**Domain:** registry entry with three install routes, AppImage desktop integration, owned-region terminal config (shell sync and keys row), container e2e
**Confidence:** HIGH for the code mechanism, the Ghostty config semantics and the asset pins (read from source and probed live in a disposable container); MEDIUM for the FUSE pass in a rootless container and the KDE shortcut behavior.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Registry entry
- **D-01: One `[[tool]]`:** `id = "ghostty"`, `name = "Ghostty"`, `category = "terminal"`, `cmd = "ghostty"`, `tier = "user"`, `audience = "human"`, `priority = "P3"` (as wezterm and kitty), `post_install = ["apply_terminal_tuning"]`, `config_paths = ["~/.config/ghostty", "~/Library/Application Support/com.mitchellh.ghostty"]`. `"ghostty"` joins `_POST_15_3_HUMAN_TOOLS` (`tests/test_registry.py:276-285`). Patterns: `installer/registry.toml:3103-3131,3152-3164`; `~/Library` config paths exist for tealdeer and pnpm (`:1327,2239`).
- **D-02: Linux and Bazzite use two `tarball` methods, one per arch, `raw = true`, `member = "ghostty"`, `os = ["debian","fedora"]`, `version = "1.4.0"`,** URL `https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v{ver}/Ghostty-{ver}-x86_64.AppImage` (and `aarch64`); the `v` is literal in the path (draw.io's macOS `app` method does the same, `registry.toml:3336-3338`). Pins: x86_64 `50ad4f8b54a01e7d41426e7d12ffae9c88aa1c516ac140755e2bca596e1d2ae6` (equals the GitHub digest and was re-hashed after a container download), aarch64 `932e21c671c215e6140633027acb4e8705cef3377d335202211c32d88b5bf506` (GitHub digest). `raw` becomes an allowed key on `tarball` (`installer/model.py:637-640`; the install path checks `raw` without looking at the kind, `installer/download.py:408,418,460`; shared with phase 32's Bruno) and the loader refuses `raw` together with `strip` or `archive`. Reason: `github_release` takes no `version` or `sha256` (`model.py:69-82`; it installs the latest tag checked against the API digest, `download.py:116-140`), while `tarball` pins (`model.py:83-96,646-666`); `verify-registry` already handles tarball pins (`verify_registry.py:294-341,536-554,1088-1091,1188-1198`) so phase 33's bot covers them. jev pin_in_catalog_raw_key 0.85 (TypeSafe).
- **D-03: macOS is `kind = "cask"`, `cask = "ghostty"`, `app = "Ghostty.app"`, `min_os_version = "13"`,** installed with `--appdir` into `~/Applications` (`executors.py:700-703`). The cask has no `binary` stanza and the `cask` kind has no `cli` key (`model.py:105`), so no CLI link is promised; the CLI stays at `~/Applications/Ghostty.app/Contents/MacOS/ghostty`; the `# Verified` comment says why (27 D-10, 29 D-05). **Own reasoning** (jev accept_and_document low 0.53; first rung low 0.47). Ledger.
- **D-04: Arch is `kind = "pacman"`, `package = "ghostty"`** (`extra/ghostty 1.4.0 x86_64` read live); the tarballs carry `os = ["debian","fedora"]` only, so Arch never gets the community build; pacman is a hand-off, never a real install here.
- **D-05: "Community build" appears in `desc` and in a new optional per-method `note` key on download methods,** surfaced through `_perform`'s existing notes channel (`installer/engine.py:138-157,353`, rendered by `installer/render.py:485-494`) and repeated in `# Verified`; the label applies only to the AppImage methods. jev method_note_and_desc 0.98 (TypeSafe).
- **D-06: No `smoke_argv`:** the default `--version` works on the AppImage with and without FUSE (container probe: without `/dev/fuse` and fusermount the runtime prints "failed to utilize FUSE ... Trying to extract and run", then "Ghostty 1.4.0", exit 0; `executors.py:51-58`). Bazzite has `fuse-2.9.9`, `fuse3` and `fusermount`, so no reboot.
- **D-07: The install adds an application-menu entry and icon:** extract the AppImage's own `.desktop` and icon after the digest check, render with `desktop_entry.render` pointing at `~/.local/bin/ghostty`, record them as receipt leaves, remove them on uninstall. Bazzite users launch apps from the KDE menu; the other two app-image entries (wezterm, draw.io) write none (`desktop_entry.py` is used only by `cargo_distrobox`, `cargo_distrobox.py:20`), so this is new install code. jev add_menu_entry 0.78 (Laya).

#### Shell sync (Linux)
- **D-08: A Linux-only `_sync_ghostty`,** gated on `lookup("ghostty")`, writes an owned region `ghostty` holding `command = <shlex.join((zsh, "-l"))>` **at the top of the file** (a placement option on `_replace_owned_region`, shared with phase 29 D-01 for kitty), so a user `command` further down wins on its own; it also detects a user `command` outside the regions and reports `ghostty: partial: you already set command`. Ghostty is last-wins per key; `command` with arguments runs through `/bin/sh -c`, and shell integration still detects zsh from arg0's basename (`src/termio/shell_integration.zig:137-165`). Ghostty joins `_revert_terminal_shells` and `_TERMINAL_ROWS` (`"ghostty": ("ghostty", "Ghostty")`, `terminal_shell.py:854-890`; `version_status.py:734-740`). **Own reasoning** (jev top_with_report low 0.59; first rung low 0.58). Ledger.
- **D-09: The config file is Ghostty's preferred XDG path:** `$XDG_CONFIG_HOME/ghostty/config.ghostty` if it exists and is non-empty, else the legacy `config` if it exists and is non-empty, else `config.ghostty`; shell and keys regions share it. Both names load (legacy first) and Ghostty warns when both exist, so writing `config.ghostty` beside a user's legacy `config` would override them.
- **D-10: A user `config-file =` include is not followed:** write anyway and add a `partial:` line saying included files were not checked (included files load after the file that names them, so an included `command` wins without any action; Alacritty's refusal would mean such users never get zsh). jev first rung none_of_these 0.71 contradicted the evidence; second opinion write_and_note low 0.53. **jev overridden / Own reasoning.** Ledger.

#### Keys row
- **D-11: The row writes region `ghostty-keys`** with `sibling_regions = ("ghostty",)`: Linux `keybind = ctrl+shift+k=text:\x0c`; macOS `keybind = super+k=text:\x0c`; no Option or Alt lines (the macOS defaults `esc:b` and `esc:f` fire whatever `macos-option-as-alt` says, and the owner decided no Alt rows on Linux); `macos-option-as-alt` is never written. Ghostty's default `cmd+k` is the native `clear_screen`, which does not send Ctrl+L, so the macOS line is needed under KEYS-03 (research `STACK.md:25,74` "macOS: write nothing" is overridden, as 27 D-14 did for WezTerm); SPEC R3's "nothing written where the vendor default already meets a rule" still holds for word navigation and same-directory. jev first rung none_of_these 0.81 contradicted the evidence; second opinion rebind_to_ctrl_l 0.95. **jev overridden.**
- **D-12: Conflict detection normalizes the chord** (modifier order; `cmd`/`command` to `super`, `opt`/`option` to `alt`, `control` to `ctrl`), drops the prefixes `all:`, `global:`, `unconsumed:` and `performable:`, ignores key tables and sequences, and reports `ghostty: partial: you already bind ctrl+shift+k`; on macOS the scan covers all four loaded files. jev normalize_then_compare 0.96 (TypeSafe).
- **D-13: The macOS file mirrors Ghostty's `preferredDefaultFilePath`:** App Support `config.ghostty`, else legacy `config`, if one exists and is non-empty; otherwise the preferred XDG file if it exists; otherwise App Support `config.ghostty` (`~/Library/Application Support/com.mitchellh.ghostty/`). A pure resolver `(platform_os, home, environ)` lets Linux CI test every case, including empty files. It needs phase 28's row field `config_path` to take `platform_os` *(amended 2026-11-19, 30 D-13, in 28-CONTEXT D-03)*. jev terminals_preferred_file 0.97 (TypeSafe).
- **D-14: `same_directory` is `vendor`** with a dated note: `window-`, `tab-` and `split-inherit-working-directory` default to true (Ghostty `Config.zig` v1.4.0 :2086-2099) and need shell integration, which works with our `command`; a user's `shell-integration = none` is the user's choice.

#### Tests, removal and the container proof
- **D-15: Byte goldens through the public routes in a scratch HOME** (28 D-10): Linux created-file bytes (shell plus keys regions), macOS created-file bytes (keys only), user content kept, a user `command` and a user `ctrl+shift+k` each giving `partial`, a regression assert that `macos-option-as-alt` appears in neither golden, the four macOS resolver cases, and drift: pending only without a record (28 D-06), reconfigure restores, a second reconfigure is a no-op. Registry tests: Arch amd64 and arm64 resolve to pacman; debian and Bazzite amd64 to the x86_64 tarball; arm64 to the aarch64 tarball; macOS to the cask; URLs equal the live asset names; sha256 values are lowercase 64-hex; the loader refuses `raw` with `strip`; a digest-mismatch fixture raises `ChecksumMismatch` and places nothing (`download.py:486-510`); the phase 27 closed-table row and phase 28 completeness test. The real-Mac check (`ghostty +show-config`, `+list-keybinds`) is a UAT line. jev byte_goldens_public_routes 0.96 (TypeSafe).
- **D-16: The receipt records `~/.local/bin/ghostty` (kind `file`) plus the menu entry and icon leaves;** `app._after_removal` calls `strip_terminal_keys` for the Ghostty row (strips `ghostty-keys`, the sibling `ghostty` region and the record) and deletes the config file and created directories only if the installer created them and they now hold only whitespace; `config_paths` are kept by default. Without the sibling strip the shell region would outlive the tool (`_revert_terminal_shells` runs only when zsh goes, `terminal_shell.py:917-921`).
- **D-17: The residue diff excludes the existing allowlist** (`scripts/e2e-residue-allowlist.txt`: `.cache`) and also asserts `/tmp` holds no installer leftovers: without FUSE the AppImage writes thumbnails under `~/.cache` and `/tmp/appimage_extracted_*`. **Own reasoning** (first rung installer_folders_only 0.92, weaker than the shared leftover check; second opinion low 0.54). Ledger.
- **D-18: A dedicated container target `ghostty`** modeled on `audit-landing` and `bun-lifecycle` (`scripts/container-e2e-verify.sh:95-130`): a Bazzite-like `fedora:44` with `/run/ostree-booted` (so `detect_immutable` reads true, `installer/platform.py:16,60`), `fuse fuse3`, `--device /dev/fuse`, never privileged; install through the engine, take file lists, run `ghostty --version`, check both regions, uninstall, diff against the receipt plus the allowlist; a second pass without FUSE; the container is removed on every exit. Arch's pacman is a hand-off, covered by resolve tests only. jev dedicated_target 0.72 (Laya).
- **D-19: Dependencies:** phases 27, 28 and 29 execute first (the skill table, `TERMINAL_KEYS` and the helpers do not exist yet); phase 29 adds rows to the same dict, table and `_TERMINAL_ROWS` (merge coupling); phase 31 extends the table.

### Claude's Discretion
- The install note's wording, the menu entry's category and name text, and helper names.

### Deferred Ideas (OUT OF SCOPE)
- To confirm (UAT or planning): whether `TERMINFO` resolves `xterm-ghostty` inside an AppImage window (zsh line editing), under FUSE and extract-and-run; the exact flags of `ghostty +show-config` and `+list-keybinds`; whether Option+Left/Right `esc:b` works on a Spanish Mac layout; whether the 5 s status-probe timeout is enough for an AppImage extracting about 49 MB without FUSE.
- SPEC out of scope: iTerm2 and the Herdr desktop app (phase 31); a Flatpak, snap or source-build route; theme or font customization; real-Mac verification.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NTERM-01 | Ghostty is in the catalog: the official cask on macOS (user-writable app location), a digest-verified community AppImage on Linux and Bazzite with a visible "community build" note, and pacman on Arch; its shell syncs to zsh on Linux and it meets SKILL-01 through its owned keys region. | Registry: pins re-verified live (Package and Asset Audit), loader changes and every test pin listed (Registry Touch List). Shell: `_sync_ghostty` on the existing `Placement.TOP` and `commit_region` (Pattern 2). Keys: a fourth `TERMINAL_KEYS` row (Pattern 1); golden syntax accepted by real Ghostty 1.4.0 (probe 2). Menu entry: the AppImage's own desktop file and icon, extracted by pattern without FUSE (probe 1, Pattern 3). Removal: already generic in `app._after_removal` (`installer/app.py:630-636`). Container proof: target modeled on `herdr-keys` (Pattern 4). |
</phase_requirements>

## Project Constraints (from CLAUDE.md and AGENTS.md)

- uv owns the environment; never pip, poetry or a hand-rolled venv. [VERIFIED: AGENTS.md]
- Never run `make run`, `make fix`, `make uninstall`, `make doctor`, `make dev-setup` or mutating `systemctl --user` on the host. Real installs and removals only in disposable containers (`scripts/detect-container-runtime.sh`), removed afterwards. [VERIFIED: AGENTS.md]
- Zero sudo: no `sudo`, `pkexec` or `doas` in any code path; pacman stays a hand-off. [VERIFIED: AGENTS.md]
- Never bypass a gate (ruff, ruff format, pyright, bandit, vulture, shellcheck, pytest with coverage floor); no `skip`/`xfail` to go green. [VERIFIED: AGENTS.md, .claude/testing.md]
- Plans are `type: execute`, test-first inside one green commit (RED output kept in the SUMMARY); never commit a red tree. [VERIFIED: .claude/testing.md "Test-first inside one green commit"]
- While working run only the tests covering the edit (`uv run pytest <files> --no-cov -q`); after a plan run `make validate` and `make test` once each. [VERIFIED: AGENTS.md]
- Every test xdist-safe: `tmp_path`, `monkeypatch` for HOME and env, no fixed paths, offline (conftest refuses internet sockets and unlisted subprocess launches). [VERIFIED: .claude/testing.md; tests/conftest.py:133-171]
- Architecture: less total code, no orphan helpers (a shared helper must have production callers), `setup.py` wiring only, one apply workflow. [VERIFIED: .claude/architecture.md]
- English only; coherent commits (amend or squash review fixes). [VERIFIED: AGENTS.md, .claude/git-workflow.md]
- Temporary files: unique run dir, `TMPDIR` exported, removed on every exit path. [VERIFIED: ~/.claude/CLAUDE.md]

## Summary

Phases 27-29 left exactly the mechanism this phase needs. `TERMINAL_KEYS` is a dict keyed by registry id whose `KeysRow` already carries `config_path(platform_os, home, environ)`, a `Placement` (`END`, `TOP`, `BEFORE_RETURN`), `sibling_regions`, `bind_created_path`, callable `Writes.snippet` and `KeysPlan.notes`; `apply_terminal_keys`, `terminal_keys_pending` and `strip_terminal_keys` are generic, and `app._after_removal` already strips any row's regions when its tool is removed. So Ghostty is mostly data: one registry entry, one keys row, one `_sync_ghostty` branch modeled on Alacritty's `commit_region` pattern, one `_TERMINAL_ROWS` entry, one `_revert_terminal_shells` line, plus three small loader/installer changes (`raw` and `note` on `tarball`, the menu entry and icon).

Two live container probes on 2026-11-20 settled the riskiest facts. The pinned x86_64 AppImage hashes to the CONTEXT digest; its runtime is uruntime v0.8.1, whose `--appimage-extract PATTERN` extracts only `com.mitchellh.ghostty.desktop` and `com.mitchellh.ghostty.png` into `./AppDir/` without FUSE; the AppImage's root desktop file has no `DBusActivatable` key but does carry `X-KDE-Shortcuts=Ctrl+Alt+T`. Real Ghostty 1.4.0 accepted the planned Linux golden (`+show-config` printed `command = /usr/bin/zsh -l`, `+list-keybinds` printed `keybind = ctrl+shift+k=text:\x0c`), a user `command` placed below the top region won, and a binding in the legacy `config` file was silently overridden by our `config.ghostty` line. That last finding means the conflict scan must cover both XDG files on Linux too, not only the four macOS files (D-12 names macOS only).

Two findings change verification details, not decisions. First, every Ghostty CLI action that loads config (`+show-config`, `+validate-config`) writes a 2 KB template `config.ghostty` when no config exists, while `--version` writes nothing; the container driver must only read config back after the installer wrote one. Second, uruntime leaves `/tmp/appimage_extracted_*.lock` and a dangling symlink in `/tmp` by design after an extract-and-run, so D-17's `/tmp` assertion must be scoped to installer-owned names, and the install smoke and extraction should run with `TMPDIR` set to the install's own temporary directory.

**Primary recommendation:** Add Ghostty as data on the existing mechanism (a `TERMINAL_KEYS["ghostty"]` row with `Placement.TOP`, `bind_created_path=True` and a shared `ghostty_config_path(platform_os, home, environ)` resolver), extend `tarball` with `raw`, `note` and one desktop-id key, extract the menu files with `--appimage-extract PATTERN` through `ctx.runner`, and prove the Linux route in a `ghostty` container target cloned from `herdr-keys`.

## Architectural Responsibility Map

This is a local CLI/TUI installer; the tiers are its modules.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Catalog entry, pins, `note`, `raw`, desktop id | Registry data (`installer/registry.toml`) | Loader validation (`installer/model.py`) | The registry selects; the loader refuses bad combinations at load time. |
| AppImage download, digest check, placement, menu files | Download executor (`installer/download.py`) | `installer/desktop_entry.py` (render) | Same staged-then-swap flow as the binary; render stays pure. |
| Receipt leaves for menu files | `download.artifact_paths` | `installer/receipts.py`, `installer/uninstall.py` | `artifact_paths` is "the one formula" every recorder and remover reads (`download.py:284-300`). |
| Install note | Engine notes channel (`installer/engine.py:138-157,353`) | `installer/render.py:485-497`, `installer/catalog_tui.py:711-712` | Existing row-note path; no new channel. |
| zsh `command` region on Linux | Terminal sync (`installer/terminal_shell.py`) | `installer/terminal_regions.py` primitives | The sync owns every shell region; keys rows only strip it as a sibling. |
| Keys region, drift, reconfigure, strip | `installer/terminal_keys.py` row | `installer/post_install.py`, `installer/version_status.py`, `installer/app.py` | All four routes are already generic over `TERMINAL_KEYS`. |
| Config-file resolution (both OSes) | Pure resolver in `installer/terminal_regions.py` | used by the sync, the keys row and the revert | One resolver so shell, keys and strip always touch the same file. |
| Container proof | `scripts/container-e2e-verify.sh` + `tests/e2e_ghostty_driver.py` | host tests with stubbed `ct` | Mirrors the `herdr-keys` split (29-05). |
| Skill table row | `.claude/skills/tool-onboarding/SKILL.md` | `tests/test_tool_onboarding_skill.py` | Closed table enforced by tests. |

## CONTEXT Reconciliation

CONTEXT was written before phases 27-29 executed. Every statement that assumed missing code, checked against the code on this branch:

| # | What CONTEXT says | What the code is now | What the plan should do |
|---|---|---|---|
| R1 | Boundary and D-19: "`installer/terminal_keys.py`, `installer/terminal_regions.py` and `TERMINAL_KEYS` do not exist yet". | All exist. `TERMINAL_KEYS` holds `"alacritty"`, `"kitty"`, `"wezterm"` [VERIFIED: installer/terminal_keys.py:257-311]. | Add a fourth row; no prerequisite work. The merge coupling with phase 29 is resolved (29 is executed). |
| R2 | D-08: "a placement option on `_replace_owned_region`, shared with phase 29 D-01 for kitty" (new work). | It exists: `class Placement(Enum): END = "end"`, `TOP = "top"`, `BEFORE_RETURN = "before_return"` [VERIFIED: installer/terminal_regions.py:26-29]; `TOP` returns `f"{region}{content}"` [VERIFIED: installer/terminal_regions.py:214-215]. kitty's keys row uses `OwnedRegion(KITTY_KEYS, "#", Placement.TOP)` [VERIFIED: installer/terminal_keys.py:276]. | Use `Placement.TOP`; drop "placement option" from the SPEC in-scope amendment as already delivered. |
| R3 | D-13: "needs phase 28's row field `config_path` to take `platform_os`". | Done: `config_path: Callable[[str, Path, Mapping[str, str]], Path]  # Platform, home, environment.` [VERIFIED: installer/terminal_keys.py:91]; kitty's resolver already branches on `platform_os == "macos"` [VERIFIED: installer/terminal_regions.py:245-266]. | Write `ghostty_config_path(platform_os, home, environ)` with that signature; no row-type change. |
| R4 | D-08 cites `_revert_terminal_shells` at `terminal_shell.py:854-890`; D-16 cites the zsh-gone revert at `terminal_shell.py:917-921`. | `_revert_terminal_shells` is at `installer/terminal_shell.py:604-640`; the zsh-gone branch is `installer/terminal_shell.py:667-671`. | Cite the new lines. |
| R5 | D-08 cites `_TERMINAL_ROWS` at `version_status.py:734-740`. | `installer/version_status.py:735-741` (verbatim below). | Add `"ghostty": ("ghostty", "Ghostty")`. |
| R6 | D-16: "`app._after_removal` calls `strip_terminal_keys` for the Ghostty row" (implied new code). | Already generic: `row = TERMINAL_KEYS.get(tool.id)` then `strip_terminal_keys(row, tool.id, platform_os, Path.home(), os.environ)` [VERIFIED: installer/app.py:630-636]. `strip_terminal_keys` strips `(*row.sibling_regions, row.ownership.region)` [VERIFIED: installer/terminal_keys.py:450-452]. | No `app.py` change; the row's `sibling_regions=("ghostty",)` is enough. |
| R7 | D-01 cites `_POST_15_3_HUMAN_TOOLS` at `tests/test_registry.py:276-285`. | `tests/test_registry.py:278-282`, currently `"alacritty"`, `"copilot"`, `"neovim"`. | Add `"ghostty"`; see the full pin list below. |
| R8 | D-18: "a Bazzite-like `fedora:44`". | The landing targets use `LANDING_IMAGE="$IMAGE_FEDORA"` with `IMAGE_FEDORA=fedora:latest` [VERIFIED: scripts/container-e2e-verify.sh:19, 2711]. | Either keep `fedora:latest` like every landing target (recommended: one image, shared pull) or set the ghostty target's image to `registry.fedoraproject.org/fedora:44`; flag for the planner. Today `fedora:latest` is Fedora 44 or later [ASSUMED]. |
| R9 | D-18 cites `scripts/container-e2e-verify.sh:95-130` as the model. | Those lines are the usage text; implementations: landing infra `:2705-2851`, `cmd_bun_lifecycle` `:2879-2909`, `cmd_herdr_keys` `:2913-2938`, dispatch `:2960-2975`. | Model the new target on `cmd_herdr_keys` (newest, PID-named container). |
| R10 | D-15: "the phase 27 closed-table row and phase 28 completeness test". | Both exist and will fail until Ghostty lands: `test_table_matches_the_registry` [VERIFIED: tests/test_tool_onboarding_skill.py:642-645], `test_table_cells_follow_the_terminal_keys_table` requires every `TERMINAL_KEYS` id's clear cell to start with `written` [VERIFIED: tests/test_tool_onboarding_skill.py:603-630], completeness [VERIFIED: tests/test_terminal_keys.py:273-277]. | Add the skill row and the keys row in the same commit as the registry entry. |
| R11 | D-12: the scan covers "all four loaded files" on macOS (silent on Linux). | Ghostty loads the legacy XDG `config` then `config.ghostty` on every OS [CITED: ghostty Config.zig v1.4.0:4245-4262]; probe 2 showed a legacy-file `keybind = ctrl+shift+k=reset` silently overridden by our `config.ghostty` line. | Not a conflict with D-12 (it adds coverage): scan every default file Ghostty loads on that OS, two on Linux, four on macOS. Same for D-08's user-`command` detection. |
| R12 | D-08: write `command` at the top so a user `command` further down wins, and report `partial`. | Verified for the same file (probe 2: a later `command = /bin/bash` won). A user `command` in the legacy `config` loads BEFORE `config.ghostty`, so writing ours would override it. D-08 is marked "Own reasoning" (provisional). | Recommend: when a user `command` is found in a file loaded before the target, write no `command` line and report the same `partial:`; in the target file below the region, writing stays harmless. Owner confirmation (Assumptions A3). |
| R13 | D-17: assert `/tmp` holds no installer leftovers. | uruntime keeps its `<target>.lock` inode after cleanup by design [CITED: github.com/VHSgunzo/uruntime docs/CONFIGURATION.md "Extraction cleanup"], and probe 2 found `appimage_extracted_*.lock` plus a dangling symlink in `/tmp` after the reuse delay. The install smoke (`--version`) on a no-FUSE host creates them. | Keep D-17, scoped: the installer's own `/tmp/tools-installer-*` dirs must be gone, and the smoke plus the extraction run with `TMPDIR=<install workdir>` so uruntime files land in the workdir the installer deletes. uruntime files from the harness's own `ghostty --version` are listed as INFO, not failures. |
| R14 | D-07: render with `desktop_entry.render`. | `render` rewrites only `TryExec=`, `Exec=` (every group) and `Icon=` [VERIFIED: installer/desktop_entry.py:36-52]. The AppImage's desktop file carries `X-KDE-Shortcuts=Ctrl+Alt+T` (probe 1). | Decide whether to drop `X-KDE-Shortcuts` (Konsole on Bazzite owns Ctrl+Alt+T) [ASSUMED risk]; if yes, a `drop` key set on `render` is the smallest change. Menu text is Claude's discretion. |
| R15 | D-01 lists no `owner_probes`. | wezterm (pacman-only native) declares `owner_probes = ["pacman"]`, and `test_native_package_manager_rows_declare_their_owner_probes` pins the set of rows with native probes [VERIFIED: tests/test_registry.py:2252-2290]. | Add `owner_probes = ["pacman"]` and `"ghostty": ("pacman",)` to that test (additive to D-01). |

## Standard Stack

No new libraries. Everything uses the standard library and code already in the repository.

### Core (existing modules, reused)
| Module | Purpose | Why |
|--------|---------|-----|
| `installer/terminal_keys.py` | `KeysRow`, `apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys` | Phase 28's single mechanism; every route reads it. |
| `installer/terminal_regions.py` | `replace_owned_region`, `Placement`, `commit_region`, `strip_region`, `snapshot_text`, `xdg_config_home` | Owned-region primitives shared by shell sync and keys. |
| `installer/download.py` | `install_download`, `_fetch_verified`, `_replace_raw`, `artifact_paths` | The digest-verified raw placement and the artifact formula. |
| `installer/desktop_entry.py` | `render(source, binary=..., icon=...)` | Already refuses relative paths and control characters. |
| `installer/cargo_distrobox.py` | `_swap` staged-pair swap with rollback | The only existing multi-file swap; reuse instead of a second copy. |

### Upstream artifacts
| Artifact | Version | Purpose |
|----------|---------|---------|
| `pkgforge-dev/ghostty-appimage` AppImage | v1.4.0 (published 2026-10-28) | Linux and Bazzite route (community build). |
| Homebrew cask `ghostty` | 1.4.0, `depends_on macos >= 13`, `auto_updates true` | macOS route. |
| Arch `extra/ghostty` | 1.4.0-1, x86_64 | Arch route (hand-off). |

## Package and Asset Audit

No Python, npm or crates package is installed by this phase, so the package-legitimacy seam has nothing to check. The supply-chain surface is the community AppImage; it is pinned by digest.

| Asset | Source | Digest (GitHub API, 2026-11-20) | CONTEXT pin | Verdict |
|-------|--------|----------------------------------|-------------|---------|
| `Ghostty-1.4.0-x86_64.AppImage` (49,217,678 B) | `gh api repos/pkgforge-dev/ghostty-appimage/releases/tags/v1.4.0` | `sha256:50ad4f8b54a01e7d41426e7d12ffae9c88aa1c516ac140755e2bca596e1d2ae6` | same | MATCH, and re-hashed after a container download: `50ad4f8b...2ae6  g.AppImage` (probe 1) [VERIFIED: GitHub API + sha256sum] |
| `Ghostty-1.4.0-aarch64.AppImage` (47,990,666 B) | same | `sha256:932e21c671c215e6140633027acb4e8705cef3377d335202211c32d88b5bf506` | same | MATCH [VERIFIED: GitHub API] |

Repository facts: MIT, 232 stars, not archived, pushed 2026-11-20; `releases/latest` is `v1.4.0`; upstream `ghostty-org/ghostty` tags `v1.4.0` (latest stable) [VERIFIED: gh api]. The repo publishes rebuild tags such as `v1.2.0+1` and `v1.1.3+3` whose assets keep the plain version name (`Ghostty-1.2.0-x86_64.AppImage`) [VERIFIED: gh api releases list] (see Pitfall 6).

## Registry Touch List

Every file and test a new terminal entry touches, modeled on wezterm, kitty and draw.io:

| Where | Change | Evidence |
|-------|--------|----------|
| `installer/registry.toml` | New `[[tool]]` after the alacritty entry, dated `# Verified 2026-11-20` comment (asset digests, cask facts, no CLI link, community label, FUSE note). | Pattern: wezterm block [VERIFIED: installer/registry.toml:3101-3131]. |
| `installer/model.py` `METHOD_PARAMS["tarball"]` | Add `"raw"`, `"note"` and the desktop-id key; today the set is `"url", "member", "strip", "bin_name", "archive", "bin_dir", "version", "sha256", "smoke_argv"`. | [VERIFIED: installer/model.py:83-95] |
| `installer/model.py` validation | Already refuses `strip` with `raw`: `if params.get("archive") == "zip" or params.get("raw") is True:` raise "'strip' does not apply to a zip archive or a raw asset". Add: `raw` with `archive` refused; `note` a non-empty single-line string; desktop id matching a safe file-name pattern. | [VERIFIED: installer/model.py:667-673]. No current registry method combines `raw` and `archive` (checked: every raw method lists only `asset, checksum, member, raw, repo, smoke_argv`) [VERIFIED: tomllib scan this session]. |
| `tests/test_model.py` | Loader refusals (raw+strip, raw+archive, bad note, bad desktop id); `test_shipped_registry_uses_only_allowed_method_keys` keeps passing. | [VERIFIED: tests/test_model.py:1397-1410] |
| `tests/test_registry.py` | `_POST_15_3_HUMAN_TOOLS` add `"ghostty"` (`:278-282`); audience `"human": 28` to 29 (`:300-304`); `len(tools) == 86` to 87 (`:1214`); tier `"user": 49` to 50 (`:1266-1270`); post_install declarers add `"ghostty"` (`:1370-1378`); owner probes add `"ghostty": ("pacman",)` (`:2271-2276`); new resolve test modeled on `test_wezterm_appimage_covers_bazzite_where_kitty_cannot` (`:1632-1657`); extend `test_pinned_methods_render_their_upstream_asset_names` (`:2019`). | [VERIFIED: read this session] |
| `tests/test_terminal_keys.py` | `assert set(TERMINAL_KEYS) == {"alacritty", "kitty", "wezterm"}` (`:250`) and `missing_rows(load_tools(REGISTRY), {}) == {"alacritty", "kitty", "wezterm"}` (`:287`) gain `"ghostty"`; new goldens. | [VERIFIED: tests/test_terminal_keys.py:250,287] |
| `installer/terminal_shell.py` | `_sync_ghostty` branch in `sync_terminal_shells` after Alacritty (`:756-765` pattern); a ghostty strip in `_revert_terminal_shells` (`:604-640`). | [VERIFIED] |
| `installer/version_status.py` | `_TERMINAL_ROWS` add `"ghostty": ("ghostty", "Ghostty")`. | [VERIFIED: installer/version_status.py:735-741] |
| `.claude/skills/tool-onboarding/SKILL.md` | One `ghostty` row in the closed table (`:209-218`), clear cell starting `written`. | [VERIFIED] |
| `verify-registry` | No code change: tarball pins with `{ver}` in a GitHub release URL are read by `_newer_stable_findings` (`app`/`tarball`, `{ver}` url, `_GITHUB_RELEASE_PATH`) and digest-checked by `_github_pin_mismatch`. | [VERIFIED: installer/verify_registry.py:101-103, 294-341, 536-554] |
| `scripts/e2e-residue-allowlist.txt` | Likely none (`.cache` already covers `~/.cache/AppImage-Cache` and `~/.cache/thumbnails`, probe 1). | [VERIFIED: allowlist line `.cache  # runtime cache root ...`] |
| `README.md`, `docs/` | No catalog tool list mentions terminals (no `wezterm` hit in README or docs) [VERIFIED: rg]. | none |

Verbatim values used above:
- `_TERMINAL_ROWS` [VERIFIED: installer/version_status.py:735-741]: `"kitty": ("kitty", "Kitty")`, `"wezterm": ("wezterm", "WezTerm")`, `"konsole": ("zsh", "Konsole")`, `"alacritty": ("alacritty", "Alacritty")`, `"herdr": ("herdr", "herdr")`.
- `_POST_15_3_HUMAN_TOOLS` [VERIFIED: tests/test_registry.py:278-282]: `"alacritty"`, `"copilot"`, `"neovim",  # Phase 24.1`.
- Counts [VERIFIED: tests/test_registry.py:300-304, 1214, 1266-1270]: `"both": 50`, `"ai": 8`, `"human": 28`; `assert len(tools) == 86`; `"system": 28`, `"ai": 9`, `"user": 49`.
- `METHOD_PARAMS["cask"]` [VERIFIED: installer/model.py:105]: `frozenset({"cask", "app", "min_os_version", "smoke_argv"})`.
- `DOWNLOAD_KINDS = ("github_release", "tarball")` [VERIFIED: installer/download.py:35].

## Architecture Patterns

### System Architecture Diagram

```
 catalog selection (TUI/CLI)
        |
        v
 resolve_methods(tool, platform) --macos+brew--> cask: brew install --cask --appdir=~/Applications ghostty
        |                        --arch--------> pacman: hand-off command (no sudo, no install)
        | debian/fedora/bazzite (immutable ok: tarball is not a native kind)
        v
 install_download (tarball, raw)
   curl -> workdir/Ghostty-1.4.0-<arch>.AppImage
   sha256 == pin ?  --no--> ChecksumMismatch, nothing placed
        | yes
   chmod +x; env --chdir=workdir TMPDIR=workdir <asset> --appimage-extract <id>.desktop / <id>.png
   render desktop (Exec/TryExec -> ~/.local/bin/ghostty, Icon -> absolute png)
   stage .new siblings -> smoke --version (TMPDIR=workdir) -> swap binary, desktop, icon
        |
        v
 receipts.record: file ~/.local/bin/ghostty + leaf .desktop + leaf .png (only if created now)
        |
        v
 post_install apply_terminal_tuning -> TERMINAL_KEYS["ghostty"]
   ghostty_config_path(os, home, env) -> scan loaded files -> ghostty-keys region (TOP) -> record
        |
        v
 post-run terminal sync (Linux, zsh present, lookup("ghostty") found)
   same resolver -> scan for user command / config-file -> ghostty region (TOP) or partial
        |
        v
 status pass: terminal_keys_pending -> "≈ apply install tuning"; dry-run sync -> "point Ghostty at zsh"
        |
 uninstall: receipt paths removed -> _after_removal -> strip ghostty + ghostty-keys -> drop created file
```

### Recommended file layout
```
installer/terminal_regions.py   # GHOSTTY, GHOSTTY_KEYS, GHOSTTY_CREATED, ghostty_config_path,
                                # ghostty_default_files, scan_ghostty, ghostty_chord, validate_ghostty
installer/terminal_keys.py      # TERMINAL_KEYS["ghostty"], _ghostty_plan
installer/terminal_shell.py     # _sync_ghostty, revert line
installer/download.py           # menu-entry extraction + leaves in artifact_paths
tests/test_terminal_keys.py     # goldens, resolver cases, conflicts, drift
tests/test_terminal_shell.py    # shell region, partials, revert
tests/test_download.py          # extraction, leaves, mismatch places nothing
tests/e2e_ghostty_driver.py     # in-container verbs
tests/test_container_e2e_ghostty.py  # host tests with stubbed ct
```

### Pattern 1: The keys row (data on the existing mechanism)

```python
# Source: modeled on TERMINAL_KEYS["kitty"] (installer/terminal_keys.py:275-289)
"ghostty": KeysRow(
    ownership=OwnedRegion(GHOSTTY_KEYS, "#", Placement.TOP),
    config_path=ghostty_config_path,            # (platform_os, home, environ) -> Path
    plan=_ghostty_plan,                         # scans every loaded default file
    validate=validate_ghostty,                  # region lines must start with "keybind ="
    summary="Ghostty keys: ...",                # Claude's discretion
    created_record=GHOSTTY_CREATED,             # "terminal-ghostty-created"
    same_directory=Vendor("2026-11-20, Ghostty Config.zig v1.4.0:2086-2099: window-, tab- and "
                          "split-inherit-working-directory default to true. The installer writes nothing."),
    sibling_regions=(GHOSTTY,),
    bind_created_path=True,                     # resolution depends on which files exist
),
```

Lines the plan renders (D-11), with the escape verified against real Ghostty (probe 2) and against Ghostty's own default `.{ .text = "\\x01" }` [CITED: ghostty Config.zig v1.4.0:7394-7397]:
- Linux: `keybind = ctrl+shift+k=text:\x0c` (Python literal `"keybind = ctrl+shift+k=text:\\x0c"`).
- macOS: `keybind = super+k=text:\x0c`, plus a `KeysPlan.notes` line naming the displaced default `clear_screen` (the skill's conflicts rule, SKILL.md:225). Ghostty binds `super+k` to `clear_screen` with the `performable` flag on Darwin only [CITED: ghostty Config.zig v1.4.0:7128-7138]; Linux has no default `ctrl+shift+k` binding (no other `'k'` binding in Config.zig).
- `clear_binding(row, platform_os)` returns `("cmd+k" if platform_os == "macos" else "ctrl+shift+k", row.clear)` [VERIFIED: installer/terminal_keys.py:124-129]; map `cmd+k` to `super+k` when rendering.
- Refusal like kitty's `clear_all_shortcuts`: a user `keybind = clear` outside the regions (it "removes ALL keybindings up to this point" [CITED: ghostty Config.zig v1.4.0 keybind docs]) would clear a `TOP` region, so refuse with one line.

Golden for a new Linux file through the install route (keys written first by post_install, shell region placed on top by the later sync), marker format `f"{comment} {edge} tools-installer terminal-shell {terminal} {edge}"` [VERIFIED: installer/terminal_regions.py:172-173]:
```
# >>> tools-installer terminal-shell ghostty >>>
command = /usr/bin/zsh -l
# <<< tools-installer terminal-shell ghostty <<<
# >>> tools-installer terminal-shell ghostty-keys >>>
keybind = ctrl+shift+k=text:\x0c
# <<< tools-installer terminal-shell ghostty-keys <<<
```
Real Ghostty 1.4.0 parsed exactly these lines (probe 2). macOS golden: only the keys region with the `super+k` line; assert `macos-option-as-alt` absent in both.

### Pattern 2: Config resolution and scanning (one pure resolver)

Ghostty v1.4.0 facts [CITED: github.com/ghostty-org/ghostty src/config/file_load.zig@v1.4.0]:
- `open()` counts a path only if it is a regular file with size > 0 (`if (stat.size == 0) return OpenFileError.FileIsEmpty;`, `:142-176`).
- Linux `preferredXdgPath`: `config.ghostty` if open succeeds, else legacy `config`, else `config.ghostty` (`:38-59`). Matches D-09.
- macOS `preferredDefaultFilePath`: preferred App Support (`config.ghostty`, else legacy `config`) if it opens; else preferred XDG if it opens; else App Support `config.ghostty` (`:105-125`). Matches D-13.
- Load order [CITED: Config.zig v1.4.0:4245-4300]: legacy XDG, XDG; on macOS then legacy App Support, preferred App Support. Later wins per key. When nothing loads, Ghostty writes a template (`writeConfigTemplate`), App Support on macOS, XDG elsewhere (`:4302-4313`); probe 2 confirmed a 2,011-byte all-comment `config.ghostty` after `+show-config` on an empty HOME, and none after `--version`.
- Line parser [CITED: src/cli/args.zig@v1.4.0:1449-1490]: trim whitespace and CR; skip blank lines and lines whose first character is `#`; split at the first `=`; trim key and value; strip one pair of surrounding double quotes.
- `config-file` includes load after the file that names them [CITED: Config.zig v1.4.0:2578-2605].

Resolver shape (implementation sketch, names are discretion):
```python
def ghostty_config_path(platform_os: str, home: Path, environ: Mapping[str, str]) -> Path:
    xdg = xdg_config_home(home, environ) / "ghostty"
    preferred_xdg = _first_nonempty(xdg / "config.ghostty", xdg / "config") or xdg / "config.ghostty"
    if platform_os != "macos":
        return preferred_xdg
    support = home / "Library" / "Application Support" / "com.mitchellh.ghostty"
    return (_first_nonempty(support / "config.ghostty", support / "config")
            or _first_nonempty(preferred_xdg) or support / "config.ghostty")
# _first_nonempty: p.is_file() and p.stat().st_size > 0 (follows symlinks like openFileAbsolute)
```
`ghostty_default_files(platform_os, home, environ)` returns the load-order list (two on Linux, four on macOS) for the scans; the scans read every file with `read_capped` and strip both owned regions from each before parsing (as `scan_kitty` does, `installer/terminal_regions.py:323`).

Chord normalization (D-12 plus findings): modifier aliases are exactly `cmd`/`command` to `super`, `opt`/`option` to `alt`, `control` to `ctrl` [CITED: src/input/key_mods.zig@v1.4.0:8-14]; flags `all`, `global`, `unconsumed`, `performable` are prefixes up to `:` [CITED: Binding.zig@v1.4.0:148-196]; `chain=` lines bind nothing new (`Binding.zig:123-125`); sequences use `>` and tables use `/` (skip both, D-12). Also normalize the physical key name `key_k` to `k` (Ghostty maps `'k'` to `.key_k`, key.zig:791) and compare keys case-insensitively, so an ambiguous spelling reports `partial` rather than being overridden [ASSUMED: conservative choice].

Shell sync (Pattern from `_sync_alacritty`, `installer/terminal_shell.py:483-507`): read with `read_settings`, plan body `f"command = {shlex.join((zsh_path, '-l'))}"`, `replace_owned_region(text, GHOSTTY, body, placement=Placement.TOP)`, then `commit_region(..., validate=validate_ghostty, created_marker=<GHOSTTY_CREATED marker>, bind_path=True)` so whichever writer creates the file records it and the keys strip can delete it. Ghostty runs a `command` with arguments through `/bin/sh -c` and detects zsh from arg0's basename [CITED: Config.zig v1.4.0:1130-1159; shell_integration.zig@v1.4.0:137-165]. Treat any user `command` line, including an empty `command =` (which resets to default), as the user's.

### Pattern 3: Menu entry and icon from the AppImage

Facts (probe 1, uruntime v0.8.1 inside the pinned AppImage):
- `--appimage-extract [PATTERN]` "If pattern is passed, only extract matching files"; extraction goes to `./AppDir/` plus a `squashfs-root -> ./AppDir` symlink, without FUSE.
- Root files: `com.mitchellh.ghostty.desktop` (694 B) and `com.mitchellh.ghostty.png` (46,837 B, the 256x256 icon: the bundle script sets `ICON=.../256x256/apps/com.mitchellh.ghostty.png` [CITED: github.com/pkgforge-dev/ghostty-appimage bin/bundle-appimage.sh]).
- The root desktop file has `TryExec=ghostty`, `Exec=ghostty --gtk-single-instance=true` (also in `[Desktop Action new-window]`), `Icon=com.mitchellh.ghostty`, `StartupWMClass=com.mitchellh.ghostty`, `X-KDE-Shortcuts=Ctrl+Alt+T`, and no `DBusActivatable` (upstream's `app.desktop.in` has `DBusActivatable=true` [CITED: ghostty dist/linux/app.desktop.in@v1.4.0]; the community build removed it).

Recommended flow inside `install_download` for a raw method that declares the desktop id:
1. After `_fetch_verified` (digest checked), `asset_path.chmod(0o755)`.
2. `ctx.runner(["env", f"--chdir={workdir}", f"TMPDIR={workdir}", str(asset_path), "--appimage-extract", f"{desktop_id}.desktop"])` and the same for `.png`. Using `ctx.runner` keeps tests offline (they stub the runner and pre-create `AppDir/...`), needs no shell, and reuses the curl call style (`download.py:472`). `env --chdir` is coreutils 8.28+ [ASSUMED available on Fedora, Debian, Arch, Bazzite].
3. Render with `desktop_entry.render(text, binary=<~/.local/bin/ghostty>, icon=<placed png path>)`.
4. Stage `.new` siblings and swap with the binary; a pre-existing `.desktop` or `.png` not recorded by any receipt is kept with a note (`cargo_distrobox._stage` precedent: "kept your existing ...", `installer/cargo_distrobox.py:154-157`).
5. `artifact_paths` adds two `leaf` artifacts when the key is set, so `receipts.record` records them only if this install created them (`installer/receipts.py:513-519`) and `uninstall` unlinks leaves and prunes empty parents (`installer/uninstall.py:579-584`).

Leaf paths (literal `~/.local/share`, the Alacritty precedent `registry.toml` artifacts): `~/.local/share/applications/com.mitchellh.ghostty.desktop`, `~/.local/share/icons/hicolor/256x256/apps/com.mitchellh.ghostty.png`.

The key: `artifact_paths` has only the method, so the leaf names must come from the registry. A new tarball key such as `desktop = "com.mitchellh.ghostty"` is the smallest deterministic option; SPEC's amendment lists only `raw` and `note`, so this third key needs owner confirmation (Assumptions A1). The alternative, a code-owned table keyed by member name, hides catalog data in code.

### Pattern 4: The `ghostty` container target

Clone `cmd_herdr_keys` (`scripts/container-e2e-verify.sh:2913-2938`): PID-named container `tools-installer-e2e-ghostty-$$`, `LANDING_DRIVER_MODULE=tests.e2e_ghostty_driver`, transcript under `.e2e-artifacts/container-ghostty/`, `trap landing_teardown EXIT` (removes the container, and the image only when this run pulled it, `:2746-2765`).

Differences from herdr-keys:
- `start_container` runs `ct run -d --init --name ... "$IMAGE" sleep infinity` with no extra arguments (`:220`). The ghostty target needs `--device /dev/fuse` (the `nested` target already passes it with `--security-opt label=disable`, `:1957`) and never `--privileged`; add an optional run-arguments variable or a dedicated start function.
- Extra stage: `dnf install -y zsh fuse fuse3` and `touch /run/ostree-booted` as root (`detect_immutable` reads `_OSTREE_MARKER = Path("/run/ostree-booted")`, `installer/platform.py:16,60-62`). `install_root_prereqs` deliberately installs no zsh (`:236-238` comment).
- Driver verbs (each prints a `TRACER_GHOSTTY_*` verdict): `install` (engine `install_tool`; assert method `tarball`, `~/.local/bin/ghostty` runs `--version`, the two leaves exist, the receipt lists the three paths), `sync` (`sync_terminal_shells(write=True, lookup=shutil.which)`), `regions` (both regions present; `ghostty +show-config` contains `command = <zsh> -l` and `+list-keybinds` contains `keybind = ctrl+shift+k=text:\x0c`; run these only after the file exists, Pitfall 3), `remove` (`uninstall_one`, then diff the home listing against the pre-install listing; must equal receipt paths plus the config file the installer created).
- Second pass without FUSE: `APPIMAGE_EXTRACT_AND_RUN=1` [CITED: uruntime docs/CONFIGURATION.md] forces extract-and-run in the same box, avoiding a second Homebrew bootstrap; a separate container without `--device /dev/fuse` is the stricter alternative (planner's choice; it doubles the bootstrap time).
- Record whether FUSE was used: uruntime prints `failed to utilize FUSE during startup!` on fallback (probe 1); a FUSE pass that fell back prints `_UNPROVEN`, not `_OK`.

Host tests with a stubbed `ct` (model: `tests/test_container_e2e_herdr_keys.py`, `_CT_STUB` at `:30-32`, `_function` extraction at `:51-54`): the verb is registered in `main`, the steps run in order, `ct run` carries `--device /dev/fuse` and never `--privileged`, `/run/ostree-booted` is written, teardown removes only its own container and a pulled image, the harness never prunes or resets, the driver refuses outside the container marker (`tests/e2e_landing_driver.py:838-850`), and the verdict functions are pure and covered.

### Anti-Patterns to Avoid
- **A second resolver per route:** the sync, the keys row, the revert and the strip must call the same `ghostty_config_path`, or the strip misses the file the sync wrote.
- **Kitty's shell-sync write style (`_write_if_changed`) for Ghostty:** it records no created marker, so an installer-created file would outlive the tool. Use `commit_region` with the shared marker (Alacritty pattern).
- **Running `ghostty +show-config` to probe before any config exists:** it creates the template file (Pitfall 3).
- **Scanning only the resolved file:** Ghostty merges every default file (Pitfall 2).
- **`subprocess.run(..., cwd=...)` for extraction outside `ctx.runner`:** unstubbable in tests (the conftest launch allowlist refuses it) and a second process seam.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Owned regions, placement, compare-before-commit | new marker code | `replace_owned_region`, `Placement.TOP`, `commit_region`, `strip_region` | Malformed-region refusal and created-file tracking already tested. |
| Drift, reconfigure, strip | Ghostty-specific status code | `terminal_keys_pending`, `apply_terminal_keys(skip_recorded=...)`, `strip_terminal_keys` | Routes already dispatch on `TERMINAL_KEYS`. |
| Reading the AppImage contents | squashfs or DwarFS parsing | `--appimage-extract PATTERN` of the verified asset | uruntime ships the extractor; works without FUSE (probe 1). |
| Desktop entry escaping | string formatting of `Exec=` | `desktop_entry.render` | Desktop Entry spec quoting and control-character refusal exist. |
| Multi-file swap with rollback | a new swap loop | `cargo_distrobox._swap` (move it to a shared module if a second caller appears, architecture rule 5) | Interrupt-safe rollback already reviewed. |
| Pin bumps | a Ghostty bump script | `make verify-registry ARGS="--write"` | Handles `{ver}` GitHub release URLs and digests. |

## Runtime State Inventory

Not a rename or migration phase; omitted.

## Common Pitfalls

### Pitfall 1: Legacy-file override on Linux
**What goes wrong:** a user binding or `command` in `~/.config/ghostty/config` is silently overridden when the installer writes `config.ghostty`.
**Why:** Ghostty loads the legacy file first, then `config.ghostty` (Config.zig v1.4.0:4245-4262); probe 2 showed `keybind = ctrl+shift+k=reset` in the legacy file replaced by our line.
**How to avoid:** scan every default file Ghostty loads; report `ghostty: partial: you already bind ctrl+shift+k` and skip that line.
**Warning sign:** a golden that only seeds the target file.

### Pitfall 2: macOS scan scope
**What goes wrong:** checking only App Support misses a user binding in the XDG files, which load first; checking only the resolved file misses App Support bindings that load after.
**How to avoid:** D-12's four-file scan via `ghostty_default_files("macos", ...)`; tests seed each file in turn.

### Pitfall 3: Ghostty writes a template config
**What goes wrong:** any config-loading CLI action on an empty HOME creates `config.ghostty` (2,011 bytes of comments), which then reads as a user file (non-empty, no created marker) and survives uninstall.
**How to avoid:** never run `+show-config`, `+list-keybinds` or `+validate-config` in tests or the driver before the installer wrote the file; `--version` is safe (probe 2: no `~/.config` after it). No production code path should run those actions.

### Pitfall 4: uruntime residue in `/tmp` without FUSE
**What goes wrong:** the install smoke `--version` on a no-FUSE host extracts about 145 MB into `/tmp/appimage_extracted_*`; after the reuse delay the directory goes but a `.lock` file and a dangling symlink stay (probes 1 and 2), and the 5 s smoke timeout can cut a slow extraction (a timeout counts as "ran", `installer/executors.py:94-95`).
**How to avoid:** run the smoke and the extraction with `TMPDIR` set to the install workdir that `install_download` already deletes in `finally` (`installer/download.py:414-435`); this needs an `env`/`tmpdir` argument on `smoke_binary` or `_replace_raw` (`installer/executors.py:86-108`).
**Warning sign:** the no-FUSE container pass listing `appimage_extracted_*` after uninstall.

### Pitfall 5: The status probe on a no-FUSE host
**What goes wrong:** every refresh pass runs `ghostty --version` (5 s timeout, `installer/versions.py:284`); without FUSE each run extracts again.
**How to avoid:** none needed for Bazzite (FUSE present: host has `fuse-2.9.9-26.fc45`, `fuse3-3.18.3-1.fc45`, `/dev/fuse`, verified this session). Record as a known limit; the deferred 5 s question stays open for no-FUSE hosts.

### Pitfall 6: Rebuild tags `vX.Y.Z+N`
**What goes wrong:** pkgforge-dev publishes fix rebuilds as `v1.2.0+1` with the same asset names. The single `{ver}` template cannot express the path `v1.4.0+1/Ghostty-1.4.0-...`, and `is_outdated("1.4.0", "v1.4.0+1")` is False because build metadata is discarded (`installer/versions.py:228-239`), so the bump bot never proposes the rebuild.
**How to avoid:** accept (the original release stays downloadable and digest-pinned) and note it in `# Verified`; a later rebuild that matters is a manual edit.

### Pitfall 7: `lookup("ghostty")` before `~/.local/bin` is on PATH
**What goes wrong:** the post-run sync gates on `which_with_brew("ghostty")`, which checks PATH and brew prefixes only (`installer/postinstall.py:180-200`); a session without `~/.local/bin` on PATH skips the shell region until the next run. Same limit as the wezterm AppImage today.
**How to avoid:** accept (consistent with wezterm) or also probe `locations.bin_dir(None) / "ghostty"`; planner's call.

### Pitfall 8: `X-KDE-Shortcuts=Ctrl+Alt+T`
**What goes wrong:** Konsole's desktop file on KDE claims the same global shortcut; a second claimant may steal or conflict with it [ASSUMED].
**How to avoid:** drop the key in the rendered entry (Assumptions A4).

### Pitfall 9: Order of the two `TOP` regions
**What goes wrong:** both regions use `TOP`, so their order depends on which writer ran first; a golden that assumes another route's order fails.
**How to avoid:** pin the install-route order (keys by post_install, then the shell region above it by the sync) and assert idempotence of a re-run, which replaces regions in place (`installer/terminal_regions.py:226-227`).

## Code Examples

Engine note (D-05), smallest change in `_perform` (`installer/engine.py:148-150`):
```python
if method.kind in download.DOWNLOAD_KINDS:
    reason = download.install_download(method, ctx)   # may also return menu-entry notes
    note = method.params.get("note")
    return reason is None, reason, ((note,) if isinstance(note, str) else ())
```
Notes reach `postinstall_warning` (`installer/engine.py:353-357`) and print as `⚠ ghostty postinstall warning: ...` in the CLI (`installer/render.py:494-497`) and after the row in the TUI (`installer/catalog_tui.py:711-712`). The wording "postinstall warning" frames the community label as a warning; acceptable under D-05, flagged as discretion.

Registry entry skeleton (values from D-01..D-04; the desktop key name is a proposal):
```toml
[[tool]]
id = "ghostty"
name = "Ghostty"
category = "terminal"
cmd = "ghostty"
priority = "P3"
audience = "human"
tier = "user"
verified = 2026-11-20
desc = "Fast, native GPU terminal emulator; Linux and Bazzite get a community build AppImage"
owner_probes = ["pacman"]
config_paths = ["~/.config/ghostty", "~/Library/Application Support/com.mitchellh.ghostty"]
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "pacman"
package = "ghostty"
[[tool.method]]
kind = "tarball"
os = ["debian", "fedora"]
arch = ["amd64"]
url = "https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v{ver}/Ghostty-{ver}-x86_64.AppImage"
version = "1.4.0"
sha256 = "50ad4f8b54a01e7d41426e7d12ffae9c88aa1c516ac140755e2bca596e1d2ae6"
member = "ghostty"
raw = true
desktop = "com.mitchellh.ghostty"
note = "community build (pkgforge-dev/ghostty-appimage), not an official Ghostty release"
[[tool.method]]
kind = "tarball"
os = ["debian", "fedora"]
arch = ["arm64"]
url = "https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v{ver}/Ghostty-{ver}-aarch64.AppImage"
version = "1.4.0"
sha256 = "932e21c671c215e6140633027acb4e8705cef3377d335202211c32d88b5bf506"
member = "ghostty"
raw = true
desktop = "com.mitchellh.ghostty"
note = "community build (pkgforge-dev/ghostty-appimage), not an official Ghostty release"
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "ghostty"
app = "Ghostty.app"
min_os_version = "13"
```
Cask facts for `# Verified` [VERIFIED: formulae.brew.sh/api/cask/ghostty.json, 2026-11-20]: version 1.4.0; artifacts `app` (target `/Applications/Ghostty.app`), manpages and shell completions into `$HOMEBREW_PREFIX`, no `binary` stanza; `depends_on` `{'macos': {'>=': ['13']}}`; `auto_updates` true; zap trashes `~/.config/ghostty` and `~/Library/Application Support/com.mitchellh.ghostty`. Arch [VERIFIED: archlinux.org/packages/extra/x86_64/ghostty/json]: `1.4.0 1 x86_64`.

## State of the Art

| Old | Current | When | Impact |
|-----|---------|------|--------|
| Ghostty config file `config` | `config.ghostty`, legacy still loaded first | Ghostty 1.3.0 (`file_load.zig` comments "Ghostty <1.3.0") | Resolver must handle both names. |
| Key names like `zero`, `plus` | W3C key codes; 1.1.x names kept for compatibility | Ghostty 1.2 (`Binding.zig` `backwards_compatible_keys`) | Normalize `key_k` to `k`. |
| Chained actions, key tables | available | Ghostty 1.3.0 | Skip `chain=` and `table/` lines in the scan. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A third tarball key (proposed `desktop = "com.mitchellh.ghostty"`) is acceptable although SPEC lists only `raw` and `note`. | Pattern 3 | Needs owner confirmation; the alternative is a code-owned table. |
| A2 | `env --chdir=DIR` (coreutils 8.28+) exists on every supported Linux host. | Pattern 3 | Extraction fails; fall back to a small `subprocess` seam with `cwd`. |
| A3 | Skipping the `command` write when a user `command` sits in an earlier-loaded file is the right refinement of provisional D-08. | Reconciliation R12 | Either the user's command is overridden (if we write) or zsh is not set (if we skip); owner decides. |
| A4 | `X-KDE-Shortcuts=Ctrl+Alt+T` in a user desktop entry can conflict with Konsole's Ctrl+Alt+T on KDE Plasma. | Pitfall 8 | If harmless, dropping it changes nothing; if harmful and kept, the user's Konsole shortcut may move. |
| A5 | `fedora:latest` is Fedora 44 or newer today. | Reconciliation R8 | Only affects the Bazzite-likeness claim. |
| A6 | Rootless podman with `--device /dev/fuse` lets the tester mount the AppImage with FUSE. | Pattern 4 | The FUSE pass falls back to extraction and reads `_UNPROVEN`; real Bazzite UAT covers it. |
| A7 | Case-folding keys and treating `key_k` as `k` in conflict detection matches Ghostty's matching closely enough. | Pattern 2 | Over-reporting `partial` (safe direction). |
| A8 | `ghostty +show-config` and `+list-keybinds` run headless inside the container as the tester (probe 2 ran them as root). | Pattern 4 | The driver step reads `_UNPROVEN`. |
| A9 | `uruntime`'s cleanup actor removes `/tmp/appimage_extracted_*` after the reuse delay on a normal host (probe 2 saw only the lock and symlink left after 8 s in a container). | Pitfall 4 | More residue in `/tmp` on no-FUSE hosts. |

## Open Questions

1. **Desktop-id key name and scope (A1).** Recommendation: `desktop` on `tarball` only; confirm with the owner before the plan locks it.
2. **Keys region placement.** Recommendation: `Placement.TOP` (kitty precedent; user lines win) with a refusal on a user `keybind = clear`. `END` would survive a user's `keybind = clear` but contradicts "user lines win". Discretion; no CONTEXT decision.
3. **Second container pass.** `APPIMAGE_EXTRACT_AND_RUN=1` in the same box (fast) versus a second box without `/dev/fuse` (faithful, slower). Recommendation: same box plus env var; D-18 says "a second pass without FUSE", so state the substitution in the plan.
4. **Readback after write.** A `ghostty +list-keybinds` readback (like WezTerm's `show-keys`) would prove the keys at install time but costs an AppImage launch per status pass and risks Pitfall 3. Recommendation: no production readback; the container target reads back once.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | container target, probes | yes | 6.1.3 | docker via `detect-container-runtime.sh` |
| `registry.fedoraproject.org/fedora:44` image | probes | yes (local) | 44 | pull |
| uv | tests | yes | 0.11.28 (project Python 3.12.12) | none |
| gh (authenticated) | asset digests | yes | 2.101.0 | GitHub API |
| FUSE on the host (Bazzite) | AppImage runtime | yes | fuse 2.9.9-26.fc45, fuse3 3.18.3-1.fc45, `/dev/fuse` | extract-and-run |
| macOS host | cask install, real-Mac checks | no | - | UAT deferred to the owner's Mac (D-15) |

Missing with no fallback: none for planning. Real-Mac verification stays manual.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-xdist and coverage (`pyproject.toml` `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml`; isolation fixtures in `tests/conftest.py` |
| Quick run command | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_registry.py tests/test_model.py tests/test_download.py tests/test_desktop_entry.py tests/test_tool_onboarding_skill.py tests/test_container_e2e_ghostty.py --no-cov -q` |
| Full suite command | `make validate` then `make test` (once per plan) |
| Container proof | `scripts/container-e2e-verify.sh ghostty` (orchestrator only, never on the host) |

### Phase Requirements to Test Map
| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|-------------|
| NTERM-01 R1 | Entry loads; Arch amd64/arm64 -> pacman; debian and Bazzite amd64 -> x86_64 tarball; arm64 -> aarch64; macOS -> cask; URLs equal asset names; lowercase 64-hex pins; "community build" in desc and note | unit | `uv run pytest tests/test_registry.py -k ghostty --no-cov -q` | partial (file exists; new tests) |
| NTERM-01 R1 | Loader refuses raw+strip, raw+archive, bad note, bad desktop id | unit | `uv run pytest tests/test_model.py -k "raw or note or desktop" --no-cov -q` | partial |
| NTERM-01 R1 | Digest mismatch raises `ChecksumMismatch` and places nothing (no binary, no menu files) | unit | `uv run pytest tests/test_download.py -k ghostty --no-cov -q` | partial |
| NTERM-01 R1/D-07 | Extraction argv, render, leaves recorded only when created, kept user `.desktop` | unit | `uv run pytest tests/test_download.py tests/test_desktop_entry.py --no-cov -q` | partial |
| NTERM-01 R2 | Shell region at the top; user `command` (same file and legacy file) gives `partial`; `config-file` gives `partial`; revert strips | unit | `uv run pytest tests/test_terminal_shell.py -k ghostty --no-cov -q` | partial |
| NTERM-01 R3 | Linux and macOS goldens through `run_post_install`; `macos-option-as-alt` absent; four macOS resolver cases plus empty files; conflict normalization; `keybind = clear` refusal | unit | `uv run pytest tests/test_terminal_keys.py -k ghostty --no-cov -q` | partial |
| NTERM-01 R4 | Pending without record; reconfigure restores; second reconfigure no-op | unit | same file, `-k "ghostty and drift"` | partial |
| NTERM-01 R5 | `_after_removal` strips both regions and drops a created whitespace-only file | unit | `uv run pytest tests/test_terminal_keys.py -k "ghostty and strip" --no-cov -q` | partial |
| NTERM-01 R5 | Container install, regions, uninstall, residue diff (FUSE and no-FUSE) | e2e (container) | `scripts/container-e2e-verify.sh ghostty` | no (Wave 0) |
| NTERM-01 R5 | Harness wiring, own-container-only teardown, no prune, `--device /dev/fuse` without `--privileged` | unit (stubbed ct) | `uv run pytest tests/test_container_e2e_ghostty.py --no-cov -q` | no (Wave 0) |
| Skill table | `ghostty` row present; clear cell `written` | unit | `uv run pytest tests/test_tool_onboarding_skill.py --no-cov -q` | yes |
| Real Mac | `~/Applications/Ghostty.app/Contents/MacOS/ghostty +show-config` and `+list-keybinds` show the `super+k` line and no `macos-option-as-alt` | manual UAT | owner's Mac | n/a |

### Sampling Rate
- Per task commit: the quick command limited to the files the task touched.
- Per plan: `make validate`, then `make test`.
- Phase gate: full suite green, the `ghostty` container target PASS, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/e2e_ghostty_driver.py`: in-container verbs and pure verdict functions.
- [ ] `tests/test_container_e2e_ghostty.py`: host tests with stubbed `ct`.
- [ ] Fixture text for the AppImage desktop file (copy the 694-byte root file from probe 1) for render and extraction tests.
- No framework install needed.

## Security Domain

`security_enforcement` is true, ASVS level 1 (`.planning/config.json`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | - |
| V3 Session Management | no | - |
| V4 Access Control | no (user-scope writes only, zero sudo) | - |
| V5 Input Validation | yes | loader validation of `note` and the desktop id; `desktop_entry.render` refuses relative paths and control characters; `_safe_executable` on the zsh path (`installer/terminal_shell.py:160-167`) |
| V6 Cryptography | yes (integrity) | sha256 pin compared before placement (`installer/download.py:486-497`) |
| V10 Malicious code / V14 Configuration | yes | registry cannot supply commands; extraction executes only the digest-verified asset |

### Known Threat Patterns
| Pattern | STRIDE | Mitigation |
|---------|--------|-----------|
| Tampered or swapped community AppImage | Tampering | Pinned sha256 per arch; mismatch places nothing; bumps only through `verify-registry`. |
| Executing an unverified binary during extraction | Elevation | Extract only after `_fetch_verified`; run under `TMPDIR=workdir`, no shell. |
| Desktop entry injection (`Exec=` with crafted path) | Tampering | `render` checks absolute path, control characters, quoting per spec. |
| Path traversal from extracted names | Tampering | Read only the two fixed names under `workdir/AppDir/`; refuse symlinks out of the workdir (`staged_member` style check, `installer/executors.py:61-70`). |
| Overwriting a user's config, desktop file or binding | Tampering | Owned regions only; `partial:` on conflicts; keep pre-existing unrecorded files; created-file proof before deletion. |
| Shell injection via zsh path in `command` | Tampering | `shlex.join` plus `_safe_executable`; Ghostty runs it through `/bin/sh -c`. |
| Rich markup in a registry `note` | Spoofing (display) | Validate the note (no `[`), or escape at render. |

## Sources

### Primary (HIGH)
- Repository code read this session: `installer/terminal_keys.py`, `installer/terminal_regions.py`, `installer/terminal_shell.py`, `installer/model.py`, `installer/download.py`, `installer/engine.py`, `installer/render.py`, `installer/desktop_entry.py`, `installer/cargo_distrobox.py`, `installer/receipts.py`, `installer/uninstall.py`, `installer/app.py`, `installer/post_install.py`, `installer/version_status.py`, `installer/verify_registry.py`, `installer/versions.py`, `installer/executors.py`, `installer/platform.py`, `installer/compose.py`, `installer/postinstall.py`, `scripts/container-e2e-verify.sh`, `scripts/e2e-residue-allowlist.txt`, the tests named above, `.claude/skills/tool-onboarding/SKILL.md`.
- Ghostty v1.4.0 sources via `gh api repos/ghostty-org/ghostty/contents/...?ref=v1.4.0` (2026-11-20): `src/config/Config.zig`, `src/config/file_load.zig`, `src/config/config-template`, `src/input/Binding.zig`, `src/input/key_mods.zig`, `src/input/key.zig`, `src/termio/shell_integration.zig`, `src/cli/args.zig`, `src/cli/show_config.zig`, `dist/linux/app.desktop.in`, `dist/linux/dbus.service.in`.
- `gh api repos/pkgforge-dev/ghostty-appimage/releases/tags/v1.4.0`, `/releases`, `/contents/bin/bundle-appimage.sh` (2026-11-20).
- Container probe 1 and probe 2 (disposable `registry.fedoraproject.org/fedora:44`, `podman run --rm`, no FUSE device, removed; 2026-11-20).

### Secondary (MEDIUM)
- https://formulae.brew.sh/api/cask/ghostty.json (2026-11-20).
- https://archlinux.org/packages/extra/x86_64/ghostty/json/ (2026-11-20).
- https://github.com/VHSgunzo/uruntime README.md, docs/USAGE.md, docs/CONFIGURATION.md (fetched 2026-11-20; the AppImage embeds uruntime v0.8.1).

### Tertiary (LOW)
- KDE `X-KDE-Shortcuts` conflict behavior (training knowledge; A4).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no new libraries; every module read).
- Architecture: HIGH (the mechanism is generic; changes are data plus three localized code changes).
- Pitfalls: HIGH for 1, 3, 4, 6 (probed or read from source); MEDIUM for 5, 7, 8.

**Research date:** 2026-11-20
**Valid until:** 2026-12-20 (asset pins and cask facts move with upstream releases; re-run `gh api` before execution if a Ghostty 1.4.1 ships).
