---
phase: 17-stop-the-bleeding
plan: "03"
subsystem: infra
tags: [subprocess, start-new-session, streaming-runner, tui-safety, posix-sessions]

# Dependency graph
requires:
  - phase: 17-stop-the-bleeding
    provides: "StreamingRunner with stdin=subprocess.DEVNULL (pre-existing) and the runner module's test doubles"
provides:
  - "Install children (StreamingRunner) run in their own session: start_new_session=True in popen_with_env"
  - "Update children (run_output/run_captured) run in their own session with closed stdin: stdin=subprocess.DEVNULL, start_new_session=True"
  - "Session-discriminating (getsid) and /dev/tty fail-fast tests for both runners"
affects: [22-life-support, sudo-handoff, execute_screen]

# Actuals
actuals:
  tokens: 8500
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "signal.alarm(N) in child scripts as a hang guard paired with a wall-clock elapsed assertion"
    - "os.getsid(0) == os.getpid() child script as the discriminating new-session check"

key-files:
  created: []
  modified:
    - installer/run.py
    - tests/test_run.py

key-decisions:
  - "One keyword per runner (D-10): start_new_session=True in StreamingRunner.popen_with_env; stdin=subprocess.DEVNULL + start_new_session=True in run_output"
  - "run_command untouched — the console path keeps the terminal for interactive prompts"
  - "A child in its own session no longer receives the terminal's SIGINT/SIGHUP (accepted: Textual holds the terminal in raw mode, so Ctrl+C never reached children as a signal anyway; T-17-07)"

patterns-established:
  - "getsid child as session discriminator: exit 0 only when the child is its own session leader"
  - "alarm-guarded /dev/tty reader paired with an elapsed-time assertion: proves fail-fast, catches regressions to a hang"

requirements-completed: [SAFE-07]

coverage:
  - id: D1
    description: "StreamingRunner install children start in their own session (start_new_session=True)"
    requirement: SAFE-07
    verification:
      - kind: unit
        ref: "tests/test_run.py#test_streaming_runner_child_runs_in_its_own_session"
        status: pass
    human_judgment: false
  - id: D2
    description: "A fake /dev/tty reader exits non-zero within 5 s under StreamingRunner"
    requirement: SAFE-07
    verification:
      - kind: unit
        ref: "tests/test_run.py#test_streaming_runner_tty_reader_fails_fast"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_output/run_captured update children run in their own session with stdin=DEVNULL"
    requirement: SAFE-07
    verification:
      - kind: unit
        ref: "tests/test_run.py#test_run_captured_child_runs_in_its_own_session"
        status: pass
      - kind: unit
        ref: "tests/test_run.py#test_run_output_unbounded_by_default"
        status: pass
    human_judgment: false
  - id: D4
    description: "A fake /dev/tty reader exits non-zero within 5 s under run_captured"
    requirement: SAFE-07
    verification:
      - kind: unit
        ref: "tests/test_run.py#test_run_captured_tty_reader_fails_fast"
        status: pass
    human_judgment: false

# Metrics
duration: 14min
completed: 2026-10-14
status: complete
---

# Phase 17: Plan 03 Summary

**Install and update children now run detached in their own session (start_new_session=True) with closed stdin, so a vendor script that prompts on /dev/tty fails fast instead of hanging the TUI (SAFE-07, D-10).**

## Performance

- **Duration:** 14 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `StreamingRunner.popen_with_env` passes `start_new_session=True` (stdin was already DEVNULL): install children get no controlling terminal.
- `run_output` (hence `run_captured`, the update runner at setup.py:1121 and update.py:406) passes `stdin=subprocess.DEVNULL, start_new_session=True`: update children cannot grab the terminal either; all other `run_output` callers read no stdin (verified against the caller list in the plan context).
- `run_command`/`run_interactive_command` untouched — the console path keeps the terminal for interactive prompts (verified: zero `start_new_session` occurrences in that range).

## Task Commits

