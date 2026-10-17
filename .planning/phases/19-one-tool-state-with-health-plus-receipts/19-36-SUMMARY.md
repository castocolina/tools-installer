---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "36"
subsystem: ui
tags: [execute-screen, health, receipts, e2e, textual]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: Health.BROKEN from receipt drift, and the UpdateService.run drift gate (19-31)
provides:
  - The execute preview refuses a BROKEN tool before the run
  - CatalogScreen._health_of is deleted
  - The container e2e pre-uninstall cd survives a spaced workspace
affects: [19-37]

actuals:
  tokens: 4278
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - A refused tool is rendered from self._refused, never from the progress map

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/test_execute_screen.py
    - installer/catalog_tui.py
    - tests/test_catalog_tui.py
    - scripts/container-e2e-verify.sh
    - tests/test_container_e2e_receipts.py
    - tests/test_shell_scripts_path.py

key-decisions:
  - "A BROKEN state with an empty reasons tuple is refused without a head line, instead of indexing reasons[0]"
  - "The PATH-scan classification follows the two export lines the workspace quote shifted (317 -> 319, 340 -> 342)"

patterns-established:
  - "A tool the run will not touch is drawn from its own list, so the run-finished sweep cannot relabel it"

requirements-completed: [STATE-02, STATE-03]

coverage:
  - id: D1
    description: "A drift-BROKEN tool is refused before the run, with its reason in the head and a not-done row from the first frame"
    requirement: STATE-02
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_drifted_tool_is_refused_before_the_run_starts"
        status: pass
    human_judgment: false
  - id: D2
    description: "The dead CatalogScreen._health_of is gone; the probe-less pack test reads health from the service"
    requirement: STATE-02
    verification:
      - kind: unit
        ref: "tests/test_catalog_tui.py#test_skill_pack_with_no_status_probes_uses_path_presence"
        status: pass
    human_judgment: false
  - id: D3
    description: "The nested pre-uninstall cd keeps a workspace path with a space as one word"
    requirement: STATE-03
    verification:
      - kind: e2e
        ref: "tests/test_container_e2e_receipts.py#test_pre_uninstall_check_survives_a_spaced_workspace"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 36: Preview honesty and cleanup Summary

**The execute preview refuses a drift-BROKEN tool before the run, the dead catalog health accessor is gone, and the e2e pre-uninstall check survives a workspace path with a space.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-10-17T00:11:10Z
- **Completed:** 2026-10-17T00:26:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- A selected tool whose state is `Health.BROKEN` (and not the pnpm-shim repair case) is refused before the run: the head prints `{id} is broken: {reason}`, the progress row reads `✖ {id} update [not done]` from the first frame, and the update service never sees it.
- `CatalogScreen._health_of` is deleted. The one test that used it reads health from the service, and `tests/test_catalog_tui.py` carries 105 `pyright: ignore` comments, one fewer.
- `assert_receipt_ready_for_removal` quotes the workspace with `printf -v workspace '%q'`, so a path with a space reaches the nested `cd` as one word.

## Task Commits

Each task was committed atomically:

1. **Task 1: a BROKEN tool is refused before the run** - `37b3d92` (fix)
2. **Task 2: delete the dead `CatalogScreen._health_of`** - `f9203a2` (refactor)
3. **Task 3: the nested pre-uninstall `cd` survives a spaced workspace** - `29b41cf` (fix)

**Review fix:** `88d3f3f` (fix) — a BROKEN state with no reason is refused, not crashed.

## Files Created/Modified

- `installer/execute_screen.py` - `_refused` classification, head line and progress row
- `tests/test_execute_screen.py` - up-front refusal regression, plus the empty-reason case
- `installer/catalog_tui.py` - `_health_of` deleted
- `tests/test_catalog_tui.py` - the probe-less pack test reads the service
- `scripts/container-e2e-verify.sh` - quoted nested workspace
- `tests/test_container_e2e_receipts.py` - spaced-workspace pre-uninstall test
- `tests/test_shell_scripts_path.py` - PATH-scan line pins follow the insertion

## Decisions Made

- A hand-built `Health.BROKEN` state with an empty `reasons` tuple is refused without printing a head line. `tool_health` never produces that state; the guard stops the preview crashing on one.
- The accumulating-PATH scan classifies by line number. Inserting two lines above the nested command moved the classified exports from 317 and 340 to 319 and 342, so the table moved with them. The reasons are unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Empty reasons must not crash the preview**

