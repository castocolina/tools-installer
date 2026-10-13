---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
plan: 02
subsystem: catalog
tags: [registry, cursor-agent, antigravity, script-kind, agent-hosts]

requires:
  - phase: 08-ai-tier-catalog-expansion-uv-tool-executor
    provides: "08-01's uv-tool executor and ai-tier tripwire baseline (11)"
provides:
  - cursor-agent and antigravity as verified tier="ai" catalog entries
affects: [08-04]

actuals:
  tokens: 21000
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "cursor-agent's cmd is the legacy-but-real \"cursor-agent\" symlink name, not the newer \"agent\" primary name -- avoids a real collision risk with an unrelated agent binary on a machine with more than one agent tool (08-RESEARCH.md Pitfall 3)."
  - "Neither entry declares a kind=\"cask\" fallback -- each vendor's only Homebrew artifact installs the GUI IDE app, a different product from the terminal CLI (confirmed live via formulae.brew.sh's cask API)."
  - "antigravity does not join test_human_agent_clis_are_p0_human_tools or test_agent_clis_use_supported_install_methods (it is P1, and has no cask counterpart to assert against) -- only cursor-agent's shape genuinely matches those tests' assertions."

patterns-established: []

requirements-completed:
  - REQ-agent-host-entries

coverage:
  - id: D1
    description: "cursor-agent appears as a tier=\"ai\" catalog entry, installs via its live-fetched official vendor script, cmd uses the collision-safe legacy name"
    requirement: REQ-agent-host-entries
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_cursor_agent_uses_the_legacy_collision_safe_cmd_name"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_human_agent_clis_are_p0_human_tools"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_agent_clis_use_supported_install_methods"
        status: pass
    human_judgment: false
  - id: D2
    description: "antigravity appears as a tier=\"ai\" catalog entry, installs via its live-fetched official vendor script, no recommends declared"
    requirement: REQ-agent-host-entries
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_antigravity_installs_via_official_script_with_no_recommends"
        status: pass
    human_judgment: false
  - id: D3
    description: "both entries' script method resolves on every supported (os, arch) platform"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_cursor_agent_and_antigravity_scripts_resolve_on_every_platform"
        status: pass
    human_judgment: false
  - id: D4
    description: "both entries' dated comments record the GUI-cask-is-a-different-product finding and antigravity's SHA-512 self-verification"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_cursor_agent_and_antigravity_entries_record_the_verification_findings"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-09-06
status: complete
---

# Phase 8 Plan 2: cursor-agent and antigravity Summary

**`cursor-agent` (P0, collision-safe `cmd`) and `antigravity` (P1) added as verified `tier="ai"` catalog entries, each installing via its own live-fetched official vendor script.**

## Performance

- **Duration:** 20 min
- **Completed:** 2026-09-06
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `cursor-agent`: `id="cursor-agent"`, `category="ai"`, `cmd="cursor-agent"`, `priority="P0"`, `audience="human"`, `tier="ai"`, one `kind="script"` method with `url="https://cursor.com/install"`, `shell="bash"`. `cmd` deliberately uses the script's "legacy" symlink name rather than its newer `"agent"` primary name, avoiding a real collision risk with an unrelated `agent` binary on a multi-agent-tool machine.
- `antigravity`: `id="antigravity"`, `category="ai"`, `cmd="agy"`, `priority="P1"`, `audience="human"`, `tier="ai"`, one `kind="script"` method with `url="https://antigravity.google/cli/install.sh"`, `shell="bash"`. No `recommends` field (deferred per CONTEXT.md D-01).
- Both entries' dated comments record the live-fetched script findings verbatim: `cursor-agent`'s dual-symlink behavior and the GUI-cask-is-a-different-product finding; `antigravity`'s SHA-512 self-verification against a signed manifest and its no-op-if-already-installed behavior.
- `test_human_agent_clis_are_p0_human_tools` and `test_agent_clis_use_supported_install_methods` extended to cover `cursor-agent` (not `antigravity` — P1, no cask counterpart).
- `test_registry_includes_requested_installable_entries`'s floor-check set extended with `cursor-agent`/`antigravity`.
- Four new tests: entry-shape pins for both tools, universal-platform resolution, and comment-substring locality checks.
- `ai` tier tripwire updated from 11 to 13.
- `make validate && make test`: **1243 passed** (up from 1239), 99.40% coverage, 0 lint/type/security findings.

## Task Commits

1. **Task 1: `cursor-agent` and `antigravity` registry entries** + **Task 2: Extend the agent-CLI shape tests and the installable-entries floor check** — `79df050` (feat, single commit — both tasks landed together since Task 2 only extends tests Task 1 already made pass)

## Files Created/Modified
- `installer/registry.toml` — `cursor-agent` and `antigravity` `[[tool]]` blocks + dated comments
- `tests/test_registry.py` — new entry-shape/resolution/comment tests, extended existing agent-CLI shape tests, extended floor check, tier tripwire bump

## Decisions Made

- `cursor-agent`'s `cmd` uses the legacy-but-real symlink name, not the newer one — matches every existing reference to this tool in CONTEXT.md/ROADMAP/REQUIREMENTS.md, not a new naming decision.
- Neither entry declares a `kind="cask"` fallback — each vendor's only Homebrew artifact installs a different product (the GUI IDE), confirmed live via `formulae.brew.sh`'s cask API.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 9/12 — circuit breaker] Direct-execution fallback after a systemic cross-AI backend outage**
- **Found during:** Wave 2 cross-AI dispatch (opencode, model `router-env/my-coding`)
- **Issue:** 5 consecutive identical `Error: Service temporarily unavailable due to resource pressure. Retry shortly.` failures across this wave and the prior one (08-01) — a systemic outage pattern, not an isolated blip.
- **Fix:** Executed both of this plan's tasks directly in this orchestrator session rather than continuing to retry cross-AI dispatch. No plan content was altered.
- **Verification:** `make validate && make test` both pass (1243 passed, 99.40% coverage).
- **Committed in:** `79df050` (task commit, fallback explicitly disclosed)

---

**Total deviations:** 1 (execution-channel fallback only; zero content deviation from the reviewed plan)
**Impact on plan:** None — the plan's own content was already finalized through three cross-AI review cycles before this ran.

## Issues Encountered

Cross-AI execution (opencode) remained unavailable for this wave (systemic backend outage, same as 08-01); resolved via the documented direct-execution fallback.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`cursor-agent` and `antigravity` are fully wired and tested. Wave 3 (`08-03-PLAN.md`: `rtk` github_release) has no dependency on this wave beyond the shared registry file and can proceed independently. Wave 4's `recommends` wiring (08-04) will add `cursor-agent` to the four-host `recommends` set once `rtk` (08-03) exists.

---
*Phase: 08-ai-tier-catalog-expansion-uv-tool-executor*
*Completed: 2026-09-06*
