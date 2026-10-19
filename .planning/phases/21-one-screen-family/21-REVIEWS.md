---
phase: 21
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-19T04:20:00Z
cycle: 2
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

## Cycle 2 (current) — reviewed at HEAD 46b6a76

Reviewer: opencode-plan-review (`opencode run --model router-env/my-plan-review`, the router lane, about 15 minutes, exit 0). No direct alternate was needed. There was a single reviewer, so the consensus gate is skipped. The reviewer was told four things: 21-CONTEXT.md, 21-SPEC.md and the approved 21-UI-SPEC.md are locked; the 21-REUSE.md notes are part of the plans they name; D-16 is read literally as "same plan"; and it should first check every cycle-1 HIGH and actionable item against the current plan text, then review the revised plans afresh. It read the plans and the supporting artifacts from disk, cited source `file:line` throughout (about 83 source citations) and gave every plan id its own section (plan coverage 21/21). It modified no file. The raw output is under `.review-diagnostics/20261019T040516Z-gsd-review-cycle2/` (gitignored).

## OpenCode Review (opencode-plan-review)

### Cycle-1 resolution table

| Plan | Cycle-1 concern | Status | Evidence |
|---|---|---|---|
| 21-06 | A failed `refresh` is followed by a clean-looking publication; skills-stage errors disappear | **RESOLVED** | `.planning/phases/21-one-screen-family/21-06-PLAN.md:138-139,156` requires the second publication to retain the first error and tests the final status after both stages. This addresses the actual exception mapping in `installer/ui_common.py:52-55` and the failing-refresh/succeeding-skills double in `tests/state_doubles.py:307-313,265-271`. |
| 21-14 | Failed rows cannot always remain selected after fresh proof disappears | **RESOLVED** | `.planning/phases/21-one-screen-family/21-14-PLAN.md:77,112-113,120` now makes retryability conditional on published removability and tests both retained and lost proof. That agrees with browser pruning at `installer/tool_browser.py:235-251` and deletion-time proof at `installer/uninstall.py:546-553`. A separate partial-delete feedback issue remains below. |
| 21-14 | `q` does nothing during removal under a modal | **RESOLVED** | `.planning/phases/21-one-screen-family/21-14-PLAN.md:80,158-164` explicitly preserves modal soft-quit behavior and tests unguarded `ctrl+c` waiting. This matches the existing distinction at `installer/wizard_app.py:3061-3070`; the previously unspecified behavior is now defined. |
| 21-15 | Daemon callback without policy ID leaves the mutation lock held forever | **RESOLVED** | `.planning/phases/21-one-screen-family/21-15-PLAN.md:158,172` tests the constructor shape and makes the completion post unconditional, with an optional ID and release first. This repairs the conditional post at `installer/wizard_app.py:2729-2733`. |
| 21-18 | A superseded job-state thread can repaint stale state | **PARTIAL** | `.planning/phases/21-one-screen-family/21-18-PLAN.md:76,107,113` correctly adds a generation for successive renders. It does not supersede reads when mutation-completion paths replace the answer; those writers remain at `installer/wizard_app.py:2024-2040,2107-2115`. Its late-delivery test also lacks deterministic confirmation that the cancelled thread posted. |
| 21-05 | Off-PATH MISSING note allegedly violates the dangling-shim BROKEN contract | **N/A (refuted in cycle 1)** | `.planning/phases/21-one-screen-family/21-05-PLAN.md:168-179` still addresses a tracked package whose command is absent. The opposite dangling-shim condition remains distinct at `installer/status.py:218-241` and becomes a broken fact at `installer/version_status.py:760`. No replan change overturns the refutation. |
| 21-09 | Fresh per-tool attribution allegedly hides refused preview paths | **N/A (refuted in cycle 1)** | `.planning/phases/21-one-screen-family/21-09-PLAN.md:68-71,108` retains attribution through both `removable` and `yourself`. Existing unproven artifacts reach `yourself` at `installer/uninstall.py:191-196`; drift invalidates the entire receipt proof at `installer/uninstall.py:96-98`. |
| 21-19 | Removing the old Doctor formatter allegedly drops incomplete groups | **N/A (refuted in cycle 1)** | `.planning/phases/21-one-screen-family/21-19-PLAN.md:78,120` renders published reasons. `installer/version_status.py:681-693,1632-1634,1715-1716` already computes and carries incomplete-group facts into that channel. |
| 21-20 | An exception after reinstall allegedly bypasses lock release | **N/A (refuted in cycle 1)** | `.planning/phases/21-one-screen-family/21-16-PLAN.md:82,161` requires a `finally:` completion post and release first. `.planning/phases/21-one-screen-family/21-20-PLAN.md:72-73,111` preserves that guarantee. The fresh invalidation concern below is not a renewed deadlock claim. |
| 21-02 | Assert that `build_plan` never emits `REMOVE` | **RESOLVED** | `.planning/phases/21-one-screen-family/21-02-PLAN.md:99,104,127` adds the direct boundary test across health, unpublished state, and reinstall requests. The current builder selects dispositions through `installer/session.py:626-711,738-805`; `RUNNABLE` remains separate at `installer/session.py:113-121`. |
| 21-10 | Test review arrival both before a pass starts and during a running pass | **RESOLVED** | `.planning/phases/21-one-screen-family/21-10-PLAN.md:142-146,149` explicitly tests both orders and pending-pass deferral. The retained token/error boundary is implemented today at `installer/execute_screen.py:559-584`. |
| 21-14 | `_failed_lines` is cleared on entry, losing retry guidance | **RESOLVED** | `.planning/phases/21-one-screen-family/21-14-PLAN.md:76,114,120` preserves reasons across navigation and publication and tests navigation followed by retry. Its new cleanup condition has a separate partial-deletion weakness below. |
| 21-16 | Define Doctor early-return refusals and their pass counts | **RESOLVED** | `.planning/phases/21-one-screen-family/21-16-PLAN.md:86-90,164-170,178` enumerates silent returns as zero passes and note-writing/lock refusals as one, corresponding to `installer/wizard_app.py:651-653,737-774`. |
| 21-17 | Define Requires/detail behavior when `missing_requirements()` fails | **RESOLVED** | `.planning/phases/21-one-screen-family/21-17-PLAN.md:89,164,170` replaces independent reads with one guarded map, blanks failed Requires cells, omits stale requirement detail, and refuses Space. Existing independent readers are at `installer/wizard_app.py:1732,1747,2055`. |
| 21-20 | Surface failed invalidation and defer the fix pass until guard confirmations finish | **RESOLVED** | `.planning/phases/21-one-screen-family/21-20-PLAN.md:72-74,104-105,111` defines a separate invalidation error and terminal guard-chain publication. The callback chain exists at `installer/wizard_app.py:690-714,730-735`. |
| 21-21 | Navigate during a held mutation and prove repaint without re-entry | **RESOLVED** | `.planning/phases/21-one-screen-family/21-21-PLAN.md:74,105,113` adds the held-removal/navigation/release case and asserts the same active screen updates without another key. It exercises the top-screen publication mechanism specified in `.planning/phases/21-one-screen-family/21-06-PLAN.md:101,156`. |
| 21-21 | UAT permits a wrapped refusal despite the one-row contract | **RESOLVED** | `.planning/phases/21-one-screen-family/21-21-PLAN.md:22,177-178` now requires one row, matching `.planning/phases/21-one-screen-family/21-UI-SPEC.md:264-273` and the automated backstop in `.planning/phases/21-one-screen-family/21-16-PLAN.md:171`. |
| 21-11/21-12 | Delete each fork in the same plan that makes it unreferenced | **PARTIAL** | Normal execution now performs replacement and deletion within 21-12 at `.planning/phases/21-one-screen-family/21-12-PLAN.md:152-158,203-205,258-260`. However, its binding rule at `:112` permits unfinished deletions to move into a separate `21-12b`, asserting that the same wave suffices. That contradicts the fixed same-plan reading. |

### 21-01

**Summary:** Establishes the neutral root, six installed views, and one lifecycle/navigation order.

**Strengths**
- The root sentinel prevents launch from taking the current-view early return; awaiting push before entry fixes the existing enter-before-mount ordering. The task and call-order pilots are explicit at `.planning/phases/21-one-screen-family/21-01-PLAN.md:80,113-124`, grounded in `installer/wizard_app.py:2759-2785`.
- Warning flush precedes entry, and the Uninstall standing status must respect an existing warning (`.planning/phases/21-one-screen-family/21-01-PLAN.md:81,167-175`). This addresses the replacing status write at `installer/wizard_app.py:2792-2796`.

**Concerns:** No additional substantive concern established.

**Suggestions:** Keep the six-view call-order and status pilots as the acceptance evidence; symbol-count gates alone do not prove lifecycle behavior.

**Risk Assessment: LOW.** The ordering change and its connected test-host migrations are explicitly covered.

### 21-02

**Summary:** Extends the shared outcome vocabulary without making removal an install-engine operation.

**Strengths**
- The revised task directly tests that `build_plan` never emits `REMOVE`, rather than relying solely on `RUNNABLE` membership (`.planning/phases/21-one-screen-family/21-02-PLAN.md:98-106`; `installer/session.py:113-121,738-805`).
- REUSE is correctly incorporated by widening the existing failure-detail branch instead of adding another renderer (`.planning/phases/21-one-screen-family/21-02-PLAN.md:108`; `installer/render.py:151-162`).

**Concerns:** No additional substantive concern established.

**Suggestions:** Preserve the distinction between removal vocabulary and executable install dispositions.

**Risk Assessment: LOW.** The new boundary assertion closes the cycle-1 omission.

### 21-03

