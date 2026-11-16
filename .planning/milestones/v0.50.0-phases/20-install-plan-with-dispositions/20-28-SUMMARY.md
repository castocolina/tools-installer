---
phase: 20-install-plan-with-dispositions
plan: 28
subsystem: installer-core
tags: [dependency-resolution, install-plan, wizard, questionary]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: plan rows with dispositions, the install plan render/execute flow, and the plan-level force set
provides:
  - a single install wrapper that binds the sensitive-action confirmation
  - a slimmed Resolution surface (closure, blocked, requested_by)
  - a run_wizard signature with one platform source of truth
affects: [phase-20-execute-screen, phase-20-plan-render, wizard-tests]

# Actuals
actuals:
  tokens: 31175
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SensitiveInstall is the only install protocol; the composition root binds the confirmation into _with_force"
    - "Resolution carries plan rows (closure/blocked/requested_by) only — no install-order or warning text"
    - "run_wizard reads the platform from the injected refresh service, never from a parallel parameter"

key-files:
  created: []
  modified:
    - installer/session.py
    - installer/deps.py
    - installer/app.py
    - setup.py
    - tests/test_session.py
    - tests/test_deps.py
    - tests/test_registry.py
    - tests/test_catalog_tui.py
    - tests/test_app.py
    - tests/test_version_status.py
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "_with_force is the single wrapper: it binds the sensitive-action confirmation and adds repair=True for repair/reinstall rows; the old Install protocol and with_sensitive_confirm are gone"
  - "Resolution drops order, dragged_in, and warnings; blocked rows keep only tool_id and needs, and one deps-first topo sort produces the closure"
  - "run_wizard no longer takes a platform argument; setup.py and every test call site rely on refresh.platform"

patterns-established:
  - "Plan-level concerns (confirmation binding, disposition rows) live in session.py; deps.py stays free of version/ownership state"
  - "The composition root owns questionary style tokens; unused tag-* classes do not survive refactors"

requirements-completed: [PLAN-01, PLAN-06]

coverage:
  - id: D1
    description: "One install wrapper binds the sensitive-action confirmation and repair forcing"
    requirement: PLAN-01
    verification:
      - kind: unit
        ref: "tests/test_session.py#install wrapper and sensitive-install protocol tests"
        status: pass
    human_judgment: false
  - id: D2
    description: "Resolution returns closure, blocked (tool_id + needs), and requested_by only"
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "tests/test_deps.py#closure, blocked, and requester tests"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_wizard reads the platform from refresh and the questionary style table drops tag-* classes"
    verification:
      - kind: unit
        ref: "tests/test_app.py, tests/test_setup.py, tests/test_version_status.py#headless wizard call-site tests"
        status: pass
    human_judgment: false

duration: 95min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 28 Summary

**The install wrapper, dependency resolution, and wizard entry point each lost a redundant seam: one wrapper binds the sensitive-action confirmation, Resolution carries only plan rows, and run_wizard has a single platform source.**

## Performance

- **Duration:** ~95 min
- **Completed:** 2026-10-18
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Deleted the `Install` protocol and `with_sensitive_confirm`; `_with_force` is now the single install wrapper, binding `confirm_sensitive` and forcing `repair=True` for repair/reinstall rows.
- Slimmed `Resolution` to `closure`, `blocked` (`tool_id` + `needs`), and `requested_by`; removed `order`, `dragged_in`, `warnings`, the second topo sort, and per-blocked warning text while still raising `DependencyCycleError` on cycles.
- Dropped the `platform` parameter from `run_wizard` (always `refresh.platform`) and removed the unused `tag-*` classes from the questionary style table.

## Task Commits

Each task was committed atomically:

1. **Task 1: Collapse the install wrappers** - `da244d1` (refactor)
2. **Task 2: Slim resolve_dependencies** - `a2444b5` (refactor)
3. **Task 3: Drop run_wizard's platform parameter** - `fa2ea1b` (refactor)

**Plan metadata:** not present for this plan

## Files Created/Modified

- `installer/session.py` - single `_with_force` wrapper binding confirmation; `execute_plan` calls it directly
- `installer/deps.py` - slimmed `Resolution`/`Blocked`; one topo sort for the closure
- `installer/app.py` - `run_wizard` without the `platform` parameter
- `setup.py` - headless call site ported; unused `tag-*` style rows removed
- `tests/test_session.py`, `tests/test_deps.py`, `tests/test_registry.py`, `tests/test_catalog_tui.py`, `tests/test_app.py`, `tests/test_version_status.py`, `tests/test_docs.py` - ported to the new surfaces
- `.claude/architecture.md` - Phase 14 paragraph re-anchored to `SensitiveInstall`

## Deviations from Plan

None - plan executed as written. Expectation values in registry tests were re-anchored to the first selected requester recorded by the resolver (e.g. `requested_by["uv"] == "graphify"`), matching the slimmed contract.

## Issues Encountered

None beyond mechanical call-site porting; a scripted patch double-removed one prompter argument in `tests/test_version_status.py`, caught by the test run and fixed immediately.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The slimmer seams are stable: later execute-screen and render work builds on `closure`/`blocked`/`requested_by` and the single wrapper. No blockers.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
