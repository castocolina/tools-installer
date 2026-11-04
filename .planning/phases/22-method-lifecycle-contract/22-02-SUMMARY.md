---
phase: 22-method-lifecycle-contract
plan: "02"
subsystem: install
tags: [zero-sudo, manual-handoff, native-packages, dnf, apt, pacman, plan-review, tui-copy]
requires:
  - phase: 20
    provides: Disposition, WORDS, RowOutcome and the execute_plan run engine
provides:
  - "Disposition.MANUAL: a native-only install is planned as a manual handoff that runs nothing"
  - "executors.needs_manual(method) -> ManualHandoff: the one shared predicate for plan time and run time"
  - "The native dnf, apt and pacman executors are deleted; an AST test keeps sudo, pkexec and doas out of argv literals"
  - "The finished MANUAL row and the run report print the exact command, copy-safe"
affects: [22-04 (adds the writable_prefix branch and a required writable keyword to needs_manual), 22-05, 22-13 (copy text)]
actuals:
  tokens: 9086      # chars/4 over the realized diff (git diff 6fcaa7f..HEAD: 36343 bytes)
  tasks: 3
  commits: 3       # MEASURED: git rev-list --count 6fcaa7f..HEAD
tech-stack:
  added: []
  patterns:
    - "One predicate (executors.needs_manual) answers at plan time (_row) and at run time (engine ladder)"
    - "Display strings for handed-off commands live in one dict of str templates; nothing in it is executed"
key-files:
  created: []
  modified:
    - installer/executors.py
    - installer/session.py
    - installer/engine.py
    - installer/render.py
    - tests/test_executors.py
    - tests/test_engine.py
    - tests/test_plan.py
    - tests/test_session.py
    - tests/test_render.py
key-decisions:
  - "D-12 as locked: MANUAL decided at plan time; review word manual, yellow; not RUNNABLE; retained; exit code unchanged"
  - "The engine re-checks the same predicate before each ladder method; a handoff ends the ladder and the runner is never called"
  - "Dependents of a MANUAL row are BLOCKED at plan time with 'needs <tool>' (ledger: the handoff ends the ladder)"
  - "manual_command travels on PlanRow and InstallOutcome; the same handoff.command fills both"
  - "Command text is exact: sudo dnf install {p}, sudo apt-get install {p}, sudo pacman -S --needed {p} (no -y, no --noconfirm); rpm-ostree install {p} for the rpm_ostree row"
requirements-completed: [LIFE-02]
duration: unknown
completed: 2026-11-04
status: complete
---

# Phase 22 Plan 02: Native installs become a manual handoff; no executor runs sudo

**A native-only install is a MANUAL review row with the exact `sudo ...` command, the engine hands native methods off at run time, and no executor builds an elevated argv.**

## Performance

- **Duration:** unknown (PLAN_START_TIME was not captured at spawn; the three commits span 01:03:31 to 01:10:25 -0300)
- **Tasks:** 3, one green `feat(22-02)` commit each
- **Files modified:** 9

## Accomplishments

- `Disposition.MANUAL` (review word `manual`, yellow). A native-only tool reads `manual — needs sudo (never run here); you run: \`sudo dnf install jq\``, nothing runs, the row stays selected, and the exit code is unchanged.
- `executors.needs_manual(method)` returns a `ManualHandoff(reason, command)` for dnf, apt, pacman and rpm_ostree, and `None` for every other kind.
- The engine checks `needs_manual` before `runner.method_started`. A native method reached at run time returns `MANUAL_REQUIRED` with `handoff=(command,)`, ends the ladder, and the runner is called zero times.
- The native executor functions and their `EXECUTORS` entries are deleted. An AST test over `installer/` and `setup.py` fails on any list or tuple literal whose first element is `sudo`, `pkexec` or `doas`.
- The finished row reads ``manual — you run: `sudo dnf install jq` ``. The run report prints `  <id> — manual setup required:`, then the bare command on the next line, sanitized, with markup off and `soft_wrap=True`.

## Task Commits

