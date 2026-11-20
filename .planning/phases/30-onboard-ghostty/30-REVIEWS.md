---
phase: 30
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T21:40:00Z
plans_reviewed: [30-01-PLAN.md, 30-02-PLAN.md, 30-03-PLAN.md, 30-04-PLAN.md, 30-05-PLAN.md, 30-06-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 30

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 94934568)

Reviewer selection: `review.default_reviewers = ["opencode-referee-one"]` (router-env/my-referee-one), the owner-required first lane. Failover only on a real failure.

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 18:37 | opencode-referee-one | one-shot probe (`Reply with exactly: OK`) | OK |
| 18:38 to 18:40 | opencode-referee-one | real review through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one`, background, 2700 s timeout, stdin `/dev/null` | exit 0, 15 KB, stderr empty |

Failures this cycle: none. No other lane or model was used. A read-only `gsd-plan-checker` pass ran beside it (0 blockers, 3 warnings, 6 info; recorded below).

## Orchestrator verification of the cycle 1 concerns

| Id | Claim | Verified against | Judgment |
|---|---|---|---|
| H1 (30-01) | `tests/test_resolve.py` freezes the first method of every registry tool per platform, so a new entry breaks it | `tests/test_resolve.py:915-925` (`_first_kinds` over `load_tools`, compared with the frozen `_FIRST_METHOD` tables) | Real: the file is missing from Task 1's files and verification. Add the Ghostty value to each fixture table (an existing-test edit forced by the decision; assertion meaning unchanged). |
| M1 (30-01) | The tracer assigns `fixture_runner(...)` to `runner`, but it returns `(calls, runner)` | `tests/test_download.py:826-828,864` | Real wording defect: unpack the tuple. |
| H2 (30-02) | `receipts.recorded_elsewhere("")` returns every receipt's paths, so another tool's file could be overwritten | `installer/receipts.py:684-701` (the function skips only its own id; with an empty id it includes all) | Real principle gap, low odds: authorize an overwrite only through Ghostty's own previous receipt (`receipts.read("ghostty")` leaves). |
| H3 (30-02) | Rollback unlinks an authorized existing icon when the desktop write fails | the plan's algorithm step (d) and `installer/cargo_distrobox.py:173-199` (staged swap that restores) | Real: stage both files and restore the previous ones on failure, or write the desktop entry first from the staged bytes; never unlink a file that existed before. |
| M2 (30-02) | `mkdtemp` sits outside the try that keeps the menu step optional | the plan and `installer/engine.py:282-283,318-319` | Real: the whole helper body, temp creation included, is inside the note-not-failure boundary; add a test. |
| H4 (30-03) | An unreadable, oversized or undecodable EARLIER default file is only reported and the write goes ahead, although that file loads before ours and our binding would override it | the plan's scan contract and `_ghostty_plan` write condition; Ghostty loads the legacy `config` before `config.ghostty` (research R11) | Real and distinct from kitty (kitty's region sits above everything, so an unscanned file cannot be overridden by it): Ghostty is last-wins per key and ours loads later. Decision: when a default file loaded BEFORE the target cannot be scanned, write nothing for that region and report a `ghostty: partial:` reason naming the file; a file loaded AFTER the target is only reported. Test an unreadable earlier file. |
| M3 (30-03, checker W2) | SPEC R4 says deleting the region shows `≈ apply install tuning`, but the shared drift rule (28 D-06, provisional) keeps a recorded install quiet | `installer/terminal_keys.py:383-397`, 30-SPEC R4 | Real tension, resolved the way 29 did: the contract holds for a host with no record or a changed region; a recorded, deleted region stays quiet (28 D-06). Record it in 30-03's decision record, name it provisional, and add one status-row test (`test_version_status`) that reaches the `apply install tuning` step text for an unrecorded Ghostty row. |
| H5 (30-04) | `_sync_ghostty` writes the zsh command even when an earlier default file could not be scanned | 30-04 plan scan reuse | Same rule as H4 for the `command` line. |
| M4 (30-04) | Revert strips only the file the resolver returns now, so a region written to legacy `config` outlives zsh removal after `config.ghostty` becomes preferred | `installer/terminal_regions.py:583-592` (strip acts on the path given) | Real: revert and strip walk every default file Ghostty loads on that OS and remove the owned regions in each; only owned regions are touched. Test resolver movement between sync and revert. |
| H6 (30-05) | The residue baseline precedes `sync_terminal_shells`, which writes the shared `.zshenv`; Ghostty removal does not revert it, so the diff fails on the test's own sync | `installer/terminal_shell.py:681-692` and `installer/app.py:630-645` (the zsh revert runs only when zsh is removed) | Real: take the baseline after a first zsh-only sync (Ghostty absent), or account for the shared file explicitly; keep the Ghostty files in the diff. |
| H7 (30-05) | FUSE success is inferred from the absence of one error string and the return code is discarded | the plan's `fuse_verdict` and `_run_ghostty` | Real: require return code 0, the `Ghostty 1.4.0` line, no fallback string and the presence of `/dev/fuse`; otherwise `_UNPROVEN`. |
| M5 (30-05) | An exception before uninstall skips uninstall and the later verdicts | the plan's driver order | Real: uninstall in a `finally`; test a failure before the readback. |
| M6 (30-06) | The negative mutation puts `note` on a pacman method, which the loader rejects before the guard runs | `installer/model.py:635-640` | Real: mutate a loader-valid download method of another tool. |
| M7 (30-06) | The PASS gate accepts any line starting `ghostty-container: PASS (` | the plan's awk | Real: require exactly one well-formed line with an ISO date. |
| W1 (checker; cross-plan) | `make validate` and `make test` run twice in the last task of 30-01 and 30-02 | 30-01 lines 198-199, 30-02 lines 237-238 | Real: keep only the post-commit run; the targeted pytest is the only pre-commit command. |
| W3 (checker 2b) | The phase has no defined path when FUSE cannot mount in rootless podman: 30-06 stays BLOCKED forever | 30-05 and 30-06 gate text | Decision: the gate accepts one well-formed `ghostty-container: PASS (<date>; fuse: PROVEN)` or `PASS (<date>; fuse: UNPROVEN, extract-and-run proven)` line; in the second case 30-06 words the evidence as "extract-and-run proven in a container; the FUSE mount is checked on a Bazzite host (UAT)" and never claims the FUSE pass. A lifecycle failure or an unproven extract-and-run pass is never accepted. |
| X1 (cross-plan) | 30-02 and 30-03 share a checkout (30-02 runs tests/test_registry.py that 30-03 edits) | the plan file lists | No plan change: the orchestrator runs the same-wave plans one after the other in the working tree, never in parallel. |

Checker advisories 3 to 9 are recorded; the ones that change a plan: 4 (ledger the three narrowings of locked decisions in the SUMMARY), 6 (30-06 must not break the 60-line window of 30-01's facts test: widen nothing in an existing test, keep the comment short or add the new text outside the window), 7 (count only code lines in the X-KDE-Shortcuts acceptance grep), 8 (add a test that reaches `app._after_removal`'s Ghostty path or state the generic path covers it).

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist to check all six plans against the current source and their execution order.
A high-risk interaction is emerging around the staged receipt changes: the existing tracer’s one-artifact assertion conflicts with the later menu integration. I’m checking the related ownership and container paths before finalizing the review.
# Phase 30 plan review

**Verdict: Issues found — revise before execution.** The plans cover the requested routes and lifecycle in detail, but the current sequence has test-gate blockers, a receipt-ownership/data-loss risk, and gaps in the proposed container proof.

**Review basis:** GSD · plan archetype. I read all six current plan files and checked the material findings below against the cited repository source. This is cycle 1; the plans’ ledgers record no previous cross-AI review cycle.

## 30-01

### 1. Summary

Adds the Ghostty catalog entry, download-method keys and community-build note, with an engine tracer and checksum-mismatch tests.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- The proposed pinned raw route uses the existing checksum-before-placement path: `installer/download.py:415-434` fetches and verifies before replacement, and `installer/download.py:486-496` raises on a digest mismatch.
- The plan stages the registry entry and closed skill-table row together, and defers the tuning declaration until the keys row exists (`.planning/phases/30-onboard-ghostty/30-01-PLAN.md:34-35`).

### 4. Concerns

- **HIGH — The new entry breaks an unlisted registry-wide golden.** `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:151-152` lists the permitted pin edits and commits only the named files. But `tests/test_resolve.py:915-925` compares the complete registry-derived first-method mapping against frozen platform tables. Adding Ghostty adds a key to each actual mapping, so the full suite cannot pass without updating those tables. `tests/test_resolve.py` is absent from the task’s files and targeted verification.
- **MEDIUM — The prescribed tracer runner is not a runner.** The plan assigns `fixture_runner(...)` directly to `runner` (`.planning/phases/30-onboard-ghostty/30-01-PLAN.md:140`), but `tests/test_download.py:826-828,864` returns `(calls, runner)`. Passing the tuple to `install_tool` fails before proving the tracer.

### 5. Suggestions

Add the Ghostty value to each first-method golden, include that file in Task 1 and its verification, and unpack the fixture runner explicitly.

### 6. Risk Assessment

**High:** the catalog change cannot meet the stated full-suite gate as written.

## 30-02

### 1. Summary

Adds AppImage desktop/icon extraction, receipt leaves, uninstall filtering, and temporary-directory handling.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- `artifact_paths` is already the shared formula for placement and receipt/removal evidence (`installer/download.py:284-313`; `installer/receipts.py:500-520`), so extending it is an appropriate integration point.
- The plan retains a no-receipt uninstall filter analogous to the existing cargo-distrobox filter (`installer/uninstall.py:56-64`).

### 4. Concerns

- **HIGH — Any other tool’s receipt authorizes overwriting its files.** The algorithm uses `receipts.recorded_elsewhere("")` as the set of paths it may replace (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:196`). That function explicitly returns paths from *other* receipts (`installer/receipts.py:684-701`); with an empty ID it returns all readable receipts. A path owned by a different tool can therefore be overwritten. The new Ghostty receipt will not necessarily claim it because pre-existing leaves are excluded unless Ghostty’s previous receipt proved them (`installer/receipts.py:513-519`).
- **HIGH — Failure rollback can delete an existing recorded icon.** The same algorithm replaces an authorized existing icon, puts its path in `written`, and unlinks every written path if the later desktop write fails (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:196`). That removes the prior icon rather than restoring it. The existing multi-file staging precedent preserves prior files and rolls back on failure (`installer/cargo_distrobox.py:173-199`). This is a data-loss path on reinstall or repair.
- **MEDIUM — Temporary-directory creation is outside the promised failure boundary.** The plan constructs `work = Path(tempfile.mkdtemp(...))` before the `try` (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:196`). An `OSError` there escapes the menu helper; the engine handles `OSError` as an install-method failure after the binary has already been placed (`installer/engine.py:282-283,318-319`), contradicting the promised optional-menu behavior.

