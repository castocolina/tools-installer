---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "42"
subsystem: testing
tags: [python, json, skill-lifecycle, robustness]

# Dependency graph
requires: []
provides:
  - "Corrupt skill lock JSON, including deep nesting and invalid UTF-8, returns unknown rather than escaping the skill probe."
affects: [skill-lifecycle, version-status]

# Actuals (#2632)
actuals:
  tokens: 540
  tasks: 1
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Parse capped JSON bytes in one json.loads call and treat ValueError or RecursionError as unknown."

key-files:
  created: []
  modified:
    - installer/skill_lifecycle.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "Aligned _skills_lock_skills with _installed_project_paths: parse bytes directly and catch (ValueError, RecursionError)."

patterns-established:
  - "Malformed, undecodable, or excessively nested skill lock JSON is an unknown probe result."

requirements-completed: [STATE-07]
coverage:
  - id: D1
    description: "Deeply nested and invalid UTF-8 skill locks settle the harness state as unknown."
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_skills_lock_deep_nesting_or_bad_bytes_is_unknown"
        status: pass
      - kind: other
        ref: "make validate && make test"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-10-17
status: complete
---

# Phase 19: One Tool State with Health Plus Receipts Summary

**Capped skill lock JSON is parsed safely so deeply nested or invalid UTF-8 data settles as unknown instead of killing the skill probe.**

## Performance

- **Duration:** approximately 20 minutes
- **Started:** Not recorded precisely
- **Completed:** 2026-10-17
- **Tasks:** 1
- **Files modified:** 2 implementation/test files (plus this summary)

## Accomplishments

- Changed `_skills_lock_skills` to parse capped bytes directly with one `json.loads` call and catch `(ValueError, RecursionError)`.
- Added parameterized coverage for deeply nested JSON and invalid UTF-8, asserting the harness state is `unknown`.
- Verified the touched suite, lint/type/security/dead-code/shell validation, and full test suite.

## Task Commits

1. **Task 1: A deeply nested or undecodable skill lock is unknown, never a crash** - `6be6432` (`fix(19-42): a corrupt skill lock is unknown, never a dead skill worker`)

**Plan summary:** recorded separately in the summary-only commit after verification.

## Files Created/Modified

- `installer/skill_lifecycle.py` - Parse capped lock bytes and return unknown for malformed, undecodable, or deeply nested JSON.
- `tests/test_skill_lifecycle.py` - Verify deeply nested and invalid-byte lock files produce an unknown state.
- `.planning/phases/19-one-tool-state-with-health-plus-receipts/19-42-SUMMARY.md` - Execution record, RED evidence, and verification results.

## Decisions Made

- Followed the existing `_installed_project_paths` reader pattern: pass bytes directly to `json.loads` and treat `ValueError` and `RecursionError` as an unknown result.

## Deviations from Plan

- `ruff format` requested formatting for the newly added test; the test file was formatted before validation and commit. No behavior or scope deviation.

**Total deviations:** 1 formatting adjustment.
**Impact on plan:** None; formatted output follows repository rules.

## Issues Encountered

- The first RED test command's output was dominated by pytest's enormous parametrized ID for the repeated-bracket payload. Added explicit short parameter IDs and reran; the deep-nesting case then failed as expected with `RecursionError` escaping from `json.loads`.
- Initial `make validate` found the added test needed Ruff formatting. Formatted the test and reran validation successfully.

## TDD Evidence

**RED command:** `uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "deep_nesting_or_bad_bytes"`

**Observed before implementation:** one failure, `test_skills_lock_deep_nesting_or_bad_bytes_is_unknown[deep-nesting]`, with `RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string`. The malformed lock escaped the probe as predicted. The invalid-byte case did not fail because the old manual UTF-8 decode already returned unknown.

**GREEN:** `uv run pytest tests/test_skill_lifecycle.py -q --no-cov` passed (200 tests). `uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "skills_lock"` passed (11 tests).

## Verification

- `make validate` — passed (Ruff, formatting, Pyright, Bandit, Vulture, ShellCheck).
- `make test` — passed: **4627 passed, 4 skipped**, coverage 95.98%.
- Plan acceptance checks — passed: both JSON readers use `except (ValueError, RecursionError)`; no JSONDecodeError-only catch or manual UTF-8 decode remains in the module; suppression and test-file truncation guards passed.
- `git diff --check` — passed for the task commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

STATE-07 corrupt-lock handling is implemented and verified. No blockers identified.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
