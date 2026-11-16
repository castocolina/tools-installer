---
phase: 22-method-lifecycle-contract
plan: "06"
subsystem: removal
tags: [removal-plan, receipts, manager-uninstall, recipe-remove, run-captured, dependency-order, tdd]
commits: 3
plan_head_before: 853b1afed4ef6e2ed9919508053f4995bb9d2af7
plan_head_after: fb07b621d807912dae3984c2498043046f8b4935

requires:
  - phase: 22-01
    provides: "Tool.config_paths, script keys paths/remove/update/writable_prefix, SCRIPT_ROOTS"
  - phase: 22-03
    provides: "receipt tree/leaf artifacts, record(preexisting=), preexisting_paths, remove_paths(trees=)"
  - phase: 22-04
    provides: "executors.needs_manual / prefix_writable (the install ladder this plan extends)"
provides:
  - "uninstall.removal_plan(tool, default_bin_dir, *, verify, hint) -> RemovalPlan with level, argv, config, hint"
  - "uninstall.MANAGER_UNINSTALL_ARGV (L1 table), config_targets(tool)"
  - "app.remove_tool (the one per-tool remover: command, proven paths, receipt), ToolRemoval, removal_order, removal_runs_line"
  - "app.run_uninstall returns (removed paths, failed ids); the CLI exits 1 on a failed removal"
  - "model.method_package / KIND_PACKAGE_PARAM (moved from ownership.py)"
  - "engine.install_tool: install-time preexisting snapshot and manager-package proof (read_inventory_fn)"
affects: [22-07, 22-08, 22-09, 22-10, 22-11]

actuals:
  tokens: 24800     # chars/4 over the realized diff (99194 bytes of `git diff 853b1af..fb07b62`)
  tasks: 3
  commits: 3        # MEASURED: git rev-list --count 853b1af..HEAD (before this SUMMARY commit)

tech-stack:
  added: []
  patterns:
    - "One removal seam: removal_plan decides the level from proof alone; remove_tool runs one tool in the locked order for both the CLI and the TUI"
    - "Fail closed on proof: a manager package the inventory lists (or cannot read) never gets a receipt, so L1 can never uninstall it"
    - "A vendor command runs only on a leaf this installer's receipt proved, bound by absolute path (no PATH lookup)"

key-files:
  created: []
  modified:
    - installer/uninstall.py
    - installer/app.py
    - installer/model.py
    - installer/ownership.py
    - installer/engine.py
    - setup.py
    - tests/test_app.py
    - tests/test_uninstall.py
    - tests/test_uninstall_e2e.py
    - tests/test_setup.py
    - tests/test_engine.py

key-decisions:
  - "L1: a manager argv only when the receipt's kind is a MANAGER_UNINSTALL_ARGV kind and its package equals the package a method of that kind declares (brew, cask, uv-tool, node)"
  - "L3: the vendor remove needs a script receipt with at least one proven artifact; its first word is replaced by a proven leaf's absolute path (exact path, or the unique bare name); otherwise no argv (fail closed)"
  - "remove_tool re-plans with verify=True after the confirm and refuses the whole tool when paths or argv changed; the no-argv path re-proves the previewed paths through remove_proven"
  - "removal_order reuses deps.resolve_dependencies on the selection as its own catalog and reverses the closure (dependents first)"
  - "A manager package the inventory lists, or cannot read, gets no receipt unless the previous receipt proved the same kind and package"
  - "install_tool's preexisting snapshot fails closed to None when artifact_paths raises, so record fails inside its own guard as before (the existing crash test pins this)"

requirements-completed: [LIFE-01, LIFE-03]

