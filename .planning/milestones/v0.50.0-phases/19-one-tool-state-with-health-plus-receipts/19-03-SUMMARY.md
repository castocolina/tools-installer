---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "03"
subsystem: core
tags: [health, pure-function, precedence, string-enum, tdd]

requires:
  - phase: 18
    provides: version_status module and test conventions this plan extends
provides:
  - Health StrEnum whose declaration order is precedence (CHECKING, BROKEN, MISCONFIGURED, OUTDATED, OK, MISSING, UNAVAILABLE)
  - Evidence frozen dataclass (present, available, checking/broken/misconfigured/outdated/notes, absent_reason)
  - pure tool_health(ev) -> (Health, reasons) mapping every evidence combination to one mark plus ordered reasons
affects: [19-08 builder, 19-12/14/16 evidence plans, 19-13/15 catalog views]

actuals:
  tokens: 6100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "closed StrEnum whose declaration order is precedence (D-01)"
    - "pure evidence-to-mark mapping; notes carry configuration facts for absent tools (checker B1/W1)"

key-files:
  created:
    - tests/test_tool_health.py
  modified:
    - installer/version_status.py

key-decisions:
  - "Reasons are de-duplicated keeping first occurrence (dict.fromkeys); absent tools keep only absent_reason + notes, present-only facts are dropped"
  - "UNAVAILABLE puts absent_reason first, then notes in the given order; notes are never re-sorted"

patterns-established:
  - "Pattern: tool_health is the single evidence-to-mark function; nothing else decides a mark"
  - "Pattern: typed parametrize rows via a Row alias so pyright accepts table-driven tests"

requirements-completed: [STATE-02]

coverage:
  - id: D1
    description: Health StrEnum with precedence-ordered declaration and lower-case values
    requirement: STATE-02
    verification:
      - kind: unit
        ref: tests/test_tool_health.py#test_health_declaration_order_is_precedence
        status: pass
  - id: D2
    description: tool_health maps every present evidence combination by precedence CHECKING > BROKEN > MISCONFIGURED > OUTDATED > OK, and absent tools to MISSING/UNAVAILABLE
    requirement: STATE-02
    verification:
      - kind: unit
        ref: tests/test_tool_health.py#test_tool_health_precedence_table
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_tool_health_precedence_table_absent
        status: pass
  - id: D3
    description: Reasons ordered winner-first, then precedence, then notes; broken+outdated yields BROKEN with both reasons; duplicates listed once; notes never change the state
    requirement: STATE-02
    verification:
      - kind: unit
        ref: tests/test_tool_health.py#test_broken_and_outdated_is_broken_with_both_reasons
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_reasons_put_the_winner_first_then_precedence_then_notes
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_duplicate_sentences_are_listed_once
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_notes_never_change_the_state
        status: pass
  - id: D4
    description: Absent tools keep their notes in the caller's order and drop present-only facts (19-08 builder contract)
    requirement: STATE-02
    verification:
      - kind: unit
        ref: tests/test_tool_health.py#test_absent_tool_keeps_configuration_notes
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_absent_tools_ignore_present_only_facts
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_missing_keeps_its_notes
        status: pass
      - kind: unit
        ref: tests/test_tool_health.py#test_unavailable_lists_its_reason_first
        status: pass

duration: 25min
completed: 2026-10-16
status: complete
---

# Plan 19-03 Summary

**Pure `Health`/`Evidence`/`tool_health` core in `installer/version_status.py` — one function maps every evidence combination to exactly one mark with ordered reasons, proven by an 18-row parametrized table plus 9 behavior tests.**

## Performance

- **Duration:** 25 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `Health(StrEnum)` with declaration order = precedence (D-01): CHECKING, BROKEN, MISCONFIGURED, OUTDATED, OK, MISSING, UNAVAILABLE; values are lower-case names.
- Frozen `Evidence` dataclass; `tool_health` is pure: present tools take the first non-empty of checking > broken > misconfigured > outdated, else OK; absent tools are MISSING (method applies) or UNAVAILABLE (none).
- Reason ordering per 19-UI-SPEC A12: winner's facts, then the other states' facts in precedence order, then notes; UNAVAILABLE lists absent_reason first; notes survive absence in the caller's order (the 19-08 B1/W1 contract); present-only facts are dropped for absent tools; duplicates listed once at first occurrence.

## Task Commits

1. **Task 1: the precedence table maps every evidence combination to one Health** - `74ff98b` (feat)
2. **Task 2: tool_health orders its reasons for the focused-row detail** - `362d59e` (feat)

## TDD Evidence

Task 1 RED (before implementation):
```
ERROR tests/test_tool_health.py - ImportError: cannot import name 'Evidence' from 'installer.version_status'
!!! Interrupted: 1 error during collection !!!
```

Task 2 RED: none observed — the plan's Task 1 `<implementation>` already directed the full Task-2 reason ordering ("Reasons per Task 2 (in this task: winner's facts, then the others in precedence order, then notes)"), so the seven Task 2 tests passed on first run (27 passed). The tests still pin the contract; the implementation did not change in Task 2.

## Verification

- `uv run pytest tests/test_tool_health.py -q --no-cov` — 27 passed (18 table rows + 9 tests)
- `uv run pytest tests/test_tool_health.py -n auto -q --no-cov` — 27 passed
- `make validate` — exit 0 (ruff, format, pyright, bandit, vulture, shellcheck)
- `make test` — 4067 passed, 4 skipped; coverage 95.54% (gate 90%)
- Suppression check: no new `type: ignore`/`noqa`/etc.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` — no new dependencies

## Deviations from Plan

- Task 2 had no distinct RED run because Task 1's implementation sketch already specified the complete reason ordering; tests were still added first and pass. No behavior or scope change.

## Issues Encountered

- Pyright flagged untyped parametrize parameters in the new test file; fixed by annotating the table rows (`Row` alias) and test signatures — no suppressions added.
- Ruff isort wanted `from enum import StrEnum` merged into the from-import block; fixed by `ruff check --fix`.

## Next Phase Readiness

- 19-08's builder can now call `tool_health` and pass an absent tool's configuration facts as the leading notes, per the pinned `test_absent_tool_keeps_configuration_notes`.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
