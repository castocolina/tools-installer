---
phase: 25-lean
plan: "03"
subsystem: installer
tags: [lean, sensitive-action, post-install, registry-loader, tui]
requires: []
provides:
  - "no sensitive-action prompt exists in the TUI run or the CLI run; the checksum-mismatch prompt is untouched"
  - "every post-install action takes (tool, platform); run_post_install(tool, platform)"
  - "load_tools rejects default_enabled_sensitive_actions with an explicit retired-key error"
affects: [installer/execute_screen.py, installer/app.py, installer/session.py, installer/engine.py, installer/post_install.py, installer/model.py, .claude/architecture.md]
tech-stack:
  added: []
  patterns: ["explicit retired-key ValueError beside the skill_lifecycle precedent"]
key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - installer/app.py
    - installer/session.py
    - installer/engine.py
    - installer/post_install.py
    - installer/model.py
    - .claude/architecture.md
    - tests/test_execute_screen.py
    - tests/test_app.py
    - tests/test_wizard_app.py
    - tests/test_session.py
    - tests/test_engine.py
    - tests/test_post_install.py
    - tests/test_model.py
    - tests/state_doubles.py
    - tests/test_setup.py
    - tests/test_docs.py
  deleted: []
decisions:
  - "D-11: the consent machinery retired in three green commits (entry points, threading and types, docs)"
  - "SensitiveInstall keeps its name (renaming ripples through about thirty test references); only its docstring changed"
metrics:
  duration: "about 45 minutes"
  completed: "2026-11-15"
status: complete
actuals:
  tokens: 60000
  tasks: 3
  commits: 3
plan_head_before: c6db57a771740c589040d29be2601c0f99cf00b6
plan_head_after: 38ce08e6cf6c701094fccdd2af367118cb6965a0
requirements: [LEAN-01]
---

# Phase 25 Plan 03: Retire the sensitive-action machinery Summary

The empty consent path is gone end to end: 818 lines net left the tree (152 added, 970 deleted across 17 files). No action ever asked, so behaviour is unchanged; the checksum-mismatch prompt, the login-shell handoff text and `repair=True` for repair rows are untouched.

## Commits

| Task | Commit | What |
|------|--------|------|
| 1 | f5a8dada | refactor(25-03): cut the sensitive-action prompt from the TUI and CLI runs |
| 2 | e007918d | refactor(25-03): retire the sensitive-action types and confirmation threading |
| 3 | 38ce08e6 | docs(25-03): describe the repair wrapper, not a sensitive-action confirmation |

`make validate && make test` exit 0 on each commit's tree (7656, 7650 and 7650 passed, 6 skipped; coverage 96.1%).

## RED evidence (Task 2)

```
FAILED tests/test_model.py::test_a_retired_default_enabled_sensitive_actions_key_is_rejected
  Failed: DID NOT RAISE <class 'ValueError'>
FAILED tests/test_post_install.py::test_post_install_actions_take_tool_and_platform_only
  AssertionError: set_login_shell
  assert ['tool', 'pla...m', 'confirm'] == ['tool', 'platform']
```

Both tests were added in the Task 2 commit only; the RED run was never committed alone.

## Tests touched

Class per Interfaces. No test assertion was changed to make the refactor pass; STRIP tests lost only lines about the retired confirmation.

**Task 1**
- DELETE (tests/test_execute_screen.py): the autouse fixture `legacy_sensitive_prompts`; the block `_recording_sensitive_install` through `test_cancel_is_inert_while_the_sensitive_prompt_is_open` (including `_sensitive_action_screen`, `_sensitive_labels`); `test_each_shell_init_prompt_shows_its_effect`, `test_the_login_shell_prompt_is_unchanged`, `_LOGIN_SHELL_TEXT`, and the `SHELL_INIT_TOOLS, shell_init_bundle` import.
- STRIP (tests/test_execute_screen.py): `test_markup_in_review_values_renders_literally` lost `screen_cls = _sensitive_action_screen()` and the modal lines; the `assert any(prompt.startswith(f"○ {markup_id}") ...)` line is byte-identical.
- DELETE (tests/test_app.py): `test_run_wizard_never_asks_sensitive_question_without_login_shell_action`; the `FakePrompter` double lost its `sensitive_confirm` parameter, attribute and branch (`confirm` now answers every question with its one answer).

