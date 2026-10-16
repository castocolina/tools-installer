---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "25"
subsystem: testing
tags: [pytest, home-sandbox, shlex, container-e2e, gap-closure]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: the receipts directory sandbox, the state-double services, and the container-e2e receipt checks
provides:
  - an autouse per-test scratch HOME, so declared locations expand away from the developer's home
  - a real-registry proof that the scratch HOME is the tree a refresh pass reads
  - shell-quoted interpreter and workspace paths in the e2e receipt tests
  - an explicit pass1 failure when the receipt check fails
affects: [test-harness, container-e2e, ownership]

actuals:
  tokens: 2194
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "every test starts with HOME pointing at a per-test scratch dir under pytest's base temp; a test that sets HOME itself still overrides it"
    - "paths interpolated into generated shell text go through shlex.quote"

key-files:
  created: []
  modified:
    - tests/conftest.py
    - tests/test_locations.py
    - tests/test_container_e2e_receipts.py
    - scripts/container-e2e-verify.sh

key-decisions:
  - "The import-time real home is Path.home() with no suppression comment; the fixture has not run yet at import, so the capture is the developer's home"
  - "shlex.quote wraps the interpreter in single quotes, which stays one word inside the stub's exec line"

patterns-established:
  - "Pattern: a test that writes under Path.home() first asserts the home is not the developer's, so a missing sandbox fails before any write"

requirements-completed: [STATE-04, STATE-03]

coverage:
  - id: D1
    description: "Every test runs with HOME, Path.home() and expanduser pointing at a per-test scratch dir under pytest's base temp, never the developer's home"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_suite_home_is_a_per_test_scratch_dir"
        status: pass
    human_judgment: false
  - id: D2
    description: "A real-registry refresh sees an SDKMAN java planted under the scratch HOME as owner sdkman, and sees no SDKMAN owner when that tree is empty"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_registry_pass_reads_declared_locations_from_the_scratch_home"
        status: pass
    human_judgment: false
  - id: D3
    description: "The e2e receipt uv stub and the workspace assignment survive a path that contains a space"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_uv_stub_survives_a_spaced_interpreter_path"
        status: pass
    human_judgment: false
  - id: D4
    description: "cmd_pass1 fails explicitly when the receipt check fails, not only through errexit"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_receipt_checks_are_wired_into_the_passes"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 25: Scratch HOME and quoted e2e receipt paths Summary

**Every test runs under a per-test scratch HOME, proven by a real-registry SDKMAN pass, and the e2e receipt checks survive a path with spaces and fail pass1 explicitly**

## Performance

- **Duration:** 12 min
- **Started:** 2026-10-16T20:40:36Z
- **Completed:** 2026-10-16T20:50:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- An autouse `sandboxed_home` fixture points `HOME` at a per-test scratch dir, so `Path.home()` and `expanduser` never read the developer's home through a declared location.
- A real-registry refresh of `java` reports owner `sdkman` only after a binary is planted under the scratch `~/.sdkman`, which proves the pass expanded `~` into the scratch dir.
- The e2e receipt stub and the workspace assignment are shell-quoted, and `cmd_pass1` returns 1 itself when the receipt check fails.

## Task Commits

Each task was committed atomically (tests and code together; RED captured, never committed):

1. **Task 1: every test runs under a scratch HOME, proven through a real-registry pass** - `b0522d0` (test)
2. **Task 2: quoted paths in the e2e receipt tests, and an explicit pass1 receipt failure** - `e64640c` (test)

## Files Created/Modified
- `tests/conftest.py` - autouse `sandboxed_home`, placed before `sandboxed_receipts`
- `tests/test_locations.py` - scratch-HOME proofs and the import-time `_REAL_HOME` comparison
- `tests/test_container_e2e_receipts.py` - `shlex.quote` in `_uv_stub`, the `_assign` helper, two spaced-path tests
- `scripts/container-e2e-verify.sh` - `assert_receipt_present "$categories" || return 1` in `cmd_pass1`

## TDD RED evidence

Task 1, before `sandboxed_home` existed (`uv run pytest tests/test_locations.py -q --no-cov -k "scratch_dir or scratch_home or default_bin_dir"`):

```
>       assert home.is_relative_to(tmp_path_factory.getbasetemp())
E       AssertionError: assert False
E        +  where False = is_relative_to(PosixPath('/tmp/pytest-of-bazzite/pytest-2005'))
E        +    where is_relative_to = PosixPath('/home/bazzite').is_relative_to

>       assert not Path.home().is_relative_to(_REAL_HOME)
E       AssertionError: assert not True
E        +  where True = is_relative_to(PosixPath('/home/bazzite'))
E        +    where is_relative_to = PosixPath('/home/bazzite').is_relative_to

FAILED test_suite_home_is_a_per_test_scratch_dir
FAILED test_registry_pass_reads_declared_locations_from_the_scratch_home
2 failed, 1 passed, 34 deselected
```

Both failed on the first HOME assertion, before writing anything. The updated bin-dir test already passed.

Task 2, before quoting and the script edit (`uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -k "spaced or wired_into_the_passes"`):

```
>       assert 'assert_receipt_present "$categories" || return 1' in pass1
E       AssertionError: assert 'assert_receipt_present "$categories" || return 1' in 'cmd_pass1() {...'

>       assert result.returncode == 0, result.stdout + result.stderr
E       AssertionError: /usr/bin/bash: line 6: /tmp/.../py: No such file or directory
E       assert 127 == 0

FAILED test_receipt_checks_are_wired_into_the_passes
FAILED test_uv_stub_survives_a_spaced_interpreter_path
2 failed, 1 passed, 6 deselected
```

The assignment test passed before the production change, because `_assign` already quotes; the uv stub is what was broken.

## Verify results

- Task 1: `uv run pytest -n auto --no-cov` → 4530 passed, 4 skipped (exit 0). `make validate` exit 0. Suppressions 487 → 487.
- Task 2: `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov` → 9 passed; `-k spaced` → 2 passed. `bash -n scripts/container-e2e-verify.sh` parses. Suppressions unchanged.
- Final tree: `make validate` exit 0. `make test` → 4532 passed, 4 skipped, coverage 95.98% (floor 90%).
- Plan verification: `uv run pytest tests/test_locations.py tests/test_container_e2e_receipts.py tests/test_layout_80x20.py -n auto -q --no-cov` exit 0 (60 passed).
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` exit 0: no dependency change.
- The real `~/.local/state/tools-installer/receipts` is still empty.

## Decisions Made

None - followed plan as specified. The import-time home is captured with `Path.home()` rather than `os.path.expanduser` so the new line needs no suppression comment; at import time the fixture has not run, so both read the developer's home.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0
**Impact on plan:** None.

## Issues Encountered

None. The full suite was green on the first run under the scratch HOME; the only test the planning probe predicted (`test_suite_sandbox_redirects_the_default_bin_dir`) was updated as the plan said.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G28, G19 and the IN-05 part of G22 are closed. Later plans in this wave can rely on the scratch HOME.
- Self-review of `b0522d0~1..e64640c` (no subagent tool used for the review): no Critical or Important findings. `shlex.quote` emits single quotes, which stay one word inside the stub's `exec` line for spaces, quotes, `$` and backticks.

## Rulings I made

- Final: Ruling: no subagent reviewer was dispatched — the harness has a subagent tool, but this plan's executor contract says pi runs the plan alone and the orchestrator owns review, so the whole-branch review was done in this session — cost if wrong: a defect in the four-file diff ships until the orchestrator's review.

## Deferred minors

None.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
