---
phase: 18
cycle: 2
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-15T13:02:33Z
plans_reviewed: [18-01-PLAN.md, 18-02-PLAN.md, 18-03-PLAN.md, 18-04-PLAN.md, 18-05-PLAN.md, 18-06-PLAN.md, 18-07-PLAN.md, 18-08-PLAN.md, 18-09-PLAN.md, 18-10-PLAN.md, 18-11-PLAN.md, 18-12-PLAN.md, 18-13-PLAN.md, 18-14-PLAN.md, 18-15-PLAN.md, 18-16-PLAN.md, 18-17-PLAN.md, 18-18-PLAN.md, 18-19-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 18 (convergence cycle 2)

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-plan-review)

Baseline confirmed: `load_tools` at `installer/model.py:639` has no `today`/`METHOD_PARAMS`/`verified` yet — plans describe future work against this state. Now dispatching four parallel source-verification agents.
While the four verification agents run, I'll check the cycle-1 review record for disposition fidelity.
**Document type:** GSD execution plans · convergence cycle 2  
**Coverage:** 19/19 plans reviewed against repository source and revised plan text.  
**Citation shorthand:** `18-NN-PLAN.md` refers to `.planning/phases/18-registry-truth-and-drift-guard/18-NN-PLAN.md`.

## 18-01

**Summary:** Closing method parameters and validating structured dates address the actual pass-through at `installer/model.py:666–667`.

- **Strengths:** The structural-key regression at `18-01-PLAN.md:119` preserves the existing `os`/`arch` checks (`installer/model.py:656–665`).
- **Concerns — MEDIUM:** The fixture helper unconditionally inserts `verified`, while the new validation fixtures supply explicit values (`18-01-PLAN.md:158–170`). Unless those fixtures disable seeding, duplicate TOML keys fail before loader validation; the valid timezone-tolerance case also fails.
- **Suggestions:** Explicitly disable seeding for every fixture supplying `verified`, or seed only tool tables lacking that key.
- **Risk Assessment: MEDIUM** — Production scope is bounded, but the fixture contract needs clarification before execution.

## 18-02

**Summary:** The revised test migration now matches the intended parser behavior.

- **Cycle-1 H1 — FULLY RESOLVED:** Task 2 explicitly migrates the conflicting assertions (`18-02-PLAN.md:134–139`), which currently reject `version=` and procs output (`tests/test_versions.py:313,424–425`).
- **Strengths:** The unbalanced procs quote matches the actual audit evidence (`.planning/research/audit-2026-10-13/E-registry-user-part2.md:75`), rather than an easier balanced fixture.
- **Concerns — LOW:** Quote removal precedes punctuation and `version=` removal (`18-02-PLAN.md:139`), so combinations such as `version="1.2.3",` remain unhandled. This is outside the named acceptance fixtures.
- **Suggestions:** Add one combined-form fixture or explicitly document that normalization supports only the audited forms.
- **Risk Assessment: LOW** — The required behavior and conflicting tests are now accounted for.

## 18-03

**Summary:** The stub checks fit the current PATH-first detection flow without preventing detection through alternate declared paths.

- **Strengths:** `is_installed` already checks PATH, `detect_path`, `bin_dir`, then bundles (`installer/status.py:40–66`); the plan preserves that fallback structure.
- **Concerns — LOW:** The threat model calls the probe table absolute-path-only, but the git entry executes bare `xcode-select` (`18-03-PLAN.md`, Task 1). Its resolution remains PATH-dependent.
- **Suggestions:** Use `/usr/bin/xcode-select`, or correct the threat-model claim. The explicitly tested two-read audit behavior is otherwise acceptable.
- **Risk Assessment: LOW** — Clear platform guards and injected probes keep the change contained.

## 18-04

**Summary:** The naming fix is correctly concentrated in the existing shared CLI specification.

- **Strengths:** Install, update, and uninstall already consume `cli_spec` (`installer/apps.py:80,116`; `installer/uninstall.py:48`). Validation now lands with the behavior change (`18-04-PLAN.md:93–99`).
- **Concerns:** No new blocking concern. The earlier unsafe intermediate-commit issue is resolved.
- **Suggestions:** Retain the install-side zero-runner-call assertion, not just direct `cli_spec` rejection tests.
- **Risk Assessment: LOW** — One shared function fixes both creation and removal naming.

## 18-05

**Summary:** The revised plan covers both uv-added PATH entries and an inherited activated project venv.