coverage:
  - id: D1
    description: "A recipe tool is removed by its vendor command (bound to a proven leaf), then its proven paths, then its receipt; a failed command deletes nothing"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_a_recipe_tool_is_removed_by_its_vendor_command_first"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_a_failing_remove_deletes_nothing"
        status: pass
    human_judgment: false
  - id: D2
    description: "A manager package is uninstalled only on this installer's receipt proof; a native owner gets no argv"
    requirement: "LIFE-03"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_a_brew_package_without_a_receipt_runs_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_a_native_owned_tool_has_no_argv"
        status: pass
    human_judgment: false
  - id: D3
    description: "CLI and TUI remove through the same remove_tool, with the post-confirm re-proof and dependents before their managers"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_the_cli_re_proves_after_the_confirm"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_the_cli_removes_a_dependent_before_its_manager"
        status: pass
    human_judgment: false
  - id: D4
    description: "An install never adopts a path that existed before it, and never claims a package the manager already listed"
    requirement: "LIFE-03"
    verification:
      - kind: unit
        ref: "tests/test_uninstall_e2e.py#test_a_declared_path_present_before_the_install_is_never_adopted"
        status: pass
      - kind: unit
        ref: "tests/test_uninstall_e2e.py#test_a_package_already_in_the_manager_gets_no_receipt"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every receipt-writing kind installs and removes in both directions in a scratch HOME"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_uninstall_e2e.py#test_every_receipt_kind_installs_and_removes_in_both_directions"
        status: pass
    human_judgment: false
  - id: D6
    description: "A failed CLI removal reaches the exit code"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_setup.py#test_a_failed_cli_removal_exits_non_zero"
        status: pass
    human_judgment: false
---

# Phase 22 Plan 06: One removal contract (removal_plan, remove_tool, receipt-proven manager removal) Summary

**removal_plan decides each tool's removal level from receipt and layout proof alone, and remove_tool runs the vendor or manager command, the proven paths and the receipt in that order for the CLI and the TUI; a manager package is only ever uninstalled on this installer's own receipt, and an install never claims a path or package it did not create.**

## Performance

- **Duration:** not recorded (the plan start timestamp was not captured in this run)
- **Tasks:** 3 of 3, one green commit each
- **Files modified:** 11

## Accomplishments

