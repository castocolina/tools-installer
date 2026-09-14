---
phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins
plan: 05
subsystem: installer-tui
tags: [execute-screen, checksum-mismatch, cancel, post-run-report, wave-3]

requires:
  - phase: 13
    provides: "13-01 MECHANISM=A (call_from_thread + push_screen_wait), 13-02 StreamingRunner/should_continue, 13-04 ExecuteScreen tracer"
provides:
  - ChecksumMismatchScreen and ask_from_worker (MECHANISM=A, documented rule-2 exception)
  - ExecuteScreen._ask_mismatch with D-05.3 dismissal-to-skip
  - running per-tool status list and weak cancel (DD-1)
  - full post-run report in the held log (D-02)
affects: ["13-06 link-mode picker wiring", "13-07 architecture.md rule-2 documentation of push_screen_wait"]

actuals:
  tokens: 14931
  tasks: 3
  commits: 4
  plan_head_before: a3478f763b75ce649eb1122d16d43b997e7b9f0a

tech-stack:
  added: []
  patterns:
    - "ask_from_worker is MECHANISM=A (call_from_thread + push_screen_wait), the documented exception to architecture rule 2"
    - "A dismissed checksum-mismatch prompt resolves to skip and writes an attributed log line (D-05.3)"
    - "Weak cancel via threading.Event + should_continue; never kills the in-flight child"
    - "Post-run report reuses installer/render.py helpers through Console-over-StringIO so TUI words match console words"

key-files:
  created: []
  modified:
    - installer/execute_screen.py
    - tests/test_execute_screen.py

key-decisions:
  - "ask_from_worker implements MECHANISM=A only; its docstring names the rule-2 exception so 13-07 Task 1 can lift it."
  - "Dismissing ChecksumMismatchScreen resolves to skip (never retry or fallback) and names the tool, the dismissal, and the skip in the log and status line (T-13-13)."
  - "While the mismatch modal is open, c does not set the cancel event; the status names the waiting prompt. After dismissal, c works again."
  - "execute-keys names all three stop keys: escape (does not leave or stop), c (stops between tools), ctrl+c (aborts the app, may leave a tool half-installed)."

patterns-established:
  - "Worker-to-modal: ask_from_worker is the production seam; the three 13-01 characterisation tests remain the Textual-upgrade pin."
  - "A dismissed in-app prompt is never a silent no-op: it writes an attributed line and a status sentence."

requirements-completed: ["D-02", "D-03", "D-04", "D-05"]

coverage:
  - id: D1
    description: "A checksum mismatch mid-run asks the same three-way question inside the app, and the worker acts on retry, skip, or fallback."
    requirement: D-03
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_retrying_a_mismatch_installs_twice_and_summarizes_installed
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_skipping_a_mismatch_leaves_the_tool_in_mismatched
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_fallback_mismatch_reinstalls_with_continue_policy
        status: pass
    human_judgment: false
  - id: D2
    description: "Dismissing the mismatch prompt writes an explanatory log line naming the tool and the resulting skip, never a silent no-op (D-05.3)."
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_escaping_mismatch_skips_and_explains_the_dismissal
        status: pass
    human_judgment: false
  - id: D3
    description: "A single tool's failure does not stop the batch; a running per-tool status list shows pending, done, and not-done (DD-1)."
    requirement: D-02
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_a_failed_tool_does_not_stop_the_batch
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_progress_pending_count_falls_as_each_tool_finishes
        status: pass
    human_judgment: false
  - id: D4
    description: "The user can stop the batch between tools with c; not-attempted tools are listed in resolved order."
    requirement: D-02
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_cancel_mid_run_lets_the_in_flight_tool_finish
        status: pass
    human_judgment: false
  - id: D5
    description: "Everything the console flow prints after a run — failure detail, skipped reasons, handoff, postinstall warnings, verification — is in the log the screen holds."
    requirement: D-02
    verification:
      - kind: unit
        ref: tests/test_execute_screen.py#test_post_run_log_carries_every_renderer_in_wizard_order
        status: pass
      - kind: unit
        ref: tests/test_execute_screen.py#test_wire_path_oserror_names_the_section_and_still_finishes
        status: pass
    human_judgment: false

duration: 36 min
completed: 2026-09-14
status: complete
---

# Phase 13 Plan 05: In-app mismatch prompt, cancel, and full post-run report — Summary

**Checksum mismatch, weak cancel, and the full console post-run report now live inside ExecuteScreen: retry/skip/fallback work in the TUI, a dismissed prompt skips and says so, a failed tool never aborts the batch, and the held log carries every renderer `run_wizard` prints after an install.**

## Performance

- **Duration:** 36 min
- **Started:** 2026-09-14T02:40:00-04:00
- **Completed:** 2026-09-14T03:16:10-04:00
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- `ChecksumMismatchScreen` asks the same three-way question as `setup.py::_ask_mismatch`, word-for-word; `ask_from_worker` is MECHANISM=A (`call_from_thread` + `push_screen_wait`) with a docstring that names the architecture rule-2 exception.
- Dismissing the prompt resolves to `skip`, posts an attributed log line naming the tool and the skip, and sets a status line (D-05.3 / T-13-13). Unattended (`--yes`) never opens the modal.
- A running `#execute-progress` list marks every resolved tool pending / done / not-done; `c` stops new tools after the in-flight one finishes; not-attempted ids are listed. While the mismatch modal is open, `c` stays inert and the status names the waiting prompt.
- `on_install_run_finished` runs `render_summary`, `render_failure_details`, `render_skipped`, `render_handoff`, `render_postinstall_warnings`, and `render_verification` in `run_wizard` order through the existing StringIO helper, then PATH wiring and PATH audit under their own headings.

## Task Commits

Each task was committed atomically:

1. **Task 1: in-app checksum-mismatch prompt** - `0c5def8` (feat)
2. **Task 2: running per-tool status list and between-tools cancel** - `aa09979` (feat)
3. **Task 3: the full post-run report in the held log** - `1b987ac` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `installer/execute_screen.py` - ChecksumMismatchScreen, ask_from_worker, cancel, progress list, full post-run report
- `tests/test_execute_screen.py` - Pilot cases for mismatch, cancel, progress, and post-run rendering

## Decisions Made

- MECHANISM=A is the production worker-to-modal path; the three 13-01 characterisation tests stay in place as the Textual-upgrade pin.
- Dismissal is skip, never retry or fallback, because `MismatchChoice` has no cancelled member and skip is the only option that does not install an unverified artifact.
- `c` under the mismatch modal is inert by design: the worker is blocked on the answer anyway, and the status must not claim cancel is available.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 13-06 (settings wiring: no pre-TUI prompt, Policies link-mode picker). `ask_from_worker`'s docstring is the sentence 13-07 Task 1 lifts into `.claude/architecture.md`.

## Self-Check: PASSED

- Key files exist: `installer/execute_screen.py`, `tests/test_execute_screen.py`
- Commits: `git log --oneline --grep=13-05` returns `0c5def8`, `aa09979`, `1b987ac`
- `uv run pytest tests/test_execute_screen.py tests/test_session.py tests/test_render.py -q` — green
- `make validate` — passed
- `make test` — 1973 passed, 1 skipped, 95.33% coverage (floor 90%)
- `git diff --stat` against the pre-plan tree lists only `installer/execute_screen.py` and `tests/test_execute_screen.py`

---
*Phase: 13-live-in-tui-install-execution-persistent-wizard-settings-ins*
*Completed: 2026-09-14*