1. **Task 1: a native-only tool is planned as manual with its exact command** - `c1e9ee9` (feat)
2. **Task 2: the engine hands off a native method at run time; the native argv is gone** - `d86271e` (feat)
3. **Task 3: the finished row and the run report show the exact command, copy-safe** - `b3844b9` (feat)

The RED output is recorded below. It stayed out of the git history: each task's test and code shipped in one commit, and every commit is green (R1-01).

## RED and GREEN evidence

### Task 1 RED

`uv run pytest tests/test_plan.py tests/test_session.py -k "native_only or apt_and_pacman or dependent_of_a_manual or every_disposition" -q --no-cov -n 0`

```
FAILED tests/test_plan.py::test_a_native_only_tool_is_planned_manual_with_its_exact_command
FAILED tests/test_plan.py::test_apt_and_pacman_commands_are_exact[apt-debian-sudo apt-get install jq]
FAILED tests/test_plan.py::test_apt_and_pacman_commands_are_exact[pacman-arch-sudo pacman -S --needed jq]
FAILED tests/test_plan.py::test_a_dependent_of_a_manual_row_is_blocked_at_plan_time
FAILED tests/test_session.py::test_every_disposition_manual_is_reviewed_right_after_blocked
E   AttributeError: 'PlanRow' object has no attribute 'manual_command'
E   AttributeError: type object 'Disposition' has no attribute 'MANUAL'
```

The parametrized `test_every_disposition_has_words_and_a_review_place` passed before the change. It iterates the existing members, so it is a regression guard. Its placement assertion is the RED, in `test_every_disposition_manual_is_reviewed_right_after_blocked`.

### Task 1 GREEN

- Selector above: 17 passed, exit 0.
- `uv run pytest tests/test_plan.py tests/test_session.py tests/test_deps.py tests/test_execute_screen.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 0 (ruff, pyright 0 errors, bandit, vulture, shellcheck).
- `make test`: exit 0, 5255 passed, 4 skipped. The first run failed; see Issues Encountered.

### Task 2 RED

`uv run pytest tests/test_engine.py tests/test_executors.py -q --no-cov -n 0`: exit 1, 10 failed. Log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/22-02-logs/t2-red.log`.

```
FAILED tests/test_engine.py::test_a_native_method_is_handed_off_with_zero_runner_calls
FAILED tests/test_engine.py::test_a_native_method_after_a_failed_method_is_handed_off
FAILED tests/test_engine.py::test_repair_walks_the_ladder_past_already_installed
FAILED tests/test_engine.py::test_receiptless_install_writes_nothing
FAILED tests/test_executors.py::test_native_kind_is_a_manual_handoff_and_never_executed[dnf-sudo dnf install jq]
FAILED tests/test_executors.py::test_native_kind_is_a_manual_handoff_and_never_executed[apt-sudo apt-get install jq]
FAILED tests/test_executors.py::test_native_kind_is_a_manual_handoff_and_never_executed[pacman-sudo pacman -S --needed jq]
FAILED tests/test_executors.py::test_every_command_kind_has_an_executor
FAILED tests/test_executors.py::test_native_kinds_have_no_executor
FAILED tests/test_executors.py::test_no_argv_literal_starts_with_an_elevation_command
```

The AST test failed on the then-present `["sudo", "dnf", ...]` literals in `installer/executors.py`.

### Task 2 GREEN

- `uv run pytest tests/test_engine.py tests/test_executors.py tests/test_plan.py tests/test_session.py -n auto -q --no-cov`: exit 0.
- Acceptance greps: no `def _dnf(`, `def _apt(` or `def _pacman(` in `installer/executors.py` (grep exit 1); `needs_manual(` appears once in `installer/engine.py`; `"sudo", "dnf"` appears 0 times in `tests/test_engine.py`.
- Suppression comments (`type: ignore|pyright: ignore|noqa|nosec`) in `installer/ tests/ setup.py`: 456 at base `6fcaa7f`, 456 now. None added.
- `make validate`: exit 0. `make test`: exit 0, 5261 passed, 4 skipped.

### Task 3 RED

