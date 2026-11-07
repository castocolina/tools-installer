---
phase: 23-configuration-as-a-lifecycle-step
plan: "01"
subsystem: installer
tags: [postinstall, hooks, receipts, host-presence, testing]
status: complete

requires:
  - phase: 22-method-lifecycle-contract
    provides: the receipt model and the method lifecycle that the hook receipts sit beside
provides:
  - one host list for every hook (present_hosts reading skill_lifecycle.present_harnesses)
  - codegraph hook registers only present, supported, unrecorded hosts and records them in receipt.hooks
  - receipts.record keeps previous.hooks; receipts.record_hooks merges hosts under the write lock
  - register_hooks refuses a targeted registration without a receipt
  - rtk postinstall hook removed (catalog entry kept)
  - catalog tools parameter removed from install_tool, the session install protocol, perform_update and UpdateService
  - test sandbox that answers no hosts, re-roots setup.py home constants, and guards .zshenv, environment.d and the config ledger
affects: [23-05 (unregister builders, herdr, tealdeer on the HookPair table), 23-07 (drift and new-host sweep), 23-08 (removal)]

actuals:
  tokens: 29634        # chars/4 over `git diff 97b9e0b HEAD` (118534 chars)
  tasks: 2
  commits: 2           # MEASURED: git rev-list --count 97b9e0b..HEAD
plan_head_before: 97b9e0b418d4947f60e375e5613978007dfcc10b
plan_head_after: 0ac2979

tech-stack:
  added: []
  patterns:
    - "HookPair(targets, register, unregister): a closed table of hook pairs keyed by name; targets None marks a host-independent hook"
    - "hosts read at each dispatch (register_hooks hosts=None -> present_hosts()), after the method's PATH prepend"

key-files:
  created: []
  modified:
    - installer/postinstall.py
    - installer/receipts.py
    - installer/engine.py
    - installer/session.py
    - installer/update.py
    - installer/model.py
    - installer/registry.toml
    - setup.py
    - tests/conftest.py
    - tests/test_sandbox.py
    - tests/test_postinstall.py
    - tests/test_engine.py
    - tests/test_receipts.py
    - tests/test_update.py
    - tests/test_registry.py
    - tests/test_session.py
    - tests/test_catalog_tui.py
    - tests/test_execute_screen.py
    - tests/test_wizard_app.py
    - tests/test_app.py
    - tests/test_ownership.py
    - tests/state_doubles.py

key-decisions:
  - "Hooks take hosts from present_harnesses through one reader (present_hosts); present_agent_hosts and _AGENT_HOST_IDS are deleted (D-01, CONF-03)"
  - "A targeted hook with no install receipt runs nothing and returns 'hook not registered: no install receipt to record it in' (review R1-08)"
  - "receipts.record carries previous.hooks forward on every re-record (research Pitfall 1)"
  - "Target maps are keyed by harness id; receipt.hooks stores harness ids; HOST_CATALOG_IDS maps harness to catalog id for display (UI-SPEC U10)"
  - "codegraph's binary resolves through _resolve_binary (brew: shutil.which, then BREW_BIN_DIRS; else bin_dir), replacing the bin_dir-only path"
  - "The generic setup-path re-rooting skips paths inside the checkout: this checkout sits under the real HOME, and setup._REGISTRY is package data (deviation below)"

patterns-established:
  - "Shortcut comment at the dispatch: a host removed by hand is registered again while its marker dir remains (SPEC known limit)"

requirements-completed: [CONF-01, CONF-03]

# Plan-level status against the requirements
# CONF-03 complete: one host list, the second table is deleted.
# CONF-01 register half complete (codegraph pair, receipt.hooks). The unregister half and the herdr/tealdeer pairs are 23-05 and 23-08.
# CONF-02 not in this plan: the new-host sweep is 23-07.
---

# Phase 23 Plan 01: Hook hosts from one list, recorded in the receipt — Summary

**Hook hosts come from one list (`present_harnesses`); codegraph registers only present, supported, unrecorded hosts and records them in `receipt.hooks`; every re-record keeps them; rtk's hook is gone; the catalog `tools` parameter leaves the install and update path.**

## Performance

