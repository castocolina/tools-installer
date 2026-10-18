---
phase: 20-install-plan-with-dispositions
reviewed: 2026-10-18T16:51:05Z
depth: deep
diff_base: f9d98fe
reviewed_head: 3c74d96
files_reviewed: 33
files_reviewed_list:
  - installer/app.py
  - installer/deps.py
  - installer/engine.py
  - installer/execute_screen.py
  - installer/model.py
  - installer/post_install.py
  - installer/receipts.py
  - installer/registry.toml
  - installer/render.py
  - installer/selection.py
  - installer/session.py
  - installer/version_status.py
  - installer/wizard_app.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/state_doubles.py
  - tests/test_app.py
  - tests/test_catalog_tui.py
  - tests/test_container_e2e_receipts.py
  - tests/test_deps.py
  - tests/test_docs.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_model.py
  - tests/test_plan.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_selection.py
  - tests/test_session.py
  - tests/test_setup.py
  - tests/test_shell_scripts_path.py
  - tests/test_version_status.py
  - tests/test_wizard_app.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 20: Code Review Report (round 2)

**Reviewed:** 2026-10-18T16:51:05Z
**Depth:** deep
**Files Reviewed:** 33 (`git diff f9d98fe 3c74d96 -- installer setup.py scripts tests`)
**Status:** issues_found

## Summary

Round 2 re-reviews the gap plans 20-20..20-29 (plus the two test-only commits
1f31b9e and 102bdf9) against the round-1 findings consolidated as J1..J12. I
read every source diff, traced the new code across modules (headless route ->
refresh service -> receipts; review wait -> state settle -> repaint; plan
builder -> propagation -> prune; engine refusal -> post-install -> session
result; e2e parser -> gate), checked the vocabulary against the amended
20-UI-SPEC.md, grepped the production tree for any remaining reference to the
symbols plans 20-28/20-29 deleted (none), and ran the phase test modules
(`test_plan test_session test_render test_app test_execute_screen
test_version_status test_engine test_deps test_model test_setup test_wizard_app
test_container_e2e_receipts test_selection test_registry`: all green, no cov).
Two probes ran from the scratchpad with a scratch `HOME`; nothing in the repo
was modified.

Every round-1 Critical and Warning is closed with a test that pins it. One new
Warning: the e2e gate still cannot see the headless route's new exit-1 cause
(PATH wiring / PATH audit failure) when the run also has explained dependency
failures, which the real catalog always has. One Info with a one-line fix: a
refused reinstall of a present tool (the new `refuses_existing` path) is
treated as unresolved, so a dependent would be reported `dependency failed`
even though the dependency is installed (not reachable with the shipped
registry, where nothing requires `oh-my-zsh`).

No test in scope touches the real `HOME` (the autouse scratch-HOME fixture and
`_REAL_HOME` fingerprint guard in `tests/conftest.py` still cover every new
test) and no test runs a host binary other than `bash` for the extracted e2e
functions, which is the pre-existing pattern of `test_container_e2e_receipts`.
No new suppression comment was added in production code (`ruff` selects no
`BLE` rule, so the two new `except Exception` arms need none).

## Closure table (round 1 -> round 2)

