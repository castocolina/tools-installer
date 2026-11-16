---
phase: 17-stop-the-bleeding
plan: "10"
subsystem: ui
tags: [textual, tui, setup-wizard, exit-codes, composition-root, pilot-tests]

requires:
  - phase: 17-stop-the-bleeding
    provides: "17-07's Summary.has_failure and install_summary on UnifiedApp; _execute_inputs seam"
provides:
  - "_build_app(..., unattended: bool = False) that always builds ExecuteInputs itself (the optional execute parameter is gone, D-12)"
  - "_session_exit_code(app) -> int — the one exit rule, called by all four non-setup TUI routes and _run_interactive_wizard"
  - "tests/test_setup.py::_hermetic_route(monkeypatch, tmp_path) — reusable hermetic route-pilot setup (plan 17-11 reuses it)"
  - "Per-route execute tests (5 ids), per-route exit-code tests, empty-Enter test; test_accepting_the_catalog_without_execute_still_exits_with_ids deleted"
affects: [17-11, wizard-routes, doctor, fix, uninstall, guard]

actuals:
  tokens: 22000
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Route pilots run the real app under Textual Pilot with all isolation patched in one helper (_hermetic_route), install replaced at the _execute_inputs seam"
    - "One exit rule: _session_exit_code reads Summary.has_failure; no route invents its own"

key-files:
  created: []
  modified:
    - setup.py
    - tests/test_setup.py
    - tests/test_wizard_app.py

key-decisions:
  - "D-12 applied: _build_app builds ExecuteInputs through _execute_inputs from its own tools/platform/_current_link_mode/unattended/one shared probe; execute= parameter removed so no route can build an app that cannot execute"
  - "The install closure for route pilots is replaced by wrapping setup._execute_inputs (the seam itself), never by reaching into ExecuteScreen"

patterns-established:
  - "_hermetic_route: scratch HOME (_sandbox) + empty PATH + systemd_available False + Linux platform + one-tool fake catalog + seeded settings.json + fake TTY + recorded install; returns the recorder ids"

requirements-completed: [SAFE-09, SAFE-05]

coverage:
  - id: D1
    description: "_build_app always builds ExecuteInputs itself; the execute parameter no longer exists"
    requirement: SAFE-09
    verification:
      - kind: unit
        ref: "tests/test_setup.py#test_build_app_always_builds_execute"
      - kind: unit
        ref: "tests/test_setup.py#test_build_app_has_no_execute_parameter"
      - kind: other
        ref: "grep acceptance: no 'execute: ExecuteInputs' in _build_app signature, no 'if execute is not None'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Enter on a catalog selection executes it on every TUI route (setup, doctor, fix, uninstall, guard)"
    requirement: SAFE-09
    verification:
      - kind: automated_ui
        ref: "tests/test_setup.py#test_every_tui_route_executes_the_accepted_selection"
        status: pass
    human_judgment: false
  - id: D3
    description: "Doctor/fix/uninstall/guard routes return 1 on install_summary.has_failure, else 0; the setup route decides through the same _session_exit_code"
    requirement: SAFE-05
    verification:
      - kind: unit
        ref: "tests/test_setup.py#test_tui_routes_exit_1_when_the_session_failed"
        status: pass
    human_judgment: false
  - id: D4
    description: "Enter with nothing selected shows 'Select at least one tool, or press q to quit.' and runs nothing"
    requirement: SAFE-09
    verification:
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_enter_with_nothing_selected_runs_nothing"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 10 Summary

**Every TUI route now builds an app that can execute an accepted selection and reports its outcome honestly in the exit code; `_build_app` owns ExecuteInputs (D-12), `_session_exit_code` is the one exit rule, and `_hermetic_route` gives all route pilots their isolation.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments
- `_build_app(tools, platform, *, ..., unattended: bool = False, ...)` builds `execute` itself via `_execute_inputs` (link mode read live through `_current_link_mode`), then rebinds `version_refresh`/`updates` unconditionally; the optional `execute` parameter and its `None` guard are gone.
- `_run_interactive_wizard` no longer builds its own cache/probe — `_build_app` builds one shared timer cache and disk-pressure probe when omitted (shared-cache test still sees exactly one `_timer_state_cache` call).
- Added `_session_exit_code(app) -> int` and returned it from the TTY branches of `_run_doctor`, `_run_fix`, `_run_uninstall`, `main`'s guard branch, and `_run_interactive_wizard` (replacing its `has_failure` branch; troubleshooting still rendered on 1).
- Added `_hermetic_route(monkeypatch, tmp_path)` on top of `_sandbox` — the single hermetic setup for route pilots (scratch HOME, empty PATH, `systemd_available -> False`, Linux platform, one-tool fake catalog, seeded settings.json, fake TTY, install recorded at the `_execute_inputs` seam).
- Tests: `test_build_app_always_builds_execute`, `test_build_app_has_no_execute_parameter`, `test_every_tui_route_executes_the_accepted_selection` (5 ids: setup/doctor/fix/uninstall/guard, each navigating to the catalog via `show_view(BASE_VIEW)` before selecting), `test_tui_routes_exit_1_when_the_session_failed` (4 argv x failed/clean/None summaries), `test_enter_with_nothing_selected_runs_nothing`; deleted `test_accepting_the_catalog_without_execute_still_exits_with_ids` and Task 1's interim doctor-route test.

