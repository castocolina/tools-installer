---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 09
subsystem: ownership
tags: [pnpm, dangling-shim, broken, repair, mmdc]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: ManagerOwnership.off_policy as the previous last field, and resolve_ownership return sites for native and os-package records
provides:
  - dangling_shim predicate for a pnpm bin shim whose package is gone
  - ManagerOwnership.broken computed from the live path, pnpm dir, and pnpm inventory already in hand
  - install_tool(repair=True) that skips only the already-installed short-circuit
affects: [16-13, 16-15]

actuals:
  tokens: 4489
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - broken is a sibling of is_installed, never a third boolean return
    - repair reuses the normal method ladder; it does not re-link a shim

key-files:
  created: []
  modified:
    - installer/status.py
    - installer/ownership.py
    - installer/engine.py
    - tests/test_status.py
    - tests/test_ownership.py
    - tests/test_engine.py

key-decisions:
  - "broken is applied with dataclasses.replace at every resolve_ownership return, including the native and os-package sites, so a helper default cannot leave those records False."
  - "An unreadable pnpm inventory (None) is not-broken. A missing claim is not evidence the package is gone."

patterns-established:
  - "dangling_shim is the only broken predicate. resolve_ownership calls it once after owner dirs are built and copies the bool onto every returned record."
  - "install_tool(repair=True) is the only repair entry. Plan 16-13 sets it; this plan does not widen Install or SensitiveInstall."

requirements-completed: [D-18]

coverage:
  - id: D1
    description: "A node shim under a pnpm bin dir is broken when the inventory was read and the npm package is absent. Listed, unreadable, outside the pnpm dir, and missing binary are not broken."
    requirement: D-18
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_dangling_shim_true_when_pnpm_package_is_gone"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_dangling_pnpm_shim_reads_broken"
        status: pass
    human_judgment: false
  - id: D2
    description: "ManagerOwnership.broken is present on every resolve_ownership record, including an os-package winner, and equals the dangling_shim result for that evidence."
    requirement: D-18
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_os_package_owner_broken_matches_computed_false"
        status: pass
    human_judgment: false
  - id: D3
    description: "install_tool without repair still returns already-installed and does not call the runner. repair=True walks the first resolved method and dispatches post_install on that same success path."
    requirement: D-18
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_repair_walks_the_ladder_past_already_installed"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_repair_dispatches_post_install_like_a_fresh_install"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_already_installed_short_circuits"
        status: pass
    human_judgment: false

duration: 33min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 09: Dangling pnpm shim Summary

**A pnpm bin shim whose package is gone reads broken, and an explicit repair walks the same install ladder as a fresh install**

## Performance

- **Duration:** 33 min
- **Started:** 2026-10-10T13:18:12Z
- **Completed:** 2026-10-10T13:51:18Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- D-18: `dangling_shim` is true only when a node method names an `npm_pkg`, the live binary is under a pnpm dir, the inventory was read, and the package is not listed. That is the mmdc case from todo 2026-09-16.
- `ManagerOwnership.broken` carries that verdict. `resolve_ownership` computes it once from `dirs["pnpm"]` and `inventory.pnpm_globals`. No new subprocess.
- `install_tool(..., repair=True)` skips only the `ALREADY_INSTALLED` short-circuit. The default path is unchanged. `is_installed` is unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: dangling shim reads broken** - `b6ece40` (feat)
2. **Task 2: repair walks the normal ladder** - `7a26bbe` (feat)

**Plan metadata:** this summary commit (`docs(16-09): summary for plan 16-09`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/status.py` - `dangling_shim(tool, *, active_path, pnpm_dirs, pnpm_globals)`
- `installer/ownership.py` - `ManagerOwnership.broken`, applied at every `resolve_ownership` return
- `installer/engine.py` - keyword-only `repair: bool = False` on `install_tool`
- `tests/test_status.py` - predicate true/false cases
- `tests/test_ownership.py` - mmdc end-to-end cases plus the os-package return
- `tests/test_engine.py` - repair walks the ladder and dispatches `post_install`

## Decisions Made

- `broken` is set with `dataclasses.replace` at every `resolve_ownership` return, not as a kwarg on `_owned` / `_unknown`. The plan allowed either. Replace keeps `grep 'broken: bool = False'` to the field line, and it covers the native and os-package returns the review named.
- `pnpm_globals is None` is not-broken. An unreadable inventory is unknown, not a missing package.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-13 can pass `repair=True` for a tool the user selected while `broken` was true. Do not set it for an unattended or merely installed tool.
- Plan 16-15 can read `ManagerOwnership.broken` for the Inst marker. `is_installed` stays a boolean.
- Doctor is unchanged. D-18 closed the dangling-shim todo through the catalog row, not a Doctor finding.

## Self-Check: PASSED

- `grep -n 'def dangling_shim' installer/status.py` returned `98:def dangling_shim(`.
- `grep -n 'def is_installed(tool: Tool, app_roots' installer/status.py` returned the unchanged signature at line 18.
- `grep -n 'broken: bool = False' installer/ownership.py` returned one line, `312:    broken: bool = False`.
- `grep -n 'if is_installed(tool) and not repair' installer/engine.py` returned `132:    if is_installed(tool) and not repair:`.
- `installer/status.py`, `installer/ownership.py`, and `installer/engine.py` exist.
- `uv run pytest tests/test_status.py tests/test_ownership.py -q -k "broken or dangling"` passed (13 tests, no FAILED).
- `uv run pytest tests/test_ownership.py -q` passed.
- `uv run pytest tests/test_engine.py tests/test_session.py -q` passed.
- `uv run pytest tests/test_status.py tests/test_ownership.py tests/test_engine.py tests/test_session.py -q` passed.
- `uv run pytest -q` exited 0 and reached 100% with no FAILED line.
- `make validate` passed (ruff, format, pyright, bandit, vulture, shellcheck).

## Verification

- Task 1 RED: collecting `tests/test_status.py` raised `ImportError: cannot import name 'dangling_shim'`. After the predicate and the return-site wiring, the `-k "broken or dangling"` run passed and the full `tests/test_ownership.py` passed.
- Task 2 RED: both repair tests failed with `TypeError: install_tool() got an unexpected keyword argument 'repair'`. After the keyword and the short-circuit change, `tests/test_engine.py` and `tests/test_session.py` passed.
- Pyright rejected untyped `lambda tool: True` fakes. They were replaced with the existing `fake_installed(tool: Tool) -> bool` shape and folded into the Task 2 commit before validate.
- `make validate` passed. Full `uv run pytest -q` exited 0.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
