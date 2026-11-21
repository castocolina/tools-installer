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
