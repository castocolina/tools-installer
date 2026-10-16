---
status: complete
phase: 18-registry-truth-and-drift-guard
source: [18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md, 18-04-SUMMARY.md, 18-05-SUMMARY.md, 18-06-SUMMARY.md, 18-07-SUMMARY.md, 18-08-SUMMARY.md, 18-09-SUMMARY.md, 18-10-SUMMARY.md, 18-11-SUMMARY.md, 18-12-SUMMARY.md, 18-13-SUMMARY.md, 18-14-SUMMARY.md, 18-15-SUMMARY.md, 18-16-SUMMARY.md, 18-17-SUMMARY.md, 18-18-SUMMARY.md, 18-19-SUMMARY.md, 18-20-SUMMARY.md, 18-21-SUMMARY.md, 18-22-SUMMARY.md, 18-23-SUMMARY.md, 18-24-SUMMARY.md, 18-25-SUMMARY.md, 18-26-SUMMARY.md, 18-27-SUMMARY.md]
started: 2026-10-16T02:15:00Z
updated: 2026-10-16T02:22:00Z
---

<!-- Autonomous run (playbook .planning/goals/2026-10-14-v0.50.0-phases-17-25.md: "never pause for UAT"):
     tests are derived from 18-VERIFICATION.md, the 18-SPEC.md acceptance criteria and the 18-NN-SUMMARY
     files. Each was resolved by the orchestrator against HEAD daf0524 (code = c58db6b) with the evidence
     named in `evidence:`; nothing was answered on the user's behalf. Targeted pytest runs below were
     re-run at HEAD with `-q --no-cov` (scratch HOME via conftest). Items only a human on real hardware
     can do are `skipped` with a reason and stay listed under human_verification in 18-VERIFICATION.md. -->

## Current Test

[testing complete]

## Tests

### 1. An unknown method key fails the registry load
expected: A method with a key outside its kind's closed set (e.g. `formula` on a `github_release`, or a key valid only for another kind) fails to load with the tool id and key in the message; a kind-only method loads when the kind allows it.
result: pass
evidence: pytest tests/test_model.py -k (unknown_method_key_names_the_tool_and_key, key_valid_for_another_kind_is_rejected, kind_only_method_loads) — 3 passed

### 2. Every tool carries a valid `verified` date
expected: Loading rejects a missing, string, integer, datetime or future `verified` value, and a `verified` key on a method table, naming the tool; the shipped registry loads with every tool dated.
result: pass
evidence: pytest -k (missing/string/integer/datetime/future_verified_is_rejected, verified_on_a_method_table_is_rejected, every_shipped_tool_declares_a_verified_date) — 7 passed; installer/registry.toml has 89 `[[tool]]` and 89 `verified =` lines

### 3. draw.io's CLI link is named by `cli_name` (macOS fixture)
expected: Installing the draw.io app links its CLI under `cli_name`; the plan shows the same name; a bad `cli_name` is rejected before any side effect.
result: pass
evidence: pytest -k (install_app_links_the_cli_under_cli_name, plan_app_uses_cli_name, cli_spec_rejects_a_bad_cli_name, install_app_rejects_bad_cli_name_before_side_effects) — 8 passed; CI macos-latest leg green (run 38839041957)

### 4. verify-registry reports drift
expected: The pre-fix difftastic asset template, a member missing from the archive, a downloaded hash mismatch and a checksum or pinned sha256 that disagrees with the GitHub digest are each reported as drift.
result: pass
evidence: pytest tests/test_verify_registry.py -k (prefix_difftastic_template_is_reported_as_drift, member_missing_from_archive_is_drift, downloaded_hash_mismatch_is_drift, checksum_file_disagreeing_with_the_digest_is_drift, pinned_sha256_differing_from_the_github_digest_is_drift) — 6 passed; 18-VERIFICATION live spot-check: pre-fix template exit 1 with 4x `asset missing (HTTP 404)`, fixed template exit 0

### 5. One drift issue, no issue when inconclusive, uncheckable kinds listed
expected: A second drift run edits the open `registry-drift` issue instead of opening another; a network failure is "inconclusive" and makes no gh call; script/brew/native-only tools appear under "Not checkable".
result: pass
evidence: pytest tests/test_verify_registry.py -k (second_drift_edits_the_open_issue, inconclusive_run_makes_no_gh_call, kinds_that_cannot_be_checked_are_listed) — 3 passed; .e2e-artifacts/verify-registry/final-check.log has a `## Not checkable` section (alacritty, brew, claude, docker, ...)