- **Cycle-1 H2 — FULLY RESOLVED:** The entry-point filter and activated-venv control/filtered probes are explicit (`18-05-PLAN.md:199–206`). The real entry point is shared by launchers (`setup.py:1549–1556`).
- **Strengths:** All six actual Makefile launchers are covered while validation/test commands remain separate (`Makefile:15–51`; `install.sh:88`).
- **Concerns — LOW:** The guarantee deliberately targets `<repo>/.venv`; other virtual environments remain searchable.
- **Suggestions:** Keep that project-specific scope explicit rather than describing the change as removing every development environment.
- **Risk Assessment: LOW** — The original ownership-shadowing case now has a meaningful regression check.

## 18-06

**Summary:** Duplicate-row removal, dead-probe removal, and the first audit ledger form a coherent data cleanup.

- **Strengths:** The removed probe really executes a PATH-resolved helper (`installer/install_ownership.py:83–89`); removing its model, dispatch, and registry references closes that path.
- **Concerns:** No new blocking concern. The ruff ordering is now intentional and tested: equal-rank release/uv-tool methods precede brew (`installer/resolve.py:13–29,83–84`; `18-06-PLAN.md`, Task 3).
- **Suggestions:** Preserve conditional D7 evidence as conditional; do not record a future live pass as completed evidence.
- **Risk Assessment: LOW** — Registry count changes and stale-cache behavior are explicitly included.

## 18-07

**Summary:** One release snapshot plus the existing checksum exception is a sound verification design.

- **Strengths:** The behavioral default-resolver test now exercises actual composition (`18-07-PLAN.md:124,135`); the current engine already hard-fails checksum mismatches (`installer/engine.py:146–151`).
- **Concerns — MEDIUM:** Function identity remains a fragile production/test discriminator. The new tests detect regressions, but a legitimate wrapper still changes verification semantics (`18-07-PLAN.md:129–135`).
- **Suggestions:** Keep the behavioral test load-bearing; any future resolver wrapper must preserve release metadata explicitly.
- **Risk Assessment: MEDIUM** — Hash checking is straightforward; resolver selection remains unusually sensitive to wiring.

## 18-08

**Summary:** The revised ladder expectations now match the resolver rather than registry declaration order.

- **Cycle-1 H3 — FULLY RESOLVED:** The three glab platform expectations are corrected (`18-08-PLAN.md:99`); native rank 30 precedes brew rank 40 (`installer/resolve.py:23–28,83–84`).
- **Strengths:** The final ledger distinguishes applied, already-done, optional, and precondition-dependent changes instead of blindly applying audit suggestions.
- **Concerns — LOW:** F4 allows a loader-rejected probe to be recorded as not applied, while the final verification still requires eight F tests (`18-08-PLAN.md`, Task 2). That fallback needs a corresponding test disposition.
- **Suggestions:** State how F4’s test and minimum count behave if its allowed fallback occurs.
- **Risk Assessment: LOW** — The previous executable ordering contradiction is removed.

## 18-09

**Summary:** Staging cleanup and executable-member containment are substantially improved, but the smoke contract still has an observation gap.

- **Cycle-1 H4/H5 — FULLY RESOLVED:** Extraction now enters the cleanup region, and resolved members must remain inside staging (`18-09-PLAN.md:154–166`), correcting `installer/download.py:322–329` and the following file check at `installer/executors.py:57`.
- **Strengths:** Hash-before-smoke and smoke-before-swap preserve the existing good installation.
- **Concerns — HIGH:** Loader text is checked only when `run_output` raises (`18-09-PLAN.md:162–164`). On exit 0, that helper returns stdout and discards captured stderr (`installer/run.py:93–108`), so a wrapper can print a loader failure to stderr and still pass the promised loader-error check.
- **Suggestions:** Inspect stderr regardless of exit status; add an exit-0/loader-stderr fixture. Also explicitly reject or normalize absolute links into `.new`, which become broken after relocation.
- **Risk Assessment: HIGH** — The stated smoke guarantee is stronger than the information its proposed helper exposes.

## 18-10

**Summary:** The cache format is appropriate, but the task boundary prevents the first required commit from passing.

- **Strengths:** Per-entry malformed-digest handling now avoids `_str_map`’s whole-map rejection (`installer/version_cache.py:251–256`; `18-10-PLAN.md:136`).
- **Concerns — HIGH:** Task 1 requires a digest save/load round trip and an encode/decode acceptance check (`18-10-PLAN.md:99,115`), but implements only encoding (`:105`). Decoding is deferred to Task 2 (`:136`); the current decoder constructs entries without digests (`installer/version_cache.py:104–117`).
- **Suggestions:** Move basic decoding into Task 1. Keep malformed-input hardening and mixed-map coverage in Task 2.
- **Risk Assessment: HIGH** — Correctly following Task 1 cannot satisfy its own green-before-commit gate.

