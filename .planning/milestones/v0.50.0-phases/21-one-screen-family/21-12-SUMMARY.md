---
phase: 21-one-screen-family
plan: "12"
subsystem: uninstall-view
tags: [textual, uninstall, state-projection, deletion, tdd]
requires: ["21-08", "21-11"]
provides:
  - "UninstallScreen built from the published tool state (uninstall_group / uninstall_label / uninstall_detail)"
  - "_reread_env: publish re-reads ban, PATH block and tweaks"
  - "standing 'Nothing to uninstall.' written only when every state is known, retracted only while still shown"
affects: [21-13, 21-14, 21-15]
tech-stack:
  added: []
  patterns: ["painted-memory for unknown state", "state projection instead of a second classifier"]
key-files:
  modified:
    - installer/wizard_app.py
    - setup.py
    - installer/uninstall.py
    - installer/ownership.py
    - installer/resolve.py
    - installer/registry.toml
    - .claude/architecture.md
    - tests/state_doubles.py
    - tests/test_wizard_app.py
    - tests/test_uninstall_e2e.py
    - tests/test_layout_80x20.py
    - tests/test_setup.py
    - tests/test_screen_family.py
    - tests/test_policies_e2e.py
    - tests/test_execute_screen.py
    - tests/test_catalog_tui.py
    - tests/test_uninstall.py
    - tests/test_ownership.py
    - tests/test_version_status.py
decisions:
  - "A row with an unknown state reuses the entry last painted from a known state (Health cell set to the unknown glyph); a never-painted row is an unselectable 'nothing to do' row"
  - "The repaint method keeps the 21-11 name _repaint (Widget._render collision)"
metrics:
  tasks: 3
  completed: 2026-11-03
status: complete
actuals:
  tokens: 90000
  tasks: 3
  commits: 6
plan_head_before: c43b3b5f77f1f98476bca5f6d4c3140aa06a66bb
plan_head_after: 1fe9fa05732563d2ef893d35c476d13407cf8f87
commits: 6
---

# Phase 21 Plan 12: Uninstall as a projection of the published state Summary

The Uninstall view now builds every tool row from `state_of` through `uninstall_group`, `uninstall_label` and `uninstall_detail`, re-reads its three environment predicates on every publish, and the whole second classification (`classify_tools`, `ToolRow`, the owner hints, the rows closures in `setup.py`, the `_VIA_*` constants and the script-install special case) is deleted in this one plan.

## Commits

- 3433a54 test(21-12): Uninstall draws its rows from the published state (RED)
- b135815 feat(21-12): Uninstall renders from the published tool state
- cb9b85e test(21-12): the Uninstall view reads the app catalog and service, with no rows seam (RED)
- 8a70dd9 refactor(21-12): delete the Uninstall rows seam and setup's rows closure
- f074bbc test(21-12): an installer-owned script record is treated like every installer record (RED)
- 1fe9fa0 refactor(21-12): delete the Uninstall classification and the script-install removal special case

## RED output

Task 1 (12 new tests collected from the new block, 11 failing for the right reason before the screen changed; the 12th, `test_uninstall_detail_markup_renders_literally`, passed only after its assertions were corrected to the real detail text):
```
FAILED test_uninstall_draws_three_sections_from_the_published_state
FAILED test_uninstall_rows_change_when_a_pass_publishes
FAILED test_uninstall_offers_nothing_before_the_first_pass
FAILED test_uninstall_nothing_installed_draws_only_nothing_to_do
FAILED test_uninstall_unpublished_row_keeps_its_painted_section
FAILED test_uninstall_unknown_owner_row_names_no_manager
FAILED test_uninstall_broken_row_shows_the_repair_text
FAILED test_uninstall_detail_markup_renders_literally
FAILED test_a_publish_rereads_the_environment_rows
FAILED test_a_publish_that_adds_an_env_row_retracts_nothing_to_uninstall
FAILED test_a_failed_env_read_on_publish_keeps_rows_and_status
  (last: Could not refresh the tool list: denied; denied.  vs  written)
```
Task 2:
```
AssertionError: assert 'rows' not in {'ban_names', 'has_path_block', 'invalidate', 'remove', 'rows', 'terminal_sync', ...}
```
Task 3:
```
FAILED tests/test_ownership.py::test_script_kind_installer_record_is_treated_like_every_installer_record
FAILED tests/test_version_status.py::test_uninstall_script_install_shows_its_reasons_and_label
  assert UNPROVEN_NOTE in "installed by its own installer — remove it with that installer's own uninstaller — found at ..."
```

