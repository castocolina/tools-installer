---
phase: 04-package-manager-redirect-policy
plan: 04
subsystem: ui
tags: [doctor, guard_guidance, D-02, volta-tradeoff, per-command-labels]

requires:
  - phase: 04-package-manager-redirect-policy
    provides: guard_label / guarded_names (04-01); volta catalog finding (04-02); live pnpm shim as volta-resolved signal (04-03)
provides:
  - per-command doctor labels distinguishing redirect from block
  - degraded-redirect cross-reference on the guards-active item
  - volta install-scripts tradeoff note gated on status["pnpm"]
affects:
  - 04-05 CLI-vs-TUI next_step prefix split sits beside this copy
  - phase-close TUI capture-pane of Doctor view

actuals:
  tokens: 3070
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - D-02: guard_status stays dict[str, bool]; redirect vs block lives in guard_label text
    - wording layer consumes bool dict + warning string; no IO, no status enum
    - volta note gated on a live pnpm shim, Severity.OK so a standing property does not train users to ignore warnings

key-files:
  created: []
  modified:
    - installer/guidance.py
    - tests/test_guidance.py
    - tests/test_render.py
    - tests/test_app.py
    - tests/test_wizard_app.py

key-decisions:
  - "D-02: per-command label text distinguishes redirect from block; guard_guidance signature unchanged"
  - "D-07: volta note states the verified mechanism (real npm install --global, install scripts ungated) at Severity.OK"
  - "Cross-reference sentence connects a static redirect label to the warning channel when a redirect is active and a warning is present"

patterns-established:
  - "guard_guidance is the single wording source; both renderers consume the list unchanged"
  - "Iterate guarded_names() not the caller's dict so doctor copy is order-stable"

requirements-completed:
  - REQ-npm-npx-redirect-policy
  - REQ-npx-ban

coverage:
  - id: D1
    description: "Each active guard is named with its own label in one Guidance item; silent when nothing is active"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_reports_active_guards_with_per_command_labels
        status: pass
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_silent_when_inactive_and_no_warning
        status: pass
    human_judgment: false
  - id: D2
    description: "guard_guidance signature stays (status: dict[str, bool], warning: str | None) -> list[Guidance]"
    requirement: REQ-npx-ban
    verification:
      - kind: other
        ref: inspect.signature(guard_guidance)
        status: pass
    human_judgment: false
  - id: D3
    description: "A warning present alongside an active redirect adds a cross-reference sentence; a plain block or no warning does not"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_cross_references_warning_when_redirect_is_active
        status: pass
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_no_cross_reference_without_warning
        status: pass
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_no_cross_reference_for_plain_block
        status: pass
    human_judgment: false
  - id: D4
    description: "When global installs go to volta, the doctor states that volta runs a real npm install --global with install scripts ungated; absent when pnpm is not live"
    requirement: REQ-npm-npx-redirect-policy
    verification:
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_volta_note_follows_guards_when_pnpm_is_live
        status: pass
      - kind: unit
        ref: tests/test_guidance.py#test_guard_guidance_volta_note_absent_when_pnpm_is_not_live
        status: pass
    human_judgment: false
  - id: D5
    description: "Console doctor and TUI DoctorScreen both render the per-command labels without renderer code changes"
    requirement: REQ-npx-ban
    verification:
      - kind: unit
        ref: tests/test_render.py#test_render_guard_status_reports_per_command_labels
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_doctor_reports_npx_redirect
        status: pass
      - kind: unit
        ref: tests/test_wizard_app.py#test_doctor_screen_shows_npx_redirect_label
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-09-05
status: complete
---

# Phase 4 Plan 04: Per-command doctor labels Summary

**Doctor copy names each guarded command with its own redirect-or-block label, and a live volta path states that `volta install` still runs ungated npm install scripts.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-05T14:34:08Z
- **Completed:** 2026-09-05T14:52:19Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- `guard_guidance` titles the active item `Package manager guards active` and lists `{name}: {guard_label(name)}` in `guarded_names()` order.
- A warning plus an active redirect appends a cross-reference sentence so a static label is not the only channel when the on-disk body degraded.
- A second Severity.OK item names volta when `status["pnpm"]` is True — the on-disk signal that 04-03 wrote the wrapper after volta resolved.
- Console `render_guard_status` and TUI `DoctorScreen` needed no code change; both consume the same list.

