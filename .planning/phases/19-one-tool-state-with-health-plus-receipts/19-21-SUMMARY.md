---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "21"
status: complete
subsystem: skill-packs
tags: [skill-lifecycle, project-scope, opengsd, registry, repo-walk, tdd, security]

requires:
  - phase: 19-11
    provides: ProjectPackReport, inspect_project_pack (global leftovers), PROJECT_PACK_PACKAGES, _GSD_RUNTIME_IDS, _has_gsd_entry, opengsd scope/version pin
  - phase: 19-07
    provides: ConfigStep / ConfigStepKind (project_pack_install)
provides:
  - "PROJECT_ROOTS, PROJECT_RUNTIME_DIRS (claude .claude, opencode .opencode), _MAX_WALK_DEPTH/_MAX_WALK_DIRS/_MAX_WALK_ENTRIES"
  - "_find_project_repos(home): bounded BFS for .planning/config.json, sorted result, no symlink descent, symlinked roots rejected"
  - "_installed_runtimes(repo): VERSION file plus a gsd-* entry in skills or commands"
  - "inspect_project_pack fills repos and adds per-repo reasons plus project_pack_install steps (install / reinstall)"
  - "opengsd install/update/removal handoff text pinned to pnpm dlx @opengsd/gsd-core@1.16.0, project-local"
affects: [19-16 skill state wiring (reads repos/reasons/steps), phase 20 RECONFIGURE (runs project_pack_install steps)]

actuals:
  tokens: 21000
  tasks: 2
  commits: 2
plan_head_before: 4432bf984a4d750989ebe9718c17bc6a55e1a61e
plan_head_after: 68afb20198ae82a993ca1b1f4440b14d0ff22922

tech-stack:
  added: []
  patterns:
    - "walk queue admissions are the bound: every append (roots included) counts against _MAX_WALK_DIRS, every entry read against _MAX_WALK_ENTRIES"
    - "lstat-based checks (_lstat_mode) for roots, the repo marker and the step cwd, so a symlink is never taken for a dir"
    - "one argv builder (_project_install_step) serves the steps and the registry handoff-text test"

key-files:
  created: []
  modified:
    - installer/skill_lifecycle.py
    - installer/registry.toml
    - tests/test_skill_lifecycle.py
    - tests/test_registry.py

key-decisions:
  - "A visited dir is not listed once the admission cap is spent or at max depth: no new admission is possible, so reading its entries would be wasted work"
  - "The empty-install case takes precedence over 'not installed': a repo whose only trace is an empty opencode install gets the opencode reinstall step only, not install steps for every runtime"
  - "Reinstall steps are scoped by `present` like install steps; the reason is kept either way"
  - "Reinstall step text is `reinstall opengsd for {Label} in {repo}`; install step text is `install opengsd for {Label} in {repo}` (plan wording)"
  - "Found repos are sorted, so reasons and steps do not follow arbitrary directory listing order"
  - "The step cwd check uses lstat: the repo must be an absolute, real (non-symlink) directory at build time"

requirements-completed: [STATE-07]

duration: ~40min
completed: 2026-10-16
---

# Phase 19 Plan 21: GSD repo walk, real per-runtime installs and per-repo steps Summary

The project pack now finds GSD repos with a bounded walk under HOME. A runtime only counts as installed in a repo when it has `gsd-core/VERSION` plus at least one `gsd-*` skill or command. That removes the 2026-10-14 empty-dirs false positive, and also a stale VERSION file that sits beside other packs' skills. Each repo missing an install gets a validated `pnpm dlx @opengsd/gsd-core@1.16.0 --<runtime> --local --relative-includes` step with `cwd=<repo>`, which Phase 20 will run. opengsd's handoff text now gives the user the same pinned, project-local command.

## What was built

### Task 1: bounded repo walk and real per-runtime installs (commit 394a3fc)

- `PROJECT_ROOTS = ("git", "src", "code", "projects", "work", "dev")`, `PROJECT_RUNTIME_DIRS = {"claude": ".claude", "opencode": ".opencode"}`, `_MAX_WALK_DEPTH = 4`, `_MAX_WALK_DIRS = 5000`, `_MAX_WALK_ENTRIES = 50000`. Each constant has a one-line comment explaining why it exists.
- `_find_project_repos(home)` walks breadth-first with `os.scandir` and `entry.is_dir(follow_symlinks=False)`, using a module-level `deque`. Roots are admitted only when `lstat` shows a real dir, which rejects a symlinked root. It skips dot-names (`.venv` included) and `node_modules`. A repo is not descended into. An `OSError` on a dir skips that dir. The caps are read from module globals at call time.
- `_installed_runtimes(repo)` is described above. `inspect_project_pack` reports every repo it finds, with `()` when no runtime is installed.
- 11 new tests: `test_repo_walk_finds_planning_configs`, `test_repo_walk_skips_hidden_node_modules_and_venv`, `test_repo_walk_is_capped`, `test_repo_walk_bounds_queue_and_entries`, `test_repo_walk_rejects_a_symlinked_root`, `test_repo_walk_never_follows_symlinks`, `test_real_install_counts`, `test_empty_dirs_install_is_not_installed`, `test_stale_version_beside_unrelated_skills_is_not_installed`, `test_two_runtimes_in_one_repo`, `test_repo_walk_writes_nothing`.

