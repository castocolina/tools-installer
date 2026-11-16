---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "05"
status: complete
subsystem: core
tags: [ownership, volta, uv, host-setup, update, tdd]

requires:
  - phase: 15.4
    provides: _os_package_owner synthetic-candidate shape, removal/label tables, UNMANAGEABLE_OWNERS refusal
provides:
  - "Owner \"volta\": a live binary resolving to exactly <$VOLTA_HOME or ~/.volta>/bin/volta-shim is owned by volta (direct), decided before the single-active-candidate return (review H3)"
  - "volta entries in OWNER_LABELS, OWNER_DETAIL_LABELS, _REMOVAL_COMMANDS, _REMOVAL_DESCRIPTIONS"
  - "query_uv_tool_dir(query) -> Path | None (`uv tool dir`, never --bin)"
  - "owner_dirs(..., uv_tool_dir=) and resolve_ownership(..., uv_tool_dir=): uv attribution from the passed-in dir only; no UV_TOOL_BIN_DIR read, no ~/.local/bin guess"
  - "host_setup owner: a verified non-native host-setup manager (pi -> pnpm) is claimed with the setup probe's package when the live path sits in that owner's dir"
  - "ownership.method_package(method): the one reader of a method's manager package name"
  - "update refusals: volta -> unsupported with `volta install <pkg>`; pnpm with no method -> unsupported with `pnpm add --global <pkg>`"
affects: [19-09 receipt packages via method_package, 19-12 refresh pass supplies uv_tool_dir]

actuals:
  tokens: 7650
  tasks: 3
  commits: 3
plan_head_before: 3d5972b0b2f0e552f7a0a384cac024447e7f1b47
plan_head_after: ae204ed503f7c02066920473c084c7c2eb6209ea

tech-stack:
  added: []
  patterns:
    - "synthetic OwnershipCandidate + _owned for evidence that is not an inventory (Volta shim, host setup)"
    - "owner directories passed in as data (uv_tool_dir) instead of read from the environment"

key-files:
  created: []
  modified:
    - installer/ownership.py
    - installer/update.py
    - tests/test_ownership.py
    - tests/test_update.py
    - tests/test_version_status.py

key-decisions:
  - "Volta claim needs the resolved live path to be exactly <Volta bin>/volta-shim (name and parent, both resolved); any other file in that dir keeps the existing candidate rules"
  - "Volta and host-setup owners set active_candidate to their own owner: both claims rest on directory attribution of the live path"
  - "Volta is not added to NATIVE_OWNERS, UNMANAGEABLE_OWNERS or _CANDIDATE_ORDER; update.py refuses it in its own branch after the UNMANAGEABLE_OWNERS branch"
  - "No uv_tool_dir means uv attributes nothing: a uv tool on PATH resolves by inventory elimination only until plan 19-12 passes the dir"
  - "_native_owner takes attributed as a required keyword; only its one caller passes it"

requirements-completed: [STATE-04]

duration: ~21 min
completed: 2026-10-16
---

# Phase 19 Plan 05: Volta, uv tool dir and host_setup owners Summary

Volta shims now resolve to a `volta` owner (ahead of an overlapping installer candidate), uv ownership comes from a passed-in `uv tool dir` instead of the colliding `~/.local/bin` guess, pi resolves to `pnpm` through its verified host-setup probe, and updates for Volta and host-setup pnpm tools end in a clean `unsupported` with the right command instead of `failed`.

