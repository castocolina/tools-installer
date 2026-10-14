# Phase 17 — Ponytail ultra reuse pass (plans 17-01..17-13)

Run 2026-10-14, read-only, codegraph-verified. Verdict: 13 findings (1 HIGH). Locked decisions (D-01..D-18, RUN-LEDGER rows) not flagged.

| Plan | Task | Sev | Finding | Plan edit |
|------|------|-----|---------|-----------|
| 17-01 | 1 | LOW | `unsupported mode` guard in `_prune_common_find_matches0` serves only a hypothetical regex caller; every caller passes `name` (scripts/prune-user-tmpdir.sh:231-235) | Delete the regex branch and the guard |
| 17-02 | 2 | LOW | `link_executable` at the apps site adds `chmod 0o755` on a file inside the .app bundle; `install_app` never chmods; `_relink_app_cli` (apps.py:179-183) already does `replace_symlink` | Apps site: `is_file()` check then `_relink_app_cli` (or `chmod: bool = True` flag, `False` for apps) |
| 17-03 | 2 | LOW | `test_run_output_closes_the_childs_stdin` duplicates the extended `test_run_output_unbounded_by_default` (`stdin is DEVNULL`) | Drop one |
| 17-05 | 1 | LOW | `test_graphify_declares_no_postinstall_hook` covered by `test_only_codegraph_and_rtk_declare_a_postinstall_hook` | Drop the new test |
| 17-06 | 1,2 | MEDIUM | ~9 per-call-site tests re-prove `tests/test_atomic.py` properties (:59 OSError keeps original, :46 symlink write-through, :23 missing file, :40 mode); routing already enforced by `.write_text(` count = 0 grep | Keep one failure + one symlink test at rc level (guards), keep 17-06 T3 `clean_rc` tests (D-06), move `test_rc_reader_never_sees_a_partial_write` into tests/test_atomic.py, drop the rest |
| 17-08 | 1 | MEDIUM | new `PolicyMove` cites no analog; `uninstall.SweepResult(swept, failed, warnings)` (uninstall.py:369-384) has the same shape; new type justified (uninstall imports policy → cycle) | Add one line naming `SweepResult` and the cycle reason |
| 17-09 | 1 | HIGH | `plan_removal` copies `plan_uninstall`'s `bin_dir`/default lookup and traversal guard (uninstall.py:80-95) into a second deletion path; drift between predicate and evidence list | Extract one `_download_link(method, default_bin_dir) -> tuple[Path, str] \| None` (link_name + guard) used by both |
| 17-09 | 1 | MEDIUM | `link_name` replaces only download.py:144; same expression at download.py:242 (`update_download`) | Use `link_name(...)` at :242 too; acceptance: `grep -c 'bin_name") or PurePosixPath' installer/download.py` = 0 |
| 17-09 | 1,2 | MEDIUM | same removal fixture set planted separately in tests/test_uninstall.py and tests/test_app.py; `test_tui_and_cli_delete_the_same_set` only meaningful on identical fixtures | One public fixture builder in tests/test_uninstall.py, imported by test_app.py (17-02 `fixture_runner` pattern) |
| 17-10 | 1 (+17-11 T1) | MEDIUM | hermetic route-pilot setup (PATH, systemd_available, detect, settings seed, `_has_controlling_tty`, `_stdin_on_tty`, `_execute_inputs` recorder) described in 17-10 and "reused" in 17-11 without a named helper | 17-10 creates `_hermetic_route(monkeypatch, tmp_path)` on top of `_sandbox` (tests/test_setup.py:436); 17-11 imports it |
| 17-10 | 2 | LOW | `_session_exit_code(app)` added while `_run_interactive_wizard` keeps its own `has_failure` branch (setup.py:1275) | Call `_session_exit_code` there too (keep troubleshooting print) |
| 17-10 | 2 | LOW | parametrized route test's doctor case duplicates Task 1's `test_doctor_route_executes_the_accepted_selection` | Task 2 replaces Task 1's test |
| 17-11 | 2 | MEDIUM (scope) | warnings for wrong-shape JSON / unknown link_mode go beyond SPEC R8 / D-11 | RUN-LEDGER: drop (TypeSafe 0.98) — warn only for invalid UTF-8 / invalid JSON; leave the two existing tests unchanged |

Clean: 17-04, 17-07, 17-12, 17-13. All new production code ships with tests in the same plan; no new method kind/executor/resolver rank; no new dependency.
