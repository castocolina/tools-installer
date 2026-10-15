---
phase: 18-registry-truth-and-drift-guard
plan: "13"
subsystem: infra
tags: [registry, tomllib, verify-registry, pin-bump, pytest]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: check_registry, newer-stable drift, offline probe tests (plans 18-12, 18-17)
provides:
  - RegistryEdit / RegistryWriteError / apply_registry_edits with tomllib semantic guard
  - maintainer --write (verified dates for passed_tools only)
  - --candidate pin bump with pinned-only eligibility and as-written final report
affects: [18-14, 18-15]

actuals:
  tokens: ~22000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Scoped line rewrite + tomllib.loads equality guard before atomic_write_text"
    - "Bump eligibility on pinned-method-only check_registry copy; verified from final report"

key-files:
  created: []
  modified:
    - installer/verify_registry.py
    - tests/test_verify_registry.py

key-decisions:
  - "Verified edits and exit code come from the post-bump final report when --write is set"
  - "EXIT_USAGE (64) for malformed --candidate; inconclusive remains exit 2"

patterns-established:
  - "Registry writer never reformats: one-line replacements anchored in tool/method regions"

requirements-completed: [REG-02, REG-03]

coverage:
  - id: D1
    description: "--write updates verified only for tools in passed_tools() after final report"
    requirement: REG-02
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_write_dates_only_passing_tools
        status: pass
    human_judgment: false
  - id: D2
    description: "Scoped registry edits with tomllib guard; no comment or off-target changes"
    requirement: REG-02
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_writer_keeps_every_other_byte
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_writer_refuses_an_unintended_change
        status: pass
    human_judgment: false
  - id: D3
    description: "GitHub and --candidate pin bumps with all-or-nothing multi-method updates"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_newer_github_pin_is_bumped_when_the_candidate_passes
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_candidate_flag_bumps_a_pin_without_a_release_source
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_one_failing_method_blocks_the_whole_tool_bump
        status: pass
    human_judgment: false
  - id: D4
    description: "As-written report replaces superseded pin findings; unpinned drift preserved"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_write_run_after_a_bump_reports_the_registry_as_written
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_bump_keeps_the_findings_of_the_tools_unpinned_methods
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-15
status: complete
---

# Plan 18-13 Summary

**Maintainer `--write` records `verified`/`version`/`sha256` via guarded line edits; pin bumps run a pinned-only candidate check and report the registry as written.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `apply_registry_edits` + `RegistryWriteError` with tomllib semantic guard; `--write` stamps `verified` only for `passed_tools()`.
- Auto and explicit `--candidate` bumps update all pinned methods together; failed candidates add `bump to … not applied` drift.
- Final report under `--write` drops findings on superseded pinned URLs, keeps unpinned drift, and drives exit code.

## Task Commits

1. **Task 1: `--write` dates exactly the passing tools, guarded by a tomllib re-parse** — `9839341`
2. **Task 2: pin bump through a candidate check; `--candidate` for non-GitHub pins** — `c6a067c`

**Plan metadata:** (this commit) `docs(18-13): plan summary`

## TDD RED evidence (Task 1)

```
ImportError: cannot import name 'RegistryEdit' from 'installer.verify_registry'
```

## Verify commands

- `uv run pytest tests/test_verify_registry.py -q --no-cov -k "write or writer"` — 6 passed
- `uv run pytest tests/test_verify_registry.py -q --no-cov -k "bump or candidate or pin_keys"` — 9 passed
- `uv run pytest tests/test_verify_registry.py tests/test_model.py tests/test_registry.py -q --no-cov` — passed
- `make validate && make test` — passed (3846 tests, coverage 95.30%)

## Deviations from Plan

- **Test helper fix:** `test_writer_keeps_every_other_byte` uses `Counter` diff because many tools share the same `verified = 2026-10-13` line in the real registry (same intent as plan: exactly one line change for `jq`).
- **Test dates:** bump/write tests use `date(2026, 10, 15)` so `load_tools` future-date validation passes on the execution host (2026-10-15).

## Issues Encountered

None blocking. Sublime bump fixtures needed `archive = "xz"` and matching `sha256` for old pins.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
