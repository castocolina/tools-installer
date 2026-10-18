---
phase: 20-install-plan-with-dispositions
plan: "19"
subsystem: testing
tags: [container-e2e, install-plan, bash, outcome-rows]

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: "RowOutcome summary vocabulary from 20-07 and render_run_summary output contract from 20-09"
provides:
  - "Container e2e verification parses install-plan Summary counts and cross-checks dependency blockers against manual handoffs"
affects: [container-e2e, make-e2e]

# Actuals
actuals:
  tokens: 3423
  tasks: 1
  commits: 1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Parse the Summary — outcome vocabulary, defaulting absent counters to zero"
    - "Cross-check dependency-failed outcome rows against manual handoff rows"

key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-19-SUMMARY.md
  modified:
    - scripts/container-e2e-verify.sh

key-decisions:
  - "Use the first Summary — line from render_run_summary as the source for disposition counts."
  - "Use concrete dependency-failed and manual outcome rows for the blocker explanation check; an earlier failure remains unexplained."
  - "Keep the failed and checksum-mismatch gates unchanged while reporting updated, skipped, blocked, and manual counts."

patterns-established:
  - "Keep the dependency-failure lines file separately named from the skipped counter."

requirements-completed: [PLAN-06]

coverage:
  - id: D1
    description: "Container e2e verification parses Summary — disposition counts and validates dependency blockers against manual handoff rows."
    requirement: PLAN-06
    verification:
      - kind: integration
        ref: "Sourced parser self-check from 20-19-PLAN verify #1; output: 2 1 3 1 1 0"
        status: pass
      - kind: integration
        ref: "Sourced dependency/manual cross-check from 20-19-PLAN verify #2; output: CROSS_CHECK_OK"
        status: pass
      - kind: integration
        ref: "uv run pytest tests/test_shell_scripts_path.py tests/test_container_e2e_receipts.py -q --no-cov; 24 passed"
        status: pass
      - kind: other
        ref: "make validate && make test; 4,874 passed, 4 skipped, 96.05% coverage"
        status: pass
    human_judgment: true
    rationale: "The complete make e2e run is the plan's disposable-container/CI backstop and was not run locally; confirm PASS1 counts against actual Fedora-container output."

duration: 23min
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 19: Install-plan E2E Parser Summary

**Container e2e verification now parses install-plan disposition counts and cross-checks dependency failures against manual handoff rows.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-10-18T04:55:17Z
- **Completed:** 2026-10-18T05:19:10Z
- **Tasks:** 1
- **Files modified:** 1 task-scoped source file

## Accomplishments

- Replaced the retired summary parser with a parser for the `Summary — …` line, covering all emitted categories and defaulting omitted categories to zero.
- Updated the pass counters and log output to report installed, updated, skipped, failed, dependency-failed, checksum-mismatch, blocked, and manual outcomes while preserving the failed and mismatch gates.
- Reworked the dependency explanation check to read blockers and manual tool names from the rendered outcome rows; `an earlier failure` remains unexplained.

## Task Commits

1. **Task 1: the parser reads the `Summary — …` line and the cross-check reads the outcome rows** — `4ab0ea8f8bbb6b35ab902378303c9a80ca5a62d4` (`fix(20-19)`).

**Plan metadata:** committed separately as `docs(20-19): plan summary`.

## Files Created/Modified

- `scripts/container-e2e-verify.sh` — parses summary counts and cross-checks dependency-failure and manual outcome rows.
- `.planning/phases/20-install-plan-with-dispositions/20-19-SUMMARY.md` — this execution record.

## Decisions Made

- Treat `render_run_summary`'s first `Summary —` line as the stable source for counts and initialize absent categories to zero.
- Keep dependency-failure rows in `ACC_DEP_LINES_FILE`, distinct from the `ACC_SKIPPED` counter, and match their blocker names against manual outcome rows.
- Preserve the existing `failed == 0` and checksum-mismatch gates.

## Verification

- **TDD RED:** the new Summary line did not match the old parser; the parser self-check exited nonzero as expected (`RED: new Summary line did not match the existing parser (as expected)`).
- `bash -n scripts/container-e2e-verify.sh` — passed.
- Sourced Summary parser self-check — printed `2 1 3 1 1 0`; the previous `Installed: 2  Already: 0` format was rejected.
- Sourced dependency/manual cross-check — printed `CROSS_CHECK_OK`; a blocker missing from the manual rows and `an earlier failure` were rejected.
- `uv run pytest tests/test_shell_scripts_path.py tests/test_container_e2e_receipts.py -q --no-cov` — 24 passed.
- Acceptance checks — passed: new Summary pattern found; old pattern, variable names, renderer name, and manual bucket absent; `ACC_DEP_LINES_FILE` count 13; new manual/dependency row phrases present.
- `make validate && make test` — passed on the committed code: ruff, format, pyright, bandit, vulture, and shellcheck gates passed; 4,874 passed, 4 skipped, 96.05% coverage (90% required).
- `make e2e` — not run, as required by the plan; it is the disposable-container/CI backstop.

## Deviations from Plan

None — plan scope and behavior were followed. The parser implementation was compacted to preserve existing line-number anchors used by the shell PATH classification test; no additional tracked source files were changed.

## Issues Encountered

- The PATH classification test initially failed after the parser expansion shifted two classified shell lines. The implementation was compacted to restore their original line numbers; the targeted tests and full suite then passed.
- A read-only review subagent could not be dispatched because of provider budget and API-key errors. The full diff and renderer contracts were manually checked instead.
- The pre-existing orchestrator-owned `.planning/config.json` change was left untouched and unstaged.

## User Setup Required

None — no external service configuration is required.

## Next Phase Readiness

The PLAN-06 parser and cross-check are ready. The actual Fedora-container `make e2e` backstop remains for CI or a disposable-container run; the rest of Phase 20 can proceed independently.

## Self-Check: PASSED

- Task artifact exists and is limited to `scripts/container-e2e-verify.sh`.
- Both sourced self-checks, acceptance criteria, targeted tests, `make validate`, and the full coverage suite passed.
- Requirement `PLAN-06` is recorded as completed; the orchestrator-owned config and other protected planning state were not modified.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
