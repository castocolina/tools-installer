---
phase: 18-registry-truth-and-drift-guard
verified: 2026-10-16T02:10:00Z
status: human_needed
score: 6/6 must-haves verified
covered_files: [".claude/architecture.md", ".claude/dev-environment.md", ".claude/skills/tool-onboarding/SKILL.md", ".github/workflows/verify-registry.yml", ".planning/phases/18-registry-truth-and-drift-guard/18-01-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-01-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-02-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-02-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-03-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-03-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-04-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-04-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-05-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-05-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-06-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-06-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-07-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-07-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-08-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-08-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-09-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-09-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-10-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-10-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-11-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-11-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-12-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-12-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-13-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-13-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-14-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-14-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-15-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-15-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-16-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-16-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-17-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-17-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-18-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-18-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-19-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-19-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-20-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-20-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-21-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-21-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-22-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-22-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-23-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-23-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-24-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-24-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-25-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-25-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-26-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-26-SUMMARY.md", ".planning/phases/18-registry-truth-and-drift-guard/18-27-PLAN.md", ".planning/phases/18-registry-truth-and-drift-guard/18-27-SUMMARY.md", "AGENTS.md", "Makefile", "README.md", "docs/TROUBLESHOOTING.md", "install.sh", "installer/apps.py", "installer/audit.py", "installer/download.py", "installer/engine.py", "installer/executors.py", "installer/install_ownership.py", "installer/locations.py", "installer/model.py", "installer/ownership.py", "installer/registry.toml", "installer/render.py", "installer/run.py", "installer/status.py", "installer/uninstall.py", "installer/update.py", "installer/verify_registry.py", "installer/version_cache.py", "installer/version_status.py", "installer/versions.py", "scripts/container-e2e-verify.sh", "setup.py", "tests/test_app.py", "tests/test_apps.py", "tests/test_audit.py", "tests/test_docs.py", "tests/test_download.py", "tests/test_engine.py", "tests/test_executors.py", "tests/test_install_ownership.py", "tests/test_install_sh.py", "tests/test_locations.py", "tests/test_makefile.py", "tests/test_model.py", "tests/test_ownership.py", "tests/test_postinstall.py", "tests/test_registry.py", "tests/test_render.py", "tests/test_run.py", "tests/test_session.py", "tests/test_skill_lifecycle.py", "tests/test_status.py", "tests/test_uninstall.py", "tests/test_update.py", "tests/test_verify_registry.py", "tests/test_verify_registry_workflow.py", "tests/test_version_cache.py", "tests/test_version_status.py", "tests/test_versions.py"]
covered_digest: "v3:sha256:9374118646f00d4c2e9708b309fbb3357cf1a2be067c96fc7c4a4d4ad10520c7"
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "Review LOW/INFO items not fixed by gap plans 18-21..18-27 (IN-02 tarball checksum branch, IN-03 launch-time clock check, IN-04 explicit resolver through install_tool, IN-05 workflow token scope/concurrency/SHA pins, IN-06 conftest smoke sandbox, ponytail #10 part, #14, #18 part, #19, apps._UNVERIFIED_REASON import swap)"
    addressed_in: "Phase 25"
    evidence: "18-27-PLAN.md 'Deferred to Phase 25 (Lean)' table with per-item rationale; Phase 25 goal: 'About 2,000 production lines are gone with behavior unchanged'. IN-05/IN-06 name Phase 26 (CI/hooks) as the better home."
