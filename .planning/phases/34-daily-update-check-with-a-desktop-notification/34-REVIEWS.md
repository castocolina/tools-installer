---
phase: 34
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-21T23:40:00Z
plans_reviewed: [34-01-PLAN.md, 34-02-PLAN.md, 34-03-PLAN.md, 34-04-PLAN.md, 34-05-PLAN.md, 34-06-PLAN.md, 34-07-PLAN.md, 34-08-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 34

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log (convergence cycle 1, plans at 8c3d1435)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 19:48 | opencode-referee-one | one-shot probe | OK |
| 19:48 to about 20:30 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null` | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 1 concerns

Cycle 1 of 3. Plan-internal findings were checked against the cited plan lines; claims that rest on repository code (`installer/atomic.py`, `installer/run.py`, the runner's 300-character cap, the schedules tests) are for the planner to verify against source and fix or reject with a stated reason in the Round 1 ledger. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (34-01) | The allowed test edits omit failures caused by the default-on eighth row (mid-pass report, moved-checkout restart sequence, legacy adoptions, first-enable failure, concurrent reconcile, partial sweeps; the damaged-state sweep's explicit basename list) | Real by the referee's reading (`tests/test_schedules_lifecycle.py:147-152,284-309,329-344,400-430,478-492,695-725,910-928`; `tests/test_schedules_handover.py:313-327`); planner verifies. DECISION: run the affected test files first, list the exact fixture and expectation changes as explicit exceptions with reasons; where a test isolates an old row, decide the new row OFF in the fixture rather than weakening an old assertion; add the new row to the damaged-state basename list. |
| M1 (34-01) | Ordinary last-off does not sweep the notified state (only uninstall cleanup does) | By design: the state file is tiny and the off decision persists. DECISION: no change; state the limit in the plan and the docs; test the uninstall sweep with a planted file. |
| M2 (34-02) | A set `XDG_RUNTIME_DIR` whose bus is missing never tries `/run/user/<uid>/bus` | Real for direct callers. DECISION: fall back to `/run/user/<uid>/bus` when it is a socket; test the case. |
| L1 (34-02) | The notifier accepts arbitrary strings while the no-`--`/markup-safety argument relies on Phase 34's own message construction | Document the caller contract (summary and body are plain text built by the caller); keep golden argv; macOS delivery stays owner UAT. |
| M3 (34-03) | The cap and failure tests cover only GitHub-backed fixtures; npm, Bun, pnpm and uv paths differ | Real. DECISION: add one mixed GitHub/npm/Bun fixture for the shared budget and failure plumbing; describe the cap as a resolver-call cap and say which manager-query failures are visible. |
| L2 (34-03) | The concurrency note overstates what a same-service test proves for two processes | Reword: atomic replacement prevents a torn file, not the loss of at most one entry. |
| H2 (34-04) | No self-update clause is emitted: the plan adds `tools-installer` to the set and count but appends an installer clause only on a skip, while the SPEC requires a behind clause | Real (`34-SPEC.md:47-50`; `setup.py:547-561`). DECISION: emit the behind clause on the result line independently of notification delivery; test it with and without a failed notifier. |
| H3 (34-04) | The notified file is written with `atomic_write_text`, which resolves a symlink and overwrites its target, though the reader rejects links | Real by the referee's reading (`installer/atomic.py:36-78,186-215`); planner verifies. DECISION: write the notified file with `atomic_replace_entry` (replaces the link, never writes through it); test that the link is replaced and its target unchanged. |
| H4 (34-04) | The real-service test expects only `update-check.json`, but a normal pass also saves `versions.json` and can adopt or retire receipts | Real. DECISION: name the allowed writes (`update-check.json`, the version cache `versions.json`, receipt housekeeping through the existing path) and test exactly those, including an adoptable or stale receipt; the update-executor spy still sees zero calls; never hide the cache outside the scratch HOME. |
| H5 (34-04) | Git isolation and credential protection are overstated: user and repo Git configuration stays in effect, raw command diagnostics are logged after line sanitization only (a credential-bearing remote URL could appear), and the `cat-file` handler treats every `CommandError` (timeout, launch failure) as proof the object is absent | Real by the referee's reading (`installer/run.py:61-77,181-195`); planner verifies. DECISION: log only fixed failure categories (for example `installer check skipped: git query failed`), never raw transport diagnostics; distinguish a missing object (the specific exit code) from operational errors (those skip); state the isolation limit honestly; tests with a planted credential-bearing URL. |
| M4 (34-04) | The oldest-first sort can crash on a naive timestamp (`TypeError` against an aware one) and the same 20 oldest failures can consume every daily slot after the backoff | Real. DECISION: reuse the cache's timestamp validation (`installer/version_cache.py:70-92,125-144`); sort by the latest attempt time (the newer of `checked_at` and `failed_at`) so failures rotate; test both. |
| M5 (34-04) | Two tests conflict with the control flow (an all-clauses test needs a failed notification AND a failed save but no save is attempted after a notification failure; `failed: boom` expects `CommandError.detail` while the action takes the first line of `str(exc)`) | Real plan-internal defects. DECISION: split the mutually exclusive clause tests and align the `failed:` test with the real source of the text. |
| M6 (34-04) | The reachability check greps a substring instead of verifying the exact orphan list | Real. DECISION: the named check compares the exact orphan list (only `installer.update_check`); the one-plan red exception stays (the wiring is plan 34-05). |
| H6 (34-05) | The runner reuses `_update`'s 300-character sanitize of the whole result, so an early long lookup reason can cut off the installer or notifier clause | Real by the referee's reading (`installer/helper_assets/schedule_runner.py:102,129-134,345-358`); planner verifies. DECISION: bound each clause in `update_check` (a per-clause budget that leaves room for every required clause within the runner's single-line limit) and add a hermetic composition test passing a real check result with long diagnostics and a failing notifier through the runner log path. |
| M7 (34-05) | The reused outer runner launch does not close stdin; the direct parser route bypasses the runner's token filter while the production fetcher reads token variables | Pin closed stdin for the check job. The direct manual CLI route may use the user's own token (D-11's anonymity is by construction on the runner path): document it; do not change interactive fetch behavior. |
| H7 (34-06) | The macOS permission sentence comes after `what`, `last` and `times` in the row detail, so at the planned detail height it is cut off on screen although the test reads the uncut string | Real by the referee's reading (`installer/schedules_screen.py:443-448,474-482`; `installer/ui_common.py:70-92`). DECISION: put the permission sentence FIRST in this row's detail (the limits last), and test the rendered widget at 80x20 with a row that has a prior log result. |
| L3 (34-06) | The no-count promise is broader than the UI: `last:` carries the count | Apply the promise to the explanatory copy only. |
| M8 (34-07) | The container verdict is weaker than promised: the harness accepts `skipped` and any Last cell other than `never`; the `--direct` route bypasses the OFF check and prints a different marker | DECISION: for the check-updates pair require the expected `ok:` result prefix and a matching Last cell; give the `--direct` fallback its own pass criteria and record the unit/calendar/teardown proof as not exercised in that mode; both orchestrator-only. |
| M9 (34-08) | The consistency tests do not pin `Notifier`; the one-way key subtraction passes if the runner drops a shared key; a literal return-annotation comparison ignores postponed annotations | DECISION: assert equality against the unit keys plus the two runner-only keys, keep the explicit bus exclusion from the unit keys, exercise the notifier seam through a typed fake, resolve annotations before comparing. |
| C1 (cross) | "At most one notification a day" versus a changed-set test that allows a second notification on a second run, with a date-less state | DECISION: the daily limit describes the timer cadence; manual runs, catch-up and retiming may notify again when the set changed (the shrinking-set rule stays); state this in the docs and the row detail and test the stated contract. |
| C2 (cross) | Wave 1 registers a default-on unit whose job is unknown until wave 5; the red reachability exception and `--deselect` conflict with the per-plan gate rule | Treat the pre-wiring waves as non-deployable (the branch is not released between plans); keep the one-plan red exception (phases 29-31 precedent) with the exact-orphan-list check (M6). |
| X (cross) | Final gates with the default TMPDIR instead of an owned directory | Not raised again by the referee; the standing ruling stays (the doctor test wraps by path length): record it in the 34-01 ledger only. |

## OpenCode Review (opencode-referee-one), cycle 1

Using the plan-review checklist, Ponytail Review, and codebase-memory to check all eight plans against the repository. This is a read-only review for convergence cycle 1.
Two blockers are confirmed in source: 34-04 never emits the required self-update clause, and its proposed atomic writer follows the very symlink that the reader rejects. I’m checking the runner and acceptance tests for similar gaps.
# Phase 34 cross-AI plan review — convergence cycle 1

**What this change does:** It adds a default-on daily check that refreshes version information without updating tools, reports whether the installer checkout is behind, and notifies the user when the outdated set changes. The plans reuse the existing schedule engine, lock, and version service.

**Verdict: revise before execution.** The main blockers are in 34-01, 34-04, 34-05, and 34-06: incomplete test edits for the default-on row, a missing self-update clause, a state writer that follows symlinks, a runner that can truncate required clauses, and macOS permission instructions that can be cut off in the actual UI.

## 34-01

**Summary:** Registers the eighth schedule, adds `Schedule.daily`, renders the Linux and macOS units, and introduces the notified-state path.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** The proposed cadence split matches the source. Linux tmp cleanup takes its fixed-cadence path before the calendar grid (`installer/schedules.py:842–850`), and its retime refusal is separate from the daily interval override (`installer/schedules.py:1409–1417`). Generic reconcile already enables undecided rows and remembers explicit off decisions (`installer/schedules.py:1548–1562,1699–1721`).

**Concerns:**
- **HIGH — The allowed test edits omit failures caused by default-on reconcile.** The list in `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:134` omits the mid-pass report, moved-checkout restart sequence, legacy adoptions, first-enable failure, concurrent reconcile, and partial sweeps. These tests pin exact outputs or file sets that now include another built-in (`tests/test_schedules_lifecycle.py:147–152,284–309,329–344,400–430,478–492,695–725`; `tests/test_schedules_handover.py:313–327`). The damaged-state sweep’s explicit basename list also needs the new row if it is to keep proving *every* timer was removed (`tests/test_schedules_lifecycle.py:910–928`).
- **MEDIUM — Ordinary last-off does not sweep state.** Adding `notified_path` in `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:132–141` covers uninstall cleanup. Ordinary `turn_off` preserves the off decision and removes idle shared assets; it does not call `_cleanup_if_last` (`installer/schedules.py:1298–1317,1340–1381,1837–1853,1871–1892`). The tracer’s `files_left` helper also deliberately excludes `schedules.json` and lock files (`tests/test_schedules_engine.py:195–205`).

**Suggestions:** List the exact fixture and expectation changes. Where a test isolates an old row, explicitly decide the new row off in the fixture rather than weakening the old assertion. If ordinary last-off must clear the notified set, test that path with a planted file and keep the saved off decision intact.

**Risk Assessment:** **High execution risk** as written: the executor is required to leave a green plan but is not authorized to fix several predictable failures.

## 34-02

**Summary:** Adds the shared notifier, platform-specific argv, Linux session-bus handling, and safe dependency defaults.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** Constant AppleScript source and separate title/body arguments keep message text out of the script. Linux retains `--`, and the scheduled message uses registry IDs whose grammar excludes markup and leading dashes (`installer/model.py:196,616`). The runner’s inherited environment and the unit’s serialized environment are separate boundaries; forwarding the bus address through the former does not require widening the latter (`installer/helper_assets/schedule_runner.py:82–97,191–195`; `installer/daemon.py:34–67`; `installer/systemd_daemon.py:198–211`). The proposed process helper already closes stdin and supports the timeout and group settings (`installer/run.py:115–151`).

**Concerns:**
- **MEDIUM — The runtime-directory fallback stops too early.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:136–137,154` tests a valid `XDG_RUNTIME_DIR` and an absent one, but not a set directory whose bus is missing. Under the proposed selection rule, that case never checks `/run/user/<uid>/bus`. This affects direct callers; the scheduled route intentionally does not forward `XDG_RUNTIME_DIR` (`installer/helper_assets/schedule_runner.py:82–97,191–195`).
- **LOW — The shared seam’s input contract is broader than the safety argument.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:154` accepts arbitrary summary/body strings, but the no-`--` and markup-safety arguments rely on how Phase 34 constructs its message. The registry restriction applies to IDs, not arbitrary notifier arguments (`installer/model.py:196,616`).

**Suggestions:** Keep the selected argv forms and runner-only bus propagation. Test fallback from an unusable runtime directory, and document which message inputs callers must supply. Keep actual LaunchAgent argument handling and delivery as owner UAT, not as claims established by the golden test.

**Risk Assessment:** **Medium.** The subprocess design is sound; desktop delivery and permission attribution still need real-platform evidence.

## 34-03

**Summary:** Adds a per-call freshness window, a lookup-failure callback, and the pure `outdated_ids` contract for Phase 35.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** Applying the same window at the budget check and the actual fetch gate keeps the accounting aligned (`installer/version_status.py:390–420,1879–1905,1975–1978`). Putting the failure callback in the existing exception branch preserves the digest path: `release_resolver` only selects the digest-bearing reader for the original `resolve_github_tag` function (`installer/versions.py:436–446`). Reading `state.present` and `version.outdated` separately also preserves the meaning of an outdated tool whose health is broken or misconfigured (`installer/version_status.py:1029–1056`).

**Concerns:**
- **MEDIUM — The cap and failure tests cover only one of the fetching paths.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:109–113,196` uses GitHub-backed fixtures. Installer-owned npm and Bun have separate forwarding sites, while `pnpm outdated` and `uv tool list --outdated` run outside the 20-call resolver counter (`installer/version_status.py:580–590,618–633,1839–1846,1879–1905`; `installer/manager_versions.py:238–286`). The cap is not a guarantee about all network requests or all lookup failures in a run.
- **LOW — The concurrency note overstates what the existing test proves.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:28–29,122` cites a same-service test for an interprocess claim. Two processes can each merge and replace a cache containing several new entries; atomic replacement prevents a torn file, not loss of at most one entry (`installer/version_status.py:2013–2027`; `installer/atomic.py:36–55`).

**Suggestions:** Add one mixed GitHub/npm/Bun fixture that proves the shared budget and failure plumbing. Describe the cap as a resolver-call cap and document what manager-query failures are visible. Keep the 20-hour window, seven-day interactive default, and digest-preservation test.

**Risk Assessment:** **Medium.** The core plumbing is well grounded; the current verification overstates its breadth.

## 34-04

**Summary:** Implements self-checking Git queries, oldest-first ordering, the persisted notification set, and the result line.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** The plan validates the exact remote ref and object ID before using the ID in subsequent Git calls, and distinguishes ancestry exit code `1` from a failed ancestry query (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:131–145`; `installer/run.py:145–150`). A fake Git runner is appropriate for pytest because the sandbox prohibits real Git and `gh` (`tests/sandbox.py:41–55`).

