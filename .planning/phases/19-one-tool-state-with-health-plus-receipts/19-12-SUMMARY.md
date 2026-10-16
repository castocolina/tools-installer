---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "12"
status: complete
subsystem: version-status
tags: [ownership, refresh-pass, uv, volta, shims, native-index, rpm, tool-state, reasons]

requires:
  - phase: 19-04
    provides: "install_ownership.native_index / NativeIndex, guards.look_through_shim"
  - phase: 19-05
    provides: "ownership.query_uv_tool_dir, resolve_ownership(uv_tool_dir=), owner_dirs, attribute_path, Owner volta"
  - phase: 19-08
    provides: "VersionRefreshService._pass building one ToolState per tool (tool_state(..., notes=)), _default_present"
provides:
  - "Refresh pass asks `uv tool dir` once (only with uv on PATH) and resolves uv tools by it"
  - "Pass-local look-through `which` (VersionRefreshService._looked_through) for ownership and default presence; `path_value=` constructor kwarg"
  - "is_installed skips this installer's ban/redirect shims in the declared and implicit bin-dir checks (guarded names only)"
  - "One NativeIndex per pass: one batched native path query per OS family, every other native argv memoized per pass"
  - "ownership_notes / version_notes: the catalog's owner and version sentences as ToolState.reasons (none for skill packs)"
  - "`unresolved=` keyword forwarded through resolve_status -> resolve_github_release_status / _probed_version -> _version_argv; Volta and host_setup tools probe the PATH hit"
affects: [19-13, 19-15, 19-16, catalog_tui, uninstall, update]

actuals:
  tokens: 10900
  tasks: 3
  commits: 3
plan_head_before: 4432bf984a4d750989ebe9718c17bc6a55e1a61e
plan_head_after: 7efc515db94dfbec8ec674d4f33918d8e8382971

tech-stack:
  added: []
  patterns:
    - "Per-pass evidence objects (uv tool dir, NativeIndex) built at the top of `_pass` and handed to every resolve_ownership call; nothing cached across passes"
    - "Reasons are raw text; the catalog escapes them (plan 19-15)"

key-files:
  created: []
  modified:
    - installer/version_status.py
    - installer/status.py
    - tests/test_version_status.py
    - tests/test_status.py
    - tests/test_catalog_tui.py

key-decisions:
  - "The look-through `which` is a service method (`_looked_through`) used by both the pass and `_default_present`, so `is_present` outside a pass also never counts a shim"
  - "The batch collects `Path(hit).resolve()` (OSError fallback) via a local `_resolved_hit`, the same strings resolve_ownership asks the index about; `ownership._resolve_active_path` is private, so it is mirrored, not imported"
  - "On macOS the raw native probe is passed through unchanged (no OS package database, no batch), per the plan"
  - "version notes: `version unreadable` (present, installed None) and `no latest version to compare against` (present, latest or outdated None) are exclusive, mirroring `_ver_cell`; they come before the installer/pin/stale sentences (UI-SPEC note order: unreadable before stale)"

patterns-established:
  - "Manager-snapshot query counters answer `uv tool dir` without counting it; its own test pins it to once per pass"

requirements-completed: [STATE-04]

coverage:
  - id: D1
    description: "graphify resolves to owner uv through `uv tool dir`; asked once per pass, never without uv"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_pass_resolves_graphify_to_uv_by_tool_dir, #test_pass_queries_uv_tool_dir_once"
        status: pass
  - id: D2
    description: "pnpm behind the redirect shim reads owner volta; a shim alone (PATH hit or managed-bin file) is MISSING"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_pass_looks_through_the_redirect_shim, #test_redirect_shim_without_a_real_binary_is_missing, #test_shim_only_managed_bin_path_is_missing; tests/test_status.py#test_installer_shim_is_never_presence"
        status: pass
  - id: D3
    description: "One batched rpm path query per pass, tracked paths excluded, rpm-ostree status and declared-package queries memoized per pass"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_pass_makes_one_rpm_path_query_for_many_native_tools, #test_pass_excludes_tracked_paths_from_the_batch, #test_pass_without_native_probe_makes_no_native_query, #test_pass_reads_rpm_ostree_status_once, #test_pass_memoizes_declared_package_queries"
        status: pass
  - id: D4
    description: "Owner and version sentences are ToolState.reasons; skill packs get none; Volta/host_setup versions probe the unresolved hit on all four routes"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_version_status.py -k 'note or unreadable or no_comparison or unresolved_path' (15 passed)"
        status: pass

