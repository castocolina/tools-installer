---
phase: 20-install-plan-with-dispositions
plan: "27"
subsystem: ui
tags: [python, textual, rich, install-plan, reporting, tui]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: RowOutcome, render_run_report, the finished-row renderer, the execute screen review
provides:
  - outcome_mark dims finished rows the run did not change; done stays green, failures stay red
  - One failure vocabulary from row to report to log (✖ mark, single dependency-failure statement, no second not-attempted line)
  - _paint_review owns the review cursor with a row-1 fallback across every repaint
  - The running keys line is pinned verbatim by a test
affects: [install-plan, execute-screen, reporting, verify-work]
actuals:
  tokens: 2500
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: [dim-for-unchanged finished rows, single-owner cursor persistence, verbatim UI copy pinned by test]
key-files:
  created: [.planning/phases/20-install-plan-with-dispositions/20-27-SUMMARY.md]
  modified: [installer/render.py, installer/execute_screen.py, tests/test_render.py, tests/test_execute_screen.py, tests/test_app.py]
key-decisions:
  - "Dim every finished result the run did not change (skipped, blocked, manual, dependency_failed, not_attempted), not only skipped, so a reinstall of an OK tool that ends dependency_failed or not_attempted shows no green check."
  - "Delete render_skipped instead of rewording it: render_run_summary already prints dependency failed — {ids} for every such outcome in the same report, so any second line states the fact twice."
  - "_paint_review captures and restores the highlighted option id so on_resize and action_toggle_reinstall need no restore code; the fallback is row 1, which also makes the review open with a usable cursor (r works at once)."
patterns-established:
  - "One owner per mutable UI state: whoever rebuilds a widget also restores its selection."
  - "Verbatim user-facing copy is pinned by an exact-equality test, proven to bite by a one-character drift probe."
requirements-completed: [PLAN-04, PLAN-06]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "A finished row the run did not change renders its plan-time health glyph dimmed; done stays green ✓ and failed/mismatch/crashed stay red ✖."
    requirement: "PLAN-04"
    verification:
      - kind: unit
        ref: "tests/test_render.py#test_a_finished_mark_dims_a_row_the_run_did_not_change"
        status: pass
    human_judgment: false
  - id: D2
    description: "Failure details use the run failure mark ✖ (U+2716), not U+2717."
    requirement: "PLAN-06"
    verification:
      - kind: unit
        ref: "tests/test_render.py#test_failure_details_use_the_run_failure_mark"
        status: pass
    human_judgment: false
  - id: D3
    description: "The end-of-run report states a dependency failure exactly once and the TUI log has no second capitalised not-attempted line."
    requirement: "PLAN-06"
    verification:
      - kind: unit
        ref: "tests/test_render.py#test_the_run_report_states_a_dependency_failure_once"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_cancel_mid_run_lets_the_in_flight_tool_finish"
        status: pass
    human_judgment: false
  - id: D4
    description: "The review opens with the cursor on row 1 so r works at once, and every repaint (reinstall toggle, resize, published state) keeps the cursor on the same tool id or falls back to row 1."
    requirement: "PLAN-04"
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_the_review_opens_with_the_first_row_highlighted_so_r_works_at_once"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_a_published_state_keeps_the_cursor_on_the_same_tool"
        status: pass
    human_judgment: false
  - id: D5
    description: "While an install runs, the keys line is exactly 'c stop after this tool · ctrl+c aborts and can leave a tool half-installed'."
    requirement: "PLAN-04"
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_the_running_keys_line_is_the_contract_copy"
        status: pass
    human_judgment: false

# Metrics
duration: 35min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 27 Summary

**Finished rows the run did not change now render dimmed, the end-of-run report speaks one failure vocabulary, and the review cursor survives every repaint with the running keys copy pinned.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2
- **Files modified:** 5 implementation/test files, plus this summary.

## Accomplishments

- Task 1 — `outcome_mark` dims the plan-time health glyph for `skipped`, `blocked`, `manual`, `dependency_failed`, and `not_attempted` while `done` stays green and the failure results stay red; failure details use the run failure mark (U+2716); `render_skipped` is deleted with its second "skipped — dependency failed" line, and the TUI log's capitalised not-attempted line is gone. Commit: `4ca29bc` (`fix(20-27): a finished run states each fact once, with an unchanged row dimmed`).
- Task 2 — `_paint_review` owns cursor persistence: it restores the highlighted tool id across every repaint and falls back to row 1, so the review opens with a usable cursor (`r` works at once); the redundant restores in `on_resize` and `action_toggle_reinstall` are deleted, and the running keys line is pinned verbatim. Commit: `3521604` (`fix(20-27): the review opens on row 1 and keeps the cursor on its tool`).

