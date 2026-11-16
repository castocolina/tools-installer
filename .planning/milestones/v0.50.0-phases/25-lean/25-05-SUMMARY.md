---
phase: 25-lean
plan: "05"
subsystem: composition-root
tags: [compose, setup, pyright-strict, sandbox, test-patching, lean]
status: complete

requires:
  - phase: 25-01
    provides: tests/test_reachability.py import-graph guard (compose.py is reachable from setup.py)
  - phase: 25-03
    provides: install_tool keeps only the checksum_policy and repair keyword options
provides:
  - installer/compose.py, the composition root under pyright strict, coverage, bandit and vulture
  - a setup.py reduced from 1489 to 663 lines (argument parsing, tty and questionary plumbing, the _run_* routes)
  - tests/compose_patch.py patch_composition, the one way a test patches a name the composition code reads
  - an autouse sandbox that re-roots the home constants of both setup and installer.compose
affects: [25-lean later plans that edit setup.py, tests/test_setup.py or the composition code]

actuals:
  tokens: 38678    # 154710 diff characters / 4
  tasks: 3
  commits: 3
commits: 3
plan_head_before: a6d1af5930926f7970e5a9cef45e7ca31530732a
plan_head_after: fc892f90291d5e63f99fdfba8f07029e211199cf

tech-stack:
  added: []
  patterns:
    - "Composition lives in installer/compose.py; setup.py imports back only what its routes call"
    - "A test patches a composition name through patch_composition, which patches every module that binds it and raises when none does"
    - "Private names kept across the move are listed in compose.__all__ so pyright strict sees them as the module surface"

key-files:
  created:
    - installer/compose.py
    - tests/compose_patch.py
    - .planning/phases/25-lean/25-05-SUMMARY.md
  modified:
    - setup.py
    - tests/conftest.py
    - tests/test_sandbox.py
    - tests/test_setup.py
    - tests/test_schedules_handover.py
    - tests/test_schedule_update.py
    - tests/test_versions.py
    - tests/test_reachability.py
    - Makefile
    - .claude/architecture.md
    - README.md

key-decisions:
  - "Moved names keep their names (D-05); the 18 helpers, classes and two entry functions moved verbatim in source order, found by an AST closure pass that reported no moved def referencing a staying one."
  - "compose.py declares __all__ with the private names setup.py imports back; without it pyright strict reports reportUnusedFunction for every one of them (see Deviations)."
  - "_build_services._install types **options as Unpack[_InstallOptions] (TypedDict total=False: checksum_policy, repair) and forwards it unchanged, so an omitted key stays omitted (review R3-03)."
  - "_schedule_context binds checkout=Path(__file__).resolve().parent.parent, the repository root, the one allowed non-verbatim edit beside _REGISTRY (review R1-15)."
  - "Test reads of a moved name go through setup only while setup binds it; setup._execute_inputs, setup.install_tool, setup.resolve_github_tag and setup.diskusage became compose or module-object references."

patterns-established:
  - "patch_composition(monkeypatch, name, value): patch each of installer.compose and setup that binds name"

requirements-completed: [LEAN-02]

duration: 95min
completed: 2026-11-15
---

# Phase 25 Plan 05: Composition root moved to installer/compose.py Summary

App composition moved out of `setup.py` into `installer/compose.py` in three green commits (constants and sandbox, helper closure, then `_build_app` and `_execute_inputs`), with a generalized home sandbox, `patch_composition` for the ~140 moved test patches, and a structural guard that compose imports neither questionary nor prompt_toolkit.

## Commits

| Task | Commit | What |
| ---- | ------ | ---- |
| 1 | 301362d6 | 12 path and environment constants live once in compose; sandbox re-roots both modules; `test_no_compose_home_constant_points_at_the_real_home` |
| 2 | 12a59e49 | 16 probes, services and schedule helpers move; `patch_composition`; source scans retargeted |
| 3 | fc892f90 | `_build_app`, `_execute_inputs` move; `test_composition_lives_in_compose_not_setup`; Makefile, architecture, README |

