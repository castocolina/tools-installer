---
phase: 17-stop-the-bleeding
verified: 2026-10-15T08:38:26Z
status: gaps_found
score: 22/25 must-haves verified
covered_files: [".claude/architecture.md",".planning/phases/17-stop-the-bleeding/17-01-PLAN.md",".planning/phases/17-stop-the-bleeding/17-01-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-02-PLAN.md",".planning/phases/17-stop-the-bleeding/17-02-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-03-PLAN.md",".planning/phases/17-stop-the-bleeding/17-03-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-04-PLAN.md",".planning/phases/17-stop-the-bleeding/17-04-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-05-PLAN.md",".planning/phases/17-stop-the-bleeding/17-05-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-06-PLAN.md",".planning/phases/17-stop-the-bleeding/17-06-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-07-PLAN.md",".planning/phases/17-stop-the-bleeding/17-07-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-08-PLAN.md",".planning/phases/17-stop-the-bleeding/17-08-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-09-PLAN.md",".planning/phases/17-stop-the-bleeding/17-09-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-10-PLAN.md",".planning/phases/17-stop-the-bleeding/17-10-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-11-PLAN.md",".planning/phases/17-stop-the-bleeding/17-11-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-12-PLAN.md",".planning/phases/17-stop-the-bleeding/17-12-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-13-PLAN.md",".planning/phases/17-stop-the-bleeding/17-13-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-14-PLAN.md",".planning/phases/17-stop-the-bleeding/17-14-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-15-PLAN.md",".planning/phases/17-stop-the-bleeding/17-15-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-16-PLAN.md",".planning/phases/17-stop-the-bleeding/17-16-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-17-PLAN.md",".planning/phases/17-stop-the-bleeding/17-17-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-18-PLAN.md",".planning/phases/17-stop-the-bleeding/17-18-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-19-PLAN.md",".planning/phases/17-stop-the-bleeding/17-19-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-20-PLAN.md",".planning/phases/17-stop-the-bleeding/17-20-SUMMARY.md","installer/app.py","installer/apps.py","installer/catalog_tui.py","installer/doctor.py","installer/download.py","installer/execute_screen.py","installer/executors.py","installer/guards.py","installer/guidance.py","installer/model.py","installer/policy.py","installer/postinstall.py","installer/registry.toml","installer/render.py","installer/run.py","installer/session.py","installer/settings.py","installer/tweaks.py","installer/uninstall.py","installer/wizard_app.py","scripts/lib/prune-tmp-common.sh","scripts/prune-tmp-linux.sh","setup.py","tests/conftest.py","tests/test_app.py","tests/test_apps.py","tests/test_atomic.py","tests/test_catalog_tui.py","tests/test_doctor.py","tests/test_download.py","tests/test_engine.py","tests/test_execute_screen.py","tests/test_guards.py","tests/test_guidance.py","tests/test_policies_e2e.py","tests/test_policy.py","tests/test_postinstall.py","tests/test_prune_tmp_linux_sh.py","tests/test_registry.py","tests/test_render.py","tests/test_run.py","tests/test_session.py","tests/test_settings.py","tests/test_setup.py","tests/test_shellrc.py","tests/test_uninstall.py","tests/test_update.py","tests/test_version_status.py","tests/test_wizard_app.py"]
covered_digest: "v3:sha256:737ee12bff14e2cc58a4788993de4531e8308d4e598c225b54050d93ac4b3604"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "17-18 prohibition: MUST NOT skip, xfail or weaken any existing test, and MUST NOT add a new type: ignore / pyright: ignore / noqa"
    status: failed
    reason: "Commit ad63b1f (fix(17-18): removal proof survives loops and is re-checked at deletion time) adds two new `# type: ignore[arg-type]` suppressions. They are not false positives: `_uninstall_kwargs` returns dict[str, object] and the splat into run_uninstall's typed parameters is a real typing gap. The 17-18 SUMMARY claims 'suppression-free tests' (lines 16 and 132), which is false for this commit. It also breaks .claude/python-tooling.md:22 ('Do not add # type: ignore ... Fix the underlying code instead')."
    artifacts:
      - path: "tests/test_app.py"
        issue: "line 3584 `**_uninstall_kwargs(tmp_path, bin_dir, lambda _m: True),  # type: ignore[arg-type]` (git blame: ad63b1fb)"
      - path: "tests/test_app.py"
        issue: "line 3617 `**_uninstall_kwargs(tmp_path, bin_dir, swap_then_confirm),  # type: ignore[arg-type]` (git blame: ad63b1fb)"
      - path: "tests/test_app.py"
        issue: "line 3463 `_uninstall_kwargs(...) -> dict[str, object]` is the root cause; the same helper also carries 4 more ignores from 17-09 (lines 3492, 3521, 3538, 3560; commit 5c559ae)"
    missing:
      - "Type `_uninstall_kwargs` precisely (a TypedDict matching run_uninstall's keyword parameters, or a small frozen dataclass/explicit keyword call) and delete all six `# type: ignore[arg-type]` markers at tests/test_app.py:3492, 3521, 3538, 3560, 3584, 3617; make validate must stay green"
      - "Correct the 17-18 SUMMARY 'suppression-free' claim, or record the fix commit next to it"
