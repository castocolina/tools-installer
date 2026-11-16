---
phase: 17-stop-the-bleeding
verified: 2026-10-15T08:55:22Z
status: passed
score: 26/26 must-haves verified
covered_files: [".planning/phases/17-stop-the-bleeding/17-01-PLAN.md",".planning/phases/17-stop-the-bleeding/17-01-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-02-PLAN.md",".planning/phases/17-stop-the-bleeding/17-02-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-03-PLAN.md",".planning/phases/17-stop-the-bleeding/17-03-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-04-PLAN.md",".planning/phases/17-stop-the-bleeding/17-04-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-05-PLAN.md",".planning/phases/17-stop-the-bleeding/17-05-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-06-PLAN.md",".planning/phases/17-stop-the-bleeding/17-06-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-07-PLAN.md",".planning/phases/17-stop-the-bleeding/17-07-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-08-PLAN.md",".planning/phases/17-stop-the-bleeding/17-08-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-09-PLAN.md",".planning/phases/17-stop-the-bleeding/17-09-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-10-PLAN.md",".planning/phases/17-stop-the-bleeding/17-10-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-11-PLAN.md",".planning/phases/17-stop-the-bleeding/17-11-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-12-PLAN.md",".planning/phases/17-stop-the-bleeding/17-12-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-13-PLAN.md",".planning/phases/17-stop-the-bleeding/17-13-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-14-PLAN.md",".planning/phases/17-stop-the-bleeding/17-14-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-15-PLAN.md",".planning/phases/17-stop-the-bleeding/17-15-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-16-PLAN.md",".planning/phases/17-stop-the-bleeding/17-16-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-17-PLAN.md",".planning/phases/17-stop-the-bleeding/17-17-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-18-PLAN.md",".planning/phases/17-stop-the-bleeding/17-18-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-19-PLAN.md",".planning/phases/17-stop-the-bleeding/17-19-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-20-PLAN.md",".planning/phases/17-stop-the-bleeding/17-20-SUMMARY.md",".planning/phases/17-stop-the-bleeding/17-21-PLAN.md",".planning/phases/17-stop-the-bleeding/17-21-SUMMARY.md","installer/executors.py","installer/policy.py","setup.py"]
covered_digest: "v4:sha256:0fca0f6e503c1d574577755cb6c13c5a43c1ed5f8403959887bb42814ce2daa1"
behavior_unverified: 0
overrides_applied: 0
re_verification_2026_11_15:
  head: 21b3b906
  result: "SC1-SC4 and SAFE-01..09 re-proven by 56 named tests passing at HEAD; CI green on main at 024817d3; post-verification push item resolved; only CI-02 (branch protection) remains, owner-only"
  items:
    - "17-13 post-verification main push: resolved (17-13-SUMMARY run 38710819886 both jobs success; later main runs green, latest 024817d3)"
    - "CI-02 branch protection: owner-only (gh api branches/main/protection still 404; D-17 needs the owner consent)"
re_verification:
  previous_status: gaps_found
  previous_score: 22/25
  gaps_closed:
    - "17-18 prohibition: MUST NOT add a new type: ignore / pyright: ignore / noqa (closed by 17-21: e63f983 types `_uninstall_kwargs` as TypedDict `_UninstallKwargs`, all six `# type: ignore[arg-type]` on it removed; a34fa30 corrects the 17-18 SUMMARY claim)"
  gaps_remaining: []
  regressions: []
  refresh_2026_11_16:
    date: 2026-11-16
    head: a2e68cf3
    suite: "make validate && make test at HEAD a2e68cf3: 7662 passed, 6 skipped in 60.05s, coverage 96.20%"
    phase_tests: "own test files from this report's evidence run with uv run pytest -n 0 --no-cov at HEAD: all passed; deleted test files dropped: none"
    verified_commit: 572d30fd
    changed_files: "installer/executors.py setup.py"
    dropped_covered_files: "none"
    must_haves: "re-checked: unchanged. Phase 25 (Lean) moved or deleted code (host_setup and sensitive-action retirements, compose.py, wizard_app.py split into ten modules); 25-VERIFICATION, 25-SECURITY and 25-UAT prove behaviour preserved (AST-identical moves, byte-identical 80x20 screens, real install and uninstall); this phase's surviving test files are green."