**Summary:** Prunes unselectable selections on reload and filters acceptance again.

**Strengths**
- The in-place set operation preserves shared selection identity and foreign-tier IDs (`.planning/phases/21-one-screen-family/21-03-PLAN.md:96,123-125`; `installer/tool_browser.py:246-249`).
- Acceptance filtering reuses the existing `selected_ids()` boundary, and the later catalog pilot checks actual decided IDs (`.planning/phases/21-one-screen-family/21-03-PLAN.md:90-96`; `.planning/phases/21-one-screen-family/21-06-PLAN.md:200`; `installer/tool_browser.py:356-365`).

**Concerns:** No additional substantive concern established.

**Suggestions:** Keep pruning silent: the existing selection-change handler is not an appropriate publication notification.

**Risk Assessment: LOW.** The change is localized and its shared-set behavior is tested.

### 21-04

**Summary:** Makes policy prerequisites live and supplies OMZ’s missing live activity predicate.

**Strengths**
- The predicate closure fits the existing `Policy.missing_requirements()` seam (`.planning/phases/21-one-screen-family/21-04-PLAN.md:89-95`; `installer/policy.py:166-170,586-603`).
- Binding REUSE correctly deletes Linux’s unused parameter instead of widening it (`.planning/phases/21-one-screen-family/21-REUSE.md:11-20`; `installer/policy.py:1089-1095`). The original task’s contrary wording is therefore not an open design concern.
- The macOS test pins an existing live plist predicate, while OMZ gains the predicate it actually lacks (`.planning/phases/21-one-screen-family/21-04-PLAN.md:124-131`; `installer/policy.py:790-800,1014-1023`).

**Concerns:** No additional substantive concern after applying REUSE.

**Suggestions:** Execute REUSE’s caller migrations and replacement acceptance criteria, not the superseded Linux predicate test.

**Risk Assessment: LOW.** The effective plan reuses existing policy interfaces.

### 21-05

**Summary:** Adds precise pending suppression, session evidence, and the cached-inventory off-PATH fact.

**Strengths**
- Filtering pending IDs at the commit point prevents an already-running pass from restoring them (`.planning/phases/21-one-screen-family/21-05-PLAN.md:99-106`; `installer/version_status.py:1727-1760`).
- Evidence is snapshotted under the existing lock and fed through existing health inputs rather than introducing another health decision path (`.planning/phases/21-one-screen-family/21-05-PLAN.md:133-140`; `installer/version_status.py:1703-1720`).
- REUSE’s `audit_node_globals` call preserves the existing tracked-package/missing-command rule without spawning smoke checks (`.planning/phases/21-one-screen-family/21-REUSE.md:28-38`; `installer/pnpm_globals.py:566-580`).

**Concerns:** No additional substantive defect established. The off-PATH MISSING note must not be confused with the already-supported dangling-shim BROKEN condition.

**Suggestions:** Retain the deterministic in-pass pending/evidence tests.

**Risk Assessment: LOW.** The proposed additions follow the service’s lock and publication model.

### 21-06

**Summary:** Introduces the coalescing app refresh owner and removes per-tier refresh workers.

**Strengths**
- Running/pending flags on the event loop prevent overlapping refresh threads independently of Textual cancellation (`.planning/phases/21-one-screen-family/21-06-PLAN.md:97,156,197`; `installer/version_status.py:1582-1614`).
- The first-error rule now fixes both cycle-1 reporting failures, with final-status assertions after both stages (`.planning/phases/21-one-screen-family/21-06-PLAN.md:138-139,156`; `installer/ui_common.py:52-55`).

**Concerns**
- **HIGH — The modal-publication pilot cannot reach the entry it claims to test.** At `.planning/phases/21-one-screen-family/21-06-PLAN.md:198`, the test opens a modal over system, publishes without repainting, dismisses it, then calls `show_view("system")` and expects the new glyph. But `current_view` is still `"system"`, so the required no-op at `.planning/phases/21-one-screen-family/21-01-PLAN.md:124` returns without entry. The same early return exists at `installer/wizard_app.py:2763-2764`. With no further publication, the table remains painted from the old state. The prescribed pilot fails the plan’s own acceptance.

**Suggestions:** After dismissing the modal, actually leave and re-enter system. Keep the locked current-view no-op and top-screen-only publication rules unchanged.

**Risk Assessment: HIGH.** The central owner is coherent, but a mandatory acceptance pilot is internally inconsistent.

### 21-07

**Summary:** Removes the ownership-message fork and connects removal and refused updates to the owner.

**Strengths**
- The payload-free request follows the existing bubbling message pattern while preserving unmounted-screen tests (`.planning/phases/21-one-screen-family/21-07-PLAN.md:73,157-159`; `installer/catalog_tui.py:831-849`).
- The refusal cases correspond to real status-writing branches, rather than treating silent no-op paths as mutations (`.planning/phases/21-one-screen-family/21-07-PLAN.md:151-157`; `installer/catalog_tui.py:777-825`).

**Concerns:** No additional substantive concern. Environment-only completion is explicitly deferred here and supplied by 21-14, rather than accidentally omitted.

**Suggestions:** Keep the exactly-one-pass assertions when later moving lock checks earlier in the update action.

**Risk Assessment: LOW.** The transitional and final responsibilities are identified.

### 21-08

**Summary:** Adds pure group, label, and detail projections over published state.

**Strengths**
- The functions reuse the existing proof and owner vocabulary, including fixed unknown-owner text and BROKEN precedence (`.planning/phases/21-one-screen-family/21-08-PLAN.md:101-109,139-151`; `installer/ownership.py:1602-1641`).
- Locating the projections in `version_status.py` avoids importing the state module back through its existing uninstall dependency (`.planning/phases/21-one-screen-family/21-08-PLAN.md:68`; `installer/uninstall.py:16-24`).

**Concerns**
- **MEDIUM — REUSE introduces an undeclared same-wave shared writer.** REUSE requires 21-08 to edit `installer/catalog_tui.py` (`.planning/phases/21-one-screen-family/21-REUSE.md:72-76`), but its execution metadata lists only the state module and its tests (`.planning/phases/21-one-screen-family/21-08-PLAN.md:5-9`). Wave-2 plan 21-06 also edits the catalog (`.planning/phases/21-one-screen-family/21-06-PLAN.md:5-14,158-160`). The executor’s overlap detection examines `files_modified`, so it cannot detect this effective overlap (`.claude/gsd-core/workflows/execute-phase.md:527-559`). This is an integration/staging risk, not missing implementation guidance.

**Suggestions:** Include REUSE-expanded paths in execution metadata and serialize or explicitly coordinate the shared-file edits.

**Risk Assessment: MEDIUM.** Projection behavior is sound; execution ownership is incompletely represented.

### 21-09

**Summary:** Adds per-tool removal outcomes and isolates ordinary delete failures.

**Strengths**
- All deletion still goes through `remove_proven`, preserving fresh hashes, artifact-type authorization, and refusal reporting (`.planning/phases/21-one-screen-family/21-09-PLAN.md:108,143`; `installer/uninstall.py:532-557`).
- Both current return paths retain the new outcomes, including the tweak-sweep replacement result (`.planning/phases/21-one-screen-family/21-09-PLAN.md:108`; `installer/app.py:706,722`).
- Failure tests require continuation to other tools and environment levers (`.planning/phases/21-one-screen-family/21-09-PLAN.md:136-143`), unlike the current single removal call before those levers (`installer/app.py:681-690`).

**Concerns:** No new substantive defect established. The refuted attribution HIGH should not be reinstated.

**Suggestions:** Preserve the existing re-proof tests and use a separate real partial-delete fixture for 21-14.

**Risk Assessment: LOW.** Destructive authority remains unchanged.

### 21-10

**Summary:** Replaces ExecuteScreen’s private refresh worker with publication waiting.

**Strengths**
- The existing settlement message and cancellation token remain the execution boundary (`.planning/phases/21-one-screen-family/21-10-PLAN.md:107-109`; `installer/execute_screen.py:559-584`).
- Both arrival orders and pending-pass deferral are now explicit task behavior (`.planning/phases/21-one-screen-family/21-10-PLAN.md:142-146`).
- Escaping exceptions still produce settlement, retaining the current worker’s fail-closed guarantee (`.planning/phases/21-one-screen-family/21-10-PLAN.md:71,107`; `installer/execute_screen.py:542-557`).

**Concerns:** No additional substantive defect established.

**Suggestions:** Give the pending-pass test independently controlled completion points so it demonstrably observes “not served after pass one.”

**Risk Assessment: LOW.** The revised waiter contract addresses cycle 1.

### 21-11

**Summary:** Lands Uninstall rendering prerequisites without retiring the row source prematurely.

**Strengths**
- The re-cut keeps classified rows live until 21-12, so this plan does not strand the classifier (`.planning/phases/21-one-screen-family/21-11-PLAN.md:84,129-134`; `installer/wizard_app.py:995-1006`).
- Rich truncation and an 80×20 backstop address the destructive screen’s fixed-width constraint (`.planning/phases/21-one-screen-family/21-11-PLAN.md:89,122-123`).
- Proof-test migrations keep real planted-tree removal plans (`.planning/phases/21-one-screen-family/21-11-PLAN.md:167-178`; `installer/uninstall.py:136-196`).

**Concerns**
- **MEDIUM — The sixth column is not carried into environment-row builders.** Task 1 adds Health to `_tool_entry` and the adapter (`.planning/phases/21-one-screen-family/21-11-PLAN.md:130-132`), but the three environment builders still emit five positional cells (`installer/wizard_app.py:1064-1073,1081-1090,1122-1129`). `ToolBrowser` inserts those cells unchanged (`installer/tool_browser.py:196-207`). Consequently `env` lands under Health, `shell config` under Cat, and removal text under Installed via.

