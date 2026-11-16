---
phase: 20-install-plan-with-dispositions
plan: "17"
subsystem: execute-screen
tags: [execute-inputs, presence, state-service, test-helpers, L-20-09]
requires:
  - 20-03 (VersionRefreshService state and is_present)
  - 20-04 (frozen_service and plan_state test doubles)
provides:
  - ExecuteInputs with a required version_refresh, a terminal_sync field, and no installed field
  - presence_service and FrozenStateService.assume_present (tests/state_doubles.py)
  - _execute_inputs(catalog, present=, install=, platform=) (tests/test_wizard_app.py)
affects:
  - installer/execute_screen.py
  - setup.py
  - tests/state_doubles.py
  - tests/test_execute_screen.py
  - tests/test_setup.py
  - tests/test_wizard_app.py
key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - setup.py
    - tests/state_doubles.py
    - tests/test_execute_screen.py
    - tests/test_setup.py
    - tests/test_wizard_app.py
key-decisions:
  - "ExecuteInputs.version_refresh is required and is the only presence source; the installed predicate is deleted, so no second answer can disagree with the published state (L-20-09)."
  - "terminal_sync is a defaulted ExecuteInputs field wired by _build_app; no code reads it yet, and 20-10 passes it into the run context."
  - "A test that passes its own service keeps that service's published states; presence for the tools it has not published answers through the service probe, because publishing a state would turn a deliberately missing ownership snapshot into a present one."
  - "A presence predicate in a test is probed, never published, so a predicate that changes mid-run is seen at the next read."
  - "The wizard tests keep each predicate verbatim (ids or callable) rather than converting to ids, because seven predicates read a dict the test mutates during the run."
requirements-completed: []
status: complete
duration: about 60 min (approximate)
completed: 2026-10-17
---

# Phase 20 Plan 17: ExecuteInputs reads presence from the one state service Summary

**ExecuteInputs requires the state service, loses the `installed` predicate and gains `terminal_sync`; the screen reads presence only through `version_refresh.is_present`, and screen tests publish presence through one helper.**

## Performance

- **Duration:** about 60 min (approximate)
- **Tasks:** 2 of 2
- **Commits:** 2 task commits plus this summary commit

## Accomplishments

- `ExecuteInputs` declares `version_refresh: VersionRefreshService` as a required field, before the defaulted fields; the `installed` field is gone; `terminal_sync: Callable[[], str | None] | None = None` is added.
- `_build_app` wires `terminal_sync=_sync_omz_terminals` into `ExecuteInputs` and no longer passes `installed=`.
- The four presence reads in `ExecuteScreen` go through `version_refresh.is_present`; every `is None` guard on the service is removed. `is_installed` is no longer imported by the screen.
- `presence_service(catalog, *, present=, states=, platform=, service=)` in `tests/state_doubles.py` is the one place a screen or wizard test builds its presence.
- Both test modules construct their inputs through a helper with a published-state default; no test was deleted.

## Task Commits

1. **Task 1: ExecuteInputs reads presence from the one state service** - `dbcad5a` (refactor, TDD: RED first, then the contract change and the test ports in one commit)
   - `installer/execute_screen.py`: new `ExecuteInputs` shape and docstring; four presence reads through the service; `None` guards removed; unused `is_installed` import removed.
   - `setup.py`: `_execute_inputs` takes `version_refresh` and passes it into `ExecuteInputs`; `_build_app` drops `installed=` and wires `terminal_sync`.
   - `tests/state_doubles.py`: `presence_service`, `Presence`, `FrozenStateService.assume_present`.
   - `tests/test_execute_screen.py`: two new tests; `_inputs(present=, states=)`; 53 call sites ported (39 id predicates to `present=("id",)`, 14 always-true predicates to explicit id tuples).
   - `tests/test_setup.py`: the `_hermetic_route` stub forwards `version_refresh`; three direct `_execute_inputs` calls pass `presence_service([])`; the presence test asserts `execute.version_refresh is service`.
   - `tests/test_wizard_app.py`: the 21 `ExecuteInputs` constructions get `version_refresh=presence_service(...)` in place of `installed=` (see Deviations).
