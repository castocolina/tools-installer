---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "15"
status: complete
subsystem: catalog-ui
tags: [tool-state, health, catalog, legend, detail-bar, update, textual, tdd]

requires:
  - phase: 19-12
    provides: "ownership_notes / version_notes as ToolState.reasons"
  - phase: 19-13
    provides: "health_cell, _HEALTH_CELL/_HEALTH_DETAIL, state_of-driven decisions, tests/state_doubles.py"
  - phase: 19-20
    provides: "CatalogScreen/UnifiedApp without `installed`"
provides:
  - "Ver and Owner cells read only state_of (19-UI-SPEC Ver/Owner tables)"
  - "Focused-row detail = identity line + health block `{glyph} {label} — {reasons} — to configure: {steps}`, every reason/step escaped"
  - "_LEGEND = the 19-UI-SPEC three-line string (78/78/77 cells)"
  - "`u` reads the state: pending/CHECKING and BROKEN copies, UpdateTarget built from state.ownership"
  - "tests/state_doubles.py: FrozenStateService (publish, refresh/refresh_skills without probing), frozen_service, pass_state, unknown_ownership"
affects: [19-16, 19-17, 19-18]

actuals:
  tokens: 95000
  tasks: 3
  commits: 3
plan_head_before: b4f41b96470e1f5531eb87612d4a8f48ff95eb18
plan_head_after: af11c7d

tech-stack:
  added: []
  patterns:
    - "screen tests publish ToolStates on a FrozenStateService built by pass_state (owner and version sentences as notes, the way the pass builds them); no test assigns a service's private store"
    - "an update test changes the frozen machine from the update runner; the follow-up refresh re-publishes it at the new epoch"

key-files:
  created:
    - .planning/phases/19-one-tool-state-with-health-plus-receipts/19-15-SUMMARY.md
  modified:
    - installer/catalog_tui.py
    - tests/state_doubles.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_setup.py

key-decisions:
  - "FrozenStateService.refresh re-stamps the published states at the current epoch (a pass over an unchanged machine), so a post-update pass restores every row; refresh_skills is overridden too, because the base one rebuilds published pack states"
  - "The Ver stale suffix appears only when the cell compared against a latest (outdated is True or False), as before (19-UI-SPEC A13)"
  - "Owner is blank whenever there is no state (no `checking…` text); it is not gated on presence"
  - "detail_text stays one markup string: identity, a newline, then the health block (19-17 turns it into a Group)"
  - "`u` on a BROKEN row refuses with the first reason; a receipt-drifted row (BROKEN) is therefore no longer updated over the drift"
  - "ToolUpdated and VersionStatusRefreshed carry no status payload; the worker receives the UpdateTarget built from state.ownership"

requirements-completed: [STATE-02, STATE-06]

duration: ~2h
completed: 2026-10-16
---

# Phase 19 Plan 15: the cells, the detail bar, the legend and `u` read the one tool state

The Ver and Owner cells, the focused-row detail, the legend and the `u` action now read `state_of` only. A highlighted row shows why it has its mark and what it needs (`≈ needs configuration — a · b — to configure: s1; s2`). The legend is the 19-UI-SPEC key. `u` refuses a pending or broken row with the UI-SPEC copy. No catalog or wizard test writes a service's private stores any more.

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | 62166b3 | `_ver_cell` reads `state.version` (empty unless present with a readable version; no color; dim ` ~` only on a compared stale latest). `_owner_cell` reads `state.ownership`/`state.skill_hosts` (blank without a state). `FrozenStateService`, `frozen_service`, `pass_state` in tests/state_doubles.py. The Ver/Owner tests and the wizard `_freeze_status` helper (now returns a FrozenStateService) are converted. |
| 2 | fc839fa | `_detail_text` = identity line + `_health_block` (glyph in the Health style, detail label, escaped reasons, default-shell note, `— to configure:` escaped steps; with no state `… checking…` plus the launch-time unavailable detail). `_LEGEND` = 19-UI-SPEC string. Deleted `_version_detail`, `_skill_detail`, `_skill_status`, `_version_statuses`, `_VER_CHECKING/_VER_NO_VERSION/_VER_SOURCE_UNKNOWN/_VER_NO_COMPARISON`, the legend comment block, and the `statuses`/`status` message payloads. `u` reads version and ownership from the state. Every remaining private poke in the two test files converted. |
| 3 | af11c7d | `u` copies: pending or CHECKING → `cannot update {id}: its state is still being checked — try again in a moment`; BROKEN → `{id} is broken: {first reason}`. `_BROKEN_DETAIL` deleted. Test calls of `ownership_of`/`skill_status_of` switched to `state_of`. Source-scan test against private-store pokes. |

