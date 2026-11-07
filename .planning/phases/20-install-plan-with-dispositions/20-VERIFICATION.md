---
phase: 20-install-plan-with-dispositions
verified: 2026-11-07T10:13:39Z
status: passed
score: 9/9 must-haves verified
covered_files: [".claude/architecture.md",".planning/phases/20-install-plan-with-dispositions/20-01-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-01-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-02-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-02-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-03-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-03-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-04-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-04-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-05-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-05-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-06-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-06-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-07-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-07-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-08-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-08-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-09-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-09-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-10-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-10-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-11-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-11-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-12-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-12-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-13-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-13-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-14-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-14-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-15-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-15-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-16-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-16-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-17-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-17-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-18-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-18-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-19-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-19-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-20-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-20-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-21-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-21-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-22-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-22-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-23-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-23-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-24-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-24-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-25-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-25-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-26-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-26-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-27-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-27-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-28-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-28-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-29-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-29-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-30-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-30-SUMMARY.md",".planning/phases/20-install-plan-with-dispositions/20-31-PLAN.md",".planning/phases/20-install-plan-with-dispositions/20-31-SUMMARY.md","installer/app.py","installer/catalog_tui.py","installer/deps.py","installer/engine.py","installer/execute_screen.py","installer/model.py","installer/post_install.py","installer/prompt.py","installer/receipts.py","installer/registry.toml","installer/render.py","installer/selection.py","installer/session.py","installer/update.py","installer/version_status.py","installer/wizard_app.py","scripts/container-e2e-verify.sh","setup.py","tests/test_app.py","tests/test_engine.py","tests/test_execute_screen.py","tests/test_plan.py","tests/test_render.py","tests/test_session.py","tests/test_setup.py","tests/test_update.py","tests/test_version_status.py","tests/test_wizard_app.py"]
covered_digest: "v4:sha256:ea704e63b5a535cb22d40826fd6412e595ecf3e0e45dbd8eca26ed1c91837865"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: passed
  previous_score: 9/9
  reason: "Stale fingerprint: covered files changed in phases 21-23 (510 commits since 4c44626)"
  gaps_closed: []
  gaps_remaining: []
  regressions: []
decision_coverage:
  honored: 17
  total: 17
  not_honored: []
human_verification: []
---

# Phase 20: Install plan with dispositions Verification Report

