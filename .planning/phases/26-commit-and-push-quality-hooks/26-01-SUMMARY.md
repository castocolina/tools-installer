---
phase: 26-commit-and-push-quality-hooks
plan: "01"
subsystem: infra
tags: [makefile, pre-commit, git-hooks, pytest, wiring, pyproject, devtools]

# Dependency graph
requires: []
provides:
  - "Six [gate]-marked make targets (lint, format-check, typecheck, security, dead-code, shellcheck); test is marked too"
  - "validate is exactly pre-commit run --all-files, so a new gate is one Makefile target plus one hook entry"
  - "Seven-hook .pre-commit-config.yaml: six static gates at commit and push, make test last and push-only"
  - "devtools/ package joined to the lint, format-check, security, pyright, coverage and vulture scopes"
  - "make run as the wizard target; the setup target is gone; make help lists names with digits"
  - "tests/test_hook_wiring.py: wiring_errors drift checker plus the P1 bypass and P3 auto-fix pins"
affects: [26-02, 26-04, 26-05, 26-06, 26-07, 26-09]

# Actuals (#2632) — chars/4 over the realized diff (25107 bytes), not a harness token count.
actuals:
  tokens: 6277
  tasks: 3
  commits: 3   # MEASURED at SUMMARY write: git rev-list --count 8106a063..HEAD (the SUMMARY commit is not counted)
plan_head_before: 8106a063dd3f5b2553fb116f2e71989239e7ec87
plan_head_after: 016adef0101577bda2eb564f637675e6485c535a

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gate marker: a Makefile target whose ## help text starts with [gate] is a gate; gate_targets() reads it"
    - "Pure wiring_errors(hooks, recipe_map, gates) checker shared by real-file pins and synthetic drift cases"

key-files:
  created:
    - devtools/__init__.py
    - tests/test_hook_wiring.py
  modified:
    - Makefile
    - .pre-commit-config.yaml
    - pyproject.toml
    - tests/test_makefile.py

key-decisions:
  - "The gate set comes from the Makefile [gate] marker via gate_targets(), never a literal set in a test (review M1)"
  - "Every static hook is entry make <target>, language system, pass_filenames false, always_run true, stages [pre-commit, pre-push], so an empty changed-file set still runs every gate"
  - "default_install_hook_types is [pre-commit] and there is no top-level fail_fast, so the commit stage reports every failing gate"
  - "A hook with no stages key counts as a commit-stage hook in the test helpers, so an unstaged hook cannot pass the wiring pins silently"
  - "Task 1 test names stay as direct assertions on the real files; wiring_errors carries the set, order and zero-check drift and the synthetic cases"
  - "The duplicate-code gate is not added; it is Backlog 999.17 (D-13)"

patterns-established:
  - "Each gate is one [gate]-marked make target whose recipe holds the command once; hooks call make <target>"
  - "Pins follow the hook entry into the Makefile recipe (P1 and P3), not a grep over the hook file"

requirements-completed: [HOOK-01, HOOK-02, HOOK-04]

coverage:
  - id: D1
    description: "Six static gates are make targets, validate is pre-commit run --all-files, and each commit hook calls its target"
    requirement: "HOOK-01"
    verification:
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_commit_stage_targets_equal_the_gate_targets_as_a_set"
        status: pass
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_validate_is_exactly_pre_commit_run_all_files"
        status: pass
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_every_commit_hook_calls_an_existing_gate_target"
        status: pass
    human_judgment: false
  - id: D2
    description: "The push stage runs every static gate, then make test last; pre-commit installs only the commit hook"
    requirement: "HOOK-02"
    verification:
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_push_stage_runs_every_gate_then_test"
        status: pass
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_the_test_hook_is_push_only_and_last"
        status: pass
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_pre_commit_installs_only_the_commit_hook"
        status: pass
    human_judgment: false
  - id: D3
    description: "make run launches the wizard, setup is removed, and make help lists names with digits"
    requirement: "HOOK-04"
    verification:
      - kind: unit
        ref: "tests/test_makefile.py#test_run_launches_the_wizard_and_setup_is_gone"
        status: pass
      - kind: unit
        ref: "tests/test_makefile.py#test_help_lists_names_with_digits"
        status: pass
    human_judgment: false
  - id: D4
    description: "devtools/ is under pyright, coverage, vulture, ruff, bandit and format-check and stays out of the wheel"
    requirement: "HOOK-01"
    verification:
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_devtools_joins_every_gate"
        status: pass
    human_judgment: false
  - id: D5
    description: "No gate file offers a hook bypass (P1) and no hook auto-fixes files (P3)"
    requirement: "HOOK-02"
    verification:
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_no_gate_file_offers_a_hook_bypass"
        status: pass
      - kind: unit
        ref: "tests/test_hook_wiring.py#test_no_hook_auto_fixes_files"
        status: pass
    human_judgment: false

