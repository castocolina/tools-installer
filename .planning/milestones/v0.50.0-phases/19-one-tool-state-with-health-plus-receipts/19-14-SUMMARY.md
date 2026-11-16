---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "14"
subsystem: tool-state
status: complete
tags: [receipts, adoption, health, removal-proof, refresh-pass]
requires: ["19-08", "19-09", "19-10", "19-12"]
provides:
  - "receipts.adopt(tool, method, artifact, *, package)"
  - "receipt, drift, corrupt, adoption and unproven evidence in the refresh pass"
affects: [installer/version_status.py, installer/receipts.py]
tech-stack:
  added: []
  patterns:
    - "one fingerprint per adoption, re-checked under the non-reentrant receipts lock"
    - "non-match memo keyed by (path, size, mtime_ns, asset, expected digest)"
key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/version_status.py
    - tests/test_receipts.py
    - tests/test_version_status.py
key-decisions:
  - "Adoption reads the freshest cache entry of the pass (new_entry if this pass fetched, else the loaded entry). The pass never makes an extra network call for it."
  - "A raw method is the first applicable github_release method (github_repo) with raw = true. Archive, tarball and every other kind are never adopted by digest."
  - "The unproven note applies when the tool is present, owner == installer, there is no valid matching receipt (none, corrupt or drifted) and the removal plan is empty. A drifted tool therefore reads BROKEN with both 'changed since install' and the note."
  - "Locked copy lives in module constants CHANGED_SINCE_INSTALL, RECEIPT_UNREADABLE_NOTE, ADOPTED_NOTE and UNPROVEN_NOTE in installer/version_status.py."
requirements-completed: [STATE-03]
duration: ~45min
completed: 2026-10-16
actuals:
  tokens: 21000
  tasks: 3
  commits: 3
plan_head_before: 108282415734d45d4f3df277329333fbce74074c
plan_head_after: 520a94a
---

# Phase 19 Plan 14: Receipts as state evidence, digest adoption, unproven note Summary

The refresh pass now reads each tool's receipt into `ToolState.receipt`. A receipt that no longer matches the files on disk turns the tool BROKEN with `changed since install`. A receipt file that does not parse is a note and never counts as proof. A present raw `github_release` binary that has no receipt is adopted when its sha256 matches the cached release digest. Adoption needs no network call and holds up against races. Any installer-owned tool that is still left without proof gets `not proven: reinstall with r to adopt`.

## Tasks

| # | Task | Commit |
|---|------|--------|
| 1 | Receipts as state evidence: drift is BROKEN, a corrupt receipt is unproven (D-08, R4) | 877ceaa |
| 2 | `receipts.adopt` plus digest adoption in the pass (D-09, Pitfall 5, H1, H9, M10, C2-H1) | 2786d82 |
| 3 | `not proven: reinstall with r to adopt` for installer-owned tools with no proof (C2-M2) | 520a94a |

### Task 1
- `VersionRefreshService._receipt_evidence(tool, *, present, entry, platform)` returns `(receipt, broken, notes)`:
  - no receipt file: no receipt, so it tries adoption (Task 2)
  - receipt file present but `read` returns None: note `install receipt unreadable — treated as unproven`
  - `receipts.drifted(receipt)` non-empty: broken fact `changed since install`, added once
- The pass passes `receipt=` and `broken=` to `tool_state`. The receipt notes come after the owner notes and the version notes.
- New tests:
  - `test_state_carries_the_receipt`
  - `test_drifted_receipt_is_broken`
  - `test_corrupt_receipt_is_an_unproven_note`
  - `test_receiptless_kinds_have_no_receipt_reason`
  - `test_changed_link_target_is_broken_and_not_removable_end_to_end`. It runs the real `install_tool` with an rg archive, offline, through `tests.test_download.fixture_runner`. It then relinks `bin/rg` to `opt/rg/other` and checks three things: the tool reads BROKEN, `removable == ()`, and `remove_proven` refuses with `changed since the preview; not removed: …` while the link and the receipt are both kept.

### Task 2
- `receipts.adopt` holds `_WRITE_LOCK` and steps through these checks:
  1. It returns None when a receipt file or symlink already exists.
  2. It takes ONE `fingerprint(artifact.path, artifact.type)` and returns None unless that result equals `artifact`.
  3. It builds the receipt with `_build_receipt(..., (fresh,), smoke=None)` and writes it with `_write_unlocked`.
  - The AST gate passes: `['receipt_path', 'fingerprint', '_build_receipt', '_write_unlocked', 'exists', 'is_symlink']`.
- `VersionRefreshService._adopt` covers a present tool with no receipt file. It goes through these steps:
  1. It uses the first applicable `github_release` method, and only when that method has `raw = true`.
  2. It calls `resolve_target(method, ExecContext(runner=_run_nothing, platform, resolve_release=lambda _: Release(entry.latest_version, entry.digests)))`, then looks up `expected = entry.digests.get(asset)`.
  3. It takes the file path from `artifact_paths(method, managed_bin_dir)`.
  4. It runs `lstat`, then checks the memo.
  5. It takes ONE `receipts.fingerprint`.
  6. On a match it calls `receipts.adopt` with that same artifact. On a miss it adds the key to the memo.
  - `ExecutorError` and `OSError` mean no adoption.
- The removal plan is computed after adoption, so a tool adopted in this pass is already removable.
- `_run_nothing` is a runner that raises if anything calls it.

### Task 3
- After the removal plan: if the tool is present, `owner == "installer"`, `receipt is None or broken`, and `removable.removable` is empty, the pass adds `UNPROVEN_NOTE`. A tool whose receipt was removed after a failed rewrite gets no special case.

