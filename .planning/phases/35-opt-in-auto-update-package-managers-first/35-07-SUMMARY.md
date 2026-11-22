# Phase 35 Plan 07 Summary

The plan ran as themed pi runs (one per task); the text below is the executors' own final notes.

## Task 1 (`55993027`)

**Commit:** `55993027` — `feat(35-07): notify once with counts after an update-all run that changed something`

Added the notification builder and one executor notification attempt for runs with updated or failed tools. Added coverage for the notification matrix, bounded and sanitized result lines, and the real adapter handoff through a scratch recorder.

## Verification

**RED tail:** Six notification tests failed before implementation because `notification` was absent or no notification was sent. The nothing-to-report test passed.

**GREEN tail:**
```text
........................................................................ [ 49%]
........................................................................ [ 99%]
.                                                                        [100%]
```

The task’s targeted pytest command exited 0. The commit hook passed all six static gates. An initial hook attempt exposed a line-length issue and strict typing errors; those were fixed, and the affected gates passed on rerun. Every run directory created for these commands was removed by its trap.

## Decisions

- **35 D-17 (locked):** One injected `Notifier` call after a real run with something to report; a returned reason or exception adds a final `notify skipped` clause without changing the result.
- **Orchestrator decision 3 — needs confirmation:** Notify only when updated or failed count is nonzero. The dated SPEC amendment remains for Task 2.
- **Orchestrator decision 5 — provisional, needs confirmation:** The bus address rides through the runner’s per-job `readonly` environment; `_PASSED_ENV` stays closed. CONTEXT D-21’s contrary claim is not followed.
- **O7 — needs confirmation:** Unchanged results do not notify; a manager with an unreadable version can count as updated and notify each night.
- **Review G1 and H2 — provisional, needs confirmation:** The recorder test exercises the real `_schedule_run_deps` constructor; notification is an attempt, not a delivery guarantee.
- **Orchestrator decision 10 — provisional, needs confirmation:** Notifications contain counts and registry IDs only; tests use fakes or a scratch recorder, never a real desktop notification.
- **Review-round decisions — provisional, needs confirmation:** Recency windows replace fresh-this-pass; `run_guarded`, runner injection, kernel-lock proof, process-group stop budget, and SPEC, ROADMAP and REQUIREMENTS amendments remain subject to confirmation.

## Pin edits

None. No existing assertion was changed.

## Deviations

- The real-adapter recorder test was added before implementation but was not included in the RED selection; it passed in the final targeted run. All named Task 1 tests were written.
- Final `make validate` and `make test` were not run, as directed for this split Task 1 run.

## Task 2 (`65eaa7af`)

**Commit:** `65eaa7af` — amended SPEC R10 and pinned the update-all child’s environment.

## Verification

- **RED:** Not applicable as a failing run. The new test passed on its first run, as the plan expected for the existing read-only runner path: `. [100%]`.
- **GREEN:** The targeted three-file command exited 0: `........................................................................ [65%]` and `...................................... [100%]`.
- The commit hook passed all six static gates.
- Each run directory was removed by its trap. Targeted pytest used the default `TMPDIR`, as directed by the orchestrator.

## Decisions

- **35 D-17 (locked):** One injected `Notifier` call after a real run with something to report; a returned reason or exception adds a final `notify skipped` clause without changing the result.
- **Orchestrator decision 3 — needs confirmation:** Notify only when updated plus failed is greater than zero. SPEC R10 was amended and dated.
- **Orchestrator decision 5 — provisional, needs confirmation:** The bus address passes through the read-only job’s `extra_env`; it stays outside `_PASSED_ENV` and daemon environment keys. D-21’s contrary claim is not followed.
- **O7 — needs confirmation:** Unchanged results never notify; a manager whose version cannot be read counts as updated and may notify nightly.
- **Review G1 and H2 — provisional, needs confirmation:** Exercise the real dependency constructor in the recorder test and describe notification as an attempt.
- **Orchestrator decision 10 — provisional, needs confirmation:** Notifications contain counts and registry IDs only; tests use fakes and send no real notification.
- **Review M7 — provisional, needs confirmation:** `XDG_RUNTIME_DIR` is not forwarded; a nonstandard runtime socket requires an explicit bus address on the timer route.

## Pin edits

No existing assertions were edited. The new test covers the set and unset bus address, the per-tool update exclusion, both closed-environment pins, and the `XDG_RUNTIME_DIR` exclusion.

## Deviations

None. Every test scenario named by Task 2 has an assertion. The pre-existing untracked goals file was left untouched.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: two themed pi runs, both first time; commits 55993027 (Task 1) and 65eaa7af (Task 2, also the dated SPEC R10 amendment); the commit hook ran the six static gates on both.
- Named tests: all 17 names in the tasks are defined.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9638 passed, 6 skipped, coverage 96.43%.
- Python 3.15 targeted run on tests/test_schedule_runner.py, test_update_all_job.py, test_update_all_run.py: all passed.
- Provisional decisions (need owner confirmation): D-17, orchestrator decision 3 (notify only when updated plus failed is above zero; SPEC R10 amended), decision 5 (D-21's bus-address claim corrected: per-job `extra_env`), review decisions of rounds 1 to 3 (real adapter with a scratch notify-send recorder, the production `notify=` wiring exercised, notification described as an attempt, XDG_RUNTIME_DIR not forwarded).
- Not proven here: a real desktop notification or its delivery from a systemd user unit (owner UAT).

orchestrator-verification: none required
