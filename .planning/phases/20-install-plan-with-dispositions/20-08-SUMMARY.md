---
phase: 20-install-plan-with-dispositions
plan: 08
subsystem: infra
tags: python, install-plan, execution, reconfigure, config-steps, tdd, pytest

# Dependency graph
requires:
  - phase: 20-install-plan-with-dispositions
    provides: execute_plan with its per-row try, RunContext (runner, terminal_sync, on_row_started), RowOutcome and the interim RECONFIGURE branch
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: typed ConfigStep/ConfigStepKind producers, the node group executor (L-19-28) and the reviewed skill handoff (L-19-07)
provides:
  - one RECONFIGURE dispatcher keyed by ConfigStep.kind that runs or hands off all eight kinds
  - in_directory, the portable per-step cwd wrapper, plus execution-time cwd validation via lstat
  - stop-at-first-failure step ordering with per-step refusal details, and manual rows for handoff lines
  - a kind-set guard (_STEP_KINDS) so an undeclared step kind can never reach a command path
affects: [20-09, 20-10, 20-11, execute-screen, wizard-app, doctor-repair]

# Actuals (#2632)
actuals:
  tokens: 9200
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - one dispatcher per step kind, its set equality asserted against the model's Literal
    - execution-time re-validation of a path discovered minutes earlier (lstat, never stat)
    - an external executor's own refusals read as failed steps, its unexpected errors as row crashes
    - handoff lines carried on RowOutcome.install so the existing renderer prints them unchanged

key-files:
  created: []
  modified:
    - installer/session.py
    - tests/test_session.py

key-decisions:
  - "in_directory wraps argv in `sh -c 'cd -- \"$1\" && shift && exec \"$@\"' sh <cwd> …` — positional parameters only, no shell interpretation, no process-global chdir, and portable to macOS where `env -C` is absent."
  - "_valid_cwd is is_absolute() plus stat.S_ISDIR(path.lstat().st_mode) inside try/except OSError; lstat on a symlink reports S_IFLNK, so the S_ISDIR test already refuses it (REUSE 08-1) and the refusal text names the field."
  - "pnpm_group_install carries no argv: it dispatches executors.execute on the declaring tool's first node method, so the group, --allow-build, real pnpm and the smoke floors cannot drift from install and update (19 L-19-28, review H10)."
  - "An argv-less skill_install is a reviewed handoff through perform_action; manual-required → RowOutcome.install with MANUAL_REQUIRED, completed/present → ran, absent/unknown → failed with the lifecycle's own word (19 L-19-07)."
  - "terminal_sync's returned warning becomes the row detail while the step counts as run; an unbound synchronizer is a failed step."
  - "perform_action's ValueError stays outside the per-step catch list: from a partial_steps-produced row it is unreachable, so if it ever fires the row fails closed as crashed (exit 1, row kept selected)."

patterns-established:
  - "Kind-set guard: `_run_step` refuses anything outside `_STEP_KINDS`, and `test_each_config_step_kind_dispatches` is parametrized over every member with the set equality asserted inside each case — so a ninth kind is a failing test rather than an unreviewed command."
  - "Stop-at-first-failure rows: a RECONFIGURE row never continues past a failed step, preserving 19 D-18's enable-before-remove order; the failure does not propagate `dependency_failed` to dependents because the tool is still on disk."
  - "REUSE findings applied as written are recorded in the SDD ledger with the test that pins the trust-boundary property, not re-litigated per task."

requirements-completed: [PLAN-03]

