# Phase 34: Daily update check with a desktop notification - Research

**Researched:** 2026-11-21
**Domain:** Python stdlib scheduling engine (systemd user timers / launchd agents), headless version refresh, desktop notification argv (libnotify `notify-send`, macOS `osascript`), read-only `git ls-remote`
**Confidence:** HIGH for the code reconciliation and the Linux mechanics (read or run this session); MEDIUM for GitHub limits; LOW for macOS attribution and permission behaviour (forum reports only, deferred to the owner's Mac)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**6 requirements are locked via SPEC.md** (`34-SPEC.md`; NOTIFY-01..NOTIFY-06). *Amended 2026-11-19 (34 D-20, D-21):* the extra clauses ride in the one result line, and tests that list every schedule row gain one entry. Out of scope: failed-run notifications; a click action; a token in the unit; updating any tool; real-Mac checks.

#### The row
- **D-01: The 24.2 amendment is already written** into `24.2-SPEC.md:179` and `24.2-CONTEXT.md:43` (this phase's SPEC commit); nothing else to edit there.
- **D-02: `JobKind.CHECK_UPDATES = "check-updates"`** and `Schedule("check-updates", "update check", JobKind.CHECK_UPDATES, None, 24, "09:00")` appended as the last row of `SCHEDULES` (`installer/schedules.py:37-41,71-93`); `UPDATE_SCHEDULE_IDS` filters by kind and does not change *(amended 2026-11-19, 35 D-02: `installer/cli.py:56-62` builds the `--run-schedule` choices from it, so 34 must widen the choices for `check-updates`)*. Appending keeps the other rows' ids and order (positional view tests at `tests/test_schedules_view.py:105,240`).
- **D-03: The unit and plist need no new template.** The generic path (`basename_for`, `label_for`, `render_exec_service`, `render_timer(on_calendar=...)`, `render_agent_plist`) writes `tools-installer-schedule-check-updates.{service,timer}` and `com.tools-installer.schedule.check-updates.plist`. Only `runner_argv` (`schedules.py:853-888`, where an unknown kind falls into tmp-cleanup's argv) gets a new branch, and the runner gets a job `check-updates --installer CHECKOUT --uv UV` that reuses `_update(run_id, installer, uv)` (`installer/helper_assets/schedule_runner.py:320-358,454-474,511-515`); its timeout message must not say "the update timed out". Existing rows' unit text does not change, so `_is_stale` rewrites nothing.
- **D-04: `run_schedule` dispatches by kind** (`installer/schedule_run.py:127-148`): UPDATE to `_run_unlocked`, CHECK_UPDATES to a new check function, TMP and CACHE keep the exact refusal text `failed: tmp-cleanup is not an update schedule` (`tests/test_schedule_update.py:180-187`). The check takes the same lock branch as the update rows (manual run: `try_acquire`, a held lock gives `skipped: busy`; under the runner: `parent_holds_lock`).
- **D-05: The row is on by default** through the generic reconcile (`_row_action` turns on when `decided is None`, gated by `manager_reachable`; `schedules.py:1548-1562,1699-1721`), as `cache-cleanup` does; `row_state` gates on presence only for UPDATE (`:1488-1492`). The owner asked for a daily check that leaves a notification, and 24.2 D-09 makes built-in rows default on. **Own reasoning** (jev first rung none_of_these 0.86 contradicted the evidence; second opinion off_by_default low 0.51). Ledger.
- **D-06: The row is daily-only:** a `daily: bool = False` field on `Schedule` (True for tmp-cleanup and check-updates) replaces the seven hard-coded "tmp cleanup is daily" checks (`schedules.py:847-850,1412-1415`; `installer/schedules_screen.py:384,395-396,501-502,577,717`); the time editor hides the interval for both. No test constructs `Schedule(` directly. jev fixed_daily 0.99 (TypeSafe).
- **D-07: The default start is 09:00,** off the 00:00/06:00/12:00/18:00 update grid so it does not wait behind them; Linux `Persistent=true` and macOS wake coalescing catch up missed runs (24.2 D-05). **Own reasoning** (jev midnight low 0.67; TypeSafe low). Ledger.
- **D-08: The row detail** names the notifier and, on macOS, the one-time permission ("notifications come from Script Editor: allow them once in System Settings > Notifications"); `what` and `_target` in `schedules_screen.py:430-482` get a branch for the new kind (the target reads "installed", not cache-cleanup's managers list); the `runs:` line already prints `check-updates` (`:480`).

#### Refresh and the outdated set
- **D-09: A `stale_after` keyword threaded from `VersionRefreshService.refresh(tools, *, stale_after=STALE_AFTER)` through `_pass`, `resolve_status`, `_latest_status` into `should_fetch`/`is_stale`;** the check passes about 20 h. Never shift `now`: `_parse_iso` rejects stamps more than 5 min in the future (`version_cache.py:70-92`). A window under 24 h meets every SPEC boundary and avoids refetching what the TUI fetched an hour earlier; `RETRY_BACKOFF` (6 h) stays shorter than the interval. The freshness gates are `version_cache.py:216-231` (`STALE_AFTER` at :44), called at `version_status.py:389,416-419,1877`. jev: first answer `keep the 7-day window` (TypeSafe 0.94) contradicts SPEC R2, so the evidence decides: **jev overridden**.
- **D-10: `refresh` receives its tools sorted oldest-`checked_at` first** (missing first), because the 20-fetch cap is spent in iteration order (`version_status.py:1855-1866,1961-1962`). **Own reasoning** (jev low 0.55 / 0.65). Ledger.
- **D-11: Lookups stay anonymous by construction:** `urlopen_fetch` adds a token only from `GITHUB_TOKEN`/`GH_TOKEN` (`installer/versions.py:358-373`), and neither reaches the child (`daemon.ENVIRONMENT_KEYS` `daemon.py:34-47`; runner `_PASSED_ENV` `schedule_runner.py:82-97`).
- **D-12: A rate-limited fetch surfaces like any failed fetch** (`HTTPError` to `VersionError`, stamped `failed_at`, `versions.py:396-409`; `version_status.py:400-412`); the service gains an optional error sink and the line gets `; N lookups failed: <first reason>`; exit stays 0. **Own reasoning** (jev low 0.68 / 0.58). Ledger.
- **D-13: The outdated set is a pure function `outdated_ids(states) -> frozenset[str]`** keeping present tools whose `state.version.outdated is True` (`version_status.py:1019-1043`); it does not read `Health.OUTDATED` (health ranks broken and misconfigured above outdated, `:271-304`); `None` never counts; manager-owned tools arrive through `OutdatedReport` inside `resolve_status` (`manager_versions.py:40-51`). Phase 35 reuses it; its name and signature are a contract.

#### The changed-set rule
- **D-14: The notified set lives in its own file** `~/.local/state/tools-installer/update-check.json`, derived from `ctx.state_path.with_name(...)` so a scratch HOME works: `{"version":1,"notified":[sorted ids]}`, written with `installer.atomic.atomic_write_text`, read with `read_capped(..., follow_symlinks=False)`; any decode problem counts as empty and is rewritten; the path joins `_state_artifacts` so the last-off cleanup and the uninstall sweep delete it (`schedules.py:1803-1853`). Verified: `schedules.json` has a closed key set (`_TOP_KEYS`, :255) and sticky damage that stops every reconcile from turning anything on (`:1510-1512`, `:1692-1706`). jev key_in_schedules_file 0.82 twice (TypeSafe, first and second opinion) contradicts that evidence; **jev overridden**.
- **D-15: Notify then store the set only if the notification succeeded;** unchanged does nothing; empty stores empty and never notifies; members are tool ids without versions. Note: a shrinking non-empty set (`{a,b}` to `{a}`) counts as changed under the SPEC wording and notifies again; reported, not re-decided. jev store_only_after_success low 0.61 (second opinion). **Own reasoning**, ledger.

#### Notifiers
- **D-16: `installer/notify.py`** holds `Notifier = Callable[[str, str], str | None]` (summary, body; None on success or a skip reason), `notify_send(...)`, `osascript(...)` and `notifier_for(platform_os, which, run)`; children use the house runner style (stdin DEVNULL, `new_session=False` so the runner's group kill reaches them, short timeout; `installer/run.py:103-127,184-191`). The check appends `; notify skipped: <reason>`. A notifier inside the stdlib runner would sit where `installer` cannot be imported (`schedule_runner.py:26-29`). jev main_package_module 0.82 (TypeSafe).
- **D-17: Linux argv** `[notify-send, "--app-name=tools-installer", "--urgency=normal", "--", summary, body]`, no `--transient`; `notify-send` found with `which` on the unit's clean PATH. The bus address: add `DBUS_SESSION_BUS_ADDRESS` to the runner's `_PASSED_ENV` (the user manager carries `unix:path=/run/user/1000/bus` on this host; the runner strips it today), else derive `unix:path=$XDG_RUNTIME_DIR/bus` or `/run/user/<uid>/bus` when that socket exists, else leave it unset, never empty; never bake it into the unit (24.2 D-10 F4 bans `/run/user/*` in unit text, `systemd_daemon.py:207-211`). **Own reasoning** (jev none_of_these 0.91 contradicted the evidence; second opinion derive_only low 0.77). Ledger.
- **D-18: macOS argv** `["osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", "--", title, body]`: tool names reach AppleScript as data, never source text. A non-zero exit, timeout or missing binary gives `notify skipped`; the golden argv test runs on both OSes; whether osascript passes trailing args to `on run argv` is a Mac UAT item. **Own reasoning** (jev none_of_these 0.73 contradicted the evidence; second opinion separate_arguments low 0.52). Ledger.

#### The self-check
- **D-19: The checkout is `deps.context.checkout`** (`setup.py:539-543`, the runner's `--installer`/`cwd`). Run `git -C <checkout> rev-parse HEAD`, then `git -C <checkout> ls-remote origin refs/heads/main` (a full ref), with run_git_isolated's environment (no prompts, askpass or hooks; `installer/run.py:157-171`) plus `GIT_SSH_COMMAND="ssh -o BatchMode=yes"`, stdin DEVNULL, in the caller's group, about 20 s (run_git_isolated's 600 s and new session are wrong for a timer child). It runs after the refresh and before the notify step, so the installer joins the set as `tools-installer`. A non-git directory, missing git, or an unreachable or auth-failing remote appends `; installer check skipped: <reason>`. This dev checkout's `origin` is SSH and the runner strips `SSH_AUTH_SOCK`, so here it will usually skip; the README clones over HTTPS, so end users read anonymously. **Own reasoning** (jev none_of_these 0.97 contradicted the evidence; second opinion public_https_address low 0.51). Ledger.
- **D-20: "Behind" means the remote main differs from HEAD and is not already an ancestor of HEAD** when its object exists locally (`cat-file -e`, then `merge-base --is-ancestor`); an unknown remote commit means new commits upstream; no fetch, no pull. **Own reasoning** (jev low 0.48 / 0.67). Ledger.

#### Log line and tests
- **D-21: One result line carries everything.** `setup.py --run-schedule` only prints; the runner writes `start` plus the child's last line starting `ok:`/`skipped:`/`failed:` (`schedule_runner.py:345-358,510-522`; `setup.py:547-561`), so separate `notify skipped` or self-update lines would be discarded. The extras are `; ` clauses of the one `ok: N updates available` line, as the update rows already do (`schedule_run.py:61-62`, `schedules.py:495-496`). R1's log acceptance is tested through `schedule_runner.main([...])`, not a bare `--run-schedule`. SPEC R1, R4-R6 amended.
- **D-22: The SPEC's "existing schedule tests unedited" is read as "assertions about the other rows stay".** Tests that list every row gain one entry: `tests/test_schedules.py:105-140` (ids, labels, targets), `tests/test_schedules_view.py:240-248`, and because the row is on by default `tests/test_schedules_lifecycle.py:103,107,152` and `tests/test_schedules_handover.py:493` (`turned_on` tuples). Unchanged: `tests/test_schedule_update.py:180`, `tests/test_container_e2e_schedules.py:174` (derived from `SCHEDULES`), runner tests while `_PASSED_ENV` only grows.
- **D-23: New tests** (scratch HOME, fakes only): `run_schedule("check-updates", ...)` with a spy `UpdateService` (zero calls); `schedule_runner.main` log with exactly `start` and one `ok:` line; cache aged 1 day and 7 days -1 s/0/+1 s with 20 and 21 eligible tools; set rules (same, changed, emptied, corrupt) with a fake `Notifier`; a fake `notify-send` recording argv and `DBUS_SESSION_BUS_ADDRESS`, and a missing binary; a golden osascript argv with `"`, `\` and non-ASCII names plus a failing fake; a fixture bare repo whose main is ahead (byte-compare of the checkout), non-git and unreachable cases; a held lock giving `skipped: busy`; unit-template tests (`runner_argv` branch, plist `ProgramArguments`, OnCalendar `*-*-* 09:00:00`); a token grep over the unit, state file and log. Seams: `VersionRefreshService(resolve_tag=..., now=...)` (`version_status.py:1193-1222`).
- **D-24: The SPEC R2 concurrency backstop is restated:** the TUI's view-entry refresh takes no run lock (only mutations do, 24.2 D-12); two refreshing processes are last-writer-wins with at worst one entry lost and the file never corrupted (`version_status.py:17-24`); healed by the next refresh.

### Claude's Discretion
- Notification summary and body wording, the exact `; ` clause text, and the helper names in `notify.py`.

### Deferred Ideas (OUT OF SCOPE)
- To confirm (UAT or planning): whether `osascript -e ... -- a b` passes trailing args to `on run argv` on current macOS and whether a LaunchAgent notification attributes to Script Editor; whether `brew outdated` with `HOMEBREW_NO_AUTO_UPDATE=1` sees new formula versions without `brew update`; whether the GitHub repo is public (HTTPS `ls-remote`); whether notify-send falls back to `$XDG_RUNTIME_DIR/bus` without it.
- Reviewed todos (not folded): none other matched.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTIFY-01 | Daily `check-updates` row, headless through `--run-schedule`, one `ok: N updates available` line, no tool changed | Engine map and touch list (Architecture, CONTEXT Reconciliation); runner job table `schedule_runner.py:432-475,503-520`; dispatch `schedule_run.py:127-148` |
| NOTIFY-02 | Refresh despite the 7-day cache window | `stale_after` plumbing sites listed (Standard Stack / Pattern 2); 20-fetch cap, `RETRY_BACKOFF`, GitHub 60/h analysis; the wrapped-resolver digest pitfall |
| NOTIFY-03 | Notify only when the outdated set changed | `outdated_ids` health analysis; notified-set file mechanics (atomic, corrupt, failure-not-stored); D-15 shrink ambiguity |
| NOTIFY-04 | Linux `notify-send` with the session bus address; absent binary logs `notify skipped`, exit ok | Verified argv behaviour (`--`, exit 1, error texts, GLib fallback); user-manager environment fact; `_PASSED_ENV` change |
| NOTIFY-05 | macOS `osascript display notification`, failure logs `notify skipped`, row detail names the permission, real-Mac check deferred | Argv shape and injection safety; attribution and silent-drop caveats (LOW confidence); UAT lines |
| NOTIFY-06 | Self-check: `git ls-remote origin main` vs HEAD, one self-update clause, no pull | Experiment results (read-only, shallow clones, missing ref, unreachable); `run_output` seams; install.sh shallow-clone consequence |
</phase_requirements>

## Summary

The phase is almost entirely additive on top of an engine that phases 27 to 33 left untouched: `schedules.py`, `schedule_run.py`, `schedule_runner.py`, `versions.py`, `version_cache.py`, `daemon.py` and `schedules_screen.py` still match the line numbers CONTEXT cites to within a line or two. Drift exists only in `version_status.py` (+1 to +14 lines) and `installer/run.py` (+12 to +26 lines), and the cited `systemd_daemon.py:207-211` is the wrong place for the "no `/run/user/*` in unit text" rule (see `## CONTEXT Reconciliation`). No locked decision is contradicted by the code. Four gaps in CONTEXT matter for planning: (1) the Schedules table CSS caps the table at 8 lines, which exactly fits header plus 7 rows, so an 8th row scrolls and breaks a layout test CONTEXT D-22 does not list; (2) the D-12 "error sink" cannot be done by wrapping `resolve_tag`, because the wrapper silently drops asset digests from the saved cache entry; (3) the tests inherit the developer's `DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR` and a real `/usr/bin/notify-send`, so every notifier test must inject `which` and `run` and clear those variables; (4) `RunDeps` is built positionally in a test, so any new field needs a default.

Linux mechanics were exercised on this host without sending any notification. `notify-send` 0.8.9 accepts `--` and exits 1 with a one-line stderr on every failure, GLib itself falls back to `$XDG_RUNTIME_DIR/bus` when `DBUS_SESSION_BUS_ADDRESS` is unset, and the systemd user manager exports `DBUS_SESSION_BUS_ADDRESS` (set by `dbus.socket`'s `ExecStartPost`) which the runner then strips because `_PASSED_ENV` omits it. That makes D-17 correct and necessary. `git ls-remote origin refs/heads/main` was proven read-only (checkout byte-identical), exits 0 with empty output for a missing ref, 128 when unreachable; the repository is public (`gh api` reports `private: false`), so HTTPS `ls-remote` works anonymously, but `install.sh` makes a `--depth 1` clone, which the D-20 "object exists locally" branch must tolerate.

macOS behaviour remains unverifiable here. Sources agree that `osascript` notifications are attributed to the launching app (Script Editor for a launchd job) and that nothing appears until the user enables that app once; at least one report says `osascript` still exits 0 when nothing is shown, so a "failed notification" cannot be detected in that case and the one-line row detail is the only mitigation.

**Primary recommendation:** Implement CONTEXT D-01..D-24 as locked, in three waves (engine row and `daily` flag; notifier + outdated set + notified-set file + refresh plumbing; self-check + UI text + tests), put the check logic in a new `installer/update_check.py` so `schedule_run.run_schedule` stays a thin dispatcher, keep every notifier test hermetic by injecting `which`/`run`, and treat the macOS items as owner UAT lines only.

## Architectural Responsibility Map

This is a local CLI/TUI product; "tiers" map to the processes involved.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Timer firing (OnCalendar 09:00, `Persistent=true`; launchd `StartCalendarInterval`) | OS service manager (systemd user / launchd `gui/<uid>`) | `installer/schedules.py` engine writes the unit | Generic path already renders it; no new template (D-03) |
| Locking, log line, timeout, group kill | `helper_assets/schedule_runner.py` (stdlib only, cannot import `installer`) | — | Same runner as every row; `_update` already folds the child's last `ok:/skipped:/failed:` line |
| Version refresh, outdated set, notified set, notify call, self-check | `installer/` package (child `uv run setup.py --run-schedule check-updates`) | `setup.py` wiring (`_schedule_run_deps`) | Decision code belongs in `installer/` (architecture rule 4); the runner cannot import it |
| Desktop notification delivery | Session notification daemon (KDE/GNOME `org.freedesktop.Notifications`; macOS Notification Center) | `notify-send` / `osascript` child | The installer only builds argv and reads the exit status |
| Schedules view row, detail text, time editor | `installer/schedules_screen.py` | `installer/schedules.py` (`Schedule.daily`) | One view registry; a new row is a table row, not a new view |
| Persistent state (versions cache, notified set) | Local files under `~/.local/state/tools-installer/` | — | `atomic_write_text`, same dir on both OSes (`default_state_path`) |

## Standard Stack

Stdlib only; no new package. Everything reuses in-repo modules.

### Core
| Library / module | Version | Purpose | Why standard |
|------------------|---------|---------|--------------|
| `installer.run.run_output` | in-repo (`run.py:154`) | The only way `installer/` spawns a child (`subprocess` is imported only in `run.py` and `install_ownership.py`); has `timeout`, `env`, `new_session` | Keeps bandit quiet, gives CommandError mapping, injectable |
| `installer.atomic.atomic_write_text`, `read_capped` | in-repo (`atomic.py:76,186`) | Notified-set file write and read | The one sibling-temp-plus-`os.replace` writer; `read_capped(path, cap, follow_symlinks=False)` returns None for non-regular files and raises OSError when missing |
| `installer.version_status.VersionRefreshService` | in-repo (`version_status.py:1204`) | The refresh pass, `state_of` | Already the shared service; `setup._schedule_run_deps` already builds it |
| `installer.runlock` | in-repo | Run lock for a manual run | Same as the update rows (`schedule_run.py:136-148`) |
| `installer.sanitize.sanitize_log_line` | in-repo | One-line sanitising of reasons before they join the result line | Already used by `schedule_run._first_line` |
| `shutil.which`, `os`, `json`, `dataclasses`, `datetime` | stdlib | Locating binaries, parsing | — |

### Supporting
| Item | Purpose | When to use |
|------|---------|-------------|
| `git` (host binary) | `rev-parse`, `ls-remote`, `cat-file -e`, `merge-base --is-ancestor` | Self-check only |
| `notify-send` (libnotify 0.8.9 on this host, `/usr/bin/notify-send`) | Linux delivery | Found with `which` on the unit PATH; never installed by us |
| `osascript` (`/usr/bin/osascript` on macOS) | macOS delivery | Same |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Wrap `resolve_tag` to collect error text (D-12) | A sink threaded into `_latest_status` | Wrapping breaks `release_resolver`'s identity check (`resolve_tag is resolve_github_tag`) and the saved cache entry loses its asset digests (Pitfall 2). Thread the sink. |
| `gdbus call ... Notify` fallback when `notify-send` is missing | — | Out of scope (CONTEXT locks `notify-send`); the research file notes it unverified without libnotify |
| `terminal-notifier` on macOS | — | New dependency; research file rejects it |

**Installation:** none.

**Version verification:** no packages added. Host facts: `notify-send --version` prints `notify-send 0.8.9`; `systemd 262 (262.1-1.fc45)`; `git` at `/usr/bin/git` [VERIFIED: ran on this host, 2026-11-21].

## Package Legitimacy Audit

No external package is installed by this phase (stdlib plus in-repo modules, host binaries `git`, `notify-send`, `osascript`). Audit not applicable.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
 systemd user timer (OnCalendar=*-*-* 09:00:00, Persistent=true)   |  launchd gui/<uid> StartCalendarInterval 09:00
        |                                                          |
        v                                                          v
 unit ExecStart: uv run --no-cache --no-project --script <data_dir>/runner.py
                 check-updates --installer <checkout> --uv <uv> --log L --lock K --cap-bytes N
        |      (unit Environment: PATH HOME TMPDIR + proxy/cert passthrough; NO DBUS, NO token)
        v
 schedule_runner.main  --parse job--> _locked_run: run lock (wait/skip busy) -> emit "start"
        |
        v   _run_child(uv run --isolated --no-dev setup.py --run-schedule check-updates
        |                --parent-holds-run-lock), env = _child_env(_PASSED_ENV + CHILD_ENV)
        v
 setup._run_schedule -> run_schedule(id, deps, parent_holds_lock=True)
        |  kind CHECK_UPDATES                       (kind UPDATE -> _run_unlocked; TMP/CACHE -> failed ... not an update schedule)
        v
 update_check.run_check(deps)
   1. tools sorted oldest checked_at first  (load_version_cache)
   2. refresh.refresh(tools, stale_after=~20h, on_failure=sink)   -> GitHub/npm lookups (anonymous, <=20), manager snapshot, versions.json written
   3. ids = outdated_ids(state_of(t.id) ...)                      (present and version.outdated is True)
   4. self-check: git rev-parse HEAD ; git ls-remote origin refs/heads/main ; [cat-file -e ; merge-base --is-ancestor]  -> adds "tools-installer"
   5. compare with update-check.json  --unchanged/empty--> no notification
        | changed
        v
   notifier_for(os, which, run)(summary, body)
      Linux : notify-send --app-name=tools-installer --urgency=normal -- SUMMARY BODY   env DBUS_SESSION_BUS_ADDRESS (passed, or derived, else unset)
      macOS : osascript -e 'on run argv' -e '...' -e 'end run' -- TITLE BODY
        | None = ok -> store set (atomic)        | reason -> "; notify skipped: <reason>", set NOT stored
        v
   prints ONE line: "ok: N updates available[; X lookups failed: R][; installer check skipped: R][; notify skipped: R]"   exit 0
        |
        v   runner keeps the child's last ok:/skipped:/failed: line -> emit(result) -> schedules.log
```

### Recommended Project Structure
```
installer/
├── notify.py            # NEW (D-16): Notifier alias, notify_send, osascript, notifier_for
├── update_check.py      # NEW (recommended): run_check, notified-set read/write, self-check, summary text
├── version_status.py    # + outdated_ids(states); + stale_after / failure sink keywords on refresh path
├── schedules.py         # + JobKind.CHECK_UPDATES, Schedule.daily, row, runner_argv branch, _state_artifacts
├── schedule_run.py      # dispatch by kind; RunDeps gains DEFAULTED fields after `context`
├── cli.py               # --run-schedule choices widen to include check-updates
├── schedules_screen.py  # daily flag, what/_target/detail branch, DataTable max-height
└── helper_assets/schedule_runner.py   # job table entry, _PASSED_ENV += DBUS_SESSION_BUS_ADDRESS, timeout wording
```
`update_check.py` is a recommendation (the CONTEXT only fixes `notify.py` and the function name `outdated_ids`); it keeps `schedule_run.py` (148 lines, "this module decides") from absorbing git, JSON and notification logic. `outdated_ids` belongs beside `ToolState` in `version_status.py` (its input type).

### Pattern 1: Dispatch by kind (D-04)
**What:** replace the single `kind is not UPDATE` refusal with a table.
**Current code** (`installer/schedule_run.py:133-135`): `schedule = schedules.schedule_by_id(schedule_id)` / `if schedule.kind is not schedules.JobKind.UPDATE:` / `return f"failed: {schedule_id} is not an update schedule", 2`. The lock branch below it (`:136-148`) is shared; only the function called inside `_run_unlocked` position differs.
**When:** always; keep the exact refusal string for TMP and CACHE (`tests/test_schedule_update.py:180-187`).

### Pattern 2: Thread `stale_after` and a failure sink through the refresh path
Call sites that must carry the keyword (all in `installer/version_status.py`, default keeps every other caller unchanged):
`refresh` (:1791) -> `_pass` (:1825) -> `should_fetch` gate at :1891 and `resolve_status` (:1893, def :542) -> `resolve_github_release_status` (:334, called :568), `_latest_status` (:360; called :580 and :622) -> `should_fetch` at :390 and :417, `is_stale` at :420. `version_cache.should_fetch(entry, *, now)` and `is_stale(entry, *, now)` (`version_cache.py:216,225`) gain `stale_after: timedelta = STALE_AFTER`. `resolve_status` has no caller outside `version_status.py` in `installer/`; tests call it directly, so a keyword with a default is safe. The failure sink goes in the `except (VersionError, OSError)` branch of `_latest_status` (:398-411).

### Pattern 3: Notified-set file (D-14/D-15)
```python
# Source: pattern of installer/atomic.py:76-93,186-217 (read here) + CONTEXT D-14
path = ctx.state_path.with_name("update-check.json")      # scratch HOME works: state_path derives from Path.home()
try:
    raw = read_capped(path, 64 * 1024, follow_symlinks=False)   # None for a non-regular file; OSError when missing
    data = json.loads(raw) if raw is not None else None
except (OSError, ValueError):
    data = None
notified = frozenset(i for i in (data or {}).get("notified", []) if isinstance(i, str)) if isinstance(data, dict) and data.get("version") == 1 else frozenset()
...
atomic_write_text(path, json.dumps({"version": 1, "notified": sorted(ids)}) + "\n")
```
`atomic_write_text` does not create the parent directory (`atomic.py:36-57` writes a sibling temp in the same directory); the state dir exists after any schedule or version-cache write, but a scratch-HOME test must `mkdir(parents=True)` or the code must call `installer.locations.ensure_dir(path.parent)` as `version_cache.save_version_cache` does (`version_cache.py` imports `ensure_dir`).

### Pattern 4: House runner call for children (D-16, D-19)
`run_output(cmd, *, timeout=None, env=None, new_session=True)` (`installer/run.py:154-160`) wraps `subprocess.run(... stdin=subprocess.DEVNULL, start_new_session=new_session, env=env)` and raises `CommandError` (`run.py:61-73`) with `detail` = stripped stderr and `returncode` 124 on timeout, 127 on OSError. `command_error_line(exc)` (`run.py:75`) gives the first non-empty stderr line: use it as the `notify skipped` reason, then `sanitize_log_line` and bound to ~300 characters like `schedule_run._first_line` (`_REASON_LIMIT = 300`, `schedule_run.py:21`).

### Pattern 5: `run_git_isolated` (what it is)
`run_git_isolated(argv)` (`run.py:186-195`) strips `GIT_DIR, GIT_WORK_TREE, GIT_INDEX_FILE, GIT_ASKPASS, SSH_ASKPASS` (`_GIT_INHERITED`, `run.py:183`), sets `GIT_TERMINAL_PROMPT=0` and `SSH_ASKPASS_REQUIRE=never`, adds `-c core.hooksPath=/dev/null -c core.autocrlf=false` (`_GIT_ISOLATION`, private) and calls `run_output(..., timeout=600, env=env)` (new session, 600 s). It has two production callers (`setup.py:554,601`, `compose.py:651`) and a test asserting the env scrub (`tests/test_run.py:992`). The self-check needs 20 s and the caller's group. Recommended: add keyword-only `timeout: float = 600`, `new_session: bool = True` and `env_extra: Mapping[str, str] | None = None` to `run_git_isolated` rather than importing the private `_GIT_ISOLATION`; the default call stays byte-identical so `tests/test_run.py:992` and the `use_git_runner(run_git_isolated)` identity asserts (`tests/test_setup.py:4859,4867`) keep passing.

### Anti-Patterns to Avoid
- **Wrapping `resolve_tag`/`resolve_npm` to capture errors:** drops digests (Pitfall 2).
- **Shifting `now` to defeat the cache:** `_parse_iso` returns None for stamps more than `FUTURE_SKEW` ahead (`version_cache.py:62-92`), which makes `is_stale` true for the wrong reason and hides real staleness.
- **Putting the notified set in `schedules.json`:** closed `_TOP_KEYS` and sticky damage (D-14, verified `schedules.py:255`).
- **Calling the default `notifier_for(...)` from any test:** it resolves the real `notify-send`/`osascript` (Pitfall 3).
- **Baking a bus address into the unit:** `daemon.check_environment` rejects any key outside `ENVIRONMENT_KEYS` (`daemon.py:55-59`), so it would raise `DaemonScheduleError`.
- **Pluralising the result text:** SPEC R1 and the roadmap fix the literal `ok: N updates available` (so `ok: 1 updates available`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic JSON write | open/write/rename | `atomic_write_text` | symlink-resolving, unique sibling temp, crash safe |
| Bounded file read of untrusted bytes | `Path.read_text` | `read_capped(..., follow_symlinks=False)` | refuses FIFOs and symlinks, size cap |
| Spawning a child | `subprocess` import in `notify.py`/`update_check.py` | `run_output` | stdin closed, timeout, CommandError, bandit-clean, injectable |
| One-line, control-free log text | regex | `sanitize_log_line` + the `_first_line` pattern | already the house rule for result lines |
| Lock for a manual run | own flock | `runlock.try_acquire` (as `schedule_run.run_schedule`) | same busy semantics |
| Quoting for AppleScript | string escaping | argv data via `on run argv` (D-18) | no source text is built from tool names |
| Timer unit/plist | new templates | `render_exec_service`, `render_timer(on_calendar=...)`, `render_agent_plist` | D-03; `Persistent=true` at `systemd_daemon.py:237` |

**Key insight:** every hard part (locking, group kill, log trimming, atomic state, calendar rendering) already exists for the update rows; the phase is wiring plus three small pure functions (`outdated_ids`, the set comparison, the behind test).

## Runtime State Inventory

Not a rename or migration phase. Omitted. (One migration-like fact for completeness: the shared runner copy under `~/.local/share/tools-installer/schedules/` gains the `check-updates` job and the changed `_PASSED_ENV`; `_refresh_shared` (`schedules.py:1659`, called first in `_reconcile_pass` when the state is undamaged, `:1696`) rewrites recorded shared assets that differ from source, so installed users pick it up on the next launch reconcile with no migration code.)

## Common Pitfalls

### Pitfall 1: The eighth row does not fit the Schedules table
**What goes wrong:** `SchedulesScreen DataTable { height: auto; max-height: 8; }` (`schedules_screen.py:240`) is exactly header plus 7 rows. `tests/test_schedules_view.py:677-679` asserts `table.region.height == 8`, `table.max_scroll_y == 0` and `detail.region.height == 4` at 80x20. With `check-updates` the table needs 9 lines: it scrolls (`max_scroll_y` becomes 1) and those asserts fail. CONTEXT D-22 lists only `:240-248` for this file.
**Why:** the CSS cap was sized to the old row count.
**How to avoid:** decide in plan: raise `max-height` to 9 and update the asserts (`detail.region.height` becomes 3 at 80x20, and the detail text is already cut with an ellipsis), or keep 8 and accept scrolling and change the `max_scroll_y` assert. Recommended: 9, because the test's stated intent is "every row visible at 80x20". [header counted as one line: derived from the 8-line assert with 7 rows; run the pilot test to confirm]
**Warning signs:** `test_schedules_view.py` layout test fails on `max_scroll_y`.

### Pitfall 2: Wrapping the tag resolver loses digests
**What goes wrong:** `release_resolver(resolve_tag)` returns `resolve_github_release` (with asset digests) only when `resolve_tag is resolve_github_tag`; any other callable becomes `lambda repo: Release(resolve_tag(repo), {})` (`versions.py`, `release_resolver`, ~line 436-445; read this session). A check that passes a wrapping resolver to collect failure text would write cache entries with empty `digests`, silently disabling download verification for later updates.
**How to avoid:** put the sink inside `_latest_status`'s except branch (Pattern 2). Test: after a check run with the production resolver faked at the HTTP layer (`urlopen_fetch` seam), the saved entry keeps its digests.

### Pitfall 3: Tests reach the developer's notification daemon
**What goes wrong:** the sandbox (`tests/conftest.py`, `tests/sandbox.py`) strips the real home, `/run/user` and linuxbrew from PATH but does not clear `DBUS_SESSION_BUS_ADDRESS` or `XDG_RUNTIME_DIR` (rg for `DBUS|XDG_RUNTIME_DIR|notify` in both files: no match), and `/usr/bin` stays on PATH, so `shutil.which("notify-send")` finds the real binary on this host (and `osascript` on the macOS runner). A test using the default resolver would pop a real notification.
**How to avoid:** every notifier test injects `which` and `run`; tests of the bus rules call `monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)` and `delenv("XDG_RUNTIME_DIR", ...)` first and use a `tmp_path` runtime dir; tests of `setup._schedule_run_deps` replace the notifier. Add one test that `setup._schedule_run_deps(...)` builds the notifier from `notifier_for` and is never invoked by the schedule tests.

### Pitfall 4: `RunDeps` is built positionally
`tests/test_schedule_update.py:193` calls `RunDeps(deps.tools[:0], deps.updates, deps.resolve_owner, deps.probe_version, None)`. New fields (refresh service, notifier, git seam) must follow `context` and carry defaults, or that test and `:128,:285` break.

### Pitfall 5: The runner's clean env strips what notify-send needs
`_child_env` keeps only `_PASSED_ENV` (`schedule_runner.py:82-97,191-195`). Neither `DBUS_SESSION_BUS_ADDRESS` nor `XDG_RUNTIME_DIR` is there, so today a child sees neither; verified result without both and without `DISPLAY`: `Failed to show notification: Cannot autolaunch D-Bus without X11 $DISPLAY`, exit 1. D-17 fixes it (pass `DBUS_SESSION_BUS_ADDRESS`; derive when absent).

### Pitfall 6: A catch-up run at login can precede the notification daemon
`Persistent=true` (`systemd_daemon.py:237`) makes a missed 09:00 run fire as soon as the user manager starts at login. The user manager starts before the graphical session's notification server is guaranteed to be up, so `notify-send` may fail, the set is not stored (D-15) and the next try is the next day. Harmless but the notification can systematically arrive a day late on laptops that sleep through 09:00. [ASSUMED: start-order timing not observed; accept and document, or a later phase can add a bounded retry]

### Pitfall 7: `osascript` can exit 0 and show nothing
Reports say that until Script Editor's notifications are enabled the command "finished normally but never appeared" (macscripter/Zenn sources below). The set would then be stored as notified although nothing was shown. Only the row detail (D-08) mitigates it. [CITED forum reports, LOW]

### Pitfall 8: brew-owned tools reflect the local brew index only
`manager_versions.py:30` sets `_BREW_ENV = {"HOMEBREW_NO_AUTO_UPDATE": "1", "HOMEBREW_NO_ENV_HINTS": "1"}` for every `brew outdated`/`brew info` query (`:164,:198,:210`). The check therefore cannot see a new formula version until the user's own `brew update` ran; the constraint "changes no tool, writes nothing outside installer state" rules out the check running `brew update`. The notification can under-report for brew-owned tools. [`brew outdated` not refreshing the index by itself: ASSUMED from docs.brew.sh/Manpage, whose `outdated` entry says only "List installed casks and formulae that have an updated version available" and which names `update-if-needed`/`install` as the auto-update triggers; the ENVIRONMENT section was not readable]

### Pitfall 9: `ls-remote` pattern is a suffix match
`git ls-remote origin refs/heads/main` can also list refs that end in `/refs/heads/main`. Parse the output and accept only the line whose ref column equals `refs/heads/main` exactly; empty output with exit 0 means the ref is missing (verified), which is "no information", not "behind".

### Pitfall 10: The installer is a shallow clone for end users
`install.sh` runs `git clone --depth 1 --branch "$TI_REF" "$TI_REPO_URL" "$TI_DIR"` (`install.sh:74`; defaults `TI_REF=main`, HTTPS URL at `:17`). In such a clone, a newer remote main is not present locally, so `git cat-file -e <sha>^{commit}` exits 128 (verified in a scratch shallow clone) and D-20 reads it as "behind", which is right. Caveat: a user who installed with `TI_REF` set to a tag or another branch is "behind" `main` forever; the clause will repeat daily and the installer joins the set permanently as `tools-installer` (set unchanged, so no repeat notification, but N includes it). Decide wording at plan time (see Open Questions).

### Pitfall 11: Layout/logic of "daily" on Linux tmp cleanup
`TMP_CLEANUP` checks are of two kinds. Daily-ness (replace with `schedule.daily`): `schedules.py:848-849` (`_calendar_grid`), `:1412-1415` (`_retime` forces interval 24), `schedules_screen.py:384,395-396,501-502,577,717`. Tmp-specific (keep): Linux fixed 10-minute cadence (`_grid` `:842`, `_is_linux_tmp` `schedules_screen.py:374-377`, `_retime` refusing on Linux `:1413-1414`), the `$TMPDIR` target and `_TMP_WHAT`, marker logic in `_row_action` (`:1552`), `_seed_legacy_start` (`:1567`), `_is_stale` (`:1591`), `_state_artifacts`/`_footprint` legacy wrapper (`:1826`), `_tmp_decided` users. A search-and-replace of `TMP_CLEANUP` would break these; change only the seven sites. On Linux a `daily` row that is not tmp (check-updates) stays editable (time only).

## Code Examples

### Linux notifier (verified behaviour, not a verified implementation)
```python
# argv per D-17; --app-name/--urgency per `notify-send` man page (manpages.debian.org notify-send.1: -a/--app-name, -u/--urgency)
argv = [binary, "--app-name=tools-installer", "--urgency=normal", "--", summary, body]
env = {**os.environ}                                   # the child already holds _PASSED_ENV
addr = env.get("DBUS_SESSION_BUS_ADDRESS") or _derived_bus(env)   # unix:path=$XDG_RUNTIME_DIR/bus or /run/user/<uid>/bus when the socket exists
if addr: env["DBUS_SESSION_BUS_ADDRESS"] = addr
else: env.pop("DBUS_SESSION_BUS_ADDRESS", None)        # unset, never empty
try:
    run_output(argv, timeout=10, env=env, new_session=False)
except CommandError as exc:
    return sanitize(command_error_line(exc))           # e.g. "Failed to show notification: Could not connect: No such file or directory"
return None
```
Observed on this host (libnotify 0.8.9), all with a bogus or scratch bus so nothing was displayed: with `--` and a summary starting with `-` the call reached the bus step (`Could not connect: No such file or directory`, exit 1); the same summary without `--` gives `Unknown option -x`, exit 1; with no bus variable, no `XDG_RUNTIME_DIR` and no `DISPLAY`: `Cannot autolaunch D-Bus without X11 $DISPLAY`, exit 1; with only `XDG_RUNTIME_DIR` pointing at a scratch directory holding a listening socket named `bus`, the client connected to it (the fake server saw `\x00AUTH\r\n`) and failed on the reset, so GLib's own `$XDG_RUNTIME_DIR/bus` fallback is real [VERIFIED: ran on this host 2026-11-21; scratch directories removed].

### macOS notifier argv (D-18) and its injection property
```python
argv = ["osascript", "-e", "on run argv", "-e",
        "display notification (item 2 of argv) with title (item 1 of argv)",
        "-e", "end run", "--", title, body]
```
`title` is a fixed string; `body` is built only from counts and tool ids. Tool ids match `TOOL_ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]*")` (`installer/model.py:196`), so no quote, backslash, `<`, `>` or `&` can occur; the golden test still feeds `"`, `\` and non-ASCII names to prove the AppleScript source text never contains them. The `on run argv` / `item N of argv` pattern is the documented way to pass arguments (Zenn write-up and the Debian `notify-send.scpt` example below); whether `osascript` swallows `--` as a getopt end-of-options marker or hands it over as `item 1` is **unverified**. Since title and body always start with a letter or digit, `--` is not needed for safety: recommend the planner either drop it or keep it only if the Mac UAT proves it is swallowed (D-18 is provisional "own reasoning", so this is a recommendation, not an override).

### The check's result line (SPEC R1 literal)
`ok: {N} updates available` then optional `; {k} lookups failed: {first reason}`, `; installer check skipped: {reason}`, `; notify skipped: {reason}`, each reason through `sanitize_log_line`, first line only, at most 300 characters. The runner picks the child's last line starting with `ok:`/`skipped:`/`failed:` (`schedule_runner.py:52` `_RESULT_PREFIXES = ("ok:", "skipped:", "failed:")`; `:345-358`), so nothing else the child prints may start with those words.

### Behind test (D-20), verified commands
`git -C <co> rev-parse HEAD`; `git -C <co> ls-remote origin refs/heads/main` (stdout `<sha>\trefs/heads/main`, exit 0; empty output exit 0 when absent; exit 128 `fatal: unable to access ...` when unreachable); `git -C <co> cat-file -e <sha>^{commit}` (128 `Not a valid object name` when unknown); `git -C <co> merge-base --is-ancestor <sha> HEAD` (0 when already contained). In a scratch repo, `rev-parse`, `ls-remote` and `cat-file` left every file of the checkout and `.git` byte-identical [VERIFIED: sha256 of all files before and after, 2026-11-21]. Here `origin/main` (`72f6312d...`) exists locally and is an ancestor of HEAD, so this checkout reads "not behind" [VERIFIED: `git cat-file -e`, `git merge-base --is-ancestor`].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Notifications out of scope (24.2) | Daily update-check notification | 2026-11-19 amendment (D-01) | `24.2-SPEC.md:179` and `24.2-CONTEXT.md:43` already carry the amendment text (read this session) |
| `UPDATE`-only `--run-schedule` | `UPDATE` plus `CHECK_UPDATES` | this phase | `cli.py:58` `choices=list(schedules.UPDATE_SCHEDULE_IDS)` must widen; `tests/test_cli.py:114-123` keeps `tmp-cleanup` and `bogus` invalid |

**Deprecated/outdated:** none.

## CONTEXT Reconciliation

CONTEXT was written 2026-11-19; phases 27-33 are on this branch. Result: the engine files are unchanged where it matters. Each citation checked against the code read this session.

| CONTEXT says | Code now | Plan should |
|--------------|----------|-------------|
| D-02 `schedules.py:37-41,71-93` | `JobKind` 37-41; `SCHEDULES` tuple 70-92 (rows end `_update("copilot"),` then `)`) [VERIFIED schedules.py:37-41,70-92] | Append the row after `_update("copilot")`; no drift beyond one line |
| D-02 `cli.py:56-62` builds choices from `UPDATE_SCHEDULE_IDS` | `choices=list(schedules.UPDATE_SCHEDULE_IDS)` at `cli.py:58`; help text says "run one scheduled update" | Widen choices (e.g. a `RUN_SCHEDULE_IDS` derived by kind), reword help; `tests/test_cli.py:114-123` stays green because `tmp-cleanup` remains rejected |
| D-03 `runner_argv` `schedules.py:853-888`, unknown kind falls into tmp cleanup | `runner_argv` at 853; branches `UPDATE` (:858), `CACHE_CLEANUP` (:860), else tmp (:862-872) | Add an explicit `CHECK_UPDATES` branch `["check-updates", "--installer", str(ctx.checkout), "--uv", str(uv)]` before the else |
| D-03 runner `schedule_runner.py:320-358,454-474,511-515` | `_update` 320-358; `_parse` required-options map 454-458 and positional/run_id logic to 475; job table 510-515; `_UPDATE_TIMEOUT` 51; message `"failed: the update timed out"` in `_update` | Add `"check-updates": ("--installer", "--uv")` to the map with `wanted=1`, `run_id = job`; add a `check-updates` lambda that calls `_update(run_id, ...)`; pass the timeout wording as a parameter. The child is invoked as `--run-schedule <run_id>` so `run_id` must be `check-updates` |
| D-04 `schedule_run.py:127-148` | exact: refusal at 134-135, lock branch 136-148 | As written |
| D-05 `schedules.py:1548-1562,1699-1721`, `row_state` `:1488-1492` | `_row_action` 1548-1562; `_reconcile_pass` 1692-1721; `row_state` UPDATE gate at 1488-1492 | As written; on-by-default also changes `reconcile_lines` text (`schedules.py:1743-1745`): `Turned on schedules: tmp cleanup, cache cleanup, claude update, update check. Change them in Schedules.` |
| D-06 seven sites `schedules.py:847-850,1412-1415`; `schedules_screen.py:384,395-396,501-502,577,717` | all seven match: `_calendar_grid` 847-850, `_retime` 1412-1415, screen `_grid` 384, `_cells` 395-396, `_times_line` 501-502, `action_edit_time` 577, `_retime_line` 717 | Replace `kind is TMP_CLEANUP` with `schedule.daily` at exactly these; keep the tmp-specific checks (Pitfall 11) |
| D-06 "no test constructs `Schedule(` directly" | not re-grepped beyond CONTEXT; `tests/test_schedules.py:105-140` lists ids | Re-check with `rg "Schedule\(" tests` in Wave 0 |
| D-08 `schedules_screen.py:430-482` | `_target` 431-437, `_detail` 459-482 incl. `what` branches (:463) and `runs:` line (:479-481: `job = f"update {schedule.target}" if schedule.target else schedule.kind.value`) | Add branches: `what`, `_target` ("installed"), `_extra_lines` (notifier name, macOS permission sentence); `runs:` prints `check-updates` unchanged |
| D-09 `version_cache.py:44-45`, `70-92`, `216-231` | `STALE_AFTER = timedelta(days=7)` :44, `RETRY_BACKOFF = timedelta(hours=6)` :45, `_parse_iso` ~62-92, `is_stale` 216, `should_fetch` 225 | As written |
| D-09 call sites `version_status.py:389,416-419,1877` | now :390, :417-420, :1891 (+1, +1, +14) | Use the Pattern 2 list; do not trust old numbers |
| D-10 `version_status.py:1855-1866,1961-1962` | `for tool in tools:` :1870; `allow_fetch = fetches < MAX_FETCHES_PER_REFRESH` :1880; `fetches += 1` :1976 | Cap is consumed in iteration order and only by tools whose owner is `installer` (github or npm) or `bun` and whose `should_fetch` is true (:1882-1892); an uninstalled tool never spends it |
| D-11 `versions.py:358-373`; `daemon.py:34-47`; runner `82-97` | `urlopen_fetch` 358-373 (token only from `token` arg, `GITHUB_TOKEN`, `GH_TOKEN`, and only for `api.github.com`); `PASSTHROUGH_KEYS` and `ENVIRONMENT_KEYS` at `daemon.py:47`; `_PASSED_ENV` 82-97 | As written. Nuance: a manual `--run-schedule check-updates` from a shell that exports a token WILL use it (never written anywhere); "anonymous" holds for timer runs |
| D-12 `versions.py:396-409`, `version_status.py:400-412` | `resolve_github_release` 396-409 maps `OSError, HTTPException, ValueError` to `VersionError`; `_latest_status` except branch 398-411 stamps `failed_at` | Thread the sink in that except branch, not by wrapping resolvers (Pitfall 2) |
| D-13 `version_status.py:1019-1043`, `271-304`, `manager_versions.py:40-51` | `_PRESENT_HEALTH` :1029, `ToolState` 1033-1056 (`present` property :1054); `tool_health` 271-305; `OutdatedReport` at `manager_versions.py:40-51` | Put `outdated_ids` after `ToolState`. Counted states: `present` = `{BROKEN, MISCONFIGURED, OUTDATED, OK}` (CHECKING excluded) |
| D-14 `schedules.py:1803-1853`, `_TOP_KEYS` :255, `:1510-1512`, `:1692-1706` | `_state_artifacts` 1803-1811; `_cleanup_if_last` ~1830-1853; `_TOP_KEYS` :255-257; `STICKY_DAMAGE_WARNING` ~1510; `_reconcile_pass` 1692 | Add `ctx.state_path.with_name("update-check.json")` to `_state_artifacts`; extend the last-off test (`tests/test_schedules_lifecycle.py:564` lists the artifacts) |
| D-16 `run.py:103-127,184-191` | `run_output_with_stderr` 115-152, `run_output` 154-183, `run_git_isolated` 186-195 | Use `run_output(..., new_session=False)` |
| D-17 "24.2 D-10 F4 bans `/run/user/*` in unit text, `systemd_daemon.py:207-211`" | Lines 207-211 are the `Environment=` render loop. The F4 text is `schedules.py:442-446` (`clean_unit_path` docstring: PATH carries "transient `/run/user/*` dirs"); the hard stop is `daemon.check_environment` (`daemon.py:55-69`): a key outside `ENVIRONMENT_KEYS` raises `DaemonScheduleError` | Keep the decision (never in the unit); cite the real lines; the unit cannot carry the bus variable even by mistake |
| D-17 "user manager carries `unix:path=/run/user/1000/bus`; runner strips it" | `systemctl --user show-environment` lists `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` (`dbus.socket`: `ExecStartPost=-/usr/bin/systemctl --user set-environment DBUS_SESSION_BUS_ADDRESS=unix:path=%t/bus`); neither is in `_PASSED_ENV` [VERIFIED: ran read-only on this host] | As written; add the variable to `_PASSED_ENV` |
| D-19 `setup.py:539-543`; `run.py:157-171` | `context_for(..., checkout=Path(__file__).resolve().parent, ...)` at `setup.py:539-543` (`_schedule_run_deps` 529-544); `run_git_isolated` env at `run.py:183-195` | As written; checkout resolves to the repo root |
| D-21 `schedule_runner.py:345-358,510-522`; `setup.py:547-561`; `schedule_run.py:61-62`; `schedules.py:495-496` | all match (`_update` result folding 345-358; `_locked_run` 503-520; `_run_schedule` 547-561 prints the line; warning clauses `schedule_run.py:61-62`, `update_result_line` postinstall clause) | As written |
| D-22 test lists | `test_schedules.py:105-140` ids/labels/targets (the three lists at :106-114, :115-121, :131-139 plus `UPDATE_SCHEDULE_IDS` :124 unchanged); `test_schedules_view.py:240-248` last-cells list of 7; lifecycle `:103-113` (records list :104, tuple :107, text :110) and `:152`; handover `:493` plus `:62` (text constant) and `:494` (id list) | Also edit: lifecycle `:548` (`ALL_IDS`), `:600`, `:654` loops; handover `:62`, `:494`; view layout test `:673-679` (Pitfall 1). `tests/test_wizard_app.py:4034` and `tests/test_screen_family.py:1772` construct reports with `("tmp-cleanup",)` only and are unaffected |
| D-23 `version_status.py:1193-1222` | `VersionRefreshService` class 1204, `__init__` 1207-1245 | Seams used by tests: `tests/test_version_status.py:162-196` (`_versions`, `_installer_owned_service`), cap test at :504 and :658-667 |
| Roadmap SC1/SC5 wording | SC1 "exactly one `ok: N updates available` line"; SC5 "logs one self-update line from `git ls-remote`" | SC5 contradicts D-21 literally (a separate line cannot reach the log). SPEC is already amended; ROADMAP.md text is not. Update the ROADMAP SC5 sentence to "one self-update clause on the result line" in the phase's docs task |

**Locked-decision conflicts:** none. Items needing a plan-time decision that CONTEXT does not settle: Pitfall 1 (table height), D-18 `--`, the `TI_REF` tag case (Pitfall 10), and the D-15 shrinking-set behaviour (CONTEXT says "reported, not re-decided").

## What a new `check-updates` kind must touch (checklist)

**Production:** `schedules.py` (`JobKind`, `Schedule.daily`, row, `runner_argv`, `_state_artifacts`, the `daily` sites); `cli.py` (choices, help); `schedule_run.py` (dispatch, `RunDeps` defaulted fields); `setup.py` (`_schedule_run_deps` builds the refresh service handle, notifier, and passes them; `_run_schedule` unchanged); `helper_assets/schedule_runner.py` (usage docstring lines 15-19, `_parse`, job table, `_PASSED_ENV`, timeout wording); `schedules_screen.py` (daily, `what`, `_target`, `_extra_lines`, CSS height); `version_status.py` (`outdated_ids`, `stale_after`, sink); `version_cache.py` (`stale_after` on `is_stale`/`should_fetch`); `run.py` (`run_git_isolated` keywords); new `notify.py`, `update_check.py`.

**Tests that enumerate rows or counts** (closed-table and completeness): `test_schedules.py` (`test_the_table_is_closed_and_ordered` :105-140), `test_schedules_view.py` (`IDS` derived from `SCHEDULES` at :40; last-cells list :240-248; layout :673-679), `test_schedules_lifecycle.py` (:104,:107,:110,:152,:548,:600,:654), `test_schedules_handover.py` (:62,:493,:494), `test_cli.py` (:109-123 keeps rejecting `tmp-cleanup`), `test_schedule_runner.py` (job table/usage errors near :125; `_PASSED_ENV` growth is additive), `test_schedule_update.py` (:180-187 unchanged, RunDeps positional :193). Derived and self-adapting: `test_container_e2e_schedules.py:174` (`[schedule.id for schedule in schedules.SCHEDULES]`).

**Golden files:** none exist for schedules; the "golden" osascript argv is an in-test literal. Unit text tests are assertion-based (OnCalendar `*-*-* 09:00:00` from `on_calendar(((9, 0),))`, `schedules.py:156-158`).

**Docs:** README has no Schedules section (`rg -i "schedul|timer|notif" README.md docs/TROUBLESHOOTING.md` only hits unrelated lines 254, 351 and TROUBLESHOOTING:57); optional short README/TROUBLESHOOTING note is test-read (see below). `.claude/architecture.md` contains no schedules section at all (`rg -i schedul` finds nothing in its 1254 lines), so the "schedules section" the brief mentions does not exist; adding a short "Phase 34" subsection (notify seam, outdated-set contract, notified-set file) follows the file's per-phase pattern and is optional. `tests/test_docs.py` lints rule documents (banned truncation-banner fragments `[Showing lines`, `Use offset=`); keep new prose clear of them.

**docs-only / TEST_READ / LEDGER:** `devtools/docs_only.py` treats `.planning/*` and `*.md` as docs-only unless they match `TEST_READ` (`AGENTS.md`, `README.md`, `.claude/*`, `.github/*`, `docs/*`, `scripts/*`, `tests/*`, two `.planning` globs). So a README or `.claude/architecture.md` edit triggers the full CI run; phase planning files do not. `tests/test_docs_only.py:209-` `LEDGER` must classify every string literal ending in `.md` or starting with `.planning` found in any other test (`markdown_literals`): new tests must avoid such literals or add LEDGER entries (stale and new pairs both fail `test_every_markdown_literal_in_the_tests_is_classified`). The 24.2 amendment (D-01) is already in place, so no test needs to read the 24.2 files.

## Contract phase 35 inherits (names are locked)
`installer/notify.py`: `Notifier = Callable[[str, str], str | None]`, `notifier_for(platform_os, which, run)`; `version_status.outdated_ids(states) -> frozenset[str]`; `VersionRefreshService.refresh(tools, *, stale_after=...)`; `Schedule.daily: bool = False`; `JobKind.CHECK_UPDATES`; `DBUS_SESSION_BUS_ADDRESS` in `_PASSED_ENV`; the notifier injected through `RunDeps` (35 D-17). Confirmed by reading `35-CONTEXT.md` D-02, D-03, D-07, D-17, D-21. Every one of these needs a production caller inside phase 34 (architecture rule 5, `vulture`), which the check itself provides; do not add Phase-35-only parameters.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `brew outdated` with `HOMEBREW_NO_AUTO_UPDATE=1` reads the local index and never refreshes it | Pitfall 8 | Brew-owned updates under- or correctly reported; only affects wording of docs |
| A2 | `osascript` consumes `--` as end-of-options and passes only title and body as `argv` items | Code Examples | If it passes `--` as item 1, title and body shift by one; recommend dropping `--` (safe either way) |
| A3 | `osascript display notification` exits 0 when the app's notifications are disabled | Pitfall 7 | If it exits non-zero, `notify skipped` covers the unallowed case and the set is not stored |
| A4 | A LaunchAgent in `gui/<uid>` attributes the notification to Script Editor | D-08 text | Detail sentence would name the wrong app; Mac UAT confirms |
| A5 | Installed installer-owned (github/npm) plus bun tools stay under 20 eligible per run | Pattern 2 | If more, the oldest-first sort (D-10) spreads them over days; no failure |
| A6 | GitHub returns 403 or 429 on the primary limit | Rate limits | Either maps to `HTTPError` then `VersionError` (an OSError subclass is caught at `versions.py:396-409`), so behaviour is identical |
| A7 | The 8th table row needs 9 lines (header counted) | Pitfall 1 | If the header is not counted the test may still pass; run the pilot test first |
| A8 | The user manager can start before the notification server at login | Pitfall 6 | If not, no late-notification risk |
| A9 | Ubuntu/macOS CI runner images carry `notify-send`/`osascript` on PATH | Pitfall 3 | Tests inject fakes either way; only the "never default" guard depends on it |
| A10 | `--urgency=normal` without `--transient` leaves the notification in the shell's history on KDE and GNOME | D-17 | Cosmetic |

## Open Questions

1. **GitHub repository public, HTTPS `ls-remote` anonymous** (RESOLVED)
   - `gh api repos/castocolina/tools-installer --jq .private` returned `false` and an unauthenticated `curl` of the repository page returned HTTP 200 (2026-11-21). The README clone and `install.sh` use the HTTPS URL.
2. **Does notify-send fall back to `$XDG_RUNTIME_DIR/bus` without the variable** (RESOLVED)
   - Yes on this host's GLib/libnotify 0.8.9 (scratch socket experiment above). D-17's explicit pass/derive logic is still required because the runner strips both variables.
3. **Does the user manager export the bus address to services** (RESOLVED)
   - Yes (`show-environment` and `dbus.socket` text above). Other Bazzite/Fedora Atomic variants and Ubuntu are untested.
4. **Eighth row versus the 80x20 layout** (plan decision, not owner)
   - Recommendation: `max-height: 9` and update `tests/test_schedules_view.py:677-679` (detail 3 lines). Confirm with the pilot test in Wave 1.
5. **`osascript` `--` handling, Script Editor attribution, silent drop, one-time permission wording** (OPEN, needs the owner's Mac)
   - UAT lines to defer: (a) `osascript -e 'on run argv' -e 'display notification (item 2 of argv) with title (item 1 of argv)' -e 'end run' -- "T" "B"` shows title T and body B (not "--"); (b) after `launchctl kickstart gui/$UID/com.tools-installer.schedule.check-updates` on a Mac with at least one outdated tool, schedules.log carries `ok: N updates available` and Notification Center shows the notification, attributed to Script Editor; (c) with Script Editor notifications disabled, record whether the run still logs no `notify skipped`.
6. **`TI_REF` tag or branch installs read "behind main" forever** (OPEN, small owner/plan decision)
   - Options: accept (document); or compare against `refs/heads/<current branch>` when HEAD is on a branch and skip when detached. CONTEXT D-19 fixes `refs/heads/main`; a detached HEAD (tag install) could log `installer check skipped: not on a branch` without touching D-19 for branch checkouts.
7. **D-15 shrinking non-empty set notifies again** (OPEN, owner; CONTEXT already reported it)
   - `{a,b}` to `{a}` sends a second notification. Cheaper alternative the owner may want: notify only when the new set has a member not previously notified. Not re-decided here.
8. **Brew-owned tools under-reported without `brew update`** (OPEN, owner; scope choice)
   - Recommend: keep as is and say so in the row detail or docs; the constraint "changes no tool" excludes `brew update`.
9. **Container e2e extension** (RESOLVED as a recommendation, orchestrator-run only)
   - `scripts/container-e2e-verify.sh schedules` already runs each built-in once through its real unit and checks the log verdict with `schedules_run_verdict` (`:2497-2519`, pairs in `schedules_run_all` `:2570-2583`, the box has real systemd and `/run/user/<uid>/bus` per `schedules_bus_ready`). Adding the pair `check-updates:tools-installer-schedule-check-updates` proves, on a real user manager, the `start` plus one result line and a `notify skipped`/`ok` exit 0 (the Fedora image has no libnotify, so the clause is `notify skipped: ...`). Proving the bus variable reaches `notify-send` needs a planted stub `notify-send` and a non-empty outdated set, which is hard to force offline; keep that proof at host-test level. Extending the script means editing `tests/test_container_e2e_schedules.py:443-447` (`_BUILTINS`) and `:688` (`_IDS`) in the same commit. Executors never run the container; the orchestrator does, with `scripts/detect-container-runtime.sh`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `notify-send` | Linux delivery (runtime, tests use fakes) | yes (`/usr/bin/notify-send`) | 0.8.9 | absent: `notify skipped: notify-send not found`, exit 0 |
| `osascript` | macOS delivery (runtime) | no (Linux host) | - | tests use a fake; real check is owner UAT |
| `git` | self-check | yes (`/usr/bin/git`) | present | missing: `installer check skipped` |
| `systemctl --user` | engine tests use fakes; container e2e real | yes (systemd 262) | 262.1-1.fc45 | n/a |
| `gh` (authenticated) | research reads only | yes | - | - |
| podman/docker | optional orchestrator container run | not probed (read-only facts not needed) | - | skip e2e extension |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `osascript` (tests inject; macOS UAT deferred).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (+ pytest-xdist, pytest-asyncio for Textual pilots), coverage floor in `pyproject.toml` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_notify.py tests/test_update_check.py tests/test_schedules.py tests/test_schedules_engine.py tests/test_schedules_lifecycle.py tests/test_schedules_handover.py tests/test_schedules_view.py tests/test_schedule_update.py tests/test_schedule_runner.py tests/test_cli.py tests/test_version_status.py tests/test_version_cache.py tests/test_run.py --no-cov -q` |
| Full suite command | `make test` once after the plan; `make validate` once after the plan (AGENTS.md) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTIFY-01 | `run_schedule("check-updates")` returns `ok: N updates available`, zero update-executor calls, held lock gives `skipped: busy`; tmp/cache refusal unchanged | unit | `uv run pytest tests/test_update_check.py tests/test_schedule_update.py --no-cov -q` | new file Wave 0; refusal test exists |
| NOTIFY-01 | runner log is exactly `start` plus one `ok:` line through `schedule_runner.main(["check-updates", "--installer", ..., "--uv", fake_uv, ...])` | unit | `uv run pytest tests/test_schedule_runner.py -k check_updates --no-cov -q` | extend; helpers `_checkout`, `_script` exist |
| NOTIFY-01 | row in tuple, labels, targets, default on, unit texts, plist `ProgramArguments`, OnCalendar `*-*-* 09:00:00`, `daily` sites, view row/detail | unit + Textual pilot | `uv run pytest tests/test_schedules.py tests/test_schedules_engine.py tests/test_schedules_lifecycle.py tests/test_schedules_handover.py tests/test_schedules_view.py tests/test_cli.py --no-cov -q` | exist; edit |
| NOTIFY-02 | cache aged 1 day and 7 days -1 s/0/+1 s refreshes; 20 vs 21 eligible tools; rate-limited fetch gives `; N lookups failed: reason`, exit ok; saved entry keeps digests | unit | `uv run pytest tests/test_version_status.py tests/test_version_cache.py tests/test_update_check.py --no-cov -q` | exist; extend |
| NOTIFY-03 | same set twice sends once; changed sends again; emptied none and resets; corrupt or missing file = empty and rewritten; failed notification does not store; order does not matter | unit (fake `Notifier`) | `uv run pytest tests/test_update_check.py --no-cov -q` | Wave 0 |
| NOTIFY-04 | fake `notify-send` records argv and `DBUS_SESSION_BUS_ADDRESS`; unset stays unset, never empty; derivation from `XDG_RUNTIME_DIR`; missing binary gives `notify skipped`; `_PASSED_ENV` carries the variable | unit (fake binaries on tmp PATH, `which` injected) | `uv run pytest tests/test_notify.py tests/test_schedule_runner.py --no-cov -q` | Wave 0 |
| NOTIFY-05 | golden osascript argv with `"`, `\`, non-ASCII; failing fake gives `notify skipped`; row detail names Script Editor permission | unit + pilot | `uv run pytest tests/test_notify.py tests/test_schedules_view.py --no-cov -q` | Wave 0 / extend |
| NOTIFY-06 | bare-repo fixture ahead of the checkout adds the clause; checkout bytes identical; non-git, unreachable, missing ref, detached cases give `installer check skipped`; already-ancestor remote is not behind | unit with real `git` in `tmp_path` | `uv run pytest tests/test_update_check.py -k installer --no-cov -q` | Wave 0 |

Host dependence to state in the tests: the self-check tests need a real `git` and `file://` remotes (present on the dev host, `ubuntu-latest` and `macos-latest`; the existing suite already shells git, e.g. clone tests); use `GIT_CONFIG_GLOBAL=/dev/null`-style isolation and fixed author variables as in the experiment. Notifier tests use fake scripts, never the real `notify-send`/`osascript`, and clear the two bus variables (Pitfall 3). CI runs Python 3.15 and the local venv 3.12 (`.claude/testing.md` and memory note); nothing here is version-sensitive, but run the new files under both when touching `datetime` or `json` edge cases. CI matrix is `ubuntu-latest`, `macos-latest` (`ci.yml:24`); the golden osascript argv test must run on both without calling `osascript`.

### Sampling Rate
- **Per task commit:** the targeted files above for the edited module only (AGENTS.md: hooks run the static gates; do not run `make validate` per commit).
- **Per wave merge:** the quick command above.
- **Phase gate:** `make validate` then `make test` once, then `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_notify.py`, covers NOTIFY-04, NOTIFY-05 (argv, env, exit mapping, injection data)
- [ ] `tests/test_update_check.py`, covers NOTIFY-01 (dispatch, spy), NOTIFY-02 (windows, cap, failure sink, digests), NOTIFY-03 (set rules), NOTIFY-06 (git fixtures)
- [ ] hermetic fixtures: scratch `HOME`, cleared `DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR`, a `fake_bin` helper writing executable scripts that log argv and env (pattern: `_script`/`_recorder` in `tests/test_schedule_runner.py:221-` and `_checkout` at `:557`)
- [ ] edits to the existing row-listing tests (checklist above) and the layout test (Pitfall 1)
- Framework install: none.

## Security Domain

`security_enforcement` is true, ASVS level 1, block on high (`.planning/config.json:42-44`).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no credentials: lookups anonymous, no token in unit, state or log |
| V3 Session Management | no | - |
| V4 Access Control | partial | state file written with `atomic_write_text`; read with `read_capped(..., follow_symlinks=False)`; unit files stay 0600 (`_UNIT_MODE`) |
| V5 Input Validation | yes | tool ids constrained by `TOOL_ID_RE`; argv list, never a shell; AppleScript data via `argv`; notified-set JSON decoded defensively (type-check every element); result clauses through `sanitize_log_line` |
| V6 Cryptography | no | none |
| V12/V14 Files and config | yes | no write outside `~/.local/state/tools-installer`; `ls-remote` is read-only (verified) |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Option or markup injection through a tool name in `notify-send` | Tampering | `--` before summary/body; ids limited to `[a-z0-9._-]`; body is markup-capable per the notification spec (`<b> <i> <u> <a> <img>`), so never put free text (reasons, remote output) in the body |
| AppleScript source injection | Tampering / Elevation | text passed as `argv`, source is constant; golden test with `"` and `\` |
| Planted symlink or FIFO at `update-check.json` | Tampering / DoS | `read_capped` refuses non-regular files and symlinks; `atomic_write_text` resolves symlinks (a planted link at the path would redirect the write, same as the existing state files; the dir is user-owned) |
| Git steered by user config or repo env | Tampering | `run_git_isolated` environment, `core.hooksPath=/dev/null`, no prompts, `GIT_SSH_COMMAND` BatchMode |
| Token leak into unit/log/state | Information disclosure | no token read; grep test over unit, state and log (D-23) |
| Rate-limit exhaustion hiding real updates | DoS | cap 20, per-run failure clause, 6 h retry backoff |
| Lock-screen disclosure of installed tool names | Information disclosure | accepted; ids only, no versions or paths |

## Sources

### Primary (HIGH confidence)
- Repository files read this session: `installer/schedules.py`, `schedule_run.py`, `helper_assets/schedule_runner.py`, `schedules_screen.py`, `version_status.py`, `version_cache.py`, `versions.py`, `daemon.py`, `run.py`, `atomic.py`, `manager_versions.py`, `cli.py`, `setup.py`, `compose.py`, `.claude/architecture.md`, `.claude/testing.md`, `install.sh`, tests named above, `35-CONTEXT.md`, `34-SPEC.md`, `34-CONTEXT.md`.
- Host experiments (2026-11-21, no notification delivered, scratch dirs removed): `notify-send` error shapes and `--` handling, GLib `$XDG_RUNTIME_DIR/bus` fallback, `systemctl --user show-environment`, `git ls-remote`/`cat-file`/`rev-parse` read-only proof, scratch shallow clone behaviour, `gh api` repository visibility.
- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), fetched 2026-11-21: 60 requests per hour unauthenticated, per IP; exceeding returns 403 or 429 with `x-ratelimit-remaining: 0` and `x-ratelimit-reset`.
- [Desktop Notifications spec, markup](http://specifications.freedesktop.org/notification/latest/markup.html), fetched 2026-11-21: body tags `<b> <i> <u> <a href> <img>`; the page does not say how to treat `&` or `<`.

### Secondary (MEDIUM confidence)
- [notify-send(1), Debian manpages](https://manpages.debian.org/testing/libnotify-bin/notify-send.1.en.html), fetched 2026-11-21: synopsis, `-a/--app-name`, `-u/--urgency`, `-e/--transient`, `-t/--expire-time`, `-w/--wait`; exit codes and `--` not documented there (both observed locally instead).
- [Homebrew manpage](https://docs.brew.sh/Manpage), fetched 2026-11-21 (first 100000 characters): `outdated` description; auto-update triggers named `update-if-needed` and `install`.
- `.planning/research/2026-11-17-update-automation.md` (feature 1), read this session.

### Tertiary (LOW confidence, forum reports; need the owner's Mac)
- [Zenn: osascript notification and argv](https://zenn.dev/todesking/articles/d45044c470339e), [Apple Developer Documentation Archive: Displaying Notifications](https://developer.apple.com/library/content/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/DisplayNotifications.html), [Debian `notify-send.scpt` example](https://sources.debian.org/src/catgirl/2.2a-1/scripts/notify-send.scpt), [macscripter: notifications not displayed](https://www.macscripter.net/t/notifications-not-being-displayed/74931), [Late Night Software forum: Terminal for display notification](https://forum.latenightsw.com/t/trying-to-use-terminal-for-display-notification/5068): attribution to the launching app (Script Editor), one-time enablement, silent non-display, `on run argv` pattern. Search results dated unknown; none confirms behaviour on current macOS or under launchd.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, stdlib and in-repo modules read directly.
- Architecture: HIGH, all touch points read; the CONTEXT line numbers checked one by one.
- Pitfalls: HIGH for 1-5, 9-11 (code or experiment); MEDIUM for 8; LOW for 6 and 7 (timing, macOS).
- macOS behaviour: LOW, unverifiable on this host.

**Research date:** 2026-11-21
**Valid until:** 2026-12-21 for the code facts if `installer/schedules*.py`, `version_status.py` and `run.py` do not change on this branch; the macOS items stay open until the owner's Mac run.
