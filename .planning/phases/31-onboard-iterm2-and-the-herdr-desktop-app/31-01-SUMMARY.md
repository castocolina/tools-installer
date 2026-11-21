# Phase 31 Plan 01 Summary

- **Task 1 — Whole-file ownership:** `95d4a8be`. RED: `ImportError` for `DefaultProfile`; GREEN: targeted tests reached `[100%]`. The first commit attempt failed on two Ruff line-length errors; those were fixed.
- **Task 2 — Per-key ownership:** `1fdc97c9`. RED: `ImportError: cannot import name 'OwnedKeys'`; GREEN: the specified targeted pytest command reached `[100%]`. The first commit attempt failed lint, formatting and type checking; the failures were fixed and the commit hook passed all six gates.

## Final gates

- `make validate`: passed lint, format-check, typecheck, security, dead-code and shellcheck.
- `make test`: **8306 passed, 6 skipped**; coverage **96.25%**, exceeding the 90% requirement.

## Provisional decisions (need confirmation)

- 31 D-01: two variants (WholeFile, OwnedKeys) with the hook on the WholeFile variant; needs confirmation.
- 31 D-02: whole-file proof is the created record plus the fixed GUID; needs confirmation.
- 31 D-04: validate stays per row; needs confirmation.
- Orchestrator decision 5 (generic part): a blank keys file counts as missing, strip deletes a created file only when what remains equals the vendor default; needs confirmation.
- 31 D-08 and D-12; the 2026-11-21 amendments to D-07, D-09, D-11 and D-16; iTerm2 uninstall ordering and refusal; the parent key-map rule; and the keys.json edge cases all need owner confirmation.

## Accepted limits and backlog candidates

- `shortcut:` A symlink may be swapped after the check and before file access. Backlog candidate: use no-follow file operations if the configuration folder is shared.
- `shortcut:` The file is written before its created marker and records. Backlog candidate: improve recovery if interrupted writes occur.
- `shortcut:` The single-path ledger forgets ownership at an old path after a path change. Backlog candidate: maintain a ledger per path if moves become common.

## Deviations and remaining verification

Task 2 did **not** add every test case specified in the plan. In particular, the planned exhaustive path-change, seed-refusal, recorded-write-error, explicit-environment and pinned-default scenarios remain unverified. The passing suite therefore does not establish every plan acceptance criterion; these cases need follow-up before relying on the mechanism.

Each run directory created for the commands was removed by its exit trap. No real installation, GUI, macOS tool or container was run.

## Orchestrator verification

Checked 2026-11-21 03:10 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding; the whole-plan prompt was refused within 90 seconds, so the plan ran as part a (Task 1, 02:48 to 02:50), part b (Task 2 and gates, 02:51 to 02:55) and a completion run (03:00 on)).

- Commits since `b78e2062`: `95d4a8be` (whole-file mechanism), `1fdc97c9` (owned-keys mechanism), `8a4b5370` (the tests part b had skipped); each passed the commit hook. Plan verifies 1 and 2 re-run by the orchestrator (`run_plan_verifies.py 31-01`): both exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8334 passed, 6 skipped, coverage 96.29%.
- Deviation read and closed: part b admitted that Task 2 lacked tests the plan names (path change, seed refusal, recorded write error, explicit environment, pinned default). The orchestrator compared the plan's test list with the file, listed the behaviors without a test (two reconfigures and a reinstall, recorded ownership before the user-binding check, strip never calling the seed, strip deleting a created seed-only file, user sections surviving in any order, explicit home and environment, pending states, drift rewrite, no-byte-change second apply, the user-changed-value report) and had the completion run add them: `8a4b5370` adds sixteen tests, test-only, no production fix needed.
- Accepted limits (`shortcut:` comments in the code, backlog 999.31): the symlink check window, the file-before-marker write order, the single-path ledger.
- The four region rows and their tests are untouched (no existing test edited).

herdr-app-container: not run