**Task 2**
- DELETE: tests/test_post_install.py `_record`, `_yes`, `test_sensitive_tables_are_empty`, `test_missing_chsh_explains_without_a_confirm_callback`, `test_missing_chsh_cannot_be_silenced_via_default_enabled`, `test_set_login_shell_ignores_a_refusing_callback`; tests/test_model.py `test_sensitive_tables_are_empty`; tests/test_session.py `test_execute_plan_prints_the_login_shell_handoff_whatever_the_confirmation_says`, `test_execute_plan_forwards_the_confirmation_and_unchanged_kwargs`, `test_sensitive_install_protocol_parameters_are_unchanged`.
- STRIP: tests/test_post_install.py `test_run_post_install_returns_chsh_instructions_without_asking`, `test_run_post_install_skips_when_no_actions_declared`, `test_missing_chsh_explains_without_asking_or_offering_a_command`, `test_missing_chsh_explains_on_mutable_hosts_too`, `test_immutable_host_with_chsh_prints_the_command_without_asking`, `test_unknown_post_install_action_name_is_inert`, and `test_post_install_tables_are_disjoint_and_match_their_schema_sets` (the `sensitive = set(...)` line and its assert); tests/test_model.py `test_post_install_action_names_include_the_new_actions` (the `== ()` line) plus the import name; tests/test_session.py `test_force_repair_composes_under_sensitive_confirm` (kept the result and `recorder.installs` asserts); tests/test_engine.py `test_login_shell_action_dispatches_reviewed_instructions_after_oh_my_zsh_install`, `test_login_shell_action_is_not_offered_when_tool_declares_no_post_install`, `test_already_installed_login_shell_never_invokes_confirm`, `test_manual_required_login_shell_never_invokes_confirm`, `test_repair_dispatches_post_install_like_a_fresh_install`, `test_omz_install_writes_plugins_and_theme_end_to_end`, and the `confirm_sensitive_action=lambda ...` keyword in `test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair`.
- MECHANICAL: every third argument of `run_post_install` in tests/test_post_install.py (45 single-line sites plus the two multi-line ones: the starship lambda and the `set_omz_theme` call with a trailing comment); `_tool` lost its `default_enabled_sensitive_actions` parameter and keyword, `_login_shell_tool` its `default_enabled` parameter; the two `boom` doubles in tests/test_engine.py dropped `_confirm: object`; every install double's `confirm_sensitive_action` parameter, its name in the `del ...` line, forwarded keyword and the `ConfirmSensitiveAction` import in tests/test_execute_screen.py, tests/test_wizard_app.py, tests/test_app.py, tests/test_session.py, tests/test_setup.py and tests/state_doubles.py (`RunRecorder.confirms` dropped, nothing read it); `_run_context` in tests/test_session.py lost its `confirm_sensitive` parameter and keyword; one `assert confirm_sensitive_action is None` line inside an install double in tests/test_session.py went with the parameter it checked.
- ADDED: `test_a_retired_default_enabled_sensitive_actions_key_is_rejected` (tests/test_model.py), `test_post_install_actions_take_tool_and_platform_only` (tests/test_post_install.py).

**Task 3**: tests/test_docs.py lost the `"binds the sensitive-action confirmation"` entry of `_PHASE_14_REQUIRED` and its docstring sentence (a pin of retired text, deleted with its target).

### Renamed tests (names described the retired callback)

