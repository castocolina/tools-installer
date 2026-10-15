---
phase: 18-registry-truth-and-drift-guard
plan: "09"
subsystem: installer
tags: [smoke, download, executors, registry, REG-05]
requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: staged update swap, checksum verification, engine install ladder
provides:
  - run_output_with_stderr and smoke_binary on the run_output path
  - Archive/raw install smoke before atomic swap; staged_member containment
  - Fresh-install rollback removes dangling bin links after post-relink failure
affects: [18-11, 18-18, 18-19, 18-20]
actuals:
  tokens: 22000
  tasks: 2
  commits: 3
tech-stack:
  added: []
  patterns:
    - "Smoke runs only after verification; loader patterns checked in stderr even on exit 0"
    - "Install uses staged .new tree for archives and raw siblings before os.replace"
key-files:
  created: []
  modified:
    - installer/run.py
    - installer/executors.py
    - installer/download.py
    - tests/test_run.py
    - tests/test_executors.py
    - tests/test_download.py
    - tests/test_engine.py
key-decisions:
  - "fixture_runner writes default curl payloads as a tiny #!/bin/sh script only when files is empty; partial file maps keep missing names absent for checksum error tests"
  - "Directory-member update failures now fail at staged_member before swap (live tree unchanged without a restored message)"
patterns-established:
  - "method_smoke_argv reads smoke_argv from Method.params; argv[0] is always the installed binary path"
requirements-completed: [REG-05]
coverage:
  - id: D1
    description: "Shared smoke_binary with loader detection and DISPLAY stripped"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_executors.py#test_smoke_binary_fails_on_exit_127"
        status: pass
      - kind: unit
        ref: "tests/test_run.py#test_run_output_with_stderr_returns_both_streams"
        status: pass
    human_judgment: false
  - id: D2
    description: "Archive install smokes staged member before swap; failures fall through or leave no link"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_smoke_failure_falls_through_to_the_next_method"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_smoke_failure_keeps_an_existing_good_install"
        status: pass
    human_judgment: false
  - id: D3
    description: "Raw install smokes staged sibling; updates skip smoke"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_download.py#test_raw_asset_is_smoked_before_it_replaces_the_link"
        status: pass
      - kind: unit
        ref: "tests/test_download.py#test_raw_update_does_not_smoke"
        status: pass
    human_judgment: false
duration: 120min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 09 Summary

**Verified downloads are smoke-tested on a staged path before any bin/opt link is written, with loader errors detected from stderr even on exit 0.**

## Performance

- **Duration:** ~120 min
- **Tasks:** 2
- **Files modified:** 7 production/test files (+ this summary)

## Accomplishments

- Added `run_output_with_stderr`, `smoke_binary`, `method_smoke_argv`, and `staged_member`; archive installs use the update-style staged swap with pre-swap smoke.
- Engine and download tests cover fall-through on exit 127, checksum-before-smoke, symlink containment, extraction cleanup, and fresh-install link rollback.
- Raw installs smoke the `.new` sibling before `os.replace`; updates still skip smoke; `fixture_runner` defaults unnamed fetches to an executable shell script.

## Task Commits

1. **Task 1: broken archive binary never linked; ladder continues** — `45c0676` (feat)
2. **Task 2: raw asset smoked before link replace** — `33a3fe5` (feat)

**Plan metadata:** (this file) — `docs(18-09): plan summary` (pending)

## TDD RED evidence (trimmed)

Task 1 (before implementation):

```
FAILED tests/test_executors.py::test_smoke_binary_fails_on_exit_127
AttributeError: module 'installer.executors' has no attribute 'smoke_binary'
```

Task 2 (before wiring install raw smoke):

```
FAILED tests/test_download.py::test_raw_asset_is_smoked_before_it_replaces_the_link
# install succeeded with exit-127 script at link (no ExecutorError)
```

## Verify results

- `uv run pytest tests/test_executors.py tests/test_download.py tests/test_engine.py -q --no-cov -k "smoke or falls_through or leaves_no_link or never_runs or writes_through or staged_tree or member_symlink"` → 33 passed
- `uv run pytest tests/test_run.py -q --no-cov` → 49 passed
- `uv run pytest tests/test_download.py -q --no-cov -k "raw_asset_is_smoked or raw_update_does_not_smoke"` → 2 passed
- `make validate && make test` → pass (3721 passed, coverage 95.99%)

## Deviations from Plan

- **fixture_runner curl default (Task 2):** When `files` is non-empty but omits a curl destination (checksum error tests), the runner still skips writing that file; only an empty `files` map triggers the default script payload. Prevents breaking verified checksum-missing tests.

Otherwise none.

## Issues Encountered

- `tests/test_download.py` was corrupted once by an editor truncation artifact during multi-step edits; restored from git and re-applied changes via an external patch script (`/tmp/patch_test_download_18_09.py`, deleted after use).

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
