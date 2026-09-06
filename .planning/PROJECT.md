# tools-installer

## What This Is

tools-installer is an interactive, cross-platform (macOS/Linux, including immutable
Bazzite) Textual TUI and CLI that installs and manages a developer's AI-assisted dev
environment from a single declarative `registry.toml` catalog. It handles install
ordering, dependency drag-in, PATH repair, uninstall, and shell/environment tweaks so
a developer never has to sequence machine-bootstrap steps by hand. Python 3, managed
end-to-end by `uv` (interpreter version, venv, dependencies).

## Core Value

A developer can go from a bare machine to a working, correctly-ordered install
(system prerequisites -> user tools -> AI-agent tooling) entirely through the
catalog, with dependency drag-in resolving automatically and no manual ordering
knowledge required.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from the existing codebase (brownfield) — this is the first GSD planning pass over an already-working installer. -->

- ✓ Interactive Textual TUI catalog: browse/select tools grouped by Category, Priority, Audience, or Status, or as a flat sortable table — shipped pre-GSD
- ✓ Cross-platform install engine covering script/node/sdkman/github_release/tarball/app/dnf/apt/pacman/rpm_ostree/brew/cask methods — shipped pre-GSD
- ✓ Hard-dependency resolution via `Tool.requires`: transitive drag-in, deps-first topological order, cycle detection, unavailable-dependency skipping (`installer/deps.py`) — shipped pre-GSD
- ✓ PATH doctor: read-only audit plus an explicit apply-fix flow — shipped pre-GSD
- ✓ Registry-driven uninstall for userspace (download/app) artifacts, with "managed by Homebrew" vs. "removable here" classification — shipped pre-GSD
- ✓ Policies tab: pip/npm ban (shims + aliases) and curated cross-shell tweak bundles (docker shortcuts, countdown helper, claude skip-permissions, apt selective upgrade) written into `~/.myshellrc` — shipped pre-GSD
- ✓ One view registry / one navigation path / one apply workflow UI architecture (`installer/ui_common.py`, `.claude/architecture.md`) — shipped pre-GSD

### Active

<!-- Current scope: the catalog-tiers-and-dependency-chain PRD (1st of 7 in the 2026-09-04 planning batch). -->

- [ ] **REQ-catalog-tier-field**: Every registry tool declares a `tier` (system/user/ai) on the `Tool` model and registry schema, validated like `Priority`/`Audience`; `uv`/`pnpm`/`brew`/`sdkman` migrate to `tier="system"`
- [ ] **REQ-dependency-chain-requires**: Cross-tier `requires` chains resolve via the existing resolver with zero new resolver logic
- [ ] **REQ-catalog-tier-views**: The catalog splits into three tier-scoped top-level views (System/User/AI) reachable from the top nav
- [ ] **REQ-recommends-soft-dependency**: `Tool.recommends`, a soft-dependency field distinct from `requires`, surfaces (never auto-installs) complementary tools
- [ ] **REQ-install-failure-propagation**: A tool whose `requires` dependency failed earlier in the same run is skipped with a clear "dependency failed" outcome
- [ ] **REQ-uninstall-sweep-tweak-executables**: A full uninstall also removes tweak-managed executables, not only `Tool`-shaped artifacts
- [ ] **REQ-oh-my-zsh-plugin-config**: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to `.zshrc`, reusing the existing rc-editing tweak mechanism

### Out of Scope

- New resolver/ordering logic keyed on `tier` — `requires` already handles ordering, cycle detection, and availability skipping; a second mechanism would drift out of sync (PRD Design Decisions)
- A tier-keyed "gate" blocking ai-tier selection until its system-tier `requires` resolves — redundant with the existing `requires` drag-in
- The actual new tool catalog additions (`oh-my-zsh`, `volta`, `ruby`, `kitty`, `wezterm`, `cursor-agent`, `antigravity`, `codegraph`, etc.) — covered by the companion catalog-expansion PRD, not yet ingested
- Postinstall actions (MCP registration, non-bundled shell plugin wiring) — covered by the companion postinstall-hooks PRD, not yet ingested
- External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step — explicitly deferred per the source PRD's Open Questions
- Package-manager policy, live package management, background maintenance daemon, and agent CLI ergonomics — the four remaining companion PRDs from this batch, deferred to their own future ingest passes

## Context

This is the first of seven PRDs from a 2026-09-04 planning batch being ingested one
at a time, in a deliberate dependency order — catalog-tiers-and-dependency-chain
first because it is foundational (Tier enum, tier-scoped views, the `recommends`
soft-dependency field, and two dependency-resolution gaps found by code review). The
remaining six (package-manager-policy, postinstall-hooks, catalog-expansion,
live-package-management, background-maintenance-daemon, agent-cli-ergonomics) will
be ingested in subsequent merge-mode passes immediately after this one, each
expected to extend ROADMAP.md with further phases — this is not the complete
project scope.

