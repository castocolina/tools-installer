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
> Seeded from 34-RESEARCH.md "Validation Architecture" and the orchestrator decisions of 2026-11-21 (all provisional, "needs confirmation"). The task rows below are placeholders keyed to NOTIFY-01 to NOTIFY-06: the planner replaces each `34-PP-TT` id with the real plan, wave and task ids and keeps the automated command and the secure behavior.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage, pytest-asyncio for Textual pilots); fake `notify-send` / `osascript` scripts on a tmp `PATH` with `which` and `run` injected; real `git` against bare repos in `tmp_path` for the self-check |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); worker cap and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan; never chained with `make validate` at a commit) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof (orchestrator only)** | `scripts/container-e2e-verify.sh schedules`, extended by the orchestrator with a `check-updates` pair (`tests/e2e_schedules_driver.py`); never executor-run; it cannot prove the bus variable reaches `notify-send` (decision 9). A host test with a stubbed runtime is the minimum if the plan size forces a choice |
| **Estimated runtime** | ~30 seconds per targeted run (the quick list below is about thirteen files; confirm in the first plan) |

Files the quick command draws from (research "Validation Architecture"): `tests/test_notify.py` (new), `tests/test_update_check.py` (new), `tests/test_schedules.py`, `tests/test_schedules_engine.py`, `tests/test_schedules_lifecycle.py`, `tests/test_schedules_handover.py`, `tests/test_schedules_view.py`, `tests/test_schedule_update.py`, `tests/test_schedule_runner.py`, `tests/test_cli.py`, `tests/test_version_status.py`, `tests/test_version_cache.py`, `tests/test_run.py`. Also read by this phase: `tests/test_reachability.py`, `tests/test_shell_scripts_path.py`, `tests/test_docs.py`, `tests/test_docs_only.py` (a `.claude/` or ROADMAP edit is read-test territory).

Constraints on every new test (orchestrator decision 12, lessons of phases 27 to 33):

