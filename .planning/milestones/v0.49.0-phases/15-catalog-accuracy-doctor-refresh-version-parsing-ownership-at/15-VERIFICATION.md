---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
verified: 2026-09-15T01:01:55Z
status: passed
score: 10/10 must-haves verified
covered_files:
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-01-PLAN.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-01-SUMMARY.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-02-PLAN.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-02-SUMMARY.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-03-PLAN.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-03-SUMMARY.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-04-PLAN.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-04-SUMMARY.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-05-PLAN.md"
  - ".planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-05-SUMMARY.md"
  - "installer/catalog_tui.py"
  - "installer/install_ownership.py"
  - "installer/model.py"
  - "installer/ownership.py"
  - "installer/registry.toml"
  - "installer/ui_common.py"
  - "installer/update.py"
  - "installer/version_status.py"
  - "installer/versions.py"
  - "installer/wizard_app.py"
  - "setup.py"
covered_digest: "v1:sha256:53ca4277e783f7d93cf5de1ddc4f35834829606ac808db2e37c7d096b28ba2a9"
behavior_unverified: 0
overrides_applied: 0
warnings:
  - id: WR-02
    severity: warning
    finding: "`_strip_name_prefix`'s `_NAME_PREFIX_BOUNDARY` (`installer/versions.py:54`) lets `.*` match the empty string, so a token that is nothing but punctuation before the digits now parses. Reproduced live on HEAD: `parse_version('-1') == (1, 0, 0, 1)`, `parse_version('--2') == (2, 0, 0, 1)`, `parse_version('-v1.2.3') == (1, 2, 3, 1)`, `parse_version('a-1') == (1, 0, 0, 1)`. All returned None before this phase."
    impact: "`extract_observed_version` scans EVERY whitespace token of a tool's whole `--version` stdout, so a tool that exits 0 while printing a usage line containing a `-1`/`-2` flag would yield a fabricated `installed` version that `is_outdated` then ranks. This is the general clause of a 15-02 must-have truth (\"Nothing that was unparseable for a good reason becomes parseable\")."
    why_not_blocker: "No live trigger exists in the shipped catalog. The D-04 audit recorded ~50 registry tools' real `--version` output in 15-RESEARCH.md; a regex scan of that record for the `[-\\s]-{1,2}[vV]?[0-9]` shape returns zero hits. All three examples the truth enumerates by name (`dasel` usage line, `gron version dev`, the `commit=, ... version=0.64.1, os=darwin` line) still return None, verified live. Both reviewers graded it WARNING and the fix pass deferred it deliberately."
    recommended_fix: "`_NAME_PREFIX_BOUNDARY = re.compile(r\".*[0-9A-Za-z_.+][-\\s](?=[vV]?\\d)\")` plus regression cases for `-1`, `--2`, `release-2024`."
  - id: WR-04
    severity: warning
    finding: "`_native_owner` runs every declared probe per tool inside the blocking refresh, with no memoization and no platform gate (`installer/ownership.py:370`, `installer/version_status.py:521-529`)."
    impact: "On an ostree host `rpm-ostree status --json` is a D-Bus call into `rpm-ostreed`; with a transaction in flight, ten native rows at `timeout=5` each can add ~50 s to a catalog refresh. Absent binaries fail instantly (FileNotFoundError -> `_run` returns None), so the macOS half of this finding is near-free; the stalled-daemon half is real."
    why_not_blocker: "Robustness/latency, not truthfulness. No incorrect assertion is produced."
  - id: WR-06
    severity: warning
    finding: "`_native_owner` calls the full `detect_owner`, then discards a verified NON-native result (`Homebrew`/`pnpm`/`SDKMAN`/`host-setup`/`managed-download`) and returns None (`installer/ownership.py:458-463`)."
    impact: "For `pi` (`owner_probes = [\"host-setup\"]`) a verified answer is dropped and control falls through to by-elimination branches whose premise is 'nobody else claims this tool'."
    why_not_blocker: "Not a regression: `detect_owner` had zero production callers before this phase, so these rows resolved the same way. The guard `if probe is None or candidates or unreadable` means brew/pnpm/uv can only reach this path when their own inventory already produced no candidate and was readable. Result is `unknown`, which is not a false assertion."
  - id: WR-07
    severity: warning
    finding: "`_managed_download` execs `tools-installer-managed-download`, a binary that exists nowhere in the repo (`installer/install_ownership.py:73-80`). Phase 15 made this probe live for `drawio-desktop`/`drawio-cli`."
    impact: "Two rows fork a doomed subprocess on every ownership resolution and can never return a claim. Dead code masquerading as a working probe (`.claude/architecture.md` rule 5)."
    why_not_blocker: "Fails closed to `unknown`; produces no untrue assertion. Pre-existing code, newly reachable."
  - id: WR-08
    severity: warning
    finding: "`tests/test_setup.py:1427-1434` guards the production wiring with `source.count(\"native_probe=\") == 2` — a source-text scrape that would pass if both sites passed None."
    impact: "The 15-05 truth 'the live app actually asks' rests on a test that asserts nothing about behavior."
    why_not_blocker: "Verified independently by direct source read: `setup.py:40` imports `run_probe` from `installer.install_ownership`, and `setup.py:580` / `setup.py:593` pass `native_probe=run_probe` as real code (not comments, not None), on the display path and the mutation path respectively."
  - id: WR-01 / WR-09
    severity: warning
    finding: "WR-01: `action_update_tool` has no `NATIVE_OWNERS` pre-check, so a refusal costs a full worker plus a second probe sweep. WR-09: `tests/test_ui_common.py`'s AI-tab test scrapes module source with positional `split()` and hand-maintained English-collision heuristics."
    impact: "WR-01 is latency only and is a recorded deliberate choice (commit c93c4c7: 'one refusal, one wording'). WR-09 is test brittleness."
    why_not_blocker: "Neither affects a goal clause. The D-10 comment content was verified directly against live registry tier values rather than through the scraper."
