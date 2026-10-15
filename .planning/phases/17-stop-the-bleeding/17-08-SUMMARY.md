---
phase: 17-stop-the-bleeding
plan: "08"
subsystem: ui
tags: [textual, policy, link-mode, rollback, settings, run-live]

# Dependency graph
requires:
  - phase: 17-stop-the-bleeding (17-06)
    provides: atomic marker-scoped rc writes the move relies on
  - phase: 17-stop-the-bleeding (17-07)
    provides: picker wiring and screen seams the pickers reuse
provides:
  - Policy.link_mode_aware appended field (ban, tweak, macOS cache redirect set it)
  - PolicyMove and move_link_mode (remove-old / save / apply-new with per-policy restore)
  - _rollback helper shared by the save-failure and recovery re-set-failure raise paths
  - SettingsStore.set_link_mode saves before it assigns the live mode
  - PoliciesScreen.link_mode_aware_active() and the shared _link_mode_status formatter; both link-mode pickers route through move_link_mode via run_live
affects: [17-11, uninstall, policies-screen]

# Actuals
actuals:
  tokens: 30000
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "per-policy failure isolation mirroring uninstall.sweep_policies (catch OSError/CommandError/ShellrcRefusal, continue)"
    - "raise-and-rollback contract: re-raise after restoring, never report a policy 'moved' that is not"

key-files:
  created: []
  modified:
    - installer/policy.py
    - installer/settings.py
    - installer/wizard_app.py
    - tests/test_policy.py
    - tests/test_policies_e2e.py
    - tests/test_wizard_app.py (append-only field assertion extended)

key-decisions:
  - "PolicyMove is a new dataclass in policy.py, not uninstall.SweepResult: uninstall.py already imports policy.py, so the reverse import would be a cycle"
  - "_rollback calls remove() then apply() per policy on both raise paths; verified remove() is mode-independent for ban, tweak and the macOS cache redirect (ban strips the remove_rc_paths union, tweak and the redirect strip their fixed rc_path), so it also takes an already-moved block out of the new mode's files"
  - "moved-entry detail is 'moved from <old> to <new>' (uses old_mode, satisfying vulture, and is honest about what happened)"

patterns-established:
  - "Picker status text is built by one module-level formatter (_link_mode_status) so the two pickers cannot drift"

requirements-completed: [SAFE-06]

coverage:
  - id: D1
    description: "centralized -> split moves an active ban and tweak end to end through the Policies picker, foreign rc bytes untouched"
    requirement: SAFE-06
    verification:
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_moves_ban_and_tweak_to_split"
        status: pass
      - kind: unit
        ref: "tests/test_policy.py#test_link_mode_move_keeps_foreign_rc_bytes_identical"
        status: pass
      - kind: automated_ui
        ref: "tests/test_policies_e2e.py#test_policies_screen_link_mode_change_moves_active_policies"
        status: pass
    human_judgment: false
  - id: D2
    description: "apply failure restores the old block and reports failed; save failure and recovery re-set failure roll everything back and re-raise through a real SettingsStore"
    requirement: SAFE-06
    verification:
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_restores_the_old_block_when_apply_fails"
        status: pass
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_restores_everything_when_saving_the_mode_fails"
        status: pass
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_rolls_back_when_re_saving_the_new_mode_fails"
        status: pass
    human_judgment: false
  - id: D3
    description: "empty move saves only the mode; non-aware policies are never touched; the first-run picker moves active policies; a failed move is named with severity warn"
    requirement: SAFE-06
    verification:
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_with_no_policies_only_saves_the_mode"
        status: pass
      - kind: automated_ui
        ref: "tests/test_policies_e2e.py#test_move_link_mode_ignores_policies_that_are_not_link_mode_aware"
        status: pass
      - kind: automated_ui
        ref: "tests/test_policies_e2e.py#test_first_run_link_mode_picker_moves_active_policies"
        status: pass
      - kind: automated_ui
        ref: "tests/test_policies_e2e.py#test_policies_screen_reports_a_failed_move"
        status: pass
    human_judgment: false

# Metrics
duration: 75min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 08 Summary

**`move_link_mode` carries active link-mode-aware policies (ban, tweak, macOS cache redirect) across a mode change with per-policy restore on failure, save-first `SettingsStore.set_link_mode`, and both pickers routing through `run_live` with one shared status formatter.**

## Performance

- **Duration:** ~75 min
- **Tasks:** 2 of 2
- **Files modified:** 6

## Accomplishments
- `Policy.link_mode_aware` (appended after `owned`, per the append-only comment); set on `ban_policy`, `tweak_policy`, and `cache_redirect_policy` when `platform_os == "macos"`.
- `PolicyMove` + `move_link_mode(policies, new_mode, set_link_mode, *, old_mode)` in `installer/policy.py`: remove in the old mode, save the new mode, apply in the new mode, one report entry per policy; per-policy failure isolation copied from `uninstall.sweep_policies`; both raise paths (mode-save failure, recovery re-set failure) roll every removed policy back via the shared `_rollback` helper and re-raise.
- `SettingsStore.set_link_mode` now saves before assigning the live mode (review cycle 2 MEDIUM), so the ban/tweak closures read the old mode on every rollback path.
- Both pickers (`PoliciesScreen._link_mode_picked`, `UnifiedApp._first_link_mode_picked`) call `move_link_mode` through `ui_common.run_live`, share `PoliciesScreen.link_mode_aware_active()`, and set status only through the module-level `_link_mode_status` formatter (names `Moved:` and `Failed:` entries, warn on any failure, ok otherwise).

