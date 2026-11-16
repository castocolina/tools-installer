---
phase: 20-install-plan-with-dispositions
plan: "24"
subsystem: installer
tags: [python, textual, installer, install-plan]

# Dependency graph
requires:
  - phase: 20-22
    provides: Install plan and disposition execution used by the headless and TUI routes
provides:
  - Shared presence-aware install seam across headless and TUI execution
  - Accurate exit handling for PATH wiring and audit failures
  - Per-row terminal-sync failures and run-aware manual handoffs
  - Latest-wins app error/update outcomes and mutation-gated invalidation
affects: [phase-20, installer, install-plan]

# Actuals
actuals:
  tokens: 2400
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Catch live terminal-sync exceptions at the step boundary and preserve batch execution
    - Treat handoff-only manual rows as no-op for run-level effects

key-files:
  created: []
  modified:
    - setup.py
    - installer/session.py
    - installer/wizard_app.py
    - tests/test_setup.py
    - tests/test_session.py
    - tests/test_wizard_app.py

key-decisions:
  - "Headless and TUI installation use the same install callable bound to the refresh service's published presence state."
  - "A manual reconfigure row counts as run only if its reviewed steps include an executable command operation."
  - "Run errors are replaced only by a run that executed work or had an uncaught run error; otherwise prior PATH errors remain actionable."

patterns-established:
  - "Run-level side effects are guarded by ran_anything(outcomes), not merely a handoff result."
  - "Direct successful updates record a done outcome so latest-wins clears stale failures."

requirements-completed: [PLAN-04, PLAN-06]
coverage:
  - id: D1
    description: Headless and TUI execution share the presence-bound install seam; headless PATH failures produce actionable exit code 1.
    requirement: PLAN-04
    verification:
      - kind: unit
        ref: tests/test_setup.py#test_build_services_binds_the_update_service_to_the_refresh_service
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_headless_post_run_failure_exits_1_with_the_reason
        status: pass
    human_judgment: false
  - id: D2
    description: Terminal-sync row errors, manual handoff run accounting, and latest-wins app bookkeeping behave as specified.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_session.py#test_a_raising_terminal_sync_step_fails_its_row_and_the_batch_continues
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_a_successful_u_after_a_failed_u_clears_the_failure
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_a_run_where_nothing_ran_does_not_invalidate
        status: pass
    human_judgment: false

duration: 75min
completed: 2026-10-18
status: complete
---

# Phase 20: Install Plan with Dispositions Summary

**Headless and TUI installs now share presence-aware execution, while row and run bookkeeping accurately reflects errors, handoffs, and completed updates.**

## Performance

- **Duration:** approximately 75 minutes
- **Started:** 2026-10-18T07:27:00-03:00
- **Completed:** 2026-10-18T08:42:35-03:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Bound the install callable to the refresh service's presence predicate and supplied it to both app composition and the headless route.
- Made headless PATH wiring and audit failures report their reason, render troubleshooting help, and exit 1; removed the duplicate decline line.
- Converted terminal-sync exceptions into failed row outcomes while allowing subsequent rows to run; handoff-only manual reconfigure rows no longer trigger run-level side effects.
- Made run errors latest-wins when a run attempted wiring/audit, recorded successful direct updates as done, and gated invalidation on actual work.

## Task Commits

1. **Task 1: headless shares the install seam and exits on run-level errors** - `e268ca6`
2. **Task 2: terminal-sync failure and handoff run accounting** - `ff856d6`
3. **Task 3: latest-wins errors and update outcomes; gate invalidation** - `20e97ec` (follow-up documentation clarification: `eb15872`)

**Plan metadata:** the `docs(20-24)` summary commit.

## Files Created/Modified
- `setup.py` - shared install seam and headless post-run error handling.
- `installer/session.py` - terminal-sync failures and executed-work accounting.
- `installer/wizard_app.py` - latest-wins run/update outcomes and conditional invalidation.
- `tests/test_setup.py` - headless composition, error and decline coverage.
- `tests/test_session.py` - row-failure and manual-handoff behavior coverage.
- `tests/test_wizard_app.py` - run-error, direct-update and invalidation coverage.

## Decisions Made
- Kept the run error history when an outcome batch executed no work and had no run-level exception; a no-op must not erase an outstanding PATH failure.
- Counted reconfigure manual outcomes as executed only when a step has argv or is a terminal-sync/pnpm-group operation.

## Deviations from Plan

None. The plan's requested tests and outcomes were implemented. During validation, existing wizard tests required their install/service doubles to reflect the now-shared presence state; their fixtures were adjusted without changing product scope.

## Issues Encountered
- Initial wizard tests for run-level invalidation used tools already marked present, so the new `ran_anything` behavior correctly skipped installation. The relevant tests were corrected to model an absent tool, then passed.
- The repository-configured `.planning/config.json` modification was present at start and preserved untouched.

## Verification
- Task 1 RED: targeted tests failed on the three-value service tuple, missing install keyword, and headless exception escape; after implementation the focused tests passed. Setup collection was 154 (start 151), below the plan's stated 155 floor; this is a recorded verification discrepancy, not a claim that the floor passed.
- Task 2 RED: 3 failures covered manual INSTALL accounting, a raising terminal-sync step, and handoff-only manual reconfigure; GREEN focused and session/plan suites passed. `tests/test_session.py` collection: 87 (start 84).
- Task 3 RED: 3 failures for retained run errors, successful update latest-wins, and invalidation on no work; GREEN focused tests and setup/wizard suite passed. `tests/test_wizard_app.py` collection: 315 (start 311).
- `make validate`: passed on the final implementation tree, including the follow-up documentation clarification.
- `make test`: passed on the implementation tree, 4,886 passed and 4 skipped; total coverage 96.00%.

## Next Phase Readiness
- Phase 20 plan 24 requirements PLAN-04 and PLAN-06 are covered and all three task commits are on `main`.
- The orchestrator-owned `.planning/config.json` remains modified and unstaged/uncommitted.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
