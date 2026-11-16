---
phase: 21-one-screen-family
plan: "13"
subsystem: uninstall-removal
tags: [textual, worker, mutation-lock, uninstall, tdd]
requires: ["21-02", "21-07", "21-09", "21-12"]
provides:
  - "MutationHolder (REMOVAL) and the app mutation lock: begin_mutation, end_mutation, refuse_if_mutating, mutation_in_flight"
  - "MUTATION_REFUSAL, the one refusal template"
  - "RemovalFinished; UninstallScreen._remove_worker and on_removal_finished"
  - "HeldRemover test double"
affects: [21-14, 21-15, 21-16]
key-files:
  modified:
    - installer/enums.py
    - installer/wizard_app.py
    - tests/screen_family.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
    - tests/test_uninstall_e2e.py
decisions:
  - "The invalidate seam runs inside the worker after the remover, also after a failed or crashed remover, because only invalidate clears the pending ids marked at confirm (D-09)"
  - "The follow-up pass is requested only when the decision names a tool; an environment-only sweep asks for none (existing test, 21-14 revisits)"
  - "The finish handler reads the ban/PATH/tweak flags from the decision, not from the live selection, since the selection can change while the worker runs"
metrics:
  tasks: 2
  completed: 2026-11-03
status: complete
actuals:
  tokens: 40000
  tasks: 2
  commits: 4
plan_head_before: 4e989857e7f411ac18f36772e1780959943f6741
plan_head_after: 01fdc4678e2c8cfba30ca9843d82e5df037d5149
commits: 4
---

# Phase 21 Plan 13: Removal on a worker under the app mutation lock Summary

A confirmed removal now marks its tools pending, takes the app mutation lock, runs the remover on an exclusive `uninstall-removal` worker, and finishes with the Phase 20 count line and one follow-up pass; a second removal (or any refused mutation) gets the one template and still ends with one pass.

## Commits

- a04b6a8 test(21-13): a confirmed removal keeps the UI responsive and refuses a second one (RED)
- d1202e8 feat(21-13): removals run on a worker under the app mutation lock
- 48d6c72 test(21-13): a refused removal ends with one pass, a crash releases the lock (RED)
- 01fdc46 feat(21-13): a refused mutation still ends with one refresh pass

## RED output

Task 1 (the held remover blocked the event loop until `HeldRemover` timed out):
```
FAILED tests/test_screen_family.py::test_a_held_removal_keeps_the_ui_responsive
FAILED tests/test_screen_family.py::test_a_second_removal_is_refused_while_one_runs
At index 0 diff: 'Uninstall failed: HeldRemover was never released. Check permissions, then press enter.' != 'Removing…'
```
Task 2 (`-k "refused_removal or remover_crashes or exit_code"`): only the refusal-pass test failed (`condition never became true within the polling budget`). `test_the_lock_is_released_when_the_remover_crashes` and `test_removal_outcomes_do_not_change_the_exit_code` already passed on the Task 1 code, as the plan anticipated.

## GREEN

- `uv run pytest tests/test_screen_family.py tests/test_wizard_app.py tests/test_uninstall_e2e.py -n auto`: all pass.
- Final tree: `make validate` exit 0; `make test` exit 0, 5016 passed, 4 skipped, coverage 96.11%.
- Task 1 tree: `make validate` exit 0, `make test` exit 0 (5013 passed).

## Test counts (start -> end)

| File | Start | End | Floor |
| --- | --- | --- | --- |
| tests/test_screen_family.py | 40 | 45 | start + 5 |
| tests/test_wizard_app.py | 320 | 320 | start |
| tests/test_uninstall_e2e.py | 3 | 3 | start |

## Changed existing tests (reason)

- `tests/test_wizard_app.py`, 22 removal pilots: `await pilot.pause()` after the confirm became `await settle(app, pilot)`, because the removal now completes on a worker (locked D-08).
- `test_uninstall_apply_calls_the_terminal_synchronizer_once_on_success`: the remover returns `SweepResult(removed=("rg",))` and the assertion reads `1 removed` instead of `Removed 1 tool(s).` (locked D-11: the count line replaces the old sentence).
- `test_uninstall_apply_does_not_invalidate_on_a_failed_sweep` renamed `test_uninstall_apply_invalidates_after_a_failed_sweep`, now expecting one invalidate: the tools were marked pending at confirm (locked D-09) and only `invalidate` clears them, so a failed sweep must still call the seam.
- `test_uninstall_applied_summary_omits_tool_line_when_no_tool`: docstring only.
- `tests/test_uninstall_e2e.py`: the three confirm sites await `settle`.

## Deviations from Plan

None - plan executed as written. The worker and finish handler sit after `_applied_summary` in the class, so the plan's awk check on `_apply_removal`..`_applied_summary` finds no remover call on the event loop.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Files verified: installer/enums.py (REMOVAL = "A removal"), installer/wizard_app.py (group="uninstall-removal", begin_mutation, end_mutation, refuse_if_mutating, MUTATION_REFUSAL), tests/screen_family.py (HeldRemover), tests/test_screen_family.py. Commits a04b6a8, d1202e8, 48d6c72, 01fdc46 are in the branch history.