human_verification:
  - test: "CI-02: apply branch protection on main once the post-verification main push is green: printf '%s' '<body from 17-13-SUMMARY.md:80>' | gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -"
    expected: "gh api repos/castocolina/tools-installer/branches/main/protection returns required_status_checks with exactly 'validate & test on ubuntu-latest' and 'validate & test on macos-latest', and enforce_admins.enabled false (it returns 404 'Branch not protected' as of this verification)"
    why_human: "A GitHub settings change needs the user's in-the-moment consent (D-17); RUN-LEDGER records CI-02 as 'skip', with the command handed to the user"
  - test: "17-13 backstop truth: after /gsd-verify-work the orchestrator pushes main, watches the CI run for that HEAD, and records both job conclusions under '## Post-verification main push' in 17-13-SUMMARY.md"
    expected: "Both 'validate & test on ubuntu-latest' and 'validate & test on macos-latest' conclude success for the main HEAD that lands; the section no longer reads 'pending: orchestrator (after /gsd-verify-work)'"
    why_human: "Orchestrator-owned step after verification (verification: backstop); it cannot exist at verify time, so 'pending' is the expected state now"
---

# Phase 17: Stop the bleeding Verification Report

**Phase Goal:** No known host hazard can fire on the user's machine, every failed or crashed run says so, and nothing merges to main without a green check on both OSes.
**Verified:** 2026-10-15T08:38:26Z
**Status:** gaps_found
**Re-verification:** No (initial verification)

The product goal is met in code and tests: every SAFE hazard has a fix wired into production paths, and a named behavioral test for each passes on HEAD. The only blocking finding is a test-hygiene prohibition that 17-18 itself declared and then broke: two new `# type: ignore[arg-type]` in tests/test_app.py. Branch protection (CI-02) is not applied. That is an expected user action, recorded under human verification, not a gap.

## Goal Achievement

