---
phase: 20-install-plan-with-dispositions
plan: "10"
subsystem: tui-install-execution
tags: [execute-screen, plan, outcomes, exit-code, retained-selection, tdd]
requires:
  - 20-03 (build_plan, PlanRow, Disposition)
  - 20-07 (execute_plan, RunContext, RowOutcome, updates through the plan)
  - 20-08 (RECONFIGURE steps, set_tool on the streaming runner)
  - 20-09 (plan renderers: plan_row_text, outcome_row_text, render_run_summary)
  - 20-17 (ExecuteInputs with version_refresh required, terminal_sync wired)
provides:
  - plan-driven ExecuteScreen (OptionList #plan-rows, RowStarted/RowFinished, InstallRunFinished(outcomes, ...))
  - UnifiedApp.outcomes / run_errors fold; retained selection; ran_anything terminal-sync gate
  - setup._session_exit_code over outcomes
affects:
  - 20-11 (headless route still uses Summary; untouched here)
  - 20-12 (_await_state attaches to action_start; _wait_token is first read there)
  - 20-13 (r key on the review)
  - 20-14 (deletes Summary, fold_run, run_installs, reapply_post_install)
status: complete
key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - installer/wizard_app.py
    - installer/session.py
    - setup.py
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
    - tests/test_setup.py
    - tests/test_catalog_tui.py
key-decisions:
  - "The screen dismisses with list[RowOutcome] (None before a run); the app keeps one latest outcome per tool id, so cancel-then-retry never leaks a stale not_attempted."
  - "run_error carries only a crash that escapes execute_plan; PATH wiring and verify failures are kept beside it as path_error and verify_error. The app appends all three to run_errors (L-20-08)."
  - "The worker's row callback calls runner.set_tool before posting RowStarted; it is the only set_tool site and precedes every command a row runs. attributed_install is deleted."
  - "session._with_force now calls the install seam without a repair keyword unless the row is a repair or reinstall, and RunContext.install is a SensitiveInstall. RepairSensitiveInstall is deleted (no remaining user)."
  - "exit_code takes an Iterable, so setup passes app.outcomes.values() directly."
  - "Finished status: Failed. when exit 1 or any run error; Nothing ran. when no row ran; Done. otherwise. Still selected counts retained rows that the user picked (dragged-in dependencies excluded, L-20-07)."
  - "Post-install reapply of an explicitly re-selected current tool is gone: the plan skips the row as already current and RECONFIGURE runs typed steps (D-06)."
requirements-completed: [PLAN-01, PLAN-04, PLAN-05]
duration: "about 4h (single executor session)"
completed: 2026-10-17
commits: 1
plan_head_before: 0ced12411324cfdf64a1d87163edbf3a5d8ef491
plan_head_after: 09918bf48df9216a3901fd1cf7b8d6a34f2d30a6
---

# Phase 20 Plan 10: The TUI reviews, runs, retains and exits through the plan

**The execute screen reviews, runs and summarizes one `build_plan`/`execute_plan` plan; the app keeps the retained selection and the exit code reads the outcomes, with the old classification, progress-list, update-loop and Summary copies deleted.**

## What was built

Tasks 1 and 2 landed as one commit, `09918bf`, as the plan requires: Task 1 alone leaves `wizard_app.on_install_run_finished` reading the reshaped `InstallRunFinished`, and a red tree is never committed.

### Task 1: the screen reviews, runs and finishes through the plan (commit 09918bf)

- `installer/execute_screen.py` (1166 to 835 lines): `ExecuteScreen` builds rows with `build_plan` on mount and on every Enter (`_replan`), paints one `OptionList#plan-rows` with `plan_row_text(..., hint=True)`, and shows `plan_head` in `#execute-head`. Enter with a `checking…` row shows the Waiting status and starts nothing (the wait worker is plan 20-12).
- The worker calls `execute_plan(rows, RunContext(...))` once with the streaming runner, `on_row_started` calling `runner.set_tool` then posting `RowStarted` (and `-- updating --` for UPDATE rows), and `on_outcome` posting `RowFinished`. PATH wiring and verify run only when `ran_anything`.
- Outer `except Exception` completes the outcome list with `RowOutcome(row, "not_attempted", detail=run_error)` for every row without an outcome, so no row is dropped (D-10, SPEC R5). The `# noqa: BLE001` pre-existed and is the only suppression.
- Finished: head `Summary — {summary_counts}` (green exit 0, red otherwise), rows show their outcome text, the log gets `render_run_summary` and the install report renderers, status `{Done.|Failed.|Nothing ran.} {Still selected: N. }enter or esc returns to the catalog.`, keys `enter / esc return to catalog`. Dismiss value is the outcome list.
- Keys lines per UI-SPEC: idle `enter start · r reinstall · up/down move · esc cancel` (r omitted when no row can reinstall), empty `esc close`, running `c stop after this tool · ctrl+c aborts and can leave a tool half-installed`, waiting `waiting for the state check · esc cancels the wait`, finished `enter / esc return to catalog`.
- Deleted from the screen: `attributed_install`, `_with_repair`, `_partial_run`, `InstallToolFinished`, `UpdateToolFinished`, `_classify_selection`, `_update_targets`, `_run_updates`, `_render_updates`, `_updated_line`, `_preflight_prompt`, `_refresh_progress`, `_PROGRESS_GLYPH`, `ProgressState`, `#execute-progress`, `summary`/`not_attempted` attributes.

### Task 2: the app and the exit code read the outcomes (commit 09918bf)

- `installer/wizard_app.py`: `self.outcomes: dict[str, RowOutcome] | None` (latest outcome per tool id wins) and `self.run_errors: list[str]`. `on_install_run_finished` records each outcome, appends run/path/verify errors, and keeps the invalidate call. `on_tool_updated` folds a failed direct `u` as `RowOutcome(PlanRow(id, UPDATE, ""), "failed")`. `_install_closed(result)` does `self._staged.intersection_update(retained(result))` (in place; `None` leaves the set alone) and runs the terminal sync only on `ran_anything(result)`. `install_summary`, `_merge_summary`, `_install_state_changed` and the `Summary`/`fold_run` imports are gone.
- `setup.py`: `_run_interactive_wizard` reads `app.outcomes is None` for the Aborted branch; `_session_exit_code` is 1 for `run_in_flight or run_errors`, `exit_code(app.outcomes.values())` when outcomes exist, else 0. The headless route is untouched (20-11).
- `installer/session.py`: `_with_force` omits the `repair` keyword for non-forced rows; `RunContext.install` is `SensitiveInstall`; `RepairSensitiveInstall` is deleted; `exit_code` accepts an `Iterable`. See Deviations.

## TDD evidence

RED for Task 1 (ten new pilots in `tests/test_execute_screen.py`, run before the screen was rewritten):

```
FAILED tests/test_execute_screen.py::test_review_lists_every_row_with_its_disposition
FAILED tests/test_execute_screen.py::test_enter_runs_the_plan_and_finishes_with_the_summary_head
FAILED tests/test_execute_screen.py::test_nothing_selected_shows_the_empty_state_and_enter_does_nothing
FAILED tests/test_execute_screen.py::test_only_skipped_rows_finish_immediately_without_the_engine_or_path_wiring
FAILED tests/test_execute_screen.py::test_enter_rebuilds_the_plan_from_the_latest_publication
FAILED tests/test_execute_screen.py::test_checking_rows_render_dim_and_enter_waits
FAILED tests/test_execute_screen.py::test_failed_row_is_red_still_selected_and_the_status_reads_failed
FAILED tests/test_execute_screen.py::test_a_worker_crash_marks_the_rest_not_attempted_and_keeps_them_selected
FAILED tests/test_execute_screen.py::test_a_crash_outside_execute_plan_fills_every_row_as_not_attempted
9 failed, 1 passed (test_escape_before_start_dismisses_with_none: the old screen already dismissed with None on Esc, so it passes before and after)
```

The first RED attempt was an import error of my own (`OptionList` imported from `textual.widgets.option_list`); fixed to `textual.widgets` before the run above. Only the FAILED list was captured, not the full tracebacks.

Task 2 pins (`test_install_closed_keeps_exactly_the_retained_rows_selected`, `test_install_closed_never_adds_a_dragged_in_dependency`, `test_escape_before_start_leaves_the_selection_untouched`, `test_terminal_sync_runs_only_when_a_row_ran`, `test_cancel_then_retry_leaves_the_latest_outcome_and_exits_clean`, and the parametrized `test_session_exit_code_is_one_iff_an_outcome_failed_or_a_run_error_exists`) were written after the implementation, not RED first. Their failing precursors were observed: before porting, `tests/test_wizard_app.py` had 17 failing tests, `tests/test_setup.py` 61, `tests/test_catalog_tui.py` 1, and `tests/test_execute_screen.py` could not collect. Each port was driven by one of those failures. This is a deviation from the plan's RED-first rule for Task 2.

## Verification

- `make validate`: exit 0 on the committed tree (ruff, format, pyright strict: 0 errors, bandit, vulture, shellcheck, pre-commit hooks).
- `make test`: exit 0, 4835 passed, 4 skipped, coverage 96.03% (floor 90%).
- Affected modules green: `tests/test_execute_screen.py` (79), `tests/test_wizard_app.py` (306), `tests/test_setup.py` (129), `tests/test_catalog_tui.py`, `tests/test_session.py`, `tests/test_render.py`.
- Grep gates: `build_plan(` 1, `execute_plan(` 1, `set_tool(` 1, `OptionList(id="plan-rows"` 1, `"not_attempted", detail=run_error` 1, `intersection_update(retained(` 1, `ran_anything(` 1, `exit_code(` 1 in setup. No forbidden names in `installer/execute_screen.py`, no `install_summary` in `tests/test_wizard_app.py`, no `summarize` in `tests/test_execute_screen.py`. `git grep attributed_install` leaves only the Phase 13 doctrine entry in `tests/test_docs.py` (pinned to `.claude/architecture.md`, rewritten by 20-16).
- Sizes (HEAD~1 to 09918bf): `installer/execute_screen.py` 1166 to 835; `tests/test_execute_screen.py` 4753 to 3235; `tests/test_wizard_app.py` 8015 to 8133; `tests/test_setup.py` 3932 to 3968. `git diff --stat` for the commit: 8 files, 1051 insertions, 2825 deletions.

## Test-count floors and deletions (REUSE adjustments and by-decision removals)

Floors: the plan's `test_execute_screen.py ≥ 100` check is no longer met. The file has 79 test functions (116 at HEAD~1, minus 47 deleted, plus 10 new). The 47 deletions are listed below; the REUSE rule says to adjust the floor to the exact number, so the floor is now 79. `test_wizard_app.py` (306, floor 295) and `test_setup.py` (129, floor 120) meet their floors.

REUSE adjustments applied:
- Finding 10-1 (screen state): `_outcomes` was not added (the app holds `outcomes`), `_wait_token` was not added (20-12 adds it with `_waiting`), and `_run_error` is not stored (only the message carries it). `_start_requested` and `_reinstall` are kept, as the finding says.

Deleted by decision (behaviour gone; reason in brackets). 47 tests:
- Progress lists (`#execute-progress`, the three pending/done/skipped lists): `test_progress_lists_every_resolved_tool_as_pending_before_start`, `test_progress_pending_count_falls_as_each_tool_finishes`, `test_queued_outdated_update_progress_row_leaves_pending_when_update_returns`.
- Update-loop tail sweep (`_to_update`): `test_cancel_mid_update_tail_sweeps_unreached_outdated_row_to_skipped`, `test_latch_refused_outdated_update_row_is_swept_to_skipped`, `test_error_before_outdated_update_tail_sweeps_pending_update_rows`.
- Updates section and update lines (`_render_updates`, `_updated_line`, `_NO_MANAGER_CLAIMED`): `test_update_section_is_silent_when_no_outdated_updates_were_queued`, `test_successful_outdated_update_is_named_in_the_post_run_log`, `test_successful_outdated_update_without_a_new_version_still_reports`, `test_successful_outdated_update_line_carries_outcome_extras`, `test_blocked_update_reason_reaches_the_post_run_log`, `test_blocked_update_reason_is_absent_from_the_log_until_the_run_finishes`, `test_blocked_update_without_detail_falls_back_to_no_manager_claimed`, `test_blocked_update_latch_refusal_reuses_the_in_flight_sentence`.
- Update-loop internals (`_run_updates`, refresh and ownership reads inside the loop): `test_classify_reads_the_state`, `test_run_updates_reads_ownership_and_version_from_state`, `test_refresh_oserror_after_outdated_update_still_produces_the_report`, `test_refresh_failure_on_missing_ownership_reports_error_not_a_clean_run`, `test_blocked_update_error_from_run_live_is_reported`, `test_blocked_update_does_not_reprobe_the_version_cache`, `test_a_completed_update_stays_done_when_the_version_refresh_crashes`, `test_missing_ownership_snapshot_refreshes_then_dispatches_outdated_update`, `test_missing_version_status_still_dispatches_an_outdated_update`, `test_update_dispatch_opens_no_confirm_prompt_of_its_own` (pinned `_run_updates` source), `test_failed_update_status_marks_the_run_failed`, `test_raised_update_error_marks_the_run_failed`, `test_completed_updates_survive_a_later_crash`, `test_cancel_mid_updates_keeps_completed_updates_and_reports_the_rest_not_attempted`, `test_stale_update_terminal_message_for_another_tool_does_not_clear_in_flight` (UpdateToolFinished deleted).
- Latch skips (a blocked row in `execute_plan`): `test_in_flight_latch_skip_is_a_failure_on_neither_signal`, `test_in_flight_latch_skips_outdated_update_and_keeps_the_holder`.
- In-flight marker for UPDATE rows: `test_silent_update_establishes_in_flight_tool_via_marker` (see gaps).
- Preflight copy (`_preflight_prompt`, the plan head replaces it): `test_preflight_head_names_install_and_outdated_update_counts_before_any_keypress`, `test_update_only_outdated_preflight_does_not_read_as_zero_work`, `test_current_only_selection_says_already_current_not_install_zero`, `test_mixed_install_and_current_names_already_current`, `test_broken_tool_preflight_counts_as_install`, `test_outdated_selected_tool_stays_an_update_target` (`_to_update` classification).
- Post-install reapply (D-06; RECONFIGURE runs typed steps; `reapply_post_install` removed in 20-14): `test_explicit_current_selection_reapplies_post_install_once`, `test_explicit_outdated_selection_reapplies_post_install_once`, `test_cancel_stops_reapply_before_any_dispatch`, `test_installed_drag_in_is_not_reapplied`, `test_fresh_install_is_not_reapplied`.
- Receipt drift as a refusal (build_plan puts drift on a REPAIR row now): `test_drifted_receipt_update_is_refused_per_tool`, `test_drifted_tool_is_refused_before_the_run_starts`, `test_broken_and_outdated_repairs_instead_of_updating` (repair-vs-update is build_plan's; see gaps).
- Superseded by the new pilot `test_only_skipped_rows_finish_immediately_without_the_engine_or_path_wiring`: `test_all_skipped_run_is_done_and_green`.

Renamed or re-expressed (kept behaviour, new vocabulary): `test_a_broken_batch_still_finishes_with_an_empty_summary` to `test_a_crashing_install_finishes_the_run_and_names_the_rest_not_attempted`; `test_execute_keys_names_escape_c_and_ctrl_c_with_distinct_meanings` to `test_execute_keys_name_the_idle_actions_before_a_run`; `test_retrying_a_mismatch_installs_twice_and_summarizes_installed` to `test_retrying_a_mismatch_installs_twice_and_finishes_installed`. The `InstallToolFinished` stale-message pins now send `RowFinished`. `test_two_runs_accumulate_failures_into_install_summary` is now `test_two_runs_keep_the_latest_outcome_per_tool`.

Helpers removed as unused: `_progress_text`, `_assert_head_hint`, `_BlockedUpdateService`, `_RaisingUpdateService`, `_SuccessUpdateService`, `_VersionedRefreshService`, `_StateOnlyRefreshService`, `_counting_reapply`, `_capture_run_finished`, `_raw_yq`.

## Deviations from the plan

1. **Commit shape.** The orchestrator asked for one commit per task; the plan requires Tasks 1 and 2 in one commit (Task 1 alone leaves `wizard_app` red). I followed the plan: one commit, `09918bf`.
2. **`installer/session.py` is outside `files_modified`.** `_with_force` passed `repair=False` to every install, so a plain install seam (every test fake, and any seam that does not know repair) raised `TypeError`. It now omits the keyword for non-forced rows, which is what the plan's `test_non_broken_install_omits_the_repair_kwarg` requires. `RepairSensitiveInstall` is deleted (no user left), `RunContext.install` is `SensitiveInstall`, and `exit_code` takes `Iterable[RowOutcome]` so setup can pass `.values()`. All of `tests/test_session.py` still passes.
3. **`setup.py` import.** Added `from installer.session import exit_code`.
4. **`run_error` scope.** The plan's `InstallRunFinished.run_error` is used for the crash that escapes `execute_plan`. PATH wiring and verify failures go in `path_error`/`verify_error`. The app appends all three to `run_errors`, and the screen shows all three as Failed. This satisfies L-20-08 with a cleaner log.
5. **`tests/test_catalog_tui.py` is outside `files_modified`.** One test asserted `install_summary.update_failed`; it now asserts the outcome row (`outcomes["rg"].result == "failed"`).
6. **Dropped text.** The Updates section lines (`updated rg now X`, `cannot update rg: …`) are gone with the update-loop copy the plan deletes. An update's result is its row (`✓ rg  updated`, `↑ rg  blocked — reason`, `✖ rg  failed — detail`).
7. **Post-install reapply.** A re-selected current tool with post-install steps is now skipped as already current (D-06). This is behaviour the plan does not spell out; 20-14 deletes the engine function it used.
8. **Status word.** `Nothing ran.` is used when no row ran and nothing failed, which is the plan's three-way copy; the skipped-only pilot pins it.
9. **Still selected.** Counted as `retained ∩ selected ids`, so a dragged-in dependency never counts (L-20-07).
10. **Plan-head subtitle.** The screen uses the plan head from 20-09 (`plan_head`), so the review shows `Indented rows are needed by the tool above and run first.` when a dependency is dragged in.
11. **TDD order.** See the TDD evidence section: Task 2's pins were written after the code.
12. **Commit ledger.** The per-plan ledger file (`gsd-plan-head-before-20-10`) was not persisted before the first commit. `commits`, `plan_head_before` and `plan_head_after` are measured from git: the base is the parent of `09918bf` (`0ced124`), giving one commit.

## Gaps the orchestrator should know about

- **Running keys copy is not pinned by a pilot.** The idle keys are pinned (`test_execute_keys_name_the_idle_actions_before_a_run`); the running and waiting strings are constants with no test that reads them after a run starts. Plan 20-12 will exercise the waiting string.
- **UPDATE in-flight marker has no pilot.** `test_silent_update_establishes_in_flight_tool_via_marker` was deleted with the update loop. The row callback still posts `-- updating --` for UPDATE rows; no test now proves the silence indicator names an updating tool.
- **Build-plan semantics of repair vs update.** `test_broken_and_outdated_repairs_instead_of_updating` was deleted. Its behaviour should be covered by `tests/test_session.py` or `tests/test_build_plan`-level tests; I did not verify that.
- **No plan-level pin for `_start_requested`.** It is set in the WAIT branch of `action_start` and read by 20-12; vulture accepts it today.

## Self-Check

- [x] Commit `09918bf` exists on `worktree-agent-a3f295f12f476044a` (checked with `git log`).
- [x] `make validate` exit 0 and `make test` exit 0 on that tree.
- [x] `git status --short` clean before this summary commit; `.planning/config.json` never staged.
- [x] No `git checkout`, `merge`, `rebase`, `push`, or branch creation performed.

## Gap closure (test floor)

This addendum closes the acceptance gap without repeating plan 20-10’s implementation. Commit `c5e51a4` ports the surviving update-loop pins to the plan rows, `execute_plan`, row messages, and finished outcomes. No installer source changed. `tests/test_execute_screen.py` now has 102 test functions and 103 collected pytest cases, up from 79 functions after 20-10; both counts exceed the requested floor of 100.

### Behavior re-expressed through the plan model

The prior 47-name deletion ledger above remains the history of removed function names. The following live behaviors now have replacement assertions under the new seams:

- Failed and raised updates: `test_failed_update_status_marks_the_run_failed`, `test_raised_update_error_marks_the_run_failed`, and `test_blocked_update_error_from_run_live_is_reported` are covered by `test_failed_update_row_marks_the_run_failed` and `test_raised_update_row_is_crashed_and_marks_the_run_failed`. `test_failed_update_does_not_stop_a_later_install_row` also pins that a returned failure does not halt a later plan row.
- Completed outcomes, crashes, and cancellation: `test_completed_updates_survive_a_later_crash` maps to `test_completed_update_survives_a_run_level_crash`; `test_a_completed_update_stays_done_when_the_version_refresh_crashes` and `test_refresh_oserror_after_outdated_update_still_produces_the_report` map to `test_update_outcome_survives_state_invalidation_without_followup_refresh`; `test_cancel_mid_updates_keeps_completed_updates_and_reports_the_rest_not_attempted` maps to `test_cancel_mid_update_keeps_completed_rows_and_marks_the_rest_not_attempted`; and `test_error_before_outdated_update_tail_sweeps_pending_update_rows` maps to `test_install_crash_marks_a_later_update_not_attempted`. The plan reports the unreached row as `not_attempted`, not the old update-loop `skipped` result.
- Latch and blocked outcomes: `test_in_flight_latch_skip_is_a_failure_on_neither_signal` maps to `test_in_flight_update_latch_is_blocked_not_failed`; `test_in_flight_latch_skips_outdated_update_and_keeps_the_holder` and `test_blocked_update_latch_refusal_reuses_the_in_flight_sentence` map to `test_latch_refusal_keeps_the_update_holder_and_reports_a_blocked_row`.
- Blocked details: `test_blocked_update_reason_reaches_the_post_run_log`, `test_blocked_update_reason_is_absent_from_the_log_until_the_run_finishes`, and `test_blocked_update_without_detail_falls_back_to_no_manager_claimed` are covered by `test_blocked_update_reason_reaches_finished_row_and_log`, `test_blocked_update_reason_appears_only_when_the_row_finishes`, and `test_blocked_update_without_detail_uses_the_plan_reason`. The old hard-coded “no manager claimed” fallback is gone; a detail-less outcome now uses the reviewed plan-row reason.
- State and dispatch: `test_blocked_update_does_not_reprobe_the_version_cache` maps to `test_blocked_update_does_not_trigger_a_version_refresh`; `test_missing_version_status_still_dispatches_an_outdated_update` maps to `test_outdated_row_without_version_status_still_dispatches_update`; and `test_missing_ownership_snapshot_refreshes_then_dispatches_outdated_update` plus `test_run_updates_reads_ownership_and_version_from_state` map to `test_update_target_uses_the_plan_captured_owner`. The latter pins the new contract: the plan carries ownership to `UpdateTarget` even without cached method/package/version fields; no second ownership snapshot lookup is needed. A fully unknown owner still follows the plan’s fail-closed refusal rather than dispatching an update.
- Successful updates and interaction: `test_successful_outdated_update_is_named_in_the_post_run_log` and `test_successful_outdated_update_without_a_new_version_still_reports` map to `test_successful_update_is_named_in_summary_and_outcome_row` and `test_successful_update_without_a_new_version_still_reports_updated`; `test_update_dispatch_opens_no_confirm_prompt_of_its_own` maps to `test_update_dispatch_does_not_open_a_confirmation_prompt`.
- Progress and classification seams: `test_silent_update_establishes_in_flight_tool_via_marker` maps to `test_update_marker_establishes_the_silence_indicator`; `test_stale_update_terminal_message_for_another_tool_does_not_clear_in_flight` maps to `test_stale_finished_update_row_does_not_clear_the_next_rows_indicator`; and `test_outdated_selected_tool_stays_an_update_target` is pinned through the UPDATE disposition in `test_outdated_row_without_version_status_still_dispatches_update`.
- Review and receipt drift: the old preflight-count pins are represented by `test_plan_head_counts_install_update_and_skip_rows`, which checks install, update, and skipped rows in one plan. `test_broken_tool_preflight_counts_as_install`, `test_drifted_receipt_update_is_refused_per_tool`, `test_drifted_tool_is_refused_before_the_run_starts`, and `test_broken_and_outdated_repairs_instead_of_updating` are replaced by `test_receipt_drift_is_reviewed_as_repair_and_not_update` (L-20-01: receipt drift is REPAIR). `test_update_row_transitions_from_review_to_running_to_finished` pins the plan row’s live lifecycle.

### Deletions that remain justified

The exact deleted function names above remain removed; only assertions for surviving behavior were ported. The remaining removals follow the plan decisions:

- The three pending/done/skipped progress-list tests (`test_progress_lists_every_resolved_tool_as_pending_before_start`, `test_progress_pending_count_falls_as_each_tool_finishes`, and `test_queued_outdated_update_progress_row_leaves_pending_when_update_returns`) pin `#execute-progress`, which the plan replaces with one plan-row list updated by `RowStarted` and `RowFinished`.
- The separate Updates section (`test_update_section_is_silent_when_no_outdated_updates_were_queued`) and its extra success-line fields (`test_successful_outdated_update_line_carries_outcome_extras`) are gone with `_render_updates`/`_updated_line`; the finished renderer emits one outcome row per plan row instead.
- `_classify_selection` and update-loop-only refresh mechanics are not screen behaviors anymore: `test_classify_reads_the_state`, `test_refresh_oserror_after_outdated_update_still_produces_the_report`, and `test_refresh_failure_on_missing_ownership_reports_error_not_a_clean_run` are not restored as screen-loop tests. The plan is authoritative; no post-plan ownership/version refresh is attempted. Missing version and captured ownership dispatch are pinned above, while unknown ownership remains fail-closed.
- The `_preflight_prompt` copy tests remain deleted because `plan_head` and `plan_row_text` replace that copy. Their meaningful cases are represented by the existing current/skipped and outdated-row pilots plus `test_plan_head_counts_install_update_and_skip_rows`; exact “install zero”/“already current” wording belongs to the plan renderer, not a second preflight path.
- The five post-install reapply tests remain deleted under D-06 and 20-14: a current tool is skipped, and RECONFIGURE performs only its typed steps; `reapply_post_install` no longer exists.
- `test_all_skipped_run_is_done_and_green` is superseded by `test_only_skipped_rows_finish_immediately_without_the_engine_or_path_wiring`, which asserts the current plan’s summary and no-mutation behavior.

### Verification and file sizes

This was a test-port task, so no production RED run or regression fix was needed. Initial pilot attempts exposed test-only assumptions about querying a screen after its Textual context closed and about blocked rows staying selected; the tests were adjusted to snapshot the rendered log while mounted and to assert the plan’s retained-selection status. The final focused module run and collection check passed.

- `make validate`: passed (ruff, formatting, pyright, bandit, vulture, shellcheck).
- `make test`: passed, 4,858 passed, 4 skipped, 96.04% coverage.
- `tests/test_execute_screen.py`: 102 test functions; 103 collected cases.
- `wc -l`: `tests/test_execute_screen.py` 3,882; `tests/test_wizard_app.py` 8,133; `tests/test_setup.py` 3,968.
- `git diff --stat c5e51a4^ c5e51a4 -- tests/test_execute_screen.py tests/test_wizard_app.py tests/test_setup.py`: `tests/test_execute_screen.py | 647 +++++++++++++++++++++++++++++++++++++++++++`; the other two files were unchanged.
- The pre-existing `.planning/config.json` modification was left untouched and remains unstaged.
- Commit: `c5e51a4 test(20-10): port the plan-model behaviour pins deleted with the update loop`.
