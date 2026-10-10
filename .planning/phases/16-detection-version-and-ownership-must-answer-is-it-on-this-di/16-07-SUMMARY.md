---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 07
subsystem: skill-lifecycle
tags: [skill_pack, supported_harnesses, by_harness, host-presence]

requires:
  - phase: 16-02
    provides: status_probes model and closed plugin-cli / skills-lock / install-state sources
provides:
  - Audited supported_harnesses and Verified citations for all seven skill packs
  - by_harness install handoff filtered by present_harnesses
  - SKILL_HARNESS_LABELS exhaustive over SKILL_HARNESSES
affects: [16-12]

actuals:
  tokens: 9729
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "by_harness pairs are sorted by SKILL_HARNESSES at parse time"
    - "Host presence is a closed command-or-disk table, injected via home and which"

key-files:
  created: []
  modified:
    - installer/registry.toml
    - installer/model.py
    - installer/skill_lifecycle.py
    - tests/test_registry.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "Codex App and Codex CLI share id codex. OpenSpec windsurf is an alias of devin and is not a second openspec host."
  - "A host with no closed probe source has no status_probes row and reads unknown. generic and the shared .agents target are not hosts."
  - "New SKILL_HARNESSES ids were added rather than dropping an upstream-named host."

patterns-established:
  - "A # Verified line sits within 15 lines above each [tool.skill_lifecycle] header."
  - "Every install-state probe match is the literal gsd-core."

requirements-completed: [D-09, D-11, D-13, D-15]

coverage:
  - id: D1
    description: "superpowers is multi-host, has no requires pi, and its install handoff on a Claude-only home omits pi install."
    requirement: D-09
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_superpowers_install_on_a_claude_only_host_omits_pi"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_superpowers_catalog_is_multi_host_without_a_forced_pi_dependency"
        status: pass
    human_judgment: false
  - id: D2
    description: "An empty home prepends the no-host header and includes every superpowers host command."
    requirement: D-15
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_superpowers_install_with_no_host_lists_every_upstream_command"
        status: pass
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_cursor_is_present_from_disk_when_path_misses"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every skill pack has a Verified comment, and every install-state probe match is gsd-core."
    requirement: D-09
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_every_skill_pack_records_a_verified_comment"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_install_state_probes_match_gsd_core"
        status: pass
    human_judgment: false
  - id: D4
    description: "SKILL_HARNESS_LABELS covers every SKILL_HARNESSES id with a non-empty ASCII label."
    requirement: D-13
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_skill_harness_labels_cover_every_harness"
        status: pass
    human_judgment: false

duration: 90min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 07: Audited skill-pack hosts and filtered install handoff Summary

**Seven skill packs cite upstream host lists, superpowers no longer forces Pi, and install instructions show only hosts this machine has.**

## Performance

- **Duration:** 90 min
- **Started:** 2026-10-10T11:00:00Z
- **Completed:** 2026-10-10T12:28:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Re-audited all seven skill packs. `# Verified` count went from 21 to 28.
- superpowers `requires = ["pi"]` is gone. Install `by_harness` commands come from the upstream README. A Claude-only home does not show `pi install`.
- `present_harnesses` detects Cursor from `~/.cursor` when `which` misses. `SKILL_HARNESS_LABELS` names every harness id.

## New harness ids

Added rather than dropped. Mapped onto an existing id where the product was already named: `factory`/`droid` -> `factory-droid`, `gemini` -> `gemini-cli`, `github-copilot` -> `copilot`, `kilocode` -> `kilo`, `agy` -> `antigravity`, `cursor-agent` -> `cursor`, `kiro-cli` -> `kiro`, `mcode` -> `minimax-code`, `omp` -> `oh-my-pi`, `qodercli` -> `qoder`.

New ids: `adal`, `aider`, `alquimia`, `amazon-q`, `amp`, `auggie`, `bob`, `cline`, `codeartsagent`, `codeassistant`, `codebuddy`, `codewhale`, `command-code`, `continue`, `costrict`, `crush`, `devin`, `docker-agent`, `dsh`, `firebender`, `forge`, `forgecode`, `goose`, `grok`, `hermes`, `iflow`, `jules`, `junie`, `kiro`, `lingma`, `minimax-code`, `muse`, `oh-my-pi`, `openclaw`, `qoder`, `qwen`, `roocode`, `rovodev`, `shai`, `tabnine`, `trae`, `vibe`, `zcode`, `zed`.

