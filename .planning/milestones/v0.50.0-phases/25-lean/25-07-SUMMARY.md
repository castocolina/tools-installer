---
phase: 25-lean
plan: "07"
subsystem: ui
tags: [textual, refactor, verbatim-move, wizard-app-split, ast-check]

# Dependency graph
requires:
  - phase: 25-lean
    provides: plans 25-04 to 25-06 (the wizard_app composition root, cleanup and run-log work this split builds on)
provides:
  - installer/mutation_lock.py holding MUTATION_REFUSAL, SCHEDULED_RUN_REFUSAL and MutationLock, moved verbatim
  - installer/modals.py holding ConfirmGuardFile, ConfirmUninstall, NavScreen, LinkModeScreen, ScheduleTimeScreen, CursorModelsRead and CursorModelScreen, moved verbatim
  - ui_common.sentence and ui_common.TIMES_LISTED as the public homes of the names a modal shares with the schedules view
affects: [25-08, 25-09, 25-10]

# Actuals (#2632) — chars/4 over the realized diff (git diff 6fa3bf77..HEAD = 49513 chars)
actuals:
  tokens: 12378
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verbatim move, proven by AST: moved nodes compared against the HEAD node with docstrings dropped and the rename map applied"
    - "no compatibility shim: importers switch to the new module in the same commit"

key-files:
  created:
    - installer/mutation_lock.py
    - installer/modals.py
  modified:
    - installer/wizard_app.py
    - installer/ui_common.py
    - tests/test_mutation_runlock.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
    - tests/test_layout_80x20.py
    - tests/test_policies_e2e.py
    - tests/test_schedules_view.py
    - tests/test_setup.py

key-decisions:
  - "The moved classes keep their bodies, comments and names; the only renames are _sentence -> sentence and _TIMES_LISTED -> TIMES_LISTED, both public in ui_common (D-07)"
  - "CursorModelsRead moves with the modals although only CursorModelScreen uses it, as the plan lists it"
  - "No compatibility shim and no runtime import of installer.wizard_app from either new module"
  - "Test importers now import from the new modules; no test assertion changed (the test diff is 18 import lines)"

patterns-established:
  - "Verbatim-move gate: p25-moved-same.py compares every moved top-level node against HEAD, fails on lost, mismatched, remaining or zero-name cases, and is reused by plans 25-08 and 25-09"

requirements-completed: [LEAN-03]

