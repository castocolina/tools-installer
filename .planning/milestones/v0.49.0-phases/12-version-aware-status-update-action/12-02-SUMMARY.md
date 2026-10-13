---
phase: 12-version-aware-status-update-action
plan: 02
subsystem: ui
tags: [ownership, brew, pnpm, uv, manager-versions, version-cache, catalog]

# Dependency graph
requires:
  - phase: 12-version-aware-status-update-action
    provides: "Catalog Ver column, VersionRefreshService, timestamped versions.json cache, and github_repo() as a latest-version source (Plan 12-01)"
provides:
  - "installer/ownership.py — fail-closed ManagerOwnership from artifacts, manager inventories, and live PATH attribution; MUTATION_GRADE for Plan 12-03"
  - "installer/manager_versions.py — one batched outdated query per manager, preserving current AND latest"
  - "installer/run.py::run_query — the one bounded subprocess runner for every manager query in this phase"
  - "Manager snapshot under versions.json managers key; a fresh snapshot issues zero manager subprocesses; invalidate drops it"
  - "Catalog Ver cell sourced from ownership.owner, with owner/unknown-reason/pin/stale segments in _detail_text"
affects: [12-03-update-action]

# Actuals (#2632)
actuals:
  tokens: 5512
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ownership is a separate concept from resolve_methods ranking: provenance comes from artifacts + inventory membership + live PATH attribution, never from _RANK."
    - "None means unknown, never empty. A malformed manager report fails closed to None so silence cannot render as up to date."
    - "One manager query set per refresh pass, cached as one unit under versions.json; invalidate drops the snapshot and bumps epoch; a mid-flight epoch mismatch discards the write."
    - "Composition-root wiring only: setup.py supplies _DEFAULT_BIN_DIR and the detected Platform to VersionRefreshService."

key-files:
  created:
    - installer/ownership.py
    - installer/manager_versions.py
    - tests/test_run.py
    - tests/test_ownership.py
    - tests/test_manager_versions.py
  modified:
    - installer/run.py
    - installer/uninstall.py
    - installer/pnpm_globals.py
    - installer/version_cache.py
    - installer/version_status.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_uninstall.py
    - tests/test_pnpm_globals.py
    - tests/test_version_cache.py
    - tests/test_version_status.py
    - tests/test_catalog_tui.py
    - tests/test_setup.py
    - tests/test_wizard_app.py

key-decisions:
  - "Ownership is asserted only on an active-path match (direct) or complete negative evidence with no live binary (by-elimination). A live unattributable path is checked BEFORE by-elimination, so a stray ~/.local artifact cannot override /usr/bin or an unreadable brew inventory."
  - "The Owner literal covers brew/cask/pnpm/uv/installer only. dnf/apt/pacman/rpm_ostree resolve unknown by design in Phase 12."
  - "The manager snapshot is cached as one unit with MANAGER_STALE_AFTER=6h (shorter than GitHub's seven days) because it describes this machine. invalidate is what keeps the window honest for in-app mutations."
  - "github_repo() remains a latest-version SOURCE for installer-owned github_release tools; the Plan 12-01 provisional wave-1-source paragraph is deleted."

patterns-established:
  - "Fail-closed parsers: an unrecognized line or missing required field returns None for the whole report, never a partial map that would look like 'nothing outdated'."
  - "Epoch compare-and-discard: capture epoch before slow work, re-read it under the persist lock, drop the write on mismatch so a pre-update refresh cannot resurrect invalidated evidence."

requirements-completed:
  - REQ-manager-version-resolution
  - REQ-background-version-refresh-worker
  - REQ-cached-timestamped-version-state

