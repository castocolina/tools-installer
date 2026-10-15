---
phase: 18-registry-truth-and-drift-guard
reviewed: 2026-10-15T22:00:37Z
depth: deep
files_reviewed: 55
files_reviewed_list:
  - .claude/architecture.md
  - .claude/dev-environment.md
  - .claude/skills/tool-onboarding/SKILL.md
  - .github/workflows/verify-registry.yml
  - AGENTS.md
  - Makefile
  - README.md
  - docs/TROUBLESHOOTING.md
  - install.sh
  - installer/apps.py
  - installer/audit.py
  - installer/download.py
  - installer/engine.py
  - installer/executors.py
  - installer/install_ownership.py
  - installer/locations.py
  - installer/model.py
  - installer/ownership.py
  - installer/registry.toml
  - installer/render.py
  - installer/run.py
  - installer/status.py
  - installer/update.py
  - installer/verify_registry.py
  - installer/version_cache.py
  - installer/version_status.py
  - installer/versions.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/test_app.py
  - tests/test_apps.py
  - tests/test_audit.py
  - tests/test_download.py
  - tests/test_engine.py
  - tests/test_executors.py
  - tests/test_install_ownership.py
  - tests/test_install_sh.py
  - tests/test_locations.py
  - tests/test_makefile.py
  - tests/test_model.py
  - tests/test_ownership.py
  - tests/test_postinstall.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_run.py
  - tests/test_session.py
  - tests/test_skill_lifecycle.py
  - tests/test_status.py
  - tests/test_uninstall.py
  - tests/test_update.py
  - tests/test_verify_registry.py
  - tests/test_verify_registry_workflow.py
  - tests/test_version_cache.py
  - tests/test_version_status.py
  - tests/test_versions.py
findings:
  critical: 2
  warning: 7
  info: 8
  total: 17
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-10-15T22:00:37Z
**Depth:** deep
**Files Reviewed:** 55
**Status:** issues_found

## Summary

Scope: `git diff 22e6c5e..HEAD` excluding `.planning/` (55 files). Cross-file traces covered:
- install: `engine.install_tool` -> `download`/`apps` -> `executors.smoke_binary` -> `run.run_output_with_stderr`, plus the rendering of `errors[-1]`;
- verification: `verify_registry` -> `download.resolve_target`/`pinned_url` -> `versions.resolve_github_release`;
- ownership: install-path replacement against `uninstall.is_still_proven` and `atomic.recover_update_remnants`.

Several findings were reproduced in a scratch HOME rather than only reasoned about:
- the app `.old` leak;
- the url-less tarball crash of verify-registry;
- the checker/tar member divergence;
- the OSError smoke message with no reason;
- the truncation banner embedded in `architecture.md`.

Answers to the orchestrator's four items:

1. **`strip` on zip.** Install and checker disagree. `_extract_into` ignores `strip` for zip, but `_member_present` applies it. The checker also drops a leading `./` before stripping, which GNU tar does not do. The checker reads `strip = true` as 1, while install reads it as 0. The 18-15 gh change (`strip = 1` -> `0`) worked around a checker bug by editing data. The loader should reject `strip` on zip and raw methods (WR-02).
2. **Smoke stderr.** For a non-zero exit, stderr is available. It is already in `str(CommandError)`, on the line after `command failed (127): ...`. So "fuse: device not found" and "Missing X server" do reach `render_failure_details`, but only when the smoke error is the last error in the ladder. For an OSError launch (wrong arch ENOEXEC, missing ELF interpreter ENOENT), the reason is dropped entirely (WR-03).
3. **Coverage of `verify_registry.py`.** It is now 87%, measured to a scratch `COVERAGE_FILE`. The core safety guard of the registry writer has never run under test. The test named for that guard fails earlier, in a different function (WR-05).
4. **Truncated tests.** Per-file test-name diffs show only planned removals. Every file parses and every file ends cleanly. However:
   - one Phase 17 preservation assertion was deliberately inverted to bless deleting a pre-existing tree (CR-02);
   - the same edit-tool truncation hit a non-test file: `.claude/architecture.md` lost about 140 lines of binding doctrine (CR-01).

## Critical Issues

### CR-01: `.claude/architecture.md` truncated by an agent edit; ~140 lines of binding doctrine lost and a tool banner committed

