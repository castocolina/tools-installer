---
phase: "34"
slug: "daily-update-check-with-a-desktop-notification"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-21"
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 34-RESEARCH.md "Validation Architecture" and the orchestrator decisions of 2026-11-21 (all provisional, "needs confirmation"). The per-task map below was filled from the eight plans by the planner on 2026-11-21.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage, pytest-asyncio for Textual pilots); fake `notify-send` / `osascript` scripts on a tmp `PATH` with `which` and `run` injected; a fake `git` callable for the self-check (the test sandbox refuses launching `git` and `gh`; `git_for_check` is proven by patching `subprocess.run`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); worker cap and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan; never chained with `make validate` at a commit) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof (orchestrator only)** | `scripts/container-e2e-verify.sh schedules`, extended by the orchestrator with a `check-updates` pair (`tests/e2e_schedules_driver.py`); never executor-run; it cannot prove the bus variable reaches `notify-send` (decision 9). A host test with a stubbed runtime is the minimum if the plan size forces a choice |
| **Estimated runtime** | ~30 seconds per targeted run (the quick list below is about thirteen files; confirm in the first plan) |

Files the quick command draws from (research "Validation Architecture"): `tests/test_notify.py` (new), `tests/test_update_check.py` (new), `tests/test_schedules.py`, `tests/test_schedules_engine.py`, `tests/test_schedules_lifecycle.py`, `tests/test_schedules_handover.py`, `tests/test_schedules_view.py`, `tests/test_schedule_update.py`, `tests/test_schedule_runner.py`, `tests/test_cli.py`, `tests/test_version_status.py`, `tests/test_version_cache.py`, `tests/test_run.py`. Also read by this phase: `tests/test_reachability.py`, `tests/test_shell_scripts_path.py`, `tests/test_docs.py`, `tests/test_docs_only.py` (a `.claude/` or ROADMAP edit is read-test territory).

Constraints on every new test (orchestrator decision 12, lessons of phases 27 to 33):

