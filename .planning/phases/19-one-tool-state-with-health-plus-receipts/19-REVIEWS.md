---
phase: 19
cycle: 2
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-16T08:46:47Z
plans_reviewed: [19-01-PLAN.md, 19-02-PLAN.md, 19-03-PLAN.md, 19-04-PLAN.md, 19-05-PLAN.md, 19-06-PLAN.md, 19-07-PLAN.md, 19-08-PLAN.md, 19-09-PLAN.md, 19-10-PLAN.md, 19-11-PLAN.md, 19-12-PLAN.md, 19-13-PLAN.md, 19-14-PLAN.md, 19-15-PLAN.md, 19-16-PLAN.md, 19-17-PLAN.md, 19-18-PLAN.md, 19-19-PLAN.md, 19-20-PLAN.md, 19-21-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 19 (convergence cycle 2)

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

> Cycle 2 replaces the cycle-1 review (`git show db26ba9:.planning/phases/19-one-tool-state-with-health-plus-receipts/19-REVIEWS.md`). The cycle-1 findings are verified per id in the reviewer's "Cycle-1 Findings Verification" table below.

## OpenCode Review (opencode-plan-review)

# Phase 19 — Convergence Cycle 2 Review

**Document type:** GSD implementation plans · source-grounded, read-only review  
**Coverage:** All 21 current on-disk plans, the cycle-1 review, locked phase contracts, and relevant source seams.

`P/` below means `.planning/phases/19-one-tool-state-with-health-plus-receipts/`. **RESOLVED means the implementation prescription is corrected—not that the planned code has been implemented or tested.**

## Cycle-1 Findings Verification

| ID | Plan | Verdict | Evidence |
|---|---|---|---|
| H1 | 19-01, 19-14 | **RESOLVED** | `P/19-01-PLAN.md:131,226` separates `_write_unlocked` from locked public operations and gives the hash memo its own lock. `P/19-14-PLAN.md:145,157` explicitly uses the unlocked writer and adds a timed completion test. No nested non-reentrant acquisition is prescribed. |
| H2 | 19-02 | **RESOLVED** | `P/19-02-PLAN.md:210,217` requires `which=None`, resolved inside the function. This preserves the dynamic module lookup currently used at `installer/status.py:45,91`, including existing monkeypatch isolation. |
| H3 | 19-05 | **RESOLVED** | `P/19-05-PLAN.md:103-104,115` moves verified Volta-shim handling before the actual early return at `installer/ownership.py:618-632`, with overlapping-directory shim and non-shim controls. |
| H4 | 19-07 | **RESOLVED** | `P/19-07-PLAN.md:157-162,174-175` ties marketplace removal to emitted preceding uninstall steps for every dependent entry. A missing project working directory now keeps the marketplace. |
| H5 | 19-08 | **RESOLVED** | `P/19-08-PLAN.md:122,134-135` uses current `resolve_methods` availability and reserves `unavailable_reason` for wording. This correctly distinguishes current gating (`installer/resolve.py:66-84`) from potential support that assumes brew (`:131-138,195`). |
| H6 | 19-10 | **RESOLVED** | `P/19-10-PLAN.md:118,127,157` authorizes `(path, kind)` pairs, with planning and removal tests. This prevents a receipt from authorizing recursive removal where the formula permits only a file; actual deletion branches on filesystem type at `installer/uninstall.py:420-425`. |
| H7 | 19-10 | **RESOLVED** | `P/19-10-PLAN.md:119,127` checks every receipt artifact for drift before intersecting authorized pairs, matching the whole-receipt health check at `P/19-14-PLAN.md:116`. |
| H8 | 19-10 | **RESOLVED** | `P/19-10-PLAN.md:193,200-205` adds `_UninstallEntry.tool`, populates it from `ToolRow`, and skips environment rows. This addresses the real entry shape at `installer/wizard_app.py:875-882` and conversion at `:1003-1059`. |
| H9 | 19-14 | **PARTIALLY RESOLVED** | `P/19-14-PLAN.md:150,159` binds the digest comparison to the artifact passed to `adopt`. However, `:157` shares record construction with a builder that fingerprints paths under `P/19-09-PLAN.md:131`. It must explicitly reuse the validated artifact rather than acquire another fingerprint. |
| H10 | 19-16 | **RESOLVED for Phase 19** | `P/19-16-PLAN.md:152-153,162` emits an empty-argv step whose contract is the declaring node executor. That matches grouped/pinned installation, allowances and smoke at `installer/executors.py:475-507,547-548`. Actual step dispatch remains Phase 20. |
| H11 | 19-17 | **RESOLVED** | `P/19-17-PLAN.md:142,150` wraps first, retains two rendered lines, and tests word boundaries, newlines and unbroken text. Installed Rich implements newline splitting and word wrapping at `.venv/lib/python3.12/site-packages/rich/text.py:1229-1249`. |
| H12 | 19-17 | **RESOLVED** | `P/19-17-PLAN.md:143,150` selects `Text` versus `Text.from_markup` from the adapter flag and preserves section handling. This retains the existing contract at `installer/tool_browser.py:337-348`, including Uninstall’s `detail_is_markup=False` at `installer/wizard_app.py:1152`. |
| M1 | 19-01 | **RESOLVED** | `P/19-01-PLAN.md:171,183` requires type-specific file/link proof fields and explicitly rejects boolean schema versions and integer fields. A hashless file cannot enter the stat shortcut. |
| M2 | 19-02 | **RESOLVED** | `P/19-02-PLAN.md:121-122,134` validates the final name in both artifact calculation and installation, before writes. This covers explicit overrides currently returned unchanged by `installer/download.py:185`. |
| M3 | 19-07 | **RESOLVED** | `P/19-07-PLAN.md:115,123,174,189` closes scope to `user/project/local` before putting it after `-s`; invalid scopes invalidate the listing. |
| M4 | 19-07 | **RESOLVED** | `P/19-07-PLAN.md:114,123,161` consistently makes any malformed entry unknown rather than skipping it into fabricated absence. The plan also requires adapting the existing boolean matcher contract at `installer/skill_lifecycle.py:385-388`. |
| M5 | 19-08 | **RESOLVED for within-pass consistency** | `P/19-08-PLAN.md:213,225,244` captures a pass-local platform and threads it through helpers, replacing shared reads currently at `installer/version_status.py:619,624,676,708,721,732`. |
| M6 | 19-08 | **RESOLVED** | `P/19-08-PLAN.md:211-212,226` tests and rejects fresh snapshots whose brew evidence contradicts the pass platform. This fixes the unconditional freshness return at `installer/version_status.py:613-615` while preserving failure backoff. |
| M7 | 19-09 | **RESOLVED as warning policy; regression remains** | `P/19-09-PLAN.md:124,132,168,206` explicitly deletes old receipts on rewrite failure and reports deletion failure truthfully. But archive-layout fallback contradicts the new promise that deletion makes the tool unproven; see NEW N3. |
| M8 | 19-11 | **RESOLVED** | `P/19-11-PLAN.md:164,174,189` bounds the actual read to `cap + 1`, tests a file larger than its reported stat, and rejects excess. |
| M9 | 19-12 | **RESOLVED** | `P/19-12-PLAN.md:110-111,119-121` excludes installer shims from both declared and implicit filesystem fallbacks, reaching the independent acceptance path at `installer/status.py:98-107`. Both sentinel types and real-file controls are covered. |
| M10 | 19-14 | **RESOLVED** | `P/19-14-PLAN.md:149,159` adds asset and expected digest to negative memoization, with a changed-digest test. New release evidence therefore rechecks an unchanged file. |
| M11 | 19-16 | **PARTIALLY RESOLVED** | Exception and unreadable-pnpm notes are explicit at `P/19-16-PLAN.md:117,123,154,162,197,205`. Ordinary skill-probe failures return unknown/None without raising (`installer/skill_lifecycle.py:306-315,385-388`), so those paths still bypass the notes. |
| M12 | 19-18 | **RESOLVED** | `P/19-18-PLAN.md:157-158,168,182` defines one evidence-only private resolver, with fresh acquisition outside it and batched acquisition retained in refresh. The one-native-query regression test protects the existing shared evidence boundary at `installer/version_status.py:698-714`. |
| M13 | 19-19 | **RESOLVED for non-vacuous removal** | `P/19-19-PLAN.md:100-101,112,115` requires binary and receipt preconditions immediately before uninstall, then checks absence afterward. Placement matches the actual rerun/uninstall boundary at `scripts/container-e2e-verify.sh:433-456`. The grep check is only a format sanity check, not complete receipt validation. |
| M14 | 19-21 | **RESOLVED** | `P/19-21-PLAN.md:105-107,118` requires VERSION plus a `gsd-*` command/skill, and tests unrelated content. The integration fixture is aligned at `P/19-16-PLAN.md:191`. |
| M15 | 19-21 | **RESOLVED in prescribed algorithm** | `P/19-21-PLAN.md:103-104,116-117` explicitly caps queue admissions and entries, rejects symlinked roots, and avoids following child symlinks. The queue test should observe admission/peak queue, not merely `scandir` calls. |
| Cycle-1 LOW: default-shell exception | 19-15 | **EXPLICITLY RETAINED — acceptable** | `P/19-15-PLAN.md:72,148` narrowly retains render-time default-shell evidence. The UI contract expressly permits moving this existing note into the health block (`P/19-UI-SPEC.md:219`). This is an acknowledged exception, not another stored presence map. |
| Cycle-1 LOW: stale `resolve_status` range | 19-12 | **NOT RESOLVED — non-blocking** | `P/19-12-PLAN.md:75` still cites the old range; the real declaration is `installer/version_status.py:298`. The symbol is correct, so this does not change implementation behavior. |
| Cycle-1 advisory: D-12 body versus ledger | Context | **RESOLVED by explicit precedence** | The supplied current context annotates the `--bin` decision as superseded by L-19-01. Plans correctly use `uv tool dir`. |
| Cycle-1 advisory: historical prerequisite/line references | Context | **EXPLICITLY RETAINED — acceptable** | Research identifies the landed Phase 17/18 primitives and current seams; L-19-11 identifies historical references as drifted. Executors should use symbols/current source rather than those historical line numbers. |

## 19-01

**Summary:** A strong persistence foundation. H1 and M1 now have precise implementations and discriminating tests.

**Strengths**
- One unlocked inner writer removes the adoption deadlock (`P/19-01-PLAN.md:131`).
- Type-specific proof validation protects the stat shortcut (`:183,226`).
- Receipt and bin-directory sandboxes land before consumers.

**Concerns**
- **MEDIUM — NEW N4: the receipt size cap still bounds stat, not reading.** `P/19-01-PLAN.md:181-182` checks `lstat().st_size` and then reads bytes without a bounded-read requirement. A growing or replaced file can exceed the advertised 64 KiB cap—the same mechanism corrected for hook configs in 19-11.

**Suggestions**
- Require `read(65537)` from the opened receipt and reject excess; add the growing-file case.

**Risk assessment: MEDIUM.** Proof validation is substantially improved, but resource-bound behavior remains incomplete.

## 19-02

**Summary:** The artifact consolidation and lookup compatibility fixes are executable and consistent with existing source.

**Strengths**
- Final-name validation reaches the explicit `bin_name` override and installation before writes (`P/19-02-PLAN.md:121-122`).
- Moving `cli_spec` follows the existing apps → download dependency.
- Call-time lookup preserves current status-test isolation (`installer/status.py:45,91`).

**Concerns**
- No independent blocking defect found in the revised prescription.

**Suggestions**
- Keep the registry-wide placement-agreement test and raw-file exclusion from layout proof.

**Risk assessment: LOW.** Scope is controlled and reaches install, status and uninstall consumers.

## 19-03

**Summary:** A well-isolated pure core with adequate precedence and reason-order coverage.

**Strengths**
- The complete table and enum-order assertion pin the intended closed health model (`P/19-03-PLAN.md:89-97`).
- Absent configuration notes survive in caller order (`:123-134`), supporting the skill-pack requirements.

**Concerns**
- No independent blocker found.

**Suggestions**
- Retain the full table and duplicate-sentence tests rather than reducing them to examples.

**Risk assessment: LOW.** No I/O or mutation; failures are independently testable.

## 19-04

**Summary:** The batch adapter preserves existing native consumer semantics without rebuilding ownership logic.

**Strengths**
- Path-keyed partial-success parsing avoids positional misattribution.
- Per-argv memoization and usrmerge canonicalization are explicit (`P/19-04-PLAN.md:97-112,135-148`).
- Synthesized responses accommodate the existing per-path functions in `installer/install_ownership.py:181-195,251-266`.

**Concerns**
- No independent blocker found.

**Suggestions**
- Preserve the distinction between ambiguous inverse ownership and a positive package-membership answer.

**Risk assessment: LOW.** Pass-local evidence, injected probes and fail-closed uncollected paths limit the impact.

## 19-05

**Summary:** The revised Volta precedence addresses the actual early-return defect, while uv and host-setup changes remain appropriately constrained.

**Strengths**
- Both overlapping-directory cases are specified (`P/19-05-PLAN.md:103-115`).
- uv directory evidence is injected rather than guessed (`:153-155`).
- Host-setup claims require both verified inventory and matching live-path attribution (`:194`).

**Concerns**
- No additional independent blocker found.

**Suggestions**
- Keep clean update refusals and exhaustive owner-table tests in the same implementation unit.

**Risk assessment: LOW–MEDIUM.** Attribution is safety-sensitive, but the previously missing precedence rule is now explicit.

## 19-06

**Summary:** The plan reaches the terminal synchronizer’s non-obvious write sites and reuses pnpm inventory without another query.

**Strengths**
- Covers Konsole state creation, shared config writes and zsh-absent reversal (`installer/terminal_shell.py:260-266,307-311,369-380`).
- Whole-HOME path/bytes/mtime assertions are stronger than checking expected files only.
- Updates the real pnpm Doctor caller at `installer/pnpm_globals.py:593`.

**Concerns**
- No independent blocker found.

**Suggestions**
- Retain the dry-run `.zshrc`, Konsole and revert fixtures.

**Risk assessment: LOW.** Existing transformations are reused; read-only behavior is directly tested.

## 19-07

**Summary:** H4, M3 and M4 are materially corrected. Structured unknown results still need coordination with state reporting.

**Strengths**
- Closed scope validation and whole-listing invalidation avoid fabricated absence (`P/19-07-PLAN.md:123-124`).
- Marketplace cleanup now requires addressable preceding removals (`:174-175`).

**Concerns**
- **MEDIUM — CYCLE-1 M11, residual:** malformed listings deliberately produce unknown with no reasons (`:30,123,161`), while 19-16 only adds failure notes for raised exceptions. A pack present on another harness can consequently lose configuration evidence without explanation.

**Suggestions**
- Preserve an inconclusive-check indication separately from duplicate reasons and map it to the locked “skill configuration not checked” note.

**Risk assessment: MEDIUM.** Mutation-step construction is improved; unknown-evidence presentation remains incomplete.

## 19-08

**Summary:** The availability, cache-transition and pass-local-platform fixes are well targeted. One concrete builder contract remains incomplete.

**Strengths**
- Current availability now uses the resolver that actually gates brew (`P/19-08-PLAN.md:134-135`).
- Deterministic tests cover fresh cached evidence and overlapping platforms (`:211-213`).

**Concerns**
- **HIGH — NEW N5: `tool_state` cannot express the required checking fact as specified.** Its signature at `P/19-08-PLAN.md:135` has no `checking` input, while `:229` requires an unprobed pack to be built with a checking fact. Neither an explicit input nor a builder inference from missing skill data is defined.

**Suggestions**
- Specify `checking=()` and forward it into `Evidence`, or explicitly define the builder’s skill-data inference. Test both refresh and skill-state rebuild through that route.
- Make platform capture/publication ordering part of pass admission, so flight joiners bypass all acquisition and publication.

**Risk assessment: HIGH until N5 is clarified.** This is the shared producer of every displayed and actionable state.

## 19-09

**Summary:** The two write points fit the existing engine/update seams. The new rewrite-failure policy needs reconciliation with archive fallback.

**Strengths**
- Reuses one writer before postinstall (`installer/engine.py:234-255`, `installer/update.py:303-309`).
- Write failures remain visible without turning a completed install into failure.

**Concerns**
- **MEDIUM — NEW N3: deleting the previous receipt does not necessarily make the tool unproven.** `P/19-09-PLAN.md:31,132` promises that outcome, but receipt absence activates archive-layout proof under 19-10. A repaired archive with the normal layout remains proven and removable.

**Suggestions**
- Either retain a fail-closed marker for failed rewrites or explicitly permit layout fallback and narrow the “unproven” promise. Add an archive rewrite-failure test, not only raw yq.

**Risk assessment: MEDIUM.** The warning is truthful about deletion, but the resulting proof policy is contradictory.

## 19-10

**Summary:** H6–H8 now have concrete source-compatible fixes and tests across both removal interfaces.

**Strengths**
- Whole-receipt drift precedes pair authorization (`P/19-10-PLAN.md:127`).
- Optional tool identity correctly handles mixed environment/tool selections (`:200-205`).
- One remover rehashes before deletion.

**Concerns**
- **MEDIUM — NEW N3, inherited:** “no receipt” layout fallback conflicts with 19-09’s new failure semantics. Existing layout proof accepts a regular target inside the tool’s opt directory without receipt fingerprints (`installer/download.py:197-204`).

**Suggestions**
- Resolve the policy once across 19-09/10/14 and add the corresponding removal assertion.

**Risk assessment: MEDIUM.** The reported destructive-authority defects are fixed; proof fallback still needs a consistent contract.

## 19-11

**Summary:** The hook read-bound fix is sound. JSON root validation and inconclusive scan reporting remain underspecified.

**Strengths**
- The actual read is bounded, including after a misleading stat (`P/19-11-PLAN.md:164,174`).
- All nine global surfaces are covered without deleting machinery directly.

**Concerns**
- **MEDIUM — NEW N6: hooks-json traversal does not enforce the promised root shape.** The test at `:162` requires top-level arrays to fail closed, but `:174` scans the whole document without first requiring an object. An array containing `"gsd-context-monitor.js"` can therefore produce a leftover and uninstall step.
- **MEDIUM — CYCLE-1 M11, residual:** unreadable/malformed hook configs return None and count as no leftover (`:174-175`), bypassing 19-16’s exception-only note path.

**Suggestions**
- Require an object root for both JSON formats.
- Preserve inconclusive scan results and surface a configuration-check note.

**Risk assessment: MEDIUM.** Detection is read-only, but its conclusions produce later uninstall actions.

## 19-12

**Summary:** Shim-presence handling now reaches both independent filesystem fallbacks. Version-path forwarding needs one more explicit interface change.

**Strengths**
- Declared and implicit shim-only paths have regression coverage (`P/19-12-PLAN.md:110-121`).
- The pass retains one native index and one uv-directory query.

**Concerns**
- **MEDIUM — NEW N7: unresolved-path forwarding is incomplete.** `P/19-12-PLAN.md:195` changes `_version_argv` and says the pass supplies its hit, but the pass calls `resolve_status`, then `_probed_version`, then `_version_argv`. Those forwarding signatures are not specified. The actual call chain includes `installer/version_status.py:175,277,298-339,359,415`.

**Suggestions**
- Name the forwarding parameter on `resolve_status` and `_probed_version`, with every affected call reaching `_version_argv`.

**Risk assessment: MEDIUM.** Correct owner evidence will not by itself prevent probing the resolved shim.

## 19-13

**Summary:** The catalog migration is coherent and has strong generation, error and live-selectability checks.

**Strengths**
- Replaces independent decisions currently in `installer/catalog_tui.py:479-517,647-654`.
- Tests full-catalog refresh, mutation-induced checking and shared-flight tier switching (`P/19-13-PLAN.md:142-160`).

**Concerns**
- No independent blocker beyond upstream state contracts.
- The double test at `:109` ambiguously describes a successful helper call “with no explicit home” while also requiring that omission to raise `TypeError`.

**Suggestions**
- Separate the explicit-home success assertions from the missing-required-argument assertion.
- Assert Health declaration order explicitly rather than relying on `StrEnum` lexical ordering.

**Risk assessment: MEDIUM.** The UI prescription is sound but inherits service correctness.

## 19-14

**Summary:** Lock ownership and negative memoization are corrected. The final adoption-construction boundary remains insufficiently precise.

**Strengths**
- Compares the same immutable artifact passed into adoption (`P/19-14-PLAN.md:159`).
- Tests replacement before the adoption recheck and computes removability afterward.

**Concerns**
- **HIGH — CYCLE-1 H9, residual / NEW N1:** `:157` says to build the receipt exactly as `record` does through a shared builder, while `P/19-09-PLAN.md:131` fingerprints paths during construction. A literal shared builder can validate artifact A, then fingerprint replacement B and record B without comparing B to the cached digest. The receipt lock does not serialize filesystem replacement.
- **MEDIUM — NEW N3, inherited:** layout-proven archives contradict the new failed-rewrite “unproven” promise.

**Suggestions**
- Require adoption’s builder to consume the already validated artifact; prohibit another fingerprint acquisition during adopted-receipt construction.
- Add a test targeting that final construction boundary.

**Risk assessment: HIGH until N1 is closed.** Adoption automatically grants removal proof.

## 19-15

**Summary:** State-driven cells, escaped detail and update refusal behavior remain well aligned with the UI contract.

**Strengths**
- Removes independent detail builders currently at `installer/catalog_tui.py:656-775`.
- Explicit escaping and frozen-state doubles protect machine-derived content (`P/19-15-PLAN.md:106,138,148`).
- Return-type migration is accounted for downstream.

**Concerns**
- **LOW — CYCLE-1 retained:** default-shell evidence still runs outside ToolState (`:72`). This is expressly allowed by the locked UI contract, so it is not a blocker.

**Suggestions**
- Keep that exception narrow and documented.

**Risk assessment: LOW.** Remaining risks are integration volume and upstream evidence accuracy.

## 19-16

**Summary:** The pnpm repair contract is now correct. Failure reporting only covers part of the actual fail-closed pipeline.

**Strengths**
- Reuses the grouped node executor with pins, allowances and smoke (`P/19-16-PLAN.md:152-162`).
- Preserves absent-pack configuration facts and ordered steps.

**Concerns**
- **MEDIUM — CYCLE-1 M11, residual / NEW N2:** exception notes at `:197,205` miss ordinary unknown/None outcomes. Existing CLI errors are absorbed at `installer/skill_lifecycle.py:306-315,385-388`; malformed Claude output and unreadable hook configs also return normally. A pack present elsewhere can read OK without the promised “not checked” explanation.

**Suggestions**
- Carry inconclusive status in reports and add malformed-CLI/unreadable-hook integration tests.
- Retain a Phase-20 test starting from the emitted empty-argv `ConfigStep`, dispatching it, and observing the grouped install plus smoke. Manually invoking the executor here does not prove future dispatch.

**Risk assessment: MEDIUM.** H10 is corrected; incomplete evidence reporting still weakens truthful health.

## 19-17

**Summary:** Both prior HIGH rendering defects are corrected with the right underlying APIs.

**Strengths**
- Wrap-before-cut matches Rich’s actual line-building mechanism (`rich/text.py:1229-1249`).
- The adapter-selected parser preserves Uninstall’s literal filesystem paths.
- Compositor checks cover the shared Rule change’s blast radius (`P/19-17-PLAN.md:178-189`).

**Concerns**
- No remaining independent blocker found in the revised rendering mechanism.

**Suggestions**
- Keep all three overflow cases and re-cut on resize using current content width.
- Preserve the plain-text adapter and section-row controls.

**Risk assessment: LOW–MEDIUM.** The design is now sound; actual Textual geometry remains a runtime verification obligation.

## 19-18

**Summary:** The fresh-versus-batched resolver extraction is now precise enough to preserve both mutation-time freshness and refresh batching.

**Strengths**
- One private evidence-only resolver avoids duplicate attribution contracts (`P/19-18-PLAN.md:168,182`).
- Live platform reaches both ExecuteScreen and UpdateService.
- Base and override return types change together (`:208-210`).

**Concerns**
- No independent blocker beyond inherited state and version-probe contracts.

**Suggestions**
- Retain the regression proving public fresh resolution does not turn a refresh into per-tool native queries.

**Risk assessment: MEDIUM.** This is a large consumer migration, but the revised seam is appropriately defined.

## 19-19

**Summary:** The new pre-uninstall check closes the vacuous-removal gap, and the script remains isolated to disposable-container execution.

**Strengths**
- Establishes probe existence before the real uninstall boundary (`P/19-19-PLAN.md:100-115`; `scripts/container-e2e-verify.sh:433-456`).
- Keeps host-side tests as plumbing tests and real e2e as the phase gate.
- Documentation follows the existing phrase-test pattern in `tests/test_docs.py:188-199`.

**Concerns**
- **LOW:** `grep` for `"v": 1` and the tool string is not JSON/schema validation (`P/19-19-PLAN.md:112`). For example, malformed text containing both strings can pass.

**Suggestions**
- Call this a writer-format sanity check or use the receipt parser for the “valid receipt” claim. The actual removal gate remains the decisive proof.

**Risk assessment: LOW–MEDIUM.** The integration test is now non-vacuous; real container execution is still required.

## 19-20

**Summary:** The deletion remains appropriately scoped and reaches known constructor callers without leaving forwarding shims.

**Strengths**
- Removes the old catalog-wide sweep at `installer/wizard_app.py:3005-3020`.
- Covers both navigation and install-close callers (`:2776-2780,2940-2943`).
- Seeds replacement state rather than retaining an unused installed parameter (`P/19-20-PLAN.md:108-112`).

**Concerns**
- No independent blocking defect found.

**Suggestions**
- Keep a return-from-successful-uninstall regression as well as install-close/navigation tests. The actual uninstall path already invalidates and starts replacement refresh at `installer/wizard_app.py:1496-1519`.

**Risk assessment: LOW.** Mechanical deletion with an explicit replacement mechanism.

## 19-21

**Summary:** The revised discovery algorithm addresses both reported false-presence and traversal-bound defects.

**Strengths**
- Requires GSD-owned content rather than arbitrary non-empty directories (`P/19-21-PLAN.md:118`).
- Queue admission, entry count and symlinked roots are explicitly constrained (`:116-117`).
- Per-repo commands remain pinned and local.

**Concerns**
- **LOW:** the proposed `scandir` call-count assertion at `:103` observes visits, not queue admissions. An implementation can enqueue too much before visiting while satisfying that measurement.

**Suggestions**
- Add an admission/peak-queue assertion or an equivalent observable test that distinguishes bounded admission from bounded visitation.
- Consider extending a scan budget to adjacent global/runtime artifact listings; those listings are outside the primary walk’s entry budget.

**Risk assessment: LOW–MEDIUM.** The algorithm is corrected; its strongest resource-bound assertion could be more discriminating.

## Regressions Introduced by the Replan

### 1. Failed receipt rewrite re-enables archive-layout fallback — NEW N3

The new M7 policy deletes the previous receipt (`P/19-09-PLAN.md:132`). Receipt absence then permits archive-layout proof (`P/19-10-PLAN.md:127`), and 19-14 explicitly treats that proof as sufficient (`P/19-14-PLAN.md:187`).

Thus the claim that the tool becomes **unproven** is false for normal archive layouts. Decide whether fallback is intended, then align warning semantics, proof behavior and tests.

### 2. Adoption’s revised shared builder leaves a second fingerprint boundary — CYCLE-1 H9 / NEW N1

The digest-to-artifact comparison is fixed, but final construction remains ambiguous (`P/19-14-PLAN.md:157-159` versus `P/19-09-PLAN.md:131`). Explicitly preserve the validated artifact through receipt construction.

### 3. Failure-note revision misses non-exception failures — CYCLE-1 M11 / NEW N2

The new notes cover raised helper errors, but existing and newly planned fail-closed readers intentionally return unknown/None. Those results need propagation rather than being treated as negative evidence.

### Structural checks

- **21 plans present.**
- **No same-wave `files_modified` collisions found.**
- Declared dependencies point to earlier waves; no dependency cycle found.
- The new status files in 19-12 do not collide with another wave-3 writer.
- The 19-18 return-type migration reaches the named test overrides.
- H11/H12’s revised rendering mechanism introduces no additional identified adapter or wrapping regression.
- Commit `368da6a` carries the pnpm step-dispatch contract into Phase 20’s context.

## Overall Assessment

### Status: Issues Found — revise before execution

The replan substantially improves convergence: **10 of 12 HIGH findings are resolved; H9 remains partially resolved, and M11 remains partially resolved among the MEDIUM findings.** H1’s repeated appearances are counted once.

Priorities for the next revision:

1. **Close adoption construction:** reuse the validated artifact, without re-fingerprinting it in a shared builder.
2. **Complete the CHECKING builder interface.**
3. **Propagate inconclusive skill/hook evidence into “not checked” notes.**
4. **Reconcile archive fallback after failed receipt rewrites.**
5. **Bound receipt reads, require hook JSON object roots, and specify unresolved-version-path forwarding.**

**Overall risk: HIGH until the adoption and shared-state interface gaps are closed.** The remaining work is narrow contract correction, not a redesign or expansion of phase scope.

No files were edited, and no installers, tests, containers, explicit index sync, or host-mutating commands were run. Runtime correctness and platform behavior remain unverified.

---

## Consensus Summary

Convergence cycle 2. One reviewer ran: the `opencode-plan-review` instance (`router-env/my-plan-review`, pinned). It reviewed the plans at `368da6a`, after the replan `4c80be7`. The consensus gate does not engage with a single reviewer, so every HIGH it raised counts. The review is source-grounded: it cites `file:line` evidence throughout and carries neither the `[reviewed-without-source-citations]` marker nor the `[reviewed-without-repo-access]` marker. It covers all 21 plan ids.

**Cycle-1 status.** The reviewer checked all 12 cycle-1 HIGHs and 15 MEDIUMs against the current plans, and the orchestrator re-checked them against the Round 1 ledgers:
- **Resolved:** 11 of 12 HIGHs (H1-H8 and H10-H12) and 14 of 15 MEDIUMs. Some fixes are scoped: H10 for Phase 19 only (L-19-28 hands step dispatch to Phase 20), M5 within one pass, and M13 and M15 in the prescribed algorithm.
- **Partially resolved:** H9 and M11. Both are listed below.
- **Still open:** the cycle-1 LOW about the stale `resolve_status` range.
- **Acceptable:** the cycle-1 LOW about the default-shell exception in 19-15 is retained on purpose, which the UI-SPEC allows.

**Orchestrator check of this cycle's findings.** Each finding was checked against the current PLAN.md files and the source.

| # | Plan(s) | Severity | Finding | Orchestrator check | Origin |
|---|---|---|---|---|---|
| C2-H1 | 19-14 (+19-09) | HIGH | `adopt` re-fingerprints under the lock and then builds the receipt "exactly as `record` does (share one private builder)". `record` fingerprints `artifact_paths` itself, so a file replaced after the recheck is recorded without a digest comparison | **Confirmed.** See 19-14-PLAN.md:157 and 19-09-PLAN.md:131. The builder's input is not specified. The fix: the shared builder takes the already-verified `artifacts` tuple, and `adopt` passes `(artifact,)` from its own under-lock recheck. Do not fingerprint a second time | Cycle-1 H9, partially resolved. The wording predates the replan |
| C2-H2 | 19-08 | HIGH | The `tool_state(...)` signature has no `checking` input, but the skill pass must build "present=True with checking fact `checking which hosts have it`" | **Confirmed.** The signature at 19-08-PLAN.md:135 has `broken`, `misconfigured`, `unconfigured` and `notes` but no `checking`. The requirement is at :229, and 19-03 `Evidence` has `checking=()`. The fix: add `checking: tuple[str, ...] = ()` to `tool_state` and forward it to `Evidence`, with a test that goes through the builder | New. It was already present at 9a492dc and missed in cycle 1 |
| C2-M1 | 19-01 | MEDIUM | The 64 KiB receipt cap is a `lstat` size check followed by an unbounded read | **Confirmed.** See 19-01-PLAN.md:181-182. Apply the same bounded `read(65537)` fix that 19-11 M8 uses | New (pre-existing) |
| C2-M2 | 19-09, 19-10, 19-14 | MEDIUM | 19-09 deletes the old receipt when a rewrite fails and says the tool "reads unproven". Without a receipt, 19-10 falls back to archive-layout proof (`:127`), so an archive tool stays proven | **Confirmed.** See 19-09-PLAN.md:31 and 19-10-PLAN.md:127. The behaviour is defensible because layout proof checks the new on-disk structure. The 19-09 truth and its warning need narrowing ("unproven unless the layout proves it"), plus an archive rewrite-failure test | Regression from the M7 fix |
| C2-M3 | 19-07, 19-11, 19-16 | MEDIUM | "Not checked" notes fire only on raised exceptions. Fail-closed readers that return unknown/None (an invalid Claude listing, an unreadable hook config, absorbed CLI errors) still drop facts silently | **Confirmed.** See 19-16-PLAN.md:26,205 for the exception-only notes, 19-11-PLAN.md:175 ("None counts as no leftover") and 19-07-PLAN.md:123 (invalid listing is unknown). Carry an inconclusive flag in the report and map it to `skill configuration not checked: …` | Cycle-1 M11, partially resolved |
| C2-M4 | 19-11 | MEDIUM | `test_hook_config_fails_closed` lists "a top-level array", but the hooks-json action scans the whole document without requiring an object root | **Confirmed as a test/action gap.** The reviewer's own example (`["gsd-context-monitor.js"]`) would not match, because the scan needs a dict with `gsd-managed`. `[{"gsd-managed": true}]` would match, though. The fix: require a dict root for both JSON formats | New |
| C2-M5 | 19-12 | MEDIUM | `_version_argv(tool, ownership, unresolved=None)`: "the pass passes its looked-through hit", but the pass reaches `_version_argv` only through `resolve_status` and then `_probed_version` | **Confirmed.** The call sites are installer/version_status.py:175,277,339,359,415,724. Name the forwarding parameter on `resolve_status` and `_probed_version` | New (pre-existing) |
| C2-L1 | 19-13 | LOW | Test :109 says "with no explicit home", but :118 makes `home`/`skill_home` a REQUIRED keyword | **Confirmed wording contradiction.** Reword the test | New |
| C2-L2 | 19-19 | LOW | `assert_receipt_ready_for_removal` calls a receipt "valid" after two `grep -q` checks | **Confirmed.** See 19-19-PLAN.md:24,112. Call it a format sanity check, or validate it with the receipt parser | New |
| C2-L3 | 19-21 | LOW | The `scandir`-count assertion observes visits, not queue admissions | **Confirmed.** See 19-21-PLAN.md:103. Add an admission or peak-queue assertion | Cycle-1 M15 follow-up |
| C2-L4 | 19-12 | LOW | `resolve_status` is cited as `:150-340`, but it is declared at :298 | **Confirmed.** See 19-12-PLAN.md:75. The citation was not updated | Cycle-1 source-grounding LOW, unresolved |

The 19-08 and 19-16 suggestions were not counted. These are pass-admission ordering, and a Phase 20 dispatch test that the L-19-28 handoff already covers. They come with no concern attached.

### Agreed Strengths
With a single reviewer there is no cross-reviewer agreement. Its main strengths were:
- The replan's fixes trace to real source seams: `_write_unlocked`, call-time `which`, `(path, kind)` authorization, whole-receipt drift, `_UninstallEntry.tool`, the grouped node executor, wrap-then-cut, and the per-adapter parser.
- Structure is intact: no same-wave `files_modified` collisions, dependencies only point to earlier waves, and there is no cycle.

### Agreed Concerns
With one reviewer, the priorities stand as the reviewer ranked them:
1. Bind adoption's receipt construction to the verified artifact (C2-H1).
2. Add the `checking` input to `tool_state` (C2-H2).
3. Propagate inconclusive skill/hook evidence into "not checked" notes (C2-M3).
4. Reconcile the failed-rewrite wording with the archive layout fallback (C2-M2).
5. Bound receipt reads, require JSON object roots, and forward the unresolved version path (C2-M1, C2-M4, C2-M5).

### Divergent Views
None. Only one reviewer ran. The orchestrator corrected one detail of the reviewer's evidence (the C2-M4 example), and that correction does not change the finding.

### Cycle history
| Cycle | Commit reviewed | HIGH | Actionable non-HIGH |
|---|---|---|---|
| 1 | 9a492dc (review db26ba9) | 12 | 15 |
| 2 | 368da6a (this review) | 2 | 9 |

---
## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`), cycle 2. It ran on 2026-10-16 over all 21 plans at `368da6a`.

**Authority.** `drift-guard authority --raw` returned `intel`. `.planning/intel/` lists only CLI entry points, so every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO) under that authority. It is not treated as verified or missing on that basis. Supplementary evidence came from two sources:
- `codegraph explore` (the repo is CodeGraph-indexed), for declarations.
- Grep over `git ls-files`, outside `.planning/`, `.claude/` and `docs/`.