---

# Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes — Verification Report

**Phase Goal:** Everything the catalog and Doctor assert about a tool is true: the Doctor screen
renders post-fix state and says which part of it cannot move yet, a tool that prints its version in
its own format is read rather than shown as unknown, a tool the OS package manager owns is attributed
to that manager and cleanly refused by the update action instead of silently mutated or mislabelled,
and each of the three tier tabs lists exactly what its own definition says it lists.

**Verified:** 2026-09-15T01:01:55Z
**HEAD:** f37ba36
**Status:** passed (with 6 recorded WARNING-severity findings, none goal-blocking)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Decision | Truth | Status | Evidence |
|---|----------|-------|--------|----------|
| 1 | D-01 | `action_apply` recomputes guidance before rendering, unconditionally | ✓ VERIFIED | `installer/wizard_app.py:408-409` calls `_refresh_guidance()` then `_refresh_body()` at the same indentation as the `run_live` result, NOT nested under an `if self.error is None`. Matches the ordering at `:254-255`, `:270-272`, `:520-521`. Behavioral: `test_doctor_enter_applies_fix_and_refreshes_guidance` drives a guard flag that flips as a side effect of the fix and asserts it appears in the rendered body; `test_doctor_enter_applies_failed_fix_still_refreshes_guidance` proves the refresh survives a fix that raises. Both green. |
| 2 | D-02 | The frozen-PATH note appears only after a successful apply | ✓ VERIFIED | `installer/wizard_app.py:313-324` — the note is inside the `if self.applied:` branch, absent from the `elif self.error` and `else` branches. Text: "The audit above still describes the PATH this process started with -- that's expected until you open a new shell or run `source ~/.myshellrc`." Behavioral: `test_doctor_screen_adapts_the_body_with_a_frozen_path_note_once_applied` asserts absence before enter and presence after. |
| 3 | D-03 | A glued `<name>-<version>` token parses in all three parsers | ✓ VERIFIED | Ran live against HEAD: `parse_version('jq-1.8.1') == (1, 8, 1, 1)`, `parse_status_version('jq-1.8.1') == ((1,8,1), None)`, `extract_observed_version('jq-1.8.1') == 'jq-1.8.1'`. One shared `_match_observed_version` (`versions.py:69-82`) feeds BOTH call sites (`:124` and `:195`) — the outdated signal is not left dead. Fallback is second, never instead: `'1.2.3'`/`'v1.2.3'` still take the direct path. `'tool-2.3.4-rc.1'` correctly isolates to `(2,3,4)` prerelease `rc.1`, proving the embedded prerelease hyphen is not a split point. |
| 4 | D-04 | The registry audit is recorded in code and pinned by a test | ✓ VERIFIED | `installer/versions.py:31-53` records the live ~50-tool audit and names the two deliberately-uncovered shapes (`procs` — double-quote boundary; `bash` — noise trailing the numeric core) with reasons. Confirmed live that the previously-unparseable examples still return None: `'gron version dev'`, `'GNU bash, version 5.3.9(1)-release'`, `'commit=, build date=, version=0.64.1, os=darwin'`, `'Usage: dasel <command>'` → all None. |
| 5 | D-05 | A native-manager-owned tool resolves to that manager, not `unknown` | ✓ VERIFIED (live hardware) | `installer/ownership.py:370` inserts `_native_owner` between the tracked-candidate branch and the active-path unknown branch — the only placement that fires for a real `/usr/bin/<cmd>`. Ran the real resolver against a real Bazzite host: a layered package → `owner='rpm-ostree', confidence='direct'`; a mutable Fedora platform with a dnf-verifying probe → `owner='dnf', confidence='direct'`. No probe logic duplicated — `ownership.py` imports `detect_owner`/`package_owns_path` (`:61`) and writes no subprocess of its own. |
| 6 | D-05 | Evidence rule preserved; record self-consistent | ✓ VERIFIED | Guard `if probe is None or candidates or unreadable: return None` (`ownership.py:453`). `test_native_owner_requires_complete_negative_evidence`, `test_native_owner_suppressed_by_leftover_installer_artifact`, `test_native_owner_never_overrides_tracked_manager_precedence` all green. Record: `candidates=(synthetic,)`, `shadowed=False` (`:479-490`), pinned field-by-field at `tests/test_ownership.py:436-447`. CR-01 fix live-verified: a hand-built binary earlier in PATH forces `unknown` because `rpm -qf` contradicts the package claim. |
| 7 | D-05 | The update action refuses natively-owned tools by name, with zero mutation | ✓ VERIFIED | `installer/update.py:240-252` — the `NATIVE_OWNERS` branch sits ABOVE the owner-dispatch ladder and returns `status="unsupported"` with `_NATIVE_OWNER_DETAIL.format(owner=...)` naming the concrete manager. `NATIVE_OWNERS` is written once in `ownership.py:84` and imported by `update.py:88` — the two sets cannot drift. Parameterized `test_native_owner_is_refused_with_concrete_manager_named` covers all four owners and asserts `calls == []`. End-to-end: `test_native_owner_update_key_reaches_the_service_and_renders_its_refusal` presses `u` in the TUI and asserts `runner_calls == []`. |
| 8 | D-05 | Live app wiring + catalog label | ✓ VERIFIED | `setup.py:40` imports `run_probe` from `installer.install_ownership` (stdin-isolated, `timeout=5`), NOT `run.run_query`. Passed at `setup.py:580` (`VersionRefreshService`, display path) and `setup.py:593` (`_reresolve_ownership`, mutation path). Catalog label at `catalog_tui.py:401-404` gives all four owners "managed by X — this installer will not update it"; pinned by `test_native_owner_detail_names_manager_and_no_update_fact`. `resolve_status` tail pinned field-by-field (`latest is None`, `outdated is None`, `stale is True`, `source == "unknown"`) at `tests/test_version_status.py:981-986`. |
| 9 | D-06 | rpm-ostree probe reads the booted deployment's layered packages | ✓ VERIFIED (live hardware) | `install_ownership.py:130-175`. Validated the JSON contract against this actual Bazzite host: `rpm-ostree status --json` yields a `booted: true` deployment with a `requested-packages` list. `detect_owner` with the REAL `run_probe` on real hardware returned `Ownership(manager='rpm-ostree', confidence='verified', detail='rpm-ostree layers amdgpu_top')` for a layered package and `unknown` for base-image `podman`/`git`. Fails closed on malformed JSON, missing `deployments`, no booted deployment, non-list `requested-packages`, absent binary, and (WR-05 fix) a recursion bomb. `"rpm-ostree"` is in `model.py:OWNER_PROBES`; `tests/test_install_ownership.py:508-514` asserts `OWNER_PROBES` and `_PROBES` equal in BOTH directions. Ten native rows declare `owner_probes` with `rpm-ostree` first, pinned by `test_native_package_manager_rows_declare_their_owner_probes` including the reverse "nobody forgot to opt in" assertion. |
| 10 | D-07/08/09/10 | Each tier tab lists exactly what its definition says | ✓ VERIFIED | Loaded the live registry: `ast-grep` → `ai` (D-07, beside `rg`/`fd`), `puppeteer` → `ai` (D-08), `mmdc`/`gitleaks`/`vale`/`drawio-cli` → `user` (D-09, now pinned by `test_d09_borderline_tools_stay_user_tier`). Tripwires updated in the same commit: `test_puppeteer_is_an_ai_tier_node_tool_requiring_pnpm` renamed, `test_registry_tier_distribution_is_pinned` reads `{system: 26, ai: 17, user: 46}` — matches the live `Counter` exactly. D-10: `ui_common.py:128-132` comment now cites `rg`, `fd`, `codegraph`, `ast-grep` (all live `tier="ai"`, confirmed), and the user-visible `palette` at `:136` reads "AI - tooling an agent session runs on" instead of promising agent CLIs the human launches. |

