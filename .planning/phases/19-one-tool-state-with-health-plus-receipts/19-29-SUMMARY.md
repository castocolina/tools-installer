---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "29"
subsystem: receipts
tags: [receipts, fail-closed, permission-error, drift, uninstall]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "receipt read/record/adopt (19-01, 19-09, 19-14), plan_removal (19-10), _receipt_evidence (19-14), capped reader (19-28)"
provides:
  - "receipts.receipt_exists: a missing receipt is False, an unreadable receipts dir is present-but-untrusted"
  - "receipts.all_gone and receipts.retire: the pass deletes a receipt only when every artifact is conclusively gone and a re-read still matches"
  - "plan_removal and _receipt_evidence share receipt_exists, so PermissionError no longer aborts a refresh or an uninstall plan"
affects: [19-30, 19-31, phase-20-repair]

actuals:
  tokens: 4370
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Receipt lookups go through receipt_exists (lstat), never Path.exists, so Python 3.12 and 3.14 agree"
    - "An inaccessible receipts dir is simulated by wrapping os.stat/lstat/open, never chmod (root ignores modes)"

key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/uninstall.py
    - installer/version_status.py
    - tests/test_receipts.py
    - tests/test_uninstall.py
    - tests/test_version_status.py

key-decisions:
  - "Ruling: test_partially_drifted_receipt_stays_broken removes the opt dir and keeps the bin link. Unlinking only the link (the plan's literal) makes is_installed return False, so the tool is MISSING, not BROKEN. Cost if wrong: the guard covers a different half-gone shape than the plan named; both halves stay BROKEN by the same drifted() path."
  - "Final: Ruling: retire deletes only when the re-read equals the receipt the pass just read. A receipt rewritten to different bytes that are also all-gone is kept for one pass and retired on the next. The plan's retire contract requires the equality check (T-19-97). Cost if wrong: one extra pass of a BROKEN mark."

patterns-established:
  - "Pattern: deny_receipts_dir(monkeypatch) is the public root-safe double for an inaccessible receipts dir; other tests import it from tests.test_receipts"
  - "Pattern: all_gone is False for no artifacts and for any lstat that is not FileNotFoundError or NotADirectoryError"

requirements-completed: [STATE-03, STATE-01]

coverage:
  - id: D1
    description: "An unreadable receipts dir counts as a receipt that proves nothing: no adoption, no layout fallback, and neither plan_removal nor refresh raises"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_receipt_exists_treats_an_unreadable_dir_as_present"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_adopt_refuses_when_the_receipts_dir_is_unreadable"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_inaccessible_receipts_dir_never_aborts_plan_removal"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_inaccessible_receipts_dir_never_aborts_refresh"
        status: pass
    human_judgment: false
  - id: D2
    description: "A receipt whose every artifact is gone is retired under the write lock; a partly-gone or artifactless receipt stays"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_all_gone_needs_every_artifact_gone"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_retire_refuses_a_replaced_receipt"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_receipt_with_every_artifact_gone_is_retired"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_partially_drifted_receipt_stays_broken"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_artifactless_receipt_is_never_retired"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 29: Receipt existence and all-gone retirement Summary

**One `receipt_exists` treats an unreadable receipts dir as present-but-untrusted, and the refresh pass retires a receipt only when every artifact it names is gone.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-10-16T21:00:00Z
- **Completed:** 2026-10-16T21:55:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `receipts.receipt_exists` answers with `lstat`: missing is False, any other lookup failure is True, and a dangling symlink counts.
- `plan_removal`, `record`, `adopt` and `_receipt_evidence` all use it, so `PermissionError` from an inaccessible receipts dir no longer aborts a refresh or an uninstall plan. The dir reads as the existing unreadable note, with no adoption and no archive-layout fallback.
- `all_gone` plus `retire` delete a receipt under the write lock only after a re-read still equals it and every artifact is conclusively absent. A dnf reinstall then reads from current evidence instead of staying BROKEN.

## Task Commits

Each task was committed atomically (tests and code together; no red commit):

1. **Task 1: receipt_exists, shared by plan_removal, record and adopt (G23)** - `0b5ad9f` (fix)
2. **Task 2: the pass uses receipt_exists and retires an all-gone receipt (G23, G10)** - `be1ca58` (fix)

**Plan metadata:** this summary, committed after the two task commits.

## Files Created/Modified

- `installer/receipts.py` — `receipt_exists`, `all_gone`, `retire`; `record` and `adopt` call `receipt_exists`
- `installer/uninstall.py` — `plan_removal` tests `receipts.receipt_exists(tool.id)`
- `installer/version_status.py` — `_receipt_evidence` uses `receipt_exists` and retires an all-gone receipt
- `tests/test_receipts.py` — public `deny_receipts_dir`; existence, adoption, `all_gone` and `retire` tests
- `tests/test_uninstall.py` — an inaccessible dir never aborts `plan_removal` and drops the layout proof
- `tests/test_version_status.py` — all-gone retirement, partial drift, artifactless receipt, inaccessible refresh

## Decisions Made

- The partial-drift guard keeps the bin link and removes the opt dir. See Deviations.
- `retire` requires the re-read to equal the receipt. A receipt replaced with different all-gone bytes survives one pass. See the self-review ruling.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's partial-drift fixture cannot observe BROKEN**

