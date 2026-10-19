---
phase: 21
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-19T03:18:07Z
cycle: 1
plans_reviewed: [21-01-PLAN.md, 21-02-PLAN.md, 21-03-PLAN.md, 21-04-PLAN.md, 21-05-PLAN.md, 21-06-PLAN.md, 21-07-PLAN.md, 21-08-PLAN.md, 21-09-PLAN.md, 21-10-PLAN.md, 21-11-PLAN.md, 21-12-PLAN.md, 21-13-PLAN.md, 21-14-PLAN.md, 21-15-PLAN.md, 21-16-PLAN.md, 21-17-PLAN.md, 21-18-PLAN.md, 21-19-PLAN.md, 21-20-PLAN.md, 21-21-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 21

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## Cycle 1 (current) — reviewed at HEAD ccfca9f

Reviewer: opencode-plan-review (`opencode run --model router-env/my-plan-review`, the router lane; no direct alternate was needed). Single reviewer, so the consensus gate is skipped. The reviewer was told that 21-CONTEXT.md, 21-SPEC.md and the approved 21-UI-SPEC.md are locked, and that the 21-REUSE.md orchestrator notes are part of the plans they name. It read all 21 plans and the supporting artifacts from disk, cited source `file:line` throughout (36 source citations), and gave every plan id its own section (plan coverage 21/21).

## OpenCode Review (opencode-plan-review)


**Verdict: revise before execution.** The plans have a coherent implementation path and substantial test coverage, but several written contracts can produce false removal results, stale or missing state, or a mutation lock that never releases. I reviewed all 21 plans against the locked context, specification, UI contract, REUSE instructions, and current source. Source citations describe the **current** tree; the planned code has not landed.

### 21-01

**Summary:** Establishes a neutral root and one clear → pop → push → enter path for all six views.

- **Strengths:** Starting `current_view` at a root sentinel avoids the current base-view early return; pushing before entry lets first-entry rendering use mounted widgets (`.planning/phases/21-one-screen-family/21-01-PLAN.md:79-81,113-128`; `installer/wizard_app.py:2630,2759-2785`).
- **Concerns:** **LOW** — The call-order and status pilots are more meaningful than the symbol-count gates (`21-01-PLAN.md:113-151`). Keep them as the acceptance evidence.
- **Suggestions:** Test warning-flush precedence on a second view as well as Uninstall; the current flush replaces a status rather than merging one (`installer/wizard_app.py:2792-2796`).
- **Risk Assessment:** **LOW–MEDIUM**; lifecycle ordering is addressed, with a narrow status-precedence risk.

### 21-02

**Summary:** Adds removal outcomes to the shared vocabulary without making removal an install-engine action.

- **Strengths:** Keeping `REMOVE` outside `RUNNABLE` protects the existing install dispatch boundary (`21-02-PLAN.md:94-105`; `installer/session.py:112-121,738-805`).
- **Concerns:** **LOW** — Adding a disposition also affects generic review iteration; the plan does not directly assert that `build_plan` never emits `REMOVE` (`21-02-PLAN.md:65-67`; `installer/session.py:197-200`).
- **Suggestions:** Add that boundary assertion. Apply REUSE’s extension of the existing failure-detail branch, not a duplicate branch (`21-REUSE.md:63-68`; `installer/render.py:147-162`).
- **Risk Assessment:** **LOW**; REUSE supplies the simpler rendering implementation.

### 21-03

**Summary:** Prunes selections on reload and filters selectable IDs again at acceptance.

- **Strengths:** In-place pruning preserves the shared selection set, while the acceptance filter covers the period before another reload (`21-03-PLAN.md:89-98`; `installer/tool_browser.py:235-251,356-365`).
- **Concerns:** **LOW** — Browser acceptance alone is not an execute-boundary proof: the catalog handler builds its decision from `_staged`, not the acceptance event’s IDs (`installer/catalog_tui.py:896-907`).
- **Suggestions:** Keep the downstream catalog-input pilot in 21-06 and assert the rejected ID is absent there.
- **Risk Assessment:** **LOW**; the downstream test closes the remaining boundary.

### 21-04

**Summary:** Makes policy prerequisites and OMZ activity live.

- **Strengths:** `Policy.missing_requirements()` already supplies the live-read seam; the planned OMZ `is_active` predicate addresses a construction-time snapshot (`21-04-PLAN.md:85-96,122-133`; `installer/policy.py:166-170,790-800`).
- **Concerns:** **MEDIUM** — The plan’s Task 2 still describes widening and testing `linux_daemon_policy(installed_tools=...)`, whereas binding REUSE instructions delete that unused parameter and update callers outside the plan’s file list (`21-04-PLAN.md:113-145`; `21-REUSE.md:9-20`; `installer/policy.py:1036-1044,1089-1095`; `setup.py:599-605`). REUSE resolves the design, but the executor’s file scope and original count gates must follow it.
- **Suggestions:** Treat REUSE’s caller migrations, replacement test floor, and revised predicate count as Task 2’s acceptance criteria.
- **Risk Assessment:** **MEDIUM**; a literal execution of the unamended task would break callers.

### 21-05

**Summary:** Adds precise pending-tool suppression, Doctor evidence, and a cached-inventory pnpm finding.

- **Strengths:** Filtering pending IDs at the service’s commit point prevents an older pass from restoring a removed tool’s mark (`21-05-PLAN.md:99-106`; `installer/version_status.py:1727-1760`). REUSE correctly redirects missing-command detection to the existing audit rule (`21-REUSE.md:22-39`; `installer/pnpm_globals.py:556-580`).
- **Concerns:** **HIGH** — The planned off-PATH finding is carried as a note on an **absent** tool and the test explicitly expects `Health.MISSING` (`21-05-PLAN.md:73,168-179`). The locked specification and UI contract require a dangling pnpm shim to show `!` on its tier (`21-SPEC.md:90-98`; `21-UI-SPEC.md:165-169`); `tool_health` returns `MISSING` for an absent tool regardless of broken facts (`installer/version_status.py:218-251`). Resolve this conflict before implementing 21-19’s tier/Doctor parity test.
- **Suggestions:** Specify the evidence and health classification for the dangling-shim fixture, then test its actual tier glyph, not only its reason. Adapt the frozen service to pending semantics before using it in screen pilots (`tests/state_doubles.py:244-264`).
- **Risk Assessment:** **HIGH**; as written, a named phase acceptance criterion can fail.

### 21-06

**Summary:** Replaces per-tier refresh workers with one coalescing app owner.

- **Strengths:** The event-loop running/pending flags avoid relying on Textual worker cancellation to prevent overlapping threads (`21-06-PLAN.md:97-106`; `installer/version_status.py:1582-1614`). The modal publication behavior follows the locked top-screen rule (`21-CONTEXT.md:51-58`).
- **Concerns:** **HIGH** — The worker posts a failed refresh result, then posts a clean-looking publication after `refresh_skills`; the clean handler clears the error it just displayed (`21-06-PLAN.md:101,152`). `run_live` returns errors instead of raising them (`installer/ui_common.py:42-55`). A failed initial pass can therefore leave `…` rows without the promised retry instruction. **MEDIUM** — The proposed second publication also discards a `refresh_skills` error (`21-06-PLAN.md:152`).
- **Suggestions:** Carry failure through the complete worker or do not emit a clean publication after failure. Assert final status after both worker stages. Apply REUSE’s test-helper migration, including the many deleted-flag waits (`21-REUSE.md:41-56`).
- **Risk Assessment:** **HIGH**; failure reporting can contradict the displayed state.

### 21-07

**Summary:** Connects Uninstall and refused `u` paths to the app refresh owner and removes the ownership message fork.

- **Strengths:** The message seam accommodates bare-screen tests, and the existing `u` action has identifiable refusal branches (`21-07-PLAN.md:71-76,143-167`; `installer/catalog_tui.py:787-825`).
- **Concerns:** **MEDIUM** — This plan’s Uninstall request remains transitional: the environment-only removal path lacks the tool-count-gated invalidation it uses (`21-07-PLAN.md:75,103-115`; `installer/wizard_app.py:1493-1505`). Plan 21-14 must close that gap; a pass-count test here alone is not UI-01 proof.
- **Suggestions:** Label environment-only removal as deferred in this plan’s acceptance and assert the final path in 21-14.
- **Risk Assessment:** **MEDIUM**; acceptable only with the stated downstream dependency.

### 21-08

**Summary:** Defines pure Uninstall group, label, and detail projections over `ToolState`.

- **Strengths:** The group rules keep unproven and unknown-owner tools out of removable rows (`21-08-PLAN.md:103-109`; `installer/version_status.py:705-728`; `installer/ownership.py:1602-1641`).
- **Concerns:** **MEDIUM** — REUSE moves the existing health-detail table from `catalog_tui.py` to `version_status.py` and changes its readers, but that cross-file work is absent from the plan’s listed files (`21-REUSE.md:70-76`; `21-08-PLAN.md:7-9`). Without it, the shared-copy acceptance check cannot pass.
- **Suggestions:** Include the catalog import and both reader migrations in Task 1’s explicit scope.
- **Risk Assessment:** **MEDIUM**; the intended implementation is sound, but the amended file scope is incomplete.

### 21-09

**Summary:** Converts removal into per-tool re-proof, deletion, and outcome reporting.

- **Strengths:** `remove_proven` remains the deletion authority and re-verifies proof at delete time (`21-09-PLAN.md:68-73`; `installer/uninstall.py:532-557`).
- **Concerns:** **HIGH** — The plan attributes previewed paths using a *new* `plan_removal([tool])`, then treats paths absent from that new plan as unmatched warnings (`21-09-PLAN.md:68-71,106-108`). If one of a tool’s previewed artifacts disappears while another remains removable, that tool can be reported `removed` despite a refused previewed path. The current remover explicitly reports every previewed path not removed (`installer/uninstall.py:546-553`).
- **Suggestions:** Require every previewed path attributable to a selected tool to be removed before reporting that tool as `removed`; add a partial-drift fixture, not only an all-refused fixture.
- **Risk Assessment:** **HIGH**; destructive-operation success could be overstated.

### 21-10

**Summary:** Joins ExecuteScreen’s state waiter to app publication rather than starting a private pass.

- **Strengths:** Retaining its token and `StateSettled` handling preserves the existing fail-closed review boundary (`21-10-PLAN.md:69-73,107-109`; `installer/execute_screen.py:559-584`).
- **Concerns:** **MEDIUM** — `await_publication` may have to start a pass when none is running, but the held test assumes a launch pass is already in progress (`21-10-PLAN.md:24,98-100`). The current execute test host does not inject `version_refresh` into `UnifiedApp` (`tests/test_execute_screen.py:320-337`).
- **Suggestions:** Test both event orders deterministically: review arrives before a pass starts and review joins a pass already running.
- **Risk Assessment:** **MEDIUM**; the waiter’s ordering contract needs a stronger pilot.

### 21-11

**Summary:** Replaces Uninstall’s rows input with published-state rows and adds the Health column.

- **Strengths:** Pre-pass emptiness is distinguished from “nothing installed”; `ToolBrowser.reload` can retain a keyed cursor, and the width backstop covers the destructive screen (`21-11-PLAN.md:126-134`; `installer/tool_browser.py:186-225`).
- **Concerns:** **MEDIUM** — The explicit painted-row rule retains old paths and selectability when state becomes unknown (`21-11-PLAN.md:32,90-94`). Deletion-time re-proof prevents unauthorized deletion (`installer/uninstall.py:532-553`), but a row can still offer a preview based on prior rather than current proof. This is a user-facing truth trade-off, not a proof bypass.
- **Suggestions:** Test ordinary invalidation separately from removal-pending state. Make the preview say that proof is being rechecked if a painted selectable row remains available. Apply REUSE’s `_VIA_*` deletion and Rich truncation instructions (`21-REUSE.md:78-89`).
- **Risk Assessment:** **MEDIUM**; removal safety survives, but the selectable UI can be misleading.

### 21-12

**Summary:** Deletes the classifier and owner-hint fork after the new Uninstall projection lands.

- **Strengths:** It retains the actual removal planner and dependency utilities rather than deleting proof logic with presentation logic (`21-12-PLAN.md:96-110`; `installer/uninstall.py:136-196,351-356`).
- **Concerns:** **MEDIUM** — The replacement is wave 5 and the fork deletion wave 6 (`21-11-PLAN.md:5-6`; `21-12-PLAN.md:5-6`), although locked D-16 says each fork is deleted in the **same wave** as its replacement (`21-CONTEXT.md:100-103`). Calling adjacent waves one “logical” step in 21-11 does not meet that wording (`21-11-PLAN.md:96`).
- **Suggestions:** Put the serialized replacement and deletion in one wave, or obtain an explicit amendment to D-16.
- **Risk Assessment:** **MEDIUM**; the final tree can be correct, but the execution sequence violates a locked decision.

### 21-13

**Summary:** Runs removal on a worker, marks only its tools pending, and introduces the app mutation lock.

- **Strengths:** Acquiring the lock before launch and posting completion from `finally` gives the worker a release path even on failure (`21-13-PLAN.md:25-30,129-135`).
- **Concerns:** **MEDIUM** — Task 1 introduces `refuse_if_mutating` without the required refresh request; Task 2 adds that contract in a separate supposedly green commit (`21-13-PLAN.md:27-28,129-130,158-175`). **MEDIUM** — `mark_pending` needs an immediate visible render at removal start: merely changing service state does not itself invoke the app’s publish renderer (`21-CONTEXT.md:74-78`; `21-06-PLAN.md:152`).
- **Suggestions:** Make refusal-plus-request atomic and assert `…` on the already-visible tier before the removal worker finishes.
- **Risk Assessment:** **MEDIUM**; both issues are local but affect the promised in-flight behavior.

### 21-14

**Summary:** Adds failed-row feedback, unconditional follow-up refresh, retry, and quit-wait behavior.

- **Strengths:** It covers environment-only removal and invalidation failure (`21-14-PLAN.md:101-106`). Its worker wait accounts for Textual’s failure/cancellation exceptions (`21-14-PLAN.md:146-154`).
- **Concerns:** **HIGH** — A partial delete may leave no newly proven removable path. After refresh, the row becomes unselectable and reload prunes it, making the promised “failed row stays selected; Enter retries” impossible (`21-14-PLAN.md:22-25,102-112`; `tests/test_uninstall.py:1598-1639`; `installer/tool_browser.py:235-251`). **HIGH** — Keeping `_navigable()` ahead of the soft-quit wait means `q` under a modal still does nothing (`21-14-PLAN.md:75,154`; `installer/wizard_app.py:3061-3070`), contrary to the unqualified removal quit copy in `21-UI-SPEC.md:119-130`. **MEDIUM** — Clearing `_failed_lines` on entry loses the row’s error before retry (`21-14-PLAN.md:72-74,112`).
- **Suggestions:** Make retry conditional on fresh removability, retain failure guidance otherwise, and test partial deletion. Define modal soft-quit behavior explicitly and preserve the error across navigation until resolved.
- **Risk Assessment:** **HIGH**; retry and quit promises are not reliably achievable as written.

### 21-15

**Summary:** Folds update, job-toggle, and default-daemon guards into the one lock.

- **Strengths:** Fixed holder nouns and completion-handler release match the UI contract; the existing update worker already posts completion from `finally` (`21-15-PLAN.md:26-31`; `installer/catalog_tui.py:831-849`).
- **Concerns:** **HIGH** — The plan locks whenever a daemon callback is wired and unlocks on `DaemonDefaultApplied` (`21-15-PLAN.md:80,169`), but the current daemon worker posts that message only when `daemon_default_policy_id` is non-`None`; the constructor accepts callback and ID independently (`installer/wizard_app.py:2507-2509,2729-2733`). A callback without an ID can permanently block mutations.
- **Suggestions:** Enforce paired arguments at construction or make completion/release unconditional, and test the callback-without-ID case. Use REUSE’s shared `settle` migration rather than replacing old flag loops with new loops (`21-REUSE.md:58-61`).
- **Risk Assessment:** **HIGH**; a valid constructor shape can leave the app locked.

### 21-16

**Summary:** Guards remaining mutating keys and completes the shared lock-holder vocabulary.

- **Strengths:** The key matrix, fixed refusal strings, and crash pilot cover the main safety boundary (`21-16-PLAN.md:111-114,153-159`).
- **Concerns:** **MEDIUM** — “Every refused mutation ends with one pass” needs a precise definition across Doctor’s existing early returns (`21-16-PLAN.md:25,112`; `installer/wizard_app.py:651-653,737-774`). **MEDIUM** — The install holder begins on `InstallRunStarted`, after catalog acceptance has already pushed ExecuteScreen (`21-16-PLAN.md:82-83`; `installer/wizard_app.py:2884-2888,2969-2971`).
- **Suggestions:** Enumerate which early returns are refusal events and assert each pass count. Add a held hand-off pilot proving a second mutation cannot start between acceptance and install-run lock acquisition.
- **Risk Assessment:** **MEDIUM**; the remaining issue is timing and contract coverage.

### 21-17

**Summary:** Renders Policies activity and prerequisites on entry and publication, blanking failed live reads.

- **Strengths:** The `installed_or` seam avoids a blocking presence probe on the render path, and the failed-read test rejects a stale ON/OFF cell (`21-17-PLAN.md:83-86,113-119,159-167`; `installer/policy.py:166-170`).
- **Concerns:** **MEDIUM** — A failed state read blanks the State cell, but the existing detail builder independently calls `missing_requirements()` (`installer/wizard_app.py:1746-1748,1847-1861`). The plan does not pin what Requires and detail display when *their* live reads fail (`21-17-PLAN.md:159-167`).
- **Suggestions:** Cover failed prerequisite/detail reads as well as `is_active`. Do not raise OMZ staleness as an omission here: 21-04 already supplies its live predicate (`21-04-PLAN.md:122-133`).
- **Risk Assessment:** **MEDIUM**; partial-row failure handling needs definition.

### 21-18

**Summary:** Adds DRIFT, reads systemd-backed state off-loop, and republishes after toggles.

- **Strengths:** DRIFT requires both owned and inactive; the worker pilot checks the thread used, not merely the final cell (`21-18-PLAN.md:71-75,99-105`).
- **Concerns:** **HIGH** — `exclusive=True` cancels a Textual worker but does not stop a thread already performing a probe. `JobStatesRead` carries no generation, so an older result may arrive after a newer render and repaint stale ON/OFF/DRIFT (`21-18-PLAN.md:74,110`). Doctor already uses a generation to reject this exact class of late audit result (`installer/wizard_app.py:481-494,828-835`).
- **Suggestions:** Carry an entry/read generation and discard superseded job-state messages; test reversed completion order.
- **Risk Assessment:** **HIGH**; the live screen can show an older answer as current.

### 21-19

**Summary:** Routes Doctor’s pnpm findings through `ToolState.reasons` and keeps console formatting.

- **Strengths:** Changed-only evidence prevents a full pass on every Doctor entry, and the existing audit generation protects against stale audit completion (`21-19-PLAN.md:80,108-112`; `installer/wizard_app.py:828-835`).
- **Concerns:** **HIGH** — Removing `node_globals_guidance` from TUI rendering while recording only smoke failures and split-group notes drops the existing **incomplete-group** finding (`21-19-PLAN.md:78-80,120`). `NodeGlobalsReport` explicitly distinguishes incomplete from split groups (`installer/pnpm_globals.py:159-178`), and the old formatter handles that condition (`installer/guidance.py:382-400`). Locked D-13 calls for incomplete global findings in the shared reasons channel (`21-CONTEXT.md:92-95`; `21-SPEC.md:90-97`).
- **Suggestions:** Map incomplete groups into per-tool evidence and test a previously supported partial-install fixture before removing the old TUI renderer.
- **Risk Assessment:** **HIGH**; a named diagnostic would disappear.

### 21-20

**Summary:** Removes Doctor’s hidden `a`, republishes fixes, and rerenders after the first-run link pick.

- **Strengths:** It retains the existing consented `r` package set and uses the planned completion handler (`21-20-PLAN.md:62-65`; `installer/wizard_app.py:786-795`).
- **Concerns:** **HIGH** — Invalidation is moved inside the reinstall worker after mutation, but the plan does not define a guaranteed completion post or visible invalidation failure (`21-20-PLAN.md:62,98`). `run_live` catches named operational errors, not arbitrary exceptions (`installer/ui_common.py:42-55`); an exception after a successful reinstall could bypass the lock-release message established in 21-16. **MEDIUM** — Doctor `enter` can continue into guard-file confirmations after its first fix (`installer/wizard_app.py:651-674`), so a pass requested only after the initial fix need not reflect the final mutation.
- **Suggestions:** Post completion in `finally`, report invalidation failure, and test it after a successful fake reinstall. Define publication after confirmed guard edits.
- **Risk Assessment:** **HIGH**; the exceptional path threatens both truth and lock release.

### 21-21

**Summary:** Adds the final source × target matrix, deleted-fork guard, architecture documentation, and human terminal check.

- **Strengths:** Real key-path drivers and a guard over tracked plus untracked, non-ignored source are stronger than a snapshot or a `git grep` of tracked files alone (`21-21-PLAN.md:104-115,142-155`).
- **Concerns:** **MEDIUM** — Binding REUSE places `matrix_app` and matrix constants in `tests/test_screen_family.py`, but the plan’s file artifacts, task text, and grep target still put them in `tests/screen_family.py` (`21-REUSE.md:91-100`; `21-21-PLAN.md:34-36,97-126`). **MEDIUM** — The 42-case matrix treats “visible” as the source view, then navigates to other targets only *after* settling (`21-21-PLAN.md:76,104-106`). It cannot prove immediate repaint of another view that was already visible when background work finished. **LOW** — The UAT allowance for a wrapped refusal conflicts with the approved one-row refusal contract (`21-21-PLAN.md:23`; `21-UI-SPEC.md:262-273`).
- **Suggestions:** Apply REUSE’s location and gate changes throughout. Add one held mutation that navigates to a different target before completion, then checks repaint without re-entry; require the locked one-row refusal width.
- **Risk Assessment:** **MEDIUM**; the final matrix otherwise overclaims its immediate-publication coverage.

#### Cross-plan priorities

1. **Correct removal truth before building its UI:** 21-09’s partial-drift attribution feeds 21-13/14’s summaries and retry selection (`21-09-PLAN.md:68-71`; `21-14-PLAN.md:22-25`). Fix the outcome contract first.
2. **Protect completion and ordering:** 21-06’s two publications, 21-15’s conditional daemon completion, 21-18’s unordered probes, and 21-20’s post-mutation exception each permit a stale answer or stuck lock. Their tests need held or reversed completions, not only eventual success.
3. **Close the locked pnpm contract:** 21-05’s MISSING glyph conflicts with the required `!`, and 21-19 omits incomplete groups (`21-SPEC.md:90-98`; `installer/version_status.py:218-251`; `installer/pnpm_globals.py:159-178`).
4. **Honor execution boundaries:** Apply REUSE as part of the affected tasks, and reconcile 21-11/12’s adjacent waves with D-16 before dispatch (`21-REUSE.md:7`; `21-CONTEXT.md:100-103`).

**Not checked:** I did not run tests, execute the plans, or perform NO_COLOR container UAT. This is a read-only review of plan contracts against the current source; runtime and coverage-floor claims remain to be verified during execution.

---

## Source-grounding adjudication of the reviewer's HIGHs

Each HIGH was traced against the current tree (HEAD `ccfca9f`) and the plan text. Four are refuted on their premise; five stand.

| Plan | Reviewer HIGH | Verdict | Evidence |
|---|---|---|---|
| 21-05 | The off-PATH pnpm fact yields `MISSING`, but the locked SPEC requires a dangling shim to show `!` | **REFUTED** | A "dangling shim" (todo `2026-09-16-detect-dangling-pnpm-global-bin-shims-in-doctor`: shim on PATH, package gone from pnpm's manifest) is already a BROKEN fact: `installer/version_status.py:608` `BROKEN_SHIM_REASON`, `:626` `dangling_shim(...)`, `:760` adds it to `broken_facts`, so the tier shows `!`. 21-19 pins it (`21-19-PLAN.md:110` `test_a_dangling_pnpm_shim_reads_broken_in_doctor_and_on_the_tier`). The 21-05 fact covers the reverse case (pnpm tracks the package, the command is gone). It is a MISSING row with a note, which RESEARCH A4 (`21-RESEARCH.md:620`) records explicitly. |
| 21-06 | After a failed `refresh`, the second `RefreshPublished(None, warning)` posted after `refresh_skills` is a clean publish that clears the retry copy; a `refresh_skills` error is dropped | **CONFIRMED** | `21-06-PLAN.md:152`: the worker posts `RefreshPublished(None, warning)` after `refresh_skills` whatever happened, and "on a clean publish clear the remembered line". `tests/state_doubles.py:307-312`: `HeldRefreshService.raising` raises only in `refresh`. `refresh_skills` is inherited and succeeds, so the plan's own `test_failed_pass_writes_the_retry_copy` (`21-06-PLAN.md:135`) would go red against the action as written. |
| 21-09 | Per-tool attribution through a fresh `plan_removal([tool])` can report a tool `removed` while one of its previewed paths was refused | **REFUTED** | Every existing path matched by name lands in `removable` or `yourself` (`installer/uninstall.py:62-70`), so it is attributed and a refusal makes the tool `remove_failed`. Any drifted or vanished receipt artifact voids the whole receipt proof (`uninstall.py:97-98`: `receipts.drifted(...)` returns `()`), so the tool's remaining paths stop being removable and are refused. Only paths that no longer exist go unmatched, and they still get the `changed since the preview` warning line. |
| 21-14 (a) | A failed row can't "stay selected; Enter retries" once the follow-up pass prunes it | **CONFIRMED (narrowed)** | This holds for refusals (the path is no longer proven). After the follow-up pass publishes, the tool is no longer `removable here`, so 21-03's reload prune (`21-UI-SPEC.md:180`, `installer/tool_browser.py:235-251`) drops it. That contradicts `21-14-PLAN.md:23` and `21-UI-SPEC.md:130`. An `OSError` failure keeps its proof, so that row does stay. The painted-row memory (`21-11-PLAN.md:92`) only covers the window before the pass publishes. The plan must define which failures stay selectable after the pass. |
| 21-14 (b) | `q` during a removal still does nothing under the nav palette, because `_navigable()` returns first | **CONFIRMED (low impact)** | `installer/wizard_app.py:3061-3066`: this guard exists today, by design. `ctrl+c` (`:3068-3070`) stays unguarded, and `21-14-PLAN.md:75` routes it through `_exit_after_removal`, so a quit never cuts a delete. The `21-UI-SPEC.md:129` quit row is silent on modals. The plan needs one sentence that states the modal behaviour. |
| 21-15 | The lock is taken whenever a daemon callback is wired, but it is released only by `DaemonDefaultApplied`, which is posted only when `daemon_default_policy_id` is set | **CONFIRMED (latent)** | `installer/wizard_app.py:2639` sets the flag on `daemon_default is not None`. `:2729-2733` posts only when the id is not None. `21-15-PLAN.md:80,169` carry this over to the app-wide lock. Production pairs the two arguments (`setup.py:1100-1129`), but the constructor accepts a callback without an id, and that app would refuse every mutation forever. |
| 21-18 | `JobStatesRead` has no generation, so an older thread's late result can repaint stale ON/OFF/DRIFT | **CONFIRMED** | `21-18-PLAN.md:74`: `exclusive=True` plus a `finally:` post, with no generation or entry token. A Textual thread worker that is cancelled keeps running and still posts. Doctor already guards this race with a generation (`installer/wizard_app.py:481-494`, `:828-835`). |
| 21-19 | Dropping `node_globals_guidance` from the TUI drops the incomplete-group finding | **REFUTED** | Incomplete co-install groups are already computed in the refresh pass and reach `ToolState.reasons`. `installer/version_status.py:663-685` `_pnpm_group_facts` (D-19) is wired into `_pass` at `:1633`. Doctor renders those reasons (`21-19-PLAN.md:77`). |
| 21-20 | An exception after a successful reinstall could bypass the lock release | **REFUTED (lock); residual MEDIUM** | 21-16 makes `_reinstall_globals_worker` `exit_on_error=False` and posts `GlobalsReinstalled` from `finally:` with a default error (`21-16-PLAN.md:27,81`). The handler's first statement releases the lock, and 21-20 builds on that (`21-20-PLAN.md:62`). Two gaps remain. A failed `invalidate` (a `run_live` error) is not surfaced. An unexpected exception after a successful reinstall is reported as `the reinstall did not complete`. |

### Disposition of the reviewer's MEDIUM/LOW findings

- **Already incorporated, not counted:**
  - 21-03 downstream proof: `21-06-PLAN.md:195`, `test_publish_prunes_a_staged_tool_that_became_unavailable`, exits with `["fd"]` only.
  - 21-04 file scope: REUSE 04-1.
  - 21-07 env-only invalidation: 21-14 W2 makes every removal end with `request_refresh()` (`21-14-PLAN.md:24,71`).
  - 21-08 `HEALTH_DETAIL` move and reader migration: REUSE 08-1.
  - 21-11 painted row: explicit rationale at `21-11-PLAN.md:92`, because `remove_proven` re-proves at deletion.
  - 21-11 `_VIA_*` and truncation: REUSE 11-1/11-2.
  - 21-12 D-16 "same wave": explicit rationale at `21-11-PLAN.md:96`. It reads the locked D-16 as the logical 21-11+21-12 step. The user should confirm that reading.
  - 21-13 mark_pending render: `21-13-PLAN.md:132` re-renders the visible Uninstall screen. Other views render from state on entry.
  - 21-13 Task-1/Task-2 refusal split: normal TDD sequencing; the final contract is pinned.
  - 21-15 `settle` migration: REUSE 15-1.
  - 21-16 install-run window: ExecuteScreen is modal from acceptance on, so no other view's mutating key is reachable.
  - 21-17 OMZ staleness: 21-04.
  - 21-21 matrix location: REUSE 21-1.
- **Still actionable (counted):**
  - 21-02 needs a boundary assertion that `build_plan` never emits `REMOVE`.
  - 21-10 needs a pilot for the ordering where the review arrives while no pass is running.
  - 21-14 clears `_failed_lines` on `enter_view`, so a failed row loses its reason before the retry.
  - 21-16 must say which Doctor early returns (`installer/wizard_app.py:651-653`, `:737-774`) count as refusals, and pin the pass count for each.
  - 21-17 does not define what Requires and the detail bar show when a live read of `missing_requirements()` fails (`installer/wizard_app.py:1746-1748`, `:1847-1861`).
  - 21-20 does not surface a failed `invalidate`. It also does not say whether the Doctor `enter` pass request waits for the guard-file confirmations that follow the fix (`installer/wizard_app.py:667-674`).
  - 21-21 has no held-mutation case where the user navigates to another view before completion and gets an immediate repaint without re-entry.
  - 21-21 UAT allows "a wrapped refusal on its own second row" (`21-21-PLAN.md:23`), but the locked contract says every refusal fits one row (`21-UI-SPEC.md:273`).

## Consensus Summary

Single reviewer (opencode-plan-review, source-grounded: `file:line` citations throughout), so no cross-reviewer consensus is possible. Reviewer verdict: revise before execution. After source grounding, 5 HIGHs stand (21-06, 21-14 ×2, 21-15, 21-18) and 4 are refuted (21-05, 21-09, 21-19, 21-20).

### Agreed Strengths
- (single reviewer) The wave chain is serialized and the forks are deleted beside their replacements. Re-proof at deletion stays the one removal authority (`installer/uninstall.py:532-557`). The 42-case matrix uses real key paths.

### Agreed Concerns
- n/a (one reviewer). Unresolved items are listed in the adjudication above.

### Divergent Views
- None (one reviewer). Source grounding overturned four of the reviewer's nine HIGHs; see the table.

## Verification coverage

Source-grounding pass (`plan_review.source_grounding = true`; effective authority `intel` via `drift-guard authority --raw`; severities via `drift-guard severity`: VERIFIED → none, MISSING → needs-acknowledgement, AMBIGUOUS → MEDIUM, UNCHECKABLE → INFO; nothing set `hardBlock`):
- **File paths:**
  - VERIFIED: all 48 distinct existing repo paths extracted from the 21 plans (including `scripts/detect-container-runtime.sh`), plus `.claude/architecture.md`.
  - Excluded as new artifacts of this phase: `tests/test_screen_family.py` (created by 21-01) and `tests/screen_family.py` (created by 21-06).
- **Symbols:** 140 distinct backticked call-form symbols were extracted from the plans; 74 resolve to an existing `def`/`class` in `installer/`, `setup.py`, `tests/` or `scripts/`. Of the other 66:
  - Phase-21 artifacts (excluded): `request_refresh`, `await_publication`, `mark_pending`, `record_evidence`, `refuse_if_mutating`, `begin_mutation`/`end_mutation`, `MutationHolder`, `RefreshPublished`/`RefreshFinished`/`RefreshRequested`, `JobStatesRead`, `installed_or`, `uninstall_group`/`uninstall_label`/`uninstall_detail`, `_pnpm_missing_facts`, `_read_live_state`, `_remove_worker`, `_exit_after_removal`, `_render_published`, `_removable_state`, `settle`, `matrix_app`, `_family_app`, `first_line` (made public by 21-02), and others.
  - Textual, stdlib or pytest APIs (out of scope for the adapter; `DataTable.update_cell` verified at `.venv/.../textual/widgets/_data_table.py:871`).
  - Attribute references verified by direct read: `ToolBrowser` adapter `selectable` (`installer/tool_browser.py:77`) and `Policy.owned` (`installer/policy.py:158`).
  - No MISSING verdict remains.
- **Line references:** REUSE line references spot-checked and VERIFIED: `installer/policy.py:507,838,1043,1095`; `installer/pnpm_globals.py:556,573-574`. The reviewer's own citations were re-read for every HIGH (table above).
- **UNCHECKABLE (INFO):**
  - Python signatures and dataclass fields: the `intel` adapter does not analyze Python and `grep` cannot assert signatures, so these rest on manual reads only.
  - Runtime behaviour: `make validate`, `make test`, the pilots and the NO_COLOR container UAT were not executed (read-only review).

Cross-artifact fact-drift pass (advisory; contributes to neither count):
- Phase status (deterministic, `drift-guard phase-status --phase 21`): verdict `lag` (STATE.md "Ready to execute" vs ROADMAP "Not started"). Not a finding.
- Requirement IDs: ROADMAP lists UI-01, 02, 03, 05, 06, 07, 08. Every `requirements:` entry across the 21 plans is within that set, and each ID is covered (21-21 covers all seven). UI-04 is correctly absent (Phase 22). No contradiction.
- Success criteria vs `must_haves.truths`: the five ROADMAP criteria are restated across 21-06/13/14/17/19/21 without contradiction. One near-pair was examined: SC5's "a dangling pnpm global shim shows as broken" vs 21-05's MISSING note. It is not drift, because those are two different findings (see the 21-05 adjudication).
- Glossary (CONTEXT decisions vs plan usage): D-16 "same wave" vs the 21-11/21-12 split across waves 5/6. 21-11 carries an explicit reinterpretation (`21-11-PLAN.md:96`), so it is flagged for user confirmation, not as drift. No other contradiction found.
