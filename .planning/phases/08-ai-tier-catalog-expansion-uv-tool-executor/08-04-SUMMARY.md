---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
plan: 04
subsystem: catalog
tags: [recommends, registry, docker, tier-3-verification, project-consolidation]

requires:
  - phase: 08-ai-tier-catalog-expansion-uv-tool-executor
    provides: "08-01's graphify, 08-02's cursor-agent/antigravity, 08-03's rtk -- all four real catalog tools this plan's recommends wiring depends on"
provides:
  - real per-host recommends data on claude/opencode/codex/cursor-agent
  - Tier-3 disposable-container proof that graphify (uv-tool) and rtk (github_release) install and run through the real production install_tool path
  - Phase 8's four-row Key Decisions consolidation in PROJECT.md
affects: [09]

actuals:
  tokens: 31000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py
    - tests/test_catalog_tui.py
    - .planning/PROJECT.md

key-decisions:
  - "recommends wiring across claude/opencode/codex/cursor-agent is the honest RESULT of per-host verification (D-01), not a uniform default applied blindly -- rtk's weaker instructions-based Codex integration is recorded in the comment rather than smoothed over."
  - "antigravity stays unwired (no recommends field) per D-01 -- deferred, not dropped, until its own companion-tool ecosystem is researched."
  - "Tier-3 verification routes through installer.engine.install_tool (the real production entry point app.py uses), not through _uv_tool/install_download directly -- proves the catalog-to-production path, not merely equivalent primitives."

patterns-established: []

requirements-completed:
  - REQ-recommends-wiring-agent-hosts

coverage:
  - id: D1
    description: "claude, opencode, codex, and cursor-agent each declare recommends == (\"codegraph\", \"graphify\", \"rtk\"); antigravity remains unwired"
    requirement: REQ-recommends-wiring-agent-hosts
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_agent_host_recommends_match_the_researched_per_host_set"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_agent_hosts_recommend_existing_catalog_tools"
        status: pass
    human_judgment: false
  - id: D2
    description: "each host's recommends comment records the per-host rationale, and codex's specifically records the rtk instructions-based Codex caveat"
    requirement: REQ-recommends-wiring-agent-hosts
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_agent_host_recommends_entries_record_the_rtk_codex_caveat"
        status: pass
    human_judgment: false
  - id: D3
    description: "graphify (uv-tool) and rtk (github_release) install and run a working binary end-to-end through the real installer.engine.install_tool production path in a real disposable python:3.13-slim container"
    verification:
      - kind: other
        ref: "docker run --rm python:3.13-slim, this session -- GRAPHIFY_OUTCOME installed uv-tool False, graphify --version -> graphify 0.9.55; RTK_TAG rtk-ai/rtk v0.48.0, RTK_OUTCOME installed github_release True, rtk --version -> rtk 0.48.0"
        status: pass
    human_judgment: false
  - id: D4
    description: "PROJECT.md's Key Decisions table records all four of Phase 8's decisions, footer updated"
    verification:
      - kind: other
        ref: "grep -cE '\\| Phase 8 \\|$' .planning/PROJECT.md == 4; grep -Eq '^\\*Last updated:.*Phase 8' .planning/PROJECT.md"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-09-06
status: complete
---

# Phase 8 Plan 4: recommends Wiring + Tier-3 Verification + Phase Close-out Summary

**Real per-host `recommends` data (`codegraph`, `graphify`, `rtk`) wired onto `claude`/`opencode`/`codex`/`cursor-agent`; both of this phase's new install mechanisms proven end-to-end in a real disposable container through the actual production `install_tool` path; Phase 8 closed out with a four-decision `PROJECT.md` consolidation.**

## Performance

- **Duration:** 40 min
- **Completed:** 2026-09-06
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

