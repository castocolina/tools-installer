---
phase: 19
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-16T08:06:30Z
plans_reviewed: [19-01-PLAN.md, 19-02-PLAN.md, 19-03-PLAN.md, 19-04-PLAN.md, 19-05-PLAN.md, 19-06-PLAN.md, 19-07-PLAN.md, 19-08-PLAN.md, 19-09-PLAN.md, 19-10-PLAN.md, 19-11-PLAN.md, 19-12-PLAN.md, 19-13-PLAN.md, 19-14-PLAN.md, 19-15-PLAN.md, 19-16-PLAN.md, 19-17-PLAN.md, 19-18-PLAN.md, 19-19-PLAN.md, 19-20-PLAN.md, 19-21-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 19

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-plan-review)

**Review type:** GSD implementation plans, source-grounded, read-only.  
**Coverage:** All 21 plans reviewed against the repository and the locked phase artifacts.

Below, `P/` means `.planning/phases/19-one-tool-state-with-health-plus-receipts/`. Findings concern the prescribed implementation—not claims that unimplemented code has already failed.

## 19-01

**Summary:** A sound persistence foundation, but the proof schema and lock contract need tightening before downstream plans depend on them.

**Strengths**
- Reuses the existing atomic replacement and streaming checksum primitives rather than inventing alternatives (`installer/atomic.py:34-58`, `installer/checksums.py:55-58`).
- Explicit receipt and default-bin sandboxes address host-dependent tests before receipt-writing callers land.

**Concerns**
- **HIGH — Adoption can deadlock on the writer lock.** `P/19-01-PLAN.md:130` requires `write()` to acquire a non-reentrant `threading.Lock`; `P/19-14-PLAN.md:153` requires adoption to hold that same lock while writing. Calling the public writer from adoption hangs.
- **MEDIUM — Required proof fields are optional in reader validation.** `P/19-01-PLAN.md:181` permits missing file hashes and fingerprints and does not explicitly reject boolean schema versions. A file with matching size/mtime but no hash can pass the shortcut prescribed at `:224`, despite the corrupt-receipt prohibition (`P/19-SPEC.md:169-173`).

**Suggestions**
- Specify a private unlocked writer beneath the locked public operations, or explicitly use `RLock`.
- Require a valid target for links and valid hash/size/mtime fields for files; reject `v=True`.
- Add a timed adoption-completion test and malformed type-specific artifact tests.

**Risk assessment: HIGH.** This module supplies destructive-operation proof and synchronization to later plans.

## 19-02

**Summary:** The shared artifact formula is the right consolidation, but lookup compatibility and final-name validation remain incomplete.

**Strengths**
- Moving `cli_spec` into `download.py` respects the existing dependency direction: apps already imports download.
- Keeps raw downloads outside archive-layout proof, preserving the structural guard in `installer/download.py:188-204`.

**Concerns**
- **HIGH — Binding `which=shutil.which` breaks existing monkeypatch isolation.** The action at `P/19-02-PLAN.md:214` captures the function at import time. Existing tests patch `status.shutil.which` and call the function without an explicit lookup (`tests/test_status.py:31-45`, `:209-219`); those tests would instead consult the host PATH. Current code looks it up dynamically (`installer/status.py:45,91`).
- **MEDIUM — Final download names can still traverse directories.** The guard at `P/19-02-PLAN.md:132` rejects only empty, dot and dot-dot names. `bin_name="../other"` or an absolute value survives. Existing `link_name` returns declared `bin_name` unchanged, and installation joins it into destinations (`installer/download.py:176-185,222-229`).

**Suggestions**
- Default `which` to `None` and resolve the module lookup at call time.
- Apply a shared single-basename validation to the final download name, including explicit `bin_name`.
- Test slashed and absolute overrides, not just shipped registry values.

**Risk assessment: HIGH.** The lookup issue immediately affects validation; path validation affects both installation and removal authority.

## 19-03

**Summary:** Well-scoped pure logic with clear precedence and reason-order contracts.

**Strengths**
- The table directly covers the locked precedence and broken-plus-outdated behavior (`P/19-SPEC.md:32-35`).
- Explicitly preserves absent-tool notes while dropping present-only facts, supporting downstream skill-pack reporting.
- Reason ordering matches the UI contract (`P/19-UI-SPEC.md:216-217`).

**Concerns**
- No independent blocking defect found.

**Suggestions**
- Keep the full declaration-order assertion and absent-note tests as specified; avoid replacing them with a handful of illustrative cases.

**Risk assessment: LOW.** No I/O or mutation, and the contract is testable independently.

## 19-04

**Summary:** A strong batching adapter that preserves existing consumers without multiplying native queries.

**Strengths**
- Path-keyed parsing handles partial-success output without positional misattribution.
- The synthesized response formats accommodate existing owner and package-membership consumers (`installer/install_ownership.py:181-195,251-266`).
- Per-argv memoization addresses repeated declared-package and rpm-ostree probes.

**Concerns**
- No independent blocking defect found.

