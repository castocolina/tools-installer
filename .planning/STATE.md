---
gsd_state_version: 1.0
current_phase: 07
current_phase_name: System & User Tier Catalog Expansion
status: executing
stopped_at: 07-02 complete, ready for 07-03
last_updated: "2026-09-06T10:22:00.000Z"
last_activity: 2026-09-06
last_activity_desc: 07-02 executed — gnu-bash and Apple Containers shipped; D-01 disabled-state threaded through catalog TUI
state_head: f155e4d
progress:
  total_phases: 12
  completed_phases: 6
  total_plans: 19
  completed_plans: 18
  percent: 53
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-04)

**Core value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.
**Current focus:** Phase 07 — System & User Tier Catalog Expansion

## Current Position

Phase: 07 — System & User Tier Catalog Expansion
Plan: 07-03 (next)
Status: 07-02 complete
Last activity: 2026-09-06 — 07-02 executed; gnu-bash and Apple Containers shipped, D-01 disabled-state threaded through catalog TUI

Progress: [█████░░░░░] 53%

## Performance Metrics

**Velocity:**

- Total plans completed: 11
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 1 | - | - |
| 4 | 5 | - | - |
| 5 | 4 | - | - |
| 6 | 1 | - | - |

**Recent Trend:**

- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [PRD, resolved 2026-09-04]: Tier gets three top-level catalog views, not an in-screen filter
- [PRD, resolved 2026-09-04]: `tier` is orthogonal to `Category`; `requires` remains the sole install-order mechanism, never `tier`
- [PRD, resolved 2026-09-04]: `recommends` is a separate, smaller mechanism from `requires` — never auto-installs
- [PRD, resolved 2026-09-04]: Oh-My-Zsh's `git`/`docker` plugins are a config-array edit to `.zshrc`, not new `Tool` entries
- [03-02, 2026-09-05]: Shipped as `omz_plugins_policy` (third Policy factory), in-place single-line editor in `installer/omz.py`, not `apply_block`/`strip_block`
- [04-02, 2026-09-05]: volta is a `tier="system"` catalog tool (Linux script + macOS brew, `~/.volta/bin` on both methods); D-07 recorded on the entry — volta install runs ungated npm postinstall scripts
- [04-03, 2026-09-05]: npm/pnpm global install/add/i exec volta install via an argv-conditional PATH shim; _node uses real_pnpm() absolute path so the wrapper cannot intercept catalog installs
- [04-04, 2026-09-05]: doctor copy distinguishes redirect from block via per-command labels; volta install-scripts tradeoff is a Severity.OK note gated on a live pnpm shim
- [04-05, 2026-09-05]: residual kind=node set is mmdc; snapshot-reinstall is a manual Doctor r action through real_pnpm; automatic post-pnpm-update trigger is Phase 12 (R-03)
- [05-01, 2026-09-05]: GROUP_PIN=ok on pnpm 12.3.4; clean two-invocation path ends as ONE group; allowBuilds is name-only; LIBCHECK=fail without shared libs; BROWNFIELD_BEFORE=ok on this pnpm
- [05-02, 2026-09-05]: codegraph is github_release only (no node/script/brew); no Homebrew formula as of 2026-09-05 so a checksum mismatch is terminal; ai-tier tripwire 9 -> 10
- [05-03, 2026-09-05]: mmdc stays on pnpm (brew and Volta rejected); puppeteer is a user-tier node tool with Linux arm64 gated off; GROUP_PIN=ok; user-tier tripwire 35 -> 36
- [05-04, 2026-09-06]: Doctor replay is grouped/pinned/allow-build-aware; TUI detects split groups via path hashes; console make doctor left unwired
- [07-01, 2026-09-06]: oh-my-zsh is kind=script only with RUNZSH=no CHSH=no KEEP_ZSHRC=yes; requires=[zsh, git] because install.sh clones via git; CHSH=no is a Bazzite correctness requirement
- [07-02, 2026-09-06]: `Platform.os_version`/`min_os_version` fail closed via existing `meets_minimum`; `platform_could_support` is a has_brew-blind browse-time predicate distinct from `resolve_methods`; D-01 disabled catalog rows reuse `UninstallScreen`'s existing dim-row mechanism, threaded through `setup.py`/`UnifiedApp`/`CatalogScreen`

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

- Six companion PRDs from the same 2026-09-04 batch (`package-manager-policy`, `postinstall-hooks`, `catalog-expansion`, `live-package-management`, `background-maintenance-daemon`, `agent-cli-ergonomics`) are queued for ingestion immediately after this roadmap — expect ROADMAP.md to grow with additional phases soon.
- REQ-dependency-chain-requires' illustrative examples (`oh-my-zsh`, `volta`) now have both tools in `registry.toml` (`volta` since 04-02, `oh-my-zsh` since 07-01).

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-06T10:22:00.000Z
Stopped at: 07-02 complete, ready for 07-03
Resume file: .planning/phases/07-system-user-tier-catalog-expansion/07-02-SUMMARY.md
