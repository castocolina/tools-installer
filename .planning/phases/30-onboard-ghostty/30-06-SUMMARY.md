# Phase 30 Plan 06 Summary

The pre-edit gate passed:

`ghostty-container: PASS (2026-11-20; fuse: UNPROVEN, extract-and-run proven)`

The registry and skill row record the extract-and-run evidence without claiming a FUSE mount pass.

## Tasks

- **Task 1 — container evidence:** `9d2f0e8b`
  - RED: `test_ghostty_entry_records_the_container_proof` and `test_ghostty_row_records_what_is_proven` failed on the missing evidence.
  - GREEN: the targeted four-file pytest command exited 0 at `[100%]`.
- **Task 2 — catalog consistency guards:** `38960c7a`
  - RED mutations: a loader-valid `rg` GitHub-release note triggered the note-scope assertion; removing the macOS config directory triggered the resolver-directory assertion.
  - GREEN: the targeted three-file pytest command exited 0 at `[100%]`.

Review H5: evidence was counted by occurrence, with a separate assertion for each skill-table cell. The final counts were one registry occurrence and two skill occurrences.

Review M5: GNU `date -d` rejected both `2026-02-30` and `2026-99-99`; each negative gate check exited 1.

## Final gates

- `make validate`: exit 0; lint, format, typecheck, security, dead-code and shellcheck all **Passed**.
- `make test`: exit 0; **8260 passed, 6 skipped**, coverage **96.31%**.
- Local tests ran on Python 3.12.12; Python 3.15 remains a CI check.

## Provisional decisions — owner confirmation needed

- **30 D-03**, plan `30-01-SUMMARY`: macOS cask location and no promised CLI link — needs owner confirmation.
- **SPEC R4 amendment versus 28 D-06**, plan `30-03-SUMMARY`: a deleted recorded region remains deleted and quiet — needs owner confirmation.
- **30 D-08**, plan `30-04-SUMMARY`: a user `command` in any default file writes no shell region — needs owner confirmation.
- **30 D-10**, plan `30-04-SUMMARY`: included configuration is not followed; report partial — needs owner confirmation.
- **30 D-17**, plan `30-05-SUMMARY`: residue exclusions and installer-owned temporary paths — needs owner confirmation.

## Narrowings of locked decisions — owner confirmation needed

- **30 D-08**, plan `30-04-SUMMARY`: a user `command` in any default file prevents writing the shell region.
- **30 D-17**, plan `30-05-SUMMARY`: the `/tmp` assertion covers installer-owned `tools-installer-*` names.
- **30 D-18**, plan `30-05-SUMMARY`: extract-and-run uses the same Fedora container; the base is `fedora:latest`.

## Orchestrator verification

Checked 2026-11-20 22:20 by the orchestrator, independently of the executor's report (pi, router-env/my-coding, 22:04:47 to 22:09:47, exit 0; no BLOCKED claim).

- Commits since `8d0a6d33`: `9d2f0e8b`, `38960c7a`; each passed the commit hook. Plan verifies 1 to 3 re-run by the orchestrator (`run_plan_verifies.py 30-06`): all exit 0 (the PASS gate, then the two pytest commands). `make test` re-run by the orchestrator on the committed tree: exit 0, 8260 passed, 6 skipped, coverage 96.31%.
- The gate read `ghostty-container: PASS (2026-11-20; fuse: UNPROVEN, extract-and-run proven)` in `30-05-SUMMARY.md`; the registry comment and the skill row say "extract-and-run proven in a container; the FUSE mount is checked on a Bazzite host (UAT)" and never claim a FUSE pass.
- The container result of this phase lives in `30-05-SUMMARY.md` (PASS with FUSE unproven); there is no separate container line for this plan.

## Orchestrator checklist

- Task 2's verify lists `make validate` and `make test`: they run once each, in that order, after the plan's last commit (never before it); both exit 0.
- Orchestrator checklist after this plan (the phase's last), each in its own disposable environment, nothing on the host's real configs: (1) the read-only `make verify-registry` (network) to confirm both Ghostty pins against the live GitHub digests; (2) the real-Mac UAT lines, deferred to the owner's Mac by the standing rule and never marked passed by an agent: the cask installs Ghostty into `~/Applications` through `--appdir`, Cmd+K clears the screen and scrollback, Option+Left and Option+Right move by word (including on the Spanish layout), `~/Applications/Ghostty.app/Contents/MacOS/ghostty +show-config` and `+list-keybinds` show the `super+k` line and no `macos-option-as-alt`, and the written file is the one Ghostty resolves, and a new tab opens in the same directory; (3) the Bazzite-host lines: the AppImage mounts through the host's own FUSE (the container FUSE pass reads `_UNPROVEN` if rootless podman cannot mount), `xterm-ghostty` TERMINFO resolves in the window (`echo $TERM`, `infocmp xterm-ghostty`, arrows and Ctrl+L), and the measured time of the status probe `ghostty --version` without FUSE against its 5 s timeout; (4) record the five provisional decisions (30 D-03, the SPEC R4 (amended 2026-11-20) versus 28 D-06 reading, 30 D-08 with orchestrator decision 2, 30 D-10, 30 D-17) and the three narrowings of locked decisions (30 D-08, 30 D-17, 30 D-18) for the owner's confirmation in the phase verification.

## Deviations and cleanup

Mutation proofs invoked the actual guard functions against temporary registry copies rather than running pytest on the copies. All created run directories were removed by their exit traps. The pre-existing untracked goal file was left untouched.

Live container, network, real-Mac and Bazzite-host checks were not run here; FUSE remains unproven until owner UAT.
