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

---

## Lane Log (convergence cycle 2, plans at 4c342c03)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 07:29 | opencode-referee-one | one-shot probe | OK |
| 07:29 to about 08:30 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, cycle 1 findings supplied | exit 0 |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

Cycle 2 of 3 (cap rule: after replan round 2 comes cycle 3, the last; fixes found after it go to the post-execution fix round). Claims that rest on repository code are for the planner to verify against source and fix or reject with a stated reason in the Round 2 ledger. DECISIONS apply exactly; all are provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| A1 (35-04) | A recently failed manager lookup still authorizes an update: the service can retain a recent manager stamp and the old report while setting a newer `failed_at`, and a package in that report reads `outdated=True, stale=False` (`installer/version_status.py:698-710,1768-1811`; `installer/update_check.py:163-177`) | Real by the referee's reading; planner verifies. Round 1 recency windows stay. DECISION: evidence from a manager report whose snapshot has a failure newer than its success stamp (a backfilled report) is UNCONFIRMED, in both passes and in the explicit second-pass fallback; test it with the real `VersionRefreshService`. |
| A2 (35-04) | The guard does not cover every side effect: Cursor's helper refreshes its shim after `_update` even when the guard returned a skip, which can run a model query and write shim state (`installer/schedule_run.py:89-123`) | Real. DECISION: a guarded skip short-circuits the helper before any follow-up (no model query, no shim write); test with a recording runner. |
| A3 (35-04) | The guard only checks managers that already failed: if uv was planned before a later manager but fresh ownership says it belongs to that later manager, uv can be authorized before its owner ran | Real. DECISION: the guard also refuses a dependent whose fresh owner manager has not yet succeeded in this batch (not planned earlier, or planned later), with a fixed reason; test an ownership change that points at a later manager. |
| A4 (35-04) | A manager's pnpm self-update can replay the whole captured global set before the second pass, including non-catalog packages; that work bypasses the dependent's guard, daily record and log, and the second pass can select the same dependent again; the run cannot claim "nothing updated twice" from the planned tally | Real by the referee's reading (`installer/update.py:688-722`; `installer/pnpm_globals.py:803-823,834-866`); planner verifies. DECISION: keep the replay (it restores what the manager's self-update wiped); never claim "nothing updated twice" from the tally; the second pass re-reads outdated after the replay so a dependent the replay already updated is omitted; test that a replayed dependent is not updated again; document replay as an accepted limit of the run result (the result counts planned updates only) in the 35-08 amendment list. |
| B1 (35-03) | `status == "updated"` is not proof of mutation: the pnpm path can finish `add -g` then fail its smoke check and report `failed` (`installer/executors.py:573-599,613-614`; `installer/update.py:248-262,432-436`), so `ToolRun.mutated` is false and the other schedule repeats it | Real by the referee's reading; planner verifies. DECISION: carry mutation evidence from the service (a structured outcome field the executor sets once its mutating command succeeded); test the pnpm add-then-smoke-failure case records the day; where the service cannot say, record conservatively and say so in the plan. |
| B2 (35-03) | A run that crosses midnight records the wrong day for later mutations | DECISION: the record date is sampled at the mutation boundary (the injected clock after each update), not at run start; test midnight with the injected clock. |
| C1 (35-05) | An asserted parent lock still bypasses mutual exclusion: the flag is a Boolean and dispatch skips acquisition before any check; the tests expect mutation while an unrelated holder owns the lock (`installer/cli.py:66-71`; `installer/schedule_run.py:148-163`) | Real. DECISION: verify the handoff instead of trusting the flag: the child accepts the flag only when the lock is held by its own parent (the planner reads `installer/runlock.py` and picks the smallest sound proof, for example the recorded holder pid equals the parent pid), otherwise it refuses with a fixed line; an unrelated holder with the flag set must REFUSE; the tests in 35-05 and 35-10 and the 35-01 tracer expect refusal there and success only with a real parent. |
| C2 (35-05) | The 1,200 s per-command timeout kills the direct child only; the outer runner kills the job group only on its own timeout, not on a normal failure result; the manual route has no outer runner; closed stdin does not detach the controlling terminal | Real by the referee's reading (`installer/run.py:127-146,371-382`; `installer/helper_assets/schedule_runner.py:206-257`); planner verifies. DECISION: the bounded runner kills the command's whole process group on its timeout and waits for it before continuing or unlocking; test a per-command timeout followed by a normal job exit with a descendant; keep the documented vendor and new-session limits distinct. |
| C3 (35-05) | The root check runs after lock creation and can leave a root-owned state directory or lock file; the held-lock fake takes two args but the batch passes `runner=`; two replay fakes cannot accept the keyword | DECISION: refuse root before creating the lock; fix the fake signatures without weakening their assertions. |
| D1 (35-09) | `would update` does not identify `uv self update`: a brew-owned uv and a standalone uv print the same line; the inner bound starts after the harness's outer `uv run`; `runner_argv` does not supply the generated unit's environment | Real by the referee's reading. DECISION: record the actual updater route (owner and leaf argv) in the evidence and require it to be the standalone `uv self update`; run with the unit-equivalent environment; bound or account for the outer launch separately. |
| D2 (35-09) | The rerun can pass on missing evidence: an omitted Ruff row with the same installed version does not distinguish current from a failed lookup; the rerun emits one new start and one new result, not two results | DECISION: an omitted dependent needs fresh valid current evidence (a confirmed lookup), else UNPROVEN; the verdict counts one start and one result for the rerun. |
| D3 (35-09) | The transcript cannot substantiate the claimed evidence: hashes and rc digests are gathered but not printed or kept in the handoff; `install_one` rejects `ALREADY_INSTALLED` | DECISION: persist the measured path, hashes and rc digests in the handoff file before rerunning and print them; accept already-present prerequisites after verifying them. |
| E1 (35-02) | A skipped ownership cycle can still authorize an update through a cycle member (the fixture updates Volta through uv while uv is skipped as cyclic) | DECISION: propagate a cycle-blocked reason to managers that would update through the cyclic branch; independent branches continue; test it. |
| E2 (35-02) | The cask-first rule has two definitions: `_decide` returns `refusal not evaluated` for a missing evidence key before `exclusion` sees the cask | DECISION: cask precedence is consistent: the exclusion check runs before the missing-evidence reason; test the missing-evidence cask case. |
| F1 (35-06) | Preview can label a failed manager report `would update`: it uses `not stale` alone | DECISION: preview reuses the run's confirmation helper with the preview's release-cache window and the same manager-evidence rule; test a failed manager lookup in preview; keep the no-write claim scoped to installer state. |
| G1 (35-07) | The real adapter test replaces `_schedule_run_deps` and so bypasses the production `notify=` wiring | DECISION: keep the real deps constructor for one recorder test and fake the services underneath it; describe notification as an attempt. |
| H1 (35-08) | The second rendered row is not necessarily the second logical line (the what-text wraps); the action's limits text omits the record-health qualification | DECISION: assert the whole preview command at 80x20 on the rendered widget (keep it visible with a three-line status or specify how it is revealed); add the record-health qualification. |
| H2 (35-08) | The amendments leave different versions of the same promise (timer opt-in vs explicit manual run; notification attempt vs delivery; process and deduplication limits) | DECISION: 35-08's amendment list states one wording for each, and the architecture text, UI text, SPEC/ROADMAP/REQUIREMENTS amendment bullets use it. |
| I1 (35-10) | The worst-case summary is only an all-clauses fixture: a long valid catalog ID can hide a fixed degradation clause or make manual and timer results differ | DECISION: bound the variable fields before allocating room to the fixed clauses; test manual and runner output with a long valid ID. |
| I2 (35-10, 35-01) | Final composition expects an overlapping run under an unrelated holder; the tracer does not prove the child is protected by the same lock; AUTOUPD-08 pass must be bound to the tested revision | DECISION: C1's contract is tested here and in the tracer (same scratch lock on both sides, consuming the runner's actual child arguments); a repair that changes the exercised path invalidates an earlier AUTOUPD-08 observation. |
| J1 (35-01) | The no-Policies assertion checks a source list, not the composed Policies rows (LOW) | DECISION: assert absence from the composed Policies rows separately from presence in uninstall. |
| K1 (cross) | All ten plans prescribe GNU `df --output=pcent`, which fails on macOS | DECISION: use a portable disk check (`df -Pk` with awk) that fails closed when usage cannot be read, in all ten plans' shared executor wrapper; keep the scratch cleanup and final-gate TMPDIR rules. |
| X | Final gates with the default TMPDIR | Standing ruling; not raised. |

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist and Ponytail Review to assess all ten plans, with Codebase Memory and Graphify for source grounding. I’ll keep this read-only: no tests, updates, timers, notifications, or containers.
**HIGH — 35-04 still accepts some failed refreshes as confirmed evidence.** The real refresh service can retain a recent manager timestamp after a failed query, and the proposed age check would still accept it (`installer/version_status.py:1768–1811`, `installer/update_check.py:148–178`).
**HIGH — 35-04’s fresh-owner guard still leaves a Cursor follow-up path.** The existing helper refreshes the shim after `_update` even if the update returns a skip. Without an explicit short-circuit, a guard refusal can still run a model query and write shim state (`installer/schedule_run.py:89–123`).
**HIGH — 35-05 and 35-10 still treat the parent-lock flag as proof of a lock handoff.** The proposed tests expect an update to proceed while an unrelated holder owns the lock (`installer/schedule_run.py:148–163`). That leaves the overlap finding open.
**HIGH — 35-09 still needs stronger container evidence.** A `would update` line does not identify the updater that ran, and an unchanged installed Ruff version does not distinguish a successful current-version check from a failed lookup (`installer/update.py:195–209,512–555`, `installer/version_status.py:662–709`).
# Phase 35 plan review — convergence cycle 2

