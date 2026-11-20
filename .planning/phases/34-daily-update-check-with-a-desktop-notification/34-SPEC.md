# Phase 34: Daily update check with a desktop notification — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 6 locked

## Goal

A user learns that installed tools (and the installer's own checkout) have updates without opening the TUI, from at most one desktop notification a day, on Bazzite and macOS, produced by a new daily `check-updates` schedule that changes no tool.

## Background

- The Schedules engine (`installer/schedules.py`) holds a closed tuple `SCHEDULES` of `Schedule(id, label, kind, target, default_interval, default_start)` rows (`tmp-cleanup`, `cache-cleanup`, five `update-<tool>` rows) and a `JobKind` enum (`UPDATE`, `TMP_CLEANUP`, `CACHE_CLEANUP`); `--run-schedule <id>` reaches `installer/schedule_run.py:run_schedule`, which today accepts only `JobKind.UPDATE` and returns one result line and an exit code.
- The version cache treats a cached latest as stale after `STALE_AFTER = timedelta(days=7)` (`installer/version_cache.py:44`; `RETRY_BACKOFF` is :45); a refresh fetches at most `MAX_FETCHES_PER_REFRESH = 20` (`installer/version_status.py:143`); the schedule unit carries no GitHub token, so lookups are anonymous (60 requests per hour).
- Phase 24.2 put desktop notifications out of scope: `24.2-SPEC.md:179` ("A desktop notification for failed runs — not requested; the log and the view show it") and `24.2-CONTEXT.md:43` (`.planning/milestones/v0.50.0-phases/24.2-schedules-view/`). The owner approved the reversal at the 2026-11-19 ingest gate; this SPEC records it (amended below).
- Linux hosts have `notify-send` (libnotify 0.8.9 on the dev host); macOS needs `osascript display notification` and a one-time Script Editor permission.
- Research: `.planning/research/2026-11-17-update-automation.md` (feature 1). Unverified per research: macOS `osascript` from a launchd agent.
- The owner's request (2026-11-17): a daily schedule that checks whether a software version is available and leaves a notification, on Bazzite and macOS.

## Requirements

1. **Daily headless check row (NOTIFY-01)**: The Schedules engine has a daily `check-updates` row that runs the version refresh headless through `--run-schedule`, writes exactly one `ok: N updates available` line to the shared schedule log (any notify-skipped or self-update text rides in that one line as `; ` clauses *(amended 2026-11-19, 34 D-21)*), and changes no tool.
   - Current: no such row; `run_schedule` rejects non-update kinds.
   - Target: a new `JobKind` and a `check-updates` row (daily interval, default start chosen in discuss) dispatched by the runner.
   - Acceptance: `--run-schedule check-updates` in a scratch HOME writes one `ok: N updates available` line and no other schedule-log line; a spy on the update executor shows zero calls; the row appears in the Schedules view and the unit templates for both OSes.

2. **Refresh despite the cache window (NOTIFY-02)**: The scheduled check refreshes versions even when the cache is younger than the 7-day staleness window.
   - Current: `STALE_AFTER = 7 days` (`version_cache.py:44`) makes a daily check read cached values.
   - Target: the check forces a refresh bounded by the 20-fetch cap and anonymous lookups.
   - Acceptance: with a scratch cache aged one day, a run refreshes (a fake fetcher is called) and respects `MAX_FETCHES_PER_REFRESH`; a rate-limited fetch logs a reason and the run still exits ok.

3. **Notify only on change (NOTIFY-03)**: The runner sends one desktop notification only when the set of outdated tools changed since the last run; an unchanged set sends nothing.
   - Current: no notification code.
   - Target: the last notified set is persisted in the installer's state directory and compared as a set.
   - Acceptance: two runs with the same outdated set send one notification (fake notifier); a changed set sends another; a set that shrinks to empty sends none and resets the stored set; a corrupt state file is treated as empty and rewritten.

4. **Linux notification (NOTIFY-04)**: On Linux the notification goes through `notify-send` with the session bus address passed to the child; without `notify-send` the run logs `notify skipped` (as a clause of the result line) and still exits ok.
   - Current: n/a.
   - Target: a notifier that finds `notify-send` on PATH and sets `DBUS_SESSION_BUS_ADDRESS` for the child.
   - Acceptance: a fake `notify-send` on a scratch PATH records the argv and the bus variable; with no `notify-send` the log has `notify skipped` and the exit code is 0.

5. **macOS notification (NOTIFY-05)**: On macOS the notification goes through `osascript display notification`; a failure logs `notify skipped` without failing the run, the row detail names the one-time permission, and the real-Mac check is a UAT line deferred to the owner's Mac.
   - Current: n/a.
   - Target: a notifier that builds the AppleScript string safely and runs `osascript`.
   - Acceptance: a golden test of the generated `osascript` argv passes on both OSes (including a tool name with a quote); a failing fake `osascript` logs `notify skipped` and exits 0; the row detail text names the Script Editor permission; the UAT line is marked deferred.

6. **Installer self-check (NOTIFY-06)**: The check compares `git ls-remote origin main` with the checkout's HEAD and, when the checkout is behind, adds one self-update clause to the result line *(amended 2026-11-19, 34 D-21)*; it makes no API call, uses no token and does not pull.
   - Current: n/a.
   - Target: one `git ls-remote` call with the child's stdin closed, only when the installer runs from a git checkout.
   - Acceptance: a fixture repo whose remote main is ahead adds one self-update clause to the result line and the checkout is byte-identical afterwards (no fetch, pull or checkout); a non-git install or an unreachable remote logs a reason and exits ok.

## Boundaries

**In scope:**
- The `check-updates` row, its runner, the forced refresh, the changed-set rule, the two notifiers, the self-check line, unit templates for both OSes, and tests.
- Recording the 24.2 amendment (below).
- *Amended 2026-11-19 (34 D-22):* tests that list every schedule row gain one entry (`tests/test_schedules.py`, `tests/test_schedules_view.py`, `tests/test_schedules_lifecycle.py`, `tests/test_schedules_handover.py`); assertions about the other rows stay unedited.

**Out of scope:**
- Notifications for failed runs of other schedules — decided in the interview (update check only).
- A click action on the notification — Linux action support differs by desktop and macOS needs a signed helper; not requested.
- A GitHub token in the schedule unit, or `gh auth` use — lookups stay anonymous.
- Updating any tool — that is phase 35.
- Real-Mac checks — UAT lines deferred to the owner's Mac.

## Constraints

- The check changes no tool and writes no file outside the installer's own state and log directories.
- No sudo; children run with stdin closed; the run takes the run lock like other schedules (a held lock gives `skipped: busy`).
- Tests use a scratch HOME and fakes for `notify-send`, `osascript` and the fetcher; no real notification is sent from tests.
- `make validate && make test` pass on the commit.

## Amendment of Phase 24.2

*(amended 2026-11-19, 34 D-01: the 24.2 cut of desktop notifications is reopened for the daily update check only; notifications for failed runs stay out of scope. Owner-approved at the 2026-11-19 ingest gate.)* The statements amended are `24.2-SPEC.md:179` and `24.2-CONTEXT.md:43`.

## Acceptance Criteria

- [ ] `--run-schedule check-updates` writes one `ok: N updates available` line and calls no update executor.
- [ ] A cache younger than 7 days is refreshed by the check, within the 20-fetch cap.
- [ ] Same outdated set twice sends one notification; a changed set sends another; an emptied set sends none.
- [ ] Linux: fake `notify-send` receives the argv and bus address; without it, `notify skipped` and exit 0.
- [ ] macOS: the `osascript` argv golden file passes on both OSes; a failing `osascript` logs `notify skipped` and exits 0; the permission is named in the row detail.
- [ ] A checkout behind `origin/main` logs one self-update line and stays byte-identical.
- [ ] The row appears in the Schedules view and in both OSes' unit templates.

## Edge Coverage

**Coverage:** 20/20 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1 and 7: the new row sits beside the update rows without changing their ids, order or intervals (existing schedule tests unedited) |
| empty | R1 | ✅ covered | Acceptance 1: zero outdated tools logs `ok: 0 updates available` |
| encoding | R1 | ✅ covered | Acceptance 1: the result line is compared byte-exact (`ok: N updates available` plus `; ` clauses), and clause text is sanitized to one line like the update rows' results (schedule_runner _sanitize) |
| ordering | R1 | ✅ covered | Acceptance 7: rows are looked up by id; the new row's position in SCHEDULES never changes another row's behavior |
| idempotency | R1 | ✅ covered | Acceptance 1: two runs in a row write one line each and change no state beyond the stored set (R3) |
| concurrency | R1 | 🧪 backstop | held-out test: a run while the run lock is held logs `skipped: busy` and exits ok, as the update rows do |
| boundary | R2 | ✅ covered | Acceptance 2: a cache aged one second under, exactly at, and one second over 7 days all refresh; the 20-fetch cap is asserted at 20 and 21 tools |
| precision | R2 | ✅ covered | Acceptance 2: the cap and the age are integers and timedeltas compared exactly, with no rounding step |
| concurrency | R2 | 🧪 backstop | held-out test: the TUI's view-entry refresh takes no run lock (only mutations do, 24.2 D-12); two refreshing processes are last-writer-wins with at most one entry lost and the file never corrupted (version_status.py:17-24), healed by the next refresh |
| adjacency | R3 | ✅ covered | Acceptance 3: a set that differs by one tool counts as changed; the same tools in another order do not |
| empty | R3 | ✅ covered | Acceptance 3: an emptied set sends none and resets the stored set; a missing or corrupt state file is empty |
| ordering | R3 | ✅ covered | Acceptance 3: sets compare as sets, so list order never triggers a notification |
| concurrency | R3 | 🧪 backstop | held-out test: the state file is written atomically so an interrupted run never leaves a half-written set |
| adjacency | R4 | ✅ covered | Acceptance 4: a tool list with one or many names produces one notify-send call |
| empty | R4 | ✅ covered | Acceptance 4: no notify-send on PATH logs `notify skipped` and exits 0; an unset bus address is passed as unset, not as an empty string |
| ordering | R4 | ✅ covered | Acceptance 4: the argv order (summary then body) is asserted by the fake |
| empty | R5 | ✅ covered | Acceptance 5: no outdated tools sends no notification, so no empty osascript is built |
| encoding | R5 | ✅ covered | Acceptance 5: quote, backslash and non-ASCII tool names produce a safe AppleScript string (golden test) |
| idempotency | R6 | ✅ covered | Acceptance 6: a second run with the same remote state logs the same one line and still changes nothing in the checkout |
| concurrency | R6 | 🧪 backstop | held-out test: git ls-remote is read-only, so a concurrent user git operation in the checkout is never blocked |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The check MUST NOT install, update, remove or pull anything | 1 | resolved | test: spy on the update executor and a byte-comparison of the checkout |
| The check MUST NOT write a GitHub token or any credential into a unit file, log or state file | 2 | resolved | test: grep of the generated unit text and state for token patterns; lookups are anonymous |
| The notification text MUST NOT carry unescaped tool names into the AppleScript or shell command line | 5 | resolved | test: a tool name containing a quote and a backslash produces a safe argv |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Owner request and roadmap are specific |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Update check only; no click action; anonymous lookups |
| Constraint Clarity | 0.75  | 0.65 | ✓      | Default start time and state file name left to discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Fakes for every external call; Mac check deferred |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The open items went through jev: one advisory answer per item, and `needs_fallback` items are decided by own reasoning. Summaries only, advisory. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Boundary Keeper | OQ-NOTIFY-1: how far to reverse the 24.2 notification cut? | low 0.59 (none_of_these); second rung choice update_check_only 0.98 | Update check only (R1, amendment) |
| 1 | Simplifier | OQ-NOTIFY-2: notify every run or only on change? | low 0.67 (every_run); second rung choice only_on_change 1.00 | Only on change (R3) |
| 1 | Constraint | OQ-NOTIFY-3: token in the unit, `gh auth token`, or anonymous? | low 0.61 (none_of_these); second rung low 0.74 (gh_auth_token_at_run) | **Own reasoning:** anonymous (a daily run of at most 20 fetches fits 60 per hour; no standing secret; a rate limit logs a reason and retries next day) (R2, ledger) |
| 1 | Boundary Keeper | OQ-NOTIFY-4: include the installer self-check? | noul yes 0.77 | Yes (R6; the owner asked for the installer itself to be considered) |
| 1 | Simplifier | OQ-NOTIFY-5: click action? | noul yes 0.81 (contradicts the evidence); second opinion noul no 0.87 | **jev overridden:** no click action (out of scope) |

---

*Phase: 34-daily-update-check-with-a-desktop-notification*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 34 — implementation decisions (how to build what's specified above)*
