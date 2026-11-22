---
phase: 34-daily-update-check-with-a-desktop-notification
verified: 2026-11-22T12:00:00Z
status: human_needed
score: 5/5 roadmap criteria verified by code and tests (real notification delivery, timer firing, real-Mac permission, real shallow clone and the owner decisions listed as human items)
covered_files:
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-09-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-09-SUMMARY.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-10-PLAN.md
  - .planning/phases/34-daily-update-check-with-a-desktop-notification/34-10-SUMMARY.md
  - installer/helper_assets/schedule_runner.py
  - installer/notify.py
  - installer/schedule_run.py
  - installer/schedules.py
  - installer/schedules_screen.py
  - installer/update_check.py
  - installer/version_cache.py
  - installer/version_status.py
  - scripts/container-e2e-verify.sh
  - setup.py
  - tests/test_notify.py
  - tests/test_update_check.py
  - tests/test_update_check_job.py
covered_digest: "v4:sha256:7f0cb3193b0b0ce170742ab71c1c8f450125565e5caf18b51c7c0b98935f1a85"
behavior_unverified: 4
overrides_applied: 0
gaps: []
behavior_unverified_items:
  - truth: "On Linux the runner calls notify-send with the session bus address passed to the child (SC3)"
    test: "On the real Bazzite session, trigger the check (or let the timer fire) with a changed outdated set"
    expected: "A desktop notification appears; the unit-launched runner's child saw the bus address"
    why_human: "Tests use fake notify-send and injected sockets; the container has no desktop session"
  - truth: "On macOS a failing or silently dropped osascript notification logs notify skipped without failing the run, and the row names the Script Editor permission (SC4)"
    test: "On the owner's Mac, run the check with a changed set before and after granting Script Editor notifications"
    expected: "Notification appears after the permission; before it, the run stays ok and the detail names the permission"
    why_human: "Real osascript and System Settings permission behavior (a silent drop exits 0 and cannot be detected)"
  - truth: "The daily timer fires the check on both OSes (login catch-up possibly late) (SC1 timer side)"
    test: "Owner observes the systemd user timer and the launchd agent firing at 09:00 on real hosts"
    expected: "One start and one ok line per firing; a login catch-up may precede the notification daemon"
    why_human: "No timer or unit may be installed here; the container proved the row, the result line and the Last cell only"
  - truth: "The self-update clause on a real shallow clone (SC5)"
    test: "Owner runs the check from a real shallow or partial clone of main behind origin"
    expected: "installer behind origin/main, or a fixed skip category (partial clone), never a pull"
    why_human: "Unit tests use injected git; the container workspace copy has no Git metadata (not a git checkout skip observed)"
human_verification:
  - test: "Real Bazzite notification: run the check with a changed outdated set on the desktop session and from the systemd user unit"
    expected: "A notification appears; the session bus address reaches notify-send from the unit on a real session"
    why_human: "Needs a real desktop session; tests and the container use fakes"
  - test: "Real-Mac osascript notification with the Script Editor permission, and a silently dropped one"
    expected: "Delivered after the one-time permission; a drop stays ok with the row detail naming the permission"
    why_human: "Real macOS behavior; osascript argv without -- is provisional"
  - test: "The daily timer fires on Bazzite (systemd user timer) and macOS (launchd), including the login catch-up lateness"
    expected: "One start and ok pair per firing; a catch-up before the notification daemon can arrive a day late"
    why_human: "No timer, unit or plist may be installed from this verification"
  - test: "Self-check on a real shallow clone (and a real behind-origin checkout)"
    expected: "Fixed skip category or the installer behind origin/main clause; the checkout is unchanged"
    why_human: "Unit tests inject git; the container copy has no Git metadata"
  - test: "Owner confirmation of the provisional decisions: the 34-0N-SUMMARY.md lines, the eighth row and table height 9, the osascript argv without --, the bus address scope (runner-only, check child only), the self-update skip rules (detached HEAD, non-main, not worktree root, partial clone), a shrinking non-empty set notifying again, the daily limit as timer cadence, the SPEC and ROADMAP amendments, proxy values carried as for every row, uv and manager scratch writes accepted, the confirmed-only membership rule, brew under-reporting (no brew update)"
    expected: "Each confirmed, or reopened as a follow-up"
    why_human: "Flagged provisional or needs confirmation in the 34-01..10 summaries, the review triage and the SPEC and ROADMAP amendments"
