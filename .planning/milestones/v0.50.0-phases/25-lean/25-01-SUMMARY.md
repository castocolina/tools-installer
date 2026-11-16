---
phase: 25-lean
plan: "01"
subsystem: testing
tags: [ast, reachability, dead-code, import-graph, dispatch-tables, pytest]

# Dependency graph
requires:
  - phase: 24.5
    provides: the string-keyed dispatch tables (install_ownership probes and batches, post-install hooks, executors) that the guard must reach
provides:
  - tests/test_reachability.py, a permanent import-reachability guard run from setup.py and the Makefile entry modules
  - an inventory of the twelve string-keyed callable dispatch tables at HEAD, enforced by exact equality
affects: [25-02, 25-03, 25-04, 25-05, 25-06, 25-07, 25-08, 25-09, 25-10, 25-11]

# Actuals (#2632) — chars/4 over the realized diff, same scale as the plan estimate.
actuals:
  tokens: 3550
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AST NodeVisitor edge collector that skips TYPE_CHECKING bodies and resolves relative imports"
    - "Dispatch-table inventory: top-level Assign/AnnAssign names of each reachable module, filtered by runtime value (non-empty str-keyed dict with an installer callable)"
    - "Exemptions asserted live: the exempt directory exists, holds .py files, and no reachable module imports it"

key-files:
  created:
    - tests/test_reachability.py
  modified: []

key-decisions:
  - "Reachability is decided by the import graph, not by name grep. Function-level imports are edges; TYPE_CHECKING-only imports are not."
  - "A relative import that climbs above the top-level package raises AssertionError naming the file, so no ImportFrom is silently dropped."
  - "_DISPATCH_TABLES lists the twelve HEAD tables by name. The inventory test compares for exact equality, so an unlisted table or a stale entry fails by name."
  - "installer/helper_assets stays the one exemption and is asserted live and unimported. vulture remains the symbol-level check; pyproject [tool.vulture] is unchanged."

patterns-established:
  - "Guard tests that name the file and line of an unsupported construct instead of skipping it"
  - "Scratch-tree tests (tmp_path) for every graph rule, each paired with a real-tree test"

requirements-completed: [LEAN-01]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "Module-level reachability guard passes on the real tree (no installer module unreachable from setup.py or the entry modules)"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_every_installer_module_is_reachable_from_an_entry_point"
        status: pass
    human_judgment: false
  - id: D2
    description: "A seeded orphan module in a scratch tree is reported by name, so the guard is not vacuous"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_a_seeded_orphan_module_is_reported"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every python -m installer.<x> module named in the Makefile or install.sh is a discovered entry point, and both files launch setup.py"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_makefile_and_install_sh_name_only_discovered_entry_points"
        status: pass
    human_judgment: false
  - id: D4
    description: "Function-level imports count as edges, so a lazily imported module is reachable"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_a_function_level_import_is_an_edge"
        status: pass
    human_judgment: false
  - id: D5
    description: "Imports under if TYPE_CHECKING do not count as edges, so a typing-only module is reported"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_a_type_checking_only_import_is_not_an_edge"
        status: pass
    human_judgment: false
  - id: D6
    description: "Relative imports resolve against the importing package; one that climbs above the top-level package fails by name"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_a_relative_import_is_an_edge"
        status: pass
    human_judgment: false
  - id: D7
    description: "Every dispatch-table target that is an installer callable lives in a reachable module; a stale table entry fails"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_dispatch_table_targets_live_in_reachable_modules"
        status: pass
    human_judgment: false
  - id: D8
    description: "The string-keyed callable dispatch-table inventory equals the twelve listed tables; an unlisted table fails by name"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_every_string_keyed_callable_table_is_listed"
        status: pass
    human_judgment: false
  - id: D9
    description: "The installer/helper_assets exemption is live (directory and .py files exist) and no reachable module imports it"
    requirement: "LEAN-01"
    verification:
      - kind: unit
        ref: "tests/test_reachability.py#test_the_exemptions_are_live"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-11-15
status: complete
---

# Phase 25 Plan 01: Import-reachability guard from the production entry points Summary

**Permanent import-reachability guard: AST walk from setup.py and the Makefile entry modules, function-level imports counted, TYPE_CHECKING skipped, relative imports resolved, and the twelve string-keyed dispatch tables listed by name**

