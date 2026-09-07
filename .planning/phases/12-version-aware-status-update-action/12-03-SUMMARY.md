---
phase: 12-version-aware-status-update-action
plan: 03
subsystem: ui
tags: [update, ownership, catalog, textual, pnpm-globals, atomic-replace]

# Dependency graph
requires:
  - phase: 12-version-aware-status-update-action
    provides: "ManagerOwnership, MUTATION_GRADE, VersionRefreshService.invalidate/ownership_of, and the Catalog Ver column (Plans 12-01 and 12-02)"
provides:
  - "installer/update.py — ownership-first perform_update plus UpdateService (in-flight guard, fresh re-resolve, pnpm pre-capture, invalidate)"
  - "installer/download.py::update_download and installer/apps.py::update_app — stage, validate, os.replace rollback state machine"
  - "Catalog `u` action registered in ui_common.VIEWS and CatalogScreen.BINDINGS, wired from setup.py through UnifiedApp into all three tier screens"
affects: [12-04-verification]

# Actuals (#2632)
actuals:
  tokens: 5559
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Display can be cheap and cached; mutation cannot. UpdateService.run re-resolves ownership for the one tool at mutation time and uses that fresh result, never the 6-hour snapshot that gated the keypress."
    - "Capture-before-mutate: the pnpm-managed package set is snapshotted BEFORE perform_update when tool.id == 'pnpm', held immutably, and replayed only after updated. None is not empty."
    - "exclusive=True is not a concurrency guard. UpdateService.begin/end under a lock refuse a second u while the first thread is already inside subprocess.run."
    - "try/finally post_message plus exit_on_error=False so a domain exception outside run_live's (OSError, CommandError) still clears the in-flight flag and leaves the TUI running."

key-files:
  created:
    - installer/update.py
    - tests/test_update.py
  modified:
    - installer/download.py
    - installer/apps.py
    - installer/executors.py
    - installer/catalog_tui.py
    - installer/tool_browser.py
    - installer/ui_common.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_download.py
    - tests/test_apps.py
    - tests/test_catalog_tui.py
    - tests/test_ui_common.py
    - tests/test_wizard_app.py
    - tests/test_setup.py

key-decisions:
  - "perform_update dispatches on ownership.owner, never resolve_methods ranking. The rg regression proves brew upgrade ripgrep even when github_release outranks brew."
  - "A pnpm-owned update reuses executors.execute with the owning node method. pnpm update -g and --latest are both rejected: the former respects declared range (12-RESEARCH.md:221), the latter discards registry pins, and either bypasses _node's co-install, allow-build, floors, and smoke check."
  - "should_replay_node_globals keys on tool.id == 'pnpm', not on owner, because pnpm itself has no node method. The snapshot is captured BEFORE the update that can wipe it."
  - "action_update_tool hides u only when outdated is False. outdated=None (script/tarball/app kinds, including script-installed pnpm) is reachable so the installer-owned dispatch and the pnpm-globals replay are not dead UI paths."
  - "Production runner is run_captured. Live streaming of manager output is not built this phase."

patterns-established:
  - "Fresh ownership re-resolution at mutation time via an injected reresolve_ownership seam, so a cached Ver-cell owner cannot authorize a no-confirmation mutation after the user installed the same tool through a different manager."
  - "Footer discoverability is the VIEWS registry UNION nested widget bindings, not CatalogScreen.BINDINGS alone."

requirements-completed:
  - REQ-update-action-manager-delegation
  - REQ-pnpm-global-reinstall-mitigation

