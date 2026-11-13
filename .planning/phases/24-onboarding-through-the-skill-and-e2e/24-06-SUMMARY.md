---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "06"
subsystem: terminal-sync
tags: [alacritty, herdr, toml, terminal-shell, install-tuning, tdd]
requires:
  - phase: 24-01
    provides: Alacritty registry entry (cargo_distrobox, config_paths)
  - phase: 24-02
    provides: agent_settings apply_value / revert_group, herdr adapter and ledger
provides:
  - "alacritty shell region (a branch of sync_terminal_shells) and alacritty-keys region (install tuning, written-once record)"
  - "apply_terminal_tuning post-install action, strip_alacritty on removal"
  - "herdr terminal.default_shell branch of the synchronizer with an injected reload runner"
  - "partial: terminal warnings as misconfigured reasons; Alacritty and herdr terminal rows; keybindings tuning fact"
affects: [24-07 herdr catalog row, 24-08 container e2e]
tech-stack:
  added: []
  patterns:
    - "per-part conflict guard: each owned part (shell, SHELL, each binding) is decided on its own and each skipped part is named by one `partial:` warning"
    - "compare-before-commit region writes through agent_settings.read_settings/write_if_unchanged plus a whole-document tomllib re-parse"
key-files:
  created: []
  modified:
    - installer/terminal_shell.py
    - installer/post_install.py
    - installer/model.py
    - installer/version_status.py
    - installer/app.py
    - installer/registry.toml
    - setup.py
    - tests/test_terminal_shell.py
    - tests/test_post_install.py
    - tests/test_version_status.py
    - tests/test_app.py
    - tests/test_setup.py
    - tests/test_registry.py
    - tests/test_model.py
key-decisions:
  - "The shell region and the keys region share one file but are separate owned regions; neither writer touches the other's region (markers compare as whole lines, so `alacritty` never matches `alacritty-keys`)"
  - "Key and modifier names are compared case-insensitively and order-free when looking for a user binding that already takes a key (Alacritty reads them that way)"
  - "A binding conflict is reported by the sync as well as by the install action, so the `≈ partial` reason persists on the row after the region exists"
  - "An inline keyboard.bindings (any `keyboard.bindings` value with no `[[keyboard.bindings]]` header outside the regions) refuses the keys region; the reason shows on the row with no step"
  - "herdr dry run reads the config itself (parse failure is a note); a write run goes through apply_value, so a user value equal to zsh is `already` with no ledger entry"
  - "zsh-gone revert calls revert_group(\"herdr\", \"default-shell\") with no runner: panes already open keep the shell they started with"
patterns-established:
  - "_TERMINAL_ROWS is keyed by tool id: the herdr entry added here is picked up unchanged by the real catalog row 24-07 adds"
requirements-completed: [ONB-07, ONB-01]
metrics:
  duration: "~1h30m"
  completed: "2026-11-13"
status: complete
actuals:
  tokens: 16000
  tasks: 3
  commits: 3
commits: 3
plan_head_before: a2f4320deed77856e8b4042948d390854187b8f0
plan_head_after: 971ffdc638f0f6d9c9212089d95090b29729f2b9
---

# Phase 24 Plan 06: Alacritty and herdr join the terminal synchronizer Summary

Alacritty gets an owned `[terminal.shell]`/`[env] SHELL` region that follows zsh plus an owned keybindings region (Alt+Left/Right word moves, Control+Shift+K ClearHistory) written at install with no question, both stripped with the tool; herdr's `terminal.default_shell` follows zsh absent-only through the ledgered writer and is reloaded through an injected runner.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Alacritty install writes both regions, removal strips them, end to end (tracer) | 49674b8 |
| 2 | Alacritty's guards, drift and pending-tuning facts | a2d8cd8 |
| 3 | herdr's default shell follows zsh, with the reload through an injected runner | 971ffdc |

## What was built

- **installer/terminal_shell.py:** `alacritty_config_path` (first existing of the three locations, else the XDG one); the Alacritty branch of `sync_terminal_shells` (`[terminal.shell]` program + `args = ["-l"]`, `[env] SHELL`, decided per part); `apply_alacritty_keys` (region then the `terminal-tuning-alacritty` record, `skip_recorded` honours a user deletion); `alacritty_keys_pending`; `strip_alacritty`; the herdr branch (`_sync_herdr`, `_herdr_check` for the dry run, `_revert_herdr`); `sync_terminal_shells(..., runner=)`; `_revert_terminal_shells` strips the `alacritty` region and reverts the ledgered herdr key. Every Alacritty write is checked with `tomllib.loads` of the whole new text and committed with `write_if_unchanged`.
- **post_install / model / registry / app:** `apply_terminal_tuning` in `POST_INSTALL_ACTIONS`, `POST_INSTALL_HOOKS` and the `apply_install_tuning` branch; Alacritty declares it; `_after_removal` strips both regions and the record for `alacritty`.
- **version_status:** `_TERMINAL_ROWS` gains `alacritty` and `herdr`; a `<terminal>: partial: ...` warning becomes a `misconfigured` reason with no step (other warnings stay `unchecked` notes); `_terminal_tuning_fact` gives `≈ apply install tuning` while pending, the refusal reason with no step when the file cannot take the region, and nothing once the region or its record exists.
- **setup.py:** `_sync_terminals` passes `runner=run_captured`; the refresh pass's `terminal_drift` stays `write=False` with no runner. No Policies change.

## TDD evidence (RED output)

Task 1 (`-k "alacritty or post_install_action_names"` before any implementation):

