---
phase: 23-configuration-as-a-lifecycle-step
plan: "09"
subsystem: installer
tags: [shell-init, post-install, tweaks, shellrc, omz, tdd]
status: complete
requirements-completed: [CONF-04, CONF-11, CONF-12]

# Actuals (#2632): chars/4 over the realized code diff (git diff 3dd533e..836e796, 32289 chars)
actuals:
  tokens: 8072
  tasks: 3
  commits: 3

# Measured commit ledger (#3968): rev-list count from the plan base, taken before this SUMMARY commit.
# The count includes the earlier blocked-plan SUMMARY commit 3dd533e.
commits: 4
plan_head_before: 58fe43485d5a573da08956a70eac6b75a66d4c57
plan_head_after: 836e796
---

# Phase 23 Plan 09: Shell-init bundles and install handoffs — Summary

**Starship, direnv, zoxide, fzf, fnm and volta each offer a default-off shell-init block at install; starship's yes also makes it the only prompt; Oh-My-Zsh names its theme; VS Code prints its lean tips; the chsh-absent text names the sync that actually runs.**

## Performance

- **Tasks:** 3 of 3, each test-first with one green commit.
- **Commits:** `49a8913`, `8902667`, `836e796`. The earlier blocked-plan SUMMARY commit `3dd533e` is kept in history.
- **Test counts:** base `5680` (5676 passed, 4 skipped) → after Task 1 `5686` → after Task 2 `5711` → after Task 3 `5719` (5715 passed, 4 skipped). The plan delta is +6, +25 and +8.

## Accomplishments

- `installer/tweaks.py`: `SHELL_INIT_TOOLS`, six shell-init bundles (`id` = tool id, `requires=(tool,)`, `platforms=()`, description = the UI-SPEC effect), `shell_init_bundle(tool_id)`. The bundles sit in `BUNDLES` after `apt-upgrade`.
- `installer/post_install.py`:
  - `SensitivePrompt` (with `default`), `SENSITIVE_PROMPTS` and `sensitive_prompt`. `sensitive_prompt` raises `KeyError` for an action with no entry.
  - The split-mode reader `_shell_init_sourced_from` and its setter `use_shell_init_sourcing`.
  - Actions `source_shell_init` (through `tweak_policy(...).apply()`, and `apply_theme` for starship), `set_omz_theme` and `show_lean_tips`.
  - The third chsh-absent line now names the terminal sync.
- `installer/model.py`: `POST_INSTALL_ACTIONS` and `SENSITIVE_POST_INSTALL_ACTIONS` gained the new names.
- `installer/shellrc.py`: `_apply_path_block`, used by `write_myshellrc` and `write_managed_path`. A PATH block written into a file with none yet lands above the first tweak or source block. An existing PATH block is still replaced in place. `apply_block` is unchanged.
- `installer/registry.toml`: oh-my-zsh declares `["set_login_shell", "set_omz_theme"]`; vscode declares `["show_lean_tips"]`. The six `source_shell_init` declarations are not here. They belong to 23-14, as the plan says.

## Task Commits

1. **Task 1: offer starship and friends' shell init at install, default off** — `49a8913` (feat; tests and code in one commit).
2. **Task 2: six guarded shell-init bundles** — `8902667` (feat; tests and code in one commit).
3. **Task 3: theme and lean-mode handoff lines; chsh-absent text names the sync** — `836e796` (feat; tests and code in one commit).

## Test-first evidence

### Task 1

RED, the plan's command, at collection on the missing API. No test ran:
```
ImportError: cannot import name 'SENSITIVE_PROMPTS' from 'installer.post_install'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
exit=2
```

RED, the model test on its own:
```
FAILED tests/test_model.py::test_post_install_action_names_include_the_new_actions
E       AssertionError: assert ('configure_p..._login_shell') == ('configure_p...ow_lean_tips')
exit=1
```

GREEN, targeted (the six new tests, the renamed model test and the disjoint-table test): `8 passed`, exit 0.

GREEN, full gate on the committed tree: `make validate` exit 0. `make test` exit 0, `5682 passed, 4 skipped`, coverage 96.20%.

### Task 2

