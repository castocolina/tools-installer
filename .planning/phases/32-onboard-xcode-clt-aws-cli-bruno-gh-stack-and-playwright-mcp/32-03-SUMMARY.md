# Phase 32 Plan 03 Summary

- **Task 1 — AWS CLI:** committed as `6f12b91d`. The prior executor’s RED and GREEN output was not available in this run.
- **Task 2 — Bruno:** committed as `022df33e`. Added the macOS cask, architecture-specific pinned Linux AppImages, and the requested entry and resolution tests.
  - RED: the targeted command exited 1 with 12 failures, including the four Bruno tests and the registry and resolution pins, because the entry did not yet exist.
  - GREEN: the targeted command exited 0; its output ended at `100%`.
  - The first commit attempt failed lint, formatting and type checking; the test code was corrected, those gates were rerun successfully, and the commit hook passed all six gates.

## Final gates

- `make validate`: exit 0; lint, format-check, typecheck, security, dead-code and shellcheck all passed.
- `make test`: exit 0; **8796 passed, 6 skipped**, coverage **96.29%** against the 90% requirement.

## Decisions

- **32 D-03, D-04 and orchestrator decision 4 — provisional, needs confirmation:** AWS uses the `prefer` sort key to put the script before brew, pins `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=false`, and uses brew `awscli` as the fallback.
- **Review H3 — provisional, needs confirmation:** Dropped D-03’s tool-level `requires = ["unzip"]` because it blocks the brew fallback. The vendor script checks for unzip and fails closed; the registry comment records the reason.
- **32 D-06 and D-07:** Bruno uses the macOS cask into `~/Applications` and pinned per-architecture raw tarballs on Linux. The existing tarball `raw` and `desktop` keys required no model change.
- **32 D-08, locked; orchestrator decision 5 — provisional, needs confirmation:** No desktop entry is written. The registry records the existing `desktop` key and follow-up 999.32. `smoke_argv` remains at its default pending plan 32-07’s container result; an UNPROVEN result is not a pass, and plan 32-09 applies the result.
- **Orchestrator decision 9 — provisional, needs confirmation:** Registry pins were edited in the entry’s commit; the plan was bounded to the split task supplied.

## Pin edits

- `tests/test_registry.py`: tool count 92 → 93, user tier 54 → 55, human audience 31 → 32, and Bruno added to the reviewed human-tool set.
- `tests/test_resolve.py`: added Bruno’s cask and tarball first-method values for the four platform fixtures.

## Deviations and limits

- No named Task 2 test scenario was omitted.
- Targeted pytest used the default `TMPDIR` per the orchestrator’s override. Each explicitly created run directory was removed by its exit trap.
- No container, GUI, vendor binary or network registry verification was run. Bruno’s FUSE, sandbox and smoke behavior remains unconfirmed.
- Orchestrator to run: `make verify-registry` (read-only, network) and record its result under ## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `6f12b91d` (Task 1, AWS CLI) and `022df33e` (Task 2, Bruno), both through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: both exit 0; every long plan-named test exists.
- `make test` on the final tree, default TMPDIR: 8796 passed, 6 skipped, coverage 96.29%.
- `make verify-registry` (read-only): exit 1 only for the pre-existing draw.io drift (32.7.4 vs pinned 32.6.10, left for phase 33's package gate); both Bruno AppImage URLs listed under Passed; `aws-cli` is listed as not checkable (a script entry with no pin).
- Container checks: `aws-cli` and `bruno` run after plans 32-06 and 32-07.

Provisional decisions carried to the verification report (needs owner confirmation): 32 D-03 deviation (tool-level `requires = ["unzip"]` dropped so the brew fallback is reachable; the vendor script fails closed without unzip); D-04 and orchestrator decision 4 (script before brew by a per-method sort key, `AWS_CLI_INSTALL_SKIP_SIGNATURE_VERIFICATION=false`); D-08 locked and orchestrator decision 5 (Bruno has no desktop entry, follow-up backlog 999.32; `smoke_argv` stays default until plan 32-07's container result, applied by plan 32-09).

orchestrator-verification: none required (the `aws-cli` and `bruno` container lines are appended to the 32-06 and 32-07 summaries)

.

## Orchestrator verification

orchestrator-verification: none required
