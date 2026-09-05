# Phase 2: Tier-Scoped Catalog Views & Recommends - Pattern Map

**Mapped:** 2026-09-04
**Files analyzed:** 5 (2 modified core files, 1 new field, 1 UI hook point, N/A new files — this phase mostly extends existing files rather than creating new ones)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `installer/ui_common.py::VIEWS` (add 3 rows, reorder) | config (data-table registry) | CRUD (row insert/reorder) | `installer/ui_common.py::VIEWS` itself (existing 4-row table) | exact — same table, more rows |
| `installer/wizard_app.py::UnifiedApp.__init__` (3 `CatalogScreen` instances instead of 1) | controller (screen wiring) | request-response (screen install/push) | `installer/wizard_app.py:690` current single `CatalogScreen(tools, installed, blurbs)` call | exact — same constructor, filtered inputs |
| `installer/model.py::Tool.recommends` (new field) | model | CRUD (declarative parse) | `installer/model.py::Tool.requires` (lines 65, 78, 93, 137-140, 152) | exact — same shape, soft vs hard semantics differ |
| recommends prompt hook (new, screen-level or `ToolBrowser`-level) | component / event-driven | event-driven (fires on space-mark) | `installer/tool_browser.py::ToolBrowser.action_toggle_selected` (lines 211-220) + `SelectionChanged` message (line 80-82) | role-match — extend the toggle handler, not a new mechanism |
| `installer/deps.py`-adjacent "recommends" lookup (NOT a deps.py addition) | utility (pure function, no resolution graph) | transform (id list lookup, one hop, no recursion) | `installer/deps.py::resolve_dependencies` (lines 31-137) — explicitly a **negative** analog: recommends must NOT follow this transitive/cycle-checked/warning-producing shape | anti-pattern reference — recommends is deliberately simpler |

## Pattern Assignments

### `installer/ui_common.py::VIEWS` — add System/User/AI tier views, reorder existing 4

**Analog:** `installer/ui_common.py` lines 79-145 (the `View` dataclass + `VIEWS` tuple itself)

**The registry row shape** (lines 79-96):
```python
@dataclass(frozen=True)
class View:
    name: str
    label: str
    palette: str
    mode: str
    glyph: str
    style: str
    hint: str
    actions: str
```

**Existing catalog row to model the 3 new tier rows on** (lines 101-111):
```python
View(
    name="catalog",
    label="Catalog",
    palette="Catalog - pick tools to install",
    mode="STAGED",
    glyph="o",
    style="cyan",
    hint="space marks a tool; enter installs your selection",
    actions="space toggle | enter install | a all | i invert",
),
```

