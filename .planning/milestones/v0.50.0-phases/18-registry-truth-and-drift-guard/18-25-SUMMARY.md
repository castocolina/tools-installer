---
phase: 18-registry-truth-and-drift-guard
plan: "25"
subsystem: testing
tags: [verify-registry, github-api, drift-guard, pytest]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: plan 18-24 _member_present and prior verify_registry baseline
provides:
  - Identity-preserving shared-URL propagation and single-fetch 404 caching in check_registry
  - Memoized release reads with VersionError stored per repo; pinned tools survive API failures
  - resolve_github_release wraps all read/parse failures; unredirected GitHub token header
  - _TRANSPORT_ERRORS for inconclusive transport; malformed registry rows become drift findings
affects: [18-26, 18-27]

actuals:
  tokens: ~16000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "dataclasses.replace for URL-wide finding propagation preserves per-target identity"
    - "release_memo dict stores Release | VersionError for one attempt per repo per run"

key-files:
  created: []
  modified:
    - installer/verify_registry.py
    - installer/versions.py
    - tests/test_verify_registry.py
    - tests/test_versions.py

key-decisions:
  - "Shared URL-wide findings copy status/reason from the first target but always replace tool_id, member, and platforms from each target"
  - "Failed release reads are memoized like successes so platform expansion does not re-hit the API"

patterns-established:
  - "_TRANSPORT_ERRORS tuple centralizes inconclusive transport handling across HEAD, checksum, and download paths"

requirements-completed: [REG-03, REG-04]

coverage:
  - id: D1
    description: Shared-URL checksum/archive failures report per tool; 404 URLs download once; gzip fixtures clock-stable
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_a_shared_url_failure_keeps_every_target_identity
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_a_url_that_404s_on_download_is_fetched_once
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_gzip_fixtures_do_not_depend_on_the_clock
        status: pass
    human_judgment: false
  - id: D2
    description: Release reads once per repo; pinned tools report API failures without crashing; token not forwarded on redirect
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_pinned_release_read_failure_is_reported_not_raised
        status: pass
      - kind: unit
        ref: tests/test_versions.py#test_resolve_github_release_wraps_every_read_failure
        status: pass
    human_judgment: false
  - id: D3
    description: Transport and malformed registry/checksum paths are inconclusive or drift, never crash; dead branches removed
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_head_incomplete_read_is_inconclusive
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_tarball_without_url_is_drift_not_a_crash
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Plan 18-25: Registry truth fixes (shared URLs, release reads, transport)

**Weekly verify-registry now attributes shared-URL failures to every affected tool, memoizes flaky GitHub release reads, and treats transport glitches as inconclusive instead of aborting the run.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 3 (+ summary commit)
- **Files modified:** 4 production/test files

## Task Commits

1. **Task 1: shared-URL identity + 404 once + gzip fixtures** — `78f77ac`
2. **Task 2: release memo, VersionError wrapping, unredirected token** — `28777f0`
3. **Task 3: _TRANSPORT_ERRORS, drift for malformed rows, dead branch removal** — `4b7680d`

## Finding disposition

| ID | Source | Outcome | Commit | Test |
|----|--------|---------|--------|------|
| HIGH shared-URL identity | opencode | fixed | 78f77ac | `test_a_shared_url_failure_keeps_every_target_identity` |
| #10 404 re-download | ponytail | fixed (same-URL part) | 78f77ac | `test_a_url_that_404s_on_download_is_fetched_once` |
| MEDIUM gzip mtime | opencode | fixed | 78f77ac | `test_gzip_fixtures_do_not_depend_on_the_clock` |
| HIGH pinned API abort | opencode | fixed | 28777f0 | `test_pinned_release_read_failure_is_reported_not_raised` |
| M1 release memo | ponytail | fixed | 28777f0 | `test_failed_release_read_is_attempted_once_per_repo` |
| M2 newer-stable swallow | ponytail | fixed | 28777f0 | `test_pinned_release_not_found_is_drift` |
| WR-04 root (resolve) | review | fixed | 28777f0 | `test_resolve_github_release_wraps_every_read_failure` |
| IN-08 token redirect | review | fixed | 28777f0 | `test_github_token_is_not_forwarded_on_a_redirect` |
| WR-04 check_registry | review | fixed | 4b7680d | incomplete_read / without_url / binary_checksum tests |
| WR-05 branches | review | covered | 4b7680d | checksum_sidecar_* / asset_get_404_* |
| IN-02 dead branches | review | fixed | 4b7680d | `_full_verify` removed; ExecutorError handler fixed |
| #6–#8 dead code | ponytail | fixed | 4b7680d | same commit |

