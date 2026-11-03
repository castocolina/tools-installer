---
phase: 21-one-screen-family
plan: "07"
subsystem: wizard-app
tags: [refresh, uninstall, messages, textual]
requires: [21-06]
provides:
  - Uninstall removal asks the app owner for its pass (request_refresh) after the invalidate
  - RefreshRequested message + UnifiedApp.on_refresh_requested
affects: [21-13, 21-14]
key-files:
  modified:
    - installer/wizard_app.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_wizard_app.py
    - tests/test_catalog_tui.py
    - tests/test_setup.py
status: complete
commits: 4
plan_head_before: 8d88cd1d7842ec7fe048c15875214182c155190a
plan_head_after: fb1c72346ca998a77976239643ad76efff7ba453
actuals:
  tokens: 30000
  tasks: 2
  commits: 4
requirements: [UI-01]
---

# Phase 21 Plan 07: Finish the refresh owner's reach

Uninstall removals and every refused `u` now end with one pass of the one app owner; the Uninstall-only refresh fork (`OwnershipRefreshed`, its app handler, the screen worker, `UninstallInputs.refresh`, the `setup.py` seam) is deleted.

## Commits
- ecd4031 test(21-07): RED - a removal asks the app owner for its pass
- 2eb5628 refactor(21-07): Uninstall removals ask the app owner; the ownership message and worker are gone
- 1b5109f test(21-07): RED - a refused update still requests one pass
- fb1c723 feat(21-07): a refused update still ends with one refresh pass

## TDD evidence

RED Task 1 (`-k "requests_the_app_pass or rerenders_when_a_pass or even_when_invalidate"`): 2 failed, 1 passed (the rerender pilot already held through the 21-06 publish path).
```
E   assert 1 == (1 + 1)
E    +  where 1 = <FrozenStateService>.passes      (test_removal_requests_a_pass_even_when_invalidate_raises)
E   assert 1 == (1 + 1)                              (test_removal_requests_the_app_pass_after_invalidate)
```
RED Task 2 (`-k refused_update_still_requests`): all 5 parametrizations failed on `assert service.passes == before + 1` (status copy already correct, no pass requested).

GREEN: the same selections pass; full suite below.

## Deleted names (start -> end counts)
| name | file | start | end |
|------|------|-------|-----|
| OwnershipRefreshed / _refresh_ownership_worker / uninstall-ownership-refresh | installer/wizard_app.py | 10 | 0 |
| OwnershipRefreshed | installer/catalog_tui.py | 1 | 0 |
| OwnershipRefreshed | setup.py | 1 | 0 |
| UninstallInputs `refresh:` field | installer/wizard_app.py | 1 | 0 |

## Collected tests
- tests/test_wizard_app.py: 312 -> 318 (floor 318)
- tests/test_catalog_tui.py: 177 -> 213 (floor 210)

## Tests changed or deleted (with reason)
- `test_a_same_session_removal_refreshes_the_attribution_its_invalidate_dropped` (test_wizard_app): replaced by the three app-pass pilots; it exercised the deleted `refresh` seam.
- `test_build_app_wires_a_refresh_seam_that_restores_the_invalidated_hint` (test_setup): deleted with the `refresh=` closure it exercised.
- `_uninstall_inputs` helper lost its `refresh` parameter.
- Added `test_an_environment_only_removal_requests_no_pass` to pin the plan's note that the env-only path (no invalidate) is extended in 21-14.

## Verification
- `make validate`: exit 0 on the final tree.
- `make test`: exit 0, 5001 passed, 4 skipped, coverage 96.06%.
- Absence grep over `installer/` and `setup.py`: no match.

## Deviations from Plan
None - plan executed exactly as written. (The first RED commits of each task were adjusted to satisfy the pre-commit pyright/ruff hooks: an unused import and typing of the test doubles; no stub was needed.)

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