**Concerns:**
- **HIGH — No self-update clause is emitted.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:188,203` adds `tools-installer` to the set and count but appends an installer clause only on a skip. The locked requirement explicitly calls for a behind clause, and `setup.py` prints only what `run_check` returns (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md:47–50`; `setup.py:547–561`).
- **HIGH — The proposed writer follows a rejected symlink.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:183,201,245` reads without following links, then writes with `atomic_write_text`. That helper resolves the link and overwrites its target, leaving the link in place. The check can write outside its state directory and then read the same link as corrupt on the next run (`installer/atomic.py:36–78,186–215`).
- **HIGH — The real-service test asserts a filesystem contract the service does not have.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:192,248` expects only `update-check.json`. A normal pass saves `versions.json`, and it can also adopt or retire receipts; none of those actions goes through the update-executor spy (`installer/version_status.py:1473–1488,1535–1553,2013–2027`; `installer/version_cache.py:191–235`; `installer/receipts.py:94–108`). The plan needs to distinguish required cache writes from receipt housekeeping, not make the test green by hiding the cache outside scratch HOME.
- **HIGH — Git isolation and credential protection are overstated.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:135,144–145,246` keeps user/repo Git configuration in effect and logs raw command diagnostics after only line sanitization. The existing helper strips a small set of variables, disables prompts/hooks, and still permits Git configuration to affect transport; `command_error_line` does not redact secrets (`installer/run.py:61–77,181–195`). A diagnostic containing a credential-bearing remote URL is not covered by the planted-token tests. Also, the proposed `cat-file` handler treats *every* `CommandError`, including timeout or launch failure, as proof that the remote object is absent.
- **MEDIUM — The sort can crash or starve later tools.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:200,203` sorts raw `fromisoformat` results; a persisted naive timestamp can produce a `TypeError` when compared with an aware one. The cache already rejects naive and excessive future timestamps (`installer/version_cache.py:70–92,125–144`). Separately, failed fetches preserve `checked_at` and stamp `failed_at`; after the six-hour backoff, the same 20 oldest failures can consume every daily slot again (`installer/version_status.py:401–413,1879–1905,1975–1978`; `installer/version_cache.py:225–231`).
- **MEDIUM — Two proposed tests conflict with the specified control flow.** The all-four-clauses test requires both a failed notification and a failed save, but the plan does not attempt a save after notification failure. The `failed: boom` test expects `CommandError.detail`, while the action takes the first line of `str(exc)`, which is the command summary (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:188–189,203`; `installer/run.py:61–77`).

**Suggestions:** Emit and test the behind clause independently of notification delivery. Use `atomic_replace_entry` for the notified file and assert that the link is replaced and its target is unchanged. Test the exact allowed writes with the real refresh service, including an adoptable or stale receipt. Use safe Git failure categories rather than raw transport diagnostics; distinguish missing objects from operational errors. Reuse the cache’s timestamp-validation rules, account for last attempts in ordering, and split the mutually exclusive clause tests. Make the named reachability check verify the exact orphan list, not just grep for a substring (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:211–219`; `tests/test_reachability.py:161–162,196–197`).

**Risk Assessment:** **High.** This plan can miss a locked requirement, report a false self-update, and overwrite a file outside the intended state path.

## 34-05

**Summary:** Connects the generated job to the runner, CLI, shared lock, and production dependencies.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** The dispatch fits the existing architecture: CLI choices come from the schedule table, the runner uses the job ID for `--run-schedule`, and the child either trusts the parent lock or acquires and releases its own (`installer/cli.py:56–67`; `installer/helper_assets/schedule_runner.py:320–340,432–474`; `installer/schedule_run.py:121–148`). The runner-versus-direct-CLI distinction is correct: only the runner appends to the shared log (`setup.py:555–561`; `installer/helper_assets/schedule_runner.py:484–488,506–523`).

**Concerns:**
- **HIGH — The runner can truncate required clauses.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:130–143` reuses `_update` unchanged except for timeout wording. `_update` sanitizes the *whole* result to 300 characters; an early 300-character lookup reason can cut off the installer or notifier clause entirely (`installer/helper_assets/schedule_runner.py:102,129–134,345–358`). The proposed short fake output cannot catch this.
- **MEDIUM — Separate fakes leave the key integration unproven.** The fake `uv` prints a canned result and the CLI test patches the dependencies separately (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:130–136,177–183`). Neither proves that an actual failing notifier becomes a skip clause in the runner’s log, or that a direct invocation remains anonymous. The runner filters tokens, but the direct parser route bypasses that filter and the production fetcher reads token variables from its environment (`setup.py:529–567`; `installer/helper_assets/schedule_runner.py:191–195`; `installer/versions.py:358–373`). Also, the reused outer runner launch does not explicitly close stdin (`installer/helper_assets/schedule_runner.py:219–235`).