## Performance

- **Duration:** 8 min (approximate: from the plan-start ledger write to the SUMMARY write)
- **Started:** 2026-11-15T22:07:33Z (approximate, ledger mtime)
- **Completed:** 2026-11-15T22:15:53Z
- **Tasks:** 2
- **Files modified:** 1 (new file)

## Accomplishments

- `tests/test_reachability.py` builds the module graph by AST from `setup.py`, every `installer/` module with a top-level `if __name__ == "__main__"` guard, and `installer/__main__.py` when present. It reports any `installer/` module that no entry point reaches. At HEAD the real tree has zero unreachable modules, so the guard is a regression guard that protects every later Phase 25 deletion.
- Function-level imports are edges. Imports under `if TYPE_CHECKING:` are not, but their `else:` branch is.
- Relative imports (`from . import x`, `from .x import y`, `from .. import x`) resolve against the importing package. A relative import that climbs above the top-level package raises `AssertionError` naming the file.
- `_DISPATCH_TABLES` lists the twelve string-keyed callable tables at HEAD. The inventory test derives the set from each reachable module's own top-level assignments and runtime values, and asserts exact equality with the list. The dispatch test checks that every installer callable target of each table lives in a reachable module.
- `installer/helper_assets` is asserted live (the directory exists and holds `.py` files) and unimported by every reachable module.
- The inventory at HEAD matches the plan exactly: twelve tables, no extras. `install_ownership._PATH_ANSWERS` is keyed by tuples, so the all-`str` rule excludes it. `host_setup.HOST_SETUPS` (`str`-keyed, dataclass values) has no installer callable in its values, so it is excluded too.

## Task Commits

Each task was committed atomically:

1. **Task 1: reachability guard from the entry points, with a seeded orphan** - `203d1584` (test)
2. **Task 2: lazy and relative imports count, typing-only imports do not, dispatch tables listed** - `b07217bb` (test)

**Plan metadata:** recorded in the SUMMARY commit that follows this file (docs: complete plan). STATE.md and ROADMAP.md were not modified (orchestrator-owned in parallel mode).

## TDD Gate Compliance

- RED evidence was produced before GREEN for both tasks (see "RED runs" below). The RED runs used temporary stubs or temporarily broken visitors in the working copy; none of those edits were committed.
- Both tasks changed only `tests/test_reachability.py`, which is test-only, so the plan's rule "one commit per task; the RED run is pasted in the SUMMARY, never committed alone" applies. Each commit carries the test and its implementation together. The reference commit pattern (`test(...)` then `feat(...)`) therefore does not apply to this plan: `git log --grep="^feat\(25-01\):"` finds no `feat` commit, and this is the expected shape for a test-only guard, not a skipped GREEN.

### RED runs

- **Task 1 (stubs):** `_unreachable_modules`, `_entry_modules` and `_python_m_modules` were stubbed to return nothing. Result: 2 failed, 1 passed.
  - `test_a_seeded_orphan_module_is_reported`: `assert [] == ['installer.orphan']`.
  - `test_makefile_and_install_sh_name_only_discovered_entry_points`: `the Makefile names no installer entry module` (the non-empty assertion is the non-vacuity check added in deviation 1).
  - `test_every_installer_module_is_reachable_from_an_entry_point` passes on the stub, as the plan anticipated: it is a guard against the real tree, not a RED test.
  - Output: `.../scratchpad/p25-01-task1-red.txt`.
- **Task 2, visitor ignoring relative imports (level > 0):** `test_a_relative_import_is_an_edge` failed with `assert ['installer.o...ller.sibling'] == []`, reporting `installer.other` and `installer.sibling` as unreachable. The function-level, TYPE_CHECKING and dispatch tests were already green at this point. Output: `.../scratchpad/p25-01-task2-red-ignore-level.txt`.
- **Task 2, visitor not skipping TYPE_CHECKING bodies:** `test_a_type_checking_only_import_is_not_an_edge` failed with `assert [] == ['installer.typing_only']`. The real file was restored byte-identical afterwards (`cmp` confirmed). Output: `.../scratchpad/p25-01-task2-red-no-typechecking-skip.txt`.