2. **Task 2: wizard app tests build ExecuteInputs through one helper** - `12bd28b` (test)
   - `tests/test_wizard_app.py`: `_execute_inputs(catalog, *, present=, install=, platform=)` replaces the 21 inline constructions and the old `_execute_inputs(*, install=)`; each block keeps its own presence predicate and its comment; wire and verify default to the empty lambdas every site used.

## TDD RED Evidence

Command: `uv run pytest tests/test_execute_screen.py -q --no-cov -k "requires_a_version_refresh or publishes_presence"` (before any implementation; the helper and tests were in place, `ExecuteInputs` and `_inputs` unchanged)

```
FAILED tests/test_execute_screen.py::test_execute_inputs_requires_a_version_refresh_service
E   Failed: DID NOT RAISE <class 'TypeError'>
FAILED tests/test_execute_screen.py::test_inputs_helper_publishes_presence_into_a_frozen_service
E   TypeError: _inputs() got an unexpected keyword argument 'present'
2 failed
```

Both failures are the expected ones: the omitted service was accepted, and the helper had no `present` keyword.

## Verification

- `make validate` passes on each task commit and on the final tree (ruff check, ruff format, pyright with 0 errors, bandit, vulture, shellcheck).
- `make test` passes on each task commit and on the final tree: 4860 passed, 4 skipped; coverage 96.01% against the 90% floor.
- Test-count floors: `tests/test_execute_screen.py` has 116 `def test_` (114 before, plus the 2 new tests; floor 116). `tests/test_wizard_app.py` has 301 (floor 301). No test was removed.
- `uv run pytest tests/test_execute_screen.py tests/test_setup.py -n auto -q --no-cov` passes after the port (run before the wizard port, and again inside `make test`).
- Acceptance greps on the final tree:
  - `installed: Callable` in `installer/execute_screen.py`: 0
  - `version_refresh: VersionRefreshService` (field line): 1
  - `terminal_sync: Callable`: 1
  - `self._inputs.installed(`: 0
  - `terminal_sync=_sync_omz_terminals` in `setup.py`: 4 (UnifiedApp kwarg, the replace, and two existing call sites)
  - `installed=version_refresh.is_present` in `setup.py`: 0
  - `def _execute_inputs(` in `tests/test_wizard_app.py`: 1; `_execute_inputs(` calls and definition: 28
  - `ExecuteInputs(` constructions in `tests/test_wizard_app.py`: 1 (inside the helper)
- Suppression comments: no `type: ignore`, `pyright: ignore`, `noqa` or `nosec` added or removed in the plan diff.
- Line counts (before to after, pre-plan commit `c6f7bfa`): `installer/execute_screen.py` 1166 to 1166; `setup.py` 1600 to 1602; `tests/state_doubles.py` 362 to 417; `tests/test_execute_screen.py` 4705 to 4753; `tests/test_setup.py` 3921 to 3932; `tests/test_wizard_app.py` 8036 to 8015.
- `git diff --stat c6f7bfa`: 6 files changed, 323 insertions(+), 228 deletions(-). Hunks in `tests/test_execute_screen.py`: 57; in `tests/test_wizard_app.py`: 25.

## Deviations from Plan

**Scope and ordering**

- **[Ordering] Wizard port moved into Task 1.** `ExecuteInputs.version_refresh` is required, so the 21 wizard constructions had to gain it in the same commit as the contract change, or that commit would break the wizard tests (and fail "every commit green"). Task 1 therefore ports them inline with `version_refresh=presence_service(...)`; Task 2 folds them into `_execute_inputs`. Both commits are green.
- **[Files] `tests/state_doubles.py` and `tests/test_setup.py` were modified** though not in `files_modified`. The first gained the reuse helper the 20-REUSE finding asks for; the second's `_hermetic_route` stub and three direct `_execute_inputs` calls had to pass the now-required service, and its presence test read the removed `execute.installed` attribute.
- **[Wiring] `version_refresh` goes through `_execute_inputs`, not the `replace(...)`.** The plan's key link listed `version_refresh=` in the `replace(execute, ...)` call. The service is already available where `_execute_inputs` is called, so it is passed there, and the `replace` sets `install`, `updates` and `terminal_sync`.

**Presence port rule**

