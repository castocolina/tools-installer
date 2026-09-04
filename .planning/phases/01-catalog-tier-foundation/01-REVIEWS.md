---
phase: 1
reviewers: [opencode-plan-review]
reviewed_at: 2026-09-04T21:49:44Z
plans_reviewed: [01-01-PLAN.md]
models:
  opencode-plan-review: "xai/grok-4.6 (reasoning=high)"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 1 (Cycle 2)

## Consensus Summary

Only one reviewer (`opencode-plan-review`, an OpenCode instance running `xai/grok-4.6`) ran
this cycle, so there is no cross-reviewer consensus to synthesize — no "Agreed Strengths" or
"Agreed Concerns" sections apply. This is cycle 2, run specifically to verify that the plan was
revised to incorporate cycle 1's 6 actionable findings (SC#2 id-pinning, registry.toml splitter
substring bug, `_tool()` keyword-only tier param, two-row fixture clarification, live-availability
leak in the cross-tier proof, and two corrected factual counts). The reviewer independently
re-derived every factual claim against the live tree (registry counts, fixture counts,
`_parse_enum`/`_tool`/`_resolve` call sites, `.claude/architecture.md` line count) and confirmed
all 6 findings are now incorporated into `01-01-PLAN.md`'s actual task text, not merely asserted.
It raised two new LOW-severity observations (SC#2 pinning lives only in a shell verify, not a
durable pytest; a `re.split` code example in the plan's action text drops delimiters if followed
literally) and no HIGH or MEDIUM findings. Overall risk: LOW.

### Agreed Strengths
Not applicable — single reviewer this cycle.

### Agreed Concerns
Not applicable — single reviewer this cycle.

### Divergent Views
Not applicable — single reviewer this cycle.

---

## OpenCode Review (opencode-plan-review)

I'll verify cycle-1 findings against the current plan text, then check the referenced files so the review is grounded in the repo.
Cycle-1 wording looks updated; next I'll check registry counts, fixtures, and `_parse_enum` against the plan's claims.

### Phase 1 Plan Review — Cycle 2

#### 1. Summary

The revised plan is executable against the current tree and meets Phase 1. Cycle 1's six findings
are in the plan text, not just claimed. The reviewer re-derived the 21/9/35 split from
`installer/registry.toml` (65 tools); `mmdc`→`pnpm` is the only user→system `requires` edge;
`java`→`sdkman` is system→system; `_parse_enum` / `_tool` / `_resolve` / `architecture.md`
(25 lines) / 11 `test_deps.py` tests all match. Residual risk is LOW: leftover nits, not blockers.

#### 2. Cycle-1 Findings Incorporation Check

| # | Finding | Verdict | Evidence |
|---|---------|---------|----------|
| 1 | SC#2 not pinned by id | **INCORPORATED** | Task 1 third `<verify>`: `assert tools['uv'] == 'system'` (and `pnpm`/`brew`/`sdkman`). `fails_when` names "ROADMAP Phase 1 SC#2 pinned by id, not merely inferred from the aggregate Counter". Also in Task 1 `<acceptance_criteria>` and plan `<success_criteria>`. |
| 2 | registry.toml splitter substring bug | **INCORPORATED** | Task 1 `<action>`: split on line-anchored `[[tool]]` (`re.split(r"(?m)^\[\[tool\]\]$")` or stripped line equals `[[tool]]`); "never a bare substring search like `text.split("[[tool]]")`"; cites `installer/registry.toml:2` (`# Each [[tool]] declares…`). Confirmed: bare split yields 67 parts; there are 65 real `[[tool]]` rows plus that comment. |
| 3 | `_tool()` `tier` must be keyword-only | **INCORPORATED** | Task 2 `<behavior>`: `_tool(tool_id: str, *requires: str, tier: str = "user")` with `tier` after `*requires`. Explains that `_tool("mmdc", "pnpm")` at `tests/test_deps.py:12,51` would bind `tier="pnpm"` if `tier` sat before `*requires`. Matches current helper. |
| 4 | Two-row fixture needs two `tier =` lines | **INCORPORATED** | Task 1 `<action>` + `<artifacts_produced>`: `test_tool_requires_defaults_empty_and_parses` has `mmdc` and `rg` (`tests/test_model.py:21-35`); both need `tier =`; 16 insertions across 15 tests. Confirmed: 17 `load_tools` tests, minus `test_tool_without_methods_raises` and `test_load_tools_rejects_unknown_category` = 15. |
| 5 | Live-availability leak in cross-tier proof | **INCORPORATED** | Task 2 `<behavior>`: resolve via `_resolve` (`tests/test_deps.py:23-37`), "never call `resolve_dependencies` directly with a live `available` callable"; default `available_ids is None` makes every loaded id available (`tests/test_deps.py:30`). |
| 6 | Factual counts (11 tests, 25 lines) | **INCORPORATED** | Task 2 `<acceptance_criteria>`: "11 pre-existing tests". Task 3 `<read_first>`: "whole file, 25 lines". Confirmed: 11 `test_*` functions in `tests/test_deps.py`; `.claude/architecture.md` is 25 lines. |