RED, 25 selected tests, `3 failed, 22 passed`. The failures are the three placement tests:
```
FAILED tests/test_post_install.py::test_a_first_install_puts_the_path_block_above_shell_init
FAILED tests/test_shellrc.py::test_a_new_path_block_lands_above_the_first_tweak_block
FAILED tests/test_shellrc.py::test_a_new_path_block_lands_above_the_source_block
E       assert 7 < 0   (path block index 7; zoxide tweak index 0)
```

The other 22 passed on the Task 1 code. They are regression guards, not RED: the six `follows_yes_and_no` cases, six `guarded_and_parses` cases, six `parses_in_zsh` cases, `sit_after_apt_upgrade`, `only_starship_touches_the_theme`, `test_an_existing_path_block_is_replaced_in_place` and `test_a_file_without_path_or_tweak_block_appends_the_path_block`.

GREEN, the same 25 selected tests: `25 passed`, exit 0. None were skipped; zsh is on the host, so `parses_in_zsh` ran.

GREEN, full gate: `make validate` exit 0 (after one E501 fix). `make test` exit 0, `5707 passed, 4 skipped`.

### Task 3

RED, 8 selected tests, `7 failed, 1 passed`. The failures are the behavioural ones, because `set_omz_theme`, `show_lean_tips` and the registry declarations did not exist yet:
```
FAILED tests/test_post_install.py::test_omz_install_adds_robbyrussell_and_names_the_theme_commands
FAILED tests/test_post_install.py::test_omz_install_keeps_a_user_theme
FAILED tests/test_post_install.py::test_a_user_theme_name_is_sanitized_in_the_handoff
FAILED tests/test_post_install.py::test_omz_install_with_starship_on_writes_an_empty_theme
FAILED tests/test_post_install.py::test_vscode_install_returns_the_lean_tips
FAILED tests/test_post_install.py::test_the_chsh_absent_text_names_the_sync_that_runs
FAILED tests/test_registry.py::test_omz_and_vscode_declare_their_actions
E       AssertionError: assert ('set_login_shell',) == ('set_login_s...et_omz_theme')
```

`test_omz_install_without_oh_my_zsh_hands_off_nothing` passed on the Task 2 code. It is a regression guard.

GREEN, targeted: `8 passed`, exit 0.

GREEN, full gate: `make validate` exit 0. `make test` exit 0, `5715 passed, 4 skipped`.

## Deviations from Plan

### 1. [Coordinator decision — Q4 amended] volta body exports only `VOLTA_HOME`

