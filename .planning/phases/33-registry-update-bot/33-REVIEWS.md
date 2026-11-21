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


## Lane Log (convergence cycle 2, plans at 2528bb05)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 13:59 | opencode-referee-one | one-shot probe | OK |
| 13:59 to 14:03 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

Cycle 2 of 3. Real HIGH by cycle: 6, now 5 (second-order gaps in the round 1 fixes). Plan-internal findings were checked against the cited plan lines; claims that rest on repository code (`installer/verify_registry.py` candidate validation) are for the planner to verify. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (33-03) | Identical registry bytes do not prove the existing proposal is usable: if `main` advances without changing `registry.toml` the bot branch keeps an old base and cannot be fast-forwarded; the skip also prevents a rerun from dispatching CI after a push that succeeded but a dispatch that failed | Real (`.claude/git-workflow.md:40-45`). DECISION: skip only when BOTH the bot branch's registry content is byte-identical AND its parent equals the run ref's current HEAD; an identical file on an old base counts as changed (new commit on the new base, force-update with the lease). On a skip, still dispatch CI when `gh run list --workflow ci.yml --branch <bot> --json headSha` shows no run for that head SHA (no commit, no push, no issue edit). Test both texts. |
| H2 (33-03) | The claimed runtime no-main control is overstated: the plan says default-branch protection keeps the bot off `main`, but CONTEXT records that a `contents: write` token can fast-forward an already-green commit to `main` (no push restrictions) | Real wording defect (`33-CONTEXT.md:83-86`). DECISION: no claim that protection stops the token. The accurate statement everywhere (workflow header, issue body, threat T-33-11, runbook): the workflow contains no step that targets `main` (a structural guard, tested); the token itself could push an already-green commit to `main` because the repository has no push restrictions; the control is that only a user with write access can dispatch, and a dispatched ref runs its own code, so dispatch is the owner's act. The owner may close the gap with a push restriction (a repository setting, outside this phase): list it as an owner follow-up item in the deferred verification and backlog. No requirement amendment; BOT-03's acceptance is the structural one in the SPEC. |
| M1 (33-03) | Old-branch deletion by name without an expected SHA can remove a ref changed after enumeration | Real, cheap. DECISION: enumerate with `git ls-remote --heads` and delete each with `--force-with-lease=<ref>:<sha>`; a rejected deletion is reported and skipped. |
| M2 (33-03) | The issue is edited before the lease-protected push, so a failed push leaves it advertising a branch | Real. DECISION: the failure-report step covers a failed push as well as a failed dispatch (a comment on the issue naming the failed stage and the manual command); the issue upsert stays first (D-08: the commit carries the closing keyword). |
| M3 (33-03) | `git fetch ... \|\| true` hides network and authentication errors as an absent branch | Real. DECISION: probe with `git ls-remote --heads origin <ref>` first (its failure fails the step; empty output means absent), fetch only when present, no `\|\| true` on the fetch itself; test the text. |
| H3 (33-04) | The stale-pin command `--candidate drawio-desktop=32.6.1` is rejected by the verifier: a candidate older than the latest release gets its own drift finding and `_plan_bumps` refuses any non-OK candidate | Real by the referee's reading (`installer/verify_registry.py:294-330,1298-1314`); planner verifies. DECISION: drop the stale fixture and the proof ref entirely. The proof relies on the real drift that exists on the default branch (today draw.io 32.6.10 against 32.7.4); the runbook's first stage dispatches the bot on the default branch itself. If no bot branch appears, there was no drift: the runbook says STOP, nothing proved, retry when drift exists (never a pass). |
| H4 (33-04) | The pushed proof ref can create the false-positive CI evidence the proof must exclude | Resolved by H3's DECISION (no proof ref is pushed). Add explicit identification: the bot-created SHA, its parent equals the default branch's tip, the CI run's event is `workflow_dispatch` and its head is that SHA, and STOP on any push-event check run for that SHA. |
| M4 (33-04) | After UTC midnight the bot computes a different branch name, so the second run does not exercise the same-day skip | Real. DECISION: the runbook stops and restarts the proof when the UTC date changes between the two runs (no `DATE` reset). |
| M5 (33-04) | A recorded owner decision is allowed to make BOT-02 read `passed` | Real. DECISION: `passed` only for demonstrated behavior (dispatched checks reported on the head and the fast-forward of that head accepted); a decision to use Option B or to investigate keeps BOT-02 `human_needed` or `blocked`, never `passed`. |
| H5 (33-05) | The clean-tree recovery tells the executor to commit or remove any modified or untracked file outside `.planning`, which can destroy unrelated user work | Real. DECISION: assert only, never alter: check the expected files are tracked and that none of the phase's own files is dirty; any unrelated modified or untracked file is REPORTED and left alone. |
| M6 (33-05) | The documented landing command pushes `bot/registry-<date>:main` using a possibly missing or stale local ref | Real. DECISION: the documented landing steps fetch the exact remote head, record its SHA, verify the checks for that SHA, then push that SHA (`git push origin "$SHA:refs/heads/main"`), never a branch name. |
| L1 (33-05) | The consistency test extracts every `gh workflow run (\S+)` from the whole runbook and scripts, including prose | Constrain the extraction to the fenced command examples and the workflow `run:` text; test it. |
| M7 (33-01) | A bumped tool is marked verified despite a known failing method elsewhere; the `verified` meaning differs between flagged and unflagged runs; the stated "the flag only narrows the edit set" is false | SPEC-driven (criterion 1: version, sha256 and verified change together), so the behavior stays (cycle 1 H1). DECISION: correct the statement (the flag keeps the bump edits and adds the date of a bumped tool even when a neighbour method is still drifted) in the threat entry, the docs and the issue-body sentence; document that after a bump `verified` certifies the bumped pins, while findings on other methods still appear in the drift report. Provisional, needs confirmation. |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory | REJECTED again (the doctor test wraps its output by path length and failed under executor-owned long TMPDIRs); ruling stays in the 33-01 ledger. |

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist to verify the revised plans against the source and the previous findings.
# Phase 33 plan review — convergence cycle 2