**Task 1 — recommends wiring:**
- `claude`'s and `opencode`'s Phase 2 illustrative placeholder (`recommends = ["rg", "fd", "jq"]`) fully retired; `codex` and `cursor-agent` gained the identical real companion set for the first time. All four hosts: `recommends = ["codegraph", "graphify", "rtk"]`.
- `antigravity` remains unwired (no `recommends` field), per CONTEXT.md D-01.
- Each host's dated comment records the per-host rationale (`codegraph`: MCP server, host-agnostic; `graphify`: explicit README support for all four hosts; `rtk`: native hook for three hosts, instructions-based for `codex`).
- New tests: `test_agent_host_recommends_match_the_researched_per_host_set` (exact-membership pin) and `test_agent_host_recommends_entries_record_the_rtk_codex_caveat` (comment-locality + the specific caveat phrase in `codex`'s window). Extended `test_agent_hosts_recommend_existing_catalog_tools` to all four real hosts.
- Fixed the now-stale `test_cursor_agent_uses_the_legacy_collision_safe_cmd_name`'s `recommends == ()` assertion and `tests/test_catalog_tui.py`'s hardcoded pre-Phase-8 recommends text/staged-set.

**Task 2 — Tier-3 disposable-container verification (real, not simulated):**
Ran the plan's exact `docker run --rm python:3.13-slim bash -c '...'` recipe against a real container, exercising `installer.engine.install_tool` — the actual production entry point — for both of this phase's genuinely new install mechanisms:
```
GRAPHIFY_OUTCOME installed uv-tool False
graphify --version -> graphify 0.9.55
RTK_TAG rtk-ai/rtk v0.48.0
RTK_OUTCOME installed github_release True
rtk --version -> rtk 0.48.0
```
Both `install_tool` calls returned `status == "installed"` with the expected `method_kind`; `rtk`'s `verified` flag was `True` (checksum-verified); both installed binaries ran and reported their real versions. This closes cross-AI review's HIGH finding (cycle 1) that the phase close-out lacked ONESHOT Rule 14's required Tier-3 evidence, and cycle 2/3's follow-up findings that the recipe bypassed the real production path and couldn't capture the resolved RTK tag.

**Task 3 — Phase close-out consolidation:**
- `.planning/PROJECT.md`'s Key Decisions table gained exactly 4 new rows (all `Outcome = Phase 8`), covering: the `resolve.py` `KeyError` fix, `graphifyy`'s legitimacy-gate discharge, `cursor-agent`'s collision-safe `cmd`, and `rtk`'s arch-gated split + honest `recommends` wiring.
- Footer bumped to `*Last updated: 2026-09-06 after Phase 8 AI tier catalog expansion & uv-tool executor (08-01..08-04)*`.

- `make validate && make test`: **1250 passed**, 99.40% coverage, 0 lint/type/security findings — the full cross-plan test surface (`test_executors.py`, `test_resolve.py`, `test_model.py`, `test_registry.py`) is green.
- **Final `ai` tier count: 14** (`codex`, `claude`, `opencode`, `cursor-agent`, `antigravity`, `codegraph`, `graphify`, `rtk`, plus 6 pre-existing).

## Requirements Satisfied (Phase 8, all four)

- **REQ-uv-tool-executor** — 08-01: `_uv_tool` executor, `resolve.py`'s `KeyError` fix, `graphify`'s entry.
- **REQ-agent-host-entries** — 08-02: `cursor-agent`/`antigravity` entries.
- **REQ-rtk-github-release** — 08-03: `rtk`'s checksum-verified, arch-gated `github_release` ladder.
- **REQ-recommends-wiring-agent-hosts** — this plan: real per-host `recommends` data.

## Task Commits

1. **Task 1: Wire the real per-host `recommends` data** — `bbaf5d1` (feat)
2. **Task 2: Tier-3 verification** — no commit (verification-only, evidence recorded above per the plan's own acceptance criteria)
3. **Task 3: Consolidate Phase 8's decisions into `PROJECT.md`** — `c974894` (docs)

## Files Created/Modified
- `installer/registry.toml` — `recommends` field + comment on `codex`/`claude`/`opencode`/`cursor-agent`
- `tests/test_registry.py` — new exact-membership and caveat-locality tests, extended host-loop test, fixed stale `cursor-agent` assertion
- `tests/test_catalog_tui.py` — fixed stale hardcoded recommends text/staged-set
- `.planning/PROJECT.md` — 4 new Key Decisions rows + footer bump

## Decisions Made

- The uniform `recommends` outcome across all four hosts is the honest result of D-01's per-host verification directive, not a shortcut around it — `rtk`'s one real asymmetry (weaker Codex integration) is recorded rather than smoothed over.
- Tier-3 verification goes through `installer.engine.install_tool`, not lower-level primitives, to prove the actual catalog-to-production path `app.py` uses.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 9/12 — circuit breaker] Direct-execution fallback continuing the systemic cross-AI backend outage**
- **Found during:** Wave 4 (no cross-AI dispatch attempted — the systemic outage was already confirmed across all three prior waves)
- **Issue:** Same `Error: Service temporarily unavailable due to resource pressure` pattern observed throughout this phase.
- **Fix:** Executed all three of this plan's tasks directly in this orchestrator session, including the real Docker Tier-3 verification. No plan content was altered.
- **Verification:** `make validate && make test` both pass (1250 passed, 99.40% coverage); Tier-3 container run succeeded with all assertions passing (no `AssertionError`, `set -eux` would have aborted on any failure).
- **Committed in:** `bbaf5d1`, `c974894` (Tier-3 verification is evidence-only, folded into this SUMMARY per the plan's own acceptance criteria allowing no separate commit)

---

**Total deviations:** 1 (execution-channel fallback only, consistent with all four waves this phase; zero content deviation from the reviewed plans)
**Impact on plan:** None — every plan's content was already finalized through three cross-AI review cycles before execution.

## Issues Encountered

Cross-AI execution (opencode) remained unavailable throughout Phase 8 (systemic backend outage, confirmed across all four waves); resolved via the documented direct-execution fallback each time.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Phase 8 is fully complete: all four REQs satisfied, all four plans' `make validate && make test` green, Tier-3 evidence recorded for both new install mechanisms, `PROJECT.md` consolidated. Ready to proceed to Phase 9.

---
*Phase: 08-ai-tier-catalog-expansion-uv-tool-executor*
*Completed: 2026-09-06*
