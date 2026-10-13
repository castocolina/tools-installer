# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v0.49.0 — Tiered Catalog

**Shipped:** 2026-10-13 (override closeout)
**Phases:** 28 (1–16 incl. 12.1–12.4, 15.1–15.8) | **Plans:** 110 | **Tests at close:** 3466

### What Was Built
- Catalog tiers (system/user/ai), tier-scoped views, `recommends`, failure propagation
- Package-manager redirect policy, `uv-tool` executor, postinstall hooks, maintenance daemon (launchd / systemd user timer)
- Version-aware status, owner-routed updates, live in-TUI install, Owner column, filesystem-based detection
- Self-deduping PATH emission and `~/.shellrc` consolidation; terminal default shell on immutable hosts

### What Worked
- Phase-per-PRD ingestion kept each change reviewable
- Container verification (Rule 14) proved shell changes without touching the real host
- Independent read-only audits (ponytail, GPT-6.1-sol, seven Opus sections) found what per-phase verifiers missed

### What Was Inefficient
- Each phase was verified against its own plan, never against earlier phases' promises: 53 deferred items were forgotten and 15 verifications went stale
- Install, detection, ownership, uninstall and configuration were each fixed per subsystem, so the same question ("installed? whose? removable? healthy?") got 7–10 answers
- CI went red on both OSes and the merge skipped the PR check
- A background CLI hung 2.5 h on an open stdin before anyone checked its log

### Patterns Established
- Research the tool's real install and removal per OS/arch before writing a registry entry (tool-onboarding skill)
- Never remove an artifact the installer cannot prove it wrote
- Background delegated CLIs run with `< /dev/null`, a timeout, and an early log check

### Key Lessons
1. Audit promises across the whole milestone before closing it, not only the last phase.
2. A shared state model has to exist before screens and lifecycle steps can agree; fixing them one by one multiplies the forks.
3. A verification that only checks exit codes cannot catch a link to a directory, a postinstall writing into the CWD, or a removal of someone else's file.
4. Gate merges on CI; a red main hides every later regression.

### Cost Observations
- Sessions: many; audits ran as parallel Opus xhigh subagents plus one opencode GPT-6.1-sol pass
- Notable: the seven-part audit cost less than one phase and reshaped the next milestone

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Key Change |
|-----------|--------|------------|
| v0.49.0 | 28 | First GSD milestone; closed by an independent multi-auditor audit |

### Cumulative Quality

| Milestone | Tests | Zero-Dep Additions |
|-----------|-------|-------------------|
| v0.49.0 | 3466 | — |
