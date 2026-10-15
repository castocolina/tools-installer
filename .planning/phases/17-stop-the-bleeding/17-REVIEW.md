---
phase: 17-stop-the-bleeding
reviewed: 2026-10-15T04:10:32Z
depth: deep
files_reviewed: 49
files_reviewed_list:
  - .claude/architecture.md
  - installer/app.py
  - installer/apps.py
  - installer/doctor.py
  - installer/download.py
  - installer/execute_screen.py
  - installer/executors.py
  - installer/guards.py
  - installer/guidance.py
  - installer/model.py
  - installer/policy.py
  - installer/postinstall.py
  - installer/registry.toml
  - installer/render.py
  - installer/run.py
  - installer/session.py
  - installer/settings.py
  - installer/tweaks.py
  - installer/uninstall.py
  - installer/wizard_app.py
  - scripts/lib/prune-tmp-common.sh
  - scripts/prune-tmp-linux.sh
  - setup.py
  - tests/conftest.py
  - tests/test_app.py
  - tests/test_apps.py
  - tests/test_atomic.py
  - tests/test_catalog_tui.py
  - tests/test_doctor.py
  - tests/test_download.py
  - tests/test_engine.py
  - tests/test_execute_screen.py
  - tests/test_guards.py
  - tests/test_guidance.py
  - tests/test_policies_e2e.py
  - tests/test_policy.py
  - tests/test_postinstall.py
  - tests/test_prune_tmp_linux_sh.py
  - tests/test_registry.py
  - tests/test_render.py
  - tests/test_run.py
  - tests/test_session.py
  - tests/test_settings.py
  - tests/test_setup.py
  - tests/test_shellrc.py
  - tests/test_uninstall.py
  - tests/test_update.py
  - tests/test_version_status.py
  - tests/test_wizard_app.py
findings:
  critical: 1
  warning: 7
  info: 7
  total: 15
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-10-15T04:10:32Z
**Depth:** deep
**Files Reviewed:** 49
**Status:** issues_found

## Summary

I reviewed the whole phase diff `a7dba6f..HEAD` (49 non-planning files) against the code around it. I traced these call chains:

- `plan_removal` → `classify_tools` → `UninstallScreen.__init__` → `run_live`
- `_execute_worker` → `InstallRunFinished` → both `fold_run` callers → `_session_exit_code`
- `move_link_mode` ↔ `SettingsStore.set_link_mode` ↔ the ban, tweak and cache-redirect closures
- `link_executable` and the install, update and raw download paths
- `load_settings` → `_settings_store` → every route in `setup.py`

`make validate` gates are green: pyright strict reports 0 errors, ruff is clean, and vulture is clean at 80%.

I ran scratch probes outside the repo to confirm the defects. No source file was changed.

- **CR-01:** reproduced (`RuntimeError` when building `UninstallScreen`).
- **WR-01:** reproduced (the screen showed "Failed." while `install_summary.has_failure` was `False`).
- **WR-02:** reproduced (after two failures, the policy block was gone from both modes).
- **WR-07:** the suppression-free alternative was checked with pyright strict.

The main concerns:

- A crash introduced by the new removal proof (CR-01).
- Two places that disagree about what a failure is (WR-01, WR-06).
- Rollback holes in `move_link_mode` (WR-02).
- The link-safety guard covers only the install path. The update and raw-download paths still write through, or link to, things that are not regular files (WR-03, WR-04).

Not reported, per the orchestrator: the registry's `sudo dnf/apt-get/pacman` methods now fail fast under the session-isolated StreamingRunner. That is accepted until Phase 22.

Orchestrator item 1 is confirmed as WR-07. Orchestrator item 2 is confirmed as IN-01.

## Critical Issues

### CR-01: A symlink loop at any catalog download link name crashes every TUI route at launch, and `make uninstall --yes` too

**File:** `installer/uninstall.py:146-151`

**Issue:** `plan_removal` calls `link.resolve()` and `opt.resolve()` without a guard. On Python 3.11 and 3.12 (the project allows `>=3.11`; uv runs 3.12.12 here), non-strict `Path.resolve()` raises `RuntimeError("Symlink loop from ...")` when the path loops.

`classify_tools` calls `plan_removal` for every catalog tool. `UninstallScreen.__init__` evaluates the rows through `run_live`, which catches only `OSError`, `CommandError` and `ShellrcRefusal`. Every view screen is built when the app mounts, so the `RuntimeError` escapes and the whole app dies on every route: setup, doctor, fix, uninstall and guard. The CLI `run_uninstall` (`app.py:563`) crashes the same way.

The old `plan_uninstall` never resolved links (it only checked `exists`/`is_symlink`), so this is a regression introduced by 17-09.

