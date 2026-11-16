---
phase: 22-method-lifecycle-contract
plan: "07"
subsystem: uninstall-view
tags: [uninstall, removal-level, native-hint, sdkman, l3-recipe, interrupted-removal, tdd]

commits: 3
plan_head_before: 705385ccd9bf60ec6acfc4bb6005b43ae5102b71
plan_head_after: 687eaa8a326b117aea652b62b2b269a2929d815f

requires:
  - phase: 22-04
    provides: "install ladder and prefix_writable (the pass's unwritable prefixes)"
  - phase: 22-06
    provides: "removal_plan (level, argv, config, hint), MANAGER_UNINSTALL_ARGV, remove_tool with the post-confirm re-proof"
provides:
  - "The refresh pass stores removal_plan(tool, bin, hint=removal_hint(ownership, cmd, version=...)) in ToolState.removable"
  - "uninstall_group reads the plan (paths or argv); uninstall_label names the L1 manager; uninstall_detail reads the stored hint and builds the L1 and L3 sentences"
  - "manager_kind_label(kind); removal_hint(..., version=None); native _REMOVAL_COMMANDS set to None"
  - "_UninstallEntry.argv; the What-gets-removed cell by level; UninstallDecision.argv from _apply_removal (closes the 22-06 TUI gap)"
affects: [22-08, 22-09]

actuals:
  tokens: 10800     # chars/4 over the realized diff (43216 bytes of `git diff 705385c..687eaa8`)
  tasks: 3
  commits: 3        # MEASURED: git rev-list --count 705385c..HEAD (before this SUMMARY commit)

tech-stack:
  added: []
  patterns:
    - "The refresh pass decides and stores the removal hint once; the Uninstall projection only reads it (never a second probe or recomputation)"
    - "A native owner names its package and never carries a command; L1 commands are derived from MANAGER_UNINSTALL_ARGV so a hint and the removal run one command"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - installer/ownership.py
    - installer/wizard_app.py
    - tests/test_version_status.py
    - tests/test_wizard_app.py
    - tests/test_ownership.py
    - tests/test_setup.py
    - tests/state_doubles.py

key-decisions:
  - "The hint is computed in the refresh pass from the ownership and the SDKMAN version it already read; uninstall_detail reads state.removable.hint and never calls removal_hint"
  - "L1 detail: `installed by this installer through {label}: receipt matches — runs `{command}`` with no active-copy suffix (the label is already the manager)"
  - "L3 detail: RECEIPT_PROOF_NOTE, plus ` — runs `{command}`, then deletes the proven paths` only when the plan has an argv"
  - "A receipt whose recorded file or link no longer matches counts as presence for health in the pass (R1-11): an interrupted vendor removal reads BROKEN; a receipt with nothing left is retired (G10) and the tool reads MISSING; both publish level none with no argv"
  - "Native _REMOVAL_COMMANDS values are None (keys kept for the exhaustiveness gate); native rows with a package read the os-package sentence; SDKMAN fills `<version>` from the pass or says it was not read"

requirements-completed: [LIFE-03, LIFE-01]

coverage:
  - id: D6-1
    description: "An L1 brew/cask/uv/pnpm row is removable, names its manager and command, and its removal carries the argv the row showed"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_an_l1_brew_row_is_removable_and_names_its_command"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_the_pass_publishes_removal_plan_levels"
        status: pass
    human_judgment: false
  - id: D6-2
    description: "Native owners name the package and carry no command; no native removal command exists"
    requirement: "LIFE-03"
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_a_native_owner_row_names_the_package_and_no_command"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_native_removal_commands_are_gone"
        status: pass
    human_judgment: false
  - id: D6-3
    description: "SDKMAN's hint carries the version the pass read, without a second probe"
    requirement: "LIFE-03"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_the_pass_fills_the_sdkman_version_from_its_own_status"
        status: pass
      - kind: unit
        ref: "tests/test_ownership.py#test_the_sdkman_hint_carries_the_installed_version"
        status: pass
    human_judgment: false
  - id: D6-4
    description: "L3 rows name the vendor command then the proven paths; a missing tool keeps unproven leftovers; a foreign file stays listed"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_an_l3_row_shows_the_vendor_command_then_the_paths"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_missing_tool_keeps_its_unproven_leftovers"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_a_foreign_file_stays_listed_before_and_after_the_removal"
        status: pass
    human_judgment: false
  - id: D6-5
    description: "Every Uninstall row level matches the UI-SPEC copy byte for byte"
    requirement: "LIFE-03"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_l1_l2_l3_and_hint_rows_match_the_ui_spec_table"
        status: pass
    human_judgment: false
  - id: D6-6
    description: "An interrupted recipe removal is never removable on the next refresh pass (BROKEN, or retired and MISSING)"
    requirement: "LIFE-01"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_an_interrupted_recipe_removal_is_never_removable_on_the_next_pass"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_an_interrupted_recipe_removal_with_nothing_left_retires_its_receipt"
        status: pass
    human_judgment: false
