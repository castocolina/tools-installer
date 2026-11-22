# Phase 34 Plan 04 Summary

## Tasks

- **Task 1 — self-check:** `306f5cc1` added the installer checkout comparison using an injected, read-only Git runner.
- **Task 2 — state and evidence:** `35204662` added the strict notified-set reader and atomic writer, confirmed-only membership, and fitted result line.
- **Task 3 — check flow:** `ebc2e22f` added `run_check`, shared fakes and flow tests. It refreshes with a 20-hour staleness window, preserves unknown membership, sends notifications on changed non-empty sets and reports ordered result clauses.

## Verification

- **Tasks 1 and 2 RED/GREEN output:** unavailable in this split run; their commits were present at dispatch.
- **Task 3 RED tail:** 13 flow cases failed with `AttributeError: module 'installer.update_check' has no attribute 'run_check'`.
- **Task 3 GREEN tail:** the targeted `test_update_check.py`, `test_version_cache.py` and `test_version_status.py` command exited 0, reaching `[100%]`.
- **Commit hook:** all six static gates passed. An initial hook attempt found lint and formatting issues; these were corrected, and the affected gates were rerun successfully.
- **`make validate` tail:** lint, format-check, typecheck, security, dead-code and shellcheck all `Passed`.
- **NAMED RED-GUARD EXCEPTION:** the full-suite command with the single reachability guard deselected exited 0: `9302 passed, 6 skipped in 74.75s`; coverage was `96.43%`, above the 90% requirement. This was not a green `make test`.

The separately run reachability guard produced the expected failure:

```text
_________ test_every_installer_module_is_reachable_from_an_entry_point _________

    def test_every_installer_module_is_reachable_from_an_entry_point() -> None:
>       assert _unreachable_modules(_ROOT) == []
E       AssertionError: assert ['installer.update_check'] == []
E         
E         Left contains one more item: 'installer.update_check'
E         Use -v to get more diff

tests/test_reachability.py:197: AssertionError
```

## Decisions

- **34 D-14:** locked, jev overridden, needs confirmation — keep the notified set in its own file and write it with `atomic_replace_entry`.
- **34 D-15:** own reasoning, needs confirmation — notify before storing and store only after success; a shrinking non-empty set notifies again (orchestrator decision 6, needs confirmation). Confirm membership only on fresh, non-stale evidence; unknown membership is retained (rounds 2 and 3, needs confirmation). An uninstalled tool leaves the set at once (needs confirmation).
- **34 D-19:** own reasoning, needs confirmation — report fixed self-check failure categories only; the isolated production runner belongs to plan 34-05.
- **34 D-20:** own reasoning, needs confirmation — behind means the remote differs and is not an ancestor; a missing local object reported by bare `cat-file -e` exit 1 means upstream has new commits.
- **34 D-21:** locked — one result line carries ordered clauses within 300 characters.
- **Orchestrator decision 5:** needs confirmation — detached HEAD and branches other than `main` silently skip the self-check.
- **Orchestrator decision 12:** needs confirmation — use fakes only; the reachability guard is red for exactly this plan.
- **34 D-23:** locked — scratch HOME and fakes only.

## Deviations and limits

- The plan-named `test_a_shrinking_non_empty_set_notifies_again` was not written under that exact name. Shrinking non-empty sets are asserted in `test_the_set_rules_over_several_runs` and `test_a_real_shrink_is_told_apart_from_stale_evidence`.
- The result-line fitter now divides the available reason budget among non-empty reasons, rather than fixed-label-only clauses; this preserves the specified equal share for reasons.
- Every run directory created by this executor was removed by its EXIT trap. No timer, real notification, container or remote write was run. Python 3.15 and real desktop delivery were not checked.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commits `306f5cc1` (Task 1: the installer self-check over an injected git runner), `35204662` (Task 2: the notified-set file, the evidence rule, the fitted result line) and `ebc2e22f` (Task 3: the update check with its one result line), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run: every one exits 0 except the reachability check, which my runner could not execute because the plan writes to `$TMPDIR`; I ran the equivalent directly: `tests/test_reachability.py::test_every_installer_module_is_reachable_from_an_entry_point` fails with exactly `assert ['installer.update_check'] == []`, which is the PLAN'S NAMED RED-GUARD EXCEPTION (the module is wired by plan 34-05, whose first commit clears it). The full suite on this tree: 9302 passed, 6 skipped, with that single test red (and 96.43% coverage with the test deselected). This is NOT a green `make test`; the branch is not pushed until plan 34-05 clears the guard.
- One plan-named test was not written under its exact name (`test_a_shrinking_non_empty_set_notifies_again`): the shrinking non-empty set is asserted in `test_the_set_rules_over_several_runs` and `test_a_real_shrink_is_told_apart_from_stale_evidence`, both present.
- No timer, notification, container or remote write was run; the self-check is tested over a fake git callable only (pytest forbids real git), so real-git behavior is an orchestrator or owner observation.

Provisional decisions carried to the verification report (needs owner confirmation): D-13 to D-15 and D-19 to D-21 (outdated set, notified-set file, notify then store, self-check, one result line); orchestrator decision 5 (the self-update line is skipped silently on a detached HEAD or a non-main branch); decision 6 (a shrinking non-empty set notifies again); the confirmed-only membership rule (an id counts as in or out only when its comparison is not stale and freshly stamped this run; unknown ids keep their prior membership); the daily limit is the timer cadence; the symlink-safe notified file (`atomic_replace_entry`, mode 0600); credential helpers disabled and fixed skip categories for git failures.

orchestrator-verification: none required

orchestrator-verification: none required
