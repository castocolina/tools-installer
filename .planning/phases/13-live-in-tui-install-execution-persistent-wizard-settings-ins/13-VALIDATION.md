---
phase: "13"
slug: "live-in-tui-install-execution-persistent-wizard-settings-ins"
status: draft
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-14"
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_wizard_app.py -x -q` |
| **Full suite command** | `make test` |
| **Estimated runtime** | ~75 seconds |

---

## Sampling Rate

- **After every task commit:** Run the narrowest test file touched (e.g. `uv run pytest tests/test_run.py -k streaming -x -q`)
- **After every plan wave:** `uv run pytest tests/test_wizard_app.py tests/test_run.py tests/test_settings.py -q`
- **Before `/gsd-verify-work`:** `make test` (full suite) must be green
- **Max feedback latency:** ~75 seconds

---

## Worker-to-modal mechanism

**MECHANISM=A** — `call_from_thread` + `push_screen_wait`.

The Task 1 spike (scratchpad only, not committed) drove a `@work(thread=True)` worker under `app.run_test()` with a real `Pilot` keypress. Mechanism A returned the selected value to the worker thread and printed `MECHANISM=A`. Mechanism A was not rejected: `push_screen(..., wait_for_dismiss=True)` did not raise `NoActiveWorker`, and the modal appeared. Mechanism B was not used.

Plan 13-05's `installer/execute_screen.py::ask_from_worker` implements MECHANISM=A and nothing else.

MECHANISM=A is a documented exception to `.claude/architecture.md` rule 2 ("Modals return results only via `push_screen(modal, callback)`"). Rule 2 governs main-thread callers; a thread worker has no callback to return into. Plan 13-07 Task 1 must name `push_screen_wait` in `.claude/architecture.md` as the checksum-mismatch seam, or a later contributor will read rule 2 and rip it out as a violation.

Plans 13-04 and 13-05 grow `tests/test_execute_screen.py`. The three characterisation tests Task 2 commits — `test_a_thread_worker_receives_the_users_modal_answer`, `test_a_dismissed_modal_gives_the_worker_none`, `test_the_event_loop_keeps_running_while_the_worker_waits` — must keep passing, keep their names, and never be skipped or deleted as that file grows. They are the only pin of this mechanism against a future Textual upgrade; a renamed or removed characterisation test loses that signal silently.

---

## Recorded design decisions

- **DD-1 — Failure handling mid-run: continue, with a per-tool running status list.** A single
  tool's failure does NOT stop the batch. `installer/session.py::run_installs` is already a single
  forward pass whose only stop condition is a blocked `requires` chain, and `Summary` /
  `InstallOutcome` already carry partial outcomes across a batch; fail-fast would need brand-new
  logic in the worker loop for strictly less information. Mid-run **cancel is supported in the
  weak form only**: a keybind stops new tools being queued and lets the in-flight tool finish
  (plan 13-05). Killing an in-flight child process is explicitly out of scope — it means owning
  `subprocess` lifecycle/`terminate()` semantics this phase's other primitives never need.
- **DD-2 — Settings scope and location: `link_mode` only, folded into `PoliciesScreen`.** Default
  shell preference and headless-flag defaults are NOT raised as bugs by this phase's CONTEXT.md
  and are out of scope. The adjustment UI is a new `m` binding on the existing `PoliciesScreen`
  plus a `LinkModeScreen` modal — structurally a near-copy of the already-shipped
  `TimePickerScreen` + `action_pick_time` + `_time_picked` trio (`installer/wizard_app.py`
  1232-1290, 1353-1386). That needs **zero** `installer/ui_common.py::VIEWS` rows, so it cannot
  create a second navigation mechanism (`.claude/architecture.md` rules 1 and 2). A dedicated
  Settings view would add a seventh number key and a seventh palette entry for one three-valued
  string — unjustified at this scope.
- **DD-3 — CLI flag vs persisted setting: `--link-mode` overrides for that run ONLY and never
  overwrites the stored value.** Principle of least surprise: a one-off override must not silently
  rewrite the user's standing preference. An explicit in-TUI change through the picker always
  persists, because that is the user asking for a new standing preference.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-T2 | 01 | 1 | D-03 / D-05.3 | T-13-06, T-13-07 | A thread worker receives the user's modal answer (or `None` on dismiss) without blocking the event loop | characterisation (Textual Pilot) | `uv run pytest tests/test_execute_screen.py -q` | ✅ | ✅ green |
| 13-02-T1 | 02 | 2 | D-05.2 | — | Every output line is attributed to a tool, unconditionally | unit | `uv run pytest tests/test_run.py -q` | ✅ | ⬜ pending |
| 13-03-T1 | 03 | 2 | link_mode persistence | — | Round-trip save/load, malformed and tampered files degrade safely | unit | `uv run pytest tests/test_settings.py -q` | ❌ created by 13-03 | ⬜ pending |
| 13-03-T2 | 03 | 2 | link_mode persistence | — | Precedence functions and `SettingsStore` | unit | `uv run pytest tests/test_settings.py -q` | ❌ created by 13-03 | ⬜ pending |
| 13-04-T1 | 04 | 3 | D-01 / D-02 / D-03 | — | Confirming install pushes a new screen, never exits to console; screen stays visible after completion until keypress | integration (Textual Pilot) | `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py -q` | ✅ | ⬜ pending |
| 13-04-T3 | 04 | 3 | D-05.1 | — | Visible pre-flight is on screen before any subprocess runs | integration (Textual Pilot) | `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py -q` | ✅ | ⬜ pending |
| 13-05-T1 | 05 | 4 | D-05.3 | T-13-06 | A cancelled prompt shows an explicit message, never a silent no-op | integration (Textual Pilot) | `uv run pytest tests/test_execute_screen.py -q` | ✅ | ⬜ pending |
| 13-06-T2 | 06 | 5 | D-05.3 | — | Link-mode picker and first-run cases on the Policies view | integration (Textual Pilot) | `uv run pytest tests/test_wizard_app.py -q` | ✅ | ⬜ pending |
| 13-06-T3 | 06 | 5 | D-05.3 | — | First-run link-mode prompt inside the app | integration (Textual Pilot) | `uv run pytest tests/test_wizard_app.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

This project's `CLAUDE.md` requires `make test` green on the exact tree being committed, so a committed-red test file is not available as a Wave 0 device and the RED step lives inside each owning task instead.

- [x] `tests/test_run.py` streaming-runner unit tests — plan 13-02, Task 1 (`StreamingRunner`, its `<behavior>` list, and `uv run pytest tests/test_run.py -q`).
- [x] `tests/test_settings.py` — plan 13-03, Task 1 (envelope round-trip, malformed and tampered degrade) and Task 2 (precedence functions and `SettingsStore`).
- [x] `tests/test_wizard_app.py` execute-screen Pilot tests — plan 13-04, Task 1 (the tracer's push-not-exit and stay-until-keypress assertions) and Task 3 (the pre-flight-before-subprocess assertions), with the screen's own cases living in `tests/test_execute_screen.py` because `installer/execute_screen.py` is the unit under test; plan 13-06, Tasks 2 and 3 add the link-mode picker and first-run cases to `tests/test_wizard_app.py`.
- [x] The throwaway spike — this plan (13-01), Task 1, the only Wave 0 item this plan discharges itself.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 75s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** recorded — autonomous run