human_verification:
  - test: "After pushing main, run `gh workflow run verify-registry.yml` and inspect the run"
    expected: "Job runs on workflow_dispatch with contents: read / issues: write; `make verify-registry ARGS=\"--issue\"` exits 0 (no drift) or 1 with exactly one open `registry-drift` issue; cache save step stores verify-registry.json"
    why_human: "Needs GitHub Actions after a push; the first real scheduled/dispatched run cannot happen locally (18-VALIDATION manual-only row)"
  - test: "After pushing, check the CI workflow on ubuntu-latest and macos-latest"
    expected: "Both matrix legs green, including the macOS-fixture tests for the java/git stub rule (REG-07) and draw.io cli_name"
    why_human: "No local macOS host; the macOS leg only runs on GitHub"
  - test: "On a real Mac: install draw.io through the pinned app method (no brew cask) and run the installer's smoke"
    expected: "`~/.local/bin/drawio` links Contents/MacOS/draw.io; the `--version` smoke does not leave a GUI window open; /usr/bin/java and /usr/bin/git stubs alone show as not installed"
    why_human: "macOS-only runtime behavior; executors.smoke_binary docstring records that the macOS app-CLI smoke behavior is not verified"
---

# Phase 18: Registry truth and drift guard Verification Report

**Phase Goal:** The registry matches upstream releases and this host, and drift is caught by a check before a user hits it.
**Verified:** 2026-10-16T02:10:00Z (HEAD c58db6b)
**Status:** human_needed (all automated must-haves verified; three post-push / macOS-only items remain)
**Re-verification:** No (initial verification)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: unknown method key fails; draw.io `cli_name` honored; a missing/invalid `verified = YYYY-MM-DD` fails | VERIFIED | `model.METHOD_PARAMS` (model.py:42) + `load_tools` rejection at :726 naming tool and key; `verified` must be `type(...) is date`, future > today+1 rejected (:700-709, L-18-06). Tests: `test_unknown_method_key_names_the_tool_and_key`, `test_key_valid_for_another_kind_is_rejected`, `test_kind_only_method_loads`, `test_missing/string/integer/datetime/future_verified_is_rejected`, `test_verified_on_a_method_table_is_rejected`, `test_every_shipped_tool_declares_a_verified_date`. `apps.cli_spec` is the only reader of `cli_name`, used by install and `uninstall.py:48`; `test_install_app_links_the_cli_under_cli_name`, `test_plan_app_uses_cli_name`. |
| 2 | SC2: `make verify-registry` flags the pre-fix difftastic template (renamed asset), missing members and checksum drift; weekly, non-blocking, never in the PR gate | VERIFIED | `installer/verify_registry.py` (1655 lines), Makefile target `verify-registry` (`uv run --isolated --no-dev python -m installer.verify_registry`). Tests: `test_prefix_difftastic_template_is_reported_as_drift`, `test_member_missing_from_archive_is_drift`, `test_downloaded_hash_mismatch_is_drift`, `test_checksum_file_disagreeing_with_the_digest_is_drift`, `test_second_drift_edits_the_open_issue`, `test_inconclusive_run_makes_no_gh_call`. Workflow: only `schedule` (Mon `17 5 * * 1` + Thu cache refresh) and `workflow_dispatch`, `contents: read, issues: write`, absent from ci.yml (`tests/test_verify_registry_workflow.py`, 5 tests). Live spot-check by this verifier against GitHub with a scratch registry: pre-fix template exit 1 with 4x `asset missing (HTTP 404)`; fixed template exit 0, all 4 assets digest-verified; working tree unchanged. |
| 3 | SC3: unverified `github_release` methods 50 -> 0 wherever GitHub exposes a digest; a fake binary exiting 127 falls through | VERIFIED | `versions.resolve_github_release` gives tag + digests from one read; `download.resolve_target` orders checksum file -> pinned sha256 -> API digest -> unverified reason. Live final-check (.e2e-artifacts/verify-registry/final-check.exit = EXIT 0) "Unverified at install" lists only gron and jless among github_release tools (no upstream digest, Ledger L-18-02), plus unpinned vendor URLs (vscode, jetbrains-toolbox). Fall-through: `test_smoke_failure_falls_through_to_the_next_method` (exit-127 first method, asserts no `rg` link and no opt tree, IN-07), `test_single_failing_method_leaves_no_link`, `test_digest_mismatch_fails_with_nothing_linked`. |
| 4 | SC4: without the dev venv on PATH ruff resolves its real owner under `make setup` (container); `/usr/bin/java` alone never counts; `parse_version('-1') is None`; quoted/`version=` output never fabricates | VERIFIED | All 7 launchers + install.sh:88 + e2e harness use `uv run --isolated --no-dev` (L-18-01); `setup.py __main__` calls `drop_project_venv_from_path` (L-18-08). 18-18 container probe: control `.venv/bin/ruff`, launch-before `None`, launch-after `/home/tester/.local/bin/ruff`; Makefile/setup.py/install.sh/harness/locations.py unchanged since that probe (git log 17d404b..HEAD empty). `status.MACOS_STUBS` with absolute probes; `test_java_stub_alone_is_not_installed_with_a_reason`, `test_java_stub_with_a_real_jdk_is_installed`, git/CLT pair. Spot-check: `parse_version('-1')` -> None; `extract_observed_version('procs "0.14.6"')` -> `0.14.6`; `version=0.44.1, ...` -> `0.44.1`; fixture table `test_observed_version_fixture_table`. |
| 5 | SC5: every C/D/E/F audit data fix applied, `managed-download` probe gone, `drawio-cli` removed with `drawio-desktop` serving both | VERIFIED | 35-row ledger (18-08-SUMMARY) maps each fix to a named `test_audit_fix_*` test or a verify-registry pass; C7 and E9 are not applied, and both are worded "Optionally" in the audits themselves (checked in C-registry-system.md, E-registry-user-part2.md); C9 superseded by the `verified` key; E1/E3 already done. `rg -n managed-download installer/` -> no match. Registry has 0 `drawio-cli`; `drawio-desktop` `audience = "both"`; stale-id tests in `tests/test_version_cache.py -k drawio` pass. |
| 6 | SPEC R11: pins bumped to latest stable, checksummed, dated; pinned app/tarball URLs template `{ver}` with `version` + `sha256` | VERIFIED | Loader requires `version` + 64-hex `sha256` when a pinned kind's URL has `{ver}` and rejects them otherwise (model.py:729-750). Shipped pinned URLs: sublime (4215, 3 methods), drawio-desktop app (32.4.1, 2 methods), all `{ver}`. Live final-check has no `newer stable release` line (only the expected `sublime: newer stable: no release source` notes). Writer: `test_write_dates_only_passing_tools`, `test_renamed_candidate_asset_keeps_the_old_pin`, `test_unpinned_entries_never_gain_pin_keys`, guard tests `test_writer_guard_refuses_*`, snapshot-bound `test_write_refuses_when_the_registry_changed_during_the_run`. Registry edits after the live run (18-18 `smoke_argv`, 18-24 removal of meaningless gh zip `strip = 0`) do not change any checked URL, member or checksum. |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | IN-02 (part), IN-03, IN-04, IN-05, IN-06, ponytail #10 (part), #14, #18 (part), #19, `apps._UNVERIFIED_REASON` | Phase 25 (IN-05/IN-06 better homed in Phase 26) | 18-27-PLAN.md "Deferred to Phase 25 (Lean)" table gives a reason for each item. All are INFO/LOW; none is CRITICAL, HIGH or WARNING |