**Verdict: revise before execution.** The revisions improve the opt-in row, planner purity, state-file handling, and container verdicts. The remaining blockers are at the mutation boundary: an asserted parent lock still permits overlap, a command timeout can leave work running after unlock, and recent manager evidence can still be accepted after a failed lookup. The container plan also needs to prove which updater actually replaced `uv`.

**Scope:** All ten current GSD execution plans, checked against repository source and test fixtures. The expected load is one developer’s machine, with several schedules and a manual CLI sharing it. This was a read-only review.

## 35-01

**Summary:** Adds the off-by-default 03:00 row, runner dispatch, empty-run tracer, state-artifact names, and ninth-row layout.

**Findings status:** M5 and M6 are addressed in the plan: `busy` is a missed execution, stale-unit reconfiguration and saved off-row time are covered, and the layout baseline precedes the reflow. The tracer still does not prove lock handoff.

**Strengths:** `default_on` changes only the undecided branch; the existing decided-off and decided-on branches stay intact. A distinct job kind also avoids the per-tool missing-target cleanup (`installer/schedules.py:1561–1575`, `:1598–1642`, `:1704–1725`).

**Concerns:**
- **MEDIUM — The tracer proves dispatch, not that the child is protected by the same lock.** It hardcodes the child CLI and supplies a scratch runner lock without checking it against the child context. The production context derives its lock from HOME, and the child trusts the parent flag without checking the handoff (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:151–152`; `installer/schedules.py:622–646`; `installer/schedule_run.py:148–163`).
- **LOW — The no-Policies assertion checks a source list, not the view.** The proposed test checks `tweaks.BUNDLES` and the uninstall adapters, while the Policies screen renders a composed list that also includes redirects and desktop policies (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:148`; `installer/compose.py:702–717`; `installer/policies_screen.py:131–145`).

**Suggestions:** Make the tracer consume the runner’s actual child arguments and verify the same scratch lock protects both sides. Assert absence from the composed Policies rows separately from presence in uninstall.

**Risk Assessment:** Low for seeding; medium for the tracer until it proves the lock contract.

## 35-02

**Summary:** Defines pure manager ordering, owner groups, exclusions, and failure lookup.

**Findings status:** H1 is addressed by passing refusal evidence in. M1 is partially addressed: cycle members are skipped, but the tests still authorize a manager whose owner is in the cycle.

**Strengths:** Ownership edges are the right input; `_RANK` ranks install methods, not installed owners. The plan also correctly supplies both keyword-only callbacks to the resolver and filters its closure back to the group (`installer/ownership.py:82–100`; `installer/resolve.py:12–31`; `installer/deps.py:40–55`, `:123–153`). Capturing refusals outside the planner removes the Bun manifest read from it (`installer/update.py:265–278`, `:353–381`).

**Concerns:**
- **MEDIUM — A skipped ownership cycle can still authorize an update through a cycle member.** The fixture explicitly updates Volta through uv while uv is skipped as cyclic. Treating that edge as absent makes ordering terminate, but it does not make the owner independent. The existing updater still dispatches by the actual owner (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:131`, `:146–147`; `installer/update.py:195–209`, `:418–423`).
- **MEDIUM — The cask-first rule has two different definitions.** Task 2 specifies cask precedence, but `_decide` returns `refusal not evaluated` for a missing evidence key before calling `exclusion`. A macOS cask with missing evidence therefore gets a different reason, even though the cask decision needs no refusal evidence (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:178–180`, `:193–194`; `installer/ownership.py:82–97`; `installer/update.py:203–207`).

**Suggestions:** Propagate a cycle-blocked reason to managers that would update through the cyclic branch, while independent branches continue. Add the missing-evidence cask case and make precedence consistent.

**Risk Assessment:** Medium. The pure planner is sound in structure; the remaining issues concern what it authorizes or reports at the edges.

## 35-03

**Summary:** Adds the daily record, link-safe run log, and the per-tool schedules’ side of deduplication.

**Findings status:** H2, M2, and M3 are addressed in the plan. C1 is addressed for probe and shim failures *after* the service returns `updated`, but not for partial mutations reported by the service itself.

**Strengths:** Type-checking before set membership closes the malformed-JSON crash. `atomic_replace_entry` swaps the final link rather than writing to its target, and the nonblocking open plus descriptor check matches the existing capped-read pattern. The module lands with its first production import (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:149–152`, `:195`; `installer/atomic.py:58–73`, `:186–215`; `tests/test_reachability.py:142–162`, `:196–197`).

**Concerns:**
- **HIGH — `status == "updated"` is not proof of whether a mutation happened.** The real pnpm path can finish `add -g`, then fail its smoke check without rolling the packages back. `perform_update` reports `failed`; the proposed `ToolRun.mutated` is false, so the other schedule can repeat the mutation (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:136–137`, `:151–152`; `installer/executors.py:573–599`, `:613–614`; `installer/update.py:248–262`, `:432–436`).
- **MEDIUM — A run that crosses midnight records the wrong day for later mutations.** The per-tool path samples the date before updating, and the batch reuses its start date for every record. On the next run those entries are ignored even if the mutation completed earlier that same calendar day (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:150–152`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:158–159`; `installer/schedules.py:161–164`).

