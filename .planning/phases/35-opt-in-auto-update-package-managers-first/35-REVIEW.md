---
phase: 35-opt-in-auto-update-package-managers-first
reviewed: 2026-11-22T00:00:00Z
depth: deep
files_reviewed: 35
files_reviewed_list:
  - installer/update_all.py
  - installer/update_all_state.py
  - installer/schedule_run.py
  - installer/update.py
  - installer/executors.py
  - installer/compose.py
  - installer/runlock.py
  - installer/cli.py
  - installer/schedules.py
  - installer/schedules_screen.py
  - installer/helper_assets/schedule_runner.py
  - setup.py
  - scripts/container-e2e-verify.sh
  - tests/e2e_update_all_driver.py
  - .claude/architecture.md
  - tests/test_cli.py
  - tests/test_container_e2e_update_all.py
  - tests/test_docs.py
  - tests/test_layout_80x20.py
  - tests/test_schedule_runner.py
  - tests/test_schedules.py
  - tests/test_schedules_view.py
  - tests/test_setup.py
  - tests/test_shell_scripts_path.py
  - tests/test_update_all.py
  - tests/test_update_all_contract.py
  - tests/test_update_all_job.py
  - tests/test_update_all_plan.py
  - tests/test_update_all_row.py
  - tests/test_update_all_rows.py
  - tests/test_update_all_run.py
  - tests/test_update_all_state.py
  - tests/test_update_check_contract.py
  - tests/update_all_child.py
  - tests/update_all_doubles.py
findings:
  critical: 0
  high: 0
  medium: 2
  low: 8
  total: 10
  necessity: 1
status: issues_found
---

# Phase 35: Code Review Report

**Reviewed:** 2026-11-22
**Depth:** deep
**Files Reviewed:** 35
**Status:** issues_found

## Summary

The unattended mutation boundary holds. Every path that reaches a mutation in the update-all route
goes through `UpdateService.run_guarded`: root is refused in both the runner (`schedule_runner.py:551`)
and `run_schedule` (`schedule_run.py:709`); the parent-lock flag is verified by holder line and
kernel probe (`runlock.py:101`); the guard runs on the freshly re-resolved ownership before any
receipt read, pnpm capture or mutation (`update.py:686`); dependents need confirmed evidence
(`schedule_run.py:392`). Managers run without evidence by owner decision D-07, not as a defect.
Plan mode writes nothing: version-cache save, manager-snapshot save, receipt adoption and receipt
retirement all go through `_write_or_queue` / `_pending_writes` (`version_status.py:1356`, `:1520`,
`:1578`), and `context_for`, `read_updated` and `read_capped` are pure reads. The result line is
provably within 300 characters (checked with extreme counts and clauses). The record reader is
strict, FIFO-safe (`read_capped` is non-blocking and `fstat`-checked) and the writers are link-safe.

No CRITICAL or HIGH finding was proven. Two MEDIUM findings concern process lifetime at the signal
boundary and the keyboard reachability of the opt-in disclosure at the 80x20 floor. Both MEDIUM
process-lifetime claims and one LOW claim were reproduced with a harmless `sh`/`sleep` command through
`update_all_runner` (no updater, container, timer or notification was run; the scratch directory was
removed and no `sleep` is left).

## Medium

### ME-01: A second SIGTERM during cleanup aborts the command-group kill, leaving the group alive after the lock is released

