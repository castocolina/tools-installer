---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "39"
subsystem: testing
tags: [pytest, subprocess, PATH, sandbox, e2e]

# Dependency graph
requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: Existing pytest sandbox and container e2e receipt harness
provides:
  - Test-wide PATH stripping for real HOME and /run/user toolchain directories
  - Guarded subprocess.Popen preventing host node-family and brew execution
  - BREW_BIN-based e2e harness calls with a tmp_path brew stub
  - Isolated uv stub for countdown tests after uv was removed from PATH
affects: [pytest-sandbox, container-e2e, test-infrastructure]

# Actuals (#2632)
actuals:
  tokens: 24681
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Resolve PATH entries before comparing them to real HOME and /run/user
    - Guard subprocess.Popen with a subscriptable subclass and pytest base-temp allowlist
    - Replace host executables with per-test fakes under tmp_path

key-files:
  created:
    - tests/test_sandbox.py
  modified:
    - tests/conftest.py
    - tests/test_tweaks.py
    - scripts/container-e2e-verify.sh
    - tests/test_container_e2e_receipts.py
    - tests/test_shell_scripts_path.py

key-decisions:
  - "Keep Linuxbrew on PATH for required zsh/python3 binaries; guard brew itself at process launch."
  - "Permit host-toolchain executables only when their resolved location is under pytest's base temp directory."

patterns-established:
  - "Tests requiring toolchain commands plant executable stubs under tmp_path."
  - "Extracted e2e functions receive host executable paths through overridable shell constants."

requirements-completed: [STATE-04, STATE-03]
coverage:
  - id: D1
    description: "Tests remove host toolchain directories from PATH and reject host node-family or brew subprocess launches."
    requirement: STATE-04
    verification:
      - kind: unit
        ref: tests/test_sandbox.py
        status: pass
      - kind: unit
        ref: make test (4622 passed, 4 skipped)
        status: pass
    human_judgment: false
  - id: D2
    description: "Extracted receipt e2e functions use BREW_BIN and tests point it at a local stub."
    requirement: STATE-03
    verification:
      - kind: unit
        ref: tests/test_container_e2e_receipts.py
        status: pass
      - kind: other
        ref: bash -n scripts/container-e2e-verify.sh
        status: pass
    human_judgment: false

duration: 70min
completed: 2026-10-17
status: complete
---

# Phase 19, Plan 39 Summary

**The test sandbox now removes host toolchain PATH entries, blocks host node-family and brew launches, and runs extracted e2e brew calls against a stub.**

## Performance

- **Duration:** approximately 70 minutes
- **Started:** 2026-10-17 (approximate; session start timestamp was unavailable after compaction)
- **Completed:** 2026-10-17T01:20:23-03:00
- **Tasks:** 2
- **Files modified:** 6 (including the new sandbox test)

## Accomplishments

- Added a resolved-path PATH strip for the developer's real HOME and `/run/user`, plus an autouse `Popen` guard that reports the blocked executable.
- Added regressions for PATH isolation, blocked host executables, allowed tmp-path fakes, and named-program-only guard behavior.
- Reworked countdown helper tests to plant a local `uv` stub after the PATH isolation correctly removed the host's `uv` executable.
- Routed the two locally extracted e2e functions' Homebrew shellenv calls through `BREW_BIN` and provided a temporary stub in receipt tests.
- Updated shell-script PATH classification line numbers because the harness changes moved the PATH-export lines.

## Task Commits

Each task was committed atomically:

1. **Task 1: no host toolchain dir on PATH, and no host node-family or brew process can start** - `bc7aab4` (test)
2. **Task 2: the extracted e2e functions name brew through BREW_BIN and the tests stub it** - `1664d9d` (test)

**Plan metadata:** committed with this summary.

## Files Created/Modified

