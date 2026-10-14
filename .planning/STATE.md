---
gsd_state_version: "1.0"
milestone: v0.50.0
milestone_name: Truthful lifecycle
current_phase: 17
current_phase_name: Stop the bleeding
status: executing
stopped_at: Phase 25 context gathered (assumptions mode); phases 17-25 all have CONTEXT
last_updated: "2026-10-14T21:36:30.723Z"
last_activity: 2026-10-14
last_activity_desc: Phase 17 execution started
state_head: d78fdb1d6502024ca65204c663daad1744486738
progress:
  total_phases: 10
  completed_phases: 0
  total_plans: 13
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-10-13)

**Core value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.
**Current focus:** Phase 17 — Stop the bleeding

## Current Position

Phase: 17 (Stop the bleeding) — EXECUTING
Plan: 1 of 13
Status: Executing Phase 17
Last activity: 2026-10-14 — Phase 17 execution started

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
- [2026-09-16] [doctor] Detect dangling pnpm global bin shims in Doctor — [todo file](.planning/todos/pending/2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor.md)
- [2026-10-13] [tweaks] Point Playwright MCP at the Flatpak Chrome (shell tweak + Cursor MCP env) — [todo file](.planning/todos/pending/2026-10-13-playwright-mcp-flatpak-chrome.md)
- [2026-10-13] [pi] Repair pi's install leftovers and ship the pi model/MCP sync — [todo file](.planning/todos/pending/2026-10-13-repair-pi-install-and-sync-models.md)
- [2026-10-14] [catalog] Add xcode-clt catalog entry as macOS prerequisite — [todo file](.planning/todos/pending/2026-10-14-add-xcode-clt-catalog-entry-as-macos-prerequisite.md)
- [2026-10-14] [catalog] Port what is useful from ai-kit's shelved "context tools" wizard Step 0 — [todo file](.planning/todos/pending/2026-10-14-port-ai-kit-context-tools-step0.md) — Needs Read the tag from the ai-kit checkout (`git show.

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

Last session: 2026-10-14T11:55:49.111Z
Stopped at: Phase 25 context gathered (assumptions mode); phases 17-25 all have CONTEXT
Resume file: .planning/phases/25-lean/25-CONTEXT.md

## Deferred Verification

| Phase | State | Resume |
|-------|-------|--------|
| *(none; phase 16 UAT closed 2026-10-13)* | | |

## Operator Next Steps

- Discuss the first phase with /gsd-discuss-phase 17
