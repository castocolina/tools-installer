---
phase: 20-install-plan-with-dispositions
plan: "22"
subsystem: install-planning
tags: [python, dependency-resolution, install-plan, pytest]
key-files:
  created: []
  modified: [installer/session.py, tests/test_plan.py]
key-decisions:
  - "Only unsettled blocked rows propagate dependency blocking; present blocked rows continue satisfying their dependency edges."
  - "Prune dragged runnable dependencies after propagation when no runnable requester needs them; preserve dependencies shared with a runnable requester."
  - "Blocked dependencies with pending state become WAIT rows; the generic unavailable fallback is fixed copy."
requirements-completed: [PLAN-01, PLAN-03, PLAN-07]
duration: 31 min
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 22 Summary

**Dependency dispositions now reflect settled health: only unsatisfied blockers propagate, unused dragged dependencies are skipped, and pending dependencies wait.**

## Accomplishments

- Task 1: Changed `build_plan` propagation to include only BLOCKED rows whose published state is unsettled, and only propagate through a dependent when its own state is unsettled. Added direct and dragged cases for a present, misconfigured dependency. Commit `f785046`.
- Task 2: Added a reverse-order prune for dragged dependencies not needed by any runnable requiring row; preserved shared dependencies still needed by a runnable requester. `_blocked_row` now returns WAIT for pending state and uses the fixed `not available on this platform` fallback. Commit `5965df9`.
- The added UI disposition copy is `not needed while {requester} is blocked`; it should be added to the UI-SPEC Disposition-copy amendment.

## TDD Evidence

**Task 1 RED** — `uv run pytest tests/test_plan.py -q --no-cov -n 0 -k "own_reason or plan_time_blocked"`:

```text
F. [100%]
AssertionError: (<Disposition.BLOCKED: 'blocked'>, 'needs pnpm') != (<Disposition.INSTALL: 'install'>, 'not installed')
1 failed, 1 passed
```

**Task 1 GREEN** — same focused command: `2 passed`; `uv run pytest tests/test_plan.py -q --no-cov -n 0`: `73 passed`.

**Task 2 RED** — `uv run pytest tests/test_plan.py -q --no-cov -n 0 -k "blocked_requester or blocked_tool_is_skipped or still_needed or method_waits or reads_not_available"`:

```text
FF.FF [100%]
4 failed, 1 passed
```
Failures showed the unnecessary pnpm and dependency-chain INSTALL rows, the method-less pending zsh BLOCKED instead of WAIT, and the unavailable fallback leaking resolver text. The shared-needed dependency guard passed.

**Task 2 GREEN** — focused command: `5 passed`; `uv run pytest tests/test_plan.py tests/test_session.py -q --no-cov -n auto`: `162 passed`.

## Verification

- `tests/test_plan.py` collected-test floor: start `72`; after Task 1 `73`; after Task 2 `78`.
- Task 1 targeted test file: passed; acceptance `_settled(state_of(` count: `3` (minimum 2).
- Task 2 required acceptance counts: `reason = blocked.reason` `0`; `f"not needed while {` `1`; fixed unavailable phrase `1`.
- Suppression-count gate: passed; no suppressions added.
- `make validate`: passed after resolving strict typing findings from the new pending-state early return.
- `make test`: passed, `4863 passed, 4 skipped`; coverage `96.02%`.
- Pre-commit hooks ran on both task commits and passed (ruff, format, pyright, bandit, vulture; shellcheck skipped for no matching files).

## Deviations from Plan

None. The test expectation for the blocked puppeteer's existing health reason uses the actual resolver-produced catalog detail (`puppeteer declares no install method.`), rather than the shorthand illustrative string in the behavior description; implementation behavior and contract remain unchanged.

## Issues Encountered

The first validation run identified three strict-pyright complaints about redundant `state is not None` checks after the WAIT early-return. The checks were removed while preserving the intended state typing; validation then passed. No host mutation, network operation, or container was needed.

## Next Phase Readiness

The install plan correctly treats state-settled presence independently from a row's own disposition and avoids installing prerequisites solely for blocked requesters. No known blocker for subsequent phase work.
