# Phase 30: Onboard Ghostty - Context

**Gathered:** 2026-11-19 (assumptions mode, after 30-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

Ghostty is a catalog entry (macOS cask, pinned community AppImage on Linux and Bazzite, pacman on Arch) with a Linux zsh sync, a keys row in the shared mechanism, an application-menu entry for the AppImage, drift and reconfigure behavior, and a clean uninstall proved in a container. Phases 27, 28 and 29 must execute first: `installer/terminal_keys.py`, `installer/terminal_regions.py` and `TERMINAL_KEYS` do not exist yet.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `30-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `30-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the Ghostty registry entry, its postinstall row, shell-sync branch and keys row, removal, tests and container checks; the macOS app location. *Amended 2026-11-19 (30 D-02, D-05, D-07, D-08, D-13):* `raw` as an allowed key on `tarball`, an optional per-method `note`, the AppImage's menu entry and icon, a placement option for the owned-region helper, and `platform_os` in the row's `config_path`.
**Out of scope (from SPEC.md):** iTerm2 and the Herdr app; new method kinds; theme and font customization; real-Mac verification.

</spec_lock>

<decisions>
## Implementation Decisions

### Registry entry
- **D-01: One `[[tool]]`:** `id = "ghostty"`, `name = "Ghostty"`, `category = "terminal"`, `cmd = "ghostty"`, `tier = "user"`, `audience = "human"`, `priority = "P3"` (as wezterm and kitty), `post_install = ["apply_terminal_tuning"]`, `config_paths = ["~/.config/ghostty", "~/Library/Application Support/com.mitchellh.ghostty"]`. `"ghostty"` joins `_POST_15_3_HUMAN_TOOLS` (`tests/test_registry.py:276-285`). Patterns: `installer/registry.toml:3103-3131,3152-3164`; `~/Library` config paths exist for tealdeer and pnpm (`:1327,2239`).
- **D-02: Linux and Bazzite use two `tarball` methods, one per arch, `raw = true`, `member = "ghostty"`, `os = ["debian","fedora"]`, `version = "1.4.0"`,** URL `https://github.com/pkgforge-dev/ghostty-appimage/releases/download/v{ver}/Ghostty-{ver}-x86_64.AppImage` (and `aarch64`); the `v` is literal in the path (draw.io's macOS `app` method does the same, `registry.toml:3336-3338`). Pins: x86_64 `50ad4f8b54a01e7d41426e7d12ffae9c88aa1c516ac140755e2bca596e1d2ae6` (equals the GitHub digest and was re-hashed after a container download), aarch64 `932e21c671c215e6140633027acb4e8705cef3377d335202211c32d88b5bf506` (GitHub digest). `raw` becomes an allowed key on `tarball` (`installer/model.py:637-640`; the install path checks `raw` without looking at the kind, `installer/download.py:408,418,460`; shared with phase 32's Bruno) and the loader refuses `raw` together with `strip` or `archive`. Reason: `github_release` takes no `version` or `sha256` (`model.py:69-82`; it installs the latest tag checked against the API digest, `download.py:116-140`), while `tarball` pins (`model.py:83-96,646-666`); `verify-registry` already handles tarball pins (`verify_registry.py:294-341,536-554,1088-1091,1188-1198`) so phase 33's bot covers them. jev pin_in_catalog_raw_key 0.85 (TypeSafe).
- **D-03: macOS is `kind = "cask"`, `cask = "ghostty"`, `app = "Ghostty.app"`, `min_os_version = "13"`,** installed with `--appdir` into `~/Applications` (`executors.py:700-703`). The cask has no `binary` stanza and the `cask` kind has no `cli` key (`model.py:105`), so no CLI link is promised; the CLI stays at `~/Applications/Ghostty.app/Contents/MacOS/ghostty`; the `# Verified` comment says why (27 D-10, 29 D-05). **Own reasoning** (jev accept_and_document low 0.53; first rung low 0.47). Ledger.
- **D-04: Arch is `kind = "pacman"`, `package = "ghostty"`** (`extra/ghostty 1.4.0 x86_64` read live); the tarballs carry `os = ["debian","fedora"]` only, so Arch never gets the community build; pacman is a hand-off, never a real install here.
- **D-05: "Community build" appears in `desc` and in a new optional per-method `note` key on download methods,** surfaced through `_perform`'s existing notes channel (`installer/engine.py:138-157,353`, rendered by `installer/render.py:485-494`) and repeated in `# Verified`; the label applies only to the AppImage methods. jev method_note_and_desc 0.98 (TypeSafe).
- **D-06: No `smoke_argv`:** the default `--version` works on the AppImage with and without FUSE (container probe: without `/dev/fuse` and fusermount the runtime prints "failed to utilize FUSE ... Trying to extract and run", then "Ghostty 1.4.0", exit 0; `executors.py:51-58`). Bazzite has `fuse-2.9.9`, `fuse3` and `fusermount`, so no reboot.
- **D-07: The install adds an application-menu entry and icon:** extract the AppImage's own `.desktop` and icon after the digest check, render with `desktop_entry.render` pointing at `~/.local/bin/ghostty`, record them as receipt leaves, remove them on uninstall. Bazzite users launch apps from the KDE menu; the other two app-image entries (wezterm, draw.io) write none (`desktop_entry.py` is used only by `cargo_distrobox`, `cargo_distrobox.py:20`), so this is new install code. jev add_menu_entry 0.78 (Laya).

### Shell sync (Linux)
- **D-08: A Linux-only `_sync_ghostty`,** gated on `lookup("ghostty")`, writes an owned region `ghostty` holding `command = <shlex.join((zsh, "-l"))>` **at the top of the file** (a placement option on `_replace_owned_region`, shared with phase 29 D-01 for kitty), so a user `command` further down wins on its own; it also detects a user `command` outside the regions and reports `ghostty: partial: you already set command`. Ghostty is last-wins per key; `command` with arguments runs through `/bin/sh -c`, and shell integration still detects zsh from arg0's basename (`src/termio/shell_integration.zig:137-165`). Ghostty joins `_revert_terminal_shells` and `_TERMINAL_ROWS` (`"ghostty": ("ghostty", "Ghostty")`, `terminal_shell.py:854-890`; `version_status.py:734-740`). **Own reasoning** (jev top_with_report low 0.59; first rung low 0.58). Ledger.
- **D-09: The config file is Ghostty's preferred XDG path:** `$XDG_CONFIG_HOME/ghostty/config.ghostty` if it exists and is non-empty, else the legacy `config` if it exists and is non-empty, else `config.ghostty`; shell and keys regions share it. Both names load (legacy first) and Ghostty warns when both exist, so writing `config.ghostty` beside a user's legacy `config` would override them.
- **D-10: A user `config-file =` include is not followed:** write anyway and add a `partial:` line saying included files were not checked (included files load after the file that names them, so an included `command` wins without any action; Alacritty's refusal would mean such users never get zsh). jev first rung none_of_these 0.71 contradicted the evidence; second opinion write_and_note low 0.53. **jev overridden / Own reasoning.** Ledger.

### Keys row
- **D-11: The row writes region `ghostty-keys`** with `sibling_regions = ("ghostty",)`: Linux `keybind = ctrl+shift+k=text:\x0c`; macOS `keybind = super+k=text:\x0c`; no Option or Alt lines (the macOS defaults `esc:b` and `esc:f` fire whatever `macos-option-as-alt` says, and the owner decided no Alt rows on Linux); `macos-option-as-alt` is never written. Ghostty's default `cmd+k` is the native `clear_screen`, which does not send Ctrl+L, so the macOS line is needed under KEYS-03 (research `STACK.md:25,74` "macOS: write nothing" is overridden, as 27 D-14 did for WezTerm); SPEC R3's "nothing written where the vendor default already meets a rule" still holds for word navigation and same-directory. jev first rung none_of_these 0.81 contradicted the evidence; second opinion rebind_to_ctrl_l 0.95. **jev overridden.**
- **D-12: Conflict detection normalizes the chord** (modifier order; `cmd`/`command` to `super`, `opt`/`option` to `alt`, `control` to `ctrl`), drops the prefixes `all:`, `global:`, `unconsumed:` and `performable:`, ignores key tables and sequences, and reports `ghostty: partial: you already bind ctrl+shift+k`; on macOS the scan covers all four loaded files. jev normalize_then_compare 0.96 (TypeSafe).
- **D-13: The macOS file mirrors Ghostty's `preferredDefaultFilePath`:** App Support `config.ghostty`, else legacy `config`, if one exists and is non-empty; otherwise the preferred XDG file if it exists; otherwise App Support `config.ghostty` (`~/Library/Application Support/com.mitchellh.ghostty/`). A pure resolver `(platform_os, home, environ)` lets Linux CI test every case, including empty files. It needs phase 28's row field `config_path` to take `platform_os` *(amended 2026-11-19, 30 D-13, in 28-CONTEXT D-03)*. jev terminals_preferred_file 0.97 (TypeSafe).
- **D-14: `same_directory` is `vendor`** with a dated note: `window-`, `tab-` and `split-inherit-working-directory` default to true (Ghostty `Config.zig` v1.4.0 :2086-2099) and need shell integration, which works with our `command`; a user's `shell-integration = none` is the user's choice.

### Tests, removal and the container proof
- **D-15: Byte goldens through the public routes in a scratch HOME** (28 D-10): Linux created-file bytes (shell plus keys regions), macOS created-file bytes (keys only), user content kept, a user `command` and a user `ctrl+shift+k` each giving `partial`, a regression assert that `macos-option-as-alt` appears in neither golden, the four macOS resolver cases, and drift: pending only without a record (28 D-06), reconfigure restores, a second reconfigure is a no-op. Registry tests: Arch amd64 and arm64 resolve to pacman; debian and Bazzite amd64 to the x86_64 tarball; arm64 to the aarch64 tarball; macOS to the cask; URLs equal the live asset names; sha256 values are lowercase 64-hex; the loader refuses `raw` with `strip`; a digest-mismatch fixture raises `ChecksumMismatch` and places nothing (`download.py:486-510`); the phase 27 closed-table row and phase 28 completeness test. The real-Mac check (`ghostty +show-config`, `+list-keybinds`) is a UAT line. jev byte_goldens_public_routes 0.96 (TypeSafe).
- **D-16: The receipt records `~/.local/bin/ghostty` (kind `file`) plus the menu entry and icon leaves;** `app._after_removal` calls `strip_terminal_keys` for the Ghostty row (strips `ghostty-keys`, the sibling `ghostty` region and the record) and deletes the config file and created directories only if the installer created them and they now hold only whitespace; `config_paths` are kept by default. Without the sibling strip the shell region would outlive the tool (`_revert_terminal_shells` runs only when zsh goes, `terminal_shell.py:917-921`).
- **D-17: The residue diff excludes the existing allowlist** (`scripts/e2e-residue-allowlist.txt`: `.cache`) and also asserts `/tmp` holds no installer leftovers: without FUSE the AppImage writes thumbnails under `~/.cache` and `/tmp/appimage_extracted_*`. **Own reasoning** (first rung installer_folders_only 0.92, weaker than the shared leftover check; second opinion low 0.54). Ledger.
- **D-18: A dedicated container target `ghostty`** modeled on `audit-landing` and `bun-lifecycle` (`scripts/container-e2e-verify.sh:95-130`): a Bazzite-like `fedora:44` with `/run/ostree-booted` (so `detect_immutable` reads true, `installer/platform.py:16,60`), `fuse fuse3`, `--device /dev/fuse`, never privileged; install through the engine, take file lists, run `ghostty --version`, check both regions, uninstall, diff against the receipt plus the allowlist; a second pass without FUSE; the container is removed on every exit. Arch's pacman is a hand-off, covered by resolve tests only. jev dedicated_target 0.72 (Laya).
- **D-19: Dependencies:** phases 27, 28 and 29 execute first (the skill table, `TERMINAL_KEYS` and the helpers do not exist yet); phase 29 adds rows to the same dict, table and `_TERMINAL_ROWS` (merge coupling); phase 31 extends the table.

### Claude's Discretion
- The install note's wording, the menu entry's category and name text, and helper names.

### Folded Todos
- Backlog 999.20 (this phase's source).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/30-onboard-ghostty/30-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/phases/28-shared-terminal-keys-mechanism/28-CONTEXT.md`, `.planning/phases/29-terminal-defaults-for-the-terminals-in-the-catalog/29-CONTEXT.md`, `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-CONTEXT.md`
- `.planning/research/STACK.md` (§1.4, §2.2; its macOS clear claim is overridden), `installer/terminal_shell.py`, `installer/model.py`, `installer/download.py`, `installer/engine.py`, `installer/desktop_entry.py`, `installer/executors.py`
- `scripts/container-e2e-verify.sh`, `scripts/e2e-residue-allowlist.txt`
- Ghostty v1.4.0 sources read by the analyzer (saved under the scratchpad `p30/src`, read-only): `src/config/Config.zig`, `file_load.zig`, `src/input/Binding.zig`, `src/termio/shell_integration.zig`
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Alacritty's shell-plan partial shape, `_replace_owned_region`, the wezterm and herdr registry entries, the download receipt machinery, `desktop_entry.render`, the container e2e harness.

### Established Patterns
- A user's own setting is kept and reported `<terminal>: partial: you already ...`; pins move together and are bumped by `verify-registry`.

### Integration Points
- `TERMINAL_KEYS`, `_TERMINAL_ROWS`, `_revert_terminal_shells`, `METHOD_PARAMS["tarball"]`, the engine's `notes` channel.
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in this commit): `github_release` has no pin fields, so the pins ride on `tarball` with `raw`; the macOS clear needs one keybind line; the AppImage needs a menu entry to be usable from the KDE menu.
</specifics>

<deferred>
## Deferred Ideas

- To confirm (UAT or planning): whether `TERMINFO` resolves `xterm-ghostty` inside an AppImage window (zsh line editing), under FUSE and extract-and-run; the exact flags of `ghostty +show-config` and `+list-keybinds`; whether Option+Left/Right `esc:b` works on a Spanish Mac layout; whether the 5 s status-probe timeout is enough for an AppImage extracting about 49 MB without FUSE.

### Reviewed Todos (not folded)
None other matched.
</deferred>
