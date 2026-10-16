---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "18"
subsystem: tool-state consumers (execute screen, update service, composition root)
status: complete
tags: [state, D-03, D-04, D-14, refresh-service, execute-screen, update]
requires: ["19-09", "19-14", "19-16", "19-17"]
provides:
  - "VersionRefreshService.resolve_owner(tool) and private _resolve_owner_from (the one resolve_ownership caller)"
  - "UpdateService(live_platform=...) read at run time"
  - "ExecuteScreen live platform + state-driven repair/current/update targets"
  - "state_of as the only per-tool reader; refresh() -> None"
affects: [installer/catalog_tui.py, installer/uninstall.py, tests/test_catalog_tui.py]
tech-stack:
  added: []
  patterns: ["composition-root seam swap in tests (setup.VersionRefreshService -> FrozenStateService / subclass) instead of private-store pokes"]
key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - installer/update.py
    - installer/version_status.py
    - setup.py
    - tests/test_execute_screen.py
    - tests/test_update.py
    - tests/test_setup.py
    - tests/test_version_status.py
    - tests/state_doubles.py
    - installer/catalog_tui.py
    - installer/uninstall.py
    - tests/test_catalog_tui.py
key-decisions:
  - "Repair stays the pnpm-shim case (state.ownership.broken); a drifted BROKEN state is never repaired (Pitfall 10)"
  - "resolve_owner re-reads has_brew but does not publish or replace the service platform; only a pass does"
  - "Held skill answers are read in tests through refresh_skills(()) (a probe-free read), since skill_status_of is gone"
  - "ExecuteScreen also uses the live platform for post-install reapply, not only availability and run_installs"
requirements-completed: [STATE-01, STATE-05]
duration: ~2h
completed: 2026-10-16
actuals:
  tokens: 47000
  tasks: 3
  commits: 3
plan_head_before: 08aeed80137c82b52bbb412f1a52777ee6229ccc
plan_head_after: f266afd
---

# Phase 19 Plan 18: Consumers read the one state and the live platform

Every consumer now reads presence, ownership and the platform from the one refresh service. The execute screen and the update service use the live platform, so a brew that appears mid-session makes colima installable and updatable. Install skip, uninstall rows, owner hints and update re-resolution all go through `state_of`, `is_present` and `resolve_owner`. `ownership_of`, `statuses`, `skill_status_of` and their stores are deleted, and `refresh` returns None.

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | e5249ee | `ExecuteScreen._platform()` returns `version_refresh.platform` when a service is bound. It is used for dependency availability, `run_installs` and post-install reapply. `_classify_selection`, `_update_targets` and `_run_updates` read `state_of`, and the new version after an update is `state_of(id).version.installed`. `UpdateService(live_platform=...)` is read once per `run`. The execute-screen doubles now seed state through `FrozenStateService.publish`, which removed 8 private pokes. |
| 2 | a783a20 | `resolve_owner(tool)` gathers fresh evidence: has_brew re-read, a fresh `read_inventory_fn`, `uv tool dir`, look-through `which` and the native probe. It then calls the private `_resolve_owner_from`, which is also what the pass calls with its batched evidence. In setup.py, `ExecuteInputs.installed=is_present`; the bound install forwards `present=is_present` to `install_tool`; uninstall rows use `is_present`; owner hints use `state_of`; `reresolve_ownership=version_refresh.resolve_owner`; `live_platform=lambda: version_refresh.platform`. The local `_reresolve_ownership` and its imports are gone. |
| 3 | f266afd | Deleted `ownership_of`, `statuses`, `skill_status_of`, `_ownership` and `_statuses`, and rewrote the old one-map comments. `refresh`/`_pass` return None, and the flight now carries only a failure. `FrozenStateService.refresh` and the four execute-screen overrides return `-> None`. The private-store poke scan now covers every `tests/*.py` except state_doubles.py. |

The tracer gate (auto mode, end-of-phase) passed: Task 1's `<verify>` re-ran green end to end before Task 2 started.

## TDD RED evidence

