---
phase: 18-registry-truth-and-drift-guard
plan: "19"
subsystem: installer-engine
tags: [registry, smoke, manager-kind, path, ownership, REG-05]

requires:
  - phase: 18-09
    provides: smoke_binary, method_smoke_argv, download/app staging smoke
  - phase: 18-20
    provides: registry smoke_argv loader key
provides:
  - Manager-kind post-install smoke inside install_tool with bin_dir prepend, PATH restore, and fall-through
  - ownership.method_removal_command for leftover package reporting (L-18-16)
  - PATH-sandboxed tests for every default install_tool entry point in the six tripwire modules
affects: [18-18, verify-work, registry-truth]

actuals:
  tokens: 18000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Manager smoke runs in the method try after prepend_path; ExecutorError restores PATH and falls through"
    - "Leftover packages reported via method_removal_command, never uninstalled"

key-files:
  created: []
  modified:
    - installer/engine.py
    - installer/ownership.py
    - tests/test_engine.py
    - tests/test_ownership.py
    - tests/test_app.py
    - tests/test_session.py
    - tests/test_postinstall.py

key-decisions:
  - "Executable declared bin_dir/<cmd> is the smoke target; non-executable present file skips smoke with no PATH fallback (L-18-14)"
  - "Failed manager smoke reports removal command in error and postinstall_warning; installer never runs removal (L-18-16)"

patterns-established:
  - "Module-local scratch PATH autouse fixture in test_engine.py for cmd=rg install tests"
  - "Public pytest fixture name scratch_path_for_manager_smoke (pyright-visible)"

requirements-completed: [REG-05]

coverage:
  - id: D1
    description: "Manager-kind install smoke with fall-through when the binary cannot run"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_manager_install_with_a_broken_binary_falls_through"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_manager_install_with_a_working_binary_is_installed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Smoke edges — bin_dir target, PATH restore, argv, SDKMAN non-executable shape"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_engine.py -k skips_smoke or handoff_kinds or searchable_before_the_smoke or declared_argv or restores_path or is_smoked or not_smoked or falls_back_to_which"
        status: pass
    human_judgment: false
  - id: D3
    description: "Failed smoke reports removal command and never uninstalls the package"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_ownership.py#test_method_removal_command_uses_the_shared_table"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_failed_manager_smoke_reports_the_removal_command_and_never_uninstalls"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tripwire — fake rg/graphify/mmdc/omz first on PATH never execute during six-module pytest run"
    requirement: REG-05
    verification:
      - kind: unit
        ref: "plan 18-19 Task 1 bash tripwire (rc=0, no marker during pytest, marker when rg run directly)"
        status: pass
    human_judgment: false

duration: 120min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 19: Manager-kind install smoke

**Manager-installed tools are smoke-run once after each successful method (with bin_dir-aware targets and PATH restore on failure), fall through when broken, and name leftover packages with removal commands without uninstalling them.**

## Performance

- **Duration:** ~120 min
- **Tasks:** 3
- **Files modified:** 7

## Task commits

1. **Task 3 (L-18-16 helper, committed first for a green intermediate tree):** `35a2a3c` — `ownership.method_removal_command` + parametrized table tests
2. **Tasks 1–2 (engine smoke + PATH restore + leftovers):** `1e11199` — `install_tool` manager smoke ladder
3. **Tasks 1–3 (tests + PATH pins):** `6e4690d` — engine/postinstall/app/session tests and tripwire

**Plan summary:** `6b07a39`

## TDD RED (Task 1)

Before `1e11199`, with tests from `6e4690d` staged and stock `engine.py`:

```
FAILED tests/test_engine.py::test_manager_install_with_a_broken_binary_falls_through
AssertionError: assert 'brew' == 'cask'
  - cask
  + brew
```

(Brew smoke did not fail on exit 127, so the ladder never reached cask.)

## Verify results

| Command | Result |
|---------|--------|
| `uv run pytest tests/test_engine.py -q --no-cov -k "manager_install_with"` | 3 passed |
| Task 2 `-k` filter (9 tests) | 9 passed |
| Task 3 `-k "removal_command or leftover_package or own_uninstaller"` | 9 passed (incl. parametrized) |
| Task 1 tripwire bash one-liner | rc=0, clean=0, armed=0 |
| `make validate` | pass |
| `make test` | 3784 passed, 4 skipped; coverage 95.33% |

## Enumeration (committed tree, default `install` callers)

| Module | Line | Entry | Notes |
|--------|------|-------|-------|
| tests/test_engine.py | many | `install_tool` | autouse `scratch_path_for_manager_smoke`; cmd mostly `rg` |
| tests/test_postinstall.py | 555 | `install_tool` | graphify uv-tool; PATH pinned empty scratch |
| tests/test_app.py | 3370,3407,3433,3456 | `run_wizard` | `_not_present` pins PATH; omz script / rg brew |
| tests/test_session.py | 612–615, 668–669 | `with_sensitive_confirm` → `run_installs` | PATH pinned; omz script |
| tests/test_node_install_e2e.py | 63 | `install_tool` | already pinned (unchanged) |
| tests/test_skill_lifecycle.py | 454 | `install_tool` | skill_pack handoff only (never smoked) |

No additional modules with default `install` were found beyond the plan list.

## Deviations from plan

- **Commit order:** `method_removal_command` landed in commit `35a2a3c` before the engine hook so `make validate && make test` stayed green on each commit; functionally matches Task 3 then Tasks 1–2.
- **test_engine.py edits:** Large-file appends used a shell/Python patch after an edit-tool truncation corrupted the file once; final file is 1568 lines, verified with `make validate && make test`.

## Issues for orchestrator

None.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