### 5. Suggestions

Authorize replacement only with the current tool’s matching receipt proof; preserve or restore previously existing files on partial failure. Put temporary-directory creation and cleanup failures inside the optional-menu error contract, with reinstall, other-tool ownership and `mkdtemp` failure tests.

### 6. Risk Assessment

**High:** the proposed optional feature can overwrite another tool’s artifact or delete a previously installed icon.

## 30-03

### 1. Summary

Adds Ghostty’s config resolver, conflict scan, keys region, tuning declaration, drift behavior and removal tests.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- The proposed resolver tests cover the important empty/non-empty and legacy/preferred file combinations (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:130-133`).
- The plan uses the existing path-bound cleanup guard rather than deleting whichever config happens to resolve later (`installer/terminal_keys.py:435-449`).

### 4. Concerns

- **HIGH — Conflict-scan failures do not prevent a potentially overriding write.** The plan says an unreadable, oversized, undecodable or malformed default file produces a partial report and scanning continues (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:152`); `_ghostty_plan` then writes if the collected `taken` set does not contain the chord (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:199`). A setting in an unreadable *earlier* loaded file can consequently be overridden by the new binding in the later target file. This violates the plan’s own no-overwrite guarantee; a warning does not make the write safe.
- **MEDIUM — Deleted-region drift conflicts with the locked SPEC acceptance.** The plan explicitly treats a deleted region with a written-once record as non-pending (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:33,232-233`), matching the current shared mechanism (`installer/terminal_keys.py:383-397`). But `30-SPEC.md` requires deleting the region to show `≈ apply install tuning` and reconfigure to restore it. The plan and acceptance contract need an explicit reconciliation; implementing both as written is impossible.

### 5. Suggestions

Fail closed for an unchecked default file when its contents could be overridden, and test an unreadable earlier file. Resolve the SPEC/shared-mechanism discrepancy before execution rather than silently choosing one.

