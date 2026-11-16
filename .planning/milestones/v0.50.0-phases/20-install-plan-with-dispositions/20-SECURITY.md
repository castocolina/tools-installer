---
phase: "20"
slug: install-plan-with-dispositions
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 52
threats_closed: 52
threats_open: 0
threats_open_nonblocking: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_head: d0fed09
created: "2026-10-18"
---

# Phase 20 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

The register comes from the `<threat_model>` blocks of 20-01..20-31-PLAN.md: T-20-01..T-20-51 with no duplicate ids and no gaps, plus T-20-SC, which appears in every plan and is counted once (52 total; severity 14 high, 26 medium, 12 low; disposition 50 mitigate, 2 accept, 0 transfer). Later gap plans repeat earlier rows; the latest plan's disposition wins. Each `mitigate` threat was checked in the code at the cited line and against a named test that exists. The 71 cited test names were run on this tree (`uv run --frozen pytest --no-cov -n 4 -k <names> tests/`): 104 collected items passed, exit 0. Two cited tests were renamed by later plans and are cited under their current names: `test_render_update_notes_prints_child_output_literally` -> `test_render_done_notes_prints_child_output_literally` (20-31), `test_with_sensitive_confirm_reaches_post_install_gate` -> `test_execute_plan_confirmation_reaches_the_post_install_gate` (20-28). The configured level is ASVS L1. The audited tree is d0fed09, whose code equals 4c44626 (`git diff 4c44626 d0fed09 -- installer setup.py scripts tests` is empty).

Path shorthand: `ss` installer/session.py, `es` installer/execute_screen.py, `wa` installer/wizard_app.py, `rd` installer/render.py, `ap` installer/app.py, `vs` installer/version_status.py, `rc` installer/receipts.py, `en` installer/engine.py, `e2e` scripts/container-e2e-verify.sh, `tce` tests/test_container_e2e_receipts.py; other tests are `tests/<file>`.

