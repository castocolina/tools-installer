---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "20"
status: complete
subsystem: catalog-ui
tags: [tool-state, catalog, d-04, deletion, tdd]

requires:
  - phase: 19-13
    provides: "every catalog decision reads state_of; tests/state_doubles.py seeded_service"
provides:
  - "CatalogScreen(tools, blurbs, *, ...) and UnifiedApp(tools, blurbs, *, ...): no installed parameter, no per-tier presence map"
  - "install close and view switches re-enter only through enter_view (the refresh pass); no catalog-wide presence sweep"
affects: [19-15, 19-17]

actuals:
  tokens: 14000
  tasks: 2
  commits: 2
plan_head_before: 108282415734d45d4f3df277329333fbce74074c
plan_head_after: 3319ff2

tech-stack:
  added: []
  patterns:
    - "a counting presence predicate in ExecuteInputs proves that no code path sweeps the catalog"
    - "a gated service presence probe holds the refresh pass so a test can observe the `…` rows and version_refreshing"

key-files:
  created:
    - .planning/phases/19-one-tool-state-with-health-plus-receipts/19-20-SUMMARY.md
  modified:
    - installer/catalog_tui.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_policies_e2e.py
    - tests/test_uninstall_e2e.py
    - tests/test_execute_screen.py

key-decisions:
  - "The test helpers _version_app and _update_app (tests/test_wizard_app.py) also lose their installed parameter, because they receive the service from the caller and never seed one. Only the test_catalog_tui helpers (_unified_app, _screen) keep installed, as the seed for seeded_service."
  - "Tests that asserted the deleted map now assert behaviour: a predicate that fails after the run no longer reaches the close, the non-tier close leaves the doctor view untouched, and the cross-tier test feeds its presence into the service."
  - "setup.py keeps its installed map because _build_daemon_policy and the uninstall inputs (installed_tools=) still read it. Only the UnifiedApp argument is removed."

requirements-completed: [STATE-01]

duration: 25min
completed: 2026-10-16
---

# Phase 19 Plan 20: Delete the per-tier installed maps Summary

The catalog no longer keeps its own record of what is installed. `CatalogScreen` and `UnifiedApp` lose their `installed` parameter, the per-screen `_installed` map, `set_installed` and `_rederive_installed`, with no shim left behind. Closing an install run and switching views now only re-enter through the refresh pass, and two counting tests check that.

## What was built

### Task 1: delete the per-tier installed maps and the constructor parameters (`3fd491e`)
- `installer/catalog_tui.py`: removed the `installed` parameter, `self._installed` and `set_installed`. The ownership-cell comment now says "presence" where it used to name the deleted map.
- `installer/wizard_app.py`: removed the `installed` parameter, the pass-through to `CatalogScreen`, `_catalog_tools` (it existed only for the sweep), `_rederive_installed`, and its two call sites in `show_view` and `_install_closed`. The long comments explaining the sweep went with it. `run_live` is still used elsewhere.
- `setup.py`: `UnifiedApp(` no longer gets `installed`. The map stays, because `_build_daemon_policy` and `installed_tools=` still read it.
- New test: `test_catalog_screen_has_no_installed_parameter` (tests/test_catalog_tui.py).
- Test sites were converted with an out-of-repo AST script that drops the second positional argument. It printed these counts per file:
  - tests/test_catalog_tui.py: CatalogScreen 4, UnifiedApp 1
  - tests/test_wizard_app.py: UnifiedApp 5, `_version_app` 30, `_update_app` 14
  - tests/test_policies_e2e.py: UnifiedApp 10
  - tests/test_uninstall_e2e.py: UnifiedApp 3
  - tests/test_execute_screen.py: UnifiedApp 1
  - Total: 20 `UnifiedApp(` and 4 `CatalogScreen(` test constructions. The plan estimated 22 and 5. Its grep also counted a docstring mention and helper definitions; a re-grep after the script shows no constructor still passes the map.
- Helper definitions were changed with a second count-asserting script: `_version_app`/`_update_app` lost the parameter, and the `_app`/`_host` locals were removed. Also removed: one unused `installed` local (found by ruff F841), and `"installed"` from the `UnifiedApp.__init__` signature list in `test_unified_app_signature_carries_no_disk_pressure_parameter`.

### Task 2: install close and view switches re-enter through the pass (`3319ff2`)
- `test_install_close_reenters_without_a_presence_sweep`: one tool per tier, with a counting `ExecuteInputs.installed`. After the run closes, the active tier's `version_refreshing` is True and the row's Health shows `…` while the pass is held by a gated service presence probe. Once the gate is released the row shows a real mark, and the counting predicate recorded no calls.
- `test_view_switch_reenters_without_a_presence_sweep`: switching user, then ai, then system starts a pass on each entered tier, and the counting predicate records no calls.
- `installer/wizard_app.py`: one short D-04 paragraph in `UnifiedApp.__init__` (each tier renders from `state_of`; a mutation invalidates the epoch, rows read `…`, and the next pass repaints every tier in one swap) plus a one-line pointer in `_install_closed`.
- Test comments that still described the sweep were rewritten in tests/test_wizard_app.py (section header, three docstrings or comments) and in tests/test_catalog_tui.py (one comment).

## TDD evidence

RED (Task 1, before any source change):
```
>       assert "installed" not in inspect.signature(CatalogScreen).parameters
E       assert 'installed' not in mappingproxy(OrderedDict({'tools': <Parameter "tools: list[installer.model.Tool]">, 'installed': <Parameter "installed...
tests/test_catalog_tui.py:4662: AssertionError
FAILED tests/test_catalog_tui.py::test_catalog_screen_has_no_installed_parameter
```

