---
phase: 17-stop-the-bleeding
plan: "11"
subsystem: settings
tags: [settings-json, error-handling, utf-8, tui-warnings, tdd]

requires:
  - phase: 17-stop-the-bleeding/08
    provides: SettingsStore.set_link_mode save-first order (save, then live mode)
  - phase: 17-stop-the-bleeding/10
    provides: _hermetic_route pilot helper in tests/test_setup.py
provides:
  - "LoadedSettings(settings, warning) and load_settings(path) -> LoadedSettings (single read+parse)"
  - "SettingsStore(..., warning=None) with a read-only warning property (the invalid-on-disk flag)"
  - "setup.py threads the warning through _settings_store and _build_app into UnifiedApp(startup_warning=...)"
  - "UnifiedApp flushes the startup warning onto the first visible screen via the existing _pending_warnings queue; a dismissed first-run picker keeps it"
affects: [settings, wizard-app, setup-routes]

actuals:
  tokens: 55600
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Startup warning rides the existing T-15.6-13 _pending_warnings queue, never a side channel"

key-files:
  created: []
  modified:
    - installer/settings.py
    - setup.py
    - installer/wizard_app.py
    - tests/test_settings.py
    - tests/test_setup.py
    - tests/test_wizard_app.py

key-decisions:
  - "Warn only for invalid UTF-8 and invalid JSON (ValueError covers both); wrong shape, unknown link_mode and unreadable file keep today's no-warning behaviour (RUN-LEDGER 17-11 row)"
  - "One read: json.loads(path.read_text(encoding='utf-8')); the rejected separate settings_warning probe stays rejected"
  - "set_link_mode clears the warning LAST (save, assign, clear) so a failed save keeps flag and live mode (review cycle 2 MEDIUM)"
  - "Base-view flush defers with call_later, not call_after_refresh: the repaint hook does not fire from inside on_mount before the default screen exists (tracer test decided)"

patterns-established:
  - "Damaged user state costs a warning, never the app and never the file: launch never writes over an invalid settings.json; only set_link_mode may rewrite it"

requirements-completed: [SAFE-08]

coverage:
  - id: D1
    description: "An invalid-UTF-8 or invalid-JSON settings.json launches to the first screen with a warning and the bytes on disk are unchanged after launch with a dismissed first-run picker"
    requirement: SAFE-08
    verification:
      - kind: e2e
        ref: "tests/test_setup.py#test_invalid_settings_file_launches_to_the_first_screen_with_a_warning[invalid-utf8|invalid-json]"
        status: pass
      - kind: unit
        ref: "tests/test_settings.py#test_load_settings_invalid_utf8_returns_defaults_and_a_warning"
        status: pass
    human_judgment: false
  - id: D2
    description: "The invalid-on-disk flag clears only on a successful user set_link_mode; a failed save keeps both the flag and the old live mode"
    requirement: SAFE-08
    verification:
      - kind: unit
        ref: "tests/test_settings.py#test_settings_store_keeps_the_warning_until_a_successful_set_link_mode + test_a_failed_set_link_mode_keeps_the_warning_and_the_live_mode"
        status: pass
    human_judgment: false
  - id: D3
    description: "The startup warning lands on a non-base initial view (doctor/fix/uninstall/guard) and survives a dismissed first-run picker"
    requirement: SAFE-08
    verification:
      - kind: e2e
        ref: "tests/test_wizard_app.py#test_startup_warning_lands_on_a_non_base_initial_view + test_dismissed_first_run_picker_keeps_the_startup_warning"
        status: pass
    human_judgment: false

duration: 38min
completed: 2026-10-14
status: complete
---

# Plan 17-11 Summary

**A damaged settings.json now costs the user a warning on the first screen — never a crash on any route and never a rewrite of their file — via a single-read `LoadedSettings(settings, warning)` contract threaded through `SettingsStore` and `UnifiedApp(startup_warning=...)`.**

## What was built