Tracer gate: Task 1's `<verify>` was rerun (catalog file green, 11 targeted tests) and `make test` passed (4414 passed) before Task 2 started.

## TDD RED evidence

Task 1 (tests and double first, against b4f41b9 code):
```
FAILED test_ver_cell_follows_the_state[unreadable-version3-]          'no version' == ''
FAILED test_ver_cell_follows_the_state[no latest-version4-1.2.3]      'no version' == '1.2.3'
FAILED test_ver_cell_follows_the_state[current-version5-1.2.3]
FAILED test_ver_cell_follows_the_state[outdated-version6-1.2.3 -> 1.3.0]
FAILED test_ver_cell_follows_the_state[stale current-version7-1.2.3 ~]
FAILED test_ver_cell_follows_the_state[stale outdated-version8-1.2.3 -> 1.3.0 ~]
FAILED test_owner_cell_follows_the_state                              'checking…' == 'Homebrew'
```
Task 2 (against 62166b3):
```
FAILED test_detail_health_block - IndexError: list index out of range
FAILED test_detail_labels_per_health - IndexError
FAILED test_detail_escapes_reasons_and_steps - 'reason [red]x[/]' not in 'rg — rg  |  P1 recommended  |  for both'
FAILED test_detail_identity_line_is_unchanged - ValueError: not enough values to unpack
FAILED test_default_shell_note_in_the_health_block
FAILED test_legend_is_the_ui_spec_string - '[bold red]P0...cached latest' != '[green]✓ ok[...nager owns it'
FAILED test_legend_lines_fit_78_cells - [69, 76, 77] != [78, 78, 77]
```
Task 3 (against fc839fa):
```
FAILED test_u_on_a_pending_row_says_checking   'cannot update rg: ownership data is being refreshed — …' != '… its state is still being checked — …'
FAILED test_u_on_a_broken_row_names_the_first_reason   ('updating rg…', 'ok') != ('rg is broken: changed since install', 'warn')
```
The second Task 3 failure shows the old gate started an update on a receipt-drifted (BROKEN) row. `test_u_uses_the_state_ownership`, `test_u_current_and_unknown_owner_copies_unchanged` and `test_no_test_pokes_private_service_stores` already passed at fc839fa, because Task 2 had moved the ownership read and the conversions (see Deviations).

## Verify results

- Task 1: `uv run pytest tests/test_catalog_tui.py -q --no-cov` green; `-k "ver_cell_follows or owner_cell_follows or frozen_state_service"` 11 passed (≥ 9).
- Task 2: catalog file green; `-k "detail_health_block or detail_labels or escapes_reasons or identity_line or default_shell_note or legend"` 12 passed (≥ 8).
- Task 3: `uv run pytest tests/test_catalog_tui.py tests/test_wizard_app.py -n auto -q --no-cov` green; `-k "u_on_a or u_uses_the_state or u_current or private_service_stores"` 5 passed (≥ 5).
- Acceptance greps:
  - `class FrozenStateService` in tests/state_doubles.py: 1. `ownership_of(` in catalog_tui.py: 4 at HEAD → 3 after Task 1 → 0.
  - `def _version_detail|def _skill_detail|_version_statuses|_VER_NO_COMPARISON|_VER_SOURCE_UNKNOWN` in catalog_tui.py: 0. `✓ ok\[/\] · \[yellow\]↑ update`: 1.
  - `its state is still being checked`: 1; `ownership data is being refreshed`: 0. Non-comment `ownership_of(|skill_status_of(|.statuses` in catalog_tui.py: 0. In tests/test_catalog_tui.py + tests/test_wizard_app.py: 0 + 0.
- `make validate` 0 and `make test` green before each commit: 4414 passed (Task 1), 4419 (Task 2), 4424 passed / 4 skipped, coverage 95.92% (Task 3, final tree).
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: empty (no new dependency).
- The real `~/.local/state/tools-installer/receipts` is still empty.

Suppression comments (`type: ignore|pyright: ignore|noqa|nosec` over installer/, setup.py, tests/), from b4f41b9 to af11c7d:
```
all: b4f41b9 590 -> fc839fa 503 -> af11c7d 503 (Task 3 adds none)
tests/test_catalog_tui.py 217 -> 137
tests/test_wizard_app.py   50 -> 43
tests/state_doubles.py, installer/catalog_tui.py: 0 -> 0
tests/test_setup.py 109 -> 109
```
The first draft of Task 3's `_u_screen` helper added 3 `type: ignore[method-assign]`; it was rewritten with `monkeypatch.setattr` and typed local functions, so Task 3 adds none.

