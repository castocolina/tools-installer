# Phase 29 Plan 01 Summary

## Tasks and commits

- Task 1 — `566737b`: Alacritty Ctrl+Shift+K now sends Ctrl+L; recorded phase-28 regions report pending and reconfigure to the new bytes.
  - RED: the targeted suite failed on the old Alacritty bytes and summary; the new clear and drift tests also failed as expected.
  - GREEN: targeted pytest suites passed.
- Task 2 — `cab27a1`: Added placement, callable writes, config-path-aware plans, notes, read-back, opt-in status validation, and path-bound created-file cleanup; WezTerm shell regions now use exact markers and land before `return config`.
  - RED: collection failed because `Placement` and `WEZTERM_SKELETON` were not defined.
  - GREEN: targeted pytest suites passed; focused placement, read-back, cleanup, and WezTerm tests passed (`14 passed`).

## Gates

- `make validate`: passed.
- `make test`: passed on retry. The first run had one unrelated doctor-output test failure caused by output wrapping; that test passed alone and the full suite passed on retry.
- Scratch directories created for test runs were removed.

## Decisions and notes

- **29 D-08 / 28 D-06: needs owner confirmation.** Existing Alacritty installs rely on the phase-28 drift rule to pick up the new bytes; no migration code was added.
- **Architecture rule 5:** `Placement.TOP`, callable `Writes`, `KeysPlan.notes`, and the new row hooks have no production callers until plans 29-02/29-03. `Placement.BEFORE_RETURN` is used now by WezTerm shell sync.
- Created marker and path sidecar are removed together only along phase-28 cleanup paths; if the sidecar is absent or points elsewhere, cleanup leaves both records and the config untouched.
- Existing test edits: `tests/test_terminal_keys.py` updates Alacritty summary/region expectations, replaces the old clear-history assertion, extends the row field list, and updates the fixture plan signature/call for the new path argument. `tests/test_terminal_shell.py` updates the Alacritty clear assertion and adds the two WezTerm marker-placement regressions. Alacritty created-file goldens were unchanged.
- Deviations: no live container, GUI, or WezTerm D-07 cwd check was run, as instructed. `herdr-keys: not run`; `D-07 cwd check: not run`.
- Final reviewer dispatch was attempted but unavailable due to provider/model authentication ambiguity; no fresh subagent review was completed.

Skipped static checks by hand per the owner’s gate rule; the commit hooks and `make validate` covered them. Main remaining risk: owner confirmation of the provisional 28 D-06 dependency.

## Orchestrator verification

Checked 2026-11-20 14:40 by the orchestrator, independently of the executor's report (pi, router-env/my-coding-lite, started 13:33:44, exit 0 at 13:51).

- Commits since `9adc1bb0`: `566737bc` (Alacritty one-tuple change) and `cab27a19` (row interface). Both passed the commit hook.
- Plan verifies 1-4 re-run by the orchestrator (`run_plan_verifies.py 29-01`): all exit 0; the Alacritty golden and created-file tests are unedited.
- Test edits read from the diff: only the listed exceptions (Alacritty summary/region/clear assertions, the row field list, the fixture plan signature) plus new tests.
- Production diff read: `Placement`, callable `Writes.snippet`, `KeysPlan.notes`, `readback`, `validate_on_status`, `bind_created_path` with the `-path` sidecar, exact-marker WezTerm shell region. `make validate` and `make test` are re-run once at the end of the phase.
- Known limit (accepted in 29 plan review): an already-moved WezTerm shell region stays where it is.
