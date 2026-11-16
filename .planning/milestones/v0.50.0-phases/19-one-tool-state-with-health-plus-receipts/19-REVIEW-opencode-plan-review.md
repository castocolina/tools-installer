# Phase 19 code review (opencode, router-env/my-plan-review)

## Findings

### P19-01 [HIGH] Removal can promote an authorized file into a recursive directory deletion
- File: `installer/uninstall.py:411–417`, `installer/uninstall.py:387–396`
- Problem: Receipt verification checks both path and type, but the removal plan retains only paths. If a receipt-proven raw file such as `~/.local/bin/yq` is replaced by a nonempty directory after verification, `remove_paths()` reclassifies it and calls `shutil.rmtree()`. This recursively deletes content that was never authorized as a directory. Verifying other artifacts before deletion widens this window.
- Fix: Preserve the authorized artifact type through deletion. File and link artifacts must use `unlink()`, which safely refuses a replacement directory; only directory artifacts may reach recursive removal. Add a deterministic test that substitutes a directory between verification and deletion.

### P19-02 [HIGH] A refresh during Status grouping can duplicate a row and crash the TUI
- File: `installer/catalog_tui.py:104–112`, `installer/tool_browser.py:198–207`
- Problem: Status grouping reads each tool’s health separately for every health group. If the worker publishes between the CHECKING and OK groups, one tool can belong to both groups. `_rebuild()` then inserts the same tool ID twice into `DataTable`, which rejects duplicate row keys. Other transition timings can omit a tool entirely. Atomic publication does not make this sequence of independent reads atomic.
- Fix: Capture one snapshot for each rebuild and use it consistently for grouping, sorting, row cells, and detail rendering. Add a deterministic test that publishes between health-group evaluations.

### P19-03 [MEDIUM] A malformed receipt path escapes the fail-closed reader
- File: `installer/receipts.py:398–406`, `installer/receipts.py:346–368`
- Problem: An absolute artifact path containing a JSON-encoded NUL, such as `"/tmp/x\u0000"`, passes `_read_artifact()`. For a file artifact, `matches()` calls `lstat()`, which raises `ValueError` on supported Python versions; the handler catches only `OSError`. Because drift checking precedes path authorization, this malformed receipt can abort the entire refresh or uninstall even though its path could never authorize removal.
- Fix: Reject NUL-containing paths during receipt decoding and make matching fail closed on invalid-path errors. Cover the malformed receipt through refresh and removal planning, not just the decoder.

### P19-04 [MEDIUM] Receipt existence checks can abort operations before the safe reader runs
- File: `installer/uninstall.py:115–116`, `installer/version_status.py:1210–1215`
- Problem: Both callers check `exists()` before calling `receipts.read()`. On supported Python 3.11/3.12, an inaccessible receipts directory—for example, one accidentally changed to mode `000`—can make this check raise `PermissionError`. The whole refresh or uninstall then aborts instead of treating the receipt as unreadable and unproven.
- Fix: Distinguish confirmed absence from an inaccessible receipt path. Treat permission failures as present-but-untrusted, allowing neither adoption nor archive-layout fallback. Share that guarded check between both callers.

### P19-05 [MEDIUM] The rehash memo reuses a result for a different expected digest
- File: `installer/receipts.py:359–365`
- Problem: The memo stores a Boolean under `(path, live_size, live_mtime)` without including the expected digest. The reader permits two artifacts for the same path. If their recorded timestamps differ from the live timestamp, the first artifact’s correct digest caches `True`; a second artifact with a different digest receives that same `True`. Refresh and ordinary removal planning consequently accept a receipt containing a digest mismatch. Deletion-time verification remains protected because it bypasses the memo.
- Fix: Cache the computed digest rather than the comparison result, or include `artifact.sha256` in the key. Test two comparisons of the same live file against different expected digests.

### P19-06 [MEDIUM] Cached skill presence becomes a false green health state while checks are pending
- File: `installer/version_status.py:1175–1193`
- Problem: A stale host report adds only a note; cached `"present"` still produces settled health. Cached reports do not contain duplicate/disabled reasons or configuration steps. A cached Superpowers install with a current duplicate therefore publishes `✓ ok` with no steps until the skill probe finishes. `tests/test_version_status.py:4719–4749` explicitly demonstrates this transition from cached OK to freshly detected MISCONFIGURED. The same issue applies after invalidation.
- Fix: Keep probed user-scope packs CHECKING while their host reports are stale. Publish settled health only after current configuration evidence arrives, and change the tests that currently require cached green marks.

### P19-07 [MEDIUM] One absent host incorrectly overrides another host’s unknown result
- File: `installer/version_status.py:1175–1186`
- Problem: CHECKING is suppressed whenever any host answers `"absent"`. If Claude’s probe fails but Codex reports absent, the pack becomes MISSING even though Claude may have it installed. This regresses the previous consumer, which settled absence only when all host answers were absent; `inspect_status()` still follows that rule at `installer/skill_lifecycle.py:953–959`.
- Fix: Settle presence when a host confirms it, but require conclusive absence before publishing MISSING. Unknown answers from relevant present harnesses must retain CHECKING. Add a mixed absent/unknown fixture.

