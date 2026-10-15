---
phase: 18
reviewers: [opencode-plan-review]
reviewed_at: 2026-10-15T12:24:25Z
plans_reviewed: [18-01-PLAN.md, 18-02-PLAN.md, 18-03-PLAN.md, 18-04-PLAN.md, 18-05-PLAN.md, 18-06-PLAN.md, 18-07-PLAN.md, 18-08-PLAN.md, 18-09-PLAN.md, 18-10-PLAN.md, 18-11-PLAN.md, 18-12-PLAN.md, 18-13-PLAN.md, 18-14-PLAN.md, 18-15-PLAN.md, 18-16-PLAN.md, 18-17-PLAN.md, 18-18-PLAN.md, 18-19-PLAN.md]
models:
  opencode-plan-review: "router-env/my-plan-review"
model_sources:
  opencode-plan-review: "pinned"
---

# Cross-AI Plan Review — Phase 18

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review (opencode-plan-review)

## 18-01

**Summary:** The schema plan addresses a real gap: `load_tools` currently passes non-structural method keys through without a per-kind allowlist (`installer/model.py:639-668`). The shipped-registry test is a useful guard against closing the schema too narrowly.

- **Strengths:** Tests unknown and cross-kind keys, bare methods, and the real registry; preserves the existing per-kind value checks.
- **Concerns:** **LOW** — The new allowlist check runs after `os` and `arch` are removed from `params` (`18-01-PLAN.md`, Task 1). Those structural keys rely on the existing checks at `installer/model.py:656-665`, but preservation of those checks is not an explicit acceptance test.
- **Suggestions:** Add a regression assertion that malformed `os` and `arch` values still fail after the schema change.
- **Risk Assessment: LOW** — The change is well bounded; the remaining risk is accidentally weakening adjacent validation.

## 18-02

**Summary:** Tightening the glued-name boundary targets the observed `-1` false version, and one normalization path is appropriate for the three public parsers (`installer/versions.py:71-84,99-133,172-210`).

- **Strengths:** Keeps ordinary version matching intact and specifies positive fixtures for lazygit and procs.
- **Concerns:** **HIGH** — Existing assertions say `version=0.64.1,` is not extracted and procs output is unparseable (`tests/test_versions.py:313,417-425`). Task 2 mentions adjusting `tests/test_version_status.py` if needed, but not these directly conflicting tests. A correct implementation will fail the required full suite.
- **Suggestions:** Explicitly replace those negative assertions with the new expected results, retaining malformed-token cases.
- **Risk Assessment: MEDIUM** — The behavior is clear, but the test migration is incomplete.

## 18-03

**Summary:** The exact-path macOS stub table fits the current `is_installed` flow: PATH is checked first, then declared paths and bundles (`installer/status.py:18-66`). Exposing a reason in the existing audit table is sensible.

- **Strengths:** Includes real-JDK/CLT, alternate-install-path, and non-macOS tests.
- **Concerns:** **MEDIUM** — The proposed `audit` first calls `is_installed` and then independently calls `macos_stub_reason` for missing tools (`18-03-PLAN.md`, Task 1). That can run the same five-second probe twice and, if its result changes, display “missing” without the corresponding reason. The audit is used by both CLI and TUI (`installer/app.py:165-167`, `installer/execute_screen.py:517-520`).
- **Suggestions:** Derive installation and reason from one probe result, or test and define how inconsistent consecutive results are presented.
- **Risk Assessment: MEDIUM** — Primarily a latency and truthful-display risk on macOS.

## 18-04

**Summary:** `apps.cli_spec` is the right single source for the link name: install, update, and uninstall already consume it (`installer/apps.py:47-65,80-100,116-130`; `installer/uninstall.py:47-53`).

- **Strengths:** The draw.io link and removal tests exercise both sides of the naming contract.
- **Concerns:** **MEDIUM** — Task 1 honors `cli_name` and commits before Task 2 validates it (`18-04-PLAN.md`, Tasks 1–2). In that intermediate commit, a malformed registry name can reach link-path construction, contrary to the promised pre-side-effect validation.
- **Suggestions:** Implement the small `cli_name` validation in Task 1; leave the exhaustive invalid-input tests to Task 2 if separate tasks are useful.
- **Risk Assessment: LOW** for the final design; **MEDIUM** for the required individually valid commits.

## 18-05