**Suggestions:** Add a blank Health cell to all three environment-row builders and include an environment row in the alignment pilot.

**Risk Assessment: MEDIUM.** The re-cut is sound, but the column migration is incomplete.

### 21-12

**Summary:** Switches Uninstall to state projections and deletes the old seams and classifier.

**Strengths**
- Normal Task 1–3 execution combines the replacement with its newly possible deletions (`.planning/phases/21-one-screen-family/21-12-PLAN.md:152-158,203-205,258-260`).
- The unpublished-state pilot prevents both unproven selection and a false empty-machine claim (`.planning/phases/21-one-screen-family/21-12-PLAN.md:137,154-157`; `installer/version_status.py:1008-1018`).

**Concerns**
1. **HIGH — Visible environment rows remain stale after publication.** The plan explicitly reserves environment reads for `enter_view`; `state_refreshed` only renders cached values (`.planning/phases/21-one-screen-family/21-12-PLAN.md:102,157`). The inherited `_render` only rebuilds entries and reloads the browser (`.planning/phases/21-one-screen-family/21-11-PLAN.md:87,134`). Those entries depend on cached `_ban_names`, `_has_path_block`, and `_tweak_ids` (`installer/wizard_app.py:973-1002`). Start a held Policies job toggle, enter Uninstall before completion, then release it: the ensuing pass repaints Uninstall without refreshing those caches. The environment row remains absent or obsolete until re-entry, violating `.planning/REQUIREMENTS.md:63` and `.planning/ROADMAP.md:260`.

2. **HIGH — The split fallback reintroduces the rejected D-16 interpretation.** `.planning/phases/21-one-screen-family/21-12-PLAN.md:112` permits remaining tasks to become `21-12b` “in the same wave.” Task 2 removes the classifier’s last production caller, while Task 3 deletes it (`:205,258`). Moving Task 3 into another plan violates the fixed same-plan rule regardless of push timing.

3. **HIGH — Task 3’s absence gate fails on a known comment deferred to 21-21.** The mandatory gate rejects `_managed_hint` anywhere under `installer/` (`.planning/phases/21-one-screen-family/21-12-PLAN.md:271-272`). That exact name remains at `installer/registry.toml:2510`; its rewrite is explicitly assigned to the later plan at `.planning/phases/21-one-screen-family/21-21-PLAN.md:76,139,159`. The current action ordering cannot satisfy 21-12’s gate.

**Suggestions:** Re-read environment predicates through the guarded publication lifecycle without clearing status; test held-toggle → visible-Uninstall environment changes. Resume unfinished work within 21-12 rather than creating a deletion plan. Move the known registry-comment rewrite into Task 3 without weakening the gate.

**Risk Assessment: HIGH.** False visible state, a locked execution-contract violation, and a guaranteed gate failure remain.

### 21-13

**Summary:** Moves removal off-loop, marks affected tools pending, and introduces the shared lock.

**Strengths**
- Lock acquisition precedes worker launch, and completion is posted from `finally` with release first (`.planning/phases/21-one-screen-family/21-13-PLAN.md:89-90,129-132`), replacing the synchronous removal path at `installer/wizard_app.py:1456-1486`.
- Removal start immediately repaints Uninstall from service pending state, rather than creating another renderer input (`.planning/phases/21-one-screen-family/21-13-PLAN.md:120,132`; `.planning/phases/21-one-screen-family/21-05-PLAN.md:106`).

**Concerns**
- **MEDIUM — A required pilot globally settles workers while deliberately holding removal open.** `.planning/phases/21-one-screen-family/21-13-PLAN.md:166` requires `settle` while the remover is still held. Binding REUSE defines that helper as waiting until no app worker is pending/running (`.planning/phases/21-one-screen-family/21-REUSE.md:49-50`); its reused polling loop eventually raises (`tests/test_catalog_tui.py:2832-2837`). It cannot successfully observe refresh completion while preserving the held removal.

**Suggestions:** Wait specifically for refresh completion/pass count while asserting the removal remains held, then release before global `settle`.

**Risk Assessment: MEDIUM.** The worker design is sound; the concurrency pilot’s wait is incompatible with its scenario.

### 21-14

**Summary:** Adds conditional retryability, durable row feedback, service invalidation, and quit waiting.

**Strengths**
- Proof-conditional retry and navigation-preserved reasons now appear in executable tests and actions (`.planning/phases/21-one-screen-family/21-14-PLAN.md:112-120`).
- Modal quit behavior is explicit, with separate soft/hard cases (`.planning/phases/21-one-screen-family/21-14-PLAN.md:158-164`; `installer/wizard_app.py:3061-3070`).
- Environment-only removals now request publication without unnecessary tool invalidation (`.planning/phases/21-one-screen-family/21-14-PLAN.md:111,120`).

**Concerns**
- **MEDIUM — “Nothing to do” is not proof that every artifact is gone.** The plan deletes `_failed_lines` when publication puts a tool in that group, explaining that it is gone (`.planning/phases/21-one-screen-family/21-14-PLAN.md:76,120`). The existing partial-delete fixture removes the command link, fails deleting the opt directory, and leaves that directory in `yourself` (`tests/test_uninstall.py:1598-1639`). Presence does not count an opt directory without a live command (`installer/status.py:163-176`), so the resulting MISSING state enters “nothing to do” and loses the deletion error despite remaining files. The new tests cover retained proof and a present unknown-owner refusal, not this real partial-delete shape (`.planning/phases/21-one-screen-family/21-14-PLAN.md:112-114`).

**Suggestions:** Add the real link-deleted/directory-delete-failed fixture and retain its explanation while published removal evidence identifies leftovers.

**Risk Assessment: MEDIUM.** Cycle-1 fixes are real, but partial deletion can still lose durable failure guidance.

### 21-15

**Summary:** Folds update, job-toggle, and daemon-default guards into the shared lock.

**Strengths**
- The optional-ID daemon completion is now correctly paired with acquisition (`.planning/phases/21-one-screen-family/21-15-PLAN.md:81,158,172`; `installer/wizard_app.py:2729-2742`).
- Update release reuses its existing guaranteed completion message (`.planning/phases/21-one-screen-family/21-15-PLAN.md:121-123`; `installer/catalog_tui.py:832-849`).

**Concerns**
- **HIGH — The specified update-check position violates the locked refusal contract.** `.planning/phases/21-one-screen-family/21-15-PLAN.md:121` puts `refuse_if_mutating` after informational refusals. During removal, `u` on a pending removed tool therefore returns “state is still being checked”; current, BROKEN, and unknown-owner tools also return before the lock (`installer/catalog_tui.py:787-821`). The runner is safely refused, but the holder template required by `.planning/phases/21-one-screen-family/21-UI-SPEC.md:126,132` is not shown. The pilot uses an unrelated outdated tool and misses these branches (`.planning/phases/21-one-screen-family/21-15-PLAN.md:112`).

**Suggestions:** Check the lock before status-writing state refusals. Test pending, current, and BROKEN rows during removal, asserting the exact holder template and one pass.

**Risk Assessment: HIGH.** This is not a destructive-operation bypass, but it deterministically breaks the locked interaction contract.

### 21-16

**Summary:** Completes remaining lock checks, holder vocabulary, and Doctor refusal accounting.

**Strengths**
- Doctor’s six early-return cases now have explicit outcomes and pass counts (`.planning/phases/21-one-screen-family/21-16-PLAN.md:164-170,178`; `installer/wizard_app.py:737-774`).
- The reinstall worker gains guaranteed completion and release on unexpected exceptions (`.planning/phases/21-one-screen-family/21-16-PLAN.md:82,160-161`; `installer/wizard_app.py:786-795`).
- The one-row width backstop directly checks the longest fixed refusal (`.planning/phases/21-one-screen-family/21-16-PLAN.md:171`; `installer/ui_common.py:71`).

**Concerns**
- **LOW — Held early-return cases need targeted waits.** The table measures behavior while reinstall/audit workers remain held (`.planning/phases/21-one-screen-family/21-16-PLAN.md:164,167-168`). App-wide `settle`, defined in `.planning/phases/21-one-screen-family/21-REUSE.md:49-50`, cannot complete then. Unlike 21-13, this wording does not explicitly require that helper, so this is an execution clarification.

**Suggestions:** Specify `wait_until` on pass/status conditions for held cases, releasing the holder before global settling. Correct update refusal precedence in 21-15.

**Risk Assessment: LOW locally.** The cycle-1 accounting gap is closed; complete refusal behavior depends on 21-15.

### 21-17

**Summary:** Makes Policies render live state and guarded prerequisites through one lifecycle hook.

**Strengths**
- `installed_or` avoids `is_present`’s blocking probe fallback on the render path (`.planning/phases/21-one-screen-family/21-17-PLAN.md:87,120,127`; `installer/version_status.py:1020-1025`).
- The requirements map closes the actual independent cell/detail/toggle reads and tests failure recovery (`.planning/phases/21-one-screen-family/21-17-PLAN.md:89,164,170`; `installer/wizard_app.py:1732,1747,2055`).

**Concerns**
- **MEDIUM — Deleting unreadable state entries breaks the schedule action’s direct lookup.** The plan removes `active_state[id]` after failed reads and updates Space handling (`.planning/phases/21-one-screen-family/21-17-PLAN.md:84-86,170`). However, `action_pick_time` still directly indexes `self.active_state[policy.id]` (`installer/wizard_app.py:2128-2139`). Pressing `t` on a schedulable policy after the newly supported failed read raises `KeyError` before the callback-level lock check.

