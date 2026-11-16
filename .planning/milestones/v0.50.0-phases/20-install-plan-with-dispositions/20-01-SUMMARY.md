---
phase: 20-install-plan-with-dispositions
plan: "01"
subsystem: installer
tags: [dependency-resolution, topological-sort, install-plan, python]

requires: []
provides:
  - "Resolution.closure: deps-first order of every non-blocked tool, present tools included, from the same topo sort as order"
  - "Resolution.requested_by: dependency id -> first selected tool whose closure reached it"
  - "Resolution.blocked: one Blocked(tool_id, needs, reason) row per blocked tool"
affects: [20-04 build_plan, 20-06 render_plan]

tech-stack:
  added: []
  patterns:
    - "one topological sort function (topo) called twice rather than a second sort"

key-files:
  created: []
  modified:
    - installer/deps.py
    - tests/test_deps.py

key-decisions:
  - "closure is produced by the same nested topo() as order, called on the non-blocked set (no second sort)"
  - "requested_by records the first selected root per dependency via setdefault, dependencies only (never a selected tool)"
  - "Blocked.needs is the first blocking dependency id, None when the tool itself is unavailable and not installed"
  - "Blocked.reason reuses the two existing warning literals verbatim; warnings are unchanged"
  - "requested_by is typed Mapping[str, str] with default_factory=dict[str, str] (pyright strict rejected a bare dict factory)"

patterns-established:
  - "Resolution stays a pure, defaulted-field dataclass; new facts are added as defaulted fields only"

requirements-completed: [PLAN-01]

duration: unknown (not measured)
completed: 2026-10-17
---

# Phase 20 Plan 01: Resolution closure, requested_by and blocked data

**`Resolution` now exposes present-tool position (`closure`), the first requester of each dragged-in dependency (`requested_by`) and blocked tools as data (`blocked`), while `order`, `dragged_in` and `warnings` are unchanged.**

## Tasks

| # | Task | Commit | TDD |
|---|------|--------|-----|
| 1 | `Resolution.closure` keeps present tools deps-first | `8fc5b75` | RED then GREEN |
| 2 | `requested_by` (first requester) and `blocked` (needs + reason) | `74f0802` | RED then GREEN |

## TDD evidence

Task 1 RED (`uv run pytest tests/test_deps.py -q --no-cov -k closure`):

```
E       AttributeError: 'Resolution' object has no attribute 'closure'
tests/test_deps.py:267: AttributeError
FAILED tests/test_deps.py::test_closure_keeps_present_tools_deps_first - Attr...
FAILED tests/test_deps.py::test_closure_excludes_blocked_tools_and_keeps_selected_order
```

Task 2 RED (`uv run pytest tests/test_deps.py -q --no-cov -k "requested_by or blocked"`):

```
E       AttributeError: 'Resolution' object has no attribute 'requested_by'
E       AttributeError: 'Resolution' object has no attribute 'blocked'
FAILED tests/test_deps.py::test_requested_by_names_the_first_selected_requester
FAILED tests/test_deps.py::test_requested_by_follows_a_chain_to_the_selected_root
FAILED tests/test_deps.py::test_requested_by_never_lists_a_selected_tool
FAILED tests/test_deps.py::test_blocked_carries_needs_and_the_warning_text
FAILED tests/test_deps.py::test_blocked_needs_is_the_first_blocking_dependency
5 failed, 1 passed, 25 deselected
```

Task 1's cycle test (`test_closure_raises_on_a_cycle`) was already green before implementation because `order` already raised `DependencyCycleError`. It is a regression guard for the new `closure` path, not a RED test.

## Verification

- `uv run pytest tests/test_deps.py --no-cov`: 31 passed (23 existing unchanged + 8 new).
- `make validate`: exit 0 on the final tree of each commit.
- `make test`: 4649 passed, 4 skipped, coverage 95.99% (floor 90%), exit 0 on the tree of commit `74f0802`.
- Suppression count (`type: ignore|pyright: ignore|noqa|nosec`) in installer/tests/setup.py: 482 before, 482 after.
- `installer/deps.py` 184 -> 227 lines, `tests/test_deps.py` 260 -> 331 lines; both far below the large-file threshold and diffs contain only the intended hunks.

## Deviations from plan

- `requested_by` uses `field(default_factory=dict[str, str])` rather than `field(default_factory=dict)`. The plan's bare `dict` factory made `make validate` fail with a pyright strict "partially unknown" error. The explicit type fixes it without a suppression. Field type and behavior are as specified.
- Task 1's `topo` nested helper is named `_place` as the plan requires; the `visit` name is absent.
- The RED for Task 2 was first written with an unused variable and a meaningless `assert a is not None`. I rewrote that test before running GREEN, so the committed test is clean and the RED evidence above is from the rewritten test.

## Issues for the orchestrator

- `.planning/config.json` is modified and uncommitted, as expected. Not staged.
- An untracked `.planning/phases/20-install-plan-with-dispositions/20-REUSE.md` exists that this executor did not create. Not staged, not touched.
