---
phase: 01-catalog-tier-foundation
reviewed: 2026-09-04T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - installer/enums.py
  - installer/model.py
  - installer/registry.toml
  - tests/test_model.py
  - tests/test_registry.py
  - tests/test_deps.py
  - .claude/architecture.md
findings:
  critical: 0
  warning: 4
  info: 7
  total: 11
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-09-04
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed commits `007ded0`, `23a1efc`, `8a821eb`, `5fc3ee2` (diff `4053e97..HEAD`) — a
`Tier` StrEnum, a hard-required `Tool.tier` field, a 65-entry `registry.toml` backfill,
seven new tests, and one architecture.md section. This work was produced by an external
cross-AI executor, so every claim in `01-01-SUMMARY.md` was re-derived from the tree rather
than trusted.

**Claims independently verified (all hold):**

- `installer/registry.toml` contains exactly 65 `[[tool]]` headers and exactly 65 top-level
  `tier = ` lines; `tomllib` confirms every one of the 65 tool tables carries `tier` (no line
  leaked into a `[[tool.method]]` sub-table). Diff is `+65 / -0` — no pre-existing line was
  disturbed by the backfill script.
- Distribution is exactly `{'system': 21, 'ai': 9, 'user': 35}`. `uv`, `pnpm`, `brew`, `sdkman`
  all load as `system`. The claimed cross-tier edge is real: `mmdc` (`user`) → `pnpm` (`system`).
- `installer/deps.py` is byte-identical (`git diff 4053e97..HEAD -- installer/deps.py` is empty).
  No file outside the declared 7 (+ the planning SUMMARY) was touched.
- The hard-required check is genuine: `load_tools` raises `ValueError` on a missing `tier`
  (model.py:106-107) and `_parse_enum` raises on an unknown value; there is no
  `row.get("tier", …)` silent-fallback anywhere. `Tool.__init__`'s `Tier.USER` default is
  never reached from `load_tools` (model.py:150 passes `row["tier"]` unconditionally), and
  `load_tools` is the only `Tool(...)` construction site in production code.
- Quality gates re-run on the committed tree: `ruff check` clean, `ruff format --check` clean
  (83 files), `pyright` 0 errors (strict), `vulture` clean, full `pytest --cov` green with
  99.87% coverage against a 90% floor. The `make validate && make test` claim is accurate.

No Critical findings. The defects below are latent type-safety, test-strength, and
data-classification issues that will surface in Phase 2 rather than today.

## Warnings

### WR-01: `Tier.AI` and `Audience.AI` are mutually interchangeable — two "orthogonal" axes now compare equal

**File:** `installer/enums.py:23-28` (with `installer/model.py:91`, `installer/catalog_tui.py:31,104`)

**Issue:** `Tier.AI` and `Audience.AI` are both `StrEnum` members whose value is `"ai"`.
Verified in this interpreter:

```
Tier.AI == Audience.AI          -> True
hash(Tier.AI) == hash(Audience.AI) -> True
{Audience.AI: 1}[Tier.AI]       -> 1
_parse_enum(Tier, Audience.AI, "tier", "x") -> <Tier.AI: 'ai'>
```

Three concrete consequences, none caught by any gate:

1. `_parse_enum` accepts an `Audience` where a `Tier` is expected and vice versa. `Tool.__init__`
   is typed `tier: str | Tier`, and `Audience.AI` is a `str` subclass, so pyright strict passes
   `Tool(..., tier=Audience.AI)` without complaint.
2. `AUDIENCE_LABEL` (catalog_tui.py:31) and `_AUDIENCE_STYLE` (catalog_tui.py:104) are dicts
   keyed by `Audience` members. `AUDIENCE_LABEL[tool.tier]` silently returns `"AI"` for
   ai-tier tools and only `KeyError`s for `system`/`user` — a partial success, the worst kind
   of failure mode for the tier-keyed lookup tables Phase 2 will add right next to these.
3. D-01 declares tier and audience deliberately orthogonal, yet nothing in the code enforces
   that they are not substitutable. This diff introduced the overlap and shipped no guard.

**Fix:** Reject a cross-enum member in the shared parser, and pin the behaviour with a test:

```python
# installer/model.py
from enum import Enum

def _parse_enum(enum_type: type[EnumValue], value: object, field: str, context: str) -> EnumValue:
    if isinstance(value, Enum) and not isinstance(value, enum_type):
        raise ValueError(
            f"{context}: '{field}' must be a {enum_type.__name__}, "
            f"got {type(value).__name__}.{value.name}"
        )
    if not isinstance(value, str):
        raise ValueError(f"{context}: '{field}' must be a string")
    ...
```

```python
# tests/test_model.py
def test_tier_and_audience_are_not_interchangeable() -> None:
    with pytest.raises(ValueError, match="must be a Tier"):
        Tool(id="x", name="x", category="search", cmd="x",
             methods=(Method(kind="brew", params={"formula": "x"}),), tier=Audience.AI)
```

### WR-02: The real-registry resolver proof does not actually prove "resolve_unchanged"

**File:** `tests/test_deps.py:139-152`