**Suggestions**
- Preserve tests distinguishing ambiguous ownership from “this package owns this path”; the existing consumers intentionally answer different questions.
- Keep the uncollected-path refusal explicit.

**Risk assessment: LOW.** The planned adapter is bounded and fail-closed, with representative OS-family fixtures.

## 19-05

**Summary:** Correctly fixes uv’s directory evidence and introduces clean update refusals, but Volta precedence fails when owner directories overlap.

**Strengths**
- Uses the tools directory rather than the colliding uv bin-directory guess.
- Covers owner labels, removal hints and update refusal together.
- Keeps verified host-setup ownership behind both a probe and path attribution.

**Concerns**
- **HIGH — Volta can lose to an installer candidate before its branch runs.** `P/19-05-PLAN.md:112` inserts Volta handling after the active-candidate return. If the managed bin directory is `$VOLTA_HOME/bin`, attribution can include both owners. An installer artifact candidate then returns first. The relevant mechanisms are the managed-directory prefix (`installer/ownership.py:445`), multi-owner attribution (`:467-483`), early candidate return (`:615-632`) and artifact candidate creation (`:958-965`).

**Suggestions**
- Define the overlap policy explicitly and resolve verified Volta shim evidence before the generic candidate return.
- Add a fixture containing both a Volta shim and an installer artifact candidate.

**Risk assessment: MEDIUM.** Most owner fixes are sound; this edge can still produce wrong mutation routing.

## 19-06

**Summary:** Carefully addresses the terminal synchronizer’s actual write sites and makes the pnpm check reusable without another query.

**Strengths**
- Accounts for Konsole state creation, profile/config writes, zsh-absent reversal and `.zshrc` repair (`installer/terminal_shell.py:307-311,347-364,399-412,424,444`).
- Whole-tree path/bytes/mtime tests are substantially stronger than checking only expected output files.
- The pnpm refactor reaches the existing production caller (`installer/pnpm_globals.py:593`).

**Concerns**
- No independent blocking defect found.

**Suggestions**
- Retain the zsh-absent and Konsole tests; these protect the less obvious mutation paths.

**Risk assessment: LOW.** The plan reuses existing transformations and directly tests read-only behavior.

## 19-07

**Summary:** Structured plugin evidence and ordered repair steps are improvements, but malformed-input handling and marketplace cleanup conditions need clarification.

**Strengths**
- Replaces substring presence checks with canonical structured entries.
- Explicitly enables or installs the canonical copy before removing alternatives.
- Conservatively suppresses project uninstall steps when their working directory cannot be identified.

**Concerns**
- **HIGH — Marketplace cleanup can outlive suppressed uninstall steps.** `P/19-07-PLAN.md:171-172` suppresses a project uninstall without a valid path, but marketplace removal is described in terms of copies “being removed.” It must require executable preceding uninstall steps—not merely duplicate classification.
- **MEDIUM — Scope values are not closed before entering argv.** The parser accepts arbitrary scope strings (`:121`), and uninstall commands use that value after `-s` (`:155`). This violates the plan’s own output-validation promise.
- **MEDIUM — Parser and test disagree about malformed entries.** The test requires non-boolean `enabled` to produce unknown (`:113`), while the action says to skip invalid entries (`:121`). A malformed singleton then becomes absent.

**Suggestions**
- Offer marketplace removal only when every dependent copy has an addressable preceding uninstall step.
- Validate executable scopes against `user`, `project` and `local`.
- Choose one malformed-entry policy and align the implementation and tests; unknown is safer than fabricated absence.

**Risk assessment: HIGH.** These steps become executable configuration actions in Phase 20.

## 19-08

**Summary:** The concurrency tests are strong, but the availability helper cannot satisfy the specified brew transition, and platform/cache consistency needs an explicit contract.

**Strengths**
- Deterministic barriers cover invalidation, overlapping subsets and shared flights.
- Preserves a single publication point and fail-closed generation reads, building on the existing reader ordering (`installer/version_status.py:523-542`).

**Concerns**
- **HIGH — `unavailable_reason` cannot produce the required initial UNAVAILABLE state.** The builder uses it at `P/19-08-PLAN.md:130`, while `:206` expects brew-only UNAVAILABLE → MISSING. But `installer/resolve.py:131-138,171-195` deliberately evaluates potential support with `has_brew=True`.
- **MEDIUM — Concurrent passes can mix platform values.** The plan updates shared `self._platform` while different-set passes may overlap. Existing helpers read that shared field separately for inventory, outdated evidence and resolution (`installer/version_status.py:619-624,706-732`).
- **MEDIUM — A fresh manager snapshot can conceal brew’s appearance.** `_load_or_query_snapshot` returns a fresh cached snapshot before reaching brew-aware queries (`installer/version_status.py:613-624`). The proposed transition test must include this cache shape.

**Suggestions**
- Separate current method availability from potential platform support, with an explicit missing-manager explanation.
- Capture one immutable pass-local platform and pass it through helpers.
- Refresh manager evidence when manager availability changes.

**Risk assessment: HIGH.** This is the central producer of every state claim.

## 19-09

**Summary:** The shared writer and two integration points are appropriate, but write failure over an existing receipt needs a truthful outcome.

