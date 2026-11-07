---
phase: 23-configuration-as-a-lifecycle-step
plan: "08"
subsystem: installer
tags: [uninstall, removal, postinstall, hooks, unregister, codegraph, receipts, tdd]
status: complete

requires:
  - phase: 23-01
    provides: receipt.hooks (hosts recorded per hook), register_hooks, the codegraph target map
  - phase: 23-05
    provides: unregister_argvs, hook_method, host_labels (postinstall.py)
provides:
  - RemovalPlan.unregister and RemovalPlan.hook_hosts: the undo argvs and hosts from receipt.hooks, never the present hosts
  - remove_tool(unregister=...): runs the previewed undo first, refuses the whole tool when the fresh undo differs, keeps the tool when the undo fails
  - ToolRemoval.unregistered and SweepResult.unregistered
  - UninstallDecision.unregister: the Uninstall view hands its previewed undo to the same remover the CLI uses
  - CLI preview line "{id}: runs {command}" for each undo, and the "Unregistered from agent hosts: {hosts}." result line
affects: [23-15 (removal copy: detail clause, review, result line), 23-16 (container run of codegraph removal, R1-38 evidence), 24 (herdr wiring)]

actuals:
  tokens: 8655     # chars/4 over `git diff 6f2c6e6 HEAD` (34622 chars); realized diff, not a harness count
  tasks: 3
  commits: 3       # MEASURED: git rev-list --count 6f2c6e6..HEAD (before this SUMMARY commit)

# Measured commit ledger (#3968): base..HEAD measured before this SUMMARY commit
commits: 3
plan_head_before: 6f2c6e6d3dd6736105b5ed10782fdd1ac4a51fb6
plan_head_after: c086632a9bfb8e42f07b00a84af871b63d0e54e8

tech-stack:
  added: []
  patterns:
    - "One rule per question: the hook method (hook_method), the proven named artifact (_proven_named), the undo host filter (unregister_hosts) and the command error line (_command_error_line) each have one definition, used by every caller"
    - "The undo argv's first word is the receipt-proven executable; the host list comes from the receipt only, filtered through the closed target map"

key-files:
  created:
    - .planning/phases/23-configuration-as-a-lifecycle-step/23-08-SUMMARY.md
  modified:
    - installer/uninstall.py
    - installer/app.py
    - installer/wizard_app.py
    - installer/postinstall.py
    - tests/test_uninstall.py
    - tests/test_uninstall_e2e.py
    - tests/test_app.py
    - tests/test_wizard_app.py

key-decisions:
  - "D-04 as planned: RemovalPlan.unregister / hook_hosts are separate fields (no hook slot in argv); both are filled only when the receipt records hooks for tool.postinstall AND the tool has a receipt-proven artifact of type link, leaf or file named tool.cmd"
  - "unregister_hosts(name, recorded) is the one host filter; unregister_argvs and removal's hook_hosts both use it, so the closed target map is applied in one place"
  - "The undo argv keeps the target map order (claude,codex); hook_hosts and SweepResult.unregistered are sorted"
  - "remove_tool compares unregister with the fresh plan exactly like argv: a difference refuses the whole tool before anything runs (T-23-21)"
  - "A failed undo returns ToolRemoval(False, 'unregister: {first error line}') and deletes nothing, keeps the receipt (O4, U5)"
  - "ToolRemoval.unregistered is set on every successful return after the undo ran; a refusal returns no hosts (see Issues)"
  - "The CLI prints each tool's undo lines before its own command line, shown by executable name (unregister_runs_line); the Uninstall view hands the same commands to remove_tool"
  - "Receipts with hooks={} (written before Phase 23) unregister nothing; the removal still succeeds (R1-39, shortcut comment at _hook_undo)"

patterns-established:
  - "Test-first, one green commit per task: RED output recorded here; tests and code committed together where a task has code"

requirements-completed: [CONF-01]

# Plan-level status against the requirements
# CONF-01: removing a hook tool unregisters exactly the receipt's recorded hosts, first, through the shared remover and re-proof.
# The removal copy (detail clause, review block, result line) is 23-15.
---

# Phase 23 Plan 08: Unregister a hook tool from its recorded hosts before removal — Summary

**Removing codegraph first runs `codegraph uninstall --target <recorded hosts> --keep-cli` for exactly the hosts its receipt records, through one remover shared by the CLI and the Uninstall view; a failed or drifted undo keeps the tool and deletes nothing.**

## Performance

