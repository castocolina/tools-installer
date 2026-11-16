---
phase: "18"
slug: registry-truth-and-drift-guard
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_total: 99
threats_closed: 99
threats_open: 0
threats_open_nonblocking: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
audited_head: 344b8f5
reverified_head: 342c7f1
created: "2026-10-15"
---

# Phase 18 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

The register comes from the `<threat_model>` blocks of 18-01..18-27-PLAN.md: T-18-01..T-18-98 plus T-18-SC, which appears in every plan and is counted once. Each `mitigate` threat was checked in the code at the cited line and against a named test. The cited tests were run on this tree: `uv run --frozen pytest --no-cov -n 4 -k <names>`, 214 selected items, all passed. The configured level is ASVS L1. The areas the orchestrator flagged got deeper traces (L2/L3): archive symlink escapes, the L-18-19 ownership proof, token handling, registry write integrity and the smoke run. Those traces found two gaps, T-18-56 and T-18-69. Gap plan 18-28 closed both; the re-verification is below. Line numbers cite 344b8f5, except the T-18-56/T-18-69 evidence, which cites 342c7f1.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| registry.toml -> `model.load_tools` | data decides which params, pins, link names and smoke argv executors receive | repo data (trusted, reviewed) |
| release download host -> staging -> `~/.local/opt`, `~/.local/bin`, `~/Applications` | untrusted bytes cross into user bin/opt/app dirs on install and update | untrusted archives and binaries |
| freshly downloaded binary -> smoke execution | the installer runs upstream code once before linking | untrusted code execution |
| installer -> pre-existing `~/.local/opt/<name>` / `~/Applications/<App>` | files the installer did not prove it created (L-18-19) | user data |
| child stdout/stderr -> messages and TUI report | untrusted bytes of arbitrary length | untrusted text |
| GitHub API / CDN / vendor hosts -> verify-registry verdicts | flaky or hostile network answers decide drift vs ok | untrusted metadata |
| GitHub token -> outbound requests | the token must reach api.github.com only | credential |
| verify-registry `--write` -> installer/registry.toml | the only repo-writing path | trusted data file |
| weekly GitHub Actions job -> repository and issues | job token scoped by `permissions` | credential, markdown issue body |
| e2e container -> developer host | downloaded binaries run only inside a disposable container | untrusted code execution |
| agent edit tool -> tracked rule documents | an automated edit can truncate binding doctrine | repo docs |

---

## Threat Register

*Status: closed · open — below high threshold (non-blocking). Paths are relative to the repo root; `vr` = `installer/verify_registry.py`, `tvr` = `tests/test_verify_registry.py`.*