### Review Finding Closure (CRITICAL / HIGH / WARNING / MEDIUM)

| Finding | Source | Closed by | Test evidence (passing at HEAD) |
|---------|--------|-----------|---------------------------------|
| CR-01 architecture.md truncated | REVIEW | 18-21 | `git diff 22e6c5e HEAD -- .claude/architecture.md` is +20/-4 (only the intended Phase 18 edits); tail sentence restored; `tests/test_docs.py` guards `[Showing lines`, `Use offset=` and the sentinel `this project does NOT parse shell` |
| CR-02 unproven opt tree deleted | REVIEW | 18-22 | `test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical`, `test_install_replaces_a_proven_opt_tree`; download.py:230 gate via `is_still_proven` |
| WR-01 / ponytail M3 / opencode MEDIUM app `.old` leak | all three | 18-22 | `test_install_over_a_proven_bundle_leaves_no_old_bundle`, `test_install_refuses_an_unproven_bundle_before_any_download` |
| WR-02 strip/zip/`./` divergence | REVIEW | 18-24 | `test_strip_must_be_a_non_negative_integer`, `test_strip_is_rejected_where_install_ignores_it`, `test_dot_prefixed_tar_strips_like_tar`, `test_zip_member_must_match_the_stored_name` |
| WR-03 smoke reason lost | REVIEW | 18-23 | `test_smoke_binary_names_the_os_launch_error`, `test_smoke_reason_is_one_bounded_line_under_noisy_stderr`, `test_failure_report_keeps_an_earlier_smoke_reason`; run.py:104 `detail=str(exc)` |
| WR-04 crashes exit 1 | REVIEW | 18-25, 18-26 | `test_tarball_without_url_is_drift_not_a_crash`, `test_head/download_incomplete_read_is_inconclusive`, `test_binary_checksum_file_is_drift_not_a_crash`, `test_an_unexpected_error_exits_70_not_1`, `test_malformed_gh_issue_list_is_an_upsert_failure` |
| WR-05 writer guard untested | REVIEW | 18-26 | `test_writer_guard_refuses_an_edit_that_breaks_the_toml`, `test_writer_guard_refuses_an_edit_that_changes_another_value` |
| WR-06 usage after network / exit 64 reuse | REVIEW | 18-26 | `test_candidate_usage_errors_cost_no_network`, `test_refused_write_leaves_the_registry_untouched_and_exits_73`; live: `--candidate nope=1` exits 64 immediately |
| WR-07 OSError aborts batch | REVIEW | 18-22 | `test_an_oserror_in_one_method_falls_through_to_the_next`, `test_an_oserror_in_the_only_method_is_a_failed_outcome`, rollback-failure tests |
| HIGH writes not bound to checked snapshot | opencode | 18-26 | `test_write_refuses_when_the_registry_changed_during_the_run` |
| HIGH pinned API failure aborts report / ponytail M2 | opencode, ponytail | 18-25 | `test_pinned_release_read_failure_is_reported_not_raised`, `test_pinned_release_not_found_is_drift` |
| HIGH shared-URL identity loss | opencode | 18-25 | `test_a_shared_url_failure_keeps_every_target_identity` |
| MEDIUM EXDEV app staging | opencode | 18-22 | `test_app_staging_stays_on_the_applications_filesystem` |
| MEDIUM non-UTF-8 output | opencode | 18-23 | `test_undecodable_output_is_replaced_not_raised` (run.py `errors="replace"`) |
| MEDIUM gzip timestamp fixtures | opencode | 18-25 | `test_gzip_fixtures_do_not_depend_on_the_clock` (`mtime=0`) |
| LOW unpinned-version assertion | opencode | 18-26 | `test_unpinned_entries_never_gain_pin_keys` |
| ponytail M1 failed release reads uncached | ponytail | 18-25 | `test_failed_release_read_is_attempted_once_per_repo` |
| ponytail M4 three error ladders | ponytail | 18-27 | `test_every_request_site_classifies_a_failure_the_same_way` (21 cases, mutation-proven) |
| ponytail M5 two release resolvers | ponytail | 18-27 | `test_exec_context_requires_a_release_resolver`; `ExecContext` is `runner, platform, resolve_release` |
| IN-01 / IN-07 / IN-08 | REVIEW | 18-22/23/25 | stale docstrings corrected (macOS limitation recorded in `smoke_binary`); fall-through asserts no link; `add_unredirected_header` at versions.py:363 |

