---
phase: 23-configuration-as-a-lifecycle-step
plan: "15"
subsystem: installer
tags: [uninstall, removal, agent-settings, shell-init, desktop-shell, tui, cli, tdd]
status: complete

requires:
  - phase: 23-06
    provides: agent_settings.revert_agent, ledger_summary, the config-write ledger, display_path
  - phase: 23-08
    provides: unregister on removal, RemovalPlan.unregister/hook_hosts, SweepResult.unregistered, _command_error_line
  - phase: 23-09
    provides: SHELL_INIT_TOOLS and the six shell-init bundles
  - phase: 23-11
    provides: desktop_shell_policy (owned by its environment.d sentinel), settings Policies rows
provides:
  - An agent's removal reverts exactly the ledgered keys that still hold the installer's value (SPEC R8, D-08)
  - A shell-init tool's removal turns off only its own bundle; zsh's Linux removal sweeps the owned desktop SHELL row (R1-48)
  - One revert helper (_revert_settings) and one copy each of the settings lines (removal_change_lines, settings_change_lines, removal_result_lines)
  - The Uninstall view's agent/editor settings row (O5) and the CLI whole-environment revert
  - ConfirmUninstall block 3 (undo first) and block 3b (what changes); the detail bar hosts clause; the result lines; the 80x20 backstop
affects: [23-16 (container run evidence), 23-14 (same wave: setup.py composition and the desktop row composition)]

# Actuals (#2632): chars/4 over the realized diff (git diff ef1bbeb HEAD = 61553 chars)
actuals:
  tokens: 15388
  tasks: 3
  commits: 4

# Measured commit ledger (#3968): base..HEAD measured before this SUMMARY commit
commits: 4
plan_head_before: ef1bbebd61e78ccf7595d45a7735975eed6e3dc4
plan_head_after: 7760d24b5fd9d6a3b7bb0cf165b25df85a5d9fbf

key-files:
  modified:
    - installer/app.py
    - installer/uninstall.py
    - installer/wizard_app.py
    - installer/version_status.py
    - tests/test_app.py
    - tests/test_uninstall_e2e.py
    - tests/test_wizard_app.py
    - tests/test_version_status.py
    - tests/test_layout_80x20.py
    - tests/test_uninstall.py

key-decisions:
  - "One revert loop: _revert_settings(agent_ids, platform_os) returns (reverted, kept, warnings); the per-tool revert, the pseudo-row and the CLI whole-environment revert all call it (23-REUSE 15-1, R1-60)"
  - "The per-tool post-removal step (_after_removal) runs only after a successful removal: settings revert, the tool's own shell-init bundle through active_policies + sweep_policies, and the owned desktop row when zsh goes (R1-48). Never sweep_tweaks (T-23-40)"
  - "The shell-init bundle is taken from the bundles the caller passed, and the CLI preview reads the same active-policy list the sweep reads, so preview and effect cannot disagree"
  - "No config-supersedes branch: revert_agent reverts every file before it returns and no CONFIG_AGENTS tool declares config_paths. A shortcut comment sits at the per-tool revert and test_no_config_agent_declares_config_paths guards the assumption (R1-58, R1-59)"
  - "The CLI reverts every ledgered agent after its tool loop (O5), so an agent whose tool is not removed still loses its written keys; the nothing-to-uninstall guard counts a ledger as something to uninstall"
  - "The CLI result lines and the Uninstall status lines come from one helper, removal_result_lines, so the copy has one home"
  - "Block 3b lines are de-duplicated (dict.fromkeys) so a tool and the pseudo-row never print the same ledgered file twice"
  - "The CLI does not sweep a policy a tool's removal already turned off, so the final sweep does not report it twice"

patterns-established:
  - "Test-first, one green commit per task: RED output pasted below, tests and code committed together as one feat(23-15) commit each"
  - "A guard test whose behavior already held is committed as a test-only commit (test(23-15)), the 23-08 precedent"

