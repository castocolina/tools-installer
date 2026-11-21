# Phase 32 Plan 09 Summary

## Recorded evidence

Both digest-bound evidence gates returned `GATE_OK` before Task 2 edits.

- aws-container: PASS (2026-11-21; transcript 9515b665dff5)
- playwright-container: PASS (2026-11-21; transcript ee31bd6542f3)
- bruno-container: UNPROVEN (2026-11-21; transcript 430723b2c2b1; engine-smoke-failed: no FUSE in rootless podman)

```text
BRUNO_MODE=none
BRUNO_ARCH=none
BRUNO_SMOKE_ARGV=none
```

Bruno retains the default smoke arguments; its registry comment does not claim a verified container pass.

## Tasks and verification

- **Task 1 — `b594493a`:** Recorded AWS and Playwright container evidence and the unverified Bruno result in the registry, with consistency tests. The prior executor’s RED and GREEN output tails were not available in the commit; they are not reconstructed here.
- **Task 2 — `2db4edd5`:** Documented the script keys and consent route, and added the skill-row pin and seven catalog consistency guards.
  - RED: `test_the_script_row_names_the_validated_keys` failed because `install` was absent from the script row.
  - Mutation checks: the Playwright pin, Bruno command name and Xcode URL mutations each produced a nonzero test result and were restored. The Xcode mutation was rejected by the registry loader, including in both entry-shape tests.
  - GREEN: the specified targeted pytest command exited 0.
  - The first commit attempt failed the lint and format hooks; the reported line-length and formatting issues were fixed, both failed gates passed on rerun, and the commit hook then passed all six gates.

Final-tree gates, with default `TMPDIR`:

```text
make validate:
make lint................................................................Passed
make format-check........................................................Passed
make typecheck...........................................................Passed
make security............................................................Passed
make dead-code...........................................................Passed
make shellcheck..........................................................Passed

make test:
Required test coverage of 90.0% reached. Total coverage: 96.33%
9025 passed, 6 skipped in 73.73s
```

Each executor-created scratch run directory was removed by its exit trap. No containers, live installs or registry network verification were run in this part.

## SPEC acceptance evidence

| Criterion | Evidence | Deferred |
|---|---|---|
| Xcode CLT | Plan 32-02 unit tests | Real Mac UAT |
| AWS CLI | Plan 32-03 unit tests; plan 32-06 container record | macOS script and brew fallback UAT |
| Bruno | Plan 32-03 pins; plan 32-07 container report, **UNPROVEN** | Read-only registry verification by orchestrator; Mac and Bazzite UAT |
| gh-stack | Plan 32-02 unit tests | macOS data-directory UAT |
| Playwright MCP | Plans 32-04 and 32-05 unit tests; plan 32-08 container record | Removal preview in plan 32-10; confirmed `hook_register` consent step and `rereads` drift rule in plan 32-11; real host loads |

**Concurrency backstop:** Interleaved scratch-HOME or container runs rely on the existing run lock and `write_if_unchanged`; no phase 32 plan adds a separate lock or write path.

## Deviations and limits

- Task 1’s RED/GREEN tails and negative-gate mutation outputs were not available to this executor; the earlier task was not repeated.
- The named Task 2 tests were written. The Bruno verdict-name guard uses the plan’s closed verdict-name list.
- The commit hook caught test formatting issues on its first attempt; no hook was bypassed.
- The existing untracked planning goal file was left untouched. The real-Mac, Bazzite and agent-host checks below remain unverified.

## Phase provisional decisions (need confirmation)

- **32 D-01:** Unconditional Xcode CLT hand-off, refining the writable-prefix test; Update refused and no removal offered.
- **32 D-04 with orchestrator decision 4:** AWS script before brew by a per-method sort key, with the gpg environment pin.
- **32 D-07:** Bruno uses pinned per-architecture raw tarballs; this supports the available Linux artifacts without inventing a different package method.
- **32 D-08:** Bruno writes no desktop entry; the AppImage menu entry remains follow-up backlog 999.32.
- **32 D-09:** Script `install` is validated fixed argv, checked by both elevation checks, with closed stdin and no shell; this supports extensions without a free-form command.
- **32 D-10 and D-11:** gh-stack is detected by its manifest and removed by its proven folder, amending ONB-14.
- **32 D-12 and D-13 with orchestrator decision 7:** Playwright remains pinned at 0.0.85 without a checkpoint; 0.0.86 is recorded as the alternative.
- **32 D-14:** The settings-ledger revert is the Playwright hook’s undo because a bun receipt cannot invoke a postinstall-hook undo.
- **32 D-15 as implemented:** One listed `hook_register` step, built by plan 32-11, has Claude as a consent host covering `~/.claude.json` and the `settings.json` environment key.
- **Orchestrator decisions 1–10 as implemented:** Host-specific ledger registration and Pi hand-off; confirmed Claude consent route; Xcode hand-off; AWS ordering; Bruno without a desktop entry; generic skip list; Playwright pin; `install` in both elevation checks; phase lessons; and dedicated container targets.
- **Container evidence gate:** AWS and Playwright require digest-bound PASS records; environmental UNPROVEN or infeasible results do not pass. Bruno is reported, not gated.
- **Bruno smoke application:** Only a digest-verified, reproducible argument-only mode is applied, and only to the tested architecture. Extract modes retain the default because the shipped smoke cannot supply `APPIMAGE_EXTRACT_AND_RUN=1`; unverified records produce no proof wording.
- **Other accepted limits:** The OpenCode v1/v2 shapes, Bazzite discriminator and `shortcut:` limits remain provisional and need owner confirmation.
- **Review M8:** Task 1’s prescribed order was tests, RED, registry evidence and Bruno data, GREEN, then commit.

## UAT lines deferred (no agent marks them passed)

- Xcode CLT on a real Mac: missing command, present state, Update refusal and empty Uninstall.
- AWS `install.sh` on macOS under `~/.local/share/aws-cli` without admin rights, or the brew fallback.
- Bruno cask on Mac: `~/Applications/Bruno.app`; uninstall retains `~/Documents/bruno`.
- Bruno AppImage on Bazzite: FUSE mount and menu-entry follow-up, backlog 999.32.
- gh-stack’s macOS data directory.
- macOS agent hosts’ MCP files.
- Playwright with real Flatpak Chrome on Bazzite.
- Each agent host’s own load of the `playwright` server.
- Claude plugin key spelling `enabledPlugins["playwright@claude-plugins-official"]` (assumption A7).
- Pi’s manual `pi mcp add` step.

## Orchestrator verification

Verified by the orchestrator on 2026-11-21:

- Commits `b594493a` (Task 1: both digest-bound evidence gates returned `GATE_OK` before any edit; registry comments record the AWS and Playwright container evidence; Bruno reported UNPROVEN with the default `smoke_argv` kept) and `2db4edd5` (Task 2: skill row, architecture rules, catalog guards), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists.
- `make test` on the final tree, default TMPDIR: the first run showed 1 failed, 9024 passed (the failing test was not captured); two further runs on the identical tree passed (9025 passed, 6 skipped, coverage 96.33%), so it was a flake of the host-state kind already seen in earlier phases, not a regression.
- The recorded evidence lines (AWS PASS, Playwright PASS, Bruno UNPROVEN) are copied from the 32-06, 32-08 and 32-07 summaries, where the orchestrator recorded them after real container runs.

The phase provisional decisions and the deferred UAT lines below are carried into the phase verification report as they stand.

orchestrator-verification: none required

orchestrator-verification: none required
