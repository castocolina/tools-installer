---
phase: "25"
slug: "lean"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-15"
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 25-RESEARCH.md § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8 + pytest-xdist + pytest-asyncio (`asyncio_mode = "auto"`); Textual `App.run_test` pilot |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`, `[tool.pyright]`, `[tool.vulture]`) |
| **Quick run command** | `uv run pytest <the test files the task edits> -n auto -q --no-cov` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | ~180 seconds (full); quick runs ~10-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick command over the test files the task edits, plus the pilot safety net (`tests/test_layout_80x20.py tests/test_screen_family.py tests/test_wizard_app.py`) whenever `wizard_app.py` or a split module changes
- **After every plan wave:** Run `make validate && uv run pytest -n auto --no-cov`
- **Before `/gsd-verify-work`:** `make validate && make test` must be green on the exact tree
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

Filled by the planner per task (each task's `<automated>` command). Requirement-level map:

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| LEAN-01 | no unreachable `installer/` module; a seeded orphan is detected | unit (AST) | `uv run pytest tests/test_reachability.py --no-cov` | ❌ W0 | ⬜ pending |
| LEAN-01 | `host_setup` is rejected as an unknown kind; `host-setup` as an unknown probe | unit | `uv run pytest tests/test_model.py tests/test_install_ownership.py --no-cov` | ✅ edit | ⬜ pending |
| LEAN-01 | `default_enabled_sensitive_actions` is rejected; post-install actions take `(tool, platform)` | unit | `uv run pytest tests/test_post_install.py tests/test_model.py tests/test_engine.py tests/test_session.py --no-cov` | ✅ edit | ⬜ pending |
| LEAN-01 | race epoch tests still pass | unit | `uv run pytest tests/test_wizard_app.py tests/test_screen_family.py --no-cov` | ✅ | ⬜ pending |
| LEAN-02 | `installer/compose.py` passes pyright strict and is in the coverage report | gate | `uv run pyright installer/compose.py` and `make test` | ❌ W0 | ⬜ pending |
| LEAN-02 | `setup.py` defines no `_build_app`; the sandbox covers compose's home constants | unit | `uv run pytest tests/test_setup.py tests/test_sandbox.py --no-cov` | ✅ extend | ⬜ pending |
| LEAN-03 | every split module ≤ 800 lines; no `CR-0`/`WR-0`/`IN-0` in them | unit (file scan) | `uv run pytest tests/test_reachability.py --no-cov` | ❌ W0 | ⬜ pending |
| LEAN-03 | pilot safety net green at every commit | pilot | `uv run pytest tests/test_layout_80x20.py tests/test_screen_family.py tests/test_wizard_app.py -n auto --no-cov` | ✅ | ⬜ pending |
| LEAN-03 | `tests/test_cli.py` byte-identical; `--all`/`--categories` asserts in `tests/test_setup.py` unchanged (D-12) | gate | `git diff --exit-code <before> -- tests/test_cli.py` plus the D-12 assert-diff guard | ❌ W0 | ⬜ pending |
| LEAN-04 | 5,000 writes: no notice; 6,000: 5,000 lines + "1000 earlier lines dropped", newest last | pilot | `uv run pytest tests/test_execute_screen.py --no-cov` | ❌ W0 | ⬜ pending |
| R5 | full suite + validate; net production lines reported | gate | `make validate && make test`; `git diff --shortstat <before> HEAD -- installer setup.py` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_reachability.py` — reachability from the entry points + seeded orphan; later the size and review-ID guards
- [ ] `tests/test_execute_screen.py` — boundary tests for the bounded log
- [ ] `tests/conftest.py` + `tests/test_sandbox.py` — sandbox generalized to `installer.compose`
- [ ] a composition patch helper in `tests/` used by `tests/test_setup.py`

Framework install: none.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI green on ubuntu and macOS | R5 | remote runners | push per wave (orchestrator), watch the `ci.yml` run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