requirements-completed: [CONF-01, CONF-04, CONF-08, CONF-09, CONF-12]
---

# Phase 23 Plan 15: Removal reverts configuration and the review and results say so — Summary

**Removing claude, codex, opencode, cursor-agent or VS Code reverts exactly the keys the installer wrote, a shell-init tool's removal turns off only its own bundle, the Uninstall view and the CLI can revert every written key, and the review lists each undo and change before the confirm.**

## Performance

- **Tasks:** 3 planned, each test-first with one green `feat(23-15)` commit. One test-only `test(23-15)` commit added two guard tests after Task 3 (see Deviations, D-6).
- **Commits (measured `git rev-list --count ef1bbeb..HEAD` = 4 before this SUMMARY commit):**
  - `a0c113a` feat(23-15): removing an agent reverts the settings the installer wrote (Task 1)
  - `cfb10b6` feat(23-15): shell init leaves with its tool; every written key can be reverted (Task 2)
  - `402dd67` feat(23-15): the removal review and results show unregister, revert and shell init (Task 3, carries the Task 2 preview fix, D-2)
  - `7760d24` test(23-15): a refused or macOS zsh removal keeps the desktop SHELL file (guard tests)
- **Duration:** unmeasured (no start timestamp recorded for this run)

## Accomplishments

