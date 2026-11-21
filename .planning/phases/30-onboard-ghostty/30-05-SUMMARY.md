# Phase 30 Plan 05 Summary

- **Task 1 — Ghostty lifecycle driver:** `df1e9740`. RED: `ImportError` for the missing driver module. GREEN: host tests reached `[100%]`.
- **Task 2 — Ghostty container target:** `e2a2dbbf`. RED: host tests failed because `cmd_ghostty`, `ghostty_run_args`, and registration were absent. GREEN: the specified four-file pytest command reached `[100%]`.
- **Follow-up — preserve the shell PATH audit’s line classifications:** `8ed80fa3`. The first full suite exposed stale line-number classifications after the script additions. The targeted shell-audit and container tests then reached `[100%]`.

## Final gates

- `make validate`: exit 0; lint, format, typecheck, security, dead-code and shellcheck all **Passed**.
- `make test`: exit 0; **8252 passed, 6 skipped**, coverage **96.31%**.

The first commit attempt exposed formatting and type-annotation errors in the new tests; those were corrected and their gates passed before the commit. The first full test run failed the shell PATH audit as described above; the final-tree rerun passed.

All run directories created for these commands were removed by their exit traps. The additional Task 1 cases were not added: the supplied Task 2 read-first and verification lists did not identify individual missing Task 1 cases.

## Decisions and review findings

- **30 D-18 / orchestrator decision 6:** the target uses the shared `fedora:latest` landing image, a PID-named container, and exact-name teardown. Config-loading Ghostty commands run only after installer configuration; a FUSE fallback is unproven, not a pass.
- **H6:** the residue baseline follows a zsh-only sync. **H7/H3:** FUSE proof requires an observed mount, including the printed mount point in `/proc/self/mountinfo`; the mount process is terminated.
- **H4:** the device is passed only when present; without it the FUSE pass is unproven and the extract pass still runs. The install itself is inside the lifecycle cleanup boundary.
- **M5:** lifecycle cleanup runs in `finally`. **M3:** the receipt-path test binds `Path.home()` to scratch. **M4:** version and both configuration readbacks require exit 0.
- **H5:** removal uses before, installed and after listings and verifies seeded user content. **X1:** command scratch directories use exit-safe cleanup.
- **W3:** the orchestrator may record either a proven-FUSE PASS or the explicitly qualified extract-and-run PASS after the prescribed checks; neither a product failure nor an unproven extract pass is accepted.

## Provisional decisions (need confirmation)

