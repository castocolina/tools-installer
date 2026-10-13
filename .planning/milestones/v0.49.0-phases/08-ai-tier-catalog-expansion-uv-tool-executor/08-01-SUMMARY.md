---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
plan: 01
subsystem: catalog
tags: [uv, uv-tool, pypi, executors, resolve, registry, graphify]

requires:
  - phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
    provides: the automated, fail-closed package-legitimacy gate pattern (05-03-PLAN.md Task 1)
provides:
  - a new kind="uv-tool" installer executor, resolvable on every platform at the userspace-install rung
  - graphify's registry entry, the ai-tier catalog's first uv-tool-kind tool
affects: [08-02, 08-03, 08-04]

actuals:
  tokens: 43000
  tasks: 1
  commits: 1

tech-stack:
  added: []
  patterns:
    - "uv-tool executor: bare argv `[\"uv\", \"tool\", \"install\", pypi_pkg]`, no absolute-path resolution needed (unlike node/pnpm) since `uv` carries no guards.py redirect entry"

key-files:
  created: []
  modified:
    - installer/executors.py
    - installer/model.py
    - installer/resolve.py
    - installer/registry.toml
    - tests/test_executors.py
    - tests/test_resolve.py
    - tests/test_model.py
    - tests/test_registry.py
    - tests/test_status.py

key-decisions:
  - "Fixed a real KeyError gap in installer/resolve.py's _applies/_RANK dispatch tables that 08-RESEARCH.md's Architecture Patterns section did not surface: uv-tool was in neither the unconditional-True kind tuple nor _RANK, so the first resolve_methods call against graphify's entry would have raised KeyError from the _NATIVE_OS[kind] fallthrough."
  - "graphifyy's automated [SUS] legitimacy flag (too-new/unknown-downloads heuristic) was discharged with a live, fail-closed check against PyPI + GitHub metadata before the registry entry was written, mirroring 05-03-PLAN.md Task 1's identity-versus-artifact boundary rather than a blocking-human gate."

patterns-established:
  - "uv-tool executor pattern: simpler than node's, no real_pnpm()-style path resolution"

requirements-completed:
  - REQ-uv-tool-executor

coverage:
  - id: D1
    description: "installer/executors.py has a working kind=\"uv-tool\" executor (_uv_tool) registered in EXECUTORS"
    requirement: REQ-uv-tool-executor
    verification:
      - kind: unit
        ref: "tests/test_executors.py#test_uv_tool_executor_builds_uv_tool_install"
        status: pass
      - kind: unit
        ref: "tests/test_executors.py#test_uv_tool_without_pypi_pkg_raises_executor_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "installer/resolve.py's _applies/_RANK correctly resolve any uv-tool method on every platform at the userspace-install rung (rung 20), fixing a real KeyError gap"
    requirement: REQ-uv-tool-executor
    verification:
      - kind: unit
        ref: "tests/test_resolve.py#test_uv_tool_is_userspace_ranked_before_brew"
        status: pass
      - kind: unit
        ref: "tests/test_resolve.py#test_uv_tool_applies_on_every_platform_including_immutable"
        status: pass
    human_judgment: false
  - id: D3
    description: "graphify's registry entry installs via the new uv-tool executor using PyPI package graphifyy, requires=[\"uv\"]"
    requirement: REQ-uv-tool-executor
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_graphify_uses_the_uv_tool_executor_and_requires_uv"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_selecting_graphify_drags_in_uv"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_uv_tool_kind_parses_with_pypi_pkg"
        status: pass
      - kind: unit
        ref: "tests/test_status.py#test_uv_tool_status_is_detected_through_its_cli_shim"
        status: pass
    human_judgment: false
  - id: D4
    description: "graphifyy's [SUS] legitimacy flag discharged with a live, fail-closed check against PyPI + GitHub metadata, recorded verbatim"
    verification:
      - kind: other
        ref: "live curl+python3 check against https://pypi.org/pypi/graphifyy/json and https://api.github.com/repos/Graphify-Labs/graphify, this session -- see Accomplishments below"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-09-06
status: complete
---

# Phase 8 Plan 1: uv-tool Executor + Graphify Summary

**New `kind="uv-tool"` installer executor wired end-to-end through `graphify`'s registry entry, closing a real `KeyError` gap in the resolver dispatch tables found during grounding.**

## Performance

- **Duration:** 55 min
- **Completed:** 2026-09-06
- **Tasks:** 1
- **Files modified:** 9

## Accomplishments