**File:** `.claude/architecture.md:878-884` (introduced by `fd42638`, plan 18-01)
**Issue:** The file now ends mid-sentence ("...an entry would therefore cover whatever that function might"). Line 884 is a tool-output artifact: `[Showing lines 1-871 of 878 (50.0KB limit). Use offset=872 to continue.]`.

The diff for this file in 18-01 is +11/-141. It deleted the rest of the Phase 15.8 section (old lines ~871-1008):
- the shell-script PATH text scan rule;
- the `PNPM_HOME` open question;
- the entire `~/.shellrc` foreign-file consolidation doctrine: backup no-clobber, mode and bytes matching, symlink refusals, the "this project does NOT parse shell" rule, and the single-route rule.

`AGENTS.md` links this file as a non-negotiable rule source, and the deleted text governs live code in `installer/rcclean.py` and the consolidation path. Nothing catches this: `tests/test_docs.py` reads the file but does not check that it is complete.

**Fix:** Restore the tail from `22e6c5e`, then re-apply only the intended Phase 18 edits:
```bash
git show 22e6c5e:.claude/architecture.md > /tmp/arch.orig   # take lines 871-1008
# re-apply the 18-01/18-20 "verified key / smoke_argv" paragraphs onto the restored file
```
Add a guard to `tests/test_docs.py`: assert that `"Use offset="` and `"[Showing lines"` are absent, and that a sentinel phrase from the last section is present (for example `"this project does NOT parse shell"`).

### CR-02: Install path deletes a pre-existing `~/.local/opt/<name>` tree with no ownership proof

**File:** `installer/download.py:320-365` (reached from `install_download`, `download.py:219`); `tests/test_download.py:269-292`
**Issue:** Since 18-09, every archive install goes through `_replace_archive`. That function moves any existing `opt_dir(link.name)` aside with `os.replace(opt, old)` (line 339), then runs `shutil.rmtree(old)` (line 362).

Before this phase, the install extracted into the existing directory and deleted nothing. Install has no `is_still_proven` check, but `uninstall.py:128-156` deletes an opt tree only when the bin link proves ownership. An unproven tree is listed in `yourself` instead ("is this ours, not does this exist").

Example: a portable VS Code at `~/.local/opt/code` (VS Code portable mode keeps `data/` with extensions and settings inside the install directory). If `code` is not on PATH, `is_installed` returns False. The `vscode` tarball method (`link name = code`) then wipes the whole tree.

The Phase 17 test `test_reinstall_over_a_link_to_a_directory_leaves_its_files_byte_identical` was replaced. Its second half now asserts `assert not legacy.exists()` (`tests/test_download.py:292`), which blesses the deletion.

**Fix:** On the install path only, refuse to replace an existing opt tree unless the bin link proves ownership:
```python
# download.install_download, before _replace_archive
opt = opt_dir(link.name)
if opt.exists() and not uninstall.is_still_proven(link):
    raise ExecutorError(f"{opt} exists and is not proven to be ours; remove it or install manually")
```
Updates keep the unit replace, because they are already ownership-gated. Restore a test asserting that an unproven pre-existing tree survives an install byte-for-byte.

## Warnings

### WR-01: `install_app` over an existing bundle leaves `<app>.tools-installer.old`, which a later run restores over the fresh install

**File:** `installer/apps.py:192-212`, `installer/apps.py:119-129`, `installer/atomic.py:78-115`
**Issue:** `_stage_and_swap_app` moves an existing `live` bundle to `.old`, swaps, and validates, but only `update_app` deletes `.old` afterwards. `install_app` returns with `.old` still on disk.

Reproduced in a scratch HOME: `['Demo.app', 'Demo.app.tools-installer.old']`. `recover_update_remnants` "always restore[s] a leftover `.old` over `live`". So the next install or update first discards the new bundle for the stale one. If that run then fails, for example on network, the stale bundle stays live.

Reachable today when `~/Applications/<app>` exists but is not a directory (`is_installed` checks `is_dir()`), and through any future repair path for app kinds. No test covers a successful `install_app` over an existing bundle.

**Fix:** Move the `.old` cleanup and the warnings into `_stage_and_swap_app` after `_validate_app`, mirroring `download._replace_archive:359-365`. `update_app` then only forwards the warnings. Add a test asserting that no `.old` sibling remains after a successful install over a planted bundle.

