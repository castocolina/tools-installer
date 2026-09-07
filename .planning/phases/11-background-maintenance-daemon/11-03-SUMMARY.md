---
phase: 11-background-maintenance-daemon
plan: 03
subsystem: ui
tags: [textual, policies-screen, modal, launchd, daemon]

# Dependency graph
requires:
  - phase: 11-background-maintenance-daemon
    provides: "installer/daemon.py's last_run_summary/read_schedule mechanism (11-01) and installer/policy.py's daemon_policy factory with Policy.log_path/set_schedule/read_schedule (11-02)"
provides:
  - "installer/wizard_app.py::PoliciesScreen — policy-aware Effect-column cell, a daemon-accurate _policy_detail entry, and persistent 'last run'/'scheduled daily at HH:MM' lines guarded by their own local try/except on every normal render"
  - "installer/wizard_app.py::PoliciesScreen — the l binding/action_toggle_log, toggling #policy-detail between the normal detail and a defensively-read log tail for any policy carrying a log_path"
  - "installer/wizard_app.py::TimePickerScreen — a ModalScreen[str | None] quantized 30-minute time-of-day picker with valid, letter-prefixed widget ids and its own bounded/centered DEFAULT_CSS"
  - "installer/wizard_app.py::PoliciesScreen — the t binding/action_pick_time, gated on active+set_schedule, routing a picked slot through ui_common.run_live"
affects: [11-04-composition-and-on-by-default]

# Actuals (#2632)
actuals:
  tokens: 5640
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A second, independent try/except (OSError, ValueError, UnicodeDecodeError) guard directly around installer.daemon.last_run_summary/policy.read_schedule call sites inside _policy_detail, on top of installer/daemon.py's own total/never-raising guarantee — belt-and-suspenders against a future regression, applied on every normal render (mount, row-highlight), not only the new l action."
    - "TimePickerScreen's widget-id/display-value split: a letter-prefixed, colon-free id (time-HH-MM) for Textual identifier validity, with the plain HH:MM string kept only as the Label's own display text and reconstructed on selection by reversing the transform — the modal's own outer dismiss-value contract (an HH:MM string) never changes."
    - "action_pick_time threads the already-null-checked set_schedule closure into _time_picked as its own parameter (never re-reading policy.set_schedule inside the callback), removing a structurally-unreachable None branch that pyright would otherwise require and coverage would otherwise flag."

key-files:
  created: []
  modified:
    - installer/wizard_app.py
    - tests/test_wizard_app.py
    - tests/test_policies_e2e.py

key-decisions:
  - "_fake_policy in tests/test_wizard_app.py gained optional id/log_path/set_schedule/read_schedule kwargs (defaulting to the prior ban-shaped behavior) rather than a parallel fixture, per the plan's own read_first instruction — every pre-existing call site is unaffected."
  - "tests/test_policies_e2e.py's _daemon_app now returns (app, plist_path, log_path) instead of (app, plist_path), and a new _daemon_policy_for_test helper factors out the real daemon_policy construction so Task 3's e2e test and the 80-column fit check can both build one without duplicating the plist/log/wrapper/script path wiring. The one pre-existing 11-02 call site was updated to unpack the new log_path (discarded via _log_path) rather than leaving a second, parallel builder function."
  - "The 'enable this policy first' status message for pressing t on an inactive policy is new copy (there is no pre-existing exact string to reuse verbatim), written to mirror the tone and placement of the existing 'Install required tool(s) first...' message per the plan's own instruction, rather than literally reusing that unrelated wording."

patterns-established:
  - "Defense-in-depth for managed-file reads inside a screen's own render path: a second local guard directly around a mechanism-layer function that is already total/never-raising, so a regression in that lower-layer guarantee (or an input shape it does not yet anticipate) still cannot crash the whole screen."

requirements-completed: [REQ-launchd-prune-policy, REQ-daemon-log-diagnostics]