- **Tasks:** 3 (all `tdd="true"`)
- **Commits:** 3, measured against base `6f2c6e6` (`git rev-list --count 6f2c6e6..HEAD`)
- **Duration:** unmeasured (no start timestamp recorded for this run)
- **Test counts (collected; `make test` passed / skipped):**
  - Start (measured with `uv run pytest --collect-only`, per-file sum): 5644 collected.
  - After Task 1: 5644 passed, 4 skipped (5648 collected; +4 new tests).
  - After Task 2: 5648 passed, 4 skipped (5652 collected; +4 new cases, see below).
  - After Task 3: 5653 passed, 4 skipped (5657 collected; +5 new tests).
  - Plan delta: 13 collected tests and cases. No test was removed.
  - Coverage: 96.19% (Task 1), 96.20% (Tasks 2 and 3). No coverage floor lowered.

## Accomplishments

- `installer/uninstall.py`: `RemovalPlan.unregister` and `RemovalPlan.hook_hosts` (appended fields); `removal_plan` fills them from `receipt.hooks[tool.postinstall]` through `_hook_undo`; `_recipe_argv` picks its method through `hook_method` (the 23-05 rule, no inline copy) and finds its leaf through `_proven_named`; `SweepResult.unregistered`.
- `installer/app.py`: `remove_tool(unregister=...)` compares the previewed undo with the fresh plan, runs the undo before the manager check, the recipe argv and any path, and returns `unregister: {first error line}` on failure; `_command_error_line` is the one error-line pick; `ToolRemoval.unregistered`; `unregister_runs_line`; `UninstallDecision.unregister`; `perform_uninstall` passes the previewed undo per tool and reports `unregistered` on both return sites; `run_uninstall` prints each tool's undo lines before the confirm and prints `Unregistered from agent hosts: {hosts}.` after a successful removal.
- `installer/wizard_app.py`: `_UninstallEntry.unregister` (appended field, default `()`), filled from `state.removable.unregister` for a selectable row; the decision builder passes `unregister={…}`. No copy change (23-15).
- `installer/postinstall.py`: `unregister_hosts(name, recorded)`, the one host filter (see Deviations).
- Tests: the codegraph fixture `plant_codegraph` (tests/test_uninstall.py) builds a github_release codegraph with a proven link, its receipt and the recorded hosts; the e2e test drives the real removal through it.

## Task Commits

1. **Task 1: unregister a hook tool from its recorded hosts before removal** — `364369c` (`feat`). Tests and code in one commit.
2. **Task 2: a failed or changed unregister keeps the tool** — `689a7dd` (`test`). Tests only; see Deviations, item 2.
3. **Task 3: preview and pass the unregister commands in both removal routes** — `c086632` (`feat`). Tests and code in one commit.

Commit `e7a8fe7` was made first and amended to `364369c` before any push, to remove a `Co-Authored-By` trailer that this run's rules forbid. Only this plan's own unpushed commit was rewritten.

## Test-first evidence

### Task 1 RED

