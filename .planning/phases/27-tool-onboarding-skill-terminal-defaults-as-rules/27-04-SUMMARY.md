---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
plan: 04
subsystem: skill-judge verdicts and their tests
tags: [skill-judge, verdict-test, shared-parser, docs-only-ledger, fix-round]
requires:
  - phase: 27-03
    provides: the final skill text the after verdict judges
provides:
  - "27-SKILLJUDGE-after.md: AFTER verdict 72.0% C (90/125, rubric v4) against BEFORE 69.6% D (87/125), same spec_sha"
  - "27-SKILLJUDGE-ROUND-1.md: the first after judgment (68.8%), recorded under D-08 before the fix round"
  - "tests/skill_verdicts.py: the verdict parser and grader shared by the catalog-audit and tool-onboarding tests"
  - "Verdict tests: two non-ROUND files by exact name, same skill, rubric maxima, rubric_version and spec_sha, after >= before (no floor)"
  - "TEST_READ entry and four LEDGER globs so the verdict files are classified as read by tests"
affects: [phase-28, phase-29, phase-31, phase-32]
actuals:
  tasks: 3
  commits: 5
tech-stack:
  added: []
  patterns:
    - "A verdict from a fresh read-only judge, bracketed by a tree snapshot diff, recorded with the judged SKILL.md blob"
    - "Fix rounds kept as ROUND files outside the counted verdict names"
key-files:
  created:
    - tests/skill_verdicts.py
    - .planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-after.md
    - .planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-ROUND-1.md
  modified:
    - tests/test_catalog_audit_skill.py
    - tests/test_tool_onboarding_skill.py
    - tests/test_docs_only.py
    - devtools/docs_only.py
    - .claude/skills/tool-onboarding/SKILL.md
key-decisions:
  - "The first after judgment scored lower (68.8% against 69.6%), so D-08 applied: ROUND-1 recorded, the skill fixed, a fresh judge run again (72.0%). The before verdict was never re-run"
  - "The round 1 fixes are text only (description boundary, review-mode bullet, step 9 mechanics and validation, reasons in Common Mistakes, the opencode remove fact); evals were not added in this phase"
requirements-completed: [SKILL-06]
coverage:
  - id: D1
    description: "Before and after skill-judge verdicts exist, come from fresh read-only judges under one rubric, and the after is not lower"
    requirement: "SKILL-06"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tool_onboarding_skill.py -k verdict (4 passed, orchestrator run)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The verdict parser is shared and the catalog-audit tests keep every assertion (58) and still pass"
    requirement: "SKILL-06"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_catalog_audit_skill.py (orchestrator run, four-file targeted run passes)"
        status: pass
    human_judgment: false
duration: 8min (executor) plus the orchestrator pre-dispatch judge rounds
completed: 2026-11-20
---

# Phase 27 Plan 04 Summary

- Task 1 — verified by the orchestrator in commit `522b9ee3`. The committed after verdict scored 72.0% versus 69.6% before, with the same rubric and maxima; the before verdict remains untouched. `27-SKILLJUDGE-ROUND-1.md` is present.
- Task 2 — commit `3684d2aa`: shared the verdict parser and grader in `tests/skill_verdicts.py`; catalog-audit assertions remain at 58. Targeted tests and pyright passed.
- Task 3 — commit `7c24e88c`: added verdict regression checks and CI test-read classification. Targeted tests passed, including four verdict tests.

**Test output**
- Task 1: `OK 69.6 72.0`; `AFTER-COMMITTED-BEFORE-UNTOUCHED`.
- Task 2: 51 targeted tests passed; pyright reported 0 errors.
- Task 3 RED: 3 failures, each `NameError` for the not-yet-defined `verdict_regressions` helper.
- Task 3 GREEN: 98 targeted tests passed; 4 verdict tests passed; pyright reported 0 errors.
- Final gates: `make validate` passed. `make test`: 7,870 passed, 6 skipped; 96.21% coverage.

No deviations. The pre-existing untracked goals file was left untouched.

Skipped: no additional review or checks beyond the plan's verification. Risk: none known.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Pre-dispatch work by the orchestrator (D-06, D-08):**
  - Attempt 1 judged blob `76d1b18c` (333 lines): 68.8% (86/125), lower than the before 69.6%, same rubric v4 and spec_sha. It is recorded as `27-SKILLJUDGE-ROUND-1.md`.
  - Fix round 1 (commit `d2cf60ee`, text only, 333 to 331 lines): description gained a "Not for" boundary without naming the audit skill (a test allows exactly one line naming it), a review-mode bullet, step 9 now separates `postinstall` from `post_install` and names the validation commands and the container route, Common Mistakes carry their reasons and four restating bullets were removed, the `remove` example no longer says no entry ships one (opencode does), and step 6's broken sentence was rewritten.
  - Attempt 2 judged blob `6a6f4f8e`: **72.0% C (90/125)**, committed as `27-SKILLJUDGE-after.md` in `522b9ee3`.
  - Both judge runs were bracketed by a tree snapshot (status, diff hash, hashes of untracked files) and both diffs were empty, so neither judge wrote anything.
  - All three verdict JSON lines are byte-identical to what the judges printed (checked by script against the judge transcripts; one transcription slip in the after file was found and fixed before its commit).
- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 8 minutes (02:23 to 02:31), stderr empty, two commits (`3684d2aa`, `7c24e88c`); the executor changed no verdict file and no SKILL.md; the untracked goals file is byte-identical.
- **Checked by the orchestrator:** the plan's acceptance checks pass, one exception below; Task 1's first verify prints `OK 69.6 72.0` and the second prints `AFTER-COMMITTED-BEFORE-UNTOUCHED`; the catalog-audit test still has 58 `assert` lines, unchanged from before; no bypass marker in the changed files; the four-file targeted run passes and `-k verdict` runs 4 passing tests; I read the verdict test and it matches D-06 (two non-ROUND names, same skill, rubric maxima, rubric_version, spec_sha, after >= before as numbers, boundary and mixed-rubric fixtures).
- **Deviation in a plan check, not in the result:** the plan expects one `from tests.skill_verdicts import` line in the catalog-audit test; there are four, one per aliased name, because ruff's isort keeps aliased imports as separate statements. All four old private names (`_DIMENSIONS`, `_RUBRIC_MAX`, `_grade`, `_parse_verdict`) still resolve.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,870 passed, 96.21% coverage). The push gate runs the full suite again.
- **Open skill findings, deliberately not fixed in this phase (for the owner):**
  - D7, no `evals/`: the catalog-audit skill ships `evals/evals.json` and `trigger-queries.json` with shape tests, so the same would apply here; it would be new files under the gitignored `.claude/` (`git add -f`) and new test code. It is the largest single loss (13 to 15 points of 125).
  - D8-1: step 2 says the catalog installs no skills, then advises symlinking into a host's skills directory; an agent gets two answers.
  - D5: the skill is 331 lines (about 6,400 tokens); the terminal and macOS-app blocks could move to `references/` behind a condition, which would also repoint `tests/test_tool_onboarding_skill.py`.
  - Judge noise: D7 scored 2 then 0 on an unchanged evals gap, so single scores move by a few points either way.
