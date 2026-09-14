---
phase: 14-install-update-engine-correctness-default-shell-action-selec
plan: "02"
subsystem: install-execution
tags: [execute-screen, update-service, preflight, progress, post-run-report, textual]

requires:
  - phase: 14-install-update-engine-correctness-default-shell-action-selec
    provides: ExecuteScreen._to_update/_update_targets/_run_updates, recording UpdateService/VersionRefreshService doubles
provides:
  - Update-aware preflight head derived from _to_update
  - Progress rows for queued updates using the closed four-state glyph table
  - End-of-run sweep of leftover pending update rows into skipped/not_attempted
  - InstallRunFinished update payload (outcomes, errors, skips, versions)
  - Post-run update section reusing the u-keybind refusal and success wording
affects:
  - 14-03 (catalog Ver-column staleness after ExecuteScreen pop is still open)

actuals:
  tokens: 3836
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Disclosed-set vs dispatched-set asserted on separate fixtures (equality only on the undisturbed run)"
    - "Finish-handler sweep of leftover pending update rows instead of a second worker-side list"
    - "InstallRunFinished carries update results as defaulted constructor args so existing sites stay valid"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/test_execute_screen.py

key-decisions:
  - "Head count and progress rows both read the one _to_update list from 14-01; never recompute eligibility"
  - "D-03: cannot update {id}: {reason} and the in-flight sentence reused verbatim; heading is Updates"
  - "Refused/failed updates never enter Summary buckets or the run-level error"
  - "Post-success version re-probe goes through run_live; refusals and failures skip it"

patterns-established:
  - "Fixture A asserts disclosed == dispatched; fixtures B/C assert skip reporting only"
  - "Pending update rows that survive a finished run are swept to skipped and join not_attempted"
  - "Update section is silent when nothing was queued"

requirements-completed: ["D-01", "D-03"]

coverage:
  - id: D1
    description: Preflight head names install and update counts; update-only selection is not Install 0 tools?
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_preflight_head_names_install_and_outdated_update_counts_before_any_keypress
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_update_only_outdated_preflight_does_not_read_as_zero_work
        status: pass
    human_judgment: false
  - id: D2
    description: Fixture A — disclosed update ids equal dispatched ids, including a missing-status probe
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_undisturbed_outdated_run_dispatches_exactly_the_disclosed_update_ids
        status: pass
    human_judgment: false
  - id: D3
    description: Fixture B — cancel mid-update-tail sweeps the unreached row to skipped and names it in not_attempted
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped
        status: pass
    human_judgment: false
  - id: D4
    description: Fixture C — latch refusal never calls run, sweeps the row to skipped, and names it in not_attempted
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_latch_refused_outdated_update_row_is_swept_to_skipped
        status: pass
    human_judgment: false
  - id: D5
    description: A refused update produces cannot update {id}: {reason} only after InstallRunFinished and never changes install buckets
    requirement: D-03
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_reason_reaches_the_post_run_log
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_without_detail_falls_back_to_no_manager_claimed
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_reason_is_absent_from_the_log_until_the_run_finishes
        status: pass
    human_judgment: false
  - id: D6
    description: Latch refusal and run_live errors are reported; neither changes Summary buckets
    requirement: D-03
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_latch_refusal_reuses_the_in_flight_sentence
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_error_from_run_live_is_reported
        status: pass
    human_judgment: false
  - id: D7
    description: Successful updates use the u-keybind success line, re-probe only after success, and stay silent when nothing was queued
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_successful_outdated_update_is_named_in_the_post_run_log
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_successful_outdated_update_line_carries_outcome_extras
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_blocked_update_does_not_reprobe_the_version_cache
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_refresh_oserror_after_outdated_update_still_produces_the_report
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_update_section_is_silent_when_no_outdated_updates_were_queued
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-14
status: complete
---

# Phase 14 Plan 02: Install/Update Engine Correctness — Visible Updates Summary

**Selecting outdated tools now shows queued updates before enter, progress while they run, and a post-run report that reuses the u-keybind wording for both refusals and successes.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-09-14T16:05:00Z
- **Completed:** 2026-09-14T17:00:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Preflight head and progress list both enumerate `_to_update`; an update-only selection no longer reads as `Install 0 tools?`
- Finish-handler sweep turns leftover pending update rows into `skipped` and joins them to `not_attempted` (cancel, latch refusal, worker died before the tail)
- Post-run `Updates` section reports refusals with `cannot update {id}: {reason}`, latch skips with the in-flight sentence, and successes with the u-keybind line including the re-probed version

## Task Commits

Each task was committed atomically:

1. **Task 1: the preflight head and the progress list account for queued updates** - `623941c` (feat)
2. **Task 2: refused updates reach the post-run summary with the reused reason text (D-03)** - `655a0fd` (feat)
3. **Task 3: successful updates are reported, and the shared version cache is re-probed** - `c68bbc4` (feat)

## Files Created/Modified

- `installer/execute_screen.py` - update-aware head/progress, `UpdateToolFinished`, `InstallRunFinished` update payload, finish-handler sweep, `_render_updates` / `_updated_line`, post-success `run_live` re-probe
- `tests/test_execute_screen.py` - fixtures A/B/C, blocked_update D-03 cases, success/re-probe/silence cases

## Decisions Made

- Followed the plan as specified for D-01 visibility and D-03 wording.
- Head wording: `Install N tools, update M?` when both, `Update M tools?` when updates only; `enter start · esc cancel` kept verbatim.
- Update rows labelled `{id} update [{state}]` so they share the closed four-state glyph table.

## Follow-up (deliberately out of this plan)

`CatalogScreen` keeps its own copy of version statuses. Returning from the pushed `ExecuteScreen` does not re-enter the view, so the catalog Ver column can still show the pre-update value until the next refresh. That is a pre-existing Phase 13 screen-stack property; fixing it means touching `installer/wizard_app.py`'s modal-dismissal path.

## Deviations from Plan

None - plan executed exactly as written.

The 14-01 missing-ownership test's `refresh.asked == ["rg"]` assertion became `["rg", "rg"]` because the new post-success re-probe is a second `refresh` of the same tool. That is the Task 3 behaviour, not a scope change.

## Issues Encountered

- `make validate` caught a pyright `reportArgumentType` on `UpdateToolFinished.state` (Textual `Message` attributes default to `str`). Annotated the field as `ProgressState` and folded it into the Task 3 commit.
- `_run_execute` tears the app down before log widgets remain queryable; Task 2/3 log assertions drive the screen inside `run_test` instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for later 14 plans; D-01/D-03 batch-path visibility is closed.
- Catalog Ver-column staleness after ExecuteScreen pop remains a documented follow-up.

## Verification

- `uv run pytest tests/test_execute_screen.py -q` — pass (56 tests)
- `uv run pytest tests/test_execute_screen.py -k blocked_update -q` — pass (5 tests)
- `uv run pytest tests/test_catalog_tui.py -q` — pass
- `make validate && make test` — pass (2037 passed, 1 skipped, 95.35% coverage)
- `git diff --stat` lists only `installer/execute_screen.py` and `tests/test_execute_screen.py`

## Self-Check: PASSED

---
*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Completed: 2026-09-14*
