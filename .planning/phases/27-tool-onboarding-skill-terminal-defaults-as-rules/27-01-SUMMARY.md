---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
plan: 01
subsystem: tool-onboarding skill and its tests
tags: [skill, terminal, registry-coverage, docs-only-ledger, skill-judge]
requires: []
provides:
  - "Closed per-terminal table (8 rows) in .claude/skills/tool-onboarding/SKILL.md step 7"
  - "tests/test_tool_onboarding_skill.py: table_drift, registry coverage test, malformed-table fixtures"
  - "27-SKILLJUDGE-before.md: BEFORE verdict 69.6% D (87/125, rubric v4), committed on the unedited skill"
affects: [27-02, 27-03, 27-04, phase-28, phase-29]
actuals:
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns:
    - "A closed table in a skill, with a pure drift function and a test that keeps it in step with the registry"
    - "Pre-dispatch orchestrator step for a verdict the executor must never fabricate (autonomous: false)"
key-files:
  created:
    - tests/test_tool_onboarding_skill.py
    - .planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-before.md
  modified:
    - .claude/skills/tool-onboarding/SKILL.md
    - tests/test_docs_only.py
key-decisions:
  - "VS Code (d) same-directory cell is `unverified` (terminal.integrated.splitCwd, a terminal setting, not a keybinding)"
  - "The registry test asserts a non-empty id list and table_drift == [], with no row count, so a new terminal adds its row without editing the test"
requirements-completed: [SKILL-02, SKILL-06]
coverage:
  - id: D1
    description: "Closed per-terminal table with one row per terminal or editor registry entry"
    requirement: "SKILL-02"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k table (14 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A missing, extra, duplicate, case-variant, shuffled, header-only or lookalike row, or a bad status word, fails the test"
    requirement: "SKILL-02"
    verification:
      - kind: unit
        ref: "tests/test_tool_onboarding_skill.py fixtures (bad_status_cells, table has no rows), orchestrator run"
        status: pass
    human_judgment: false
  - id: D3
    description: "BEFORE skill-judge verdict committed from a fresh read-only judge on the unedited skill"
    requirement: "SKILL-06"
    verification:
      - kind: other
        ref: "Task 1 verify commands (parser, rubric maxima, git log proof, SKILL.md equals 1bb31e00 at the verdict commit)"
        status: pass
    human_judgment: false
duration: 8min (executor) plus the orchestrator pre-dispatch step
completed: 2026-11-20
---

# Phase 27 Plan 01 Summary

- **Task 1 — orchestrator prerequisite verified:** commit `84f567c9`. Both verify commands passed; the verdict parses with rubric v4 maxima and is committed against the unedited skill.
- **Task 2 — closed terminal table and registry coverage:** commit `432d9e35`. RED: 4 table tests failed because the subsection was missing. GREEN: the required table, docs-only, docs and catalog-audit tests passed; `make validate && make test` passed (**7,828 passed, 6 skipped**).
- **Task 3 — malformed-table checks:** commit `d7ce3adf`. RED: 9 tests failed against the minimal helpers. GREEN: table tests passed (**14 passed**); `make validate && make test` passed (**7,837 passed, 6 skipped**).

**Verification:** The final combined regression command passed. The three task commits appear in order; the table heading occurs once and the skill contains 12 backticked tool rows. Pre-existing planning changes remain untouched.

**Deviations:** The first validation attempts caught line-length/formatting issues in the new test fixture; corrected them and reran the gates successfully. `.claude` is ignored in this checkout, so the skill file required an explicit `git add -f` by path.

Skipped: no additional review beyond the plan's tests and gates. Risk: this plan did not produce the after skill-judge verdict.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 8 minutes (01:29 to 01:37), stderr empty. Two commits by the executor (`432d9e35`, `d7ce3adf`); Task 1 made none, as designed.
- **Checked by the orchestrator:** all plan acceptance greps for Tasks 2 and 3 pass (heading count 1, 12 backticked rows, `table_drift` defined once, LEDGER row present, kitty XDG cell, `terminal.integrated.splitCwd`, `with-row` fixture, `bad_status_cells`, `table has no rows` twice); no `noqa`, `type: ignore`, `nosec`, skip or xfail marker in the new test file; `SKILL.md` gained 19 added lines and no deleted line against 1bb31e00; `uv run pytest tests/test_tool_onboarding_skill.py tests/test_docs_only.py tests/test_docs.py tests/test_catalog_audit_skill.py -n auto -q --no-cov` passes; `-k table` runs 14 tests, all passing; the three files that were already dirty before the dispatch (`.planning/STATE.md`, `.planning/state.json`, the untracked goals file) are byte-identical before and after.
- **Reported by the executor and not re-run by the orchestrator:** the two full `make validate && make test` runs and their counts (7,828 and 7,837 passed). The full suite runs again at the push gate.
- **Note:** the executor says `.claude` is ignored in this checkout. `SKILL.md` is tracked, so edits to it are unaffected; a new untracked file under `.claude/` would need `git add -f`, which matters for any plan that adds files there.
