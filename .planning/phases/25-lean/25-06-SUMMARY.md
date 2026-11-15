---
phase: 25-lean
plan: "06"
subsystem: installer
tags: [lean, run-log, richlog, textual, tdd]

# Dependency graph
requires:
  - phase: 25-lean (plan 25-03)
    provides: ExecuteScreen without the sensitive-action prompt; every post-install action takes (tool, platform)
provides:
  - "RunLog: the Execute run log is a RichLog bounded at 5,000 stored lines that counts what Textual trims"
  - "dropped_notice(count): '1 earlier line dropped' / 'N earlier lines dropped' (D-12 wording)"
  - "The #execute-log-dropped label directly above the log, hidden until the first drop"
  - "ExecuteScreen.write_log: the one write path for every #execute-log line (both install handlers)"
affects: [25-11 (also declares LEAN-04)]

# Actuals (#2632) — chars/4 over the realized diff of this plan
actuals:
  tokens: 3971
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RichLog subclass that reads Textual's trimmed-line counter (_start_line) and reports it from a write() override"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/test_execute_screen.py

key-decisions:
  - "The dropped count is RichLog's own _start_line, not a per-write tally: a multi-line or wrapped write stores several strips per call, and deferred writes are counted when replayed"
  - "The notice is a label directly above the log, not a line inside it: an in-log notice would need a full buffer rewrite or would break newest-line-last"
  - "Empty writes are not skipped: Textual stores \"\" as one stored line, so the bound holds after every write_log call"
  - "The label costs a row only after the first drop, so the 80x20 layout and every log-content test below 5,000 lines are unchanged"

requirements-completed: [LEAN-04]

# Metrics
duration: "not measured (plan-start timestamp was not recorded)"
completed: 2026-11-15
status: complete

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "The Execute run log keeps at most 5,000 stored lines (RunLog max_lines=5000)"
    requirement: "LEAN-04"
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_the_run_log_keeps_5000_lines_and_names_the_dropped_ones"
        status: pass
    human_judgment: false
  - id: D2
    description: "The dropped-lines notice wording: 1 line, N lines, and 1000 lines"
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_dropped_notice_wording"
        status: pass
    human_judgment: false
  - id: D3
    description: "An install log line past the bound refreshes the notice; the newest line stays last"
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_an_install_log_line_past_the_bound_updates_the_notice"
        status: pass
    human_judgment: false
  - id: D4
    description: "Writes Textual defers until the first resize refresh the notice when they are replayed"
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_writes_replayed_after_the_first_resize_update_the_notice"
        status: pass
    human_judgment: false
  - id: D5
    description: "Multi-line writes, empty writes at the bound and a near-full completion report count every stored line"
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_a_multi_line_write_counts_every_stored_line"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_an_empty_write_at_the_bound_still_trims"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_a_near_full_run_finished_report_updates_the_notice"
        status: pass
    human_judgment: false
  - id: D6
    description: "At 80x20 the notice sits directly above a log that stays visible with at least five rows"
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_the_80x20_running_layout_shows_the_notice_above_a_visible_log"
        status: pass
    human_judgment: false

# Plan-level measured commit range (#3968)
plan_head_before: a6d1af5930926f7970e5a9cef45e7ca31530732a
plan_head_after: 6b2511feadf7d78616f5bf387a960ee73b051d1f
---

# Phase 25: Lean, Plan 06: Bounded Execute run log Summary

**Execute run log bounded at 5,000 lines by a RichLog subclass, with a one-line "N earlier lines dropped" label directly above the log that appears at the first drop.**

## Performance

- **Duration:** not measured (the plan-start timestamp was not recorded)
- **Started:** not recorded
- **Completed:** 2026-11-15
- **Tasks:** 2 of 2
- **Files modified:** 2 (`installer/execute_screen.py`, `tests/test_execute_screen.py`)

## Accomplishments

