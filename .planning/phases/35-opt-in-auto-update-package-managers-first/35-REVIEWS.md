---
phase: 35
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-22T09:30:00Z
plans_reviewed: [35-01-PLAN.md, 35-02-PLAN.md, 35-03-PLAN.md, 35-04-PLAN.md, 35-05-PLAN.md, 35-06-PLAN.md, 35-07-PLAN.md, 35-08-PLAN.md, 35-09-PLAN.md, 35-10-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 35

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 437bc6df)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 05:37 | opencode-referee-one | one-shot probe | OK |
| 05:37 to about 06:30 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null` | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 1 concerns

Cycle 1 of 3. Plan-internal findings were checked against the cited plan lines; claims that rest on repository code (`installer/update.py`, `installer/compose.py`, `installer/bun_globals.py`, `installer/version_status.py`, `installer/atomic.py`) are for the planner to verify against source and fix or reject with a stated reason in the Round 1 ledger. DECISIONS apply exactly; all are provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (35-02) | The default planner is not pure over its supplied inputs: `_decide` calls `update_refusal`, which reads Bun's live global manifest and installed package files | Real by the referee's reading (`installer/update.py:265-278,353-381`; `installer/bun_globals.py:133-161`); planner verifies. DECISION: the planner takes the refusal evidence as an INPUT mapping computed by the caller (the production caller computes it once per pass, tests pass fakes); the live refusal still runs at mutation time inside `UpdateService`; an AST/IO test keeps the planner free of filesystem and subprocess access. |
| M1 (35-02) | The ownership-cycle handling can yield unequal depths or unsafe order, and the dependent resolver raises `DependencyCycleError` for a reachable `requires` cycle | DECISION: deterministic, non-mutating handling: members of an ownership cycle are all placed in one cyclic group that is SKIPPED with a fixed reason (never updated), and a `DependencyCycleError` skips that group's dependents with a fixed reason; test a cycle beside an independent manager. |
| H2 (35-03) | Malformed `by` values escape the strict reader: membership in a frozenset of a list or object raises `TypeError`, not a caught exception | Real (`installer/update_check.py:125-139` checks types first). DECISION: type-check `by` (string) before the membership test; test list and object values; both routes read this file before updating. |
| M2 (35-03) | The log append can block on a FIFO that replaced the log, while holding the run lock; short writes | DECISION: open without blocking and verify a regular file (the `read_capped` pattern of `installer/atomic.py:186-215`), reject a non-regular target, handle short writes; test a FIFO. |
| M3 (35-03) | Task 1 intentionally commits a red reachability test | Prefer one green commit: land `update_all_state.py` with its first real caller in the same commit; if impossible keep a named one-plan exception (phase 29-34 precedent) with the exact orphan list asserted. |
| H3 (35-04) | The failure guard checks the PLANNED `entry.owner_manager`, but `UpdateService.run` resolves ownership again and uses that: a tool planned as uv-owned can be brew-owned after brew failed; a planned formula can resolve to a cask; the shared refusal does not enforce the cask or script-without-update exclusions | Real by the referee's reading (`installer/update.py:283-392,404-423,512-528,660-675`); planner verifies. DECISION: apply the batch exclusions (cask, script without update) and the failed-manager check to the EXACT fresh ownership the service will use, before any mutation or replay; test real-service ownership changes. |
| H4 (35-04) | The second pass can return stale evidence without raising: `outdated=True, stale=True` after a failed lookup, or an older manager report whose derived status says `stale=False` | Real (`installer/version_status.py:396-441,698-710,1079-1092,1768-1811`; phase 34's confirmed rule `installer/update_check.py:148-163,274-301`). DECISION: the second pass authorizes an update only from CONFIRMED evidence (the phase 34 rule: not stale and freshly stamped this pass, per-manager stamps), otherwise the dependent is skipped with a fixed reason; test partial refresh failures. |
| H5 (35-05) | The injected bounded runner does not reach every subprocess: pnpm replay defaults to unbounded `run_captured` in a new session; terminal reload and cursor model lookup use separate runners; manager queries use `run_query`, which does not close stdin | Real by the referee's reading (`installer/compose.py:366-373,411-458`; `installer/pnpm_globals.py:834-865`; `installer/cursor_shim.py:134-143`; `installer/run.py:133-143,209-216,449-472`). DECISION: enumerate every runner site the update path uses; inject the bounded runner wherever the service accepts one; for a path that starts a new session or cannot be injected, record it as an accepted limit bounded by the 3 h job timeout and prove the residual with a test that has a descendant surviving the outer timeout; test with a fake child that spawns a descendant. |
| H6 (35-05) | The lock and no-root claims are stronger than the entry-point checks: the CLI accepts an asserted parent lock, dispatch skips acquisition on that assertion alone, no effective-UID refusal exists, and an AST literal scan proves neither | Real by the referee's reading (`installer/cli.py:66-71`; `setup.py:552-566`; `installer/schedule_run.py:142-163`). DECISION: refuse to run when the effective UID is 0 (`failed: update-all refuses to run as root`) before any refresh or mutation, in the dispatch; test lock handoff through the CLI; keep the AST scan as a regression check only and state the vendor-script residual honestly. |
| H7 (35-06) | The no-write proof can miss receipt writes (the autouse fixture redirects receipts outside a nested scratch HOME) and a generic nonempty control diff can pass from a cache write alone; the one-day-old copied cache can be fresh under the preview's seven-day window | Real (`tests/conftest.py:377-389`; `tests/test_update_check_job.py:47-73`; `installer/version_cache.py:46,248-267`). DECISION: snapshot the actual cache and receipt paths (override `receipts_dir` into the snapshot tree as phase 34 does) and require the exact control change for adoption, retirement and cache persistence; make the copied cache stale under the preview window. |
| M4 (35-06) | A matching fixture proves parity only on matching evidence: preview and execution use different windows, and the note appears only when a manager is planned to update | DECISION: keep one equal-evidence parity test and add a differing-evidence test that checks the preview explains its limit (the note appears whenever the evidence windows differ). |
| M5 (35-01) | The 7,200 s wait cannot outlast a 10,800 s holder; "skipped: busy" is a missed execution, not proof the tool was covered | DECISION: keep the chosen deadlines; describe `skipped: busy` as a missed execution everywhere. |
| M6 (35-01) | The reconfigure test only reseeds unchanged files (not the stale-unit rewrite path where the on decision and saved time must survive); Task 2 reflows the check text before and after the baseline | DECISION: test a stale generated unit and an off row with a saved nondefault time; run the layout baseline before reflowing the text. |
| M7 (35-07) | The tests prove the two halves of delivery separately; the runner drops `XDG_RUNTIME_DIR` so a nonstandard runtime socket is unavailable without an explicit bus address; summary sanitation differs between the timer and manual routes (tabs, ANSI) | DECISION: connect the real adapter to a scratch `notify-send` recorder as phase 34 does; normalize at the result boundary and test the direct CLI line with tabs and ANSI. |
| M8 (35-08) | The preview instruction is not runnable as shown (bare `setup.py`) and says "changes nothing" instead of "writes no installer state"; the test reads uncut text but the renderer discards the tail; "off until you turn it on" shows when the row is already on; "one update per tool per day" hides the retained six-hour per-tool cadence; the pnpm checkout guarantee is timer-only | DECISION: use a copyable `uv run` command, say "off by default", say "writes no installer state", test visibility or reveal at 80x20 on the rendered widget, document cross-row deduplication and the timer-only working-directory guarantee. |
| H8 (35-09) | `UV_SELF_UPDATE_OK` can certify a no-op: bootstrap installs an unversioned standalone uv, `ok: up to date` is accepted, and updater stdout is discarded so the synthesized line is not vendor output | Real by the referee's reading (`scripts/container-e2e-verify.sh:431-438,3019-3028`; `installer/registry.toml:73-86`). DECISION: seed a known OLDER standalone uv and require a version CHANGE at the executable the running chain uses; record the real command evidence or label the artifact as an installer outcome. |
| H9 (35-09) | The Ruff fixture can pass without a dependent upgrade then reject a real one: an exact pin survives `uv tool upgrade`; a current dependent should be omitted by the outdated-only planner, not logged `updated today` | Real (upstream preserves the exact pin on upgrade). DECISION: seed an UPGRADEABLE older dependent without an exact pin and measure its version change; accept current-and-omitted only with fresh evidence. |
| H10 (35-09) | Failed prerequisites do not stop later steps (`|| failed=1`); the rerun has no evidence handoff (each step launches a new Python process, the rerun replaces the per-tool log); the 7,200 s wrapper expires before the job's 10,800 s timeout | Real. DECISION: gate each mutating step on its prerequisites; capture first-run evidence before the second run starts; the wrapper bound covers the job timeout. |
| M9 (35-10) | The gates can certify different trees (only the failing target is rerun after a repair); the summary glob cannot find a missing summary; the composition fixture replaces `_schedule_run_deps` and asserts a parent lock without a parent; the summary fixture omits the second-refresh fallback clause | DECISION: rerun the final gate pair after any repair; enumerate all nine summaries explicitly; add a real composition case with an actual scratch lock; include every coexisting summary clause. |
| C1 (cross) | Deduplication records only formatted `ok:` results: a mutation can succeed and later report failure (post-update probe or cursor shim fails) so the next row repeats it | DECISION: record from a structured mutation outcome, and surface degraded deduplication (an unreadable or unsaved record) in the result line; keep the six-hour cadence decision. |
| C2 (cross) | A green suite, a no-op uv update and a demonstrated replacement under `uv run` are three different results | DECISION: keep `not run` and `UNPROVEN` visible; neither closes AUTOUPD-08; the verifier lists the real replacement as a human item. |
| X | Final gates with the default TMPDIR | Standing ruling; not raised: keep the note in the 35-01 ledger only. |

## OpenCode Review (opencode-referee-one), cycle 1

Using the plan-review checklist and Ponytail Review to assess all ten plans, and Codebase Memory and Graphify to verify their assumptions against the repository. This is a read-only review.
The bounded runner in 35-05 reaches the primary update command, but the production wiring uses separate runners for probes, pnpm replay, and terminal follow-up. The proposed runner-spy test would miss those paths.
I found a gap in the failure guard: the executor checks the planned owner, but `UpdateService` can resolve a different owner just before mutation. The failure and cask checks need to use that same fresh ownership.
# Phase 35 plan review — convergence cycle 1

**Verdict: revise before execution.** The ten plans cover the requested feature and reuse the right installer components. The main blockers are at the boundaries: the ownership checked by the planner can differ from the ownership used to update a tool, several production subprocesses bypass the proposed runner, and the container can report success without proving that `uv` was replaced. These findings do not require reopening the provisional decisions.

**Review scope:** GSD implementation plans, checked against the current repository source and test fixtures. This was a read-only review; no tests, updaters, timers, notifications, or containers were run.

## 35-01

**Summary:** Adds the off-by-default 03:00 row, runner dispatch, empty-run tracer, and screen wiring.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** Adding `default_on` to the schedule definition preserves the existing three-state decision record. A distinct job kind also avoids the missing-target cleanup that applies only to per-tool updates (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:159–160`; `installer/schedules.py:247–269`, `:1561–1575`, `:1704–1724`). The small-screen check-row regression test actually reads rendered text (`tests/test_schedules_view.py:914–951`).