Large-file evidence (guard run as a script file in the scratchpad; the sandbox refuses `bash -c` guards whose paths contain "git"):
```
Task 1 vs b4f41b9: catalog_tui.py 1102 -> 1051; test_catalog_tui.py 4661 -> 4608, tests 166 -> 169; test_wizard_app.py 8056 -> 8036, tests 301 -> 301; all end in a newline
Task 2 vs 62166b3: catalog_tui.py 1051 -> 885 (166 lines; guard budget 150, see Deviations); test_catalog_tui.py 4608 -> 4635, tests 169 -> 174; test_wizard_app.py 8036 -> 8036
Task 3 vs fc839fa: catalog_tui.py 885 -> 884; test_catalog_tui.py 4635 -> 4784, tests 174 -> 179; test_wizard_app.py 8036 -> 8036
git show --stat 62166b3: catalog_tui.py 105, state_doubles.py 125, test_catalog_tui.py 787, test_wizard_app.py 90 (549+, 558-)
git show --stat fc839fa: catalog_tui.py 292, test_catalog_tui.py 1273, test_setup.py 1, test_wizard_app.py 54 (740+, 880-)
git show --stat af11c7d: catalog_tui.py 20, test_catalog_tui.py 183, test_wizard_app.py 4 (178+, 29-)
```
Every hunk was checked with `git diff -U0 | grep ^@@` before each commit.

## Replaced or rewritten tests (Phase 18 test-integrity rule)