**What changes per D-01:** `VIEWS` becomes an 6-row tuple. The single `catalog` row is replaced by three rows — e.g. `name="system"`, `name="user"`, `name="ai"` — each keeping `mode="STAGED"` and the same `actions=` string (interaction model is identical, only the tool list differs), landing FIRST, before `doctor`/`uninstall`/`policies` (which shift +2 automatically since `_view_key` in `_view_key(index)` at line 148-154 and `GLOBAL_NAV` at line 160 both derive from position/count, not hardcoded numbers — note `GLOBAL_NAV`'s `"1-4 views"` string literal at line 160 must be hand-updated to `"1-6 views"` since it is NOT auto-derived).

`VIEW_ORDER`/`VIEW_BY_NAME` (lines 144-145) need no code change — they derive from `VIEWS` automatically:
```python
VIEW_ORDER: tuple[str, ...] = tuple(view.name for view in VIEWS)
VIEW_BY_NAME: dict[str, View] = {view.name: view for view in VIEWS}
```

**Caution:** `WayfindingHeader` (lines 185-224) and `FooterBar` (163-183) both iterate `VIEWS`/index into `VIEW_BY_NAME` generically — no per-view-name branching exists in `ui_common.py`, so no additional edits are needed there beyond the `GLOBAL_NAV` literal.

---

### `installer/wizard_app.py::UnifiedApp` — one `CatalogScreen` becomes three tier-filtered instances

**Analog:** `installer/wizard_app.py` lines 674-698 (`UnifiedApp.__init__`), lines 708-730 (`on_mount`, `get_default_screen`), lines 732-742 (`show_view`)

**Current single-instance wiring** (line 690):
```python
self._catalog = CatalogScreen(tools, installed, blurbs)
```

**Pattern to extend to 3 tier-scoped instances** — filter `tools` by `tool.tier` before construction (per CONTEXT.md's stated discretion note — `CatalogScreen.__init__` at `installer/catalog_tui.py:150-161` already takes an arbitrary `tools: list[Tool]`, no widget change needed):
```python
self._system_catalog = CatalogScreen([t for t in tools if t.tier == Tier.SYSTEM], installed, blurbs)
self._user_catalog = CatalogScreen([t for t in tools if t.tier == Tier.USER], installed, blurbs)
self._ai_catalog = CatalogScreen([t for t in tools if t.tier == Tier.AI], installed, blurbs)
```

**Base-screen precedent to preserve or adapt** (lines 722-730):
```python
@property
def catalog(self) -> CatalogScreen:
    return self._catalog

def get_default_screen(self) -> CatalogScreen:
    # The catalog is the app's base screen ... reports via Decided message
    return self._catalog
```
Only ONE of the three tier screens can be `get_default_screen()`'s base screen (Textual apps have exactly one base screen); the other two must be handled like `doctor`/`uninstall`/`policies` today — installed via `self.install_screen(screen, name)` in `on_mount` (lines 708-720) and pushed/popped via `show_view` (lines 732-742), which already generalizes over arbitrary view names in `self._views: dict[str, Screen[None]]` (line 692). Per D-01 nav order, `system` is first, so `system` is the natural new base screen; `user` and `ai` join the `self._views` dict alongside `doctor`/`uninstall`/`policies`.

**`show_view`'s existing one-view-active invariant** (lines 732-742) needs no logic change — it already generalizes over `name != "catalog"` by construction; only the literal string `"catalog"` (used as the base-screen sentinel in 4 places: `show_view` lines 738/740, `_navigable` line 750, `action_back` line 766-767) must be renamed to whichever tier becomes the new base view name (e.g. `"system"`).

**`Screen.Decided` message wiring** — each tier `CatalogScreen` independently posts `CatalogScreen.Decided` (catalog_tui.py lines 142-148); `UnifiedApp` must listen on all three, not just the base screen's forwarded message, since Textual only auto-bubbles from the *active* screen. Check how `on_mount`/`run()`'s message forwarding currently listens for `Decided` before this phase — three producers means the app must accumulate a cross-tier staged selection or reduce three `Decided` results into one final list depending on which tier screen the user pressed `enter` from.

---

### `installer/model.py::Tool.recommends` — new soft-dependency field, mirroring `requires`

**Analog:** `installer/model.py::Tool.requires` — the exact hard-dependency field this phase's field must mirror in *shape* while staying semantically distinct.

**Field declaration** (line 65, dataclass body):
```python
# No-op dependency seam for the tool-dependencies PRD: ids this tool needs
# at install time. Parsed and carried here; no resolution logic lives yet.
requires: tuple[str, ...] = ()
```
Add directly below it:
```python
# Soft-dependency seam (REQ-recommends-soft-dependency): ids this tool
# pairs well with but never auto-installs or auto-drags-in. Surfaced only
# as a UI prompt at selection time; distinct from `requires`, which
# resolve_dependencies() expands transitively.
recommends: tuple[str, ...] = ()
```

**`__init__` signature + assignment** (lines 67-93) — add a `recommends: tuple[str, ...] = ()` parameter after `requires` and `object.__setattr__(self, "recommends", recommends)` after line 93, following the identical pattern already used for `requires`.

**`load_tools` parsing** (lines 137-153) — mirror the exact `raw_requires` validation block for a new `raw_recommends`:
```python
raw_requires = row.get("requires", [])
if isinstance(raw_requires, str):
    # tuple("pnpm") would silently become ('p','n','p','m'); a list is required.
    raise ValueError(f"tool '{row['id']}': 'requires' must be a list of tool ids")
```
and the constructor call site adds `recommends=tuple(raw_recommends)` beside `requires=tuple(raw_requires)` at line 152.

**Key contrast — where `recommends` must NOT mirror `requires`:**
- `installer/model.py::load_tools` has no `requires_integrity_errors`-style unresolved-id CI gate applied to `requires` shown in `deps.py` lines 140-150 (`requires_integrity_errors`) — per CONTEXT D-03, Phase 2's demo `recommends` pair must resolve to real ids, but the mechanism itself is NOT required to add an analogous `recommends_integrity_errors` gate in this phase (deferred; Phase 8 is where non-existent recommended ids would first appear were the gate skipped).
- `installer/deps.py::resolve_dependencies` (lines 31-137) is the hard-dependency analog to explicitly NOT copy: no transitive closure, no cycle detection, no auto drag-in, no warnings list. `recommends` needs only a flat one-hop lookup: given a selected tool id, return `tool.recommends` verbatim.

**Test pattern to mirror** — `tests/test_model.py` lines 15-43 (`test_tool_requires_defaults_empty_and_parses`) is the direct template for a new `test_tool_recommends_defaults_empty_and_parses` test; line 202-214 (`test_load_tools_rejects_requires_as_a_string`) is the template for the `recommends`-as-string rejection test.

**Demo tool pair for Phase 2 (Claude's Discretion per D-02):** `rg` (id `rg`, `installer/registry.toml` lines 77-93, tier=`ai`, category=`search`) and `jq` (id `jq`, category likely `data`/`text`, tier=`ai` — verify with `grep -n 'id = "jq"' -A6 installer/registry.toml`) are both real, already-cataloged AI-tier tools with an "obviously complementary, not required" relationship (search + JSON transform, commonly piped together) — a strong, low-risk illustrative pair that avoids the not-yet-existing `codegraph`/`graphify`/`rtk` ids reserved for Phase 8.

---

### Recommends prompt hook — fires on space-mark, joins the same STAGED batch

**Analog:** `installer/tool_browser.py::ToolBrowser.action_toggle_selected` (lines 211-220) and the `SelectionChanged` message (lines 80-82) it posts; consumed today by `CatalogScreen.on_tool_browser_selection_changed` (`installer/catalog_tui.py` lines 240-243).

**Current toggle flow to hook into:**
```python
def action_toggle_selected(self) -> None:
    item = self._highlighted_item()
    if item is None:  # empty table or a section row
        return
    if not self._adapter.selectable(item):  # a space on a non-selectable row is inert
        return
    item_id = self._adapter.item_id(item)
    self.selected.symmetric_difference_update({item_id})
    self.query_one(DataTable[Any]).update_cell(item_id, "sel", mark(item_id in self.selected))
    self.post_message(self.SelectionChanged())
```

**Where the recommends prompt hooks in (per D-04/D-05):** NOT inside `ToolBrowser` itself (that widget is generic/reusable across catalog and uninstall, per its own docstring lines 1-8 — it must stay data-agnostic). Instead, hook at the `CatalogScreen` level, which already owns tool-specific knowledge (`self.tools`, `tool.requires` detail rendering at lines 198-209 of `catalog_tui.py`). Extend `CatalogScreen.on_tool_browser_selection_changed` (lines 240-243) — currently just clears the status line — to also: (1) check if the just-toggled tool (available via `event` or a new `ToolBrowser` public "last toggled id" seam) has a non-empty `.recommends`, (2) if newly marked (not unmarked) and any recommended id is not yet in `self._browser.selected`, surface the prompt.

**Non-blocking prompt UX (D-05 constraint — must land in the SAME staged batch, no separate install):** the prompt's "accept" action should call the exact same mutation `ToolBrowser` already exposes for marking a tool — `self.selected.symmetric_difference_update({rec_id})` plus `update_cell(rec_id, "sel", mark(True))` (mirroring lines 217-219) — NOT `resolve_dependencies` (that would wrongly treat `recommends` as a hard dependency) and NOT a new install-trigger path. This keeps "accepting a recommendation" indistinguishable from the user manually space-marking that row, exactly as D-05 requires.

**Do NOT use as the analog:** `installer/wizard_app.py::PoliciesScreen._requires_cell`/`_policy_detail`'s "missing: ..." rendering (lines 490-495, 533-537) — this is LIVE-mode, read-only inline text for a hard requirement gate (policy blocked until requirement installed), the opposite of `recommends`'s non-blocking, always-optional, STAGED-mode nature. It is cited in CONTEXT.md only as "closest existing UI precedent for surfacing a dependency relationship inline" — useful for the *visual convention* (dim inline text near the row) but NOT for the interaction semantics.

**Detail-bar precedent worth reusing for visual convention only:** `CatalogScreen._detail_text` (`installer/catalog_tui.py` lines 198-209) already appends a conditional dependency clause:
```python
if tool.requires:
    detail += f"  |  requires {', '.join(tool.requires)}"
return detail
```
A parallel `if tool.recommends: detail += f"  |  pairs well with {', '.join(tool.recommends)}"` is a low-risk, no-new-widget way to make `recommends` visible in the existing detail bar — independent of whatever the interactive one-action prompt turns out to be (D-note: "exact widget/screen mechanics ... implementation detail, not a user decision").

---

## Shared Patterns

### One view registry, one nav path (`.claude/architecture.md`)
**Source:** `installer/ui_common.py::VIEWS`/`VIEW_ORDER`/`VIEW_BY_NAME` (lines 101-145)
**Apply to:** the 3 new tier views — add rows, do not special-case tier views elsewhere; `WayfindingHeader`, `FooterBar`, and `_view_key` all already generalize over `VIEWS` by iteration/index, never by name-matching.

### Derived, not hand-assigned, number-key bindings
**Source:** `installer/wizard_app.py` lines 668-671
```python
*[
    Binding(str(i + 1), f"show('{name}')", name, priority=True)
    for i, name in enumerate(VIEW_ORDER)
],
```
**Apply to:** confirms D-01's claim that reordering `VIEWS` is a pure data change — no binding-logic edit needed when the 3 tier views are inserted first.

### Hard vs. soft dependency field pair on `Tool`
**Source:** `installer/model.py::Tool.requires` (hard, lines 65/78/93/137-153) vs. new `Tool.recommends` (soft)
**Apply to:** `installer/model.py` only. Both fields share identical parse/validate shape (tuple of str ids, list-not-string guard, default `()`); they diverge entirely downstream — `requires` feeds `installer/deps.py::resolve_dependencies`'s transitive/auto-drag-in graph, `recommends` must feed only a flat, one-hop, never-auto-install prompt.

### Tool-list filtering by enum field (no new query mechanism)
**Source:** existing `tool.category ==`/`tool.priority ==`/`tool.audience ==` filters throughout `installer/catalog_tui.py::group_tools` (lines 48-87)
**Apply to:** `installer/wizard_app.py`'s 3 tier-filtered `CatalogScreen` instantiations — `[t for t in tools if t.tier == Tier.SYSTEM]` follows the exact same list-comprehension-over-enum-equality idiom already used pervasively for `category`/`priority`/`audience` grouping, no new filtering utility needed.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| cross-tier `Decided`-message reduction in `UnifiedApp` | controller | event-driven | No existing precedent for multiple `CatalogScreen` instances coexisting and each independently posting `Decided` — today there is exactly one `CatalogScreen`. Planner must design how `UnifiedApp` merges/awaits three tier screens' selections into the single final result `run()` returns. |
| `recommends`-triggered inline prompt widget itself | component | event-driven | No existing "small modal / inline annotation on space-mark" widget exists in the codebase; `_requires_cell`'s inline text (Policies, LIVE mode) and `NavScreen`'s `ModalScreen` (`installer/wizard_app.py` ~line 640) are the two nearest shapes but neither matches D-05's "same table, one more row got checked" non-blocking constraint exactly — this is genuinely new UI, left to planner/implementer discretion per CONTEXT.md. |

## Metadata

**Analog search scope:** `installer/ui_common.py`, `installer/catalog_tui.py`, `installer/tool_browser.py`, `installer/model.py`, `installer/enums.py`, `installer/deps.py`, `installer/wizard_app.py`, `installer/prompt.py`, `installer/selection.py`, `installer/registry.toml`, `tests/test_model.py`, `tests/test_catalog_tui.py`
**Files scanned:** 12
**Pattern extraction date:** 2026-09-04
