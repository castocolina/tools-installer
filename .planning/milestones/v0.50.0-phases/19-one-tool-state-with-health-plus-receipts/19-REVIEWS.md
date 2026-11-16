---
phase: 19
cycle: 3
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-16T09:35:35Z
plans_reviewed: [19-01-PLAN.md, 19-02-PLAN.md, 19-03-PLAN.md, 19-04-PLAN.md, 19-05-PLAN.md, 19-06-PLAN.md, 19-07-PLAN.md, 19-08-PLAN.md, 19-09-PLAN.md, 19-10-PLAN.md, 19-11-PLAN.md, 19-12-PLAN.md, 19-13-PLAN.md, 19-14-PLAN.md, 19-15-PLAN.md, 19-16-PLAN.md, 19-17-PLAN.md, 19-18-PLAN.md, 19-19-PLAN.md, 19-20-PLAN.md, 19-21-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 19 (convergence cycle 3, final)

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

> Cycle 3 replaces the cycle-2 review (`git show 40b51d5:.planning/phases/19-one-tool-state-with-health-plus-receipts/19-REVIEWS.md`). It reviews the plans at `e019192`, after the replan `cefe8a9`. The reviewer verifies the cycle-2 findings per id in its "Cycle-2 Findings Verification" table below.

## OpenCode Review (opencode-plan-review)

# Phase 19 — Convergence Cycle 3 (final) Review

**Document type:** GSD implementation plans (`.planning/phases/19-one-tool-state-with-health-plus-receipts/19-01..19-21-PLAN.md`) · archetype `plan`, grounded against the phase's CONTEXT/SPEC/UI-SPEC siblings and live source at the current tree (post-`cefe8a9`).
**Method:** read-only. `git show cefe8a9`, `git show 40b51d5:...19-REVIEWS.md`, codegraph/source reads of `installer/version_status.py`, `installer/download.py`, `installer/update.py`, `installer/apps.py`, `installer/status.py`, `installer/atomic.py`, `tests/test_download.py`, current plan texts. No files edited, no tests/containers/host mutation run.

## Cycle-2 Findings Verification

| ID | Plan(s) | Verdict | Evidence (current plans / source) |
|---|---|---|---|
| C2-H1 | 19-14 (+19-09) | **RESOLVED** | 19-09-PLAN.md:132-133 defines pure `_build_receipt(tool, method, artifacts, *, package, smoke)` that "never calls `fingerprint`, `sha256_file`, `artifact_paths` or any stat"; 19-14-PLAN.md:160 `adopt` takes ONE under-lock `fingerprint`, requires `fresh == artifact`, builds via `_build_receipt(tool, method, (fresh,), ...)`, writes via `_write_unlocked`; AST verify gates on both plans forbid the second fingerprint and `record`/`write` calls |
| C2-H2 | 19-08 | **RESOLVED** | 19-08-PLAN.md:137 `tool_state(..., checking=(), ...)` forwarded to `Evidence(checking=checking)`; `inspect.signature` verify gate; Task 3 (:233) builds the unprobed pack through that input; `test_tool_state_forwards_checking_facts` compares pass output with builder output |
| C2-M1 | 19-01 | **RESOLVED** | 19-01-PLAN.md:182-184 `fh.read(_MAX_RECEIPT_BYTES + 1)` rejects a longer read; lstat kept as shortcut; `test_read_fails_closed_on_a_file_that_grew_after_the_size_check`; acceptance grep forbids `read_bytes`/`read_text` |
| C2-M2 | 19-09/10/14 | **RESOLVED** | 19-09-PLAN.md:134 warning "states only what happened to the receipt file… never says 'unproven'"; 19-10-PLAN.md no-receipt layout fallback unchanged; 19-14-PLAN.md:200 "proof is whatever `plan_removal` answers without a receipt (layout for an archive, nothing for a raw binary)"; end-to-end parametrized test `test_failed_rewrite_leaves_an_archive_layout_proven_and_a_raw_binary_unproven` |
| C2-M3 | 19-07/11/16 | **RESOLVED** | 19-07 truth: `unknown` host status *is* the inconclusive flag (never collapsed to absent) + `test_four_install_pack_with_an_unreadable_listing_is_an_unknown_host`; 19-11 `ProjectPackReport.unchecked` (19-11-PLAN.md Task 2 truth + acceptance grep `unchecked: tuple[str, ...] = ()`); 19-16 Task 3 adds `skill configuration not checked: no readable answer from {Harness}` and `cannot read ~/{path}` notes with two dedicated tests |
| C2-M4 | 19-11 | **RESOLVED** | 19-11 Task 2 truth: "Both JSON formats require a top-level JSON object… `[{"gsd-managed": true}]` matches nothing (review C2-M4)"; `test_hook_config_fails_closed` parametrized cases include both top-level-array shapes |
| C2-M5 | 19-12 | **RESOLVED** | 19-12-PLAN.md Task 3: keyword-only `unresolved` on `resolve_status`, `resolve_github_release_status`, `_probed_version`, forwarded at all six call sites; forwarding-count verify gate (`unresolved=unresolved` ≥ 6); four-route parametrized test. Source chain confirmed: version_status.py:175, 277, 317, 339, 359, 415, 724 |
| C2-L1 | 19-13 | **RESOLVED** | 19-13 Task 1 behavior: success assertion passes explicit scratch homes; separate `TypeError` assertion for omitted `skill_home`; "No success case omits the home" |
| C2-L2 | 19-19 | **RESOLVED** | 19-19 Task 1: receipt validated by `receipts.read(<id>)` via `uv run` in `TESTER_WORKSPACE`; parser exit code in the MISSING line; host test stubs `uv` with the test interpreter and adds the strings-only `{"v": 1, "tool": "yq"}` case; acceptance grep `receipts.read(` ≥ 1 |
| C2-L3 | 19-21 | **RESOLVED** | 19-21-PLAN.md:103/117: module-level `from collections import deque`; recording `deque` subclass asserts ≤ `_MAX_WALK_DIRS` appends and peak queue length; symlinked roots rejected; acceptance grep pins the import |
| C2-L4 | 19-12 | **RESOLVED** | 19-12-PLAN.md context now cites "declared at `:298`" with the full callee chain; matches source (`resolve_status` at installer/version_status.py:298) |

All eleven cycle-2 findings are resolved in the current plan texts, not merely in the ledgers.

## Regressions Introduced by cefe8a9

I hunted for new contradictions, interface mismatches, missing symbols, impossible tests, same-wave file collisions and broken `depends_on`. Structural checks pass: 21 plans; no two plans in any wave share a `files_modified` entry (re-derived from current frontmatter, all 8 waves); every `depends_on` points to an earlier wave; no dependency cycle. The C2 fixes introduce no new symbol that another plan consumes inconsistently (`_build_receipt` is produced by 19-09 and consumed by 19-14 with matching signatures; `unchecked` is produced by 19-11 and consumed by 19-16 with matching copy).

Two residual executable gaps remain — both **pre-existing holes the cycle-2 scope did not cover**, not breakage from the replan (details under 19-02 and 19-09 below):

1. **R1 — the unsafe-name guard misses the third write site (`update_download`).** `installer/download.py:268` computes `binname = link_name(method, target.member)` and writes to `dest / binname` (`:273-278`, `_replace_raw`/`_replace_archive`) with no single-basename check. 19-02's `_is_single_name` is prescribed for `artifact_paths` and `install_download` only (19-02 Task 1). A registry `bin_name = "../x"` that install now rejects before any write can still be written outside the bin dir by an installer-owned update (`installer/update.py:329-337` → `update_download`). Same threat class as the mitigated T-19-06/M2.
2. **R2 — the update receipt records a smoke that never ran.** `tests/test_download.py:1858` (`test_update_download_does_not_smoke`) pins that download updates perform no smoke; 19-09 Task 3 (`installer/update.py _perform` receipt call, `smoke="ok" if the kind is a download/app kind else None`) would write `"smoke": "ok"` anyway. 19-14 itself sets `smoke=None` for adoption "because adoption runs no smoke" — the same reasoning applies to the update path.

No other new regression found.

## 19-01

**Summary:** Receipts module plus the Wave-0 sandboxes; C2-M1's bounded read is correctly implemented at the read itself, with a growth-after-lstat test that monkeypatches `lstat` and counts `read` calls.
**Strengths:** one writer under one non-reentrant lock with `_write_unlocked` as the only file-writing function (deadlock-safe for 19-14's `adopt`); strict per-type required fields and `bool` rejection; per-session re-hash memo with its own lock; autouse `sandboxed_receipts`/`sandboxed_bin_dir` plus the real-home fingerprint entry land before any consumer.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW.

## 19-02

**Summary:** One `artifact_paths` formula for install/receipt/uninstall plus implicit bin-dir presence; sound and well-tested, but the traversal guard covers two of the three write sites.
**Strengths:** `cli_spec` move respects the import cycle (L-19-04, AST-gated); registry-wide placement-agreement test over all 96 (method, arch) pairs; `which=None` resolved at call time preserves the existing `status.shutil.which` monkeypatch pattern (matches installer/status.py:91 today); raw files excluded from layout proof.
**Concerns:**
- **MEDIUM (R1): `update_download` is unguarded.** Plan Task 1 applies `_is_single_name` in `artifact_paths` and `install_download` only. Source: `installer/download.py:268-278` (`link_name` → `dest / binname` → `_replace_raw`/`_replace_archive`), reached from `installer/update.py:329-337`. A declared `bin_name` of `../x` or `/abs/x` that install rejects can still overwrite a path outside the bin dir during an installer-owned update.
**Suggestions:** apply `_is_single_name` to `link_name(method, target.member)` at the top of `update_download` (same `ExecutorError` before `ensure_dir`/fetch), with raw and archive update rejection tests mirroring `test_install_download_rejects_an_unsafe_bin_name`; note it in T-19-06.
**Risk:** MEDIUM (one guard, one test away from LOW).

## 19-03

**Summary:** Pure `Health`/`Evidence`/`tool_health` core proven by an 18-row parametrized table before any caller exists; unchanged by cefe8a9 and still consistent with 19-08's `checking` input.
**Strengths:** declaration-order-is-precedence pinned by test; absent-tool notes contract (B1/W1) exactly what 19-08/19-16 rely on; no I/O.
**Concerns:** none.
**Suggestions:** none.
**Risk:** LOW.

## 19-04

**Summary:** Batched native index and shim look-through; unchanged this cycle, still executable against the real argv shapes in `installer/install_ownership.py`.
**Strengths:** path-keyed parse with usrmerge canonicalization on both sides; per-argv memoization covers `rpm-ostree status` and declared-package queries; existing per-path probe functions stay byte-identical.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW.

## 19-05

**Summary:** Volta/uv-tool-dir/host_setup attribution with clean update refusals; unchanged this cycle.
**Strengths:** Volta shim evidence decided before the single-active-candidate return (review H3) with both overlap fixtures; `uv tool dir` per L-19-01 with the env-var guess deleted and gated (`UV_TOOL_BIN_DIR` grep = 0); `method_package` as the one package reader with byte-identical `method_removal_command` strings.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW–MEDIUM (owner claims gate update/remove hints, but refusals are zero-subprocess).

## 19-06

**Summary:** Dry-run terminal sync and pnpm group check over the cached inventory; unchanged this cycle.
**Strengths:** all four write sites gated (L-19-05) with whole-HOME byte+mtime fingerprints including the zsh-absent revert; `incomplete_install_groups` reads a plain package collection so the pass adds no query.
**Concerns:** none.
**Suggestions:** none.
**Risk:** LOW.

## 19-07

**Summary:** Claude `--json` parser, `ConfigStep`, `TOOL_ID_RE`; the C2-M3/M4 fixes are correctly instantiated here (unknown host = the inconclusive flag; one malformed-entry policy).
**Strengths:** `CLAUDE_SCOPES` closed before any `-s` argv; hostile ids make the whole listing unknown rather than skipped; H4's marketplace-remove ordering keeps a suppressed-copy marketplace installed; id validation at registry load (checker I4) so a bad id fails before any refresh.
**Concerns:** none new — the residual presentation gap is closed by 19-16's mapping, which this plan's truth now names explicitly.
**Suggestions:** none.
**Risk:** LOW.

## 19-08

**Summary:** The one-swap `ToolState` snapshot with single-flight join and live `has_brew`; C2-H2 is properly closed through the builder, and the fix is consistent across Tasks 1 and 3 and the artifacts list.
**Strengths:** availability from `resolve_methods` with the pass platform (`unavailable_reason` wording only); per-record newest-wins via `seq` with an overtaken pass publishing nothing; join never crosses an invalidate and a failed pass re-raises in every joiner; `sandboxed_skill_home` keeps test-built services off the developer's HOME.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (highest-centrality plan of the phase; contract is now complete, residual risk is execution volume, not design).

## 19-09

**Summary:** One receipt writer called from install and update; C2-H1 (`_build_receipt`) and C2-M2 (narrowed "unproven unless layout proves it") are correctly instantiated.
**Strengths:** pure builder AST-gated to never fingerprint; `record`'s failed-rewrite policy decided once for both write points; receipt write failure never fails the install (SPEC AC9); manager updates rewrite only an existing receipt (T-19-27).
**Concerns:**
- **MEDIUM (R2): update receipts falsely record `smoke: "ok"`.** Task 3 prescribes `smoke="ok" if the kind is a download/app kind else None` on the update path, but download/app updates run no smoke — pinned by `tests/test_download.py:1858` (`test_update_download_does_not_smoke`, which even installs a member script exiting 127). A receipt is proof metadata; writing a verification result that never ran contradicts the phase's truthfulness goal and 19-14's own `smoke=None`-because-no-smoke reasoning.
**Suggestions:** record `smoke=None` on the update path unless a smoke actually runs and passes (then say so); add an update-receipt smoke-field test asserting `None`.
**Risk:** MEDIUM (a one-word fix plus one assertion; not a removal-authority defect since removal matches artifacts only).

## 19-10

**Summary:** Receipt ∩ `artifact_paths` removal with deletion-time re-hash through one shared remover; C2-M2's fallback policy now consistent with 19-09/19-14.
**Strengths:** whole-receipt drift checked before the `(path, kind)` pair authorization (H6/H7 both still pinned by tests and acceptance greps); `_UninstallEntry.tool` matches the real row shape; corrupt receipt gets no layout fallback while a deleted one does — the two cases are now deliberately and consistently distinguished.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (destructive authority — but the guard set is complete as written).

## 19-11

**Summary:** Project-pack registry keys and the global-leftover scan across all nine harness homes; C2-M3 (`unchecked`) and C2-M4 (object-root JSON) are correctly instantiated.
**Strengths:** tri-state `_gsd_hooks_registered` (missing = False, inconclusive = None) with `unchecked` carried in the report; the read bound is the read itself (256 KiB + 1) with the grew-after-stat test; module assert keeps `PROJECT_GLOBAL_MACHINERY` keys equal to `INSTALL_STATE_HARNESS_DIRS`.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW.

## 19-12

**Summary:** Owner evidence wiring (uv tool dir, shim look-through, one batched native query) and owner/version notes; C2-M5/L4 fixes verified above.
**Strengths:** shim skip reaches both filesystem fallbacks in `is_installed` (M9), matching the real checks at installer/status.py:98-107; forwarding is count-gated so an executor cannot silently drop the unresolved hit; skill packs get no binary notes (W1).
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW–MEDIUM.

## 19-13

**Summary:** Health column and state-driven catalog decisions; unchanged in substance by cefe8a9 beyond the C2-L1 test split, which removes the wording contradiction.
**Strengths:** `…` on every row after a mutation with no stale-mark fallback (SPEC prohibition "no ✓ while pending"); full-catalog refresh joining the service's single flight; cache-save warning surfaced (checker W3).
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (inherits 19-08 correctness; its own contracts are complete).

## 19-14

**Summary:** Receipts as state evidence plus digest adoption; both cycle-2 HIGH/MEDIUM threads (C2-H1, C2-M2) land coherently with AST gates and replacement-race tests at both the pass and the construction step.
**Strengths:** adoption binds the digest to the bytes it records (one fingerprint per attempt, one under lock, equality-checked); non-match memo keyed by expected digest (M10); unproven note computed from `plan_removal`'s actual answer, not asserted; deadlock test repeated 5×.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (adoption grants removal proof; the prescribed races are now closed).

## 19-15

**Summary:** Ver/Owner cells, health-block detail, legend and state-driven `u`; unchanged by cefe8a9.
**Strengths:** markup escaping on every reason/step; private-store pokes converted to `FrozenStateService`/`seeded_service` with a source-scan test; the retained default-shell render-time exception stays inside the UI-SPEC's allowance.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW (large but mechanical conversion with gates).

## 19-16

**Summary:** The `≈` evidence assembly; C2-M3's mapping (unknown host → `no readable answer from {Harness}`; `unchecked` path → `cannot read ~/{path}`) is instantiated with dedicated parametrized tests, and stale/absent-harness non-firing is stated.
**Strengths:** the `pnpm_group_install` step keeps the empty-argv grouped-node-executor contract (H10) with an execution test through `executors.execute` on the real registry method; terminal-drift seam failure degrades to a `not checked` note, never an exception; project-pack presence/reasons/steps flow through the 19-08 builder's absent-pack demotion.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (broadest integration surface of the phase; contracts verified consistent with 19-06/07/08/11/21).

## 19-17

**Summary:** 80×20 layout contract; unchanged by cefe8a9; H11/H12 remain correctly prescribed (`Text.wrap` then keep two rows; per-adapter parser choice).
**Strengths:** compositor-based visibility checks on every tier and on Doctor/Uninstall/Policies (the Rule change's blast radius); every-mark-on-every-tier test (SPEC AC4) via `FrozenStateService`.
**Concerns:** none new (runtime Textual geometry remains an execution obligation, as the plan itself acknowledges with the fallback path).
**Suggestions:** none.
**Risk:** LOW–MEDIUM.

## 19-18

**Summary:** Consumer rewiring and transitional-reader deletion; unchanged by cefe8a9.
**Strengths:** `_resolve_owner_from` is the single `resolve_ownership` caller with batched (pass) and fresh (public) evidence (M12), gated by the one-native-query regression test; `UpdateService(live_platform=...)` read at run time; `refresh -> None` migrated together with every test override (checker W4).
**Concerns:** none new.
**Suggestions:** none.
**Risk:** MEDIUM (largest mechanical migration; seams verified against source).

## 19-19

**Summary:** Container e2e receipt assertions and the architecture record; C2-L2 is resolved by validating the pre-uninstall receipt with the real parser via `uv run` (exit code surfaced), and the host-side test's `uv` stub makes that command runnable offline — the strings-only `{"v": 1, "tool": "yq"}` case proves the parser, not a text match, decides.
**Strengths:** category-scoped skipping with a named `TRACER_RECEIPT_SKIPPED` line; append-only architecture.md guard; no task runs a container or touches the host.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW.

## 19-20

**Summary:** Mechanical deletion of the per-tier installed copies; unchanged by cefe8a9.
**Strengths:** signature test plus grep gates keep the map gone; discriminating-mutation protocol where RED is unavailable; the sweep's replacement (epoch bump + one pass) is asserted with counting predicates.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW.

## 19-21

**Summary:** Bounded repo walk, real per-runtime install counting, per-repo install steps and pinned handoff text; C2-L3 is resolved by asserting queue admissions and peak length on an observable module-level `deque` (19-21-PLAN.md:103, :117), with symlinked roots rejected and `_MAX_WALK_ENTRIES` bounding single-dir enumeration.
**Strengths:** M14's `gsd-`-entry rule with the stale-VERSION-beside-unrelated-skills test; the checker-I3 host case (real claude + empty opencode) yields exactly one opencode reinstall step; step argv built only from constants and the validated pin, `cwd` checked absolute and existing.
**Concerns:** none new.
**Suggestions:** none.
**Risk:** LOW–MEDIUM.

## Overall Assessment

**Status: Approved for execution, with two small fixes recommended first.** All 11 cycle-2 findings (2 HIGH, 6 MEDIUM, 3 LOW) are verified RESOLVED in the current plan texts — not just in the dispositions ledgers — and the replan introduced no regressions: no same-wave `files_modified` collisions across all 8 waves, no broken `depends_on`, no new undefined symbol, no new cross-plan contract mismatch. Plan coverage: all 21 ids reviewed above.

Remaining actionable findings (both pre-existing scope gaps, both one-line-to-few-line plan edits):

| # | Plan | Severity | Concrete PLAN.md change still needed |
|---|---|---|---|
| R1 | 19-02 | MEDIUM | In Task 1's action, apply `_is_single_name` to `link_name(method, target.member)` at the top of `update_download` (installer/download.py:268), raising the same `ExecutorError` before `ensure_dir`/fetch; add `test_update_download_rejects_an_unsafe_bin_name` (raw + archive) and name `update_download` in T-19-06's mitigation. |
| R2 | 19-09 | MEDIUM | In Task 3, change the update-path receipt call to `smoke=None` unless a smoke actually runs (source: `tests/test_download.py:1858` pins that download updates do not smoke); add an assertion that the update receipt's `smoke` is `None`. |

Overall risk: **MEDIUM** — down from cycle 2's HIGH. The adoption-construction, CHECKING-builder, inconclusive-evidence and fallback-policy threads that blocked cycles 1–2 are closed with discriminating tests and gates; what remains are two guard/metadata omissions on the update path, neither of which grants wrong removal authority or deadlocks execution.

Not checked: live runtime behavior (no tests, containers or TUI runs were executed — that is the executors' and the orchestrator's `make e2e` gate), and Rich/Textual version behavior beyond what cycle 2 already grounded.

---

## Consensus Summary

Convergence cycle 3 (final). One reviewer ran: the `opencode-plan-review` instance (`router-env/my-plan-review`, pinned). It reviewed the plans at `e019192`, after the replan `cefe8a9`. The consensus gate does not engage with a single reviewer, so every HIGH it raised would count; it raised none. The review is source-grounded: it cites `file:line` evidence and carries neither the `[reviewed-without-source-citations]` marker nor the `[reviewed-without-repo-access]` marker. It covers all 21 plan ids.

**Cycle-2 status.** The reviewer marked all 11 cycle-2 findings RESOLVED in the current plan text. The orchestrator re-checked each one against the current task action, acceptance and test text, not only the Round 2 ledgers, and agrees:
- **C2-H1:** 19-09-PLAN.md:31,132-133,147 (pure `_build_receipt`, AST gate) and 19-14-PLAN.md:29,145,160,169 (one under-lock `fingerprint`, `_build_receipt(tool, method, (fresh,), ...)`, construction-step race test, AST gate). Resolved.
- **C2-H2:** 19-08-PLAN.md:31,125,137,147,218,233. `checking=()` is forwarded to `Evidence`, has a signature gate, and the pass is compared with the builder. `ToolState.present` is a property that is False for CHECKING (:135), so the test's `state.present is False` is consistent. Resolved.
- **C2-M1:** 19-01-PLAN.md:23,171,182-183,198. The read is bounded to 65537 bytes, and there is a grep gate against whole-file reads. Resolved.
- **C2-M2:** 19-09-PLAN.md:32,134; 19-10-PLAN.md:27,116; 19-14-PLAN.md:30,195,200. The policy is "unproven unless the archive layout proves it", with a raw-binary removal test and the rg/yq end-to-end test. `install_tool(..., repair=True)` exists (installer/engine.py:136,145). Resolved.
- **C2-M3:** 19-07-PLAN.md:31,164,175; 19-11-PLAN.md:27,163-164,177; 19-16-PLAN.md:27,199-200,209,223. `CalledProcessError` is a `SubprocessError`, which `_probe_outputs` absorbs to None (installer/skill_lifecycle.py:306-315), and None -> `"unknown"` (:386-387). `SKILL_HARNESS_LABELS["claude"] == "Claude Code"` (:74) matches the test literal. Resolved.
- **C2-M4:** 19-11-PLAN.md:26,163. Resolved.
- **C2-M5 and C2-L4:** 19-12-PLAN.md:27,78,189,195-196,203. The six forwarding sites match installer/version_status.py:175,277,317,339,359,415, and the pass call is :724. Resolved.
- **C2-L1:** 19-13-PLAN.md:109. Resolved.
- **C2-L2:** 19-19-PLAN.md:101,112-113. The parser runs in a subprocess with `HOME=<scratch>`. `default_receipts_dir()` derives from `Path.home()` (19-01-PLAN.md:118), so it resolves to the same `<scratch>/.local/state/tools-installer/receipts` the test writes to. Resolved.
- **C2-L3:** 19-21-PLAN.md:103,117. Resolved.

**Orchestrator check of this cycle's findings.** Each finding was checked against the current PLAN.md files and the source.

| # | Plan(s) | Severity | Finding | Orchestrator check | Origin |
|---|---|---|---|---|---|
| C3-M1 | 19-02 | MEDIUM | The single-basename guard `_is_single_name` covers `artifact_paths` and `install_download` but not `update_download`. That function computes `binname = link_name(method, target.member)` and writes `dest / binname` through `_replace_raw`/`_replace_archive` with no check | **Confirmed.** See installer/download.py:257-278 and the call from installer/update.py. 19-02-PLAN.md:134,151 and its M2 ledger row (:286) name only `artifact_paths` and `install_download`. The registry loader does not validate `bin_name` (installer/model.py:62,72 only list it as a known param). The fix: apply `_is_single_name` to `link_name(method, target.member)` at the top of `update_download` and raise the same `ExecutorError` before `ensure_dir`/fetch. Add `test_update_download_rejects_an_unsafe_bin_name` (raw and archive), bump the `_is_single_name(` grep floor from 3 to 4, and name `update_download` in T-19-06 | Cycle-1 M2, scope incomplete. Pre-existing; cefe8a9 did not introduce it |
| C3-M2 | 19-09 | MEDIUM | The update-path receipt records `smoke="ok"` for download/app kinds, but updates never run a smoke | **Confirmed.** See 19-09-PLAN.md:216. installer/apps.py:117 says "Updates never smoke the staged CLI (D-06)". `update_download` passes no `smoke_argv` (installer/download.py:274-276, against install's :239,248), and tests/test_download.py:1858 `test_update_download_does_not_smoke` pins this. 19-14 already uses `smoke=None` because "adoption runs no smoke". The fix: in 19-09 Task 3, pass `smoke=None` on the update path, or the real result if a smoke actually ran. Add an assertion that an update receipt's `smoke` is None. The field is metadata only (no plan reads `receipt.smoke`), so removal authority is unaffected | New (pre-existing in 19-09) |

No HIGH was raised and no cycle-2 HIGH remains. Both MEDIUMs are pre-existing scope gaps on the update path, not regressions from cefe8a9. The reviewer and the orchestrator found no regression introduced by the replan.

### Agreed Strengths
With a single reviewer there is no cross-reviewer agreement. Its main strengths were:
- Every cycle-2 fix appears in the task action, the tests and the verify gates, not only in the ledgers. Examples: the AST gates on `_build_receipt`/`adopt`, the `inspect.signature` gate on `tool_state`, the `unresolved=unresolved` count gate, and the deque admission test.
- Structure is intact: no same-wave `files_modified` collisions (re-derived by the orchestrator from frontmatter for all 8 waves), all `depends_on` point to earlier waves, and there is no cycle.

### Agreed Concerns
With one reviewer, the priorities are:
1. Guard `update_download` with the same single-basename rule (C3-M1).
2. Stop recording an un-run smoke as `"ok"` in update receipts (C3-M2).

### Divergent Views
None. Only one reviewer ran, and the orchestrator confirmed both findings against the source without correction.

### Cycle history
| Cycle | Commit reviewed | HIGH | Actionable non-HIGH |
|---|---|---|---|
| 1 | 9a492dc (review db26ba9) | 12 | 15 |
| 2 | 368da6a (review 40b51d5) | 2 | 9 |
| 3 | e019192 (this review) | 0 | 2 |

---
## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`), cycle 3. It ran on 2026-10-16 over the 12 plans that cefe8a9 changed.

**Authority.** `drift-guard authority --raw` returned `intel`. `.planning/intel/` lists only CLI entry points, so every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO) under that authority. It is not treated as verified or missing on that basis. Supplementary evidence came from two sources:
- `codegraph explore` (the repo is CodeGraph-indexed), for declarations.
- Grep over `git ls-files`, outside `.planning/`, `.claude/` and `docs/`.

`drift-guard severity` under `intel` gives VERIFIED -> none, MISSING -> needs-acknowledgement (no hardBlock), AMBIGUOUS -> MEDIUM and UNCHECKABLE -> INFO. No verdict produced a hardBlock.

**Scope (delta pass).** Cycles 1 and 2 grounded the earlier token sets. This cycle enumerates the backticked tokens that cefe8a9 newly introduced in the 12 changed plans (19-01, 07, 08, 09, 10, 11, 12, 13, 14, 16, 19, 21), compared with the same plans at `40b51d5`. That gives 176 plan/token pairs and 166 unique tokens. About 60 of these are prose fragments, operators, literal strings or argv examples (`()`, `==`, `"not json"`, UI copy) with nothing to ground.

- **Source evidence: existing declarations verified.**
  - In installer/version_status.py: `resolve_github_release_status` :156, `_version_argv` :238, `_probed_version` :269, `resolve_status` :298, and `probe_output` :322,730. The six forwarding sites are :175,277,317,339,359,415, and the pass call is :724. The plan cites the same lines.
  - In installer/download.py: `is_still_proven` :188 and `link_name` :175.
  - `sha256_file` (installer/checksums.py:55).
  - In installer/engine.py: `install_tool` :136 with `repair` :145, and `postinstall_warning` :255,288. Also `postinstall_warning` in installer/update.py :315.
  - `default_bin_dir` kwarg (installer/app.py:402).
  - `SKILL_HARNESSES` (installer/model.py:113).
  - In installer/skill_lifecycle.py: `SKILL_HARNESS_LABELS` :66 (`"claude": "Claude Code"` :74), `_probe_outputs` :306 (absorbs `OSError`/`RuntimeError`/`SubprocessError`), `HarnessStatus` with `unknown` :17, and None -> `"unknown"` :386-387.
  - In scripts/container-e2e-verify.sh: `exec_tester` :75, the `/home/tester/workspace` checkout :196,262, and `run_setup_as_tester` with `$HOME/.local/bin` first on PATH :247-264.
  - `StrEnum`, `inspect.signature`, `collections.deque`, `pathlib.Path.lstat` and `subprocess.CalledProcessError` are stdlib.
- **No source evidence. All of them are new by design.** None is a hallucinated reference to existing code:

| Cited at | Token(s) | Why absent |
|---|---|---|
| 19-01 | `_MAX_RECEIPT_BYTES`, `ReceiptMethod`, `method_key`, `fingerprint`, `receipts.read/write/receipts_dir` | created by 19-01 (`installer/receipts.py` is new) |
| 19-09, 19-14 | `_build_receipt`, `adopt` | created by 19-09 / 19-14 |
| 19-08 | `tool_state(..., checking=())`, `Evidence(checking=...)` | builder created by 19-08; `Evidence` by 19-03 |
| 19-07, 19-16 | `SkillPackReport`, `SkillPackReport.hosts` | created by 19-07 |
| 19-11, 19-16, 19-21 | `ProjectPackReport`, `.unchecked`, `PROJECT_GLOBAL_MACHINERY`, `inspect_project_pack` | created by 19-11 (19-21 extends) |
| 19-12 | `unresolved: str \| None = None` keyword | added by 19-12 |
| 19-19 | `TESTER_WORKSPACE`, `RECEIPT_PROBE_TOOL`, `assert_receipt_ready_for_removal` | created by 19-19 |
| 19-21 | `_MAX_WALK_DIRS`, module-level `deque` import | created by 19-21 |
| all | 13 new `test_*` names (e.g. `test_adopt_records_the_verified_fingerprint_without_a_second_one`, `test_tool_state_forwards_checking_facts`, `test_resolve_status_forwards_the_unresolved_path_for_volta_and_host_setup`) | new tests the plans create |

**Existence-class notes from this pass (needs-acknowledgement, not counted):**
- `skill_lifecycle.os` (19-11-PLAN.md:164 and 19-21-PLAN.md:103 monkeypatch `os.scandir` through it). installer/skill_lifecycle.py imports `json`, `re`, `shutil` and `subprocess` today (:3-6), but not `os`. The plans' actions use `os.scandir`, which requires a module-level `import os`. That import is implied rather than stated, so it is acknowledged as new.
- 19-21-PLAN.md:72 lists `ProjectPackReport(repos, leftovers, reasons, steps)` without the `unchecked` field that cefe8a9 added in 19-11. This is a stale interface excerpt with no behavioural effect, because 19-21 fills `repos` and 19-11's definition is authoritative.

**Reviewer citations spot-checked:**
- installer/download.py:257-278 (`update_download`: no single-name guard and no `smoke_argv`).
- installer/apps.py:117 ("Updates never smoke the staged CLI").
- tests/test_download.py:1858.
- installer/version_status.py call sites.

All of these match the reviewer's description.

**UNCHECKABLE / skipped.**
- Signatures cannot be asserted under `intel`/grep. Names, declaration lines and call sites only were checked.
- External surfaces are not in the repo: Claude Code `--json` listing shape, GSD 1.16.0 hook surfaces, and uv/pnpm/Volta output.
- No tests, containers or live runs were executed. All checks were read-only.
- Wave/file-overlap check: no two plans in one wave share a `files_modified` entry (all 8 waves, re-derived from frontmatter). All `depends_on` entries point to earlier waves.

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 19`): verdict `consistent`. STATE.md says "Ready to plan" and ROADMAP.md says "Not started" (both rank 0).
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction introduced by cefe8a9.
  - SC3 ("a receipt whose link target no longer matches makes the tool not removable") is unchanged and strengthened by 19-10/19-14's no-receipt and raw-binary truths.
  - SC1 (overtaken pass publishes nothing) and SC2 (`…` checking) are consistent with 19-08's `checking` builder input.
- **Requirement IDs** (ROADMAP.md authority): STATE-01..STATE-07 are each still covered, and no plan cites an ID outside the roadmap.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority):
  - L-19-30 (19-CONTEXT.md:227, added in e019192) matches the plans: `_build_receipt` never fingerprints, adopted receipts have `smoke = null`, deleted receipt = no-receipt case, `unknown` host -> "not checked" only for present harnesses with a fresh report, and `unresolved=` forwarding.
  - D-05 receipt fields (19-CONTEXT.md:44) are unchanged.
- **UI-SPEC copy ↔ plan strings:** the e019192 row `no readable answer from {Harness}` · `cannot read ~/{path}` matches the 19-16 literals exactly (19-16-PLAN.md:27,209).
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