## GREEN

After every implementation commit `make validate` exit 0 and `make test` exit 0 (final tree: 5011 passed, 4 skipped, coverage 96.11%).
Task 1 tree: 5036 passed. Task 2 tree: 5034 passed.

## Test counts (start -> end)

| File | Start | End | Floor |
| --- | --- | --- | --- |
| tests/test_wizard_app.py | 323 | 320 | plan 334 (see deviation 2) |
| tests/test_uninstall.py | 120 | 96 | 96 |
| tests/test_version_status.py | 222 | 223 | 223 (orchestrator) |
| tests/test_setup.py | not measured | 151 | start minus 2 (three closure tests became one; two rewritten) |
| tests/test_uninstall_e2e.py | 3 | 3 | 3 |
| tests/test_layout_80x20.py | 15 | 15 | 15 |

## Deleted tests (reason: the code they exercised is deleted)

tests/test_uninstall.py, 23 `test_classify_*` functions (24 collected items): test_classify_removable_when_artifacts_on_disk, test_classify_managed_when_installed_without_artifacts, test_classify_managed_cask_hint, test_classify_managed_seam_fed_apt_hint_names_apt, test_classify_managed_generic_hint_when_no_seam_and_no_brew_method, test_classify_managed_seam_returning_none_falls_back_per_tool, test_classify_managed_seam_only_consulted_for_managed_rows, test_classify_managed_codex_gets_generic_hint_on_linux_not_homebrew, test_classify_managed_codex_keeps_cask_hint_on_macos, test_classify_managed_brew_only_tool_gets_generic_hint_without_brew, test_classify_managed_linuxbrew_cask_tool_gets_generic_fallback_on_linux, test_classify_managed_seam_hint_gets_found_at_suffix, test_classify_managed_sdkman_tool_names_sdkman_on_every_platform, test_classify_managed_brew_hint_uses_formula_not_cmd, test_classify_managed_cask_hint_uses_cask_name_not_cmd, test_classify_managed_brew_hint_falls_back_to_cmd_without_formula, test_classify_managed_cask_hint_falls_back_to_cmd_without_cask, test_classify_managed_shows_resolved_path, test_classify_absent_when_not_installed, test_classify_unavailable_when_no_method_applies, test_classify_returns_a_row_per_tool_in_order, test_classify_appends_required_by_note_to_hint, test_classify_without_reverse_deps_leaves_hint_unchanged; plus the six helpers they alone used (`_dl`, `_brew`, `_cask`, `_apt`, `_linuxbrew_cask_tool`, `_sdkman_tool`).

tests/test_wizard_app.py (rows predicate / registry-guess behavior no longer exists):
- test_uninstall_rows_change_makes_new_tool_ids_reachable, test_uninstall_tool_becomes_selectable_when_rows_reports_it_removable (covered by `test_uninstall_rows_change_when_a_pass_publishes`)
- test_precedence_failure_wins_over_a_standing_applied_summary_when_unchanged, test_precedence_failure_still_wins_when_environment_rows_also_changed, test_uninstall_does_not_refresh_after_it_has_applied_when_unchanged (the `_resync` precedence rules are deleted; a nav entry now always clears `applied`, per the plan)
- test_env_predicate_failure_inside_the_rows_failure_branch_never_escapes_nav (the branch is deleted)
- test_no_uninstall_construction_site_hands_rows_a_bare_list, test_the_rows_predicate_is_re_read_on_every_entry (the rows field is gone)
- test_uninstall_screen_cell_falls_back_when_seam_has_no_record, test_uninstall_screen_cell_reflects_post_run_ownership_map, test_uninstall_next_entry_after_removal_shows_registry_phrase_not_pre_removal_attribution, test_uninstall_direct_initial_view_renders_registry_phrase_with_no_ownership_pass, test_uninstall_screen_renders_codex_generic_hint_on_linux_not_homebrew, test_uninstall_screen_renders_ripgrep_not_rg_for_the_dnf_split_package (they pinned the registry-guess hints and the `which`/owner-hint seam; 21-08 pins the projection text)

