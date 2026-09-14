---
phase: "13"
slug: "live-in-tui-install-execution-persistent-wizard-settings-ins"
status: draft
nyquist_compliant: false
wave_0_complete: false
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

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-TBD | 01 | 1 | D-01 | — | Confirming install pushes a new screen, never exits to console | integration (Textual Pilot) | `uv run pytest tests/test_wizard_app.py -k execute_screen -x` | ❌ W0 | ⬜ pending |
| 13-01-TBD | 01 | 1 | D-02 | — | Screen stays visible after completion until keypress | integration (Textual Pilot) | `uv run pytest tests/test_wizard_app.py -k execute_screen -x` | ❌ W0 | ⬜ pending |
| 13-01-TBD | 01 | 1 | D-05.2 | — | Every output line is attributed to a tool, unconditionally | unit | `uv run pytest tests/test_run.py -k streaming -x` | ❌ W0 | ⬜ pending |
| 13-01-TBD | 01 | 1 | D-05.3 | — | A cancelled prompt shows an explicit message, never a silent no-op | integration (Textual Pilot) | `uv run pytest tests/test_wizard_app.py -x` | ❌ W0 | ⬜ pending |
| 13-01-TBD | 01 | 1 | link_mode persistence | — | Round-trip save/load, malformed file degrades safely | unit | `uv run pytest tests/test_settings.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_run.py` — streaming-runner unit tests (fake `Popen`-shaped subprocess via `monkeypatch`, matching this project's existing fake-injection convention)
- [ ] `tests/test_settings.py` — new file for `installer/settings.py` (load/save round-trip, malformed-file degrade — mirror `tests/test_version_cache.py`'s pattern if one exists)
- [ ] `tests/test_wizard_app.py` — extend with new execute-screen Pilot-driven tests (reuse the existing `_settle(app, pilot)` helper)
- [ ] A throwaway (non-committed) spike script proving the `call_from_thread` + `push_screen_wait` combination works as expected — run BEFORE the real plan's tasks are written, per RESEARCH.md's flagged risk

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 75s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
