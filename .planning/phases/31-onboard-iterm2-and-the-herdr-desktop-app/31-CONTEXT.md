# Phase 31: Onboard iTerm2 and the Herdr desktop app - Context

**Gathered:** 2026-11-19 (assumptions mode, after 31-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

iTerm2 is a macOS-only cask with an installer-owned default Dynamic Profile (word navigation by key-map rows, Cmd+K sending Ctrl+L, same-directory, requested colors) whose default status is restored on uninstall; the Herdr desktop app (`herdr-app`) is its own entry (Linux vendor script, Apple Silicon cask) whose single keys file gets installer-owned keys without disturbing the user's. Phases 27 to 30 must execute first: `terminal_keys.py`, `terminal_regions.py`, the phase 27 table and the Ghostty row do not exist yet.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked.** See `31-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `31-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the iTerm2 entry, Dynamic Profile generator, default-profile set and restore; the Herdr desktop app entry and its keys row; the JSON modes of the keys mechanism, goldens and container checks. *Amended 2026-11-19 (31 D-01, D-04, D-08, D-14, D-15):* two new ownership variants (whole file and per-key), `placement` inside the owned-region variant, key-map rows for word navigation, and one keys file for the app.
**Out of scope (from SPEC.md):** iTerm2 "Show Focus Cursor" and the agent-collaboration extension; changing the `herdr` multiplexer entry; the app's auto-update; real-Mac verification.

</spec_lock>

<decisions>
## Implementation Decisions

### JSON modes of the keys mechanism
- **D-01: The ownership union gets two new variants,** not one: `WholeFile(proof)` for the iTerm2 Dynamic Profile and a per-key variant (`OwnedKeys`, name open) for the herdr app's `keys.json`, because the app creates and owns that file (herdr-app `src/keys.rs:175-189`) and uninstall must "remove only the owned keys". The per-key variant adds and removes two-level key paths such as `("terminal","ctrl-shift-k")` through the formatting-preserving splice helpers of `installer/agent_settings.py` (`insert_key`/`remove_key`, `:290-333,486-510`); the record stores the owned paths and the values written; drift means an owned key still holds the recorded value but the current render differs (rewrite); a current value that differs from the recorded one is a user change (`partial: kept yours`); strip removes only owned keys still holding the recorded value. `_dump` writes Ctrl+L as `"send:\f"` where the vendor uses a `\u000c` style (`agent_settings.py:255-256`): the golden pins one of the two. **Own reasoning** (jev separate_per_key_mode low 0.69; first rung low 0.56; splice_existing_helpers low 0.79 as second opinion). Ledger.
- **D-02: `WholeFile` ownership proof is the created-record plus a fixed installer GUID inside the JSON.** The record is `$XDG_DATA_HOME/tools-installer/terminal-iterm2-created` (28 D-01 naming). Apply: a missing file is created (and the `DynamicProfiles` folder); a file with our GUID and the record whose bytes differ is rewritten (drift); a file with foreign content is refused with `iTerm2 keys not changed: ...`, never overwritten. Strip: delete the file when the GUID matches even if the bytes differ, otherwise refuse. Writes are atomic with compare-before-commit (`installer/atomic.py:36-80`, `FileSnapshot`). Golden bytes: `json.dumps(sort_keys=True, indent=2, ensure_ascii=False) + "\n"`. **Own reasoning** (jev record_and_guid low 0.49). Ledger.
- **D-03: What a deleted file means depends on the variant:** a deleted iTerm2 profile while the default-profile setting still names our GUID reads `≈ apply install tuning` (the default is broken, not a choice; iTerm2 falls back to its parent or default when the profile is missing); a herdr-app owned key gone after a recorded install is the user's choice (the app's escape hatch moves `keys.json` aside and restores defaults, `defaults/AGENTS.md:59-61`). This amends SPEC R5 and refines 28 D-06. jev per_mode 0.80 (TypeSafe).
- **D-04: `placement` moves into the `OwnedRegion` variant** (amending 29 D-11): a whole file has no position and a per-key edit is located by key path. `validate` stays per row: iTerm2 JSON parses and holds exactly one profile with our GUID; herdr-app JSON parses and every section is an object. **Own reasoning** (jev row_field_with_na low 0.56; first rung low 0.64). Ledger.