Task 1 (before implementation):
```
test_brew_appearing_mid_session_unblocks_colima: AssertionError: assert [] == ['colima']
test_classify_reads_the_state: AssertionError: assert [] == ['shim']
test_run_updates_reads_ownership_and_version_from_state: AssertionError: assert [] == ['from-state']
test_update_service_reads_the_live_platform: TypeError: UpdateService.__init__() got an unexpected keyword argument 'live_platform'
(+ 30 converted update/repair tests failing: ownership_of/statuses read stores the doubles no longer seed)
```
Task 2:
```
test_install_binding_passes_present: AttributeError: <module 'setup'> has no attribute 'install_tool'
test_resolve_owner_uses_the_pass_evidence: AttributeError: 'VersionRefreshService' object has no attribute 'resolve_owner'
test_pass_still_makes_one_native_query_with_resolve_owner: AttributeError: ... no attribute 'resolve_owner'
test_uninstall_rows_and_hints_read_the_state: AssertionError: assert 'dnf remove ripgrep' in 'managed outside this installer — remove with your package manager — ...'
test_execute_inputs_presence_is_the_state: AssertionError: assert <function is_installed> == is_present
test_update_service_reresolves_through_the_service: AssertionError: assert [] == ['rg']
test_update_service_reads_the_live_platform_through_the_service: assert [] == [False, True]
(+ 6 converted setup tests)
```
Task 3:
```
test_service_has_no_transitional_readers: AssertionError: ownership_of — assert not True (hasattr(VersionRefreshService, 'ownership_of'))
test_the_service_publishes_one_snapshot_of_tool_states: AssertionError: assert 3 == 1 (the VersionStatus map and the ownership map beside the skill store)
```

## Replacements and conversions (Task 3, scripted with asserted counts)

- `test_the_service_holds_one_epoch_tagged_ownership_map_not_two` was replaced by `test_the_service_publishes_one_snapshot_of_tool_states`.
- `test_a_raced_refresh_publishes_no_ownership_record_or_epoch` was replaced by `test_a_raced_refresh_publishes_no_state`, which uses public reads only: `state_of` plus the version cache.
- `test_ownership_of_answers_fail_closed_across_commit_and_invalidate_boundaries` was replaced by `test_state_of_answers_fail_closed_across_commit_and_invalidate_boundaries`.
- `test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record` was replaced by `test_state_of_under_an_unsynchronized_reader_never_serves_a_superseded_state`. The identity check now runs on `ToolState`.
- `test_ownership_of_returns_last_pass_and_none_for_missing` was replaced by `test_state_of_returns_last_pass_and_none_for_missing`.
- `test_ownership_of_returns_none_for_a_record_older_than_the_current_epoch` was replaced by `test_state_of_returns_none_for_a_state_older_than_the_current_epoch`.
- Added `test_service_has_no_transitional_readers` and `test_no_test_file_pokes_private_service_stores`.
- Scripted counts:
  - `statuses = X.refresh(...)` became `_versions(X, ...)` at 6 sites.
  - `service.ownership_of(tool.id)` became `state_of` at 4 sites.
  - `service.skill_status_of(` became `_held_skills(service).get(` at 8 sites.
  - Prose mentions of `` `ownership_of` `` were updated at 3 sites.
  - The two jq ownership reads were converted.
  - The race tests dropped their `statuses`/`ownership_of` snapshots and kept the `state_of` identity checks.
  - `test_identical_passes_share_one_flight` now checks that both callers finished, not that two return dicts were equal.
- In tests/test_setup.py (Task 2), 3 private `_ownership` pokes and 1 `ownership_of` read became `FrozenStateService.publish` / `state_of`, through a `_bind_refresh` seam on `setup.VersionRefreshService`.

## Verify results

