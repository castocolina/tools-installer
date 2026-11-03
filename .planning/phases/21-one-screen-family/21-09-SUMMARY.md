---
phase: 21-one-screen-family
plan: "09"
subsystem: uninstall
tags: [uninstall, per-tool-outcome, tdd]
requires: ["21-02"]
provides: ["SweepResult.removed", "SweepResult.remove_failed", "per-tool removal loop in perform_uninstall"]
key-files:
  modified: [installer/app.py, installer/uninstall.py, tests/test_app.py]
requirements: [UI-05]
status: complete
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
plan_head_before: 83003441e2c8c6ccf1c9765d6744f2c832730ee7
plan_head_after: 65c4c14f59e63d2bdbbe6701536200e83601f6be
---

# Phase 21 Plan 09: Per-tool uninstall outcome Summary

`perform_uninstall` removes each selected tool through its own `remove_proven([tool], ...)` call and reports `SweepResult.removed` / `remove_failed`; an `OSError` from one tool's delete becomes its `first_line` and never stops the next tool or the levers.

## Commits
- f3ded53 test(21-09): reports each tool as removed or remove failed (RED; also adds the two empty-default `SweepResult` fields so the tests type-check under the pre-commit pyright hook)
- 80c1e0e feat(21-09): perform_uninstall removes and reports tool by tool
- d7c97a2 test(21-09): a failed delete is that tool's remove_failed line (RED)
- 65c4c14 feat(21-09): a failed delete is reported per tool and never aborts the sweep

## RED output
Task 1: `AssertionError: assert () == ('yq', 'fd')` and `assert () == (('yq', 'changed since the preview; not removed: .../.local/bin/yq'),)`.
Task 2: `OSError: disk full / second line` propagated out of `perform_uninstall`; the empty-error test failed on the same raise. (The nothing-left test already passed after Task 1, since the unmatched-path refusal covers it.)

## GREEN
`pytest tests/test_app.py tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_setup.py -n auto`: all pass. `make validate` exit 0. `make test` exit 0: 4984 passed, 4 skipped, coverage 96.07%. `tests/test_app.py` collected: 136 at start, 141 at end.

## Deviations from Plan
- [Rule 3 - Blocking] The pre-commit pyright hook rejects tests that reference nonexistent attributes, so the RED commit carries the two empty-default `SweepResult` fields (no behavior). The tests still fail on behavior (output above).
- Test helper `_sweep_two_tools` plus `_raising_remove_proven` added to `tests/test_app.py` (shared by the five tests); `UninstallDecision` is now imported at module top there.

## Known Stubs
None.

## Self-Check: PASSED
Files and the four commits exist on the branch.