coverage:
  - id: D1
    description: "installer/mutation_lock.py holds the mutation lock; UnifiedApp still refuses a second mutation through it"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/mutation_lock.py (checked 3 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_mutation_runlock.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "installer/modals.py holds the seven modal screens and messages, moved verbatim; wizard_app and the tests import them from there"
    requirement: "LEAN-03"
    verification:
      - kind: other
        ref: "p25-moved-same.py --rev HEAD --source installer/wizard_app.py --target installer/modals.py --target installer/ui_common.py --rename _sentence=sentence --rename _TIMES_LISTED=TIMES_LISTED (checked 9 names, exit 0)"
        status: pass
      - kind: unit
        ref: "tests/test_layout_80x20.py, tests/test_screen_family.py, tests/test_wizard_app.py, tests/test_schedules_view.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "ui_common exposes sentence and TIMES_LISTED, the names the modals share with the schedules view"
    requirement: "LEAN-03"
    verification:
      - kind: unit
        ref: "tests/test_schedules_view.py"
        status: pass
    human_judgment: false

# Metrics
duration: "not measured (the plan start time was not captured)"
completed: 2026-11-15
status: complete
---

# Phase 25 Plan 07: the mutation lock and the modal screens move out of wizard_app.py verbatim

**The mutation lock and seven modal screens moved verbatim out of wizard_app.py into installer/mutation_lock.py and installer/modals.py, with sentence and TIMES_LISTED public in ui_common, each move proven by an AST checker against HEAD.**

## Performance

- **Duration:** not measured (the plan start time was not captured)
- **Started:** not captured
- **Completed:** 2026-11-15
- **Tasks:** 2 of 2 completed
- **Files modified:** 11 modified, 2 created

## Accomplishments
- The mutation lock (MUTATION_REFUSAL, SCHEDULED_RUN_REFUSAL, MutationLock) lives in installer/mutation_lock.py; UnifiedApp still inherits it.
- The seven modal screens and messages live in installer/modals.py; no modal reads a wizard_app name.
- ui_common publishes sentence (was _sentence) and TIMES_LISTED (was _TIMES_LISTED); the schedules view and the modals use the same public names.
- The verbatim-move checker is written and self-checked; the AST comparison of all 12 moved top-level names (3 + 9) passes against HEAD and against each task's parent.
- The pilot safety net and the full suite are green on each commit.

## Task Commits

Each task was committed atomically:

1. **Task 1: the mutation lock lives in installer/mutation_lock.py** - `5d5daac2` (refactor)
2. **Task 2: the modal screens live in installer/modals.py, with sentence and TIMES_LISTED public in ui_common** - `6479ce16` (refactor)

## Files Created/Modified
- `installer/mutation_lock.py` (new) - MUTATION_REFUSAL, SCHEDULED_RUN_REFUSAL, MutationLock, moved verbatim
- `installer/modals.py` (new) - the seven modal screens and messages, moved verbatim; the two renamed names are used from ui_common
- `installer/ui_common.py` - adds sentence (was `_sentence`) and TIMES_LISTED (was `_TIMES_LISTED`), bodies unchanged, plus the sanitize_log_line import sentence needs
- `installer/wizard_app.py` - the moved blocks are removed; it imports MutationLock, the six modals it uses, sentence and TIMES_LISTED; its SchedulesScreen references use the public names
- `tests/test_mutation_runlock.py`, `tests/test_screen_family.py`, `tests/test_wizard_app.py`, `tests/test_layout_80x20.py`, `tests/test_policies_e2e.py`, `tests/test_schedules_view.py`, `tests/test_setup.py` - import lines only

## Verification Evidence

**Checker self-check** (`/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/p25-moved-same.py`, self-check driver `.../scratchpad/p25-07-selfcheck.py`, run on scratch git repos):

```
[PASS] moved names equal (docstrings ignored): exit=0 (want 0)
    checked 3 names at HEAD
[PASS] changed function body is a mismatch: exit=1 (want 1)
    checked 3 names at HEAD
    mismatch: helper differs from installer/target.py:helper at HEAD
[PASS] dropped name is lost: exit=1 (want 1)
    checked 2 names at HEAD
    lost: Moved (-> Moved) is not a top-level definition in any target
[PASS] leftover renamed reference remains: exit=1 (want 1)
    checked 4 names at HEAD
    remains: _old is still referenced or defined in installer/source.py
[PASS] class copied into target but kept in source remains: exit=1 (want 1)
    checked 0 names at HEAD
    remains: MOVED is defined in installer/target.py but still at top level in installer/source.py
    remains: helper is defined in installer/target.py but still at top level in installer/source.py
    remains: Moved is defined in installer/target.py but still at top level in installer/source.py
    zero: no removed name was compared
[PASS] nothing removed fails with zero names checked: exit=1 (want 1)
    checked 0 names at HEAD
    remains: MOVED is defined in installer/target.py but still at top level in installer/source.py
    remains: helper is defined in installer/target.py but still at top level in installer/source.py
    remains: Moved is defined in installer/target.py but still at top level in installer/source.py
    zero: no removed name was compared
[PASS] renamed constant is equal under the rename map: exit=0 (want 0)
    checked 1 names at HEAD
7/7 self-checks passed
```

**Move checker on the real tree:**
- Task 1, `--rev HEAD --source installer/wizard_app.py --target installer/mutation_lock.py`: `checked 3 names at HEAD`, exit 0. After the commit, `--rev HEAD~1`: `checked 3 names at HEAD~1`, exit 0.
- Task 2, `--rev HEAD --source installer/wizard_app.py --target installer/modals.py --target installer/ui_common.py --rename _sentence=sentence --rename _TIMES_LISTED=TIMES_LISTED`: `checked 9 names at HEAD`, exit 0. After the commit, `--rev HEAD~1`: `checked 9 names at HEAD~1`, exit 0.

**Acceptance greps (plan):**
- `installer/mutation_lock.py` defines 3 of the lock names; `installer/wizard_app.py` defines 0 of them.
- `installer/mutation_lock.py` and `installer/modals.py` reference `installer.wizard_app` 0 times (no runtime import cycle).
- `installer/modals.py` defines 7 of the modal classes; `installer/wizard_app.py` defines 0.
- `installer/ui_common.py` defines `def sentence(` and `TIMES_LISTED = ` (2 matches).

**Test diff prohibition:** `git diff -U0 -- tests` over this plan changes 18 lines, all import lines (`from installer.wizard_app import` replaced by `from installer.modals import` or `from installer.mutation_lock import`, and the names removed from the wizard_app import lists). No assertion changed; no suppression added.

**Gates:**
- Task 1: `make validate` exit 0; `make test` 7617 passed, 6 skipped, coverage 96.13%.
- Task 2: `make validate` exit 0; `make test` 7617 passed, 6 skipped, coverage 96.14%.
- The final tree is the Task 2 tree plus this SUMMARY file (documentation only), so the gates above hold for the final tree.

## Decisions Made
- Moved text keeps bodies, comments and names; the only text edits are the two renames the plan lists, applied inside the moved modal block and in wizard_app's SchedulesScreen references.
- `from __future__ import annotations` is not added to the new modules, matching wizard_app; the lock's annotations are evaluated at class-definition time against real imports.
- The new modules import ExecuteScreen, AppScreen, RefreshRequested and run_live at runtime, which the bodies need; none of them imports installer.wizard_app.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Modal module imports the moved bodies need were missing**
- **Found during:** Task 2 (modals.py creation)
- **Issue:** The verbatim bodies of CursorModelScreen reference `Callable`, `run_live` and `sanitize_log_line`, which the plan's header did not list; ruff F821 reported them.
- **Fix:** Added the three imports to installer/modals.py's header, and the sanitize_log_line import to ui_common.py (needed by `sentence`). Bodies unchanged.
- **Files modified:** installer/modals.py, installer/ui_common.py
- **Verification:** `ruff check` clean; the AST checker reports 9 names equal.
- **Committed in:** 6479ce16 (Task 2)

**2. [Rule 3 - Blocking] Unused imports left behind by the moves**
- **Found during:** Task 1 and Task 2
- **Issue:** Moving the blocks left imports unused in wizard_app.py (for example `runlock`, and several textual and rich names) and unused names in the new module headers.
- **Fix:** `ruff check --fix` removed them (F401) and sorted the new import blocks (I001). Import lines only.
- **Files modified:** installer/wizard_app.py, installer/mutation_lock.py, installer/modals.py
- **Verification:** `ruff check installer tests setup.py` and `make validate` exit 0.
- **Committed in:** 5d5daac2 (Task 1) and 6479ce16 (Task 2)

**Total deviations:** 2 auto-fixed (both Rule 3, blocking lint/import completeness)
**Impact on plan:** Import-line changes only. No code body, name or behavior changed; no scope creep.

## Issues Encountered
- The guard script `p25-moved-same.py` was not present in the session scratchpad. It was re-created from the plan text under the same name and self-checked (output above) before first use.
- The first Task 1 commit attempt failed because its message file had not been written yet. Git refused the commit before creating anything; the pre-commit hooks had already passed. The message file was written and the commit repeated, so the history has one commit per task.
- The measured realized diff (49513 characters, `actuals.tokens` 12378) is well below the plan's `estimate.tokens` of 50000. The measured figure is recorded as is, so future estimates are calibrated against it.

## Known Stubs
None.

## Threat Flags
None. The change moves existing code between modules and adds no network endpoint, auth path, file access pattern or schema change.

## Next Phase Readiness
- Plans 25-08 and 25-09 reuse `p25-moved-same.py` in the session scratchpad; its self-check is `p25-07-selfcheck.py` in the same directory.
- The modal and lock modules are leaves: later screen moves can import them without a cycle.
- wizard_app.py now holds the screen classes that stay (DoctorScreen, UninstallScreen, PoliciesScreen, SchedulesScreen, UnifiedApp and the messages).

## Self-Check: PASSED

Created files present: installer/mutation_lock.py, installer/modals.py, this SUMMARY. Task commits 5d5daac2 and 6479ce16 are ancestors of HEAD.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