- Task 1: `pytest tests/test_execute_screen.py tests/test_update.py -n auto` passed. The `-k "brew_appearing or classify_reads or run_updates_reads or live_platform"` selection ran 4 tests and all 4 passed. Guard: execute_screen 1143 -> 1148, test_execute_screen 4367 -> 4530 (tests 108 -> 111), test_update 1395 -> 1431 (55 -> 56), update.py 542 -> 545.
- Task 2: `pytest tests/test_setup.py tests/test_version_status.py -n auto` passed. The `-k` selection ran 8 tests and all passed (the gate requires at least 7). Greps:
  - `def resolve_owner` = 1
  - `is_present` in setup.py = 3
  - `def _resolve_owner_from` = 1
  - non-comment `resolve_ownership(` in version_status.py = 1
  - `resolve_ownership(` in setup.py = 0

  Guard: setup.py 1572 -> 1573, version_status.py 1629 -> 1671, test_setup 3633 -> 3827/3830 (121 -> 126), test_version_status 4728 -> 4809 (146 -> 148).
- Task 3: `uv run pytest -n auto -q --no-cov` passed. The transitional-reader grep over installer/*.py and setup.py has 0 hits, and `self._ownership|self._statuses` = 0. Guard: version_status.py 1671 -> 1618, test_version_status 4809 -> 4832 (148 -> 150), test_setup 3830 -> 3830, test_execute_screen 4530 -> 4522 (111 -> 111). Suppressions went from 490 to 487 against Task 3's HEAD, and from 503 to 487 across the whole plan.
- Before each commit: `make validate` exit 0 and `make test` passed. Final `make test`: 4493 passed, 4 skipped, coverage 95.95%.
- `pyproject.toml` and `uv.lock` are unchanged since fde3e68. The real receipts dir is still empty.
- Final wc -l: execute_screen 1148, update 545, version_status 1618, setup 1573, test_execute_screen 4522, test_update 1431, test_setup 3830, test_version_status 4832, state_doubles 232, catalog_tui 889, test_catalog_tui 4768.
- `git diff --stat 08aeed8..HEAD`: 12 files, +852 / -364.

## Deviations from Plan

1. **[Rule 1 - Bug] installer/catalog_tui.py (outside files_modified), Task 3.** The refresh worker set `warning = service.warning` only when `refresh` returned a value. Once `refresh` returns None, the cache-save warning would never surface. It now reads the warning when `run_live` reports no error.
2. **[Rule 3 - Blocking] tests/test_catalog_tui.py (outside files_modified), Task 3.** `assert service.refresh([tool]) == {...}` now reads `state_of`. The `recording` refresh wrapper now returns None, to match the base signature under strict pyright.
3. **[Rule 1] installer/uninstall.py (outside files_modified), Task 3.** Two comments named the deleted `ownership_of`; they now name `state_of`. Comment-only change.
4. **tests/test_setup.py, Task 2.** `_hermetic_route` now patches `setup.install_tool`, the engine call the bound install forwards to. It used to replace `install`/`installed` at the `_execute_inputs` seam, which the composition root now overrides by design (D-04). `_recording_install` accepts `present=`. `test_native_probe_is_wired_at_both_the_display_and_mutation_sites` was renamed to `..._wired_once_and_the_mutation_site_reuses_the_service`, because `native_probe=` now appears once and the mutation path goes through `resolve_owner`.
5. **installer/execute_screen.py, Task 1.** The live platform also feeds `reapply_post_install` (D-14 "every consumer reads it"); the plan names only two sites.
6. **New `pyright: ignore[reportPrivateUsage]`, Task 1.** 4 new suppressions in tests/test_execute_screen.py read `screen._repair`/`_current`/`_to_update`/`_ordered`, the same pattern the file already uses. The plan's net suppression gate still passes: 503 -> 487.

## Issues for the orchestrator

- `tests/test_run.py::test_streaming_runner_emits_incrementally_before_child_exits` failed once during a whole-suite `--no-cov` run under load and passed on rerun and in both later `make test` runs. It is a timing-sensitive test, unrelated to this plan.
- tests/test_catalog_tui.py still has the 19-15 `test_no_test_pokes_private_service_stores`. The new test_version_status.py scan covers it, so it can be dropped later.
- Files touched outside files_modified (for rebase): installer/catalog_tui.py, installer/uninstall.py, tests/test_catalog_tui.py.

## Self-Check: PASSED

- Commits e5249ee, a783a20 and f266afd are on the branch.
- Every key file listed above exists.
