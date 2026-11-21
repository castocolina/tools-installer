---
phase: 31-onboard-iterm2-and-the-herdr-desktop-app
verified: 2026-11-21T06:00:00Z
status: human_needed
score: 4/4 roadmap criteria verified by automated or recorded evidence (live-Mac and desktop behavior listed as human items)
covered_files:
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-01-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-01-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-02-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-02-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-03-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-03-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-04-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-04-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-05-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-05-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-06-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-06-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-07-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-07-SUMMARY.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-08-PLAN.md
  - .planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/31-08-SUMMARY.md
  - installer/app.py
  - installer/herdr_app_keys.py
  - installer/iterm2_profile.py
  - installer/registry.toml
  - installer/terminal_keys.py
covered_digest: "v4:sha256:3b9390fc1d663e5c22a1bcfea87ed2d8470a81dcdfe5881e4a5bd073f1f5f0a6"
behavior_unverified: 0
overrides_applied: 0
gaps: []
human_verification:
  - test: "iTerm2 loads the Dynamic Profile live and it becomes the default profile, whether iTerm2 is running or not"
    expected: "The profile appears without a restart; a new window uses it"
    why_human: "Real Mac; Default Bookmark Guid and live reload behavior come from iTerm2 master source, not the 3.7.8 tag"
  - test: "Cmd+K sends 0x0c"
    expected: "Screen and scrollback clear in a zsh prompt"
    why_human: "Real keyboard and iTerm2 key handling"
  - test: "Option+Left/Right move by word; the Spanish @ still types"
    expected: "Word navigation works with Option Normal; Option+2 types @"
    why_human: "Real Mac, Spanish layout"
  - test: "Parent key-map rule: 2-, 3- and 4-part key spelling and the defaults-read absent-key message"
    expected: "Merged parent rows load; an absent Default Bookmark Guid reads as none set"
    why_human: "Needs real iTerm2 preferences"
  - test: "Colors in light and dark mode"
    expected: "Dark-green palette stays readable in both"
    why_human: "Real Mac appearance switching; owner RGB values never recorded"
  - test: "Recycle for tabs, windows and split panes"
    expected: "Each opens in the same pwd"
    why_human: "Real Mac GUI"
  - test: "Uninstall restores the previous default, including uninstall from inside iTerm2"
    expected: "Previous default (or none set) back, profile file gone"
    why_human: "Real Mac; defaults and the running app (the cask quit closes the installer's terminal)"
  - test: "herdr app cask on Apple Silicon macOS"
    expected: "Installs, launches, owned cmd-k works, ~/.config/herdr untouched"
    why_human: "Real Apple Silicon Mac"
  - test: "herdr app on a Linux desktop session"
    expected: "App launches from the menu; Ctrl+Shift+K clears in a terminal pane; uninstall leaves no residue"
    why_human: "Needs a live desktop session; the container proves files only"
---

# Phase 31: Onboard iTerm2 and the Herdr desktop app - Verification Report

