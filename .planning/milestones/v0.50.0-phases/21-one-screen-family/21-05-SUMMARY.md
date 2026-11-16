---
phase: 21-one-screen-family
plan: "05"
subsystem: state-service
tags: [version_status, pending, evidence, pnpm]
requires: []
provides:
  - VersionRefreshService.mark_pending
  - VersionRefreshService.record_evidence
  - pnpm off-PATH reason from the pass (PNPM_TRACKED_OFF_PATH)
affects: [21-13, 21-19]
key-files:
  modified:
    - installer/version_status.py
    - installer/pnpm_globals.py
    - installer/guidance.py
    - tests/test_version_status.py
    - tests/test_guidance.py
status: complete
commits: 3
plan_head_before: 390f464298f06a30365de37e11510d5479afa09a
plan_head_after: ddf1806b63b1dbbb696985f5876cb1f846dd75ce
actuals:
  tokens: 6000
  tasks: 3
  commits: 3
requirements: [UI-05, UI-07]
---

# Phase 21 Plan 05: Pending, evidence and pnpm off-PATH in the state service

`mark_pending` hides exactly a removal's tool ids (even from an in-flight pass), `record_evidence` feeds Doctor findings into every pass, and the pass reports "pnpm tracks it but the command left PATH" from the cached inventory.

## Commits
- baaae63 feat(21-05): mark_pending hides the tools a removal is changing
- 25d620b feat(21-05): a session evidence store feeds Doctor findings into every pass
- ddf1806 feat(21-05): the pass reports pnpm-tracked tools whose command left PATH

## TDD evidence
- RED task 1: `AttributeError: 'VersionRefreshService' object has no attribute 'mark_pending'` (3 failed); GREEN: tests/test_version_status.py + test_tool_health.py passed.
- RED task 2: `AttributeError` on `record_evidence` (3 failed); GREEN passed.
- RED task 3: `assert _OFF_PATH in state.reasons` failed (reasons held only the multi-manager sentence); GREEN passed.

## Verification
- `make validate`: exit 0 on each commit's tree. `make test`: exit 0 (4932 passed, 4 skipped on the final tree; coverage 96.05%).
- `tests/test_version_status.py` collected count: 191 at start, 199 at end.

## Reuse (21-REUSE finding 05-1)
`_pnpm_missing_facts` is one call to the existing `audit_node_globals` (stubbed `smoke`, so no subprocess); the sentence lives once in `PNPM_TRACKED_OFF_PATH`, reused by `guidance.node_globals_guidance` (output byte-identical, asserted by a new test).

## Deviations from Plan

**1. [Rule 1 - Bug] `_group_service` test fixture contradicted itself**
- **Found during:** Task 3
- **Issue:** the fixture marked tools present while `which` always returned `None`; the new off-PATH fact (correctly) flagged them, breaking `test_complete_group_is_quiet`.
- **Fix:** the fixture's `which` now resolves the ids in `present`.
- **Files modified:** tests/test_version_status.py
- **Commit:** ddf1806

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
