---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "32"
subsystem: receipts
tags: [receipts, sha256, key-file, drift, uninstall, update]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "19-22 directory identity proof (st_dev, st_ino), replaced here by Ledger L-19-31"
provides:
  - "A dir receipt artifact is the sha256 of one key file (the linked archive member, or Contents/Info.plist for an .app), never a device or inode"
  - "Dir-only drift is unproven and not removable, never BROKEN and never an update refusal; file and link drift stay BROKEN and refused"
affects: [19-33, uninstall, update, version-status]

actuals:
  tokens: 6800
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Dir proof is one regular key file's digest; _safe_key refuses absolute, .., empty, NUL and unencodable keys"
    - "Dir-only drift returns the unproven note from _receipt_evidence and is excluded from the update gate"

key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/uninstall.py
    - installer/version_status.py
    - installer/update.py
    - tests/test_receipts.py
    - tests/test_uninstall.py
    - tests/test_engine.py
    - tests/test_version_status.py
    - tests/test_update.py

key-decisions:
  - "Followed L-19-31 exactly: a re-created directory with identical key-file bytes matches; a changed, missing or symlinked key file never does"
  - "Kept receipt schema v: 1; the host receipts dir is empty, so no migration"

patterns-established:
  - "Pattern: every dir fingerprint passes key= (key=None included); a dir without a safe key and its three digest fields makes the whole receipt unreadable"

requirements-completed: [STATE-03, STATE-02]

coverage:
  - id: D1
    description: "A dir artifact records one key file's sha256, size and mtime_ns, never a device or inode, and a re-created dir with the same bytes matches"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_dir_fingerprint_records_its_key_file"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_dir_recreated_with_the_same_key_file_matches"
        status: pass
    human_judgment: false
  - id: D2
    description: "An old dev/ino dir artifact, an unsafe key, and a changed, missing or symlinked key file are unproven"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_old_shape_dir_artifact_is_unreadable"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_unsafe_dir_keys_never_fingerprint"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_dir_with_a_changed_or_missing_key_file_does_not_match"
        status: pass
    human_judgment: false
  - id: D3
    description: "record keys an archive by the linked member and an app by Contents/Info.plist, which is only read"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_record_keys_each_dir_by_its_key_file"
        status: pass
    human_judgment: false
  - id: D4
    description: "A replaced key file drops removal proof; identical key-file bytes keep the directory and its link removable"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_replaced_dir_artifact_is_not_removable"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_dir_recreated_with_the_same_key_file_stays_removable"
        status: pass
    human_judgment: false
  - id: D5
    description: "Dir-only drift is unproven, not BROKEN, and an update runs and re-records the receipt"
    requirement: STATE-02
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_dir_drift_is_unproven_not_broken"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_partially_gone_receipt_is_unproven_not_broken"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_dir_drift_does_not_block_an_update"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 32: Key-file directory proof Summary

**A directory receipt is proven by one key file's sha256, so a reboot or remount no longer marks every archive BROKEN, and a vendor-updated directory stays updatable while file and link drift stay refused.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-16T23:41:06Z
- **Completed:** 2026-10-16T23:49:02Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Replaced the `(st_dev, st_ino)` directory proof with the sha256, size and mtime_ns of one key file: the archive member the bin link resolves to, or `Contents/Info.plist` for an `.app`, which is only read.
- An old-shape `dev`/`ino` artifact, an unsafe key, and a changed, missing or symlinked key file make the directory unproven; a re-created directory with the same key-file bytes still matches and stays removable.
- Directory-only drift shows `not proven: reinstall with r to adopt` once, is not removable, is not BROKEN, and does not refuse an update; the update re-records the receipt. File and link drift stay `changed since install` and stay refused.

## Task Commits

Each task was committed atomically (tests and code together; the RED run happened before the implementation):

1. **Task 1: a dir artifact is proven by one key file, never by device or inode** - `7e5c695` (fix)
2. **Task 2: dir-only drift loses the removal proof but is never BROKEN and never refuses an update** - `25ad9ab` (fix)

## Files Created/Modified

- `installer/receipts.py` - `APP_KEY_FILE`, `ReceiptArtifact.key` (no `dev`/`ino`), `link_key`, `_safe_key`, `_dir_key`, `_file_fingerprint`, `_file_matches`; key-file dir fingerprint, match and reader; `record` keys each dir
- `installer/uninstall.py` - the layout proof fingerprints the opt dir with `key=receipts.link_key(opt, link)`
- `installer/version_status.py` - `_receipt_evidence` turns only non-dir drift into BROKEN; dir-only drift returns `UNPROVEN_NOTE`
- `installer/update.py` - `UpdateService.run` refuses only when a non-dir artifact drifted
- `tests/test_receipts.py`, `tests/test_uninstall.py`, `tests/test_engine.py`, `tests/test_version_status.py`, `tests/test_update.py` - the new proof and the planned fixture updates

## Decisions Made

None - followed plan as specified. The only ledgered ruling is the orchestrator's: execute on `main` rather than a worktree.

## Deviations from Plan

None - plan executed exactly as written.

### Planned updates applied (Task 1, Phase 18 test-integrity rule)

