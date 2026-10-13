---
phase: 12-version-aware-status-update-action
plan: 04
subsystem: docs
tags: [deferral, architecture, ownership, drift-alerting, guard-tests]

# Dependency graph
requires:
  - phase: 12-version-aware-status-update-action
    provides: "Ownership resolution, version cache, update-safe executors, and the Catalog u action (Plans 12-01 through 12-03)"
provides:
  - "REQ-manager-drift-alerting recorded as deferred in REQUIREMENTS.md, ROADMAP.md SC#5, and PROJECT.md with three structural reasons"
  - "Phase 12 mechanisms consolidated into .claude/architecture.md (preference vs provenance, evidence rule, update-safe executors, capture-before-update, epoch-invalidated manager cache)"
  - "Guard tests pinning the abandoned drift helpers as absent and the architecture section's load-bearing phrases as present"
affects: [phase-12-verification]

# Actuals (#2632)
actuals:
  tokens: 2200
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A stretch requirement whose data source cannot observe the target condition is recorded as deferred, with independently-checkable reasons, rather than shipped as a zero-caller helper."
    - "A Phase 12 disposition guard names the two abandoned identifiers specifically and does not ban the substring drift, so a future correctly-wired implementation is recorded as absent rather than forbidden."
    - "The comment is the mechanism; a substring test keeps a load-bearing architecture paragraph from rotting away unnoticed."

key-files:
  created:
    - tests/test_docs.py
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/PROJECT.md
    - .claude/architecture.md
    - tests/test_ownership.py

key-decisions:
  - "REQ-manager-drift-alerting is deferred, not implemented. brew outdated lists only already-installed formulae and casks; zero registry rows declare both a node/uv-tool method and a brew/cask method; an unwired helper would violate architecture rule 5. 12-CONTEXT.md D-02's planner's-call clause authorized the deferral."
  - "The drift-helper guard asserts only has_declared_manager_drift and manager_drift_alert are absent from installer.manager_versions and installer.ownership — not a substring ban on the word drift (12-REVIEWS.md:486-490)."
  - "architecture.md records the preference-versus-provenance distinction from the committed 12-01..12-03 code, not from the original false-premise plans."

patterns-established:
  - "End-of-phase decision consolidation writes the phase's load-bearing distinction into .claude/architecture.md and guards the phrases with a substring test, matching the Phase 7/8/9 precedent."
  - "A requirement this plan owns as a DISPOSITION, not a delivery, stays listed in requirements-completed so the milestone audit finds the recorded deferral rather than a silent miss."

requirements-completed:
  - REQ-manager-drift-alerting

coverage:
  - id: D1
    description: "REQ-manager-drift-alerting deferral is recorded, dated 2026-09-07, and discoverable from the requirement entry, the status-table row, ROADMAP Phase 12 SC#5, and PROJECT.md's Key Decisions table."
    requirement: REQ-manager-drift-alerting
    verification:
      - kind: other
        ref: "python -c status-table wording check on .planning/REQUIREMENTS.md"
        status: pass
      - kind: unit
        ref: tests/test_ownership.py#test_abandoned_drift_helpers_are_absent
        status: pass
    human_judgment: false
  - id: D2
    description: "A narrow guard test asserts has_declared_manager_drift and manager_drift_alert are absent from installer.manager_versions and installer.ownership, without banning the substring drift."
    requirement: REQ-manager-drift-alerting
    verification:
      - kind: unit
        ref: tests/test_ownership.py#test_abandoned_drift_helpers_are_absent
        status: pass
    human_judgment: false
  - id: D3
    description: "architecture.md Phase 12 section records preference-versus-provenance, the evidence rule, update-safe executors, the pnpm _node reuse, capture-before-update, the epoch-invalidated manager cache, the visible stale marker, the VIEWS-registered u action, and the dnf/apt/pacman/rpm_ostree exclusion."
    verification:
      - kind: unit
        ref: tests/test_docs.py#test_architecture_records_phase_12_mechanisms
        status: pass
    human_judgment: false
  - id: D4
    description: "tests/test_docs.py asserts the nine load-bearing substrings and names the missing one on failure."
    verification:
      - kind: unit
        ref: tests/test_docs.py#test_architecture_records_phase_12_mechanisms
        status: pass
    human_judgment: false

# Metrics
duration: 20 min
completed: 2026-09-07
status: complete
---

# Phase 12 Plan 04: Drift-Alerting Deferral and Decision Consolidation Summary

**REQ-manager-drift-alerting is recorded as deferred in every place a reader checks, with three independently-checkable reasons, and Phase 12's preference-versus-provenance distinction is written into `.claude/architecture.md` and guarded by a test — no drift helper was built.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-09-07T16:03:46Z
- **Completed:** 2026-09-07T16:13:13Z
- **Tasks:** 2/2
- **Files modified:** 6

