---
phase: 21-one-screen-family
plan: "17"
subsystem: policies-view
tags: [policies, live-state, textual, version-refresh]
requires: [21-04, 21-12, 21-16]
provides:
  - VersionRefreshService.installed_or
  - PoliciesScreen.state_refreshed with guarded live reads
affects: [21-18]
key-files:
  modified:
    - installer/version_status.py
    - installer/wizard_app.py
    - setup.py
    - tests/test_version_status.py
    - tests/test_policies_e2e.py
    - tests/test_setup.py
    - tests/test_wizard_app.py
decisions:
  - "Toggle re-reads prerequisites at the mutation point (through the same guarded read that feeds the map), so a tool installed after the render is honoured; the map still feeds cell and detail."
status: complete
requirements: [UI-06, UI-01]
actuals:
  tokens: 45000
  tasks: 2
  commits: 4
plan_head_before: fdf4fb267558bf36a28c3440036d4aa1048c0ce0
plan_head_after: 0432e89e8c530096c4c065c74be2d1d509e12f76
---

# Phase 21 Plan 17: Policies live state Summary

Policies now re-reads every policy's `is_active()` and `missing_requirements()` on every entry and publish through `state_refreshed()`, via a render-safe `VersionRefreshService.installed_or` predicate; a failed read blanks the row, writes one error, and refuses `space`/`t`.

## Commits

- be3df53 test(21-17): ... (RED) - Task 1 tests, `installed_or` naive stub for type-checking
- e191f17 feat(21-17): policies render live state and prerequisites on entry
- 1254c93 test(21-17): ... (RED) - Task 2 tests
- 0432e89 feat(21-17): a failed policy read shows its error instead of a stale state

## RED / GREEN

Task 1 RED (stub in place): 5 failed (`test_a_removed_ban_reads_off_on_the_next_entry`, `test_installing_watch_unblocks_the_docker_tweak`, `test_macos_prune_reads_off_without_its_plist` ('● [on]' == '○ [off]'), `test_the_policy_requirements_read_the_shared_state` (('watch',) == ()), `test_installed_or[missing-watch-False]`). GREEN: all pass.

Task 2 RED (verified against the pre-implementation wizard_app.py): `test_a_failed_policy_read_shows_the_error` ('● [on]' == ''), `test_space_on_an_unreadable_policy_applies_nothing` (['remove'] == []), `test_a_failed_requirements_read_blanks_requires_and_detail` ('missing: watch' == ''), `test_t_on_an_unreadable_policy_opens_no_picker` (TimePickerScreen is app.screen); the empty backstop passed already. GREEN: all pass.

## Notes

- The empty-Policies detail copy the backstop pins is the empty string (`_set_detail(None)`).
- Pilots moved to awaiting the first entry: none needed changes.
- Existing tests changed:
  - `tests/test_wizard_app.py::test_daemon_default_resolves_the_row_state_off_the_event_loop`: the fake policy now carries a `state_cache`, because a plain `is_active` is read on the loop by the render (plan decision); a state_cache policy models the systemctl-probing Linux daemon and is left to a worker (21-18). Its intent (completion handler never probes on the loop) is unchanged.
- `setup.py`: the daemon policy is now built right after `_build_services` (it needs the service); the sequence is otherwise unchanged.
- No new `type: ignore`/`noqa`/`nosec`/`pyright: ignore`.

## Test counts (start -> end)

| File | Start | End |
|------|-------|-----|
| tests/test_policies_e2e.py | 22 | 31 |
| tests/test_version_status.py | 223 | 227 (+4) |
| tests/test_setup.py | 151 | 152 |
| tests/test_wizard_app.py | 319 | 319 |

`make validate` exit 0; `make test` exit 0 (5081 passed, 4 skipped, coverage 96.15%).

## Deviations from Plan

**1. [Rule 1 - Bug] Toggle re-reads prerequisites** - `test_policies_screen_rechecks_omz_requirement_before_toggle` requires a prerequisite that lands after the render to be honoured; reading only the render-time map would refuse it. The toggle now calls the guarded `_read_requirements` once at the mutation point (failure refuses as an unreadable row). Files: installer/wizard_app.py.

## Known Stubs

None.

## Self-Check: PASSED

Commits be3df53, e191f17, 1254c93, 0432e89 exist on the branch; modified files present.
