---
gsd_state_version: "1.0"
milestone: v0.50.0
milestone_name: Truthful lifecycle
current_phase: 17
current_phase_name: milestone v0.50.0, phases 17–25
status: planning
stopped_at: Phase 24 context gathered (assumptions mode)
last_updated: "2026-10-14T11:28:33.650Z"
last_activity: 2026-10-13
last_activity_desc: Roadmap for v0.50.0 created (9 phases, 72/72 requirements mapped)
state_head: 48b0932f3a5a739a24e8c2e84309e183d4d0068b
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-13)

**Core value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.
**Current focus:** Phase 17 — Stop the bleeding (milestone v0.50.0 Truthful lifecycle)

## Current Position

Phase: 17 of 25 (Stop the bleeding) — milestone v0.50.0, phases 17–25
Plan: Not started
Status: Ready to plan
Last activity: 2026-10-13 — Roadmap for v0.50.0 created (9 phases, 72/72 requirements mapped)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed (v0.50.0): 0
- Previous milestone v0.49.0: 110 plans across 28 phases
- Average duration: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. The full v0.49.0 decision log, metrics and roadmap evolution are archived in `.planning/milestones/v0.49.0-STATE.md`.
Recent decisions affecting current work:

- [v0.50.0, 2026-10-13]: Built from the ponytail-ultra target architecture (`.planning/research/2026-10-13-target-architecture.md`); phases 17–25 = TA §8 P1–P9
- [O1, 2026-10-13]: Native package installs are handed off as the exact command; no executor runs sudo
- [O5, 2026-10-13]: Alacritty on Bazzite is a cargo build in a throwaway Distrobox (overrides the TA's "stay unavailable" recommendation and its no-new-kind cut); lands in Phase 24 on Phase 22's contract
- [Roadmap, 2026-10-13]: Receipts are the only removal proof (Phase 19 format and writer, Phase 22 removal); UI-04 "delete config too" moved from TA P5 to Phase 22, where `config_paths` exists

### Pending Todos

- [2026-09-16] doctor — Detect dangling pnpm global bin shims in Doctor — [todo](todos/pending/2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md) — closes with Phase 21 (UI-07)

### Blockers/Concerns

- [Host hazard] Until Phase 17 lands, `make uninstall --yes` can delete foreign `~/.local/bin` files, and reinstalling Sublime further damages `~/.local/opt/subl` — do not run either
- [Phase 17] CI-02 (branch protection requiring the PR check) is a user action on GitHub
- [Phase 17] O14: graphify switches to the global form only if the HOME-sandbox probe proves the cwd untouched; otherwise its `postinstall` is removed
- [Phase 23/24] Not verified yet: whether `herdr integration install` edits an agent's main config (merge-safety check before shipping)
- [Phase 24] Phase 18 is not in Phase 24's dependency chain; herdr's registry entry must still pass Phase 18's `# Verified` and unknown-key checks, so finish Phase 18 before Phase 24

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| verification | 15 stale phase verifications (override closeout) | acknowledged | 2026-10-13 | v0.49.0 |
| uat | 15.1-UAT.md open items | acknowledged | 2026-10-13 | v0.49.0 |
| todo | detect dangling pnpm global bin shims in doctor | carried to v0.50.0 (Phase 21) | 2026-10-13 | v0.49.0 |
| requirement | REQ-manager-drift-alerting | dropped in v0.50.0 (off-policy note covers it) | 2026-10-13 | v0.49.0 |

### Roadmap Evolution

- 2026-10-13: v0.50.0 roadmap created — Phases 17–25; backlog 999.1–999.11 kept, each marked with the phase(s) that absorb it

## Session Continuity

Last session: 2026-10-14T11:28:33.636Z
Stopped at: Phase 24 context gathered (assumptions mode)
Resume file: .planning/phases/24-onboarding-through-the-skill-and-e2e/24-CONTEXT.md

## Deferred Verification

| Phase | State | Resume |
|-------|-------|--------|
| *(none; phase 16 UAT closed 2026-10-13)* | | |

## Operator Next Steps

- Discuss the first phase with /gsd-discuss-phase 17
