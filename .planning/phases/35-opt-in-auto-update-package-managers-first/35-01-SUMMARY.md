# Phase 35 Plan 01 Summary

- **Task 1 — `8b1871a6`:** Added the opt-in `update-all` schedule, runner and installer dispatch, lock verification, summary formatting, and hermetic tracer.
- **Task 2 — `0a08ef4d`:** Added the Schedules screen target and detail text, daily time-editor coverage, and the ten-row table layout. Re-flowed the update-check detail to preserve visibility.

## Verification

- Task 1 RED and GREEN output was not available to this split executor; the commit and tests exist, but their original output cannot be reconstructed.
- Task 2 RED: the target cell returned `uv` instead of `all tools`; both on/off detail cases displayed cache-prune text. The daily editor test passed before the screen change.
- Task 2 baseline before pin edits: the five expected failures appeared—`test_cells_from_state_and_log`, `test_encoding_and_width`, `test_schedules_chrome_at_80x20`, and the macOS/no-status and Fedora/status check-detail visibility cases.
- Task 2 GREEN: the prescribed three-file pytest command reached **100%**, exit 0. The broader targeted run including importing test files also reached **100%**, exit 0.
- The first commit hook reported one overlong test line and formatting drift. Both were corrected; `make lint`, `make format-check`, and the subsequent commit hook passed.
- `make validate` tail: all six gates **Passed**.
- `make test` tail: **9438 passed, 6 skipped**; total coverage **96.41%**, exceeding the 90% requirement.

## Decisions

- **35 D-01 (locked):** `Schedule.default_on` defaults to true; `update-all` sets it false. `_row_action` remains the seeding rule; state schemas are unchanged.
- **35 D-02 (locked):** `JobKind.UPDATE_ALL` has no target and follows `check-updates`; `UPDATE_SCHEDULE_IDS` remains unchanged and `RUN_SCHEDULE_IDS` includes the new row.
- **35 D-03 (own reasoning, needs confirmation):** Run daily at 03:00, off the update grid and before the 09:00 check. **D-04 (locked):** Reuse the existing view mechanism, branching only for target and what-text.
- **35 D-10 and D-11:** Reuse `_update` in readonly mode with a longer bound. **D-11 is own reasoning and needs confirmation**; per-command bounds belong to plan 35-05. **D-12 and D-13:** `update-all.log` and `updated-today.json` are swept artifacts.
- **35 D-15, D-16, D-19 and D-21:** Use the specified summary shapes; pin the already-closed child stdin with a test; pass `DBUS_SESSION_BUS_ADDRESS` per job via `extra_env`.
- **Orchestrator decision 7 (needs confirmation):** The ninth row requires table height ten, the listed layout pins, and re-flowed check-row text.
- **Assumption delta (advisory):** `default_on` is the sole per-row seeding anchor read by `_row_action`.
- **Reviews (all provisional, needs confirmation):** M5 treats `skipped: busy` as a missed execution; M6 preserves user decisions and times; M7 uses `plain_line`; M8 says off by default; C1/I2/L1 verify the parent PID, holder line and kernel lock for update-all; I1 caps the first failed ID at 40; J1, K1 and L2 retain their planned safeguards and short wait seam.

## Pin edits

- `tests/test_schedules.py`: added the new ID, label and target to the ordered table assertion; renamed the daily-row test and added the third daily row.
- `tests/test_cli.py`: added `update-all` to the accepted schedule-ID tuple.
- `tests/test_update_check_contract.py`: included `UPDATE_ALL` in the schedule-kind choices assertion.
- `tests/test_schedules_view.py`: added the ninth `never` last-run cell; changed table/detail heights from 9/3 to 10/2 while retaining the no-scroll assertion.
- `tests/test_layout_80x20.py`: extended table rows through 13 and moved detail rows to 14–17.
- Task 1’s recorded baseline output was unavailable; the plan’s measured baseline named the four Task 1 tests above. Task 2’s independently observed baseline matched its five planned failures.

## Deviations and limits

- No named Task 2 test was omitted. Task 1’s named tests are present, but its original RED/GREEN output was not supplied to this executor.
- Targeted pytest used the default `TMPDIR` per the binding run note; each separately created run directory was removed by its exit trap. Final gates also used the default `TMPDIR`.
- No live timer, real update, notification, or container was run. Plans 01–04 remain non-deployable intermediate work: the opt-in job currently reports an empty update plan.
- The advisory lock retains the documented same-user trust-boundary limitation.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: the first run of Task 1 stopped after about 90 seconds with a partial RED file and an unjustified BLOCKED claim; the retry (with a retry notice) completed both tasks: commits 8b1871a6 (Task 1) and 0a08ef4d (Task 2).
- Plan verifies run by the orchestrator with an owned TMPDIR: both <automated> pytest commands passed (all non-make verifies passed).
- Named tests: 46 names in the tasks; every one is defined or is a module name; the two exceptions are the renamed old test `test_exactly_two_rows_are_daily` (plan-listed rename) and `test_update_all_summary` (the plan allows the summary test in tests/test_update_all_row.py, where `test_the_summary_line_shapes` exists).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9438 passed, 6 skipped, coverage 96.41%.
- Python 3.15 targeted run (`uv run --python 3.15 --isolated pytest` on the eight changed or new test files): all passed.
- Provisional decisions (need owner confirmation): D-03 (03:00 daily time), D-11 (3 h job bound), orchestrator decision 7 (table height 10, pin edits, check-row re-flow), review rounds 1 to 3 decisions of this plan (skipped: busy as a missed execution, plain_line normalizer, kernel-lock proof of the parent handoff with its same-user advisory residual, first-failed id cap of 40, composed Policies rows test).
- Scratch directory of the verification run removed.

orchestrator-verification: none required
