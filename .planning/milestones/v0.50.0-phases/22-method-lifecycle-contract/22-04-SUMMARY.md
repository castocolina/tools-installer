---
phase: 22-method-lifecycle-contract
plan: "04"
subsystem: install
tags: [zero-sudo, writable-prefix, preflight, homebrew, manual-handoff, time-of-check]
requires:
  - phase: 22-01
    provides: "script method key writable_prefix (absolute path, validated at load)"
  - phase: 22-02
    provides: "executors.needs_manual, ManualHandoff, Disposition.MANUAL, the engine's per-method re-check"
provides:
  - "executors.prefix_writable(prefix) -> bool: one lstat/access per prefix, nearest existing parent must be user-owned and writable, fails closed"
  - "executors.needs_manual(method, *, writable): a script with writable_prefix the user cannot write becomes a MANUAL handoff with the vendor command and runs nothing"
  - "ToolState.unwritable: the declared prefixes the refresh pass found unwritable"
  - "Plan-time MANUAL reads pass evidence only; run-time re-check calls prefix_writable live"
  - "The three Homebrew bootstrap stanzas declare writable_prefix (macOS arm64, macOS amd64, Linux)"
affects: [22-05, 22-08, 22-13]

actuals:
  tokens: 4638      # chars/4 over the realized diff (git diff 5f242f1..HEAD: 18551 bytes)
  tasks: 3
  commits: 3        # MEASURED: git rev-list --count 5f242f1..HEAD

tech-stack:
  added: []
  patterns:
    - "One predicate (needs_manual with a required writable keyword) answers at plan time and at run time"
    - "The refresh pass is the only place that stats for the plan; the plan reads published evidence (D-12)"

key-files:
  created: []
  modified:
    - installer/executors.py
    - installer/version_status.py
    - installer/session.py
    - installer/engine.py
    - installer/registry.toml
    - tests/state_doubles.py
    - tests/test_executors.py
    - tests/test_plan.py
    - tests/test_engine.py
    - tests/test_version_status.py
    - tests/test_registry.py

key-decisions:
  - "needs_manual takes writable as a required keyword (keyword-only), so no caller can forget the prefix check; native kinds ignore it"
  - "Writability: an existing prefix answers os.access(W_OK); a missing one answers its nearest existing parent, which must be owned by os.getuid() and writable (D-13)"
  - "prefix_writable fails closed: a foreign-owned writable parent and any OSError while probing both answer not writable (review R1-06)"
  - "The vendor command in the MANUAL row is the method's shell with the url, no env prefix, because the user runs it interactively (UI-SPEC A9); shell defaults to sh"
  - "The pass computes unwritable for every applicable script method with writable_prefix (one stat each); the plan reads it only for MISSING rows"
  - "The amd64 macOS prefix is /usr/local/Homebrew, the directory Homebrew's installer creates; /usr/local is root-owned, so the parent rule hands off exactly when the installer would escalate"
requirements-completed: [LIFE-07, LIFE-02]
# LIFE-07: the preflight is delivered here. LIFE-02: the brew-bootstrap half of the zero-sudo
# contract is delivered here; the native-package half landed in 22-02.

coverage:
  - id: D1
    description: "A script whose writable_prefix the user cannot write is planned MANUAL with the vendor command, and nothing runs"
    requirement: "LIFE-07"
    verification:
      - kind: unit
        ref: "tests/test_plan.py#test_an_unwritable_prefix_is_planned_manual_and_nothing_runs"
        status: pass
    human_judgment: false
  - id: D2
    description: "A writable prefix plans INSTALL and the vendor script runs through the install seam"
    requirement: "LIFE-07"
    verification:
      - kind: unit
        ref: "tests/test_plan.py#test_a_writable_prefix_plans_an_install"
        status: pass
    human_judgment: false
  - id: D3
    description: "prefix_writable follows the nearest existing parent and fails closed on a foreign owner or a probe error"
    requirement: "LIFE-07"
    verification:
      - kind: unit
        ref: "tests/test_executors.py#test_prefix_writable_follows_the_nearest_existing_parent"
        status: pass
      - kind: unit
        ref: "tests/test_executors.py#test_prefix_writable_fails_closed_on_a_foreign_owner_or_a_probe_error"
        status: pass
    human_judgment: false
  - id: D4
    description: "The refresh pass records unwritable prefixes once each; the engine re-checks a prefix that became unwritable and runs nothing"
    requirement: "LIFE-07"
    verification:
      - kind: unit
        ref: "tests/test_version_status.py#test_the_pass_records_an_unwritable_prefix"
        status: pass
      - kind: unit
        ref: "tests/test_version_status.py#test_the_pass_stats_each_prefix_once"
        status: pass
      - kind: unit
        ref: "tests/test_engine.py#test_the_engine_re_checks_a_prefix_that_became_unwritable"
        status: pass
    human_judgment: false
  - id: D5
    description: "The three Homebrew bootstrap stanzas declare their prefixes; no other tool does"
    requirement: "LIFE-02"
    verification:
      - kind: unit
        ref: "tests/test_registry.py#test_brew_bootstrap_stanzas_declare_their_prefix"
        status: pass
    human_judgment: false