coverage:
  - id: D1
    description: "PoliciesScreen's Effect-column cell and _policy_detail's daemon:prune-tmpdir entry render accurate, daemon-specific copy for any policy with log_path set, replacing the generic 'shell config'/'reversible shell policy' fallback; every pre-existing policy (log_path is None) renders byte-identically to before this plan."
    requirement: "REQ-daemon-log-diagnostics"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_existing_policies_render_byte_identical_effect_and_detail"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_daemon_policy_detail_uses_accurate_daemon_copy"
        status: pass
    human_judgment: false
  - id: D2
    description: "_policy_detail appends a 'last run: ...' line (installer.daemon.last_run_summary) and a persistent 'scheduled daily at HH:MM' line (policy.read_schedule(), read fresh on every render) for any policy that offers them, each guarded by its own local try/except (OSError, ValueError, UnicodeDecodeError) so a corrupt log or plist never crashes the normal mount/row-highlight render path, not only the l action."
    requirement: "REQ-daemon-log-diagnostics"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_policy_with_log_file_shows_last_run_and_l_toggles_raw_content, #test_policy_with_read_schedule_shows_persistent_schedule_line, #test_normal_detail_render_is_defensive_against_corrupt_schedule_and_log, #test_normal_detail_render_defends_against_last_run_summary_raising"
        status: pass
      - kind: e2e
        ref: "tests/test_policies_e2e.py#test_daemon_policy_time_picker_rewrites_the_real_plist_and_updates_detail"
        status: pass
    human_judgment: false
  - id: D3
    description: "A new l binding/action_toggle_log toggles #policy-detail between the normal detail and the log file's last 20 lines for the highlighted policy row only (no-op for a policy with no log_path), defensively handling a missing file ('log file does not exist yet') and an unreadable/invalid-UTF-8 file ('log could not be read: ...') without ever raising. No new top-level Diagnostics view is introduced."
    requirement: "REQ-daemon-log-diagnostics"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_policy_with_log_path_and_no_log_file_shows_no_last_run_and_placeholder, #test_toggle_log_is_noop_when_policy_has_no_log_path, #test_toggle_log_against_invalid_utf8_shows_read_failure_placeholder"
        status: pass
      - kind: e2e
        ref: "tests/test_policies_e2e.py#test_daemon_policy_time_picker_rewrites_the_real_plist_and_updates_detail"
        status: pass
    human_judgment: false
  - id: D4
    description: "TimePickerScreen (ModalScreen[str | None]) offers 48 quantized 30-minute slots as valid Textual identifiers (time-HH-MM ids, HH:MM display text) with its own bounded/centered DEFAULT_CSS; a new t binding opens it only for an active policy with set_schedule set, shows a status message instead for an inactive one, and routes a picked slot's set_schedule(hour, minute) call through ui_common.run_live, surfacing failure on the status line and refreshing the detail panel on success."
    requirement: "REQ-launchd-prune-policy"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_time_picker_widget_ids_are_all_valid_textual_identifiers, #test_time_picker_is_noop_when_policy_has_no_set_schedule, #test_time_picker_shows_enable_first_message_for_inactive_policy, #test_time_picker_selecting_a_slot_calls_set_schedule_with_parsed_hour_minute, #test_time_picker_escape_cancels_without_calling_set_schedule, #test_time_picker_list_view_does_not_overflow_smallest_tested_terminal, #test_time_picker_set_schedule_failure_surfaces_on_status_line"
        status: pass
    human_judgment: false
  - id: D5
    description: "A real daemon_policy, enabled via space then rescheduled via t in a headless pilot, actually rewrites the real tmp_path-scoped plist file's StartCalendarInterval (read back via plistlib, never a mock) and the detail panel immediately shows the matching schedule line; l shows a fabricated real log file's content; the 80-column detail-panel fit check now includes the daemon policy's longer copy."
    requirement: "REQ-launchd-prune-policy"
    verification:
      - kind: e2e
        ref: "tests/test_policies_e2e.py#test_daemon_policy_time_picker_rewrites_the_real_plist_and_updates_detail, #test_every_policy_detail_fits_the_panel_at_80_columns"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-09-07
status: complete
---

# Phase 11 Plan 03: Policies Detail-Panel UI Summary

**"Last run"/persistent-schedule lines, daemon-accurate copy, a defensive `l` log-view toggle, and a 48-slot `TimePickerScreen` modal (`t` binding, routed through `run_live`) added to the existing `PoliciesScreen` — zero new top-level views.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-07T01:26:00-03:00 (approx., first read of required context)
- **Completed:** 2026-09-07T01:46:36-03:00
- **Tasks:** 3
- **Files modified:** 3 (`installer/wizard_app.py`, `tests/test_wizard_app.py`, `tests/test_policies_e2e.py`)

