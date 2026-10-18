---
phase: 20-install-plan-with-dispositions
plan: "31"
subsystem: install-planning
tags: [python, pytest, dependencies, reporting]
requires:
  - phase: 20-install-plan-with-dispositions
    provides: InstallPlan, RowOutcome, shared run report
provides:
  - Dependency checks for every runnable disposition; failed reinstall propagation reflects whether the present tool was lost
  - End-of-run detail notes for successful reconfiguration and crash details through _first_line
affects: [PLAN-04, PLAN-05, PLAN-06, install-plan]
actuals:
  tokens: 1100
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns: ["Disposition-specific unresolved status sets", "One shared done-notes renderer"]
key-files:
  created: []
  modified: [installer/session.py, tests/test_session.py, installer/render.py, tests/test_render.py]
key-decisions:
  - "An installed prerequisite is considered lost only when a reinstall actually ran and failed (FAILED or CHECKSUM_MISMATCH)."
  - "A prerequisite check runs before any runnable disposition, including UPDATE and RECONFIGURE."
  - "Reconfiguration details are emitted in the shared report only for successful rows; failed details remain on their row."
  - "Crash formatting tests the exception's first line, including RuntimeError(\"\\nx\")."
requirements-completed: [PLAN-04, PLAN-05, PLAN-06]
coverage:
  - id: D1
    description: "Prerequisite failures block dependent update/reconfiguration rows, and failed present-tool reinstalls correctly govern dependency propagation."
    requirement: PLAN-05
    verification:
      - kind: unit
        ref: tests/test_session.py#test_a_failed_prerequisite_stops_a_present_dependents_update_or_reconfigure
        status: pass
      - kind: unit
        ref: tests/test_session.py#test_a_reinstall_that_changed_nothing_leaves_the_tool_resolved
        status: pass
    human_judgment: false
  - id: D2
    description: "The shared run report prints a successful reconfiguration warning once and provides consistent first-line crash detail."
    requirement: PLAN-04
    verification:
      - kind: unit
        ref: tests/test_render.py#test_the_run_report_states_a_reconfigurations_detail_once
        status: pass
      - kind: unit
        ref: tests/test_session.py#test_a_crash_detail_is_the_type_and_the_first_line
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 31 Summary

**Runnable rows now respect unresolved prerequisites, and shared run reporting preserves reconfiguration warnings and precise crash details.**

## Performance

- **Duration:** approximately 25 minutes
- **Tasks:** 2
- **Files modified:** 4 implementation/test files

## Accomplishments

- Moved the dependency check ahead of dispatch for all runnable row dispositions. UPDATE and RECONFIGURE rows with unresolved prerequisites now yield the same `dependency_failed` outcome used by install-family rows.
- Added `_PRESENT_TOOL_LOST`: a row that started from an installed tool contributes to `unresolved` only when a reinstall fails with `FAILED` or `CHECKSUM_MISMATCH`. INSTALL and REPAIR retain the broader `_UNRESOLVED` behavior.
- Renamed and extended `render_update_notes` to `render_done_notes`; it now prints a successful RECONFIGURE detail once in the shared report, while failed detail remains only on its outcome row.
- Routed crash details through `_first_line`. A message-less exception and an exception whose first line is empty both use `{Type} failed`.

## Task Commits

1. **Task 1: prerequisite checks and present-tool reinstall resolution** — `c79b4c8` (`fix(20-31)`)
2. **Task 2: done notes and crash first-line formatting** — `bd31773` (`fix(20-31)`)
3. **Plan summary** — committed separately after the required final verification.

## TDD Evidence

**Task 1 RED** — `uv run pytest tests/test_session.py -q --no-cov -n 0 -k "present_dependents_update or changed_nothing"`: 4 failed, 2 passed. The UPDATE and RECONFIGURE rows incorrectly finished `done`; MANUAL_REQUIRED and NO_METHOD reinstall cases incorrectly made the dependent `dependency_failed`.

**Task 1 GREEN** — same command: `6 passed`.

**Task 2 RED** — `uv run pytest tests/test_render.py tests/test_session.py -q --no-cov -n 0 -k "detail_once or type_and_the_first_line"`: 4 failed, 1 passed. The successful reconfiguration detail was absent; crash strings for multi-line, empty, and leading-empty-line exceptions did not match the expected first-line/fallback format. The failed-reconfiguration report guard passed.

**Task 2 GREEN** — same command: `5 passed`.

## Verification Results

- Task 1 targeted suite: `uv run pytest tests/test_session.py tests/test_plan.py tests/test_execute_screen.py tests/test_app.py -q --no-cov -n auto` — passed; test_session collection floor: **87 → 93**.
- Task 2 targeted suite: `uv run pytest tests/test_render.py tests/test_session.py tests/test_execute_screen.py tests/test_app.py tests/test_layout_80x20.py -q --no-cov -n auto` — passed; test_render collection: **120 → 122**; test_session collection: **93 → 96**.
- Suppression-count gate — passed; no new suppression comments.
- Final `make validate` — passed (ruff, formatting, pyright, bandit, vulture, shellcheck).
- Final `make test` — **4923 passed, 4 skipped**, 96.03% coverage; coverage floor 90%.
- Pre-commit hooks passed on both implementation commits.
- CodeGraph identified the renderer's consumers before rename: `render_run_report` has six callers in `installer/execute_screen.py` and `installer/app.py`, plus tests in `tests/test_render.py`; the renamed `render_done_notes` is called by `render_run_report`, replacing the five former renderer call references in `installer/render.py` and its tests.

## Deviations from Plan

None. The orchestrator note's leading-empty-first-line exception case was included in the K6 parameterization.

## Issues Encountered

The first validation attempt found formatting/import-order issues in the new changes; these were corrected, then validation passed. The intentionally orchestrator-owned `.planning/config.json` remains modified and was not staged or changed by this work.

## Next Phase Readiness

No known blocker for the next phase. Working tree is expected to retain only the orchestrator-owned `.planning/config.json` modification.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
