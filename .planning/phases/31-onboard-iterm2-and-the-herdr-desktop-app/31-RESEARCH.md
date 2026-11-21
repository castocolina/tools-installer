# Phase 31: Onboard iTerm2 and the Herdr desktop app - Research

**Researched:** 2026-11-21
**Domain:** terminal keys mechanism (two new JSON ownership variants), macOS preferences (`defaults`), a macOS-only cask, a vendor `install.sh` script method, container e2e
**Confidence:** HIGH for the code and the upstream source facts (read this session at pinned tags); MEDIUM for iTerm2 runtime behavior that only a real Mac can show

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### JSON modes of the keys mechanism
- **D-01: The ownership union gets two new variants,** not one: `WholeFile(proof)` for the iTerm2 Dynamic Profile and a per-key variant (`OwnedKeys`, name open) for the herdr app's `keys.json`, because the app creates and owns that file (herdr-app `src/keys.rs:175-189`) and uninstall must "remove only the owned keys". The per-key variant adds and removes two-level key paths such as `("terminal","ctrl-shift-k")` through the formatting-preserving splice helpers of `installer/agent_settings.py` (`insert_key`/`remove_key`, `:290-333,486-510`); the record stores the owned paths and the values written; drift means an owned key still holds the recorded value but the current render differs (rewrite); a current value that differs from the recorded one is a user change (`partial: kept yours`); strip removes only owned keys still holding the recorded value. `_dump` writes Ctrl+L as `"send:\f"` where the vendor uses a `\u000c` style (`agent_settings.py:255-256`): the golden pins one of the two. **Own reasoning** (jev separate_per_key_mode low 0.69; first rung low 0.56; splice_existing_helpers low 0.79 as second opinion). Ledger.
- **D-02: `WholeFile` ownership proof is the created-record plus a fixed installer GUID inside the JSON.** The record is `$XDG_DATA_HOME/tools-installer/terminal-iterm2-created` (28 D-01 naming). Apply: a missing file is created (and the `DynamicProfiles` folder); a file with our GUID and the record whose bytes differ is rewritten (drift); a file with foreign content is refused with `iTerm2 keys not changed: ...`, never overwritten. Strip: delete the file when the GUID matches even if the bytes differ, otherwise refuse. Writes are atomic with compare-before-commit (`installer/atomic.py:36-80`, `FileSnapshot`). Golden bytes: `json.dumps(sort_keys=True, indent=2, ensure_ascii=False) + "\n"`. **Own reasoning** (jev record_and_guid low 0.49). Ledger.
- **D-03: What a deleted file means depends on the variant:** a deleted iTerm2 profile while the default-profile setting still names our GUID reads `≈ apply install tuning` (the default is broken, not a choice; iTerm2 falls back to its parent or default when the profile is missing); a herdr-app owned key gone after a recorded install is the user's choice (the app's escape hatch moves `keys.json` aside and restores defaults, `defaults/AGENTS.md:59-61`). This amends SPEC R5 and refines 28 D-06. jev per_mode 0.80 (TypeSafe).
- **D-04: `placement` moves into the `OwnedRegion` variant** (amending 29 D-11): a whole file has no position and a per-key edit is located by key path. `validate` stays per row: iTerm2 JSON parses and holds exactly one profile with our GUID; herdr-app JSON parses and every section is an object. **Own reasoning** (jev row_field_with_na low 0.56; first rung low 0.64). Ledger.