- **Found during:** Task 2 (the pass uses receipt_exists and retires an all-gone receipt)
- **Issue:** The plan says `_install(_rg_archive())` then unlink only `bin_dir / "rg"`. `is_installed` follows that link (`artifact.path.is_file()`), so with the link gone the archive reads absent and `tool_health` returns MISSING, not BROKEN. The first RED run failed that way (`Health.MISSING`), which does not test the guard. Leaving the opt dir does not help: a directory alone is not presence.
- **Fix:** The test removes the opt dir with `shutil.rmtree` and keeps the bin link, so the tool stays present while one artifact is gone. It asserts BROKEN, `changed since install`, and that the receipt still exists.
- **Files modified:** tests/test_version_status.py
- **Verification:** The corrected test passed on the pre-change code (the plan said this guard may), and still passes after `all_gone`/`retire`.
- **Committed in:** `be1ca58` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in the prescribed fixture)
**Impact on plan:** The guard still pins "one remaining artifact stays BROKEN". No production behavior changed because of it.

## TDD RED evidence

Task 1, `uv run pytest tests/test_receipts.py tests/test_uninstall.py -q --no-cov -k "unreadable_dir or receipts_dir_is_unreadable or inaccessible_receipts"` (3 failed):

```
E       AttributeError: module 'installer.receipts' has no attribute 'receipt_exists'
tests/test_receipts.py:960: AttributeError

installer/receipts.py:291: in adopt
    if path.exists() or path.is_symlink():
E           PermissionError: [Errno 13] Permission denied: '.../receipts/.../yq.json'

installer/uninstall.py:126: in plan_removal
    if _exists(receipts.receipt_path(tool.id)):
E           PermissionError: [Errno 13] Permission denied: '.../receipts/.../rg.json'
```

Task 2, `uv run pytest tests/test_receipts.py tests/test_version_status.py -q --no-cov -k "all_gone or retire or every_artifact_gone or partially_drifted or artifactless or inaccessible_receipts"`:

```
E       AttributeError: module 'installer.receipts' has no attribute 'all_gone'
E       AttributeError: module 'installer.receipts' has no attribute 'retire'
E       AssertionError: assert <Health.BROKEN: 'broken'> is not <Health.BROKEN: 'broken'>
    (test_receipt_with_every_artifact_gone_is_retired — the dnf copy stayed BROKEN)
E           PermissionError: [Errno 13] Permission denied: '.../yq.json'
    (test_inaccessible_receipts_dir_never_aborts_refresh, from path.exists in _receipt_evidence)
```

`test_partially_drifted_receipt_stays_broken` passed on the old code once the fixture kept the tool present (see Deviations). `test_artifactless_receipt_is_never_retired` was collected with the others and passes on the old code too: nothing retired an artifactless receipt before this plan.

## Verify-command results

- Task 1: `uv run pytest tests/test_receipts.py tests/test_uninstall.py -q --no-cov` green; the `-k` filter passed 3. `make validate` exit 0. Shrink guard: test_receipts.py 916→980 lines, tests 39→41; test_uninstall.py 2233→2252, tests 100→101. Suppressions 487→487.
- Task 2: `uv run pytest tests/test_receipts.py tests/test_version_status.py tests/test_uninstall.py -q --no-cov` green; the `-k` filter passed 6. Shrink guard: test_receipts.py 980→1058, tests 41→43; test_version_status.py 5096→5177, tests 159→163. `path.exists() or path.is_symlink()` in receipts.py and version_status.py: 0. Suppressions 487→487.
- Final tree: `make validate` exit 0; `make test` exit 0 — 4563 passed, 4 skipped, coverage 95.99% (floor 90%).
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` exit 0 (no new dependency).
- `wc -l` at the final tree: receipts.py 511 (HEAD before the plan 459), uninstall.py 666 (665), version_status.py 1667 (1663), test_receipts.py 1058 (916), test_uninstall.py 2252 (2233), test_version_status.py 5177 (5096). `git diff --stat 27afe03..be1ca58`: 6 files, +312/−13.

## Self-review

No subagent tool was used for a fresh reviewer. Read of `git diff 27afe03..be1ca58` against the plan:

- Strengths: one helper for the four lookups; `lstat` so 3.12 and 3.14 agree; `all_gone` fails closed on `OSError` and `ValueError`; `retire` re-reads under `_WRITE_LOCK` and a failed delete returns False.
- Critical: none. Important: none.
- Declined to judge, then ruled: a receipt replaced between the pass's read and `retire` with different all-gone bytes is not deleted this pass. That is what the plan's `retire` contract says (`current != receipt` returns False), and the next pass retires it. Recorded above.
- Minor (deferred): `all_gone` stats outside the lock, so the check is repeated inside `retire`; the pass pays one extra stat per artifact. Harmless.

## Issues Encountered

None beyond the fixture deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G23 and G10 are closed. A broken receipts dir can no longer crash a refresh or an uninstall plan, and a receipt whose files are all gone stops pinning the tool to BROKEN.
- `deny_receipts_dir` is public in tests/test_receipts.py for later plans.
- No blocker for 19-30 or 19-31.

## Rulings I made

- Task 2: the partial-drift fixture removes the opt dir and keeps the link, because unlinking the link makes the tool MISSING. Cost if wrong: the guard covers the other half-gone shape; both stay BROKEN through `drifted`.
- Final: `retire` keeps a receipt that was replaced with different all-gone bytes for one pass. Cost if wrong: one extra pass of a BROKEN mark.

## Deferred minors

- `all_gone` stats once in the pass and again inside `retire`.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
