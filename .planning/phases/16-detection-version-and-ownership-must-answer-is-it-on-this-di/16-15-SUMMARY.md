---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 15
subsystem: ui
tags: [catalog, ownership, off-policy, broken, textual]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: off_policy, also_installed_note, active_path_note, declared_manager_label, and ManagerOwnership.broken
provides:
  - Off-policy Owner cell tag and never-silent current u
  - Dual-owner and unknown-path detail text, with markup-escaped filesystem paths
  - Broken Inst marker, legend entry, detail sentence, and u repair hint
affects: [16-16]

actuals:
  tokens: 5835
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - Catalog row text for off-policy, dual-owner, and unknown-path is read from ownership.py helpers, not re-derived
    - A filesystem path interpolated into detail markup is escaped per segment, never as the whole joined string

key-files:
  created: []
  modified:
    - installer/catalog_tui.py
    - tests/test_catalog_tui.py

key-decisions:
  - "The broken Inst check lives in _inst_cell, where the check/circle ternary moved in plan 16-12. The skill-pack branch is unchanged."
  - "An off-policy sentence is omitted when declared_manager_label or owner_label is None, so the status line never says via None."

patterns-established:
  - "u always sets a status line. A current tool says it is already current. A broken row says how to repair it and does not call UpdateService.begin."

requirements-completed: [D-02, D-03, D-05, D-06, D-08, D-18]

coverage:
  - id: D1
    description: "An off-policy row shows Homebrew ≠ policy in the Owner cell, with the tag dim, and the detail names the catalog policy manager."
    requirement: D-02
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_off_policy_owner_cell_and_detail_name_the_declared_manager"
        status: pass
    human_judgment: false
  - id: D2
    description: "u on a current tool always answers. An off-policy current tool names the real owner and says migration is not available yet. UpdateService.begin is not called."
    requirement: D-05
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_update_on_current_off_policy_tool_explains_and_does_not_begin"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_update_on_current_tool_says_already_current"
        status: pass
    human_judgment: false
  - id: D3
    description: "A shadowed copy's detail says also installed via the other manager, with the live path when known."
    requirement: D-06
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_detail_names_also_installed_via_the_shadowed_manager"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_detail_line_names_competing_manager_and_active_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unknown owner shows where the active binary resolves, in the detail pane and on the u refusal. A bracket in that path does not restyle the detail."
    requirement: D-08
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_unknown_detail_names_the_active_binary"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_update_unknown_appends_the_active_path"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_detail_escapes_path_with_bracket"
        status: pass
    human_judgment: false
  - id: D5
    description: "A broken row shows a red ! in Inst, the repair sentence in the detail, ! broken on legend line 1, and u answers with the same hint without updating."
    requirement: D-18
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_broken_row_marks_inst_red_and_explains_repair"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_update_on_broken_row_hints_repair_without_updating"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_legend_names_the_broken_mark"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_legend_keeps_the_catalog_table_usable_at_the_minimum_size"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 15: Catalog Ownership Markers Summary

**The catalog row now shows off-policy, dual-owner, unknown-path, and broken facts, and u never returns silently.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-10-10T16:47:00Z
- **Completed:** 2026-10-10T17:12:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- An off-policy Owner cell reads `Homebrew ≠ policy`, with the tag dim. The detail says the catalog's policy installs that tool via the declared manager.
- `u` on a current tool sets `<id> is already current`. An off-policy current tool appends the migration-pending sentence and does not call `UpdateService.begin`.
- The detail pane uses `also_installed_note` and `active_path_note`. Filesystem paths in that markup are escaped per segment.
- A broken row shows a red `!`, the repair sentence, a legend entry on line 1, and `u` repeats the hint instead of updating.

## Task Commits

Each task was committed atomically:

1. **Task 1: off-policy Owner cell, detail, and current u** - `2d7c81b` (feat)
2. **Task 2: dual-owner and unknown-path detail texts** - `b3379bc` (feat)
3. **Task 3: broken Inst state** - `46ba533` (feat)

**Plan metadata:** this commit (docs)

## Files Created/Modified

- `installer/catalog_tui.py` - Owner tag, detail notes, escaped paths, broken Inst/legend/`u`
- `tests/test_catalog_tui.py` - pinned texts, begin-not-called fake, markup escape, legend width

## Decisions Made

- The broken check is in `_inst_cell`, not `_row_cells`. Plan 16-12 moved the check/circle ternary there. The skill-pack branch is untouched, so a skill pack does not grow a broken mark.
- Off-policy sentences are skipped when `declared_manager_label` or `owner_label` returns None.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The silent-current test called the real status line**

- **Found during:** Task 2 (full `tests/test_catalog_tui.py` run)
- **Issue:** `test_action_update_tool_skips_confirmed_current` did not stub `status.set`. Once `u` answers, the real `StatusLine.set` calls `update()` and raises `NoActiveAppError` on an unmounted screen.
- **Fix:** Stub `set` and pin `rg is already current`.
- **Files modified:** `tests/test_catalog_tui.py`
- **Verification:** `uv run pytest tests/test_catalog_tui.py -q` exited 0.
- **Committed in:** `b3379bc` (Task 2 commit)

**2. [Rule 2 - Missing] No test pinned the literal `also claimed by`**

- **Found during:** Task 2
- **Issue:** The plan said to update tests that pinned `also claimed by`. None did. `test_detail_line_names_competing_manager_and_active_path` only asserted the substring `installer`.
- **Fix:** That test now pins `also installed via installer artifact — live copy at <path>`.
- **Files modified:** `tests/test_catalog_tui.py`
- **Verification:** The test failed on the old wording, then passed.
- **Committed in:** `b3379bc` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing assertion)
**Impact on plan:** Both keep the new `u` answer and the D-06 wording from passing on the old contract. No scope creep.

## Issues Encountered

None beyond the two test fixes above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The three tier views share this screen, so the markers are already on every catalog view.
- An outdated off-policy `u` still goes through `UpdateService`. Plan 16-05's note is appended by `on_tool_updated` from `outcome.detail`. This plan did not add a second update path.
- Migration itself stays deferred (D-04). No migrate key was added.

## Self-Check: PASSED

- `grep -n '≠ policy' installer/catalog_tui.py` returned line 609.
- `grep -n 'is already current' installer/catalog_tui.py` returned line 913.
- `grep -c 'also claimed by' installer/catalog_tui.py` printed 0.
- `grep -n 'from rich.markup import escape' installer/catalog_tui.py` returned line 13.
- `grep -n '! broken' installer/catalog_tui.py` returned line 279.
- `uv run pytest tests/test_catalog_tui.py tests/test_wizard_app.py -q` — 455 passed.
- `uv run pytest -q` exited 0. Reached 100% with no FAILED line.
- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
