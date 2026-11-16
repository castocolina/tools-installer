---
phase: 18
cycle: 3
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-15T13:46:42Z
plans_reviewed: [18-01-PLAN.md, 18-02-PLAN.md, 18-03-PLAN.md, 18-04-PLAN.md, 18-05-PLAN.md, 18-06-PLAN.md, 18-07-PLAN.md, 18-08-PLAN.md, 18-09-PLAN.md, 18-10-PLAN.md, 18-11-PLAN.md, 18-12-PLAN.md, 18-13-PLAN.md, 18-14-PLAN.md, 18-15-PLAN.md, 18-16-PLAN.md, 18-17-PLAN.md, 18-18-PLAN.md, 18-19-PLAN.md, 18-20-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 18 (convergence cycle 3 of 3, final)

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-plan-review)

# Phase 18 — Final Convergence Review

**Document type:** GSD implementation plans  
**Coverage:** All **20/20** plans reviewed against on-disk plans and relevant source.  
**Citation convention:** `18-xx-PLAN.md` refers to `.planning/phases/18-registry-truth-and-drift-guard/18-xx-PLAN.md`.

“Resolved” below means **resolved in the implementation instructions and planned tests**, not implemented or proven passing.

## 18-01

**Summary:** The schema change is cohesive: closed keys, required dates, registry seeding, fixtures and authoring guidance land together.

- **Strength:** The closed-key check follows existing structural validation rather than accidentally treating `os` and `arch` as method parameters. Source: `installer/model.py:656–666`.
- **Cycle-2 MEDIUM — FULLY RESOLVED:** The revised helper seeds only tool tables without their own `verified` key (`18-01-PLAN.md:170`). Explicit invalid-date fixtures therefore reach the loader instead of failing as duplicate TOML keys; the loader currently reads each parsed tool row at `installer/model.py:644–650`.
- **Concerns:** No additional blocking concern identified.
- **Suggestion:** Keep the missing-date fixture explicitly opted out of helper seeding, as specified.
- **Risk:** **LOW** — broad fixture impact, but the plan addresses that impact directly.

## 18-02

**Summary:** The parser changes have useful real-output fixtures and preserve the shared parsing path.

- **Strength:** The change targets the actual empty-prefix fallback at `installer/versions.py:56–68`, rather than introducing a second parser.
- **Cycle-2 LOW — FULLY RESOLVED:** Normalization is now punctuation → `version=` → independent quotes, with the combined `version="1.2.3",` case (`18-02-PLAN.md:131,140`).
- **Concern — MEDIUM:** Task 1’s instruction to rewrite “the comment block above the boundary” to six lines is ambiguous. The existing block includes audit evidence required by `tests/test_versions.py:402–414`; migration of that contract belongs to Task 2. See `18-02-PLAN.md:97–110` versus `:135–140`, and `installer/versions.py:33–55`.
- **Suggestion:** Restrict Task 1’s rewrite explicitly to the boundary explanation at source lines 49–55, preserving the preceding audit paragraphs until Task 2.
- **Risk:** **MEDIUM** — possible failure of the intermediate green-commit gate, not a parser-design blocker.

## 18-03

**Summary:** The stub rule remains localized, preserves alternate installation evidence and exposes a user-visible reason without overriding injected state.

- **Strength:** Continuing through `detect_path` and `bin_dir` preserves the existing union semantics at `installer/status.py:40–53`.
- **Cycle-2 LOW — FULLY RESOLVED:** The git probe is explicitly `("/usr/bin/xcode-select", "-p")`, with an argv assertion and absolute-path test (`18-03-PLAN.md:119,147–148,168`). This removes the PATH-dependent probe.
- **Concerns:** No additional blocking concern identified. The documented second reason lookup is a bounded, explicitly accepted trade-off.
- **Suggestion:** Retain the test proving the injected installed check controls the row even when the subsequent probe changes.
- **Risk:** **LOW** — macOS runtime evidence remains a backstop.

## 18-04

**Summary:** This is an appropriately small fix in the shared naming function.

- **Strength:** `install_app` already calls `cli_spec` before side effects (`installer/apps.py:75–82`), so validation and use can safely land together as required by `18-04-PLAN.md:95–100`.
- **Concerns:** No additional actionable concern identified.
- **Suggestion:** Keep install, update and removal dependent on `cli_spec`; avoid additional `cli_name` readers.
- **Risk:** **LOW** — narrow production change with install/removal regression coverage.

## 18-05

**Summary:** The final design covers both uv-added and inherited project-venv PATH entries, but one verification command contradicts the supported activated-venv scenario.

- **Strength:** The entry-point filter complements isolation rather than mutating the development environment.
- **Concern — MEDIUM:** Task 1 requires standalone isolated Python to find no `.venv` ruff (`18-05-PLAN.md:139–140`). Task 3 deliberately demonstrates that the same command inherits an activated project venv (`:211–212`). The filter runs only through `setup.py`, so it cannot affect Task 1’s standalone `python -c`.
- **Suggestion:** Label Task 1’s probe a **non-activated-environment control** and remove project-venv PATH entries from that probe’s environment. Keep Task 3’s activated-PATH control/filter pair.
- **Risk:** **MEDIUM** — the final implementation can work, but the current verification sequence is environment-dependent.