duration: ~40min
completed: 2026-10-16
---

# Phase 19 Plan 12: Owner evidence wired into the refresh pass Summary

The refresh pass now resolves uv tools by `uv tool dir`, looks through this installer's own shims for owner and presence, answers every native package question from one batched query per pass, and publishes the catalog's owner/version sentences as `ToolState.reasons`. Volta and host_setup tools are version-probed through the PATH hit.

## Performance

- Duration: about 40 min
- Completed: 2026-10-16
- Tasks: 3/3
- Files modified: 5 (2 source, 3 test)

## Task Commits

1. **Task 1: uv tool dir + shim look-through + no shim presence (D-12, D-13, review M9)** - `2310a11` (feat)
2. **Task 2: one batched native query per pass (D-11)** - `e363da3` (perf)
3. **Task 3: owner/version facts as reasons; unresolved version argv (D-15, Pitfall 6, C2-M5)** - `7efc515` (feat)

## What was built

- **Task 1** (`installer/version_status.py`, `installer/status.py`): constructor kwarg `path_value: Callable[[], str] | None` (default reads `PATH` at call time). New `VersionRefreshService._looked_through(name)` = `look_through_shim(self._which(name), name, shim_dir=managed_bin_dir, path_value=self._path_value())`; used by `resolve_ownership(which=...)` in the pass and by `_default_present` (`is_installed(tool, which=..., default_bin_dir=self._managed_bin_dir)`; an injected `present` is still honored). At the top of `_pass`, after the has_brew re-read: `uv_tool_dir = query_uv_tool_dir(self._query) if self._which("uv") is not None else None`, passed as `uv_tool_dir=` to `resolve_ownership`. `is_installed` gained `_is_installer_shim(tool, path)` (module import `installer.guards`; `is_our_shim` runs only when `tool.cmd in guarded_names()`), applied to the declared-`bin_dir` loop and the implicit artifact check.
- **Task 2** (`installer/version_status.py`): when a native probe is injected and the OS is not macOS, the pass collects each tool's resolved live path that `attribute_path(path, owner_dirs(..., uv_tool_dir=uv_tool_dir))` gives to no tracked owner, builds `native_index(platform.os, paths, probe)` once, and passes it as `native_probe=` to every `resolve_ownership` call. The index answers the per-path argv shapes from the batch and memoizes every other argv for the pass only.
- **Task 3** (`installer/version_status.py`): pure `ownership_notes(tool, ownership, platform)` and `version_notes(tool, status, ownership, *, present)` reproduce `catalog_tui._version_detail`'s sentences verbatim and in its order (without markup escaping), plus `version unreadable` / `no latest version to compare against`. Both return `()` for a tool with a `skill_pack` method. The pass passes `notes=ownership_notes(...) + version_notes(...)` to `tool_state` for non-pack tools. `_version_argv(tool, ownership, *, unresolved=None)` returns `[unresolved, "--version"]` for owner `volta` or a tool with a `host_setup` method. `unresolved` is keyword-only on `resolve_status`, `resolve_github_release_status` and `_probed_version`, forwarded at all six call sites. The pass passes `unresolved=which(tool.cmd)`.

## TDD RED evidence (trimmed)