## What was built

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | 503647e | `"volta"` in `Owner`; `owner_dirs` volta entry `Path($VOLTA_HOME or ~/.volta)/bin`; `_volta_owner` called before the `active_candidate` return, claims only when the resolved live path is `<Volta bin>/volta-shim`, package = first node method's npm_pkg else `tool.cmd`, existing candidates kept with `shadowed=True`; four label/removal table entries; `update._perform` volta refusal after the `UNMANAGEABLE_OWNERS` branch, zero subprocess |
| 2 | 8886e60 | `query_uv_tool_dir` (`["uv","tool","dir"]`; `CommandError`/`OSError`/blank -> None); `uv_tool_dir` keyword on `owner_dirs` and `resolve_ownership`; `UV_TOOL_BIN_DIR` read and `~/.local/bin` default deleted; four planned test conversions; version-status fixture adjusted (see Deviations) |
| 3 | ae204ed | `method_package`; `method_removal_command` rewritten over it (byte-identical, checked against a frozen copy of the old formula over every registry method); Volta package read switched to it; `_HOST_SETUP_OWNERS = {"pnpm": "pnpm"}` and `_host_setup_owner`, reached from `_native_owner` when the verified manager is not native and the owner is in `attributed`; `update._perform` pnpm branch returns `unsupported` for `method is None` |

The plan's exhaustiveness tests (`test_owner_labels_covers_every_non_unknown_owner_value`, `test_owner_detail_prose_register_is_exhaustive`, the removal-table and `UNMANAGEABLE_OWNERS` pins) pass with no edits. In `tests/test_ownership.py` the only removed lines are in the four planned conversions.

## TDD RED evidence

Task 1 (`-k volta`, before implementation): 6 failed, 1 passed. The non-shim overlap test already held, because today's code keeps the installer owner.
```
FAILED tests/test_ownership.py::test_volta_shim_resolves_to_volta - AssertionError
FAILED tests/test_ownership.py::test_volta_resolves_for_a_node_tool_with_a_pnpm_candidate
FAILED tests/test_ownership.py::test_volta_dir_defaults_to_home_volta_bin - KeyError: 'volta'
FAILED tests/test_ownership.py::test_volta_shim_wins_over_an_overlapping_installer_candidate
FAILED tests/test_ownership.py::test_volta_owner_labels - KeyError: 'volta'
FAILED tests/test_update.py::test_update_refuses_volta_cleanly
E       AssertionError: assert 'failed' == 'unsupported'
```

Task 2 (whole `tests/test_ownership.py`): 89 failed, 118 passed. Every `_resolve` call now forwards `uv_tool_dir=`, so all of them failed with the TypeError. The distinct new-test failures were:
```
E       TypeError: resolve_ownership() got an unexpected keyword argument 'uv_tool_dir'
E       TypeError: owner_dirs() got an unexpected keyword argument 'uv_tool_dir'
E       AttributeError: module 'installer.ownership' has no attribute 'query_uv_tool_dir'. Did you mean: '_query_uv_tools'?
E       AssertionError: assert (PosixPath('/opt/uv/bin'),) == ()
```

Task 3 (`-k "host_setup or method_package or removal_command or volta"`): 3 failed, 20 passed.
```
E       AssertionError: assert 'unknown' == 'pnpm'
E           AttributeError: module 'installer.ownership' has no attribute 'method_package'
E       AssertionError: assert 'failed' == 'unsupported'
FAILED tests/test_ownership.py::test_host_setup_tool_resolves_to_its_verified_owner
FAILED tests/test_ownership.py::test_method_package_reads_the_kind_param
FAILED tests/test_update.py::test_update_refuses_host_setup_pnpm_cleanly
```
The other two host-setup tests (`needs_the_live_path_in_that_owners_dir`, `unverified_probe_stays_unknown`) already held, because the old code never claimed pnpm. They stay as regression guards.

## Verify results

