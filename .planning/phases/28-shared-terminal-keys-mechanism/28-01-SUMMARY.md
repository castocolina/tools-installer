---
phase: 28-shared-terminal-keys-mechanism
plan: 01
subsystem: terminal key regions
tags: [terminal-keys, golden-bytes, behavior-preserving-move, terminal_regions]
requires:
  - phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
    provides: the onboarding skill and its table that name the mechanism this phase builds
provides:
  - "tests/test_terminal_keys.py: six golden-byte tests that pin the Alacritty keys files before the move (D-10)"
  - "installer/terminal_regions.py: the shared owned-region primitives and the Alacritty plan, moved out of terminal_shell with public names (D-05)"
affects: [28-02, 28-03, 28-04, phase-29]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "Golden bytes committed against the unchanged code, then a move that must leave them equal"
    - "An AST check over every function that stays, so 'moved verbatim' is proved, not claimed"
key-files:
  created:
    - tests/test_terminal_keys.py
    - installer/terminal_regions.py
  modified:
    - installer/terminal_shell.py
    - tests/test_tool_onboarding_skill.py
key-decisions:
  - "The loop-local `marker` in the moved region replacer is renamed `text_line`, because the new public helper is also called `marker` (review H1: an UnboundLocalError otherwise)"
  - "The one existing-test edit is the source path in tests/test_tool_onboarding_skill.py that reads where the `alacritty: partial: you already bind` literal now lives (OQ2)"
requirements-completed: []
coverage:
  - id: D1
    description: "The Alacritty keys files (config text, record file, created marker) are pinned byte for byte before the move, and still equal after it"
    requirement: "KEYS-01"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_terminal_keys.py (6 golden tests, orchestrator run, green before and after the move)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The owned-region primitives live in installer/terminal_regions.py with no upward import, and every other function of terminal_shell is AST-identical"
    requirement: "KEYS-01"
    verification:
      - kind: other
        ref: "the plan's AST check prints BODIES-UNCHANGED 32 with no STALE, CHANGED or NOT-MOVED line (orchestrator run)"
        status: pass
    human_judgment: false
duration: 9min (executor)
completed: 2026-11-20
---

# Phase 28 Plan 01 Summary

- **Task 1 — `467b575c`** (`test(28-01): pin the Alacritty keys bytes before the move`): Added six golden-byte tests using the public install, sync, and removal routes. Passing pre-move run: `6 passed`.
- **Task 2 — `c7bde357`** (`refactor(28-01): move the owned-region primitives into installer/terminal_regions.py`): Moved the shared primitives and Alacritty planning helpers; updated the onboarding test's source path. Targeted tests: **passed**. AST check: `BODIES-UNCHANGED 32`.
- **`make validate`**: passed all six static gates.
- **`make test`**: `7878 passed, 6 skipped`; coverage **96.21%** (required: 90%).

**Owner confirmation required — D-06:** the pending/drift behavior amendment remains provisional.
**Owner confirmation required — amended SPEC R3 round-trip wording:** the stated newline behavior remains provisional.
**Owner confirmation required — D-12 import-line deviation to `tests.test_terminal_keys`:** flag retained for orchestrator review.

**Deviation:** The only existing-test edit was the plan-authorized one-line source-path change in `tests/test_tool_onboarding_skill.py`. No other tracked changes remain.

Skipped: No push, merge, or branch integration performed. The pre-existing untracked planning file was left untouched.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 9 minutes (09:48 to 09:57), stderr empty, two commits; the pre-existing untracked goals file is byte-identical.
- **Checked by the orchestrator:** all plan acceptance criteria pass (six golden tests, four module-level installer imports in the golden test, task 1 subject, six primitives in `terminal_regions` with exactly two `installer.` imports and no upward one, the `partial:` literal moved out of `terminal_shell`, the three old private definitions gone, 14 `terminal_regions` import statements in `terminal_shell` against the plan's `>=2`, `text_line` three times, no bypass marker); `git show --stat 467b575c` touches only the new test file, so the golden test really precedes any production change; the plan's targeted pytest run over seven test files passes; the plan's AST check prints `BODIES-UNCHANGED 32`; only `tests/test_tool_onboarding_skill.py` changed among existing tests, by one line out and one in.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,878 passed, 96.21%). The push gate runs the full suite again.
- **Provisional decisions carried to the verification report:** 28 D-06, the amended SPEC R3 round-trip wording (backlog 999.27), and the D-12 import-line deviation to `tests.test_terminal_keys` (decided in plan 28-02).