### WR-02: verify-registry and install disagree on archive member layout (`strip`/zip/`./`)

**File:** `installer/verify_registry.py:182-186`, `installer/verify_registry.py:473-485`, `installer/download.py:62-67`, `installer/download.py:375-388`, `installer/model.py:52-78`, `installer/registry.toml:455-462`
**Issue:** D-07 promises that "a passing check means the real install works". There are three divergences, all reproduced against `_member_present`:
- **zip:** install runs `unzip <asset> <member>` and ignores `strip`. The checker strips names. With `strip = 1`, member `bin/gh` passes the check (`True`), while unzip matches nothing and the install fails.
- **`./`-prefixed tars:** GNU tar counts `.` as a component (`./top/bin/tool` with `--strip-components=1` gives `top/bin/tool`, verified locally). The checker removes `.` first, so `bin/tool` passes the check and fails the install. The correct member, `top/bin/tool`, is reported as drift.
- **bool:** for `strip = true`, `_strip_default` returns 1 (`isinstance(True, int)`), while install `_opt_int` returns 0.

The loader validates none of these cases. gh macOS now carries a meaningless `strip = 0` on a zip, a data edit (18-15) that hides the checker bug.

**Fix:** Have one helper own member semantics and call it from both sides. In the loader:
- reject `strip` when `archive == "zip"` or `raw = true`;
- require a non-bool `int >= 0`.

In the checker, never strip zip names, and strip tar names exactly as tar does (do not drop `.` first). Delete `strip = 0` from gh macOS. Add `./`-prefixed tar and zip-with-strip fixtures to `tests/test_verify_registry.py`.

### WR-03: Smoke failures lose their reason for OSError launches and are hidden behind later ladder errors

**File:** `installer/run.py:101-102`, `installer/executors.py:28-31`, `installer/executors.py:97-101`, `installer/render.py:101`
**Issue:** When a launch fails with an OSError, `run_output_with_stderr` raises `CommandError(cmd, 127)` with no detail. That covers a wrong-architecture binary (`ENOEXEC`) and a binary whose ELF interpreter is missing (`ENOENT`, for example a musl build on a glibc host). The smoke message then reads only `smoke run failed for X: command failed (127): X --version`. Reproduced with a bad-interpreter script and a garbage ELF.

The `_LOADER_ERROR` patterns `Exec format error` and `cannot execute binary file` can never match a direct exec: that text comes from a shell, while Python reports the case as `OSError`.

For non-zero exits, stderr is attached, but:
- `render_failure_details` prints only `errors[-1]`, so for a multi-method tool the smoke reason (GLIBC, FUSE) is replaced by the last method's unrelated error;
- the detail is the whole unbounded stderr. Electron's dbus noise buries the one line that matters, such as "Missing X server".

**Fix:**
```python
except OSError as exc:
    raise CommandError(cmd, 127, detail=str(exc)) from exc   # run.py
```
In `smoke_binary`, report the first `_LOADER_ERROR` line, else the last ~5 stderr lines. In `render_failure_details`, list each method's error, or at least any smoke error, not just `errors[-1]`.

### WR-04: verify-registry crashes exit with 1, the drift exit code

**File:** `installer/verify_registry.py:385-395`, `installer/verify_registry.py:617-635`, `installer/verify_registry.py:705`, `installer/verify_registry.py:1521`, `installer/verify_registry.py:1699-1700`
**Issue:** These paths escape `main`. Python then exits 1, which the workflow and the documentation treat as confirmed drift:
- **Handler re-raises:** the `except ExecutorError` handler calls `pinned_url(method)` again, so it raises again. Reproduced: a tarball without `url` crashes the run with `ExecutorError: ... required param 'url'`. The loader does not require the per-kind keys (`url`, `repo`, `asset`, `member`).
- **`http.client.HTTPException` (for example `IncompleteRead`):** these are not `OSError`. They escape `tracked_download` and `head_once`. `head_once` even stores any `BaseException` and re-raises it.
- **`UnicodeDecodeError`:** raised by `sidecar.read_text()` on a binary checksum file.
- **`json.loads`/`KeyError` in `upsert_drift_issue`:** not covered by `except CommandError`.