1. **Task 1: install children start in their own session — StreamingRunner (D-10)** - `270f335` (feat)
2. **Task 2: update children too — run_output/run_captured get closed stdin and a new session** - `ce02282` (feat)

## TDD RED evidence

Task 1 (before the fix, the child shared the installer's session, so `getsid(0) != getpid()` → exit 3):

```
E installer.run.CommandError: command failed (3): ...python3 -c import os, sys;
  sys.exit(0 if os.getsid(0) == os.getpid() else 3)
FAILED tests/test_run.py::test_streaming_runner_child_runs_in_its_own_session
```

Task 2 (same discriminator, now via `run_captured`):

```
E installer.run.CommandError: command failed (3): ...python3 -c import os, sys;
  sys.exit(0 if os.getsid(0) == os.getpid() else 3)
FAILED tests/test_run.py::test_run_captured_child_runs_in_its_own_session
FAILED tests/test_run.py::test_run_output_unbounded_by_default - TypeError (fake_run signature)
```

## Verify-command results

- `uv run pytest tests/test_run.py -q --no-cov -k "own_session or tty_reader_fails_fast or streaming_runner"` — 21 passed
- `uv run pytest tests/test_run.py -q --no-cov` — 48 passed
- `uv run pytest tests/test_daemon.py tests/test_systemd_daemon.py tests/test_policy.py tests/test_pnpm_globals.py tests/test_versions.py tests/test_update.py -q --no-cov` — 97 passed
- `make validate` — passed (both commits)
- `make test` — 3477 passed, 4 skipped; coverage 95.87% (gate 90%)

## Known limitation until Phase 22

The registry's `sudo dnf`/`sudo apt-get`/`sudo pacman` methods (installer/executors.py:371-379) run under StreamingRunner in the TUI. With no controlling terminal, sudo cannot prompt for a password, so those methods now fail fast (CommandError, the ladder falls through) instead of hanging on a hidden password prompt. Phase 22 (LIFE-02, RUN-LEDGER sudo row) replaces them with a zero-sudo native handoff. The builders are deliberately unchanged in this plan.

Also accepted (T-17-07): children in their own session no longer receive the terminal's SIGINT/SIGHUP — Textual holds the terminal in raw mode, so Ctrl+C never reached children as a signal anyway; app-level cancel is unchanged.

## Files Created/Modified
- `installer/run.py` — `start_new_session=True` in `StreamingRunner.popen_with_env`; `stdin=subprocess.DEVNULL, start_new_session=True` in `run_output` (with rationale comments)
- `tests/test_run.py` — `_PopenKwargs.start_new_session` (docstring "all six" → "all seven"); `wrapping_popen` double updated; new tests `test_streaming_runner_child_runs_in_its_own_session`, `test_streaming_runner_tty_reader_fails_fast`, `test_run_captured_child_runs_in_its_own_session`, `test_run_captured_tty_reader_fails_fast`; `test_run_output_unbounded_by_default` extended to assert `stdin`/`start_new_session`

## Decisions Made
- Followed the plan as specified; no scope or design changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [plan action line] Existing Popen double needed the new keyword**
- **Found during:** Task 1 verification
- **Issue:** `test_streaming_runner_reaps_child_when_emit_raises`'s `wrapping_popen` has a fixed keyword list and broke once `start_new_session=True` was added ("all six" TypedDict contract working as designed)
- **Fix:** Added `start_new_session: bool = False` to the double and forwarded it to the real `Popen`
- **Files modified:** tests/test_run.py
- **Verification:** full task-1 verify command green
- **Committed in:** `270f335` (part of task commit)

---

**Total deviations:** 1 auto-fixed (signature maintenance on an existing test double, anticipated by the plan's action text)
**Impact on plan:** None — no scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- H7 closed for both runners; 17-05's CODEX_NON_INTERACTIVE registry change is independent and unblocked.
- Phase 22 (LIFE-02) owns the sudo handoff noted above.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
