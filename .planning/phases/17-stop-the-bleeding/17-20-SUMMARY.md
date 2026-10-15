---
phase: 17-stop-the-bleeding
plan: "20"
subsystem: installer
tags: [link-mode, migration, policy, settings, headless, rich]
requires:
  - phase: 17-stop-the-bleeding
    provides: "link-mode-aware policies and the settings warning rule (17-08, 17-11), Uninstall view activity predicates"
provides:
  - "move_link_mode that restores cleanly, names unrestorable ids, and no-ops on the live mode"
  - "link-mode migration driven by live on-disk policy activity, with an explicit PATH-wiring report for split exits"
  - "damaged-settings.json warning printed on every headless route before acting, never wrapped or markup-parsed"
affects: [17-verify, future-link-mode-work]
actuals:
  tokens: 38000
  tasks: 3
  commits: 4
tech-stack:
  added: []
  patterns:
    - "live-activity predicate: policies bind an is_active callback re-probed at use time instead of a construction-time snapshot"
key-files:
  created: []
  modified:
    - installer/policy.py
    - installer/wizard_app.py
    - installer/settings.py
    - setup.py
    - tests/test_policy.py
    - tests/test_policies_e2e.py
    - tests/test_wizard_app.py
    - tests/test_settings.py
    - tests/test_setup.py
key-decisions:
  - "H2 fixed at the policy layer: ban/tweak policies take a live is_active predicate so migration re-probes disk activity (policy_owned) at the moment of the change"
  - "M1 reported, not auto-wired: the picker does not re-run PATH wiring, so the status names the exact action: make fix ARGS=\"--link-mode <mode>\""
  - "WR-05 printed once per headless route from _settings_store; the TUI route keeps its startup_warning only"
patterns-established:
  - "Copyable-path rule: any console output containing a path the user must copy uses markup=False, soft_wrap=True (matches 17-17's render.py fix)"
requirements-completed: [SAFE-06, SAFE-08]
coverage:
  - id: D1
    description: "move_link_mode restore removes partial new-mode blocks, names unrestorable ids, and the live mode is a no-op (WR-02, ponytail #4/#5/#7)"
    requirement: SAFE-06
    verification:
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_clears_a_partial_new_mode_write_before_restoring"
        status: pass
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_names_the_ids_it_could_not_restore"
        status: pass
      - kind: unit
        ref: "tests/test_policy.py#test_move_link_mode_with_the_live_mode_is_a_no_op"
        status: pass
    human_judgment: false
  - id: D2
    description: "Link-mode migration reads live disk activity (no resurrection after Uninstall) and reports the split->centralized wiring action (opencode H2, M1)"
    requirement: SAFE-06
    verification:
      - kind: integration
        ref: "tests/test_policies_e2e.py#test_link_mode_change_after_an_uninstall_does_not_resurrect"
        status: pass
      - kind: integration
        ref: "tests/test_policies_e2e.py#test_split_to_centralized_move_reports_the_path_wiring_action"
        status: pass
    human_judgment: false
  - id: D3
    description: "A damaged settings.json warns once on every headless route before acting, byte-identical file preserved, message never wrapped or markup-parsed (WR-05)"
    requirement: SAFE-08
    verification:
      - kind: unit
        ref: "tests/test_setup.py#test_all_yes_with_a_damaged_settings_json_warns_before_acting"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_non_tty_doctor_with_a_damaged_settings_json_warns_before_acting"
        status: pass
    human_judgment: false
duration: 65min (across two runs; first run hit its timeout after the three task commits)
completed: 2026-10-14
status: complete
---

# Plan 17-20: Stop the bleeding — link-mode migration and settings warnings

