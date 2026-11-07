---
phase: 23-configuration-as-a-lifecycle-step
plan: "14"
subsystem: installer
tags: [policies, tweaks, legacy-alias, shell-init, settings-rows, desktop-shell, tdd]
status: complete

requires:
  - phase: 23-01
    provides: sandboxed_setup_paths (real-home re-rooting) and test_no_setup_home_constant_points_at_the_real_home
  - phase: 23-09
    provides: SHELL_INIT_TOOLS, shell_init_bundle, post_install.use_shell_init_sourcing
  - phase: 23-11
    provides: settings_policies (nine rows), desktop_shell_policy (no installed_tools argument)
  - phase: 23-12
    provides: keyed TUI shell-init modal
  - phase: 23-13
    provides: headless default-no shell-init and run-option questions, Prompter.confirm(default=)
provides:
  - tweaks.LEGACY_ALIAS_BUNDLES, LegacyStrip (launch_lines, failure_lines, uninstall_line), strip_tweak_block, strip_legacy_aliases
  - the four agent alias bundles and their bodies removed from BUNDLES
  - launch and CLI uninstall strip wiring; the settings rows and the desktop SHELL row composed into Policies
  - the six shell-init tools declare source_shell_init; split-mode reader injected in both front ends
affects: [23-15, 23-16]

# Actuals (#2632): chars/4 over the realized diff (git diff ef1bbeb HEAD = 61747 chars)
actuals:
  tokens: 15437
  tasks: 3
  commits: 3

# Measured commit ledger (#3968): rev-list count from the plan base, before this SUMMARY commit
commits: 3
plan_head_before: ef1bbebd61e78ccf7595d45a7735975eed6e3dc4
plan_head_after: 5e529ea

key-files:
  modified:
    - installer/tweaks.py
    - installer/registry.toml
    - setup.py
    - tests/conftest.py
    - tests/test_tweaks.py
    - tests/test_policy_tweaks.py
    - tests/test_policy.py
    - tests/test_policies_e2e.py
    - tests/test_setup.py
    - tests/test_registry.py

key-decisions:
  - "Legacy alias blocks are stripped, never migrated: no agent settings file is read or written at launch, uninstall or strip time (user decision 2026-11-06, RUN-LEDGER row 23 Alias migration)"
  - "strip_legacy_aliases goes through strip_tweak_block (marker-scoped, atomic); remove_tweak delegates to it, so there is no third read-strip-write copy (REUSE 14-1)"
  - "strip_legacy_aliases takes no home parameter; LegacyStrip.rc is display_path(rc_path) (REUSE 14-2)"
  - "The startup warning composed in _build_app carries the TUI launch notice (the single composition root for every TUI route)"
  - "The split-mode reader is one module-level _split_sourced_from(link_mode), injected by post_install.use_shell_init_sourcing in the TUI composition and on the headless route (RUN-LEDGER 09-2 option b, R1-05)"
  - "The six shell-init declarations land here, after the keyed prompts exist in both front ends (R1-42)"

patterns-established:
  - "Retired ids keep their legacy table only; BUNDLES holds none of them, and a test asserts the absence on every platform"

metrics:
  duration: unmeasured (no start timestamp recorded for this run)
  completed: 2026-11-07
---

# Phase 23 Plan 14: Legacy alias strip and composition Summary

**The four agent alias bundles leave Policies; an enabled legacy alias block is stripped from ~/.myshellrc at every launch and in the CLI uninstall with a one-line notice that points at the auto-approve row, and nothing is written to any agent settings file. The app now composes the nine settings rows, the Linux desktop SHELL row, and the install-time shell-init question for six tools.**

## Performance

- **Tasks:** 3 of 3, each test-first, one green `feat(23-14)` commit each (tests and code together).
- **Commits (measured with `git rev-list --count ef1bbeb..HEAD`):** `523611d` (Task 1), `fca1574` (Task 2), `5e529ea` (Task 3). Base `ef1bbeb`.
- **Gates:** `make validate` exit 0 and `make test` exit 0 on the tree of each commit (run before each commit; the tree did not change between the two runs and the commit).
- **Suppressions:** `git diff ef1bbeb HEAD` adds 0 and removes 0 lines matching `type: ignore|pyright: ignore|noqa|nosec`.