- **Found during:** Task 1 `make test`.
- **Issue:** The plan's volta body prepends `~/.volta/bin` to PATH with `export PATH="$VOLTA_HOME/bin:$PATH"`. That line trips `tests/test_shellrc.py::test_no_accumulating_path_build_under_installer_or_setup`, the PATH-accumulation invariant. Its only exemption is the `rcclean.py` docstring, and the rules forbid exempting or silencing it. An earlier executor stopped here and recorded the blocker (`3dd533e`). A patch of the work was saved outside the repo.
- **Decision (binding, from the coordinator):** the volta body exports only `VOLTA_HOME`. `~/.volta/bin` reaches PATH through the managed PATH block via the registry `bin_dir` (`bin_dir = "~/.volta/bin"`, wired by `collect_bin_dirs` once the directory exists). A custom `VOLTA_HOME` outside `~/.volta` is not supported. This is recorded as a `shortcut:` comment above `_VOLTA_BODY` in `installer/tweaks.py`.
- **Copy kept:** the volta bundle's description is still the UI-SPEC section 2 text, `exports VOLTA_HOME and puts Volta's bin directory on PATH`. It stays verbatim because the copy is locked. Its PATH half is delivered by the managed PATH block, not by the body. **Open copy point for the orchestrator:** the UI-SPEC wording may need a one-line amendment, or the description may stay as is.

### 2. [Plan-forced test changes] existing assertions updated

Each change is listed with its reason. No test was deleted and no assertion was weakened.

- `tests/test_model.py`: `test_post_install_actions_are_the_live_ones` is renamed to `test_post_install_action_names_include_the_new_actions`. Its literal now holds the five plan names, and it also checks the sensitive tuple and that a registry row declaring `source_shell_init` loads. Reason: the names exist from this plan on.
- `tests/test_post_install.py`: `test_post_install_tables_are_disjoint_and_match_their_schema_sets` replaces `len(actions) == 1` and `actions <= sensitive` with `sensitive <= actions`. Reason: the plan adds a second dispatched action (`source_shell_init`), and Task 3 adds non-sensitive ones.
- `tests/test_tweaks.py`: `test_bundles_have_stable_ids_and_order` gains the six shell-init ids in `SHELL_INIT_TOOLS` order. Reason: the plan puts them into `BUNDLES` after `apt-upgrade`.
- `tests/test_registry.py`: `test_only_oh_my_zsh_declares_a_post_install_action` is renamed to `test_only_reviewed_tools_declare_a_post_install_action`. Its expected set is now `["oh-my-zsh", "vscode"]`, and oh-my-zsh's expected actions now include `set_omz_theme`. Reason: the D-07 guard is about reviewed declarers, and this plan adds two reviewed declarations (CONF-11 and CONF-12). The guard still fails on any unreviewed declarer.

### 3. [Judgement] handoff copy outside the plan's examples

- A theme line that cannot be read (for example, a value with a space) reads `Theme: your own theme (left as is).`. The plan gave no copy for this case.
- An installer-owned `robbyrussell` that a later run replaces with `robbyrussell` again reads with the "added because ~/.zshrc had no ZSH_THEME" line. This is an edge case, and the copy is slightly wrong there.

## Verification

- Acceptance greps: `def sensitive_prompt(` is 1 in `post_install.py`. `"source_shell_init"` is 2 in `model.py`. It is 0 in `registry.toml`. `SHELL_INIT_EFFECTS` is 0. `tweak_policy(` is 1 in `post_install.py`. `write_tweak(` is 0 in `post_install.py`. The new chsh sentence is 1. The stale sentence is 0 across `installer/`.
- `apply_block` is unchanged. The `installer/shellrc.py` hunks are at lines 234 and later.
- Suppression gate: `git diff 58fe434 HEAD` adds zero `type: ignore`, `pyright: ignore`, `noqa` or `nosec` lines.
- Collected test count: base 5680, final 5719.

## Process notes

- Worktree branch check passed: branch `worktree-agent-a49d102674b326af5`, base `58fe434`. The cwd-drift sentinel and the plan-head ledger were written before the first commit.
- `codegraph init -i` ran in the worktree (gitignored). `make install` created the worktree `.venv` (gitignored).
- The harness refused some compound git commands, and some commands that named git inside a variable. Each was split into plain commands run from the worktree.
- Lint fixes applied during the gate, with no suppressions: a long docstring and a lambda assigned to a name (Task 1), an import sort and a long docstring (Task 2).
- The test-session guard did not trip on any `make test` run.
- AGENTS.md asks for a `Co-Authored-By` trailer. The orchestrator asked for no attribution trailers, and I followed that. No commit here has a trailer.
- Nothing ran on the real host. No `make setup`, `make fix` or `make uninstall`. No real rc, settings or shell file was touched. No sudo.

## Not done in this plan (by design)

- The six `post_install = ["source_shell_init"]` registry declarations, and the split-mode reader wiring through `use_shell_init_sourcing`, belong to 23-14.
- The keyed TUI modal (23-12) and the headless prompt (23-13) still carry the login-shell text literals and read `SENSITIVE_PROMPTS` only after those plans land.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-23-23 (shell-init body injection) is covered by the code-constant bodies and `test_each_shell_init_body_is_guarded_and_parses`. T-23-24 (no consent, no enable) is covered by `test_shell_init_is_never_turned_on_without_a_yes` and `test_each_shell_init_tool_follows_yes_and_no`. T-23-58 (a PATH block below the guards) is covered by `test_a_first_install_puts_the_path_block_above_shell_init`. T-23-25 (ANSI in a theme name) is covered by `test_a_user_theme_name_is_sanitized_in_the_handoff`.

## Self-Check: PASSED

- [x] Commits `49a8913`, `8902667` and `836e796` exist on `worktree-agent-a49d102674b326af5` after base `58fe434`.
- [x] `make validate` exit 0 and `make test` exit 0 on each task's committed tree.
- [x] No change to `STATE.md` or `ROADMAP.md`.
- [x] No trailers in any commit message.