**Strengths**
- Records after successful execution and before postinstall.
- Preserves receiptless kinds and avoids claiming ownership merely by updating a foreign manager package.
- Matches the existing successful update seam (`installer/update.py:303-309`).

**Concerns**
- **MEDIUM — “No receipt exists” is false when rewriting an old receipt fails.** `P/19-09-PLAN.md:30` promises no receipt after write failure, but repair and update can already have one (`:164,171,208`). Atomic replacement failure leaves the old receipt while the artifacts may already have changed (`installer/engine.py:181-200`, `installer/update.py:329-341`).

**Suggestions**
- Specify the existing-receipt failure policy explicitly.
- Test successful repair/update followed by receipt-write failure.
- Keep the result successful with an accurate stale-proof warning; do not claim the old receipt proves new bytes.

**Risk assessment: MEDIUM.** Fail-closed behavior is available, but the current outcome specification is inaccurate.

## 19-10

**Summary:** Correctly places proof below both uninstall interfaces, but several concrete safety and integration defects remain.

**Strengths**
- Rejects corrupt-receipt fallback and rehashes before deletion.
- Uses one shared remover rather than separate CLI/TUI interpretations.

**Concerns**
- **HIGH — Path-only intersection permits artifact-type escalation.** `P/19-10-PLAN.md:125` authorizes paths but trusts the receipt’s type. A forged directory artifact at a raw-binary path can pass directory matching and reach recursive removal (`installer/uninstall.py:416-425`).
- **HIGH — Drift outside the allowed intersection is ignored.** The same algorithm checks only filtered candidates, contradicting the whole-tool drift rule (`P/19-10-PLAN.md:26`) and the full-receipt health check in `P/19-14-PLAN.md:115`.
- **HIGH — The prescribed TUI expression accesses a nonexistent field.** `P/19-10-PLAN.md:200` uses `self._by_key[key].tool`, but `_UninstallEntry` has no `tool` field (`installer/wizard_app.py:875-882`). The same map also contains environment pseudo-rows (`:993-1000,1418-1440`).

**Suggestions**
- Authorize `(path, expected kind)` pairs, not paths alone.
- Reject removal if any receipt artifact drifts before intersecting authorized artifacts.
- Derive selected tools from tool rows using non-environment IDs, or retain an optional tool explicitly.
- Test tool-only, environment-only and mixed TUI selections.

**Risk assessment: HIGH.** These defects affect recursive deletion authority and basic TUI uninstall execution.

## 19-11

**Summary:** Broad, well-documented global-leftover coverage, with one remaining resource-bound weakness.

**Strengths**
- Covers machinery and hooks across all nine harness homes.
- Names the shared Codex/Kimi root ambiguity instead of silently assigning certainty.
- Offers the pack’s uninstaller rather than deleting harness machinery directly.

**Concerns**
- **MEDIUM — The read cap is only a pre-read stat check.** `P/19-11-PLAN.md:173` follows `stat()` with unrestricted `read_bytes()`. A growing or replaced file can bypass the advertised cap; the test at `:163` covers only an already oversized file. These are mutable HOME-relative surfaces (`installer/skill_lifecycle.py:201-216`).

**Suggestions**
- Read at most `limit + 1` bytes from the opened file and reject excess.
- Keep stat as an optimization, not the actual bound.

**Risk assessment: MEDIUM.** Detection is read-only, but it runs on a latency-sensitive worker over mutable files.

## 19-12

**Summary:** Correctly integrates owner evidence, but looking through PATH shims does not eliminate shim-based false presence.

**Strengths**
- Reuses one native index and uv-directory query per pass.
- Preserves unresolved invocation paths for Volta and host-setup versions.
- Suppresses irrelevant binary-owner notes for skill packs.

**Concerns**
- **MEDIUM — Filesystem presence fallback can rediscover the shim just rejected by `which`.** `P/19-12-PLAN.md:112-113` injects looked-through lookup, but the implicit artifact check from 19-02 independently accepts `path.is_file()`. The existing declared-bin fallback does likewise (`installer/status.py:98-107`); installer shims are regular files (`installer/guards.py:140-142,389-392`).

**Suggestions**
- Exclude installer-owned shims from all presence paths, including declared and implicit directories.
- Add a raw-download fixture whose managed-bin path contains only a shim and no real binary.

**Risk assessment: MEDIUM.** Owner attribution improves, but presence can still disagree with it.

## 19-13

**Summary:** A coherent migration of catalog decisions to state, with strong pending/error/availability checks.

**Strengths**
- Replaces independent presence decisions currently concentrated in `installer/catalog_tui.py:479-517,647-654`.
- Tests full-catalog refreshes, generation-induced checking and live selectability.
- Preserves cursor behavior through the existing browser rebuild mechanism (`installer/tool_browser.py:187-197`).

**Concerns**
- No independent blocking defect found beyond the inherited availability and shim-presence issues in 19-08 and 19-12.

**Suggestions**
- Assert the complete Health sort order, not just a pair of states; `StrEnum` lexical ordering is not precedence ordering.
- Carry the upstream availability fixes into the live-selectability fixtures.

