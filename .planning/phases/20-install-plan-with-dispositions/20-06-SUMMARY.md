---
phase: 20-install-plan-with-dispositions
plan: "06"
subsystem: ui
tags: [rich, plan-rendering, tui, sanitization]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: PlanRow, Disposition, WORDS, review_counts
provides:
  - Shared plan renderer for TUI/headless output with grouping, marks, folding, and sanitization
  - Shared Health glyph/style table in version_status
  - Catalog consumes the shared glyph table directly
affects: [20-09, 20-10, 20-14]

# Actuals (#2632)
actuals:
  tokens: 1040
  tasks: 3
  commits: 1

# Tech tracking
tech-stack:
  added: []
  patterns: [Rich Text composition for data, textwrap-based hanging folds, shared Health presentation table]

key-files:
  created: []
  modified: [installer/render.py, installer/version_status.py, installer/catalog_tui.py, tests/test_render.py]

key-decisions:
  - "Used textwrap.wrap for space folding and long-word breaking, reusing the standard-library behavior identified in the reuse audit."
  - "Moved glyph/style data into HEALTH_MARKS and replaced all catalog alias references directly."
  - "Task start helpers did not recognize XML task blocks; executed tasks in order and committed the combined, fully verified change once."

patterns-established:
  - "Render untrusted plan text as Rich Text with markup disabled and sanitize control characters before display."
  - "Plan outcome and health presentation draws words and marks from their canonical tables."

requirements-completed: [PLAN-01, PLAN-04]
coverage:
  - id: D1
    description: "Plan rows render with shared health marks, disposition words, reasons, optional reinstall hints, grouped dependencies, configuration steps, and bounded folded text."
    requirement: PLAN-01
    verification:
      - kind: unit
        ref: tests/test_render.py#test_render_plan_row_anatomy_fits_78_cells_with_a_24_char_id
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_plan_groups_dragged_rows_under_their_first_requester
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_plan_folds_a_400_char_reason_and_twelve_steps_within_width
        status: pass
  - id: D2
    description: "Probe-derived reasons and step text render literally and contain no terminal escape controls."
    requirement: PLAN-04
    verification:
      - kind: unit
        ref: tests/test_render.py#test_render_plan_renders_markup_and_escapes_in_a_reason_literally
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_plan_sanitizes_step_text
        status: pass
  - id: D3
    description: "Catalog health glyphs and styles share the canonical Health table."
    requirement: PLAN-01
    verification:
      - kind: unit
        ref: tests/test_render.py#test_health_marks_is_the_catalog_glyph_table
        status: pass
human_judgment: false

duration: 4min
completed: 2026-10-17
status: complete
---

# Phase 20: Install plan with dispositions — Plan 06 Summary

A shared `render_plan` now presents plan dispositions consistently and safely across terminal output, with grouped dependencies and bounded, sanitized detail text.

## Performance

- **Duration:** approximately 4 minutes
- **Started:** 2026-10-17
- **Completed:** 2026-10-17
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added plan row builders and the `render_plan` console entry point, sourcing all row marks and disposition words from shared tables.
- Grouped dragged dependencies under requesters; rendered plan counts, RECONFIGURE steps, hints, and hanging-folded reasons.
- Moved the health glyph/style map to `installer.version_status.HEALTH_MARKS`; catalog code now reads the canonical table directly.
- Added tests for each disposition on three tiers, row-width budgets, grouping, folding, step rendering, and untrusted markup/control text.

## Task Commits

Tasks were performed in the specified order. Because the plan's XML `<task>` syntax was not recognized by the installed task-brief extractor (which requires Markdown `## Task N` headings), the task changes are in one consolidated commit:

1. **Task 1: one plan row renders mark, id, word and reason within 78 cells; the glyph table moves** - `5b0eba1` (feat)
2. **Task 2: grouping under the requester, the head line, steps continuation, folding** - `5b0eba1` (feat)
3. **Task 3: probe-derived text is data, never markup** - `5b0eba1` (test/feat)

## Files Created/Modified
- `installer/render.py` - Shared row composition, text folding, grouping, plan head, and console rendering.
- `installer/version_status.py` - Canonical `HEALTH_MARKS` table.
- `installer/catalog_tui.py` - Uses `HEALTH_MARKS` in place of the local duplicate table.
- `tests/test_render.py` - Renderer, grouping, width, disposition/style, and sanitization tests.

## Decisions Made
- Applied reuse finding 06-1: standard-library `textwrap.wrap` handles spaces and long-word splitting within a hanging-indent routine.
- Applied reuse finding 06-2: all catalog call sites use `HEALTH_MARKS` directly; no redundant alias remains.
- Preserved the orchestrator-owned `.planning/config.json` modification and left it unstaged.

## Deviations from Plan

### Auto-fixed Issues

**1. Task helper incompatibility**
- **Found during:** Task 1 startup.
- **Issue:** The task-start/task-brief scripts searched for Markdown task headings, while this plan stores tasks as XML `<task>` blocks; no task brief could be generated.
- **Fix:** Read each task block directly from the plan, executed tasks sequentially, and kept all task scope in one commit.
- **Files modified:** None beyond planned files.
- **Verification:** Task-focused tests and full validation/test suite passed.
- **Committed in:** `5b0eba1`.

**2. Health glyph alias removed**
- **Found during:** Task 1, applying reuse finding 06-2.
- **Issue:** Plan context proposed retaining `_HEALTH_CELL` as a compatibility alias, but the reuse audit recommended no alias and found no tests/users requiring it.
- **Fix:** Replaced the three catalog references with `HEALTH_MARKS` and deleted the local table.
- **Files modified:** `installer/catalog_tui.py`.
- **Verification:** `grep -c "_HEALTH_CELL" installer/catalog_tui.py` returned 0; catalog tests passed.
- **Committed in:** `5b0eba1`.

**Total deviations:** 2 auto-fixed (one execution-helper mismatch, one reuse adjustment).
**Impact on plan:** Functional scope and planned public interfaces were retained; only commit granularity and the redundant alias differed.

## Issues Encountered
- The first style assertion compared Rich style names (`green`) against their ANSI-parsed equivalent names (`color(2)`). The assertion was adjusted to verify the actual emitted ANSI SGR sequence for the table-defined style.
- Console output lines include a width-100 title by default. Width tests appropriately assert the row budget with an explicit width, as specified.

## User Setup Required

None - no external service configuration required.

## Verification

- Task 1 targeted tests: `uv run pytest tests/test_render.py -q --no-cov -k "plan_row or words_and_marks or health_marks"` — 27 passed.
- Task 2 targeted tests: `uv run pytest tests/test_render.py -q --no-cov -k "groups or head or chain or blocked_requester or reconfigure or folds"` — 11 passed.
- Task 3 targeted tests: `uv run pytest tests/test_render.py -q --no-cov -k "literally or sanitizes_step"` — 2 passed.
- Catalog/render integration: `uv run pytest tests/test_render.py tests/test_catalog_tui.py -n auto -q --no-cov` — passed.
- `make validate && make test` — passed; 4,769 passed, 4 skipped, coverage 95.99%.
- Suppression no-growth gate and `git diff --check` — passed.
- No real installs or host mutations performed.

## Next Phase Readiness

The renderer exports `id_width`, `display_order`, `fold_reason`, `plan_row_text`, `plan_head`, and `render_plan` for plans 20-09/20-10 to reuse. Health mark data is available from `installer.version_status`.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-17*
