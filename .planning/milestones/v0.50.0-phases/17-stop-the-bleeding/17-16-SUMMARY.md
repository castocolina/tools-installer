---
phase: 17-stop-the-bleeding
plan: "16"
subsystem: testing
tags: [pytest, textual, race-flake, threading-event, ci-oracle]

requires:
  - phase: 17-stop-the-bleeding/15
    provides: wave-1 CI oracle run 38656028040 that exposed the macOS flake
provides:
  - deterministic test_manual_toggle_of_the_daemon_is_refused_while_the_worker_is_in_flight (release-gated daemon_default worker)
affects: [17-01 (wave-1 CI oracle re-run)]

actuals:
  tokens: 12000
  tasks: 1
  commits: 2

tech-stack:
  added: []
  patterns:
    - "release-gated thread worker: gate the daemon_default callable on a threading.Event the test releases after the guarded interaction"

key-files:
  created: []
  modified:
    - tests/test_wizard_app.py

key-decisions:
  - "Gate the worker on threading.Event with wait(timeout=30) and release in a finally, so a failing assertion never wedges the worker thread for 30 s"

patterns-established:
  - "Release-gated daemon_default worker (same idiom as _GatedUpdateService and the existing slow_daemon_default tests in this file)"

requirements-completed: [CI-01]

duration: 18min
completed: 2026-10-14
status: complete
---

# Phase 17 Plan 16 Summary

**Deterministic daemon-toggle refusal test: the on-by-default worker is held in flight by a threading.Event until the test has proven the refusal, closing the macOS CI flake (run 38656028040)**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-10-14
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- `test_manual_toggle_of_the_daemon_is_refused_while_the_worker_is_in_flight` no longer races: `daemon_default` is a gated callable that blocks on `release.wait(timeout=30)` before calling `ensure_daemon_default(policy)`.
- The test waits (bounded 400-iteration `pilot.pause()` loop) for `app.daemon_default_in_flight is True`, asserts the "wait a moment" refusal, then `release.set()` and settles via `_settle_daemon`; `release.set()` also runs in a `finally` around the whole `async with` so a failing assertion never leaves the worker blocked.
- The two final assertions are unchanged: `active_state["daemon:prune-tmpdir"] is True` and exactly one `launchctl bootstrap` call.
- No installer/ code touched; no skip/xfail/skipif introduced; all existing asserts kept.

## Race audit of the same file (plan action item)
Grepped `tests/` for other `daemon_default_in_flight is True` / `toggle_in_flight is True` assertions:
- line 5096 (`test_reschedule_is_refused_while_the_worker_is_in_flight`) — already gated (`slow_daemon_default` release event).
- lines 5176, 5224 (uninstall-refusal tests) — already gated (release events).
- line 5036 (`test_a_second_toggle_is_refused_while_a_daemon_toggle_is_in_flight`) — not the same race: `toggle_in_flight` is asserted synchronously in the same event-loop turn as the keypress that starts the gated `slow_apply` worker; no mount-time worker involved. Left unchanged.

## TDD
Not a `tdd="true"` task (flake fix, test already existed and passed locally); no RED capture required by the plan. The change is test-only and green by construction.

## Verify results
- `uv run pytest tests/test_wizard_app.py -q --no-cov -k daemon` → 27 passed, exit 0.
- Stress: 20/20 passes of `uv run pytest tests/test_wizard_app.py -q --no-cov -n auto -k "daemon"`.
- Stress under one CPU: 20/20 passes of `taskset -c 0 uv run pytest … -n auto -k "daemon"`.
- `make validate` → exit 0 (all pre-commit hooks pass).
- `make test` → 3467 passed, 4 skipped, coverage 95.87% (gate 90%), exit 0.

## Task Commits
1. **Task 1: the daemon-default worker stays in flight until the test releases it** — `d5858ee` (test)

## Files Created/Modified
- `tests/test_wizard_app.py` - gated the daemon_default worker behind a release event in the refusal test

## Decisions Made
- Timeout of 30 s on `release.wait` (plan-specified) with a `finally` release, so neither a hung worker nor a blocked teardown is possible.

## Deviations from Plan

None — plan executed exactly as written. (`files_modified` respected: only `tests/test_wizard_app.py`.)

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Orchestrator should re-push HEAD to `ci/phase-17-wave1` (PR #1) and record both job conclusions in 17-01-SUMMARY `## CI oracle (wave 1)` per the plan's verification section.

---
*Phase: 17-stop-the-bleeding*
*Completed: 2026-10-14*