`drift-guard severity` under `intel` gives VERIFIED -> none, MISSING -> needs-acknowledgement (no hardBlock), AMBIGUOUS -> MEDIUM and UNCHECKABLE -> INFO. No verdict produced a hardBlock.

**Scope (delta pass).** Cycle 1 (db26ba9) grounded the full 1083-token set at `9a492dc`. This cycle enumerates the backticked symbol, path and flag tokens that the replan (`4c80be7`) newly introduced: 100 tokens in total, compared with the same plans at `9a492dc`.

- **Source evidence (54).** These have a declaration or reference in tracked source, or are an existing path or flag. The following declarations were spot-verified:
  - `_UninstallEntry` (installer/wizard_app.py:864) has no `tool` field today, which 19-10 adds. In the same file: `_tool_entry` :1003, `_ENV_KEYS` :896, `_apply_removal` :1453, Uninstall `detail_is_markup=False` :1152.
  - `ToolRow.tool` (installer/uninstall.py:178).
  - `_resolve_active_path` (installer/ownership.py:1042).
  - In installer/guards.py: `guarded_names` :476, `is_our_shim` :274, `real_pnpm` :316.
  - In installer/executors.py: `SMOKE_CHECKS` :386, `_node` :464, `allow_build`/`--allow-build` :472,495.
  - `section_detail_style` and `detail_is_markup` (installer/tool_browser.py:66-67,342-345).
  - `macos_stub_reason` (installer/status.py:36).
  - `should_fetch_managers` (installer/version_cache.py:429) and its unconditional freshness return (installer/version_status.py:613-615).
  - In installer/resolve.py: `resolve_methods` :81, `unavailable_reason` :131, `platform_could_support` :171 (`has_brew=True` probe :195).
  - `IncompleteGroup.present/missing` (installer/pnpm_globals.py:138-139), `node_install_policy` :229 and `incomplete_install_groups` :489.
  - `ManagerSnapshot.failed_at` (installer/version_cache.py:58).
  - `TRACER_RERUN_OK` (scripts/container-e2e-verify.sh:446).
  - `is_still_proven` layout proof (installer/download.py:197-204).
  - The `resolve_status`, `_probed_version` and `_version_argv` call chain (installer/version_status.py:175,238,269,277,298,339,359,415,724).
