# Phase 35 Plan 03 Summary

- **Task 1 — daily record and per-tool deduplication:** commit `8d72c80b`. Added the strict, link-safe record, structured mutation evidence, and per-tool row handling. The earlier executor’s RED and GREEN output was not available in this split run; the targeted tests passed in the Task 2 verification.
- **Task 2 — run-log primitives:** commit `538d6d9d`. Added link-safe truncation, non-blocking regular-file append with short-write handling, and sanitized, bounded log lines.

## Verification

- **Task 2 RED:** four new tests failed with the expected `AttributeError` for the missing log functions.
- **Task 2 GREEN:** targeted pytest command exited 0, reaching `[100%]`.
- The first commit attempt found formatting and strict typing errors in the new tests. Both were fixed; their individual gates and the subsequent commit hook passed.
- **Final `make validate` tail:** lint, format-check, typecheck, security, dead-code and shellcheck all `Passed`.
- **Final `make test` tail:** `9522 passed, 6 skipped in 79.43s`; total coverage `96.43%`, above the 90% requirement.
- Each command’s owned scratch directory was removed by its exit trap. Pytest and the final gates used the default TMPDIR as instructed.

## Decisions

- **35 D-12 — own reasoning, needs confirmation:** truncate the last-run log at start and append one link-safe, non-blocking line per tool. Plan 35-04 supplies its executor.
- **35 D-13, corrected by orchestrator decision 6 — provisional, needs confirmation:** use `atomic_replace_entry` and a strict `read_capped(..., follow_symlinks=False)` reader; accept the closed set of update schedule IDs; type-check dates and `by` before use and validate date shape before parsing.
- **35 D-14 — own reasoning, needs confirmation:** per-tool rows skip only updates recorded by `update-all` today; `update-all` will skip updates recorded by either runner. This preserves the per-tool six-hour cadence.
- **Review C1 — provisional, needs confirmation:** deduplication follows `ToolRun.mutated`; unreadable or unsaved records are surfaced in the result line.
- **Review H2, M2 and M3 — provisional:** type-check the reader, use a non-blocking regular-file append, and land the record module with its first production caller.
- **Review B1 and B2 — provisional, needs confirmation:** `UpdateOutcome.mutated` records evidence of successful mutation, including subsequent smoke-check failures; an unsuccessful mutating command remains unrecorded because a skip requires evidence. Sample the record date after the update.
- **Orchestrator decision 10 — provisional, needs confirmation:** use an injected clock, avoid timing-sensitive assertions, guard date parsing with a shape regex, and use POSIX `os.mkfifo` on supported platforms.

## Pin edits and deviations

- No existing test assertions were edited in Task 2. All four named Task 2 tests were written.
- Task 1’s original RED and GREEN output could not be reconstructed from its commit; it was not rerun in RED.
- No live scheduler, notification, container, or real update was run. The log’s production caller remains for plan 35-04.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: both tasks completed first time: commits 8d72c80b (Task 1) and 538d6d9d (Task 2).
- Named tests: all 34 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9522 passed, 6 skipped, coverage 96.43%.
- Python 3.15 targeted run (`uv run --python 3.15 --isolated pytest` on tests/test_update_all_rows.py, test_update_all_state.py, test_update.py, test_schedule_update.py): all passed.
- Provisional decisions (need owner confirmation): D-12, D-13 (corrected by orchestrator decision 6), D-14, review decisions C1, B1/B2 (mutation evidence from the service; an unsuccessful mutating command stays unrecorded), H2/M2/M3, orchestrator decision 10.
- The run-log functions have their production caller in plan 35-04 (named one-plan exception of the plan).

orchestrator-verification: none required