### Observable Truths: Roadmap Success Criteria (contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | A download/app method with a directory member fails and links nothing; reinstall over a link-to-directory leaves the inner file untouched; installing or updating graphify leaves an empty cwd empty | ✓ VERIFIED | `installer/executors.py:49-64` `link_executable` raises ExecutorError on `not binary.is_file()` before chmod/link. All three sites route through it (`download.py:209,421`, `apps.py:100`); raw installs use `_replace_raw` (`download.py:183,271,304,400`). graphify `[[tool]]` (`registry.toml:1586-1615`) has no `postinstall`; `POSTINSTALL_HOOKS` (`postinstall.py:243-246`) and `POSTINSTALL_HOOK_NAMES` (`model.py:20`) no longer list graphify. Tests pass: `test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical`, `test_github_release_directory_member_falls_through_the_ladder`, `test_install_app_cli_that_is_a_directory_links_nothing`, `test_installing_graphify_runs_no_host_registration` (exact argv `uv tool install graphifyy`, `cwd.iterdir() == []`), `test_updating_graphify_runs_no_host_registration`. Container probe recorded verbatim in 17-05-SUMMARY.md:111-117 |
| SC2 | Neither `--uninstall --yes` nor the TUI deletes the uv ruff symlink, the pip yq file or the shared drawio file, each listed as "remove it yourself"; an injected rc write failure leaves the file intact; `clean_rc_duplicates` refuses a file changed between preview and confirm | ✓ VERIFIED | `plan_removal` is shared by `classify_tools` and `run_uninstall` (key link verified). Tests pass: `test_run_uninstall_deletes_only_proven_artifacts` (removes exactly `{bin/fd, opt/fd}`; ruff/yq/drawio byte-identical and printed), `test_tui_and_cli_delete_the_same_set`, `test_run_uninstall_refuses_paths_changed_since_the_preview`, `test_ban_aliases_write_failure_leaves_the_rc_byte_identical`, `test_clean_rc_duplicates_refuses_a_file_edited_between_preview_and_confirm`, `..._treats_a_trailing_newline_change_as_changed`. guards.py/tweaks.py contain no direct `write_text`/`write_bytes`/`open(...w)` left |
| SC3 | A worker exception shows red "Failed" and exits 1; a failed update exits 1; a /dev/tty vendor script fails fast; a non-UTF-8 settings.json does not crash launch; Enter executes the selection on every route | ✓ VERIFIED | `setup.py:1302-1311` `_session_exit_code` (has_failure or run_in_flight → 1) is used by every route (`setup.py:1281,1323,1361,1387,1479`); headless uses `has_failure` at `:1543`. `run.py:99-100,248-260` set `stdin=DEVNULL, start_new_session=True`. Tests pass: `test_worker_exception_marks_the_run_failed_and_keeps_done_rows[RuntimeError,OSError]`, `test_failed_update_exits_1`, `test_tui_routes_exit_1_when_the_session_failed[4 routes]`, `test_*_tty_reader_fails_fast` (elapsed < 5 s), `test_*_child_runs_in_its_own_session`, `test_load_settings_invalid_utf8_returns_defaults_and_a_warning`, `test_invalid_settings_file_launches_to_the_first_screen_with_a_warning` (bytes identical), `test_every_tui_route_executes_the_accepted_selection[setup,doctor,fix,uninstall,guard]` |
| SC4 | With a ban and a tweak active, centralized → split removes their blocks from the old mode's rc and writes them where the new mode sources | ✓ VERIFIED | `installer/policy.py:231-304` `move_link_mode` (remove in old mode → save → apply in new mode; rollback on save failure, on apply failure and on re-save failure; same-mode no-op). Tests pass: `test_move_link_mode_moves_ban_and_tweak_to_split` (ban gone from .myshellrc and present in .zshrc/.bashrc; tweak sourced from both rc files), `test_link_mode_move_keeps_foreign_rc_bytes_identical`, plus 7 rollback/no-op/lost-policy tests and `test_move_link_mode_ignores_policies_that_are_not_link_mode_aware` |
| SC5 | CI green on ubuntu and macOS; merges to main require the PR check; plans 16-17..19 carry secure and validate re-audit records | ? UNCERTAIN (human) | CI: `gh run view 38698283448` → headSha 91952dd, both jobs `success`; HEAD 6612222 differs from 91952dd only under `.planning/`. Re-audit: 16-SECURITY.md:82-89 has the qualified `T-16-49/50/51 (16-18)` and `(16-19)` rows; 16-VALIDATION.md has 18 rows `16-17-0x..16-19-0x` plus a dated 2026-10-14 audit entry. Branch protection: `gh api .../branches/main/protection` → 404 "Branch not protected" (CI-02 handed to the user per RUN-LEDGER; see Human Verification) |

### Observable Truths: Plan must_haves (grouped per plan)

