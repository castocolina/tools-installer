---
phase: 22-method-lifecycle-contract
plan: "09"
subsystem: removal
tags: [config-paths, uninstall, step-4, shared-paths, symlink-safety, pnpm-co-install, cli, tdd]
commits: 3
plan_head_before: 705385ccd9bf60ec6acfc4bb6005b43ae5102b71
plan_head_after: dcf128b1720cca0f6ae6e4f10f34453038d22406

requires:
  - phase: 22-01
    provides: "Tool.config_paths (validated at load), HARNESS_MARKER_DIRS"
  - phase: 22-06
    provides: "removal_plan, config_targets, remove_tool, removal_order, MANAGER_UNINSTALL_ARGV"
provides:
  - "UninstallDecision.config: per-tool declared config paths the review listed (empty by default; the CLI never sets it)"
  - "perform_uninstall step 4: a listed path is deleted once, after every removal, only when every catalog owner was removed and listed it; a required catalog keyword"
  - "uninstall.delete_config_path: parent and harness-target refusal, final symlinks unlinked only"
  - "SweepResult.config_deleted and config_not_deleted"
  - "CLI: the config-kept block before the confirm; pnpm group warnings before the confirm"
  - "pnpm_globals.co_install_warnings and app.pnpm_removal_packages (public; 22-11 reuses the latter)"
affects: [22-10, 22-11, 22-13]

actuals:
  tokens: 9688     # chars/4 over the realized diff (38752 bytes of `git diff 705385c HEAD -- installer tests setup.py`)
  tasks: 3
  commits: 3       # MEASURED: git rev-list --count 705385c..HEAD (before this SUMMARY commit)

tech-stack:
  added: []
  patterns:
    - "Step 4 after the removal loop: a config path follows every owner, never a single tool"
    - "Trust-boundary re-check at delete time: the parent resolves inside HOME and outside harness dirs; the target is never a harness dir or one a marker resolves into"

key-files:
  created:
    - .planning/phases/22-method-lifecycle-contract/22-09-SUMMARY.md
  modified:
    - installer/uninstall.py
    - installer/app.py
    - installer/pnpm_globals.py
    - setup.py
    - tests/test_app.py
    - tests/test_uninstall.py
    - tests/test_pnpm_globals.py
    - tests/test_uninstall_e2e.py

key-decisions:
  - "Step 4 runs once after the tool loop and before the environment levers (D-07). Deletion needs every catalog declarer removed and listed (UI-SPEC A5, review R1-15); an undeclared path is never deleted and gets the warning `config {path} is not declared by any tool; not deleted`"
  - "SweepResult.config_deleted names the tools whose listed path was deleted or already gone. config_not_deleted names the tools that asked for config but were not removed (failed or refused, review R2-02)"
  - "delete_config_path resolves the parent with realpath and refuses outside the real HOME or under a harness marker; it also refuses a non-symlink target that a resolved marker equals or sits under; a final symlink is unlinked only (review R1-17, R2-06)"
  - "The CLI prints the config-kept heading only when a tool being removed has an existing declared path, and reads plan.config instead of re-expanding (no private import from uninstall)"
  - "co_install_warnings reads only the declared co_install groups; the group name is the declaring tool id (no pnpm query, D-10)"

requirements-completed: [UI-04, LIFE-08]

