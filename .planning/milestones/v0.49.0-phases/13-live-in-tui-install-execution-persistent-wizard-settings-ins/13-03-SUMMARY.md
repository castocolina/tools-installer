---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 03
subsystem: installer-core
tags: [settings, persistence, link-mode, wave-1]

requires:
  - phase: 12
    provides: version_cache JSON envelope and atomic_write_text convention
provides:
  - Persisted wizard settings envelope at ~/.local/state/tools-installer/settings.json
  - Closed-set load_settings that degrades tampered or malformed input to never-chosen
  - resolve_link_mode / link_mode_needs_choice precedence (DD-3)
  - SettingsStore live owner that persists set_link_mode atomically
affects: ["13-06 settings wiring", "13-07 rule-5 adoption gate"]

actuals:
  tokens: 2550
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "JSON state envelope mirroring version_cache (version: 1 + atomic_write_text)"
    - "Two-outcome load contract: missing-or-null vs present-but-not-a-member, both Settings()"
    - "Flag overrides for one run; persist only via explicit SettingsStore.set_link_mode"

key-files:
  created:
    - installer/settings.py
    - tests/test_settings.py
  modified: []

key-decisions:
  - "Settings.link_mode=None is never-chosen, distinct from DEFAULT_LINK_MODE centralized."
  - "JSON null is the valid on-disk encoding of never-chosen; a number, list, object, or arbitrary string is a defect. Both land on Settings()."
  - "Closed-set membership against LINK_MODES is the T-13-01 mitigation; isinstance is folded into that branch, not a third outcome."
  - "An explicit --link-mode applies to that run only and never rewrites the stored preference (DD-3)."
  - "SettingsStore.set_link_mode does not catch OSError so run_live can surface it."

patterns-established:
  - "Wizard state lives next to versions.json and is written only through atomic_write_text."
  - "Precedence is a tested property of installer/, not an if-chain in setup.py."

requirements-completed: ["D-05"]

coverage:
  - id: D1
    description: "A link-mode choice survives between runs as a versioned JSON envelope written atomically."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_settings.py#test_save_then_load_round_trips_split
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_writing_twice_leaves_one_file_and_no_temp_sibling
        status: pass
    human_judgment: false
  - id: D2
    description: "A missing, unreadable, malformed, or tampered settings file degrades to never-chosen instead of propagating an arbitrary string."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_settings.py#test_tampered_link_mode_is_rejected
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_not_json_returns_never_chosen
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_wrong_json_shapes_return_never_chosen
        status: pass
      - kind: other
        ref: "load_settings('../../etc') and literal-null fixtures print REJECTED"
        status: pass
    human_judgment: false
  - id: D3
    description: "An explicit --link-mode flag is honoured for one run without overwriting the stored preference."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_settings.py#test_resolve_link_mode_flag_wins_over_stored
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_resolve_link_mode_stored_wins_over_default
        status: pass
      - kind: other
        ref: "resolve_link_mode one-liner prints PRECEDENCE-OK"
        status: pass
    human_judgment: false
  - id: D4
    description: "A caller can tell 'the user has never chosen' apart from 'the user chose centralized'."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_settings.py#test_settings_default_is_never_chosen
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_load_literal_null_fixture_is_never_chosen
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_save_empty_settings_writes_json_null
        status: pass
    human_judgment: false
  - id: D5
    description: "SettingsStore mutates live link_mode and persists it atomically; write errors propagate as OSError."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_settings.py#test_set_link_mode_is_live_and_persisted
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_set_link_mode_rejects_unknown_value
        status: pass
      - kind: unit
        ref: tests/test_settings.py#test_set_link_mode_propagates_oserror
        status: pass
    human_judgment: false

duration: 10 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 03: Persisted wizard settings envelope — Summary

**A versioned settings.json under ~/.local/state/tools-installer stores link_mode through the same atomic write path as versions.json, rejects tampered values, and exposes flag/stored/default precedence plus a live SettingsStore — with no TUI and no setup.py coupling.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-09-14T05:14:05Z
- **Completed:** 2026-09-14T05:23:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `installer/settings.py` round-trips `{"version": 1, "link_mode": ...}` through `atomic_write_text`. JSON `null` is never-chosen; a value outside `LINK_MODES` (including `"../../etc"`) degrades to `Settings()`.
- `resolve_link_mode` / `link_mode_needs_choice` encode DD-3 as tested keyword-only functions. `SettingsStore.set_link_mode` persists atomically and lets `OSError` propagate for `run_live`.

## Task Commits

1. **Task 1: The settings envelope** — `26e6d20` (`feat(13-03): persist wizard settings envelope`)
2. **Task 2: Precedence functions and SettingsStore** — `49a25aa` (`feat(13-03): add link-mode precedence and SettingsStore`)
3. **Plan metadata** — this SUMMARY plus STATE/ROADMAP.

## Files Created/Modified

- `installer/settings.py` — `LINK_MODES`, `DEFAULT_LINK_MODE`, `Settings`, `default_settings_path`, `load_settings`, `save_settings`, `resolve_link_mode`, `link_mode_needs_choice`, `SettingsStore`.
- `tests/test_settings.py` — 21 tests: envelope round-trip, two-way CLI-choices pin, two-outcome load contract, precedence, live store, OSError propagation.

## Decisions Made

- `None` on `Settings.link_mode` is never-chosen, not a collapse into `DEFAULT_LINK_MODE`.
- Load has two outcomes only: missing-or-null → `Settings()`; present-but-not-a-member → `Settings()`. The `isinstance` check is inside the membership branch.
- Flag honours DD-3: the caller that uses a flag must not also call `set_link_mode`.
- `set_link_mode` does not catch `OSError`; `run_live` is the one place a screen-triggered core mutation's failure becomes a message.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `uv run rtk pytest` collected zero tests (rtk's pytest proxy). Used `rtk uv run pytest` for verifies; `make test` uses `uv run pytest --cov` and passed.
- pyright-strict rejected `dict.get` on an uncast decoded object. Folded `cast(dict[str, object], raw_decoded)` the same way `version_cache._as_object` does; no `# type: ignore`.
- The OSError test initially asserted `.link_mode` stayed `"single"` after a failed write. The plan assigns then saves, so a write failure can leave the live value updated; the assertion was dropped to match `<action>`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 13-04 (Wave 2 tracer). Plan 13-06 Task 1 is the first production caller of every symbol in this module. Plan 13-07 Task 2 re-asserts the rule-5 adoption gate over the whole phase. Wave 1 is complete.

## Self-Check: PASSED

- `uv run pytest tests/test_settings.py tests/test_version_cache.py tests/test_locations.py tests/test_atomic.py -q` green (21 settings tests).
- `grep -c 'never chosen' installer/settings.py` is 4; `atomic_write_text` present; `open(` absent.
- Tampered `"../../etc"` and literal-`null` fixtures print `REJECTED`; CLI subset prints `CHOICES-OK`; precedence prints `PRECEDENCE-OK`.
- `uv run vulture` exits 0; `git diff -- pyproject.toml` empty; `min_confidence` still 80.
- `make validate && make test` green: 1936 passed, 1 skipped, 95.39% coverage.

---
*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Completed: 2026-09-14*
