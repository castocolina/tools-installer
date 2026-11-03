---
phase: 21-one-screen-family
plan: "15"
subsystem: tui
tags: [textual, mutation-lock, update, policies, daemon-default]
requires: ["21-13", "21-14", "21-12", "21-06"]
provides:
  - "MutationHolder.UPDATE, POLICY_TOGGLE, DAEMON_DEFAULT"
  - "u, the Policies job toggle and the on-by-default daemon hold the one app lock"
  - "daemon-default completion repaints a visible view without a pass"
affects: ["21-16"]
tech-stack:
  added: []
  patterns: ["one app lock, taken at the mutation point, released by the first statement of the worker's completion handler"]
key-files:
  created: []
  modified:
    - installer/enums.py
    - installer/catalog_tui.py
    - installer/wizard_app.py
    - tests/test_screen_family.py
    - tests/test_catalog_tui.py
    - tests/test_wizard_app.py
    - tests/test_policies_e2e.py
    - tests/test_setup.py
decisions:
  - "Lock check in u sits right after the three silent structural returns and before every informational refusal (T-21-51)"
  - "DaemonDefaultApplied.policy_id is str | None and is posted from finally on every outcome, pairing the take and the release (T-21-26)"
  - "on_daemon_default_applied repaints through _render_published unless Policies is the visible screen; no pass (D-05), top screen only (D-06) (T-21-59)"
metrics:
  tasks: 2
  completed: 2026-11-03
status: complete
actuals:
  tokens: 36000
  tasks: 2
  commits: 4
plan_head_before: 38f20bbde90e2ed2e93c52ea88f3f0763b5bef92
plan_head_after: ffde6e43cde88c43755aff307607d4e916ab21bb
commits: 4
---

# Phase 21 Plan 15: Fold the worker guards into the app lock Summary

`u`, the Policies background-job toggle and the on-by-default daemon now take the one app mutation lock with their fixed holder nouns; the per-screen flags and refusal strings are gone, and the daemon completion repaints a visible Uninstall without a pass.

## Commits

| Commit | Subject |
| ------ | ------- |
| c247b04 | test(21-15): an update holds the app mutation lock (RED) |
| d99c73b | feat(21-15): an update holds the app mutation lock |
| 60b1766 | test(21-15): the job toggle and daemon default hold the app lock (RED) |
| ffde6e4 | refactor(21-15): fold the toggle and daemon-default guards into the app lock |

## RED output

Task 1 (`-k "update_holds or u_is_refused or update_crashes"`): 6 failed. Example, the `unknown_owner` case:

```
AssertionError: assert ('cannot upda...WARN) == ('A removal i...WARN)
At index 0 diff: 'cannot update rg: no manager claimed this tool' != 'A removal is running; wait for it to finish. Navigation still works.'
```

The `broken` case read `rg is broken: rg exits non-zero`, the others their own refusal or started the update. `test_the_lock_is_released_when_the_update_crashes` already passed before the change (no holder existed to leak); it is a regression guard, not a RED test.

Task 2 (`-k "background_job or daemon_default or any_toggle or t_and_m"`): 6 failed.
- toggle and no-policy-id and construction tests: `assert app.mutation_in_flight` -> `False` (nothing took the lock).
- `any_toggle`: `'other enabled.\nJob: registered' != 'A daemon apply is running; ...'` (the toggle ran).
- `t_and_m`: `'job rescheduled.\nJob: registered' != 'A removal is running; ...'`.
- repaint pilot: failed earlier than planned, at `assert app.mutation_in_flight` while the apply was held, since the lock was not yet taken for the daemon default.

## GREEN output

After each implementation commit: `make validate` exit 0; `make test` exit 0, 5043 passed, 4 skipped, coverage 96.17% (required 90%). The six Task 2 pilots and the seven Task 1 items pass under `-n auto`.

## Counts (collected, before -> after)

| File | Start | End |
| ---- | ----- | --- |
| tests/test_screen_family.py | 60 | 73 (+7 Task 1 items, +6 Task 2) |
| tests/test_wizard_app.py | 319 | 319 |
| tests/test_catalog_tui.py | 214 | 214 |
| tests/test_policies_e2e.py | 22 | 22 |

Flag and constant counts over `installer/` and `setup.py`: the toggle flag 5 -> 0, the daemon flag 6 -> 0 (start of Task 2 counts from the plan), both message constants 7 -> 0. `def _settle_daemon/_settle_toggle` in tests/: 3 -> 0 (REUSE 15-1, now `settle`).

## Tests changed, with reasons

- `tests/test_catalog_tui.py`: 15 bare-screen `u` tests (`test_update_*`, `test_u_*`, `test_action_update_tool_*`) became `async` and call `action_update_tool()` inside a new `_lock_host()` (a running `UnifiedApp`), because the lock check now precedes every refusal and needs an active app. Assertions unchanged.
- `tests/test_catalog_tui.py::test_second_update_press_shows_already_in_flight` and `tests/test_wizard_app.py::test_second_u_press_while_latched_is_refused`: the second `u` now reads the `An update is running; ...` template (D-08; `update already in flight` remains only as the `UpdateService.begin` refusal, unreachable from the TUI now).
- `tests/test_setup.py::_App` stub gained a no-op `end_mutation` because `UnifiedApp.on_tool_updated` now calls it first.
- `tests/test_wizard_app.py`: reads of the deleted flags became `app.mutation_in_flight`; the "wait a moment" / "still applying" substring checks became the exact `A daemon apply ...` / `A policy toggle ...` strings; `test_daemon_default_in_flight_clears_even_on_an_unexpected_exception` renamed `test_daemon_default_lock_clears_even_on_an_unexpected_exception`; the poll loop before the in-flight assertion went away (the lock is held from construction).
- `tests/test_policies_e2e.py`: `_settle_toggle` deleted; 15 calls use `settle(app, pilot)`.

## Default-daemon refuse-all regression (plan check it.1 INFO 2)

While the on-by-default daemon apply runs, every mutation is refused with `A daemon apply is running; wait for it to finish. Navigation still works.`, not only the daemon's own policy row. In production the window is from `UnifiedApp.__init__` until the apply worker posts `DaemonDefaultApplied` (one `launchctl bootstrap`/`systemctl --user` sequence on a fresh machine, near-instant on later runs, where `ensure_daemon_default` is a no-op). It will also refuse install `enter` from 21-16 on. No test measured the window (the pilots hold the apply on an event).

## Deviations from Plan

**1. [Rule 3 - Blocking] `tests/test_setup.py` stub** — `_App` lacked `end_mutation`, failing `test_failed_direct_catalog_update_exits_1`. Added a no-op beside the existing no-op stubs. Commit d99c73b.

**2. [Rule 3 - Blocking] pyright deprecation** — `@asynccontextmanager` with `AsyncIterator` is flagged; used `AsyncGenerator[None]`.

No other deviations. Plan files list did not name `tests/test_setup.py`; it was the only added file.

## Known Stubs

None.

## Threat Flags

None. T-21-25, T-21-26, T-21-51 and T-21-59 are mitigated by the tests named in the plan.

## Self-Check: PASSED

Files exist (installer/enums.py, catalog_tui.py, wizard_app.py, the five test files); commits c247b04, d99c73b, 60b1766, ffde6e4 are ancestors of HEAD.