coverage:
  - id: D1
    description: "A RECONFIGURE row runs its argv steps in order through ctx.runner, wrapped in the portable directory shim when a cwd is set, and is done."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_runs_argv_steps_in_order_and_is_done"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_wraps_a_step_with_cwd_in_the_portable_directory_shim"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_step_without_a_command_fails"
        status: pass
    human_judgment: false
  - id: D2
    description: "ConfigStep.cwd is re-validated at execution time (absolute, lstat says directory, not a symlink) and a refusal stops the step without running it (T-20-14, V12)."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_refuses_a_cwd_that_is_relative_missing_or_a_symlink[relative|missing|symlink]"
        status: pass
    human_judgment: false
  - id: D3
    description: "Steps stop at the first failure with the step text and reason as detail, and a RECONFIGURE failure does not propagate dependency_failed to dependents (T-20-15, RESEARCH A7)."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_stops_at_the_first_failing_step"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_failure_does_not_block_a_dependent"
        status: pass
    human_judgment: false
  - id: D4
    description: "pnpm_group_install runs the declaring tool's first node method through the same executor install and update use, reporting the executor's own refusals as failed steps (19 L-19-28)."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_pnpm_group_install_runs_the_tools_first_node_method"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_pnpm_group_install_reports_the_executors_own_refusal"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_each_config_step_kind_dispatches[pnpm_group_install]"
        status: pass
    human_judgment: false
  - id: D5
    description: "terminal_sync calls the synchronizer the app bound, keeps its warning as row detail, and fails when none is bound."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_terminal_sync_step_calls_the_bound_synchronizer[with warning|without warning]"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next"
        status: pass
    human_judgment: false
  - id: D6
    description: "An argv-less skill_install is a reviewed handoff whose lines land on RowOutcome.install, making the row manual; an absent/unknown lifecycle answer fails with that word (19 L-19-07)."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_skill_install_without_argv_is_a_reviewed_handoff_and_manual"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_skill_install_reports_what_the_lifecycle_returned[absent|unknown|completed|present]"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_skill_install_with_argv_runs_it"
        status: pass
    human_judgment: false
  - id: D7
    description: "Every ConfigStepKind has a branch, an undeclared kind is refused instead of run, and perform_action's ValueError fails the row closed as crashed with exit 1."
    requirement: PLAN-03
    verification:
      - kind: unit
        ref: "tests/test_session.py#test_each_config_step_kind_dispatches (8 collected cases, set equality asserted per case)"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_an_unknown_step_kind_fails_closed_instead_of_running_argv"
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_skill_install_without_an_executable_operation_crashes_the_row"
        status: pass
    human_judgment: false
  - id: D8
    description: "The generic reapply_post_install workflow is not used for RECONFIGURE, and every command a step runs goes through ctx.runner (D-06, attribution precondition from review 8d0a71d)."
    requirement: PLAN-03
    verification:
      - kind: automated_ui
        ref: 'grep -c "reapply_post_install" installer/session.py -> 0'
        status: pass
      - kind: unit
        ref: "tests/test_session.py#test_reconfigure_runs_argv_steps_in_order_and_is_done"
        status: pass
    human_judgment: false

# Metrics
duration: 60min
completed: 2026-10-17
status: complete
---

# Phase 20 Plan 08: Reconfigure Execution Summary

**A RECONFIGURE row now runs the steps the review listed: one dispatcher over all eight `ConfigStepKind`s, argv steps executed in a re-validated cwd through the portable directory shim, the pnpm group through the existing node executor, the terminal synchronizer, and the per-harness skill handoff — stopping at the first failure.**

## Performance