tests/test_setup.py: test_the_uninstall_rows_closure_re_reads_presence_live, test_the_uninstall_rows_closure_calls_presence_once_per_catalog_tool, test_uninstall_rows_and_hints_read_the_state (replaced by `test_the_uninstall_view_reads_the_app_catalog_and_service`).

## Tests rewritten (expected text changed, reason)

- test_wizard_app.py: the unchanged-rows, tool-disappearing, rows-failure and construction-failure tests became `test_uninstall_reentry_repaints_equal_entries`, `test_uninstall_tool_disappearing_drops_its_stale_selection`, `test_uninstall_env_failure_during_enter_view_keeps_previous_rows_and_warns` and `test_uninstall_construction_env_failure_yields_a_usable_screen_that_self_heals` (environment predicate instead of rows; warn copy is now `Could not read the uninstall state: {error}.`). `test_env_predicate_failure_during_a_background_repaint_never_escapes` now expects the env warn only. `test_tool_entry_cell_per_state_and_removes_cell_lists_the_paths` reads `uninstall_label`. `test_install_closed_then_navigating_to_uninstall_shows_the_post_install_state` reads the published Health cell. The three `state_refreshed` app tests spy on `state_refreshed` instead of counting `rows()` calls. The 21-11 Health tests pass `tools=` over a service that already holds the states.
- test_setup.py: `test_build_app_uninstall_hint_*` became `test_build_app_uninstall_detail_*`; after an invalidate the row keeps its painted text and reads `…`.
- test_screen_family.py: the startup-error test fails an environment predicate; the flushed-warning test publishes absent states so the standing copy is true.
- test_ownership.py: the script-install test now asserts both hints are `None`.
- test_layout_80x20.py: see deviation 3.
- The old default app now lists the catalog tools `rg` and `fd` (unpublished, `checking…`); tests that need only environment rows pass `cases=[]`.

## Deviations from Plan

1. **[Rule 3 - Blocking] `_repaint`, not `_render`.** Used the 21-11 name (Widget._render collision), as the orchestrator instructed.
2. **Test floor for tests/test_wizard_app.py is 320, not 334.** The plan's floor assumed no deletions; the 15 listed deletions (their subject is deleted code) outweigh the 12 new tests. Not padded with filler tests.
3. **[Rule 1] 80x20 backstop lead 12 -> 8 cells.** The "Installed via" cell is now `uninstall_label` (for example `installer artifact`) instead of the 9-cell `userspace`, so the last column starts 70 cells in with the widest catalog id; the assertion that the column starts at least 8 cells inside the screen replaces 12. The 40-cell budget bound is unchanged.
4. **Task 2 test_setup count not measured at start.** Final count 151; the three closure tests became one, and two were rewritten.
5. A test-only `_app(cases=, tools=)` parameter publishes states onto a frozen service so the ~60 migrated pilots stayed one-line edits.

## Known Stubs

None.

## Threat Flags

None. T-21-18 (no row selectable before a state proves it) is pinned by `test_uninstall_offers_nothing_before_the_first_pass`; T-21-19/T-21-49 by the retract and re-read pilots; T-21-35/T-21-36 by the absence grep (empty over `installer/`, `setup.py`, `tests/`, `.claude/architecture.md`) and the script-install pilots.

## Self-Check: PASSED

All six commits are reachable from HEAD; `make validate` and `make test` exit 0 on the final tree.