---

# Phase 34: Daily update check with a desktop notification - Verification Report

**Phase Goal:** A user learns that installed tools (and tools-installer itself) have updates without opening the TUI, from a desktop notification the daily timer sends when the set of outdated tools changes (at most one per timer firing; no date is stored), on Bazzite and macOS (amended 2026-11-21).
**Verified:** 2026-11-22
**Status:** human_needed
**Re-verification:** No, initial verification (after the review fix round, last commit `74feb6b0`)

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP criteria, as amended) | Status | Evidence |
| - | ------------------------------------ | ------ | -------- |
| 1 | `--run-schedule check-updates` refreshes past the 7-day cache, prints one `ok: N updates available` line, changes no tool (NOTIFY-01, NOTIFY-02) | VERIFIED in code, timer firing HUMAN | `schedules.py:97` is the eighth row (`CHECK_UPDATES`, `daily=True`, 24h, 09:00); `runner_argv` builds the `check-updates` job (`schedules.py:873`); `schedule_run.run_schedule` dispatches by kind through the lock branches to `update_check.run_check`; `update_check.CHECK_STALE_AFTER` is 20 h, passed as `stale_after=` to `refresh.refresh` (overrides the 7-day window); `result_line` builds `ok: N updates available` capped at 300 chars; no install/update code is reachable from `run_check` (read the module). Real container: orchestrator ran `schedules` after the fix round, PASS (`TRACER_SCHEDULE_RESULT ... ok: 0 updates available; installer check skipped: not a git checkout`, `CHECKOUT_UNCHANGED`, cell, OFF, teardown; see `34-07-SUMMARY.md` and `34-REVIEW-FIX.md`). Timer firing on real hosts is a human item. |
| 2 | Two runs with the same outdated set send one notification; a changed set sends another (NOTIFY-03) | VERIFIED | `run_check` notifies only when `not healthy or ids != prior`, notifies before `write_notified` and stores only after success; `next_set` keeps unknown membership, confirms only on fresh stamps from this pass (`fresh_ids`), drops uninstalled ids; an empty set resets silently. `tests/test_update_check.py` and `tests/test_update_check_job.py` use a fake notifier and pass. A shrinking non-empty set notifies again (provisional). |
| 3 | On Linux the runner calls `notify-send` with the session bus address passed to the child; no `notify-send` logs `notify skipped`, exit ok (NOTIFY-04) | VERIFIED in code, delivery HUMAN | `notify.notify_send` returns `notify-send not found` when absent (the `run_check` clause becomes `notify skipped: ...`, return code 0); `session_bus_environment` keeps an existing address or derives `unix:path=` (percent-encoded) from `XDG_RUNTIME_DIR/bus` then `/run/user/<uid>/bus` only when the path is a socket; `schedule_runner._update` forwards only `DBUS_SESSION_BUS_ADDRESS` and `PYTHONDONTWRITEBYTECODE=1` to the check child (`readonly=True`), never into a unit; tests assert the bus key is not a unit environment key. Real session delivery is a human item. |
| 4 | On macOS a failing `osascript display notification` logs `notify skipped` without failing the run; the row detail names the one-time permission (NOTIFY-05) | VERIFIED in code, real Mac HUMAN | `notify.osascript` returns fixed reasons by exit code (never stderr or argv); constant AppleScript with data passed as argv items; `schedules_screen.py` row detail carries the Script Editor permission first (`_CHECK_NOTIFIER_*`, `_CHECK_LIMITS_SHORT`); layout tests at 80x20 and 120x40 pass. A silently dropped notification exits 0 and cannot be detected (documented limit, human item). |
| 5 | A checkout on `main` behind `origin/main` adds the clause `installer behind origin/main`, joining the set as `tools-installer`, read from `git ls-remote`; checkout unchanged; detached HEAD or another branch skipped (NOTIFY-06) | VERIFIED in code with injected git, real clone HUMAN | `update_check.installer_behind` uses only `symbolic-ref`, `rev-parse`, `ls-remote`, `config --get-regexp`, `cat-file -e`, `merge-base --is-ancestor` (no fetch, pull or API); branch compared as the full ref `refs/heads/main`; detached or other branch returns `(None, None)` (silent skip); not-root and partial clone fixed categories; production runner `git_for_check` disables credential helpers, askpass, cookies, extra headers and lazy fetch; `run_check` adds the clause and `INSTALLER_ID` to the set. Container: `not a git checkout` skip observed, checkout unchanged. |

