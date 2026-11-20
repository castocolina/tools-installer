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
