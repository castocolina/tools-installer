# Handoff: Unified-UI redesign — shared pattern & wayfinding fix (execution-ready)

## Session Metadata
- Created: 2026-06-15 19:46:24
- Project: /Users/ramon/git/personal/tools-installer
- Branch: main (clean, unpushed)
- Session duration: long (Phase 4 close-out → audit → redesign → planning)

### Recent Commits (for context)
  - fb8d1d1 docs: shared-UI-pattern redesign plan + deferred dependencies PRD
  - 80d35ab feat: Phase 4 — Policies tab (generic Policy model, live toggle)
  - e7a3e1b docs: reconcile Phase 3 spec with as-built uninstall layout
  - b10841e Merge unified-UI Phase 3: in-app uninstall view

## Handoff Chain
- **Continues from**: [2026-06-10-182726-tools-installer-catalog-and-path-features.md](./2026-06-10-182726-tools-installer-catalog-and-path-features.md)
- **Supersedes**: None

## Current State Summary

Phase 4 (Policies tab) is DONE, merged to `main`, and its history compacted to 2 commits (`80d35ab` feat + `fb8d1d1` docs). The next body of work — a unified-UI redesign — is fully PLANNED but NOT started. I audited all four UI phases, ran a `ui-ux-designer` redesign and a `reducing-entropy` code pass (the two converged), wrote an execution-ready 3-phase plan, and captured a deferred dependencies PRD. I briefly started Phase 1 then DISCARDED it at the user's request for a clean slate (branch deleted; commits recoverable in reflog as `50f8555`). The next session should execute the plan from Phase 1 on a fresh branch.

## Codebase Understanding

### Architecture Overview
`UnifiedApp` (installer/wizard_app.py) hosts five views (catalog, doctor, fix, uninstall, policies) via a one-deep push/pop screen stack over a base `CatalogScreen`. Decisor/guide split: the pure `installer/` core executes and is 100%-covered + pyright-strict; `setup.py` is the untested, pyright-excluded IO composition root. UI screens collect decisions + render; live-apply (fix/uninstall/policies) runs in-view via injected closures; the app's run value stays `list[str] | None`.

### Critical Files
| File | Purpose | Relevance |
|------|---------|-----------|
| docs/superpowers/plans/2026-06-15-unified-ui-shared-pattern.md | THE plan to execute (3 phases, TDD, complete code) | Start here |
| docs/prds/tool-dependencies-v1.0-prd.md | Deferred deps PRD (separate later effort), clarified 93/100 | Don't build now |
| installer/wizard_app.py | UnifiedApp + the 5 screens | DoctorScreen/FixScreen lack a Footer (the bug) |
| installer/catalog_tui.py | CatalogScreen browser | Source of the Phase-3 `ToolBrowser` extraction |
| installer/uninstall.py | `removable_tools` | Phase 3 extends it with `classify_tools` |
| installer/ui_common.py | TO BE CREATED in Phase 2 | AppScreen scaffold + StatusLine + WayfindingHeader + helpers |
| installer/tool_browser.py | TO BE CREATED in Phase 3 | reusable browser for catalog + uninstall |
| .e2e-artifacts/_capture_audit.py | gitignored; renders all 5 views to SVG | UX review after changes |
| .remember/remember.md | short handoff (same content, condensed) | quick resume |

### Key Patterns Discovered
- TDD throughout; **100% coverage on `installer/` is mandatory** (NOT the 90% pyproject floor) — a single dead line fails the standard.
- Subagent-driven development with two-stage review per task (spec compliance, then code quality).
- Coherent commits ending `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`; English only.
- Headless TUI tests via `app.run_test(size=...)` + Pilot; query parametrized tables with `query_one(DataTable[Any])`; SVG screenshots NBSP-encode spaces — decode with `html.unescape(t).replace(chr(160)," ")`.

## Work Completed

