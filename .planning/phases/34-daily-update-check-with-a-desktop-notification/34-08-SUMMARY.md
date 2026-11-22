# Phase 34 Plan 08 Summary

**Task 1 commit:** `306e83ad` — `test(34-08): pin the cross-file consistency of the daily update check`

Added cross-file tests for schedule argv parsing on Linux and macOS, schedule choices and daily intervals, the phase 35 interface, notifier invocation, environment closure, and module hygiene. Extended the existing privilege-escalation scan to cover the two update-check modules.

## Verification

- **RED:** None applicable. These contract tests and the scan extension were written against finished implementation and passed on their first run; no failing result is claimed.
- **Targeted GREEN:** The plan’s pytest command exited 0, including `tests/test_reachability.py`. A broader targeted run covering the shared doubles’ consumers also exited 0.
- **Commit hook:** All six static gates passed.
- **`make validate` tail:** lint, format-check, typecheck, security, dead-code and shellcheck all `Passed`.
- **`make test` tail:** `9382 passed, 6 skipped in 78.40s`; coverage `96.44%`, above the required `90.0%`.
- Both final gates used the default `TMPDIR`. The targeted-run scratch directories were removed by their exit traps.

## Decisions

- **Locked:** Phase 35 inherits the names `Notifier`, `notifier_for`, `outdated_ids`, `Schedule.daily` and the `stale_after` keyword; this plan pins them.
- **Provisional; needs confirmation — orchestrator decision 12:** Tests are hermetic; no real Git, GitHub CLI, notifier binary or container was launched.
- **Owner rule 4:** The strict reachability guard passed.
- **Review round 1 M9:** The notifier seam is pinned through a typed fake, runner environment by equality, and postponed return annotations by resolved type hints.
- **Review round 2 M9:** Only `run_check` calls the typed fake.
- **Review round 3 L1:** The fake uses two matching tools, inert typed dependencies and a freshly cleared call list.

### Other provisional phase decisions — need confirmation

1. Eight-row schedules table height and the listed existing-test exceptions.
2. New `RunDeps` fields have defaults to preserve positional construction.
3. The runner passes the session bus address; unit environment validation remains closed.
4. macOS `osascript` argv omits `--`; real delivery and permission remain owner UAT.
5. The installer self-check skips detached HEAD and non-`main` branches.
6. A shrinking non-empty outdated set notifies again.
7. Brew-owned updates may be under-reported without `brew update`.
8. Resolver failure reporting stays in `_latest_status`, without wrapping `resolve_tag`.
9. The schedules container extension is orchestrator-run and cannot prove bus delivery.
10. The phase architecture subsection and dated ROADMAP wording amendment.
11. A login catch-up can precede the notification daemon and delay delivery.
12. Hermetic tests, cross-version compatibility and the reachability guard remain required.
13. The confirmed-only membership rule, narrowed write-boundary claim, SPEC and ROADMAP amendments, and daily limit as timer cadence remain **provisional; need confirmation**.

## Pin edits

- `tests/test_schedules_engine.py`: added `notify.py` and `update_check.py` to the existing escalation scan’s module list; its assertion is unchanged.

## Deviations and limits

- The plan’s fake-state recipe supplied strings to `outdated_state`; the existing helper requires `Tool` objects, so the test supplies its matching tools instead.
- No named test was omitted. The suite’s six existing skips are reported above.
- No live timer, desktop notification, container check or real Mac UAT was run.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commit `306e83ad` (the cross-file consistency tests: the real generated argv of every row on both OSes parsed by the runner, the runner environment equal to the unit keys plus the two runner-only keys, the bus variable excluded from the unit keys, the Phase 35 interfaces `Notifier`, `outdated_ids` and `Schedule.daily` pinned through typed fakes and resolved annotations, the escalation scan of the two new modules), through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's verify re-run (owned scratch `TMPDIR`): exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 9382 passed, 6 skipped, coverage 96.44%.
- One deviation: the plan's fake-state recipe supplied strings to `outdated_state`, which needs `Tool` objects, so the test supplies matching tools.
- No timer, notification or container was run in this plan.

Provisional decisions carried to the verification report (needs owner confirmation): the contract phase 35 inherits (`installer/notify.py`'s `Notifier` seam, `outdated_ids(states)`, `Schedule.daily`: names and signatures pinned); the runner/unit environment boundary (the bus address is runner-only, never serialized into a unit).

orchestrator-verification: none required

orchestrator-verification: none required