**Summary:** The plan reaches the actual launch sites—six Makefile recipes, `install.sh`, and the container harness—without removing dev dependencies from validation (`Makefile:14-51`; `install.sh:87-88`; `scripts/container-e2e-verify.sh:247-263`).

- **Strengths:** Tests launcher recipes separately from quality gates and retains the dev-synced venv in the container as a meaningful control.
- **Concerns:** **HIGH** — `uv run --isolated --no-dev` stops uv from adding the project venv; it does not remove `.venv/bin` already present on the inherited `PATH`. The plan’s unconditional claim that the launcher cannot resolve dev ruff (`18-05-PLAN.md`, must-haves and Task 1) is therefore too strong for a shell with an activated venv.
- **Suggestions:** Either remove the project venv path at the launcher boundary and test an activated-venv PATH, or narrow the stated guarantee and document that limitation.
- **Risk Assessment: MEDIUM** — Normal launch is covered, but the original ownership error can persist in an activated environment.

## 18-06

**Summary:** The registry, probe, test, and stale-cache changes form a coherent removal of the duplicate draw.io row and dead owner probe.

- **Strengths:** Includes a registry-driven stale-id regression and accounts for changed catalog counts.
- **Concerns:** **MEDIUM** — The added ruff `uv-tool` fallback is placed after release methods and before brew (`18-06-PLAN.md`, Task 3). `resolve_methods` sorts by kind rank, not merely row position: `uv-tool` is 20 and brew is 40 (`installer/resolve.py:13-28,81-84`). A failed release will therefore try a uv install before an available brew install.
- **Suggestions:** State that preference as intentional and test the resolved ladder, or change the fallback strategy if brew should precede uv.
- **Risk Assessment: MEDIUM** — The cleanup is straightforward; the new fallback changes install behavior.

## 18-07

**Summary:** Reading tag and digest from one release response is a strong way to avoid mismatched “latest” snapshots. Reusing `ChecksumMismatch` fits the current engine’s fail-fast contract (`installer/engine.py:95-110`).

- **Strengths:** Covers match, mismatch, missing digest, and user-visible verification reason.
- **Concerns:** **MEDIUM** — Production digest selection depends on `resolve_tag is resolve_github_tag` (`18-07-PLAN.md`, Tasks 1–2). Today the tag resolver travels through `installer/session.py:168-173,218`, but a legitimate caching wrapper or partial would silently select an empty digest map. The proposed signature/AST test detects some rewiring, not whether a composed production install actually verifies.
- **Suggestions:** Pass an explicit release resolver at the composition boundary, or add a behavioral test through that boundary with a digest-backed install.
- **Risk Assessment: MEDIUM** — The hash path is sound once selected; selection is fragile.

## 18-08

**Summary:** The audit ledger and conditional upstream-script check make the data corrections reviewable instead of treating every audit suggestion as mandatory.

- **Strengths:** Keeps the already-fixed Sublime member out of the diff and requires evidence before adding kitty’s macOS method.
- **Concerns:** **HIGH** — The plan says glab’s new native methods rank *after* brew (`18-08-PLAN.md`, Task 1), but native kinds rank 30 and brew ranks 40 (`installer/resolve.py:23-28,81-84`). The stated ladder test cannot pass with that expectation.
- **Suggestions:** Correct the expected order and its rationale, or explicitly change the resolver if brew-first is a requirement. Keep the complete 35-row ledger in the designated `18-08-SUMMARY.md`, as the plan’s output section requires.
- **Risk Assessment: MEDIUM** — A concrete ordering contradiction needs resolution before execution.

## 18-09

**Summary:** Hash-before-smoke and smoke-before-swap are the right ordering for downloaded binaries. Reusing the existing replacement path avoids a second swap mechanism.

- **Strengths:** Tests a broken binary with and without fallback, preservation of a good install, custom argv, and the update path’s no-smoke rule.
- **Concerns:** **HIGH** — The proposed cleanup covers member-check and smoke failure, but extraction occurs before the existing `_replace_archive` cleanup blocks (`installer/download.py:311-335`; `18-09-PLAN.md`, Task 1). A failed extractor can leave a partial `.new` tree. **HIGH** — The proposed `(new / member).is_file()` follows symlinks; a malicious archive member pointing outside staging could pass, then be chmodded and executed. The current link helper also uses a following file check (`installer/executors.py:49-62`). **MEDIUM** — Adding `env` to `run_output`’s `subprocess.run` call changes the keyword contract of the strict fake in `tests/test_run.py:117-140`, but that test file is not assigned.
- **Suggestions:** Clean staging on *every* extraction/validation failure; reject symlinked executable members or constrain their resolved path to staging; add extraction-failure and symlink-member tests. Include `tests/test_run.py` in the env change.
- **Risk Assessment: HIGH** — The two staging cases undermine the central “broken download never touches anything else” guarantee.