## 18-11

**Summary:** Sharing the existing staged app update flow is preferable to maintaining separate install and update mechanisms.

- **Strengths:** The revised pre-swap executable and containment checks (`18-11-PLAN.md:130`) address validation currently delayed until after replacement (`installer/apps.py:155–162,186–194`).
- **Concerns — MEDIUM:** Internal symlinks require relocation-aware handling here too. A CLI resolving inside the staged bundle can still contain an absolute reference to its temporary location.
- **Suggestions:** Reuse the explicit absolute-link policy established in 18-09 and test it before bundle replacement.
- **Risk Assessment: MEDIUM** — The previous executability gap is fixed; relocation semantics remain an edge to define.

## 18-12

**Summary:** Per-member findings fix the original shared-archive omission, but cached verification still omits part of the install contract.

- **Cycle-1 H6 — FULLY RESOLVED:** Shared URLs now feed separate member checks and findings (`18-12-PLAN.md:154–160`), matching broot’s actual distinct members (`installer/registry.toml:2127–2135`).
- **Strengths:** Reuses the install resolver and lists archives without extracting them.
- **Concerns — HIGH:** State identity is only URL/member plus content fingerprint (`18-12-PLAN.md:160`). Changing `strip` can therefore return cached `ok` although installation can no longer locate the member; extraction actually applies `strip` (`installer/download.py:412–419`).
- **Concerns — MEDIUM:** Archive-parser failures are not classified, and pinned GitHub hashes are compared with latest-release metadata rather than necessarily the URL’s tag (`18-12-PLAN.md:160`; `installer/versions.py:329`).
- **Suggestions:** Include extraction settings in verification identity; classify corrupt archives; separate requested-tag integrity from latest-version discovery.
- **Risk Assessment: HIGH** — A cached pass can certify a registry entry that no longer installs correctly.

## 18-13

**Summary:** The guarded writer is well bounded, but the revised post-write report is not yet consistently the registry-as-written report.

- **Cycle-1 H7 — PARTIALLY RESOLVED:** The ordinary successful-bump verdict is now specified (`18-13-PLAN.md:135,144`), but failure and replacement cases remain contradictory.
- **Strengths:** The semantic guard and per-tool all-or-nothing pin edits protect registry integrity (`18-13-PLAN.md:106,142`).
- **Concerns — HIGH:** A failed explicit Sublime candidate retains the healthy old findings plus only a report line (`:142–144`). It can therefore remain in `passed_tools()` and receive a new date, violating the unchanged-date test (`:133`).
- **Concerns — HIGH:** Successful bumps remove only “newer stable” findings (`:144`); obsolete 404/member drift from replaced pinned targets survives and falsely fails the final report.
- **Suggestions:** Represent rejected candidates in verdict/dating eligibility; replace findings for superseded pinned targets while retaining unrelated findings.
- **Risk Assessment: HIGH** — Both paths can misreport or misdate the registry.

## 18-14

**Summary:** The workflow correctly separates reporting permissions, PR gates, and incremental verification state.

- **Strengths:** Split cache restore/save and per-target atomic saves address interrupted checks (`18-14-PLAN.md:202–212`); existing CI remains a separate install/validate/test workflow (`.github/workflows/ci.yml:29–34`).
- **Concerns — LOW:** Backticks alone do not safely quote arbitrary upstream text containing backticks or newlines; the issue-body safety claim is broader than the formatting rule.
- **Suggestions:** Escape embedded delimiters/control characters or use a code-span renderer that selects a safe delimiter.
- **Risk Assessment: LOW** locally — The larger reporting risk comes from 18-17’s verdict logic, not workflow wiring.

## 18-15

**Summary:** Saved logs and a separate read-only rerun provide a useful final data gate.

- **Cycle-1 H6 — FULLY RESOLVED** for the live-run precondition; **H7 — PARTIALLY RESOLVED** because it still inherits 18-13’s report contradictions (`18-15-PLAN.md:159–175`).
- **Strengths:** The source really contains the five literal pins targeted here (`installer/registry.toml:2262,2282,2290,2756,2764`), and acceptance does not rely solely on the write run.
- **Concerns — MEDIUM:** The procedure assumes per-target passing evidence appears in the saved report, while 18-12’s formatter primarily specifies drift/inconclusive sections.
- **Suggestions:** Explicitly require successful target lines, including member and platform identity, before relying on them for ledger citations.
- **Risk Assessment: MEDIUM** — Execution should wait for verifier/writer corrections; the final read-only gate itself is sound.

## 18-16

**Summary:** Consolidating staged fetches and updating through the same verification sources reduces duplicated security-sensitive behavior.