Task 1. test_status, before the `is_installed` change:
```
>       assert is_installed(tool("npx"), which=_which_none, default_bin_dir=bin_dir) is False
E       AssertionError: assert True is False
FAILED tests/test_status.py::test_installer_shim_is_never_presence[# tools-installer-ban-shim-declared]
FAILED tests/test_status.py::test_installer_shim_is_never_presence[# tools-installer-ban-shim-implicit]
FAILED tests/test_status.py::test_installer_shim_is_never_presence[# tools-installer-redirect-shim-declared]
FAILED tests/test_status.py::test_installer_shim_is_never_presence[# tools-installer-redirect-shim-implicit]
```
Task 1. test_version_status: first `TypeError: ... unexpected keyword argument 'path_value'`. After adding only the kwarg, the behavioral RED was:
```
E       AssertionError: assert 'unknown' == 'uv'
E       AssertionError: assert 0 == 1   (['uv', 'tool', 'dir'] count)
E       AssertionError: assert 'unknown' == 'volta'
E       AssertionError: assert <Health.OK: 'ok'> is <Health.MISSING: 'missing'>   (x2)
FAILED test_pass_resolves_graphify_to_uv_by_tool_dir / test_pass_queries_uv_tool_dir_once /
       test_pass_looks_through_the_redirect_shim / test_redirect_shim_without_a_real_binary_is_missing /
       test_shim_only_managed_bin_path_is_missing
```
Task 2:
```
E       AssertionError: assert [] == [['rpm', '-qf', '--qf', '[%{FILENAMES}\\t%{=NAME}\\n]', '.../usr/bin/native0', ...]]
E       AssertionError: assert [] == [['rpm', '-qf', '--qf', '[%{FILENAMES}\\t%{=NAME}\\n]', '.../usr/bin/native0']]
E       AttributeError: <module 'installer.version_status'> has no attribute 'native_index'
E       AssertionError: assert 3 == 1   (['rpm-ostree', 'status', '--json'])
E       AssertionError: assert 2 == 1   (['rpm', '-q', '--qf', '%{NAME}\\n', 'shared'])
5 failed
```
Task 3: the first run was `ImportError: cannot import name 'ownership_notes'`. With temporary `()` stubs (removed before the implementation), the behavioral RED was:
```
E       AssertionError: assert () == ('managed by ...brew/bin/rg')
E       assert 0 == 1  (off-policy / active-path / version sentences)
E       AssertionError: assert () == ('no manager claimed the tool',)
E       AssertionError: assert 'version unreadable' in ()
E       AssertionError: assert [['.../volta-shim', '--version']] == [['.../volta/bin/pnpm', '--version']]   (volta, host_setup)
E       TypeError: resolve_status() got an unexpected keyword argument 'unresolved'   (x4 routes)
12 failed (test_skill_pack_gets_no_binary_notes passes against the stubs by design: it is the W1 guard)
```

## Verify-command results

- Task 1 `-k "graphify or uv_tool_dir or redirect_shim or looks_through or shim_only or never_presence"`: **9 passed** (gate ≥ 9). `tests/test_status.py tests/test_guards.py -n auto`: green.
- Task 2 `-k "rpm or native or batch or tracked_paths or declared_package"`: **7 passed** (gate ≥ 5).
- Task 3 `-k "note or unreadable or no_comparison or unresolved_path"`: **15 passed** (gate ≥ 13). Forwarding gate: `unresolved=unresolved` at **6** non-comment sites. Suppression gate: 598 -> 598. `git diff --exit-code HEAD -- installer/catalog_tui.py`: 0.
- Acceptance greps: `query_uv_tool_dir(` 1, `look_through_shim(` 1, `is_our_shim(` 1 and `guarded_names()` 1 in status.py, `native_index(` **1**, `def ownership_notes|def version_notes` 2.
- Plan verification: `tests/test_version_status.py tests/test_ownership.py tests/test_install_ownership.py -n auto`: 391 passed. `git diff --exit-code fde3e68 -- pyproject.toml uv.lock`: 0 (no new dependency).
- Before every commit: `make validate` exit 0 and `make test` green. Final tree: **4338 passed, 4 skipped, coverage 95.80%**. The pre-commit hook passed on every commit.

### Large-file evidence (shrink guard before each commit)

| Commit | installer/version_status.py | tests/test_version_status.py |
|--------|-----------------------------|------------------------------|
| 2310a11 | 1127 -> 1141 | 2969 -> 3176 (top-level `def test_` 79 -> 84) |
| e363da3 | 1141 -> 1168 | 3176 -> 3334 (84 -> 89) |
| 7efc515 | 1168 -> 1266 | 3334 -> 3578 (89 -> 100) |

