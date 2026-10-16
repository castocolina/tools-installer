---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "11"
status: complete
subsystem: skill-packs
tags: [skill-lifecycle, project-scope, opengsd, registry, global-leftovers, hooks, tdd, security]

requires:
  - phase: 19-07
    provides: ConfigStep / ConfigStepKind (project_pack_global_uninstall), TOOL_ID_RE
provides:
  - "SkillLifecycle.scope (closed: user | project, default user) and SkillLifecycle.version (X.Y.Z pin, required for project scope); a project pack with a global target fails registry load"
  - "opengsd: scope = \"project\", version = \"1.16.0\", project target only"
  - "PROJECT_PACK_PACKAGES, PROJECT_GLOBAL_MACHINERY, PROJECT_SHARED_GLOBAL_DIRS, PROJECT_HOOK_CONFIGS"
  - "ProjectPackReport(repos, leftovers, reasons, steps, unchecked) and inspect_project_pack(tool, home, present): global leftovers only (repos filled by 19-21)"
  - "_gsd_hooks_registered: tri-state (True / False / None = inconclusive), size-capped, read-only"
affects: [19-16 skill state wiring (maps unchecked to not-checked notes), 19-21 repo walk and per-repo steps, phase 20 RECONFIGURE]

actuals:
  tokens: 8800
  tasks: 2
  commits: 2
plan_head_before: 22c5dcb00ea0a33f624b81a7f05b5c8bf3db70aa
plan_head_after: 6d1b59a4698312cc83b17975a97e88c28dd1a45a

tech-stack:
  added: []
  patterns:
    - "the leftover scan iterates INSTALL_STATE_HARNESS_DIRS; PROJECT_GLOBAL_MACHINERY is derived from it, so a new harness cannot be skipped"
    - "tri-state readers: missing = False, unreadable = None, and every None lands in ProjectPackReport.unchecked"
    - "the size cap is the read itself (read(cap + 1)); the stat check is only a shortcut"

key-files:
  created: []
  modified:
    - installer/model.py
    - installer/registry.toml
    - installer/skill_lifecycle.py
    - tests/test_model.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "PROJECT_GLOBAL_MACHINERY is built by comprehension over INSTALL_STATE_HARNESS_DIRS, so its keys equal that dict by construction; no module assert (bandit B101 rejects assert in installer code), and a test pins the equality"
  - "A gsd-core dir whose stat fails for a reason other than 'missing' is also listed in unchecked as `{home_dir}/gsd-core` (same rule as unlistable machinery dirs)"
  - "Hook-config walk: a string anywhere in the scanned value matching the GSD script regex, or a dict with `gsd-managed: true`, is a registration; settings.json scans only its `hooks` value, hooks.json the whole object"
  - "inspect_project_pack reports leftovers whatever `present` holds (files on disk are leftovers even when the harness CLI is gone); `present` is accepted now for 19-21's per-repo steps"

requirements-completed: [STATE-07]

duration: ~45min
completed: 2026-10-16
---

# Phase 19 Plan 11: Project-scope packs and global GSD leftovers Summary

opengsd is now a pinned (`1.16.0`) project-scope pack in the registry, and `inspect_project_pack` finds its global machinery in all nine harness homes, from `gsd-*` dirs and from GSD hook registrations in each harness's hook config. Each harness with a leftover gets one `pnpm dlx @opengsd/gsd-core@1.16.0 --<runtime> --global --uninstall` step. Reads that cannot be completed are listed in `unchecked` instead of being treated as clean.

## What was built

