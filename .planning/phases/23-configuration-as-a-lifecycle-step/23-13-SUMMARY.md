---
phase: 23-configuration-as-a-lifecycle-step
plan: "13"
subsystem: installer
tags: [run-options, headless, prompter, shell-init, cli, tdd]
status: complete

requires:
  - phase: 23-08
    provides: unregister on removal (no direct dependency in this plan; wave 4 base)
  - phase: 23-09
    provides: SENSITIVE_PROMPTS, sensitive_prompt (per-action default), SHELL_INIT_TOOLS bundles
  - phase: 23-10
    provides: RUN_OPTIONS, run_options, review_problems, RunContext.options, run_option_lines, RUN_OPTIONS_LEFT_OFF, shell_init_left_off_line, render_run_report(options=)
provides:
  - Prompter.confirm(message, *, default=True) end to end (prompter, CallbackPrompter, setup.ask_confirm -> questionary)
  - headless attended route asks one default-no question per shown run option, in table order, after "Run this plan?"
  - headless shell-init question through sensitive_prompt (source_shell_init defaults to no; set_login_shell keeps yes)
  - --yes asks nothing and prints the run-options and shell-init left-off lines
affects: [23-12 (TUI front end of the same options; execute_screen login-shell literal removed there), 23-16 (run evidence)]

# Actuals (#2632): chars/4 over the realized diff (git diff 9440a74 HEAD, 21026 chars)
actuals:
  tokens: 5256
  tasks: 2
  commits: 2

# Measured commit ledger (#3968): rev-list count from the plan base, before this SUMMARY commit
commits: 2
plan_head_before: 9440a741d4d4636c736d55668bc214a5b91ab710
plan_head_after: 6864d0d06a6066d53fc8a1fc353a7aa0343612df

tech-stack:
  added: []
  patterns:
    - "A run option is asked only when the plan shows it, and every question defaults to no (T-23-47)"
    - "--yes never turns an option on and says so; the left-off lines are the one copy each (render.py)"
    - "Sensitive questions read their text and default from SENSITIVE_PROMPTS; the callers pass only the tool and action"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-13-SUMMARY.md
  modified:
    - installer/app.py
    - installer/prompt.py
    - setup.py
    - tests/test_app.py
    - tests/test_cli.py
    - tests/test_prompt.py
    - tests/test_setup.py
    - tests/test_version_status.py

key-decisions:
  - "Prompter.confirm takes a keyword default (default=True keeps every existing caller); AskConfirm is Callable[[str, bool], bool]"
  - "setup._ask_confirm is public as setup.ask_confirm (see Deviations 1): the test calls it without a new pyright suppression"
  - "Headless run options are asked after Run this plan? is answered yes and before the held bookkeeping writes commit; a declined plan asks nothing"
  - "confirm_sensitive passes the table's per-action default: source_shell_init asks default no, set_login_shell keeps today's default yes (R1-54)"
  - "--yes: RUN_OPTIONS_LEFT_OFF prints after the commit writes, right before the run, when the plan shows options; shell_init_left_off_line prints after the report"
  - "The parse_args guard reads the accepted flags from --help: Phase 23 adds no flag (O1, A33)"

patterns-established:
  - "RED evidence in the SUMMARY only: each task's failing run was pasted, then the tests and code were committed together as one green feat(23-13) commit"

requirements-completed: []  # headless front end of CONF-04, CONF-05, CONF-08, CONF-09, CONF-12; the TUI review (23-12) is the other front and closes them with this

# Metrics
duration: unmeasured (no start timestamp recorded for this run)
completed: 2026-11-07
---

# Phase 23 Plan 13: Headless run options and shell-init questions Summary

**The headless route asks the same run-option and shell-init questions as the TUI, one default-no question each, while `--yes` turns nothing on and says so; `Prompter.confirm` carries the default from the caller to questionary.**

## Performance

- **Duration:** unmeasured (no start timestamp recorded for this run)
- **Tasks:** 2 of 2, each test-first, one green commit each
- **Commits:** 2, measured against base `9440a74` (`git rev-list --count 9440a74..HEAD` = 2): `24c3258`, `6864d0d`
- **Test counts (collected; `make test` passed / skipped):**
  - Start (per-file sum of `pytest --collect-only`, measured before any change): 5731 collected; `make test` 5727 passed, 4 skipped.
  - After Task 1: 5733 collected; 5729 passed, 4 skipped (+2 tests).
  - After Task 2: 5737 collected; 5733 passed, 4 skipped (+4 tests).
  - Plan delta: 6 new tests, all present (2 in Task 1, 4 in Task 2). No test was removed.
- **Gates:** `make validate` exit 0 and `make test` exit 0 on each commit's tree (see Test-first evidence for the one load-related retry in Task 1).

## Accomplishments

