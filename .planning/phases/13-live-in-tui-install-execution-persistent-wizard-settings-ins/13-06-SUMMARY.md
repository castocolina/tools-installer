---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 06
subsystem: installer-tui
tags: [settings, link-mode, policies, first-run, wave-4]

requires:
  - phase: 13
    provides: "13-03 SettingsStore/resolve_link_mode/link_mode_needs_choice, 13-04 UnifiedApp execute seam, 13-05 ExecuteScreen"
provides:
  - setup.py resolves link mode from SettingsStore; _resolve_link_mode deleted
  - Live re-read of link mode in ban_policy, tweak_policy, Doctor preview, PATH wiring
  - PoliciesScreen m picker (LinkModeScreen) with D-05.3 dismissal status
  - First-run in-app LinkModeScreen, status posted to the visible AppScreen
affects: ["13-07 architecture.md and PRD record"]

actuals:
  tokens: 17244
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Link mode is a live SettingsStore read, never a launch-time snapshot"
    - "PoliciesScreen m picker mirrors TimePickerScreen + run_live (architecture rules 1-3)"
    - "First-run status target is self.screen when AppScreen else self._views.get(self.current_view) or self.catalog"
    - "--link-mode overrides for one run only; only the in-app picker persists (DD-3)"

key-files:
  created: []
  modified:
    - setup.py
    - installer/policy.py
    - installer/wizard_app.py
    - installer/ui_common.py
    - tests/test_setup.py
    - tests/test_policy.py
    - tests/test_wizard_app.py
    - tests/test_ui_common.py

key-decisions:
  - "Asked at most once per ANSWER, not once per machine: a dismissed picker stores nothing and the next launch prompts again (link_mode_needs_choice's contract)."
  - "No new VIEWS row: the picker lives on PoliciesScreen; the m key is registered in the policies actions string so the footer names it (rule 1)."
  - "First-run status lands on the visible AppScreen; the non-AppScreen arm uses the view registry, never a hard catalog fallback (T-13-17)."
  - "prompt_link_mode is passed only from make setup and make fix's interactive branch; --doctor/--uninstall/--guard/--all and no-TTY never see it (T-13-18)."

patterns-established:
  - "Installer-level settings that change while the app is running are live closures, not construction-time captures."
  - "A dismissed in-app picker always writes an explicit status naming what did not change and how to change it later (D-05.3)."

requirements-completed: ["D-04", "D-05"]

coverage:
  - id: D1
    description: "The link mode comes from a persisted file, never a pre-TUI questionary prompt, and every consumer re-reads the current value."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_setup.py#test_interactive_run_with_nothing_stored_opens_the_app_without_a_questionary_prompt
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_live_set_link_mode_rereads_fix_preview_apply_execute_and_policies
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_link_mode_flag_overrides_stored_split_without_rewriting_it
        status: pass
    human_judgment: false
  - id: D2
    description: "The link mode is visible and changeable from the Policies view; a cancelled picker says so (D-05.3)."
    requirement: D-05
    verification:
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_selecting_split_saves_and_sets_ok_status
        status: pass
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_link_mode_picker_escape_warns_and_does_not_call_the_setter
        status: pass
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_link_mode_setter_oserror_surfaces_and_leaves_the_line_unchanged
        status: pass
      - kind: other
        ref: "uv run python -c VIEW_BY_NAME['policies'].actions contains m; prints FOOTER-OK"
        status: pass
    human_judgment: false
  - id: D3
    description: "A fresh machine is asked once inside the app; dismissal explains on the visible screen, including make fix's Doctor view."
    requirement: D-05
    verification:
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_first_run_picker_is_the_last_modal_even_with_a_daemon_default
        status: pass
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_first_run_escape_explains_on_the_catalog
        status: pass
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_first_run_escape_on_make_fix_explains_on_the_doctor
        status: pass
      - kind: automated_ui
        ref: tests/test_wizard_app.py#test_dismissed_first_run_picker_persists_nothing
        status: pass
      - kind: unit
        ref: tests/test_setup.py#test_all_yes_and_no_tty_never_prompt_for_link_mode
        status: pass
    human_judgment: false