**Suggestions:** Preserve the single-line contract with a check-specific aggregate budget that leaves room for every required clause. Add one hermetic composition test passing a real check result, with long diagnostics and a fake notifier failure, through the runner log path. Pin closed stdin and anonymous fetches on both supported entry paths without changing interactive fetch behavior.

**Risk Assessment:** **High** until the log boundary is fixed. The dispatch itself is straightforward, but a successful check can lose the explanation the user needs.

## 34-06

**Summary:** Describes the check in Schedules, documents its limitations, and aligns the roadmap with the one-result-line contract.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** The new target and description branches prevent the row from falling through to cache-cleanup text (`installer/schedules_screen.py:430–435,458–482`). The Homebrew limitation is grounded in the existing read path, which sets `HOMEBREW_NO_AUTO_UPDATE=1` and queries `brew outdated` (`installer/manager_versions.py:30,160–167`). The roadmap edit correctly calls for a clause rather than a second result line (`.planning/ROADMAP.md:320`; `installer/helper_assets/schedule_runner.py:345–358`).

**Concerns:**
- **HIGH — The macOS permission can be present in a test and absent on screen.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:115–125` puts the permission after `what`, `last`, and `times`. At the planned three-row detail height, those earlier lines consume the visible space. The renderer wraps and discards overflow; it does not make the discarded lines scrollable. The proposed test reads the uncut backing string at 100×30 (`installer/schedules_screen.py:443–448,474–482`; `installer/ui_common.py:70–92`; `tests/test_schedules_view.py:1133–1150`).
- **LOW — The no-count promise is broader than the UI behavior.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:29,117,125` should apply to explanatory copy, not `last:`, which includes the logged result and its update count (`installer/schedules_screen.py:484–494`).

**Suggestions:** Make the complete permission instruction visible or reachable at 80×20 without undoing the table-height decision. Test the rendered widget, including a row with a prior log result. Keep the actual notification attribution and silent-delivery behavior marked as owner UAT.

**Risk Assessment:** **High for NOTIFY-05 usability.** A macOS user who receives no notification may also be unable to see how to enable it.

## 34-07

**Summary:** Adds the new job to the disposable-container run, teardown, and direct fallback paths.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** The driver already accepts any registered schedule ID and uses the engine’s real argv, so no driver change is needed (`tests/e2e_schedules_driver.py:46–85`). The proposed loop edits are below the four classified PATH lines and do not require shifting their pins (`tests/test_shell_scripts_path.py:519–537`; `scripts/container-e2e-verify.sh:2570–2583,2704–2717,2764–2775`).

**Concerns:**
- **MEDIUM — The container verdict is weaker than the promised evidence.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:21–24,97–107` asks for `ok: N updates available`, but the unchanged harness accepts `skipped`, accepts any Last cell other than `never`, and does not print the successful result text before teardown (`scripts/container-e2e-verify.sh:2497–2559,2693–2698`). Its `--direct` route also bypasses the OFF check and emits a different completion marker (`scripts/container-e2e-verify.sh:2764–2775,2794–2812`).

**Suggestions:** Require fresh evidence of one successful `check-updates` result with the expected prefix and matching Last cell. Give the direct fallback its own pass criteria and record the unit/calendar/teardown proof as not exercised in that mode. Keep both modes orchestrator-only.

**Risk Assessment:** **Medium verification risk.** Adding the row to the loops is sound; the current verdict can certify less than the plan claims.

## 34-08

**Summary:** Adds final consistency checks for runner argv, inherited interfaces, environment boundaries, and module rules.

**Findings status:** First review; no previous-cycle findings.

**Strengths:** Parsing the real generated argv for every row on both OSes is a useful regression test. The six-token prefix and parser return shape match the source, and the two platforms exercise different tmp-cleanup tails (`installer/schedules.py:853–888`; `installer/helper_assets/schedule_runner.py:432–474`).

**Concerns:**
- **MEDIUM — Two advertised contracts can drift without failing the tests.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-PLAN.md:22–23,103–104` says it pins `Notifier`, but the behavior never asserts it. Its one-way set subtraction also passes if the runner drops a shared key such as `HOME` or a certificate variable (`installer/daemon.py:34–47`; `installer/helper_assets/schedule_runner.py:82–97,191–195`). A literal comparison of `inspect.signature(...).return_annotation` also needs to account for postponed annotations (`installer/version_status.py:43`).

**Suggestions:** Assert equality against the unit keys plus the two runner-only keys, retain explicit bus exclusion from unit keys, and exercise the notifier seam through a typed fake. Resolve annotations before comparing the return type. Keep the real argv/parser test rather than replacing it with a source-text check.

**Risk Assessment:** **Low product risk, medium regression risk.** The proposed checks are cheap, but their current assertions leave gaps in the Phase 35 handoff.

## Cross-plan assessment