duration: not recorded (start timestamp was not captured in this run)
completed: 2026-11-04
status: complete
commits: 3
plan_head_before: 5f242f17b9297450f597a700e90727dac185ccfa
plan_head_after: 8202dad8fca5d845b10dbef22901abc4e9df1c54
---

# Phase 22 Plan 04: Writable-prefix preflight for the Homebrew bootstrap Summary

**An unwritable Homebrew bootstrap prefix is a MANUAL review row with the vendor command and nothing runs; a writable one installs; the engine re-checks the same predicate live before the method runs.**

## Performance

- **Duration:** not recorded (start timestamp was not captured in this run)
- **Tasks:** 3 of 3 completed, one commit each
- **Files modified:** 11 (no new files)

## Accomplishments

- `executors.prefix_writable(prefix)`: one `lstat` walk to the nearest existing path, then `os.access(W_OK)` for an existing prefix, or owner `== os.getuid()` plus `os.access(W_OK)` for the nearest existing parent. Any `OSError` answers False. No subprocess, no `sudo -n`.
- `executors.needs_manual(method, *, writable)`: a `kind = "script"` method with `writable_prefix` returns `ManualHandoff("{prefix} is not writable by you; you run: `{command}`", command)` when `writable(prefix)` is False, where `command` is `{shell} -c "$(curl -fsSL {url})"`. A script without the key returns None. Native kinds keep their 22-02 answers.
- `ToolState.unwritable: tuple[str, ...] = ()`, passed through `tool_state(..., unwritable=...)`. The refresh pass computes it once per applicable script method (`_unwritable_prefixes`).
- `session._row` plans from `state.unwritable` (`writable=lambda prefix: prefix not in state.unwritable`) and never probes. `engine.install_tool` re-checks with `writable=executors.prefix_writable` before each method.
- The three Homebrew bootstrap stanzas in `installer/registry.toml` declare `writable_prefix`: `/opt/homebrew` (macOS arm64), `/usr/local/Homebrew` (macOS amd64), `/home/linuxbrew` (Linux). The brew `verified` date is refreshed to 2026-11-04.
- `tests/state_doubles.py`: `pass_state` and `plan_state` gain `unwritable=()` and forward it.

## Task Commits

1. **Task 1: preflight writable_prefix at plan time and run time** - `9e8ef45` (feat, tests and implementation together)
2. **Task 2: pin prefix evidence on the pass and the engine re-check** - `6c54f59` (test only; see Deviations 2)
3. **Task 3: declare the Homebrew bootstrap prefixes** - `8202dad` (feat, registry data with its test)

Every commit was made after `make validate` and `make test` exited 0 on that exact tree. The pre-commit hooks passed on each commit. No `--no-verify`. No attribution trailers (project rule). RED runs were not committed on their own.

## RED and GREEN evidence

### Task 1 RED

Command: `uv run pytest tests/test_plan.py tests/test_executors.py -k "unwritable_prefix or writable_prefix_plans or prefix_writable_follows or prefix_writable_fails_closed or without_a_prefix" -q --no-cov -n 0`

```
FAILED tests/test_plan.py::test_an_unwritable_prefix_is_planned_manual_and_nothing_runs
  TypeError: plan_state() got an unexpected keyword argument 'unwritable'
FAILED tests/test_executors.py::test_needs_manual_ignores_a_script_without_a_prefix
  TypeError: needs_manual() got an unexpected keyword argument 'writable'
FAILED tests/test_executors.py::test_prefix_writable_follows_the_nearest_existing_parent
  AttributeError: module 'installer.executors' has no attribute 'prefix_writable'
FAILED tests/test_executors.py::test_prefix_writable_fails_closed_on_a_foreign_owner_or_a_probe_error
  AttributeError: module 'installer.executors' has no attribute 'prefix_writable'
PASSED tests/test_plan.py::test_a_writable_prefix_plans_an_install   (regression guard, see Deviations 3)
4 failed, 1 passed, 176 deselected
```