- Every notifier test injects `which` and `run`; fake binaries only, never the real `notify-send` or `osascript` (the dev host and the CI runners carry them). Isolate `PATH`, scratch `HOME`, and clear `DBUS_SESSION_BUS_ADDRESS` and `XDG_RUNTIME_DIR` (Pitfall 3).
- Unit tests never launch real `gh`; `git` is launched only in the NOTIFY-06 fixtures, with `GIT_CONFIG_GLOBAL=/dev/null`-style isolation, fixed author variables and `file://` remotes (the sandbox forbids `git` elsewhere: use fakes).
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
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green; the container proof `scripts/container-e2e-verify.sh schedules` with the `check-updates` pair recorded in VERIFICATION (or "not run" with the reason, never a pass); the manual-only rows below carried as deferred items
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are placeholders (`34-PP-TT`: plan, task); the planner assigns plan, wave and task ids. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). Threat refs are placeholders for the planner's threat model: T-34-01 option or markup injection through a tool name in `notify-send`; T-34-02 AppleScript source injection; T-34-03 planted symlink or FIFO at `update-check.json`; T-34-04 git steered by user config or repo env; T-34-05 token leak into unit, state or log; T-34-06 rate-limit exhaustion hiding real updates; T-34-07 lock-screen disclosure of tool names (accepted, ids only).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 34-PP-01 | TBD | TBD | NOTIFY-04, NOTIFY-05 | T-34-01, T-34-02 | `tests/test_notify.py`: the fake `notify-send` records an argv with `--` before summary and body, ids only in the body (never free text); `DBUS_SESSION_BUS_ADDRESS` is passed when set, stays unset (never empty) when not, and is derived from `XDG_RUNTIME_DIR` as `unix:path=$XDG_RUNTIME_DIR/bus`; a missing binary maps to `notify skipped`, exit ok; golden osascript argv with `"`, `\` and non-ASCII data carried as `argv` with a constant script source and no `--` (decision 4); a failing fake maps to `notify skipped`, never a failed run | unit | `uv run pytest tests/test_notify.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 34-PP-02 | TBD | TBD | NOTIFY-04 | T-34-01 | `_PASSED_ENV` of the runner carries `DBUS_SESSION_BUS_ADDRESS` and nothing outside `ENVIRONMENT_KEYS` (the `/run/user/*` rule at `installer/schedules.py:442-446` and `daemon.check_environment` stays enforced, decision 3); a runner log with the variable unset has no empty value | unit | `uv run pytest tests/test_notify.py tests/test_schedule_runner.py --no-cov -q` | ❌ W0 (`test_notify.py`) / ✅ exists (extend) | ⬜ pending |
| 34-PP-03 | TBD | TBD | NOTIFY-03 | T-34-03 | `tests/test_update_check.py`: the same outdated set twice notifies once; a changed set notifies again (a shrinking non-empty set included, D-15, decision 6); an emptied set sends nothing and resets; order does not matter; a corrupt, missing or wrong-typed `update-check.json` reads as empty and is rewritten (every element type-checked, read with `read_capped(..., follow_symlinks=False)`, written with `atomic_write_text`); a failed notification does not store the set | unit (fake `Notifier`) | `uv run pytest tests/test_update_check.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 34-PP-04 | TBD | TBD | NOTIFY-02 | T-34-06 | A cache aged 1 day and one aged 7 days minus 1 s, 0 and plus 1 s all refresh when the scheduled check asks (the `stale_after` plumbing at every listed site; the interactive 7-day window unchanged); 20 eligible tools fetch and 21 stop at the cap; a rate-limited fetch gives `; N lookups failed: reason` and exit ok through the sink in `_latest_status`'s except branch (decision 8: `resolve_tag` is not wrapped); the saved cache entry keeps the asset digests | unit | `uv run pytest tests/test_version_status.py tests/test_version_cache.py tests/test_update_check.py --no-cov -q` | ✅ exists (extend) / ❌ W0 (`test_update_check.py`) | ⬜ pending |
| 34-PP-05 | TBD | TBD | NOTIFY-01 | T-34-05 | `run_schedule("check-updates")` returns `ok: N updates available` and makes zero update-executor calls (spy); a held lock gives `skipped: busy`; the tmp and cache refusal is unchanged; any `notify skipped`, lookup-failure or self-update text rides in the one result line as `; ` clauses, each through `sanitize_log_line`; `RunDeps` gains the new field with a default so `tests/test_schedule_update.py:193` is untouched (decision 2) | unit | `uv run pytest tests/test_update_check.py tests/test_schedule_update.py --no-cov -q` | ❌ W0 / ✅ exists (extend) | ⬜ pending |
| 34-PP-06 | TBD | TBD | NOTIFY-01 | T-34-05 | The runner log is exactly `start` plus one `ok:` line through `schedule_runner.main(["check-updates", "--installer", ..., "--uv", fake_uv, ...])`; a grep test over the unit text, the state file and the log finds no token or credential (D-23) | unit | `uv run pytest tests/test_schedule_runner.py -k check_updates --no-cov -q` | ✅ exists (extend; helpers `_checkout`, `_script`) | ⬜ pending |
| 34-PP-07 | TBD | TBD | NOTIFY-01 | T-34-07 | The row sits in the `SCHEDULES` tuple with label, target, default on, systemd unit texts, launchd plist `ProgramArguments`, `OnCalendar` `*-*-* 09:00:00` and the `daily` sites; the unit files stay `0600` (`_UNIT_MODE`) | unit | `uv run pytest tests/test_schedules.py tests/test_schedules_engine.py tests/test_cli.py --no-cov -q` | ✅ exists (edit) | ⬜ pending |
| 34-PP-08 | TBD | TBD | NOTIFY-01 | — | Decision 1: Schedules table CSS `max-height: 9` (confirmed first with a pilot test) so the eighth row shows without scrolling; every edit the eighth row forces is a listed exception with its exact reason and keeps each assertion's meaning (D-22): `tests/test_schedules_lifecycle.py` lines 104, 110, 548, 600, 654, `tests/test_schedules_handover.py` lines 62 and 494, `tests/test_schedules_view.py:677-679`, and the `reconcile_lines` text that becomes `..., claude update, update check.`; assertions about the other rows stay | unit + Textual pilot | `uv run pytest tests/test_schedules_lifecycle.py tests/test_schedules_handover.py tests/test_schedules_view.py --no-cov -q` | ✅ exists (edit) | ⬜ pending |
| 34-PP-09 | TBD | TBD | NOTIFY-05 | — | The check-updates row detail names the one-time Script Editor permission on macOS; the view and detail text states D-15 (a shrinking set notifies again), the brew-index limit (decision 7) and the late-notification limit at login (decision 11) | unit + Textual pilot | `uv run pytest tests/test_notify.py tests/test_schedules_view.py --no-cov -q` | ❌ W0 / ✅ exists (extend) | ⬜ pending |
| 34-PP-10 | TBD | TBD | NOTIFY-06 | T-34-04 | Bare-repo fixture ahead of the checkout adds one self-update clause and the checkout bytes stay identical (no pull, no API call, no token); an ancestor remote is not behind; a non-git directory, an unreachable remote, a missing `main` ref and a detached HEAD or a branch other than `main` each give `installer check skipped` (decision 5: no line, no error); `git ls-remote` runs through `run_git_isolated` with `core.hooksPath=/dev/null`, no prompts, a `BatchMode` ssh command; the `ls-remote` ref match is exact, not a suffix match (Pitfall 9) | unit (real `git` in `tmp_path`) | `uv run pytest tests/test_update_check.py -k installer --no-cov -q` | ❌ W0 | ⬜ pending |
| 34-PP-11 | TBD | TBD | NOTIFY-01 to NOTIFY-06 | — | The new modules are imported by a production entry point in the plan that adds them or the next (reachability guard); `.claude/architecture.md` gains a short Phase 34 subsection and the ROADMAP success criterion 5 is amended with a dated note (decision 10); the rule-document tests stay green | docs + gate | `uv run pytest tests/test_reachability.py tests/test_docs.py tests/test_docs_only.py --no-cov -q` | ✅ exists | ⬜ pending |
| 34-PP-12 | TBD | TBD | NOTIFY-01 | — | `tests/e2e_schedules_driver.py` and `scripts/container-e2e-verify.sh` gain the `check-updates` pair (orchestrator-run, decision 9); the classified PATH lines of `tests/test_shell_scripts_path.py` move in the same commit as any usage-text change | unit (host) + container (orchestrator) | `uv run pytest tests/test_shell_scripts_path.py --no-cov -q`; then `scripts/container-e2e-verify.sh schedules` (orchestrator only) | ✅ exists (edit) | ⬜ pending |
| 34-PP-13 | TBD | TBD | NOTIFY-01 to NOTIFY-06 | — | Phase gate: `make validate` then `make test`, once each, green on the final tree (never chained at a commit) | gate | `make validate` then `make test` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every test file is created or extended inside the task that needs it (test-first inside one green commit), so there is no separate scaffold task:

- [ ] `tests/test_notify.py` — new; NOTIFY-04, NOTIFY-05 (argv, env, exit mapping, injection data)
- [ ] `tests/test_update_check.py` — new; NOTIFY-01 (dispatch, spy), NOTIFY-02 (windows, cap, failure sink, digests), NOTIFY-03 (set rules), NOTIFY-06 (git fixtures)
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