## TDD RED evidence

Task 1 (before the implementation):
```
FAILED tests/test_version_status.py::test_state_carries_the_receipt - assert None is not None
FAILED tests/test_version_status.py::test_drifted_receipt_is_broken - assert <Health.OK: 'ok'> is <Health.BROKEN: 'broken'>
FAILED tests/test_version_status.py::test_corrupt_receipt_is_an_unproven_note - 'install receipt unreadable — treated as unproven' in ('installed via GitHub release',)
FAILED tests/test_version_status.py::test_changed_link_target_is_broken_and_not_removable_end_to_end - <Health.OK: 'ok'> is <Health.BROKEN: 'broken'>
```
(`test_receiptless_kinds_have_no_receipt_reason` is a guard and passes on both sides of the change. Its first draft failed on a substring match against the tmp path, so it now matches the locked strings exactly.)

Task 2:
```
E       AttributeError: module 'installer.receipts' has no attribute 'adopt'   (x5, test_receipts.py adopt tests)
E       assert ([])                                                          (without_deadlock)
FAILED test_pass_adopts_a_raw_binary_by_cached_digest - assert None is not None
FAILED test_adoption_makes_no_network_call - 'adopted: the file matches the release checksum' in ('installed via GitHub release',)
FAILED test_adoption_mismatch_is_hashed_once - assert [] == [PosixPath('…/.local/bin/yq')]
FAILED test_adoption_memo_is_keyed_by_the_expected_digest - 'adopted: …' in ('installed via GitHub release',)
FAILED test_adoption_binds_the_digest_to_the_adopted_bytes - assert [] == [PosixPath('…/.local/bin/yq'), …]
```
(`test_no_digest_no_adoption` and both archive/raw-tarball cases are fail-closed guards and passed before the change.)

Task 3:
```
FAILED test_unproven_installer_tool_gets_the_reinstall_note - 'not proven: reinstall with r to adopt' in ('installed via GitHub release',)
FAILED test_failed_rewrite_leaves_an_archive_layout_proven_and_a_raw_binary_unproven[yq] - same
```
(The layout, manager, adopted and rg failed-rewrite cases are negative guards and passed before the change.)

## Verify results

- Task 1 `-k "carries_the_receipt or drifted_receipt or corrupt_receipt or receiptless_kinds or changed_link_target"`: 5 passed
- Task 2 `-k "adopt or adoption or digest"` across test_receipts.py and test_version_status.py: 17 passed (the gate requires ≥12). The AST gate is OK. `without_deadlock` passed 5 of 5 repetitions.
- Task 3 `-k unproven`: 9 passed (the gate requires ≥6)
- Acceptance greps:
  - `def adopt` = 1
  - `resolve_target(` = 1
  - non-comment `sha256_file(` in version_status.py = 0
  - `_write_unlocked(` in receipts.py = 3
  - `changed since install` ≥ 1
  - `not proven: reinstall with r to adopt` = 1
- Suppression guard: 593 -> 593, so no new suppressions.
- Deps: `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` is clean.
- `make validate` exited 0 and `make test` passed before every commit. On the final tree: 4400 passed, 4 skipped, 95.81% coverage.
- Plan verification `pytest tests/test_receipts.py tests/test_version_status.py tests/test_uninstall.py -n auto`: green.
- The real `~/.local/state/tools-installer/receipts` is still empty (0 entries).
- Combined-tree check: I temporarily checked out main's 19-20 files into this tree, then restored them. With those files `make test` gave 4403 passed, 4 skipped, and `make validate` exited 0. The two plans touch disjoint files.

Large-file evidence (truncation guard OK at every commit):
```
installer/version_status.py:  1279 -> 1303 -> 1372 -> 1383 lines
tests/test_version_status.py: 3578 -> 3803 -> 3949 -> 4038 lines, tests 100 -> 105 -> 112 -> 117
git diff --stat 1082824..HEAD
 installer/receipts.py        |  23 +++
 installer/version_status.py  | 110 +++++++++-
 tests/test_receipts.py       | 118 ++++++++++-
 tests/test_version_status.py | 464 ++++++++++++++++++++++++++++++++++-
 4 files changed, 709 insertions(+), 6 deletions(-)
```

## Deviations from Plan

None in scope. All changes stay inside files_modified. Notes:
- The per-task guard scripts (the truncation guard and the AST gate) ran as script files in the plan's scratch subdirectory. The sandbox refuses compound `bash -c` commands that contain git. The checks are identical.
- The `.git` commit-ledger file (protocol 0c) was not written, because the sandbox refused the compound command. The commit count is measured instead: `git rev-list --count 1082824..HEAD` = 3 before this summary.
- `test_manager_owned_tool_has_no_unproven_note` monkeypatches `version_status.resolve_ownership` to claim the yq file for brew, uv or dnf. Building real brew, uv and dnf ownership evidence would have needed three different inventory setups to prove the same branch.

## Known Stubs

None.

## Issues for the orchestrator

- No conflicts are expected with 19-20 (disjoint files). The combined tree is green.
- New reasons now appear on installer-owned rows. A present `~/.local/bin` raw binary with no receipt and no matching cached digest shows `not proven: reinstall with r to adopt` until its digest is cached or it is reinstalled. Per the plan this is by design on this host: the cache entries predate stored digests.

## Self-Check: PASSED

- installer/receipts.py `def adopt`: FOUND
- Commits 877ceaa, 2786d82 and 520a94a are ancestors of HEAD: FOUND