coverage:
  - id: D1
    description: "A listed config path is deleted after its tool's removal succeeds, and kept when the toggle is off"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_toggled_config_is_deleted_after_the_removal"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_config_survives_with_the_toggle_off"
        status: pass
    human_judgment: false
  - id: D2
    description: "A failed or refused removal keeps its config and names the tool in config_not_deleted"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_a_failed_removal_keeps_the_config"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_a_refused_removal_keeps_the_config"
        status: pass
    human_judgment: false
  - id: D3
    description: "A shared path goes only when every catalog owner was removed and listed it"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_a_shared_config_path_needs_every_owner_removed"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_a_shared_config_path_needs_every_catalog_owner"
        status: pass
    human_judgment: false
  - id: D4
    description: "Config is never deleted through a parent that resolves outside HOME or into a harness dir, nor through a target a harness marker resolves to"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_uninstall.py#test_a_config_path_under_a_symlinked_parent_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall.py#test_a_config_dir_a_harness_marker_points_to_is_refused"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_a_refused_config_parent_is_a_warning_and_the_tool_is_removed"
        status: pass
    human_judgment: false
  - id: D5
    description: "The CLI never deletes config and prints the kept block before the confirm"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_the_cli_never_deletes_config"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_the_cli_prints_no_config_block_without_existing_config"
        status: pass
    human_judgment: false
  - id: D6
    description: "Removing a pnpm co-install member warns about its group before anything runs; a full group removal gives one line; a package outside any group gives none"
    requirement: "LIFE-08"
    verification:
      - kind: unit
        ref: "tests/test_pnpm_globals.py#test_removing_one_member_warns_with_the_group"
        status: pass
      - kind: unit
        ref: "tests/test_pnpm_globals.py#test_removing_every_member_warns_once"
        status: pass
      - kind: unit
        ref: "tests/test_pnpm_globals.py#test_a_package_outside_any_group_warns_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_the_cli_prints_the_group_warning_before_the_confirm"
        status: pass
    human_judgment: false
---

# Phase 22 Plan 09: Config is kept unless the user asks, per tool (step 4, safe deletes, pnpm group warning) Summary

**Config deletion is step 4 of each tool's removal: a listed path goes after the removal succeeded, only when every catalog owner went with it, never through a symlinked parent into HOME's harness dirs; the CLI keeps config and says so, and removing a pnpm co-install member warns about its group before anything runs.**

## Performance