### Document Type

GSD · implementation plans

### Status: Issues Found — revise and re-review

The revised plans address several first-cycle findings, notably the applied-bump date regression, explicit proof-head fetch, protection cleanup, and two-form cron test. **Execution should still wait:** the prescribed proof cannot reliably create its stale candidate, and the bot’s identical-content shortcut can strand a proposal without CI or on an obsolete base.

## 33-01

**Summary.** Add `--bumps-only`, retain applied version/hash edits, date bumped tools, and cover the flag with offline fixtures.

**Findings status.** The prior HIGH finding about a bumped tool missing its date and the multi-method coverage finding are addressed in the proposed design and tests.

**Strengths.**
- The revised selection uses applied bump results, consistent with `_BumpResult` and `_build_bump_edits` in `installer/verify_registry.py:1176-1198`. The `combo` regression exercises the surviving drift finding at `tests/test_verify_registry.py:3345-3411`.
- The guard is placed before probe construction and network work, alongside the existing candidate guard at `installer/verify_registry.py:1576-1594`.

**Concerns.**
- **MEDIUM — A bumped tool can be marked verified despite a known failing method.** `33-01-PLAN.md:111` dates every applied bump, including the deliberately drifted `combo` case at `33-01-PLAN.md:180`. The existing report considers a tool passing only when all its findings pass, and its current unflagged test deliberately retains the old date (`tests/test_verify_registry.py:3405-3411`). This makes the tool-level `verified` field mean different things depending on the flag and can conceal the known failure. The plan acknowledges the divergence but does not reconcile it with the existing whole-tool verification semantics.
- **MEDIUM — The plan’s stated trust boundary is false.** `33-01-PLAN.md:214-216` says the flag only narrows the edit set; the new `combo` behavior adds a date that the unflagged path does not produce (`installer/verify_registry.py:1330-1339`). The threat model and documentation should not claim narrowing.

**Suggestions.** Define and document whether `verified` certifies the whole tool or only the pinned candidate. If it remains whole-tool certification, do not publish a bump as a three-field change while another finding fails; test the chosen behavior.

**Risk Assessment.** Medium: the edit mechanics are well grounded, but the meaning of a persisted catalog field changes.

## 33-02

**Summary.** Add bare `workflow_dispatch` to CI, preserve its push configuration and check names, and add structural contract tests.

**Findings status.** The prior concern is addressed: the plan now explicitly separates file-level evidence from the live BOT-02 proof (`33-02-PLAN.md:23-28,183-191`).

**Strengths.**
- The proposed change matches the existing trigger, matrix, job name and concurrency configuration in `.github/workflows/ci.yml:3-22`.
- The two named assertion amendments correspond to the existing checks in `tests/test_ci_workflow.py:36-53`.

**Concerns.**
- No new plan-specific blocking concern found. The live dispatch and protection result remains unresolved, not established by these tests.

**Suggestions.** Retain the explicit `human_needed` status until the corrected live proof succeeds.

**Risk Assessment.** Low for the YAML edit; BOT-02 remains dependent on the live proof.

## 33-03

**Summary.** Add a dispatch-only bot that verifies pins, compares the proposed registry with the dated branch, upserts an issue, pushes with an explicit lease, dispatches CI, and deletes older bot refs.

**Findings status.**
- Numeric issue validation is addressed (`33-03-PLAN.md:196-209`).
- Dispatch retry and issue annotation improve the previous failure path, but do not provide reliable automatic recovery.
- Identical-registry reruns now skip publication, but the comparison is too narrow.
- The prior no-main security concern and deletion risk are documented as accepted; documentation does not itself enforce the stronger claims.