**Concerns:**
- **MEDIUM — Two hours is not enough to wait out a three-hour holder.** The plan says the 7,200-second wait lets `update-all` finish and assumes it covers the timed-out per-tool row. The runner stops waiting at the deadline regardless of what the holder completed, and `update-all` deliberately skips some tools that still have their own rows (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:163`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:158`; `installer/helper_assets/schedule_runner.py:266–285`).
- **MEDIUM — The reconfigure test only reseeds unchanged files.** The test does not exercise the stale-unit rewrite path, where the on decision and saved time must survive registration. Separately, Task 2 tells the executor to reflow the check text before the baseline run and again after it (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:146`, `:209–211`; `installer/schedules.py:1598–1642`).

**Suggestions:** Keep the chosen deadlines, but describe `skipped: busy` as a missed execution, not proof the tool was covered. Test a stale generated unit and an off row with a saved nondefault time; run the layout baseline before reflowing the text.  
**Risk Assessment:** Medium. The seed rule is sound; the remaining gaps are in verification and timeout expectations.

## 35-02

**Summary:** Defines manager ordering, dependent groups, refusal reasons, and failure lookup.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** Ownership edges are the right input: `_RANK` ranks installation methods, not who manages an installed copy. The dependency resolver really does require both keyword-only callbacks and returns a closure, so filtering it back to the group is appropriate (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:136–138`; `installer/ownership.py:82–100`; `installer/resolve.py:12–31`; `installer/deps.py:40–55`, `:123–153`).

