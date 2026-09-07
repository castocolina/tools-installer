---
phase: 01-catalog-tier-foundation
plan: 01
subsystem: catalog
tags: [tier, registry, StrEnum, load_tools, resolve_dependencies]

requires: []
provides:
  - "Tier StrEnum (system/user/ai) and hard-required Tool.tier on every catalog entry"
  - "65-entry registry.toml backfill (21 system / 9 ai / 35 user)"
  - "CI-pinned proof that uv/pnpm/brew/sdkman are system-tier"
  - "Proof that resolve_dependencies is tier-agnostic across requires edges"
  - "architecture.md lock: tier is a browsing label, requires is the only install order"
affects: [02-tier-scoped-catalog-views]

actuals:
  tokens: 4934
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Hard-required registry field via load_tools presence check, constructor default kept for non-registry Tool(...) callers"
    - "Category-default + named-id override as a one-time data backfill, never computed at load time"

key-files:
  created: []
  modified:
    - installer/enums.py
    - installer/model.py
    - installer/registry.toml
    - tests/test_model.py
    - tests/test_registry.py
    - tests/test_deps.py
    - .claude/architecture.md

key-decisions:
  - "Tool.__init__ defaults tier to Tier.USER so ~40 unrelated Tool(...) test call sites stay unchanged; D-03's hard requirement is enforced in load_tools, not the constructor."
  - "installer/deps.py was not modified; tier flows through the resolver opaquely."

patterns-established:
  - "New catalog enums copy Audience/Priority StrEnum shape and parse through _parse_enum."
  - "Missing required registry keys raise ValueError(f\"tool '{id}': ...\") in load_tools, never silent .get defaults."
  - "Whole-catalog distribution pins live in tests/test_registry.py so a later reclassification fails CI."

requirements-completed:
  - REQ-catalog-tier-field
  - REQ-dependency-chain-requires

coverage:
  - id: D1
    description: "Every registry tool has an explicit valid tier; missing or unknown tier is a hard load_tools ValueError"
    requirement: REQ-catalog-tier-field
    verification:
      - kind: unit
        ref: tests/test_model.py#test_load_tools_rejects_missing_tier
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_load_tools_rejects_unknown_tier
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_tier_parses_to_enum_member
        status: pass
    human_judgment: false
  - id: D2
    description: "uv, pnpm, brew, and sdkman load as system, and the 21/9/35 system/ai/user distribution is CI-pinned"
    requirement: REQ-catalog-tier-field
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_registry_tier_distribution_is_pinned
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_bootstrap_package_managers_are_system_tier
        status: pass
    human_judgment: false
  - id: D3
    description: "Cross-tier and same-tier requires edges resolve identically with zero changes to installer/deps.py"
    requirement: REQ-dependency-chain-requires
    verification:
      - kind: unit
        ref: tests/test_deps.py#test_resolver_drags_in_dependency_across_a_tier_boundary
        status: pass
      - kind: unit
        ref: tests/test_deps.py#test_real_registry_cross_tier_and_same_tier_requires_edges_resolve_unchanged
        status: pass
    human_judgment: false
  - id: D4
    description: "architecture.md states tier is a browsing label and requires is the sole install-order mechanism"
    requirement: REQ-catalog-tier-field
    verification:
      - kind: other
        ref: "grep -n browsing .claude/architecture.md"
        status: pass
    human_judgment: false

duration: 23min
completed: 2026-09-04
status: complete
---

# Phase 1 Plan 1: Catalog Tier Foundation Summary

**Hard-required `Tool.tier` (`system`/`user`/`ai`) on all 65 catalog entries, with `resolve_dependencies` proven tier-agnostic**

## Performance

- **Duration:** 23 min
- **Started:** 2026-09-04T22:20:00Z
- **Completed:** 2026-09-04T22:43:38Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `Tier` StrEnum and a hard-required `Tool.tier` field. `load_tools` rejects a missing or unknown `tier` the same way it rejects a bad priority/audience.
- Backfilled all 65 `installer/registry.toml` entries (21 system / 9 ai / 35 user). `uv`, `pnpm`, `brew`, and `sdkman` are `tier="system"`, pinned by committed tests.
- Proved `installer/deps.py::resolve_dependencies` needs zero new logic: synthetic ai→system and real `mmdc`→`pnpm` (user→system) / `java`→`sdkman` (system→system) edges drag in dependencies as before.
- Documented in `.claude/architecture.md` that tier is a browsing label and `requires` is the only install-order mechanism.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tier enum + hard-required Tool.tier validation + full registry backfill** - `007ded0e8c1b22adbdfdf53012049fcda27d6b13` (feat: add hard-required catalog tier field)
2. **Task 2: Prove resolve_dependencies is tier-agnostic** - `23a1efc4fd71d16bb8cf9c479c9f727c24984adb` (test: prove the requires resolver ignores catalog tier)
3. **Task 3: State tier-is-a-label in architecture.md** - `8a821eb0c8c8169c76c45cb39a00f9f03eda07d4` (docs: state that catalog tier is a browsing label only)

## Success Criteria

All ROADMAP Phase 1 / plan `<success_criteria>` are met:

1. Every one of `installer/registry.toml`'s 65 tools has an explicit, valid `tier`; a missing or unknown `tier` is a hard `load_tools` error (SC#1).
2. `uv`, `pnpm`, `brew`, `sdkman` all load with `tier == "system"`, pinned by `tests/test_registry.py` together with the 21/9/35 distribution (SC#2).
3. The real `mmdc`→`pnpm` cross-tier edge (user→system) and the named `java`→`sdkman` pair (system→system) both resolve identically to pre-tier behavior, with zero changes to `installer/deps.py` (SC#3, REQ-dependency-chain-requires).
4. `.claude/architecture.md` states tier is a browsing label and requires is the sole ordering mechanism (SC#4).
5. `make validate && make test` passed on the committed tree.

## Files Created/Modified

- `installer/enums.py` — `Tier` StrEnum (`system`/`user`/`ai`)
- `installer/model.py` — `Tool.tier` field, `_parse_enum` wiring, hard-required `load_tools` check
- `installer/registry.toml` — `tier = "..."` on all 65 `[[tool]]` entries
- `tests/test_model.py` — missing/unknown/parse tests plus `tier = "user"` on 15 existing fixtures
- `tests/test_registry.py` — pinned 21/9/35 distribution and uv/pnpm/brew/sdkman == system
- `tests/test_deps.py` — keyword-only `_tool(..., tier=)` helper; synthetic and real-registry resolver proofs
- `.claude/architecture.md` — new "Tier is a browsing label" section; five rules unchanged

## Decisions Made

- Followed the plan: constructor default `tier=Tier.USER` for non-registry `Tool(...)` callers; D-03's hard requirement lives in `load_tools` (`if "tier" not in row`).
- No changes to `installer/deps.py`, `installer/catalog_tui.py`, or any executor.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 plan 01 is complete. `Tool.tier` exists on every catalog entry, so Phase 2 can split the flat Catalog view into System/User/AI top-level views without touching the resolver.

---
*Phase: 01-catalog-tier-foundation*
*Completed: 2026-09-04*
