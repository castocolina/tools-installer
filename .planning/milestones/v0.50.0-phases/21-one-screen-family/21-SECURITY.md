---
phase: "21"
slug: one-screen-family
status: verified
verdict: SECURED
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 77
threats_closed: 76
threats_open: 0
threats_open_nonblocking: 1
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_range: 390f464..68d498d
audited_head: 68d498d
created: "2026-11-03"
---

# Phase 21 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Where the register comes from:**
- The `<threat_model>` blocks of 21-01..21-21-PLAN.md: T-21-01..T-21-60, with no gaps and no duplicate ids. T-21-SC appears in every plan and is counted once. That is 61 threats.
- 16 threats added from the review fix loop, ids T-21-R01..T-21-R16. They come from 21-REVIEW.md (consolidated C-01..C-34 and the RR-01..RR-06 re-review) and 21-REVIEW-FIX.md. Only findings with a security angle are registered: removal truth, the mutation lock, crash safety, attribution, and the forced exit. Two security findings fold into existing ids instead: C-11 into T-21-41 and C-04 into T-21-11.
- Severity: a review High is `high`, Important is `medium`, Minor is `low`.

**Totals:** 77 threats.
- Severity: 5 high, 42 medium, 30 low.
- Disposition: 72 mitigate, 5 accept, 0 transfer.

**How each threat was checked:**
- Every `mitigate` threat was read in the code at the cited line, using codegraph explore first, then file reads.
- Every cited test was confirmed to exist under its current name. They were then run on this tree with `uv run pytest -n 4 --no-cov -k <names> tests/`:
  - the plan-cited tests: 117 items passed;
  - the review-fix RED tests: 24 passed;
  - the tests found for the unnamed plan tests: 16 passed.
  - Exit code 0 in every run.

**Configuration:** ASVS L1, block_on high.

**Path shorthand:**

| Short | Path |
|-------|------|
| `wa` | installer/wizard_app.py |
| `ap` | installer/app.py |
| `un` | installer/uninstall.py |
| `vs` | installer/version_status.py |
| `tb` | installer/tool_browser.py |
| `ct` | installer/catalog_tui.py |
| `uc` | installer/ui_common.py |
| `po` | installer/policy.py |
| `rd` | installer/render.py |
| `ss` | installer/session.py |
| `es` | installer/execute_screen.py |
| `own` | installer/ownership.py |
| `sf` | tests/test_screen_family.py |
| `tw` | tests/test_wizard_app.py |
| `pe` | tests/test_policies_e2e.py |
| `tv` | tests/test_version_status.py |

Other tests are written as `tests/<file>`.

---

## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| keyboard -> App priority bindings | key bursts and quit keys reach `show_view` and the quit actions while a pop/push or a delete is in flight |
| published state -> Uninstall rows -> filesystem delete | only a row the state proves removable can be selected, and the delete re-proves at deletion time |
| removal / audit / pass worker threads -> event loop and published state | the outcomes cross back as posted messages, and shared state is written under the service lock |
| TUI keys -> host mutations | brew/apt/pnpm/`systemctl --user`/`launchctl`, rc writes and file removals, all behind one app mutation lock |
| child-process and OS error text -> status, detail and Doctor body | untrusted strings reach Rich/Textual widgets |
| Policies/Doctor screen -> host state | live reads of shims, rc blocks, plists and the user systemd manager |
| test/UAT process -> developer host | the guard tests only read, and the UAT shim lives only in a disposable container |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Status | Evidence file:line + test |
|---|---|---|---|---|---|---|
| T-21-01 | DoS | `show_view` transient root | medium | mitigate | CLOSED | wa:3207-3210 (`_navigable` = `self.screen in self._views.values()`); wa:3172-3190 (awaited pop then push); `sf::test_nav_burst_with_escape_keeps_depth_two` (`4 5 esc 6 1 esc`) |
| T-21-02 | Repudiation | stale status after leave | low | mitigate | CLOSED | wa:3178-3181 (`leaving.clear_transient()` before the pop); uc:376; `sf::test_entry_status_survives_first_entry_and_leave_clears_it` |
| T-21-03 | Tampering | `outcome_detail_text` remove_failed | medium | mitigate | CLOSED | rd:147-163 (first line, then `sanitize_log_line`); `tests/test_render.py::test_outcome_words_for_removal` (`\x1b[31mx` case, line 1255) |
| T-21-04 | EoP | REMOVE reaching `execute_plan` | medium | mitigate | CLOSED | ss:115-123 (`RUNNABLE` has no REMOVE); `tests/test_session.py::test_remove_is_not_runnable`; `tests/test_plan.py::test_build_plan_never_emits_remove` |
| T-21-05 | Tampering | stale selected id in `Accepted` | medium | mitigate | CLOSED | tb:250-256 (`reload` prunes unselectable ids); tb:365-371 (`selected_ids` filters on `selectable`); `tests/test_tool_browser.py::test_accept_never_carries_an_unselectable_id`; `sf::test_publish_prunes_a_staged_tool_that_became_unavailable` |
| T-21-06 | Tampering | stale prerequisite snapshot | low | mitigate | CLOSED | po:137, po:166-169 (`missing_requirements` calls `missing_requires_now` on each read); wa:2275-2276 (re-read at apply); wa:1926-1931 (on render); `pe::test_a_failed_requirements_read_blanks_requires_and_detail` |
| T-21-07 | Tampering | in-flight pass republishing a pending id | medium | mitigate | CLOSED | vs:1197-1205 (`mark_pending`); vs:1874-1878 (the commit filter skips `_pending_ids`); `tv::test_mark_pending_survives_a_pass_that_commits_after_it` |
| T-21-08 | Tampering | torn `_states`/`_evidence` reads | medium | mitigate | CLOSED | vs:1203-1205, vs:1223-1231, vs:1240-1245 (writes under `self._lock`); vs:1739-1741 (evidence snapshot under the lock); `tv::test_evidence_is_read_under_the_lock_as_a_snapshot` |
| T-21-09 | DoS | new probe inside the pass | low | mitigate | CLOSED | vs:746 (`smoke=lambda _cmd: None`, so no subprocess); vs:1801 (reuses the pass's `which`); the phase diff of vs adds no `subprocess`/`urlopen` call (only a docstring word) |
| T-21-10 | Tampering | overlapping passes out of order | medium | mitigate | CLOSED | wa:2978-2987 (`_refresh_running`/`_refresh_pending`); wa:3031-3037 (restart on finish); vs:1874-1878 (seq/epoch barrier); `sf::test_two_requests_during_a_pass_coalesce_into_one`; `sf::test_a_mutation_during_a_running_pass_supersedes_it` |
| T-21-11 | DoS | failed pass leaves `…` / pass per entry | low | mitigate | CLOSED | wa:3003-3020 (the first error rides on both publications; `except` also publishes, the C-04 fold); wa:3026 (retry copy); `sf::test_failed_pass_writes_the_retry_copy`; `sf::test_a_failed_skills_stage_writes_the_retry_copy`; `sf::test_an_unexpected_pass_failure_writes_the_retry_copy`; `sf::test_entering_a_view_starts_no_pass` |
| T-21-12 | Info Disclosure | pass error rendered as markup | low | mitigate | CLOSED | uc:83-86 (`StatusLine.set` uses `Text(text, …)` and never parses markup); wa:3022-3029 |
| T-21-13 | Spoofing | unknown owner attributed to a manager | medium | mitigate | CLOSED | vs:1971-1972 (unknown returns `UNKNOWN_OWNER_NOTE` before `removal_hint` at vs:1974); vs:637; vs:1945 + own:1314-1315 (`owner_label` is None for unknown, so the cell reads `unknown`); `tv::test_uninstall_unknown_owner_names_no_manager` |
| T-21-14 | Tampering | BROKEN grouped as removable | medium | mitigate | CLOSED | vs:1930-1931 (BROKEN maps to MANAGED before the proof check at vs:1932); wa:1136 (only REMOVABLE is selectable); `tv::test_uninstall_group` |
| T-21-15 | Tampering | one tool's proof authorizing another's delete | medium | mitigate | CLOSED | ap:696-709 (`remove_proven([tool], …)` per tool); un:315-326 (`plan_removal(…, verify=True)`; `kept` is only paths in this tool's `fresh.artifacts`; anything else is refused and never deleted); `tests/test_app.py::test_perform_uninstall_reports_a_refused_tool` |
| T-21-16 | Repudiation | failed delete hidden or reported removed | medium | mitigate | CLOSED | ap:710-717 (`OSError` -> `remove_failed`; `removed` only with no refusal); `tests/test_app.py::test_perform_uninstall_one_failed_delete_does_not_stop_the_rest` |
| T-21-17 | Tampering | review served before the newest pass | medium | mitigate | CLOSED | wa:2989-2997, wa:3031-3040 (waiters are served only when no pass is pending; an error is passed through, never dropped); `sf::test_await_publication_waits_for_the_pending_pass` |
| T-21-18 | Tampering | row selectable before any state proves it | medium | mitigate | CLOSED | wa:1195-1215 (`_unknown_entry` with no paint is `selectable=False, paths=()`); wa:1136-1138; un:315 (re-proof); `tw::test_uninstall_offers_nothing_before_the_first_pass` |
| T-21-19 | Spoofing | false `Nothing to uninstall.` | low | mitigate | CLOSED | wa:1407-1424 (requires every state known; retracts its own copy); `tw::test_a_publish_that_adds_an_env_row_retracts_nothing_to_uninstall` |
| T-21-20 | DoS | Health column pushing `What gets removed` off 80 cols | medium | mitigate | CLOSED | wa:1018 (`_REMOVES_CELL_MAX = 40`); wa:1140-1141 (`Text.truncate`); `tests/test_layout_80x20.py::test_uninstall_rows_fit_at_80x20_with_health` |
| T-21-21 | Tampering | two removals at once | high | mitigate | CLOSED | wa:1462 and wa:1505-1507 (`refuse_if_mutating`, then `begin_mutation(REMOVAL)` before the worker); wa:2736-2741 (a second take raises); `sf::test_a_second_removal_is_refused_while_one_runs` |
| T-21-22 | DoS | crashed remover holding the lock | medium | mitigate | CLOSED | wa:1589-1603 (invalidate even after a crash; `RemovalFinished` posted from `finally`); wa:1606 (`end_mutation()` is the first statement); wa:1566 (`exit_on_error=False`); `sf::test_the_lock_is_released_when_the_remover_crashes` |
| T-21-23 | Tampering | quit mid-delete | medium | mitigate | CLOSED | wa:3496-3520 (`_quit` -> `_exit_after_removal` awaits the `uninstall-removal` worker); wa:3475-3480 (`q` inert under a modal); wa:3487-3494; wa:1594-1601 (invalidate inside the worker); `sf::test_quit_during_a_removal_waits_for_it`; `sf::test_ctrl_c_under_the_palette_during_a_removal_waits` |
| T-21-24 | Repudiation | stale `✓` during removal | medium | mitigate | CLOSED | wa:1510-1511 (`mark_pending` before the worker); vs:1874-1878; `sf::test_a_held_removal_keeps_the_ui_responsive` |
| T-21-25 | Tampering | worker mutations racing | high | mitigate | CLOSED | Each take refuses first, then holds until a completion posted from `finally`: update ct:633-636, ct:680, ct:701-704; toggle wa:2273, wa:2302, wa:2317-2318; daemon wa:2944, wa:3140-3141; removal wa:1505-1507, wa:1602-1603; `sf::test_every_mutating_key_is_refused_during_a_removal`; `sf::test_u_is_refused_during_a_removal` |
| T-21-26 | DoS | holder never releasing | medium | mitigate | CLOSED | Release first in each handler: wa:3447 (`on_tool_updated`), wa:2321, wa:3146, wa:965, wa:1606; unconditional `finally` posts as in T-21-25; `sf::test_a_daemon_default_without_a_policy_id_releases_the_lock` |
| T-21-27 | Spoofing | Policies claiming a removed guard is ON | medium | mitigate | CLOSED | wa:1828-1850 (every render re-reads); wa:1852-1876 (a failed read drops the answer, so the cell is blank); `pe::test_a_removed_ban_reads_off_on_the_next_entry`; `pe::test_a_failed_policy_read_shows_the_error` |
| T-21-28 | DoS | `is-active` probe on the event loop | medium | mitigate | CLOSED | wa:1859-1860 (`state_cache` policies are skipped on the loop); wa:1884-1901 (thread worker); wa:2218-2230 (`live_state` is called only from the daemon worker, wa:3139); `sf::test_the_job_state_is_read_off_the_event_loop` |
| T-21-29 | Tampering | evidence store content | low | accept | CLOSED | AR-21-01 |
| T-21-30 | DoS | full pass on every Doctor entry | medium | mitigate | CLOSED | vs:1207-1231 (`record_evidence` returns whether it changed); wa:958-962 (request only on a change); `sf::test_an_unchanged_audit_requests_no_pass` |
| T-21-31 | Repudiation | Doctor vs tier disagreeing | medium | mitigate | CLOSED | wa:632-639 (Doctor prints `pnpm_findings` of the published `ToolState.reasons`); vs:682-694 (the same template constants); `sf::test_a_healthy_pnpm_owned_tool_prints_no_doctor_finding` |
| T-21-32 | Tampering | deleted fork re-introduced | medium | mitigate | CLOSED | `sf:3588::test_the_replaced_forks_are_gone` (runs over tracked and untracked files in `make test`); `sf::test_a_held_mutation_repaints_a_view_navigated_to_before_it_finishes` |
| T-21-33 | DoS | held `u` requesting passes | low | mitigate | CLOSED | wa:2752 (a refusal posts `RefreshRequested`); wa:2978-2987 (at most one running and one pending); `sf::test_two_requests_during_a_pass_coalesce_into_one` |
| T-21-34 | Tampering | failed invalidate leaving stale `✓` | medium | mitigate | CLOSED | wa:1597-1601 (the invalidate error is kept); wa:1621 and wa:1670-1674 (`_request_pass` on every branch); `tw::test_removal_requests_a_pass_even_when_invalidate_raises` |
| T-21-35 | Tampering | surviving second classifier | low | mitigate | CLOSED | un (237 lines deleted in this range); `sf::test_the_replaced_forks_are_gone` |
| T-21-36 | Spoofing | script install shown with a non-removing hint | low | mitigate | CLOSED | own:1609-1610 (`_NO_REMOVAL_HINT`); vs:1974-1976 (no hint, so the row's own reasons show); `tv::test_uninstall_script_install_shows_its_reasons_and_label` |
| T-21-37 | Repudiation | failed tool reported removed / env-only removal not published | medium | mitigate | CLOSED | wa:1623-1636 (per-tool words from `swept.removed`/`remove_failed`); wa:1670-1674; `sf::test_an_env_only_removal_requests_a_pass_without_invalidating` |
| T-21-38 | Tampering | pnpm reinstall / install run racing | high | mitigate | CLOSED | wa:804, wa:847 (refuse, then `GLOBALS_REINSTALL`); es:580 -> wa:3395-3399 (`INSTALL_RUN`); es:674-685 (`InstallRunFinished` from `finally`) -> wa:3401-3402; `sf::test_a_pnpm_reinstall_holds_the_lock`; `sf::test_an_install_run_holds_the_lock`; `sf::test_every_mutating_key_is_refused_during_a_removal` |
| T-21-39 | DoS | reinstall crash holding the lock | medium | mitigate | CLOSED | wa:857 (`exit_on_error=False`); wa:870-881 (nested `finally` posts `GlobalsReinstalled`); wa:965 (release first); `sf::test_the_lock_is_released_when_the_reinstall_crashes` |
| T-21-40 | Tampering | toggle/`t` on an unreadable row | medium | mitigate | CLOSED | wa:2276-2283 and wa:2377-2380 (`_refuse_unreadable`); wa:1934-1938 (error status plus one pass); `pe::test_space_on_an_unreadable_policy_applies_nothing`; `pe::test_a_failed_requirements_read_blanks_requires_and_detail`; `pe::test_t_on_an_unreadable_policy_opens_no_picker` |
| T-21-41 | Spoofing | fix preview / guard answer stale after a failed read (with C-11) | medium | mitigate | CLOSED | Doctor reads go through `run_live`, and a failure drops the section; wa:707-712 (`enter` refuses while `_preview_error` is set, the C-11 fold); `sf::test_a_failed_doctor_read_shows_the_error`; `sf::test_doctor_enter_does_not_apply_a_fix_it_could_not_preview` |
| T-21-42 | Repudiation | reinstall/PATH fix not reaching the tiers | medium | mitigate | CLOSED | wa:870-878 (invalidate on the worker); wa:726-735 and wa:791-797 (one pass after the last `ConfirmGuardFile`); `sf::test_reinstall_invalidates_and_requests_one_pass`; `sf::test_doctor_fix_requests_one_pass`; `tw::test_doctor_fix_with_a_guard_file_requests_its_pass_after_the_confirmations` |
| T-21-43 | EoP | hidden rc-mutating key | low | mitigate | CLOSED | wa:325-328 (Doctor BINDINGS has only `enter` and `r`); `sf::test_a_is_inert_on_doctor`; `sf::test_doctor_footer_lists_enter_and_r_only` |
| T-21-44 | Spoofing | owned-but-inactive guard reading healthy | medium | mitigate | CLOSED | wa:1873-1874 (owned and not active is DRIFT); wa:1691-1710 (a failed `owned()` fails the pair); `pe::test_an_owned_inactive_policy_reads_drift`; `sf::test_an_unreadable_job_state_shows_the_error` |
| T-21-45 | Tampering | proof tests no longer exercising the real proof | low | mitigate | CLOSED | `tests/test_uninstall.py` calls the real `plan_removal` 63 times over planted trees; the suite passes (part of the 5233-test run in 21-REVIEW-FIX.md) |
| T-21-46 | Tampering | refused row kept selected | medium | mitigate | CLOSED | tb:250-256 (prune); un:315 (re-proof); `sf::test_a_refused_row_leaves_the_selection_when_its_proof_is_gone` |
| T-21-47 | Spoofing | superseded job read repainting | medium | mitigate | CLOSED | wa:1878-1882 (each read carries a generation); wa:1903-1905 (any other generation is dropped); `sf::test_a_superseded_job_state_read_is_discarded` |
| T-21-48 | Repudiation | failed invalidate hidden after a reinstall | low | mitigate | CLOSED | wa:875-877 (a default is set before the call); wa:655-657 (`version cache invalidation failed: …`); `sf::test_a_failed_invalidate_after_a_reinstall_is_reported` |
| T-21-49 | Spoofing | stale environment rows on a visible Uninstall | medium | mitigate | CLOSED | wa:1367-1374 (`_reread_env`); wa:1396-1405 (`state_refreshed` re-reads; a failure keeps the rows and warns only into an empty line); `tw::test_a_publish_rereads_the_environment_rows`; `tw::test_a_failed_env_read_on_publish_keeps_rows_and_status` |
| T-21-50 | Repudiation | partial delete reason dropped | low | mitigate | CLOSED | wa:1166-1191 (dropped only with no `removable` and no `yourself`); `sf::test_a_partial_delete_keeps_its_reason_while_leftovers_remain` |
| T-21-51 | Spoofing | `u` during a removal answering with a row refusal | low | mitigate | CLOSED | ct:633-636 (the lock check comes before every informational refusal); `sf::test_u_is_refused_during_a_removal` |
| T-21-52 | Spoofing | pre-mutation job read landing after a toggle/daemon apply | medium | mitigate | **OPEN (non-blocking)** | Present: wa:2330 (`_finish_toggle` advances the generation) and wa:2267 (`refresh_daemon_state` starts a fresh read). Gap: `refresh_daemon_state` returns at wa:2253-2254 when `live is None` and the policy has `is_active`, and the generation never advances. So a job read started before the apply, landing after it, still repaints its pre-apply ON/OFF. `sf::test_a_mutation_completion_supersedes_an_in_flight_job_read[daemon_default]` covers only a resolved `live`. |
| T-21-53 | Tampering | hostile pnpm reason in the Doctor body | low | mitigate | CLOSED | wa:636-639 (`sanitize_log_line`, then `Text.append`); `sf::test_a_hostile_pnpm_reason_renders_literally` |
| T-21-54 | Repudiation | unmapped reinstall exception skipping the invalidate/post | medium | mitigate | CLOSED | wa:868-881 (the invalidate runs in the outer `finally`, the post in a nested `finally`); `sf::test_a_crashed_reinstall_still_invalidates`; `sf::test_a_real_cache_write_failure_after_a_reinstall_is_reported` |
| T-21-55 | Spoofing | visible Uninstall keeping a removed env row | low | mitigate | CLOSED | wa:1396-1405; `sf::test_a_visible_uninstall_repaints_its_environment_rows_on_publish` |
| T-21-56 | Tampering | UAT `systemctl` shim on the host | low | mitigate | CLOSED | 21-21-PLAN.md:78, 21-21-PLAN.md:180 (container only; the host is forbidden); `rg uat-bin scripts tests` is empty; `/tmp/uat-bin` was absent on the host at audit time; the RUN-LEDGER "Phase 21 tmux TUI check" row records the real home as unchanged |
| T-21-57 | Spoofing | env row cells shifted under the header | low | mitigate | CLOSED | wa:1224-1230 (env rows carry an empty Health cell third); `tw::test_uninstall_health_column_reads_the_published_state` |
| T-21-58 | Tampering | moved health-detail table drifting | low | mitigate | CLOSED | vs:205 (the one `HEALTH_DETAIL`); `rg _HEALTH_DETAIL installer setup.py` is empty; `tests/test_catalog_tui.py` passes |
| T-21-59 | Spoofing | visible Uninstall missing the daemon tweaks row after the apply | low | mitigate | CLOSED | wa:3150-3154 (`_render_published` unless Policies is the visible view); `sf::test_the_daemon_default_apply_repaints_a_visible_uninstall` |
| T-21-60 | Spoofing | persisted pre-reinstall manager snapshot reused | medium | mitigate | CLOSED | vs:1249 (`_managers_invalid` set before the write); vs:1619 (the persisted snapshot is skipped while it is set); vs:1912-1915 (cleared only when a queried snapshot is saved); `tv::test_failed_invalidate_save_still_requeries_the_managers`; `sf::test_a_real_cache_write_failure_after_a_reinstall_is_reported` |
| T-21-SC | Tampering | npm/pip/cargo installs | high | accept | CLOSED | AR-21-02 |
| T-21-R01 | Tampering | forced exit / inherited `ctrl+q` abandoning the delete thread (C-26, RR-01) | high | mitigate | CLOSED | wa:3482-3485 (`action_quit` routes to the soft quit); wa:3487-3494 (only a second `ctrl+c` while `quitting` cuts, with `_REMOVAL_QUIT_CUT` at wa:1025). What a cut leaves is bounded: receipts are written with `atomic_write_text` (installer/receipts.py:149) and deleted only after every path is gone (un:323-325); rc edits are atomic (installer/guards.py:607, installer/shellrc.py:193); a dir is removed through an exclusive quarantine rename (un:226-247), and a leftover quarantine sibling is listed as `yourself`. Tests: `sf::test_ctrl_q_during_a_removal_waits_like_q`, `sf::test_a_second_ctrl_c_during_a_removal_exits_at_once`, `sf::test_a_second_q_during_a_removal_still_waits` |
| T-21-R02 | Tampering | first-run link pick bypassing the lock during the daemon apply (C-18) | medium | mitigate | CLOSED | wa:3276-3282 (the pick is deferred while the lock is held); wa:3155-3157 (it runs after `end_mutation`); `sf::test_a_first_run_link_pick_waits_for_the_daemon_default` |
| T-21-R03 | Repudiation | `removed` claimed while the plan changed under the confirm (C-14, RR-05) | medium | mitigate | CLOSED | ap:700-708 (a dropped or added removable path refuses the whole tool and keeps its receipt); `tests/test_uninstall_e2e.py::test_a_tool_whose_plan_dropped_a_previewed_path_is_not_removed`, `::test_a_tool_only_refusal_is_on_the_status_once`; `tests/test_app.py::test_perform_uninstall_names_only_the_previewed_paths_that_dropped_out`, `::test_perform_uninstall_refuses_a_plan_that_grew_since_the_preview` |
| T-21-R04 | DoS | planning `OSError` aborting the batch and its levers (C-15) | low | mitigate | CLOSED | ap:698-712 (`plan_removal` inside the per-tool `try`); `tests/test_app.py::test_perform_uninstall_a_planning_error_does_not_stop_the_rest` |
| T-21-R05 | Tampering | double lock take released by one `end_mutation` (C-30) | low | mitigate | CLOSED | wa:2736-2741 (raises `RuntimeError`, which survives `-O`, unlike an assert); `sf::test_a_held_lock_is_never_taken_twice` |
| T-21-R06 | DoS | audit worker crash killing the app (C-13) | low | mitigate | CLOSED | wa:883 (`exit_on_error=False`); wa:909-912 (`finally` post); `sf::test_an_unexpected_audit_error_does_not_kill_the_app` |
| T-21-R07 | Tampering | modal opened before the lock refusal (C-17) | low | mitigate | CLOSED | Refuse before the modal: wa:1462, wa:2375, wa:2432. Re-check at the mutation point: wa:1505, wa:2409, wa:2448. Tests: `sf::test_uninstall_enter_is_refused_before_the_confirm_modal`, `sf::test_t_and_m_are_refused_before_their_picker` |
| T-21-R08 | Spoofing | unreachable user manager read as DRIFT (C-19) | medium | mitigate | CLOSED | po:1394-1400 (`UNAVAILABLE` raises `OSError`, so the read is a failure and the cell is blank); `tests/test_systemd_daemon.py::test_an_unreachable_user_manager_is_a_failed_read_not_drift` |
| T-21-R09 | DoS | `UnicodeDecodeError` escaping `run_live` on the loop (C-20) | low | mitigate | CLOSED | uc:55 (`UnicodeDecodeError` is in the caught tuple); `sf::test_an_undecodable_policy_read_shows_the_error` |
| T-21-R10 | Spoofing | manager label on a row that removes installer artifacts (C-23) | medium | mitigate | CLOSED | vs:1943-1944 (REMOVABLE reads `installer`, proven by receipt or layout); vs:1965-1968 (the active manager copy is named only in the detail); `tv::test_a_removable_row_names_the_installer_as_its_owner` |
| T-21-R11 | Spoofing | stale Doctor evidence keeping a repaired tool BROKEN (C-09) | medium | mitigate | CLOSED | vs:1243-1245 (`invalidate` clears `_evidence`); vs:1223-1224 (an audit epoch older than the current one is dropped); wa:959 (the epoch travels from the audit start); `tv::test_invalidate_drops_the_doctor_evidence`; `sf::test_an_audit_that_started_before_a_mutation_records_nothing` |
| T-21-R12 | DoS | queued pass starting after shutdown begins (C-05) | medium | mitigate | CLOSED | wa:3035 (`pending and self.is_running and not self.quitting`); `sf::test_a_queued_pass_does_not_start_once_quit_began` |
| T-21-R13 | Repudiation | failed update reusing the pre-update manager snapshot (C-24) | low | mitigate | CLOSED | installer/update.py:581-590 (invalidates on `updated` and on `failed`); `tests/test_update.py::test_update_service_invalidates_after_a_failed_update` |
| T-21-R14 | Repudiation | quit during a non-removal mutation drops its outcome, exit 0 (C-25) | low | accept | CLOSED | AR-21-03 |
| T-21-R15 | Repudiation | missing rows hide `remove it yourself` leftovers (C-27) | low | accept | CLOSED | AR-21-04 |
| T-21-R16 | Spoofing | overlapping timer-cache probes storing the older answer (C-22) | low | accept | CLOSED | AR-21-05 |

---

## Accepted Risks Log

| Risk ID | Threat | Rationale | Source |
|---------|--------|-----------|--------|
| AR-21-01 | T-21-29 | The evidence store lives in this process only. It is written on the event loop through `record_evidence` under the service lock (vs:1222). The smoke argv comes from the registry, not from user input. | 21-19 |
| AR-21-02 | T-21-SC | No dependency was added or changed. In `git diff 390f464..HEAD -- pyproject.toml uv.lock`, `uv.lock` is unchanged and `pyproject.toml` gains only `faulthandler_timeout = 120` (pytest config, C-01). | every plan |
| AR-21-03 | T-21-R14 | The behavior predates this phase: `390f464` exited at once for every mutation. The user decided to backlog it. The exit code after a cut removal also stays 0. | RUN-LEDGER.md:221, :229; 21-REVIEW-FIX.md C-25 |
| AR-21-04 | T-21-R15 | The behavior predates this phase, and the fix changes UI-SPEC copy. The user decided to backlog it. Nothing is deleted on this path; the files only go unmentioned. | RUN-LEDGER.md:221; 21-REVIEW-FIX.md C-27 |
| AR-21-05 | T-21-R16 | A pre-existing mechanism, rated PARTIAL. Poisoning it needs an external state change inside the overlap, and `STATE_CACHE_TTL = 5.0` bounds the window. Backlogged. | RUN-LEDGER.md:220; 21-REVIEW-FIX.md C-22 |

---

## Open Threats

### Blocking (severity >= high)

None.

### Non-blocking (severity below high)

| Threat ID | Category | Severity | Mitigation Expected | Files Searched |
|-----------|----------|----------|---------------------|----------------|
| T-21-52 | Spoofing | medium | `refresh_daemon_state` should supersede any in-flight job read on every completion. Today it advances the generation only through `_start_job_state_read()` at wa:2267. The early return at wa:2253-2254 (`live is None` and `policy.is_active is not None`) skips it. Fix: `self._job_state_generation += 1` before the early returns, or call `_start_job_state_read()` there, plus a `[daemon_default]` test case where the worker's `live` is None. | installer/wizard_app.py:2232-2268, :1878-1905; tests/test_screen_family.py:2529-2600 |

---

## Residuals and Notes (no register change)

- **Sudo.** Phase 21 adds no `sudo`, `pkexec` or `doas`: `git diff 390f464..HEAD -- installer setup.py` adds none. The native `_dnf`/`_apt`/`_pacman` executors (installer/executors.py:448-457) still build `sudo` argv. They date from 2026-06-08 (eff6b5c) and are reachable through resolve.py:23-25 / :75-78 on mutable Fedora/Debian/Arch. This is the Phase 20 accepted item OC-01 -> LIFE-02. The plan path is pinned by `test_plan.py::test_no_sudo_argv_on_the_plan_path`, so it is not a Phase 21 regression. It still conflicts with AGENTS.md "Zero sudo", so it should stay tracked under LIFE-02.
- **C-26 forced exit.** A second `ctrl+c` can leave a partly deleted tree; the cut message says so. Receipts and rc files cannot be half-written (atomic writes). A dir is either captured in its quarantine sibling or untouched. The receipt is removed only after every proven path is gone.
- **The removal proof holds end to end.**
  - Row paths come only from a published REMOVABLE state (wa:1136-1138).
  - The delete re-proves per tool with `verify=True` (un:315).
  - A path outside the tool's fresh receipt or layout plan is refused, never deleted (un:317-322).
  - The type that proved a path picks the operation: only a `dir` is removed recursively (un:286-297).
- **Plain-text rendering.**
  - Status lines use `Text` (uc:86).
  - The Uninstall detail is sanitized (wa:1153, :1191) and rendered with `detail_is_markup=False` (wa:1316, tb:392).
  - Doctor findings are sanitized and appended as `Text` (wa:639).

---

## Unregistered Flags

- No 21-NN-SUMMARY.md `## Threat Flags` section lists new surface. All of them say "None", or map only to registered ids (21-03 -> T-21-05, 21-12 -> T-21-18/19/35/36/49, 21-15 -> T-21-25/26/51/59).
- **WARNING (auditor-found, unregistered, low):** the catalog tiers do not strip terminal control bytes from pnpm smoke reasons.
  - **Where it comes from.** Phase 21 (D-13) merges Doctor smoke evidence into the published `ToolState.reasons` (vs:1824). Each reason is `PNPM_SMOKE_FAILED` with the child's output, which comes from `executors._smoke_reason`; installer/executors.py:79-87 strips whitespace only.
  - **Doctor** passes it through `sanitize_log_line` (T-21-53).
  - **The catalog tier detail** `_health_block` (ct:494) applies only `rich.markup.escape`. That stops markup, but not ESC/OSC bytes: Rich `Text` and Textual 8.2.7 `_strip_control_codes` remove only BEL/BS/VT/FF/CR. Verified: `Text.from_markup(escape('a\x1b[31mb')).plain` keeps `\x1b`.
  - **The catalog `u` refusal** `{tool_id} is broken: {state.reasons[0]}` (ct:651-652) is also not sanitized.
  - **Suggested fix:** sanitize once at the source, in `_record_pnpm_evidence` (wa:948-951) or in `record_evidence`. Add a test that publishes a hostile smoke reason and asserts the catalog detail and the status contain no `\x1b`.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open (blocking) | Open (non-blocking) | Run By |
|------------|---------------|--------|-----------------|---------------------|--------|
| 2026-11-03 | 77 | 76 | 0 | 1 (T-21-52, medium) | gsd-security-auditor (Claude Opus 5.5), ASVS L1, block_on high, range 390f464..68d498d; 117 + 24 + 16 cited test items passed |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (one medium threat open below the block_on threshold)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-11-03
