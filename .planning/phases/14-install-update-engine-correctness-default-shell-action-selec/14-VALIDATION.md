---
phase: "14"
slug: "install-update-engine-correctness-default-shell-action-selec"
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-09-14"
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml:46-49`), `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`/`[tool.coverage.report]`) |
| **Quick run command** | `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q` |
| **Full suite command** | `make test` |
| **Estimated runtime** | ~60-120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_deps.py tests/test_engine.py tests/test_execute_screen.py tests/test_catalog_tui.py -x -q`
- **After every plan wave:** Run `make test`
- **Before `/gsd-verify-work`:** Full suite must be green (`make validate && make test`)
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

No REQ-IDs were supplied for this phase (CONTEXT.md/ROADMAP.md describe it narratively). The map below is keyed to CONTEXT.md's D-01 through D-07 instead.

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-01 | Selecting an outdated, installed, selected tool via the main flow triggers `UpdateService.run` | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k outdated -x` | ❌ W0 | ⬜ pending |
| D-01 (resolver layer) | `resolve_dependencies` contract stays unchanged — new split logic lives one layer up | unit | `uv run pytest tests/test_deps.py -x` | ✅ | ⬜ pending |
| D-02 | No second confirm prompt added; `enter start` remains the only gate | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k confirm -x` | ❌ W0 | ⬜ pending |
| D-03 | A blocked update surfaces in the post-run summary log with the reused `"cannot update {tool_id}: {reason}"` text | unit (Textual pilot) | `uv run pytest tests/test_execute_screen.py -k blocked_update -x` | ❌ W0 | ⬜ pending |
| D-04 | `set_login_shell` never offered/executed when `Platform.immutable` is `True` | unit | `uv run pytest tests/test_engine.py -k login_shell -x` or new `tests/test_post_install.py` | ❌ W0 | ⬜ pending |
| D-05 | On a non-immutable host, `set_login_shell` never fires without an explicit confirm returning True | unit | same new test file | ❌ W0 | ⬜ pending |
| D-06 | `set_login_shell` dispatches only from the `oh-my-zsh` tool's ladder, only after a successful method | unit | same new test file + `tests/test_registry.py` assertion that only `oh-my-zsh` declares `post_install = ["set_login_shell"]` | ❌ W0 | ⬜ pending |
| D-07 | No generalized "future shell" parameter is introduced | code-review / registry-integrity | `uv run pytest tests/test_registry.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] A test asserting `resolve_dependencies` output for a *selected, installed, outdated* tool (currently no such test exists in `tests/test_deps.py`) — establishes the documented, unchanged baseline before `ExecuteScreen`'s new split logic is layered on top.
- [ ] `tests/test_execute_screen.py` fixtures for an `ExecuteInputs` that also carries `version_refresh`/`updates` (today's `_execute_inputs` helper at `tests/test_wizard_app.py:4070-4100` has no such fields).
- [ ] A new `tests/test_post_install.py` (or equivalent) mirroring `tests/test_postinstall.py`'s structure, for the new `post_install`/`set_login_shell` dispatch table.
- [ ] A `Platform.immutable=True` fixture case proving `set_login_shell` is never offered (D-04) — reuse the existing `Platform(os=..., arch=..., immutable=True, has_brew=...)` construction pattern already used throughout `tests/test_resolve.py`/`tests/test_engine.py`.

---

## Manual-Only Verifications

*All phase behaviors have automated verification (see Per-Task Verification Map). `chsh`'s real PAM-password-prompt behavior on a live atomic-distro host is not exercised automatically — see RESEARCH.md's Assumption A1 — but D-04's hard `Platform.immutable` block makes that path unreachable on the target platform, so no manual verification is required for this phase's scope.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
