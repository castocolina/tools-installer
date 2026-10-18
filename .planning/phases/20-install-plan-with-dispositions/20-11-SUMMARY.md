---
phase: 20-install-plan-with-dispositions
plan: "11"
subsystem: installer
tags: [headless, install-plan, outcomes, version-refresh, setup]

# Dependency graph
requires:
  - phase: 20-03
    provides: "The shared _build_services composition for refresh, updates, and node-globals policy"
  - phase: 20-09
    provides: "The run-summary and outcome-row renderers used by the headless flow"
  - phase: 20-10
    provides: "The shared execute_plan engine, RowOutcome contract, and outcome-based exit helpers"
provides:
  - "Headless --all/--categories runs refresh and execute the same plan as the TUI"
  - "Headless state-check failures fail closed with not_attempted outcomes"
  - "setup.main gates PATH wiring, verification, and terminal sync on ran_anything and exits from outcomes"
affects: ["20-19 e2e parser", "headless install", "setup CLI"]

# Actuals (#2632)
actuals:
  tokens: 15057
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Headless and TUI execution share build_plan/execute_plan and outcome rendering"
    - "Lifecycle side effects and process status derive from RowOutcome values"

key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-11-SUMMARY.md
  modified:
    - installer/app.py
    - setup.py
    - tests/test_app.py
    - tests/test_setup.py

key-decisions:
  - "Reuse tests.state_doubles.presence_service rather than adding a duplicate frozen-service helper (reuse finding 20-17/17-1)."
  - "Keep Tasks 1 and 2 in one implementation commit because the setup caller cannot use the new run_wizard signature until both are ported."
  - "Hard-code reinstall=frozenset() in headless runs so --yes never reinstalls current tools."
  - "Fail closed when refresh raises or any planned row remains WAIT; report an empty exception using its type name."

patterns-established:
  - "Headless routes pass the shared refresh/update services into the plan executor."
  - "PATH wiring, verification, and terminal sync run only when ran_anything(outcomes) is true."

requirements-completed: [PLAN-06]

# Coverage metadata
coverage:
  - id: D1
    description: "Headless runs render and confirm the shared plan, execute it through execute_plan, and fail closed on unsettled state."
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_app.py#test_all_yes_prints_the_plan_installs_the_missing_tool_and_returns_outcomes
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_headless_reports_a_state_check_failure_and_runs_nothing
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_headless_reports_refresh_errors_without_messages
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_all_yes_updates_an_outdated_brew_tool_and_exits_zero
        status: pass
    human_judgment: false
  - id: D2
    description: "setup.main wires shared services, skips lifecycle side effects when no row ran, and derives its exit code from outcomes."
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_setup.py#test_headless_main_builds_services_once_and_exits_on_outcomes
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_headless_main_skips_path_wiring_and_sync_when_nothing_ran
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_headless_main_prints_aborted_when_the_run_is_declined
        status: pass
      - kind: integration
        ref: make validate && make test
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 11: Headless runs use the shared install plan and engine

**Headless `--all` and `--categories` runs now execute the TUI's refreshed plan, fail closed on unsettled state, and derive setup side effects and exit status from row outcomes.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-10-18T00:27:33-03:00
- **Completed:** 2026-10-18T01:09:09-03:00
- **Tasks:** 2
- **Files modified:** 4 implementation and test files (plus this summary)

## Accomplishments

- Replaced the headless two-step selection/install path with `_choose_tools`, one synchronous state refresh, `build_plan`, plan rendering, optional confirmation, `execute_plan`, and outcome rendering.
- Made refresh exceptions and lingering WAIT rows produce `not_attempted` outcomes without starting the engine; empty exception messages now use the exception type as the detail.
- Migrated `setup.main` to `_build_services`, gated PATH wiring/verification/terminal sync on `ran_anything`, and derived the process code with `exit_code`.
- Added coverage for all-current no-op behavior, confirmation and cancellation, TUI plan ordering, outdated brew updates, failed rows, blocked-plus-done exit behavior, setup service wiring, and state-check failures.
- Ported setup headless tests from `Summary` to `RowOutcome` lists.

## TDD RED Evidence

Task 1's new plan tests first failed against the old API:

```text
TypeError: run_wizard() got an unexpected keyword argument 'refresh'
```

The Task 2 seven-test selection produced the expected RED before setup/state-failure handling was implemented:

```text
FF.F...                                                                  [100%]
FAILED test_headless_main_builds_services_once_and_exits_on_outcomes
  AttributeError: 'list' object has no attribute 'has_failure'
FAILED test_headless_main_skips_path_wiring_and_sync_when_nothing_ran
  AttributeError: 'list' object has no attribute 'has_failure'
FAILED test_headless_reports_a_state_check_failure_and_runs_nothing
  OSError: probe failed
3 failed, 4 passed
```

A final edge-case test also caught an empty-message `OSError` raising `IndexError: list index out of range`; the test then passed after the error-detail fallback was corrected.

## Task Commits

1. **Task 1: Headless plan display, confirmation, and execution** - `9f297cf` (`feat`)
2. **Task 2: Setup service wiring and outcome-based exit behavior** - `9f297cf` (`feat`)

Tasks 1 and 2 share one implementation commit as required by the plan. This summary is committed separately as requested; its own commit hash is reported outside the file to avoid a self-referential hash.

## Files Created/Modified

- `installer/app.py` - Headless selection, refresh, shared plan/engine, confirmation, state-check failure handling, and outcome reports.
- `setup.py` - Shared service composition, ran-anything side-effect gate, and outcome-derived exit code.
- `tests/test_app.py` - New plan, update, failure, ordering, and state-check tests; existing callers ported.
- `tests/test_setup.py` - Headless setup behavior tests and migration from `Summary` to outcomes.
- `.planning/phases/20-install-plan-with-dispositions/20-11-SUMMARY.md` - Execution summary.

## Decisions Made

- Used the existing `presence_service` test double from `tests.state_doubles`; no duplicate helper was added.
- Kept the plan's single combined feature commit rather than committing Task 1 while `setup.main` still used the old interface.
- Preserved the two existing TUI `updates=updates` sites in `setup.py`; the headless route adds one more, so the total is 3.

## Deviations from Plan

- Removed two additional tests for the deleted catalog-selection seam: `test_catalog_seam_abort_returns_none_without_confirm` and `test_all_flag_bypasses_catalog_seam`. Both asserted behavior of the now-removed seam; equivalent user-facing cancel and `--all` behavior is covered by the new plan tests.
- Added a regression test and safe type-name fallback for refresh exceptions with empty messages, discovered during final review.
- The plan's `updates=updates` acceptance count of 1 was stale: HEAD already had two TUI sites. Verification used the exact baseline/current counts (2/3) and confirmed the headless call contributes exactly one.

**Total deviations:** 3 (two obsolete seam tests removed; one refresh-error edge case covered; one stale verification count corrected).
**Impact on plan:** No scope change to production behavior; the additions protect the planned fail-closed contract and preserve existing TUI service wiring.

## Issues Encountered

- `make validate` first requested Ruff formatting for the edited test files; `ruff format` resolved it. Pyright then caught a widened `str` in a hyphenated keyword test fixture; explicit typed outcomes fixed it.
- Two code-review subagent dispatches were rejected by the service with HTTP 429 (policy budget exceeded). A staged local diff review was performed; no external reviewer approval is claimed.

## Verification

- `make validate` - passed (Ruff, formatting, pyright, Bandit, Vulture, ShellCheck).
- `make test` - passed: **4,865 passed, 4 skipped**; coverage **96.04%** (90% required).
- Task acceptance checks passed: `tests/test_app.py` has 127 tests; `tests/test_setup.py` has 132 tests; all state/plan/setup acceptance greps passed with the pre-existing TUI `updates=updates` count accounted for.
- Implementation diff stat:

```text
 installer/app.py    | 153 +++++-------
 setup.py            |  47 ++--
 tests/test_app.py   | 706 +++++++++++++++++++++++++++++++++++-----------------
 tests/test_setup.py | 205 +++++++++++----
 4 files changed, 722 insertions(+), 389 deletions(-)
```

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Headless execution is aligned with the shared plan and engine.
- Plan 20-19 remains responsible for updating the container e2e parser in the same wave; it was not modified here.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
