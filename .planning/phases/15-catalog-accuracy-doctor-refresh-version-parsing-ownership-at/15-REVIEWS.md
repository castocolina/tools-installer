---
phase: 15
reviewers: [opencode-fallback]
reviewed_at: 2026-09-14T20:55:00Z
plans_reviewed:
  - .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-01-PLAN.md
  - .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-02-PLAN.md
  - .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-03-PLAN.md
  - .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-04-PLAN.md
  - .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-05-PLAN.md
models:
  opencode-fallback: "router-env/my-coding (reasoning=medium)"
model_sources:
  opencode-fallback: "pinned"
failed_lanes:
  opencode-fallback-cycle2-attempt-1: "first attempt this cycle returned narration-only output (orchestration commentary, self-applied [reviewed-without-source-citations] marker) with no per-plan Summary/Strengths/Concerns content despite ok:true — the #1936 'no final assistant text' defect class, manifesting as premature truncation rather than an empty file. Retried immediately (attempt 2) with the identical prompt/model; attempt 2 succeeded with a complete, well-grounded review."
---

# Cross-AI Plan Review — Phase 15

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

**Round 1 (this review) — none.** All findings (0 HIGH, 5 actionable MEDIUM, several LOW) are
plan-internal verify-gate/scope defects or advisory confirmations — none proposes changing a
locked CONTEXT.md decision (D-01 through D-10). Nothing here touches which refresh call the
Doctor screen makes (D-01/D-02), the fallback shared-helper design (D-03/D-04), the ownership
adapter/refusal mechanism (D-05/D-06), or the two tier moves (D-07/D-08). No conflict recorded.