**Strengths.**
- The planned exact permissions match D-07, while the existing drift workflow remains read-only for contents (`33-03-PLAN.md:153-158`; `.github/workflows/verify-registry.yml:13-15`).
- The explicit expected-SHA lease protects the current dated ref from a concurrent replacement between fetch and push (`33-03-PLAN.md:162-164`).

**Concerns.**
- **HIGH — Identical registry bytes do not prove the existing proposal is usable.** `33-03-PLAN.md:162-164` skips the issue, push, and CI dispatch solely when `registry.toml` matches. If `main` advances without changing that file, the bot branch remains based on the old commit and cannot be fast-forwarded to the new `main`; the repository requires updating and retesting an out-of-date branch (`.claude/git-workflow.md:40-45`). The same skip also prevents a rerun from dispatching CI after the previous push succeeded but dispatch failed (`33-03-PLAN.md:208-211`). The issue comment helps only if it succeeds and a person acts on it.
- **HIGH — The claimed runtime no-main control is overstated.** The plan says default-branch protection “keeps this bot off” main (`33-03-PLAN.md:153,243,256`), but the phase context explicitly records that a token with `contents: write` can fast-forward an already-green commit to main because there are no push restrictions (`33-CONTEXT.md:83-86`). A dispatched ref’s own code receives the write-capable job token (`33-03-PLAN.md:242-243`). Required checks limit *which* commit can land; they do not prove that the token cannot push. This remains a gap against the absolute prohibition in `33-SPEC.md:34-37`.
- **MEDIUM — Old-branch deletion can remove a ref changed after enumeration.** The plan enumerates refs then deletes them by name without an expected SHA (`33-03-PLAN.md:199,211`). Accepting replacement of older proposals does not protect a concurrently updated ref from deletion. The current-branch lease does not apply to deletions.
- **MEDIUM — The issue can advertise a branch before a failed push.** The issue is edited or created before the lease-protected push (`33-03-PLAN.md:208-209`). If the lease rejects or the push fails, the issue names a branch that may not exist or may still contain a different head; the failure-report step only handles dispatch failure (`33-03-PLAN.md:210`).
- **MEDIUM — Fetch errors are indistinguishable from an absent branch.** The prescribed `git fetch ... || true` suppresses authentication, network, and server errors as well as a missing ref (`33-03-PLAN.md:162`). A subsequent empty expected SHA generally makes a push to an existing ref fail safely, but the run can already have updated the tracking issue. Fail closed on unexpected fetch errors.

**Suggestions.** Compare both the proposed content **and base/head validity**, and recover missing CI independently of whether a new commit is needed. Report push as well as dispatch failures. Use expected-SHA deletion or stop on changed refs. Correct the security statement and establish a control that actually meets BOT-03, or explicitly obtain an amendment to the absolute requirement.

**Risk Assessment.** High: this workflow has repository write authority, and static YAML scans cannot establish the runtime guarantees.

## 33-04

**Summary.** Provide an owner-run proof runbook with preflight, exact bot-head fetching, a temporary protected target, cleanup, and a later cron-enabling step.

**Findings status.** The previous missing-local-ref, explicit protection-removal, preflight, and unverified-fallback concerns are materially addressed in the plan. New blockers remain in the prescribed proof itself.

**Strengths.**
- Fetching the bot head and using its SHA addresses the former missing-local-ref problem (`33-04-PLAN.md:130-131,164`).
- The preflight and recorded issue number reduce the risk of closing an existing proposal; protection removal is specified before deleting the protected target (`33-04-PLAN.md:120-121,173`).

**Concerns.**
- **HIGH — The prescribed stale-pin command is rejected by the verifier.** The runbook is to run `--candidate drawio-desktop=32.6.1` while a newer stable release exists (`33-04-PLAN.md:97,130`). Candidate validation runs `check_registry` on the candidate (`installer/verify_registry.py:1298-1304`), which independently creates a drift finding when its pin is older than the latest release (`installer/verify_registry.py:294-330`). `_plan_bumps` then refuses a candidate with any non-OK finding (`installer/verify_registry.py:1302-1314`). Consequently the command does not reliably create the stale registry commit that the proof needs.
- **HIGH — The proof’s ref can create the very false-positive CI evidence it is meant to exclude.** The owner pushes `proof/registry-bot-$DATE` before the bot runs (`33-04-PLAN.md:130`), and existing CI runs on all branch pushes except `main` (`.github/workflows/ci.yml:3-7`). The bot’s new commit is distinct when it successfully bumps, but if stale-pin setup is skipped or fails, the runbook does not require proving the expected changed parent and bot commit before proceeding. The test should explicitly identify the bot-created SHA, parent and dispatch run, and stop on any unexpected push-event check for that SHA.
- **MEDIUM — Midnight handling is not sufficient.** `33-04-PLAN.md:128` tells the owner to reset `DATE` to the existing branch date after UTC midnight, but the bot independently computes its branch name at each run (`33-03-PLAN.md:159`). A second run after midnight creates a different branch instead of exercising the same-day skip. Stop and restart the proof if the UTC date changes.
- **MEDIUM — “Recorded owner decision” is not itself proof of BOT-02.** `33-04-PLAN.md:175` allows `passed` after a recorded owner decision, even though `33-SPEC.md:29-32` requires a successful dispatch/protection proof or a stop for a token-route choice. A decision to investigate or use an unverified fallback must not make the original requirement pass.