| Old | New |
|-----|-----|
| `test_force_repair_composes_under_sensitive_confirm` (tests/test_session.py) | `test_a_reinstall_row_repairs_while_an_install_row_does_not` |
| `test_already_installed_login_shell_never_invokes_confirm` (tests/test_engine.py) | `test_already_installed_login_shell_prints_no_handoff` |
| `test_manual_required_login_shell_never_invokes_confirm` (tests/test_engine.py) | `test_manual_required_login_shell_prints_no_handoff` |

### R1-10 assert lines (retired third argument removed inside an assert; expected value byte-identical)

All in tests/test_post_install.py.

| Test | Before | After |
|------|--------|-------|
| `test_run_post_install_skips_when_no_actions_declared` | `assert run_post_install(_tool(), _mutable(), confirm).lines == ()` | `assert run_post_install(_tool(), _mutable()).lines == ()` |
| `test_unknown_post_install_action_name_is_inert` | `assert (run_post_install(_tool(post_install=("not-a-real-action",)), _mutable(), confirm).lines == ())` (three physical lines) | `assert run_post_install(_tool(post_install=("not-a-real-action",)), _mutable()).lines == ()` |
| the shell-init bundle test | `assert run_post_install(_shell_init_tool("zoxide"), _mutable(), None).lines == ()` | `assert run_post_install(_shell_init_tool("zoxide"), _mutable()).lines == ()` |
| the `set_omz_theme` empty-lines test | `run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable(), None).lines == ()` (inside a parenthesised assert) | `assert run_post_install(_action_tool("oh-my-zsh", "set_omz_theme"), _mutable()).lines == ()` |
| first `set_omz_plugins` assert | `assert run_post_install(tool, _mutable(), None).lines == ("Plugins: added docker to ~/.zshrc.",)` | `assert run_post_install(tool, _mutable()).lines == ("Plugins: added docker to ~/.zshrc.",)` |
| second `set_omz_plugins` assert | `assert run_post_install(tool, _mutable(), None).lines == ("Plugins: git and docker are on.",)` | `assert run_post_install(tool, _mutable()).lines == ("Plugins: git and docker are on.",)` |
| third `set_omz_plugins` assert | `assert run_post_install(tool, _mutable(), None).lines == ()` | `assert run_post_install(tool, _mutable()).lines == ()` |

## Deviations from Plan

None - plan executed exactly as written. Three renames (above) were within the plan's executor rule. `ruff format` collapsed two now-short multi-line expressions; no suppression was added anywhere (`git diff` adds no noqa, type: ignore, pyright: ignore or nosec).

## Acceptance results

- `rg 'ConfirmSensitiveAction|SensitivePrompt|SENSITIVE_|sensitive_prompt|confirm_sensitive|SensitiveActionScreen|_ask_sensitive_action|_DISMISSAL_SENSITIVE' installer setup.py` prints nothing.
- `default_enabled_sensitive_actions` in installer/model.py: 2 lines (the retired-key check and its message).
- `ChecksumMismatchScreen` occurrences in installer/execute_screen.py: 5; class definition 1; the one `ask_from_worker(self.app, ChecksumMismatchScreen(tool_id))` call site 1.
- tests/ has no `ConfirmSensitiveAction`, `SensitivePrompt`, `SENSITIVE_PROMPTS`, `sensitive_prompt` or `confirm_sensitive` reference.
- `.claude/architecture.md`: no `sensitive-action` or `SENSITIVE_POST_INSTALL_ACTIONS`; `_with_force` named once.
- tests/test_reachability.py needed no row change (it named none of the deleted tables).

## Known Stubs

None.

## Threat Flags

None. T-25-07 is mitigated by the explicit loader error and its test; T-25-08 by keeping the checksum prompt plumbing and running its tests and the pilot safety net in Task 1.

## Self-Check: PASSED

All three commits (f5a8dada, e007918d, 38ce08e6) are ancestors of HEAD; the 17 modified files exist; `make validate && make test` exit 0 on the final tree.
