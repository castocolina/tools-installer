# Phase 35 Plan 04 Summary

The plan ran as themed pi runs (Task 1 in four themes, Task 2 in three) because single runs stopped early; the text below is the executors' own final notes per task.

## Task 1 (`59275bdb`)

**Commit:** `59275bdb` — guarded update-all execution, two refresh passes, run log, and daily mutation records.

## Verification

- Task-targeted pytest command: **passed**, 297 tests.
- Commit hook: lint, format, typecheck, security, dead-code, and shellcheck **passed**.
- RED output from earlier themes was not available in this session. The tests added in this theme passed against the existing uncommitted implementation; no RED run was observed for them.
- Targeted test run directories were removed by their exit traps.
- `make validate` and `make test` were not run, as directed for this partial execution.

## Pin edits

No existing test files were edited.

## Decisions

- **35 D-06 and D-07 — own reasoning, needs confirmation:** failed owner or transitive dependency blocks updates; an uncompleted owner blocks its dependent; unknown, stale, or unconfirmed versions are not planned.
- **35 D-08 — jev overridden / own reasoning, needs confirmation:** one refresh pass per stage, caller-computed refusal evidence, and fresh-ownership guarding. **D-10:** use the existing per-tool update path and schedule lock. **D-12 and D-14 — own reasoning, needs confirmation:** run logging and daily deduplication. **D-13 and D-15:** mutation records and bounded summaries.
- **Orchestrator decision 1 and O7 — needs confirmation:** refresh dependents again after managers; count unchanged outcomes separately and unknown-version successful outcomes as updated.
- **Reviews H3, H4, A1–A8, B1, B2, and C1 — provisional, needs confirmation:** recency windows, fresh-ownership guard, owner-bound evidence, failure propagation, per-decision day, and grouped-package limit.
- **Decision 10 — provisional, needs confirmation:** fake external tools and clocks, avoid timing assertions, and bound result lines to 300 characters.

## Deviations

- The requested `catalog(*specs)` test helper was not added.
- The named `test_the_record_is_written_and_read_in_the_same_run` was not added under that name; record behavior is covered by `test_the_record_is_written_and_read_in_both_directions` and `test_records_survive_interruption_and_use_the_post_update_day`.
- The full executor-level A3 fresh-owner ordering scenario and owner-change comparisons across both the second pass and fallback were not separately asserted; the existing guard tests exercise their component decisions directly.
- The interruption test verifies the first record before midnight and the second afterward; the record writer deliberately prunes the previous day when writing the second record.

## Task 2 (`fab937ba`)

**Commit:** `fab937ba` — proved the update-all guard with a real service and exercised the run through the real runner and setup.

## Verification

- **RED:** The new runner scenarios failed as expected before the child supported them: the three-tool scenario returned `ok: 0 updated`, and the failing-manager scenario exited 0 instead of 1.
- **GREEN:** The task’s targeted pytest command exited 0; all displayed tests passed.
- **Commit hook:** All six static gates passed. The first commit attempt exposed import-order and strict-typing errors; those were fixed, and the affected gates were rerun successfully.
- Full `make validate` and `make test` were **not run**, as directed for this themed run.
- Each shell scratch directory was removed by its exit trap. Targeted pytest used the default `TMPDIR`, as directed.

## Pin edits

No existing assertions were changed. The existing job fixture gained a scenario parameter; its empty-scenario assertions remain intact.

## Decisions

- **35 D-06, D-07 — own reasoning, needs confirmation:** Fresh ownership and transitive requirements determine failure skips; an owner manager must have completed first. Unknown, stale, or unconfirmed versions are not planned.
- **35 D-08 — jev overridden / own reasoning, needs confirmation:** One pass per stage, caller-computed refusal evidence, and a guard on fresh ownership. **D-10:** Updates use the existing per-tool path and `run_schedule` lock. **D-12, D-14 — own reasoning, needs confirmation; D-13 and D-15** apply to logging, records and summary.
- **Orchestrator decision 1 and O7 — needs confirmation:** Dependents receive a second pass; up-to-date results count as unchanged, and updates with unknown versions count as updated.
- **Reviews H3, H4, A1–A8, B1, B2 and C1 — provisional, needs confirmation:** Includes owner-bound evidence, failure propagation through skipped managers, per-decision day sampling and the grouped-package limit.
- **Decision 10 — needs confirmation:** Use fake tool seams and clocks, avoid timing assertions and keep the result line within 300 characters.

## Deviations

All named Task 2 test functions were written. The real-service changed-ownership cases primarily exercise the guarded per-tool path directly; a separate test exercises a failed manager and changed dependent ownership through the executor.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: single pi runs stopped early twice (no commit, unjustified BLOCKED claims); the orchestrator split Task 1 into four themed runs (commit 59275bdb) and Task 2 into three themed runs (commit fab937ba), the second set also closing the Task 1 gaps its summary listed (catalog helper, executor-level A3 scenario, owner-change comparisons).
- Named tests: all 38 names in the tasks are defined (the seven Task 2 names were missing after Task 1 and exist now).
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9584 passed, 6 skipped, coverage 96.44%. The commit hook ran the six static gates on both commits.
- Python 3.15 targeted run (`uv run --python 3.15 --isolated pytest` on tests/test_update_all_run.py, test_update_all.py, test_update.py, test_schedule_update.py, test_schedule_runner.py): all passed.
- Provisional decisions (need owner confirmation): D-06, D-07, D-08 (jev overridden), D-10, D-12, D-14, orchestrator decisions 1 and 7, review decisions of rounds 1 to 3 for this plan (recency windows instead of fresh-this-pass; run_guarded with the private _run; owner-bound evidence; failure propagation through planner skips; per-decision day; replay accepted limit; unknown-version successful outcomes count as updated).

orchestrator-verification: none required