### Task 2: per-repo install steps and opengsd handoff text (commit 68afb20)

- `_project_install_step(...)` is the only argv builder: `("pnpm", "dlx", f"{package}@{version}", f"--{flag}", "--local", "--relative-includes")`. It uses only constants, `PROJECT_PACK_PACKAGES` and the registry pin. It returns `None` unless the repo is an absolute, real dir.
- In `inspect_project_pack`, steps are built per repo as follows:
  - A repo with no real install and no empty trace gets the reason `not installed in {repo}` and one `install` step for each present runtime.
  - Each runtime with an empty trace (`gsd-core/VERSION` or `gsd-install-state.json` present but no content) gets `{Label} install in {repo} is empty` and a `reinstall` step, even when another runtime in the same repo is real (checker I3).
  - A runtime with no trace at all, in a repo where another runtime is real, gets no step.
  - Global-leftover reasons and steps come first, as before.
- In `registry.toml`, opengsd's text changed:
  - install: project-local, per repository, never a global install, Node >= 24, then the pinned command.
  - update: re-run the same pinned command.
  - removal: the global leftover uninstall, then a last line `pnpm dlx @opengsd/gsd-core@1.16.0 --<runtime> --local --uninstall` (`Tool.uninstall`).
  - `status` and `revision_policy` are unchanged.
- 8 new tests: `test_repo_without_any_install_gets_install_steps`, `test_empty_install_gets_a_reinstall_step`, `test_absent_runtime_gets_no_step`, `test_repo_with_one_real_runtime_gets_no_step_for_others`, `test_empty_dirs_opencode_beside_real_claude_gets_the_reinstall_step`, `test_install_step_cwd_is_validated` (both a relative home and a repo removed between discovery and step building), `test_no_step_installs_globally`, and `test_opengsd_handoff_text_matches_scope_and_pin` in tests/test_registry.py.
- Planned updates:
  - The opengsd entry of `test_shipped_skill_pack_contracts_use_only_documented_upstream_commands` now expects the pinned install fragment, `--local --relative-includes` and `--local --uninstall`.
  - `test_audit_fix_f7_opengsd_notes_node_24` keeps its Node 24 assertion and adds `"npx" not in joined and "@latest" not in joined`.

## TDD RED evidence

Task 1 (before implementation): `-k "repo_walk or real_install or empty_dirs or two_runtimes or stale_version"` gave 9 failed, 2 passed. The two passes were the hidden-skip and symlinked-root tests, which pass trivially with no walk.
```
FAILED tests/test_skill_lifecycle.py::test_repo_walk_finds_planning_configs
FAILED tests/test_skill_lifecycle.py::test_repo_walk_is_capped - AttributeErr...   (no skill_lifecycle.deque)
FAILED tests/test_skill_lifecycle.py::test_repo_walk_bounds_queue_and_entries
FAILED tests/test_skill_lifecycle.py::test_repo_walk_never_follows_symlinks
FAILED tests/test_skill_lifecycle.py::test_real_install_counts - AssertionErr...
FAILED tests/test_skill_lifecycle.py::test_empty_dirs_install_is_not_installed
FAILED tests/test_skill_lifecycle.py::test_stale_version_beside_unrelated_skills_is_not_installed
FAILED tests/test_skill_lifecycle.py::test_two_runtimes_in_one_repo - Asserti...
FAILED tests/test_skill_lifecycle.py::test_repo_walk_writes_nothing - Asserti...
E       AssertionError: assert 0 == 3   (_repos(...) == {})
```
Task 2 (before implementation): 8 failed.
```
E       AssertionError: assert () == ('not installed in app',)
E       AssertionError: assert () == ('OpenCode in...pp is empty',)
E       AssertionError: assert () == ('not install...n b is empty')
E       AssertionError: assert ('npx' not in 'After leavi... repository.'
E       AssertionError: assert [] == ['project_pack_install']
FAILED tests/test_skill_lifecycle.py::test_repo_without_any_install_gets_install_steps
FAILED tests/test_skill_lifecycle.py::test_empty_install_gets_a_reinstall_step
FAILED tests/test_skill_lifecycle.py::test_absent_runtime_gets_no_step
FAILED tests/test_skill_lifecycle.py::test_empty_dirs_opencode_beside_real_claude_gets_the_reinstall_step
FAILED tests/test_skill_lifecycle.py::test_install_step_cwd_is_validated
FAILED tests/test_skill_lifecycle.py::test_no_step_installs_globally
FAILED tests/test_registry.py::test_audit_fix_f7_opengsd_notes_node_24
FAILED tests/test_registry.py::test_opengsd_handoff_text_matches_scope_and_pin
```

