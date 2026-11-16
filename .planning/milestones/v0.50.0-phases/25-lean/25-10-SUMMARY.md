---
phase: 25-lean
plan: "10"
subsystem: ui
tags: [textual, refactor, comment-cleanup, size-guard, wizard-app-split]
status: complete

requires:
  - phase: 25-lean
    provides: plans 25-07..25-09 (the split modules, moved verbatim)
provides:
  - every split module at most 800 lines, free of review ids
  - nine pure UninstallScreen helpers as public functions in installer/uninstall_review.py
  - installer/app_messages.py holding ScheduleDefaultsApplied, RefreshPublished and RefreshFinished
  - permanent size, review-id, import-direction and moved-lines guards in tests/test_reachability.py
affects: [25-11]

actuals:
  tokens: 24000
  tasks: 3
  commits: 7

plan_head_before: 1991939083ace6aa885078a8893a691c0d4d3d28
plan_head_after: 2ebd2e5b9b6866d49d5f70621e89e0ef809ed1af

tech-stack:
  added: []
  patterns:
    - "comment cleanup is its own commit and is proven code-free by AST equality with docstrings dropped (p25-ast-same.py)"
    - "a screen over the cap sheds side-effect-free helper methods to module-level functions in its sibling, values read from self passed explicitly"

key-files:
  created:
    - installer/app_messages.py
  modified:
    - installer/uninstall_screen.py
    - installer/uninstall_review.py
    - installer/wizard_app.py
    - installer/doctor_screen.py
    - installer/doctor_messages.py
    - installer/policies_screen.py
    - installer/schedules_screen.py
    - installer/modals.py
    - installer/mutation_lock.py
    - installer/systemd_daemon.py
    - installer/diskusage.py
    - installer/omz.py
    - installer/locations.py
    - installer/compose.py
    - installer/terminal_shell.py
    - installer/settings.py
    - tests/test_reachability.py
    - tests/test_omz.py
    - tests/test_run.py
    - tests/test_post_install.py
    - tests/test_shellrc.py
    - tests/test_terminal_shell.py
    - tests/test_catalog_tui.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py

key-decisions:
  - "Comment rule applied as: review ids, round ids, C-NN review concern ids, L-20-NN, finding numbers, review-file citations and phase or plan narratives go; every why sentence stays, reworded without the id. Bare D-NN, T-NN and UI-SPEC pointers that annotate a why stay."
  - "All nine candidate helpers moved, not five: the five with no self use free about 87 lines and leave uninstall_screen near 890, so the read-only family was needed too."
  - "wizard_app needed app_messages.py and a tightening of its longest why comments, because the comment cleanup alone freed 8 lines, not the 30-odd the projection assumed."

patterns-established:
  - "test_reachability.py owns the permanent split guards: _SPLIT_MODULES, _MOVED_INTO_SHARED, _review_ids"

requirements-completed: [LEAN-03]

duration: 75min
completed: 2026-11-15
---

# Phase 25 Plan 10: Finish the split Summary

**Every split module is at most 800 lines with no review ids, the comment cleanup provably changed no code, and permanent guards keep it that way.**

## Performance

- **Tasks:** 3 planned, plus 4 orchestrator items, each its own commit
- **Commits:** 7 (SUMMARY commit excluded)

## Accomplishments

- Task 1 (`02702536`): review-history comments left the nine split modules and the moved lines of systemd_daemon (`CompetingProbe`) and diskusage (`DiskPressureProbe`); wizard_app's module docstring now describes only the app. `p25-ast-same.py HEAD` over all twelve files exits 0, so the commit changed no code. `p25-moved-ids.py` exits 0 (baseline printed `WR-10`). ui_common's `fit`, `sentence` and `TIMES_LISTED` carried no id, so that file is untouched; its one id (StatusLine) and systemd_daemon's 8 stay.
- Task 2 (`06b65806`): `config_clause`, `block_entry`, `retired_entry`, `accept_summary`, `config_lines`, `unknown_entry`, `tweak_entry`, `settings_entry` and `applied_summary` moved from `UninstallScreen` to installer/uninstall_review.py. Each writes no state and calls no self method; the values read from self (`_painted.get(tool.id)`, `_tweak_ids`, `_platform_os`, `_settings_files`) are arguments. `_tool_entry` and `_with_failure` stay on the class. `config_lines` reads the disk and its one call site is unchanged (the summary built after a removal finishes, never cached). The three message classes moved verbatim to installer/app_messages.py (`p25-moved-same.py` checked 3 names); the three test importers changed import lines only.
- Task 3 (`56f7e055`): five guards in tests/test_reachability.py (size, review ids, typing-only import of the app, moved-lines scan, seeded scan). The seeded test was shown RED against a stub first.

Final `wc -l`: uninstall_screen 762, wizard_app 793, doctor_screen 782, schedules_screen 749, policies_screen 526, uninstall_review 417, modals 389, mutation_lock 89, doctor_messages 55, app_messages 38. app_messages.py WAS created. doctor_screen needed no change.

Orchestrator items (one commit each):
1. `ba692124` `omz_present` deleted with its three tests; comments that named it now name `omz_root`.
2. `33025161` three tests renamed, bodies unchanged.
3. `a6c441fd` comments now name compose.py for `_timer_state_cache`, `_ZSHRC`, `_build_app` and `_current_link_mode` (four files, AST unchanged).
4. `2ebd2e5b` streaming-runner bound is `>= 0.2` with a one-line comment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] wizard_app still 840 lines after the app_messages move**
- **Found during:** Task 2
- **Issue:** the Task 1 cleanup freed only 8 lines of wizard_app, so moving the three messages left it about 40 lines over the cap.
- **Fix:** tightened eight verbose why comments (the schedule-defaults worker, the invalidate block, five `_install_closed` blocks) without dropping a reason; AST equals the version before the tightening.
- **Files modified:** installer/wizard_app.py
- **Commit:** 06b65806

### Orchestrator-directed adjustments

**2. omz_root coverage kept.** Item 1 asked to delete the `omz_present` tests including `test_omz_root_agrees_with_omz_present_on_every_case`. That test held the only direct `omz_root` assertions (home directory, valid `$ZSH`, home wins when both exist), so those assertions live on in one new `test_omz_root_resolves_the_real_install_directory`. The three `omz_present` tests are gone.

**3. Extra stale reference fixed.** `setup.py::_build_app` also sat in installer/doctor_screen.py (not in the listed files); fixed with the rest of item 3. `setup.py::_has_controlling_tty` and `setup.py::_ask_mismatch` stay: both still live in setup.py.

## Issues Encountered

Two other tests carry the retired "yes" wording (`test_a_split_mode_yes_wires_the_rc_files_to_source_myshellrc`, `test_starship_in_policies_sets_and_restores_the_theme_like_the_install_yes` in tests/test_post_install.py). Not renamed, outside the three listed.

## Known Stubs

None.

## Threat Flags

None. T-25-25 (code under cover of comments) mitigated by the AST check, T-25-27 (confirm text) by moving only state-free helpers with unchanged bodies; tests/test_uninstall_e2e.py and the confirm-modal tests ran unchanged and green.

## Self-Check: PASSED

- installer/app_messages.py and the seven code commits exist; `make validate && make test` exit 0 on every commit's tree (final: 7620 passed, 6 skipped).
- No `noqa`, `type: ignore`, `pyright: ignore` or `nosec` added; STATE.md and ROADMAP.md untouched.