## Task Commits

1. **Task 1: centralized -> split moves an active ban and tweak end to end** - `ca5a5c0` (feat)
2. **Task 2: restore on failure, mode-save failure, empty case, first-run picker, scope filter** - `f22eb53` (feat)

## Files Created/Modified
- `installer/policy.py` - `Policy.link_mode_aware`, `PolicyMove`, `_rollback`, `move_link_mode`
- `installer/settings.py` - `set_link_mode` save-then-assign reorder
- `installer/wizard_app.py` - `link_mode_aware_active()`, `_link_mode_status`, both picker call sites
- `tests/test_policy.py` - 6 unit tests (happy path, foreign bytes, apply-failure restore, save-failure rollback through a real SettingsStore, empty case, re-save-failure rollback)
- `tests/test_policies_e2e.py` - 4 pilot tests (screen move, non-aware policy untouched, first-run picker, failed-move status)
- `tests/test_wizard_app.py` - append-only field assertion extended for the new `link_mode_aware` field

## TDD RED evidence

Task 1 (trimmed):
```
FAILED tests/test_policy.py::test_move_link_mode_moves_ban_and_tweak_to_split - NameError: name 'move_link_mode' is not defined
FAILED tests/test_policies_e2e.py::test_policies_screen_link_mode_change_moves_active_policies
E  assert 'tools-installer ban' not in ...ban aliases still in ~/.myshellrc after picking split
```
Task 2 (trimmed):
```
FAILED tests/test_policy.py::test_move_link_mode_restores_the_old_block_when_apply_fails
FAILED tests/test_policy.py::test_move_link_mode_restores_everything_when_saving_the_mode_fails - Failed: DID NOT RAISE <class 'OSError'>
FAILED tests/test_policy.py::test_move_link_mode_rolls_back_when_re_saving_the_new_mode_fails - Failed: DID NOT RAISE <class 'OSError'>
FAILED tests/test_policies_e2e.py::test_first_run_link_mode_picker_moves_active_policies - ban aliases still in rc
FAILED tests/test_policies_e2e.py::test_policies_screen_reports_a_failed_move - status said only 'Moved: ban.'
```
The two DID-NOT-RAISE failures are the pinned RED for the `set_link_mode` reorder: with the old assign-then-save setter the rollback read the new mode and the patched `save_settings` failure path was never exercised as contracted.

## Verify-command results
- `uv run pytest tests/test_policy.py tests/test_policies_e2e.py -q --no-cov -k "..."` — green at both task gates (3 passed Task 1, 7 passed Task 2).
- Task-scope suites (`test_policy.py test_policies_e2e.py test_policy_tweaks.py test_wizard_app.py`; plus `test_settings.py test_setup.py` for Task 2) — green.
- `make validate` and `make test` — green on the final tree (3508 passed, 4 skipped, coverage 95.89% > 90% gate).

## Decisions Made
- `moved` report detail is `moved from <old_mode> to <new_mode>` — honest and keeps `old_mode` load-bearing in the Task 1 shape.
- Verified while implementing that `remove()` is mode-independent for all three aware policies (ban strips the `remove_rc_paths` union; tweak and the macOS cache redirect strip their fixed `rc_path`), so `_rollback`'s remove-then-apply also retracts an already-moved block. Noted asymmetry (accepted by review round 2): a `remove()` that fails partway across multiple files leaves per-file inconsistency; the policy is reported `failed` and left as it was.

## Deviations from Plan

### Auto-fixed Issues

**1. Extended the append-only Policy field assertion outside files_modified**
- **Found during:** Task 1 full-suite run
- **Issue:** `tests/test_wizard_app.py::test_policy_appends_decided_closures_after_every_existing_field` pins the last Policy field names and broke when `link_mode_aware` was appended.
- **Fix:** Extended the assertion to `["decided", "clear_decided", "owned", "link_mode_aware"]`.
- **Files modified:** tests/test_wizard_app.py
- **Verification:** full suite green
- **Committed in:** `ca5a5c0` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (test assertion forced by the plan's own appended field; no production scope creep).
**Impact on plan:** None beyond the pinned assertion; everything else stayed inside `files_modified`.

## Issues Encountered
- The first-run-picker test initially set `active_state` by hand and used `app._views` (pyright-protected access). Reworked to the production-shaped scenario: apply the ban before the app is built so `active_state` starts True at construction (matching on_mount's picker timing, per the plan's context note).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 17-11 can build on the save-first `set_link_mode` order and assert it (per RUN-LEDGER row 37); `move_link_mode` is the seam 17-11's warning-clear work sits next to.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