**Fix:** In the handler, use `method.params.get("url", "")` rather than `pinned_url`. Treat `http.client.HTTPException` and `ValueError` from reads as inconclusive. Wrap `main` so that an unexpected exception prints the error and returns 2, or a dedicated non-drift code, never 1.

### WR-05: The registry writer's safety guard is untested, and the test named for it never reaches it

**File:** `installer/verify_registry.py:1108-1113`, `tests/test_verify_registry.py:2041-2065`
**Issue:** D-09's guarantee is: "re-parse ... and assert the result equals the old document plus exactly the intended edits; any other difference aborts". Lines 1110-1111 (`TOMLDecodeError`) and line 1113 (`new_doc != expected_doc`) are never executed by the suite (measured).

`test_writer_refuses_an_unintended_change` raises in `_apply_edits_to_document` ("unknown tool" and "method index out of range") before any line is rewritten. Its final assertion `registry.read_text() == content` is vacuous, because `apply_registry_edits` takes a string and never touches the file.

Other uncovered branches that matter:
- checksum sidecar 404 -> drift, and 5xx/network -> inconclusive (706-735);
- asset GET 404 after a passing HEAD (799-819);
- `RegistryWriteError` -> exit (1678-1680);
- upsert failure -> exit 2 (1691-1693);
- `--candidate` without `--write` (1685-1686);
- the auto-bump "different newer tags" failure (1350-1359).

**Fix:** Add a test where the line rewrite and the document edit diverge, so the equality guard must fire. For example, `verified=2026-10-01` (no spaces) makes the writer insert a duplicate key, and the re-parse raises. Add one test per branch listed above.

### WR-06: `main()` validates usage after the network run and reuses exit 64 for write-guard failures

**File:** `installer/verify_registry.py:1660-1686`
**Issue:** `check_registry` runs over the full network before `--candidate` is parsed (1662) and before the `--candidate requires --write` check (1684). A typo therefore costs a full catalog of API reads, against an unauthenticated budget of 60/h, before exit 64. `RegistryWriteError` also returns `EXIT_USAGE` (64), although Ledger L-18-17 reserves 64 for `--candidate` usage errors.

**Fix:** Parse and validate `--candidate` and the `--write` dependency before calling `check_registry`. Give the write-guard failure its own exit code.

### WR-07: Filesystem `OSError` from download and app executors escapes `install_tool` and aborts the whole batch

**File:** `installer/download.py:297-307`, `installer/download.py:324`, `installer/download.py:345-358`, `installer/engine.py:235`, `installer/session.py:216-235`
**Issue:** `install_tool` catches only `CommandError`, `ExecutorError` and `VersionError`, and `run_installs` has no guard. Since all archive installs now go through `_replace_archive`, these raw `OSError`s reach the install path:
- `recover_update_remnants(opt)` (a stale `.new` that is a file or a symlink makes `rmtree` raise);
- the rollback `os.replace(old, opt)` and `_undo_archive_swap` inside `except` blocks, which also mask the original error;
- `_replace_raw`'s `copy2`, `chmod` and `os.replace`, where ENOSPC on a ~150 MB AppImage is the realistic trigger. On a failed copy, the partial `<link>.tools-installer.new` is also left in `~/.local/bin`.

One tool's disk error ends the run for every queued tool. The raw path was already like this; this phase widened the exposure.

**Fix:** At the executor boundary, convert `OSError` to `ExecutorError` (wrap the bodies of `install_download` and `install_app`). In `_replace_raw`, unlink `new` on any failure, not only on a smoke failure.

## Info

### IN-01: Stale docstrings contradict the new behavior

**File:** `installer/download.py:95-101`, `installer/engine.py:114-117`, `installer/executors.py:87-92`
**Issue:**
- `resolve_target`: "tarball is verbatim and does not support checksums". Tarballs now render `{ver}` and verify `sha256`.
- `_perform`: "app zips have no published checksums". Pinned app zips are now verified.
- `smoke_binary`: "DISPLAY and WAYLAND_DISPLAY are removed so a GUI binary cannot open a window". That is false on macOS, where the draw.io app CLI is smoked with plain `--version`, unverified on macOS.

**Fix:** Correct the three docstrings. Note the macOS limitation, or declare `smoke_argv` for the draw.io app methods.

