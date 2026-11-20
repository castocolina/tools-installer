---
phase: 28-shared-terminal-keys-mechanism
plan: 02
subsystem: terminal key regions
tags: [terminal-keys, table-driven-dispatch, completeness-test, tracer]
requires:
  - phase: 28-01
    provides: installer/terminal_regions.py and the golden-byte tests
provides:
  - "installer/terminal_keys.py: one TERMINAL_KEYS table keyed by registry tool id; apply, pending and strip run through it (D-01, D-02, D-04)"
  - "The three dispatch sites (post_install.py, version_status.py, app.py) look up TERMINAL_KEYS.get(tool.id) and no longer branch on the Alacritty id"
  - "A completeness test with a failing fixture in both directions (a tool with no row, a row with no tool) and a refusal line for a registry tool that names the action but has no row"
affects: [28-03, 28-04, phase-29]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "A closed Final[dict] table keyed by registry tool id, with required fields before defaulted ones"
    - "A completeness test that fails against a fixture registry in both directions, so an always-empty checker cannot pass"
key-files:
  created:
    - installer/terminal_keys.py
  modified:
    - installer/terminal_shell.py
    - installer/post_install.py
    - installer/version_status.py
    - installer/app.py
    - tests/test_terminal_keys.py
    - tests/test_terminal_shell.py
key-decisions:
  - "The four existing import lines in tests/test_terminal_shell.py now import apply_alacritty_keys from tests.test_terminal_keys: a production wrapper with no production caller is forbidden by architecture rule 5. This changes locked D-12 (installer.terminal_keys) and needs owner confirmation"
  - "The install site uses TERMINAL_KEYS.get with a refusal line, not an index, so a registry tool that names the action without a row cannot raise a bare KeyError"
requirements-completed: [KEYS-01]
coverage:
  - id: D1
    description: "Alacritty's keys are applied, checked, re-applied and stripped through one table keyed by registry tool id, and no dispatch site branches on the Alacritty id"
    requirement: "KEYS-01"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py (plan verify, orchestrator run) and the DISPATCH-CLEAN check"
        status: pass
    human_judgment: false
  - id: D2
    description: "A registry tool with apply_terminal_tuning and no row fails a test, and a table key with no declarer fails a test; Konsole stays outside the table"
    requirement: "KEYS-02"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_terminal_keys.py -k 'completeness or without_a_row' (6 passed, orchestrator run)"
        status: pass
    human_judgment: false
duration: 13min (executor)
completed: 2026-11-20
---

# Phase 28 Plan 02 Summary

- **Task 1 — `5b8364db`** (`feat(28-02): run the terminal keys through one table keyed by registry tool id`)
  - RED: targeted run failed with `ModuleNotFoundError: No module named 'installer.terminal_keys'`.
  - GREEN: targeted tests passed; dispatch check printed `DISPATCH-CLEAN`.
- **Task 2 — `4e2889c4`** (`test(28-02): fail when a registry tool has apply_terminal_tuning and no keys row`)
  - RED: completeness-focused run reported **5 failed** with `NameError` for the missing helpers; the backstop test passed.
  - GREEN: targeted run **13 passed**; completeness-focused run **6 passed**.
- **`make validate`**: passed all six static gates.
- **`make test`**: **7,885 passed, 6 skipped**; coverage **96.21%**, above the 90% requirement.
- **Dispatch check**: `DISPATCH-CLEAN`.
- **D-12 deviation — needs owner confirmation:** the four existing import lines use `tests.test_terminal_keys`, not D-12's specified `installer.terminal_keys`.
- **D-06 — needs owner confirmation:** the pending/drift behavior remains provisional.
- **Amended SPEC R3 round-trip wording — needs owner confirmation:** the stated newline behavior remains provisional.

Skipped: No push, merge, or branch change. The pre-existing untracked planning file was left untouched.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 13 minutes (09:59 to 10:12), stderr empty, two commits; the pre-existing untracked goals file is byte-identical.
- **Checked by the orchestrator:** all plan acceptance criteria pass (one `TERMINAL_KEYS` table, exactly three `installer.` imports in `terminal_keys` and none of `terminal_shell`, the record path derived from the key, the five old Alacritty definitions gone from `terminal_shell`, four repointed import lines, one `TERMINAL_KEYS.get(tool.id)` per dispatch site, `missing_rows` and `extra_rows`, the Konsole-outside check, the fixture message, the `== {"ghost"}` reverse-direction fixture, no bypass marker); the plan's four non-make verify commands all exit 0 (the seven-file targeted run, `DISPATCH-CLEAN`, the 13-test file run, the 6-test completeness run); the only existing-test edits are the four import lines in `tests/test_terminal_shell.py`; the one `"alacritty"` literal left in the dispatch sites is the `_TERMINAL_ROWS` display row in `version_status.py`, which the plan expects.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,885 passed, 96.21%). The push gate runs the full suite again.
- **Provisional decisions to carry into the verification report:** 28 D-06, the amended SPEC R3 round-trip wording (backlog 999.27), and the D-12 import-line deviation above.