- Every notifier test injects `which` and `run`; fake binaries only, never the real `notify-send` or `osascript` (the dev host and the CI runners carry them). Isolate `PATH`, scratch `HOME`, and clear `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` (Pitfall 3).
- Unit tests never launch real `gh` or `git` (the sandbox refuses both, orchestrator decision 12): every NOTIFY-06 test drives `installer_behind` through a fake `git` callable returning canned output or raising `CommandError`; the real-git byte-identity of a checkout is an owner or orchestrator observation (manual-only row below), not a unit test.
- No timing-sensitive assertions (cache-window boundaries use an injected clock, `-1 s / 0 / +1 s`); xdist-safe (`tmp_path`, `monkeypatch`, no fixed path, port or order); holds on Python 3.12 and 3.15 and macOS bash 3.2 where a shell is involved (no apostrophes or unbalanced quotes inside a heredoc inside `$(...)`).
- The golden osascript argv test runs on `ubuntu-latest` and `macos-latest` without calling `osascript`.
- A Textual pilot waits with `tests/screen_family.wait_until`, never one `pilot.pause()`.
- A module added in a plan is imported by a production entry point in that plan or the next (`tests/test_reachability.py`).
- Any usage-text change of `scripts/container-e2e-verify.sh` moves the classified PATH line numbers of `tests/test_shell_scripts_path.py` in the same commit.
- Each plan stays under about 50 KB of executor-visible text with at most two large tasks.

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan wave:** the quick-run files above
- **After every plan:** `make validate` once, then `make test` once, on the final tree (plan 34-04 runs the full suite with the one reachability test deselected: `installer/update_check.py` is wired by plan 34-05, owner rule 4)
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green; the container proof `scripts/container-e2e-verify.sh schedules` with the `check-updates` pair recorded in VERIFICATION (or "not run" with the reason, never a pass); the manual-only rows below carried as deferred items
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are `34-<plan>-<task>`; the eight plans run in strictly sequential waves 1 to 8. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row); plan 34-04 runs the full suite with the one reachability test deselected, because `installer/update_check.py` is wired by plan 34-05 (owner rule 4: the strict guard is red for exactly that plan and names only that module). Threat refs are the plans' own IDs: T-34-01 option or markup injection through a tool name in `notify-send`; T-34-02 AppleScript source injection; T-34-03 planted symlink, FIFO or oversized file at `update-check.json`; T-34-04 git steered by user config or repo env; T-34-05 token leak into unit, state or log (registered in 34-01, state part proven in 34-04, log part in 34-05); T-34-06 rate-limit exhaustion hiding real updates; T-34-07 lock-screen disclosure of tool names (accepted, ids only); T-34-08 session bus address passed by the runner (accepted); T-34-09 skip-reason text in the result line; T-34-10 digests lost from the saved cache entry; T-34-11 remote sha in later git argv; T-34-12 the check writes into or pulls the checkout; T-34-13 a hung check holds the run lock; T-34-14 the container check mutates the host; T-34-15 notified path joins the swept artifacts; T-34-16 unvetted `--run-schedule` id; T-34-17 a row whose runner argv the runner cannot parse.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 34-01-01 | 01 | 1 | NOTIFY-01 | T-34-05, T-34-15 | The `check-updates` row is registered last, daily, on by default; its Linux unit has `OnCalendar=*-*-* 09:00:00` and the runner argv, its macOS plist one 09:00 entry; no token name or value in the unit or plist; `retime` forces interval 24; `update-check.json` is swept with the state artifacts; every listed pin edit keeps its assertion's meaning; table `max-height: 9` shows eight rows | unit + Textual pilot | `uv run pytest tests/test_schedules.py tests/test_schedules_engine.py tests/test_schedules_lifecycle.py tests/test_schedules_handover.py tests/test_schedules_view.py -n auto -q --no-cov` | exists (edit) / new tests in existing files | pending |
| 34-01-02 | 01 | 1 | NOTIFY-01 | - | The five hard-coded daily sites of the screen read `schedule.daily`; the check row shows `24h 09:00`, `times: daily at 09:00 (local)` and a daily-only time editor; tmp cleanup's own behavior is unchanged | Textual pilot | `uv run pytest tests/test_schedules_view.py tests/test_schedules.py tests/test_schedules_engine.py -n auto -q --no-cov`; then `make validate`; `make test` | exists (edit) | pending |
| 34-02-01 | 02 | 2 | NOTIFY-04, NOTIFY-05 | T-34-01, T-34-02, T-34-09 | `tests/test_notify.py`: the Linux argv is `[notify-send, --app-name=tools-installer, --urgency=normal, --, summary, body]`; the macOS argv has constant AppleScript source and the title and body as the last two argv items, no `--`; the bus address is passed when set, derived from the runtime dir when that is a socket, else removed, never empty; a missing binary and every failure map to one sanitized reason of at most 300 characters; `RunDeps.notify` defaults to a notifier that cannot reach the host; `setup` wires `notifier_for(platform.os)`; the reachability guard stays green | unit (injected `which` and `run`, one fake script under `tmp_path`) | `uv run pytest tests/test_notify.py tests/test_schedule_update.py tests/test_reachability.py -n auto -q --no-cov` | new (`tests/test_notify.py`) / exists (extend) | pending |
| 34-02-02 | 02 | 2 | NOTIFY-04 | T-34-08 | The runner passes `DBUS_SESSION_BUS_ADDRESS` and no token variable to its child; an unset variable stays unset; the variable is not in `daemon.ENVIRONMENT_KEYS` and `check_environment` still rejects it in a unit environment | unit | `uv run pytest tests/test_schedule_runner.py tests/test_daemon.py tests/test_notify.py tests/test_schedule_update.py tests/test_reachability.py -n auto -q --no-cov`; then `make validate`; `make test` | exists (extend) | pending |
| 34-03-01 | 03 | 3 | NOTIFY-02 | T-34-06, T-34-10 | `refresh(tools, stale_after=..., on_failure=...)`: a cache aged 1 day and 7 days minus 1 s, 0 and plus 1 s all refresh with the 20 hour window while the default window stays 7 days; 20 and 21 eligible tools stop at the cap; a rate-limited fetch reaches the sink and the run continues with `failed_at` stamped and 6 hour backoff; the production resolver's digests survive (no `resolve_tag` wrapper); `cache_path` is exposed | unit | `uv run pytest tests/test_version_cache.py tests/test_version_status.py -n auto -q --no-cov` | exists (extend) | pending |
| 34-03-02 | 03 | 3 | NOTIFY-03 | - | `outdated_ids(states)` keeps present tools whose `version.outdated is True` (a BROKEN state counts, a CHECKING, MISSING or UNAVAILABLE state and `None` never do), independent of order and duplicates | unit | `uv run pytest tests/test_version_status.py tests/test_version_cache.py -n auto -q --no-cov`; then `make validate`; `make test` | exists (extend) | pending |
| 34-04-01 | 04 | 4 | NOTIFY-06 | T-34-04, T-34-11, T-34-12 | `installer_behind` over a fake git: behind, not behind (equal, ancestor), diverged, detached HEAD or another branch silent, non-git, missing git, unreachable remote, missing or suffix-only main ref, malformed sha; only `rev-parse`, `ls-remote`, `cat-file` and `merge-base` are issued; the checkout tree is byte-identical; `git_for_check` is isolated, 20 s, in the caller's group, `BatchMode`; `run_git_isolated` keywords leave the default call unchanged | unit (fake git, patched `subprocess.run`) | `uv run pytest tests/test_update_check.py tests/test_run.py tests/test_setup.py -n auto -q --no-cov` | new (`tests/test_update_check.py`) / exists (extend) | pending |
| 34-04-02 | 04 | 4 | NOTIFY-01, NOTIFY-02, NOTIFY-03 | T-34-03, T-34-05 | `run_check`: one line `ok: N updates available` with ordered `; ` clauses (lookups, installer, notify, notified set), `ok: 0` sends nothing; the same set twice notifies once, a changed or shrinking non-empty set notifies again, an emptied set resets; a corrupt, oversized or symlinked state file is empty and rewritten; a failed notification stores nothing; the state file holds sorted ids only and no token; tools are refreshed oldest-checked first; a real `VersionRefreshService` drives the check and only the notified set is written; the reachability guard is red for `installer.update_check` only | unit (fake refresher, notifier, git; one real service) | `uv run pytest tests/test_update_check.py tests/test_run.py tests/test_version_status.py -n auto -q --no-cov`; the guard's failure names `installer.update_check`; `make validate`; the full suite with that one test deselected | exists (extend) | pending |
| 34-05-01 | 05 | 5 | NOTIFY-01 | T-34-13, T-34-16, T-34-05 | `schedule_runner.main(["check-updates", ...])` writes exactly `start` plus one `ok:` line (two runs, one pair each), keeps only the child's last result line, names the check in its timeout, skips busy, exits 2 on a bad argv; a token in the parent environment reaches neither the child nor the log; `--run-schedule` accepts `check-updates` and still rejects tmp and cache cleanup | unit | `uv run pytest tests/test_schedule_runner.py tests/test_cli.py tests/test_schedules.py -n auto -q --no-cov` | exists (extend) | pending |
| 34-05-02 | 05 | 5 | NOTIFY-01 | T-34-05 | `run_schedule("check-updates")` returns `ok: N updates available` with the spy `UpdateService` at zero runs and the recording runner at zero calls; a manual run takes, honors and releases the run lock (`skipped: busy`); tmp and cache cleanup keep the exact refusal; an unwired check fails loudly; `setup` wires the shared refresh service and `git_for_check`; the reachability guard is green again | unit | `uv run pytest tests/test_schedule_update.py tests/test_update_check.py tests/test_schedule_runner.py tests/test_reachability.py tests/test_cli.py tests/test_setup.py -n auto -q --no-cov`; then `make validate`; `make test` | exists (extend) | pending |
| 34-06-01 | 06 | 6 | NOTIFY-01, NOTIFY-05 | T-34-07 | The check row's target reads `installed`; its detail names the what-text, `notify-send` on Linux, the Script Editor permission (one line) on macOS, and the `limits:` line (shrinking list notifies again, brew index, a day late); no tool id appears | Textual pilot | `uv run pytest tests/test_schedules_view.py tests/test_schedules.py -n auto -q --no-cov` | exists (extend) | pending |
| 34-06-02 | 06 | 6 | NOTIFY-03 | - | `.claude/architecture.md` gains the Phase 34 subsection and `tests/test_docs.py` pins its phrases; ROADMAP criterion 5 is amended with a dated note; the rule-document lint and the docs-only ledger stay green | docs + gate | `uv run pytest tests/test_docs.py tests/test_docs_only.py tests/test_schedules_view.py -n auto -q --no-cov`; then `make validate`; `make test` | exists (extend) | pending |
| 34-07-01 | 07 | 7 | NOTIFY-01 | T-34-14 | `scripts/container-e2e-verify.sh` runs, verifies and removes the `check-updates` unit with the other built-ins; host tests pin the three loops and the driver argv; no container is started by the executor; the classified PATH lines hold | unit (host, stubbed seams) + container (orchestrator only, after this plan) | `uv run pytest tests/test_container_e2e_schedules.py tests/test_shell_scripts_path.py tests/test_schedules_engine.py -n auto -q --no-cov`; then `make validate`; `make test`; orchestrator: `scripts/container-e2e-verify.sh schedules` | exists (edit) | pending |
| 34-08-01 | 08 | 8 | NOTIFY-01 to NOTIFY-06 | T-34-17 | Every row's runner argv parses through the runner's `_parse` with the row's own id on both OSes; `RUN_SCHEDULE_IDS` is exactly the update and check rows; the phase 35 contract and the runner environment (`{LANG, DBUS_SESSION_BUS_ADDRESS}` beyond `ENVIRONMENT_KEYS`) are pinned; the new modules name no escalation word, token variable or `subprocess` import; phase-final `make validate` and `make test` | unit + gate | `uv run pytest tests/test_update_check_contract.py tests/test_schedules_engine.py tests/test_reachability.py tests/test_schedule_runner.py tests/test_schedules.py -n auto -q --no-cov`; then `make validate`; `make test` | new (`tests/test_update_check_contract.py`) | pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every test file is created or extended inside the task that needs it (test-first inside one green commit), so there is no separate scaffold task:

- [ ] `tests/test_notify.py` — new; NOTIFY-04, NOTIFY-05 (argv, env, exit mapping, injection data)
- [ ] `tests/test_update_check.py` — new; NOTIFY-01 (dispatch, spy), NOTIFY-02 (windows, cap, failure sink, digests), NOTIFY-03 (set rules), NOTIFY-06 (fake git)
- [ ] hermetic fixtures: scratch `HOME`, cleared `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR`, a `fake_bin` helper writing executable scripts that log argv and env (pattern: `_script` / `_recorder` in `tests/test_schedule_runner.py:221-` and `_checkout` at `:557`)
- [ ] edits to the existing row-listing tests (the checklist in decision 1 and the research) and the layout test (Pitfall 1)

Framework install: none.

---

## Manual-Only Verifications

Nothing here is run by an agent on the real host: no timer, unit or notification is installed or shown on the developer's machine. The rows are deferred owner UAT items; VERIFICATION carries them as `human_needed`, never as a pass.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real notification appears on the Bazzite desktop (title, ids-only body, no markup artifacts) | NOTIFY-04 | The suite uses fake binaries; only a real session shows a real notification, and a real notification on the host is forbidden for agents | Owner, from a throwaway outdated set on the real session: run `--run-schedule check-updates` and confirm the notification, then a second run with the same set shows none (NOTIFY-03); record in VERIFICATION |
| The session bus address reaches `notify-send` from a systemd user unit on a real session (the user manager exports `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR`; the runner strips both and `_PASSED_ENV` restores one) | NOTIFY-04 | Needs a real user manager and session bus; the container proof cannot show it (decision 9) | Owner: enable the row, `systemctl --user start` its service once, then read the log for `ok:` with no `notify skipped` clause and see the notification |
| Real-Mac `osascript display notification`, including the one-time permission prompt attributed to Script Editor | NOTIFY-05 | macOS behavior is unverifiable on this host (LOW confidence; Pitfall 7) and an agent never runs it | Owner on a real Mac: trigger the check, grant the permission when asked, confirm the notification; record the macOS version |
| A silently dropped notification (macOS `osascript` exits 0 and shows nothing when the permission is missing, focus mode, or the launching app is not allowed) cannot be detected by exit code | NOTIFY-05 | The exit code carries no signal; the row detail names the permission as the only mitigation | Owner on a real Mac: with the permission denied, confirm the run still logs `ok:` and the row detail text names the permission; VERIFICATION states the limit |
| The daily timer fires on both OSes (systemd `OnCalendar` `*-*-* 09:00:00` with a login catch-up, launchd calendar interval) and writes one `ok:` line per day | NOTIFY-01 | Needs real timers over a day boundary on a real Linux user session and a real Mac | Owner, one day after enabling: read the shared schedule log for one `start` and one `ok:` line per day on each OS; a catch-up run at login can precede the notification daemon, so a notification may arrive a day late (accepted, decision 11) |
| First real installer self-update clause on an end-user shallow clone (install from a tag or another branch gives no line) | NOTIFY-06 | Depends on a real remote ahead of a real checkout and on the shallow-clone shape of `install.sh` (Pitfall 10) | Owner: with a checkout on `main` behind `origin/main`, run the check and confirm one clause and an unchanged checkout; on a detached HEAD confirm no clause and no error (decision 5) |
| Brew-owned tools can be under-reported because the query runs with `HOMEBREW_NO_AUTO_UPDATE=1` and the check never runs `brew update` | NOTIFY-02 | An accepted limit of the local brew index (decision 7), not a testable defect | Stated in the docs and VERIFICATION; backlog item |
| Container proof of the `check-updates` pair | NOTIFY-01 | Orchestrator-run only (decision 9), after the plan that adds the pair | Orchestrator: `scripts/container-e2e-verify.sh schedules` in a disposable container, removed afterwards; record the output in VERIFICATION, or "not run" with the reason |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
