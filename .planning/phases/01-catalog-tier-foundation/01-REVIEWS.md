---
phase: 1
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-04T21:34:20Z
plans_reviewed: [01-01-PLAN.md]
models:
  opencode-plan-review: "xai/grok-4.6 (reasoning=high)"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 1

## Consensus Summary

Only one reviewer (`opencode-plan-review`, an OpenCode instance running `xai/grok-4.6`) ran
this cycle, so there is no cross-reviewer consensus to synthesize — no "Agreed Strengths" or
"Agreed Concerns" sections apply. The single review is source-grounded: it opened the plan, the
context/patterns docs, and the actual source files (`installer/enums.py`, `installer/model.py`,
`installer/deps.py`, `installer/registry.toml`, `tests/test_model.py`, `tests/test_deps.py`,
`.claude/architecture.md`) and cited concrete `file:line` evidence for every strength and
concern, rather than restating the plan's own claims. It approved the plan overall (LOW risk)
while flagging four MEDIUM and two LOW implementation-detail gaps — none of which were rated
HIGH.

### Agreed Strengths
Not applicable — single reviewer this cycle.

### Agreed Concerns
Not applicable — single reviewer this cycle.

### Divergent Views
Not applicable — single reviewer this cycle.

---

## OpenCode Review (opencode-plan-review)

I'll verify the plan against the real files it cites, then score completeness and risk.
Plan is inline — I'll confirm the on-disk file and ground every claim against the source.
Plan is on disk. Next I'll read it and check the claims that look most likely to be wrong.
Checking registry counts, fixtures, and the claims the plan treats as facts.

### Review: `.planning/phases/01-catalog-tier-foundation/01-01-PLAN.md`

#### Document Type
GSD · plan

#### Files Read
- `.planning/phases/01-catalog-tier-foundation/01-01-PLAN.md` (357)
- `.planning/phases/01-catalog-tier-foundation/01-CONTEXT.md` (99)
- `.planning/phases/01-catalog-tier-foundation/01-PATTERNS.md` (172)
- `installer/enums.py`, `installer/model.py`, `installer/deps.py`
- `installer/registry.toml` (header + 65 `[[tool]]` entries)
- `tests/test_model.py` (432), `tests/test_deps.py` (124)
- `.claude/architecture.md` (25)

---

#### 1. Summary

The plan is executable and grounded: `Tier` copies `Audience` (`installer/enums.py:15-21`),
`Tool.tier` follows the frozen `__init__` + `_parse_enum` path
(`installer/model.py:32-41,52-90,102,143-146`), and `resolve_dependencies` never reads `.tier`
(`installer/deps.py:63,92-93,126-128`). Independently replaying D-04/D-05 over the live catalog
yields exactly **65 tools, 21/9/35 system/ai/user**, with `uv`/`pnpm`/`brew`/`sdkman` as
`system` and `mmdc→pnpm` as the only cross-tier `requires` edge. Phase goals are met without
resolver/view scope creep. Remaining gaps are test pinning and two autonomous-executor
footguns, not design holes.

#### 2. Strengths

- Corrects CONTEXT/PATTERNS `~240` against the real 65-entry catalog; 21/9/35 is reproducible
  from `registry.toml`.
- Honest about ROADMAP SC#3: `java` and `sdkman` are both `runtime` → `system` (`java`
  `requires = ["sdkman"]`); uses real `mmdc` (`diagram`/`user`) → `pnpm` (`pkg-mgr`/`system`) as
  the cross-tier proof and keeps java→sdkman as same-tier regression.
- D-03 vs constructor default is explicit and justified: `load_tools` hard-fails (`if "tier"
  not in row`), `Tool.__init__(..., tier=Tier.USER)` preserves the 47 `Tool(` call sites in the
  15 named test files.
- Task 1 fixture math matches `tests/test_model.py`: 17 `load_tools` tests, 2 exempt
  (`test_tool_without_methods_raises` at line 96 fires at `model.py:100`;
  `test_load_tools_rejects_unknown_category` at line 208 fires at `model.py:102`), 15 need a
  `tier` line.
- `load_tools(REGISTRY)` count is 42. Zero `deps.py` edits; architecture.md append-only. Threat
  model is proportionate.

#### 3. Concerns

- **MEDIUM — SC#2 not pinned by id.** Acceptance says `uv`/`pnpm`/`brew`/`sdkman` load as
  `system`, but Task 1 only asserts `Counter == {system:21, ai:9, user:35}`. Swapping `uv` to
  `user` and some other tool to `system` still passes. Task 2 pins `pnpm`/`sdkman` only.
- **MEDIUM — throwaway splitter vs comment.** Plan says split on the literal line `[[tool]]`.
  `installer/registry.toml:2` contains the substring "Each [[tool]] declares".
  `text.split("[[tool]]")` yields 66 hits / 65 whole-line headers and would corrupt the
  preamble. Line-based split is required.
- **MEDIUM — `_tool` signature.** Current helper is `def _tool(tool_id: str, *requires: str)`
  (`tests/test_deps.py:12-20`). A non-keyword-only `tier` parameter makes `_tool("mmdc",
  "pnpm")` bind `tier="pnpm"` and breaks every drag-in test. Must be `*requires, tier: str =
  "user"`.
- **MEDIUM — two-row fixture.** `test_tool_requires_defaults_empty_and_parses`
  (`tests/test_model.py:21-36`) has two `[[tool]]` rows. "15 tests" ≠ 15 rows; both `mmdc` and
  `rg` need `tier` or `load_tools` raises on the second.
- **MEDIUM — real-registry proof vs live `available`.** Task 2 says call
  `resolve_dependencies` on real tools. Production availability is OS/arch-filtered; existing
  tests use `_resolve` (`tests/test_deps.py:23-37`) with all catalog ids available. Using live
  `available` makes SC#3 environment-dependent.
- **LOW — "12 pre-existing tests" is 11.** `tests/test_deps.py` has 11 `def test_` functions
  (lines 40–124).
- **LOW — architecture.md is 25 lines, not 26.** Five rules at `.claude/architecture.md:9-24`
  are correct.

#### 4. Suggestions

- Add `assert {t.id: str(t.tier) for t in tools if t.id in {"uv","pnpm","brew","sdkman"}} ==
  {...system}` next to the Counter check.
- Specify the backfill as whole-line `[[tool]]` splits (skip the header comment), and
  `_tool(tool_id, *requires, tier: str = "user")`.
- Route the real-registry case through `_resolve([mmdc], catalog)` / `_resolve([java],
  catalog)` so availability is not live.
- State that every `[[tool]]` row in the 15 tests gets `tier =`, including both rows in
  `test_tool_requires_defaults_empty_and_parses`.

#### 5. Risk Assessment

**LOW.** Scope is a labeled field + data backfill + proof tests; no resolver/UI/executor
changes. Classification table matches the live catalog. Residual risk is autonomous-agent
mis-implementation (substring split, `_tool` arity, unpinned SC#2), not an architectural miss.

#### Status: Approved

---