## 18-06

**Summary:** Deletion and data changes are well scoped, with explicit catalog-count and stale-cache consequences.

- **Strength:** The ruff ladder is intentionally pinned to release → uv-tool → brew (`18-06-PLAN.md:198`), matching ranks 20, 20 and 40 plus stable ordering in `installer/resolve.py:13–28,81–84`.
- **Concerns:** No new blocking concern identified.
- **Suggestion:** Preserve the ledger distinction between actual applied fixes and optional sub-bullets not applied.
- **Risk:** **LOW–MEDIUM** — mostly data edits, with upstream-layout evidence deferred explicitly.

## 18-07

**Summary:** The single-release-snapshot and production-composition tests are strong, but the changed return contract introduces false verification for tarballs.

- **Strength:** The engine’s existing checksum branch already distinguishes hard integrity failure from ordinary fall-through (`installer/engine.py:144–153`).
- **Concern — HIGH:** `None` now means “verified,” but the plan sets `unverified_reason` only for `github_release` targets (`18-07-PLAN.md:131–133`). Existing tarball construction supplies only URL/member/asset (`installer/download.py:122–126`), leaving the new reason default as `None`. A no-hash tarball would therefore produce `verified=True`.
- **Execution impact:** The required migration of `test_install_download_returns_false_when_unverified` cannot assert a reason without adding tarball behavior: that existing fixture is specifically a tarball (`tests/test_download.py:516–526`; plan migration at `18-07-PLAN.md:137`).
- **Suggestion:** Assign the no-hash tarball reason in this task, not later in 18-16, and assert the engine outcome is unverified.
- **Risk:** **HIGH** — contradicts the phase’s central truthful-status requirement and the plan’s own green-commit gate.

## 18-08

**Summary:** Audit E/F edits have explicit application conditions and a complete evidence ledger.

- **Strength:** The corrected glab ordering follows native rank 30 before brew rank 40 (`installer/resolve.py:23–28`).
- **Cycle-2 LOW — FULLY RESOLVED:** F4 keeps its test in both application and rejection branches, preserving eight passing F tests (`18-08-PLAN.md:139,148,151–158`). Current source supports the intended probe: `installer/registry.toml:2862`, `installer/model.py:132,389–391,438`.
- **Concerns:** No new blocker identified.
- **Suggestion:** Record the actual branch taken, rather than retaining the hypothetical fallback as evidence.
- **Risk:** **MEDIUM** — vendor-script and platform behavior still require the named backstops.

## 18-09

**Summary:** The revised smoke path closes the exit-zero stderr gap and adds important pre-swap containment and cleanup.

- **Cycle-2 N1 — FULLY RESOLVED:** The plan moves the existing subprocess implementation into `run_output_with_stderr` and checks stderr on successful exits (`18-09-PLAN.md:132–150`). This directly addresses `installer/run.py:102–108`, where successful stderr is currently discarded.
- **Strength:** Extraction, containment, chmod and smoke now share a cleanup boundary (`18-09-PLAN.md:152`), addressing the extraction currently outside cleanup at `installer/download.py:323–329`.
- **Concern — MEDIUM:** Reusing the update rollback unchanged for fresh installs leaves a gap after relinking. `_undo_archive_swap` restores a link only when an original target exists (`installer/download.py:381–390`). If a fresh install creates its link and post-swap validation fails, rollback can remove the tree but leave a dangling new link.
- **Suggestion:** Add a fresh-install post-relink failure test and require rollback to remove a newly created link when there was no prior link.
- **Risk:** **MEDIUM** — normal smoke failures are handled correctly; post-swap failure recovery needs one more case.

## 18-10

**Summary:** Encoding and decoding now land together, with compatibility and per-entry hardening separated sensibly.

- **Cycle-2 N2 — FULLY RESOLVED:** Task 1 explicitly implements both cache encoding and basic decoding (`18-10-PLAN.md:105`), satisfying its round-trip test before committing. The existing decoder currently returns only version/time fields (`installer/version_cache.py:104–117`).
- **Strength:** Failed refreshes preserve previous digests alongside the previous version; this follows the existing failure-entry mechanism at `installer/version_status.py:185–191`.
- **Concern — LOW:** Task 2 says `_as_object(raw)` where the intended object is the digest submapping (`18-10-PLAN.md:136`). Source `_entry_from_raw(raw)` uses `raw` for the entire cache entry.
- **Suggestion:** Name the digest mapping explicitly and decode from `mapping.get("digests")`; avoid a literal implementation that scans the outer entry.
- **Risk:** **LOW–MEDIUM** — tests should catch the naming ambiguity.

## 18-11

**Summary:** Shared staged app installation, pre-swap executable checks and hash-before-smoke ordering are sound.