The new tests reference `executors.prefix_writable` and `executors.needs_manual` through the module attribute, so the module imports and the RED is per test, not a collection error.

### Task 1 GREEN

- Targeted selection: `5 passed`, exit 0.
- `uv run pytest tests/test_plan.py tests/test_executors.py tests/test_session.py tests/test_engine.py tests/test_version_status.py -n auto -q --no-cov`: exit 0.
- `! grep -nE "sudo -n|subprocess"` over the `prefix_writable` body: no match, exit 1 from grep (the check passes).
- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `make test`: `5313 passed, 4 skipped`, coverage 96.23%, exit 0.

### Task 2 RED

Command: `uv run pytest tests/test_version_status.py tests/test_engine.py -k "unwritable_prefix or stats_each_prefix or became_unwritable" -n 0 --no-cov -rA`

```
PASSED tests/test_version_status.py::test_the_pass_records_an_unwritable_prefix[unwritable]
PASSED tests/test_version_status.py::test_the_pass_records_an_unwritable_prefix[writable]
PASSED tests/test_version_status.py::test_the_pass_records_an_unwritable_prefix[no-key]
PASSED tests/test_version_status.py::test_the_pass_stats_each_prefix_once
PASSED tests/test_engine.py::test_the_engine_re_checks_a_prefix_that_became_unwritable
5 passed, 311 deselected
```

All five passed at RED because the pass and the engine wiring shipped in Task 1 (the plan anticipated this: "close what the RED run shows without adding a second probe", and there was nothing to close). They are regression guards, not RED, as the project rule requires. Their value is shown by a mutation check (below).

Mutation checks, each reverted with `git checkout -- <file>` on the committed file (no uncommitted work in either file):

- `installer/version_status.py`: `unwritable=_unwritable_prefixes(tool, platform),` replaced with `unwritable=(),`. Result: `2 failed, 2 passed`. Failing: `test_the_pass_records_an_unwritable_prefix[unwritable]`, `test_the_pass_stats_each_prefix_once`.
- `installer/engine.py`: `writable=executors.prefix_writable` replaced with `writable=lambda _p: True`. Result: `1 failed` (`test_the_engine_re_checks_a_prefix_that_became_unwritable`).

### Task 2 GREEN

- `make validate`: exit 0.
- `make test`: `5318 passed, 4 skipped`, coverage 96.24%, exit 0.

### Task 3 RED

Command: `uv run pytest tests/test_registry.py -k brew_bootstrap_stanzas -n 0 --no-cov`

```
E       KeyError: 'writable_prefix'
FAILED tests/test_registry.py::test_brew_bootstrap_stanzas_declare_their_prefix
1 failed, 179 deselected
```

### Task 3 GREEN

- `grep -c '^writable_prefix = ' installer/registry.toml`: `3`.
- `uv run pytest tests/test_registry.py tests/test_model.py -n auto -q --no-cov`: exit 0.
- `make validate`: exit 0.
- `make test`: `5319 passed, 4 skipped`, coverage 96.24%, exit 0.

## Test counts (floors: measured at task start, plus delta)

| File | Task start | After plan | Delta |
|---|---|---|---|
| tests/test_executors.py | 85 | 88 | +3 (T1) |
| tests/test_plan.py | 91 | 93 | +2 (T1) |
| tests/test_engine.py | 79 | 80 | +1 (T2) |
| tests/test_version_status.py | 232 | 236 | +4 (T2: 3 parametrized cases + 1) |
| tests/test_registry.py | 179 | 180 | +1 (T3) |

Full suite: 5308 passed at wave-1 close (ledger figure; the plan start was not re-run at full suite) -> 5313 after Task 1 -> 5318 after Task 2 -> 5319 at plan end. The floor for `test_version_status.py` was start + 2 = 234; the measured end count is 236.

## Changed or Deleted Existing Tests

| Test | Change | Reason |
|---|---|---|
| `tests/test_executors.py::test_native_kind_is_a_manual_handoff_and_never_executed` | The call is now `needs_manual(method, writable=lambda _prefix: True)`; assertions unchanged | The plan makes `writable` a required keyword (D-12 signature) |
| `tests/test_executors.py::test_only_native_kinds_are_manual_handoffs` | The brew method is bound to a name and the call passes `writable=lambda _prefix: True`; assertion unchanged | Same keyword requirement |