## Task Commits

1. **Task 1: `_build_app` builds execute itself; doctor route runs an accepted selection** - `cc871b1` (feat)
2. **Task 2: every route executes and reports its exit code; empty Enter runs nothing** - `edaa4db` (feat)
3. **Plan summary** - this commit (docs)

## TDD RED evidence (trimmed)

Task 1 (`uv run pytest ... -k "always_builds_execute or has_no_execute_parameter or doctor_route_executes or shares_one_cache or live_set_link_mode"`):
```
FAILED tests/test_setup.py::test_build_app_always_builds_execute - assert None is not None
FAILED tests/test_setup.py::test_build_app_has_no_execute_parameter - assert ...
FAILED tests/test_setup.py::test_doctor_route_executes_the_accepted_selection
FAILED tests/test_setup.py::test_live_set_link_mode_rereads_fix_preview_apply_execute_and_policies
```

Task 2 (`-k "every_tui_route or routes_exit_1 or nothing_selected_runs_nothing"`):
```
FAILED tests/test_setup.py::test_tui_routes_exit_1_when_the_session_failed[argv0..argv3]
E  AssertionError: assert 0 == 1   (where 0 = setup.main(['--guard']) etc.)
4 failed, 6 passed
```
(The five route-execute ids and the empty-Enter test already passed at RED time — Task 1 had wired execution; the remaining failure was the exit code, which Task 2's production change fixes.)

## Verify-command results

- Task 1: `uv run pytest tests/test_setup.py -q --no-cov -k "..."` → 5+ passed; `uv run pytest tests/test_setup.py tests/test_wizard_app.py -q --no-cov` → green.
- Task 2: `-k "every_tui_route or routes_exit_1 or nothing_selected_runs_nothing"` → 10 passed; `tests/test_setup.py tests/test_wizard_app.py tests/test_catalog_tui.py` → 587 passed.
- Final tree: `make validate` all checks passed (ruff, format, pyright strict, bandit, vulture, shellcheck); `make test` → 3517 passed, 4 skipped, coverage 95.90% (gate 90%).
- Acceptance greps all hold: no `execute: ExecuteInputs` in `_build_app` signature; `unattended: bool = False` present; no `if execute is not None`; no `_timer_state_cache(` in `_run_interactive_wizard`; `_session_exit_code` defined once and called 5 times (6 grep hits incl. definition); deleted tests grep to 0; `_hermetic_route(` count 3; 5 parametrized route ids pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule — existing test contract] `_capture_app` fakes needed a class-level `install_summary`**
- **Found during:** Task 2 (full-file run)
- **Issue:** Making `install_summary` a pure instance attribute broke three existing tests that `monkeypatch.setattr` the class attribute (`test_interactive_wizard_exits_1_when_the_session_has_a_failure`, `test_interactive_wizard_exits_0_when_the_session_is_clean`, `test_failed_update_exits_1`), and `_DummyApp` lacked the attribute for `_session_exit_code`.
- **Fix:** Kept `install_summary: Summary | None = None` as a class attribute on both fakes; `_capture_app` sets the instance attribute only when a summary is injected.
- **Files modified:** tests/test_setup.py
- **Verification:** full `tests/test_setup.py tests/test_wizard_app.py tests/test_catalog_tui.py` green
- **Committed in:** edaa4db (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (existing-test compatibility, within the plan's files_modified)
**Impact on plan:** No scope creep; all changes inside the plan's declared files.

## Issues Encountered
- `pytest` parametrization reran `_hermetic_route` within one exit-code test on the same `tmp_path`; the helper's `empty_bin.mkdir()` needed `exist_ok=True`.
- The pilot's first `await pilot.press("enter")` after `show_view(BASE_VIEW)` needed one `await pilot.pause()` for browser focus before the accept keypress registered.

## Next Phase Readiness
- `_hermetic_route` is ready for plan 17-11's route pilots to reuse as-is.
- No blockers.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
