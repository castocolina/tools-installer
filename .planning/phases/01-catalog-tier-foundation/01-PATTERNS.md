# Phase 1: Catalog Tier Foundation - Pattern Map

**Mapped:** 2026-09-04
**Files analyzed:** 3 (1 new/modified enum+model surface, 1 modified data file, 1 proof/no-op file)
**Analogs found:** 3 / 3 (all in-repo, no external analogs needed — this phase is a direct extension of an existing pattern, not new architecture)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `installer/enums.py` (add `Tier` StrEnum) | model/config (enum) | CRUD (closed value set) | `Priority`/`Audience` in same file, lines 6-20 | exact |
| `installer/model.py` (add `Tool.tier` field + hard-required parsing) | model | CRUD (per-row parse/validate) | `Tool.audience` field + `_parse_enum` wiring, lines 60/86-88/144 | exact, with one deliberate divergence (hard-required, no default) |
| `installer/registry.toml` (backfill `tier =` on ~240 `[[tool]]` entries) | config/data | batch (declarative data) | existing `priority =` / `audience =` lines per entry, e.g. lines 64-65 | exact |
| `installer/deps.py` (no code change — used as proof target) | service | transform (graph resolution) | itself — `resolve_dependencies`, `Tool.requires` walk, lines 58-68 | n/a (verify-only, not authored) |
| `installer/catalog_tui.py` (no change this phase; informs Phase 2) | component | request-response (UI grouping) | `AUDIENCE_LABEL`/`_AUDIENCE_STYLE`, lines 31/104 — reference only, not touched in Phase 1 | future-reference |

## Pattern Assignments

### `installer/enums.py` — add `Tier`

**Analog:** `Audience` enum, `installer/enums.py:15-20`

```python
class Audience(StrEnum):
    """Who primarily benefits from a catalog tool."""

    AI = "ai"
    BOTH = "both"
    HUMAN = "human"
```

**Apply directly by analogy** — same `StrEnum` base, same lowercase string values matching TOML literals, same one-line docstring style. Per CONTEXT.md D-02, values are `system` / `user` / `ai` (not renamed):

```python
class Tier(StrEnum):
    """Bootstrap-order / top-level view a tool belongs to."""

    SYSTEM = "system"
    USER = "user"
    AI = "ai"
```

Place it adjacent to `Priority`/`Audience` (before `Category`) to keep the "closed value sets" file grouped by concern, matching the file's existing top-to-bottom ordering (Priority, Audience, Category, InstallStatus, UninstallState, Severity).

---

### `installer/model.py` — add `Tool.tier` field + parsing

**Analog:** `Tool.audience` wiring, three touch points:

**1. Import line** (`installer/model.py:8`):
```python
from installer.enums import Audience, Category, Priority
```
→ becomes `from installer.enums import Audience, Category, Priority, Tier`

**2. `EnumValue` TypeVar** (`installer/model.py:25`):
```python
EnumValue = TypeVar("EnumValue", Audience, Category, Priority)
```
→ add `Tier` to the bound so `_parse_enum(Tier, ...)` type-checks: `TypeVar("EnumValue", Audience, Category, Priority, Tier)`

**3. Dataclass field declaration** (`installer/model.py:59-60`):
```python
priority: Priority
audience: Audience
```
→ add `tier: Tier` alongside. **Divergence per CONTEXT.md D-03:** unlike `priority`/`audience`, `tier` has no default in the `__init__` signature — no `= Priority.P3`-style default (`installer/model.py:73-74` shows the pattern to *not* copy: `priority: str | Priority = Priority.P3`). Declare it as a required positional/keyword parameter instead, e.g. `tier: str | Tier,` with no `=` default.

