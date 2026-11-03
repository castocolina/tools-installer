---
phase: 21-one-screen-family
reviewed: 2026-11-03T16:33:14Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - installer/wizard_app.py
  - installer/version_status.py
  - installer/tool_browser.py
  - installer/catalog_tui.py
  - installer/execute_screen.py
  - installer/app.py
  - installer/uninstall.py
  - installer/policy.py
  - installer/session.py
  - installer/render.py
  - installer/ui_common.py
  - installer/enums.py
  - installer/pnpm_globals.py
  - installer/guidance.py
  - installer/ownership.py
  - installer/resolve.py
  - setup.py
findings:
  critical: 0
  warning: 10
  info: 8
  total: 18
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-11-03T16:33:14Z
**Depth:** deep
**Files Reviewed:** 17 (`git diff 390f464..HEAD -- installer setup.py`; `installer/registry.toml` is a data-only pin bump and was not reviewed)
**Status:** issues_found

## Summary

I reviewed the single refresh owner (`request_refresh` / `await_publication` / `on_refresh_finished`), the `MutationLock` and every `begin_mutation` / `refuse_if_mutating` site, the removal path from end to end (`_apply_removal` → `_remove_worker` → `perform_uninstall` → `remove_proven` → `on_removal_finished`), the quit-wait, the epoch, pending-id and `_managers_invalid` handling in `VersionRefreshService`, the Policies live reads, and the Doctor lifecycle. I also traced the call chains into `installer/app.py`, `installer/uninstall.py`, `installer/daemon.py`, `installer/ownership.py` and the Textual worker and shutdown code.

The core design holds.
- Waiters are served only once no pass is pending.
- A pass that raced an `invalidate` is discarded under the lock.
- `mark_pending` ids are filtered at the one publication point and in the `refresh_skills` rebuild.
- `remove_proven` re-proves every path with `verify=True` at deletion time, so no path is deleted without fresh proof.
- An unknown owner gets `unknown` plus the fixed sentence, never a manager or a command.
- Every worker mutation posts its completion from `finally:`, and the completion handler releases the lock first.

I found no Critical defect. The risks that remain:
- one mutation path that bypasses the lock while the launch daemon apply holds it (a race on `~/.myshellrc`)
- a removal summary that can claim a tool was removed when one of its previewed paths was not
- a pass crash that writes no status copy
- the Doctor fix applying after its preview failed to read
- three widget queries on the shutdown path that have the same root cause as the macOS failures fixed in bc6b9ef and 765c0e5
- quit and exit-code behaviour for mutations other than a removal

**macOS CI timeout on cddad0c (bf456b6..cddad0c):** I found no unbounded wait or infinite loop in the production code of that range.
- `_managers_invalid`, the Doctor `RefreshRequested` posts and the first-run `enter_view()` add no wait.
- Measured locally, serially, over the whole suite: 420.9 s at bf456b6 and 426.7 s at cddad0c (+5.8 s, all from the 14 new tests at ≤0.5 s each). That cannot turn 8.5 min into more than 12 min.
- The arithmetic matches a single 300 s stall. Python 3.12's `asyncio.Runner.close()` runs `shutdown_default_executor(THREAD_JOIN_TIMEOUT=300)`, and Textual thread workers run on that default executor (`textual/worker.py` `_run_threaded` → `loop.run_in_executor(None, …)`). So any test that ends while a worker thread is still blocked stalls its event-loop teardown for up to 5 minutes. On macOS (3 vCPU → `round(3*0.4)=1` xdist worker) that stall is serial: 8.5 min + 5 min + ~2.5 min of setup and validate is more than 15 min.
- The suspects for such a stall are in WR-09 and WR-10.
- The macOS rerun (attempt 2 of run 41670062871) was still in progress when this report was written.

## Warnings

### WR-01: The first-run link-mode pick bypasses the mutation lock while the launch daemon apply writes the same `~/.myshellrc`

**File:** `installer/wizard_app.py:3108-3157` (with `:2855-2856`, `:2876-2887`; `setup.py:120`; `installer/daemon.py:382-394`)
**Issue:**
- `on_mount` starts `_apply_daemon_default_worker` (lock held as `DAEMON_DEFAULT` from `__init__`) and then pushes `LinkModeScreen`.
- `_first_link_mode_picked` runs `move_link_mode(aware_active, …)` on the event loop with no `refuse_if_mutating` check. That move removes and re-applies the ban and tweak blocks, which write `~/.myshellrc`.
- The daemon worker's `ensure_daemon_default` → `daemon.record_decided(state_path)` is a read-modify-write of the same file: `_DAEMON_STATE_PATH = _MYSHELLRC` (`setup.py:120`), and `daemon.py:392-394` reads, edits and atomically writes it.
- If the user answers the picker while the apply runs, one writer's edit is lost. A tweak block is either duplicated across modes or dropped, or the decided marker is lost.
- The Policies `m` path guards exactly this (`:2367-2370`: "the modal can outlive a mutation that started after it opened"). The first-run path does not.
- The window is narrow: a first run with active link-mode-aware policies and no decided marker, for example after an upgrade or a deleted `settings.json`, with the answer given before a `launchctl` or `systemctl` call returns. It still breaks the one-lock guarantee D-05 relies on.

**Fix:** Check the lock at the mutation point, as `_link_mode_picked` does:
```python
setter = self._set_link_mode
if setter is None:
    return
if self.refuse_if_mutating(target):   # MutationLock method on the app
    return
```
To avoid making the user re-answer, an alternative is to defer the move until `on_daemon_default_applied` releases the lock (store the picked value and run the move there).

### WR-02: A removal can report a tool `removed` while one of its previewed paths was not deleted, and the refusal is hidden

**File:** `installer/app.py:692-716`, `installer/wizard_app.py:1505-1536`, `installer/uninstall.py:315-326`
**Issue:**
- `perform_uninstall` keeps, for each tool, only the paths its current non-verified plan still names (`mine`).
- A previewed path that is no longer named goes only into `refused` (the "unclaimed" tuple at `:711-715`). The tool still lands in `removed` when its other paths succeed (`:707-710`).
- `SweepResult.removed` is documented as "tools whose every previewed path was removed" (`uninstall.py:360`), so this breaks that contract.
- `UninstallScreen._applied_summary` renders `swept.warnings` only inside `if decision.remove_tweaks:` (`wizard_app.py:1505, 1534`). For a tool-only removal the refusal line is never shown.
- `remove_proven` then deletes the receipt, because every path in the fresh plan is gone. The leftover file stays on disk with no receipt, and the screen says `removed`.
- The selection comes from the last painted entry, kept while the state is unknown (`_unknown_entry`). So the trigger is any in-session change to the receipt or layout between the paint and the removal, such as a reinstall that moved the artifact.

**Fix:** Count a tool as removed only if every previewed path that belongs to it was removed. Surface the unclaimed-path refusals whatever levers were chosen:
```python
# app.py: attribute unclaimed previewed paths back to the selected tool by name and fail it
leftover = [p for p in decision.paths if p not in claimed]
...
# wizard_app.py _applied_summary: move the warnings line out of the tweaks branch
parts.extend(f"warning: {warning}." for warning in swept.warnings)
```

### WR-03: A pass that raises an unmapped exception leaves every row at `…` with no status copy

**File:** `installer/wizard_app.py:2911-2930`, `:2948-2956`
**Issue:**
- `_refresh_worker` catches `Exception` and puts its first line into `pass_error`. When `service.refresh` raises something `run_live` does not map (anything other than `OSError`, `CommandError` or `ShellrcRefusal`, for example a `ValueError` or `KeyError` from a cache or parse bug), no `RefreshPublished` is posted.
- `on_refresh_finished` passes the error only to `_publication_waiters`. It never calls `_write_state_line`.
- Every view then keeps `…` rows and shows no `tool state check failed: … — the next change retries it` line. T-21-11's mitigation (the retry copy) is silently skipped for exactly the unexpected failures.

**Fix:** Write the retry copy from the finish handler whenever the pass failed and no publication carried the error:
```python
def on_refresh_finished(self, message: RefreshFinished) -> None:
    self._refresh_running = False
    if message.error is not None and self._state_line is None:
        self._render_published()
        self._write_state_line(
            f"tool state check failed: {message.error} — the next change retries it")
    ...
```
Alternatively, post a `RefreshPublished(pass_error, None)` from the `except` branch.

### WR-04: Doctor `enter` wires the PATH even when the fix preview could not be read

**File:** `installer/wizard_app.py:572-573`, `:702-708`
**Issue:**
- `_refresh_body` drops the preview section on a failed `fix_preview` read and records `_preview_error`. That is T-21-41's mitigation.
- `action_apply` never consults `_preview_error`, so `enter` still runs `self._fix()` and edits rc files the user was never shown.
- T-21-41 names exactly this threat ("`enter` wires a PATH the user did not review"). Policies refuses the action on an unreadable row (`_refuse_unreadable`), and Doctor should do the same.