Reproduced in a scratch HOME: `~/.local/bin/foo -> foo` plus a tarball tool with `member = "foo"`. Building `UninstallScreen(UninstallInputs(rows=lambda: classify_tools(...)))` raises `RuntimeError Symlink loop from '/tmp/.../.local/bin/foo'`.

The same unguarded resolve also affects `opt.resolve()` when `~/.local/opt/<name>` loops.

**Fix:** An unresolvable link is unproven, so skip it. Add one test with a self-loop at a catalog link name. It should expect an empty `removable` and no exception.

```python
            if not link.is_symlink():
                continue
            try:
                resolved = link.resolve(strict=True)
                opt_real = opt.resolve(strict=True)
            except (OSError, RuntimeError):  # dangling or looping: never proof
                continue
            if not resolved.is_file() or not resolved.is_relative_to(opt_real):
                continue
```

## Warnings

### WR-01: The Execute screen shows red "Failed." for a run that exits 0, because the two `fold_run` calls get different `not_attempted` lists

**Files:** `installer/execute_screen.py:960-971`, `installer/wizard_app.py:3015-3021`

**Issue:** `fold_run`'s docstring says both callers "cannot disagree about what counts as a failure". They do disagree.

- `ExecuteScreen.on_install_run_finished` folds `self.not_attempted`. That list also includes every `_to_update` tool whose progress row is still `pending`.
- `UnifiedApp.on_install_run_finished` folds only `message.not_attempted`.

An update that `_run_updates` skips posts no `UpdateToolFinished`, so its row stays `pending`. That happens for "update already in flight for X" and for "ownership could not be resolved". Only the screen then counts the tool as not attempted.

Reproduced with the existing `_RecordingUpdateService` and a pre-taken `begin("other")` latch. The screen status was `"Failed. enter or esc returns to the catalog."` with `has_failure=True`. `app.install_summary.has_failure` was `False`, so the process exits 0.

`fold_run` itself says skips are not failures, so the screen is the side that is wrong.

The acceptance test `test_all_skipped_run_exits_0` (`tests/test_setup.py:3306`) does not catch this. It patches `install_summary` with an `already=("rg",)` bucket and never drives a real skipped row through either fold.

**Fix:** Fold the worker's list on the screen too, and keep `self.not_attempted` only for the log line:

```python
        folded = fold_run(
            message.summary,
            not_attempted=message.not_attempted,  # same input UnifiedApp folds
            ...
        )
```

Then add one ExecuteScreen test that drives the in-flight-latch skip. It should assert both a "Done." status and `app.install_summary.has_failure is False`.

### WR-02: `move_link_mode` restore paths can silently drop an active policy, or leave a stray new-mode block

**File:** `installer/policy.py:188-256`

**Issue:** There are two concrete failure modes.

1. **Double failure drops the policy.** Policy P's new-mode `apply()` fails, so the code runs `set_link_mode(old_mode)`. If that save also fails (for example, the settings dir is unwritable), the live mode stays `new_mode`, because `SettingsStore` saves before it assigns. `_rollback` then runs `P.remove()` + `P.apply()` in the *new* mode. The apply fails again and the error is swallowed with `continue`. P is now absent from both modes.

   The error shown is only the settings-save error. `PoliciesScreen.active_state[P]` is still `True`, so the UI shows the ban or tweak as ON when it is gone.

   Reproduced with fake closures: the output was `raised: settings.json unwritable` / `live mode: split blocks: {'centralized': set(), 'split': set()}`.

   The `set_link_mode` parameter of `_rollback` is never used. The step that "returns every removed policy to the live (old) mode" assumes a live mode that this path does not guarantee, so the docstring is false here.

2. **Partial write is not cleaned up.** The per-policy restore (`set_link_mode(old_mode); policy.apply(); set_link_mode(new_mode)`) does not call `policy.remove()` first. Example: the ban's split-mode apply writes `~/.zshrc`, then fails on `~/.bashrc`. The `~/.zshrc` block stays while the report says "old block restored", so the policy is now active in both modes' files.

**Fix:**

- Call `policy.remove()` (mode-independent, per the docstring) before restoring in the old mode.
- In `_rollback`, drop the unused parameter and collect the ids whose re-apply failed.
- Raise or report those ids so the screen can set `active_state[id] = False` and name them. For example: `raise OSError(f"{restore_exc}; not restored: {', '.join(lost)}")`.

### WR-03: The update paths still link a directory member; only install got the `is_file()` guard

**Files:** `installer/download.py:332`, `installer/apps.py:193`

**Issue:** SPEC R1 says a non-regular-file member links nothing, and `link_executable` enforces that on install. The update paths validate with `exists() and os.access(X_OK)` instead. A directory passes both checks.

So `update_download` → `_replace_archive` for a registry entry whose `member` names a directory (the exact Sublime defect class, whose data fixes are deferred to Phase 18) does three things:

- relinks `~/.local/bin/<name>` to the directory,
- runs `chmod` on the directory,
- reports the update as successful.

`update_app` → `_validate_app` has the same gap.

**Fix:** Use the same predicate install uses:

```python
        if not live_binary.is_file() or not os.access(live_binary, os.X_OK):
```

Make the same change in `_validate_app` (`path.is_file()`), and add one update test with a directory member.

### WR-04: Raw downloads still write through an existing link and shell `chmod +x` (same hazard class as H1)

**File:** `installer/download.py:169-173`, `installer/download.py:386-389`

**Issue:** The raw branches were left out of the D-01 sweep.

- `_install_unverified` runs `curl -fsSL -o <link>`.
- `_place_verified` runs `cp <asset> <link>`.
- Both then run `chmod +x <link>`.

`curl -o`, `cp` and `chmod` all follow a symlink at `<link>`. For a raw tool, `~/.local/bin/<name>` can be a link to a directory; `which()` ignores directories, so the tool counts as not installed and gets installed again. In that case:

- The verified path's `cp` copies the asset *into* that directory.
- `chmod +x` changes the directory.
- The run reports success while the link still points at a directory.

The raw tools are yq, direnv, shfmt, tldr, fx, dasel, wezterm and drawio. tldr and wezterm are checksum-verified, so they go through `cp`.

A link to another manager's file is overwritten through the link. That is the write-through SAFE-01 exists to stop.

**Fix:** Reuse the existing `_replace_raw(link, asset_path)` for the verified raw install (sibling temp + `os.replace`, which replaces the link itself). For the unverified raw install, fetch into a temp file first and then call `_replace_raw`. This also removes the last shelled `chmod +x` calls.

### WR-05: A damaged settings.json is silent on every headless route, and headless wiring then uses the default mode

**File:** `setup.py:1281-1287` (and its callers in `main`, `_run_fix`, `_run_doctor`)

**Issue:** `SettingsStore.warning` reaches the user only through `_build_app(startup_warning=...)`, which means only on the TUI. These routes all call `_settings_store` and drop `store.warning`:

- `--all/--categories`
- `--guard` without a TTY
- `--fix --link-mode`
- non-TTY `--fix`
- non-TTY `--doctor`

A user whose `settings.json` is corrupt and whose real mode is `split` runs `make setup ARGS="--all --yes"`. `configure_path` then silently wires `rc_paths_for_mode("centralized")` with no notice. SPEC R8 says the app "falls back to defaults, shows a warning".

**Fix:** In `_settings_store` (setup.py is allowed to print), print the warning once:

```python
    if loaded.warning:
        Console(stderr=True).print(loaded.warning, style="yellow")
```

Alternatively, print `store.warning` in each headless branch before acting.

### WR-06: A hard abort (ctrl+c) mid-run exits 0 on every route

**Files:** `setup.py:1263-1266`, `setup.py:1290-1296`, `installer/wizard_app.py:3081-3083`

**Issue:** `action_hard_abort` calls `self.exit(None)` with no check. If the user presses ctrl+c while `ExecuteScreen` is running, the app exits before `InstallRunFinished` reaches `UnifiedApp`, so `install_summary` stays `None`.

- `_run_interactive_wizard` prints "Aborted." and returns 0.
- `_session_exit_code` returns 0 for doctor, fix, uninstall and guard.

The app's own warning says this abort "can leave the current tool half-installed". The phase goal is "every failed or crashed run reports failure and exits 1".