- **Duration:** ~60 minutes wall clock (18:43 → 19:45 local; two task commits plus metadata)
- **Started:** 2026-10-17T18:43:31-03:00 (picked up from 20-07's summary commit `11e98f1`)
- **Completed:** 2026-10-17T19:45:00-03:00 (final gates re-run on the committed tree)
- **Tasks:** 2
- **Files modified:** 2

## Accomplishment
- Replaced 20-07's interim `not_attempted` RECONFIGURE branch with `_run_step` / `_run_reconfigure`: a single dispatcher keyed by `ConfigStep.kind` that runs or hands off all eight kinds.
- Added `in_directory`, the portable per-step cwd wrapper (`sh -c 'cd -- "$1" && shift && exec "$@"' sh <cwd> <argv…>`), so argv stays a list of positional parameters, no process-global `chdir` is taken, and it works on macOS where `env -C` does not exist.
- Added `_valid_cwd`: execution-time re-validation of a repo path discovered minutes earlier, with `lstat` + `stat.S_ISDIR` so a directory swapped for a symlink is refused (T-20-14, V12).
- Steps stop at the first failure with `{step text}: {reason}` as the detail, preserving 19 D-18's enable-before-remove order so a failed enable cannot be followed by the removal that deletes the only working copy (T-20-15); the failure does not propagate `dependency_failed` to dependents.
- Wired `pnpm_group_install` to `executors.execute` on the declaring tool's first node method — the whole pinned group, `--allow-build`, real pnpm and the smoke check, on the same path install and update use (19 L-19-28).
- Wired `terminal_sync` to `ctx.terminal_sync()`, keeping its warning as the row detail, and an argv-less `skill_install` to `perform_action(tool, "install", ctx.runner)`, so a harness the installer cannot write to gets reviewed handoff lines on `RowOutcome.install` and the row reads `manual` (19 L-19-07).
- Added the kind-set guard `_STEP_KINDS = frozenset(get_args(ConfigStepKind))`, refused in `_run_step` and asserted in a test, so a future ninth kind fails instead of running an unreviewed command.
- 16 new test functions, 28 collected tests (8 + 4 + 3 + 2 + 2 + 1 per the parametrizations); `tests/test_session.py` now collects 112, and 22 of them are this plan's Task 2 selection. Full suite: 4836 passed / 4 skipped at 96.02% total coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): RECONFIGURE argv steps in order, cwd wrapped and re-validated** — `eed34e7` (feat)
2. **Task 2: the three argv-less kinds — pnpm group, terminal sync, skill handoff → manual** — `e1bd8ba` (feat)

**Plan metadata:** this commit (`docs(20-08): complete plan summary`)

## Files Created/Modified
- `installer/session.py` — `in_directory`, `_valid_cwd`, `_first_line`, `_STEP_KINDS`, `_StepResult`, `_run_step`, `_run_reconfigure`, and the RECONFIGURE branch of `execute_plan`
- `tests/test_session.py` — one test per `ConfigStepKind`, cwd wrapping and refusal, stop-at-first-failure, manual handoff, executor refusals, and the fail-closed `ValueError` pin

## Decisions Made
- **REUSE finding 08-1 applied as written.** `_valid_cwd` is `is_absolute()` plus `stat.S_ISDIR(path.lstat().st_mode)` inside `try/except OSError` — no separate `S_ISLNK` clause, because `lstat` on a symlink reports `S_IFLNK` and the `S_ISDIR` test already refuses it. The parametrized case name keeps `symlink → cwd is not a directory`, so the trust-boundary check is pinned by test rather than by a redundant second branch.
- **Refusal texts name the field** (`cwd is not absolute`, `cwd does not exist`, `cwd is not a directory`). The plan fixed the `{step.text}: {refusal}` shape but not the wording; the prefix tells a user reviewing the detail which of several steps' fields was refused.
- **`_StepResult` carries `warning` in addition to `failed` and `handoff`.** The plan's context block requires `terminal_sync`'s warning to become the row detail *and* the step to count as run, which a `(failed, handoff)`-only record cannot express.
- **The node executor's refusals are caught per step** (`CommandError`, `OSError`, `executors.ExecutorError`, `VersionError`). "pnpm is not on PATH" and "node 20.0.0 does not meet the required minimum 22.12.0" are expected answers with a sentence to act on, and the engine already treats them as per-method failures; `ValueError` from `perform_action` deliberately stays outside that list, so a broken producer invariant fails closed as `crashed` rather than reading as a refusal.

## Deviations from Plan

### Authoritative interface followed over the plan's paraphrase

**1. [Rule 2 - Architecture] `perform_action` is called positionally**
- **Found during:** Task 2 (skill handoff)
- **Issue:** The plan's key-link pattern reads `perform_action(tool, 'install', runner)` and its Task 2 action writes `perform_action(tool, "install", ctx.runner)`. The authoritative definition (`installer/skill_lifecycle.py:656`) takes `tool, action, runner` positionally with `home`/`which` keyword-only — and the plan's own context block cites that exact call site (`skill_lifecycle.py:678`) for the `ValueError`.
- **Fix:** Called positionally, matching the interface. `grep -c 'perform_action(tool, "install"' installer/session.py` → 1, so the acceptance check still holds.
- **Files modified:** `installer/session.py`
- **Verification:** `uv run pyright` (strict) clean; `make validate` exit 0; the three handoff tests pass.
- **Impact:** None — the plan's paraphrase was abbreviated, not wrong in intent.

### Added coverage beyond the plan's enumerated behaviors

**2. [Rule 1 - Missing Critical] Two guards the plan's own tests demanded**
- **Found during:** Task 2 (writing `test_each_config_step_kind_dispatches`)
- **Issue:** The plan asked for a guard ("the test fails if a new kind is added without a branch") and for `pnpm_group_install` to run a real external executor. A literal fall-through would have given an undeclared kind a command, and an un-caught `ExecutorError` would have turned every machine without pnpm into a `crashed` row — the one shape the TUI and the wizard agree is a bug rather than a refusal — which also halts the whole plan.
- **Fix:** Added `_STEP_KINDS` with its refusal branch and the per-step executor-refusal catch, each pinned by its own test (`test_an_unknown_step_kind_fails_closed_instead_of_running_argv`, `test_pnpm_group_install_reports_the_executors_own_refusal`).
- **Files modified:** `installer/session.py`, `tests/test_session.py`
- **Verification:** `uv run pytest tests/test_session.py --no-cov` → 112 passed; `make test` → 4836 passed / 4 skipped, 96.02%.
- **Impact:** Scope unchanged (same two files, same two tasks); three collected cases added beyond the plan's list.

**3. [Rule 3 - Supporting] Task 2's kind parametrization collects as 8 tests**
- **Found during:** Task 2 verification
- **Issue:** The plan describes `test_each_config_step_kind_dispatches` as "parametrized over all 8 `ConfigStepKind` literals via `typing.get_args`", and the Task 2 verify gate fails when `-k "step_kind"` passes fewer than 8 tests. One looping test collects as 1 and satisfies neither statement.
- **Fix:** `@pytest.mark.parametrize("kind", sorted(_ALL_KIND_STEPS))` with the set-equality guard asserted inside each case, so the parametrization runs over every model member and the gate sees 9 passing cases.
- **Files modified:** `tests/test_session.py`
- **Verification:** `uv run pytest tests/test_session.py --no-cov -k "step_kind"` → 9 passed (≥8).

Total deviations: 3 (1 authoritative-interface alignment, 2 additional coverage/verification adjustments). No requested behavior was dropped, deferred, or replaced, and no file outside the plan's `files_modified` list was touched.

## RED outputs

### Task 1 (tracer) — 9 tests written first, then

`uv run pytest tests/test_session.py --no-cov -k reconfigure` against 20-07's tree (`11e98f1`: RECONFIGURE → `not_attempted`, detail `reconfigure not wired`). 9 failed, 103 deselected; the same file at that base with these tests added is 29 failed / 83 passed against 112 collected.

```
>       assert events == ["gsd", list(_ENABLE), list(_UNINSTALL)]
E       AssertionError: assert ['gsd'] == ['gsd', ['cla...sd-core@gsd']]
E         Right contains 2 more items, first extra item: ['claude', 'plugin', 'enable', '-s', 'user', 'gsd-core']

tests/test_session.py:493: AssertionError
____ test_reconfigure_wraps_a_step_with_cwd_in_the_portable_directory_shim _____

>       assert recorder.argv == [
            ["sh", "-c", 'cd -- "$1" && shift && exec "$@"', "sh", str(repo), *_GSD_INSTALL]
        ]
E       assert [] == [['sh', '-c',... 'pnpm', ...]]
E         Right contains one more item: ['sh', '-c', 'cd -- "$1" && shift && exec "$@"', 'sh', '.../repo', 'pnpm', ...]

tests/test_session.py:510: AssertionError
_ test_reconfigure_refuses_a_cwd_that_is_relative_missing_or_a_symlink[relative-cwd is not absolute] _

>       assert outcomes[0].result == "failed"
E       AssertionError: assert 'not_attempted' == 'failed'
E         - failed
E         + not_attempted

tests/test_session.py:544: AssertionError
______________ test_reconfigure_failure_does_not_block_a_dependent ______________

>       assert [outcome.result for outcome in outcomes] == ["failed", "done"]
E       AssertionError: assert ['not_attempted', 'done'] == ['failed', 'done']

tests/test_session.py:584: AssertionError
=== 9 failed, 103 deselected in 0.13s ===
```

The informative one is the dependent case: the interim branch returns `not_attempted`, so `test_reconfigure_failure_does_not_block_a_dependent` fails as `['not_attempted', 'done'] == ['failed', 'done']` — a plan whose reconfigure did nothing could not yet be shown to leave its dependents alone.

### Task 2 — 13 test functions written first, then

`uv run pytest tests/test_session.py --no-cov -k "step_kind or pnpm_group or terminal_sync_step or skill_install or builtin_step"` against Task 1's tree (`eed34e7`): 10 failed, 11 passed, 91 deselected. The file as a whole at that base is 10 failed / 102 passed.

```
__________ test_each_config_step_kind_dispatches[marketplace_remove] ___________

    monkeypatch.setattr(session_module.executors, "execute", _execute_nothing)
    declared = frozenset(get_args(ConfigStepKind))
>   assert declared == getattr(session_module, "_STEP" + "_KINDS")
E   AttributeError: module 'installer.session' has no attribute '_STEP_KINDS'

tests/test_session.py:1446: AttributeError
__________ test_pnpm_group_install_reports_the_executors_own_refusal ___________

>       assert outcome.result == "failed"
E       AssertionError: assert 'crashed' == 'failed'
E         - failed
E         + crashed

tests/test_session.py:1526: AssertionError
__________ test_an_unknown_step_kind_fails_closed_instead_of_running_argv ______

>       assert outcome.result == "failed"
E       AssertionError: assert 'done' == 'failed'
E         - failed
E         + done

tests/test_session.py:1716: AssertionError
=== 10 failed, 11 passed, 91 deselected in 0.14s ===
```

Against 20-07's tree the same selection fails 21 tests (91 deselected), because Task 1's `reconfigure` cases are in it too. The three excerpts above are the Task 2-specific shapes: the guard's `AttributeError` (the `_STEP_KINDS` name did not exist yet — that is the guard failing closed before it was written, not a defect in the final code), `crashed` where a `failed` refusal belongs, and a fall-through that ran an undeclared kind's argv and reported `done`.

## Verification (evidence, not assertions)

Run on the committed tree `e1bd8ba` (`git status` showed only this summary file and the pre-existing `.planning/config.json`):

| Gate | Result |
|------|--------|
| `make validate` (ruff check, ruff format --check, pyright strict, bandit, vulture, shellcheck) | exit 0, 0 errors |
| `make test` (`pytest -n auto` + coverage) | **4836 passed, 4 skipped**, total coverage 96.02% (floor 90%) |
| `uv run pytest tests/test_session.py --no-cov` | 112 passed |
| `uv run pytest tests/test_session.py --no-cov -k "step_kind"` (Task 2 gate, ≥8) | 9 passed |
| `uv run pytest tests/test_session.py --no-cov -k reconfigure` (Task 1 gate, ≥8) | 9 passed |
| Suppression-count check (the plan's verify command, verbatim) | exit 0 — no new `noqa` / `type: ignore` / `pyright: ignore` / `nosec` |
| Artifact greps on `installer/session.py` | `^def in_directory` 1, shim string 1, `^def _run_reconfigure` 1, `executors.execute(` 1, `perform_action(tool, "install"` 1, `"no terminal synchronizer bound"` 1, `"no node method declares the group"` 1, `InstallStatus.MANUAL_REQUIRED` 5, `reapply_post_install` 0, `reconfigure not wired` 0 |
| `git status` before both commits | only `.planning/config.json` (pre-existing, orchestrator-owned, never staged) plus this plan's two files |
| Host safety | no `make setup` / `fix` / `uninstall`, no mutating `systemctl --user`, no real shell rc or agent settings touched; zero sudo; tests run offline against a recording runner and a scratch `HOME`; the two throwaway RED worktrees under `/tmp` were removed |

`installer/session.py` is at 98% (7 lines missed, 5 partial). Two of them are this plan's `except (CommandError, OSError)` arm (lines 609-610): the `CommandError` path the plan asked to pin is covered by `test_reconfigure_stops_at_the_first_failing_step`, while the `OSError` path — a missing `sh`, which the sandbox cannot reproduce without a second monkeypatch of the same branch — is untested. Recorded here rather than left silent; the remaining misses (733, 735, 902, 963, 984) are pre-existing UPDATE/SKIP/BLOCKED planner paths outside this plan.

## Threat register disposition

- **T-20-14 (Tampering, high) — mitigated.** `_valid_cwd` re-checks the step's `cwd` at execution time with `lstat` (never `stat`) plus `stat.S_ISDIR`, so a directory swapped for a symlink, removed, or made unreadable refuses the step: `test_reconfigure_refuses_a_cwd_that_is_relative_missing_or_a_symlink[relative|missing|symlink]` asserts `recorder.argv == []` alongside the detail, i.e. the step never ran.
- **T-20-15 (Denial of Service, high) — mitigated.** The row stops at the first failure, so a failed `plugin_enable` can never be followed by the duplicate-removal step that would delete the only working copy: `test_reconfigure_stops_at_the_first_failing_step` (argv steps) and `test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next` (a row whose first failure is a built-in step and whose later step would run argv).
- **T-20-16 (Tampering, medium) — mitigated.** `in_directory` passes argv as positional parameters to `sh -c 'cd -- "$1" && shift && exec "$@"'`; nothing is concatenated or re-parsed, and `test_reconfigure_wraps_a_step_with_cwd_in_the_portable_directory_shim` pins the exact recorded argv.
- **T-20-SC (Tampering, high) — accepted, unchanged.** `pyproject.toml` and `uv.lock` are untouched (no new dependency); `pnpm_group_install` runs the existing executor over registry-pinned packages, which is exactly why it dispatches `executors.execute` instead of re-typing an argv.

## Root-cause chain (5 Whys)
1. Why did 20-07 leave RECONFIGURE as `not_attempted`? It shipped the engine, and the dispatcher needed the kinds' real backends to exist first.
2. Why did the kinds need re-examining rather than a single argv loop? Three of the eight carry no argv at all (`pnpm_group_install`, `terminal_sync`, an argv-less `skill_install`), so an argv-only loop would silently skip them.
3. Why dispatch `pnpm_group_install` through the executor instead of building the argv here? Because a locally typed argv would drift from `--allow-build`, the real-pnpm and smoke-version floors that 19 L-19-28 put behind `executors.execute` — and the plan named that as a no.
4. Why re-validate the cwd at execution time? The path was discovered minutes earlier in `build_plan`; between planning and running it can be a symlink, be deleted, or be made unreadable (T-20-14), and `cd` into it is the one place a stale answer becomes a command.
5. Why fail closed on an unknown kind? Because `_STEP_KINDS` is the only thing that ties the dispatcher to the model's `Literal`; a fall-through would give a future kind a command nobody reviewed. The guard is asserted equal to `get_args(ConfigStepKind)` so the link cannot rot quietly.

## Issues Encountered
- The transient `AttributeError: module 'installer.session' has no attribute '_STEP_KINDS'` in Task 2's RED output is the guard failing closed before it existed, which is what the parametrization collects against; the same test asserts the set equality once the module defines the name.
- The plan's `test_reconfigure_handoff_and_builtin_steps_run_in_order_and_stop_at_the_first_failure` names a behavior (stop-at-first-failure when the row starts with a built-in step) that no other case covers; it is committed as `test_reconfigure_stops_at_a_builtin_step_and_never_reaches_the_next` and referenced under that name in D3/D5.
- A project-local review subagent could not be dispatched (the configured reviewer model returned an upstream access error), so the plan's cross-AI review step was carried out as a self-review against the plan text, the full `11e98f1..e1bd8ba` diff and every verify command. No Critical or Important findings remained; the three deviations above are the substance of that review.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- 20-09 (composition root) can drive the wizard from `execute_plan` outputs: RECONFIGURE rows now return `done` / `failed` / `manual` truthfully, and a `manual` row carries `RowOutcome.install.handoff` for `render_handoff`.
- 20-10 (execute screen) can rely on the attribution precondition: `ctx.on_row_started(row)` still fires before a row's first step, and every command a step runs goes through `ctx.runner`.
- Hook re-registration is deliberately not a step kind here (Phase 23 owns it), and `reapply_post_install` is not wired into RECONFIGURE (D-06).
- No deferred review findings, failing tests, or host-touching verification remain.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-17*