**File:** `installer/schedule_run.py:140-160`, `:78-109`
**Issue:** `update_all_runner` installs `interrupted` (raises `SystemExit`) for SIGTERM and SIGHUP and
keeps it installed until the `finally` at line 167. The first signal raises inside `communicate`, the
`except BaseException` branch calls `_end_update_group`, and that function is not shielded: a second
signal that lands during its `child.wait(timeout=KILL_GRACE)` or `time.sleep` raises `SystemExit`
again from inside the cleanup. `suppress` covers only `TimeoutExpired`, `ProcessLookupError` and
`PermissionError`. The second signal is the normal case under systemd: `systemctl --user stop` (and
logout or shutdown) sends SIGTERM to every process in the cgroup at once, so `setup.py` gets one
SIGTERM from systemd and a second from the schedule runner's `_on_signal` -> `_stop` -> `killpg`
(`schedule_runner.py:225`, `:211`) within milliseconds. The phase's stop-budget design (`CLEANUP_BUDGET`,
runner `_UPDATE_ALL_STOP_BUDGET`, the contract test at `test_update_all_contract.py:504`) assumes
the cleanup runs to completion.
**Reproduced:** `update_all_runner(["sh","-c","trap '' TERM; ...; exec sleep 300"])`, SIGTERM at
t=2 s and again at t=3 s: the driver exits 143 and the `sleep` group is still alive 5 s later (SIGKILL
was never sent). The runner then waits only for `setup.py`'s own group (the command group is a separate
session, `start_new_session=True`), SIGKILLs that, exits, and the run lock is released while the
update command keeps running. On Linux systemd the cgroup SIGKILL after `TimeoutStopSec` (90 s) caps the
leak; on macOS launchd the command group is in its own session and nothing else ends it.
**Fix:** make the cleanup non-interruptible. In the `except BaseException` and timeout branches, set
the two handlers to `signal.SIG_IGN` (or a flag-only handler) before calling `_end_update_group`, then
re-raise the original exception; restore in the existing `finally`:
```python
        except BaseException:
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            _end_update_group(child)
            raise
```
Apply the same shielding before `_end_update_group` in the `TimeoutExpired` branch. Add a contract
test that sends two SIGTERMs 1 s apart to a TERM-ignoring command and asserts the group is gone.

### ME-02: The row that needs the most disclosure shows none of it at 80x20, and the detail pane cannot be scrolled by keyboard

**File:** `installer/schedules_screen.py:293`, `:269-271`, `:559-560`; `tests/test_schedules_view.py:954-977`
**Issue:** `update-all` builds seven detail lines: what it does, the preview command, last, times, the
`log:` line, the `limits:` line (casks, failed manager, no update command, daily-record behavior, "vendor
updaters may edit shell files") and `runs:`. The ninth table row shrinks the pane to 4 rows at 80x20 (2
rows with a 3-line status, 1 row with a 4-line status; the tests pin these heights). The pane is a
plain `Static` (`yield Static("", id="schedule-detail")`), which takes no focus, so `overflow-y: auto`
is reachable by mouse wheel only; arrow and page keys act on the focused `DataTable`. The author's
own test confirms the limits and log lines render only at 100x30. A keyboard user at the supported 80x20
floor turns on an unattended-mutation row without ever seeing the limits line, including the
disclosure that vendor updaters may edit shell files.
**Fix:** put the highest-value disclosure first. Either move a shortened `limits:` clause into line 0
(`update all is off — updates managers, then their tools; vendor updaters may edit shell files`), or
make the pane focusable and scrollable (`can_focus = True` with `VerticalScroll`, bound to PageUp/PageDown
or `d`/`u`). Extend `test_the_preview_is_visible_in_the_rendered_widget_at_80x20` to assert the shell-file
warning is in the visible rows, not only in `detail_text`.

## Low

### LO-01: A normal command exit does not end the process group, so same-group descendants outlive the run and the lock

**File:** `installer/schedule_run.py:149`, `:161-166`
**Issue:** The group is ended only on a timeout or an interruption. After `communicate` returns (EOF
on both pipes) and the leader exits 0 or non-zero, any group member that closed its pipes keeps running
after `update_all_runner` returns, after the next tool starts and after the runner releases the lock.
The architecture note scopes the guarantee to "timeout or an interruption", so this is a documented
limit, but "descendants after unlock" is the stated failure to hunt.
**Reproduced:** `sh -c 'sleep 300 >/dev/null 2>&1 </dev/null & exit 0'` returns "ok" and the `sleep`
is alive 1 s later.
**Fix:** after a normal exit, SIGTERM then SIGKILL the group with the same bounded helper, accepting
that a legitimate daemon started by an updater is also ended. Or record the limit in
`architecture.md` as an accepted residual. A flat `killpg(child.pid, SIGTERM)` after `communicate`
returns is the smallest version.

### LO-02: The signal handlers are installed after `Popen`, leaving a window in which a signal kills the parent and orphans the new session

