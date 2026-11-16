---
phase: 25-lean
plan: "08"
subsystem: ui
tags: [textual, refactor, verbatim-move, wizard-app-split, ast-check]

# Dependency graph
requires:
  - phase: 25-lean
    provides: plan 25-07 (mutation_lock.py, modals.py, public ui_common.sentence and TIMES_LISTED, and the p25-moved-same.py checker)
provides:
  - installer/policies_screen.py holding PolicyInputs, PoliciesScreen, link_mode_status and the helpers and constants only the Policies view uses, moved verbatim
  - installer/schedules_screen.py holding ScheduleInputs, ScheduleChange, ScheduleChanged, ScheduleManagerProbed, SchedulesScreen and the helpers and constants only the Schedules view uses, moved verbatim
  - ui_common.fit (was wizard_app._fit), diskusage.DiskPressureProbe and systemd_daemon.CompetingProbe as the one public home of each shared name
affects: [25-09, 25-10]

# Actuals (#2632) - chars/4 over the realized diff (git diff c1536185..HEAD = 135386 chars)
actuals:
  tokens: 33847
  tasks: 2
  commits: 2

plan_head_before: c1536185491cd6823a8175c2d31c7e3bbe590758
plan_head_after: e590c115238e3667357ba9b1531116d09e801630

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verbatim move, proven by AST: p25-moved-same.py compares every moved top-level node against the HEAD node with docstrings dropped and the rename map applied"
    - "no compatibility shim and no cycle: importers switch to the new module in the same commit; screens import UnifiedApp only under TYPE_CHECKING"

key-files:
  created:
    - installer/policies_screen.py
    - installer/schedules_screen.py
  modified:
    - installer/wizard_app.py
    - installer/compose.py
    - installer/ui_common.py
    - installer/diskusage.py
    - installer/systemd_daemon.py
    - tests/test_catalog_tui.py
    - tests/test_execute_screen.py
    - tests/test_layout_80x20.py
    - tests/test_policies_e2e.py
    - tests/test_schedules_view.py
    - tests/test_schedules_handover.py
    - tests/test_screen_family.py
    - tests/test_setup.py
    - tests/test_uninstall_e2e.py
    - tests/test_wizard_app.py

key-decisions:
  - "Moved bodies, comments and names are unchanged; the only renames are _fit -> fit and _link_mode_status -> link_mode_status (D-07)"
  - "The two probe aliases moved beside the types they wrap (DiskPressure, CompetingUnit) instead of staying in wizard_app, so neither screen module needs wizard_app at runtime"
  - "The silent vars(wizard_app) refresh patch now targets schedules_screen through monkeypatch.setattr, which raises on a missing name (T-25-19)"
  - "No shim: compose.py and every test import from the new homes in the same commit"

patterns-established:
  - "Screen modules narrow self.app with a TYPE_CHECKING-only UnifiedApp import, as catalog_tui.py does"

requirements-completed: [LEAN-03]

