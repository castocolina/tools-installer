---
phase: 23-configuration-as-a-lifecycle-step
plan: "12"
subsystem: installer
tags: [run-options, tui, execute-screen, shell-init, sensitive-prompt, tdd]
status: complete
requirements-completed: [CONF-04, CONF-05, CONF-08, CONF-09, CONF-12]

# Actuals (#2632): chars/4 over the realized code diff (git diff 9440a74..HEAD, installer/execute_screen.py + tests/test_execute_screen.py)
actuals:
  tokens: 21000
  tasks: 2
  commits: 2

# Measured commit ledger (#3968): rev-list count from the plan base 9440a741, taken before this SUMMARY commit.
commits: 2
plan_head_before: 9440a741d4d4636c736d55668bc214a5b91ab710
plan_head_after: 9c2b58e
---

# Phase 23 Plan 12: TUI run options and keyed shell-init prompt — Summary

**The install review lists the run options a plan triggers (off by default, toggled with `space`, frozen at `enter`), the sensitive modal asks the question of its own action, and an unattended TUI run turns nothing on and says so.**

## Performance

- **Tasks:** 2 of 2, each test-first with one green commit.
- **Commits:** `e98670f` (Task 1), `9c2b58e` (Task 2). Base `9440a741`.
- **Test counts (collected, `pytest --collect-only` summed per file):**
  - Before: 5731 (`tests/test_execute_screen.py`: 135).
  - After Task 1: 5736 (5732 passed, 4 skipped; execute-screen file 140).
  - After Task 2: 5746 (5742 passed, 4 skipped; execute-screen file 150).
  - Plan delta: +5 (Task 1), +10 collected (Task 2: six parametrized shell-init cases and four more).
- **Gates:** `make validate` exit 0 and `make test` exit 0 on the tree of each commit. Coverage 96.17%.

## Accomplishments

- `installer/execute_screen.py`:
  - Review rows: after the plan rows, when `run_options` shows any option, a disabled bold heading and one `[ ]`/`[x]` row per shown option (ids `run-opt-<name>`). Notes come from `run_option_lines` with `review_problems` (O7), dim and indented 4 cells, folded with `fold_reason`.
  - `space` (`action_toggle_option`) toggles the highlighted option and clears the status. On a plan row or the heading it warns `space toggles run options only; plan rows change with r.`. After `enter` (waiting, running or finished) it warns `A run option is set before start; it cannot change now.` and changes nothing.
  - `_begin_run` freezes `self._run_options` at `enter`. The worker passes it as `RunContext.options`, and the finished report gets `render_run_report(..., options=...)`.
  - The idle keys line gains `space option` only when option rows exist.
  - `SensitiveActionScreen(tool_id, action="set_login_shell")` takes its prompt and choices from `sensitive_prompt(tool_id, action)`, with `markup=False` on the prompt. `_ask_sensitive_action(tool_id, action)` passes the action through. The login-shell sentence literal is deleted from this module.
  - Unattended runs: `RUN_OPTIONS_LEFT_OFF` is written before the run when options are shown; `shell_init_left_off_line(outcomes, SHELL_INIT_TOOLS)` is written after the run when it is not None.
  - Finished and resized reviews repaint the option rows dim with their final cell.
- `tests/test_execute_screen.py`: 15 new tests (listed below).
- No change to `installer/render.py`, `installer/session.py`, `installer/post_install.py` or `installer/tweaks.py`; those were 23-09 and 23-10 work and are consumed as they are.

## Task Commits

1. **Task 1: run options in the install review** — `e98670f` (`feat(23-12): run options in the install review`; tests and code in one commit).
2. **Task 2: keyed sensitive prompts and unattended run-option lines** — `9c2b58e` (`feat(23-12): keyed sensitive prompts and unattended run-option lines`; tests and code in one commit).

## Test-first evidence

### Task 1