**File:** `installer/schedule_run.py:126-147`
**Issue:** The child is started with `start_new_session=True` at line 126, but the `interrupted`
handlers are installed at lines 145-147. A SIGTERM or SIGHUP in that window takes the default action,
the parent dies, and the new session (the update command) is never signaled.
**Fix:** install the handlers before `Popen` (and restore them in the existing `finally`), or block the
signals with `signal.pthread_sigmask` across the two statements.

### LO-03: The root refusal in the stdlib runner leaves no schedule-log line

**File:** `installer/helper_assets/schedule_runner.py:551-553`
**Issue:** The check runs before `_run_lock` and before any `emit`, and only prints to stderr. Every
other failure path in `_locked_run` ends in `emit(result)`. A user timer enabled by a root user fails
silently each night as far as the Schedules view is concerned (it keeps showing `never`); only the
journal carries the reason.
**Fix:** `emit("failed: update-all refuses to run as root")` through the existing `emit` closure
(it needs no lock) before returning 1.

### LO-04: A dangling `agent` link fails cursor-agent before the guard runs and fails every night

**File:** `installer/schedule_run.py:345-348`, `:578-579`
**Issue:** `_update_cursor_agent` checks `_agent_resolves(agent)` before `_update(..., guard=guard)`.
In an update-all run, a planned cursor-agent whose `~/.local/bin/agent` is missing or dangling returns
`failed: ~/.local/bin/agent is missing or dangling` without consulting the guard (a failed owner
chain, an owner change or a refusal would have turned it into a skip). The tool counts as failed, exits
1 and triggers the nightly notification, because nothing about the condition changes between nights.
**Fix:** run the guard first, or treat the precondition as a skip in the batch route
(`ToolRun("skipped: agent link missing", 0, False)` when `guard is not None`).

### LO-05: The version probe runs before the guard