**Link-mode migration now restores cleanly and acts on live disk activity (WR-02, ponytail #4/#5/#7, H2, M1), and a damaged settings.json warns unwrapped on every headless route (WR-05).**

## Findings table

| Finding | Source lane | Outcome | Commit | Test |
|---|---|---|---|---|
| WR-02 restore loses partial new-mode blocks, silent failures | 17-REVIEW | Wired: per-policy restore removes before re-applying; `_rollback` returns lost ids; `PolicyRestoreError` says `"; not restored: a, b"`; screen flips those rows OFF | `58ff7e6` | `test_move_link_mode_clears_a_partial_new_mode_write_before_restoring`, `test_move_link_mode_names_the_ids_it_could_not_restore` |
| Ponytail #4 (same as WR-02) | 17-REVIEW-ponytail | Wired, same fix | `58ff7e6` | same as WR-02 |
| Ponytail #5 live-mode no-op | 17-REVIEW-ponytail | Wired: picking the already-live mode only saves it, zero remove/apply calls | `58ff7e6` | `test_move_link_mode_with_the_live_mode_is_a_no_op` |
| Ponytail #7 unused `_rollback` param | 17-REVIEW-ponytail | Wired: `set_link_mode` parameter dropped; `_rollback` returns lost ids | `58ff7e6` | covered by WR-02 tests |
| H2 cached active_state resurrects uninstalled policies | 17-REVIEW-opencode | Wired: migration set re-probed on disk at change time via `policy_owned`; ban/tweak policies bind a live `is_active` predicate | `03343fe` | `test_link_mode_change_after_an_uninstall_does_not_resurrect` |
| M1 split->centralized leaves aliases unsourced | 17-REVIEW-opencode | Reported (not wired): confirmed the picker does not re-run PATH wiring, so the status names the exact action `make fix ARGS="--link-mode <mode>"`; auto-wiring was judged out of 17-08's scope | `03343fe` | `test_split_to_centralized_move_reports_the_path_wiring_action` |
| WR-05 damaged settings.json silent on headless routes | 17-REVIEW | Wired: `_settings_store` prints the warning once to stderr in yellow on every non-TUI route before acting; TUI keeps `startup_warning` only | `df0a02d` | `test_all_yes_with_a_damaged_settings_json_warns_before_acting`, `test_non_tty_doctor_with_a_damaged_settings_json_warns_before_acting` |
| WR-05 follow-up: warning wrapped/markup-parsed | resume note | Wired: `_WARN_CONSOLE.print(..., markup=False, soft_wrap=True)` — the path is copyable and never parsed as markup (same defect 17-17 fixed in render.py) | `3d62faf` | same two tests, under xdist `-n auto` |

## TDD RED evidence (reproduced against each task's parent commit, trimmed)

Task 1 (`58ff7e6`):
```
FAILED tests/test_policy.py::test_move_link_mode_clears_a_partial_new_mode_write_before_restoring
FAILED tests/test_policy.py::test_move_link_mode_names_the_ids_it_could_not_restore
FAILED tests/test_policy.py::test_move_link_mode_with_the_live_mode_is_a_no_op
```

Task 2 (`03343fe`):
```
FAILED tests/test_policies_e2e.py::test_link_mode_change_after_an_uninstall_does_not_resurrect
FAILED tests/test_policies_e2e.py::test_split_to_centralized_move_reports_the_path_wiring_action
```

Task 3 (`df0a02d`):
```
FAILED tests/test_setup.py::test_all_yes_with_a_damaged_settings_json_warns_before_acting
FAILED tests/test_setup.py::test_non_tty_doctor_with_a_damaged_settings_json_warns_before_acting
```

## Task Commits

1. **Task 1: move_link_mode restores cleanly and reports what it could not** - `58ff7e6` (fix)
2. **Task 2: migration acts on live state and leaves moved policies sourced/reported** - `03343fe` (fix)
3. **Task 3: damaged settings.json warns on headless routes** - `df0a02d` (fix)
4. **Task 3 follow-up: warning not word-wrapped, not markup-parsed (xdist fix)** - `3d62faf` (fix)

## Verify results

- `uv run pytest tests/test_policy.py tests/test_policies_e2e.py tests/test_wizard_app.py -q --no-cov` — pass
- `uv run pytest tests/test_wizard_app.py tests/test_policies_e2e.py -q --no-cov` — pass
- `uv run pytest tests/test_setup.py tests/test_settings.py -q --no-cov` — pass
- `make validate` — exit 0
- `make test` — **3572 passed, 4 skipped**, coverage 95.96% (gate 90%) — this run includes `3d62faf`, which fixed the only two xdist failures (`_WARN_CONSOLE.print(..., markup=False, soft_wrap=True)` so the long tmp path is not wrapped at the 80-column non-TTY width)

## Deviations from Plan

One post-plan fix commit (`3d62faf`) beyond the three tasks, per the resume note: the WR-05 warning was word-wrapped by Rich at the 80-column non-TTY width (breaking the two Task 3 tests under `pytest -n auto`, though passing serially) and could contain `[...]` path segments parsed as markup. Fixed the product line in `setup.py`; test assertions unchanged. No amending of shared commits.

## Issues Encountered

- The original run hit its 3600 s timeout after the three task commits; only the summary and the xdist wrap fix were outstanding. No quota stop.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All confirmed 17-08/17-11 review findings are closed; the D-11 warning rule (invalid UTF-8 / invalid JSON only) and the `Policy.link_mode_aware` scope were left untouched per the plan's prohibition.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