coverage:
  - id: D1
    description: "perform_update dispatches on resolved ManagerOwnership, refuses unknown and non-MUTATION_GRADE with zero mutations, routes pnpm through _node, contains all seven domain exceptions, and re-dispatches postinstall."
    requirement: REQ-update-action-manager-delegation
    verification:
      - kind: unit
        ref: tests/test_update.py
        status: pass
    human_judgment: false
  - id: D2
    description: "update_download and update_app stage, validate, and atomically replace through one rollback state machine that recovers interrupted remnants and restores the captured original symlink on any failure."
    requirement: REQ-update-action-manager-delegation
    verification:
      - kind: unit
        ref: tests/test_download.py
        status: pass
      - kind: unit
        ref: tests/test_apps.py
        status: pass
    human_judgment: false
  - id: D3
    description: "Catalog u action is in the VIEWS footer registry, off the event loop, guarded against concurrent triggers, crash-contained, and refuses unknown/non-mutation-grade ownership with the ownership reason."
    requirement: REQ-update-action-manager-delegation
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_update_binding_exists_and_is_shown
        status: pass
      - kind: unit
        ref: tests/test_ui_common.py#test_catalog_footer_actions_match_effective_bindings
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_second_u_press_while_latched_is_refused
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_update_runs_off_the_event_loop_with_no_confirmation
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_rg_end_to_end_delegates_to_brew
        status: pass
    human_judgment: false
  - id: D4
    description: "UpdateService.run re-resolves ownership before any mutation, captures pnpm globals before a pnpm self-update, replays only that captured tuple, treats None as unknown not empty, and invalidates the shared version-refresh epoch."
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: unit
        ref: tests/test_wizard_app.py#test_fresh_ownership_dispatches_on_reresolve_not_cache
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_pnpm_precapture_replays_pre_update_set
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_none_package_snapshot_is_not_replayed_as_empty
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_epoch_guard_drops_stale_refresh_after_update
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_build_app_shares_one_update_service_and_invalidate
        status: pass
    human_judgment: false

# Metrics
duration: ~25 min (Task 3 resumption; Tasks 1-2 already committed)
completed: 2026-09-07
status: complete
---

# Phase 12 Plan 03: Version-Aware Status Update Action Summary

**Pressing `u` on an outdated Catalog row updates the tool through the manager that actually owns it — brew, cask, pnpm, uv, or this installer's own download/app/script path — with no confirmation, off the event loop, refused unless ownership is mutation-grade, and followed by an automatic pnpm-globals replay only when pnpm itself was the tool updated.**

## Performance

- **Duration:** ~25 min for Task 3 (this resumption). Tasks 1-2 were already committed on a prior run.
- **Started:** 2026-09-07 (Tasks 1-2 on `63681b6`/`a4dc569`; Task 3 resumed after a killed unattended run)
- **Completed:** 2026-09-07
- **Tasks:** 3/3
- **Files modified:** 17 (9 production created/modified, 1 composition-root, 7 test)

## Accomplishments

- `installer/update.py::perform_update` acts on a resolved `ManagerOwnership`, never on `resolve_methods` ranking. Unknown or non-`MUTATION_GRADE` ownership is refused with zero subprocess and zero filesystem write. A pnpm-owned tool reuses `executors.execute` with the owning `node` method so co-install grouping, `--allow-build`, registry pins, version floors, and the smoke check cannot drift from install. Every named domain exception becomes a typed `UpdateOutcome`; declared postinstall hooks re-dispatch after success.
- `download.update_download` and `apps.update_app` stage into a temp location, verify checksums before touching anything live, and replace via one rollback state machine: capture the original symlink, recover `.new`/`.old` remnants, aside-move, swap, recreate the symlink with `os.symlink` plus `os.replace`, then validate. A failure at any step restores the prior tree and captured symlink.
- The Catalog `u` action is live from `setup.py::_build_app` through one shared `UpdateService`. `run` re-resolves ownership at mutation time, captures pnpm globals BEFORE a pnpm self-update, mutates, replays the captured tuple, and invalidates the shared version-refresh epoch. A second `u` is refused while the first holds the latch. The worker uses `exit_on_error=False` and posts `ToolUpdated` from `finally`. The three catalog `VIEWS` rows name `u update` in the footer.