**Suggestions:** Define unknown-state handling for schedule opening and test `t` after a failed live read; do not silently treat unknown as proven OFF.

**Risk Assessment: MEDIUM.** The failure model is improved, but a connected caller retains the old dictionary invariant.

### 21-18

**Summary:** Adds DRIFT and generation-guarded asynchronous job-state reads.

**Strengths**
- DRIFT requires explicit footprint ownership and inactivity, matching Linux’s separate predicates (`.planning/phases/21-one-screen-family/21-18-PLAN.md:73-74,102-106`; `installer/policy.py:1375-1384`).
- Capturing generation as a worker argument correctly protects successive-render ordering (`.planning/phases/21-one-screen-family/21-18-PLAN.md:76,113`; `installer/wizard_app.py:828-835`).

**Concerns**
- **HIGH — Mutation completions do not supersede in-flight job reads.** Generation advances only when `state_refreshed` starts another worker (`.planning/phases/21-one-screen-family/21-18-PLAN.md:75-76`). Yet `_finish_toggle` and retained `refresh_daemon_state` independently replace the answer (`installer/wizard_app.py:2024-2040,2107-2115`; `.planning/phases/21-one-screen-family/21-17-PLAN.md:88`). A pre-mutation probe can return its old answer even after cache invalidation—the cache prevents storage, not return (`installer/systemd_daemon.py:501-520`). Its message still has the current screen generation and can overwrite the completion’s newer state. Toggle publication may later repair this; daemon completion guarantees no new app pass (`.planning/phases/21-one-screen-family/21-15-PLAN.md:172`), so false OFF/DRIFT can persist until another render.
- **MEDIUM — The reverse-completion test can assert before late delivery.** `.planning/phases/21-one-screen-family/21-18-PLAN.md:107` releases the cancelled thread and then uses global `settle`. REUSE waits on Textual pending/running states, not completion of an already-cancelled underlying thread (`.planning/phases/21-one-screen-family/21-REUSE.md:49-50`). The plan itself recognizes that cancellation does not stop the thread (`.planning/phases/21-one-screen-family/21-18-PLAN.md:76`), so the final assertion may precede its `finally` post.

**Suggestions:** Supersede read generations at mutation-completion boundaries too. Test a held pre-mutation read finishing after daemon/toggle completion, and explicitly observe late-message handling before asserting unchanged state.

**Risk Assessment: HIGH.** Render-to-render ordering is fixed, but another permitted ordering still reports false policy state.

### 21-19

**Summary:** Routes Doctor findings through published reasons and adds guarded failed-read rendering.

**Strengths**
- Incomplete groups retain their existing pass-owned channel; no second evidence mapper is needed (`.planning/phases/21-one-screen-family/21-19-PLAN.md:78,120`; `installer/version_status.py:681-693,1632-1634`).
- Recording every node tool clears resolved evidence, while changed-only requests avoid an audit/publication loop (`.planning/phases/21-one-screen-family/21-19-PLAN.md:80,108-112`; `.planning/phases/21-one-screen-family/21-05-PLAN.md:133-140`).
- Failed-read tests reject earlier data and check recovery (`.planning/phases/21-one-screen-family/21-19-PLAN.md:150-156`; `installer/wizard_app.py:502,546`).

**Concerns**
- **MEDIUM — The new reason-rendering boundary lacks explicit sanitization and hostile-text coverage.** The action inserts `{tool_id}: {reason}` without requiring `sanitize_log_line` (`.planning/phases/21-one-screen-family/21-19-PLAN.md:78-80,120`), although the locked contract requires it (`.planning/phases/21-one-screen-family/21-UI-SPEC.md:284`). Existing `_refresh_body` uses `Text.append`, which is not the shared sanitizer (`installer/wizard_app.py:539-546,599-605`). Smoke failure text can contain raw captured stderr: `installer/run.py:101-104`; `_condensed` only collapses whitespace at `installer/executors.py:327-329`; `_unhealthy` retains the resulting string at `installer/pnpm_globals.py:546-553`.
- **LOW — An existing ordering test still asserts the formatter being removed.** `tests/test_wizard_app.py:4341-4357` expects `node_globals_guidance` inside `screen.guidance`, contrary to the deliberate removal in `.planning/phases/21-one-screen-family/21-19-PLAN.md:120`. The suite catches it, but the migration is not identified.

**Suggestions:** Sanitize new reason text at insertion and test literal markup plus absence of escape bytes. Rewrite the ordering test for the new body location.

**Risk Assessment: MEDIUM.** The state/evidence mechanism is coherent; rendering-boundary enforcement remains incomplete.

### 21-20

**Summary:** Removes Doctor’s hidden key, reports invalidation errors, and publishes after complete fix/guard workflows.

**Strengths**
- Separate reinstall and invalidation outcomes correctly handle an unexpected exception from invalidation without misreporting reinstall success (`.planning/phases/21-one-screen-family/21-20-PLAN.md:72,104`; `installer/ui_common.py:52-55`).
- Guard-chain publication points match actual terminal callbacks (`.planning/phases/21-one-screen-family/21-20-PLAN.md:74,105,111`; `installer/wizard_app.py:667-674,690-714,730-735`).
- First-run success rerenders through the existing lifecycle after the error return, not through another bespoke renderer (`.planning/phases/21-one-screen-family/21-20-PLAN.md:149`; `installer/wizard_app.py:2874-2882`).

**Concerns**
- **HIGH — Invalidation is not guaranteed when reinstall itself raises unexpectedly.** The sequence places invalidation after the reinstall’s `run_live` returns (`.planning/phases/21-one-screen-family/21-20-PLAN.md:71-72,111`). But `run_live` does not map `RuntimeError` (`installer/ui_common.py:52-55`), and 21-16 expressly tests that exception from the reinstall seam (`.planning/phases/21-one-screen-family/21-16-PLAN.md:161`). In that path the inherited `finally` posts completion and unlocks, but execution skips invalidation. The requested pass may then reuse fresh pre-mutation manager inventory (`installer/version_status.py:1501-1507`), despite the plan’s success-or-failure invalidation promise.
- **MEDIUM — Raising-fake invalidation tests do not cover the actual cache-write failure.** `.planning/phases/21-one-screen-family/21-20-PLAN.md:104` proves error transport, but real invalidation first bumps the epoch and then clears persistent manager data (`installer/version_status.py:1128-1140`). If that write fails, the next pass can reload the still-fresh disk snapshot (`installer/version_status.py:1501-1507`). The plan does not test or define whether that inventory is forced fresh or treated as unverified.

**Suggestions:** Attempt invalidation in guaranteed post-reinstall cleanup, including unexpected reinstall exceptions, while preserving separate outcomes and unconditional completion. Add a real-service cache-write-failure case.

**Risk Assessment: HIGH.** Lock release remains protected; the remaining issue is publishing pre-mutation inventory after partial mutation.

### 21-21

**Summary:** Adds the final publication matrix, held-navigation proof, fork guard, and documentation/UAT.

**Strengths**
- The held-navigation case now proves repaint without re-entry on the same screen object (`.planning/phases/21-one-screen-family/21-21-PLAN.md:74,105`), exercising the direct visible-screen publication mechanism.
- Helper placement now consistently follows REUSE (`.planning/phases/21-one-screen-family/21-21-PLAN.md:75,113,122-123`; `.planning/phases/21-one-screen-family/21-REUSE.md:93-100`).
- The guard scans tracked and untracked non-ignored files, including the real registry comment (`.planning/phases/21-one-screen-family/21-21-PLAN.md:76,157-159`; `installer/registry.toml:2504-2511`).

**Concerns**
- **MEDIUM — The final matrix misses the environment-publication defect in 21-12.** Uninstall’s observable is only a tool-state witness, and the held-navigation target is a catalog tier (`.planning/phases/21-one-screen-family/21-21-PLAN.md:71-74,103-105`). These cases can pass while `_ban_names`, `_has_path_block`, or `_tweak_ids` remains stale on visible Uninstall, because those values control separate environment rows (`installer/wizard_app.py:973-1002`). The matrix therefore does not fully establish roadmap success criterion 1 for that projection.
- **LOW — UAT requires observing refusals but does not explain how to produce a held lock.** `.planning/phases/21-one-screen-family/21-21-PLAN.md:177-178` specifies visits and drift setup, but no safe refusal-triggering scenario. Automated width coverage already exists in 21-16, so this is a reproducibility gap rather than missing width coverage.

**Suggestions:** Add a held policy-toggle → visible-Uninstall case asserting environment-row changes without re-entry. Move the registry-comment rewrite earlier as required by 21-12; let the final guard confirm it stays absent.

**Risk Assessment: MEDIUM.** Cycle-1 coverage fixes are present, but the matrix still misses a real projection-specific failure.

### Cross-plan priorities

**Verdict: revise before execution.** Framework: **GSD · implementation plans**. Coverage: **21/21 plans**, reviewed against HEAD `46b6a76`, locked context/specification/UI contract, binding REUSE instructions, and current source.

1. **Repair 21-12 before dispatch.**
   - Refresh environment predicates when visible Uninstall receives publication.
   - Remove the separate-plan deletion fallback.
   - Perform the known registry-comment rewrite before its mandatory absence gate.
   - Add the environment witness to 21-21.

2. **Close remaining ordering and invalidation defects.**
   - Supersede job-state reads when daemon/toggle completion supplies newer state.
   - Guarantee invalidation after an attempted reinstall, including unexpected exceptions.
   - Exercise real cache-write failure rather than only replacing `invalidate` with a raising fake.