`uv run pytest tests/test_render.py -k "manual_row_finishes or render_handoff_prints or render_handoff_keeps or long_manual_reason" -q --no-cov -n 0`: exit 1, 4 failed. Log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/22-02-logs/t3-red.log`.

```
E   AssertionError: assert 'see the setup steps in the log' == 'you run: `sudo dnf install jq`'
E   AssertionError: assert ['jq — manual...nf install x'] == ['jq — manual...ll [red]x[/]']   (markup consumed [red]x[/])
E   AssertionError: assert '\x1b' not in 'jq — manual... \x1b[31my\n'                       (ESC printed; line wrapped)
FAILED tests/test_render.py::test_a_manual_row_finishes_with_its_command
FAILED tests/test_render.py::test_render_handoff_prints_the_command_alone_with_markup_off
FAILED tests/test_render.py::test_render_handoff_keeps_a_long_command_on_one_line_without_escapes
```

`test_the_review_row_folds_a_long_manual_reason` passed before the change, because the existing `fold_reason` already folds a 141-cell reason at width 78. It stays as the coverage the plan asked for.

### Task 3 GREEN

- Selector: exit 0. `uv run pytest tests/test_render.py tests/test_execute_screen.py tests/test_plan.py -n auto -q --no-cov`: exit 0.
- Acceptance: `sed -n "/def render_handoff/,/^def /p" installer/render.py` contains `markup=False, soft_wrap=True` (1) and `sanitize_log_line(` (1).
- `make validate`: exit 0. `make test`: exit 0, 5265 passed, 4 skipped.

## Test counts (start measured with `--collect-only`, end measured the same way)

| File | Start | End | Delta |
| --- | --- | --- | --- |
| tests/test_executors.py | 81 | 85 | +4 |
| tests/test_engine.py | 77 | 79 | +2 |
| tests/test_plan.py | 87 | 91 | +4 |
| tests/test_session.py | 100 | 111 | +11 |
| tests/test_render.py | 126 | 133 | +7 |

Full suite: 5265 passed, 4 skipped at the final commit. The ledger's replan figure was 5237 passed, measured before this plan.

## Existing tests changed or rewritten (each with its reason; none deleted)

- `tests/test_render.py::test_render_plan_words_and_marks_come_from_the_tables`: added `Disposition.MANUAL: Health.MISSING` to its health map. The new Disposition member raised a KeyError without it. A MANUAL row only arises from a MISSING, BROKEN or OK tool.
- `tests/test_executors.py`:
  - `test_dnf_executor_builds_sudo_install`, `test_apt_executor_builds_sudo_install` and `test_pacman_executor_builds_sudo_install` became the parametrized `test_native_kind_is_a_manual_handoff_and_never_executed`, which checks `needs_manual` and that `execute` raises with the runner empty. Reason: the native argv is deleted (plan R1-03 named these tests).
  - `test_missing_required_param_raises` uses `brew` with `formula`. Reason: the dnf executor no longer exists.
  - `test_every_command_kind_has_an_executor` expects the set without dnf, apt and pacman. Reason: deleted executors.
- `tests/test_engine.py`:
  - Native-argv assertions became handoff assertions: `test_repair_walks_the_ladder_past_already_installed`.
  - Native-as-succeeding-vehicle tests moved to `brew`, keeping their purpose: `test_first_method_succeeds` (brew first), `test_install_tool_prepends_declared_bin_dir`, `test_non_download_install_is_not_marked_verified`, `test_postinstall_hook_dispatches_after_a_successful_install`, `test_postinstall_hook_sees_the_same_tools_freshly_prepended_bin_dir`, `test_postinstall_failure_does_not_fail_the_install`, `test_no_postinstall_field_means_no_dispatch`, `test_failed_install_never_dispatches_postinstall`, `test_login_shell_action_is_not_offered_when_tool_declares_no_post_install`, `test_raising_confirm_degrades_to_named_warning_not_a_crash`, `test_repair_dispatches_post_install_like_a_fresh_install`, `test_all_methods_fail_returns_failed`.
  - `test_falls_through_to_next_method_on_failure` is the plan-named version: failing `uv-tool` then succeeding `brew`.
  - `test_postinstall_hook_exception_does_not_fail_the_install_or_crash`: brew first, dnf second; asserts `attempted == ["brew"]`.
  - `test_receiptless_install_writes_nothing`: kept as `dnf`, and the first assertion is now `MANUAL_REQUIRED`. The test's purpose is that a receiptless kind writes nothing; `brew` would have written a receipt.
  - Left unchanged: `test_already_installed_short_circuits` and `test_already_installed_never_dispatches_postinstall` keep their `dnf` placeholders. The method never runs there.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Test bug] Plan-test platform**
- **Found during:** Task 1 GREEN
- **Issue:** `plan_state` defaults to the macOS platform. The new fedora, debian and arch tests therefore built unavailable rows (SKIP), not MISSING rows.
- **Fix:** the tests pass their own platform to `plan_state`. The implementation was not changed.
- **Committed in:** `c1e9ee9`

**2. [Plan-test note] Two planned tests not added as new**
- `test_a_broken_native_owned_tool_stays_blocked`: the existing parametrized `test_broken_tool_owned_by_a_native_manager_is_blocked_never_repaired` already asserts the same BLOCKED text, `"<owner> owns it; repair needs sudo (never run here)"`. It is a regression guard that passes before and after, so no duplicate was added.

**3. [Lint] Ruff fixes during Task 1**
- An E501 line and an I001 import order in new code, fixed by hand and by `ruff check --fix --select I001` plus `ruff format` on the touched files. No check was relaxed.

### Behavior to review (per plan, not changed)

- The `build_plan` reverse pass treats MANUAL like BLOCKED, as the plan requires. A RUNNABLE dependency whose only requirer is a MANUAL row is therefore skipped with the existing text `not needed while <requirer> is blocked`. The word "blocked" is slightly off for a MANUAL requirer. Flagged for review.

### Risk noted

- `needs_manual` uses `require_str(method, "package")`. A native method without `package` now raises `ExecutorError` at plan time (inside `build_plan`) and outside `install_tool`'s try block, where it used to be a row failure. Checked: all 32 native methods in `installer/registry.toml` declare `package`. The loader does not enforce it (`installer/model.py`), so this is unguarded. Plan 22-04 touches the same predicate.

## Issues Encountered

- **Bash guard refused the compound worktree check** at the start (`this command is too complex to verify...`). I ran the same checks as separate commands from the worktree root: branch `worktree-agent-a17686acfc95a23cf`, HEAD `6fcaa7f` (the expected base), and the top-level path all matched.
- **Host guard event during the first `make test` of Task 1.** `tests/conftest.py::real_home_untouched` reported `the test suite modified real files under /home/bazzite: ['.bashrc']`, with 3 failures in `test_render` (my missing MANUAL health mapping, fixed) and 10 teardown errors. The 10 errors are one session-guard event seen by 10 xdist workers. A concurrent `make test` from sibling worktree `agent-ae1458d9997f5e90d` was running on the same host during that window (`.bashrc` mtime 04:00:28Z, inside my run). I did not touch `.bashrc`, and I did not write it manually or restore it. I could not attribute the write. Re-runs on Task 1, Task 2 and Task 3 all passed, with `.bashrc` unchanged before and after each run. **For the orchestrator:** the session guard is cross-process and can false-fail when two `make test` runs overlap on the same host.
- **Scratch logs** from `make validate` and `make test` were kept out of the worktree and stored under `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/22-02-logs/`.

## Human check (not run here)

Task 3's human-check is outstanding: at end of phase, in a disposable Fedora container TUI, select a native-only tool, run it, select the command under `{id} — manual setup required:` in the run log, paste, and compare with the command. Not automated; it needs a UTF-8 terminal.

## Next Phase Readiness

- 22-04 adds the `writable_prefix` branch and a required `writable` keyword to `needs_manual`. `_row` and the engine re-check both call it with the first resolved method, so the keyword reaches both callers.
- 22-13 consumes the copy text (`you run: ...`, `manual setup required:`) as specified in 22-UI-SPEC.

---
*Phase: 22-method-lifecycle-contract*
*Completed: 2026-11-04*

## Self-Check: PASSED

Every file named above exists, and commits `c1e9ee9`, `d86271e` and `b3844b9` are ancestors of HEAD.