## Exact doctor wording (capture-pane contract)

Per-command labels from `guard_label`:

| Command | Label |
|---------|-------|
| npx | redirected to pnpm dlx |
| pip | blocked |
| pip3 | blocked |
| npm | global installs redirected to volta install, other npm use blocked |
| pnpm | global adds redirected to volta install |

Guards-active item (when any status value is True):

- **title:** `Package manager guards active`
- **meaning:** `"; ".join(f"{name}: {guard_label(name)}" for name in active) + "."`
- **cross-reference** (only when `warning is not None` and at least one active name is in `REDIRECTED` or `GLOBAL_REDIRECTED`): ` Labels describe the configured redirect; the warning below reports anything that degraded.`
- **next_step:** `Open a new shell or run \`hash -r\` so cached command paths refresh.`
- **severity:** ok

Volta note (only when `status.get("pnpm", False)` is True):

- **title:** `Volta global installs run npm install scripts`
- **meaning:** `A global install through volta runs a real \`npm install --global\`; npm's install scripts are not gated the way pnpm gates them.`
- **next_step:** `Keep untrusted packages on a project-local \`pnpm add\`.`
- **severity:** ok

PATH-order warning item is unchanged: title `PATH order warning`, meaning is the warning string verbatim, severity warn.

## Task Commits

1. **Task 1: Per-command label text in the doctor report** - `5884c4e` (feat)
2. **Task 2: State the volta tradeoff where the user reads it** - `e16d43f` (feat)
3. **Task 3: Prove both renderers show it** - `10827a3` (test)

## Files Created/Modified

- `installer/guidance.py` - rewritten `guard_guidance` (per-command labels, cross-reference, volta note)
- `tests/test_guidance.py` - label, ordering, cross-reference, and volta cases
- `tests/test_render.py` - console renderer pins
- `tests/test_app.py` - `run_doctor` pins plus redirect-shim case
- `tests/test_wizard_app.py` - headless DoctorScreen pin

## Decisions Made

Followed the plan: D-02 (no status enum, signature unchanged), D-07 (verified mechanism, Severity.OK, gated on `status["pnpm"]`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `'npm' not in meaning` false-positive against `pnpm`**
- **Found during:** Task 1
- **Issue:** Plan AC `assert 'npm' not in i.meaning` fails because `npx: redirected to pnpm dlx` contains the substring `npm`
- **Fix:** Tests assert `"npm:" not in item.meaning` (npm is not a listed command)
- **Files modified:** `tests/test_guidance.py`
- **Verification:** per-command label test passes; signature AC and empty-list AC pass as written
- **Committed in:** `5884c4e` (Task 1)

**2. [Rule 2 - Missing Critical] Renderer tests pinned the old title**
- **Found during:** Task 1 (`make test` after the wording change)
- **Issue:** `tests/test_render.py`, `tests/test_app.py`, `tests/test_wizard_app.py` still looked for `pip/npm ban active`
- **Fix:** Task 1 retargeted those assertions at the new title so the tree stayed green; Task 3 then pinned per-command lines and added the two new cases
- **Files modified:** `tests/test_render.py`, `tests/test_app.py`, `tests/test_wizard_app.py`
- **Verification:** `make validate && make test` passed on Task 1 and again on Task 3
- **Committed in:** `5884c4e` (Task 1) and `10827a3` (Task 3)

---

**Total deviations:** 2 auto-fixed (1 plan-AC substring bug, 1 quality-gate ordering). **Impact:** none on shipped wording.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 04-05: pnpm-global snapshot/reinstall as a Doctor remediation. This plan's `guard_guidance` wording sits beside 04-05's CLI-vs-TUI `next_step` prefix split; nothing in that split changes the guard copy specified here.

## Self-Check: PASSED

- `installer/guidance.py` exists and `guard_guidance` signature is unchanged
- `git log --oneline --all --grep="04-04"` returns 3 task commits
- `uv run pytest tests/test_guidance.py tests/test_render.py tests/test_app.py tests/test_wizard_app.py -x -q` passed
- `make validate && make test` passed on each task tree
- neither `installer/render.py` nor `installer/wizard_app.py` changed

---
*Phase: 04-package-manager-redirect-policy*
*Completed: 2026-09-05*