- `tests/test_receipts.py`: `_sample` plants `k` and fingerprints with `key="k"`; the relative-path variant carries `key` plus the three digest fields; `test_fingerprint_records_each_artifact_type` plants `k`, asserts `dir_fp.key == "k"` and passes `key="k"` to both dir None-checks; `test_matches_dir_only_when_it_is_a_real_directory` keys `k` and replaces the dir with a symlink to a dir holding the same `k`; `test_record_skips_missing_artifacts` plants `Contents/Info.plist` and expects `key=APP_KEY_FILE`; `test_invalid_artifact_paths_fail_closed` uses `key="k"` and `fingerprint(path, kind, key="k")`; `test_reader_keeps_only_each_types_fields` reads the dir back as `key="k"` with its digest, dropping `target`, `dev` and `ino`. Deleted `test_dir_fingerprint_records_its_identity`, `test_recreated_dir_does_not_match` and `test_dir_artifact_without_identity_is_unreadable`, and retitled the section comment.
- `tests/test_uninstall.py`: `write_receipt` gained keyword-only `dir_key` and keys a dir by that, else `APP_KEY_FILE` for an app, else `link_key`; `_plant_retyped_yq` passes `dir_key="decoy"`; the three `remove_paths` / failed-delete sites key `fd`, `member` and `gone`; the swap test rewrites `member` after the swap; `test_plan_removal_keeps_each_proven_artifact` uses `key="rg"`; `recreate_opt` rewrites `fd` after `_recreate_over`; `_recreate_over`'s docstring now says it puts a new directory at the same path.
- `tests/test_engine.py`: the archive receipt expects `key="rg-x/rg"`; the app `place()` writes `Contents/Info.plist` and the expectation uses `key=APP_KEY_FILE`.

## TDD RED evidence

### Task 1

`uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py -q --no-cov -k "key_file or old_shape or unsafe_dir_keys or link_key or record_keys_each_dir or replaced_dir_artifact or same_key_file"` → exit 1, 21 failed.

- `test_dir_fingerprint_records_its_key_file`: `TypeError: fingerprint() got an unexpected keyword argument 'key'`
- `test_dir_recreated_with_the_same_key_file_matches`: same `TypeError`
- `test_dir_with_a_changed_or_missing_key_file_does_not_match[rewritten|removed|symlinked]`: same `TypeError`
- `test_old_shape_dir_artifact_is_unreadable[shape0]` (`{"dev": 7, "ino": 9}`): `AssertionError: assert Receipt(... dev=7, ino=9) is None` — the old reader still accepted the 19-22 shape
- `test_unsafe_dir_keys_never_fingerprint`: same `TypeError`
- `test_link_key_is_the_member_inside_the_dir`: `AttributeError: module 'installer.receipts' has no attribute 'link_key'`
- `test_record_keys_each_dir_by_its_key_file[archive|app]`: `AttributeError: 'ReceiptArtifact' object has no attribute 'key'`
- `test_record_keys_each_dir_by_its_key_file[app-without-info-plist]`: `assert ['dir', 'link'] == ['link']`
- `test_replaced_dir_artifact_is_not_removable` and `test_dir_recreated_with_the_same_key_file_stays_removable`: `no attribute 'link_key'` (archive) and `no attribute 'APP_KEY_FILE'` (app)

### Task 2

`uv run pytest tests/test_version_status.py tests/test_update.py -q --no-cov -k "dir_drift or partially_gone"` → exit 1, 3 failed.

- `test_dir_drift_is_unproven_not_broken`: `assert <Health.BROKEN> is not <Health.BROKEN>` (reasons started `changed since install`)
- `test_partially_gone_receipt_is_unproven_not_broken`: same BROKEN assertion
- `test_dir_drift_does_not_block_an_update`: `assert 'unsupported' == 'updated'`

## Verify results

- Task 1: `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py -q --no-cov` → all passed. The `-k` filter passed 28 (the plan's floor was 22: 18 in test_receipts.py, 4 in test_uninstall.py). Shrink guard: `test_receipts.py` 1058 → 1220 lines, tests 43 → 47; `test_uninstall.py` 2252 → 2287, tests 101 → 102; `test_engine.py` 2055 → 2057. Suppressions 483 → 483. `git diff --stat`: receipts.py +241/−, uninstall.py 5, test_engine.py 6, test_receipts.py +248/−, test_uninstall.py 93. `make validate` exit 0; `make test` 4591 passed, 4 skipped, coverage 96.01%.
- Task 2: `uv run pytest tests/test_version_status.py tests/test_update.py -q --no-cov -k "receipt or drift or partially_gone or unproven or adopt or update_service"` → 60 passed. The `dir_drift or partially_gone` filter passed 3. Shrink guard: `test_version_status.py` 5177 → 5199, tests 163 → 164; `test_update.py` 1513 → 1544, tests 60 → 61. `git diff --stat`: update.py 6, version_status.py 12, test_update.py +31, test_version_status.py +38/−8. `make validate` exit 0; `make test` 4593 passed, 4 skipped, coverage 96.01%.
- Acceptance greps: `dev`/`ino` references in `installer/receipts.py` (comments excluded) = 0; `APP_KEY_FILE` = 1; `def link_key` = 1; `receipts.link_key(` in uninstall.py = 1; no `fingerprint(…"dir")` without `key=`; the three deleted identity tests = 0; `artifact.type != "dir"` = 1 in each of version_status.py and update.py; `test_partially_drifted_receipt_stays_broken` = 0.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` clean: no new dependency.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 19-33 owns the quarantine removal (H2) and the forced final re-hash (H3). `_receipt_proof` still drops a receipt on any drift, including dir drift (L-19-14), and `remove_paths` is unchanged.
- The host receipts directory held 0 receipts, so schema stays `"v": 1` and every previously written 19-22 dir artifact now reads as unproven.

## Self-Review

Self-review of `972243f..25ad9ab` (no subagent: the orchestrator forbids extra agents and branches). No Critical or Important findings. Deferred minors: none. The plan's `one` helper inside `record` and the `_file_fingerprint` extraction are the implementation the tests require, not extra behavior.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
