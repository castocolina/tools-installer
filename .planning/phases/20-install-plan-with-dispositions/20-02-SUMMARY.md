---
phase: 20-install-plan-with-dispositions
plan: "02"
subsystem: ui
tags: [update, refusal, ownership, catalog, tui, copy, pure-core]

# Dependency graph
requires:
  - phase: 19-one-tool-state-health-and-receipts
    provides: ManagerOwnership, MUTATION_GRADE, UNMANAGEABLE_OWNERS, owner_label and declared_manager_label
provides:
  - update_refusal(tool, ownership) -> UpdateOutcome | None, the single pre-flight update refusal
  - PLAN-08 off-policy copy that states the owners and promises no migration
affects: [20-05 build_plan (consumes update_refusal for UPDATE vs SKIP), 20-03, 20-04, phase 20 review copy]

# Actuals
actuals:
  tokens: n/a
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One refusal predicate: _perform and (later) the review call the same update_refusal, so they cannot disagree"
    - "Grep guard test pins absence of a forbidden UI promise under installer/"

key-files:
  created: []
  modified:
    - installer/update.py
    - installer/catalog_tui.py
    - tests/test_update.py
    - tests/test_catalog_tui.py

key-decisions:
  - "update_refusal returns the full UpdateOutcome (status, owner, detail), not a bare string, so _perform keeps unknown-owner and unsupported distinct"
  - "The pnpm host-setup refusal moved into update_refusal; _perform's pnpm branch keeps only executors.execute"
  - "PLAN-08 texts use the 20-UI-SPEC Copywriting Contract wording; the unknown-declared catalog case is not pinned (see deviations)"

patterns-established:
  - "Refusal parity: the test asserts literal status/owner/detail captured from the pre-refactor branches, never by calling the function under test to compute its own expectation"

requirements-completed: [PLAN-08]  # PLAN-03 stays open: update_refusal is its input, the disposition mapping lands in 20-05

coverage:
  - id: D1
    description: "update_refusal returns the exact pre-refactor refusal for every pre-flight branch and None for an updatable owner"
    requirement: "PLAN-08"
    verification:
      - kind: unit
        ref: "tests/test_update.py::test_update_refusal_matches_perform_for_every_refusal (8 cases) + test_update_refusal_is_none_for_an_updatable_owner"
        status: pass
  - id: D2
    description: "No 'moving it there' promise anywhere under installer/"
    requirement: "PLAN-08"
    verification:
      - kind: unit
        ref: "tests/test_update.py::test_no_migration_promise_anywhere_under_installer"
        status: pass
  - id: D3
    description: "Off-policy update detail and catalog u line name both owners and carry no migration clause"
    requirement: "PLAN-08"
    verification:
      - kind: unit
        ref: "tests/test_update.py::test_off_policy_brew_update_names_the_declared_manager; tests/test_catalog_tui.py::test_update_on_current_off_policy_tool_explains_and_does_not_begin; tests/test_catalog_tui.py::test_update_on_stale_current_off_policy_keeps_the_tail"
        status: pass

duration: n/a
completed: 2026-10-17
status: complete
---

# Phase 20 Plan 02: one update_refusal predicate and the PLAN-08 copy

**The engine's pre-flight update refusals now come from one `update_refusal` predicate, and the two off-policy strings state the owners without promising a migration.**

## Tasks and commits

| Task | Commit | Result |
|---|---|---|
| 1. `update_refusal` is the one pre-flight gate `_perform` answers with (tdd) | `7d1034b` refactor(20-02) | Refusal branches moved verbatim into `update_refusal`; `_perform` delegates first |
| 2. No migration promise anywhere under `installer/` (PLAN-08, tdd) | `3577fa7` fix(20-02) | Both strings reworded; grep guard added; three pins updated |

## What was built

**Task 1.** `installer/update.py` gained `update_refusal(tool, ownership) -> UpdateOutcome | None`. It holds, in the original order: the unknown-owner / non-`MUTATION_GRADE` refusal, the sdkman refusal, the `UNMANAGEABLE_OWNERS` (native and os-package) refusal, the volta refusal, and the pnpm host-setup refusal (no node method, `pnpm_add_command` hint). `_perform` now calls it first and returns the result unchanged; its pnpm branch keeps only `executors.execute`. Pure refactor: no behaviour change.

**Task 2.** The two strings that promised "moving it there is not available yet" now state only the fact:
- `update.py` detail: `{real} owns this copy; the catalog installs {tool_id} via {declared}, so it was updated through {real}`
- `catalog_tui.py` u line: ` — {real} owns this copy; the catalog installs it via {declared}`

The `declared`/`real` computation and the guards are untouched.

## TDD RED evidence