```
FAILED tests/test_terminal_shell.py::test_alacritty_install_writes_both_regions_and_removal_strips_them
FAILED tests/test_registry.py::test_alacritty_entry_declares_its_terminal_tuning
FAILED tests/test_model.py::test_post_install_action_names_include_the_new_actions
FAILED tests/test_registry.py::test_only_reviewed_tools_declare_a_post_install_action  (AssertionError: declarer set missing 'alacritty')
```

Task 2 (`-k "alacritty or partial"` after the guard tests were added). The terminal_shell guard tests (`test_alacritty_partial_conflicts`, `test_alacritty_invalid_toml_writes_nothing`, the two backstops, `test_alacritty_keys_without_zsh`) passed at once: Task 1's implementation already carried the per-part guard, so they act as pinning tests. The version_status tests were RED:

```
FAILED tests/test_version_status.py::test_alacritty_shell_region_drift_reads_terminal_sync_step
FAILED tests/test_version_status.py::test_untuned_alacritty_reads_apply_install_tuning
FAILED tests/test_version_status.py::test_alacritty_that_cannot_take_the_keys_shows_the_refusal_without_a_step
FAILED tests/test_version_status.py::test_partial_warning_is_a_reason_not_a_note
E   AssertionError: assert <Health.OK: 'ok'> is <Health.MISCONFIGURED: 'misconfigured'>
```

Task 3 (`-k "herdr or update_route or runner"` before implementation):

```
FAILED tests/test_terminal_shell.py::test_herdr_default_shell_written_and_reloaded   (TypeError: sync_terminal_shells() got an unexpected keyword argument 'runner')
FAILED tests/test_terminal_shell.py::test_herdr_reload_failure_is_a_note
FAILED tests/test_terminal_shell.py::test_herdr_user_default_shell_is_kept
FAILED tests/test_terminal_shell.py::test_herdr_nothing_without_zsh_or_herdr[no-herdr]
FAILED tests/test_terminal_shell.py::test_herdr_nothing_without_zsh_or_herdr[no-zsh]
FAILED tests/test_terminal_shell.py::test_herdr_dry_run_reports_drift_without_reloading
FAILED tests/test_version_status.py::test_herdr_drift_lands_on_its_own_row
FAILED tests/test_version_status.py::test_herdr_partial_warning_reads_as_a_reason
FAILED tests/test_setup.py::test_sync_terminals_passes_a_runner_and_drift_does_not   (KeyError: 'runner')
```

Passed at once (pins, not RED): `test_herdr_removal_reverts_default_shell` (24-02's CONFIG_AGENTS branch already reverts the dynamic group), `test_zsh_gone_reverts_only_the_ledgered_default_shell`, and both `test_update_route_*` tests (the Alacritty compare is already byte-stable and repairs only the shell region, so no update-route special case was needed, R2-12).

## Deviations from Plan

**1. [Rule 1 - Bug] Existing tests pinned the old `sync_terminal_shells` kwargs and the old Alacritty row**
- **Found during:** Tasks 2 and 3 (full test runs)
- **Issue:** `tests/test_version_status.py::test_newer_alacritty_tag_reads_outdated` (24-01) now saw a present, untuned Alacritty as `misconfigured` (pending install tuning); two `tests/test_setup.py` assertions compared the exact kwargs `_sync_terminals` passes.
- **Fix:** the OUTDATED test applies the install tuning first (an installed Alacritty has had it); the two kwargs assertions gain `"runner": run_captured`.
- **Files modified:** tests/test_version_status.py, tests/test_setup.py
- **Commits:** a2d8cd8, 971ffdc

**2. [Rule 2 - Correctness] A binding conflict is also reported by the sync**
- **Issue:** the plan names the install action as the place a bound key is left out, but after the region exists nothing would keep the `≈ partial: you already bind ...` reason on the row.
- **Fix:** `_sync_alacritty` (read-only for this part) appends the binding-conflict warnings, so SPEC R6 adjacency reads the same on every refresh.
- **Commit:** 49674b8

`run_post_install` drops `PostInstallOutput.refused` (it keeps only crashed-action warnings), so an install-time refusal of the keys region is one output line, `Alacritty keys not changed: <reason>`; RECONFIGURE (`apply_install_tuning`) does carry `refused`. This is the existing omz-plugins behaviour, left as is.

## Known Stubs

None.

## Threat Flags

None. The two trust boundaries (alacritty.toml, herdr config + server reload) are in the plan's threat model; T-24-22 (marker regions, per-part guard, tomllib re-parse, compare-before-commit), T-24-23 (absent-only ledgered writer, user value kept and reported) and T-24-24 (`_safe_executable`, `json.dumps` TOML strings) are each pinned by a test named in the plan.

## Verification

- `make validate` exit 0 and `make test` exit 0 (6240 passed, 6 skipped, coverage 96.19%) on the final tree; every commit passed the pre-commit hooks.
- Acceptance greps: `"apply_terminal_tuning"` once in registry.toml; `apply_terminal_tuning` in model.py; `alacritty-keys` and `reload-config` in terminal_shell.py; `strip_alacritty` in app.py; non-comment `herdr` count in terminal_shell.py is 27; `"alacritty"` in version_status.py; `def test_alacritty_partial_conflicts(` once; `test_policies_list_keeps_only_the_kept_ids` passes (no Policies row added).
- No `herdr` or `alacritty` process was launched: the reload runner is a recording fake and the lookup returns fixed paths; every config file lives in the scratch HOME.
- The Alt+arrow byte strings (`\u001bb`, `\u001bf`) remain RESEARCH A3 assumptions, checked in the user's UAT.

## Self-Check: PASSED

- FOUND: installer/terminal_shell.py, installer/post_install.py, installer/model.py, installer/version_status.py, installer/app.py, installer/registry.toml, setup.py and the seven touched test files
- FOUND commits: 49674b8, a2d8cd8, 971ffdc (ancestors of HEAD)