## 18-10

**Summary:** Storing release digests alongside versions is a useful, backward-compatible handoff to Phase 19; the plan preserves previous values after a failed refresh.

- **Strengths:** Specifies round-trip, old-cache, malformed-cache, and failed-refresh tests.
- **Concerns:** **MEDIUM** — `_str_map` rejects an entire mapping if one value is not a string (`installer/version_cache.py:246-256`). Reusing it before filtering, as Task 2 proposes, loses a valid digest beside one malformed entry. **LOW** — Counting one mocked resolver call does not itself establish one underlying API fetch.
- **Suggestions:** Decode digest entries independently and add a mixed valid/invalid map fixture; rely on an integrated fetch-count test for the one-read claim.
- **Risk Assessment: MEDIUM** — Corrupt cache data should not discard unrelated valid proof.

## 18-11

**Summary:** Folding app install into the existing staged update flow is a good way to add checksum and smoke protection without maintaining two app-swap implementations (`installer/apps.py:103-176`).

- **Strengths:** Covers pinned mismatch before extraction, unpinned attribution, preservation of an existing bundle, and update without smoke.
- **Concerns:** **MEDIUM** — The proposed pre-swap staged CLI check requires a regular file but not executability (`18-11-PLAN.md`, Task 1). The existing `_validate_app` checks executability only after swap (`installer/apps.py:186-194`), causing an avoidable swap and rollback for a non-executable CLI.
- **Suggestions:** Check the staged CLI’s executable condition before moving the bundle, while retaining post-swap validation.
- **Risk Assessment: MEDIUM** — Rollback may work, but preventable post-swap failures raise the chance of disrupting a working app.

## 18-12

**Summary:** Reusing `download.resolve_target` grounds the checker in the install URL and member renderer (`installer/download.py:99-126`). Separating missing assets from network failures is appropriate.

- **Strengths:** Offline fixtures cover renamed assets, hashes, archive members, cache hits, and read-only registry behavior.
- **Concerns:** **HIGH** — Task 1 deduplicates *findings* by URL per tool (`18-12-PLAN.md`, Task 1). Distinct methods can use one asset URL but require different members; the shipped broot methods show differing member declarations (`installer/registry.toml:2121-2136`). Skipping the second method can mark a broken platform install as verified.
- **Suggestions:** Deduplicate HEAD/download work by URL, but check and record every method/platform member against that downloaded archive. Add a shared-URL, different-member fixture.
- **Risk Assessment: HIGH** — A false passing checker propagates into verification dates and live acceptance evidence.

## 18-13

**Summary:** A scoped rewrite with a TOML semantic guard is a defensible no-dependency writer, and requiring all of a tool’s pinned methods to pass prevents split-version pins.

- **Strengths:** Explicit `--write`, per-tool candidate validation, byte-preservation tests, and an atomic write.
- **Concerns:** **HIGH** — Task 2 says a successful candidate bump makes the tool eligible for `verified`, but does not define whether the original “newer stable release” drift finding is replaced or whether the final exit code is recomputed (`18-13-PLAN.md`, Task 2). Plan 18-15 expects its `--write` run to exit cleanly. An otherwise correct bump could remain reported as drift.
- **Suggestions:** Specify and test the post-write report and exit code. Alternatively, permit the initial write to exit 1 and make the clean read-only rerun the sole pass gate.
- **Risk Assessment: HIGH** — The ambiguity directly affects the live pin-bump procedure.

## 18-14

**Summary:** The job is separated from the PR gate, has read-only repository permission, and saves state even after a drift result. A step timeout below the job timeout leaves room for cache saving.

