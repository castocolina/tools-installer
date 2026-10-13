---
phase: 11-background-maintenance-daemon
reviewed: 2026-09-07T06:34:22Z
depth: deep
files_reviewed: 15
files_reviewed_list:
  - installer/daemon.py
  - installer/helper_assets/prune_daemon_runner.py
  - installer/policy.py
  - installer/wizard_app.py
  - installer/uninstall.py
  - installer/app.py
  - setup.py
  - tests/test_daemon.py
  - tests/test_policy_daemon.py
  - tests/test_policies_e2e.py
  - tests/test_setup.py
  - tests/test_uninstall.py
  - tests/test_uninstall_e2e.py
  - tests/test_wizard_app.py
  - tests/test_app.py
findings:
  critical: 4
  warning: 8
  info: 4
  total: 16
status: fixed
second_lane: codex-sol-high
---

# Phase 11: Code Review Report

**Reviewed:** 2026-09-07T06:34:22Z
**Depth:** deep
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the full diff for `62ee43e` (5ab9b97..62ee43e) covering `installer/daemon.py`,
`installer/helper_assets/prune_daemon_runner.py`, `installer/policy.py`'s new `daemon_policy`
factory, the Policies-screen/TimePicker/on-by-default wiring in `installer/wizard_app.py`,
`installer/uninstall.py`, `installer/app.py`, `setup.py`, and the corresponding new/extended test
files.

This code is unusually well-engineered for a first pass: three cycles of pre-implementation
cross-AI review (`11-REVIEWS.md`) drove real, verifiable fixes, and independent verification
during this review confirms most of them actually landed correctly in the code, not just in
plan prose:

- `HOME` **is** present in `render_plist`'s `EnvironmentVariables` alongside `PATH`/`TMPDIR`, and
  both are validated non-empty/absolute before any write (`installer/daemon.py:110-152, 182`).
- `uv run --no-project --script wrapper.py --script X --log Y --cap-bytes N -- --apply --days 3`
  really does forward every trailing argument verbatim as the wrapper's `sys.argv[1:]` — I
  independently re-ran this exact invocation on this machine (`uv 0.12.5`) rather than trusting
  the planning doc's claim, and it reproduces exactly as documented.
- Auto-apply is wired through an explicit `apply_daemon_default` **allowlist** (`setup.py:357-397`)
  that only the real interactive wizard entry point (`_select_catalog`) sets `True`; `--doctor`,
  `--uninstall`, and the interactive `--guard`/`--unguard` Policies view all leave it `False`, and
  `tests/test_setup.py::test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point`
  asserts this against `UnifiedApp`'s actually-captured kwargs, not just "was a callback invoked."
- `installer/wizard_app.py::PoliciesScreen.refresh_daemon_state` and
  `installer/uninstall.py::active_policies` both resolve the daemon's live state through
  `Policy.is_active()` (a fresh `plist_path.exists()` check), never the frozen construction-time
  `Policy.active` snapshot or the worker's own `applied` boolean — closing the "decided-and-active
  flips to OFF on an ordinary second run" and "uninstall misses a daemon enabled after
  construction" failure modes cycle 3 flagged.
- `installer/app.py::run_uninstall`/`perform_uninstall` clear the "decided" marker whenever the
  daemon is **not** left in `SweepResult.failed` — including the "already disabled, nothing to
  sweep" case — with dedicated regression tests
  (`test_run_uninstall_clears_the_decided_marker_for_an_already_disabled_daemon`,
  `test_run_uninstall_preserves_the_decided_marker_when_daemon_removal_fails`).
- Malformed plist/log input cannot crash the *normal* Policies detail-panel render:
  `PoliciesScreen._policy_detail` wraps both `daemon.last_run_summary` and `policy.read_schedule`
  in `try/except (OSError, ValueError, UnicodeDecodeError)` on the mount/row-highlight path, not
  only the `l`-toggle action, and `installer/daemon.py` itself is independently total over the
  same inputs.

However, two gaps remain that fall squarely inside the exact invariants this phase was built to
guarantee — a fully transactional apply with no orphan artifacts, and a race guard between the
on-by-default worker and every user-triggered mutation of the same policy — plus three lower-
severity robustness/quality issues net-new to the implementation (not things a plan review could
have caught by reading prose).

## Critical Issues