**Suggestions:** Carry mutation evidence from the service, including a known successful package change followed by failure. Test midnight with the injected clock and define the record date at the mutation boundary, or document a deliberate run-start-day rule consistently.

**Risk Assessment:** High for the once-a-day guarantee. The file handling is materially better; the record still does not faithfully describe every mutation.

## 35-04

**Summary:** Executes the two stages through the update service, guards fresh ownership, and records per-tool outcomes.

**Findings status:** H3 is partially addressed by `run_guarded`; H4 remains open for recently failed manager reads. The revised tests cover age and changed eligibility, but not all paths that authorize or perform mutation.

**Strengths:** The new service seam can judge the exact ownership used for dispatch before receipt checks and pnpm capture. Keeping the existing `run(target)` signature avoids changing every caller, and separate pass results avoid rereading unrelated cache state (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:154–157`; `installer/update.py:660–714`; `installer/update_check.py:148–178`).

**Concerns:**
- **HIGH — A recently failed manager lookup can still authorize an update.** The proposed age rule accepts a two-hour-old manager timestamp. The real service can retain that stamp and the old report while setting a newer `failed_at`; a package in that report still reads `outdated=True, stale=False`. The real-service test covers release lookups, not this manager path (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:139–141`, `:156`, `:196`; `installer/version_status.py:698–710`, `:1768–1811`; `installer/update_check.py:163–177`).
- **HIGH — The guard does not cover every side effect or preserve order after ownership changes.** Cursor’s helper refreshes its shim after `_update` even if the guard returns a skip; that can run a model query and write state. Separately, the guard only checks managers that already failed. If uv was planned before a later manager but fresh ownership says it belongs to that later manager, the guard can authorize uv before its owner has run (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:155–160`, `:200`; `installer/schedule_run.py:89–123`; `installer/update.py:660–675`, `:708–714`).
- **HIGH — Manager replay can mutate dependents outside the batch plan.** A successful pnpm self-update can replay the entire captured global set before the second pass, including packages that are not catalog rows. That work never goes through the dependent’s failure guard, daily record, or per-tool log; the second pass can then select the same dependent again. The run cannot claim “nothing updated twice” from the planned tally alone (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:155–161`; `installer/update.py:688–722`; `installer/pnpm_globals.py:803–823`, `:834–866`).

**Suggestions:** Keep the freshness windows, but distinguish successful evidence from backfilled failures, including in the explicit second-pass fallback. Require a fresh route to match the evidence and stage that authorized it, or skip it. Short-circuit guarded Cursor skips before follow-up. Make the batch account for or contain pnpm replay, and test the real site rather than only the `UpdateService` spy.

**Risk Assessment:** High. These are gaps in unattended mutation authorization and accounting, not objections to the two-pass design.

## 35-05

**Summary:** Adds the bounded runner, environment policy, root refusal, and lock and refusal tests.

**Findings status:** H5 improves through replay and reload injection, but the per-command cleanup gap remains. H6 is only partially addressed: root is checked late, and the lock test explicitly blesses overlap.

**Strengths:** Passing the runner to pnpm replay and terminal reload closes two real paths that currently bypass it. The privilege scan is correctly described as a regression check, not proof of vendor behavior (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:147–149`, `:185`; `installer/compose.py:433–458`; `installer/pnpm_globals.py:834–865`; `installer/run.py:48–58`).

**Concerns:**
- **HIGH — An asserted parent lock still bypasses mutual exclusion.** The test expects mutation while an unrelated holder owns the lock. `--parent-holds-run-lock` is a Boolean, and dispatch checks it before attempting any acquisition or verification (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:184`; `installer/cli.py:66–71`; `setup.py:560–564`; `installer/schedule_run.py:148–163`).
- **HIGH — The 1,200-second timeout can leave an in-group helper running after unlock.** The per-command subprocess timeout kills the direct child. The outer runner kills the job group only on its own timeout or interruption, not when the installer returns a normal failure result. The proposed descendant test exercises the outer timeout, not this case; the manual route has no outer runner. Also, closed stdin alone does not detach a manual invocation from its controlling terminal (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:139`, `:147`, `:166`; `installer/run.py:127–146`, `:371–382`; `installer/helper_assets/schedule_runner.py:206–257`).
- **MEDIUM — The root and wiring tests miss the actual entry-point behavior.** With no parent flag, the root check runs after lock creation and can leave a root-owned state directory or lock file. The held-lock test specifies a two-argument fake even though the batch call passes `runner=`; two existing replay fakes likewise cannot accept the planned keyword (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:148–149`, `:180–192`; `installer/runlock.py:29–36`, `:56–70`; `tests/test_setup.py:1786–1795`, `:1901–1909`).

**Suggestions:** Verify lock handoff or acquire the lock rather than trusting the flag. Refuse root before creating the lock. Exercise a per-command timeout followed by an otherwise normal job exit, and require cleanup before continuing or unlocking. Fix fake signatures without weakening their assertions. Keep the documented vendor and new-session limits distinct from these controllable paths.

**Risk Assessment:** High. The overlap and process-lifetime claims are not established for either entry point.

## 35-06

**Summary:** Adds lock-free preview using the shared planner and a refresh service that holds its writes.

**Findings status:** H7 is addressed for cache and receipt persistence; M4 is partially addressed. The wider preview window is disclosed, but the preview and run also apply different confirmation rules to manager evidence.

**Strengths:** `hold_writes()` covers adoption, retirement, and cache persistence. The corrected scratch receipt path, aged cache fixtures, and exact positive controls make the no-write proof meaningful (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:164–166`; `installer/version_status.py:1356–1360`, `:1519–1528`, `:1575–1593`, `:2085–2104`; `tests/test_update_check_job.py:47–73`).

**Concerns:**
- **MEDIUM — Preview can label a failed manager report `would update`.** The preview uses `not stale` alone. Holding writes does not hide timestamps: the service returns the in-memory entries and snapshot. The same stale-manager guard can therefore be used with the seven-day release window, without writing anything or changing the chosen preview mechanism (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:118–120`, `:132`; `installer/version_status.py:698–710`, `:1789–1811`, `:2085–2104`).

**Suggestions:** Reuse the corrected run confirmation helper with the preview’s release-cache window and the same manager-evidence rule. Test a failed manager lookup in preview. Keep the no-write claim scoped to installer state unless the test also covers the outer `uv` launcher and checkout.

**Risk Assessment:** Medium. The write boundary is credible; what the preview says is eligible still needs correction.

## 35-07

**Summary:** Attempts one notification after tool updates or failures and carries the session bus address through the runner.

**Findings status:** M7’s adapter and result-normalization tests are materially improved. The nonstandard socket limit is explicitly documented. Production notifier injection is still not exercised by the recorder test.