coverage:
  - id: D1
    description: "Bounded run_query plus fail-closed ownership resolution from artifacts, inventories, and live PATH; MUTATION_GRADE is exactly direct and by-elimination."
    requirement: REQ-manager-version-resolution
    verification:
      - kind: unit
        ref: tests/test_run.py
        status: pass
      - kind: unit
        ref: tests/test_ownership.py
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py
        status: pass
      - kind: unit
        ref: tests/test_uninstall.py
        status: pass
    human_judgment: false
  - id: D2
    description: "One batched outdated query per manager, preserving current and latest; formulae and casks stay in separate maps; malformed reports return None."
    requirement: REQ-manager-version-resolution
    verification:
      - kind: unit
        ref: tests/test_manager_versions.py
        status: pass
    human_judgment: false
  - id: D3
    description: "Ver column sourced from ownership.owner; fresh manager snapshot issues zero queries; stale pass is a constant 7+1; invalidate drops the snapshot; mid-flight epoch mismatch discards the write."
    requirement: REQ-cached-timestamped-version-state
    verification:
      - kind: unit
        ref: tests/test_version_status.py#test_fresh_manager_snapshot_issues_zero_queries
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_stale_manager_snapshot_requeries_seven_plus_one
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_invalidate_drops_snapshot_and_bumps_epoch
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_refresh_discards_snapshot_when_epoch_changes_mid_flight
        status: pass
      - kind: unit
        ref: tests/test_version_cache.py
        status: pass
    human_judgment: false
  - id: D4
    description: "Catalog detail line names the owner, competing manager and active path, unknown_reason verbatim, pin, and stale explanation; installer-no-repo rows explain undetermined latest."
    requirement: REQ-background-version-refresh-worker
    verification:
      - kind: unit
        ref: tests/test_catalog_tui.py#test_detail_line_names_homebrew_for_brew_owned_row
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_unknown_owner_detail_contains_unknown_reason
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_stale_latest_has_marker_and_detail_explanation
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_build_app_constructs_version_refresh_with_default_bin_dir
        status: pass
    human_judgment: false

# Metrics
duration: ~20 min (Task 3 resumption; Tasks 1-2 already committed)
completed: 2026-09-07
status: complete
---

# Phase 12 Plan 02: Version-Aware Status Update Action Summary

**Ownership is now a tested concept, and the Catalog Ver cell takes current-vs-latest from the row's real owner — brew, cask, pnpm, uv, or this installer — with each manager queried at most once per refresh pass and not at all while the manager snapshot is fresh.**

## Performance

- **Duration:** ~20 min for Task 3 (this resumption). Tasks 1-2 were already committed on a prior run.
- **Started:** 2026-09-07 (Tasks 1-2 on `c20217e`/`e6c1058`; Task 3 resumed after a killed unattended run)
- **Completed:** 2026-09-07T14:25:07Z
- **Tasks:** 3/3
- **Files modified:** 19 (8 production created/modified, 1 composition-root, 10 test)

## Accomplishments

- `installer/ownership.py` decides which manager actually owns an installed tool from installer artifacts, real manager inventories, and live PATH attribution. `resolve_methods` ranking is never provenance. A brew-installed `rg` resolves `owner="brew"` even though `github_release` outranks `brew`. Partial or contradictory evidence fails closed to `unknown` with a stated `unknown_reason`.
- `installer/manager_versions.py` reads each manager's outdated report once per call through `run_query`, preserving both currently-installed and latest. Formulae and casks stay in separate maps from one `brew outdated --json=v2` payload. Malformed reports return `None`, never a partial map that would render as up to date.
- The Ver column is routed through `ownership.owner`. A timestamped manager snapshot under the same `versions.json` means a fresh pass issues zero brew/pnpm/uv queries; `invalidate` drops it and bumps the epoch; a refresh whose epoch changed mid-flight discards its own snapshot write. `_detail_text` names the owner, competing managers, `unknown_reason`, pin, and stale explanation.

## Task Commits

Each task was committed atomically:

1. **Task 1: One bounded query runner and the ownership model** — `c20217e` (feat)
2. **Task 2: One batched outdated query per manager, preserving current AND latest** — `e6c1058` (feat)
3. **Task 3: Route the Ver column through ownership, with one batched query set per refresh pass** — `6640deb` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `installer/run.py` — `QUERY_TIMEOUT`, `CommandError.stdout`, `run_query` with env merge and `accept_codes`
- `installer/ownership.py` — `ManagerInventory`, `OwnershipCandidate`, `ManagerOwnership`, `MUTATION_GRADE`, `read_inventory`, `resolve_ownership`
- `installer/uninstall.py` — public `manager_name` (rename from `_manager_name`)
- `installer/pnpm_globals.py` — fail-closed `parse_global_packages` on malformed project/group shapes
- `installer/manager_versions.py` — `ManagerVersion`, `OutdatedReport`, batched brew/pnpm/uv parsers and readers
- `installer/version_cache.py` — `ManagerSnapshot`, encode/decode, `MANAGER_STALE_AFTER` / `MANAGER_RETRY_BACKOFF`
- `installer/version_status.py` — `resolve_status` branched on `ownership.owner`, snapshot-aware `refresh`, full `invalidate`, `ownership_of`
- `installer/catalog_tui.py` — owner / unknown-reason / pin / stale segments on `_detail_text`
- `setup.py` — `_DEFAULT_BIN_DIR` wired into `VersionRefreshService`
- Tests: `tests/test_run.py`, `tests/test_ownership.py`, `tests/test_pnpm_globals.py`, `tests/test_uninstall.py`, `tests/test_manager_versions.py`, `tests/test_version_cache.py`, `tests/test_version_status.py`, `tests/test_catalog_tui.py`, `tests/test_setup.py`, `tests/test_wizard_app.py`

## Decisions Made

See `key-decisions` in frontmatter. Followed the plan: fail-closed evidence, one query set per pass, manager snapshot as one unit, epoch compare-and-discard, and `_detail_text` reading the ownership evidence fields.

## Deviations from Plan

None - plan executed exactly as written.

Task 3's uncommitted tree already implemented the specified behavior. This resumption typed the lambda fixtures (`read_inventory_fn` / `read_outdated_fn` / `is_installed` monkeypatch) and `_pinned_spec`'s versions map so strict pyright passed without silencing findings or loosening config.

## Issues Encountered

This run was a resumption after the harness killed an unattended executor mid-Task-3. Tasks 1-2 were already committed (`c20217e`, `e6c1058`) and independently verified. Task 3's working tree already contained the production change and tests; 15 `reportUnknownArgumentType` / `reportUnknownLambdaType` / `reportPrivateUsage` findings on those tests were the remaining gate.

The `rtk` wrapper intercepts bare `pytest` and collects zero tests; verification used `uv run python -c "import pytest, sys; sys.exit(pytest.main(['-q']))"`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 12-03 (mutating update action). `MUTATION_GRADE` and `VersionRefreshService.ownership_of` / `invalidate` are the seams 12-03 imports: mutate only on `direct` or `by-elimination`, refuse `unknown` with the same `unknown_reason` the detail line already shows, and call `invalidate` after every successful update.

No blockers. STATE.md and ROADMAP.md were left untouched per the executor prompt (orchestrator owns those in worktree mode).

---
*Phase: 12-version-aware-status-update-action*
*Completed: 2026-09-07*

## Self-Check: PASSED

- All cited production and test files present on disk.
- Commits `c20217e`, `e6c1058`, `6640deb` present in `git log`.
- `make validate` — ruff check/format, pyright, bandit, vulture, shellcheck all clean.
- Full suite via `uv run python -c "import pytest,sys; sys.exit(pytest.main(['-q']))"` — 0 failures (EXIT 0).
- Task 3 filter `tests/test_version_cache.py tests/test_version_status.py tests/test_catalog_tui.py tests/test_setup.py` — all passed.
- `grep` for subprocess imports in `installer/ownership.py` and `installer/manager_versions.py` returns nothing.
- Working tree clean after this SUMMARY commit.
