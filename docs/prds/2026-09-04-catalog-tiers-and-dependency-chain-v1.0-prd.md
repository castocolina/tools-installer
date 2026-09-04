# Catalog Tiers and Dependency Chain - Product Requirements Document (PRD)

## Requirements Description

### Background

The catalog is currently flat. Every tool carries a `Category` (topical, e.g.
`pkg-mgr`, `search`, `ai`), a `Priority` (`P0`-`P3`), and an `Audience`
(`ai`/`human`/`both`), but nothing expresses which tools are *foundational
prerequisites* the machine needs before anything else can install cleanly, as
opposed to tools a human picks for their own workflow, as opposed to the
agent-facing CLIs that are this project's original reason to exist.

The user's own mental model, given while scoping this PRD, is three tiers:

- **system** - OS-level prerequisites: shell (`zsh`), shell framework
  (`oh-my-zsh` with plugins such as `git`, `docker`), `gnu bash` on macOS,
  Apple Containers, and package managers themselves (`brew`, `volta`, `pnpm`).
- **user** - tools a human picks for their own terminal/editor experience:
  `kitty`, `wezterm`, `sublime`, `vscode`.
- **ai** - agent-facing CLIs and their MCP wiring: `claude`, `opencode`,
  `codex`, `cursor-agent`, `antigravity`, plus MCP registration for tools like
  `codegraph`.

Critically, the user's own example shows tiers are **not** a strict
install-order partition: `oh-my-zsh` (system) must install before `volta`,
`brew`, and `pnpm` (also system, but package managers), which in turn must
install before `claude`, `opencode`, `cursor-agent`, `antigravity`, and their
MCPs (ai tier). The real structure is a dependency graph that happens to
correlate with tier, not three sequential buckets.

**Resolved per user (2026-09-04): oh-my-zsh is a framework layered on zsh,
not a separate shell.** `zsh` is the shell itself; `oh-my-zsh` is a
community framework that manages zsh themes and plugins on top of it - a
distinction the user asked to confirm, verified against oh-my-zsh's own
docs. Concretely, this settles Open Question 1 from the prior draft: `git`
and `docker` "plugins" are **not** separate `Tool` catalog entries. They
ship *bundled inside* oh-my-zsh itself and only need enabling in the
`plugins=(...)` array inside `.zshrc` - no download, no install method of
their own. (A genuinely *external/custom* oh-my-zsh plugin - one not
bundled - would need a `git clone` into `~/.oh-my-zsh/custom/plugins/`
first; the user's two named plugins are both bundled, so this PRD's core
scope does not need that download step, but it is worth naming as a future
extension, not built now.) This is a config-array edit, matching this
project's existing rc-editing tweak mechanism (`installer/shellrc.py`'s
`apply_block`/`strip_block`), not the `Tool`/`Method`/`requires` model.

**Correction to the bootstrap-order example, verified 2026-09-04:**
Homebrew's own installer has been a plain bash script since 2020 (no system
Ruby needed to *run* the installer) - and once installed, Homebrew manages
its own bundled Ruby internally (`portable-ruby`) for its own operations.
**A separate system-level Ruby install is not actually a Homebrew
prerequisite on a modern macOS.** The real, verified clean-machine bootstrap
order the user was describing is: **Xcode Command Line Tools** (needed by
many build toolchains and by Homebrew itself when it has to build from
source) -> **Homebrew** (bash installer, brings its own Ruby) -> everything
else. If the user still wants a `ruby` catalog entry, it is for the user's
*own* Ruby/gem-based development (e.g. CocoaPods-style workflows), not as a
Homebrew dependency - a different, legitimate reason, just not the one in
the original example.

**Important finding from codebase research (2026-09-04):** the dependency
graph mechanism this PRD might otherwise propose building **already exists
and is already wired end-to-end**:

- `Tool.requires: tuple[str, ...]` (`installer/model.py`) is a generic field,
  not scoped to any one install `kind`.
- `installer/deps.py:resolve_dependencies` does transitive drag-in, deps-first
  topological ordering, cycle detection (`DependencyCycleError`), and drops
  branches blocked by an unavailable-on-this-platform dependency.
