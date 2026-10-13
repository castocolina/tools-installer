---
phase: 04-package-manager-redirect-policy
plan: 05
subsystem: policy
tags: [pnpm-globals, doctor, D-08, R-03, real_pnpm, run_live]

requires:
  - phase: 04-package-manager-redirect-policy
    provides: real_pnpm absolute-path resolver (04-03); per-command doctor labels (04-04)
provides:
  - registry-derived residual pnpm-managed global snapshot (mmdc)
  - one-invocation reinstall through real_pnpm
  - Doctor audit + explicit r remediation
  - run_live catches CommandError
affects:
  - Phase 12 automatic post-pnpm-update trigger (still owed)
  - Phase 5 REQ-mmdc-install-decision (may empty the residual set)

actuals:
  tokens: 11800
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns:
    - snapshot IS the live registry kind=node set; no persisted state file
    - reinstall argv[0] is guards.real_pnpm, never a bare program name
    - DoctorScreen reinstall state is globals_done/globals_error, not applied/error
    - UnifiedApp new closures default to None so existing constructions keep working

key-files:
  created:
    - installer/pnpm_globals.py
    - tests/test_pnpm_globals.py
  modified:
    - installer/guidance.py
    - installer/render.py
    - installer/app.py
    - installer/wizard_app.py
    - installer/ui_common.py
    - setup.py
    - tests/test_guidance.py
    - tests/test_render.py
    - tests/test_app.py
    - tests/test_wizard_app.py
    - tests/test_ui_common.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "D-08: residual kind=node set at execution is mmdc (@mermaid-js/mermaid-cli); requirement is not satisfied by elimination"
  - "Reinstall argv is [/real/pnpm, add, -g, ...pkgs] with argv[0] from guards.real_pnpm (shim dir excluded)"
  - "run_live catches (OSError, CommandError); a failed reinstall is a message on DoctorScreen"
  - "UnifiedApp node_globals/globals_preview/reinstall_globals default to None (healthy empty / no-op); setup.py wiring makes production real"
  - "R-03: no automatic pnpm-self-update trigger; REQUIREMENTS.md/ROADMAP.md now read Partial, Phase 12 owns the automatic trigger"

patterns-established:
  - "reinstall_preview is the single three-state render (empty / unresolvable / resolvable); the screen prints the string and does not build argv"
  - "CLI next_step uses Run `make setup`; DoctorScreen._tui_guidance rewrites that prefix to name the r key"

requirements-completed:
  - REQ-pnpm-global-reinstall-mitigation

coverage:
  - id: D1
    description: "Residual kind=node set is derived live from the registry; mmdc is present; reinstall is one argv for the whole set through real_pnpm"
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_real_registry_residual_set_contains_mmdc
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_reinstall_skips_wrapper_first_on_path
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_reinstall_node_globals_unresolvable_pnpm_raises_without_running
        status: pass
    human_judgment: false
  - id: D2
    description: "make doctor reports a lost pnpm-managed global with a CLI Run `make setup` next_step, and is silent when healthy"
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: unit
        ref: tests/test_guidance.py#test_node_globals_guidance_warns_and_points_at_make_setup
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_doctor_reports_missing_pnpm_globals
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_doctor_silent_on_healthy_pnpm_globals
        status: pass
    human_judgment: false
  - id: D3
    description: "Doctor r reinstalls the whole set once, empty set is a no-op, CommandError is a message, PATH fix and reinstall states are independent"
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: unit
        ref: tests/test_wizard_app.py#test_doctor_r_reinstalls_once_and_reports_success
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_doctor_r_commanderror_leaves_screen_usable
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_doctor_enter_then_r_both_run
        status: pass
      - kind: unit
        ref: tests/test_ui_common.py#test_run_live_returns_result_or_error_message
        status: pass
    human_judgment: false
  - id: D4
    description: "Unresolvable-pnpm preview is a named message, never a blank section or a bare-name argv"
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: unit
        ref: tests/test_wizard_app.py#test_doctor_screen_renders_unresolvable_pnpm_preview
        status: pass
      - kind: unit
        ref: tests/test_pnpm_globals.py#test_reinstall_preview_unresolvable_is_message_not_argv
        status: pass
    human_judgment: false
  - id: D5
    description: "R-03 manual-only trigger is recorded as Partial in REQUIREMENTS.md and ROADMAP.md, with Phase 12 named as owner of the automatic trigger"
    requirement: REQ-pnpm-global-reinstall-mitigation
    verification:
      - kind: other
        ref: .planning/REQUIREMENTS.md traceability row Partial / Phase 12
        status: pass
    human_judgment: false
  - id: D6
    description: "Live tmux Doctor footer structural check (both actions visible)"
    verification: []
    human_judgment: true
    rationale: "Plan-level tmux capture-pane is a phase-close structural check; unit tests already pin VIEWS.actions and FooterBar text. Verifier should capture the Doctor footer without pressing r or enter."

