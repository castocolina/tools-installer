## 15-01

### Summary
The plan is executable and correctly addresses both Doctor behaviors. It matches the existing refresh lifecycle and preserves the process-level PATH snapshot semantics.

### Strengths
- Correctly identifies the missing call at `installer/wizard_app.py:389-394`; sibling refresh paths already establish `_refresh_guidance()` before `_refresh_body()` at lines 253-255 and 270-272.
- Tests a mutable guard source rather than relying on unchanged PATH guidance.
- Explicitly covers failed fixes that mutate state before raising, preserving `run_live`’s behavior.
- Keeps the note screen-local, appropriate because `installer/guidance.py` is pure and `self.applied` is UI state.

### Concerns
- **LOW:** The plan says the refresh is “after a successful fix” in several places while implementing it unconditionally. The task clarifies this adequately, but the final implementation summary should consistently call it an unconditional post-attempt refresh.

### Suggestions
- Keep the failed-fix test and the exact refresh ordering assertion as specified.

### Risk Assessment
**LOW** — isolated UI behavior, clear existing patterns, and strong regression tests.

## 15-02

### Summary
The version-parser plan is well-grounded and correctly fixes both independent `_OBSERVED_VERSION` call sites without weakening the strict declared-version parser.

### Strengths
- Correctly targets `installer/versions.py:70` and `:141`; both currently call `_OBSERVED_VERSION.fullmatch` independently.
- Reuses one matcher and the existing capture groups, avoiding divergence between feature-floor parsing and outdated comparison.
- Preserves `extract_observed_version`’s documented verbatim return contract at `installer/versions.py:116-126`.
- Explicitly protects `parse_declared_version` at `installer/versions.py:80-91`.
- The residual `procs` and bash cases are documented rather than incorrectly handled with broad substring parsing.

### Concerns
- **LOW:** The audit comment is date-specific (`2026-09-14`). This is acceptable for the requested audit record, but future registry additions can make the statement stale unless the test or comment clearly states the audited registry revision/scope.

### Suggestions
- Include the audited registry commit or an explicit “as of this registry contents” qualifier if available.

### Risk Assessment
**LOW** — the fallback remains fail-closed through `_OBSERVED_VERSION.fullmatch`, and both parser paths are covered.

## 15-03

### Summary
The tier corrections and AI-tab documentation updates are appropriately scoped. The plan correctly treats tier as presentation metadata rather than dependency-ordering logic.

### Strengths
- Grounds the two changes against the actual registry entries: `ast-grep` at `installer/registry.toml:1836-1841` and the existing `rg`/`fd` AI-tier entries.
- Updates the existing puppeteer and tier-count tripwires rather than weakening them.
- Adds explicit D-09 coverage for `mmdc`, `gitleaks`, `vale`, and `drawio-cli`.
- The comment scanner distinguishes backticked catalog citations from ordinary English, avoiding false positives from IDs such as `git` and `watch`.
- Correctly notices that the stale user-visible palette at `installer/ui_common.py:135` must change alongside the comment.

### Concerns
- **LOW:** The planned source scanner uses string slicing from `name="ai"` to `palette=`. This is adequate for the current table, but it is somewhat format-sensitive and could break on harmless formatting changes.

### Suggestions
- Prefer extracting the AI `View` block using a narrowly anchored structural pattern or keep the test intentionally documented as source-format-sensitive.

### Risk Assessment
**LOW** — declarative edits only, with registry-count and dependency regression tests.

## 15-04

### Summary
The rpm-ostree probe and registry opt-in plan is technically coherent and correctly preserves the existing probe architecture. Its wave dependency is appropriate because it shares registry tests with 15-03.

### Strengths
- Reuses `_method_values`, `_run`, and `_PROBES` from `installer/install_ownership.py:42-59` and `:167-185`.
- Correctly scopes ownership to the booted deployment’s `requested-packages`.
- Adds the new `"rpm-ostree"` value to the closed `OWNER_PROBES` set at `installer/model.py:55-64`, matching validation at `:654-660`.
- Correctly identifies all ten native-manager rows from the registry’s native method declarations.
- Places rpm-ostree before dnf so layered packages are attributed to the mechanism that installed them.
- Explicitly documents that `detect_owner` remains temporarily orphaned until 15-05.

### Concerns
- **MEDIUM:** The plan’s own verification gate checks `set(_PROBES) <= set(OWNER_PROBES)`, but the production contract is the reverse direction: every registry-declarable owner probe must have an implementation. The gate does not detect an `OWNER_PROBES` entry with no `_PROBES` implementation, which would make a future registry row load successfully and fail at `detect_owner`.
- **LOW:** The plan intentionally adds registry declarations before the production caller exists. The plan documents this correctly, but execution must not treat 15-04 alone as phase-complete.

### Suggestions
- Add an assertion for `set(OWNER_PROBES) <= set(_PROBES)` or explicitly assert equality.
- Keep 15-05 mandatory before release verification.

### Risk Assessment
**MEDIUM** — implementation risk is modest, but the closed-set validation gate has a one-way coverage gap.

## 15-05

### Summary
The final integration plan correctly handles the most consequential risk: verified native ownership must not accidentally authorize unsupported or privileged updates. It also places the ownership fallback before the real machine’s unattributed active-path return.

### Strengths
- Correctly identifies the live-path early return at `installer/ownership.py:333-345`; placing the adapter only before the final return would not fix real `/usr/bin/<cmd>` cases.
- Preserves the evidence rule by requiring empty candidates and no unreadable inventories.
- Requires a self-consistent synthetic candidate, matching the existing branch at `installer/ownership.py:356-373`.
- Widens `Owner` instead of using casts or type ignores.
- Adds refusal before the existing unsupported-owner exception at `installer/update.py:229-245`.
- Injects `run_probe`, whose stdin isolation is implemented at `installer/install_ownership.py:30-39`, into both display and mutation paths.
- Adds labels for new owners in the catalog, where the current map at `installer/catalog_tui.py:391-400` would otherwise silently omit them.

### Concerns
- **MEDIUM:** The plan claims that a native-owned tool’s `VersionStatus` should retain `stale=True`, `latest=None`, and `source="unknown"`, but the proposed tests must verify this against the actual final branch of `resolve_status`, not merely assert ownership. The plan mentions this, but it is an important integration contract because the new owner values widen every `Owner` consumer.
- **LOW:** The `_NATIVE_OWNER_DETAIL` constant is described as naming the owning manager, but the exact proposed formatting is left open. Ensure the returned `UpdateOutcome.detail` includes the concrete owner (`dnf`, `apt`, `pacman`, or `rpm-ostree`) rather than only a generic phrase.
- **LOW:** The plan’s source-inspection assertions are brittle (`count("native_probe=") == 2`), though they are supplemental to behavioral tests.

### Suggestions
- Add an explicit parameterized test for all four native owner labels and refusal details.
- Assert the unchanged `VersionStatus` fields directly in the service integration test.
- Prefer a shared native-owner tuple for update refusal and test that tuple contains exactly the four widened owner values.

### Risk Assessment
**MEDIUM** — cross-module integration and ownership gating are high-impact, but the plan has strong placement, safety, and regression coverage.

## Overall Assessment

The five plans are substantially improved and collectively cover the phase goal. No critical blockers remain. The one actionable issue is the one-way closed-set assertion in 15-04; add the reverse coverage check before execution.
