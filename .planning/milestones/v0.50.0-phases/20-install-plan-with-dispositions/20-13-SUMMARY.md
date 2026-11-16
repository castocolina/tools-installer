---
phase: 20-install-plan-with-dispositions
plan: "13"
subsystem: ui
tags: [textual, pytest, reinstall, resize, terminal-layout]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: "20-12 published-state plan review, OptionList rows, and run lifecycle"
provides:
  - "Review-only r toggle for eligible installer-owned current tools"
  - "Accurate unproven-tool guidance pointing to the review r key"
  - "80x20 layout and resize re-fold behavior pinned by Textual pilots"
affects: [phase-20-follow-on-plans, ExecuteScreen, version-status-guidance]

# Actuals (#2632)
actuals:
  tokens: 5348
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rebuild Textual OptionList prompts at the widget's current fold width while preserving selection by option id."
    - "Keep reinstall-set mutation in the single user action that validates row eligibility."

key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-13-SUMMARY.md
  modified:
    - installer/execute_screen.py
    - installer/version_status.py
    - tests/test_execute_screen.py
    - tests/test_version_status.py

key-decisions:
  - "Only the review screen's r action toggles reinstall, and only for a current installer-owned direct row."
  - "The review already had the locked max-height CSS values; automated layout pilots confirmed them, so no CSS changes were needed."
  - "Reuse finding 13-1 made the exact _UNPROVEN text pin sufficient; no separate 156-cell budget test was added."
  - "The plan's recursive grep was narrowed to Python source after it matched generated .pyc caches."
  - "The orchestrator-owned .planning/config.json change was left untouched and unstaged."

patterns-established:
  - "Resize handling preserves the highlighted tool id when review prompts are rebuilt."
  - "Finished outcome prompts are re-folded at the new width; running prompts re-fold on their next normal repaint."

requirements-completed: [PLAN-02, PLAN-01]

coverage:
  - id: D1
    description: "r toggles reinstall both ways only for an eligible current installer-owned row; other rows warn, and waiting/running/finished states remain inert."
    requirement: PLAN-02
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_r_toggles_an_installer_owned_current_row_both_ways"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_r_then_enter_reinstalls_with_repair"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_r_on_a_dnf_owned_row_changes_nothing_and_warns; test_r_on_a_dragged_row_changes_nothing; test_r_is_inert_while_waiting_running_and_finished"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unproven-tool copy names the review screen where r can request reinstall and adoption."
    requirement: PLAN-02
    verification:
      - kind: unit
        ref: "tests/test_version_status.py -k unproven"
        status: pass
      - kind: other
        ref: "grep -rIn --include='*.py' 'reinstall with r to adopt' installer/ tests/"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 80x20 layout keeps status and keys visible for long plans and a worst-case finished head; row folding and resize selection are verified."
    requirement: PLAN-01
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_layout_pins_status_and_keys_to_the_last_two_rows_with_25_rows"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_layout_holds_with_the_worst_case_finished_head; test_running_layout_gives_the_log_at_least_six_rows; test_no_plan_row_line_exceeds_78_cells; test_resize_refolds_rows_and_keeps_the_cursor"
        status: pass
      - kind: unit
        ref: "make validate && make test"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real-terminal visual distinction and alignment with NO_COLOR in a non-CJK UTF-8 locale."
    requirement: PLAN-01
    verification:
      - kind: manual_procedural
        ref: "20-UI-SPEC.md: human UAT backstop, tmux 80x20 with NO_COLOR=1 and a 25-row selection"
        status: unknown
    human_judgment: true
    rationale: "Automated Textual pilots verify cell geometry but cannot judge legibility, marks, or alignment in a real terminal."

# Metrics
duration: "Not recorded; first task commit to final verification was about 18 minutes"
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 13 Summary

**The review now makes reinstall an explicit, row-scoped choice and keeps its guidance and layout truthful.**

## Performance

- **Duration:** Not fully recorded; first task commit was at 2026-10-18T02:45:49-03:00 and final verification completed at 2026-10-18T03:03:45-03:00.
- **Started:** Exact session start not recorded.
- **Completed:** 2026-10-18T03:03:45-03:00.
- **Tasks:** 3.
- **Files modified:** 5, including this summary.

## Accomplishments

- Added the review-only `r` toggle for installer-owned current rows. It rebuilds the plan, retains the highlighted id, updates the head counts, and refuses foreign-owned, dragged, or otherwise ineligible rows with a warning. The action is inert while waiting, running, or finished.
- Updated `UNPROVEN_NOTE` and its existing exact-text pin to direct users to the review screen's `r` key.
- Added 80x20 layout pilots for 25 rows, the worst-case finished head, running space, the 78-cell row limit, and resize re-folding with cursor preservation. Finished rows also re-fold on resize.

## Task Commits

Each task was committed atomically:

1. **Task 1: `r` toggles reinstall for an installer-owned current row** — `663ec43` (`feat(20-13)`).
2. **Task 2: clarify unproven reinstall guidance** — `dc6bf3d` (`docs(20-13)`).
3. **Task 3: keep status and keys visible across plan sizes** — `2dba1ad` (`feat(20-13)`).

**Plan metadata:** `docs(20-13): plan summary` (committed separately).

## Files Created/Modified

- `installer/execute_screen.py` — `r` action and refusal copy; resize re-folding; finished-state focus restored.
- `installer/version_status.py` — review-specific `UNPROVEN_NOTE` copy.
- `tests/test_execute_screen.py` — six reinstall interaction tests and five layout/resize pilots.
- `tests/test_version_status.py` — updated `_UNPROVEN` exact-text pin; no redundant budget test.
- `.planning/phases/20-install-plan-with-dispositions/20-13-SUMMARY.md` — this plan summary.

## Verification and Measured Layout

- Task 1 focused `test_r_` run: 6 passed; `tests/test_execute_screen.py` passed; `make validate && make test`: 4,880 passed, 4 skipped, 96.03% coverage.
- Task 2 `-k unproven`: 11 passed; related `tests/test_version_status.py` + `tests/test_catalog_tui.py` subset: 60 passed; full quality gate: 4,880 passed, 4 skipped, 96.03% coverage.
- Task 3 layout/78-cell/resize selection: 6 passed; `tests/test_execute_screen.py` passed; final `make validate && make test`: 4,885 passed, 4 skipped, 96.04% coverage. Post-commit, the combined `tests/test_execute_screen.py` and `tests/test_version_status.py` suite passed.
- `make validate` passed Ruff, format, Pyright, Bandit, Vulture, and ShellCheck. No new suppression comments were introduced.
- Measured with Textual pilots at 80x20:
  - **25-row review:** head y=0/h=1; plan y=1/h=17; status y=18/h=1; keys y=19/h=1; log hidden.
  - **Worst-case finished head (13 non-zero categories, two-digit counts):** head y=0/h=3; plan y=3/h=8; log y=11/h=7; status y=18/h=1; keys y=19/h=1.
  - **One-row running state:** head y=0/h=1; plan y=1/h=3; log y=4/h=14; status y=18/h=1; keys y=19/h=1.
- The real-terminal human UAT backstop was not run; see D4 in the coverage metadata.

## Decisions Made

- The reinstall set is mutated only by `action_toggle_reinstall`, through the symmetric-difference toggle after eligibility validation.
- `PlanRow.can_reinstall` stays truthful for an eligible row, while the screen suppresses the `(r: reinstall)` hint after the row changes to `REINSTALL` so the prompt matches the locked copy exactly.
- The existing CSS already contained `max-height: 3` for the head and `max-height: 8` for the running/finished plan region; pilot measurements confirmed the layout, so those rules were retained.
- No dependencies, setup behavior, host configuration, or other plan files were changed.

## Deviations from Plan

1. **Reuse finding 13-1 — omitted redundant budget test.** The plan's Task 2 listed a separate `len(UNPROVEN_NOTE) <= 156` test, but the locked reuse finding explicitly directed that it be omitted because the exact `_UNPROVEN` equality pin is stronger. Task 2 added zero budget tests.
2. **Old-copy grep scoped to source.** The specified `grep -rn` also matched pytest-generated `.pyc` caches, producing a false positive. The Python-source-only equivalent found no old string in `installer/` or `tests/`. No source artifacts or production files were changed to work around the cache matches.

**Total deviations:** 2 (one reuse-directed test omission; one validation-command adjustment).
**Impact on plan:** No behavior or scope was dropped. The manual terminal UAT remains an explicitly identified human backstop.

## Issues Encountered

- Task 1's initial pilot found that `OptionList` has no initial highlighted row. The tests now explicitly select the row before pressing `r`; the first behavior RED then showed the row stayed “skipped — already current” instead of switching to “will be reinstalled.”
- Task 2 RED produced four failures where the updated exact pin did not match the old production string; after updating the constant, all 11 `unproven` tests passed.
- Task 3 RED showed the resize test still contained a line break after expanding from 80 to 120 columns. The resize handler now repaints prompts at the current width and preserves the highlighted id.
- Quality gates initially caught formatting and type issues in the new tests and resize handler. Ruff formatting and Pyright-guided optional-index handling resolved them; the complete gate then passed.

## User Setup Required

None — no external service or configuration is required.

## Next Phase Readiness

The review interaction, truthful reinstall guidance, and automated layout contract are ready for follow-on phase work. The only remaining backstop is the planned human UAT in a real 80x20 terminal with `NO_COLOR=1` and a 25-row selection.

---
*Phase: 20-install-plan-with-dispositions*
*Plan: 20-13*
*Completed: 2026-10-18*