#### iTerm2
- **D-05: The entry:** `id = "iterm2"`, `name = "iTerm2"`, `category = "terminal"`, `tier = "user"`, `cmd` default (iTerm2 has no command; presence comes from the `iTerm.app` bundle, `installer/status.py:201-210`), one `cask` method with `os = ["macos"]`, `cask = "iterm2"`, `app = "iTerm.app"`, `min_os_version = "13"` (cask 3.7.8 needs macOS 13, read live), `post_install = ["apply_terminal_tuning"]`; `iterm2` joins `MACOS_ONLY` (`tests/test_registry.py:797`). Uninstall is `brew uninstall --cask` with no zap (`installer/uninstall.py:113`); the cask's own `quit: com.googlecode.iterm2` closes iTerm2 first.
- **D-06: No `config_paths`:** preferences are a plist cached by the macOS preferences daemon, and `~/Library/Application Support/iTerm2` also holds the user's other dynamic profiles and scripts. Our one file is stripped by the keys row. jev none 0.97 (TypeSafe).
- **D-07: The profile file** is `~/Library/Application Support/iTerm2/DynamicProfiles/tools-installer.json` (name open), one profile with a fixed `Guid` and `Name` and no `"Rewritable"` key (the install note says changes made in the iTerm2 settings window do not stick). `"Custom Directory": "Recycle"` for new tabs, windows and panes (allowed values Yes/No/Recycle/Advanced, `ITAddressBookMgr.h:54`; the factory default is `"No"`, so `same_directory = writes`). Cmd+K is the keyboard-map entry `"0x6b-0x100000"` to `{"Action": 11, "Text": "0x0c"}` (`KEY_ACTION_HEX_CODE = 11`, `iTermKeyBindingAction.h:51`; a profile mapping applies before the Clear Buffer menu item, `iTermApplication.m:562-583`). Reload is live, but one malformed file anywhere in the folder blocks every reload, so the check message says so. These facts come from iTerm2's master source, not the 3.7.8 tag: confirmed in the Mac UAT. jev send_ctrl_l low 0.69 (TypeSafe), 0.57 (Laya). **Own reasoning** (KEYS-03). Ledger.
- **D-08: Option stays Normal; word navigation is two keyboard-map rows:** Option+Left `0xf702-0x280000` to `{"Action": 10, "Text": "b"}` and Option+Right `0xf703-0x280000` to `{"Action": 10, "Text": "f"}` (iTerm2's own "Terminal.app Compatibility" preset rows, `PresetKeyMappings.plist`; arrows send `CSI 1;%dD` whatever the Option setting, `VT100Output.m:58-61,246-262`). Setting both Option keys to Esc+ is iTerm2's form of the global Option-as-Alt switch, which 27 D-11 forbids (it breaks Spanish `@ | # \`) and which alone would not produce `ESC b`/`ESC f`. This **amends NTERM-02 / SPEC R1 / ROADMAP criterion 1** ("sets Option as Esc+"); **flagged: needs confirmation**. jev map_rows_only 0.97 (TypeSafe).
- **D-09: The profile inherits from the previous default:** `Dynamic Profile Parent GUID` is the recorded previous default GUID (left out when none), and the parent's keyboard map is merged in (read with `defaults export` through the injected runner) because a keyboard map in the profile replaces the parent's whole map; a clash is reported `partial: kept yours`. Without this the user's font, size and key mappings vanish when our profile becomes the default. **Own reasoning** (jev parent_plus_merged_keys low 0.63; first rung low 0.50). Ledger.
- **D-10: Colors:** the requested scheme is "dark background with dark-green text, a Matrix console look" (todo `.planning/todos/completed/2026-10-15-add-iterm2-macos-only-entry-after-tool-onboarding-refactor.md`, item 3). A dynamic profile cannot name a color preset, so five explicit color entries (Red/Green/Blue/Alpha Component, Color Space sRGB) set Foreground, Background, Bold, Cursor and Selection, plus `"Use Separate Colors for Light and Dark Mode": false` (the factory default is `true`, which makes the plain keys ignored; `DefaultBookmark.plist`); the 16 ANSI colors stay untouched. The owner's exact RGB values were never recorded: the generator uses a documented dark-green palette and the Mac UAT confirms it. **Own reasoning** (jev core_five low 0.36; TypeSafe full_palette low 0.55). Ledger.
- **D-11: Making the profile the default is an optional hook on the iTerm2 keys row,** not a new post-install action: it reads and writes the `Default Bookmark Guid` preference (`ITAddressBookMgr.h:38`) in `com.googlecode.iterm2` through `defaults read`, `defaults write` and `defaults delete`, with the command runner injected (as `post_install.use_git_runner`, `installer/post_install.py:142-153`) and pure functions turning the before state into commands. The previous value, or "none set", is recorded in `$XDG_DATA_HOME/tools-installer/terminal-iterm2-default`. Restore runs only when the current value is still our GUID (otherwise the user's later choice is kept, `partial: kept yours`); "none set" is restored with `defaults delete`; the step is skipped with a `partial` note when `LoadPrefsFromCustomFolder` is on (`SUMMARY.md:109,143`). Order: restore the preference, then delete the file; restore runs after the cask removal (`installer/app.py:611-643`), when brew has already quit iTerm2. jev first rung none_of_these 0.99 contradicted the evidence; second opinion separate_action low 0.65. **jev overridden / Own reasoning.** Ledger.

#### Herdr desktop app
- **D-12: The id is `herdr-app`** (category `terminal`), matching the cask token, the command and the config folder; every herdr check in the installer is an exact match, so the two ids cannot collide (`installer/receipts.py:292`, `installer/app.py:625`, `installer/agent_settings.py:620,695,721`, `installer/version_status.py:739`). Linux is a `script` method: `os = ["debian","fedora","arch"]`, `url = "https://releases.herdr.dev/app/install.sh"`, `shell = "sh"`, `bin_dir = "~/.local/bin"`, `paths` = `~/.local/share/herdr-app/`, `~/.local/bin/herdr-app`, `~/.local/share/applications/herdr-app.desktop`, `~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg`; no `writable_prefix`, no sudo, no `remove` or `update` (re-running the script updates the app, and the app self-updates); the receipt claims only paths this run created (`installer/receipts.py:500-519`); Linux arm64 is published. The script also installs `herdr-core` and `hc` through a nested unchecked `curl | sh` when none exists (`install.sh:139-143`): those stay out of `paths` per SPEC R3 and remain after removal (recorded in `# Verified`); it honors `XDG_DATA_HOME`, so a custom value leaves the receipt empty and fails closed. macOS is `cask = "herdr-app"`, `os = ["macos"]`, `arch = ["arm64"]`, `app = "Herdr.app"`; brew links `herdr-app` into `$HOMEBREW_PREFIX/bin` (the 27 D-10 gap, recorded); Intel macOS resolves no method (`installer/resolve.py:50-55`, `installer/catalog_tui.py:397`) and a new test allowlist `NO_MACOS_INTEL` is needed (`MACOS_ARM64_ONLY` means macOS-only). Flagged for the owner: the vendor `install.sh` on macOS puts `Herdr.app` in `~/Applications` and links `~/.local/bin/herdr-app` (`install.sh:110-136`), which meets the 27 macOS-app rule better than the cask; the SPEC locks the cask. jev herdr_app 0.98 (TypeSafe).
- **D-13: `config_paths = ["~/.config/herdr-app"]`,** with no overlap with herdr's `~/.config/herdr` (`installer/model.py:461-474`); owned keys are stripped before any config deletion, as for herdr (`installer/app.py:625-629`). jev declare 0.80 (TypeSafe).
- **D-14: The keys file is `~/.config/herdr-app/keys.json` on every OS** (the folder resolves as `$HERDR_APP_HOME`, else `$XDG_CONFIG_HOME/herdr-app`, else `~/.config/herdr-app`, `src/mods.rs:60-65`); `keys.macos.json` is only the default compiled into macOS builds (`src/keys.rs:1,30-33,111-113`). This **amends SPEC R4** ("keys.json / keys.macos.json"). Rows write to the `terminal` section: Linux `"ctrl-shift-k": "send:\f"`, macOS `"cmd-k": "send:\f"`; the `terminal` section beats `global` (`defaults/AGENTS.md:523-525`), so the vendor `global` `ctrl-shift-k` picker binding stays active outside terminals; the install note names it as displaced in terminals (the picker stays in the palette, Ctrl+Shift+P). macOS Option word navigation is `vendor` (`keys.macos.json` already sends `ESC b`/`ESC f`); Linux gets no Alt rows (owner rule); `same_directory = vendor` for tabs and splits (`README.md:45`, `defaults/AGENTS.md:114-118`), new windows unverified. jev first rung none_of_these 0.76 contradicted the evidence; second opinion terminal_section_override 0.95. **jev overridden.**
- **D-15: When `keys.json` is missing, the installer writes the app's vendor default for that OS and version (a pinned golden file) and then adds the owned key.** The app never merges `keys.json` with its defaults: it writes its defaults only when the file is missing or byte-identical to a default it shipped earlier, and any edit freezes future default updates (`src/keys.rs:166-189`; CHANGELOG 0.1.16), so a file with only our keys would turn off every default shortcut; the install note warns that new defaults must be added by hand afterwards. This **amends SPEC edge R4** ("a missing keys file is created with only owned keys"). jev first rung none_of_these 0.91 contradicted the evidence; second opinion seed_vendor_defaults 0.92. **jev overridden.**
- **D-16: User-binding detection** normalizes chord strings (split on `-` keeping a trailing `-` key such as `ctrl--`, modifiers sorted, aliases folded: `cmd`/`super`/`platform`, `alt`/`option`); the user's binding is any `terminal` entry on the chord or a `global`/`layout:*` entry whose value differs from the vendor default; reported `herdr-app: partial: kept yours`. **Own reasoning** (jev terminal_only low 0.70; first rung none_of_these 0.93 contradicted the evidence). Ledger.

#### Tests and the Mac UAT
- **D-17: The herdr-app install and removal proof is a dedicated container target** `herdr-app` in `scripts/container-e2e-verify.sh`, modeled on `cmd_bun_lifecycle` (`:2864`) and `cmd_schedules` (`:2658`); it needs the network (the script fetches `latest.json` and the core installer); it hashes `~/.local/bin/herdr` and `~/.config/herdr` before and after each install and removal, in both orders, and lists leftovers (`herdr-core`, `hc`). jev container_target_with_network 0.85 (TypeSafe).
- **D-18: Tests:** registry tests (`iterm2` in `MACOS_ONLY`; `herdr-app` in `NO_MACOS_INTEL` with an Intel fixture, following `tests/test_registry.py:865-876`; distinct ids; script `paths`; cask `arch`); byte goldens from pure generators taking `platform_os` for the iTerm2 profile and the herdr-app Linux and macOS keys, on both CI OSes; a default-profile golden test with a fake runner over four starting states (a GUID set, none set, already ours, changed by the user after install); fixtures for a foreign file, shuffled user keys, a kept user binding, idempotent reconfigure, and drift `≈` through `version_status`; phase 27 table rows (`iterm2`: (b), (c), (d) written; `herdr-app`: (b) macOS vendor and Linux n/a, (c) written, (d) vendor, (a) unverified) and phase 28 declarations (`iterm2` writes `Custom Directory = Recycle`, `herdr-app` vendor).
- **D-19: Deferred to the owner's Mac (UAT lines):** iTerm2 loads the profile live and it becomes the default (iTerm2 running or not); Cmd+K sends `0x0c`; Option+Left/Right move by word and Spanish `@` still types; colors in light and dark mode; `Recycle` for tabs, windows and split panes; uninstall restores the previous default, including from inside iTerm2 (the cask's `quit` closes the installer's own terminal); the herdr-app cask install into `~/Applications` and `cmd-k` in a herdr-app terminal; Intel macOS (fixture only).
- **D-20: Dependencies:** phases 27 (table and closed-table test), 28 (`TERMINAL_KEYS`, the typed union, the `same_directory` test, the D-06 drift rule) and 29 (`placement`, `validate`) and 30 (the Ghostty row, which edits the same table first) execute before this phase.

### Claude's Discretion
- The profile file name, the optional-keys variant's name, the install notes' wording, and the dark-green RGB values (until the owner names them).

### Deferred Ideas (OUT OF SCOPE)
- To confirm: whether iTerm2 3.7.8 stable still reads the two-part key format and which format "Save Profile as JSON" writes there (analysis used master); whether a Dynamic Profile GUID survives as `Default Bookmark Guid` at launch and whether a running iTerm2 overwrites a `defaults write` on quit; what 3.7.8 sends for Option+Left with Option Normal and Esc+; herdr-app's default shell (rule a), new-window directory, and whether `herdr-app --version` exists; the owner's exact RGB values.

(Several of these were answered by source reads this session; see "Deferred questions answered" below. They stay out of scope as decisions; the answers only inform the plan.)

**Out of scope (SPEC):** iTerm2 "Show Focus Cursor" and the agent-collaboration extension; changing the `herdr` multiplexer entry; the app's auto-update; real-Mac verification.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NTERM-02 | iTerm2 is a macOS-only cask with an installer-owned Dynamic Profile: Option+Left/Right word navigation through key-map rows (Option stays Normal, amended 31 D-08, needs confirmation), the KEYS-03 clear, new tabs, windows and panes in the current directory, the requested colors; the profile becomes the default and an uninstall restores the previous default. | Registry touch list (iTerm2 rows); `WholeFile` variant design; iTerm2 facts table (all key values re-verified at tag v3.7.8); default-profile hook design with the `defaults` seam; pitfalls 1-6; goldens G1-G3 |
| NTERM-03 | The Herdr desktop app (`herdrdev/herdr-app`) is an entry distinct from `herdr`: user-scope `install.sh` on Linux, the cask on Apple Silicon macOS; it meets SKILL-01 through its own keys file, displacing its Linux Ctrl+Shift+K picker binding with an install note. | Registry touch list (herdr-app rows, `NO_MACOS_INTEL`); `OwnedKeys` variant design; herdr-app facts table (v0.1.16 source); GPUI chord grammar (corrects D-16 aliases); container target `herdr-app`; pitfalls 7-12; goldens G4-G5 |
</phase_requirements>

## Project Constraints (from CLAUDE.md and AGENTS.md)

Binding on the plan, with the same authority as locked decisions:

- English only in every identifier, comment, docstring, log line and commit message.
- uv owns the environment; never `pip`, `poetry`, `conda`. No new dependency is needed by this phase (stdlib `json`, `plistlib`, `dataclasses`).
- Never bypass a gate (ruff check, ruff format, pyright strict at Python 3.11, bandit, vulture, shellcheck, pytest with coverage floor). Never skip, xfail or delete an assertion to go green.
- Test what you changed while working (`uv run pytest <files> --no-cov -q`); after each plan run `make validate` and `make test` once each. Never `make validate && make test` per commit.
- Plans are `type: execute`, test-first inside one green commit (`.claude/testing.md`, "Test-first inside one green commit"); keep the RED output in the SUMMARY.
- Never mutate the developer's host: no `make run`, `make fix`, `make doctor`, `make uninstall`, `make dev-setup`; no real installs on the host; `install.sh` runs only in a disposable container (`scripts/detect-container-runtime.sh`), removed by exact name afterwards.
- Zero sudo: no code path runs `sudo`, `pkexec` or `doas`. `defaults write` on the user domain needs none.
- Every test is xdist-safe (tmp_path, monkeypatch HOME and env, no fixed shared path) and offline (network calls mocked).
- Temporary files live in a run-owned directory and are deleted on every exit path.
- Coherent commits: one self-contained change per commit; changes reach `main` by branch push, green CI, fast-forward.
- Architecture (`.claude/architecture.md`): one registry, one apply workflow, wiring-only `setup.py`.
- CI runs Python 3.15 on ubuntu-latest and macos-latest (`.github/workflows/ci.yml:21-22`); local venv is 3.12.12 (probed). See "Python 3.12 vs 3.15" below.

## Summary

Phases 27 to 30 have executed, so the mechanism this phase extends is real code: `installer/terminal_keys.py` holds `TERMINAL_KEYS` with four rows (alacritty, kitty, wezterm, ghostty), all `OwnedRegion` rows, and three generic entry points (`apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys`) that are wired into exactly three production call sites (`post_install._tune_terminal`, `version_status._terminal_tuning_fact`, `app._after_removal`). The ownership "union" CONTEXT D-01 talks about does not exist yet: `KeysRow.ownership` is typed `OwnedRegion` and its docstring still says "the sole ownership mode until phase 31". D-04's `placement` move already happened (it lives in `OwnedRegion`). So phase 31 creates the union, keeps the four region rows on the existing code path byte-for-byte, and adds two dispatch branches.

The upstream facts the CONTEXT relied on were re-read this session at pinned tags, which removes most of the "master, not 3.7.8" uncertainty: every iTerm2 file the analyzer read on master (`ITAddressBookMgr.h`, `iTermKeyBindingAction.h`, `iTermKeystroke.m`, `VT100Output.m`, `iTermApplication.m`, `PresetKeyMappings.plist`, `DefaultBookmark.plist`) is byte-identical at tag `v3.7.8`, the version the cask ships. Two CONTEXT claims change: (1) at v3.7.8 a malformed dynamic-profile file is ignored per file, not "blocking every reload" (the docs still say the latter; code wins for behavior, so the check message should not claim it); (2) the herdr app's chord grammar (vendored GPUI 0.3.8) accepts `cmd`/`super`/`win` and `secondary`, not `option` or `platform` as modifiers, so D-16's alias list needs a correction (it is "own reasoning", so this is a recommendation, not an override). Three deferred questions are answered from source: a `Default Bookmark Guid` naming a dynamic profile is honored at launch; `herdr-app --version` exists and prints `herdr-app 0.1.16` without opening a window; and a running iTerm2 that loses its default profile writes a fallback default into the preferences itself, which is why the uninstall must run with iTerm2 quit.

The biggest unplanned risk is the iTerm2 uninstall from inside iTerm2: the cask's `quit` closes the window that runs the installer, so the restore step may never run. The second is that `make e2e`'s `--all` pass will now run the herdr-app `install.sh` (network, plus a nested `herdr-core` install that intentionally stays after removal), which the global residue allowlist does not know about.

**Primary recommendation:** add `WholeFile` and `OwnedKeys` beside `OwnedRegion` as a typed union, dispatch on `isinstance` at the top of the three entry points (region code untouched), keep every generator pure (`platform_os` plus recorded state in, bytes out), put every `defaults` call behind one module-level seam stubbed in `tests/conftest.py` exactly like `wezterm_show_keys`, and prove herdr-app's install and removal with a landing-style container target and a Python driver modeled on `tests/e2e_ghostty_driver.py`.

## CONTEXT Reconciliation

CONTEXT was written 2026-11-19, before phases 27 to 30 executed. Each statement that assumed missing code or cites old lines, checked against the tree on branch `gsd/phase-27-tool-onboarding-skill-terminal-defaults-as-rules`:

| # | CONTEXT says | The code is now | What the plan should do |
|---|--------------|-----------------|-------------------------|
| R1 | Domain: "`terminal_keys.py`, `terminal_regions.py`, the phase 27 table and the Ghostty row do not exist yet." | All exist. `TERMINAL_KEYS` has `"alacritty"`, `"kitty"`, `"wezterm"`, `"ghostty"` rows [VERIFIED: installer/terminal_keys.py:292-367]; the skill table has a `ghostty` row [VERIFIED: .claude/skills/tool-onboarding/SKILL.md:214]. | Extend, do not create. Every edit to the table follows the phase 30 shape. |
| R2 | D-01 "The ownership union gets two new variants" (implies a union exists). | No union. `class OwnedRegion` docstring: `"A marker-delimited region owned by the installer; the sole ownership mode until phase 31."` and `KeysRow` field `ownership: OwnedRegion  # The region this row owns.` [VERIFIED: installer/terminal_keys.py:89-100]. | Create `Ownership = OwnedRegion \| WholeFile \| OwnedKeys` and retype `KeysRow.ownership: Ownership`. Update the docstring. |
| R3 | D-04 "`placement` moves into the `OwnedRegion` variant (amending 29 D-11)". | Already done: `placement: Placement = Placement.END  # Where a new region goes.` is an `OwnedRegion` field [VERIFIED: installer/terminal_keys.py:95]. | Nothing to move. Only make sure the two new variants carry no `placement`, and that `strip_terminal_keys`'s `seed=WEZTERM_SKELETON if row.ownership.placement is Placement.BEFORE_RETURN` [VERIFIED: installer/terminal_keys.py:522] and `terminal_keys_pending`'s `row.ownership.placement is Placement.BEFORE_RETURN` [VERIFIED: installer/terminal_keys.py:459] stay inside the region branch (pyright strict fails on attribute access through the union otherwise). |
| R4 | D-11 "the command runner injected (as `post_install.use_git_runner`, `installer/post_install.py:142-153`)". | `use_git_runner` exists at `installer/post_install.py:150-153` with `_no_git` at 142-143. But the closer in-module precedent is the WezTerm read-back seam: module function `wezterm_show_keys(path)` [VERIFIED: installer/terminal_keys.py:274-281] replaced by an autouse fixture `no_wezterm_show_keys` [VERIFIED: tests/conftest.py:122-130]. The keys row API (`plan(platform_os, text, path)`) has no runner parameter, and the status pass calls `terminal_keys_pending(row, tool.id, platform.os, Path.home(), os.environ)` [VERIFIED: installer/version_status.py:832]. | Use one module-level seam in `terminal_keys.py` (say `iterm2_defaults(argv) -> str`) plus an autouse conftest stub that raises or returns "unavailable"; tests that need it monkeypatch a fake. This satisfies D-11's "runner injected" without threading a runner through three call sites. Flag the choice in the plan (it implements D-11's intent, not its cited mechanism). |
| R5 | D-11 "a new post-install action" is ruled out; "an optional hook on the iTerm2 keys row". | `KeysRow` fields are pinned exactly by `test_row_fields_are_exactly_the_declared_set` [VERIFIED: tests/test_terminal_keys.py:2169-2184], listing `"ownership", "config_path", "plan", "validate", "summary", "created_record", "same_directory", "sibling_regions", "clear", "readback", "validate_on_status", "bind_created_path", "strip_files"`. | Adding the hook field means updating that test in the same commit (append the new name). Keep the field optional with `None` default, as `readback` and `strip_files` are. |
| R6 | D-17 "modeled on `cmd_bun_lifecycle` (`:2864`) and `cmd_schedules` (`:2658`)". | Lines moved: `cmd_schedules` at 2687, `cmd_bun_lifecycle` at 2893, plus two newer and closer models, `cmd_herdr_keys` at 2931 and `cmd_ghostty` at 2979 [VERIFIED: scripts/container-e2e-verify.sh, `rg '^cmd_'`]. The dispatcher `main()` is at 3007 with `herdr-keys) cmd_herdr_keys "$@" ;;` and `ghostty) cmd_ghostty "$@" ;;`. | Model the target on `cmd_ghostty` (landing box, PID-named container, `LANDING_DRIVER_MODULE`, a root setup stage, `landing_step` verdicts) with a new driver `tests/e2e_herdr_app_driver.py`. `cmd_bun_lifecycle` is the right model only for the "several verdict steps, collect all" shape. |
| R7 | D-12 cites `installer/version_status.py:739` for the herdr exact match. | Now line 741: `"herdr": ("herdr", "herdr"),` inside `_TERMINAL_ROWS` [VERIFIED: installer/version_status.py:735-742]. Other cites hold: `CONFIG_AGENTS = ("claude", "codex", "opencode", "cursor-agent", "vscode", "copilot", "herdr")` [VERIFIED: installer/receipts.py:292]; `if tool.id in receipts.CONFIG_AGENTS:` [VERIFIED: installer/app.py:625]; `"herdr": "toml",`, `("herdr", "sidebar"): (`, `("herdr", "default-shell"): (("terminal", "default_shell"),),` [VERIFIED: installer/agent_settings.py:620,695,721]. Also exact: `installer/postinstall.py:452,469,562`, `installer/agent_env.py:52-54`, `installer/terminal_shell.py:590` (`HERDR = "herdr"`). | All exact `==`/`in tuple` matches; `herdr-app` cannot collide. The `_TERMINAL_ROWS` warning router splits on the first colon (`prefix, _, rest = warning.partition(":")` [VERIFIED: installer/version_status.py:1603]), so a `herdr-app: partial: ...` line never lands on the `herdr` row. Add one regression test that a `herdr-app:` prefixed line is not routed to `herdr`. |
| R8 | D-05 "`iterm2` joins `MACOS_ONLY` (`tests/test_registry.py:797`)". | `MACOS_ONLY = {"gnu-bash"}` is at line 798 [VERIFIED: tests/test_registry.py:798]. | Add `"iterm2"`. |
| R9 | D-12 "a new test allowlist `NO_MACOS_INTEL` is needed (`MACOS_ARM64_ONLY` means macOS-only)". | Confirmed: `MACOS_ARM64_ONLY = {"container", "podman"}` and the honesty test asserts no method on `macos/amd64` and some method on `macos/arm64` [VERIFIED: tests/test_registry.py:801,864-877]; the stranded-tool test adds `MACOS_ARM64_ONLY` to the allowed set on every non-macOS platform too [VERIFIED: tests/test_registry.py:835-839], which would wrongly excuse herdr-app on Linux. | Add `NO_MACOS_INTEL = {"herdr-app"}`, allowed only when `platform_os == "macos" and arch != "arm64"`, plus an honesty test (no method on macos/amd64, a method on macos/arm64 and on each Linux distro). |
| R10 | D-07 "one malformed file anywhere in the folder blocks every reload, so the check message says so". | At tag v3.7.8 the loader skips a bad file and loads the others: `loadDynamicProfilesFromFileLoggingFailure` logs `"Ignoring dynamic profiles in “%@” because of an error."` and the reload loop continues over the sorted file list [VERIFIED: v3.7.8 sources/Settings/Profiles/iTermDynamicProfileManager.m:321-347,544-552]. The docs still say "If any is malformed, then no changes will be processed" [CITED: iterm2.com/documentation-dynamic-profiles.html, cached copy read 2026-11-19]. | Do not claim the whole folder is blocked. Suggested note: "iTerm2 skips a Dynamic Profiles file it cannot parse and reports it." The claim is "own reasoning" in D-07, so this is a correction to a provisional detail, not an override. |
| R11 | D-07 "These facts come from iTerm2's master source, not the 3.7.8 tag: confirmed in the Mac UAT." | The seven files are byte-identical between the 2026-11-19 master cache and tag `v3.7.8` (diff printed no difference this session). | Cite the v3.7.8 tag in code comments. The Mac UAT still confirms runtime behavior (D-19). |
| R12 | D-16 aliases "`cmd`/`super`/`platform`, `alt`/`option`". | Vendored GPUI `Keystroke::parse` at herdr-app v0.1.16 accepts modifiers `ctrl`, `alt`, `shift`, `fn`, `secondary` (cmd on macOS, ctrl elsewhere) and `cmd`/`super`/`win` (platform), case-insensitively; a single uppercase letter means shift plus the lowercase key; a trailing `-` is the `-` key; any other leading token is an error [VERIFIED: herdr-app v0.1.16 vendor/gpui-pre/src/platform/keystroke.rs:171-262]. `KeyBinding::load` splits a binding on whitespace into a keystroke sequence [VERIFIED: vendor/gpui-pre/src/keymap/binding.rs:48-60]. | Normalize with exactly that grammar: fold `cmd`/`super`/`win` to one platform modifier, fold `secondary` per OS, lowercase, expand a single uppercase key to shift plus lowercase, and treat a binding whose first keystroke equals our chord as the user's. `option` and `platform` are not modifiers in this grammar (a `keys.json` using them fails to load in the app); do not fold them. D-16 is "own reasoning": flag the correction in the plan. |
| R13 | D-20 dependencies "execute before this phase". | Executed; STATE records 27 to 30 as `verification_deferred_human` [VERIFIED: .planning/STATE.md:185-188]. | None. Phase 30 left `NTERM-01` "Pending" in the traceability table [VERIFIED: .planning/REQUIREMENTS.md:129]; not this phase's concern. |
| R14 | D-12 "brew links `herdr-app` into `$HOMEBREW_PREFIX/bin`"; cask installs into `/Applications`. | Live cask JSON: `{'app': ['Herdr.app'], 'target': '/Applications/Herdr.app'}`, `{'binary': ['$APPDIR/Herdr.app/Contents/MacOS/Herdr', {'target': 'herdr-app'}], ...}`, `depends_on: {'arch': [{'type': 'arm', 'bits': 64}], 'macos': {}}`, zap `~/.config/herdr-app` [VERIFIED: formulae.brew.sh/api/cask/herdr-app.json, 2026-11-21]. The installer always passes `--appdir={applications_dir()}` [VERIFIED: installer/executors.py:704-707]. | Herdr.app lands in `~/Applications`; the binary link follows `$APPDIR`. Matches D-12. |

### Deferred questions answered by source (inform the plan; decisions unchanged)

| Deferred question | Answer | Evidence |
|-------------------|--------|----------|
| Does 3.7.8 still read the two-part key format? | Yes. `initWithString:` parses 4-part, 3-part, then `"%x-%x"` two-part; lookup falls back to `dict[self.legacySerialized]` where `legacySerialized` is `@"0x%x-0x%x"`. | [VERIFIED: v3.7.8 sources/Keyboard/iTermKeystroke.m:203-251,347-349,421-433] |
| Which format does iTerm2 write now? | Four-part `0x%x-0x%llx-0x%x-0x%x` (character, flags, keycode, serialization version); three-part is an older spelling still matched. | [VERIFIED: v3.7.8 iTermKeystroke.m:372-390] |
| Does a dynamic profile GUID survive as `Default Bookmark Guid` at launch? | Yes. The original default GUID is read before dynamic profiles load and re-applied when a dynamic profile carries it: `[[ProfileModel sharedInstance] setDefaultByGuid:originalDefaultGuid];`. | [VERIFIED: v3.7.8 sources/Settings/Profiles/ITAddressBookMgr.m:309,369-377] |
| Does a running iTerm2 overwrite the preference? | Only when its in-memory default changes. Removing the default profile while running calls `setDefaultByGuid:` with `bookmarks_[0]`, which writes `KEY_DEFAULT_GUID` to the preferences. | [VERIFIED: v3.7.8 sources/Settings/Profiles/ProfileModel.m:590-621,910-919] |
| Does `herdr-app --version` exist? | Yes, handled before any window code: `Some("-V" \| "--version" \| "version") => return println!("herdr-app {}", env!("CARGO_PKG_VERSION")),`. | [VERIFIED: herdr-app v0.1.16 src/main.rs:105-111] |
| herdr-app new-window directory and default shell (rule a) | Still unverified (no source read covers them). | — |

## Architectural Responsibility Map

This is a local CLI/TUI installer; the "tiers" are its layers.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Catalog entries (`iterm2`, `herdr-app`) | Registry data (`installer/registry.toml`) | Loader validation (`installer/model.py`) | One registry; methods resolve through `resolve.py` |
| Install and removal routes (cask, script) | Executors (`executors.py`, `uninstall.py`) | Receipts (`receipts.py`) | Existing kinds; no new executor code |
| Ownership variants and dispatch | Keys mechanism (`terminal_keys.py`) | Shared primitives (`terminal_regions.py`, `agent_settings.py`, `atomic.py`) | The single apply/check/strip path for terminals (28 D-01) |
| iTerm2 profile and herdr keys rendering | Pure generators in `terminal_keys.py` (or a new sibling module) | — | Goldens run on both CI OSes |
| `Default Bookmark Guid` read/write/restore | Keys row hook + `defaults` seam | Records under `$XDG_DATA_HOME/tools-installer/` | Host side effect isolated behind one seam |
| Pending `≈` fact | `version_status._terminal_tuning_fact` (unchanged) | `terminal_keys_pending` dispatch | Generic already |
| Strip on removal | `app._after_removal` (unchanged) | `strip_terminal_keys` dispatch | Generic already; runs before `config_paths` deletion |
| Install/removal proof for the script | Container target + Python driver | Host tests with stubbed `ct` | Never on the host |

## Standard Stack

### Core (all in-repo or stdlib; nothing to install)

| Component | Version | Purpose | Why |
|-----------|---------|---------|-----|
| `json` (stdlib) | 3.11+ | Render and parse the profile and keys files | Deterministic with `sort_keys=True, indent=2, ensure_ascii=False` |
| `plistlib` (stdlib) | 3.11+ | Parse `defaults export com.googlecode.iterm2 -` XML for the parent keyboard map | Runs on Linux CI with a fixture plist |
| `installer/agent_settings.py` splice helpers | in-repo | `insert_key`, `remove_key`, `replace_value`, `lookup`, `same_value`, `key_held`, `read_settings`, `write_if_unchanged`, `missing_dirs`, `remove_created_dirs` | Formatting-preserving, guarded by re-parse (`_guarded`) [VERIFIED: installer/agent_settings.py:109-137,259-325,486-510,556-607] |
| `installer/terminal_regions.py` | in-repo | `xdg_config_home`, `xdg_data_home`, `snapshot_text`, `first_line`, `KeysPlan`, `TerminalShellError`, `created_path_record` | Shared by every row [VERIFIED: installer/terminal_regions.py:230-237,606-650,694-695] |
| `installer/atomic.py` | in-repo | `atomic_write_text`, `FileSnapshot`, `read_capped` | Compare-before-commit writes |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `OwnedKeys` in the keys mechanism | The agent-settings ledger (`apply_agent_tuning`, `_KEYS[("herdr-app","keys")]`) that `herdr` already uses | Gives absent-only insert, ledger and `kept_changed` for free, but cannot seed the vendor default (D-15) or normalize chords (D-16), and breaks the "every `apply_terminal_tuning` tool has a `TERMINAL_KEYS` row" completeness test. D-01 locks the keys mechanism; reuse the helpers, not the ledger. |
| A runner threaded through `KeysRow` | Module-level seam (`wezterm_show_keys` precedent) | Seam is smaller and already the module's pattern (see R4). |

**Installation:** none.

## Package Legitimacy Audit

No PyPI, npm or crates package is added. The phase installs two vendor artifacts for users, not into the project:

| Artifact | Source | Verification | Disposition |
|----------|--------|--------------|-------------|
| Cask `iterm2` 3.7.8 | Homebrew cask API | `depends_on.macos >= 13`, `auto_updates: True` [VERIFIED: formulae.brew.sh/api/cask/iterm2.json, 2026-11-21] | Approved (official cask) |
| Cask `herdr-app` 0.1.16 | Homebrew cask API | arm64 only, `auto_updates: True` [VERIFIED: formulae.brew.sh/api/cask/herdr-app.json, 2026-11-21] | Approved |
| `https://releases.herdr.dev/app/install.sh` | Vendor | Fetched live 2026-11-21, byte-identical to the 2026-11-19 copy; verifies the app tarball against `latest.json` sha256 (`install.sh:53-77`); the nested core installer `https://releases.herdr.dev/core/install.sh` is piped to `sh` unchecked (`install.sh:139-143`) | Approved with the SPEC R3 note; container-only in tests |

**Packages removed due to [SLOP] verdict:** none. **Packages flagged [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
 install / reconfigure                       status pass                         removal
        |                                         |                                  |
 post_install._tune_terminal          version_status._terminal_tuning_fact    app._after_removal
        |                                         |                                  |
        v                                         v                                  v
 apply_terminal_keys(row, ...)        terminal_keys_pending(row, ...)       strip_terminal_keys(row, ...)
        |                                         |                                  |
        +------------- dispatch on type(row.ownership) ------------------------------+
        |                         |                                   |
   OwnedRegion               WholeFile (iterm2)                  OwnedKeys (herdr-app)
   (unchanged code)               |                                   |
                       recorded state (prev default,         keys.json present?
                       merged parent rows) --> pure            no  --> seed pinned vendor default (D-15)
                       iterm2_profile(platform_os,...)         yes --> parse, find user bindings (D-16)
                                  |                                   |
                       compare with file on disk:              insert_key per owned (section, chord)
                        missing -> create + record             record [(path, value)] actually written
                        our GUID, bytes differ -> rewrite      drift: owned key holds recorded value but
                        foreign -> refuse                        render differs -> rewrite
                                  |                            user changed value -> partial: kept yours
                       hook: defaults read/write                       |
                       Default Bookmark Guid  <-- seam --> /usr/bin/defaults (macOS only; stub in tests)
                                  |
                       strip: restore pref if still ours, then delete file (GUID match), drop records
```

### Recommended structure (files touched)

```
installer/
├── terminal_keys.py        # Ownership union, dispatch, two new rows, iterm2/herdr generators, defaults seam
├── registry.toml           # iterm2 and herdr-app entries with "# Verified 2026-11-2x" comment blocks
└── vendor_defaults/        # new: herdr-app keys defaults pinned at v0.1.16 (keys.json, keys.macos.json)
tests/
├── test_terminal_keys.py   # union, goldens, fixtures, drift, strip, field-list update
├── test_iterm2_profile.py  # (optional split) profile golden, keymap merge, default-profile states
├── test_herdr_app_keys.py  # (optional split) chord grammar, seed, kept-yours, strip
├── test_registry.py        # MACOS_ONLY, NO_MACOS_INTEL, counts, declarers, human set
├── test_resolve.py         # four _FIRST_METHOD tables
├── test_tool_onboarding_skill.py  # row assertions for iterm2 and herdr-app
├── e2e_herdr_app_driver.py # container-only driver
└── test_container_e2e_herdr_app.py  # host tests, stubbed ct
scripts/container-e2e-verify.sh     # cmd_herdr_app + usage + dispatcher line
scripts/e2e-residue-allowlist.txt   # herdr-core and hc entries (see Pitfall 9)
.claude/skills/tool-onboarding/SKILL.md  # two table rows
```

`installer/vendor_defaults/` is a suggestion: hatchling packages everything under `installer/` (`[tool.hatch.build.targets.wheel] packages = ["installer"]`, `pyproject.toml:16-17`), and the precedent for a non-Python data file read by path is `installer/patches/kickstart-no-lsp.patch` read through `Path(__file__).parent / "patches" / ...` [VERIFIED: installer/post_install.py:139].

### Pattern 1: The typed union and the dispatch

**What:** keep `OwnedRegion` as is, add two frozen dataclasses, retype the field, branch once per entry point.
**When:** every entry point (`apply_terminal_keys`, `terminal_keys_pending`, `strip_terminal_keys`) and `_render` (the `Writes` text concatenation at `installer/terminal_keys.py:143-161` only makes sense for regions).

```python
# Sketch; names are discretion (D-01 "name open").
@dataclass(frozen=True)
class WholeFile:
    """The whole file is the installer's; proof is the created record plus this GUID (31 D-02)."""
    guid: str

@dataclass(frozen=True)
class OwnedKeys:
    """Two-level keys the installer added to a JSON file the app owns (31 D-01)."""
    seed: Callable[[str], str]  # platform_os -> pinned vendor default text (31 D-15)

Ownership = OwnedRegion | WholeFile | OwnedKeys

def apply_terminal_keys(row, tool_id, platform_os, home, environ, *, skip_recorded):
    if isinstance(row.ownership, WholeFile):
        return _apply_whole_file(row, row.ownership, tool_id, platform_os, home, environ,
                                 skip_recorded=skip_recorded)
    if isinstance(row.ownership, OwnedKeys):
        return _apply_owned_keys(...)
    ...  # existing body, untouched, now narrowed to OwnedRegion
```

The three region rows' tests must pass unchanged; that is the proof the dispatch did not move them.

### Pattern 2: Pure generators plus recorded state

**What:** every macOS behavior is a pure function with a golden that runs on Linux and macOS CI.
- `iterm2_profile(guid, parent_guid: str | None, merged_map: Mapping[str, Mapping[str, object]], colors) -> str` returns `json.dumps({"Profiles": [profile]}, sort_keys=True, indent=2, ensure_ascii=False) + "\n"` (D-02).
- `default_profile_commands(before: str | None, ours: str) -> tuple[tuple[str, ...], ...]` and `restore_commands(recorded: str | None, current: str | None, ours: str)`: pure, four golden states (D-18).
- `herdr_keys_plan(platform_os, text) -> (new_text, written, conflicts, notes)`.

**Recommendation (discretion):** record what apply decided (previous default GUID or "none set", and the merged parent rows) in the iTerm2 records at apply time, and let the status pass render from the record. Then the status pass needs no `defaults export` (only the D-03 `defaults read` when the file is gone), and the render is deterministic. A parent-keymap change after install is then the user's business until a reconfigure, which matches the "a reconfigure re-applies it" rule.

### Pattern 3: One host seam, stubbed for every test

```python
# installer/terminal_keys.py — same shape as wezterm_show_keys (terminal_keys.py:274-281)
def iterm2_defaults(argv: Sequence[str]) -> str:
    """The `defaults` seam that tests replace in tests/conftest.py."""
    return run_output(["/usr/bin/defaults", *argv], timeout=20)

# tests/conftest.py — same shape as no_wezterm_show_keys (conftest.py:122-130)
@pytest.fixture(autouse=True)
def no_iterm2_defaults(monkeypatch):
    def unavailable(argv): raise CommandError(list(argv), 127, detail="no defaults in tests")
    monkeypatch.setattr(terminal_keys, "iterm2_defaults", unavailable)
```

`run_output` and `CommandError` are already imported in `terminal_keys.py` (`from installer.run import CommandError, run_output`, line 15). `defaults read com.googlecode.iterm2 "Default Bookmark Guid"` exits non-zero when the key is absent: the seam caller must map that to "none set" (assumed behavior; see A3).

### Anti-Patterns to Avoid
- **Attribute access through the union** (`row.ownership.region` outside the region branch): pyright strict rejects it, and it hides a missing branch.
- **Folding `Writes` text into a JSON file:** `_render` concatenates `snippet` strings with `"\n\n"` [VERIFIED: installer/terminal_keys.py:145-152]. For the iTerm2 row declare `same_directory=Writes(...)` (the KEYS-04 declaration the completeness test checks) and let the profile generator emit `"Custom Directory": "Recycle"` exactly when the declaration is `Writes`; skip `_render`'s concatenation for non-region rows.
- **Treating a missing herdr `keys.json` as an empty object:** an `OwnedKeys` file that holds only our key turns off every default shortcut (D-15).
- **Calling `defaults` on Linux or in tests:** CI has no `/usr/bin/defaults`; probed `command -v defaults` → absent on this host.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON key insert/remove keeping formatting | A new splicer | `agent_settings.insert_key` / `remove_key` | Handles one-line objects, comma placement, created parent, re-parse guard; refuses an empty file (`"empty file: there is no object to insert into"`, `agent_settings.py:298-299`) |
| "Still holds our value?" | Ad hoc `==` | `key_held` / `same_value` | `same_value` rejects `1 == True` and compares types [VERIFIED: agent_settings.py:117-137] |
| Atomic, race-safe write | `open(...).write` | `write_if_unchanged(path, before, text)` | Raises `SettingsChanged` if the file moved under us; follows symlinks to the real target [VERIFIED: agent_settings.py:556-569] |
| Created-directory cleanup | `rmtree` | `missing_dirs` + `remove_created_dirs` | Never removes outside HOME or a non-empty dir [VERIFIED: agent_settings.py:584-607] |
| XDG resolution | String joins | `xdg_config_home`, `xdg_data_home` | Empty-string env handled as unset |
| Plist parsing | Regex over XML | `plistlib.loads(output.encode())` | Handles `<data>`, `<real>`, nested dicts |
| Profile GUID | `uuid4()` at runtime | A fixed constant generated once at plan time | D-02: the GUID is the ownership proof, it must not change between runs |

## Common Pitfalls

### Pitfall 1: Uninstalling iTerm2 from inside iTerm2 kills the restore
**What goes wrong:** `brew uninstall --cask iterm2` runs the cask's `quit: com.googlecode.iterm2`; if the installer runs in an iTerm2 window, that window closes, the installer gets SIGHUP, and `_after_removal` (which holds the restore and the file delete) never runs. The preference may then name a deleted profile, or iTerm2's own fallback (Pitfall 2) wins.
**Why:** strip runs after the manager removal by design (D-11).
**How to avoid:** detect that the installer runs inside iTerm2 (iTerm2 sets `TERM_PROGRAM=iTerm.app` [ASSUMED]) and either hand off the iTerm2 removal ("run the uninstall from another terminal") or restore the preference before the cask removal when inside iTerm2. This is a design decision the CONTEXT does not make (D-19 only lists it as a UAT line): raise it with the owner.
**Warning signs:** a UAT where the installer window disappears mid-removal.

### Pitfall 2: A running iTerm2 rewrites the default when our profile disappears
**What goes wrong:** deleting our file while iTerm2 runs removes the dynamic profile; because it was the in-memory default, iTerm2 calls `setDefaultByGuid` with its first profile and writes that GUID to the preferences, overwriting a restore done a moment earlier.
**Evidence:** [VERIFIED: v3.7.8 ProfileModel.m:601-603,617-619,910-919].
**How to avoid:** strip only after the cask quit iTerm2 (D-11 order holds), and treat "iTerm2 is running" during a strip as a reported `partial` rather than a silent success. A `defaults write` while iTerm2 runs is safe but only takes effect at the next launch (the in-memory default is not re-read) [ASSUMED from the code path; UAT line].

### Pitfall 3: The profile keyboard map replaces the parent's whole map
**What goes wrong:** a dynamic profile's top-level keys override the parent's entirely: `profileByMergingProfile` copies child keys over parent keys with no deep merge [VERIFIED: v3.7.8 iTermDynamicProfileManager.m:680-691]. Writing only three rows erases the user's own key mappings.
**How to avoid:** D-09's merge. Compare keystrokes by (character, modifier flags) across the 2-, 3- and 4-part spellings, since the parent's map is likely 4-part (Pitfall 4). Mask flags to the four modifier bits when comparing (shift 0x20000, control 0x40000, option 0x80000, command 0x100000) [ASSUMED mask; the preset rows carry 0x280000 = option plus numeric-pad 0x200000].

### Pitfall 4: A parent that is itself a dynamic profile
**What goes wrong:** the previous default may be another dynamic profile; its keyboard map lives in another file in `DynamicProfiles/`, not in the `New Bookmarks` array of the exported preferences, so D-09's merge finds nothing to merge.
**How to avoid:** if the previous default GUID is not in `New Bookmarks`, write no parent map rows and report `iterm2: partial: your previous default is a Dynamic Profile; its key mappings were not merged` (wording discretion). The Parent GUID still works (dynamic profiles load in filename order; a parent must load first, docs "Parent Profiles" [CITED: iTerm2 Dynamic Profiles docs]) — `tools-installer.json` sorts after most names but not all. Flag as an open question.

### Pitfall 5: `Use Separate Colors for Light and Dark Mode` false switches every color to the plain keys
**What goes wrong:** with `false`, iTerm2 reads the plain `Ansi N Color` keys, which the profile inherits from the parent; a parent customized only through `(Dark)`/`(Light)` keys looks different after the switch. Also `Cursor Text Color` and `Selected Text Color` stay inherited and may clash with dark green. Keys exist in `DefaultBookmark.plist`: `'Bold Color', 'Cursor Color', 'Cursor Text Color', 'Foreground Color', 'Background Color', 'Selected Text Color', 'Selection Color', 'Use Separate Colors for Light and Dark Mode'` [VERIFIED: v3.7.8 plists/DefaultBookmark.plist, parsed with plistlib].
**How to avoid:** D-10 locks five entries; record the risk as a Mac UAT line ("colors in light and dark mode").

### Pitfall 6: `LoadPrefsFromCustomFolder`
iTerm2 can load preferences from a custom folder at launch (`kPreferenceKeyLoadPrefsFromCustomFolder = @"LoadPrefsFromCustomFolder"` [VERIFIED: v3.7.8 iTermPreferences.m:52]); a `defaults write` to the domain is then overwritten at launch. D-11 already skips with a `partial` note.

### Pitfall 7: Seeding the herdr default freezes future default updates
`load_text` rewrites `keys.json` only when it is missing or byte-identical to a shipped original (`if text != defaults && originals.contains(&text.as_str())`) [VERIFIED: herdr-app v0.1.16 src/keys.rs:175-189]. Our seeded-plus-key file is neither, so app updates never refresh it. D-15's install note covers it. Recommendation: on strip, when the installer created the file (created record) and the document after removing our keys equals the pinned vendor default (`same_value`), delete the file so the app re-seeds and migration resumes; otherwise keep it.

### Pitfall 8: An empty or invalid `keys.json`
The app does not re-seed an empty file (`read_to_string` succeeds, parsing fails) and writes the reason to `keys.error`, keeping the last good bindings [CITED: herdr-app v0.1.16 defaults/AGENTS.md:50-53]. `insert_key` refuses an empty file. SPEC's edge row says "an existing empty file is extended". Recommend treating whitespace-only like missing (seed plus key) and an unparseable file as a refusal (`herdr-app keys not changed: the file does not parse; left as it is`). Open question O3.

### Pitfall 9: `make e2e --all` now runs the herdr-app script
`pass1` runs `setup.py --all --yes` and `pass2` uninstalls everything and checks residue against `scripts/e2e-residue-allowlist.txt`, which has no herdr entries (`rg herdr scripts/e2e-residue-allowlist.txt` → nothing). After removal, `.local/bin/herdr-core` and `.local/bin/hc` stay by design (SPEC R3, `install.sh:139-143`; core installer `bin=${HC_INSTALL_DIR:-$HOME/.local/bin}` and `ln -s herdr-core "$bin/hc"`). The `--all` pass also needs network to `releases.herdr.dev`, and `herdr-app --version` (the engine's generic smoke for a script method, `executors.method_smoke_argv` default `("--version",)` [VERIFIED: installer/executors.py:51-58], run for non-download kinds [VERIFIED: installer/engine.py:43-73]) needs `libxcb.so.1` and `libxkbcommon.so.0` (Pitfall 10).
**How to avoid:** add two allowlist entries with reasons (`.local/bin/herdr-core  # nested vendor core install by herdr-app's install.sh, outside herdr-app paths (SPEC R3)`, same for `hc`), and make sure the e2e image has the two libraries (or accept a reported smoke failure in pass1). Check `cmd_all` before planning.

### Pitfall 10: The Linux binary links X11/xkb libraries
`readelf -d herdr-app/herdr-app` from the v0.1.16 linux-x86_64 tarball (sha256 matched `282d2632...`): `NEEDED libxcb.so.1, libxkbcommon.so.0, libgcc_s.so.1, libm.so.6, libc.so.6, ld-linux-x86-64.so.2` [VERIFIED: tarball inspected, not executed]. A minimal `fedora:latest` lacks the first two, so the smoke fails there. The container target's root stage installs `libxcb libxkbcommon` (package names [ASSUMED]); a desktop host has them.

### Pitfall 11: Shared desktop caches
`install.sh` runs `update-desktop-database "$data/applications"` when present (`install.sh:103`), which writes `~/.local/share/applications/mimeinfo.cache`, a file shared with every other desktop entry. It is not ours to remove. On a host with `desktop-file-utils` it appears after install; the container driver must allow it (do not add it to `paths`).

### Pitfall 12: Pipes and empty directories in the container driver (phase 30 lessons)
Phase 30's driver hung 120 s reading through a pipe a child kept open and now captures through files; it also had to allow exactly three standard empty directories after removal (`".local/share/applications/", ".local/share/icons/", ".local/share/tools-installer/"`) [VERIFIED: tests/e2e_ghostty_driver.py:41-47; .planning/phases/30-onboard-ghostty/30-05-SUMMARY.md:61-63]. herdr-app adds nested icon dirs (`.local/share/icons/hicolor/scalable/apps/`): the `leftovers()` matcher treats an allowed entry as a prefix both ways [VERIFIED: tests/e2e_ghostty_driver.py:241-251], but the empty-directory allowance is an exact set, so list the nested ones too. Rootless podman cannot FUSE-mount (irrelevant here: no AppImage). The tuning and created records (`terminal-tuning-herdr-app`, `terminal-herdr-app-created`) must not be counted as residue while installed and must be gone after removal (phase 30's first-run defect).

## Code Examples

### iTerm2 profile shape (values verified; GUID and RGB are placeholders)
```json
{
  "Profiles": [
    {
      "Background Color": {"Alpha Component": 1, "Blue Component": 0.0, "Color Space": "sRGB", "Green Component": 0.0, "Red Component": 0.0},
      "Custom Directory": "Recycle",
      "Dynamic Profile Parent GUID": "<recorded previous default, omitted when none>",
      "Guid": "<fixed installer GUID>",
      "Keyboard Map": {
        "0x6b-0x100000": {"Action": 11, "Text": "0x0c"},
        "0xf702-0x280000": {"Action": 10, "Text": "b"},
        "0xf703-0x280000": {"Action": 10, "Text": "f"}
      },
      "Name": "tools-installer",
      "Use Separate Colors for Light and Dark Mode": false
    }
  ]
}
```
Verbatim sources for every value: `#define KEY_DEFAULT_GUID @"Default Bookmark Guid"`, `#define KEY_CUSTOM_DIRECTORY @"Custom Directory"  // values are Yes, No, Recycle, Advanced`, `#define KEY_USE_SEPARATE_COLORS_FOR_LIGHT_AND_DARK_MODE @"Use Separate Colors for Light and Dark Mode"`, `#define KEY_KEYBOARD_MAP @"Keyboard Map"`, `#define KEY_DYNAMIC_PROFILE_PARENT_GUID @"Dynamic Profile Parent GUID"`, `#define KEY_DYNAMIC_PROFILE_REWRITABLE @"Rewritable"` [VERIFIED: v3.7.8 ITAddressBookMgr.h:38,54,140,319,362,364]; `KEY_ACTION_ESCAPE_SEQUENCE = 10,` `KEY_ACTION_HEX_CODE = 11,` [VERIFIED: v3.7.8 iTermKeyBindingAction.h:50-51]; preset rows `Terminal.app Compatibility 0xf702-0x280000 {'Action': 10, 'Text': 'b'}` and `0xf703-0x280000 {'Action': 10, 'Text': 'f'}` [VERIFIED: v3.7.8 plists/PresetKeyMappings.plist]; factory `Custom Directory 'No'`, `Use Separate Colors for Light and Dark Mode True`, `Option Key Sends 0`, `Right Option Key Sends 0` [VERIFIED: v3.7.8 plists/DefaultBookmark.plist]; color dict keys `'Alpha Component', 'Blue Component', 'Color Space': 'sRGB', 'Green Component', 'Red Component'` [VERIFIED: same plist, `Foreground Color`]. Folder: `// Returns ~/Library/Application Support/iTerm2/DynamicProfiles` [VERIFIED: v3.7.8 iTermDynamicProfileManager.m:261-268]. `"0x6b-0x100000"` (k = 0x6b, command = 0x100000) and `"Text": "0x0c"` for action 11 are [CITED: CONTEXT D-07, analyzer read]; the Mac UAT confirms (D-19).

### herdr-app keys row values
Linux vendor default holds `"ctrl-shift-k": "mod.open:picker",` in `global` [VERIFIED: herdr-app v0.1.16 defaults/keys.json:51]; the macOS default has no `cmd-k` anywhere and its `terminal` section holds `"alt-left": "send:\u001bb",` and `"alt-right": "send:\u001bf",` [VERIFIED: v0.1.16 defaults/keys.macos.json]. Sections: `"global" => Ok("Herdr".into()), "terminal" => Ok("Terminal".into()),` plus `mod:` and `layout:` prefixes [VERIFIED: v0.1.16 src/keys.rs:119-130]. Path: `crate::mods::app_dir().join("keys.json")` [VERIFIED: src/keys.rs:111-113] with `env("HERDR_APP_HOME").unwrap_or_else(|| env("XDG_CONFIG_HOME").unwrap_or_else(|| home().join(".config")).join("herdr-app"))` [VERIFIED: v0.1.16 src/mods.rs:62-65] (note: `HERDR_APP_HOME` is the folder itself, no `herdr-app` suffix). Pinned default hashes: `d1831fe2e9a685abf5fd95c156f4425fcbc17f81919163955a3688a166ea269f  defaults_keys.json`, `8728a5190aa2ef1609c08c0cb49cf31dd74ab7018944b6453d9f371570d023c0  defaults_keys.macos.json` (74 and 75 lines) [VERIFIED: sha256sum this session].

`insert_key(text, "json", ("terminal", "ctrl-shift-k"), "send:\x0c")` places the member first in `terminal` with the indentation of the existing first member and writes `"send:\f"` (`json.dumps(value, ensure_ascii=False)` [VERIFIED: agent_settings.py:255-256]). The app parses `\f` (serde_json). Golden G4 pins those bytes.

### Registry entry shapes
```toml
[[tool]]
id = "iterm2"
name = "iTerm2"
category = "terminal"
priority = "P3"
audience = "human"
tier = "user"
verified = 2026-11-2x
desc = "macOS terminal emulator; the installer adds its own default profile"
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "cask"
os = ["macos"]
cask = "iterm2"
app = "iTerm.app"
min_os_version = "13"

[[tool]]
id = "herdr-app"
name = "Herdr"
category = "terminal"
priority = "P3"
audience = "human"
tier = "user"
config_paths = ["~/.config/herdr-app"]
post_install = ["apply_terminal_tuning"]
[[tool.method]]
kind = "script"
os = ["debian", "fedora", "arch"]
url = "https://releases.herdr.dev/app/install.sh"
shell = "sh"
bin_dir = "~/.local/bin"
paths = ["~/.local/share/herdr-app/", "~/.local/bin/herdr-app", "~/.local/share/applications/herdr-app.desktop", "~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg"]
[[tool.method]]
kind = "cask"
os = ["macos"]
arch = ["arm64"]
cask = "herdr-app"
app = "Herdr.app"
```
Allowed keys: `"script": frozenset({"url", "shell", "bin_dir", "env", "detect_path", "version_file", "args", "smoke_argv", "refuses_existing", "paths", "remove", "update", "writable_prefix", "latest_npm"})` and `"cask": frozenset({"cask", "app", "min_os_version", "smoke_argv"})` [VERIFIED: installer/model.py:44-60,109]; `arch` is a method-level key read separately (`raw_arch = entry.get("arch", [])`, model.py:636). `cmd` defaults to the id (`cmd=row.get("cmd", row["id"])`, model.py:866): `iterm2` has no binary, presence comes from the bundle (`if any((root / app).is_dir() for root in roots)`, status.py:201-210), and the engine smoke finds no `iterm2` on PATH and skips (engine.py:51-73). `audience = "human"` and `priority = "P3"` are discretion (matching ghostty). The install paths are verified against `install.sh:82-91` (`data=${XDG_DATA_HOME:-$HOME/.local/share}`, `home="$data/herdr-app"`, `ln -sfn "$home/herdr-app" "$bin/herdr-app"`, `cp ... "$data/icons/hicolor/scalable/apps/herdr-app.svg"`, `cat > "$data/applications/herdr-app.desktop"`) [VERIFIED: install.sh fetched 2026-11-21].

## Registry and test touch list

| Place | Change | Evidence of the current pin |
|-------|--------|-----------------------------|
| `tests/test_registry.py` `MACOS_ONLY` | add `"iterm2"` | `MACOS_ONLY = {"gnu-bash"}` (798) |
| `tests/test_registry.py` new `NO_MACOS_INTEL` | `{"herdr-app"}`, allowed only on macos/amd64, plus honesty test | see R9 |
| `tests/test_registry.py` `_POST_15_3_HUMAN_TOOLS` | add both (if `audience = "human"`) | set at 278-283 ends with `"neovim",  # Phase 24.1` |
| `test_registry_audience_distribution_is_pinned` | `"human": 29` → 31 | 301-305 |
| `test_registry_tier_distribution_is_pinned` | `"user": 50` → 52 | 1267-1271 |
| post-install declarers test | add `"iterm2"`, `"herdr-app"` to the declarer set | 1369-1379 |
| `test_native_package_manager_rows_declare_their_owner_probes` | none (no native methods; no `owner_probes`) | 2394-2420 |
| Entry-shape tests | one per entry, like phase 30's `ghostty` tests (2256-2380) | — |
| `tests/test_resolve.py` `_FIRST_METHOD` | `iterm2`: macos `"cask"`, fedora-mutable/fedora-immutable/debian `None`; `herdr-app`: macos `"cask"` (fixture is arm64), the three Linux fixtures `"script"` | tables at 560, 649, 738, 827; `_FIXTURES` at 549-554 (macos fixture `arch="arm64"`) |
| `tests/test_terminal_keys.py` | `set(TERMINAL_KEYS) == {...}` (255) and `missing_rows(..., {}) == {...}` (290) gain two ids; field-list test (2169-2184) gains the hook field | — |
| `tests/test_tool_onboarding_skill.py` | table drift requires a row per terminal/editor id; every `TERMINAL_KEYS` row's clear cell starts with `written` (603-625); add a row test per new entry like `test_ghostty_row_records_what_is_proven` (642-655) | — |
| `.claude/skills/tool-onboarding/SKILL.md` | two rows in "#### Closed per-terminal table" (rows at 211-219; columns id, config path, (a) shell, (b) word navigation, (c) clear, (d) same directory, reload) | TEST_READ covers `.claude/*` |
| `scripts/container-e2e-verify.sh` | `cmd_herdr_app`, usage text, `herdr-app) cmd_herdr_app "$@" ;;` | — |
| `scripts/e2e-residue-allowlist.txt` | `herdr-core`, `hc` entries (Pitfall 9) | — |
| `docs/` | nothing found for Ghostty in phase 30 (`rg -l ghostty docs/` → none) | — |

Docs-only/TEST_READ: `devtools/docs_only.py` treats `.planning/*` and `*.md` as docs unless they match `TEST_READ = ("AGENTS.md", "README.md", ".claude/*", ".github/*", "docs/*", "scripts/*", "tests/*", ...)` [VERIFIED: devtools/docs_only.py:20-36]. A phase 31 test that reads a `.planning` file (for example a UAT or VERIFICATION file) must add that path to `TEST_READ` in the same commit; prefer tests that read only code, the registry and the skill.

## Container target `herdr-app` (D-17)

Shape (from `cmd_ghostty`, scripts/container-e2e-verify.sh:2979-3005): parse `--keep-image`; `LANDING_CONTAINER_NAME="tools-installer-e2e-herdr-app-$$"`; `IMAGE="$LANDING_IMAGE"`; `DISTRO=fedora`; `LANDING_DRIVER_MODULE=tests.e2e_herdr_app_driver`; `PHASE_DIR="$REPO_ROOT/.e2e-artifacts/container-herdr-app"`; `trap landing_teardown EXIT`; `landing_bootstrap`; `landing_stage herdr-app-root herdr_app_root_setup` (dnf install the two X libraries); then verdict steps. Suggested verdict steps (all collected, like `cmd_bun_lifecycle`):

1. `app-then-herdr`: install herdr-app, hash `~/.local/bin/herdr` (absent) and `~/.config/herdr`; install herdr; remove herdr-app; herdr's binary and config hashes unchanged.
2. `herdr-then-app`: the reverse order in a fresh HOME (or after a full clean).
3. `keys`: after the herdr-app install, `keys.json` holds the seeded default plus `"ctrl-shift-k": "send:\f"` in `terminal`; `herdr-app --version` prints `herdr-app 0.1.16`; uninstall strips only the owned key.
4. `residue`: removal leaves only allowlisted paths; `herdr-core` and `hc` reported as expected leftovers.

What the host tests with a stubbed `ct` can prove (pattern: tests/test_container_e2e_herdr_keys.py:40-117 extracts functions from the script and runs them with a `ct` stub writing to a `calls` file): the container name is PID-scoped, the teardown removes exactly that container (and image unless `--keep-image`), the root setup installs the libraries, every step runs as the tester, a failing step does not stop the others, and the dispatcher routes `herdr-app`. They cannot prove the vendor script's footprint, the network, or real bytes; that is the container run's job, recorded in the registry `# Verified` comment.

## Goldens per OS

| ID | Golden | Generator input | Runs on |
|----|--------|-----------------|---------|
| G1 | iTerm2 profile bytes, no previous default | `platform_os="macos"`, parent None, no parent map | Linux and macOS CI |
| G2 | iTerm2 profile with parent GUID and merged parent map, one clash kept (`partial: kept yours`) | fixture `defaults export` plist | both |
| G3 | Default-profile before/after commands for four states (GUID set, none set, already ours, user-changed after install) | fake seam | both |
| G4 | herdr-app Linux keys: seeded v0.1.16 `keys.json` + `"ctrl-shift-k": "send:\f"` | missing file, `platform_os="fedora"` | both |
| G5 | herdr-app macOS keys: seeded `keys.macos.json` + `"cmd-k": "send:\f"` | missing file, `platform_os="macos"` | both |

A sha256 test pins the two vendor default files to the upstream v0.1.16 hashes above, so a later bump is a deliberate edit.

## State of the Art

| Old approach | Current approach | When | Impact |
|--------------|------------------|------|--------|
| iTerm2 key map keys `0xCHAR-0xFLAGS` | 4-part `0xCHAR-0xFLAGS-0xKEYCODE-0xVERSION`; 2- and 3-part still matched | present at v3.7.8 | Writing 2-part works; parent maps read back from prefs are mostly 4-part (merge must parse all three) |
| herdr-app keys `keys.json`/`keys.macos.json` as user files | One user `keys.json`; `keys.macos.json` is only the compiled-in macOS default | v0.1.x | D-14 |

## Python 3.12 vs 3.15

No stdlib behavior this phase relies on is known to differ: `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` output, `plistlib.loads`, `dataclasses`, `isinstance` on PEP 604 unions (3.10+). Pyright runs at `pythonVersion = "3.11"` (pyproject.toml:45), so do not use 3.12+ syntax (`type X = ...` aliases, PEP 695 generics). [ASSUMED for 3.15: not tested here.]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | iTerm2 sets `TERM_PROGRAM=iTerm.app` in its sessions | Pitfall 1 | The inside-iTerm2 detection misses; mitigated by also checking `ITERM_SESSION_ID` and by the UAT |
| A2 | Comparing iTerm2 keystrokes on the four modifier bits (mask 0x1E0000) matches iTerm2's own matching | Pitfall 3 | A clash with a parent row goes unnoticed or a non-clash is reported; Mac UAT |
| A3 | `defaults read <domain> <key>` exits non-zero when the key is absent, and `defaults export <domain> -` prints XML to stdout | Pattern 3 | The "none set" state is misread; a fake-runner test fixes the contract, the Mac UAT confirms |
| A4 | A `defaults write` while iTerm2 runs takes effect at next launch and is not overwritten unless iTerm2's default changes | Pitfall 2 | Install from inside a running iTerm2 shows the old default until restart; UAT line |
| A5 | `"0x6b-0x100000"` is Cmd+K and action 11 with `"Text": "0x0c"` sends Ctrl+L | Code Examples | Cmd+K does nothing or clears via the menu item; Mac UAT (D-19) |
| A6 | Fedora package names `libxcb` and `libxkbcommon` provide the two NEEDED libraries | Pitfall 10 | The container smoke fails until the names are fixed (cheap to discover in the run) |
| A7 | No 3.12-vs-3.15 stdlib difference affects the generators | Python 3.12 vs 3.15 | A golden differs only on CI; caught on the first push |
| A8 | `audience = "human"` and `priority = "P3"` for both entries | Registry | Count pins change differently; owner preference |
| A9 | Dark-green palette values | D-10 | Owner rejects colors at UAT; values are discretion until named |

## Open Questions (RESOLVED)

Each recommendation below was adopted by the plans and the orchestrator decisions (31-CONTEXT amendments, 2026-11-21).

1. **Uninstalling iTerm2 from inside iTerm2 (Pitfall 1).** What we know: the cask quits iTerm2 before removal, and strip runs after removal. What's unclear: whether the owner prefers a hand-off ("run the uninstall from another terminal") or a pre-removal restore when running inside iTerm2. Recommendation: hand off; it never leaves a half-restored state.
2. **Parent that is a dynamic profile (Pitfall 4).** Recommendation: set the Parent GUID, merge nothing, report `partial`.
3. **Empty `keys.json` (Pitfall 8).** SPEC edge says "extended"; the app semantics say an empty file has no defaults. Recommendation: seed like a missing file, refuse an unparseable one.
4. **Strip of a created `keys.json` (Pitfall 7).** Recommendation: delete it when what remains equals the pinned vendor default, so the app's default migration resumes.
5. **`herdr-app` record format.** D-01 says "the record stores the owned paths and the values written". Recommendation: the `terminal-tuning-herdr-app` record holds JSON (`{"keys": [["terminal", "ctrl-shift-k", "send:\f"]]}`) instead of `"written\n"`; its existence keeps the "applied" meaning every other row uses.
6. **D-16 alias correction (R12)** and **D-07 message correction (R10)**: both "own reasoning"; the plan applies the source-backed version and lists both for owner confirmation with 31 D-08 and D-12's flag.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| podman | container target `herdr-app` | ✓ | 6.1.3 (`CONTAINER_TOOL=podman`) | — |
| network to releases.herdr.dev | container target, `--all` e2e | ✓ (fetched install.sh, latest.json, tarball) | — | none (the target needs it) |
| gh (authenticated) | upstream source reads | ✓ | 2.101.0 | — |
| uv / Python | tests | ✓ | uv 0.11.28, Python 3.12.12 | — |
| `/usr/bin/defaults` | iTerm2 hook at runtime | ✗ on Linux (expected) | — | seam stub in tests; real only on a Mac (UAT) |
| A Mac with iTerm2 | D-19 UAT lines | ✗ here | — | deferred to the owner's Mac |
| `/tmp` space | container and tests | ✓ 5% used of 16G | — | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-xdist and coverage (`[tool.pytest.ini_options]` in pyproject.toml) |
| Config file | `pyproject.toml`, `tests/conftest.py` (autouse seams, HOME sandbox) |
| Quick run command | `uv run pytest tests/test_terminal_keys.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_container_e2e_herdr_app.py --no-cov -q` |
| Full suite command | `make test` (once per plan), `make validate` (once per plan) |
| Container proof | `scripts/container-e2e-verify.sh herdr-app` (orchestrator only, disposable container) |

Baseline: `tests/test_terminal_keys.py tests/test_tool_onboarding_skill.py tests/test_resolve.py` pass on this tree (run this session with `--no-cov`, scratch `TMPDIR`, cleaned).

### Phase Requirements → Test Map
| Req | Behavior | Type | Automated Command | File Exists? |
|-----|----------|------|-------------------|-------------|
| NTERM-02 | `iterm2` resolves only on macOS (≥13) and is unavailable on Linux; in `MACOS_ONLY` | unit | `uv run pytest tests/test_registry.py tests/test_resolve.py -k "iterm2 or macos_only or first_method" --no-cov -q` | ✅ files, ❌ new cases |
| NTERM-02 | Profile golden G1/G2 bytes; key map holds exactly Cmd+K, the two Option rows and merged parent rows; no `Option Key Sends` key; `Custom Directory` present iff `Writes` | unit/golden | `uv run pytest tests/test_terminal_keys.py -k iterm2 --no-cov -q` | ❌ Wave 0 |
| NTERM-02 | Default-profile G3: install sets, uninstall restores exact previous value incl. "none set"; user change kept; `LoadPrefsFromCustomFolder` skip | unit (fake seam) | same, `-k default_profile` | ❌ Wave 0 |
| NTERM-02 | Foreign file refused, never overwritten; drift rewrite; deleted file with default still ours reads `≈`; strip deletes on GUID match | unit (scratch HOME) | same, `-k "iterm2 and (foreign or drift or strip or pending)"` | ❌ Wave 0 |
| NTERM-03 | `herdr-app` distinct id; script `paths` exactly the four; cask `arch = ["arm64"]`; `NO_MACOS_INTEL` honesty; Intel fixture unavailable | unit | `uv run pytest tests/test_registry.py -k "herdr_app or no_macos_intel" --no-cov -q` | ❌ Wave 0 |
| NTERM-03 | Keys goldens G4/G5; user binding (normalized chord, shuffled sections) kept with `herdr-app: partial: kept yours`; install note names the displaced picker; reconfigure idempotent; strip removes only owned keys still holding the recorded value | unit | `uv run pytest tests/test_terminal_keys.py -k herdr_app --no-cov -q` | ❌ Wave 0 |
| NTERM-03 | GPUI chord grammar normalization (cmd/super/win, secondary per OS, uppercase key, trailing `-`, multi-stroke first keystroke) | unit | same, `-k chord` | ❌ Wave 0 |
| NTERM-03 | `herdr-app:` prefixed warning never routed to the `herdr` row | unit | `uv run pytest tests/test_version_status.py -k herdr_app --no-cov -q` | ❌ Wave 0 |
| NTERM-03 | Container orchestration: PID-named box, root libs stage, steps as tester, teardown by exact name | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_herdr_app.py --no-cov -q` | ❌ Wave 0 |
| NTERM-03 | Install/removal leaves herdr's binary and `~/.config/herdr` byte-identical, both orders; residue only allowlisted | container | `scripts/container-e2e-verify.sh herdr-app` | ❌ Wave 0 |
| Both (KEYS-02/04) | Completeness and `same_directory` tests pass with both rows; union dispatch leaves the four region rows' tests unchanged | unit | `uv run pytest tests/test_terminal_keys.py --no-cov -q` | ✅ |
| Both | Skill table rows match registry and `TERMINAL_KEYS` | unit | `uv run pytest tests/test_tool_onboarding_skill.py --no-cov -q` | ✅ (+ new row tests) |
| NTERM-02 | Live load, default switch, Cmd+K, Option+arrows with Spanish `@`, colors, Recycle, restore from inside iTerm2 | manual | Mac UAT (D-19) | n/a |

### Sampling Rate
- **Per task commit:** the quick run command above, narrowed to the edited files.
- **Per plan:** `make validate` and `make test` once each.
- **Phase gate:** full suite green, the container target PASS (orchestrator), then `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] iTerm2 tests (profile goldens, default-profile states, foreign/drift/strip/pending) — new cases in `tests/test_terminal_keys.py` or `tests/test_iterm2_profile.py`
- [ ] herdr-app keys tests and chord grammar — new cases or `tests/test_herdr_app_keys.py`
- [ ] autouse `defaults` seam stub in `tests/conftest.py`
- [ ] `tests/e2e_herdr_app_driver.py` and `tests/test_container_e2e_herdr_app.py`
- [ ] fixture plist for `defaults export` (inline string in the test)
- No framework install needed.

