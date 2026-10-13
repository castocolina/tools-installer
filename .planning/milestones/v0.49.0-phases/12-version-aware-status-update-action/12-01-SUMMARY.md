---
phase: 12-version-aware-status-update-action
plan: 01
subsystem: ui
tags: [textual, catalog, github-release, version-cache, atomic-write, background-worker]

# Dependency graph
requires:
  - phase: 02-tier-scoped-catalog-views-recommends
    provides: "Three tier-scoped CatalogScreen instances sharing one UnifiedApp, with show_view as the single navigation path"
provides:
  - "installer/atomic.py — one sibling-temp-plus-os.replace writer (unique pid+uuid4 temp name) consumed by omz, daemon, and the version cache"
  - "installer/version_cache.py — timezone-aware JSON cache at ~/.local/state/tools-installer/versions.json with STALE_AFTER, RETRY_BACKOFF, and FUTURE_SKEW"
  - "installer/version_status.py — VersionRefreshService reconstructing status for every github_release tool, with fetch budget, epoch, and one-process merge lock"
  - "Catalog Ver column driven from setup.py::_build_app -> UnifiedApp -> CatalogScreen, refreshed on a Textual thread worker"
affects: [12-02-manager-version-resolution, 12-03-update-action]

# Actuals (#2632)
actuals:
  tokens: 5500
  tasks: 4
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One atomic writer (installer.atomic) with a unique sibling temp name; omz._atomic_write and daemon._atomic_write are delegations, so the version cache does not add a third copy of os.replace."
    - "A dedicated status comparator (parse_status_version / is_outdated) coexists with parse_version: the latter stays the three-component feature-floor parser; the former keeps every numeric component and orders prereleases individually."
    - "VersionRefreshService is constructed once in setup.py and shared by all three CatalogScreens; refresh is blocking and belongs on a Textual thread worker; generation discards a superseded screen pass and epoch discards a mutation-invalidated pass."
    - "A public version_refreshing flag (set in _start_version_refresh, cleared in on_version_status_refreshed for the current generation only) is the test-observable in-flight seam, matching DoctorScreen.globals_auditing."

key-files:
  created:
    - installer/atomic.py
    - installer/version_cache.py
    - installer/version_status.py
    - tests/test_atomic.py
    - tests/test_version_cache.py
    - tests/test_version_status.py
  modified:
    - installer/omz.py
    - installer/daemon.py
    - installer/versions.py
    - installer/catalog_tui.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_versions.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_setup.py

key-decisions:
  - "Task 1 extracted daemon's more general bytes+optional-mode writer as atomic_write_bytes and layered atomic_write_text on top; policy.py's two daemon._atomic_write call sites were left as private-name delegations so this plan did not widen a pure-refactor commit."
  - "parse_version is byte-for-byte unchanged. Update-status comparison goes through parse_status_version so a fourth numeric component or a distinct prerelease cannot produce a false up-to-date."
  - "Cache timestamps are read only through _parse_iso: naive, non-ISO, and far-future values are stale rather than raising or suppressing checks forever."
  - "github_repo() is a latest-version SOURCE lookup, not ownership. A provisional module-docstring paragraph records the wave-1 over-attribution; Plan 12-02 Task 3 deletes it when ownership routing lands."
  - "The merge lock is one-process/one-service. A second concurrently-running app instance is not a supported topology; unique temp names mean its worst case is last-writer-wins, never a corrupt file."

patterns-established:
  - "Composition-root injection of a shared background service: setup.py builds one VersionRefreshService and UnifiedApp threads it into every CatalogScreen."
  - "try/finally post_message plus exit_on_error=False so a domain exception outside run_live's (OSError, CommandError) still clears the in-flight flag and leaves the TUI running."

requirements-completed:
  - REQ-version-aware-status-github
  - REQ-cached-timestamped-version-state
  - REQ-background-version-refresh-worker

coverage:
  - id: D1
    description: "One atomic writer in installer/atomic.py with unique sibling temps; omz and daemon delegate without behavior change."
    requirement: REQ-cached-timestamped-version-state
    verification:
      - kind: unit
        ref: tests/test_atomic.py
        status: pass
      - kind: unit
        ref: tests/test_omz.py
        status: pass
      - kind: unit
        ref: tests/test_daemon.py
        status: pass
    human_judgment: false
  - id: D2
    description: "Catalog Ver column for codegraph, wired from setup.py through UnifiedApp into CatalogScreen, with stale marker and generation/epoch guards."
    requirement: REQ-version-aware-status-github
    verification:
      - kind: unit
        ref: tests/test_wizard_app.py#test_codegraph_ver_cell_contains_installed_and_latest_after_refresh
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_build_app_shares_one_version_refresh_service_across_tier_screens
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_stale_marker_is_visible_on_rendered_ver_cell
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_epoch_guard_drops_a_superseded_version_refresh
        status: pass
    human_judgment: false
  - id: D3
    description: "Every github_release tool gets a reconstructed status on view entry; fresh cache skips the network; failed lookups back off; MAX_FETCHES_PER_REFRESH=20; one-service two-thread merge survives."
    requirement: REQ-cached-timestamped-version-state
    verification:
      - kind: unit
        ref: tests/test_version_status.py
        status: pass
      - kind: unit
        ref: tests/test_version_cache.py
        status: pass
      - kind: unit
        ref: tests/test_catalog_tui.py#test_unparseable_probe_output_renders_unknown
        status: pass
    human_judgment: false
  - id: D4
    description: "Version refresh runs off the event loop, degrades to unknown on VersionError or a domain crash, and discards a superseded generation under rapid tier navigation."
    requirement: REQ-background-version-refresh-worker
    verification:
      - kind: unit
        ref: tests/test_wizard_app.py#test_version_refresh_runs_off_the_event_loop
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_version_unknown_on_network_failure
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_version_worker_crash_clears_refreshing_and_renders_a_cell
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_version_navigation_discards_a_superseded_generation
        status: pass
    human_judgment: false

