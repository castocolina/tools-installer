---
gsd_state_version: "1.0"
milestone: v0.51.0
milestone_name: Onboard terminal tools
current_phase: 28
current_phase_name: Shared terminal-keys mechanism
status: executing
stopped_at: Completed 28-04-PLAN.md
last_updated: "2026-11-20T13:26:43.509Z"
last_activity: 2026-11-20
last_activity_desc: Phase 28 execution started
state_head: 2899d560e1f46c4a8ddf1de893a0264fa636aa9c
progress:
  total_phases: 9
  completed_phases: 0
  total_plans: 8
  completed_plans: 7
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-16)

**Core value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required, and every screen tells the truth about what is on the host.
**Current focus:** Phase 28 — Shared terminal-keys mechanism

## Current Position

Phase: 28 (Shared terminal-keys mechanism) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-11-20 — Phase 28 execution started

Progress: [░░░░░░░░░░] 0%


## Performance Metrics

**Velocity:**

- Total plans completed (v0.50.0): 0
- Previous milestone v0.49.0: 110 plans across 28 phases
- Average duration: -

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 20 | 31 | - | - |
| 23.1 | 18 | - | - |
| 23.2 | 8 | - | - |
| 24 | 9 | - | - |
| 24.1 | 5 | - | - |
| 24.2 | 13 | - | - |
| 24.3 | 11 | - | - |
| 24.4 | 7 | - | - |
| 24.5 | 9 | - | - |
| 22 | 13 | - | - |
| 18 | 28 | - | - |
| 23 | 16 | - | - |
| 19 | 46 | - | - |
| 21 | 21 | - | - |
| 17 | 21 | - | - |
| 25 | 11 | - | - |
| 26 | 9 | - | - |

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 27 P01 | 8min | 3 tasks | 3 files |
| Phase 27 P02 | 14min | 2 tasks | 3 files |
| Phase 27 P03 | 14min | 3 tasks | 2 files |
| Phase 27 P04 | 8min | 3 tasks | 8 files |
| Phase 28 P01 | 9min | 2 tasks | 4 files |
| Phase 28 P02 | 13min | 2 tasks | 7 files |
| Phase 28 P04 | 10min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. The full v0.49.0 decision log, metrics and roadmap evolution are archived in `.planning/milestones/v0.49.0-STATE.md`.
Recent decisions affecting current work:

- [v0.50.0, 2026-10-13]: Built from the ponytail-ultra target architecture (`.planning/research/2026-10-13-target-architecture.md`); phases 17–25 = TA §8 P1–P9
- [O1, 2026-10-13]: Native package installs are handed off as the exact command; no executor runs sudo
- [O5, 2026-10-13]: Alacritty on Bazzite is a cargo build in a throwaway Distrobox (overrides the TA's "stay unavailable" recommendation and its no-new-kind cut); lands in Phase 24 on Phase 22's contract
- [Roadmap, 2026-10-13]: Receipts are the only removal proof (Phase 19 format and writer, Phase 22 removal); UI-04 "delete config too" moved from TA P5 to Phase 22, where `config_paths` exists
- [v0.51.0 Roadmap, 2026-11-16]: Owner order: skill refactor first (27), shared keys mechanism (28), existing terminals (29), new terminals (30 Ghostty; 31 iTerm2 + Herdr desktop app, split because both need a JSON file mode), other onboardings (32) in parallel with 28–31 once 27 lands
- [v0.51.0 owner decisions, 2026-11-16]: clear = screen and scrollback, Modifier+K sends Ctrl+L; no global Option-as-Alt; Konsole verify-only; iTerm2 profile becomes the default; Ghostty Linux = labelled community AppImage; AWS CLI official script first; Xcode CLT handoff only (full list in REQUIREMENTS.md)

### Pending Todos

- [2026-10-13] [tweaks] Point Playwright MCP at the Flatpak Chrome (shell tweak + Cursor MCP env) — [todo file](.planning/todos/pending/2026-10-13-playwright-mcp-flatpak-chrome.md)
- [2026-10-13] [pi] Repair pi's install leftovers and ship the pi model/MCP sync — [todo file](.planning/todos/pending/2026-10-13-repair-pi-install-and-sync-models.md)
- [2026-10-14] [catalog] Add xcode-clt catalog entry as macOS prerequisite — [todo file](.planning/todos/pending/2026-10-14-add-xcode-clt-catalog-entry-as-macos-prerequisite.md)
- [2026-10-14] [catalog] Port what is useful from ai-kit's shelved "context tools" wizard Step 0 — [todo file](.planning/todos/pending/2026-10-14-port-ai-kit-context-tools-step0.md) — Needs Read the tag from the ai-kit checkout (`git show.
- [2026-10-15] [catalog] Adopt Apple Containers runtime; colima stays compose path — [todo file](.planning/todos/pending/2026-10-15-adopt-apple-containers-runtime-colima-stays-compose-path.md)
- [2026-10-15] [catalog] Onboard Bruno API client via the tool-onboarding skill (nice to have) — [todo file](.planning/todos/pending/2026-10-15-onboard-bruno-api-client-via-the-tool-onboarding-skill.md)
- [2026-10-22] [catalog] Onboard AWS CLI through the tool-onboarding skill — [todo file](.planning/todos/pending/2026-10-21-onboard-aws-cli-through-the-tool-onboarding-skill.md)
- [2026-10-21] [tweaks] Rename container shortcuts and detect the available engine — [todo file](.planning/todos/pending/2026-10-21-rename-container-shortcuts-and-detect-the-available-engine.md)
- [2026-10-21] [catalog] Research memory-efficient Compose on Apple Silicon — [todo file](.planning/todos/pending/2026-10-21-research-memory-efficient-compose-on-apple-silicon.md)
- [2026-11-03] [catalog] Add the gh-stack extension through the tool-onboarding skill — [todo file](.planning/todos/pending/2026-11-03-add-the-gh-stack-extension-through-the-tool-onboarding-skill.md)
- [2026-11-04] [lifecycle] Hand off casks whose uninstall needs root instead of running brew uninstall --cask — [todo file](.planning/todos/pending/2026-11-04-hand-off-casks-whose-uninstall-needs-root.md)
- [2026-11-07] [general] Untitled — [todo file](.planning/todos/pending/2026-11-07-strip-fnm-vendor-shell-blocks-left-on-existing-hosts.md)
- [2026-11-08] [general] Untitled — [todo file](.planning/todos/pending/2026-11-08-retry-transient-tls-errors-in-network-installs.md) — Needs Retry a download or script fetch a small bounded number of times with backoff, only for curl's.
- [2026-11-08] [general] Untitled — [todo file](.planning/todos/pending/2026-11-08-small-23-2-follow-ups.md) — Needs Fix the skill text with a skill-judge re-score; look at the summary block layout at 80x20; check claude's.
- [2026-11-13] [general] Untitled — [todo file](.planning/todos/pending/2026-11-13-phase-24-review-deferrals.md)
- [2026-11-14] [catalog] Replace codegraph with codebase-memory-mcp as the code-and-doc exploration tool — [todo file](.planning/todos/pending/2026-11-14-replace-codegraph-with-codebase-memory-mcp.md)
- [2026-11-16] [tooling] Adopt the branch → green CI → main flow in the outside tools that push to main — [todo file](.planning/todos/pending/2026-11-16-adopt-the-branch-ci-main-flow-in-outside-tools.md)
- [2026-11-16] [tui] Keep the Execute run log's newest line visible after the window shrinks — [todo file](.planning/todos/pending/2026-11-16-keep-the-run-log-tail-visible-after-a-shrink.md)
- [2026-11-16] [catalog] Terminal defaults for herdr (multiplexer): check the word-navigation and clear keys pass through — [todo file](.planning/todos/pending/2026-11-16-terminal-defaults-for-herdr.md)
- [2026-11-16] [catalog] Terminal defaults for kitty: clear-screen shortcut and macOS Option word navigation — [todo file](.planning/todos/pending/2026-11-16-terminal-defaults-for-kitty.md)
- [2026-11-16] [catalog] Terminal defaults for Konsole: Ctrl+Shift+K clear-screen shortcut (owner decision) — [todo file](.planning/todos/pending/2026-11-16-terminal-defaults-for-konsole.md)
- [2026-11-16] [catalog] Terminal defaults for WezTerm: clear-screen shortcut and macOS Option word navigation — [todo file](.planning/todos/pending/2026-11-16-terminal-defaults-for-wezterm.md)
- [2026-11-16] [testing] Transient test ERRORs under xdist in the push gate — [todo file](.planning/todos/pending/2026-11-16-transient-test-errors-under-xdist-in-the-push-gate.md)
- [2026-11-17] [schedules] Daily update check with a desktop notification (Bazzite and macOS) — [todo file](.planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md)
- [2026-11-17] [schedules] Opt-in auto-update schedule: package managers first, then dependents — [todo file](.planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md)
- [2026-11-17] [ci] Registry update bot in GitHub Actions (catalog pins, Dependabot-like) — [todo file](.planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md)

### Roadmap Evolution

- Phase 26 added: Commit and push quality hooks (user request 2026-10-15; runs last in the v0.50.0 autonomous run)
- Phase 23.1 inserted after Phase 23: Host safety: drop 8 skill-pack entries, sandboxed tests, container-only e2e (global GSD root cause)
- Phase 23.2 inserted after Phase 23: Install-time tuning instead of Policies knobs; live progress indicator
- Phase 24.2 inserted after Phase 24: Schedules view: cache cleanup, agent-CLI updates, cursor-agent shim
- Phase 24.3 inserted after Phase 24: Catalog audit skill; opencode v2 and Pi MCP

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| todos | 2026-10-13-playwright-mcp-flatpak-chrome.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-13-repair-pi-install-and-sync-models.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-14-add-xcode-clt-catalog-entry-as-macos-prerequisite.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-14-port-ai-kit-context-tools-step0.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-15-add-iterm2-macos-only-entry-after-tool-onboarding-refactor.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-15-adopt-apple-containers-runtime-colima-stays-compose-path.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-15-onboard-bruno-api-client-via-the-tool-onboarding-skill.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-21-onboard-aws-cli-through-the-tool-onboarding-skill.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-21-rename-container-shortcuts-and-detect-the-available-engine.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-10-21-research-memory-efficient-compose-on-apple-silicon.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-03-add-the-gh-stack-extension-through-the-tool-onboarding-skill.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-04-hand-off-casks-whose-uninstall-needs-root.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-07-strip-fnm-vendor-shell-blocks-left-on-existing-hosts.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-08-retry-transient-tls-errors-in-network-installs.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-08-small-23-2-follow-ups.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-13-phase-24-review-deferrals.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-14-replace-codegraph-with-codebase-memory-mcp.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-16-adopt-the-branch-ci-main-flow-in-outside-tools.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-16-keep-the-run-log-tail-visible-after-a-shrink.md | (presence-only) | 2026-11-16 | v0.50.0 |
| todos | 2026-11-16-transient-test-errors-under-xdist-in-the-push-gate.md | (presence-only) | 2026-11-16 | v0.50.0 |
| verification | 15 stale phase verifications (override closeout) | acknowledged | 2026-10-13 | v0.49.0 |
| uat | 15.1-UAT.md open items | acknowledged | 2026-10-13 | v0.49.0 |
| todo | detect dangling pnpm global bin shims in doctor | carried to v0.50.0 (Phase 21) | 2026-10-13 | v0.49.0 |
| requirement | REQ-manager-drift-alerting | dropped in v0.50.0 (off-policy note covers it) | 2026-10-13 | v0.49.0 |

### Roadmap Evolution

- 2026-11-19: Phases 33–35 added to v0.51.0 by /gsd-ingest-docs (registry bot, daily update check, opt-in auto-update; 18 requirements BOT/NOTIFY/AUTOUPD; 24.2 notification cut and SCHED-01 amended, owner-approved)
- 2026-11-16: v0.51.0 roadmap created — Phases 27–32; backlog 999.18 → 27, 999.19 → 29, 999.20 → 30, 999.21 and 999.22 → 31
- 2026-10-13: v0.50.0 roadmap created — Phases 17–25; backlog 999.1–999.11 kept, each marked with the phase(s) that absorb it

## Session Continuity

Last session: 2026-11-20T13:26:43.443Z
Stopped at: Completed 28-04-PLAN.md
Resume file: None

## Deferred Verification

| Phase | State | Resume |
|-------|-------|--------|
| 17 | verification_deferred_human (only CI-02 branch protection, a user action; main pushed e412b03, CI run 38710819886 green on both OSes) | /gsd-verify-work 17 |
| 18 | verification_deferred_human (only the real-Mac draw.io pinned-app install + smoke; UAT 18/19 pass, 1 skipped; SECURITY 99/99 closed; CI run 38839041957 green on both OSes; first verify-registry run 38839643252 exit 0, cache saved) | /gsd-verify-work 18 |
| 19 | verification_deferred_human (only host adoption on the real machine; UAT 11/12 pass, 1 skipped; make e2e on d49e7b2 rc 0 (PASS1 74/0/8, receipt tracers OK, REINSTALL 47); tmux 80x20 NO_COLOR check pass; SECURITY 139/139 closed; CI run 39019413698 green on both OSes) | /gsd-verify-work 19 |
| 27 | verification_deferred_human (only the real-Mac check of the macOS rules, SKILL-05; verifier 7/7 must-haves, Nyquist 0 gaps, SECURITY 15/15 closed, deep code review fixed 10 of 16 and ledgered the rest, skill-judge 69.6% before and 73.6% after, full suite 7,872 passed on the final tree; macOS deferred by the owner's standing rule) | /gsd-verify-work 27 |

## Operator Next Steps


- Plan Phase 27 with /gsd-plan-phase 27 (Phase 32 may be planned in parallel once 27 lands)