A targeted run of the closure tests (`-k` over 14 test files, 106 selected) passed with no failures.

### Locked Decisions and Ledger

D-01..D-15 and L-18-01..L-18-23 were checked against the code. Examples: `METHOD_PARAMS` (D-01); TOML-date `verified` with a +1 day tolerance (D-02/L-18-06); `{ver}` pins (D-03); `cli_spec` as the single reader (D-04); one-read `Release` (D-05); `smoke_binary` before link (D-06); `MACOS_STUBS` with absolute probes (D-10/L-18-17); `--isolated --no-dev` (L-18-01); two crons (L-18-07); the venv dropped from PATH at the entry point (L-18-08); exit codes 0/1/2/64/70/73 (L-18-21, `--help` lists them); strip value rules (L-18-20); a required `resolve_release` (L-18-23). No contradiction found.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `installer/verify_registry.py` | VERIFIED | substantive (1655 lines), wired via Makefile target and workflow; live run produced correct verdicts |
| `.github/workflows/verify-registry.yml` | VERIFIED | schedule + dispatch only, read-only contents, cache restore/save |
| `installer/model.py` METHOD_PARAMS / verified / pin rules | VERIFIED | used by every `load_tools` caller; shipped registry loads |
| `installer/executors.py` `smoke_binary` | VERIFIED | called from download/app before link and from engine manager smoke |
| `installer/status.py` `MACOS_STUBS` | VERIFIED | consulted by `is_installed` (:92) |
| `installer/versions.py` `resolve_github_release`, parser fixes | VERIFIED | used by download ctx, version cache, verify-registry |
| `installer/registry.toml` | VERIFIED | 89 tools, all carry `verified`; no `drawio-cli`/`managed-download` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Live drift on pre-fix difftastic | `python -m installer.verify_registry --registry <scratch prefix.toml> --state <scratch>` | exit 1, 4x `asset missing (HTTP 404)` | PASS |
| Live pass on fixed difftastic | same, fixed template | exit 0, 4 assets passed, none unverified | PASS |
| Usage error before network | `--candidate nope=1` (no `--write`) | exit 64 at once | PASS |
| Version parser fixtures | `parse_version` / `extract_observed_version` on `-1`, procs, lazygit | None / `0.14.6` / `0.44.1` | PASS |
| 18-VALIDATION commands | 14 targeted pytest invocations + `rg` + dependency diff | all pass; `rg` no match; pyproject/uv.lock unchanged vs 72c9047 | PASS |
| Container e2e on c58db6b | `make e2e` (orchestrator run, transcripts read here) | pass1 `PASS1_COUNTS installed=74 failed=0 manual_required=8 setup_exit=0`, `TRACER_CLEAN_INSTALL_OK`; pass2 `TRACER_RERUN_OK`, `TRACER_UNINSTALL_OK`, `TRACER_REINSTALL_OK installed=39 failed=0`, `TRACER_CONTAINER_TEARDOWN_OK`; no container left; `ruff: sha256 ✓` | PASS |