- `RunLog(RichLog)` with `max_lines=5000`. Its `dropped` property is Textual's cumulative trimmed-line count, and its `write` override reports that count through a callback whenever it changes.
- `dropped_notice(count)` with the D-12 wording: singular for one line, plural otherwise.
- `ExecuteScreen.write_log(*lines)` is now the only path into `#execute-log`. All ten former direct writes (two in `on_install_log_line`, eight in `on_install_run_finished`) go through it, in the same order and with the same strings.
- The `#execute-log-dropped` label sits directly above the log. It is hidden until the first drop and then shows the notice. Below 5,000 lines nothing about the log changes.
- Eight tests cover the 5,000 / 5,001 / 6,000 boundaries, the wording, the end-to-end install path, replayed (deferred) writes, multi-line and empty writes at the bound, a near-full completion report, and the 80x20 layout.

## Task Commits

Each task was committed atomically:

1. **Task 1: the bounded log is fed only through write_log, and the label names every dropped line, replayed writes included** - `3f103448` (feat)
2. **Task 2: multi-line, empty and completion-report writes count every stored line; the 80x20 notice leaves the log visible** - `6b2511fe` (test)

**Plan metadata:** recorded in the docs commit that adds this file.

_Note: TDD ordering deviated from the test-then-feat pattern. See "TDD Gate Compliance" below._

## Files Created/Modified

- `installer/execute_screen.py` - `RUN_LOG_MAX_LINES`, `dropped_notice`, `RunLog` (`dropped` property, `on_dropped` callback, `write` override), `ExecuteScreen._show_dropped`, `ExecuteScreen.write_log`, the `#execute-log-dropped` label and its `-dropped` CSS rule
- `tests/test_execute_screen.py` - the eight tests named in the Coverage block; no existing assertion changed

## Decisions Made

- The counter is Textual's `_start_line` read through a subclass. A per-write tally would be wrong for multi-line and wrapped writes, and for deferred writes that Textual replays on first resize.
- The notice is a sibling label above the log, not a line inside it. Keeping it inside would need a full buffer rewrite on every write, or would put the notice last and break newest-line-last.
- Empty writes are not skipped. Textual stores `""` as one line, so the bound holds after every `write_log` call with no caveat. The test `test_an_empty_write_at_the_bound_still_trims` pins this.
- The label takes a row only after the first drop, so the existing 80x20 layout test is unaffected.

## Deviations from Plan

### Auto-fixed Issues

None - the implementation followed the plan's Interfaces, Task 1 action and Task 2 action. No code defect was found by the new tests, so no source change was made in Task 2.

### Process deviations (no code change)

**1. [Process - TDD evidence captured after GREEN] RED classifier record produced post hoc**
- **Found during:** TDD gate check after the Task 2 commit.
- **Issue:** The RED run in the live session (four failures, see below) was observed before the implementation was written, but the `check tdd-red-evidence` record was not produced then, and the classifier was not run before GREEN.
- **Fix:** The four target tests were re-run against the pre-plan module (`git show a6d1af59:installer/execute_screen.py`, swapped in for the RED run only), with JUnit output and run timestamps. The committed module was then restored with `git checkout -- installer/execute_screen.py` and verified byte-identical to the GREEN copy. The records were built inside the worktree because the classifier refuses paths outside the project.
- **Verification:** All four records returned `RED_EVIDENCE_OK` (format `junit`, 4 of 4 target tests failed). The temporary evidence folder was removed afterwards, so the tree is clean.
- **Committed in:** not committed (evidence only).

**Total deviations:** 0 code deviations; 1 process deviation (TDD evidence captured after GREEN) and the commit-order issue below.

## TDD Gate Compliance

