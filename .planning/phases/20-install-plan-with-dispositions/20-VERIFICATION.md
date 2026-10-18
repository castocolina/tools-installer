---
phase: 20-install-plan-with-dispositions
verified: 2026-10-18T18:30:00Z
status: passed
score: 9/9 must-haves verified
covered_files: [".claude/architecture.md",".planning/phases/20-install-plan-with-dispositions/20-01-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-01-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-02-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-02-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-03-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-03-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-04-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-04-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-05-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-05-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-06-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-06-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-07-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-07-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-08-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-08-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-09-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-09-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-10-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-10-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-11-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-11-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-12-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-12-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-13-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-13-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-14-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-14-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-15-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-15-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-16-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-16-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-17-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-17-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-18-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-18-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-19-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-19-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-20-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-20-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-21-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-21-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-22-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-22-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-23-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-23-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-24-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-24-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-25-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-25-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-26-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-26-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-27-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-27-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-28-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-28-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-29-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-29-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-30-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-30-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-31-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-31-SUMMARY.md","installer/app.py","installer/catalog_tui.py","installer/deps.py","installer/engine.py","installer/execute_screen.py","installer/model.py","installer/post_install.py","installer/prompt.py","installer/receipts.py","installer/registry.toml","installer/render.py","installer/selection.py","installer/session.py","installer/update.py","installer/version_status.py","installer/wizard_app.py","scripts/container-e2e-verify.sh","setup.py","tests/test_app.py","tests/test_execute_screen.py","tests/test_plan.py","tests/test_render.py","tests/test_session.py","tests/test_setup.py","tests/test_update.py","tests/test_wizard_app.py"]
covered_digest: "v3:sha256:86b1bf94740541b85d4242f7b5d0922754d1008abd415c459e71a4f718156c83"
behavior_unverified: 0
overrides_applied: 0
decision_coverage:
  honored: 17
  total: 17
  not_honored: []
human_verification: []
---

# Phase 20: Install plan with dispositions Verification Report