- It is already invoked from `installer/app.py` for every install run,
  regardless of tool kind - this is not scoped to `node`/`npm_pkg` tools.

So the dependency-chain part of this PRD is a **data problem** (declare the
right `requires` in `registry.toml` for the new tools), not an architecture
problem. What is actually new is the **tier** concept itself: a label for
catalog organization (browsing, filtering, default sort) that today has no
representation at all.

### Target Users

- Developers bootstrapping a new machine who want the installer to get the
  OS-level prerequisites right before anything else, without having to
  understand the dependency graph themselves.
- Developers browsing the catalog who want to distinguish "things my machine
  needs" from "things I personally like" from "things my AI agents need."

### Value Proposition

- Make the catalog's browsing structure match how the user actually thinks
  about their toolchain, without duplicating the ordering logic that
  `installer/deps.py` already provides correctly.
- Let new system-prerequisite tools (shell, shell framework, package
  managers) be declared once and have every downstream tool that needs them
  drag them in automatically, exactly as `mmdc`'s `pnpm` dependency already
  does today.

## Feature Overview

### Core Features

1. Add a `tier` field to the `Tool` model and `registry.toml` schema:
   `system` / `user` / `ai`.
2. **Resolved per user (2026-09-04): tier gets its own top-level views, not
   just a filter.** Instead of one Catalog view with a tier filter, the
   catalog splits into separate views the user navigates to directly - a
   System view, a User view, an AI view - matching how the user actually
   works through a fresh machine (system prerequisites first, then personal
   picks, then agent tooling), each aware that its own tools can carry
   `requires` on tools from an earlier tier. This is a bigger UI change than
   originally scoped: it means the existing single-`Catalog` entry in the
   shared `VIEWS` registry (`installer/ui_common.py` - the "one registry, one
   nav path" standard from `.claude/architecture.md`) becomes three catalog
   views (or one `CatalogScreen` parameterized by tier, reusing
   `ToolBrowser` - an implementation choice for the planning phase, not
   decided here) rather than a single view with an in-screen filter.
3. Declare `requires` chains in the registry for the new system-tier tools so
   the existing resolver drags them in correctly (see the companion catalog
   PRD `2026-09-04-catalog-expansion-v1.0-prd.md` for the actual tool list).
4. **Added per user (2026-09-04): move existing package-manager tools onto
   the system tier.** `uv`, `pnpm`, `brew` already exist in the registry
   under `category="pkg-mgr"` (verified) and simply gain `tier="system"`.
   `sdkman` already exists (added by the doctor/catalog refresh PRD's Java
   tooling) and gains `tier="system"` too. `volta` does not exist in the
   registry yet - it is a new addition (tracked in
   `2026-09-04-catalog-expansion-v1.0-prd.md`) that ships directly as
   `tier="system"`, `category="pkg-mgr"` from the start. `ruby`, if added,
   is `tier="system"` as well, per the corrected bootstrap-order note above.
5. **Added per user (2026-09-04): "soft dependencies" - a `recommends`
   field, distinct from `requires`.** When a user selects an ai-tier tool
   (e.g. `claude`, `opencode`), the catalog should surface (not
   auto-install) tools that improve LLM-assisted workflows - `codegraph`,
   `graphify`, `rtk`, and similar. Unlike `requires`, a `recommends` edge
   never drags the recommended tool in automatically; it is a prompt/
   highlight the user can accept or ignore. This needs its own field on
   `Tool` (`recommends: tuple[str, ...] = ()`) and its own, separate
   handling in `installer/deps.py` (or a new, smaller pure function next to
   it) - `resolve_dependencies` must not be extended to silently also drag
   in `recommends` edges, since that would collapse the very distinction
   this feature exists to draw.
6. Document, in `.claude/architecture.md`, that `tier` is a browsing/
   navigation label and `requires` remains the single source of truth for
   install order - so a future contributor does not try to build a second
   ordering mechanism keyed on tier.

### Feature Boundaries

In scope:

- The `tier` field itself: enum, registry schema, model validation.
- Splitting the catalog into per-tier top-level views (System/User/AI),
  including the `VIEWS` registry and navigation wiring this implies.
- Registry `requires` declarations connecting the new system-tier tools to
  the tools that need them (data only - the resolver code does not change).
- The new `recommends` field and its own (non-`requires`) surfacing
  mechanism in the TUI.
- Reassigning `uv`/`pnpm`/`brew`/`sdkman` to `tier="system"` in the existing
  registry.

Out of scope:

- Any change to `installer/deps.py`'s resolution algorithm - it already does
  what this PRD needs.
- The actual list of new tools and their install methods (covered by
  `2026-09-04-catalog-expansion-v1.0-prd.md`).
- Postinstall actions (MCP registration, shell plugin wiring) - covered by
  `2026-09-04-postinstall-hooks-v1.0-prd.md`.

## Detailed Requirements

### Tier Field Requirements

- Add `Tier` to `installer/enums.py` as a `StrEnum` with values `system`,
  `user`, `ai`, following the exact pattern of `Priority`/`Audience`.
- Every registry entry must declare a `tier`. Existing entries need a
  migration pass: package managers (`brew`, `pnpm`/`volta` once added) and
  shell tools -> `system`; editors, terminals, GUI apps -> `user`; agent
  CLIs (`claude`, `codex`, `opencode`) and AI-facing utilities -> `ai`.
- `Tool` model validation must reject an unknown tier value the same way it
  already rejects an unknown `Priority`/`Category` (see `_parse_enum` in
  `installer/model.py`).

### Dependency Chain Requirements

- No new resolver logic. `requires` continues to be the single mechanism
  that determines install order; `resolve_dependencies` continues to handle
  transitive drag-in, cycle detection, and unavailable-dependency skipping
  exactly as it does today.
- The new system-tier tools' `requires` chains must express the graph from
  the Background section, e.g. (illustrative, not final registry syntax):
  `oh-my-zsh.requires = ["zsh"]`, `volta.requires = ["oh-my-zsh"]` (or
  `["zsh"]`, see Open Questions), and agent CLIs that need a node-based
  package manager keep their existing `requires = ["pnpm"]`-style
  declarations.
- A tier value must never be required to make a `requires` chain resolve -
  the resolver has no notion of tier and this PRD must not introduce one.

### Install-Time Failure Propagation (gap found by review, added 2026-09-04)

**Background - how this surfaced:** a code-review of the already-merged
dependencies-and-shell-tweaks work (commit `431a0a9`) found that its own
PRD (`docs/prds/dependencies-and-shell-tweaks-v1.0-prd.md`) and plan
(`docs/superpowers/plans/2026-06-21-dependencies-and-shell-tweaks.md`,
task A3) both specify: "install the resolved order deps-first; soft-warn +
skip dependents on failure" - but `installer/session.py::run_installs`
iterates the resolved order and installs every tool unconditionally,
regardless of whether an earlier tool in the same run failed. A failed
`pnpm` install today still lets a dependent like `mmdc` run its
`pnpm add -g` step and fail with a confusing pnpm-side error, instead of
being skipped with a clear "skipped: its dependency `pnpm` failed to
install" message. `resolve_dependencies` (`installer/deps.py`) only
resolves the *pre-install* case (a dependency unavailable on this
platform, or a cycle) - it has no visibility into runtime install outcomes,
so this is a distinct gap, not a duplicate of what it already handles.

- `run_installs` (or wherever the per-tool install loop lives) must track
  which tool ids failed during the current run, and skip any subsequent
  tool whose `requires` intersects that failed set - emitting a distinct
  `SKIPPED`-shaped outcome (not `INSTALLED`, not silently omitted) naming
  which dependency failed, so the summary view is honest about why a tool
  was never attempted.
- This does not change `resolve_dependencies`'s pre-install resolution
  logic (still "no new resolver logic," per the requirement above) - it is
  a new runtime concern layered on top of the already-resolved install
  order, scoped to `installer/session.py` (or `installer/engine.py`,
  whichever owns the per-tool install loop - resolve at implementation
  time).
- **Status: identified by review, not implemented.** Left for GSD's own
  research/plan/execute flow rather than an ad hoc assistant fix, per the
  user's explicit correction (2026-09-04) that mid-review implementation
  should not have happened for the SDKMAN item either - see the parallel
  note in `2026-09-04-package-manager-policy-v1.0-prd.md`'s Open
  Questions.

### Uninstall Sweep Completeness (gap found by review, added 2026-09-04)

**Background:** the same review found that `installer/tweaks.py`'s
countdown-helper managed executable (`tools-installer-wait-time`, in
`~/.local/bin`) is only removed when its own policy is explicitly toggled
off - a full uninstall run (`installer/app.py::run_uninstall`/
`perform_uninstall`, `installer/uninstall.py::plan_uninstall`) has no
knowledge the file exists and leaves it behind. Every other artifact this
installer writes (binaries, cask bundles, managed shell blocks) is swept
by a full uninstall; this one specific managed executable is not,
because it was added as part of a `TweakBundle` rather than a `Tool`, and
the uninstall planner only walks `Tool` entries today.

- Uninstall's plan/execute path must also account for tweak-managed
  executables (`installer/tweaks.py`'s `ManagedExecutable` mechanism),
  not just `Tool`-shaped artifacts, so a full uninstall genuinely leaves
  nothing behind regardless of whether an artifact came from a `Method` or
  a `TweakBundle`.
- **Status: identified by review, not implemented.** Same GSD-flow
  deferral as the failure-propagation gap above - this PRD records the
  requirement; execution belongs to GSD's own process.

### Catalog TUI Requirements

- **Per-tier top-level views**, not an in-screen filter: System, User, and
  AI each get their own entry point reachable from the top nav, alongside
  (or nested under) the existing views. Within each tier view, the existing
  Category/Priority/Audience/Status/Table grouping/sort still applies -
  tier is the outer navigation dimension, the existing dimensions remain
  the inner ones.
- Cross-tier `requires` must stay visible from a dependent tool's own tier
  view - e.g. selecting `claude` (ai tier) that needs `pnpm` (system tier)
  must not require the user to have separately visited the System view
  first; the existing drag-in behavior and its notice
  (`render_dependency_notice`) already communicate this, just now across a
  tier boundary instead of within one flat list.
- The tier a user has *not* yet visited should still make it obvious "what
  does my system need first" - concretely, opening the AI view before the
  System view, and selecting a tool with an unresolved system-tier
  `requires`, should make the drag-in (or, per the existing unavailable-
  dependency handling, a clear notice) obvious without forcing a specific
  visit order.

### Recommends (Soft Dependency) Requirements

- `Tool.recommends: tuple[str, ...] = ()` - ids of tools that pair well
  with this one, never auto-installed.
- Selecting a tool with `recommends` surfaces a prompt/notice naming the
  recommended tools and letting the user add them to the current selection
  with one action - never a blocking modal, and never silently added.
- `recommends` referencing an id lower in the same tier or a different tier
  is valid (e.g. `claude.recommends = ["codegraph", "graphify", "rtk"]`,
  all ai tier) - unlike `requires`, there is no ordering obligation to
  enforce, since nothing is auto-dragged-in.

## Design Decisions

### Technical Approach

- Reuse `installer/deps.py` and `Tool.requires` unchanged for hard
  dependencies. `recommends` is a deliberately separate, smaller mechanism -
  not a variant of `resolve_dependencies` - so the two can never be
  confused in code the way they must not be confused in the UI.
- Treat `tier` as strictly orthogonal to `Category` - a tool keeps its
  existing topical category (e.g. `shell`, `pkg-mgr`) and gains a tier on
  top, the same way it already has a priority and an audience.
- Do not build a "tier gate" that blocks selecting an ai-tier tool until its
  system-tier dependency is resolved as a separate check - `requires` already
  does this via drag-in; a second, tier-keyed gate would be redundant logic
  that could drift out of sync with the registry's actual `requires` data.
- Oh-My-Zsh's `git`/`docker` plugins are a config-array edit
  (`plugins=(...)` in `.zshrc`), reusing the existing `apply_block`/
  `strip_block` rc-editing mechanism - not new `Tool` entries, not a new
  primitive. A future *external/custom* oh-my-zsh plugin (requiring its own
  `git clone` step) would need its own small mechanism, explicitly deferred
  - see Open Questions.

### Risks

- If `tier` is treated as purely cosmetic by registry authors, catalog
  entries can drift (e.g., a package manager filed under `user` by mistake)
  with no test catching it unless tier gets its own invariant test, the way
  `Priority`/`Audience` already have coverage per the doctor-catalog-refresh
  PRD's acceptance criteria.
- Splitting Catalog into three tier-scoped views is a larger change to the
  `VIEWS` registry / navigation architecture than the original single-filter
  scoping assumed - it touches the same "one registry, one nav path"
  standard the TUI interaction consistency work spent real effort
  establishing, so this needs its own careful design pass at plan time, not
  a quick bolt-on.
- A `recommends` prompt that fires too often or on tools with a long
  recommends list could feel naggy - needs a UX pass on exactly when/how it
  surfaces (see Open Questions), not just that it exists.

## Acceptance Criteria

### Functional Acceptance

- [ ] `Tier` enum exists in `installer/enums.py` with `system`/`user`/`ai`.
- [ ] Every registry entry declares a `tier`; loading a registry entry with a
      missing or unknown `tier` fails the same way an unknown `Priority` does.
- [ ] `uv`/`pnpm`/`brew`/`sdkman` carry `tier="system"`.
- [ ] The catalog has three tier-scoped top-level views (System/User/AI),
      each still supporting the existing Category/Priority/Audience/Status/
      Table grouping within it.
- [ ] System-tier prerequisite tools (shell, shell framework, package
      managers) drag in correctly via `requires` when a dependent tool is
      selected from any tier view, using the existing `resolve_dependencies`
      - no new resolver code.
- [ ] Selecting `claude`/`opencode` (or similar) surfaces its `recommends`
      list without auto-installing anything.
- [ ] A tool whose `requires` dependency failed to install during the same
      run is skipped with a clear "dependency failed" outcome, never
      silently attempted or silently omitted.
- [ ] A full uninstall removes every tweak-managed executable
      (`ManagedExecutable`-shaped artifacts), not only `Tool`-shaped ones.
- [ ] Oh-My-Zsh's `git`/`docker` plugins are enabled via a config-array edit
      to `.zshrc`, not a separate `Tool` entry.

### Quality Standards

- [ ] New and changed behavior is covered by failing tests before
      implementation.
- [ ] `make validate` passes.
- [ ] `make test` passes at the project's current coverage gate.
- [ ] `.claude/architecture.md` documents that `tier` is a browsing label,
      not an ordering mechanism.

### User Acceptance

- [ ] Browsing the catalog, it is obvious which tools are machine
      prerequisites versus personal picks versus agent-facing tools.
- [ ] Selecting an ai-tier tool that needs an undeclared system-tier
      prerequisite still drags it in automatically, with no manual step.

## Open Questions

All three original open questions are resolved per the user (2026-09-04):
oh-my-zsh plugins are a config-array edit, not `Tool` entries; tier gets its
own top-level views, not a filter; and the package-manager-to-`oh-my-zsh`
dependency question is superseded by `oh-my-zsh` itself only needing `zsh`
(nothing else in the system tier needs to depend on the framework, just the
shell). Remaining questions, all opened by this session's scope additions:

1. **View layout mechanics**: does each tier get a fully separate
   `Screen`/`AppScreen`, or one parameterized `CatalogScreen` instantiated
   three times (reusing `ToolBrowser`)? This is squarely an implementation
   choice for the planning phase, not a requirements question, but it
   determines how much new code this PRD's "bigger UI change" risk actually
   costs.
2. **`recommends` surfacing UX**: does it show once per session, once ever
   (dismissible, remembered), or every time the tool is (re)selected? Needs
   a design pass to avoid the "naggy" risk noted above.
3. **External (non-bundled) oh-my-zsh plugins**: explicitly out of this
   PRD's core scope (the user's two named plugins are both bundled), but
   worth deciding whether it is a fast-follow or genuinely out of scope
   long-term, since "which plugins are bundled vs. custom" is itself a fact
   that would need verifying per-plugin if this ever expands beyond
   `git`/`docker`.
4. Does `recommends` need its own registry-authoring convention/lint (e.g.
   "every ai-tier tool should consider whether it has LLM-workflow-adjacent
   recommends") or is it purely opportunistic, added only where someone
   thought to add it?
