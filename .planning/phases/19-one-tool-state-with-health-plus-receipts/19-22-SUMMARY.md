---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "22"
subsystem: receipts
tags: [receipts, identity, fail-closed, uninstall, version-status]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: the receipt module, plan_removal's receipt proof and the refresh pass's receipt evidence (plans 19-01, 19-09, 19-10, 19-14)
provides:
  - "A dir receipt artifact proven by (st_dev, st_ino), so a re-created directory never inherits an old receipt's proof"
  - "A per-type receipt reader that keeps only the fields each artifact type is checked on"
  - "Fail-closed handling of artifact paths lstat would refuse, through read, matches, fingerprint, plan_removal and refresh"
  - "A re-hash memo that stores the observed sha256 and compares each receipt's own digest"
affects: [19-24, 19-25, 19-31, phase-20-removal]

actuals:
  tokens: 3800
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A directory artifact is matched by identity (st_dev, st_ino from lstat), never by existence"
    - "The re-hash memo stores the observed digest, not a bool, so a hit is compared with the receipt being verified"

key-files:
  created: []
  modified:
    - installer/receipts.py
    - tests/test_receipts.py
    - tests/test_uninstall.py
    - tests/test_version_status.py

key-decisions:
  - "Directory identity is (st_dev, st_ino) rather than a content hash: one lstat, no bundle-layout knowledge, and it catches the same-version vendor reinstall a content hash would miss"
  - "Schema stays v: 1; the host holds no receipts, and an older dir artifact without identity reads as unreadable, which is the fail-closed reading"

patterns-established:
  - "Pattern: widen what a receipt recognizes (reject every path lstat would refuse) and keep what it writes narrow (only each type's checked fields)"

requirements-completed: [STATE-03]

coverage:
  - id: D1
    description: "A dir receipt artifact records (st_dev, st_ino) and matches only while the path is still that same directory, so a re-created bundle or opt dir is never removable"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_dir_fingerprint_records_its_identity"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_recreated_dir_does_not_match"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_recreated_dir_artifact_is_not_removable"
        status: pass
    human_judgment: false
  - id: D2
    description: "The reader keeps only each artifact type's checked fields, and a dir artifact without an int dev and ino makes the whole receipt unreadable"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_reader_keeps_only_each_types_fields"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_dir_artifact_without_identity_is_unreadable"
        status: pass
    human_judgment: false
  - id: D3
    description: "An artifact path lstat would refuse (embedded NUL, lone surrogate) fails closed through read, matches, fingerprint, plan_removal and the refresh pass"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_nul_artifact_path_is_unreadable"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_invalid_artifact_paths_fail_closed"
        status: pass
      - kind: integration
        ref: "tests/test_uninstall.py#test_nul_receipt_path_never_aborts_plan_removal"
        status: pass
      - kind: integration
        ref: "tests/test_version_status.py#test_nul_receipt_path_never_aborts_refresh"
        status: pass
    human_judgment: false
  - id: D4
    description: "The re-hash memo stores the observed sha256 and compares it with each receipt's own digest, so a cached success never vouches for a different expected digest"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_rehash_memo_compares_each_receipts_digest"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 22: Receipt Proof Exactness Summary

**A directory receipt artifact is proven by its `(st_dev, st_ino)` identity, the reader keeps only each type's checked fields, malformed artifact paths fail closed through read, match, plan and refresh, and the re-hash memo compares each receipt's own digest.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-10-16T20:18:54Z
- **Completed:** 2026-10-16T20:59:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- A `dir` artifact records the directory's own identity from one `lstat`, and `matches` accepts it only while the path is still that directory, so a stale receipt can never authorize removing a re-created `~/Applications` bundle or `~/.local/opt` tree
- The reader keeps exactly the fields each type is checked on (`file`: path, sha256, size, mtime_ns; `link`: path, target; `dir`: path, dev, ino) and a dir artifact without an int `dev` and `ino` makes the whole receipt unreadable
- An artifact path `lstat` would refuse (embedded NUL, lone surrogate) makes the receipt unreadable, and `fingerprint`/`matches` answer None/False on `ValueError`, proven through `plan_removal` and the refresh pass
- The re-hash memo stores the observed sha256 per `(path, size, mtime_ns)` and compares it with the receipt being verified

## Task Commits

Each task was committed atomically (tests and code together, TDD):

1. **Task 1: a dir artifact proves itself by identity, and the reader keeps only each type's fields (G2, G18)** - `7a9395d` (fix)
2. **Task 2: malformed paths fail closed everywhere, and the memo compares each receipt's own digest (G5, G6)** - `a071032` (fix)

**Plan metadata:** committed by the summary commit (docs)

## TDD RED evidence

Task 1, `uv run pytest tests/test_receipts.py tests/test_uninstall.py -q --no-cov -k "identity or recreated or only_each_types"` — 9 failed:

```
FAILED tests/test_receipts.py::test_dir_fingerprint_records_its_identity
FAILED tests/test_receipts.py::test_recreated_dir_does_not_match
FAILED tests/test_receipts.py::test_dir_artifact_without_identity_is_unreadable[identity0]
FAILED tests/test_receipts.py::test_dir_artifact_without_identity_is_unreadable[identity1]
FAILED tests/test_receipts.py::test_dir_artifact_without_identity_is_unreadable[identity2]
FAILED tests/test_receipts.py::test_dir_artifact_without_identity_is_unreadable[identity3]
FAILED tests/test_receipts.py::test_reader_keeps_only_each_types_fields
    TypeError: ReceiptArtifact.__init__() got an unexpected keyword argument 'dev'
FAILED tests/test_uninstall.py::test_recreated_dir_artifact_is_not_removable[archive]
    AssertionError: removable still held the re-created opt dir and its link
FAILED tests/test_uninstall.py::test_recreated_dir_artifact_is_not_removable[app]
```

