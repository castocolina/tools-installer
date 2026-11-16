---
phase: 18-registry-truth-and-drift-guard
plan: "05"
subsystem: infra
tags: [uv, makefile, path, reg-06, pytest]

requires: []
provides:
  - "Launch form uv run --isolated --no-dev setup.py on all Makefile launchers, install.sh, and container e2e harness"
  - "tests/test_makefile.py recipe parser guarding launcher vs gate targets"
  - "installer/locations.py::drop_project_venv_from_path called first in setup.py __main__"
affects: [18-18]

actuals:
  tokens: 8500
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Isolated no-dev uv run for installer launchers; validate/test keep dev deps"
    - "Entry-point PATH filter removes inherited <repo>/.venv entries (L-18-08)"

key-files:
  created:
    - tests/test_makefile.py
  modified:
    - Makefile
    - install.sh
    - scripts/container-e2e-verify.sh
    - installer/locations.py
    - setup.py
    - tests/test_install_sh.py
    - tests/test_locations.py
    - README.md
    - AGENTS.md
    - .claude/dev-environment.md
    - docs/TROUBLESHOOTING.md

key-decisions:
  - "REG-06/D-11 launch form is uv run --isolated --no-dev plus setup.py __main__ PATH strip (L-18-01, L-18-08)"

patterns-established:
  - "Living docs that quote a launch command commit with the launcher they describe"

requirements-completed: [REG-06]

coverage:
  - id: D1
    description: "Makefile launchers (setup, doctor, fix, uninstall, guard, unguard) use isolated no-dev form; validate/test unchanged"
    requirement: REG-06
    verification:
      - kind: unit
        ref: "tests/test_makefile.py#test_launch_targets_run_without_the_dev_venv"
        status: pass
      - kind: unit
        ref: "tests/test_makefile.py#test_gate_targets_keep_dev_dependencies"
        status: pass
    human_judgment: false
  - id: D2
    description: "install.sh and container-e2e-verify.sh launch setup.py with the same form over a dev-synced venv"
    requirement: REG-06
    verification:
      - kind: unit
        ref: "tests/test_install_sh.py#test_run_launches_wizard_with_passthrough_args"
        status: pass
    human_judgment: false
  - id: D3
    description: "Activated project venv entries are removed from PATH before setup.py main runs"
    requirement: REG-06
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_drop_project_venv_from_path_removes_only_the_project_venv"
        status: pass
      - kind: unit
        ref: "tests/test_locations.py#test_setup_entry_point_drops_the_project_venv_before_main"
        status: pass
    human_judgment: false
  - id: D4
    description: "Container pass1 reports ruff with real owner under launch form (dev-synced venv)"
    requirement: REG-06
    verification:
      - kind: e2e
        ref: "plan 18-18 container harness (backstop)"
        status: unknown
    human_judgment: true
    rationale: "Full container e2e deferred to plan 18-18 per this plan's verification backstop"

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 05 Summary

**Installer launchers use `uv run --isolated --no-dev`, and setup.py strips inherited project `.venv` PATH entries so dev tools never shadow the host.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- Six Makefile launchers and gate-preserving recipe tests in `tests/test_makefile.py`
- `install.sh`, container harness, and direct-command docs aligned on the launch form
- `drop_project_venv_from_path` at the setup.py script entry for activated-venv shells (L-18-08)

## Task Commits

1. **Task 1: Makefile launchers, recipe test, target docs** — `2ec0f9d` (feat)
2. **Task 2: install.sh, container harness, direct-command docs** — `a553e12` (feat)
3. **Task 3: entry-point PATH filter** — `a7fa634` (feat)

## TDD RED evidence (trimmed)

**Task 1:** `test_launch_targets_run_without_the_dev_venv` — `AssertionError: setup` — recipe had `uv run setup.py $(ARGS)` without `--isolated --no-dev`.

**Task 2:** `test_run_launches_wizard_with_passthrough_args` — log contained `uv run setup.py --all --yes`, not the isolated form.

**Task 3:** `ImportError: cannot import name 'drop_project_venv_from_path'` at collection (then AST assertion adjusted after GREEN for `Path(__file__).resolve().parent` shape).

## Verify results

- Task 1: `uv run pytest tests/test_makefile.py tests/test_docs.py -q --no-cov` — 8 passed; `make -n setup doctor fix uninstall guard unguard` — ok; non-activated ruff probe — exit 0
- Task 2: `uv run pytest tests/test_install_sh.py tests/test_docs.py -q --no-cov` — 16 passed; `bash -n scripts/container-e2e-verify.sh` + `shellcheck -x install.sh` — ok; `git grep uv run setup.py` on living files — exit 1 (no matches)
- Task 3: `uv run pytest tests/test_locations.py -k project_venv -q --no-cov` — 3 passed; activated PATH control finds `.venv` ruff; filtered probe exit 0
- Final: `make validate` — ok; `make test` — 3635 passed, 4 skipped, coverage 95.94%; combined plan tests — 50 passed

## Deviations from Plan

- **setup.py module docstring:** Wrapped onto multiple lines so ruff E501 (100 cols) passes; launch command text unchanged.
- **AST test:** Uses `ast.unparse` on the drop call argument instead of strict nested-Call shape (actual tree is `Path(__file__).resolve().parent`).

## Issues Encountered

None.

## Next Phase Readiness

Launch form and PATH filter are in place; plan 18-18 container backstop can assert ruff ownership under a dev-synced venv.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