Command: `uv run pytest tests/test_uninstall_e2e.py tests/test_uninstall.py -k "unregisters_exactly_the_recorded_hosts or builds_unregister_from_the_receipt or no_proven_executable_means_no_unregister or pre_phase_23_receipt_unregisters_nothing" -q --no-cov -n 0`
Log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-23-08-task1.log`. Exit 1, 4 failed (none committed alone):

```
FAILED tests/test_uninstall_e2e.py::test_removing_codegraph_unregisters_exactly_the_recorded_hosts
FAILED tests/test_uninstall.py::test_removal_plan_builds_unregister_from_the_receipt
FAILED tests/test_uninstall.py::test_no_proven_executable_means_no_unregister
FAILED tests/test_uninstall.py::test_a_pre_phase_23_receipt_unregisters_nothing
E   AttributeError: 'RemovalPlan' object has no attribute 'unregister'   (x4)
```

### Task 1 GREEN

- Focused command, same selection: 4 passed, exit 0.
- `make validate`: exit 0 (log `.../scratchpad/validate-23-08-t1.log`).
- `make test`: exit 0, 5644 passed, 4 skipped, coverage 96.19% (log `.../scratchpad/test-23-08-t1.log`).

### Task 2 (guard tests, no RED)

Command: `uv run pytest tests/test_app.py tests/test_uninstall.py -k "failed_unregister_stops or unregister_that_changed_since or tampered_receipt_host_list" -q --no-cov -n 0`. Exit 0, 4 passed (log `.../scratchpad/red-23-08-task2.log`). All four cases already passed on Task 1's code, so this is a regression guard, not RED.

Mutation check (the guards are not vacuous; each mutation was reverted by hand and `installer/app.py` was checked against the commit afterwards):
- Dropping `or unregister != fresh.unregister` from `remove_tool`: `test_an_unregister_that_changed_since_the_preview_refuses` FAILED, exit 1.
- Swallowing the undo's `CommandError` (no `return ToolRemoval(...)`): `test_a_failed_unregister_stops_the_removal` FAILED, exit 1.

`make validate`: exit 0. `make test`: exit 0, 5648 passed, 4 skipped, coverage 96.20%.

### Task 3 RED

Command: `uv run pytest tests/test_app.py tests/test_wizard_app.py -k "unregister_line_before_the_remove_line or reports_the_unregistered_hosts or reports_a_failed_unregister or passes_the_previewed_unregister or decision_carries_unregister" -q --no-cov -n 0`
Log: `.../scratchpad/red-23-08-task3.log`. Exit 1, 5 failed:

```
test_the_cli_prints_the_unregister_line_before_the_remove_line  AssertionError: the runs line is not printed
test_the_cli_reports_the_unregistered_hosts                    AssertionError: failed == ('codegraph',) (refused: changed since the preview)
test_the_cli_reports_a_failed_unregister                       AssertionError: "remove failed — unregister: boom" not printed
test_perform_uninstall_passes_the_previewed_unregister         TypeError: UninstallDecision.__init__() got an unexpected keyword argument 'unregister'
test_the_uninstall_view_decision_carries_unregister            AttributeError: 'UninstallDecision' object has no attribute 'unregister'
```

### Task 3 GREEN

- Focused command: 5 passed, exit 0.
- `make validate`: exit 0 (log `.../scratchpad/validate-23-08-t3.log`).
- `make test`: exit 0, 5653 passed, 4 skipped, coverage 96.20% (log `.../scratchpad/test-23-08-t3.log`).

Suppression gate: `git diff 6f2c6e6 HEAD` adds no `type: ignore`, `pyright: ignore`, `noqa` or `nosec`.

## Test changes (every change, with its reason)

- No existing test was changed or deleted.
- `tests/test_uninstall.py`: the import line gained `artifact_paths` (Task 1 helper) and `removal_plan`. Imports only.
- New tests (Task 1): `test_removing_codegraph_unregisters_exactly_the_recorded_hosts` (e2e), `test_removal_plan_builds_unregister_from_the_receipt`, `test_no_proven_executable_means_no_unregister`, `test_a_pre_phase_23_receipt_unregisters_nothing`.
- New tests (Task 2): `test_a_failed_unregister_stops_the_removal`, `test_an_unregister_that_changed_since_the_preview_refuses`, `test_a_tampered_receipt_host_list_is_filtered` (parametrized: `filtered` and `nothing-left`, 2 cases).
- New tests (Task 3): `test_the_cli_prints_the_unregister_line_before_the_remove_line`, `test_the_cli_reports_the_unregistered_hosts`, `test_the_cli_reports_a_failed_unregister` (split out of the plan's single CLI test so each route has one assertion focus), `test_perform_uninstall_passes_the_previewed_unregister`, `test_the_uninstall_view_decision_carries_unregister`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical: one rule per question] `installer/postinstall.py` gained `unregister_hosts`**
- **Found during:** Task 1 (`removal_plan` needs the hosts that `unregister_argvs` keeps, filtered through the map).
- **Issue:** `installer/postinstall.py` is not in this plan's `files_modified`. Computing `hook_hosts` in `uninstall.py` would have copied the closed-map filter that `unregister_argvs` already applies (a second rule that could drift).
- **Fix:** extracted `unregister_hosts(name, recorded) -> tuple[str, ...]` (map order, closed map) and made `unregister_argvs` call it. `uninstall._hook_undo` uses it too. Behaviour of `unregister_argvs` is unchanged; the 23-05 tests stay green.
- **Files modified:** `installer/postinstall.py`
- **Verification:** `make validate` and `make test` exit 0; `test_a_tampered_receipt_host_list_is_filtered` covers the filter through `removal_plan`.
- **Committed in:** `364369c`

**2. [Process] Task 2 is a tests-only commit, typed `test(23-08)`**
- **Found during:** Task 2 RED run.
- **Issue:** the three planned tests passed on Task 1's code. The plan's own text says that a test that already passes is a regression guard, and the plan's Task 2 has no implementation to write.
- **Fix:** kept the guard tests in their own commit, typed `test(23-08)`, instead of a `feat(23-08)` commit that would claim a code change. The mutation check above shows they catch their targets.
- **Committed in:** `689a7dd`

**3. [Process] Attribution trailer removed from Task 1**
- **Found during:** Task 1 commit.
- **Issue:** the first commit carried a `Co-Authored-By` trailer. This run's rules say no attribution trailers.
- **Fix:** amended the same (unpushed, this plan's) commit before any push. The branch history contains no trailer.
- **Committed in:** `364369c` (rewritten from `e7a8fe7`)

**4. [Rule 3 - Blocking] `ruff` lint and format on the new tests**
- **Found during:** Task 1 and Task 3 `make validate`.
- **Issue:** import order (`removal_plan` sorts before `remove_paths`), 100-column limit on a docstring and a call, and ruff format's expansion of two tuples.
- **Fix:** `ruff check --fix`, `ruff format` on the changed files, one docstring shortened. No suppression added.
- **Committed in:** `364369c`, `c086632`

### Judgement calls (not deviations from the plan's behaviour)

- `_proven_named(plan, tool_id, name, types)` matches a name against both the bare name and the absolute path (`name in (artifact.path.name, str(artifact.path))`). This is one rule that covers what `_recipe_argv` used to split on `"/"`. A bare name never equals an absolute path and an absolute path never equals a bare name, so the behaviour is identical and the existing recipe tests stay green unchanged.
- `unregister_runs_line` lives beside `removal_runs_line` in `installer/app.py`.
- The e2e test drives the real `remove_tool`, but with `present_hosts` patched to claim `opencode` is present, so the test proves that removal reads the receipt, not the present hosts.

## Issues Encountered

- **Interim commit state (between `364369c` and `c086632`):** `run_uninstall` and `perform_uninstall` do not pass `unregister` until Task 3. In `364369c` alone, the CLI and the Uninstall view refuse a codegraph whose receipt records hooks, with `changed since the preview; not removed`. That refusal is fail-closed (nothing runs, nothing is deleted), but the message is misleading. The branch's final tree is correct. Do not cut a release from `364369c`.
- **Harness refusals:** the Bash guard refused several compound commands that name git, and one `until` loop whose path names git. Each was split into plain commands. No command ran outside the worktree.
- **Host safety:** all tests use `tmp_path` and a monkeypatched `HOME`. No real `codegraph`, `herdr` or `tldr` was invoked, and no `make setup`, `make fix`, `make uninstall`, or sudo. The session guard did not trip in any of the three full runs.
- **Estimate calibration:** the plan's `estimate.tokens` was 95000. The measured realized diff is 8655 (chars/4). Recorded as is, not rounded; the orchestrator may want to recalibrate.

## Known Stubs

None.

## Threat Flags

None beyond the plan's register. T-23-19 (`test_a_tampered_receipt_host_list_is_filtered`, `test_removing_codegraph_unregisters_exactly_the_recorded_hosts`), T-23-20 (`test_a_failed_unregister_stops_the_removal`), T-23-21 (`test_an_unregister_that_changed_since_the_preview_refuses`), T-23-22 (`test_no_proven_executable_means_no_unregister`), and T-23-57 (`test_a_pre_phase_23_receipt_unregisters_nothing`, accepted) are covered by the tests named.

## Unverified and open items for the orchestrator

- **Report gap after an undo ran (new):** `remove_tool` returns `ToolRemoval(False, ...)` without `unregistered` when a later path refusal occurs after the undo ran. The hosts were unregistered but the CLI does not print `Unregistered from agent hosts`. The plan's success-only rule produces this. Option: set `unregistered=fresh.hook_hosts` on the refusal return too. Left as planned; the orchestrator decides.
- **R1-38 (absent recorded host):** whether `codegraph uninstall --target <host>` exits non-zero when that host's config is gone is unverified. Evidence belongs to the 23-16 container run, not to this plan. No filter was added (D-04/O4 locked).
- **R1-39 manual check:** a pre-Phase-23 codegraph receipt (hooks={}) unregisters nothing by design. The manual check in 23-VALIDATION was not run here.
- **Copy and result display:** `SweepResult.unregistered` is computed and returned but no TUI copy shows it yet. The removal copy is 23-15.
- **Orphan helpers (23-05 note):** `unregister_argvs`, `hook_method` and `host_labels` now have production callers, via `uninstall.py` and `app.py`. The herdr pair stays unwired until Phase 24, as planned.

## Self-Check

- [x] `installer/uninstall.py`: `unregister: tuple[tuple[str, ...], ...] = ()` present in `RemovalPlan`; `unregister_argvs(` called once (`_hook_undo`); `hook_method(` used in `_recipe_argv`; `keyed = ` gone from `_recipe_argv`; `def _proven_named(` once.
- [x] `installer/app.py`: `fresh.unregister` appears 2 times (refusal comparison, undo loop); `f"unregister: {…}"` once; `def _command_error_line(` once; `def unregister_runs_line(` once; `Unregistered from agent hosts:` once.
- [x] Commits `364369c`, `689a7dd`, `c086632` exist on `worktree-agent-a7ac0b660bd11fb41` after base `6f2c6e6`.
- [x] `make validate` exit 0 and `make test` exit 0 on each commit's tree (and on the final tree).
- [x] STATE.md and ROADMAP.md are not modified.

## Self-Check: PASSED