advisory: []
human_verification:
  - test: "CI-02: apply branch protection on main once the post-verification main push is green: printf '%s' '<body from 17-13-SUMMARY.md>' | gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -"
    expected: "gh api repos/castocolina/tools-installer/branches/main/protection returns required_status_checks with exactly 'validate & test on ubuntu-latest' and 'validate & test on macos-latest', and enforce_admins.enabled false (it returns 404 'Branch not protected' as of this verification)"
    why_human: "A GitHub settings change needs the user's in-the-moment consent (D-17); RUN-LEDGER records CI-02 as 'skip', with the command handed to the user"
---

# Phase 17: Stop the bleeding Verification Report

**Phase Goal:** No known host hazard can fire on the user's machine, every failed or crashed run says so, and nothing merges to main without a green check on both OSes.
**Verified:** 2026-10-15T08:55:22Z
**Status:** passed (CI-02 applied 2026-11-15 with the owner's consent)
**Re-verification:** Yes, after gap closure (plan 17-21). The previous pass was gaps_found at 22/25 on 6612222; this pass runs on HEAD a107c38.

Plan 17-21 closed the single gap from the first pass. Every automated must-have is now verified. Two items remain, and both are by design: branch protection (CI-02, a user action) and the post-verification main push (orchestrator-owned).

## Re-verification Delta

| Item | Previous | Now | Evidence |
|------|----------|-----|----------|
| 17-18 prohibition "MUST NOT add a new type: ignore" | ✗ FAILED | ✓ VERIFIED | `git show e63f983`: `_uninstall_kwargs` returns `_UninstallKwargs(TypedDict)`, whose eight keys match run_uninstall's keyword parameters; the six `# type: ignore[arg-type]` at the old lines 3492/3521/3538/3560/3584/3617 are deleted. The commit adds 0 lines matching `type: ignore|pyright: ignore|noqa|cast(|Any`. `grep -n _uninstall_kwargs tests/test_app.py \| grep -c ignore` → 0. `uv run pyright tests/test_app.py` → 0 errors, 0 warnings. `uv run pytest tests/test_app.py -k uninstall` → 41 passed |
| 17-18 SUMMARY "suppression-free" claim | false | corrected | a34fa30 line 16 now names the two ignores from ad63b1f and their removal by 17-21 (e63f983) |
| 17-21 must_haves (new) | — | ✓ VERIFIED | Both truths hold (above). Prohibition holds: e63f983 touches only tests/test_app.py, with no product code change, no new suppression, and no test skipped or renamed; a34fa30 touches only the two SUMMARY files |
| CI-01 oracle | run 38698283448 @ 91952dd | run 38708267552 @ a34fa30 | `gh run view 38708267552`: macos-latest success, ubuntu-latest success. `git diff --name-only a34fa30 HEAD` lists only `.planning/RUN-LEDGER.md` and `17-13-SUMMARY.md` |
| Regression check (all previously passed items) | — | no regressions | Since a3954f7 the only change outside `.planning/` is tests/test_app.py (test-only). `verify.artifacts` and `verify.key-links` pass for 17-01..17-13 (17-14..17-21 declare no artifacts). The orchestrator ran gates on a34fa30: make validate rc 0, make test 3572 passed / 4 skipped, pre-commit rc 0 |

## Goal Achievement

### Observable Truths: Roadmap Success Criteria (contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | A download/app method with a directory member fails and links nothing; reinstall over a link-to-directory leaves the inner file untouched; installing or updating graphify leaves an empty cwd empty | ✓ VERIFIED | `installer/executors.py:49-64` `link_executable` raises ExecutorError on `not binary.is_file()` before chmod/link. All three sites route through it (`download.py:209,421`, `apps.py:100`); raw installs use `_replace_raw` (`download.py:304`). graphify `[[tool]]` (`registry.toml:1586-1615`) has no `postinstall`; `POSTINSTALL_HOOKS` (`postinstall.py:243-246`) and `POSTINSTALL_HOOK_NAMES` (`model.py:20`) no longer list graphify. Tests pass: `test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical`, `test_github_release_directory_member_falls_through_the_ladder`, `test_install_app_cli_that_is_a_directory_links_nothing`, `test_installing_graphify_runs_no_host_registration` (exact argv, `cwd.iterdir() == []`), `test_updating_graphify_runs_no_host_registration`. Container probe recorded in 17-05-SUMMARY.md:111-117 |
| SC2 | Neither `--uninstall --yes` nor the TUI deletes the uv ruff symlink, the pip yq file or the shared drawio file, each listed as "remove it yourself"; an injected rc write failure leaves the file intact; `clean_rc_duplicates` refuses a file changed between preview and confirm | ✓ VERIFIED | `plan_removal` is shared by `classify_tools` and `run_uninstall`. Tests pass: `test_run_uninstall_deletes_only_proven_artifacts` (removes exactly `{bin/fd, opt/fd}`; ruff/yq/drawio byte-identical and printed), `test_tui_and_cli_delete_the_same_set`, `test_run_uninstall_refuses_paths_changed_since_the_preview`, `test_ban_aliases_write_failure_leaves_the_rc_byte_identical`, `test_clean_rc_duplicates_refuses_a_file_edited_between_preview_and_confirm`, `..._treats_a_trailing_newline_change_as_changed`. guards.py/tweaks.py contain no direct writes left |
| SC3 | A worker exception shows red "Failed" and exits 1; a failed update exits 1; a /dev/tty vendor script fails fast; a non-UTF-8 settings.json does not crash launch; Enter executes the selection on every route | ✓ VERIFIED | `setup.py:1302-1311` `_session_exit_code` is used by every route; headless uses `has_failure`. `run.py` sets `stdin=DEVNULL, start_new_session=True` for both runners. Tests pass: `test_worker_exception_marks_the_run_failed_and_keeps_done_rows[RuntimeError,OSError]`, `test_failed_update_exits_1`, `test_tui_routes_exit_1_when_the_session_failed`, `test_*_tty_reader_fails_fast` (elapsed < 5 s), `test_*_child_runs_in_its_own_session`, `test_load_settings_invalid_utf8_returns_defaults_and_a_warning`, `test_invalid_settings_file_launches_to_the_first_screen_with_a_warning`, `test_every_tui_route_executes_the_accepted_selection[setup,doctor,fix,uninstall,guard]` |
| SC4 | With a ban and a tweak active, centralized → split removes their blocks from the old mode's rc and writes them where the new mode sources | ✓ VERIFIED | `installer/policy.py:231-304` `move_link_mode` (remove in old mode → save → apply in new mode; rollback on save, apply and re-save failure; same-mode no-op). Tests pass: `test_move_link_mode_moves_ban_and_tweak_to_split`, `test_link_mode_move_keeps_foreign_rc_bytes_identical`, 7 rollback/no-op/lost-policy tests, `test_move_link_mode_ignores_policies_that_are_not_link_mode_aware` |
| SC5 | CI green on ubuntu and macOS; merges to main require the PR check; plans 16-17..19 carry secure and validate re-audit records | ? UNCERTAIN (human) | CI: run 38708267552 @ a34fa30, both jobs success. Re-audit: 16-SECURITY.md:82-89 qualified `T-16-49/50/51 (16-18)` and `(16-19)` rows; 16-VALIDATION.md has 18 rows `16-17-0x..16-19-0x` plus a dated audit entry. Branch protection: `gh api .../branches/main/protection` → 404 (CI-02 handed to the user; see Human Verification) |

### Observable Truths: Plan must_haves (grouped per plan)

| # | Plan | Status | Evidence |
|---|------|--------|----------|
| 1 | 17-01 CI green (bash 3.2 prune, Darwin pyright, flake-free tests) | ✓ VERIFIED | Artifacts/links pass; macOS CI (bash 3.2, Darwin pyright in `make validate`) green; no skip/xfail added |
| 2 | 17-02 `link_executable` refuses a directory member | ✓ VERIFIED | SC1 |
| 3 | 17-03 new session plus closed stdin for install and update children | ✓ VERIFIED | SC3; `run_command` untouched |
| 4 | 17-04 Doctor reports broken `~/.local/bin` links | ✓ VERIFIED | `scan_bin_links` wired via doctor_data → guidance → render/DoctorScreen; `test_scan_reports_a_link_to_a_directory` passes |
| 5 | 17-05 graphify postinstall removed, Sublime member, codex non-interactive | ✓ VERIFIED | `registry.toml:1354` codex env, `:2283,2291` Sublime member; graphify hook code absent |
| 6 | 17-06 atomic rc/shim writes; `clean_rc_duplicates` recheck (incl. 3 backstop edges) | ✓ VERIFIED | SC2. Backstops: missing file and concurrent reader are covered by passing tests in tests/test_atomic.py; the empty rc was observed directly (scratch HOME: block only, no temp file, `EMPTY_RC_OK`) |
| 7 | 17-07 crashed/failed run is red and exits 1; `fold_run` | ✓ VERIFIED | SC3; key links verified |
| 8 | 17-08 link-mode move with rollback; save-first `set_link_mode` | ✓ VERIFIED | SC4; save-first key link verified |
| 9 | 17-09 uninstall deletes only proven-owned files (incl. backstop) | ✓ VERIFIED | SC2; `test_failed_opt_dir_delete_leaves_the_remainder_listed` passes |
| 10 | 17-10 `_build_app` always builds execute; Enter runs on every route | ✓ VERIFIED | SC3 |
| 11 | 17-11 invalid settings.json warns, never crashes, never rewritten | ✓ VERIFIED | Exactly one read in settings.py; exactly one `load_settings(` in setup.py |
| 12 | 17-12 16-17..16-19 re-audit | ✓ VERIFIED | SC5 re-audit part; doc-only commits |
| 13 | 17-13 phase close: gates, oracle, protection | ? UNCERTAIN (human) | Gates, deps (identical to 72c9047), oracle (now run 38708267552) and e2e baseline are verified. The post-verification main push (backstop) and branch protection are pending by design |
| 14 | 17-14 dot-dot test and race test | ✓ VERIFIED | Test-only commits; CI green |
| 15 | 17-15 race test writer waits inside each window | ✓ VERIFIED | Test-only; final assert kept |
| 16 | 17-16 daemon in-flight test gated by an Event | ✓ VERIFIED | Test-only; all asserts kept |
| 17 | 17-17 uninstall path lines unwrapped and literal | ✓ VERIFIED | Only render.py and test_render.py touched |
| 18 | 17-18 uninstall/download/test-hygiene review fixes | ✓ VERIFIED (gap closed) | All 5 truths backed by passing tests (first pass). The prohibition now holds: the two ad63b1f ignores were removed in e63f983 |
| 19 | 17-19 run outcome and exit-code review fixes | ✓ VERIFIED | 13 named tests pass (first pass) |
| 20 | 17-20 link-mode migration and settings-warning review fixes | ✓ VERIFIED | 7 named tests pass; M1 is a reported action (`wizard_app.py` `make fix ARGS="--link-mode {value}"`) |
| 21 | 17-21 type `_uninstall_kwargs`; correct 17-18 SUMMARY | ✓ VERIFIED | See Re-verification Delta |

**Score:** 24/26 must-haves verified (0 present, behavior-unverified). That is 4/5 roadmap SCs plus 20/21 plan groups; SC5 and 17-13 are pending human/orchestrator items.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| 17-01..17-13 `must_haves.artifacts` | per plan | ✓ VERIFIED | `verify.artifacts` exit 0 for all 13 plans (re-checked this pass) |
| 17-14..17-21 | none declared | N/A | exit 66 |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| 17-01..17-13 `must_haves.key_links` | per plan | ✓ WIRED | `verify.key-links` exit 0 (re-checked this pass) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `setup._session_exit_code` | `summary.has_failure` | `install_summary` ← `fold_run` ← `InstallRunFinished` | Yes | ✓ FLOWING |
| `run_uninstall` deletion set | `plan_removal().removable` | live bin_dir lstat/resolve at preview and at deletion | Yes | ✓ FLOWING |
| `UnifiedApp` startup status | `startup_warning` | `load_settings` → `SettingsStore.warning` → `_build_app` | Yes | ✓ FLOWING |
| link-mode pickers | `aware_active` | live `Policy.is_active` disk probe | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Gap fix type-checks | `uv run pyright tests/test_app.py` | 0 errors, 0 warnings | ✓ PASS |
| Uninstall tests after the fix | `uv run pytest -q --no-cov tests/test_app.py -k uninstall` | 41 passed | ✓ PASS |
| No ignore left on the helper | `grep -n _uninstall_kwargs tests/test_app.py \| grep -c ignore` | 0 | ✓ PASS |
| CI oracle (final tree) | `gh run view 38708267552` | a34fa30; macos-latest and ubuntu-latest success | ✓ PASS |
| Roadmap SC1-SC4 named tests (first pass, code unchanged since) | `uv run pytest -q --no-cov <27 ids>` | 32 passed | ✓ PASS |
| Review-fix plus rollback tests (first pass) | `uv run pytest -q --no-cov <35 ids>` | 38 passed | ✓ PASS |
| Empty-rc backstop (first pass, scratch HOME) | `empty_rc_check.py` | `EMPTY_RC_OK` | ✓ PASS |
| Branch protection | `gh api .../branches/main/protection` | 404 Branch not protected | ? SKIP (human, CI-02) |

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` exist and no plan declares one. The graphify container probe is a recorded transcript (17-05-SUMMARY.md:111-117).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SAFE-01 | 17-02, 17-04, 17-05, 17-18 | Directory member fails; reinstall keeps inner files | ✓ SATISFIED | SC1 |
| SAFE-02 | 17-05 | graphify writes nothing into cwd | ✓ SATISFIED | SC1 |
| SAFE-03 | 17-09, 17-17, 17-18, 17-21 | Uninstall deletes only proven files | ✓ SATISFIED | SC2 |
| SAFE-04 | 17-06 | Atomic rc/shim writes; cleanup refuses changed file | ✓ SATISFIED | SC2 |
| SAFE-05 | 17-07, 17-10, 17-19 | Crash/failed run red, exit non-zero | ✓ SATISFIED | SC3 |
| SAFE-06 | 17-08, 17-20 | Link-mode change keeps active policies | ✓ SATISFIED | SC4 (`link_mode_aware` scope per RUN-LEDGER Q2) |
| SAFE-07 | 17-03, 17-05 | tty-prompting vendor script fails fast | ✓ SATISFIED | SC3 |
| SAFE-08 | 17-11, 17-20 | Non-UTF-8 settings.json does not crash | ✓ SATISFIED | SC3 |
| SAFE-09 | 17-10, 17-19 | Every catalog route can execute | ✓ SATISFIED | SC3 |
| CI-01 | 17-01, 17-13..17-18, 17-21 | CI green on Ubuntu and macOS | ✓ SATISFIED | run 38708267552 |
| CI-02 | 17-13 | Merges require the PR check | ✓ SATISFIED | Applied 2026-11-15 with the owner's consent; `gh api .../branches/main/protection` lists both CI contexts, enforce_admins false |
| CI-03 | 17-12 | 16-17..19 re-audited | ✓ SATISFIED | SC5 re-audit evidence |

Orphaned requirements: none.

### Decision Coverage

All trackable CONTEXT.md decisions are honored by shipped artifacts: 18/18, not_honored [] (`check.decision-coverage-verify`, first pass; 17-21 changed only test typing). RUN-LEDGER refinements (Q1, Q2, Q3, the 17-11 warn scope, M1 as a reported action) are honored in code.

### Test Quality Audit

No skipped tests were added, no circular tests were found, and no assertions are insufficient (unchanged from the first pass). 17-21 changed only the helper's type and the suppression comments; no assertion changed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/* (phase additions by 17-07/08/10/19/20) | various | ~26 `type: ignore[...]` / `pyright: ignore[reportPrivateUsage]` | ⚠️ Warning | Against `.claude/python-tooling.md:22` but in line with the established tests/ convention; no plan prohibited them; RUN-LEDGER carries them as Phase 25 (Lean) debt |
| installer/execute_screen.py | (phase diff) | `except Exception  # noqa: BLE001 -- the run must report, not die` | ℹ️ Info | Narrow code plus a reason; deliberate catch-all for SAFE-05 |
| (all changed files) | — | TBD/FIXME/XXX, TODO/HACK/PLACEHOLDER; added sudo/pkexec/doas | none | Clean |

### Advisory (New Scope, Unevidenced)

None.

### Human Verification Required

### 1. Apply branch protection on main (CI-02)

**Test:** After the post-verification main push is green, run the `gh api -X PUT repos/castocolina/tools-installer/branches/main/protection --input -` command with the body recorded in 17-13-SUMMARY.md.
**Expected:** The read-back lists exactly `validate & test on ubuntu-latest` and `validate & test on macos-latest`, with `enforce_admins` false. Today it returns 404 "Branch not protected".
**Why human:** A GitHub settings change needs the user's in-the-moment consent (D-17).

### 2. Post-verification main push CI (17-13 backstop)

**Test:** The orchestrator pushes main after /gsd-verify-work and records the run under `## Post-verification main push` in 17-13-SUMMARY.md.
**Expected:** Both jobs succeed for the main HEAD that lands.
**Why human:** This step is orchestrator-owned and runs after verification; "pending" is the expected state now.

### Re-verification 2026-11-15 (HEAD 21b3b906)

| Item | Verdict | Evidence |
|------|---------|----------|
| SAFE-01..09, CI-03 | resolved | 56 named tests from SC1-SC4 and the UAT `-k` list pass at HEAD (`uv run pytest tests -k <names> -n 4 --no-cov -q`, all dots); `installer/postinstall.py` still has no graphify hook |
| CI-01 | resolved | `gh run list --branch main`: CI success for 024817d3, d8c469f7, c597ea42 |
| Human 2: post-verification main push | resolved | 17-13-SUMMARY `## Post-verification main push`: e412b03, run 38710819886, ubuntu and macos success |
| Human 1 / CI-02: branch protection | needs owner confirmation | `gh api repos/castocolina/tools-installer/branches/main/protection` -> 404 Branch not protected; `rulesets` -> []. A GitHub settings change needs owner consent (D-17) |

jev (ladder) returned `empty_context` for both items, so the verdicts above are my own reasoning. No screen items exist in this phase, so no container run was needed.

### Needs owner confirmation

- None. CI-02 was applied on 2026-11-15 after the owner chose "apply now".

### Gaps Summary

There are no remaining gaps. The first pass's only blocker (17-18's own prohibition against new `type: ignore`) was fixed by 17-21 rather than overridden. That fix types `_uninstall_kwargs` precisely, removes all six ignores, type-checks clean, keeps the tests green, and passes the CI oracle on both OSes. The phase goal is achieved in code. Status is human_needed only because of the two by-design items above.

---

_Verified: 2026-10-15T08:55:22Z_
_Verifier: Claude (gsd-verifier)_

## CI-02 applied (2026-11-15)

The owner was asked and chose to apply branch protection now. The orchestrator ran the 17-13-SUMMARY.md
`gh api -X PUT repos/castocolina/tools-installer/branches/main/protection` body. Read-back:
`required_status_checks.contexts` = ["validate & test on ubuntu-latest", "validate & test on macos-latest"],
`enforce_admins.enabled` = false. SC5 and CI-02 are satisfied; the phase status is `passed`. Undo:
`gh api -X DELETE repos/castocolina/tools-installer/branches/main/protection`.

## jev classification of the re-verification findings (2026-11-15)

Ladder run 2026-11-15 (jev-fast-decision `ladder`, summaries only; TypeSafe under the 2026-10-14 consent). 

| Finding | Laya | TypeSafe | Verdict |
|---|---|---|---|
| CI-02 branch protection | open-real 0.45 (fallback) | resolved 0.97 | resolved (protection read back with both contexts) |
| Post-verification main push green | resolved 0.36 (fallback) | resolved 0.97 | resolved |