## Accomplishments

- `installer/tweaks.py`:
  - `_CLAUDE_BODY`, `_CODEX_BODY`, `_OPENCODE_BODY`, `_CURSOR_DEFAULT_MODEL`, `_CURSOR_AGENT_BODY` and their four `TweakBundle` entries deleted from `BUNDLES`.
  - `strip_tweak_block(bundle_id, rc_path) -> bool`; `remove_tweak` delegates to it.
  - `LEGACY_ALIAS_BUNDLES` (alias id to the agent whose row the notice names; `None` for the cursor wrapper).
  - `LegacyStrip(rc, stripped, failed)` with `launch_lines()`, `failure_lines()` and `uninstall_line()`.
  - `strip_legacy_aliases(rc_path)`: idempotent, table order, an `OSError` keeps the block and records `(alias, first line)`.
- `setup.py`:
  - `_build_app` strips at composition time and joins the notices with any existing settings warning into `startup_warning`.
  - Headless `--all`/`--categories` prints each launch line before `run_wizard`.
  - CLI `_run_uninstall` prints `uninstall_line()` and each failure line.
  - Policies appends `*settings_policies(...)` and then `*desktop` (`desktop_shell_policy` with `which_with_brew("zsh")`, Linux only); every `extra_policies` site passes `(*redirects, *desktop)`, and the CLI uninstall sweep includes the desktop row.
  - `_split_sourced_from(link_mode)` hoisted to module level; `use_shell_init_sourcing` called in `_build_app` and on the headless route.
- `installer/registry.toml`: `post_install = ["source_shell_init"]` on starship (with a dated Phase 23 D-11 comment), direnv, zoxide, fzf, fnm and volta.
- `tests/conftest.py`: autouse `no_shell_init_sourcing` resets `post_install._shell_init_sourced_from` per test (monkeypatch restores it).

## Task Commits

1. **Task 1: the agent alias bundles leave Policies and legacy blocks are stripped** - `523611d`
2. **Task 2: strip legacy alias blocks at launch and uninstall** - `fca1574`
3. **Task 3: wire the settings rows and the shell-init question into the app** - `5e529ea`

## Test-first evidence

### Worktree and host-safety checks (before Task 1)

- Branch check (orchestrator block): `worktree-agent-abbe1c797ca1c46e1`, base `ef1bbebd61e78ccf7595d45a7735975eed6e3dc4`, not a protected branch; passed.
- cwd-drift sentinel (`gsd-spawn-toplevel`) and plan-head ledger (`gsd-plan-head-before-23-14`) written under the worktree git dir before the first commit.
- `make install` created the worktree `.venv` (gitignored). No `make setup`, `make fix`, `make uninstall`, sudo, or real rc or settings write.
- `uv run pytest tests/test_sandbox.py -k no_setup_home_constant -q --no-cov -n 0` output (before Task 2, and again before Task 3):
  ```
  .                                                                        [100%]
  ```
  and `tests/test_sandbox.py` full file: `.....` (5 passed).

### Real `~/.myshellrc` fingerprint (read-only, before and after every `make test` run)

| Point | `sha256sum ~/.myshellrc` | `stat -c '%s %Y'` |
| --- | --- | --- |
| Before Task 1 gate | `c3db1d823958f1bedabe469e1d70b6331bb6af7795b40afac6faf2c146a2606b` | `4376 1792008265` |
| After Task 1 `make test` | same | same |
| Before Task 2 tests | same | same |
| After Task 2 `make test` | same | same |
| After Task 3 `make test` (first run, 2 failures, before the fixes) | same | same |
| Before final Task 3 `make test` | same | same |
| After final Task 3 `make test` | same | same |

The before-fingerprint of the first Task 3 run was issued in the same background command as that run, and its output was not captured. The final run has both before and after values. Every other run has both. No test or command read-wrote the real rc; the session fingerprint never changed.

### Task 1

