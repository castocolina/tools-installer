---
phase: 20-install-plan-with-dispositions
plan: "20"
subsystem: ui
tags: [textual, install-plan, skill-packs, state-refresh, pytest]
requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: VersionRefreshService.refresh and refresh_skills, ToolState, skill-pack status probes
provides:
  - Headless install planning settles version and skill-pack state before building dispositions
  - Review wait joins both refresh operations, reports all failures, and safely ignores late messages
  - Shared skill-pack test double and regression tests for both paths
affects: [phase-20-install-plan-with-dispositions, install-plan, review-wait]
actuals:
  tokens: 2800
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - "Join skill-pack status refresh immediately after the version refresh in the same state-check pass"
    - "Always post worker settlement from finally; guard late UI messages before repaint"
key-files:
  created: [.planning/phases/20-install-plan-with-dispositions/20-20-SUMMARY.md]
  modified: [installer/app.py, installer/execute_screen.py, tests/state_doubles.py, tests/test_app.py, tests/test_execute_screen.py]
key-decisions:
  - "Keep headless skill and version refreshes within its existing error-handling try block."
  - "Render only the first line of a refresh failure and ignore matching-token settlements after a run starts or finishes."
requirements-completed: [PLAN-06, PLAN-07]
coverage:
  - id: D1
    description: "Headless state pass settles skill packs before it builds or runs the install plan."
    requirement: PLAN-06
    verification:
      - kind: integration
        ref: tests/test_app.py#test_headless_all_settles_skill_packs_before_planning
        status: pass
    human_judgment: false
  - id: D2
    description: "Review state wait settles both refresh operations, handles exceptional failures, and cannot repaint an active or completed run."
    requirement: PLAN-07
    verification:
      - kind: automated_ui
        ref: tests/test_execute_screen.py#wait-settlement regression tests
        status: pass
    human_judgment: false
# Metrics
duration: approximately 30min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 20 Summary

**Headless and Textual install-plan waits now settle skill-pack state, recover from uncaught refresh errors, and protect completed runs from late repaint.**

## Performance

- **Duration:** approximately 30 minutes
- **Tasks:** 2
- **Files modified:** 5 implementation/test files, plus this summary

## Accomplishments

- Task 1 added `refresh.refresh_skills(tools)` to the headless synchronous state pass, within the existing exception handling, so skill-pack rows are settled before planning.
- Task 2 made the review wait join `refresh` and `refresh_skills` in order, always post `StateSettled` from `finally`, report uncaught exceptions using their first line (or type name), ignore late messages after start/finish, and display only the first line of a state-check error.
- Added a public skill-pack double plus one headless and four Textual pilot regression tests.

## Task Commits

1. **Task 1: headless settles skill packs before planning** — `f5f879b` (`fix(20-20): headless settles skill packs before it plans`)
2. **Task 2: review wait settles safely and avoids repainting runs** — `90a6008` (`fix(20-20): the review's state wait always settles and never repaints a run`)
3. **Plan summary** — this documentation commit, recorded in git history.

## TDD Evidence and Verification

### Task 1

- **RED:** `uv run pytest tests/test_app.py -q --no-cov -n 0 -k settles_skill_packs` failed with `State check failed: no state for superpowers`; the plan then showed both tools as `not attempted`.
- An initial fixture-construction attempt also failed because the test double used the wrong `SkillLifecycle` constructor shape. The fixture was corrected to use the model's required lifecycle fields before confirming the intended behavioral RED.
- **GREEN:** the same targeted test passed after adding `refresh_skills`. `uv run pytest tests/test_app.py -q --no-cov -n 0` passed (131 tests); collected floor ended at 131 (required >=131).
- `make validate` passed before the task commit.

### Task 2

- **RED:** `uv run pytest tests/test_execute_screen.py -q --no-cov -n 0 -k "before_its_host_check or raising_value_error or late_settle or first_line_only"` failed all four new cases: skill pack remained WAIT, uncaught `ValueError` left the status in Waiting and retry inert, late settlement repainted a finished run, and the second line of a multiline error was displayed.
- **GREEN:** the same four tests passed. `uv run pytest tests/test_execute_screen.py -q --no-cov -n auto -k "wait or settle or checking or state_check or publication"` passed (15 tests). Full touched-file run `uv run pytest tests/test_app.py tests/test_execute_screen.py -n auto -q --no-cov` passed (174 tests); collect floor ended at 128 (required >=128). Suppression count did not increase.
- `make validate` passed before the task commit.

### Final plan verification

- `make validate` passed.
- `make test` passed: **4,844 passed, 4 skipped**, coverage **96.01%** (90% required).
- Final review: self-review of `.superpowers/sdd/20-20-PLAN/review-7dedc98..90a6008.diff` (no subagent tool available); no findings.

## Deviations from Plan

- None in shipped behavior or scope. The first fixture draft did not match the actual required `SkillLifecycle` constructor and was corrected before the meaningful red/green cycle.

## Issues Encountered

- The headless behavior exposed the expected stale skill-pack state before implementation. During Task 2, the pilot tests were refined to hold the live probe and observe a truly pending pack state; this ensured they tested the specified wait behavior rather than an already-settled state.
- No known issue remains for the orchestrator. The requested container e2e was not run; the plan assigns that proof to the orchestrator after the waves.

## User Setup Required

None.

## Next Phase Readiness

PLAN-06 and PLAN-07 gap closures are implemented and covered. The orchestrator can run the planned container e2e proof.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
