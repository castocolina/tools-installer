---
phase: 20-install-plan-with-dispositions
plan: "29"
subsystem: install-plan
tags: [python, dispositions, plan-review, rendering]
requires:
  - phase: "20-28"
    provides: [InstallPlan, build_plan, execute_plan, render_plan]
provides:
  - One shared RUNNABLE disposition set for plan pruning, TUI review keys, and headless consent
  - One PlanRow maker and one off-policy reason helper; removed dead selection helpers
  - A 20-cell minimum fold width when continuation space permits
affects: [phase-20-install-plan-with-dispositions, plan-review]
actuals:
  tokens: 4571
  tasks: 3
  commits: 4
tech-stack:
  added: []
  patterns:
    - Shared closed disposition set across decision and consent paths
    - Typed local row maker with explicit optional PlanRow fields
    - Bounded minimum fold width constrained by continuation room
key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-29-SUMMARY.md
  modified:
    - installer/session.py
    - installer/execute_screen.py
    - installer/app.py
    - tests/test_plan.py
    - installer/selection.py
    - tests/test_selection.py
    - installer/render.py
    - tests/test_render.py
key-decisions:
  - "RUNNABLE is defined beside Disposition in installer/session.py and consumed by all three plan/review/headless paths."
  - "The local row maker uses typed can_reinstall and steps parameters instead of untyped arbitrary keyword expansion."
  - "Dead selection helpers and their four tests were removed as permitted by the plan; the test floor moves from 10 to 6."
requirements-completed: [PLAN-01, PLAN-06]
coverage:
  - id: D1
    description: The engine-runnable dispositions are named once and shared by build_plan, TUI review keys, and headless consent.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "tests/test_plan.py::test_runnable_is_every_disposition_an_engine_runs; tests/test_execute_screen.py; tests/test_app.py"
        status: pass
    human_judgment: false
  - id: D2
    description: Plan rows use a common maker, off-policy explanations are centralized, and unused selection-flow helpers are removed.
    requirement: PLAN-01
    verification:
      - kind: unit
        ref: "tests/test_plan.py::test_an_outdated_off_policy_row_names_both_owners; tests/test_plan.py; tests/test_selection.py"
        status: pass
      - kind: other
        ref: "AST PlanRow-constructor check and installer.selection import check"
        status: pass
    human_judgment: false
  - id: D3
    description: A long reason after an already-full first line wraps at a readable width without exceeding the available continuation room.
    requirement: PLAN-01
    verification:
      - kind: unit
        ref: "tests/test_render.py::test_fold_reason_keeps_a_readable_width_after_a_full_first_line"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py and tests/test_layout_80x20.py"
        status: pass
    human_judgment: false
# Metrics
duration: "about 50 minutes"
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 29 Summary

**The shared install plan now has one runnable-disposition set, one row-construction path, and readable reason folding at narrow widths.**

## Performance

- **Duration:** about 50 minutes
- **Started:** 2026-10-18T11:27:31-03:00 (Task 1 base commit timestamp)
- **Completed:** 2026-10-18
- **Tasks:** 3
- **Files modified:** 8 implementation/test files (plus this summary)

## Accomplishments

- Defined `RUNNABLE` once in `installer/session.py`; `build_plan`, `ExecuteScreen._idle_keys`, and `app.run_wizard` now share it.
- Routed `_row` branches through one typed local maker and both off-policy branches through `_off_policy_reason`; removed `Choice`, `categories`, `tools_in`, and their four dead tests.
- Added a continuation-width floor to `fold_reason`, preventing one-character-per-line wrapping when the first line is already full.

## Task Commits

1. **Task 1: one runnable set for plan, review, and headless** — `b6fa8c3` (`refactor(20-29)`).
2. **Task 2: one row maker and off-policy reason; remove dead selection helpers** — `cdace86` (`refactor(20-29)`).
3. **Task 3: readable narrow-width reason folding** — `83bc530` (`fix(20-29)`).

## Files Created/Modified

- `installer/session.py` — exports `RUNNABLE`, centralizes off-policy reason text, and builds `_row` results with one local maker.
- `installer/execute_screen.py` — consumes `RUNNABLE` for the review's idle keys.
- `installer/app.py` — consumes `RUNNABLE` for the headless consent check.
- `tests/test_plan.py` — pins the runnable set and outdated off-policy owner wording.
- `installer/selection.py` — retains only `select_tools` and `unstaged_recommends`.
- `tests/test_selection.py` — removes the four tests for deleted helpers; six live tests remain.
- `installer/render.py` — enforces the readable fold-width floor.
- `tests/test_render.py` — adds two narrow-width regression cases.
- `.planning/phases/20-install-plan-with-dispositions/20-29-SUMMARY.md` — this execution record.

## Verification Results