- **Tasks:** 3 of 3, one green commit each
- **Files modified:** 8 (5 source/test files in the plan's list plus the e2e test)
- **Commits:** ca9d3e4, 1af2b37, dcf128b

## Accomplishments

- `UninstallDecision.config` (empty default). `perform_uninstall` gains the required `catalog` keyword; `setup._do_uninstall` passes the registry.
- Step 4 runs once after the tool loop: a path is deleted only when every catalog tool declaring it was removed and lists it; a path no catalog tool declares is never deleted (warning); a delete failure is a warning that never restores the receipt.
- `delete_config_path` refuses a parent that resolves outside the real HOME or under a harness marker, and refuses a non-symlink target that a resolved marker equals or lies under. A final symlink is unlinked, never followed.
- `SweepResult.config_deleted` and `config_not_deleted`.
- `run_uninstall` (CLI): prints `Config kept; only the Uninstall view deletes config (press c on a row):` and each existing declared path of the tools being removed, before the confirm. The CLI path never calls `delete_config_path`.
- `pnpm_globals.co_install_warnings(removing, catalog)` from the declared groups (no pnpm query); `app.pnpm_removal_packages(plans)` (public, reused by 22-11); `run_uninstall` prints the group warnings after the runs lines and before the confirm.

## Task Commits

1. **Task 1: per-tool config deletion as removal step 4** - `ca9d3e4` (feat, tests and implementation together)
2. **Task 2: shared-path rule, safe deletes and the CLI config line** - `1af2b37` (feat, tests and implementation together)
3. **Task 3: warn about the pnpm group before removing a member** - `dcf128b` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree; the pre-commit hooks passed on each commit. No `--no-verify`, no attribution trailers, no RED-only commit.

**Intermediate-commit caveat:** `ca9d3e4` alone has the basic `delete_config_path` (no parent or harness-marker refusal). The symlink and harness guards landed in `1af2b37`. Do not cut anything from `ca9d3e4` by itself; the branch's final state is the one that matters.

## TDD Gate Compliance

RED output is recorded here only. Each feat commit holds its tests with the implementation (review R1-01, ledger row 31). Logs are kept under the session scratchpad.

### Initial RED, before any implementation (HEAD `705385c`)

`uv run pytest tests/test_app.py tests/test_uninstall.py -k "toggled_config or toggle_off or ... symlinked_config" -q --no-cov -n 0`: 16 FAILED entries (listed below). `test_the_cli_prints_no_config_block_without_existing_config` was selected but is not in the failure list, so it passed on HEAD (see below).

```
FAILED tests/test_app.py::test_toggled_config_is_deleted_after_the_removal - ...
  E  TypeError: UninstallDecision.__init__() got an unexpected keyword argument 'config'
FAILED tests/test_app.py::test_config_survives_with_the_toggle_off - TypeError ...
FAILED tests/test_app.py::test_a_failed_removal_keeps_the_config - TypeError ...
FAILED tests/test_app.py::test_a_refused_removal_keeps_the_config - TypeError ...
FAILED tests/test_app.py::test_a_shared_config_path_needs_every_owner_removed
FAILED tests/test_app.py::test_a_shared_config_path_needs_every_catalog_owner
FAILED tests/test_app.py::test_a_config_path_already_gone_is_skipped - TypeError ...
FAILED tests/test_app.py::test_an_undeclared_config_path_is_never_deleted - TypeError ...
FAILED tests/test_app.py::test_a_config_delete_failure_is_a_warning
  E  AttributeError: module 'installer.app' has no attribute 'delete_config_path'
FAILED tests/test_app.py::test_a_refused_config_parent_is_a_warning_and_the_tool_is_removed - TypeError ...
FAILED tests/test_app.py::test_an_interrupt_before_step_4_leaves_the_config
  E  AttributeError: module 'installer.app' has no attribute 'delete_config_path'
FAILED tests/test_app.py::test_the_cli_never_deletes_config
  E  AssertionError: assert 'Config kept; only the Uninstall view deletes config (press c on a row):\n' in 'gh: runs brew uninstall gh\n'
FAILED tests/test_app.py::test_the_cli_prints_the_group_warning_before_the_confirm
  E  AssertionError: assert 'Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli leaves puppeteer installed.' in 'mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli\n'
FAILED tests/test_uninstall.py::test_a_config_path_under_a_symlinked_parent_is_refused
FAILED tests/test_uninstall.py::test_a_config_dir_a_harness_marker_points_to_is_refused
FAILED tests/test_uninstall.py::test_symlinked_config_is_unlinked_not_followed
  E  ImportError: cannot import name 'delete_config_path' from 'installer.uninstall'
```

The pnpm tests were not in that run. `tests/test_pnpm_globals.py` failed at collection, which is the RED for Task 3:

```
E   ImportError: cannot import name 'co_install_warnings' from 'installer.pnpm_globals'
ERROR collecting tests/test_pnpm_globals.py
```

`test_the_cli_prints_no_config_block_without_existing_config` already passed at HEAD. It is a regression guard (the CLI must not print the block when no config exists), not RED.

### Task 1 RED (against HEAD, the four task-1 tests)

`uv run pytest tests/test_app.py -k "toggled_config or config_survives or failed_removal_keeps_the_config or refused_removal_keeps_the_config" -q --no-cov -n 0` failed on `TypeError: UninstallDecision.__init__() got an unexpected keyword argument 'config'` for all four (the RED run above).

### Task 1 GREEN

```
uv run pytest tests/test_app.py -k "toggled_config or config_survives or failed_removal_keeps_the_config or refused_removal_keeps_the_config" -q --no-cov -n 0
....   [100%]        exit 0
```

Uninstall suites after the implementation (`tests/test_app.py tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_setup.py tests/test_wizard_app.py -n auto`): exit 0, no failures.

### Task 2 RED (against the Task 1 commit, 12 task-2 tests selected)

Four failed; eight already passed on the Task 1 code (the step-4 rule was built with Task 1, see the deviation below):

```
FAILED tests/test_app.py::test_a_refused_config_parent_is_a_warning_and_the_tool_is_removed
FAILED tests/test_app.py::test_the_cli_never_deletes_config - AssertionError (no "Config kept" block)
FAILED tests/test_uninstall.py::test_a_config_path_under_a_symlinked_parent_is_refused
FAILED tests/test_uninstall.py::test_a_config_dir_a_harness_marker_points_to_is_refused
```

Already passing on the Task 1 code: `test_a_shared_config_path_needs_every_owner_removed`, `test_a_shared_config_path_needs_every_catalog_owner`, `test_a_config_path_already_gone_is_skipped`, `test_an_undeclared_config_path_is_never_deleted`, `test_a_config_delete_failure_is_a_warning`, `test_an_interrupt_before_step_4_leaves_the_config` (backstop), `test_the_cli_prints_no_config_block_without_existing_config` (guard), `test_symlinked_config_is_unlinked_not_followed`.

### Task 2 GREEN

`uv run pytest tests/test_app.py tests/test_uninstall.py -k "..." -v --no-cov -n 0`: `12 passed, 276 deselected`, exit 0.

### Task 3 RED

`tests/test_pnpm_globals.py`: `ImportError: cannot import name 'co_install_warnings' from 'installer.pnpm_globals'` (collection error, exit 2).
`tests/test_app.py::test_the_cli_prints_the_group_warning_before_the_confirm`:
`AssertionError: assert 'Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli leaves puppeteer installed.' in 'mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli\n'`

### Task 3 GREEN

`uv run pytest tests/test_pnpm_globals.py tests/test_app.py -k "one_member_warns or every_member_warns or outside_any_group or group_warning_before_the_confirm" -v`: `4 passed, 268 deselected`, exit 0.

## Test counts (floors)

| File | Start (705385c) | End (dcf128b) | Delta |
|---|---|---|---|
| tests/test_app.py | 169 | 183 | +14 (task 1: 4, task 2: 9, task 3: 1) |
| tests/test_uninstall.py | 103 | 106 | +3 (task 2) |
| tests/test_pnpm_globals.py | 86 | 89 | +3 (task 3) |
| tests/test_uninstall_e2e.py | 18 | 18 | 0 (5 existing call sites gained `catalog=`) |
| whole suite (`--collect-only`) | 5405 | 5425 | +20 |

Task 2 floor (test_app + test_uninstall at least start + 10): 272 → 289, +17. Met.

`make validate` exit 0 on each commit's tree (last run on the Task 3 tree: exit 0, after one E501 fix in a docstring).
`make test` on each commit's tree: 5409 collected (task 1: 5405 passed, 4 skipped; coverage 96.23%), 5421 collected (task 2: 5417 passed, 4 skipped; coverage 96.28%), 5425 collected (task 3: 5421 passed, 4 skipped; coverage 96.27%); exit 0 each time. The session guard did not trip.

## Test changes (existing tests)

Each existing test that changed, and why:

- `tests/test_app.py`: 16 existing `perform_uninstall(` call sites gained a `catalog=` keyword (the plan requires `catalog` as a required keyword, review R1-15, so every caller passes one). No assertion changed. The two `# type: ignore[call-arg]` tests that check a missing `daemon_policy` were left as they were.
- `tests/test_uninstall_e2e.py`: the 5 existing `perform_uninstall(` call sites gained `catalog=` (the two `_remove` wrappers pass `decision.tools`; three `UninstallDecision(tools=(tool,), ...)` calls pass `(tool,)`). No assertion changed.
- No test was deleted.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 3 - Blocking] Lint and format fixes in my own edits.** An E501 in the `perform_uninstall` docstring (my inserted sentence ran into the next line), an E501 in the `config_not_deleted` comprehension, an E501 in the `delete_config_path` docstring, an E501 in the `pnpm_removal_packages` docstring, and `ruff format` on `tests/test_app.py`. Fixed in the same commit each time; no suppression comment was added.

