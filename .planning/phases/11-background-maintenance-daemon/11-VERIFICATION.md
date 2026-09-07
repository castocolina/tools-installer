---
phase: 11-background-maintenance-daemon
verified: 2026-09-07T08:05:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification: []
---

# Phase 11: Background Maintenance Daemon Verification Report

**Phase Goal:** The existing, already-safe `scripts/prune-user-tmpdir.sh` becomes a set-and-forget background policy, toggleable the same way every other Policies entry already is, with a real audit trail instead of silent background deletion.
**Verified:** 2026-09-07T08:05:00Z (Tier-3 real-machine verification: 2026-09-07T08:05:00Z, superseding the earlier `human_needed` verdict)
**Status:** passed
**Re-verification:** Yes — the initial pass (2026-09-07T07:28:57Z) routed the real-LaunchAgent-firing test to human verification; per `.planning/ONESHOT-RULES.md` Rule 14's Tier-3 model, this was instead performed directly on this machine using a disposable, uniquely-labeled test LaunchAgent (never the real production label/paths), bootstrapped, force-triggered, and torn down within minutes. This caught a genuine, 100%-reproducing production bug (see below), which was fixed and re-verified before this report was finalized.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On-by-default: a normal interactive `make setup` run auto-applies the daemon exactly once per machine, via the "decided" marker, with no manual enabling needed | ✓ VERIFIED | `setup.py::_select_catalog` is the only call site passing `apply_daemon_default=True` into `_build_app` (setup.py:402); `_build_app` only wires a real `daemon_default` callback when that flag is set (setup.py:367-379); `UnifiedApp.on_mount` fires `_apply_daemon_default_worker` when `_daemon_default is not None` (wizard_app.py:1535-1536), calling `ensure_daemon_default(policy, state_path)` (installer/policy.py:549-573), which checks `daemon.decided(state_path)` first and is a no-op once already decided. Directly tested end-to-end: `tests/test_setup.py::test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point`, and `tests/test_wizard_app.py::test_ensure_daemon_default_applies_once_when_undecided` / `test_ensure_daemon_default_is_a_noop_once_decided` / `test_ensure_daemon_default_returns_false_on_a_failed_apply_without_recording`. |
| 2 | Linux invisibility/inertness: the daemon is never constructed, never wired, produces no TUI artifacts on Linux | ✓ VERIFIED | `setup.py::_build_daemon_policy` returns `None` immediately when `platform.os != "macos"` (setup.py:177-178); `_build_app` only appends the daemon Policy to `policy_inputs.policies` when it is not `None` (setup.py:307). Directly tested: `tests/test_setup.py::test_daemon_policy_is_absent_on_linux` (asserts no `daemon:`-prefixed policy id reaches `PolicyInputs` on a simulated Debian platform) and `test_build_daemon_policy_returns_none_off_macos`. |
| 3 | Configurable time-of-day schedule via the TUI's time picker, persisted and re-readable | ✓ VERIFIED | `TimePickerScreen` (wizard_app.py:1351-1384) offers 30-minute-granularity slots; `action_pick_time`/`_time_picked` (wizard_app.py:1230-1286) route the chosen `HH:MM` through `policy.set_schedule` via `run_live`; `daemon_policy._set_schedule` (installer/policy.py:506-524) re-validates, re-writes the plist, and re-bootstraps, rolling back on a `launchctl` failure; `read_schedule` (installer/daemon.py:233-255) parses `StartCalendarInterval` back out of the plist and is rendered in the detail panel (wizard_app.py:1115-1122). Directly tested: `tests/test_wizard_app.py::test_time_picker_selecting_a_slot_calls_set_schedule_with_parsed_hour_minute`, `test_time_picker_set_schedule_failure_surfaces_on_status_line`, plus `tests/test_policy_daemon.py` transactional apply/reschedule tests and `tests/test_daemon.py` plist round-trip tests. |
| 4 | Full audit-trail observability: last-run summary and log-tail visible from the Policies detail panel | ✓ VERIFIED | `daemon.last_run_summary` (installer/daemon.py:429-466) parses the last `=== timestamp ===` block and its `deleted: N` line; `PoliciesScreen._policy_detail` appends it whenever `policy.log_path is not None` (wizard_app.py:1108-1114); `action_toggle_log`/`_log_tail` (wizard_app.py:1149-1154, 1132-1139) show the last N lines of the real log file, bound to the `l` key (wizard_app.py:932). The log itself is written by the standalone `installer/helper_assets/prune_daemon_runner.py` wrapper (timestamped header + stdout/stderr + exit code, then byte-cap truncation snapped to a run boundary). Directly tested: `tests/test_daemon.py` (`last_run_summary` cases), `tests/test_wizard_app.py` last-run/log-view tests, `tests/test_wait_time.py`-style coverage of the wrapper via `tests/test_helper_assets` equivalents (98% coverage on `prune_daemon_runner.py`). |
| 5 | Safe, complete teardown on uninstall (both CLI `run_uninstall` and TUI `perform_uninstall`) — no orphaned wrapper, plist, or stale "decided" marker survives, including the already-inactive-daemon edge case | ✓ VERIFIED | `run_uninstall` (installer/app.py:367-480) sweeps the daemon via `active_policies`/`sweep_policies` and clears the marker post-sweep unless the daemon is in `swept.failed`, with an explicit "nothing to sweep" early-return branch that still clears the marker for an already-inactive daemon (app.py:419-428). `perform_uninstall` (app.py:495-553) mirrors this: clears the marker after a real sweep, AND (the 7ceb950 fix) clears it in the `remove_tweaks=False` branch when the daemon was already inactive (app.py:539-551) — closing exactly the gap the dual-lane review's finding #10/CR-04 identified. `daemon_policy._remove()` unregisters via `daemon.bootout`, removes the plist, removes the wrapper, and retries the marker write once (`_record_decided_durably`). Directly tested: `tests/test_app.py::test_perform_uninstall_clears_marker_for_disabled_daemon_with_no_tweaks_row`, `test_perform_uninstall_preserves_the_decided_marker_for_an_active_daemon_left_unselected`, plus `tests/test_policy_daemon.py` rollback/marker-retry regression tests referenced in 11-REVIEW.md's resolution table (items 1, 3, 4, 10). |
| 6 | `make doctor` and other non-setup entry points remain genuinely read-only/non-mutating with respect to the daemon (never auto-apply it) | ✓ VERIFIED | `_build_app`'s allowlist comment and code (setup.py:357-379) wire a real `daemon_default` callback ONLY when `apply_daemon_default=True`, which only `_select_catalog` (the bare `make setup` / no-flag path) passes; `_run_doctor`, `_run_fix`, `_run_uninstall`, and the `--guard`/`--unguard` interactive branch all call `_build_app` without that flag, defaulting to `False`. The daemon Policy object is still constructed and shown (read-only visibility), but no auto-apply worker is ever wired. Directly tested: `tests/test_setup.py::test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point` asserts `daemon_default is None` for `--doctor`, `--uninstall`, and `--guard`, and non-`None` only for the bare `make setup` path. |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/daemon.py` | plist gen/parse, launchctl bootstrap/bootout, wrapper install/remove, "decided" marker | ✓ VERIFIED | 467 lines, fully substantive; 100% test coverage (`installer/daemon.py 153 0 54 0 100%`) |
| `installer/policy.py::daemon_policy` | Policy factory: transactional apply/remove/set_schedule, soft `fd`/`rg` gating | ✓ VERIFIED | Lines 351-546; 100% coverage; transactional rollback logic read directly and matches REVIEW.md's claimed fixes |
| `installer/wizard_app.py` (PoliciesScreen, TimePickerScreen, UnifiedApp) | detail panel (last-run/log), `t`/`l` bindings, on-by-default worker, race guards | ✓ VERIFIED | 1673 lines; 98% coverage; direct read confirms `action_pick_time`, `_apply_removal`, `_apply_daemon_default_worker`, `daemon_default_in_flight` guards all present and wired as claimed |
| `installer/app.py` (`run_uninstall`, `perform_uninstall`) | full teardown incl. already-inactive edge case | ✓ VERIFIED | 100% coverage; both functions read directly, match REVIEW.md's fix descriptions exactly |
| `installer/helper_assets/prune_daemon_runner.py` | standalone log-writing/truncating wrapper | ✓ VERIFIED | 161 lines, self-contained stdlib-only; 98% coverage |
| `setup.py` (`_build_daemon_policy`, `_build_app`) | macOS-only gating, on-by-default allowlist wiring | ✓ VERIFIED | Read directly; allowlist logic and comments match test assertions |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `setup.py::_select_catalog` | `UnifiedApp.__init__(daemon_default=...)` | `apply_daemon_default=True` allowlist | ✓ WIRED | Only call site passing the flag; verified by direct read + `test_daemon_default_is_wired_only_for_the_genuine_setup_wizard_entry_point` |
| `UnifiedApp.on_mount` | `installer/policy.py::ensure_daemon_default` | `_apply_daemon_default_worker` thread worker | ✓ WIRED | Worker calls `self._daemon_default()`, which closes over `ensure_daemon_default(daemon_policy_instance, state_path=...)` |
| `PoliciesScreen.action_pick_time` | `installer/policy.py::daemon_policy._set_schedule` | `Policy.set_schedule` closure, via `run_live` | ✓ WIRED | Confirmed by direct read of `_time_picked`/`picked` |
| `installer/app.py::run_uninstall`/`perform_uninstall` | `installer/daemon.py::clear_decided`/`bootout`/`remove_wrapper` | `daemon_policy.remove()` + composition-root marker clear | ✓ WIRED | Confirmed by direct read; matches REVIEW.md fix #4/#10 |
| `installer/helper_assets/prune_daemon_runner.py` | `PoliciesScreen._policy_detail`/`_log_tail` | shared log file path (`policy.log_path`) | ✓ WIRED | Wrapper writes the log the detail panel reads; `last_run_summary` parses the wrapper's own `=== ts ===` / `deleted: N` format |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes with claimed counts | `uv run pytest --cov` (via `rtk proxy` to bypass token-filtering) | `1486 passed, 1 skipped in 122.64s`, `Total coverage: 99.32%` (re-run after the Tier-3 fix below) | ✓ PASS — matches SUMMARY/REVIEW claims exactly, independently reproduced |
| `make validate` (ruff, format, pyright, bandit, vulture, shellcheck) | `make validate` | All checks passed, `0 errors, 0 warnings, 0 informations` (pyright) | ✓ PASS |
| Real end-to-end launchd registration and scheduled firing | Real `launchctl bootstrap`/`kickstart -k`/`bootout` against a disposable, uniquely-labeled test LaunchAgent (`com.tools-installer.tier3-verify-20260907`) built via the actual `installer.daemon.render_plist`/`write_plist`/`install_wrapper` production functions, pointed at scratch paths under `/tmp/tools-installer-tier3-verify/` (never the real `~/Library/LaunchAgents`/production label) | **Found and fixed a real, 100%-reproducing production bug** — see "Tier-3 Real-Machine Finding" below. Re-verified clean after the fix; the disposable LaunchAgent, wrapper, plist, and log were fully torn down (`launchctl bootout` + `rm -rf`) within minutes, leaving zero trace | ✓ PASS (after fix) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| REQ-launchd-prune-policy | 11-01, 11-02, 11-03, 11-04 | `daemon_policy` factory installs/removes a macOS-only LaunchAgent running the prune script daily, `--days 3` default | ✓ SATISFIED | Truths 1, 2, 3, 5 |
| REQ-daemon-log-diagnostics | 11-01, 11-03 | Single append-mode log with truncation; "last run" line + log-view keybinding in the detail panel | ✓ SATISFIED | Truth 4 |
| REQ-daemon-dependency-gating | 11-02 | `fd`/`rg` as soft `requires` (not `hard_requires`); degrades to the script's own fallback | ✓ SATISFIED | `daemon_policy(..., hard_requires=False)`; `test_policy_with_hard_requires_false_still_enables_when_requires_missing_with_recommended_copy` |

