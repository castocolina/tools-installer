---
phase: 17-stop-the-bleeding
plan: "07"
subsystem: installer
tags: [textual, error-handling, exit-codes, summary, fold, tui, worker]
requires:
  - phase: 17-01
    provides: the locked D-07/D-08 decisions and the run_live/Summary seams this plan extends
provides:
  - Summary.not_attempted / update_failed / crash_error fields plus has_failure (D-08)
  - session.fold_run, the one pure fold both handlers call
  - _execute_worker except-Exception catch and _partial_run rebuild from the per-tool accumulator (D-07)
  - _run_updates caller-owned accumulators with an attempted set; unattempted update ids land in not_attempted
  - red "Failed." status and summary.has_failure-driven exit 1 on both setup.py routes
affects: [17-10, phase 20 outcome mapping]
actuals:
  tokens: 100000
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "caller-owned accumulators written by a long-running phase so a mid-phase crash still reports what completed"
    - "one pure fold (fold_run) shared by the screen status and the session accumulation"
key-files:
  created: []
  modified:
    - installer/session.py
    - installer/execute_screen.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_session.py
    - tests/test_execute_screen.py
    - tests/test_setup.py
key-decisions:
  - "fold_run dedupes update_failed (dict.fromkeys), outcome order first then error order (RESEARCH Pattern 3)"
  - "unattempted update ids are appended to not_attempted in the worker's finally, so a cancel or crash mid-updates reaches has_failure without being a crash or update failure"
  - "attempted counts a _to_update id that produced an outcome, an error or a skip; only ids the loop never reached stay not attempted"
requirements-completed: [SAFE-05]
coverage:
  - id: D1
    description: "Summary failure fields, has_failure, and the pure fold_run"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_summary_has_failure"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_fold_run_records_not_attempted_update_failures_and_crash"
        status: pass
    human_judgment: false
  - id: D2
    description: "A worker exception mid-run ends red, keeps done rows, reports the rest not attempted, and exits 1"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_worker_exception_marks_the_run_failed_and_keeps_done_rows"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_interactive_wizard_exits_1_when_the_session_has_a_failure"
        status: pass
    human_judgment: false
  - id: D3
    description: "Update failures and raised update errors mark the run failed and exit 1; completed updates survive a later crash; a cancel mid-updates keeps completed updates and reports the rest not attempted; an all-skipped run stays green and exits 0"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_failed_update_status_marks_the_run_failed"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_raised_update_error_marks_the_run_failed"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_completed_updates_survive_a_later_crash"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_cancel_mid_updates_keeps_completed_updates_and_reports_the_rest_not_attempted"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_all_skipped_run_is_done_and_green"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_failed_update_exits_1"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_all_skipped_run_exits_0"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_headless_run_exits_1_on_failure"
        status: pass
    human_judgment: false
duration: 95min
completed: 2026-10-14
status: complete
---

# Plan 17-07 Summary

**Every crashed or failed install/update run now reports a red "Failed." status, keeps the rows that finished, marks the rest not attempted, and exits 1 via Summary.has_failure on both setup.py routes — an all-skipped run stays green and exits 0.**

## Performance

- **Duration:** 95 min (including resuming a quota-interrupted prior run whose Task 1 edits were recovered and verified)
- **Completed:** 2026-10-14
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Hazard H6 (SAFE-05) closed: `_execute_worker` had only try/finally, so an exception ended in a green "Done." and exit 0. Now both stop paths (run_live-caught OSError/CommandError/ShellrcRefusal → result-is-None branch, and any other Exception → the new except branch) rebuild `outcomes`/`summary`/`not_attempted` from the same per-tool `collected` accumulator via `_partial_run`.
- Per D-08, `Summary` gained `not_attempted`, `update_failed`, `crash_error`, a `has_failure` property (manual_required/no_method excluded), and one pure `fold_run` that both `ExecuteScreen.on_install_run_finished` (status colour) and `UnifiedApp.on_install_run_finished` (session accumulation) call.
- Per Task 2, `_run_updates` writes into caller-owned accumulators plus an `attempted` set; the worker appends never-attempted update ids to the posted `not_attempted`, so a failed update, a raised update error, or a crash/cancel mid-updates all reach the status and the exit code, while a cancel is neither a crash (`crash_error` None) nor an update failure (`update_failed` empty).
- `setup.py` decides both exit codes (interactive :1275 and headless :1509) with `summary.has_failure`.

## Task Commits

1. **Task 1: a worker crash mid-run ends red, keeps done rows, and exits 1** - `8e3eea5` (feat)
2. **Task 2: failed updates exit 1, completed updates survive a crash, an all-skipped run exits 0** - `a59951d` (feat)

