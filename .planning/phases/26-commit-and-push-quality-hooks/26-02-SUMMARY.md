---
phase: 26-commit-and-push-quality-hooks
plan: "02"
subsystem: installer-ui
tags: [make-run, wizard-target, hints, docs, test-pins]

# Dependency graph
requires:
  - phase: 26-commit-and-push-quality-hooks
    provides: "26-01 makes `make run` the only wizard target in the Makefile (same wave)"
provides:
  - "Every user-visible hint that named the old wizard target now names `make run`"
  - "Test pins assert the new `make run` wording with unchanged assertions"
  - "README, AGENTS.md, dev-environment table and the catalog-audit skill name `make run` as the wizard target"
affects: [26-01, HOOK-04]

# Actuals (#2632) — chars/4 over the realized diff (8106a063..HEAD, 19696 chars)
actuals:
  tokens: 4924
  tasks: 2
  commits: 2

# Measured commit ledger (#3968): git rev-list --count plan_head_before..HEAD
commits: 2
plan_head_before: 8106a063dd3f5b2553fb116f2e71989239e7ec87
plan_head_after: d444804b1c25e91bae393f051af4a2344fd69e42

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hint text pinned by startswith / in assertions; the wording changes, the assertion shape does not"

key-files:
  created: []
  modified:
    - installer/guidance.py
    - tests/test_guidance.py
    - tests/test_app.py
    - tests/test_render.py
    - tests/test_schedules_handover.py
    - tests/test_wizard_app.py
    - tests/test_setup.py
    - tests/test_tool_browser.py
    - tests/e2e_landing_driver.py
    - tests/test_catalog_audit_skill.py
    - installer/compose.py
    - setup.py
    - .claude/skills/catalog-audit/SKILL.md
    - README.md
    - AGENTS.md
    - .claude/dev-environment.md

key-decisions:
  - "Only the target name inside asserted text changed; no assertion was loosened"
  - "The `make run` alias wording is removed from product docs: `make run` is named as the wizard target"
  - "`installer/doctor_screen.py` is unchanged: its prefixes (`Run \\`make fix\\``, `Turn on tmp cleanup`) do not contain the target name"
  - "Dated records under `.planning/` and `docs/superpowers/` are left as they are (D-08)"

patterns-established:
  - "Zero-count gate: `git grep -n -w 'make setup' -- . ':!.planning' ':!docs/superpowers'` must print nothing"

requirements-completed: [HOOK-04]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "User-visible wizard hints (broken-link reinstall, pnpm globals reinstall, disk-pressure Schedules step) name `make run`"
    requirement: "HOOK-04"
    verification:
      - kind: unit
        ref: "tests/test_guidance.py#test_node_globals_guidance_warns_and_points_at_make_setup"
        status: pass
      - kind: unit
        ref: "tests/test_schedules_handover.py#test_disk_pressure_points_at_schedules"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_run_doctor_reports_missing_pnpm_globals"
        status: pass
      - kind: unit
        ref: "tests/test_render.py#test_render_node_globals_prints_finding"
        status: pass
    human_judgment: false
  - id: D2
    description: "Comments, docstrings, README, AGENTS.md, the dev-environment table and the catalog-audit skill name `make run` as the wizard target; no tracked file outside dated records names the old target"
    requirement: "HOOK-04"
    verification:
      - kind: other
        ref: "git grep -n -w 'make setup' -- . ':!.planning' ':!docs/superpowers' (empty, exit 1)"
        status: pass
      - kind: unit
        ref: "tests/test_catalog_audit_skill.py#test_skill_host_safety_text"
        status: pass
    human_judgment: false
  - id: D3
    description: "Docs no longer describe `make run` as an alias of `make setup`"
    requirement: "HOOK-04"
    verification:
      - kind: other
        ref: "grep -c 'alias for' AGENTS.md (0); git grep -n -i 'is an alias' over README.md, AGENTS.md, .claude/dev-environment.md (empty)"
        status: pass
    human_judgment: false

# Metrics
duration: unmeasured (plan start time was not recorded)
completed: 2026-11-16
status: complete
---

# Phase 26 Plan 02: Name `make run` as the wizard target in every hint, pin and doc Summary

**Every user-visible wizard hint, test pin, comment, doc and the catalog-audit skill now names `make run` as the wizard target, with no old-target reference left in tracked source outside dated records**

## Performance

- **Duration:** unmeasured (plan start time was not recorded)
- **Tasks:** 2 of 2 completed
- **Files modified:** 16

## Accomplishments
- The broken-link reinstall hint, the Doctor's pnpm-globals reinstall step and the disk-pressure Schedules step read `make run`
- The pins for those hints assert the `make run` text with the assertion shape unchanged
- README (both shell blocks, the Makefile table row, the layout line), AGENTS.md (command list, alias line removed, host-safety rule), the dev-environment table and the catalog-audit skill's host-forbidden list name `make run`
- Comments and docstrings in `setup.py`, `installer/compose.py`, and the test helpers name `make run`