- **Found during:** final self-review of Task 1
- **Issue:** `state.reasons[0]` raises `IndexError` when a BROKEN state carries no reason. `tool_health` always pairs BROKEN with a fact, but `ToolState` allows an empty tuple.
- **Fix:** take the first reason only when one exists, and skip the head line when it does not. The progress row is still `✖ {id} update [not done]`.
- **Files modified:** `installer/execute_screen.py`, `tests/test_execute_screen.py`
- **Verification:** `test_broken_tool_with_no_reason_is_still_refused` failed with `IndexError: tuple index out of range`, then passed; `make test` → 4602 passed, 4 skipped
- **Committed in:** `88d3f3f`

**2. [Rule 3 - Blocking] PATH-scan line pins follow the insertion**

- **Found during:** Task 3 (`make test`)
- **Issue:** `test_no_unclassified_accumulating_path_line_in_any_shell_script` classifies the nested `export PATH` lines by number. The two inserted lines shifted them.
- **Fix:** re-pin 317 → 319 and 340 → 342 with the same reasons.
- **Files modified:** `tests/test_shell_scripts_path.py`
- **Verification:** the scan passes; `make test` → 4601 passed, 4 skipped
- **Committed in:** `29b41cf` (part of the Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** both keep existing checks honest. No scope creep.

## TDD RED evidence

Task 1 (`uv run pytest tests/test_execute_screen.py -q --no-cov -k "refused_before_the_run or classify_reads_the_state or refused_per_tool"`):

```
E   AssertionError: assert ['○ old updat...te [pending]'] == ['○ old updat...e [not done]']
E
E   At index 1 diff: '○ drifted update [pending]' != '✖ drifted update [not done]'
FAILED tests/test_execute_screen.py::test_classify_reads_the_state
FAILED tests/test_execute_screen.py::test_drifted_receipt_update_is_refused_per_tool
FAILED tests/test_execute_screen.py::test_drifted_tool_is_refused_before_the_run_starts
```

Task 3 (`uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -k "pre_uninstall"`):

```
E   AssertionError: TRACER_RECEIPT_PRE_UNINSTALL_MISSING tool=yq missing=valid receipt (parser exit 2)
E     bash: line 4: cd: too many arguments
FAILED tests/test_container_e2e_receipts.py::test_pre_uninstall_check_survives_a_spaced_workspace
```

Task 2 is a deletion: no RED.

## Verify-command results

- Task 1: `uv run pytest tests/test_execute_screen.py tests/test_update.py -q --no-cov` passed (193). Truncation guard: tests 112 → 113, lines 4617 → 4668. Suppressions stayed 483. `make validate && make test`: 4600 passed, 4 skipped.
- Task 2: `uv run pytest tests/test_catalog_tui.py -q --no-cov -k "probe_less or no_status_probes or group_tools or health"` passed (18); `no_status_probes` passed 2. Test count stayed 181. Suppressions 483 → 482. `make validate && make test`: 4600 passed, 4 skipped.
- Task 3: `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov` passed (10); `bash -n scripts/container-e2e-verify.sh` passed. Tests 9 → 10, lines 335 → 382. Suppressions stayed 482. `make validate && make test`: 4601 passed, 4 skipped.
- Review fix: `make validate && make test`: 4602 passed, 4 skipped, coverage 95.99%.

## Issues Encountered

- The executing-plans brief script looks for a markdown `Task N` heading. This plan uses `<task>` blocks, so the briefs were extracted into the plan workspace by hand.
- `make validate` failed once on a 108-column comment (wrapped) and once on ruff format of the review test (formatted). Both were fixed before their commits.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 19-37 can edit `installer/catalog_tui.py`; this plan's deletion is committed.
- Self-review only (the dispatch said not to use a subagent). No Critical or Important finding remains. No deferred minors.

## Rulings I made

- Task 3: the PATH-scan pins move with the inserted lines (317 → 319, 340 → 342). Cost if wrong: the scan fails, or a real new PATH line hides behind a stale number. The scan passes with the new numbers and the reasons are unchanged.
- Final: a BROKEN state with no reason prints no head line and still shows the not-done row. Cost if wrong: a reason-less broken tool shows the row without the sentence. `tool_health` never builds that state.

## Deferred minors

None.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