**Concerns:**
- **HIGH — The default planner is not pure over its supplied inputs.** `_decide` calls `update_refusal`, which reads Bun's live global manifest and installed package files. The same catalog, status pass, and outdated set can therefore produce different plans. The AST and subprocess tests do not catch filesystem reads (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:128`, `:169–181`; `installer/update.py:265–278`, `:353–381`; `installer/bun_globals.py:133–161`).
- **MEDIUM — The ownership-cycle instruction can produce unequal depths or permit unsafe ordering.** Returning zero upon detecting recursion does not make all cycle members depth zero if callers add one while unwinding. More importantly, executing both members cannot honor both manager-first edges. The dependent resolver also raises `DependencyCycleError` for a reachable `requires` cycle, even with constant-true callbacks (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:123`, `:137–138`; `installer/deps.py:123–148`).

**Suggestions:** Feed captured refusal evidence into the planner and keep the live refusal at mutation time. Specify deterministic, non-mutating handling for cyclic branches, and test a cycle with an otherwise independent manager.  
**Risk Assessment:** High until the planner's input contract is explicit; the overall grouping design is sound.

## 35-03

**Summary:** Adds the daily deduplication record, per-tool log, and the existing rows' side of deduplication.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** The state reader uses the right bounded, nonblocking primitive. `atomic_replace_entry` replaces a final symlink rather than writing through it, unlike `atomic_write_text` (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:132–135`; `installer/atomic.py:36–78`, `:186–215`).

