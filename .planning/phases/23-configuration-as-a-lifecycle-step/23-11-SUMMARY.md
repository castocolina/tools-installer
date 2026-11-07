---
phase: 23-configuration-as-a-lifecycle-step
plan: "11"
subsystem: policies
tags: [policies, settings, agent-settings, shell-init, desktop-shell, environment.d, tdd]
requires:
  - phase: 23-04
    provides: shell_redirect, DESKTOP_SHELL_CONF, conf_owned, remove_owned_conf, linux_applied
  - phase: 23-06
    provides: agent_settings apply/revert/setting_state, config-write ledger, display_path
  - phase: 23-09
    provides: SHELL_INIT_TOOLS, shell_init_bundle, the six shell-init bundles
provides:
  - Policy.effect_kind, Policy.state, Policy.detail_lines, PolicyResult.changed (appended)
  - settings_policy, settings_policies (nine rows, UI-SPEC copy), desktop_shell_policy, shell_init_detail
  - agent_settings.SettingFacts and setting_facts (the one classification; setting_state maps over it)
  - PoliciesScreen yours state, set-by-you/drift/already detail lines, changed-False refusals
affects: [23-14, 23-15]

# Actuals (#2632): chars/4 over the realized diff (git diff 9440a74 HEAD = 75562 chars)
actuals:
  tokens: 18890
  tasks: 3
  commits: 4

# Measured commit ledger (#3968): rev-list count from the plan base, before this SUMMARY commit
commits: 5
plan_head_before: 9440a741d4d4636c736d55668bc214a5b91ab710
plan_head_after: e9ae14d

key-files:
  modified:
    - installer/policy.py
    - installer/agent_settings.py
    - installer/wizard_app.py
    - tests/test_policy_settings.py
    - tests/test_policies_e2e.py
    - tests/test_agent_settings.py
    - tests/test_wizard_app.py
    - tests/test_layout_80x20.py
  created:
    - tests/test_policy_settings.py

key-decisions:
  - "A settings row's yours refusal is produced by its apply closure, not by the screen: the screen has no path to put in the copy, and the policy does"
  - "setting_facts leaves a CLI-default value (cursor attribution true) out of set_by_you, because apply replaces it"
  - "desktop_shell_policy takes no installed_tools argument: a missing zsh is zsh_path None, which sets requires=(zsh,) and the missing list"
  - "Settings reads go through policy.state into the existing active/drift pair; yours is a separate set on the screen"

metrics:
  duration: unmeasured (no start timestamp recorded for this run)
  completed: 2026-11-07
status: complete
---

# Phase 23 Plan 11: Policies rows Summary

**Policies lists one row per agent and VS Code setting with on, yours, off and drift states and exact toggle results; the six shell-init rows and the desktop SHELL row toggle, read and remove through the one writer, and the desktop row is swept by its conf sentinel. The Task 3 behaviour tests were written after the implementation and are proved by mutation.**

## Task Commits

1. **Task 1: agent and editor settings rows in Policies** - `bebc5a8` (feat; tests and code together)
2. **Task 2: settings rows read yours, drift and unreadable states** - `5470ca4` (feat)
3. **Task 3: shell-init, VS Code and desktop SHELL rows with their details** - `c58a9e6` (feat)
4. **Gap closure: 80x20 fit, shell-init toggle, desktop sweep, retired alias copy** - `e9ae14d` (test; no production code changed)

Each commit was made after `make validate` exit 0 and `make test` exit 0 on that exact tree. The pre-commit hooks passed on each commit. No trailers were added. No commit used `--no-verify`.

## Test-first evidence

### Task 1

RED, the plan's command (`uv run pytest tests/test_policies_e2e.py tests/test_policy_settings.py -k "auto_approve_toggles_from_policies or results_map_every_outcome or requires_its_agent" -q --no-cov -n 0`), exit 2. Both files fail at collection because `settings_policy` does not exist yet:
```
ERROR tests/test_policies_e2e.py
ERROR tests/test_policy_settings.py
E   ImportError: cannot import name 'settings_policy' from 'installer.policy'
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!
```
The full RED output is in the scratchpad at `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-task1.txt`.

