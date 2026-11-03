---
phase: 21-one-screen-family
plan: "06"
subsystem: wizard-app
tags: [refresh, worker, coalescing, publish, textual]
requires: [21-01, 21-03]
provides:
  - UnifiedApp.request_refresh (one full-catalog pass, coalesced)
  - RefreshPublished / RefreshFinished
  - CatalogScreen.state_refreshed
  - UninstallScreen.state_refreshed (renamed from ownership_refreshed)
  - tests/screen_family.py settle / wait_until
affects: [21-07, 21-10, 21-13, 21-15, 21-20]
key-files:
  created:
    - tests/screen_family.py
  modified:
    - installer/wizard_app.py
    - installer/catalog_tui.py
    - tests/state_doubles.py
    - tests/test_screen_family.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_setup.py
status: complete
commits: 3
plan_head_before: 83003441e2c8c6ccf1c9765d6744f2c832730ee7
plan_head_after: 25f8142c4190ff2f04b2d905cbc454d92b24470e
actuals:
  tokens: 60000
  tasks: 2
  commits: 3
requirements: [UI-01, UI-08]
---

# Phase 21 Plan 06: One app-level refresh owner

`UnifiedApp.request_refresh()` runs one `refresh` + `refresh_skills` pass over the full catalog on one `full-catalog-refresh` worker, coalesces requests behind the running pass, and on each publication re-renders only the visible view through `state_refreshed()`. The catalog's per-tier refresh workers, flags and messages are deleted in the same commit.

## Commits
- 1e33b8b test(21-06): RED - app-level refresh owner pilots
- c6b9b87 feat(21-06): one app-level refresh owner publishes to the visible view
- 25f8142 test(21-06): pin the refresh owner's entry, coalescing and publish contracts

## TDD evidence

RED (commit 1e33b8b, `-k "launch_pass or failed_pass or failed_skills_stage or update_completion or install_close"`): 4 failed, 1 passed (the launch-pass tracer already held on the old per-tier path).

```
E  - tool state check failed: disk — the next change retries it
E  + tool state check failed: disk — leave and re-enter this view to retry
E  assert '' == 'tool state c...ge retries it'        (skills stage error was dropped)
E  assert 1 == 2        (u completion: service.passes)
E  assert 2 == 1        (install close with None requested a pass)
```

GREEN: same selection plus the whole file passes (34 tests). Task 2 tests (entry, coalescing, modal, keep, prune, supersede) passed on first run because Task 1 implements those contracts; they pin them: `test_entering_a_view_starts_no_pass[x6]`, `test_two_requests_during_a_pass_coalesce_into_one`, `test_publish_under_a_modal_waits_for_the_next_entry`, `test_publish_keeps_cursor_selection_and_status`, `test_publish_prunes_a_staged_tool_that_became_unavailable`, `test_a_mutation_during_a_running_pass_supersedes_it`. No `installer/` fix was needed in Task 2.

## Verification
- `make validate`: exit 0 on the final tree.
- `make test`: exit 0, 4989 passed, 4 skipped, coverage 96.03%.
- Suppression comments (`type: ignore|pyright: ignore|noqa|nosec`): 483 at base, 464 after (none added).
- Deleted names in `installer/` and `setup.py`: `version_refreshing`, `skill_refreshing`, `_start_version_refresh`, `_refresh_versions_worker`, `_refresh_skills_worker`, `VersionStatusRefreshed`, `SkillStatusRefreshed` all 0. catalog_tui `_state_line` 7 -> 0, `_version_refresh_generation` 5 -> 0, `post_message(OwnershipRefreshed` 1 -> 0. `group="full-catalog-refresh"` 1, `def request_refresh` 1, `def state_refreshed` in catalog_tui 1, `def ownership_refreshed` in wizard_app 0.
- Collected counts (start -> end): test_catalog_tui 214 -> 208 (floor 205), test_wizard_app 315 -> 315 (floor 315; one superseded-generation test deleted, one clean-publish test added), test_screen_family 22 -> 34 (floors 23 and 34).
- REUSE 06-1: `wait_until` is public in `tests/screen_family.py`; `_wait_until`, `_wait_for`, `_settle_versions` are gone from `tests/`.

## Decisions
- The worker keeps the first error of the pass; both publications carry it, so a clean publication means both stages succeeded.
- A status line written while no view is visible goes through `_pending_warnings` (deduplicated).
- `_visible_app_screen` returns None on an unmounted app (empty screen stack) so handlers driven directly in tests do not raise.

## Deviations from Plan

**1. [Rule 1 - Bug] First-run link-mode picker left rows at `…`**
- Found during: Task 1 design. The launch pass can publish while `LinkModeScreen` covers the view; under D-06 nothing re-renders and nothing re-entered the view afterwards.
- Fix: `_first_link_mode_picked` calls `_render_published()` first. Not in the plan; same intent as the install-close re-render.
- Files: installer/wizard_app.py. Commit: c6b9b87.

**2. [Rule 3 - Blocking] `tests/test_setup.py` fake app**
- `test_failed_direct_catalog_update_exits_1` borrows the real `on_tool_updated` onto a stub `_App`; the handler now calls `_render_published` and `request_refresh`, so the stub gets no-op versions. Commit: c6b9b87.

**3. Test expectations changed (each follows a locked rule)**
- Retry copy `— leave and re-enter this view to retry` -> `— the next change retries it` (21-06-PLAN truths, RESEARCH P5/O2).
- `test_quick_tier_switching_runs_one_full_pass`: hidden tiers render the published state on their next entry (D-06 top screen only), so the test re-enters each tier before reading its cell.
- `test_install_closed_refreshes_even_when_the_run_never_started` became `..._requests_no_pass_when_the_run_never_started` (A11: a pass only when the run ran something); the non-base-tier and terminal-sync tests count service passes instead of the deleted per-tier generation, and the non-base-tier test now makes the tool actually install.
- `test_returning_from_another_view_rereads_presence_through_the_pass` became `..._shows_the_state_a_pass_published` (entry starts no pass, D-05); it requests the pass a removal would.
- Deleted: the bare-screen handler tests (epoch guard, three `OwnershipRefreshed` post tests, skill epoch discard), `test_ver_cell_is_empty_without_a_state_whether_or_not_refreshing`, `test_version_navigation_discards_a_superseded_generation` (the per-tier flags/generation they exercised no longer exist; the app-level behavior is covered by the new pilots and the supersede backstop).

**4. Test adaptation**
- `tests/test_screen_family.py::_family_app` gained `version_refresh`, `updates` and `app_cls` parameters. `_install_closed` is driven through a test-local `UnifiedApp` subclass instead of a `pyright: ignore`.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