- **No source evidence (46). All of them are new by design.** None is a hallucinated reference to existing code:

| Cited at | Token(s) | Why absent |
|---|---|---|
| 19-01, 19-14 | `_WRITE_LOCK`, `_write_unlocked`, `receipts._write_unlocked`, `_MEMO_LOCK` | created by 19-01 |
| 19-02 | `_is_single_name` | created by 19-02 |
| 19-07 | `CLAUDE_SCOPES` | created by 19-07 |
| 19-08 | `NEEDS_BREW_REASON`, `pass_platform` | created by 19-08 (`pass_platform` is a pass-local name) |
| 19-17 | `_two_rows`; `MarkupError` | created by 19-17; `rich.errors.MarkupError` is a dependency |
| 19-18 | `_resolve_owner_from` | created by 19-18 |
| 19-19 | `assert_receipt_ready_for_removal`, `TRACER_RECEIPT_PRE_UNINSTALL_OK/MISSING` | created by 19-19 |
| 19-21 | `_MAX_WALK_ENTRIES`; `a/.planning/config.json`, `claude/commands/gsd-plan-phase.md` | created by 19-21; fixture paths in new tests |
| 19-02..19-21 | 29 `test_*` names (for example `test_adopt_completes_without_deadlock`, `test_receipt_type_cannot_turn_a_file_path_into_a_directory`) | new tests the plans create |