Task 1 (`uv run pytest tests/test_update.py -q --no-cov -k update_refusal`), RED before implementation:
```
ERROR collecting tests/test_update.py
E   ImportError: cannot import name 'update_refusal' from 'installer.update'
Interrupted: 1 error during collection
```

Task 2 (`-k "promise or off_policy"`), RED before the source edits:
```
FAILED tests/test_update.py::test_off_policy_brew_update_names_the_declared_manager
FAILED tests/test_update.py::test_no_migration_promise_anywhere_under_installer
FAILED tests/test_catalog_tui.py::test_update_on_current_off_policy_tool_explains_and_does_not_begin
FAILED tests/test_catalog_tui.py::test_update_on_stale_current_off_policy_keeps_the_tail
E   AssertionError: assert ['catalog_tui..., 'update.py'] == []
```

Refusal literals were captured by running the pre-refactor `perform_update` on each branch before the refactor, so the parity test asserts those values, not the new function's own output.

## Verify results

- `update_refusal` tests: 9 PASSED (8 parametrized refusal cases + 1 updatable case); the plan requires at least 8.
- `uv run pytest tests/test_update.py tests/test_catalog_tui.py -n auto` green.
- `grep -rl "moving it there" installer/ --include=*.py` → none.
- `grep -vE '^\s*#' installer/update.py | grep -c 'status="unknown-owner"'` → 2; `status="unsupported"` → 5 (same counts as before, the refusals moved rather than multiplied).
- `make validate` → exit 0 (both commits; pre-commit hook passed on each).
- `make test` → exit 0; 4659 passed, 4 skipped, coverage 95.99% (gate 90%).
- Suppression markers (`type: ignore|pyright: ignore|noqa|nosec`) across `installer/`, `setup.py`, `tests/`: 482 before, 482 after. No new suppressions.

## File sizes and diff stat (large test files)

| File | HEAD (before plan) | After | `git diff --stat` at HEAD~2 → HEAD |
|---|---|---|---|
| tests/test_catalog_tui.py | 4935 lines | 4934 lines | 5 lines changed (2 pins, 1 wording) |
| tests/test_update.py | 1544 lines | 1665 lines | 125 insertions, 5 deletions (refusal table, grep guard, pin) |
| installer/update.py | 578 lines | 591 lines | refactor hunks only |
| installer/catalog_tui.py | 920 lines | 917 lines | 5 lines changed |

`ruff format` reformatted only files this plan touches, and each diff was checked to contain only the intended hunks.

## Deviations from the plan

1. **Unknown-declared catalog case not pinned (Task 2 `behavior`, 4th bullet).** The plan required `test_u_on_an_off_policy_row_with_unknown_declared_manager_names_only_the_real_owner`. I wrote it, but every route to the highlighted row in this file either patches the private `_browser` / `status` attributes (which needs `type: ignore` markers, and the rules forbid adding any) or needs a full pilot app. I removed the test rather than add suppressions. The guard it would pin, `if declared is not None and real is not None`, is unchanged code. **Coverage gap:** the no-clause path for an unknown declared manager is not directly pinned by a test. The orchestrator should decide whether a pilot-based test is worth adding in a later plan.
2. **pnpm guard is not an assert.** The plan said "assert-free" for the `method is None` guard in `_perform`'s pnpm branch. Pyright needs `method` narrowed before `executors.execute`, so I raise `UpdateError` there. It is unreachable because `update_refusal` answers that case first.
3. **Docstring scope.** The `update_refusal` docstring describes the review as the consumer of the predicate. `session.build_plan` does not call it yet (that is plan 20-05), so the docstring says the review "consults" it as the plan intends and not as a present fact.
4. **Task 1 `ruff format`.** Formatting changed the test table and the `update.py` pnpm branch; the diff was checked and contains only intended hunks.

## Issues the orchestrator must know

- **PLAN-03 is not satisfied by this plan.** `update_refusal` is the input 20-05 needs for UPDATE vs SKIP; the broken/misconfigured/outdated disposition mapping is not in this plan. Left open in `requirements-completed`.
- `installer/update.py` line 340 (off-policy detail) and the test pins use the wording from 20-UI-SPEC verbatim, with the catalog line now lacking the `, and moving it there…` clause. The UI-SPEC copy row for the update detail says `so it was updated through {real}`; that matches.
- `.planning/config.json` (orchestrator-owned) and `.planning/phases/20-install-plan-with-dispositions/20-REUSE.md` are untouched and unstaged, as required.
- A separate pre-existing finding noted while reading: `installer/version_status.py:805` contains `owns this copy; the catalog's policy installs {tool.id} via {declared}` (no migration clause). Not in this plan's scope; it does not promise a migration.