### IN-02: Dead or duplicated code in the new modules (rule 5)

**File:** `installer/verify_registry.py:561,687-696` (`_full_verify`, never passed False); `:396-397` (`except ValueError`, unreachable because `resolve_target` wraps ValueError); `:617-618` (`except (...): raise`, a no-op); `:831,837` (`actual_hash, listings` assigned twice); `:1645,1655` (`import sys` twice inside `main`); `installer/download.py:147-148` (the tarball `checksum` branch, unreachable because `METHOD_PARAMS["tarball"]` rejects `checksum`); `installer/verify_registry.py:207-215` and `:1217-1227` (two copies of the `app/cli` member rule)
**Fix:**
- delete the unreachable branches and the `_full_verify` parameter;
- hoist `import sys`;
- derive the app member from one helper, ideally `apps.cli_spec`.

### IN-03: The loader's future-date check gates every app launch on the host clock

**File:** `installer/model.py:707-709`
**Issue:** A user whose clock is more than one day behind the newest `verified` date cannot start the installer at all, because `load_tools` raises. Examples: an RTC-less board, or a VM restored from a snapshot. This is within the letter of SPEC R2 and L-18-06, but the cost (the whole app) is far larger than the defect it guards against (a bad data date).
**Fix:** Keep the hard check in tests and verify-registry. Consider a runtime `today=None` mode that warns instead of raising.

### IN-04: `release_resolver` depends on function identity; any wrapped production resolver silently drops digest verification

**File:** `installer/versions.py:405-415`
**Issue:** Only `resolve_tag is resolve_github_tag` gets digests. A future cached or wrapped tag resolver in `setup.py`/`ExecuteScreen` would turn every no-checksum `github_release` into "unverified" with no error. The docstring says it is "not silently skipped", which contradicts what the code does.
**Fix:** Pass a `ReleaseResolver` explicitly through `install_tool` and `ExecContext`, rather than inferring it from identity.

### IN-05: Workflow token scope and duplicate-issue race

**File:** `.github/workflows/verify-registry.yml:21-22`
**Issue:**
- `GH_TOKEN` (issues: write) is set in job-level `env`, so it is visible to every step, including third-party actions pinned by mutable tags (`astral-sh/setup-uv@v5`, `actions/cache/*@v4`).
- There is no `concurrency:` group. A manual dispatch that overlaps the Monday run can make both runs list zero open issues, so both create one.

**Fix:** Move `GH_TOKEN` into the `Check registry drift` step's `env`, pin actions by SHA, and add `concurrency: verify-registry`.

### IN-06: The manager-smoke PATH sandbox is opt-in per test module

**File:** `tests/test_engine.py:45-50`, `tests/test_app.py:3347-3356`, `tests/test_session.py:596-604`, `tests/test_postinstall.py:551-553`
**Issue:** `_run_manager_smoke` executes `shutil.which(tool.cmd)`. Only the modules patched in 18-19 sandbox PATH. A future test that reaches `install_tool` with a manager method while `is_installed` is faked False will run the developer's real `<cmd> --version`, which breaks the hermetic and offline rule.
**Fix:** Add a `conftest.py` autouse guard that stubs `engine._run_manager_smoke` (or sandboxes PATH). Tests that exercise the smoke opt back in.

### IN-07: The fall-through test does not prove the failed method left no link

**File:** `tests/test_engine.py:308-312`
**Issue:** `test_smoke_failure_falls_through_to_the_next_method` asserts only that `rg2` exists. It never checks that the first method's `bin/rg` was not created. That is the "broken binary never gets a link" property.
**Fix:** Add `assert not (bin_dir / "rg").exists() and not (bin_dir / "rg").is_symlink()`.

### IN-08: The GitHub token is attached with `add_header`, which urllib copies onto redirects to any host

**File:** `installer/versions.py:362`
**Issue:** The "never another host" promise in `urlopen_fetch` is enforced only on the first URL. `HTTPRedirectHandler.redirect_request` (Python 3.12) copies `req.headers` into the redirected request. Today `api.github.com` redirects only to itself, so this is not exploitable now.
**Fix:** `req.add_unredirected_header("Authorization", f"Bearer {auth}")`.

---

_Reviewed: 2026-10-15T22:00:37Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
