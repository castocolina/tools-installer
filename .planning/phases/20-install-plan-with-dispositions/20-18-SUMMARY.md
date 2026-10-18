---
phase: 20-install-plan-with-dispositions
plan: "18"
subsystem: testing
tags: [textual, pytest, install-plan, xdist]
key-files:
  created: []
  modified:
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
key-decisions:
  - "Applied REUSE finding 18-1: omitted a redundant unavailable-row pilot and folded its assertion into the plan-order pilot."
  - "No production fix was needed; the existing plan and selection behavior passed the new pins."
requirements-completed: [PLAN-05, PLAN-01]
duration: 18 min
completed: 2026-10-18
status: complete
---

# Phase 20, Plan 18 Summary

**Added pilot coverage for all-current bulk selection, TUI/headless plan ordering and retained selection after a mixed outcome run.**

## What was built

- **Task 1:** Added an all-current `a` flow through `UnifiedApp`: Enter reviews the three skipped rows, starts no install, performs no PATH wiring or terminal sync, displays `Summary — 3 skipped`, and clears the selection on close. Added a plan-order parity test that also verifies an UNAVAILABLE row is excluded by `a`. Added a mixed-outcome retained-selection test through the app's catalog decision/close callback. Production code required no changes.
- Task commit: `8999518` (`test(20-18): pin bulk install plan behavior through the app`).

## TDD RED evidence

The order-parity test first failed because the review contained `fd` although the unavailable row was absent from `display_order(build_plan(...))`:

```text
E           AssertionError: assert ['rg', 'fd'] == ['rg']
E             Left contains one more item: 'fd'
```

Test harness setup was corrected to use the actual app's `VersionRefreshService`; the final test then passed. A first mixed-run attempt also exposed that the test had not used the app's dismiss callback (the staged set still included done/skipped IDs); routing through the catalog decision callback fixed that test setup.

## Verification

- RED/GREEN targeted run: `uv run pytest tests/test_wizard_app.py tests/test_execute_screen.py -q --no-cov -k 'all_current_tier or same_plan_order or mixed_run_keeps'` — 3 passed.
- Plan verification: `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_setup.py tests/test_session.py tests/test_render.py tests/test_plan.py -n auto -q --no-cov` — passed.
- Suppression-count gate — passed, unchanged at 483.
- All three retained acceptance test definitions were counted exactly once.
- `make validate` — passed.
- Touched test modules: `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py -n auto -q --no-cov` — passed.
- Final full suite: `make test` — 4838 passed, 4 skipped; coverage 96.00% (90% required).
- `git diff --check` — passed. Test file line counts remained intact; changes were limited to intended additions.

## Deviations from plan

- **REUSE 18-1 → removed `test_a_never_selects_an_unavailable_row` and its acceptance grep → three new pilot tests instead of four.** Its coverage was folded into `test_a_and_enter_use_the_same_plan_order_as_the_headless_route`, which asserts the unavailable tool is absent from the displayed plan. No test-count floor was prescribed; the required three remaining acceptance tests each occur exactly once.
- The plan's unavailable-row standalone test was replaced with a focused assertion in the existing order-parity test, as the REUSE note permits. No other deviations.

## Issues for the orchestrator

- None.