#### 3. Strengths

- **Counts match the tree.** 65 `[[tool]]` entries; category histogram `pkg-mgr=3, shell=4, docker=5, runtime=9` → 21 system; `ai` category (4) + `{rg,fd,bat,eza,sd}` → 9 ai; remainder 35 user. All 65 rows have exactly one `audience =` line (`installer/registry.toml`).
- **Honest SC#3.** ROADMAP still calls `java`→`sdkman` a cross-tier proof; both are `runtime` → `system` under D-04 (`java` `requires = ["sdkman"]`). Plan uses `mmdc` (`diagram`→user, `requires = ["pnpm"]`) → `pnpm` (`pkg-mgr`→system) as the real cross-tier edge and keeps java/sdkman as a same-tier regression.
- **D-03 vs constructor default is justified.** Production `Tool(` exists only in `installer/model.py:137` (`load_tools`). ~47 test `Tool(` sites stay valid if `__init__` defaults `tier`. Hard-required check is `"tier" not in row` in `load_tools`, not the constructor — matches D-03.
- **Validation order is right.** Empty methods (`installer/model.py:100-101`) then category (`:102`) then new tier check: `test_tool_without_methods_raises` and `test_load_tools_rejects_unknown_category` still fail first; the other 15 `load_tools` fixtures need `tier =`.
- **Whole-line split also avoids `[[tool.method]]`.** A bare `split("[[tool]]")` would fragment every method table, not just line 2. The planned `^[[tool]]$` match does not.
- **Resolver proof stays a proof.** `installer/deps.py` has no `.tier` reads (`:63`, `:92-93`, `:126-128`). Task 2 forbids editing it and checks `git diff --stat -- installer/deps.py`.
- **Scope is tight.** No `catalog_tui.py`, no `recommends`, no new resolver branches. Phase 2 can consume `Tool.tier`.

#### 4. Concerns

- **LOW — SC#2 / 21-9-35 live only in Task 1 shell verifies, not pytest.** `uv run python3 -c "… assert tools['uv'] == 'system' …"` and the Counter assert run during execution; they are not added to `tests/test_registry.py` (42 `load_tools(REGISTRY)` sites). A later catalog edit can reclassify `uv`/`pnpm`/`brew`/`sdkman` and CI will not catch it. Missing `tier` still fails those 42 loads; wrong `tier` does not.
- **LOW — `re.split` example drops delimiters.** `re.split(r"(?m)^\[\[tool\]\]$", text)` yields preamble + 65 bodies **without** `[[tool]]` headers (join-back required; skip `parts[0]`). The line-iteration alternative in the same paragraph is safer. Not a logic error if the executor join-backs correctly.

No HIGH or MEDIUM findings on this cycle.

#### 5. Suggestions

- Add one `test_registry.py` test: distribution `{'system': 21, 'ai': 9, 'user': 35}` and `uv`/`pnpm`/`brew`/`sdkman` → `system`. That is the durable form of cycle-1 finding 1.
- Prefer the line-iteration splitter only; drop the `re.split` example, or use a capturing split and skip the preamble.
- Keep the synthetic cross-tier test as the durable SC#3 proof. Phase 5 may retarget `mmdc`'s `requires` (ROADMAP Phase 5 / `REQ-mmdc-install-decision`); the real-registry test will need a new edge then.

#### 6. Risk Assessment

**LOW.** Cycle-1 gaps are closed in the plan text. Independent checks against `installer/model.py`, `installer/deps.py`, `installer/registry.toml`, `tests/test_model.py`, `tests/test_deps.py`, and `.claude/architecture.md` support the mechanism. Remaining items are persistence of SC#2 in pytest and backfill-script hygiene — neither blocks execution or the phase goal.

#### Status: Approved

---
