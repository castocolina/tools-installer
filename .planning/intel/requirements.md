# Requirements

Source PRD: `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`
(classified `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`,
confidence: high, manifest_override: true, locked: false)

## REQ-catalog-tier-field
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Add a `tier` field (`system`/`user`/`ai`) to the `Tool` model and `registry.toml` schema, replacing the flat category/priority-only structure, so catalog entries can be organized by machine-prerequisite vs. personal-pick vs. agent-facing tooling.
- acceptance:
  - `Tier` enum exists in `installer/enums.py` with `system`/`user`/`ai`, following the exact pattern of `Priority`/`Audience`.
  - Every registry entry must declare a `tier`; loading a registry entry with a missing or unknown `tier` fails the same way an unknown `Priority` does (see `_parse_enum` in `installer/model.py`).
  - `uv`/`pnpm`/`brew`/`sdkman` carry `tier="system"` (migration of existing entries).
  - `tier` is treated as strictly orthogonal to `Category` — a tool keeps its existing topical category and gains a tier on top, the same way it already has a priority and an audience.
  - `.claude/architecture.md` documents that `tier` is a browsing/navigation label and `requires` remains the single source of truth for install order.
- scope: catalog tiers, registry schema, Tool model validation

## REQ-dependency-chain-requires
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Declare `requires` chains in `registry.toml` for new system-tier tools (e.g. `oh-my-zsh`, `volta`) so the existing `installer/deps.py:resolve_dependencies` resolver drags them in correctly across tier boundaries. This is a data problem, not an architecture problem — the resolver already exists and is already invoked from `installer/app.py` for every install run.
- acceptance:
  - No new resolver logic; `requires` remains the single mechanism for install order, transitive drag-in, cycle detection, and unavailable-dependency skipping, exactly as `resolve_dependencies` does today.
  - New system-tier tools' `requires` chains express the graph described in the Background section (illustrative, not final registry syntax: `oh-my-zsh.requires = ["zsh"]`, `volta.requires = ["oh-my-zsh"]` or `["zsh"]`).
  - A tier value must never be required to make a `requires` chain resolve — the resolver has no notion of tier.
  - System-tier prerequisite tools drag in correctly via `requires` when a dependent tool is selected from any tier view, using the existing `resolve_dependencies` — no new resolver code.
  - Selecting an ai-tier tool that needs an undeclared system-tier prerequisite still drags it in automatically, with no manual step.
- scope: dependency chain, requires declarations, Homebrew bootstrap order, oh-my-zsh

## REQ-install-failure-propagation
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: `run_installs` (or wherever the per-tool install loop lives) must track which tool ids failed during the current run and skip any subsequent tool whose `requires` intersects that failed set, emitting a distinct `SKIPPED`-shaped outcome naming which dependency failed — instead of letting a dependent (e.g. `mmdc`) run and fail with a confusing downstream error after its dependency (e.g. `pnpm`) already failed. Gap identified by review of the already-merged dependencies-and-shell-tweaks work (commit `431a0a9`); its own PRD/plan specified "soft-warn + skip dependents on failure" but `installer/session.py::run_installs` does not currently implement the skip.
- acceptance:
  - A tool whose `requires` dependency failed to install during the same run is skipped with a clear "dependency failed" outcome, never silently attempted or silently omitted.
  - Does not change `resolve_dependencies`'s pre-install resolution logic — this is a new runtime concern layered on top of the already-resolved install order, scoped to `installer/session.py` (or `installer/engine.py`).
- scope: install-time failure propagation, installer/session.py, installer/engine.py
- status: Per source — "identified by review, not implemented." Deferred to GSD's own research/plan/execute flow rather than an ad hoc assistant fix.

