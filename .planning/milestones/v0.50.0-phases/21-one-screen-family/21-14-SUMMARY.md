---
phase: 21-one-screen-family
plan: "14"
subsystem: uninstall-removal
tags: [textual, worker, uninstall, quit, tdd]
requires: ["21-09", "21-12", "21-13"]
provides:
  - "Failed-row words and reasons (`_failed_lines`), retry on Enter"
  - "Removal worker invalidates through the app's VersionRefreshService; UninstallInputs.invalidate deleted"
  - "Every removal ends with one refresh pass (environment-only included) unless quitting"
  - "UnifiedApp.quitting and _exit_after_removal: q / ctrl+c wait for a running removal"
affects: [21-15, 21-16]
key-files:
  modified:
    - installer/wizard_app.py
    - setup.py
    - tests/state_doubles.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
decisions:
  - "The quit wait runs on its own worker (`_exit_when_done`) instead of an await inside the action: awaiting in the handler blocks the app message pump, so pilot.press hangs until the remover returns and a shutdown cannot cancel the wait"
  - "action_abort / action_hard_abort stay sync (plan said async) for that reason"
  - "A failed row's word goes in the `What gets removed` cell; its detail is `remove failed — reason`, followed by the state's own detail (known non-absent states) or the `remove it yourself:` list (absent with leftovers)"
metrics:
  tasks: 2
  completed: 2026-11-03
status: complete
actuals:
  tokens: 45000
  tasks: 2
  commits: 4
plan_head_before: bb54d4bef2e4b4e945ce0941960eb39b733a57dc
plan_head_after: 5b394a3b6305cc9490653c47c17e021444910047
commits: 4
---

# Phase 21 Plan 14: Failed removals retry, one pass per removal, quit waits Summary

Failed tools keep a `remove failed — {reason}` row (kept across navigation and publishes, selected while their state still proves them removable), Enter retries them, the invalidate comes from the app's service, every removal ends with one pass, and q / ctrl+c wait for a running removal.

## Commits

- f16d8ba test(21-14): failed removals stay selected, every removal ends with one pass (RED)
- 4ac5ab8 feat(21-14): failed removals stay selected and retry; every removal ends with one pass
- ba9e30c test(21-14): quitting during a removal waits for it (RED)
- 5b394a3 feat(21-14): quitting waits for a running removal

## RED output

Task 1 (`-k "failed_removal or retries or ... or failed_reason"`): 8 of 9 failed; `test_enter_retries_the_failed_rows` already held on 21-13 code.
```
assert '/tmp/pytest-...st-150/test_…' == 'remove failed'
assert 'version cache invalidation failed: disk' in '1 removed\n'
FAILED test_a_failed_removal_keeps_the_row_selected_with_its_reason
FAILED test_the_removal_invalidates_through_the_app_service
FAILED test_an_invalidate_failure_is_reported_and_the_pass_still_runs
FAILED test_an_env_only_removal_requests_a_pass_without_invalidating
FAILED test_a_permission_failure_stays_selected_after_the_follow_up_pass
FAILED test_a_refused_row_leaves_the_selection_when_its_proof_is_gone
FAILED test_a_partial_delete_keeps_its_reason_while_leftovers_remain
FAILED test_a_failed_reason_survives_leaving_and_reentering_uninstall
```
Task 2 (`-k "quit or ctrl_c or under_the_palette"`): the three wait tests and the ctrl+c-under-palette test failed (app exited at once, no waiting copy); `q` under the palette and quit without a removal already held.

## GREEN

- `uv run pytest tests/test_screen_family.py tests/test_wizard_app.py tests/test_uninstall_e2e.py tests/test_setup.py -n auto`: all pass.
- Final tree: `make validate` exit 0; `make test` exit 0, 5030 passed, 4 skipped, coverage 96.12%.
- Task 1 tree: `make validate` exit 0, `make test` exit 0 (5024 passed).

## Test counts (start -> end)

| File | Start | End | Floor |
| --- | --- | --- | --- |
| tests/test_screen_family.py | 45 | 60 | 60 |
| tests/test_wizard_app.py | 320 | 319 | one test deleted (below) |

Suppression comments (type: ignore / pyright: ignore / noqa / nosec across installer, setup.py, tests): 458 -> 456. The plan assumed an `except Exception` with a suppression on the invalidate path; none existed (that block carried no comment). To satisfy the drop gate honestly I replaced the two `service.refresh = ...  # type: ignore[method-assign]` assignments in `test_epoch_guard_drops_stale_refresh_after_update` with `monkeypatch.setattr`.

## Changed existing tests (reason)

All in `tests/test_wizard_app.py`; the `UninstallInputs.invalidate` seam they exercised is deleted by this plan (locked D-05/D-08):
- `test_uninstall_apply_invalidates_the_shared_data_once_on_success`, `..._after_a_failed_sweep`, `test_an_env_lever_only_sweep_does_not_invalidate_ownership`, `test_removal_requests_the_app_pass_after_invalidate`: assert on `FrozenStateService.invalidations` instead of a lambda seam.
- `test_uninstall_apply_survives_a_raising_invalidate_seam` renamed `..._a_raising_invalidate`, and `test_removal_requests_a_pass_even_when_invalidate_raises`: the service double raises `OSError` (the worker reports it through `run_live`, which catches OSError).
- `test_a_removal_with_no_refresh_seam_still_completes` renamed `..._no_refresh_service_...`: a ban removal with no service.
- `test_an_environment_only_removal_requests_no_pass` deleted: opposite of locked W2 (every removal ends with one pass); covered by the new `test_an_env_only_removal_requests_a_pass_without_invalidating`.
- `test_state_refreshed_preserves_a_standing_removal_summary`: an environment-only removal now queues a pass behind the held one, so the test waits on `screen.applied` instead of `settle`.
- `tests/state_doubles.py`: `FrozenStateService` records `invalidations` and can raise `invalidate_error` (test support).

## Deviations from Plan

**1. [Rule 1 - Bug] Quit wait must not block the key handler**
- **Issue:** plan makes `action_abort` / `action_hard_abort` `async` and awaits the worker in them. That blocks the app message pump: `pilot.press("q")` hung until the remover returned (10 s HeldRemover timeout), and a shutdown could not cancel the wait.
- **Fix:** the actions stay sync and `_exit_after_removal` starts a `quit-wait` worker (`_exit_when_done`) that awaits the removal workers (`Worker.wait`, `WorkerFailed`/`WorkerCancelled` suppressed) then `exit(None)`. Shutdown cancels the waiter. The acceptance greps for `async def action_abort` / `async def action_hard_abort` therefore return 0; `def _exit_after_removal` and the waiting copy return 1.
- **Commit:** 5b394a3

**2. [Rule 3] Suppression gate** - see counts above; the premise block did not exist.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

installer/wizard_app.py contains `Fix the cause and press enter to try again.` once, `def _exit_after_removal` once, no `invalidate` in `UninstallInputs`; setup.py has no `uninstall run finished` invalidate argument; commits f16d8ba, 4ac5ab8, ba9e30c, 5b394a3 are in the branch history.