coverage:
  - id: D1
    description: "installer/policies_screen.py holds the Policies view; fit, link_mode_status and the probe aliases each have one public home"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/policies_screen.py --target installer/ui_common.py --target installer/diskusage.py --target installer/systemd_daemon.py --rename _fit=fit --rename _link_mode_status=link_mode_status (checked 12 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_policies_e2e.py, tests/test_layout_80x20.py, tests/test_screen_family.py, tests/test_wizard_app.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "installer/schedules_screen.py holds the Schedules view; its constant patch is loud and on the owning module"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/schedules_screen.py (checked 24 names, exit 0; after the commit with --rev HEAD~1, checked 24 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_schedules_view.py, tests/test_schedules_handover.py"
        status: pass
    human_judgment: false

# Metrics
duration: "not measured (the plan start time was not captured)"
completed: 2026-11-15
status: complete
---

# Phase 25 Plan 08: the Policies and Schedules views move out of wizard_app.py verbatim

**The Policies and Schedules views now live in installer/policies_screen.py and installer/schedules_screen.py, moved verbatim with their inputs, messages, helpers and constants, and the names they share have one public home each (ui_common.fit, diskusage.DiskPressureProbe, systemd_daemon.CompetingProbe), each move proven by an AST checker against HEAD.**

## Performance

- **Duration:** not measured (the plan start time was not captured)
- **Completed:** 2026-11-15
- **Tasks:** 2 of 2 completed
- **Files modified:** 15 modified, 2 created (wizard_app.py 3990 -> 2755 lines; policies_screen.py 526, schedules_screen.py 749)

## Accomplishments
- PolicyInputs, PoliciesScreen, link_mode_status and `_POLICY_READ_ERROR`, `_read_failure`, `_DRIFT_DETAIL`, `_read_active_owned`, `_POLICY_FIXED_COLUMNS`, `_POLICY_EFFECT_FLOOR` live in installer/policies_screen.py.
- ScheduleInputs, ScheduleChange, ScheduleChanged, ScheduleManagerProbed, SchedulesScreen and the 18 helpers and constants only the view uses live in installer/schedules_screen.py. The Messages keep their post sites and handlers on SchedulesScreen.
- `fit` is public in ui_common; SchedulesScreen's `_fit` calls became `fit` in Task 1 and moved with it in Task 2. DiskPressureProbe and CompetingProbe sit next to DiskPressure and CompetingUnit.
- Neither screen module imports installer.wizard_app outside `if TYPE_CHECKING:`. compose.py imports PolicyInputs and ScheduleInputs from the new modules.
- The pilot safety net and the full suite are green on each commit.

## Task Commits

1. **Task 1: the Policies view lives in installer/policies_screen.py, with fit, link_mode_status and the probe aliases in their one public home** - `51c8d3e3` (refactor)
2. **Task 2: the Schedules view lives in installer/schedules_screen.py, and its tests patch the module that now owns its constants** - `e590c115` (refactor)

## Files Created/Modified
- `installer/policies_screen.py` (new) - the Policies view, moved verbatim; `_fit(` -> `fit(` and `_link_mode_status` -> `link_mode_status` only
- `installer/schedules_screen.py` (new) - the Schedules view, moved verbatim; `_fit(` -> `fit(` only
- `installer/ui_common.py` - adds `fit` (body unchanged)
- `installer/diskusage.py`, `installer/systemd_daemon.py` - gain the probe aliases with their comments
- `installer/wizard_app.py` - the moved blocks are removed; it imports the screens, `link_mode_status`, `fit` and the aliases it still uses (UnifiedApp, DoctorScreen)
- `installer/compose.py` - imports PolicyInputs and ScheduleInputs from the new modules
- `tests/*` (nine files) - import lines, plus two lines in tests/test_schedules_view.py (the `vars(wizard_app)` patch and read now use `schedules_screen`)

## Verification Evidence

**Move checker on the real tree** (`p25-moved-same.py`, reused from 25-07):
- Task 1, `--rev HEAD` on the working tree before the commit: `checked 12 names at HEAD`, exit 0.
- Task 2, `--rev HEAD` before the commit: `checked 24 names at HEAD`, exit 0; after the commit, `--rev HEAD~1`: `checked 24 names at HEAD~1`, exit 0.

**Acceptance greps (plan):**
- `class PoliciesScreen|PolicyInputs|def link_mode_status(`: 3 in policies_screen.py; the old forms in wizard_app.py: 0.
- `def fit(` in ui_common.py: 1; `DiskPressureProbe` in diskusage.py: 1; `CompetingProbe` in systemd_daemon.py: 1.
- `class SchedulesScreen|ScheduleInputs|ScheduleChanged|ScheduleManagerProbed`: 4 in schedules_screen.py, 0 in wizard_app.py.
- `vars(wizard_app)` in tests/test_schedules_view.py: 0 (baseline 2).
- `installer.wizard_app` in each new module: only the line inside `if TYPE_CHECKING:`.

**Test diff prohibition:** over this plan the test diff is import lines and exactly two non-import changes in tests/test_schedules_view.py: `monkeypatch.setitem(vars(wizard_app), "_REFRESH_SECONDS", 0.05)` became `monkeypatch.setattr(schedules_screen, "_REFRESH_SECONDS", 0.05)`, and `vars(wizard_app)["_SCHEDULE_COLUMNS"]` became `vars(schedules_screen)[...]`. Both are the monkeypatch-target and module-reference changes the plan names. No assertion changed; no suppression added.

**Gates:** on each commit `make validate` exit 0 and `make test` 7617 passed, 6 skipped, coverage 96.14%. The final tree is the Task 2 tree plus this SUMMARY file.

## Decisions Made
- `tests/test_screen_family.py` keeps patching `"installer.wizard_app.move_link_mode"`: it drives the UnifiedApp path, which still calls `move_link_mode` from wizard_app. No test drives the Policies path through a patch.
- Consecutive one-line constants that sat adjacent in wizard_app stay adjacent in schedules_screen (blank lines are formatting, not AST; the checker confirms equality).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] New-module headers and wizard_app imports needed completion**
- **Found during:** Task 1 and Task 2
- **Issue:** The verbatim bodies referenced names (Text, Static, DataTable, ColumnKey, env_redirect, run_live, cursor_shim and others) that the new headers did not import; the moves left unused imports in wizard_app.
- **Fix:** Added the imports to the new module headers (ruff F821 guided) and ran `ruff check --fix` for F401 and I001 in wizard_app and tests. Import lines only.
- **Files modified:** installer/policies_screen.py, installer/schedules_screen.py, installer/wizard_app.py
- **Committed in:** 51c8d3e3, e590c115

**Total deviations:** 1 auto-fixed (Rule 3, import completeness). No code body, name or behavior changed.

## Issues Encountered
None.

## Known Stubs
None.

## Threat Flags
None. The change moves existing code between modules and adds no network endpoint, auth path, file access pattern or schema change.

## Next Phase Readiness
- Plan 25-09 can move DoctorScreen and UninstallScreen reusing `p25-moved-same.py`; DoctorScreen imports DiskPressureProbe and CompetingProbe from diskusage and systemd_daemon, and `fit` from ui_common if it needs it.
- wizard_app.py now holds DoctorScreen, UninstallScreen, UnifiedApp, UninstallInputs and the remaining messages.

## Self-Check: PASSED

Created files present: installer/policies_screen.py, installer/schedules_screen.py, this SUMMARY. Task commits 51c8d3e3 and e590c115 are ancestors of HEAD.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