RED (plan command after the five tests were written, before any implementation; not committed alone):
```
ERROR tests/test_policy_tweaks.py
ImportError while importing test module '.../tests/test_policy_tweaks.py'.
E   ImportError: cannot import name 'LEGACY_ALIAS_BUNDLES' from 'installer.tweaks'
ERROR tests/test_tweaks.py
E   ImportError: cannot import name 'strip_legacy_aliases' from 'installer.tweaks'
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
exit=2
```
GREEN (same selection, after implementation): `....` (4 passed), exit 0. Full suite afterwards: `5755 passed, 4 skipped`, exit 0.
Gate: `make validate` exit 0 (one `ruff format` pass on `tests/test_policy.py` after a first failed validate; no logic change); `make test` exit 0, coverage 96.20%.

### Task 2

RED (plan command, four tests written, before the setup.py wiring):
```
FAILED tests/test_setup.py::test_launch_strips_and_shows_the_notice - assert ... (the notice missing from the startup warning)
FAILED tests/test_setup.py::test_headless_launch_strips_and_prints_the_notice_before_the_plan - assert ... (the notice missing)
FAILED tests/test_setup.py::test_the_cli_uninstall_strips_legacy_alias_blocks
E   AssertionError: assert 'Removed the codex-skip alias block(s) from ~/.myshellrc.' in ''
FAILED tests/test_setup.py::test_headless_main_strips_only_the_scratch_rc
E   AssertionError: assert 'tools-installer tweak:claude-skip' not in '# >>> tools-installer tweak:claude-skip >>>...'
4 failed
```
GREEN (focused, same four): `....` (4 passed), exit 0.
Gate: `make validate` exit 0 (after two pyright strict fixes in the new tests: a `cast` on the `run_wizard` wrapper and a typed `def` in place of an untyped lambda); `make test` exit 0, `5759 passed, 4 skipped`, coverage 96.20%.
Plan verify: `uv run pytest tests/test_setup.py tests/test_wizard_app.py -n auto -q --no-cov` exit 0; `uv run pytest tests/test_sandbox.py -q --no-cov -n 0` exit 0.

### Task 3

RED (four tests written, before the composition and registry edits):
```
FAILED tests/test_setup.py::test_the_app_composes_the_settings_rows
E   AssertionError: assert ['tweak:apt-u...eak:fnm', ...] == ['agent:claud...ibution', ...]
FAILED tests/test_setup.py::test_the_composition_root_wires_split_mode_sourcing
E   AssertionError: assert (PosixPath('.../.bashrc')) in ()
FAILED tests/test_setup.py::test_the_headless_route_injects_split_mode_sourcing
E   AssertionError: assert (PosixPath('.../.bashrc')) in ()
FAILED tests/test_registry.py::test_the_six_tools_declare_shell_init
E   AssertionError: starship
4 failed
```
GREEN (focused, same four): `....` (4 passed), exit 0.

Existing tests that the new state broke, found by the first full run (2 failed, 5761 passed) and fixed:
```
FAILED tests/test_setup.py::test_the_policies_view_is_wired_ban_then_tweaks_then_omz
E   assert False   (the settings rows now follow the cache redirects)
FAILED tests/test_registry.py::test_only_reviewed_tools_declare_a_post_install_action
E   AssertionError: assert ['zoxide', 'f... 'volta', ...] == ['oh-my-zsh', 'vscode']
```
After the two assertions were updated to the new expected state, both pass (`..`, exit 0).
Gate: `make validate` exit 0 (after an E501 wrap in one comment); `make test` exit 0, `5763 passed, 4 skipped`, coverage 96.19%.

## Test counts (measured where stated)

| Point | Passed | Skipped | Note |
| --- | --- | --- | --- |
| Base `ef1bbeb` | 5768 | 4 | Derived, not measured at base: the Task 1 count minus the 5 new tests plus the 18 removed tests |
| After Task 1 (`make test`, exit 0) | 5755 | 4 | measured |
| After Task 2 (`make test`, exit 0) | 5759 | 4 | measured |
| After Task 3 (`make test`, exit 0) | 5763 | 4 | measured |

Plan delta: +13 new tests (Task 1: 5; Task 2: 4, of which 3 were named by the plan and 1 is the extra headless-notice test; Task 3: 4), and 18 removed (the bundle-pinned tests listed under "Changed existing tests"). Net -5; 5768 + 13 - 18 = 5763.

## Changed existing tests (each with its reason)

