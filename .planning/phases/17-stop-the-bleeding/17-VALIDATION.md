---
phase: "17"
slug: "stop-the-bleeding"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-14"
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Source: 17-RESEARCH.md § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-xdist + coverage (`fail_under = 90`) |
| **Config file** | `pyproject.toml`, `tests/conftest.py` (40% worker cap, real-home guard) |
| **Quick run command** | `uv run pytest <touched test files> -x -q --no-cov` (never a fixed `-n`) |
| **Full suite command** | `make validate && make test` (`pytest -n auto --cov`); `make e2e` for container installs |
| **Estimated runtime** | quick < 30 s; full ~75 s; e2e ~30–60 min |

---

## Sampling Rate

- **After every task commit:** the quick command of the touched requirement row
- **After every plan wave:** `make validate && make test`
- **Before `/gsd-verify-work`:** `make validate && make test` (twice), `pre-commit run --all-files`, `make e2e`, CI green on ubuntu + macOS
- **Max feedback latency:** 30 seconds (quick)

---

## Per-Requirement Verification Map

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| SAFE-01 | dir member raises, no link; reinstall over link-to-dir leaves inner file byte-identical; Sublime member | unit (scratch HOME) | `uv run pytest tests/test_download.py tests/test_apps.py tests/test_engine.py tests/test_registry.py -x -q --no-cov` | ✅ (+ W0 helper) | ⬜ pending |
| SAFE-02 | graphify has no `postinstall`; install/update run no hook; scratch cwd stays empty | unit | `uv run pytest tests/test_postinstall.py tests/test_registry.py tests/test_model.py -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-03 | ruff/yq/drawio never deleted in TUI or `--yes`; same deletion set both paths; second `--yes` deletes nothing | unit + e2e | `uv run pytest tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_setup.py tests/test_wizard_app.py -k "uninstall or removal" -x -q --no-cov` | ✅ (+ W0 fixtures) | ⬜ pending |
| SAFE-04 | injected write failure keeps bytes; changed-between-preview-and-confirm refused; symlinked rc stays symlink | unit | `uv run pytest tests/test_guards.py tests/test_tweaks.py tests/test_app.py tests/test_atomic.py -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-05 | worker raise → red "Failed", exit 1; failed update exits 1; all-skipped exits 0 | pilot + unit | `uv run pytest tests/test_execute_screen.py tests/test_session.py tests/test_setup.py tests/test_wizard_app.py -k "summary or crash or failed or exit" -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-06 | centralized→split moves ban+tweak blocks; injected failure keeps old block | unit + pilot | `uv run pytest tests/test_policy.py tests/test_policies_e2e.py tests/test_wizard_app.py -k "link_mode" -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-07 | child runs in a new session; `/dev/tty` reader exits non-zero < 5 s for `StreamingRunner` and `run_output` | unit | `uv run pytest tests/test_run.py tests/test_registry.py tests/test_executors.py -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-08 | invalid-UTF-8 / invalid-JSON `settings.json` reach first screen, bytes unchanged, warning shown | unit + pilot | `uv run pytest tests/test_settings.py tests/test_setup.py tests/test_wizard_app.py -k "settings" -x -q --no-cov` | ✅ | ⬜ pending |
| SAFE-09 | Enter runs the selection on setup/doctor/fix/uninstall/guard; empty Enter shows message | pilot | `uv run pytest tests/test_setup.py tests/test_wizard_app.py -k "route or execute or accept" -x -q --no-cov` | ✅ (+ W0 tests) | ⬜ pending |
| R10 (Doctor) | link-to-dir and dangling link → one finding each with repair text; fs unchanged | unit | `uv run pytest tests/test_doctor.py tests/test_guidance.py tests/test_render.py -x -q --no-cov` | ✅ | ⬜ pending |
| CI-01 | named failures pass on both OSes; prune scripts run under bash 3.2 | unit + container + CI | `uv run pytest tests/test_prune_tmp_linux_sh.py tests/test_prune_user_tmpdir_sh.py tests/test_shellrc.py tests/test_app.py tests/test_setup.py tests/test_catalog_tui.py -x -q --no-cov`; CI run success on both jobs | ✅ | ⬜ pending |
| CI-02 | branch protection requires both checks | manual (user action) | `gh api repos/castocolina/tools-installer/branches/main/protection` | n/a | ⬜ pending |
| CI-03 | secure + validate re-audit records for 16-17..19 committed | doc check | `grep -c "16-1[789]" .planning/milestones/*/16-*SECURITY.md .planning/milestones/*/16-*VALIDATION.md` (path per plan) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] shared test runner helper that materializes the extracted member (`test_download.py`, `test_apps.py`, `test_engine.py`)
- [ ] strict-shape uninstall fixtures (real `opt/<bin>/<member>` + symlink; link into another tool's opt dir)
- [ ] per-route Enter tests (5) and the empty-Enter test
- [ ] `getsid` session test and `/dev/tty` reader test for `run_output` and `StreamingRunner`
- [ ] link-mode move tests with injected apply failure (reuse `os.replace` injection from `test_atomic.py`)
- [ ] every new test: scratch HOME via `tmp_path` + `monkeypatch`, xdist-safe, home-derived constants patched like `tests/test_setup.py::_sandbox`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Branch protection on `main` requires both CI checks | CI-02 | GitHub admin action on the user's repo | Apply the `gh api` body from 17-RESEARCH.md with user consent; verify with `gh api .../protection` |
| macOS-only behaviors (BSD `find`, bash 3.2) | CI-01 | no macOS host | proven only by the `macos-latest` CI job on the final commit |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