**Fix:**
```python
def action_apply(self) -> None:
    if self.applied:
        return
    if self.app.refuse_if_mutating(self):
        return
    if self._preview_error is not None or self._guard_error is not None:
        self._sync_read_status()               # keeps "Could not read the doctor state: …"
        self.post_message(RefreshRequested())
        return
```

### WR-05: Widget queries on the shutdown path have the same root cause as the macOS NoMatches failures

**File:** `installer/wizard_app.py:3020-3031` → `:2194-2201`; `:908-928`, `:952-966`, `:505-509` → `:565-566`
**Issue:**
- bc6b9ef and 765c0e5 established that under `run_test` teardown the app keeps dispatching messages after it stops running, and that Textual removes child widgets before their parents. `is_mounted` stays True on a screen whose children are gone.
- Only `_visible_app_screen`, `ToolBrowser.reload`, `on_removal_finished` and `on_job_states_read` were hardened.
- These handlers can still run during shutdown and query a removed widget:
  - `on_daemon_default_applied` → `PoliciesScreen.refresh_daemon_state`, guarded by `is_mounted` only, then `query_one(DataTable)` and `_start_job_state_read()`.
  - `DoctorScreen.on_globals_audited`, `on_globals_reinstalled` (no guard at all) and `on_disk_pressure_probed` (`is_mounted` only), each of which calls `_refresh_body` → `query_one("#doctor-body")`.
- All of them are fed by thread workers that finish at arbitrary times, which is the same race. 21-20 added one more Doctor entry (`_first_link_mode_picked` → `target.enter_view()` → a new audit worker).
- This would show up as a macOS-only `NoMatches` failure, not a hang.

**Fix:** Add one guard in the shared spots, the same check `on_removal_finished` uses:
```python
def on_daemon_default_applied(self, message):
    self.end_mutation()
    if not self.is_running:
        return
    ...
# DoctorScreen._refresh_body / PoliciesScreen.refresh_daemon_state
if not self.is_attached or not self.app.is_running:
    return
```

### WR-06: Quitting during a mutation other than a removal drops its outcome, and the process lingers invisibly

**File:** `installer/wizard_app.py:3341-3345`; `setup.py:1181-1189`
**Issue:**
- `_quit` waits only for `MutationHolder.REMOVAL`. For `UPDATE`, `GLOBALS_REINSTALL`, `POLICY_TOGGLE` and `DAEMON_DEFAULT` it calls `self.exit(None)` at once.
- The thread keeps running, and `App.run` → `asyncio.run` → `shutdown_default_executor` joins it. A `pnpm add -g` lasts minutes, during which the terminal shows nothing.
- Its completion message is never handled, so `UnifiedApp.on_tool_updated` never records a failed update. `setup.py` then sees `outcomes is None` and returns `Aborted.` with exit code 0 after an update that may fail.
- The lock now names the holder, so the removal quit-wait mechanism generalizes for little cost.

**Fix:** In `_quit`, wait for the workers of any held mutation. For example, map each holder to its worker group (`tool-update`, `globals-reinstall`, `policy-toggle`, `daemon-default`, `uninstall-removal`), then reuse `_exit_after_removal` with that group and the generic copy `Waiting for {holder} to finish…`.

### WR-07: During a removal no key can exit, and nothing gets out of a wedged remover

**File:** `installer/wizard_app.py:2680-2684`, `:3337-3365`
**Issue:**
- During a removal, both `q` and `ctrl+c` route to `_exit_after_removal`. The binding comment ("ctrl+c is the hard abort: unguarded, so it quits from anywhere") and `action_hard_abort` ("always exits") are no longer true.
- The tweak sweep inside the removal calls `launchctl` and `systemctl` teardown through `run_captured`, which has no timeout (`:2988-2990` says so for the same calls).
- A wedged user manager therefore leaves a TUI that no key can exit. Textual's raw mode swallows SIGINT, and every further `ctrl+c` just starts another `quit-wait` worker.

**Fix:** Keep the first press as the waiting quit, and let a second `ctrl+c` while `self.quitting` is already True force `self.exit(None)` with a warning that the removal may be incomplete. Also update the two comments.

### WR-08: The Installed-via wording does not match UI-SPEC:107-109, and a manager label appears on rows that remove installer artifacts

**File:** `installer/version_status.py:1904-1912`; `installer/ownership.py:1296`, `:1303-1308`, `:1310-1322`
**Issue:**
- UI-SPEC:107-109 requires `installer` for removable rows: with a receipt ("the owner label (`installer`, or the proven manager)"), by adoption and by layout.
- `uninstall_label` returns `removal_label(...) or owner_label(...)`. For an installer-owned record, `owner_label` returns the kind label (`GitHub release`, `tarball download`, `downloaded app`, `own installer`) or `installer artifact`. This is the ledger's known open note, and it is confirmed.
- Second case: `uninstall_group` returns `REMOVABLE` whenever `state.removable.removable` is non-empty, whatever the owner. A shadowed installer copy whose active binary belongs to brew therefore reads `Installed via: Homebrew`, `What gets removed: ~/.local/bin/rg`, and has a receipt-proof detail. The user can believe the Homebrew copy is what gets removed.

**Fix:** For `UninstallState.REMOVABLE`, return `"installer"` (the removed paths are installer artifacts by proof). Keep `removal_label or owner_label or "unknown"` for `MANAGED`. Where ownership names another manager, add that manager to the detail line (`— active copy: Homebrew`).

### WR-09: `test_epoch_guard_drops_stale_refresh_after_update` now passes only through its 5 s latch timeout

**File:** `tests/test_wizard_app.py:6879-6938`
**Issue:**
- The test takes 0.20 s at 390f464 and 5.1 s at HEAD (measured).
- Under the single refresh owner, the latched launch pass keeps `full-catalog-refresh` running. `await settle(app, pilot)` at `:6932` therefore waits until `assert release.wait(timeout=5)` fails inside the worker thread, which `_refresh_worker` turns into a pass error. Only then does the pending pass run.
- `release.set()` at `:6934` is dead, and the "stale pass dropped" path is no longer exercised.
- `settle`'s budget is 400 `pilot.pause()` calls, so the result depends on the runner's speed: a faster runner fails the test, and a slower one burns 5 s every run.

**Fix:** Release the latch before settling, then assert that the stale pass publishes nothing:
```python
await pilot.press("u")
await _settle_update(app, pilot)
release.set()                      # let the raced pass finish; the epoch guard must drop it
await settle(app, pilot)
assert app.catalog.query_one(DataTable[Any]).get_cell("rg", "ver").plain == "14.1.1"
```

### WR-10: Unbounded waits in the test doubles plus asyncio's 300 s executor join are the most likely cause of the macOS 15-minute timeout

**File:** `tests/state_doubles.py:322-328`; `tests/test_screen_family.py:279-290, 293-303, 422-435`; `tests/test_execute_screen.py:4140, 4167, 4190`; `.github/workflows/ci.yml:17`; `pyproject.toml:48`
**Issue:**
- `HeldRefreshService.refresh` blocks on `self.release.wait()` with no timeout. Its siblings `HeldRemover` and `_held_reinstall` use `timeout=10`.
- Six tests that use it set `release` only on the happy path, with no `finally`.
- Any assertion failure before the release (a timing-sensitive `pilot.pause()` count on a slow macOS runner is enough) leaves the worker thread blocked forever. `asyncio.Runner.close()` then waits `THREAD_JOIN_TIMEOUT=300` s, verified at 300 in this venv's Python 3.12.12.
- With one xdist worker on macOS, one such failure turns the ~8.5 min Test step into more than 13.5 min. That exceeds `timeout-minutes: 15` once setup and validate are added, and the failure itself is never reported because the job is cancelled.
- No `pytest-timeout` is configured, so a genuine hang is also unbounded.
- Separately, 24 `tests/test_setup.py` tests each wait the full `DAEMON_DEFAULT_WAIT_SECONDS=5` because `_capture_app` never runs the armed collector's worker. This is pre-existing (present at 390f464): about 120 s serial on macOS out of the 15-minute budget.

**Fix:**
- Bound the double: `if not self.release.wait(timeout=10): raise TimeoutError("HeldRefreshService was never released")`.
- Wrap the six tests in `try/finally: service.release.set()`.
- Add `pytest-timeout` (for example `timeout = 120` with the `thread` method) so a hang fails with a traceback instead of a cancelled job.
- Have `_capture_app` call `daemon_default_warnings.finish()`, or pass an unarmed collector.

## Info

### IN-01: `_managers_invalid` disables the manager backoff for as long as cache saves fail

**File:** `installer/version_status.py:1588`, `:1847-1848`, `:1872-1885`
**Issue:**
- The flag clears only inside a successful `save_pass`. While writes fail (a read-only cache directory or a full disk, as in the 21-20 test), and on a pass whose `fresh` is empty, every pass bypasses the persisted snapshot and re-runs `read_inventory` and `read_outdated` (`brew outdated` and the rest).
- The 30-minute `MANAGER_RETRY_BACKOFF` never applies.
- Coalescing bounds the rate, but every refused key and every Doctor evidence change now costs a full manager query.
- The held-writes case is the ledger's known note.

