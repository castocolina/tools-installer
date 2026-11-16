---
phase: 26-commit-and-push-quality-hooks
plan: "06"
subsystem: testing
tags: [git-hooks, pre-commit, e2e, bash, scratch-repos, signals, cleanup]

requires:
  - phase: 26-04
    provides: push-gate refusal logic, PRE_PUSH_ARGS and the signal-forwarding runner in devtools/push_gate.py
  - phase: 26-05
    provides: the devtools.hooks installer and its pre-push shim, foreign/symlink preflight
provides:
  - "scripts/hooks-e2e.sh: real-git, real-pre-commit, real-gate proof of HOOK-01..HOOK-04 in throwaway repos"
  - "make hooks-e2e target and shellcheck wiring"
  - "tests/test_makefile.py pins for the target, scratch-only markers, descendant-group cleanup and isolated background pushes"
affects: [26-07 (CI runs make hooks-e2e on ubuntu and macOS), 26-08]

actuals:
  tokens: 11267
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Every git/uv/pre-commit call goes through run_isolated (env -i allowlist) so no inherited GIT_* reaches the scratch repo"
    - "One self-contained mktemp -d repo per case; EXIT trap reaps every descendant process group before removing the scratch dir"

key-files:
  created: [scripts/hooks-e2e.sh]
  modified: [Makefile, tests/test_makefile.py]

key-decisions:
  - "One fresh scratch repo per case (new_repo + install_hooks): keeps pushed refs and unstaged edits independent, at the cost of a few extra uv/venv setups."
  - "run_isolated execs env -i with an explicit PATH/HOME/PRE_COMMIT_HOME/UV_* allowlist; the exec keeps a background push's pid equal to its process-group id so kill -- -pid reaches it."
  - "cleanup walks a single ps snapshot for descendants of each recorded push, collects their process groups, INTs the push group, KILLs surviving collected groups and removes $SCRATCH only after no member remains (FAIL cleanup: otherwise)."
  - "expect_edit copies the file after the unstaged edit and assert_restored pairs cmp -s with a git diff --quiet non-vacuity check, so a lost edit fails and a correct restore passes."
  - "A real ref update (ahead, a new remote ref or a root push) and a test.ran / push refused: proof precede every gate case, so no case can pass through the gate's empty-input exit."

patterns-established:
  - "Scratch-repo e2e harness: cheap stand-in Makefile gates record marks outside the work tree, real .pre-commit-config.yaml and devtools are copied in."

requirements-completed: [HOOK-01, HOOK-02, HOOK-03, HOOK-04]

coverage:
  - id: D1
    description: "make hooks-e2e runs uv run scripts/hooks-e2e.sh, is on .PHONY with a help comment, and the script is in the shellcheck file list"
    requirement: HOOK-01
    verification:
      - kind: unit
        ref: "tests/test_makefile.py#test_hooks_e2e_target_runs_the_script"
        status: pass
      - kind: unit
        ref: "tests/test_makefile.py#test_shellcheck_covers_the_hooks_e2e_script"
        status: pass
    human_judgment: false
  - id: D2
    description: "The e2e script is scratch-only: env -i allowlist, mktemp -d, no $ROOT/.git path"
    requirement: HOOK-04
    verification:
      - kind: unit
        ref: "tests/test_makefile.py#test_hooks_e2e_script_runs_only_in_scratch_dirs"
        status: pass
    human_judgment: false
  - id: D3
    description: "A real commit runs the six static gates and no test; a green push lands; a red push is aborted with the remote ref unmoved"
    requirement: HOOK-01
    verification:
      - kind: e2e
        ref: "make hooks-e2e#ok commit_runs_static_gates, ok green_push_lands, ok red_push_is_aborted"
        status: pass
    human_judgment: false
  - id: D4
    description: "All R3 refusals, unstaged-edit restore on every push shape, fail-fast, unmerged, config and ignored gate-read files behave as specified with real git"
    requirement: HOOK-03
    verification:
      - kind: e2e
        ref: "make hooks-e2e#ok staged_is_refused_sorted ... ok fail_fast_skips_test (16 cases)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The real hook step's install branches, interrupt restore for INT/TERM/HUP, and the harness's own abort cleanup are proven; nothing is left behind"
    requirement: HOOK-04
    verification:
      - kind: e2e
        ref: "make hooks-e2e#ok install_leaves_both_hooks_and_is_idempotent ... ok harness_abort_reaps_every_group (13 cases)"
        status: pass
    human_judgment: false
  - id: D6
    description: "EXIT trap reaps descendant process groups; background pushes run through run_isolated"
    requirement: HOOK-02
    verification:
      - kind: unit
        ref: "tests/test_makefile.py#test_hooks_e2e_cleanup_reaps_descendant_groups, test_hooks_e2e_background_push_is_isolated"
        status: pass
      - kind: e2e
        ref: "make hooks-e2e#ok harness_abort_reaps_every_group"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-11-16
status: complete
---

# Phase 26 Plan 06: Real-git hooks e2e harness Summary

**scripts/hooks-e2e.sh proves the commit hook, push gate and hook-step install branches with real git, pre-commit and uv in 32 scratch-repo cases, with full process-group cleanup**

