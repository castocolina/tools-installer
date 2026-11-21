---
phase: 31
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-21T04:00:00Z
plans_reviewed: [31-01-PLAN.md, 31-02-PLAN.md, 31-03-PLAN.md, 31-04-PLAN.md, 31-05-PLAN.md, 31-06-PLAN.md, 31-07-PLAN.md, 31-08-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 31

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 9cd94290)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 00:55 | opencode-referee-one | one-shot probe | OK |
| 00:55 to 00:58 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null` | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used. A read-only `gsd-plan-checker` pass ran beside it (1 blocker, 4 warnings, 3 info; folded in below).

## Orchestrator verification of the cycle 1 concerns

Cycle 1 of 3. Every HIGH below was checked against the cited plan lines (31-01:123, :132-134, :171-172, :186; 31-06:171-172 were read by the orchestrator and match the referee's reading); concerns that rest on repository code facts are for the planner to verify against source and either fix or reject in the Round 1 ledger with a stated reason. DECISIONS apply exactly.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (31-01, also 31-03 and 31-05) | `test_the_four_registry_rows_are_still_region_rows` asserts EVERY `TERMINAL_KEYS` row is an `OwnedRegion`, so the iTerm2 and herdr-app rows of 31-03 and 31-05 break it | Real (31-01:123). Pin the four existing ids as region rows; assert nothing about future rows. |
| H2 (31-01) | A recorded, deleted key stays deleted, but the record rewrite keeps only still-held keys, so the tombstone is lost after one reconfigure and a second reconfigure re-inserts it | Real (31-01:171 vs :186). The record keeps a per-key state (held with value, or deleted by the user) until strip or reinstall; test two consecutive reconfigures and then a reinstall. |
| H3 (31-01 and 31-04) | The apply algorithm and the detector classify a terminal entry with a differing value as the user's before the recorded-drift case, so a recorded old value is kept instead of rewritten | Real (31-01:172 vs :186, 31-04:162,172). Resolve recorded ownership first: an entry whose value equals the RECORDED value is ours (rewritten on drift); only an entry that differs from the record and from the vendor value is the user's. The detector receives the record. Test the integrated detector with the old ledger. |
| H4 (31-01) | Apply requires the created marker AND the proof, but strip deletes on proof alone, so a foreign file containing the fixed GUID but no marker is deleted | Real (31-01:132-134). Strip uses the same rule as apply (marker AND proof); a GUID file without the marker is left with the warning; test it. |
| M1 (31-01) | Recorded rows are silent on every post-check `OSError`, but a compare-before-commit refusal must be observable | Follow the existing region implementation (`installer/terminal_keys.py`, the write error is returned): read errors are silent for a recorded row, a write or compare-before-commit failure is reported; one contract, tested. |
| H5 (31-02) | A failed restore (`CommandError` or custom-folder refusal) still drops the record and then the profile is deleted, leaving the preference pointing at a removed profile with no previous GUID | Real (31-02:180). The recorded previous default is kept until restore is confirmed (or the preference no longer names our GUID); the profile is deleted only then; fault-injection tests at each transition (state persisted, profile written, preference written, preference restored). |
| H6 (31-02) | A failed default switch is never retried: both hooks are no-ops on reconfigure | Real (31-02:162,178-179). The record stores whether the switch succeeded; a reconfigure retries a pending switch only while the preference still equals the recorded previous default (never over a later user choice); a visible line says so. |
| M2 (31-02) | The golden argv sequence omits the reads the implementation issues | Align the expected complete argv sequences (reads included). |
| H7 (31-03) | Its first task cannot pass the ownership test | Same as H1; the fix lands in 31-01. |
| H8 (31-03, checker advisory 5) | The pre-removal hook stores its result in `note`, but `remove_tool` has later returns that drop it (manager-absent, failing command) and `note = moot` overwrites it | Real by the referee's source reading (`installer/app.py:812-842`; planner verifies). Append to `note`, surface hook lines on every post-hook outcome, tests for the manager-absent and failing-command paths. |
| M3 (31-03, also 31-05) | `_iterm2_plan` reads `Path.home()` and `os.environ` although the API receives `home` and `environ` | The new variants are defined in 31-01, so give `WholeFile.plan` and `OwnedKeys.keys` the `home` and `environ` arguments explicitly (no `Path.home()` in any new generator); test differing explicit and process environments. |
| H9 (31-04) | The chord tests demand incompatible results for uppercase keys (`CMD-K` unshifted vs shifted) | Real (31-04:161-162,171). One rule consistent with the pinned grammar (research R12), stated once and used by parser, detector and tests. |
| H10 (31-05) | The real-row drift and repeated-reconfigure tests depend on 31-01 and 31-04 contracts that do not guarantee them | Follows H2 and H3; include the real-row multi-reconfigure cases in 31-05. |
| M4 (31-05) | The claim that a custom `XDG_DATA_HOME` leaves the receipt empty is too strong (the script still links `~/.local/bin/herdr-app`) | Real by the plan's own statement (31-05:102 vs :136): test the actual custom-XDG artifacts and removal and describe the partial receipt accurately; test config deletion separately from the default keep-config path. |
| H11 (31-06 and checker blocker 1) | Both prescribed orders remove the app first; "and the reverse" (removing `herdr` while the app stays, app binary, its script paths and `~/.config/herdr-app` byte-identical) is never proven, though SPEC R3 prohibition 2 requires it | Real (31-06:171-172). Add the reverse scenario with a verdict line, digests of the app's binary, script paths and config directory before and after the multiplexer's removal in BOTH orders; add the lines to 31-07's expected list. |
| H12 (31-06) | Cleanup (`uninstall_one(other_tool)`) is written after `return` and its `SweepResult` is never inspected | Real (31-06:171-172). Cleanup runs before returning (or in a `finally`) and its result is inspected; test the sequencing with fakes. |
| H13 (31-06) | Isolation is compared only before the app install and after its removal, so a transient change made by the install is unproven | Real. Compare immediately after the app install and again after removal with a nonempty seeded multiplexer config. |
| M5 (31-06) | Task 1's acceptance depends on a caller added in Task 2 (`TARGET_ALLOWED`) | Move the acceptance to Task 2 or add a genuine Task 1 caller. |
| M6 (31-07) | The generic-e2e filter covers `cmd_bootstrap` and `cmd_resync` but `nested_install` runs the whole terminal category | The planner verifies against `scripts/container-e2e-verify.sh` (~2060-2068) whether the container's registry copy already hides the tool there; state the result explicitly and test the intended exclusion or its safe behavior. |
| M7 (31-07) | Verification blocks require `make shellcheck` unconditionally though the plan says hand runs are for diagnosis | Make them consistent with the hook policy (no hand shellcheck per commit). |
| L1 (31-07) | `cmd_herdr_app; echo rc=$?` masks the exit code | Preserve and assert the captured status. |
| H14 (31-08) | The evidence paragraph claims both orders leave the multiplexer byte-identical and every app path removed, more than the driver proves | Fixed by H11 to H13 first; then the claim names the verdict lines of the recorded transcript, nothing wider. |
| M8 (31-08) | The gate relies on GNU `date -d` | Use `python3 -c` with `datetime.date.fromisoformat` (cross-platform) for the calendar check. |
| X1 (cross) | 31-04 is wave 4 but depends only on 31-01, not 31-03 | Add the dependency (strict sequencing encoded). |
| X2 (cross) | Scratch cleanup is not exit-safe | Same exit-safe wrapper as phase 30 (`RUNDIR=$(mktemp -d); trap 'rm -rf "$RUNDIR"' EXIT; trap 'exit 130' INT TERM HUP`, `TMPDIR` only for scratch, the two final gates with the default TMPDIR) and the free-space check. |
| W2 (checker) | Four locked decisions (D-07, D-09, D-11, D-16) are changed in the plans while CONTEXT says otherwise | Done by the orchestrator: `31-CONTEXT.md` now has a dated `<amendments>` block (provisional, needs confirmation); the plans cite it. |
| W3 (checker) | `≈ apply install tuning` is never tested through `version_status` | Real (`installer/version_status.py:823-839` maps `KEYS_PENDING` to the tuning step): add one status-pass assertion per new row in `tests/test_version_status.py` (29 and 30 did the same). |
| W4 (checker) | Research open questions and the validation file are not closed | Research questions are marked RESOLVED by the orchestrator. `31-VALIDATION.md` stays `draft` until the end-of-phase Nyquist audit, as in every earlier phase: rejected, no plan change. |
| A6, A7 (checker) | The pi executor needs network access for the vendor download; the generic-e2e exclusion goes beyond D-17 | Accepted as recorded (the hash gate stops on mismatch; the exclusion is a recorded orchestrator decision). |

## OpenCode Review (opencode-referee-one), cycle 1

Using the spec-review checklist to assess all eight plans against the current repository and their shared contracts.
A cross-plan blocker is already visible: the new ownership test requires every terminal row to remain an `OwnedRegion` (`31-01-PLAN.md:123`), but 31-03 and 31-05 add other variants and repeatedly run that test unchanged.
### Document Type

GSD · implementation plans

### Overall verdict

**Issues Found — revise and re-review.** The plans are detailed and mostly sequenced, but several prescribed behaviors would either fail their own verification or leave user state incorrectly owned, unrestored, or unproven. The most consequential issues are the cross-plan ownership test, the owned-key ledger and drift rules, failed iTerm2 restoration, and the container driver’s incomplete isolation proof.

The citations below use repo-relative paths under `.planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/`. No earlier cross-AI review cycle is recorded in the plans’ round-zero ledgers.

## 31-01

**Summary:** Introduces the ownership union and generic whole-file and per-key operations.

**Findings status:** First cross-AI review; no previous-cycle findings to disposition.

**Strengths:** The proposed dispatch targets the three existing entry points (`installer/terminal_keys.py:378–525`), and `commit_region` already validates and compares the snapshot before writing (`installer/terminal_regions.py:698–725`).

**Concerns:**

- **HIGH — A test blocks both later entries.** `31-01-PLAN.md:123` requires *every* `TERMINAL_KEYS` row to be an `OwnedRegion`. Plans 31-03 and 31-05 add `WholeFile` and `OwnedKeys` rows and run this test module (`31-03-PLAN.md:152`; `31-05-PLAN.md:142`). **Required:** Pin the four existing IDs as region rows without asserting that all future rows use that variant.
- **HIGH — Deleted-key ownership is forgotten.** The plan says a recorded, deleted key remains deleted on reconfigure (`31-01-PLAN.md:171`), but then writes only previously recorded keys “still held” plus newly written keys (`31-01-PLAN.md:186`). After one reconfigure the tombstone disappears; a second reconfigure treats the key as new and inserts it. **Required:** Preserve sufficient deletion history and test at least two consecutive reconfigures, followed by reinstall.
- **HIGH — The detector prevents the required drift rewrite.** The apply algorithm checks `taken` before its recorded-value drift case (`31-01-PLAN.md:186`). Plan 31-04 classifies the exact terminal chord with an older value as a user binding (`31-04-PLAN.md:162,172`). Thus a recorded old value is kept instead of rewritten, contrary to `31-01-PLAN.md:172` and `31-05-PLAN.md:177`. **Required:** Resolve recorded ownership before treating the same key as a competing user binding; test the integrated detector and old ledger together.
- **HIGH — Strip can delete an unowned whole file.** Apply requires both marker and proof, but strip deletes on proof alone (`31-01-PLAN.md:132–134`). A pre-existing foreign profile containing the fixed GUID but no created marker can therefore be deleted, despite the foreign-file test requiring it to survive (`31-01-PLAN.md:117`). **Required:** Make deletion proof consistent with the non-ownership case and test strip of a GUID-bearing file without the marker.
- **MEDIUM — Recorded write failures are prescribed as silent.** `31-01-PLAN.md:122,132` simultaneously requires an observable race refusal and says every post-check `OSError` is silent for recorded rows. The existing region implementation returns the write error (`installer/terminal_keys.py:418–433`). **Required:** Specify and test one error contract that reports compare-before-commit failures.

**Suggestions:** Exercise multi-step state transitions rather than only one apply or strip.

**Risk Assessment:** **High:** ownership and recovery errors propagate to both terminal entries.

## 31-02

**Summary:** Generates the iTerm2 profile and implements the `defaults` seam and restoration state.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The profile generator has explicit goldens, parent-map conflict cases and a single replaceable command seam (`31-02-PLAN.md:106–114,171–182`). The existing runner accepts argv and reports command failures (`installer/run.py:130–154`).

**Concerns:**

- **HIGH — Failed restoration destroys the recovery record.** `31-02-PLAN.md:180` drops the record whenever `final` is true, including after a `CommandError` or custom-folder refusal. Plan 31-01 then deletes the profile (`31-01-PLAN.md:134`), potentially leaving the preference pointing at a removed profile with no prior GUID available for retry. **Required:** Define and test a recoverable failure path that retains the recorded previous default until restoration is confirmed or the user explicitly chose another default.
- **HIGH — Reconfigure cannot retry a failed default switch.** If `hook_after_write` fails to set the default, the state still exists; both hooks are then no-ops on reconfigure (`31-02-PLAN.md:162,178–179`). The profile can appear configured while the default was never set. **Required:** Record whether the switch actually succeeded and provide a safe, visible retry without overwriting a subsequent user choice.
- **MEDIUM — The golden command sequence contradicts the implementation.** The test expects `hook_after_write` to issue exactly a write (`31-02-PLAN.md:157`), whereas the action first reads the current default (`31-02-PLAN.md:179`); restore likewise reads preferences before writing (`31-02-PLAN.md:180`). **Required:** Align the expected complete argv sequences with the specified reads.

**Suggestions:** Add fault-injection tests at each transition: state persisted, profile written, preference written, and preference restored.

**Risk Assessment:** **High:** failures in the preference tool can strand user configuration even when happy-path goldens pass.

## 31-03

**Summary:** Adds the iTerm2 catalog entry and hooks restoration into removal.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The chosen insertion point follows fresh removal-plan verification and precedes the manager command (`installer/app.py:782–825`); the plan also calls for production-route lifecycle tests (`31-03-PLAN.md:179–185`).

**Concerns:**

- **HIGH — Its first task cannot pass the earlier ownership test.** The new `WholeFile` row (`31-03-PLAN.md:147`) contradicts `31-01-PLAN.md:123`, and the task explicitly runs that test (`31-03-PLAN.md:152`). **Required:** Fix the earlier guard before this wave.
- **HIGH — Pre-removal notes can be lost on existing early returns.** The proposed hook stores its result in `note` (`31-03-PLAN.md:192`), but `remove_tool` has subsequent returns that do not include it, including an already-removed manager package and command failures (`installer/app.py:812–842`). A restoration refusal can be invisible precisely when recovery matters. **Required:** Preserve and surface hook warnings on every post-hook outcome, with tests for the manager-absent and failing-command paths.
- **MEDIUM — Explicit HOME/environment are not used for rendering.** `_iterm2_plan` reads `Path.home()` and `os.environ` (`31-03-PLAN.md:147`), although the generic API accepts explicit `home` and `environ` (`installer/terminal_keys.py:378–386`). A caller using a different home or XDG data directory can write a profile from the wrong recorded state. **Required:** Pass the same resolved context to state lookup and rendering, and test differing explicit versus process environments.

**Suggestions:** Keep the agreed pre-cask ordering, but test its failure paths as well as the happy path.

**Risk Assessment:** **High:** an incomplete or unreported restore can outlive removal.

## 31-04

**Summary:** Pins Herdr defaults and defines the app’s key-path, parser and conflict detector.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The acquisition step requires both pinned hashes before copying files (`31-04-PLAN.md:66`), and the path rules cover `HERDR_APP_HOME` and XDG (`31-04-PLAN.md:117`). Wheel packaging includes the `installer` package (`pyproject.toml:12–17`).

**Concerns:**

- **HIGH — The chord tests demand incompatible results.** `31-04-PLAN.md:161` says `CMD-K` normalizes to unshifted `cmd+k`, while the same line and `31-04-PLAN.md:171` say any uppercase single-letter key adds Shift. `Ctrl-Shift-K` is also described as the same chord as lowercase in `31-04-PLAN.md:162`. **Required:** Establish one expected treatment of uppercase keys consistent with the pinned app grammar and make parser and detector tests agree.
- **HIGH — The detector conflicts with recorded drift handling.** The detector’s “any differing terminal value is the user’s” rule (`31-04-PLAN.md:162,172`) does not account for a value proven by the prior ownership record. See 31-01’s drift finding. **Required:** Specify the interface/order that distinguishes a recorded old value from a user change.

**Suggestions:** Keep hash verification, and test the installed wheel’s access to both data files in addition to source-tree reads.

**Risk Assessment:** **High:** incorrect chord matching either blocks the intended binding or changes a user’s shortcut.

## 31-05

**Summary:** Adds the Herdr app entry and its production keys-row lifecycle.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The plan distinguishes the app from the multiplexer, tests Intel-macOS unavailability, and adds registry, row and skill-table changes together (`31-05-PLAN.md:123–139`). Existing receipt creation records script artifacts only when created or previously proven (`installer/receipts.py:500–519`).

**Concerns:**

- **HIGH — The planned drift and repeated-reconfigure behavior depends on contradictory earlier contracts.** The real-row tests require deleted keys to stay deleted and recorded old values to update (`31-05-PLAN.md:176–177`), but 31-01’s record rewrite and 31-04’s detector do not guarantee either. **Required:** Repair those contracts first and include the real-row multi-reconfigure cases here.
- **MEDIUM — The custom-XDG receipt claim is too strong.** `31-05-PLAN.md:136` says a custom `XDG_DATA_HOME` leaves the receipt empty. The same plan states the script still links `~/.local/bin/herdr-app` (`31-05-PLAN.md:102`), and receipt recording fingerprints each declared path independently (`installer/receipts.py:514–534`). The receipt can therefore be partial rather than empty. **Required:** Test actual custom-XDG artifact and removal behavior, and describe the resulting partial receipt accurately.

**Suggestions:** Test explicit config deletion separately from the default “keep config” path; the UI allows users to opt into deleting declared config (`installer/uninstall_screen.py:551–569`).

**Risk Assessment:** **High:** user-key preservation is contingent on the unresolved ownership contract.

## 31-06

**Summary:** Builds the container-only lifecycle driver and host-testable verdicts.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The plan uses a container guard, explicit verdicts and file-backed subprocess output (`31-06-PLAN.md:155–175`). Its residue helper is grounded in the existing Ghostty driver (`tests/e2e_ghostty_driver.py:241–251`).

**Concerns:**

- **HIGH — The required reverse removal is not tested.** Both prescribed orders remove the app first (`31-06-PLAN.md:171–172`); neither removes `herdr` while the app remains and checks the app’s files. That does not establish the “and the reverse” prohibition in `31-05-PLAN.md:55–57`. **Required:** Add the reverse-removal scenario and compare the app’s binary and configuration before and after multiplexer removal.
- **HIGH — The lifecycle instructions place cleanup after `return`.** Both order steps are described as returning verdicts and *then* calling `uninstall_one(other_tool, ...)` (`31-06-PLAN.md:171–172`). Literal implementation makes the uninstall unreachable, contaminating the next order. Further, `uninstall_one` returns a `SweepResult`; it does not itself assert success or raise for a normal removal failure (`tests/e2e_landing_driver.py:468–496`). **Required:** Perform and inspect cleanup before returning each step, and test the sequencing with fakes.
- **HIGH — Isolation around installation is unproven.** In the `herdr-first` order, the driver compares before app installation with after app removal only (`31-06-PLAN.md:172`). A transient or later-reverted modification by installation is not checked; the `app-first` order has no multiplexer before app install. **Required:** Compare immediately after app installation and again after removal, with a nonempty seeded multiplexer config.
- **MEDIUM — Task 1’s acceptance depends on Task 2.** `31-06-PLAN.md:136` requires `TARGET_ALLOWED` to have a definition and a residue-rule caller, but the lifecycle caller is introduced only in Task 2 (`31-06-PLAN.md:169–172`). **Required:** Move the acceptance criterion to Task 2 or supply a genuine Task 1 caller.

**Suggestions:** Host-test lifecycle orchestration with injected install/removal functions; reserve only the vendor and container facts for the real run.

**Risk Assessment:** **High:** a green container transcript could overstate the required isolation proof.

## 31-07

**Summary:** Adds the Fedora target and filters Herdr app from the generic container registry copy.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The proposed target follows the existing landing pattern, names its container by PID and confines package installation to the container (`31-07-PLAN.md:119–124`). The dedicated PASS is required before the final plan.

**Concerns:**

- **MEDIUM — Nested category installs remain exposed to the app.** The filter is limited to `cmd_bootstrap` and `cmd_resync` (`31-07-PLAN.md:169–171`), while `nested_install` runs the entire terminal category (`scripts/container-e2e-verify.sh:2060–2068`). Ignoring the app’s outcome does not prevent its network install or nested side effects. **Required:** Account for that separate path explicitly and test the intended exclusion or its safe behavior.
- **MEDIUM — The prescribed shellcheck runs conflict with executor rules.** The plan says to run shellcheck by hand only after a hook failure (`31-07-PLAN.md:62`), but both task verification blocks require it unconditionally (`31-07-PLAN.md:128–130,176–179`). **Required:** Make verification instructions consistent with the repository’s hook policy.
- **LOW — The failing-step test’s command can mask the exit code.** `31-07-PLAN.md:110` specifies `cmd_herdr_app; echo rc=$?` while also requiring the shell process to exit 1. Without an explicit `exit` of the captured status, `echo` normally makes the shell exit successfully. **Required:** Preserve and assert the captured status.

**Suggestions:** Test the registry filter and lifecycle target independently, then validate the real target only through the orchestrator.

**Risk Assessment:** **Medium:** scope leakage into another container path and inconsistent verification instructions may derail execution.

## 31-08

**Summary:** Gates published container evidence on an orchestrator PASS and adds catalog consistency guards.

**Findings status:** No previous cross-AI cycle.

**Strengths:** The plan refuses to publish evidence before a recorded PASS and validates the date (`31-08-PLAN.md:118–127`). It keeps real-Mac checks explicitly deferred (`31-08-PLAN.md:62`).

**Concerns:**

- **HIGH — The evidence paragraph claims more than the driver proves.** `31-08-PLAN.md:121` directs a statement that both orders leave the multiplexer byte-identical and that uninstall removed every app path. The driver only checks isolation after app removal, only checks residue in the `herdr-first` order, and does not test reverse removal (`31-06-PLAN.md:171–172`). **Required:** Strengthen the driver and PASS contract first, or narrow the published claim to the checks actually performed.
- **MEDIUM — The gate relies on GNU `date` on the executor host.** `31-08-PLAN.md:118` uses `date -d`, while the project supports macOS as well as Linux (`AGENTS.md`, project description). **Required:** Use a cross-platform date validation method or explicitly constrain the executor host and verify that prerequisite.

**Suggestions:** Pin the evidence paragraph to specific verdicts in the recorded transcript, not merely a manually formatted PASS line.

**Risk Assessment:** **High:** the evidence gate can be syntactically sound while the underlying proof is insufficient.

## Cross-plan comparison

- **Wave ordering:** The declared waves are numbered sequentially, and shared-file edits are separated. However, `31-04-PLAN.md:6–7` declares wave 4 but depends only on 31-01, not 31-03. If an executor relies on dependencies rather than wave numbers, strict sequencing is not encoded. Add the dependency if strict sequencing is required.
- **Plan size:** All eight files are below approximately 60 KB and each has two tasks. That does not eliminate the much larger execution scope of several tasks, but the stated size limit is met.
- **Scratch cleanup:** The plans explicitly run `make validate` and `make test` without an owned `TMPDIR` (for example, `31-01-PLAN.md:76`), whereas the governing temporary-file rule requires an owned run directory, exported `TMPDIR`, cleanup on exit and verification of cleanup. Resolve the known long-path test issue using a short owned directory rather than exempting full runs.
- **Real-world proof:** Fake `defaults`, source-based goldens and container-only installation are useful but do not prove iTerm2’s live default behavior or Herdr’s GUI shortcuts. The deferred owner UAT is appropriate and should remain visibly open.

### Status: Issues Found — fix and re-invoke

**Not checked:** I did not execute the plans, tests, vendor downloads, containers or macOS UAT. No scratch files were created.


## Lane Log (convergence cycle 2, plans at 36d44377)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 01:32 | opencode-referee-one | one-shot probe | OK |
| 01:32 to 01:36 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

Cycle 2 of 3. The referee's readings of the plan lines were checked where they are plan-internal contradictions (31-05 golden shape vs 31-01 writer, 31-02 golden vs hooks, 31-08 claim vs 31-06 sequence); claims resting on repository code (31-07 comment association in `installer/registry.toml`, 31-03 receipt retirement before `_after_removal`, 31-01 symlink handling in `installer/agent_settings.py`) are for the planner to verify against source and fix or reject with a stated reason. DECISIONS apply exactly.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (31-01) | Per-key ownership (held entries and tombstones) is not bound to the file that received it; a changed `HERDR_APP_HOME` or XDG path lets the old ledger rewrite or strip an equal-valued key in another user file | Real. The record stores the resolved path; when the resolved path differs from the recorded one the old ledger does not apply to this file (a fresh first apply for the new file; strip leaves the other file and reports it). Test apply, drift and strip after changing the path for an initially existing file. |
| H2 (31-01) | Per-key strip deletes a seed-equal created file through `delete_if_unchanged` without refusing a symlink at the keys path | Real (planner verifies `installer/agent_settings.py` helpers). Fail closed: per-key apply and strip refuse a symlink at the keys path (a warning, never a write or delete through it); test a created file replaced by a symlink to a matching foreign file. |
| M1 (31-01) | A user-changed held value is kept without the required partial report | Real (31-01:24 vs :203). Report the partial line on that first reconfigure; test through the production row. |
| H3 (31-02) | The already-ours golden expects reads that the hooks do not issue (retained parent exports; `hook_after_write` issues no argv when `switched`) | Real plan-internal contradiction (31-02:159 vs :185-186). Choose one sequence consistent with the reinstall behavior and make golden and implementation agree. |
| H4 (31-02) | The first switch writes the installer GUID for any current value, overwriting a default the user changed between the recorded previous default and the write | Real. Apply the retry branch's previous-value check to the initial switch: write only while the preference still equals the recorded previous default, else leave it and report; test the X to Y interleaving before `hook_after_write`. |
| H5 (31-03) | After a real failed restore the successful cask removal retires the receipt before `_after_removal`, so no later uninstall reaches strip; the warning telling the user to uninstall again is unreachable | Real by the referee's source reading (`installer/app.py:859-862`, `1258-1274`; planner verifies). DECISION: when the pre-removal hook cannot confirm the restore, `remove_tool` REFUSES the removal with a visible message (the cask stays installed and the receipt intact, so the retry is reachable); a preference that no longer names our GUID counts as confirmed (so the user can fix it by choosing a default in iTerm2 Settings and retry). Test the failed restore followed by a retry through `perform_uninstall`, CLI and TUI routes. Mark provisional. |
| M2 (31-03) | The Task 1 commit ships the iTerm2 entry with the old removal ordering | Land the pre-removal hook (inert for region rows) in Task 1 and the entry and row in Task 2, or make both atomic. |
| M3 (31-04) | The pinned seed is 0.1.16 but the installer fetches the latest vendor version | Real. Fail closed: the writer seeds a missing `keys.json` only when the installed version equals the pinned default's version (read through one injected seam, `herdr-app --version`, with a recorded-output test); otherwise write nothing and report a `partial` line naming both versions; tests for equal, different and unreadable versions. |
| M4 (31-04) | `sha256sum` is not standard on macOS | Use python `hashlib` for the hash check. |
| H6 (31-05) | The real-row golden expects the record `{"keys": [...]}` but 31-01 writes `{"deleted": [...], "keys": [...]}` | Real plan-internal contradiction (31-05:180 vs 31-01:202). Align the golden with the two-field record and assert the empty tombstone list. |
| H7 (31-05) | The production path-change test starts with a created file, so it misses the existing-file case | Follows H1: add the existing-file case with a changed environment and a matching key in the newly resolved file, for apply and for removal. |
| H8 (31-06, 31-08) | App-first compares an absent multiplexer binary, so its `ISOLATION_OK` cannot prove an existing multiplexer survived the app install | Real. DECISION: narrow the claims to what is proven. App-first proves that the multiplexer's install and removal leave the app's binary, script paths and config directory byte-identical (digests taken with the app present before and after); herdr-first proves that the app's install and removal leave the existing multiplexer binary and config byte-identical (digests taken with the multiplexer present). Reword the truths, the verdict detail and the 31-08 evidence paragraph accordingly. |
| H9 (31-06) | A failed install can leave untracked vendor files outside cleanup (the `Ops.installed` check is receipt-only; `install_one` raises for any non-INSTALLED outcome) | Real (`tests/e2e_landing_driver.py:412-431`). Track attempted installs; after a failed install list the home, report files left without a receipt as the order's failure and remove the known paths in cleanup; test a failed install that leaves files and no receipt. |
| M5 (31-06) | The truth says a failed verdict ends the order but `run_order` appends verdicts and continues | State the policy explicitly: a failed INSTALL ends the order (after cleanup); verdict failures are collected and later phases still run; test the actual sequence. |
| H10 (31-07) | The awk block filter buffers from one `[[tool]]` to the next, but verified comments precede their own `[[tool]]`, so dropping the app block drops herdr's preceding comment and keeps the app's with the previous block | Real by the referee's source reading (`installer/registry.toml` herdr comment before its marker; planner verifies). A block is the comment lines immediately before a `[[tool]]` plus its body; the filter keeps every retained entry byte-identical including its preceding comments; the real-registry test compares the full retained blocks. |
| H11 (31-07) | An awk or `mv` failure is masked by the cleanup of the staged file and `nested_prepare` calls the filter without `|| return 1` | Real. Propagate staging, awk and move failures while still cleaning the staged file; `|| return 1` at both call sites; test each failure stops the bootstrap and sync. |
| H12 (31-08) | The evidence paragraph says the multiplexer was byte-identical at the app-install point in both orders | Follows H8. |
| M6 (31-08) | The gate validates a typed PASS line, not the transcript | Real. The gate also checks the run's transcript (`.e2e-artifacts/container-herdr-app/herdr-app-transcript.log` on the orchestrator host): every required verdict line present, no `_FAILED` line, ends with `TRACER_LANDING_TEARDOWN_OK`; the expected list lives in one place shared by the host test. |
| X (cross) | Final gates run with the default TMPDIR instead of an owned directory | REJECTED, no plan change: a long TMPDIR breaks `tests/test_doctor.py::test_run_doctor_reports_broken_links_and_changes_nothing` (observed in phase 30); pytest's own basetemp is removed by pytest, and every scratch directory the plans create is owned and trapped. |
| X (cross) | 31-01 is 60,749 bytes | Accepted (about 60 KB). |

## OpenCode Review (opencode-referee-one), cycle 2

Using the spec-review checklist to review all eight current plans against the repository and the previous cycle’s findings.
### Document Type

GSD · implementation plans

### Overall verdict

**Issues found — revise and re-review.** The revision addresses much of the previous cycle, including the region-only guard, tombstones, record-first drift handling, restore failure retention, reverse-removal sequencing, and the macOS date check. Several remaining issues affect ownership safety, executable test contracts, and the evidence that the container run can support.

Plan citations below are relative to `.planning/phases/31-onboard-iterm2-and-the-herdr-desktop-app/`.

## 31-01

**Summary:** Adds the ownership union and generic whole-file and per-key lifecycle.

**Findings status:** The previous region-row guard, tombstone, record-first drift, marker-and-proof, and write-error findings have explicit revisions (`31-01-PLAN.md:24-33, 123-134, 180-188`).

**Strengths:** Dispatch is specified at all three lifecycle entry points, matching the existing region paths in `installer/terminal_keys.py:378-525`. The shared write helper validates and compares the snapshot before replacing a file (`installer/terminal_regions.py:698-725`).

**Concerns:**

- **HIGH — Per-key ownership is not bound to the file that received it.** `31-01-PLAN.md:202-205` stores only key paths and values. The created-path sidecar is consulted only when a created marker exists; an *existing* user file receives no marker (`31-01-PLAN.md:182`). If `HERDR_APP_HOME` or `XDG_CONFIG_HOME` changes, the old ledger can therefore rewrite or strip an equal-valued key in a different user file. `installer/terminal_keys.py:495-505` shows the existing path-bound strip check is conditional on the marker. **Required:** Bind held entries and tombstones to the resolved file path regardless of whether the installer created it; test apply, drift and strip after changing the resolved path for an initially existing file.
- **HIGH — Per-key strip can delete a symlink target it did not create.** `31-01-PLAN.md:205` deletes a seed-equal created file through `delete_if_unchanged`, but does not refuse a symlink at the keys path. The existing helpers explicitly resolve symlinks for reads and deletion (`installer/agent_settings.py:556-577`). A created file replaced by a symlink to a matching foreign file can thus cause deletion of the target. **Required:** Define and test a fail-closed symlink policy for per-key apply and strip, including replacement of a previously created file by a symlink.
- **MEDIUM — A user-changed held value is kept without the required partial report.** The decision and truth require reporting a changed owned key (`31-01-PLAN.md:24`), but the prescribed held-value branch keeps it without calling `taken` or adding a conflict (`31-01-PLAN.md:203`). **Required:** Return the partial line on that first reconfigure and test it through the production row.

**Suggestions:** Add transition tests involving a changed path and a replaced file, rather than only a changed value at the original path.

**Risk Assessment:** **High:** the current ledger can act on another file and the strip path can delete a symlink target.

## 31-02

**Summary:** Generates the iTerm2 profile and implements the `defaults` seam and restoration state.

**Findings status:** Failed-restore retention and retry are now specified; complete command lists were added, but one golden still contradicts the implementation.

**Strengths:** The planned fake seam and autouse fixture follow the existing replaceable readback seam and fixture pattern (`installer/terminal_keys.py:274-290`, `tests/conftest.py:122-130`). Restore validates a recorded GUID before passing it to an argv-based command (`31-02-PLAN.md:170, 180-188`).

**Concerns:**

- **HIGH — The already-ours golden cannot satisfy the prescribed hooks.** `31-02-PLAN.md:159` expects an already-settled record to cause two reads in `hook_before_write` and one in `hook_after_write`. The implementation specification at `31-02-PLAN.md:185-186` can export when the retained parent is non-null and explicitly makes `hook_after_write` issue **no argv** when `switched` is true. **Required:** Choose one complete sequence consistent with the intended reinstall behavior and make the golden and implementation agree.
- **HIGH — The first switch can overwrite an intervening user choice.** `31-02-PLAN.md:185-186` records previous default X before the file write, then on a first install writes the installer GUID for *any* current value. If the user changes X to Y in between, the switch overwrites Y; uninstall later restores X, not Y. The retry branch already has the safer comparison. **Required:** Apply the same previous-value check to the initial switch and test the X→Y interleaving before `hook_after_write`.

**Suggestions:** Include the initial-switch race in the transition fault tests, alongside the existing failure and retry cases.

**Risk Assessment:** **High:** the plan contains a failing golden and can overwrite a user’s later default selection.

## 31-03

**Summary:** Adds the iTerm2 entry, row, skill table entry and pre-removal hook.

**Findings status:** The previous lost-note and explicit-HOME findings are addressed in the proposed wrapper and renderer (`31-03-PLAN.md:137, 192, 201`).

**Strengths:** `remove_tool` re-proves the preview before the proposed hook point and then executes the manager command (`installer/app.py:782-825`). Both uninstall paths use `remove_tool`, and successful removal reaches `_after_removal` (`installer/app.py:1059-1073, 1258-1274`).

**Concerns:**

- **HIGH — Recovery after a real failed restore is not demonstrated through the public lifecycle.** The test retries `strip_terminal_keys` directly (`31-03-PLAN.md:193`), but a successful cask removal retires the receipt before `_after_removal` (`installer/app.py:859-862`, `1258-1274`). The plan does not establish that a later user-visible uninstall can reach strip when the package and receipt are already gone; its warning nevertheless instructs the user to uninstall again (`31-01-PLAN.md:145`). **Required:** Test a failed restore followed by a retry through the actual CLI/TUI removal route, and provide a reachable recovery action if that route cannot retry.
- **MEDIUM — The Task 1 commit ships removal without the pre-removal hook.** The entry and working install land in Task 1 (`31-03-PLAN.md:148-154`); the required pre-cask restore lands only in Task 2 (`31-03-PLAN.md:198-203`). An interrupted execution leaves a green commit in which the new tool can be installed but removal follows the old ordering. **Required:** Land the entry and required removal ordering atomically, or make the intermediate entry unavailable until the hook lands.

**Suggestions:** Test the failure and retry from `perform_uninstall`, not solely from the generic strip helper.

**Risk Assessment:** **High:** the recovery path is unproven after the normal lifecycle removes its own receipt.

## 31-04

**Summary:** Pins Herdr vendor defaults and implements path, validation and chord-conflict logic.

**Findings status:** The uppercase grammar and record-aware detector conflicts from the previous cycle are reconciled in the current tests and action (`31-04-PLAN.md:161-173`).

**Strengths:** The plan requires both source files to match pinned hashes before copying (`31-04-PLAN.md:24, 66`). The package configuration includes the `installer` package (`pyproject.toml:12-17`).

**Concerns:**

- **MEDIUM — The pinned seed is not tied to the version actually installed.** `31-04-PLAN.md:24` fixes the seed at 0.1.16, while `31-05-PLAN.md:105-106` describes a vendor script resolving `latest.json`. A newer install may therefore receive older frozen shortcuts, despite the decision calling for the default for the installed version. **Required:** Specify a version-compatibility check or fail-closed/partial behavior for an installed version that differs from the pinned defaults, and test it.
- **MEDIUM — The required hash command is Linux-specific.** `31-04-PLAN.md:66, 137` requires `sha256sum`, which is not a standard macOS utility. The plan otherwise targets both supported host platforms. **Required:** Use a portable hash check, such as Python’s `hashlib`, or explicitly verify the executor prerequisite.

**Suggestions:** Exercise the installed wheel’s data-file access; source-tree tests alone do not prove the wheel contains the files.

**Risk Assessment:** **Medium:** a future vendor release can silently receive the wrong frozen defaults.

## 31-05

**Summary:** Adds the Herdr desktop catalog entry and production keys lifecycle.

**Findings status:** Previous repeated-reconfigure and custom-XDG receipt findings now have explicit tests (`31-05-PLAN.md:185-192`).

**Strengths:** The planned registry distinguishes the app from the multiplexer and preserves the existing receipt model, which fingerprints declared paths independently (`installer/receipts.py:500-534`).

**Concerns:**

- **HIGH — The golden expects a ledger shape that plan 31-01 cannot write.** `31-05-PLAN.md:180` requires exactly `{"keys": [...]}`, while the new writer always emits both `deleted` and `keys` (`31-01-PLAN.md:202`). The task’s first green run therefore cannot satisfy both plans. **Required:** Align the real-row golden with the specified two-field record and assert the empty tombstone list.
- **HIGH — The production path-change test misses existing user files.** `31-05-PLAN.md:188` starts with a created file and therefore exercises the sidecar. It does not cover an existing file, for which no created marker is written (`31-01-PLAN.md:182`), leaving the cross-file ownership problem described in 31-01 untested. **Required:** Add an existing-file case with a changed environment and a matching key in the newly resolved file.

**Suggestions:** Keep the separate keep-config and explicit-delete tests, and add the path-change case to both apply and removal coverage.

**Risk Assessment:** **High:** one acceptance test is inconsistent with its producer, and path changes can affect a different user file.

## 31-06

**Summary:** Builds the host-testable container driver and lifecycle verdicts.

**Findings status:** Reverse removal, cleanup before return, inspection of `SweepResult`, and separate install/removal comparisons were added. The earlier install-isolation finding is only **partially** resolved.

**Strengths:** The existing landing helper returns a `SweepResult` rather than raising for every removal failure (`tests/e2e_landing_driver.py:468-496`); the revised `removal_problem` contract accounts for that (`31-06-PLAN.md:117, 179`).

**Concerns:**

- **HIGH — App-first “install isolation” compares an absent multiplexer binary.** In the app-first sequence, `m0` and `m1` are taken before `install("herdr")` (`31-06-PLAN.md:165, 179`). The seeded config exists, but the binary is absent on both sides. The resulting `ISOLATION_OK` cannot prove an existing multiplexer binary survived that install, contrary to `31-06-PLAN.md:25` and the proposed evidence wording. **Required:** Establish and verify a non-absent binary before any comparison described as protecting an installed multiplexer, or narrow the app-first claim and add a separate scenario that proves it.
- **HIGH — A failed installation can leave untracked vendor side effects outside cleanup.** The real `Ops.installed` checks only for a receipt (`31-06-PLAN.md:180`), while `install_one` raises when installation does not reach `INSTALLED` (`tests/e2e_landing_driver.py:412-431`). A script can write files and fail before a receipt exists; cleanup then considers the tool absent and does not inspect those files before the next order. **Required:** Track attempted installs and inspect/clean or fail the order on partial artifacts even without a receipt; test a failed install that leaves files but no receipt.
- **MEDIUM — Verdict failures need not stop subsequent phases.** The truth says a failure ends the order (`31-06-PLAN.md:21`), but `run_order` appends verdict strings and continues (`31-06-PLAN.md:179`); the changed-digest test expects other verdicts to remain OK (`31-06-PLAN.md:167`). **Required:** Make the stop-or-continue policy explicit and test the actual phase sequence after a failed verdict.

**Suggestions:** Assert the actual before-state, not just equality of two digests, for every isolation claim.

**Risk Assessment:** **High:** a green app-first verdict can overstate what was present, and failed installs can contaminate the next order.

## 31-07

**Summary:** Adds the dedicated container target and filters the generic registry copy.

**Findings status:** The previous nested-target exclusion, manual shellcheck conflict and masked-exit-code issues have explicit revisions (`31-07-PLAN.md:62, 111, 157-171`).

**Strengths:** The target follows the existing bootstrap/resync locations (`scripts/container-e2e-verify.sh:383-407`), and the revised plan includes `nested_prepare` in the filter’s scope.

**Concerns:**

- **HIGH — The block filter moves or deletes neighboring entries’ comments.** `31-07-PLAN.md:169` buffers from one `[[tool]]` to the next, but verified comments precede their own `[[tool]]`; for example, the existing herdr comment is at `installer/registry.toml:3253-3281`, before its marker at line 3282. Once the new app entry is inserted before herdr, dropping the app block also drops herdr’s preceding comment, while retaining the app’s preceding comment with the previous block. This contradicts the promised byte-preservation of every other entry (`31-07-PLAN.md:23, 154`). **Required:** Preserve comment association and byte identity for all retained entries, and compare the full retained blocks—including their preceding comments—in the real-registry test.
- **HIGH — Filter errors can be hidden by cleanup.** `31-07-PLAN.md:170` specifies an awk/`mv` command followed by removal of the staged program, but does not require preserving the filtering command’s status. A successful final cleanup can mask an awk or move failure; `nested_prepare` is also instructed to call the filter without `|| return 1` (`31-07-PLAN.md:171`). **Required:** Propagate staging, awk and move failures while still cleaning the staged file, and test each failure prevents the subsequent bootstrap/sync.

**Suggestions:** Include the reverse verdict in the target’s usage description; the orchestration contract already requires it.

**Risk Assessment:** **High:** the generic copy can lose catalog documentation or proceed after a failed exclusion.

## 31-08

**Summary:** Gates the published container evidence and adds catalog consistency guards.

**Findings status:** GNU `date` was replaced with a portable Python calendar check (`31-08-PLAN.md:118`); the evidence claim remains dependent on the unresolved driver issue in 31-06.

**Strengths:** The gate rejects missing, duplicate, malformed and impossible-date PASS records before edits (`31-08-PLAN.md:64-66, 118-119`).

**Concerns:**

- **HIGH — Published evidence still overstates app-first binary isolation.** `31-08-PLAN.md:25, 121` says the multiplexer’s binary was byte-identical at the app-install point in **both** orders. In the specified app-first sequence the multiplexer has not yet been installed (`31-06-PLAN.md:165, 179`). **Required:** Strengthen that scenario as described in 31-06 before publishing this claim, or make the paragraph distinguish the absent-binary case.
- **MEDIUM — The gate validates a summary assertion, not the transcript.** `31-08-PLAN.md:118` checks a manually appended PASS line but does not verify the required verdicts or teardown in the transcript described by `31-07-PLAN.md:24`. The gate can pass with a stale or incorrectly recorded summary. **Required:** Tie the recorded PASS to the specific transcript/run and verify the required verdict set and absence of failure lines before publishing the evidence.

**Suggestions:** Retain the owner’s Mac and Linux desktop checks as open UAT, as the plan already requires.

**Risk Assessment:** **High:** the wording can claim stronger isolation than the specified test proves.

## Cross-plan comparison

- **Ordering:** The dependencies now encode the requested sequential waves, including `31-04`’s dependency on `31-03`; shared edits are not scheduled in parallel.
- **Scratch cleanup remains unresolved from the previous cycle.** Every plan directs the final `make validate` and `make test` runs to use the default temporary directory—for example, `31-01-PLAN.md:82`—rather than an owned `TMPDIR` with cleanup. That still conflicts with the governing temporary-file rule. **Required:** Use a sufficiently short owned run directory for each final gate, export `TMPDIR`, trap cleanup, and verify its removal; resolve the long-path test rather than exempting the runs.
- **Size:** All eight plans have two tasks. `31-01-PLAN.md` is 60,749 bytes, just over 60 KB; the others are below that approximate threshold. The main concern is execution scope within individual tasks, not the small size overage.
- **Verification limits:** This was a read-only review. I did not run the plans, tests, vendor downloads, containers, or macOS UAT. No scratch files were created, so there is no scratch directory to clean up.

### Status: Issues Found — fix and re-invoke