- **Tasks:** 2 (Task 1 TDD; Task 2 mechanical refactor)
- **Commits:** 2 (`05c95a4`, `0ac2979`) — measured against base `97b9e0b`
- **Test counts:** collected 5589 at start → 5569 after Task 1 → 5570 after Task 2 (net −19).
  - Task 1 gate: `make validate` exit 0; `make test` 5565 passed, 4 skipped, coverage 96.33%.
  - Task 2 gate: `make validate` exit 0; `make test` 5566 passed, 4 skipped, coverage 96.33%.

## Accomplishments

- `installer/postinstall.py`: `HookOutcome`, `HookPair`, `HOST_CATALOG_IDS`, `present_hosts()`, `_resolve_binary(method, cmd)`, the codegraph pair over a harness-keyed target map, `run_postinstall(name, method, runner, hosts)`, `register_hooks(tool, method, runner, hosts=None)`. The host table, its presence function, the rtk tables, `_rtk_register` and `PostinstallHook` are deleted.
- `installer/receipts.py`: `record` carries `previous.hooks`; `record_hooks(tool_id, name, hosts) -> bool` merges sorted hosts under `_WRITE_LOCK` and writes nothing when the tool has no receipt.
- `installer/engine.py`: `InstallOutcome.hooks` (appended field, with the `init=False` `__init__` parameter and its `object.__setattr__`); `install_tool` loses `tools` and dispatches `register_hooks`.
- `installer/session.py`: `tools` removed from `SensitiveInstall`, `_with_force` and the three `install(...)` calls.
- `installer/update.py`: `PostinstallFn` is `(Tool, Method, Runner, frozenset | None) -> HookOutcome`; `perform_update`, `_perform`, `_run_postinstall` and `UpdateService.run` lose `tools`; `UpdateService` loses the keyword in Task 2.
- `installer/model.py`: `POSTINSTALL_HOOK_NAMES = {"codegraph-mcp-register"}`.
- `installer/registry.toml`: rtk's `postinstall` line and its argv comments removed (catalog entry kept); codegraph's stale host-detection paragraph replaced with one CONF-02/CONF-03 dated line.
- Tests: the twelve planned tests plus the update re-record test; the test sandbox (`no_host_presence`, `real_present_hosts`, `sandboxed_setup_paths`, the extended real-HOME listing loop with `.zshenv`).

## RED evidence (Task 1, before any implementation)