**Risk assessment: MEDIUM.** The UI migration is sound but depends on accurate service evidence.

## 19-14

**Summary:** Good end-to-end drift coverage, but adoption’s synchronization and digest binding are not implementation-safe yet.

**Strengths**
- Tests changed links across install, state and removal.
- Rechecks that no receipt appeared before adoption.
- Computes removability after adoption.

**Concerns**
- **HIGH — Nested acquisition of the non-reentrant receipt lock can hang adoption.** `P/19-14-PLAN.md:153` conflicts with the locked writer prescribed by `P/19-01-PLAN.md:130`.
- **HIGH — The verified digest must be bound to the exact artifact adopted.** `P/19-14-PLAN.md:155` separately hashes, compares and adopts, while `fingerprint()` independently hashes (`P/19-01-PLAN.md:210`). Replacement between comparison and fingerprint acquisition can validate replacement bytes against themselves.
- **MEDIUM — Negative memoization ignores changed release evidence.** A mismatch cached solely by path/size/mtime remains negative after cached tag/digests change (`installer/version_status.py:181-190`).

**Suggestions**
- Resolve lock ownership explicitly.
- Compare the expected release digest to the same immutable artifact hash passed to adoption, then revalidate that artifact under the lock.
- Cache observed hashes, or include expected asset/digest in the negative-memo key.
- Add a replacement race before fingerprint acquisition.

**Risk assessment: HIGH.** Adoption grants removal proof automatically and must not hang or bind proof to different bytes.

## 19-15

**Summary:** A well-aligned state-driven presentation plan with explicit escaping and update refusal behavior.

**Strengths**
- Replaces the independent detail builders currently used at `installer/catalog_tui.py:656-685`.
- Preserves the stale-version and policy qualifications while making Health the primary mark.
- Escaping tests directly protect machine-derived reasons and configuration text.

**Concerns**
- No independent blocking defect found.
- **LOW — Rendering still reads default-shell state outside ToolState.** This is explicitly permitted by the plan (`P/19-15-PLAN.md:72`), but it is an exception to the “one state” presentation claim, not complete elimination of live render-time evidence.

**Suggestions**
- Keep that exception narrowly documented; do not use it as precedent for adding other probes to rendering.
- Preserve the planned migration of test doubles when `refresh` changes return type in 19-18.

**Risk assessment: LOW.** Main risks are integration volume and inherited evidence defects.

## 19-16

**Summary:** Most evidence wiring is sensible, but the proposed pnpm fix does not repair the actual co-install contract.

**Strengths**
- Uses the same dry-run terminal synchronizer and cached package inventory.
- Correctly anchors incomplete groups on their declaring package (`installer/pnpm_globals.py:505-522`).
- Preserves duplicate reasons and steps even for absent packs.

**Concerns**
- **HIGH — `pnpm add --global puppeteer` is not the existing group repair.** The exact step at `P/19-16-PLAN.md:148,157` installs missing peers independently. The existing executor deliberately installs the dependent and peers as one comma-separated group, includes build allowances and version pins, and runs smoke checks (`installer/executors.py:485-507,547-548`). Installing only the missing package can leave mmdc isolated from puppeteer and omit the browser-build allowance.
- **MEDIUM — Probe failure silently becomes absence of configuration facts.** `P/19-16-PLAN.md:121,198` drops failures. A previously misconfigured present tool can consequently look OK without a note explaining that configuration was not checked.

**Suggestions**
- Build the repair from the declaring node method’s existing executor contract rather than a separate missing-package command.
- Test that reconfiguration restores grouping, build allowances and smoke behavior.
- Retain a checking/stale/failed-check note when secondary evidence cannot be collected.

**Risk assessment: HIGH.** Phase 20 would execute a step that does not necessarily solve the condition it advertises.

## 19-17

**Summary:** The compositor-based layout validation is excellent, but the prescribed text truncation and shared-widget rendering introduce real regressions.

**Strengths**
- Tests actual topmost widgets rather than merely examining render buffers.
- Covers the Rule change’s blast radius and every mark on every tier.
- Keeps the fixed row budget explicit.

**Concerns**
- **HIGH — `truncate(2 * width)` does not guarantee two wrapped rows.** The action at `P/19-17-PLAN.md:147` truncates total cell length before word wrapping. Rich’s implementation only limits total text width (`.venv/lib/python3.12/site-packages/rich/text.py:859-880`). Word-boundary wrapping can still produce three health rows. A read-only reproduction at width 20 using repeated `"abcdefghijk "` produced four rows including identity; the final ellipsis was on the clipped fourth row.
- **HIGH — Unconditional markup parsing breaks plain-text adapters.** The same action prescribes `Text.from_markup` for the shared browser, but Uninstall explicitly sets `detail_is_markup=False` (`installer/wizard_app.py:1137-1153`). Existing handling respects that flag (`installer/tool_browser.py:344-348`). Paths containing brackets must remain literal there.