### P19-08 [MEDIUM] Terminal-check warnings disappear from health evidence
- File: `installer/version_status.py:1268–1284`
- Problem: `_terminal_facts()` keeps only `.drifted` and discards `.warnings`. A present WezTerm using a configuration such as `return { default_prog = {"bash"} }` produces `"wezterm: unsupported return shape"` without a drift entry (`installer/terminal_shell.py:461–467`). Its row can therefore show `✓ ok` without explaining that configuration checking failed. A user-owned Konsole profile follows the same path.
- Fix: Carry returned warnings into row-specific “terminal shell not checked” reasons. Do not offer an automatic repair for a configuration shape the synchronizer cannot handle. Test returned warnings through the refresh service.

### P19-09 [MEDIUM] Multiple canonical user plugin copies lose their duplicate reasons
- File: `installer/skill_lifecycle.py:840–850`
- Problem: Two enabled canonical user entries—for example, Superpowers versions `6.4.1` and `6.2.0`—make `_claude_matches()` report absent. However, `_claude_fixes()` puts both entries in `users`, excludes both from `copies`, and returns no reasons or steps. The row says MISSING without explaining the duplicate versions. The two-entry input already exists in `tests/test_skill_lifecycle.py:998–1003`, but that test checks only presence.
- Fix: Detect surplus canonical user entries and emit their duplicate reasons. Suppress unsafe automatic cleanup where the CLI cannot distinguish the version to preserve. Extend the existing fixture to assert the complete report.

### P19-10 [MEDIUM] An unreadable project install is classified as empty and offered a reinstall
- File: `installer/skill_lifecycle.py:419–423`, `installer/skill_lifecycle.py:549–567`
- Problem: `_has_gsd_entry()` returns `None` when a directory cannot be listed, but `_installed_runtimes()` collapses that result through `any()`. With a readable VERSION file and unreadable skills/commands directories, the runtime is excluded from installed runtimes, then classified as empty. The report generates a reinstall step despite having no evidence that the installation is empty.
- Fix: Preserve an inconclusive runtime result. When no directory confirms an install and a required read fails, emit a “not checked” note and suppress the reinstall step. Classify an install as empty only after conclusive reads.

### P19-11 [MEDIUM] Repo detection follows an intermediate `.planning` symlink
- File: `installer/skill_lifecycle.py:389–391`
- Problem: `lstat()` examines only the final path component. A real directory under `~/git` whose `.planning` is a symlink to another project’s planning directory is admitted as a GSD repo because `.planning/config.json` appears regular. It then receives per-repo install steps, despite the walk’s explicit no-symlink contract.
- Fix: Require `.planning` itself to be a real directory before inspecting its config file. Add an intermediate-component symlink fixture beside the existing root and child symlink tests.

### P19-12 [MEDIUM] New state-test helpers still inspect the developer’s real install locations
- File: `tests/state_doubles.py:73–89`, `tests/state_doubles.py:118–133`
- Problem: The helpers supply scratch `skill_home` and `managed_bin_dir` values but do not redirect HOME or `Path.home()`. Their real refresh path still expands declared locations in `_location_proof()` and `_version_argv()`, and computes real opt/Application paths during removal planning. For example, the real-registry layout tests at `tests/test_layout_80x20.py:31–38` can inspect the developer’s actual SDKMAN Java installation. The new global fixtures do not sandbox these declared paths.
- Fix: Redirect HOME/`Path.home()` for tests using these helpers, or inject all location-dependent evidence. Strengthen the isolation test to reject reads outside the scratch home rather than checking only the supplied service directories.

### P19-13 [LOW] The receipt-test shell stub does not quote the interpreter path
- File: `tests/test_container_e2e_receipts.py:224–231`
- Problem: `_uv_stub()` interpolates `sys.executable` directly into shell text. An interpreter under a path such as `/home/user/My Projects/tools-installer/.venv/bin/python` makes Bash attempt to execute `/home/user/My`. The test fails independently of receipt behavior. The generated `TESTER_WORKSPACE` assignment also needs quoting for such a checkout.
- Fix: Shell-quote the interpreter and workspace paths with `shlex.quote()` before inserting them into the generated script.

## Summary

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| HIGH | 2 |
| MEDIUM | 10 |
| LOW | 1 |
| **Total** | **13** |

The three most important fixes are:

1. **Preserve authorized artifact types through deletion**, preventing file-to-directory escalation into recursive removal.
2. **Render from one captured snapshot**, preventing duplicate Status rows, missing rows, and mixed-generation cells.
3. **Make receipt handling fail closed end to end**, including malformed paths and inaccessible receipt directories.

Review used the ponytail-review and parallel-review skills, source/caller tracing, and the requested contracts. `git diff --check` reported no whitespace errors; the working tree remained clean.

Not checked: tests, installs, or live-host probes were not run, and no files were edited. The findings are source-verified; their runtime fixes still need regression tests.
