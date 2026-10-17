---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "33"
subsystem: uninstall
tags: [receipts, uninstall, quarantine, sha256, race-safety]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "Receipt artifacts with key-file directory fingerprints (L-19-31)"
provides:
  - "Directory deletion captures the proven tree in a unique quarantine sibling, re-hashes its key file, then deletes only that captured tree"
  - "Final file deletion checks force a sha256 re-hash; remove_proven uses the artifact map as its single proof set"
  - "Phase 19 architecture record documents key-file directory proof and quarantine removal"
affects: [uninstall, receipts, STATE-03]

actuals:
  tokens: 2200
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Directory deletion by same-parent exclusive quarantine rename, captured-tree verification, and put-back on mismatch or delete failure"
    - "Force re-hashing at the final file deletion gate"

key-files:
  created: []
  modified:
    - installer/uninstall.py
    - tests/test_uninstall.py
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "Use a `.tools-installer.rm` suffix distinct from update recovery's `.tools-installer.old`"
  - "When a captured tree cannot be put back, leave it intact at quarantine and raise an error naming both paths"

patterns-established:
  - "A directory's final proof is re-evaluated against the quarantined tree, not the original pathname"
  - "A file is re-hashed immediately before unlink; size and mtime equality alone is insufficient"

requirements-completed: [STATE-03]

coverage:
  - id: D1
    description: "Directory removal captures and re-verifies the exact tree; races preserve vendor data and failed put-back preserves the quarantined tree"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_paths_refuses_a_dir_replaced_after_its_final_check"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_paths_keeps_a_captured_dir_it_cannot_put_back"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_dir_removal_leaves_no_quarantine_behind"
        status: pass
    human_judgment: false
  - id: D2
    description: "File removal re-hashes at the final gate, while removal uses one artifact map and architecture records the key-file/quarantine contract"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_remove_proven_rehashes_a_file_swapped_after_verification"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_architecture_records_phase_19_mechanisms"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 33: Quarantine-safe, receipt-proven removal Summary

**Directory deletion now removes only the quarantined tree whose key file was re-hashed, and file deletion refuses same-length replacements even when mtime is restored.**

## Performance

- **Duration:** 25 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `_remove_dir` to create an exclusive same-parent quarantine sibling, rename the proven directory into it, and re-hash the key file before recursive deletion. A failed match puts the directory back and refuses it; a failed recursive delete puts the remainder back before propagating the error.
- Added deterministic directory-swap tests, including a collision that prevents put-back and verifies neither tree is deleted. Updated the failed-rmtree fixture to target the quarantine path.
- Forced re-hashing in `remove_paths` immediately before file unlink. Simplified `remove_proven` to filter against `fresh.artifacts` only.
- Documented key-file directory proof and quarantine deletion in the Phase 19 architecture record; pinned both phrases in the docs test.

## Task Commits

1. **Task 1: capture and re-verify directory before deleting** — `ec53258` (fix)
2. **Task 2: force final file re-hash and record proof rules** — `79dc84a` (fix)
3. **Plan summary** — committed separately as `docs(19-33): plan summary`

## TDD Evidence

### Task 1 RED

Command: `uv run pytest tests/test_uninstall.py -q --no-cov -k "replaced_after_its_final_check or cannot_put_back or no_quarantine or remainder_listed"`

Exit 1, 3 failed / 1 passed:
- `test_failed_opt_dir_delete_leaves_the_remainder_listed`: expected `OSError`, but the old implementation still called `rmtree(opt)` rather than the quarantine-targeting injected failure.
- `test_remove_paths_refuses_a_dir_replaced_after_its_final_check`: got `refused == ()` instead of `(opt,)`, and the swapped-in vendor tree was deleted by the original path-based `rmtree`.
- `test_remove_paths_keeps_a_captured_dir_it_cannot_put_back`: expected `OSError`, but no error was raised.

**GREEN on both trees:** `test_dir_removal_leaves_no_quarantine_behind` passed on the pre-change tree as expected. After implementation, the filtered Task 1 command passed all four tests.

### Task 2 RED

Command: `uv run pytest tests/test_uninstall.py tests/test_docs.py -q --no-cov -k "swapped_after_verification or phase_19_mechanisms"`

Exit 1: the new `test_remove_proven_rehashes_a_file_swapped_after_verification` failed because the replaced file was removed (`removed` contained the target instead of being empty); `test_architecture_records_phase_19_mechanisms` passed before its new required phrases were added. After implementation, this filtered command passed both tests.

## Verification Results

- Task 1: `uv run pytest tests/test_uninstall.py tests/test_app.py -q --no-cov -k "remove or uninstall or receipt or proven"` — passed.
- Task 1 pre-commit `make validate` — passed; `make test` — 4606 passed, 4 skipped, coverage 95.97%.
- Task 2: `uv run pytest tests/test_uninstall.py tests/test_docs.py tests/test_app.py -q --no-cov` — passed.
- Final `make validate && make test` — passed; 4607 passed, 4 skipped, coverage 95.97%.
- Acceptance checks: quarantine suffix and `mkdtemp` each appear once; direct `shutil.rmtree(artifact.path)` appears zero times; captured-tree `rehash=True` and final `receipts.matches(artifact, rehash=True)` each appear once; `set(fresh.removable)` appears zero times; architecture contains both `quarantine sibling` and `Contents/Info.plist`.
- Test shrink guard, suppression guard, `git diff --check`, and no-dependency check passed.
- `tests/test_uninstall.py` line count: 2287 at baseline; 2403 after Task 1; 2430 after Task 2. Task 1 `git diff --stat`: `installer/uninstall.py` +70, `tests/test_uninstall.py` +118/−6 (182 insertions, 6 deletions total). Task 2 `git diff --stat`: `.claude/architecture.md` +10, `installer/uninstall.py` +12/−6, `tests/test_docs.py` +2, `tests/test_uninstall.py` +27 (45 insertions, 6 deletions total).

## Deviations from Plan

None. The first `git add` attempt could not stage the ignored `.claude` path directly; staged its already-tracked modification with `git add -u .claude/architecture.md` instead. No scope change.

## Issues Encountered

The pre-commit hook initially rejected an explicit ignored `.claude` path. The tracked-file staging method resolved it; both task commits passed all pre-commit checks.

## Next Phase Readiness

STATE-03 removal now closes the directory replacement and final file re-hash windows identified by RR-01 and RR-02. No blocker for downstream Phase 19 work.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
