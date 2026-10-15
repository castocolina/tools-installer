---
phase: 17-stop-the-bleeding
plan: "19"
subsystem: ui
tags: [textual, exit-codes, session-summary, fold-run, tui, execute-screen, catalog-updates]

requires:
  - phase: 17-stop-the-bleeding
    provides: "D-08 Summary failure fields + fold_run (17-07), ExecuteScreen crash guard D-07, _session_exit_code"
provides:
  - "Screen and exit code agree on what a failure is: both fold_run sites fold the worker's not_attempted"
  - "Update-outcome row reconciliation before the pending-row sweep (completed updates stay done across a refresh crash)"
  - "not_attempted no longer leaks across runs (cancel-then-retry exits 0)"
  - "Crash text appends to a PATH-wiring error instead of replacing it (both texts reach the log)"
  - "Failed direct catalog updates ('u') render as errors and fold into the session summary, so the process exits 1"
  - "Hard abort (ctrl+c) while a run is in flight exits 1 on every route (UnifiedApp.run_in_flight)"
affects: [17-20, phase-20-plan-outcomes]

actuals:
  tokens: 12700
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One session fold: UnifiedApp._merge_summary is the single field-wise merge for install runs AND direct-update failures"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - installer/wizard_app.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
    - tests/test_catalog_tui.py
    - tests/test_setup.py

key-decisions:
  - "WR-01 fixed at the fold input (fold message.not_attempted on the screen), never in fold_run itself — prohibition honored, fold_run semantics byte-identical"
  - "H3 folds a direct-update failure into install_summary through the same _merge_summary the install run uses, so _session_exit_code needs no second rule (no new state class)"
  - "WR-06 uses a public run_in_flight flag set by a new InstallRunStarted message; abort-with-no-run keeps exit 0"
  - "IN-07 log condition keys on 'error differs from path/verify error' so the combined text is logged without duplicating the dedicated wiring-failure line"

patterns-established:
  - "Session failure signals have exactly one writer per source: worker messages -> fold_run -> _merge_summary -> _session_exit_code"

requirements-completed: [SAFE-05, SAFE-09]

coverage:
  - id: D1
    description: "A skipped update (in-flight latch) is a failure on neither signal: screen shows 'Done.' and has_failure is False on both folds"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_in_flight_latch_skip_is_a_failure_on_neither_signal"
        status: pass
    human_judgment: false
  - id: D2
    description: "A completed update stays done when the version refresh crashes; the run is red only from the crash"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_a_completed_update_stays_done_when_the_version_refresh_crashes"
        status: pass
    human_judgment: false
  - id: D3
    description: "not_attempted does not leak across runs: cancel then successful re-run folds clean (has_failure False; exit 0)"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_a_cancelled_run_then_a_successful_rerun_is_not_a_failure"
        status: pass
    human_judgment: false
  - id: D4
    description: "A crash after a PATH-wiring failure keeps both texts in the log"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_a_crash_after_a_path_wiring_failure_keeps_both_texts_in_the_log"
        status: pass
    human_judgment: false
  - id: D5
    description: "A failed direct catalog update renders as an error and folds into the session summary; setup exits 1"
    requirement: SAFE-09
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_a_failed_direct_update_renders_as_an_error_not_a_warning"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_a_failed_direct_update_folds_into_the_session_summary"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_failed_direct_catalog_update_exits_1"
        status: pass
    human_judgment: false
  - id: D6
    description: "ctrl+c while a run is in flight leaves run_in_flight set and exits 1 on the wizard and doctor routes; abort with no run keeps 0"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_ctrl_c_while_a_run_is_in_flight_leaves_the_flag_set"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_run_in_flight_flag_lifecycle"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_ctrl_c_with_no_run_in_flight_keeps_the_clean_abort"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_ctrl_c_mid_run_exits_1"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_doctor_route_interrupted_mid_run_exits_1"
        status: pass
    human_judgment: false

duration: 75min
completed: 2026-10-14
status: complete
---

# Phase 17, Plan 19 Summary

**Every code-review finding about run outcome and exit codes is closed: skipped updates are not failures on screen or exit code, completed updates survive a refresh crash, cancel-then-retry exits 0, a failed direct `u` update is red and exits 1, and a ctrl+c mid-run exits 1 on every route.**

## Performance