**4. `__init__` body parsing** (`installer/model.py:86-88`, the exact template):
```python
object.__setattr__(
    self, "audience", _parse_enum(Audience, audience, "audience", f"tool '{id}'")
)
```
→ copy verbatim with `tier`/`Tier`:
```python
object.__setattr__(
    self, "tier", _parse_enum(Tier, tier, "tier", f"tool '{id}'")
)
```
`_parse_enum` (`installer/model.py:32-41`) already raises `ValueError` with an "unknown X (expected one of: ...)" message on a bad value — reuse unmodified, no new error path needed for *invalid* values. The *missing* case is the divergence (see below).

**5. `load_tools` per-row construction** (`installer/model.py:143-144`, the exact template):
```python
priority=row.get("priority", "P3"),
audience=row.get("audience", "both"),
```
**Do NOT copy the `.get(..., default)` silent-default shape for `tier`.** Per D-03, a missing `tier` must be a hard `load_tools` error, same severity class as an unrecognized enum value. Use `row["tier"]` (raises `KeyError`) or an explicit presence check that raises `ValueError` with a message consistent with the rest of `load_tools`'s error style (e.g. compare to `installer/model.py:101`: `raise ValueError(f"tool '{row['id']}' declares no install methods")`). Recommended concrete shape, matching the file's existing "raise ValueError with tool id context" idiom:
```python
if "tier" not in row:
    raise ValueError(f"tool '{row['id']}' is missing a required 'tier'")
```
placed near the other early per-row validations (alongside the `category`/`requires` checks at `installer/model.py:102`/`132-135`), then pass `tier=row["tier"]` into the `Tool(...)` call — no default fallback string.

**Category-default backfill logic (D-04/D-05):** this is *data* backfill into `registry.toml`, not code in `load_tools`. CONTEXT.md's Claude's-Discretion note explicitly allows either a lookup dict or inline conditionals if the executor chooses to generate defaults programmatically while backfilling, but the field itself must land as literal `tier = "..."` TOML lines (see registry.toml pattern below) — `load_tools` should not silently compute tier from category at load time, since D-03 requires the value to already be present and hard-required.

---

### `installer/registry.toml` — backfill `tier =` per entry

**Analog:** existing `priority =` / `audience =` lines, e.g. the `uv` entry (`installer/registry.toml:59-66`):
```toml
[[tool]]
id = "uv"
name = "uv"
category = "pkg-mgr"
cmd = "uv"
priority = "P0"
audience = "both"
desc = "Fast Python package and venv manager"
```
Add a `tier = "..."` line in the same position (after `audience`, before `desc`, matching existing field order) for all ~240 `[[tool]]` entries. Apply CONTEXT.md's classification rules:

| Category | Default tier |
|---|---|
| `pkg-mgr`, `shell`, `docker`, `runtime` | `system` |
| `ai` | `ai` |
| everything else | `user` |

Named overrides regardless of category (D-05):
- Xcode Command Line Tools → `system`
- `rg` (ripgrep), `bat`, `fd`, `eza`, `sd`, `codegraph`, `graphify`, `rtk` → `ai`
- GUI desktop apps (VS Code, Sublime, iTerm) → `user` (no override needed, category default already gives `user`)

Confirmed via grep: `sdkman` (`installer/registry.toml:1203`, category likely `runtime`) and `java` (`installer/registry.toml:1218`, `requires = ["sdkman"]` at line 1225) are the concrete cross-tier pair named in D-07/success-criterion #3 — `sdkman` should land as `tier = "system"` (runtime-category default) while `java` may default to `tier = "user"` unless RUNTIME's category-default rule (which explicitly includes `RUNTIME`) also classifies `java` as `system`. Per D-04, `Category.RUNTIME` (`installer/enums.py:39`, value `"runtime"`) defaults to `tier="system"` — so both `sdkman` and `java` land on `system` by category default; if the planner wants a genuine cross-tier edge for the resolver proof, verify against `registry.toml` which `requires` edges actually cross a category boundary that maps to different tiers (e.g. an `ai`-tier tool requiring a `system`-tier package manager) rather than assuming sdkman/java differ.

---

