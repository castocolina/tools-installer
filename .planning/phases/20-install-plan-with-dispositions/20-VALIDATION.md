---
phase: "20"
slug: "install-plan-with-dispositions"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-17"
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from 20-RESEARCH.md `## Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = "auto", pytest-xdist, coverage `fail_under = 90`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| **Quick run command** | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py tests/test_render.py -q --no-cov -n 0` |
| **Screen run command** | `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py -q --no-cov -n 0` (per wave, not per task) |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | quick ~30 s; full ~80 s |

---

## Sampling Rate

- **After every task commit:** quick run command (no Textual pilots)
- **After every plan wave:** quick command + the screen run command for touched screen files, then `make validate && make test`
- **Before `/gsd-verify-work`:** full suite green on the committed tree
- **Max feedback latency:** 30 seconds (quick), 90 seconds (full)

---

## Per-Task Verification Map

Filled by the planner, one row per task (Task ID `20-NN-TT`).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Requirement → test map (from research)

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAN-01 | G cases A–I as parametrized `build_plan` tests on system, user, ai tiers | unit | `uv run pytest tests/test_plan.py -q --no-cov -n 0` | no, Wave 0 |
| PLAN-01 | `Resolution` closure/blocked/requested_by; `order` unchanged | unit | `uv run pytest tests/test_deps.py -q --no-cov -n 0` | yes (extend) |
| PLAN-01 | dragged present dep under its requester, listed once; 78-col budget with 24-char ids (L-20-05) | unit/pilot | `uv run pytest tests/test_render.py tests/test_execute_screen.py -k plan -q --no-cov -n 0` | partial |
| PLAN-02 | `r` toggles both ways on installer-owned (receipt optional, L-20-06); inert on dnf-owned; `a`/`--yes` never reinstall | pilot + unit | `uv run pytest tests/test_execute_screen.py -k reinstall -q --no-cov -n 0` | no, Wave 0 |
| PLAN-03 | one test per (health × owner × direct/dragged); BROKEN-by-drift → REPAIR with reason (L-20-01); MISCONFIGURED without step → BLOCKED (L-20-04); sudo-needing repair BLOCKED; `build_plan` makes no subprocess | unit | `uv run pytest tests/test_plan.py -k "health or sudo or pure" -q --no-cov -n 0` | no, Wave 0 |
| PLAN-03 | each `ConfigStepKind` executes (cwd wrapper, handoff → manual, `pnpm_group_install` via `executors.execute` (L-19-28), stop at first failure) | unit | `uv run pytest tests/test_session.py -k config_step -q --no-cov -n 0` | no, Wave 0 |
| PLAN-04 | `WORDS` parity (every `Disposition` has a review and a done word, L-20-02); summary and review read only the table | unit | `uv run pytest tests/test_session.py -k words -q --no-cov -n 0` | no, Wave 0 |
| PLAN-05 | retained selection `_staged ∩ retained` (L-20-07); `esc` before start keeps `_staged`; crash marks unfinished rows | pilot | `uv run pytest tests/test_wizard_app.py tests/test_execute_screen.py -k "retained or esc" -q --no-cov -n 0` | partial |
| PLAN-06 | `--all --yes` with one outdated brew tool updates it and exits 0; failure exits 1; all-current runs nothing, exits 0; run-level wiring error exits 1 (L-20-08) | integration | `uv run pytest tests/test_app.py tests/test_setup.py -k "wizard or headless" -q --no-cov -n 0` | partial |
| PLAN-07 | held refresh: rows "checking…", Enter starts nothing, release → plan rebuilt → run; one joined pass (L-20-03); `esc` during wait keeps selection | pilot | `uv run pytest tests/test_execute_screen.py -k wait -q --no-cov -n 0` | no, Wave 0 |
| PLAN-08 | no `moving it there` under `installer/`; off-policy reason names both owners | unit | `uv run pytest tests/test_update.py tests/test_catalog_tui.py -k off_policy -q --no-cov -n 0` + grep test | partial |
| Docs | Phase 20 architecture section pinned | unit | `uv run pytest tests/test_docs.py -q --no-cov -n 0` | yes (extend) |

---

## Wave 0 Requirements

- [ ] `tests/test_plan.py` — G cases A–I × 3 tiers, health × owner matrix, dragged rows, purity (GuardedPopen)
- [ ] `tests/state_doubles.py` — `plan_state(...)` builder; `HeldRefreshService` (blocks `refresh` on an Event, counts calls); scripted fake `UpdateService`
- [ ] shared `RunContext` fake (install, runner, updates, terminal_sync recorders) for `tests/test_session.py` and the screen tests
- [ ] `ExecuteInputs.version_refresh` required with a test default in the `_inputs(...)` helper (L-20-09)
- [ ] `scripts/container-e2e-verify.sh` summary parser updated with the new summary words

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `make e2e` summary parser and headless run | PLAN-06 | needs real executors in a disposable container | `make e2e`; PASS1 counts parse; outdated-tool update exits 0 |
| 80x20 review with 25 rows, `NO_COLOR=1` | PLAN-01, PLAN-04 | real terminal glyph widths | tmux 80x20, select a tier, open the review, navigation only |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
