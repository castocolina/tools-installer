---
phase: 21-one-screen-family
plan: "02"
subsystem: session-vocabulary
tags: [removal, outcome-vocabulary]
requires: []
provides: [Disposition.REMOVE, remove_failed result, session.first_line]
affects: [21-09, 21-13]
key-files:
  modified: [installer/session.py, installer/render.py, tests/test_session.py, tests/test_render.py, tests/test_plan.py]
requirements: [UI-05]
status: complete
actuals:
  tokens: 6000
  tasks: 2
  commits: 2
plan_head_before: 390f464298f06a30365de37e11510d5479afa09a
plan_head_after: 0a960d6
---

# Phase 21 Plan 02: Removal vocabulary Summary

`Disposition.REMOVE` and `remove_failed` join the shared WORDS/RESULT_WORDS tables, `_FAILURE` and `_FAILURE_RESULTS`; `session.first_line` is public.

## Commits
- 79a0072 feat(21-02): removed and remove failed join the outcome vocabulary
- 0a960d6 refactor(21-02): make session.first_line public for the removal path

## RED / GREEN
- Task 1 RED: `-k "removed or ... never_emits_remove"` failed with `AttributeError: REMOVE` (render parametrizations, test_outcome_words_for_removal, 7x test_build_plan_never_emits_remove). GREEN after implementation.
- Task 2 RED: `ImportError: cannot import name 'first_line' from 'installer.session'`. GREEN after rename.
- Collected counts (start -> end): test_session 96 -> 100, test_render 122 -> 126, test_plan 80 -> 87.
- `make validate` exit 0, `make test` exit 0 (4938 passed, 4 skipped) on the final tree; Task 1 tree: 4937 passed.

## Deviations from Plan
- [Rule 1] `test_result_words_cover_every_non_done_result_the_engine_can_produce` pins the exact RESULT_WORDS key set; added `"remove_failed"` to it.
- [Rule 3] In `execute_plan` a local named `first_line` would shadow the renamed function; renamed the local to `lines`.
- Plan-head ledger file was not written (worktree git-dir command refused by the sandbox); base is the known spawn HEAD above.

## Known Stubs
None.

## Self-Check: PASSED