**Phase Goal:** A macOS user gets iTerm2 with a ready default profile that meets the terminal defaults, and the Herdr desktop app installs on Linux and Apple Silicon macOS as its own entry with the same defaults.
**Verified:** 2026-11-21
**Status:** human_needed
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP criteria, SPEC acceptance) | Status | Evidence |
| - | ----------------------------------------- | ------ | -------- |
| 1 | iTerm2 cask on macOS only; one owned Dynamic Profile with Option+Left/Right key-map rows (Option Normal), Cmd+K clear, same directory, colors; golden on both OSes | VERIFIED (live behavior human) | `installer/registry.toml:3259-3273` (id iterm2, single `cask` method `os=["macos"]`, `min_os_version=13`, `post_install=["apply_terminal_tuning"]`, no Linux method); `installer/iterm2_profile.py:29-31` (Cmd+K `0x6b-0x100000` Action 11 Text 0x0c; Option+Left/Right `0xf702/0xf703-0x280000` Action 10 b/f), `:138` (separate light/dark colors off), `:141` (`Custom Directory = Recycle`); no `Option Key Sends` key; `tests/test_registry.py:800` `iterm2` in `MACOS_ONLY`; `tests/test_iterm2_profile.py` and `tests/test_iterm2_row.py` goldens pass (re-run) |
| 2 | Installer profile becomes default; uninstall deletes it and restores the previous default (four-state golden, incl. "none set") | VERIFIED (real Mac human) | `installer/iterm2_profile.py:20,224-264,408` (Default Bookmark Guid seam, install/restore commands, hook_restore with read-back); `installer/app.py:828-848` restores before the cask removal and refuses removal when the restore is unconfirmed; review fixes `1b5a6c5f` (read-back, kept record) pass in `tests/test_iterm2_profile.py` / `tests/test_iterm2_row.py` (both uninstall routes) |
| 3 | Herdr desktop app is a distinct entry: user-scope `install.sh` on Linux, cask on Apple Silicon macOS, unavailable on Intel; one entry never disturbs the other's binaries or `~/.config/herdr` | VERIFIED | `installer/registry.toml:3296-3319` (id `herdr-app`, script method for debian/fedora/arch with app-only `paths`, cask `arch=["arm64"]`, `config_paths=["~/.config/herdr-app"]`); `tests/test_registry.py:804` `NO_MACOS_INTEL`; `tests/test_herdr_app_row.py` pass; real container run `herdr-app-container: PASS (2026-11-21; transcript 34591570ed07)` (31-07-SUMMARY.md): INSTALL_OK, KEYS_OK, ISOLATION_OK and REVERSE_OK in both orders, REMOVE_OK, `TRACER_LANDING_TEARDOWN_OK`; `gate_problem` None |
| 4 | App keys files meet defaults on both OSes; Linux Ctrl+Shift+K clears and displaced picker is named; user binding kept as `partial: kept yours` | VERIFIED (desktop behavior human) | `installer/herdr_app_keys.py:38` (`cmd-k` macOS / `ctrl-shift-k` Linux), `:108-147` (chord-normalizing detector returns `herdr-app: partial: you already bind ...`); `installer/terminal_keys.py:408` (install note names the picker `mod.open:picker`, stays in palette); goldens G4/G5 in `tests/test_herdr_app_row.py`; per-key `OwnedKeys` drift/strip in `tests/test_terminal_ownership.py` |
| 5 | SPEC prohibitions: default not left changed after uninstall; multiplexer untouched; foreign profile/keys file never overwritten | VERIFIED | Golden before/after tests (iTerm2); container byte comparison (herdr both orders); foreign-content refusal tests in `tests/test_terminal_ownership.py` and `tests/test_iterm2_row.py`; targeted run of 7 phase test files all passed on this tree |
| 6 | Phase 28 undeclared-row and closed-table tests pass with both rows | VERIFIED | `tests/test_terminal_json_catalog.py`, `tests/test_tool_onboarding_skill.py` (31-VALIDATION audit; included in orchestrator's 8639-pass `make test`) |

**Score:** 6/6 truths verified by automated or recorded evidence; 0 behavior-unverified in code terms. Nine real-Mac / desktop checks remain as human items.

### Requirements Coverage

| Requirement | Status | Evidence |
| ----------- | ------ | -------- |
| NTERM-02 | SATISFIED in code and goldens; live-Mac checks human | Truths 1, 2, 5 |
| NTERM-03 | SATISFIED in code, goldens and container; Mac/desktop checks human | Truths 3, 4, 5 |

No orphaned requirements.

### Provisional owner decisions (need confirmation, not failures)

- 31 D-08 (Option stays Normal, key-map rows) and 31 D-12 (macOS herdr-app via cask; vendor script would place the app in `~/Applications`).
- CONTEXT amendments of 2026-11-21: D-07 (malformed file skipped on its own), D-09 (parent key map merged only when readable), D-11 (`iterm2_defaults` seam, restore before cask removal), D-16 (`cmd/super/win/secondary` chord names).
- Orchestrator decisions 2 to 5 and 7 (iTerm2 restore before the cask removal with refusal; parent key-map rule; D-07/D-16 corrections; keys.json edge cases; generic-e2e exclusion), and 28 D-06.
- Accepted limits in 31-REVIEW-DISPOSITION.md (stale created marker after a keys-path change WR-03, `tool_id` special case IN-01, injected-vs-process home IN-02, strip deletes a file with an appended profile, custom prefs folder bypass), tracked in backlog 999.31.
- Dark-green RGB values are documented guesses (D-10); iTerm2 key formats taken from master source (see CONTEXT deferred list).

### Anti-Patterns

No unreferenced TBD/FIXME/XXX found in the checked files' relevant paths; accepted review limits are documented, not silent. 31-SECURITY.md: SECURED, 21/21 threats closed.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase test files (profile, row, keys, ownership, catalog, container driver) | `uv run pytest tests/test_iterm2_profile.py tests/test_iterm2_row.py tests/test_herdr_app_keys.py tests/test_herdr_app_row.py tests/test_terminal_ownership.py tests/test_terminal_json_catalog.py tests/test_container_e2e_herdr_app.py --no-cov -q` | all passed | PASS |

### Probe Execution

Container probe `scripts/container-e2e-verify.sh herdr-app` not re-run by the verifier (orchestrator evidence relied on, as instructed): PASS, transcript 34591570ed07.

### Gaps Summary

No gaps. Status is human_needed because the owner-assigned real-Mac and Linux-desktop checks cannot be exercised here; phase.complete refusing on this status is by design.

---

_Verified: 2026-11-21_
_Verifier: Claude (gsd-verifier)_