---

# Phase 22 Plan 07: The Uninstall view shows each removal level, and the TUI removes with the argv it showed

**The refresh pass stores each tool's removal plan with its hint; the Uninstall view groups by level, names an L1 manager and its command, shows an L3 vendor command before the proven paths, names native packages without a command, and fills the SDKMAN version from the pass. An interrupted removal reads BROKEN, not removable.**

## Performance

- **Duration:** not recorded (the plan start timestamp was not captured in this run)
- **Tasks:** 3 of 3, one green commit each
- **Files modified:** 8

## Accomplishments

- The pass stores `removal_plan(..., hint=removal_hint(ownership, cmd, version=status.installed))` in `ToolState.removable` for both the skill-pack and the other-tool branches (the two former `plan_removal` calls are gone).
- `uninstall_group` counts a plan with an argv as removable, so an L1 plan (argv, no paths) is in `removable here`.
- L1 row: `Installed via` = `Homebrew` / `cask` label / `uv` / `pnpm` (`manager_kind_label`), `What gets removed` = `brew uninstall gh`, detail `installed by this installer through Homebrew: receipt matches — runs `brew uninstall gh``.
- L3 row: `What gets removed` = `{command}, {paths}` truncated at 40 cells; detail `installed by this installer: receipt matches — runs `{command}`, then deletes the proven paths`; without a `remove`, the proof sentence only.
- A missing tool keeps its unproven leftovers: `not installed · remove it yourself: {paths}`; a foreign file stays listed.
- `_UninstallEntry.argv` and `_apply_removal` passes `UninstallDecision(argv={id: entry.argv})`, so a TUI-confirmed L1 or L3 removal hands `remove_tool` the argv the row showed. This closes the 22-06 "Known gap (TUI decision carries no argv)".
- Native `_REMOVAL_COMMANDS` (dnf, apt, pacman, rpm-ostree) are `None`; a native row with a package reads `managed by {label} — this installer will not remove the package {package}`; the package-less sentence stands when unknown.
- The brew, cask, pnpm and uv command templates are derived from `uninstall.MANAGER_UNINSTALL_ARGV` (one source for the hint and the L1 argv).
- `removal_hint(..., version=None)`: SDKMAN fills `<version>` from the pass, or says `the installed version was not read`.
- The pass's receipt drift counts as presence for health: `present=present or bool(broken)` in `_pass` (R1-11).

## Task Commits

1. **Task 1: Uninstall reads removal levels from the published plan** - `066118c` (feat, tests and implementation together)
2. **Task 2: package-naming native hints and the SDKMAN version hint** - `d864b62` (feat, tests and implementation together)
3. **Task 3: L3 row copy and visible leftovers** - `687eaa8` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree. Pre-commit hooks passed on each commit. No `--no-verify`, no attribution trailers, no RED-only commit.

## TDD Gate Compliance

The RED runs are recorded here only. Each feat commit holds its tests with the implementation (review R1-01, ledger row 31).

### Task 1 RED (`uv run pytest tests/test_wizard_app.py tests/test_version_status.py -k "l1_brew_row or uninstall_group_reads_the_level or publishes_removal_plan_levels" -q --no-cov -n 0`)

```
FAILED tests/test_wizard_app.py::test_an_l1_brew_row_is_removable_and_names_its_command
FAILED tests/test_version_status.py::test_uninstall_group_reads_the_level[plan0-removable]
FAILED tests/test_version_status.py::test_the_pass_publishes_removal_plan_levels
E   AssertionError: assert '—' == 'brew uninstall gh'         (the What gets removed cell)
E   AssertionError: assert <UninstallState.MANAGED: 'managed'> is <UninstallState.REMOVABLE: 'removable'>
E   AssertionError: assert 'none' == 'manager'
```
The five passing cases (the paths-only shapes, which must stay removable) are regression guards, not RED.

### Task 1 GREEN

- Targeted selection (the three named tests and their parametrized cases): 8 passed, exit 0.
- Broader set `test_wizard_app test_version_status test_uninstall_e2e test_screen_family test_layout_80x20 -n auto`: exit 0.
- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture; two E501 lines fixed before the commit).
- `make test`: `5409 passed, 4 skipped in 51.83s`, coverage 96.27%, exit 0.