Deleted (their bundles, bodies or behaviour no longer exist; the plan requires the removal, and the absence is asserted by `test_policies_list_none_of_the_four_alias_bundles`):
- `tests/test_tweaks.py`: `test_codex_skip_body_matches_the_verified_flag`, `test_opencode_auto_body_matches_the_verified_flag`, `test_opencode_auto_description_states_it_is_narrower_than_a_full_bypass`.
- `tests/test_tweaks.py`: the twelve cursor-agent behaviour tests (`test_cursor_*`) and the `_run_cursor_agent` helper and `_SCRIPT_COUNTER`; their wrapper body was deleted. Also the now-unused `import itertools`.
- `tests/test_policy_tweaks.py`: `test_codex_skip_policy_round_trips`, `test_opencode_auto_policy_round_trips`, `test_cursor_agent_model_policy_round_trips`.

Retargeted (the bundle id is no longer offered; the assertion keeps its meaning on a bundle that stays in `BUNDLES`):
- `tests/test_tweaks.py`: `test_block_is_marker_delimited_around_body`, the two `tweak_executables_present` asserts, `test_re_enable_does_not_duplicate`, and the apt-upgrade platform set: `claude-skip` to `docker`, and `claude-skip` removed from the expected set. `test_bundles_have_stable_ids_and_order` lost the four alias ids.
- `tests/test_policy_tweaks.py`: `test_remove_strips_block` to `docker` (asserts `docker-stats` is gone); the three `ensure_sourced_from` tests and the fresh-shell test from `codex-skip` to `docker`; the fresh-shell assertion now checks `alias docker-stats`.
- `tests/test_policy.py`, `tests/test_policies_e2e.py`: `claude-skip` to `docker` throughout (a rename; the assertions are unchanged in meaning).
- `tests/test_policies_e2e.py::test_policies_screen_link_mode_change_moves_active_policies`: the tweak policy is given `installed_tools={"watch": True}`. `docker` requires `watch`, and the screen refuses to apply a row whose requirement is missing (`claude-skip` had none). The retired-alias parametrize list keeps the four alias ids on purpose: those are synthetic `Policy` objects that guard the retired copy.
- `tests/test_setup.py`: five `tweak:codex-skip` lookups to `tweak:docker` (plan R2-01).
- `tests/test_setup.py::test_the_policies_view_is_wired_ban_then_tweaks_then_omz`: the post-daemon assertion now expects the cache-redirect rows followed by the nine settings rows (the plan appends them after the existing rows). macOS has no desktop row, and the test asserts that.
- `tests/test_registry.py::test_only_reviewed_tools_declare_a_post_install_action`: the declarers set now includes the six shell-init tools (D-11), as a set comparison.

## Deviations from Plan

### Scope note (not done)

**The orchestrator's execution note says 23-14 wires `unregister_argvs`, `hook_method` and `host_labels` in `installer/postinstall.py`. The 23-14 PLAN contains no such task, and `installer/postinstall.py` is not in its `files_modified`.** `hook_method` belongs to 23-08 (REUSE 05-1, uninstall.py), and the `host_labels` display belongs to 23-15 (its `unregister` lines and `host_labels(hook_hosts)`). Nothing was done for them here. The orchestrator should confirm the note.

### Auto-fixed and plan-interpretation items