- `tests/conftest.py` - PATH filtering, guarded Popen and shared toolchain policy.
- `tests/test_sandbox.py` - regression tests for PATH and process-launch isolation.
- `tests/test_tweaks.py` - countdown tests now provide their own uv executable stub.
- `scripts/container-e2e-verify.sh` - `BREW_BIN` constant used by tester harness functions.
- `tests/test_container_e2e_receipts.py` - brew-stub helper and assertions for extracted functions.
- `tests/test_shell_scripts_path.py` - updated expected line numbers for classified PATH exports.

## Decisions Made

- Kept Linuxbrew's directory on PATH because this host's shell tests require its `zsh` and `python3`; the guard blocks brew by executable name.
- Allowed toolchain binaries only when the resolved executable is under pytest's base temp directory, enabling safe fakes.

## Deviations from Plan

### Auto-fixed Issues

**1. Countdown tests depended on host `uv` remaining on PATH**
- **Found during:** Task 1 full-suite verification.
- **Issue:** PATH isolation removed the developer's `~/.local/bin/uv`, causing four countdown tests to fail with `uv: command not found`.
- **Fix:** Added a per-test `uv` stub that dispatches the managed helper to `sys.executable`.
- **Files modified:** `tests/test_tweaks.py`.
- **Verification:** `tests/test_tweaks.py` passed; the final suite passed.
- **Committed in:** `bc7aab4`.

**2. Shell-script PATH scanner classifications tracked shifted line numbers**
- **Found during:** focused verification after adding the BREW_BIN constant.
- **Issue:** Existing scanner expected the old line numbers for three PATH exports.
- **Fix:** Updated the classifications to the new locations; the PATH behavior is unchanged.
- **Files modified:** `tests/test_shell_scripts_path.py`.
- **Verification:** `tests/test_shell_scripts_path.py` passed in focused and full runs.
- **Committed in:** `1664d9d`.

**3. Task 2 RED test was not observed**
- **Found during:** Task 2 execution.
- **Issue:** The implementation was edited before the prescribed RED run; the new receipt tests passed immediately, so no failing `BREW_BIN is not assigned` output was captured.
- **Fix:** Verified the behavior with explicit extracted-function assertions and stubbed pre-uninstall tests. This is recorded rather than representing the run as a RED/GREEN cycle.
- **Files modified:** `scripts/container-e2e-verify.sh`, `tests/test_container_e2e_receipts.py`.
- **Verification:** Focused tests, full suite, and `bash -n` passed.
- **Committed in:** `1664d9d`.

**Total deviations:** 3 auto-fixed/recorded (2 environment/test adjustments, 1 TDD sequencing deviation).
**Impact on plan:** Required host-safety behavior is implemented and the complete quality gate passed. The missing Task 2 RED observation is a process deviation only.

## TDD RED Evidence

- **Task 1:** `uv run pytest tests/test_sandbox.py -q --no-cov` failed during collection because `tests.conftest` did not yet export `HOST_TOOLCHAIN` and `assert_not_host_toolchain` (`ImportError`). This was an import/collection RED, not an assertion-level PATH failure.
- **Task 2:** No RED output was captured; see the deviation above.

## Verification

- Focused tests: `uv run pytest tests/test_sandbox.py tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py tests/test_pnpm_globals.py tests/test_executors.py tests/test_run.py -n auto -q --no-cov` — passed.
- `bash -n scripts/container-e2e-verify.sh` — passed.
- `make validate` — passed (ruff, format, pyright, bandit, vulture, shellcheck).
- `make test` — passed: **4622 passed, 4 skipped**, 95.97% coverage.
- Each task commit was preceded by `make validate && make test` on its staged task tree.

## Issues Encountered

- The initial full suite identified countdown tests depending on host `uv`; a tmp-path stub removed that dependency.
- A focused test initially found stale PATH scanner line classifications; corrected alongside the harness change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The regression net is in place for subsequent test work. Tests that need toolchain executables must plant them under `tmp_path`; Linuxbrew remains available for non-brew test utilities.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
