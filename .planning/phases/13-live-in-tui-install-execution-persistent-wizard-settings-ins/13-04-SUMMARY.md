---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 04
subsystem: installer-tui
tags: [execute-screen, tracer, wave-2]

requires:
  - phase: 13
    provides: "13-01 MECHANISM=A (call_from_thread + push_screen_wait), 13-02 StreamingRunner/should_continue, 13-03 Settings/SettingsStore"
provides:
  - installer/execute_screen.py with ExecuteInputs, ExecuteScreen, InstallLogLine, InstallRunFinished, attributed_install, sanitize_log_line
  - UnifiedApp pushes ExecuteScreen instead of exiting the process for interactive installs
  - setup.py seam split — interactive path never calls the console run_wizard
  - Pre-flight header rendered on screen before the install worker starts (D-05.1)
affects: ["13-05 worker-to-modal checksum-mismatch prompt", "13-06 link-mode picker wiring", "13-07 architecture.md rule-2 documentation"]

actuals:
  tokens: 40000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "ExecuteScreen pushed onto the running Textual app instead of process exit for interactive installs"
    - "setup.py _execute_inputs / _run_interactive_wizard seam split so console main() never imports run_wizard for the interactive path"
    - "Pre-flight header render happens in on_mount before action_start queues the worker"

key-files:
  created:
    - installer/execute_screen.py
  modified:
    - installer/wizard_app.py
    - installer/catalog_tui.py
    - setup.py
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
    - tests/test_setup.py

key-decisions:
  - "Task 1 tracer proves one staged tool installs end-to-end inside the running app (push, not exit) before the remaining screen behavior is built out in 13-05/13-06."
  - "setup.py's interactive path is split into ExecuteInputs/_execute_inputs/_run_interactive_wizard so the console run_wizard is no longer reachable from the TUI flow, keeping the two paths structurally separate."
  - "Pre-flight text renders synchronously in on_mount before action_start is called, satisfying D-05.1 (visible pre-flight before any subprocess starts)."

patterns-established:
  - "Screen-push-not-exit is the standing convention for any future in-TUI long-running operation."

requirements-completed: ["D-01", "D-02", "D-03", "D-04", "D-05"]

coverage:
  - id: D1
    description: "Staging a tool and confirming installs it inside the running app without exiting to the console."
    requirement: D-01
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py (Task 1 tracer test)
        status: pass
    human_judgment: false
  - id: D2
    description: "The interactive console wizard path (run_wizard) is no longer invoked when the TUI executes an install."
    requirement: D-02
    verification:
      - kind: unit
        ref: tests/test_setup.py (Task 2 seam-split tests)
        status: pass
    human_judgment: false
  - id: D3
    description: "A pre-flight summary is visibly rendered before any subprocess is spawned."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py / tests/test_wizard_app.py (Task 3 pre-flight tests)
        status: pass
    human_judgment: false

duration: 76 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 04: Live in-TUI install tracer — Summary

**A staged tool now installs end-to-end inside the running Textual app via a pushed `ExecuteScreen` instead of exiting to the console; `setup.py`'s interactive path is split so it never calls the legacy `run_wizard`; and the pre-flight summary renders before the install worker starts (D-05.1).**

## Performance

- **Duration:** 76 min
- **Started:** 2026-09-14T02:15:54-04:00 (first task commit)
- **Completed:** 2026-09-14T02:30:48-04:00 (final pyright fix commit)
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `installer/execute_screen.py` created with `ExecuteInputs`, `ExecuteScreen`, `InstallLogLine`, `InstallRunFinished`, `attributed_install`, `sanitize_log_line`.
- `UnifiedApp` pushes `ExecuteScreen` for a staged install instead of exiting the process (Task 1 tracer).
- `setup.py`'s `_execute_inputs` / `_run_interactive_wizard` seam split keeps the interactive path from calling the console `run_wizard` (Task 2).
- Pre-flight header is rendered in `on_mount` before `action_start` queues the worker, proving D-05.1 (Task 3).

## Deviations from plan

The cross-AI dispatch (`opencode run --model router-env/my-coding --auto`) completed all three tasks and their commits (`691a2cb`, `65ca659`, `312ecc4`) but hit its 3600s wall-clock timeout while polishing a single `pyright` diagnostic (`reportUnknownVariableType`) on an already-green test in `tests/test_setup.py`. Per the fallback protocol, this was finished directly in a follow-up commit (`fb7c39f`) — a `cast("list[object]", rc_paths)` in place of an untyped list comprehension. No test behavior changed; `make validate && make test` was independently re-run after the fix and passed (1956 passed, 1 skipped, 95.33% coverage).

## Verification

- `uv run pytest tests/test_execute_screen.py tests/test_wizard_app.py tests/test_setup.py tests/test_app.py tests/test_catalog_tui.py -q` — all green.
- `make validate` — passed (ruff, pyright, bandit, vulture, shellcheck).
- `make test` — 1956 passed, 1 skipped, 95.33% coverage (floor 90%).
- `git diff --stat` against the pre-plan tree lists exactly this plan's declared `files_modified`.