**Score:** 10/10 truths verified (0 present, behavior-unverified)

### Key Link Verification

| From | To | Via | Status |
|------|-----|-----|--------|
| `DoctorScreen.action_apply` | `_refresh_body`'s Audit block | `_refresh_guidance()` → `self.guidance` → `_tui_guidance()` | ✓ WIRED |
| `DoctorScreen.applied` | frozen-PATH note | `if self.applied:` branch in `_refresh_body` | ✓ WIRED |
| `parse_version` / `parse_status_version` | `_OBSERVED_VERSION` | shared `_match_observed_version` (direct, then prefix-stripped retry) | ✓ WIRED (both sites, one helper) |
| `registry.toml owner_probes` | `_PROBES[name]` | `Tool.owner_probes` → `detect_owner` iteration | ✓ WIRED (closed sets equal both ways) |
| `resolve_ownership` | `ManagerOwnership(confidence='direct')` | `install_ownership.detect_owner` → `_NATIVE_OWNER_TRANSLATION` | ✓ WIRED |
| `ownership.NATIVE_OWNERS` | `update.py` refusal branch | direct import at `update.py:88` | ✓ WIRED (single source) |
| `setup.py::_build_app` | `resolve_ownership(native_probe=...)` | `install_ownership.run_probe` at `:580` and `:593` | ✓ WIRED (both paths) |
| `VersionRefreshService.ownership_of` | `CatalogScreen._version_detail` owner label map | `catalog_tui.py:388` → `:401-406` | ✓ WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Value | Source | Status |
|----------|-------|--------|--------|
| `catalog_tui._version_detail` | owner label | real `ManagerOwnership` from `VersionRefreshService`, itself from `resolve_ownership` + injected `run_probe` | ✓ FLOWING |
| `VersionStatus.installed` | version string | real `<cmd> --version` stdout via `probe_version_output` | ✓ FLOWING |
| `UpdateOutcome.detail` | refusal text | `_NATIVE_OWNER_DETAIL.format(owner=ownership.owner)` — concrete manager interpolated, not a constant | ✓ FLOWING |
| `DoctorScreen.guidance` | audit findings | `doctor_guidance(self._report)` + live `self._guard_state()` closure | ✓ FLOWING |
| `rpm-ostree` ownership | layered package names | real `rpm-ostree status --json` on the booted deployment (validated against this host) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| jq-style version parses in all three parsers | `uv run python -c "…parse_version('jq-1.8.1')…"` | `(1, 8, 1, 1)` / `((1,8,1), None)` / `'jq-1.8.1'` | ✓ PASS |
| Previously-unparseable inputs stay None | same driver over the 4 recorded shapes | all `None` | ✓ PASS |
| Live registry tier distribution | `Counter(t.tier for t in load_tools(...))` | `{'system': 26, 'ai': 17, 'user': 46}` | ✓ PASS |
| ast-grep / puppeteer are `ai` | live registry load | both `ai` | ✓ PASS |
| Ownership on immutable host, layered pkg | `resolve_ownership(..., immutable=True)` | `owner='rpm-ostree'`, `confidence='direct'` | ✓ PASS |
| Ownership on immutable host, base-image pkg | same | `owner='unknown'` + honest `unknown_reason` (CR-02 intent) | ✓ PASS |
| Ownership on mutable Fedora | same | `owner='dnf'`, `confidence='direct'` | ✓ PASS |
| **Real-host probe** | `detect_owner(tool, run_probe, immutable=True)` on this Bazzite box | layered → `rpm-ostree` verified; base-image `podman`/`git` → unknown | ✓ PASS |
| Real rpm-ostree JSON contract | `rpm-ostree status --json` | booted deployment exposes `requested-packages` list | ✓ PASS |
| Full test suite | `uv run pytest` | exit 0, ~2100 passed / 1 skipped | ✓ PASS |
| Quality gates | `make validate` | ruff check clean, ruff format clean, pyright 0 errors, bandit clean, vulture clean, shellcheck clean | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| D-01 | 15-01 | ✓ SATISFIED | `wizard_app.py:408-409` + 2 behavioral tests |
| D-02 | 15-01 | ✓ SATISFIED | `wizard_app.py:313-324` + pilot test |
| D-03 | 15-02 | ✓ SATISFIED | `versions.py:54-82`, both call sites, live-run |
| D-04 | 15-02 | ✓ SATISFIED | `versions.py:31-53` audit record + pinning test |
| D-05 | 15-04, 15-05 | ✓ SATISFIED | adapter, refusal branch, wiring, label — live-verified |
| D-06 | 15-04 | ✓ SATISFIED | `_rpm_ostree` probe, closed set, 10 registry rows — real-host verified |
| D-07 | 15-03 | ✓ SATISFIED | `ast-grep` tier=`ai` in live registry |
| D-08 | 15-03 | ✓ SATISFIED | `puppeteer` tier=`ai` in live registry |
| D-09 | 15-03 | ✓ SATISFIED | 4 tools stay `user`, pinned by test |
| D-10 | 15-03 | ✓ SATISFIED | comment + palette corrected, cited tools verified `ai` |

