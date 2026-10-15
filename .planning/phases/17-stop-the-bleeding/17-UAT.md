---
status: complete
phase: 17-stop-the-bleeding
source: [17-01-SUMMARY.md, 17-02-SUMMARY.md, 17-03-SUMMARY.md, 17-04-SUMMARY.md, 17-05-SUMMARY.md, 17-06-SUMMARY.md, 17-07-SUMMARY.md, 17-08-SUMMARY.md, 17-09-SUMMARY.md, 17-10-SUMMARY.md, 17-11-SUMMARY.md, 17-12-SUMMARY.md, 17-13-SUMMARY.md, 17-14-SUMMARY.md, 17-15-SUMMARY.md, 17-16-SUMMARY.md, 17-17-SUMMARY.md, 17-18-SUMMARY.md, 17-19-SUMMARY.md, 17-20-SUMMARY.md, 17-21-SUMMARY.md]
started: 2026-10-15T08:58:00Z
updated: 2026-10-15T08:58:29.959Z
---

<!-- Autonomous run (playbook .planning/goals/2026-10-14-v0.50.0-phases-17-25.md: "never pause for UAT"):
     every test below was executed by the orchestrator against HEAD 4db5f21 (code = a34fa30) with the
     evidence named in `evidence:`; nothing was answered on the user's behalf. Items only a human can do
     are `skipped` with a reason and stay listed under human_verification in 17-VERIFICATION.md and the
     RUN-LEDGER "Deferred questions / human verification" table. -->

## Current Test

[testing complete]

## Tests

### 1. A directory member is refused and links nothing
expected: A download or app method whose member is a directory fails with an error and leaves no link in ~/.local/bin; an update to a directory member rolls back and reports failure.
result: pass
evidence: pytest -k (directory_links_nothing, directory_member_falls_through_the_ladder, directory_member_rolls_back, directory_cli_rolls_back) — 4 passed

### 2. Reinstall over a link-to-directory leaves the target untouched
expected: Reinstalling over an existing ~/.local/bin link that points at a directory or a foreign file replaces the link itself; the target's files stay byte-identical.
result: pass
evidence: pytest -k (reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical, replaces_a_link_instead_of_writing_through_it) — 3 passed

### 3. graphify install/update leaves the working directory empty
expected: Installing or updating graphify runs no host registration, so an empty cwd stays empty.
result: pass
evidence: pytest -k (installing/updating_graphify_runs_no_host_registration) — 2 passed; registry postinstall removed (RUN-LEDGER Q1)

### 4. Uninstall deletes only proven artifacts; the rest is "remove it yourself"
expected: Neither `--uninstall --yes` nor the TUI deletes the uv-tool ruff symlink, a pip yq file or the shared drawio file; each is listed for manual removal on one copyable line; a looping link does not crash; a path changed since the preview is refused and reported.
result: pass
evidence: pytest -k (deletes_only_proven_artifacts, tui_and_cli_delete_the_same_set, refuses_paths_changed_since_the_preview, survives_looping_link, only_unproven_matches_still_lists_them) — 7 passed; make e2e pass2 TRACER_UNINSTALL_OK (91952dd); CI macOS green (run 38708267552)

### 5. rc writes are atomic and the duplicate cleaner rechecks
expected: An injected rc write failure leaves the original file byte-identical; `clean_rc_duplicates` refuses a file edited between preview and confirm.
result: pass
evidence: pytest -k (ban_aliases_write_failure_leaves_the_rc_byte_identical, clean_rc_duplicates_refuses_a_file_edited_between_preview_and_confirm) — 2 passed

### 6. Failures are red and exit 1; non-failures exit 0
expected: A worker exception mid-run shows a red "Failed" status and exits 1; a failed update (also from the catalog `u` key) is red and exits 1; ctrl+c during a run exits 1; a skipped in-flight update is a failure on neither the screen nor the exit code; a completed update stays done after a refresh crash; a cancelled run followed by a clean re-run exits 0.
result: pass
evidence: pytest -k (worker_exception_marks_the_run_failed, failed_update_exits_1, tui_routes_exit_1_when_the_session_failed, failed_direct, ctrl_c_while, in_flight_latch_skip_is_a_failure_on_neither, completed_update_stays_done, cancelled_run_then_a_successful_rerun) — 14 passed

