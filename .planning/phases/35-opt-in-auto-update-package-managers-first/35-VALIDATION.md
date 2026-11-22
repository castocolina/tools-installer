---
phase: "35"
slug: "opt-in-auto-update-package-managers-first"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-22"
---

# Phase 35 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 35-RESEARCH.md "Validation Architecture" and the orchestrator decisions of 2026-11-22 (all provisional, "needs confirmation"). The per-task map below holds PLACEHOLDER rows: the planner replaces the plan, wave and task ids (and narrows each command) once the plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage, pytest-asyncio for Textual pilots); fake managers (`brew`, `uv`, `bun`, `pnpm`, `sdk`, `volta`) and a fake `UpdateService` executor spy with a per-tool outcome map; every test injects `which`, `run` and git as fakes (CI runners and the dev host carry real tools); `FakeNotifier` from `tests/update_check_doubles.py` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); worker cap and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once per plan, after `make validate`; never chained with it at a commit) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof (orchestrator only)** | `scripts/container-e2e-verify.sh schedules` (the existing pairs stay green), extended by the orchestrator with a dedicated `update-all` target modeled on `cmd_bun_lifecycle` over fake managers; never executor-run. The target must assert the plan line for uv says "would update", or the run proves nothing about `uv self update` (decision 8). A host test with a stubbed runtime is the minimum if the plan size forces a choice |
| **Estimated runtime** | ~30 seconds per targeted run (the quick list below is about eleven files; confirm in the first plan) |

Files the quick command draws from (research "Validation Architecture"): `tests/test_update_all.py` (new, pure planner), `tests/test_update_all_run.py` (new, executor, log, store, notifier, plan-equals-run, lock, AST no-sudo), `tests/test_container_e2e_update_all.py` (new, static pin of the container target) with `tests/e2e_update_all_driver.py` (new, shared test support, not a test file), `tests/test_schedules.py`, `tests/test_schedules_lifecycle.py`, `tests/test_schedules_handover.py`, `tests/test_schedules_view.py`, `tests/test_layout_80x20.py`, `tests/test_schedule_runner.py`, `tests/test_schedule_update.py`, `tests/test_cli.py`, `tests/test_update_check_contract.py`, `tests/test_docs.py`. Also read by this phase: `tests/test_reachability.py` (once `installer/update_all.py` gets its production import), `tests/test_shell_scripts_path.py` (renumber `:517-540` when the container usage text grows), `tests/test_docs_only.py`, `tests/update_check_doubles.py` (extend only if a shared helper is needed).

Constraints on every new test (orchestrator decision 10, lessons of phases 27 to 34):

- Every test injects `which`, `run` and git as fakes; fake binaries only, never a real manager (the dev host and the CI runners carry them). Isolate `PATH`, scratch `HOME`.
- No timing-sensitive assertions: poll with a cap, never a fixed sleep; the once-a-day rule uses an injected clock. xdist-safe (`tmp_path`, `monkeypatch`, no fixed path, port or order); holds on Python 3.12 and 3.15 and macOS bash 3.2 where a shell is involved (no apostrophes or unbalanced quotes inside a heredoc inside `$(...)`).
- `os.killpg` can raise `PermissionError` on macOS; `find -printf` and other GNU-only flags break host tests on macOS runners (use portable forms).
- The sandbox forbids launching `git` and `gh` from unit tests.
- A result line is bounded by the runner's 300-character single-line budget (see `update_check.result_line`): give every required clause room and assert the bound.
- A module added in a plan is imported by a production entry point in that plan or the next (`tests/test_reachability.py`).
- Any usage-text change of `scripts/container-e2e-verify.sh` moves the classified PATH line numbers of `tests/test_shell_scripts_path.py` in the same commit.
- Each plan stays under about 50 KB of executor-visible text with at most two large tasks; a task that edits a test not added by phase 35 lists it as an explicit exception in the plan's files, with its reason and the unchanged assertion meaning (decision 7).

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan wave:** the quick-run files above, plus `tests/test_reachability.py` once `installer/update_all.py` gets its production import
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green; the container target `scripts/container-e2e-verify.sh update-all` (and `schedules`) recorded in VERIFICATION, or "not run" with the reason, never a pass; the manual-only rows below carried as deferred items
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