Task 2 had no RED, because Task 1 had already removed the sweep. Each test was instead checked against a temporary mutation, applied and reverted by a scratch script, with the source confirmed clean afterwards:
- Mutation 1: a loop over `self._execute.catalog` calling `self._execute.installed(tool)` inserted at the top of `_install_closed`:
  ```
  E       AssertionError: a presence sweep read ['sys-tool', 'user-tool', 'ai-tool'] (catalog: ['sys-tool', 'user-tool', 'ai-tool'])
  FAILED tests/test_wizard_app.py::test_install_close_reenters_without_a_presence_sweep
  ```
- Mutation 2: the same loop in `show_view` before the pop/push:
  ```
  E       AssertionError: a presence sweep read ['sys-tool', 'user-tool', 'ai-tool', 'sys-tool', 'user-tool', 'ai-tool', 'sys-tool', 'user-tool', 'ai-tool'] (catalog: [...])
  FAILED tests/test_wizard_app.py::test_view_switch_reenters_without_a_presence_sweep
  ```

## Verify results
- `uv run pytest tests/test_catalog_tui.py tests/test_wizard_app.py tests/test_policies_e2e.py tests/test_uninstall_e2e.py tests/test_execute_screen.py tests/test_setup.py -n auto -q --no-cov`: all passed.
- `uv run pytest tests/test_wizard_app.py -q --no-cov -k presence_sweep`: 2 passed, five repeated runs under `-n auto`.
- Grep gate `def set_installed|def _rederive_installed|self\._installed\b` in catalog_tui.py and wizard_app.py: 0 and 0.
- Shrink, trailing-newline and test-count guard (run as a scratch script, because the sandbox rejects inline `bash -c` guards):
  - Task 1 (max 120 lines lost):
    - wizard_app.py 3174 -> 3107
    - setup.py 1565 -> 1564
    - test_catalog_tui.py 4656 -> 4661 (tests 165 -> 166)
    - test_wizard_app.py 8007 -> 7976 (299 -> 299)
    - test_policies_e2e.py 1090 -> 1080 (22 -> 22)
    - test_execute_screen.py 4369 -> 4367 (108 -> 108)
  - Task 2 (max 60 lines lost):
    - wizard_app.py 3107 -> 3113
    - test_wizard_app.py 7978 -> 8056 (299 -> 301)
    - test_catalog_tui.py 4661 -> 4661
- Suppression guard: 593 at plan start, 590 at the end. Three `pyright: ignore` lines were removed along with the deleted `_installed` assertions, and none were added.
- `git diff --exit-code 1082824 -- pyproject.toml uv.lock`: unchanged.
- Final `wc -l`:
  - installer/catalog_tui.py 1102
  - installer/wizard_app.py 3113
  - setup.py 1564
  - tests/test_catalog_tui.py 4661
  - tests/test_wizard_app.py 8056
  - tests/test_policies_e2e.py 1080
  - tests/test_uninstall_e2e.py 255
  - tests/test_execute_screen.py 4367
- `git diff --stat 1082824`: 8 files changed, 173 insertions(+), 219 deletions(-).
- `make validate`: exit 0 before each commit. `make test`: 4374 passed / 4 skipped after Task 1 and 4376 passed / 4 skipped after Task 2, coverage 95.83%.

## Deviations from Plan

**1. [Rule 3 - Blocking] The `_version_app`/`_update_app` helpers lost their `installed` parameter**
- Found during Task 1. These helpers take the service from the caller, so `installed` became an unused argument. That meant 44 extra call sites in tests/test_wizard_app.py, converted by the same AST script.

**2. [Rule 1 - Bug in tests] Three tests asserted the deleted map and were converted to behaviour**
- `test_install_closed_reports_a_failed_presence_sweep_and_keeps_the_old_map` became `test_install_close_survives_a_presence_predicate_that_fails_after_the_run`. It now asserts that the app keeps running and that no re-check warning or OSError text appears.
- `test_install_closed_degrades_when_the_active_view_is_not_a_catalog_tier` now asserts the doctor view is unchanged instead of checking the map.
- `test_install_closed_keeps_cross_tier_ids_in_every_installed_map` lost its structural loop over `_installed`. Its service now gets `present=` from the test's presence holder, so the behavioural check ("also needs pnpm" never shown) reads real state.
- `test_returning_from_another_view_rederives_the_installed_map` was renamed to `test_returning_from_another_view_rereads_presence_through_the_pass`; its body is unchanged.
- `test_unified_app_signature_carries_no_disk_pressure_parameter` dropped `"installed"` from the expected parameter list.

**3. [Rule 2] Task 2 touched tests/test_catalog_tui.py**
- One comment there still described the deleted per-tier map. It is a one-line comment edit, outside Task 2's listed files but inside the plan's.

**4. Task 1 also removed the sweep-explaining comments**
- They described code that Task 1 deleted. Task 2 then added the short replacement paragraph the plan asks for.

## Issues for the orchestrator
- No file outside the plan's files_modified was touched.
- Rebase overlap with 19-14 is possible only if 19-14 also edits tests/test_wizard_app.py or tests/test_execute_screen.py around a `UnifiedApp(`/`_version_app(` call. Any new call site it adds must drop the second positional `installed` argument.
- Behaviour note: after an uninstall, a catalog shows fresh presence only once the refresh pass re-reads it. This was already true after 19-13, because the deleted map was not read. `test_returning_from_another_view_rereads_presence_through_the_pass` still passes.

## Self-Check: PASSED
- Commits `3fd491e` and `3319ff2` are on HEAD. All 8 modified files exist, and the grep gate is 0.