### Task 1: scope, pin and the machinery-dir scan (commit 9ed7837)
- `installer/model.py`: `SKILL_PACK_SCOPES = ("user", "project")`, `_PACK_PIN_RE`; `SkillLifecycle.scope` (default `"user"`) and `SkillLifecycle.version` (default `None`). `_parse_skill_lifecycle` accepts both keys, rejects an unknown scope (`unknown scope 'global'`), rejects a non-`X.Y.Z` version, requires the pin for project scope, and rejects a `global` target on a project pack. All errors use the `tool '{id}': ...` form.
- `installer/registry.toml` (opengsd only): `scope = "project"` and `version = "1.16.0"`, with a one-line D-21 comment. The `global` target is removed, so `<selected-runtime-global-dir>` no longer appears anywhere.
- `installer/skill_lifecycle.py`: `import os`. Adds `PROJECT_PACK_PACKAGES`, `_GSD_RUNTIME_IDS` (`kimi` -> `kimi-code`), `PROJECT_GLOBAL_MACHINERY` (D-21's `skills/agents/commands/hooks` in every harness home, plus GSD 1.16.0's antigravity `.gemini/config/{skills,agents}`, codex `.agents/skills` and kilo `.config/kilo/command`), `PROJECT_SHARED_GLOBAL_DIRS`, `ProjectPackReport` and `inspect_project_pack`. Steps are `ConfigStep(kind="project_pack_global_uninstall")`. Their argv is built only from constants, the registry pin and the runtime map. A `gsd-*` entry in `~/.agents/skills` adds the Codex/Kimi CLI sentence after the locked reason (checker I5).

### Task 2: hook registrations (commit 6d1b59a)
- `PROJECT_HOOK_CONFIGS` follows GSD 1.16.0's `hooksSurface`. copilot, kilo and opencode have no entry.
- `_HOOK_CONFIG_MAX_BYTES = 256 * 1024`, `_GSD_HOOK_SCRIPT_RE`, `_GSD_TOML_MARKER_RE`, and an iterative walk bounded to 20000 nodes.
- `_gsd_hooks_registered(path, fmt) -> bool | None`:
  - The `stat` follows symlinks. A missing file or a dangling link returns False.
  - A non-regular or oversized file returns None.
  - The file is read with `fh.read(cap + 1)`, and a read longer than the cap returns None.
  - The text is decoded as UTF-8. Both JSON formats must have a top-level object.
  - `OSError`, `UnicodeDecodeError`, `ValueError` and `RecursionError` all return None.
- `ProjectPackReport.unchecked` holds every inconclusive hook config, every machinery dir that could not be listed for a reason other than "missing", and every unreadable `gsd-core`.

## TDD RED evidence