PLACEHOLDER ids: the planner replaces `35-NN-NN`, the plan and the wave with the real ones and narrows the commands. Threat refs are placeholders keyed to the research security table (`T-35-xx`): the planner registers each in the plan that mitigates it. T-35-01 planted symlink at `updated-today.json` or `update-all.log` redirecting a write; T-35-02 unattended run of vendor installers and updaters (opt-in only, refusal predicate, no-update-argv skip, `--plan` preview, closed stdin); T-35-03 privilege escalation inside a child (casks excluded, `HOMEBREW_NO_SUDO=1`, no sudo/pkexec/doas); T-35-04 log or notification injection from tool output (counts and ids only, `sanitize_log_line`/`reason_line`); T-35-05 overlapping runs corrupting state (the run lock, store written only under it); T-35-06 rc-file rewrite by `uv self update` or a vendor installer (accepted limit, container only, update-all child env disables PATH modification where the installer supports it); T-35-07 corrupted state used to bypass the once-a-day rule or crash the run.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 35-NN-NN | NN | N | AUTOUPD-01 | T-35-02 | The `update-all` row is registered, seeds OFF and is never a Policies row; the `_row_action` truth table over (default_on, decided) holds; a recorded on or off survives re-seeding (the installer never changes it on its own); unit text and runner argv parse through the runner's `_parse` | unit + Textual pilot | `uv run pytest tests/test_schedules.py tests/test_schedules_lifecycle.py tests/test_schedules_handover.py tests/test_schedule_runner.py --no-cov -q` | exists (edit; `test_exactly_two_rows_are_daily` at `test_schedules.py:105` must change, decision 7) / new cases in existing files | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-02 | — | Managers first by ownership edges (a manager installed by another follows it, ties by tool id, a brew-owned manager after brew); dependents grouped by owner and ordered by `deps.resolve_dependencies`; empty and managers-only inputs; the planner runs a second pass over the dependents with a refreshed outdated set (decision 1, pure, the outdated set is an input twice) | unit (pure, fakes) | `uv run pytest tests/test_update_all.py --no-cov -q` | ❌ W0 (`tests/test_update_all.py`) | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-03 | T-35-02 | A failing fake manager yields one `skipped: <mgr> failed` per dependent and zero executor calls for them; manager-on-manager and `requires` chains cascade | unit with executor spy | `uv run pytest tests/test_update_all_run.py -k failed --no-cov -q` | ❌ W0 (`tests/test_update_all_run.py`) | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-04 | T-35-03, T-35-05 | Each refusal text is exact (native, SDKMAN, Volta, pin, os-package); a held lock gives `skipped: busy`; an AST test finds no `sudo`/`pkexec`/`doas`; the child env carries `HOMEBREW_NO_SUDO=1` and the PATH-modification-off variable where the installer supports it (decision 8); child stdin is `/dev/null` (D-16, pinned with a test only); eight script tools without a declared `update` are each `skipped: no unattended update path` by the generic rule with no per-tool special case, `opencode` keeps its own row (decision 4) | unit | `uv run pytest tests/test_update_all_run.py tests/test_schedule_runner.py tests/test_schedule_update.py --no-cov -q` | stdin test exists (`test_schedule_runner.py:1212`); rest ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-05 | T-35-03 | macOS fixture: a formula is planned, a cask is `skipped: cask excluded`; Linux plans no cask | unit (pure) | `uv run pytest tests/test_update_all.py -k cask --no-cov -q` | ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-06 | T-35-01, T-35-04 | Three tools give three lines in `update-all.log` and exactly one `update-all` line in `schedules.log` via `schedule_runner.main([...])`; the summary fits 300 characters with every clause; no C0 or C1 control character; the log append does not follow a symlink | unit / hermetic (model on `tests/test_update_check_job.py`, `tests/update_check_child.py`) | `uv run pytest tests/test_update_all_run.py -k log --no-cov -q` | ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-07 | T-35-01, T-35-07 | `updated-today.json` through `atomic_replace_entry` with a strict reader (UTF-8, version 1, id shape, bounded `read_capped`, `RecursionError` and `OverflowError` handled, a directory at the path untouched and reported; decision 6); both directions with an injected clock, next-day reset, corrupt, symlinked and oversized file read as empty; a per-tool row skips only for `by == "update-all"`; `update-all` skips a tool either runner updated today | unit with injected clock | `uv run pytest tests/test_update_all.py tests/test_update_all_run.py tests/test_schedule_update.py -k today --no-cov -q` | ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-08 | T-35-06 | A static pin test of the `update-all` container target and its verdict markers (the target asserts the uv plan line says "would update", cleanup confirmed in the runtime that ran the container); the target script and its usage text keep the classified PATH lines of `tests/test_shell_scripts_path.py` renumbered in the same commit; no container started by the executor | unit (static) + container (orchestrator only, after this plan) | `uv run pytest tests/test_container_e2e_update_all.py tests/test_shell_scripts_path.py --no-cov -q`; orchestrator: `scripts/container-e2e-verify.sh update-all` | ❌ W0 (`tests/test_container_e2e_update_all.py`, `tests/e2e_update_all_driver.py`) | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-01, AUTOUPD-02 (spec R9) | T-35-02 | `--plan` output equals the real run's order and skips on one fixture; zero executor calls; no installer state file is written: the refresh runs against a scratch copy of the version cache path that the run creates and removes (decision 2; the SPEC "writes nothing" is amended to "writes no installer state", or reworded and said so in the SUMMARY) | unit | `uv run pytest tests/test_update_all_run.py -k plan --no-cov -q` | ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-06 (spec R10) | T-35-04 | One notification with counts after a real run only when `updated + failed > 0` (a run that only skipped, and an empty run, send nothing; decision 3); a notifier failure gives `; notify skipped: <reason>` and exit 0; the update-all child gets the bus variable through `extra_env` like the check job (decision 5) | unit with `FakeNotifier` | `uv run pytest tests/test_update_all_run.py tests/test_schedule_runner.py -k notif --no-cov -q` | `FakeNotifier` exists (`tests/update_check_doubles.py:177`); tests ❌ W0 | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-01 (CLI) | T-35-02 | `--plan` is valid only with `--run-schedule update-all`; the flag set in `tests/test_cli.py` (`:96-128`, `:101-112`) and `RUN_SCHEDULE_IDS` include the new row; `setup.py` stays wiring-only | unit | `uv run pytest tests/test_cli.py tests/test_update_check_contract.py tests/test_reachability.py --no-cov -q` | exists (edit; `tests/test_update_check_contract.py:47-57` choices test changes, decision 7) | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-01 (view) | — | Ninth row of Schedules with the `never` cell, table height 9 to 10, the detail panel keeps the macOS permission sentence visible at 80x20 (phase 34 lesson), detail text for the new row; each viewport case is its own freshly mounted app | Textual pilot | `uv run pytest tests/test_schedules_view.py tests/test_layout_80x20.py --no-cov -q` | exists (edit; `tests/test_schedules_view.py:241-250`, `:679-681`, `tests/test_layout_80x20.py:331-334`, decision 7) | ⬜ pending |
| 35-NN-NN | NN | N | AUTOUPD-01 to AUTOUPD-08 | — | Phase 35 phrases pinned in the docs: `.claude/architecture.md` gains the Phase 35 subsection with the accepted limits (opt-in OFF, brew dependents judged with a refreshed set, plan mode writes no installer state, `uv self update` rc-file rewrite limit, the eight script tools without an update path, casks excluded, notification only after a real change or failure); the SPEC, ROADMAP and REQUIREMENTS amendments carry dated entries; the phase's last `make validate` and `make test` pass with the reachability guard green | docs + gate | `uv run pytest tests/test_docs.py tests/test_docs_only.py --no-cov -q`; then `make validate`; `make test` | exists (edit `tests/test_docs.py`) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every test file is created or extended inside the task that needs it (test-first inside one green commit), so there is no separate scaffold task unless the planner decides one is needed:

- [ ] `tests/test_update_all.py` — new; AUTOUPD-02, AUTOUPD-05, AUTOUPD-07 (pure planner fixtures via `tests/state_doubles.pass_state` with explicit `ownership`)
- [ ] `tests/test_update_all_run.py` — new; AUTOUPD-03, AUTOUPD-04, AUTOUPD-06, AUTOUPD-07, R9, R10 (executor, log, store, notifier, plan-equals-run, lock, AST no-sudo test)
- [ ] `tests/e2e_update_all_driver.py` and `tests/test_container_e2e_update_all.py` — new; AUTOUPD-08 (static pin of the target and its verdict markers)
- [ ] `tests/update_check_doubles.py` — extend only if a shared helper is needed (a fake `UpdateService` spy with a per-tool outcome map)
- [ ] edits to existing files, each listed as an explicit exception in the plan that makes it: `tests/test_schedules.py` (`:105-107`, `:138-178`), `tests/test_schedules_view.py` (`:241-250`, `:679-681`), `tests/test_layout_80x20.py` (`:331-334`), `tests/test_cli.py` (`:96-128`, the flag set at `:101-112`), `tests/test_schedule_runner.py` (job table, per-job timeout, `_parse`), `tests/test_update_check_contract.py` (`:47-57`), `tests/test_docs.py`, `tests/test_shell_scripts_path.py` (renumber `:517-540` if the usage text grows)

