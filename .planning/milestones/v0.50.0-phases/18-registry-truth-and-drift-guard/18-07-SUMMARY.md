---
phase: 18-registry-truth-and-drift-guard
plan: "07"
subsystem: installer
tags: [github, sha256, release, download, verification]
requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: checksum mismatch ladder and download executors from plans 18-01..18-03
provides:
  - Release snapshot reader (tag + digests from one API fetch)
  - Digest-backed install path via plain curl argv and staging hash
  - InstallOutcome.unverified_reason and render_verification reason line
affects: [18-09, 18-10, 18-12, 18-16]
actuals:
  tokens: 42000
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - "release_resolver(resolve_tag) identity selects resolve_github_release in production"
    - "install_download returns None when verified, str reason when unverified"
key-files:
  created: []
  modified:
    - installer/versions.py
    - installer/download.py
    - installer/engine.py
    - installer/render.py
    - tests/test_download.py
    - tests/test_engine.py
    - tests/test_versions.py
    - tests/test_render.py
key-decisions:
  - "Derive resolve_release from resolve_tag via release_resolver instead of a second entry-point parameter"
  - "fixture_runner plain-curl writes only filenames present in the test files dict (missing-asset error tests)"
requirements-completed: [REG-04]
coverage:
  - id: D1
    description: Unchecksummed github_release assets verified from API digest in one snapshot
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_download.py#test_release_digest_verifies_an_unchecksummed_asset
        status: pass
      - kind: unit
        ref: tests/test_engine.py#test_default_resolver_verifies_against_the_api_digest
        status: pass
    human_judgment: false
  - id: D2
    description: Digest mismatch fails closed with nothing linked
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_engine.py#test_digest_mismatch_fails_with_nothing_linked
        status: pass
    human_judgment: false
  - id: D3
    description: No-digest and tarball installs flagged unverified with reason on screen
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_render.py#test_render_verification_prints_the_unverified_reason
        status: pass
    human_judgment: false
duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 07 Summary

**GitHub release installs now verify against one `/releases/latest` snapshot (tag + digests), with plain-curl staging, mismatch fail-closed, and unverified reasons through outcomes and the verification summary.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Added `Release`, `resolve_github_release`, and `release_resolver`; `resolve_github_tag` delegates without changing callers.
- Generalized `_fetch_verified` (install + update); `install_download` returns `None` when verified or a reason string when not; tarball targets always carry the unpinned-url reason.
- Wired `ExecContext.resolve_release`, `InstallOutcome.unverified_reason`, and `render_verification` reason lines.

## Task Commits

1. **Task 1: one release snapshot verifies an unchecksummed asset end to end** — `e0d0fc5` (feat)
2. **Task 2: well-formed digests and unverified reason printed** — `3aa7fca` (feat)

## TDD RED evidence (Task 1, trimmed)

Before implementation, new tests failed on missing symbols and return-type contract, for example:

```
ImportError: cannot import name 'resolve_github_release' from 'installer.versions'
AttributeError: module 'installer.download' has no attribute 'resolve_target'
AssertionError: assert True is None  # install_download still returned bool
```

## Verify results

- Task 1 filter: `uv run pytest tests/test_download.py tests/test_engine.py -q --no-cov -k "release_digest or digest_mismatch or unverified or verifies_against_the_api_digest"` → 11 passed
- Task 1 broader: `uv run pytest tests/test_versions.py tests/test_download.py tests/test_engine.py tests/test_apps.py tests/test_update.py tests/test_session.py -q --no-cov` → all passed
- Task 2 filter: `uv run pytest tests/test_versions.py tests/test_render.py -q --no-cov -k "one_snapshot or delegates or release_resolver or unverified_reason"` → 5 passed
- Final: `make validate && make test` → exit 0 (3665 passed, coverage 96.04%)

## Deviations from Plan

- **Verified-path download tests** rewritten in Task 1 commit: assert plain `curl -fsSL -o …` argv pairs and on-disk staging instead of a single `sh -c` two-curl string (same commit as implementation).
- **`test_install_download_returns_false_when_unverified`** replaced by **`test_unhashed_tarball_install_is_unverified_with_a_reason`** (exact tarball reason string).
- **`fixture_runner`**: plain `curl -o` writes only when the basename exists in the test `files` dict (preserves missing-asset / unreadable-checksum error tests).

## Issues Encountered

None blocking. Pyright required explicit casts when parsing GitHub `assets` JSON in strict mode.

## Next Phase Readiness

Plan 18-16 can delete the no-hash shell pipeline and add pinned tarball verification; 18-12 can import public `resolve_target`; 18-10 can cache `Release.digests`.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