Command: `uv run pytest <6 files> -k "registers_codex_once or not_registered_again or no_present_supported_host or pi_is_in_no_target_map or failed_register_is_a_warning or no_second_host_table or keeps_the_hooks_on_a_re_record or merges_sorted or registers_only_new_hosts or rtk_has_no_hook or no_receipt_means_no_registration or no_setup_home_constant" -q --no-cov -n 0`. Exit 1. Full log: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/red-task1.log`.

```
FAILED tests/test_postinstall.py::test_a_recorded_host_is_not_registered_again
FAILED tests/test_postinstall.py::test_no_present_supported_host_runs_nothing[none]
FAILED tests/test_postinstall.py::test_no_present_supported_host_runs_nothing[pi-only]
FAILED tests/test_postinstall.py::test_pi_is_in_no_target_map - AttributeError
FAILED tests/test_postinstall.py::test_no_receipt_means_no_registration - AttributeError
FAILED tests/test_engine.py::test_installing_codex_with_codegraph_registers_codex_once
FAILED tests/test_engine.py::test_a_failed_register_is_a_warning_and_records_nothing
FAILED tests/test_engine.py::test_no_receipt_means_no_registration - AttributeError
FAILED tests/test_receipts.py::test_record_keeps_the_hooks_on_a_re_record - AttributeError
FAILED tests/test_receipts.py::test_record_hooks_merges_sorted_and_skips_a_missing_receipt
FAILED tests/test_update.py::test_update_re_record_keeps_hooks_and_registers_only_new_hosts
FAILED tests/test_registry.py::test_rtk_has_no_hook - AssertionError: 'rtk-register' in POSTINSTALL_HOOKS
FAILED tests/test_sandbox.py::test_no_setup_home_constant_points_at_the_real_home - AssertionError: _REGISTRY (then _DEFAULT_BIN_DIR after the checkout exclusion)
ERROR tests/test_postinstall.py::test_one_host_list_has_no_second_host_table - fixture 'real_present_hosts' not found
```

Each failure is on the planned behaviour: the missing API (`register_hooks`, `record_hooks`, `present_hosts`, `HookPair`) or the rtk hook still registered. The sandbox RED is a real home-derived constant (`_DEFAULT_BIN_DIR`, `_MYSHELLRC`) pointing into the real HOME. The fixture error is the missing conftest fixture. No RED test was committed alone; the tests were committed together with the implementation in `05c95a4`.

## GREEN evidence

- Task 1: `make validate` exit 0 (ruff, format, pyright strict, bandit, vulture); `make test` exit 0, 5565 passed, 4 skipped, coverage 96.33%. The pre-commit hooks passed on the commit.
- Task 2: RED `uv run pytest tests/test_update.py -k update_service_takes_no_catalog -q --no-cov -n 0` failed (`'tools' in signature`); after the change, focused run exit 0; `make validate` exit 0; `make test` 5566 passed, 4 skipped. Pre-commit passed.
- Suppression gate: `rg` count of `type: ignore|pyright: ignore|noqa|nosec` over `installer setup.py tests` is 451 now, 456 at base `97b9e0b`. No suppression was added.

## Test changes (every change, with its reason)

Deleted, because the subject no longer exists (`tests/test_postinstall.py`, rewritten in full around the new API):
- `present_agent_hosts` tests (4) and the WR-01 missing-tool-id test: the host table is deleted (D-01, CONF-03).
- The rtk hook tests and the rtk-specific `_resolve_rtk_binary` github tests: rtk has no hook (user 2026-11-02, ledger Q2).
- `test_run_postinstall_dispatches_by_name_and_forwards_method_and_tools`: its `tools` argument is gone; replaced by the signature-level tests.

Retargeted (same behaviour, new API):
- The codegraph argv tests now call `run_postinstall(name, method, runner, hosts)` with harness ids. The brew binary-resolution tests moved from the private `_resolve_rtk_binary` to public `run_postinstall` behaviour, so they add no `pyright: ignore`.
- `test_installing_graphify_runs_no_host_registration` (`tests/test_postinstall.py`): `pi.is_installed` patch → `pi.present_hosts`; `tools=` removed.
- `test_engine.py`: the nine `monkeypatch.setattr(engine, "run_postinstall", …)` sites repointed to `register_hooks` with the new signature (R1-10 grep gate: 9 → 0). `test_receipt_write_failure_keeps_installed` keeps its assertion that the hook is dispatched, through a fake `register_hooks`; the new `test_no_receipt_means_no_registration` covers the no-receipt gate.
- `test_session.py`: the three catalog assertions (`actual_catalog is catalog`, `mapping is catalog`, `seen == [("fail", catalog, confirm)]`) rewritten so the install fake has no `tools` parameter and the rest of each test is kept. `test_sensitive_install_protocol_parameters_are_unchanged` no longer pins `tools` (the protocol drops it).
- `test_update.py`: `_perform` helper and the `postinstall=` fakes moved to `(tool, method, runner, hosts)`; the graphify update test's `pi.is_installed` patch → `pi.present_hosts`.
- `test_registry.py`: the codegraph comment needles `is_installed` → `present_harnesses` and `D-01` → `CONF-02`, because the comment was rewritten as the plan requires.
- `test_catalog_tui.py`: the `POSTINSTALL_HOOKS` fake is a `HookPair(targets=None, …)`.
- `test_execute_screen.py`: six install wrappers stop forwarding `tools=` into `install_tool`; the `_RecordingUpdateService` constructor and one `strict` fake keep the keyword (a test fake, not the engine).

New (planned): `test_installing_codex_with_codegraph_registers_codex_once`, `test_a_recorded_host_is_not_registered_again`, `test_a_host_already_recorded_runs_nothing`, `test_no_present_supported_host_runs_nothing` (2 cases), `test_pi_is_in_no_target_map`, `test_one_host_list_has_no_second_host_table`, `test_a_failed_register_is_a_warning_and_records_nothing`, `test_no_receipt_means_no_registration` (engine and postinstall), `test_record_keeps_the_hooks_on_a_re_record`, `test_record_hooks_merges_sorted_and_skips_a_missing_receipt`, `test_update_re_record_keeps_hooks_and_registers_only_new_hosts`, `test_rtk_has_no_hook`, `test_no_setup_home_constant_points_at_the_real_home`, `test_update_service_takes_no_catalog`. Also new: `test_codegraph_hook_brew_*` (3), `test_run_wizard_install_takes_no_catalog` (rewritten from `test_run_wizard_passes_the_full_catalog_as_tools_by_id_into_execute_plan`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The generic setup-path re-rooting skipped the checkout**
- **Found during:** Task 1, RED run of `test_no_setup_home_constant_points_at_the_real_home`
- **Issue:** this checkout lives under the real HOME (`/var/home/bazzite/git/...`), so the plan's rule ("every `Path` under the real HOME") would re-root `setup._REGISTRY`, the package-data path to `installer/registry.toml`, onto the scratch HOME and break registry loading in every `setup` test.
- **Fix:** `sandboxed_setup_paths` and the self-test exclude paths inside the directory that contains `setup.py`. Only home-derived paths are re-rooted.
- **Files modified:** `tests/conftest.py`, `tests/test_sandbox.py`
- **Commit:** `05c95a4`

**2. [Rule 3 - Blocking] `test_sandbox.py` imports `setup` at module level**
- **Found during:** Task 1 design
- **Issue:** the fixture is a no-op when `setup` is not in `sys.modules`, so the self-test run on its own would import `setup` after the fixture and see real paths.
- **Fix:** `import setup` at the top of `tests/test_sandbox.py`, matching `tests/test_setup.py`.
- **Commit:** `05c95a4`

**3. [Rule 3 - Blocking] Files outside the plan's list needed one mechanical change each**
- `tests/test_ownership.py`: one `perform_update(..., tools={})` keyword removed (D-01: `perform_update` loses `tools`).
- `tests/test_app.py`: `test_run_wizard_passes_the_full_catalog_as_tools_by_id_into_execute_plan` asserted the removed behaviour; rewritten as `test_run_wizard_install_takes_no_catalog`.
- `tests/state_doubles.py`: `ScriptedUpdates` passed `tools={}` to `UpdateService`; keyword removed (Task 2).
- Several `UpdateService` subclasses pass `tools={}` through `super().__init__`, which the AST pass missed. They were removed by a regex with an asserted count (`tests/test_execute_screen.py`, `tests/test_catalog_tui.py`).
- Commits: `05c95a4` (test_app, test_ownership, test_execute_screen), `0ac2979` (state_doubles, the UpdateService subclasses).

**4. Stale comment left in `tests/test_setup.py:2021`**
- It still says "`_resolve_rtk_binary`". The file is outside this plan's list, so the comment-only edit was reverted. Fix it in a later plan that touches that file.

**Total deviations:** 3 auto-fixed (Rule 3), plus one stale comment left in place. **Impact:** none on the design; the file list grew by test-only files, all mechanical.

## Behaviour changes to note

- codegraph's binary resolves through `_resolve_binary`. For a brew-kind codegraph method this now prefers `shutil.which("codegraph")` and then the brew prefixes, where it used to use `bin_dir` only. This is what the plan specifies, but it is a behaviour change for brew-owned codegraph installs.
- A targeted hook with no receipt now warns on update too. A manager-owned codegraph whose receipt was not re-recorded gets `hook not registered: no install receipt to record it in` on each update. This is the R1-08 rule applied to the update path; it should show up in the 23-16 end-to-end run.
- Hosts are read at dispatch time, so a host installed earlier in the same run is seen (research D14).
- Known limit (shortcut comment at `register_hooks`): a host removed by hand is registered again while its marker dir remains. A marker dir without its CLI counts as present (review R1-09).

## Issues Encountered

- The worktree guard refused compound git commands and the `$(git rev-parse --git-dir)` ledger write. The commit ledger file (`gsd-plan-head-before-23-01`) was not written. `commits:` above is measured directly against the known base SHA `97b9e0b`, which is the same measurement.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path or file-access pattern beyond the receipt and host-presence trust boundaries already in the plan's `<threat_model>`.

## Self-Check

- [x] `installer/postinstall.py` has `def register_hooks(`; `installer/receipts.py` has `def record_hooks(`; `tests/conftest.py` has `def sandboxed_setup_paths(`.
- [x] Commits `05c95a4` and `0ac2979` exist on `worktree-agent-a9502b7a651be902c`.
- [x] `make validate` exit 0 and `make test` exit 0 on the final tree.
- [x] STATE.md and ROADMAP.md are not edited.

## Self-Check: PASSED