**Fix:** Have UnifiedApp record that a run is in flight: set it when `ExecuteScreen.action_start` posts, and clear it in `on_install_run_finished`. Make `_session_exit_code` (and the wizard's `summary is None` branch) return 1, or 130, when a run was interrupted. Add one test that presses ctrl+c during a blocked install.

### WR-07: The scoped `pyright: ignore[reportUnknownMemberType]` in the owner-cell test hides a fixable typing gap (orchestrator item 1)

**File:** `tests/test_catalog_tui.py:2043`

**Issue:** The gap is real but comes from a third party. `WorkerManager.wait_for_complete(self, workers: Iterable[Worker] | None = None)` uses a bare generic `Worker`, so pyright strict reports `Iterable[Worker[Unknown]]`. I confirmed this with a scratch probe.

It is not a false positive, and it does not need suppressing:

1. **The file already has a suppression-free wait for the version refresh.** Four tests (around lines 1694-1720 and 1755-1777) poll `app.catalog.version_refreshing` with `pilot.pause()`.
2. **A one-line equivalent type-checks clean.** `await asyncio.gather(*(worker.wait() for worker in app.workers))` passes, because `WorkerManager.__iter__` returns `Iterator[Worker[Any]]`. I verified it with `uv run pyright` in strict mode: 0 errors on the alternative, 1 on the original.

The cited precedent (`tests/test_execute_screen.py:2740`) is a different library: `pytest.approx` has a partially-unknown return type and no typed equivalent. So the precedent does not justify this site.

`.claude/python-tooling.md` allows a suppression only for a genuine false positive, prefers typing the boundary, and requires that the suppression be "called out to the user for approval before committing". 17-01-SUMMARY lists it as an auto-fixed deviation with no record of approval.

**Fix:** Delete the ignore and its comment, and use the file's existing pattern:

```python
        await asyncio.gather(*(worker.wait() for worker in app.workers))
```

Or poll `app.catalog.version_refreshing` the way the neighbouring tests do.

## Info

### IN-01: The 17-01-SUMMARY duration and timestamps do not match the commit history (orchestrator item 2)

**File:** `.planning/phases/17-stop-the-bleeding/17-01-SUMMARY.md:95,106-108`

**Issue:** The summary records `duration: 140min`, started `2026-10-14T18:37:00Z`, completed `2026-10-14T20:55:00Z`. The git history shows:

- the phase-start commit `a7dba6f` at 18:36:33 -0300,
- the three task commits at 18:41, 18:44 and 18:54 -0300,
- the summary commit `bd54566` at 19:00:51 -0300.

Execution therefore took about 24 minutes. The `Z` timestamps are local -0300 times mislabeled as UTC. The "completed 20:55" value is later than the commit that recorded it.

**Fix:** Set `duration: ~24min` and give the started/completed times in UTC (21:37Z / 22:01Z), or derive them from the commit timestamps.

### IN-02: The Doctor repair text names the link, not the catalog entry, and advises `rm -rf` on a directory it cannot prove the installer owns

**File:** `installer/guidance.py:128-133`

**Issue:** For `subl`, the text says "reinstall subl from the catalog", but the catalog entry is `sublime` / "Sublime Text".

Because the scan never checks the registry (as D-13 locks), any `~/.local/bin/<x>` that dangles, or links to a directory, into `~/.local/opt/<x>` gets the advice `rm -rf ~/.local/opt/<x>`. That holds even when the user installed that tree by hand, for example `~/.local/opt/go`. Following that printed advice would delete user data, which conflicts with SAFE-03's "only proven artifacts" rule.

Nothing is executed, and D-13 locks the registry independence.

**Fix:** Word the advice conditionally ("if tools-installer installed it, remove ... and reinstall it from the catalog"), or name the catalog tool only when a catalog download method's link name matches.

### IN-03: Typo in the variable name `youself_hint`

**File:** `installer/uninstall.py:370-375`

**Fix:** Rename it to `yourself_hint`.

### IN-04: Tests split string literals to keep a plan acceptance grep at zero

**Files:** `tests/test_apps.py:64,90`, `tests/test_engine.py:198`

**Issue:** `shelled = {"l" + "n", "ch" + "mod"}` exists only so 17-02's acceptance grep (`grep -cE '"ln",|...'`) prints 0. This games a check instead of stating intent.

**Fix:** Use a named constant such as `SHELLED_LINKERS = frozenset({"ln", "chmod"})`, and make the plan grep target production files only.

### IN-05: `link_name` claims to be "the one rule" for install, update and uninstall, but receives different `member` strings

**Files:** `installer/uninstall.py:62-69`, `installer/download.py:130-134,151,248`

**Issue:** Install and update pass the *rendered* member (`target.member`, after `render_asset`). Uninstall passes the raw registry template (`method.params["member"]`). A future `github_release` whose member basename contains a placeholder and has no `bin_name` would produce a link that uninstall never finds, so it could be neither proven nor listed. No current registry entry triggers this; I checked the whole registry.

**Fix:** Either reject templated basenames without `bin_name` at registry validation, or correct the docstring.

### IN-06: UnifiedApp still accepts `execute=None` and keeps the exit-with-ids branch, which no production route can reach after D-12

**File:** `installer/wizard_app.py:2854`

**Issue:** D-12 removed `execute` from `_build_app` so that "no route can build an app that cannot execute". `UnifiedApp(execute: ExecuteInputs | None = None)` and the `self._execute is None` → `self.exit(result)` branch remain. Only tests use them.

**Fix:** Make `execute` required on `UnifiedApp`, or note that the branch is test-only.

### IN-07: When a crash follows a PATH-wiring failure, the crash text never reaches the log

**File:** `installer/execute_screen.py:688`

**Issue:** `error = error or f"run stopped: {exc}"` keeps the earlier `path_fail` text. The log prints `message.error` only when there is no path or verify error, so the exception detail is never shown. The status is still red.

**Fix:** Append the crash text instead of replacing it, for example `error = f"{error}; run stopped: {exc}" if error else f"run stopped: {exc}"`.

---

_Reviewed: 2026-10-15T04:10:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
