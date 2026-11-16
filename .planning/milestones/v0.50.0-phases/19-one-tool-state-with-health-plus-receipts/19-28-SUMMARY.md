---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "28"
subsystem: file-io
tags: [posix, fifo, O_NONBLOCK, receipts, skill-lifecycle]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "receipt reader (19-22) and skill probes of installed_plugins.json and GSD hook configs (19-23)"
provides:
  - "atomic.read_capped: one non-blocking, descriptor-checked, size-capped reader"
  - "receipts, installed_plugins.json and every GSD hook config read through it"
affects: [19-one-tool-state-with-health-plus-receipts, phase-20-skill-install]

actuals:
  tokens: 5061
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A capped config is opened with O_NONBLOCK and typed with fstat on the opened descriptor, never stat-then-open"

key-files:
  created: []
  modified:
    - installer/atomic.py
    - installer/receipts.py
    - installer/skill_lifecycle.py
    - tests/test_atomic.py
    - tests/test_receipts.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "read_capped returns None for a non-regular or oversize file and lets OSError from os.open propagate, so each caller keeps its own missing-versus-unreadable answer"
  - "Receipts pass follow_symlinks=False; installed_plugins.json and hook configs pass True, so a dotfiles-manager symlink is still followed"

patterns-established:
  - "Pattern: one helper owns every capped config read phase 19 added; a FIFO, device, directory or oversize file is refused without blocking"

requirements-completed: [STATE-07, STATE-03]

coverage:
  - id: D1
    description: "read_capped opens non-blocking, checks fstat on the descriptor and returns at most cap bytes; a FIFO, directory, symlink (unless followed) or oversize file yields no bytes"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_atomic.py#test_read_capped_reads_a_regular_file"
        status: pass
      - kind: unit
        ref: "tests/test_atomic.py#test_read_capped_refuses_an_oversize_file"
        status: pass
      - kind: unit
        ref: "tests/test_atomic.py#test_read_capped_never_blocks_on_a_fifo"
        status: pass
      - kind: unit
        ref: "tests/test_atomic.py#test_read_capped_refuses_a_symlink_unless_following"
        status: pass
    human_judgment: false
  - id: D2
    description: "receipts.read goes through read_capped without following symlinks, and a FIFO at the receipt path returns None without blocking"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_receipt_read_goes_through_read_capped"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_receipt_read_never_blocks_on_a_fifo"
        status: pass
    human_judgment: false
  - id: D3
    description: "The skill probes read installed_plugins.json and every GSD hook config through read_capped with symlink following; a FIFO at either keeps the existing fail-closed answer"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_installed_plugins_fifo_never_blocks"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_hook_config_fifo_is_not_checked"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_capped_config_reads_use_read_capped"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 28: One non-blocking capped reader Summary

**One `read_capped` helper opens every phase-19 capped config non-blocking and checks the type on the opened descriptor, so a FIFO at a receipt, `installed_plugins.json` or a GSD hook config can no longer stall a worker**

## Performance

- **Duration:** 7 min
- **Started:** 2026-10-16T21:28:31Z
- **Completed:** 2026-10-16T21:35:12Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `atomic.read_capped` opens with `O_NONBLOCK` (plus `O_NOFOLLOW` unless following), `fstat`s the descriptor and reads at most `cap + 1` bytes
- Receipts use it with `follow_symlinks=False`; a FIFO or a symlink at the receipt path is no receipt
- `_installed_project_paths` and `_gsd_hooks_registered` use it with `follow_symlinks=True`, keeping each caller's existing fail-closed answer

## Task Commits

Each task was committed atomically:

1. **Task 1: read_capped, and receipts read through it (G12)** - `129eebd` (fix)
2. **Task 2: installed_plugins.json and hook configs read through read_capped (G12)** - `bfde9ad` (fix)

