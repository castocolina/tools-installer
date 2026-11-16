---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "41"
subsystem: installer
tags: [python, PATH, pnpm, shims, resolved-paths]
requires: []
provides:
  - Redirect shim look-through and retry matching are resilient to symlinked PATH spellings and trailing slashes.
affects: [STATE-04, installer/guards.py]
actuals:
  tokens: 900
  tasks: 1
  commits: 2
tech-stack:
  added: []
  patterns:
    - Compare filesystem directory identity with pathlib.Path.resolve() while preserving the PATH-spelled real binary as the result.
key-files:
  created: []
  modified:
    - installer/guards.py
    - tests/test_guards.py
key-decisions:
  - "Resolved comparisons are used for recognizing the managed directory; the returned executable path retains PATH's spelling."
patterns-established:
  - "Managed PATH entries are filtered by resolved directory identity, not textual equality."
requirements-completed: [STATE-04]
coverage:
  - id: D1
    description: Resolve real binaries behind redirect shims even when PATH uses a symlink alias or trailing slash.
    requirement: STATE-04
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_look_through_shim_matches_the_shim_dir_by_resolved_path
        status: pass
      - kind: unit
        ref: tests/test_guards.py#test_real_binary_drops_every_spelling_of_the_managed_dir
        status: pass
      - kind: other
        ref: make validate && make test
        status: pass
    human_judgment: false
duration: 8min
completed: 2026-10-17
status: complete
---

# Phase 19: Plan 41 Summary

**Redirect shim recognition now follows resolved directory identity across symlinked and trailing-slash PATH entries.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-17T01:25
- **Completed:** 2026-10-17T01:33
- **Tasks:** 1
- **Files modified:** 2 implementation/test files (plus this summary)

## Accomplishments

- Updated `look_through_shim` to compare resolved parent and managed-bin paths, while returning the original PATH-spelled hit when it is not a managed shim.
- Updated `real_binary` retry filtering to remove all PATH entries resolving to the managed directory.
- Added alias/trailing-slash regression coverage for both code paths.

## Task Commits

1. **Task 1: the shim look-through compares resolved paths (J6: IN3-02)** — `2443ae0` (`fix(19-41): the shim look-through matches the managed dir by resolved path`)

**Plan metadata:** summary commit recorded separately below.

## TDD Evidence

RED command: `uv run pytest tests/test_guards.py -q --no-cov -k "resolved_path or every_spelling"`

```text
2 failed
- look_through_shim returned the alias spelling instead of the real binary.
- real_binary returned None after retrying against a PATH that still contained the aliased managed directory.
```

After implementation, both regression tests passed. The focused guard/status run passed (63 tests).

## Verification Results

- `uv run pytest tests/test_guards.py -q --no-cov -k "resolved_path or every_spelling"` — **2 passed** after implementation.
- `uv run pytest tests/test_guards.py tests/test_status.py -q --no-cov -k "shim or real_binary or real_pnpm or presence"` — **63 passed**.
- File-integrity check for `tests/test_guards.py` — passed; file grew and gained two test functions.
- Suppression-count check — passed; unchanged at 482.
- Acceptance checks — `shim_dir.resolve()` occurs exactly twice; old textual comparisons occur zero times.
- `make validate && make test` — passed; **4625 passed, 4 skipped**, coverage **95.97%**. The commit's pre-commit hooks also passed.

## Decisions Made

- Compared normalized directory paths for recognition and filtering, but retained the resolved binary path returned by lookup rather than canonicalizing the output.

## Deviations from Plan

None — plan executed as written.

## Issues Encountered

- The first validation run found one unused local in the new test; removed the unnecessary assignment and reran the complete validation and test gates successfully.
- Final review was a self-review because no subagent tool is available in this Pi session; this is weaker than a fresh-context review.

## Next Phase Readiness

STATE-04's resolved-path alias/trailing-slash regression is closed. No known blocker for subsequent plans.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