Framework install: none.

---

## Manual-Only Verifications

Nothing here is run by an agent on the real host: no timer, unit, notification or real update-all run is started on the developer's machine. The rows are deferred owner UAT items; VERIFICATION carries them as `human_needed`, never as a pass.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real unattended `update-all` run on a Bazzite host with the real managers present (brew, uv, bun, pnpm, sdkman, volta): managers update first, dependents follow, refusals and skips are logged, no sudo prompt, one summary line | AUTOUPD-02, AUTOUPD-04, AUTOUPD-06 | Fakes prove ordering and logging; only real managers show real exit codes, real prompts and real vendor behavior, and an agent must never mutate the host | Owner: enable the row, run `--run-schedule update-all --plan` and read the preview, then one real run (or `systemctl --user start` of its service); read `update-all.log` and the one `schedules.log` line; confirm the plan matched the run; record in VERIFICATION |
| A real unattended `update-all` run on a Mac with real managers (brew formulae, uv, bun, pnpm, sdkman, volta), with casks excluded | AUTOUPD-02, AUTOUPD-05, AUTOUPD-06 | macOS behavior is unverifiable on this host and an agent never runs it; macOS is deferred to the owner | Owner on a real Mac: run `--plan`, then one real run; confirm no cask was touched (`skipped: cask excluded`), no permission or sudo prompt, and the Script Editor notification permission path from phase 34 still holds; record the macOS version |
| The real `uv self update` replacing the running `uv` (the vendor installer replaces the binary with `mv`, expected safe, confirmed only by a real run; a uv installed without `UV_NO_MODIFY_PATH` can have shell rc files rewritten) | AUTOUPD-08 | Only a real replacement of a running binary shows it; the container run uses the container's own uv and fake managers around it; the rc-file rewrite is an accepted limit (decision 8) | Orchestrator, in the container run: the `update-all` target asserts the uv plan line says "would update" and records the post-run `uv --version`; owner on a disposable user or after a backup: one real run, then check `uv` still runs and diff the shell rc files; record in VERIFICATION |
| The 03:00 timer fires on both OSes (systemd `OnCalendar` with a login catch-up, launchd calendar interval) and writes one `update-all` line per night | AUTOUPD-01, AUTOUPD-06 | Needs real timers over a day boundary on a real Linux user session and a real Mac | Owner, one day after enabling: read the shared schedule log for one `start` and one `update-all` summary line per night on each OS |
| The notification after a real run (counts only, no tool output, none for a run that only skipped) | AUTOUPD-06 (R10) | The suite uses fake binaries; only a real session shows a real notification, and a real notification on the host is forbidden for agents | Owner: after a real run that updated or failed at least one tool, confirm one notification with counts; after a run with only skips confirm none; the update-all child receives the bus address through `extra_env` as the check job does |
| The first night's actual outdated set: what really updates, what is skipped, and the cost of a first run (the brew index lag, decision 1, and the eight script tools skipped with no update path, decision 4) | AUTOUPD-02, AUTOUPD-04 | Depends on the real catalog state of the owner's machines on the first night | Owner: read `update-all.log` after the first night, compare the updated and skipped sets with `--plan` of the previous evening; record surprises as backlog items |
| Container proof of the `update-all` target | AUTOUPD-08 | Orchestrator-run only (decision 9), after the plan that adds the target | Orchestrator: `scripts/container-e2e-verify.sh update-all` and `schedules` in a disposable container, removed afterwards (cleanup confirmed with `CONTAINER_TOOL` from `scripts/detect-container-runtime.sh`, never assumed podman); record the verdict markers and the uv "would update" assertion; an environmental failure (exit 2, network) is a re-run, never a pass; or "not run" with the reason |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
