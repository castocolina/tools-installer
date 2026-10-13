---
phase: 14-install-update-engine-correctness-default-shell-action-selec
plan: "01"
subsystem: install-execution
tags: [update-service, execute-screen, version-refresh, dependency-resolver, textual]

requires:
  - phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
    provides: ExecuteScreen, enter-start confirm gate, shared VersionRefreshService/UpdateService on catalog screens
  - phase: 12-live-package-management
    provides: UpdateService.run ownership re-resolution, VersionRefreshService.statuses/ownership_of/refresh
provides:
  - ExecuteInputs.version_refresh and ExecuteInputs.updates wired from setup._build_app
  - ExecuteScreen install-vs-update split beside resolve_dependencies
  - Batch update dispatch through UpdateService.run behind the existing enter confirm
affects:
  - 14-02 (preflight/progress set equality for _to_update)
  - 14-02 (update outcome rendering)

actuals:
  tokens: 5815
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Recording subclasses of real UpdateService/VersionRefreshService for strict pyright"
    - "dataclasses.replace at composition root to re-bind ExecuteInputs onto shared services"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - setup.py
    - tests/test_execute_screen.py
    - tests/test_setup.py
    - tests/test_deps.py

key-decisions:
  - "D-01: one update mechanism, two call sites — batch path calls UpdateService.run"
  - "D-02: existing enter confirm is the only consent; no second prompt"
  - "Eligibility predicate copied from action_update_tool (skip only when status exists AND outdated is False)"
  - "deps.py untouched — split computed in ExecuteScreen.on_mount"
  - "Missing ownership snapshot: batch path blocks on refresh (deliberate divergence from u keybind)"

patterns-established:
  - "Test doubles are real service subclasses overriding one method, caches seeded with reportPrivateUsage"
  - "Latch refusal driven through the real begin() lock, never a fake False answer"
  - "Structural absence gates (MUTATION_GRADE/perform_update/VersionStatus in deps.py) lock design decisions"

requirements-completed: ["D-01", "D-02"]

coverage:
  - id: D1
    description: Selecting an installed-but-outdated tool and pressing enter reaches UpdateService.run
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_outdated_installed_selected_tool_is_dispatched_through_update_service
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_only_outdated_selection_still_starts_and_dispatches
        status: pass
    human_judgment: false
  - id: D2
    description: Confirmed-current tools are not dispatched; missing status still attempts update
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_confirmed_current_tool_is_not_dispatched_as_outdated
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_missing_version_status_still_dispatches_an_outdated_update
        status: pass
    human_judgment: false
  - id: D3
    description: Missing ownership snapshot triggers blocking single-tool refresh before dispatch
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_missing_ownership_snapshot_refreshes_then_dispatches_outdated_update
        status: pass
    human_judgment: false
  - id: D4
    description: In-flight latch refusal skips without releasing a latch the batch did not take
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_in_flight_latch_skips_outdated_update_and_keeps_the_holder
        status: pass
    human_judgment: false
  - id: D5
    description: setup._build_app rebinds execute onto shared services only when execute= is passed
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_setup.py#test_build_app_rebinds_execute_onto_shared_services_when_execute_is_passed
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_build_app_leaves_execute_none_when_caller_omits_it
        status: pass
    human_judgment: false
  - id: D6
    description: Nothing updates before enter; enter is the only consent gate (D-02)
    requirement: D-02
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_nothing_updates_before_the_confirm_keypress
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_confirm_keypress_dispatches_exactly_one_outdated_update
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_update_dispatch_opens_no_confirm_prompt_of_its_own
        status: pass
    human_judgment: false
  - id: D7
    description: Resolver still excludes selected installed tools; no version/ownership coupling
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_deps.py#test_explicitly_selected_installed_tool_is_excluded_from_order
        status: pass
      - kind: unit
        ref: tests/test_deps.py#test_resolver_source_names_neither_version_status_nor_ownership
        status: pass
    human_judgment: false

duration: 36min
completed: 2026-09-14
status: complete
---

# Phase 14 Plan 01: Install/Update Engine Correctness — Tracer Summary

**Select+enter on an outdated installed tool now reaches UpdateService.run through ExecuteScreen, behind the existing enter confirm, with deps.py left presence-only.**

## Performance

- **Duration:** 36 min
- **Started:** 2026-09-14T14:22:22Z
- **Completed:** 2026-09-14T14:58:51Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `ExecuteInputs` carries shared `version_refresh`/`updates`; `setup._build_app` rebinds them via `dataclasses.replace` when the wizard passes `execute=`
- `ExecuteScreen` splits selected tools into install order vs update list using the `action_update_tool` eligibility predicate, then dispatches updates through `UpdateService.run` under the in-flight latch
- Confirm-gate and resolver-baseline tests lock D-02 and the deliberate deps.py contract

## Task Commits

Each task was committed atomically:

1. **Task 1: end-to-end outdated update dispatch** - `f2e54c5` (feat)
2. **Task 2: lock enter confirm gate** - `8236610` (test)
3. **Task 3: lock resolver exclusion baseline** - `12efa6e` (test)

## Files Created/Modified

- `installer/execute_screen.py` - ExecuteInputs service fields, `_to_update`/`_update_targets`/`_run_updates`
- `setup.py` - rebind execute onto shared VersionRefreshService/UpdateService
- `tests/test_execute_screen.py` - recording-service doubles and outdated/confirm pilot tests
- `tests/test_setup.py` - wiring assertions for execute rebind / no-execute contract
- `tests/test_deps.py` - selected-installed exclusion + structural version/ownership absence gate

## Decisions Made

- Followed plan as specified for D-01/D-02.
- Kept `installer/deps.py` and `installer/update.py` byte-unchanged.

## Deliberate Divergence from the `u` Keybind

When no ownership snapshot is cached, `CatalogScreen.action_update_tool` returns and does nothing (`installer/catalog_tui.py:571-573`) because it runs on the UI thread. The batch path instead calls the refresh service's blocking single-tool `refresh` and proceeds with whatever snapshot that produced. That is legal because `_execute_worker` is already a thread worker, and necessary because the eligibility predicate queues tools whose version probe has not resolved. The mutation gate itself is unchanged: `UpdateService.run` re-resolves ownership freshly either way.

## Documented Temporary Gap

This tracer does not yet disclose `_to_update` in the preflight head or progress list (those still iterate `_ordered` only). Plan 14-02 Task 1 closes that set-equality gap. Neither plan reaches a released build alone.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 1 verify's `grep -q 'dataclasses import'` required `from dataclasses import replace` rather than `import dataclasses`.
- `make validate` caught an E501 in the new deps structural test and a `reportPrivateUsage` on `inspect.getsource(ExecuteScreen._run_updates)`; both folded into the owning task commits before close-out.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 14-02: preflight/progress must enumerate exactly `_to_update`, and update outcomes need rendering.
- No blockers.

## Verification

- `uv run pytest tests/test_execute_screen.py tests/test_setup.py tests/test_deps.py -q` — pass
- `uv run pytest tests/test_execute_screen.py -k outdated -q` — pass (6 tests)
- `uv run pytest tests/test_execute_screen.py -k 'confirm or outdated' -q` — pass
- `make validate && make test` — pass (2019 passed, 1 skipped, 95.34% coverage)

## Self-Check: PASSED

---
*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Completed: 2026-09-14*
