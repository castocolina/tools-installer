---
phase: 21-one-screen-family
plan: "20"
subsystem: ui
tags: [textual, doctor, version-cache, invalidate]
requires: ["21-19"]
provides:
  - "Doctor without the hidden `a` key; `r` and `enter` republish the shared state"
  - "`_managers_invalid`: a failed invalidate write still forces a manager re-query"
affects: [installer/wizard_app.py, installer/version_status.py]
key-files:
  modified:
    - installer/wizard_app.py
    - installer/version_status.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
    - tests/test_version_status.py
decisions:
  - "invalidate_error travels raw on GlobalsReinstalled; the screen formats it as `version cache invalidation failed: {error}`"
  - "A saved failed-query snapshot also clears `_managers_invalid`, so the 30-minute retry backoff governs a failing manager"
metrics:
  tasks: 3
  completed: 2026-11-03
status: complete
actuals:
  tokens: 30000
  tasks: 3
  commits: 6
plan_head_before: bf456b6b492117088f27840d116e72613e4d3b62
plan_head_after: 251dbde
---

# Phase 21 Plan 20: Doctor lifecycle Summary

Doctor loses its hidden `a` key, republishes the state after `r` and `enter`, reports a failed cache invalidation under the reinstall line, and re-renders after a first-run link pick; a failed invalidate write no longer lets the next pass reuse the persisted pre-reinstall manager snapshot.

## Commits

- 6725183 test(21-20): doctor drops its hidden key and republishes after its fixes (RED)
- f292d72 feat(21-20): drop doctor's hidden key and republish after its fixes
- f0cc70c test(21-20): a failed invalidate write forces the next manager query (RED)
- 06bde98 fix(21-20): a failed invalidate write forces the next manager query
- 9f51e54 test(21-20): the first-run link pick re-renders doctor (RED)
- 251dbde fix(21-20): the first-run link pick re-renders doctor

## RED output (abridged)

Task 1 (11 failing before the implementation): `test_reinstall_invalidates_and_requests_one_pass`, `test_a_is_inert_on_doctor`, `test_doctor_footer_lists_enter_and_r_only`, `test_doctor_fix_requests_one_pass[fix_ok|fix_raises]`, `test_a_failed_invalidate_after_a_reinstall_is_reported[mapped|unmapped]`, `test_a_crashed_reinstall_still_invalidates[invalidate_ok|invalidate_crashes]`, `test_a_real_cache_write_failure_after_a_reinstall_is_reported`, `test_doctor_fix_with_a_guard_file_requests_its_pass_after_the_confirmations` (e.g. `AssertionError: condition never became true within the polling budget` waiting for the pass).

Task 2:
```
test_failed_invalidate_save_still_requeries_the_managers   assert 1 == 2
test_a_failed_query_after_a_failed_invalidate_save_...     assert 1 == 2
test_a_real_cache_write_failure_after_a_reinstall_...      assert 1 > 1   (len(['inventory']))
```
Task 3: `assert 'PREVIEW-split' in 'PATH Doctor ... PREVIEW...centralized'` (`test_a_first_run_link_pick_rerenders_doctor`). `test_a_failed_first_run_pick_keeps_the_error` passed already (it pins the unchanged failure branch).

GREEN: each targeted run passes; after every task `make validate` exit 0 and `make test` exit 0 (5112, 5114, 5116 passed, 4 skipped; coverage 96.2%).

## Notes

- Manager-only fact flipped by the extended Doctor test: pnpm's global inventory (`ManagerInventory.pnpm_globals`) goes from empty (A, persisted at launch) to containing `@mermaid-js/mermaid-cli` (B); the published `ToolState.ownership` for `mmdc` differs after `r` with the save failing, and the manager reader is called again.
- The pre-commit hooks passed on the RED commits (no stub symbols were needed).
- `_family_app` gained `fix`, `reinstall_globals` and `prompt_link_mode` kwargs (test helper only).
- The 80x20 Doctor status-row gap was not touched or needed.

## Tests changed or removed

- `tests/test_wizard_app.py::test_doctor_hidden_a_alias_applies_fix` deleted: the code it exercised (the hidden `a` binding) is deleted by this plan (D-14). Replaced by `test_a_is_inert_on_doctor`.
- No test switched from `a` to `enter`; `test_doctor_enter_applies_fix_once` already used `enter`.

## Collected counts (start -> end)

- tests/test_screen_family.py: 113 -> 125 (+12)
- tests/test_wizard_app.py: 319 -> 319 (-1 deleted, +1 added)
- tests/test_version_status.py: 227 -> 229 (+2)

## Deviations from Plan

None - plan executed as written. The plan's stale floors (121/123) were replaced by measured start counts plus the delta, per the orchestrator decision.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

All six commits are ancestors of HEAD; the five touched files exist.