**2. [Rule 1 - Bug, my fixture] The brew test helper needed `config_paths`.** `Tool(...)` takes `config_paths` as a keyword (22-01); I used it directly in `_brew_config_tool` rather than changing `_manager_tool`.

### Plan deviations (recorded, not auto-fixed)

**1. Task 1 implemented the full step-4 rule, not only the tracer.** Task 1's commit carries the catalog-wide shared-owner rule and the undeclared-path warning, because step 4 is one function and splitting it would have written the same logic twice. Task 2 therefore added only what the RED run still showed missing: the parent and target refusals (`delete_config_path`) and the CLI config block. Eight of the twelve Task 2 tests already passed on the Task 1 code; that is recorded above rather than presented as RED. Scope is unchanged.

**2. Task 1's `delete_config_path` was the basic version.** The symlink and harness refusals were not in `ca9d3e4` and landed in `1af2b37`. See the intermediate-commit caveat above.

**3. `HARNESS_MARKER_DIRS` is a dict of tuples (17 keys), not a flat list.** The plan's "flattened values" is implemented as a nested comprehension over `.values()`.

**4. `config_not_deleted` semantics for a shared path.** A tool whose listed path stays because another catalog owner stays is in neither `config_deleted` nor `config_not_deleted`, and no warning is printed. The review screen (22-10, UI-SPEC row 5 "Config kept, shared") must report that case; this plan's result type does not carry it.