**File:** `installer/schedule_run.py:265-269`
**Issue:** `_update_tool` calls `deps.probe_version(tool, ownership)` (executes the tool's own binary)
before `run_guarded`. Planning already excludes refused tools, but tools that the guard refuses at run
time (a failed manager, `did not run first`, `owner changed since the evidence`) still have their
binary executed unattended before being skipped.
**Fix:** for the guarded route take the `before` version after the guard passes, or run the probe lazily
from a callback in the guard. Smallest version: have `_BatchGuard` pre-check `blocking_manager` and
`completed` in `_update_tool` before probing.

### LO-06: The plan can promise an update that the real run refuses

**File:** `installer/update_all.py:300-302`, `installer/schedule_run.py:249-253`
**Issue:** `plan_dependents` appends dependents of an owner manager that is not in the present-manager
order (`other_managers`) and plans them as `would update`. The real run's `_BatchGuard` refuses them with
`<manager> did not run first`, because only planned managers are in `completed`. The permanent PLAN_NOTE
covers evidence-window differences but not this order difference, and these tools can never update.
**Fix:** plan those entries as `skip: <manager> did not run first` (or `owner manager not present`),
and add a plan-equals-run fixture with a dependent owned by an absent manager.

### LO-07: A vacuous assertion and a narrow scan in the privilege test

**File:** `tests/test_update_all_contract.py:1001`, `:968-976`
**Issue:** `assert "homebrew_no_sudo" not in forbidden` compares a literal to the 3-element set defined
four lines earlier; it cannot fail. The scan covers four modules and misses the code that actually
spawns update commands (`update.py`, `executors.py`, `run.py`, `setup.py`, `compose.py`). The docstring
already says it proves only these modules; the dead line gives a false impression of an environment
check.
**Fix:** delete the line (the environment is asserted in `test_update_all_job.py:87`/`:104`), and add
`update.py` and `executors.py` to the scanned paths.

### LO-08: `_update_all` is a 160-line function with a 90-line nested closure mutating five nonlocals

**File:** `installer/schedule_run.py:494-656`
**Issue:** `run_entries` carries the manager-skip bookkeeping, guard construction, tool dispatch, count
classification by `startswith`, record write and log write in one closure. The classification by line
prefix (`failed:`, `skipped:`, `ok: up to date`) couples counts to message wording. This is the module the
owner will have to change for the next manager rule.
**Fix:** return structured results from `_update_tool` (`kind: Literal["updated","unchanged","skipped","failed"]`)
and split `run_entries` into `_settle_manager(...)`, `_record(...)` and `_log(...)` helpers.

## Necessity

### NE-01: Impossible-state guards for a missing ownership

**Category:** necessity
**File:** `installer/update_all.py:136`, `:218-223`, `:263`, `:297`, `:320`, `:98`
**Issue:** `ToolState.ownership` is declared `ManagerOwnership` (not optional) at
`installer/version_status.py:1065`; the module casts it to `ManagerOwnership | None` at five sites and
carries `SKIP_NOT_EVALUATED` plus `if state is None: continue` branches. `_decide`'s
`tool.id not in refusals` branch is unreachable in a real run, because `refusals` is built from the same
`states` that feed the planner (`schedule_run.py:606`, `:629`), and `_refusal_evidence` already
dereferences `state.ownership` directly (`:447`, `:450`). The three call sites in `run_entries` also
dereference `states[tool.id].ownership.owner` unguarded. The guards hide a type contract and add three
untestable-in-production branches.
**Fix:** type `states` as `Mapping[str, ToolState]`, drop the casts and the None branches, and keep
`SKIP_NOT_EVALUATED` only if a test needs it.

## Info

### IN-01: Unused constant and shadowed name

**File:** `installer/update_all.py:90`, `:182-183`
**Issue:** `GROUP_INSTALLER` is defined and never used anywhere in `installer`, `tests` or `setup.py`.
`blocking_manager`'s parameter `owner_manager` shadows the module-level function of the same name.
**Fix:** delete `GROUP_INSTALLER`; rename the parameter to `owner`.

---

## Checked and not defective (for the record)

- Managers always run without evidence (D-07), and `skipped` managers pass work on (owner decision).
- Plan mode holds every write (`hold_writes` covers cache, snapshot, adoption and retirement).
- `held_by` probes with a separate read-only descriptor and releases at once; the holder line is
  verified; lock fds are `O_CLOEXEC`, so command children never inherit the lock.
- Midnight handling: the day is re-read per decision and the queue is re-planned minus `processed`.
- `record_updated` prunes older days, caps at 64 KiB and raises `OSError`, which the caller names.
- `summary_line` clause budget leaves exactly 300 characters at most.
- `_row_action` honors `default_on` only for the `None` decision; recorded decisions are untouched.

_Reviewed: 2026-11-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_


## Orchestrator triage (2026-11-22)

Sources: this report (gsd-code-reviewer, deep: 0 critical, 0 high, 2 medium, 8 low, 1 info), the external lane `opencode-referee-one` (14 findings, one pass, 14:06 to 14:20; its numbered findings are the "Lane N" items), the security audit (`35-SECURITY.md`: SECURED, 21 threats: 18 closed, 3 accepted, 0 open, 7 low notes) and the orchestrator's real container check of plan 35-09 (PASS, see the 35-10 summary). ME-01 was reproduced by the reviewer and independently found by Lane 1; every other Lane item marked VERIFY is checked against the source by the fix executor before any change.

| Item | Source | Decision |
|---|---|---|
| Lane 1 + ME-01 + LO-01 + LO-02 | lane, reviewer (reproduced) | FIX: process lifetime in `update_all_runner`: cleanup is non-reentrant (a second SIGTERM during cleanup must not abort the SIGKILL), a cleanup that reports a surviving group aborts the batch instead of starting the next update, a normal command exit also ends its process group (descendants must not outlive the run and the lock), and the signal handlers are installed before `Popen` so no window orphans the new session; tests with a real child and descendant. |
| Lane 2 | lane | VERIFY, then FIX: a Brew-owned manager upgrade (`brew upgrade uv`) also upgrades installed dependents unless `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK` is set (read Homebrew's `cmd/upgrade.rb` under `/home/linuxbrew/.linuxbrew/Homebrew/Library/Homebrew/`); set it for the update-all commands only and state the remaining package-manager side effects in the limits list of the architecture rules. |
| Lane 3 | lane | VERIFY, then FIX (smallest sound mechanism): a successful pnpm self-update whose replay failed returns `updated` with the failure only in `detail`, which the schedule formatter drops; surface the replay failure in the run log and result line and block pnpm dependents when the restoration failed; keep the self-update's mutation record. |
| Lane 4 | lane | FIX: a manager skipped as `unknown-owner` (the service returns it before the guard runs) is NOT complete: track the structured outcome rather than `guard.refused`; the shared spy must behave like the real service (test with a spy that returns `unknown-owner` before the guard). |
| Lane 5 | lane | FIX: when a failed manager's refresh also fails to answer (`outdated=None`), its first-pass dependents appear in the log as skip-only rows (never authorized from old evidence). |
| Lane 6 | lane | VERIFY, then FIX or RECORD: bind the guard to more than the owner label if the ownership object carries the target or method (a changed target under the same owner skips); if it does not, RECORD as an accepted limit in the limits list. |
| Lane 7 | lane | DEFER: record the daily entry when the primary mutation is known, before slow follow-ups (midnight edge and an interrupt during follow-ups); the harm is a repeated, idempotent update; backlog 999.36. |
| Lane 8 + security note 1 | lane, auditor | FIX: refuse root at the CLI boundary for `--plan` too (before dependencies or settings are read); keep the dispatcher's check. |
| Lane 9 | lane | VERIFY, then FIX: the scheduled PATH includes the registry's standard pnpm executable directory (`PNPM_HOME/bin`) if the standalone layout puts it there; runner fixture for that layout. |
| Lane 10 + LO-06 | lane, reviewer | FIX: the planner carries known ownership-cycle and missing-manager blocks into the preview (no `would update` for a dependent the run predictably skips); the runtime guard stays. |
| Lane 11 | lane | DEFER: the log stays from the last run that reached tool execution; label it so in the screen text; backlog 999.36. |
| Lane 12 | lane | DEFER: a hard link to another file replaced by the same user can pass the regular-file check of the log append (same-user residual like the lock); backlog 999.36. |
| Lane 13 | lane | FIX: the container rerun verdict verifies the record's local date and `by` value and distinguishes "Ruff is already current" (installer evidence) from a proven `skipped: updated today`; `ruff_now` and `inventory_ruff` come from different reads; unit tests of the pure verdict. The orchestrator reruns the container after the fixes. |
| Lane 14 | lane | DEFER: the container target's fixed transcript path (two orchestrator runs can mix results); the target is orchestrator-run, serialized by hand; backlog 999.36. |
| ME-02 | reviewer | DEFER (owner UI decision): the `limits:` and `log:` lines show only at 100x30 and the detail pane is not focusable at 80x20; the vendor-shell-edit limit is also in the docs and the preview command; backlog 999.36 (owner decision: scrollable or focusable detail). |
| LO-03 | reviewer | DEFER: the runner's root refusal writes stderr only, no schedule-log line; backlog 999.36. |
| LO-04, LO-05 | reviewer | DEFER: a dangling `agent` link fails cursor-agent before the guard; the version probe runs the tool binary before the guard (both inherited per-tool behavior); backlog 999.36. |
| LO-07 | reviewer | FIX: `assert "homebrew_no_sudo" not in forbidden` can never fail: make it a real assertion; widen the privilege scan to the files that can run commands (`update.py`, `executors.py`, `run.py`, `setup.py`, `compose.py`) as a regression check. |
| LO-08 | reviewer | DEFER: `_update_all` is about 160 lines with a closure mutating five nonlocals and classifies by message prefix; a refactor, not a defect; backlog 999.36. |
| NE-01, IN-01 | reviewer | FIX (small): drop the unreachable `None` ownership branches and the unused `GROUP_INSTALLER`, and rename the shadowing parameter, if the change needs no assertion edit of an existing test. |
| Security notes 2, 3, 4, 5, 6, 7 | auditor | RECORD: uncapped in-memory output capture, an uncredential-scrubbed 0600 run log (as per-tool rows), the inherited environment, a helper left in its own group by a normally exiting command (covered by LO-01 now), the same-user `held_by` race (accepted residual) and the HEAD binding of container evidence (procedural: done by the orchestrator in the 35-10 summary). |