**Round 2 (this review) — none.** Cycle 2 confirms cycle 1's five findings were correctly
incorporated (verified against the live tree, not taken on the plan's word — e.g. the
`_NATIVE_OWNER_DETAIL` grep-stable anchor, the `candidates=(synthetic,)` self-consistency fix,
the backtick-anchored id scanner, the palette-copy update, and the leftover-artifact test). It
raises 2 new MEDIUM findings (15-04's one-way `OWNER_PROBES`/`_PROBES` coverage-gap assertion,
15-05's `resolve_status` final-branch field assertion) plus advisory LOWs, none of which touches
a locked CONTEXT.md decision — both MEDIUMs are plan-internal verify-gate completeness defects
in newly-written gates, not design changes. No `## Plan-Revision Conflicts` entry required.
<!-- gsd:plan-revision-conflicts:end -->

## OpenCode Review Round 1 (opencode-fallback)

I'll review the five plans against the live code, not the plan text. Loading the review skill and reading the files they cite.
This is a grounded plan review, not an orchestrator run. I'll check each plan's claims against the live source.
Confirmed DoctorScreen skips `_refresh_guidance` and versions has two independent `fullmatch` sites. Next I'll ground ownership, update dispatch, registry, and tests.
I have the ownership and Doctor bugs. Next I'll check tests, registry rows, catalog labels, and the composition-root wiring.
Checking registry tripwires, native-manager rows, composition-root wiring, and a few test helpers the plans depend on.
Need the native-manager tool IDs, catalog update gate, setup wiring, and a few test helpers.
Checking composition-root wiring, the catalog update gate, and a few remaining type/test details.
Checking a few more load-bearing paths: `competing_owners`, `resolve_status` owner branches, `run_live`, and the AI-tab palette.
Checking a few remaining call sites that could break after `Owner` is widened.
Verified the live tree. The five plans match the code; 15-05 correctly moves the native fallback *before* the `active_path` unknown return that research placed too late.

### 15-01

**Summary.** Small, correctly-scoped fix for the one Doctor event that renders without recomputing guidance. Sibling call sites at `installer/wizard_app.py:253-256`, `:270-272`, and `:505-506` already pair `_refresh_guidance()` then `_refresh_body()`; `action_apply` at `:389-394` is the outlier (`self._refresh_body()` only). The plan treats D-01 as an ordering invariant and D-02 as the visible "expected, not broken" note, and it does not pretend the PATH audit can change inside one process.

**Strengths**
- Grounded in the real refresh contract: `_refresh_guidance` is IO-free (`:290-302`) and re-reads `self._guard_state()`, so a flipping `guard_status` callable is a real signal. `_predicate` / `_app` already accept that callable (`tests/test_wizard_app.py:85-100`, `:165-191`).
- Test asserts the rendered `#doctor-body`, matching `test_doctor_screen_adapts_missing_path_guidance_for_tui` (`:282-292`), so it proves ordering rather than a silent `self.guidance` write.
- Keeps the note DoctorScreen-local. `guard_guidance` (`installer/guidance.py:73-105`) has no `applied` concept; `make doctor` has no apply action.
- Explicitly forbids asserting that the missing-PATH finding disappears — `self._report` is a process-lifetime snapshot.

**Concerns**
- **MEDIUM — verify gate does not catch a success-gated refresh.** Task 1 requires refresh on failed apply (`run_live` maps `OSError` to `self.error` at `installer/ui_common.py:47-50`). The ORDER-OK extractor only keeps lines containing `_refresh_guidance()` / `_refresh_body()`, so this still passes:

```python
if self.error is None:
    self._refresh_guidance()
self._refresh_body()
```

`fails_when` claims it would fail; the assertion would not. CONTEXT D-01 also says "after a fix succeeds," which an implementer may follow literally.
- **LOW — failed-apply behavior is specified but not named as its own test.** Task 1's behavior list includes the OSError path; action/verify only pin the success + once-only path.

**Suggestions**
- Assert `self._refresh_guidance()` is not indented under `if self.error is None`, or add a Pilot test: `fix` raises `OSError`, `applied is False`, error text is shown, no crash.
- Keep Task 2's required word `audit`; CONTEXT's example ("PATH check") would fail the NOTE-IN-APPLIED-BRANCH gate.

**Risk:** LOW. Two localized edits; the only real hole is the success-gated refresh slipping the source gate.

### 15-02

**Summary.** Correct shared-helper design for the two independent `_OBSERVED_VERSION.fullmatch` sites (`installer/versions.py:70` and `:141`). Fixing only `parse_version` would display `jq-1.8.1` while `is_outdated` (via `parse_status_version`) stayed `None` — Pitfall 1 is real. The prefix-split is narrow, fail-closed, and leaves `parse_declared_version` (`:80-91`) strict.

**Strengths**
- One helper, both call sites, same commit. `extract_observed_version` (`:116-126`) returns the verbatim token, so `is_outdated("jq-1.8.1", "1.8.2")` is the proof the second parser moved.
- Retry reuses `_OBSERVED_VERSION`, so `group(1)` / `group(2)` stay stable. Direct match still wins for `1.2.3` / `v1.2.3` / `25.10.0-rc.1`.
- Existing None cases stay None: `version=0.64.1` is preceded by `=`, not `[-\s]`; `gron version dev` never yields a numeric token (`tests/test_versions.py:248-250`).
- D-04 records `procs` / `bash` as residuals with `# Verified` + substring test, matching `.claude/architecture.md` registry-authoring practice. Does not widen the boundary class.

**Concerns**
- **LOW — `parse_status_version` still fullmatches the entire stripped string** (`:141`). After this fix that is correct for the verbatim token `jq-1.8.1`; a raw multi-token line still would not parse. Callers already go through `extract_observed_version`. Not a defect — don't "fix" it here.
- **LOW — wezterm/cursor-agent date-hash false positives** are correctly left as a SUMMARY fast-follow. Do not pin them.

**Suggestions**
- Keep the three `prefix`-named tests on `parse_version`, `extract_observed_version`, and `is_outdated` as separate tests so a later revert of one call site is visible.
- Quote `5.3.9(1)-release` and the `Not covered:` marker exactly; a bare `bash` substring is too weak, as the plan already says.

**Risk:** LOW. Pure, IO-free, well-tested, no schema change.

### 15-03

**Summary.** Two one-field registry moves plus tripwire updates, with D-09 pinned instead of left in a discussion log. Live data matches the plan: `ast-grep` is `category="search"` / `tier="user"` (`installer/registry.toml:1834-1841`) beside `rg`/`fd` at `tier="ai"` (`:81-87`); `puppeteer.desc` already says it is required at runtime by mmdc (`:2399-2408`). The AI-tab comment at `installer/ui_common.py:129-134` still names `claude`/`codex`.

**Strengths**
- Updates the tripwires in the same commit: `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` (`tests/test_registry.py:584-593`) encodes the wrong tier in its name; `test_registry_tier_distribution_is_pinned` (`:928-936`) is `{"system": 26, "ai": 15, "user": 48}` and documents that catalog edits must update it.
- D-09 group pin is the right way to close the borderline review; `test_reconciliation_tier_audit_confirms_all_11_re_added_rows` (`:945-966`) already pins `drawio-cli` as user — overlap is harmless if the new test is a group, not a second drawio-only assertion.
- Tier is a browsing label; `tests/test_deps.py` in the verify gate is the right non-regression for `mmdc.requires`.
- D-10 test re-derives cited ids from the live registry rather than hardcoding names.

**Concerns**
- **MEDIUM — user-visible palette is the same stale claim and is out of scope.** `palette="AI - agents you run and tools agents call"` (`installer/ui_common.py:135`) is the header users see. Task 2 forbids changing any View field so `test_tier_views_lead_the_nav_and_match_the_tier_enum` (`tests/test_ui_common.py:234-241`) stays green — that test does not read `palette`. Leaving it contradicts D-10's goal.
- **MEDIUM — whole-word id scan false-positives.** Registry ids include `just`, `code`, `git`, `watch`, `pi`, `bat`, `sd`. A comment that says "just the tools an agent calls" would fail `AI-TAB-OK` even with no intended citation. The verify regex is the same (`\\b` + id).
- **LOW — `jq` remains `tier="user"` with `audience="ai"` (`registry.toml:119-125`).** Out of D-09's named set; don't expand, but don't let a drive-by "fix" land either. The Counter gate will catch an extra move.

**Suggestions**
- Update the palette in the same comment task. It is copy, not structure; keep `name`/`mode`/`actions` untouched.
- Isolate the comment slice tightly (between `name="ai"` and `palette=`, as the gate already does) and cite only distinctive ids (`codegraph`, `ast-grep`, `rg`) so `just`/`code` cannot match English.
- Rename the puppeteer test so `-k puppeteer` still selects it.

**Risk:** LOW–MEDIUM. Data edits are right; the leftover palette and the comment scanner are the execution risks.

### 15-04

**Summary.** The right first half of Bug 3: probes and opt-in data, no live wiring yet. `detect_owner` (`installer/install_ownership.py:179-185`) iterates `tool.owner_probes` and indexes `_PROBES` directly — an unregistered name is a `KeyError`. Only three rows declare the field today (`pi`, `drawio-desktop`, `drawio-cli`). Native dnf/apt/pacman methods exist on exactly ten tools (26 `kind = "dnf"|"apt"|"pacman"` lines = 8×3 + 2×1). `OWNER_PROBES` (`installer/model.py:55-64`) has no `"rpm-ostree"`. `_applies` returns `False` for `rpm_ostree` (`installer/resolve.py:70-73`), so the probe cannot key off that method kind.

**Strengths**
- Mirrors `_dnf` (`install_ownership.py:111-116`): `_method_values` → `_run` → parse → `Ownership | None`.
- Booted-deployment + `requested-packages` is the live JSON shape; a non-booted hit is specified as `None`.
- Fail-closed on malformed JSON / missing keys / non-list / absent binary, via `_run`'s existing swallow (`:55-59`) plus `json.loads` try/except including `KeyError` (stricter than `_pnpm` at `:148-151`).
- Hyphenated `"rpm-ostree"` matches `OWNER_PROBES` style (`"managed-download"`, `"host-setup"`), not `METHOD_KINDS`'s `rpm_ostree`.
- `rpm-ostree` first in `owner_probes` is load-bearing: `_dnf` is `rpm -q`, which still answers on ostree hosts.
- Pinning the ten-id set turns a forgotten new dnf row into a red test — the silent gap this phase exists to close.
- Honest about the one-wave architecture-rule-5 orphan; 15-05 is the caller.

**Concerns**
- **LOW — `packages` vs `requested-packages`.** A package pulled in only as a layered dependency is in `packages` but not `requested-packages`, so it falls through to `_dnf`. The plan accepts this; don't add a third probe.
- **LOW — per-refresh cost.** Eight tools will each run `rpm-ostree status --json`. Research timed this well under a second; don't cache here.
- **LOW — verify `Tool(...)` fixtures** must keep explicit `priority`/`audience`/`tier`. `Tool.__init__` currently defaults them (`model.py:285-287`); the plan already warns.

**Suggestions**
- Extend `_manager_for` with `"rpm-ostree": "rpm-ostree"` so `_probe` can serve the new command (`tests/test_install_ownership.py:26-35` keys on `command[0]`).
- Re-run the mechanical `kind = "dnf"|"apt"|"pacman"` scan before editing expected sets if `registry.toml` moved after 15-03.
- Put `owner_probes` on the `[[tool]]` table, above the first `[[tool.method]]` — a key after that header is a method field and will fail load or silently vanish.

**Risk:** LOW. Probe + schema + ten opt-ins; no mutation path yet.

### 15-05

**Summary.** This is the load-bearing plan, and it corrects research rather than copying it. `resolve_ownership` returns unknown for a live unattributable path at `installer/ownership.py:333-345` *before* the final `_unknown` at `:374-385`. A `/usr/bin/jq` dnf install takes that earlier branch (`attribute_path` only knows installer/brew/cask/pnpm/uv dirs, `:232-271`). A fallback placed only at the end would pass every no-PATH unit test and do nothing on a real machine. Mapping `verified` → `direct` then requires a `_perform` refusal: `direct` is in `MUTATION_GRADE` (`:64`), the dispatch `else` raises `UpdateError(f"unsupported owner {owner!r}")` (`installer/update.py:244-245`), and `perform_update` turns that into `status="failed"` (`:186-201`) — worse than today's pre-flight unknown-owner refusal.

**Strengths**
- Placement is specified as after `if active_candidate is not None:` (`ownership.py:322-332`) and before `if active_path is not None:` (`:333`). One call site covers live-unattributable-path *and* no-path.
- Adapter-only: `detect_owner`, no new subprocess in `ownership.py`. Translation table is the closed set of four native names; `"Homebrew"` from `_brew` (`install_ownership.py:97`) cannot leak onto this path.
- Complete-negative-evidence guard (empty `candidates` *and* empty `unreadable`) preserves `test_linux_system_package_manager_is_unknown_by_design` (`tests/test_ownership.py:357-381`) when no probe is injected.
- Refusal is a sibling of the SDKMAN branch (`update.py:222-228`), before the ladder, not an `elif` that looks like a future `sudo dnf upgrade`. `_NATIVE_OWNER_DETAIL` is grep-stable even if the condition is a tuple of four names.
- `run_probe` (`install_ownership.py:30-39`: `stdin=DEVNULL`, `timeout=5`) at both composition-root sites (`setup.py:573-591` currently wires neither). Catalog vs mutation cannot disagree.
- `resolve_status` final branch (`version_status.py:324-336`) already yields `latest=None`, `source="unknown"` for these owners — correctly left alone (`source` is where *latest* came from).
- No second gate in `action_update_tool` (`catalog_tui.py:574-577`). Native+direct passes `MUTATION_GRADE`, `UpdateService.run` (`update.py:368-375`) also lets it through, and `_perform` is the single refusal wording. Today a native owner with no label would drop the `unknown_reason` sentence (`catalog_tui.py:391-400` `labels.get` → None, and `:411` only runs for `owner == "unknown"`).

**Concerns**
- **MEDIUM — native winner may be absent from `candidates`.** `_owned` will be called with the empty tracked-manager tuple while `owner="dnf"`. The script by-elimination path passes `candidates=(synthetic,)` (`ownership.py:365-370`). Shadowed UI iterates `ownership.candidates` (`catalog_tui.py:401-406`). Pass `candidates=(synthetic,)` (and `shadowed=False`) so the record is self-consistent.
- **MEDIUM — leftover installer artifacts block native attribution.** If `~/.local/bin/jq` exists, `_collect_candidates` adds an installer candidate (`ownership.py:403-410`). The helper then returns None (`candidates` nonempty), and the live `/usr/bin/jq` still falls into the unattributable-path unknown. Fail-closed and consistent with the evidence rule, but the catalog will still say unknown on a machine that has both a stale download and a dnf install. Worth one test so it is a decision, not a surprise.
- **LOW — `resolve_update_argv` (`update.py:149`) still raises for `dnf`.** `_perform` will not call it if the refusal is first; don't add a native branch there.
- **LOW — size.** Ten files is five modules + five test modules; Tasks 1+2 are the honesty minimum. Don't split Task 1 from Task 2.

**Suggestions**
- Widen `Owner` with the hyphenated `rpm-ostree`; never `rpm_ostree`. No `cast` / `# type: ignore`.
- Default `VersionRefreshService.native_probe` to `None`, not `run_probe` — otherwise unit tests spawn `rpm -q`.
- Task 3 labels must say both the manager *and* that this installer will not update it; a bare "managed by dnf" is a downgrade from today's `unknown_reason` (`ownership.py:547-551`).
- Keep `test_linux_system_package_manager_is_unknown_by_design` unmodified; add `-k native` siblings.

**Risk:** MEDIUM. Highest blast radius in the phase, but the plan names the actual landmines (placement, Literal widening, privileged-update refusal, stdin isolation, label gap). Complexity, not a missing design.

### Cross-plan

Wave 1 file split is real: 15-01 `wizard_app.py`, 15-02 `versions.py`, 15-03 `registry.toml` + `ui_common.py`. 15-04 correctly `depends_on: ["15-03"]` (shared `registry.toml` / `tests/test_registry.py`). 15-05 correctly `depends_on: ["15-04"]`.

Splitting Bug 3 across 15-04 (probe + opt-in) and 15-05 (adapter + refusal + wiring) is better than the original four-plan sketch: widening `Owner` without a producer, or wiring `direct` without a `_perform` branch, is worse than doing nothing.

jq is the accidental end-to-end fixture: 15-02 parses `jq-1.8.1`, 15-04 opts its dnf/apt/pacman methods into `owner_probes`, 15-05 attributes `/usr/bin/jq` and refuses `u`. No file overlap.

**Phase risk: MEDIUM**, almost entirely 15-05's mutation-surface coupling. 15-01–15-04 are low-risk if the 15-01 success-gated-refresh hole and the 15-03 palette/scanner issues are closed in-plan. Do not ship 15-04 without 15-05; together they satisfy D-05/D-06.

## OpenCode Review Round 2 (opencode-fallback)

### 15-01

**Summary.** The plan is executable and correctly addresses both Doctor behaviors. It matches the existing refresh lifecycle and preserves the process-level PATH snapshot semantics.

**Strengths**
- Correctly identifies the missing call at `installer/wizard_app.py:389-394`; sibling refresh paths already establish `_refresh_guidance()` before `_refresh_body()` at lines 253-255 and 270-272.
- Tests a mutable guard source rather than relying on unchanged PATH guidance.
- Explicitly covers failed fixes that mutate state before raising, preserving `run_live`'s behavior.
- Keeps the note screen-local, appropriate because `installer/guidance.py` is pure and `self.applied` is UI state.

**Concerns**
- **LOW** — The plan says the refresh is "after a successful fix" in several places while implementing it unconditionally. The task clarifies this adequately, but the final implementation summary should consistently call it an unconditional post-attempt refresh.

**Risk:** LOW — isolated UI behavior, clear existing patterns, and strong regression tests.

### 15-02

**Summary.** The version-parser plan is well-grounded and correctly fixes both independent `_OBSERVED_VERSION` call sites without weakening the strict declared-version parser.

**Strengths**
- Correctly targets `installer/versions.py:70` and `:141`; both currently call `_OBSERVED_VERSION.fullmatch` independently.
- Reuses one matcher and the existing capture groups, avoiding divergence between feature-floor parsing and outdated comparison.
- Preserves `extract_observed_version`'s documented verbatim return contract at `installer/versions.py:116-126`.
- Explicitly protects `parse_declared_version` at `installer/versions.py:80-91`.
- The residual `procs` and bash cases are documented rather than incorrectly handled with broad substring parsing.

**Concerns**
- **LOW** — The audit comment is date-specific (`2026-09-14`). This is acceptable for the requested audit record, but future registry additions can make the statement stale unless the test or comment clearly states the audited registry revision/scope.

**Risk:** LOW — the fallback remains fail-closed through `_OBSERVED_VERSION.fullmatch`, and both parser paths are covered.

### 15-03

**Summary.** The tier corrections and AI-tab documentation updates are appropriately scoped. The plan correctly treats tier as presentation metadata rather than dependency-ordering logic.

**Strengths**
- Grounds the two changes against the actual registry entries: `ast-grep` at `installer/registry.toml:1836-1841` and the existing `rg`/`fd` AI-tier entries.
- Updates the existing puppeteer and tier-count tripwires rather than weakening them.
- Adds explicit D-09 coverage for `mmdc`, `gitleaks`, `vale`, and `drawio-cli`.
- The comment scanner distinguishes backticked catalog citations from ordinary English, avoiding false positives from IDs such as `git` and `watch`.
- Correctly notices that the stale user-visible palette at `installer/ui_common.py:135` must change alongside the comment.

**Concerns**
- **LOW** — The planned source scanner uses string slicing from `name="ai"` to `palette=`. This is adequate for the current table, but it is somewhat format-sensitive and could break on harmless formatting changes.

**Risk:** LOW — declarative edits only, with registry-count and dependency regression tests.

### 15-04

**Summary.** The rpm-ostree probe and registry opt-in plan is technically coherent and correctly preserves the existing probe architecture. Its wave dependency is appropriate because it shares registry tests with 15-03.

**Strengths**
- Reuses `_method_values`, `_run`, and `_PROBES` from `installer/install_ownership.py:42-59` and `:167-185`.
- Correctly scopes ownership to the booted deployment's `requested-packages`.
- Adds the new `"rpm-ostree"` value to the closed `OWNER_PROBES` set at `installer/model.py:55-64`, matching validation at `:654-660`.
- Correctly identifies all ten native-manager rows from the registry's native method declarations.
- Places rpm-ostree before dnf so layered packages are attributed to the mechanism that installed them.
- Explicitly documents that `detect_owner` remains temporarily orphaned until 15-05.

**Concerns**
- **MEDIUM** — The plan's own verification gate checks `set(_PROBES) <= set(OWNER_PROBES)`, but the production contract is the reverse direction: every registry-declarable owner probe must have an implementation. The gate does not detect an `OWNER_PROBES` entry with no `_PROBES` implementation, which would make a future registry row load successfully and fail at `detect_owner`.
- **LOW** — The plan intentionally adds registry declarations before the production caller exists. The plan documents this correctly, but execution must not treat 15-04 alone as phase-complete.

**Suggestions**
- Add an assertion for `set(OWNER_PROBES) <= set(_PROBES)` or explicitly assert equality.
- Keep 15-05 mandatory before release verification.

**Risk:** MEDIUM — implementation risk is modest, but the closed-set validation gate has a one-way coverage gap.

### 15-05

**Summary.** The final integration plan correctly handles the most consequential risk: verified native ownership must not accidentally authorize unsupported or privileged updates. It also places the ownership fallback before the real machine's unattributed active-path return.

**Strengths**
- Correctly identifies the live-path early return at `installer/ownership.py:333-345`; placing the adapter only before the final return would not fix real `/usr/bin/<cmd>` cases.
- Preserves the evidence rule by requiring empty candidates and no unreadable inventories.
- Requires a self-consistent synthetic candidate, matching the existing branch at `installer/ownership.py:356-373`.
- Widens `Owner` instead of using casts or type ignores.
- Adds refusal before the existing unsupported-owner exception at `installer/update.py:229-245`.
- Injects `run_probe`, whose stdin isolation is implemented at `installer/install_ownership.py:30-39`, into both display and mutation paths.
- Adds labels for new owners in the catalog, where the current map at `installer/catalog_tui.py:391-400` would otherwise silently omit them.

**Concerns**
- **MEDIUM** — The plan claims that a native-owned tool's `VersionStatus` should retain `stale=True`, `latest=None`, and `source="unknown"`, but the proposed tests must verify this against the actual final branch of `resolve_status`, not merely assert ownership. The plan mentions this, but it is an important integration contract because the new owner values widen every `Owner` consumer.
- **LOW** — The `_NATIVE_OWNER_DETAIL` constant is described as naming the owning manager, but the exact proposed formatting is left open. Ensure the returned `UpdateOutcome.detail` includes the concrete owner (`dnf`, `apt`, `pacman`, or `rpm-ostree`) rather than only a generic phrase.
- **LOW** — The plan's source-inspection assertions are brittle (`count("native_probe=") == 2`), though they are supplemental to behavioral tests.

**Suggestions**
- Add an explicit parameterized test for all four native owner labels and refusal details.
- Assert the unchanged `VersionStatus` fields directly in the service integration test.
- Prefer a shared native-owner tuple for update refusal and test that tuple contains exactly the four widened owner values.

**Risk:** MEDIUM — cross-module integration and ownership gating are high-impact, but the plan has strong placement, safety, and regression coverage.

### Overall Assessment

The five plans are substantially improved and collectively cover the phase goal. No critical blockers remain. The one actionable issue is the one-way closed-set assertion in 15-04; add the reverse coverage check before execution.

## Consensus Summary

Single reviewer both cycles (opencode-fallback) — no cross-reviewer corroboration to report. No HIGH-severity findings raised in either round.

**Round 1** (5 actionable MEDIUM, all now incorporated — see Round 1 Plan-Revision Conflicts entry above and commit `f339bd9`):
1. 15-01 success-gated-refresh gate had no teeth.
2. 15-03 AI-tab `palette=` left stale.
3. 15-03 whole-word id scan risked false positives.
4. 15-05 synthesized native-owner candidate not threaded into `candidates`.
5. 15-05 leftover-artifact × native-attribution interaction untested.

**Round 2** (2 actionable MEDIUM, unresolved as of this write):
1. **15-04** — the verify gate's closed-set assertion checks the wrong direction (`set(_PROBES) <= set(OWNER_PROBES)` instead of `set(OWNER_PROBES) <= set(_PROBES)`), leaving a real coverage gap: a future `OWNER_PROBES` entry with no matching `_PROBES` implementation would pass the gate and fail at runtime in `detect_owner`.
2. **15-05** — the plan states the native-owned `VersionStatus` fields (`stale=True`, `latest=None`, `source="unknown"`) should stay unchanged, but no task explicitly asserts this against `resolve_status`'s actual final branch — needs a direct assertion, not just an ownership check.

Additionally treated as actionable (a concrete behavioral requirement, not merely advisory): **15-05** — `UpdateOutcome.detail` must include the concrete owner name (`dnf`/`apt`/`pacman`/`rpm-ostree`), not a generic refusal phrase.

All other Round 2 findings (LOW-severity) are wording/robustness suggestions the reviewer frames as optional ("adequate for the current table," "acceptable... if the comment clearly states the audited scope") — treated as confirmations, not actionable items requiring a plan change.

## Verification coverage

Source-grounding: the reviewer traced every cited symbol against the live tree in both rounds (file:line citations throughout, cross-checked against `installer/wizard_app.py`, `installer/versions.py`, `installer/ownership.py`, `installer/install_ownership.py`, `installer/update.py`, `installer/registry.toml`, `installer/ui_common.py`, `installer/catalog_tui.py`, `installer/version_status.py`, `setup.py`, `installer/model.py`, and the corresponding test files). No UNCHECKABLE symbols reported. Cross-artifact fact-drift pass: no STATE.md/ROADMAP.md status divergence detected (phase in planning, not yet executed); no CONTEXT.md/PLAN.md term contradiction found. Round 2's first attempt at the opencode-fallback lane returned truncated narration-only output (no per-plan findings) despite `ok:true` — recorded in `failed_lanes` above; an immediate retry with the identical prompt produced this complete review.