- `installer/prompt.py`: `Prompter.confirm(message, *, default=True)`; `CallbackPrompter.confirm` forwards the default; `AskConfirm = Callable[[str, bool], bool]`.
- `setup.py`: `ask_confirm(message, default=True)` (renamed from `_ask_confirm`) passes the default to `questionary.confirm`; the six existing callers are unchanged apart from the name.
- `installer/app.py`:
  - `_ask_run_options(rows, prompter, console, refresh)`: for each option in `run_options(rows, os)`, prints the notes from `run_option_lines` (sanitized, markup off, soft wrap), then asks `"{first}?"` with `default=False`; the yes answers become `RunContext(options=...)` and `render_run_report(..., options=...)`.
  - `confirm_sensitive(tool_id, action)` asks `sensitive_prompt(tool_id, action).prompt` with the table's `default`. The hard-coded login-shell sentence is deleted (23-REUSE 09-3, app.py side).
  - `--yes`: no question; `RUN_OPTIONS_LEFT_OFF` before the run when the plan shows options; `shell_init_left_off_line(outcomes, SHELL_INIT_TOOLS)` after the report when it is not None.
- No new CLI flag: `parse_args` is unchanged (regression guard passes).

## Task Commits

1. **Task 1: headless questions can default to no** - `24c3258` (feat; tests and code in one commit)
2. **Task 2: headless run options and shell-init questions default to no** - `6864d0d` (feat; tests and code in one commit)

## Test-first evidence

### Task 1 RED

Command: `uv run pytest tests/test_prompt.py tests/test_setup.py -k "forwards_the_default or passes_the_default_to_questionary" -q --no-cov -n 0` (run against the `_ask_confirm` name, before the rename in Deviation 1). Both new tests failed:

```
FAILED tests/test_prompt.py::test_callback_prompter_forwards_the_default
E       TypeError: CallbackPrompter.confirm() got an unexpected keyword argument 'default'
FAILED tests/test_setup.py::test_ask_confirm_passes_the_default_to_questionary
E       TypeError: _ask_confirm() takes 1 positional argument but 2 were given
2 failed
```

Not committed alone; the RED output stays here.

### Task 1 GREEN

- Focused command, same selection: exit 0.
- Affected files (`tests/test_prompt.py tests/test_setup.py tests/test_app.py tests/test_version_status.py -n auto`): exit 0.
- `make validate`: exit 0 (after the rename, which cleared a pyright `reportPrivateUsage` error in the new test).
- `make test`, first run: exit 2, `1 failed, 5728 passed, 4 skipped`. The failure is `tests/test_screen_family.py::test_a_failed_invalidate_after_a_reinstall_is_reported[mapped]` (a Textual polling test, `condition never became true within the polling budget`). It is not in this plan's code. Re-running that single test alone: exit 0. Re-running the full suite: exit 0, `5729 passed, 4 skipped`. Treated as a load-sensitive flake from three executors running `make test` on this host (the baseline on the base tree passed with the same test). It was not changed.

### Task 2 RED

Command: `uv run pytest tests/test_app.py tests/test_cli.py -k "option_questions_default_to_no or yes_asks_nothing_and_says_so or shell_init_question_is_keyed or parse_args_is_unchanged" -q --no-cov -n 0`. Exit 1, 3 failed:

```
FAILED tests/test_app.py::test_headless_option_questions_default_to_no
E       AssertionError: assert [('Run this plan?', True)] == [('Run this p...PRs?', False)]
E         Right contains 2 more items, first extra item: ('auto-approve agents — claude, codex: no permission prompts?', False)
FAILED tests/test_app.py::test_headless_yes_asks_nothing_and_says_so
E       ValueError: substring not found          (no "Run options left off" line yet)
FAILED tests/test_app.py::test_the_headless_shell_init_question_is_keyed_and_default_no
E       AssertionError: Extra items in the left set:
E         ('Show a reviewed command to change the login shell to zsh for zoxide, which you run ...', True)
E       Extra items in the right set:
E         ('Turn on zoxide shell init? It adds one guarded block to ~/.myshellrc that adds z, ...', False)
```

`test_parse_args_is_unchanged` (tests/test_cli.py) was run on the base tree before any code change and **passed** (exit 0). It is a regression guard, not RED: the flag set it asserts is what `parse_args` already accepts.

### Task 2 GREEN

- Focused command, same selection (4 tests, including the guard): exit 0.
- `make validate`: exit 0 (after an E501 fix in one test docstring, `ruff format` of `installer/app.py`, and an explicit `chosen: frozenset[str]` annotation for pyright).
- `make test`: exit 0, `5733 passed, 4 skipped`.

## Acceptance checks (measured on the final tree)