- `installer/app.py`: `HOST_SETTINGS_OS`; `_revert_settings` (the one revert helper); `settings_change_lines`, `removal_change_lines` (`active_tweaks` is the policy-id list the sweep reads), `removal_result_lines`; `_after_removal` (settings revert, shell-init bundle sweep, zsh's owned desktop row); `_merge`; `UninstallDecision.revert_settings`; `platform_os` keyword on `run_uninstall` and `perform_uninstall`; the CLI preview block, the whole-environment block and its revert, and the result lines.
- `installer/uninstall.py`: `SweepResult.settings_reverted`, `.settings_kept`, `.shell_init_off`.
- `installer/wizard_app.py`: the `#settings` pseudo-row in the environment section (after the shell tweaks row, shown only when a ledger exists), `c` refused with `This row has no config to delete.`, `remove_settings`, `revert_settings` in the decision; `ConfirmUninstall` block 3 lists each unregister line before the tool's own command; block 3b lists the change lines; the removal status adds the unregister, settings and shell-init lines.
- `installer/version_status.py`: the hook clause ` — unregisters it from {hosts} first` right after the proof sentence.
- Copy strings are verbatim from 23-UI-SPEC section 6 (`Settings reverted for`, `Kept settings you changed since this installer wrote them:`, `Shell init turned off for`, `could not revert … — …`, `{id}: removes {keys} from {path}`, `{id}: turns off its shell init in ~/.myshellrc`, `Agent and editor settings this installer wrote (reverted):`).

## Test-first evidence

### Task 1 RED (`uv run pytest tests/test_app.py tests/test_uninstall_e2e.py -k "removing_claude_reverts or changed_since_is_kept or unparsable_settings_file_is_a_removal_warning or failed_removal_reverts_nothing or previews_and_reports_the_revert" -q --no-cov -n 0`)

Exit 1, 5 failed. Every failure is the missing keyword the API needs, so the RED is a missing-API failure, not an assertion failure:
```
FAILED tests/test_app.py::test_the_cli_previews_and_reports_the_revert - Type...
FAILED tests/test_uninstall_e2e.py::test_removing_claude_reverts_its_settings
FAILED tests/test_uninstall_e2e.py::test_a_key_changed_since_is_kept_and_named
FAILED tests/test_uninstall_e2e.py::test_an_unparsable_settings_file_is_a_removal_warning
FAILED tests/test_uninstall_e2e.py::test_a_failed_removal_reverts_nothing
E   TypeError: perform_uninstall() got an unexpected keyword argument 'platform_os'
```
### Task 1 GREEN

- Focused selection: `.....`, exit 0.
- Wide (`test_app.py test_uninstall_e2e.py test_uninstall.py -n auto`): exit 0.
- `make validate`: exit 0 (after E501 fixes in three lines).
- `make test`: exit 0, **5773 passed, 4 skipped**, coverage 96.19%.

### Task 2 RED (`-k "turns_off_only_its_shell_init or names_the_shell_init_it_turns_off or pseudo_row_reverts_every or cli_uninstall_reverts_every or no_config_agent_declares_config_paths or removing_zsh_sweeps_the_desktop_shell_file or pseudo_row_is_selected_and_refuses_c or row_is_absent_without_a_ledger"`)

Exit 1. Six behavior or missing-API failures, and two guards that already held:
```
FAILED tests/test_app.py::test_removing_starship_turns_off_only_its_shell_init   (assert () == ('starship',))
FAILED tests/test_app.py::test_the_cli_names_the_shell_init_it_turns_off          (preview line not printed)
FAILED tests/test_app.py::test_the_settings_pseudo_row_reverts_every_written_key (UninstallDecision has no revert_settings)
FAILED tests/test_app.py::test_the_cli_uninstall_reverts_every_written_key
FAILED tests/test_app.py::test_removing_zsh_sweeps_the_desktop_shell_file        (swept == ())
FAILED tests/test_uninstall_e2e.py::test_the_settings_pseudo_row_is_selected_and_refuses_c
PASSED (guards, not RED): test_no_config_agent_declares_config_paths, test_the_settings_row_is_absent_without_a_ledger
```
### Task 2 GREEN

- App-level focused selection: `......`, exit 0 (after a test-only fix: a `.codex/config.toml` the installer created is deleted when empty).
- `make validate`: exit 0 (after `ruff format` and E501 fixes).
- `make test`: exit 0, **5781 passed, 4 skipped**, coverage 96.22%.

### Task 3 RED (`-k "unregister_line_first or lists_the_changes_block or uninstall_values_render_literally or results_name_unregister_revert or unregister_failure_row or names_the_hosts_to_unregister or uninstall_review_fits_80x20"`)

Exit 1. Six behavior failures:
```
FAILED tests/test_wizard_app.py::test_confirm_uninstall_lists_the_unregister_line_first  (review empty: IndexError)
FAILED tests/test_wizard_app.py::test_confirm_uninstall_lists_the_changes_block           (... in [])
FAILED tests/test_wizard_app.py::test_uninstall_values_render_literally                   (... in [])
FAILED tests/test_wizard_app.py::test_removal_results_name_unregister_revert_and_shell_init
        assert 'Unregistered from agent hosts: claude, codex.' in '1 removed\nwarning: could not revert ~/.codex/config.toml — not valid TOML (line 2).'
FAILED tests/test_version_status.py::test_the_detail_bar_names_the_hosts_to_unregister
        - installed in userspace — removable here — unregisters it from claude, cursor-agent first
        + installed in userspace — removable here
FAILED tests/test_layout_80x20.py::test_uninstall_review_fits_80x20                        (IndexError)
PASSED (regression guard, not RED): test_an_unregister_failure_row_reads_remove_failed (the row path already rendered `remove failed — unregister: …` from 23-08)
```
### Task 3 GREEN

- Focused selection: 7 passed, exit 0 (one test-only fix: the settings line folds at 54 cells, so the test compares the unfolded text).
- `make validate`: exit 0 (after E501 and pyright strict fixes: the status is read after `isinstance(screen, UninstallScreen)`).
- `make test`: exit 0, **5788 passed, 4 skipped**, coverage 96.23%.

### Test-only guard commit `7760d24`

- `test_a_refused_zsh_removal_keeps_the_desktop_shell_file`, `test_macos_zsh_removal_leaves_the_desktop_shell_file`: both pass (guards).
- `make validate` exit 0; `make test` exit 0, **5790 passed, 4 skipped**, coverage 96.23%.

## Test counts (measured)

| Point | Passed | Skipped | Delta |
| --- | --- | --- | --- |
| Base `ef1bbeb` | 5768 (derived) | 4 | - |
| After Task 1 `a0c113a` | 5773 | 4 | +5 |
| After Task 2 `cfb10b6` | 5781 | 4 | +8 |
| After Task 3 `402dd67` | 5788 | 4 | +7 |
| After guard commit `7760d24` | 5790 | 4 | +2 |

The base is derived, not re-measured at the start: 5773 minus the five tests Task 1 added. Coverage floor 90% was never lowered.

## Changes to existing tests (each with its reason)

- `tests/test_uninstall.py`: `plant_codegraph` now delegates to a new `plant_receipted_tool(home, tool_id, postinstall)`. Behavior unchanged. See D-1.
- No existing test was changed in assertion or deleted.

## Deviations from Plan

### D-1 [outside `files_modified`] `tests/test_uninstall.py`

- **Found during:** Task 1 test setup.
- **Issue:** the claude removal tests need a receipt-proven claude, and `plant_codegraph` hardcodes the codegraph id.
- **Fix:** added `plant_receipted_tool`; `plant_codegraph` delegates to it, same artifacts and receipt.
- **Committed in:** `a0c113a`. Recorded here as the executor rule requires.

### D-2 [plan text, fixed in Task 3] `removal_change_lines` takes `active_tweaks`, and the shell-init bundle comes from the caller's `bundles`

- **Found during:** wiring block 3b of the review. The plan's Task 2 used the global shell-init table for the sweep and `myshellrc_path` for the preview. A caller passing different `bundles` would see a preview that disagrees with the effect.
- **Fix:** `removal_change_lines(tools, *, platform_os, active_tweaks)` reads the same policy-id list the sweep reads; `_after_removal(bundles=…)` selects the bundle from the caller's `bundles`. The CLI test passes `BUNDLES`, which is what the composition root passes.
- **Committed in:** `402dd67`, not in Task 2's commit. Task 2's tree was green on its own, and history was not rewritten.

### D-3 [acceptance grep] `Kept settings you changed since this installer wrote them` lives in `app.py`, not `wizard_app.py`

- **Found during:** Task 3 acceptance grep.
- **Issue:** the plan expected the literal in `wizard_app.py`. Both the CLI and the Uninstall view need the same copy.
- **Fix:** one copy in `app.py::removal_result_lines`, called from both. `grep -c` in `installer/wizard_app.py` is 0 and in `installer/app.py` is 1. A second copy would drift.

### D-4 [plan text] the pseudo-row UI tests live in `tests/test_uninstall_e2e.py`

- **Issue:** the Task 2 file list named `tests/test_wizard_app.py`. The pilot tests use the sandbox harness in `test_uninstall_e2e.py` (`_build_real_app`).
- **Fix:** placed there. The file is in the plan's `files_modified`.

### D-5 [judgement] `UninstallScreen._env_state` is a four-element tuple

- The settings ledger files are read in the screen through `ledger_summary`, the same `run_live` seam the other env predicates use. A new `UninstallInputs` field would need `setup.py`, which 23-14 owns in the same wave.

### D-6 [process] guard tests in a test-only commit

- The zsh refusal and macOS cases were in the plan's behavior list but not in the Task 2 test set. Added after Task 3 as a `test(23-15)` commit (the 23-08 precedent). Both already held.

### D-7 [judgement] `_accept_summary` gained `the agent/editor settings`

- UI-SPEC has no copy for the accept summary. It follows the pattern of the other env rows.

### D-8 [judgement] the hook clause position

- The clause is appended after the branch's own text, before the config suffix. For the plain receipt-proven removable branch (codegraph) it follows the proof sentence exactly. For the L1 manager and L3 recipe branches it follows the `— runs …` text. The plan said "right after the proof sentence" without covering these branches.

### D-9 [process] first Task 1 commit attempt

- The commit was attempted with a `-F` path that did not yet exist. The pre-commit hooks ran and passed, the commit failed, and nothing was committed. The message file was written and the commit retried. No `--no-verify`.

### D-10 [process] harness and worktree housekeeping

- The Bash guard refused several compound commands that name git; each was split into plain commands. `codegraph init` created a gitignored `.codegraph/` in the worktree. The cwd-drift sentinel and the plan-head ledger were written under the worktree's git dir. No file outside the worktree was touched. Host safety held: all tests use a sandboxed HOME, and no `make setup`, `make fix`, `make uninstall`, real install, or sudo was run.

## Verification

- `make validate` and `make test` exit 0 on each commit's tree (Task 1, Task 2, Task 3 and the guard commit).
- Suppression gate: `git diff ef1bbeb HEAD` adds **0** `type: ignore`, `pyright: ignore`, `noqa` or `nosec` lines.
- Acceptance greps: `revert_agent(` in app.py is 1 (inside `_revert_settings`); `def removal_change_lines(` is 1; `def _revert_settings(` is 1; `Shell init turned off for` is 1 in app.py; `unregisters it from` is 1 in version_status.py; `agent/editor settings` is 2 in wizard_app.py; `sweep_tweaks(` in `perform_uninstall` is 1 (the existing remove_tweaks lever only).
- Worktree branch check at start: `worktree-agent-a3a0a5a1a7603c7b7`, HEAD `ef1bbebd61e78ccf7595d45a7735975eed6e3dc4`.
- No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-23-39 (`test_a_key_changed_since_is_kept_and_named`), T-23-40 (`test_removing_starship_turns_off_only_its_shell_init`), T-23-62 (`test_removing_zsh_sweeps_the_desktop_shell_file`, the refused and macOS guards), T-23-41 (`test_the_cli_previews_and_reports_the_revert`, `test_confirm_uninstall_lists_the_changes_block`), T-23-42 (`test_uninstall_values_render_literally`) are covered by the tests named.

## Not checked

- The macOS branch (`HOST_SETTINGS_OS == "macos"`): the environment.d and `update.mode` paths are only exercised with `platform_os="linux"` and `"macos"` passed explicitly; the real `darwin` host detection is not run here.
- The real-terminal look and the 3-line status wrap visually (23-VALIDATION human check). The 80x20 backstop asserts the review fold, the 60-cell box, and that the kept line is present on the status.
- The pseudo-row's own block 3b lines in the TUI review are produced by `settings_change_lines` and are not asserted in a pilot test; the CLI test covers the same helper.
- The pseudo-row's count cell (`keys this installer wrote in 2 file(s)`) is not asserted in a pilot test; the detail bar's file list is.
- A real uninstall against a real Claude, Codex, opencode, cursor-agent or VS Code install: none was run.
- `ledger_summary`'s `platform_os` is accepted but unused (23-06 note); the callers pass it, which is harmless.

## Unverified and open items for the orchestrator

- **Block 3b for the pseudo-row:** the ConfirmUninstall shows every ledgered file when the settings row is selected, but only the CLI path and the helper are tested for it.
- **Wave 6 composition:** 23-14 (same wave) owns `setup.py` and composes the desktop row into every site. This plan's tests pass the desktop row directly, as the plan asks.
- **23-16 evidence:** the removal of a settings agent and the zsh sweep are for the container run, not this plan.

## Self-Check

- [x] Commits exist on `worktree-agent-a3a0a5a1a7603c7b7` after base `ef1bbeb`: `a0c113a`, `cfb10b6`, `402dd67`, `7760d24`.
- [x] `make validate` exit 0 and `make test` exit 0 on the final tree (5790 passed, 4 skipped).
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.
- [x] This SUMMARY is the only planning file this plan writes.

## Self-Check: PASSED