RED, the plan's command, before any implementation (4 failing, 1 passing; the RED output is not committed):

```
FAILED tests/test_execute_screen.py::test_an_auto_approve_option_toggles_and_reaches_the_run
FAILED tests/test_execute_screen.py::test_space_on_a_plan_row_warns_and_changes_nothing
FAILED tests/test_execute_screen.py::test_space_after_enter_is_refused
FAILED tests/test_execute_screen.py::test_the_review_shows_an_unparsable_file_note
exit=1
E   textual.widgets._option_list.OptionDoesNotExist: There is no option with an ID of 'run-opt-auto-approve'
E   IndexError: list index out of range
E   AssertionError: assert '' == 'space toggles run options only; plan rows change with r.'
```

`test_a_skip_only_plan_shows_no_run_options` passed on the RED tree. It is a regression guard, not RED: the plan has no option rows, so the keys line and the review are already correct, and the test pins that.

GREEN, the same selection: `5 passed`, exit 0. Note: Textual's `OptionList` binds no `space`, so the screen binding works without `priority=True` (the R1-53 question is settled by the pilot test).

GREEN, full gate on `e98670f`: `make validate` exit 0; `make test` exit 0, `5732 passed, 4 skipped`.

### Task 2

RED, 10 selected tests, 9 failed and 1 passed (the 80x20 fit test). The failures are the keyed constructor (`TypeError: SensitiveActionScreen.__init__() takes 2 positional arguments but 3 were given`), the missing unattended lines (`assert 'Run options left off (--yes never turns them on); change them in Policies.' in 'Summary — 2 installed …'`), and the markup test. `test_option_rows_fit_80x20` passed on the Task 1 tree: it is a regression guard for the fit rules.

GREEN, the same selection: `10 passed`, exit 0.

GREEN, full gate on `9c2b58e`: `make validate` exit 0 (after one E501 wrap and one pyright strict fix, which replaced an untyped lambda with a typed function, and one `ruff format` pass on the test file); `make test` exit 0, `5742 passed, 4 skipped`.

## Tests added

Task 1: `test_an_auto_approve_option_toggles_and_reaches_the_run` (the `RunContext.options` handed to `execute_plan`, captured through the existing `execute_plan` seam), `test_space_on_a_plan_row_warns_and_changes_nothing`, `test_space_after_enter_is_refused`, `test_a_skip_only_plan_shows_no_run_options`, `test_the_review_shows_an_unparsable_file_note`.

Task 2: `test_each_shell_init_prompt_shows_its_effect` (parametrized over the six shell-init tools, at `size=(80, 20)` with `NO_COLOR=1`), `test_the_login_shell_prompt_is_unchanged`, `test_unattended_runs_leave_every_option_off`, `test_option_rows_fit_80x20`, `test_markup_in_review_values_renders_literally`.

Existing tests changed: none. No assertion was changed, weakened or deleted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, lint] E501 in the 80x20 fit test**
- **Found during:** Task 2 `make validate`
- **Fix:** the tool-name tuple moved to a named variable (`names`), no behaviour change.
- **Committed in:** `9c2b58e`

**2. [Rule 3 - Blocking, pyright strict] untyped lambda in the markup test**
- **Found during:** Task 2 `make validate`
- **Fix:** replaced the lambda that fakes `review_problems` with a typed nested function (`fake_problems`).
- **Committed in:** `9c2b58e`

**3. [Formatting] `ruff format` on `tests/test_execute_screen.py`**
- **Found during:** Task 2 `make validate`. A formatting-only pass; no test or code changed beyond layout.
- **Committed in:** `9c2b58e`

### Plan-text interpretation (behaviour as specified)

**4. `RunContext.options` is snapshotted in `_begin_run`, not in the worker**
- The plan wrote `options=frozenset(self._options & shown)` inside the run. The snapshot is taken on the main thread at `enter` and read by both the worker and the finished report, so the report and the run always agree and the worker never reads the screen's mutable state. Same set, earlier point.

