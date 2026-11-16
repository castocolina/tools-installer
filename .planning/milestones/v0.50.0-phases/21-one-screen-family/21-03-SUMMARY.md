---
phase: 21-one-screen-family
plan: "03"
subsystem: tool-browser
tags: [selection, reload, cursor]
requires: []
provides:
  - "ToolBrowser.reload prunes ids that became unselectable"
  - "selected_ids filters on selectable"
  - "vanished cursor row lands on the nearest item row"
affects: [21-06]
key-files:
  modified:
    - installer/tool_browser.py
    - tests/test_tool_browser.py
requirements: [UI-08]
status: complete
actuals:
  tokens: 6000
  tasks: 2
  commits: 1
plan_head_before: 390f464298f06a30365de37e11510d5479afa09a
plan_head_after: e91fe928717b8940307a1f8947bffeddd9c6cadc
---

# Phase 21 Plan 03: Reload prune and nearest-row cursor Summary

`ToolBrowser.reload` silently drops still-listed ids that are no longer selectable, `selected_ids()` filters on `selectable`, and a vanished highlighted row moves the cursor to the nearest item row (`_first_selectable_row` became `_nearest_selectable_row(row=0)`).

## Commits

- e91fe92 feat(21-03): reload prunes unselectable picks and keeps a vanished cursor near its row

## TDD evidence

RED (before implementation, `-k "prune or unselectable or filters_on_selectable or nearest_surviving"`): 7 failed (nearest-row cursor, prune, selected_ids filter, accept, foreign ids/shared set, zero-one-many [1] and [2]); the silent-prune and `[0]` cases passed trivially because they pin contracts the change must not break.

GREEN: `tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_wizard_app.py -n auto` all pass.

## Verification

- `make validate` exit 0
- `make test` exit 0: 4931 passed, 4 skipped, coverage 96.03%
- `tests/test_tool_browser.py` collected count: 37 at start, 45 at end (floor 45 met)

## Deviations from Plan

**Task 2 folded into the Task 1 commit.** Both tasks' tests were written RED-first in one pass and committed with the implementation in a single commit rather than two. Task 2's tests (foreign ids, silent prune, zero-one-many) went RED/GREEN together with Task 1's. No behavior difference; the only loss is commit granularity.

## Known Stubs

None.

## Threat Flags

None. T-21-05 mitigated: `Accepted` cannot carry an unselectable id (`test_accept_never_carries_an_unselectable_id`).

## Self-Check: PASSED

e91fe92 is HEAD; both modified files committed.