Violations against the `tdd.md` commit pattern (the plan's binding rule forbade committing RED alone, so the test-first commit could not exist):

- **Missing RED-before-GREEN commit:** the four Task 1 tests and the implementation were committed together as `3f103448 feat(25-06): ...`. No `test(25-06): ...` commit precedes that `feat(25-06): ...` commit.
- **GREEN before RED in history:** the only `test(25-06): ...` commit is `6b2511fe`, Task 2's pinning tests. It follows the `feat` commit, so the git-ancestry check (#5275, "no GREEN commit follows a RED commit") reports `green_before_red`.
- **RED evidence:** the four Task 1 tests failed before the implementation (see the RED run below). The classifier verdict for each is `RED_EVIDENCE_OK`, but it was produced after GREEN (Process deviation 1).
- **Semantic assessment of RED:** each target fails at the first line that touches a planned name (`dropped_notice`, `RunLog`, `write_log`), with `AttributeError`. This is a missing-behaviour failure for the planned API, not an import, fixture or unrelated fault. It is weaker than an assertion-level failure, because the tests name the planned surface directly.

## RED run (Task 1, before the implementation)

```
FAILED tests/test_execute_screen.py::test_dropped_notice_wording - AttributeError: module 'installer.execute_screen' has no attribute 'dropped_notice'
FAILED tests/test_execute_screen.py::test_the_run_log_keeps_5000_lines_and_names_the_dropped_ones - AttributeError: module 'installer.execute_screen' has no attribute 'RunLog'
FAILED tests/test_execute_screen.py::test_an_install_log_line_past_the_bound_updates_the_notice - AttributeError: module 'installer.execute_screen' has no attribute 'RunLog'
FAILED tests/test_execute_screen.py::test_writes_replayed_after_the_first_resize_update_the_notice - AttributeError: module 'installer.execute_screen' has no attribute 'RunLog'
4 failed
```

## Gate results

- Task 1 gate (before commit): `make validate` exit 0; `make test` exit 0 with 7611 passed, 6 skipped, coverage 96.12%.
- Task 2 gate (before commit): the first `make validate` failed only on `ruff format --check` (`Would reformat: tests/test_execute_screen.py`). `ruff format` was applied to the new Task 2 block only. The re-run of `make validate` exit 0, and `make test` exit 0 with 7615 passed, 6 skipped, coverage 96.12%.
- pyright on `installer/execute_screen.py` and `tests/test_execute_screen.py`: 0 errors. No `noqa`, `type: ignore`, `pyright: ignore`, `nosec` or vulture whitelist entry was added (checked against the plan diff).

## Issues Encountered

- The codegraph index is attached to the main checkout, not this worktree. The code was read directly with the Read tool, and `codegraph explore` was used only for the blast-radius hint.
- The worktree had no `.venv`. `make install` created it inside the worktree, which is the normal per-worktree environment. Nothing on the host was mutated.
- The first Task 2 validate run failed on formatting, which is recorded under Gate results.

## Known Stubs

None.

## Threat Flags

None. The threat-register mitigations are implemented as planned: T-25-15 (bounded `RunLog`, pinned by the 5,000 / 6,000 test) and T-25-16 (the notice names the exact trimmed count, refreshed inside `write`, pinned by the replay, empty and completion tests). T-25-SC is accepted (no package change).

## Deferred Items

Per the plan's Review Dispositions Ledger, both are deliberately not changed:
- R2-12: Textual's pre-size write queue is unbounded. The log is shown when the run starts, so the queue lasts one layout pass. The replay test drives a 5,001-line burst through it.
- R2-13: `textual>=8` has no upper bound. `uv.lock` pins 8.2.7, and the boundary and replay tests fail if `_start_line` or the replay path moves.

## Requirements

- LEAN-04 is declared by this plan and by 25-11. `requirements.ready-ids` reports it as **blocked** (25-11 has no SUMMARY yet), so `requirements.mark-complete` was not run. LEAN-04 should be marked complete once 25-11 is summarized, or by the orchestrator.

## Net production change (plan scope)

`git diff --shortstat a6d1af59..HEAD -- installer`: 1 file changed, 92 insertions(+), 15 deletions(-). Net +77 production lines in this plan. This is a bounded-log addition, not a deletion, so the phase-level net count (R5 / D-09) is for the orchestrator.

## Next Phase Readiness

- `installer/execute_screen.py` is now the sole place that writes the run log. Plan 25-11 should not add a direct `#execute-log` write.
- Plan 25-11 also declares LEAN-04, so the shared-ID gate holds completion until it has a SUMMARY.

## Self-Check: PASSED

Verified after writing this file (see the commit listing below). Files exist on disk: `installer/execute_screen.py`, `tests/test_execute_screen.py`. Commits `3f103448` and `6b2511fe` are ancestors of HEAD, and HEAD is recorded in `plan_head_after`.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
