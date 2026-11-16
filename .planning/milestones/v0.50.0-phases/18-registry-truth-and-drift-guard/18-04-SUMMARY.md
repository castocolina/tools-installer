---
phase: 18-registry-truth-and-drift-guard
plan: "04"
subsystem: testing
tags: [registry, cli_name, macos, apps, pytest]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: METHOD_PARAMS includes cli_name on app methods (plan 18-01)
provides:
  - apps.cli_spec honors and validates cli_name as the sole reader
  - Install/uninstall tests for draw.io-shaped app methods
  - Shipped-registry invariant test_shipped_app_cli_links_match_the_tool_cmd
affects: [18-registry-truth-and-drift-guard, drawio-desktop]

actuals:
  tokens: ~3500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "cli_name validated only in apps.cli_spec; install/update/uninstall share link naming"

key-files:
  created: []
  modified:
    - installer/apps.py
    - tests/test_apps.py
    - tests/test_uninstall.py

key-decisions:
  - "Merged invalid cli_name checks into one ExecutorError raise so grep -c 'invalid cli_name' is 1"

patterns-established:
  - "App CLI symlink name comes from cli_spec[1], optionally overridden by registry cli_name"

requirements-completed: [REG-01]

coverage:
  - id: D1
    description: "apps.cli_spec honors cli_name and rejects malformed values before side effects"
    requirement: REG-01
    verification:
      - kind: unit
        ref: "tests/test_apps.py#test_install_app_links_the_cli_under_cli_name"
        status: pass
      - kind: unit
        ref: "tests/test_apps.py#test_cli_spec_rejects_a_bad_cli_name"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_plan_app_uses_cli_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every shipped app method with cli links under tool.cmd via cli_spec"
    requirement: REG-01
    verification:
      - kind: unit
        ref: "tests/test_apps.py#test_shipped_app_cli_links_match_the_tool_cmd"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 04 Summary

**macOS draw.io app installs now symlink `~/.local/bin/drawio` via a single `cli_spec` reader, with registry-wide tests pinning link names to each tool's `cmd`.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 3 (+ this summary)

## Accomplishments

- `installer/apps.py::cli_spec` reads optional `cli_name`, validates bare filenames, and uses it as the symlink name; default remains the `cli` basename.
- Install and uninstall planning tests cover draw.io-shaped methods and bad `cli_name` rejection before `install_app` runs the pipeline.
- `test_shipped_app_cli_links_match_the_tool_cmd` loads the real registry and asserts every app method with `cli` resolves `cli_spec(method)[1] == tool.cmd` (passed on first run after Task 1).

## Task Commits

1. **Task 1: draw.io CLI link named by cli_name, install to uninstall (D-04)** — `9b4b4d0` (feat)
2. **Task 2: pin the shipped-registry invariant for app CLI links (D-04)** — `577d99e` (test)

## TDD RED evidence (Task 1, trimmed)

Before `cli_spec` honored `cli_name`, new tests failed as expected:

```
FAILED test_install_app_links_the_cli_under_cli_name - link at .../bin/draw.io not .../bin/drawio
FAILED test_plan_app_uses_cli_name - planned .../bin/draw.io instead of .../bin/drawio
FAILED test_cli_spec_rejects_a_bad_cli_name[""] - DID NOT RAISE ExecutorError
FAILED test_cli_spec_rejects_a_bad_cli_name[1] - DID NOT RAISE ExecutorError
(... same for bin/drawio, ., ..)
FAILED test_install_app_rejects_bad_cli_name_before_side_effects - DID NOT RAISE
```

Task 2 invariant test **passed on first run** (registry already declares `cli_name = "drawio"` where needed).

## Verify commands

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_apps.py tests/test_uninstall.py -q --no-cov -k cli_name` | 9 passed |
| `uv run pytest tests/test_apps.py tests/test_uninstall.py tests/test_engine.py -q --no-cov` | passed |
| `uv run pytest tests/test_apps.py -q --no-cov -k match_the_tool_cmd` | 1 passed |
| `make validate && make test` (final tree) | exit 0; 3628 passed |

## Acceptance checks

- `rg -rln 'cli_name' installer/*.py` → `installer/apps.py`, `installer/model.py` (allowed)
- `rg -c "invalid cli_name" installer/apps.py` → 1

## Deviations from Plan

- **test_uninstall.py insert:** Used a short Python insert script instead of the edit tool for `test_plan_app_uses_cli_name` because a large-file edit truncated the file once; content matches the plan's behavior spec.
- **Pyright:** Combined `cli_name` validation branches and `name = str(cli_name)` after guards to satisfy strict typing.

Otherwise none — plan executed as written.

## Issues Encountered

- First attempt to patch `tests/test_uninstall.py` via bulk edit truncated the file; restored from git and re-applied with a targeted script.

## Next Phase Readiness

- REG-01 cli_name half is satisfied for install/uninstall naming; remaining REG-01 work lives in plan 18-01 (closed METHOD_PARAMS) and data-fix plans if the invariant test ever fails on new registry rows.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