**Concerns:**
- **HIGH — Malformed `by` values can escape the strict reader.** The action checks membership in a `frozenset` without first checking that `by` is a string. A JSON list or object there raises `TypeError`, not one of the specified caught exceptions. Both update routes read this file before updating. The existing notified-state reader checks types before using the values (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:119–125`, `:133`, `:181`; `installer/update_check.py:125–139`).
- **MEDIUM — Log append is protected against symlinks but can still block on a FIFO.** The proposed append does a blocking write-open without verifying that the opened file is regular. If a FIFO replaces the log after truncation, append can stall while holding the run lock. The repository's read primitive shows the nonblocking-open and descriptor-type pattern (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:135`; `installer/atomic.py:186–203`).
- **MEDIUM — Task 1 intentionally commits a red reachability test.** The plan explicitly omits the known failing test until Task 2, even though the test rejects every unreachable installer module (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:136–137`; `tests/test_reachability.py:142–162`, `:196–197`).

**Suggestions:** Type-check `by` before membership and test list/object values. Reject nonregular append targets and handle short writes. Land the IO module with its first real caller in the same green commit.  
**Risk Assessment:** High for availability: one malformed record can stop both routes; a blocked append can hold up other jobs.

## 35-04

**Summary:** Executes managers, refreshes again, executes dependents, and records the outcomes.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** The second pass is placed after manager updates. The existing service invalidates manager and version evidence after an updated or failed outcome. The three-tool tracer also distinguishes per-tool log lines from the shared result (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:143–146`, `:176–177`; `installer/update.py:732–746`; `installer/version_status.py:1465–1485`; `installer/helper_assets/schedule_runner.py:522–545`).