**Phase Goal:** Before anything runs, the user sees what will happen to each selected and dragged tool, and the TUI and headless runs execute that same plan with honest outcomes.
**Verified:** 2026-11-07T10:13:39Z (HEAD 18ab7f2)
**Status:** passed
**Re-verification:** Yes. The previous report (2026-10-18, HEAD 4c44626) passed 9/9 but went stale: phases 21-23 refactored most covered files (45 production files changed, +8088/-2979). Every truth below was re-checked against the code at HEAD, and its behavior tests were re-run. Line numbers are from HEAD.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence at HEAD |
|---|-------|--------|------------------|
| 1 | SC1: on every tier the review says missing → "will install"; current → "skipped — already current (r: reinstall)", after `r` → "will be reinstalled"; broken → "will repair"; outdated brew → "will update"; outdated dnf → "skipped — managed by dnf"; a dragged present dependency → "already present" under its dependent (G cases A–I as tests) | ✓ VERIFIED | `session._row` (session.py:903-1006) maps each health/owner/direct pair: MISSING→INSTALL, BROKEN→REPAIR (BLOCKED for `UNMANAGEABLE_OWNERS`), OUTDATED→UPDATE or SKIP "managed by {label}" via `update_refusal`, OK+requester→SKIP "already present", OK+installer→SKIP "already current" with `can_reinstall`, REINSTALL only when `tool.id in reinstall`. `WORDS` (session.py:154-165). `render.plan_row_text` appends ` (r: reinstall)` (render.py:104-105) and indents dragged rows. Tests passed at HEAD: `test_g_probe_cases_on_every_tier` (A–I × 3 tiers), `test_outdated_direct_row_is_will_update_when_the_owner_allows`, `test_broken_dragged_dependency_is_will_repair_under_its_requester`, `test_dragged_present_dependency_is_skipped_already_present`, `test_dependency_needed_by_two_selected_tools_is_listed_once_under_the_first` |
| 2 | SC2: `a` on an all-installed tier runs nothing, and the summary counts outcomes with the same words as the review | ✓ VERIFIED | `review_counts` (session.py:246) and `summary_counts` (session.py:290) both read `WORDS`/`RESULT_WORDS`. Tests passed: `tests/test_wizard_app.py::test_a_on_an_all_current_tier_starts_nothing_and_summarizes_n_skipped`, `tests/test_plan.py::test_words_cover_every_disposition_and_result` |
| 3 | SC3: after a run failed/blocked/not-attempted selections stay selected and done/skipped clear; `esc` before start keeps the selection; refreshing rows show "checking…" and Enter waits | ✓ VERIFIED | `retained` keeps `_FAILURE ∪ {blocked, manual}` (session.py:252-266). `wizard_app._install_closed` does `intersection_update(retained(result))` and leaves the selection alone on `None` (wizard_app.py:3611-3616). WAIT word is "checking…" (session.py:155). `ExecuteScreen.action_start` / `_await_state` / `on_state_settled` (execute_screen.py:589-660) wait on a token through `UnifiedApp.await_publication` (wizard_app.py:3286), which joins the one refresh owner (refresh then `refresh_skills`, settle in `finally`, wizard_app.py:3296-3317). Tests passed: `test_mixed_run_keeps_only_the_failing_blocked_and_manual_rows_selected`, `test_a_worker_crash_marks_the_rest_not_attempted_and_keeps_them_selected`, `test_install_closed_keeps_exactly_the_retained_rows_selected`, `test_escape_before_start_leaves_the_selection_untouched`, `test_enter_with_a_held_refresh_waits_and_starts_nothing`, `test_releasing_the_refresh_rebuilds_the_plan_and_starts_the_run`, `test_esc_during_the_wait_cancels_it_and_keeps_the_selection`, `test_a_late_publication_after_esc_starts_nothing`, `test_enter_settles_a_pack_selected_before_its_host_check`, `test_a_refresh_raising_value_error_settles_with_the_error_and_enter_retries`, `test_a_late_settle_never_repaints_a_finished_run` |
| 4 | SC4: headless `--all --yes` uses the same plan and engine; an outdated tool is updated with exit 0; a failed row exits 1 | ✓ VERIFIED | `app.run_wizard` calls `hold_writes` (app.py:144), `refresh_skills` (147), `build_plan(..., reinstall=frozenset())` (154-159), `render_plan` (169), `Run this plan?` unless `--yes` (171), `commit_writes` after consent (178), `execute_plan` (199), `render_run_report` (200). `setup.py:1504` sets the code from `exit_code(outcomes)` or a run-level PATH/verify error. Tests passed: `test_all_yes_updates_an_outdated_brew_tool_and_exits_zero`, `test_an_injected_failing_row_exits_one`, `test_a_blocked_row_plus_a_done_row_exits_zero`, `test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped`, `test_headless_all_settles_skill_packs_before_planning`, `tests/test_setup.py::test_headless_main_builds_services_once_and_exits_on_outcomes` |
| 5 | SC5: no screen promises an off-policy migration ("moving it there") | ✓ VERIFIED | `grep -rn "moving it there" installer/ setup.py`: no matches. Guard test `tests/test_update.py::test_no_migration_promise_anywhere_under_installer` (line 1416) passed. `test_off_policy_outdated_row_with_unknown_declared_manager_names_only_the_real_owner` passed |
| 6 | Goal: one plan, one engine and one vocabulary for the TUI and headless routes | ✓ VERIFIED | `execute_screen` (build_plan at 465-470, execute_plan at 720) and `app.run_wizard` (154, 199) both call `session.build_plan` / `session.execute_plan`. `render.py` takes its words from `session`. Legacy paths still absent: no `installer/audit.py`; no `run_installs`, `summarize`, `class Summary`, `reapply_post_install` or `render_audit` under `installer/` or `setup.py`. Test passed: `test_a_and_enter_use_the_same_plan_order_as_the_headless_route` |
| 7 | L-20-10: the pre-confirmation refresh writes nothing on the headless route; the TUI consent boundary is documented in `.claude/architecture.md` "Phase 20" | ✓ VERIFIED | `hold_writes`/`commit_writes` around the consent prompt (app.py:144-178). `.claude/architecture.md:1113` "Phase 20: one install plan, one engine, one vocabulary". Tests passed: `test_run_wizard_commits_held_writes_only_after_consent`, `test_a_declined_headless_plan_retires_nothing_and_saves_no_cache`, `test_a_declined_headless_plan_adopts_nothing`, `test_a_held_adoption_whose_file_changed_before_consent_is_printed_not_written` |
| 8 | L-20-11: oh-my-zsh health ignores the login shell; the chsh handoff shows on install and on `r` reinstall | ✓ VERIFIED | Tests passed: `tests/test_engine.py::test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair`, `tests/test_execute_screen.py::test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff`, `tests/test_engine.py::test_login_shell_action_dispatches_reviewed_instructions_after_oh_my_zsh_install`, `tests/test_app.py::test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed` |
| 9 | PLAN-03/D-06: a misconfigured direct row runs its typed `ConfigStep`s; with no executable step it is blocked (L-20-04); a sudo-needing repair is blocked | ✓ VERIFIED | `_row` MISCONFIGURED branch (session.py:965-974): RECONFIGURE with `steps=state.unconfigured`, else BLOCKED; dragged misconfigured → SKIP. BROKEN + `UNMANAGEABLE_OWNERS` → BLOCKED "repair needs sudo (never run here)" (955-960). Tests passed: `test_misconfigured_direct_row_with_steps_is_will_reconfigure_listing_them`, `test_misconfigured_direct_row_without_steps_is_blocked_with_the_reason`, `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired`, `test_no_sudo_argv_on_the_plan_path`, `tests/test_session.py::test_each_config_step_kind_dispatches` |

