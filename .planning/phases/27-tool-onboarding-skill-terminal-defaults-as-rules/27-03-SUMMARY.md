---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
plan: 03
subsystem: tool-onboarding skill and its tests
tags: [skill, conflicts, macos, ci-workflow-check, verified-examples]
requires:
  - phase: 27-02
    provides: step 7 rules and the extras text
provides:
  - "#### Conflicts: a user's own binding is kept (partial: kept yours); a displaced vendor default is named in an install note"
  - "#### Testing macOS behavior: pure config generators with golden-file tests, CI coverage by the validate-and-test job, real-Mac check deferred to the owner"
  - "#### macOS apps under step 4: ~/Applications, CLI into ~/.local/bin, say why when no method allows it, with platform gaps recorded"
  - "Three separate # Verified examples in step 9 (cask, app kind, dmg-only)"
  - "ci_workflow_problems: a structural check of .github/workflows/ci.yml with fixed-runner and inverted-gate mutation fixtures"
affects: [27-04, phase-28, phase-29, phase-31]
actuals:
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns:
    - "A skill's CI claim is checked by parsing the workflow with yaml.safe_load, not by grepping strings"
key-files:
  created: []
  modified:
    - .claude/skills/tool-onboarding/SKILL.md
    - tests/test_tool_onboarding_skill.py
key-decisions:
  - "Conflict item 1 uses today's alacritty partial line as its example; the kitty scroll_line_up example is labelled planned for phase 29"
  - "Platform gaps (a .dmg-only app, a cask's CLI link) are recorded as gaps, never promised as a mechanism"
requirements-completed: [SKILL-03, SKILL-04, SKILL-05]
coverage:
  - id: D1
    description: "Conflict rule: a user's binding is kept and reported partial: kept yours; a displaced vendor default is named"
    requirement: "SKILL-03"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k conflicts (3 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D2
    description: "macOS app rule: ~/Applications, CLI into ~/.local/bin, the say-why clause, and three consistent # Verified examples"
    requirement: "SKILL-04"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k macos_apps (4 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D3
    description: "macOS testing rule names the CI job, and a test ties that job to ci.yml structurally (matrix, matrix-driven runner, gated Test step running make test)"
    requirement: "SKILL-05"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k macos_testing (5 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real-Mac behavior of the macOS rules"
    requirement: "SKILL-05"
    verification: []
    human_judgment: true
    rationale: "No Mac host in this run; the skill states a deferred UAT line for the owner's Mac and no agent marks it passed"
duration: 14min (executor)
completed: 2026-11-20
---

# Phase 27 Plan 03 Summary

- **Task 1 — `3336cec8`:** Added the step 7 conflict rule and tests. **RED:** 3 conflict tests failed because `#### Conflicts` was missing. **GREEN:** all 3 conflict tests passed; the targeted regression run passed.
- **Task 2 — `14e3e995`:** Added the macOS testing rule and structural CI workflow checks, including fixed-runner and inverted-gate mutation cases. **RED:** 2 of 5 macOS-testing tests failed because the subsection was missing. **GREEN:** all 5 macOS-testing tests passed; the targeted regression run passed.
- **Task 3 — `47a4ab94`:** Added the step 4 macOS apps rule and three separate step 9 `# Verified` examples. **RED:** all 4 macOS-app tests failed before the skill edits. **GREEN:** all 4 macOS-app tests passed; the targeted regression run passed.
- **End-of-plan targeted regression:** `tests/test_tool_onboarding_skill.py`, `tests/test_docs.py`, and `tests/test_catalog_audit_skill.py` passed. The three focused conflict, macOS-testing, and macOS-app test runs also passed.
- **End-of-plan gates:** `make validate` passed all six static gates. `make test` passed: **7,863 passed, 6 skipped**, **96.21%** total coverage.
- **Deviation:** Commit hooks caught test formatting and line-length issues during the first commit attempts. I corrected them and retried; all three commits passed their hooks. No other plan deviation.

Skipped: no fresh branch review or real-Mac UAT. The pre-existing untracked planning file remains untouched.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 14 minutes (01:56 to 02:10), stderr empty, three commits (`3336cec8`, `14e3e995`, `47a4ab94`) touching only `SKILL.md` and `tests/test_tool_onboarding_skill.py`; `.github/workflows/ci.yml` is unchanged.
- **Checked by the orchestrator:** all 15 plan acceptance checks pass (headings once each, `partial: kept yours`, `scroll_line_up` twice, the alacritty example once, `validate-and-test` once, `golden-file` once, `yaml.safe_load` once, `ci_workflow_problems` once, both mutation fixtures named, `~/Applications` on six lines, the two bundle `# Verified` lines and the `.dmg` line); no bypass marker in the test file; the four-file targeted run passes; `-k conflicts` runs 3, `-k macos_testing` 5 and `-k macos_apps` 4 tests, all passing (`-k table` now selects 16 and `-k rules` 15, because new test names contain those words); I read the added skill text and it matches D-10, D-12 and D-15; the untracked goals file, `STATE.md` and `state.json` are byte-identical across the run.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,863 passed, 96.21% coverage). The push gate runs the full suite again.
- **Open for the owner:** the real-Mac check of the macOS rules is a deferred UAT line (D4 above); this run has no Mac.
