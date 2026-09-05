# Phase 3 Plan 01: Install Failure Propagation

Implements REQ-install-failure-propagation: a tool whose `requires` names an id that
failed (or was itself skipped) earlier in the same run is never handed to the
installer. It is reported as `dependency-failed` with `blocked_by`, and the summary
line explains why.

## Task Commits

1. **Task 1: Skip dependents when a required tool fails** - `05ad2e59a1ef9a8b177098f05504b26dfa5b6980` (feat)
2. **Task 2: Pin skip contract across statuses and chains** - `1df8233dda3aaa4c281f796256481ab849445788` (test)
3. **Task 3: Report skipped dependents in the install summary** - `244d730dadc83b72ea96907223ecf45dd2527a2b` (feat)
4. **Fix: Gate skip transitivity on `_UNRESOLVED` membership** - `6618cebbd69540dd52dafb0b2499f420fa626a6d` (fix)

## Deviations from Plan

- The skip path originally added failed ids straight into the `unresolved` set without
  routing through `_UNRESOLVED` status membership, so a chain test (drop
  `DEPENDENCY_FAILED` from `_UNRESOLVED` and confirm transitivity breaks) would not have
  been falsifiable. Follow-up commit `6618ceb` routes the add through membership so the
  chain test actually exercises the intended contract.
- Both review-mandated docstring pins (`run_installs`'s deps-first-topological-order
  assumption on `installer/session.py`, `render_verification`'s `method_kind=None`
  omission note on `installer/render.py`) landed as part of Tasks 1 and 3 respectively,
  each asserted against `__doc__` in the corresponding test file.

## Self-Check: PASSED

Independently verified (not the executor's self-report): `make validate` (ruff, pyright,
bandit, vulture, shellcheck) — 0 errors/warnings. `make test` — 759 passed, 99.81%
coverage (required 90%).