1. **Resolve notification frequency explicitly.** The goal says *at most one notification a day*, while the changed-set test deliberately allows another on a second run, and persisted state has no date (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md:9,33–35`; `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:180–182,201–203`). The run lock serializes runs; it does not limit their daily frequency (`installer/schedule_run.py:133–148`). Keep the settled shrinking-set behavior. State whether the daily limit describes normal timer cadence or is an invariant that must also hold across manual runs, catch-up, and retiming; test the stated contract.
2. **Keep intermediate states out of rollout.** Wave 1 can register a default-on unit whose job is unknown until Wave 5 (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:45–47`; `installer/helper_assets/schedule_runner.py:453–460`). The final reconciliation order already refreshes owned runner copies before enabling rows (`installer/schedules.py:1659–1712`). Treat the pre-wiring waves as non-deployable. Separately, reconcile the deliberately red reachability exception and `--deselect` command with the repository’s per-plan gate rule; the cleanest boundary is to land legitimate production wiring with the module rather than weaken the guard (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:211–219`; `AGENTS.md:41–55`).
3. **Require one hermetic functional path, then keep real-platform proof separate.** The runner/parser contract, fake notifier tests, and container test each prove different things. Tie the real check result to the real runner log with injected external dependencies: verify one result line, preserved self-update and skip clauses, no update-executor calls, and only the allowed writes. Record the container result, real desktop delivery, and LaunchAgent permissions separately in validation; none substitutes for the others.

**Review scope:** Source and plan inspection only. No files were edited, no tests or containers were run, and no host schedules or notifications were triggered.


## Lane Log (convergence cycle 2, plans at c099c272)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 21:29 | opencode-referee-one | one-shot probe | OK |
| 21:29 to about 22:15 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 2 concerns

Cycle 2 of 3. Real HIGH by cycle: 7, now 5 (second-order gaps in the round 1 fixes). Plan-internal findings were checked against the cited plan lines; claims that rest on repository code are for the planner to verify. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (34-01) | The no-credentials claim covers only two token variables: the shared renderer copies proxy values (which may carry credentials) into both unit formats, and existing tests expect them | Real wording and test gap (`installer/schedules.py:891-901,925-955`; `tests/test_systemd_daemon.py:1197-1211`; `tests/test_daemon.py:158-165`). DECISION: narrow the guarantee to what D-11 locks (the GitHub token variables never reach the unit, the runner child or the log) and state that proxy values the user configured are carried like for every other row (existing approved behavior, private 0600 unit files); test the real boundary, not "any credential". |
| M1 (34-01) | Task 1 cannot collect the 29-failure baseline as written (pin edits before and after the baseline, the layout file missing from the baseline command, seven files committed though eight are listed) | Real. DECISION: one sequence: new tests, RED, production edits, baseline run with the OLD pins and the layout file, pin edits, GREEN; stage all eight files. |
| M2 (34-02) | A socket probe `OSError` (inaccessible candidate) can fail the check instead of skipping the notification | Real. DECISION: on a probe error advance to the next candidate; test it. |
| M3 (34-02) | NOTIFY-05's failure path is tested in pieces (a command error injected into the adapter; the runner test replays a precomputed line); `command_error_line` echoes the full argv, including the notification body | Real. DECISION: add one composition case with the real macOS adapter, a fake `osascript` executable and the real check result; use a fixed fallback reason when stderr is empty, never the argv. |
| M4 (34-03) | The cap test uses rows that fetch by construction; it does not prove present tools get the slots (owner and freshness decide budget use before presence) | Real. DECISION: one real-service budget test with missing, fresh, backed-off, manager-owned and eligible rows asserting which resolver calls are spent. |
| L1 (34-03) | Manager queries are not once per pass (a fresh manager snapshot is reused) | Reword. |
| H2 (34-04) | Unknown results are treated as confirmed removals: a transient origin failure removes a notified `tools-installer` id and recovery notifies again; a tool lookup can return `outdated=None` or a stale comparison | Real (`installer/version_status.py:401-431,642-675,1728-1758`). DECISION: an id whose status is unknown keeps its prior membership in the saved set; only a confirmed status changes membership; test failure then recovery separately from a real shrink. |
| H3 (34-04) | Git subcommand names do not establish read-only or anonymous behavior: credential helpers and transport configuration stay in effect; a partial clone can lazy-fetch objects | Real by the referee's reading (`installer/run.py:181-195`); planner verifies. DECISION: run the check's git with credential helpers disabled (`-c credential.helper=`), `GIT_TERMINAL_PROMPT=0` and lazy fetch disabled (`GIT_NO_LAZY_FETCH=1`, ignored by older git), state the remaining limit (the user's other git configuration stays in effect), keep real-git immutability as an orchestrator or owner observation (pytest forbids real git). |
| M5 (34-04) | Malformed-state recovery has gaps: invalid UTF-8, no strict version and id shape, a directory at the notified-file path; the initial cache load can raise on invalid UTF-8 | Real. DECISION: treat invalid UTF-8 as corrupt, require a strict version and id shape, leave a directory at the path untouched (report, no crash), guard the initial cache load. |
| H4 (34-05) | The production path can write outside the allowed directories: `uv run --isolated --no-dev` in the checkout can rewrite a lockfile and puts uv's cache outside the installer state; the shared `versions.json` writer follows a final symlink; the HOME snapshot misses receipts (pytest redirects them) and a fake tag resolver cannot exercise digest adoption | Real by the referee's reading (`installer/schedules.py:871-879`; `installer/version_status.py:2013-2027`; `installer/version_cache.py:191-213`; `installer/atomic.py:36-55`; `tests/conftest.py:377-389`); planner verifies. DECISION: the check's inner launch cannot rewrite the checkout (`--frozen`, or the verified equivalent) and the test asserts the checkout unchanged; the version-cache writer replaces a final symlink instead of writing through it (`atomic_replace_entry`, also on the interactive path; list any existing test edit as an exception); receipt fixtures go inside the snapshot and both permitted receipt paths are verified. |
| M6 (34-05) | The integration test crosses the output boundary, not the job boundary; the byte-exact test uses printable reasons only while the child's sanitizer preserves C1 controls the runner removes | Real. DECISION: one hermetic job through the real parser, service wiring and dispatch with a one-day-old cache, a nonempty outdated set and fake external I/O, asserting the resulting shared log; include a C1-control reason in the byte-exact test. |
| M7 (34-06) | The limits can still be invisible below the long result, and `last:` can legitimately name a tool (an npm resolver error can name an id), so the no-id ban is too broad | DECISION: keep the permission first; state which larger viewport reveals the limits (or place the short limits sentence before `last:`); scope the no-id assertion to explanatory copy; say a changed NONEMPTY set triggers an attempt, empty resets silently, and a successful command does not prove delivery. |
| H5 (34-07) | An old success can certify a launch that did nothing: no link to the requested invocation; both routes ignore launch status before reading the log; a standalone `skipped: busy` can be ignored by the start/result finder | Real (`scripts/container-e2e-verify.sh:2494-2559,2764-2769`; `installer/helper_assets/schedule_runner.py:503-510`; `tests/test_container_e2e_schedules.py:489-517`). DECISION: require a NEW start/result pair attributable to the requested launch (count before and after, or a marker), check the Last cell against that result, reject stale success, no new output and a standalone busy result; the host fixture must not pre-seed success before the stub launches. |
| M8 (34-07) | The handoff misstates the live proof: the copied workspace has no Git metadata so no origin-query skip, and the live calendar and catch-up probes exercise cache cleanup, not the new row; direct mode skips the unit OFF check but runs teardown | DECISION: record check-row service/result/OFF evidence separately from the generic calendar/catch-up evidence and from direct-mode runner evidence; correct the expected-lines text. |
| M9 (34-08) | The once-only spy is called twice (a preliminary `deps.notify("s", "b")` before expecting one call from the check) | Real plan-internal defect. DECISION: drop the preliminary call; pass `deps.notify` into `run_check` and assert the entire recorded call list. |
| C1 (cross) | The locked artifacts still say an absolute "at most one notification a day" and the bare-CLI logging wording: `setup.py` prints, the runner logs, a contended run can add a `waited:` entry | DECISION: plan 34-06 amends `ROADMAP.md` criterion text AND adds a dated amendment note to `34-SPEC.md` (the goal sentence and the logging wording): the daily limit is the timer cadence, a changed nonempty set triggers an attempt on any run, and a contended run may add a `waited:` entry before the single result. Provisional, needs confirmation. |
| C2 (cross) | 34-05 Task 1 commits before Task 2 adds a reachable import | DECISION: the first 34-05 commit imports `update_check` from a production entry point (clearing the orphan); keep the guard unchanged and keep its real failure output in 34-04's verify (no `grep -q` suppression). |
| X | Final gates with the default TMPDIR | Standing ruling; not raised again: keep the note in the 34-01 ledger only. |

## OpenCode Review (opencode-referee-one), cycle 2

Using the plan-review checklist, Ponytail Review, and codebase-memory to verify all eight revised plans against the repository. This is a read-only review of cycle 2.
The revised plans now specify the self-update clause and a link-safe writer for `update-check.json`. The shared refresh still writes `versions.json` through a symlink-following helper, so the current allowed-writes test does not prove the phase’s write boundary.
# Phase 34 cross-AI plan review — convergence cycle 2

**What this change does:** It adds a default-on daily update check for installed tools and the installer checkout. The check reuses the version refresh and schedule lock, logs one result, and attempts a desktop notification when the known outdated set changes.

**Verdict: revise before execution.** The revised plans address most cycle-1 findings, including the missing self-update clause, the notified-file symlink, and the placement of the Mac permission instruction. The remaining blockers are substantive: the real runner does not enforce the write boundary, incomplete lookups can be mistaken for a changed set, and the container verdict can accept an old success.

## 34-01

**Summary:** Adds the eighth schedule, its daily cadence and unit arguments, its state-file sweep, and the table and fixture changes.

**Findings status:** H1 is addressed in the fixture list; M1 is resolved as uninstall-only cleanup. C2’s non-deployable window is explicit.

**Strengths:** The plan changes cadence without changing Linux tmp cleanup’s fixed timer or retime refusal (`installer/schedules.py:838–850,1409–1417`). The expanded fixture rules preserve old-row assertions and extend the damaged-state sweep to the new row (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:137–148`; `tests/test_schedules_lifecycle.py:910–928`). Ordinary off and uninstall really do take different cleanup paths (`installer/schedules.py:1298–1317,1837–1853`).

**Concerns:**

- **HIGH — The no-credentials test proves only that two token variables are absent.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:33,55–57,133` prohibits *any* credential, but the shared renderer still copies proxy values into both formats. Existing tests explicitly expect credential-bearing proxy URLs in the private files (`installer/schedules.py:891–901,925–955`; `tests/test_systemd_daemon.py:1197–1211`; `tests/test_daemon.py:158–165`).
- **MEDIUM — Task 1 cannot collect the required 29-failure baseline as written.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:91,142–163` tells the executor to edit existing pins both before and after the baseline, omits `tests/test_layout_80x20.py` from the command that must count its failures, and says to commit seven files although the task lists eight. The layout assertions are real (`tests/test_layout_80x20.py:326–335,859–871`).

**Suggestions:** Make the credential rule explicit for the new row: either exclude credential-bearing proxy values or record an approved exception and test the actual boundary. Give Task 1 one sequence: new tests → RED → production edits → baseline with old pins and the layout file → pin edits → GREEN. Stage all eight files.

**Risk Assessment:** **High** until the credential guarantee matches the renderer; the cadence design itself does not need rework.

## 34-02

**Summary:** Adds the shared notifier, platform arguments, the Linux bus fallback, and a default notifier that never launches a child.

**Findings status:** M2’s missing-socket fallback and L1’s caller contract are addressed. Real Mac delivery remains deferred.