---

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| published state -> plan | the plan is a pure function of published state: no probe, no network, no subprocess |
| registry `requires` -> resolver | a registry cycle or an unknown id is reported, never loops or crashes the plan |
| review -> Enter / "Run this plan?" | the consent covers exactly the dispositions shown; a hidden overwrite (drift repair), escalation or reinstall would void it |
| review text -> user decision | a promised update the engine refuses, or a promised migration that does not exist, misleads the consent |
| plan (minutes old) -> engine | state can change between consent and the row's turn (TOCTOU); the engine re-checks |
| probe and child-process text -> review, summary and log | plugin ids, repo paths and `CommandError.detail` are untrusted strings reaching a Rich console and a Textual widget |
| `ConfigStep.argv` / `cwd` -> child process | argv values come from constants and registry pins; cwd is a repo path found on disk minutes earlier |
| composition root -> services | a route that builds its own service copy acts on a different epoch than the UI |
| headless refresh -> bookkeeping writes (L-20-10) | the pre-confirmation refresh holds adoption, retirement and cache writes until consent |
| headless transcript -> `make e2e` gate | the gate must fail a run that did nothing, crashed, or exited non-zero for a run-level reason |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Status | Evidence file:line + test |
|---|---|---|---|---|---|---|
| T-20-01 | DoS | `topo` over the full closure | low | mitigate | CLOSED | installer/deps.py:125-146 (`visiting` guard raises `DependencyCycleError`); `test_deps.py::test_closure_raises_on_a_cycle` |
| T-20-02 | Info Disclosure | `Blocked.reason` text in the review | low | accept | CLOSED | AR-20-01 |
| T-20-03 | Repudiation | two copies of the update gate | medium | mitigate | CLOSED | one `update_refusal` (installer/update.py:238) used by `_perform` (update.py:323) and `build_plan` (ss:683); `test_update_refusal_matches_perform_for_every_refusal`, `test_update_refusal_is_none_for_an_updatable_owner` |
| T-20-04 | Spoofing | UI promising a migration | low | mitigate | CLOSED | no migration promise in UI strings; `test_update.py::test_no_migration_promise_anywhere_under_installer` |
| T-20-05 | Tampering | headless service construction drifting from the TUI's | medium | mitigate | CLOSED | `_build_services` (setup.py:718); `VersionRefreshService(`, `UpdateService(`, `node_install_policy(tools)` each appear once in setup.py |
| T-20-06 | Tampering | `build_plan` probing the host | medium | mitigate | CLOSED | ss:738-805 reads only `state_of`; `test_plan.py::test_build_plan_spawns_no_subprocess` |
| T-20-07 | EoP | `a` / `--yes` reinstalling every current tool | high | mitigate | CLOSED | ss:692-705 (REINSTALL only for direct + OK + installer-owned + id in the set; dragged rows SKIP); `test_reinstall_requires_the_id_in_the_reinstall_set`, `test_reinstall_set_is_ignored_for_a_foreign_owned_row`, `test_reinstall_set_is_ignored_for_a_dragged_row` |
| T-20-08 | EoP | REPAIR/UPDATE of a native or os-package tool reaching sudo | high | mitigate | CLOSED | ss:659-665 (broken + `UNMANAGEABLE_OWNERS` -> BLOCKED), ss:683-691 (`update_refusal` -> SKIP, not runnable), engine gate update.py:260; `test_plan.py::test_no_sudo_argv_on_the_plan_path` |
| T-20-09 | Tampering | silent overwrite through a drift REPAIR | medium | mitigate | CLOSED | ss:590-594 (`changed since install; the file is replaced`); `test_broken_by_receipt_drift_is_will_repair_with_the_drift_reason` |
| T-20-10 | Tampering | markup or ANSI in a plan reason | medium | mitigate | CLOSED | rd:87-103 (`Text.append`, `sanitize_log_line`), rd:250 (`markup=False`); `test_render_plan_renders_markup_and_escapes_in_a_reason_literally`, `test_render_plan_sanitizes_step_text`, `test_outcome_row_text_renders_markup_and_control_characters_literally` |
| T-20-11 | Tampering | a raced row reported as done | medium | mitigate | CLOSED | ss:449 (`ALREADY_INSTALLED` -> skipped), ss:555-561 (update status other than updated/failed -> blocked); `test_update_latch_refusal_is_blocked`, `test_a_crashing_row_is_crashed_and_the_rest_not_attempted` |
| T-20-12 | Repudiation | crash or cancel leaving rows without an outcome | high | mitigate | CLOSED | ss:476-478, ss:565-574 (`crashed`, then every later row `not_attempted`); `test_session.py::test_a_crashing_row_is_crashed_and_the_rest_not_attempted` |
| T-20-13 | Tampering | executing a plan that has a WAIT row | high | mitigate | CLOSED | ss:460-461 raises `ValueError` before anything runs; `test_session.py::test_execute_plan_refuses_a_plan_with_a_wait_row` |
| T-20-14 | Tampering | `cwd` swapped for a symlink or removed | high | mitigate | CLOSED | ss:316-333 (`_valid_cwd`: absolute, `lstat`, `S_ISDIR`), checked at execution time ss:405-408; `test_reconfigure_refuses_a_cwd_that_is_relative_missing_or_a_symlink` |
| T-20-15 | DoS | continuing past a failed `plugin_enable` | high | mitigate | CLOSED | ss:431-434 returns at the first failed step; `test_reconfigure_stops_at_the_first_failing_step`, `test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next` |
| T-20-16 | Tampering | shell interpretation through the cwd wrapper | medium | mitigate | CLOSED | ss:308-313 (`sh -c 'cd -- "$1" && shift && exec "$@"' sh <cwd> <argv…>`); `test_reconfigure_wraps_a_step_with_cwd_in_the_portable_directory_shim` |
| T-20-17 | Tampering | ANSI or markup in install error text | medium | mitigate | CLOSED | rd:162, rd:195 (`sanitize_log_line`), rd:310 (`escape`); `test_render.py::test_outcome_row_error_text_is_sanitized_and_literal` |
| T-20-18 | Tampering | retained selection rebinding `_staged` or adding a dragged id | medium | mitigate | CLOSED | wa:2890-2895 (`intersection_update`); `test_install_closed_keeps_exactly_the_retained_rows_selected`, `test_install_closed_never_adds_a_dragged_in_dependency` |
| T-20-19 | Repudiation | PATH or verify failure exiting 0 | medium | mitigate | CLOSED | wa:3004-3009 (`run_errors`), setup.py:1302-1310 (`_session_exit_code`); `test_setup.py::test_session_exit_code_is_one_iff_an_outcome_failed_or_a_run_error_exists` |
| T-20-20 | Tampering | an all-skipped run still wiring PATH or syncing terminals | low | mitigate | CLOSED | es:667 (`ran_anything` gates wire and verify), wa:2920 (sync gated); `test_only_skipped_rows_finish_immediately_without_the_engine_or_path_wiring` |
| T-20-21 | EoP | `--yes` reinstalling or mutating unselected tools | high | mitigate | CLOSED | ap:133 (`reinstall=frozenset()`); `test_app.py::test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped` |
| T-20-22 | Tampering | executing rows whose state never settled | high | mitigate | CLOSED | ap:135-141 (`State check failed`, every row `not_attempted`, no `execute_plan`); `test_app.py::test_headless_reports_a_state_check_failure_and_runs_nothing` |
| T-20-23 | Repudiation | `make e2e` passing while it parses nothing | medium | mitigate | CLOSED | e2e:364-405 (`Summary — ` parser, dependency rows, manual-names cross-check), e2e:411-428; `tce::test_accumulate_counts_not_attempted_and_crashed`, `tce::test_install_step_gate` |
| T-20-24 | Tampering | a late publication after `esc` starting a cancelled run | high | mitigate | CLOSED | es:538 (token captured), es:560 (compared), es:908 (bumped by `esc`); `test_execute_screen.py::test_a_late_publication_after_esc_starts_nothing`, `test_esc_during_the_wait_cancels_it_and_keeps_the_selection` |
| T-20-25 | DoS | the screen starting a second refresh pass | medium | mitigate | CLOSED | es:548 is the only `.refresh(` in es; `test_mount_with_checking_rows_joins_the_flight_without_starting` |
| T-20-26 | EoP | `r` on a foreign-owned or dragged row | medium | mitigate | CLOSED | es:488-506 (only `can_reinstall` rows; the set is mutated only at es:504); `test_r_toggles_an_installer_owned_current_row_both_ways`, `test_r_on_a_dnf_owned_row_changes_nothing_and_warns`, `test_r_on_a_dragged_row_changes_nothing` |
| T-20-27 | Tampering | a second vocabulary or engine loop surviving | low | mitigate | CLOSED | `git grep` finds no `run_installs`, `summarize(`, `fold_run`, `Summary(`, `render_audit`, `render_summary`, `render_dependency_notice`, `installer.audit`, `ToolStatus`; `installer/audit.py` and `tests/test_audit.py` are absent |
| T-20-28 | Info Disclosure | unreachable prompt path kept alive | low | mitigate | CLOSED | `git grep` finds no `select_categories`, `ask_checkbox`, `_ask_checkbox`, `reapply_post_install` |
| T-20-29 | Tampering | stale doctrine in architecture.md | low | mitigate | CLOSED | no `run_installs`, `render_dependency_notice` or `audit(` before the Phase 20 section (.claude/architecture.md:670); `test_docs.py::test_architecture_records_phase_20_mechanisms` |
| T-20-30 | Tampering | presence-only `installed` fallback | low | mitigate | CLOSED | es:322 `version_refresh: VersionRefreshService` is required, the `installed` field is gone; `test_execute_screen.py::test_execute_inputs_requires_a_version_refresh_service` |
| T-20-31 | EoP | `a` on an all-current tier re-running anything | medium | mitigate | CLOSED | `test_wizard_app.py::test_a_on_an_all_current_tier_starts_nothing_and_summarizes_n_skipped` |
| T-20-32 | Repudiation | a crash outside `execute_plan` dropping rows | high | mitigate | CLOSED | es:678-694 (outer except, `_complete` in the finally), es:286-295; `test_execute_screen.py::test_a_crash_outside_execute_plan_fills_every_row_as_not_attempted` |
| T-20-33 | DoS | `_wait_worker` dying on a refresh error | medium | mitigate | CLOSED | es:553-557 (catch, `StateSettled` from the finally); `test_a_refresh_raising_value_error_settles_with_the_error_and_enter_retries` |
| T-20-34 | Repudiation | a late settle repainting a finished run | medium | mitigate | CLOSED | es:563-564 (`started`/`finished` guard); `test_a_late_settle_never_repaints_a_finished_run` |
| T-20-35 | Repudiation | `make e2e` passing an empty, crashed or summary-less run | high | mitigate | CLOSED | e2e:430-438 (`install_step_ok`: runs = summaries, no not_attempted or crashed, exit rule); `tce::test_install_step_gate`, `tce::test_every_install_step_uses_the_one_gate` |
| T-20-36 | Tampering | a dependency installed for a tool that will never install, or a runnable tool blocked | medium | mitigate | CLOSED | ss:775-804 (settled-aware propagation and prune); `test_a_dragged_chain_needed_only_by_a_blocked_tool_is_skipped`, `test_a_dragged_dependency_of_a_blocked_requester_is_skipped_not_installed`, `test_a_dragged_dependency_still_needed_by_a_runnable_tool_keeps_its_disposition`, `test_a_present_dependency_blocked_for_its_own_reason_does_not_block_its_dependent` |
| T-20-37 | Repudiation | headless decline after writes were made | medium | mitigate | CLOSED | ap:118 (`hold_writes`), ap:145-150 (commit only after consent), vs:957-990; `test_a_declined_headless_plan_adopts_nothing`, `test_a_declined_headless_plan_retires_nothing_and_saves_no_cache` |
| T-20-38 | Tampering | queued adoption of swapped bytes | high | mitigate | CLOSED | vs:1386-1402 (the commit re-calls `receipts.adopt`), rc:304-333 (`_WRITE_LOCK`, receipt-exists refusal, fresh `rehash=True` fingerprint); `test_a_held_adoption_whose_file_changed_before_consent_is_printed_not_written`, `test_adoption_binds_the_digest_to_the_adopted_bytes` |
| T-20-39 | Repudiation | headless exit 0 after a PATH failure, or a second presence predicate | medium | mitigate | CLOSED | setup.py:1530-1550 (`run_live` errors join the exit code), one bound install via `_build_services` (setup.py:1513); `test_session_exit_code_is_one_iff_an_outcome_failed_or_a_run_error_exists` |
| T-20-40 | DoS | a raising terminal-sync step halting the batch | low | mitigate | CLOSED | ss:370-376 (caught as a failed step); `test_session.py::test_a_raising_terminal_sync_step_fails_its_row_and_the_batch_continues` |
| T-20-41 | Repudiation | pnpm replay or cleanup notes never shown | medium | mitigate | CLOSED | rd:257-284 (`render_done_notes`, UPDATE branch) inside `render_run_report` (rd:287-296); `test_render_done_notes_prints_every_successful_update_extra`, `test_render_done_notes_is_silent_without_extras` |
| T-20-42 | Tampering | markup or escapes in update detail | low | mitigate | CLOSED | rd:281-284 (`sanitize_log_line`, `markup=False`); `test_render_done_notes_prints_child_output_literally` |
| T-20-43 | EoP | reinstall changing the login shell or deleting `~/.oh-my-zsh` | high | mitigate | CLOSED | en:208-222 (`refuses_existing` -> MANUAL_REQUIRED, the runner is never called; post-install returns reviewed lines only behind `confirm_sensitive_action`); `test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair` (`calls == []`), `test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff` |
| T-20-44 | Tampering | a registry key that silently skips installs | medium | mitigate | CLOSED | installer/model.py:795-797 (bool validated at load), en:208 (only when installed and repair); `test_a_refusing_method_still_runs_when_the_tool_is_absent`, `test_the_registry_marks_only_oh_my_zsh_as_refusing_existing`, `test_refuses_existing_must_be_a_bool` |
| T-20-45 | Repudiation | finished marks making an untouched tool look changed | low | mitigate | CLOSED | `test_render.py::test_a_finished_mark_dims_a_row_the_run_did_not_change`, `test_render.py::test_the_run_report_states_a_dependency_failure_once` |
| T-20-46 | EoP | the merged wrapper dropping the sensitive confirmation | medium | mitigate | CLOSED | ss:272-302 (`_with_force` always forwards `confirm_sensitive_action`), ss:467; `test_force_repair_composes_under_sensitive_confirm`, `test_execute_plan_forwards_the_confirmation_and_unchanged_kwargs`, `test_execute_plan_without_a_confirmation_produces_no_instructions`, `test_execute_plan_confirmation_reaches_the_post_install_gate` |
| T-20-47 | EoP | headless skipping consent because its runnable test drifted | medium | mitigate | CLOSED | `RUNNABLE` at ss:113-121, read at ap:144 and es:478; `test_plan.py::test_runnable_is_every_disposition_an_engine_runs` |
| T-20-48 | Repudiation | e2e reporting OK despite a PATH wiring or audit failure | medium | mitigate | CLOSED | e2e:388-391 (`ACC_POST_RUN_ERRORS`), e2e:435 (must be 0); the drift guard ties the prefixes to setup.py:1542 and :1548; `tce::test_install_step_gate`, `tce::test_the_gate_reads_the_post_run_lines_setup_prints` |
| T-20-49 | Tampering | a receipt adopting a binary swapped between plan and consent | medium | mitigate | CLOSED | vs:1389-1402 (fresh `receipts.adopt` at commit; a refusal is printed via `commit_writes`, never recorded), rc:324-333; `test_a_held_adoption_whose_file_changed_before_consent_is_printed_not_written`, `test_a_consented_headless_plan_commits_the_adoption_before_it_runs` |
| T-20-50 | Tampering | update or reconfigure after its prerequisite failed | medium | mitigate | CLOSED | ss:484-493 (the `blockers` check runs before every runnable disposition); `test_session.py::test_a_failed_prerequisite_stops_a_present_dependents_update_or_reconfigure` |
| T-20-51 | Repudiation | a reconfigure warning or a message-less crash leaving no trace | low | mitigate | CLOSED | rd:262-263 (RECONFIGURE branch of `render_done_notes`), ss:336-339 (`_first_line`), ss:565-573; `test_session.py::test_a_crash_detail_is_the_type_and_the_first_line`, `test_render_done_notes_*` |
| T-20-SC | Tampering | npm/pip/cargo installs (supply chain) | high | accept | CLOSED | AR-20-02 |

