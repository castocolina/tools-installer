---
phase: 23-configuration-as-a-lifecycle-step
plan: "10"
subsystem: installer
tags: [run-options, agent-settings, environment.d, desktop-shell, which-with-brew, report, tdd]
status: complete

requires:
  - phase: 23-04
    provides: shell_redirect, write_linux_redirect (absolute value, no mkdir), environment_d_dir
  - phase: 23-06
    provides: agent_settings.apply_setting, FileResult, KeyResult, setting_keys, settings_file, file_problem, CONFIG_AGENTS
  - phase: 23-07
    provides: RUNNABLE, RowOutcome.resynced, _resync_hooks, the render_run_report section order
provides:
  - RUN_OPTIONS, AGENT_OPTION_IDS, ATTRIBUTION_IDS, NO_ATTRIBUTION_KEY_IDS (derived where possible), OPTION_COVERS
  - run_options(rows, platform_os) and review_problems(rows, home, platform_os) in installer/session.py
  - RunContext.options (default empty) and the post-row engine step _apply_run_options (agent, VS Code and desktop SHELL)
  - RowOutcome.settings, settings_skipped, desktop_shell, desktop_shell_error
  - postinstall.which_with_brew (moved from setup.py, one copy; _resolve_binary calls it)
  - render.run_option_lines, render_settings_lines, render_run_report(..., options=), RUN_OPTIONS_LEFT_OFF, shell_init_left_off_line
affects: [23-11 (Policies rows reuse which_with_brew), 23-12 (TUI review reads run_options, run_option_lines, review_problems), 23-13 (headless reads RUN_OPTIONS_LEFT_OFF, shell_init_left_off_line), 23-14 (desktop row), 23-15 (removal reverts)]

# Actuals (#2632): chars/4 over the realized diff (git diff 58fe434 HEAD, 46833 chars)
actuals:
  tokens: 11708
  tasks: 3
  commits: 3

# Measured commit ledger (#3968): rev-list count from the plan base, taken before this SUMMARY commit
commits: 3
plan_head_before: 58fe43485d5a573da08956a70eac6b75a66d4c57
plan_head_after: 8bb2add477f85f3edb81f767e2d9bb2c35cc7e77

tech-stack:
  added: []
  patterns:
    - "Run options are engine inputs: RunContext.options defaults empty, so a run writes no setting unless an option is chosen"
    - "Option coverage is one table (OPTION_COVERS); run_options, the engine and the review texts all read it"
    - "The desktop SHELL conf resolves zsh through the one which_with_brew lookup, the same one the terminal sync uses"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-10-SUMMARY.md
  modified:
    - installer/session.py
    - installer/render.py
    - installer/postinstall.py
    - installer/agent_settings.py
    - setup.py
    - tests/test_session.py
    - tests/test_render.py
    - tests/test_postinstall.py
    - tests/test_setup.py

key-decisions:
  - "AGENT_OPTION_IDS and ATTRIBUTION_IDS are derived from CONFIG_AGENTS x setting_keys (auto-approve: claude, codex, opencode, cursor-agent; no-attribution: claude, cursor-agent); the derivation uses a non-macOS platform_os because the agent sets do not depend on the OS"
  - "OPTION_COVERS is public: render.py reads it for the review texts and the O7 notes, so one table decides which rows an option covers"
  - "The engine applies options only to runnable rows that ended done; a runnable row that did not end done is marked settings_skipped and named in the report"
  - "The desktop SHELL option writes only when platform is not macOS and a zsh, kitty or wezterm row ended done; the first such row carries the result"
  - "The desktop error carries the display path too, so its heading prints without a second path computation"
  - "The replaced CLI default is reported as the value it replaced (true), not the value we wrote (false), the same convention the removed kind already uses"
  - "No option text is built by hand in the TUI or headless code: run_option_lines and RUN_OPTIONS_LEFT_OFF are the one copy each (23-12 and 23-13 read them)"

patterns-established:
  - "RED evidence in the SUMMARY only: each task's failing run was pasted, then the tests and code were committed together as one green feat(23-10) commit"

requirements-completed: []  # engine and report side of CONF-05, CONF-08, CONF-09, CONF-12; the review rows (23-12) and headless prompts (23-13) close them

# Metrics
duration: unmeasured (no start timestamp recorded for this run; worktree base 58fe434)
completed: 2026-11-07
---

# Phase 23 Plan 10: Run options Summary

**Run options are run-level, default-off engine inputs: each chosen option writes its settings to every agent or editor row that ended done, the plan decides which options exist, and the report says what was written, left, refused or skipped, with the desktop SHELL option writing its environment.d conf through the brew-aware zsh lookup.**

