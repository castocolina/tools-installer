---
phase: 17-stop-the-bleeding
plan: "15"
subsystem: testing
tags: [pytest, race-test, threading, macos-ci, gil]

requires:
  - phase: 17-stop-the-bleeding plan 14
    provides: reader_ready handshake + iteration-capped race test that still failed on macos-latest
provides:
  - "race test whose overlap is guaranteed by a writer-side wait, deterministic on macOS and Linux"
affects: [wave-1 CI oracle re-run, 17-01-SUMMARY CI oracle record]

actuals:
  tokens: 8400
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "writer-waits-for-reader window pattern: shared iteration counter, spin until reads >= reads+2, iteration-capped, never wall-clock"

key-files:
  created: []
  modified:
    - tests/test_version_status.py

key-decisions:
  - "Only a writer-side wait can fix the macOS failure: on macOS time.sleep(0) yields the GIL back to the same thread, so no pass count can schedule the reader inside the committed/invalidated windows"
  - "The waits bracket only the windows (after commit, after invalidate); the reads themselves stay unsynchronized, so the superseded-record race the test exists to catch is still exercised"
  - "Pass cap lowered 20_000 -> 200: with windows waited for, passes no longer need to be numerous"

patterns-established:
  - "_let_reader_run(): spin time.sleep(0) until the reader's shared iteration counter advances by 2, capped at 200_000 iterations -- overlap by construction, bounded by iteration count, never wall-clock"

requirements-completed: [CI-01]

coverage:
  - id: D1
    description: "unsynchronized-reader race test overlaps writer and reader by construction on every OS"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 15: race test waits for the reader inside each window Summary

**The unsynchronized-reader race test now guarantees overlap by construction: the writer waits for the reader inside the committed and invalidated windows via a shared iteration counter — the macOS GIL-yield blind spot is closed with no production change.**

## What was built

### Task 1 — writer waits for the reader inside each window (`ebbc454`)

`tests/test_version_status.py::test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record`
(17-14, run 38654588972) was still `seen_record` False on macos-latest: the
committed window is the few bytecodes between `refresh()` returning and
`invalidate()`, and on macOS `time.sleep(0)` hands the GIL back to the same
thread, so the reader was never scheduled there regardless of pass count.
Changes, exactly per plan:

- Reader counts every completed loop iteration in a shared `reads` counter,
  incremented in a `try/finally` around the loop body so all `continue` paths
  count.
- New in-test helper `_let_reader_run()`: records `target = reads + 2`, spins
  `time.sleep(0)` until `reads >= target` or a 200_000-iteration cap is hit;
  never a wall-clock sleep. Two iterations guarantee at least one whole
  `ownership_of` call starts and ends inside the current window.
- Writer calls `_let_reader_run()` after `committed_at[...] = record` (inside
  the committed window) and after `invalidate(...)` (inside the gap). The
  early break (`seen_record and seen_none and checked > 0`) and
  `reader_ready` are kept; `_MAX_PASSES` lowered 20_000 → 200.
- The four final asserts (`errors == []`, `seen_record`, `seen_none`,
  `checked > 0`) are unchanged verbatim; docstring updated to state the
  windows are waited for and the reads themselves are not fenced. No
  skip/xfail/skipif anywhere; no `installer/` change (`git diff --stat` of the
  commit lists only `tests/test_version_status.py`).

## TDD RED evidence

The task is not marked `tdd="true"` and the failure only reproduces on the
macOS runner (20/20 green on Linux before the change). The RED evidence is the
CI oracle's macos-latest job of run 38654588972:
`assert seen_record, "the unsynchronized reader never overlapped a committed pass"`.
No local RED run exists; on this Linux host the test passed before and after.

## Verify results

- `uv run pytest tests/test_version_status.py -q --no-cov` — 44 passed
- Acceptance: `grep -c '_let_reader_run' tests/test_version_status.py` — 4 (≥ 3)
- Stress, parallel: **20/20** consecutive runs green
  (`uv run pytest tests/test_version_status.py -q --no-cov -n auto`)
- Stress, single CPU: **20/20** consecutive runs green
  (`taskset -c 0 uv run pytest tests/test_version_status.py -q --no-cov -k unsynchronized_reader`)
- `make validate` — pass
- `make validate && make test` — 3467 passed, 4 skipped, coverage 95.87% (gate 90%)

## Deviations from the plan

None.

## Issues for the orchestrator

- The plan's <verification> step remains: push HEAD to `ci/phase-17-wave1`
  (PR #1) and record the new run's two job conclusions in 17-01-SUMMARY
  `## CI oracle (wave 1)`. The macOS job is the only proof surface this host
  cannot provide.
