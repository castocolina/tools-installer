---
phase: 21-one-screen-family
plan: "08"
subsystem: uninstall-projection
tags: [uninstall, tool-state, pure-projection]
requires: [21-05, 21-07]
provides: [uninstall_group, uninstall_label, uninstall_detail, HEALTH_DETAIL]
affects: [21-11, 21-12]
key-files:
  modified:
    - installer/version_status.py
    - installer/catalog_tui.py
    - tests/test_version_status.py
decisions:
  - "Projection lives in version_status (import cycle with uninstall otherwise)"
  - "HEALTH_DETAIL moved unchanged from catalog_tui to version_status (REUSE 08-1)"
status: complete
commits: 4
plan_head_before: f5e8a975f3f86827c0d1ae69667fb20bb4c8c5a0
plan_head_after: aabf3db9cfb14cf3aac97ec5d76d2b0f3ac7fff2
actuals:
  tokens: 9000
  tasks: 2
  commits: 4
---

# Phase 21 Plan 08: Uninstall row projections Summary

Three pure functions in `installer/version_status.py` (`uninstall_group`, `uninstall_label`, `uninstall_detail`) project one published `ToolState` to its Uninstall group, Installed-via cell and detail sentence; an unknown owner is never attributed, and the yourself / required-by suffixes of `classify_tools` survive.

## Commits

- 82d8cec test(21-08): RED for group/label/proof/nothing-to-do (with NotImplementedError stubs so pyright resolves the symbols; `required_by` is passed to the exception so vulture accepts the stub)
- 854700d feat(21-08): group, label, proof, `HEALTH_DETAIL` moved to `version_status`, catalog re-pointed
- 26c46ed test(21-08): RED for managed rows, prohibition and suffixes (adds the two remaining copy constants so the tests import)
- aabf3db feat(21-08): managed branch, BROKEN repair text, unknown owner, suffixes

## RED output

Task 1 (all 15 new cases): `FAILED test_uninstall_group[...]` x7, `test_uninstall_label[...]` x6, `test_uninstall_detail_proof`, `test_uninstall_detail_nothing_to_do` - all `NotImplementedError`.

Task 2: 7 of 8 failed (`known_owner_shows_the_removal_command`, `known_owner_without_package_shows_the_sentence`, `unknown_owner_names_no_manager`, `broken_shows_the_repair_text`, `keeps_the_yourself_suffix`, `keeps_the_required_by_suffix`, `removable_detail_keeps_the_yourself_suffix`). The unproven-installer test already passed because the Task 1 fallback returns the joined reasons.

## GREEN

`make validate` exit 0; `make test` exit 0, 5025 passed, 4 skipped, coverage 96.08%.

## Collected count of tests/test_version_status.py

Start 199, end 222. The plan floors (218, 226) assumed more parametrized cases (3 per proof/nothing-to-do test as separate params); the plan's behavior list is fully covered (23 new cases: 7 + 6 + 1 + 1 + 8). The 226 floor is not met numerically; no listed behavior is missing.

## Deviations from Plan

None in behavior. Existing tests changed: none (no test referenced `_HEALTH_DETAIL`).

## Known Stubs

None.

## Self-Check: PASSED

All four commits exist; the three files exist and are committed.