The orchestrator also reported `make validate` x2 rc 0, `make test` x2 with 3949 passed / 4 skipped, and pre-commit --all-files rc 0. The full suite was not re-run here, per instruction.

### Probe Execution

Step 7c: no `scripts/*/tests/probe-*.sh` exists and no plan declares a probe. Not applicable.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| REG-01 | closed method keys | SATISFIED | Truth 1 |
| REG-02 | `verified` date key | SATISFIED | Truth 1 |
| REG-03 | verify-registry + weekly job outside PR gate | SATISFIED (first live workflow run is post-push) | Truth 2 |
| REG-04 | checksum -> digest -> unverified | SATISFIED | Truth 3 |
| REG-05 | smoke run falls through | SATISFIED | Truth 3 |
| REG-06 | no dev venv at launch | SATISFIED | Truth 4 |
| REG-07 | macOS stubs not tools | SATISFIED (fixtures; real Mac is human) | Truth 4 |
| REG-08 | no fabricated versions | SATISFIED | Truth 4 |
| REG-09 | audit data fixes, managed-download gone | SATISFIED | Truth 5 |
| REG-10 | one drawio row | SATISFIED | Truth 5 |
| SPEC R11 | pins bumped and verified | SATISFIED | Truth 6 |

No orphaned requirements. REQUIREMENTS.md still shows Pending, and 18-VALIDATION.md is still `draft`. Neither was changed by this verifier.

