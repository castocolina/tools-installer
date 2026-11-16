---
phase: 21-one-screen-family
plan: "10"
subsystem: tui
tags: [textual, refresh-owner, execute-screen]
requires: [21-02, 21-06, 21-07]
provides: [UnifiedApp.await_publication, RefreshFinished.error]
affects: [installer/wizard_app.py, installer/execute_screen.py]
key-files:
  modified:
    - installer/wizard_app.py
    - installer/execute_screen.py
    - tests/test_execute_screen.py
    - tests/test_screen_family.py
    - .claude/architecture.md
status: complete
requirements: [UI-01]
actuals:
  tokens: 9000
  tasks: 2
  commits: 3
plan_head_before: f5e8a975f3f86827c0d1ae69667fb20bb4c8c5a0
---

# Phase 21 Plan 10: Review waits on the app refresh owner Summary

`ExecuteScreen._await_state` now calls `UnifiedApp.await_publication`, which joins the app's running pass (or starts one) and serves waiters only when no follow-up pass is pending; the `execute-wait` worker is deleted.

## Commits

- dc2c482 test(21-10): RED test for the review running no worker of its own
- 75b6366 refactor(21-10): the review waits on the app refresh owner
- f52c93a test(21-10): pin the publication waiter and document it

## RED

```
>  assert [w for w in app.workers if w.group == "execute-wait"] == []
E  AssertionError: assert [<Worker RUNNING name='_wait_worker' group='execute-wait' ...>] == []
FAILED tests/test_execute_screen.py::test_the_review_waits_on_the_app_pass_and_runs_no_worker_of_its_own
```

## GREEN

`uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_screen_family.py -n auto` all passed after the implementation. Task 2 tests: the five waiter tests were already satisfied by Task 1 (no RED); one, `without_a_service`, failed first on a sentinel bug in the test itself, fixed in the same commit.

## Changes

- `RefreshFinished(error)`: pass error (tool refresh, else skills); starts as `state check did not complete`; an escaping exception becomes `session.first_line`.
- `await_publication`: no service answers `None` at once; otherwise appends and requests a pass only if none runs.
- `on_refresh_finished` re-requests when pending, else serves and clears waiters.
- `ExecuteScreen.app` is typed `UnifiedApp` under TYPE_CHECKING; `ask_from_worker` now takes `App[Any]` (needed because `App[object]` is invariant against `UnifiedApp`).
- Architecture paragraph rewritten (keeps `_await_state` and `single flight`).

## Tests changed in tests/test_execute_screen.py

- `_host`: passes `version_refresh=inputs.version_refresh` (plan decision).
- `_RecordingRefreshService.refresh` no longer publishes "outdated" for every tool: with the app's launch pass now running against it, it clobbered the seeded states of 9 tests (dispositions turned UPDATE). It still records `asked`.
- `test_update_outcome_survives_state_invalidation_without_followup_refresh` and `test_blocked_update_does_not_trigger_a_version_refresh`: `asked == []` became `asked == ["rg"]` (the app's launch pass only; the run still asks for none).
- Added: `test_the_review_waits_on_the_app_pass_and_runs_no_worker_of_its_own`.

## Counts

- tests/test_execute_screen.py: 134 -> 135
- tests/test_screen_family.py: 34 -> 40
- `make validate` exit 0; `make test` exit 0, 5009 passed, 4 skipped, coverage 96.10%.

## Deviations

[Rule 3] `ask_from_worker` annotation widened to `App[Any]` to type-check against `UnifiedApp`. Otherwise as planned. No stubs; no new threat surface.

## Self-Check: PASSED