**Phase Goal:** Before anything runs, the user sees what will happen to each selected and dragged tool, and the TUI and headless runs execute that same plan with honest outcomes.
**Verified:** 2026-10-18T18:30:00Z (HEAD 4c44626)
**Status:** passed
**Re-verification:** No. This is the first verification. Two review rounds closed through gap plans 20-20..20-31 before it.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: on every tier the review says missing → "will install"; current → "skipped — already current (r: reinstall)", after `r` → "will be reinstalled"; broken → "will repair"; outdated brew → "will update"; outdated dnf → "skipped — managed by dnf"; a dragged present dependency → "already present" under its dependent (G cases A–I as tests) | ✓ VERIFIED | `installer/session.py` `_row`/`build_plan` (lines 626-805) map each health/owner/direct pair. `WORDS` (134-143) supplies the words. `render.plan_row_text` appends ` (r: reinstall)` from `can_reinstall` (render.py:98), and `display_order` indents dragged rows under their first requester. Tests: `tests/test_plan.py::test_g_probe_cases_on_every_tier` (27 params, A–I × system/user/ai), plus `test_outdated_direct_row_is_will_update_when_the_owner_allows[brew]`, `test_broken_dragged_dependency_is_will_repair_under_its_requester`, `test_dragged_present_dependency_is_skipped_already_present` and `test_dependency_needed_by_two_selected_tools_is_listed_once_under_the_first` |
| 2 | SC2: `a` on an all-installed tier runs nothing, and the summary counts outcomes with the same words as the review | ✓ VERIFIED | `summary_counts`/`review_counts` both read `WORDS`/`RESULT_WORDS` (session.py:203-269). `catalog_tui.py:365` makes unavailable rows non-selectable for space and `a`. Tests: `tests/test_wizard_app.py::test_a_on_an_all_current_tier_starts_nothing_and_summarizes_n_skipped` (real app, `a`+enter, `Summary — 3 skipped`, no install, no PATH wiring, no sync) and `tests/test_plan.py::test_words_cover_every_disposition_and_result` (parity) |
| 3 | SC3: after a run failed/blocked/not-attempted selections stay selected and done/skipped clear; `esc` before start keeps the selection; refreshing rows show "checking…" and Enter waits | ✓ VERIFIED | `retained` (session.py:227) feeds `wizard_app._install_closed` with `intersection_update` (wizard_app.py:2895). A `None` dismiss leaves `_staged` alone. `ExecuteScreen.action_start`/`_await_state`/`on_state_settled` use a wait token (execute_screen.py:508-584). Behavior tests (all passed in the HEAD suite run): `test_mixed_run_keeps_only_the_failing_blocked_and_manual_rows_selected`, `test_a_worker_crash_marks_the_rest_not_attempted_and_keeps_them_selected`, `test_install_closed_keeps_exactly_the_retained_rows_selected`, `test_escape_before_start_leaves_the_selection_untouched`, `test_enter_with_a_held_refresh_waits_and_starts_nothing`, `test_releasing_the_refresh_rebuilds_the_plan_and_starts_the_run`, `test_esc_during_the_wait_cancels_it_and_keeps_the_selection`, `test_a_late_publication_after_esc_starts_nothing` |
| 4 | SC4: headless `--all --yes` uses the same plan and engine; an outdated tool is updated with exit 0; a failed row exits 1 | ✓ VERIFIED | `app.run_wizard` (app.py:98-171) calls `build_plan(..., reinstall=frozenset())`, `render_plan`, `Run this plan?` unless `--yes`, `execute_plan` and `render_run_report`. `setup.py:1550` sets the exit code from `exit_code(outcomes)` or a run-level PATH/verify error (L-20-08). Tests: `tests/test_app.py::test_all_yes_updates_an_outdated_brew_tool_and_exits_zero`, `test_an_injected_failing_row_exits_one`, `test_a_blocked_row_plus_a_done_row_exits_zero`, `test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped`, and `tests/test_setup.py::test_headless_main_builds_services_once_and_exits_on_outcomes`. The container e2e at 3c74d96 printed `1 updated, 78 skipped, 2 blocked, 8 manual` with rc 0 on the rerun (orchestrator evidence) |
| 5 | SC5: no screen promises an off-policy migration ("moving it there") | ✓ VERIFIED | `grep -rn "moving it there" installer/` finds nothing. Off-policy copy names both owners: catalog_tui.py:811, update.py:340, session.py:622. Guard: `tests/test_update.py` (line ~1256, literal grep over `installer/`) and `tests/test_plan.py::test_off_policy_outdated_row_with_unknown_declared_manager_names_only_the_real_owner` |
| 6 | Goal: one plan, one engine and one vocabulary for the TUI and headless routes | ✓ VERIFIED | `execute_screen._replan` and `app.run_wizard` both call `session.build_plan`. `ExecuteScreen._execute_worker` (execute_screen.py:611-693) and `run_wizard` both call `session.execute_plan`. `render.py` imports its words only from `session` (`WORDS`, `RESULT_WORDS`). The legacy paths are gone: no `installer/audit.py`, and no `run_installs`, `summarize`, `class Summary`, `reapply_post_install` or `render_audit` under `installer/` or `setup.py`. Test: `test_a_and_enter_use_the_same_plan_order_as_the_headless_route` |
| 7 | L-20-10: the pre-confirmation refresh writes nothing on the headless route; the TUI consent boundary is documented in `.claude/architecture.md` "Phase 20" | ✓ VERIFIED | `run_wizard` calls `refresh.hold_writes()` before the pass and `commit_writes()` only after consent (app.py:117-149). The service queues cache saves, receipt retirement and adoption through `_write_or_queue` and `_pending_writes` (version_status.py:957-988, 1331-1403). The architecture.md section at line 1112 states the route-specific boundary. Tests: `tests/test_app.py::test_run_wizard_commits_held_writes_only_after_consent`, `tests/test_version_status.py::test_a_declined_headless_plan_retires_nothing_and_saves_no_cache`, `test_a_declined_headless_plan_adopts_nothing`, `test_a_held_adoption_whose_file_changed_before_consent_is_printed_not_written` |
| 8 | L-20-11: oh-my-zsh health ignores the login shell; the chsh handoff shows on install and on `r` reinstall | ✓ VERIFIED | `version_status.py` never reads `$SHELL`. `status.is_default_shell` is a display hint only. The engine skips a refusing-existing installer on an explicit repair/reinstall and still dispatches the reviewed post-install handoff (20-26). Tests: `tests/test_engine.py::test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair`, `tests/test_execute_screen.py::test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff`, `tests/test_engine.py::test_login_shell_action_dispatches_reviewed_instructions_after_oh_my_zsh_install`, `tests/test_app.py::test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed` |
| 9 | PLAN-03/D-06: a misconfigured direct row runs its typed `ConfigStep`s; with no executable step it is blocked (L-20-04); a sudo-needing repair is blocked | ✓ VERIFIED | `_run_step` dispatches all eight `ConfigStepKind`s and refuses an unknown kind (session.py:363-418). `_run_reconfigure` stops at the first failure. `_row` sends MISCONFIGURED without steps to BLOCKED and BROKEN with an `UNMANAGEABLE_OWNERS` owner to BLOCKED. Tests: `test_misconfigured_direct_row_with_steps_is_will_reconfigure_listing_them`, `test_misconfigured_direct_row_without_steps_is_blocked_with_the_reason`, `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired`, `test_no_sudo_argv_on_the_plan_path`, `tests/test_session.py::test_each_config_step_kind_dispatches` |