## Task Commits

Each task was committed atomically:

1. **Task 1: ownership-first update dispatch** — `63681b6` (feat)
2. **Task 2: update-safe download and app replacement** — `a4dc569` (feat)
3. **Task 3: wire Catalog update action with in-flight guard** — `55b9935` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `installer/update.py` — `UpdateTarget`, `UpdateOutcome`, `perform_update`, `UpdateService` (begin/end lock, fresh re-resolve, pre-capture, replay, invalidate)
- `installer/download.py` — `UpdateExecResult`, `update_download` rollback state machine
- `installer/apps.py` — `UpdateExecResult`, `update_app` rollback state machine
- `installer/executors.py` — `_node` smoke-check comment now names install and update paths
- `installer/catalog_tui.py` — `ToolUpdated`, `action_update_tool`, crash-contained `_update_tool_worker`, `on_tool_updated`
- `installer/tool_browser.py` — `highlighted_id` seam for the `u` action
- `installer/ui_common.py` — `u update` on the three catalog `VIEWS` rows
- `installer/wizard_app.py` — `updates=` threaded into all three `CatalogScreen`s
- `setup.py` — composition-root `UpdateService` with `run_captured`, `_reinstall_globals`, `reresolve_ownership`, and the same `VersionRefreshService.invalidate`
- Tests: `tests/test_update.py`, `tests/test_download.py`, `tests/test_apps.py`, `tests/test_catalog_tui.py`, `tests/test_ui_common.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`

## Decisions Made

See `key-decisions` in frontmatter. Followed the plan: ownership-first dispatch, `_node` reuse for pnpm, capture-before-mutate, fresh re-resolution at mutation time, `outdated is False` as the only hide-the-action gate, and `run_captured` with no live streaming.

## Deviations from Plan

None - plan executed exactly as written.

Task 3's uncommitted tree already implemented the specified behavior. This resumption typed the lambda fixtures (`perform_update` fakes, `InvalidateFn` Protocol, BINDINGS `isinstance(Binding, …)` narrowing, `state: dict[str, dict[str, str]]`) so strict pyright passed without silencing findings or loosening config. The success status line now also surfaces `outcome.detail` so a `None` pnpm snapshot warning is visible rather than only carried on the outcome object.

## Issues Encountered

This run was a resumption after the harness killed an unattended executor mid-Task-3. Tasks 1-2 were already committed (`63681b6`, `a4dc569`) and independently verified. Task 3's working tree already contained the production change and tests; 52 `reportUnknownArgumentType` / `reportUnknownLambdaType` / `reportAttributeAccessIssue` findings on those tests were the remaining gate.

The `rtk` wrapper intercepts bare `pytest` and collects zero tests; verification used `uv run python -c "import pytest, sys; sys.exit(pytest.main(['-q']))"`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 12-04 (verification). The update action is live, ownership-first, crash-contained, and coordinated with version refresh through a shared epoch. STATE.md and ROADMAP.md were left untouched per the executor prompt (orchestrator owns those in worktree mode).

No blockers.

---
*Phase: 12-version-aware-status-update-action*
*Completed: 2026-09-07*

## Self-Check: PASSED

- All cited production and test files present on disk.
- Commits `63681b6`, `a4dc569`, `55b9935` present in `git log`.
- `make validate` — ruff check/format, pyright, bandit, vulture, shellcheck all clean.
- Full suite via `uv run python -c "import pytest,sys; sys.exit(pytest.main(['-q']))"` — 0 failures (EXIT 0).
- Task 3 files `tests/test_catalog_tui.py tests/test_ui_common.py tests/test_wizard_app.py tests/test_setup.py tests/test_update.py` — all passed.
- `grep` for `run_command` imports in `installer/update.py` and `installer/catalog_tui.py` returns nothing.
- `grep` for `installer.engine` imports in `installer/update.py` returns nothing.