**Strengths:** Counts and registry IDs match the adapter’s plain-text contract. Per-job bus forwarding reuses the existing runner path without widening the global environment (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:114–117`, `:153–160`; `installer/notify.py:1–5`, `:79–104`; `installer/helper_assets/schedule_runner.py:346–356`).

**Concerns:**
- **MEDIUM — The real adapter test can pass if production stops injecting the notifier.** The child explicitly inserts `notifier_for` into prebuilt deps and replaces `_schedule_run_deps`. That proves runner-to-adapter delivery, but bypasses the production constructor whose `notify=` wiring is part of the feature (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:117`, `:122`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:197`; `setup.py:531–549`).

**Suggestions:** Keep the real deps constructor for one recorder test and fake the services underneath it. Describe notification as an attempt, not guaranteed delivery; missing adapters and delivery failures leave the run result unchanged.

**Risk Assessment:** Low to medium. The notification rule is clear; real desktop delivery remains owner UAT.

## 35-08

**Summary:** Adds the preview command and limits to the Schedules detail panel and records the dated contract amendments.

**Findings status:** M8’s command and timer-only working-directory wording improve. The 80×20 promise remains only partially tested, and some documentation still overstates the contract.

**Strengths:** The proposed test inspects the rendered widget rather than `detail_text`. The row-specific branch also avoids disturbing Phase 34’s rendered permission and limits checks (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:105–114`; `installer/schedules_screen.py:460–465`, `:493–505`; `tests/test_schedules_view.py:929–951`).

**Concerns:**
- **MEDIUM — The second logical line is not necessarily the second rendered row.** The what-text wraps at 80 columns. With a three-line status, the two-row detail panel can lose the preview entirely; the planned assertion only checks the what-line in that case. Without status it checks `--plan`, not the complete copyable command. And the action’s limits text omits the record-health qualification required by the plan’s own truth statement (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:211`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:26`, `:107–113`; `installer/ui_common.py:70–92`).
- **MEDIUM — The amendments leave different versions of the same promise.** The architecture action says every command runs in the caller’s group while acknowledging separate sessions. The SPEC still says only opted-in users can run and that preview changes nothing, while 35-06 allows an explicit manual run with the timer off and narrows the preview guarantee. The deployed runner and the manual `setup.py` route really are different entry points (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:147–150`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-SPEC.md:86–91`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:28–29`; `installer/cursor_shim.py:134–145`; `setup.py:552–572`).

**Suggestions:** Assert the whole preview command at the promised viewport and either keep it visible with status or specify how to reveal it. Synchronize the operative SPEC, roadmap, requirements, and UI wording: timer opt-in versus explicit manual execution, notification attempt versus delivery, and the precise process and deduplication limits.

**Risk Assessment:** Medium. The risk is pinning claims the implementation does not make true.

## 35-09

**Summary:** Builds the disposable-container instrument for a real `uv` replacement, Ruff upgrade, and same-day rerun.

**Findings status:** H8–H10’s main revisions are present: older seeds, non-vacuous replacement checks, gated steps, and first-run handoff. C2 is correctly retained: instrumentation is not completion. The remaining gaps can still make the verdict wrong.

**Strengths:** Reusing `runner_argv` exercises the real nested launch shape. Requiring both a version change and executable hash change rejects a no-op, and the inherited teardown checks that the named container is gone (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:24–28`, `:122`; `installer/schedules.py:864–901`; `scripts/container-e2e-verify.sh:2972–2993`).

**Concerns:**
- **HIGH — `would update` does not identify `uv self update`.** Bootstrap accepts an existing PATH uv. Both a brew-owned uv and a standalone uv can produce the same preview line, but the service would run different commands. The inner bound also starts after the harness’s outer `uv run`, and `runner_argv` does not supply the generated unit’s environment (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:119–125`, `:134`; `scripts/container-e2e-verify.sh:431–438`, `:3033–3039`; `installer/schedules.py:904–914`; `installer/update.py:195–209`, `:512–555`).
- **HIGH — The rerun can pass on missing evidence or fail after correct behavior.** An omitted Ruff row with the same installed version does not distinguish “current” from a failed or unparseable lookup. And the rerun emits one new `start` and one new result, not two new results as the verdict asks (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:124`; `installer/version_status.py:662–709`, `:1079–1092`; `installer/manager_versions.py:129–155`, `:253–258`; `installer/helper_assets/schedule_runner.py:522–545`).
- **MEDIUM — The transcript cannot substantiate all of the claimed evidence.** The action gathers hashes and rc digests but prints versions, exit and changed filenames; the handoff JSON does not retain the digests. The harness persists what the driver prints. In addition, `install_one` rejects `ALREADY_INSTALLED`, so using it unconditionally for zip and unzip can fail a sound prerequisite setup (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:122–125`, `:134`, `:224`; `scripts/container-e2e-verify.sh:3044–3057`; `tests/e2e_landing_driver.py:412–431`; `installer/engine.py:213–219`).

**Suggestions:** Prove that the measured path is the standalone updater’s declared leaf and record the actual updater route. Use the unit-equivalent environment for the run, and bound the outer launch or prove its lock is uncontended and account for startup separately. Require fresh, valid Ruff-current evidence when its row is omitted. Persist the measured path, hashes and rc digests before rerunning; accept already-present prerequisites after verifying them. Label installer outcomes as such, not as vendor stdout.

**Risk Assessment:** High for sign-off. AUTOUPD-08 stays open until the revised instrument produces a valid real-run transcript.

## 35-10

**Summary:** Checks production dispatch and composition, closed tables, final gates, and the owner handoff.

**Findings status:** M9’s same-tree gate pair, named-summary enumeration, and complete clause inventory are addressed. The composition proof remains incomplete at the lock boundary. C2 is addressed in the sign-off language.

**Strengths:** Separating dispatch parity from composition is the right test split. Running both gates again after a repair also prevents two passing results from certifying different trees (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:96–100`, `:136–149`; `setup.py:531–566`; `Makefile:60–64`).

**Concerns:**
- **HIGH — The final integration test still expects an overlapping run.** Using an actual scratch lock improves fixture fidelity, but expecting the parent flag to allow mutation under an unrelated holder certifies the failure mode rather than the contract (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:96`, `:99`; `installer/schedule_run.py:148–163`; `installer/runlock.py:56–70`).
- **MEDIUM — The “worst-case” summary is only an all-clauses fixture.** Its first failed ID is `mmdc`; catalog IDs have no length bound in the loader. With a sufficiently long valid ID, the planned formatter preserves the head and trims only clauses, while the outer runner truncates the full result. This can hide a fixed degradation clause or make manual and timer results differ (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:100`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:153`, `:162`; `installer/model.py:609–619`; `installer/helper_assets/schedule_runner.py:130–135`, `:363–376`).

**Suggestions:** Test a verified parent handoff and refusal under an unrelated holder. Bound the variable fields before allocating room to fixed clauses, then test manual and runner output with a long valid ID. Bind any AUTOUPD-08 pass to the tested revision; invalidate it after a repair that changes the exercised path.

**Risk Assessment:** Medium for the closeout machinery, high if it is used to certify the current lock contract.

## Cross-plan assessment

1. **Fix lock ownership and process lifetime together.** The batch must not start under an unrelated lock holder or release its own lock while a timed-out command is still mutating. Make 35-01’s tracer, 35-05’s timeout and lock tests, and 35-10’s final composition test prove that same contract.
2. **Make authorization and accounting follow the actual work.** Keep the pure planner and two-pass design. Fix how failed refreshes, changed ownership, Cursor follow-up, pnpm replay, and partial mutations cross the service boundary. A recent timestamp, a planned owner, and a formatted `ok:` line are each insufficient on their own.
3. **Keep proof and implementation status separate.** The revised container instrument must identify the updater, persist its measurements, and distinguish current from unobserved on rerun. A green suite, `not run`, and `UNPROVEN` all leave AUTOUPD-08 open.
4. **Fix the shared executor wrapper once.** All ten plans prescribe GNU `df --output=pcent` while requiring macOS-compatible commands. Use a portable disk check that fails closed if usage cannot be read, while retaining the scratch cleanup and final-gate TMPDIR rules (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:99`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:73–77`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:54–58`).

