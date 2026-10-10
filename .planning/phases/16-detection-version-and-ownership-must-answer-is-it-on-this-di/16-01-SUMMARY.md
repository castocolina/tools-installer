---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 01
subsystem: ownership
tags: [sdkman, ownership, bin_dir, installer]

requires: []
provides:
  - sdkman Owner end to end, proven from the method's existing bin_dir
  - own installer column label for script-kind location proof
  - _sdkman probe reads kind=sdkman and candidate, deliberately unwired
affects: [16-05, 16-06, 16-10]

actuals:
  tokens: 5157
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Location proof is one predicate, _location_proof, shared by candidate collection and directory attribution"
    - "Ownership location evidence reuses the registry bin_dir; no second location field"

key-files:
  created: []
  modified:
    - installer/ownership.py
    - installer/update.py
    - installer/install_ownership.py
    - installer/uninstall.py
    - tests/test_ownership.py
    - tests/test_update.py
    - tests/test_install_ownership.py
    - tests/test_catalog_tui.py

key-decisions:
  - "Reused bin_dir as the location proof. No new registry field."
  - "Probe fixed, deliberately unwired. detect_owner only runs probes listed in tool.owner_probes, and no registry row declares owner_probes = [\"sdkman\"]. No phase-16 plan wires it; location proof is the primary evidence, so wiring would add one fail-closed subprocess per SDKMAN tool with no evidence gain."
  - "sdkman is not in UNMANAGEABLE_OWNERS. Update still refuses, with the real sdk upgrade command, and never calls the runner."

patterns-established:
  - "Pattern: kinds with an inventory source (brew, cask, node, uv-tool) never get location proof. sdkman and installer kinds do, via the same is_file() rule status.is_installed uses."

requirements-completed: [D-01, D-07, D-08, D-19]

coverage:
  - id: D1
    description: "A pure-SDKMAN tool resolves to SDKMAN, direct when the live binary is under bin_dir and by-elimination when it is not on PATH, and unknown when the command file is absent."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_sdkman_location_proof_resolves_direct_when_which_matches"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_sdkman_location_proof_is_by_elimination_when_not_on_path"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_sdkman_absent_bin_dir_file_is_unknown"
        status: pass
    human_judgment: false
  - id: D2
    description: "Script-kind tools such as bun read own installer from on-disk bin_dir proof, and a path two managers both claim stays unknown."
    requirement: D-07
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_own_installer_location_proof_resolves_bun_when_brew_does_not_list_it"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_script_and_uv_attributing_the_same_live_path_stay_unknown"
        status: pass
    human_judgment: false
  - id: D3
    description: "springbootcli's probe argv is sdk current springboot, not springbootcli. The probe stays unwired."
    requirement: D-01
    verification:
      - kind: unit
        ref: "tests/test_install_ownership.py#test_sdkman_probe_uses_declared_candidate_not_tool_id"
        status: pass
    human_judgment: false
  - id: D4
    description: "An SDKMAN-owned update refuses with sdk upgrade <candidate> and never calls the runner."
    requirement: D-08
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_sdkman_owned_update_refuses_with_real_command"
        status: pass
    human_judgment: false
  - id: D5
    description: "Location proof is the existing bin_dir param. No second location field."
    requirement: D-19
    verification:
      - kind: other
        ref: "grep bin_dir installer/ownership.py _location_proof; no new registry field"
        status: pass
    human_judgment: false

duration: 13min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 01: SDKMAN and own-installer location proof Summary

**SDKMAN and own-installer tools resolve from the bin_dir each method already declares, and an SDKMAN update names `sdk upgrade` instead of refusing with a placeholder.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-10-10T09:21:52Z
- **Completed:** 2026-10-10T09:34:47Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- `sdkman` is an Owner across the literal, kind map, candidate order, and the four label/removal tables. A pure-SDKMAN tool resolves direct or by-elimination only when `<bin_dir>/<cmd>` is a file.
- Script methods (bun at `~/.bun/bin`) resolve to `installer` with column label `own installer`. Two candidates attributing the same live path stay `unknown`.
- `_sdkman` reads `kind=sdkman` and `candidate`. springbootcli probes `springboot`. Probe fixed, deliberately unwired.
- `u` on an SDKMAN-owned tool returns `unsupported` with `sdk upgrade {candidate}` and does not call the runner.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end SDKMAN location proof and update refusal** - `9d4bd02` (feat)
2. **Task 2: Fix the `_sdkman` probe kind filter and param key** - `a162cdb` (fix)
3. **Task 3: Own-installer location proof and the `own installer` label** - `f030875` (feat)

