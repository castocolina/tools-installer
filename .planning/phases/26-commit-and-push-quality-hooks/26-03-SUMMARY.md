---
phase: 26-commit-and-push-quality-hooks
plan: "03"
subsystem: tests
tags: [flaky-test, textual, pilot, push-gate]
requires: []
provides:
  - "tests/test_screen_family.py::_published_passes, a baseline pass-count read that waits on app.await_publication"
affects: [push-gate]
tech-stack:
  added: []
  patterns: ["wait on the app's own completion signal instead of two equal reads after settle"]
key-files:
  created: []
  modified:
    - tests/test_screen_family.py
    - .planning/todos/completed/2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test.md
key-decisions:
  - "Record the change as a mitigation of the suspected window, never a root-cause fix: the failure was never reproduced (A1)"
  - "The todo moves to completed (D-12) with a Resolution that keeps the root cause unconfirmed and carries a reopen rule"
requirements-completed: [HOOK-02]
duration: 40min
completed: 2026-11-16
status: complete
actuals:
  tokens: 2500
  tasks: 2
  commits: 2
plan_head_before: 8106a063dd3f5b2553fb116f2e71989239e7ec87
plan_head_after: 5e3436e476de98128148734030f16bebaaf5960b
commits: 2
---

# Phase 26 Plan 03: Settle the reinstall tests Summary

Four reinstall/Doctor tests now read their baseline pass count only after `app.await_publication` calls back, and the two body-reading tests wait for their text before asserting. This mitigates the window the code shows; it is not a root-cause fix.

## What changed

- `_published_passes(app, pilot, service)` registers `app.await_publication(done.append)`, waits (bounded by `wait_until`'s 400 tries) until it calls back, pauses once and returns `service.passes`. A pass queued while the Doctor view opened (the launch pass or the globals audit's `request_refresh`) lands before `before` is read. `settle` cannot see such a pass: it can return between one pass's worker ending and `on_refresh_finished` starting the queued successor.
- Used in `test_reinstall_invalidates_and_requests_one_pass`, `test_doctor_fix_requests_one_pass` (both params), `test_a_failed_invalidate_after_a_reinstall_is_reported` and `test_a_crashed_reinstall_still_invalidates`. The post-press `_wait_for_passes(pilot, service, before + 1)` is unchanged, and `await_publication` is never called after the press.
- The last two tests also `wait_until` their first expected body phrase is in `_doctor_text(app)` and `app.mutation_in_flight` is false, before reading the body. Existing assertions are unchanged.
- No fixed pause, sleep, skip, xfail or loosened assertion was added.

## Measurements

Loop: `uv run pytest tests/test_screen_family.py -n auto -q --no-cov`, 50 runs, one log per run (kept in the session scratchpad, not in the repo).

| Tree | Runs | Passed | Failed |
|------|------|--------|--------|
| Before (unmodified, HEAD 8106a063) | 50 | 50 | 0 |
| After (HEAD 1c320802) | 50 | 50 | 0 |

A 50 of 50 baseline is an honest result: the todo saw the failure only twice under full-suite load, and research could not reproduce it in 650 targeted runs (RESEARCH Assumption A1). The loop counts are measurements, not a proof that the race is gone, and the root cause stays unconfirmed. Full `make test` on the Task 1 tree: 7662 passed, 6 skipped, coverage 96.20%. `make validate` green.

## Todo

`.planning/todos/pending/2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test.md` moved (git mv) to `.planning/todos/completed/` with a `## Resolution` that names the mitigation, both run counts, the sentence that the root cause stays unconfirmed, and the reopen rule (a new todo citing it, with the failing run's log).

## Deviations from Plan

None - plan executed as written. One mechanical note: the `body = ...; assert "pnpm globals reinstalled." in body` text occurs in two tests, so the edit script anchored on the following `_INVALIDATE_FAILED.format(error=shown)` line to touch only the intended test.

## Task Commits

1. Task 1: `1c320802` test(26-03): read the reinstall pass baseline after the app's publication signal
2. Task 2: `5e3436e4` docs(26-03): close the flaky reinstall todo as a mitigation with a reopen rule

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Files found: tests/test_screen_family.py, the completed todo, this SUMMARY. Commits 1c320802 and 5e3436e4 are ancestors of HEAD.