**Score:** 9/9 truths verified (0 present-but-behavior-unverified)

### Prohibitions (SPEC must-NOT; test-tier, enforcement wired)

| Prohibition | Status | Enforcement evidence at HEAD |
|-------------|--------|------------------------------|
| MUST NOT reinstall a current tool unless `r` was pressed (`a` and `--yes` never do) | ✓ VERIFIED | `run_wizard` passes `reinstall=frozenset()` (app.py:159); `_row` gives REINSTALL only for `tool.id in reinstall` (session.py:994). Tests passed: `test_reinstall_requires_the_id_in_the_reinstall_set`, `test_reinstall_set_is_ignored_for_a_foreign_owned_row`, `test_all_yes_on_an_all_current_host_runs_nothing_and_exits_zero_shaped` |
| MUST NOT start the engine on state from an older generation | ✓ VERIFIED | Wait token check in `on_state_settled` (execute_screen.py:627). Tests passed: `test_execute_plan_refuses_a_plan_with_a_wait_row`, `test_a_late_publication_after_esc_starts_nothing`, `test_enter_with_a_held_refresh_waits_and_starts_nothing` |
| MUST NOT escalate privileges for a repair or update | ✓ VERIFIED | `UNMANAGEABLE_OWNERS` → BLOCKED; `update_refusal` → SKIP. `test_no_sudo_argv_on_the_plan_path`, `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired` passed |
| MUST NOT show a migration promise | ✓ VERIFIED | `test_no_migration_promise_anywhere_under_installer` passed |

