---
phase: 17-stop-the-bleeding
plan: "12"
subsystem: governance
tags: [security-audit, validation-map, phase-16, threat-register, docs-only]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: shipped plans 16-17/16-18/16-19 with their threats, tests, and commits
provides:
  - 16-SECURITY.md covers plans 16-17..16-19 (T-16-45..T-16-53, qualified T-16-49..51, AR-16-09/10, T-16-SC x19)
  - 16-VALIDATION.md covers tasks 16-17-01..06, 16-18-01..08, 16-19-01..04, every command re-run green
  - two dated audit-trail rows; threats_open 0, status verified retained
affects: [17-13, v0.49.0-milestone-audit]

actuals:
  tokens: 5700
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Evidence cited as file::symbol plus pytest node id, not line numbers, so rows survive later edits"

key-files:
  created: []
  modified:
    - .planning/milestones/v0.49.0-phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-SECURITY.md
    - .planning/milestones/v0.49.0-phases/16-detection-version-and-ownership-must-answer-is-it-on-this-di/16-VALIDATION.md

key-decisions:
  - "Colliding T-16-49..T-16-51 kept as six qualified rows plus a one-line collision note under the register (D-18)"
  - "T-16-47 and T-16-53 recorded accept via new AR-16-09 and AR-16-10; T-16-SC widened to plans 16-01..16-19 after an empty git show --stat check on all 17 gap-plan commits"
  - "Gate-run rows (16-17-06, 16-18-08, 16-19-04) each record an actual make test run on this tree (3467 passed, 4 skipped; coverage 95.87%)"

patterns-established:
  - "Re-audit rows cite installer/<file>::<symbol> and tests/<file>::<test>, never line numbers"

requirements-completed: [CI-03]

coverage:
  - id: D1
    description: "16-SECURITY.md carries one row per 16-17..16-19 threat with code+test evidence and a closed/open status"
    requirement: CI-03
    verification:
      - kind: other
        ref: "bash: grep -F for T-16-45..T-16-48, the six qualified IDs, T-16-52, T-16-53, AR-16-09, AR-16-10, T-16-SC (x19)"
        status: pass
    human_judgment: false
  - id: D2
    description: "16-VALIDATION.md carries map rows 16-17-01..06, 16-18-01..08, 16-19-01..04, each command re-run green on this tree"
    requirement: CI-03
    verification:
      - kind: other
        ref: "bash: plan verify loops re-running every recorded uv run pytest command (all exit 0)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both files carry dated audit-trail entries and are committed; no production code or tests touched"
    requirement: CI-03
    verification:
      - kind: other
        ref: "git show --stat 918877b b4a238c (only the two milestone documents)"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 12: Phase 16 gap-plan re-audit Summary

**16-SECURITY.md and 16-VALIDATION.md now cover the post-audit gap plans 16-17..16-19 with evidence-based rows whose every command was re-run green, keeping the colliding T-16-49..51 IDs apart by plan qualifier.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2
- **Files modified:** 2 (milestone documents only)

## Accomplishments
- 16-SECURITY.md: rows T-16-45..T-16-48 (16-17), T-16-49 (16-18)..T-16-53, T-16-49 (16-19)..T-16-51 (16-19); every closed row cites `installer/<file>::<symbol>` plus a pytest node id; AR-16-09 and AR-16-10 added; T-16-SC widened to x19; footer 75; two audit-trail rows dated 2026-10-14; `threats_open: 0`.
- 16-VALIDATION.md: 18 new map rows (16-17-01..06, 16-18-01..08, 16-19-01..04); every recorded command re-run green during this plan; `audited: "2026-10-14"`; re-audit paragraph naming the date, the plans and the command count.
- No production code or test files touched.

## TDD evidence

This plan contains no `tdd="true"` tasks (docs-only audit); no RED run applies. The read-only rule was verified instead: `git show --stat` on both commits lists only the two milestone documents.

## Task Commits

1. **Task 1: re-audit plan 16-17 in both records** - `918877b` (docs(16))
2. **Task 2: re-audit plans 16-18 and 16-19, collisions kept apart** - `b4a238c` (docs(16))

## Verify-command results

- Task 1 verify: all `| 16-17-0N |` rows present, no 16-17-07, every recorded command re-ran exit 0; T-16-45..T-16-48 and AR-16-09 present.
- Task 2 verify: all twelve `16-18-*`/`16-19-*` rows present, no 16-18-09/16-19-05, every recorded command re-ran exit 0; all six qualified IDs, T-16-52, T-16-53, AR-16-10 and `T-16-SC (x19)` present; `threats_open: 0` / `status: verified` retained.
- SC check: `git show --stat --format= <sha> -- pyproject.toml uv.lock` empty for all 17 commits of 16-17/16-18/16-19.
- Plan-level: `make validate` exit 0; `make test` exit 0 (`3467 passed, 4 skipped`, coverage 95.87%, floor 90%).

## Decisions Made
- Evidence cited as `file::symbol` + node id per the plan, located via `codegraph explore` (rcclean, shellrc, locations, skill_lifecycle, model, ownership, catalog_tui, wizard_app, guidance).
- The 16-18-07 comment-only registry row is verified by the registry load tests, per the plan action.

## Deviations from Plan

### Auto-fixed Issues

**1. [smallest deviation] Gate-run rows 16-18-08 and 16-19-04 record two separate runs but 16-19-04's status is from the same session**
- **Found during:** Task 2
- **Issue:** Both gate rows demand a `make test` run; running the identical command twice back-to-back on an unchanged tree adds no information.
- **Fix:** Ran `make test` once per gate row anyway (runs A and B, both green) so each row's status is literally from its own run.
- **Verification:** outputs `3467 passed, 4 skipped` twice.
- **Committed in:** `b4a238c` (no extra commit needed)

---

**Total deviations:** 0 substantive (1 procedural note above)
**Impact on plan:** None.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 17-13 can re-run every `uv run pytest` command recorded in the 16-17..16-19 map rows on the final tree; all commands are recorded verbatim and currently green.
- SPEC R13 acceptance met: both files exist with entries for 16-17..19 and are committed.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