### Status: Issues Found — revise and re-review

No tests, updaters, timer units, desktop notifications, or containers were run. Actual uv replacement, shell-file effects, timer delivery, and desktop delivery remain unverified.

---

## Lane Log (convergence cycle 3, plans at ba9c8456)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 09:31 | opencode-referee-one | one-shot probe | OK |
| 09:31 to about 10:30 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, cycle 2 findings supplied | exit 0 |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 3 concerns (LAST cycle: cap rule)

Cycle 3 of 3. HIGH count fell 10, then 8, now 5. The cap is three cycles, so there is no cycle 4: replan round 3 is the last revision and executes without a re-review; anything found afterwards goes to the post-execution fix round. Claims that rest on repository code are for the planner to verify and fix or reject with a stated reason in the Round 3 ledger. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| L1 (35-01) HIGH | Lock metadata is not proof of a handoff: `held_by` compares the supplied job and pid with `holder()`, which reads text and checks the pid is alive; it does not check the kernel lock (`installer/runlock.py:56-98`); an unrelated invocation naming the live holder would pass | Real by the referee's reading; planner verifies. DECISION: the child additionally proves the KERNEL lock is held: a non-blocking acquire attempt on the lock file must fail as busy (if it succeeds nobody holds it: release it and refuse with the fixed line); the recorded job and pid must match a live holder as before; test no kernel lock held, text naming a live pid without a held lock, and wrong job/pid/path all refuse. State the residual honestly: the lock is advisory and a same-user process that holds the real lock and names itself can pass (same user trust boundary). |
| L2 (35-01) MEDIUM | The timer busy test can wait two hours: the wait seam is unspecified | DECISION: shorten both wait constants as `tests/test_schedule_runner.py:734-747` does. |
| P1 (35-02) MEDIUM | The exact-refusal fixture asks for a pinned `github_release`; `pinned_method()` only knows `app` and `tarball` (`installer/download.py:178-187`) | DECISION: use an `app` or `tarball` fixture for the pinned-refusal case. |
| S1 (35-03) MEDIUM | The writer can save a record its own reader rejects (no write-side cap) | DECISION: enforce the reader's cap before replacement (as `installer/version_cache.py:221-245`); a record that would exceed it reports `not saved`; test it. |
| S2 (35-03) MEDIUM | The smoke failure test calls `_update_tool`, which does not write the record; persistence is in `_run_update_row` | DECISION: test through the public dispatcher (`tests/test_schedule_update.py:306-332`). |
| A5 (35-04) HIGH | A confirmed tool id can authorize an update to a DIFFERENT copy: Ruff reported outdated by uv can be brew-owned at execution; if brew completed, that copy is upgraded without brew evidence (`installer/version_status.py:662-710`; `installer/update.py:195-209,660-714`) | Real by the referee's reading; planner verifies. DECISION: confirmed evidence is bound to the route that produced it: record (id, owner) with each confirmed id; the guard refuses with `skipped: owner changed since the evidence` when the fresh owner differs; test the Ruff uv-to-brew case through the real service. |
| A6 (35-04) HIGH | Planner-skipped managers are marked complete without checking their failed upstream: brew fails, brew-owned uv is skipped as updated today, Ruff's owner and `requires` point to uv, and nothing carries the failure; the same rule can authorize a manager whose fresh owner is on a cycle-blocked branch | DECISION: a skipped manager counts as complete only when none of its upstream managers failed or is cycle-blocked; failed and cycle-blocked states propagate through skips to dependents with a fixed reason; test brew failed then uv skipped then Ruff. |
| A7 (35-04) MEDIUM | The daily lookup is fixed at run start but writes sample the day after each outcome | DECISION: look up the daily record per entry at decision time with the injected clock; test midnight. |
| A8 (35-04) MEDIUM | pnpm accounting is wider than self-update replay: an ordinary pnpm-owned `mmdc` update also submits Puppeteer in the same command | DECISION: document the grouped-package effect in the accepted limit (W6, SPEC amendment, threat entry); the tally counts planned tools only. |
| T1 (35-05) HIGH | The shutdown test bypasses the runner's real stop sequence: production `_stop()` waits for the outer uv process then SIGKILLs the group as soon as it exits; if uv exits on SIGTERM before the installer finishes forwarding and cleanup, the installer is killed while the command's separate group continues; the inner cleanup has an uncapped `wait()` and no failure disposition when the group poll expires (`installer/helper_assets/schedule_runner.py:199-217,227-257`) | Real by the referee's reading; planner verifies. DECISION: drive the runner's real `_stop` in the test; give the installer's cleanup a hard cap and a defined failure disposition (kill the command group with SIGKILL, log a fixed line, exit failed); the runner's `_stop` waits for the installer's cleanup budget before it SIGKILLs the group; no uncapped waits. |
| T2 (35-05) MEDIUM | Root timer entry still creates state before refusal: the stdlib entry has created and acquired the lock, written `start` and launched uv before `run_schedule` checks root | DECISION: refuse root in the stdlib runner for `update-all` before the lock, the `start` line and the launch; test no lock and no start line. |
| T3 (35-05) MEDIUM | Manual-route queries still inherit stdin: `run_query` supplies neither `stdin=DEVNULL` nor a new session | DECISION: close stdin for the update-all queries (an injected query runner or a `stdin=DEVNULL` default where safe), else document the residual with a test. |
| V1 (35-06) MEDIUM | A newer failed release lookup does not invalidate the preview's cached evidence (`checked_at` two days old plus a newer `failed_at`) | DECISION: the confirmation helper treats an entry whose `failed_at` is newer than its `checked_at` as unconfirmed in both run and preview; test it. |
| V2 (35-06) MEDIUM | Preview can print `would update` for a receipt-drift tool the run refuses | DECISION: preview mirrors the drift refusal when it can be computed without writing, else adds a fixed note that drift refusals are decided at run time. |
| N1 (35-07) LOW | The notifier fixture relies on scratch PATH, but the real probe can execute an absolute ownership path | DECISION: isolate the probe seam in that fixture. |
| U1 (35-08) MEDIUM | The 80x20 promise omits an `n/a` row (two logical lines) and the longest status (four rows) | DECISION: test those two cases too, or state in the plan how the command is revealed there. |
| U2 (35-08) MEDIUM | The amendments do not replace contradictory operative wording: the group claim, and the append-only SPEC amendment leaves constraints and the acceptance checklist saying preview changes nothing and every non-empty run notifies | DECISION: the executor-side edits rewrite the contradicting operative lines (dated, marked as amended) as well as appending; the group claim is reworded to say queries and the notifier are not in a command group. |
| C1 (35-09) HIGH | An independent PyPI lookup can certify a rerun whose installer lookup failed: production uses `uv tool list --outdated`, a failed or unparseable report makes status unknown and omits the row | Real. DECISION: an omitted dependent needs the INSTALLER's own successful current evidence (the parsed outdated report that confirms the dependent is current); PyPI may add a cross-check, never replace it; otherwise `AGAIN_UNPROVEN`. |
| C2 (35-09) MEDIUM | Route evidence measures the realpath of a symlinked declared leaf; the unit keeps the unresolved path; the transcript lacks the actual plan and shared-log lines | DECISION: record lstat and readlink of the declared leaf and measure it unresolved; keep the actual plan and shared-log result lines in the transcript. |
| C3 (35-09) MEDIUM | The stubbed step test misses the environmental exit (`landing_step` exits 2 and later steps never emit skip markers) | DECISION: emit the skip markers on an environmental exit too and test it. |
| G1 (35-10) MEDIUM | The gate SHA does not identify the container input (the harness streams tracked and untracked files; `setup.py` and the registry are not in the list) | DECISION: record HEAD plus a digest of the porcelain status (untracked included) with the transcript and add `setup.py` and `installer/registry.toml` to the invalidating paths. |
| G2 (35-10) MEDIUM | The composition test leaves real seams live (platform detection, probes, notifier) | DECISION: isolate those seams in the composition fixture. |
| G3 (35-10) LOW | The summary parity fixture truncates one repeated character, missing a cut right after a space | DECISION: add a multiword reason that is cut at a space boundary. |
| X | Final gates with the default TMPDIR | Standing ruling; not raised. |