**5. The `space` refusal guard mirrors `action_toggle_reinstall`**
- Refused when `started`, `finished` or `_start_requested` (the state-check wait after `enter`). A pre-`enter` publication wait (`_waiting` without `enter`) still lets `space` toggle, because the answers are not frozen until `enter`. UI-SPEC's "waiting" is read as the wait after `enter`.

**6. Unattended shell-init line gated on `unattended`**
- `shell_init_left_off_line` alone would also fire after an attended run where the user answered no, which would say "left off (--yes)" wrongly. It is written only when `self._inputs.unattended` is set.

**7. Finished and resized reviews refold the option rows**
- The plan asks for dim option rows at finish. The resize path while finished refolds the outcome rows, so the option rows are refolded there too; otherwise they would keep the old fold width.

### Process notes

- **Plan head ledger (#3968) not written before the first commit.** Protocol 0c asks for the ledger file before the first task commit. It was not written before `e98670f`. `plan_head_before` above is the orchestrator's base (`9440a741`, the merge base with `main`), and `commits: 2` is `git rev-list --count 9440a741..HEAD` measured before this SUMMARY commit.
- **Cwd-drift sentinel (#3097) not written.** Worktree commits were all made from the worktree root; the sentinel was not created before the first commit.
- **Harness refused compound git commands** (for example, a `git grep` inside a `$(...)` pipeline and a `cd && git ...` chain). Each was split into a plain command run from the worktree.
- **Test-session guard** did not trip on either `make test` run.
- **No attribution trailers** on any commit, per the orchestrator's rule (AGENTS.md's Co-Authored-By trailer is not used).
- **Suppression gate:** `grep -cE "type: ignore|pyright: ignore|noqa|nosec"` over `installer`, `tests` and `setup.py` is 446 at `9440a741` and 446 now. No suppression was added.
- **Nothing ran on the host.** Tests use the scratch HOME from `tests/conftest.py`. No `make setup`, `make fix` or `make uninstall`. No real rc, settings, shell or environment.d file touched. No sudo.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. Each threat has a test:

- T-23-33 (an option turned on by `--yes`, `a`, a remembered answer or a default): `test_unattended_runs_leave_every_option_off`; `test_an_auto_approve_option_toggles_and_reaches_the_run` (off on every review, never stored).
- T-23-34 (an option changed after the run started): `test_space_after_enter_is_refused` (the answers handed to `execute_plan` stay `frozenset({"auto-approve"})` after the refused `space`).
- T-23-35 (markup in ids, file names or errors): `test_markup_in_review_values_renders_literally`.
- T-23-SC: no package added.

## Not checked

- **Real-terminal NO_COLOR look.** The 80x20 tests are text-level backstops; the real-terminal check stays a human check (23-VALIDATION).
- **Desktop-shell row in the TUI.** No test shows the `desktop-shell` option in the review (the macOS fixture hides it). `run_options` covers the trigger and 23-10's tests cover the write.
- **Headless route.** 23-13 (same wave) owns the headless prompt and the `app.py` login-shell copy, which still exists there.
- **UI-SPEC copy for volta.** The volta shell-init description is the one 23-09 kept verbatim; the UI-SPEC amendment wording is an open copy point for the orchestrator (recorded in 23-09's SUMMARY), not changed here.

## Self-Check: PASSED

- [x] `e98670f` and `9c2b58e` exist on `worktree-agent-a7604517e4e091e77` after base `9440a741`.
- [x] `make validate` exit 0 and `make test` exit 0 on each commit's tree.
- [x] `rg "Show a reviewed command to change the login shell" installer/` matches the one copy in `installer/post_install.py` and the `installer/app.py` copy that 23-13 removes. `installer/execute_screen.py` no longer carries the literal.
- [x] No change to `.planning/STATE.md` or `.planning/ROADMAP.md`.