- **Strengths:** The production-composition update test covers the actual context construction currently lacking a release resolver (`installer/update.py:329–333`; `18-16-PLAN.md`, Task 1).
- **Concerns:** No new blocking concern. Declared hashes are explicitly honored even for directly constructed methods (`18-16-PLAN.md`, Task 2).
- **Suggestions:** Retain the existing live-tree preservation assertions alongside the new digest assertions; checking only the failed outcome would be insufficient.
- **Risk Assessment: LOW** — Clear reuse and deletion, with relevant failure-path tests.

## 18-17

**Summary:** Version ranking and rate-limit evidence are improved, but the run-wide outage rule contradicts the new per-repo behavior.

- **Cycle-1 H8 — FULLY RESOLVED:** Uses the existing comparator (`18-17-PLAN.md:125`; `installer/versions.py:213–236`).
- **Cycle-1 H9 — PARTIALLY RESOLVED:** Header-based classification is correct (`18-17-PLAN.md:127`), but the blanket zero-success rule (`:129`) can still block a plain-403 repo.
- **Strengths:** Explicitly separates incomparable tags from newer releases.
- **Concerns — HIGH:** The required plain-403-plus-HEAD-drift test expects exit 1 (`:116`), yet its only release read fails, compelling exit 2 under `:129`. All-404 runs similarly become “outages,” suppressing genuine drift issues.
- **Suggestions:** Distinguish transport outage from received HTTP evidence; do not infer whole-run network failure merely from zero successful release reads.
- **Risk Assessment: HIGH** — Correct execution currently conflicts with an explicit acceptance test and can silence drift reporting.

## 18-18

**Summary:** Fresh-container retries and specific ruff artifacts make the acceptance evidence substantially more credible.

- **Cycle-1 H10 — FULLY RESOLVED / previously refuted:** Cleanup remains required at every stop; successful pass2 already removes the container (`scripts/container-e2e-verify.sh:477–478`).
- **Cycle-1 H11 — FULLY RESOLVED:** Retries require bootstrap replacement (`18-18-PLAN.md:96,127`), rather than `resync`, which only streams and syncs the workspace (`scripts/container-e2e-verify.sh:225–230`).
- **Strengths:** Exact preview and verification rows replace an uninformative “ruff appeared somewhere” check.
- **Concerns — LOW:** Timestamp ordering is supporting evidence, not proof of container identity.
- **Suggestions:** Record the final container ID with the transcripts if readily available; retain the exact artifact assertions.
- **Risk Assessment: LOW** — Runtime availability remains an execution precondition, not something this review established.

## 18-19

**Summary:** PATH restoration and narrowed smoke attribution address the two original manager-smoke concerns.

- **Cycle-1 H12/H13 — FULLY RESOLVED:** Failed smoke restores PATH; declared directories select their binary, while no-directory claims are explicitly limited (`18-19-PLAN.md:150–158`). This corrects the current persistent prepend (`installer/engine.py:162–164`; `installer/locations.py:103–108`).
- **Strengths:** The test sandbox includes indirect default-install callers, which genuinely reach the engine (`installer/app.py:139`; `installer/session.py:73,173`).
- **Concerns — MEDIUM:** A failed manager smoke restores PATH but not installed artifacts. The broad SPEC promise of no remaining linked binary is therefore not guaranteed for manager methods (`18-SPEC.md:48–49`).
- **Suggestions:** Explicitly scope that guarantee to staged download/app methods, or define safe manager-specific cleanup. Do not add generic deletion without ownership proof.
- **Risk Assessment: MEDIUM** — The revised attribution is honest, but failure-artifact semantics need reconciliation.

## Overall assessment

**Status: Issues Found — revise before execution.**

Most cycle-1 concerns are resolved. **H7 and H9 remain partially resolved**; the strongest new blockers are:

1. **18-10:** Task 1 requires decoding before implementing it.
2. **18-12:** Cached verification ignores changed extraction settings.
3. **18-13:** Candidate failure/dating and superseded-target reporting conflict.
4. **18-17:** Zero-success outage detection contradicts per-repo error handling.
5. **18-09:** Successful stderr is unavailable to the promised loader-error check.

The plan set is substantially stronger, but these are contract corrections, not optional polish.

Skipped tests, live upstream checks, and container execution; no files were changed. Runtime success and current upstream digest availability remain unverified.

---

## Consensus Summary