- `grep -c "default: bool = True" installer/prompt.py` = 2 (plan: at least 1)
- `grep -c "default=False" installer/app.py` = 1 (plan: at least 1)
- `grep -c "default=prompt.default" installer/app.py` = 1
- `grep -c "change the login shell to zsh" installer/app.py` = 0
- `grep -rc "Show a reviewed command to change the login shell" installer/` matches `installer/post_install.py` (the table) and `installer/execute_screen.py` (the TUI literal; 23-12 deletes it, as the plan notes)
- Suppression gate: `git diff` adds no `type: ignore`, `pyright: ignore`, `noqa` or `nosec` line (checked on both commits' diffs)
- Collected tests: 5737 (base 5731 + 6 new)

## Changed existing tests (each, with its reason)

- `tests/test_prompt.py`: `test_callback_prompter_is_a_prompter` lambda and the `ask_confirm` callback in `test_confirm_forwards_message` take `(message, default)`. **Reason:** `AskConfirm` is now `Callable[[str, bool], bool]` (review R1-55; the plan named lines 5 and 16, and the callback definition at line 12 needed the same change).
- `tests/test_app.py`: `FakePrompter.confirm` and `MustNotConfirm.confirm` gain `*, default: bool = True`. **Reason:** the `Prompter` protocol gained the keyword.
- `tests/test_version_status.py`: the four fake prompters (`confirm` methods) gain the same keyword. **Reason:** the same protocol change.

No assertion was changed or weakened, and no test was deleted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, lint gate] `_ask_confirm` renamed to public `ask_confirm` in setup.py**
- **Found during:** Task 1 `make validate`
- **Issue:** the plan's test calls `setup._ask_confirm`; pyright strict reports `reportPrivateUsage` on that call. The repo's usual fix is a module-level alias with a `pyright: ignore` comment, which the orchestrator forbids as a new suppression.
- **Fix:** renamed the helper to `ask_confirm` in `setup.py` (the definition, its six call sites and the comment that names it). No other code or test in the repo referenced the name. The test calls `setup.ask_confirm`; its assertions are unchanged. The RED run used the old name, before this rename.
- **Files modified:** `setup.py`, `tests/test_setup.py` (both in files_modified)
- **Committed in:** `24c3258`

**2. [Plan text] The `parse_args` guard reads the flags from `--help`**
- **Found during:** Task 2 RED design
- **Issue:** the plan says "read from its parser's actions". Reading them needs a private argparse attribute, which the same pyright rule rejects.
- **Fix:** the test runs `parse_args(["--help"])`, captures stdout and extracts the `--flag` names. The literal set is the flags `parse_args` accepts today, and the test passes on the base tree.
- **Committed in:** `6864d0d`

### Judgement calls (not deviations from the plan's behaviour)

- The option loop lives in `_ask_run_options` rather than inline in `run_wizard` (the same behaviour; keeps `run_wizard` readable). Its result is annotated `frozenset[str]` for pyright.
- Order: option questions come after `Run this plan?` and before the held bookkeeping writes commit. `RUN_OPTIONS_LEFT_OFF` prints after the commit writes, right before the run. The shell-init left-off line prints after the report, because UI-SPEC section 7 says "after the run".
- Option notes go through `sanitize_log_line`, matching the report lines (the note text can include a settings file name).

## Issues Encountered

- **Load-sensitive Textual test (Task 1, first full run):** `tests/test_screen_family.py::test_a_failed_invalidate_after_a_reinstall_is_reported[mapped]` failed once under parallel load and passed on its own and on the full re-run (see Test-first evidence). Not changed; it is outside this plan's code.
- **Bash path guard:** the guard refused two compound commands that named git (a heredoc append to `tests/test_cli.py` and a `$(...)` count). Each was redone as a plain command or with the Edit tool. No command ran outside the worktree.
- **Host safety:** `make install` created the worktree `.venv` and `codegraph init -i` created `.codegraph/` (both gitignored). No `make setup`, `make fix`, `make uninstall`, sudo, or real settings/rc write. Every test uses the scratch HOME from `tests/conftest.py`.
- **Worktree metadata:** `gsd-spawn-toplevel` (cwd-drift sentinel) and `gsd-plan-head-before-23-13` (commit ledger) were written under the worktree's git dir, not in the tracked tree.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. Each threat has a test:

- T-23-47 (a headless question answered yes by pressing enter): `test_headless_option_questions_default_to_no` (every option question is `default=False`) and `test_the_headless_shell_init_question_is_keyed_and_default_no` (`source_shell_init` is default no)
- T-23-48 (`--yes` turning an option on): `test_headless_yes_asks_nothing_and_says_so` (no question, options empty, the left-off line)
- T-23-SC: no package added

## Not checked

- No live run on a real host. Every test uses the scratch HOME, fake installs and scripted prompters; no `make setup`, `make fix` or `make uninstall` was run.
- The TUI route (23-12) and its `execute_screen.py` login-shell literal are untouched by this plan, as planned.
- The "Shell init left off" line is verified in the `--yes` test with a fake install. The real post-install step is not run here.

## Self-Check

- [x] `installer/prompt.py`, `setup.py`, `installer/app.py` and the test files are committed in `24c3258` and `6864d0d` (`git show --stat` lists them)
- [x] Each commit's tree passed `make validate` (exit 0) and `make test` (exit 0: 5729 and 5733 passed, 4 skipped; the Task 1 first run had the flake recorded above)
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`
- [x] The worktree branch was checked before the first commit: `worktree-agent-a16ca4fe3bbbde9b3`, base `9440a741d4d4636c736d55668bc214a5b91ab710`

## Self-Check: PASSED