| Round-1 id | J | Status | Evidence (file:line) |
|---|---|---|---|
| CR-01 / E2E-01 / P-01 / OC-02 (headless and TUI skill packs never settle) | J1 | closed | `installer/app.py:118-121` runs `refresh` then `refresh_skills` in the one synchronous pass; `installer/execute_screen.py:542-557` joins both in the same `run_live`; pinned by `tests/test_app.py::test_headless_all_settles_skill_packs_before_planning` (real `offline_service` with a skill probe) and `tests/test_execute_screen.py::test_enter_settles_a_pack_selected_before_its_host_check` |
| CR-02 / OC-05 (e2e gate ignores not attempted, crashed, setup exit) | J2 | closed (see WR2-01 for the remaining exit-1 hole) | `scripts/container-e2e-verify.sh:426-434` `install_step_ok` gates `ACC_NOT_ATTEMPTED`, `ACC_CRASHED`, `ACC_SUMMARIES == ACC_RUNS` and the setup exit; used once in pass1 and twice in pass2 (`tests/test_container_e2e_receipts.py::test_every_install_step_uses_the_one_gate`, `::test_install_step_gate`) |
| WR-07 (GNU sed in the parser) | J2 | closed | `scripts/container-e2e-verify.sh:251` bash `=~` only; `::test_parse_summary_line_needs_no_external_tool` runs with `PATH=""` |
| IN-07 (folded dependency-failed rows) | J2 | closed | `scripts/container-e2e-verify.sh:384-399` joins 4+-space continuations; `::test_a_folded_dependency_failed_row_is_read_whole`, `::test_a_two_space_report_line_is_not_joined_to_a_row` |
| CR-03 (update extras dropped) | J3 | closed | `installer/render.py:257-277` `render_update_notes`, called from `render_run_report` (`:280-289`) on both routes (`installer/app.py:169`, `installer/execute_screen.py:886`); the deleted pin is ported as `tests/test_execute_screen.py::test_successful_outdated_update_line_carries_outcome_extras` and `tests/test_app.py::test_headless_report_carries_a_successful_updates_extras` |
| CR-04 (present-but-blocked dependency blocks dependents) | J4 | closed | `installer/session.py:765-777` propagates from `unsatisfied` (BLOCKED and not `_settled`) only; `tests/test_plan.py::test_a_present_dependency_blocked_for_its_own_reason_does_not_block_its_dependent` |
| WR-04 (dragged dependency of a blocked requester installed) | J4 | closed | `installer/session.py:778-795` reverse prune to `SKIP not needed while {requester} is blocked`; probe S1/S3 confirmed chains and sudo-blocked requesters; `::test_a_dragged_dependency_of_a_blocked_requester_is_skipped_not_installed`, `::test_a_dragged_chain_needed_only_by_a_blocked_tool_is_skipped`, `::test_a_dragged_dependency_still_needed_by_a_runnable_tool_keeps_its_disposition` |
| P-02 (method-less pending dependency makes dependent BLOCKED, not WAIT) | J4 | closed | `installer/session.py:710-711` `_blocked_row` returns WAIT for a pending state; `::test_a_pending_dependency_without_a_method_waits` |
| CR-05 (non-OSError refresh failure hangs the wait) | J5 | closed | `installer/execute_screen.py:544-557` try/except/finally always posts `StateSettled`; `::test_a_refresh_raising_value_error_settles_with_the_error_and_enter_retries` |
| WR-01 (late settle repaints a running/finished run) | J5 | closed | `installer/execute_screen.py:563-564` guard after the token check; `::test_a_late_settle_never_repaints_a_finished_run` |
| IN-05 (multi-line state-check error) | J5 | closed | `installer/execute_screen.py:567` first line before truncation; `::test_a_multi_line_state_check_error_shows_its_first_line_only` |
| WR-02 / P-03 / OC-08 (failure reasons lost) | J6 | closed | `installer/render.py:155-161` failed branch falls back to `outcome.detail`; `tests/test_render.py::test_failed_row_prefers_outcome_detail_when_install_errors_are_empty` |
| WR-05 / P-04 (second presence predicate headless) | J7 | closed | `setup.py:779-788` the one bound `_install` (`present=version_refresh.is_present`) returned by `_build_services`, passed at `setup.py:1513-1522`; `tests/test_setup.py::test_headless_main_passes_the_shared_install_to_run_wizard`, `::test_build_app_takes_its_services_from_build_services` asserts the TUI gets the same object |
| WR-06 / OC-03 (declined run already wrote receipts and cache) | J8 | closed (headless); TUI scoped by L-20-10 | `installer/app.py:118` `hold_writes` before the pass, `:149` `commit_writes` only after consent; `installer/version_status.py:957-984` hold/commit/queue; retirement deferred at `:1325-1333`, adoption via `receipts.adopt(write=False)` at `:1381-1393` and `receipts.commit_adoption` (`installer/receipts.py:336-349`) re-checks the fingerprint at commit; `tests/test_version_status.py::test_a_declined_headless_plan_retires_nothing_and_saves_no_cache`, `::test_a_declined_headless_plan_adopts_nothing`, `::test_a_consented_headless_plan_commits_the_adoption_before_it_runs`, `::test_held_cache_saves_wait_for_commit`; the TUI boundary (no hold) is recorded in `.claude/architecture.md` (diff +29..+33) and the hold docstring |
| IN-08 first half (two decline lines) | J10 | closed | `setup.py:1525-1526` returns without `Aborted.`; `tests/test_setup.py::test_a_declined_headless_run_prints_one_line` |
| IN-08 second half (drift note on a broken receipt) | J10 | closed | `installer/version_status.py:1685-1690` note only when `receipt is None`; `tests/test_version_status.py::test_a_broken_receipt_tool_carries_no_unproven_note` |
| OC-04 (headless PATH wiring / audit failures bypass the exit rule) | J9 | closed | `setup.py:1529-1550` both wrapped in `run_live`, exit 1 with the reason; `tests/test_setup.py::test_headless_post_run_failure_exits_1_with_the_reason` |
| OC-07 (stale run error after a clean retry) | J9 | closed | `installer/wizard_app.py:3004-3009` replaces `run_errors` when a run ran; `tests/test_wizard_app.py::test_a_run_that_rewires_path_replaces_an_earlier_run_error`, `::test_a_run_that_ran_nothing_keeps_an_earlier_run_error` |
| P-05 (successful `u` after a failed `u`) | J9 | closed | `installer/wizard_app.py:3027-3029` records `done`; `::test_a_successful_u_after_a_failed_u_clears_the_failure` |
| WR-03 (raising terminal_sync crashes the batch) | J9 | closed | `installer/session.py:368-371` step failure, not a crash; `tests/test_session.py::test_a_raising_terminal_sync_step_fails_its_row_and_the_batch_continues` |
| OC-06 (handoff-only manual counts as ran) | J9 | closed | `installer/session.py:215-239` `manual` counts only for a RECONFIGURE row with a command step; the only `_perform` handoff source is `host_setup_handoff` (`installer/executors.py:585`), which installs nothing, so no install-then-handoff path lost PATH wiring; `::test_a_manual_reconfigure_row_ran_only_when_it_had_a_command_step` |
| IN-04 (invalidate after a run where nothing ran) | J9 | closed | `installer/wizard_app.py:2997`; `::test_a_run_where_nothing_ran_does_not_invalidate` |
| WR-08 (skipped OK row shows the done check) | J10 | closed | `installer/render.py:135-136` unchanged rows keep the glyph in `dim`; 20-UI-SPEC.md:131,135 amended (c128ccc); `tests/test_render.py::test_a_finished_mark_dims_a_row_the_run_did_not_change` |
| IN-02 (competing words) | J10 | closed | `render_skipped` deleted (no reference remains in `installer/`), the `Not attempted:` line deleted (`installer/execute_screen.py:885-887`), `✖` in failure details (`installer/render.py:303`), `_blocked_row` fallback `not available on this platform` (`installer/session.py:717`); `tests/test_render.py::test_the_run_report_states_a_dependency_failure_once`, `tests/test_execute_screen.py::test_cancel_mid_run_lets_the_in_flight_tool_finish` |
| IN-01 (running keys line unpinned) | J10 | closed | `tests/test_execute_screen.py::test_the_running_keys_line_is_the_contract_copy` asserts `_KEYS_RUNNING` (`installer/execute_screen.py:73`) verbatim mid-run |
| TUI-01 (no highlighted row on open) | J10 | closed | `installer/execute_screen.py:453-473` `_paint_review` owns the cursor (keeps the id, else 0); `::test_the_review_opens_with_the_first_row_highlighted_so_r_works_at_once`, `::test_a_published_state_keeps_the_cursor_on_the_same_tool` |
| WR-09 (lost chsh handoff for an installed oh-my-zsh) | J11 | closed per L-20-11 | `installer/engine.py:208-222` a present tool whose method declares `refuses_existing` skips the script on repair/reinstall and dispatches post-install, result `manual`; `installer/model.py:795-799` bool validation; `installer/registry.toml:589-592` only `oh-my-zsh`; `tests/test_engine.py::test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair`, `::test_a_refusing_method_still_runs_when_the_tool_is_absent`, `tests/test_execute_screen.py::test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff`, `::test_a_fresh_oh_my_zsh_install_in_the_review_shows_the_reviewed_chsh_handoff`; see IN2-01 for a side effect |
| P-06 (`Install` / `with_sensitive_confirm`) | J12 | closed | both deleted from `installer/session.py`; `_with_force` binds the confirmation (`installer/session.py:462`); protocol pin ported to `SensitiveInstall` (`tests/test_session.py::test_sensitive_install_protocol_parameters_are_unchanged`) |
| P-08 (`Resolution.order` / `dragged_in` / `warnings`, second sort, `Blocked.reason`) | J12 | closed | `installer/deps.py:23-36` three fields, one `topo` call; the only production caller (`installer/session.py:744`) reads `closure`, `blocked`, `requested_by`; no production reference to the deleted fields remains |
| P-07 / IN-03 (`run_wizard(platform=…)`, questionary `tag-*` styles, `selection.Choice` / `categories` / `tools_in`) | J12 | closed | `installer/app.py:97-110` signature; `setup.py:1513-1522` caller; `_STYLE` no longer carries `tag-*`; `installer/selection.py` keeps `select_tools` and `unstaged_recommends` only; no production reference remains |
| P-09 (runnable set x3, post-run renderers x2) | J12 | closed | one `RUNNABLE` (`installer/session.py:108-116`) used at `installer/app.py:144` and `installer/execute_screen.py:477`; one `render_run_report`; `tests/test_plan.py::test_runnable_is_every_disposition_an_engine_runs` |
| P-10 (`_row` duplication, unreachable branch) | J12 | closed / kept by decision | `installer/session.py:606-614` `_off_policy_reason`, `:628-640` local `make`; the final `return make(Disposition.SKIP, _first_clause(state))` is reachable (a present tool with no method for this platform reaches it) and the pyright narrowing guard was kept as 20-29 recorded |
| IN-06 (`fold_reason` on narrow widths) | J12 | closed | `installer/render.py:70` floor of 20 cells; `tests/test_render.py::test_fold_reason_keeps_a_readable_width_after_a_full_first_line` |
| IN-09 (plan-gate miscalibrations) | — | n/a (verifier note, recorded in RUN-LEDGER) | — |
| OC-01 (native executors run sudo) | — | deferred to LIFE-02 per the brief; not re-raised | — |