One reviewer ran (`opencode-plan-review`, the only entry in `review.default_reviewers`), so there is no cross-reviewer consensus and the consensus gate does not apply: every HIGH that this reviewer raised and the orchestrator confirmed in the source counts. The review is source-grounded. It cites about 40 `file:line` locations, carries no discount marker, and covers all 19 plan ids (coverage check: complete). The reviewer was also given the cycle-1 HIGH table and asked for a verdict on each. The orchestrator checked those verdicts and every new HIGH against the revised plans (89ac279) and the source at `7fecef2`.

### Agreed Strengths
- (single reviewer) Ten of the 13 cycle-1 HIGHs are fully resolved by the revisions: H1, H2, H3, H4, H5, H6, H8, H11, H12 and H13. H10 was already refuted in cycle 1. The fixes reuse existing seams: `versions.is_outdated`, `staged_member` containment, `prepend_path` restore, and the setup.py `__main__` PATH filter.

### Agreed Concerns
- None (single reviewer). The highest-priority single-reviewer concerns are 18-13's post-write verdict, which still misdates or misreports in two cases (H7 is partial), 18-17's zero-success outage rule (H9 is partial), 18-12's cached state that ignores `strip`/`archive`, and 18-10 Task 1, which requires a decode it does not implement.

### Divergent Views
- None (single reviewer).

### Cycle-1 HIGH resolution (orchestrator, source-checked)

| # | Plan | Cycle-1 HIGH | Revised plan / source evidence | Status |
|---|------|--------------|-------------------------------|--------|
| H1 | 18-02 | Pinned negative assertions conflict with the new parser | 18-02-PLAN.md Task 2 names the four tests and migrates them. Acceptance greps forbid the two old negatives. `tests/test_versions.py:313,424-425` are the lines that get migrated. Live check: the lazygit date tokens (`date=2025-07-19T11:51:45Z,`) do not parse today, so the fixture row with the full string is sound | FULLY RESOLVED |
| H2 | 18-05 | An activated venv keeps `.venv/bin` on PATH | Task 3 adds `drop_project_venv_from_path` and calls it first in the `__main__` block. `setup.py` ends with that block, and the Makefile launchers and `install.sh:88` all run `setup.py`. An AST test plus a control/filtered probe pair cover it. Ledger L-18-08 records the reading | FULLY RESOLVED |
| H3 | 18-08 | glab natives are expected after brew | 18-08-PLAN.md:99 now expects `["dnf","brew"]`, `["brew"]` (immutable) and `["apt"]` (no brew). This matches `installer/resolve.py:13-29` (native 30 before brew 40, natives skipped on immutable), `:65` (`brew` needs `has_brew`) and `installer/platform.py:20-24` (field order `os, arch, immutable, has_brew`) | FULLY RESOLVED |
| H4 | 18-09 | A failed extraction leaves a partial `.new` | One cleanup `try` now runs from `_extract_into` through the pre-swap checks. Today `_extract_into` sits before the first `try` (`installer/download.py:323`). `test_failed_extraction_leaves_no_staged_tree` covers it | FULLY RESOLVED |
| H5 | 18-09 | A symlinked member is followed out of staging | `staged_member` uses `resolve(strict=True)`, then `is_relative_to(root)` and a regular-file check before chmod and smoke. There is an outside-symlink test and an inside-symlink test, and 18-11 reuses the helper. Zip extraction lists only the member (`installer/download.py:366`), so an internal-link zip member fails closed instead of escaping | FULLY RESOLVED |
| H6 | 18-12 (+18-15) | Per-url dedup skips per-member checks | Findings and state are now per (tool, url, member). HEAD and download are de-duplicated per url. There is a broot shared-zip test (`installer/registry.toml:2123-2136`), and 18-15's precondition runs it. Ledger L-18-11 records the change | FULLY RESOLVED |
| H7 | 18-13 (+18-15) | The `--write` verdict is undefined | The ordinary bump path is now defined (18-13-PLAN.md:144, `test_write_run_after_a_bump_reports_the_registry_as_written`). Two gaps remain. (a) A rejected candidate keeps the tool's original all-ok findings, so the tool stays in `passed_tools()` and gets dated. That contradicts `test_one_failing_method_blocks_the_whole_tool_bump` ("`verified` is unchanged", :133). (b) An applied bump drops only the `newer stable release` findings, so any drift on the superseded old-pin targets (for example, a 404 on the old asset) survives in the "registry as written" report | PARTIALLY RESOLVED (two HIGHs below) |
| H8 | 18-17 | Inequality is labelled "newer" | `is_outdated(version, tag)` (`installer/versions.py:213-236`) handles True/False/None. An incomparable tag is a separate inconclusive finding. Acceptance grep and tests cover it. Ledger L-18-13 records it | FULLY RESOLVED |
| H9 | 18-17 | Every 403 blocks the run | Header evidence (429, or 403 with `X-RateLimit-Remaining: 0`/`Retry-After`) is now required for a rate limit. A plain 403 is a per-repo inconclusive finding. A gap remains: `blocked = "no GitHub release read succeeded"` (18-17-PLAN.md:129) counts a received 403/404 response as a failed read. So a run where every attempted release read got an HTTP answer (a plain 403 or a 404 "release not found" drift) is still reported as a whole-run outage and suppresses the issue. Whether `test_forbidden_without_rate_limit_evidence_does_not_block` (:116) passes depends on how its fixture is built | PARTIALLY RESOLVED (HIGH below) |
| H10 | 18-18 | No teardown at a Task 1 stop | Refuted in cycle 1. The executor rules remove the container at any stop, and `cmd_pass2` removes it on success (`scripts/container-e2e-verify.sh:477`) | FULLY RESOLVED (refuted) |
| H11 | 18-18 | A `resync` retry is not a clean install | Every retry restarts from `bootstrap --replace`. Task 1's verify requires the pass1 and probe logs to be newer than the bootstrap log. `cmd_resync` is unchanged (`scripts/container-e2e-verify.sh:225-230`). The exact ruff rows match `render_verification`/`render_uninstall` (`installer/render.py:173-175,299-300`) | FULLY RESOLVED |
| H12 | 18-19 | PATH is not restored after a failed smoke | `path_before` is recorded before the prepend and restored on `ExecutorError`. `test_failed_smoke_restores_path_before_the_next_method` and an acceptance grep cover it | FULLY RESOLVED |
| H13 | 18-19 | `which(cmd)` can smoke a pre-existing binary | A declared `bin_dir/<cmd>` is smoked first. Without a `bin_dir`, the claim is narrowed to "the command PATH runs" (Ledger L-18-09) and pinned by two tests | FULLY RESOLVED |

