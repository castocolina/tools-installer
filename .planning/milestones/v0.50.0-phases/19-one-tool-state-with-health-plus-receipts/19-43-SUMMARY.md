---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "43"
subsystem: persistence
tags: [python, receipts, memoization, update-safety]
requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: receipt-backed artifact fingerprinting and directory key-file proof
provides:
  - Session memoization for file and directory key-file fingerprints, with forced rehash when recording/adopting receipts
  - One BROKEN drift classifier shared by health reporting and the installer update gate
affects: [phase-19-receipts, version-health, update-safety]
actuals:
  tokens: 1900
  tasks: 2
  commits: 1
tech-stack:
  added: []
  patterns: [session hash memo keyed by path and stat tuple; central receipt drift classification]
key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/version_status.py
    - installer/update.py
    - tests/test_receipts.py
    - tests/test_version_status.py
key-decisions:
  - "Receipt creation and adoption always bypass the fingerprint memo so receipts bind to the bytes just read."
  - "Directory drift only removes proof; file and link drift alone classify a receipt as BROKEN."
patterns-established:
  - "Use rehash=True when a persisted receipt is created or adopted; ordinary fingerprints may use the session memo."
  - "Route BROKEN classification through receipts.broken_drift rather than duplicating artifact-type filters at callers."
requirements-completed: [STATE-03, STATE-02]
coverage:
  - id: D1
    description: Unchanged file and directory key-file fingerprints reuse a session hash, while changed stat tuples and rehash=True read bytes again.
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_receipts.py#test_fingerprint_hashes_an_unchanged_file_once_per_session
        status: pass
      - kind: unit
        ref: tests/test_receipts.py#test_dir_key_file_is_hashed_once_per_session
        status: pass
      - kind: unit
        ref: tests/test_receipts.py#test_record_and_adopt_never_trust_the_memo
        status: pass
    human_judgment: false
  - id: D2
    description: Health and the installer update gate use one BROKEN classifier, which skips directory hashing.
    requirement: STATE-02
    verification:
      - kind: unit
        ref: tests/test_receipts.py#test_broken_drift_skips_dirs_and_never_hashes_their_key_file
        status: pass
      - kind: integration
        ref: tests/test_version_status.py and tests/test_update.py receipt/drift regression suites
        status: pass
    human_judgment: false
duration: 25min
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 43 Summary

**Receipt fingerprints now reuse hashes within a session, while receipt creation forces fresh bytes and health/update share one BROKEN rule.**

## Performance

- **Duration:** approximately 25 minutes
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Memoized `_file_fingerprint` by `(path, size, mtime_ns)` and added `rehash=True` to force fresh reads. Directory key-file proofs now reuse the same session memo.
- Ensured both `record` and `adopt` bypass the memo so persisted receipts are constructed from freshly read bytes.
- Added `receipts.broken_drift`; version health and the update gate use it, and the update gate no longer hashes directory key files it ignores.
- Added regression coverage for memo reuse, cache bypass, and BROKEN classification behavior.

## Task Commits

Both tasks were committed together in one atomic implementation commit:

1. **Task 1: memoized fingerprints and receipt rehashing** - `5cd5e4f` (`fix(19-43): memoize fingerprints and centralize broken drift`)
2. **Task 2: shared BROKEN drift classification** - `5cd5e4f` (same combined commit; task changes were not split into separate commits)

**Plan metadata:** this summary is committed separately as `docs(19-43): plan summary`.

## TDD RED Evidence

- **Task 1:** The required focused memo test run failed before the implementation: tests reported that `fingerprint()` did not accept `rehash=`, and repeated file/key-file fingerprints rehashed instead of hitting the memo. During validation, existing race-test wrappers also needed to accept and forward the new keyword so they continued testing the forced rehash path.
- **Task 2:** `uv run pytest tests/test_receipts.py -q --no-cov -k broken_drift` — **1 failed** as expected: `AttributeError: module 'installer.receipts' has no attribute 'broken_drift'`.

## Verification

- Task 1 targeted tests: `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py -q --no-cov` — passed.
- Task 1 `make validate && make test` — passed after resolving formatting/type-check feedback: **4630 passed, 4 skipped**, coverage **95.98%**.
- Task 2 focused selection: `uv run pytest tests/test_receipts.py tests/test_version_status.py tests/test_update.py -q --no-cov -k "broken_drift or drift or receipt or adopt or unproven or update_service"` — passed.
- Final touched-suite verification: `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py tests/test_version_status.py tests/test_update.py -n auto -q --no-cov` — passed.
- Final `make validate && make test` — passed: **4631 passed, 4 skipped**, coverage **95.98%**.
- File-size/suppression guards and `git diff --check` passed. `tests/test_receipts.py` grew from 1311 lines at plan start to 1398 lines at Task 2 verification. Task 2 diff stat: 5 files changed, 177 insertions, 24 deletions.
- Acceptance checks: one `broken_drift` definition and one call at each caller; no inline `type != "dir"` filters at either caller and exactly one in the central helper; the fingerprint rehash call sites are the two `record` branches and `adopt`.

## Deviations from the Plan

**1. Compatibility update to existing test wrappers**
- **Found during:** Task 1 integration verification.
- **Issue:** Two existing monkeypatched `fingerprint` wrappers rejected the newly introduced `rehash=` keyword.
- **Fix:** Updated both wrappers to accept and forward the keyword, preserving their original race assertions.
- **Files modified:** `tests/test_receipts.py`, `tests/test_version_status.py`.
- **Verification:** Touched suites and full validation/test gates passed.

**2. Task commits combined**
- The implementation work for Tasks 1 and 2 was committed as a single commit rather than separate task commits. All tests and quality gates passed on that committed tree; the summary records this deviation transparently.

**Total deviations:** 2 (one test compatibility adjustment; one combined task commit).

## Issues Encountered

- The first validation attempt found a long docstring line; the next found a formatting mismatch and pyright private/optional type issues in the new tests. These were corrected, and the complete validation and test gates passed afterward.
- Fresh reviewer subagent attempts could not start: the configured Claude reviewer provider was ambiguous/unavailable, and the available Codex reviewer had no authenticated API key. I therefore performed a self-review of the complete diff against the plan and spec. The self-review is weaker than an independent reviewer.

## User Setup Required

None.

## Next Phase Readiness

Fingerprint memoization retains the D-08 session shortcut without allowing receipt creation/adoption to trust it. BROKEN classification is centralized and directory drift remains unproven rather than broken. No known blocker for follow-on work.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
