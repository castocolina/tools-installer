# Phase 34 Plan 05 Summary

## Tasks

- **Task 1 — dispatch and service wiring:** `b0d65ed2` routes `check-updates` through the shared schedule lock and wires the refresh service.
- **Task 2 — runner job:** `3e67765f` adds the `check-updates` runner job and its single-result-line logging contract.
- **Task 3 — isolated Git runner:** `0106e2b0` adds bounded, noninteractive Git queries and wires them into the check.

## Verification

- **Tasks 1 and 2 RED/GREEN output:** Not available in this split session; their commits were already present.
- **Task 3 RED:** The targeted suite failed on the missing `git_for_check` and unsupported `run_git_isolated(timeout=...)`, as expected.
- **Task 3 GREEN:** The specified targeted pytest command exited 0, including `tests/test_reachability.py`.
- **Commit hook:** The first attempt failed `make format-check` on two new test blocks. After formatting, that target and all six commit-hook gates passed.
- **Final `make validate` tail:** lint, format-check, typecheck, security, dead-code and shellcheck **Passed**.
- **Final `make test` tail:** `9328 passed, 6 skipped`; total coverage **96.44%**, above the 90% requirement.

Both targeted-run scratch directories were removed by their exit traps. The final gates used the default TMPDIR.

## Decisions

- **34 D-03, locked:** The `check-updates` runner job reuses `_update` and has check-specific timeout wording.
- **34 D-04, locked:** Dispatch is by kind; cleanup jobs retain their refusal and the check shares the update lock branches.
- **34 D-21, locked:** The runner logs `start` and the child’s last result line.
- **34 D-11, locked:** Runner-path lookups are anonymous; tokens do not reach the child or log.
- **34 D-19, own reasoning, needs confirmation:** The production Git runner is isolated, bounded to 20 seconds, stays in the caller’s process group, and disables prompting, credential helpers, askpass and lazy fetch.
- **Orchestrator decision 2, needs confirmation:** New `RunDeps` fields default after `notify`; existing positional construction remains valid.
- **Orchestrator decision 12, needs confirmation:** Tests use fakes; the reachability guard is green. **34 D-23, locked:** scratch HOME and fakes only.
- **Round 2 H4, needs confirmation:** The check’s inner `uv run` uses `--frozen`; plan 34-09 covers the named allowed writes.
- **Round 3 H5, needs confirmation:** The child also receives `PYTHONDONTWRITEBYTECODE=1`. The narrowed write boundary excludes checkout writes, permits only named installer-state files, and accepts uv cache and manager-query scratch; plan 34-06 records the amendment.
- **Round 3 M4:** The closed-stdin claim applies to the runner route.

## Deviations and limits

- Updated Task 1’s `deps.git is None` assertion because Task 3 deliberately wires that field; the plan’s general expectation that no existing assertion would change was incompatible with its required wiring.
- No Task 3 named test was omitted. Earlier tasks’ RED/GREEN output could not be recovered from their commits.
- No live timer, notification, container or real-Git immutability check was run. An ignored `.coverage` file was present after the suite; it was not removed because its prior existence was not established.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commits `b0d65ed2` (Task 1: the dispatch of the update check in `run_schedule`, `RunDeps.refresh`, the CLI choice and the `setup` wiring; its first commit imports `update_check` from a production entry point), `3e67765f` (Task 2: the runner's `check-updates` job, `PYTHONDONTWRITEBYTECODE=1` for the check child, `uv run --frozen`, closed stdin) and `0106e2b0` (Task 3: the isolated production git runner: credential helpers and askpass disabled, no prompts), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py` (with an owned scratch `TMPDIR`): all exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 9328 passed, 6 skipped, coverage 96.44%. The strict reachability guard is GREEN again: the named red-guard exception of plan 34-04 is cleared by this plan's first commit. The runner, update-check, schedule and run tests also pass on Python 3.15.
- One assertion edit beyond the plan: Task 1's own `deps.git is None` assertion changed because Task 3 deliberately wires that field.
- No timer, notification, container or real-git run: the claims about checkout writes (none: frozen lockfile, no bytecode) and installer-state writes (only the named files) are file-level; real-launch evidence is the orchestrator's container observation after plan 34-07.

Provisional decisions carried to the verification report (needs owner confirmation): D-04, D-11, D-21 (dispatch by kind, anonymous lookups by construction on the runner path only, one result line); orchestrator decision 12 and the narrowed write-boundary claim (uv's own cache and manager-query scratch writes are outside installer state: an accepted exception, to be recorded in the SPEC amendment of plan 34-06); the closed-stdin claim qualified to the runner route.

orchestrator-verification: none required

orchestrator-verification: none required