### Required Artifacts

`gsd-tools query verify.artifacts` over all 31 plans at HEAD: 30 plans exit 0 with every artifact passing. 20-20 exits 1 on one artifact:

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/session.py` | `Disposition`, `PlanRow`, `WORDS`/`RESULT_WORDS`, `build_plan`, `execute_plan`, `exit_code`/`retained`/`ran_anything`/`summary_counts` | ✓ VERIFIED | Present, substantive, imported by render/app/execute_screen/wizard_app/setup |
| `installer/render.py` | `render_plan`, `render_run_summary`, `render_run_report` | ✓ VERIFIED | Called from `app.run_wizard` and `ExecuteScreen` |
| `installer/execute_screen.py` | Review, `r` toggle, wait-for-state, worker on `execute_plan` | ✓ VERIFIED | 20-20 literal `refresh_skills(` no longer in this file (see below) |
| `installer/app.py` | Headless `run_wizard` on the same plan and engine | ✓ VERIFIED | Called by `setup.main` (setup.py:1468) |
| `installer/version_status.py` | `hold_writes`/`commit_writes`, `refresh_skills` | ✓ VERIFIED | Wired from `run_wizard` and `UnifiedApp._refresh_worker` |
| `scripts/container-e2e-verify.sh` | `Summary —` parser and gates | ✓ VERIFIED | Present |
| `.claude/architecture.md` | "Phase 20" section | ✓ VERIFIED | Line 1113 |

20-20 `installer/execute_screen.py contains "refresh_skills("`: a stale literal, not a regression. Commit 75b6366 `refactor(21-10): the review waits on the app refresh owner` moved the wait's refresh from `ExecuteScreen._wait_worker` into `UnifiedApp.await_publication`/`_refresh_worker` (wizard_app.py:3286-3317). That worker still runs `refresh` and then `refresh_skills` and settles in `finally`. So the 20-20 truths (J1 TUI half, J5) still hold, and their tests pass at HEAD: `test_enter_settles_a_pack_selected_before_its_host_check`, `test_a_refresh_raising_value_error_settles_with_the_error_and_enter_retries`, `test_a_late_settle_never_repaints_a_finished_run`. The 20-20 key link `execute_screen.py → version_status.py via refresh_skills(` now runs `execute_screen.py → wizard_app.await_publication → version_status.refresh_skills`.

### Key Link Verification (hand-checked at HEAD)

| From | To | Via | Status |
|------|----|-----|--------|
| execute_screen.py | session.py | `build_plan(..., reinstall=frozenset(self._reinstall))` (465-470), `execute_plan` (720), `exit_code` (940) | WIRED |
| execute_screen.py | wizard_app.py → version_status.py | `self.app.await_publication(settled)` (623) → `_refresh_worker` refresh + `refresh_skills` | WIRED (relocated in 21-10) |
| app.py | session.py / render.py / version_status.py | `build_plan`, `execute_plan`, `render_plan`, `render_run_report`, `hold_writes`/`refresh_skills`/`commit_writes` | WIRED |
| setup.py | app.py / session.py | `run_wizard` (1468), `ran_anything` (1483), `exit_code` (1504); `_session_exit_code` → `exit_code(app.outcomes.values())` (1252) | WIRED |
| wizard_app.py | session.py | `retained` (3616), `ran_anything` (3641, 3657, 3723, 3730) | WIRED |
| render.py | session.py | `WORDS`, `RESULT_WORDS`, `review_counts`, `summary_counts` | WIRED |
| session.py | update.py / deps.py | `update_refusal` in `_row`; `resolve_dependencies` in `build_plan` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| ExecuteScreen review rows | `self._rows` | `build_plan(..., state_of, ...)` over published `ToolState` | Yes | ✓ FLOWING |
| ExecuteScreen finished rows/head | outcomes | `execute_plan` → `RowOutcome` | Yes | ✓ FLOWING |
| Headless plan/summary | `rows`, `outcomes` | same `build_plan`/`execute_plan` | Yes | ✓ FLOWING |
| Process exit code | `exit_code(outcomes)` | outcome list | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 39 named Phase 20 behavior tests across 8 files | `uv run pytest -n 4 --no-cov <8 files> -k "<39 names>"` | 84 passed (parametrized), 0 failed | ✓ PASS |
| Skill-pack settle tests (20-20 relocated) | `uv run pytest --no-cov ... -k "<4 names>"` | 4 passed | ✓ PASS |
| Migration-promise guard | `uv run pytest tests/test_update.py -k "moving or migration or promise"` | passed | ✓ PASS |
| Quality gate | `make validate` | ruff, format, pyright 0 errors, bandit, vulture, shellcheck; rc 0 | ✓ PASS |
| Legacy paths deleted | `ls installer/audit.py`; grep legacy symbols | absent | ✓ PASS |

The full suite was not run (another agent was running it). The container e2e was not run (host-mutation rules).

### Probe Execution

Skipped: no PLAN/SUMMARY declares a probe, and no `scripts/*/tests/probe-*.sh` exists.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PLAN-01 | Review lists every selected and dragged tool with disposition and reason | ✓ SATISFIED | Truths 1, 6 |
| PLAN-02 | Current installer-owned tool skipped unless `r` → "will be reinstalled" | ✓ SATISFIED | Truths 1, 8; `test_r_then_enter_reinstalls_with_repair` passed |
| PLAN-03 | Broken → repair, misconfigured → reconfigure, incl. dragged deps | ✓ SATISFIED | Truths 1, 9 |
| PLAN-04 | Summary counts in the review's words | ✓ SATISFIED | Truth 2 |
| PLAN-05 | Retained selection after a run; `esc` keeps it | ✓ SATISFIED | Truth 3 |
| PLAN-06 | Headless same plan/engine; exit code from outcomes | ✓ SATISFIED | Truth 4 |
| PLAN-07 | "checking…" + Enter waits | ✓ SATISFIED | Truth 3 |
| PLAN-08 | No off-policy migration promise | ✓ SATISFIED | Truth 5 |

No orphaned requirements: REQUIREMENTS.md maps exactly PLAN-01..08 to Phase 20. They still show `Pending`/`[ ]` there, which is phase-close bookkeeping, not a verification gap.

### Decision Coverage

`check.decision-coverage-verify <phase> 20-CONTEXT.md` at HEAD: 17/17 trackable decisions honored.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX` in the covered production files at HEAD.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| 20-20-PLAN.md artifact `contains` | — | Literal `refresh_skills(` expected in execute_screen.py; moved to wizard_app.py by 21-10 | ℹ️ Info | Stale plan literal; behavior and tests intact |

### Accepted / deferred (carried forward from the prior report, still valid)

- OC-01: native executors run sudo. Belongs to LIFE-02 in a later phase. The Phase 20 plan path blocks sudo-needing rows (`test_no_sudo_argv_on_the_plan_path` passes).
- OC2-01: the TUI catalog refresh writes before the review. This is the documented L-20-10 TUI boundary (architecture.md "Phase 20").
- OC-06 residual: PATH wiring runs after a failed row. It is idempotent.

### Human Verification Required

None. The review, wait, `r` and esc flows are pinned by Textual pilot tests, and those tests pass at HEAD.

### Gaps Summary

None. At HEAD a single `build_plan` still gives each selected or dragged row one disposition and one reason. Both routes render it from the one `WORDS` table and run it through the one `execute_plan`. Exit code, retained selection and post-run effects come from the `RowOutcome` list. The only drift from the original plans is the 21-10 move of the review's state wait into the app refresh owner. It keeps the behavior, and its tests pass.

---

_Verified: 2026-11-07T10:13:39Z_
_Verifier: Claude (gsd-verifier)_
