---
phase: 18-registry-truth-and-drift-guard
plan: "10"
subsystem: infra
tags: [version-cache, github-release, sha256, digests]

requires:
  - phase: 18-07
    provides: Release(tag, digests) and release_resolver from one /releases/latest read
provides:
  - VersionCacheEntry.digests persisted in versions.json
  - resolve_github_release_status stores digests from one release_resolver call
  - Tolerant pair-by-pair digest decode on cache load
affects: [18-registry-truth-and-drift-guard, phase-19-pre-receipt]

actuals:
  tokens: 4500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Pair-by-pair digest decode via _digests_from_raw (not _str_map)"
    - "release_resolver(resolve_tag) in version refresh path"

key-files:
  created: []
  modified:
    - installer/version_cache.py
    - installer/version_status.py
    - tests/test_version_cache.py
    - tests/test_version_status.py

key-decisions:
  - "Store full Release.digests map (all assets), per D-05 and plan Open Question 9"
  - "Failure path preserves prior digests like latest_version"

patterns-established:
  - "Digest values in cache must be 64 lowercase hex chars after Task 2 hardening"

requirements-completed: [REG-04]

coverage:
  - id: D1
    description: "Version refresh persists Release.digests from one release read"
    requirement: REG-04
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_refresh_stores_digests_from_one_read"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_refresh_reads_tag_and_digests_from_one_api_fetch"
        status: pass
    human_judgment: false
  - id: D2
    description: "Cache save/load round-trips digests; failed refresh keeps prior digests"
    requirement: REG-04
    verification:
      - kind: unit
        ref: "tests/test_version_cache.py#test_digests_round_trip_through_the_cache_file"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_failed_refresh_keeps_the_previous_digests"
        status: pass
    human_judgment: false
  - id: D3
    description: "Pre-phase and malformed digest maps load with empty or filtered digests"
    requirement: REG-04
    verification:
      - kind: unit
        ref: "tests/test_version_cache.py#test_cache_without_digests_loads_with_empty_digests"
        status: pass
      - kind: unit
        ref: "tests/test_version_cache.py#test_malformed_digests_are_dropped_not_fatal"
        status: pass
      - kind: unit
        ref: "tests/test_version_cache.py#test_mixed_digests_keep_the_valid_entries"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Plan 18-10 Summary

**GitHub version refresh now persists per-asset SHA-256 digests in `versions.json` from the same single `/releases/latest` read that supplies the tag.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `VersionCacheEntry.digests` with encode/decode in the version cache envelope.
- Switched `resolve_github_release_status` to `release_resolver(resolve_tag)(repo)` so tag and digests share one read.
- Hardened digest decode to accept only `name -> 64 lowercase hex` pairs, dropping bad pairs without dropping the entry.

## Task Commits

1. **Task 1: refresh stores the release digests and they survive a save/load (D-05)** — `c1b60e7` (feat)
2. **Task 2: old and malformed caches load (backward compatible decode)** — `195b76d` (feat)

**Plan metadata:** (this commit) (docs: plan summary)

## TDD RED evidence

Task 1 (before implementation):

```
FAILED tests/test_version_cache.py::test_digests_round_trip_through_the_cache_file
AttributeError: 'VersionCacheEntry' object has no attribute 'digests'
FAILED tests/test_version_status.py::test_refresh_stores_digests_from_one_read
FAILED tests/test_version_status.py::test_failed_refresh_keeps_the_previous_digests
FAILED tests/test_version_status.py::test_refresh_reads_tag_and_digests_from_one_api_fetch
```

Task 2 (before hardening):

```
FAILED tests/test_version_cache.py::test_malformed_digests_are_dropped_not_fatal[digests_value3]
FAILED tests/test_version_cache.py::test_mixed_digests_keep_the_valid_entries
(mixed map kept 'worse' and uppercase 'upper' entries)
```

## Verify results

- `uv run pytest tests/test_version_cache.py tests/test_version_status.py -q --no-cov -k digest` — 4 passed (Task 1)
- `uv run pytest tests/test_version_cache.py -q --no-cov -k digests` — 7 passed (Task 2)
- `uv run pytest tests/test_version_status.py -n auto -q --no-cov` — 47 passed
- `make validate` — pass
- `make test` — 3691 passed, 4 skipped, coverage 96.01%

## Deviations from Plan

- **Pyright private import:** Used `VersionCacheEntry(latest_version=None, checked_at=None).digests` on the failure path instead of importing `_empty_digest_map` across modules (reportPrivateUsage).
- **test_version_status.py edits:** Large-file `StrReplace` once truncated the file; tests were re-applied via a one-off patch script under `.superpowers/sdd/18-10-PLAN/` (removed after use).

## Issues for orchestrator

- If automated editing targets `tests/test_version_status.py`, prefer patch scripts or small hunks — a bad replace truncated the file mid-function once in this run.

## Next Phase Readiness

Phase 19 can compare pre-receipt binaries against cached digests without an extra GitHub fetch.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
