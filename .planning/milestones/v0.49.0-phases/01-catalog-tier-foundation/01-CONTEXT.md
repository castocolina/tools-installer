# Phase 1: Catalog Tier Foundation - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Every catalog tool is labeled `system`/`user`/`ai` via a new `Tool.tier` field
(validated like `Priority`/`Audience` today), and the existing dependency
resolver is proven to carry that labeling across tier boundaries with zero
new ordering logic. This phase also backfills `tier` onto every existing
`registry.toml` entry (~240 tools) so the field can be hard-required.

</domain>

<decisions>
## Implementation Decisions

### Tier vs. Audience relationship
- **D-01:** `tier` and `audience` stay two separate, orthogonal fields — `tier` (system/user/ai) captures bootstrap order and which top-level view a tool appears under; `audience` (ai/both/human) keeps meaning "who benefits" and keeps driving the existing Audience grouping view in `catalog_tui.py`. Collapsing them was considered and rejected because `audience=both` (e.g. ripgrep, fd) has no lossless equivalent in a 3-value tier.
- **D-02:** Views/tier value names are `system` / `user` / `ai` as already stated in ROADMAP.md/REQUIREMENTS.md — not renamed to `dev-tools`.

### Tier validation strictness
- **D-03:** A registry entry with a missing `tier` is a hard `load_tools` validation error, same code path as an unrecognized enum value (`_parse_enum`). This deliberately diverges from `priority`/`audience`'s silent-default pattern — it forces every existing entry to be tagged deliberately in this phase, matching ROADMAP success criterion #1's literal wording. — **Reversibility:** costly — reverting to a silent default later means re-auditing which of the ~240 entries were left unclassified, since nothing will have forced that data to exist.

### Classification rule for the ~240 existing entries
- **D-04:** Base rule is **per-Category default**, not per-audience: `Category.PACKAGE_MANAGER`, `SHELL`, `CONTAINER`, `RUNTIME` default to `tier="system"` (bootstrap-layer categories — package managers, shells like zsh/oh-my-zsh, containers like Apple Containers, and language runtimes/version managers including sdkman-managed ones); `Category.AI` defaults to `tier="ai"`; every other category defaults to `tier="user"`.
- **D-05:** Named overrides on top of the category default (category alone is not authoritative for these):
  - Xcode Command Line Tools → `tier="system"` regardless of its Category — it is a bootstrap prerequisite for installing Ruby and then Homebrew itself, same conceptual layer as `uv`/`pnpm`/`brew`/`sdkman`.
  - Agent-optimized CLI replacement tools → `tier="ai"` regardless of Category, even though their Category (e.g. SEARCH/TEXT) would otherwise default them to `user`. Named examples the user gave: `rg`, `bat`, and similar fast/agent-consumable replacements (`fd`, `eza`, `sd` follow the same reasoning — these are the tools the PRD that inspired this repo specifically calls out), plus `codegraph`, `graphify`, and `rtk`.
  - GUI desktop apps stay `tier="user"` under the plain category default — no override needed. Named examples: VS Code, Sublime, iTerm.
- **D-06:** No named override list is exhaustive as written — the planner/executor apply the category-default + these two override principles across the actual `registry.toml` contents, rather than requiring the user to enumerate all ~240 entries by hand.

### Backfill scope
- **D-07:** Full backfill now — all ~240 existing entries get a real `tier` value in this phase, not just `uv`/`pnpm`/`brew`/`sdkman`. This is a direct consequence of D-03 (missing tier is a hard error): a partial backfill would make `load_tools` raise for every untouched entry and break the app until later phases finish tagging.

### Claude's Discretion
- Exact wiring of the per-Category default table into code (e.g. a lookup dict vs. inline conditionals in `load_tools`) is an implementation detail, not a user decision.
- Whether the cross-tier resolver proof (success criterion #3, java→sdkman) becomes a new automated test or is verified by an existing one is left to planning/testing strategy.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tier/requirements source
- `.planning/PROJECT.md` — Requirements, Constraints, Key Decisions table (tier orthogonal to Category, `requires` stays the sole ordering mechanism)
- `.planning/REQUIREMENTS.md` — REQ-catalog-tier-field, REQ-dependency-chain-requires full text
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, "Depends on: Nothing"
- `.claude/architecture.md` — must be updated per success criterion #4 to state `tier` is a browsing label only

### Existing pattern to mirror
- `installer/enums.py` — `Priority`/`Audience` `StrEnum` pattern; new `Tier` enum should follow the identical shape
- `installer/model.py` — `Tool.priority`/`Tool.audience` field declaration, `_parse_enum` validation call, and `load_tools`'s per-row parsing (lines ~59-90, ~143-146) are the direct template for wiring `tier`
- `installer/catalog_tui.py` — `AUDIENCE_LABEL`/`_AUDIENCE_STYLE` grouping-view pattern (lines ~31, ~69-72, ~104, ~188, ~203) is the template for a future tier-scoped view (Phase 2), informs how tier will be consumed downstream

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/enums.py::Priority`/`Audience` (`StrEnum`) — exact shape to copy for the new `Tier` enum
- `installer/model.py::_parse_enum` — generic enum-parsing helper already used for `priority`/`audience`/`category`; reuse directly for `tier`, including its errors-on-unknown-value behavior

### Established Patterns
- `Tool` is a frozen dataclass built via `object.__setattr__` during parsing (`installer/model.py` `__init__` / `from_row`-style construction) — `tier` wiring should follow this same construction path, not a separate post-processing step
- `installer/deps.py::resolve_dependencies` already does transitive `requires` resolution, deps-first topological order, cycle detection, and unavailable-dependency skipping — Phase 1 must NOT add tier-aware branches here; success criterion #3 is proven by feeding it entries whose `tier` differs across a `requires` edge (java→sdkman) and confirming behavior is unchanged

### Integration Points
- `installer/model.py::load_tools` — where the new hard-required `tier` validation and Category-default backfill logic both land
- `installer/registry.toml` — ~240 `[[tool]]` entries needing a `tier =` line each
- `.claude/architecture.md` — needs the explicit "tier is a browsing label, requires is the only ordering mechanism" statement (success criterion #4)

</code_context>

<specifics>
## Specific Ideas

- Xcode Command Line Tools named explicitly by the user as the canonical "hidden system-tier tool under a general category" example (needed to install Ruby, which then installs Homebrew).
- Agent-optimized CLI tools named explicitly as tier=ai regardless of category: ripgrep (`rg`), `bat`, and "similars" (fd/eza/sd), plus `codegraph`, `graphify`, `rtk` — these are the tools the project's own founding PRD called "the reason that inspired this repo."
- User-tier examples named explicitly: VS Code, Sublime, iTerm, and other desktop apps.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope. (The tier/audience relationship question could have become scope creep toward redesigning Audience entirely, but the "keep both axes" decision closed it without needing a separate phase.)

</deferred>

---

*Phase: 1-catalog-tier-foundation*
*Context gathered: 2026-09-04*
