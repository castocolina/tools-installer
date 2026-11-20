---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
plan: 02
subsystem: tool-onboarding skill and its tests
tags: [skill, terminal-defaults, rules-not-questions, catalog-audit-quote]
requires:
  - phase: 27-01
    provides: the closed per-terminal table and tests/test_tool_onboarding_skill.py
provides:
  - "Step 7 renamed 'terminal defaults are rules, extras are asked' with four rules (a) to (d) stated without asking"
  - "#### Extras are asked: only non-terminal extras stay questions"
  - "Tests: five rules tests, negation tests for the question detector and for Option-as-Alt, with mutation fixtures (14 rules tests)"
affects: [27-03, 27-04, phase-28, phase-29]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "Skill rule text pinned by a test that compares rule letters as a sorted set, not an order"
key-files:
  created: []
  modified:
    - .claude/skills/tool-onboarding/SKILL.md
    - .claude/skills/catalog-audit/SKILL.md
    - tests/test_tool_onboarding_skill.py
key-decisions:
  - "Rule (c) states the zsh half (Ctrl+L clears scrollback) as planned for phase 28 (KEYS-03): nothing in installer/ does it today"
  - "Rules apply to every entry that has the capability; the table marks the rest n/a with the reason"
requirements-completed: [SKILL-01]
coverage:
  - id: D1
    description: "The four terminal and IDE defaults are stated as rules that are never questions and never Policies rows, and the global Option-as-Alt switch is never recommended"
    requirement: "SKILL-01"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k rules (14 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Step 7 pinned phrases and the catalog-audit heading quote still resolve after the rename"
    requirement: "SKILL-01"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_docs.py tests/test_catalog_audit_skill.py (orchestrator run, 4-file targeted run passes)"
        status: pass
    human_judgment: false
duration: 14min (executor)
completed: 2026-11-20
---

# Phase 27 Plan 02 Summary

- **Task 1 — `98fee00d`:** Added the renamed step 7 heading, four terminal-default rule items, and the matching catalog-audit quote. RED: five rules tests failed because the subsection was missing. GREEN: the targeted combined tests and all five rules tests passed.
- **Task 2 — `53e99843`:** Moved author questions to `#### Extras are asked`, revised the description, Overview, step 9 and Common Mistakes, and added checks for default-related questions and unnegated Option-as-Alt references. RED: five behavior checks failed before the prose changes. GREEN: the specified targeted regression tests passed; all 14 rules tests passed.
- **End-of-plan gates:** `make validate` passed. `make test` passed: **7,851 passed, 6 skipped**; total coverage **96.21%**.
- **Deviation:** The commit hook caught formatting and line-length issues during both tasks. I corrected them and retried the commits; the successful commit hooks passed all six static gates. No other plan deviation.

Skipped: no separate branch review; no code beyond this plan's files was changed. Risk: the pre-existing untracked planning file remains untouched.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 14 minutes (01:40 to 01:55), stderr empty, two commits (`98fee00d`, `53e99843`).
- **Checked by the orchestrator:** all 15 plan acceptance greps pass for Tasks 1 and 2 (renamed heading in the skill and in the catalog-audit quote, old phrases gone, four rule items, `that has the capability` once, `#### Extras are asked` once, `option-as-alt` twice); the two pinned phrases `none of them is a question` and `never a Policies row` are intact; no `noqa`, `type: ignore`, `nosec`, skip or xfail marker in the test file; the four-file targeted run (`test_tool_onboarding_skill`, `test_docs_only`, `test_docs`, `test_catalog_audit_skill`) passes; `-k rules` runs 14 tests, all passing; I read the rewritten rules and extras text and it matches the locked decisions; the untracked goals file is byte-identical and `STATE.md` and `state.json` were not touched.
- **Reported by the executor and not re-run by the orchestrator:** `make validate`, and the full `make test` run (7,851 passed, 96.21% coverage). The push gate runs the full suite again.