**Line-length follow-up (Task 2 assertion):** `fbbb3f1` (style)

## Files Created/Modified

- `installer/ownership.py` - `sdkman` Owner, `_location_proof` / `_location_dirs`, `own installer` label, removal tables
- `installer/update.py` - SDKMAN refusal names `sdk upgrade {candidate}`
- `installer/install_ownership.py` - probe reads `candidate` on `kind=sdkman`; still unwired
- `installer/uninstall.py` - stale "no Owner can carry sdkman" comment rewritten; behavior unchanged
- `tests/test_ownership.py` - `test_sdkman_*` and own-installer / ambiguity / idempotency tests
- `tests/test_update.py` - real-command refusal; hybrid installer+sdkman record removed
- `tests/test_install_ownership.py` - `test_sdkman_probe_*`
- `tests/test_catalog_tui.py` - script label pin updated to `own installer`

## Decisions Made

- Location proof reuses `bin_dir`. No new registry field and no parallel per-tool table.
- Probe fixed, deliberately unwired. `detect_owner` only runs probes in `tool.owner_probes`. No registry row declares `owner_probes = ["sdkman"]`, and no plan in phase 16 wires it. Location proof is the primary evidence.
- `sdkman` is mutation-grade and not in `UNMANAGEABLE_OWNERS`. The update path still refuses, with the real command, so a brownfield interactive `sdk` prompt cannot hang the worker.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Parametrized sdkman row pinned the broken probe shape**
- **Found during:** Task 2 (probe kind/key fix)
- **Issue:** `test_owner_verifies_each_manager_from_its_own_output` built `Method(kind="script", params={"sdk_candidate": "java"})` on a tool whose id is `demo`. After the probe reads the real registry shape, that row falls through to `tool.id` and fails.
- **Fix:** The row now uses `Method(kind="sdkman", params={"candidate": "java"})`.
- **Files modified:** tests/test_install_ownership.py
- **Verification:** `uv run pytest tests/test_install_ownership.py tests/test_uninstall.py -q` passed
- **Committed in:** `a162cdb`

**2. [Rule 3 - Blocking] Assertion line exceeded the 100-character ruff gate**
- **Found during:** Plan verification after the Task 2 commit
- **Issue:** `make validate` failed E501 on the new springboot assertion (101 > 100).
- **Fix:** Wrapped the `Ownership(...)` call. The one-line probe comment was also wrapped to two physical lines for the same gate.
- **Files modified:** tests/test_install_ownership.py, installer/install_ownership.py
- **Verification:** `make validate` passed
- **Committed in:** `fbbb3f1` (test wrap); comment wrap is in `a162cdb`

TDD red was observed (owner `unknown`, probe argv `springbootcli`, label `install script`) and not committed separately. A failing-test commit would be a knowingly broken tree, which the executor prompt forbids.

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both keep the suite green against the real registry shape and the line-length gate. No scope creep.

## Issues Encountered

The plan's "update stale comments in ownership.py that say no sdkman owner exists" was a no-op. `ownership.py` had no such comment. The real stale comment was in `installer/uninstall.py` and was rewritten in Task 2.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-06 can read `ownership.method.params["bin_dir"]`. The direct sdkman record's `method` is the iterated method, not None.
- Plan 16-05 can treat `sdkman` as a real owner. Ambiguous live paths still resolve `unknown` with the existing active-path sentence.
- The `_sdkman` probe is fixed and deliberately unwired. Do not add `owner_probes = ["sdkman"]` in this phase.

## Self-Check: PASSED

- `installer/ownership.py` contains exactly one `"sdkman": "SDKMAN"`, exactly one `"sdkman": "sdk uninstall {package} <version>"`, exactly one `"script": "own installer"`, one `def _location_proof`, and 3 `_location_proof(` occurrences.
- `grep -c 'this phase does not implement' installer/update.py` printed 0.
- `grep -n 'sdk_candidate' installer/install_ownership.py` returned nothing. `_method_values(tool, {"sdkman"}, "candidate")` is one line (`install_ownership.py:367`).
- `grep -rn '"install script"' installer/ tests/` returned nothing. `owner="installer"` is not inside `test_sdkman_owned_is_unsupported`.
- `uv run pytest tests/test_ownership.py tests/test_install_ownership.py tests/test_update.py tests/test_uninstall.py tests/test_catalog_tui.py -q` passed.
- `uv run pytest -q` passed (skips only, no FAILED).
- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