## Performance

- **Duration:** unmeasured (no start timestamp recorded for this run)
- **Tasks:** 3 of 3, each test-first, one green commit each
- **Commits:** 3, measured against base `58fe434` (`4b0b02a`, `816f114`, `8bb2add`)
- **Test counts (collected):** start 5680 (per-file sum of `pytest --collect-only`, measured before any change) → after Task 1 5683 (5679 passed, 4 skipped) → after Task 2 5687 (5683 passed, 4 skipped) → after Task 3 5692 (5688 passed, 4 skipped). Delta +12 = +3 (Task 1) +4 (Task 2) +5 (Task 3: +7 new, -2 moved to test_postinstall.py).
- **make validate / make test:** exit 0 on each commit's tree (validate: pyright 0 errors; test: 96.17 to 96.20 percent coverage).

## Accomplishments

- `installer/session.py`:
  - The option table `RUN_OPTIONS` and the derived id sets; `OPTION_COVERS` maps each option to its setting group and covered row ids.
  - `run_options(rows, platform_os)` shows an option only when a runnable row triggers it, in table order.
  - `review_problems` names each runnable agent whose settings file does not parse (the O7 input of the review texts).
  - `RunContext.options` (default empty) and `_apply_run_options`, called after `_resync_hooks`: agent and VS Code options write through `apply_setting` per covered done row; a row that did not end done is `settings_skipped`.
  - `_desktop_shell`: writes the environment.d conf through `write_linux_redirect(shell_redirect(zsh))`, with `zsh = postinstall.which_with_brew("zsh")`; no zsh, a `ValueError` or an `OSError` becomes `desktop_shell_error`.
- `installer/postinstall.py`: `which_with_brew(name)` moved from `setup._which_with_brew` (body and CR-04 docstring); `_resolve_binary`'s brew branch calls it; one copy.
- `setup.py`: the copy is deleted; the two terminal-sync `lookup=` sites and the docstring reference use `which_with_brew`.
- `installer/render.py`:
  - `run_option_lines` returns each option's first line and dim notes, verbatim from UI-SPEC section 1 (pi note, no-key note, Cursor caveat, VS Code `update.mode` note per OS, O7 notes in that order).
  - `render_settings_lines` prints the `Agent and editor settings` section: one block per file (`wrote`, `set by you` cut to 78 cells, `already set`, `replaced CLI default` with one `revert restores the replaced defaults` per file, the parse and changed-while-writing refusals), then the file-less lines (cursor caveat, no-key line, pi line, `not installed by this run`, environment.d block or error).
  - `render_run_report(..., options=...)` prints that section after the hooks section.
  - `RUN_OPTIONS_LEFT_OFF` and `shell_init_left_off_line` are the unattended texts 23-12 and 23-13 read.
- `installer/agent_settings.py` (one line, see Deviations): a `replaced_default` key carries the CLI default it replaced.

## Task Commits

1. **Task 1: run options apply agent settings to every installed agent row** - `4b0b02a` (feat; tests and code in one commit)
2. **Task 2: the plan decides which run options exist and how they read** - `816f114` (feat)
3. **Task 3: settings report lines and the desktop SHELL option** - `8bb2add` (feat)

## Test-first evidence

### Task 1 RED

`uv run pytest tests/test_session.py tests/test_render.py -k "applied_to_every_agent_row or default_run_writes_no_setting or failed_agent_row_writes_nothing" -q --no-cov -n 0` → exit 1, 3 failed:

```
FAILED tests/test_session.py::test_auto_approve_is_applied_to_every_agent_row_that_ended_done
    TypeError: RunContext.__init__() got an unexpected keyword argument 'options'
FAILED tests/test_session.py::test_a_default_run_writes_no_setting
    AttributeError: 'RowOutcome' object has no attribute 'settings'
FAILED tests/test_session.py::test_a_failed_agent_row_writes_nothing_and_says_so
    TypeError: RunContext.__init__() got an unexpected keyword argument 'options'
3 failed
```

The new tests build their context with `dataclasses.replace(ctx, options=...)`, so the rest of the file stayed green while RED. GREEN: the same selection → 3 passed.

### Task 2 RED

`uv run pytest tests/test_session.py tests/test_render.py -k "run_options_follow_the_plan or run_option_lines_match or unparsable_target_file_adds or review_problems_name" -q --no-cov -n 0` → exit 2, collection failed on the missing names (missing-API RED, the same shape as 23-07 Task 2):