30 D-17: the residue diff excludes scripts/e2e-residue-allowlist.txt and asserts no /tmp/tools-installer-* leftovers (narrowed to the installer's own temp paths); ~/.config/ghostty is not exempted; needs confirmation

30 D-03, 30 D-08, 30 D-10, and the SPEC R4 amendment following 28 D-06 remain flagged for owner confirmation; for D-08, a user `command` in any default file writes no shell region.

## Narrowings of locked decisions

30 D-17 narrowed: the /tmp assertion covers only installer-owned names (tools-installer-*), because the AppImage runtime leaves its own appimage_extracted files there by design

30 D-18 narrowed: the second pass without FUSE is APPIMAGE_EXTRACT_AND_RUN=1 in the same box, not a second container, and the base image is fedora:latest (Fedora 44 today) rather than a pinned fedora:44

## Orchestrator handoff

Run `scripts/container-e2e-verify.sh ghostty`. Expected, in order:

```text
TRACER_GHOSTTY_INSTALL_OK mode=fuse method=tarball version=Ghostty 1.4.0
TRACER_GHOSTTY_FUSE_OK
TRACER_GHOSTTY_SYNC_OK mode=fuse
TRACER_GHOSTTY_REGIONS_OK mode=fuse
TRACER_GHOSTTY_REMOVE_OK mode=fuse
TRACER_GHOSTTY_INSTALL_OK mode=extract method=tarball version=Ghostty 1.4.0
TRACER_GHOSTTY_SYNC_OK mode=extract
TRACER_GHOSTTY_REGIONS_OK mode=extract
TRACER_GHOSTTY_REMOVE_OK mode=extract
TRACER_LANDING_TEARDOWN_OK
```

The real container, Ghostty AppImage and Python 3.15 CI run were not executed here; the container result remains an orchestrator verification requirement.

## Orchestrator verification

ghostty-container: PASS (2026-11-20; fuse: UNPROVEN, extract-and-run proven)

- Run by the orchestrator: `scripts/container-e2e-verify.sh ghostty`, second run started 21:43:13, exit 1 by design (`TRACER_GHOSTTY_FUSE_UNPROVEN` fails the step). Output lines: `TRACER_GHOSTTY_INSTALL_OK mode=fuse method=tarball version=Ghostty 1.4.0`, `TRACER_GHOSTTY_FUSE_UNPROVEN detail=no FUSE mount of the AppImage was observed`, `TRACER_GHOSTTY_SYNC_OK mode=fuse`, `_REGIONS_OK mode=fuse`, `_REMOVE_OK mode=fuse`, then the same four `_OK` lines for `mode=extract` (install, sync, regions, remove), then `TRACER_LANDING_TEARDOWN_OK`. The container `tools-installer-e2e-ghostty-<pid>` was removed by exact name, no prune or reset ran, and the `fedora:latest` image pulled by the runs was removed by exact name.
- The FUSE mount was not observed because rootless podman denies it: a throwaway probe (two disposable containers, removed) showed `fusermount3: mount failed: Operation not permitted` for a non-root user, after which the AppImage runtime falls back to a user-namespace mount and `--version` still prints `Ghostty 1.4.0` in 0.13 s. So the FUSE pass stays UNPROVEN on this host (a Bazzite host check is the UAT line); the extract-and-run pass proves install, shell and keys regions, real Ghostty reading both, and a residue-free uninstall.
- First real run (21:20, exit 1): two defects of the executor's driver, fixed by the orchestrator in `1bdaff0c`: the installer's own tuning record (`terminal-tuning-ghostty`) was counted as stray residue (it is expected after the install and removed by the uninstall), and the driver read the AppImage's output through a pipe that the FUSE fallback's mount helper keeps open, so `--version` waited its full 120 s timeout. The driver now captures through files; both fixes have host tests.
- Re-runs on the final tree after the review-fix round: run 3 (22:48 to 23:34) showed the new directory check finding three empty directories left after the FUSE pass (`~/.local/share/applications/`, `icons/` and `tools-installer/`); the orchestrator allowed exactly those three standard empty directories (a file left inside one is still reported on its own) in `63455e08`. Run 4 (23:35 to about 23:46, on `63455e08`, exit 1 by design because of the FUSE `_UNPROVEN` line): `INSTALL_OK`, `FUSE_UNPROVEN` (no mount observed), `SYNC_OK`, `REGIONS_OK` and `REMOVE_OK` for `mode=fuse`, then the same four `_OK` lines for `mode=extract`, then `TRACER_LANDING_TEARDOWN_OK`; the container was removed by exact name. The PASS line above is the result of run 4 and unchanged in shape.
- `make verify-registry` (23:36, read-only): the only drift is the pre-existing draw.io pin (newer stable v32.7.4 against 32.6.10); both Ghostty pins (`Ghostty-1.4.0-x86_64.AppImage` and `-aarch64.AppImage`) are listed under `## Passed`.
- Executor and orchestrator history of this plan: four executor attempts on the whole plan stopped within a minute (a bloated prompt from a builder bug plus the plan size); it ran as part A (Task 1, `df1e9740`) and part B (Task 2 and gates, `e2a2dbbf`, `8ed80fa3`). The orchestrator reverted the compression of the target usage text and moved the classified PATH lines instead (`397068ed`). `make test` of the executor: exit 0, 8252 passed.
- Plan verifies 1 and 2 re-run by the orchestrator (`run_plan_verifies.py 30-05`): both exit 0.
- Open: some individually named Task 1 host-test cases of the plan are covered by differently named or merged tests; the verdict functions and the lifecycle boundary are tested.