- **Cycle-2 absolute-link concern — FULLY RESOLVED by recorded rejection:** The rejection is explicit at `18-11-PLAN.md:224`. Its claimed fallback is real: post-swap validation checks the CLI at `installer/apps.py:186–194` and invokes rollback at `:160–166`.
- **Strength:** Pre-swap containment and executability checks avoid unnecessarily disturbing a working bundle (`18-11-PLAN.md:126–133`).
- **Concern — MEDIUM:** As with downloads, the existing rollback restores only a previous symlink (`installer/apps.py:197–206`). A fresh install failing after creating its link can leave a dangling link when the new bundle is removed.
- **Suggestion:** Cover fresh-install relink/validation failure and removal of a newly created CLI link, while retaining restoration of an existing link.
- **Risk:** **MEDIUM** — fixture coverage is strong, but real macOS smoke remains unproven.

## 18-12

**Summary:** Target identity and evidence reporting are substantially improved. Two checker semantics still need tightening.

- **Cycle-2 N3 — FULLY RESOLVED:** State identity includes tool, URL, member, archive, strip and raw, with changed-strip tests (`18-12-PLAN.md:161–168`).
- **Cycle-2 corrupt-archive MEDIUM — FULLY RESOLVED:** Tar/zip parser failures become drift without state writes (`:163,168`).
- **Cycle-2 pinned/latest-hash MEDIUM — FULLY RESOLVED:** API digest comparison is restricted to the URL’s own latest tag (`:155,168`).
- **Concern — MEDIUM:** `tarfile.open(..., "r:*")` autodetects compression (`:168`), but installation selects gzip or xz from the registry (`installer/download.py:63–72,369–377`). A wrongly declared compression can pass verification yet fail installation.
- **Concern — MEDIUM:** A target matching cached state is immediately accepted, while a later target on the same URL can force a download that discovers a URL-wide hash/archive failure (`:168`). The plan does not define overriding earlier cached successes or invalidating their state.
- **Suggestions:** Match declared compression during checking; make fresh URL-wide failures override all cache hits irrespective of target order.
- **Risk:** **MEDIUM** — both gaps can produce misleading “Passed” evidence.

## 18-13

**Summary:** Rejected-candidate dating is fixed, but the revised bump eligibility contradicts the preserved-unpinned-drift test.

- **Cycle-2 N4 — FULLY RESOLVED:** Rejected candidates add drift before computing date edits (`18-13-PLAN.md:134,147`).
- **Cycle-2 H7b — PARTIALLY RESOLVED:** Superseded pinned-URL findings are replaced explicitly (`:137,147`), but the eligibility problem below prevents one required scenario.
- **Concern — HIGH:** Candidate checking runs on a copy of the **whole tool** and requires every finding to be ok (`:145`). Yet `test_bump_keeps_the_findings_of_the_tools_unpinned_methods` requires an applied pin bump while an unchanged unpinned method returns 404 (`:138`). That unpinned method fails the candidate check too, so the bump cannot apply.
- **Suggestion:** Check candidate **pinned methods only** for bump eligibility. Preserve original unpinned findings when building the final report, and compute `verified` exclusively from that final report.
- **Risk:** **HIGH** — the action and required acceptance test cannot both hold as written.

## 18-14

**Summary:** Issue formatting and state persistence now have good explicit contracts.

- **Cycle-2 LOW — FULLY RESOLVED:** Variable-length code-span delimiters and control-character replacement address backtick/newline injection (`18-14-PLAN.md:138–144`).
- **Strength:** The issue body excludes the large Passed section, and incremental state persistence uses the existing atomic writer (`installer/atomic.py:34–58`).
- **Concern — LOW:** “Zero gh calls” for clean or blocked runs is broader than production behavior: authentication can first call `gh auth token` (`18-17-PLAN.md:200`). Injected-probe tests bypass that path.
- **Suggestion:** Specify **zero issue/label calls**, allowing the credential lookup. The workflow supplies `GH_TOKEN`, so its scheduled path remains unaffected.
- **Risk:** **LOW–MEDIUM** — primary remaining dependencies are checker correctness and first real workflow execution.

## 18-15

**Summary:** Saved evidence and a separate read-only acceptance run are appropriate safeguards.

- **Cycle-2 per-target-evidence MEDIUM — FULLY RESOLVED:** The checker now emits Passed targets with platforms, and this plan requires those exact citations (`18-12-PLAN.md:118,123`; `18-15-PLAN.md:174`).
- **Cycle-2 H7b — PARTIALLY RESOLVED:** The precondition covers superseded-target replacement, but the 18-13 whole-tool eligibility contradiction remains.
- **Concern — MEDIUM:** The final run reuses state (`18-15-PLAN.md:163–174`), so its evidence depends on resolving 18-12’s cache-hit versus fresh URL-failure precedence.
- **Suggestion:** Add the mixed pinned/unpinned bump test and order-independent URL-failure test to the preconditions before the live write.
- **Risk:** **MEDIUM–HIGH** until those checker/writer contracts are corrected.

## 18-16

**Summary:** The staged plain-argv fetch unification is appropriately scoped and reuses existing update machinery.

- **Strength:** The production-composition wrong-digest update test verifies more than resolver invocation (`18-16-PLAN.md:105–114`). Existing download placement and rollback are available at `installer/download.py:304–358`.
- **Concern:** Its no-hash tarball reason is correct (`18-16-PLAN.md:147`), but it arrives too late to repair 18-07’s independently committed false-verification contract.
- **Suggestion:** Move the basic unverified tarball reason into 18-07; leave pin rendering and supplied-hash verification here.
- **Risk:** **LOW** locally, **MEDIUM** for integration ordering.