- **Strengths:** Issue upsert tests include repeat drift, partial inconclusiveness, and no calls during an outage.
- **Concerns:** **MEDIUM** — The claim that the Thursday refresh *never* permits seven-day cache eviction (`18-14-PLAN.md`, Task 3) assumes scheduled workflows execute and complete on time. The existing design’s cache-miss and incremental-save paths are the actual recovery mechanisms.
- **Suggestions:** Describe the second schedule as a mitigation, not a guarantee; retain and test a full-download cache-miss path. Confirm first-run cache persistence in the stated post-push backstop.
- **Risk Assessment: MEDIUM** — Mainly an operational reliability risk, not a PR-gate risk.

## 18-15

**Summary:** Separating URL templating from the authenticated live bump, retaining logs, and requiring a read-only final rerun are good acceptance practices.

- **Strengths:** Does not execute downloaded assets on the host; checks changed lines and requires audit-ledger citations from actual findings.
- **Concerns:** **HIGH** — Its clean-run and member evidence depend on 18-12 validating each method even when URLs coincide (`18-15-PLAN.md`, Task 2; `installer/registry.toml:2121-2136`). **HIGH** — The expected `--write` exit-zero workflow depends on the unresolved post-bump verdict in 18-13.
- **Suggestions:** Make the shared-URL/different-member regression and defined bump verdict prerequisites to the live write. Do not use a clean log as proof until both hold.
- **Risk Assessment: HIGH** — This is the phase’s acceptance gate; a false green would certify incorrect registry data.

## 18-16

**Summary:** One staged plain-argv fetch removes the present unverified shell pipeline (`installer/download.py:169-191`) and aligns install and update verification. The update context currently lacks the proposed release resolver (`installer/update.py:320-333`).

- **Strengths:** Tests no-hash installs, pinned tarball mismatch, and digest-backed updates without touching the live copy.
- **Concerns:** **MEDIUM** — A direct `update_download` test supplies a digest-bearing context, while the installer-owned update test only checks that `release_resolver` was called (`18-16-PLAN.md`, Task 1). Neither proves those seams together reject bad bytes in the production update path.
- **Suggestions:** Add one installer-owned update with a wrong API digest, asserting `ChecksumMismatch` and unchanged live files. Also test that a direct malformed `Method` cannot silently discard a supplied hash on an unpinned URL.
- **Risk Assessment: MEDIUM** — A missing composition test could conceal an unverified update.

## 18-17

**Summary:** The verdict design usefully distinguishes whole-run blockage from one flaky host, and makes the residual unverified methods visible.

- **Strengths:** Tests credential isolation and tokenless download-host requests against the existing API-only token boundary (`installer/versions.py:311-322`).
- **Concerns:** **HIGH** — Comparing latest tag for *inequality* with the pin (`18-17-PLAN.md`, Task 1) does not prove “newer stable”; an older tag or formatting difference would be mislabeled as a newer release. `installer/versions.py:213-236` already has an ordering helper for parseable versions. **HIGH** — Treating every API HTTP 403 as a rate limit can block a run containing real drift elsewhere; 403 can also mean access denied. **MEDIUM** — “No release read succeeded” applies only if one was attempted; a run comprising HEAD-only checks needs an explicit all-failed verdict.
- **Suggestions:** Compare order where possible and report incomparable tags separately; recognize rate limits from response evidence rather than status alone; test an all-HEAD-fail run.
- **Risk Assessment: HIGH** — Wrong verdicts can either create false drift or suppress a real issue.

## 18-18

**Summary:** Paired control and isolated-launch probes are valuable container evidence, and container-only FUSE handling rightly stays out of production smoke.

- **Strengths:** Requires ruff’s dev-venv control, post-install path, pass markers, and container removal.
- **Concerns:** **HIGH** — Teardown is required on a Task 1 stop, but the specified `rm -f` is at Task 2’s end (`18-18-PLAN.md`, executor rules and Task 2). The harness’s EXIT cleanup belongs to its `all` flow (`scripts/container-e2e-verify.sh:481-488`), whereas this plan runs subcommands separately. **HIGH** — `resync` and repeat pass1 do not reset prior installed tools (`scripts/container-e2e-verify.sh:149-151,225-230`); a retry can pass because a partial first run populated the container, not because a clean install works. **MEDIUM** — The automated pass2 check merely finds “ruff” somewhere, not removal of both its link and opt tree; `TRACER_CLEAN_INSTALL_OK` itself permits some unresolved outcomes (`scripts/container-e2e-verify.sh:378-400`).
- **Suggestions:** Use an outer cleanup trap for the entire multi-command run. Re-bootstrap a fresh container for final clean-install evidence after any fix; assert the specific ruff uninstall lines and per-tool success rows.
- **Risk Assessment: HIGH** — The current procedure can leave a container or produce misleading clean-install evidence.