## Performance

- **Duration:** 8 min
- **Started:** 2026-11-16T16:56:57Z
- **Completed:** 2026-11-16T17:04:41Z
- **Tasks:** 3
- **Files modified:** 3
- **make hooks-e2e wall time:** 9 s (measured; 32 cases)

## Accomplishments

- Added `scripts/hooks-e2e.sh` (mode 755): every git/uv/pre-commit call runs through an `env -i` allowlist; one fresh `mktemp -d` repo per case; an EXIT trap (plus INT/TERM/HUP traps) reaps all descendant process groups before removing the scratch dir.
- Task 1: the commit runs six static gates and no test, a green push lands, a red push is aborted with the remote ref unmoved.
- Task 2: all 16 R3/refusal/restore cases — staged (sorted, space in name intact), untracked `.py`, root `conftest.py`/`pytest.ini`, ignored gate-read conftest and GNUmakefile with non-vacuity, restore on existing/new/root pushes, failed-gate restore, HEAD refspec, non-HEAD refusal, deletion without checks, unstaged config, unmerged, fail-fast.
- Task 3: nine install branches (idempotence, outside-checkout skip, core.hooksPath, worktree common dir, legacy migration, foreign/symlink refusals), three interrupt-restore cases (INT/TERM/HUP), and `harness_abort_reaps_every_group`, which aborts a nested run with two live groups and proves both are gone.
- Wired `make hooks-e2e` into `.PHONY`, the help list and the shellcheck recipe; added six `tests/test_makefile.py` pins.

## Task Commits

1. **Task 1: commit gates / green push / red push** - `8fa709e5` (feat)
2. **Task 2: refusals, restore on every push shape, deletion, fail-fast** - `81462730` (feat)
3. **Task 3: install branches, interrupt restore, abort cleanup** - `0f561eb5` (feat)

**Plan metadata:** this commit (`docs(26-06): complete real-git hooks e2e plan`)

## Files Created/Modified

- `scripts/hooks-e2e.sh` - the real-git e2e harness (new, ~1097 lines, executable)
- `Makefile` - `hooks-e2e` target on `.PHONY` with help comment; script appended to shellcheck list
- `tests/test_makefile.py` - generalised e2e-script gate pin; six new hooks-e2e pins

## Decisions Made

- Fresh repo per case over shared-state reset (see key-decisions); `ahead` + real ref update + `test.ran`/`push refused:` proof on every gate case.
- `expect_edit`/`assert_restored` compare against the post-edit copy, not HEAD.
- The scratch `lint` target touches its mark before failing on `LINT_FAIL`, so fail-fast proves lint ran and test did not.
- The background push launch is `run_isolated "$PY" -c 'os.setpgid(0,0); os.execvp(...)' git push ...`, so the wrapper, git and the gate inherit only the allowlist.

## Deviations from Plan

Four post-review fixes applied to `scripts/hooks-e2e.sh`:

- Prune a reaped pid from `BG_PIDS` in `interrupt_restores_edit` so `cleanup` cannot signal or SIGKILL a recycled pid's process group.
- Add `GIT_CEILING_DIRECTORIES="$SCRATCH"` to the `run_isolated` allowlist and assert no git dir is reachable above scratch in `install_outside_a_checkout_skips`; a deliberate deviation from the plan's exact allowlist for P5 (never touch a real repo).
- Assert the six push-stage gate marks in `green_push_lands`, matching `commit_runs_static_gates`.
- Make `trap '' INT TERM HUP` the first line of `cleanup` so a second Ctrl-C cannot abort it midway.

### Mutation check (required by Task 2, reverted before commit)

- Temporarily changed `assert_restored` to compare the file against `git show HEAD:tests/test_a.py` instead of the post-edit copy.
- `make hooks-e2e` then printed `FAIL unstaged_edit_restored_existing_branch` (plus the other three restore cases), exit 1 — the check is not vacuous.
- Reverted the mutation; the final run prints all 32 `ok` lines.

**Total deviations:** 4 post-review fixes (1 deliberate allowlist addition for P5).
**Impact on plan:** None beyond the `GIT_CEILING_DIRECTORIES` allowlist addition.

## Issues Encountered

- The first Task 2 run failed `fail_fast_skips_test` because the scratch `lint` target failed on `LINT_FAIL` before writing `lint.ran`; reordered the target to touch its mark first, then fail.
- A `tests/test_makefile.py` text pin reads "git " in the outside-checkout skip assertion; reworded the assertion into two `git`-free substrings to keep the pin meaningful.
- `set -e` treated the nested abort harness's expected exit 3 as fatal; the exit status is now captured with an explicit `if`/`else`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 26-07: CI can run `make hooks-e2e` on ubuntu and macOS; the script is portable (bash 3.2-compatible constructs, `ps -A -o pid= -o ppid= -o pgid=`, no `setsid`/`mapfile`/`sha256sum`).
- 26-08 can cite the measured 9 s e2e wall time.

---
*Phase: 26-commit-and-push-quality-hooks*
*Completed: 2026-11-16*
