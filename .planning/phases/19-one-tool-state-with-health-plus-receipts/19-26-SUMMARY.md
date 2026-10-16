---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "26"
subsystem: uninstall
tags: [receipts, uninstall, data-safety, artifact-type]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "receipt artifact fingerprints and receipts.matches, including directory identity (19-22)"
provides:
  - "RemovalPlan.artifacts carries the authorized artifact of every proven path"
  - "remove_paths deletes by the authorized type after a last receipts.matches re-check"
  - "remove_proven refuses a path that changed after the deletion-time proof and keeps its receipt"
affects: [uninstall, receipts, STATE-03]

actuals:
  tokens: 5150
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "The authorized ReceiptArtifact travels from the removal proof to the delete; the live path never re-chooses unlink versus rmtree"

key-files:
  created: []
  modified:
    - installer/uninstall.py
    - tests/test_uninstall.py

key-decisions:
  - "Task 2 tests characterize the refusal Task 1 already wired; the missing piece was returning the refused paths as refused rather than as removed"

patterns-established:
  - "A file or link artifact is only ever unlinked; only a dir artifact can reach rmtree, and only after receipts.matches confirms it"

requirements-completed: [STATE-03]

coverage:
  - id: D1
    description: "The removal plan keeps each proven path's authorized artifact, and deletion is chosen by that type after a last re-check"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_removal_keeps_each_proven_artifact"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_paths_unlinks_only_what_its_type_authorizes"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_paths_refuses_a_missing_artifact"
        status: pass
    human_judgment: false
  - id: D2
    description: "remove_proven refuses a path that changed after the deletion-time proof and keeps its receipt"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_proven_refuses_a_file_replaced_by_a_dir_after_verification"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_proven_refuses_a_dir_recreated_after_verification"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 26: Typed, Re-checked Removal Summary

**The remover now deletes by the artifact type that proved each path and refuses a path that changed after the deletion-time proof, so a file swapped for a directory is never recursively deleted.**

## Performance

- **Duration:** 40 min (resume of a stalled run; Task 1 was already committed)
- **Started:** 2026-10-16T20:30:00Z (approximate; this session resumed mid-plan)
- **Completed:** 2026-10-16T21:13:47Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `RemovalPlan.artifacts` carries the authorized `ReceiptArtifact` of every proven path, for both receipt-proven files and layout-proven archive pairs.
- `remove_paths` unlinks a `file` or `link` and calls `rmtree` only for a `dir`, and only after `receipts.matches` re-checks the artifact.
- `remove_proven` reports a post-proof change with the existing `changed since the preview; not removed: {path}` line and retires a receipt only after every path it proved is actually gone.

## Task Commits

Each task was committed atomically:

1. **Task 1: the removal plan carries each proven artifact, and the remover deletes by its authorized type after a re-check (G1)** - `cca5b74` (fix)
2. **Task 2: remove_proven refuses a path that changed after the deletion-time proof (G1)** - `9ce9b46` (fix)

**Plan metadata:** this summary's own commit (docs: plan summary)

## Files Created/Modified

- `installer/uninstall.py` - authorized artifacts on `RemovalPlan`; typed, re-checked `remove_paths`; `remove_proven` returns only the paths it actually deleted
- `tests/test_uninstall.py` - type-escalation, missing-artifact, and verification-race tests; existing `remove_paths` callers updated to pass fingerprints

## Decisions Made

- Task 2's uncommitted tests were kept. They failed once against Task 1's tree because `remove_proven` still returned every kept path as removed, so they were not characterization tests of already-delivered behavior. The one-line return fix made them pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Resume] Task 2 had no separate RED capture from this session's implementation step**
- **Found during:** Task 2 (resume)
- **Issue:** The stopped run had already written the two Task 2 tests and left them uncommitted. The orchestrator said to treat a pass as "no RED, Task 1 already wired the refusal". The one required run failed instead.
- **Fix:** Implemented the plan's return contract (`removed` is the kept paths minus the paths `remove_paths` refused) and re-ran the same tests to green.
- **Files modified:** `installer/uninstall.py`, `tests/test_uninstall.py`
- **Verification:** `uv run pytest tests/test_uninstall.py -q --no-cov -k "after_verification"` — 2 passed
- **Committed in:** `9ce9b46` (Task 2 commit)

---

**Total deviations:** 1 (resume handling; the code change is the plan's own Task 2 action)
**Impact on plan:** No scope change. Task 1 was not redone.

## TDD evidence

### Task 1 RED

Captured by the previous run and recorded here from that commit's working notes. The tests failed before `RemovalPlan.artifacts` and the typed `remove_paths` existed:

```
FAILED tests/test_uninstall.py::test_plan_removal_keeps_each_proven_artifact
FAILED tests/test_uninstall.py::test_remove_paths_unlinks_only_what_its_type_authorizes
FAILED tests/test_uninstall.py::test_remove_paths_refuses_a_missing_artifact
```

The planned updates of the old `remove_paths` callers (`test_remove_paths_deletes_dirs_files_and_symlinks`, `test_remove_paths_unlinks_symlink_to_dir_without_deleting_target`, the failing-rmtree test, and the `boom` double) landed in the same Task 1 commit.

### Task 2 RED (this session, one run)

`uv run pytest tests/test_uninstall.py -q --no-cov -k "after_verification"`:

```
FF
FAILED tests/test_uninstall.py::test_remove_proven_refuses_a_file_replaced_by_a_dir_after_verification
E       AssertionError: assert (PosixPath('.../.local/bin/yq'),) == ()
FAILED tests/test_uninstall.py::test_remove_proven_refuses_a_dir_recreated_after_verification
E       AssertionError: assert (PosixPath('.../.local/opt/fd'),) == (PosixPath('.../.local/bin/fd'),)
```

GREEN after the return fix: `..` (2 passed).

## Verify-command results

- Task 2 verify: `uv run pytest tests/test_uninstall.py tests/test_app.py -q --no-cov -k "remove_proven or after_verification or uninstall or receipt"` — 148 passed.
- `after_verification` alone — 2 passed (fails_when requires at least 2).
- Truncation guard against HEAD before the Task 2 commit: `tests/test_uninstall.py` 2162 → 2235 lines, tests 98 → 100. After `ruff format`: 2233 lines. Trailing newline present.
- Suppressions (`type: ignore|pyright: ignore|noqa|nosec`) stayed 487 → 487.
- `grep -c "fresh.artifacts" installer/uninstall.py` = 2.
- `make validate` exit 0 (after `ruff format` on the new tests).
- `make test` exit 0: 4536 passed, 4 skipped, coverage 95.99%.

## Size evidence

- `wc -l`: `tests/test_uninstall.py` 2233, `installer/uninstall.py` 665.
- `git diff --stat cca5b74^..9ce9b46`: `installer/uninstall.py` +70/−42, `tests/test_uninstall.py` +190/−8.
- Task 2 working diff before commit: `installer/uninstall.py` 2 lines changed, `tests/test_uninstall.py` +71. No other files.

## Issues Encountered

- The previous run committed Task 1 and stalled with the Task 2 tests uncommitted. Those tests were reviewed against the plan and kept.
- `make validate` failed once on `ruff format --check` for `tests/test_uninstall.py`. Formatting it dropped two lines and changed no behavior.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- STATE-03's G1 gap is closed for both the CLI and the TUI: both call the same `remove_proven`, whose contract `(removed, refused)` is unchanged.
- Callers that construct `RemovalPlan` directly still get an empty `artifacts` mapping from the field default.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