## 18-19

**Summary:** Manager smoke is placed where `ExecutorError` can trigger the existing method fall-through (`installer/engine.py:95-165`), and the plan correctly accounts for tests that reach the engine indirectly.

- **Strengths:** Includes a scratch-PATH tripwire, declared-bin-dir coverage, handoff exclusion, and custom argv tests.
- **Concerns:** **HIGH** — Task 2 moves `prepend_path` ahead of smoke but does not restore PATH when smoke fails and the ladder continues (`18-19-PLAN.md`, Task 2). `prepend_path` mutates process-wide `os.environ` (`installer/locations.py:103-108`), so the next method may resolve the failed method’s binary. **HIGH** — `shutil.which(tool.cmd)` can find a pre-existing unrelated binary; passing its smoke does not prove the manager method installed a working binary. Skipping smoke when nothing resolves likewise cannot support the broad “every installed manager binary was smoked” claim.
- **Suggestions:** Restore PATH after a failed attempt and test a two-method ladder with different bin dirs. Where possible, resolve a declared or manager-owned installation path; otherwise narrow the outcome claim to the command currently found on PATH and test that limitation.
- **Risk Assessment: HIGH** — A failed attempt can contaminate later attempts and yield a misleading success.

### Overall assessment

The plans cover the phase’s principal requirements, but **18-09’s staging safety, 18-12’s per-method verification, and 18-13/18-15’s write-run verdict** should be corrected before execution. The resolver ordering contradiction in 18-08 is also immediately test-blocking.

This was a read-only source-and-plan review. I did not run the future checker, live upstream verification, macOS CI, or the disposable-container e2e; those remain acceptance risks.

---

## Consensus Summary

One reviewer ran (`opencode-plan-review`, the only entry in `review.default_reviewers`), so there is no cross-reviewer consensus. The review is source-grounded: it cites 33 `file:line` locations and carries no discount marker. It covers all 19 plan ids. The orchestrator checked each HIGH against the plans and the source (see "Orchestrator adjudication" below).

### Agreed Strengths
- (single reviewer) Hash-before-smoke-before-swap ordering (18-09), one release read for tag and digests (18-07), `apps.cli_spec` as the single link-name source (18-04), and keeping verify-registry out of the PR gate (18-14).

### Agreed Concerns
- None (single reviewer). The highest-priority single-reviewer concerns are 18-12's per-URL dedup that skips members (which also invalidates 18-15's evidence), 18-13's undefined post-bump verdict (which 18-15 depends on), 18-08's glab ladder test that contradicts `installer/resolve.py`, and 18-19's PATH contamination after a failed smoke.

### Divergent Views
- None (single reviewer).

### Orchestrator adjudication of HIGHs (source-checked)