## Security Domain

`security_enforcement: true`, ASVS level 1 (`.planning/config.json`).

### Applicable ASVS Categories
| Category | Applies | Control |
|----------|---------|---------|
| V2 Authentication | no | — |
| V3 Session | no | — |
| V4 Access Control | yes (filesystem) | Writes only under HOME; `missing_dirs`/`remove_created_dirs` refuse paths outside HOME; zero sudo |
| V5 Input Validation | yes | Parse user `keys.json` and the exported plist defensively (size cap via `read_capped`, `parse_settings` errors become refusals); validate every written text by re-parse (`_guarded`, row `validate`) |
| V6 Cryptography | no new | install.sh verifies the tarball sha256 from `latest.json` (vendor-side) |
| V12 Files | yes | Compare-before-commit (`write_if_unchanged`), realpath for symlinked targets, refuse foreign files, delete only on GUID match |
| V14 Config / supply chain | yes | Vendor `install.sh` and its nested unchecked core installer run only for users who pick the entry, and only in containers in tests |

### Known Threat Patterns
| Pattern | STRIDE | Mitigation |
|---------|--------|------------|
| Symlink at `DynamicProfiles/tools-installer.json` or `keys.json` pointing elsewhere | Tampering | `read_settings`/`write_if_unchanged` resolve the real target; refuse when the resolved target is not under HOME (verify `_below_home` is applied for the whole-file delete) |
| Foreign file with our name | Tampering | GUID plus created-record proof; refuse otherwise (D-02) |
| Command injection via `defaults` arguments | Elevation | argv list through `run_output`, no shell; values are constants or the recorded GUID (validate the recorded GUID matches a UUID-like pattern before passing it) |
| Nested `curl \| sh` (herdr-core) | Spoofing/Tampering | Documented in `# Verified`; outside our receipt; SPEC R3 accepts it |
| Malicious `keys.json` content (huge file, deep nesting) | DoS | `read_capped`; two-level paths only |
| Race with the app rewriting `keys.json` | Tampering | `SettingsChanged` on mismatch → refusal, nothing written |