### iTerm2
- **D-05: The entry:** `id = "iterm2"`, `name = "iTerm2"`, `category = "terminal"`, `tier = "user"`, `cmd` default (iTerm2 has no command; presence comes from the `iTerm.app` bundle, `installer/status.py:201-210`), one `cask` method with `os = ["macos"]`, `cask = "iterm2"`, `app = "iTerm.app"`, `min_os_version = "13"` (cask 3.7.8 needs macOS 13, read live), `post_install = ["apply_terminal_tuning"]`; `iterm2` joins `MACOS_ONLY` (`tests/test_registry.py:797`). Uninstall is `brew uninstall --cask` with no zap (`installer/uninstall.py:113`); the cask's own `quit: com.googlecode.iterm2` closes iTerm2 first.
- **D-06: No `config_paths`:** preferences are a plist cached by the macOS preferences daemon, and `~/Library/Application Support/iTerm2` also holds the user's other dynamic profiles and scripts. Our one file is stripped by the keys row. jev none 0.97 (TypeSafe).
- **D-07: The profile file** is `~/Library/Application Support/iTerm2/DynamicProfiles/tools-installer.json` (name open), one profile with a fixed `Guid` and `Name` and no `"Rewritable"` key (the install note says changes made in the iTerm2 settings window do not stick). `"Custom Directory": "Recycle"` for new tabs, windows and panes (allowed values Yes/No/Recycle/Advanced, `ITAddressBookMgr.h:54`; the factory default is `"No"`, so `same_directory = writes`). Cmd+K is the keyboard-map entry `"0x6b-0x100000"` to `{"Action": 11, "Text": "0x0c"}` (`KEY_ACTION_HEX_CODE = 11`, `iTermKeyBindingAction.h:51`; a profile mapping applies before the Clear Buffer menu item, `iTermApplication.m:562-583`). Reload is live, but one malformed file anywhere in the folder blocks every reload, so the check message says so. These facts come from iTerm2's master source, not the 3.7.8 tag: confirmed in the Mac UAT. jev send_ctrl_l low 0.69 (TypeSafe), 0.57 (Laya). **Own reasoning** (KEYS-03). Ledger.
- **D-08: Option stays Normal; word navigation is two keyboard-map rows:** Option+Left `0xf702-0x280000` to `{"Action": 10, "Text": "b"}` and Option+Right `0xf703-0x280000` to `{"Action": 10, "Text": "f"}` (iTerm2's own "Terminal.app Compatibility" preset rows, `PresetKeyMappings.plist`; arrows send `CSI 1;%dD` whatever the Option setting, `VT100Output.m:58-61,246-262`). Setting both Option keys to Esc+ is iTerm2's form of the global Option-as-Alt switch, which 27 D-11 forbids (it breaks Spanish `@ | # \`) and which alone would not produce `ESC b`/`ESC f`. This **amends NTERM-02 / SPEC R1 / ROADMAP criterion 1** ("sets Option as Esc+"); **flagged: needs confirmation**. jev map_rows_only 0.97 (TypeSafe).
- **D-09: The profile inherits from the previous default:** `Dynamic Profile Parent GUID` is the recorded previous default GUID (left out when none), and the parent's keyboard map is merged in (read with `defaults export` through the injected runner) because a keyboard map in the profile replaces the parent's whole map; a clash is reported `partial: kept yours`. Without this the user's font, size and key mappings vanish when our profile becomes the default. **Own reasoning** (jev parent_plus_merged_keys low 0.63; first rung low 0.50). Ledger.
- **D-10: Colors:** the requested scheme is "dark background with dark-green text, a Matrix console look" (todo `.planning/todos/completed/2026-10-15-add-iterm2-macos-only-entry-after-tool-onboarding-refactor.md`, item 3). A dynamic profile cannot name a color preset, so five explicit color entries (Red/Green/Blue/Alpha Component, Color Space sRGB) set Foreground, Background, Bold, Cursor and Selection, plus `"Use Separate Colors for Light and Dark Mode": false` (the factory default is `true`, which makes the plain keys ignored; `DefaultBookmark.plist`); the 16 ANSI colors stay untouched. The owner's exact RGB values were never recorded: the generator uses a documented dark-green palette and the Mac UAT confirms it. **Own reasoning** (jev core_five low 0.36; TypeSafe full_palette low 0.55). Ledger.
- **D-11: Making the profile the default is an optional hook on the iTerm2 keys row,** not a new post-install action: it reads and writes the `Default Bookmark Guid` preference (`ITAddressBookMgr.h:38`) in `com.googlecode.iterm2` through `defaults read`, `defaults write` and `defaults delete`, with the command runner injected (as `post_install.use_git_runner`, `installer/post_install.py:142-153`) and pure functions turning the before state into commands. The previous value, or "none set", is recorded in `$XDG_DATA_HOME/tools-installer/terminal-iterm2-default`. Restore runs only when the current value is still our GUID (otherwise the user's later choice is kept, `partial: kept yours`); "none set" is restored with `defaults delete`; the step is skipped with a `partial` note when `LoadPrefsFromCustomFolder` is on (`SUMMARY.md:109,143`). Order: restore the preference, then delete the file; restore runs after the cask removal (`installer/app.py:611-643`), when brew has already quit iTerm2. jev first rung none_of_these 0.99 contradicted the evidence; second opinion separate_action low 0.65. **jev overridden / Own reasoning.** Ledger.

### Herdr desktop app
- **D-12: The id is `herdr-app`** (category `terminal`), matching the cask token, the command and the config folder; every herdr check in the installer is an exact match, so the two ids cannot collide (`installer/receipts.py:292`, `installer/app.py:625`, `installer/agent_settings.py:620,695,721`, `installer/version_status.py:739`). Linux is a `script` method: `os = ["debian","fedora","arch"]`, `url = "https://releases.herdr.dev/app/install.sh"`, `shell = "sh"`, `bin_dir = "~/.local/bin"`, `paths` = `~/.local/share/herdr-app/`, `~/.local/bin/herdr-app`, `~/.local/share/applications/herdr-app.desktop`, `~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg`; no `writable_prefix`, no sudo, no `remove` or `update` (re-running the script updates the app, and the app self-updates); the receipt claims only paths this run created (`installer/receipts.py:500-519`); Linux arm64 is published. The script also installs `herdr-core` and `hc` through a nested unchecked `curl | sh` when none exists (`install.sh:139-143`): those stay out of `paths` per SPEC R3 and remain after removal (recorded in `# Verified`); it honors `XDG_DATA_HOME`, so a custom value leaves the receipt empty and fails closed. macOS is `cask = "herdr-app"`, `os = ["macos"]`, `arch = ["arm64"]`, `app = "Herdr.app"`; brew links `herdr-app` into `$HOMEBREW_PREFIX/bin` (the 27 D-10 gap, recorded); Intel macOS resolves no method (`installer/resolve.py:50-55`, `installer/catalog_tui.py:397`) and a new test allowlist `NO_MACOS_INTEL` is needed (`MACOS_ARM64_ONLY` means macOS-only). Flagged for the owner: the vendor `install.sh` on macOS puts `Herdr.app` in `~/Applications` and links `~/.local/bin/herdr-app` (`install.sh:110-136`), which meets the 27 macOS-app rule better than the cask; the SPEC locks the cask. jev herdr_app 0.98 (TypeSafe).
- **D-13: `config_paths = ["~/.config/herdr-app"]`,** with no overlap with herdr's `~/.config/herdr` (`installer/model.py:461-474`); owned keys are stripped before any config deletion, as for herdr (`installer/app.py:625-629`). jev declare 0.80 (TypeSafe).
- **D-14: The keys file is `~/.config/herdr-app/keys.json` on every OS** (the folder resolves as `$HERDR_APP_HOME`, else `$XDG_CONFIG_HOME/herdr-app`, else `~/.config/herdr-app`, `src/mods.rs:60-65`); `keys.macos.json` is only the default compiled into macOS builds (`src/keys.rs:1,30-33,111-113`). This **amends SPEC R4** ("keys.json / keys.macos.json"). Rows write to the `terminal` section: Linux `"ctrl-shift-k": "send:\f"`, macOS `"cmd-k": "send:\f"`; the `terminal` section beats `global` (`defaults/AGENTS.md:523-525`), so the vendor `global` `ctrl-shift-k` picker binding stays active outside terminals; the install note names it as displaced in terminals (the picker stays in the palette, Ctrl+Shift+P). macOS Option word navigation is `vendor` (`keys.macos.json` already sends `ESC b`/`ESC f`); Linux gets no Alt rows (owner rule); `same_directory = vendor` for tabs and splits (`README.md:45`, `defaults/AGENTS.md:114-118`), new windows unverified. jev first rung none_of_these 0.76 contradicted the evidence; second opinion terminal_section_override 0.95. **jev overridden.**
- **D-15: When `keys.json` is missing, the installer writes the app's vendor default for that OS and version (a pinned golden file) and then adds the owned key.** The app never merges `keys.json` with its defaults: it writes its defaults only when the file is missing or byte-identical to a default it shipped earlier, and any edit freezes future default updates (`src/keys.rs:166-189`; CHANGELOG 0.1.16), so a file with only our keys would turn off every default shortcut; the install note warns that new defaults must be added by hand afterwards. This **amends SPEC edge R4** ("a missing keys file is created with only owned keys"). jev first rung none_of_these 0.91 contradicted the evidence; second opinion seed_vendor_defaults 0.92. **jev overridden.**
- **D-16: User-binding detection** normalizes chord strings (split on `-` keeping a trailing `-` key such as `ctrl--`, modifiers sorted, aliases folded: `cmd`/`super`/`platform`, `alt`/`option`); the user's binding is any `terminal` entry on the chord or a `global`/`layout:*` entry whose value differs from the vendor default; reported `herdr-app: partial: kept yours`. **Own reasoning** (jev terminal_only low 0.70; first rung none_of_these 0.93 contradicted the evidence). Ledger.

### Tests and the Mac UAT
- **D-17: The herdr-app install and removal proof is a dedicated container target** `herdr-app` in `scripts/container-e2e-verify.sh`, modeled on `cmd_bun_lifecycle` (`:2864`) and `cmd_schedules` (`:2658`); it needs the network (the script fetches `latest.json` and the core installer); it hashes `~/.local/bin/herdr` and `~/.config/herdr` before and after each install and removal, in both orders, and lists leftovers (`herdr-core`, `hc`). jev container_target_with_network 0.85 (TypeSafe).
- **D-18: Tests:** registry tests (`iterm2` in `MACOS_ONLY`; `herdr-app` in `NO_MACOS_INTEL` with an Intel fixture, following `tests/test_registry.py:865-876`; distinct ids; script `paths`; cask `arch`); byte goldens from pure generators taking `platform_os` for the iTerm2 profile and the herdr-app Linux and macOS keys, on both CI OSes; a default-profile golden test with a fake runner over four starting states (a GUID set, none set, already ours, changed by the user after install); fixtures for a foreign file, shuffled user keys, a kept user binding, idempotent reconfigure, and drift `≈` through `version_status`; phase 27 table rows (`iterm2`: (b), (c), (d) written; `herdr-app`: (b) macOS vendor and Linux n/a, (c) written, (d) vendor, (a) unverified) and phase 28 declarations (`iterm2` writes `Custom Directory = Recycle`, `herdr-app` vendor).
- **D-19: Deferred to the owner's Mac (UAT lines):** iTerm2 loads the profile live and it becomes the default (iTerm2 running or not); Cmd+K sends `0x0c`; Option+Left/Right move by word and Spanish `@` still types; colors in light and dark mode; `Recycle` for tabs, windows and split panes; uninstall restores the previous default, including from inside iTerm2 (the cask's `quit` closes the installer's own terminal); the herdr-app cask install into `~/Applications` and `cmd-k` in a herdr-app terminal; Intel macOS (fixture only).
- **D-20: Dependencies:** phases 27 (table and closed-table test), 28 (`TERMINAL_KEYS`, the typed union, the `same_directory` test, the D-06 drift rule) and 29 (`placement`, `validate`) and 30 (the Ghostty row, which edits the same table first) execute before this phase.

### Claude's Discretion
- The profile file name, the optional-keys variant's name, the install notes' wording, and the dark-green RGB values (until the owner names them).

### Folded Todos
- Backlog 999.21 and 999.22 (this phase's sources).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/phases/28-shared-terminal-keys-mechanism/28-CONTEXT.md`, `29-CONTEXT.md`, `30-CONTEXT.md`, `27-CONTEXT.md` (under `.planning/phases/`)
- `.planning/research/SUMMARY.md`, `.planning/todos/completed/2026-10-15-add-iterm2-macos-only-entry-after-tool-onboarding-refactor.md`
- `installer/agent_settings.py` (splice helpers), `installer/atomic.py`, `installer/post_install.py`, `installer/status.py`, `installer/receipts.py`, `installer/resolve.py`, `scripts/container-e2e-verify.sh`
- Sources read by the analyzer (scratchpad `p31/`): herdr-app v0.1.16 (`src/keys.rs`, `src/mods.rs`, `defaults/AGENTS.md`, `install.sh`), iTerm2 master (`ITAddressBookMgr.h`, `VT100Output.m`, `PresetKeyMappings.plist`, Dynamic Profiles docs)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent_settings` JSON splice helpers and recorded-value ledger (`swap_recorded`, `kept_changed`), the created-record pattern of `terminal_shell.py`, `atomic.py`, the injected-runner seam of `post_install`.

### Established Patterns
- A user's own binding is kept and reported `partial: kept yours`; a recorded block the user deleted is the user's; macOS behaviors are pure generators with goldens on both OSes.

### Integration Points
- The phase 28 ownership union, `TERMINAL_KEYS`, `MACOS_ONLY` and the new `NO_MACOS_INTEL` allowlist, the container e2e harness.
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in this commit): the herdr app has one user keys file and never merges defaults; Esc+ on Option is the forbidden global switch and does not give word navigation; the iTerm2 key-map rows are the correct mechanism.
</specifics>

<deferred>
## Deferred Ideas

- To confirm: whether iTerm2 3.7.8 stable still reads the two-part key format and which format "Save Profile as JSON" writes there (analysis used master); whether a Dynamic Profile GUID survives as `Default Bookmark Guid` at launch and whether a running iTerm2 overwrites a `defaults write` on quit; what 3.7.8 sends for Option+Left with Option Normal and Esc+; herdr-app's default shell (rule a), new-window directory, and whether `herdr-app --version` exists; the owner's exact RGB values.

### Reviewed Todos (not folded)
None other matched.
</deferred>