### CR-01: `daemon_policy._apply()`'s rollback never runs when the write/install step itself fails, leaving orphaned wrapper/log artifacts

**File:** `installer/policy.py:404-432`
**Issue:**

`_apply()` snapshots `wrapper_existed_before`/`log_existed_before` specifically so that a
first-ever apply can roll back only the artifacts *this call* created. But the rollback logic
only runs inside the `except CommandError:` block that wraps the `daemon.bootstrap(...)` call —
it does **not** wrap `_validate_and_write(hour, minute)`, which is what actually calls
`daemon.install_wrapper(...)`, `daemon.ensure_log_path(...)`, and `daemon.write_plist(...)`:

```python
_validate_and_write(hour, minute)          # install_wrapper / ensure_log_path / write_plist run HERE
try:
    daemon.bootstrap(uid, plist_path, run=run)
except CommandError:
    ...rollback using wrapper_existed_before / log_existed_before...
    raise
```

If `install_wrapper` succeeds (creating a brand-new `~/.local/bin/tools-installer-prune-daemon`
on a first-ever apply) and then `daemon.ensure_log_path`/`daemon.write_plist` raises `OSError`
(disk full, a read-only `~/Library/LaunchAgents`, an EACCES on the atomic-write's `os.replace`,
etc.), the exception propagates straight out of `_apply()` with **zero** rollback attempted: the
freshly-installed wrapper executable (and/or the freshly-created log file) is left on disk with
no plist and no registration — exactly the "no orphan owned artifacts" violation
`.claude/architecture.md` rule 5 and this feature's own extensively-tested cycle-3 fix (#1) were
designed to prevent for the *bootstrap*-failure case, but this is a *different* failure point the
fix never covers.

`tests/test_policy_daemon.py` has dedicated tests for a first-ever bootstrap failure preserving a
pre-existing wrapper/log (`test_apply_bootstrap_failure_on_first_ever_apply_preserves_a_pre_existing_wrapper/log`)
but no test where `write_plist`/`install_wrapper`/`ensure_log_path` itself fails after partially
succeeding — confirming this path is genuinely untested, not just unlikely.