**Suggestions.** Construct the stale fixture using real, independently verified historical pins without asking the current candidate verifier to accept an outdated candidate; verify the actual registry diff before pushing. Require exact event, SHA, ancestry and check evidence, fail safely across midnight, and reserve `passed` for demonstrated behavior or an explicitly amended requirement.

**Risk Assessment.** High: the current runbook can fail before the intended proof and could misclassify its result.

## 33-05

**Summary.** Add grouped weekly Dependabot configuration, owner documentation, cross-file consistency tests, and final gates.

**Findings status.** The previous cron-follow-up concern is addressed by a helper designed for both forms (`33-05-PLAN.md:180-184`). The subject-derived baseline is removed, although the replacement clean-tree instruction has its own safety problem.

**Strengths.**
- The proposed parse test constrains the single ecosystem, schedule, directory and group (`33-05-PLAN.md:113-120`).
- The docs-only classification is grounded in `devtools/docs_only.py:18-35`; the existing workflow guide requires green checks on the exact fast-forwarded commit (`.claude/git-workflow.md:35-45`).

**Concerns.**
- **HIGH — The clean-tree recovery can destroy unrelated user work.** `33-05-PLAN.md:190,198-199` tells the executor to commit or remove *any* modified or untracked file outside `.planning`. That can include pre-existing or concurrent user work unrelated to this phase. A clean-tree assertion does not establish ownership of a file.
- **MEDIUM — The documented landing command can use the wrong local ref.** `33-05-PLAN.md:151` says to fetch the bot branch and then push `bot/registry-<date>:main`. An ordinary fetch normally creates or updates a remote-tracking ref, not necessarily a local branch named `bot/registry-<date>`; a stale local branch of that name could also select the wrong commit. This repeats the source-ref issue fixed in the proof plan. Use a fetched, verified SHA or explicitly created and verified local ref.
- **LOW — The phase-end consistency test captures command-like prose as well as commands.** `33-05-PLAN.md:183` extracts every `gh workflow run (\S+)` from the entire runbook and bot scripts. Keep explanatory examples and the failed-dispatch issue body within that contract, or constrain extraction to actual command examples.

**Suggestions.** Record a baseline and report unrelated work without altering it. Make landing instructions fetch and verify the exact remote head, verify checks for that SHA, then push that SHA.

**Risk Assessment.** Medium-to-high: the configuration is small, but the cleanup instruction risks user data and the landing guidance can select an unintended source ref.

## Cross-plan assessment

1. **Phase completion remains blocked.** The live proof and cron enablement are deferred (`33-04-PLAN.md:57-60`; `33-05-PLAN.md:231-240`). That staging is consistent with the chosen rollout, but it is not completion of the live acceptance criterion in `33-SPEC.md:29-32`.
2. **Mandatory scratch isolation remains unresolved.** All five plans prescribe default `TMPDIR` for full gates, for example `33-01-PLAN.md:68`, despite the session’s mandatory owned-directory and cleanup rule. The known path-length-sensitive test explains why a *long* path fails; it does not authorize unowned scratch space. Use a sufficiently short owned directory, or fix the path-sensitive test without weakening its assertion.
3. **The new tests predominantly inspect text.** They can establish wiring conventions, but cannot establish shell error handling, race behavior, or live GitHub protection. The runbook correctly carries some live work forward, but the failure cases above need executable regression coverage or an explicit, safe owner verification procedure.

**Not checked:** No tests, containers, GitHub operations, or remote writes were run; no scratch files were created. GitHub protection behavior remains a live-proof risk, not an established result.


## Lane Log (convergence cycle 3, plans at 861b70cc)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 14:57 | opencode-referee-one | one-shot probe | OK |
| 14:57 to 15:03 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 3 concerns