# Metrics
duration: 14min
completed: 2026-11-16
status: complete
---

# Phase 26 Plan 01: Every static gate runs through its own make target at commit and push Summary

**Six named make gates, a seven-hook pre-commit config that calls them at commit and push with make test last at push, make validate as pre-commit run --all-files, and wiring pins that fail when a hook and a gate target drift apart**

## Performance

- **Duration:** 14 min (wall clock; the ledger file, created at plan start, sets the start time)
- **Started:** 2026-11-16T15:14:26Z
- **Completed:** 2026-11-16T15:28Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- Each static gate is one make target with its command written once: `lint`, `format-check`, `typecheck`, `security`, `dead-code`, `shellcheck`. The help text of each gate and of `test` starts with `[gate] `, and `gate_targets()` reads that marker.
- `make validate` is `uv run pre-commit run --all-files` and names no gate itself. Each static hook is `entry: make <target>` with `stages: [pre-commit, pre-push]`.
- The push stage runs the six gates, then `make test`. The `tests` hook is push-only and the last hook in the file. `default_install_hook_types: [pre-commit]` is set and there is no top-level `fail_fast`.
- `devtools/` joins the lint, format-check and security recipes, pyright `include`, coverage `source` and vulture `paths`. The wheel still ships only `installer`.
- `make run` holds the wizard recipe with no prerequisite. The `setup` target and its alias are gone. `make help` lists `e2e` and any other name with digits.
- `tests/test_hook_wiring.py` pins the wiring: the real-file checks, the `wiring_errors` drift checker with synthetic cases (zero checks, extra argument, missing target, gate with no hook, new `[gate]` target with no hook, `make test` moved before a static hook, reordered static hooks accepted), and the P1 and P3 pins.

## Task Commits

Each task was committed atomically:

1. **Task 1: every static gate runs through its own make target, and validate runs them through pre-commit** - `67d62acc` (feat)
2. **Task 2: the push stage ends with make test; pre-commit installs only the commit hook; no hook auto-fixes or offers a bypass** - `e9f7f75a` (feat)
3. **Task 3: make run is the wizard target, setup is gone, make help shows names with digits** - `016adef0` (feat)

**Plan metadata:** recorded in the docs commit that adds this file (SUMMARY only; see Self-Check).

## Files Created/Modified

- `Makefile` - six `[gate]` targets, `validate` as pre-commit, `run` as the wizard target, `setup` removed, help grep widened to digits
- `.pre-commit-config.yaml` - `default_install_hook_types`, six static hooks as `make <target>` at both stages, `tests` hook last at push
- `pyproject.toml` - `devtools` added to `[tool.pyright] include`, `[tool.coverage.run] source` and `[tool.vulture] paths`; wheel `packages` left as `installer`
- `devtools/__init__.py` - one-line docstring; developer tooling kept out of the wheel
- `tests/test_makefile.py` - `_recipes` renamed to public `recipes()`, new `gate_targets()`, launch and gate-recipe pins updated for `run`, phony and help pins added
- `tests/test_hook_wiring.py` - new: wiring tests, `wiring_errors`, P1 and P3 pins

## Decisions Made

- The gate set is read from the Makefile `[gate]` marker, not a hard-coded set (review M1). A new gate target with no hook fails `wiring_errors`.
- Hooks carry `language: system`, `pass_filenames: false` and `always_run: true`, so a push or commit with no changed files still runs every gate.
- Test helpers treat a hook with no `stages` key as a commit-stage hook. This makes the RED state of the commit-stage pins real and stops an unstaged hook from slipping past them.
- The Task 1 test names stay as direct assertions on the real files, which keeps every behaviour asserted. `wiring_errors` covers the set, order and zero-check drift and the synthetic cases.
- The duplicate-code gate is not added; it is Backlog 999.17 (D-13).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] devtools docstring over the line-length limit**
- **Found during:** Task 1 (`make validate`, `make lint`)
- **Issue:** the first `devtools/__init__.py` docstring was 119 characters; `E501` allows 100
- **Fix:** shortened the docstring to one line under 100 characters
- **Files modified:** `devtools/__init__.py`
- **Verification:** `make validate` green; `make test` green
- **Committed in:** `67d62acc` (Task 1 commit, after the fix)