**Suggestions**
- Wrap to the actual content width first, retain two rendered lines, and ellipsize the final retained line.
- Preserve `detail_is_markup=False` and section-row behavior.
- Add word-boundary, embedded-newline and bracketed-path cases, not only long unbroken strings.

**Risk assessment: HIGH.** The prescribed implementation can hide the very reasons the layout work is intended to expose.

## 19-18

**Summary:** Correctly completes consumer migration and live-platform routing, though the owner-resolution extraction needs a clearer internal API.

**Strengths**
- Addresses actual frozen-platform consumers (`installer/execute_screen.py:498-510`, `installer/update.py:478-484`).
- Keeps repair restricted to the existing ownership-broken case, avoiding automatic overwrite of receipt drift.
- Explicitly updates refresh overrides alongside the base return type.

**Concerns**
- **MEDIUM — “Extract, don’t copy” is underspecified for fresh versus batched resolution.** `P/19-18-PLAN.md:166` requires a public fresh-inventory `resolve_owner(tool)` while also reusing it in a pass that must retain one shared inventory/index. Calling the public operation per tool would defeat batching; copying its internals would duplicate the evidence contract.

**Suggestions**
- Specify one private evidence-based resolver used by both operations.
- Keep fresh inventory acquisition in the public mutation-time operation and batch acquisition in refresh.
- Add a test proving fresh owner resolution does not change the pass’s one-native-query guarantee.

**Risk assessment: MEDIUM.** The intended behavior is correct, but the extraction seam needs enough precision to avoid reintroducing duplicated probes.

## 19-19

**Summary:** Useful integration assertions and documentation, but removal success can be vacuous in a standalone or category-filtered workflow.

**Strengths**
- Adds receipt assertions at the real install/uninstall boundary rather than pretending host-side shell tests prove executors.
- Preserves category-filtered pass1 behavior.
- Places removal verification immediately after the actual uninstall step (`scripts/container-e2e-verify.sh:449-456`).

**Concerns**
- **MEDIUM — Absence after uninstall does not prove the probe existed before uninstall.** The new pass2 assertion checks only absence (`P/19-19-PLAN.md:109-112`). Existing step 1 checks aggregate failures, not specifically yq and its receipt (`scripts/container-e2e-verify.sh:428-447`). A skipped/manual probe could make removal pass without exercising receipt-proven deletion.

**Suggestions**
- Assert both the probe binary and a valid receipt immediately before pass2 uninstall.
- Keep the post-uninstall absence check.
- Treat the real container run as the phase gate; extracted-function tests remain plumbing tests.

**Risk assessment: MEDIUM.** The implementation chain is covered only if the integration fixture establishes its preconditions.

## 19-20

**Summary:** The deletion scope is appropriate and reaches the known constructor callers.

**Strengths**
- Removes the whole-catalog presence sweep currently performed by `_rederive_installed` (`installer/wizard_app.py:3005-3020`).
- Covers both navigation and install-close callers (`:2776-2780,2940-2943`).
- Avoids leaving unused forwarding parameters.

**Concerns**
- No independent blocking defect found.

**Suggestions**
- Keep a regression case for returning from successful uninstall: removal of the sweep is safe only because invalidation and refresh replace its former responsibility.
- Validate behavior through the published state, not merely constructor signatures.

**Risk assessment: LOW.** Primarily mechanical, with clear replacement behavior.

## 19-21

**Summary:** Bounded discovery and pinned per-repo commands are appropriate, but “non-empty directory” is not sufficient evidence of an actual framework install.

**Strengths**
- Keeps execution project-local and deferred to Phase 20.
- Distinguishes an absent runtime from an empty damaged install.
- Bounds traversal and rejects symlink descent for discovered child directories.

**Concerns**
- **MEDIUM — Unrelated harness content can make a damaged GSD install count as real.** `P/19-21-PLAN.md:115` accepts VERSION plus any non-empty skills/commands directory. A stale VERSION beside an unrelated `superpowers` skill passes even if all GSD machinery is gone. The global scan already distinguishes `gsd-*` from unrelated entries; project detection should be equally specific.
- **MEDIUM — The stated directory cap does not explicitly bound enumeration or queued work.** `:114` caps visited directories, but a breadth-first implementation can still enumerate and enqueue an arbitrarily large root before hitting that count.

**Suggestions**
- Require a GSD-owned command/skill or validated manifest entry, not arbitrary directory content.
- Test stale VERSION plus unrelated skills.
- Bound entries admitted to the traversal queue and explicitly reject symlinked configured roots.

**Risk assessment: MEDIUM.** These gaps can produce false presence and refresh latency on large home trees.

## Cross-plan priorities

**Status: Issues Found — revise before execution.**

Fix these first:

1. **Removal authority and TUI integration:** authorize artifact types, check whole-receipt drift, and replace the nonexistent `_UninstallEntry.tool` access.
2. **Adoption:** resolve nested locking and bind the release digest to the exact adopted fingerprint.
3. **State availability:** distinguish current method availability from `platform_could_support`.
4. **Configuration repair:** reuse the real pnpm co-install contract.
5. **Shared detail rendering:** preserve plain-text adapters and truncate rendered lines rather than total text length.
6. **Validation compatibility:** avoid capturing `shutil.which` before existing monkeypatches.