No ORPHANED requirements: the ROADMAP names D-01..D-10 and all ten are claimed by a plan.

### Anti-Patterns Found

| Category | Result |
|----------|--------|
| Debt markers (`TBD`/`FIXME`/`XXX`) in phase-modified files | **None** |
| Cleanup markers (`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented") | **None** |
| Stub returns / hollow props | **None** — every new branch returns computed values from real probes |
| Orphan helpers | 1 pre-existing (`_managed_download`, see WR-07) — newly reachable, not newly written |

### Code-Review Fix Verification (independent of `fix_outcomes` claims)

| Finding | Claimed | Independently verified |
|---------|---------|------------------------|
| CR-01 (mutation-grade claim over a contradictory live PATH) | fixed | ✓ `ownership.py:477` calls `package_owns_path` before returning; `test_native_owner_refuses_to_claim_a_live_binary_the_package_does_not_own` asserts `owner == "unknown"`, `confidence not in MUTATION_GRADE`, and that `rpm -qf` was actually issued against the resolved path. |
| CR-02 (base-image RPMs attributed to dnf on ostree) | fixed | ✓ `detect_owner` takes a defaultless keyword-only `immutable`; `_MUTABLE_HOST_ONLY_PROBES` skips dnf/apt/pacman. Verified on real hardware: base-image `podman`/`git` return unknown, layered package returns rpm-ostree. |
| WR-05 (recursion bomb crashes the refresh worker) | fixed | ✓ `install_ownership.py:154` catches `RecursionError` alongside `TypeError`/`ValueError`; `test_rpm_ostree_owner_fails_closed_on_a_recursion_bomb_from_the_probe` present and green. |
| WR-10 (`resolve_status` has no native-owner branch) | no_change_needed | ✓ Confirmed deliberate — the status tail is pinned field-by-field at `tests/test_version_status.py:981-986`, exactly as the 15-05 must-have declares. |

### Human Verification Required

None. Every goal clause was exercised either by a Textual pilot test asserting rendered output, or by
running the production code path live — including the rpm-ostree probe against this machine's real
`rpm-ostree status --json`.

### Gaps Summary

**No goal-blocking gaps.** All four bug classes named in the ROADMAP are demonstrably fixed, and the
strongest evidence is that the ownership half was verified against the real Bazzite host the bugs were
originally reported on, not only against fixtures.

Six WARNING-severity findings are recorded in the frontmatter. The one a reader should not skip:

**WR-02 — an evidenced regression introduced by this phase.** `_NAME_PREFIX_BOUNDARY` permits an empty
name prefix, so `-1`, `--2`, `-v1.2.3` and `a-1` now parse as versions where they previously returned
None. `extract_observed_version` scans every token of a tool's whole `--version` stdout, so a tool that
exits 0 while printing a usage line with a numeric short flag would surface a fabricated installed
version. It is graded WARNING rather than BLOCKER because no tool in the shipped catalog triggers it —
the D-04 audit captured ~50 tools' real output and none contains a token of that shape — and because
every sub-clause the 15-02 truth enumerates by name still holds. It nonetheless breaches that truth's
general statement and weakens `meets_minimum`'s fail-closed contract in principle. Recommend scheduling
the one-character-class fix (`.*[0-9A-Za-z_.+][-\s](?=[vV]?\d)`) plus regression cases.

The remaining five (WR-01, WR-04, WR-06, WR-07, WR-08/WR-09) are latency, dead-code and test-quality
concerns that produce no untrue assertion; all were graded WARNING by both reviewers and explicitly
deferred by the fix pass.

---

*Verified: 2026-09-15T01:01:55Z*
*Verifier: Claude (gsd-verifier)*
