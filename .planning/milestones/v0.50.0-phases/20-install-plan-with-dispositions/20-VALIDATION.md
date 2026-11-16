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
| 20-01-01 | 20-01 | 1 | PLAN-01 | T-20-01 | `Resolution.closure` via the same cycle-guarded sort as `order` | unit | `uv run pytest tests/test_deps.py -q --no-cov` | yes (extend) | ⬜ |
| 20-01-02 | 20-01 | 1 | PLAN-01 | T-20-02 | `requested_by` first requester; `Blocked(needs, reason)` as data | unit | `uv run pytest tests/test_deps.py tests/test_catalog_tui.py tests/test_execute_screen.py tests/test_app.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-02-01 | 20-02 | 1 | PLAN-03 | T-20-03 | one `update_refusal` for engine and plan | unit | `uv run pytest tests/test_update.py tests/test_catalog_tui.py tests/test_execute_screen.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-02-02 | 20-02 | 1 | PLAN-08 | T-20-04 | no migration promise under `installer/` (grep test) | unit | `uv run pytest tests/test_update.py tests/test_catalog_tui.py -n auto -q --no-cov` + `! grep -rn "moving it there" installer/` | yes (extend) | ⬜ |
| 20-03-01 | 20-03 | 1 | PLAN-06 | T-20-05 | one `_build_services` for both routes | unit | `uv run pytest tests/test_setup.py tests/test_wizard_app.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-04-01 | 20-04 | 2 | PLAN-01, PLAN-04 | T-20-06 | `build_plan` spawns no subprocess; `WORDS` parity | unit | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py -q --no-cov` | no, Wave 0 (`tests/test_plan.py`, `plan_state`) | ⬜ |
| 20-04-02 | 20-04 | 2 | PLAN-01 | T-20-06 | dragged rows once under the first requester; blocked dependents | unit | `uv run pytest tests/test_plan.py -q --no-cov` | created in 20-04-01 | ⬜ |
| 20-04-03 | 20-04 | 2 | PLAN-02 | T-20-07 | reinstall only from the `r` set; WAIT when pending | unit | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py -n auto -q --no-cov` | created in 20-04-01 | ⬜ |
| 20-05-01 | 20-05 | 3 | PLAN-03 | T-20-08, T-20-09 | broken -> repair with reason; native owner -> blocked; dependents of a blocked row -> blocked `needs X`; no sudo literal on the plan path | unit | `uv run pytest tests/test_plan.py -q --no-cov -k "broken or sudo or blocked_dependency"` | yes (extend) | ⬜ |
| 20-05-02 | 20-05 | 3 | PLAN-03 | T-20-08 | misconfigured/outdated x owner x direct/dragged | unit | `uv run pytest tests/test_plan.py -q --no-cov` | yes (extend) | ⬜ |
| 20-05-03 | 20-05 | 3 | PLAN-01 | — | G cases A–I x system/user/ai | unit | `uv run pytest tests/test_plan.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-06-01 | 20-06 | 3 | PLAN-01, PLAN-04 | T-20-10 | row anatomy within 78 cells; words/marks from the tables only | unit | `uv run pytest tests/test_render.py tests/test_catalog_tui.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-06-02 | 20-06 | 3 | PLAN-01 | T-20-10 | grouping, head, steps, folding (400-char backstop) | unit | `uv run pytest tests/test_render.py -q --no-cov -k "render_plan"` | yes (extend) | ⬜ |
| 20-06-03 | 20-06 | 3 | PLAN-01 | T-20-10 | reasons render literally; no escape bytes (backstop) | unit | `uv run pytest tests/test_render.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-07-01 | 20-07 | 4 | PLAN-04, PLAN-05, PLAN-06 | T-20-12, T-20-13 | one outcome per row; WAIT refused; pure views | unit | `uv run pytest tests/test_session.py tests/test_plan.py -q --no-cov` | yes (extend; `ScriptedUpdates`/`RunRecorder` Wave 0) | ⬜ |
| 20-07-02 | 20-07 | 4 | PLAN-05, PLAN-06 | T-20-11, T-20-12 | updates via the service; propagation; crash/cancel -> crashed/not_attempted | unit | `uv run pytest tests/test_session.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-07-03 | 20-07 | 4 | PLAN-04 | T-20-11 | total status -> result table | unit | `uv run pytest tests/test_session.py tests/test_plan.py tests/test_render.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-08-01 | 20-08 | 5 | PLAN-03 | T-20-14, T-20-15, T-20-16 | argv steps in order; validated cwd via the argv shim; stop at first failure | unit | `uv run pytest tests/test_session.py -q --no-cov -k reconfigure` | yes (extend) | ⬜ |
| 20-08-02 | 20-08 | 5 | PLAN-03 | T-20-15 | every `ConfigStepKind` dispatches; pnpm group via node executor; handoff -> manual | unit | `uv run pytest tests/test_session.py tests/test_plan.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-09-01 | 20-09 | 5 | PLAN-04 | T-20-17 | `Summary —` first line; done rows from the tables | unit | `uv run pytest tests/test_render.py -q --no-cov -k "run_summary or outcome_row"` | yes (extend) | ⬜ |
| 20-09-02 | 20-09 | 5 | PLAN-04 | T-20-17 | every result's row text, sanitized | unit | `uv run pytest tests/test_render.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-17-01 | 20-17 | 5 | PLAN-05, PLAN-07 | T-20-30 | `ExecuteInputs.version_refresh` required, `installed` deleted, `terminal_sync` wired; screen reads presence from the service; `_inputs(present=, states=)` | unit + pilot | `uv run pytest tests/test_execute_screen.py tests/test_setup.py -n auto -q --no-cov` | yes (port; Wave 0 for 20-10/20-12, L-20-09) | ⬜ |
| 20-17-02 | 20-17 | 5 | PLAN-05 | T-20-30 | `tests/test_wizard_app.py` builds inputs through `_execute_inputs(...)` | pilot | `uv run pytest tests/test_wizard_app.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-10-01 | 20-10 | 6 | PLAN-01, PLAN-04 | T-20-20, T-20-32 | screen reviews `build_plan`, runs `execute_plan`, wires PATH only when something ran; empty/all-skipped/checking/failed/crash states; a crash outside `execute_plan` fills every row `not_attempted` | pilot | `uv run pytest tests/test_execute_screen.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-10-02 | 20-10 | 6 | PLAN-05 | T-20-18, T-20-19 | `_staged ∩ retained` in place; sync on `ran_anything`; exit on outcomes + run errors (None outcomes -> 0) | pilot + unit | `uv run pytest tests/test_wizard_app.py tests/test_setup.py tests/test_execute_screen.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-11-01 | 20-11 | 7 | PLAN-06 | T-20-21 | headless on `build_plan`/`execute_plan`; `Run this plan?`; no reinstall set | integration | `uv run pytest tests/test_app.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-11-02 | 20-11 | 7 | PLAN-06 | T-20-22 | services from `_build_services`; side effects only when something ran; state-check failure -> not_attempted, exit 1; outdated brew updates and exits 0 (one commit with 20-11-01) | integration | `uv run pytest tests/test_setup.py tests/test_app.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-19-01 | 20-19 | 7 | PLAN-06 | T-20-23 | e2e parser reads `Summary —`; old line no longer matches; `dependency_failures_explained` reads the outcome rows | script | `bash -n scripts/container-e2e-verify.sh` + the two sourced self-checks (`parse_summary_line`, `dependency_failures_explained`); `uv run pytest tests/test_shell_scripts_path.py tests/test_container_e2e_receipts.py -q --no-cov` | yes (edit) | ⬜ |
| 20-12-01 | 20-12 | 7 | PLAN-07 | T-20-25 | Enter joins the one flight with the whole catalog; release rebuilds then starts | pilot | `uv run pytest tests/test_execute_screen.py -q --no-cov -k "held_refresh or releasing_the_refresh or joins_the_flight or auto_start_waits or checking_rows"` | no, Wave 0 (`HeldRefreshService`) | ⬜ |
| 20-12-02 | 20-12 | 7 | PLAN-07 | T-20-24 | `esc` cancels with the selection kept; stale publication ignored; failed refresh reports and retries | pilot | `uv run pytest tests/test_execute_screen.py -n auto -q --no-cov` | created in 20-12-01 | ⬜ |
| 20-13-01 | 20-13 | 8 | PLAN-02 | T-20-26 | `r` toggles both ways on eligible rows only; refused elsewhere; inert while waiting/running/finished | pilot | `uv run pytest tests/test_execute_screen.py -q --no-cov -k "test_r_"` | yes (extend) | ⬜ |
| 20-13-02 | 20-13 | 8 | PLAN-02 | — | `UNPROVEN_NOTE` points at the review's `r` (L-20-06) | unit | `uv run pytest tests/test_version_status.py tests/test_catalog_tui.py -n auto -q --no-cov -k "unproven or adopt or detail"` | yes (extend) | ⬜ |
| 20-13-03 | 20-13 | 8 | PLAN-01 | — | status/keys on rows 18–19 at 80x20 with 25 rows and the worst-case head; running layout; 78 cells; Resize | pilot | `uv run pytest tests/test_execute_screen.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-14-01 | 20-14 | 8 | PLAN-04 | T-20-27 | audit/summary/notice renderers deleted; `render_failure_details` docstring reworded (no quoted result word, no deleted-renderer name) | unit + grep | `uv run pytest tests/test_render.py -n auto -q --no-cov` + grep gate | yes (port) | ⬜ |
| 20-14-02 | 20-14 | 8 | PLAN-04 | T-20-27 | `Summary`/`fold_run`/`run_installs`/`summarize` deleted; no reference (incl. annotation-only imports) survives | unit + grep | `uv run pytest tests/test_session.py tests/test_plan.py tests/test_versions.py tests/test_render.py -n auto -q --no-cov` + git grep gate | yes (port) | ⬜ |
| 20-14-03 | 20-14 | 8 | PLAN-03 | T-20-27 | `reapply_post_install` deleted | unit + grep | `uv run pytest tests/test_engine.py tests/test_post_install.py tests/test_session.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-15-01 | 20-15 | 9 | PLAN-06 | T-20-28 | `audit.py`, `tool_choices`, `category_choices` deleted | unit + grep | `uv run pytest tests/test_selection.py tests/test_status.py tests/test_app.py -n auto -q --no-cov` | delete/port | ⬜ |
| 20-15-02 | 20-15 | 9 | PLAN-06 | T-20-28 | `Prompter.confirm` only; `_ask_checkbox` deleted; `FakePrompter` trimmed in the same commit | unit + grep | `uv run pytest tests/test_prompt.py tests/test_setup.py tests/test_app.py -n auto -q --no-cov` | yes (port) | ⬜ |
| 20-18-01 | 20-18 | 9 | PLAN-05, PLAN-01 | T-20-31 | `a` on all-current runs nothing; mixed run retains; order parity; D-05 pin (through the real app) | pilot | `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_setup.py tests/test_session.py tests/test_render.py tests/test_plan.py -n auto -q --no-cov` | yes (extend) | ⬜ |
| 20-16-01 | 20-16 | 10 | PLAN-01, PLAN-04, PLAN-06 | T-20-29 | Phase 20 doctrine pinned by `_PHASE_20_REQUIRED` | unit | `uv run pytest tests/test_docs.py -q --no-cov` | yes (extend) | ⬜ |
| 20-16-02 | 20-16 | 10 | PLAN-01 | T-20-29 | Tier/Phase 3/13/14 paragraphs describe live code; 13/14 pins kept | unit + grep | `uv run pytest tests/test_docs.py -q --no-cov` + the grep gate over everything before the Phase 20 section | yes (extend) | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Every plan ends with `make validate && make test` green on the committed tree (per-plan gate), in addition to the per-task command above.

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

- [ ] `tests/test_plan.py` — G cases A–I × 3 tiers, health × owner matrix, dragged rows, purity (GuardedPopen) — plans 20-04 (created) and 20-05
- [ ] `tests/state_doubles.py` — `plan_state(...)` builder (20-04); `ScriptedUpdates` + `RunRecorder` (20-07); `HeldRefreshService` (20-12)
- [ ] shared `RunContext` fake (install, runner, updates, terminal_sync recorders) for `tests/test_session.py` and the screen tests — `RunRecorder`, 20-07
- [ ] `ExecuteInputs.version_refresh` required with a test default in the `_inputs(...)`/`_execute_inputs(...)` helpers (L-20-09) — 20-17 (wave 5, before 20-10)
- [ ] `scripts/container-e2e-verify.sh` summary parser and dependency-failure cross-check updated with the new summary words and outcome rows — 20-19 (wave 7, same wave as the headless summary switch in 20-11)

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
