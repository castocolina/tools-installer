---
phase: 25-lean
plan: "09"
subsystem: ui
tags: [textual, refactor, verbatim-move, wizard-app-split, ast-check]

# Dependency graph
requires:
  - phase: 25-lean
    provides: plans 25-07 and 25-08 (mutation_lock.py, modals.py, policies_screen.py, schedules_screen.py, ui_common.fit, the probe aliases and the p25-moved-same.py checker)
provides:
  - installer/doctor_screen.py holding DoctorScreen and the helpers and constants only it uses, moved verbatim
  - installer/doctor_messages.py holding GlobalsReinstalled, GlobalsAudited (with its generation field) and DiskPressureProbed, moved verbatim
  - installer/uninstall_screen.py holding RemovalFinished and UninstallScreen, moved verbatim
  - installer/uninstall_review.py holding UninstallInputs, config_split and the pure review types, constants and helpers, twelve of them now public
affects: [25-10]

# Actuals (#2632) - chars/4 over the realized diff
actuals:
  tokens: 90000
  tasks: 2
  commits: 2

plan_head_before: 0d06e92a616af17cb7ddfee2fb61ea674e385288
plan_head_after: 81be1c67871ca9dfb6fe3216cae1f0ba9c8992f6

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verbatim move, proven by AST: p25-moved-same.py compares every moved top-level node against the HEAD node with docstrings dropped and the rename map applied"
    - "no shim and no cycle: importers switch to the new module in the same commit; screens import UnifiedApp only under TYPE_CHECKING"

key-files:
  created:
    - installer/doctor_screen.py
    - installer/doctor_messages.py
    - installer/uninstall_screen.py
    - installer/uninstall_review.py
  modified:
    - installer/wizard_app.py
    - installer/compose.py
    - tests/test_catalog_tui.py
    - tests/test_execute_screen.py
    - tests/test_layout_80x20.py
    - tests/test_policies_e2e.py
    - tests/test_schedules_view.py
    - tests/test_screen_family.py
    - tests/test_setup.py
    - tests/test_uninstall_e2e.py
    - tests/test_wizard_app.py

key-decisions:
  - "Moved bodies, comments and names are unchanged; the only renames are the twelve uninstall privates that uninstall_screen imports, which became public (D-07)"
  - "_REVIEW_COLUMN stays private (only review_line uses it); _REMOVAL_QUIT_WAIT and _REMOVAL_QUIT_CUT stay in wizard_app (only UnifiedApp reads them)"
  - "No shim: compose.py and every test import from the new homes in the same commit"

patterns-established:
  - "A view too big for the 800-line cap gets a sibling module for its messages or its pure helpers"

requirements-completed: [LEAN-03]