## Sources

### Primary (HIGH confidence)
- In-repo code read this session: `installer/terminal_keys.py`, `installer/terminal_regions.py`, `installer/agent_settings.py`, `installer/post_install.py`, `installer/app.py`, `installer/version_status.py`, `installer/receipts.py`, `installer/resolve.py`, `installer/model.py`, `installer/status.py`, `installer/executors.py`, `installer/engine.py`, `installer/uninstall.py`, `scripts/container-e2e-verify.sh`, `tests/conftest.py`, `tests/test_terminal_keys.py`, `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_tool_onboarding_skill.py`, `tests/e2e_ghostty_driver.py`, `tests/test_container_e2e_herdr_keys.py`, `devtools/docs_only.py`, `.claude/skills/tool-onboarding/SKILL.md`
- gnachman/iTerm2 at tag `v3.7.8` via `gh api` (2026-11-21): `sources/Settings/Profiles/ITAddressBookMgr.{h,m}`, `ProfileModel.m`, `iTermDynamicProfileManager.m`, `sources/Keyboard/iTermKeyBindingAction.h`, `iTermKeystroke.m`, `sources/AppKit/iTermApplication.m`, `sources/Settings/iTermPreferences.m`, `sources/VT100/VT100Output.m`, `plists/PresetKeyMappings.plist`, `plists/DefaultBookmark.plist`
- herdrdev/herdr-app at tag `v0.1.16` via `gh api` (2026-11-21): `src/keys.rs`, `src/mods.rs`, `src/main.rs`, `defaults/keys.json`, `defaults/keys.macos.json`, `vendor/gpui-pre/src/platform/keystroke.rs`, `vendor/gpui-pre/src/keymap/binding.rs`, `Cargo.toml`
- `https://releases.herdr.dev/app/install.sh`, `/app/latest.json`, `/core/install.sh`, `/app/0.1.16/herdr-app-linux-x86_64.tar.gz` (sha256 matched, inspected with readelf, not executed), 2026-11-21
- `https://formulae.brew.sh/api/cask/iterm2.json` and `herdr-app.json`, 2026-11-21

### Secondary (MEDIUM)
- iTerm2 Dynamic Profiles documentation (cached copy `dp37.md`, read 2026-11-19): file format, Parent GUID since 3.4.9, Rewritable, load order
- herdr-app `defaults/AGENTS.md` v0.1.16 (cached 2026-11-19): section precedence, `keys.error`, escape hatch

### Tertiary (LOW)
- `TERM_PROGRAM=iTerm.app` (training knowledge)

## Metadata

**Confidence breakdown:**
- Mechanism reconciliation: HIGH (every claim from code read this session with line numbers)
- iTerm2 file and preference facts: HIGH at source level (v3.7.8 tag), MEDIUM for runtime (Mac UAT)
- herdr-app facts: HIGH (v0.1.16 tag, live script and tarball)
- Container plan: MEDIUM (library names and the `--all` interaction need a run)

**Research date:** 2026-11-21
**Valid until:** 2026-12-05 (herdr-app ships often; re-check `latest.json` and the defaults hashes before execution)