### 6. Risk Assessment

**High:** incomplete conflict evidence can lead to an effective user-binding override.

## 30-04

### 1. Summary

Adds Linux Ghostty shell synchronization, user-command detection, removal and status reporting.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- The planned use of `_safe_executable` plus `shlex.join` addresses the shell-command boundary; `_safe_executable` already rejects relative paths and control characters (`installer/terminal_shell.py:160-167`).
- The plan covers both install orders and tests that the sibling keys region survives zsh removal (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:115-123`).

### 4. Concerns

- **HIGH — The shell path inherits the scan’s unsafe partial behavior.** `_sync_ghostty` writes the zsh command whenever `scan.user_command` is false, even when `scan.reports` says a default file could not be checked (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:130-132`). As in 30-03, an unchecked earlier file can contain a user command overridden by the new target-file command. This is distinct from the locked decision to report, rather than follow, explicit `config-file` includes.
- **MEDIUM — Resolver movement leaves the old shell region behind.** Revert strips only `ghostty_config_path(...)` at the time of revert (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:133`). The resolver intentionally changes when a preferred file appears (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:131-132`), so a region previously written to legacy `config` can remain active after `config.ghostty` becomes preferred and zsh is removed. The current `strip_region` only acts on the path passed (`installer/terminal_regions.py:583-592`).

### 5. Suggestions

Refuse an unsafe write when a relevant default file cannot be scanned. Test resolver movement between sync and revert, and define a safe way to locate and remove the old owned region.

### 6. Risk Assessment

**High:** user settings can be overridden when the scan is incomplete; stale regions can survive lifecycle changes.

## 30-05

### 1. Summary

Builds the disposable-container target, host-tested verdict helpers, and orchestrator-only FUSE and extract-and-run lifecycle runs.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- The target reuses the existing exact-name teardown and verifies the container is gone (`scripts/container-e2e-verify.sh:2745-2764`).
- The plan requires fallback to be recorded as `_UNPROVEN`, not as a FUSE pass (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:24`).

### 4. Concerns

- **HIGH — The residue baseline precedes a shared zsh mutation that Ghostty removal does not revert.** The driver takes `before` before calling `sync_terminal_shells`, then expects no non-allowlisted new home files after removing Ghostty (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:143-145`). The sync writes the shared `.zshenv` before terminal-specific work (`installer/terminal_shell.py:681-692`), while Ghostty removal strips its keys row; the desktop-shell cleanup is conditional on removing **zsh** (`installer/app.py:630-645`). On a clean baseline, the proposed Ghostty lifecycle can therefore fail its residue verdict because of the test’s own shared sync. The host tests exercise verdict functions, not this lifecycle interaction.
- **HIGH — FUSE success is inferred from absence of one error string.** `fuse_verdict("")` must return OK (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:121`), and `_run_ghostty` discards the subprocess return code (`:144`). Silence is not positive evidence of a successful FUSE mount; a different runtime failure or fallback diagnostic could be misclassified. This does not meet the plan’s claim that `FUSE_OK` means the AppImage really mounted (`:24`).
- **MEDIUM — Early lifecycle exceptions can skip uninstall and later verdicts.** The driver is instructed to read the resolved config and run subsequent work before uninstall, while also claiming every later step runs after failure (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:145`). A missing or unreadable config raises before `uninstall_one`; `main` catches it outside the lifecycle (`:146`). The container is eventually removed, but the promised removal diagnosis and cleanup sequence do not run.

### 5. Suggestions

Establish the shared zsh baseline before the Ghostty-specific residue comparison, or account for it explicitly. Require a successful command and positive FUSE-mount evidence. Put uninstall in a lifecycle `finally` and test failures before readback.

### 6. Risk Assessment

**High:** the mandatory gate may either fail for test-created residue or claim stronger FUSE evidence than it collected.

## 30-06

### 1. Summary

Gates evidence wording on the recorded container result and adds catalog consistency tests.

### 2. Findings status

No previous review findings to assess.

### 3. Strengths

- The plan stops before edits when its recorded PASS gate is absent or contradicted (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:62-63,115-116`).
- It keeps real-Mac and Bazzite-host checks as owner UAT rather than claiming them complete (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:193-195`).

### 4. Concerns