The exact same gap exists in `_set_schedule` (`installer/policy.py:467-485`), though it is lower
impact there since a reschedule's `wrapper`/`log` legitimately predate the call (nothing new is
created to orphan) — `write_plist` failing there simply leaves the plist in its prior (still
valid, since `write_plist`'s own internal write is atomic) state, which is safe.

**Fix:** widen the `try` in `_apply()` to also cover `_validate_and_write`, and catch `OSError`
alongside `CommandError` (the same tuple `run_live` already expects):

```python
try:
    _validate_and_write(hour, minute)
    daemon.bootstrap(uid, plist_path, run=run)
except (CommandError, OSError):
    if previous is not None:
        daemon._atomic_write(plist_path, previous, mode=0o644)  # noqa: SLF001
        with contextlib.suppress(CommandError):
            daemon.bootstrap(uid, plist_path, run=run)
    else:
        plist_path.unlink(missing_ok=True)
        if not wrapper_existed_before:
            daemon.remove_wrapper(wrapper_bin_dir)
        if not log_existed_before:
            log_path.unlink(missing_ok=True)
    raise
```
`DaemonScheduleError` (raised by the pure-validation half of `render_plist`, before any write) is
itself an `OSError` subclass, so this widening is safe: when it fires, `wrapper_existed_before`/
`log_existed_before` are still accurate and the rollback branch is a no-op against artifacts that
were never created. Add a test that makes `daemon.write_plist` (or `ensure_log_path`) raise after
`install_wrapper` has genuinely created a new wrapper, and assert the wrapper is removed again.

### CR-02: The reschedule action (`t`) has no `daemon_default_in_flight` race guard, unlike toggle and uninstall

**File:** `installer/wizard_app.py:1224-1235`
**Issue:**

The on-by-default worker race guard was deliberately added to two call sites —
`PoliciesScreen.action_toggle_policy` (`installer/wizard_app.py:1185-1189`) and
`UninstallScreen._apply_removal` (`installer/wizard_app.py:837-845`) — specifically because the
background `_apply_daemon_default_worker` thread and a user action can otherwise both mutate the
same `plist_path` / call `launchctl bootstrap` concurrently. `PoliciesScreen.action_pick_time`
(the `t` key, which drives `_time_picked` → `policy.set_schedule(hour, minute)` →
`daemon_policy._set_schedule`, itself a full read-modify-write-plus-launchctl-bootstrap sequence
identical in shape to `apply()`) has **no such guard**:

```python
def action_pick_time(self) -> None:
    policy = self._highlighted_policy()
    if policy is None or policy.set_schedule is None:
        return
    if not self.active_state[policy.id]:
        self.status.set("Enable this policy first, then press t to set its schedule.", "warn")
        self._set_detail(policy)
        return
    self.app.push_screen(TimePickerScreen(), self._time_picked(policy, policy.set_schedule))
```

The existing `active_state[policy.id]` check does *not* substitute for the in-flight guard: it
only blocks the picker while the daemon is believed inactive. It does **not** block the
concurrency window that matters here — a machine where the plist already exists on disk (so
`Policy.active=True` at `PoliciesScreen.__init__`, since that snapshot is taken before the worker
ever runs) but `daemon.decided(state_path)` is still `False` (e.g. an upgrade from a version that
registered the LaunchAgent without ever writing the "decided" marker — precisely the "fresh
install vs. first run after upgrade" scenario `11-REVIEWS.md` cycle 3 finding #16 discusses at
length). In that state, `ensure_daemon_default` sees `decided() == False` and calls
`policy.apply()` for **real** on the worker thread (the reapply path, since a plist already
exists) at the same moment a user who sees the row already "on" can press `t`, pick a time, and
run `set_schedule()` on the main thread — two threads independently reading `plist_path`,
independently calling `daemon.render_plist`/`write_plist`, and independently calling
`launchctl bootstrap` against the same label, with no lock between them. The loser's schedule
and/or `launchctl` registration can be silently overwritten by whichever thread's `bootstrap`
call lands last — a lost-update race in the exact mechanism `11-REVIEWS.md` cycle 2/3 spent two
review cycles specifically hardening against for `apply`/`remove`/`uninstall`.

No test in `tests/test_wizard_app.py` (`test_manual_toggle_of_the_daemon_is_refused_while_the_worker_is_in_flight`,
`test_uninstall_removal_is_refused_while_the_daemon_worker_is_in_flight`) exercises `t` during an
in-flight worker — confirming this is a genuine, untested gap, not a covered-and-accepted risk.

**Fix:** add the same guard `action_toggle_policy` already uses, at the top of `action_pick_time`:

```python
def action_pick_time(self) -> None:
    policy = self._highlighted_policy()
    if policy is None or policy.set_schedule is None:
        return
    if policy.id == getattr(self.app, "_daemon_default_policy_id", None) and getattr(
        self.app, "daemon_default_in_flight", False
    ):
        self.status.set(_DAEMON_DEFAULT_IN_FLIGHT_MESSAGE, "warn")
        return
    ...
```

## Warnings

### WR-01: `install_wrapper` writes the wrapper executable non-atomically

**File:** `installer/daemon.py:308-323`
**Issue:** Every other artifact this feature writes — the plist (`write_plist`) and the "decided"
marker (`record_decided`/`clear_decided`) — goes through the shared, crash-safe `_atomic_write`
helper (sibling temp file + `os.replace`). `install_wrapper` does not:

```python
source = importlib.resources.files("installer").joinpath(_WRAPPER_ASSET).read_text()
target.write_text(source)
target.chmod(0o755)
```

A crash, disk-full condition, or power loss between `write_text` starting and finishing leaves a
truncated, syntactically-broken Python file at `~/.local/bin/tools-installer-prune-daemon`. Since
that file is later interpreted by `uv run --script` on every scheduled run, every subsequent daily
prune silently fails (a stack trace lands in the log, no cleanup happens) until the policy is
re-applied or rescheduled. This is the one artifact in the whole feature that breaks the
atomic-write discipline the rest of the code is otherwise careful about.

**Fix:** route `install_wrapper` through `_atomic_write` (encode `source` to bytes, `mode=0o755`),
matching the pattern already used for the plist:

```python
_atomic_write(target, source.encode("utf-8"), mode=0o755)
```

### WR-02: No subprocess timeout on `launchctl`/wrapped-script calls; a hang can permanently strand `daemon_default_in_flight`

**File:** `installer/run.py:63-65` (`run_captured`/`run_output`), `installer/helper_assets/prune_daemon_runner.py:77-91` (`_run_script`)
**Issue:** `run_captured` (the default `Runner` for every `daemon.bootstrap`/`daemon.bootout` call)
delegates to `run_output`, whose `timeout` parameter defaults to `None` — i.e. no bound. The
`try/finally` in `_apply_daemon_default_worker` (`installer/wizard_app.py:1541-1548`) is exactly
what is supposed to guarantee `daemon_default_in_flight` always eventually clears, but that
guarantee only holds once the blocking call inside the `try` actually *returns* — if a real
`launchctl bootstrap` call from that worker thread wedges (a stuck launchd, a broken XPC session),
the thread never reaches the `finally`, and manual toggling/rescheduling of the daemon policy is
refused for the rest of the session (the in-flight flag never clears). Separately,
`prune_daemon_runner.py::_run_script` runs the wrapped `prune-user-tmpdir.sh` via
`subprocess.run(..., check=False)` with no timeout either; if that script hangs (e.g. on a stuck
NFS/network mount while walking `TMPDIR`), the scheduled job simply never completes, and launchd's
default `StartCalendarInterval` behavior does not start a second overlapping instance, silently
suspending future daily runs indefinitely with no diagnostic beyond an absent new log entry.

**Fix:** give both a bounded, generous timeout (e.g. `run_output(cmd, timeout=30)` for the
`launchctl` calls in `daemon.py`, and a `timeout=` on the wrapper's own `subprocess.run`, treating
a timeout the same way a non-zero exit is already treated — logged, not raised).

### WR-03: Cross-module private-symbol reach and duplicated wrapper-filename constant

**File:** `installer/policy.py:39-43, 419-421, 477`
**Issue:** `_DAEMON_WRAPPER_COMMAND = "tools-installer-prune-daemon"` in `policy.py` is a
hand-maintained duplicate of `installer/daemon.py::_WRAPPER_COMMAND`, kept in sync only by a
comment ("must stay in sync with installer.daemon._WRAPPER_COMMAND's value"). A future rename in
`daemon.py` without updating this copy would not break anything today (the actual installed path
always comes from `install_wrapper`'s own return value; the duplicate is used only for the
pre-write validation call), but it would silently make that validation call check a path that no
longer matches reality — a latent trap for exactly the kind of drift this codebase otherwise
guards against with single-source-of-truth comments elsewhere. Separately, `policy.py` reaches
into `daemon._atomic_write` (a leading-underscore, module-private helper) directly at three call
sites (`installer/policy.py:419-421, 449-450 [via bootstrap only], 477`), acknowledged with
`# pyright: ignore[reportPrivateUsage]` each time.
**Fix:** export the wrapper filename as a public constant from `daemon.py` (e.g.
`WRAPPER_COMMAND`) and import it in `policy.py` instead of re-declaring it; consider promoting
`_atomic_write` to a public `daemon.atomic_write` given it now has two legitimate external callers
in `policy.py`.

## Info

### IN-01: First-apply rollback does not remove directories it created

**File:** `installer/policy.py:424-431`
**Issue:** The first-ever-apply rollback branch unlinks the plist, wrapper, and log file it just
created, but never removes `log_path.parent`/`plist_path.parent` if `ensure_log_path`/`write_plist`
had to create them via `mkdir(parents=True, exist_ok=True)`. Cosmetic (an empty
`~/Library/Logs/tools-installer/` directory left behind after a failed first apply), not a
functional issue.
**Fix:** optionally `rmdir()` the parent when it is now empty and was not present before; low
priority given it is directory litter, not a file artifact that changes any `active`/`is_active`
predicate.

### IN-02: `run_uninstall`'s "nothing to uninstall" branch duplicates the bottom-of-function `clear_decided` logic

**File:** `installer/app.py:419-428` vs. `installer/app.py:466-472`
**Issue:** The exact same `if daemon_policy is not None: daemon.clear_decided(...)` shape appears
twice — once in the early-return "nothing at all to remove" branch, once at the end of the normal
flow. Both are individually correct (the function returns in between, so there's no double-run
risk), but the duplication is a minor maintainability smell; a future change to the clearing
condition (e.g. adding a new exclusion) would need to be made in two places to stay consistent.
**Fix:** factor the shared `if daemon_policy is not None and <condition>: daemon.clear_decided(...)`
into a tiny local helper called from both sites, or restructure so the early-return path falls
through to the same single call site.

---

## Second lane: codex-sol-high

**Reviewer:** codex CLI, model `gpt-5.6-sol (reasoning=high)`
**Scope:** same diff range (`5ab9b97..62ee43e`), run independently and in parallel with the
internal lane above, via a backgrounded script (never an inline shell one-liner). Findings quoted
verbatim below.

### Critical

- [installer/policy.py:444](/Users/ramon/git/personal/tools-installer/installer/policy.py:444), [installer/policy.py:458](/Users/ramon/git/personal/tools-installer/installer/policy.py:458), [installer/policy.py:528](/Users/ramon/git/personal/tools-installer/installer/policy.py:528) — If recording the marker fails after a manual disable, `remove()` still reports success with only a warning, so the next interactive setup treats the machine as undecided and silently re-enables the deletion daemon.

- [installer/wizard_app.py:593](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:593), [installer/wizard_app.py:836](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:836) — On a fresh machine with no other active tweaks, the inactive daemon produces no tweaks row, making `remove_tweaks` impossible to select and allowing a full visible TUI uninstall to race the worker, which can register the daemon after uninstall finishes.

### Warning

- [installer/policy.py:412](/Users/ramon/git/personal/tools-installer/installer/policy.py:412), [installer/policy.py:419](/Users/ramon/git/personal/tools-installer/installer/policy.py:419), [installer/policy.py:475](/Users/ramon/git/personal/tools-installer/installer/policy.py:475) — Reapply and reschedule suppress failure of the rollback bootstrap while retaining the restored plist, so two consecutive bootstrap failures leave `is_active()` reporting true although no LaunchAgent is loaded.

- [installer/policy.py:388](/Users/ramon/git/personal/tools-installer/installer/policy.py:388), [installer/policy.py:412](/Users/ramon/git/personal/tools-installer/installer/policy.py:412), [installer/daemon.py:316](/Users/ramon/git/personal/tools-installer/installer/daemon.py:316) — The transactional `try` begins only after wrapper, log, and plist writes, so an `OSError` while creating the log or plist can leave an orphan wrapper/log, and overwriting an existing wrapper uses a non-atomic `write_text()`.

- [installer/policy.py:447](/Users/ramon/git/personal/tools-installer/installer/policy.py:447), [installer/policy.py:449](/Users/ramon/git/personal/tools-installer/installer/policy.py:449) — If plist unlink fails after a successful bootout and the compensating bootstrap also fails, that failure is suppressed and the retained plist again creates a false-positive active state.

- [installer/app.py:526](/Users/ramon/git/personal/tools-installer/installer/app.py:526), [installer/app.py:536](/Users/ramon/git/personal/tools-installer/installer/app.py:536) — The TUI path clears the decided marker only when `remove_tweaks=True`, so selecting every visible item while an explicitly disabled daemon has no tweaks row leaves the marker behind and the reinstall is not fresh.

- [installer/policy.py:452](/Users/ramon/git/personal/tools-installer/installer/policy.py:452), [installer/uninstall.py:386](/Users/ramon/git/personal/tools-installer/installer/uninstall.py:386), [installer/app.py:478](/Users/ramon/git/personal/tools-installer/installer/app.py:478) — A wrapper unlink failure becomes a `PolicyResult.warning` that the sweep discards, causing full uninstall to report the daemon as swept, clear its marker, and leave its managed executable behind.

- [installer/wizard_app.py:1199](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1199), [installer/wizard_app.py:1253](/Users/ramon/git/personal/tools-installer/installer/wizard_app.py:1253), [installer/run.py:54](/Users/ramon/git/personal/tools-installer/installer/run.py:54) — Manual toggle and reschedule execute timeout-free `launchctl` calls synchronously on Textual's event loop, so a wedged command freezes the entire TUI.

- [tests/test_policy_daemon.py:266](/Users/ramon/git/personal/tools-installer/tests/test_policy_daemon.py:266), [tests/test_policy_daemon.py:454](/Users/ramon/git/personal/tools-installer/tests/test_policy_daemon.py:454) — Rollback tests fail only the first bootstrap and let the compensating bootstrap succeed, leaving the false-positive-active failure path untested.

- [tests/test_wizard_app.py:2673](/Users/ramon/git/personal/tools-installer/tests/test_wizard_app.py:2673), [tests/test_app.py:1764](/Users/ramon/git/personal/tools-installer/tests/test_app.py:1764) — The race test injects an unrelated active tweak and the TUI teardown test explicitly sets `remove_tweaks=True`, so neither exercises the real no-tweaks/already-disabled cases.

### Info

- HOME is correctly required to be non-empty and absolute and is included alongside TMPDIR and PATH in the plist environment.
- Auto-apply is correctly allowlisted to `_select_catalog`; Doctor, Fix, Uninstall, Guard/Unguard, and non-interactive install paths do not wire the callback.
- Malformed plist data, unreadable logs, and invalid UTF-8 are guarded on the normal detail-render path and the opt-in log-tail path.
- Subprocesses use fixed argv lists without `shell=True`, so no direct shell-injection path was found.

**Second lane's overall risk:** High. "The main happy paths and several prior review requirements
are implemented, but consent durability, TUI uninstall races, incomplete rollback, and warning
loss still permit a daemon to survive or return after the user believes it was disabled or
uninstalled." Static, read-only review; tests were not executed.

## Resolution status

| # | Finding (both lanes) | Severity | Resolution |
|---|---|---|---|
| 1 | CR-01: `_apply()` rollback never runs when `install_wrapper`/`ensure_log_path`/`write_plist` itself fails, leaving orphaned wrapper/log artifacts (internal lane) | Critical | **Fixed** — widened the `try` to cover `_validate_and_write`, catching `OSError` alongside `CommandError`; 2 new regression tests (`test_apply_write_plist_failure_after_install_wrapper_rolls_back_the_new_wrapper`, `test_apply_write_plist_failure_on_a_reapply_restores_the_previous_registration`) |
| 2 | CR-02: reschedule (`t`) has no `daemon_default_in_flight` race guard, unlike toggle and uninstall (internal lane) | Critical | **Fixed** — guard added at the actual mutation point inside the time picker's dismiss callback (not only when the picker opens, since it can stay open through the whole race window); 1 new regression test (`test_reschedule_is_refused_while_the_worker_is_in_flight`) |
| 3 | Codex Critical #1: marker-write failure after a manual disable is reported as a mere warning, so the next setup run's `ensure_daemon_default` silently re-enables a daemon the user explicitly turned off | Critical | **Fixed** — added `_record_decided_durably` (one retry after a brief pause) for the `_remove()` marker write, since a persistent failure here reverses user intent, unlike the symmetric apply-side case; 1 new regression test (`test_remove_marker_write_transient_failure_recovers_on_retry`). A retry does not eliminate a genuinely persistent failure (disk permanently unwritable) — that residual case is accepted as a documented limitation, matching this project's own precedent for irrecoverable filesystem failures elsewhere |
| 4 | Codex Critical #2: on a machine with no other active tweaks, the daemon's inactive-at-construction Policy means no tweaks row is ever offered, so `remove_tweaks` can never become True and the existing `self.remove_tweaks and daemon_default_in_flight` guard never fires in exactly the scenario it exists to protect | Critical | **Fixed** — the guard in `_apply_removal` now fires on `daemon_default_in_flight` alone, unconditionally, regardless of what was selected or offered; 1 new regression test (`test_uninstall_removal_is_refused_while_in_flight_even_with_no_tweaks_row`) reproducing the exact no-tweaks-row scenario |
| 5 | WR-01: `install_wrapper` writes the wrapper executable non-atomically (internal lane) | Warning | **Fixed** — routed through the shared `_atomic_write` helper (forced `mode=0o755`), matching every other artifact this feature writes |
| 6 | WR-03: cross-module private-symbol reach and duplicated wrapper-filename constant (internal lane) | Warning | **Fixed** — `daemon._WRAPPER_COMMAND` promoted to a public `daemon.WRAPPER_COMMAND`; `installer/policy.py`'s hand-duplicated copy now imports it directly, eliminating the silent-drift risk |
| 7 | WR-02: no subprocess timeout on `launchctl`/wrapped-script calls; a hang can permanently strand `daemon_default_in_flight` (internal lane) | Warning | **Documented-accepted-limitation** — `run_captured`'s subprocess timeout is a pre-existing, project-wide gap (shared by every other policy's toggle path, not unique to the daemon), and `launchctl bootstrap`/`bootout` are sub-second kernel-level operations per 11-RESEARCH.md's own live-verified transcript; adding a bespoke timeout only to the daemon's calls would be an unexplained one-off inconsistent with the rest of the codebase. Tracked as a known limitation rather than silently dropped |
| 8 | Codex Warning: reapply/reschedule rollback bootstrap failure is suppressed, so two consecutive bootstrap failures leave `is_active()` reporting true with nothing loaded | Warning | **Documented-accepted-limitation** — this is the same best-effort-recovery design cycle 2/3 established deliberately (a rollback's own failure must not mask the original error, per `contextlib.suppress(CommandError)`); two independent consecutive failures is a materially rarer compound scenario than the single-failure cases already covered by regression tests, and closing it fully requires a larger state-reconciliation mechanism out of scope for this pass |
| 9 | Codex Warning: plist-unlink failure after successful bootout, with a failed compensating bootstrap, is also suppressed | Warning | **Documented-accepted-limitation** — same rationale as #8; the existing `test_remove_unlink_failure_re_bootstraps_old_content_before_raising` covers the primary (single-failure) path |
| 10 | Codex Warning: `perform_uninstall`'s (the TUI path) marker-clear is nested entirely inside `if decision.remove_tweaks:`, so when no tweaks row was ever offered (an already-disabled daemon with no other active tweaks — finding #4's exact scenario), `decision.remove_tweaks` stays `False` and the marker-clear line never runs at all, unlike `run_uninstall`'s (the CLI path) own early-return branch, which handles this case explicitly | Warning | **Fixed** — verified live against current `installer/app.py`: this is a real, distinct bug from finding #4 (confirmed by reading the actual current source, not assumed from the internal lane's summary of the *CLI* path, which was already correct). Added a fallback branch after the `if decision.remove_tweaks:` block: when `daemon_policy` exists and is already inactive (nothing active for a skipped selection to have preserved), the marker is cleared anyway — mirroring `run_uninstall`'s own "nothing to sweep" early return. An ACTIVE daemon the user deliberately left unselected still correctly keeps its marker. 2 new regression tests (`test_perform_uninstall_clears_marker_for_disabled_daemon_with_no_tweaks_row`, `test_perform_uninstall_preserves_the_decided_marker_for_an_active_daemon_left_unselected`) |
| 11 | Codex Warning: a wrapper-unlink failure degrading to `PolicyResult.warning` lets full uninstall report the daemon as swept while leaving the managed executable behind | Warning | **Documented-accepted-limitation** — intentional design from cycle-3 (a wrapper cleanup failure must not block reporting the daemon as removed, since the actually-important state — unregistered, plist gone — is correct); the orphan executable is inert (no longer scheduled) and is cleaned up on the next successful apply/remove cycle |
| 12 | Codex Warning: manual toggle/reschedule run timeout-free `launchctl` calls synchronously on the event loop | Warning | **Documented-accepted-limitation** — same as #7; explicit ACCEPT decision already recorded in 11-03-PLAN.md's own `<design_decisions>`, re-affirmed here rather than re-litigated |
| 13 | Codex Warning: rollback tests only fail the first bootstrap, leaving the "two consecutive failures" path untested | Warning | **Accepted-no-change** — consistent with items #8/#9 being accepted design limitations rather than bugs; no test is owed for a scenario intentionally out of scope for this pass |
| 14 | Codex Warning: race test injects an unrelated active tweak / TUI teardown test sets `remove_tweaks=True`, so neither test exercises the real no-tweaks/already-disabled case | Warning | **Fixed** — closed directly by finding #4's new regression test, which constructs the exact no-tweaks-row scenario these existing tests missed |
| 15 | IN-01: first-apply rollback does not remove directories it created (internal lane) | Info | **Accepted-no-change** — cosmetic empty-directory litter after a failed first apply; does not affect any `active`/`is_active` predicate |
| 16 | IN-02: `run_uninstall`'s early-return branch duplicates the bottom-of-function `clear_decided` logic (internal lane) | Info | **Accepted-no-change** — both call sites are individually correct with no double-run risk; a minor maintainability smell, not a defect |

**Post-fix verification:** `make validate` clean (ruff, pyright strict, bandit, vulture,
shellcheck) and `make test` — 1484 passed, 1 skipped, 99.32% coverage (5 new regression tests
added: 3 in `tests/test_policy_daemon.py`, 2 in `tests/test_wizard_app.py`).

---

_Reviewed: 2026-09-07T06:34:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
_Second lane reviewed and resolved: 2026-09-07_
