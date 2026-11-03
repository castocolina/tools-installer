---
phase: 21-one-screen-family
plan: "11"
subsystem: uninstall-view
tags: [textual, uninstall, health-column, tdd]
requires: ["21-03", "21-08", "21-09", "21-10"]
provides:
  - "UninstallScreen Health column read from the app's one VersionRefreshService"
  - "three Uninstall sections, bounded removal-path cell, repaint on every publish"
  - "pass_state(removable=, receipt=)"
affects: [21-12]
tech-stack:
  added: []
  patterns: ["always-repaint re-derivation", "Text.truncate ellipsis cell"]
key-files:
  modified:
    - installer/wizard_app.py
    - tests/state_doubles.py
    - tests/test_wizard_app.py
    - tests/test_layout_80x20.py
    - tests/test_uninstall.py
decisions:
  - "_REMOVES_CELL_MAX = 40"
  - "Repaint method is _repaint, not _render (Textual Widget._render collision)"
metrics:
  tasks: 2
  completed: 2026-11-03
status: complete
actuals:
  tokens: 30000
  tasks: 2
  commits: 4
plan_head_before: 3c89a02b5c21c1605700d04204a264d991778396
plan_head_after: da5b8efc8c7c5ceb363b6348948314905e06f220
commits: 4
---

# Phase 21 Plan 11: Uninstall Health column Summary

Uninstall now shows a Health cell per tool from the app's single refresh service, three sections (`removable here`, `managed elsewhere`, `nothing to do`), a `What gets removed` cell listing the proven paths cut to 40 cells, and repaints on every publish; the removal-proof tests read the state projection.

## Commits

- 11c2be5 test(21-11): Uninstall Health column, three sections and bounded removal list pilots (RED)
- c531345 feat(21-11): Uninstall gains the Health column, three sections and a bounded removal list
- 99a1faa test(21-11): the removal-proof tests read the state projection (RED, with a type-checking stub in `pass_state`)
- da5b8ef test(21-11): pass_state forwards removable= and receipt= to tool_state (GREEN)

## RED output

Task 1 (6 new tests, all failing for the right reason):
```
CellDoesNotExist: No cell exists for row_key='yq', column_key='health'
assert ['#not instal...lable', 'xyz'] == ['#nothing to..., 'fd', 'xyz']
assert '1 artifact(s)' == '/opt/rg'
assert ['Sel','Tool',...] == [... 'Health' ...]   (index 2: 'Cat' != 'Health')
```
Task 2 (stub accepted `removable=`/`receipt=` but ignored them):
```
FAILED test_uninstall_group_follows_the_removal_proof   (managed == removable)
FAILED test_uninstall_group_uses_the_receipt_proof      (managed == removable)
FAILED test_failed_opt_dir_delete_leaves_the_remainder_listed (path not in 'owner unknown; ...')
FAILED test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself
```
The tracer pilot `test_uninstall_health_column_reads_the_published_state` is part of the 6 and was also green after the feature commit.

## GREEN

`make validate` exit 0. `make test` exit 0: 5039 passed, 4 skipped, coverage 96.08%.
Test counts (start -> end): `tests/test_wizard_app.py` 318 -> 323, `tests/test_layout_80x20.py` 14 -> 15, `tests/test_uninstall.py` 120 -> 120.

## Chosen `_REMOVES_CELL_MAX`

40 (cell is cut with `Text.truncate(40, overflow="ellipsis")`).

## Tests changed (reason)

- `test_tool_entry_cell_per_state_and_removes_cell_unchanged` renamed `..._lists_the_paths`: cell indexes shift by the Health column; removes cell now `/opt/rg` / `—` (locked removes-cell rule).
- `test_uninstall_unchanged_rows_rebuilds_nothing_on_reentry`, `test_state_refreshed_returns_early_through_the_unchanged_comparison`: identity (`is`) became equality (`==`); the always-repaint rule (D-06) rebuilds the entries on every re-derivation.
- `test_uninstall_screen_cell_falls_back_when_seam_has_no_record`: cell index 3 -> 4.
- `test_classify_rows_follow_the_removal_proof` -> `test_uninstall_group_follows_the_removal_proof`; `test_classify_rows_use_the_receipt_proof` -> `test_uninstall_group_uses_the_receipt_proof` (read `uninstall_group` over `plan_removal` states).
- Four other tests stop calling `classify_tools`: `test_plan_removal_survives_looping_link_and_opt_dir` (the classify lines were redundant with the `plan.removable == ()` assertion), `test_tui_and_cli_delete_the_same_set`, `test_failed_opt_dir_delete_leaves_the_remainder_listed`, `test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself` (the last two read `uninstall_group` / `uninstall_detail`). The plan named five and stale line numbers (`test_plan_app_skips_cli...` never used the classification); these four are the real callers. The other `test_classify_*` tests are untouched; `installer/uninstall.py` is unchanged.

## Deviations from Plan

1. **[Rule 1 - Bug] `_render` renamed `_repaint`.** `Widget._render` is a Textual method returning the widget's visual; shadowing it crashed rendering (`'NoneType' object has no attribute 'render_strips'`). Behavior is as specified.
2. **[Rule 1] 80x20 backstop cannot hold the literal "every row at most 78 cells".** The widest catalog id (`softaworks-agent-toolkit`, 24 chars) plus Sel, Health, Cat and Installed via already take 64 cells, leaving 14-16 for a 17-char header. The backstop instead asserts the six headers, that `What gets removed` starts at least 12 cells inside the screen, and that its width is at most budget + padding (42). CR-03's real concern (the column start on screen, never sized by the longest path) is kept.
3. `pass_state`'s RED stub (accepts and ignores the two keywords) was committed first, as the project rules allow.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Files and the four commits above exist on branch `worktree-agent-af23e22b2793cacaa`.