Cross-archive-mode #10 listing dedup deferred to plan 18-27 per plan text.

## TDD RED evidence (trimmed)

**Task 1** (`uv run pytest … -k "do_not_depend_on_the_clock or keeps_every_target_identity or fetched_once"`):

- `test_gzip_fixtures_do_not_depend_on_the_clock`: `AssertionError` at index 4 (mtime in gzip header)
- `test_a_shared_url_failure_keeps_every_target_identity`: `assert {'a'} == {'a', 'b'}`
- `test_a_url_that_404s_on_download_is_fetched_once`: initially `ValueError` missing sha256 on pinned tarball (test fixed before GREEN); after pin fix would have failed on download count

**Task 2** (`-k "release_read_failure or …"`):

- Pinned tests: `VersionError` escaped from `_github_pin_mismatch` / `tracked_release`
- `test_failed_release_read_is_attempted_once_per_repo`: `assert 8 == 1`
- `test_resolve_github_release_wraps_every_read_failure[incomplete]`: `IncompleteRead` escaped
- `[not_a_dict]`: `AttributeError: 'list' object has no attribute 'get'`
- `test_github_token_is_not_forwarded_on_a_redirect`: redirect still had `Bearer t`

**Task 3** (four bug tests):

- `IncompleteRead` propagated from `head_once` / `tracked_download`
- `test_tarball_without_url_is_drift_not_a_crash`: `ExecutorError` re-raised from handler calling `pinned_url` again
- `test_binary_checksum_file_is_drift_not_a_crash`: `UnicodeDecodeError` on `read_text()`

## Mutation RED (WR-05)

- **checksum sidecar 404 → inconclusive:** one-line status flip in checksum `HTTPError` 404 branch; `test_checksum_sidecar_404_is_drift` failed (`drift` vs `inconclusive`); reverted before commit.

(Other three coverage tests pass on correct branches; same mutate/revert pattern verified for 404 branch only in-session.)

## Verify commands

- Task 1/2/3 per-plan `uv run pytest` filters: exit 0 after each task
- Final: `make validate && make test` — 3917 passed, coverage 95.48%

## Line-count / diff-stat evidence

After Task 1 (pre-commit): `tests/test_verify_registry.py` 3261 lines, `installer/verify_registry.py` 1735 lines; diff +175/-13.

Final: `installer/verify_registry.py` 1738 lines; `tests/test_verify_registry.py` 3623 lines.

## Deviations from Plan

- **Test file edit safety:** First `StrReplace` on `tests/test_verify_registry.py` truncated the file (~3121 → ~1873 lines). Restored via `git checkout HEAD -- tests/test_verify_registry.py` and re-applied edits with an out-of-repo Python patch script. No logic deviation from plan.
- **404 shared-URL test:** Added required `sha256` pins on pinned tarball URLs so registry loads (loader requires 64 hex for `{ver}` tarballs).

Otherwise none.

## Issues for orchestrator

- Pi/Cursor `StrReplace` on `tests/test_verify_registry.py` can truncate mid-file; use patch scripts or small hunks for files >~1000 lines.

---
*Phase: 18-registry-truth-and-drift-guard · Plan: 25 · Completed: 2026-10-15*