## TDD evidence

- **Task 1 RED:** `uv run pytest tests/test_render.py -q --no-cov -n 0 -k "finished_mark or failure_details_use or dependency_failure_once"` — `..FFFFFFF`: the five unchanged results returned `('✓', 'green')` instead of `('✓', 'dim')`, the failure details used U+2717 instead of U+2716, and the report stated the dependency failure twice. GREEN: `uv run pytest tests/test_render.py tests/test_execute_screen.py tests/test_app.py -q --no-cov -n auto` — passed (380 tests).
- **Task 2 RED:** `uv run pytest tests/test_execute_screen.py -q --no-cov -n 0 -k "first_row_highlighted or keeps_the_cursor"` — `FF.`: `options.highlighted` was `None` at open (so `r` was a no-op), and publishing a state moved the cursor from `rg` to `fd`. The keys-line pin was proven to bite by changing one character of `_KEYS_RUNNING` locally — the exact-equality assertion failed — then the constant was restored before commit. GREEN: full suite below.

## Collected test counts

| Test file | Start | End |
|---|---:|---:|
| `tests/test_render.py` | 113 | 118 |
| `tests/test_execute_screen.py` | 131 | 134 |
| `tests/test_app.py` | 136 | 136 |

Counts used the plan's `--collect-only`/`awk` method. test_render gained 5 net (+9 new items, −4 deleted `render_skipped` tests, matching the acceptance criteria); test_execute_screen gained 3 net (three new tests, two changed in place, one transient keys assertion folded into the pin).

## Verification

- Task 1 tree gates: `uv run pytest tests/test_render.py tests/test_execute_screen.py tests/test_app.py -q --no-cov -n auto` — passed; `make validate` via pre-commit — passed.
- Task 2 gates (final tree): `make test` — **4908 passed, 4 skipped, 96.00% coverage (90% required)**; `make validate` via pre-commit — passed.
- Acceptance greps: `render_skipped` 0 references in all five files; `✗` 0 / `✖` 2 in `installer/render.py`; `Not attempted: ` 0 in `installer/execute_screen.py`; `options.highlighted = ` assignments 2 (`_paint_review`, in-flight row); keys copy 1; `skipped — dependency failed` only as `not in` assertions (0 positive occurrences, ASCII variant 0).
- Suppression comparison: none added (pass-through check green).
- `uv run python -c "import installer.render as r; assert not hasattr(r, 'render_skipped')"` — passed.

## Deviations from Plan

None in behaviour or scope. Two mechanical notes:

1. The two tasks' file split was preserved per the plan: Task 1 owns the `execute_screen.py` not-attempted-line deletion and the changed `test_cancel_mid_run…` / `test_post_run_log…` assertions; Task 2 owns the cursor work. An initial commit split was redone so each commit's exact tree passes the gates (the first attempt would have left `tests/test_app.py` failing at the Task 1 commit).
2. `test_a_stopped_run_names_its_not_attempted_rows_only_in_the_rows` from the plan's behaviour list was written as strengthened assertions inside the existing `test_cancel_mid_run_lets_the_in_flight_tool_finish` (per the plan's context block, which said that test "stays unchanged and green" — the plan text is contradictory; the strengthened version asserts the single `bat` line and the absence of the capitalised label, which is the required RED behaviour). The transient keys-line assertion added to the cancel test was removed once the dedicated pin test landed, keeping the key copy at exactly one pinned occurrence.

## Issues Encountered

- Textual types `OptionList.highlighted` as `int` (not `Optional[int]`), so the restore logic computes the target index in one assignment (`highlighted_index if highlighted_index is not None else 0`) instead of an `is not None` re-check that pyright flagged; the assignment count acceptance grep (2) still passes.
- Pyright also required the published-state test's wait loop to key on the row prompt text (`_plan_prompts(screen)[1].startswith("○ fd")`) rather than the highlighted index.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- J10 gap-closure for wave 5 is complete: marks, report vocabulary, cursor contract, and keys copy are all pinned by tests.
- Remaining known follow-ups, if any, belong to the orchestrator's wave bookkeeping; nothing in this plan blocks later phases.

---
*Phase: 20-install-plan-with-dispositions*
*Plan: 27*
*Completed: 2026-10-18*