coverage:
  - id: D1
    description: "installer/doctor_screen.py holds the Doctor view and installer/doctor_messages.py its three messages; GlobalsAudited keeps its generation field"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/doctor_screen.py --target installer/doctor_messages.py (checked 16 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_layout_80x20.py, tests/test_screen_family.py, tests/test_wizard_app.py, tests/test_setup.py, tests/test_reachability.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "installer/uninstall_screen.py holds the Uninstall view and installer/uninstall_review.py its inputs and pure review helpers"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/uninstall_review.py --target installer/uninstall_screen.py with the twelve --rename pairs (checked 17 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall_e2e.py, tests/test_wizard_app.py, tests/test_screen_family.py and the other importers"
        status: pass
    human_judgment: false

# Metrics
duration: "not measured"
completed: 2026-11-15
status: complete
---

# Phase 25 Plan 09: the Doctor and Uninstall views move out of wizard_app.py verbatim

**The Doctor and Uninstall views now live in installer/doctor_screen.py and installer/uninstall_screen.py, each with a sibling (doctor_messages.py, uninstall_review.py), moved verbatim and proven by an AST checker; wizard_app.py holds only the app.**

## Performance

- **Tasks:** 2 of 2 completed
- **Files:** 11 modified, 4 created
- **Line counts:** wizard_app.py 2755 -> 879; doctor_screen.py 782; doctor_messages.py 55; uninstall_screen.py 979; uninstall_review.py 184. uninstall_screen.py still exceeds 800; plan 25-10 does the cleanup and lands the cap guard.

## Accomplishments
- DoctorScreen, `_NOTHING_TO_REINSTALL`, the `_GLOBALS_*` and `_DISK_PRESSURE_*` constants, `_POST_APPLY_REWRITES`, `_DOCTOR_READ_ERROR` and `_smoke_findings` live in doctor_screen.py; the three messages live in doctor_messages.py, `GlobalsAudited.generation` intact (the race epoch check is unchanged).
- RemovalFinished and UninstallScreen live in uninstall_screen.py; UninstallInputs, config_split, `UninstallEntry`, `STATE_TITLES`, `REMOVES_CELL_MAX`, `NOTHING_TO_UNINSTALL`, `BLOCK_KEY`, `TWEAK_KEY`, `SETTINGS_KEY`, `ENV_KEYS`, `EnvState`, `review_line`, `retired_detail`, `retired_review_lines` and private `_REVIEW_COLUMN` live in uninstall_review.py.
- wizard_app.py defines only ScheduleDefaultsApplied, RefreshPublished, RefreshFinished, UnifiedApp and the two removal-quit strings.
- None of the four new modules imports installer.wizard_app outside `if TYPE_CHECKING:` (only uninstall_screen.py and doctor_screen.py need it).

## Task Commits

1. **Task 1: the Doctor view lives in installer/doctor_screen.py with its messages in installer/doctor_messages.py** - `ee259c8c` (refactor)
2. **Task 2: the Uninstall view lives in installer/uninstall_screen.py with its inputs and pure review helpers in installer/uninstall_review.py** - `81be1c67` (refactor)

## Verification Evidence

**Move checker** (`p25-moved-same.py`, reused from 25-07), run on the working tree with `--rev HEAD` before each commit:
- Task 1: `checked 16 names at HEAD`, exit 0.
- Task 2: `checked 17 names at HEAD` with the twelve renames, exit 0.

**Acceptance greps:**
- Task 1: one DoctorScreen class in doctor_screen.py; three message classes in doctor_messages.py; `generation` present in doctor_messages.py; none of the four classes left in wizard_app.py.
- Task 2: `grep -c "^class \|^def "` on wizard_app.py prints 4; the four moved definitions no longer appear there.

**Test diff prohibition:** over this plan `git diff -U0 -- tests` is import lines only (new-home imports added, old names dropped from the wizard_app import lines). No assertion changed; no suppression added. The pre-existing `monkeypatch.setattr("installer.wizard_app.path_writer_lines_for", ...)` and `...move_link_mode` targets are untouched because UnifiedApp still calls both.

**Gates:** on each commit `make validate` exit 0 (ruff, format, pyright, bandit, vulture) and `make test` 7617 passed, 6 skipped, coverage 96.15%.

## Decisions Made
- The new modules start from the original wizard_app import block and let `ruff check --select F401,I --fix` prune it, so each header imports exactly what its moved bodies use.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] New-module headers and wizard_app imports needed completion**
- **Found during:** Task 1 and Task 2
- **Issue:** the moves left unused imports in wizard_app and the new modules needed headers for the names their bodies use.
- **Fix:** seeded each header from the original import block and ran `ruff check --fix` (F401, I001); added the explicit `uninstall_review` import list in uninstall_screen.py. Import lines only.
- **Files modified:** the four new modules, installer/wizard_app.py
- **Committed in:** ee259c8c, 81be1c67

**Total deviations:** 1 auto-fixed (Rule 3, import completeness). No code body, name (beyond the planned renames) or behavior changed.

## Issues Encountered
None.

## Known Stubs
None.

## Threat Flags
None. The change moves existing code between modules and adds no network endpoint, auth path, file access pattern or schema change.

## Next Phase Readiness
- Plan 25-10 does the comment cleanup and helper extraction and lands the 800-line cap guard; installer/uninstall_screen.py (979 lines) is the module that still exceeds the cap.

## Self-Check: PASSED

Created files present: installer/doctor_screen.py, installer/doctor_messages.py, installer/uninstall_screen.py, installer/uninstall_review.py, this SUMMARY. Task commits ee259c8c and 81be1c67 are ancestors of HEAD.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