---

## Accepted Risks Log

| Risk ID | Threat | Rationale | Plan |
|---------|--------|-----------|------|
| AR-20-01 | T-20-02 | `Blocked.reason` texts are literals built only from registry ids; probe-derived text is sanitized by the renderer (rd:97). | 20-01 |
| AR-20-02 | T-20-SC | No package installs: `git log 8fc5b75^..HEAD -- pyproject.toml uv.lock` is empty. | every plan |

---

## Residuals and Deferred Items (no register change)

- T-20-08: an outdated native-owned tool lands as SKIP (not the BLOCKED the plan describes); it still never reaches an executor.
- T-20-23/35/48 (e2e gate) are verified by the shell code and the `tce` unit tests; the live `make e2e` runs are recorded in RUN-LEDGER.md (3c74d96 rc 0; the 4c44626 re-run is recorded there when it finishes).
- Accepted review items (not register threats): OC-01 native executors run sudo -> LIFE-02 (the plan path blocks those rows, `test_no_sudo_argv_on_the_plan_path`); OC2-01 the TUI catalog refresh writes bookkeeping before the review (L-20-10 TUI boundary, .claude/architecture.md "Phase 20"); OC-06 residual, idempotent PATH wiring after a failed row. Sources: 20-REVIEW-CONSOLIDATED.md, 20-REVIEW-CONSOLIDATED-2.md, 20-VERIFICATION.md, RUN-LEDGER.md.

---

## Unregistered Flags

None. No 20-NN-SUMMARY.md has a `## Threat Flags` section; 20-08-SUMMARY.md has a disposition note that maps only to T-20-14, T-20-15 and T-20-16.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-18 | 52 | 52 | 0 | gsd-security-auditor (Claude Opus 5.5), ASVS L1, block_on high, HEAD d0fed09 (code = 4c44626); 104 cited test items passed |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-18