**Score:** 9/9 truths verified (0 present-but-behavior-unverified)

### Prohibitions (SPEC must-NOT; all test-tier with wired enforcement)

| Prohibition | Status | Enforcement evidence |
|-------------|--------|----------------------|
| MUST NOT reinstall a current tool unless `r` was pressed (`a` and `--yes` never do) | ✓ VERIFIED | `run_wizard` passes `reinstall=frozenset()`. `_row` gives REINSTALL only for ids in the screen's `_reinstall` set. Tests: `test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped`, `test_a_on_an_all_current_tier_starts_nothing_and_summarizes_n_skipped`, `test_reinstall_requires_the_id_in_the_reinstall_set` |
| MUST NOT start the engine on state from an older generation | ✓ VERIFIED | `execute_plan` raises on a WAIT row (session.py:460). The wait token ignores a stale publication. Tests: `test_execute_plan_refuses_a_plan_with_a_wait_row`, `test_a_late_publication_after_esc_starts_nothing`, `test_enter_with_a_held_refresh_waits_and_starts_nothing` |
| MUST NOT escalate privileges for a repair or update | ✓ VERIFIED | BLOCKED via `UNMANAGEABLE_OWNERS` and `update_refusal`. `test_no_sudo_argv_on_the_plan_path`, `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired` |
| MUST NOT show a migration promise | ✓ VERIFIED | Literal grep test in `tests/test_update.py` |

### Required Artifacts