- `installer/executors.py`'s new `_uv_tool(method, runner)` executor: `runner(["uv", "tool", "install", pypi_pkg])`, registered in `EXECUTORS`.
- `installer/model.py`'s `METHOD_KINDS` accepts `"uv-tool"`.
- `installer/resolve.py`'s `_applies` and `_RANK` correctly resolve `uv-tool` methods on every platform at rung 20 (userspace install) — this closes a real defect: without this fix, `resolve_methods` on `graphify`'s entry would raise `KeyError: 'uv-tool'` from `_applies`'s `_NATIVE_OS[kind]` fallthrough, the very first time the catalog rendered or `resolve_dependencies` ran against it.
- `graphify`'s registry entry (`id="graphify"`, `tier="ai"`, `requires=["uv"]`, one `kind="uv-tool"` method with `pypi_pkg="graphifyy"`), placed after `codegraph`, before `deno`.
- **Legitimacy-gate evidence (PART A, recorded verbatim):**
  - PyPI (`https://pypi.org/pypi/graphifyy/json`): `info.name == "graphifyy"`; `project_urls` normalizes to `github.com/Graphify-Labs/graphify`; **223** published releases; earliest `upload_time_iso_8601` across all release files is **2026-04-04T21:58:47.847340Z**; `info.version == "0.9.55"`.
  - GitHub (`https://api.github.com/repos/Graphify-Labs/graphify`): `full_name == "Graphify-Labs/graphify"`; `stargazers_count == 115225`; `created_at == "2026-04-03T15:49:07Z"`.
  - **Disposition:** the automated package-legitimacy seam's `[SUS]` verdict is a `too-new`/`unknown-downloads` false positive — it reads only the latest release's timestamp, and `graphifyy` ships very frequently (223 releases in five months). The package's real age (earliest release April 2026, repo created April 2026 — both well before this session) and real community size (115K+ stars) are the opposite of a fresh look-alike. This gate establishes identity and real age/ownership — the package name resolves to the canonical upstream project, not a fresh or unaffiliated publication. It does NOT establish artifact-level approval of the exact wheel a later `uv tool install graphifyy` will fetch — `graphifyy` ships very frequently, so a later install legitimately resolves to bytes this gate never examined.
- Full Rule-7 same-commit test coverage across `test_executors.py`, `test_resolve.py`, `test_model.py`, `test_registry.py`, `test_status.py`.
- `ai` tier tripwire updated from 10 to 11 (`test_registry_tier_distribution_is_pinned`).
- `make validate && make test`: **1239 passed**, 99.40% coverage, 0 lint/type/security findings.

## Task Commits

1. **Task 1: `uv-tool` executor + resolver wiring, `graphifyy`'s legitimacy gate, and `graphify`'s registry entry** — `9b55e5f` (feat)

## Files Created/Modified
- `installer/executors.py` — new `_uv_tool` executor, registered in `EXECUTORS`
- `installer/model.py` — `"uv-tool"` added to `METHOD_KINDS`
- `installer/resolve.py` — `"uv-tool"` added to `_applies`'s unconditional-True tuple and to `_RANK` (rung 20)
- `installer/registry.toml` — `graphify`'s new `[[tool]]` block + dated comment
- `tests/test_executors.py`, `tests/test_resolve.py`, `tests/test_model.py`, `tests/test_registry.py`, `tests/test_status.py` — new coverage per Rule 7

## Decisions Made

- The `_applies`/`_RANK` `KeyError` gap was found by re-reading `installer/resolve.py`'s actual source during grounding rather than trusting 08-RESEARCH.md's Architecture Patterns diagram alone (which named only `model.py`/`executors.py`) — fixed in this same task/commit since it is on the same wiring path this plan already touches.
- The legitimacy check is an automated, fail-closed gate (not a `gate="blocking-human"` checkpoint), mirroring `05-03-PLAN.md` Task 1's precedent, per ONESHOT-RULES Rules 9/14.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 9/12 — circuit breaker] Direct-execution fallback after 3 consecutive cross-AI backend outages**
- **Found during:** Wave 1 cross-AI dispatch (opencode, model `router-env/my-coding`)
- **Issue:** Three consecutive dispatch attempts all failed identically with `Error: Service temporarily unavailable due to resource pressure. Retry shortly.` (`EXIT_CODE=1`, zero commits each time) — a demonstrated repeated zero-progress tool failure, not a deterministic sandbox wall or a plan defect.
- **Fix:** Per ONESHOT-RULES Rule 9/12's circuit breaker, executed this plan's single task directly in this orchestrator session instead of continuing to retry cross-AI dispatch. No plan content was altered — the task was implemented exactly as `08-01-PLAN.md`'s three cross-AI review cycles left it.
- **Verification:** `make validate && make test` both pass (1239 passed, 99.40% coverage) on the resulting commit.
- **Committed in:** `9b55e5f` (task commit, with the fallback explicitly disclosed in the commit message)

---

**Total deviations:** 1 (execution-channel fallback only; zero content deviation from the reviewed plan)
**Impact on plan:** None on scope or design — the plan's own content was already finalized through three cross-AI review cycles before this task ran.

## Issues Encountered

Cross-AI execution (opencode) was unavailable for this wave due to a transient backend resource-pressure condition (confirmed via 3 identical failures); resolved via the documented direct-execution fallback.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`uv-tool` executor and `graphify` are fully wired and tested; Wave 2 (`08-02-PLAN.md`: `cursor-agent`/`antigravity` script entries) has no dependency on this wave's internals beyond the shared registry file, and can proceed independently.

---
*Phase: 08-ai-tier-catalog-expansion-uv-tool-executor*
*Completed: 2026-09-06*