Codebase research performed while drafting the source PRD found that the
dependency-chain mechanism this PRD might otherwise have proposed building already
exists end-to-end (`Tool.requires`, `installer/deps.py:resolve_dependencies`, wired
from `installer/app.py` for every install run) — so the dependency-chain portion of
this milestone is a data problem (declare `requires` in `registry.toml`), not an
architecture problem.

The `REQ-install-failure-propagation` and `REQ-uninstall-sweep-tweak-executables`
requirements were both surfaced by a code review of the already-merged
dependencies-and-shell-tweaks work (commit `431a0a9`): its own PRD/plan specified
"soft-warn + skip dependents on failure", but `installer/session.py::run_installs`
never implemented the skip, and the uninstall planner only walks `Tool` entries,
missing `installer/tweaks.py`'s `ManagedExecutable` artifacts (e.g.
`tools-installer-wait-time`).

## Constraints

- **Tech stack**: Python 3, `uv`-managed (venv + deps + interpreter), Textual TUI, cross-platform macOS/Linux including immutable Bazzite — per `CLAUDE.md`, non-negotiable
- **Architecture**: one view registry (`installer/ui_common.py` `VIEWS`), one navigation path (`UnifiedApp.show_view`), one apply workflow (`ui_common.run_live`), `setup.py` is wiring-only — per `.claude/architecture.md`, "the bias is less total code"
- **No new resolver logic**: `requires` stays the single mechanism for install order, transitive drag-in, cycle detection, and unavailable-dependency skipping; `tier` must never be required to make a `requires` chain resolve — per PRD Design Decisions
- **Quality gates**: new/changed behavior covered by failing tests before implementation; `make validate` and `make test` (at the project's current coverage gate) must pass — per PRD Quality Standards and `CLAUDE.md`'s "never bypass a quality gate"

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `tier` gets three top-level catalog views, not an in-screen filter | Matches the user's actual bootstrap mental model (system -> user -> ai); resolved 2026-09-04 | — Pending |
| `tier` is strictly orthogonal to `Category`; `requires` remains the sole install-order mechanism | Avoids a second ordering mechanism drifting out of sync with the registry's actual `requires` data | — Pending |
| `recommends` is a deliberately separate, smaller mechanism from `requires` — never auto-installs | Preserves the requires/recommends distinction the feature exists to draw, in code and in the UI | — Pending |
| Oh-My-Zsh's `git`/`docker` plugins are a config-array edit to `.zshrc`, not `Tool` entries | They ship bundled inside oh-my-zsh and only need enabling — no download, no install method of their own | — Pending |
| `mmdc` stays on pnpm (`kind="node"`) — Homebrew and Volta both rejected after research | Upstream mermaid-cli's README states Homebrew is "no longer supported"; GitHub issue #1122 records brew-installed mmdc failing at runtime because the formula depends only on `node`. Volta's unrestricted npm postinstall buys nothing for mmdc (no lifecycle scripts of its own) while giving up pnpm's default-deny gate for puppeteer's postinstall. Weighed on stability, security, simplicity, and maintainability. | Phase 5 (05-03) |
| This phase adds new node-method mechanisms (`co_install`/`allow_build`/`versions`/`min_node`, a load-time validator, a version preflight and a replay policy) despite 05-CONTEXT.md `<specifics>` saying "no new mechanisms" | ROADMAP SC#3 cannot be met honestly without them: `requires` alone orders the install while leaving the dependent CLI unable to load its peer at runtime under pnpm's per-invocation isolation | Phase 5 |
| `java`'s SDKMAN candidate needs no pinned `version`. | Verified live in a Tier-3 container (colima+docker, ubuntu:24.04) — `sdk install java` completed non-interactively, exit 0, because SDKMAN's one interactive prompt requires an existing `$CURRENT` version that a first install never has, and this project's `?ci=true` bootstrap additionally closes that prompt's other guard condition for any future re-install through a clean bootstrap this installer performs (not claimed for a brownfield, pre-existing SDKMAN install). | Phase 6 (06-01) |
| Registry-authoring verification is recorded as a `# Verified {date}: ...` prose comment above the entry, never a checked-in snapshot of the verified source (D-01). | Lower friction, matches the project's existing ad hoc convention (`codegraph`/`mmdc`/`puppeteer`), avoids staleness risk from snapshotting upstream content that can change. | Phase 6 (06-01) |
| The general "prefer brew over other userspace package managers" preference is a documented-only registry-authoring guideline, not lint/test enforced (D-02); the SDKMAN carve-out for the Java toolchain named alongside it remains separately test-enforced (`tests/test_registry.py:122-140`), not additionally claimed unenforced. | Brew availability differs too much per OS/tool for a reliable automated "prefer brew" check, so the general preference stays prose; the carve-out already has its own test coverage from commit `0e05f50` and needs no new enforcement. | Phase 6 (06-01) |

---
*Last updated: 2026-09-06 after Phase 6 SDKMAN hardening & registry-authoring guidelines (06-01)*