| Threat ID | Category | Component | Severity | Disposition | Mitigation evidence (code; test) | Status |
|-----------|----------|-----------|----------|-------------|----------------------------------|--------|
| T-18-01 | Tampering | opaque method params | medium | mitigate | `installer/model.py:42` METHOD_PARAMS; `:726-729` raises naming tool and key. `tests/test_model.py::test_unknown_method_key_names_the_tool_and_key`, `::test_key_valid_for_another_kind_is_rejected` | closed |
| T-18-02 | Repudiation | `verified` claim | low | mitigate | `model.py:700-709` (`type(...) is date`, limit today+1). `test_model.py::test_missing/string/integer/datetime/future_verified_is_rejected` | closed |
| T-18-03 | Tampering | `{ver}` url without digest | medium | mitigate | `model.py:730-744` (needs `version` + 64-hex `sha256`, `:182`); verified at install by T-18-45/T-18-25. `test_model.py::test_pinned_url_requires_version_and_sha256`, `::test_pinned_sha256_must_be_64_lowercase_hex` | closed |
| T-18-04 | Spoofing | version parser | low | mitigate | `installer/versions.py:100` prefix < 2 chars or non-alpha rejected. `tests/test_versions.py::test_parse_version_never_fabricates_from_a_bare_flag`, `::test_observed_version_fixture_table` | closed |
| T-18-05 | Elevation of Privilege | macOS stub probe | low | mitigate | `installer/status.py:14-17` closed table, absolute argv; `:22-26` via `run_output` (`run.py:95-96` DEVNULL stdin, new session; 5 s). `tests/test_status.py::test_every_stub_probe_is_an_absolute_path`, `::test_java_stub_alone_is_not_installed_with_a_reason` | closed |
| T-18-06 | Spoofing | Rich markup in stub reason | low | mitigate | `installer/render.py:59` `escape(status.reason)`. `tests/test_audit.py::test_audit_row_shows_the_stub_reason`. Test gap: no reason fixture contains markup | closed (test gap) |
| T-18-66 | Repudiation | stub probe run twice | low | mitigate | `installer/audit.py:34` reason only for missing rows; `render.py:56-61`. `test_audit.py::test_audit_asks_for_a_reason_only_for_missing_rows`, `::test_audit_row_is_plain_missing_when_the_stub_probe_now_passes` | closed |
| T-18-07 | Tampering | `cli_name` path | medium | mitigate | `installer/apps.py:56-88` `cli_spec` (bare name, no `.`/`..`), called at `:133` before any dir creation. `tests/test_apps.py::test_cli_spec_rejects_a_bad_cli_name`, `::test_install_app_rejects_bad_cli_name_before_side_effects` | closed |
| T-18-08 | Tampering | install/uninstall link name | low | mitigate | one reader `apps.cli_spec`, used by `installer/uninstall.py:48`. `tests/test_uninstall.py::test_plan_app_uses_cli_name` | closed |
| T-18-09 | Spoofing | dev venv ruff shadows host | medium | mitigate | `Makefile:15-35`, `install.sh:88`, `scripts/container-e2e-verify.sh:198,263` use `uv run --isolated --no-dev`. `tests/test_makefile.py::test_launch_targets_run_without_the_dev_venv`; 18-18 container probe (control `.venv/bin/ruff`, launch-after `~/.local/bin/ruff`) | closed |
| T-18-10 | Tampering | `--exact` alternative | low | accept | AR-18-02; `--exact` is in no launcher (grep) | closed |
| T-18-55 | Spoofing | activated venv on PATH | medium | mitigate | `setup.py:1558` `drop_project_venv_from_path` before `main`; `installer/locations.py:111`. `tests/test_locations.py::test_setup_entry_point_drops_the_project_venv_before_main`, `::test_drop_project_venv_from_path_removes_only_the_project_venv` | closed |
| T-18-11 | Elevation of Privilege | PATH-plantable owner probe | medium | mitigate | `rg managed-download installer/` -> no match. `tests/test_registry.py::test_removed_owner_probe_is_rejected_at_load` | closed |
| T-18-12 | Spoofing | moved upstream repos | medium | mitigate | `registry.toml:942-958` `gitui-org/gitui`, `:1289-1297` `tealdeer-rs/tealdeer`; digests via T-18-13; 18-15 final-check exit 0. `test_registry.py::test_audit_fix_d4_gitui_uses_the_org_repo_and_ships_macos`, `::test_audit_fix_d5_tealdeer_uses_the_org_repo` | closed |
| T-18-13 | Tampering | swapped release asset | high | mitigate | `installer/download.py:286-315` checksum file -> pinned sha256 -> API digest, `ChecksumMismatch` `:314`, before `_replace_*` (`:237-249`); `installer/engine.py:226-230` halts the ladder. `tests/test_engine.py::test_digest_mismatch_fails_with_nothing_linked`, `::test_checksum_mismatch_halts_the_ladder_by_default`, `tests/test_download.py::test_verified_mismatch_raises_and_cleans_up` | closed |
| T-18-14 | Tampering | tag and digest from two snapshots | medium | mitigate | `versions.py:388-401` one `/releases/latest` read -> `Release(tag, digests)`; `download.py:117-131`. `test_versions.py::test_resolve_github_release_reads_one_snapshot` | closed |
| T-18-15 | Repudiation | unverified install reported fine | low | mitigate | `engine.py:249-257` outcome carries `unverified_reason`; `render.py:315`. `test_engine.py::test_engine_outcome_carries_the_unverified_reason`, `tests/test_render.py::test_render_verification_prints_the_unverified_reason` | closed |
| T-18-77 | Repudiation | unhashed tarball marked verified | medium | mitigate | `download.py:160` `UNPINNED_REASON` when no pin. `test_download.py::test_unhashed_tarball_install_is_unverified_with_a_reason` | closed |
| T-18-65 | Tampering | wrapped resolver drops digests | medium | mitigate | `test_engine.py::test_default_resolver_verifies_against_the_api_digest` (production default, only `urlopen` faked); `test_versions.py::test_production_paths_select_the_real_release_resolver` (signature + setup.py AST pin). Residual IN-04 deferred (see Residuals) | closed |
| T-18-17 | Tampering | duplicate superpowers route | low | mitigate | `test_registry.py::test_audit_fix_f5_superpowers_has_one_claude_route` | closed |
| T-18-18 | Tampering | new jetbrains arm64 / draw.io Linux downloads | medium | mitigate | draw.io Linux has a checksum file (E7); jetbrains appears in "Unverified at install" in the 18-15 final check. `test_registry.py::test_audit_fix_e7_drawio_linux_release_is_checksummed`, `tvr::test_report_lists_methods_that_would_install_unverified` | closed |
| T-18-52 | Elevation of Privilege | kitty macOS script, `/Applications` | low | mitigate | `registry.toml:2714-2720`; 18-08-SUMMARY E8 quote. Auditor re-fetch of `installer.sh` on 2026-10-15 (208 lines): no `sudo`/`doas`/`pkexec`, dest `/Applications` at line 67. `test_registry.py::test_audit_fix_e8_kitty_script_covers_macos` | closed |
| T-18-19 | Elevation of Privilege | smoke of a tampered download | high | mitigate | verification `download.py:237` precedes smoke `:354` (archive) / `:324` (raw); apps hash `:168-176` precedes smoke `apps.py:188`. `test_download.py::test_mismatch_never_runs_the_staged_binary` | closed |
| T-18-21 | Denial of Service | GUI window / hang during smoke | low | mitigate | `installer/executors.py:107-110` drops DISPLAY/WAYLAND_DISPLAY; `installer/run.py:87-100` DEVNULL stdin, new session, timeout -> 124 counts as executed. `tests/test_executors.py::test_smoke_binary_hides_the_display`, `::test_smoke_binary_passes_on_timeout`, `tests/test_run.py::test_run_output_unbounded_by_default`. macOS limit recorded (`executors.py:101-104`) | closed |
| T-18-22 | Tampering | half-swapped install | medium | mitigate | `download.py:346-357` smoke on `.new` before the aside-move; failure removes `.new` only. `test_download.py::test_smoke_failure_keeps_an_existing_good_install` | closed |
| T-18-53 | Elevation of Privilege | archive member symlink outside staging | high | mitigate | `executors.py:65-76` `staged_member` (strict resolve, `is_relative_to`, regular file), called at `download.py:348` before chmod `:350` and smoke `:354`; the root is the installer-created `.new` (`:342`, `:405`). `test_download.py::test_member_symlink_outside_staging_is_rejected` (mode stays 0644, marker absent, no `.new`, no link). The app-bundle variant is T-18-56 | closed |
| T-18-54 | Tampering | partial `.new` tree | low | mitigate | `download.py:346-357` one cleanup `try`; `installer/atomic.py:78-115` backstop. `test_download.py::test_failed_extraction_leaves_no_staged_tree` | closed |
| T-18-67 | Spoofing | wrapper exits 0 over a loader failure | medium | mitigate | `executors.py:112`, `:120-123` loader check on exit 0. `test_executors.py::test_smoke_binary_fails_on_a_loader_error_even_on_exit_0`, `::test_smoke_binary_passes_with_other_stderr_on_exit_0` | closed |
| T-18-78 | Tampering | dangling link after a failed fresh install | low | mitigate | `download.py:431-434`. `test_download.py::test_fresh_install_failure_after_relink_leaves_no_link` | closed |
| T-18-23 | Tampering | hand-edited cache digests | low | mitigate | `installer/version_cache.py:101-113` keeps only 64-hex values. `tests/test_version_cache.py::test_malformed_digests_are_dropped_not_fatal` | closed |
| T-18-24 | Denial of Service | one bad digest pair drops the entry | low | mitigate | `version_cache.py:104-113` pair by pair. `::test_mixed_digests_keep_the_valid_entries` | closed |
| T-18-25 | Tampering | swapped app zip | high | mitigate | `apps.py:168-176` sha256 of the staged zip before `ditto` `:178`; `ChecksumMismatch`; nothing moved. `test_engine.py::test_pinned_app_mismatch_moves_nothing`, `test_apps.py::test_pinned_app_is_verified_and_installed` | closed |
| T-18-26 | Elevation of Privilege | smoke of an unverified zip's CLI | medium | mitigate | smoke `apps.py:188` only after the hash check; unpinned -> `_UNVERIFIED_REASON` `:230`. `test_apps.py::test_unpinned_app_installs_unverified_with_a_reason`, `::test_app_smoke_uses_the_declared_argv` | closed |
| T-18-27 | Tampering | `sh -c` url pipeline | low | mitigate | `apps.py:167`, `:178` plain argv; no `sh -c` in apps/download/verify_registry. `test_apps.py::test_install_app_uses_plain_curl_and_ditto_argv` | closed |
| T-18-56 | Tampering | staged app CLI resolves outside the bundle | medium | mitigate | `apps.py:182-183` refuses a staged bundle that is a symlink or not a real directory (58abaf9), before `staged_member` + `X_OK` (`:186-188`), smoke and swap. `test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing` (4 cases), `::test_staged_cli_symlink_outside_the_bundle_is_rejected`, `::test_non_executable_staged_cli_moves_nothing` (see 18-28 re-verification) | closed |
| T-18-79 | Tampering | dangling CLI link after a failed fresh app install | low | mitigate | `apps.py:260-263`. `test_apps.py::test_fresh_app_install_failure_after_relink_leaves_no_cli_link` | closed |
| T-18-28 | Tampering | traversal during the member check | medium | mitigate | `vr:500-506` lists names only (`getnames`/`namelist`); `vr:718`, `:762` temp dir per download. `tvr::test_zip_and_app_members_are_listed_not_extracted` | closed |
| T-18-30 | Tampering | stale or forged state file | low | mitigate | `vr:558-571` fingerprint (checksum, digest, pin+HEAD, HEAD); `vr:828-854` state pop on url-wide failure. `tvr::test_changed_bytes_under_an_unchanged_pin_are_downloaded_again`, `::test_changed_digest_triggers_a_download`, `::test_cache_miss_downloads_every_asset_once` | closed |
| T-18-80 | Repudiation | autodetecting reader certifies a wrong `archive` | medium | mitigate | `vr:504-506` explicit `r:gz`/`r:xz`; `vr:803-811` drift `archive unreadable as <mode>`. `tvr::test_declared_archive_type_mismatch_is_drift` | closed |
| T-18-81 | Repudiation | cached ok survives a later url failure | low | mitigate | `vr:828-854` post-walk override. `tvr::test_a_fresh_checksum_mismatch_overrides_every_cached_ok_on_the_url` (a_first / b_first) | closed |
| T-18-31 | Information Disclosure | token to download hosts | low | mitigate | `vr:1531-1544` HEAD/download build bare Requests (the token is not in their closure); `versions.py:362` host check. `tvr::test_explicit_token_is_sent_to_api_github_only`, `test_versions.py::test_urlopen_fetch_never_sends_the_token_to_another_host`. Test gap: `default_probe` head/download not exercised | closed (test gap) |
| T-18-57 | Repudiation | shared url checked once | high | mitigate | `vr:415-446` per (tool, url, member, archive, strip, raw) target; `vr:760-790` one download per url feeds every target. `tvr::test_shared_url_with_different_members_checks_each_member`, `::test_a_new_member_on_a_known_url_is_downloaded` | closed |
| T-18-68 | Repudiation | cached ok survives a strip/archive/raw edit | high | mitigate | `vr:209-220` `state_key` carries tool id + extraction settings. `tvr::test_a_strip_change_invalidates_the_cached_ok`, `::test_targets_differing_only_in_strip_are_checked_separately` | closed |
| T-18-69 | Denial of Service | corrupt archive aborts the check | medium | mitigate | `vr:772-779` TarError/EOFError/BadZipFile/`lzma.LZMAError`/`zlib.error` -> drift `archive unreadable`, no state (b4af643). `tvr::test_corrupt_archive_is_drift` (gz, zip, xz_corrupt_stream, gz_bad_deflate_block), `::test_corrupt_archive_is_drift_truncated_tar` (see 18-28 re-verification) | closed |
| T-18-32 | Tampering | writer corrupts the registry | high | mitigate | `vr:1034-1051` scoped line rewrite + tomllib re-parse equality guard; `vr:1621` `atomic_write_text`. `tvr::test_writer_guard_refuses_an_edit_that_breaks_the_toml`, `::test_writer_guard_refuses_an_edit_that_changes_another_value`, `::test_writer_keeps_every_other_byte` | closed |
| T-18-33 | Tampering | bump to a swapped/renamed asset | medium | mitigate | `vr:1311-1325` the candidate must pass the full check, else the old pin stays. `tvr::test_renamed_candidate_asset_keeps_the_old_pin` | closed |
| T-18-34 | Repudiation | `verified` written for failing entries | medium | mitigate | `vr:1347-1348` dates only from `passed_tools()` (`vr:148-156`); the workflow never passes `--write`. `tvr::test_write_dates_only_passing_tools`, `tests/test_verify_registry_workflow.py::test_verify_registry_job_cannot_write_the_repo` | closed |
| T-18-58 | Repudiation | `--write` report disagrees with the file | medium | mitigate | `vr:1211-1247`, `:1612`. `tvr::test_write_run_after_a_bump_reports_the_registry_as_written` | closed |
| T-18-70 | Repudiation | failed `--candidate` still dated | medium | mitigate | `vr:1228-1240` unapplied bump adds drift. `tvr::test_one_failing_method_blocks_the_whole_tool_bump` | closed |
| T-18-71 | Repudiation | superseded old-pin drift | medium | mitigate | `vr:1219-1225` replaced by old pinned urls only. `tvr::test_bump_replaces_the_findings_of_the_superseded_pin_targets`, `::test_github_app_pin_bump_matches_findings_by_app_cli_member` | closed |
| T-18-82 | Repudiation | bump decided on unrelated findings | medium | mitigate | `vr:1130-1153` candidate copy holds pinned methods only. `tvr::test_bump_keeps_the_findings_of_the_tools_unpinned_methods` | closed |
| T-18-35 | Elevation of Privilege | weekly job writes or pushes | high | mitigate | `.github/workflows/verify-registry.yml:13-15` `contents: read`, `issues: write`; `:39` `--issue` only; `Makefile:35`. `test_verify_registry_workflow.py::test_verify_registry_job_cannot_write_the_repo`, `::test_verify_registry_runs_only_on_schedule_and_dispatch`, `::test_ci_workflow_never_runs_verify_registry` | closed |
| T-18-36 | Spoofing | asset names inject markdown | low | mitigate | `vr:1370-1426` every upstream value in `code_span`; `vr:1457-1477` `--body-file`. `tvr::test_issue_body_never_breaks_out_of_a_code_span` | closed |
| T-18-73 | Spoofing | backtick/newline breaks the code span | low | mitigate | `vr:1352-1367` control chars -> space, fence longer than any run. `tvr::test_issue_code_span_picks_a_safe_delimiter`, `::test_issue_body_never_breaks_out_of_a_code_span` | closed |
| T-18-37 | Information Disclosure | token in argv, logs or body | medium | mitigate | `verify-registry.yml:21-22` job env; `gh` reads env; upsert argv `vr:1430-1477` carries no token. `tvr::test_issue_body_carries_no_environment_values`. Residual IN-05 deferred | closed |
| T-18-38 | Repudiation | rate-limited run reported clean / noise issues | low | mitigate | `vr:135-146` exit code; `vr:1628` issue only on exit 1. `tvr::test_inconclusive_run_makes_no_gh_call`, `::test_inconclusive_without_drift_exits_2`, `::test_blocked_run_with_confirmed_drift_still_updates_the_issue` | closed |
| T-18-51 | Denial of Service | state never saved | low | mitigate | `verify-registry.yml:30-45` split restore/save, `if: always()`, step 25 < job 30 min, Thursday cron; `vr:825-826` save after each verified target. `test_verify_registry_workflow.py::test_verify_registry_job_keeps_the_state_after_every_run`, `tvr::test_state_is_saved_after_each_verified_asset` | closed |
| T-18-39 | Tampering | trust-on-first-use pin hash | medium | mitigate | draw.io pins come from GitHub digests and are cross-checked against the download (`vr:1138-1147`, `:791`); Sublime comes over TLS from the vendor; 18-15-SUMMARY.md:136-137 lists the hashes, which match `registry.toml:2926`, `:2936` and the Sublime pins | closed |
| T-18-41 | Information Disclosure | maintainer gh token | medium | mitigate | `vr:1503-1513` in-process `gh auth token` (the token is output, never argv); `vr:1528` used by `urlopen_fetch` only; 18-15-SUMMARY:181 "No token was logged or pasted". `tvr::test_main_never_prints_the_token` | closed |
| T-18-42 | Tampering | `--write` changes other bytes | medium | mitigate | guard per T-18-32; registry diff of commit 429b383 is only `sha256` x5, `version` x5 and `verified` x47 lines, plus the recorded gh `strip` data fix | closed |
| T-18-16 | Tampering | registry url in a shell string | low | mitigate | `download.py:291`, `:296` plain `curl ... -- <url>` argv. `test_download.py::test_unverified_install_fetches_into_staging_with_a_plain_argv` | closed |
| T-18-44 | Tampering | update installs unverified bytes | medium | mitigate | `download.py:268-281` `update_download` uses the same `_fetch_verified`. `test_download.py::test_update_verifies_the_release_digest`, `::test_checksum_mismatch_during_update_leaves_live_untouched`, `tests/test_update.py::test_installer_owned_update_rejects_a_wrong_api_digest` | closed |
| T-18-63 | Tampering | declared sha256 silently dropped | medium | mitigate | `download.py:153-160`. `test_download.py::test_supplied_sha256_is_never_discarded` | closed |
| T-18-45 | Tampering | pinned tarball swapped upstream | medium | mitigate | `download.py:304-314` before extraction. `test_download.py::test_pinned_tarball_is_verified_against_its_sha256` | closed |
| T-18-29 | Repudiation | rate limit read as "no drift" | medium | mitigate | `vr:858-868` blocked; failed reads become findings, never `ok`. `tvr::test_rate_limit_without_drift_blocks_the_run`, `::test_no_network_blocks_the_run`, `::test_all_failed_requests_without_release_reads_block_the_run` | closed |
| T-18-83 | Repudiation | block suppresses confirmed drift | high | mitigate | `vr:142-143` drift -> 1 even when blocked; `vr:1376-1377` note. `tvr::test_blocked_run_still_reports_confirmed_drift` | closed |
| T-18-46 | Repudiation | one flaky host hides drift | medium | mitigate | `vr:142-146`. `tvr::test_one_flaky_host_does_not_hide_drift` | closed |
| T-18-47 | Information Disclosure | token leaks to output or another host | medium | mitigate | `versions.py:362-363`; `vr:1527-1546`. `tvr::test_main_never_prints_the_token`, `::test_explicit_token_is_sent_to_api_github_only` | closed |
| T-18-48 | Repudiation | unverified methods invisible | low | mitigate | `vr:1396-1404` section on every run. `tvr::test_report_lists_methods_that_would_install_unverified`, `::test_unverified_section_says_none_when_everything_verifies` | closed |
| T-18-59 | Repudiation | plain 403 blocks the run | high | mitigate | `vr:254-263` rate limit only on 429 or 403 + `X-RateLimit-Remaining: 0`/`Retry-After`; `vr:279-285` other 403 per repo. `tvr::test_forbidden_without_rate_limit_evidence_does_not_block` | closed |
| T-18-72 | Repudiation | HTTP answers counted as an outage | high | mitigate | `vr:640-647`, `vr:858-868` only no-response failures + rate limits block. `tvr::test_http_answers_never_block_the_run`, `::test_forbidden_without_rate_limit_evidence_does_not_block` | closed |
| T-18-60 | Spoofing | older tag reported as newer | medium | mitigate | `vr:319-338` `is_outdated`; incomparable -> inconclusive. `tvr::test_older_or_equal_latest_tag_is_not_newer_stable`, `::test_incomparable_latest_tag_is_reported_separately` | closed |
| T-18-40 | Elevation of Privilege | executing downloaded binaries in e2e | high | mitigate | `scripts/container-e2e-verify.sh:479-480` `rm -f` + `TRACER_CONTAINER_TEARDOWN_OK`, `:485` EXIT trap; 18-VERIFICATION e2e on c58db6b; auditor `podman ps -a` on 2026-10-15 shows no `tools-installer-e2e` | closed |
| T-18-43 | Denial of Service | smoke weakened for the container | low | mitigate | `APPIMAGE_EXTRACT_AND_RUN` only at `container-e2e-verify.sh:260`; no `appimage-extract`/`appimage-version` in `installer/`; `registry.toml:2907`, `:2917` headless argv. `test_registry.py::test_drawio_desktop_declares_its_smoke_argv` | closed |
| T-18-50 | Tampering | leftover container / host dev venv | low | mitigate | 18-18-SUMMARY control probe `.venv/bin/ruff`; force-remove trap `:485` | closed |
| T-18-64 | Repudiation | retry evidence not from a clean system | medium | mitigate | `container-e2e-verify.sh:486` `all` starts with `bootstrap --replace`; `.e2e-artifacts/container` mtimes: bootstrap 18:12 < pass1 18:35 < probe 18:36 | closed |
| T-18-74 | Repudiation | logs from different containers | low | mitigate | `.e2e-artifacts/container/18-18-container-id.log`: one id (`6d3bd01a…`) for bootstrap, probe, pass1, pass2 | closed |
| T-18-49 | Elevation of Privilege | manager smoke runs the PATH binary | low | accept | AR-18-03 | closed |
| T-18-61 | Tampering | failed method's `bin_dir` stays on PATH | high | mitigate | `engine.py:198` record, `:214` restore on a failed smoke. `test_engine.py::test_failed_smoke_restores_path_before_the_next_method` | closed |
| T-18-62 | Spoofing | smoke passes on an earlier PATH binary | medium | mitigate | `engine.py:36-48` declared `bin_dir` target; `:181` `is_installed` short-circuit. `test_engine.py::test_declared_bin_dir_binary_is_smoked_not_an_earlier_path_hit`, `::test_without_a_bin_dir_the_path_hit_is_smoked` | closed |
| T-18-75 | Repudiation | broken package left unreported / unproven delete | medium | mitigate | `engine.py:215-225`, `:246-248` removal command from `installer/ownership.py:1454`; nothing is uninstalled. `test_engine.py::test_failed_manager_smoke_reports_the_removal_command_and_never_uninstalls`, `::test_leftover_package_is_reported_on_a_later_install` | closed |
| T-18-76 | Tampering | non-executable `bin_dir` file falls back to PATH | medium | mitigate | `engine.py:39-43` present non-executable -> nothing to smoke. `test_engine.py::test_non_executable_declared_bin_dir_file_is_not_smoked`, `::test_missing_declared_bin_dir_file_falls_back_to_which` | closed |
| T-18-20 | Elevation of Privilege | registry-supplied smoke command | medium | mitigate | `model.py:181`, `:839-855` argument tail in a closed charset; `executors.py:110` argv[0] is the installed path; `executors.py:162-177` closed `smoke` names. `test_model.py::test_smoke_argv_shape_is_validated`, `::test_smoke_argv_is_rejected_where_nothing_is_installed`, `::test_node_smoke_name_is_unchanged_by_smoke_argv` | closed |
| T-18-84 | Tampering | rule document truncation | medium | mitigate | `tests/test_docs.py::test_rule_documents_carry_no_truncation_banner`, `::test_architecture_records_phase_15_8_mechanisms` | closed |
| T-18-85 | Tampering | deleting an unproven `~/.local/opt/<name>` | high | mitigate | `download.py:228-234` gate `is_still_proven(link)` (`:188-204`) before the temp dir and the download. `test_download.py::test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical`, `::test_install_replaces_a_proven_opt_tree` | closed |
| T-18-86 | Tampering | replacing `~/Applications/<App>`; leaked `.old` | medium | mitigate | `apps.py:150-158` gate `is_still_proven(link, live)` before recovery and download (no CLI link -> refuse); `:224-229` `.old` removed for install and update. `test_apps.py::test_install_refuses_an_unproven_bundle_before_any_download`, `::test_install_over_a_proven_bundle_leaves_no_old_bundle` | closed |
| T-18-87 | Denial of Service | one OSError aborts the batch | medium | mitigate | `engine.py:232` OSError per method; `download.py:326-328` `.new` unlinked on any failure; rollback errors name the prior path (`download.py:371-374`, `:384-388`; `apps.py:205-208`, `:217-220`). `test_engine.py::test_an_oserror_in_one_method_falls_through_to_the_next`, `test_download.py::test_failed_raw_copy_leaves_no_staged_sibling`, `::test_rollback_failure_names_both_errors_and_the_old_tree` | closed |
| T-18-88 | Denial of Service | undecodable child output | medium | mitigate | `run.py:92-93` UTF-8 with `errors="replace"`; `:101-104` exit -> `CommandError`. `test_run.py::test_undecodable_output_is_replaced_not_raised` | closed |
| T-18-89 | Spoofing | failure report from child stderr | low | mitigate | `executors.py:79-87` one line (loader line, else the last 5 lines joined); `render.py:102-106` `sanitize_log_line` + `escape`. `test_executors.py::test_smoke_reason_is_one_bounded_line_under_noisy_stderr`, `test_render.py::test_failure_report_keeps_an_earlier_smoke_reason`, `::test_render_failure_details_escapes_bracketed_error_text` | closed |
| T-18-90 | Repudiation | checker/install strip divergence | medium | mitigate | `model.py:751-759`; `vr:509-534` mirrors tar/unzip. `test_model.py::test_strip_must_be_a_non_negative_integer`, `::test_strip_is_rejected_where_install_ignores_it`, `tvr::test_dot_prefixed_tar_strips_like_tar`, `::test_zip_member_must_match_the_stored_name` | closed |
| T-18-91 | Repudiation | shared-url failure loses target identity | high | mitigate | `vr:490-497`, `vr:828-854`. `tvr::test_a_shared_url_failure_keeps_every_target_identity` | closed |
| T-18-92 | Denial of Service | release reads and transports | medium | mitigate | `vr:625-647` memo including failures; `vr:94` `HTTPException` in the transport class; `vr:697-700`, `:314-318` pinned API failures reported. `tvr::test_failed_release_read_is_attempted_once_per_repo`, `::test_head_incomplete_read_is_inconclusive`, `::test_pinned_release_read_failure_is_reported_not_raised` | closed |
| T-18-93 | Information Disclosure | token copied onto a redirect | low | mitigate | `versions.py:363` `add_unredirected_header`. `test_versions.py::test_github_token_is_not_forwarded_on_a_redirect` | closed |
| T-18-94 | Tampering | `--write` not bound to the checked text | high | mitigate | `vr:1583` snapshot; `vr:1615-1619` refuse if changed -> 73 (`:1624-1626`); `vr:1620` edits apply to the snapshot. `tvr::test_write_refuses_when_the_registry_changed_during_the_run`, `::test_refused_write_leaves_the_registry_untouched_and_exits_73` + T-18-32 guard tests | closed |
| T-18-95 | Repudiation | crash exits 1 (drift) | medium | mitigate | `vr:1646-1651` -> 70; `vr:1631-1633` malformed gh -> 2; `vr:1516-1524` `--help` epilog. `tvr::test_an_unexpected_error_exits_70_not_1`, `::test_malformed_gh_issue_list_is_an_upsert_failure`, `::test_help_lists_the_exit_codes` | closed |
| T-18-96 | Denial of Service | usage error after a full network run | low | mitigate | `vr:1586-1592` before `github_token`/probe (`:1594-1606`). `tvr::test_candidate_usage_errors_cost_no_network` | closed |
| T-18-97 | Tampering | `ExecContext` without a release resolver | medium | mitigate | `download.py:51-55` `resolve_release` required, no default. `test_download.py::test_exec_context_requires_a_release_resolver`. Residual IN-04 deferred | closed |
| T-18-98 | Repudiation | three diverging error ladders | medium | mitigate | `vr:478-487` `_transport_finding` used at `vr:707-712`, `:722-727`, `:777-788`. `tvr::test_every_request_site_classifies_a_failure_the_same_way` (21 cases) | closed |
| T-18-SC | Tampering | npm/pip/cargo installs | high | accept | AR-18-01 | closed |