`gsd-tools query verify.artifacts` ran over all 31 plans: every plan exited 0 and every declared artifact passed (existence + substance). The core artifacts:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/session.py` | `Disposition`, `PlanRow`, `WORDS`/`RESULT_WORDS`, `build_plan`, `execute_plan`, `exit_code`/`retained`/`ran_anything`/`summary_counts` | ✓ VERIFIED | 805 lines, substantive, imported by render/app/execute_screen/wizard_app/setup |
| `installer/render.py` | `render_plan`, `render_run_summary`, `render_run_report` | ✓ VERIFIED | Called from `app.run_wizard` and `ExecuteScreen` |
| `installer/execute_screen.py` | Review on `OptionList`, `r` toggle, wait-for-state, worker on `execute_plan` | ✓ VERIFIED | Pushed by `UnifiedApp.on_catalog_screen_decided` |
| `installer/app.py` | Headless `run_wizard` on the same plan and engine | ✓ VERIFIED | Called by `setup.main` headless route (setup.py:1513) |
| `installer/version_status.py` | `hold_writes`/`commit_writes`, `HEALTH_MARKS`, `UNPROVEN_NOTE` rewording | ✓ VERIFIED | Wired from `run_wizard` |
| `scripts/container-e2e-verify.sh` | `Summary —` parser, install-step gate, PATH-error gate | ✓ VERIFIED | Pinned by `tests/test_container_e2e_receipts.py` |
| `.claude/architecture.md` | "Phase 20: one install plan, one engine, one vocabulary" | ✓ VERIFIED | Line 1112, includes the L-20-10 boundary |

### Key Link Verification

`verify.key-links` passed links in 12 plans. It reported 26 links "Pattern not verified (not valid RE2 syntax)" and 2 "not found" (20-12 `refresh(self._inputs.catalog)`, 20-13 `reinstall=frozenset(self._reinstall)`). The two "not found" patterns contain literal parentheses that the regex engine reads as groups, so these are tool false negatives. I checked every link by hand:

| From | To | Via | Status |
|------|----|-----|--------|
| execute_screen.py | session.py | `build_plan(... reinstall=frozenset(self._reinstall))` (l.435-441), `execute_plan(rows, RunContext(...))` (l.649) | WIRED |
| execute_screen.py | version_status.py | `self._inputs.version_refresh.refresh(self._inputs.catalog)` + `refresh_skills` in `_wait_worker` (l.548-551) | WIRED |
| app.py | session.py | `build_plan`, `execute_plan` (l.128, 169) | WIRED |
| app.py | render.py | `render_plan`, `render_run_summary`, `render_run_report` | WIRED |
| app.py | version_status.py | `hold_writes`/`commit_writes` (l.117, 148) | WIRED |
| setup.py | app.py / session.py | `run_wizard(...)`, `exit_code`, `ran_anything` (l.1513-1550); `_session_exit_code` → `exit_code(app.outcomes.values())` (l.1309) | WIRED |
| wizard_app.py | session.py | `retained`, `ran_anything` in `_install_closed` (l.2895, 2920) | WIRED |
| render.py | session.py | imports `WORDS`, `RESULT_WORDS`, `review_counts`, `summary_counts` | WIRED |
| session.py | update.py | `update_refusal` in `_row`; `UpdateService.begin/run/end` in `execute_plan` | WIRED |
| session.py | executors.py / skill_lifecycle.py | `executors.execute` (pnpm group), `perform_action` (skill install) in `_run_step` | WIRED |
| session.py | deps.py | `resolve_dependencies` → `Resolution.closure/blocked/requested_by` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| ExecuteScreen review rows | `self._rows` | `build_plan(..., version_refresh.state_of, ...)`, the published `ToolState` | Yes | ✓ FLOWING |
| ExecuteScreen finished rows/head | `message.outcomes` | `execute_plan` → `RowOutcome` per row | Yes | ✓ FLOWING |
| Headless plan/summary | `rows`, `outcomes` | same `build_plan`/`execute_plan` | Yes | ✓ FLOWING |
| Process exit code | `exit_code(outcomes)` | outcome list (TUI `app.outcomes`, headless `run_wizard` return) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Whole test suite at HEAD (run once) | `make test` | `4923 passed, 4 skipped`, coverage 96.03%, rc 0 | ✓ PASS |
| Quality gate | `make validate` | ruff, format, pyright 0 errors, bandit, vulture, shellcheck; rc 0 | ✓ PASS |
| No migration promise | `grep -rn "moving it there" installer/` | no matches | ✓ PASS |
| Legacy paths deleted | `ls installer/audit.py`; grep `run_installs|summarize|class Summary|reapply_post_install|render_audit` | absent | ✓ PASS |
| TUI review, `r` refusal, esc, q (orchestrator, tmux 80x20, NO_COLOR, scratch HOME, 4c44626) | navigation only | `Install plan — 1 will install`; `colima: r needs a current tool this installer owns.`; esc returns with nothing run; receipts dir empty | ✓ PASS |
| Real container install/rerun/uninstall (orchestrator, `make e2e` at 3c74d96) | `make e2e` | pass 1 `74 installed, 5 skipped, 2 blocked, 8 manual`, 0 failed; rerun `1 updated, 78 skipped, 2 blocked, 8 manual`; rc 0 | ✓ PASS (pre-20-30/31) |

### Probe Execution

Step 7c skipped: no probe is declared by any PLAN/SUMMARY, and no `scripts/*/tests/probe-*.sh` exists.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PLAN-01 | 20-01, 04, 05, 06, 18, 22 | Review lists every selected and dragged tool with disposition and reason | ✓ SATISFIED | Truths 1, 6 |
| PLAN-02 | 20-04, 13, 26 | Current installer-owned tool skipped unless `r` → "will be reinstalled" | ✓ SATISFIED | Truths 1, 8; `test_r_then_enter_reinstalls_with_repair`, `test_reinstall_set_is_ignored_for_a_foreign_owned_row` |
| PLAN-03 | 20-05, 08 | Broken → repair, misconfigured → reconfigure, incl. dragged deps | ✓ SATISFIED | Truths 1, 9 |
| PLAN-04 | 20-07, 09, 25 | Summary counts in the review's words | ✓ SATISFIED | Truth 2 |
| PLAN-05 | 20-10, 18 | Retained selection after a run; `esc` keeps it | ✓ SATISFIED | Truth 3 |
| PLAN-06 | 20-11, 19, 21 | Headless same plan/engine; exit code from outcomes | ✓ SATISFIED | Truth 4 |
| PLAN-07 | 20-12, 20 | "checking…" + Enter waits | ✓ SATISFIED | Truth 3 |
| PLAN-08 | 20-02 | No off-policy migration promise | ✓ SATISFIED | Truth 5 |

No orphaned requirements: REQUIREMENTS.md maps exactly PLAN-01..08 to Phase 20, and all appear in plan frontmatter. REQUIREMENTS.md still shows them as `Pending`/`[ ]`. That bookkeeping belongs to phase close, not to this verification.

### Decision Coverage

`check.decision-coverage-verify`: all 17 trackable CONTEXT.md decisions are honored by shipped artifacts. L-20-10 and L-20-11 (RUN-LEDGER) are covered by Truths 7 and 8.

### Test Quality Audit

| Test File | Linked Req | Skipped | Circular | Assertion Level | Verdict |
|-----------|-----------|---------|----------|-----------------|---------|
| tests/test_plan.py | PLAN-01/02/03/08 | 0 | No | Value (exact tuples of id/disposition/reason) | OK |
| tests/test_session.py | PLAN-04/05/06 | 0 | No | Value + behavioral | OK |
| tests/test_execute_screen.py | PLAN-02/05/07 | 0 | No | Behavioral (pilot, held refresh) | OK |
| tests/test_wizard_app.py | PLAN-05, R9 | 0 | No | Behavioral (real app) | OK |
| tests/test_app.py | PLAN-06, L-20-10/11 | 1 `skipif(no bash)`, unrelated | No | Value + behavioral | OK |

Disabled tests on requirements: 0. Circular patterns: 0. Insufficient assertions: 0.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/placeholder markers in the 18 production files the phase touched (installer/*, setup.py, scripts/container-e2e-verify.sh).

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (verify.key-links tool) | — | RE2 cannot evaluate 26 plan patterns; 2 literal-paren patterns fail | ℹ️ Info | Tooling only; every link was checked by hand above |

### Accepted / deferred (not gaps, per review consolidation and RUN-LEDGER)

- OC-01: native executors run sudo. Belongs to LIFE-02 in a later phase. Phase 20's plan path blocks sudo-needing rows (pinned by `test_no_sudo_argv_on_the_plan_path`).
- OC2-01: the TUI catalog refresh writes before the review. This is the documented L-20-10 TUI boundary (architecture.md "Phase 20").
- OC-06 residual: PATH wiring runs after a failed row. It is idempotent.
- sd 1.0.0 → v1.1.0 install/version-check disagreement in the e2e: registry/update debt, not Phase 20.

### Human Verification Required

None. The user-facing review/wait/`r`/esc flows are pinned by Textual pilot tests at 80x20. The orchestrator also exercised them manually in tmux at HEAD.

### Gaps Summary

None. The codebase delivers the goal: one `build_plan` gives one disposition and one reason per selected or dragged row. Both routes render it from the one `WORDS` table and run it through the one `execute_plan`. The exit code, retained selection and post-run effects are all derived from the `RowOutcome` list.

Info: the container e2e at HEAD (after 20-30/20-31) was still running when this report was written. The deltas since the passing 3c74d96 e2e are in `execute_plan` prerequisite gating, the adoption commit and the e2e PATH-error gate. They are covered by new unit tests in `tests/test_session.py`, `tests/test_version_status.py` and `tests/test_container_e2e_receipts.py`, all green in this run. A red e2e at HEAD would reopen this verification.

---

_Verified: 2026-10-18T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
