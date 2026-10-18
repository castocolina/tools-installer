---
phase: 20-install-plan-with-dispositions
plan: "26"
subsystem: installer
tags: [python, textual, installer, install-plan, oh-my-zsh]

# Dependency graph
requires:
  - phase: 20-20
    provides: Install-plan review and reinstall disposition
  - phase: 20-24
    provides: Shared install seam and run-aware manual handoff bookkeeping
provides:
  - Opt-in handling for install methods that refuse to run over an existing installation
  - Oh My Zsh reinstall handoff without rerunning its upstream installer
  - Boolean validation and TUI coverage for fresh and reinstall flows
affects: [phase-20, installer, install-plan, oh-my-zsh]

# Actuals
actuals:
  tokens: 3710
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A refusing-existing method on a present tool skips execution only for an explicit repair/reinstall and dispatches reviewed post-install actions."

key-files:
  created:
    - .planning/phases/20-install-plan-with-dispositions/20-26-SUMMARY.md
  modified:
    - installer/engine.py
    - installer/model.py
    - installer/post_install.py
    - installer/registry.toml
    - tests/test_engine.py
    - tests/test_execute_screen.py
    - tests/test_model.py

key-decisions:
  - "Kept the behavior opt-in per script method and guarded it by both published presence and explicit repair/reinstall."
  - "Kept health and plan-time copy unchanged; refusal is represented by a manual result and a reviewed handoff."

patterns-established:
  - "Handoff-only MANUAL_REQUIRED results do not write receipts, run commands, or count as work; confirmation for sensitive actions still applies."

requirements-completed: [PLAN-02]
coverage:
  - id: D1
    description: "Repair/reinstall of present Oh My Zsh skips its refusing installer, dispatches the confirmed chsh handoff, and stays manual without counting as run work."
    requirement: PLAN-02
    verification:
      - kind: unit
        ref: tests/test_engine.py#test_a_present_tool_whose_installer_refuses_existing_is_not_re_run_on_repair
        status: pass
      - kind: automated_ui
        ref: tests/test_execute_screen.py#test_r_on_an_installed_oh_my_zsh_shows_the_reviewed_chsh_handoff
        status: pass
    human_judgment: false
  - id: D2
    description: "Fresh Oh My Zsh install still dispatches the sensitive handoff in the TUI, and refusing-existing is a bool-validated opt-in."
    requirement: PLAN-02
    verification:
      - kind: automated_ui
        ref: tests/test_execute_screen.py#test_a_fresh_oh_my_zsh_install_in_the_review_shows_the_reviewed_chsh_handoff
        status: pass
      - kind: unit
        ref: tests/test_model.py#test_refuses_existing_must_be_a_bool
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-10-18
status: complete
---

# Phase 20 Plan 26: Install Plan with Dispositions Summary

**Present Oh My Zsh reinstalls now show the reviewed login-shell handoff without rerunning the refusing installer, while fresh installs and other methods keep their existing behavior.**

## Performance

- **Duration:** approximately 4 minutes of implementation and verification.
- **Started:** 2026-10-18T09:52:00-03:00
- **Completed:** 2026-10-18T09:56:00-03:00
- **Tasks:** 2
- **Files modified:** 7 implementation/test files, plus this summary.

## Accomplishments

- Marked only oh-my-zsh's script installer with `refuses_existing = true`, based on the recorded upstream refusal behavior.
- Added a narrow engine branch for a present tool under explicit repair/reinstall. It skips the runner and receipt, dispatches declared `post_install` actions, and returns the not-rerun instruction as `MANUAL_REQUIRED`.
- Validated the opt-in field as a boolean and documented the reinstall dispatch behavior.
- Pinned the installed `r` flow, fresh TUI install flow, and the absent-tool guard through the real engine. Existing headless and execute-plan fresh-install pins remain in place.
- Left health, disposition planning, and protected `.planning/config.json` unchanged.

## Task Commits

1. **Task 1: `r` on installed Oh My Zsh shows the reviewed handoff** - `15a85b1`
2. **Task 2: validate the key and pin the fresh TUI handoff** - `19a6981`

## Files Created/Modified

- `installer/registry.toml` - opt-in key and dated upstream behavior comment for Oh My Zsh.
- `installer/model.py` - script-method parameter and bool validation.
- `installer/engine.py` - present+repair refusal handling, with no runner or receipt write.
- `installer/post_install.py` - documents actions dispatching when the installer refuses a present install.
- `tests/test_engine.py` - refusal, absent-tool, and registry uniqueness tests.
- `tests/test_execute_screen.py` - installed reinstall and fresh install TUI coverage through the real engine.
- `tests/test_model.py` - invalid boolean shape validation.
- `20-26-SUMMARY.md` - execution record.

## Decisions Made