Cycle 3 of 3: the cap. Real HIGH by cycle: 6, 5, now 5 distinct (second-order gaps in the previous round's fixes; two are plan-internal contradictions between a plan's workflow text and its own tests). The count is no longer falling: under the owner's cap rule this is the LAST revision and the run executes right after it, with no cycle 4; whatever the review gates find afterwards goes to the post-execution fix round. Plan-internal findings were checked against the cited lines; claims about Git behavior and the repository's push gate are for the planner to verify. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (33-03) | The workflow text and its own tests contradict each other: the compare test wants the FIRST `expected=` after the fetch but the script initializes it earlier; the issue test bans apostrophes though the required `jq` filter is single-quoted (the drift workflow uses the same idiom); another test bans the word `token` in every run block though the required issue body says `write token` | Real plan-internal contradictions. DECISION: align the tests to the workflow, never the reverse: match the actual fetch assignment, allow single-quoted `jq` filters, and replace the `token` word ban by a credential-exposure test (no `secrets.` reference in a run block, no echo or print of `GH_TOKEN`, no `set -x`); ordinary security prose in the issue body stays. |
| H2 (33-03) | `git ls-remote` patterns match ref tails at slash boundaries, so filtering by `refs/heads/bot/registry-*` does not prove each returned full ref starts with that prefix; a failed listing in a pipe can look like an empty cleanup | Real by the referee's reading of `git-ls-remote(1)`; planner verifies. DECISION: after listing, accept a ref only when its full name starts with exactly `refs/heads/bot/registry-` (a shell `case`), capture the listing without a pipe so its failure fails the step (and set `pipefail`), exclude the current branch, delete with the expected-SHA lease. |
| M1 (33-03) | After a push that succeeded but a dispatch that failed, an identical rerun can redispatch CI but deletion still needs `same != 'true'`, so the one-branch policy is not restored; the redispatch treats any run for the SHA, even failed or cancelled, as enough | Real. DECISION: cleanup runs after a successful publish OR a successful redispatch; the redispatch counts only a queued, in-progress or successful run for the head (a failed or cancelled run triggers a new dispatch); test the texts. |
| M2 (33-03) | The changed-file guard maps every nonzero `git diff --quiet` result to "changed", so a Git error fails open | Real. DECISION: capture the exit code: 0 means unchanged, 1 means changed, anything else fails the step; test the text. |
| H3 (33-04) | The repository's push gate rejects any pushed commit other than the current `HEAD` (`devtools/push_gate.py:226-237`); Option A pushes `BASE` then `SHA` and Option B pushes `SHA`, but the runbook only fetches them | Real by the referee's reading; planner verifies. DECISION: every push of the runbook is made from a clean scratch worktree created with `git worktree add --detach <dir> <sha>` at exactly the commit being pushed (so `HEAD` is that commit), removed afterwards; never bypass the hook or the gate. |
| H4 (33-04) | STOP paths can leave the proof's own work behind: a run crossing midnight after the pre-dispatch check creates a branch the runbook never looks up; a failed publish leaves an issue but no branch; Part 1 stops before `ISSUE` is captured, so cleanup misses it and the next preflight blocks | Real. DECISION: the preflight proves the namespace empty (no `bot/registry-*` ref, no open `registry-bot` issue), so cleanup removes whatever now exists in exactly that namespace without needing recorded names: every `bot/registry-*` ref (full-prefix check, expected-SHA lease from a fresh listing) and the open `registry-bot` issues present at cleanup were created by the proof, and the runbook says so; rollover and failed-publish leftovers are covered the same way. |
| M3 (33-04) | The proof does not bind evidence to the dispatched run: `--limit 1` and `gh run watch` without an ID; "every run" without a nonempty result; and Option A's push triggers ordinary CI on the target ref, so the dispatch-only evidence must be captured before it | Real. DECISION: capture the dispatched run's id from `gh run list --workflow ci.yml --branch <bot> --json databaseId,headSha,event` filtered by head SHA and event `workflow_dispatch`, require it nonempty, watch it by id, record its two job results (both success) and the protection read-back BEFORE Option A's final push. |
| H5 (33-05) | The documented landing command fetches a remote-tracking ref and pushes its SHA, but the push gate rejects a SHA that is not the checked-out `HEAD`; the guide must also verify the two named checks, not list a run | Real. DECISION: the landing text creates a clean worktree detached at the fetched SHA, verifies BOTH required check names concluded `success` on that SHA (through the check-runs of that commit), then pushes `HEAD:refs/heads/main` from that worktree. |
| M4 (33-05) | The mutation exercise restores with `git checkout -- <path>`, which resets the tracked test file to the index and discards the uncommitted new tests; a dirty planned path is not proof of executor ownership | Real. DECISION: save the temporary mutation as a patch under the owned scratch directory and reverse exactly it with `git apply -R`; the new tests stay. Treat an unexpected edit to ANY path (planned or not) as user-owned: report it, never commit it. |
| M5 (33-01) | A same-version, same-digest candidate can produce a date-only diff because the filter equates "applied" with a real bump | Real. DECISION: exclude a no-op candidate (version and digest equal to the current) from the flagged date set; add the regression. |
| M6 (33-01) | The canonical registry guide still describes whole-entry verification (`.claude/architecture.md:226-230`) while the flag refreshes `verified` for a bumped tool whose neighbour still fails | Document the pin-only exception in the architecture guide as well as the help text, tracking issue body and README. |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory; `make validate` does not lint inline Actions scripts | X REJECTED a third time (the doctor test wraps its output by path length); the actionlint run stays an orchestrator-run phase-gate step recorded as "not run" if unavailable. |