3. **Make required pilots executable and deterministic.**
   - Actually leave/re-enter in 21-06’s modal test.
   - Use targeted waits while mutation workers remain held.
   - Observe the cancelled job thread’s late message before asserting rejection.

4. **Finish connected UI migrations.**
   - Add blank Health cells to environment rows.
   - Handle missing policy state in the schedule action.
   - Move update lock refusal ahead of informational refusals.
   - Preserve partial-delete explanations while artifacts remain.
   - Sanitize Doctor’s newly inserted reason text.

5. **Represent effective file ownership.** Expand execution metadata for REUSE edits so same-wave overlap detection sees the catalog shared writer.

The plans substantially cover all five roadmap success criteria, but **SC1 remains incomplete** because visible environment rows can stay stale, and **SC5 remains at risk** from job-read completion ordering. The lifecycle/status and removal architecture are otherwise materially stronger than cycle 1. Destructive operations continue to use the existing deletion-time proof authority; this review found no new path bypassing it.

### Not checked

No files were modified, created, or deleted. Tests, plan execution, package-manager operations, and terminal/container UAT were not run; runtime timing, coverage floors, and visual claims remain unverified. The pre-existing `.planning/config.json` modification was left untouched.

---

## Source-grounding adjudication of the reviewer's cycle-2 HIGHs

Each HIGH was traced against the current tree (HEAD `46b6a76`) and the plan text. None is refuted on its premise, so all seven stand. One reviewer ran, so each counts. Two notes on severity are recorded beside their verdicts.

| Plan | Reviewer HIGH | Verdict | Evidence |
|---|---|---|---|
| 21-06 | `test_publish_under_a_modal_waits_for_the_next_entry` dismisses the modal and then calls `show_view("system")` while `current_view` is still `"system"`, so no entry runs and the new glyph never paints | **CONFIRMED** | `21-06-PLAN.md:198` is the test. `21-01-PLAN.md:124` makes the new `show_view` body "return when `name == self.current_view`", the same early return as today (`installer/wizard_app.py:2763-2764`). A modal leaves `current_view` alone, so the pilot cannot pass as written. `21-06-PLAN.md:204` says to fix any failure in `installer/wizard_app.py`, which would push the executor to break the D-01 no-op. The fix is to leave and re-enter, or to navigate from another view. |
| 21-12 | A publish repaints the visible Uninstall only from cached environment values, so the ban, PATH-block and tweak rows stay stale until the next entry | **CONFIRMED** | `21-12-PLAN.md:102`: only `enter_view` re-reads the three environment predicates, and `state_refreshed` "only calls `_render()`". `_build_entries` builds the environment rows from the cached `_ban_names`, `_has_path_block` and `_tweak_ids` (`installer/wizard_app.py:973-1002`, `:1064-1075`). There is a more direct trigger than the reviewer's held-toggle case. An environment-only removal on the visible Uninstall ends with `request_refresh()` (`21-14-PLAN.md:27,75`). The publish then re-renders with the pre-removal `_ban_names`, so the removed ban row is still listed. Neither 21-13 nor 21-14 re-reads the environment after a removal (grep for `_env_state`/`_ban_names` in 21-13/21-14 finds nothing). That breaks SC1, "immediately when it is visible", for Uninstall removal × Uninstall and Policies job toggle × Uninstall. The daemon is a tweak id (`installer/wizard_app.py:1458-1468`), and job toggles run on a worker (`:2068-2079`), so navigating during one is possible. |
| 21-12 | The stop-and-split rule lets unfinished deletions move to a separate `21-12b` "in the same wave", which reopens the rejected reading of D-16 | **CONFIRMED (contingency only)** | `21-12-PLAN.md:112`. The orchestrator's fixed reading (RUN-LEDGER, Phase 21 cycle 1 row; prompt) is "the same plan as the change that leaves it unreferenced". Task 2 removes the classifier's last caller (`:205`) and Task 3 deletes it (`:258`). A split after Task 2 would put the deletion in a different plan. The normal path is compliant. The fix is to make the fallback a continuation of 21-12 itself (same plan id and SUMMARY), not a new plan. |
| 21-12 | Task 3's absence gate greps `_managed_hint` over `installer/`, but `installer/registry.toml:2510` still names it, and that comment's rewrite is scheduled for 21-21 | **CONFIRMED** | Gate: `21-12-PLAN.md:271`, `grep -rnE "…_managed_hint…" installer/ setup.py tests/ .claude/architecture.md`. Hit: `installer/registry.toml:2510` `# changes what \`_managed_hint\` is telling the user…`. `installer/registry.toml` is not in 21-12's `files_modified` (`21-12-PLAN.md:7-23`). It is rewritten only in `21-21-PLAN.md:139,143,159,184`. The gate fails deterministically. The fix is to move the registry-comment rewrite into 21-12 Task 3. |
| 21-15 | `u` checks the lock after the informational refusals, so during a removal `u` on a pending, current, BROKEN or unknown-owner tool writes its informational line, not the lock template | **CONFIRMED** (severity judgment noted) | `21-15-PLAN.md:121`: "after the informational refusals and right before `self._updates.begin(tool_id)`". The informational returns are at `installer/catalog_tui.py:787-821`. A tool being removed is CHECKING (D-09 `mark_pending`), so it hits `cannot update …: its state is still being checked` first. The locked UI-SPEC lists `u` among the keys refused with the lock template during a removal (`21-UI-SPEC.md:126,132`). Nothing starts on these paths, and 21-07 already makes them request one pass, so this is a copy-contract break, not a safety hole. It counts as HIGH because it contradicts a locked artifact. The fix: check the lock first, or record a UI-SPEC-consistent rationale for why a key that would not mutate is not a "mutating key". |
| 21-18 | The generation only advances when `state_refreshed` starts a read. A daemon-default or toggle completion that writes a newer answer does not supersede an in-flight read, so the older read can overwrite it | **CONFIRMED** (partial resolution of the cycle-1 HIGH) | `21-18-PLAN.md:75-76`: the bump happens only per worker start. `refresh_daemon_state` (`installer/wizard_app.py:2008-2040`, kept by `21-17-PLAN.md:88`) writes `active_state` directly, and the daemon-default completion requests no app pass (`21-15-PLAN.md:81`; no `request_refresh` in 21-15). A read started on entry before the apply can return its pre-apply answer. `StateCache.read` returns an unstored probe value after an invalidate (`installer/systemd_daemon.py:501-520`). It carries the current generation, so `on_job_states_read` accepts it and paints the stale OFF, which stays until the next render. On the toggle path, the stale paint lasts only until the toggle's own publish starts a newer read (`21-18-PLAN.md:77`), but it can still flash. |
| 21-20 | An unmapped exception from the reinstall skips the invalidate, so the follow-up pass can reuse fresh pre-mutation manager inventory | **CONFIRMED (crash path only)** | `21-20-PLAN.md:71-72`: the invalidate runs after the reinstall's `run_live` returns. `run_live` maps only `OSError`, `CommandError` and `ShellrcRefusal` (`installer/ui_common.py:52-53`). A `RuntimeError` from the reinstall (pinned by `21-16-PLAN.md:161`) escapes before the invalidate. The `finally:` post still releases the lock, and the pass still runs, but the pass loads the not-yet-stale manager snapshot (`installer/version_status.py:1501-1507`). That contradicts the plan's own truth, "invalidates … success or failure". Mapped failures (the common case) do invalidate. The fix is to call the invalidate from the worker's `finally:`, before the post. |

### Disposition of the reviewer's cycle-2 MEDIUM/LOW findings

Each premise was checked against source. All are confirmed, and none is already covered by a plan task, a ledger entry or a REUSE instruction, so all count as actionable:

- **21-08 (M):** REUSE 08-1 edits `installer/catalog_tui.py` (`21-REUSE.md:72-76`), but `21-08-PLAN.md:7-9` lists only `version_status.py` and its tests. Wave-2 sibling 21-06 also edits `catalog_tui.py` (`21-06-PLAN.md:9`), and the overlap is undeclared.
- **21-11 (M):** the Health column is added to tool rows only. The three environment builders still emit five cells (`installer/wizard_app.py:1064-1075` and its siblings), so their cells shift one column left. 21-11 never mentions the environment rows.
- **21-13 (M):** `test_a_refused_removal_still_requests_one_pass` calls `settle` "the remover still held" (`21-13-PLAN.md:166`). REUSE `settle` waits for no RUNNING worker (`21-REUSE.md:49-50`), and `wait_until` raises after 400 tries (`tests/test_catalog_tui.py:2830-2836`).
- **21-14 (M):** `_failed_lines` is dropped when a publish puts the tool in `nothing to do` (`21-14-PLAN.md:76`). In a real partial delete (`tests/test_uninstall.py:1598-1639`), the link is gone and the opt dir delete failed. The tool reads MISSING, its failure reason is dropped, and files remain.
- **21-16 (L):** in the held early-return cases (`21-16-PLAN.md:164-168`), passes are measured "after the key settles", which hangs while the holder is held. These cases need targeted `wait_until` conditions.
- **21-17 (M):** `action_pick_time` indexes `self.active_state[policy.id]` (`installer/wizard_app.py:2132`). 21-17 deletes that entry after a failed read (`21-17-PLAN.md:84`), so `t` raises `KeyError`. Today only the macOS daemon has `set_schedule` (`installer/policy.py:1021`).
- **21-18 (M):** the reverse-order test releases the cancelled read and then `settle`s (`21-18-PLAN.md:107`). A cancelled Textual worker is no longer RUNNING, so `settle` can return before the late `finally:` post. The test must observe the late message before it asserts.
- **21-19 (M):** the new `{tool_id}: {reason}` lines (`21-19-PLAN.md:78`) do not require `sanitize_log_line`, which the locked UI-SPEC demands (`21-UI-SPEC.md:284`). Smoke reasons carry captured stderr (`installer/pnpm_globals.py:546-553`).
- **21-19 (L):** `tests/test_wizard_app.py:4341-4357` asserts `node_globals_guidance(...)` inside `screen.guidance`. 21-19 removes that formatter from the TUI, and the plan does not name this test migration.
- **21-20 (M):** a real cache-write failure inside `invalidate` bumps the epoch, but the persisted manager snapshot stays fresh (`installer/version_status.py:1120-1140`, `:1501-1507`). The next pass can reuse it. 21-20 reports the error but neither defines nor explicitly defers that behavior.
- **21-21 (M):** the matrix's Uninstall witness is tool state only, and the held-navigation target is a tier (`21-21-PLAN.md:71-74,103-105`). It cannot catch the 21-12 environment-row staleness above.
- **21-21 (L):** the UAT asks that "every lock refusal fits one row" (`21-21-PLAN.md:177-178`) but gives no safe way to trigger a held lock in the container.