**Concerns:**
- **HIGH — The failure guard and mutation use different ownership.** The executor checks the planned `entry.owner_manager`; `UpdateService.run` then resolves ownership again and uses that result. A tool planned as uv-owned can actually be Brew-owned after Brew failed, or a planned formula can resolve to a macOS cask. The shared refusal does not enforce the phase's cask or script-without-update exclusions (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:142–145`; `installer/update.py:283–392`, `:404–423`, `:512–528`, `:660–675`).
- **HIGH — A second pass can return stale evidence without raising.** The plan promises to exclude stale dependents but passes raw `outdated_ids` and handles only thrown exceptions. GitHub lookup failures can retain `outdated=True` with `stale=True`; a partial manager failure can reuse an older report whose derived status still says `stale=False`. Phase 34 already distinguishes confirmed evidence from these cases (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:27`, `:143–145`; `installer/version_status.py:396–441`, `:698–710`, `:1079–1092`, `:1768–1811`; `installer/update_check.py:148–163`, `:274–301`).

**Suggestions:** Apply batch exclusions and the failed-manager check to the exact fresh ownership the service will use, before any mutation or replay. Test real-service ownership changes and partial refresh failures. Keep the chosen second pass and fallback, but do not authorize an update from unconfirmed evidence.  
**Risk Assessment:** High. Both gaps can authorize an unattended mutation the plan says must not occur.

## 35-05

**Summary:** Adds command bounds and environment policy, plus refusal and held-lock tests.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** The proposed primary runner correctly reuses closed stdin and the shared Homebrew environment policy, remains in the timer child's process group, and lets short queries override the default timeout (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:116–127`; `installer/run.py:48–58`, `:127–151`, `:219–240`).

**Concerns:**
- **HIGH — The injected runner does not reach every subprocess.** `_build_services` passes it to the primary update, but pnpm replay defaults to unbounded `run_captured` in a new session. Terminal reload and cursor model lookup use separate runners, and manager queries use `run_query`, which does not close stdin itself. The one-runner test can pass while a replay survives the outer timeout (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:116–127`; `installer/compose.py:366–373`, `:411–458`; `installer/pnpm_globals.py:834–865`; `installer/cursor_shim.py:134–143`; `installer/run.py:133–143`, `:209–216`, `:449–472`).
- **HIGH — The lock and no-root claims are stronger than the entry-point checks.** The CLI accepts an asserted parent lock and dispatch skips acquisition on that assertion alone. The planned branch adds no effective-UID refusal. Scanning literals in four files proves neither that the manual route is unprivileged nor that delegated vendor tools cannot escalate; the shared policy explicitly documents the vendor-script residual (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:126–127`, `:159–161`, `:203`; `installer/cli.py:66–71`; `setup.py:552–566`; `installer/schedule_run.py:142–163`; `installer/run.py:48–52`).

**Suggestions:** Wire or explicitly bound the actual production subprocess paths. Test timeout cleanup with a fake child that spawns a descendant, test lock handoff through the CLI, and reject root before refresh or mutation. Keep the AST scan as a regression check, not as proof of vendor behavior.  
**Risk Assessment:** High. The proposed tests do not yet prove the phase's privilege, locking, or process-lifetime guarantees.

## 35-06

**Summary:** Adds lock-free preview using the shared planner and `hold_writes()`.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** The early branch avoids settings and post-install wiring. Holding writes is stronger than copying only the cache: it also defers receipt adoption and retirement and manager snapshot persistence (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:129–130`; `setup.py:531–566`; `installer/version_status.py:1328–1360`, `:1513–1528`, `:1575–1593`, `:2085–2104`).

**Concerns:**
- **HIGH — The no-write proof can miss receipt writes.** The autouse fixture redirects receipts outside a nested scratch HOME, and a generic nonempty control diff can pass from a cache write alone. Phase 34 explicitly overrides `receipts_dir` into the snapshot tree. Also, the copied one-day-old cache can be fresh under preview's seven-day window (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:161–163`; `tests/conftest.py:377–389`; `tests/test_update_check_job.py:47–73`; `installer/version_cache.py:46`, `:248–267`).
- **MEDIUM — A matching fixture proves parity only on matching evidence.** Preview and execution use different windows, and the note appears only when a manager is planned to update, even though execution refreshes dependents regardless. The test therefore misses a user-visible difference when no manager needs an update (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:117–129`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:145`; `installer/version_cache.py:248–267`).

**Suggestions:** Snapshot the actual cache and receipt paths and require the exact control change for adoption, retirement, and cache persistence. Keep one equal-evidence parity test and add a differing-evidence test that checks the preview explains its limit.  
**Risk Assessment:** Medium–high. The no-write design is credible, but its planned proof is not yet reliable.

## 35-07