## OpenCode Review (opencode-referee-one), cycle 3

Using the plan-review checklist and ponytail review to verify all five plans against the repository. I’ll use Codebase Memory to trace the verifier and check the proposed README guidance against the existing workflow. This is a read-only review.
Two blockers are clear from the prescribed commands: plan 33-03 requires issue text that its own workflow test rejects, and plan 33-04 can stop before recording the branch or issue it needs to clean up.
# Phase 33 plan review — convergence cycle 3

### Document Type
GSD · implementation plans

### Status: Issues Found — revise and re-review

The revisions fix several cycle-2 problems, including comparing the bot branch’s parent, using leases for branch deletion, and fetching the exact SHA before landing. **Do not execute the phase as written.** The workflow and its tests contradict each other, branch deletion is not confined to the claimed namespace, and the proof and landing instructions can be rejected by the repository’s own push gate.

## 33-01

**Summary.** Add `--bumps-only` at the registry edit boundary, preserving the unflagged path and testing both with offline fixtures.

**Findings status.** The applied-bump date fix and multi-method coverage are retained. The plan now accurately says the flag can add a date that the unflagged path would not write. The persisted meaning of that date still needs one documentation correction.

**Strengths.** Keeping the filter in the edit builder preserves the existing per-method version/hash pairing and the single write. Deriving dates from applied candidates also covers the case where an unpinned method still reports drift (`.planning/phases/33-registry-update-bot/33-01-PLAN.md:113–116,184–186`; `installer/verify_registry.py:1188–1216,1598–1613`; `tests/test_verify_registry.py:3405–3411`).

**Concerns.**
1. **MEDIUM — An explicit same-version candidate can still produce a date-only diff.** The filter at `.planning/phases/33-registry-update-bot/33-01-PLAN.md:113` equates `applied` with a real bump. The verifier accepts an explicit candidate without checking whether it equals the current version, and builds version/hash edits even when both values already match (`installer/verify_registry.py:1188–1198,1268–1272,1298–1326`). A passing same-version, same-digest candidate with an old date can therefore change only `verified`. Auto-discovery checks for a newer tag, so this gap affects the CLI contract rather than the bot’s normal discovery path (`installer/verify_registry.py:315–330`).
2. **MEDIUM — The canonical registry guide still describes whole-entry verification.** The new CLI help documents pin-only certification (`.planning/phases/33-registry-update-bot/33-01-PLAN.md:156`), but `.claude/architecture.md:226–230` says a verification run refreshes the field when the entry passes. The planned `combo` behavior intentionally refreshes it when another method still fails.

**Suggestions.** Add a same-version, same-digest regression and exclude no-op candidates from the flagged date set. Keep the chosen pin-only behavior, but document the exception in the canonical registry guide as well as the CLI help and README.

**Risk Assessment.** Medium for the public flag contract; low for the edit mechanics and normal automatic bumps.

## 33-02

**Summary.** Add bare `workflow_dispatch` to CI, preserve the two required check names, and relax only the checkout version lookup.

**Findings status.** The previous concern is addressed: file-level evidence is explicitly separated from live BOT-02 proof (`.planning/phases/33-registry-update-bot/33-02-PLAN.md:183–191`).

**Strengths.** The trigger and checkout edits match the two existing assertions, while retaining the push filter and full-history checkout. The added tests preserve the existing job and matrix names and the per-ref concurrency group. The separate loader is appropriate because the drift test’s loader is hard-wired to its own file (`.planning/phases/33-registry-update-bot/33-02-PLAN.md:102–110,130–145`; `.github/workflows/ci.yml:5–27`; `tests/test_ci_workflow.py:36–53`; `tests/test_verify_registry_workflow.py:13–23`).

**Concerns.** No new blocker. The generated names are an assertion about workflow structure, not proof that GitHub attached those checks to the bot’s SHA or accepted them under protection (`.planning/phases/33-registry-update-bot/33-02-PLAN.md:139–140,183–191`; `.planning/phases/33-registry-update-bot/33-SPEC.md:29–32`).

**Suggestions.** Keep this plan narrow and retain `human_needed` for the live result.

**Risk Assessment.** Low for the change; live dispatch acceptance remains unverified.

## 33-03

**Summary.** Add the dispatch-only bot, its guarded publication path, CI dispatch and recovery, issue tracking, and old-branch cleanup.

**Findings status.** The stale-base comparison and suppressed-fetch-error findings are addressed in design. The plan adds expected-SHA deletion and failure reporting, but neither fully closes the underlying failure paths. The no-`main` wording is more accurate, although dispatch authorization is still overstated.