duration: 30 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 06: Persistent link-mode preference, asked once inside the app — Summary

**The pre-TUI questionary link-mode prompt is gone. The preference is persisted, honoured on later runs, overridable for one run by `--link-mode` without being rewritten, changeable from the Policies view, and every consumer re-reads it live — with every prompt outcome explained on the screen the user is actually looking at.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-09-14T08:26:30Z
- **Completed:** 2026-09-14T08:55:59Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- `setup.py` resolves link mode through `SettingsStore`; `_resolve_link_mode` is deleted. `ban_policy` / `tweak_policy` / Doctor preview / PATH wiring re-read the current value so a mid-session change cannot write aliases into a file nothing sources.
- `PoliciesScreen` exposes the mode and an `m` picker (`LinkModeScreen`) whose three labels are the retired questionary wording. Escape sets a warn status; `OSError` surfaces and leaves the line unchanged. The `VIEWS` policies row advertises `m`.
- First-run `prompt_link_mode=True` pushes `LinkModeScreen` last on mount. Dismissal stores nothing and posts the fallback explanation on the visible `AppScreen` (catalog or Doctor for `make fix`); `--all --yes` and no-TTY never see the picker.

## Task Commits

1. **Task 1: setup.py resolves the link mode from settings, and every consumer re-reads it live** — `5f0c730` (`feat(13-06): resolve link mode from settings, re-read live at apply`)
2. **Task 2: the link-mode picker on the Policies view** — `286acc5` (`feat(13-06): add link-mode picker on the Policies view`)
3. **Task 3: ask once, on first run, inside the app** — `f8b1562` (`feat(13-06): ask link mode once, inside the app, on first run`)

**Plan metadata:** this SUMMARY plus STATE/ROADMAP.

## Files Created/Modified

- `setup.py` — `_settings_store`; `_resolve_link_mode` removed; `_build_app` takes `settings=` and `prompt_link_mode=`; live reader for every link-mode consumer.
- `installer/policy.py` — `ban_policy.apply_rc_paths` and `tweak_policy.ensure_sourced_from` accept a value or a zero-argument callable.
- `installer/wizard_app.py` — `LinkModeScreen`; `PoliciesScreen.action_pick_link_mode` / `_link_mode_picked`; `UnifiedApp.prompt_link_mode` / `_first_link_mode_picked`; Doctor/UnifiedApp `fix_preview` callable.
- `installer/ui_common.py` — policies `View.actions` gains `m link mode`.
- `tests/test_setup.py`, `tests/test_policy.py`, `tests/test_wizard_app.py`, `tests/test_ui_common.py` — stored-settings fixtures, Pilot picker/first-run cases, footer assertion.

## Decisions Made

- Once per answer, not once per machine: dismiss stores nothing and the next launch prompts again.
- No seventh view: the picker is folded into Policies; `m` is in the `VIEWS` row so the footer names it.
- Status target is the visible `AppScreen`; the fallback is `self._views.get(self.current_view) or self.catalog`.
- `--link-mode` never calls `set_link_mode` (DD-3).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `uv run rtk pytest` / `rtk pytest` collected zero tests (project-local rtk wrapper). Used `.venv/bin/pytest` for per-task verifies; `make test` uses `uv run pytest --cov` and passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 13-07 (architecture.md and PRD record, plus the full-suite phase gate). The first-run picker, Policies `m` binding, and live re-reads are the shipped surface 13-07 documents.

## Self-Check: PASSED

- Key files exist: `setup.py`, `installer/policy.py`, `installer/wizard_app.py`, `installer/ui_common.py`
- Commits: `git log --oneline --grep=13-06` returns `f8b1562`, `286acc5`, `5f0c730`
- `grep -c '_resolve_link_mode' setup.py` is 0; `def _settings_store` is 1; `questionary.select` is 1
- `grep -c 'self._views.get(self.current_view)' installer/wizard_app.py` is 1
- `grep -rl 'Binding("m"' installer/` names only `installer/wizard_app.py`
- `make validate` — passed
- `make test` — 2002 passed, 1 skipped, 95.34% coverage (floor 90%)

---
*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Completed: 2026-09-14*