## REQ-uninstall-sweep-tweak-executables
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Uninstall's plan/execute path (`installer/app.py::run_uninstall`/`perform_uninstall`, `installer/uninstall.py::plan_uninstall`) must also account for tweak-managed executables (`installer/tweaks.py`'s `ManagedExecutable` mechanism, e.g. `tools-installer-wait-time` in `~/.local/bin`), not just `Tool`-shaped artifacts, so a full uninstall genuinely leaves nothing behind regardless of whether an artifact came from a `Method` or a `TweakBundle`. Gap identified by the same review: this managed executable is currently only removed when its own policy is explicitly toggled off, since the uninstall planner only walks `Tool` entries today.
- acceptance:
  - A full uninstall removes every tweak-managed executable (`ManagedExecutable`-shaped artifacts), not only `Tool`-shaped ones.
- scope: uninstall sweep completeness, installer/uninstall.py, installer/tweaks.py
- status: Per source — "identified by review, not implemented." Same GSD-flow deferral as REQ-install-failure-propagation.

## REQ-catalog-tier-views
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Split the existing single `Catalog` entry in the shared `VIEWS` registry (`installer/ui_common.py`) into three tier-scoped top-level views (System/User/AI) reachable directly from the top nav — not an in-screen filter — matching how the user works through a fresh machine. Each tier view retains the existing Category/Priority/Audience/Status/Table grouping and sort as inner dimensions, tier being the outer navigation dimension. Whether this is three separate screens or one `CatalogScreen` parameterized by tier (reusing `ToolBrowser`) is an implementation choice deferred to the planning phase.
- acceptance:
  - The catalog has three tier-scoped top-level views (System/User/AI), each still supporting the existing Category/Priority/Audience/Status/Table grouping within it.
  - Cross-tier `requires` stays visible from a dependent tool's own tier view — e.g. selecting `claude` (ai tier) that needs `pnpm` (system tier) must not require a prior System-view visit; the existing drag-in behavior and its notice (`render_dependency_notice`) communicate this across the tier boundary.
  - Opening a tier view before its prerequisite tier (e.g. AI before System) and selecting a tool with an unresolved system-tier `requires` makes the drag-in, or a clear unavailable-dependency notice, obvious without forcing a specific visit order.
  - Browsing the catalog, it is obvious which tools are machine prerequisites versus personal picks versus agent-facing tools.
- scope: catalog TUI, VIEWS registry, one-registry-one-nav-path standard (.claude/architecture.md)

## REQ-recommends-soft-dependency
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Add a `Tool.recommends: tuple[str, ...] = ()` field, distinct from `requires`, that surfaces (never auto-installs) tools that pair well with a selected tool (e.g. `codegraph`, `graphify`, `rtk` for `claude`/`opencode`), with its own resolution/surfacing mechanism in `installer/deps.py` or an adjacent, smaller pure function. `resolve_dependencies` must not be extended to also drag in `recommends` edges, since that would collapse the distinction the feature exists to draw.
- acceptance:
  - Selecting `claude`/`opencode` (or similar) surfaces its `recommends` list without auto-installing anything.
  - Selecting a tool with `recommends` surfaces a prompt/notice naming the recommended tools and letting the user add them to the current selection with one action — never a blocking modal, and never silently added.
  - `recommends` referencing an id lower in the same tier or a different tier is valid (e.g. `claude.recommends = ["codegraph", "graphify", "rtk"]`, all ai tier) — unlike `requires`, there is no ordering obligation to enforce.
- scope: recommends soft dependency, catalog TUI, installer/deps.py

## REQ-oh-my-zsh-plugin-config
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to the `plugins=(...)` array in `.zshrc`, reusing the existing rc-editing tweak mechanism (`installer/shellrc.py`'s `apply_block`/`strip_block`) — not modeled as separate `Tool`/`Method`/`requires` catalog entries, since they ship bundled inside oh-my-zsh and only need enabling, no download or install method of their own.
- acceptance:
  - Oh-My-Zsh's `git`/`docker` plugins are enabled via a config-array edit to `.zshrc`, not a separate `Tool` entry.
- scope: oh-my-zsh, shell config, installer/shellrc.py
