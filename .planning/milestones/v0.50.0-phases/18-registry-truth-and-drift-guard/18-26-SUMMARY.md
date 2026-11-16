---
phase: 18-registry-truth-and-drift-guard
plan: "26"
subsystem: testing
tags: [verify-registry, registry, tomllib, exit-codes, tdd]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: verify_registry checker/transport fixes from plans 18-24 and 18-25
provides:
  - Snapshot-bound `--write` with EXIT_WRITE_REFUSED (73)
  - Usage validation before network; EXIT_INTERNAL (70) crash wrapper
  - Documented exit codes in module docstring and `--help`
  - Mutation-backed writer guard, auto-bump refusal, and unpinned-key tests
affects: [18-registry-truth-and-drift-guard, verify-registry workflow]

actuals:
  tokens: 0
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Registry text loaded once; write path compares on-disk bytes before atomic_write_text"
    - "main catches Exception only; BaseException (argparse, simulated kill) propagates"

key-files:
  created: []
  modified:
    - installer/verify_registry.py
    - tests/test_verify_registry.py

key-decisions:
  - "RegistryWriteError from write path maps to exit 73, not 64, so usage and write refusal stay distinct (L-18-17)."
  - "Removed vacuous file round-trip from test_writer_refuses_an_unintended_change; file safety covered by Task 1 exit-73 test."

patterns-established:
  - "Guard coverage proven by mutation RED (remove TOMLDecodeError wrapper, remove expected_doc check, neutralize auto-bump refusal)."

requirements-completed: [REG-02, REG-03]

coverage:
  - id: D1
    description: "--write applies only to the registry bytes loaded at start; concurrent edit exits 73 untouched"
    requirement: REG-02
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_write_refuses_when_the_registry_changed_during_the_run
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_refused_write_leaves_the_registry_untouched_and_exits_73
        status: pass
    human_judgment: false
  - id: D2
    description: "Usage and internal/upsert exit semantics; --help documents 0/1/2/64/70/73"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_candidate_usage_errors_cost_no_network
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_an_unexpected_error_exits_70_not_1
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_help_lists_the_exit_codes
        status: pass
    human_judgment: false
  - id: D3
    description: "Writer D-09 guards and auto-bump/unpinned invariants pinned by tests"
    requirement: REG-02
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_writer_guard_refuses_an_edit_that_breaks_the_toml
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_auto_bump_with_different_newer_tags_is_not_applied
        status: pass
    human_judgment: false

duration: 0min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 26 Summary

**verify-registry `--write` is snapshot-bound (exit 73 on refusal), usage errors skip the network, crashes exit 70, and writer/auto-bump guards are mutation-proven in tests.**

## Performance

- **Tasks:** 3 (+ summary commit)
- **Files modified:** 2 (`installer/verify_registry.py`, `tests/test_verify_registry.py`)
- **Line counts (final):** `tests/test_verify_registry.py` 3976; `installer/verify_registry.py` 1769

## Finding disposition

| ID | Source | Outcome | Commit | Test |
|----|--------|---------|--------|------|
| opencode HIGH (snapshot write) | 18-REVIEW-opencode | Fixed | `df8cd04` | `test_write_refuses_when_the_registry_changed_during_the_run` |
| WR-06 write half (exit 64 on refusal) | 18-REVIEW | Fixed | `df8cd04` | `test_refused_write_leaves_the_registry_untouched_and_exits_73` |
| WR-06 usage half | 18-REVIEW | Fixed | `b11bee2` | `test_candidate_usage_errors_cost_no_network` |
| WR-04 main (crash → drift) | 18-REVIEW | Fixed | `b11bee2` | `test_an_unexpected_error_exits_70_not_1` |
| WR-04 upsert JSON | 18-REVIEW | Fixed | `b11bee2` | `test_malformed_gh_issue_list_is_an_upsert_failure` |
| WR-05 writer guards | 18-REVIEW | Test-only | `806f2f0` | `test_writer_guard_refuses_*` |
| opencode LOW (unpinned keys) | 18-REVIEW-opencode | Test-only | `806f2f0` | `test_unpinned_entries_never_gain_pin_keys` |
| ponytail #16 / IN-02 | 18-REVIEW-ponytail | Fixed | `b11bee2` / `df8cd04` | housekeeping + `_plan_bumps` in write try |