- Preserved the locked reinstall-only behavior. No health exception, zsh-shell drift reason, `--yes` exception, or architecture exception was introduced.
- The engine condition remains strictly `installed and repair and refuses_existing is True`; an absent tool still executes the method, and other reinstall methods retain their ladder behavior.

## Deviations from Plan

None. Work stayed on `main`; no branch or worktree was created. The orchestrator-owned `.planning/config.json` was preserved and not staged.

## Issues Encountered

- The initial test draft used the wrong `CommandError` call shape and the TUI seam needed an install wrapper to provide the recording runner and presence predicate; corrected before the valid RED run.
- An initial test placement accidentally inherited an adjacent pytest parameterization; corrected before running its RED assertion.
- The fresh-install TUI pin exposed that the engine's script smoke logic probes the installed command; the test's `which` fake was narrowed to return `/usr/bin/chsh` only for `chsh`, matching the real handoff dependency and keeping the run isolated.
- The first quality-gate attempt caught a line-length issue, then pyright caught test-double typing and private-field access; all were fixed without adding suppressions.
- A final-review subagent dispatch was attempted but the available reviewer lane returned an upstream policy-budget error. Per the review procedure, the author performed a read-only self-review of the committed range; this is weaker than an independent review.

## RED / Pin / GREEN Evidence

### Task 1

RED command:

```text
uv run pytest tests/test_engine.py tests/test_execute_screen.py -q --no-cov -n 0 -k "refuses_existing or refusing_method or chsh_handoff"
```

RED output: `F.F` (2 failed, 1 passed). The engine test reached the existing script runner and returned `FAILED` instead of `MANUAL_REQUIRED`; the TUI reinstall finished as failed without presenting `SensitiveActionScreen`. The registry uniqueness test already passed because its empty result did not match the expected set. A preceding draft run failed on the incorrect `CommandError` constructor, and was corrected before this valid RED evidence.

GREEN command: same command after implementation.

GREEN output: `... [100%]`.

Task verification:

```text
uv run pytest tests/test_engine.py tests/test_execute_screen.py tests/test_model.py tests/test_registry.py tests/test_session.py -q --no-cov -n auto
```

Result: all tests passed. `make validate && make test` passed on the Task 1 implementation tree: 4,891 passed, 4 skipped, 96.00% coverage.

### Task 2

The fresh TUI test was added as the planned pin. Its first run exposed a test harness issue (the broad `which` fake also made the smoke probe select nonexistent `/usr/bin/chsh`); after narrowing the fake, it passed. The pre-change tree was not separately run with this newly added test:

```text
uv run pytest tests/test_execute_screen.py -q --no-cov -n 0 -k fresh_oh_my_zsh
. [100%]
```

The validation test RED:

```text
uv run pytest tests/test_model.py -q --no-cov -n 0 -k refuses_existing_must
F [100%]
Failed: DID NOT RAISE <class 'ValueError'>
```

After adding the loader check:

```text
uv run pytest tests/test_model.py -q --no-cov -n 0 -k refuses_existing_must
. [100%]
```

Task verification:

```text
uv run pytest tests/test_model.py tests/test_execute_screen.py tests/test_post_install.py tests/test_app.py tests/test_session.py -q --no-cov -n auto
```

Result: all tests passed. The suppression-count gate passed (no increase). Final `make validate && make test` passed: 4,892 passed, 4 skipped, 96.00% coverage. A subsequent focused run across engine, execute screen, model, registry, post-install, app, and session files also passed; its exact collected count was not recorded.

Collected-test floors (start → final):

- `tests/test_engine.py`: 74 → 77
- `tests/test_execute_screen.py`: 128 → 130
- `tests/test_model.py`: 122 → 123
- `tests/test_post_install.py`: 13 → 13

## Fresh-install pins

- Headless, real engine: `tests/test_app.py::test_run_wizard_prints_login_shell_instructions_when_sensitive_confirmed`.
- `execute_plan`, real engine: `tests/test_session.py::test_with_sensitive_confirm_reaches_post_install_gate`.
- TUI, real engine: `tests/test_execute_screen.py::test_a_fresh_oh_my_zsh_install_in_the_review_shows_the_reviewed_chsh_handoff`.

## UI-SPEC Copy Addition

The new line is rendered from the outcome handoff:

```text
{tool_id}: its installer refuses to run over an existing install, so it was not re-run.
```

For the Oh My Zsh registry ID, it reads: `oh-my-zsh: its installer refuses to run over an existing install, so it was not re-run.`

## Final Review

Read-only self-review of `5b6447b..19a6981` after the independent reviewer dispatch failed due to the upstream policy budget. No findings identified. The code review is not independent; the human should treat it as a weaker check.

## Next Phase Readiness

- PLAN-02 is implemented and covered; both task commits are on `main`.
- No host installation, shell configuration change, or other host mutation was performed.
- `.planning/config.json` remains orchestrator-owned and untouched by this plan.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