| # | Plan | Status | Evidence |
|---|------|--------|----------|
| 1 | 17-01 CI green (bash 3.2 prune, Darwin pyright, flake-free tests) | ✓ VERIFIED | Artifacts/links pass (`while IFS= read -r`, `grep -E`, `sys.platform`, `dash`). macOS CI (bash 3.2 /bin/bash, Darwin pyright in `make validate`) green in run 38698283448. No skip/xfail added anywhere in the phase diff |
| 2 | 17-02 `link_executable` refuses a directory member | ✓ VERIFIED | See SC1 |
| 3 | 17-03 new session plus closed stdin for install and update children | ✓ VERIFIED | See SC3; `run_command` untouched |
| 4 | 17-04 Doctor reports broken `~/.local/bin` links | ✓ VERIFIED | `scan_bin_links` wired via `app.py` doctor_data → `guidance.py` → render/DoctorScreen (key links verified); `test_scan_reports_a_link_to_a_directory` passes; the tmux check in RUN-LEDGER shows the repair text in view 4 |
| 5 | 17-05 graphify postinstall removed, Sublime member, codex non-interactive | ✓ VERIFIED | `registry.toml:1354` `env = { CODEX_NON_INTERACTIVE = "1" }`, `:2283,2291` `member = "sublime_text/sublime_text"`; `_graphify_register` and `graphify-register` absent from installer/ and setup.py |
| 6 | 17-06 atomic rc/shim writes; `clean_rc_duplicates` recheck (incl. 3 backstop edges) | ✓ VERIFIED | See SC2. Backstops: missing file → `test_atomic_write_bytes_creates_a_file_that_does_not_exist_yet`; concurrent reader → `test_rc_reader_never_sees_a_partial_write` (tests/test_atomic.py, 12/12 pass); empty rc → observed directly (scratch HOME script: `write_ban_aliases` / `write_tweak` on an empty file leave exactly the managed block and no temp file, `EMPTY_RC_OK`) |
| 7 | 17-07 crashed/failed run is red and exits 1; `fold_run` | ✓ VERIFIED | See SC3; `session.fold_run` wired from execute_screen and wizard_app (key links verified) |
| 8 | 17-08 link-mode move with rollback; save-first `set_link_mode` | ✓ VERIFIED | See SC4; `settings.py` `save_settings(self._path, Settings(value))` before the live assignment (key link verified) |
| 9 | 17-09 uninstall deletes only proven-owned files (incl. backstop opt-dir failure) | ✓ VERIFIED | See SC2; backstop `test_failed_opt_dir_delete_leaves_the_remainder_listed` passes |
| 10 | 17-10 `_build_app` always builds execute; Enter runs on every route | ✓ VERIFIED | See SC3 |
| 11 | 17-11 invalid settings.json warns, never crashes, never rewritten | ✓ VERIFIED | `settings.py` has exactly one read (`:65`); `setup.py` has exactly one `load_settings(`; warning carried via `startup_warning=` (key links verified) |
| 12 | 17-12 16-17..16-19 security and validation re-audit | ✓ VERIFIED | See SC5 (re-audit part); commits b4a238c and 918877b touch only the two milestone docs |
| 13 | 17-13 phase close: gates, oracle, protection | ? UNCERTAIN (human) | Gates and oracle VERIFIED: pyproject.toml/uv.lock identical to 72c9047; oracle run 38698283448 green; e2e baseline recorded (17-13-SUMMARY.md:66-68). The post-verification main push (backstop) and branch protection are pending by design: see Human Verification |
| 14 | 17-14 dot-dot test and race test (macOS) | ✓ VERIFIED | Commits 8f85cb5 and 789c168 touch only the two test files; CI green |
| 15 | 17-15 race test writer waits inside each window | ✓ VERIFIED | ebbc454 touches only tests/test_version_status.py; the final `assert observed is expected` is kept (re-indented) |
| 16 | 17-16 daemon in-flight test gated by an Event | ✓ VERIFIED | d5858ee touches only tests/test_wizard_app.py; every original assert re-appears inside the gated block |
| 17 | 17-17 uninstall path lines unwrapped and literal | ✓ VERIFIED | 73067f2 touches only installer/render.py and tests/test_render.py; the macOS job is green |
| 18 | 17-18 uninstall/download/test-hygiene review fixes | ✗ FAILED | All 5 truths hold (tests pass: `test_plan_removal_survives_looping_link_and_opt_dir`, `test_run_uninstall_survives_a_looping_link`, `test_*_refuses_paths_changed_since_the_preview`, `test_update_download_directory_member_rolls_back`, `test_update_app_directory_cli_rolls_back`, `test_*raw_install_replaces_a_link_instead_of_writing_through_it`; WR-07 wait is suppression-free via `asyncio.gather`). But the declared prohibition "MUST NOT add a new type: ignore" is violated: ad63b1f adds `# type: ignore[arg-type]` at tests/test_app.py:3584 and :3617 |
| 19 | 17-19 run outcome and exit-code review fixes | ✓ VERIFIED | Tests pass: `test_in_flight_latch_skip_is_a_failure_on_neither_signal`, `test_a_completed_update_stays_done_when_the_version_refresh_crashes`, `test_a_cancelled_run_then_a_successful_rerun_is_not_a_failure`, `test_a_failed_direct_update_*` (x2), `test_failed_direct_catalog_update_exits_1`, `test_ctrl_c_mid_run_exits_1`, `test_doctor_route_interrupted_mid_run_exits_1`, `test_a_crash_after_a_path_wiring_failure_keeps_both_texts_in_the_log`, plus 3 run_in_flight lifecycle tests |
| 20 | 17-20 link-mode migration and settings-warning review fixes | ✓ VERIFIED | Tests pass: `test_move_link_mode_clears_a_partial_new_mode_write_before_restoring`, `..._names_the_ids_it_could_not_restore`, `..._with_the_live_mode_is_a_no_op`, `test_link_mode_change_after_an_uninstall_does_not_resurrect`, `test_split_to_centralized_move_reports_the_path_wiring_action`, `test_all_yes_with_a_damaged_settings_json_warns_before_acting`, `test_non_tty_doctor_with_a_damaged_settings_json_warns_before_acting`. M1 handled as a reported action: `wizard_app.py:2250` `make fix ARGS="--link-mode {value}"` (RUN-LEDGER decision) |