### 6. The weekly job runs outside the PR gate and cannot write the repo
expected: The verify-registry workflow triggers only on `schedule` and `workflow_dispatch`, has read-only contents permission, keeps its state cache, and ci.yml never runs it; `make verify-registry` is read-only by default.
result: pass
evidence: pytest tests/test_verify_registry_workflow.py tests/test_makefile.py -k verify_registry — 6 passed (runs_only_on_schedule_and_dispatch, job_cannot_write_the_repo, keeps_the_state_after_every_run, reports_drift_with_the_job_token, ci_workflow_never_runs_verify_registry, target_is_read_only_by_default)

### 7. First live verify-registry workflow run
expected: A dispatched run on the pushed main exits 0 with no drift (or 1 with exactly one `registry-drift` issue) and saves the state cache.
result: pass
evidence: run 38839643252 (workflow_dispatch, headSha daf0524) conclusion success; its log has `## Not checkable`, `## Notes`, `## Passed` and no `## Drift` section; `gh issue list --label registry-drift --state all` is empty; `gh cache list` shows key verify-registry-38839643252 (9.47 KiB). https://github.com/castocolina/tools-installer/actions/runs/38839643252

### 8. Release downloads verify by checksum, then digest, else say "unverified"
expected: An asset with no checksum installs when the GitHub digest matches; a digest mismatch fails with nothing linked; with neither, the install proceeds and the outcome and summary say "unverified" with the reason.
result: pass
evidence: pytest -k (release_digest_verifies_an_unchecksummed_asset, digest_mismatch_fails_with_nothing_linked, install_without_checksum_or_digest_is_unverified_with_a_reason, render_verification_prints_the_unverified_reason, engine_outcome_carries_the_unverified_reason) — 7 passed; final-check.log "Unverified at install" lists only gron and jless among github_release tools (no upstream digest, L-18-02) plus unpinned vendor URLs

### 9. A broken fresh binary falls through; a lone failing method links nothing
expected: A binary whose smoke run exits 127 falls through to the next method; with a single method the install fails and `~/.local/bin/<bin>` does not exist; a broken manager install also falls through and names the removal command without uninstalling; an existing good install is kept.
result: pass
evidence: pytest -k (smoke_failure_falls_through_to_the_next_method, single_failing_method_leaves_no_link, manager_install_with_a_broken_binary_falls_through, failed_manager_smoke_reports_the_removal_command_and_never_uninstalls, smoke_failure_keeps_an_existing_good_install) — 5 passed

### 10. The app launches without the dev venv; ruff resolves to its real owner
expected: Launch targets and install.sh use `uv run --isolated --no-dev`, test/validate keep dev deps; in a container, `make setup` resolves ruff to the real install, not `.venv/bin/ruff`.
result: pass
evidence: pytest tests/test_makefile.py tests/test_install_sh.py -k (launch_targets_run_without_the_dev_venv, every_setup_py_recipe_uses_the_launch_form, gate_targets_keep_dev_dependencies) — 3 passed; .e2e-artifacts/container/18-18-ruff-probe.log: control `/home/tester/workspace/.venv/bin/ruff`, launch-before `None`, launch-after `/home/tester/.local/bin/ruff`; `git log 17d404b..daf0524` on Makefile/setup.py/install.sh/harness/locations.py is empty; pass1 transcript on c58db6b shows `ruff: sha256 ✓`

### 11. macOS java/git stubs alone are not tools
expected: With only `/usr/bin/java` (no JDK) java is not installed and shows a reason; with a JDK from `/usr/libexec/java_home` it is installed; the same for git with and without Command Line Tools.
result: pass
evidence: pytest tests/test_status.py -k (java_stub, git_stub) — 4 passed (java_stub_alone_is_not_installed_with_a_reason, java_stub_with_a_real_jdk_is_installed, git_stub_without_clt_is_not_installed, git_stub_with_clt_is_installed); CI macos-latest leg green (run 38839041957)

### 12. Versions are never fabricated
expected: `-1` gives no version; lazygit's `version=0.44.1, ...` gives `0.44.1`; procs' quoted `"0.14.6"` gives `0.14.6`.
result: pass
evidence: pytest tests/test_versions.py -k (observed_version_fixture_table, parse_version_never_fabricates_from_a_bare_flag) — 14 passed; 18-VERIFICATION spot-check: parse_version('-1') -> None, procs -> 0.14.6, lazygit -> 0.44.1