- **[Rule] Sites with an explicit service use the service probe.** About 40 screen-test sites passed `installed=<predicate>` together with `version_refresh=<service>`. Publishing the predicate's answer as states would have overwritten the snapshot those tests rely on: `test_missing_ownership_snapshot_refreshes_then_dispatches_outdated_update` expects the worker to refresh a tool whose state is absent, and the publish made it present. So `presence_service(..., service=)` answers presence through `assume_present` for the tools the service has not published, and publishes only explicit `states`. Confirmed by the failing run before the fix and green after.
- **[Rule] Wizard predicates kept verbatim.** The plan asked for ids. Seven of the 21 wizard predicates read a dict the test mutates mid-run (`presence[installed_tool.id] = True` inside an install callback), so a static id list would drop that behaviour. `presence_service` and `_execute_inputs` accept either ids or a predicate; the wizard sites pass the predicate unchanged, and the predicate is probed rather than published.
- **[Rule] Screen sites use ids.** The 53 screen-test predicates were converted to id tuples (`present=("rg",)`); the always-true ones list the catalog ids explicitly. Equivalence was checked by the port script's counts (39 and 14) and by the test run.

**Helper signatures**

- **[Signature] `_execute_inputs` is smaller than the plan's sketch.** It takes `catalog`, `present`, `install`, `platform` only. The plan listed `states`, `unattended`, `updates`, `wire_path` and `verify` as well, but no site needed them, so they were left out (no speculative options). `wire_path` and `verify` are fixed to the empty lambdas every wizard site already passed; the old helper's `"PATH wired"` and `"PATH verified"` defaults no longer apply to its six existing callers, and their tests stay green.
- **[Signature] `_inputs` keeps its `version_refresh` parameter** and adds `present` and `states`; it passes `platform=_PLATFORM` to the service so the screen's platform is unchanged.
- **[Behaviour] `ExecuteScreen._platform()` now returns `version_refresh.platform`** (required service, no fallback to `inputs.platform`). Tests pass the same platform to both, so this is unchanged in practice.

**Acceptance criteria that were stated too literally**

- **[Grep] `version_refresh.is_present(` appears 2 times, not 4.** `_classify_selection` and `_update_targets` read the service through the existing local alias `refresh = self._inputs.version_refresh` and call `refresh.is_present(tool)`. All four presence reads go through the service; the criterion's count assumed no alias.
- **[Grep] `! grep -n "installed=" tests/test_execute_screen.py` still matches six lines.** They are unrelated keywords: `VersionStatus(installed=...)` in the test refresh doubles and `_VersionedRefreshService(..., installed=...)` constructor arguments. None is an `ExecuteInputs` argument, and the field check is covered by `test_execute_inputs_requires_a_version_refresh_service`.

**Reuse pass (20-REUSE.md, finding for 20-17, also naming 20-11 and 20-12)**

- **Applied:** `presence_service` is the single publish-or-probe helper in `tests/state_doubles.py`. `_inputs` (screen tests) and `_execute_inputs` (wizard tests) are thin wrappers around it for their `ExecuteInputs` defaults and do not copy the publish logic. The 20-11 `_service` helper is not part of this plan and was not touched.
- **Test-count floors:** no test was removed, so the floors are unchanged apart from the new screen total (116 = 114 + 2 new tests). The wizard floor stays at 301.
- **Rejected:** none.

## Issues the Orchestrator Must Know

- **`terminal_sync` is a field nothing reads yet.** `_build_app` wires it and `ExecuteInputs` carries it, but `ExecuteScreen` does not consume it until 20-10 (`execute_plan` passes it into the run context). vulture does not flag dataclass fields, so this is intentional, not dead code.
- **Presence through the service probe.** Any test that passes its own service and expects a tool to be present must publish a state or give the service a probe that answers true. The helper's default path publishes states for catalog tools; the explicit-service path only probes. This is documented on `presence_service`.
- **PLAN-05 and PLAN-07 are not marked complete here.** Both are behavioural requirements (post-run selection; "checking..." waits) and are delivered by the later execute-plan work, so `requirements-completed` is empty.

## Self-Check: PASSED

- All 6 modified files exist on this branch and are committed in `dbcad5a` and `12bd28b`.
- Task commits `dbcad5a` and `12bd28b` exist on `worktree-agent-ace4ee5047faca657`.
- No `git add -A` or `.` was used; no file under `.planning/` other than this summary was touched; `.planning/config.json` was not staged.