duration: 28min
completed: 2026-09-05
status: complete
---

# Phase 4 Plan 5: pnpm-global snapshot-reinstall Summary

**Registry-derived residual pnpm-managed set (`mmdc`) reinstalls in one `real_pnpm add -g` call from an explicit Doctor `r` action; no automatic post-update trigger**

## Performance

- **Duration:** 28 min
- **Started:** 2026-09-05T14:55:00Z
- **Completed:** 2026-09-05T15:23:35Z
- **Tasks:** 4
- **Files modified:** 15

## Accomplishments

- Residual `kind="node"` set at execution time is **`mmdc`** (`npm_pkg=@mermaid-js/mermaid-cli`, `cmd=mmdc`). D-08 is not satisfied by elimination.
- Reinstall argv is `[<absolute real pnpm>, "add", "-g", ...pkgs]` in one invocation. `argv[0]` comes from `installer.guards.real_pnpm` (managed shim dir excluded, sentinel-carrying results refused). A wrapper-first PATH regression test pins that the recorded argv[0] is the real binary further down, never the bare name `pnpm`.
- `run_live` now catches `(OSError, CommandError)`. A failed reinstall is a message on DoctorScreen; the screen stays usable.
- `UnifiedApp` accepts `node_globals` / `globals_preview` / `reinstall_globals` as optional kwargs defaulting to `None` (healthy empty report, empty-set preview, no-op). Nine existing constructions in catalog/uninstall/policies e2e tests were not edited and still work. `setup.py` wiring is what makes production real.
- No automatic "pnpm just updated" trigger was added (R-03). REQUIREMENTS.md and ROADMAP.md now read the requirement as Partial; Phase 12 owns the automatic trigger alongside `REQ-update-action-manager-delegation`.

## Task Commits

1. **Task 1: The pure snapshot-and-reinstall core** - `55c12b2` (feat)
2. **Task 2: The read-only audit surface** - `d9123cf` (feat)
3. **Task 3: The explicit Doctor remediation** - `8c4d9e9` (feat)
4. **Task 4: Record R-03's narrowed trigger** - `7094faf` (docs)

**Plan metadata:** (this commit)

## Files Created/Modified

- `installer/pnpm_globals.py` - NodeGlobal snapshot, audit, one-shot reinstall, three-state preview
- `tests/test_pnpm_globals.py` - pure-core coverage, no real pnpm
- `installer/guidance.py` / `installer/render.py` / `installer/app.py` - CLI doctor finding
- `installer/wizard_app.py` / `installer/ui_common.py` / `setup.py` - Doctor `r` action, widened `run_live`, wiring
- `.planning/REQUIREMENTS.md` / `.planning/ROADMAP.md` - R-03 Partial status

## Decisions Made

- Residual set is `mmdc`; Phase 5's `REQ-mmdc-install-decision` may move it off `pnpm add -g`, at which point the registry assertion — not the mechanism — changes.
- Reinstall never falls back to a bare `pnpm` name: `resolve_pnpm()` returning None raises `CommandError` before the runner is touched.
- Doctor reinstall state is `globals_done` / `globals_error`, independent of the PATH fix's `applied` / `error`.
- R-03 stands: mechanism + audit + manual Doctor action in Phase 4; automatic trigger in Phase 12.

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Docstring avoided the words JSON/SQLite**
- **Found during:** Task 1 acceptance grep
- **Issue:** The plan required the module docstring to say there is no JSON/SQLite state file, and also required `grep -c 'json\|sqlite|...'` to be 0.
- **Fix:** Docstring says "No persisted state file" instead.
- **Files modified:** `installer/pnpm_globals.py`
- **Verification:** grep count is 0; intent (no new state store) is unchanged
- **Committed in:** `55c12b2`

---

**Total deviations:** 1 auto-fixed (plan-text contradiction).
**Impact on plan:** None on behavior.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 4's five plans are all executed. Ready for `/gsd-verify-work 4` and then Phase 5 discuss/plan. Phase 12 still owes the automatic post-pnpm-update trigger for `REQ-pnpm-global-reinstall-mitigation`. Do not press `r` or `enter` on the live Doctor view against this machine (ONESHOT-RULES Rule 5).

## Self-Check: PASSED

---
*Phase: 04-package-manager-redirect-policy*
*Completed: 2026-09-05*
