# Requirements: tools-installer

**Defined:** 2026-09-04
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.

## v1 Requirements

Requirements for this milestone (ingest batch 1/7: `catalog-tiers-and-dependency-chain`).
Each maps to exactly one roadmap phase.

### Catalog Tiers

- [ ] **REQ-catalog-tier-field**: Every registry tool declares a `tier` (`system`/`user`/`ai`) on the `Tool` model and `registry.toml` schema, validated the same way an unknown `Priority` is rejected today; `uv`/`pnpm`/`brew`/`sdkman` migrate to `tier="system"`.
- [ ] **REQ-catalog-tier-views**: The catalog's single flat view splits into three tier-scoped top-level views (System/User/AI) reachable directly from the top nav, each keeping the existing Category/Priority/Audience/Status/Table grouping, with cross-tier `requires` drag-in still visible from a dependent tool's own tier view.

### Dependency Chain

- [ ] **REQ-dependency-chain-requires**: Cross-tier `requires` chains resolve via the existing resolver (`installer/deps.py:resolve_dependencies`) with zero new resolver logic, demonstrated end-to-end using chains that now cross the new tier boundary (e.g. `mmdc`->`pnpm`, `java`->`sdkman`) once `pnpm`/`sdkman` carry `tier="system"`.
- [ ] **REQ-recommends-soft-dependency**: `Tool.recommends: tuple[str, ...] = ()`, a soft-dependency field distinct from `requires`, surfaces (never auto-installs) complementary tools via a one-action, non-blocking prompt when a tool such as `claude`/`opencode` is selected.

### Install/Uninstall Lifecycle

- [ ] **REQ-install-failure-propagation**: `run_installs` tracks which tool ids failed during the current run and skips any subsequent tool whose `requires` intersects that failed set, emitting a distinct "dependency failed" outcome instead of letting the dependent run and fail with a confusing downstream error.
- [ ] **REQ-uninstall-sweep-tweak-executables**: A full uninstall also removes tweak-managed executables (`installer/tweaks.py`'s `ManagedExecutable` artifacts, e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts.

### Shell Tweaks

- [ ] **REQ-oh-my-zsh-plugin-config**: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to the `plugins=(...)` array in `.zshrc`, reusing the existing `apply_block`/`strip_block` tweak mechanism — not a separate `Tool`/`Method`/`requires` catalog entry.

## v2 Requirements

None deferred from this batch. The six companion PRDs from the same 2026-09-04
planning batch (`package-manager-policy`, `postinstall-hooks`, `catalog-expansion`,
`live-package-management`, `background-maintenance-daemon`, `agent-cli-ergonomics`)
will be ingested in subsequent merge-mode passes immediately after this one, adding
their own v1 requirements (and likely further ROADMAP.md phases) rather than v2
deferral of this batch's scope.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New resolver/ordering logic keyed on `tier` | `requires` already does deps-first ordering, cycle detection, and unavailable-dependency skipping; a second ordering mechanism would drift out of sync (PRD Design Decisions) |
| A "tier gate" blocking ai-tier selection until its system-tier `requires` resolves | Redundant with the existing `requires` drag-in; a second, tier-keyed check could go stale |
| The actual new tool list (`oh-my-zsh`, `volta`, `ruby`, `kitty`, `wezterm`, `cursor-agent`, `antigravity`, `codegraph`, etc.) and their install methods | Covered by the companion catalog-expansion PRD, not yet ingested |
| Postinstall actions (MCP registration, non-bundled shell plugin wiring) | Covered by the companion postinstall-hooks PRD, not yet ingested |
| External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step | Explicitly deferred by the source PRD's Open Questions; the two named plugins (`git`, `docker`) are both bundled |
| `recommends` surfacing cadence (once per session vs. every reselect) and a registry-authoring lint for `recommends` completeness | Open questions left to the planning phase, not yet requirements |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-catalog-tier-field | Phase 1 | Pending |
| REQ-dependency-chain-requires | Phase 1 | Pending |
| REQ-catalog-tier-views | Phase 2 | Pending |
| REQ-recommends-soft-dependency | Phase 2 | Pending |
| REQ-install-failure-propagation | Phase 3 | Pending |
| REQ-uninstall-sweep-tweak-executables | Phase 3 | Pending |
| REQ-oh-my-zsh-plugin-config | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-04*
*Last updated: 2026-09-04 after initial roadmap creation (ingest batch 1/7: catalog-tiers-and-dependency-chain)*