Task 2, `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_version_status.py -q --no-cov -k "nul or invalid_artifact_paths or rehash_memo"` — 7 failed:

```
FAILED tests/test_receipts.py::test_nul_artifact_path_is_unreadable[/tmp/x\x00y]
FAILED tests/test_receipts.py::test_nul_artifact_path_is_unreadable[/tmp/\ud800]
    AssertionError: read() returned a Receipt, not None
FAILED tests/test_receipts.py::test_invalid_artifact_paths_fail_closed[file]
FAILED tests/test_receipts.py::test_invalid_artifact_paths_fail_closed[dir]
    ValueError: stat: embedded null character in path (pathlib.py:840)
FAILED tests/test_receipts.py::test_rehash_memo_compares_each_receipts_digest
    AssertionError: assert True is False  (the memo vouched for the wrong digest)
FAILED tests/test_uninstall.py::test_nul_receipt_path_never_aborts_plan_removal
FAILED tests/test_version_status.py::test_nul_receipt_path_never_aborts_refresh
    ValueError: stat: embedded null character in path
```

## Verify-command results

- Task 1 targeted run (`-k "identity or recreated or only_each_types or round_trips or real_directory or relative"`): 13 passed
- Task 2 targeted run (`-k "nul or invalid_artifact_paths or rehash_memo or matches or unreadable"`): 32 passed
- Task 1 acceptance: `grep -c st_ino installer/receipts.py` = 4, `grep -c '"ino"'` = 2, non-comment `def _artifact_str` = 0
- Task 2 acceptance: `grep -c ValueError installer/receipts.py` = 8, `grep -c fsencode` = 1, `_REHASH_MEMO: dict[tuple[str, int, int], str]` present
- Truncation guards (before each commit): test files only grew and each gained tests; suppression count stayed 487
- `make validate` exit 0 and `make test` exit 0 before each commit (4511 passed / 4 skipped after Task 1; 4519 passed / 4 skipped after Task 2; coverage 95.96%)
- Plan-level: `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_version_status.py -n auto -q --no-cov` green

## Large-file evidence (wc -l / git diff --stat)

Task 1 (against `e833961`):

```
tests/test_uninstall.py: 1947 -> 2009 lines, tests 94 -> 95
tests/test_receipts.py:   728 ->  835 lines, tests 30 -> 34
 installer/receipts.py   |  80 +++++++++++++++-------------------
 tests/test_receipts.py  | 113 ++++++++++++++++++++++++++++++++++++++++++++++--
 tests/test_uninstall.py |  62 ++++++++++++++++++++++++++
 3 files changed, 208 insertions(+), 47 deletions(-)
```

Task 2 (against `7a9395d`):

```
tests/test_uninstall.py:      2009 -> 2051 lines, tests  95 ->  96
tests/test_version_status.py: 4832 -> 4870 lines, tests 150 -> 151
tests/test_receipts.py:        835 ->  900 lines, tests  34 ->  37
 installer/receipts.py        | 42 ++++++++++++++++++----------
 tests/test_receipts.py       | 65 ++++++++++++++++++++++++++++++++++++++++++++
 tests/test_uninstall.py      | 42 ++++++++++++++++++++++++++++
 tests/test_version_status.py | 38 ++++++++++++++++++++++++++
 4 files changed, 172 insertions(+), 15 deletions(-)
```

## Planned updates (Phase 18 test-integrity rule)

- `tests/test_receipts.py` `_sample` builds its dir artifact with `receipts.fingerprint(directory, "dir")`
- `test_matches_dir_only_when_it_is_a_real_directory` builds its artifact with `receipts.fingerprint`
- the `relative artifact path` variant gained `"dev": 1, "ino": 1`, so it still fails only on relativity

## Files Created/Modified
- `installer/receipts.py` - `ReceiptArtifact.dev`/`.ino`; identity-checked dir fingerprint and match; per-type reader with `_artifact_str` deleted; NUL/encoding rejection; `(OSError, ValueError)` fail-closed fingerprint and match; observed-digest re-hash memo
- `tests/test_receipts.py` - identity, per-type reader, invalid-path and memo tests, plus the planned updates
- `tests/test_uninstall.py` - `test_recreated_dir_artifact_is_not_removable` (archive and app) and `test_nul_receipt_path_never_aborts_plan_removal`
- `tests/test_version_status.py` - `test_nul_receipt_path_never_aborts_refresh`

## Decisions Made
- Directory identity is `(st_dev, st_ino)` rather than a content hash, as the plan chose: one `lstat`, no knowledge of a bundle's internal layout, and it catches the same-version vendor reinstall a content hash would miss
- The receipt schema stays `"v": 1`: the host holds no receipts, and an older dir artifact without identity is simply unreadable, which is the fail-closed reading

## Deviations from Plan

None - plan executed exactly as written.

The app parametrization of `test_recreated_dir_artifact_is_not_removable` needed two details the plan's sketch left implicit, both inside the planned test: the app method carries the `url` key `artifact_paths` requires (without it the method yields no artifacts, so the receipt could never prove anything), and its receipt is written with `kind="app"` because `_receipt_proof` intersects the receipt with methods of the receipt's own kind. Both are what makes the test assert the plan's behavior.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Receipt proof is exact and fail closed. Plans 19-23 onward can rely on a re-created directory reading as drift, a malformed receipt reading as unproven (the existing `install receipt unreadable — treated as unproven` note, no new copy), and the re-hash memo never vouching for the wrong digest. No blockers.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
