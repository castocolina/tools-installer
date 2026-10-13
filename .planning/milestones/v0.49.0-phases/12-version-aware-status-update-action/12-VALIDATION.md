---
phase: "12"
slug: "version-aware-status-update-action"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-07"
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (`pyproject.toml:46-48`, `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_versions.py tests/test_manager_versions.py tests/test_wizard_app.py -k "version or outdated or update" -q` |
| **Full suite command** | `uv run pytest --cov` |
| **Estimated runtime** | ~15s quick / ~90s full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_versions.py tests/test_manager_versions.py tests/test_wizard_app.py -k "version or outdated or update" -q`
- **After every plan wave:** Run `uv run pytest --cov`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds (no real network/subprocess calls in tests — every manager/GitHub-API call is a DI seam, per 12-RESEARCH.md)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | REQ-version-aware-status-github, REQ-cached-timestamped-version-state | T-12-01 | Cache file created with restrictive perms; no code execution from cached data | unit | `uv run pytest tests/test_versions.py -k "extract_observed_version or is_outdated or version_cache" -q` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | REQ-background-version-refresh-worker | T-12-02 | Network failure degrades to unknown, never crashes | unit+pilot | `uv run pytest tests/test_wizard_app.py -k "version_refresh or off_the_event_loop" -q` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | REQ-manager-version-resolution | T-12-03 | Subprocess argv is a fixed list, never shell-interpolated | unit | `uv run pytest tests/test_manager_versions.py -q` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 3 | REQ-update-action-manager-delegation | T-12-04 | Update delegates to the tool's real manager; never runs an install method the registry didn't declare | unit+pilot | `uv run pytest tests/test_wizard_app.py tests/test_uninstall.py -k "update" -q` | ❌ W0 | ⬜ pending |
| 12-04-01 | 04 | 4 | REQ-manager-drift-alerting (stretch) | T-12-05 | Drift check reads only declared registry data, never guesses an undeclared formula name | unit | `uv run pytest tests/test_manager_versions.py -k "drift" -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_versions.py` — extend with stubs for `extract_observed_version`, `is_outdated`, version-cache read/write/staleness (REQ-version-aware-status-github, REQ-cached-timestamped-version-state)
- [ ] `tests/test_manager_versions.py` — new file, stubs for `brew_outdated`/`pnpm_outdated_global`/`uv_tool_outdated` parsers (REQ-manager-version-resolution)
- [ ] `tests/test_wizard_app.py` — extend with stubs for the version-refresh worker and update-action worker, reusing the existing `_app()`/`_settle()` fixtures (REQ-background-version-refresh-worker, REQ-update-action-manager-delegation)

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification. Every live call this phase makes (GitHub API, `brew`/`pnpm`/`uv` subprocesses) is a DI seam already proven testable by existing analogs (`resolve_github_tag`'s `Fetch` param, `installer/run.py`'s `Runner`/`OutputRunner`, `tests/test_wizard_app.py`'s `_app(node_globals=...)` factory).*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
