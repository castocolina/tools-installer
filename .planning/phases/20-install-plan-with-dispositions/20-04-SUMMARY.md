---
phase: 20-install-plan-with-dispositions
plan: "04"
subsystem: installer
tags: [install-plan, dispositions, ownership, pytest, tdd]
requires:
  - phase: 20-install-plan-with-dispositions
    provides: "Resolution closure/requester/blocked data (20-01) and update refusal/ownership labels (20-02)"
provides:
  - "Disposition and PlanRow model, shared WORDS/RESULT_WORDS vocabulary, and pure build_plan"
  - "Dragged and blocked dependency rows with first-requester attribution"
  - "Reinstall gating for installer-owned direct current rows and WAIT rows for unpublished state"
affects: [20-05, 20-06, 20-07, 20-10, 20-11]
actuals:
  tokens: 172
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns:
    - "Plan is derived solely from published state through state_of; no subprocess or network probing"
    - "Shared _count_line helper supports review_counts and later summary_counts (reuse finding 07-2)"
key-files:
  created:
    - tests/test_plan.py
  modified:
    - installer/session.py
    - tests/state_doubles.py
key-decisions:
  - "Rows follow resolver closure order, then blocked rows, without another sort"
  - "Only direct installer-owned current rows are reinstall eligible; only the explicit reinstall set changes their disposition"
  - "Unknown ownership remains a SKIP with explicit reason; pending state remains WAIT"
requirements-completed: [PLAN-01, PLAN-02, PLAN-04]
duration: 24min
completed: 2026-10-17
status: complete
---

# Phase 20 Plan 04: Install plan with dispositions

**A pure, state-driven plan now assigns one disposition and reason to each reached tool, using a shared vocabulary and explicit reinstall eligibility.**

## Task commits

1. **Task 1: plan model, vocabulary, pure builder** — `87cdd3d` (`feat(20-04): Disposition, PlanRow, WORDS and a pure build_plan`)
2. **Task 2: dragged and blocked dependencies** — `c1bd77e` (`feat(20-04): dragged dependencies plan once under their first requester`)
3. **Task 3: reinstall and pending-state behavior** — `493d38f` (`feat(20-04): reinstall only from the r set; pending state is a wait row`)

## Accomplishments

- Added `Disposition`, frozen `PlanRow`, `Result`, `Words`, `WORDS`, and `RESULT_WORDS` in `installer/session.py`.
- Added `build_plan`, which calls `resolve_dependencies` once, uses `state_of` as the only state input, preserves resolver closure order, and starts no subprocess.
- Added `plan_state` in `tests/state_doubles.py` and 20 passing plan test cases, including dragged dependency ordering/requester, blocked dependencies, current/missing tier mixes, ownership copy, reinstall gating, and WAIT state.
- Reused the shared `_count_line` helper for review word counts, as directed by 20-REUSE finding 07-2.

## TDD RED evidence

- **Task 1:** `uv run pytest tests/test_plan.py -q --no-cov` failed during collection with `ImportError: cannot import name 'RESULT_WORDS' from 'installer.session'`.
- **Task 2:** `uv run pytest tests/test_plan.py -q --no-cov -k "dragged or dependency or needed or mixing"` failed on the not-yet-implemented dragged reason (`not installed` instead of `needed by mmdc`), missing blocked row (`KeyError: 'z'`), and current-row behavior.
- **Task 3:** `uv run pytest tests/test_plan.py -q --no-cov -k "reinstall or off_policy or unknown_owner or wait or pending"` failed on current-row reasons/reinstall eligibility, unsupported test builder arguments, and unknown-owner reason before the behavior was implemented.

## Verification

- Final `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py -n auto -q --no-cov`: passed.
- Final `uv run pytest tests/test_plan.py -q --no-cov`: 20 passed.
- Final `uv run python -c "import installer.version_status, installer.session; print('ok')"`: printed `ok`.
- `make validate`: passed on the final task tree and pre-commit passed for every task commit.
- `make test`: passed after each task commit; final run: 4681 passed, 4 skipped, 95.98% coverage.
- Plan anchors: one each of `Disposition`, `PlanRow`, `build_plan`, `WORDS`, `RESULT_WORDS`, and `plan_state`; one `sorted(` in `installer/session.py`; required copy occurrences each exactly one; no `(r: reinstall)` suffix in `session.py`.
- Suppression count did not grow.

## Deviations

- Reuse finding 07-2: implemented `_count_line(words, order)` and used it from `review_counts`, so later `summary_counts` can reuse the same join/count behavior rather than duplicate it.
- Task 2's tier-mix test initially asserted `can_reinstall=True`; removed that assertion from Task 2 to keep its GREEN scope independent of Task 3. Task 3 now tests the eligibility directly.
- Added public `MACOS` alias to the test double module because pyright forbids importing private `_MACOS` across test modules.
- `test_plan.py` has 20 executed cases rather than the plan's 18 test floor: the tier-mix test is parametrized over all three tiers and the explicitly specified Task 3 tests total more cases than the initial artifact estimate.

## Issues encountered

- The unavailable dependency test was corrected to construct its state through the same `pass_state` path as production (brew-only tool on a platform without brew); this ensures the unavailable reason is the actual `ToolState.reasons[0]`.
- No unresolved issues. `.planning/config.json` remains modified by the orchestrator and was not staged or edited.

## Next phase readiness

`installer.session` now provides the plan model and builder required by 20-05's health/owner matrix and later render/execute plans.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-17*
