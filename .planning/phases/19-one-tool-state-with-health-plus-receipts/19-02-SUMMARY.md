---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "02"
subsystem: installer
tags: [artifact-paths, download, uninstall, status, d07-one-formula, d13-implicit-presence, cli-spec-move, path-traversal, tdd]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts (plan 01)
    provides: tests/conftest.py autouse sandboxed_receipts + sandboxed_bin_dir (module-attribute patch seam on installer.locations.bin_dir)
  - phase: 18
    provides: link_name, is_still_proven, replace_symlink, ExecutorError conventions
provides:
  - installer/download.py: Artifact dataclass, artifact_paths(method, default_bin_dir) — the one formula for what a method creates (D-07); _is_single_name guard; cli_spec moved from apps.py (Ledger L-19-04)
  - installer/download.py: install_download/update_download reject an unsafe final bin name with ExecutorError before any write (review M2, C3-M1)
  - installer/uninstall.py: plan_uninstall and plan_removal read artifact_paths; private _plan_app/_download_link deleted
  - installer/status.py: is_installed(..., which=..., default_bin_dir=...), macos_stub_reason(..., which=...), implicit ~/.local/bin presence via installer.locations.bin_dir(None) module-attribute read (D-13, SPEC AC12, checker W2, review H2)
affects: [19-09, 19-10, 19-08]

actuals:
  tokens: 9100
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "one placement formula (Artifact/attempt artifact_paths) read as evidence by uninstall and (from 19-09) the receipt writer"
    - "single-basename predicate applied to the FINAL link_name result, shared by artifact_paths (no artifact), install_download and update_download (ExecutorError)"

key-files:
  created: []
  modified:
    - installer/download.py
    - installer/apps.py
    - installer/uninstall.py
    - installer/status.py
    - tests/test_download.py
    - tests/test_apps.py
    - tests/test_uninstall.py
    - tests/test_status.py

key-decisions:
  - "artifact_paths mirrors _plan_app's app-name rule exactly (basename equals the value, not '.' or '..'); an ExecutorError from cli_spec yields the bundle only, matching what install could have created"
  - "plan_removal is restricted to DOWNLOAD_KINDS methods before reading artifact_paths, so an app cli link can never be layout-proven against opt_dir (app bundles were never proven by layout before either)"
  - "status Which = Callable[[str], str | None]; both is_installed and macos_stub_reason resolve shutil.which inside the body (review H2)"
  - "implicit presence uses artifact.path.is_file() only on 'file'/'link' artifacts, so a dangling link and a raw 'dir' half never count (fail-closed)"

patterns-established:
  - "Module-attribute read for home-derived defaults (installer.locations.bin_dir(None)) so runtime patches always win — second use after guards.py"

requirements-completed: [STATE-03, STATE-04]

duration: ~55 min (3 tasks, each first-try commit)
completed: 2026-10-16
---

# 19-02 Summary — one artifact formula plus implicit bin presence

One-liner: `download.artifact_paths` is now the single formula for what a method creates (D-07), the uninstaller reads it instead of its own path rules, and `is_installed` counts a download method's implicit `~/.local/bin` binary as presence with an injected `which`/`default_bin_dir` (D-13).

## What was built

