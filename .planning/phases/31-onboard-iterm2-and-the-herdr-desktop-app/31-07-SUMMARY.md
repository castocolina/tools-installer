# Phase 31 Plan 07 Summary

- **Task 1 — `188da5f6`:** Added the dedicated `herdr-app` container target, host tests and transcript evidence gate. RED: 13 expected failures. GREEN: Task 1 host tests passed, as reported by the orchestrator.
- **Task 2 — `16b6bcac`:** Added the registry-copy filter for generic bootstrap, resync and nested runs; landing targets and the production registry retain `herdr-app`. RED: eight expected missing-filter failures. GREEN: the specified targeted command and the expanded targeted suite reached `100%` with exit 0.

The first Task 2 commit attempt exposed formatting, import-order and ShellCheck failures. These were fixed; the successful commit hook passed all six static gates.

## Final gates

- `make validate`: exit 0; lint, format, typecheck, security, dead-code and shellcheck all **Passed**.
- `make test`: exit 0; **8616 passed, 6 skipped**, coverage **96.26%** against the 90% requirement.

## Decisions and deviations

- The generic all-pass and nested target filter the streamed registry copy rather than adding a production option or widening the shared residue allowlist. Chunked generic runs inherit the filtered copy.
- The dedicated Fedora target installs `libxcb` and `libxkbcommon` inside its disposable container only.
- Updated the four line-number classifications in `tests/test_shell_scripts_path.py` to follow the inserted shell code.
- No named Task 2 tests were omitted. System awk was invoked through the existing bash harness because the test sandbox rejects direct host-awk launches.
- Run directories were removed by their exit traps. The pre-existing untracked goal file was left untouched.

## Provisional decisions (need confirmation)

31 D-17 and orchestrator decision 6: the herdr-app container target on the shared Fedora landing image with libxcb and libxkbcommon installed in the box; needs confirmation

orchestrator decision 7: herdr-app is excluded from the generic make e2e all-pass by a registry-copy filter because the dedicated target proves it; needs confirmation

31 D-08: iTerm2 word-navigation key-map rows rather than global Option-as-Esc+; needs confirmation.

31 D-12: the macOS herdr-app cask choice and its install-location trade-off; needs confirmation.

The 2026-11-21 CONTEXT amendments to D-07, D-09, D-11 and D-16; need confirmation.

iTerm2 uninstall ordering and refusal behavior; need confirmation.

The parent key-map merge rule for readable and Dynamic Profile parents; needs confirmation.

The keys.json edge cases and pinned-default seeding behavior; need confirmation.

The accepted limits recorded as `shortcut:` comments; need confirmation.

## Next step for the orchestrator

Run `scripts/container-e2e-verify.sh herdr-app` from the repository root. The executor did not run the container target.

Expected exit 0 and verdicts, with a semantic version in each install line:

```text
TRACER_HERDR_APP_INSTALL_OK order=app-first method=script version=herdr-app <semver>
TRACER_HERDR_APP_KEYS_OK order=app-first
TRACER_HERDR_APP_REVERSE_OK order=app-first point=install
TRACER_HERDR_APP_ISOLATION_OK order=app-first point=removal
TRACER_HERDR_APP_REVERSE_OK order=app-first point=removal
TRACER_HERDR_APP_INSTALL_OK order=herdr-first method=script version=herdr-app <semver>
TRACER_HERDR_APP_KEYS_OK order=herdr-first
TRACER_HERDR_APP_ISOLATION_OK order=herdr-first point=install
TRACER_HERDR_APP_ISOLATION_OK order=herdr-first point=removal
TRACER_HERDR_APP_REMOVE_OK order=herdr-first
TRACER_HERDR_APP_REVERSE_OK order=herdr-first point=removal
TRACER_LANDING_TEARDOWN_OK
```

The transcript must end with the teardown line and contain no `_FAILED`, `_UNPROVEN` or `TRACER_LANDING_INFEASIBLE` line. A version mismatch or environment failure is not a pass; retry as specified by the plan. The real vendor footprint, network and package-name assumptions remain unverified until that run.

## Orchestrator verification

herdr-app-container: PASS (2026-11-21; transcript 34591570ed07)

- Run by the orchestrator: `scripts/container-e2e-verify.sh herdr-app`, started 04:57:36, exit 0 on the first attempt, on commit `16b6bcac`. Output lines: `TRACER_HERDR_APP_INSTALL_OK order=app-first method=script version=herdr-app 0.1.16`, `KEYS_OK order=app-first`, `REVERSE_OK order=app-first point=install`, `ISOLATION_OK order=app-first point=removal`, `REVERSE_OK order=app-first point=removal`, then for `order=herdr-first`: `INSTALL_OK ... version=herdr-app 0.1.16`, `KEYS_OK`, `ISOLATION_OK point=install`, `ISOLATION_OK point=removal`, `REMOVE_OK`, `REVERSE_OK point=removal`, and the transcript ends with `TRACER_LANDING_TEARDOWN_OK`. No `_FAILED`, `_UNPROVEN` or infeasible line. The container `tools-installer-e2e-herdr-app-<pid>` was removed by exact name (`podman ps -a` shows none) and no prune or reset ran.
- The transcript digest (first 12 hex of the sha256 of `.e2e-artifacts/container-herdr-app/herdr-app-transcript.log`) was computed with the driver's own `transcript_digest`; the evidence gate of plan 31-08 recomputes it. The `server_not_running` JSON lines in the output come from the installer's reload step in a container with no herdr server; they are not verdicts.
- Executor and orchestrator history of this plan: part a implemented Task 1 but could not commit (the new usage text shifted four classified PATH lines in `tests/test_shell_scripts_path.py` and the executor would not edit an existing test); the orchestrator moved those four numbers (a data edit), fixed one pyright annotation in the new test and committed Task 1 (`188da5f6`); Task 2 (`16b6bcac`) then ran as a second dispatch. Plan verifies re-run by the orchestrator (`run_plan_verifies.py 31-07`): all exit 0. `make test` re-run by the orchestrator on the committed tree: exit 0, 8616 passed, 6 skipped, coverage 96.26%.