**Strengths:** Forwarding the bus address at runtime does not widen the serialized unit environment (`installer/helper_assets/schedule_runner.py:82–97,191–195`; `installer/daemon.py:46–59`). Constant AppleScript source keeps message text out of the script, and the registry’s ID grammar supports the chosen count-and-ID message format (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:135–139`; `installer/model.py:195–196,615–619`).

**Concerns:**

- **MEDIUM — A socket probe error can fail the check instead of skipping notification.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:138,156` tests only true/false probes. On Python 3.12, `Path.is_socket` can raise on an inaccessible candidate. That probe is outside the `CommandError` handling supplied by `installer/run.py:127–150`; the direct CLI can inherit the runtime directory (`setup.py:547–567`).
- **MEDIUM — NOTIFY-05’s failure path is still tested in pieces.** The Mac adapter test injects a command error, while the actual fake executable is Linux-only (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:142–144`). The runner test replays a precomputed line from a generic fake notifier (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:144`). Neither proves a failing fake `osascript` reaches `notify skipped` with exit 0 through the real result path (`installer/helper_assets/schedule_runner.py:345–358,510–523`).

**Suggestions:** On socket-probe `OSError`, advance to the next candidate. Add one composition case with the real Mac adapter, a fake executable, and the real check result. Use a fixed fallback when stderr is empty; `command_error_line` otherwise echoes the full argv, including the notification body (`installer/run.py:64–77`).

**Risk Assessment:** **Medium.** Keep the selected argv forms; the gaps are failure handling and proof, not the platform decision.

## 34-03

**Summary:** Adds the per-call cache window, resolver failure reporting, and the `outdated_ids` helper inherited by Phase 35.

**Findings status:** M3’s mixed-source coverage and L2’s narrower concurrency claim are addressed in the plan. The distinction between stale or unknown data and a confirmed set change remains open.

**Strengths:** The same window reaches the budget check and fetch gate, and the sink does not wrap the resolver, preserving the identity check that retains asset digests (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:114–125`; `installer/version_status.py:390–420,1879–1905`; `installer/versions.py:436–446`). The pure helper correctly reads presence and version separately (`installer/version_status.py:1029–1056`).

**Concerns:**

- **MEDIUM — The cap test does not prove that present tools get the slots.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:113–114,125` uses fixtures that fetch by construction. In the real pass, owner and freshness decide budget use before presence is checked. A dangling managed artifact can supply installer ownership but does not prove presence (`installer/version_status.py:1870–1915,1975–1978`; `installer/uninstall.py:35–53`; `installer/ownership.py:1099–1106`; `installer/status.py:187–200`).
- **LOW — Manager queries are not once per pass.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:26,123` correctly leaves manager cache rules alone, but its description ignores reuse of a fresh manager snapshot (`installer/version_status.py:1698–1727`; `installer/version_cache.py:378–393`).

**Suggestions:** Use one real-service budget test with missing, fresh, backed-off, manager-owned and eligible rows; assert which resolver calls are spent. Keep `outdated_ids` pure and handle check completeness separately in 34-04.

**Risk Assessment:** **Medium.** The plumbing fits the service; the open risk is spending limited fetch slots on tools that cannot contribute to the report.

## 34-04

**Summary:** Implements Git self-checking, set persistence, oldest-attempt ordering, and result-line formatting.

**Findings status:** H2/H3, M4/M5, and the printable-text part of H6 are addressed. H5 is only partially closed: fixed Git error categories protect the log, not the transport or the checkout.

**Strengths:** `installer behind origin/main` is now independent of notification delivery. The notified-file writer replaces the file entry rather than following its final symlink, matching the reader’s no-follow policy (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:201,213–219`; `installer/atomic.py:36–78,186–215`).

**Concerns:**

- **HIGH — Unknown results are treated as confirmed removals.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:193–202,219` compares and saves the new set even when a provider cannot answer. For example, a transient origin failure removes a previously notified `tools-installer` ID; recovery adds it again and sends another notification even though nothing changed upstream. Tool lookups can similarly return `outdated=None` or a stale comparison, and manager failures can bypass the resolver sink (`installer/version_status.py:401–431,642–675,1728–1758`).
- **HIGH — Read-only Git subcommand names do not establish read-only or anonymous behavior.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:35–37,139–147,153–154` retains credential helpers and transport configuration. The existing helper strips five variables and disables prompts; it does not disable credential helpers (`installer/run.py:181–195`). Git can also fetch missing objects on demand in a partial clone (`git(1)`, `--no-lazy-fetch`). A fake argv test and unchanged fake `.git` tree prove neither property.
- **MEDIUM — Malformed-state recovery has gaps.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:195–198,216–219` does not explicitly handle invalid UTF-8 or require a strict version and ID shape. The initial version-cache load can also raise on invalid UTF-8 before the planned refresh error handler. A directory at the notified-file path cannot be replaced by the file writer and must remain untouched (`installer/version_cache.py:156–188`; `installer/atomic.py:58–73,186–215`; `installer/model.py:195–196`).

**Suggestions:** Preserve prior membership for IDs whose status is unknown, or defer the notification and baseline update on incomplete evidence. Test failure followed by recovery separately from a real shrink. Make the check’s Git transport credential-free and prevent lazy fetches, or skip checkouts where those guarantees cannot be made. Keep real Git immutability as separate disposable-environment evidence; pytest forbids real Git (`tests/sandbox.py:41–55`).

**Risk Assessment:** **High.** The current plan can send repeat notices for unchanged updates and cannot guarantee the specified Git boundary.

## 34-05

**Summary:** Connects the runner, CLI, shared lock, and production services, and adds result and filesystem checks.

**Findings status:** H6’s length-budget test and M7’s outer stdin change are addressed. H4’s write proof and the end-to-end acceptance path are incomplete.

**Strengths:** Kind dispatch fits the current shared lock and preserves the cleanup refusal (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:189–204`; `installer/schedule_run.py:121–148`). The runner, rather than `setup.py`, is the right place to verify shared-log output (`setup.py:547–561`; `installer/helper_assets/schedule_runner.py:484–488,503–523`).

**Concerns:**

- **HIGH — The production path can write outside the allowed directories.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:136,151,188–197` reuses `uv run --isolated --no-dev` in the checkout; that does not prohibit lockfile writes or place uv’s cache inside installer state. The outer `--no-cache` applies to a separate invocation (`installer/schedules.py:871–879`; `installer/helper_assets/schedule_runner.py:320–340`). Independently, the refresh writes `versions.json` using the symlink-following writer already rejected for `update-check.json` (`installer/version_status.py:2013–2027`; `installer/version_cache.py:191–213`; `installer/atomic.py:36–55`). The proposed HOME snapshot misses receipt retirement because pytest redirects receipts outside that HOME, and its fake tag resolver cannot exercise digest-based adoption (`tests/conftest.py:377–389`; `installer/version_status.py:1473–1488,1496–1537`; `installer/versions.py:436–446`).
- **MEDIUM — The integration test crosses the output boundary, not the job boundary.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:144,194–197` replays a precomputed result and replaces production dependencies in separate tests. Bad service wiring could pass all of them. The byte-exact test also uses printable reasons only, although the child’s sanitizer preserves C1 controls that the runner removes (`installer/sanitize.py:9–22`; `installer/helper_assets/schedule_runner.py:100–102,129–134,345–358`).

**Suggestions:** Make the real check launch leave the checkout unchanged, and make the version-cache writer reject or replace a final symlink without touching its target. Put receipt fixtures inside the snapshot and verify both permitted receipt paths. Run one hermetic job through the real parser, service wiring and dispatch with a one-day-old cache, a nonempty outdated set and fake external I/O; assert the resulting shared log, not just a replay.

**Risk Assessment:** **High.** The update-executor spy is useful, but it cannot prove that the scheduled check is non-mutating.

## 34-06

**Summary:** Adds Schedules detail text and the Mac permission instruction, documents limits, and amends roadmap criterion 5.

**Findings status:** H7’s first-line placement and rendered check are addressed. L3 is addressed for counts, but the no-ID claim remains too broad.

**Strengths:** Permission-first matches the widget’s actual clipping behavior, and the plan now inspects rendered rows rather than only backing text (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:120–121,130`; `installer/schedules_screen.py:443–448`; `installer/ui_common.py:70–92`). The criterion-5 edit correctly specifies a clause rather than a second result line (`.planning/ROADMAP.md:320`; `installer/helper_assets/schedule_runner.py:345–358`).

**Concerns:**

- **MEDIUM — The limits can still be invisible, and `last:` can legitimately name a tool.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:119–130` appends the notifier and limits after the long result in a panel that discards overflow. It also bans IDs throughout the detail, although `last:` displays the logged diagnostic and an npm resolver error can name `@opencode/cli` (`installer/schedules_screen.py:474–494`; `installer/ui_common.py:70–92`; `installer/versions.py:422–432`; `installer/registry.toml:1589–1597`).

**Suggestions:** Keep permission first. Make the limits reachable or state which larger viewport reveals them. Scope the no-ID assertion to explanatory copy. Say that a changed **nonempty** set triggers an attempt, empty resets silently, and a successful command does not prove delivery.

**Risk Assessment:** **Medium usability risk.** The new permission test is the right shape; actual LaunchAgent delivery and attribution still need owner UAT.

## 34-07

**Summary:** Extends both disposable-container routes with the new job and a stricter result verdict.

**Findings status:** M8 is partially addressed. The format and success-glyph checks are stronger; freshness is not proven.

**Strengths:** The driver already accepts the table’s IDs and emits real runner argv, so it needs no new verb (`tests/e2e_schedules_driver.py:46–85`). The proposed script edits are below the classified PATH lines (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:27,113`; `tests/test_shell_scripts_path.py:519–537`).

**Concerns:**

- **HIGH — An old success can certify a launch that did nothing.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:100–105,113,137` adds stricter text and glyph checks but no link to the requested invocation. Both launch routes ignore launch status before reading the log. A later standalone `skipped: busy` can also be ignored by the start/result finder because the runner writes it before `start` (`scripts/container-e2e-verify.sh:2494–2559,2764–2769`; `installer/helper_assets/schedule_runner.py:503–510`). The host fixture pre-seeds success before the stub launches (`tests/test_container_e2e_schedules.py:489–517`).
- **MEDIUM — The handoff misstates the live proof.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:24–25` anticipates an origin-query skip, but the copied workspace has no Git metadata. Also, the live calendar and catch-up probes exercise **cache cleanup**, not the new row. Direct mode skips unit OFF verification, but still runs container teardown (`scripts/container-e2e-verify.sh:324–340,2623–2665,2691–2698,2794–2811`).

**Suggestions:** Require a new start/result pair attributable to the requested launch and check the Last cell against that result. Reject stale success, no new output, and a standalone busy result. Record check-row service/result/OFF evidence separately from generic calendar/catch-up evidence and direct-mode runner evidence.

**Risk Assessment:** **High verification risk.** The current strict check can record a pass without a check from the invocation under test.

## 34-08

**Summary:** Pins generated argv, Phase 35 interfaces, environment keys, and module rules.

**Findings status:** M9’s key-set equality and resolved annotation are addressed. The notifier exercise has a conflicting call count.

**Strengths:** The six-token slice matches the real launcher, and the parser supplies the log ID the test asserts on both platforms (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-PLAN.md:103–107`; `installer/schedules.py:853–888`; `installer/helper_assets/schedule_runner.py:432–474`). Exact key-set equality catches a dropped shared key (`installer/daemon.py:34–47`; `installer/helper_assets/schedule_runner.py:82–97`).

**Concerns:**

- **MEDIUM — The once-only spy is called twice.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-PLAN.md:106` calls `deps.notify("s", "b")` before expecting that same recording fake to have one call from the check. `RunDeps` stores the callable as a field, not a wrapper (`installer/schedule_run.py:24–32`; `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:157`; `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:219`).

**Suggestions:** Pass `deps.notify` into `run_check` and assert the entire recorded call list afterward. Drop the preliminary invocation.

**Risk Assessment:** **Low product risk; medium execution risk** if the executor implements the test literally.

## Cross-plan assessment

1. **Align the locked artifacts with the adopted semantics.** Keep the daily *timer cadence* and the changed-nonempty-set rule; do not add a date throttle. Update the absolute cap in `.planning/ROADMAP.md:310` and `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md:9`. Also reconcile the bare-CLI logging wording in the SPEC at lines 22–25 and 79: `setup.py` prints, the runner logs, and a contended run can add a `waited:` entry before the single result (`setup.py:555–561`; `installer/helper_assets/schedule_runner.py:263–282,503–523`).
2. **Keep the named reachability exception contained.** The on-disk cycle-1 ledger expressly allows the 34-04 exception (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-REVIEWS.md:46,54`). But 34-05 Task 1 commits before Task 2 adds a reachable import (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:150–159,202–210`). Clear the orphan in the first 34-05 commit, or put the connected changes in one commit. Keep the guard unchanged (`tests/test_reachability.py:142–162,196–197`) and retain its actual failure output rather than suppressing it with `grep -q` (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:220–231`).
3. **Require evidence at the boundary each test claims to prove.** A fake Git runner proves argv, not checkout immutability. A replayed check result proves logging, not production composition. A success glyph proves display status, not a fresh invocation. Close those gaps without expanding the owner-only desktop UAT scope.

