# Phase 34 Plan 01 Summary

- **Task 1 — engine and eighth row:** `ad7becfd` adds the daily `check-updates` row, runner arguments, notified-set artifact, uninstall handling and eight-row layout.
- **Task 2 — Schedules view:** `ff843b32` makes the five cadence sites read `Schedule.daily` and adds pilot tests for the daily detail and time editor.

## Verification

- **Task 1:** The commit and its tests are present. Its original RED output, pre-pin failing IDs and GREEN output were not available in this split run, so the claimed set of exactly 29 failures could not be independently confirmed.
- **Task 2 RED:** Both new tests failed as intended: the detail showed `times: 09:00 (local)`, and the editor displayed an interval selector.
- **Task 2 GREEN:** The prescribed three-file targeted pytest command passed. Additional tests covering `schedules_screen` imports also passed.
- **Commit hook and `make validate`:** lint, format-check, typecheck, security, dead-code and shellcheck all passed.
- **`make test`:** `9155 passed, 6 skipped`; coverage **96.37%**, exceeding the 90% requirement.
- Each scratch run directory created in this run was removed by its exit trap.

## Decisions

- **34 D-02, locked:** Append `check-updates` as the eighth row, with a 24-hour cadence and 09:00 start; leave `UPDATE_SCHEDULE_IDS` unchanged.
- **34 D-03, locked:** Reuse the existing unit and plist templates; add only a runner-argument branch.
- **34 D-05, own reasoning, needs confirmation:** Enable the new row by default through generic reconcile.
- **34 D-06, locked, jev fixed_daily 0.99:** Make cadence a `Schedule.daily` property, true for tmp cleanup and the update check.
- **34 D-07, own reasoning, needs confirmation:** Start the check at 09:00, off the update-row grid.
- **34 D-14, locked, jev overridden, needs confirmation:** Keep the notified set in `update-check.json` beside `schedules.json`; include it in uninstall state artifacts.
- **34 D-22, locked:** Preserve assertions about existing rows while extending closed-table assertions for the eighth row.
- **Orchestrator decision 1, provisional, needs confirmation:** Use table `max-height: 9` for the header and eight rows; the pin edits below preserve the assertions’ purposes.

## Pin edits

- **Enumerate:** `test_the_table_is_closed_and_ordered` adds the new ID, label and target; `test_cells_from_state_and_log` adds its `never` result.
- **Enumerate/layout:** `test_encoding_and_width` adjusts table and detail heights while retaining the no-scroll assertion. `test_schedules_chrome_at_80x20` adjusts their row ranges. The cut-detail ellipsis test reads the outer width so the padding-column ellipsis remains covered.
- **Enumerate/lifecycle:** `test_first_run_turns_on_and_records` extends records, enabled rows and reconcile text. `test_concurrent_reconciles_write_one_unit_set` extends enabled IDs, unit basenames and decisions. `ALL_IDS`, the two all-off loops and the two changed-file sweep result tuples include the new row.
- **Enumerate/handover:** `TURNED_ON` includes the new row; `_on_lab` includes it in the enabled tuple and sweep IDs.
- **Isolate:** The lifecycle tests `test_mid_pass_decision_is_kept`, `test_moved_checkout_refreshes_units_in_place`, `test_old_tmp_units_are_adopted_on_reconcile`, `test_macos_adoption_keeps_the_daily_time` and `test_failed_default_records_nothing` decide the new row off to preserve their old-row assertions. `test_an_on_daemon_stays_on_across_the_upgrade` does the same.
- **Cover:** The damaged-state sweep basename list includes the new timer, and `plant_logs` plants the notified-set artifact so uninstall tests cover its removal.

## Deviations and risks

- No plan-named tests were identified as omitted. Task 1’s original RED/GREEN evidence was unavailable; its commit and the final green suite are the available evidence.
- The Task 2 cadence test uses the same pilot highlight path directly rather than the `row_details` helper.
- No real timer, notification, container or macOS host check was run. The intermediate branch remains **non-deployable** until plan 34-05 adds runner support; the current check-row descriptive text is deferred to plan 34-06.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commits `ad7becfd` (Task 1: the daily `check-updates` row, runner arguments, notified-set artifact, uninstall handling, eight-row layout and the listed test edits) and `ff843b32` (Task 2: the Schedules view reads `Schedule.daily`), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists. The executor could not reproduce its RED and pre-pin baseline output (the earlier part's tails were not carried); the exact 29-failure baseline is therefore NOT independently confirmed by this run.
- `make test` on the final tree, default TMPDIR: 9155 passed, 6 skipped, coverage 96.37%.
- The branch between this plan and plan 34-05 is non-deployable by design (the row's job is unknown to the runner until then).

Provisional decisions carried to the verification report (needs owner confirmation): D-02 to D-07 (the row, `Schedule.daily`, on by default, 09:00); D-22 as amended by orchestrator decision 1 (table height 9 and the listed test edits); the narrowed no-credentials guarantee (the GitHub token variables only; proxy values as for every row); the notified-set file removed at uninstall only (an unexpected directory left untouched and reported); the owned-TMPDIR ruling (doctor test path length).

orchestrator-verification: none required

orchestrator-verification: none required