Cycle-1 items, as the reviewer re-checked them against the current plan text (resolution table above): every cycle-1 HIGH and actionable item is **RESOLVED** except two. 21-18's generation is PARTIAL (now the 21-18 HIGH above). The 21-11/21-12 D-16 cut is PARTIAL (now the 21-12 split-fallback HIGH above). The four HIGHs refuted in cycle 1 (21-05, 21-09, 21-19, 21-20 lock) stay refuted, and the replan did not change them. Spot checks agree with the reviewer: 21-02 `:99,104` (the `build_plan` boundary test), 21-10 `:142-146` (both arrival orders), 21-14 `:76,114` (`_failed_lines` survives entry), 21-16 `:164-170` (pinned pass counts), 21-17 `:89` (`_missing` map), 21-20 `:72-74` (invalidate error plus guard-chain pass), and 21-21 `:22,74,105` (the held-navigation case and one-row refusal).

## Consensus Summary

There was one reviewer (opencode-plan-review, source-grounded with about 83 source `file:line` citations and 21/21 plan coverage), so no cross-reviewer consensus is possible. Reviewer verdict: **revise before execution**. After source grounding, cycle 1 is closed except for two partials. Cycle 2 has **7 HIGH** concerns (21-06, 21-12 ×3, 21-15, 21-18, 21-20) and **12 actionable MEDIUM/LOW** concerns. None is refuted.

### Agreed Strengths
- (single reviewer) Every cycle-1 HIGH and actionable concern except two is carried into executable task text and tests. Destructive removal still goes through `remove_proven`'s deletion-time re-proof (`installer/uninstall.py:532-557`). No new path bypasses it.

### Agreed Concerns
- n/a (one reviewer). The open items are in the adjudication above. 21-12 holds three of the seven HIGHs and is the priority for the replan.

### Divergent Views
- None (one reviewer). Source grounding confirmed all seven HIGHs. It found a more direct trigger for the 21-12 environment-staleness HIGH than the reviewer gave. It flags the 21-15 HIGH as a copy-contract break, not a safety hole, and the 21-20 HIGH as a crash path only.

## Verification coverage

Source-grounding pass (`plan_review.source_grounding = true`, configured authority `grep`). The effective authority from `drift-guard authority --raw` is `intel`. Severities come from `drift-guard severity --authority intel`: VERIFIED → none, MISSING → needs-acknowledgement, AMBIGUOUS → MEDIUM, UNCHECKABLE → INFO. Nothing set `hardBlock`.
- **File paths:** 52 distinct repo paths were extracted from the 21 plans.
  - VERIFIED: the 50 that exist (including `installer/registry.toml`, `scripts/detect-container-runtime.sh` and `.claude/architecture.md`).
  - Excluded as new artifacts of this phase: `tests/test_screen_family.py` (21-01) and `tests/screen_family.py` (21-06).
- **Symbols:** 755 distinct backticked identifiers and call forms were extracted from the plans.
  - VERIFIED: 429 resolve to an existing `def`/`class`/assignment in `installer/`, `setup.py`, `tests/` or `scripts/`.
  - The remaining 326 are lowercase words, constants, test names, framework or stdlib APIs, or Phase-21 artifacts. Phase-21 artifacts were excluded after checking that a plan declares them. Examples: `state_refreshed`/`clear_transient` (21-01), `mark_pending`/`record_evidence`/`_pending_ids`/`_evidence`/`_pnpm_missing_facts` (21-05), `request_refresh`/`RefreshPublished`/`RefreshFinished`/`RefreshRequested`/`wait_until`/`settle` (21-06), `await_publication` (21-10), `_render`/`_painted`/`required_by` (21-11/12), `HeldRemover`/`MutationHolder`/`begin_mutation`/`end_mutation`/`refuse_if_mutating`/`mutation_in_flight`/`RemovalFinished` (21-13), `_failed_lines`/`_exit_after_removal`/`_quitting` (21-14), `MutationLock` (21-16), `installed_or`/`_missing`/`_read_live_state` (21-04/17), `JobStatesRead`/`_job_state_generation`/`_read_job_states_worker` (21-18), `invalidate_error` (21-20), `matrix_app`/`_PHASE_21_REQUIRED` (21-21).
  - `receipt_notes` is an existing local (`installer/version_status.py:1688`).
  - No MISSING verdict remains.
- **Reviewer citations:** every source citation behind the seven HIGHs and the twelve actionable items was re-read. Among them: `installer/wizard_app.py:973-1002,1064-1075,2008-2040,2068-2079,2124-2139,2755-2800`, `installer/catalog_tui.py:777-830`, `installer/ui_common.py:40-53`, `installer/systemd_daemon.py:495-520`, `installer/version_status.py:1120-1140,1498-1510`, `installer/registry.toml:2510`, `installer/policy.py:1005-1024,1385-1400`, `tests/test_catalog_tui.py:2830-2836` and `tests/test_wizard_app.py:4341-4357`.
- **UNCHECKABLE (INFO):**
  - Python signatures and dataclass fields: the `intel` adapter does not analyze Python, and `grep` cannot assert signatures, so these rest on manual reads.
  - Textual runtime semantics (the state of a cancelled thread worker, padding of a short `add_row`): these were not executed and rest on the documented behavior.
  - `make validate`, `make test`, the pilots and the NO_COLOR container UAT were not run (read-only review).

Cross-artifact fact-drift pass (advisory; contributes to neither count):
- **Phase status** (deterministic, `drift-guard phase-status --phase 21`): verdict `lag` (STATE.md "Ready to execute" vs ROADMAP "Not started", authority STATE.md). Not a finding.
- **Requirement IDs:** ROADMAP lists UI-01, 02, 03, 05, 06, 07 and 08. Every plan `requirements:` entry is within that set. UI-04 is correctly absent (Phase 22). No contradiction.
- **Success criteria vs `must_haves.truths`:** no plan truth contradicts the five ROADMAP criteria. The SC1 gap for the visible Uninstall environment rows is an omission (a plan-checker Dimension 7b matter), not a contradiction, so it is reported as the 21-12 HIGH and the 21-21 actionable item, not as drift.
- **Glossary (CONTEXT decisions vs plan usage):** D-16 literally says "same wave" (`21-CONTEXT.md:102`), and the orchestrator reads it as "same plan". 21-12's `21-12b` fallback (`21-12-PLAN.md:112`) satisfies the literal wording but not the reading. It is reported once, as the 21-12 HIGH. No other contradiction was found.

---

## Cycle 1 (history) — reviewed at HEAD ccfca9f

Reviewer: opencode-plan-review (`opencode run --model router-env/my-plan-review`, the router lane; no direct alternate was needed). Single reviewer, so the consensus gate is skipped. The reviewer was told that 21-CONTEXT.md, 21-SPEC.md and the approved 21-UI-SPEC.md are locked, and that the 21-REUSE.md orchestrator notes are part of the plans they name. It read all 21 plans and the supporting artifacts from disk, cited source `file:line` throughout (36 source citations), and gave every plan id its own section (plan coverage 21/21).

### OpenCode Review (opencode-plan-review) — cycle 1


**Verdict: revise before execution.** The plans have a coherent implementation path and substantial test coverage, but several written contracts can produce false removal results, stale or missing state, or a mutation lock that never releases. I reviewed all 21 plans against the locked context, specification, UI contract, REUSE instructions, and current source. Source citations describe the **current** tree; the planned code has not landed.

#### 21-01

**Summary:** Establishes a neutral root and one clear → pop → push → enter path for all six views.

- **Strengths:** Starting `current_view` at a root sentinel avoids the current base-view early return; pushing before entry lets first-entry rendering use mounted widgets (`.planning/phases/21-one-screen-family/21-01-PLAN.md:79-81,113-128`; `installer/wizard_app.py:2630,2759-2785`).
- **Concerns:** **LOW** — The call-order and status pilots are more meaningful than the symbol-count gates (`21-01-PLAN.md:113-151`). Keep them as the acceptance evidence.
- **Suggestions:** Test warning-flush precedence on a second view as well as Uninstall; the current flush replaces a status rather than merging one (`installer/wizard_app.py:2792-2796`).
- **Risk Assessment:** **LOW–MEDIUM**; lifecycle ordering is addressed, with a narrow status-precedence risk.

#### 21-02

**Summary:** Adds removal outcomes to the shared vocabulary without making removal an install-engine action.