**Issue:** `test_real_registry_cross_tier_and_same_tier_requires_edges_resolve_unchanged`
asserts only `"pnpm" in mmdc_result.dragged_in` and `"sdkman" in java_result.dragged_in`. It
never asserts the resulting install order and never asserts `warnings == ()`. The plan's
must_have is explicit — the dependency must be "reported via `Resolution.dragged_in/warnings`"
— and the synthetic sibling test three lines above (`:130-136`) does assert both. As written,
a future tier-aware branch in `deps.py` that reordered the topological output or emitted a
spurious warning on a cross-tier edge would leave this test green, so the durable
registry-backed proof of ROADMAP SC#3 is weaker than its own name claims. Line 147 also
compounds two independent facts into one `assert`, so a failure does not say which tier drifted.

**Fix:**

```python
    assert mmdc.tier == "user"
    assert pnpm.tier == "system"
    assert java.tier == sdkman.tier == "system"

    mmdc_result = _resolve([mmdc], catalog)
    assert "pnpm" in mmdc_result.dragged_in
    order = [t.id for t in mmdc_result.order]
    assert order.index("pnpm") < order.index("mmdc")
    assert mmdc_result.warnings == ()

    java_result = _resolve([java], catalog)
    assert "sdkman" in java_result.dragged_in
    java_order = [t.id for t in java_result.order]
    assert java_order.index("sdkman") < java_order.index("java")
    assert java_result.warnings == ()
```

### WR-03: The `tier=Tier.USER` constructor default is an unguarded hole in the "hard-required" invariant

**File:** `installer/model.py:76`

**Issue:** D-03's guarantee is enforced in exactly one place (`load_tools`, model.py:106-107).
Everywhere else, omitting `tier` produces a silently `user`-tier `Tool` with no error, no
warning, and no failing test. It is inert *today* only because `load_tools` is the sole
production construction site — a fact nothing in the repo pins. Phase 2 adds tier-scoped views;
the moment any code synthesizes or copies a `Tool` (a derived entry for the doctor view, a
`dataclasses.replace`-style rebuild in `uninstall.py`, a stub for an unresolved `requires` id),
it lands in the User view and no gate notices. The plan justified the default with a
test-ergonomics argument ("~40 unrelated call sites"), which permanently weakens a production
invariant to avoid a one-time mechanical test edit.

Measured cost of the alternative: 47 `Tool(` occurrences across 15 test files, but most route
through a single per-file `_tool()` / `_make_tool()` factory, so the real edit surface is closer
to ~15 lines than 47.

**Fix (preferred):** drop the default and add `tier="user"` to the per-file test factories:

```python
# installer/model.py
        audience: str | Audience = Audience.BOTH,
        tier: str | Tier,          # no default — every construction site tags deliberately
        desc: str = "",
```

**Fix (cheap alternative, if the default stays):** pin the invariant the default depends on, so
a future second construction site fails CI rather than silently defaulting:

```python
# tests/test_model.py
def test_load_tools_is_the_only_production_tool_construction_site() -> None:
    sources = Path(__file__).resolve().parent.parent / "installer"
    hits = [p.name for p in sources.glob("*.py") if "Tool(" in p.read_text() and p.name != "model.py"]
    assert hits == [], f"new Tool(...) construction site(s) must pass tier explicitly: {hits}"
```

### WR-04: Backfill applied D-05's override as a hardcoded 5-id list, leaving the catalog internally inconsistent

**File:** `installer/registry.toml` (`jq` :119-122, `yq` :426-429 vs `bat` :194-197, `eza` :298-301)

**Issue:** D-06 requires applying the "agent-optimized CLI replacement → `tier = "ai"`"
*principle* mechanically across the actual registry contents, not a fixed enumeration. The
backfill instead applied exactly `{rg, fd, bat, eza, sd}`. The result contradicts the catalog's
own data:

| tool | `audience` | `desc` framing | `tier` |
|---|---|---|---|
| `rg` | `ai` | "…focused output for agents" | `ai` |
| `fd` | `ai` | "…faster defaults, .gitignore awareness" | `ai` |
| `sd` | `ai` | "…safer literal defaults" | `ai` |
| `jq` | `ai` | "…so **agents** inspect only the fields they need" | **`user`** |
| `yq` | `ai` | "…reducing noisy config inspection" | **`user`** |
| `bat` | `both` | "Replaces cat for code review" | `ai` |
| `eza` | `both` | "Replaces ls…" | `ai` |

Two tools the catalog explicitly marks `audience = "ai"` with agent-framed descriptions land in
the User tier, while two `audience = "both"` tools land in the AI tier. Phase 2 will render this
inconsistency directly to users. Worse, `test_registry_tier_distribution_is_pinned`
(test_registry.py:416-424) now freezes `21/9/35` as a CI tripwire, so correcting `jq`/`yq` later
becomes a two-file change that must also edit a hardcoded constant — the classification error is
now load-bearing.

**Fix:** decide now, before Phase 2 wires the views. Either promote the two outliers and update
the pin in the same commit:

```toml
# jq and yq — audience = "ai", agent-framed desc
tier = "ai"
```
```python
# tests/test_registry.py
    assert dict(Counter(t.tier for t in load_tools(REGISTRY))) == {
        "system": 21, "ai": 11, "user": 33,
    }
```

…or record in `.claude/architecture.md` (or `01-CONTEXT.md`) why `audience = "ai"` does **not**
imply `tier = "ai"`, so the next backfill does not re-litigate it.

## Info

### IN-01: Registry path constant duplicated for the fourth time

**File:** `tests/test_deps.py:140`

**Issue:** `Path(__file__).resolve().parent.parent / "installer" / "registry.toml"` is copied
verbatim from `tests/test_registry.py:9` (`REGISTRY`). Two further copies already exist —
`setup.py:44` (`_REGISTRY`) and `tests/test_node_install_e2e.py:10` (a relative string). A path
change now requires four edits, and the relative-string copy is CWD-dependent.

**Fix:** hoist a single `REGISTRY` fixture/constant into `tests/conftest.py` (or export one from
the `installer` package) and have all four sites use it.

### IN-02: Loop assertion drops the tool id from the failure message

**File:** `tests/test_registry.py:427-430`

**Issue:** The plan specified "asserted per id inside a loop so the failure message names the
offending tool." The implementation omits the assertion message; pytest's rewriting only
surfaces the id indirectly through the `Tool` repr.

**Fix:** `assert tools[tool_id].tier == "system", f"{tool_id} must be system tier"`

### IN-03: `test_registry_tier_distribution_is_pinned` is a churn-generating tripwire with weak signal

**File:** `tests/test_registry.py:416-424`

**Issue:** An aggregate count pin is satisfied by any edit that preserves the totals (add one
`user` tool, drop another), and its prescribed remedy — "bump the number" — does not verify that
the new entry was tagged deliberately, which is the exact guarantee D-03 exists to enforce.
Phases 7 and 8 will both break it mechanically.

**Fix:** keep the pin, but add a structural invariant that stays true as the catalog grows and
actually encodes D-04:

```python
_SYSTEM_CATEGORIES = {"pkg-mgr", "shell", "docker", "runtime"}

def test_bootstrap_categories_are_all_system_tier() -> None:
    for tool in load_tools(REGISTRY):
        if tool.category in _SYSTEM_CATEGORIES:
            assert tool.tier == "system", f"{tool.id} ({tool.category})"
        if tool.category == "ai":
            assert tool.tier == "ai", tool.id
```

### IN-04: `Tool.tier` and the `Tier` members have zero production readers

**File:** `installer/enums.py:23-28`, `installer/model.py:61`

**Issue:** Nothing under `installer/` reads `tool.tier`; `Tier.SYSTEM` and `Tier.AI` are
referenced only from tests. `.claude/architecture.md` rule 5 forbids exactly this shape ("A
shared helper with zero production callers… Only its own test keeping it covered is the tell").
It survives `make validate` only because `[tool.vulture]` is scoped to `paths = ["installer"]`
with `min_confidence = 80`, which does not report unread dataclass attributes. Defensible as a
one-phase seam, but if Phase 2 slips this becomes dead data with a CI tripwire attached to it.

**Fix:** none required now — track that Phase 2 must land, or delete the seam if it does not.

### IN-05: The AI tier will mix agent-consumed CLIs with human-driven assistant CLIs

**File:** `installer/registry.toml` (`aichat`, `codex`, `claude`, `opencode`)

**Issue:** `codex`, `claude`, and `opencode` declare `audience = "human"` but received
`tier = "ai"` via D-04's `Category.AI` default. Phase 2's "AI" view will therefore contain both
"tools an agent runs" (`rg`, `fd`, `bat`, `eza`, `sd`) and "tools a human runs to talk to an
agent" (`claude`, `codex`, `opencode`) — two different meanings of "AI" in one list.

**Fix:** make this an explicit call in the Phase 2 discussion (either split the view, or state
in `.claude/architecture.md` that the AI tier means "AI-related", not "AI-consumed").

### IN-06: `Tool.__init__`'s positional signature changed

**File:** `installer/model.py:76`

**Issue:** `tier` was inserted between `audience` and `desc` in both the dataclass body and
`__init__`. A positional call such as `Tool(id, name, cat, cmd, methods, "P0", "both", "some desc")`
now binds `"some desc"` to `tier`. No in-repo caller is positional (all 47 test sites and
`load_tools` use keywords) and the failure is loud (`ValueError: unknown tier 'some desc'`),
so this is informational only.

**Fix:** consider `def __init__(self, *, id: str, ...)` to make the whole constructor
keyword-only and remove the hazard permanently.

### IN-07: Durable architecture doc hard-codes a GSD phase number

**File:** `.claude/architecture.md:30`

**Issue:** "which top-level catalog view a tool appears under (Phase 2 wires this)" embeds a
planning-artifact reference in a permanent architecture standard. Once Phase 2 ships, is
renumbered, or is dropped, the parenthetical is stale and the reader cannot tell whether the
wiring exists.

**Fix:** drop the phase reference: "…which top-level catalog view a tool appears under."

---

_Reviewed: 2026-09-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