### New HIGHs this cycle (orchestrator, source-checked)

| # | Plan | HIGH | Source check | Status |
|---|------|------|--------------|--------|
| N1 | 18-09 | Loader errors are checked only when `run_output` raises; a loader message on an exit-0 run passes | Confirmed: `installer/run.py:93-108` returns `completed.stdout` and drops stderr on success. 18-09-PLAN.md:30 says that a loader error in stderr fails and that exit 0 passes, without saying which rule wins when both hold. D-06 says "a `GLIBC_`/loader error in stderr" fails. Real impact is limited: the dynamic loader itself exits 127, so only a wrapper that swallows the exit code is affected. It still counts (single reviewer) | Open |
| N2 | 18-10 | Task 1 requires a digest round trip, but its action only encodes | Confirmed. 18-10-PLAN.md Task 1 requires `test_digests_round_trip_through_the_cache_file` and the acceptance check `grep -c '"digests"' ... >= 2 (encode and decode)`. Its action changes only `VersionCacheEntry` and `save_version_cache`; decoding is Task 2. The current `_entry_from_raw` (`installer/version_cache.py:104-117`) builds entries without digests | Open |
| N3 | 18-12 | Cached `ok` ignores the extraction settings | Confirmed. The state key is `<url>#<member>`, and the fingerprint covers only the content (18-12-PLAN.md:60,160). A registry edit to `strip` (or to `archive`/`raw`) on an unchanged asset hits the cache and stays `ok`, but extraction applies `strip` (`installer/download.py:361-377`). verify-registry is not in the PR gate, so nothing else catches it | Open |
| N4 | 18-13 | A rejected `--candidate` still gets a new `verified` date | Confirmed. See H7(a). The final report keeps the old all-ok findings, `passed_tools()` includes the tool, and Task 1 writes `verified`. This contradicts the plan's own test at 18-13-PLAN.md:133 | Open |
| H7b | 18-13 | An applied bump leaves superseded old-pin drift in the as-written report | Confirmed. See H7(b) | Open (partial) |
| H9b | 18-17 | The zero-success rule treats received HTTP 403/404 answers as an outage | Confirmed. See H9 | Open (partial) |

18-15's "H7 partial" restates H7b/N4 and resolves with them. It is not counted twice.

### Non-HIGH findings this cycle (orchestrator disposition)