No orphaned requirements — all three REQ-IDs mapped to this phase in REQUIREMENTS.md are claimed by at least one plan.

Note: REQUIREMENTS.md's status column and ROADMAP.md's Phase 11 checkboxes / Progress table (`0/4, Not started`) are still stale relative to the actual shipped code (commit 7ceb950, plus the full 11-01..11-04 commit history already on this branch). This is a documentation-bookkeeping gap, not a code gap — every plan-level checkbox and the requirements-mapping table were evidently not updated as part of phase completion. Flagged as an info-level finding, not a blocker.

### Anti-Patterns Found

None. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/placeholder markers in any file touched by this phase (`installer/daemon.py`, `installer/policy.py`, `installer/app.py`, `installer/wizard_app.py`, `installer/uninstall.py`, `setup.py`, `installer/helper_assets/prune_daemon_runner.py`). The one incidental "not available" strings are pre-existing, legitimate UI copy for the `UNAVAILABLE` uninstall state, not debt markers.

### Dual-Lane Review Spot-Check (7ceb950)

Directly read (not trusted from 11-REVIEW.md's narrative) and confirmed present and correct:

- `daemon_policy._apply()` (installer/policy.py:427-477): the `try` now wraps `_validate_and_write` (which itself calls `install_wrapper`/`ensure_log_path`/`write_plist`) AND `daemon.bootstrap`, with a first-ever-apply rollback branch that removes the plist, wrapper, and log only if they didn't pre-exist. Matches the CR-01 fix claim.
- `daemon_policy._remove()` (installer/policy.py:479-504): retries the marker write once via `_record_decided_durably` on a manual disable. Matches the Codex Critical #1 fix claim.
- `wizard_app.py::action_pick_time`/`_time_picked` (lines 1230-1286): the `daemon_default_in_flight` guard is checked inside the `picked` closure (the actual mutation point), not only when the picker opens. Matches the CR-02 fix claim.
- `wizard_app.py::UninstallScreen._apply_removal` (lines 836-861): gated directly and unconditionally on `daemon_default_in_flight`, independent of `self.remove_tweaks` or `self._tweak_ids`. Matches the Codex Critical #2 fix claim.
- `installer/app.py::perform_uninstall` (lines 495-553): clears the "decided" marker for an already-inactive daemon even when `decision.remove_tweaks` is `False` (no tweaks row was ever offered). Matches the Codex Warning #10 fix claim, and is the one finding 11-REVIEW.md notes was verified against current source rather than assumed.
- `installer.daemon.WRAPPER_COMMAND` is now the single public source of truth, imported (not re-declared) by `installer/policy.py` as `_DAEMON_WRAPPER_COMMAND = daemon.WRAPPER_COMMAND`. Matches the WR-03 fix claim.
- `install_wrapper` (installer/daemon.py:313-334) writes through `_atomic_write` with `mode=0o755`. Matches the WR-01 fix claim.

All 7 claimed new regression tests were confirmed to exist by name in `tests/test_policy_daemon.py`/`tests/test_wizard_app.py`/`tests/test_app.py` via the commit diff and grep; the full suite passes independently (see Behavioral Spot-Checks).

### Tier-3 Real-Machine Finding (found and fixed during this verification)

**Test performed:** Built a real plist and wrapper via the actual production
`installer.daemon.render_plist`/`write_plist`/`install_wrapper` functions, using a
disposable, uniquely-labeled test LaunchAgent (`com.tools-installer.tier3-verify-20260907`,
never the real production label) pointed at scratch paths under
`/tmp/tools-installer-tier3-verify/`, with a stub `prune-user-tmpdir.sh` replacement (to avoid
any real deletion side effect while still exercising the real wrapper/launchd/uv chain). Ran
`launchctl bootstrap gui/$(id -u) <plist>` for real, then `launchctl kickstart -k` to force
immediate execution rather than waiting for the scheduled time.

**Bug found:** The wrapper crashed with `AttributeError: module 'datetime' has no attribute
'UTC'` on the real, launchd-triggered run — but not when invoked manually from an interactive
shell inside the repo. Root cause, isolated via `env -i HOME=... PATH=... TMPDIR=... uv run
--no-project --script <wrapper>` from different working directories: `uv run --no-project`
without an explicit Python version constraint resolves its interpreter partly by searching for a
`.venv` relative to the CALLER'S CURRENT WORKING DIRECTORY. From inside this repo (interactive
testing), it reuses the repo's own 3.14 venv; from any OTHER cwd — which is exactly what launchd
uses for a real scheduled job, never this repo's directory — it fell back to macOS's Command Line
Tools `python3` (3.9.6 on this machine), which predates `datetime.UTC` (added in Python 3.11).
This means **every single real scheduled run of the shipped code would have crashed**, 100% of
the time, in production — a defect the mocked-`Runner` test suite could not have caught by
construction, since it never actually invokes `uv run` for real.

