# Phase 35 Plan 05 Summary

The plan ran as themed pi runs (two themes per task); the text below is the executors' own final notes per task.

## Task 1 (`023cb04f`)

**Commit:** `023cb04f` — bounded and sanitized update-all commands, added capped group cleanup and the runner stop budget, closed stdin for queries, and injected the runner into the replay and terminal follow-up sites.

## Verification

- **RED tail:** the new tests failed with `KeyError: '_UPDATE_ALL_STOP_BUDGET'` and `ImportError: cannot import name 'update_all_stdin_closed'`.
- **GREEN tail:** the prescribed targeted pytest command exited 0:
  ```
  ........................................................................ [ 86%]
  ..........................................................               [100%]
  ```
- The first commit attempt exposed lint, formatting, and type errors. Those were corrected; the commit hook then passed all six static gates.
- The process-lifetime test covers both a command timeout and the runner’s real signal-stop path. **Deviation:** the signal-stop case was not run against the original `_stop` to capture its requested RED evidence.
- Every run directory created by the test wrappers was removed by its exit trap.

## Pin edits

- `tests/test_setup.py`: added the runner import and the keyword-only runner parameter to the two `fake_reinstall` doubles; assertions are unchanged.
- `tests/test_schedule_update.py` and `tests/test_update_check_contract.py` remain unedited.

## Decisions

- **35 D-11 — own reasoning, needs confirmation:** each update-all command has a 1200-second bound and bounded group cleanup. **D-10:** `run_schedule` owns the lock; children have closed stdin.
- **Orchestrator decision 5:** the existing stdlib child-stdin test remains unedited; this task adds installer-side stdin coverage.
- **Orchestrator decision 8 — needs confirmation:** `UV_NO_MODIFY_PATH=1` is set for update-all commands. Rename-based uv self-replacement remains an expectation pending the orchestrator’s container verification; shell-rc modification remains an accepted vendor-path limit.
- **Orchestrator decision 4 — needs confirmation:** the eight script tools without update argv are skipped by the generic rule; `opencode` retains its per-tool row.
- **Review H5 — provisional:** replay and terminal follow-up receive the selected runner; independently bounded query sites remain an accepted residual. The tighter per-tool behavior is owner-vetoable.
- **Review C2 — provisional:** commands use their own sessions and job-level signals are forwarded for cleanup.
- **Review T1 — provisional:** installer cleanup is capped, and the stdlib runner waits up to 30 seconds for the update-all group.
- **Review H6, C3, T2 — provisional:** root refusal and the AST regression check belong to Task 2.
- **Review T3 — provisional:** update-all redirects fd 0 for the whole route, including queries.
- **Review C1 — provisional:** the parent-lock flag requires a verified holder; Task 2 supplies its additional proof.
- **Orchestrator decision 10:** tests use injected fakes and capped polling.

## Task 2 (`6022cce8`)

- **Commit:** `6022cce8` — root refusal, refusal matrix, verified parent-lock handoff, and privilege-escalation regression scan.
- Added CLI lock tests for busy, unrelated, absent, forged, and verified parent holders; an AST regression scan; and real-service argv assertions for brew and uv.
- Preserved the earlier theme’s root-refusal, refusal-matrix, and opencode tests.

## Verification

- **RED:** The earlier theme’s root-test RED output was not available in this run. The first commit attempt failed on test formatting, import order, and strict typing; those issues were corrected.
- **GREEN:** Task 2’s targeted pytest command exited 0, reaching `100%`. A separate targeted run including `tests/test_schedule_runner.py` also exited 0.
- The commit hook passed lint, format-check, typecheck, security, dead-code, and shellcheck.
- Each scratch run directory was removed by its exit trap.

## Pin edits

- `tests/test_schedule_runner.py`: patched effective UID for two existing update-all runner tests.
- `tests/test_update_all_job.py`: patched effective UID in the shared update-all job fixture.
- `tests/test_setup.py` was not edited in this theme.

## Decisions

- **35 D-11 — own reasoning, needs confirmation:** Per-command 1200-second bound and bounded group cleanup; D-10 retains the run lock and closed child stdin.
- **Orchestrator decision 5:** D-16 was already implemented; installer-side stdin is tested here.
- **Orchestrator decision 8 — needs confirmation:** `UV_NO_MODIFY_PATH=1` is used; uv’s rename-based self-replacement remains subject to container verification, and vendors may still modify shell rc files.
- **Orchestrator decision 4 — needs confirmation:** The eight script tools without declared update argv are generically skipped; opencode retains its per-tool row.
- **Review H5 — provisional:** Replay and terminal follow-up runner injection tightens per-tool behavior; separately bounded query sites remain an accepted residual.
- **Review C2 — provisional:** Commands use their own sessions, with job-level signal forwarding.
- **Review T1 — provisional:** Cleanup is capped and the stdlib runner waits up to its 30-second update-all stop budget.
- **Reviews H6, C3, T2 — provisional:** Root is refused before locking or runner start; the AST scan is a regression check, not proof against vendor escalation.
- **Review T3 — provisional:** The update-all route closes stdin through an fd redirect.
- **Review C1 — provisional:** The parent-lock flag requires a verified holder.
- **Orchestrator decision 10:** Tests use fakes and isolated PATH; process checks use capped polling.

## Deviations

- No named Task 2 test was omitted.
- The earlier theme’s RED output could not be independently reported.
- The required final `make validate` and `make test` were **not run**, as directed for this split execution.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: run as four themed pi runs (Task 1 in two, Task 2 in two) from the start because earlier plans' single runs stopped early; commits 023cb04f (Task 1) and 6022cce8 (Task 2); the commit hook ran the six static gates on both.
- Named tests: all 30 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9601 passed, 6 skipped, coverage 96.42%.
- Python 3.15 targeted run (`uv run --python 3.15 --isolated pytest` on tests/test_schedule_runner.py, test_setup.py, test_update_all_contract.py, test_update_all_job.py): all passed.
- Provisional decisions (need owner confirmation): D-10, D-11, D-16, review decisions of rounds 1 to 3 for this plan (own session and group per command with the capped cleanup and `_UPDATE_ALL_STOP_BUDGET`; root refused before the lock including the stdlib timer entry; the fd-0 redirect for queries; kernel-lock verified parent handoff; runner injected at the pnpm replay and terminal reload sites, which also tightens the per-tool rows; the vendor-script and new-session residuals accepted).
- Not proven here: the real wrapper chain under `uv run` (the real stop sequence through uv) is covered by fakes and a real-process test only; the container run of plan 35-09 is the real check.

orchestrator-verification: none required