| Plan | Sev | Finding | Disposition |
|------|-----|---------|-------------|
| 18-01 | MEDIUM | `_write(seed_verified=True)` inserts `verified` into fixtures that also set it (string, integer, datetime, future and method-table cases). A duplicate key raises `TOMLDecodeError` before the loader runs, and the `2026-10-16 loads` case fails | Confirmed (18-01-PLAN.md:158-172). Actionable |
| 18-02 | LOW | Quotes are stripped before punctuation and `version=`, so `version="1.2.3",` is not normalized | Confirmed by tracing the order (18-02-PLAN.md:139). Actionable (reorder or document) |
| 18-03 | LOW | The git probe argv is bare `xcode-select`, while T-18-05 claims "absolute paths" | Confirmed (18-03-PLAN.md:116,202). Actionable |
| 18-05 | LOW | Only `<repo>/.venv` is filtered | Already explicit in the plan (the test keeps `<other>/.venv/bin`). Not actionable |
| 18-07 | MEDIUM | Function identity selects the digest path | Cycle-1 MEDIUM, already incorporated through the behavioural default-resolver test and the ledger. Not actionable |
| 18-08 | LOW | F4's allowed "not applied" fallback conflicts with "eight tests pass" | Confirmed (18-08-PLAN.md:148,152,158). Actionable |
| 18-11 | MEDIUM | An absolute link inside the staged bundle breaks after relocation | Orchestrator: not a real path. An upstream archive cannot hold an absolute link into a per-host `.new` path that did not exist when it was built, and any other absolute target resolves outside staging and is rejected by `staged_member`. Actionable only as a rejection to record in the 18-11 ledger |
| 18-12 | MEDIUM | Corrupt archives (`tarfile.ReadError`, `zipfile.BadZipFile`) are not classified | Confirmed: no classification in 18-12-PLAN.md. Actionable |
| 18-12 | MEDIUM | A pinned GitHub hash is compared with latest-release metadata | Orchestrator: benign. The comparison runs only "when present", and the versioned asset name exists in the latest release only when pin == latest. Actionable only as a clarification or rejection to record |
| 18-14 | LOW | Backticks alone do not escape values that contain backticks or newlines (error-reason text) | Actionable (strip or escape, or pick a delimiter) |
| 18-15 | MEDIUM | 18-15 must cite `ok` findings per method/arch, but 18-12's `format_report` lists only drift, inconclusive, not-checkable and notes | Confirmed (18-12-PLAN.md:120 vs 18-15-PLAN.md:35,172). Actionable (print ok targets, or a passed section with tool/url/member) |
| 18-18 | LOW | mtime ordering is not proof of container identity | Actionable (record the container ID with the transcripts) |
| 18-19 | MEDIUM | SPEC acceptance "a single failing method leaves no linked binary" (18-SPEC.md:115) cannot hold for manager kinds | Confirmed. Actionable (scope the guarantee to download/app kinds in 18-19, or define manager cleanup) |

## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). It ran on 2026-10-15 over all 19 revised plans at `7fecef2`.

**Authority.** `drift-guard authority --raw` returned `intel` (config `grep`, upgraded by `intel.enabled: true`). `.planning/intel/` lists only 6 CLI entry points, so under that authority every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO). They were not treated as verified or missing on that basis. Supplementary grep evidence was collected over `git ls-files` outside `.planning/`. `drift-guard severity` under `intel` gives: VERIFIED -> none, MISSING -> needs-acknowledgement (no hardBlock), AMBIGUOUS -> MEDIUM, UNCHECKABLE -> INFO. No verdict produced a hardBlock.

**Enumeration.** Every backticked token in the 19 PLAN.md files with a symbol shape (`module.func`, `Class.attr`, `path::name`, `name(...)`, identifiers with `_`/`.`/camelCase), a path shape or a `--flag` shape was enumerated, then de-duplicated per kind and name. Names in any plan's "Artifacts this phase produces" section were excluded (they are new by design). Result: 280 distinct cited tokens. 226 have grep evidence (a declaration or reference in the source, or an existing path or flag), and 54 were not found.

Spot-verified declarations added by the revisions: `_as_object` (`installer/version_cache.py:89`), `_str_map` (`:246`), `is_outdated` (`installer/versions.py:213`), `perform_update` (`installer/update.py:193`), `installed_for_order` (`installer/execute_screen.py:503`), `_not_present` (`tests/test_app.py:3347`), `cmd_resync` (`scripts/container-e2e-verify.sh:225`), `sync_workspace` (`:192`), `_validate_app` (`installer/apps.py:186`), `staged_sibling` (`installer/atomic.py:65`), `atomic_write_text` (`:56`), `expected_sha256`/`sha256_file` (`installer/checksums.py:23,55`), `attributed_install` (`installer/execute_screen.py:201`), `with_sensitive_confirm`/`run_installs` (`installer/session.py:71,168`), `render_uninstall`/`render_verification` (`installer/render.py:168,285`), and `Platform` field order (`installer/platform.py:20-24`).

Not-found tokens and their acknowledgement (needs-acknowledgement; none is a hallucinated reference to existing code):

