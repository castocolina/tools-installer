---
phase: 18-registry-truth-and-drift-guard
plan: "28"
subsystem: installer
tags: [security, apps, tarfile, lzma, zlib, drift, verify-registry, tdd]
requires:
  - phase: 18-27
    provides: app install/update staging state machine and verify-registry drift reporting
provides:
  - staged app bundles that are symlinks or non-directories are refused before smoke/swap (T-18-56)
  - corrupt xz/gz streams are archive-unreadable drift instead of a crash (T-18-69)
affects: [security re-audit, weekly drift job]
actuals:
  tokens: 13000
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - installer/apps.py
    - installer/verify_registry.py
    - tests/test_apps.py
    - tests/test_verify_registry.py
key-decisions:
  - "CLI containment root stays staged_bundle (tighter than extract_root); the real-directory check on the bundle closes the actual bypass; guard case fails under the extract_root mutation (per plan prohibition)"
  - "gzip.BadGzipFile not added: no reproducible RED (getnames() never reaches the CRC trailer); mid-stream BadGzipFile is an OSError already handled as inconclusive"
patterns-established: []
requirements-completed: [REG-03, REG-05]
coverage:
  - id: D1
    description: "A staged app bundle that is a symlink or not a real directory is refused before staged_member, smoke_binary and os.replace, for install and update"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_apps.py#test_staged_bundle_escape_is_refused_and_moves_nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "A corrupt .tar.xz (lzma.LZMAError) or corrupt .tar.gz deflate stream (zlib.error) is drift 'archive unreadable as <mode>' and check_registry returns a report"
    requirement: REG-03
    verification:
      - kind: unit
        ref: "tests/test_verify_registry.py#test_corrupt_archive_is_drift[xz_corrupt_stream]"
        status: pass
      - kind: unit
        ref: "tests/test_verify_registry.py#test_corrupt_archive_is_drift[gz_bad_deflate_block]"
        status: pass
    human_judgment: false
duration: 22min
completed: 2026-10-15
status: complete
---

# Phase 18-28: Registry truth and drift guard — gap closure Summary

**A staged app bundle that is a symlink or a non-directory is refused before smoke/link/swap (T-18-56), and a corrupt xz/gz stream is archive-unreadable drift instead of a crash (T-18-69).**

## Performance

- **Duration:** 22 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- T-18-56 closed: `_stage_and_swap_app` rejects a staged bundle that `is_symlink()` or is not a directory, before `staged_member`, `smoke_binary` and `os.replace`, covering install and update, with and without a CLI.
- T-18-69 closed: `lzma.LZMAError` and `zlib.error` joined the archive-listing `except` in `check_registry`, so a corrupt stream flows into the existing `archive unreadable as <mode>` drift branch; `main` never exits 70 for it.
- Containment root pinned: the `cli_resolving_to_a_zip_sibling` guard case fails when the root is mutated to `extract_root` (recorded mutation run), so the prohibition against loosening the root is enforced by a test.

## Task Commits

1. **Task 1: refuse a staged app bundle that is not a real directory (T-18-56)** - `58abaf9` (fix)
2. **Task 2: a corrupt xz or gz stream is archive-unreadable drift (T-18-69)** - `b4af643` (fix)

## TDD RED evidence

### Task 1 (venv Python 3.12.12)
```
uv run pytest tests/test_apps.py -q --no-cov -k staged_bundle_escape
E       Failed: DID NOT RAISE <class 'installer.executors.ExecutorError'>
FAILED tests/test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing[symlink_with_cli]
FAILED tests/test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing[symlink_without_cli]
FAILED tests/test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing[regular_file_without_cli]
3 failed, 1 passed            # the sibling guard case already passed
```

### Task 2 (`uv run --frozen python -V` → Python 3.12.12)
```
uv run pytest tests/test_verify_registry.py -q --no-cov -k corrupt_archive_is_drift
E               _lzma.LZMAError: Corrupt input data
E               zlib.error: Error -3 while decompressing data: invalid block type
FAILED tests/test_verify_registry.py::test_corrupt_archive_is_drift[gz_bad_deflate_block]
FAILED tests/test_verify_registry.py::test_corrupt_archive_is_drift[xz_corrupt_stream]
2 failed, 3 passed
```

### Task 1 mutation run (after the fix, then reverted)
`staged_member(staged_bundle, cli)` → `staged_member(extract_root, f"{app}/{cli}")`:
```
FAILED tests/test_apps.py::test_staged_bundle_escape_is_refused_and_moves_nothing[cli_resolving_to_a_zip_sibling]
```
Reverted; tree verified identical (`git diff --stat` back to +66/-2).

## Verify-command results
- Task 1: `-k staged_bundle_escape` → 4 passed; tests/test_apps.py + test_engine.py + test_uninstall.py all pass; structure guard (check before smoke/swap, containment root unchanged) OK; shrink guard OK.
- Task 2: `-k corrupt_archive_is_drift` → 5 passed; tests/test_verify_registry.py + test_verify_registry_workflow.py pass; shrink guard, last-line and reason-count guards OK.
- `make validate` and `make test` green on each commit tree (final: 3955 passed, 4 skipped, coverage 95.68%).
- `git diff --exit-code 8fb370d -- pyproject.toml uv.lock` → 0. No new `type: ignore`/`noqa`/`nosec` in the diff.

## Files Created/Modified
- `installer/apps.py` (266 → 268 lines) — real-directory check with rationale comment
- `installer/verify_registry.py` (1655 → 1661 lines) — `lzma`/`zlib` imports and except entries
- `tests/test_apps.py` (848 → 912 lines) — new parametrized escape test (4 cases)
- `tests/test_verify_registry.py` (4078 → 4105 lines) — `_corrupt_xz_tar_bytes`, `_corrupt_gz_tar_bytes`, two new parametrize cases, extension-map template

`git diff --stat` per commit: `58abaf9` +66/-2; `b4af643` +35/-2. Plan total vs `8fb370d~1`: +101/-4 across exactly the plan's four files.

## Decisions Made
- Kept `staged_member(staged_bundle, cli)` (the plan's prohibition); the real-directory check on the bundle closes the bypass, and the guard case proves the `extract_root` alternative fails.
- Followed the plan's "not taken" decision on `gzip.BadGzipFile`.

## Deviations from Plan

None - plan executed exactly as written.

## Security re-audit line
- T-18-56: closed. Code: `installer/apps.py` `staged_bundle.is_symlink() or not staged_bundle.is_dir()` check (before `smoke_binary` and `os.replace`). Test: `tests/test_apps.py#test_staged_bundle_escape_is_refused_and_moves_nothing` (3 RED cases + 1 guard case with recorded mutation).
- T-18-69: closed. Code: `installer/verify_registry.py` listing `except` tuple now includes `lzma.LZMAError` and `zlib.error`. Tests: `test_corrupt_archive_is_drift[xz_corrupt_stream]`, `[gz_bad_deflate_block]`.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both open medium threats in 18-SECURITY.md are closed with code + tests; the security re-audit can record the new dispositions.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