- **Duration:** 75 min
- **Tasks:** 3 of 3
- **Files modified:** 8 (all inside the plan's `files_modified`)

## Per-finding table

| Finding | Source lane | Outcome | Commit | Test |
|---|---|---|---|---|
| WR-01 screen vs exit disagree on skips | Claude review | Fixed | `f5036ca` | `test_in_flight_latch_skip_is_a_failure_on_neither_signal` |
| ponytail #1 (same defect, smaller fix) | ponytail | Fixed by the WR-01 change | `f5036ca` | same test |
| opencode M3 completed updates become not attempted | opencode | Fixed | `f5036ca` | `test_a_completed_update_stays_done_when_the_version_refresh_crashes` |
| ponytail #6 not_attempted leaks across runs | ponytail | Fixed | `f5036ca` | `test_a_cancelled_run_then_a_successful_rerun_is_not_a_failure` |
| IN-07 crash text lost after PATH-wiring failure | Claude review | Fixed | `f5036ca` | `test_a_crash_after_a_path_wiring_failure_keeps_both_texts_in_the_log` |
| opencode H3 failed direct update exits 0 | opencode | Fixed | `1d28f3f` | `test_a_failed_direct_update_renders_as_an_error_not_a_warning`, `test_a_failed_direct_update_folds_into_the_session_summary`, `test_failed_direct_catalog_update_exits_1` |
| WR-06 hard abort mid-run exits 0 | Claude review | Fixed | `f7ea9b7` | `test_ctrl_c_while_a_run_is_in_flight_leaves_the_flag_set` + 4 more |

No finding was "not reproduced"; all seven were reproduced with a failing test first.

## Task Commits

1. **Task 1: screen and exit code agree on what a failure is** — `f5036ca` (fix)
2. **Task 2: a failed direct update from the catalog is red and exits 1** — `1d28f3f` (fix)
3. **Task 3: hard abort mid-run exits 1** — `f7ea9b7` (fix)

## TDD RED evidence (trimmed)

Task 1, WR-01:

```
>           assert screen.summary.has_failure is False
E           AssertionError: assert True is False
E            +  where True = Summary(... not_attempted=('rg',) ...).has_failure
```

Task 1, M3:

```
>       assert "rg" not in screen.summary.not_attempted
E       AssertionError: assert 'rg' not in ('rg',)
```

Task 1, IN-07:

```
E           AssertionError: assert ('fd',) == ()
```
RED as `FAILED tests/test_execute_screen.py::test_a_crash_after_a_path_wiring_failure_keeps_both_texts_in_the_log`
(crash text absent from the log).

Task 1, ponytail #6:

```
E           AssertionError: assert ('fd',) == ()
E             Left contains one more item: 'fd'
tests/test_wizard_app.py:7328: AssertionError
```

Task 2, rendering:

```
E       AssertionError: assert [('brew exploded', 'warn')] == [('brew exploded', 'error')]
```

Task 2, session fold:

```
>           summary = app.install_summary
E           assert None is not None
```

Task 3:

```
E   ImportError: cannot import name 'InstallRunStarted' from 'installer.execute_screen'
```
then, after the import existed but the wiring did not:
`FAILED tests/test_setup.py::test_ctrl_c_mid_run_exits_1` (main returned 0) — all five Task 3 tests RED before the implementation commit.

## Verify-command results

- Task 1: `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_session.py -q --no-cov` — all pass.
- Task 2: `uv run pytest tests/test_catalog_tui.py tests/test_setup.py -q --no-cov` — all pass.
- Task 3: `uv run pytest tests/test_wizard_app.py tests/test_setup.py -q --no-cov` — all pass.
- `make validate` before each commit — exit 0 (ruff, ruff format, pyright, bandit, vulture, shellcheck).
- Final: `make test` — 3563 passed, 4 skipped, coverage 95.96% (gate 90%) — exit 0.

## Deviations from Plan

### Auto-fixed Issues

**1. Test fakes needed the new `run_in_flight` attribute**
- **Found during:** Task 3 (`_session_exit_code` gained an in-flight check)
- **Issue:** `_capture_app._App`, `_DummyApp`, `_SummaryApp`, `_Done`, `_Quiet` and the two local `_Aborting` fakes in `tests/test_setup.py` had no `run_in_flight`, so `_session_exit_code` raised AttributeError.
- **Fix:** added `run_in_flight = False` to each fake; `_capture_app._App` additionally installs the real `on_tool_updated`/`_merge_summary` (captured before the patch) so the H3 test can drive the real fold.
- **Files modified:** `tests/test_setup.py`
- **Verification:** full `tests/test_setup.py` passes.
- **Committed in:** `1d28f3f`, `f7ea9b7`

**2. Task 1's M3/IN-07 tests were restructured after their first RED run**
- **Found during:** Task 1
- **Issue:** the first draft asserted `_log_text(screen)` after the app context closed (screen unmounted → NoMatches). Assertions unchanged; only the harness moved inside `app.run_test`.
- **Verification:** both tests RED before the implementation (captured in the first RED run) and GREEN after.
- **Committed in:** `f5036ca`

---

**Total deviations:** 2 auto-fixed (both test-harness only, no production scope change)
**Impact on plan:** None on production behavior; all changes stayed inside `files_modified`.

## Issues Encountered

- The plan's Task 1 listed `installer/session.py` and `tests/test_session.py` as modifiable; neither needed a change — `fold_run` semantics are untouched (the prohibition requires exactly that).
- IN-07 required one judgment call the plan left open: the log condition had to change too (print `message.error` when it differs from the path/verify error), otherwise the appended crash text still never reached the log when a wiring error was present. The dedicated wiring/audit lines keep printing their own text; no duplication.

## Orchestrator notes

- IN-06 (UnifiedApp `execute=None` test-only branch) untouched, per orchestrator decision.
- Phase 20 note: `_merge_summary` is the single site a plan-outcome-based fold replaces; `update_failed` filtering across runs (a failed `u` followed by a successful re-update) is still additive and is subsumed by the Phase 20 exit rule.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
