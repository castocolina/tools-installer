---
phase: "17"
slug: "stop-the-bleeding"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-15"
---

# Phase 17 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| installer -> ~/.local/bin, ~/.local/opt | links and binaries the installer creates, replaces or deletes | user-owned executables (integrity) |
| installer -> shell rc files, shims, settings.json | managed blocks and settings written into user config | user shell configuration (integrity) |
| installer -> child processes (vendor scripts, package managers) | install/update children run with no controlling terminal | argv from the registry; child stdin/tty |
| registry -> executors | member names, postinstall hooks, env prefixes | registry data (trusted, reviewed) |
| tests -> developer host | the suite must never touch the real HOME or host services | host state |
| orchestrator -> GitHub (origin/main, branch protection) | pushes, temporary CI-oracle branches, repository settings | repository integrity |
| e2e harness -> developer host | real installs run only inside a disposable container | host state |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-17-01 | Tampering | prune regex rewritten to grep | high | mitigate | `scripts/lib/prune-tmp-common.sh:207-211` anchored `grep -E`; root escaped in `prune-tmp-linux.sh:98-104`; `test_near_miss_filenames_all_survive` | closed |
| T-17-02 | Tampering | tests touching the real HOME or host services | medium | mitigate | `tests/conftest.py:53-75` `real_home_untouched` (session, autouse); systemd faked in `test_setup.py:3008-3025` | closed |
| T-17-03 | Tampering | `ln -sf` writing through a link to a directory | high | mitigate | `executors.py:49-64` -> `atomic.replace_symlink`; raw installs via `_replace_raw` (`download.py:174-185`); `test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical`, `test_*raw_install_replaces_a_link_instead_of_writing_through_it` | closed |
| T-17-04 | Tampering | directory member linked as the binary | high | mitigate | `executors.py:55-56` `is_file()` check before link; update paths roll back (`download.py:344-351`, `apps.py:186-194`); `test_*_directory_member_links_nothing`, `test_update_*_directory_*_rolls_back` | closed |
| T-17-05 | Tampering | member symlink pointing outside the opt dir | low | accept | see Accepted Risks AR-17-01 | closed |
| T-17-06 | Denial of Service | child blocking on /dev/tty | high | mitigate | `run.py:248,260` and `:99-100` `stdin=DEVNULL`, `start_new_session=True`; `test_*_tty_reader_fails_fast`, `test_*_child_runs_in_its_own_session` | closed |
| T-17-07 | Denial of Service | child no longer receives SIGINT/SIGHUP | low | accept | see AR-17-02 | closed |
| T-17-42 | Denial of Service | sudo methods fail fast in the TUI | medium | accept | see AR-17-03 | closed |
| T-17-08 | Tampering | Doctor executing a repair | high | mitigate | `doctor.py:30-64` `scan_bin_links` read-only; `test_run_doctor_reports_broken_links_and_changes_nothing` | closed |
| T-17-09 | Elevation of Privilege | privilege escalation in repair text | medium | mitigate | `guidance.py:123-152` user-path `rm` + catalog reinstall only; `test_broken_link_guidance_never_escalates` | closed |
| T-17-10 | Tampering | repair deletes an opt dir the link does not point into | medium | mitigate | `doctor.py:52-59` opt_dir only when the target is inside it; `test_dangling_link_without_opt_dir_guidance_removes_the_link` | closed |
| T-17-11 | Tampering | link name injecting shell syntax | low | mitigate | `guidance.py:137,142` `shlex.quote` | closed |
| T-17-12 | Tampering | graphify writing into the cwd | high | mitigate | graphify `postinstall` removed (`registry.toml:1586-1605`); `test_installing_graphify_runs_no_host_registration`, `test_updating_graphify_runs_no_host_registration`, `test_only_codegraph_and_rtk_declare_a_postinstall_hook` | closed |
| T-17-13 | Denial of Service | codex install.sh prompting on /dev/tty | medium | mitigate | `registry.toml:1354` `CODEX_NON_INTERACTIVE = "1"` via `executors._env_prefix`; `test_codex_script_runs_non_interactive` | closed |
| T-17-14 | Tampering | Sublime member naming a directory | high | mitigate | `registry.toml:2283,2291` `member = "sublime_text/sublime_text"`; `test_sublime_linux_tarballs_link_the_binary_inside_the_archive_dir` | closed |
| T-17-15 | Tampering | truncated rc file | high | mitigate | `atomic.py:34-52` temp + `os.replace`; all rc/shim writers use it; `test_ban_aliases_write_failure_leaves_the_rc_byte_identical`, `test_atomic_write_bytes_oserror_leaves_the_original_and_no_temp` | closed |
| T-17-16 | Tampering | symlinked rc replaced by a regular file | high | mitigate | `atomic.py:42` resolves before replace; `test_ban_aliases_write_through_a_symlinked_rc`, `test_clean_rc_duplicates_writes_through_a_symlinked_rc` | closed |
| T-17-17 | Tampering | stale indices stripping the wrong lines | high | mitigate | `app.py:436-461` preview bytes re-checked at confirm; `test_clean_rc_duplicates_refuses_a_file_edited_between_preview_and_confirm` (+ trailing-newline, deleted cases) | closed |
| T-17-18 | Tampering | dangling symlink at a shim path | low | accept | see AR-17-04 | closed |
| T-17-19 | Repudiation | crashed or failed run shown green | high | mitigate | `execute_screen.py:693-722`, `session.py:120-160`, `setup.py:1302-1311`; `test_worker_exception_marks_the_run_failed_and_keeps_done_rows`, `test_failed_update_exits_1`, `test_headless_run_exits_1_on_failure` | closed |
| T-17-20 | Information Disclosure | exception text in status/log | low | accept | see AR-17-05 | closed |
| T-17-21 | Tampering | policy blocks lost or left behind between link modes | high | mitigate | `policy.py:211-304` `move_link_mode` + `_rollback` + `PolicyRestoreError`; rollback/restore tests in `test_policy.py` | closed |
| T-17-44 | Repudiation | failed move reported as moved | low | mitigate | `policy.py:300`; `wizard_app.py:2233-2255`; `test_policies_screen_reports_a_failed_move` | closed |
| T-17-22 | Denial of Service | daemon/.zshrc rewritten on every mode change | medium | mitigate | `wizard_app.py:2218-2230` only link_mode_aware policies still on disk; `test_move_link_mode_ignores_policies_that_are_not_link_mode_aware`, `test_link_mode_change_after_an_uninstall_does_not_resurrect` | closed |
| T-17-23 | Tampering | foreign rc content altered during a move | high | mitigate | marker-scoped atomic writers; `test_link_mode_move_keeps_foreign_rc_bytes_identical` | closed |
| T-17-24 | Tampering | uninstall deleting a foreign file with a tool's name | high | mitigate | `uninstall.py:128-182` strict proof; re-checked at deletion (`app.py:619-624`, `:708-713`); `test_run_uninstall_deletes_only_proven_artifacts`, `test_*_refuses_paths_changed_since_the_preview`, `test_plan_removal_survives_looping_link_and_opt_dir` | closed |
| T-17-25 | Tampering | link into another tool's opt dir accepted as proof | high | mitigate | `uninstall.py:139-143` `is_relative_to(opt_dir(...))`; `test_plan_removal_rejects_a_link_into_another_tools_opt_dir` | closed |
| T-17-26 | Repudiation | `--yes` deleting what the TUI would refuse | high | mitigate | both paths call `plan_removal`; `test_tui_and_cli_delete_the_same_set` | closed |
| T-17-27 | Tampering | symlink race between proof and delete | low | accept | see AR-17-06 | closed |
| T-17-28 | Repudiation | accepted selection silently dropped | medium | mitigate | `setup.py:759-773`, `:1142-1170` always builds execute; `test_every_tui_route_executes_the_accepted_selection` | closed |
| T-17-29 | Tampering | route pilot tests reaching the real host | high | mitigate | `tests/test_setup.py:526` `_hermetic_route`; `conftest.py:53-75` | closed |
| T-17-30 | Repudiation | failed non-setup route exiting 0 | medium | mitigate | `setup.py:1302-1311` on every route; `test_tui_routes_exit_1_when_the_session_failed`, `test_ctrl_c_mid_run_exits_1`, `test_failed_direct_catalog_update_exits_1` | closed |
| T-17-31 | Denial of Service | non-UTF-8 settings.json crashing launch | high | mitigate | `settings.py:64-78`; `test_load_settings_invalid_utf8_returns_defaults_and_a_warning`, `test_invalid_settings_file_launches_to_the_first_screen_with_a_warning` | closed |
| T-17-32 | Tampering | defaults written over the damaged file | medium | mitigate | `settings.py:151` single save point; byte-identical checks in `test_setup.py`, `test_all_yes_with_a_damaged_settings_json_warns_before_acting` | closed |
| T-17-33 | Tampering | arbitrary link_mode string reaching `rc_paths_for_mode` | medium | mitigate | `settings.py:85,143` closed `LINK_MODES` set; `test_tampered_link_mode_is_rejected` | closed |
| T-17-34 | Information Disclosure | warning rendered as markup | low | accept | see AR-17-07 | closed |
| T-17-35 | Repudiation | Phase 16 threat recorded closed without evidence | medium | mitigate | every closed row in `16-SECURITY.md:77-91` cites a symbol and test; 16-VALIDATION commands n=15, 0 failed | closed |
| T-17-36 | Tampering | colliding T-16-49..51 merged into one row | medium | mitigate | six qualified rows plus collision note (`16-SECURITY.md:91`) | closed |
| T-17-37 | Tampering | audit changing code to make a row pass | low | mitigate | `git show --stat 918877b b4a238c` lists only the two audit files | closed |
| T-17-38 | Elevation of Privilege | branch protection applied without consent | high | mitigate | blocking-human checkpoint; "CI-02 answer: skip"; `gh api .../protection` returns 404 | closed |
| T-17-39 | Tampering | force-push or admin merge past a failing check | high | mitigate | no `--force`/`--no-verify`/`--admin` used; oracle PRs #1-#4 closed unmerged; origin/main is an ancestor of HEAD | closed |
| T-17-40 | Tampering | `make e2e` changing the host | high | mitigate | `container-e2e-verify.sh:105` no host mounts; teardown `:477`, EXIT trap `:483` | closed |
| T-17-41 | Repudiation | runner-image change blamed on, or hidden by, the phase | medium | mitigate | 17-13 records run ids, URLs and both conclusions; both green | closed |
| T-17-43 | Tampering | main published before review and verification | high | mitigate | no main push in plan tasks; origin/main still 72c9047 at audit time; oracle branch deleted | closed |
| T-17-SC | Tampering | npm/pip/cargo installs (plans 17-01..17-04, 17-06..17-13; one row per plan) | high | accept | see AR-17-08 | closed |
| T-17-SC (17-05) | Tampering | pip install of graphifyy for the probe | medium | mitigate | `--rm` python:3.12-slim container, `graphifyy==0.9.54` (17-05-SUMMARY); dependency diff empty | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Register totals: 57 rows (44 numbered threats + 13 per-plan T-17-SC rows, collapsed above into two lines): 38 mitigate, 19 accept, 0 transfer; 57 closed, 0 open.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-17-01 | T-17-05 | An archive member that is itself a symlink out of the opt dir: argv comes only from the registry and archives from registry URLs; Phase 18 adds digests | 17-02-PLAN (planner), confirmed by gsd-security-auditor | 2026-10-15 |
| AR-17-02 | T-17-07 | Children in a new session no longer get the terminal's SIGINT/SIGHUP; Textual holds the terminal in raw mode so Ctrl+C never reached them anyway; app-level cancel unchanged | 17-03-PLAN | 2026-10-15 |
| AR-17-03 | T-17-42 | `sudo dnf/apt-get/pacman` methods fail fast in the TUI instead of hanging on a hidden password prompt; the zero-sudo handoff is Phase 22 (LIFE-02) | 17-03-PLAN | 2026-10-15 |
| AR-17-04 | T-17-18 | A dangling symlink at a shim path makes the write create the link's target; unchanged behaviour, `is_our_shim` checks shim targets first | 17-06-PLAN | 2026-10-15 |
| AR-17-05 | T-17-20 | Exception text in the status and log: a local single-user tool showing the user's own run error | 17-07-PLAN | 2026-10-15 |
| AR-17-06 | T-17-27 | Symlink race between proof and delete: one local user, one installer process; `remove_paths` never follows links; 17-18's deletion-time re-check narrows the window | 17-09-PLAN | 2026-10-15 |
| AR-17-07 | T-17-34 | Settings warning as markup: rendered via `Text(...)` in the TUI and `markup=False` headless; holds only the user's own path and the decoder message | 17-11-PLAN | 2026-10-15 |
| AR-17-08 | T-17-SC | No package installs: pyproject.toml and uv.lock unchanged 72c9047..HEAD; no commit in the range touches them | each plan's register | 2026-10-15 |

*Accepted risks do not resurface in future audit runs.*

Auditor notes (no status change): on the update path (`download.py:327-351`) the staged member is chmodded and linked before the `is_file()` check and rolled back on failure (covered by `test_update_download_directory_member_rolls_back`); `installer/agent_policy.py:110,192,205` still use plain `write_text` for agent settings/instruction files, which are outside SAFE-04 and untouched by Phase 17.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-15 | 57 | 57 | 0 | gsd-security-auditor (ASVS 1, block_on high; 70 cited tests re-run, 84 passed incl. parametrized) on HEAD 0594376 |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-15
