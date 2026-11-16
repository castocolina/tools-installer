---
phase: 21-one-screen-family
plan: "04"
subsystem: policy
tags: [policy, live-state, ui-06]
requires: []
provides:
  - "installed_tools predicate on tweak_policy, daemon_policy, linux_daemon_policy"
  - "missing_requires_now on tweak and macOS daemon policies"
  - "omz_plugins_policy.is_active live"
affects: [21-17]
key-files:
  modified:
    - installer/policy.py
    - tests/test_policy_tweaks.py
    - tests/test_policy_daemon.py
    - tests/test_policy_omz.py
    - tests/test_policy_linux_daemon.py
status: complete
commits: 2
plan_head_before: 390f464298f06a30365de37e11510d5479afa09a
plan_head_after: b304d45
actuals:
  tokens: 6000
  tasks: 2
  commits: 2
---

# Phase 21 Plan 04: Live policy prerequisites Summary

`tweak_policy`, `daemon_policy` and `linux_daemon_policy` now accept a mapping or a live `Callable[[str], bool]`; tweak and macOS daemon set `missing_requires_now` so `missing_requirements()` answers at render time, and `omz_plugins_policy` answers `is_active()` live.

## Commits

- 7c382cc feat(21-04): tweak policies read their prerequisites from a live predicate
- b304d45 feat(21-04): daemon and omz policies answer prerequisites and active state live

## Decisions

- One private helper `_installed_predicate(installed_tools)` in `installer/policy.py` serves both `tweak_policy` and `daemon_policy` (callable as-is; mapping or None wrapped in a `.get(id, False)` lookup).
- `linux_daemon_policy` only widens its annotation; it still discards the argument.
- macOS `is_active` already was `plist_path.exists()`; pinned by `test_macos_prune_reads_off_without_its_plist` (passes on first run by design, so it has no RED).

## RED / GREEN

Task 1 RED: `AttributeError: 'function' object has no attribute 'get'` at `installer/policy.py:588` (`test_tweak_policy_reads_requirements_live` failed). GREEN: `tests/test_policy_tweaks.py tests/test_policy.py tests/test_policies_e2e.py tests/test_setup.py` all pass.

Task 2 RED: `FAILED tests/test_policy_daemon.py::test_daemon_policy_reads_requirements_live` (same AttributeError) and `FAILED tests/test_policy_omz.py::test_omz_policy_is_active_reads_ownership_live` (`is_active` was None). The Linux predicate test and plist test passed already (existing behavior pinned). GREEN: the six-file run passes.

## Verification

- `make validate` exit 0; `make test` exit 0, 4929 passed, 4 skipped, coverage 96.03% (run on the final tree; Task 1 tree: 4925 passed).
- Collected counts, start -> end: tweaks 18 -> 20, daemon 23 -> 25, omz 9 -> 10, linux_daemon 29 -> 30.
- No new suppression comments; no package changes.

## Deviations from Plan

None - plan executed exactly as written. Test helper `_build` annotations in the daemon and Linux test files were widened to accept a predicate.

## Known Stubs

None.

## Self-Check: PASSED

Both commits exist (7c382cc, b304d45); the five modified files exist.