Nothing was deleted. `tests/state_doubles.py` gained the planned `unwritable=()` keyword on `pass_state` and `plan_state`.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 - Bug, my test] Recursive getuid stub**
- **Found during:** Task 1 GREEN
- **Issue:** The foreign-owner test patched `os.getuid` with `lambda: os.getuid() + 1`, which called itself and raised RecursionError.
- **Fix:** The real uid is read into `other_uid` before the patch; the stub returns that constant. The product code was not changed.
- **Committed in:** `9e8ef45`

**2. [Plan wording] Task 2 commit is test-only**
- The plan's Task 2 named a `feat(22-04)` commit, but its tests pass on the Task 1 implementation and no code changed. Committed as `test(22-04)`, which the executor rules allow for a test-only task. The mutation checks show the tests fail when the wiring is removed.

**3. [Plan note] Two RED tests passed at RED**
- `test_a_writable_prefix_plans_an_install` (Task 1) passes before the change, because a script never consulted a prefix before this plan. It is a regression guard and is marked as one in the RED output.
- The five Task 2 tests passed on the Task 1 code (see Task 2 RED).

**4. [Workflow] Stray file moved out of the worktree**
- A collection listing was first written to `.collect-start.txt` inside the worktree. It was moved to the scratchpad before any commit and is not tracked.

**5. [Environment] Harness guard on a compound command**
- The first worktree-branch check, as one compound command, was refused by the harness because it could not verify that it stayed in the worktree. The same checks were run as separate simple commands from the worktree root, and all passed: branch `worktree-agent-a635bae11c549444f`, base `5f242f17b9297450f597a700e90727dac185ccfa`, toplevel the worktree path. Wave 1 recorded the same refusal.

**6. [Environment] codegraph index**
- `codegraph explore` reported that it read the main checkout's index (the worktree has no index). It was used only for orientation. Every edit was made with Read/Edit on the worktree files.

**7. [Per-plan guard files]**
- `gsd-spawn-toplevel` and `gsd-plan-head-before-22-04` were written into the worktree's git directory (`.git/worktrees/agent-a635bae11c549444f/`). They are not tracked.

### Scope notes (plan-directed, not deviations)

- The pass evaluates `writable_prefix` for every applicable script method of every tool in the pass, present or not, as the plan specifies. The plan reads it only for MISSING rows, so present tools see no change.
- The `prefix_writable` probe runs once per prefix per pass; `tool_state` itself stays free of filesystem calls.

## Issues Encountered

- None blocking. `make test` on the Task 1 tree ran once, with the session guard not tripping (`~/.bashrc` untouched by these runs).

## Known Stubs

None.

## Threat Flags

None. No new network endpoint, auth path or schema change. The shell command text in the MANUAL row is display-only and is never executed.

## Threat Model Coverage

| Threat | Disposition | Where it is handled |
|---|---|---|
| T-22-09 brew bootstrap run on an unwritable prefix | mitigate | `needs_manual` MANUAL at plan time from pass evidence; `test_an_unwritable_prefix_is_planned_manual_and_nothing_runs` |
| T-22-10 prefix changes after planning (time of check) | mitigate | Engine re-check with live `prefix_writable`; `test_the_engine_re_checks_a_prefix_that_became_unwritable` |
| T-22-34 foreign-owned writable parent or failing probe read as writable | mitigate | Owner comparison and `OSError` both answer False; `test_prefix_writable_fails_closed_on_a_foreign_owner_or_a_probe_error` |
| T-22-SC package installs | accept | This plan installs no package |

## Open Checks for Review

- An existing prefix is judged by `os.access(W_OK)` alone, as D-13 specifies. A prefix owned by another user but writable by this user (for example through a group bit) answers writable, and the vendor script runs. The owner rule covers only a missing prefix's nearest parent. Flag for review.
- The script branch of `needs_manual` calls `require_str(method, "url")`. A script with `writable_prefix` but no `url` raises ExecutorError at plan time. The registry always declares `url` for these stanzas; the loader does not enforce it. Same residual as 22-02.
- Not run on a real host: all prefix fixtures are under `tmp_path`; `/home/linuxbrew`, `/opt/homebrew` and `/usr/local` were not stat'ed by the tests.

## Self-Check: PASSED

Commits `9e8ef45`, `6c54f59` and `8202dad` are ancestors of HEAD. `installer/executors.py` defines `prefix_writable(prefix: str) -> bool` (1 match), and `installer/session.py` contains `state.unwritable` (1 match). The SUMMARY is the only untracked file.