1. **[Task 1, RED shape]** The RED run failed at collection (`ImportError` for the new names), not at an assertion. The tests import names that do not exist yet, so they fail as required; this is a real RED.
2. **[Task 2, `LegacyStrip.failure_lines()`]** A small public method was added beyond the plan's interface (`launch_lines`, `uninstall_line`). `launch_lines()` now builds its failure entries from it, and the CLI uninstall prints the failure lines from it, so the `Could not remove ...` copy exists once.
3. **[Task 2, startup warning location]** The plan's text puts the notice into the TUI launch path. The notice is composed inside `_build_app`, where `startup_warning` is built; that is the one composition root every TUI route passes through. So the TUI uninstall and guard routes also show the notice when a legacy block is present. The effect is the same for the TUI launch the plan describes.
4. **[Task 2, extra test]** `test_headless_launch_strips_and_prints_the_notice_before_the_plan` was added beyond the plan's three tests: it checks the headless print happens before `run_wizard`, which the plan's text asks for.
5. **[Task 3, helpers]** `_desktop_shell_policies(platform)` is a new module-level helper (the plan wrote the desktop row inline in three places). `desktop_shell_policy` is called without an `installed_tools` argument, as 23-11 defined it.
6. **[Task 3, headless injection point]** `post_install.use_shell_init_sourcing` is called on the headless route right before `_build_services`, after the interactive branch; `run_wizard` is called after it, as the plan requires.
7. **[CLI uninstall ordering, risk]** The plan orders the CLI uninstall as "strip first". The strip runs before `run_uninstall`'s own confirmation, so a user who answers no to the CLI uninstall prompt still has legacy alias blocks removed. The blocks are installer-owned and no longer offered, and the printed notice says what was removed. Flagged for the orchestrator to accept or change.
8. **[Task 3, RED for the existing tests]** The two existing assertions that the plan's new state breaks were updated (listed above). Each update is the plan's own requirement, not a loosening.

No file outside the plan's `files_modified` list was edited.

## Issues Encountered

- **Harness refused compound shell commands** that mixed `git` with a `$(...)`, a `for` loop over computed values, or a `cd && ...` chain. Each was split into plain commands run from the worktree root. No command ran outside the worktree.
- **`make test` was run in the background** for each gate; the completion notifications were read from the logs, not polled.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. Each threat has a test:

- T-23-36 (auto-approval written at launch): `test_an_enabled_claude_skip_alias_is_stripped_and_nothing_written` (no `~/.claude/settings.json`, no config-write ledger), `test_the_cursor_model_alias_is_removed_and_nothing_written`, `test_launch_strips_and_shows_the_notice`, `test_headless_launch_strips_and_prints_the_notice_before_the_plan`.
- T-23-37 (stripping user content): the strip goes through `strip_block` on the owned markers only; `test_a_block_that_cannot_be_edited_is_kept_with_a_warning`.
- T-23-38 (legacy blocks left after uninstall): `test_the_cli_uninstall_strips_legacy_alias_blocks`.
- T-23-60 (the real `~/.myshellrc` reached by a `setup.main` test): `test_headless_main_strips_only_the_scratch_rc`, the 23-01 guard test (green before Tasks 2 and 3), and the fingerprint table above.
- T-23-61 (an install-time shell-init yes that split mode never sources): `test_the_composition_root_wires_split_mode_sourcing`, `test_the_headless_route_injects_split_mode_sourcing`; the per-test reset in `tests/conftest.py`.
- T-23-SC: no package added.

## Not checked

- **No live run of the app.** Per the host-safety rule, `setup.py` was never run against the real HOME. Behaviour is covered through captured `UnifiedApp` kwargs, fake installs and fake `run_uninstall`, all under the scratch HOME.
- **Multi-line `startup_warning`.** Three notices are joined with `\n` into one `startup_warning`. No test checks how the first-view status line renders a multi-line warning at 80x20; this needs a look in a real terminal or a layout test.
- **Second launch prints nothing, end to end.** The idempotence of a second strip is covered by the unit test (`again.stripped == ()`, `launch_lines() == ()`), not by a second `main()` run.
- **macOS settings and desktop rows.** The desktop row's absence on macOS is asserted only through the existing macOS ordering test; the nine rows' content is covered by 23-11.
- **Real `zsh` lookup.** `which_with_brew("zsh")` is used as the plan requires; tests run with whatever zsh the host has, and the desktop row's `zsh_path` value is not asserted.

## Self-Check

- [x] `523611d`, `fca1574`, `5e529ea` exist after base `ef1bbeb` (`git rev-list --count ef1bbeb..HEAD` = 3 before this SUMMARY commit).
- [x] Each commit's tree passed `make validate` (exit 0) and `make test` (exit 0).
- [x] The real `~/.myshellrc` fingerprint is unchanged across every run (table above).
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.
- [x] Changed files are exactly the plan's `files_modified` list.
- [x] No new `type: ignore`, `pyright: ignore`, `noqa` or `nosec` line (0 added, 0 removed).
- [x] No `--no-verify`, no `git stash`, no history rewrite, no attribution trailers.