**Fix:** Keep the queried snapshot in memory (`self._snapshot_mem`) and, while `_managers_invalid` is set, reuse it through `should_fetch_managers` instead of forcing `None` once a pass has queried it.

### IN-02: Doctor prints every `ToolState.reasons` entry for pnpm-declared tools, not only the pnpm findings

**File:** `installer/wizard_app.py:620-627`
**Issue:** UI-SPEC wants the missing, unhealthy and incomplete shim findings. The loop also prints outdated facts, ownership notes and version notes in yellow under "pnpm-managed globals", which reads as Doctor findings.
**Fix:** Filter to the shared sentences (`PNPM_SMOKE_FAILED`, `PNPM_SPLIT_GROUP`, `PNPM_TRACKED_OFF_PATH` prefixes) or to `state.broken` plus the evidence notes.

### IN-03: `remove_failed` with an empty detail falls back to install wording

**File:** `installer/render.py:149-160`
**Issue:** With no detail, `outcome_detail_text` returns `no method succeeded`, which is install vocabulary. This is unreachable today (`first_line` and the refusal lines are never empty) but has no guard.
**Fix:** Give `remove_failed` its own fallback (`not removed`).

### IN-04: Stale comments after the rewrite

**File:** `installer/wizard_app.py:127-132` (`UninstallInputs.terminal_sync` says it is "Called from `_apply_removal`"; it is now `on_removal_finished`), `:2680-2682` and `:3337-3338` (ctrl+c "quits from anywhere" / "always exits", see WR-07), `:3175-3177` (`_install_closed` says the pass is started by `enter_view`; it is `request_refresh`).
**Fix:** Update the wording.

### IN-05: `_audit_globals_worker` lacks `exit_on_error=False` and a `finally` post