**Fix applied:** Added a PEP 723 inline script metadata block (`# /// script` /
`requires-python = ">=3.11"` / `# ///`) to `installer/helper_assets/prune_daemon_runner.py`,
right after its shebang. This makes `uv run --script` honor the constraint regardless of the
caller's cwd, resolving a compliant interpreter from uv's own managed toolchain instead of
falling back to whatever system Python happens to be first on `PATH`. Re-verified via the exact
same disposable-LaunchAgent bootstrap+kickstart cycle: the real wrapper now runs to completion
and the log receives the expected `deleted: N` block. `make validate && make test` re-run clean
afterward (1486 passed, 1 skipped, 99.32% coverage — unchanged, since this fix touches only a
code comment/metadata block the existing mocked tests do not and cannot exercise).

**Cleanup:** `launchctl bootout gui/$(id -u)/com.tools-installer.tier3-verify-20260907` (exit 0,
confirmed absent via `launchctl print`), then `rm -rf /tmp/tools-installer-tier3-verify` and all
scratch log files. No trace of the disposable test LaunchAgent survives this machine.

### Gaps Summary

No gaps remain. All 6 derived observable truths (covering all 5 ROADMAP success criteria plus
the on-by-default "exactly once" guarantee) are backed by direct source reads and existing,
passing regression tests. `make validate` and `make test` were independently re-run and match
the claimed `1486 passed, 1 skipped, 99.32% coverage` exactly. The dual-lane review's 7 claimed
fixes in commit 7ceb950 were spot-checked against the actual current source and are all genuinely
present and correctly wired. The one item the initial pass routed to human verification (real
launchd registration and scheduled firing) was instead performed directly, per Rule 14's Tier-3
model, using a disposable test-scoped LaunchAgent — and caught a real, 100%-reproducing
production bug (the `uv run --script` cwd-dependent Python resolution above), which is now fixed
and re-verified. Status is upgraded from `human_needed` to `passed`.

A secondary, non-blocking observation remains: ROADMAP.md's Phase 11 plan checkboxes and
Progress table, and REQUIREMENTS.md's status column, were not updated to reflect the phase's
actual completion — a documentation-sync gap, not a code gap, to be closed as part of marking
the phase complete.

---

_Verified: 2026-09-07T07:28:57Z_
_Verifier: Claude (gsd-verifier)_
