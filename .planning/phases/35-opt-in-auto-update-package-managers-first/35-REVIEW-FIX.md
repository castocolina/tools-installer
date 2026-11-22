# Phase 35 Review Fix

Fix rounds on router-env/my-coding (pi) after the read-only gates of 2026-11-22. Round A ran three times: the first run fixed three items and reported four `unfinished`; the retries finished them (one blocked on two older tests, finished by the orchestrator). Round B ran once. The orchestrator then verified: `make test` after the last commit (see the final line), targeted tests on Python 3.15, and a SECOND real container run of `update-all` on the fixed tree (PASS).

## Part A (process lifetime and safety guards)

| Item | Status | Commit | Note |
|---|---|---|---|
| Lane 1, ME-01, LO-01, LO-02 | fixed (real, reproduced) | `5db2f4dd` | The group cleanup is shielded from a second signal, a surviving group aborts the batch, a normal command exit also ends its process group, and the handlers are installed before the child is spawned. |
| Lane 2 | fixed | `07e8cf98` | `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK` for the update-all commands only; remaining package-manager side effects added to the limits list of the architecture rules. |
| Lane 3 | fixed | `3f3c555c`, `a4eac7e1` | A failed pnpm replay is reported in the log and result line and blocks pnpm dependents; a regression test runs the real `UpdateService` replay failure. |
| Lane 4 | fixed | `4bb03a2f` | A manager skipped as `unknown-owner` no longer authorizes dependents. |
| Lane 5 | fixed | `8da88aeb` | First-pass dependents of a failed manager whose second refresh did not answer appear as skip-only rows. |
| Lane 6 | fixed | `eff95bd5` | The guard compares package, method, active path and installed version with the evidence, not only the owner label. |
| Lane 9 | fixed (orchestrator) | `7183b30a` | The scheduled PATH carries `$PNPM_HOME/bin` (the registry's standalone pnpm location). The executor stopped on two older tests that pin the exact PATH list (`tests/test_schedules.py::test_clean_unit_path`, `::test_clean_unit_path_on_macos_and_with_pnpm_home`); the orchestrator edited their expected lists, which is the contract change itself. |

## Part B (planner, preview, tests, docs)

| Item | Status | Commit | Note |
|---|---|---|---|
| Lane 8, security note 1 | fixed | `327978e6` | The CLI refuses root for runs and previews before dependencies or settings are read. |
| Lane 10, LO-06 | fixed | `22798734` | The preview shows known cycle and missing-manager blocks instead of `would update`. |
| Lane 13 | fixed | `62117ae3` | The container rerun verdict checks the record's date and writer and distinguishes an already-current Ruff (installer evidence) from a proven daily skip. |
| LO-07 | fixed | `9cf8d020` | The escalation scan covers the files that can run commands and the formerly vacuous assertion is real. |
| NE-01, IN-01 | fixed | `ee0744ec` | Unreachable `None` ownership branches and the unused constant removed. |

## Edited existing assertions (record)

Only `tests/test_schedules.py::test_clean_unit_path` and `::test_clean_unit_path_on_macos_and_with_pnpm_home` (Lane 9, one more PATH entry per OS).