```
ERROR tests/test_render.py
E   ImportError: cannot import name 'run_option_lines' from 'installer.render'
ERROR tests/test_session.py   (cannot import run_options / review_problems from installer.session)
Interrupted: 2 errors during collection
```

GREEN: the same selection → 4 passed.

### Task 3 RED

`uv run pytest tests/test_session.py tests/test_postinstall.py -k "desktop_shell_option_writes or which_with_brew_finds_a_linuxbrew or which_with_brew_prefers" -q --no-cov -n 0` → 3 failed:

```
FAILED tests/test_session.py::test_desktop_shell_option_writes_environment_d
    AttributeError: module 'installer.postinstall' has no attribute 'which_with_brew'
FAILED tests/test_postinstall.py::test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see
    AttributeError: module 'installer.postinstall' has no attribute 'which_with_brew'
FAILED tests/test_postinstall.py::test_which_with_brew_prefers_a_real_shutil_which_hit
    AttributeError: module 'installer.postinstall' has no attribute 'which_with_brew'
```

The test_render tests for Task 3 could not be collected in RED: `ImportError: cannot import name 'RUN_OPTIONS_LEFT_OFF' from 'installer.render'` (and `shell_init_left_off_line`, and `render_settings_lines` with its new signature), so the five render tests were first run in GREEN. GREEN: the seven targeted tests → 7 passed; the plan's related file set (session, render, execute_screen, app, setup, postinstall, terminal_shell, agent_settings) with `-n auto` → all passed.

## Acceptance checks (measured on the final tree)

- `grep -c "def _apply_run_options(" installer/session.py` = 1; `grep -c "Agent and editor settings" installer/render.py` = 1
- `grep -c 'AGENT_OPTION_IDS = ("claude"' installer/session.py` = 0 (derived)
- `grep -c "def run_options(" installer/session.py` = 1; `grep -c "def review_problems(" installer/session.py` = 1; `grep -c "def run_option_lines(" installer/render.py` = 1
- `cat setup.py tests/test_setup.py | grep -v "^ *#" | grep -c "_which_with_brew"` = 0 (baseline 12); `grep -c "def which_with_brew(" installer/postinstall.py` = 1
- `grep -c "which: Callable" installer/session.py` = 0; `grep -c "shell_redirect(" installer/session.py` = 1; `grep -c "revert restores the replaced defaults" installer/render.py` = 1
- `grep -v "^ *#" installer/agent_settings.py | grep -c '== "linux"'` = 0
- Suppression gate: 451 `type: ignore|pyright: ignore|noqa|nosec` matches at the base (`git grep` on `58fe434`), 446 now (the five `reportPrivateUsage` comments in test_setup went away with the private name). No new suppression.
- `RunContext` has no `which` and no `harnesses` field.

## Changed existing tests (each, with its reason)