**Strengths.** The direct `uv` command preserves the verifier’s exit categories instead of routing them through `make`. The remote probe distinguishes “absent” from a failed lookup, and the push is tied to the fetched SHA. The shared cache and unchanged read-only drift permissions match the existing workflow (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:149–159`; `Makefile:27–28`; `installer/verify_registry.py:1506–1514`; `.github/workflows/verify-registry.yml:13–15,30–35,50–55`).

**Concerns.**
1. **HIGH — The prescribed workflow cannot pass its own tests.** The compare test requires the *first* `expected=` to follow the fetch, but the script initializes `expected=` before the probe. The issue test bans apostrophes while the prescribed `jq` filter uses them; another test bans the word `token` in every run block while the required issue body contains `write token` (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:125,136,156,193,197,205`). The existing drift workflow uses the same legitimate single-quoted `jq` idiom (`.github/workflows/verify-registry.yml:45–48`).
2. **HIGH — Leases protect the listed SHA, not the deletion namespace.** Git’s `ls-remote` patterns match ref *tails* at slash boundaries. Filtering the listing with `refs/heads/bot/registry-*` is therefore not equivalent to checking that each returned full ref starts with that prefix. The loop excludes only the current branch before passing the returned ref to `git push --delete`. Under the planned default `bash -e` without `pipefail`, a failed listing can also appear as a successful empty cleanup (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:109,196,208`; local `git-ls-remote(1)`, `<patterns>`).
3. **MEDIUM — A failed dispatch can leave stale branches indefinitely.** If the new push succeeds and dispatch fails, cleanup is skipped. On an identical rerun, `redispatch` can start CI successfully, but deletion still requires `same != 'true'`, so the successful recovery does not restore the one-branch policy. Separately, the recovery treats any run with the SHA, including a failed or cancelled run, as sufficient and provides no recovery guidance in that case (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:158–159,207–208`; `.planning/phases/33-registry-update-bot/33-CONTEXT.md:32`).
4. **MEDIUM — The changed-file guard fails open on a Git error.** The prescribed `if git diff --quiet …; then … else changed=true` maps every nonzero result to “changed.” Bash does not stop on a failed `if` condition, so an error can reach the issue step as if the verifier produced a real diff (`.planning/phases/33-registry-update-bot/33-03-PLAN.md:155,205`). That conflicts with the guarded-publication contract (`.planning/phases/33-registry-update-bot/33-SPEC.md:24–27`).

**Suggestions.** Match the actual fetch assignment in the order test, and test for credential exposure rather than banning ordinary security prose or valid shell quotes. Check the full ref prefix before deletion, capture listing failure separately, and allow cleanup after successful CI recovery. Separate diff exit `1` from errors. Keep the no-`main` test as a structural guard; describe owner-only dispatch as an operating rule, not an enforced permission.

**Risk Assessment.** High. The tests as specified block execution, and the deletion flaw affects repository refs even at the intended single-owner, weekly-run scale.

## 33-04

**Summary.** Deliver an owner-run, post-landing proof using real drift and a temporary protected target; keep the cron disabled until the proof passes.

**Findings status.** The rejected stale-candidate recipe is gone. The revised proof identifies the bot commit, rejects push-event CI as evidence, and no longer lets an owner decision count as a pass. The midnight and cleanup fixes are incomplete, and the proof push instructions miss a local prerequisite.

**Strengths.** Using real drift avoids the verifier’s deliberate rejection of an outdated candidate. The parent, author, and changed-file checks improve attribution, and Option A explicitly requires approval before changing temporary protection (`.planning/phases/33-registry-update-bot/33-04-PLAN.md:134–135,166–179`; `installer/verify_registry.py:315–330,1298–1315`). Keeping the runbook as text preserves the executor’s no-remote-write boundary.

**Concerns.**
1. **HIGH — Pushing by SHA does not satisfy the local push gate unless that SHA is checked out.** Option A pushes first `BASE`, then `SHA`; Option B also pushes `SHA`. The runbook only fetches these commits and asks for a clean checkout or scratch worktree. The installed gate rejects any pushed commit other than the current `HEAD`, so even a clean worktree cannot perform both Option A pushes as written (`.planning/phases/33-registry-update-bot/33-04-PLAN.md:132–134,178`; `devtools/hooks.py:1–5,17–27`; `devtools/push_gate.py:226–237,316–324`).
2. **HIGH — STOP paths can leave the proof’s own work behind or delete a changed ref.** A run can cross midnight *after* the pre-dispatch check and create a branch the runbook never looks up. A failed publish can leave an issue but no branch because 33-03 creates the issue first. Part 1 stops before capturing `ISSUE` in either case, while cleanup deletes the original date’s branch by name and closes only the captured issue. The next preflight can then block on the proof’s own leftovers (`.planning/phases/33-registry-update-bot/33-04-PLAN.md:132–136,177`; `.planning/phases/33-registry-update-bot/33-03-PLAN.md:153,205–207`).
3. **MEDIUM — The proof does not reliably bind evidence to the dispatched run.** `--limit 1` and `gh run watch` without an ID do not establish that the watched run is the one just dispatched. The CI checks are phrased as “every run” without an explicit nonempty result or an association between the reported check runs and the bot-dispatched CI run. Also, a successful Option A push triggers ordinary CI on the target ref, so the dispatch-only evidence must be captured **before** that push (`.planning/phases/33-registry-update-bot/33-04-PLAN.md:134–135,178–179`; `.github/workflows/ci.yml:3–7`).