**Existence-class findings from this pass (needs-acknowledgement):**
- 19-08-PLAN.md:135: `tool_state(...)` has no `checking` parameter, but :229 requires a checking fact through it. This confirms C2-H2. The builder is new, so this is an interface gap, not a missing symbol in the source.
- 19-12-PLAN.md:75: `resolve_status` is cited at `:150-340`, but the declaration is at installer/version_status.py:298 (C2-L4, LOW).

**Reviewer citations spot-checked:**
- installer/version_status.py:613-615 (fresh snapshot early return).
- installer/skill_lifecycle.py:306-315 (`_probe_outputs` absorbs CLI errors to None) and :385-388 (`None` -> "unknown").
- installer/status.py:45,91 (call-time `shutil.which`).
- installer/wizard_app.py:1152.
- installer/download.py:197-204.

All of these match the reviewer's description. One reviewer example was inaccurate, and its finding was re-grounded in the Consensus table (C2-M4).

**UNCHECKABLE / skipped.**
- Signatures cannot be asserted under `intel`/grep. Names, declaration lines and the call chain only were checked.
- External surfaces are not in the repo:
  - Rich wrapping internals. The reviewer cited `.venv/.../rich/text.py:1229-1249`, which the orchestrator did not re-open.
  - Claude Code `installed_plugins.json`.
  - The GSD 1.16.0 hook surfaces.
  - pnpm, uv and Volta output.
