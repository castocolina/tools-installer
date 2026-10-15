---
phase: 18-registry-truth-and-drift-guard
plan: "21"
subsystem: testing
tags: [docs, architecture, truncation-guard, pytest]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: Phase 18 registry authoring paragraphs in architecture.md (plans 18-01, 18-20)
provides:
  - Restored Phase 15.8 tail in `.claude/architecture.md` (1024 lines, byte-exact splice)
  - Truncation banner and Phase 15.8 anchor tests in `tests/test_docs.py`
affects: [registry-truth, agent-rule-documents, rcclean, shellrc-consolidation]

actuals:
  tokens: 3750
  tasks: 1
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Rule-document truncation guard: banner fragments + trailing newline scan"
    - "Phase doctrine anchors via `_PHASE_*_REQUIRED` tuples in test_docs.py"

key-files:
  created: []
  modified:
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "Restored lost doctrine via out-of-repo splice (head 882 + git show 22e6c5e tail), not in-editor replace"

patterns-established:
  - "test_rule_documents_carry_no_truncation_banner scans explicit rule paths plus docs/**/*.md"

requirements-completed: [REG-01, REG-02, REG-05]

coverage:
  - id: D1
    description: Phase 15.8 architecture doctrine restored after 18-01 truncation (CR-01)
    requirement: REG-01
    verification:
      - kind: unit
        ref: tests/test_docs.py#test_architecture_records_phase_15_8_mechanisms
        status: pass
      - kind: other
        ref: "bash byte-exact restoration check (1024 lines; head=6794a65; tail=22e6c5e:867-1008)"
        status: pass
    human_judgment: false
  - id: D2
    description: Rule documents fail the suite on edit-tool truncation banners or missing EOF newline
    requirement: REG-02
    verification:
      - kind: unit
        ref: tests/test_docs.py#test_rule_documents_carry_no_truncation_banner
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 21 Summary

**Restored ~140 lines of Phase 15.8 binding doctrine in `.claude/architecture.md` and added pytest guards so truncation banners or missing EOF newlines fail `make test`.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 1
- **Files modified:** 2 (implementation commit)

## Accomplishments

- Closed REVIEW CR-01: removed the pasted `[Showing lines … Use offset=]` banner and restored lines 867–1008 from `22e6c5e` verbatim while keeping Phase 18 paragraphs near line 220.
- Added `test_rule_documents_carry_no_truncation_banner` and `test_architecture_records_phase_15_8_mechanisms`.

## Review findings (per-finding)

| ID | Source | Outcome | Commit | Test |
|----|--------|---------|--------|------|
| CR-01 | 18-REVIEW.md | fixed | `3d77d65` | `test_rule_documents_carry_no_truncation_banner`, `test_architecture_records_phase_15_8_mechanisms` |

## Task Commits

1. **Task 1: truncated rule doc fails suite + Phase 15.8 restoration** — `3d77d65` (docs)

**Plan metadata:** summary commit (this file)

## TDD RED evidence (trimmed)

```
FAILED tests/test_docs.py::test_rule_documents_carry_no_truncation_banner
AssertionError: .claude/architecture.md: truncation banner fragment '[Showing lines'

FAILED tests/test_docs.py::test_architecture_records_phase_15_8_mechanisms
AssertionError: missing load-bearing phrase: a second text-level scan covers
```

(Four prior tests passed; two new tests failed before the splice.)

## Verify results

- `uv run pytest tests/test_docs.py -q --no-cov` → 6 passed
- Byte-exact restoration bash check → exit 0
- Pre-commit test-count guard on `tests/test_docs.py` → exit 0
- `make validate && make test` → pass (3870 passed, 4 skipped; coverage 95.29%)
- `wc -l .claude/architecture.md` → **1024**
- `git diff --stat` (Task 1 commit): `.claude/architecture.md | 144 +++++…`, `tests/test_docs.py | 69 +++++…`
- `git diff 22e6c5e HEAD -- .claude/architecture.md` → **one hunk** near line 220 (Phase 18 authoring)
- `grep -c 'this project does NOT parse shell'` → 1; `grep -c 'smoke_argv'` → 1

## Documents audit (`git diff --numstat 22e6c5e HEAD`)

Rule docs vs `22e6c5e` (intended Phase 18 edits elsewhere; architecture net change is +20/-4 with single hunk vs base, not the prior +11/-141 truncation):

```
20	4	.claude/architecture.md
2	2	.claude/dev-environment.md
13	6	.claude/skills/tool-onboarding/SKILL.md
2	1	AGENTS.md
7	1	README.md
1	1	docs/TROUBLESHOOTING.md
```

Only `.claude/architecture.md` had the unintended mass deletion (CR-01); that loss is restored in `3d77d65`.

## Deviations from Plan

None — splice, tests, and verify commands followed the plan.

## Issues Encountered

None.

## Final review

Self-review only (no subagent tool in this Pi session): diff matches plan contract; guards exercised on RED then GREEN.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
