# Tool Dependencies & Node-Package Installs — Product Requirements Document (PRD)

> **Status:** Approved scope, **deferred** for a later milestone. NOT part of the
> unified-UI redesign; that effort only reserves a no-op `Tool.requires=()` seam +
> a detail-bar slot so this PRD retrofits without layout churn. Reference
> implementation: **uzkit** (`/Users/ramon/git/personal/uzkit/tools/installer`).

## Requirements Description

### Background

- **Business problem:** The installer has **no dependency resolution** and **no way
  to install node-package CLIs**. Two concrete failures follow:
  1. Tools like `mmdc` (mermaid CLI, the npm package `@mermaid-js/mermaid-cli`)
     can't be installed at all — there is no node/npm-package install method, and
     bare `npm` is deliberately banned by this project.
  2. Even where a tool depends on another already-installable tool, nothing
     installs them in order or pulls in a missing dependency, and removing a
     runtime silently breaks everything that needed it.
- **Target users:** Developers provisioning an AI dev environment who need
  node-based CLIs (diagram/codegen/agent tooling) alongside the existing catalog.
- **Value proposition:** Tools that depend on others install **correctly, in the
  right order, with missing dependencies pulled in automatically** — and nothing
  is silently broken on uninstall.

### Feature Overview

- **Core features:**
  1. A new **`kind = "node"` install method** — installs `npm_pkg` via
     **`pnpm add -g <pkg>`** (never bare npm; consistent with the existing pip/npm
     ban). Node-package tools declare `requires = ["pnpm"]` (plus any node runtime
     the audit finds necessary, provided via `fnm`/pnpm).
  2. A declarative **`Tool.requires` field** (list of catalog tool ids).
  3. A pure **dependency resolver:** transitive closure + a **stable, cycle-safe
     topological sort** so each tool's `requires` install first.
  4. **Auto drag-in + warn:** selecting a tool pulls in its missing dependencies
     automatically and surfaces a visible notice (uzkit's "dependency wins" model).
  5. **UI surfacing:** the catalog detail bar shows a `requires: X, Y` line; the
     uninstall view **warns (but allows)** when removing a tool others depend on.
- **Feature boundaries — explicitly NOT included:**
  - Version-constraint solving (e.g. "Node ≥ 22"). The `requires` shape is designed
    so a future `{id, min}` form fits, but no version resolution is built now.
  - Bare `npm`/`pip` (banned).
  - Arbitrary system-package dependency management (only inter-catalog deps).
  - Auto-removing dependents on uninstall (warn-but-allow only; no cascade, no block).
- **User scenarios:**
  - *Install:* user selects `mmdc` → resolver drags in `pnpm` (and any node runtime)
    with a notice → tools install pnpm-first, then `mmdc` via `pnpm add -g` → `mmdc`
    runs.
  - *Uninstall:* user removes `pnpm` while `mmdc` is present → the view warns
    "`pnpm` is required by `mmdc`" and lets them proceed.

### Detailed Requirements

- **Input/Output:**
  - Registry input per tool: `kind = "node"`, `npm_pkg = "@scope/pkg"`,
    `requires = ["pnpm", ...]`.
  - Resolver input: the set of selected tool ids + the full catalog. Output: an
    **ordered install list** (dependencies first), the **set of dragged-in ids**,
    and a list of **warnings** (unavailable/disabled deps).
- **User interaction:** selecting a tool with missing `requires` auto-adds them and
  shows a notice; install proceeds dependency-ordered; a failed dependency
  soft-warns and **skips its dependents** (does not abort the whole run).
- **Data requirements:**
  - `Tool.requires: tuple[str, ...] = ()` (parsed from `requires` in the registry).
  - `Tool.npm_pkg: str = ""` (used only by `kind = "node"`).
  - Validation at load: every `requires` id must resolve to a real catalog tool;
    an unknown id is a registry/config error caught by a test.
- **Edge cases:**
  - **Cycles:** the topological sort is stable and cycle-safe; a genuine cycle in
    registry data is a config error surfaced by a dedicated test, not a hang.
  - **Dependency unavailable on the platform:** warn and skip the dependent.
  - **Dependency present but disabled/deselected:** dependency wins — it is dragged
    in and installed — with a warning.
  - **`pnpm` missing for a `node` tool:** `requires = ["pnpm"]` drags it in; if pnpm
    install fails, the node tool soft-warns and is skipped.

## Design Decisions

### Technical Approach

- **Node-package method = `pnpm add -g` (ban-consistent).** `install_node` resolves
  the package manager (pnpm) and runs `pnpm add -g <npm_pkg>`; bare `npm` is never
  used. This reuses a tool the catalog already ships and matches the project's
  existing steering away from `npm`/`pip`. (uzkit prefers volta then pnpm; we drop
  volta — not in our catalog — and standardize on pnpm. Node runtime is provided by
  `fnm`/pnpm; the audit confirms whether a runtime must be an explicit `requires`.)
- **Resolution lives in the pure `installer/` core** (100% covered, pyright-strict),
  mirroring uzkit's `engine.py`: transitive closure + a stable topological sort that
  is cycle-safe, returning install order + dragged-in set + warnings. Screens only
  render; the install ladder consumes the resolved order.
- **UI surfacing reuses the redesign seams:** the catalog detail-bar `requires:` slot
  (reserved by the unified-UI redesign) and a reverse-dependency warning in the
  uninstall view.
- **Version-constraint forward-compatibility:** parse only the string form
  (`requires = ["node"]`) now, but keep the field/types shaped so a future
  `requires = [{ id = "node", min = "22" }]` form is reachable without a data
  migration.

### Constraints

- pyright strict, **no suppressions**; 100% coverage on `installer/`; `setup.py`
  stays the untested IO boundary.
- **English only.** Never invoke bare `npm`/`pip`.
- Deterministic install order (stable sort) so runs are reproducible and testable.

### Risk Assessment

- **Technical — cycles:** a registry cycle could break ordering. *Mitigation:*
  cycle-safe sort + a test asserting a synthetic cycle is reported as a config error.
- **Dependency — pnpm/node runtime absent:** node tools can't install without pnpm.
  *Mitigation:* `requires = ["pnpm"]` drag-in; soft-warn + skip on failure.
- **Data accuracy — full-catalog audit:** declaring wrong/missing `requires` ships
  broken installs. *Mitigation:* live-verify each declared dependency against real
  tool behavior, exactly as prior registry batches were verified against live
  releases.
- **Schedule:** the full-catalog audit (Phase 4) is the long pole. *Mitigation:* the
  mechanism (Phases 1–3) ships and is provable on `mmdc` before the audit completes.

## Acceptance Criteria

### Functional Acceptance
- [ ] A registry tool with `kind = "node"`, `npm_pkg`, and `requires = ["pnpm"]`
      installs via `pnpm add -g <npm_pkg>` (asserted: the executed command, no bare
      `npm`).
- [ ] Selecting `mmdc` with `pnpm` not selected **auto-adds `pnpm`** to the install
      set and surfaces a drag-in notice.
- [ ] The resolver returns dependencies **before** their dependents in install order
      (asserted on a multi-level graph).
- [ ] A synthetic dependency **cycle** is reported as a config error, never a hang.
- [ ] A dependency **unavailable on the platform** warns and the dependent is skipped.
- [ ] The catalog detail bar shows a `requires: …` line for tools that declare deps
      (and nothing when `requires` is empty).
- [ ] The uninstall view **warns but allows** when removing a tool others depend on.
- [ ] Every `requires` id in the shipped registry resolves to a real catalog tool
      (asserted by a registry-integrity test).

### Quality Standards
- [ ] 100% coverage on new `installer/` code; `uv run pyright` clean (no suppressions).
- [ ] No bare `npm`/`pip` anywhere in the node install path.
- [ ] `make validate && make test` green on each commit.

### User Acceptance
- [ ] Installing `mmdc` end-to-end against a sandbox yields a working `mmdc` with its
      dependencies installed in order.
- [ ] README documents the `node` kind, `requires`, the auto-drag-in behavior, and the
      uninstall reverse-dependency warning.

## Execution Phases

### Phase 1: Model & Registry
**Goal:** Declarative dependency + node-package data, validated.
- [ ] Add `requires: tuple[str, ...] = ()` and `npm_pkg: str = ""` to `Tool`; parse in `load_tools`.
- [ ] Add `"node"` to the method/kind taxonomy; validate `requires` ids resolve to real tools (registry-integrity test).
- **Deliverables:** model + parsing + validation, fully covered.

### Phase 2: Resolver
**Goal:** Pure, cycle-safe dependency resolution with drag-in.
- [ ] Implement transitive closure + stable topological sort (mirror uzkit `engine.py`), returning `(install_order, dragged_in, warnings)`.
- [ ] Cover: linear chain, diamond, missing dep drag-in, unavailable-on-platform, synthetic cycle → config error.
- **Deliverables:** `installer/`-level resolver at 100% coverage.

### Phase 3: Node install strategy + ladder wiring
**Goal:** Actually install node packages, dependency-ordered.
- [ ] `install_node` → `pnpm add -g <npm_pkg>` (ban-consistent; pnpm resolution + global-bin setup as needed).
- [ ] Install the resolved order deps-first; soft-warn + skip dependents on failure.
- [ ] Sandbox E2E: installing `mmdc` drags in `pnpm`, installs in order, `mmdc` runs.
- **Deliverables:** node tools installable; `mmdc` proven end-to-end.

### Phase 4: Full-catalog audit + UI surfacing
**Goal:** Seed real dependency data across the catalog and surface it.
- [ ] Audit every catalog tool for inter-tool dependencies and node-package candidates; add `requires`/`kind="node"`/`npm_pkg`, live-verified.
- [ ] Catalog detail-bar `requires:` line (via the redesign's reserved slot).
- [ ] Uninstall reverse-dependency warning (warn-but-allow).
- [ ] README updates.
- **Deliverables:** populated registry + UI surfacing; feature complete.

---

**Document Version:** 1.0
**Created:** 2026-06-15
**Clarification Rounds:** 2 (npm-method/missing-dep/versions/reverse-deps; then node-runtime mechanics/seed scope)
**Quality Score:** 93/100