## TDD RED evidence

Task 1 (recovered from the quota-interrupted prior run's tree; RED regenerated by stashing the installer/setup changes and running the new tests against the pre-change tree):

```
tests/test_session.py:14: in <module>
    from installer.session import (
E   ImportError: cannot import name 'fold_run' from 'installer.session'
```
(the pilot `test_worker_exception_marks_the_run_failed_and_keeps_done_rows` additionally fails RED on the pre-change tree with the green "Done." status — the bug being fixed.)

Task 2 (new tests first, then implementation):

```
FAILED tests/test_execute_screen.py::test_cancel_mid_updates_keeps_completed_updates_and_reports_the_rest_not_attempted
E           assert "fd" in summary.not_attempted
E            +  where () = Summary(..., not_attempted=(), ...).not_attempted
```
(8 of the 9 matched tests already passed RED because Task 1's fold_run already counted update failures; the cancel accumulator gap was the live RED.)

## Verify-command results

- Task 1 `-k "has_failure or fold_run or worker_exception or exits_1_when"`: 14 passed, exit 0 (>=5 ids).
- Task 2 `-k "failed_update or update_error or survive_a_later_crash or all_skipped or headless_run_exits or cancel_mid_updates_keeps"`: 9 passed, exit 0 (>=9 required).
- `uv run pytest tests/test_session.py tests/test_execute_screen.py tests/test_wizard_app.py tests/test_setup.py -q --no-cov`: green after both tasks.
- All Task 1 acceptance-criteria greps matched (fold_run/has_failure x1, `except Exception` x1, `_partial_run(` x2, `fold_run(` x1 in each handler, old three-field condition gone, `has_failure` x3 in setup.py); Task 2's: `_run_updates` signature takes the accumulators, no `-> tuple[list[UpdateOutcome]` annotation remains, existing `test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped` passes unchanged.
- `make validate` green before each commit; `make test` green on the final tree (3498 passed, 4 skipped, coverage 95.90% >= 90%).

## Files Created/Modified
- `installer/session.py` - Summary failure fields + has_failure + fold_run
- `installer/execute_screen.py` - `_partial_run`, except-Exception in `_execute_worker`, accumulator-based `_run_updates`, red "Failed." status
- `installer/wizard_app.py` - UnifiedApp folds and accumulates the new fields
- `setup.py` - `summary.has_failure` at both exit decisions
- `tests/test_session.py`, `tests/test_execute_screen.py`, `tests/test_setup.py` - the twelve behavior tests from the plan's artifact list (one extra: `test_fold_run_drops_duplicate_update_failure_ids`, plus Task 1's clean-session exit-0 test)

## Decisions Made
- Recovered the quota-interrupted prior run's uncommitted Task 1 edits by reviewing them line-by-line against the plan's `<action>`, regenerating RED evidence, and committing them as Task 1's commit.
- Attempted-update bookkeeping lives in the worker's `finally` (extend `not_attempted` with un-attempted `_to_update` ids) so both cancel and crash share one path; a cancel sets no `error`, so it is not a crash.
- A test-spy wrapper on `UnifiedApp.on_install_run_finished` captures the posted `InstallRunFinished` messages (the Summary carries no raw update outcomes, so the posted lists are the only evidence).

## Deviations from Plan

### Auto-fixed Issues

**1. Test-file naming collision — duplicate `_RaisingUpdateService`**
- **Found during:** Task 2 (RED run)
- **Issue:** the new RED test file appended a second `_RaisingUpdateService` that shadowed an existing one (OSError-based) at tests/test_execute_screen.py:2161, breaking the unrelated existing test `test_blocked_update_error_from_run_live_is_reported`
- **Fix:** renamed the new class to `_CommandErrorUpdateService`
- **Files modified:** tests/test_execute_screen.py
- **Verification:** the existing test passes again; full suite green
- **Committed in:** a59951d (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (test collision, no production impact)
**Impact on plan:** None on scope; all plan files_modified respected.

## Issues Encountered
- The session started as a RESUME with uncommitted Task 1 edits in the tree and no record of prior progress ("none"); handled by verifying the edits against the plan, regenerating RED, and committing before starting Task 2.
- `ruff format` required one formatting pass on the new test blocks (validate caught it); root cause fixed by running the formatter, no check silenced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 20 can map `not_attempted`/`update_failed`/`crash_error` onto plan outcomes; `fold_run` is the single point to re-map.
- Plan 17-10 can return the same exit code from the doctor/fix/uninstall/guard routes now that `has_failure` exists.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