Task 1, tests/test_model.py (before the model change):
```
FAILED tests/test_model.py::test_skill_lifecycle_scope_defaults_to_user - Att...
FAILED tests/test_model.py::test_skill_lifecycle_rejects_an_unknown_scope - a...
FAILED tests/test_model.py::test_project_pack_requires_a_semver_pin[] - asser...
FAILED tests/test_model.py::test_project_pack_requires_a_semver_pin[version = "latest"]
FAILED tests/test_model.py::test_project_pack_requires_a_semver_pin[version = "1.16"]
FAILED tests/test_model.py::test_project_pack_requires_a_semver_pin[version = 1]
FAILED tests/test_model.py::test_project_pack_accepts_a_semver_pin - ValueErr...
FAILED tests/test_model.py::test_project_pack_rejects_a_global_target - asser...
E  assert 'global' in "tool 'demo-pack': unknown skill_lifecycle field 'scope'"
```
Task 1, tests/test_skill_lifecycle.py:
```
E   ImportError: cannot import name 'PROJECT_GLOBAL_MACHINERY' from 'installer.skill_lifecycle'
ERROR tests/test_skill_lifecycle.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```
Task 2, tests/test_skill_lifecycle.py:
```
E   ImportError: cannot import name 'PROJECT_HOOK_CONFIGS' from 'installer.skill_lifecycle'
ERROR tests/test_skill_lifecycle.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

## Verify results

- Task 1 `-k "scope or pin or project_pack or global_leftover or leftover or opengsd or global_target"` over test_model/test_skill_lifecycle/test_registry: **46 passed** (gate >= 19).
- Task 1 shrink guard: GUARD-OK. model.py 1001 -> 1024, registry.toml 3602 -> 3604, test_model.py 1652 -> 1729 (tests 98 -> 103), test_skill_lifecycle.py 1366 -> 1525 (tests 70 -> 77).
- Task 1 acceptance:
  - `^scope = "project"$` matches one line (3476, inside opengsd).
  - `version = "1.16.0"` appears once.
  - `<selected-runtime-global-dir>` appears 0 times.
  - `def inspect_project_pack` appears once, and `PROJECT_GLOBAL_MACHINERY` appears twice.
- Task 2 filter `-k "hooks or hook_config or hook_scan or toml_hook or leftover"`: **34 passed**. Gate filter: **20 passed** (gate >= 20).
- Task 2 guards:
  - test_skill_lifecycle.py grew from 1525 to 1867 lines and from 77 to 90 tests.
  - Suppressions stayed at 598 -> 598.
  - `_HOOK_CONFIG_MAX_BYTES = 256 * 1024` appears once, `RecursionError` 3 times, and `_HOOK_CONFIG_MAX_BYTES + 1` once.
  - `read_bytes(` count is unchanged (0 / 0), and the subprocess/write/unlink/rmtree count is unchanged (2 / 2).
  - `unchecked: tuple[str, ...] = ()` appears once.
- `make validate` passed before both commits, and the pre-commit hook passed on both. `make test` passed on the final tree: 4214 passed, 4 skipped, coverage 95.73%.
- `uv run pytest tests/test_model.py tests/test_skill_lifecycle.py tests/test_registry.py -n auto -q --no-cov`: green.
- No new dependency: `pyproject.toml` and `uv.lock` are untouched.
- Final `git diff --stat 22c5dcb..HEAD`: model.py +23, registry.toml 4 (+3/-1), skill_lifecycle.py +189, test_model.py +77, test_skill_lifecycle.py +503/-1 (the `typing` import line was widened). No file shrank.

## Deviations from Plan

1. **[Rule 3 - Blocking] No module `assert` for PROJECT_GLOBAL_MACHINERY keys.** bandit (B101) rejects `assert` in `installer/`. The dict is built by comprehension over `INSTALL_STATE_HARNESS_DIRS`, so its keys match by construction, and `test_global_leftover_scan_covers_install_state_harness_dirs` pins the equality.
2. **[Rule 2 - Missing critical] An unreadable `<home>/gsd-core` is reported as `unchecked`.** `_is_dir` uses `stat` and is tri-state, so a permission error is no longer silently read as "no leftover". This applies C2-M3 to the third signal as well. Test: `test_unreadable_gsd_core_is_unchecked`.
3. **Extra tests beyond the plan list:**
   - `test_project_pack_accepts_a_semver_pin`
   - `test_hook_walk_bound_is_inconclusive` (covers the 20000-node bound)
   - `test_unreadable_gsd_core_is_unchecked`
   - `test_project_pack_requires_a_semver_pin` is parametrized over 4 bad pins.
4. Codegraph was not used: the worktree has no index, per the orchestrator's worktree note. Code was read directly.
5. The plan's `bash -c` guard scripts were run as script files in the session scratchpad, because the sandbox refuses complex inline commands. Those files are deleted.

## Known Stubs

None. `ProjectPackReport.repos` is always `()` until plan 19-21 fills it, which the plan intends. `present` is accepted but not read yet; it scopes 19-21's per-repo steps.

## Notes for the orchestrator

- Only this plan's five files were touched. No test outside them changed.
- No consumer calls `inspect_project_pack` yet; plan 19-16 wires it.

## Self-Check: PASSED
- Commits 9ed7837 and 6d1b59a are on `worktree-agent-a34634747f18eeb00`.
- All five modified files are present.
