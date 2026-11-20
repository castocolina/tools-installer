# Phase 34: Daily update check with a desktop notification - Context

**Gathered:** 2026-11-19 (assumptions mode, after 34-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

A new daily `check-updates` schedule row refreshes cached latest versions headless, computes the set of outdated tools (plus the installer's own checkout), sends one desktop notification only when that set changed, and changes no tool. Phase 35 reuses its notifier and outdated-set function.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked.** See `34-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `34-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the `check-updates` row and runner, the forced refresh, the changed-set rule, the two notifiers, the self-check, unit templates for both OSes, tests, and the 24.2 amendment record. *Amended 2026-11-19 (34 D-20, D-21):* the extra clauses ride in the one result line, and tests that list every schedule row gain one entry.
**Out of scope (from SPEC.md):** failed-run notifications; a click action; a token in the unit; updating any tool; real-Mac checks.

</spec_lock>

<decisions>
## Implementation Decisions

### The row
- **D-01: The 24.2 amendment is already written** into `24.2-SPEC.md:179` and `24.2-CONTEXT.md:43` (this phase's SPEC commit); nothing else to edit there.
- **D-02: `JobKind.CHECK_UPDATES = "check-updates"`** and `Schedule("check-updates", "update check", JobKind.CHECK_UPDATES, None, 24, "09:00")` appended as the last row of `SCHEDULES` (`installer/schedules.py:37-41,71-93`); `UPDATE_SCHEDULE_IDS` filters by kind and does not change *(amended 2026-11-19, 35 D-02: `installer/cli.py:56-62` builds the `--run-schedule` choices from it, so 34 must widen the choices for `check-updates`)*. Appending keeps the other rows' ids and order (positional view tests at `tests/test_schedules_view.py:105,240`).
- **D-03: The unit and plist need no new template.** The generic path (`basename_for`, `label_for`, `render_exec_service`, `render_timer(on_calendar=...)`, `render_agent_plist`) writes `tools-installer-schedule-check-updates.{service,timer}` and `com.tools-installer.schedule.check-updates.plist`. Only `runner_argv` (`schedules.py:853-888`, where an unknown kind falls into tmp-cleanup's argv) gets a new branch, and the runner gets a job `check-updates --installer CHECKOUT --uv UV` that reuses `_update(run_id, installer, uv)` (`installer/helper_assets/schedule_runner.py:320-358,454-474,511-515`); its timeout message must not say "the update timed out". Existing rows' unit text does not change, so `_is_stale` rewrites nothing.
- **D-04: `run_schedule` dispatches by kind** (`installer/schedule_run.py:127-148`): UPDATE to `_run_unlocked`, CHECK_UPDATES to a new check function, TMP and CACHE keep the exact refusal text `failed: tmp-cleanup is not an update schedule` (`tests/test_schedule_update.py:180-187`). The check takes the same lock branch as the update rows (manual run: `try_acquire`, a held lock gives `skipped: busy`; under the runner: `parent_holds_lock`).
- **D-05: The row is on by default** through the generic reconcile (`_row_action` turns on when `decided is None`, gated by `manager_reachable`; `schedules.py:1548-1562,1699-1721`), as `cache-cleanup` does; `row_state` gates on presence only for UPDATE (`:1488-1492`). The owner asked for a daily check that leaves a notification, and 24.2 D-09 makes built-in rows default on. **Own reasoning** (jev first rung none_of_these 0.86 contradicted the evidence; second opinion off_by_default low 0.51). Ledger.
- **D-06: The row is daily-only:** a `daily: bool = False` field on `Schedule` (True for tmp-cleanup and check-updates) replaces the seven hard-coded "tmp cleanup is daily" checks (`schedules.py:847-850,1412-1415`; `installer/schedules_screen.py:384,395-396,501-502,577,717`); the time editor hides the interval for both. No test constructs `Schedule(` directly. jev fixed_daily 0.99 (TypeSafe).
- **D-07: The default start is 09:00,** off the 00:00/06:00/12:00/18:00 update grid so it does not wait behind them; Linux `Persistent=true` and macOS wake coalescing catch up missed runs (24.2 D-05). **Own reasoning** (jev midnight low 0.67; TypeSafe low). Ledger.
- **D-08: The row detail** names the notifier and, on macOS, the one-time permission ("notifications come from Script Editor: allow them once in System Settings > Notifications"); `what` and `_target` in `schedules_screen.py:430-482` get a branch for the new kind (the target reads "installed", not cache-cleanup's managers list); the `runs:` line already prints `check-updates` (`:480`).

### Refresh and the outdated set
- **D-09: A `stale_after` keyword threaded from `VersionRefreshService.refresh(tools, *, stale_after=STALE_AFTER)` through `_pass`, `resolve_status`, `_latest_status` into `should_fetch`/`is_stale`;** the check passes about 20 h. Never shift `now`: `_parse_iso` rejects stamps more than 5 min in the future (`version_cache.py:70-92`). A window under 24 h meets every SPEC boundary and avoids refetching what the TUI fetched an hour earlier; `RETRY_BACKOFF` (6 h) stays shorter than the interval. The freshness gates are `version_cache.py:216-231` (`STALE_AFTER` at :44), called at `version_status.py:389,416-419,1877`. jev: first answer `keep the 7-day window` (TypeSafe 0.94) contradicts SPEC R2, so the evidence decides: **jev overridden**.
- **D-10: `refresh` receives its tools sorted oldest-`checked_at` first** (missing first), because the 20-fetch cap is spent in iteration order (`version_status.py:1855-1866,1961-1962`). **Own reasoning** (jev low 0.55 / 0.65). Ledger.
- **D-11: Lookups stay anonymous by construction:** `urlopen_fetch` adds a token only from `GITHUB_TOKEN`/`GH_TOKEN` (`installer/versions.py:358-373`), and neither reaches the child (`daemon.ENVIRONMENT_KEYS` `daemon.py:34-47`; runner `_PASSED_ENV` `schedule_runner.py:82-97`).
- **D-12: A rate-limited fetch surfaces like any failed fetch** (`HTTPError` to `VersionError`, stamped `failed_at`, `versions.py:396-409`; `version_status.py:400-412`); the service gains an optional error sink and the line gets `; N lookups failed: <first reason>`; exit stays 0. **Own reasoning** (jev low 0.68 / 0.58). Ledger.
- **D-13: The outdated set is a pure function `outdated_ids(states) -> frozenset[str]`** keeping present tools whose `state.version.outdated is True` (`version_status.py:1019-1043`); it does not read `Health.OUTDATED` (health ranks broken and misconfigured above outdated, `:271-304`); `None` never counts; manager-owned tools arrive through `OutdatedReport` inside `resolve_status` (`manager_versions.py:40-51`). Phase 35 reuses it; its name and signature are a contract.

### The changed-set rule
- **D-14: The notified set lives in its own file** `~/.local/state/tools-installer/update-check.json`, derived from `ctx.state_path.with_name(...)` so a scratch HOME works: `{"version":1,"notified":[sorted ids]}`, written with `installer.atomic.atomic_write_text`, read with `read_capped(..., follow_symlinks=False)`; any decode problem counts as empty and is rewritten; the path joins `_state_artifacts` so the last-off cleanup and the uninstall sweep delete it (`schedules.py:1803-1853`). Verified: `schedules.json` has a closed key set (`_TOP_KEYS`, :255) and sticky damage that stops every reconcile from turning anything on (`:1510-1512`, `:1692-1706`). jev key_in_schedules_file 0.82 twice (TypeSafe, first and second opinion) contradicts that evidence; **jev overridden**.
- **D-15: Notify then store the set only if the notification succeeded;** unchanged does nothing; empty stores empty and never notifies; members are tool ids without versions. Note: a shrinking non-empty set (`{a,b}` to `{a}`) counts as changed under the SPEC wording and notifies again; reported, not re-decided. jev store_only_after_success low 0.61 (second opinion). **Own reasoning**, ledger.

### Notifiers
- **D-16: `installer/notify.py`** holds `Notifier = Callable[[str, str], str | None]` (summary, body; None on success or a skip reason), `notify_send(...)`, `osascript(...)` and `notifier_for(platform_os, which, run)`; children use the house runner style (stdin DEVNULL, `new_session=False` so the runner's group kill reaches them, short timeout; `installer/run.py:103-127,184-191`). The check appends `; notify skipped: <reason>`. A notifier inside the stdlib runner would sit where `installer` cannot be imported (`schedule_runner.py:26-29`). jev main_package_module 0.82 (TypeSafe).
- **D-17: Linux argv** `[notify-send, "--app-name=tools-installer", "--urgency=normal", "--", summary, body]`, no `--transient`; `notify-send` found with `which` on the unit's clean PATH. The bus address: add `DBUS_SESSION_BUS_ADDRESS` to the runner's `_PASSED_ENV` (the user manager carries `unix:path=/run/user/1000/bus` on this host; the runner strips it today), else derive `unix:path=$XDG_RUNTIME_DIR/bus` or `/run/user/<uid>/bus` when that socket exists, else leave it unset, never empty; never bake it into the unit (24.2 D-10 F4 bans `/run/user/*` in unit text, `systemd_daemon.py:207-211`). **Own reasoning** (jev none_of_these 0.91 contradicted the evidence; second opinion derive_only low 0.77). Ledger.
- **D-18: macOS argv** `["osascript", "-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)", "-e", "end run", "--", title, body]`: tool names reach AppleScript as data, never source text. A non-zero exit, timeout or missing binary gives `notify skipped`; the golden argv test runs on both OSes; whether osascript passes trailing args to `on run argv` is a Mac UAT item. **Own reasoning** (jev none_of_these 0.73 contradicted the evidence; second opinion separate_arguments low 0.52). Ledger.

### The self-check
- **D-19: The checkout is `deps.context.checkout`** (`setup.py:539-543`, the runner's `--installer`/`cwd`). Run `git -C <checkout> rev-parse HEAD`, then `git -C <checkout> ls-remote origin refs/heads/main` (a full ref), with run_git_isolated's environment (no prompts, askpass or hooks; `installer/run.py:157-171`) plus `GIT_SSH_COMMAND="ssh -o BatchMode=yes"`, stdin DEVNULL, in the caller's group, about 20 s (run_git_isolated's 600 s and new session are wrong for a timer child). It runs after the refresh and before the notify step, so the installer joins the set as `tools-installer`. A non-git directory, missing git, or an unreachable or auth-failing remote appends `; installer check skipped: <reason>`. This dev checkout's `origin` is SSH and the runner strips `SSH_AUTH_SOCK`, so here it will usually skip; the README clones over HTTPS, so end users read anonymously. **Own reasoning** (jev none_of_these 0.97 contradicted the evidence; second opinion public_https_address low 0.51). Ledger.
- **D-20: "Behind" means the remote main differs from HEAD and is not already an ancestor of HEAD** when its object exists locally (`cat-file -e`, then `merge-base --is-ancestor`); an unknown remote commit means new commits upstream; no fetch, no pull. **Own reasoning** (jev low 0.48 / 0.67). Ledger.

### Log line and tests
- **D-21: One result line carries everything.** `setup.py --run-schedule` only prints; the runner writes `start` plus the child's last line starting `ok:`/`skipped:`/`failed:` (`schedule_runner.py:345-358,510-522`; `setup.py:547-561`), so separate `notify skipped` or self-update lines would be discarded. The extras are `; ` clauses of the one `ok: N updates available` line, as the update rows already do (`schedule_run.py:61-62`, `schedules.py:495-496`). R1's log acceptance is tested through `schedule_runner.main([...])`, not a bare `--run-schedule`. SPEC R1, R4-R6 amended.
- **D-22: The SPEC's "existing schedule tests unedited" is read as "assertions about the other rows stay".** Tests that list every row gain one entry: `tests/test_schedules.py:105-140` (ids, labels, targets), `tests/test_schedules_view.py:240-248`, and because the row is on by default `tests/test_schedules_lifecycle.py:103,107,152` and `tests/test_schedules_handover.py:493` (`turned_on` tuples). Unchanged: `tests/test_schedule_update.py:180`, `tests/test_container_e2e_schedules.py:174` (derived from `SCHEDULES`), runner tests while `_PASSED_ENV` only grows.
- **D-23: New tests** (scratch HOME, fakes only): `run_schedule("check-updates", ...)` with a spy `UpdateService` (zero calls); `schedule_runner.main` log with exactly `start` and one `ok:` line; cache aged 1 day and 7 days -1 s/0/+1 s with 20 and 21 eligible tools; set rules (same, changed, emptied, corrupt) with a fake `Notifier`; a fake `notify-send` recording argv and `DBUS_SESSION_BUS_ADDRESS`, and a missing binary; a golden osascript argv with `"`, `\` and non-ASCII names plus a failing fake; a fixture bare repo whose main is ahead (byte-compare of the checkout), non-git and unreachable cases; a held lock giving `skipped: busy`; unit-template tests (`runner_argv` branch, plist `ProgramArguments`, OnCalendar `*-*-* 09:00:00`); a token grep over the unit, state file and log. Seams: `VersionRefreshService(resolve_tag=..., now=...)` (`version_status.py:1193-1222`).
- **D-24: The SPEC R2 concurrency backstop is restated:** the TUI's view-entry refresh takes no run lock (only mutations do, 24.2 D-12); two refreshing processes are last-writer-wins with at worst one entry lost and the file never corrupted (`version_status.py:17-24`); healed by the next refresh.

### Claude's Discretion
- Notification summary and body wording, the exact `; ` clause text, and the helper names in `notify.py`.

### Folded Todos
- `.planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md` (the phase's own source todo).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/milestones/v0.50.0-phases/24.2-schedules-view/24.2-SPEC.md`, `24.2-CONTEXT.md`
- `installer/schedules.py`, `installer/schedule_run.py`, `installer/helper_assets/schedule_runner.py`, `installer/schedules_screen.py`, `installer/daemon.py`, `installer/systemd_daemon.py`
- `installer/version_cache.py`, `installer/version_status.py`, `installer/versions.py`, `installer/manager_versions.py`, `installer/run.py`, `installer/atomic.py`
- `.planning/research/2026-11-17-update-automation.md` (feature 1)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Update rows' `_update` runner path and result-line folding; `atomic_write_text`; `VersionRefreshService` seams; the generic unit and plist renderers.

### Established Patterns
- Built-in rows default on; schedule state in one directory; the runner writes only `start` and the child's last result line.

### Integration Points
- `SCHEDULES` tuple, `runner_argv`, `run_schedule`, the runner's job table and `_PASSED_ENV`, `_state_artifacts`.
</code_context>

<specifics>
## Specific Ideas

Contract for phase 35: `installer/notify.py`'s `Notifier` seam and `outdated_ids(states)`; their names and signatures are inherited, and a `Schedule.daily` flag exists for daily-only rows.
</specifics>

<deferred>
## Deferred Ideas

- To confirm (UAT or planning): whether `osascript -e ... -- a b` passes trailing args to `on run argv` on current macOS and whether a LaunchAgent notification attributes to Script Editor; whether `brew outdated` with `HOMEBREW_NO_AUTO_UPDATE=1` sees new formula versions without `brew update`; whether the GitHub repo is public (HTTPS `ls-remote`); whether notify-send falls back to `$XDG_RUNTIME_DIR/bus` itself.

### Reviewed Todos (not folded)
None other matched.
</deferred>