### Additional mutation checks (inventory and dispatch tests)

- Removing the `POSTINSTALL_HOOKS` row from `_DISPATCH_TABLES` (an unlisted table): `test_every_string_keyed_callable_table_is_listed` fails.
- Pointing a row at a missing attribute (a stale entry): `test_dispatch_table_targets_live_in_reachable_modules` fails.
- Both mutations were applied to a scratch copy and the committed file was restored; `git status` was clean afterwards.

## Files Created/Modified

- `tests/test_reachability.py` - new: the import graph walk (`_EdgeCollector`, `_absolute_module`, `_reachable_modules`, `_unreachable_modules`), entry discovery (`_entry_points`, `_entry_modules`, `_has_main_guard`), the dispatch-table inventory (`_DISPATCH_TABLES`, `_callables`, `_is_callable_table`, `_top_level_assigned`), the Makefile/install.sh entry check (`_python_m_modules`), and nine tests.

## Decisions Made

- Reachability is decided by the import graph (AST), not by name grep. Dispatch-table targets are plain callables imported by the table's own module, so the graph already reaches them; the dispatch test proves it rather than relying on the graph to model dynamic dispatch.
- A relative import above the top-level package fails by name. Dropping it silently would weaken the guard, so the guard refuses to guess.
- The dispatch-table inventory is an exact-equality check, not a subset check. A new table that holds installer callables must be added to `_DISPATCH_TABLES` in the same commit, and a removed table must be dropped from it.
- `vulture` stays the symbol-level check; `pyproject.toml` `[tool.vulture]` is unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Non-empty assertion on the Makefile entry-module set**
- **Found during:** Task 1 (RED run against the stubbed helper)
- **Issue:** `test_makefile_and_install_sh_name_only_discovered_entry_points` iterates the names found in the Makefile and install.sh. If the regex found nothing, every loop would pass vacuously.
- **Fix:** Added `assert named, "the Makefile names no installer entry module"`. The RED run showed the test failing for the right reason against the stub.
- **Files modified:** `tests/test_reachability.py`
- **Verification:** The RED run failed on this assertion; the GREEN run passes with `verify_registry` and `catalog_audit` discovered.
- **Committed in:** `203d1584` (Task 1)

**Total deviations:** 1 auto-fixed (1 missing critical, a non-vacuity check on a test). **Impact:** None on the plan's behaviour or scope.

## Issues Encountered

- `PLAN_START_TIME` was not recorded at the start of execution. The duration above is approximated from the plan-start ledger write (`gsd-plan-head-before-25-01`, mtime 2026-11-15 22:07:33 UTC).
- The worktree had no `.venv`, so `make install` (uv sync inside the worktree) ran before the first gate.
- The plan's `requirements-completed` field copies `LEAN-01` as the template requires. `gsd_run query requirements.ready-ids ... LEAN-01` reports `LEAN-01` as blocked, because sibling plans in phase 25 also declare it and have no SUMMARY yet. `REQUIREMENTS.md` was therefore not updated in this plan.

## Known Stubs

None. The three stubs used for the RED run were temporary working-copy edits and are not in either commit.

## Threat Flags

None. The change adds a test file that reads repository files and writes only under `tmp_path`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Every later Phase 25 deletion plan runs this guard in `make test`. A deletion that orphans an `installer/` module, or that removes a module something still imports, fails here.
- A later plan that deletes a dispatch table must remove its `_DISPATCH_TABLES` row in the same commit, or the inventory test fails. Plan 25-02 removes only the `"host-setup"` key of `install_ownership._PROBES`; the table stays listed.
- This test supplies the reachability check that the SPEC's LEAN-01 acceptance names. It does not by itself produce the deletion list: the phase-level summary still owes each kept target with its caller.

## Self-Check: PASSED

- `tests/test_reachability.py` exists.
- Task commits `203d1584` and `b07217bb` are ancestors of HEAD.
- `make validate` exit 0 and `make test` exit 0 (7688 passed, 6 skipped, coverage 96.09%) on the Task 2 tree; the SUMMARY commit changes no code.
- The worktree is clean apart from this SUMMARY before its commit.

---
*Phase: 25-lean*
*Completed: 2026-11-15*