### Task 1 — artifact_paths + cli_spec move (`2b9321c`)
- `Artifact` (frozen dataclass, `path` + `kind: Literal["dir","link","file"]`, docstring: evidence only, never removal authority — D-10) and `artifact_paths(method, default_bin_dir)` in `installer/download.py`: archive download -> (`opt_dir(name)`, dir) + (`<bin>/name`, link); raw -> one file; app -> bundle dir + optional cli link via `cli_spec`; every other kind -> `()`. `bin_name`/`cli_name` honored; `<bin>` is the declared `bin_dir` (expanduser'd) else `default_bin_dir`.
- `_is_single_name` (PurePosixPath single-component rule) applied to the FINAL `link_name` result in `artifact_paths` (no artifact) and, right after `resolve_target`, in `install_download` and `update_download` (`ExecutorError(f"unsafe bin name '{name}': must be a single file name")` before `ensure_dir`/any download — review M2, C3-M1).
- `cli_spec` moved unchanged from `installer/apps.py` to `installer/download.py` (Ledger L-19-04); apps and uninstall import it from download. `download.py` does not import `installer.apps` (verify 2 checks the AST).
- Tests: `test_artifact_paths_per_kind`, `test_artifact_paths_rejects_bad_member_basenames`, `test_artifact_paths_rejects_an_unsafe_bin_name`, `test_artifact_paths_rejects_a_bad_app_name`, `test_artifact_paths_invalid_cli_name_yields_the_bundle_only`, `test_install_download_rejects_an_unsafe_bin_name`, `test_update_download_rejects_an_unsafe_bin_name`, `test_artifact_paths_matches_install_placement_for_every_registry_method` (96 (method, arch) pairs; placement agreement of 17-REVIEW IN-05 pinned). tests/test_apps.py: import line only (38 tests unchanged).

RED (Task 1): `ImportError: cannot import name 'Artifact' from 'installer.download'` — collection error in both tests/test_download.py and tests/test_apps.py; after a stub-free first run the unsafe-name cases also fail (`pytest.raises(ExecutorError, match="unsafe bin name")` did not raise).

### Task 2 — uninstaller reads artifact_paths (`1776130`)
- `plan_uninstall` adds every `artifact_paths(method, default_bin_dir)` path that exists or is a dangling symlink, de-duplicated, in method order; docstring cites the formula.
- `plan_removal` takes the "link" and "dir" artifacts per DOWNLOAD_KINDS method; `is_still_proven(link)` and the (link, opt) pair unchanged; `yourself` stays plan_uninstall minus the proven paths; raw methods are never layout-proven.
- `_plan_app` and `_download_link` deleted; `APP_KINDS`, `cli_spec`, `applications_dir`, `PurePosixPath`, `ExecutorError` imports dropped (vulture-clean). `still_removable` untouched (plan 19-10 replaces it).
- Tests: `test_plan_uninstall_lists_exactly_the_existing_artifact_paths`, `test_plan_removal_never_proves_a_raw_file`, `test_plan_removal_still_proves_an_archive_link`.

RED (Task 2): `test_plan_uninstall_lists_exactly_the_existing_artifact_paths` FAILED — the planted stray `~/.local/opt/yq` beside the RAW method was listed (`[.../.local/opt/yq, .../.local/bin/yq]`); the two plan_removal tests passed as expected (they pin unchanged behavior).

### Task 3 — implicit bin presence + injected which (`93adcef`)
- `is_installed(tool, app_roots=None, *, darwin, probe, which=None, default_bin_dir=None)` and `macos_stub_reason(tool, *, darwin, probe, which=None)`: `lookup = shutil.which if which is None else which` resolved INSIDE the body (review H2); `is_installed` forwards `which` (None included) to `macos_stub_reason`.
- After the declared-bin_dir loop: `implicit = default_bin_dir if ... else installer.locations.bin_dir(None)` (module-attribute read, conftest `sandboxed_bin_dir` seam); per DOWNLOAD_KINDS method without a declared `bin_dir`, any "file"/"link" artifact with `path.is_file()` returns True (follows links; dangling is not present). The given `default_bin_dir` replaces the default.
- Tests (8 new): implicit file/link present, dangling link absent, declared-bin_dir methods keep their own rule, injected which for both functions, call-time which resolution (recording fake sees `tool.cmd` twice), given default bin dir replaces the default.

RED (Task 3): five tests failed with `TypeError: ... unexpected keyword argument 'which'/'default_bin_dir'` (test_implicit_local_bin_file_counts_as_present, test_implicit_local_bin_link_into_opt_counts_as_present, test_dangling_implicit_link_is_not_present, test_is_installed_uses_the_injected_which, test_implicit_presence_reads_the_given_default_bin_dir).

## Verify results
- Task 1: `-k "artifact_paths or cli_spec or cli_name or unsafe_bin_name"` -> 37 passed; AST check (cli_spec in download, not in apps, no `installer.apps` import in download) OK; truncation guard OK (test_download 2045->2225 lines, 72->80 tests; test_apps 910->910, 38->38; final newlines kept).
- Task 2: `tests/test_uninstall.py tests/test_app.py tests/test_version_status.py -q --no-cov` -> 180 passed; `grep -cE "^def (_plan_app|_download_link)"` = 0 and `artifact_paths(` count = 2; truncation guard OK (1541->1635, 75->78 tests).
- Task 3: `-k "implicit or injected_which or declared_bin_dir or call_time"` -> 10 passed (>= 7); status/engine/execute_screen `-n auto` green; suppression count 598 -> 598.
- Per-commit and final: `make validate` rc 0; `make test` -> **4040 passed / 4 skipped**, coverage 95.53% (floor 90). `git diff fde3e68 -- pyproject.toml uv.lock` empty (no new dependency).

## Deviations from the plan
- tests/test_download.py also imports `link_name` and `load_tools` (needed by the registry-wide placement test the plan mandates) — within the plan's files_modified, additive only.
- Added a standalone `_github_tool` helper in tests/test_status.py; existing module-level `_which_none` reused (pyright reportRedeclaration forced dropping my duplicate).
- Existing tests adjusted to the formula: none — no existing test planted an opt dir beside a raw method (grepped `"raw"` in tests/test_uninstall.py), so no tests needed updating for the raw-opt-dir change. The only prior-behavior dependency (uv/pip foreign files, shared drawio file, app bundles in `yourself`) is preserved and still green.

## Notes for the orchestrator
- `plan_uninstall`'s default_bin_dir semantics for app cli links are unchanged (`<default bin>/<cli name>`); callers (version_status._artifacts, setup.py) were not touched.
- Full suite run time ~65-80 s; no flakes observed across repeated `-n auto` runs.
- git status clean apart from orchestrator-owned .planning state.
