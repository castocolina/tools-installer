---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 01
subsystem: testing
tags: [textual, worker, modal, characterisation, wave-0]

requires: []
provides:
  - MECHANISM=A (call_from_thread + push_screen_wait) proven under Pilot
  - three characterisation tests pinning the worker-to-modal seam
  - 13-VALIDATION.md Wave 0 complete with DD-1/DD-2/DD-3 and a rule-2 exception
affects: ["13-05 ask_from_worker", "13-07 architecture.md push_screen_wait exception"]

actuals:
  tokens: 8000
  tasks: 3
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Thread worker asks a modal via call_from_thread + push_screen_wait (MECHANISM=A)"
    - "Characterisation tests of a Textual primitive with no production caller yet (architecture rule 5)"

key-files:
  created:
    - tests/test_execute_screen.py
  modified:
    - .planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-VALIDATION.md

key-decisions:
  - "MECHANISM=A: a @work(thread=True) worker calls app.call_from_thread(coro_fn) where coro_fn awaits app.push_screen_wait(modal). Spike printed MECHANISM=A; NoActiveWorker was not raised."
  - "MECHANISM=A is a documented exception to architecture.md rule 2: that rule governs main-thread callers; a thread worker has no callback to return into. Plan 13-07 Task 1 must name push_screen_wait in architecture.md."
  - "DD-1/DD-2/DD-3 recorded verbatim in 13-VALIDATION.md for /gsd-verify-work."

patterns-established:
  - "Wave 0 pins an unverified Textual combination with a green characterisation test and a named mechanism record, and creates no production helper ahead of its caller."

requirements-completed: [D-03, D-04, D-05]

coverage:
  - id: D1
    description: "A Textual thread worker can obtain a user's modal answer synchronously (MECHANISM=A: call_from_thread + push_screen_wait)."
    requirement: D-03
    verification:
      - kind: other
        ref: "scratchpad spike_worker_modal.py printed MECHANISM=A and exited 0"
        status: pass
      - kind: unit
        ref: "tests/test_execute_screen.py#test_a_thread_worker_receives_the_users_modal_answer"
        status: pass
    human_judgment: false
  - id: D2
    description: "A dismissed modal gives the worker None, never an indistinguishable silent default (D-05.3)."
    requirement: D-05
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_a_dismissed_modal_gives_the_worker_none"
        status: pass
    human_judgment: false
  - id: D3
    description: "The event loop keeps running while the worker waits on the modal (T-13-07)."
    requirement: D-03
    verification:
      - kind: unit
        ref: "tests/test_execute_screen.py#test_the_event_loop_keeps_running_while_the_worker_waits"
        status: pass
    human_judgment: false
  - id: D4
    description: "The chosen mechanism is recorded in 13-VALIDATION.md so plan 13-05 implements it without re-deciding, including the rule-2 exception and the three characterisation-test names."
    requirement: D-04
    verification:
      - kind: other
        ref: "13-VALIDATION.md ## Worker-to-modal mechanism contains MECHANISM=A, rule 2, and test_execute_screen.py"
        status: pass
    human_judgment: false

duration: 30 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 01: Worker-to-modal mechanism proven as MECHANISM=A — Summary

**A `@work(thread=True)` worker can synchronously obtain a Pilot-driven modal answer via `call_from_thread` + `push_screen_wait` (MECHANISM=A). Three green characterisation tests pin that combination, and 13-VALIDATION.md records it so plan 13-05 implements `ask_from_worker` without re-deciding. No production helper was created.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-09-14T04:20:23Z
- **Completed:** 2026-09-14T04:50:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Spike under `app.run_test()` printed `MECHANISM=A` and exited 0. Mechanism A was not rejected: `NoActiveWorker` was not raised and the modal appeared. Mechanism B was not used.
- `tests/test_execute_screen.py` pins the three properties plan 13-05 depends on: the worker receives the selected value, escape yields `None`, and `pilot.pause()` advances while the worker waits.
- `13-VALIDATION.md` records MECHANISM=A as a documented exception to architecture.md rule 2, carries DD-1/DD-2/DD-3, maps every behaviour to a real plan/task/command, and declares Wave 0 complete.

## Task Commits

1. **Task 1: Spike the worker-to-modal mechanism** — no commit (scratchpad only; `git status --porcelain -- installer tests setup.py` stayed empty).
2. **Task 2 + Task 3: characterisation tests and Wave 0 record** — `0fb4b10` (`test(13-01): pin worker-to-modal MECHANISM=A`).
3. **Plan metadata** — `13-01-SUMMARY.md` plus STATE/ROADMAP.

## Files Created/Modified

- `tests/test_execute_screen.py` — three characterisation tests of MECHANISM=A; module-private `_AskModal` / `_WorkerAskApp`; no import from `installer.execute_screen`.
- `.planning/phases/13-live-in-tui-install-execution-persistent-wizard-settings-ins/13-VALIDATION.md` — Worker-to-modal mechanism, Recorded design decisions, rewritten Per-Task Verification Map, ticked Wave 0 boxes, `wave_0_complete: true`, `nyquist_compliant: true`.

## Decisions Made

- **MECHANISM=A.** `asyncio.run_coroutine_threadsafe` (inside `App.call_from_thread`) plus `push_screen_wait` is sufficient; the worker's `active_worker` ContextVar is visible to `wait_for_dismiss=True` on the event loop in Textual 8.2.7.
- **Rule 2 exception.** MECHANISM=A is a documented exception to `.claude/architecture.md` rule 2. Plan 13-07 Task 1 must write `push_screen_wait` into that file as the checksum-mismatch seam.
- **DD-1, DD-2, DD-3** recorded verbatim in 13-VALIDATION.md (continue-on-failure; `link_mode` folded into PoliciesScreen; `--link-mode` overrides the run only).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `uv run pytest tests/test_execute_screen.py -q` under the rtk pytest wrapper hid the `3 passed` summary line; `.venv/bin/python -m pytest tests/test_execute_screen.py --no-header` reported `3 passed in 1.01s`. `make validate && make test` then reported 1900 passed, 1 skipped, 95.38% coverage.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 13-02 (StreamingRunner). Plan 13-05 implements `ask_from_worker` as MECHANISM=A only. Plan 13-07 Task 1 names `push_screen_wait` in `.claude/architecture.md`. The three characterisation tests keep their names, stay green, and are never skipped as `tests/test_execute_screen.py` grows.

## Self-Check: PASSED

- `tests/test_execute_screen.py` exists on disk with the three named tests.
- `13-VALIDATION.md` contains `MECHANISM=A`, `rule 2`, `DD-1`/`DD-2`/`DD-3`, `wave_0_complete: true`, `nyquist_compliant: true`, and no `13-01-TBD`.
- `make validate && make test` green on this tree (1900 passed, 1 skipped).

---
*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Completed: 2026-09-14*