## OpenCode Review (opencode-referee-one), cycle 3

Using the plan-review checklist and Ponytail Review to assess all ten plans, with Codebase Memory and direct source reads to verify the proposed behavior. This is a read-only review: I won’t run updates, timers, notifications, or containers.
The third revision improves the fixtures, but two safety claims are still unproven: a live PID in the lock file is not proof of a held lock, and the timeout test does not exercise the runner’s full stop sequence. I’m checking how those gaps affect the final sign-off.
# Phase 35 plan review — convergence cycle 3

**Verdict: revise before execution.** The current plans improve the off-by-default row, planner purity, receipt-safe preview, and container evidence. The remaining blockers are at the boundaries that authorize unattended changes: the child does not prove it holds the run lock, confirmed version evidence can authorize an update to a different installed copy, and the timeout test does not exercise the runner’s actual shutdown sequence. The container rerun can also pass without showing that the installer successfully checked Ruff.

I reviewed the ten current plans against the repository source, assuming one developer’s machine with timers and manual commands sharing it. The findings below describe proposed behavior, not observed Phase 35 runtime failures.

## 35-01

**Summary:** Adds the opt-in 03:00 row, runner dispatch, lock handoff, and ninth-row layout.

**Findings status:** The tracer now uses the runner’s actual arguments and checks the child’s lock path. The composed Policies check, stale-unit reconfiguration case, and portable disk check address the previous findings. The lock handoff is still not proven.

**Strengths:** The per-row default changes only the undecided branch. Recorded on/off decisions still take their existing paths, and a distinct job kind avoids the per-tool missing-target cleanup (`installer/schedules.py:1561–1575`, `:1598–1638`, `:1704–1725`).

**Concerns:**
- **HIGH — Lock metadata is not proof of a lock handoff.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:148–162`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md#L148) compares the supplied job and PID with `holder()`. That function reads text and checks whether the PID is alive; it neither checks the kernel lock nor ties the caller to the locker. An unrelated invocation naming the current `update-all` holder would still pass. The tests cover a wrong job, PID, or path, but not this case (`installer/runlock.py:56–98`).
- **MEDIUM — The timer’s busy test can wait two hours.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:149`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md#L149) asks for a held-lock test without specifying the wait seam. The runner immediately refuses an installer-held lock but waits on a scheduled holder; the existing test shortens both wait constants (`installer/helper_assets/schedule_runner.py:69–75`, `:266–299`; `tests/test_schedule_runner.py:734–747`).

**Suggestions:** Use actual lock ownership or a verifiable handoff that survives the `uv` wrapper. Test matching metadata without a held lock and an unrelated caller naming a real same-job holder. Use the existing short-wait fixture for scheduled contention.

**Risk Assessment:** Low for seeding and layout; high for mutual exclusion.

## 35-02

**Summary:** Defines the pure planner, manager order, owner groups, and exclusion rules.

**Findings status:** The missing-evidence cask case and cycle propagation to managers owned by a cyclic branch are addressed in the planner. Plan 35-04 can still undo the cycle protection at execution time.

**Strengths:** Ownership edges are the right input: `_RANK` ranks install methods, not installed owners. The plan supplies both required resolver callbacks and keeps dragged-in dependencies from becoming extra update targets (`installer/resolve.py:14–31`; `installer/ownership.py:82–97`; `installer/deps.py:40–55`, `:123–153`).