**Summary:** Adds one notification for an updated or failed tool and preserves per-job bus forwarding.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** Counts and registry IDs satisfy the existing notifier's plain-text contract. Reusing the per-job bus forwarding keeps the global and unit allowlists unchanged (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:110–123`, `:152–159`; `installer/notify.py:1–5`, `:79–104`; `installer/helper_assets/schedule_runner.py:83–98`, `:346–356`; `installer/daemon.py:34–47`).

**Concerns:**
- **MEDIUM — The tests prove the two halves of delivery separately.** A fake notifier in the job plus a fake uv that records the bus cannot detect a broken handoff to the actual adapter. The runner also drops `XDG_RUNTIME_DIR`, so without an explicit bus address a nonstandard runtime socket is not available to the fallback (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:116`, `:152–159`; `installer/helper_assets/schedule_runner.py:83–98`, `:192–196`; `installer/notify.py:51–68`).
- **MEDIUM — Summary sanitation is not equivalent on timer and manual routes.** `reason_line` retains interior tabs and strips the escape character, not the full ANSI sequence. The outer runner normalizes the line later, but manual `setup.main` prints directly (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:114`, `:123`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:161`; `installer/notify.py:30–33`; `installer/sanitize.py:9–22`; `installer/helper_assets/schedule_runner.py:130–135`; `setup.py:560–566`).

**Suggestions:** Connect the real adapter to a scratch `notify-send` recorder, as Phase 34 does (`tests/test_update_check_job.py:84–94`, `:164–172`). Normalize at the result boundary and test the direct CLI line with tabs and ANSI.  
**Risk Assessment:** Medium. The notification rule is clear; the weak spots are delivery proof and output handling.

## 35-08

**Summary:** Adds Schedules detail text and records the phase's decision amendments.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** A row-specific `_extra_lines` branch is the right extension point and need not change the Phase 34 permission line. The existing check-row test verifies the rendered widget (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:109–117`; `installer/schedules_screen.py:494–505`, `:532–541`; `tests/test_schedules_view.py:914–951`).

**Concerns:**
- **MEDIUM — The preview instruction is neither runnable as shown nor visible at 80×20.** It advertises bare `setup.py`, not the supported `uv run` invocation, and says “changes nothing” instead of “writes no installer state.” The test reads uncut `detail_text`; the renderer actually discards the tail after wrapping. The inherited “off until you turn it on” text also appears when the row is already on (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:104–112`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:210`; `setup.py:1–8`; `tests/test_schedules_view.py:1307–1324`; `installer/schedules_screen.py:460–465`, `:475–505`; `installer/ui_common.py:70–81`).
- **MEDIUM — Some pinned wording overstates the contract.** “One update per tool per day” hides the retained six-hour per-tool cadence and assumes the daily record was readable and saved. The pnpm checkout guarantee applies to the timer child, whose `cwd` is set explicitly, not to a manual invocation (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:112`, `:146–149`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:181`; `installer/helper_assets/schedule_runner.py:332–346`; `setup.py:552–566`).

**Suggestions:** Use a copyable command, say “off by default,” and test that the preview is visible or can be revealed at 80×20. Document cross-row deduplication and the timer-only working-directory guarantee.  
**Risk Assessment:** Medium. Fix before pinning the wording in tests and architecture docs.

## 35-09

