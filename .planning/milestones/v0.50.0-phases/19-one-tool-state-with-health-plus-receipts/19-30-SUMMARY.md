---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "30"
subsystem: ui
tags: [textual, catalog, tool-state, race, snapshot]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "one ToolState per tool published by the refresh pass, and the Status view grouping (19-27)"
provides:
  - "group_tools reads each tool's health once while building the Status grouping"
  - "CatalogScreen takes one state snapshot per rebuild and paints grouping and row cells from it"
affects: [19-one-tool-state-with-health-plus-receipts, catalog-status-view]

actuals:
  tokens: 1420
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "One read per tool per grouping: the Status branch of group_tools buckets from a dict built once"
    - "One snapshot per rebuild: CatalogScreen._painted is taken in _groups and read by _row_cells"

key-files:
  created: []
  modified:
    - installer/catalog_tui.py
    - tests/test_catalog_tui.py

key-decisions:
  - "Detail text, actions and previews keep reading live state; only the rebuild's grouping and row cells share the snapshot"
  - "The geometry test's one-argument _ver_cell/_owner_cell stubs take the optional painted argument the rebuild now passes"

patterns-established:
  - "A catalog rebuild paints grouping and cells from one snapshot, so a publication mid-rebuild cannot disagree with itself"

requirements-completed: [STATE-02, STATE-01]

coverage:
  - id: D1
    description: "The Status grouping reads each tool's health once, so a publication mid-grouping cannot place one tool in two groups"
    requirement: STATE-02
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_group_tools_reads_each_health_once"
        status: pass
    human_judgment: false
  - id: D2
    description: "One catalog rebuild paints grouping and row cells from one state snapshot, so a row's mark always agrees with its section"
    requirement: STATE-01
    verification:
      - kind: automated_ui
        ref: "tests/test_catalog_tui.py#test_status_view_survives_a_publication_mid_rebuild"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 30: Status View Race Summary

**The Status grouping reads each tool's health once, and every catalog rebuild paints its grouping and row cells from one state snapshot, so a publication mid-rebuild can neither duplicate a row nor paint a mark that disagrees with its section.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-16T21:53:21Z
- **Completed:** 2026-10-16T22:00:19Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `group_tools`' status branch reads each tool's health once and buckets from that map, closing the DuplicateKey crash (G7).
- `CatalogScreen` takes one state snapshot per rebuild in `_groups` and every row cell reads it, so a mark always agrees with its section.

## Task Commits

Each task was committed atomically (tests and code together; RED output recorded below, no red commit):

1. **Task 1: group_tools reads each tool's health once (G7)** - `532cab6` (fix)
2. **Task 2: one state snapshot per rebuild, shared by grouping and row cells (G7)** - `b9f09df` (fix)

**Plan metadata:** this commit (docs: plan summary)

## Files Created/Modified

- `installer/catalog_tui.py` - one health read per tool in the status branch; `CatalogScreen._painted` snapshot taken in `_groups` and read by `_row_cells`
- `tests/test_catalog_tui.py` - `test_group_tools_reads_each_health_once`, `test_status_view_survives_a_publication_mid_rebuild`; two geometry-test stubs widened

## TDD RED evidence

Task 1, `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "reads_each_health_once"` (exit 1), before the fix:

```
>       assert reads == {tool.id: 1 for tool in tools}
E       AssertionError: assert {'fd': 7, 'la...': 7, 'rg': 7} == {'fd': 1, 'la...': 1, 'rg': 1}
E         Differing items:
E         {'fd': 7} != {'fd': 1}
E         {'lazygit': 7} != {'lazygit': 1}
E         {'rg': 7} != {'rg': 1}
FAILED tests/test_catalog_tui.py::test_group_tools_reads_each_health_once
```

Each tool was read once per Health bucket (seven times). The flip half of the same test — first read pending, later reads OK — was reached only after the read count was fixed.

Task 2, `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "publication_mid_rebuild"` (exit 1), on the Task 1 tree:

```
>               assert glyph == section[:1], f"{key}: {glyph!r} under {section!r}"
E               AssertionError: rg: '✓' under '… checking'
E               assert '✓' == '…'
FAILED tests/test_catalog_tui.py::test_status_view_survives_a_publication_mid_rebuild
```

rg's row showed `✓` under the `… checking` section, exactly the disagreement the plan predicted.

## Verify-command results

- Task 1: `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "group or sort or reads_each_health_once"` → 12 passed. Shrink guard: tests/test_catalog_tui.py 4771 → 4799 lines, tests 179 → 180, trailing newline kept. Suppressions 487 → 487. `grep -c "healths\[t.id\] is health"` = 1.
- Task 2: `uv run pytest tests/test_catalog_tui.py -q --no-cov` → 181 passed. Shrink guard: 4799 → 4857 lines, tests 180 → 181, trailing newline kept. Suppressions 487 → 487. `grep -c "self._painted = {"` = 1, `grep -c "self._painted"` = 4.
- `make validate` exit 0 before each commit (ruff, pyright 0 errors, bandit, vulture, shellcheck).
- `make test` before Task 1's commit: 4564 passed, 4 skipped, coverage 95.99%. Before Task 2's commit: 4565 passed, 4 skipped, coverage 95.99%.
- Plan verification: `uv run pytest tests/test_catalog_tui.py tests/test_tool_browser.py tests/test_layout_80x20.py -n auto -q --no-cov` → 263 passed.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: no dependency change.
- `wc -l` / `git diff --stat` over the plan range `177d8ac..b9f09df`: installer/catalog_tui.py 889 → 911 (+52/−17 net in the range), tests/test_catalog_tui.py 4771 → 4857 (+90/−2). Both diffs are the intended hunks only.

## Decisions Made

- Detail text, the `u` action and the requires/recommends previews keep reading live state, as the plan says. Only the rebuild's grouping and its row cells share `_painted`.
- `test_owner_column_starts_inside_the_viewport_at_the_minimum_size` stubs `_ver_cell` and `_owner_cell` with one-argument lambdas. The rebuild now passes the snapshot, so those two stubs take an optional second argument. The existing one-argument production calls are unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Widened two geometry-test stubs to the new cell signature**
- **Found during:** Task 2 (one state snapshot per rebuild)
- **Issue:** `_row_cells` now passes the snapshot to `_ver_cell` and `_owner_cell`, and `test_owner_column_starts_inside_the_viewport_at_the_minimum_size` replaces both with one-argument lambdas, so the catalog file failed with `TypeError: ... takes 1 positional argument but 2 were given`.
- **Fix:** both lambdas take an optional second argument and ignore it. No new suppression; the existing `type: ignore[method-assign]` lines stayed.
- **Files modified:** tests/test_catalog_tui.py
- **Verification:** the catalog file passes (181 tests), including the geometry test and the new race test.
- **Committed in:** `b9f09df` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** the stub change is required for the new signature to be callable; no behavior change and no scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G7 is closed: no publication timing can duplicate a catalog row or paint a mark that disagrees with its section.
- The snapshot is per rebuild, so the next publication still repaints through the existing reload.
- Orchestrator note: the plan's `task-brief` script matches only markdown headings and found no task in this XML plan; the `<task>` blocks read in full were the briefs.

## Rulings I made

- Task 1: the brief extractor matches only markdown headings and this plan uses `<task>` XML, so the plan's task block read in full is the brief. Cost if wrong: none — the contract was read verbatim.

## Deferred minors

None.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
