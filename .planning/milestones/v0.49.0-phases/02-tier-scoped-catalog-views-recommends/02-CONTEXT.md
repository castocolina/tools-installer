# Phase 2: Tier-Scoped Catalog Views & Recommends - Context

**Gathered:** 2026-09-04
**Status:** Ready for planning

<domain>
## Phase Boundary

The single flat Catalog view splits into three tier-scoped top-level views
(System/User/AI), each keeping the existing Category/Priority/Audience/
Status/Table grouping. A new `Tool.recommends` soft-dependency field
surfaces complementary tools via a one-action, non-blocking prompt when a
tool like `claude`/`opencode` is selected — never auto-installed.

</domain>

<decisions>
## Implementation Decisions

### Nav bar ordering
- **D-01:** The three tier views land FIRST in `VIEW_ORDER`, before the existing maintenance views: `System(1) / User(2) / AI(3) / Doctor(4) / Uninstall(5) / Policies(6)`. This renumbers every existing view's key binding (today's Doctor=2/Uninstall=3/Policies=4 all shift by +2). — **Reversibility:** reversible — `VIEW_ORDER`/`VIEWS` in `installer/ui_common.py` is a single table; reordering rows is a one-line-per-view change per `.claude/architecture.md`'s "one view registry" design, and number keys are derived automatically from position (`installer/wizard_app.py`, `enumerate(VIEW_ORDER)`).
- **Rationale:** matches the phase's own stated goal — "browsing matches how the user actually walks a fresh machine: system prerequisites, then personal picks, then agent tooling" — putting maintenance actions (Doctor/Uninstall/Policies) after the actual catalog, not before it.

### Recommends demo tools (Phase 2 vs. Phase 8 split)
- **D-02:** Phase 2 builds the generic `Tool.recommends: tuple[str, ...] = ()` mechanism and proves it end-to-end with an illustrative pair of tools that already exist in `registry.toml` today — NOT `codegraph`/`graphify`/`rtk`, which don't exist in the catalog until Phase 8 (`REQ-recommends-wiring-agent-hosts`).
- **D-03:** Phase 8 is where `claude`/`opencode`/`codex`/`cursor-agent`/`antigravity` actually get `recommends = ["codegraph", "graphify", "rtk"]` (adjusted per tool), once those three tools are real catalog entries. Phase 2's `recommends` mechanism must not need a recommended id to resolve to an existing tool at wiring time or at runtime for the demo pair specifically — but no work is scoped in Phase 2 to make an unresolvable recommended id gracefully tolerated end-to-end, since it isn't exercised by the illustrative pair.
- **Rationale:** avoids dangling references to catalog entries that don't exist yet, and avoids Phase 2 duplicating research that Phase 8 is already scoped to do properly.

### Recommends prompt trigger & accept behavior
- **D-04:** The recommends prompt fires at selection time — when the tool is space-marked in the tier-view table — not after a real install completes.
- **D-05:** Accepting the prompt adds the recommended tool(s) into the SAME staged selection batch (mode="STAGED": space marks, enter installs) — it does not trigger a separate, immediate install action. This matches the existing Catalog interaction model exactly; `recommends` acceptance is indistinguishable from manually marking the recommended tool yourself.
- **Rationale:** one mental model for the whole Catalog surface (staged-then-commit), no new install-timing edge case introduced by `recommends`.

