---
phase: 26-commit-and-push-quality-hooks
plan: "05"
subsystem: devtools
tags: [git-hooks, pre-commit, makefile, ci, docs]
requires: ["26-01", "26-02"]
provides:
  - "make dev-setup: uv sync, then the commit hook and the push-gate shim in the shared hooks dir"
  - "devtools/hooks.py: MARKER, PRE_COMMIT_HEADER, SHIM, Runner, run_command, install, main"
affects: ["26-06", "26-09"]
tech-stack:
  added: []
  patterns: ["injected runner plus fake git common dir under tmp_path", "every check before any write"]
key-files:
  created: [devtools/hooks.py, tests/test_hooks_install.py]
  modified: [Makefile, tests/test_makefile.py, .github/workflows/ci.yml, tests/test_ci_workflow.py, README.md, AGENTS.md, .claude/dev-environment.md]
decisions:
  - "The default runner is the public `run_command` (not `_run`) so a test can exercise its LC_ALL=C env without a pyright private-usage suppression"
  - "A `core.hooksPath` query exit other than 1 is treated as set (fail closed); the message shows stdout, or stderr when stdout is empty"
status: complete
commits: 3
plan_head_before: 76a89cb1aed2fce325ee7d28cff77061f58342e3
plan_head_after: 9e832efc9eea2765588c127aa6b2438268d52fa0
actuals:
  tokens: 21000
  tasks: 3
  commits: 3
---

# Phase 26 Plan 05: make dev-setup and the hook step Summary

`make dev-setup` replaces `make install` and installs pre-commit's commit hook plus the push-gate shim into the shared hooks dir, refusing every unsafe hook layout before it writes anything.

## Tasks

| Task | Commit | What |
| ---- | ------ | ---- |
| 1 | e934eace | `devtools/hooks.py` (flow plus shim), `dev-setup` target replacing `install`, ci.yml step, Makefile/CI tests |
| 2 | 8402f753 | skip outside a checkout, surfaced rev-parse failure, `core.hooksPath`, lstat/hard-link/foreign-hook/legacy preflight, rerun, worktree warning, shim tests (real `sh` with a fake `uv`) |
| 3 | 9e832efc | README, AGENTS.md, `.claude/dev-environment.md` renames and the "Agents never run `make dev-setup`" rule |

## RED evidence

- Task 1: `tests/test_hooks_install.py` failed at collection with `ImportError: cannot import name 'hooks' from 'devtools'`; the Makefile and CI tests failed (`test_dev_setup_installs_deps_then_the_hooks`, `test_old_bootstrap_target_is_gone`, `test_gate_targets_keep_dev_dependencies` with `KeyError`, `test_ci_installs_with_dev_setup`: `'make dev-setup' not in [..., 'make install', ...]`).
- Task 2: against the Task 1 module the new file failed at collection (`cannot import name 'PRE_COMMIT_HEADER'`); once the constant existed, the run hung on `test_a_fifo_pre_push_is_refused` (the Task 1 code wrote into a FIFO) and the outside-a-checkout case wrote a stray `hooks/pre-push` under the cwd. Both prove the old order was unsafe.

## Verification

- `tests/test_hooks_install.py`: 28 tests; `devtools/hooks.py` coverage 97% (uncovered: the `--git-dir` failure branch and `__main__`).
- `make validate` and `make test` exit 0 on every commit tree (7714 passed, 6 skipped, 96.20% total coverage).
- Acceptance greps: no `make install` outside `.planning`/`docs/superpowers`; `Agents never run \`make dev-setup\`` and `final owner-assigned checkpoint` once each in AGENTS.md; `make dev-setup` twice in README.md.
- The tests never ran real git or pre-commit, and no `make dev-setup` / `pre-commit install` ran on this checkout (P5).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hard-link test asserted "no pre-push" for the pre-push case**
- **Found during:** Task 2 GREEN
- **Issue:** `assert_refused` demanded `pre-push` be absent, but in the `pre-push` parametrization that file is the hard link under test.
- **Fix:** that case checks the message, pre-commit not run and both names byte-identical with `st_nlink == 2`; the `pre-commit` case also asserts no shim.
- **Files modified:** tests/test_hooks_install.py
- **Commit:** 8402f753

**2. [Rule 3 - Blocking] E501 on shim echo line and long messages**
- **Fix:** the no-uv text lives in `_NO_UV` and is interpolated into `SHIM` (the emitted shim text is unchanged); long messages are split.
- **Commit:** e934eace, 8402f753

**3. [Rule 1 - Bug] Stray `hooks/` directory from a RED run**
- **Issue:** the Task 1 module wrote `./hooks/pre-push` when rev-parse failed during a Task 2 RED run. I deleted it before staging (untracked, never committed).

## Known Stubs

None.

## Threat Flags

None. All new surface (`.git/hooks` writes, `core.hooksPath`, shim) is in the plan's threat model (T-26-11..15, 31, 32, 40, 41).

## Self-Check: PASSED

- devtools/hooks.py, tests/test_hooks_install.py: found
- Commits e934eace, 8402f753, 9e832efc: ancestors of HEAD
