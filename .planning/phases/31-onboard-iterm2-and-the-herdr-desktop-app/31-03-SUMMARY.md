# Phase 31 Plan 03 Summary

- **Task 1 — `a1842faa`:** Added the iTerm2 registry entry, owned Dynamic Profile row, pre-removal restore and refusal path, skill-table row, and registry/status coverage. The split-run record does not include the Task 1 RED or GREEN output tails; they cannot be recovered from the commit.
- **Task 2 — `966f0484`:** Added lifecycle and public uninstall-route tests, including failed restores, lost state, failed cask removal, failed record updates, retries, and protection of an undeclared config folder. No RED run exists for Task 2: Task 1 had already implemented the behavior, as the plan anticipated. The targeted GREEN run completed at `[100%]` with exit 0.

## Verification

- Targeted Task 2 command: passed, exit 0. The dependent `test_version_status.py` and `test_tool_onboarding_skill.py` runs also passed.
- Commit hook: lint, format check, typecheck, security, dead-code and shellcheck all **Passed**.
- `make validate`: all six gates **Passed**.
- `make test`: **8413 passed, 6 skipped**; total coverage **96.25%**, exceeding the 90% requirement.
- Run directories created for targeted tests were removed by their exit traps. The pre-existing untracked goal file was left untouched.

## Existing tests edited

- `tests/test_registry.py`: `_POST_15_3_HUMAN_TOOLS`, `MACOS_ONLY`, audience and tier distribution pins, tool count, and `test_only_reviewed_tools_declare_a_post_install_action` — include the new iTerm2 entry.
- `tests/test_resolve.py`: `_FIRST_METHOD` — pin cask on macOS and unavailability on the three Linux fixtures.
- `tests/test_terminal_keys.py`: `test_alacritty_row_is_keyed_by_its_registry_id` and `test_completeness_fails_on_an_empty_table` — include the new terminal row.
- `tests/test_tool_onboarding_skill.py`: added the iTerm2 table-row proof.
- `tests/test_version_status.py`: appended iTerm2 tests for unrecorded tuning, profile drift and a pending default switch.
- `tests/test_iterm2_row.py`: Task 2 extended the Task 1 fake and added the lifecycle and removal tests.

## Decisions and deviations

- D-05/D-06: iTerm2 is a macOS cask entry with no declared config paths. D-02/D-03: the profile is installer-owned, and a deleted profile remains pending when the default still names it.
- D-07/D-08: the profile writes `Recycle`; Option remains Normal and word navigation uses key-map rows. D-11: the row hook manages the default profile.
- Orchestrator decision 2 differs from its original restore-and-delete-before-cask wording: restore is confirmed before cask removal; deletion follows removal so a running iTerm2 cannot overwrite the restored preference when the profile disappears.
- Every named Task 2 test was added. The failed-cask test checks `terminal_keys_pending` directly; it does **not** itself assert the status-pass text. Task 1’s separate pending-switch status test covers that mapping.
- Task 1 RED/GREEN output tails were not available in this split run. No production-code fix was needed in Task 2.
- Real-Mac behavior, including removal from inside iTerm2, remains owner UAT; no live application, macOS command, GUI or container was run.

## Provisional decisions (need confirmation)

orchestrator decision 2 as implemented: the previous default is restored before the cask removal, an unconfirmed restore refuses the removal (cask and receipt kept) and the profile file is deleted after the removal; needs confirmation, real-Mac result is a UAT line

31 D-08: Option stays Normal and word navigation is two keyboard-map rows (the install note says so); flagged, needs confirmation

31 D-11: the default profile is set at install and restored at uninstall through the row's hook; needs confirmation

31 D-12, the 2026-11-21 amendments to D-07, D-09, D-11 and D-16, the parent key-map rule, keys.json edge cases, and accepted `shortcut:` limits also need owner confirmation.

## Orchestrator verification

Checked 2026-11-21 03:30 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding, part a (Task 1, 03:12 to 03:15) and part b (Task 2 and gates, 03:16 to 03:19); no BLOCKED claim).

- Commits since `34f4312e`: `a1842faa` (the iTerm2 entry, row, pre-removal restore and refusal, skill row), `966f0484` (lifecycle and public uninstall-route tests); each passed the commit hook. Plan verifies re-run by the orchestrator (`run_plan_verifies.py 31-03`): all exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8413 passed, 6 skipped, coverage 96.25% (the reachability guard is green again now that the row imports the profile module).
- Production diff read: `remove_tool` is a thin wrapper over `_remove_tool_steps` that appends the pre-removal lines to every outcome's detail; before the manager command a terminal row's `before_removal_terminal_keys` runs and an unconfirmed restore returns a refusal (cask and receipt kept, message naming the fix); the profile file is deleted after the removal by the later strip, so a running iTerm2 cannot overwrite the restored default.
- Open: the failed-cask test checks `terminal_keys_pending` directly and Task 1's status test covers the status-pass text; Task 1's RED and GREEN tails were not available in the split run.

herdr-app-container: not run