| Cited at | Token | Why absent |
|---|---|---|
| each plan's `<output>` | `18-NN-SUMMARY.md` (19) | execution output created by each plan |
| 18-01:63, 18-06:237 | `model.py`, `resolve.py` | bare filenames of `installer/model.py` and `installer/resolve.py` (exist) |
| 18-02:67 | `D-registry-user-part1.md`, `E-registry-user-part2.md` | exist under `.planning/research/audit-2026-10-13/` (outside the grep corpus) |
| 18-18:78 | `detect-container-runtime.sh` | exists as `scripts/detect-container-runtime.sh` |
| 18-05:99 | `UV_PROJECT_ENVIRONMENT` | plan asserts that it is set nowhere (correct) |
| 18-12:53, 18-14:32, 18-14:101 | `installer/verify_registry.py`, `.github/workflows/verify-registry.yml`, `tests/test_makefile.py` | created by 18-12, 18-14 and 18-05 |
| 18-12:56, 18-13:68 | `--write`, `--candidate`, `--issue`, `--state` | verify-registry flags created by 18-12, 18-13 and 18-14 |
| 18-05:31, 18-05:259 | `--isolated`, `--no-dev`, `--exact` | uv CLI flags (external) |
| 18-01:94, 18-08:66, 18-14:30 | `--no-verify`, `--no-modify-path`, `--body-file` | git, opencode-installer and gh flags (external) |
| 18-09:152 | `--custom` | fixture argv in a new test |
| 18-03:215 | `java_home` | macOS `/usr/libexec/java_home` (external) |
| 18-05:128 | `_recipes()` | private helper in the new `tests/test_makefile.py` |
| 18-08:90 | `test_audit_fix_` | test-name prefix |
| 18-09:30, 18-09:164 | `GLIBC_`, `WAYLAND_DISPLAY` | loader string literal and environment variable name |
| 18-12:78,120,147,160; 18-14:140 | `urllib.error.HTTPError`, `TimeoutError`, `namelist()`, `getnames()`, `zipfile.ZipFile(...).namelist()`, `tempfile.TemporaryDirectory`, `tempfile.NamedTemporaryFile` | stdlib |
| 18-12:83 | `tests/fixtures/` | plan asserts that it does not exist (correct) |
| 18-14:32 | `workflow_dispatch` | GitHub Actions trigger key (external) |
| 18-16:147 | `installer/assets.py::render_pinned_url` | plan records the deviation: the renderer is `download.pinned_url` (correctly absent) |

**UNCHECKABLE / skipped.**
- Signatures (argument lists, return types) cannot be asserted under `intel`/`grep`. Names only were checked.
- External surfaces are not in the repo: uv/gh/git flags, GitHub REST rate-limit headers, Actions semantics, upstream asset names and digests, and macOS binaries.
- Behaviour claims were spot-checked against the tree. `extract_observed_version` on the full lazygit line returns None today, and no date/commit token in it parses. `run_output` maps OSError to exit 127 and drops stderr on success (`installer/run.py:106-108`). `_replace_archive` extracts outside any cleanup `try` (`installer/download.py:323`). `cmd_pass1` cats the setup output to stdout. `render_uninstall` prints `  <path>` with `soft_wrap=True`.
- Live network counts (18-RESEARCH.md digests 153/171) were not re-probed.

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 18`): verdict `lag`. STATE.md says "Ready to execute" (rank 1), ROADMAP.md says "Not started" (rank 0), and STATE.md is the authority. One non-terminal step apart, so this is not a finding.
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction. 18-05 adds an activated-venv truth beyond SC4, which is sanctioned (plans may add truths). The ROADMAP plan list line for 18-05 was updated in 89ac279 to match.
- **Requirement IDs** (ROADMAP.md authority): REG-01..REG-10 each appear in at least one plan's `requirements:`. No plan cites an ID outside the roadmap.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority): no contradiction. Each new revision maps to an amendment recorded inside CONTEXT.md:
  - L-18-08: 18-05's entry-point filter.
  - L-18-09: 18-19's bin_dir smoke target (amends D-06's `which`).
  - L-18-10: 18-17's rate-limit evidence.
  - L-18-11: 18-12's per-target state.
  - L-18-12: 18-13's as-written verdict.
  - L-18-13: `is_outdated` in 18-17 and the independent quote strip in 18-02.
- One near-miss, noted but not flagged: D-06 says that a "`GLIBC_`/loader error in stderr" fails a smoke, while 18-09's truth says that exit 0 passes. This is the N1 review finding, a gap in the plan's mechanism, and not a CONTEXT ↔ PLAN contradiction about one defined term, because 18-09 also lists the loader-error rule.
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
