---
phase: 20-install-plan-with-dispositions
plan: "25"
subsystem: ui
tags: [python, textual, rich, install-plan, reporting]
requires:
  - phase: 20-install-plan-with-dispositions
    provides: RowOutcome, update outcomes, shared outcome vocabulary, plan report renderers
provides:
  - Successful update extras are rendered in headless and TUI end-of-run reports
  - Both routes use one render_run_report function
  - Failed rows fall back to the recorded outcome detail when errors are absent
affects: [install-plan, headless-reporting, execute-screen]
actuals:
  tokens: 460
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns: [single shared end-of-run report, sanitized child output rendered as plain text]
key-files:
  created: [.planning/phases/20-install-plan-with-dispositions/20-25-SUMMARY.md]
  modified: [installer/render.py, installer/app.py, installer/execute_screen.py, tests/test_render.py, tests/test_app.py, tests/test_execute_screen.py]
key-decisions:
  - "Successful update notes remain in the end-of-run report rather than changing the disposition row copy."
  - "Both routes use render_run_report to prevent their report renderer lists from diverging."
  - "For failed outcomes, install/update errors take precedence; outcome.detail is the fallback before the generic message."
requirements-completed: [PLAN-04, PLAN-06]
duration: 28min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 25 Summary

**Successful update details and recorded failure reasons now reach users through a unified end-of-run report in both headless and TUI runs.**

## Performance

- **Duration:** approximately 28 minutes, including recovery of the interrupted plan work.
- **Tasks:** 3
- **Files modified:** 6 implementation/test files, plus this summary.

## Accomplishments

- Task 1 — Added `render_update_notes` and `render_run_report`; routed headless `run_wizard` through the shared report. Update notes are ordered as replayed globals, cleanup warnings, postinstall warning, then detail, sanitized and printed literally. Commit: `c755259` (`fix(20-25): successful-update extras print in one end-of-run report`).
- Task 2 — Routed `ExecuteScreen.on_install_run_finished` through the same `render_run_report`; restored the successful outdated-update extras pin in the TUI pilot. Commit: `3dcc497` (`fix(20-25): the review log prints the shared end-of-run report`).
- Task 3 — Failed rows now use the first line of the last install/update error, or the first line of `outcome.detail`, before falling back to `no method succeeded`. Commit: `01946ee` (`fix(20-25): a failed row names its real reason`).

## TDD evidence

The implementation existed in the resumed working tree, so production hunks were temporarily removed for each RED run and restored before GREEN verification. No intermediate failing tree was committed.

- **Task 1 RED:** `uv run pytest tests/test_render.py tests/test_app.py -q --no-cov -n 0 -k 'update_notes or successful_updates_extras'` — exit 1; three renderer tests failed because `render_update_notes` was absent, and the headless test showed the update-extra line missing (`Summary — 1 updated` and the row were present). After restoring production changes, `uv run pytest tests/test_render.py tests/test_app.py -q --no-cov -n auto` passed (246 collected/passed).
- **Task 2 RED:** `uv run pytest tests/test_execute_screen.py -q --no-cov -n 0 -k carries_outcome_extras` — 1 failed; log had the summary and update row but no replay/cleanup/postinstall/detail note. GREEN: `uv run pytest tests/test_execute_screen.py -q --no-cov -n auto` passed (131 passed).
- **Task 3 RED:** `uv run pytest tests/test_render.py -q --no-cov -n 0 -k outcome_detail_when` — 2 failed and 1 passed; the reconfigure and refused-update cases showed `no method succeeded` instead of their recorded reason, while the install-error precedence case passed. GREEN: `uv run pytest tests/test_render.py -q --no-cov -n auto` passed (113 passed).

## Collected test counts

| Test file | Start | End |
|---|---:|---:|
| `tests/test_render.py` | 107 | 113 |
| `tests/test_app.py` | 136 | 136 |
| `tests/test_execute_screen.py` | 131 | 131 |

Counts used the plan's `--collect-only`/`awk` method. The app and execute-screen baselines were already above their required minimums when this resumed plan began; their tests gained one each during the first two tasks.

## Verification

- Task 1: `uv run pytest tests/test_render.py tests/test_app.py -q --no-cov -n auto` — passed.
- Task 2: `uv run pytest tests/test_execute_screen.py -q --no-cov -n auto` — passed.
- Task 3: `uv run pytest tests/test_render.py tests/test_execute_screen.py tests/test_app.py -q --no-cov -n auto` — passed.
- Plan-specific render floor: 113 collected (required at least 113) — passed.
- Suppression comparison: 484 before, 484 after — passed; no suppression was added.
- Final `make validate` — passed (ruff, formatting, pyright, bandit, vulture, shellcheck).
- Final `make test` — passed: 4900 passed, 4 skipped, 96.00% coverage (90% required).
- Diff checks showed no whitespace errors. Large touched test files were checked for line counts; all grew rather than being truncated.

## Deviations from Plan

None in shipped behavior or scope. To demonstrate RED after resume, the implementation was temporarily removed and restored; the initial attempt to remove the production renderer while leaving a direct test import caused collection errors, so the isolated RED setup was adjusted to exercise the missing function dynamically. The resulting RED run failed on the expected missing function and missing output. No temporary files were retained in the repository.

## Issues Encountered

One initial `make validate` run caught a 101-character new test line; it was wrapped, after which validation passed. An initial validation attempt also surfaced Ruff formatting for the added parametrized test; formatting was applied and the final gates passed.

## Task Commits

1. Task 1 — `c755259`
2. Task 2 — `3dcc497`
3. Task 3 — `01946ee`

**Plan summary commit:** recorded separately after implementation commits.

## Files Created/Modified

- `installer/render.py` — shared update-note and end-of-run report renderers; failed-detail fallback.
- `installer/app.py` — headless route calls the shared report.
- `installer/execute_screen.py` — TUI log calls the shared report.
- `tests/test_render.py` — update-note sanitization/silence and failed-detail fallback tests.
- `tests/test_app.py` — headless update extras regression test.
- `tests/test_execute_screen.py` — ported update extras pilot regression test.
- `.planning/phases/20-install-plan-with-dispositions/20-25-SUMMARY.md` — this record.

## Issues for the Orchestrator

`.planning/config.json` was already modified by the orchestrator and was neither staged nor changed by this plan. No other issue remains.

---
*Phase: 20-install-plan-with-dispositions*
*Plan: 25*
*Completed: 2026-10-18*
