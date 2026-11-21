# Phase 31 Plan 08 Summary

The evidence gate passed on the recorded summary and transcript:

`herdr-app-container: PASS (2026-11-21; transcript 34591570ed07)`

## Tasks

- **Task 1 — `510f27e8`:** Recorded the container evidence in the `herdr-app` registry comment and onboarding skill row, with tests pinning both. The iTerm2 row makes no container claim. The commit and tests are present; the earlier executor’s RED and GREEN output and six negative-gate results were not available for this summary.
- **Task 2 — `4411f539`:** Added six catalog consistency guards in `tests/test_terminal_json_catalog.py`.
  - Initial GREEN: `...... [100%]`.
  - Mutation RED: removing the app’s `config_paths` failed the default-folder guard; adding `~/.local/bin/` failed the app-paths guard; changing the created-record name failed the naming guard. Each exited 1 and was reverted.
  - Targeted GREEN: the specified eight-file pytest command reached `[100%]`, exit 0.
  - The first commit attempt found five pyright errors caused by iterating object-typed method parameters. After explicit type narrowing, `make typecheck` reported `0 errors`, the targeted tests passed again, and all six commit-hook gates passed.

## Final gates

- `make validate`: exit 0. Lint, format-check, typecheck, security, dead-code and shellcheck **Passed**.
- `make test`: exit 0. **8624 passed, 6 skipped**; coverage **96.26%**, exceeding the 90% requirement.

The run directories created for this task were removed by their exit traps. The pre-existing untracked goal file was left untouched.

## SPEC acceptance evidence

| Criterion | Evidence | Deferred |
|---|---|---|
| iTerm2 profile golden; unavailable on Linux | Plans 31-02 and 31-03 | Real Mac behavior |
| Default profile set and restored, including none set | Plans 31-02 and 31-03, fake `defaults` lifecycle | Real Mac behavior |
| Distinct `herdr` and `herdr-app`, with isolation | Plan 31-05 unit tests; plans 31-06 and 31-07 container evidence | Linux desktop session |
| Intel macOS unavailable for herdr-app | Plan 31-05 fixture | Real Intel Mac |
| Herdr-app keys goldens, kept user binding and displaced-picker note | Plan 31-05 | Live desktop key behavior |
| Drift, reconfigure and owned-only strip for both JSON rows | Plans 31-01, 31-03 and 31-05 | Real Mac and Linux desktop behavior |
| Undeclared same-directory row fails; both rows declared | Plans 31-03 and 31-05; phase 28 test rerun in Task 2 | None for the test |

## Decisions and deviations

- Orchestrator decision 6 gates the **whole plan** on the transcript-bound PASS; only the registry paragraph and herdr-app skill row’s clear cell claim the container evidence.
- Orchestrator decisions 8 and 9 retain citations to real functions and small plans.
- No Task 2 test named by the plan was omitted. Task 1’s historical RED/GREEN tails and six negative-gate outputs could not be reconstructed from its commit; they are not claimed here.
- This executor did not run a container, GUI, real macOS tools or real installations. Live behavior remains a UAT risk.

## UAT lines deferred (no agent marks them passed)

- iTerm2 loads the profile live and makes it the default, whether already running or not.
- Cmd+K sends `0x0c`.
- Option+Left and Option+Right move by word and Spanish `@` still types.
- Parent-map 2-, 3- and 4-part key spelling and the `defaults read` absent-key message, assumptions A2 and A3.
- Colors in light and dark mode.
- `Recycle` for tabs, windows and split panes.
- Uninstall restores the previous default from Terminal.app and from inside iTerm2.
- The herdr-app cask installs into `~/Applications` on Apple Silicon and `cmd-k` clears in its terminal.
- Herdr-app installs and launches on a Linux desktop session, with `ctrl+shift+k` clearing.
- Intel macOS remains fixture-only.

## Phase provisional decisions (need confirmation)

- **31 D-08:** Option stays Normal; two key-map rows. Flagged for owner confirmation.
- **31 D-12:** herdr-app macOS installation uses the cask. Flagged for the owner.
- **31 D-01, D-02, D-04:** Two ownership variants, whole-file proof and per-row validation.
- **31 D-07 with the orchestrator correction:** A malformed Dynamic Profiles file is skipped individually.
- **31 D-09 with orchestrator decision 3:** Merge the parent key map only when readable; 2-, 3- and 4-part spelling remains unverified on a Mac.
- **31 D-10:** Palette values.
- **31 D-11:** Default-profile hook, with the amended runner and ordering.
- **31 D-14, D-15:** `keys.json` on every OS and vendor-default seeding; jev overridden.
- **31 D-16 corrected by orchestrator decision 4:** Use the app’s accepted chord aliases.
- **31 D-17:** Dedicated container target.
- **Orchestrator decision 2 as implemented:** Restore before cask removal; delete the profile file afterward. Unconfirmed restore refuses removal.
- **Orchestrator decision 5:** A blank file is missing for seeding; the created record governs deletion when stripped content equals the vendor default.
- **Orchestrator decision 7:** Exclude herdr-app from the generic e2e all-pass.
- **Accepted `shortcut:` limits:** Need owner confirmation.

## Orchestrator verification

Checked 2026-11-21 05:20 by the orchestrator, independently of the executors' reports (pi, router-env/my-coding, part a (Task 1, 05:05 to 05:08) and part b (Task 2 and gates, 05:09 to 05:12); no BLOCKED claim).

- The container result of this phase is recorded in `31-07-SUMMARY.md` as `herdr-app-container: PASS (2026-11-21; transcript 34591570ed07)`; this plan's gate (`gate_problem`, run by the executor and re-run by the orchestrator through the plan's verify command 1) read it and the transcript before any edit. There is no separate container line for this plan.
- Commits since `79169d37`: `510f27e8` (the container evidence in the `herdr-app` registry comment and skill row, tests pinning both), `4411f539` (six catalog guards in `tests/test_terminal_json_catalog.py`); each passed the commit hook. Plan verifies 1 to 3 re-run by the orchestrator (`run_plan_verifies.py 31-08`): all exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8624 passed, 6 skipped, coverage 96.26%.