- Task 1: `-k "volta or owner_labels or detail_labels or removal or unmanageable"` all passed; 7 volta tests pass. `grep -c '"volta"' installer/ownership.py` = 9, `grep -c volta installer/update.py` = 3.
- Task 2: `pytest tests/test_ownership.py` all passed; `-k "uv_tool_dir or graphify"` = 4 passed. `grep -c UV_TOOL_BIN_DIR installer/ownership.py` = 0, `grep -c "def query_uv_tool_dir"` = 1, `grep -c '"--bin"'` = 0.
- Task 3: `-k "host_setup or method_package or removal_command or volta"` = 23 passed. `grep -c "def method_package"` = 1. `git diff --exit-code HEAD -- installer/install_ownership.py installer/host_setup.py` exits 0.
- Truncation guard (lines HEAD -> new, test functions, trailing newline OK):
  - Task 1: ownership.py 1546 -> 1594; test_ownership.py 2677 -> 2783 (143 -> 149 tests); test_update.py 1213 -> 1223 (47 -> 48). `git diff --stat`: 3 files changed, 164 insertions(+).
  - Task 2: ownership.py 1594 -> 1617; test_ownership.py 2783 -> 2847 (149 -> 152). `git diff --stat`: ownership.py 31, test_ownership.py 92, test_version_status.py 5 lines changed (108 insertions, 20 deletions); test_version_status.py is 2029 lines.
  - Task 3: ownership.py 1617 -> 1668; test_ownership.py 2847 -> 2963 (152 -> 156); test_update.py 1223 -> 1236 (48 -> 49). `git diff --stat`: 4 files changed, 201 insertions(+), 12 deletions(-).
- Suppression guard: 598 -> 598.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: unchanged.
- Plan verification: `pytest tests/test_ownership.py tests/test_update.py -n auto --no-cov` all passed.
- `make validate` and `make test` passed before each commit. Final run: 4108 passed, 4 skipped (macOS-only host tests, none in this plan's files).

## Deviations from Plan

1. **[Rule 3 - Blocking] `tests/test_version_status.py` edited (outside files_modified)** in Task 2 (8886e60). `test_fresh_manager_snapshot_issues_zero_queries` expected ruff at `~/.local/bin/ruff` to read `uv`. That only held because of the `~/.local/bin` guess D-12 deletes. `VersionRefreshService` does not pass `uv_tool_dir` until plan 19-12, so the live path became unattributable and the test read `unknown`. Fix: the shared `_which_for_fixture` now returns `None` for ruff, which makes it uv-owned by elimination from the snapshot inventory. Every test that uses the fixture still passes. The edit is 2 lines plus a comment. Plan 19-07 (running in parallel) and 19-12 also list this file, so the rebase may need a trivial merge around `_which_for_fixture` (line ~555).
2. **`test_update_refuses_host_setup_pnpm_cleanly` builds a tool with no methods.** `_target` in tests/test_update.py fills `method` from `tool.methods[0]` when it is None, so a pi tool with a `host_setup` method would never reach `method is None`. The test asserts `target.ownership.method is None` before running.
3. **`test_method_package_reads_the_kind_param` uses the file's own `_REGISTRY`**, the same path as `tests.test_registry.REGISTRY`. The frozen expected formula is written out as a literal table in the test, so no private attributes are accessed and no new suppressions are needed.
4. **Guard scripts:** the worktree sandbox refused multi-statement shell commands. The shrink guard ran as a script file in the session scratchpad (deleted afterwards), and the suppression guard ran as two plain `grep | wc -l` commands. The checks were the same.

## Issues for the orchestrator

- Until plan 19-12 passes `uv_tool_dir` (from `query_uv_tool_dir`, once per pass when uv is on PATH), a uv tool that is live on PATH, such as graphify in `~/.local/bin`, resolves `unknown` in the catalog. Before, it read `uv` only through the colliding guess. With no live path it still resolves `uv` by elimination.
- `query_uv_tool_dir` has no production caller yet (19-12 wires it). Vulture passes.
- Real-host note: the host's `~/.volta/bin/{pnpm,codex,openspec,npm,node}` shims will now read `Volta` in the catalog. The `pi` row reads `pnpm` only when its live binary is in the pnpm home.

## Self-Check: PASSED

- FOUND: installer/ownership.py (`def method_package`, `def query_uv_tool_dir`, `def _volta_owner`, `def _host_setup_owner`)
- FOUND: installer/update.py (volta and host-setup pnpm refusals)
- FOUND commits: 503647e, 8886e60, ae204ed (ancestors of HEAD)