- **Strengths:** Keeping `REMOVE` outside `RUNNABLE` protects the existing install dispatch boundary (`21-02-PLAN.md:94-105`; `installer/session.py:112-121,738-805`).
- **Concerns:** **LOW** — Adding a disposition also affects generic review iteration; the plan does not directly assert that `build_plan` never emits `REMOVE` (`21-02-PLAN.md:65-67`; `installer/session.py:197-200`).
- **Suggestions:** Add that boundary assertion. Apply REUSE’s extension of the existing failure-detail branch, not a duplicate branch (`21-REUSE.md:63-68`; `installer/render.py:147-162`).
- **Risk Assessment:** **LOW**; REUSE supplies the simpler rendering implementation.

#### 21-03

**Summary:** Prunes selections on reload and filters selectable IDs again at acceptance.

- **Strengths:** In-place pruning preserves the shared selection set, while the acceptance filter covers the period before another reload (`21-03-PLAN.md:89-98`; `installer/tool_browser.py:235-251,356-365`).
- **Concerns:** **LOW** — Browser acceptance alone is not an execute-boundary proof: the catalog handler builds its decision from `_staged`, not the acceptance event’s IDs (`installer/catalog_tui.py:896-907`).
- **Suggestions:** Keep the downstream catalog-input pilot in 21-06 and assert the rejected ID is absent there.
- **Risk Assessment:** **LOW**; the downstream test closes the remaining boundary.

#### 21-04

**Summary:** Makes policy prerequisites and OMZ activity live.

- **Strengths:** `Policy.missing_requirements()` already supplies the live-read seam; the planned OMZ `is_active` predicate addresses a construction-time snapshot (`21-04-PLAN.md:85-96,122-133`; `installer/policy.py:166-170,790-800`).
- **Concerns:** **MEDIUM** — The plan’s Task 2 still describes widening and testing `linux_daemon_policy(installed_tools=...)`, whereas binding REUSE instructions delete that unused parameter and update callers outside the plan’s file list (`21-04-PLAN.md:113-145`; `21-REUSE.md:9-20`; `installer/policy.py:1036-1044,1089-1095`; `setup.py:599-605`). REUSE resolves the design, but the executor’s file scope and original count gates must follow it.
- **Suggestions:** Treat REUSE’s caller migrations, replacement test floor, and revised predicate count as Task 2’s acceptance criteria.
- **Risk Assessment:** **MEDIUM**; a literal execution of the unamended task would break callers.

#### 21-05

**Summary:** Adds precise pending-tool suppression, Doctor evidence, and a cached-inventory pnpm finding.

- **Strengths:** Filtering pending IDs at the service’s commit point prevents an older pass from restoring a removed tool’s mark (`21-05-PLAN.md:99-106`; `installer/version_status.py:1727-1760`). REUSE correctly redirects missing-command detection to the existing audit rule (`21-REUSE.md:22-39`; `installer/pnpm_globals.py:556-580`).
- **Concerns:** **HIGH** — The planned off-PATH finding is carried as a note on an **absent** tool and the test explicitly expects `Health.MISSING` (`21-05-PLAN.md:73,168-179`). The locked specification and UI contract require a dangling pnpm shim to show `!` on its tier (`21-SPEC.md:90-98`; `21-UI-SPEC.md:165-169`); `tool_health` returns `MISSING` for an absent tool regardless of broken facts (`installer/version_status.py:218-251`). Resolve this conflict before implementing 21-19’s tier/Doctor parity test.
- **Suggestions:** Specify the evidence and health classification for the dangling-shim fixture, then test its actual tier glyph, not only its reason. Adapt the frozen service to pending semantics before using it in screen pilots (`tests/state_doubles.py:244-264`).
- **Risk Assessment:** **HIGH**; as written, a named phase acceptance criterion can fail.

#### 21-06

**Summary:** Replaces per-tier refresh workers with one coalescing app owner.

- **Strengths:** The event-loop running/pending flags avoid relying on Textual worker cancellation to prevent overlapping threads (`21-06-PLAN.md:97-106`; `installer/version_status.py:1582-1614`). The modal publication behavior follows the locked top-screen rule (`21-CONTEXT.md:51-58`).
- **Concerns:** **HIGH** — The worker posts a failed refresh result, then posts a clean-looking publication after `refresh_skills`; the clean handler clears the error it just displayed (`21-06-PLAN.md:101,152`). `run_live` returns errors instead of raising them (`installer/ui_common.py:42-55`). A failed initial pass can therefore leave `…` rows without the promised retry instruction. **MEDIUM** — The proposed second publication also discards a `refresh_skills` error (`21-06-PLAN.md:152`).
- **Suggestions:** Carry failure through the complete worker or do not emit a clean publication after failure. Assert final status after both worker stages. Apply REUSE’s test-helper migration, including the many deleted-flag waits (`21-REUSE.md:41-56`).
- **Risk Assessment:** **HIGH**; failure reporting can contradict the displayed state.

#### 21-07

**Summary:** Connects Uninstall and refused `u` paths to the app refresh owner and removes the ownership message fork.

- **Strengths:** The message seam accommodates bare-screen tests, and the existing `u` action has identifiable refusal branches (`21-07-PLAN.md:71-76,143-167`; `installer/catalog_tui.py:787-825`).
- **Concerns:** **MEDIUM** — This plan’s Uninstall request remains transitional: the environment-only removal path lacks the tool-count-gated invalidation it uses (`21-07-PLAN.md:75,103-115`; `installer/wizard_app.py:1493-1505`). Plan 21-14 must close that gap; a pass-count test here alone is not UI-01 proof.
- **Suggestions:** Label environment-only removal as deferred in this plan’s acceptance and assert the final path in 21-14.
- **Risk Assessment:** **MEDIUM**; acceptable only with the stated downstream dependency.

#### 21-08

**Summary:** Defines pure Uninstall group, label, and detail projections over `ToolState`.

- **Strengths:** The group rules keep unproven and unknown-owner tools out of removable rows (`21-08-PLAN.md:103-109`; `installer/version_status.py:705-728`; `installer/ownership.py:1602-1641`).
- **Concerns:** **MEDIUM** — REUSE moves the existing health-detail table from `catalog_tui.py` to `version_status.py` and changes its readers, but that cross-file work is absent from the plan’s listed files (`21-REUSE.md:70-76`; `21-08-PLAN.md:7-9`). Without it, the shared-copy acceptance check cannot pass.
- **Suggestions:** Include the catalog import and both reader migrations in Task 1’s explicit scope.
- **Risk Assessment:** **MEDIUM**; the intended implementation is sound, but the amended file scope is incomplete.

#### 21-09

**Summary:** Converts removal into per-tool re-proof, deletion, and outcome reporting.

- **Strengths:** `remove_proven` remains the deletion authority and re-verifies proof at delete time (`21-09-PLAN.md:68-73`; `installer/uninstall.py:532-557`).
- **Concerns:** **HIGH** — The plan attributes previewed paths using a *new* `plan_removal([tool])`, then treats paths absent from that new plan as unmatched warnings (`21-09-PLAN.md:68-71,106-108`). If one of a tool’s previewed artifacts disappears while another remains removable, that tool can be reported `removed` despite a refused previewed path. The current remover explicitly reports every previewed path not removed (`installer/uninstall.py:546-553`).
- **Suggestions:** Require every previewed path attributable to a selected tool to be removed before reporting that tool as `removed`; add a partial-drift fixture, not only an all-refused fixture.
- **Risk Assessment:** **HIGH**; destructive-operation success could be overstated.

#### 21-10

**Summary:** Joins ExecuteScreen’s state waiter to app publication rather than starting a private pass.

- **Strengths:** Retaining its token and `StateSettled` handling preserves the existing fail-closed review boundary (`21-10-PLAN.md:69-73,107-109`; `installer/execute_screen.py:559-584`).
- **Concerns:** **MEDIUM** — `await_publication` may have to start a pass when none is running, but the held test assumes a launch pass is already in progress (`21-10-PLAN.md:24,98-100`). The current execute test host does not inject `version_refresh` into `UnifiedApp` (`tests/test_execute_screen.py:320-337`).
- **Suggestions:** Test both event orders deterministically: review arrives before a pass starts and review joins a pass already running.
- **Risk Assessment:** **MEDIUM**; the waiter’s ordering contract needs a stronger pilot.

#### 21-11

**Summary:** Replaces Uninstall’s rows input with published-state rows and adds the Health column.

- **Strengths:** Pre-pass emptiness is distinguished from “nothing installed”; `ToolBrowser.reload` can retain a keyed cursor, and the width backstop covers the destructive screen (`21-11-PLAN.md:126-134`; `installer/tool_browser.py:186-225`).
- **Concerns:** **MEDIUM** — The explicit painted-row rule retains old paths and selectability when state becomes unknown (`21-11-PLAN.md:32,90-94`). Deletion-time re-proof prevents unauthorized deletion (`installer/uninstall.py:532-553`), but a row can still offer a preview based on prior rather than current proof. This is a user-facing truth trade-off, not a proof bypass.
- **Suggestions:** Test ordinary invalidation separately from removal-pending state. Make the preview say that proof is being rechecked if a painted selectable row remains available. Apply REUSE’s `_VIA_*` deletion and Rich truncation instructions (`21-REUSE.md:78-89`).
- **Risk Assessment:** **MEDIUM**; removal safety survives, but the selectable UI can be misleading.

#### 21-12

**Summary:** Deletes the classifier and owner-hint fork after the new Uninstall projection lands.

