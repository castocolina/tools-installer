---
phase: 18-registry-truth-and-drift-guard
plan: "20"
subsystem: registry
tags: [registry, smoke_argv, model, toml, docs]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: METHOD_PARAMS closed keys and script args validation shape (plans 18-01, 18-06, 18-08)
provides:
  - smoke_argv registry key with closed-shape validation on binary-installing kinds
  - Authoring guidance for smoke_argv in architecture.md and tool-onboarding skill
  - Registry comments aligned with current download.py (no deleted helper names)
affects: [18-19, executors smoke runs]

actuals:
  tokens: 2100
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "smoke_argv is argument tail only; argv[0] is always the installed path"
    - "Node smoke name key stays separate from smoke_argv (two trust models)"

key-files:
  created: []
  modified:
    - installer/model.py
    - tests/test_model.py
    - .claude/architecture.md
    - .claude/skills/tool-onboarding/SKILL.md
    - installer/registry.toml
    - tests/test_registry.py

key-decisions:
  - "smoke_argv admitted on all METHOD_PARAMS kinds except host_setup, skill_pack, and rpm_ostree"
  - "Validation reuses _SCRIPT_ARG_RE and mirrors script args list shape"

patterns-established:
  - "Registry smoke customization via smoke_argv list, not a command string"

requirements-completed: [REG-05]

coverage:
  - id: D1
    description: smoke_argv loads on binary-installing kinds with closed character-set validation
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_model.py#test_smoke_argv_is_accepted_on_binary_installing_kinds"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_smoke_argv_shape_is_validated"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_smoke_argv_is_rejected_where_nothing_is_installed"
        status: pass
      - kind: unit
        ref: "tests/test_model.py#test_node_smoke_name_is_unchanged_by_smoke_argv"
        status: pass
    human_judgment: false
  - id: D2
    description: Authoring docs and registry comments describe smoke_argv and current extraction behavior
    requirement: REG-05
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_kitty_entry_records_why_it_uses_the_vendor_script"
        status: pass
      - kind: unit
        ref: "tests/test_registry.py#test_no_registry_comment_names_a_deleted_download_function"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 20 Summary

**Registry `smoke_argv` key with closed-shape validation, authoring docs for staged vs manager smoke, and kitty/wezterm comments that match current download code**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Added `smoke_argv` to `METHOD_PARAMS` for every binary-installing kind (excluding `host_setup`, `skill_pack`, `rpm_ostree`) with non-empty list validation using `_SCRIPT_ARG_RE`.
- Documented staged pre-link smoke for download/app kinds, post-install manager smoke when a runnable target exists, and `smoke_argv` vs node `smoke` in architecture and tool-onboarding skill.
- Updated kitty and wezterm registry comments; drift tests no longer assert deleted download helper names or gzip-only `tar -xzf`.

## Task Commits

1. **Task 1: smoke_argv loader key (D-06)** — `d785bf8` (feat)
2. **Task 2: docs and registry comments** — `a1c08ee` (docs)

## TDD RED evidence

Task 1 (before `installer/model.py` changes):

```
FAILED ... test_smoke_argv_is_accepted_on_binary_installing_kinds[script-...]
ValueError: tool 'demo': method 'script' has unknown key 'smoke_argv'
```

Task 2 (before registry comment edits):

```
FAILED ... test_kitty_entry_records_why_it_uses_the_vendor_script
AssertionError: missing 'archive = "xz"' above id = "kitty"
FAILED ... test_no_registry_comment_names_a_deleted_download_function
AssertionError: assert '_install_unverified' not in ...
```

## Verify results

- `uv run pytest tests/test_model.py -q --no-cov -k "smoke_argv or smoke_name_is_unchanged"` → 13 passed
- `uv run pytest tests/test_registry.py -q --no-cov -k "kitty_entry_records_why or deleted_download_function"` → 2 passed
- `make validate` → exit 0
- `make test` → 3735 passed, coverage 95.99%
- Registry diff comment-only check before Task 2 commit → 0 non-comment line changes

## Deviations from Plan

None — plan executed as written. `.claude/` paths required `git add -f` because parent `.claude` is gitignored while these files remain tracked.

## Issues Encountered

None for the orchestrator.

## User Setup Required

None.

## Next Phase Readiness

Plan 18-19 can load `smoke_argv` through `load_tools`. Plan 18-09 executors already consume `method_smoke_argv` when present.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