Skipped as not hosts: spec-kit `generic`, OpenSpec shared `.agents` target. OpenSpec's `windsurf` alias is `devin`; `windsurf` stays only where another pack still names Windsurf.

## Task Commits

Each task was committed atomically:

1. **Task 1: superpowers audit and present-host install handoff** - `35f61c1` (feat)
2. **Task 2: audit of the remaining six packs** - `aea06d9` (feat)
3. **Task 3: SKILL_HARNESS_LABELS** - `7a2bf34` (feat)

**Plan metadata:** this summary commit (`docs(16-07): summary for plan 16-07`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/model.py` - `SkillOperation.by_harness`; widened `SKILL_HARNESSES`
- `installer/skill_lifecycle.py` - `HARNESS_PRESENCE`, `present_harnesses`, filtered `perform_action`, `SKILL_HARNESS_LABELS`, widened `SKILL_LOCK_HARNESS_DIRS`
- `installer/registry.toml` - audited host lists, probes, `by_harness`, Verified comments
- `tests/test_registry.py` - Verified-comment placement and `gsd-core` match pin
- `tests/test_skill_lifecycle.py` - handoff, membership pins, label exhaustiveness

## Decisions Made

- Codex App and Codex CLI share `codex`. The App path is GUI-only; `by_harness` carries the CLI lines.
- Ambiguous tails ("etc.", "and more", "copy AGENTS.md if not listed") were not expanded. The Verified comment says so.
- openspec and spec-kit have no status probes. Global detection cannot prove project initialization.
- A harness with no row in `HARNESS_PRESENCE` is never "present", so its commands appear only in the no-host fallback.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shipped status test treated newly probed packs as manual**
- **Found during:** Task 2
- **Issue:** `test_every_shipped_skill_pack_status_is_probed_or_explicitly_manual` expected manual-required for every pack except ponytail and superpowers. New probes make those packs absent on an empty home, and skills-lock would otherwise read the real home.
- **Fix:** Pass `tmp_path` and expect absent for softaworks, matt-pocock, and opengsd.
- **Files modified:** tests/test_skill_lifecycle.py
- **Verification:** targeted pytest passed
- **Committed in:** `aea06d9`

**2. [Rule 1 - Bug] Codex was the skills-lock "unknown harness" fixture**
- **Found during:** Task 2
- **Issue:** Widening `SKILL_LOCK_HARNESS_DIRS` made codex a known dir, so `test_skills_lock_unknown_harness_is_unknown` saw absent.
- **Fix:** The fixture harness is `muse`, which the skills README does not give a global dir.
- **Files modified:** tests/test_skill_lifecycle.py
- **Verification:** that test passed
- **Committed in:** `aea06d9`

**3. [Rule 3 - Blocking] Extra probes broke the exact shipped status dict**
- **Found during:** Task 1
- **Issue:** `test_shipped_packs_report_per_host_status` raised on `claude plugin list` and pinned exact probe maps.
- **Fix:** Unknown argv returns empty output. Assertions check the known present keys only.
- **Files modified:** tests/test_skill_lifecycle.py
- **Verification:** targeted pytest passed
- **Committed in:** `35f61c1`

---

**Total deviations:** 3 auto-fixed (2 bug, 1 blocking)
**Impact on plan:** Test pins had to move with the audit. No scope creep in the installer behavior.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-12 can render `SKILL_HARNESS_LABELS`. Adding a harness id without a label fails `test_skill_harness_labels_cover_every_harness` (checked once with `zzz-fake`, then reverted).
- Hosts outside `HARNESS_PRESENCE` are not detected. Their commands show only when no supported host is present.
- Probe counts from `load_tools`: ponytail 2, superpowers 3, softaworks-agent-toolkit 4, matt-pocock-skills 8, opengsd 9, openspec 0, spec-kit 0.

## Self-Check: PASSED

- `awk` of the superpowers block printed 0 for `requires = ["pi"]`.
- `grep -n 'def present_harnesses'` printed one line.
- `grep -c '^# Verified'` printed 28 (21 before this plan).
- Adding `zzz-fake` to `SKILL_HARNESSES` failed the label test; the id was reverted.
- `make validate` passed.
- `uv run pytest tests/test_registry.py tests/test_model.py tests/test_skill_lifecycle.py tests/test_engine.py -q` reached 100% with no FAILED.
- `uv run pytest -q` reached 100% with skips only, no FAILED.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