- **MEDIUM — The proposed negative mutation cannot reach the intended guard.** The plan adds `note` to Ghostty’s pacman method in a temporary registry and expects the note-scope test to fail (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:151-153`). The model rejects unknown per-method keys before returning tools (`installer/model.py:635-640`), and `note` is deliberately not allowed on pacman. The mutation proves loader rejection, not that the catalog-scope assertion detects a valid but misplaced note.
- **MEDIUM — The PASS parser does not validate the date it later publishes.** The gate accepts any line beginning `ghostty-container: PASS (` (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:116`), while the next edit treats the parenthesized text as a date and tests require an ISO date (`:109,118`). A malformed PASS line passes the gate but cannot satisfy the prescribed evidence paragraph.

### 5. Suggestions

Mutate a loader-valid download method on another tool for the note-scope test. Require exactly one well-formed dated PASS line in the gate.

### 6. Risk Assessment

**Medium:** evidence gating is directionally sound, but its parser and one guard’s mutation proof are incomplete.

## Cross-plan assessment

- **Wave overlap:** The declared modified-file lists for 30-02 and 30-03 are disjoint (`30-02-PLAN.md:8-18`; `30-03-PLAN.md:8-15`), but 30-02’s targeted tests include `tests/test_registry.py` (`30-02-PLAN.md:239-241`), which 30-03 edits. Parallel execution in a shared checkout can observe a partially edited test or registry. Use isolated worktrees or serialize integration and final gates.
- **Test-gate sequencing:** Plans 30-01 and 30-02 say both to run the final full gates before the last commit and again after it (`30-01-PLAN.md:198-199`; `30-02-PLAN.md:237-238`), contrary to their own once-after-the-last-commit rule. Make the commands and ordering unambiguous.
- **Evidence scope:** The review verified the cited source paths and plan text; I did not execute tests, install Ghostty, check upstream release assets, or run the container. The planned real-hardware and FUSE results therefore remain unproven.

### Status: Issues Found — fix and re-invoke

No files were changed or scratch artifacts created. Remaining risk: this review is targeted, not an exhaustive execution or live upstream audit.


## Lane Log (convergence cycle 2, plans at f5e3dd48)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 19:06 | opencode-referee-one | one-shot probe | OK |
| 19:06 to 19:09 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, 14 KB, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

| Id | Claim | Verified against | Judgment |
|---|---|---|---|
| H1 (30-03) | The plan still contradicts SPEC R4's deleted-region acceptance | `installer/terminal_keys.py:350-361,383-397` (a recorded install whose region is absent returns quietly) and 30-SPEC R4 | Real contradiction in text. DECISION: amend 30-SPEC R4's acceptance (done in this commit, dated 2026-11-20, flagged "needs confirmation"): the contract holds for a host with no record or a changed region; a region deleted after a recorded install stays deleted and quiet, as 28 D-06 and the phase 29 rows do. The plan keeps the shared rule. |
| H2 (30-03) | The truth says a deleted recorded region stays quiet AND a reconfigure restores it, but reconfigure returns without writing | `installer/terminal_keys.py:350-361` | Real wording defect: the truth must say a reconfigure does NOT restore a deleted recorded region (28 D-06); the restore test uses an edited present region and an unrecorded host. |
| H3 (30-05) | `FUSE_OK` is still inferred (version output + /dev/fuse + no fallback text), not a mount observation | the plan's `fuse_verdict` | Real: positive evidence is a FUSE mount observed while the AppImage runs: the driver starts `<appimage> --appimage-mount`, reads the mount point it prints, finds that mount point with a `fuse` filesystem type in `/proc/self/mountinfo`, then terminates the process; the verdict takes that observation, the return code and the version line. Without the observation the verdict is `_UNPROVEN`. |
| H4 (30-05) | A host without `/dev/fuse` cannot reach the extract-only alternative because the script always passes `--device /dev/fuse` and container start failure is infeasible | the plan's container start, `scripts/container-e2e-verify.sh:2771-2793` | Real: add `--device /dev/fuse` only when `/dev/fuse` exists on the host; otherwise start without it, and the FUSE pass prints `_UNPROVEN` naming the missing device while the extract-and-run pass still runs. |
| H5 (30-06) | The acceptance `grep -c 'disposable container, 30 D-18'` expects 2 but both clauses are cells of one table row, so `grep -c` returns 1 | `tests/test_tool_onboarding_skill.py:141-147` (one row is one line), `grep -c` counts lines | Real: count occurrences (`grep -o ... | wc -l`) or assert the cells separately in the test. |
| M1 (30-02) | The "every failure is a note" boundary excludes the work before the try; a failed restore contradicts the "never lost" truth; parent directories created by the failed call stay | the plan's helper steps | Real: state a failed restore as a reported partial rollback (not a guarantee), move the path and lexists work inside the boundary, remove only empty parent directories this call created; test a failure after parent creation. |
| M2 (30-04) | On a resolver move the conflict path removes the old shell region only from the currently resolved file | the plan's conflict branch | Real: the conflict and blocked paths use the same every-default-file strip as the zsh-gone revert; test a resolver move followed by a user command and by a blocked scan. |
| M3 (30-05) | The scratch-home receipt-path test passes an arbitrary `home` but 30-02's artifacts use `Path.home()` | `tests/conftest.py:285-295` | Real: the test binds `Path.home()` to its home explicitly (monkeypatch HOME) or derives from `Path.home()`. |
| M4 (30-05) | Extract mode ignores the version command's exit status | the plan's `_run_ghostty` use | Real: require exit 0 in both modes. |
| M5 (30-06) | The gate accepts impossible dates such as 2026-99-99 | the plan's awk pattern | Real: after the awk match, validate with `date -d <date> +%F` equal to the date; a negative test for an impossible date. |
| L1 (30-01) | The staged registry comment describes the menu placement before 30-02 implements it | 30-01 line 153 | Accepted: 30-01's comment uses planned wording; 30-02 makes the placement claim. |
| X1 | Test-run hygiene: no owned TMPDIR for the prescribed pytest and full-suite commands | AGENTS.md scratch rule | Accepted as one objective line: run the targeted pytest and the final gates with `TMPDIR` set to a unique directory created by the executor and removed at the end (its own scratch only). |

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist to verify the revised plans against the repository and the prior findings.
One prior concern remains unresolved: the proposed deleted-region behavior still contradicts the locked acceptance criterion; marking it provisional does not make both behaviors achievable.
# Phase 30 plan review — convergence cycle 2

**Verdict: Issues found — revise before execution.** The revisions address several cycle 1 findings, notably receipt-specific menu ownership, rollback coverage, multi-file region stripping, and the zsh-only residue baseline. Blocking issues remain in the locked drift contract, container proof, and several prescribed tests and gates.

**Review basis:** GSD · plan archetype. I reread all six plans from disk and checked the material claims below against repository source. This was a targeted source review, not an execution of the plans.

## 30-01

1. **Summary**  
   Adds the Ghostty registry entry, method keys, community-build note, engine tracer, and digest-mismatch checks.

2. **Findings status**  
   Cycle 1’s first-method golden and runner-tuple findings are addressed in `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:141-145,155`. The final gate ordering is also clarified at `:203-204`.

3. **Strengths**  
   The tracer follows the existing digest-before-placement route: `installer/download.py:415-434` fetches and verifies before the raw swap, and `:486-496` raises on mismatch.

4. **Concerns**
   - **LOW — The staged registry comment describes menu behavior before it exists.** Task 1 requires the comment to say the installer places a menu entry and drops `X-KDE-Shortcuts` (`.planning/phases/30-onboard-ghostty/30-01-PLAN.md:153`), but the implementation does not land until 30-02 (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:223-246`). The intermediate commit is testable but its catalog description is temporarily ahead of behavior.

5. **Suggestions**  
   Use planned wording in 30-01, then make the placement claim in the commit that implements it.

6. **Risk assessment**  
   Low in isolation; downstream findings prevent phase approval.

## 30-02

1. **Summary**  
   Adds AppImage desktop/icon extraction, receipt leaves, uninstall filtering, and temporary-directory handling.

2. **Findings status**  
   Cycle 1’s other-tool receipt authorization, destructive rollback, and `mkdtemp` error-boundary findings are addressed by the specified own-receipt check and rollback tests (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:187-196,203-204`).

3. **Strengths**  
   The design uses `artifact_paths` for the shared placement/removal formula; the current function is explicitly the common evidence source (`installer/download.py:284-300`). The receipt writer already limits pre-existing leaves to those previously proven (`installer/receipts.py:500-519`).

4. **Concerns**
   - **MEDIUM — The “every failure is a note” boundary excludes work performed before the `try`.** The planned helper calculates artifact paths and checks `os.path.lexists` before the stated error boundary (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:204`). More importantly, the two-file rollback can itself fail, which the plan correctly reports, but its truth still promises that a previously existing file is *never* lost or changed (`:33`). A failed restore can leave the newly written icon in place. The test at `:195` acknowledges this case but does not require the resulting state to be described accurately.
   - **MEDIUM — Temporary directories created for failed menu writes can leave new host directories.** The planned rollback unlinks newly created leaves but does not remove parent directories created by `host.parent.mkdir(...)` (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:204`). This is not equivalent to restoring the pre-call filesystem state and is absent from the failure tests.

5. **Suggestions**  
   Describe failed restoration as a reported partial rollback rather than a guaranteed restoration. Cover failure after parent creation and remove only directories this invocation created if they are empty.

6. **Risk assessment**  
   Medium: ordinary ownership handling is much safer, but disk-error recovery still has a documented partial-state case.

## 30-03

1. **Summary**  
   Adds Ghostty’s resolver, conflict scan, keys region, tuning declaration, drift handling, and multi-file strip.

2. **Findings status**  
   The cycle 1 earlier-file scan finding is addressed by `blocked` and refusal (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:146,160-161,200`). The resolver-movement strip finding is addressed by `strip_files` and explicit tests (`:210,251`). The deleted-region finding is **not resolved**; it is now recorded as provisional.

3. **Strengths**  
   The plan explicitly scans both Linux and all four macOS default files and tests user chords in each (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:141-147,198`). Its multi-file strip preserves the existing bound-path check in `_drop_created_config` (`installer/terminal_keys.py:470-495`).

4. **Concerns**
   - **HIGH — The plan still contradicts the locked deleted-region acceptance.** The SPEC requires deleting the region to show `≈ apply install tuning` and reconfigure to restore it (`.planning/phases/30-onboard-ghostty/30-SPEC.md:36-39`). The plan instead requires a recorded deletion to stay quiet (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:33,245`), matching the current early returns in `installer/terminal_keys.py:350-361,383-397`. An unrecorded host is a different scenario; its new test cannot satisfy the deleted-after-install acceptance. Calling the conflict provisional does not settle which contract execution must meet.
   - **HIGH — The stated reconfigure outcome is internally inconsistent.** The plan’s truth says a deleted recorded region remains quiet **and a reconfigure restores it** (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:33`), but the existing reconfigure path returns without writing when `recorded and not region_present` (`installer/terminal_keys.py:350-361`). The planned tests only reconfigure an *edited*, present region (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:245-246`).

5. **Suggestions**  
   Before execution, obtain an explicit amendment reconciling SPEC R4 and 28 D-06, then align the status behavior, reconfigure behavior, and a test that deletes a previously installed region. Do not substitute the unrecorded-host test for that case.

6. **Risk assessment**  
   High: the current plan cannot meet its own stated behavior and the locked acceptance simultaneously.

## 30-04

1. **Summary**  
   Adds Linux zsh sync, user-command and include reporting, shell-region reversion, and status tests.

2. **Findings status**  
   Cycle 1’s unchecked-earlier-file and resolver-movement revert findings are addressed in the planned scan and revert walk (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:123-124,138-140`).

3. **Strengths**  
   The planned `shlex.join` is appropriate for Ghostty’s shell-command boundary, while the existing `_safe_executable` rejects relative paths and control characters (`installer/terminal_shell.py:160-167`).

4. **Concerns**
   - **MEDIUM — A resolver move can leave an active old shell region during an ordinary sync.** The plan removes a previous region only from the *currently resolved* path when it encounters a user command or blocked scan (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:122-123,138`). It walks all default files only when zsh disappears (`:140`). If an earlier sync wrote to legacy `config`, then `config.ghostty` becomes preferred and a user command is added, the old installer region remains in the legacy file despite the plan’s promise that an existing installer region is removed. Depending on loaded settings, this can also leave stale configuration after the conflict is reported.

5. **Suggestions**  
   Define safe removal of old owned shell regions from all applicable files during the conflict path, and test a resolver move followed by a user command and by a blocked scan.

6. **Risk assessment**  
   Medium: zsh removal is covered, but the normal conflict transition remains incomplete.

## 30-05

1. **Summary**  
   Builds the disposable-container driver and harness verb; the orchestrator runs FUSE and extract-and-run lifecycle checks.

2. **Findings status**  
   The baseline adjustment and `finally` cleanup address the main cycle 1 concerns (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:31-32,153-158`). FUSE checking is improved, but the proposed conditions still do not prove a mount.

3. **Strengths**  
   The target reuses the existing landing teardown, which removes the named container and verifies it is gone (`scripts/container-e2e-verify.sh:2745-2764`). It also distinguishes an unproven FUSE result in its recorded output (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:24,30`).

4. **Concerns**
   - **HIGH — `FUSE_OK` is still an inference, not evidence of a FUSE mount.** The proposed predicate requires successful version output, `/dev/fuse` existence, and absence of one fallback diagnostic (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:127,155`). Those observations do not establish that the process actually mounted the AppImage; an alternate fallback path or diagnostic could produce the same result. Yet 30-06 publishes “once with FUSE” from this verdict (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:119`).
   - **HIGH — A host without `/dev/fuse` cannot reach the accepted extract-only alternative.** The script always starts its sole container with `--device /dev/fuse` (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:203-207`). Container startup occurs inside `landing_stage`, which exits as infeasible on failure (`scripts/container-e2e-verify.sh:2771-2782,2791-2793`). If the host has no device to pass, neither lifecycle pass runs, so the defined `fuse: UNPROVEN, extract-and-run proven` path cannot be reached.
   - **MEDIUM — The scratch-home receipt-path test does not match the planned path formula.** The test passes an arbitrary `home` and expects all artifacts relative to it (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:141,152`), but 30-02’s planned menu artifacts use `Path.home()` rather than that argument (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:203`). The suite supplies a separate per-test HOME (`tests/conftest.py:285-295`), so unless the test explicitly makes `Path.home()` equal its supplied `home`, `relative_to(home)` fails.
   - **MEDIUM — Extract-mode version success ignores the command exit status.** `_run_ghostty` returns the code, but the install verdict takes only the output line; only FUSE mode passes the code to `fuse_verdict` (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:125-127,157-158`). A process that prints the expected version and exits nonzero can satisfy the extract-mode version check.

5. **Suggestions**  
   Require observable mount evidence before `FUSE_OK`; otherwise retain `UNPROVEN`. Provide a no-device container route for extract-only proof. Bind the path test’s HOME explicitly, and require zero exit status for the version command in both modes.

6. **Risk assessment**  
   High: the mandatory evidence gate can either overstate FUSE proof or be unreachable on a relevant host configuration.

## 30-06

1. **Summary**  
   Gates catalog evidence wording on the orchestrator result and adds Ghostty consistency guards.

2. **Findings status**  
   Cycle 1’s invalid note mutation is corrected to use a loader-valid `github_release` method (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:152-154`; `installer/registry.toml:91-117`). The PASS gate now checks a fixed date-shaped line, though it does not validate whether the date is a real calendar date.

3. **Strengths**  
   The plan distinguishes the two evidence wordings and stops before edits when its gate fails (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:63-64,117-120`).

4. **Concerns**
   - **HIGH — A mandatory acceptance count cannot pass as written.** Both evidence clauses are appended to cells of the same Ghostty table row (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:120`), but the acceptance command expects `grep -c 'disposable container, 30 D-18'` to return **2** (`:133`). `grep -c` counts matching *lines*, not occurrences; a single table row yields 1. The skill’s table parser also treats each row as one line (`tests/test_tool_onboarding_skill.py:141-147`).
   - **MEDIUM — The gate accepts impossible dates.** Its `[0-9]` pattern accepts, for example, `2026-99-99`, although the plan says a malformed ISO date is blocked (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:24,117`). The date is subsequently published in the registry comment (`:119`).

5. **Suggestions**  
   Count occurrences or assert the two parsed cells separately. Validate the date as an actual ISO calendar date and add a negative gate test for an impossible date.

6. **Risk assessment**  
   High for execution: the stated acceptance check is guaranteed to disagree with the required one-line table row.

## Cross-plan assessment

- **Execution sequencing:** The plans now state that 30-02 and 30-03 run serially in the shared checkout (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:78`; `.planning/phases/30-onboard-ghostty/30-03-PLAN.md:89`). Ensure the actual orchestrator honors that instruction rather than dispatching both wave-2 plans concurrently.
- **Evidence dependency:** 30-06’s wording is only as strong as 30-05’s proof. Fix the FUSE verdict and no-device route before allowing the evidence gate to publish a FUSE claim.
- **Test-run hygiene:** The prescribed pytest and full-suite commands do not specify an owned `TMPDIR` or cleanup procedure, despite the mandatory host scratch rule in the supplied `AGENTS.md`. Add an execution wrapper that creates a unique run directory, exports `TMPDIR`, and removes it on every exit path.
- **Previous findings:** H1–H6 and M1–M2/M4–M6 have concrete revisions. M3 remains a contract conflict; H7 is only partially addressed. The PASS parser’s date *shape* is fixed, but calendar validity remains unchecked.

### Status: Issues Found — fix and re-invoke

No files were changed or scratch artifacts created. Tests, upstream assets, real Ghostty, and containers were not run; hardware and live FUSE behavior remain unverified.


## Lane Log (convergence cycle 3, plans at abeae181)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 19:56 | opencode-referee-one | one-shot probe | OK |
| 19:56 to 19:59 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used. The referee's own first finding (30-01/30-02 tracer one-artifact assertion) was withdrawn by the reviewer in the same message and is not counted.

## Orchestrator verification of the cycle 3 concerns

Cycle 3 is the convergence cap: after it the run fixes and executes when fewer than four critical and HIGH findings remain (owner rule). Real HIGH: 3 (H1, H4, H5). Rejected: 2 (H2, H3).

| Id | Claim | Verified against | Judgment |
|---|---|---|---|
| H1 (30-01) | The method-order test applies `pinned_url` to every platform's method, but `pinned_url` needs a `url` parameter that pacman and cask methods lack | `installer/download.py:167-175` (`pinned_url(method)` renders a tarball URL) and 30-01 plan line 143 | Real: compare `pinned_url` only for tarball methods and `(kind, package or cask)` for the others. |
| H2 (30-03) | SPEC R4 still requires missing-region repair while the plan forbids it for a recorded deletion | 30-SPEC R4 as amended 2026-11-20 at edf24ed8 | REJECTED as a repeat: the contradiction was resolved by an explicit, dated SPEC amendment flagged "needs confirmation", exactly as phase 28 (R3) and phase 29 (Konsole) did. The reviewer reads the pre-amendment sentence; the amendment is on the same line. The owner confirmation list carries it. No plan change. |
| H3 (30-03) | The keys scan does not follow `config-file` includes in an earlier default file, so our later binding could override an included one | 30-CONTEXT D-10 (locked: a `config-file` include is not followed, write anyway and add a `partial:` line saying included files were not checked); research line 267 (`config-file` entries load after the file that names them, Config.zig v1.4.0:2578-2605) | REJECTED: D-10 is a locked decision that applies to includes in general, and the plan already reports the partial line; the research shows included files are replayed after the file naming them, so an included binding does not lose silently to ours without the partial note. Reopening D-10 is the owner's call (it is on the confirmation list). No plan change. |
| H4 (30-05) | `install_one` runs before `run_lifecycle`, so a failed install that already placed artifacts bypasses the cleanup and residue diagnosis | `tests/e2e_landing_driver.py:412-431` (`install_one` raises for any non-INSTALLED outcome) | Real: install and every later step run under the cleanup boundary; a failed install still triggers uninstall and the residue diagnosis. |
| H5 (30-05) | The removal verdict compares only before and after uninstall; SPEC R5 requires the after-install listing and the difference to equal the receipt paths plus the regions | 30-SPEC R5 acceptance, the plan's verdict | Real: capture before-install, after-install and after-uninstall listings; the verdict requires (after-install minus before-install) minus receipt paths and the two regions to be empty, the after-uninstall state to equal the baseline plus the allowlist, and seeded user content in `~/.config/ghostty` to survive. |
| M1 (30-01) | The desktop-id pattern allows `a..b` but the threat register claims `..` is rejected | 30-01 plan lines 205 and 246 | Real wording defect: reject consecutive dots in the pattern (smallest) and keep the claim. |
| M2 (30-02) | A destination swapped for a symlink between the ownership check and the write is followed by `atomic_write_bytes` | `installer/atomic.py:36-52` | Real, narrow: refuse a symlink destination immediately before each write (a note, never a write through it) and test a destination swapped for a symlink after the check. |
| M3 (30-04) | A target-read failure returns before the multi-file sweep | the plan's `_sync_ghostty` order, `installer/atomic.py:94-102` | Real: run the non-target sweep before reading the target, or independent of its failure; test an unreadable target with a readable old region. |
| M4 (30-05) | The region readback verdict ignores the command exit codes | the plan's `_run_ghostty` use | Real: require exit 0 for both readback commands; test a nonzero exit with matching output. |
| M5 (30-06) | 30-01 pins the comment block at 40 lines, 30-06 allows 55 and may not edit the old test | 30-01 line 145, 30-06 lines 28, 76, 91-92 | Real: carry the 40-line limit as the effective limit in 30-06 (its paragraph must keep the block at 40 lines or fewer). |
| X1 | Scratch cleanup is only "at the end" | AGENTS.md scratch rule | Accepted: each plan's scratch rule becomes an exit-safe wrapper (`trap 'rm -rf "$RUNDIR"' EXIT`) and a space check before the heavy run. |

## OpenCode Review (opencode-referee-one), cycle 3

Using the plan-review checklist to check the current six plans against the source and the previous findings.
- **HIGH — The menu-integration commit leaves the earlier engine tracer’s one-artifact assertion unchanged.** Location: `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:146`, `.planning/phases/30-onboard-ghostty/30-02-PLAN.md:95,243-255`. Required: update the tracer and its runner for the menu step in the same commit, while retaining a meaningful receipt assertion. Why: the new behavior changes the receipt and invokes extraction, but 30-02 prohibits editing existing tests.
Correction: the earlier tracer uses a runner that does not extract the menu files, so the planned helper should report a menu warning and leave its one-artifact assertion intact. I am withdrawing that finding.
# Phase 30 plan review — convergence cycle 3

**Verdict: Issues found — revise before execution.** The revisions address several cycle 2 findings, including the shell-region conflict sweep, the conditional FUSE-device argument, the version exit-code check, and the skill-row occurrence count. Blocking issues remain in the locked drift contract, conflict scanning, the install tracer, and the container proof.

### Document Type

GSD · implementation plan

## 30-01

1. **Summary**  
   Adds the Ghostty catalog entry, loader keys and validation, community-build note, engine tracer, and digest-mismatch tests.

2. **Findings status**  
   The cycle 2 staged-comment concern is addressed with planned wording at `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:84,155`.

3. **Strengths**  
   The proposed raw-tarball route uses the existing digest-before-placement path: `installer/download.py:415-434` verifies the downloaded asset before replacing the raw binary. The new keys are added to the correct method sets, currently defined at `installer/model.py:69-95`.

4. **Concerns**
   - **HIGH — The method-order test calls a tarball-only URL helper on non-download methods.** `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:143` requires the same `pinned_url` comparison for *every* platform, including Arch’s pacman method and macOS’s cask method. `installer/download.py:167-175` requires a `url` parameter, which those methods do not have. The prescribed test therefore raises rather than proving ordering.
   - **MEDIUM — The desktop-ID rule and its threat claim disagree.** The pattern specified at `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:205` permits an ID such as `a..b`, while the threat register at `:246` says it rejects `..`. The fixed suffixes prevent that example from being a path traversal, but the documented validation claim is inaccurate.

5. **Suggestions**  
   Compare rendered URLs only for tarball methods; compare the relevant package or cask parameters for the other routes. Either reject consecutive dots or narrow the threat claim to the traversal forms actually refused.

6. **Risk Assessment**  
   High for execution: the prescribed ordering test cannot pass as written.

## 30-02

1. **Summary**  
   Adds AppImage menu extraction, receipt leaves, ownership checks, rollback, and uninstall handling.

2. **Findings status**  
   Cycle 2’s boundary and rollback concerns are substantially addressed: the revised plan includes path calculation and temporary-directory creation in the error boundary and describes rollback as best effort (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:34,199-202,210`).

3. **Strengths**  
   The tool’s own previous receipt is the replacement authority (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:35,191-192`), consistent with the receipt writer’s pre-existing-leaf safeguards in `installer/receipts.py:500-519`.

4. **Concerns**
   - **MEDIUM — The plan can replace a file that changes after its ownership and backup checks.** The helper checks existence and reads backups before calling `atomic_write_bytes` (`.planning/phases/30-onboard-ghostty/30-02-PLAN.md:210`). That function resolves a symlink at write time and replaces its target (`installer/atomic.py:36-52`). A file or symlink substituted between the check and write can therefore be overwritten despite not being the file checked. The planned symlink test covers extraction input, not this destination race.

5. **Suggestions**  
   Bind authorization to the destination identity at commit time, or use a safe no-follow/compare-before-commit approach appropriate to these leaves. Add a test that swaps the destination after the check and verifies that the user’s replacement remains untouched.

6. **Risk Assessment**  
   Medium: normal ownership and rollback paths are much better specified, but the promised user-file protection has a time-of-check/time-of-use gap.

## 30-03

1. **Summary**  
   Adds Ghostty config resolution, conflict scanning, the keys row, drift behavior, and multi-file stripping.

2. **Findings status**  
   The cycle 2 internal claim that a deleted region is both quiet and restored has been corrected in the plan (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:33,246-248`). The underlying locked-requirement conflict remains: the amendment is explicitly marked as needing confirmation.

3. **Strengths**  
   The plan scans both Linux files and all four macOS defaults, and refuses an unscannable earlier file (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:140-148,160-162`). Its recorded-deletion behavior matches the existing early returns in `installer/terminal_keys.py:350-361,386-397`.

4. **Concerns**
   - **HIGH — The SPEC still requires missing-region repair, while the plan forbids it.** The normative R4 statement says a “drifted or missing” region shows tuning and is reapplied (`.planning/phases/30-onboard-ghostty/30-SPEC.md:36-39`); its conflicting amendment is marked **needs confirmation**. The plan mandates the opposite for a recorded deletion (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:33,248`). This is a product-contract decision, not resolved merely by testing the shared mechanism’s current behavior.
   - **HIGH — The keys scan does not protect bindings in included files.** The parser records `config-file` but scans only the default files (`.planning/phases/30-onboard-ghostty/30-03-PLAN.md:119-120,159-162,211`). If an earlier default file includes a user binding and a later preferred default file receives the installer’s binding, the latter can override the included binding without a conflict report. The plan’s no-overwrite prohibition at `:71-73` is broader than the implemented scan. The accepted D-10 decision not to follow includes concerns the shell sync; it does not establish an exception to the keys prohibition.

5. **Suggestions**  
   Obtain confirmation of the R4 amendment before execution, then align the normative requirement and phase success criterion. For keys, explicitly handle includes that may load before the target—by scanning safely or declining the write with a named partial result—and test the earlier-include/later-target case.

6. **Risk Assessment**  
   High: one behavior remains unresolved at the contract level; another can override a user binding.

## 30-04

1. **Summary**  
   Adds Linux zsh shell sync, conflict and include reporting, dry-run behavior, and multi-file shell-region removal.

2. **Findings status**  
   The cycle 2 resolver-move concern is addressed for normal conflict and blocked-scan paths by the shared multi-file sweep (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:27,134-146`).

3. **Strengths**  
   The plan uses the existing absolute-path/control-character guard (`installer/terminal_shell.py:160-167`) and shell-quotes the command. It also preserves the generic uninstall dispatch in `installer/app.py:630-635`.

4. **Concerns**
   - **MEDIUM — A target-read failure skips the new multi-file cleanup.** The planned `_sync_ghostty` reads the currently resolved target before calling the scan and sweep, and its enclosing `except` returns immediately on `OSError` (`.planning/phases/30-onboard-ghostty/30-04-PLAN.md:143-144`). If the target becomes unreadable while an older owned shell region remains in another default file, the old region is not swept, even though the plan says a file that cannot be read is warned about and the walk continues. The shared settings reader can raise on unreadable or non-regular files (`installer/atomic.py:94-102`).

5. **Suggestions**  
   Make the non-target sweep independent of a target read or commit failure when the sync has determined that removal is needed; add a resolver-move test with an unreadable target and a readable old region.

6. **Risk Assessment**  
   Medium: the cycle 2 ordinary conflict case is covered, but an error path can still retain stale installer configuration.

## 30-05

1. **Summary**  
   Builds the container driver and harness verb; the orchestrator runs the real FUSE and extract-and-run checks.

2. **Findings status**  
   Cycle 2’s no-device startup route, positive mount observation, receipt-path HOME binding, and version exit-code checks now have explicit designs and tests (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:23-25,129-135,149`).

3. **Strengths**  
   The FUSE verdict now requires an observed mount rather than inferring one solely from successful output (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:24,164`). The target reuses exact-name teardown, whose existing implementation verifies container disappearance (`scripts/container-e2e-verify.sh:2745-2764`).

4. **Concerns**
   - **HIGH — Failed installs bypass the lifecycle cleanup.** The plan calls `install_one` *before* entering `run_lifecycle` and assumes that a failure means “nothing exists yet to clean” (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:162,167`). But `install_one` raises for any non-`INSTALLED` outcome (`tests/e2e_landing_driver.py:412-431`), and installation can have already placed artifacts before a later failure. Thus the promised always-run uninstall and residue diagnosis do not cover the installation failure path.
   - **HIGH — The removal verdict does not prove the stated set difference.** The planned verdict compares only the before- and after-uninstall listings and checks for newly remaining paths (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:143-146,165-167`). It does not capture the required *after-install* listing or verify that the removed set equals the receipt paths plus regions. A receipt path missing before uninstall, or unrelated pre-existing data removed during uninstall, can escape that comparison. SPEC R5 explicitly requires the after-install/after-uninstall difference (`.planning/phases/30-onboard-ghostty/30-SPEC.md:41-44`).
   - **MEDIUM — Region readback can pass despite failed Ghostty commands.** `_run_ghostty` returns an exit code, but the region verdict accepts only the two output strings (`.planning/phases/30-onboard-ghostty/30-05-PLAN.md:142,163,166-167`). A command that prints the expected line and exits nonzero can still produce `REGIONS_OK`.

5. **Suggestions**  
   Put install and all subsequent work under a cleanup boundary that diagnoses partial installs. Capture and compare before-install, after-install, and after-uninstall state, including preservation of seeded user content. Require zero exit status for both config-readback commands and test nonzero exits with matching output.

6. **Risk Assessment**  
   High: the phase’s evidence gate can miss a partial-install residue or report an incomplete removal proof as successful.

## 30-06

1. **Summary**  
   Gates evidence wording on the orchestrator’s recorded container result and adds catalog consistency tests.

2. **Findings status**  
   Cycle 2’s one-row occurrence-count problem is addressed with occurrence counts and per-cell checks (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:112-113,135-136`). The calendar-date validation is also specified at `:119-120`.

3. **Strengths**  
   The hard gate distinguishes a proven FUSE mount from an extract-only result before editing the evidence text (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:24-25,119-123`).

4. **Concerns**
   - **MEDIUM — The comment-size contracts remain inconsistent across plans.** Plan 30-01 requires its existing facts test to assert that the contiguous comment block is at most **40** lines (`.planning/phases/30-onboard-ghostty/30-01-PLAN.md:145`). Plan 30-06 allows that same block to grow to **55** lines and prohibits editing the existing test (`.planning/phases/30-onboard-ghostty/30-06-PLAN.md:28,76,91-92`). A paragraph that satisfies 30-06’s own limit can therefore fail the earlier test. This is avoidable by writing a sufficiently short block, but the plan does not require that outcome.

5. **Suggestions**  
   Carry the existing 40-line limit forward as the effective limit, or explicitly revise the earlier test and explain the changed contract.

6. **Risk Assessment**  
   Medium for execution; the evidence wording is additionally dependent on correcting 30-05’s proof.

## Cross-plan assessment

- **Ordering:** The current wave chain serializes 30-02 and 30-03, which both modify `installer/registry.toml` (`30-02-PLAN.md:6-15`; `30-03-PLAN.md:6-16`). The earlier overlap concern is addressed.
- **Scratch hygiene remains incomplete:** Each plan now requests an owned `TMPDIR`, but the rules only say to remove it when the plan finishes—for example, `.planning/phases/30-onboard-ghostty/30-01-PLAN.md:95`. They do not require the supplied mandatory cleanup on failure, timeout, or interruption, nor the pre-heavy-run space check. Add an exit/signal-safe wrapper and post-run cleanup verification.
- **Evidence dependency:** 30-06’s gate verifies the *recorded line’s shape*, not the underlying lifecycle itself. Its wording must not be published until the 30-05 issues are fixed and the real run supplies the required evidence.

### Status: Issues Found — fix and re-invoke

No files were changed and no scratch artifacts were created. I did not run tests, containers, upstream verification, or real Ghostty; live FUSE and hardware behavior remain unverified.