**2. [Rule 1 - Bug] pyright strict partial-unknown in a new test fixture**
- **Found during:** Task 2 (`make validate`, `make typecheck`)
- **Issue:** `grown_map = {**recipe_map, "complexity": ([], [...])}` left the empty-list literal partially unknown
- **Fix:** annotated the fixture as `new_gate: tuple[list[str], list[str]]` before merging it into the map
- **Files modified:** `tests/test_hook_wiring.py`
- **Verification:** `make validate` green (pyright 0 errors); `make test` green
- **Committed in:** `e9f7f75a` (Task 2 commit)

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs, both caught by the gates before any commit)
**Impact on plan:** None on scope or behaviour. Both were typing and lint fixes in the new code.

## TDD Gate Compliance

`workflow.tdd_mode` is true in `.planning/config.json`, so the RED/GREEN gate applies to this `type: tdd` plan. The plan specifies one commit per task, and this plan follows that rule, so the gate is only partly met:

- **RED commit missing:** no `test(26-01):` commit exists. `git log -E --grep='^test\((0*26)-(0*1)\):'` returns 0 commits. Each task's tests were written and run to fail before its implementation, then committed together with that implementation as one `feat(26-01):` commit. This is the violation flagged under "Missing RED commit" in `gsd-core/references/tdd.md`. It is not repaired by rewriting history.
- **GREEN commits present:** three `feat(26-01):` commits (`67d62acc`, `e9f7f75a`, `016adef0`).
- **REFACTOR:** none recorded. No separate refactor commit.
- **RED evidence, by task (captured in-session, from pytest runs with `-n 0 --no-cov`):**
  - Task 1 RED: 5 failed, 0 passed on the target tests. The failures were assertion errors, not import or collection errors. Commit-stage targets were the raw `uv run ...` entries; `validate` listed six `uv run` lines; `devtools` was absent from pyright `include`. `gate_targets()` returned an empty list at HEAD. `tests/test_makefile.py` and reachability still passed.
  - Task 2 RED: 5 failed on assertions (no `tests` hook, so `0 == 1`; push stage ended in `shellcheck`; `default_install_hook_types` was `None`; `wiring_errors` reported the missing push-stage `test`). 13 passed, including the P1 and P3 pins, which are pins by design and pass at HEAD.
  - Task 3 RED: 4 failed on assertions (`run` had no wizard recipe; `run` still had prerequisite `setup`; the launcher list still began with `setup`; the help grep still lacked `0-9`).
- **Machine classification not run:** `gsd_run check tdd-red-evidence` was not run, because the RED runs were not persisted as classifier records with unfiltered output. The RED assessment above is a semantic inspection of those runs, not a `RED_EVIDENCE_OK` verdict.

## Issues Encountered

- **Wave dependency on 26-02 (not a deviation):** `make setup` still appears in product hint text and tests: `installer/guidance.py`, `installer/compose.py`, `tests/test_app.py`, `tests/test_wizard_app.py`, `tests/test_catalog_audit_skill.py`, `AGENTS.md`, `.claude/dev-environment.md`, `.claude/skills/catalog-audit/SKILL.md`. The plan leaves those edits to 26-02 in the same wave, and no test checks that hint text names a Makefile target. Until 26-02 merges, the user-facing hints name a removed target (`make run` is the replacement). The orchestrator should merge 26-02 with this wave.
- The worktree guard rejected several compound shell commands; those were split into plain commands. This had no effect on the result.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern or schema change at a trust boundary was introduced. Threat-register mitigations T-26-01 (P1 bypass pin), T-26-02 (P3 auto-fix pin) and T-26-03 (`wiring_errors` drift guard, zero-check and marker-driven gate set) are implemented as the plan specifies. T-26-SC is accepted: no package was added, and `uv sync` installed only the existing locked dependencies.

## Next Phase Readiness

- The gate set, the hook entries and the wiring pins are in place for 26-02 (docs and hint rename), 26-04 (devtools hooks installer and push gate) and 26-05 (install target and devtools coverage).
- `make validate` now runs pre-commit, so every commit runs the six gates. Expect the commit hook to take about a minute.
- Blocker for the wave: 26-02 must land with this plan, because the hint text it renames still names the removed `setup` target until then.

## Self-Check

Checked after writing this file, before the docs commit:

- Created files exist: `devtools/__init__.py` and `tests/test_hook_wiring.py`.
- Task commits exist in the branch history: `67d62acc`, `e9f7f75a`, `016adef0`.
- `make validate` and `make test` were green on the final task tree (`016adef0`): `make test` reported 7682 passed and 6 skipped, coverage 96.20%.
- STATE.md and ROADMAP.md were not modified. REQUIREMENTS.md was not modified: `requirements.ready-ids` returned `ready: []` and `blocked: [HOOK-01, HOOK-02, HOOK-04]`, because sibling plans declare the same IDs.

## Self-Check: PASSED

---
*Phase: 26-commit-and-push-quality-hooks*
*Completed: 2026-11-16*