## Accomplishments
- `PoliciesScreen.on_mount`'s Effect-column cell is now policy-aware: `"scheduled job: {description}"` for any policy with `log_path is not None`, byte-identical `"shell config: {description}"` for every other policy — pinned by a regression test.
- `_policy_detail`'s `details` dict gains a `"daemon:prune-tmpdir"` entry with accurate, daemon-specific copy (what the LaunchAgent runs, its graceful `fd`/`rg` degradation, and that disabling only unregisters the LaunchAgent), replacing the generic `"Space toggles this reversible shell policy."` fallback for that policy.
- `_policy_detail` appends a `"last run: ..."` line (`installer.daemon.last_run_summary`) and a persistent `"scheduled daily at HH:MM"` line (`policy.read_schedule()`, read fresh on every render) for any policy that offers them — each wrapped in its own local `try/except (OSError, ValueError, UnicodeDecodeError)`, applied on the NORMAL render path (mount, row-highlight), not only the new `l` action, as a second, independent guard on top of `installer/daemon.py`'s own already-total mechanism-tier functions.
- A new `l` binding (`action_toggle_log`) toggles `#policy-detail` between the normal detail text and the log file's last 20 lines for the highlighted policy row only; a missing log renders `"log file does not exist yet"` and an unreadable/invalid-UTF-8 log renders `"log could not be read: {exc}"` — never raising. `self._log_view` is explicitly initialized in `PoliciesScreen.__init__` and reset on every row highlight.
- `TimePickerScreen(ModalScreen[str | None])` offers 48 quantized 30-minute slots via `ListView`/`ListItem`, each with a letter-prefixed, colon-free widget id (`time-HH-MM`) — a raw `"HH:MM"` id is an invalid Textual identifier, live-verified — while the display text stays the plain `"HH:MM"` string; `on_list_view_selected` reverses the id transform so the modal's own dismiss-value contract is unchanged. It defines its own bounded (`height: 20`), centered `DEFAULT_CSS`, never relying on `NavScreen`'s class-scoped selector.
- A new `t` binding (`action_pick_time`) is a no-op when the highlighted policy has no `set_schedule`; shows a status message instead of opening the modal when the policy is not yet active; otherwise pushes `TimePickerScreen` and routes a picked slot's `policy.set_schedule(hour, minute)` call through `ui_common.run_live` — never directly from the modal's dismissal callback — surfacing failure on the status line and refreshing the detail panel with the new schedule on success.
- A real, headless end-to-end test drives a real `daemon_policy` through enable (`space`) → reschedule (`t`, picking a slot) → log view (`l`): the picked slot actually rewrites the real, `tmp_path`-scoped plist file's `StartCalendarInterval` (read back via `plistlib`, never a mock), the detail panel immediately reflects the new schedule, and a fabricated real log file's content shows through `l`.

## Task Commits

Each task was committed via a RED/GREEN TDD pair (per `tdd="true"`):

1. **Task 1: "Last run"/schedule lines, daemon-accurate copy, and the defensive log-view toggle**
   - `7f2548a` test(11-03): add failing tests for last-run/schedule lines and log-view toggle (RED)
   - `b760da3` feat(11-03): implement last-run/schedule lines, daemon copy, and log-view toggle (GREEN)
2. **Task 2: `TimePickerScreen` modal (valid ids) + `t` binding routed through `run_live`**
   - `8e1955a` test(11-03): add failing tests for TimePickerScreen and the t binding (RED)
   - `43460af` feat(11-03): add TimePickerScreen modal and t binding routed through run_live (GREEN)
3. **Task 3: e2e pilot coverage against a real `daemon_policy`**
   - `613ac15` test(11-03): add e2e pilot coverage for the time picker and log view (real daemon_policy)

_Note: Task 3 is a pure integration proof of behavior Tasks 1 and 2 already built (mirroring 11-02's own Task 3 precedent) — it passed on its first run with zero production changes, so no corresponding `feat(...)` commit exists. See "TDD Gate Compliance" below._

## Files Created/Modified
- `installer/wizard_app.py` — `PoliciesScreen`'s policy-aware Effect column, daemon-accurate `_policy_detail` copy, defensively-guarded "last run"/schedule lines, the `l` binding/`action_toggle_log`/`_log_tail`, `TimePickerScreen`, and the `t` binding/`action_pick_time`/`_time_picked`
- `tests/test_wizard_app.py` — 18 new tests covering Tasks 1 and 2, plus `_fake_policy`'s extended `id`/`log_path`/`set_schedule`/`read_schedule` kwargs
- `tests/test_policies_e2e.py` — a new real end-to-end round trip through a real `daemon_policy`, `_daemon_app`/`_daemon_policy_for_test` refactored to expose the daemon policy builder for reuse, and the daemon policy added to the 80-column detail-panel fit check

## Decisions Made
- Extended `_fake_policy` (rather than adding a sibling fixture) with optional `id`/`log_path`/`set_schedule`/`read_schedule` kwargs, all defaulting to the prior ban-shaped behavior — every pre-existing call site (dozens across the file) is unaffected.
- Refactored `tests/test_policies_e2e.py`'s `_daemon_app` to return `(app, plist_path, log_path)` instead of `(app, plist_path)`, and factored the real `daemon_policy` construction into a new `_daemon_policy_for_test` helper so Task 3's e2e test and the 80-column fit check can both build one without duplicating the plist/log/wrapper/script path wiring. The one pre-existing 11-02 call site was updated to unpack the new `log_path` (discarded as `_log_path`).
- `action_pick_time` threads the already-null-checked `set_schedule` closure into `_time_picked` as its own parameter, rather than re-reading `policy.set_schedule` inside the callback — this removes a structurally-unreachable `None` branch pyright would otherwise require narrowing around, and which coverage would otherwise flag as an unhit branch with no legitimate way to exercise it.
- The "enable this policy first" status message shown when `t` is pressed on an inactive policy is new copy (there is no pre-existing exact string for this exact situation to reuse verbatim) — written to mirror the tone and placement of the existing "Install required tool(s) first..." message per the plan's own instruction.

## Deviations from Plan

None — plan executed exactly as written. All three tasks' `<behavior>`/`<action>` requirements were implemented as specified, including every defensive-guard and cycle 1/2/3 review-fix detail called out in `<design_decisions>` (valid Textual ids, `run_live` routing, the persistent schedule line, daemon-accurate copy, defensive log/schedule reads on the normal render path, explicit `__init__` initialization of `self._log_view`, and `TimePickerScreen`'s own bounded `DEFAULT_CSS`).