### 13. The audit data fixes are applied and `managed-download` is gone
expected: Every C/D/E/F audit data fix is backed by a test or a verify-registry pass, and `rg managed-download installer/` finds nothing.
result: pass
evidence: pytest -k audit_fix_ — 30 passed (C1..C8, D1..D7, E2..E11, F1..F8); remaining ledger rows (C7/E9 optional in the audits, C9 superseded by `verified`, E1/E3 already done, Sublime member from Phase 17) dispositioned in the 18-08-SUMMARY 35-row ledger; `rg -n managed-download installer/` rc 1 (no match)

### 14. One draw.io row; a stale `drawio-cli` id is ignored
expected: The registry has no `drawio-cli`; settings or caches that still name it load without error, and an existing install shows under drawio-desktop.
result: pass
evidence: pytest -k (drawio_desktop_is_the_only_drawio_row, stale_drawio_cli_cache_entry_is_ignored, existing_drawio_install_shows_under_drawio_desktop) — 3 passed; `grep -c drawio-cli installer/registry.toml` = 0

### 15. Pins are bumped, templated and dated
expected: verify-registry reports no "newer stable" for any checkable entry; pinned app/tarball URLs use `{ver}` with an explicit `version`; dates are written only for passing entries; a renamed candidate asset keeps the old pin.
result: pass
evidence: .e2e-artifacts/verify-registry/final-check.exit = EXIT 0; final-check.log has no "newer stable release" line (only the expected `sublime: newer stable: no release source` notes); sublime 4215 (3 methods) and drawio-desktop 32.4.1 (2 methods) URLs all use `{ver}`; pytest tests/test_verify_registry.py -k (pinned_github_url_behind_latest_is_newer_stable_drift, unpinned_github_release_never_reports_newer_stable, write_dates_only_passing_tools, renamed_candidate_asset_keeps_the_old_pin, unpinned_entries_never_gain_pin_keys) — 5 passed

### 16. Full lifecycle in a disposable container
expected: `make e2e` installs the catalog, re-runs idempotently, uninstalls, reinstalls and tears the container down with no failures; draw.io installs checksummed and its AppImage smoke passes headless.
result: pass
evidence: make e2e on c58db6b: .e2e-artifacts/container/pass1-transcript.log `PASS1_COUNTS installed=74 already=0 failed=0 ... manual_required=8 setup_exit=0`, `TRACER_CLEAN_INSTALL_OK`, `drawio-desktop: sha256 ✓`; pass2-transcript.log `TRACER_RERUN_OK`, `TRACER_UNINSTALL_OK`, `TRACER_REINSTALL_OK installed=39 failed=0`, `TRACER_CONTAINER_TEARDOWN_OK`; 18-18-drawio-diagnosis.log: headless extract `--version` prints 32.4.1 exit 0 (plain `--version` without a display exits 127, which is why drawio-desktop declares `smoke_argv`, `test_drawio_desktop_declares_its_smoke_argv`)

### 17. Local quality gates are green on the final tree
expected: `make validate` and `make test` pass on the tree that was committed; the phase's validation commands all pass.
result: pass
evidence: orchestrator on c58db6b/daf0524: make validate x2 rc 0, make test x2 3949 passed / 4 skipped, pre-commit --all-files rc 0; 18-VALIDATION 14/14 commands pass

### 18. CI green on ubuntu and macOS
expected: The CI run for the pushed main shows both `validate & test` jobs success, including the macOS-fixture tests.
result: pass
evidence: main pushed ab23f33..daf0524; run 38839041957 on daf0524 — `validate & test on ubuntu-latest` success, `validate & test on macos-latest` success. https://github.com/castocolina/tools-installer/actions/runs/38839041957

### 19. Real-Mac draw.io pinned app install and smoke
expected: On a Mac without the draw.io cask, the pinned app method links `~/.local/bin/drawio` to Contents/MacOS/draw.io, the `--version` smoke leaves no GUI window open, and the java/git stubs alone show as not installed.
result: skipped
reason: needs a real macOS host; backstop: CI macos-latest unit tests (run 38839041957, test 3 and test 11 fixtures). Stays under human_verification in 18-VERIFICATION.md; `executors.smoke_binary` records the macOS app-CLI smoke as not verified.

## Summary

total: 19
passed: 18
issues: 0
pending: 0
skipped: 1
blocked: 0

## Gaps

[none]