## 18-17

**Summary:** HTTP error classification is corrected, but transport-outage blocking still overreaches.

- **Cycle-2 H9b — FULLY RESOLVED:** Received 403/404/503 responses count as responses, with explicit all-error-response tests (`18-17-PLAN.md:116–117,128–130`). Source preserves underlying fetch causes through the release resolver (`installer/versions.py:326–337`).
- **Concern — HIGH:** The executable verdict still blocks when every attempted **release read** fails at transport level, even if another vendor’s HEAD returns a real 404 (`18-17-PLAN.md:130`). That is not a whole-run outage: real drift exists elsewhere, but the issue would be suppressed.
- **Suggestion:** For non-rate-limit outage detection, count responses across **both release reads and HEAD/download requests**. Add one API transport failure plus one vendor 404 regression. Preserve the explicit rate-limit override.
- **Risk:** **HIGH** — can silence the weekly report despite known drift.

## 18-18

**Summary:** Fresh-container retries, exact ruff evidence and explicit identity recording make this a much stronger acceptance procedure.

- **Cycle-2 LOW — FULLY RESOLVED:** Container IDs are recorded at bootstrap, probes, pass1 and pass2, then checked for equality (`18-18-PLAN.md:95,112–113,132–144`).
- **Strength:** The plan correctly uses the pass2 transcript, where the harness actually writes its markers (`scripts/container-e2e-verify.sh:420–478`).
- **Concerns:** No new blocking concern identified in the procedure.
- **Suggestion:** Retain the stop-and-report rules for installer defects; do not turn container accommodations into weaker production smoke.
- **Risk:** **MEDIUM** — expensive live upstream behavior and Linux-only coverage remain inherent.

## 18-19

**Summary:** Manager leftovers are now honestly reported without unsafe automatic removal, and the sourced SDKMAN exception is explicit.

- **Cycle-2 MEDIUM — FULLY RESOLVED:** Task 3 reports leftovers in errors and later successful warnings (`18-19-PLAN.md:202–212`), using the existing removal table at `installer/ownership.py:1368–1382`, consistent with ledger L-18-16.
- **Concern — MEDIUM:** The broken-manager test specifies “brew then script” and expects brew to fail before script succeeds (`18-19-PLAN.md:118,204`). Actual resolution always places script rank 10 before brew rank 40 (`installer/resolve.py:13–28,81–84`), regardless of file order.
- **Suggestion:** Use two same-ranked, deterministically ordered manager methods for this scenario, or explicitly inject an ordered ladder if that is the intended unit-test seam.
- **Risk:** **MEDIUM** — the production hook is plausible, but these required tests cannot exercise their stated sequence with normal resolution.

## 18-20

**Summary:** The split reduces file contention and keeps the registry trust boundary separate from execution.

- **Strength:** Shape validation reuses the existing script-argument convention and keeps node’s closed `smoke` dispatch distinct (`18-20-PLAN.md:99–107`; current node validation at `installer/model.py:713–717`).
- **Concern — LOW:** Authoring guidance says every binary is smoked “before it is linked” while also describing manager smoke after installation (`18-20-PLAN.md:142`). Managers may already have created their links, and some installs intentionally have nothing runnable to smoke.
- **Suggestion:** State the two guarantees separately: staged smoke before installer-created links; post-install manager smoke when a runnable target exists.
- **Risk:** **LOW** — wording consistency, not a new execution blocker.

## Cross-plan assessment

### Overall summary

The revisions resolve the specific cycle-2 defects substantially better than the previous plans: stderr is retained, cache identity includes extraction settings, rejected candidates cannot be re-dated, HTTP error responses are not mistaken for network absence, and live evidence is much more precise. The declared wave file sets are sensibly separated. However, **approval should remain withheld** because four concrete issues affect truthful results or executable acceptance:

1. **18-07:** No-hash tarballs become falsely verified before 18-16.
2. **18-13:** Whole-tool candidate eligibility contradicts applying a pin bump while preserving unpinned drift.
3. **18-17:** API-only transport failure can suppress real vendor drift.
4. **18-19:** Required brew-before-script scenarios contradict actual method ranking.

### Recommended disposition

**Status: Issues Found — targeted fixes required.**

Fix those four issues first, then address the medium checker/rollback cases without another broad redesign. In particular, the checker should prove that its declared extraction mode matches installation and that fresh URL failures override cached success.

### Overall risk: HIGH

The risk is concentrated in **truth claims and failure paths**, not missing feature coverage. The plans cover the phase requirements comprehensively, but several instructions can currently report verification inaccurately, suppress actionable drift, or require tests whose execution order is impossible.

**Not checked:** No tests, live downloads, workflow dispatches or container installs were run; no files were edited.  
**Residual risk:** Real macOS smoke behavior and upstream changes remain execution-time backstops, not established review evidence.

---

## Consensus Summary

