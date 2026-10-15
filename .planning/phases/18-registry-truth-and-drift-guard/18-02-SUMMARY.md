---
phase: 18-registry-truth-and-drift-guard
plan: "02"
subsystem: registry
tags: [versions, parser, REG-08, semver]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: phase 18 registry-truth context
provides:
  - Tightened glued-name boundary (no bare-flag versions)
  - Shared _normalize_version_token for parse/status/extract
  - Parametrized audit fixture table for version parsing
affects: [18-registry-truth-and-drift-guard, version_status]

actuals:
  tokens: 4500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "One token normalizer ahead of _match_observed_version and in extract_observed_version"

key-files:
  created: []
  modified:
    - installer/versions.py
    - tests/test_versions.py

key-decisions:
  - "Glued-name prefix must be ASCII letter plus at least two characters before split (audit B WR-02)"
  - "Normalizer order: trailing punctuation, version= prefix, then independent quote strip (L-18-13)"

patterns-established:
  - "extract_observed_version returns normalized tokens, not raw stdout fragments"

requirements-completed: [REG-08]

coverage:
  - id: D1
    description: Bare flags and one-letter glued names never parse as versions
    requirement: REG-08
    verification:
      - kind: unit
        ref: tests/test_versions.py#test_parse_version_never_fabricates_from_a_bare_flag
        status: pass
    human_judgment: false
  - id: D2
    description: Quoted, version=, and lazygit/procs outputs parse to real versions
    requirement: REG-08
    verification:
      - kind: unit
        ref: tests/test_versions.py#test_observed_version_fixture_table
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 02 Summary

**Version parsing no longer fabricates from flags; lazygit and procs installed versions read correctly via one shared token normalizer.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Rejected `-1`, `--1`, `--2`, `-v1.2.3`, and `a-1` across `parse_version`, `parse_status_version`, and `extract_observed_version` while keeping `jq-1.8.1` and `tool-2.3.4-rc.1`.
- Added `_normalize_version_token` (punctuation, `version=`, independent quote strip) shared by all three public parsers.
- Parametrized audit fixture table plus migrated four pinned tests for the new extract/normalizer contract.

## Task Commits

1. **Task 1: bare flag never becomes a version** — `d4fc105` (fix)
2. **Task 2: token normalizer for quoted and version= output** — `3690211` (feat)

## TDD RED Evidence

**Task 1** (before `_strip_name_prefix` prefix check): simulated old path `parse_version('-1')` → `(1, 0, 0)`; new tests would fail on `-1` / `a-1` expecting `None`.

**Task 2** (tests added before normalizer; trimmed):

```
FAILED test_observed_version_fixture_table[balanced-double-quotes]
FAILED test_observed_version_fixture_table[procs-unbalanced-quote]
FAILED test_observed_version_fixture_table[lazygit-version-equals]
FAILED test_extract_observed_version_finds_the_first_parseable_token
  AssertionError: assert None == '0.64.1'
```

## Verify Results

| Command | Result |
|---------|--------|
| Task 1: `pytest -k "fabricat or glued_name"` | 6 passed |
| Task 1: versions + version_status + manager_versions + pnpm_globals | all passed |
| Task 2: `pytest -k "observed or quoted or audit_finding or residual_shapes"` | 16 passed |
| Task 2: + manager_versions + pnpm_globals + executors | all passed |
| Final: `make validate && make test` | exit 0 (3607 passed) |

## Deviations from Plan

None — plan executed as written. Migrated assertions (`version=0.64.1`, procs residual, audit comment block) were required in-plan, not unplanned fixes.

## Issues Encountered

None.

## Final Review

Self-review (no subagent tool): diff matches plan truths; no test_version_status.py changes were required.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