GREEN, the same selection: exit 0. One failure on the first GREEN run was in my own test (a `mkdir` that the installer's leftover directory made fail); fixed in the test.

Two existing tests needed a change for the plan's appended fields: see "Changed existing tests" below.

### Task 2

RED, `-k "setting_facts_split or preset_accept_edits or already_set_read_yours or drifted_row_rewrites or unparsable_file_with_a_ledger or unparsable_file_without_a_ledger"`, exit 1, four failing:
```
FAILED tests/test_agent_settings.py::test_setting_facts_split_written_yours_already_and_drift
    AttributeError: module 'installer.agent_settings' has no attribute 'SettingFacts'
FAILED tests/test_policies_e2e.py::test_a_preset_accept_edits_shows_set_by_you
    assert 'Set by you: permissions.defaultMode = "acceptEdits" (left as is).' in '...'
FAILED tests/test_policies_e2e.py::test_keys_already_set_read_yours_and_space_writes_nothing
    AssertionError: assert '○ [off]' == '● [yours]'
FAILED tests/test_policies_e2e.py::test_a_drifted_row_rewrites_absent_keys
    AssertionError: assert 'Only keys yo...' == 'Drift: this ...'
```
The two unparsable-file tests already passed on the Task 1 code, so they are regression guards, not RED. The full output is at `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-task2.txt`.

GREEN, the same selection: `......`, exit 0 (6 tests).

### Task 3 (no RED; the behaviour tests are regression guards, proved by mutation)

I wrote `shell_init_detail`, `desktop_shell_policy`, the `tweak_policy` detail hookup and the alias-entry removal before any Task 3 test. No RED run was observed for them, so the test-first rule was not followed for this task.

The Task 3 tests that exist are: the unit tests in `tests/test_policy_settings.py` (`test_policies_list_the_new_rows_in_order`, `test_shell_init_rows_show_their_detail`, `test_the_desktop_shell_row_writes_environment_d`, `test_a_desktop_shell_file_outlives_zsh_and_is_still_swept`, `test_vscode_and_cursor_details_follow_the_spec`), the literal-render pilot `test_settings_values_render_literally`, and the gap-closure tests below. They were written after the implementation and pass on it, so they are regression guards.

To show they can fail, I applied one-line mutations to the committed code, ran the target test, and restored the file with `git checkout -- <file>` (the tree was clean, so this restores the committed content exactly):

| # | File | Mutation | Target test | Result |
| --- | --- | --- | --- | --- |
| M1 | `installer/policy.py` | desktop `owned=` forced to `lambda: False` | `test_policy_settings.py::test_the_desktop_shell_row_is_swept_by_its_sentinel` | FAILED (exit 1) |
| M2 | `installer/policy.py` | `tweak_policy` `_remove` no longer calls `remove_tweak` | `test_policies_e2e.py::test_a_shell_init_row_toggles_its_bundle_under_a_scratch_rc` | FAILED (exit 1) |
| M3 | `installer/wizard_app.py` | `_policy_detail` dict gets the retired `tweak:claude-skip` entry back | `test_policies_e2e.py::test_retired_alias_rows_show_only_the_generic_detail[tweak:claude-skip]` | FAILED (exit 1) |
| M4 | `installer/policy.py` | `shell_init_detail` drops the first-letter capitalization | `test_policy_settings.py::test_shell_init_rows_show_their_detail` | FAILED (exit 1) |
| M5 | `installer/wizard_app.py` | `#policy-detail` height 11 becomes 5 | `test_layout_80x20.py::test_policies_fit_80x20_with_the_new_rows` | FAILED at `assert 5 == 11` (exit 1) |

After each restore, `git status --short` was empty.

## Gap closure (commit `e9ae14d`, tests only)

- **80x20 fit.** `test_policies_fit_80x20_with_the_new_rows` (in `tests/test_layout_80x20.py`) runs the Policies screen at `size=(80, 20)` with `NO_COLOR=1` and HOME set to the scratch directory, with the sixteen Task 3 rows (six shell-init, nine settings, desktop). It asserts the chrome, that the State column is 9 cells or fewer, that every label is 28 cells or fewer, that the `#policy-detail` panel is 11 rows high, that every row's detail wraps to 9 lines or fewer at 78 cells, and that a space toggle of the claude row shows its result on screen. The first run failed for `vscode:lean` at 10 wrapped lines, but that run used an absolute temp path (about 80 cells) rather than `~/.config/Code/User/settings.json`; with HOME set it passes. The macOS path is longer and is not checked (see Not checked).
- **Shell-init toggle.** `test_a_shell_init_row_toggles_its_bundle_under_a_scratch_rc` drives the zoxide row through the screen: space writes the block, the state reads on, space removes it, the state reads off.
- **Desktop sweep.** `test_the_desktop_shell_row_is_swept_by_its_sentinel` calls `active_policies` and then `sweep_policies` (the uninstall path). After the zsh path is gone, the conf is listed and swept by its sentinel. A conf without the sentinel is neither listed nor touched.
- **Retired alias copy.** `test_retired_alias_rows_show_only_the_generic_detail`, parametrized over the four retired ids, checks the generic line is shown and the alias text is absent.

## Test counts (measured)

| Point | Passed | Skipped | Collected | Delta |
| --- | --- | --- | --- | --- |
| Base `9440a74` (per-file collection) | not run | - | 5731 | - |
| After Task 1 (`make test`, exit 0, coverage 96.13%) | 5731 | 4 | 5735 | +4 |
| After Task 2 (`make test`, exit 0, coverage 96.16%) | 5737 | 4 | 5741 | +6 |
| After Task 3 (`make test`, exit 0, coverage 96.18%) | 5740 | 4 | 5744 | +3 (6 new, 3 deleted) |
| After gap closure (`make test`, exit 0, coverage 96.18%) | 5747 | 4 | 5751 | +7 (all new) |

## Changed existing tests (each with its reason)

- `tests/test_wizard_app.py::test_policy_appends_decided_closures_after_every_existing_field`: the pinned last four `Policy` fields are now the last seven, because the plan appends `effect_kind`, `state` and `detail_lines`.
- `tests/test_wizard_app.py::test_policy_detail_panel_explains_tweak_rules`: removed the `tweak:claude-skip` policy and its final assertion. The plan removes the four alias detail entries.
- Deleted `test_policy_detail_panel_explains_codex_skip`, `test_policy_detail_panel_explains_opencode_auto_is_narrower_than_a_full_bypass` and `test_policy_detail_panel_explains_cursor_agent_model_wrapper`: each asserted alias copy that the plan removes.

## Deviations from Plan

1. **Task 3 was not test-first.** The implementation came first; see "Task 3" above. The behaviour tests are regression guards and are proved by the five mutations.
2. **Yours refusal lives in the apply closure.** The plan's Task 2 puts the refusal in the screen, but the screen has no path for the copy `{label}: you set these keys yourself; edit {path} to change them.`. The policy has it, so `apply()` returns that warning with `changed=False` for a yours row. The Task 1 unit test's "nothing to write" case would now hit the yours copy, so I moved that case to a non-yours state (one recorded key holds, the other is set to `false`). The copy strings for both messages are unchanged.
3. **`setting_facts` leaves CLI defaults out of `set_by_you`.** A cursor attribution value of `true` is replaced on apply, so it is not the user's value. The plan is silent here.
4. **`desktop_shell_policy` has no `installed_tools` argument.** The plan's signature lists it. A missing zsh is expressed as `zsh_path=None`, which gives `requires=("zsh",)` and the missing list. Dropping the parameter avoids an unused argument.
5. **Shell-init rows suppress the generic tweak sentence.** `_policy_detail` skips the "needs ~/.myshellrc" sentence when `detail_lines` is set, because the four UI-SPEC lines replace it.
6. **The 80x20 fit test is now written** (gap closure). It was missing before.
7. **The sweep path is now exercised** (gap closure) through `active_policies` and `sweep_policies`.
8. **Two Task 3 tests are unit-level, not pilot-level.** `test_policies_list_the_new_rows_in_order` checks composed lists. It does not check the "apt selective upgrade" anchor (composition is 23-14) or the macOS absence of the desktop row. `test_a_settings_row_requires_its_agent` does not drive the screen's refusal text.
9. **Process incident, fixed in the Task 2 commit.** A line-splitting helper I used on over-long copy strings also split one docstring line in `settings_policy`. The docstring is rewritten in the Task 2 commit. Each line the helper touched was one I had added (the base passes lint).

## Verification

- `make validate` exit 0 on each of the four code and test commit trees.
- `make test` exit 0 on each of the four code and test commit trees (counts above).
- `grep -c "def settings_policies(" installer/policy.py` = 1; `grep -c "def setting_facts(" installer/agent_settings.py` = 1; `grep -c "raise SettingsUnreadable" installer/agent_settings.py` = 1.
- `grep -c '"tweak:claude-skip"' installer/wizard_app.py` = 0.
- Suppressions: no `type: ignore`, `pyright: ignore`, `noqa` or `nosec` added in these commits.
- No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.

## Known Stubs

None in the shipped code. Two things are unverified: the starship effect line, which comes from the bundle description; and the desktop row's reload hint, which is copied from the plan and not checked against a real desktop session.

## Threat Flags

None beyond the plan's register. T-23-29 (absent-only writes; yours refuses; drift forgets changed entries) and T-23-30 (parse refusal) are covered by the Task 2 pilots. T-23-31 is covered by the JSON-escaped values and the `Text` rendering, with the literal-render pilot. T-23-32 is covered by the sentinel-keyed `owned` and the sweep test.

## Not checked

- The macOS path length in the VS Code detail. The 80x20 test uses the Linux path (`~/.config/Code/User/settings.json`). The macOS path (`~/Library/Application Support/Code/User/settings.json`) is longer and may wrap past 9 lines; this has not been measured.
- A real desktop session for the environment.d row.
- The macOS side of the rows, beyond the VS Code `update.mode` detail line.
- A real uninstall run: the sweep test calls `active_policies` and `sweep_policies` on the policy objects directly, not through `run_uninstall`.

## Self-Check

- Commits after the base: `bebc5a8`, `5470ca4`, `c58a9e6`, `e9ae14d`, and the earlier SUMMARY commit `dd94615` (`git rev-list --count 9440a74..HEAD` = 5 before this SUMMARY commit).
- Worktree: `/var/home/bazzite/git/personal/tools-installer/.claude/worktrees/agent-a67266155bf23d080`, branch `worktree-agent-a67266155bf23d080`.

## Self-Check: PASSED
