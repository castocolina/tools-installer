---
phase: 17-stop-the-bleeding
plan: "21"
subsystem: testing
tags: [pyright, typeddict, test-hygiene, type-ignores, uninstall]

requires:
  - phase: 17-stop-the-bleeding
    provides: _uninstall_kwargs test helper (17-09) and its two suppression-covered splats (17-18, ad63b1f)
provides:
  - precisely typed _uninstall_kwargs helper (TypedDict matching run_uninstall's keywords)
  - six fewer type: ignore[arg-type] markers in tests/test_app.py
  - corrected 17-18 SUMMARY suppression-free claim
affects: [phase-18-data-fixes]

actuals:
  tokens: 8500
  tasks: 1
  commits: 2

tech-stack:
  added: []
  patterns:
    - "TypedDict helper return instead of dict[str, object] for keyword splats"

key-files:
  created: []
  modified:
    - tests/test_app.py
    - .planning/phases/17-stop-the-bleeding/17-18-SUMMARY.md

key-decisions:
  - "Type the helper with a total TypedDict (_UninstallKwargs) mirroring run_uninstall's keyword-only parameters exactly; pyright accepts the splats with no suppression"

patterns-established:
  - "TypedDict splat helpers: when a test helper builds kwargs for one function, return a TypedDict matching that function's parameters rather than dict[str, object] plus ignores"

requirements-completed: [SAFE-03, CI-01]

coverage:
  - id: D1
    description: "No type: ignore[arg-type] remains on any _uninstall_kwargs splat; pyright clean on tests/test_app.py"
    requirement: SAFE-03
    verification:
      - kind: other
        ref: "bash -c '! grep -nE \"_uninstall_kwargs\\(.*type: ignore\" tests/test_app.py && uv run pyright tests/test_app.py'"
        status: pass
    human_judgment: false
  - id: D2
    description: "tests/test_app.py passes unchanged in behavior (no test weakened, skipped or renamed)"
    requirement: CI-01
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_app.py -q --no-cov (128 passed)"
        status: pass
    human_judgment: false

duration: ~12min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 21 Summary

**Typed the `_uninstall_kwargs` test helper with a TypedDict matching `run_uninstall`'s keywords and removed all six `# type: ignore[arg-type]` markers, closing the last 17-VERIFICATION gap.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-10-14 (approx.)
- **Completed:** 2026-10-14
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added `_UninstallKwargs` TypedDict (total=True) whose keys/value types mirror `run_uninstall`'s keyword-only parameters (`installer/app.py:524`), returned by `_uninstall_kwargs` (`tests/test_app.py:~3463`)
- Deleted all six `# type: ignore[arg-type]` markers: four on the helper/splats from 17-09 (lines ~3492, 3521, 3538, 3560) and two from 17-18 commit ad63b1f (lines ~3584, 3617)
- Amended the 17-18 SUMMARY's "suppression-free" claim to name the fix (17-21, e63f983)

## Task Commits

1. **Task 1: type `_uninstall_kwargs` and remove its six arg-type ignores** - `e63f983` (test)

## Verify Results

- `! grep -nE "_uninstall_kwargs\(.*type: ignore" tests/test_app.py` → clean (exit 0)
- `uv run pyright tests/test_app.py` → 0 errors, 0 warnings
- `uv run pytest tests/test_app.py -q --no-cov` → 128 passed
- `make validate` → exit 0
- `make test` → 3572 passed, 4 skipped, coverage 95.96% (gate 90%)

## TDD Evidence

Task is type="auto" (no tdd="true"): the change is a typing refactor guarded by pyright and the existing suite; no new test was written, none weakened. RED phase not applicable — the verify gate (pyright clean + no ignore markers) fails on the pre-change tree and passes after it.

## Deviations from Plan

None — plan executed exactly as written. (The 17-18 SUMMARY note referenced "~lines 16 and 132"; the claim appears only at line 16 of the actual file and was fixed there.)

## Issues Encountered

- `make validate` initially failed on ruff import sorting after adding the `TweakBundle` / `TypedDict` imports; fixed by running `ruff check --fix` (import reordering only), then validate passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 17-VERIFICATION.md's suppression gap is closed; no product code changed and the full suite is green.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