*Severity: critical > high > medium > low. Only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`.*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party).*

---

## Gap Plan 18-28 Re-verification (T-18-56, T-18-69)

The first audit at 344b8f5 left these two threats open below the threshold. Gap plan 18-28 closed both (18-28-SUMMARY.md, 342c7f1). Each fix was re-verified in the code, by its tests on HEAD, and by a mutation run: only the fix's code hunk was reverted, in a scratch export of HEAD, and the new tests failed there.

### T-18-56: symlinked app bundle root (closed by 58abaf9)

- **Code.** `apps.py:180-183` refuses the staged bundle if `staged_bundle.is_symlink() or not staged_bundle.is_dir()`. That runs before `staged_member` (`:186`), the `X_OK` check, the smoke (`:190`) and the swap. `app` is a bare name (`apps.py:131`), so `extract_root / app` has no intermediate components. `extract_root` is created by the installer under the staging dir, so the containment root is a proven directory. The refusal also covers apps with no `cli`.
- **Tests.** `test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing` covers `symlink_with_cli`, `symlink_without_cli`, `regular_file_without_cli` and `cli_resolving_to_a_zip_sibling`. Each case asserts: no marker, empty `~/Applications`, no CLI link, outside file unchanged. All pass on HEAD.
- **Mutation.** With the hunk reverted, the three bundle cases fail. `cli_resolving_to_a_zip_sibling` still passes, as expected, because the existing `staged_member` check covers it.

### T-18-69: corrupt xz or gz stream during listing (closed by b4af643)

- **Code.** `vr:772-779` adds `lzma.LZMAError` and `zlib.error` to the listing handler. A corrupt stream is stored as the listing error and becomes drift `archive unreadable as <mode>` (`vr:809-817`). It no longer escapes `check_registry`, and no state entry is written.
- **Tests.** `tvr::test_corrupt_archive_is_drift` gained `xz_corrupt_stream` (64 flipped mid-stream bytes, the auditor's reproduction) and `gz_bad_deflate_block`. All pass on HEAD.
- **Mutation.** With the hunk reverted, both new cases fail.
- **Residual (not a crash).** A gz CRC or trailer error (`gzip.BadGzipFile`, an `OSError`) still reaches the outer transport handler. It is reported as inconclusive rather than drift.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-18-01 | T-18-SC | No package installs in any of the 27 plans; `git diff --stat 22e6c5e..HEAD -- pyproject.toml uv.lock` is empty. Per-plan notes: ruff's new `uv-tool` method installs the official PyPI `ruff` at user install time (18-06); tomlkit was rejected (D-09, 18-13); workflow actions are pinned by major tag (18-14). SHA pinning is part of IN-05 (Phase 26) | Phase 18 plan threat models (planner); recorded by gsd-security-auditor | 2026-10-15 |
| AR-18-02 | T-18-10 | `uv run --exact` would uninstall dev packages on every launch. It is not used: L-18-01 chose `--isolated`, which leaves the venv untouched (no `--exact` in any launcher) | Phase 18 plan 18-05 threat model | 2026-10-15 |
| AR-18-03 | T-18-49 | The manager-kind smoke runs the binary PATH resolves for `tool.cmd`. That is the same binary the user runs by typing the command, run once with `--version` or the closed-charset `smoke_argv` tail. stdin is closed, the display is dropped, and the timeout is 5 s (`executors.smoke_binary`). The program is resolved from PATH, never a registry-supplied path | Phase 18 plan 18-19 threat model | 2026-10-15 |

*Accepted risks do not resurface in future audit runs.*

---

## Residuals and Deferred Items (no register change)

- **IN-04 (T-18-65, T-18-97).** `versions.release_resolver` (`versions.py:409-419`) picks digests by function identity. A wrapped tag resolver gets an empty digest map, so installs read "unverified" with a reason; they are not silently skipped. Deferred to Phase 25 (18-27 deferred table).
- **IN-05 (T-18-37, T-18-SC).** `GH_TOKEN` is set in the job-level `env` (`verify-registry.yml:21-22`), so every step can read it, including third-party actions pinned by mutable tags. There is no `concurrency:` group. Deferred to Phase 26 (CI).
- **T-18-94.** Tools are parsed by a second file read (`vr:1584`) after the snapshot read (`vr:1583`). An edit-and-revert inside that microsecond window would escape the refusal. Negligible for a single-maintainer command.
- **Test gaps.** T-18-06 has no markup-bearing reason fixture. T-18-31 does not exercise `default_probe` head/download for a missing `Authorization` header. The code for both is verified by direct reading.
- **T-18-52.** The vendor script check is point in time (2026-10-15). The script can change upstream.
- **T-18-21 / T-18-26.** The macOS GUI smoke is unverified (18-VERIFICATION human item 3).
- **T-18-89.** The reason is bounded by line count (5), not by character length.
- **T-18-69.** A gz CRC or trailer error (`gzip.BadGzipFile`) is reported inconclusive rather than drift. It does not abort the run.
- **Documentation.** 18-15-SUMMARY says 57 `verified` line updates, but commit 429b383 changes 47. No security impact.

## Unregistered Flags

None. No 18-NN-SUMMARY.md has a `## Threat Flags` section. Both audit findings map to registered threats (T-18-56, T-18-69). Gap plan 18-28 closed both. Review items not fixed by gap plans are in the 18-27 "Deferred to Phase 25 (Lean)" table and carry rationale.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-15 | 99 | 97 | 0 blocking (2 non-blocking: T-18-56, T-18-69) | gsd-security-auditor (Claude Opus 5.5), ASVS L1, block_on high, HEAD 344b8f5 |
| 2026-10-15 | 99 | 99 | 0 | gsd-security-auditor (Claude Opus 5.5), re-verification of T-18-56/T-18-69 after gap plan 18-28, HEAD 342c7f1 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed; no open threats remain (T-18-56 and T-18-69 closed by gap plan 18-28)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-15