### 7. A vendor script that opens /dev/tty fails fast
expected: An install child that tries to read the terminal fails fast instead of hanging the TUI.
result: pass
evidence: pytest -k (tty_reader_fails_fast, output_timeout_fails_fast) — 3 passed

### 8. A damaged settings.json warns and is left untouched
expected: Launch with invalid UTF-8 or invalid JSON in settings.json reaches the first screen with an "Ignoring invalid settings file" warning (TUI and every headless route), and the file stays byte-identical.
result: pass
evidence: pytest -k (invalid_utf8_returns_defaults_and_a_warning, invalid_settings_file_launches_to_the_first_screen_with_a_warning, damaged_settings_json_warns_before_acting) — 5 passed; tmux check on the real setup.py (RUN-LEDGER row): warning shown, file byte-identical after quit

### 9. Enter executes the selection on every route
expected: Enter in a catalog runs the accepted selection on the doctor, fix, uninstall and guard routes.
result: pass
evidence: pytest -k test_every_tui_route_executes_the_accepted_selection — 5 passed

### 10. Link-mode change moves active policies safely
expected: With a ban and a tweak active, centralized → split removes their blocks from the old mode's rc and writes them where the new mode sources; foreign rc bytes are untouched; the live mode is a no-op; a partial failure restores cleanly and names what it could not restore; an uninstalled policy is not resurrected; split → centralized reports the exact PATH-wiring action.
result: pass
evidence: pytest -k (moves_ban_and_tweak_to_split, keeps_foreign_rc_bytes_identical, not_link_mode_aware, after_an_uninstall_does_not_resurrect, split_to_centralized_move_reports, live_mode_is_a_no_op, could_not_restore, partial_new_mode_write) — 8 passed

### 11. Doctor reports broken ~/.local/bin links with safe repair text
expected: The Doctor view lists a dangling ~/.local/bin link and its repair is conditional ("If tools-installer installed it, remove ..."), never an unconditional delete; the audit changes nothing.
result: pass
evidence: pytest -k (broken_link_guidance_names_the_opt_dir_repair, run_doctor_reports_broken_links_and_changes_nothing, broken_link_guidance_never_escalates) — 3 passed; tmux check: view 4 showed the dangling `ghost` link with the conditional repair

### 12. Full lifecycle in a disposable container
expected: `make e2e` installs the catalog, re-runs idempotently, uninstalls, reinstalls and tears the container down with no failures.
result: pass
evidence: make e2e rc 0 on 91952dd (try 2; try 1 failed only on a transient curl 56): PASS1 installed=73 failed=0; TRACER_RERUN_OK, TRACER_UNINSTALL_OK, TRACER_REINSTALL_OK installed=37 failed=0, TRACER_CONTAINER_TEARDOWN_OK

### 13. CI green on ubuntu and macOS
expected: The final tree's CI run shows both `validate & test` jobs success.
result: pass
evidence: run 38708267552 on a34fa30 — ubuntu-latest=success, macos-latest=success (17-13-SUMMARY)

### 14. 16-17..16-19 carry secure and validate re-audit records
expected: The v0.49.0 phase 16 SECURITY and VALIDATION files record the re-audit of plans 16-17..16-19.
result: pass
evidence: 17-12-SUMMARY; 17-VERIFICATION SC5 (CI-03 satisfied); 16-VALIDATION commands n=15, 0 failed

### 15. Merges to main require the PR check (branch protection)
expected: main is protected with the two CI contexts required and enforce_admins false.
result: skipped
reason: User action by policy (D-17, SPEC R12); this autonomous run records CI-02 as "skip" (RUN-LEDGER) and hands the exact `gh api` command to the user in 17-13-SUMMARY `## Left for the user (CI-02)`; tracked under human_verification.

## Summary

total: 15
passed: 14
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps

[none]