**Suggestions.** Use a clean scratch worktree checked out at each exact commit before its push; do not bypass the hook. Capture and watch both bot runs by ID, require at least one successful dispatched CI run on the exact SHA, and record its two job results and the protection read-back before Option A’s final push. Make cleanup conditional on artifacts verified to belong to that run, including failed-publish and date-rollover cases; leave a ref alone if it no longer points to the recorded SHA.

**Risk Assessment.** High. The procedure is central to rollout, and its current failure paths can leave remote state that blocks a retry.

## 33-05

**Summary.** Add grouped weekly GitHub Actions updates, document owner landing, and verify agreement between the workflow and runbook.

**Findings status.** The command-line extraction now excludes prose. The landing instructions select a fetched SHA, and the final status check no longer directs the executor to discard unrelated paths. Two remaining execution instructions undermine those fixes.

**Strengths.** The Dependabot parse test pins the single ecosystem, root directory, weekly cadence, and group. The `.txt` and YAML paths need no classifier or Markdown-ledger changes, and the proposed guide insertion leaves the tested escape-hatch section intact (`.planning/phases/33-registry-update-bot/33-05-PLAN.md:117–123,154,187–191`; `devtools/docs_only.py:18–36`; `tests/test_docs_only.py:25–45,243,266`; `tests/test_docs.py:698–735`).

**Concerns.**
1. **HIGH — The documented landing command still fails from an ordinary maintainer checkout.** Fetching a remote-tracking ref and verifying its SHA does not move `HEAD`; the push gate will reject that SHA from a checkout at `main` or another branch. The guide also needs to verify the two named checks, not merely show a workflow-run list for the commit (`.planning/phases/33-registry-update-bot/33-05-PLAN.md:154`; `devtools/push_gate.py:226–237`; `.claude/git-workflow.md:35–45`).
2. **MEDIUM — The mutation exercise can erase the new tests before they are committed.** Task 3 adds the tests, performs the mutation, and only then commits. Its `git checkout -- <path>` restore resets the tracked test file to the index, discarding the uncommitted additions along with the temporary change. Likewise, a dirty planned path is not proof of executor ownership, so “commit it” is not a safe response to unexpected changes on those paths (`.planning/phases/33-registry-update-bot/33-05-PLAN.md:192–207`; `AGENTS.md:43–53`).

**Suggestions.** Require a clean checkout at the exact fetched SHA before landing, then verify both named checks on that SHA. Reverse only the temporary mutation, preserving the new tests. Treat unexpected edits to *any* path as user-owned until proven otherwise.

**Risk Assessment.** Medium to high. Dependabot configuration is small; the owner-facing landing and executor rollback instructions are the risks.

## Cross-plan assessment

- **Separate readiness to execute from readiness to enable.** Fix the deterministic test failures, branch cleanup, and push-gate instructions before execution. Keep the agreed dispatch-only rollout. A landed workflow and green local tests do not complete BOT-01/BOT-02; the owner still needs to record the live proof before enabling the cron (`.planning/phases/33-registry-update-bot/33-SPEC.md:24–32`; `.planning/phases/33-registry-update-bot/33-VALIDATION.md:85–96`).
- **Record BOT-03 at the right assurance level.** The plan supports “the reviewed workflow does not target `main`,” not “the token cannot reach `main`.” The context explicitly records the lack of a push restriction. Keep the runtime restriction as the agreed owner follow-up rather than claiming that documentation or a regex enforces it (`.planning/phases/33-registry-update-bot/33-CONTEXT.md:83–86`; `.planning/phases/33-registry-update-bot/33-03-PLAN.md:240–254`).
- **Keep file-level evidence honest.** The existing `make validate` shellcheck target does not inspect inline Actions scripts (`Makefile:53–61`). Keep the orchestrator’s `actionlint` check, and record it as not run if unavailable. The stipulated default `TMPDIR` for full gates also is not evidence of owned scratch cleanup; if the external executor inherits the machine’s scratch-isolation rule, reconcile that at the runner boundary before running the gates (`.planning/phases/33-registry-update-bot/33-01-PLAN.md:70`; `/var/home/bazzite/.config/opencode/AGENTS.md:40–51`).

**Not checked:** No tests, containers, GitHub operations, or remote writes were run. GitHub’s acceptance of dispatched checks under classic branch protection remains unverified.
