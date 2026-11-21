# Phase 32 Plan 07 Summary

- **Task 1 — Bruno driver and verdicts:** `f222b7e0`. Added lifecycle evidence, engine-smoke UNPROVEN handling, architecture-bound records, and smoke-mode selection. The earlier executor’s RED/GREEN output was not available in this split run; the driver tests passed in this run’s targeted and full suites.
- **Task 2 — Bruno container target:** `3d9cc4cb`. Added the orchestrator-only verb, library setup, conditional FUSE device, usage text, generic skip, and host tests.

## Verification

- Task 2 RED: the targeted suite failed on the missing Bruno functions, usage, skip list and pin.
- Task 2 GREEN: the targeted suite reached `100%` and exited 0.
- Commit hook: all six static gates passed. An initial hook failure for formatting and an unused import was fixed; the failing gates then passed.
- `make validate`: lint, format, typecheck, security, dead-code and shellcheck all **Passed**.
- `make test`: **8994 passed, 6 skipped**; coverage **96.33%**, exceeding the 90% requirement.
- Targeted-run scratch directories were removed by their exit traps.

## Decisions

All decisions below are **provisional and need owner confirmation**:

- Decision 5 / D-08: no Bruno desktop entry. The container must establish smoke arguments, FUSE-library needs and `--no-sandbox` behavior; UNPROVEN is never a pass.
- Decisions 6, 9 and 10: Bruno is excluded from generic e2e; the dedicated target follows the rootless-container, file-output and residue-baseline practices. Its recorded result is reported by plan 32-09, not a hard gate.
- H10 / H7: plan 32-09 applies a recorded smoke argument only for a reproducible, argument-only mode that differs from the default; extract modes requiring an environment variable are not applied.
- H8 / H9: an engine-smoke install failure is UNPROVEN, claims no mode and still checks removal; successful install evidence records the box architecture.
- The Fedora box installs `fuse-libs` and the specified Electron runtime libraries.

## Pin edits

- Updated the exact generic skip-list pin to include `bruno`.
- Moved the four classified PATH line numbers; their reasons are unchanged.
- The AWS skip test remained a membership test and required no edit.

## Deviations and limits

- No named Task 2 test was omitted. The real container, Bruno, FUSE and network checks were not run by this executor; their behavior remains unproven until the orchestrator runs the target.
- Orchestrator to run: `scripts/container-e2e-verify.sh bruno`

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `f222b7e0` (Task 1, driver and pure verdicts) and `3d9cc4cb` (Task 2, container target), both through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 8994 passed, 6 skipped, coverage 96.33%.
- Real container check, run by the orchestrator: `scripts/container-e2e-verify.sh bruno` (10:07 to 10:13). Result: `TRACER_BRUNO_INSTALL_UNPROVEN detail=engine-smoke-failed` (the engine's smoke of the staged AppImage ended exit 127 with a FUSE error: rootless podman cannot mount FUSE, the same limit as Ghostty in phase 30), `TRACER_BRUNO_RUN_UNPROVEN detail=no mode ran` (no staged binary survives a failed install, so no argument list or environment was exercised), `TRACER_BRUNO_REMOVE_OK` (the seeded Bruno collection and preferences survive the removal), `TRACER_LANDING_TEARDOWN_OK`. The script exits 1 for UNPROVEN, as designed. Transcript: `.e2e-artifacts/container-bruno/bruno-transcript.log` (git-ignored). UNPROVEN is reported, never a pass; plan 32-09 therefore keeps the default `smoke_argv` and states the limit in the entry's `# Verified` comment (the real-Mac and Bazzite desktop UAT line covers the AppImage launch).
- No `tools-installer-e2e-*` container is left; no broad prune or reset was run.

Provisional decisions carried to the verification report (needs owner confirmation): orchestrator decision 5 and D-08 (Bruno has no desktop entry; the AppImage's FUSE, `--no-sandbox` and display-less smoke needs stay unconfirmed: the Bruno container result is UNPROVEN because the container has no FUSE); the smoke-application rule (only an argument-only mode, only for the tested architecture, only from a digest-bound PASS); `bruno` joins the generic skip list.

bruno-container: UNPROVEN (2026-11-21; transcript 430723b2c2b1; engine-smoke-failed: no FUSE in rootless podman)