- No tests, containers or live runs were executed. All checks were read-only.
- Wave/file-overlap check: no two plans in one wave share a `files_modified` entry (all 8 waves). All `depends_on` entries point to earlier waves.

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 19`): verdict `consistent`. STATE.md says "Ready to plan" and ROADMAP.md says "Not started" (both rank 0).
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction introduced by the replan.
  - SC3 ("a receipt whose link target no longer matches makes the tool not removable") is strengthened by 19-10's whole-receipt drift truth.
  - SC4 ("installing brew in-session makes colima installable") is consistent with 19-08's live `resolve_methods` availability. SPEC R2 ("unavailable (none applies)") is also consistent.
  - The ROADMAP plan list (21 plans, W1-W8) still matches each plan's `wave:` frontmatter.
- **Requirement IDs** (ROADMAP.md authority): STATE-01..STATE-07 are each covered, and no plan cites an ID outside the roadmap.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority): no new drift.
  - The cycle-1 D-12 advisory is resolved: 19-CONTEXT.md:80 now marks `--bin` as superseded by L-19-01.
  - D-21's "non-empty" rule is refined, not contradicted, by 19-21's "has a `gsd-*` entry". L-19-27 (19-CONTEXT.md:224) records the refinement in CONTEXT itself.
  - D-14 (`has_brew` re-read per pass) matches 19-08's pass-local platform.
  - L-19-28 (pnpm group step, empty argv, Phase 20 dispatch) matches 19-16-PLAN.md:152-162.
- **UI-SPEC copy ↔ plan strings:** the four rows that 368da6a added match the plan literals exactly:
  - `needs Homebrew, which is not on PATH`, which is 19-08 `NEEDS_BREW_REASON`.
  - `terminal shell not checked: {error}`, `pnpm group not checked: the pnpm inventory is unreadable` and `skill configuration not checked: {error}`, which are in 19-16.
- **Within-artifact (not a pair axis, recorded for the planner):** 19-09-PLAN.md:31 ("the tool reads unproven") contradicts the archive-layout fallback at 19-10-PLAN.md:127. This is already counted as C2-M2, and it belongs to plan-checker Dimension 9, so it is not counted again here.
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
