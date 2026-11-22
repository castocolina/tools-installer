# Phase 35 Plan 09 Summary

The plan ran as themed pi runs (Task 1 in two themes, Task 2 in one); the text below is the executors' own final notes. The real container run is performed by the orchestrator after this summary (see the orchestrator section).

## Task 1 (`5f9f3631`)

**Commit:** `5f9f3631` — `feat(35-09): add the in-container update-all driver and its verdicts`

Added the container-only driver and host tests in `tests/e2e_update_all_driver.py` and `tests/test_container_e2e_update_all.py`.

## Test output

**RED tail** — after adding tests for the missing second-half behavior:

```text
FAILED ...::test_rc_finding - AttributeError
FAILED ...::test_evidence_round_trip_and_the_again_verdict - AttributeError
FAILED ...::test_the_driver_refuses_outside_the_container_and_a_bad_verb - AttributeError
```

**GREEN tail** — task verification after the commit:

```text
........................................................................ [ 63%]
.........................................                                [100%]
```

The command exited 0. The commit hook passed all six static gates. Each test-run scratch directory was removed by its exit trap.

## Existing-test edits

None. Both committed files are new.

## Decisions

- **35 D-20 — jev overridden, needs confirmation:** use a dedicated orchestrator-run target and real managers in the container; omit the brew-formula dependent and installed Java fixtures. This deviates from orchestrator decision 9’s proposed fake managers.
- **Orchestrator decisions 8 and 9 — needs confirmation:** require a `would update` uv plan line and standalone route; record replacement evidence. The target and PATH pin edits remain for Task 2.
- **Reviews H8, H9, H10, C2, D1, D2 and D3 — provisional, needs confirmation:** use older standalone uv and upgradeable Ruff, persist first-run evidence, bound the chain, identify the route, require installer evidence for an omitted Ruff, and count rerun start and result lines. A green suite does not close AUTOUPD-08.
- **Orchestrator decision 10 — needs confirmation:** use host fakes and portable shell practices; Task 2 must move the classified PATH pins with the usage text.

## Deviations and remaining verification

All named Task 1 test functions were added, but not every named scenario has an independent assertion. In particular, prerequisite health-check behavior and live verb integration were not fully exercised. The driver has not been validated against real manager output; the orchestrator should review those paths before relying on the instrument.

No container was started. **AUTOUPD-08: instrumented in part, real run not performed.** Task 2 and the final full gates were not run in this split execution.

## Task 2 (`c36bc26b`)

**Task 2 commit:** `c36bc26b` — added the orchestrator-run `update-all` target, gated steps, EXIT-trap markers, and host-only tests.

## Verification

- **RED:** Registration test failed because the `update-all` dispatch was absent. After the usage text grew, the PATH classification test reported the expected four shifted lines.
- **GREEN:** The prescribed targeted pytest command exited 0, ending at `[100%]`. The commit hook passed all six static gates.
- The first hook attempt found line-length and type errors; the second found formatting needed after those fixes. Both were corrected and their gates rerun before the successful commit.
- Test scratch directories were removed by their cleanup traps.

## Pin edits

`tests/test_shell_scripts_path.py` retained the existing reasons and shifted the four classified lines by 16: **460→476, 583→599, 638→654, 905→921**.

## Decisions

- **35 D-20 — jev overridden; needs confirmation:** Dedicated PID-named Fedora target with exact-name EXIT teardown and installer-driven container work. The fixture choices and use of real managers rather than decision 9’s proposed fakes remain provisional.
- **Orchestrator decisions 8 and 9 — needs confirmation:** The orchestrator alone runs the container; the uv plan and standalone route must be proven, with replacement and rc findings recorded. Static pins and PATH renumbering land here; `schedules` remains separate.
- **Reviews H8, H9, H10, C2, D1, D2 and D3 — provisional; needs confirmation:** Older standalone uv and upgradeable ruff, gated steps, persisted evidence, route identification, current dependent evidence, rerun counts, prerequisite checks, and the rule that a green suite does not close AUTOUPD-08.
- **Orchestrator decision 10:** Host `ct` fakes, no timing assertions, Bash 3.2-compatible shell, and PATH pin renumbering with the usage change.

## Deviations

- All Task 2 named tests were written. The shell test harness runs an extracted temporary script file rather than `bash -c`, as required by the test sandbox.
- Final `make validate` and `make test` were not run, as instructed for this themed executor run.

## Orchestrator verification

Orchestrator verification (2026-11-22, by the orchestrator, not the executor):
- Execution: themed pi runs; commits 5f9f3631 (Task 1, driver and pure verdicts) and c36bc26b (Task 2, the `update-all` container target, static pins, renumbered classified PATH lines).
- Named tests: all 21 names in the tasks are defined. The Task 1 executor reports that prerequisite health-check behavior and the live verb integration are not fully exercised by unit tests: the real container run below is the check for them.
- Plan verifies run by the orchestrator with an owned TMPDIR (removed afterwards): both <automated> pytest commands passed (all non-make verifies passed).
- Full `make test` run once by the orchestrator with the default TMPDIR: 9684 passed, 6 skipped, coverage 96.43%.
- Python 3.15 targeted run on tests/test_container_e2e_update_all.py and tests/test_shell_scripts_path.py: all passed.
- AUTOUPD-08: instrumented, real run not yet performed at the time of this note; the real container result is recorded in the verification report of the phase, not here.
- Provisional decisions (need owner confirmation): D-20, orchestrator decisions 8, 9 and 10, review decisions of rounds 1 to 3 (older seeded uv 0.11.0 and ruff 0.1.0, the route verdict, the installer-outcome label of the evidence, gated steps, RUN_BOUND, first-run evidence file).

orchestrator-verification: none required