## Narrative Findings (AI reviewer)

## Warnings

### WR2-01: A headless PATH-wiring or PATH-audit failure passes the e2e gate whenever the run also has explained dependency failures

**File:** `scripts/container-e2e-verify.sh:426-434` (with `setup.py:1529-1550`)
**Issue:** Plan 20-24 made `setup.main` exit 1 after a run whose `configure_path` or `_verify_and_clean` raised, printing `PATH wiring could not be completed: …` / `PATH audit could not be completed: …`. Plan 20-21's `install_step_ok` accepts exit 1 on exactly one condition: `[[ "$setup_exit" -eq 1 && "$ACC_DEP_FAILED" -gt 0 ]]` after `dependency_failures_explained`. The gate reads only the `Summary —` line and the outcome rows, so the new exit-1 cause is invisible to it. The real catalog's pass1 and both pass2 install steps always carry explained dependency failures (the `TRACER_*_OK (dependency_failed=N fully explained by manual handoffs …)` branch is the normal result), so in the only full-catalog container proof the PATH-wiring failure cannot be told apart from the accepted exit. 20-21-PLAN.md:22 names "an exit 1 with no explained dependency failure (a PATH-wiring error)" as caught; the "with explained dependency failures" case is the one the catalog produces.
**Failure scenario (probe-confirmed with the test harness):** transcript `Summary — 5 installed, 1 manual, 1 dependency failed` + `✖ mmdc  dependency failed — pi` + `○ pi  manual — see the setup steps in the log` + `PATH wiring could not be completed: [Errno 30] Read-only file system: '/home/tester/.bashrc'`, then `install_step_ok 1` returns 0 (pass). The container's `~/.myshellrc` wiring is never asserted elsewhere in the script, so `make e2e` reports `TRACER_CLEAN_INSTALL_OK` for a run that left PATH unwired.
**Fix:** count the post-run error lines in `accumulate_summaries` and gate on them:
```bash
# accumulate_summaries, next to ACC_RUNS:
if grep -Eq '^PATH (wiring|audit) could not be completed: ' "$file"; then
  ACC_POST_RUN_ERRORS=$((ACC_POST_RUN_ERRORS + 1))
fi
# install_step_ok, with the other zero checks:
[[ "$ACC_POST_RUN_ERRORS" -eq 0 ]] || return 1
```
Initialise `ACC_POST_RUN_ERRORS=0` beside the other accumulators (pass1 and both pass2 steps, and `_summary_harness` in `tests/test_container_e2e_receipts.py`), print it in the `*_INCOMPLETE` lines, and add a `test_install_step_gate` case with the transcript above expecting 1.