- **Task 1:** RED command `uv run pytest tests/test_plan.py -q --no-cov -n 0 -k runnable_is_every` produced `ImportError: cannot import name 'RUNNABLE' from 'installer.session'` (expected before implementation). GREEN command `uv run pytest tests/test_plan.py tests/test_execute_screen.py tests/test_app.py -q --no-cov -n auto` completed at `[100%]`; the focused runnable test also completed at `[100%]`. Collected plan tests increased from baseline 78 to 79. `make validate && make test` passed: 4909 passed, 4 skipped, 95.99% coverage.
- **Task 2:** The new outdated/off-policy guard passed before and after refactoring. The before and after guard runs both used `uv run pytest tests/test_plan.py tests/test_session.py tests/test_selection.py -q --no-cov -n auto`; both completed at `[100%]` (exit 0). The full command added `tests/test_catalog_tui.py`: `uv run pytest tests/test_plan.py tests/test_session.py tests/test_selection.py tests/test_catalog_tui.py -q --no-cov -n auto`. It and the AST constructor and import checks passed. Counts: `test_plan.py` 80, `test_selection.py` 10 → 6 (the plan-sanctioned reduction), and `test_session.py` 87. `make validate && make test` passed: 4906 passed, 4 skipped, 96.00% coverage.
- **Task 3:** RED command `uv run pytest tests/test_render.py -q --no-cov -n 0 -k readable_width` showed 36 folded lines against a maximum of 3 (`1 failed, 1 passed`). GREEN command `uv run pytest tests/test_render.py -q --no-cov -n 0 -k readable_width` completed at `[100%]` with both cases passing; the broad command `uv run pytest tests/test_render.py tests/test_execute_screen.py tests/test_layout_80x20.py -q --no-cov -n auto` also completed at `[100%]`. The suppression-count gate passed. Collected render tests increased from 118 to 120. `make validate && make test` passed: 4908 passed, 4 skipped, 96.00% coverage.
- Pre-commit hooks passed on all three task commits. No container or network operation was needed.

### TDD RED Evidence

Task 1, with its production edits temporarily reversed while retaining the new test:

```text
$ uv run pytest tests/test_plan.py -q --no-cov -n 0 -k runnable_is_every
ImportError: cannot import name 'RUNNABLE' from 'installer.session'
1 error during collection; expected before implementation.
```

Task 2, the guard command before and after the refactor:

```text
$ uv run pytest tests/test_plan.py tests/test_session.py tests/test_selection.py -q --no-cov -n auto
[all tests passed; exit 0]
$ uv run pytest tests/test_plan.py tests/test_session.py tests/test_selection.py -q --no-cov -n auto
[all tests passed again after the refactor; exit 0]
```

Task 3, before changing `fold_reason`:

```text
$ uv run pytest tests/test_render.py -q --no-cov -n 0 -k readable_width
F. [one failure, one guard case passed]
AssertionError: assert 36 <= 3
1 failed, 1 passed.
```

## Decisions Made

- Kept the local maker strictly typed with explicit `can_reinstall` and `steps` keyword parameters. It fills the shared row fields without introducing an untyped `**extra` boundary.
- Deleted the four tests that exercised removed selection helpers, as explicitly authorized by the plan; no live selection behavior was removed.

## Kept Items

- The `row.ownership is None` UPDATE guard in `execute_plan` remains for strict pyright narrowing. Replacing it with `assert` would trigger Bandit B101; a cast would hide a real `None` case.
- The crash detail is not rewritten through `_first_line`: for an empty exception message, that helper would turn `crashed — RuntimeError: ` into the misleading `crashed — RuntimeError: RuntimeError failed`.

## Deviations from Plan

None in implementation or files changed. The project-local `task-brief` helper could not extract this plan's XML `<task><name>` format, so the already-read task sections were followed directly; this tooling fallback is recorded under rulings below.

## Rulings I Made

- **Task brief extraction:** used the exact task sections in `20-29-PLAN.md` after `task-brief` reported no matching Markdown `## Task N` heading. The plan itself remained the source of truth; cost if wrong: a detail visible only to the helper's expected heading format might have been missed, but the full plan was already read and executed.

## Final Review and Issues for the Orchestrator

- A fresh subagent review could not run: both review-agent dispatches returned `429 Policy budget exceeded`. I performed a separate author self-review of the full `9e566e2..83bc530` diff package against the plan and spec; I found no Critical, Important, or Minor issues and had no behavior to set aside. This is weaker than an independent review.
- `make validate` initially flagged Ruff SIM300 in the new test and then requested formatting; the assertion was corrected and Ruff formatting applied before the Task 1 commit. All subsequent task gates passed.
- The orchestrator-owned `.planning/config.json` remains intentionally modified and unstaged. It was not edited, staged, or reverted by this plan executor.
- After the summary commit and scratch cleanup, `git status --short --untracked-files=all` showed only `M .planning/config.json`; no untracked files created by this run remain.

## User Setup Required

None — no external service configuration or new dependency is required.

## Next Phase Readiness

The three tasks are complete and the targeted plan requirements are covered. The only outstanding process caveat is that the final code review was an author self-review because the reviewer service was over budget.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
