# Phase 35 Plan 06 Summary

The plan ran as themed pi runs; Task 1 needed a gap-closing run because the first executor left four named scenarios open. The text below is the executors' own final notes.

## Task 1 (`70381d78`) and gap closing (`871b83b2`)

**Commit:** `871b83b2` — `test(35-06): close the plan-mode scenarios the first run left open`

Added coverage for the two-day confirmation windows and newer failures; differing evidence with and without a planned manager; the manual real-run `setup.main` route; and symlink targets in the no-write snapshots. No production defect was revealed.

## Verification

- **RED:** No failing test was observed for these gap-closing cases: the implementation was already committed, and the new tests passed on their first run.
- **GREEN:** The requested targeted pytest command exited 0:
  ```text
  ........................................................................ [ 82%]
  ..............................                                           [100%]
  ```
- The first commit attempt exposed lint, formatting and typing errors in the new tests. They were corrected; their individual gates passed on rerun, and all six commit hooks passed on the successful commit.
- Run directories were removed by their exit traps.

## Existing-test edits and deviations

- Updated `tests/test_update_all_plan.py`; added the requested `WindowRefresher` double in `tests/update_all_doubles.py`. No other existing-test assertions were edited in this theme.
- None of the four scenarios named for this theme was omitted.
- Full `make validate` and `make test` were not run, as instructed for this partial execution.

## Decisions

- **35 D-18:** Plan mode takes no lock, writes no log, record or notification, and starts no update.
- **35 D-07 — provisional, needs confirmation:** Plan mode uses the cached window without forcing refresh.
- **Orchestrator decision 2 — provisional, needs confirmation:** “Writes nothing” means no installer-state writes; `hold_writes()` replaces the proposed scratch cache because receipt writes must also be held.
- **Orchestrator decision 1 — provisional, needs confirmation:** Preview judges dependents on the first pass and prints `PLAN_NOTE`.
- **Research O8:** `--plan` with `--parent-holds-run-lock` is a usage error.
- **Reviews H7, M4 and M8 — provisional, need confirmation:** Real cache and receipt paths are covered by the no-write proof; every preview prints the limit note; help scopes the claim to installer state.
- **Reviews F1, V1 and V2 — provisional, need confirmation:** Preview shares run confirmation rules; newer failures prevent confirmation; known receipt drift is skipped during planning while the runtime recheck remains.
- **Orchestrator decision 10 — provisional, needs confirmation:** Tests use fakes and scratch state without timing-sensitive assertions.

## Task 2 (`df296f5b`)

**Commit:** `df296f5b` — prove plan mode writes no installer state and amend SPEC R9.

The real-service tests cover plain, receipt-adoption, and receipt-retirement scenarios. They compare the scratch HOME before and after held refreshes, check repeatable plan output and lookups, and verify the exact cache or receipt change when writes are not held. A composition test verifies that neither direct planning nor `setup.main(... --plan)` calls `commit_writes()`.

## Verification

- **RED:** No behavioral RED was observed: the proof and controls passed against Task 1’s existing implementation. The first commit attempt exposed a pyright error in an untyped test lambda; it was fixed at the source.
- **Typecheck after fix:** `0 errors, 0 warnings, 0 informations`.
- **GREEN:** The requested four-file targeted pytest command exited 0; its output ended at `[100%]` with no failures.
- **Commit hook:** lint, format-check, typecheck, security, dead-code, and shellcheck all passed.
- Each pytest run directory was removed by its exit trap.

## Decisions

- **35 D-18:** Plan mode takes no run lock and writes no log, record, or notification; it spawns no update.
- **35 D-07 — own reasoning, needs confirmation:** Plan mode uses the cached window and does not force refresh.
- **Orchestrator decision 2 — needs confirmation:** “Changes nothing” means writes no installer state. The SPEC amendment records the deviation from a scratch-cache copy: `hold_writes()` also holds receipt adoption and retirement, and plan mode never commits those writes.
- **Orchestrator decision 1 — needs confirmation:** The preview judges dependents on the first pass and prints `PLAN_NOTE`.
- **Research O8 — resolved:** `--plan` with `--parent-holds-run-lock` is a usage error.
- **Review H7, M4 and M8 — provisional, need confirmation:** The proof covers real cache and receipt paths and exact control changes; every preview prints the note, including the differing-evidence explanation; help scopes the promise to installer state.
- **Review F1, V1 and V2 — provisional, need confirmation:** Preview confirmation shares the run’s evidence rules with the seven-day window; newer failed lookups are unconfirmed, and known receipt drift is refused during planning while runtime rehashing remains.
- **Orchestrator decision 10:** Tests use fakes and a scratch HOME; no timing-sensitive assertion was added.

## Pin edits and deviations

- No existing-test assertions were edited in this task; no named Task 2 test was omitted.
- No production fix was needed.
- `make validate` and `make test` were not run, as directed for this themed run. No live update, notification, timer, container, or remote write was attempted.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: themed pi runs; commits 70381d78 (Task 1), df296f5b (Task 2, also the dated SPEC R9 amendment) and 871b83b2 (a gap-closing run: the Task 1 executor listed four named scenarios it did not complete: the two-day confirmation controls, differing evidence with no manager planned, the manual real-run route, symlink-target snapshots; they are now real tests, no production defect found).
- Named tests: all 24 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): all non-make verifies passed.
- Full `make test` run once by the orchestrator with the default TMPDIR after the last commit: see the ledger line below (green); Python 3.15 targeted run on tests/test_cli.py and tests/test_update_all_plan.py passed.
- Provisional decisions (need owner confirmation): D-07, D-18, orchestrator decision 2 ("writes nothing" read as "writes no installer state"; `hold_writes()` instead of a scratch cache; SPEC R9 amended), review decisions of rounds 1 to 3 (shared confirmation helper with the preview window, a newer failed lookup is unconfirmed, receipt-drift mirror, the always-printed plan note).

orchestrator-verification: none required