## Task commits

1. **Task 1: snapshot-bound `--write`, exit 73** — `df8cd04`
2. **Task 2: usage before network, exit 70, documented codes** — `b11bee2`
3. **Task 3: guard / auto-bump / unpinned tests** — `806f2f0`

## TDD RED evidence

**Task 1** (`uv run pytest … -k "changed_during_the_run or untouched_and_exits_73"`):

```
ImportError: cannot import name 'EXIT_WRITE_REFUSED' from 'installer.verify_registry'
```

**Task 2** (`… -k "cost_no_network or exits_70_not_1 …"`):

```
ImportError: cannot import name 'EXIT_INTERNAL' from 'installer.verify_registry'
```

**Task 2 mutation** (`test_gh_command_failure_during_upsert_exits_2`, upsert exit forced to 1):

```
AssertionError: assert 1 == 2
```

## Mutation RED (Task 3)

1. **TOML guard removed:** `test_writer_guard_refuses_an_edit_that_breaks_the_toml` → `tomllib.TOMLDecodeError: Cannot overwrite a value`
2. **`new_doc != expected_doc` removed:** `test_writer_guard_refuses_an_edit_that_changes_another_value` → `Failed: DID NOT RAISE RegistryWriteError`
3. **Auto-bump refusal neutralized:** `test_auto_bump_with_different_newer_tags_is_not_applied` → missing `pinned methods report different newer tags` in report
4. **Unpinned injection (local):** appending `version = "1"` under a method before `tomllib.loads(after)` fails the new set-difference assertion (old loop would still pass)

## Verify commands

| Command | Result |
|---------|--------|
| Task 1: `uv run pytest tests/test_verify_registry.py -q --no-cov` | pass |
| Task 2: `uv run pytest tests/test_verify_registry.py tests/test_verify_registry_workflow.py tests/test_makefile.py -q --no-cov` | pass |
| Task 3: `uv run pytest … -k "writer_guard or … never_gain_pin_keys"` | 5+ pass |
| Final: `make validate && make test` | pass (3927 passed, coverage 95.63%) |
| `uv run python -m installer.verify_registry --help` | lists 64, 70, 73 |

## Coverage (`installer.verify_registry.py`)

Scratch run: **91%** line coverage on `tests/test_verify_registry.py` alone (`COVERAGE_FILE=$SCRATCH/.cov uv run pytest tests/test_verify_registry.py --cov=installer.verify_registry --cov-report=term -q -p no:randomly`).

## `wc -l` / `git diff --stat` (Task 1 pre-commit vs HEAD)

- Task 1: +125 / -13 across `verify_registry.py` and `test_verify_registry.py`; tests 3623 → 3728 functions (net +2 tests)
- Task 2: +164 / -26
- Task 3: +144 / -10 (tests only)

## Deviations from plan

- **Large-file edits:** Used out-of-repo Python patch scripts (`/tmp/18-26-task3-tests.py`, inline patchers) instead of pi `edit` on `tests/test_verify_registry.py` after one `StrReplace` truncated the file (restored via `git checkout`).
- **Task 3 multiline TOML fixture:** Built registry `desc` via string concatenation to avoid Python `"""` nesting / f-string `2026-10-01` arithmetic parse errors.

## Issues for orchestrator

- None. Final review: **self-review (no subagent tool)** on commits `df8cd04..806f2f0`.

---
*Phase: 18-registry-truth-and-drift-guard*
*Plan: 26*
*Completed: 2026-10-15*