**Score:** 22/25 must-haves verified (0 present, behavior-unverified). That is 4/5 roadmap SCs plus 18/20 plan groups; SC5 and 17-13 are human-pending and 17-18 FAILED.

Behavior-dependent truths (rollback paths, cancel/not_attempted, run_in_flight lifecycle, save-first ordering, atomic replace, preview/confirm recheck) are each backed by a named passing test, so none is PRESENT_BEHAVIOR_UNVERIFIED.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| 17-01..17-13 `must_haves.artifacts` (34 entries) | per plan | ✓ VERIFIED | `gsd_run query verify.artifacts` exit 0 for all 13 plans |
| 17-14..17-20 | none declared | N/A | `verify.artifacts` exit 66 (NO_INPUT) |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| 17-01..17-13 `must_haves.key_links` (23 entries) | per plan | ✓ WIRED | `gsd_run query verify.key-links` exit 0 for all 13 plans |
| 17-14..17-20 | none declared | N/A | exit 66 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `setup._session_exit_code` | `summary.has_failure` | `UnifiedApp.install_summary` ← `session.fold_run` ← `InstallRunFinished` | Yes (pilot tests drive real ExecuteScreen workers) | ✓ FLOWING |
| `run_uninstall` deletion set | `plan_removal().removable` | live `bin_dir` lstat/resolve at preview and again at deletion | Yes | ✓ FLOWING |
| `UnifiedApp` startup status | `startup_warning` | `load_settings` → `SettingsStore.warning` → `_build_app` | Yes | ✓ FLOWING |
| link-mode pickers | `aware_active` | live `Policy.is_active` disk probe (17-20) | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Roadmap SC1-SC4 named tests (27 node ids, 32 items) | `uv run pytest -q --no-cov <ids>` | 32 passed | ✓ PASS |
| 17-18..17-20 review-fix plus rollback tests (35 node ids, 38 items) | `uv run pytest -q --no-cov <ids>` | 38 passed, rc 0 | ✓ PASS |
| Atomic write edges | `uv run pytest -q --no-cov tests/test_atomic.py tests/test_guards.py::test_ban_aliases_write_through_a_symlinked_rc` | 12 passed | ✓ PASS |
| Empty-rc backstop (scratch HOME) | `HOME=<scratch> uv run python <scratch>/empty_rc_check.py` | `EMPTY_RC_OK ['.myshellrc', '.zshrc']` | ✓ PASS |
| CI oracle | `gh run view 38698283448 --json headSha,conclusion,jobs` | 91952dd; macos-latest success, ubuntu-latest success | ✓ PASS |
| Dependencies unchanged | `git diff --quiet 72c9047 HEAD -- pyproject.toml uv.lock` | identical | ✓ PASS |
| Branch protection | `gh api repos/castocolina/tools-installer/branches/main/protection` | 404 Branch not protected | ? SKIP (human, CI-02) |

