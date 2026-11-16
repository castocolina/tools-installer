---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "44"
subsystem: uninstall
tags: [python, receipts, uninstall, quarantine, interruption-safety]

# Dependency graph
requires:
  - phase: 19-38
    provides: Receipt-backed uninstall proof and quarantine-based directory removal
provides:
  - Catchable interruptions restore a captured directory or report its quarantine path
  - Surviving quarantine siblings appear in remove-it-yourself listings and are never auto-deleted
  - Directory key files are hashed twice during removal, not three times
affects: [uninstall, phase-19]

# Actuals
actuals:
  tokens: 5022
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Catchable interruption handling around a quarantined directory capture
    - List unverified quarantine remnants for manual cleanup, never automatic deletion

key-files:
  created: []
  modified:
    - installer/uninstall.py
    - tests/test_uninstall.py
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "A quarantined tree is restored on catchable exits; if restoration fails, report its surviving quarantine path and retain the triggering exception as context."
  - "Discover interrupted-removal siblings for user visibility only; they are not receipt- or layout-proven and must not be deleted automatically."
  - "Use the quarantine re-check as the authoritative directory hash, keeping the middle check stat-only."

patterns-established:
  - "Interrupted directory removal: capture, verify inside quarantine, restore on any catchable failure."
  - "Quarantine remnants are surfaced through the existing yourself listing, not given a cleanup path."

requirements-completed: [STATE-03]
coverage:
  - id: D1
    description: Catchable directory-removal interruptions restore the captured tree or name where it remains.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_remove_paths_puts_the_tree_back_when_interrupted
        status: pass
      - kind: unit
        ref: tests/test_uninstall.py#test_an_interrupted_removal_that_cannot_put_back_names_the_quarantine
        status: pass
    human_judgment: false
  - id: D2
    description: Leftover quarantine siblings are listed for manual cleanup and survive installer removal.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_a_leftover_quarantine_sibling_is_listed_to_remove_yourself
        status: pass
    human_judgment: false
  - id: D3
    description: Directory key files are hashed twice during receipt-backed removal.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_remove_proven_hashes_a_dir_key_file_twice_not_three_times
        status: pass
    human_judgment: false

duration: not recorded
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 44 Summary

**Directory removal now survives catchable interruptions, surfaces orphaned quarantine siblings for manual cleanup, and avoids a redundant key-file hash.**

## Performance

- **Duration:** Not recorded
- **Started:** Not recorded
- **Completed:** 2026-10-17
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Protected the post-capture portion of directory removal. A catchable interruption or removal error puts the captured tree back; if put-back fails, the resulting `OSError` names the quarantine path and retains the triggering exception as context.
- Added discovery of leftover `.tools-installer.rm` siblings to `plan_removal.yourself`. These paths reach existing previews and managed-tool hints but remain outside automatic removal.
- Changed the pre-delete directory check to avoid a redundant hash; the key file is hashed for fresh proof and again inside quarantine.
- Documented the interruption and quarantine-remnant behavior and anchored the architecture note with a documentation test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Restore captured directories on interruption** - `0dfec2f` (`fix(19-44): an interrupted dir removal puts the captured tree back or names where it is`)
2. **Task 2: Surface leftover quarantine and avoid an extra directory hash** - `52df7f7` (`fix(19-44): list leftover quarantine siblings and avoid an extra dir hash`)

**Plan metadata:** This plan summary is committed separately after the task commits.

## Files Created/Modified

- `installer/uninstall.py` - Added catchable-interruption recovery, quarantine sibling discovery, and the stat-only middle check for directory artifacts.
- `tests/test_uninstall.py` - Added interruption, failed put-back, leftover visibility/non-deletion, and hash-count regression tests.
- `.claude/architecture.md` - Recorded interruption recovery and manual visibility of surviving quarantine siblings.
- `tests/test_docs.py` - Required the new architecture phrase.

## Decisions Made

- Restore on `BaseException` after capture so `KeyboardInterrupt` and `SystemExit` cannot silently strand the tree; allow only uncatchable termination such as SIGKILL to leave a sibling.
- List a surviving sibling for the user without treating it as authorization to delete it.
- Keep the quarantine re-hash authoritative for directories and preserve the pre-delete re-hash for files.

## Deviations from Plan

None. The implementation and scope followed the plan.

## Issues Encountered

- Task 1's red tests exposed that interruption left the tree at its quarantine path. A failed put-back also required explicitly retaining the interruption as the `OSError` context; both were corrected and tested.
- The first Task 2 red run showed the leftover quarantine was absent from `plan.yourself`; the resulting discovery and hashing tests pass after implementation.
- The first full validation attempt reported Ruff formatting changes in the two edited Python files. Ran Ruff's formatter, then reran validation and the full suite successfully.
- The initial staging command rejected the ignored `.claude` path. Staged only the intended files, force-adding the specifically required `.claude/architecture.md` file.

## TDD RED Evidence

- **Task 1** — `uv run pytest tests/test_uninstall.py -q --no-cov -k "interrupted"` failed as expected: both interruption cases left the captured directory at the quarantine sibling instead of restoring it. The failed-put-back case also exposed that the interruption needed to remain available as the resulting `OSError` context.
- **Task 2** — `uv run pytest tests/test_uninstall.py tests/test_docs.py -q --no-cov -k "leftover_quarantine or twice_not_three or phase_19_mechanisms"` failed as expected: the leftover quarantine was absent from `plan.yourself`; the hash-count regression also failed before the stat-only check was implemented. The required architecture phrase was added with the test before implementation.

## Verification

- Task 1 targeted tests: `uv run pytest tests/test_uninstall.py -q --no-cov -k "remove_paths or remove_proven or quarantine or interrupted or put_back"` — 19 passed.
- Task 2 targeted tests: `uv run pytest tests/test_uninstall.py tests/test_docs.py tests/test_app.py -q --no-cov -k "remove_paths or remove_proven or quarantine or leftover or yourself or phase_19_mechanisms or receipt"` — 36 passed.
- `make validate` — passed (Ruff, formatting, Pyright, Bandit, Vulture, ShellCheck).
- `make test` — passed: 4,636 passed, 4 skipped; total coverage 95.99%.
- `git diff --check` — passed before the Task 2 commit.
- Large-file check before Task 2 commit: `tests/test_uninstall.py` had 2,606 lines; test-file truncation and suppression guards passed. Task 2 diff: 97 insertions and 12 deletions across four files. Task 1 diff: 87 insertions and 8 deletions across two files.

## Next Phase Readiness

Plan 19-44 is complete. Catchable interruptions restore the captured directory, surviving remnants are visible but never automatically deleted, and the complete validation suite passed.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
