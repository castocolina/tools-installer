---
gsd_state_version: "1.0"
milestone: v0.51.0
milestone_name: Onboard terminal tools
current_phase: 35
current_phase_name: Opt-in auto-update
status: verifying
stopped_at: Phases 27-35 executed; UAT and owner decisions pending (milestone audit 2026-11-23)
last_updated: "2026-11-20T13:42:35.352Z"
last_activity: 2026-11-23
last_activity_desc: Completed quick task 261123-f27: macOS terminal debt and tool-onboarding skill lift
state_head: ce04ce72b7119f8c9149a35c8b9a75635709c86f
progress:
  total_phases: 9
  completed_phases: 0
  total_plans: 8
  completed_plans: 8
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-11-16)

**Core value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required, and every screen tells the truth about what is on the host.
**Current focus:** Milestone v0.51.0: phases 27-35 are executed and every phase is human_needed; the work left is UAT on the owner's Mac and Bazzite, the owner-decision items and backlog 999.37-999.39 (see .planning/v0.51.0-MILESTONE-AUDIT.md)

## Current Position

Phase: 35 (Opt-in auto-update) — executed, needs review; phases 27-34 executed and human_needed
Status: Awaiting UAT and owner decisions
Last activity: 2026-11-23 — Completed quick task 261123-f27

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
| Phase 28 P03 | 14min | 2 tasks | 3 files |

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

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 261123-f27 | Close the v0.51.0 macOS terminal debt (iTerm2 Cmd+K row, gone-cask INSTALLED, WezTerm shadowed chord, quarantine docstring) and lift the tool-onboarding skill to 80%+ | 2026-11-23 | d6ab210c | Needs Review | [261123-f27-close-v0-51-0-macos-terminal-debt-drop-t](./quick/261123-f27-close-v0-51-0-macos-terminal-debt-drop-t/) |

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

Last session: 2026-11-20T13:42:35.281Z
Stopped at: Completed 28-03-PLAN.md
Resume file: None

## Deferred Verification