tests/test_catalog_tui.py unless named:
- `test_legend_names_every_ver_cell_marker_and_style_token` and `test_legend_uses_explicit_line_breaks_per_group`: replaced by `test_legend_is_the_ui_spec_string` and `test_legend_lines_fit_78_cells` (planned).
- `test_legend_widget_paints_every_marker_at_full_width` and `test_legend_keeps_the_catalog_table_usable_at_the_minimum_size`: the new marker list (and the dim entries `… checking`, `– unavailable`, `~`, `≠ policy`).
- `test_ver_cell_shows_probed_version_with_source_unknown_marker` → `test_ver_cell_shows_a_probed_version_without_a_source_marker` (cell `14.1.0`, reason `no latest version to compare against`).
- `test_ver_cell_shows_no_version_marker_when_nothing_was_probed_at_all` → `test_ver_cell_is_empty_when_no_version_was_read` (reason `version unreadable`).
- `test_ver_cell_dim_github_source_no_latest_shows_no_comparison_marker` → `test_ver_cell_github_source_without_latest_shows_the_bare_version`.
- `test_ver_cell_dim_unparseable_latest_keeps_installed_with_no_comparison_marker` → `test_ver_cell_unparseable_latest_shows_the_bare_version`.
- `test_ver_cell_dim_checking_marker_only_while_refreshing` → `test_ver_cell_is_empty_without_a_state_whether_or_not_refreshing`.
- `test_ver_cell_dim_six_situations_collapse_onto_exactly_four_texts` → `test_ver_cell_never_renders_a_dim_label`.
- `test_ver_cell_dim_stale_suffix_scoped_to_colored_branches_only` → `test_ver_cell_stale_suffix_only_qualifies_a_comparison` (same property, over the same situations).
- `test_ver_cell_renders_no_version_marker_for_unparseable_probe_output` → `test_ver_cell_is_empty_for_unparseable_probe_output`.
- `test_owner_column_says_checking_while_a_pass_is_in_flight` → `test_owner_column_is_blank_while_a_pass_is_in_flight` (UI-SPEC A9).
- `test_owner_column_renders_every_owner_value_in_both_branches` and `test_owner_column_is_blank_for_an_unknown_record`: the dim branch is now a real UNAVAILABLE state (a linux-only tool on macOS), because the state, not the launch map, decides once it exists.
- `test_version_detail_hand_writes_no_owner_vocabulary_of_its_own` → `test_detail_hand_writes_no_owner_vocabulary_of_its_own` (inspects `_detail_text` + `_health_block`; the `# noqa: SLF001` is gone).
- `test_version_detail_*` (prose register, installer mechanisms, os-package) assert on `_detail_text`.
- `test_skill_detail_lists_every_present_host_and_unprobed_hosts` → `test_skill_detail_reads_the_pack_state_reasons_and_steps` (the host list is the Owner cell's job).
- `test_epoch_guard_drops_a_superseded_version_refresh`: asserts that a raced message repaints nothing (it used to assert the deleted map stayed empty).
- `test_bare_true_unavailable_keeps_generic_copy` and `test_unavailable_catalog_row_is_dimmed_with_blank_sel_cell`: the detail says `not available on this machine` in the health block; the row's `(not available …)` suffix is unchanged.
- `test_update_on_broken_row_hints_repair_without_updating`: copy is now `mmdc is broken: {shim reason}`. `test_action_update_tool_reports_an_in_flight_refresh_instead_of_a_silent_noop`: copy is now `its state is still being checked`.
- `test_owner_column_starts_inside_the_viewport_at_the_minimum_size`: the `_version_statuses` poke became a `_ver_cell` override with the same worst-case text (the attribute is gone); geometry assertion unchanged.
- tests/test_wizard_app.py: `_freeze_status(tmp_path, tool, ownership=, status=)` returns a FrozenStateService (12 callers); the two post-update tests change the frozen machine from the update runner instead of monkeypatching `refresh`; `test_epoch_guard_drops_stale_refresh_after_update` holds the mount pass, updates, then releases the raced pass and checks the cell still shows the updated version; `test_version_shows_probed_install_when_latest_fetch_fails` expects `1.2.0` (no marker).
- tests/test_setup.py: `test_failed_direct_catalog_update_exits_1` builds `ToolUpdated` without the status argument.

## Deviations from Plan

1. **[Rule 3] Task boundaries shifted toward earlier tasks.** Task 1 made the Ver cell read the state, which broke the wizard tests that froze statuses through `service.refresh`; `_freeze_status` was therefore converted in Task 1 (planned for Task 3). Deleting `_version_statuses` in Task 2 forced every `u` test through the state, so Task 2 also moved `u`'s ownership read and the worker's `UpdateTarget` onto the state (planned for Task 3) instead of converting those tests twice. `_skill_status` was switched to `state.skill_hosts` in Task 1 and deleted in Task 2. Task 3 kept the copies, the new tests, the scan and the public-reader switches. Because of this, three of Task 3's five tests passed before its implementation (noted under RED evidence).
2. **Task 2 truncation guard budget.** installer/catalog_tui.py shrank by 166 lines in Task 2 (budget 150). The 16 extra lines are the `u` comment and branch moved in from Task 3 and the shortened `on_tool_updated` comment; every hunk is an intended deletion (checked with `git diff -U0`).
3. **[Rule 3, outside files_modified] tests/test_setup.py**, one line: `ToolUpdated` lost its `status` argument. That file belongs to parallel plan 19-16, so expect a possible one-line rebase conflict there.
4. **`ToolUpdated.status` dropped in Task 2**, not Task 3, together with `VersionStatusRefreshed.statuses` (the `on_tool_updated` branch wrote the deleted map).
5. **Copy changes beyond the plan text:** the identity line no longer carries `(not available on this machine)`; the health block says `not available on this machine` (the UNAVAILABLE detail label). The CatalogScreen docstring now says `updated {id}` rather than "the re-probed version".
6. **Tooling.** The worktree has no CodeGraph index, so code was read directly. Edits to the large files were applied with exact-count replacement scripts in the session scratchpad (`work-19-15/`), which were deleted afterwards. The plan-ledger file under `.git` could not be written (the sandbox refuses compound git paths); `plan_head_before` is b4f41b9 from the start check.

## Issues for the orchestrator

- **Rebase hot spot:** tests/test_setup.py line ~3367 (one deleted `None,`), shared with 19-16.
- **For 19-17:** `detail_text` is `identity + "\n" + health block` in one markup string; `#browser-detail` is still `height: 2` and wraps, so a long identity line can push the health block out of view until 19-17's Group/height-3 change lands.
- **For 19-18:** `test_no_test_pokes_private_service_stores` scans only tests/test_catalog_tui.py and tests/test_wizard_app.py; `ownership_of`, `statuses` and `skill_status_of` have no callers left in those two files or in catalog_tui.py (execute_screen.py and setup.py still call them).

## Self-Check: PASSED

- installer/catalog_tui.py, tests/state_doubles.py, tests/test_catalog_tui.py, tests/test_wizard_app.py, tests/test_setup.py exist and are committed.
- Commits 62166b3, fc839fa and af11c7d are ancestors of HEAD (`git log --oneline b4f41b9..HEAD` lists 3 before this summary commit).