| # | Plan | HIGH | Source check | Status |
|---|------|------|--------------|--------|
| H1 | 18-02 | Existing negative assertions conflict with the new behaviour | Confirmed: `tests/test_versions.py:313` asserts `version=0.64.1` extracts to None; `:413` asserts the comment block still names `procs`; `:423` asserts `procs "0.14.12` is None. The plan has only a generic "fix pinned tests" rule and names `tests/test_version_status.py`, not these. | Open (partial) |
| H2 | 18-05 | An activated venv keeps `.venv/bin` on the inherited PATH | Not addressed in 18-05. ROADMAP SC4 says "launched without the dev venv on PATH", so an explicit scope note would also resolve it. | Open |
| H3 | 18-08 | The glab native methods are "ranked after brew", which contradicts the resolver | Confirmed: `installer/resolve.py:22-28` ranks dnf/apt/pacman 30 and brew 40, and `resolve_methods` sorts by rank (`:81-84`). `test_audit_fix_e10_glab_has_native_fallbacks` (18-08-PLAN.md:99) cannot pass as written. | Open |
| H4 | 18-09 | A failed extraction leaves a partial `.new` tree | Confirmed that `_extract_into` runs outside the cleanup blocks (`installer/download.py:321`). Mitigated: the next run's `recover_update_remnants` discards a leftover `.new` (`installer/atomic.py:78`), and the live tree and link are untouched. | Open (lower real impact) |
| H5 | 18-09 | `(new / member).is_file()` follows a symlinked archive member | Confirmed: the plan text is at 18-09-PLAN.md:156; the same pattern exists in `installer/executors.py:49-62`. | Open |
| H6 | 18-12 (+18-15) | Dedup by url per tool skips per-method/arch member checks | Confirmed: 18-12-PLAN.md:119 says "de-duplicates by url per tool". broot's Linux and macOS methods share `broot_{ver}.zip` with different `member` values (`installer/registry.toml:2123-2136`), and `{arch.machine}` members differ per arch under one url. | Open |
| H7 | 18-13 (+18-15) | The verdict and exit code of a `--write` run after a successful bump are undefined | Confirmed: 18-13-PLAN.md:140 says only that the tool "counts as passing for `verified`". 18-15-PLAN.md:167 proceeds "When the `--write` run exits 0", and its fix list has no branch for a residual newer-stable finding. | Open |
| H8 | 18-17 | A tag that is not equal to the pin is labelled a "newer" release | Confirmed: 18-17-PLAN.md:120 says "a difference is drift". `installer/versions.py:213` `is_outdated` already ranks versions. | Open |
| H9 | 18-17 | Every HTTP 403 is treated as a rate limit, which blocks the whole run | Confirmed: 18-17-PLAN.md:122 says "Code 403 or 429 is an inconclusive finding and records the rate limit". | Open |
| H10 | 18-18 | No teardown when Task 1 stops | Refuted: the 18-18 executor rules say "The container is removed at the end of Task 2 whatever the outcome, and also at any stop in Task 1", and the blocker branch at 18-18-PLAN.md:98 says "stop, remove the container". | Resolved |
| H11 | 18-18 | A `resync` and pass1 retry does not reset prior installs | Confirmed: `cmd_resync` only re-streams the worktree and re-syncs (`scripts/container-e2e-verify.sh:149-151,225-230`). | Open |
| H12 | 18-19 | `prepend_path` before the smoke is never undone after a failed smoke | Confirmed: `prepend_path` mutates `os.environ` (`installer/locations.py:103-108`). 18-19-PLAN.md:149 moves it into the `try`, before the smoke, and does not restore it. | Open |
| H13 | 18-19 | `which(tool.cmd)` can smoke a pre-existing binary that is not the one just installed | Not addressed. The plan's prohibition covers only the `None` case. | Open |

The 18-15 HIGHs are restatements of H6 and H7 and resolve with them.

## Verification coverage

Source-grounding pass (`plan_review.source_grounding: true`). It ran on 2026-10-15 over all 19 plans at `fb7ea2d`.

**Authority.** `drift-guard authority --raw` returned `intel`. The config sets `grep`, and `intel.enabled: true` upgrades it to `intel`. `.planning/intel/api-map.json` / `API-SURFACE.md` list only 6 CLI entry points (`make setup/doctor/fix/uninstall/guard`, `make e2e`). Under that authority, every Python symbol, registry key and shell function is **UNCHECKABLE** (severity INFO). These were not treated as verified or missing on that basis. Supplementary grep evidence was collected so that this block is not empty: declarations were grepped over `git ls-files` outside `.planning/`. `drift-guard severity` under `intel`: VERIFIED → none, MISSING → needs-acknowledgement (no hardBlock), AMBIGUOUS → MEDIUM, UNCHECKABLE → INFO. No verdict produced a hardBlock.

**Enumeration.** Every backticked token in the 19 PLAN.md files that has a symbol shape (`module.func`, `Class.attr`, `path::name`, `name(...)`, snake/camel identifiers), a path shape or a `--flag` shape. Tokens were de-duplicated per kind and name. Names declared in any plan's "Artifacts this phase produces" section were excluded (they are new by design). Result: 223 distinct cited symbols.

