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

## Milestone: v0.50.0 — Truthful lifecycle

**Shipped:** 2026-11-16 (all 17 phases verified; override closeout only for 20 carried todos)
**Phases:** 17 (17–26 incl. 23.1–23.2, 24.1–24.5) | **Plans:** 276 | **Tests at close:** 7823

### What Was Built
- Host hazards H1–H7 closed, honest exit codes on every route, CI green on both OSes behind a required check
- Registry truth: closed keys, `verified` dates, digest-verified downloads with staged smoke, `make verify-registry` and a weekly drift guard
- One `ToolState` with a closed `Health` set, atomic install receipts as removal proof, one install plan with dispositions, one screen family
- One method lifecycle contract, configuration applied at install time, guard aliases retired, JS priority brew → bun → volta
- Sandboxed tests and container-only e2e; tool-onboarding and catalog-audit skills; Schedules view; Lean split of `setup.py`
- Commit hook, push gate and per-gate make targets; `main` reachable only by branch push → green CI → fast-forward

### What Worked
- Designing from one target architecture (TA §8 rows P1–P9) gave every phase the same state model to build on
- Cross-AI plan review (convergence) before execution, and an independent code review after it, caught real defects each time (e.g. the escape hatch that would have deleted `main` on a detached HEAD)
- opencode-go free models as executors, audited by requesting-code-review and a verifier, delivered Phase 26 at near-zero cost
- Disposable containers in a herdr tab proved removal paths end to end without touching the host

### What Was Inefficient
- Inserted phases (23.1, 23.2, 24.1–24.5) grew the milestone from 9 planned phases to 17
- Phase 26 changed files 14 earlier verifications cover, so every one went stale and had to be re-verified before the close
- Nyquist VALIDATION.md stayed draft on 14 of 17 phases; macOS was never run locally
- Free-model rate limits (longcat) cost an hour-long timeout before the run switched model

### Patterns Established
- One gate, one target: each quality gate has its own pre-commit entry and make target; `validate` aggregates
- Changes reach `main` only through the protected branch → CI → fast-forward flow under `enforce_admins`
- Agents run UATs in a herdr tab with a disposable container and close everything they open
- A test that globs planning files asserts it found them, so an archive move fails instead of passing on zero files

### Key Lessons
1. Close cross-cutting tooling phases (gates, renames) early in a milestone, or budget a re-verification pass for every phase they touch.
2. An inserted phase needs the same SPEC → discuss → converge chain as a planned one; skipping it shows up as review findings later.
3. Free executor models are good enough when a strong reviewer and verifier audit every plan.
4. Archiving moves files that tests may read; grep tests for the moved paths before landing the archive.

### Cost Observations
- Model mix: Opus orchestration and review, Sonnet verifiers and heavy executors, opencode-go free models for Phase 26 plans
- Sessions: many; 2044 commits over 34 days
- Notable: the 14 re-verifications ran in parallel and took about 6 minutes of wall clock

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Key Change |
|-----------|--------|------------|
| v0.49.0 | 28 | First GSD milestone; closed by an independent multi-auditor audit |
| v0.50.0 | 17 | One target architecture; cross-AI plan convergence; protected branch → CI → ff flow |

### Cumulative Quality

| Milestone | Tests | Zero-Dep Additions |
|-----------|-------|-------------------|
| v0.49.0 | 3466 | — |
| v0.50.0 | 7823 | — |