## Info

### IN2-01: A refused reinstall of a present tool marks it unresolved, so a dependent is reported `dependency failed` although the dependency is installed

**File:** `installer/session.py:517` (with `installer/engine.py:208-222`)
**Issue:** The 20-26 refusal path returns `InstallStatus.MANUAL_REQUIRED`, which is in `_UNRESOLVED`. `execute_plan` then adds the tool to `unresolved`, and any later INSTALL/REPAIR/REINSTALL row that requires it gets `DEPENDENCY_FAILED` (`blocked_by=(tool,)`) without being attempted, and the exit code becomes 1. The dependency is present and untouched: the user pressed `r` on a current, installer-owned tool. Probe: a REINSTALL row returning the refusal followed by an INSTALL row requiring it gives `[('omz', 'manual', ()), ('dep', 'dependency_failed', ('omz',))]`. Not reachable with the shipped registry (no tool `requires` `oh-my-zsh`, the only `refuses_existing` entry), so Info.
**Fix:** one line at `installer/session.py:517`:
```python
if result.status in _UNRESOLVED and not (
    row.disposition is Disposition.REINSTALL and result.status is InstallStatus.MANUAL_REQUIRED
):
    unresolved.add(tool.id)
```
(A REPAIR of a broken present tool stays unresolved: its state is not `_settled`.)

---

_Reviewed: 2026-10-18T16:51:05Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