### Task 2 RED (`uv run pytest tests/test_ownership.py tests/test_version_status.py tests/test_setup.py -k "native_owner_row or native_removal_commands or sdkman_hint or fills_the_sdkman_version or reads_the_plan_hint or each_managers_own_command or uses_the_shared_table or method_package_reads_the_kind_param or build_app_uninstall_detail" -q --no-cov -n 0`)

```
FAILED tests/test_ownership.py::test_a_native_owner_row_names_the_package_and_no_command[dnf-ripgrep]   (and apt, pacman, rpm-ostree, dnf-glab)
FAILED tests/test_ownership.py::test_native_removal_commands_are_gone - AssertionError: 'dnf remove {package}' is None
FAILED tests/test_ownership.py::test_the_sdkman_hint_carries_the_installed_version - TypeError: removal_hint() got an unexpected keyword argument 'version'
FAILED tests/test_ownership.py::test_method_removal_command_uses_the_shared_table[method3-None] - 'dnf remove glab' == None
FAILED tests/test_ownership.py::test_method_package_reads_the_kind_param - AssertionError: 'dnf remove ripgrep' == None
FAILED tests/test_version_status.py::test_uninstall_detail_reads_the_plan_hint
E   AssertionError: assert 'managed by H...formula name)' == 'managed by H...tall ripgrep`'
FAILED tests/test_version_status.py::test_the_pass_fills_the_sdkman_version_from_its_own_status
FAILED tests/test_setup.py::test_build_app_uninstall_detail_changes_when_the_published_state_changes
FAILED tests/test_setup.py::test_build_app_uninstall_detail_reverts_after_the_service_is_invalidated
E   AssertionError: assert 'managed by dnf — `dnf remove ripgrep`' == 'managed by dnf — this installer will not remove the package ripgrep'
13 failed
```
The `pnpm` and `uv` rows of `test_removal_hint_names_each_managers_own_command` pass as guards. The first `test_uninstall_detail_reads_the_plan_hint` run failed on the active-path suffix, not on the hint read; the test was made to set its own package and active path, and the RED above is the corrected one.

### Task 2 GREEN

- Targeted selection: 20 passed, exit 0.
- Broader set `test_ownership test_version_status test_engine test_wizard_app test_setup -n auto`: exit 0.
- `make validate`: exit 0 (after two pyright fixes in the new tests: an `Optional` narrowing and a typed `resolve_owner` in place of a lambda; no suppression).
- `make test`: `5410 passed, 4 skipped in 45.52s`, exit 0.

### Task 3 RED (`uv run pytest tests/test_wizard_app.py tests/test_version_status.py -k "l3_row or missing_tool_keeps or foreign_file_stays_listed or match_the_ui_spec_table or interrupted_recipe_removal" -q --no-cov -n 0`)

```
FAILED tests/test_wizard_app.py::test_an_l3_row_shows_the_vendor_command_then_the_paths
E   AssertionError: assert 'installed in…emovable here' == 'installed by… proven paths'   (LAYOUT_PROOF_NOTE, no L3 copy)
FAILED tests/test_version_status.py::test_l1_l2_l3_and_hint_rows_match_the_ui_spec_table[L3-with-remove]
E   AssertionError: assert 'installed by…ceipt matches' == 'installed by… proven paths'
FAILED tests/test_version_status.py::test_l1_l2_l3_and_hint_rows_match_the_ui_spec_table[missing-with-leftovers]
E   AssertionError: assert 'not installed' == 'not installe…urself: /x/rg'
FAILED tests/test_version_status.py::test_a_missing_tool_keeps_its_unproven_leftovers
FAILED tests/test_version_status.py::test_a_foreign_file_stays_listed_before_and_after_the_removal
E   AssertionError: assert 'not installed' == 'not installe…f: /x/foreign'
FAILED tests/test_version_status.py::test_an_interrupted_recipe_removal_is_never_removable_on_the_next_pass
6 failed
```
The interrupted-removal test was first written without `HOME` set. Its script paths expand through `$HOME`, so no leaf was recorded and the RED reason was a fixture error (`MISSING`, `no manager claimed the tool`). The fixture now sets `HOME` as `_vend_recorded` does. The RED reason was then confirmed by reverting the one line in `_pass` (`present=present or bool(broken)` → `present=present`): the test fails with `Health.MISSING is Health.BROKEN`. The line was restored before the commit.

The other passing cases are regression guards: the L1, L2, L3-without-remove, unreceipted-brew, native (both), SDKMAN (both) and Volta rows, and `test_an_l3_row_without_a_remove_lists_its_paths`.

### Task 3 GREEN

- Targeted selection: 17 passed, exit 0. Breakdown: the pilot (1), the table (11, the plan's "at least 11"), `test_an_l3_row_without_a_remove_lists_its_paths` (1), the missing-tool test (1), the foreign-file test (1), the interrupted-removal pair (2, the plan's "2 passed").
- Broader set `test_wizard_app test_version_status test_layout_80x20 test_screen_family -n auto`: exit 0.
- `make validate` (first run): exit 0.
- `make test` (first run): `5427 passed, 4 skipped in 51.37s`, exit 0.
- The L3 pilot was then extended to confirm the removal (see Deviations, item 5). Final `make validate`: exit 0. Final `make test`: `5427 passed, 4 skipped in 51.27s`, coverage 96.28%, exit 0. Both run on the committed tree.

## Test counts (floors: measured at task start, plus delta)

Start: the full suite was not re-measured at `705385c`; the RUN-LEDGER wave-3 figure is `5401 passed / 4 skipped` (e28aac1). Per-file counts below were measured at start.

| File | Start | End | Delta |
|---|---|---|---|
| tests/test_version_status.py | 236 | 261 | +25 (T1 +7: 6 level params, 1 pass; T2 +2; T3 +16: 11 table, 1 without-remove, 1 missing, 1 foreign, 2 interrupted) |
| tests/test_ownership.py | 212 | 211 | −1 (T2 +7: 5 native params, native-command gate, SDKMAN hint; −8: 4 dropped `removal_hint_names_each_managers_own_command` rows and 4 native cases no longer collected by `removal_hint_carries_a_command_only_when_package_is_resolved`, see Changed Tests) |
| tests/test_wizard_app.py | 320 | 322 | +2 (T1 L1 pilot, T3 L3 pilot) |
| tests/test_setup.py | 154 | 154 | 0 (two assertions changed) |
| tests/test_uninstall_e2e.py | 18 | 18 | 0 |
| tests/test_engine.py | 80 | 80 | 0 |
| tests/test_layout_80x20.py | 20 | 20 | 0 |
| tests/test_screen_family.py | 232 | 232 | 0 |
| tests/test_uninstall.py | 103 | 103 | 0 |
| tests/test_app.py | 169 | 169 | 0 |

Full suite: 5401 (ledger) → 5409 (T1) → 5410 (T2) → 5427 (T3). Every per-file floor is met, and the full-suite delta is consistent with the per-file deltas (+8, +1, +17).

## Changed or Deleted Existing Tests

No test was deleted. Each change is required by the plan's design (native commands gone, the projection reads the stored hint).

| Test | Change | Reason |
|---|---|---|
| `tests/test_ownership.py::test_removal_hint_names_each_managers_own_command` | The dnf, apt, pacman and rpm-ostree rows left the parametrization; pnpm and uv kept | R1-12: those rows moved to `test_a_native_owner_row_names_the_package_and_no_command`, which expects the package sentence |
| `tests/test_ownership.py::test_method_removal_command_uses_the_shared_table` | The dnf/glab row expects `None` (was `dnf remove glab`) | R1-12, D-08; `glab` is covered by the native-owner test |
| `tests/test_ownership.py::test_method_package_reads_the_kind_param` (`_FROZEN_REMOVAL`) | Native kinds expect `None`; the type allows `str \| None` | R1-12, D-08 |
| `tests/test_ownership.py::test_removal_hint_carries_a_command_only_when_package_is_resolved` | Not edited. Its parametrization over `_COMMAND_OWNERS` no longer collects dnf, apt, pacman, rpm-ostree (their command is gone), so 4 cases silently drop | Not in the plan's list; recorded here. The native property is covered by the new native-owner test |
| `tests/test_setup.py::test_build_app_uninstall_detail_changes_when_the_published_state_changes` and `…_reverts_after_the_service_is_invalidated` | `dnf remove ripgrep` → `this installer will not remove the package ripgrep` | R1-12; still proves the repaint |
| `tests/test_version_status.py::_uninstall_state` | Stores the hint the pass would store when the fixture gives none | The projection now reads the stored hint; no assertion weakened |
| `tests/state_doubles.py::pass_state` | Stores `removal_hint(owner, cmd, version=…)` in the plan | Same reason: a built state must carry the hint the pass stores. Not in the plan's files list; recorded here |

The Task 3 concern "existing tests that encoded MISSING for a partly-gone receipt": the full suite passed unchanged on that behaviour, so none was rewritten.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug] Test doubles had to store the hint.** `uninstall_detail` now reads `state.removable.hint`, so `pass_state` and `_uninstall_state` (the test helpers that stand in for the pass) must store `removal_hint`. Without it, every existing Uninstall detail test built from a double lost its hint. Files: `tests/state_doubles.py` (not in the plan's list), `tests/test_version_status.py`.

**2. [Rule 3 - Blocking] Lint and type fixes in the new tests.** E501 on two long lines (Task 1), a pyright `Optional` narrowing and a pyright-unknown lambda in the SDKMAN pass test (Task 2). All fixed in code; no `type: ignore`, `noqa`, `nosec` or `pyright: ignore` was added (`git diff 705385c HEAD` added-line grep: 0).

**3. Interrupted-removal test split.** The plan describes one test with two phases; its acceptance counts "2 passed". It is two tests (`test_an_interrupted_recipe_removal_is_never_removable_on_the_next_pass` for BROKEN, `test_an_interrupted_recipe_removal_with_nothing_left_retires_its_receipt` for MISSING and retirement) sharing a fixture `_interrupted_recipe`.

**4. Foreign-file test is unit-level.** `test_a_foreign_file_stays_listed_before_and_after_the_removal` asserts `uninstall_detail` before and after (the same yourself path, MISSING after) rather than driving a pilot through the fake remover. The row-level L3 pilot covers the cell and the confirm.

**5. The L3 pilot confirms the removal.** The 22-06 handoff requires that a TUI-confirmed L3 removal runs the argv the row showed. The first L3 pilot only displayed the row; `test_an_l3_row_shows_the_vendor_command_then_the_paths` now also presses space, enter, enter and asserts the decision's `argv == {"vend": argv}` and `paths == {"vend": (leaf,)}`. This was added after the first Task 3 GREEN and before the Task 3 commit; `make validate` and `make test` were rerun on that tree.

**6. `uninstall_detail` keeps an unused `tool` parameter.** The managed branch no longer calls `removal_hint`, so `tool` is unused. The signature and all callers are unchanged; the ruff rule set does not enable unused-argument checks, and validate is green.

### Plan deviations (recorded, not auto-fixed)

None.

## Threat Model Coverage

| Threat | Disposition | Where it is handled |
|---|---|---|
| T-22-17 native removal hint elevates to a command | mitigate | Native `_REMOVAL_COMMANDS` are `None`; `test_a_native_owner_row_names_the_package_and_no_command` (no backtick, argv `()` via the package-only sentence), `test_native_removal_commands_are_gone` |
| T-22-18 markup in package names, paths and commands | mitigate | Unchanged house path: detail through `sanitize_log_line` in `_tool_entry`, cells as `Text`, `detail_is_markup=False` |
| T-22-38 interrupted removal published as removable | mitigate | `_pass` keeps a receipt's drifted tool BROKEN; retired receipt reads MISSING; both level `none`, argv `()` (`test_an_interrupted_recipe_removal_*`, mutation-checked) |
| T-22-SC package installs | accept | This plan installs no package |

## Known Stubs

None.

## Threat Flags

None: no new network endpoint, auth path, file access pattern or trust-boundary schema change.

## Not Checked

- `make e2e` (container install, uninstall, reinstall) was not run; it is the orchestrator's phase-close gate.
- The TUI was not driven interactively; the coverage is the pilots at `size=(80, 20)`.
- The Task 2 plan line "a state built on it shows that detail and its plan argv is `()`" was covered at the hint-string level (`test_a_native_owner_row…`) and through the pass test; no state-level argv assertion was added for native rows.
- Estimate calibration: the plan estimated 105000 tokens; the measured chars/4 over the realized diff is 10800 (43216 bytes). Recorded as measured, not rounded toward the estimate.
- The start-of-plan full-suite count is the RUN-LEDGER figure (5401), not re-measured at `705385c`.
- `.planning/WINDOWS.md` was not appended: this plan left no stub, skipped test or unrun `<verify>`.
- STATE.md and ROADMAP.md were not modified (orchestrator updates them after merge).

## Self-Check: PASSED

Verified after writing: this SUMMARY exists in the worktree, and commits `066118c`, `d864b62` and `687eaa8` are ancestors of HEAD.

## Next Phase Readiness

- 22-08 (vendor removes for registry scripts) reads `RemovalPlan.level`/`argv` through the same projection; the TUI now carries argv for every L1 and L3 row.
- 22-09 reads `RemovalPlan.config` and the stored `hint`; its TUI decision path inherits `_apply_removal`'s argv.
- No STATE.md or ROADMAP.md change was made by this plan.
