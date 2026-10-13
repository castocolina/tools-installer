---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 19
subsystem: detection
tags: [doctor, rcclean, guidance, wizard-tui, path-writers]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: IN-02 one-shot PATH prefix detection, Doctor enter hints, and post-apply guidance from plans 16-17/16-18
provides:
  - export PATH lines with extra shell words are persistent writers again (not hidden, not strip candidates)
  - shared GUARD_ENTER_HINT and SAFE_FIX_ENTER_HINT constants in guidance.py
  - post-apply Doctor next_step text without Press enter or double periods
affects: [doctor, foreign-path-lines, rcclean]

actuals:
  tokens: 4200
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - "One-shot PATH prefix skip applies only when the assignment is not an export line"
    - "Post-apply Doctor rewrites use ordered (old, new) pairs from shared enter-hint constants"

key-files:
  created: []
  modified:
    - installer/rcclean.py
    - installer/guidance.py
    - installer/wizard_app.py
    - tests/test_rcclean.py
    - tests/test_wizard_app.py

key-decisions:
  - "Quoted export PATH with trailing assignments stays a documented no-record limit (quote-blind colon split)"
  - "NR-03 second heredoc on one line accepted; no code change"

patterns-established:
  - "Enter-hint literals live only in installer/guidance.py as public constants"

requirements-completed: [D-21, D-22, D-23, D-24]

coverage:
  - id: D1
    description: "export PATH=/m/bin:$PATH FOO=1 is reported, not guardable, compound refusal, not a strip candidate"
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_export_path_with_extra_assignments_is_a_persistent_writer"
        status: pass
    human_judgment: false
  - id: D2
    description: "Enter-hint literals exist once in guidance.py; CLI and pre-apply TUI bytes unchanged"
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_guidance.py"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "After Doctor apply, next_step strings are clean for guard, block-owner, and make-fix items"
    requirement: D-22
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_doctor_drops_inert_enter_hint_after_apply"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 19 Summary

**Gap closure for 16-REVIEW-2: compound export PATH writers visible again, shared enter hints, and post-apply Doctor copy that matches what apply actually did**

## Performance

- **Duration:** ~25 min
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments

- NR-02: `export PATH=... FOO=1` is a persistent writer again (`simple=False`, `_REFUSE_COMPOUND`, not in `find_duplicate_path_lines`); one-shot non-export forms unchanged.
- NR-04: `GUARD_ENTER_HINT` and `SAFE_FIX_ENTER_HINT` defined once in `guidance.py`; wizard imports them for TUI pre-apply text.
- NR-01 / IN-12: ordered post-apply rewrites produce full sentences without `Press enter` or `..`.
- NR-03: accepted (existing `shortcut:` on heredoc tracking); no code.

## Task Commits

1. **Task 1: NR-02 export PATH with extra words** — `a3e2cec` (fix)
2. **Task 2: NR-04 shared enter hints** — `d948594` (refactor)
3. **Task 3: NR-01 post-apply sentences** — `b2470e9` (fix)
4. **Task 4: format gate** — `b53e474` (style)

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

- `make test` reported **4 failures** in `tests/test_app.py` (configure_path exact stdout and two doctor CLI string asserts). Failures are from Rich soft-wrapping long lines (`pip: \nblocked`, path split across lines) with `Console(width=100)` / long `tmp_path` segments. These files were not changed in plan 16-19; targeted plan pytest and `make validate` both pass.

## Verification (observed)

- `uv run pytest tests/test_rcclean.py -q -k extra_assignments`: RED on first new test (0 records), then green after fix.
- `uv run pytest tests/test_wizard_app.py -q -k doctor_drops_inert`: RED (`..` in after text), then green after `_POST_APPLY_REWRITES`.
- `uv run pytest tests/test_rcclean.py tests/test_guidance.py tests/test_wizard_app.py -q`: exit 0.
- `make validate`: exit 0.
- `make test`: **4 failed**, 3454 passed, 5 skipped in 333.84s (see Issues).

## Self-check (plan must_haves)

| Truth | Met |
|-------|-----|
| NR-02 RED then fix; quoted limit pinned | Yes |
| NR-04 literals once in guidance.py | Yes (`rg` on installer) |
| NR-01 full post-apply strings; no Press enter after apply | Yes |
| NR-03 skipped / accepted | Yes |
| Sandboxed tests only | Yes |
| IN-12 disposition row updated by orchestrator | N/A (executor) |

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