## Files Created/Modified
- `installer/atomic.py` - `read_capped`
- `installer/receipts.py` - `read` over `read_capped(..., follow_symlinks=False)`
- `installer/skill_lifecycle.py` - both config readers over `read_capped(..., follow_symlinks=True)`
- `tests/test_atomic.py` - regular, oversize, FIFO and symlink cases
- `tests/test_receipts.py` - spy and FIFO cases; the grown-file cap test counts `os.read`
- `tests/test_skill_lifecycle.py` - FIFO, hook and spy cases; the hook cap test counts `os.read`

## Decisions Made
- `read_capped` returns None for a non-regular or oversize file and lets `OSError` from `os.open` propagate. Receipts fold both into None; the hook reader still maps `FileNotFoundError`/`NotADirectoryError` to False and any other `OSError` to None.
- Symlink policy stays with the caller: receipts never follow, the two skill configs do, so a dotfiles-manager symlink remains readable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing size-cap tests spied on the old open path**
- **Found during:** Task 1 (`test_read_fails_closed_on_a_file_that_grew_after_the_size_check`) and Task 2 (`test_oversized_hook_config_bound_is_the_read`)
- **Issue:** Both tests patched `Path.lstat`/`Path.stat` and `Path.open` to prove the cap is the read itself. The new reader never calls `Path.open`, so the spies saw nothing and the assertions failed.
- **Fix:** Each test now counts `os.read` as seen by `installer.atomic`, and asserts the same bound (65537 for a receipt, 262145 for a hook config). The "never open an oversized hook config" test still passes unchanged, because the helper refuses before reading once `fstat` reports the size.
- **Files modified:** `tests/test_receipts.py`, `tests/test_skill_lifecycle.py`
- **Verification:** both tests pass; `make test` is 4554 passed, 4 skipped
- **Committed in:** `129eebd` (receipt) and `bfde9ad` (hook)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The cap is still proven on the read. No scope change.

## TDD RED evidence

Task 1, `uv run pytest tests/test_atomic.py tests/test_receipts.py -q --no-cov -k "read_capped or fifo"`:

```
ERROR tests/test_atomic.py
E   ImportError: cannot import name 'read_capped' from 'installer.atomic'
Interrupted: 1 error during collection
```

Task 2, `uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "fifo or use_read_capped"`:

```
FAILED tests/test_skill_lifecycle.py::test_installed_plugins_fifo_never_blocks
E   assert not True
     +  where True = is_alive()
FAILED tests/test_skill_lifecycle.py::test_capped_config_reads_use_read_capped
E   AttributeError: module 'installer.skill_lifecycle' has no attribute 'read_capped'
```

The hook-config FIFO already returned within the join on the old code (its `stat` refuses a FIFO before `open`). The plugins FIFO is the one that blocked, and that is the failure the plan predicted.

## Verify results

- `make validate` exit 0 before each commit
- `make test` exit 0 before each commit: 4551 passed before task 2, 4554 passed, 4 skipped, coverage 95.99% on the final tree
- Plan verification `uv run pytest tests/test_atomic.py tests/test_receipts.py tests/test_skill_lifecycle.py tests/test_version_status.py -n auto -q --no-cov`: passed (464 tests)
- `-k "read_capped or fifo"` across the three files: 9 passed
- Acceptance: `def read_capped` = 1, `O_NONBLOCK` = 1, the receipt call = 1, `read_capped(` in `skill_lifecycle.py` = 2
- Suppressions stayed at 487
- Truncation guard for `tests/test_skill_lifecycle.py`: 2244 -> 2302 lines, tests 111 -> 114, file ends in a newline
- `git diff --stat` for task 2: `installer/skill_lifecycle.py | 22`, `tests/test_skill_lifecycle.py | 128`; both diffs are the intended hunks
- `pyproject.toml` and `uv.lock` unchanged against `fde3e68`

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Ready for 19-29. Every capped config read phase 19 added goes through one reader, so no special file can stall the skill worker or a refresh pass.

## Self-Check: PASSED

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
