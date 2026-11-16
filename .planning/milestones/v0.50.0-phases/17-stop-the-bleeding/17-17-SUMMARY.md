---
phase: 17-stop-the-bleeding
plan: "17"
subsystem: ui
tags: [rich, console, rendering, uninstall, ci, macos]

# Dependency graph
requires:
  - phase: 17-stop-the-bleeding
    provides: 17-09's strict removable/unproven classification that feeds render_remove_yourself
provides:
  - "render_uninstall and render_remove_yourself print each path on one unbroken, markup-free line at any console width"
  - "Regression test pinning unwrapped, literal path output on both functions"
affects: [19-receipts, 22-native-handoff, ci-oracle]

# Actuals
actuals:
  tokens: 3300
  tasks: 1
  commits: 1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rich soft_wrap=True + markup=False for any output line the user must copy verbatim"

key-files:
  created: []
  modified:
    - installer/render.py
    - tests/test_render.py

key-decisions:
  - "Per-path print uses soft_wrap=True, markup=False exactly as the plan specifies; heading lines untouched, callers untouched"

patterns-established:
  - "Copyable path listing: console.print(path, soft_wrap=True, markup=False) — never let Rich wrap or parse user-facing paths"

requirements-completed: [CI-01, SAFE-03]

coverage:
  - id: D1
    description: "Uninstall and remove-yourself path lines print unwrapped and markup-literal at any console width"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "tests/test_render.py#test_uninstall_path_lines_print_unwrapped_and_literal"
        status: pass
    human_judgment: false
  - id: D2
    description: "Unproven matches are listed as copyable paths, never deleted (SAFE-03/D-04 listing path intact)"
    requirement: SAFE-03
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_render.py tests/test_app.py -k 'uninstall or remove_yourself'"
        status: pass
    human_judgment: false

# Metrics
duration: 14min
completed: 2026-10-14
status: complete
---

# Phase 17, Plan 17: Stop the bleeding Summary

**Uninstall and remove-yourself path listings print every path on one unbroken, markup-free line (soft_wrap + markup=False), fixing the macOS CI oracle wrap failure**

## Performance

- **Duration:** 14 min
- **Completed:** 2026-10-14
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `installer/render.py` `render_uninstall` and `render_remove_yourself` now print each path with `soft_wrap=True, markup=False`, so a long `/private/var/folders/...` pytest path is never split mid-name and a path containing `[bold]` prints literally. Heading lines and callers untouched.
- New parametrized regression test `test_uninstall_path_lines_print_unwrapped_and_literal` pins the behavior on both functions with a width-40 console, a >40-char path, and a `[bold]` directory name.

## Task Commits

1. **Task 1: uninstall path lines are never wrapped or markup-parsed** - `73067f2` (fix)

## TDD RED evidence

Before the fix, the new test failed on both params (paths wrapped at width 40):

```
>       assert str(long_path) in text
E       AssertionError: assert '/tmp/pytest-of-bazzite/.../aaaa...aaaa/bin/ruff' in
'Not removed (tools-installer cannot \nprove it installed these); ... \n  /tm...aaaaaaaaaaaaa\naaaaaaaa/bin/ruff\n ...'
FAILED ...::test_uninstall_path_lines_print_unwrapped_and_literal[render_uninstall]
FAILED ...::test_uninstall_path_lines_print_unwrapped_and_literal[render_remove_yourself]
```

After the fix: both params pass; the two macOS-failing tests in `tests/test_app.py` pass unchanged (not modified, not skipped, not platform-gated).

## Verify Results

- `uv run pytest tests/test_render.py tests/test_app.py -q --no-cov -k "uninstall or remove_yourself"` — 43 passed
- `grep -c 'soft_wrap=True, markup=False' installer/render.py` — 2
- `git diff --stat` of the task commit lists only `installer/render.py` and `tests/test_render.py` (prohibition satisfied)
- `make validate` — all checks passed
- `make test` — 3543 passed, 4 skipped, coverage 95.91% (gate 90%)

## Files Created/Modified
- `installer/render.py` - both uninstall listings print each path with `soft_wrap=True, markup=False`
- `tests/test_render.py` - parametrized unwrapped/literal regression test; added `pytest`, `Callable`, `render_uninstall`, `render_remove_yourself` imports

## Decisions Made
- None beyond the plan - followed it exactly, including the exact `soft_wrap=True, markup=False` fix.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- The macOS final-tree CI oracle (17-13 Task 1) can be re-run by the orchestrator on this HEAD; both previously failing tests pass locally with an unchanged test file.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
