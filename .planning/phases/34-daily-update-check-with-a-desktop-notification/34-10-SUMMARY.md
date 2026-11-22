# Phase 34 Plan 10 Summary

## Tasks

- **Task 1 — oldest-attempt-first refresh:** Previously committed as `ed1ef6b4`. Its RED and GREEN output was not available in this run.
- **Task 2 — self-check hardening:** Implemented and tested locally but not committed by the executor (see the correction above). The changes remain in `installer/update_check.py`, `tests/update_check_doubles.py`, and `tests/test_update_check.py`.

## Test output

Task 2 RED, before the implementation:

```text
FAILED test_a_partial_clone_skips_the_object_queries
FAILED test_the_hardened_self_check_issues_only_read_only_subcommands
FAILED test_a_checkout_that_is_not_its_own_worktree_root_is_skipped
FAILED test_the_skip_reasons_are_the_nine_fixed_strings
```

After implementation, the expanded targeted run still failed:

```text
FAILED test_the_hermetic_check_job_changes_only_the_allowed_files[plain]
FAILED test_the_hermetic_check_job_changes_only_the_allowed_files[adopt]
FAILED test_the_hermetic_check_job_changes_only_the_allowed_files[retire]
FAILED test_the_hermetic_check_job_changes_only_the_allowed_files[link]
```

Each failure is the same obsolete three-query assertion; the added root query produces four. No GREEN result is claimed. Final `make validate` and `make test` were not run because the task could not be committed in a green state.

## Decisions

- 34 D-10 (own reasoning, needs confirmation): oldest-attempt-first uses the last attempt through `attempted_at`; failures rotate to the back.
- 34 D-19 (own reasoning, needs confirmation), with round 3 H4 (needs confirmation): skip a checkout that is not its own worktree root and, when SHAs differ, a partial clone, each with a fixed category.
- Orchestrator decision 12 (provisional, needs confirmation): use fakes; no unit test launches Git.

## Deviations and risk

All four Task 2 test functions named in the plan were added, but the targeted suite remains red. Updating the integration test’s count and expected sequence is necessary to retain its existing assertion meaning; that update needs authorization. Each owned run directory was removed by its exit trap. No live timer, notification, container, or remote-write check was run.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commits `ed1ef6b4` (Task 1: the refresh orders tools by their last attempt, oldest first) and `41e60a1a` (Task 2: the self-check skips a checkout that is not its own worktree root and a partial clone, nine fixed skip categories). CORRECTION to the executor's text below: Task 2 was implemented and tested by the executor but it stopped (BLOCKED) before committing, because the new worktree-root query makes plan 34-09's job test (`tests/test_update_check_job.py`, which asserted exactly three git queries) fail and the plan did not list that file. The orchestrator updated that phase-34 assertion to the four-query sequence (branch, toplevel, HEAD, ls-remote), fixed two commit-hook findings (formatting and one lint rule) and made the commit; no other assertion was changed.
- The plan's verify re-run (owned scratch `TMPDIR`): exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 9398 passed, 6 skipped, coverage 96.44%.
- No timer, notification or container was run; the self-check is tested over a fake git callable only (pytest forbids real git).

Provisional decisions carried to the verification report (needs owner confirmation): orchestrator decision 5 and the review H4 (the self-update line is skipped when HEAD is detached, the branch is not main, the checkout is not its own worktree root or the clone is partial; fixed skip categories; older git may ignore the lazy-fetch variable); the oldest-last-attempt order so failing tools rotate.

orchestrator-verification: none required

orchestrator-verification: none required
