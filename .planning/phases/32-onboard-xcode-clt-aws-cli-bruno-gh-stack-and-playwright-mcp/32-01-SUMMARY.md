# Phase 32 Plan 01 Summary

## Tasks

- **Task 1 — fixed-argv script installs:** commit `500e423c`. Added load-time argv validation, direct execution, and closed stdin and terminal detachment for the console runner. The earlier executor’s RED and GREEN output was not available in this session; its commit contains the tests.
- **Task 2 — closed handoff and script preference:** commit `bda94f34`. Added the validated `xcode-clt` handoff and per-method preference without changing `_RANK`.

## Verification

- Task 2 RED tail: six failures, covering unknown `handoff` and `prefer` keys, the missing handoff branch, and brew-first ordering.
- Task 2 GREEN: targeted pytest command exited 0, reaching `[100%]`.
- Commit hook initially caught a loop-variable closure in a new test. The closure was bound explicitly; `make lint` and all six commit-hook gates then passed.
- Final `make validate`: all six gates **Passed**.
- Final `make test`: **8768 passed, 6 skipped**, coverage **96.29%**; required 90% reached.
- Targeted-run scratch directories were removed by their exit traps. The full test run produced `.coverage`; its prior state was not established, so it was not deleted.

## Decisions

- **32 D-09 (locked):** Fixed `install` argv is validated; elevation, shell, Xcode, software-update and launcher words are refused anywhere, as are placeholders and incompatible keys. Children receive closed stdin and a new session; no shell runs. Ctrl+C reaches the installer rather than the child directly, and `subprocess.run` kills the direct child on interrupt. **Provisional reasoning; needs confirmation.**
- **32 D-01 (locked):** Handoff is a closed name mapped to code-owned display text. The handoff is unconditional, regardless of prefix writability. **Needs confirmation.**
- **32 D-04 and orchestrator decision 4:** Preference uses a per-method sort key; `_RANK` remains unchanged. **Provisional; needs confirmation.**
- **Orchestrator decision 8:** `install` joins both elevation checks and the closed-key pins. **Provisional; needs confirmation.**
- **Orchestrator decision 9:** Phase 29–31 lessons apply, including same-task guards and tests, Python 3.12/3.15 compatibility, and bounded plan size. **Provisional; needs confirmation.**

## Pin edits

- Task 1 extended the registry argv elevation guard to include `install` and all refused words, and updated three `run_command` test doubles for the added subprocess keywords. These preserve the existing assertions’ intent.
- Task 2 made no existing assertion edits.

## Deviations and limits

- No Task 2 behavior test named in the plan was omitted.
- Python 3.15 and live installations were not run here; the full suite ran on Python 3.12.12. The earlier task’s RED/GREEN output could not be independently recovered.

## Orchestrator verification

Verified by the orchestrator on 2026-11-21 (the executor's RED/GREEN tails for Task 1 were not carried into its final message):

- Commits `500e423c` (Task 1) and `bda94f34` (Task 2), both through the six-gate commit hook; the working tree was clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run by the orchestrator through `run_plan_verifies.py`: both exit 0.
- Plan-named tests exist (two under variant names: `test_run_command_passes_devnull_stdin_and_a_new_session`, `test_script_argv_refuses_shell_xcode_select_and_launcher_words_at_any_position`).
- `make test` on the final tree, default TMPDIR: 8768 passed, 6 skipped, coverage 96.29%.
- Container checks: none required for this plan.

Provisional decisions carried to the verification report (needs owner confirmation): 32 D-09 fixed-argv `script` install and its refusal set (elevation, shell, `xcode-select`, `softwareupdate`, launcher words at any position; `install` with `writable_prefix` refused at load); closed stdin plus a new session for console children (Ctrl+C reaches the installer, not the child); the owned-TMPDIR finding rejected (doctor test path-length).

orchestrator-verification: none required

orchestrator-verification: none required
