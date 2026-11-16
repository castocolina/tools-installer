---
phase: 20-install-plan-with-dispositions
plan: 07
subsystem: infra
tags: python, install-plan, execution, updates, tdd, pytest

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: settled Disposition values, PlanRow ownership capture, and the existing update service contract
provides:
  - execute_plan, RowOutcome, and RunContext as the sole production engine owner
  - deterministic outcome views for exit status, retention, activity, and summary counts
  - repair/reinstall force handling composed beneath sensitive-action confirmation
  - dependency failure propagation and update-service orchestration through the plan workflow
affects: [20-08, 20-09, 20-10, execute-screen, wizard-app, post-install]

# Actuals (#2632)
actuals:
  tokens: 8366
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - total engine-status mapping with a typed Result vocabulary
    - pure outcome views derived from the one row-to-outcome invariant
    - in-flight latch cleanup with finally while reusing UpdateService

key-files:
  created: []
  modified:
    - installer/session.py
    - tests/state_doubles.py
    - tests/test_session.py

key-decisions:
  - "Reuse UpdateService as RunContext.updates rather than introducing a duplicate runner protocol."
  - "Compose force repair under with_sensitive_confirm so the public install protocol remains unchanged."
  - "Treat a failing callback as a row crash, preserve one outcome per row, and mark later rows not attempted."
  - "Let failed installs poison dependents, while update failures are truthfully returned without blocking dependent installs."

patterns-established:
  - "Outcome views: exit_code, retained, ran_anything, and summary_counts read only the returned RowOutcome list."
  - "Total status mapping: every InstallStatus member maps to exactly one plan Result."
  - "Offline execution doubles: RunRecorder and ScriptedUpdates exercise the real engine and update latch without host access."

requirements-completed: [PLAN-04, PLAN-05, PLAN-06]

coverage:
  - id: D1
    description: "execute_plan runs every install-class disposition and returns exactly one outcome per row."
    requirement: PLAN-04
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_execute_plan_returns_one_outcome_per_row_in_plan_order"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_repair_and_reinstall_rows_force_repair"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_force_repair_composes_under_sensitive_confirm"
        status: pass
    human_judgment: false
  - id: D2
    description: "Updates, dependency failures, crashes, cancellation, and mismatch choices produce deterministic outcome views."
    requirement: PLAN-05
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_exit_code_retained_and_ran_anything_are_pure_views_of_the_list"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_summary_counts_fixed_order_and_nothing_selected"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_update_row_runs_through_the_update_service_with_the_rows_ownership"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_install_failure_blocks_dependents_down_a_chain"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_a_crashing_row_is_crashed_and_the_rest_not_attempted"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_should_continue_false_marks_the_rest_not_attempted"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_mismatch_retry_skip_and_fallback_match_run_installs"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every engine status maps to exactly one Result with complete summary vocabulary."
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_every_install_status_maps_to_one_result"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_result_words_cover_every_non_done_result_the_engine_can_produce"
        status: pass
    human_judgment: false

# Metrics
duration: 16min
completed: 2026-10-17
status: complete
---

# Phase 20 Plan 07: Install Plan Execution Summary

**`execute_plan` now executes settled plan rows through the real install and update services and returns one truthful, dependency-aware `RowOutcome` per row.**

## Performance

- **Duration:** ~16 minutes of recorded execution time
- **Started:** 2026-10-17T21:23:48Z
- **Completed:** 2026-10-17T21:41:13Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Added `execute_plan`, `RowOutcome`, and `RunContext` while preserving the existing `Install` protocol and composition-root injection path.
- Implemented SKIP and BLOCKED handling, WAIT preflight rejection, repair/reinstall force behavior, sensitive confirmation composition, checksum mismatch decisions, dependency propagation, update-service orchestration, cancellation, and crash containment.
- Established pure outcome views `exit_code`, `retained`, `ran_anything`, and `summary_counts`, all derived from the returned outcome list.
- Added a total `InstallStatus`-to-`Result` table and exercised every status with focused tests.
- Extended offline test doubles with `RunRecorder` and an `UpdateService` subclass that reuses the real in-flight latch.

## Task Commits

Each task was committed atomically:

1. **Task 1: execution core and outcome views** — `e5a34eb` (feat)
2. **Task 2: updates, dependency failures, crashes, and cancellation** — `b858c38` (feat)
3. **Task 3: total engine-status mapping** — `ecab775` (test)

**Plan metadata:** pending summary commit (`docs(20-07): plan summary`)

_Note: The shared dispatcher required in Task 1 introduced update dispatch earlier than the task-by-task outline. Task 2's behavioral RED test subsequently exposed and corrected its failed-update mapping before the Task 2 commit._

## Files Created/Modified
- `installer/session.py` — execution engine, outcome dataclasses, result mapping, and outcome-derived views
- `tests/test_session.py` — TDD coverage for all execution and result-mapping contracts
- `tests/state_doubles.py` — `RunRecorder` and `ScriptedUpdates` offline doubles

## Decisions Made
- Reused `UpdateService` directly because it already owns platform, runner, tag resolution, catalog, ownership, and the in-flight latch.
- Wrapped `_with_force` beneath `with_sensitive_confirm` to add the repair keyword without changing the shared `Install` protocol.
- Preserved row-captured ownership by passing `UpdateTarget(tool, row.ownership)` to the service and releasing the latch in `finally`.
- Used the shared `_count_line` helper so plan summaries format consistently with plan-review counts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added update dispatch during Task 1**
- **Found during:** Task 1 (execution core)
- **Issue:** The single dispatcher had to compile and route all non-UPDATE dispositions without leaving an unreachable interim path for UPDATE rows.
- **Fix:** Introduced update dispatch in Task 1, then used Task 2's focused failing-update RED test to establish the required `failed` mapping before its commit.
- **Files modified:** `installer/session.py`, `tests/test_session.py`
- **Verification:** Targeted execution and update tests, `make validate`, and full `make test` passed.
- **Committed in:** `e5a34eb` and `b858c38`

**2. [Rule 1 - Missing Critical] Preserved repair-only install arguments**
- **Found during:** Task 1 (repair/reinstall composition)
- **Issue:** The existing real `install_tool` entry point in the source tree requires the repair keyword argument, while the narrower `Install` protocol intentionally omits it.
- **Fix:** Added a dedicated `RepairSensitiveInstall` protocol for `RunContext.install` and passed `repair` explicitly through the force wrapper.
- **Files modified:** `installer/session.py`
- **Verification:** Force-order tests and Pyright passed.
- **Committed in:** `e5a34eb`

---

**Total deviations:** 2 auto-fixed (1 blocking sequencing adjustment, 1 critical interface compatibility correction)
**Impact on plan:** Both adjustments preserved the requested contracts and final scope. The public `Install` protocol and composition root remained unchanged; no additional files or features were introduced.

## Issues Encountered
- A project-local review subagent could not be dispatched because the configured reviewer model returned an upstream access error. The final review was performed as a self-review against the plan and complete diff, with no Critical or Important findings.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 20-08 can now replace the handcrafted `execute_screen._run` loop with the session-owned outcome contract.
- Plan 20-09 can drive the composition root from `execute_plan` outputs and the established pure views.
- No deferred review findings, failing tests, or host-touching verification remains.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-17*