- **Strengths:** It retains the actual removal planner and dependency utilities rather than deleting proof logic with presentation logic (`21-12-PLAN.md:96-110`; `installer/uninstall.py:136-196,351-356`).
- **Concerns:** **MEDIUM** — The replacement is wave 5 and the fork deletion wave 6 (`21-11-PLAN.md:5-6`; `21-12-PLAN.md:5-6`), although locked D-16 says each fork is deleted in the **same wave** as its replacement (`21-CONTEXT.md:100-103`). Calling adjacent waves one “logical” step in 21-11 does not meet that wording (`21-11-PLAN.md:96`).
- **Suggestions:** Put the serialized replacement and deletion in one wave, or obtain an explicit amendment to D-16.
- **Risk Assessment:** **MEDIUM**; the final tree can be correct, but the execution sequence violates a locked decision.

#### 21-13

**Summary:** Runs removal on a worker, marks only its tools pending, and introduces the app mutation lock.

- **Strengths:** Acquiring the lock before launch and posting completion from `finally` gives the worker a release path even on failure (`21-13-PLAN.md:25-30,129-135`).
- **Concerns:** **MEDIUM** — Task 1 introduces `refuse_if_mutating` without the required refresh request; Task 2 adds that contract in a separate supposedly green commit (`21-13-PLAN.md:27-28,129-130,158-175`). **MEDIUM** — `mark_pending` needs an immediate visible render at removal start: merely changing service state does not itself invoke the app’s publish renderer (`21-CONTEXT.md:74-78`; `21-06-PLAN.md:152`).
- **Suggestions:** Make refusal-plus-request atomic and assert `…` on the already-visible tier before the removal worker finishes.
- **Risk Assessment:** **MEDIUM**; both issues are local but affect the promised in-flight behavior.

#### 21-14

**Summary:** Adds failed-row feedback, unconditional follow-up refresh, retry, and quit-wait behavior.

- **Strengths:** It covers environment-only removal and invalidation failure (`21-14-PLAN.md:101-106`). Its worker wait accounts for Textual’s failure/cancellation exceptions (`21-14-PLAN.md:146-154`).
- **Concerns:** **HIGH** — A partial delete may leave no newly proven removable path. After refresh, the row becomes unselectable and reload prunes it, making the promised “failed row stays selected; Enter retries” impossible (`21-14-PLAN.md:22-25,102-112`; `tests/test_uninstall.py:1598-1639`; `installer/tool_browser.py:235-251`). **HIGH** — Keeping `_navigable()` ahead of the soft-quit wait means `q` under a modal still does nothing (`21-14-PLAN.md:75,154`; `installer/wizard_app.py:3061-3070`), contrary to the unqualified removal quit copy in `21-UI-SPEC.md:119-130`. **MEDIUM** — Clearing `_failed_lines` on entry loses the row’s error before retry (`21-14-PLAN.md:72-74,112`).
- **Suggestions:** Make retry conditional on fresh removability, retain failure guidance otherwise, and test partial deletion. Define modal soft-quit behavior explicitly and preserve the error across navigation until resolved.
- **Risk Assessment:** **HIGH**; retry and quit promises are not reliably achievable as written.

#### 21-15

**Summary:** Folds update, job-toggle, and default-daemon guards into the one lock.

- **Strengths:** Fixed holder nouns and completion-handler release match the UI contract; the existing update worker already posts completion from `finally` (`21-15-PLAN.md:26-31`; `installer/catalog_tui.py:831-849`).
- **Concerns:** **HIGH** — The plan locks whenever a daemon callback is wired and unlocks on `DaemonDefaultApplied` (`21-15-PLAN.md:80,169`), but the current daemon worker posts that message only when `daemon_default_policy_id` is non-`None`; the constructor accepts callback and ID independently (`installer/wizard_app.py:2507-2509,2729-2733`). A callback without an ID can permanently block mutations.
- **Suggestions:** Enforce paired arguments at construction or make completion/release unconditional, and test the callback-without-ID case. Use REUSE’s shared `settle` migration rather than replacing old flag loops with new loops (`21-REUSE.md:58-61`).
- **Risk Assessment:** **HIGH**; a valid constructor shape can leave the app locked.

#### 21-16

**Summary:** Guards remaining mutating keys and completes the shared lock-holder vocabulary.

- **Strengths:** The key matrix, fixed refusal strings, and crash pilot cover the main safety boundary (`21-16-PLAN.md:111-114,153-159`).
- **Concerns:** **MEDIUM** — “Every refused mutation ends with one pass” needs a precise definition across Doctor’s existing early returns (`21-16-PLAN.md:25,112`; `installer/wizard_app.py:651-653,737-774`). **MEDIUM** — The install holder begins on `InstallRunStarted`, after catalog acceptance has already pushed ExecuteScreen (`21-16-PLAN.md:82-83`; `installer/wizard_app.py:2884-2888,2969-2971`).
- **Suggestions:** Enumerate which early returns are refusal events and assert each pass count. Add a held hand-off pilot proving a second mutation cannot start between acceptance and install-run lock acquisition.
- **Risk Assessment:** **MEDIUM**; the remaining issue is timing and contract coverage.

#### 21-17

**Summary:** Renders Policies activity and prerequisites on entry and publication, blanking failed live reads.

- **Strengths:** The `installed_or` seam avoids a blocking presence probe on the render path, and the failed-read test rejects a stale ON/OFF cell (`21-17-PLAN.md:83-86,113-119,159-167`; `installer/policy.py:166-170`).
- **Concerns:** **MEDIUM** — A failed state read blanks the State cell, but the existing detail builder independently calls `missing_requirements()` (`installer/wizard_app.py:1746-1748,1847-1861`). The plan does not pin what Requires and detail display when *their* live reads fail (`21-17-PLAN.md:159-167`).
- **Suggestions:** Cover failed prerequisite/detail reads as well as `is_active`. Do not raise OMZ staleness as an omission here: 21-04 already supplies its live predicate (`21-04-PLAN.md:122-133`).
- **Risk Assessment:** **MEDIUM**; partial-row failure handling needs definition.

#### 21-18

**Summary:** Adds DRIFT, reads systemd-backed state off-loop, and republishes after toggles.

- **Strengths:** DRIFT requires both owned and inactive; the worker pilot checks the thread used, not merely the final cell (`21-18-PLAN.md:71-75,99-105`).
- **Concerns:** **HIGH** — `exclusive=True` cancels a Textual worker but does not stop a thread already performing a probe. `JobStatesRead` carries no generation, so an older result may arrive after a newer render and repaint stale ON/OFF/DRIFT (`21-18-PLAN.md:74,110`). Doctor already uses a generation to reject this exact class of late audit result (`installer/wizard_app.py:481-494,828-835`).
- **Suggestions:** Carry an entry/read generation and discard superseded job-state messages; test reversed completion order.
- **Risk Assessment:** **HIGH**; the live screen can show an older answer as current.

#### 21-19

**Summary:** Routes Doctor’s pnpm findings through `ToolState.reasons` and keeps console formatting.

- **Strengths:** Changed-only evidence prevents a full pass on every Doctor entry, and the existing audit generation protects against stale audit completion (`21-19-PLAN.md:80,108-112`; `installer/wizard_app.py:828-835`).
- **Concerns:** **HIGH** — Removing `node_globals_guidance` from TUI rendering while recording only smoke failures and split-group notes drops the existing **incomplete-group** finding (`21-19-PLAN.md:78-80,120`). `NodeGlobalsReport` explicitly distinguishes incomplete from split groups (`installer/pnpm_globals.py:159-178`), and the old formatter handles that condition (`installer/guidance.py:382-400`). Locked D-13 calls for incomplete global findings in the shared reasons channel (`21-CONTEXT.md:92-95`; `21-SPEC.md:90-97`).
- **Suggestions:** Map incomplete groups into per-tool evidence and test a previously supported partial-install fixture before removing the old TUI renderer.
- **Risk Assessment:** **HIGH**; a named diagnostic would disappear.

#### 21-20

**Summary:** Removes Doctor’s hidden `a`, republishes fixes, and rerenders after the first-run link pick.

- **Strengths:** It retains the existing consented `r` package set and uses the planned completion handler (`21-20-PLAN.md:62-65`; `installer/wizard_app.py:786-795`).
- **Concerns:** **HIGH** — Invalidation is moved inside the reinstall worker after mutation, but the plan does not define a guaranteed completion post or visible invalidation failure (`21-20-PLAN.md:62,98`). `run_live` catches named operational errors, not arbitrary exceptions (`installer/ui_common.py:42-55`); an exception after a successful reinstall could bypass the lock-release message established in 21-16. **MEDIUM** — Doctor `enter` can continue into guard-file confirmations after its first fix (`installer/wizard_app.py:651-674`), so a pass requested only after the initial fix need not reflect the final mutation.
- **Suggestions:** Post completion in `finally`, report invalidation failure, and test it after a successful fake reinstall. Define publication after confirmed guard edits.
- **Risk Assessment:** **HIGH**; the exceptional path threatens both truth and lock release.

#### 21-21

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

### Source-grounding adjudication of the reviewer's HIGHs

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

#### Disposition of the reviewer's MEDIUM/LOW findings

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

### Consensus Summary

Single reviewer (opencode-plan-review, source-grounded: `file:line` citations throughout), so no cross-reviewer consensus is possible. Reviewer verdict: revise before execution. After source grounding, 5 HIGHs stand (21-06, 21-14 ×2, 21-15, 21-18) and 4 are refuted (21-05, 21-09, 21-19, 21-20).

#### Agreed Strengths
- (single reviewer) The wave chain is serialized and the forks are deleted beside their replacements. Re-proof at deletion stays the one removal authority (`installer/uninstall.py:532-557`). The 42-case matrix uses real key paths.

#### Agreed Concerns
- n/a (one reviewer). Unresolved items are listed in the adjudication above.

#### Divergent Views
- None (one reviewer). Source grounding overturned four of the reviewer's nine HIGHs; see the table.

### Verification coverage

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
