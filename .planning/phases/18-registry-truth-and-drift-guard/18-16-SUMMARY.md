---
phase: 18-registry-truth-and-drift-guard
plan: "16"
subsystem: infra
tags: [download, sha256, curl, registry, update]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: staged _fetch_verified install path and release digests (plan 18-07)
provides:
  - One staged plain-argv fetch for every github_release and tarball install
  - pinned_url(method) for {ver} tarball URLs
  - Installer-owned updates pass release_resolver(resolve_tag) for digest verification
affects: [18-09, 18-11, 18-12]

actuals:
  tokens: 9000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "All download installs share staging + _fetch_verified; no shell URL interpolation"

key-files:
  created: []
  modified:
    - installer/download.py
    - installer/update.py
    - tests/test_download.py
    - tests/test_update.py
    - tests/test_engine.py

key-decisions:
  - "pinned_url lives in download.py (not assets.py) because it takes a Method and raises ExecutorError via require_str; assets stays pure string templating (plan deviation, 18-PATTERNS)"

patterns-established:
  - "Declared tarball sha256 is always verified when present, including unpinned URLs built directly as Method"

requirements-completed: [REG-04]

coverage:
  - id: D1
    description: Every download install uses staged plain-argv curl (no sh -c pipeline)
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_download.py#test_unverified_install_fetches_into_staging_with_a_plain_argv
        status: pass
    human_judgment: false
  - id: D2
    description: Updates verify release digests and reject wrong API digests end-to-end
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_download.py#test_update_verifies_the_release_digest
        status: pass
      - kind: unit
        ref: tests/test_update.py#test_installer_owned_update_rejects_a_wrong_api_digest
        status: pass
    human_judgment: false
  - id: D3
    description: Pinned tarball URLs render from version and verify against sha256
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_download.py#test_pinned_tarball_is_verified_against_its_sha256
        status: pass
      - kind: unit
        ref: tests/test_download.py#test_supplied_sha256_is_never_discarded
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 16 Summary

**All download installs and installer-owned updates share staged plain-argv fetch and digest verification; pinned tarballs render `{ver}` URLs and check declared sha256.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Removed `_install_unverified` shell pipeline; every install uses `tempfile.mkdtemp` + `_fetch_verified` + `_place_verified` / `_replace_raw`.
- `_update_installer_owned` builds `ExecContext` with `resolve_release=release_resolver(resolve_tag)` so updates digest-check like install.
- Added public `pinned_url(method)` and tarball-branch `sha256` verification for pinned and directly built methods.

## Task Commits

1. **Task 1: staged plain-argv install + update digest wiring** — `5e2b476` (feat)
2. **Task 2: pinned tarball url + sha256** — `783c729` (feat)

**Plan metadata:** (this commit) `docs(18-16): plan summary`

## TDD RED evidence (Task 2, trimmed)

```
FAILED tests/test_download.py::test_pinned_url_renders_the_version - Attribut...
FAILED tests/test_download.py::test_pinned_tarball_is_verified_against_its_sha256
FAILED tests/test_download.py::test_supplied_sha256_is_never_discarded
E       Failed: DID NOT RAISE <class 'installer.checksums.ChecksumMismatch'>
```

## Verify results

- Task 1: `uv run pytest tests/test_download.py tests/test_update.py -q --no-cov -k "plain_argv or verifies_the_release_digest or passes_the_release_resolver or wrong_api_digest"` → 4 passed
- Task 1 broader: `uv run pytest tests/test_download.py tests/test_update.py tests/test_apps.py tests/test_engine.py tests/test_uninstall.py -q --no-cov` → pass
- Task 2: `uv run pytest tests/test_download.py -q --no-cov -k "pinned or never_discarded or unhashed_tarball"` → 4 passed
- Final: `make validate && make test` → pass (3698 passed, coverage 95.99%)
- Grep: `_install_unverified` count 0; `"sh", "-c"` count 0 in `installer/download.py`; `resolve_release=release_resolver(resolve_tag)` count 1; `def pinned_url` count 1

## Deviations from Plan

- **`tests/test_engine.py`:** Updated two github_release ladder tests to assert plain `curl`/`tar` argv instead of `sh -c` (required by Task 1 verify including `tests/test_engine.py`; not listed in `files_modified`).
- **`tests/test_download.py`:** Rewrote existing shell-pipeline install tests to plain-argv + staging assertions in the Task 1 commit (same commit as behavior change).
- **`pinned_url` placement:** Implemented in `installer/download.py` per plan deviation note (not `assets.py`).

## Issues Encountered

None blocking. Large `tests/test_download.py` edits were applied via a one-off Python patch script to avoid editor truncation.

## User Setup Required

None.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