**Concerns:**
- **MEDIUM — The exact-refusal fixture uses a method that cannot be pinned by the real predicate.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md:178`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-02-PLAN.md#L178) calls for a pinned `github_release`. `pinned_method()` only recognizes `app` and `tarball`, so the requested fixture cannot produce the stated refusal (`installer/download.py:178–187`; `installer/update.py:315–321`).

**Suggestions:** Use a real pinned tarball or app fixture. Keep the planner pure and carry its cycle disposition into the executor rather than rediscovering it there.

**Risk Assessment:** Low for planner structure; medium for refusal and cycle coverage as composed.

## 35-03

**Summary:** Adds the daily record, link-safe run log, and deduplication for per-tool rows.

**Findings status:** The plan now records known mutations followed by smoke, probe, or shim failure, and samples the record date after the update. Failed commands with unknown mutation effects remain a named limit. The batch’s midnight lookup is still open in 35-04.

**Strengths:** The reader type-checks values before using them. The writer replaces the final directory entry rather than following a symlink, and log appends follow the existing nonblocking open and descriptor-type check pattern (`installer/atomic.py:58–73`, `:186–215`). The two smoke-check changes target calls that really occur after mutation (`installer/executors.py:573–614`; `installer/update.py:437–448`).

**Concerns:**
- **MEDIUM — The writer can save a record its own reader rejects.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:155–157`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md#L155) caps reads but not serialized writes. A large enough valid daily record can be reported saved and then read as unhealthy-empty, losing all same-day evidence. The version-cache writer already enforces its cap before replacement (`installer/version_cache.py:221–245`).
- **MEDIUM — The smoke failure test calls a helper that does not write the record.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md:142`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-03-PLAN.md#L142) invokes `_update_tool` and also expects a persisted record; the same plan leaves persistence to `_run_update_row` at lines 159–160. The existing schedule tests exercise the public dispatcher (`tests/test_schedule_update.py:306–332`).

**Suggestions:** Enforce the byte cap before replacing the record and preserve the prior file on overflow. Drive the smoke test through the per-tool row, then verify that the batch skips the recorded tool.

**Risk Assessment:** Medium. The file primitives are sound for the stated final-entry threat; the accounting tests need to prove the actual write path.

## 35-04

**Summary:** Runs managers and dependents in two passes, guards fresh ownership, and logs and records results.

**Findings status:** The newer-manager-failure check and guarded Cursor skip address the previous cases. The second-pass fallback is narrower. The fresh-owner gate still does not bind version evidence to the target it mutates.

**Strengths:** The guard sits inside `UpdateService`, before receipt checks, pnpm capture, and mutation, while preserving `run(target)` for existing callers. The backfill rule matches the refresh service: successful manager fields get the new stamp; failed fields can retain older data (`installer/update.py:660–722`; `installer/version_status.py:1768–1811`).

**Concerns:**
- **HIGH — A confirmed tool ID can authorize an update to a different copy.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:146–150`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md#L146) confirms IDs, then checks the fresh owner only for exclusions, failures, and stage order. Ruff reported outdated by uv can switch to a Brew-owned copy before execution; if Brew completed, that copy can be upgraded without Brew evidence that it is outdated. Ruff has both routes, status is owner-specific, and dispatch uses the fresh owner (`installer/registry.toml:733–764`; `installer/version_status.py:662–710`; `installer/update.py:195–209`, `:660–714`).
- **HIGH — Some skips erase a manager failure from the downstream decision.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:147–150`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md#L147) marks every planner-skipped manager complete without checking its failed upstream. If Brew fails today, Brew-owned uv is skipped as already updated today, and Ruff’s owner and `requires` still point to uv, nothing records the failure inherited through uv. The same completion rule can authorize a manager whose fresh owner is on a cycle-blocked branch (`installer/registry.toml:733–741`; `installer/update.py:418–448`).
- **MEDIUM — The batch’s daily lookup is fixed at run start.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:148–150`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md#L148) samples the day once for skips but after each outcome for writes. A dependent recorded yesterday can still be skipped after midnight. The existing immediate post-result flow offers a clear per-entry decision point (`installer/schedule_run.py:50–68`).
- **MEDIUM — The pnpm accounting limit is wider than self-update replay.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md:149–150`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-04-PLAN.md#L149) accounts for one planned tool per update, but an ordinary pnpm-owned `mmdc` update also submits Puppeteer in the same command. That peer can be current, unconfirmed, or recorded today (`installer/registry.toml:2804–2819`; `installer/executors.py:552–573`; `installer/update.py:432–436`).

**Suggestions:** Bind confirmation to the owner and package or owning method that supplied it. Test a changed route with **both** managers successful. Distinguish policy skips from failure-blocked or cyclic managers, and carry the failure through skipped intermediate managers. Recheck the calendar day at dispatch. Keep the replay decision, but document and test the grouped-update limit too. Say **zero mutation argv**, not zero subprocesses: the existing path probes versions and resolves ownership before mutation (`installer/schedule_run.py:54–59`; `installer/version_status.py:1693–1714`).

**Risk Assessment:** High. The proposed guard can still authorize an unattended update that the evidence or failure rules do not support.

## 35-05

**Summary:** Adds command bounds, signal forwarding, runner injection, and the root and refusal checks.

**Findings status:** Dedicated command groups address the direct-child timeout problem. Root refusal now precedes lock acquisition in the installer child. Neither the complete timer shutdown nor root refusal before the timer’s own lock is established.

**Strengths:** Passing the bounded runner to pnpm replay and herdr reload closes two existing bypasses without adding another updater (`installer/compose.py:347–374`, `:433–458`). The plan correctly treats the no-sudo scan as a regression check, not proof of vendor behavior (`installer/run.py:48–58`).

**Concerns:**
- **HIGH — The shutdown test bypasses the runner’s real stop sequence.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:130,139`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md#L130) sends SIGTERM directly and checks afterward. Production `_stop()` waits for the **outer uv process**, then sends SIGKILL to its group as soon as that process exits. If uv exits on SIGTERM before the installer finishes forwarding and cleanup, the installer can be killed while its command’s separate group continues. The inner cleanup also contains an uncapped `wait()` and no specified failure disposition when the group poll expires (`installer/helper_assets/schedule_runner.py:199–217`, `:227–257`).
- **MEDIUM — Root timer entry still creates state before refusal.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:173–185`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md#L173) checks root inside `run_schedule`. The stdlib timer entry has already created and acquired the lock, written `start`, and launched uv by then (`installer/helper_assets/schedule_runner.py:289–309`, `:323–346`, `:522–545`).
- **MEDIUM — Some manual-route queries still inherit stdin.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md:27–30`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-05-PLAN.md#L27) correctly lists separate query sites, but a timeout does not make those calls noninteractive. `run_query` supplies neither `stdin=DEVNULL` nor a new session, and production refresh uses it (`installer/run.py:449–472`; `installer/version_status.py:1278–1291`).

**Suggestions:** Test the actual runner timeout with a wrapper that exits before the installer’s cleanup finishes. Make the real stop path wait for cleanup before releasing mutual exclusion. Reject root at both entry points, and close input for batch queries that can otherwise read from the manual caller’s terminal.

**Risk Assessment:** High. The lock and process lifetime need to be proven together.

## 35-06

**Summary:** Adds a lock-free preview with the shared planner and held installer writes.

**Findings status:** Preview now shares manager-evidence confirmation with the real run. The receipt and version-cache fixtures have positive controls. Two other reasons for preview/run disagreement remain.

**Strengths:** `hold_writes()` fits the existing refresh service: it queues cache and snapshot saves, and adoption and retirement have explicit held paths (`installer/version_status.py:1328–1360`, `:1513–1528`, `:1575–1593`, `:2085–2104`).

**Concerns:**
- **MEDIUM — A newer failed release lookup does not invalidate the preview’s cached evidence.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:122,134`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md#L122) shares the manager backfill check, but not an equivalent check for per-tool releases. A failed run refresh can retain a two-day-old `checked_at` and add a newer `failed_at`. Preview accepts the older date under seven days even though the run rejects it under twenty hours, and `fresh_ids()` only reads `checked_at` (`installer/version_status.py:396–442`; `installer/version_cache.py:248–267`; `installer/update_check.py:148–178`).
- **MEDIUM — Equal version evidence does not establish equal skip reasons for receipt drift.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md:120,134`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-06-PLAN.md#L120) shares the refusal helper, but `UpdateService` has a separate installer-owned receipt-drift gate. Preview can print `would update` for a changed file that the run refuses, even though refresh already observed the drift (`installer/version_status.py:1513–1531`; `installer/update.py:670–687`; `tests/test_update.py:1849–1876`).

**Suggestions:** Reject release evidence superseded by a failed lookup without changing the seven-day window for clean evidence. Use the pass’s receipt-drift evidence in preview, keeping the live recheck. Add a manager-snapshot positive control alongside the existing cache and receipt cases.

**Risk Assessment:** Medium. The write boundary is credible; authorization and parity need tighter tests.

## 35-07

**Summary:** Attempts one desktop notification after a run with an update or failure.

**Findings status:** The recorder now exercises production notifier construction. The `XDG_RUNTIME_DIR` limit is explicit, and delivery is described as an attempt.

**Strengths:** Counts and registry IDs meet the adapter’s plain-text contract. The per-job bus variable uses the existing forwarding path without widening the global environment (`installer/notify.py:1–5`, `:79–104`, `:125–143`; `installer/helper_assets/schedule_runner.py:346–357`).