The plans otherwise provide substantial coverage of STATE-01..07. The main remaining risks are not missing features; they are contracts that look complete in prose but fail at their existing source seams.

**Overall risk: HIGH until those blockers are resolved.** No repository files were changed, and no installer or host-mutating commands were run. Full tests and container e2e were not run; only source inspection and a small read-only Rich rendering reproduction were performed.

---

## Consensus Summary

One reviewer ran: the `opencode-plan-review` instance (`router-env/my-plan-review`, pinned). The consensus gate does not engage with a single reviewer, so every HIGH it raised counts. The review is source-grounded: it cites `file:line` evidence throughout and carries neither the `[reviewed-without-source-citations]` marker nor the `[reviewed-without-repo-access]` marker. It covers all 21 plan ids.

The orchestrator checked each HIGH against the current PLAN.md files (at `9a492dc`) and the source. None was already resolved in the plans, and none was refuted:

| # | Plan(s) | HIGH | Orchestrator check |
|---|---|---|---|
| H1 | 19-01, 19-14 | `adopt` holds the module lock and then calls `write`, which takes the same non-reentrant `threading.Lock` | Confirmed. 19-01-PLAN.md:130 locks `write`, and 19-14-PLAN.md:153 calls it "under the module lock". No plan names an `RLock` or an unlocked inner writer. Raised in two sections and counted once |
| H2 | 19-02 | `which: ... = shutil.which` binds at definition time and bypasses `monkeypatch.setattr(status.shutil, "which", ...)` | Confirmed. 19-02-PLAN.md:214 sets that default, and tests/test_status.py:34,44,64,75,88,113,123,142,154,179 patch the module attribute |
| H3 | 19-05 | Volta is attributed after the single-active-candidate return, so an overlapping installer candidate wins first | Confirmed as written (19-05-PLAN.md:112; installer/ownership.py:614-632). It needs the managed bin dir to overlap `$VOLTA_HOME/bin` |
| H4 | 19-07 | `marketplace_remove` is offered while a project copy's uninstall step was suppressed (no usable `projectPath`) | Confirmed. 19-07-PLAN.md:171 says "being removed" and :172 suppresses the step but keeps the reason. Nothing ties the two together |
| H5 | 19-08 | `unavailable_reason` cannot yield UNAVAILABLE for a brew-only tool while `has_brew=False` | Confirmed. installer/resolve.py:131-133 returns None when `platform_could_support`, which forces `has_brew=True` (:195). The test at 19-08-PLAN.md:206 expects UNAVAILABLE after pass 1 |
| H6 | 19-10 | The removal intersection compares paths only, so a receipt's artifact `type` can turn a raw file path into an `rmtree` | Confirmed. 19-10-PLAN.md:125 builds `allowed` from `a.path` only, and installer/uninstall.py:416-425 removes a directory recursively |
| H7 | 19-10 | Drift is checked only on intersected candidates, which contradicts the whole-tool drift truth | Confirmed. 19-10-PLAN.md:26 (truth) and :125 (action) disagree |
| H8 | 19-10 | `self._by_key[key].tool` does not exist | Confirmed (existence class). `_UninstallEntry` (installer/wizard_app.py:870-882) has no `tool` field. The claim at 19-10-PLAN.md:82 that "each row carries its `tool`" is false, and the map also holds environment rows |
| H9 | 19-14 | The release-digest comparison is not bound to the artifact passed to `adopt` | Partially confirmed. 19-14-PLAN.md:155 hashes, compares and then calls `adopt(...)` without saying which `artifact` it passes, and the 19-14-PLAN.md:141 test builds it with a separate `fingerprint`. The fix is to fingerprint once and compare that `sha256` |
| H10 | 19-16 | `pnpm add --global <missing>` is not the co-install repair | Confirmed. installer/executors.py:486-507 installs `[npm_pkg, *co_install]` as one comma-joined group with `--allow-build` and pins, and its comment names separate installs as the failure mode. 19-16-PLAN.md:148,157 prescribe the separate install |
| H11 | 19-17 | `Text.truncate(2 * width)` does not bound word-wrapped output to two rows | Confirmed by mechanism. Truncation is by total cell length and wrapping happens later. The reviewer reproduced it without writing to the repo |
| H12 | 19-17 | `Text.from_markup` applied to every adapter breaks `detail_is_markup=False` (Uninstall) | Confirmed. installer/tool_browser.py:345-348 and installer/wizard_app.py:1152 against 19-17-PLAN.md:147 |

### Agreed Strengths
With a single reviewer there is no cross-reviewer agreement. Its main strengths were:
- 19-03 (pure `tool_health` table), 19-04 (batched native index), 19-06 (dry-run terminal drift with whole-tree tests), 19-13, 19-15 and 19-20 are low risk.
- The deterministic barrier tests in 19-08.
- The compositor-based layout test in 19-17.