`git diff --stat 4432bf9 HEAD`:
```
 installer/status.py          |  15 +-
 installer/version_status.py  | 165 +++++++++++-
 tests/test_catalog_tui.py    |   5 +-
 tests/test_status.py         |  31 +++
 tests/test_version_status.py | 611 ++++++++++++++++++++++++++++++++++++++++++-
 5 files changed, 810 insertions(+), 17 deletions(-)
```
Each per-commit diff held only the intended hunks; `git diff -U0` hunk headers were checked after `ruff format`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Manager-snapshot query counters now see the per-pass `uv tool dir`**
- **Found during:** Task 1 (full suite)
- **Issue:** Four existing tests (`test_fresh_manager_snapshot_issues_zero_queries`, `..._requeries_seven_plus_one`, `test_failed_at_backoff_suppresses_requery`, `test_invalidate_drops_snapshot_and_bumps_epoch`) count every `query` call. Their `which` fixture answers `uv`, so the new once-per-pass `uv tool dir` added one call.
- **Fix:** `_counting_query` answers `["uv","tool","dir"]` but does not record it. A docstring says why, and `test_pass_queries_uv_tool_dir_once` pins that count.
- **Files:** tests/test_version_status.py (in plan scope). **Commit:** 2310a11

**2. [Rule 3 - Blocking] Native-probe fakes answer the batched rpm argv (one file OUTSIDE files_modified)**
- **Found during:** Task 2
- **Issue:** Two fakes answered every argv with a bare package name (`"jq\n"`, `"git-core\n"`). The batched `rpm -qf --qf [%{FILENAMES}\t%{=NAME}\n]` parse expects `<path>\t<name>` lines, so the index answered "unowned" and the owners regressed to `unknown`.
- **Fix:** Both fakes return `<path>\t<name>` lines for the batched argv:
  - `test_native_probe_service_resolves_owner_and_status_stays_on_final_branch` in tests/test_version_status.py
  - `test_owner_column_and_detail_paint_the_os_package_case_end_to_end` in **tests/test_catalog_tui.py** (+4/-1 lines at ~:1220). That file belongs to the parallel plan 19-13, so the orchestrator may need to resolve this hunk on rebase.
- **Commit:** e363da3

**3. [Rule 2 - Coverage] Extra test `test_shadowed_note_variants`**
- The three remaining shadowed-sentence branches (also-note without a live path, `shadowed — live copy at`, bare `shadowed`) had no coverage. One small test now pins them. **Commit:** 7efc515

**Process notes (no code effect):**
- The sandbox refused the plan's `bash -c '…git…'` guard one-liners and compound git commands. I ran the same checks from script files in `<scratchpad>/exec19/work-19-12/` (shrink guard, Task 3 gates) and as plain separate commands. The scratch directory is deleted at the end.
- Edits to the large files went through an out-of-repo literal-replace and append script (exact-match asserts), never through string-replace on whole functions.
- The worktree had no `.venv`. `uv run` created it on first use, from the existing lock with no dependency change.

## Known Stubs

None.

## Threat Flags

None. T-19-35 (shim spoofing presence) is mitigated by the look-through plus `is_installed` skipping shims. T-19-36 (Volta version via `volta-shim`) is mitigated by the unresolved-path forwarding, the four-route test and the 6-site gate. T-19-37 (N native queries) is mitigated: one batch query, one `rpm-ostree status` and one query per distinct declared package per pass.

## Notes for the orchestrator

- **Rebase conflict risk:** `tests/test_catalog_tui.py` (19-13's file) has one 4-line hunk inside `test_owner_column_and_detail_paint_the_os_package_case_end_to_end`'s `native_probe` fake (commit e363da3).
- The catalog still renders its own copy of the sentences (`_version_detail`, unchanged). The reasons now duplicate that text in state until plan 19-15 switches the detail bar to `state.reasons` and deletes `_version_detail`. The reasons are unescaped, as the plan specifies.
- The pass calls the looked-through `which(tool.cmd)` up to three times per tool: path collection, resolve_ownership and `unresolved=`. Each call is cheap, and it reads a file only when the hit is a shim in the managed bin dir. This could be memoized per pass if a profile ever shows it.

## Self-Check: PASSED

- FOUND: installer/version_status.py, installer/status.py, tests/test_version_status.py, tests/test_status.py, tests/test_catalog_tui.py
- FOUND commits: 2310a11, e363da3, 7efc515 (ancestors of HEAD)