| Phase | State | Resume |
|-------|-------|--------|
| 17 | verification_deferred_human (only CI-02 branch protection, a user action; main pushed e412b03, CI run 38710819886 green on both OSes) | /gsd-verify-work 17 |
| 18 | verification_deferred_human (only the real-Mac draw.io pinned-app install + smoke; UAT 18/19 pass, 1 skipped; SECURITY 99/99 closed; CI run 38839041957 green on both OSes; first verify-registry run 38839643252 exit 0, cache saved) | /gsd-verify-work 18 |
| 19 | verification_deferred_human (only host adoption on the real machine; UAT 11/12 pass, 1 skipped; make e2e on d49e7b2 rc 0 (PASS1 74/0/8, receipt tracers OK, REINSTALL 47); tmux 80x20 NO_COLOR check pass; SECURITY 139/139 closed; CI run 39019413698 green on both OSes) | /gsd-verify-work 19 |
| 27 | verification_deferred_human (only the real-Mac check of the macOS rules, SKILL-05; verifier 7/7 must-haves, Nyquist 0 gaps, SECURITY 15/15 closed, deep code review fixed 10 of 16 and ledgered the rest, skill-judge 69.6% before and 73.6% after, full suite 7,872 passed on the final tree; macOS deferred by the owner's standing rule) | /gsd-verify-work 27 |
| 28 | verification_deferred_human (only the real-Mac redraw of the zsh Ctrl+L clear and the owner's confirmation of three provisional decisions: 28 D-06 with OQ1, the amended SPEC R3 round-trip wording, the D-12 import-line deviation; verifier 4/4 must-haves, Nyquist 0 gaps, SECURITY 16/16 closed, deep code review fixed both warnings and ledgered the rest, full suite 7,924 passed on the final tree) | /gsd-verify-work 28 |
| 29 | verification_deferred_human (only the real-Mac checks of the kitty and WezTerm rules, the cask install on a Mac and a live Konsole 26.x capture, plus the owner's confirmation of the provisional decisions 28 D-06 and 29 D-09; verifier 4/4 truths, Nyquist 5/5 requirements covered, SECURITY 25/25 closed, deep code review plus the referee-one lane fixed in six commits and ledgered the rest, herdr-keys container check PASS, WezTerm D-07 cwd check PASS, full suite 8,059 passed on the final tree) | /gsd-verify-work 29 |
| 30 | verification_deferred_human (only the real-Mac checks of the cask install and the Ghostty keys, the Bazzite-host checks (host FUSE mount, KDE menu entry and TERMINFO, probe timing) and the owner's confirmation of the provisional decisions 30 D-03, D-08, D-10, D-17, the SPEC R4 amendment following 28 D-06 and the narrowings of 30 D-08, D-17, D-18; verifier 8/8 truths, Nyquist 14 of 15 rows covered (the FUSE mount stays UAT), SECURITY 19/19 closed, deep code review plus the referee-one lane fixed in six items and ledgered the rest, ghostty container check PASS with FUSE unproven (extract-and-run proven), full suite 8,274 passed on the final tree) | /gsd-verify-work 30 |
| 31 | verification_deferred_human (only the real-Mac checks of iTerm2 (profile load, default profile, Cmd+K, Option word moves, colors, Recycle, uninstall restore including from inside iTerm2) and of the herdr app cask, the Linux desktop run of the herdr app, and the owner's confirmation of the provisional decisions 31 D-08, D-12, the CONTEXT amendments D-07, D-09, D-11, D-16, the keys.json edge cases and the accepted limits; verifier 6/6 truths, Nyquist 23 of 25 rows covered (the concurrency backstop and the manual rows remain), SECURITY 21/21 closed, deep code review plus the referee-one lane fixed in six items and ledgered the rest, herdr-app container check PASS (transcript-bound), full suite 8,639 passed on the final tree) | /gsd-verify-work 31 |
| 32 | verification_deferred_human (only the real-Mac checks of Xcode CLT, the AWS script or brew fallback, the Bruno cask and gh-stack's data directory, the macOS agent-host MCP files, the Bazzite checks (the Bruno AppImage launch: the container check is UNPROVEN, no FUSE in rootless podman; Playwright with real Flatpak Chrome), each agent host's own load of the playwright server, the Claude plugin key spelling and Pi's manual step, plus the owner's confirmation of the provisional decisions: 32 D-01, D-03 (tool-level unzip dropped), D-04, D-08, D-09, D-10, D-11, D-12, D-13, D-14, D-15 (consent route: install-time hand-off plus the confirmed Reconfigure step bound to the disclosed hosts), the OpenCode v1/v2 rule, the Codex whole-server rule (WR-03), no silent re-add of a deleted server (WR-04), the cask-sudo console limit and the accepted limits; verifier 5/5 criteria, Nyquist 25/25 rows plus 3 orchestrator rows (the concurrency backstop and the manual rows remain), SECURITY 32/32 closed, deep code review plus the referee-one lane fixed in 11 items and ledgered the rest, real container checks: aws-cli PASS and playwright-mcp PASS (transcript-bound), bruno UNPROVEN (reported), full suite 9,082 passed on the final tree) | /gsd-verify-work 32 |
| 33 | verification_deferred_human (only what needs the owner after landing the branch on main, because a workflow file must exist on the default branch to be dispatched: the one-time proof following docs/registry-bot-proof.txt (BOT-01 live behavior; BOT-02: do dispatched check runs satisfy the classic protection of main for a fast-forward; Option A needs the owner's approval of a temporary protection write on a throwaway branch), the closing keyword on a fast-forward, the first real bot run (draw.io 32.6.10 to 32.7.4), the follow-up commit that enables the cron, the push restriction on main as an owner follow-up, landing a Dependabot branch; plus the owner's confirmation of the provisional decisions: 33 D-05, D-06, D-09, D-12, D-13, D-15, D-16, D-17, the amended D-10, the runbook as a plain-text file, the skip-if-identical rerun, the verified date of a bumped tool, the accepted dispatch boundary and orchestrator decisions 1 to 10; verifier 4/4 criteria, Nyquist 13/13 rows plus the manual rows, SECURITY 17/17 closed, deep code review plus the referee-one lane fixed in about 20 items (one a real raw-AppImage bump defect of the verifier), actionlint clean before and after the fixes, full suite 9,142 passed on the final tree) | /gsd-verify-work 33 |
| 34 | verification_deferred_human (only what needs real hosts and sessions: a real notification on the Bazzite desktop and the session bus address reaching notify-send from a systemd user unit, a real-Mac osascript notification with its Script Editor permission (and a silently dropped one), the daily timer firing on both OSes with the login catch-up lateness, the self-check on a real shallow clone, plus the owner's confirmation of the provisional decisions: the eighth Schedules row and table height 9, the osascript argv without --, the bus address passed to the check child only, the self-update skip rules (detached HEAD, non-main, non-root, partial clone), a shrinking non-empty set notifying again, the daily limit as the timer cadence with the SPEC and ROADMAP amendments, proxy values carried as for every row, uv and manager scratch writes accepted, the confirmed-only membership rule with per-manager stamps, brew under-reporting and the accepted limits; verifier 5/5 criteria, Nyquist 18/18 rows plus the manual rows, SECURITY 23/23 closed, deep code review plus the referee-one lane fixed in about 25 items (real defects: a failing manager hiding another's updates, a tag named main hiding the behind clause, recursion on nested JSON, a cache writer that saved an unreadable file), the real schedules container check PASS twice, full suite 9,410 passed on the final tree) | /gsd-verify-work 34 |
| 35 | verification_deferred_human (only what needs real hosts and sessions: a real macOS run of the nightly row, the real Bazzite first night with the 03:00 timer under systemd and the real outdated set, a real desktop notification from the unit, the effect of `uv self update` on a real user's shell rc files, plus the owner's confirmation of the provisional decisions: 03:00 daily, managers by Owner value with cask mapped to brew, the eight script tools without an update argv skipped by the generic rule, recency windows (6 h manager, 20 h others) instead of fresh-this-pass, run_guarded, the kernel-lock verified parent handoff with its same-user residual, the per-command process group and stop budget, plan mode through hold_writes, notify only when updated plus failed is above zero, the `$PNPM_HOME/bin` scheduled PATH, `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK`, the pnpm replay and grouped-package limit, the SPEC, ROADMAP and REQUIREMENTS amendments, and the backlog 999.36 deferrals incl. the 80x20 detail pane UI decision; verifier 5/5 criteria and 7/7 truths, Nyquist 19 of 20 rows green (the dated doc amendments not test-pinned), SECURITY 21/21 closed or accepted, deep review plus the referee-one lane fixed in about 20 items (real defects: a second signal aborting the group kill, descendants outliving the lock, an unknown-owner manager authorizing dependents, a pnpm replay failure reported as success, a scheduled PATH missing the standalone pnpm directory), the real `update-all` container check PASS twice: uv 0.11.0 replaced itself with 0.13.9 through the real uv run chain and ruff 0.1.0 updated to 0.17.6) | /gsd-verify-work 35 |

## Operator Next Steps


- Plan Phase 27 with /gsd-plan-phase 27 (Phase 32 may be planned in parallel once 27 lands)