| Grep-evidence verdict | Count | Meaning |
|---|---|---|
| Declared once (`def`/`class`/assignment) | 95 | Python symbol has exactly one declaration |
| Declared in several places | 18 | Registry/param key names and test helpers declared in several modules (`npm_pkg`, `owner_probes`, `link_mode`, `latest_version`, `checked_at`, `failed_at`, `_tool`, `fake_which`, `wire_path`, `with_sensitive_confirm`, `setup._execute_inputs`, ...). Each plan names the module, and each declaration matches it, so none is a real AMBIGUOUS |
| Referenced, not declared | 28 | Registry kinds/keys (`github_release`, `rpm_ostree`, `skill_pack`, `host_setup`, `min_os_version`), shell functions and markers in `scripts/container-e2e-verify.sh` (`run_setup_as_tester`, `install_root_prereqs`, `cmd_pass1`, `cmd_pass2`, `sync_workspace`, `TRACER_*_OK`, `PASS1_COUNTS`), env names (`GH_TOKEN`, `GITHUB_TOKEN`, `CODEX_NON_INTERACTIVE`), and stdlib names (`JSONDecodeError`, `__cause__`, `BaseException`). All are present in the source |
| Paths and flags that exist | 33 | 23 repo paths, 10 flags |
| Not found | 49 | All acknowledged below (needs-acknowledgement; none is a hallucinated existing-code reference) |

Not-found symbols and their acknowledgement:

| Cited at | Token | Why absent (acknowledgement) |
|---|---|---|
| 18-01-PLAN.md:93 | `--no-verify` | git flag (external CLI); cited as a prohibition |
| 18-03-PLAN.md:106 | `bin_dir/java` | illustrative path fragment, not a repo path |
| 18-03-PLAN.md:197 | `java_home` | macOS `/usr/libexec/java_home` (external OS binary) |
| 18-05-PLAN.md:29 | `--no-dev` | uv CLI flag (external) |
| 18-05-PLAN.md:29 | `--isolated` | uv CLI flag (external) |
| 18-05-PLAN.md:115 | `_recipes()` | private helper inside new file `tests/test_makefile.py` (created by 18-05) |
| 18-05-PLAN.md:194 | `--exact` | uv CLI flag (external; cited as rejected alternative) |
| 18-08-PLAN.md:66 | `--no-modify-path` | opencode installer-script flag (external) |
| 18-08-PLAN.md:68 | `kitty.app/Contents/MacOS/kitty` | macOS bundle path on the target host (external) |
| 18-08-PLAN.md:90 | `test_audit_fix_` | test-name prefix, not a symbol |
| 18-09-PLAN.md:29 | `GLIBC_` | loader error substring (string literal) |
| 18-09-PLAN.md:146 | `--custom` | fixture argv in a new test (created by 18-09) |
| 18-09-PLAN.md:154 | `WAYLAND_DISPLAY` | environment variable name (external) |
| 18-11-PLAN.md:115 | `.../v32.4.1/draw.io-arm64-32.4.1.zip` | elided upstream release URL (external) |
| 18-12-PLAN.md:55 | `--candidate` | CLI flag created by 18-13 (cited by 18-12 as a later plan's) |
| 18-12-PLAN.md:59 | `actions/cache` | GitHub Action (external) |
| 18-12-PLAN.md:77 | `urllib.error.HTTPError` | stdlib `urllib.error.HTTPError` |
| 18-12-PLAN.md:82 | `tests/fixtures/` | plan asserts it does NOT exist (correct: absent) |
| 18-12-PLAN.md:119 | `TimeoutError` | stdlib builtin |
| 18-12-PLAN.md:157 | `tempfile.TemporaryDirectory` | stdlib `tempfile` |
| 18-12-PLAN.md:157 | `zipfile.ZipFile(path).namelist()` | stdlib `zipfile` |
| 18-13-PLAN.md:67 | `--state` | CLI flag created by 18-12 |
| 18-14-PLAN.md:30 | `--body-file` | gh CLI flag (external) |
| 18-14-PLAN.md:32 | `workflow_dispatch` | GitHub Actions trigger key (external) |
| 18-14-PLAN.md:140 | `tempfile.NamedTemporaryFile` | stdlib `tempfile` |
| 18-15-PLAN.md:91 | `.../v31.0.2/draw.io-x64-31.0.2.zip` | elided upstream release URL (external) |
| 18-15-PLAN.md:97 | `.e2e-artifacts/verify-registry/` | gitignored run-evidence dir created by 18-15 |
| 18-15-PLAN.md:180 | `stable_update_check` | Sublime HQ upstream endpoint (external URL path) |
| 18-16-PLAN.md:143 | `installer/assets.py::render_pinned_url` | plan explicitly records the deviation from 18-PATTERNS.md: the renderer is `download.pinned_url`, not `assets.render_pinned_url` (correctly absent) |
| 18-18-PLAN.md:90 | `.e2e-artifacts/container/18-18-ruff-probe.log` | gitignored run evidence created by 18-18 |
| 18-01..18-19 (each plan's `<output>`) | `18-NN-SUMMARY.md` (19 files) | execution output created by each plan |

**UNCHECKABLE / skipped.**
- Signatures (argument lists, return types) cannot be asserted under `intel`/`grep`. Every `name(args) -> type` citation was checked for the name only.
- External surfaces are not in the repo and are UNCHECKABLE: uv/gh/git flags, GitHub API and Actions semantics, upstream release asset names and digests, macOS binaries (`java_home`, `xcode-select`).
- Live-behaviour claims in the plans' context blocks were spot-checked, not enumerated. Each one below was confirmed against the tree:
  - `parse_version('-1') == (1, 0, 0, 1)`, `parse_version('jq-1.8.1') == (1, 8, 1, 1)`, `parse_version('"0.20.0"') is None`, `extract_observed_version('version=0.44.1, os=linux') is None`.
  - 90 `[[tool]]` blocks and 89 `github_release` methods in `installer/registry.toml`.
  - The `managed-download` probe is present at `installer/model.py:55`, `installer/install_ownership.py:86,376` and `installer/registry.toml:2734,2783`.
  - `drawio-cli` is present at `installer/registry.toml:2772`.
- The 18-RESEARCH.md "Live findings" counts (153/171 digests) were not re-probed (network).

**Source-grounding finding (orchestrator, MEDIUM, actionable).** In 18-02, the procs fixture does not match procs' real output. The audit records procs printing `procs "0.14.12 (…` (`.planning/research/audit-2026-10-13/E-registry-user-part2.md:75`), with one *unbalanced* leading quote, and `tests/test_versions.py:423` pins `procs "0.14.12` as None today. 18-02-PLAN.md:124 tests the balanced `procs "v0.14.10"`, and its normalizer "strips one pair of surrounding ... quotes" (18-02-PLAN.md:134). The real procs output therefore stays unparsed while the fixture passes. Fix: make the normalizer strip a leading quote even without a closing one, and use the audit's real string as the fixture row.

## Cross-artifact fact-drift findings

- **Phase status** (`drift-guard phase-status --phase 18`): verdict `lag`. STATE.md says "Ready to execute" (rank 1) and ROADMAP.md says "Not started" (rank 0), with STATE.md as the authority. This is one non-terminal step and not a finding.
- **Success criteria ↔ must_haves.truths** (ROADMAP.md authority): no contradiction.
  - SC1: 18-01 and 18-04.
  - SC2: 18-12 and 18-14. "Weekly non-blocking" matches a schedule/dispatch-only job outside `ci.yml`.
  - SC3: 18-07, 18-15 and 18-16. 18-15 states the residual gron/jless set through Ledger L-18-02, which reads "wherever GitHub exposes a sha256 digest".
  - SC4: 18-02, 18-03, 18-05 and 18-18.
  - SC5: 18-06 and 18-08.
- **Requirement IDs** (ROADMAP.md authority): REG-01..REG-10 each appear in at least one plan's `requirements:`. No plan cites an ID outside the roadmap list.
- **CONTEXT.md decisions ↔ plan usage** (CONTEXT.md authority): no contradiction. Each apparent difference is an amendment recorded inside CONTEXT.md itself:
  - D-02's "reject future values" is amended by L-18-06 (today + 1).
  - D-07's "inconclusive, no issue call" is amended by L-18-05.
  - D-11's `--no-dev` is amended by L-18-01 (`--isolated --no-dev`).
  - D-08's single cron is amended by L-18-07.
  - D-07 names `download._resolve_target`; 18-07 renames it to public `resolve_target`. That is a rename the plan declares, not a contradiction.
  - Stale line numbers in D-12 (`model.py:57`, `registry.toml:2721`) differ from the current source (`:55`, `:2734`). That is CONTEXT ↔ source, not a judgment pair, so it is noted only.
- Coverage: STATE.md, ROADMAP.md and CONTEXT.md were all present, so no axis was skipped.

Advisory only. These findings set no hardBlock and count toward neither HIGH_COUNT nor ACTIONABLE_COUNT.
