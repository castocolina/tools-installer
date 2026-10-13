---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 02
subsystem: installer-core
tags: [streaming, runner, popen, cancellation, wave-1]

requires:
  - phase: 13-01
    provides: Wave 0 worker-to-modal mechanism (unused by this plan; sequencing only)
provides:
  - StreamingRunner that emits attributed lines while the child is still running
  - STREAM_DETAIL_LINES-bounded CommandError.detail
  - run_installs(..., should_continue=...) weak cancel between tools
affects: ["13-04 execute worker StreamingRunner", "13-05 cancel keybind"]

actuals:
  tokens: 3760
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Popen line-streaming Runner with drain-then-wait finally (never signal the child)"
    - "Keyword-only should_continue appended after the last positional parameter"

key-files:
  created: []
  modified:
    - installer/run.py
    - installer/session.py
    - tests/test_run.py
    - tests/test_session.py

key-decisions:
  - "StreamingRunner.emit is a required constructor argument; _current() raises RuntimeError when no tool is set — D-05.2 has no None branch."
  - "finally drains proc.stdout to EOF then wait(); never terminate/kill/send_signal (DD-1 keeps child lifecycle out of this phase)."
  - "should_continue is keyword-only after catalog so the seven preexisting parameters stay POSITIONAL_OR_KEYWORD."
  - "Wave-1 engine-untouched gate used a narrowed BASE (phase 13 first production commit) because merge-base vs feat/tui-interaction-consistency includes ~1163 lines of pre-Phase-13 churn on engine/executors/download/apps/postinstall."

patterns-established:
  - "Streaming arrives through the existing Runner seam; engine and executors stay untouched."
  - "Weak cancel is 'not attempted' by list difference, not a new InstallStatus member."

requirements-completed: ["D-03", "D-05"]

coverage:
  - id: D1
    description: "A command's output reaches a caller line by line WHILE the child is still running, attributed to the tool being installed."
    requirement: D-03
    verification:
      - kind: unit
        ref: tests/test_run.py#test_streaming_runner_emits_incrementally_before_child_exits
        status: pass
      - kind: unit
        ref: tests/test_run.py#test_streaming_runner_emits_attributed_lines_without_newlines
        status: pass
    human_judgment: false
  - id: D2
    description: "An emit that raises does not wedge the runner: the child's pipe is drained to EOF before it is reaped."
    requirement: D-03
    verification:
      - kind: unit
        ref: tests/test_run.py#test_streaming_runner_reaps_child_when_emit_raises
        status: pass
    human_judgment: false
  - id: D3
    description: "A batch can be stopped between tools without killing an in-flight child; not-attempted ids are the input list minus returned outcomes."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_session.py#test_run_installs_should_continue_stops_between_tools
        status: pass
      - kind: unit
        ref: tests/test_session.py#test_run_installs_should_continue_is_checked_before_dependency_blocked
        status: pass
    human_judgment: false
  - id: D4
    description: "installer/engine.py and every executor are untouched; streaming arrived through the existing Runner seam."
    requirement: D-03
    verification:
      - kind: other
        ref: "git diff --stat 0fb4b10^..HEAD -- installer/engine.py installer/executors.py installer/download.py installer/apps.py installer/postinstall.py (empty)"
        status: pass
    human_judgment: false

duration: 14 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 02: StreamingRunner and between-tools cancel — Summary

**A Popen-based StreamingRunner emits each attributed line while the child still runs, drains then reaps on every path including a raising callback, and run_installs can stop queuing between tools via a keyword-only should_continue predicate — with zero engine or executor changes.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-09-14T04:55:10Z
- **Completed:** 2026-09-14T05:09:05Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `StreamingRunner` streams attributed lines from a live child (`python -u` + `flush=True` proves incremental delivery), raises the same `CommandError` shape as every other Runner, and drains then reaps when `emit` raises against a >256 KiB child.
- `run_installs(..., *, should_continue=...)` stops between tools, never fabricates `DEPENDENCY_FAILED` for tools that were never reached, and leaves the seven preexisting parameters positional.

## Task Commits

1. **Task 1: StreamingRunner** — `1633f28` (`feat(13-02): add StreamingRunner for live attributed child output`)
2. **Task 2: should_continue** — `a6f3f6c` (`feat(13-02): stop run_installs between tools via should_continue`)
3. **Plan metadata** — this SUMMARY plus STATE/ROADMAP.

## Files Created/Modified

- `installer/run.py` — `STREAM_DETAIL_LINES`, `StreamingRunner` (Popen, DEVNULL stdin, STDOUT-merged stderr, drain-then-wait finally).
- `tests/test_run.py` — incremental delivery, attribution, CommandError shape, missing-binary 127, stderr fold, bounded detail, `test_streaming_runner_reaps_child_when_emit_raises`.
- `installer/session.py` — keyword-only `should_continue` after `catalog`; break at the top of the tool loop.
- `tests/test_session.py` — signature kind pin, stop-between-tools, cancel-before-dependency-blocked, truncated summarize.

## Decisions Made

- `emit` is required and `_current()` raises; there is no attribution-free branch (D-05.2).
- The `finally` only reads remaining stdout to EOF and waits. It never signals the child and never closes the pipe out from under it.
- `should_continue` is appended after `catalog` behind a bare `*`. Inserting it before `catalog` would make `catalog` keyword-only or steal its positional slot.
- **Engine-untouched baseline narrowed.** `git merge-base HEAD feat/tui-interaction-consistency` is `3e3cdc8`, and the engine/executor diff from that point is the pre-Phase-13 ~1163-line baseline the plan warned about. Re-run with `BASE` at `0fb4b10^` (phase 13 first production commit): empty. No file under `installer/engine.py`, `executors.py`, `download.py`, `apps.py`, or `postinstall.py` was edited.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `uv run rtk pytest` collected zero tests (rtk's pytest proxy). Used `.venv/bin/pytest` for Task 1/2 verifies; `make test` uses `uv run pytest --cov` and passed.
- `make validate` pyright initially failed on `wrapping_popen(*args: object, **kwargs: object)` in the reap test. Tightened the wrapper to the production Popen signature; no `# type: ignore`.
- Bandit B101 on `assert proc.stdout is not None` would fail `make validate` (`--skip B404,B603,B310` only). Replaced with an `if stdout is not None` guard.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 13-03 (persisted link-mode settings). Plan 13-04 Task 1 is the first production caller of `StreamingRunner`. Plan 13-05 Task 2 binds the cancel key to `should_continue`. Plan 13-07 Task 2 re-asserts the engine-untouched gate over the whole phase and the rule-5 adoption of these Wave-1 symbols.

## Self-Check: PASSED

- `grep -n "class StreamingRunner" installer/run.py` prints one line; `DEVNULL` and `stderr=subprocess.STDOUT` are present; `finally:` drains then `wait()`; `grep -v '^\s*#' installer/run.py | grep -cE 'proc\.(terminate|kill|send_signal)'` is 0.
- `should_continue` occurs 3 times in `installer/session.py`; no `InstallStatus.CANCELLED`; `inspect.signature` prints `SIG-OK`.
- `uv run vulture` exits 0; `git diff -- pyproject.toml` empty; `min_confidence` still 80.
- `make validate && make test` green: 1915 passed, 1 skipped, 95.36% coverage.

---
*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Completed: 2026-09-14*
