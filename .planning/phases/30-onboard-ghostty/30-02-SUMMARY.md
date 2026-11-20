# Phase 30 Plan 02 Summary

## Tasks and commits

- **Task 1 — `eb09aabf`:** Added desktop-rendering and smoke-TMPDIR seams. The prior executor reported RED with four expected failures and GREEN at `[100%]`.
- **Task 2 — `f527c36e`:** Added AppImage menu placement, ownership checks, rollback, and receipt artifact paths. RED: collection failed because `installer.appimage_menu` did not exist. GREEN: targeted tests reached `[100%]`.
- **Task 3 — `a1332323`:** Wired menu placement into installation, filtered no-receipt uninstall evidence, and updated the registry comment. RED: six expected integration failures. GREEN: targeted tests reached `[100%]`.

## Final gates

- `make validate`: **passed** all six static gates.
- First `make test`: **1 failed, 8109 passed, 6 skipped**; coverage **96.27%**.
- The failing doctor test passed alone. The permitted full-suite retry failed on the same assertion: **1 failed, 8109 passed, 6 skipped**; coverage **96.27%**.

## Decisions and limitations

- Applied 30 D-07 and orchestrator decisions 1, 4, and 6: receipt-backed menu leaves, removal of `X-KDE-Shortcuts`, and installer-owned temporary directories for smoke and extraction.
- Replacement uses the tool’s own receipt; rollback is best-effort and reports failed restoration. A destination symlink is refused immediately before writing. A regular-file swap in the remaining race window is an accepted limitation.
- Menu extraction runs on install, not update. Paths use literal `~/.local/share`, not `XDG_DATA_HOME`.
- The registry comment now describes placement in the present tense, per review decision L1.
- **Needs owner confirmation:** 30 D-03.
- **Needs owner confirmation:** 30 D-08, including the decision that a user `command` in any default file writes no shell region.
- **Needs owner confirmation:** 30 D-10.
- **Needs owner confirmation:** 30 D-17.
- **Needs owner confirmation:** SPEC R4 amendment following 28 D-06.
- The synthetic desktop fixture is reconstructed from recorded keys; it is **not** byte-identical to the real 694-byte upstream file.
- Deviation: Task 2 combined several requested failure cases into parametrized tests and did not add all individually named acceptance tests or the two requested `tests/test_download.py` artifact-path tests.
- Python 3.12 ran locally; Python 3.15 remains for CI.
- Each test run’s temporary directory was removed by its exit trap. The pre-existing untracked goal file was left untouched.

## Orchestrator verification

Checked 2026-11-20 20:40 by the orchestrator, independently of the executor's report (pi, router-env/my-coding; first run 20:27 to 20:25:22 stopped after Task 1 with an unjustified BLOCKED, a second run resumed Tasks 2 and 3 and ended 20:34:50, exit 0).

- The executor's first line was `BLOCKED: make test failed twice on tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing` (output wrapped `opt/subl` as `opt/ subl`). The orchestrator re-ran the full suite on the committed tree with the default TMPDIR: `make test` exit 0, 8110 passed, 6 skipped, coverage 96.27%. The doctor test's output wrapping depends on path lengths, and the executors ran with `TMPDIR` exported to a long scratch directory (the plans' scratch rule); from plan 30-03 on the run notes tell executors to run `make test` with the default TMPDIR. The BLOCKED line is dropped.
- Commits since `8410e11c`: `eb09aabf` (first run), `f527c36e`, `a1332323`; each passed the commit hook. Plan verifies 1 to 3 re-run by the orchestrator (`run_plan_verifies.py 30-02`): all exit 0.
- Deviation read: the plan names about a dozen tests individually (rollback, extraction failure, symlink, unsafe id, artifact-path tests); the executor covered them with parametrized tests of other names (`test_write_failure_rolls_back_and_reports_failed_restore`, `test_extraction_failures_write_nothing`, `test_a_destination_swapped_for_a_symlink_after_the_check_is_refused`, the engine tests in `tests/test_appimage_menu.py`) and added no `test_download.py` artifact-path test for the `desktop` key. The behaviors are covered (the unsafe desktop id is refused by the loader tests of 30-01 and the receipt leaves by the engine test); the named-test grep checks of the plan do not hold literally.

ghostty-container: not run

No container, GUI, or real AppImage was run. The repeated full-suite failure remains unresolved.