## Task Commits

Each task was committed atomically (test-first: pins changed and run RED, then strings changed):

1. **Task 1: every user-visible hint names `make run`, and its pins assert the new text** - `457d728f` (fix)
2. **Task 2: comments, docstrings, the four docs and the skill name `make run`** - `d444804b` (docs)

**Plan metadata:** committed separately as `docs(26-02): complete plan` (SUMMARY only; STATE.md and ROADMAP.md are owned by the orchestrator).

## Files Created/Modified
- `installer/guidance.py` - three hint strings and the recognised-prefix comment now say `make run`
- `tests/test_guidance.py`, `tests/test_app.py`, `tests/test_render.py`, `tests/test_schedules_handover.py`, `tests/test_wizard_app.py` - pins assert `make run`
- `tests/test_setup.py`, `tests/test_tool_browser.py`, `tests/e2e_landing_driver.py`, `installer/compose.py`, `setup.py` - comments and docstrings name `make run`
- `tests/test_catalog_audit_skill.py` - skill phrase pin asserts `make run`
- `.claude/skills/catalog-audit/SKILL.md` - host-forbidden list names `make run`
- `README.md`, `AGENTS.md`, `.claude/dev-environment.md` - wizard target is `make run`, alias wording removed

## RED evidence (test-first, Task 1)

After the pins were changed and before `installer/guidance.py` was changed, the run failed (exit 1) on:

```
FAILED tests/test_guidance.py::test_node_globals_guidance_warns_and_points_at_make_setup
FAILED tests/test_guidance.py::test_node_globals_guidance_warns_on_a_split_install_group
FAILED tests/test_guidance.py::test_node_globals_guidance_reports_missing_and_split_together
FAILED tests/test_guidance.py::test_node_globals_guidance_warns_on_an_incomplete_install_group
FAILED tests/test_app.py::test_run_doctor_reports_missing_pnpm_globals
FAILED tests/test_render.py::test_render_node_globals_prints_finding
FAILED tests/test_schedules_handover.py::test_disk_pressure_points_at_schedules
```

Full output: `scratchpad/p26-02-task1-red.txt`. The wizard-app pins are negative assertions (`not in body`), so they pass before the string change; they are kept as the plan specifies.

RED for Task 2: `tests/test_catalog_audit_skill.py::test_skill_host_safety_text` failed with `AssertionError: ['make run']` before `SKILL.md` was changed.

## Decisions Made
- Assertions were not loosened; only the target name inside asserted text changed
- `installer/doctor_screen.py` was left unchanged, as the plan specifies: `_tui_guidance` matches the `Run \`make fix\`` and `Turn on tmp cleanup` prefixes, which do not contain the target name, so the rewrite still works

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Formatter reflow of one wizard-app assertion**
- **Found during:** Task 1 (`make validate`)
- **Issue:** The shorter `make run` text let one `assert not any(...)` call fit on one line; `ruff format --check` failed on `tests/test_wizard_app.py`
- **Fix:** Ran `ruff format` on that file (formatter output only; no assertion change)
- **Files modified:** `tests/test_wizard_app.py`
- **Verification:** `make validate` exit 0, then `make test` exit 0 (7662 passed, 6 skipped, 96.20% coverage)
- **Committed in:** `457d728f` (Task 1 commit)

**Total deviations:** 1 auto-fixed (1 blocking). **Impact on plan:** formatting only; no scope creep.

## Issues Encountered
- **Makefile is not yet updated in this tree.** The worktree is based on `8106a063`, whose Makefile still defines `run: setup` as an alias. The docs and hints now name `make run` as the wizard target, which is correct only once 26-01 lands in the same wave merge (the plan's Review Dispositions Ledger records this dependency as accepted).
- **Staging hint.** The first `git add` in Task 2 printed an "ignored by .gitignore" hint and returned non-zero, so the chained `git commit` did not run. `git check-ignore` on a tracked path returned no match, and the staged list was checked (11 intended files) before committing. No ignored or unintended file was staged.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None.

## Threat Flags
None. The change is text and test-pin edits; no new network, auth, file or schema surface.

## Next Phase Readiness
- Wave 1 merge: 26-01 (Makefile target) and this plan together complete D-08 and D-20 for the wizard target
- No blockers in this plan

## Self-Check: PASSED

- Files exist: `installer/guidance.py`, `.planning/phases/26-commit-and-push-quality-hooks/26-02-PLAN.md` - FOUND
- Commits are ancestors of HEAD: `457d728f` FOUND, `d444804b` FOUND
- Zero-count gate and alias gate: passed (see coverage block)
- `make validate` exit 0 and `make test` exit 0 on the Task 2 tree (`d444804b`), which equals the code tree for this plan

---
*Phase: 26-commit-and-push-quality-hooks*
*Completed: 2026-11-16*