### Agreed Concerns
With one reviewer, the cross-plan priorities stand as the reviewer ranked them:
1. Removal authority (19-10 H6-H8).
2. Adoption locking and digest binding (H1, H9).
3. Availability in the state builder (H5).
4. The pnpm group repair (H10).
5. Shared detail rendering (H11, H12).
6. The `which` default binding (H2).

### Divergent Views
None. Only one reviewer ran.

---
## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). It ran on 2026-10-16 over all 21 plans at `9a492dc`.

**Authority.** `drift-guard authority --raw` returned `intel`. `.planning/intel/` lists only CLI entry points, so under that authority every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO). It is not treated as verified or missing on that basis. Supplementary evidence came from two sources:
- `codegraph explore` (the repo is CodeGraph-indexed), for declarations.
- Grep over `git ls-files`, outside `.planning/`, `.claude/` and `docs/`.

`drift-guard severity` under `intel` gives VERIFIED -> none, MISSING -> needs-acknowledgement (no hardBlock), AMBIGUOUS -> MEDIUM and UNCHECKABLE -> INFO. No verdict produced a hardBlock.

**Enumeration.** Every backticked token in the 21 PLAN.md files was enumerated if it had a symbol shape (`module.func`, `Class.attr`, `path::name`, `name()`, snake/camel identifiers), a path shape or a `--flag` shape, and was de-duplicated per name. That gave 1083 distinct tokens:
- 130 sit in a plan's `artifacts` list and were excluded as new by design.
- Of the remaining 953, 512 have source evidence (a declaration or reference, an existing path or an existing flag).
- 441 were not found. Of these, 332 are new test names that the plans create, 18 are runtime home paths (`~/...`), and 91 are classified in the table below.

**Line citations.** 112 `` `name` (`:N`) `` citations were checked against the cited file. 85 match within ±3 lines and 4 point into new files (`tests/test_tool_health.py`, `tests/test_layout_80x20.py`). The other 23 fall into three groups:
- A range whose start is a comment or decorator, with the declaration inside the range. Examples: `UNMANAGEABLE_OWNERS` :109-122 -> 122, `method_removal_command` :1435-1470 -> 1454, `_inst_cell` :479-517 -> 494, `cmd_pass2` :405-481 -> 422.
- A citation that points at a call site inside the named function. Examples: `show_view` (:2778) is the `_rederive_installed` call inside `show_view` at 2762, and `_install_closed` (:2941) is the same call inside `_install_closed` at 2898.
- Counts that the regex misread as lines ("18 D-04", "19 public-reader sites").

Only one citation has a stale range: 19-12-PLAN.md:75 gives `resolve_status` (`:150-340`), but the function is declared at installer/version_status.py:298. The name is right and only the range is stale (LOW, no behavioural impact).

Declarations spot-verified with `codegraph explore`:
- `still_removable` and `plan_removal` (installer/uninstall.py:128,141).
- `INSTALL_STATE_HARNESS_DIRS` and `inspect_status` (installer/skill_lifecycle.py:206,429).
- `inspect_skill_packs` (:413).
- `attribute_path` (installer/ownership.py:467).
- `unavailable_reason` and `platform_could_support` (installer/resolve.py:131,171).
- `HOST_SETUPS` (installer/host_setup.py:27).
- `_parse_skill_lifecycle` (installer/model.py:581).
- `save_settings` (installer/settings.py:90).
- `incomplete_install_groups` (installer/pnpm_globals.py:489).
- `atomic_write_bytes` and `atomic_write_text` (installer/atomic.py:34,56). Line 42 is the resolve-the-symlink-then-replace behaviour that 19-01 relies on.
- `is_installed` (installer/status.py:63).
- `cli_spec` (installer/apps.py:56).
- `link_name` and `is_still_proven` (installer/download.py:176,188).
- `_sync_konsole` (installer/terminal_shell.py:269).
- `install_tool` (installer/engine.py:136).
- `refresh` (installer/version_status.py:690).

Existing tests that the plans name for replacement or migration all exist at the cited lines, for example tests/test_catalog_tui.py:1881,1934,1966,2077,2124 and tests/test_wizard_app.py:6578.

**Existence-class findings from this pass (needs-acknowledgement):**
- 19-10-PLAN.md:82,200: `_UninstallEntry` has no `tool` field (installer/wizard_app.py:870-882). This confirms reviewer HIGH H8.

Not-found tokens and why they are absent. None is a hallucinated reference to existing code:

| Cited at | Token(s) | Why absent |
|---|---|---|
| 19-01, 19-02, 19-08 | `sandboxed_receipts`, `sandboxed_bin_dir`, `sandboxed_skill_home` | new conftest fixtures (19-01, 19-08) |
| 19-04:148 | `NativeIndex.__call__` | created by 19-04 |
| 19-05:191, 19-05:82 | `_HOST_SETUP_OWNERS`, `VOLTA_HOME` | new dict (19-05) and the Volta environment variable (external) |
| 19-07 | `ClaudeEntry`, `_claude_entries`, `plugin_enable`, `plugin_uninstall`, `marketplace_remove`, `skill_install`, `FrozenInstanceError` | created by 19-07 (`ConfigStepKind` values); `dataclasses.FrozenInstanceError` is stdlib |
| 19-07:80 | `projectPath`, `installPath`, `installedAt`, `lastUpdated`, `projectEnabled`, `mcpServers` | keys of Claude Code's `installed_plugins.json` (external) |
| 19-08 | `Health.*`, `BROKEN_SHIM_REASON`, `_states`, `self._states`, `service._states`, `_inflight` | created by 19-03 and 19-08 |
| 19-11 | `_GSD_RUNTIME_IDS`, `_GSD_HOOK_SCRIPT_RE`, `_GSD_TOML_MARKER_RE`, `PROJECT_SHARED_GLOBAL_DIRS`, `_gsd_hooks_registered`, `project_pack_global_uninstall`, `project_pack_install` | created by 19-11 and 19-07 |
| 19-11 | `hooksSurface`, `configHome`, `--kimi`, `--kimi-code`, `.gemini/antigravity`, `.config/kilo`, `.config/opencode`, `.codeium/windsurf`, `.agents/skills`, `.gemini/config/{skills,agents}`, `.codex/agents/gsd-x` | GSD 1.16.0 surface and harness home directories (external) |
| 19-12, 19-14, 19-15, 19-16 | `ownership_notes`, `version_notes`, `ToolState.reasons`, `ToolState.removable`, `state.skill_hosts`, `state.unconfigured`, `_TERMINAL_ROWS`, `SkillHostStatus.reasons/steps`, `pnpm_group_install` | created by 19-08, 19-12 and 19-16 |
| 19-15:141 | `cell_len` | `rich.cells.cell_len` (dependency) |
| 19-17, 19-18 | `FrozenStateService.publish`, `BrowserAdapter.empty_detail` | created by 19-15 (tests/state_doubles.py) and 19-17 |
| 19-19 | `_PHASE_19_REQUIRED`, `receipt_check_applies`, `TRACER_RECEIPT_*` | created by 19-19 |
| 19-11, 19-21 | `os.scandir` | stdlib |
| 19-21:74,155 | `/gsd-update`, `gsd-core/VERSION`, `--claude` | GSD runtime layout and flags (external) |
| all plans | `--no-verify`, `--bin` | git and uv flags (external) |
| 19-02, 19-04, 19-05, 19-09, 19-10, 19-21 | `HOME/.local/bin/yq`, `/usr/bin`, `tmp/volta/bin/pnpm`, `bin/rg`, `home/git/...`, `a/b`, `../x` | fixture paths in new tests |

**UNCHECKABLE / skipped.**
- Signatures (argument lists, return types) cannot be asserted under `intel`/grep. Names and declaration lines only were checked.
- External surfaces are not in the repo:
  - GSD 1.16.0's `hooksSurface`/`configHome` and its runtime ids.
  - Claude Code's `claude plugin` argv and `installed_plugins.json` shape.
  - pnpm, uv, Volta, dpkg, pacman and rpm-ostree output formats.
  - The Rich wrapping internals beyond the reviewer's reproduction.
- No tests, containers or live runs were executed. The fact-drift and source checks were read-only.
- Wave/file-overlap check: no two plans in one wave share a `files_modified` entry (all 8 waves checked).

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 19`): verdict `consistent`. STATE.md says "Ready to plan" and ROADMAP.md says "Not started" (both rank 0).
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction. All five ROADMAP criteria are carried by plan truths:
  - SC1 by 19-03 and 19-08.
  - SC2 by 19-13, 19-15 and 19-17 (legend widths 78/78/77 against the 78×3 budget).
  - SC3 by 19-09, 19-10 and 19-14.
  - SC4 by 19-04, 19-05, 19-08 and 19-12.
  - SC5 by 19-07, 19-11, 19-16 and 19-21.

  The ROADMAP wave annotations (W1-W8) match each plan's `wave:` frontmatter, and the roadmap lists 21 plans, matching the 21 files.
- **Requirement IDs** (ROADMAP.md authority): STATE-01..STATE-07 each appear in at least one plan's `requirements:`, and no plan cites an ID outside the roadmap.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority): one advisory finding.
  - **D-12 body vs plan usage:** 19-CONTEXT.md:80 says "The uv owner dir comes from `uv tool dir --bin`". 19-05-PLAN.md:25,134,150 use `uv tool dir` (the tools dir) and explicitly not `--bin`. The plans follow the later CONTEXT Ledger L-19-01 (19-CONTEXT.md:199: "`uv tool dir --bin` returns `~/.local/bin` and resolves no owner"), which amends D-12. The authority is CONTEXT.md, which contradicts itself. To collapse to one source of truth, annotate D-12 as superseded by L-19-01. No plan change is needed.
  - CONTEXT D-02, D-03, D-04 and D-06 cite pre-Phase-17/18 line numbers (for example `version_status.py:677-771` for `refresh`, now :690). The plans cite current lines, and the fact asserted (which function) is the same. This is not drift.
  - D-05 ("installer/receipts.py is the only new module") holds. The only new `installer/` file in any `files_modified` is `installer/receipts.py`; the other new files are tests.
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