**Status: Issues found — revise and re-review.** This was a read-only review of the on-disk plans and source. No files were edited, no tests or containers were run, and no host schedules or notifications were triggered.


## Lane Log (convergence cycle 3, plans at 60b674da)

| Time (local) | Lane | Check | Result |
|---|---|---|---|
| 23:00 | opencode-referee-one | one-shot probe | OK |
| 23:00 to about 23:35 | opencode-referee-one | real review through `gsd-tools query review-lane invoke`, background, 2700 s timeout, stdin `/dev/null`, prior findings supplied | exit 0, stderr empty |

Failures this cycle: none. No other lane or model was used.

## Orchestrator verification of the cycle 3 concerns

Cycle 3 of 3: the cap. Real HIGH by cycle: 7, 5, now 8 distinct (second-order gaps in the previous round's fixes; the count is not falling). Under the owner's cap rule this is the LAST revision and the run executes right after it, with no cycle 4; what the post-execution review, security audit and verifier find goes to the fix round. Claims that rest on repository code are for the planner to verify. DECISIONS apply exactly; all provisional.

| Id | Claim | Judgment and DECISION |
|---|---|---|
| H1 (34-01) | A directory at `update-check.json` can interrupt uninstall after partial cleanup (the loop unlinks entries in order and raises on a directory) | Real by the referee's reading (`installer/schedules.py:1837-1853`; `installer/uninstall.py:829-838`). DECISION: leave an unexpected directory and its contents untouched, report it, and still clean the unrelated owned artifacts; add that uninstall case beside the regular-file fixture. |
| M1 (34-02) | The real-child "bus unset" fixture depends on the current UID having a socket (clearing variables does not disable the `/run/user/<uid>/bus` probe) | Real. DECISION: inject a false socket probe in that test and isolate the environment inherited by the fake `osascript`. |
| M2 (34-02) | Sanitized stderr is not necessarily safe to log or byte-stable (credentials, echoed text, tabs) | Real. DECISION: fixed notifier failure categories even with nonempty stderr; assert byte equivalence for the assembled result, not for `reason_line` alone. |
| H2 (34-03) | The cache loaders use blocking unbounded `read_text()`; a non-regular file can stall the check while it holds the shared lock | Real by the referee's reading (`installer/version_cache.py:156-179`; `installer/version_status.py:1838-1846`; `installer/atomic.py:186-215`). DECISION: both cache reads use `read_capped` with an explicit final-symlink policy; test a non-regular file (a FIFO or directory) that must not block. |
| M3 (34-03) | The tests miss the production path: "every saved entry gets a failure stamp" is wrong (only the attempted 20 are merged); the digest test omits `on_failure`, which the scheduled caller always supplies; "eligible rows only" is broader than the fixture (a dangling artifact can supply ownership before the presence check) | DECISION: assert exactly which 20 entries were stamped; run the digest test with the sink enabled; narrow the eligibility claim to what the fixture proves and record the dangling-artifact exception. |
| H3 (34-04) | Stale evidence can still add or remove an id: `outdated_ids` hits are all treated as confirmed; a failed resolver can return `outdated=True, stale=True`; manager failures backfill old maps and report them with `stale=False` | Real by the referee's reading (`installer/version_status.py:186-194,401-431,642-689,1728-1758`). DECISION: for the daily check an id is CONFIRMED (in or out) only when its comparison is not stale AND its latest-version stamp is newer than the run's start; anything else is unknown and keeps its prior membership; `outdated_ids` stays pure for Phase 35; test a stale positive and a failed manager query with a prior snapshot through the real service. |
| H4 (34-04) | The Git boundary still permits what the plan rules out: configured `core.askPass` is not disabled, older Git ignores the lazy-fetch variable yet object queries still run, and `git -C` does not prove the checkout is the Git root (an unpacked installer nested in another worktree queries that worktree's origin) | Real by the referee's reading (`installer/run.py:181-195`; `setup.py:539-543`). DECISION: also pass `-c core.askPass=` and an empty `GIT_ASKPASS`; verify the worktree root (`rev-parse --show-toplevel` equals the checkout) else skip; skip the object queries on a partial clone (`extensions.partialclone` or a promisor remote in the config) and say older git may ignore the lazy-fetch variable; fixed skip categories; real-git evidence stays an orchestrator or owner observation (pytest forbids real git). |
| H5 (34-05) | `--frozen` protects `uv.lock`, not the checkout or the allowed-write boundary: Python bytecode can be written into the checkout, uv and manager scratch and cache writes sit outside installer state, and `uv tool list --outdated` runs separately | Real by the referee's reading (`installer/helper_assets/schedule_runner.py:191-195,320-340`; `setup.py:26-40,65-99`; `installer/manager_versions.py:253-258`). DECISION: the check child also runs with `PYTHONDONTWRITEBYTECODE=1` (pinned by the argv/env test); narrow the claim honestly: NO writes into the checkout, writes into installer state only to the named files; uv's own cache and manager-query scratch are outside the installer's state and are an accepted exception recorded as a dated amendment of the SPEC prohibition in 34-06 (as for every other schedule row); real-launch evidence is the orchestrator's container observation. Provisional. |
| M4 (34-05) | "Every child gets closed stdin" exceeds the change: the bare CLI's refresh reaches `run_query`, which does not close stdin | DECISION: qualify the claim (the runner route) and test the two routes separately; do not change interactive query behavior. |
| H6 (34-06) | The architecture text documents exceptions (credential-bearing proxy values, outside-state uv writes) that the SPEC still prohibits (`34-SPEC.md:68,121`) | Real contract conflict. DECISION: put the effective wording in the NORMATIVE SPEC clauses with a dated amendment record: proxy values the user configured are carried like for every row (existing private 0600 units), uv and manager scratch/cache writes are accepted as for every row, daily limit = timer cadence, CLI stdout versus runner `waited:`/`start`/one result. Provisional, needs confirmation. |
| M5 (34-06) | SPEC acceptance 6 still says a separate self-update line and the plan says the ROADMAP criterion 5 is the only edit though it prescribes goal and criterion 1 changes; the pilot can keep the previous `Rows` height if status clears without a repaint | DECISION: reconcile acceptance 6 and the ROADMAP edit list; use separately settled layouts for the viewport tests or test the repaint after a status-height change. |
| H7 (34-07) | A new pair can belong to another activation: the live timer may fire between the baseline and the manual start; the log reader hides read errors | Real (`installer/schedules.py:980-991`; `installer/systemd_daemon.py:335-349`). DECISION: fail closed on a baseline read error and on argv-generation errors; require EXACTLY one new start/ok pair after the baseline (a second pair is a failure the orchestrator retries, never a false pass) and say a coincident timer firing yields a failure, not a pass. |
| M6 (34-07) | The verdict and its fixtures disagree (a lone new `start` goes to `RUN_UNEXPECTED`, not `RUN_MISSING`); the host fixtures extract functions by explicit name and miss the new helpers; the direct route discards the argv producer's exit status | DECISION: align verdicts and fixtures; include the new helpers in the extraction; the direct route checks the producer's exit status; pin a direct launch that emits a valid pair but exits nonzero. |
| M7 (34-07) | Cell time and teardown markers can misstate: the cell is compared by slicing `HH:MM` though the driver renders local time (`✓ 1d` after midnight); the teardown marker prints even if removal fails and the runtime need not be Podman | DECISION: compare the Last cell by the driver's clock rule; confirm cleanup in the runtime that ran the container. |
| H8 (34-09) | The checkout snapshot does not cover the checkout used by the check: the in-process call derives it from `setup.__file__`; nothing binds it to `tmp_path/co` or asserts the Git seam's `-C` path; the fake `uv` only replays output | Real (`setup.py:529-561`). DECISION: bind the job to the scratch checkout (patch the checkout resolution) and assert the exact `-C` path seen by the Git seam; the runner's fake child invokes the real parser, wiring and dispatch (a small Python script as the fake `uv`) and the snapshot spans that call; a pure replay stays as a separate, labeled log test. |
| M8 (34-09) | The replay command cannot resolve `cat` under a PATH holding only the fake-bin directory | Real. DECISION: use the Python interpreter by absolute path (`sys.executable`) as the child, not `cat`. |
| L1 (34-08) | The typed fake recipe leaves `RunDeps(...)` and `run_check(...)` as ellipses | DECISION: specify two matching tool objects, inert typed deps and a fresh call list. |
| C1 (cross) | The ROADMAP still says "8 plans" and carries a stale open-question note | The planner updates the ROADMAP plan count and removes the stale note; acceptance-critical instructions live in the sections Pi receives. |
| C2 (cross) | 34-04's deselected run must not be described as a green `make test` | State it as a named red-guard exception in 34-04's SUMMARY instructions. |
| X | Final gates with the default TMPDIR | Standing ruling; not raised: keep the note in the 34-01 ledger only. |

## OpenCode Review (opencode-referee-one), cycle 3

Using the plan-review checklist, Ponytail Review, and codebase-memory to check all nine plans against the repository. I’ll distinguish resolved cycle-2 findings from remaining blockers and won’t run the installer, schedules, or containers.
The proposed `--frozen` flag protects `uv.lock`, not the whole checkout or filesystem. The new integration test also snapshots a scratch checkout that `setup.main` is not wired to use, then replays its output through the runner. Those are separate gaps in the write-boundary proof.
**What this change does:** Phase 34 adds a default-on daily check for installed-tool updates and updates to the installer checkout. It reuses the schedule lock and version service, writes one result line per completed check, and attempts a desktop notification when the known outdated set changes to a nonempty set.

**Verdict: revise before execution.** The cycle-2 revisions close several real gaps. The remaining blockers are that stale evidence can still change the notified set, the scheduled launch does not meet the stated write boundary, and the container harness can still certify the wrong invocation. The daily cadence, notifier argv choices, and owner-only desktop checks do not need to be reopened.

## 34-01

**Summary:** Registers the eighth row, adds `Schedule.daily`, and extends the engine, layout, and uninstall tests.

**Findings status:** The 29-failure baseline now has one coherent RED → production edits → untouched baseline → pin edits → GREEN sequence. The plan also distinguishes ordinary turn-off from uninstall and tests the actual GitHub-token-variable boundary.

**Strengths:** The daily flag replaces the calendar and editor decisions without changing Linux tmp cleanup’s fixed timer. The generic renderers already accept the new calendar, and the default-on reconcile gates only actual update rows on tool presence (`installer/schedules.py:838–850,925–955,1691–1712`; `installer/schedules_screen.py:377–396,496–502,569–581,713–727`).

**Concerns:**
- **HIGH — A directory at `update-check.json` can interrupt uninstall after partial cleanup.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-01-PLAN.md:135,155` inserts the path before the logs. The cleanup loop unlinks entries in order, so a directory there can raise after schedule state has already been deleted and before the logs are removed. The sweep then records the adapter as failed. The planned fixture only plants a regular file (`installer/schedules.py:1837–1853`; `installer/uninstall.py:829–838`; `tests/test_schedules_lifecycle.py:562–576`).

**Suggestions:** Leave an unexpected directory and its contents untouched, report it, and still clean the unrelated owned artifacts. Add that uninstall case alongside the regular-file fixture. Keep the proxy-parity test, but align the locked prohibition as noted under 34-06.

**Risk Assessment:** **High for uninstall recovery; low for the cadence design.** Keep the explicit no-rollout restriction through wave 4.

## 34-02

**Summary:** Adds the shared notifier, constant AppleScript source, Linux bus fallback, and runner-only environment forwarding.

**Findings status:** The raising socket probe now falls through, empty stderr gets a fixed reason rather than the command line, and 34-05 adds a fake-executable macOS failure path through the log. Real LaunchAgent delivery remains deferred.

**Strengths:** The existing subprocess helper passes argv without a shell and closes stdin. The runner and unit have distinct allowlists, so forwarding the bus at runtime does not require serializing it in either unit format (`installer/run.py:115–150`; `installer/helper_assets/schedule_runner.py:82–97,191–195`; `installer/daemon.py:34–59`).

**Concerns:**
- **MEDIUM — The real-child “bus unset” fixture does not pin the fallback.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:139–146,158` clears environment values but leaves the real-child case dependent on whether the current UID has a socket. Clearing the variables alone does not disable the planned `/run/user/<uid>/bus` probe, and the subprocess receives the adapter’s resulting environment (`installer/run.py:133–144`).
- **MEDIUM — Sanitized stderr is not necessarily safe to log or byte-stable.** The plan still forwards nonempty stderr and calls the helper’s result byte-stable (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-02-PLAN.md:143–147,158,240`). The subprocess wrapper retains stderr; control stripping does not remove credentials or echoed message text, and it preserves tabs that the runner later collapses (`installer/run.py:145–150`; `installer/sanitize.py:9–22`; `installer/helper_assets/schedule_runner.py:129–134`).

**Suggestions:** Inject a false socket probe in the no-bus test and explicitly isolate the environment inherited by the fake `osascript`. Prefer fixed notifier failure categories even with nonempty stderr. Assert byte equivalence for the assembled result, not for `reason_line` alone.

**Risk Assessment:** **Medium.** The selected platform argv forms can stay; the remaining issues concern deterministic tests and what reaches the log.

## 34-03

**Summary:** Threads the shorter freshness window and failure sink through the refresh service, adds `outdated_ids`, and replaces the final cache entry atomically.

**Findings status:** Mixed-source coverage and manager-snapshot reuse are now described correctly. The eligibility test covers an ordinary missing tool, not the dangling-artifact case. The final-symlink *write* is addressed; the read boundary is not.

**Strengths:** The plan threads the same window through budget accounting and the real fetch gate, without changing the default. Keeping the production resolver’s identity preserves the digest path. The pure helper correctly separates version status from health precedence (`installer/version_status.py:390–432,1879–1905,1029–1056`; `installer/version_cache.py:216–231`; `installer/versions.py:436–446`).

**Concerns:**
- **HIGH — The cache can block before the safe writer runs.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:196–204` widens decode handling but leaves both cache loaders on blocking, unbounded `read_text()`. The scheduled job reads the file before refresh and the service reads it again. A non-regular file can stall the check while it holds the shared lock (`installer/version_cache.py:156–179`; `installer/version_status.py:1838–1846`; `installer/schedule_run.py:136–148`).
- **MEDIUM — The test assertions miss the production path in two places.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:117–120` says every saved entry gets a failure stamp even though the service merges only the attempted 20 into the seeded 24. The digest test also omits `on_failure`, which the scheduled caller always supplies. A wrapper added only on that path could pass the test and discard digests (`installer/version_status.py:1975–1978,2013–2017`; `installer/versions.py:436–446`).
- **MEDIUM — “Eligible rows only” is broader than the fixture proves.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-03-PLAN.md:118,252–254` acknowledges the dangling-artifact exception. Ownership can come from a dangling artifact, and the budget decision precedes the presence check (`installer/uninstall.py:35–53`; `installer/ownership.py:1099–1106`; `installer/version_status.py:1870–1915`).

**Suggestions:** Reuse `read_capped` for both cache reads, with an explicit final-symlink policy and a non-regular-file test (`installer/atomic.py:186–215`). Assert exactly which 20 entries were stamped and run the digest test with the sink enabled. Either prove that dangling artifacts cannot spend scheduled slots or narrow the eligibility claim.

**Risk Assessment:** **High** until cache reads are bounded; the freshness plumbing itself fits the existing service.

## 34-04

**Summary:** Implements the Git self-check, notified-set persistence, membership decisions, oldest-attempt ordering, and result formatting.

**Findings status:** Failed origin queries and stale negative resolver results now preserve prior membership. The notified file has a strict, link-safe read/write design, and the named reachability exception is contained. Git isolation and confirmed-only membership remain incomplete.

**Strengths:** The self-update clause is independent of delivery, and the notified file uses the right two primitives: a capped, no-follow read and replacement of the file entry rather than its target (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:179,219,228`; `installer/atomic.py:58–73,186–215`).

**Concerns:**
- **HIGH — Stale evidence can still add or remove an ID.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:180,215–216,228` treats every `outdated_ids` hit as confirmed in. A failed or deferred resolver can return `outdated=True, stale=True`. Manager failures are less visible: the service backfills old maps, and the manager branch reports those comparisons with `stale=False`. An old report can therefore trigger a notice about an update already installed, or cause a false change in membership (`installer/version_status.py:186–194,401–431,642–689,1728–1758`).
- **HIGH — The Git boundary still permits behavior the plan rules out.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-04-PLAN.md:128–136,271–274` disables credential helpers but leaves configured `core.askPass` available; Git can try it before the terminal. The plan also acknowledges older Git may ignore the lazy-fetch setting, yet still issues object queries. Lastly, `git -C` does not prove the intended directory is the Git root: an unpacked installer nested inside another worktree can query that worktree’s origin (`installer/run.py:181–195`; `setup.py:539–543`; Git credentials manual, `gitcredentials.adoc:25–42`).

**Suggestions:** Keep Phase 35’s pure `outdated_ids` contract. For the daily check, use evidence that distinguishes confirmed comparisons from failed or deferred ones in **both** directions; test a stale positive and a failed manager query with a prior snapshot through the real service. For Git, verify the worktree root, disable configured prompting, and skip operations whose no-fetch or no-token guarantees cannot be enforced. Keep fixed diagnostic categories and require separate disposable Git evidence; pytest forbids real Git (`tests/sandbox.py:41–54`).

**Risk Assessment:** **High.** These gaps affect what the notification tells the user and whether the self-check stays within its read-only contract.

## 34-05

**Summary:** Wires the CLI, dispatch, shared lock, and runner, then adds log-path tests and a frozen child launch.

**Findings status:** The first task now clears the named orphan. Closed outer stdin, check-specific timeout text, and failing-`osascript` log composition are specified. The production write boundary is only partially addressed.

**Strengths:** The new kind fits the two existing lock branches without changing cleanup refusal. The runner is the right boundary for testing the single result line because it owns logging and chooses the child’s last recognized result (`installer/schedule_run.py:121–148`; `setup.py:547–567`; `installer/helper_assets/schedule_runner.py:345–358,484–523`).

**Concerns:**
- **HIGH — `--frozen` protects `uv.lock`, not the checkout or the allowed-write boundary.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:174,189,232` explicitly leaves uv cache and temporary-environment writes outside installer state. The child also runs from the checkout and imports local modules, so ordinary Python bytecode can create checkout files even with a frozen lockfile. The production refresh invokes `uv tool list --outdated` separately; the launch flag does not constrain that command (`installer/helper_assets/schedule_runner.py:191–195,320–340`; `setup.py:26–40,65–99`; `installer/compose.py:411–426`; `installer/manager_versions.py:253–258`). The locked constraint still prohibits outside writes.
- **MEDIUM — The “every child gets closed stdin” claim exceeds the proposed test and change.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-05-PLAN.md:181,189` closes stdin for the runner’s direct subprocess. That covers descendants on the scheduled route by inheritance, but the bare CLI’s refresh still reaches `run_query`, which does not close stdin itself (`setup.py:529–567`; `installer/version_status.py:1246–1255,1716–1727`; `installer/run.py:438–461`).

**Suggestions:** Define and enforce the scheduled launch’s write boundary before calling T-34-21 mitigated. Prevent checkout bytecode writes, account for uv and manager scratch/cache writes, and verify the real launch in a disposable environment. Either close stdin explicitly for manual-check queries too or qualify the claim and test the two routes separately.

**Risk Assessment:** **High for the non-mutating claim; low for the shared dispatch design.**

## 34-06

**Summary:** Adds check-row detail text, rendered viewport tests, and architecture, roadmap, and SPEC amendments.

**Findings status:** Permission-first, short limits before `last:`, a larger viewport for the full detail, and the narrower explanatory-copy rule are planned. The amendments still leave conflicting requirements in force.

**Strengths:** Testing the rendered widget is necessary here: `_set_detail` passes a row budget to `Rows`, which wraps and cuts text even when the backing string contains every line (`installer/schedules_screen.py:443–456`; `installer/ui_common.py:70–92`). The phase-specific docs pin follows an existing pattern (`tests/test_docs.py:217–240`).

**Concerns:**
- **HIGH — The architecture text documents exceptions that the SPEC still prohibits.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:170–172` documents credential-bearing proxies and outside-state uv writes, but its SPEC edits do not reconcile the prohibition or the write constraint (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md:68,121`). The proxy behavior is real and already pinned for private units (`installer/schedules.py:53,891–901,925–955`; `tests/test_systemd_daemon.py:1197–1211`). Documenting it in architecture notes does not amend a locked requirement.
- **MEDIUM — The acceptance and rendering instructions still conflict.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-06-PLAN.md:171–172,218` leaves SPEC acceptance 6 saying a separate self-update line and says ROADMAP criterion 5 is the only edit despite also prescribing goal and criterion 1 changes. Separately, the pilot at line 124 can retain the previous `Rows` height if it clears status in the same screen without repainting the detail (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-SPEC.md:22–25,79–84`; `installer/helper_assets/schedule_runner.py:345–358`; `installer/schedules_screen.py:443–456`).

**Suggestions:** Put the effective wording in the normative clauses, with a dated amendment record. Keep the selected cadence and clarify CLI stdout versus runner `waited:`, `start`, and one result. Record the existing proxy exception explicitly; do not treat outside-state writes as approved by implication. Use separately settled layouts for the viewport tests, or explicitly test the repaint after a status-height change.

**Risk Assessment:** **High for contract consistency; medium for UI test execution.** Keep real macOS delivery and notification attribution as owner UAT, not facts established by a golden argv.

## 34-07

**Summary:** Extends both disposable-container routes with a strict check-row verdict and separates the evidence each route provides.

**Findings status:** The obvious stale-success and standalone-busy cases are covered. A fresh pair still does not uniquely identify the requested launch.

**Strengths:** The generic driver already accepts the new ID. The plan correctly separates the check-row service proof, the cache-cleanup calendar and catch-up probes, and direct-mode limitations. The proposed edits are below the classified PATH lines (`tests/e2e_schedules_driver.py:46–85`; `scripts/container-e2e-verify.sh:2623–2668,2794–2812`; `tests/test_shell_scripts_path.py:519–539`).

**Concerns:**
- **HIGH — A new pair can belong to another activation.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:22,103–107,118` counts lines after enabling the live timer. If the timer fires between the baseline and the manual start, both can refer to the same active service invocation. Also, the current log reader hides read errors, so an unreadable baseline can look empty and old lines can look new later (`installer/schedules.py:980–991`; `installer/systemd_daemon.py:335–349`; `scripts/container-e2e-verify.sh:2489–2492,2576–2581`).
- **MEDIUM — The verdict and its fixtures disagree.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:106,110,118` expects `RUN_MISSING` for a lone new `start`, but the algorithm sends every one-line delta to `RUN_UNEXPECTED`. The direct spy only proves count forwarding. The existing host fixtures extract functions by explicit name and do not include the new helpers; the direct route also discards the argv producer’s exit status (`tests/test_container_e2e_schedules.py:84–100,501–517,783–811`; `scripts/container-e2e-verify.sh:2764–2769`).
- **MEDIUM — Cell time and teardown markers can misstate the outcome.** The plan slices `HH:MM` from the log and treats the teardown marker as evidence (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-07-PLAN.md:22–25,108,118`). The driver converts to its local time and can legitimately render `✓ 1d` after midnight. The teardown marker prints even if removal fails, and the runtime need not be Podman (`installer/schedules.py:517–536,570–582`; `tests/e2e_schedules_driver.py:46–51`; `scripts/container-e2e-verify.sh:224–230,2691–2698`).

**Suggestions:** Isolate the manual activation from timer firing or correlate the actual invocation. Fail closed on baseline-read and argv-generation errors. Test the exact fresh result sequence, allowing a legitimate `waited:` entry, and pin a direct launch that emits a valid pair but exits nonzero. Compare the Last cell using the driver’s clock rule, and confirm cleanup in the runtime that actually ran the container.

**Risk Assessment:** **High verification risk.** As written, the harness can certify the wrong run or reject a correct result.

## 34-08

**Summary:** Pins cross-file argv, CLI choices, environment keys, Phase 35 interfaces, and module rules.

**Findings status:** The duplicate fake notifier call is removed. Exact environment equality and resolved type annotations remain useful guards.

**Strengths:** The six-token slice matches the actual producer, and the runner parser exposes the ID the test needs. The environment equality can catch a dropped shared key, not just an extra one (`installer/schedules.py:853–888`; `installer/helper_assets/schedule_runner.py:82–97,432–474`; `installer/daemon.py:34–47`).

**Concerns:**
- **LOW — The typed fake recipe leaves its real inputs implicit.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-08-PLAN.md:106,115` leaves `RunDeps(...)` and `run_check(...)` as ellipses. The closest deps fixture supplies one tool; the proposed assertion needs two tool objects whose IDs match the fake states, along with the required typed collaborators (`installer/schedule_run.py:24–32`; `tests/test_schedule_update.py:119–148`).

**Suggestions:** Specify two matching tools, inert typed deps, and a fresh call list. Pass the bound notifier through `deps.notify` and keep the whole-list assertion. Treat static source scans as regression guards, not evidence that runtime diagnostics contain no secrets.

**Risk Assessment:** **Low.** This is a fixture-completeness issue, not a reason to change the Phase 35 interface.

## 34-09

**Summary:** Adds a real-service application test for refresh, adoption, receipt retirement, and cache-link replacement, followed by a runner-log replay.

**Findings status:** Moving receipts inside the snapshot and seeding the adoption digest address two cycle-2 fixture gaps. The new test still does not prove the claimed runner-to-job and checkout boundary.

**Strengths:** The four scenarios target real service branches. Receipt retirement and digest adoption are genuine effects of a refresh, and the autouse fixture would otherwise hide the receipt paths from the HOME snapshot (`installer/version_status.py:1455–1537`; `tests/conftest.py:377–389`; `tests/test_version_status.py:4352–4372`).

**Concerns:**
- **HIGH — The checkout snapshot does not cover the checkout used by the check.** `.planning/phases/34-daily-update-check-with-a-desktop-notification/34-09-PLAN.md:99–102,127,144` creates `tmp_path/co`, but the in-process call derives its checkout from `setup.__file__`. Nothing in the fixture redirects that value or asserts the Git call’s `-C` path. The later fake `uv` only replays output, and the filesystem comparison precedes it. The test can pass with the wrong checkout or broken runner-to-child wiring (`setup.py:529–561`; `installer/helper_assets/schedule_runner.py:320–358`).
- **MEDIUM — The replay command cannot resolve `cat` under the specified PATH.** The fixture sets PATH to the fake-bin directory only and then invokes unqualified `cat` (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-09-PLAN.md:100–101`). The runner forwards that PATH; with only the named fake binary present, the replay child fails (`installer/helper_assets/schedule_runner.py:82–97,191–195,228–234`).

**Suggestions:** Bind the application job to the scratch checkout and assert the exact path seen by the Git seam. Have the runner’s fake child invoke the real parser, wiring, and dispatch rather than replay a line; snapshot across that call. If replay remains a separate log test, label it as such and use an explicit safe utility path. Neither test replaces the disposable real-launch evidence for uv or Git.

**Risk Assessment:** **High verification risk.** The application scenarios are valuable; their current scope is narrower than the phase sign-off claims.

## Cross-plan assessment

1. **Fix the production boundaries before adding more sign-off checks.** Prioritize bounded cache reads, confirmed-only membership, the noninteractive Git boundary, and the scheduled write boundary. Then update the validation map to identify which evidence proves each property.
2. **Keep the release and test gates visible.** The named 34-04 reachability exception matches the review ledger; 34-05 Task 1 now clears it through a real import, with the guard unchanged. Do not describe 34-04’s deselected run as a green `make test`, or deploy any pre-wiring wave (`.planning/phases/34-daily-update-check-with-a-desktop-notification/34-REVIEWS.md:46,54`; `tests/test_reachability.py:142–162,196–197`; `Makefile:63–64`).
3. **Give the executor and verifier one consistent contract.** Update the roadmap’s “8 plans” count and stale open-question note: it already lists nine waves and includes the self-check (`.planning/ROADMAP.md:308–322,349–350`). Carry all acceptance-critical instructions in the sections Pi actually receives. Keep fake-process tests, disposable Git/uv/container observations, and owner desktop UAT separate; none is a substitute for the others.

**Status: Issues found — revise before execution.** This was a read-only review of all nine on-disk plans and their source seams. No files were edited, and no tests, installer jobs, containers, or desktop notifications were run.