The full suite was not re-run by this verifier. The orchestrator's evidence on 91952dd/6612222 (make validate plus make test twice, 3572 passed, 4 skipped; pre-commit; make e2e rc 0) is corroborated by the CI oracle above.

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` exist, and no PLAN/SUMMARY declares one. The graphify container probe is a recorded transcript (17-05-SUMMARY.md:111-117), not a re-runnable repo probe, and installs only in a disposable container, so this verifier did not re-run it.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SAFE-01 | 17-02, 17-04, 17-05, 17-18 | Directory member fails, links nothing; reinstall keeps inner files | ✓ SATISFIED | SC1 |
| SAFE-02 | 17-05 | graphify writes nothing into cwd | ✓ SATISFIED | SC1 |
| SAFE-03 | 17-09, 17-17, 17-18 | Uninstall deletes only proven files; others "remove it yourself" | ✓ SATISFIED | SC2 (the 17-18 gap is in test typing, not in behavior) |
| SAFE-04 | 17-06 | Atomic rc/shim writes; cleanup refuses changed file | ✓ SATISFIED | SC2, 17-06 row |
| SAFE-05 | 17-07, 17-10, 17-19 | Crash/failed run red, exit non-zero | ✓ SATISFIED | SC3 |
| SAFE-06 | 17-08, 17-20 | Link-mode change keeps active policies | ✓ SATISFIED | SC4 (scoped to `link_mode_aware` per RUN-LEDGER Q2) |
| SAFE-07 | 17-03, 17-05 | tty-prompting vendor script fails fast | ✓ SATISFIED | SC3 |
| SAFE-08 | 17-11, 17-20 | Non-UTF-8 settings.json does not crash | ✓ SATISFIED | SC3 |
| SAFE-09 | 17-10, 17-19 | Every catalog route can execute | ✓ SATISFIED | SC3 |
| CI-01 | 17-01, 17-13..17-18 | CI green on Ubuntu and macOS | ✓ SATISFIED | run 38698283448 |
| CI-02 | 17-13 | Merges require the PR check | ? NEEDS HUMAN | Not applied; command in 17-13-SUMMARY.md:78-83 |
| CI-03 | 17-12 | 16-17..19 re-audited | ✓ SATISFIED | SC5 re-audit evidence |

Orphaned requirements: none. All 12 IDs mapped to Phase 17 in REQUIREMENTS.md are claimed by at least one plan.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts: `check.decision-coverage-verify` reports 18/18 honored, not_honored []. RUN-LEDGER refinements are honored in code: Q1 (graphify postinstall removed), Q2 (`Policy.link_mode_aware` filter), Q3 (race test reproduced and fixed in 17-14/17-15/17-18), the 17-11 warn-only-on-UTF-8/JSON rule (`test_wrong_json_shapes_return_never_chosen` semantics unchanged), and M1 as a reported action.

### Test Quality Audit

| Test File | Linked Req | Skipped added | Circular | Assertion Level | Verdict |
|-----------|-----------|---------------|----------|-----------------|---------|
| tests/test_download.py, test_apps.py, test_engine.py | SAFE-01 | 0 | No | Value (byte-identical files, no link) | OK |
| tests/test_postinstall.py, test_update.py | SAFE-02 | 0 | No | Value (exact argv, empty cwd) | OK |
| tests/test_uninstall.py, test_app.py | SAFE-03 | 0 | No | Behavioral (deletion sets, TUI = CLI) | OK, with 6 `type: ignore[arg-type]` (gap) |
| tests/test_guards.py, test_atomic.py, test_app.py | SAFE-04 | 0 | No | Value (byte-identical on failure) | OK |
| tests/test_execute_screen.py, test_setup.py, test_wizard_app.py | SAFE-05/09 | 0 | No | Behavioral (pilot runs, exit codes) | OK |
| tests/test_policy.py, test_policies_e2e.py | SAFE-06 | 0 | No | Behavioral (rc contents per mode) | OK |
| tests/test_run.py | SAFE-07 | 0 | No | Behavioral (getsid, elapsed < 5 s) | OK |
| tests/test_settings.py, test_setup.py | SAFE-08 | 0 | No | Value (bytes identical, warning severity) | OK |

**Disabled tests on requirements:** 0. **Circular patterns:** 0. **Insufficient assertions:** 0. The only test deleted is `test_accepting_the_catalog_without_execute_still_exits_with_ids`, which D-12 requires.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/test_app.py | 3584, 3617 | `# type: ignore[arg-type]` added by 17-18 (ad63b1f) | 🛑 Blocker | Violates the 17-18 declared prohibition and .claude/python-tooling.md:22; the SUMMARY claims the opposite |
| tests/test_app.py | 3492, 3521, 3538, 3560 | `# type: ignore[arg-type]` added by 17-09 (5c559ae), same `_uninstall_kwargs` root cause | ⚠️ Warning | Rule violation (python-tooling.md:22), with no plan-level prohibition; fixed by the same TypedDict change |
| tests/* (other phase additions) | various | ~26 more `type: ignore[...]` / `pyright: ignore[reportPrivateUsage]` added across 17-07, 17-08, 17-10, 17-19, 17-20 | ⚠️ Warning | Follows the established test-file convention (baseline: 85 type-ignore, 472 pyright-ignore in tests/); still against the written rule; no plan prohibition beyond 17-18 |
| installer/execute_screen.py | (phase diff) | `except Exception as exc:  # noqa: BLE001 -- the run must report, not die` | ℹ️ Info | Narrow code plus a reason, a deliberate catch-all required by SAFE-05 |
| (all 50 changed files) | — | TBD/FIXME/XXX, TODO/HACK/PLACEHOLDER | none | Clean |
| installer/, setup.py, scripts/ phase diff | — | `sudo` / `pkexec` / `doas` added | none | Zero-sudo rule holds for Phase 17 text |

### Human Verification Required

### 1. Apply branch protection on main (CI-02)

**Test:** After the post-verification main push is green, run `printf '%s' '<body at 17-13-SUMMARY.md:80>' | gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -`
**Expected:** The read-back lists exactly the two contexts `validate & test on ubuntu-latest` and `validate & test on macos-latest`, with `enforce_admins` false. Today it returns 404 "Branch not protected".
**Why human:** A GitHub settings change needs the user's in-the-moment consent (D-17). RUN-LEDGER hands the command to the user.

### 2. Post-verification main push CI (17-13 backstop)

**Test:** The orchestrator pushes main after /gsd-verify-work and records the run under `## Post-verification main push` in 17-13-SUMMARY.md.
**Expected:** Both jobs succeed for the main HEAD that lands.
**Why human:** This step is orchestrator-owned and runs after verification; "pending" is the expected state at verify time.

### Gaps Summary

There is one blocking gap, and it is narrow. The phase's functional goal is achieved: all four hazard criteria (SC1-SC4) have production fixes wired through the real paths and pass named behavioral tests, CI is green on both OSes for the final code, and the 16-17..19 re-audit is recorded. The gap is a must-NOT that plan 17-18 declared and then broke. Commit ad63b1f added two `# type: ignore[arg-type]` (tests/test_app.py:3584, :3617), and the 17-18 SUMMARY reports "suppression-free tests". The root cause is `_uninstall_kwargs -> dict[str, object]` (tests/test_app.py:3463, from 17-09). Typing that helper precisely removes all six ignores on that helper in one small, test-only change, with no product code involved.

**If the user prefers to accept the deviation instead:** the markers follow a pre-existing in-file pattern (`_healthy_doctor_kwargs`, tests/test_app.py:1854-2007). To accept, add this to the frontmatter and re-run verification:

```yaml
overrides:
  - must_have: "17-18 prohibition: MUST NOT add a new type: ignore / pyright: ignore / noqa"
    reason: "Two test-only arg-type ignores follow the existing **kwargs helper pattern in tests/test_app.py; tracked for cleanup in Phase 25 (Lean)"
    accepted_by: "{your name}"
    accepted_at: "{ISO timestamp}"
```

CI-02 (branch protection) is an expected human action and is not a gap.

---

_Verified: 2026-10-15T08:38:26Z_
_Verifier: Claude (gsd-verifier)_
