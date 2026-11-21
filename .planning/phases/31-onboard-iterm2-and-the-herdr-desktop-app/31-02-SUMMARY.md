# Phase 31 Plan 02 Summary

## Tasks

- **Task 1 — `309ad08d`:** Added the iTerm2 profile generator, keyboard-map merge, proof and validation functions, and state record. Its RED and GREEN output was not available in this split run; the commit and its test files were verified.
- **Task 2 — `00c635e0`:** Added the `defaults` seam, command builders, default-profile hooks, recovery-state handling and tests. Added the autouse fixture in `tests/conftest.py` so tests cannot invoke the real macOS `defaults` tool.
  - RED: the targeted command failed on the missing seam and hooks.
  - GREEN: the specified targeted command exited 0; its output ended at `100%` with no failures. Additional targeted tests for the shared fixture also exited 0.
  - The first commit-hook attempt failed on line-length errors; those were corrected, `make lint` passed, and the commit passed all six hook gates.

## Final gates

- `make validate`: **passed** — lint, format, typecheck, security, dead-code and shellcheck all passed.
- `make test`: **failed** — `1 failed, 8378 passed, 6 skipped`; coverage was **96.24%**, above the 90% requirement. The failure was `tests/test_reachability.py::test_every_installer_module_is_reachable_from_an_entry_point`, reporting `installer.iterm2_profile` as unreachable. The same test failed alone with the same result.

## Provisional decisions (need confirmation)

- 31 D-08: Option stays Normal and word navigation is two keyboard-map rows (amends NTERM-02, SPEC R1, ROADMAP criterion 1); flagged, needs confirmation.
- 31 D-07 with the orchestrator correction: no claim that one malformed file blocks every reload; values from the iTerm2 source at v3.7.8, confirmed in the Mac UAT; needs confirmation.
- 31 D-09 with orchestrator decision 3: the parent's key map is merged only when readable from the exported preferences; the 2-, 3- and 4-part spelling matching is unverified on a Mac; needs confirmation.
- 31 D-10: the dark-green palette values are this plan's own until the owner names them; needs confirmation.
- 31 D-11: the default-profile hook, its recorded state and the restore rules; needs confirmation.
- 31 D-12 and the 2026-11-21 amendments to D-07, D-09, D-11 and D-16 need owner confirmation.
- The iTerm2 uninstall ordering and refusal, parent key-map rule, `keys.json` edge cases, and accepted `shortcut:` limits need owner confirmation.

## Deviations and remaining risk

- The long named custom-folder/unreadable/non-GUID test was renamed to satisfy the lint line-length gate; its principal scenarios are tested.
- Not every specified assertion was written: the lost-record matrix does not separately assert the absent-preference variant for every record state, and some fault and restore variants have less exhaustive argv/message assertions than requested.
- The reachability failure remains for the orchestrator to resolve with the planned wiring; no gate was bypassed. Real macOS behavior remains unverified.
- Each owned scratch directory was removed by its exit trap. Targeted tests and final gates used the default `TMPDIR`.

## Orchestrator verification

Checked 2026-11-21 03:20 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding, run as part a (Task 1, 03:03 to 03:04) and part b (Task 2 and gates, 03:05 to 03:09)).

- The executor's first line was `BLOCKED: make test fails the reachability gate because installer.iterm2_profile is not imported by a production entry point`. That is a plan-ordering consequence, not a defect: the new module is wired by plan 31-03 (the iTerm2 row imports it) and the guard `tests/test_reachability.py::test_every_installer_module_is_reachable_from_an_entry_point` is deliberately strict (not to be weakened). The orchestrator re-ran the full suite on the committed tree: exactly one failure, that test (`1 failed, 8378 passed, 6 skipped`, coverage 96.24%); the suite is red between this plan and 31-03 only, and nothing is pushed in between (the push gate runs on the final tip). The BLOCKED line is dropped.
- Commits since `ff83c48d`: `309ad08d` (profile generator, key-map merge, proof, state record), `00c635e0` (the `defaults` seam, default-profile hooks, recovery state, the autouse fixture in `tests/conftest.py`); each passed the commit hook. Plan verifies re-run by the orchestrator (`run_plan_verifies.py 31-02`): all exit 0.
- Tests read: the plan's review-driven cases exist (four starting states, failed restore keeps the previous default recorded, a lost recovery record is not a confirmed restore, a restore before removal leaves a retryable switch, a retry preserves a later user choice, the first switch writes only while the default is still the previous one, a failed capture inhibits the switch even with an old record, a failed record update after the restore refuses the removal, a tampered record never reaches `defaults`, fault injection at each transition, the seam fails closed without a fake). The executor reports two weaker assertions (the absent-preference variant of the lost-record matrix and some argv/message details); the long-named custom-folder test was renamed to satisfy the line-length gate.

herdr-app-container: not run
