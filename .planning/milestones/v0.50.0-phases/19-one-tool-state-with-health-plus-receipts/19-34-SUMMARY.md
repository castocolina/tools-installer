---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "34"
subsystem: testing
tags: [presence, pnpm-shim, look-through, test-isolation, xdg, volta, pnpm]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "is_installed skips this installer's own shim; conftest sandboxes HOME"
provides:
  - "Default is_installed lookup looks through this installer's own shim to the real binary"
  - "Autouse fixture clears inherited PNPM_HOME, VOLTA_HOME, XDG_CONFIG_HOME and XDG_DATA_HOME"
affects: [19-35, headless-setup, ownership-tests]

actuals:
  tokens: 1200
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Default PATH presence looks through installer.guards.look_through_shim; a passed which is left alone"
    - "Inherited absolute location overrides are cleared per test; a test that needs one uses monkeypatch.setenv"

key-files:
  created: []
  modified:
    - installer/status.py
    - tests/test_status.py
    - tests/conftest.py
    - tests/test_locations.py

key-decisions:
  - "Followed the plan's look_through_shim call rather than the review's real_binary sketch: look_through_shim only rewrites a shim that sits directly in the managed bin dir"
  - "Kept the existing no_shell_location_env fixture name and added the four delenv calls there"

patterns-established:
  - "A real binary behind this installer's redirect shim is presence on the default lookup; a bare shim is not"
  - "Every test starts without PNPM_HOME, VOLTA_HOME, XDG_CONFIG_HOME or XDG_DATA_HOME"

requirements-completed: [STATE-04]

coverage:
  - id: D1
    description: "On the default lookup, a real pnpm behind the installer's redirect shim is presence, and a shim with nothing behind it is not"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_real_pnpm_behind_the_redirect_shim_is_presence"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every test starts with PNPM_HOME, VOLTA_HOME, XDG_CONFIG_HOME and XDG_DATA_HOME cleared, so owner prefixes fall back under the scratch HOME"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_inherited_location_overrides_are_cleared"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 34: Shim look-through and inherited location overrides Summary

**The default presence lookup treats a real pnpm behind the redirect shim as installed, and no test inherits PNPM_HOME, VOLTA_HOME or the two XDG home overrides.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-10-16T23:30:00Z
- **Completed:** 2026-10-16T23:55:53Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `is_installed` with `which=None` looks through this installer's own shim in the managed bin dir, so a brew, Volta or corepack pnpm further down PATH is presence and the headless route does not install a second pnpm.
- A shim with nothing behind it still reads as not installed, and a caller that passes `which` keeps today's behavior.
- The autouse `no_shell_location_env` fixture clears `PNPM_HOME`, `VOLTA_HOME`, `XDG_CONFIG_HOME` and `XDG_DATA_HOME`, so owner prefixes and terminal config paths resolve under the scratch HOME.

## Task Commits

Each task was committed atomically (test and code together; RED output recorded below, never committed):

1. **Task 1: the default presence lookup looks through the installer's own shim (M4, WR2-01)** - `5791779` (fix)
2. **Task 2: inherited manager and XDG overrides never reach a test (M5, RR-05)** - `b1f0ac3` (test)

**Plan metadata:** this commit (docs: plan summary)

## TDD RED evidence

### Task 1

`uv run pytest tests/test_status.py -q --no-cov -k "behind_the_redirect_shim or shim_on_path"` exited 1. The four existing shim-on-path cases passed; the new test failed on its first assertion:

```
>       assert is_installed(tool, default_bin_dir=shims, darwin=False) is True
E       AssertionError: assert False is True
FAILED tests/test_status.py::test_real_pnpm_behind_the_redirect_shim_is_presence
```

### Task 2

With the four variables exported to fake paths, `uv run pytest tests/test_locations.py -q --no-cov -k inherited_location` exited 1 on the first assertion:

```
>           assert name not in os.environ
E           AssertionError: assert 'PNPM_HOME' not in environ({...})
FAILED tests/test_locations.py::test_inherited_location_overrides_are_cleared
```

## Verify-command results

- Task 1: `uv run pytest tests/test_status.py tests/test_guards.py tests/test_deps.py tests/test_engine.py -q --no-cov` exit 0. Truncation guard and suppression guard exit 0 (483 suppressions, unchanged). `grep -c` of `look_through_shim(` and `which is None and resolved is not None` in `installer/status.py` is 1 each. `make validate` exit 0; `make test` 4594 passed, 4 skipped, coverage 96.01%.
- Task 2: the exported-env verify command over locations, ownership, terminal_shell and catalog_tui exit 0. Truncation guard (`tests/test_locations.py` 452 to 469 lines, tests 34 to 35; `tests/conftest.py` 209 to 222) and suppression guard exit 0. `grep -cE` of the four `delenv` calls is 4. `make validate` exit 0; `make test` 4595 passed, 4 skipped, coverage 96.01%.
- Plan verification: `uv run pytest tests/test_status.py tests/test_locations.py tests/test_ownership.py tests/test_engine.py -n auto -q --no-cov` exit 0. `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` exit 0.

## Files Created/Modified

- `installer/status.py` — default lookup looks through the installer's own shim before the PATH presence check
- `tests/test_status.py` — `test_real_pnpm_behind_the_redirect_shim_is_presence`
- `tests/conftest.py` — clears the four inherited location overrides in `no_shell_location_env`
- `tests/test_locations.py` — `test_inherited_location_overrides_are_cleared`

## Decisions Made

- Used `installer.guards.look_through_shim` as the plan specifies, not the review's `real_binary` sketch. `look_through_shim` only rewrites a hit that is this installer's shim directly in the managed bin dir, which matches D-13 and the refresh service.
- Moved the existing implicit bin-dir computation above the PATH branch unchanged, including its comment, so the look-through and the later implicit loop share one value.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0
**Impact on plan:** No scope change. Both tasks landed in the files the plan lists.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- STATE-04's M4 and M5 gap items are closed: the headless route sees a real pnpm behind the redirect shim, and no test can follow an inherited manager or XDG override into the real HOME.
- The existing custom-`which` test `test_installer_shim_on_path_is_never_presence` stayed green unchanged.
- No dependency change. No host mutation.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