### Tasks Finished
- [x] Phase 4 Policies tab finished, merged, history compacted (10 commits → 2).
- [x] UI audit across all phases (found: Doctor/Fix wayfinding dead-end; Uninstall inconsistency).
- [x] `ui-ux-designer` redesign (shared AppScreen scaffold + WayfindingHeader + ToolBrowser).
- [x] `reducing-entropy` code-duplication ledger (status/mark/summary/highlight → one `ui_common`).
- [x] Wrote the 3-phase implementation plan.
- [x] Captured + clarified (requirements-clarity, 93/100) the deferred dependencies PRD.
- [x] Discarded a premature Phase-1 attempt for a clean slate.

### Files Modified (this session, on main)
| File | Changes | Rationale |
|------|---------|-----------|
| docs/superpowers/plans/2026-06-15-unified-ui-shared-pattern.md | new | the redesign plan |
| docs/prds/tool-dependencies-v1.0-prd.md | new | deferred deps capture |

### Decisions Made
| Decision | Rationale |
|----------|-----------|
| Uninstall = full catalog parity, not-installed/unavailable rows disabled + hinted | makes the hidden removability filter visible; mirrors the catalog |
| Dependencies deferred to their own PRD | install-time gap (e.g. mmdc needs pnpm/node); node method via `pnpm add -g` (never bare npm), `Tool.requires` + cycle-safe topo, auto drag-in+warn, uninstall warn-but-allow |
| One phased plan, each phase independently shippable | Phase 1 ships the bug fix fast; Phase 2/3 are the larger refactor |
| Discard the premature Phase-1 commits | user wants to execute the plan fresh in a new session |

## Pending Work

## Immediate Next Steps
1. Create a feature branch (e.g. `feat/unified-ui-shared-pattern`) — don't build on main.
2. Execute Phase 1 of the plan subagent-driven: footers on Doctor/Fix + app-level `q`/`esc`. (See "Potential Gotchas".)
3. Continue Phase 2 (AppScreen scaffold + ui_common + delete PlaceholderScreen) then Phase 3 (ToolBrowser + catalog-parity Uninstall). Pause for review at each phase boundary.

### Blockers/Open Questions
- [ ] None blocking. The catalog "back" false-affordance and a full Policies→ToolBrowser migration are flagged as in-plan decisions (Phase 2/3), to settle during implementation.

### Deferred Items
- tool-dependencies feature → its own PRD/plan, later.
- main is unpushed; publishing (`git push origin main`) is an explicit owner step.

## Context for Resuming Agent

## Important Context
The plan doc is self-contained and execution-ready (full TDD task code). The fastest value is Phase 1 (an afternoon, no refactor) which fixes the exact reported bug: users get stranded on Doctor/Fix because those screens render no Footer and `q` doesn't quit there.

### Assumptions Made
- The user will `/clear` and start a fresh session to execute the plan subagent-driven.

### Potential Gotchas
- Promoting `q` to an app-level **priority** binding orphans `CatalogScreen`'s own `q`/`action_abort` → dead code that fails the 100% coverage standard. DELETE that duplicate as part of Phase 1.
- `action_back` MUST be `async` — it overrides Textual's base `App.action_back` and pyright-strict rejects a sync override.
- The `esc` app binding must NOT have `priority` (NavScreen's own escape→cancel must win while the palette is open).
- IDE pyright "import could not be resolved" / "type unknown" warnings are SPURIOUS (the IDE ignores the uv venv); the real gate is `uv run pyright` / `make validate`. `setup.py` is pyright-excluded and untested.
- NEVER run the real installer/wizard/--guard/uninstall against the dev machine's home; E2E sandboxes via `monkeypatch.setenv("HOME", tmp_path)`.

## Environment State
### Tools/Services Used
- uv owns the env. Gates: `make validate` (ruff, ruff format, pyright strict, bandit, vulture, shellcheck) and `make test` (pytest + 100% coverage).
### Active Processes
- None.
### Environment Variables
- None with secrets. E2E tests set a sandbox `HOME` (temp dir) only.

## Related Resources
- Plan: docs/superpowers/plans/2026-06-15-unified-ui-shared-pattern.md
- Deferred PRD: docs/prds/tool-dependencies-v1.0-prd.md
- Quick handoff: .remember/remember.md
- Roadmap memory: ~/.claude/projects/-Users-ramon-git-personal-tools-installer/memory/roadmap-status.md