**File:** `installer/wizard_app.py:877-902`
**Issue:**
- This is pre-existing, but 21-19 and 21-20 made it more load-bearing: it now feeds `_record_pnpm_evidence` and runs on the first-run Doctor re-entry.
- An exception that `run_live` does not map crashes the app (Textual's default `exit_on_error=True`).
- With the flag added but no `finally`, `globals_auditing` would stay True, and `r` would answer "Still checking…" forever.

**Fix:** Use `@work(..., exit_on_error=False)` and post `GlobalsAudited(_GLOBALS_UNREADABLE, …)` from `finally`, as every other worker does.

### IN-06: Completion handlers write status on hidden views, which then greets the next entry

**File:** `installer/catalog_tui.py:707-737`, `installer/wizard_app.py:1564-1612`, `:2262-2283`
**Issue:** If the user leaves during an update, a removal or a job toggle, the result is written to the hidden view's status after `clear_transient` already ran. UI-SPEC's lifecycle table says re-entry starts empty except for a standing status. It is arguably useful, but it is undocumented.
**Fix:** Decide and document it. Either route late results through `_pending_warnings` to the visible view, or add this case to the UI-SPEC table.

### IN-07: `MutationLock.begin_mutation` overwrites a held lock without complaint

**File:** `installer/wizard_app.py:2657-2661`
**Issue:**
- A second `begin_mutation` replaces the holder, and the first `end_mutation` then releases both.
- Every current site checks `refuse_if_mutating` first, or sits behind a modal (`on_install_run_started`), so nothing triggers it today.
- No invariant enforces that ordering.

**Fix:** Add `assert self._mutation_holder is None, self._mutation_holder` in `begin_mutation` (the `DAEMON_DEFAULT` constructor take is the first holder).

### IN-08: Known open notes, confirmed against source

- 21-09 empty `paths` reading `remove failed`: unreachable from the TUI. A `REMOVABLE` group requires a non-empty `state.removable.removable` (`version_status.py:1901`), and a painted selectable entry always carries its paths. Only a direct `perform_uninstall` caller can hit it (`app.py:698-700`).
- The launch daemon-default apply refuses every mutation (`wizard_app.py:2855-2856`). This is by design of the one lock, and its window is unbounded when `launchctl` hangs (see WR-07 for the missing escape).
- The held-writes plus failed invalidate-clear case in `save_pass` is confirmed as described in RUN-LEDGER 2026-11-03 (headless route only, because the TUI never holds writes).
- The `uninstall_label` wording is WR-08.

---

_Reviewed: 2026-11-03T16:33:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

## Consolidated findings (3 lanes, verified)

**Consolidated:** 2026-11-03, over `390f464..HEAD` (HEAD 9813396).
**Lanes:**
- L1: gsd-code-reviewer, deep (this file, WR-xx / IN-xx).
- L2: opencode router-env/my-referee-one (`.review-diagnostics/20261103T161719Z-code-review/opencode-referee-one/lane.out`, R2-1..R2-12 in lane order).
- L3: ponytail-review (`.review-diagnostics/20261103T161719Z-code-review/ponytail-review.md`, P1..P8).

**How each finding was verified:** read against the current source (codegraph index synced, then file:line reads). Two claims were also measured:
- `tests/test_setup.py` under `--durations`: 23 tests at 5.00 s each.
- `test_epoch_guard_drops_stale_refresh_after_update`: 5.16 s.

No source or test file was changed.

**Totals:** 34 distinct findings from 38 lane items. Four defects were raised twice: C-04, C-09, C-10, C-14. L1 IN-08 only restates ledger notes, so it is not counted.

**Verdicts:**
- 30 CONFIRMED.
- 4 PARTIAL: C-16, C-22, C-23, and the test count in C-01.
- 0 REFUTED.

**Severity:** 1 High, 11 Important, 22 Minor.

**Need the user:** six items, because their fix would change a locked decision or UI-SPEC copy: C-08, C-23 (second half only), C-25, C-26, C-27, C-28.

| id | title | lanes | verdict | severity | scope | file:line |
|----|-------|-------|---------|----------|-------|-----------|
| C-01 | macOS 15-min timeout: `HeldRefreshService` waits with no bound and 3 tests release it only on the happy path, so asyncio's 300 s executor join stalls teardown | L1 WR-10 | CONFIRMED (mechanism; cause unproven without logs) | **High** | in (CI gate) | `tests/state_doubles.py:325-327`; `tests/test_screen_family.py:279-290, 422-435`; `tests/test_execute_screen.py:4167-4187` |
| C-02 | Epoch-guard test passes only through its 5 s latch timeout | L1 WR-09 | CONFIRMED (5.16 s) | Minor | in | `tests/test_wizard_app.py:6879-6938` |
| C-03 | 23 `test_setup.py` tests each wait the full 5 s daemon-default timeout (115 s serial on macOS) | L1 WR-10 | CONFIRMED (measured) | Minor | pre-existing (CI budget) | `setup.py:1181`; `installer/policy.py:1425`; `tests/test_setup.py:451-481` |
| C-04 | An unexpected exception in a pass writes no status; rows stay `…` | L1 WR-03, L2 R2-11 | CONFIRMED | Important | in | `installer/wizard_app.py:2911-2955` |
| C-05 | A pending pass starts after shutdown begins | L2 R2-10 | CONFIRMED | Important | in | `installer/wizard_app.py:2948-2953` |
| C-06 | The app's state line overwrites a view's own status (removal/update failure hidden) | L3 P4 | CONFIRMED | Important | in (UI-SPEC "a re-render never clears…") | `installer/wizard_app.py:2932-2946, 2965-2973` |
| C-07 | Widget queries on the shutdown path (same root cause as bc6b9ef/765c0e5) | L1 WR-05 | CONFIRMED (latent) | Minor | in (hardening of the D-06 render path) | `installer/wizard_app.py:3020-3031, 2166-2201, 505-509, 908-928, 952-958, 565-566` |
| C-08 | A pass that publishes under a modal is not rendered when the modal closes | L3 P3 | CONFIRMED | Important | in; **fix conflicts with D-06 as written and tested** | `installer/wizard_app.py:2958-2963, 3099-3106`; `tests/test_screen_family.py:441-467` |
| C-09 | Doctor smoke evidence never expires: a repaired tool stays BROKEN | L2 R2-1, L3 P2 | CONFIRMED | Important | in (D-13) | `installer/version_status.py:1187-1228, 1794-1805` |
| C-10 | Doctor prints every `ToolState.reasons` entry, healthy owner notes included, as yellow findings | L1 IN-02, L3 P1 | CONFIRMED | Important | in (UI-SPEC Doctor) | `installer/wizard_app.py:620-627`; `installer/version_status.py:250-265, 836-848` |
| C-11 | Doctor `enter` wires the PATH after its preview read failed | L1 WR-04 | CONFIRMED | Important | in (T-21-41) | `installer/wizard_app.py:572, 702-708` |
| C-12 | Unreachable "Run `make setup`" rewrite left in Doctor | L2 R2-12 | CONFIRMED | Minor | in (D-16) | `installer/wizard_app.py:683-689`; `installer/guidance.py:325-330, 358-362` |
| C-13 | `_audit_globals_worker` lacks `exit_on_error=False` and a `finally` post | L1 IN-05 | CONFIRMED | Minor | pre-existing (more load-bearing now) | `installer/wizard_app.py:877-902` |
| C-14 | A removal reports a tool `removed` while a previewed path stays; refusals shown twice with tweaks, never without | L1 WR-02, L3 P6 | CONFIRMED | Important | in (21-14) | `installer/app.py:692-716, 739-744, 761`; `installer/wizard_app.py:1534`; `installer/uninstall.py:318-326` |
| C-15 | An `OSError` in `plan_removal` aborts the whole removal batch and its levers | L2 R2-6 | CONFIRMED | Minor | in (21-14 contract) | `installer/app.py:694` |
| C-16 | A removed tool stays staged on the catalog tiers | L2 R2-8 | PARTIAL | Minor | in | `installer/wizard_app.py:1589, 2721`; `installer/catalog_tui.py:310` |
| C-17 | Mutating keys open a modal before the lock refuses (Uninstall `enter`, Policies `t`/`m`) | L2 R2-9 | CONFIRMED | Minor | in (UI-SPEC removal-flow row) | `installer/wizard_app.py:1435-1446, 2311, 2355` |
| C-18 | The first-run link pick bypasses the lock while the daemon apply writes `~/.myshellrc` | L1 WR-01 | CONFIRMED | Important | in (D-08 one lock); race pre-existing | `installer/wizard_app.py:3108-3160, 2855-2856`; `installer/daemon.py:382-394`; `setup.py:120` |
| C-19 | An unreadable Linux daemon state (`UNAVAILABLE`) reads `! [drift]` | L2 R2-3 | CONFIRMED | Important | in (21-18 DRIFT, UI-SPEC "live read failed") | `installer/policy.py:1394-1396`; `installer/wizard_app.py:1635-1652`; `installer/systemd_daemon.py:436-453` |
| C-20 | `UnicodeDecodeError` escapes `run_live`, so a non-UTF-8 rc file crashes Policies entry | L2 R2-4 | CONFIRMED | Minor | in (21-17 live reads) | `installer/ui_common.py:52-55`; `installer/tweaks.py:313-318`; `installer/wizard_app.py:1764-1802` |
| C-21 | Policies blanks job rows on every publish; a key press in that window reads as a red read error | L3 P5 | CONFIRMED | Minor | in (21-18) | `installer/wizard_app.py:1775-1778, 1869-1873` |
| C-22 | Overlapping timer-cache probes: an older answer can overwrite a newer one | L2 R2-2 | PARTIAL | Minor | pre-existing (more reachable now) | `installer/systemd_daemon.py:500-519` |
| C-23 | Installed-via says `GitHub release` / `installer artifact` where UI-SPEC says `installer`; a shadowed installer copy reads `Homebrew` | L1 WR-08, ledger | CONFIRMED (wording) / PARTIAL (shadowed) | Important | in (UI-SPEC:107-109); **shadowed-case copy needs the user** | `installer/version_status.py:1904-1912`; `installer/ownership.py:1310-1322, 1655-1657` |
| C-24 | A failed update never invalidates, so the follow-up pass reuses pre-update manager data | L2 R2-5 | CONFIRMED | Minor | in (phase goal); root pre-existing | `installer/update.py:581`; `installer/wizard_app.py:3315-3317` |
| C-25 | Quitting during a non-removal mutation drops its outcome; exit code 0 | L1 WR-06 | CONFIRMED | Minor | pre-existing; **extending D-10 needs the user** | `installer/wizard_app.py:3341-3345`; `setup.py:1185-1189` |
| C-26 | During a removal no key exits a wedged remover | L1 WR-07 | CONFIRMED | Minor | in; **fix conflicts with D-10 / UI-SPEC quit row** | `installer/wizard_app.py:2680-2684, 3337-3365` |
| C-27 | Missing/unavailable rows hide `removable.yourself` leftovers; "Nothing to uninstall." still claimed | L2 R2-7 | CONFIRMED | Minor | in; **fix changes UI-SPEC copy** | `installer/version_status.py:1923-1927, 1944`; `installer/wizard_app.py:1388-1396` |
| C-28 | Completion handlers write status on hidden views; it greets the next entry | L1 IN-06 | CONFIRMED | Minor | in; **UI-SPEC "Re-entering: empty" decision** | `installer/catalog_tui.py:707-737`; `installer/wizard_app.py:1564-1612` |
| C-29 | `_managers_invalid` bypasses the manager backoff while cache saves fail | L1 IN-01 | CONFIRMED | Minor | in (21-20) | `installer/version_status.py:1588, 1872-1885` |
| C-30 | `begin_mutation` silently overwrites a held lock | L1 IN-07 | CONFIRMED (latent) | Minor | in | `installer/wizard_app.py:2657-2661` |
| C-31 | The catalog's "update already in flight" branch is unreachable | L3 P8 | CONFIRMED | Minor | in | `installer/catalog_tui.py:676-680` |
| C-32 | "Retract only my own status line" is hand-rolled four times | L3 P7 | CONFIRMED (quality) | Minor | in | `installer/wizard_app.py:657, 1405, 1789, 2944` |
| C-33 | Stale comments after the rewrite | L1 IN-04 | CONFIRMED | Minor | in | `installer/wizard_app.py:127-132, 2680-2682, 3337-3338, 3175-3177` |
| C-34 | `remove_failed` with an empty detail falls back to install wording | L1 IN-03 | CONFIRMED (unreachable) | Minor | in | `installer/render.py:149-160` |

### Per-finding detail

**C-01: macOS 15-minute hang (High; L1 WR-10)**

Evidence:
- `HeldRefreshService.refresh` calls `self.release.wait()` with no timeout (`tests/state_doubles.py:327`). Its siblings `HeldRemover` and `_held_reinstall` bound theirs at 10 s.
- Textual thread workers run on the default executor (`textual/worker.py:326` `run_in_executor(None, …)`).
- Python 3.12.12 `asyncio.constants.THREAD_JOIN_TIMEOUT == 300` (checked in `.venv`). pytest-asyncio 1.4.0 closes each loop through `asyncio.Runner`, so a worker thread still blocked at teardown stalls that test for 300 s.
- macOS runs one xdist worker (`tests/conftest.py:120`, `round(3*0.4)`). One such stall turns a ~9-10 min job into more than 15 min (`ci.yml:17`).
- No `pytest-timeout` or `faulthandler_timeout` is configured (`pyproject.toml:48-50`).

Correction to L1's count (hence PARTIAL on the count): three tests can leave the double unreleased, not six.
- The three: `test_launch_pass_renders_the_visible_tier` (`test_screen_family.py:279`, an assert before `release.set()`), `test_two_requests_during_a_pass_coalesce_into_one` (`:422`, `wait_until` and an assert before the release), and `test_a_late_settle_never_repaints_a_finished_run` (`test_execute_screen.py:4167`, `_settle_execute` and an assert before the release).
- Not candidates: `:293` releases before the app starts, and `test_execute_screen.py:4140/4190` release right after a non-asserting wait. The `Event` stays set, so later calls do not block.

The causal link to the CI timeouts is the most plausible one, not a proven one: cancelled jobs leave no logs.

Fix (tests and config only):
1. Bound the double: `if not self.release.wait(timeout=10): raise TimeoutError("HeldRefreshService was never released")`.
2. Wrap the three tests in `try/finally: service.release.set()`.
3. Add pytest's built-in `faulthandler_timeout = 120` under `[tool.pytest.ini_options]`. It needs no new dependency and dumps every thread's stack on a stall.
4. Give the `Test` step its own `timeout-minutes` below the job's 15, so the step fails with its log kept instead of the job being cancelled. Confirm this keeps the log on one run.

RED: a unit test that calls `HeldRefreshService(…).refresh([])` on a thread with `release` never set, after shortening the bound through a constructor argument, and asserts that `TimeoutError` is raised and the thread joins within 2 s. It hangs today.

**C-02: WR-09 latch (Minor; L1)**

Measured at 5.16 s. The latched launch pass keeps `full-catalog-refresh` running, so `settle` returns only after `assert release.wait(timeout=5)` fails inside the worker. The `release.set()` at `:6934` is dead, and the stale-pass path the test names is no longer exercised.

Fix: `release.set()` before `settle`, then assert that the stale pass publishes nothing.

Proof: the test runs in under 1 s under `--durations` and still asserts `14.1.1`. Add a spy that counts publications from the raced pass and expects 0.

**C-03: setup tests' 5 s wait (Minor; L1; pre-existing)**

`_capture_app`'s stand-in never runs the armed collector's worker, so each of 23 tests waits `DAEMON_DEFAULT_WAIT_SECONDS`. Measured at 5.00 s each, about 115 s serial on macOS.

Fix: have the stand-in call `daemon_default_warnings.finish()`, or monkeypatch the wait to 0.01 as `tests/test_setup.py:2831` already does.

Proof: `--durations=30` lists none of them at 5 s. It is not a defect, but it buys back two minutes of the macOS budget.

**C-04: silent pass failure (Important; L1 WR-03 + L2 R2-11)**

`_refresh_worker`'s `except Exception` sets only `pass_error` (`:2926-2927`). No `RefreshPublished` is posted, and `on_refresh_finished` (`:2948-2956`) hands the error to waiters only. A `ValueError`/`KeyError`, or an invalid-UTF-8 version cache, leaves every view at `…` with an empty status. That silently skips the T-21-11 retry copy.

Fix: in the `except` branch, `self.post_message(RefreshPublished(pass_error, None))` before `finally`. It reuses the one status path and keeps waiter delivery.

RED: a `HeldRefreshService(raising=RuntimeError("boom\nmore"))` with no waiter. Assert the visible tier's status reads `tool state check failed: boom — the next change retries it`. The existing `test_await_publication_reports_an_escaping_exception` checks only the waiter.

**C-05: pending pass after shutdown (Important; L2 R2-10)**

`on_refresh_finished` restarts `_refresh_pending` with no running or quitting check. L2 reproduced it under `run_test` teardown, where the successor started with `is_running=False`. In production, a quit while a pass is queued starts a full manager query on the executor, and the process cannot exit until it ends. It also adds a teardown thread in tests (see C-01).

Fix: in `on_refresh_finished`, run a pending pass only when `self.is_running and not self.quitting`. Otherwise drop it and still serve the waiters.

RED: a pilot with a held pass plus `request_refresh()` (pending), then `app.exit()`, release the hold, and assert `len(service.calls) == 1` after teardown.

**C-06: state line overwrites a view's status (Important; L3 P4)**

`_write_state_line` (`:2965-2973`) calls `status.set` unconditionally on every publish, two per pass. `service.warning` stays set until a save succeeds. On a machine where the cache cannot be saved, "1 remove failed. Fix the cause…" (error) becomes "version cache not saved: … — marks are current" (warn) a moment later. This breaks UI-SPEC "A re-render never clears a status written after the mutation that caused it".

Fix: write only over an empty line or the app's own previous `_state_line` text. Otherwise queue the line to `_pending_warnings`, so it shows on the next entry. C-32's `StatusLine.retract` can land with it.

RED: a service whose `warning` is set. Run a failing removal (`HeldRemover` with a refusal), settle, and assert the status still reads the removal summary with severity `error`.

**C-07: shutdown widget queries (Minor; L1 WR-05)**

Unguarded `query_one` reachable after the app stops running:
- `on_daemon_default_applied` → `refresh_daemon_state` (`:2195-2201`, guarded by `is_mounted` only).
- `on_globals_audited` (`:908-928`) and `on_globals_reinstalled` (`:952-958`), both with no guard.
- `on_disk_pressure_probed` (`:505-509`, `is_mounted` only). All three Doctor handlers reach `_refresh_body` → `query_one("#doctor-body")` at `:566`.

The guard 765c0e5 established is `self.app.is_running`. `on_removal_finished` and `on_job_states_read` already use it. No failure has been observed yet.

Fix: add `if not self.app.is_running: return` (after releasing the lock) to those handlers. The cheapest form puts it at the top of `DoctorScreen._refresh_body` and `PoliciesScreen.refresh_daemon_state`.

RED: the 765c0e5 pattern. Post `GlobalsReinstalled` / `DaemonDefaultApplied` after `app.exit()` inside `run_test` and assert that no `NoMatches` is raised.

**C-08: publish under a modal is never rendered (Important; L3 P3; needs the user)**

`_render_published` skips a view covered by a modal. Closing a modal is not an `enter_view`, and only `_first_link_mode_picked` and `_install_closed` re-render by hand (`:3110, :3213`). So after a launch pass that lands under the ctrl+p palette (or a cancelled `ConfirmUninstall`, or a Policies picker), the view keeps `…` until another pass.

**Conflict:** D-06 says "Hidden views render the published state on their next `enter_view`". `test_publish_under_a_modal_waits_for_the_next_entry` (`tests/test_screen_family.py:441-467`) pins exactly this: still `…` after `pop_screen`.

L3's fix is one `AppScreen.on_screen_resume` → `state_refreshed()`, deleting the two bespoke calls. It changes D-06's rule and that test.

User decision: treat a view under a closing modal as visible (amend D-06 and the test), or keep D-06.

**C-09: stale Doctor evidence (Important; L2 R2-1 + L3 P2)**

`_evidence` is written only by `record_evidence` (`version_status.py:1187-1202`). `invalidate` (`:1204-1228`) leaves it, and every pass merges it into `broken` (`:1794-1805`). So Doctor finds `mmdc` broken, the user reinstalls it from the tier ("reinstalled"), and the next pass still marks it BROKEN until Doctor is re-entered.

This is not a conflict: UI-SPEC already allows "the last evidence (or none)".

Fix:
- `self._evidence.clear()` inside `invalidate` under the lock.
- `record_evidence` takes the epoch the audit started at and drops the result when the epoch has moved, so an audit worker that started before the mutation cannot restore stale evidence. This is the second half of L2's fix.
- `test_evidence_is_read_under_the_lock_as_a_snapshot` (`tests/test_version_status.py:5825`) currently asserts that evidence survives `invalidate`. It must force its second pass without `invalidate`.

RED: record evidence, then `invalidate`, then run a pass, and assert that the tool's `broken` no longer carries `PNPM_SMOKE_FAILED`.

**C-10: Doctor prints every reason (Important; L1 IN-02 + L3 P1)**

The loop at `:625-627` prints all of `state.reasons` for every node entry whose health is not CHECKING or UNAVAILABLE. `tool_health` appends `ev.notes` (`version_status.py:265`), and `ownership_notes` adds `owner_detail` (`:845-848`). So a healthy pnpm-owned `mmdc` prints `mmdc: managed by pnpm` in yellow. UI-SPEC wants only the missing, unhealthy and incomplete shim findings.

Fix: print only reasons built from the shared pnpm templates (`PNPM_SMOKE_FAILED`, `PNPM_SPLIT_GROUP`, `PNPM_TRACKED_OFF_PATH` and the pass's shim sentences), by matching their prefixes or by exposing a `pnpm_findings(state)` helper next to the templates.

RED: a `pass_state(mmdc, ownership=pnpm)` with `Health.OK`. Assert that the Doctor body has no `mmdc:` line.

**C-11: Doctor `enter` after a failed preview (Important; L1 WR-04)**

`_refresh_body` records `_preview_error` (`:572`). `action_apply` (`:702-708`) never reads it and runs `self._fix()`, which edits rc files the user was not shown. That is the T-21-41 threat.

Fix: after the lock check, `if self._preview_error is not None: self._sync_read_status(); self.post_message(RefreshRequested()); return`. Refusing on `_guard_error` too is optional, because the guard is independent of the PATH fix.

RED: a `fix_preview` that raises `OSError` and a spy `fix`. Press `enter`, then assert the spy was never called and the status reads `Could not read the doctor state: …`.

**C-12: dead pnpm rewrite (Minor; L2 R2-12)**

`self.guidance` is now `doctor_guidance + guard_guidance + disk + competing` (`:533-538`). Only `node_globals_guidance` emits `_REINSTALL_NEXT_STEP` (`guidance.py:296-298`), and only the console renderer uses it (`render.py:462`).

Fix: delete the `elif` at `:683-689` and the "load-bearing prefix" comments at `guidance.py:325-330, 358-362` that describe the TUI rewrite. Keep the PATH and disk-pressure branches.

Proof: the existing `_tui_guidance` tests stay green. Grep that no `Run \`make setup\`` item reaches `DoctorScreen.guidance`.

**C-13: audit worker crash safety (Minor; L1 IN-05; pre-existing)**

`@work(thread=True, exclusive=True, group="globals-audit")` has no `exit_on_error=False`, and its post is not in a `finally`. An exception that `run_live` does not map kills the app.

Fix: `exit_on_error=False`, and post `GlobalsAudited(_GLOBALS_UNREADABLE, _GLOBALS_UNREADABLE_PREVIEW, error, generation)` from `finally`.

RED: a `_node_globals` that raises `ValueError`. Assert the app is still running and `globals_auditing` is False.

**C-14: removal outcome truth (Important; L1 WR-02 + L3 P6)**

How it happens:
- `mine` keeps only the previewed paths that the tool's current plan still names (`app.py:695-697`).
- A dropped path goes only into `refused` as "unclaimed" (`:711-715`). The tool still lands in `removed` (`:707-710`).
- `remove_proven` then deletes the receipt, because every path in the fresh plan is gone (`uninstall.py:323-325`).

Rendering side:
- `swept.warnings` is shown only inside `if decision.remove_tweaks:` (`wizard_app.py:1534`), so a tool-only removal hides the refusal.
- When tweaks are selected, each `tool_refused` path is shown twice: once as `remove failed — …` and once as `warning: …` (`app.py:706` plus `:742`).

Fix (one mechanism):
- In `perform_uninstall`, attribute each unclaimed previewed path back to its tool by the entry it came from. That needs `decision` to carry the paths per tool: build `{tool_id: paths}` in `_apply_removal` from `entry.paths`. A tool with any unclaimed or refused path goes to `remove_failed`.
- Drop `refused += tool_refused`.
- Move the `warnings` line out of the tweaks branch in `_applied_summary`.

RED: two cases.
- A pilot where tool A's preview names p1 and p2 and the receipt is rewritten before confirming so that p1 is no longer named. Assert `swept.remove_failed` names A and `removed` does not.
- A tool-only removal whose path is refused. Assert the refusal text is on the status exactly once.

**C-15: planning error aborts the batch (Minor; L2 R2-6)**

`plan_removal([tool], bin_dir)` runs outside the per-tool `try` (`app.py:694`). `Path.exists` raises `PermissionError` for a non-searchable parent. `run_live` maps that to `swept=None`, so the rest of the tools and every lever are skipped, tools already deleted are not reported as removed, and the status says "Uninstall failed". The docstring promises "one … failed delete (`OSError`) never stops the next tool or the environment levers".

Fix: move `plan_removal` and the `mine` attribution inside the `try`.

RED: monkeypatch `plan_removal` to raise `PermissionError` for the first of two tools, with the ban lever selected. Assert the second tool is in `removed`, the first is in `remove_failed`, and `remove_ban_aliases` ran.

**C-16: removed tool stays staged (Minor; L2 R2-8; PARTIAL)**

`on_removal_finished` prunes only Uninstall's own selection (`:1589`). The tiers share `UnifiedApp._staged` (`:2721`), and their predicate (`catalog_tui.py:310`) keeps a MISSING tool selectable, so D-15's prune never fires.

UI-SPEC says "Selected ids that are no longer selectable (removed, or made unavailable) are dropped silently". "removed" there is ambiguous between "uninstalled" and "row gone", hence PARTIAL. The impact is low: the next Enter shows an install plan that has to be confirmed.

Fix: `self.app.unstage(swept.removed)`, a one-line public method doing `self._staged -= ids`.

RED: stage `fd`, remove it, settle, and assert `app.catalog.selected` lacks `fd`.

**C-17: modal before the lock refusal (Minor; L2 R2-9)**

Uninstall `enter` (`:1443`), Policies `t` (`:2311`) and `m` (`:2355`) push their modal while the lock is held and refuse only in the callback. UI-SPEC's row says the key is "Refused; nothing starts; status warn on the screen that received the key".

Fix: `if self.app.refuse_if_mutating(self): return` before each `push_screen`. Keep the callback checks, because the modal can outlive a newly started mutation.

RED: hold the lock (`app.begin_mutation(MutationHolder.UPDATE)`), press the key once, and assert `app.screen` is the view (no modal) and the status is the lock template.

**C-18: first-run link pick bypasses the lock (Important; L1 WR-01)**

How it happens:
- `on_mount` starts the daemon-default worker while the lock is held as `DAEMON_DEFAULT` (`:2855-2856, :2877-2878`), then pushes `LinkModeScreen`.
- `_first_link_mode_picked` runs `move_link_mode` with no lock check (`:3140-3149`). It rewrites ban and tweak blocks in `~/.myshellrc`.
- The worker's `record_decided` is a read-modify-write of the same file (`daemon.py:392-394`, `setup.py:120`).

The race existed before (no guard at `390f464` either). It now breaks D-08's "one app-level mutation lock … no screen can forget to check it".

Fix, two options:
- Recommended (best over easiest, so the user does not have to re-answer): store the picked value and run the move from `on_daemon_default_applied` once the lock is released.
- Minimal: `refuse_if_mutating(target)` before the move.

RED: a held daemon-default callback (an `Event`), a pick, and a spy `move_link_mode`. Assert no move happens while the lock is held. With the deferral, also assert it runs once after `DaemonDefaultApplied`.

**C-19: UNAVAILABLE daemon reads as DRIFT (Important; L2 R2-3)**

`linux_daemon_policy._is_active` returns `cache.read() is DaemonState.ACTIVE` (`policy.py:1394-1396`), so `UNAVAILABLE` (unreachable user manager, `systemd_daemon.py:445-453`) becomes `False`. `_owned` is a file check, so the row reads `! [drift]` and offers "space applies it again". UI-SPEC "Policies live read failed" requires a blank cell plus `Could not read the policy state: …`.

Fix: `_is_active` raises `OSError("the systemd user manager could not be reached")` on `UNAVAILABLE`. `run_live` then routes it to the existing failed-read path.

Check callers first. `uninstall.policy_owned` (`uninstall.py:376-377`) reads `owned()` for this policy, never `is_active`. `PoliciesScreen.live_state` (`:2164`) is called in the daemon-default worker; wrap it in `run_live` or catch there, and `live=None` already means "keep the row".

RED: `linux_daemon_policy` with a cache whose probe answers `UNAVAILABLE` and a footprint present. Assert `_read_active_owned` returns `(None, error)` and the cell is empty, not `! [drift]`.

**C-20: `UnicodeDecodeError` escapes `run_live` (Minor; L2 R2-4)**

`run_live` catches `(OSError, CommandError, ShellrcRefusal)` (`ui_common.py:54`). `tweak_present` → `rc_path.read_text()` (`tweaks.py:318`) raises `UnicodeDecodeError`, a `ValueError`. `PoliciesScreen.state_refreshed` runs on the event loop, so the exception kills the app. Before Phase 21 this read happened once at startup; 21-17 made it reachable mid-session.

Fix: add `UnicodeDecodeError` to `run_live`'s tuple (one line, a typed data error, not a blanket except). It also covers the version-cache case L2 found under C-04.

RED: a managed rc file rewritten with `b"\xff"` after mount. Re-enter Policies and assert the app is running, the row is blank, and the status starts `Could not read the policy state:`.

**C-21: job rows blank on every publish (Minor; L3 P5)**

`state_refreshed` drops every `state_cache` row on every publish (`:1775-1778`), two per pass. Pressing `space`/`t` before the worker answers hits `_refuse_unreadable`, which writes "Could not read the policy state: not read yet." in red and asks for another pass, which blanks the row again.

Fix (no conflict): in `_refuse_unreadable`, when `_read_error is None` (a read is pending, not failed), write a `warn` "Still reading the policy state; try again in a moment." and request no pass.

L3's alternative, keeping the last answer on publish, would touch 21-18's "blank, not stale" choice, so it is not recommended.

RED: a slow `state_cache` probe. Press `space` before it answers and assert severity `warn` with no extra pass.

**C-22: timer-cache probe ordering (Minor; L2 R2-2; PARTIAL; pre-existing)**

`_ProbeCache.read` stores any answer whose generation did not move (`systemd_daemon.py:514-519`). Two overlapping reads with no `invalidate` between them can store the older answer last. The mechanism is real, but poisoning needs an external state change inside the overlap, and `STATE_CACHE_TTL = 5.0` bounds it.

Fix (backlog): a start-sequence number, so only the newest-started probe stores its answer.

RED: two reads with latched probes, finished in reverse order. Assert `peek()` returns the newer answer.

**C-23: Installed-via wording (Important; L1 WR-08 + ledger)**

`uninstall_label` returns `removal_label(...) or owner_label(...)`. For an installer-owned record that is the kind label (`GitHub release`, `tarball download`, …) or `installer artifact` (`ownership.py:1310-1322`). UI-SPEC:107-109 says `installer`.

Second half (PARTIAL): `uninstall_group` is `REMOVABLE` whenever `removable.removable` is non-empty, whoever the owner is. A shadowed installer copy under an active brew binary therefore reads `Homebrew` on a destructive screen.

Fix (no conflict): `if state.ownership.owner == "installer" and group is UninstallState.REMOVABLE: return "installer"`.

**Needs the user:** what a REMOVABLE row shows when the proven owner is another manager. UI-SPEC's receipt row allows "the proven manager". For the shadowed case, L1 proposes `installer` plus "— active copy: Homebrew" in the detail line, which is new copy.

RED: a removable installer-owned state with `method.kind == "github_release"`. Assert `uninstall_label(state) == "installer"`.

**C-24: failed update keeps stale manager data (Minor; L2 R2-5)**

`UpdateService` invalidates only when `status == "updated"` (`update.py:581`; unchanged in this range). `on_tool_updated` asks for a pass "because a failed update may still have changed the machine" (`wizard_app.py:3316`), but that pass reuses the persisted manager snapshot. L2 reproduced 1.0 → 2.0 then a failure, and the pass published 1.0.

Fix: invalidate whenever the runner was invoked (`updated` or `failed`). Keep invalidation errors in `detail`.

RED: a fake brew runner that bumps the inventory, then raises. Assert the follow-up pass publishes 2.0.

**C-25: quit during other mutations (Minor; L1 WR-06; pre-existing; needs the user)**

`_quit` waits only for `REMOVAL` (`:3341-3345`). An `UPDATE` or `GLOBALS_REINSTALL` keeps running invisibly while asyncio joins its thread, its completion is never handled, and `setup.py` prints `Aborted.` with exit code 0 (`:1185-1189`). `390f464` exited immediately for every mutation.

Generalizing the quit-wait extends D-10 beyond removals and adds copy (`Waiting for {holder} to finish…`), so it needs the user. Backlog otherwise.

**C-26: no exit from a wedged removal (Minor; L1 WR-07; needs the user)**

`q` and `ctrl+c` both wait (`:3341-3345`). The sweep's `launchctl`/`systemctl` teardown has no timeout. The bindings comment (`:2680-2682`) and the `action_hard_abort` comment (`:3337-3338`) still say ctrl+c "always exits".

L1's fix, a second ctrl+c that forces the exit, **contradicts D-10 and the UI-SPEC quit row** ("waits for the worker"; refusing or cutting a quit was rejected). The comment fix (C-33) needs no decision.

**C-27: orphan leftovers hidden on missing rows (Minor; L2 R2-7; needs the user)**

`uninstall_detail` returns for ABSENT and UNAVAILABLE (`version_status.py:1923-1927`) before the `removable.yourself` suffix (`:1944`), and `_nothing_to_uninstall` can still claim "Nothing to uninstall.". The fix adds text to a row that UI-SPEC fixes at `not installed`, and changes the empty-state rule, so it needs the user.

RED, if approved: an orphaned opt directory with the tool missing. Assert the detail carries `remove it yourself: …` and the status is not `Nothing to uninstall.`.

**C-28: late results on hidden views (Minor; L1 IN-06; needs the user)**

When the user leaves during an update, a removal or a toggle, the completion writes to the hidden view's status after `clear_transient`, and the next entry shows it. UI-SPEC says "Re-entering: empty, except a standing status".

The user's choice:
- Route late results through `_pending_warnings` to the visible view.
- Or document the case in the UI-SPEC lifecycle table.

**C-29: backoff bypass while saves fail (Minor; L1 IN-01)**

`_managers_invalid` clears only in a successful `save_pass` (`:1884`). While writes fail, every pass re-queries the managers.

Fix (backlog-able): keep the queried snapshot in memory and reuse it while the flag is set.

RED: a cache directory that cannot be saved. Two passes; assert one `read_outdated` call.

**C-30: `begin_mutation` overwrite (Minor; L1 IN-07)**

`begin_mutation` overwrites any holder (`:2657-2658`), so the first `end_mutation` would release both. No path triggers it today.

Fix: `assert self._mutation_holder is None, self._mutation_holder`.

RED: call `begin_mutation` twice on a `MutationLock()` and expect `AssertionError`.

**C-31: dead in-flight branch (Minor; L3 P8)**

`UpdateService.begin` (`catalog_tui.py:676-680`) can fail only while another update or an install run holds the lock, and `refuse_if_mutating` runs first. The install run's `begin` (`session.py:550`) runs under a modal.

Fix: delete the copy branch and keep `begin()` as a bare guard. Existing tests stay green.

**C-32: four hand-rolled retracts (Minor; L3 P7)**

The same "clear only if it still holds my text" logic is written at four sites.

Fix: `StatusLine.retract(text)` in `ui_common.py`, done with C-06. Quality only.

**C-33: stale comments (Minor; L1 IN-04)**

The stale comments are at `wizard_app.py:127-132`, `:2680-2682`, `:3337-3338` and `:3175-3177`. Update the wording; no test is needed.

**C-34: install-word fallback for `remove_failed` (Minor; L1 IN-03)**

The fallback is unreachable today. Optional fix: a `not removed` fallback for `remove_failed`, with a one-line test of `outcome_detail_text`.

### Decisions needed from the user (do not fix before an answer)

| id | Locked rule the fix would change | Question |
|----|----------------------------------|----------|
| C-08 | D-06 ("hidden views render on their next `enter_view`"), `test_publish_under_a_modal_waits_for_the_next_entry` | Should a view under a closing modal re-render (`on_screen_resume` → `state_refreshed`)? The recommendation is yes: it removes two bespoke re-renders and the stale `…`. |
| C-23 (second half) | UI-SPEC:107 "the owner label (`installer`, or the proven manager)" | For a REMOVABLE row whose active copy belongs to another manager: should it show `installer` plus "— active copy: {manager}" in the detail? |
| C-25 | D-10 covers removals only | Should the quit-wait cover every lock holder, with the copy `Waiting for {holder} to finish…`? Pre-existing, so the backlog is fine. |
| C-26 | D-10 and the UI-SPEC quit row ("waits") | Should a second ctrl+c during a removal force the exit, with a warning that it may be incomplete? |
| C-27 | UI-SPEC Uninstall row copy (`not installed`) and the empty state | Should missing rows show their `remove it yourself:` leftovers and suppress `Nothing to uninstall.`? |
| C-28 | UI-SPEC status lifecycle ("Re-entering: empty") | Route late completion results to the visible view, or document the hidden-view write? |

### Fix batches (test first; run them in this order, one fixer at a time)

Batches B to E all edit `installer/wizard_app.py`, in different classes. Run them in sequence, not in parallel worktrees.

**Batch A: the macOS hang (tests and CI config only; first)**
- C-01, C-02, C-03.
- Files: `tests/state_doubles.py`, `tests/test_screen_family.py`, `tests/test_execute_screen.py`, `tests/test_wizard_app.py`, `tests/test_setup.py`, `pyproject.toml` (`faulthandler_timeout`), `.github/workflows/ci.yml` (step timeout).
- Done when: the double's RED test turns green, and `--durations` shows no 5 s tests in `test_setup.py` and none in the epoch-guard test.
- Then push and watch at least two macOS runs.

**Batch B: refresh owner and status line (`UnifiedApp` in `wizard_app.py` around `:2890-2975, :3020-3031`; `ui_common.run_live`)**
- C-04, C-05, C-06 (with C-32), C-07, C-20.
- One RED test per item, in `tests/test_screen_family.py` (and `tests/test_wizard_app.py` for C-20).

**Batch C: Doctor and evidence (`DoctorScreen` in `wizard_app.py` `:440-970`; `VersionRefreshService.invalidate` / `record_evidence`; `guidance.py` comments)**
- C-09, C-10, C-11, C-12, C-13.
- C-29 is optional here, since it is the same file as C-09.

**Batch D: removal (`installer/app.py` `perform_uninstall`; `UninstallScreen` in `wizard_app.py` `:1435-1612`)**
- C-14, C-15, C-16, plus the Uninstall-`enter` half of C-17.

**Batch E: Policies and the lock (`PoliciesScreen` in `wizard_app.py` `:1635-2400`; `_first_link_mode_picked` / `on_daemon_default_applied`; `policy.linux_daemon_policy._is_active`)**
- C-18, C-19, C-21, plus the Policies `t`/`m` half of C-17.
- C-30's assert lands here too, as part of the lock.

**Batch F: labels, update freshness, cleanup (`version_status.uninstall_label`; `installer/update.py`; `catalog_tui.py`; comments)**
- C-23 (installer-owned half only), C-24, C-31, C-33, C-34.

**Not in a batch:**
- Waiting on the user: C-08, the second half of C-23, C-25, C-26, C-27, C-28.
- Backlog, pre-existing mechanism: C-22.


## Re-review of the fix loop (182e876..HEAD)

**Reviewed:** 2026-11-03, depth standard, by gsd-code-reviewer. The scope is 62 commits (batches A to F) and the 10 source files they touched: `installer/{app,catalog_tui,guidance,policy,render,ui_common,update,version_status,wizard_app}.py` and `pyproject.toml`/CI. The tests and the amended CONTEXT D-06/D-10, UI-SPEC and `.claude/architecture.md` were read against that source.

**Method:** each fix was read against its C-id in the table above and in `21-REVIEW-FIX.md`. Textual 8.2.7 internals were checked where ordering matters (`Screen.dismiss`, `App.pop_screen`, `_replace_screen`, `MessagePump.post_message`, MRO handler dispatch, `App.BINDINGS`). Two findings were proved with throwaway pilots kept outside the repo, built from the existing test helpers (`_removal_app`, `_hold_a_removal`, `frozen_service`, `_family_app`). No source or test file was changed.

### Verdict per fix

- **Fix resolves the finding and no locked rule regresses:** C-01..C-05, C-07, C-09..C-13, C-15..C-17, C-20, C-21, C-23, C-24, C-28, C-30..C-34. Notes:
  - **C-09:** the epoch is captured on the loop at audit start, and `record_evidence` compares it under the service lock.
  - **C-30:** every `begin_mutation` site still refuses first, or sits behind a modal.
  - **C-23:** a REMOVABLE row requires installer proof, so `installer` is never a guess.
- **Fix works but introduced a defect:** C-26 (RR-01), C-06 (RR-02), C-19 with C-08 (RR-03), C-08 (RR-04), C-14 (RR-05), C-18 (RR-06).
- **Locked rules:**
  - "Nothing removed without proof": C-14 is stricter now.
  - "Unknown owner never attributed": holds.
  - "One app mutation lock": C-18 defers the pick instead of bypassing the lock, and C-30 makes a double take raise.
  - "Single refresh owner": the C-04 extra publish comes from the same worker.
  - "Handlers sync": `_remove_worker` and `_exit_when_done` are workers, not handlers.
  - "Render only through `_visible_app_screen`": `AppScreen.on_screen_resume` is a second render entry. The C-08 user decision approved it, and its guard (`is_running and app.screen is self`) is equivalent. Not counted.
- **Checked, no finding:**
  - **C-26, normal quit:** `q` and the first `ctrl+c` await the worker. The worker resolves only after the thread's `finally` has posted `RemovalFinished`, so the delete and the invalidate are complete.
  - **C-26, half-written files:** receipts (`receipts.py:149`) and rc edits (`shellrc.py`) go through `atomic_write_text`, so even the forced exit cannot leave a half-written receipt or rc file. It can leave a partly deleted artifact tree, which the warning covers.
  - **C-26, `clean_rc_duplicates` after a forced exit:** it re-reads the bytes before writing (`app.py:426-433`), so the race window with the abandoned thread is negligible.
  - **C-08, confirm callback order:** `Screen.dismiss` queues the callback through `requester.call_next` before `pop_screen` posts `ScreenResume`. Both land in the Uninstall screen's own queue, so `_apply_removal` reads `_by_key` as the user saw it in the modal, before the resume repaint.
  - **C-18, lost or duplicated writes:** the deferred move runs synchronously right after `end_mutation`, and keys were refused until then. No write is lost or doubled. A pick is lost only on quit, which is a documented limit.
  - **C-21:** blanking happens only in `enter_view`.
- **Tests:**
  - Every behavioral fix has a RED commit, and the assertions test outcomes, not durations.
  - The bounded waits (`release_timeout`, `wait(timeout=…)`) are fail-fast guards, never the pass condition.
  - No new suppression: the diff only removes one `# type: ignore[method-assign]`.
  - `faulthandler_timeout` dumps stacks and does not change any verdict.
  - Gap: no test presses `ctrl+q` during a removal (RR-01).

### High

#### RR-01: `ctrl+q` during a removal exits at once and abandons the delete thread with no warning (C-26 regression)

**File:** `installer/wizard_app.py:1577` (`daemon=True`), `:2751-2757` (BINDINGS), `:3456-3469`; Textual `app.py:455-462` (`Binding("ctrl+q", "quit", priority=True)` → `action_quit` → `self.exit()`).

**Evidence:**
- `UnifiedApp` does not override the `ctrl+q` binding it inherits from `App`. `UnifiedApp._merge_bindings()` lists `('ctrl+q', ['quit'])` next to `hard_abort`.
- `action_quit` skips `_quit` and `_exit_after_removal`.
- Before a0940de, the delete ran on a Textual thread worker, that is the asyncio default executor, which is joined at interpreter exit. So `ctrl+q` closed the UI and the delete still finished. It now runs on a daemon thread, so interpreter exit stops it mid-delete. There is no "some files may remain" message, and the exit code is 0.
- Proved with a scratch pilot: hold a removal, press `ctrl+q`. The app stops while `remover.release` is unset, and the `uninstall-removal` thread is `daemon=True`.
- This breaks D-10 ("the first `q` or `ctrl+c` still waits") and `.claude/architecture.md` ("A quit during a removal does not kill it").

**Fix (minimal):** route Textual's quit through the same path. Either add `Binding("ctrl+q", "abort", show=False, priority=True)` to `UnifiedApp.BINDINGS` (`hard_abort` if it should allow the forced second press), or override it:
```python
async def action_quit(self) -> None:
    self._quit()
```
Then add one pilot test: `ctrl+q` during a held removal shows `Waiting for the removal to finish…` and the app keeps running.

### Important

#### RR-02: an app state line queued behind another status is never retracted once a show_view flushes it (C-06 regression)

**File:** `installer/wizard_app.py:3062-3083` (`_write_state_line`), `:3178-3182` (`_flush_pending_warnings`), `:3356-3358` (`_install_closed` drain).

**Evidence:**
- C-06 queues the line in `_pending_warnings` and records `_state_line = (None, line)` whenever the visible status is non-empty. That is now the common case: any refusal, result or standing copy on screen.
- `show_view` → `_flush_pending_warnings`, or `_install_closed`, writes the line (joined with ` · `) onto the entered view and empties `_pending_warnings`. `_state_line` still says `(None, line)`.
- On the next clean publish, `_write_state_line(None)` looks for the line only in the now-empty pending list. Nothing is retracted.
- Proved with a scratch pilot: `FrozenStateService.warning` is set, the catalog status is occupied, a pass runs, then `show_view("user")`, then the warning is cleared and a clean pass runs. The user view still reads `version cache not saved: read-only — marks are current; the next start checks again`. The error variant, `tool state check failed: … — the next change retries it`, sticks the same way after the check has succeeded.
- Before the fix, the line was written to the visible view and retracted from there.

**Fix:** when a flush writes the queued state line, re-home it, so the retraction can find it:
```python
def _flush_pending_warnings(self, screen: AppScreen) -> None:
    ...
    pending, self._pending_warnings = self._pending_warnings, []
    text = " · ".join(pending)
    screen.status.set(text, "warn")
    if self._state_line is not None and self._state_line[0] is None and self._state_line[1] in pending:
        self._state_line = (screen, text)
```
Apply the same re-homing in the `_install_closed` drain. Add a RED test following the pilot above.

### Minor

#### RR-03: an unreachable systemd user manager now overwrites every Policies result on the next render (C-19 with C-08)

**File:** `installer/policy.py:1394-1400`; `installer/wizard_app.py:1841-1843`, `:1912-1914`; `installer/ui_common.py:363-371`.

**Evidence:**
- C-19 turns `DaemonState.UNAVAILABLE` into an `OSError`. This happens whenever `systemctl` is present but the user bus is not, for example over SSH with no lingering.
- `on_job_states_read` and `state_refreshed` call `status.set(read_error, "error")` without checking for another writer's status.
- C-08 now re-renders Policies on every modal close, and every toggle ends with a publish. So `Link mode saved: …` (from `m`), `rescheduled …` (from `t`) and a toggle summary are replaced a moment later by `Could not read the policy state: the systemd user manager could not be reached.`
- Before C-19 this read was shown as a row state with no status. Before C-08 the picker close did not re-render.

**Fix:** write a read error only over an empty status or over this screen's previous `_read_error`, the same rule as `_write_state_line`: `if not self.status.text or self.status.text == previous: self.status.set(...)`.

#### RR-04: the Doctor guard chain renders twice when its last modal closes, doubling the live reads (C-08)

**File:** `installer/wizard_app.py:792-797` (`_finish_guard_chain`); `installer/ui_common.py:363-371`.

**Evidence:**
- `ConfirmGuardFile` is pushed from Doctor, so its callback is queued on Doctor before `ScreenResume`.
- The last callback runs `_finish_guard_chain`, which does a rescan plus `_refresh_guidance` (live `guard_state`) and `_refresh_body` (live `fix_preview`).
- The resume handler then sees `_covered=True` and `app.screen is self`, and runs `state_refreshed`, which does the same two live reads again.
- It is harmless, because both reads see the same disk, but it is exactly the "double live read" the C-08 decision meant to avoid. Before the fix, Doctor rendered here only once.

**Fix:** keep only the rescan and `post_message(RefreshRequested())` in `_finish_guard_chain`, and let the resume render. Alternatively, leave it and note it in the C-08 amendment.

#### RR-05: a whole-tool refusal labels every previewed path "changed", and a grown plan still reports `removed` (C-14)

**File:** `installer/app.py:699-713`; `installer/uninstall.py:323-325`.

**Evidence:**
- When one previewed path drops out of the plan, the refusal lines claim `changed since the preview; not removed: {p}` for every previewed path, including the unchanged ones the tool kept.
- The opposite case: a reinstall between preview and confirm adds a path but keeps the old ones. Every previewed path is removed, so `tool_refused` is empty and the tool lands in `removed` ("1 removed"). Meanwhile `remove_proven` keeps the receipt, because the new path is still on disk, and the next pass shows the tool as REMOVABLE again.
- Nothing is deleted without proof, so the locked rule holds. Only the reported outcome is untrue.

**Fix:**
- Name only `[p for p in previewed if p not in named]` in the refusal lines.
- Treat `set(plan.removable) - set(previewed)` as a refusal too ("installed files changed since the preview"), so the tool goes to `remove_failed` with its receipt kept, the same rule as a dropped path.

#### RR-06: a deferred first-run link pick gives no feedback while it waits (C-18)

**File:** `installer/wizard_app.py:3251-3255`, `:3142-3144`.

**Evidence:**
- While `DAEMON_DEFAULT` holds the lock, a pick is stored silently. The picker closes and the screen shows nothing.
- `m` on Policies is refused with "A daemon apply is running…", which reads as if the pick had been rejected.
- If the user quits before the apply ends, the pick is dropped with no message. The ledger records this limit, but the user never sees it.

**Fix:** when deferring, write one line on `target`: `target.status.set(f"Link mode {value} will be saved when the background apply finishes.", "warn")`. The later `_move_first_link_mode` status replaces it.

---

RE_REVIEW: critical=0 high=1 important=1 minor=4