### Task 1 — invalid settings.json launches to the first screen with a warning, byte-identical (commit `4b3d8ea`)
- `installer/settings.py`: frozen `LoadedSettings(settings, warning=None)`; `load_settings(path) -> LoadedSettings` keeps ONE read (`json.loads(path.read_text(encoding="utf-8"))`), `except OSError` → defaults/no warning (today's behaviour), `except ValueError` (covers `UnicodeDecodeError` and `json.JSONDecodeError`) → defaults plus a warning naming the path; wrong shape / unknown link_mode return no warning (RUN-LEDGER 17-11 row). Docstrings updated to the three outcomes.
- `SettingsStore` gains `warning: str | None = None` and a read-only `warning` property; construction still writes nothing.
- `setup.py`: `_settings_store` builds the store with `warning=loaded.warning` (return shape and six callers unchanged); `_build_app` passes `startup_warning=settings.warning if settings is not None else None`.
- `installer/wizard_app.py`: `UnifiedApp.__init__` gains `startup_warning`, queues it on the existing `_pending_warnings` list; `on_mount` flushes to the catalog for the base view (deferred with `call_later` when the default screen is not yet mounted) and `show_view` already flushes for non-base views.
- All existing `load_settings` assertions updated mechanically to `.settings`; `test_not_json_returns_never_chosen` also asserts the warning names the path.
- TDD RED evidence (launch test, before implementation): `AssertionError: assert '/tmp/.../settings.json' in ''` — `CatalogScreen().status.text` empty; both parametrized ids failed. Unit RED: `ImportError: cannot import name 'LoadedSettings'`.

### Task 2 — flag clears only on a user change, shows on a non-base first view, survives the dismissed picker (commit `818e174`)
- `SettingsStore.set_link_mode`: 17-08's order kept, warning clear added last (`save_settings(...)` → `self._link_mode = value` → `self._warning = None`), so a failed save keeps both the flag and the old live mode (review cycle 2 MEDIUM).
- `_first_link_mode_picked`'s dismissed branch prepends `self._startup_warning` to the "Link mode unchanged" message joined with `" · "` (the same separator `_flush_pending_warnings` uses).
- `missing file` and `JSON null` tests now assert `warning is None`; wrong-shape/tampered tests carry no warning assertion.
- `_app(...)` in tests/test_wizard_app.py forwards `startup_warning`.

## TDD RED evidence (trimmed)
- Launch test (parametrized invalid-utf8/invalid-json): `assert '/tmp/.../settings.json' in ''` → both FAILED before implementation.
- `test_settings_store_keeps_the_warning_until_a_successful_set_link_mode`: `TypeError: unexpected keyword argument 'warning'` before implementation.
- `test_dismissed_first_run_picker_keeps_the_startup_warning`: `'Link mode unchanged; this run uses centralized. ...'.startswith('w · ')` → False before implementation.

## Verify-command results
- `uv run pytest tests/test_setup.py tests/test_settings.py -q --no-cov -k "invalid_settings_file_launches or invalid_utf8_returns_defaults"` → 3 passed (2 ids + 1 unit).
- `uv run pytest tests/test_settings.py tests/test_setup.py tests/test_wizard_app.py -q --no-cov` → all green.
- Task 2 `-k` run → 8 passed (gate: ≥7).
- `make validate` → pass; `make test` → 3541 passed, 4 skipped, coverage 95.91% (gate 90%).
- Acceptance greps: `class LoadedSettings` = 1; non-comment reads in settings.py = 1; `load_settings(` in setup.py = 1; `startup_warning` in wizard_app.py = 4; `def warning` = 1; set_link_mode ordering gate prints `save_settings(|self._link_mode = value|self._warning = None`; `warning=` inside `load_settings` = 1; wrong-shape/tampered warning mentions = 0/0; `startup_warning` in tests/test_wizard_app.py = 7.

## Deviations from the plan
- None in scope or behaviour. One mechanism detail the plan left to the tracer test: the base-view flush defers with `self.call_later(...)` rather than `self.call_after_refresh(...)` — the repaint hook never fired from inside `on_mount` before the default screen existed (proven by the failing tracer, then fixed and commented in `installer/wizard_app.py`).

## Issues for the orchestrator
- None. Pre-existing signature-pinning test `test_unified_app_signature_carries_no_disk_pressure_parameter` was extended with the new `startup_warning` parameter (same file, same commit as Task 1).
