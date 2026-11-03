---
phase: 21-one-screen-family
plan: "18"
subsystem: policies-screen
tags: [textual, policies, drift, thread-worker, generation-guard]
requires: ["21-17"]
provides:
  - "Policies drift state: owned-but-inactive reads ! [drift] (yellow) with the UI-SPEC drift line"
  - "JobStatesRead + _read_job_states_worker: state_cache rows read off the event loop, generation-guarded"
  - "Every toggle completion requests one app pass"
affects: [installer/wizard_app.py]
tech-stack:
  added: []
  patterns: ["generation-guarded thread worker (Doctor globals-audit pattern)"]
key-files:
  modified:
    - installer/wizard_app.py
    - tests/test_policies_e2e.py
    - tests/test_screen_family.py
    - tests/test_layout_80x20.py
    - tests/test_wizard_app.py
decisions:
  - "Drift = owned() true and is_active() false in the same render; both reads share one guarded helper (_read_active_owned)"
  - "_start_job_state_read() bumps the generation and starts the worker; shared by state_refreshed and refresh_daemon_state; _finish_toggle only bumps"
metrics:
  tasks: 2
  commits: 4
  plan_head_before: 1aa7d4976b43d6ab138ee72075e6bb8ce3aac68d
  plan_head_after: e5c95e4a8dcc1ff4cbf3dcc0d748976a5c59516c
actuals:
  tokens: 14000
  tasks: 2
  commits: 4
status: complete
---

# Phase 21 Plan 18: Policies drift and job-state worker Summary

Policies shows `! [drift]` for owned-but-inactive rows, reads the systemd-backed
(`state_cache`) rows on a generation-guarded thread worker, and every toggle ends
with one `request_refresh()`.

## Commits

- 3a7d14f test(21-18): drift and job-state worker (RED; includes the `JobStatesRead` class as the only stub pyright needed)
- 29d0dc1 feat(21-18): policies show drift and read the timer state off the event loop
- 17a165e test(21-18): toggle pass and completion-supersedes pilots (RED)
- e5c95e4 feat(21-18): a policy toggle asks the app for one pass

## RED / GREEN evidence

Task 1 RED (`-k "drift or owned_read or job_state or superseded"`): 6 failed
(`test_an_owned_inactive_policy_reads_drift`: `('○ [off]','dim') == ('! [drift]','yellow')`;
`test_a_failed_owned_read_shows_the_error`: `'○ [off]' == ''`; the three job-state tests;
`test_a_drifted_policies_table_fits_80x20`). `test_a_policy_without_owned_never_drifts` passes
before and after (regression guard).

Task 2 RED: `test_a_toggle_requests_one_pass`, `test_a_job_toggle_requests_one_pass_after_it_lands`,
`test_a_failed_toggle_still_requests_a_pass` all `assert 1 == (1 + 1)` (no pass requested);
`supersedes_an_in_flight_job_read[toggle]` repainted `'○ [off]' == '● [on]'`;
`[daemon_default]` never reached `● [on]`.

GREEN: all new tests pass; the supersede and job-state tests were run 3 times under `-n auto`
(no flake). `make validate` exit 0; `make test` exit 0, 5093 passed, 4 skipped, coverage 96.16%.

## Test counts (collected, start -> end)

| File | Start | End |
|------|-------|-----|
| tests/test_policies_e2e.py | 31 | 34 |
| tests/test_screen_family.py | 96 | 104 |
| tests/test_layout_80x20.py | 16 | 17 |

(Screen-family delta is +8: 3 job-state pilots, 3 toggle-pass pilots, 2 supersede cases.)

## Deviations from Plan

**1. [Rule 1 - Changed existing test] `tests/test_wizard_app.py::test_a_second_toggle_is_refused_while_a_daemon_toggle_is_in_flight`**
- Reason: D-05 (every toggle ends with a pass) makes the pass re-read the policy's real
  state; the test's `slow_apply` never changed that state, so the row read OFF after the pass.
  The policy now binds `is_active=lambda: bool(applies)`. Behavior asserted is unchanged.

**2. 80x20 backstop interpretation.** `test_a_drifted_policies_table_fits_80x20` asserts the
State and Policy column spans end at or before column 78 with every row drifted. A literal
"rendered line past column 78" check is vacuous (the DataTable clips to its width); the
Effect column is allowed to scroll as it already does.

No other deviations. No auth gates.

## Notes

- `JobStatesRead` drops results whose generation is not current, then guards on
  `is_mounted` and `app.is_running`.
- `refresh_daemon_state` now keys its early return on an unknown policy id and always starts a fresh job-state read when mounted.
- No stubs, no new suppressions, no new dependency.

## Threat Flags

None.

## Self-Check: PASSED

Files and the four commits above exist on the branch.