### Test Integrity (no weakening)

Six test functions present at 22e6c5e are gone. Each one is a planned replacement:
- `test_install_app_builds_curl_ditto_mv_pipeline` and `..._without_cli_runs_only_the_pipeline`: the shell pipeline was deleted in 18-16, and the new tests assert the plain curl/ditto argv and that no `sh` is invoked.
- `test_install_download_returns_false_when_unverified`: replaced by the unverified-with-reason tests.
- `test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical`: the CR-02 inversion. It is replaced by the stricter `test_install_refuses_an_unproven_opt_tree_and_leaves_it_byte_identical`, and the Phase 17 `keep-me` preservation assertion is still present.
- `test_non_node_method_leaves_new_keys_untouched`: the rewrite planned in D-01.
- `test_kitty_entry_records_the_txz_extraction_gap`: replaced by `test_kitty_entry_records_why_it_uses_the_vendor_script` (18-20).

The 54 removed `assert` lines all follow these deliberate behavior changes (shell pipeline, drawio-cli, parser fixes). 304 tests were added. Every test name cited in the plans and summaries resolves to a defined test or prefix. There are no truncation banners in the repo, and the file line counts show no cut-off files.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (phase-modified code files) | - | TBD/FIXME/XXX/TODO/HACK | none found | - |
| `installer/registry.toml` | gh `[[tool]]` | `verified = 2026-10-13` (seed date) although gh passed the 2026-10-15 read-only check | Info | The 18-15 `--write` run hit the gh strip drift, so gh was not re-dated; the final run was read-only. No false date was written (prohibition holds). It refreshes on the next `--write` pass |
| `installer/verify_registry.py` | main | a registry that fails `load_tools` exits 70 with a traceback | Info | Correct per L-18-21 (internal error, never 1) |

### Human Verification Required

#### 1. First verify-registry workflow run (post-push)

**Test:** After pushing main: `gh workflow run verify-registry.yml`, then inspect the run.
**Expected:** The check step runs; it exits 0, or exits 1 with one `registry-drift` issue; the cache save step stores the state file.
**Why human:** It needs GitHub Actions. The code and workflow are covered by tests and the live local run.

#### 2. CI matrix on ubuntu-latest + macos-latest (post-push)

**Test:** Check that the CI run for the pushed HEAD is green on both legs.
**Expected:** All tests pass on macOS, including the stub-rule and cli_name fixtures.
**Why human:** There is no local macOS host.

#### 3. Real-Mac draw.io app install + stub behavior

**Test:** On a Mac with no draw.io cask, install drawio-desktop through the pinned app method. Then check java and git with no JDK or CLT installed.
**Expected:** The `drawio` CLI link is created, the smoke leaves no window open, and both stubs report as not installed.
**Why human:** This is macOS-only runtime behavior, and the code records it as unverified on macOS.

### Gaps Summary

No gaps. All five ROADMAP success criteria and SPEC R11 are backed by code, by tests that pass at HEAD, and by live evidence: a live verify-registry spot-check, the 18-15 final check, and a fresh container e2e on c58db6b. Every CRITICAL, HIGH, WARNING and MEDIUM review finding is closed with a named test. The remaining INFO/LOW items are deferred to Phase 25 (or 26), each with a reason. The status is `human_needed` only because of the three post-push / macOS-only checks above.

---

_Verified: 2026-10-16T02:10:00Z_
_Verifier: Claude (gsd-verifier)_