## RED run (Task 1, never committed alone)

With compose.py holding the constants and the fixture not yet generalized:

```
>       assert not Path(os.path.realpath(item)).is_relative_to(real_home), name
E       AssertionError: _DEFAULT_BIN_DIR
E       assert not True
E        +  where True = is_relative_to(PosixPath('/var/home/bazzite'))
E        +    where is_relative_to = PosixPath('/var/home/bazzite/.local/bin').is_relative_to
FAILED tests/test_sandbox.py::test_no_compose_home_constant_points_at_the_real_home
```

GREEN after `sandboxed_setup_paths` looped over `setup` and `installer.compose`.

## Verification

- `make validate && make test` exit 0 on every commit's tree; final run: 7609 passed, 6 skipped, total coverage 96.14 percent (floor 90).
- Coverage row: `installer/compose.py  237 stmts, 3 missed, 98%` (lines 823-825).
- `uv run pyright installer/compose.py`: 0 errors, no new suppression. The only new `# pyright: ignore[reportPrivateUsage]` text is the existing comment moving with `_execute_inputs` lines whose receiver changed from `setup` to `compose`.
- `p25-patch-audit.py`: 0 findings (it reported 101, then 46, then 4 on the way, each fixed).
- `p25-d12-guard.py d0d88257feec3895ee51d1b0050b47cabc3f9888`: exit 0, 25 `--all` tests checked, assert and decorator segments identical; tests/test_cli.py and tests/test_install_sh.py byte-identical.
- Acceptance greps: 12 constants in compose and 0 in setup; `_build_app`/`_execute_inputs` 2 in compose and 0 in setup; `checkout=...parent.parent,` 1 in compose and `checkout=...parent,$` 1 in setup; checkout assert unchanged and passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyright strict reportUnusedFunction on kept private names**
- **Found during:** Task 2, first `pyright installer/compose.py`
- **Issue:** The plan lists only the `**options` and redeclaration sites, but a module-private function that nothing in the same module accesses is an error in strict mode. Thirteen moved names, and later `_build_app`, are used only by setup.py (outside pyright's include). Renaming them public would contradict D-05 and the test patch names.
- **Fix:** `__all__` in compose.py listing the private names setup imports back, with a two-line comment saying why. No suppression comment.
- **Files modified:** installer/compose.py
- **Commit:** 12a59e49, extended in fc892f90 with `_build_app`

**2. [Rule 3 - Blocking] ruff pruned setup.py imports that tests patched**
- **Found during:** Task 3
- **Issue:** after the final move, names setup no longer reads (`load_categories`, `perform_uninstall`, `run_doctor`, ...) lost their setup bindings, so plain `setattr(setup, ...)` patches would raise.
- **Fix:** the audit script found each remaining site and a rewrite script turned them into `patch_composition` calls (42 more sites in Task 3, 97 in Task 2).
- **Commit:** fc892f90

### Scope notes

- Stale prose that names `setup.py::_timer_state_cache`, `setup.py::_ZSHRC`, `setup.py::_build_app` and `setup.py::_current_link_mode` remains as comments in installer/systemd_daemon.py, installer/terminal_shell.py, installer/wizard_app.py and installer/settings.py. They are outside this plan's `files_modified` and other wave-3 plans may edit those files, so they were left; they are comment-only and a later plan can reword them.
- The plan's `files_modified` lists tests/test_systemd_daemon.py; it has no `setup` patch site, so it did not change.

## Auth gates

None.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path or file access pattern; the home-constant surface moved with its sandbox coverage (T-25-11), patches reach moved code through `patch_composition` and the audit (T-25-12), and the structural test guards the import boundary (T-25-13).

## Self-Check: PASSED

- installer/compose.py, tests/compose_patch.py FOUND
- commits 301362d6, 12a59e49, fc892f90 are ancestors of HEAD
