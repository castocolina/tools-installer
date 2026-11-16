---
phase: 18-registry-truth-and-drift-guard
plan: "03"
subsystem: infra
tags: [macos, status, audit, registry, REG-07]

requires: []
provides:
  - MACOS_STUBS closed table with java_home and xcode-select probes
  - macos_stub_reason and is_installed darwin/probe seams
  - ToolStatus.reason and render_audit missing (reason) display
affects: [engine install short-circuit, pre-flight audit, execute screen audit]

actuals:
  tokens: 8500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Closed absolute-path probe table for macOS shims via run_output + PROBE_VERSION_TIMEOUT"
    - "Audit uses injected is_installed for state; stub_reason only on missing rows"

key-files:
  created: []
  modified:
    - installer/status.py
    - installer/audit.py
    - installer/render.py
    - tests/test_status.py
    - tests/test_audit.py

key-decisions:
  - "Kept separate is_installed and stub_reason reads in audit so injected installed checks (repair ids) are not bypassed"
  - "Stub which-hit does not short-circuit; bin_dir/detect_path/app still count as installed"

patterns-established:
  - "MACOS_STUBS + StubProbe injection in tests; never run real java_home/xcode-select in CI"

requirements-completed: [REG-07]

coverage:
  - id: D1
    description: "macOS java/git shims require probe success before counting as installed"
    requirement: REG-07
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_java_stub_alone_is_not_installed_with_a_reason"
        status: pass
      - kind: unit
        ref: "tests/test_status.py#test_git_stub_without_clt_is_not_installed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Pre-flight audit shows missing (reason) for stub-only tools"
    requirement: REG-07
    verification:
      - kind: unit
        ref: "tests/test_audit.py#test_audit_row_shows_the_stub_reason"
        status: pass
    human_judgment: false
  - id: D3
    description: "Off-macOS and non-stub paths never invoke stub probes"
    requirement: REG-07
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_stub_table_is_ignored_off_macos"
        status: pass
      - kind: unit
        ref: "tests/test_status.py#test_non_stub_path_on_macos_runs_no_probe"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 03 Summary

**macOS `/usr/bin/java` and `/usr/bin/git` shims no longer count as installed without JDK/CLT; the pre-flight audit shows `missing (<reason>)` for stub-only rows.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 5 (+ summary)

## Accomplishments

- Added `MACOS_STUBS`, `macos_stub_reason`, and `is_installed(..., darwin=, probe=)` so stub PATH hits fall through to real install markers when probes fail.
- Extended `ToolStatus.reason`, `audit(..., stub_reason=)`, and `render_audit` to surface escaped stub reasons only for missing rows.
- Eleven new unit tests cover java/git stubs, fall-through bin_dir, audit reason semantics, and off-macOS guards.

## Task Commits

1. **Task 1: java stub end to end** — `f547005` (feat)
2. **Task 2: git/CLT stub and off-macOS guard** — `a2fa5ce` (test)

## TDD RED Evidence (Task 1)

```
ImportError while importing test module 'tests/test_status.py'
from installer.status import (
E   ImportError: cannot import name 'macos_stub_reason' from 'installer.status'
```

## Verify Results

- Task 1: `uv run pytest tests/test_status.py tests/test_audit.py -q --no-cov -k "stub or reason or missing_rows"` — 6 passed
- Task 1: `uv run pytest tests/test_status.py tests/test_audit.py tests/test_render.py tests/test_engine.py tests/test_deps.py -q --no-cov` — passed
- Task 2: `uv run pytest tests/test_status.py -q --no-cov -k stub` — 8 passed
- Task 2: `uv run pytest tests/test_status.py tests/test_audit.py tests/test_ownership.py tests/test_catalog_tui.py -q --no-cov` — passed
- Final: `make validate && make test` — passed (3618 passed, 4 skipped, coverage 95.95%)

## Existing test trace (Task 2, `/usr/bin/git` / `/usr/bin/java` fakes)

| Test / area | Reaches `is_installed` / stub table? | Action |
|-------------|--------------------------------------|--------|
| `tests/test_catalog_tui.py::test_owner_column_and_detail_paint_the_os_package_case_end_to_end` | No — solo coverage of `installer.status` leaves lines 91–119 missing | Not pinned |
| `tests/test_ownership.py` rows with `which="/usr/bin/git"` or `"/usr/bin/java"` (e.g. `test_os_package_owner_resolves_git_shaped_tool_on_fedora`, `test_undeclared_brew_shadowed_by_os_package`) | No — `resolve_ownership` uses injected `which`, not `status.is_installed` for these dnf/brew-shaped tools | Not pinned |
| `tests/test_ownership.py::test_script_only_installed_tool_is_installer_by_elimination` | Calls `ownership.is_installed` but monkeypatched to `_pretend_installed` | Not pinned |
| `tests/test_version_status.py`, `tests/test_uninstall.py` fakes `f"/usr/bin/{cmd}"` | No — version/uninstall services, not `is_installed` | Not edited (wave 18-02/18-04) |

## Deviations from Plan

None — plan executed as written. No pins required in `tests/test_ownership.py` or `tests/test_catalog_tui.py` after coverage re-trace.

## Issues Encountered

None

## User Setup Required

None

## Next Phase Readiness

REG-07 acceptance fixtures are in place for macOS CI; downstream callers use default `is_installed`/`macos_stub_reason` without wiring changes.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