**Score:** 5/5 truths verified by code and tests; 4 (timer firing, real notification delivery on both OSes, real shallow clone) are present and wired but not exercised on real hosts and are listed as behavior-unverified and routed to the owner.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `installer/notify.py` | `Notifier` seam, argv builders, bus rule | VERIFIED | 143 lines, substantive, no debt markers |
| `installer/update_check.py` | self-check, notified set, `run_check` | VERIFIED | 391 lines |
| `installer/schedules.py` | `JobKind.CHECK_UPDATES`, `Schedule.daily`, eighth row, runner argv | VERIFIED | lines 41, 52, 97, 873 |
| `installer/schedule_run.py` | dispatch by kind, `_check` | VERIFIED | lines 128-155 |
| `installer/helper_assets/schedule_runner.py` | `check-updates` job via `--frozen` child | VERIFIED | `readonly=True`, closed stdin (`DEVNULL`), only the bus address forwarded |
| `installer/version_cache.py`, `version_status.py` | `stale_after`, failure sink, `outdated_ids`, per-manager stamps | VERIFIED | used by `update_check` imports |
| `installer/schedules_screen.py` | row detail with permission and limits | VERIFIED | tested |
| `setup.py` | `notifier_for(platform.os)`, `refresh`, `git_for_check` wired into `RunDeps` | VERIFIED | lines 546-548 |
| `scripts/container-e2e-verify.sh` | check-updates in the `schedules` target | VERIFIED | lines 2669, 2808, 2865; real run PASS |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| Timer unit | runner `check-updates` | `schedules.runner_argv` | WIRED |
| Runner | `setup.py --run-schedule check-updates` | `_update(..., readonly=True)` | WIRED |
| `run_schedule` | `update_check.run_check` | `_run_unlocked` -> `_check` | WIRED |
| `run_check` | `refresh.refresh(stale_after=20h)` | `Refresher` protocol | WIRED |
| `run_check` | `Notifier` | `RunDeps.notify` from `notifier_for` | WIRED |
| `run_check` | notified set `update-check.json` | `schedules.notified_path`, `atomic_replace_entry` | WIRED |
| `run_check` | `installer_behind` | injected `git_for_check` | WIRED |

### Data-Flow Trace (Level 4)

Outdated ids flow from the real `VersionRefreshService` states (`outdated_ids(states) & fresh`) into the message and the notified set. `fresh` derives from stamps written by this pass (pass cache and manager snapshot), not a later disk read (review lane 2 fix). Status FLOWING (live registry lookups not traced here).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| notify and update-check tests | `uv run pytest tests/test_notify.py tests/test_update_check.py tests/test_update_check_job.py tests/test_update_check_contract.py --no-cov -q -n 4`, scratch TMPDIR | all passed, 0 failed | PASS |
| cache, status, runner, engine, view, container-host tests | `uv run pytest tests/test_version_cache.py tests/test_version_status.py tests/test_schedule_runner.py tests/test_schedules_engine.py tests/test_schedules_view.py tests/test_container_e2e_schedules.py --no-cov -q -n 4`, scratch TMPDIR | all dots, no failure shown (summary line was cut by my tail) | PASS |
| Token variables never reach the child | `tests/test_schedule_runner.py` (`test_child_env_never_passes_the_github_token_variables`), `tests/test_update_check_job.py` plants tokens | in the passing runs above | PASS |
| Real container `schedules` check | orchestrator-run, final harness after the fix round | PASS (recorded, not re-run here) | PASS (recorded) |
| Full suite | `make test` by orchestrator after last commit: 9410 passed, 6 skipped, 96.44% | not re-run here | RECORDED |
| Debt markers | grep TBD/FIXME/XXX in `notify.py`, `update_check.py`, `schedule_run.py`, `schedule_runner.py`, `version_cache.py` | none | PASS |