## Issues Encountered

None. `rtk proxy` was used for every verification command per this environment's documented quirk (the same one noted in 11-01/11-02's own SUMMARYs), and reproduced full, unfiltered `pytest`/`make validate`/`make test` output throughout.

## TDD Gate Compliance

Tasks 1 and 2 (both `tdd="true"`) each show a `test(...)` commit (RED, confirmed failing against the pre-task tree before being committed) immediately followed by a `feat(...)` commit (GREEN, confirmed passing). Task 1's RED state was verified by reverting `installer/wizard_app.py` to its pre-plan content via `git checkout` while the new tests stayed staged, confirming 5 of the new tests failed for the right reason (missing behavior), then restoring the implementation. Task 2's RED state was verified the same way against Task 1's own GREEN tree, confirming an `ImportError` for the not-yet-defined `TimePickerScreen`. Task 3 (`tdd="true"`) is a pure end-to-end integration proof of behavior Tasks 1 and 2 already built — it produced one `test(...)` commit that passed on its first run, with no corresponding `feat(...)` commit, because no production code needed to change (identical shape to 11-02's own Task 3).

## User Setup Required

None — no external service configuration required. Every test in this plan uses an injected fake `run` (`_FakeDaemonRun`, from 11-02) or a plain fake `Policy`; no real `launchctl` is ever invoked.

## Next Phase Readiness
- `installer/wizard_app.py::PoliciesScreen`/`TimePickerScreen` are ready for 11-04's composition root to wire a real `daemon_policy(...)` into `setup.py`'s macOS-only policy list — this plan's UI additions require no further changes to consume whatever `Policy` 11-04 constructs, since they key off the already-additive `log_path`/`set_schedule`/`read_schedule`/`hard_requires` fields 11-02 introduced.
- No blockers identified. `installer/daemon.py` and `installer/policy.py` remain untouched by this plan, exactly as scoped.

## Self-Check: PASSED

- FOUND: `installer/wizard_app.py`
- FOUND: `tests/test_wizard_app.py`
- FOUND: `tests/test_policies_e2e.py`
- FOUND: `.planning/phases/11-background-maintenance-daemon/11-03-SUMMARY.md`
- FOUND commit `7f2548a` (test(11-03): add failing tests for last-run/schedule lines and log-view toggle (RED))
- FOUND commit `b760da3` (feat(11-03): implement last-run/schedule lines, daemon copy, and log-view toggle (GREEN))
- FOUND commit `8e1955a` (test(11-03): add failing tests for TimePickerScreen and the t binding (RED))
- FOUND commit `43460af` (feat(11-03): add TimePickerScreen modal and t binding routed through run_live)
- FOUND commit `613ac15` (test(11-03): add e2e pilot coverage for the time picker and log view (real daemon_policy))
- VERIFIED: `uv run pytest tests/test_wizard_app.py tests/test_policies_e2e.py -q` passes in full
- VERIFIED: `uv run pytest -q` (full suite) exits 0 (1445 passed, 1 skipped)
- VERIFIED: `make validate && make test` passes on the committed tree (1445 passed, 1 skipped, 99.43% coverage)
- VERIFIED: every phase-level `<verification>` command from 11-03-PLAN.md passes exactly as specified (`TimePickerScreen` importable, all 48 ids construct without `BadIdentifier`, `TimePickerScreen` defines its own `DEFAULT_CSS`)

---
*Phase: 11-background-maintenance-daemon*
*Completed: 2026-09-07*