# Metrics
duration: ~25 min (Task 4 resumption; Tasks 1-3 already committed)
completed: 2026-09-07
status: complete
---

# Phase 12 Plan 01: Version-Aware Catalog Status Summary

**The Catalog view now shows installed vs latest for every `github_release` tool, sourced from `resolve_github_tag` unchanged, persisted in an atomic JSON cache, and refreshed on a Textual thread worker wired from `setup.py`.**

## Performance

- **Duration:** ~25 min for Task 4 (this resumption). Tasks 1-3 were already committed on a prior run.
- **Started:** 2026-09-07 (Tasks 1-3 on `b728757`/`3a1daa9`/`b4fd7c7`; Task 4 resumed after a killed unattended run)
- **Completed:** 2026-09-07T13:02:03Z
- **Tasks:** 4/4
- **Files modified:** 16 (7 production created/modified, 1 composition-root, 8 test)

## Accomplishments

- One sibling-temp-plus-`os.replace` writer lives in `installer/atomic.py`; `omz` and `daemon` delegate to it, and the version cache is the third consumer rather than a third copy.
- Catalog `Ver` column compares full `--version` output against `resolve_github_tag` via a dedicated status parser that does not touch `parse_version`'s feature-floor contract. `setup.py::_build_app` injects one `VersionRefreshService` into all three tier screens.
- Every `github_release` tool gets a status on view entry: fresh cache reconstructs without a network call, failed lookups back off for six hours, a 20-fetch budget protects the unauthenticated GitHub rate limit, and a trailing dim ` ~` marks a stale latest.
- Refresh is proven off the event loop: a latched GitHub lookup still lets a keypress mutate selection; `VersionError` and a domain crash both leave the TUI running with a rendered `unknown` cell; rapid tier navigation discards a superseded generation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Prerequisite refactor — one atomic writer** — `b728757` (refactor)
2. **Task 2: End-to-end Ver column for codegraph** — `3a1daa9` (feat)
3. **Task 3: Generalize to every github_release tool** — `b4fd7c7` (feat)
4. **Task 4: Prove refresh never blocks, degrades, and survives rapid nav** — `bf79b52` (test)

**Plan metadata:** (this commit)

## Files Created/Modified

- `installer/atomic.py` — unique-temp `atomic_write_bytes` / `atomic_write_text`
- `installer/omz.py`, `installer/daemon.py` — `_atomic_write` delegations
- `installer/versions.py` — `probe_version_output`, `extract_observed_version`, `parse_status_version`, `is_outdated`
- `installer/version_cache.py` — JSON envelope, `_parse_iso`, staleness and retry arithmetic
- `installer/version_status.py` — `VersionStatus`, `github_repo`, `VersionRefreshService`
- `installer/catalog_tui.py` — Ver column, worker, generation/epoch guards, `version_refreshing`
- `installer/wizard_app.py` — `version_refresh=` threaded into three `CatalogScreen`s
- `setup.py` — composition-root construction of one shared service
- `tests/test_atomic.py`, `tests/test_version_cache.py`, `tests/test_version_status.py`, `tests/test_versions.py`, `tests/test_catalog_tui.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`

## Decisions Made

See `key-decisions` in frontmatter. Followed the plan: one writer, a second comparator, aware-only timestamps, one shared service, and a public `version_refreshing` flag so Task 4 could observe in-flight state without `reportPrivateUsage`.

## Deviations from Plan

None - plan executed exactly as written.

Task 4's `_settle_versions` helper was already sketched in Task 2 against `_version_statuses`; it now polls the public `version_refreshing` flag as the plan specified. No production behavior beyond that flag was added.

## Issues Encountered

This run was a resumption after the harness killed an unattended executor mid-plan. Tasks 1-3 were already committed and independently verified (`make validate` + full pytest green). Task 4 was executed against that HEAD; `setup.py` pyright findings on untyped `questionary` lambdas were ignored as instructed (they are outside `make validate`'s include).

The `rtk` wrapper intercepts bare `pytest` and collects zero tests; verification used `uv run python -c "import pytest,sys; sys.exit(pytest.main(['-q']))"`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 12-02 (manager version resolution / ownership routing). The provisional `github_repo()`-as-source paragraph in `installer/version_status.py` is the documented handoff: 12-02 Task 3 deletes it when ownership replaces wave-1 attribution. `VersionRefreshService.invalidate` is in place for Plan 12-03's update action.

No blockers. STATE.md and ROADMAP.md were left untouched per the executor prompt (orchestrator owns those in worktree mode).

---
*Phase: 12-version-aware-status-update-action*
*Completed: 2026-09-07*

## Self-Check: PASSED

- All cited production and test files present on disk.
- Commits `b728757`, `3a1daa9`, `b4fd7c7`, `bf79b52` present in `git log`.
- `make validate` — ruff check/format, pyright, bandit, vulture, shellcheck all clean.
- Full suite via `uv run python -c "import pytest,sys; sys.exit(pytest.main(['-q']))"` — 0 failures.
- Task 4 filter `version_refresh or version_off_the_event_loop or version_unknown or version_worker or version_navigation` — 5 passed.