### Probe Execution

SKIPPED: no `probe-*.sh` declared. No make target, container, timer, unit, notification or remote write was run in this verification; scratch TMPDIR removed.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| NOTIFY-01 | Daily row, headless `--run-schedule`, one `ok: N updates available` line, no tool changed | SATISFIED in code; timer HUMAN | Truth 1 |
| NOTIFY-02 | Refresh despite 7-day staleness | SATISFIED | `CHECK_STALE_AFTER` 20 h via `stale_after` |
| NOTIFY-03 | Notify only on a changed set | SATISFIED | Truth 2 |
| NOTIFY-04 | `notify-send` with bus address; missing logs `notify skipped` | SATISFIED in code; real session HUMAN | Truth 3 |
| NOTIFY-05 | `osascript`; failure skips; permission named; real Mac UAT | SATISFIED in code; real Mac HUMAN | Truth 4 |
| NOTIFY-06 | `git ls-remote` self-check, no API, no pull | SATISFIED in code; real clone HUMAN | Truth 5 |

No orphaned requirements. REQUIREMENTS.md still reads Pending and the ROADMAP checkbox is unchecked; `phase.complete` is the orchestrator's after the human items.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `installer/update_check.py` | docstring | A persistent notified-set save failure re-notifies each run | Info (accepted IN-02, now a result clause) | backlog 999.34 |
| `installer/update_check.py` | `failed_reason` | `del exc`, constant text | Info | deliberate: no raw exception text in the log |
| review lanes 11-13 | n/a | midnight clock read, joined-refresh keying, manual route stdin | Info (deferred) | backlog 999.34 |
| `34-SECURITY.md` | n/a | AR-34-01..04 accepted (git config, uv/manager scratch writes, proxy values, bus scope) | Info | SECURED 23/23, 0 open |

No TBD, FIXME or XXX in phase code. No blockers.

### Human Verification Required

See the front matter list (5 items): real Bazzite notification and bus address, real-Mac osascript with permission, timer firing on both OSes, real shallow clone self-check, and the owner confirmation of the provisional decisions below.

#### Provisional decisions awaiting owner confirmation

From the 34-01..10 summaries ("Provisional decisions"), the review triage and the amendments: the eighth row, `Schedule.daily` and 09:00 (D-02 to D-07), table `max-height: 9`; D-14 notified-set file; osascript argv without `--` (D-18); the bus address runner-only and check-child-only (decision 3, WR-04); the self-update skip rules (decision 5, H4); a shrinking non-empty set notifying again (decision 6); the daily limit as timer cadence and a changed non-empty set triggering on any run; the SPEC and ROADMAP amendments (decision 10); proxy values carried as for every row; uv and manager scratch writes accepted (narrowed write boundary); the confirmed-only membership rule; brew under-reporting because no `brew update` (decision 7); login catch-up lateness (decision 11); the container proving the row but not the bus variable or delivery (decision 9).

### Gaps Summary

No gaps. Every roadmap criterion is backed by code, passing file-level tests, the recorded full suite and the real `schedules` container run on the final harness. Status is `human_needed` because real notification delivery on both desktops, timer firing, the real-Mac permission and the real shallow clone cannot be proved here, and the provisional decisions need the owner. Residual risk: the second spot-check batch showed no failure but its summary line was not captured; the full suite and Python 3.15 were not re-run here.

---

_Verified: 2026-11-22_
_Verifier: Claude (gsd-verifier)_
