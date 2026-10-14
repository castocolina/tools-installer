---
phase: 17-stop-the-bleeding
plan: "14"
subsystem: testing
tags: [pytest, race-test, threading, macos-ci, shell-test, prune-tmp]

requires:
  - phase: 17-stop-the-bleeding plan 01
    provides: green pyright so the wave-1 CI oracle could run tests on macOS
provides:
  - "deterministic dot-dot refusal test (works where /tmp is a symlink to /private/tmp)"
  - "unsynchronized-reader race test that is guaranteed to overlap writer and reader"
affects: [wave-2 plans, ci oracle re-run on PR #1]

actuals:
  tokens: 11600
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "reader-ready handshake + writer-run-until-observed, iteration-capped race-test pattern"

key-files:
  created: []
  modified:
    - tests/test_prune_tmp_linux_sh.py
    - tests/test_version_status.py

key-decisions:
  - "`/usr/..` chosen over `/tmp/..` because it canonicalizes to `/` on both Linux and macOS (`/tmp` -> `/private/tmp` on macOS); the script's broad-path guard canonicalizes internally, verified by hand"
  - "race test overlap is made structural (reader_ready Event, writer waits, writer loops until seen_record and seen_none and checked > 0, capped at 20_000 passes) instead of lucky"

patterns-established:
  - "reader-signals-first + writer-until-observed handshake: never start the writer before the reader is looping; bound by iteration cap, never wall-clock"

requirements-completed: [CI-01]

coverage:
  - id: D1
    description: "dot-dot refusal test proves refusal of / on both OSes via /usr/.."
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_prune_tmp_linux_sh.py#test_refuses_a_dotdot_spelling_of_the_root_directory"
        status: pass
    human_judgment: false
  - id: D2
    description: "unsynchronized-reader race test always overlaps the writer; 20/20 stress green"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 14: macOS test-defect fixes Summary

**Two macOS-only test defects fixed at the root — a symlink-blind `/tmp/..` spelling and a writer-before-reader race-test start — with no production change.**

## What was built

### Task 1 — dot-dot refusal test canonicalizes to / on both OSes (`8f85cb5`)

`tests/test_prune_tmp_linux_sh.py::test_refuses_a_dotdot_spelling_of_the_root_directory`
passed `--tmpdir /tmp/..`, which canonicalizes to `/private` on macOS (`/tmp` is a
symlink to `/private/tmp`), so the broad-path refusal never fired there. Replaced
with `/usr/..` (argument, expected stderr text, and an expanded docstring stating
why). Verified by hand first, with a scratch HOME, that the script's
`_prune_common_refuse_broad_path` canonicalizes `/usr/..` to `/` and refuses:
`error: refusing broad path /usr/..` (exit 1). Acceptance criteria: 0 hits for
`"/tmp/.."`, 3 for `/usr/..`.

### Task 2 — unsynchronized-reader race test always overlaps the writer (`789c168`)

`tests/test_version_status.py::test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record`
started the writer before the reader; on the slow macOS runner all 40 passes
finished before the reader looped once, leaving `seen_record` False. Now:
`reader_ready = threading.Event()` set by the reader on loop entry; the writer
asserts `reader_ready.wait(timeout=30)` before its first pass and the reader
thread is started first. The fixed 40 passes became a loop until
`seen_record and seen_none and checked > 0`, capped at `_MAX_PASSES = 20_000`,
keeping the `time.sleep(0)` GIL yields. `stop.set()` stays in the writer's
`finally`; the four final asserts (`errors == []`, `seen_record`, `seen_none`,
`checked > 0`) are unchanged verbatim. No skip/xfail/skipif anywhere.

## TDD RED evidence

Neither task was marked tdd="true"; both fix tests that were already failing on
the CI oracle (run 38653233506): the prune test failed on macOS only
(`assert 0 != 0`), and the race test failed there with
`assert seen_record, "the unsynchronized reader never overlapped a committed pass"`.
Both pass locally before and after the change (this host is Linux), so no local
RED run exists — the RED evidence is the CI oracle's macOS job.

## Verify results

- `uv run pytest tests/test_prune_tmp_linux_sh.py -q --no-cov` — 22 passed
- `uv run pytest tests/test_version_status.py -q --no-cov` — 44 passed
- Task 2 stress: **20/20** consecutive runs green under
  `uv run pytest tests/test_version_status.py -q --no-cov -n auto -p no:randomly`
- `make validate` — pass (both commits)
- `make validate && make test` — 3467 passed, 4 skipped, coverage 95.87% (gate 90%)

## Deviations from the plan

None.

## Issues for the orchestrator

- The plan's <verification> step remains: push HEAD to `ci/phase-17-wave1`
  (PR #1) and record the new run's two job conclusions in 17-01-SUMMARY
  `## CI oracle (wave 1)`. Local verification is complete; the macOS job is the
  only remaining proof surface for both fixes.
