---
phase: 33
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-21T16:40:00Z
plans_reviewed: [33-01-PLAN.md, 33-02-PLAN.md, 33-03-PLAN.md, 33-04-PLAN.md, 33-05-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 33

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 55bee65d)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 13:33 | opencode-referee-one | one-shot probe | OK |
| 13:33 to 13:37 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null` | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used. A read-only `gsd-plan-checker` pass ran beside it (1 blocker = the research open questions, fixed in `c73d921a`; 3 warnings; 3 info).

## Orchestrator verification of the cycle 1 concerns

Cycle 1 of 3. Plan-internal findings were checked against the cited plan lines; claims that rest on repository code (`installer/verify_registry.py` `passed_tools`, `_BumpResult`) are for the planner to verify against source and fix or reject with a stated reason in the Round 1 ledger. DECISIONS apply exactly; all are provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (33-01) | An applied bump can lack its `verified` edit: the date filter keeps tools from `report.passed_tools()`, which excludes a tool when another finding for it stays drifted or inconclusive although its version and hashes were applied | Real by the referee's reading (`installer/verify_registry.py:151-159,1120-1143,1201-1215`); planner verifies. DECISION: with the flag, `verified` is written for every tool with an applied bump (from the applied-bump results), never from `passed_tools()` alone, and a tool without an applied bump keeps no date edit; keep the rule that no date is written for a tool whose candidate did not verify. Add a regression with a second finding for the same tool that stays drifted. |
| M1 (33-01) | The file-order test uses one pinned method per tool, so per-method index ordering is not exercised | Real. Add a multi-method bump fixture (a tool with two pinned methods). |
| M2 (33-02) | Name checks prove structure, not the dispatched head or protection | Not a plan defect: BOT-02's live outcome stays an owner-gated item. DECISION: the plan and VERIFICATION wording report the structural tests as file-level evidence only and link BOT-02's status to the owner-run proof; never `passed`. |
| H2 (33-03) | The bot runs the dispatched ref's Python with a write token, so text scans of `run` steps cannot enforce "no bot token reaches main" | Judged ACCEPTED, with the boundary made explicit: only a user with write access can dispatch, and such a user can already push any unprotected branch; `main` rejects a direct push by the workflow token because its protection (strict required checks, enforce_admins) is enforced on tokens too. A static scan cannot prove a runtime boundary. DECISION: no code change; add a threat-model entry and a sentence in the workflow header comment and the issue body naming this boundary (dispatch is the owner's act; the protection is the control), and word the no-main test as a structural guard, not a proof. |
| H3 (33-03) | A successful push followed by a failed CI dispatch leaves an advertised branch without required CI and no recovery | Real. DECISION: the dispatch step retries once; a final step guarded like the other publishing steps (`failure()` and the guard output) comments on the tracking issue with the exact manual `gh workflow run ci.yml --ref <branch>` command; test it. |
| M3 (33-03) | The same-day rerun always makes a new commit and force-updates the ref, contradicting the SPEC edge row (an identical same-day rerun adds no second commit) | Real: the SPEC is locked, so the plan cannot call it discretion. DECISION: after the single-ref fetch, if the remote bot branch exists and its `installer/registry.toml` is byte-identical to the working copy's, the run skips the commit, the push and the dispatch (and says so); test the skip and the non-identical case. Supersedes research Q4's "simple" recommendation (provisional, needs confirmation). |
| M4 (33-03) | The issue number is extracted from the create output and used unchecked in `Closes #N` | Real. DECISION: validate it is a nonempty numeric string, else fail the step; test the failure path text. |
| M5 (33-03) | Deleting every other `bot/registry-*` ref can destroy a proposal the owner is reviewing | Accepted: D-05 is the owner-provisional design (one live branch; unlanded bumps reappear weekly from the same main). DECISION: no change; the issue body says older bot branches are replaced by the newest one. |
| H4 (33-04) | The runbook uses `git ls-remote` for the bot SHA, then pushes `bot/registry-$DATE` as a local source ref that was never fetched; the same-day rerun changes the bot head and the procedure does not wait for the second run and refresh the SHA | Real. DECISION: fetch the exact bot head into a named local ref after each run (explicit `+refs/heads/...:refs/remotes/...` refspec), use that SHA for every push, and wait for and inspect CI on the final head before the protection test; include the second same-day run (it must now skip, M3). |
| H5 (33-04) | Cleanup assumes deleting a protected branch removes its protection, with no explicit protection removal or recovery | Real. DECISION: explicit `gh api -X DELETE .../branches/<throwaway>/protection`, read-back that it is gone (404), then delete the branch; if the branch delete is refused the runbook says what to do (remove protection first, never touch `main`'s protection). |
| H6 (33-04) | The proof can overwrite and delete real bot work: the bot upserts the open `registry-bot` issue and deletes older bot branches, and the runbook closes the labelled issue | Real. DECISION: a preflight at the top of the runbook that STOPS when any `bot/registry-*` ref or open `registry-bot` issue already exists (and records nothing to undo), so the proof can only run in a clean namespace; the cleanup closes only the issue number the proof run created. |
| M6 (33-04) | Option B is described as the standing route without its own outcome check | Real. DECISION: Option B stays labelled UNVERIFIED (assumption A3) with the wait/check sequence it would need and no claim of success. |
| H7 (33-05) | The cron consistency test reads the cron from a commented block, so the documented follow-up (uncomment, flip the trigger test) makes the final test fail | Real. DECISION: the cron assertion accepts and compares both the disabled (commented) and the enabled form; the runbook's follow-up step names the one test edit and that this assertion needs none. |
| M7 (33-05) | The exact file-set gate is tied to a commit subject and a fixed count | Real (the checker's warning 2 too). DECISION: drop the subject-derived base and the exact-count gate; keep a presence check of the expected files and a clean-tree check. |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory | REJECTED, no plan change (the doctor test wraps its output by path length and failed under executor-owned long TMPDIRs); every scratch directory a plan creates is owned and trapped. |

## OpenCode Review (opencode-referee-one), cycle 1

Using the plan-review checklist to check each plan against the repository and its locked requirements.
# Phase 33 plan review

**Verdict: Issues found — revise and re-review before execution.** The main blockers are the proof procedure’s incomplete Git ref and cleanup handling, the bot’s ability to execute code from a dispatched ref with a write token, and gaps in the promised version/hash/date and rerun guarantees.

**Review basis:** GSD · plan archetype. I read all five plans from disk and grounded the review in the cited implementation, fixtures, workflows, tests, Makefile, and documentation. This is cycle 1; there is no previous cross-AI review disposition to verify.

## 33-01

**Summary.** Add `--bumps-only` at the shared edit builder, guard its use, and test date-only and real-bump cases.

**Findings status.** First review; no prior-cycle findings.

**Strengths.**
- The proposed guard precedes probe creation and network work, matching the existing candidate guard at `installer/verify_registry.py:1576-1594`.
- The edit filter is placed where applied bump edits and date edits meet (`installer/verify_registry.py:1330-1339`), and the existing bump builder requires a hash before emitting each version/hash pair (`installer/verify_registry.py:1188-1198`).

**Concerns.**
- **HIGH — An applied bump can still lack its `verified` edit.** `.planning/phases/33-registry-update-bot/33-01-PLAN.md:108` filters dates from `report.passed_tools()`, not from all applied bumps. A candidate is checked using a copy containing only pinned methods (`installer/verify_registry.py:1120-1143`), while finalization retains findings for other URLs (`installer/verify_registry.py:1201-1215`). If another finding for the same tool remains drifted or inconclusive, `passed_tools()` excludes it (`installer/verify_registry.py:151-159`) even though its version and hashes were applied. The proposed single-method fixture at `33-01-PLAN.md:140` does not cover that case.
- **MEDIUM — The file-order test does not exercise method-index ordering.** The proposed mixed fixture at `33-01-PLAN.md:141-148` has one pinned method per tool. It cannot prove the stated per-method behavior for a tool with multiple pinned methods, despite the method-index edit logic at `installer/verify_registry.py:1192-1197`.

**Suggestions.** Define the required behavior when a candidate passes but another finding for that tool fails; add a regression covering that case and a multi-method bump fixture. Preserve the existing no-unverified-date safety rule explicitly.

**Risk Assessment.** Medium-to-high: the ordinary fixture path is well grounded, but the stated three-field invariant is not established for mixed findings.

## 33-02

**Summary.** Add a bare CI dispatch trigger while retaining the existing job names, push filter, and concurrency group.

**Findings status.** First review; no prior-cycle findings.

**Strengths.**
- The plan preserves the actual CI job template, matrix, and concurrency configuration at `.github/workflows/ci.yml:9-22`.
- The two narrowly scoped test amendments correspond to the current exact assertions at `tests/test_ci_workflow.py:36-53`.

**Concerns.**
- **MEDIUM — Check-name tests do not prove the dispatched head or protection outcome.** `.planning/phases/33-registry-update-bot/33-02-PLAN.md:134-139` correctly checks YAML structure, but BOT-02 also requires a live proof, not merely matching names (`.planning/phases/33-registry-update-bot/33-SPEC.md:29-32`). This is carried forward to plan 04 and must remain an unresolved phase gate until the corrected proof runs.

**Suggestions.** Keep the structural tests, and report them as file-level evidence only; link the final BOT-02 status to the actual owner-run proof.

**Risk Assessment.** Low for the CI edit itself; the end-to-end requirement remains unverified.

## 33-03

**Summary.** Add a guarded, dispatch-only bot workflow with issue upsert, leased branch push, CI dispatch, and old-branch cleanup.

**Findings status.** First review; no prior-cycle findings.

**Strengths.**
- The permissions and cache layout follow the existing read-only drift workflow’s patterns while retaining its separate permissions (`.github/workflows/verify-registry.yml:13-15,30-35,50-55`).
- The planned explicit lease checks the fetched expected SHA and limits the destination to the dated bot ref (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:153-157`).

**Concerns.**
- **HIGH — Workflow text scans do not enforce the claimed no-main security boundary.** The bot checks out the selected dispatch ref and then executes that ref’s Python with `GH_TOKEN` and `contents: write` (`33-03-PLAN.md:149-154`); dispatch on an unrelated ref is expressly allowed (`33-03-PLAN.md:229-242`). Modified Python, dependencies, or workflow steps on that ref can use the token directly. Scanning only `run` strings for literal `main` (`33-03-PLAN.md:127,140-141,237`) cannot establish that “no bot token” reaches main. This also matters when the proof runs from a throwaway ref.
- **HIGH — A successful push followed by failed dispatch leaves an advertised branch without required CI.** Issue upsert precedes the push, and dispatch is a separate subsequent step (`33-03-PLAN.md:156-157,198-200`). A dispatch failure leaves the issue pointing at the pushed head, with no recovery or explicit failure annotation. The issue’s instruction to wait for green helps prevent an unsafe landing, but does not restore the promised automated checks.
- **MEDIUM — The same-day rerun contradicts the locked idempotency edge.** The workflow always creates a new commit and force-updates the ref when its input checkout still contains drift (`33-03-PLAN.md:156,198-199`). The spec explicitly says an identical same-day rerun adds no second commit (`.planning/phases/33-registry-update-bot/33-SPEC.md:91`); the plan instead defers quiet reruns at `33-03-PLAN.md:280-283`.
- **MEDIUM — Issue identity and failure cases are unchecked.** The create path extracts `${url##*/}` and immediately uses it in `Closes #$ISSUE_NUMBER` (`33-03-PLAN.md:198-199`), without checking that it is a nonempty numeric issue number. The proposed test at `33-03-PLAN.md:187-188` checks substrings, not failure behavior.
- **MEDIUM — Namespace deletion can destroy an existing live proposal.** The plan deliberately deletes *all* other matching remote refs after dispatch (`33-03-PLAN.md:189,200`), without checking their SHA or whether an owner is reviewing one. The namespace limit prevents deletion outside it, but does not establish ownership of every matching ref or protect against a concurrent ref replacement.

**Suggestions.** Make the permitted trust boundary explicit and enforce it, while retaining a safe proof mechanism; add failure/recovery behavior for a pushed-but-undispatched head; validate the issue number; and add behavioral checks for reruns and deletion races. Reconcile the identical-rerun behavior with the spec rather than calling it discretion.

**Risk Assessment.** High: this is the component with repository write authority, and static YAML string checks cannot prove its runtime safety or recovery.

## 33-04

**Summary.** Deliver an owner-run proof and cleanup runbook without executing remote writes during implementation.

**Findings status.** First review; no prior-cycle findings.

**Strengths.**
- The plan keeps remote writes with the owner and marks the temporary protection write for approval (`.planning/phases/33-registry-update-bot/33-04-PLAN.md:120,162-163`).
- The stale candidate is not assigned an invented hash; the existing candidate builder obtains or computes candidate hashes (`installer/verify_registry.py:1120-1141,1188-1198`).

**Concerns.**
- **HIGH — The proof pushes a bot ref that was never fetched locally.** The runbook reads the bot SHA with `git ls-remote` (`33-04-PLAN.md:123-124`), but Option A and Option B then use `bot/registry-$DATE` as a *local source ref* in `git push` (`33-04-PLAN.md:163`). `ls-remote` does not create that ref, so both commands can fail with a missing source ref. The same-day rerun also changes the bot head; the procedure does not wait for the second bot and CI runs, refresh `$SHA`, and verify checks on that final head before testing protection.
- **HIGH — Cleanup cannot assume deleting a protected branch removes its protection.** `33-04-PLAN.md:162-163` creates protection with no explicit deletion allowance, then directs deletion of the protected branch and expects the protection to disappear. The plan supplies no explicit protection-removal operation or recovery if the branch deletion is refused. Its text-only test at `33-04-PLAN.md:153-154` cannot establish successful cleanup.
- **HIGH — The proof can overwrite and delete real bot work.** The bot upserts the existing open labelled issue and removes older bot branches (`33-03-PLAN.md:198-200`); the runbook subsequently deletes the dated bot ref and closes the selected labelled issue (`33-04-PLAN.md:122-125`). There is no preflight requiring an empty namespace and no existing tracking issue, or preserving their prior state. Running the proof can therefore replace or close a real proposal.
- **MEDIUM — The fallback is described as proved without testing its final landing condition.** Option B says an owner push starts ordinary CI and makes that the standing route (`33-04-PLAN.md:163`), but supplies no wait/check sequence and no protected-target fast-forward for that new CI result. It must remain an unverified alternative until those outcomes are recorded.

**Suggestions.** Fetch the exact bot head after each run, wait for and inspect CI on that SHA, and use that SHA or a verified local ref for push attempts. Specify approved removal and read-back of temporary protection before branch cleanup. Add a preflight that stops rather than alters pre-existing bot refs or issues.

**Risk Assessment.** High: the current runbook may fail to prove BOT-02 and can affect existing remote work.

## 33-05

**Summary.** Add grouped weekly Dependabot configuration, documentation, and cross-file consistency checks.

**Findings status.** First review; no prior-cycle findings.

**Strengths.**
- The Dependabot parse test constrains the ecosystem, schedule, directory, and group (`.planning/phases/33-registry-update-bot/33-05-PLAN.md:111-118`).
- The planned docs-only boundary is grounded: `.github/*` and `docs/*` are already classified as test-read paths (`devtools/docs_only.py:18-35`), and the existing workflow guide records the protected fast-forward flow (`.claude/git-workflow.md:35-45`).

**Concerns.**
- **HIGH — The documented cron-enabling follow-up will break the final test.** The cross-file test requires extracting the cron from a *commented* block (`33-05-PLAN.md:178-179`). The runbook tells the owner to uncomment that block and update only the trigger-set test (`33-04-PLAN.md:165`). After the prescribed follow-up, the cron regex finds nothing, so the quality gate fails.
- **MEDIUM — The exact file-set gate is coupled to an ephemeral commit subject.** `33-05-PLAN.md:185-195` finds the baseline by a specific task commit and fails if it is absent or if any additional necessary file changes occur. This makes the phase gate brittle under legitimate history folding or a fix that requires another file, without testing the bot’s behavior.

**Suggestions.** Make the cron consistency assertion accept and compare both disabled and enabled forms, and include it in the follow-up’s verification instructions. Use a recorded phase baseline and report unexpected files for review rather than tying correctness to a commit subject and a fixed count.

**Risk Assessment.** Medium: the configuration is small, but the prescribed rollout cannot pass the planned final test unchanged.

## Cross-plan assessment

- **Completion must remain blocked on the live proof.** The spec requires proof before the phase is done (`.planning/phases/33-registry-update-bot/33-SPEC.md:29-32`). The dispatch-only rollout and owner-run checkpoint are valid staging decisions, but `human_needed`, a runbook, or green file tests are not evidence that BOT-02 has passed. Likewise, the scheduled behavior remains disabled until the follow-up is completed.
- **Scratch cleanup instructions conflict with the mandatory host rule.** Each plan instructs full `make validate` and `make test` runs with the default `TMPDIR`, for example `33-01-PLAN.md:65`; the session’s mandatory rule requires an owned temporary directory exported to children and cleaned on every exit. The long-path test constraint needs a short, owned `TMPDIR` solution rather than dropping isolation.
- **Verification scope.** No tests, containers, GitHub operations, or remote writes were run during this review; the proposed workflow and runbook do not yet exist to exercise. No scratch artifacts were created.