**Summary:** Adds the disposable-container harness intended to prove real manager updates and a same-day rerun.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** It reuses the actual timer argv, distinguishes `UNPROVEN` from a pass, and builds on a teardown that verifies the named container is gone (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:24–29`, `:127`, `:165`; `installer/schedules.py:864–901`; `scripts/container-e2e-verify.sh:2972–2993`, `:3033–3057`).

**Concerns:**
- **HIGH — `UV_SELF_UPDATE_OK` can certify a no-op.** Bootstrap installs an unversioned standalone uv; the verdict accepts an `ok:` result and a readable post-run binary without requiring replacement. Equal versions are explicitly `ok: up to date`. Successful updater stdout is also discarded, so the synthesized line is not the requested command output (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:116`, `:127`; `scripts/container-e2e-verify.sh:431–438`, `:3019–3028`; `installer/registry.toml:73–86`; `installer/schedules.py:488–499`; `installer/run.py:133–151`; `installer/helper_assets/schedule_runner.py:359–376`).
- **HIGH — The Ruff fixture can pass without a dependent upgrade, then reject a real one.** It installs an exact constraint and accepts any `ok:` from ordinary `uv tool upgrade ruff`; upstream [preserves the exact pin on upgrade](https://github.com/astral-sh/uv/blob/264d8b4a5e10d195d2cc2a34dffa807cfbe6298c/crates/uv/tests/tool/tool_upgrade.rs#L723-L752). If Ruff really upgrades and is now current, the outdated-only planner should omit it, not necessarily log `updated today` (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:114–118`, `:127`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:138`; `installer/update.py:188–209`; `installer/version_status.py:683–707`).
- **HIGH — Failed prerequisites do not stop later steps, and the rerun has no specified evidence handoff.** `|| failed=1` continues after a failed or unproven preview. Each step launches a new Python process, while the rerun replaces the per-tool log. The driver must capture first-run evidence before starting the second run. Its 7,200-second wrapper also expires before the job's 10,800-second timeout (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:118`, `:127`, `:165`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:135`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:163`; `scripts/container-e2e-verify.sh:3033–3057`).

**Suggestions:** Seed a known older standalone uv and verify a version change at the same executable used by the running chain. Seed an upgradeable older dependent and measure its change. Gate each mutating step on its prerequisites; read the first result before rerunning; accept current-and-omitted dependents only with fresh evidence. Record actual command evidence or label the artifact as an installer outcome, not vendor output.  
**Risk Assessment:** High. The current verdicts can both pass without proving AUTOUPD-08 and fail after correct behavior.

## 35-10

**Summary:** Checks composition and table consistency, runs final gates, and collects handoff decisions.  
**Findings status:** First review; no previous-cycle findings.  
**Strengths:** Parser-to-dispatch parity, real unit rendering over fakes, and production reachability are useful checks. The named Make targets invoke the actual static gates and coverage suite (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:93–107`, `:137–147`; `tests/test_reachability.py:142–162`, `:196–197`; `installer/schedules.py:938–971`; `Makefile:60–64`).

**Concerns:**
- **MEDIUM — The gates can certify different trees.** If one gate passes and a repair is needed for the other, the plan reruns only the failing target and commits the repair. That does not prove both gates passed on the final revision. The summary glob also cannot find a missing individual summary if the remaining files all have `## Decisions` (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:129–147`; `Makefile:60–64`).
- **MEDIUM — The final composition and worst-case tests miss important boundaries.** The fixture replaces `_schedule_run_deps`, the code responsible for holding preview writes and wiring the update runner, and asserts a parent lock without a parent. The summary fixture omits the second-refresh fallback clause, which can coexist with the other clauses (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:93–96`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:143–146`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:129–130`; `setup.py:531–566`; `installer/schedule_run.py:142–163`).

**Suggestions:** Keep the parity fixture, but name it as a dispatch test. Add a real composition case with an actual scratch lock, include every coexisting summary clause, enumerate all nine summaries, and rerun the final gate pair after any repair.  
**Risk Assessment:** Medium. These checks support phase closure; they cannot substitute for the production-path and container proofs.

## Cross-plan assessment

1. **Put the unattended safety checks at the mutation boundary.** Revise 35-02, 35-04, and 35-05 together so eligibility, the failed-manager check, and actual mutation use the same fresh ownership. Prove the lock, unprivileged execution, and process cleanup through the real composition with fake tools.
2. **Make deduplication truthful about partial success.** The current per-tool function can mutate successfully and later report failure when the post-update probe or cursor shim fails. Plans 35-03 and 35-04 record only formatted `ok:` results, so the next row can repeat an already completed mutation. Keep the six-hour cadence decision, but record from a structured mutation outcome and surface degraded deduplication when the record cannot be read or saved (`installer/schedule_run.py:54–68`, `:113–123`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:181`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:144`).
3. **Separate feature completion from proof completion.** A successful test suite, a successful no-op `uv self update`, and a demonstrated replacement of the binary under `uv run` are three different results. Keep `not run` and `UNPROVEN` visible, but neither closes AUTOUPD-08 (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-SPEC.md:57–60`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-VALIDATION.md:46–51`, `:110–114`).

**Convergence status: issues found.** Re-review after the safety boundary and evidence contracts are revised. Actual uv replacement, shell-file effects, timer delivery, and desktop notifications remain unverified.