- `tests/test_setup.py`: the two `test_which_with_brew_*` tests are removed and re-added in `tests/test_postinstall.py` under the same names (`..._finds_a_linuxbrew_binary_shutil_which_cannot_see`, `..._prefers_a_real_shutil_which_hit`), now calling `pi.which_with_brew`. **Reason:** plan 10-1 moves the function to postinstall.
- `tests/test_setup.py`: the two `"lookup": setup._which_with_brew` fixtures use `postinstall.which_with_brew`, and the `pyright: ignore[reportPrivateUsage]` comments on them went away with the private name; `postinstall` is imported beside `pnpm_globals`. **Reason:** the same move.
- No assertion was weakened or deleted; no other existing test changed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, outside files_modified] `replaced_default` reported the wrong value**
- **Found during:** Task 3 (report design against UI-SPEC A16)
- **Issue:** `agent_settings._apply_pass` stored `_dump(key.value)` (our value, `false`) on a `replaced_default` KeyResult. UI-SPEC A16 and the plan require `replaced CLI default: attribution.attributeCommitsToAgent = true`, so the report would have named the wrong value.
- **Fix:** one line, `_dump(key.cli_default)`, which is the same convention the revert's `removed` kind already uses. No test pins the value (`tests/test_agent_settings.py` asserts the kind only).
- **Files modified:** `installer/agent_settings.py` (not in this plan's files_modified; recorded here as the plan requires)
- **Committed in:** `8bb2add`

### Plan-text corrections

**2. [Plan text] `RowOutcome.desktop_shell_error` carries the display path too**
- The plan had `str | None`. The error heading `environment.d — {path}:` needs the path, and `desktop_shell` has it only on success. The field is now `(display path, error)`, the same shape as `desktop_shell`.

**3. [Plan text] `render_run_report(options=...)` landed in Task 3, not Task 1**
- Task 1's renderer had no reader for the parameter, and `make validate` runs vulture at 80 percent confidence over `installer/`, so an unused parameter would have failed the gate. The keyword arrives with the lines that read it (cursor caveat, no-key line, pi line).

**4. [Plan text] `run_option_lines(problems=None)`, not `problems={}`**
- A mutable default is B006 under ruff's `B` rules. Same behaviour.

**5. [Plan text] `OPTION_COVERS` is public**
- The plan named it `_OPTION_COVERS`. `render.py` reads it for the review texts, and pyright strict flags a private name used across modules (`reportPrivateUsage`).

**6. [Plan text] No `a != "vscode"` filter in the id derivation**
- `setting_keys` returns no keys for `vscode` under `auto-approve` or `no-attribution`, so the filter the plan named changes nothing. The derivation is `tuple(agent for agent in CONFIG_AGENTS if setting_keys(agent, setting, "linux"))`.

**7. [Plan text] No test reaches `_resolve_binary`'s brew branch**
- `_resolve_binary` is private, and pyright strict flags a test's access to it. The branch is now one delegation to `which_with_brew`, and `which_with_brew` has the two moved tests plus the brew-prefix case. The plan's single assertion through `_resolve_binary` is not in the tests.

**8. [Plan text] Test name**
- The plan's `test_which_with_brew_finds_a_brew_binary_off_path` is covered by the moved `test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see`, which keeps its original name (the same off-PATH case).

### Orchestrator note that did not match the tree (not done)

The executor prompt said 23-10 must wire `unregister_argvs`, `hook_method` and `host_labels` and the `CommandError` first-line rule. 23-08 had already wired all of them (`installer/uninstall.py` calls `hook_method` and `unregister_argvs`; `installer/app.py` has `_command_error_line` for the unregister failure line), and the 23-10 plan has no task for them. Nothing was changed for this; verified with `grep`.

### Process notes (no code impact)

- The project's git-workflow rule asks for a Co-Authored-By trailer; the orchestrator's rule says no attribution trailers. The orchestrator's rule was followed, so no trailer is in any commit.
- `codegraph init -i` created `.codegraph/` in the worktree and `make install` created `.venv/`; both are git-ignored.
- The Bash guard refused compound commands that name git and a heredoc append; each was split into plain commands, and the test edits were made with the Edit tool.
- Lint and pyright fixes before the commits (no check silenced): long docstrings shortened; import order via `ruff check --fix` (names only); two untyped lambdas in the new tests replaced by typed nested functions, as the existing test did. Each commit's tree then passed `make validate` and `make test` before its commit, and the pre-commit hooks passed on each commit.
- The test-session guard did not trip on any `make test` run.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. Each threat has a test:

- T-23-26 (auto-approval by default): `test_a_default_run_writes_no_setting`, `test_a_failed_agent_row_writes_nothing_and_says_so`
- T-23-27 (markup or ANSI in a report value): `sanitize_log_line` on each line; `test_settings_report_lines_cover_every_outcome`
- T-23-28 (environment.d outside the user dir): `environment_d_dir` only, Linux only; `test_desktop_shell_option_writes_environment_d`
- T-23-59 (the run writing another zsh than the terminal sync): one `which_with_brew`; `test_which_with_brew_finds_a_linuxbrew_binary_shutil_which_cannot_see`
- T-23-SC: no package added

## Not checked

- **Callers:** nothing in production sets `RunContext.options` or passes `options=` to `render_run_report` yet. The TUI review (23-12) and the headless route (23-13) wire them, so no run option can be chosen by a user until those land.
- **Live hosts:** no real Claude, Codex, opencode, cursor-agent, VS Code, kitty, WezTerm or zsh was run. Every test uses a scratch HOME and fake installs.
- **Brew-only zsh path:** the test monkeypatches `which_with_brew`; the real `BREW_BIN_DIRS` lookup is covered by its own tests, with `BREW_BIN_DIRS` patched to `tmp_path`.
- **Parallel-run guard:** not exercised (single executor run).

## Self-Check

- [x] `installer/session.py`, `installer/render.py`, `installer/postinstall.py`, `installer/agent_settings.py`, `setup.py` and the four test files are committed in `4b0b02a`, `816f114` and `8bb2add` (`git show --stat` lists them)
- [x] Each commit's tree passed `make validate` (exit 0) and `make test` (exit 0: 5679, 5683 and 5688 passed, 4 skipped)
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`
- [x] The worktree branch was checked before the first commit: `worktree-agent-a6e71de135a0fb0b6`, base `58fe43485d5a573da08956a70eac6b75a66d4c57`

## Self-Check: PASSED