### `installer/deps.py` — proof target, NOT to be modified

**No pattern to copy — this is a negative-space requirement.** `resolve_dependencies` (`installer/deps.py:31-137`) walks `tool.requires` (a `tuple[str, ...]` of ids) with no reference anywhere to `tool.priority`, `tool.audience`, or any tier-like field. Confirmed at:
- `installer/deps.py:63` (`for dep_id in tool.requires:`) — transitive closure
- `installer/deps.py:92-93` (`for dep_id in tool.requires`) — blocked-check
- `installer/deps.py:126-128` (`for dep_id in tool.requires: if dep_id in runnable_ids: visit(...)`) — topological sort

Adding `Tool.tier` requires zero edits to this file — `Tool` objects flow through opaquely. Success criterion #3 (java→sdkman, or whichever cross-tier `requires` edge the backfill produces) is proven by an automated test that:
1. Loads two `Tool`s with `requires` linking them, distinct `tier` values.
2. Calls `resolve_dependencies` and asserts the deps-first order is unchanged from pre-tier behavior (i.e., same order as if `tier` didn't exist).
3. Asserts `Resolution.order`/`dragged_in`/`warnings` contain no tier-derived content.

Closest existing test analog to model this proof on: any existing `resolve_dependencies` test exercising `requires` transitivity (search `tests/test_deps.py` or equivalent — not read in this pass, but is the natural home; follow its existing fixture-construction style for `Tool(...)` instances, which will now need a `tier=` kwarg added to every fixture across the test suite since the field is hard-required).

---

### `installer/catalog_tui.py` — reference only, not modified this phase

**Analog for future Phase 2 (informational, do not implement now):** `AUDIENCE_LABEL` (`installer/catalog_tui.py:31`), `_AUDIENCE_STYLE` (`installer/catalog_tui.py:104`), and the `elif view == "audience":` branch (`installer/catalog_tui.py:67-73`) show the exact shape a future `tier`-scoped grouping view would take — a `{EnumMember: str}` label map, a `{EnumMember: style}` map, and a `group_tools` branch filtering `t.audience == a`. CONTEXT.md and ROADMAP explicitly scope this to Phase 2; Phase 1 must not touch `catalog_tui.py`.

## Shared Patterns

### Enum validation (`_parse_enum`)
**Source:** `installer/model.py:32-41`
**Apply to:** `Tool.tier` parsing in `__init__`, reused verbatim, no modification needed. Handles the "value is not the right type" and "value not in enum" error cases already; do not duplicate this logic for `tier`.

### Frozen dataclass construction via `object.__setattr__`
**Source:** `installer/model.py:66-90` (`Tool.__init__`)
**Apply to:** `tier` field assignment must go through the same `object.__setattr__(self, "tier", ...)` call inside `__init__`, not a post-construction mutation (the dataclass is `frozen=True`).

### Hard-required field validation with tool-id context in error message
**Source:** existing precedents in `load_tools` — `installer/model.py:101` (`raise ValueError(f"tool '{row['id']}' declares no install methods")`) and `installer/model.py:107` (unknown method kind)
**Apply to:** the new missing-`tier` check in `load_tools`. Keep the `f"tool '{row['id']}' ..."` message prefix convention consistent with all other row-level errors in this function.

## No Analog Found

None — every piece of Phase 1 work (enum, field, validation, data backfill) has a direct, exact-match analog already in the codebase (`Priority`/`Audience`). The only genuinely new decision is the hard-required-vs-default divergence (D-03), which has no analog to copy and is called out explicitly above.

## Metadata

**Analog search scope:** `installer/enums.py`, `installer/model.py`, `installer/registry.toml`, `installer/deps.py`, `installer/catalog_tui.py`
**Files scanned:** 5 (all named in the mandatory reading list; no additional glob/grep search needed beyond confirming `sdkman`/`java`/`requires` locations in `registry.toml`)
**Pattern extraction date:** 2026-09-04
