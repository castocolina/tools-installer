---
phase: 21-one-screen-family
plan: "01"
subsystem: ui
tags: [textual, screen-lifecycle, show_view]
requires: []
provides:
  - AppScreen.enter_view -> state_refreshed, clear_transient defaults
  - six views installed on Textual's empty root, one show_view order (clear, pop, push, enter)
  - UnifiedApp.view(name) test seam
affects: [21-02, 21-06, 21-17]
key-files:
  created: [tests/test_screen_family.py]
  modified: [installer/ui_common.py, installer/wizard_app.py, installer/catalog_tui.py, tests/test_wizard_app.py, tests/test_catalog_tui.py]
decisions:
  - "current_view starts as the empty-string root sentinel so launch goes through show_view"
  - "pending-warning flush runs before enter_view; Uninstall writes its standing status only over an empty line"
status: complete
commits: 1
plan_head_before: 390f464298f06a30365de37e11510d5479afa09a
plan_head_after: ccd0ad7
actuals:
  tokens: 30000
  tasks: 2
  commits: 1
---

# Phase 21 Plan 01: One screen family Summary

Six views are installed once on Textual's empty default screen and reached through a single `show_view` order (clear, pop, push, flush warnings, enter); `AppScreen` owns the lifecycle defaults and status written during entry survives while leaving clears it.

## Deviations from Plan

**1. [Rule 3] One commit instead of two.** Task 2's Uninstall changes (stash deletion, standing-status guard) are interleaved with Task 1's `wizard_app.py` edits, so both tasks landed in `ccd0ad7`. Gates ran on that exact tree. A true Task-2 RED run was therefore not separable; Task-1 RED was not captured separately either, because source and tests were written together under time pressure (honest gap: no pasted RED output).

**2. [Rule 1] Existing tests adapted to the new lifecycle.**
- `test_uninstall_does_not_refresh_after_it_has_applied_when_unchanged`: leaving Uninstall now clears the removal sentence (UI-SPEC "Re-entering: empty"); assertion changed to `status.text == ""` with `applied` still True.
- Two uninstall tests relied on the system tier starting its version refresh at mount; it now starts on entry, so they visit system and return (21-06 owns the app-level refresh).

**3. [Rule 2] Added `UnifiedApp.view(name)`** typed seam (like `catalog_for`) because pyright strict rejects `App.get_screen` and private `_views` in tests.

## Verification
- `make validate` exit 0; `make test` exit 0: 4941 passed, 4 skipped.
- Floors: test_screen_family 18, test_wizard_app 315, test_catalog_tui 214.
- `get_default_screen`, `_pending_status`, `_set_status` in `installer/wizard_app.py`: start 1/5/4 (plan figures), end 0/0/0.

## Known Stubs
None.

## Self-Check: PASSED