**5. The 22-06 TUI argv gap is not closed here.** 22-06's summary and RUN-LEDGER assign it to 22-07 (`_UninstallEntry.argv`, `_apply_removal`). 22-09's task list does not include it, so this plan does not touch the TUI decision's argv.

### Auto-fixed issues in tests

None beyond the lint and format fixes above.

## Threat Model Coverage

| Threat | Disposition | Where it is handled |
|---|---|---|
| T-22-21 config deletion outside declared paths | mitigate | `_config_step` deletes only paths equal to a catalog tool's expanded `config_paths`; a symlink is unlinked, never followed (`test_an_undeclared_config_path_is_never_deleted`, `test_symlinked_config_is_unlinked_not_followed`) |
| T-22-22 a shared config path of a tool that stays | mitigate | Deleted only when every catalog declarer was removed and listed it; `perform_uninstall` requires `catalog` (`test_a_shared_config_path_needs_every_owner_removed`, `test_a_shared_config_path_needs_every_catalog_owner`) |
| T-22-40 a symlinked ancestor or a harness marker reaching a config delete | mitigate | `delete_config_path` resolves the parent and refuses outside HOME or under a marker; refuses a non-symlink target that a marker equals or lies under (`test_a_config_path_under_a_symlinked_parent_is_refused`, `test_a_config_dir_a_harness_marker_points_to_is_refused`, `test_a_refused_config_parent_is_a_warning_and_the_tool_is_removed`) |
| T-22-23 CLI `--yes` deleting config | mitigate | `run_uninstall` never calls `delete_config_path` (grep gate below), `test_the_cli_never_deletes_config` |
| T-22-SC package installs | accept | This plan installs no package |

## Acceptance Greps (run on the final tree)

| Check | Expected | Actual |
|---|---|---|
| `def delete_config_path(` in installer/uninstall.py | 1 | 1 |
| `def co_install_warnings(` in installer/pnpm_globals.py | 1 | 1 |
| `def pnpm_removal_packages(` in installer/app.py | 1 | 1 |
| `"pnpm", "remove", "--global"` literal in installer/app.py | 0 | 0 |
| `delete_config_path(` inside `run_uninstall` | 0 | 0 |
| `realpath` and `is_relative_to` lines inside `delete_config_path` | at least 2 and at least 1 | 4 and 3 |
| `co_install_warnings` body queries pnpm (`split_install_groups`, `run_query`, `pnpm_global_packages`) | 0 | 0 |
| suppression comments added in the plan diff (`type: ignore`, `pyright: ignore`, `noqa`, `nosec`) | 0 | 0 |
| `make validate` on the final tree | exit 0 | exit 0 |
| `make test` on the final tree | exit 0 | exit 0 (5421 passed, 4 skipped) |

## Not Checked

- `make e2e` (container install and removal of every registry tool) was not run; it is the orchestrator's phase-close gate.
- The TUI (`wizard_app.py`, `catalog_tui.py`) was not changed and the new config toggle is not wired there; that is 22-10.
- Real `brew`, `pnpm` and `uv` were never executed: every removal command went through a recording or raising fake runner.
- Interrupt during the middle of a directory delete was not tested. The backstop test interrupts before the first `delete_config_path` call only. A kill during `shutil.rmtree` can leave a partially deleted config directory; the SPEC's "nothing half-deleted" is met at the level of which paths are attempted, not inside one directory.
- The orchestrator's cross-AI review of this plan was not run here.

## Self-Check

- `git merge-base --is-ancestor` for `ca9d3e4`, `1af2b37` and `dcf128b` against HEAD: all three FOUND.
- `22-09-SUMMARY.md`, `installer/uninstall.py` and `installer/pnpm_globals.py` exist on disk.

Self-Check: PASSED.

## Next Phase Readiness

- 22-10 reads `config_targets` and `UninstallDecision.config`; it must report the "Config kept, shared" case itself (deviation 4).
- 22-11 imports `pnpm_removal_packages` from `installer.app`.
- 22-13 consumes the CLI exit code, unchanged by this plan.
- No `.planning/STATE.md` or `ROADMAP.md` change was made here (orchestrator owns them).
