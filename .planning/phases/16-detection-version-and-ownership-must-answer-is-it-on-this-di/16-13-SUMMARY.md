---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 13
subsystem: ui
tags: [execute-screen, post-install, repair, already-current]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: ManagerOwnership.broken and install_tool(repair=True) from plan 16-09
provides:
  - Current explicit selections are named in the preflight and progress list instead of Install 0 tools
  - reapply_post_install for an explicit installed selection only
  - Broken selections enter the install order with repair=True, and broken beats outdated
affects: [16-15, 16-16]

actuals:
  tokens: 8034
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - Classification sits in ExecuteScreen before resolve_dependencies; deps.py is unchanged
    - repair=True is composed by _with_repair so SensitiveInstall stays unwidenend

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - installer/engine.py
    - installer/post_install.py
    - tests/test_execute_screen.py
    - tests/test_engine.py
    - tests/test_post_install.py

key-decisions:
  - "Repair ids are excluded from _reapply. A repair install already dispatches post_install on the success path (16-09)."
  - "Reapply outcomes are appended after summarize(), so Summary.already stays install-only."

patterns-established:
  - "A current tool is a progress row of its own (`✓ {id} [already current]`), not an install or update row."
  - "_with_repair adds repair=True only for repair ids. Fakes that lack the kwarg keep working for every other tool."

requirements-completed: [D-17, D-18, D-20]

coverage:
  - id: D1
    description: "A current explicit selection says already current and never Install 0 tools. An outdated selection stays on the update path. A mixed selection names the current tool."
    requirement: D-17
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_current_only_selection_says_already_current_not_install_zero"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_outdated_selected_tool_stays_an_update_target"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_mixed_install_and_current_names_already_current"
        status: pass
    human_judgment: false
  - id: D2
    description: "Explicit installed selections re-dispatch post_install once. Drag-ins, fresh installs, and a cancel do not. Summary.already ignores the reapply outcome."
    requirement: D-20
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_reapply_post_install_returns_handoff_without_installing"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_explicit_current_selection_reapplies_post_install_once"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_installed_drag_in_is_not_reapplied"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_cancel_stops_reapply_before_any_dispatch"
        status: pass
    human_judgment: false
  - id: D3
    description: "A broken selection is installed with repair=True, counted under Install, and not updated. Broken beats outdated."
    requirement: D-18
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_broken_selection_is_installed_with_repair"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_broken_and_outdated_repairs_instead_of_updating"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_broken_tool_preflight_counts_as_install"
        status: pass
    human_judgment: false

duration: 42min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 13: Already-current, reapply, and repair Summary

**Selecting a current tool says so, re-applies post-install only on that explicit selection, and repairs a broken tool through the normal install ladder.**

## Performance

- **Duration:** 42 min
- **Started:** 2026-10-10T15:29:48Z
- **Completed:** 2026-10-10T16:11:22Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- A current selection is named in the preflight (`already current — nothing to do`) and the progress list. `Install 0 tools` is not emitted.
- `reapply_post_install` shares install_tool's crash isolation and runs only for an explicit installed selection that was not repaired in this run.
- A broken selection is ordered as not-yet-installed and installed with `repair=True`. Broken wins over outdated.

## Task Commits

Each task was committed atomically:

1. **Task 1: current-tool classification, preflight, progress** - `437847f` (feat)
2. **Task 2: reapply_post_install on explicit selections only** - `a6a4653` (feat)
3. **Task 3: broken tool repair routing** - `8453422` (feat)

**Type fix:** `fa170e9` (fix) — pyright on the Task 2 confirm callbacks.

## Files Created/Modified

- `installer/execute_screen.py` - `_current` / `_repair` / `_reapply`, preflight, `_with_repair`
- `installer/engine.py` - `_dispatch_post_install`, `reapply_post_install`
- `installer/post_install.py` - D-20 explicit-selection exception in the module docstring
- `tests/test_execute_screen.py` - preflight, reapply, and repair tests
- `tests/test_engine.py` - reapply handoff and crash isolation
- `tests/test_post_install.py` - docstring exception pin

## Decisions Made

- Repair ids stay out of `_reapply`. Plan 16-09 already dispatches post_install on a repair install.
- Reapply outcomes are appended after `summarize()` and are skipped when the finish handler paints install progress, so an update row is not overwritten by `ALREADY_INSTALLED`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - correctness] Do not paint a reapply outcome over update progress**

- **Found during:** Task 2 (reapply loop)
- **Issue:** Appending reapply outcomes to the list the handoff renderer reads also feeds `on_install_run_finished`, which would mark an updated tool `done` from `ALREADY_INSTALLED` even when the update failed.
- **Fix:** Skip progress updates for ids in `_reapply`.
- **Files modified:** `installer/execute_screen.py`
- **Verification:** `test_explicit_outdated_selection_reapplies_post_install_once` passes; update rows still come from `UpdateToolFinished`.
- **Committed in:** `a6a4653` (Task 2 commit)

**2. [Rule 3 - blocking] Typed confirm callbacks**

- **Found during:** `make validate` after Task 3
- **Issue:** `confirm=lambda *_args: True` is an unknown argument under pyright.
- **Fix:** `_confirm(answer) -> ConfirmSensitiveAction`.
- **Files modified:** `tests/test_engine.py`
- **Verification:** `uv run pyright` reports 0 errors.
- **Committed in:** `fa170e9`

---

**Total deviations:** 2 auto-fixed (1 correctness, 1 blocking)
**Impact on plan:** Both keep the specified behavior type-clean. No scope creep. `deps.py` and `session.py` are untouched.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ExecuteScreen can classify current, outdated, and broken selections. Plan 16-15's catalog `u` hint and broken Inst marker can assume this enter-key path exists.
- Unattended runs still pass `on_confirm=None`, so sensitive actions stay skipped. No version service still means today's silent classification.

## Self-Check: PASSED

- `grep -n 'already current — nothing to do' installer/execute_screen.py` returns the preflight line.
- `grep -n 'def reapply_post_install\|def _dispatch_post_install' installer/engine.py` returns 2 lines. `grep -c 'run_post_install(' installer/engine.py` prints 1.
- `grep -n 'def _with_repair' installer/execute_screen.py` returns one line. `uv run pyright installer/execute_screen.py` reported 0 errors before the full `make validate` pyright pass, which also reported 0 errors.
- `git diff --stat 20c3a717..HEAD -- installer/deps.py installer/session.py` printed nothing.
- `uv run pytest tests/test_execute_screen.py tests/test_engine.py tests/test_post_install.py tests/test_session.py tests/test_deps.py -q` passed.
- `make validate` passed (ruff, format, pyright, bandit, vulture, shellcheck).
- `uv run pytest -q` exited 0.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