One reviewer ran (`opencode-plan-review`, the only entry in `review.default_reviewers`). There is no cross-reviewer consensus, and the consensus gate does not apply. Every HIGH that this reviewer raised and that the orchestrator confirmed in the source counts. The review is source-grounded: it cites about 60 `file:line` locations and carries no discount marker. It covers all 20 plan ids (coverage check: complete, 20/20). The reviewer was given the cycle-2 HIGH and actionable tables and asked for a verdict on each. The orchestrator checked those verdicts and every new finding against the revised plans (8d6f30a, ledger 5569f17) and the source at `5569f17`.

### Agreed Strengths
- (single reviewer) All six cycle-2 HIGHs are fixed as they were stated: N1, N2, N3, N4, H7b (superseded-target replacement) and H9b. All eleven cycle-2 actionable MEDIUM/LOW findings are incorporated, or explicitly rejected in the plan (18-11's absolute-link rejection). The 18-09 split into 18-20 is safe: the two plans share wave 4 but no file, and 18-19 depends on 18-20.

### Agreed Concerns
- None (single reviewer). The highest-priority single-reviewer concerns, both confirmed:
  - 18-07 reports a no-hash tarball as verified until 18-16 lands.
  - 18-13 checks bump eligibility on the whole tool, which contradicts its own unpinned-drift test.

### Divergent Views
- None (single reviewer). The orchestrator rejected one reviewer HIGH (18-17's API-only transport outage) because it contradicts locked Ledger L-18-05.

### Cycle-2 HIGH resolution (orchestrator, source-checked)

| # | Plan | Cycle-2 HIGH | Revised plan / source evidence | Status |
|---|------|--------------|-------------------------------|--------|
| N1 | 18-09 | Loader errors were checked only when `run_output` raised | 18-09-PLAN.md:148-150: `run_output_with_stderr` holds today's `run_output` body (`installer/run.py:93-108`) and returns both streams, and `run_output` delegates to it. `smoke_binary` checks `_LOADER_ERROR` in stderr on exit 0, and in `CommandError.detail` (which carries stderr, `installer/run.py:104-105`) otherwise. Tests `..._loader_error_even_on_exit_0` and `..._other_stderr_on_exit_0` cover this. The strict fake in `tests/test_run.py:117-127` is extended for `env`, and the other `subprocess.run` fakes take `**kwargs` (`tests/test_install_ownership.py:53`, `tests/test_setup.py:1897`) | FULLY RESOLVED |
| N2 | 18-10 | Task 1 required a digest round trip but only encoded | 18-10-PLAN.md:105: basic decoding `_as_object(raw.get("digests"))` keeps `str -> str` pairs in Task 1, next to the encode. The round-trip test and the two-occurrence grep pass in that commit. Task 2 keeps the 64-hex hardening | FULLY RESOLVED |
| N3 | 18-12 | Cached `ok` ignored the extraction settings | 18-12-PLAN.md:23,62,168: `state_key` = `<tool_id>\|<url>#<member>\|archive=\|strip=\|raw=`. Tests `test_a_strip_change_invalidates_the_cached_ok` and `test_targets_differing_only_in_strip_are_checked_separately` cover it. Extraction applies `strip` (`installer/download.py:361-377`) | FULLY RESOLVED |
| N4 | 18-13 | A rejected `--candidate` was still dated | 18-13-PLAN.md:27,134,147: an unapplied bump adds drift `bump to <v> not applied`, and the `verified` edits are built from the final report. The test asserts the line is unchanged, the tool is not in `passed_tools()`, and the exit code is 1 | FULLY RESOLVED |
| H7b | 18-13 (+18-15) | Superseded old-pin drift survived an applied bump | 18-13-PLAN.md:30,137,147: every finding on the bumped tool's old pinned urls is replaced, and findings on its other urls are kept. Superseded-target replacement is fixed. A new eligibility contradiction in the same flow is tracked separately as C3-H2 | FULLY RESOLVED (replacement); see C3-H2 |
| H9b | 18-17 | Received 403/404 answers counted as an outage | 18-17-PLAN.md:25,128-130: only transport failures with no HTTP response, and recognized rate limits, block a run (Ledger L-18-15). `HTTPError` is an `OSError` and stays the `__cause__` of `VersionError` (`installer/versions.py:329-332`). The rebuilt `test_forbidden_without_rate_limit_evidence_does_not_block` (the 403 is the only release read) and `test_http_answers_never_block_the_run` cover it | FULLY RESOLVED |

### Cycle-2 actionable non-HIGH resolution

| Plan | Finding | Evidence | Status |
|------|---------|----------|--------|
| 18-01 | Seeding duplicated `verified` keys | 18-01-PLAN.md:170: a tool table is seeded only when it has no `verified` line | FULLY RESOLVED |
| 18-02 | Normalizer order | 18-02-PLAN.md:131,140: punctuation, then `version=`, then quotes. Fixture row `version="1.2.3",` | FULLY RESOLVED |
| 18-03 | Bare `xcode-select` | 18-03-PLAN.md:119,147,168: `("/usr/bin/xcode-select", "-p")`, with an absolute-path test | FULLY RESOLVED |
| 18-08 | F4 fallback vs eight tests | 18-08-PLAN.md:139,158: the F4 test exists in both branches | FULLY RESOLVED |
| 18-11 | Absolute link after relocation | 18-11-PLAN.md:224: explicit rejection with its rationale | FULLY RESOLVED (rejected in plan) |
| 18-12 | Corrupt archives | 18-12-PLAN.md:25,168,216: `TarError`/`BadZipFile` are drift with no state entry, and there is a corrupt-archive test | FULLY RESOLVED |
| 18-12 | Pin vs latest-release digest | 18-12-PLAN.md:25,168,217: the pin is compared only when the url's tag is the latest tag, and there is an older-tag test | FULLY RESOLVED |
| 18-14 | Code-span escaping | 18-14-PLAN.md:30,139,270: `code_span` maps control characters to spaces and uses a longer backtick run. Break-out test | FULLY RESOLVED |
| 18-15 | Per-target `ok` evidence | 18-12-PLAN.md:26,118: `Passed` section with platforms. 18-15-PLAN.md:35,174 cites it | FULLY RESOLVED |
| 18-18 | Container identity | 18-18-PLAN.md:24,95,132: `18-18-container-id.log` is truncated at each bootstrap, and the ids are checked for equality | FULLY RESOLVED |
| 18-19 | SPEC "no linked binary" for manager kinds | 18-19-PLAN.md:27,191-225 + Ledger L-18-16: leftovers are reported with the `_REMOVAL_COMMANDS` command (`installer/ownership.py:1368-1382`) and never uninstalled | FULLY RESOLVED |

### New HIGHs this cycle (orchestrator, source-checked)

| # | Plan | HIGH | Source check | Status |
|---|------|------|--------------|--------|
| C3-H1 | 18-07 | A no-hash tarball becomes `verified=True` | Confirmed. 18-07-PLAN.md:131 sets `unverified_reason` only in the github_release branch. The tarball branch (`installer/download.py:122-126`) builds `DownloadTarget` with the new default `unverified_reason=None`. `install_download` returns `target.unverified_reason` and the engine maps `reason is None` to verified (18-07-PLAN.md:133). So between 18-07 (wave 2) and 18-16 (wave 3, which adds `unpinned url; no sha256 to verify against`, 18-16-PLAN.md:25), every tarball install is shown as verified. 18-07's own migration of `test_install_download_returns_false_when_unverified` to "an assertion on the returned reason" (18-07-PLAN.md:137) uses a tarball fixture (`tests/test_download.py:516-526`) whose reason is None. This is the same green-commit contradiction class as cycle-2 N2 | Open |
| C3-H2 | 18-13 | Whole-tool candidate eligibility contradicts the unpinned-drift test | Confirmed. 18-13-PLAN.md:145 runs `check_registry` on a copy of the whole tool and applies the bump "only when every finding of that tool copy is ok". The copy keeps the unpinned methods, so `test_bump_keeps_the_findings_of_the_tools_unpinned_methods` (:138, an unpinned asset HEADs 404 and the bump is expected to apply) cannot pass. :147 also says the candidate findings are "for its pinned methods (all ok by construction)", which only holds if eligibility is limited to the pinned methods' findings | Open |

Rejected reviewer HIGH (not counted):
- **18-17: an API-only transport failure blocks the run although a vendor HEAD returned 404.** The mechanism is real (18-17-PLAN.md:130). But locked Ledger L-18-05 (18-CONTEXT.md:96) names "release API unreachable" as a whole-run outage, and L-18-10 and L-18-15 refine only what counts as a failed read. The plan implements the locked decision literally. Any change belongs in a new ledger amendment, not in this plan. The impact is limited to one weekly run in which api.github.com is unreachable while vendor hosts answer, and the next run reports the drift.

18-15's "H7b partial" and 18-16's "tarball reason arrives too late" restate C3-H2 and C3-H1. They resolve with those fixes and are not counted twice.

### Non-HIGH findings this cycle (orchestrator disposition)

| Plan | Sev | Finding | Disposition |
|------|-----|---------|-------------|
| 18-19 | MEDIUM | `test_manager_install_with_a_broken_binary_falls_through` and `test_leftover_package_is_reported_on_a_later_install` expect brew to fail before script succeeds | Confirmed. `install_tool` orders methods through `resolve_methods` (`installer/engine.py:135`), and `_RANK` puts script at 10, before brew at 40 (`installer/resolve.py:13-29`). Brew also needs `has_brew`. Actionable: use two methods of equal rank in declared order (for example uv-tool then node, both rank 20), or a brew method followed by a cask |
| 18-12 | MEDIUM | `tarfile.open(path, "r:*")` autodetects compression, while install uses the declared `archive` (`installer/download.py:63-72`) | Confirmed (18-12-PLAN.md:168). A wrong or missing `archive = "xz"` would be certified as `ok` (the kitty-type gap). Actionable: list with the declared mode (`r:gz`/`r:xz`) and report a mismatch as drift, with one test |
| 18-09 | MEDIUM | Fresh-install rollback after relink leaves a dangling link | Confirmed. `_undo_archive_swap` restores the link only when `original_target is not None` (`installer/download.py:381-390`). On a fresh install a post-relink failure removes the tree but keeps the new link, which contradicts SPEC R5's "`~/.local/bin/<bin>` does not exist". The window is narrow because `staged_member` and the smoke run before the swap. Actionable: unlink a newly created link when there was no original, plus one test |
| 18-11 | MEDIUM | Same as 18-09 for `_undo_app_swap` | Confirmed (`installer/apps.py:197-206`). Actionable: same fix, with a fresh-install test |
| 18-05 | LOW | Task 1's probe `uv run --isolated --no-dev python -c ... which('ruff')` inherits the caller's PATH, so it fails from an activated venv, the case Task 3 handles | Confirmed (18-05-PLAN.md:139 vs :211). Actionable: label it a non-activated control, or drop `<repo>/.venv/bin` from that probe's PATH |
| 18-02 | LOW | "Rewrite the comment block above the boundary" could swallow the `Verified` / `Not covered:` paragraphs pinned by `test_versions_module_records_the_registry_wide_audit_finding` | Partly confirmed. `installer/versions.py:33-55` is one contiguous comment block, and `tests/test_versions.py:401-414` pins its first paragraphs. Task 1's whole-file verify would catch a wrong rewrite. Actionable: scope the rewrite to the boundary paragraph (`installer/versions.py:49-55`) |
| 18-12 | LOW | A target with a cached `ok` stays `ok` when a later target on the same url downloads it in the same run and finds a url-wide failure | Confirmed (18-12-PLAN.md:168: a cache hit returns before the per-run url cache). This is reachable only when the bytes change under an unchanged expected hash (a stale checksum file). Actionable: after the per-run download of a url, override every cached `ok` on that url |
| 18-20 | LOW | The architecture.md sentence says every binary is smoked "before it is linked", but manager kinds are smoked after the manager installs (and links) | Confirmed (18-20-PLAN.md:142). Actionable: word the two guarantees separately |
| 18-10 | LOW | Task 2 says `_as_object(raw)` | Not actionable. Task 2 "hardens Task 1's decode", and Task 1 states the exact expression `_as_object(raw.get("digests"))` (18-10-PLAN.md:105). `test_mixed_digests_keep_the_valid_entries` catches a wrong target |
| 18-14 | LOW | "zero `gh` calls" while 18-17 may call `gh auth token` | Not actionable. `github_token` runs only when `probe is None` (18-17-PLAN.md:200), so the injected-probe tests see zero calls, and the workflow supplies `GH_TOKEN`. The SPEC R3 intent (no issue call) holds |
| 18-15 | MEDIUM | The final run reuses state, so its evidence depends on the 18-12 cache precedence | Restates the 18-12 LOW above. Not counted twice |

## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). It ran on 2026-10-15 over all 20 revised plans at `5569f17`.

**Authority.** `drift-guard authority --raw` returned `intel` (config `grep`, upgraded by `intel.enabled: true`). `.planning/intel/` lists only CLI entry points, so under that authority every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO). It is not treated as verified or missing on that basis. Supplementary grep evidence was collected over `git ls-files` outside `.planning/`. `drift-guard severity` under `intel` gives VERIFIED -> none, MISSING -> needs-acknowledgement (no hardBlock), AMBIGUOUS -> MEDIUM and UNCHECKABLE -> INFO. No verdict produced a hardBlock.

**Enumeration.** Every backticked token in the 20 PLAN.md files was enumerated if it had a symbol shape (`module.func`, `Class.attr`, `path::name`, `name()`, snake/camel identifiers), a path shape or a `--flag` shape, and was de-duplicated per name. That gave 699 distinct tokens. 297 sit in a plan's artifact/interface lists and were excluded as new by design. Of the remaining 402, 317 have grep evidence (a declaration or reference in the source, or an existing path or flag) and 85 were not found.

Spot-verified declarations that the revisions rely on:
- `run_output` and its `CommandError` mapping (`installer/run.py:93-108`, `:32-43`).
- `_as_object` and `_entry_from_raw` (`installer/version_cache.py:89,104`).
- `_replace_archive`, `_extract_into`, `_undo_archive_swap` and `_tar_flag` (`installer/download.py:311,360,381,63`).
- `_undo_app_swap` and `_validate_app` (`installer/apps.py:197,186`).
- `_KIND_TO_OWNER` and `_REMOVAL_COMMANDS` (`installer/ownership.py:143,1368`), and `manager_name` (`installer/uninstall.py:225`).
- `InstallOutcome.postinstall_warning` (`installer/engine.py:40`), `_RANK` (`installer/resolve.py:13`), and `resolve_github_tag` with `OSError` wrapping (`installer/versions.py:326-332`).
- The kitty comment naming `_install_unverified/_place_verified` (`installer/registry.toml:2539,2623`), and `test_kitty_entry_records_the_txz_extraction_gap` (`tests/test_registry.py:1513`).
- `cmd = "sdkman-init.sh"` (`installer/registry.toml:1748`).

Not-found tokens and their acknowledgement (needs-acknowledgement). None is a hallucinated reference to existing code:

| Cited at | Token | Why absent |
|---|---|---|
| each plan's `<output>` | `18-NN-SUMMARY.md` (20) | execution output created by each plan |
| 18-07, 18-09, 18-10, 18-11, 18-12, 18-13, 18-14, 18-16, 18-17, 18-19 | `release_resolver`, `ExecContext.resolve_release`, `resolve_release`, `DownloadTarget.unverified_reason`, `unverified_reason`, `run_output_with_stderr`, `smoke_binary`, `method_smoke_argv`, `staged_member`, `_stage_and_swap_app`, `download.pinned_url`, `check_registry`, `state_key`, `include_passed`, `RegistryEdit`, `apply_registry_edits`, `method_index`, `Report.passed_tools()`, `report.not_checkable`, `code_span`, `on_verified`, `ownership.method_removal_command`, `verify_registry`, `_normalize_version_token`, `drop_project_venv_from_path`, `macos_stub_reason`, `stub_reason`, `seed_verified` | created by plans of this phase (18-07, 18-09, 18-11, 18-12, 18-13, 18-14, 18-16, 18-17, 18-19, 18-02, 18-05, 18-03, 18-01). Each consumer depends on its creator through `depends_on` or wave order |
| 18-16:147 | `installer/assets.py::render_pinned_url` | the plan records it as a deviation: the renderer is `download.pinned_url`, created by 18-16 |
| 18-05:128 | `_recipes()` | private helper in the new `tests/test_makefile.py` |
| 18-02:67 | `D-registry-user-part1.md`, `E-registry-user-part2.md` | exist under `.planning/research/audit-2026-10-13/` (outside the grep corpus) |
| 18-08:68 | `resolve.py::_RANK` | bare filename; `installer/resolve.py:13` |
| 18-18:71 | `sdkman-init.sh` | registry value (`installer/registry.toml:1748`); the checker missed it only because of the path shape |
| 18-05, 18-01, 18-08, 18-14 | `--isolated`, `--no-dev`, `--exact`, `--no-verify`, `--no-modify-path`, `--body-file` | external uv, git, installer and gh flags |
| 18-12, 18-13 | `--candidate`, `--state` | verify-registry flags created by 18-12 and 18-13 |
| 18-09:139 | `--custom` | fixture argv in a new test |
| 18-03:30 | `java_home` | macOS `/usr/libexec/java_home` (external) |
| 18-12, 18-14 | `tarfile.ReadError`, `tarfile.TarError`, `zipfile.BadZipFile`, `urllib.error.HTTPError`, `TimeoutError`, `getnames()`, `namelist()`, `tempfile.TemporaryDirectory`, `tempfile.NamedTemporaryFile` | stdlib |
| 18-14:32 | `workflow_dispatch` | GitHub Actions trigger key (external) |
| 18-08:90 | `test_audit_fix_` | test-name prefix |

**UNCHECKABLE / skipped.**
- Signatures (argument lists, return types) cannot be asserted under `intel`/`grep`. Names only were checked.
- External surfaces are not in the repo: uv/gh/git flags, GitHub REST rate-limit headers, Actions semantics, upstream asset names and digests, and macOS binaries.
- Behaviour claims were spot-checked against the tree:
  - `run_output` drops stderr on success and raises with `detail=stderr` otherwise.
  - `_undo_archive_swap`/`_undo_app_swap` restore a link only when one existed.
  - `install_tool` orders methods by `resolve_methods`.
  - The tarball branch of `_resolve_target` carries no reason.
- Live network counts (18-RESEARCH.md digests) were not re-probed, and no tests, containers or live runs were executed.
- Wave/file-overlap check: no two plans in one wave share a `files_modified` entry. In wave 4, 18-09 and 18-20 are disjoint; in wave 5, 18-12 and 18-19; in wave 6, 18-11 and 18-17.

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 18`): verdict `lag`. STATE.md says "Ready to execute" (rank 1), ROADMAP.md says "Not started" (rank 0), and STATE.md is the authority. The two are one non-terminal step apart, so this is not a finding.
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction. ROADMAP lists 20 plans with waves that match each plan's frontmatter (18-09 W4, 18-20 W4, 18-19 W5, and so on). 18-08's "35-row ledger" in ROADMAP matches 18-08-PLAN.md:26 (16 rows from 18-06 + 19).
- **Requirement IDs** (ROADMAP.md authority): REG-01..REG-10 each appear in at least one plan's `requirements:` (REG-07, REG-08 and REG-10 once each; REG-04 six times). No plan cites an ID outside the roadmap.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority): no contradiction. L-18-17's refinements each match the plans:
  - `run.run_output_with_stderr`: 18-09.
  - `/usr/bin/xcode-select -p`: 18-03.
  - The normalizer order: 18-02.
  - The pin compared only on the latest tag, an unlistable archive as drift, and exit 64: 18-12 and 18-13.
  - `format_report(include_passed=False)` with code spans: 18-14.
  - The leftover command in the error and the warning: 18-19.
- L-18-15 (transport-only outage) is implemented by 18-17 together with L-18-05's "release API unreachable" whole-run outage. The reviewer's 18-17 HIGH argues against that locked combination; it is recorded above as a rejected finding, not as drift.
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
