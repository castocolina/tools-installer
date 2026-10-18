---
phase: 20-install-plan-with-dispositions
plan: "12"
subsystem: tui-install-execution
tags: [Textual, Rich, pytest, execute-screen, refresh]

# Dependency graph
requires:
  - phase: "20-10"
    provides: "Plan-driven ExecuteScreen and its version refresh service."
provides:
  - "A whole-catalog refresh wait that rebuilds and paints the plan before starting."
  - "Escape cancellation with stale-publication protection and retryable refresh errors."
affects: ["20-13 review interactions", "Phase 21 refresh ownership"]

# Actuals (#2632): 25,167 diff characters / 4, rounded to the nearest token.
actuals:
  tokens: 6292
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Join the catalog's single refresh flight through one thread worker."
    - "Tag wait results so canceled publications cannot repaint or start a run."
    - "Use Rich Text.truncate to fit error details while preserving required status copy."

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/state_doubles.py
    - tests/test_execute_screen.py

key-decisions:
  - "Refresh with the whole catalog so ExecuteScreen joins the shared state flight."
  - "After Escape, skip one pre-wait replan; the next Enter waits for a current-token settlement."
  - "Truncate only the error detail to preserve the retry suffix within 78 cells."

patterns-established:
  - "A canceled wait bumps its token; stale settlement messages return before touching screen state."
  - "A refresh error or missing publication leaves rows checking and offers Enter to retry."

requirements-completed: [PLAN-07]
coverage:
  - id: D1
    description: "Enter waits for the whole-catalog refresh, then paints the settled plan before starting."
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_enter_with_a_held_refresh_waits_and_starts_nothing"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_releasing_the_refresh_rebuilds_the_plan_and_starts_the_run"
        status: pass
    human_judgment: false
  - id: D2
    description: "Escape preserves selection, cancels the start request, and makes a late publication inert."
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_esc_during_the_wait_cancels_it_and_keeps_the_selection"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_a_late_publication_after_esc_starts_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "Refresh failures and missing state report a bounded error and allow retry."
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_a_failing_refresh_reports_and_enter_retries"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_state_check_failed_status_fits_78_cells"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_a_publication_that_leaves_a_row_unsettled_does_not_start"
        status: pass
    human_judgment: false

duration: "not recorded; execution resumed after context compaction"
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 12: Wait for fresh state before running

**ExecuteScreen joins the catalog refresh flight, paints its settled plan before starting, and lets Escape cancel safely or retry a failed wait.**

## Performance

- **Duration:** Not recorded; work resumed after context compaction.
- **Started:** Not recorded.
- **Completed:** 2026-10-18T04:49:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added a thread worker that refreshes the whole catalog once. Enter waits for publication; the screen rebuilds and paints the plan before starting. Mount joins the same flight without starting a run, and unattended start follows the same wait path.
- Added Escape cancellation, a token guard against late settlements, and a retry path for refresh errors or missing state. Cancellation keeps the option prompts and selection intact.
- Capped error status text at 78 cells with Rich `Text.truncate`, keeping the retry instructions visible.

## Task Commits

1. **Task 1: Enter waits for held refresh and starts from published state** — `2aa2b24` (`feat(20-12): enter waits on the one refresh flight and starts only from published state`)
2. **Task 2: Escape cancels the wait; stale publication never starts a run** — `d118196` (`feat(20-12): esc cancels the wait; a stale publication never starts a run`)

**Plan metadata:** This summary is committed separately from the two task commits.

## Files Created/Modified

- `installer/execute_screen.py` — wait worker, publication handling, Escape cancellation, stale-token guard, retry status, and bounded error text.
- `tests/state_doubles.py` — held refresh service and event-controlled fixture.
- `tests/test_execute_screen.py` — held-refresh, cancellation, stale-publication, failure, retry, and truncation pilots.
- `.planning/phases/20-install-plan-with-dispositions/20-12-SUMMARY.md` — this plan summary.

## Decisions Made

- Keep `VersionRefreshService` as the state owner; the screen calls `refresh` with the whole catalog to join the existing flight.
- After Escape, skip one pre-wait replan. The refresh service publishes state before posting `StateSettled`, so the token guard alone would not stop the next Enter from consuming state produced by the canceled wait.
- Use Rich `Text.truncate(..., overflow="ellipsis")` for error details instead of adding a custom `_fit` helper, as directed by reuse finding 12-1.

## TDD Evidence

**Task 1 RED:** The five held-refresh pilots initially failed because the screen did not start a refresh; `service.calls` remained empty. After implementation, all five focused pilots passed.

**Task 2 RED:** The first filtered run printed `FF.F.`: Escape dismissed the screen in both cancellation pilots, and the 300-character error occupied 349 cells instead of at most 78; the other two tests passed. After the late-publication fixture was set to publish a state, its isolated RED run showed one refresh call where the second Enter required two. The cancellation, token, and truncation changes made all five filtered Task 2 tests pass.

## Verification

- `uv run pytest tests/test_execute_screen.py -q --no-cov -k "esc_during_the_wait or late_publication or failing_refresh or fits_78 or leaves_a_row_unsettled"` — 5 passed.
- `uv run pytest tests/test_execute_screen.py -n auto -q --no-cov` — passed after both tasks.
- `make validate && make test` — passed; 4,874 passed, 4 skipped, 96.05% total coverage.
- Acceptance checks — passed: one whole-catalog refresh call site, one wait-token comparison and bump, cancellation/error copy counts, no polling calls, and no new suppression comments.
- `.claude/gsd-core/bin/gsd_run check evaluation-scope --plan 20-12 --commits-only --raw` — resolved both task commits.
- Pre-commit hooks passed on both task commits.

## Deviations from Plan

### Plan consistency correction

**1. After Escape, the next Enter skips one pre-wait replan.**
- **Found during:** Task 2 (Escape cancellation and stale publication).
- **Issue:** The service publishes state before sending `StateSettled`. The existing `action_start` pre-wait `_replan()` therefore consumed the canceled worker's publication on the next Enter, so it did not start the new wait required by the plan.
- **Fix:** Mark the canceled wait and skip only the next pre-wait replan. The next wait's current-token settlement remains responsible for rebuilding and starting.
- **Files modified:** `installer/execute_screen.py`, `tests/test_execute_screen.py`.
- **Verification:** The late-publication pilot fails with one refresh call before the fix and passes with two calls afterward; the full module and suite pass.
- **Committed in:** `d118196`.

**Total deviations:** 1 plan-consistency correction.
**Impact on plan:** Preserves the explicit “Enter waits again” and stale-publication behavior without expanding scope.

## Issues Encountered

- The `task-start` helper only recognizes Markdown task headings; this plan uses XML `<task>` blocks. The full task blocks were read and used directly.
- The first `make validate` run found a Ruff formatting issue in the edited test file. Ruff formatted it, and validation passed on rerun.
- The requested review subagent could not run: `general-purpose` was unavailable, and the available reviewer agents returned HTTP 429. I reviewed the diff and relevant source/tests directly; no implementation issue remained open.
- The orchestrator-owned `.planning/config.json` change remains untouched and unstaged.

## User Setup Required

None — no external service configuration is required.

## Next Phase Readiness

The wait remains isolated behind `_await_state`, ready for the later refresh-owner change. No implementation blockers remain.

## Self-Check: PASSED

- Both task commits are present on the current branch.
- Task acceptance checks and plan-level verification commands pass.
- The evaluation-scope check resolves two commits for Plan 20-12.
- `.planning/config.json` was not staged or changed by this work.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