- `removal_plan(tool, default_bin_dir, *, verify=False, hint=None)` on top of `plan_removal`, with `level` (`manager`, `recipe`, `artifacts`, `none`), `argv`, `config` (expanded declared config entries that exist) and `hint`, all defaulted.
- L1: brew, cask, uv-tool and node uninstall argv (`brew uninstall`, `brew uninstall --cask`, `uv tool uninstall`, `pnpm remove --global`) only for a receipt whose package equals a method's declared package.
- L3: a script's `remove`, its first word bound to a receipt-proven leaf's absolute path; a command naming no proven leaf, or a receipt with no proven artifact (the pre-phase shape), gets no argv.
- `remove_tool`: post-confirm re-proof, the command (run through `run_captured`-bound runners, pnpm resolved to the executor's absolute pnpm), then the proven paths, then the receipt; a failed command or a refused path keeps the receipt.
- `run_uninstall` (CLI) and `perform_uninstall` (TUI) both remove through `remove_tool`, in `removal_order`; the CLI prints `{id}: runs {command}` before the confirm and returns `(removed, failed)`; `_run_uninstall` exits 1 on a failed removal.
- `engine.install_tool`: the declared-path snapshot before each method (never adopts a pre-existing path) and the manager receipt proof (`read_inventory_fn`, read once per call, fail closed).
- `setup.py`: both removers bind `run_captured`; the install closure binds `read_inventory`.

## Task Commits

1. **Task 1: removal_plan levels and the ordered per-tool remover** - `00aa40a` (feat, tests and implementation together)
2. **Task 2: L1 manager removal by receipt proof** - `5da27b4` (feat, tests and implementation together)
3. **Task 3: the CLI removes through remove_tool** - `fb07b62` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree; pre-commit hooks passed on each commit. No `--no-verify`, no attribution trailers. No RED commit was made on its own.

## TDD Gate Compliance

The RED runs are recorded here only. Each feat commit holds its tests with the implementation (review R1-01, ledger row 31).

### Task 1 RED (`uv run pytest tests/test_app.py -k "recipe_tool_is_removed or vendor_command_runs_before or failing_remove_deletes or vendor_remove_that_deleted or changed_argv or names_no_proven_path or drifted_previewed_path" -q --no-cov -n 0`)

```
FAILED tests/test_app.py::test_a_recipe_tool_is_removed_by_its_vendor_command_first
FAILED tests/test_app.py::test_the_vendor_command_runs_before_any_delete
FAILED tests/test_app.py::test_a_failing_remove_deletes_nothing
FAILED tests/test_app.py::test_a_vendor_remove_that_deleted_the_binary_is_a_success
FAILED tests/test_app.py::test_a_changed_argv_is_refused_like_a_changed_path
FAILED tests/test_app.py::test_a_recipe_command_that_names_no_proven_path_has_no_argv
FAILED tests/test_app.py::test_a_drifted_previewed_path_fails_the_tool_and_keeps_its_receipt
E   ImportError: cannot import name 'removal_plan' from 'installer.uninstall'
7 failed
```

### Task 1 GREEN

- Targeted selection with the two regression names (`perform_uninstall_reproves_per_tool`, `perform_uninstall_reports_a_refused_tool`): exit 0.
- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `make test`: `5353 passed, 4 skipped`, coverage 96.18%, exit 0.

### Task 2 RED (`uv run pytest tests/test_app.py -k "brew_package or another_package or cask_uv_and_pnpm or native_owned_tool_has_no_argv or already_removed_script or interrupt_after_the_vendor or old_script_receipt or empty_legacy_script_receipt or removal_order or dependent_before_its_manager" -q --no-cov -n 0`)

```
FAILED tests/test_app.py::test_cask_uv_and_pnpm_argv - AttributeError: module 'installer.app' has no attribute 'real_pnpm'
FAILED tests/test_app.py::test_removal_order_puts_dependents_first - ImportError: cannot import name 'removal_order'
FAILED tests/test_app.py::test_perform_uninstall_removes_a_dependent_before_its_manager (uv removed before the dependent ran)
3 failed, 8 passed
```

The eight passing tests are regression guards on the Task 1 code (the plan anticipated this): the L1 proof, the native owner, the already-removed script, the interrupt backstop, the old script receipt and the empty legacy receipt.

### Task 2 GREEN

- Targeted files: exit 0 (the one test that failed on a self-inflicted fixture error, a stale receipt for the second pnpm case, was fixed in the test before GREEN).
- `make validate`: exit 0.
- `make test`: `5364 passed, 4 skipped`, coverage 96.24%, exit 0.

### Task 3 RED (`uv run pytest tests/test_app.py tests/test_uninstall_e2e.py tests/test_setup.py -k "cli_previews or cli_declines or foreign_file_at_a_declared_path_survives_the_cli or only_an_argv or re_proves_after_the_confirm or dependent_before_its_manager or exits_non_zero or run_uninstall or never_adopted or bind_run_captured or already_in_the_manager or own_package_proof" -q --no-cov -n 0`)

```
FAILED tests/test_app.py::test_the_cli_previews_and_runs_the_vendor_command
FAILED tests/test_app.py::test_the_cli_declines_and_runs_nothing - TypeError
FAILED tests/test_app.py::test_a_foreign_file_at_a_declared_path_survives_the_cli_removal
FAILED tests/test_app.py::test_a_cli_tool_with_only_an_argv_is_not_nothing_to_uninstall
FAILED tests/test_app.py::test_the_cli_re_proves_after_the_confirm - TypeError
FAILED tests/test_app.py::test_the_cli_removes_a_dependent_before_its_manager
FAILED tests/test_app.py::test_a_failed_cli_removal_is_reported_and_keeps_its_receipt
FAILED tests/test_uninstall_e2e.py::test_a_package_already_in_the_manager_gets_no_receipt[repair-of-a-listed-package]
FAILED tests/test_uninstall_e2e.py::test_a_package_already_in_the_manager_gets_no_receipt[presence-miss-of-a-listed-package]
FAILED tests/test_uninstall_e2e.py::test_a_package_already_in_the_manager_gets_no_receipt[presence-miss-with-an-unreadable-inventory]
FAILED tests/test_uninstall_e2e.py::test_a_repair_keeps_the_installers_own_package_proof
FAILED tests/test_uninstall_e2e.py::test_a_declared_path_present_before_the_install_is_never_adopted
FAILED tests/test_setup.py::test_both_removers_bind_run_captured - KeyError
FAILED tests/test_setup.py::test_a_failed_cli_removal_exits_non_zero - AssertionError
14 failed
```

### Task 3 GREEN

- Targeted files: exit 0 after the implementation. Two regressions surfaced during GREEN and were fixed in the implementation: the crash-before-receipt test (`test_crash_between_method_and_receipt_leaves_no_receipt`, unchanged) caught the snapshot placement (deviation 1), and the TUI route recorder needed the new keyword (deviation 2). The three manager engine tests were updated as listed under Changed Tests.
- `make validate`: exit 0 after the lint and type fixes listed under Deviations.
- `make test`: `5386 passed, 4 skipped`, coverage 96.26%, exit 0. The every-kind lifecycle test reports 8 passed.

## Test counts (floors: measured at task start, plus delta)

| File | Start | End | Delta |
|---|---|---|---|
| tests/test_app.py | 144 | 169 | +25 (T1 +7, T2 +11, T3 +7) |
| tests/test_uninstall.py | 103 | 103 | 0 (the Task 2 tests landed in test_app.py, see Deviations) |
| tests/test_uninstall_e2e.py | 5 | 18 | +13 (T3: 3 parametrized, 1, 1 and 8 every-kind cases) |
| tests/test_setup.py | 152 | 154 | +2 (T3) |
| tests/test_engine.py | 80 | 80 | 0 (three existing tests updated, see Changed Tests) |
| tests/test_receipts.py | 129 | 129 | 0 |

Full suite: 5346 passed at the wave-2 ledger figure (not re-measured at this base) -> 5353 after Task 1 -> 5364 after Task 2 -> 5386 after Task 3 (+40 = 7 + 11 + 22). Every floor is met.

## Changed or Deleted Existing Tests

No test was deleted. Each change below is required by the plan or the signature change it implements.

| Test | Change | Reason |
|---|---|---|
| `tests/test_app.py::test_perform_uninstall_a_planning_error_does_not_stop_the_rest` | The monkeypatched seam moved from `app.plan_removal` to `app.removal_plan`; assertions unchanged | `remove_tool` plans through `removal_plan` (the post-confirm proof, review R1-10) |
| `tests/test_app.py` (16 `perform_uninstall` calls, plus `_no_removal_runner` in each new helper) | `runner=_no_removal_runner` added | `perform_uninstall` gains a required `runner` (Task 1) |
| `tests/test_app.py` (29 direct `run_uninstall` calls) and `_UninstallKwargs` / `_uninstall_kwargs` | `runner` key added; call sites that splat the helper inherit it | `run_uninstall` gains a required `runner` (Task 3) |
| `tests/test_app.py` and `tests/test_uninstall.py` (`removed = run_uninstall(...)` and `first`/`second`) | `removed, _failed = run_uninstall(...)` (and `first, _ =`) | `run_uninstall` returns `(removed, failed)` (review R1-24) |
| `tests/test_uninstall.py` | `_no_removal_runner` helper and one `runner=` kwarg | as above |
| `tests/test_uninstall_e2e.py` (2 `perform_uninstall` calls) | `runner=_no_removal_runner` | Task 1 |
| `tests/test_setup.py` (5 `fake_run_uninstall`) | Return `([], ())` and the `tuple[list[Path], tuple[str, ...]]` annotation | `_run_uninstall` unpacks the new return |
| `tests/test_setup.py::_recording_install` | Accepts and discards `read_inventory_fn` | The TUI route recorder mirrors `install_tool`'s keyword surface (the route test failed without it) |
| `tests/test_setup.py::test_the_interactive_uninstall_view_forwards_the_same_daemon_instance` | One assertion added: the forwarded `runner` is `run_captured` | Review R2-04: the TUI remover binds `run_captured` |
| `tests/test_engine.py::test_receipt_per_kind[brew, cask, uv-tool, node]`, `test_manager_smoke_status_is_recorded[True/False]`, `test_receipt_write_failure_keeps_installed` | `read_inventory_fn=_empty_inventory` added; assertions unchanged | Review R3-02: a manager receipt needs a readable inventory that lists no package (the plan's three named tests) |

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug] Engine snapshot raised outside the guard.** `install_tool` called `receipts.preexisting_paths(method)` before the method ran, outside the `try`. `artifact_paths` can raise OSError, which `record` used to contain. `test_crash_between_method_and_receipt_leaves_no_receipt` caught it. Fix: an OSError while snapshotting becomes `preexisting=None`, so `record` fails closed inside its own guard. Committed in `fb07b62`.

**2. [Rule 1 - Bug] TUI route recorder rejected the new keyword.** `_recording_install` in tests/test_setup.py did not accept `read_inventory_fn`, so the five TUI route pilots recorded nothing. Fix: the recorder accepts and discards the keyword, as the other install keywords are.

**3. [Rule 1 - Bug] Test fixture: second pnpm case started with a retired receipt.** `test_cask_uv_and_pnpm_argv` ran the second node case after the first had removed its receipt. Fix: the test re-records the receipt before the second case. Test-only.

**4. [Lint and type] Import order, docstring line length, pyright `reportUnknown*` on untyped `params` reads.** Fixed with isort (`ruff check --fix --select I001`), `ruff format`, shorter docstrings, `cast(list[object], ...)` (the repo's own convention) and a typed `_reads` factory for the e2e inventory readers. No suppression comment was added (`git diff` added-line count for `type: ignore|pyright: ignore|noqa|nosec` is 0).

**5. [Lint] `RemovalLevel` and `method_package` ordering.** `RemovalLevel` is defined above `RemovalPlan` (the annotation is evaluated at class creation). `method_package` sits after `class Method` in `installer/model.py` (a forward reference raised NameError beside `METHOD_PARAMS`). `KIND_PACKAGE_PARAM` sits beside `METHOD_PARAMS`, as planned.

### Plan deviations (recorded, not auto-fixed)

**1. The recipe drift variant replaces the leaf with a symlink, not new bytes.** The plan asks for a leaf "rewritten after the preview". Script leaves are proven by type only (ledger Q3, locked: a hash proof would make auto-updating tools unremovable), so a byte rewrite is not drift by design. The test replaces the leaf with a symlink (a type change), which the proof does refuse. Test expectation only.

**2. Task 2 tests live in tests/test_app.py, not tests/test_uninstall.py.** The helpers they share (`_vend_recorded`, `_perform`, `_manager_tool`) are there. All eleven named tests exist under their named functions.

**3. The every-kind test fakes the executor.** `test_every_receipt_kind_installs_and_removes_in_both_directions` drives `install_tool` and `perform_uninstall` through the real engine, receipt and remover in a scratch HOME. The download, app and script executors (network) are replaced by `engine._perform`, which plants the method's `artifact_paths` (opt dirs and links, app bundles, script leaves) or records the manager's install command. The test was written after the implementation existed, so its first run was GREEN; it is an acceptance test, not a RED test.

**4. `test_both_removers_bind_run_captured` covers the CLI remover in its own test; the TUI remover's runner is asserted in the existing interactive-view test.** Both are the plan's R2-04 check.

**5. `_plant` uses the first `dir` artifact for every link.** Every download method declares exactly one opt dir and one link, and an app declares one bundle and one cli link, so this holds for the eight kinds tested.

### Known gap (open, not fixed here)

**The TUI decision carries no argv yet.** `wizard_app.py` `_apply_removal` builds `UninstallDecision` from preview rows, which hold paths only, so `argv` is empty there. A recipe tool removed from the TUI therefore skips its vendor `remove` and removes its proven paths and receipt directly, and the TUI never shows the command. The CLI and the `perform_uninstall` path do run the command. Today no registry script declares a `remove` that a TUI user can reach (22-08 adds those), so the gap is latent. It must be closed before 22-08's vendor removes ship to a TUI user: the uninstall view has to publish each tool's `RemovalPlan.argv` into its row and the decision has to carry it. That wiring belongs to the view plans (22-07 and 22-09), which own the TUI preview.

## Threat Model Coverage

| Threat | Disposition | Where it is handled |
|---|---|---|
| T-22-13 L1 manager uninstall by name | mitigate | `_manager_argv` needs the receipt kind and package to match a declared method; `test_a_brew_package_without_a_receipt_runs_nothing`, `test_a_receipt_for_another_package_is_no_proof` |
| T-22-14 deleting after a failed vendor remove | mitigate | Step 1 failure returns before any delete; `test_a_failing_remove_deletes_nothing` |
| T-22-15 plan changed between preview and confirm | mitigate | `remove_tool` re-plans with `verify=True` and refuses the whole tool; `test_a_changed_argv_is_refused_like_a_changed_path`, `test_the_cli_re_proves_after_the_confirm` |
| T-22-35 empty legacy script receipt authorizing the vendor remove | mitigate | L3 needs a proven artifact; `test_an_empty_legacy_script_receipt_never_runs_remove` |
| T-22-36 manager removed before its dependents | mitigate | `removal_order` in both removers; `test_perform_uninstall_removes_a_dependent_before_its_manager`, `test_the_cli_removes_a_dependent_before_its_manager` |
| T-22-37 failed CLI removal reported as success | mitigate | `run_uninstall` returns the failed ids; `test_a_failed_cli_removal_is_reported_and_keeps_its_receipt`, `test_a_failed_cli_removal_exits_non_zero` |
| T-22-16 removal child waits on a prompt or loses its error | mitigate | Both removers bind `run_captured`; `test_both_removers_bind_run_captured` |
| T-22-46 a drifted previewed path reported as removed | mitigate | Step 2 re-proves the previewed paths; `test_a_drifted_previewed_path_fails_the_tool_and_keeps_its_receipt` |
| T-22-47 a PATH copy of a recipe's command | mitigate | The argv's first word is bound to a proven leaf's absolute path; `test_a_recipe_command_that_names_no_proven_path_has_no_argv` |
| T-22-49 a manager receipt for a package the user already had | mitigate | `_package_already_there` with the inventory read before the method; `test_a_package_already_in_the_manager_gets_no_receipt`, `test_a_repair_keeps_the_installers_own_package_proof` |
| T-22-SC package installs | accept | This plan installs no package |

## Acceptance Greps (run on the final tree)

| Check | Expected | Actual |
|---|---|---|
| `runner=run_captured` in setup.py | at least 3 | 3 |
| `run_command` outside comments in setup.py | 0 | 0 |
| `preexisting=` in installer/engine.py | 1 | 1 |
| `preexisting_paths(` in installer/engine.py | 1 | 1 |
| `read_inventory_fn` in installer/engine.py | at least 2 | 3 |
| `read_inventory_fn=read_inventory` in setup.py | 1 | 1 |
| `remove_tool(` inside `run_uninstall` | at least 1 | 1 |
| every-kind test | 8 passed | 8 passed |
| suppression comments added in the plan diff | 0 | 0 |
| `make validate` on the final tree | exit 0 | exit 0 |
| `make test` on the final tree | exit 0 | exit 0 (5386 passed, 4 skipped) |

## Not Checked

- `make e2e` (container install, uninstall, reinstall of every registry tool) was not run; it is the orchestrator's phase-close gate.
- The TUI uninstall view was not driven interactively; the TUI decision gap above is a reading of `_apply_removal`, not a run.
- The real download, app and script executors were not run (no network in this worktree); the every-kind test fakes them as described.
- The real `brew`, `uv` and `pnpm` binaries were never executed: every manager command went through a recording runner.

## Self-Check: PASSED

All twelve files named under Key Files and in this SUMMARY exist in the worktree. Commits `00aa40a`, `5da27b4` and `fb07b62` are ancestors of HEAD.

## Next Phase Readiness

- 22-07 (the uninstall view and hint templates) reads `removal_plan` and `MANAGER_UNINSTALL_ARGV` (its `_REMOVAL_COMMANDS` derive from the table, as its plan states).
- 22-09 reads `config_targets` and `RemovalPlan.config` for the config re-check and must carry `RemovalPlan.argv` into the TUI decision (the gap above).
- 22-13 consumes the failed-id exit code of the CLI removal (`_run_uninstall`).
- No STATE.md or ROADMAP.md change was made by this plan.