**Concerns:**
- **LOW — Isolate the notifier fixture at the probe seam too.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md:118`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-07-PLAN.md#L118) relies on scratch `PATH` to make probes inert. The real constructor wires the real probe, which can execute an absolute ownership path without looking at `PATH` (`setup.py:531–549`; `installer/version_status.py:472–494`, `:511–523`).

**Suggestions:** Keep the real constructor and adapter, make `PATH` exclusive, and fake version-probe output explicitly. Preserve the scratch recorder as the only notification executable.

**Risk Assessment:** Low. Actual desktop delivery remains owner UAT.

## 35-08

**Summary:** Adds the copyable preview to Schedules and records the operative contracts and limits.

**Findings status:** The full-command rendered test and record-health qualification improve the earlier UI plan. The documentation still overstates what the runner and the daily record guarantee.

**Strengths:** Testing the rendered widget rather than its uncut text matches the actual wrap-and-truncate path and the existing check-row visibility tests (`installer/schedules_screen.py:460–505`; `installer/ui_common.py:70–92`; `tests/test_schedules_view.py:929–951`).

**Concerns:**
- **MEDIUM — The 80×20 promise omits unavailable rows and the longest allowed status.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:106–115`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md#L106) tests a healthy row with up to three status lines. An `n/a` row starts with two logical lines, and status can occupy four rows. Either can displace the command even though manual preview is still usable (`installer/schedules_screen.py:486–499`; `installer/ui_common.py:70–103`).
- **MEDIUM — The amendments do not replace contradictory operative wording.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md:149–152`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-08-PLAN.md#L149) says every command has its own group, though queries and the notifier do not. Its append-only SPEC amendment also leaves the existing constraints and acceptance checklist saying preview changes nothing and every non-empty run notifies (`installer/run.py:449–472`; `installer/notify.py:93–101`, `:114–121`; `.planning/phases/35-opt-in-auto-update-package-managers-first/35-SPEC.md:86–108`).

**Suggestions:** Assert the complete command on one rendered row in the promised states, or explicitly say how to reveal it. Put the qualified contracts in the operative SPEC and acceptance statements, not only in a later appendix. Scope the process-group claim to `update_all_runner` and distinguish cross-row deduplication from the retained six-hour cadence.

**Risk Assessment:** Medium. The UI concern is discoverability; the documentation concern is promising protections the code does not provide.

## 35-09

**Summary:** Builds the disposable-container proof of standalone uv replacement, Ruff upgrade, and the same-day rerun.

**Findings status:** The older seed, version-plus-hash check, route preconditions, evidence handoff, and gated steps materially improve the instrument. The rerun can still produce a false pass.

**Strengths:** Requiring both the version and executable hash to change rejects a no-op. Reusing `runner_argv` and the unit environment tests the nested launch shape without claiming timer delivery; existing teardown verifies whether the named container is gone (`installer/schedules.py:864–914`; `scripts/container-e2e-verify.sh:2975–2993`).

**Concerns:**
- **HIGH — An independent PyPI lookup can certify a rerun whose installer lookup failed.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:119,129`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md#L119) accepts an absent Ruff row when installed Ruff equals PyPI’s latest. Production uses `uv tool list --outdated`; a failed or unparseable report makes status unknown and also omits the row. The rerun would pass even though the installer never established that Ruff was current (`installer/manager_versions.py:129–157`, `:253–258`; `installer/version_status.py:662–709`, `:1079–1092`).
- **MEDIUM — Route and transcript evidence still fall short of the claimed proof.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:116–129`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md#L116) accepts realpath equality, including a symlinked declared leaf, then launches and hashes the canonical target. The unit retains the unresolved executable path, while the updater invokes the declared leaf. Replacing the leaf can leave the driver measuring the former target. The transcript should also retain the actual plan and shared-log results, not just derived verdict markers (`installer/schedules.py:728–733`, `:864–901`; `installer/update.py:512–555`; `scripts/container-e2e-verify.sh:3033–3057`).
- **MEDIUM — The stubbed step test misses the environmental exit.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md:159–168`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-09-PLAN.md#L159) tests a step returning failure. The real `landing_step` exits 2 on a recognized environment failure, so later steps correctly do not run, but the loop never emits their skip markers (`scripts/container-e2e-verify.sh:3044–3057`).

**Suggestions:** For an omitted Ruff row, require the rerun’s own fresh, valid uv inventory and outdated report, with no refresh fallback. Check installed Ruff also stays unchanged when explicitly skipped. Require a regular, non-symlink standalone leaf for this fixture, preflight the older uv’s actual outdated output through the production parser, and persist both runs’ evidence in a run-specific transcript. Pin the exit-2 behavior using the real `landing_step` over a fake driver.

**Risk Assessment:** High for sign-off. `UNPROVEN`, `not run`, and a green host suite all leave AUTOUPD-08 open.

## 35-10

**Summary:** Checks production dispatch and composition, the summary budget, final gates, and the evidence handoff.

**Findings status:** The separate dispatch and composition tests, same-tree gate pair, and long-ID cap address earlier findings. The composition still inherits the lock gap, and the container result is not yet bound to what the harness copied.

**Strengths:** The reachability check starts from production entry points and follows runtime imports, so it tests wiring rather than merely checking file existence. The closeout also keeps the two final gates distinct and reruns them as a pair after repairs (`tests/test_reachability.py:115–162`, `:196–197`; `Makefile:60–64`).

**Concerns:**
- **MEDIUM — The gate SHA does not identify the container input.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:27`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md#L27) records a gate SHA and lists selected invalidating paths. The harness streams tracked **and untracked** working-tree files; the list also omits exercised inputs such as `setup.py` and the registry. A green gate pair can therefore accompany a transcript from different inputs (`scripts/container-e2e-verify.sh:324–340`, `:3019–3028`; `setup.py:531–566`).
- **MEDIUM — The composition test leaves real host seams live.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:100`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md#L100) patches only service construction. Real Linux detection can fail under an empty scratch PATH, and the real constructor still wires version probes and the notifier (`installer/platform.py:43–79`; `setup.py:531–565`).
- **LOW — The summary parity fixture misses a whitespace boundary.** [`.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md:101`](.planning/phases/35-opt-in-auto-update-package-managers-first/35-10-PLAN.md#L101) truncates a single repeated character. A multiword reason can be cut immediately after a space; the manual route prints it, while the timer strips it (`.planning/phases/35-opt-in-auto-update-package-managers-first/35-01-PLAN.md:159`; `setup.py:560–566`; `installer/helper_assets/schedule_runner.py:363–376`).

**Suggestions:** Record the container run’s own full SHA and transcript from a clean checkout, separately from the final gate SHA. Keep the real deps constructor but fake detection, probe output, and notification at their leaf seams. Add the actual-lock negatives from 35-01 and an exact-output case with a multiword reason cut at a space.

**Risk Assessment:** Medium for closeout; high if the current composition test is treated as proof of mutual exclusion.

## Cross-plan assessment

1. **Fix mutual exclusion and shutdown together in 35-01, 35-05, and 35-10.** The same proof must hold through the real wrapper chain: a batch starts only under the lock, and that lock is not released while a command the runner is responsible for can still mutate.
2. **Make authorization follow the installed copy in 35-02, 35-04, and 35-06.** Keep the pure planner and two passes. Bind evidence to the route that produced it, preserve failed and cycle-blocked states across stages, and distinguish planned tool counts from grouped package effects.
3. **Keep the container proof separate from the implementation gates.** Require the actual replacement, the installer’s own successful Ruff evidence, and a transcript tied to the tested input. Do not use synthetic verdicts or a clean unit suite to close AUTOUPD-08.

### Status: Issues Found — revise and re-review

No files were changed. No tests, updaters, timers, notifications, or containers were run; actual uv replacement, shell-file effects, and desktop and timer delivery remain unverified.
