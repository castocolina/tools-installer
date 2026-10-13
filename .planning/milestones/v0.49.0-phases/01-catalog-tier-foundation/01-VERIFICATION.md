---
phase: 01-catalog-tier-foundation
verified: 2026-09-04T23:06:56Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
---

# Phase 1: Catalog Tier Foundation Verification Report

**Phase Goal:** Every catalog tool is labeled system/user/ai, and the existing dependency resolver is proven to carry that labeling across tier boundaries without any new ordering logic.
**Verified:** 2026-09-04T23:06:56Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Truths are the merged set of ROADMAP Phase 1 Success Criteria #1-#4 and the PLAN
frontmatter `must_haves.truths` (identical scope — the plan neither reduced nor
extended the roadmap contract).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every tool in `installer/registry.toml` has an explicit, valid `tier`; a missing/unknown tier raises the same class of `load_tools` ValueError as an unrecognized priority/audience (SC#1, REQ-catalog-tier-field) | ✓ VERIFIED | 65/65 `[[tool]]` headers, 65/65 `^tier = ` lines; `load_tools` returns 65 Tools. Direct behavioral run: missing → `ValueError: tool 'demo': missing required 'tier'`; `tier="cloud"` → `ValueError: tool 'demo': unknown tier 'cloud' (expected one of: system, user, ai)` (same `_parse_enum` path as priority/audience); `tier="system"` → `<Tier.SYSTEM: 'system'>`. Enforcement is `installer/model.py:106-107` (`if "tier" not in row: raise`) + `model.py:91` `_parse_enum(Tier, ...)`. Named tests `test_load_tools_rejects_missing_tier`, `test_load_tools_rejects_unknown_tier`, `test_tier_parses_to_enum_member` each run green individually. |
| 2 | `uv`, `pnpm`, `brew`, `sdkman` each load with `tier == "system"`, asserted by a committed pytest alongside the 21/9/35 distribution so a later reclassification fails CI (SC#2) | ✓ VERIFIED | Live load: `uv/pnpm/brew/sdkman → system`; `Counter = {'system': 21, 'ai': 9, 'user': 35}` over 65 tools. Committed, CI-enforced form present at `tests/test_registry.py:416-431` (`test_registry_tier_distribution_is_pinned`, `test_bootstrap_package_managers_are_system_tier`); both run green as individually named tests. Not a one-off shell check. |
| 3 | A `requires` edge crossing a tier boundary still auto-drags-in its dependency and reports it via `Resolution.dragged_in`/`warnings`, with zero new branches in `installer/deps.py`; the named `java`→`sdkman` pair (both `system` by the D-04 category default) resolves identically (SC#3, REQ-dependency-chain-requires) | ✓ VERIFIED (behavioral) | `git diff 4053e97..HEAD -- installer/deps.py` is empty; `grep -n "tier" installer/deps.py` exits 1 (zero occurrences anywhere in the module). Directly executed against the real registry: `mmdc` (user) → `dragged_in=('pnpm',)`, `order=['pnpm','mmdc']`, `warnings=()` with `pnpm.tier == system` — a genuine user→system cross-tier edge; `java` (system) → `dragged_in=('sdkman',)`, `order=['sdkman','java']`, `warnings=()`. Committed proofs: synthetic registry-independent `test_resolver_drags_in_dependency_across_a_tier_boundary` (ai→system, asserts drag-in **and** order **and** `warnings == ()`) and `test_real_registry_cross_tier_and_same_tier_requires_edges_resolve_unchanged`; both run green individually. |
| 4 | `.claude/architecture.md` states plainly that tier is a browsing label and `requires`/`resolve_dependencies` is the only mechanism determining install order (SC#4) | ✓ VERIFIED | `.claude/architecture.md:27-34` — new "## Tier is a browsing label" section states the label role, names `installer/deps.py::resolve_dependencies` as "the sole mechanism that determines install order", and that a cross-tier edge drags in exactly like a same-tier one with "no tier-aware branching". The five numbered rules are byte-identical (diff is +9 lines appended, 0 deletions). |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/enums.py` | `Tier` StrEnum with exactly SYSTEM/USER/AI | ✓ VERIFIED | Lines 23-28, placed after `Audience`, before `Category`; values `system`/`user`/`ai` per D-02. Imported and used by `model.py`. |
| `installer/model.py` | `Tool.tier` field + `_parse_enum` wiring + hard-required `load_tools` check | ✓ VERIFIED | `EnumValue` TypeVar extended (L25), field declared (L61), `__init__` param (L76), `_parse_enum` assignment (L91), presence check (L106-107), `tier=row["tier"]` — no `row.get("tier", ...)` fallback anywhere (grep confirms). |
| `installer/registry.toml` | 65 entries tagged, 21/9/35 | ✓ VERIFIED | `git diff --numstat` = `65 0` — pure insertions, zero deletions; every inserted line matches `^tier = "`. All 65 sit immediately after their block's `audience = ` line. 65 `^[[tool]]$` headers intact (delimiter-loss guard passes). |
| `tests/test_model.py` | 3 new tier tests + 16 fixture lines | ✓ VERIFIED | 3 new tests present and green; 16 `tier = "user"` fixture insertions across 15 tests (incl. both rows of `test_tool_requires_defaults_empty_and_parses`); `test_tool_without_methods_raises` and `test_load_tools_rejects_unknown_category` correctly left untouched. 27 tests collected. |
| `tests/test_registry.py` | 2 new pinning tests + `Counter` import | ✓ VERIFIED | `from collections import Counter` (L1); both tests added beside `test_registry_has_unique_tools_and_cmds`; the unrelated `test_script_installer_tier_resolves_script_then_brew` untouched. 54 tests collected. |
| `tests/test_deps.py` | keyword-only `tier` kwarg + 2 resolver proofs | ✓ VERIFIED | `_tool(tool_id: str, *requires: str, tier: str = "user")` — `tier` after `*requires`, so keyword-only; all 11 pre-existing tests still pass (13 collected total). |
| `.claude/architecture.md` | tier-is-a-label statement | ✓ VERIFIED | See truth 4. |
| `installer/deps.py` | **unchanged** (negative artifact) | ✓ VERIFIED | Zero diff across the phase's three commits; zero `tier` references. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `registry.toml` `tier = "..."` | `Tool.tier` | `load_tools` row parsing → `Tool(tier=row["tier"])` → `_parse_enum(Tier, ...)` | ✓ WIRED | End-to-end confirmed by loading the real registry: values arrive as `Tier` enum members (`<Tier.SYSTEM: 'system'>`), not raw strings. |
| `Tool.tier` | `installer/deps.py::resolve_dependencies` | flows opaquely; module never reads `.tier` | ✓ WIRED (by absence, as intended) | `grep "tier" installer/deps.py` → no matches. Cross-tier and same-tier edges resolve with identical `dragged_in`/`order`/`warnings` shape. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `Tool.tier` | `row["tier"]` | `tomllib.load(registry.toml)` — real file parse, no default/literal fallback | Yes (65 real values, 3 distinct) | ✓ FLOWING |
| `Resolution.dragged_in` | `resolve_dependencies` transitive closure over real catalog | real `load_tools(REGISTRY)` output | Yes (`('pnpm',)`, `('sdkman',)`) | ✓ FLOWING |

No UI consumer exists yet by design (Phase 2 owns tier-scoped views), so there is no render-path leg to trace.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full targeted suite | `uv run python -m pytest tests/test_model.py tests/test_registry.py tests/test_deps.py -q` | 94 passed, exit 0 | ✓ PASS |
| Tier distribution | `Counter(str(t.tier) for t in load_tools(...))` | `{'system': 21, 'ai': 9, 'user': 35}`, 65 tools | ✓ PASS |
| SC#2 ids | live `load_tools` by id | uv/pnpm/brew/sdkman all `system` | ✓ PASS |
| Missing tier rejected | `load_tools` on synthetic row without `tier` | `ValueError: tool 'demo': missing required 'tier'` | ✓ PASS |
| Unknown tier rejected | `load_tools` on `tier = "cloud"` | `ValueError: ... unknown tier 'cloud' (expected one of: system, user, ai)` | ✓ PASS |
| Cross-tier drag-in (real registry) | `resolve_dependencies([mmdc], catalog, ...)` | `dragged_in=('pnpm',)`, `order=['pnpm','mmdc']`, `warnings=()` | ✓ PASS |
| Same-tier drag-in (java→sdkman) | `resolve_dependencies([java], catalog, ...)` | `dragged_in=('sdkman',)`, `order=['sdkman','java']`, `warnings=()` | ✓ PASS |
| Delimiter-loss guard | `grep -v '^#' registry.toml \| grep -c '^\[\[tool\]\]$'` | 65 | ✓ PASS |
| Named tests exist and pass individually | 7 × `pytest tests/ -k <name>` | each: 1 passed | ✓ PASS |
| Quality gate | `make validate` | exit 0 — ruff, ruff format (83 files), pyright 0 errors, bandit, vulture, shellcheck | ✓ PASS |
| Full suite + coverage floor | `make test` | 696 passed, coverage 99.87% (floor 90%), exit 0 | ✓ PASS |

### Probe Execution

Not applicable — this repo declares no `scripts/*/tests/probe-*.sh`, and neither the PLAN nor the SUMMARY references probes or stage markers. Verification used the plan's own `<verification>` block instead, run in this process.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REQ-catalog-tier-field | 01-01-PLAN.md | Every registry tool declares `tier` on `Tool` + `registry.toml` schema, validated like an unknown `Priority`; uv/pnpm/brew/sdkman migrate to `tier="system"` | ✓ SATISFIED | Truths 1, 2, 4; `Tier` enum + `Tool.tier` + `load_tools` hard check + 65-entry backfill + CI-pinned SC#2 ids |
| REQ-dependency-chain-requires | 01-01-PLAN.md | Cross-tier `requires` chains resolve via the existing resolver with zero new resolver logic, demonstrated end-to-end | ✓ SATISFIED | Truth 3; `installer/deps.py` zero-diff and zero `tier` references; synthetic + real-registry proofs green; live resolution reproduced in this verification |

**Orphan check:** `.planning/REQUIREMENTS.md`'s traceability table maps exactly two IDs to Phase 1 (lines 116-117), both declared in the PLAN frontmatter. **No orphaned requirements.**

Note (informational, not a gap): both rows still read `Pending` in the REQUIREMENTS.md traceability table. Status flips are conventionally applied at ship time, not by the executor.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | none | — | `grep -nE "TODO\|FIXME\|XXX\|TBD\|HACK\|PLACEHOLDER\|not yet implemented"` across `installer/enums.py`, `installer/model.py`, `tests/test_deps.py`, `tests/test_registry.py`, `.claude/architecture.md` → exit 1 (no matches). No stub returns, no hardcoded-empty data, no debt markers in any file this phase touched. |

### Non-Blocking Observations

These are carried forward from `01-REVIEW.md` (0 Critical, 4 Warning) and independently confirmed against the committed tree. None falsifies a Phase 1 must-have; all are recorded so Phase 2 planning inherits them.

1. **WR-01 — `Tier.AI == Audience.AI` (confirmed).** Both are `StrEnum` members valued `"ai"`, so they compare and hash equal and `_parse_enum(Tier, Audience.AI, ...)` silently succeeds. Inert today because nothing consumes `Tool.tier` yet; Phase 2 introduces tier-scoped views alongside the existing `AUDIENCE_LABEL` grouping, which is exactly where a mixed-up axis would become a real defect.
2. **WR-02 — real-registry resolver proof is weaker than its name (confirmed).** `test_real_registry_cross_tier_and_same_tier_requires_edges_resolve_unchanged` (`tests/test_deps.py:139-152`) asserts only membership in `dragged_in`; it does not assert `order` or `warnings == ()`. The must-have is still satisfied because the synthetic sibling `test_resolver_drags_in_dependency_across_a_tier_boundary` pins drag-in, order, and warnings across an ai→system edge — and I reproduced the full ordering behavior on the real registry during this verification. The gap is durability: a future tier-aware reordering in `deps.py` would leave the real-registry test green.
3. **WR-03 — `tier: str | Tier = Tier.USER` constructor default (confirmed, deliberate).** D-03's hard requirement lives only in `load_tools`; any direct `Tool(...)` construction that omits `tier` silently lands in `user`. The plan and SUMMARY both record this as an intentional trade for ~40 unrelated test call sites, and the must-have truth is scoped to registry entries — so this is not a Phase 1 failure. It becomes load-bearing the moment Phase 2 code synthesizes or rebuilds a `Tool`.
4. **WR-04 — D-05 override applied as a fixed 5-id list (confirmed).** Exactly `{rg, fd, bat, eza, sd}` deviate from the D-04 category default; every other tool matches its category default precisely. `jq` and `yq` carry `audience = "ai"` but `tier = "user"`, which reads inconsistently against D-06's "apply the principle, not an enumeration". The plan specified the fixed set explicitly, so the executor followed instructions; this is a catalog-judgment question for Phase 2/7/8, not an implementation defect.
5. **Durability of the real cross-tier edge (informational).** The only genuine cross-tier `requires` edge in the catalog is `mmdc`→`pnpm`, and ROADMAP Phase 5 (REQ-mmdc-install-decision) may retarget `mmdc.requires` to `puppeteer`. The registry-independent synthetic test keeps SC#3 provable if that happens — the plan considered this in review cycle 2 and it holds as designed.
6. **ROADMAP SC#3's parenthetical "primary proof case" is not actually cross-tier.** `java` and `sdkman` both land on `system` under the D-04 category default, so that pair is a same-tier regression check. The literal criterion ("a dependent whose `requires` crosses a tier boundary") is satisfied by `mmdc`→`pnpm` (user→system), which SC#3 itself lists as an example. The plan surfaced this discrepancy explicitly rather than papering over it, and the committed test asserts both tier facts by name. No gap.

### Gaps Summary

None. All four ROADMAP success criteria and all four PLAN `must_haves.truths` are independently reproducible on the committed tree — not merely claimed in the SUMMARY. Both declared requirement IDs are satisfied and no requirement mapped to Phase 1 is unclaimed. `make validate` and `make test` both pass on the exact committed code (696 tests, 99.87% coverage). `installer/deps.py` is provably untouched and tier-free, which is the load-bearing negative claim of this phase.

The SUMMARY's claims were checked one by one and all held, including the ones easiest to overstate: the "65-entry backfill" is a pure 65-insertion / 0-deletion diff, the "CI-pinned" tests are real committed pytests that fail on reclassification (not shell one-offs), and "zero changes to deps.py" is an empty diff rather than a small one.

---

_Verified: 2026-09-04T23:06:56Z_
_Verifier: Claude (gsd-verifier)_