## Accomplishments

- REQ-manager-drift-alerting's status-table row now reads `Deferred (not implemented in Phase 12 — see entry)`, with a dated 2026-09-07 amendment naming the three structural reasons, D-02's planner's-call authority, and what a future implementation would require.
- ROADMAP.md Phase 12 SC#5 carries an in-place bracketed amendment so an end-of-phase verifier reading the numbered criteria in isolation does not register a silent miss. PROJECT.md's Key Decisions table gained the matching row.
- `tests/test_ownership.py::test_abandoned_drift_helpers_are_absent` imports both modules and asserts the two abandoned helper names are unbound. It does not ban the substring `drift`.
- `.claude/architecture.md` gained a Phase 12 section written from the committed 12-01..12-03 code: install-preference is never provenance, ownership is asserted only on an active-path match or complete negative evidence, update is not install re-run, a pnpm-owned update reuses `_node`, the pnpm-globals snapshot is captured before the update, and `invalidate` drops the manager snapshot and bumps the epoch.
- `tests/test_docs.py` asserts the nine load-bearing phrases and names the missing one on failure.

## Task Commits

Each task was committed atomically:

1. **Task 1: Record the REQ-manager-drift-alerting deferral in every place a reader checks** - `c630d74` (docs)
2. **Task 2: Consolidate Phase 12's mechanisms into .claude/architecture.md** - `a8787b5` (docs)

**Plan metadata:** (this commit)

## Files Created/Modified

- `.planning/REQUIREMENTS.md` — dated amendment on REQ-manager-drift-alerting plus the status-table wording
- `.planning/ROADMAP.md` — Phase 12 SC#5 in-place amendment (Plans list already described the four plans as they stand after the replan)
- `.planning/PROJECT.md` — Key Decisions row for the deferral
- `tests/test_ownership.py` — narrow absent-helper guard
- `.claude/architecture.md` — Phase 12 section
- `tests/test_docs.py` — substring guard for the nine load-bearing phrases

## Decisions Made

- Deferral, not a zero-caller helper, because `brew outdated` cannot observe an uninstalled brew alternative, the registry has no qualifying row, and architecture rule 5 forbids shipping the helper unwired. Authorized by 12-CONTEXT.md D-02.
- The guard names the two abandoned identifiers only, answering cycle 2's LOW at 12-REVIEWS.md:486-490.
- The architecture section was written from the shipped code. Where the plan's behavior list and the committed modules disagreed, the modules won: `UpdateService.run` re-resolves at mutation time; `should_replay_node_globals` keys on `tool.id == "pnpm"`; manager reports share one `managers` snapshot with a hours-scale window.

## Deviations from Plan

None - plan executed exactly as written.

The ROADMAP.md Plans list already described all four plans as they stand after the replan, so Task 1's "update the Plans list" step was a no-op beyond confirming the 12-04 line already reads as the deferral-and-consolidation plan. SC#5 was the line that still needed the bracketed amendment.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 12's four plans are all executed. Ready for `/gsd-verify-work 12`. REQ-manager-drift-alerting must be read as deferred, with the rationale in `.planning/REQUIREMENTS.md` — it is not a silent miss against SC#5.

No `installer/` source file was modified by this plan (`git diff --stat` against 12-03 HEAD shows only planning docs, architecture.md, and the two test files).

## Self-Check: PASSED

- `tests/test_docs.py` exists on disk.
- `git log --oneline --all --grep="12-04"` returns the two task commits plus this metadata commit.
- Task 1 acceptance: REQUIREMENTS.md amendment dated 2026-09-07 with three structural reasons; status-table row matches; ROADMAP SC#5 amended in place; PROJECT.md Key Decisions row present; guard test names the two identifiers and does not ban `drift`; scoped edits only (25 insertions / 3 deletions across four files).
- Task 2 acceptance: architecture.md Phase 12 section covers preference-versus-provenance with the `rg` example, the evidence rule, why update is not install re-run, the rollback state machine, `_node` reuse, capture-before-update, the version/manager cache and epoch, the visible stale marker, VIEWS registration of `u`, and the Linux system-package-manager exclusion; one-line pointer to the REQUIREMENTS.md deferral; `test_docs.py` names the missing substring; scoped append.
- `uv run pytest -q` EXIT 0 (suite green, 1 skipped as before).
- `make validate` passed (ruff, pyright, bandit, vulture, shellcheck).

---
*Phase: 12-version-aware-status-update-action*
*Completed: 2026-09-07*