## Verify results

- Task 1 gate `-k "repo_walk or real_install or empty_dirs or two_runtimes or stale_version"`: 12 passed (at least 11 required; `empty_dirs` also matches a Task 2 test).
- Task 2 gate (broad `-k`): 16 passed. Narrow count `-k "install_steps or reinstall_step or absent_runtime_gets or one_real_runtime or cwd_is_validated or installs_globally or handoff_text_matches"`: 8 passed (at least 8 required).
- `uv run pytest tests/test_skill_lifecycle.py tests/test_registry.py tests/test_model.py -n auto -q --no-cov`: all passed.
- `make validate`: exit 0 before each commit. `make test`: 4329 passed, 4 skipped, coverage 95.80% (final tree).
- Acceptance greps:
  - `_MAX_WALK_DIRS = 5000` and `_MAX_WALK_ENTRIES = 50000`: one definition each.
  - `follow_symlinks=False`: 1. `^from collections import deque`: 1.
  - `"--relative-includes"`: 1. `"--local"`: 1. `"--global", "--uninstall"`: 1.
  - `@opengsd/gsd-core@latest` in registry.toml: 0. `@opengsd/gsd-core@1.16.0`: 4.
- No new suppressions (`git diff 4432bf9` adds no `type: ignore|pyright: ignore|noqa|nosec`). `pyproject.toml` and `uv.lock` are unchanged.
- Large-file evidence:

  | File | HEAD lines | After | Tests before | Tests after | Ends with newline |
  |------|-----------:|------:|-------------:|------------:|:-----------------:|
  | tests/test_skill_lifecycle.py (Task 1) | 1867 | 2063 | 90 | 101 | yes |
  | tests/test_skill_lifecycle.py (Task 2) | 2063 | 2181 | 101 | 108 | yes |
  | tests/test_registry.py | 2573 | 2601 | 178 | 179 | yes |
  | installer/registry.toml | 3604 | 3606 | - | - | yes |

  `git diff --stat` for Task 1: skill_lifecycle.py +81/-3, test_skill_lifecycle.py +198. For Task 2: registry.toml 16 lines changed, skill_lifecycle.py 63, test_registry.py +28, test_skill_lifecycle.py +124. Across the plan: 4 files, +482/-20.

## Deviations from Plan

1. **[Rule 1 - Bug] Test helper name clash.** The new helper was first named `_pack`, which shadowed an existing `_pack(tool_id, probes)` in tests/test_skill_lifecycle.py and broke about 30 tests. I renamed it to `_gsd_pack` before committing (Task 2).
2. **Walk tests observe visits through the recording deque.** The implementation does not list a dir once the admission cap is spent, because no new admission is possible. So `test_repo_walk_is_capped` asserts exactly 5000 queue admissions (the "visited" count) and at most 5000 `scandir` calls, rather than 5000 `scandir` calls. The `scandir` and entry wrappers count only calls and entries under the test root, because the 19-11 global-leftover scan also calls `os.scandir` on HOME dirs.
3. **`_find_project_repos` sorts its result.** The plan did not ask for this. Without it, reasons and steps across several repos would follow arbitrary directory listing order.
4. **The guard scripts ran as plain commands.** The sandbox refused the plan's `bash -c` truncation and suppression guards and the compound git commands. I ran the same checks as separate commands; their results are above. The plan-head ledger file was not written for the same reason; `plan_head_before` is the wave-3 base 4432bf9.

## Issues for the orchestrator

- No files outside `files_modified` were touched.
- 19-16 (skill state wiring) can now read `ProjectPackReport.repos`, `reasons` and `steps` for project packs. Reinstall steps use the same `project_pack_install` kind as install steps, and differ only in their text.

## Self-Check: PASSED

- installer/skill_lifecycle.py, installer/registry.toml, tests/test_skill_lifecycle.py and tests/test_registry.py are all present and modified.
- Commits 394a3fc and 68afb20 are on `worktree-agent-a22f1be59dd4bcf99`.