### Claude's Discretion
- Which specific existing-tool pair in `registry.toml` best illustrates `recommends` for the Phase 2 demo (planner's choice, informed by which pair has an obviously "complementary, not required" relationship).
- Exact widget/screen mechanics for the one-action recommends prompt (e.g. inline row annotation vs. a small modal) — implementation detail, not a user decision.
- How the tier-scoped `CatalogScreen` instances share code — `installer/catalog_tui.py::CatalogScreen` already takes an arbitrary `tools: list[Tool]` in its constructor, so three tier views can likely reuse it directly with a pre-filtered list; confirming/wiring this is planning/implementation work.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tier/requirements source
- `.planning/PROJECT.md` — Requirements, Key Decisions table
- `.planning/REQUIREMENTS.md` — REQ-catalog-tier-views, REQ-recommends-soft-dependency, REQ-recommends-wiring-agent-hosts (Phase 8, for context on what Phase 2 is NOT doing yet)
- `.planning/ROADMAP.md` — Phase 2 goal, 4 success criteria, `UI hint: yes`
- `.planning/phases/01-catalog-tier-foundation/01-CONTEXT.md` — Phase 1's tier classification decisions (D-01 through D-07); Phase 2 consumes `Tool.tier` as already-landed
- `.claude/architecture.md` — "one view registry" design (`VIEWS` table in `installer/ui_common.py`), "one navigation path" (`UnifiedApp.show_view`)

### Existing pattern to mirror
- `installer/ui_common.py::View`/`VIEWS`/`VIEW_ORDER`/`VIEW_BY_NAME` (lines ~79-145) — the single per-view registry; adding the 3 tier views is a row-insertion here
- `installer/wizard_app.py` — `enumerate(VIEW_ORDER)` derives number-key bindings automatically (line ~670); `CatalogScreen(tools, installed, blurbs)` instantiation (line ~690) is the direct template for tier-filtered instances
- `installer/catalog_tui.py::CatalogScreen` (line ~132) — already takes `tools: list[Tool]` in its constructor and does its own grouping/sorting (`group_tools`, `sort_for_table`) — reusable as-is per tier, just filtered by `tool.tier` before construction
- `installer/deps.py::resolve_dependencies` — produces the `warnings` list (drag-in / unavailable-dependency notices) that success criteria 2-3 require to be visible regardless of which tier view the user started from
- `installer/wizard_app.py` — Policies screen's `_requires_cell`/missing-requires rendering (lines ~490-559) is the closest existing UI precedent for surfacing a dependency relationship inline, though `recommends` is a new, distinct (never-auto-install) mechanism

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `installer/catalog_tui.py::CatalogScreen` — constructor already accepts an arbitrary tool list; no new browser widget needed for the 3 tier views, just 3 filtered instantiations
- `installer/ui_common.py::VIEWS`/`View` dataclass — one-row-per-view addition pattern, already designed for exactly this kind of extension

### Established Patterns
- Number-key bindings are never hand-assigned — they're derived from `VIEW_ORDER` position, so nav reordering (D-01) is data-only, not a binding-logic change
- `resolve_dependencies` already separates `requires` (hard, auto-drag-in) from anything else; `recommends` must stay a clearly distinct code path — mirrors the requires/recommends distinction locked in Phase 1's Key Decisions

### Integration Points
- `installer/model.py::Tool` — needs the new `recommends: tuple[str, ...] = ()` field, same shape as `requires`
- `installer/ui_common.py::VIEWS` — 3 new `View` rows (System/User/AI), existing 4 reordered per D-01
- `installer/wizard_app.py` — wherever `CatalogScreen` is currently instantiated once for the flat catalog becomes 3 call sites, one per tier, filtering `self.tools` by `tool.tier`
- `installer/catalog_tui.py` or `wizard_app.py` — new recommends-prompt UI triggered on space-mark, wired into the same staged-selection state the Catalog table already tracks

</code_context>

<specifics>
## Specific Ideas

- The recommends prompt should feel like "the same table, one more row got checked" — not a modal interrupting the staged-selection flow.
- `codegraph`/`graphify`/`rtk` are the real, named target data for `claude`/`opencode`'s recommends — just not landing until Phase 8.

</specifics>

<deferred>
## Deferred Ideas

- Wiring `claude`/`opencode`/`codex`/`cursor-agent`/`antigravity`'s actual `recommends` data — explicitly deferred to Phase 8 (`REQ-recommends-wiring-agent-hosts`), not scope creep, already on the roadmap.

</deferred>

---

*Phase: 2-tier-scoped-catalog-views-recommends*
*Context gathered: 2026-09-04*
