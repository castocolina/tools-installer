---
phase: 28-shared-terminal-keys-mechanism
plan: 03
subsystem: terminal key regions
tags: [terminal-keys, drift, reconfigure, clear-chord, same-directory, fixture-rows]
requires:
  - phase: 28-02
    provides: the TERMINAL_KEYS table and the table-driven dispatch
  - phase: 28-04
    provides: the zsh Ctrl+L widget the generic clear chord maps to
provides:
  - "D-06 drift: a recorded install whose keys region was edited reads pending and reconfigure restores it; a region the user deleted after a recorded apply stays quiet; an unreadable or refusing file stays quiet (OQ1)"
  - "clear_binding and the shared CTRL_L default: every row maps the clear chord to send-Ctrl+L, proved on fixture rows (Cmd+K on macOS, Ctrl+Shift+K on Linux)"
  - "A required same_directory field on every row with the three declarations Vendor, Writes and NotApplicable; a test fails when a row leaves it undeclared, and a test pins the row's field set"
affects: [phase-29, phase-30, phase-31]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "A required dataclass field with no default, so an undeclared row cannot be built"
    - "Fixture rows prove a generic rule before any real row uses it"
key-files:
  created: []
  modified:
    - installer/terminal_keys.py
    - tests/test_terminal_keys.py
    - tests/test_version_status.py
key-decisions:
  - "D-06 is built as decided and stays provisional (needs owner confirmation); OQ1: a recorded install whose file refuses or fails to read stays quiet, as today"
  - "clear_binding has no production caller in this phase (rule 5 allows it because the SPEC requires the proof on a fixture row); phase 29's kitty and WezTerm rows are its first callers"
requirements-completed: [KEYS-02, KEYS-03, KEYS-04]
coverage:
  - id: D1
    description: "Deleting or editing a terminal's keys region reads as pending per the D-06 table, and a reconfigure restores a drifted region"
    requirement: "KEYS-02"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_terminal_keys.py tests/test_version_status.py -k 'drift or two_applies' (orchestrator run, plan verify 2)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The mechanism maps the clear chord to Ctrl+L for every row and every row declares the same-directory rule; an undeclared row fails a test"
    requirement: "KEYS-03"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_terminal_keys.py -k 'same_directory or clear or declared_set' (orchestrator run, plan verify 4)"
        status: pass
    human_judgment: false
duration: 14min (executor)
completed: 2026-11-20
---

# Phase 28 Plan 03 Summary

- **Task 1 — Drift reconfigure (15b98f2c):** Added drift detection, recorded-region reapply, and status coverage. RED: 4 expected failures in the focused run; GREEN: 28 passed in the focused run. The five-file targeted suite also passed.
- **Task 2 — Clear chord and same-directory rule (ce04ce72):** Added the shared clear binding, required same-directory declaration, and fixture-row tests. RED: test collection failed because the new `CTRL_L` import was not yet implemented. GREEN: 7 passed in the focused run; the four-file targeted suite also passed.
- **Full validation:** `make validate` passed all six static gates.
- **Full tests:** `make test` passed — 7,920 passed, 6 skipped; coverage 96.24%.
- **Needs owner confirmation — D-06/OQ1:** The provisional rule treats only never-applied or drifted regions as pending; recorded deleted regions and recorded unreadable/refusing files remain quiet.
- **Needs owner confirmation — amended SPEC R3 round-trip wording:** Retain the owner-confirmation flag for the amended wording.
- **Needs owner confirmation — D-12 import-line deviation:** Retain the owner-confirmation flag for the deviation to `tests.test_terminal_keys`; `clear_binding` has no production caller in this phase, consistent with architecture rule 5, and phase 29's rows are its first production callers.
- **Concurrency:** No race test was added; the sequential apply and reconfigure-then-uninstall tests are proxies only. Compare-before-commit narrows, but does not eliminate, the concurrent writer window.
- **Deviations:** None to the requested implementation or scope. The pre-existing untracked planning file remains untouched.

Skipped real-install and race testing; concurrent writes retain the documented compare-before-commit window.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 14 minutes (10:27 to 10:41), stderr empty, two commits; the pre-existing untracked goals file is byte-identical.
- **Checked by the orchestrator:** all plan acceptance criteria pass (nine `test_drift_` tests, the two `test_version_status.py` tests, the `recorded = skip_recorded and record.exists()` flag replacing the early return, the five required definitions in `terminal_keys.py`, `same_directory` with no default, one `row.plan(` call, the field-set test, Konsole still outside the table, no bypass marker in any added line); the plan's four non-make verify commands exit 0; no pre-existing test file lost a line (the two removed lines are in `tests/test_terminal_keys.py`, created in plan 28-01); the table still holds only the Alacritty row.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,920 passed, 96.24%). The push gate runs the full suite again.
- **Provisional decisions for the verification report:** 28 D-06 with OQ1, the amended SPEC R3 round-trip wording (backlog 999.27), and the D-12 import-line deviation to `tests.test_terminal_keys` (plan 28-02).
- **Behavior to know:** hosts with zsh show `≈ apply install tuning` on the zsh row until a reconfigure writes the new block (plan 28-04).
