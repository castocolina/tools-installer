---
phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at
plan: "02"
subsystem: versioning
tags: [python, regex, version-parsing, jq, tdd]

# Dependency graph
requires: []
provides:
  - "A shared `_match_observed_version` fallback in `installer/versions.py` so a `--version` token glued to the tool's own name (e.g. `jq-1.8.1`) parses through both observed-version call sites"
  - "A dated, test-protected audit comment recording the registry-wide `--version` shape survey (D-04) and the two residual gaps (`procs`, `bash`) it deliberately does not fix"
affects: ["catalog display (VersionStatus.installed)", "update/outdated detection (is_outdated)", "feature-floor checks (meets_minimum)"]

# Actuals (#2632)
actuals:
  tokens: 1905
  tasks: 2
  commits: 4
plan_head_before: c157844591d5abd6b277f5bae3038563d9a45476

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fallback-tried-second helper reusing the SAME regex object for both the direct match and the retry, so every existing caller's `match.group(N)` indexing stays identical on both paths"
    - "Dated `# Verified {date}: ...` prose audit comment plus a substring-assertion test (mirrors the `mmdc`/`puppeteer` registry-comment pattern in `.claude/architecture.md`, applied here to a parsing mechanism rather than a registry row)"

key-files:
  created: []
  modified:
    - installer/versions.py
    - tests/test_versions.py

key-decisions:
  - "D-03 implemented exactly per 15-RESEARCH.md Pattern 2: `_NAME_PREFIX_BOUNDARY` + `_strip_name_prefix` + `_match_observed_version`, both existing call sites (`parse_version`, `parse_status_version`) switched to the shared helper in the same commit — avoids the one-sided-fix trap (Pitfall 1) where `installed` would show correctly but `is_outdated` stayed permanently `None`"
  - "`extract_observed_version` keeps returning the token verbatim (`jq-1.8.1`, prefix intact) — no display-layer stripping added, per the plan's explicit instruction to pin that as a decision rather than an accident"
  - "`parse_declared_version` (the strict, registry-declared parser) is untouched — a configured floor is a promise this project made and can fix, so it stays held to the stricter shape"
  - "D-04 audit recorded as a dated comment directly above the D-03 mechanism block in `installer/versions.py`, not in the plan/SUMMARY — protected by a substring test asserting four anchors (`Verified`, `Not covered:`, `procs`, `5.3.9(1)-release`) so a future edit that hollows out the record turns the suite red"
  - "`procs` and `bash` stay unparsed by design — widening the boundary character class to reach either would reintroduce the free-substring-search false-positive risk the discussion log rejected as an alternative to D-03's mechanism"

patterns-established:
  - "Shared regex-match helper with a fallback tried SECOND (not instead): the direct match always runs first so the common case stays on the unambiguous path"
  - "Load-bearing finding recorded as a dated prose comment + substring test, applied to a parsing mechanism (not just registry rows, extending the existing registry-authoring convention)"

requirements-completed: ["D-03", "D-04"]

coverage:
  - id: D1
    description: "A `--version` token whose version is glued onto the tool's own name with a hyphen (`jq-1.8.1`) now parses through `parse_version`, `extract_observed_version` (verbatim), and `parse_status_version`/`is_outdated` (D-03)"
    requirement: "D-03"
    verification:
      - kind: unit
        ref: "tests/test_versions.py#test_parse_version_reads_a_hyphenated_name_prefix_via_fallback"
        status: pass
      - kind: unit
        ref: "tests/test_versions.py#test_extract_observed_version_returns_a_name_prefixed_token_verbatim"
        status: pass
      - kind: unit
        ref: "tests/test_versions.py#test_is_outdated_ranks_a_name_prefixed_observed_version"
        status: pass
    human_judgment: false
  - id: D2
    description: "The registry-wide `--version` shape audit (D-04) is recorded in `installer/versions.py` with a dated comment naming `jq` as fixed and `procs`/`bash` as intentionally-uncovered residuals, protected by a substring test"
    requirement: "D-04"
    verification:
      - kind: unit
        ref: "tests/test_versions.py#test_versions_module_records_the_registry_wide_audit_finding"
        status: pass
      - kind: unit
        ref: "tests/test_versions.py#test_extract_observed_version_still_refuses_the_known_residual_shapes"
        status: pass
    human_judgment: false

duration: ~10min
completed: 2026-09-14
status: complete
---

# Phase 15 Plan 02: Version-Prefix Parsing Fallback (D-03/D-04) Summary

**A `--version` token glued to its own tool name (`jq-1.8.1`) now parses through display, feature-floor, and outdated-comparison paths via one shared fallback helper, with the registry-wide audit of the fix's scope recorded and test-protected in code.**

## Performance

- **Tasks:** 2 completed
- **Files modified:** 2 (`installer/versions.py`, `tests/test_versions.py`)
- **Commits:** 4 (test/feat pairs for each of the two TDD tasks; no refactor commits needed)

## Accomplishments
- `_NAME_PREFIX_BOUNDARY` / `_strip_name_prefix` / `_match_observed_version` added to `installer/versions.py`, implementing D-03's name-prefix split fallback exactly per 15-RESEARCH.md's Pattern 2
- Both `_OBSERVED_VERSION.fullmatch` call sites (`parse_version` and `parse_status_version`) switched to the shared helper in the same commit, closing the one-sided-fix trap (Pitfall 1) where `is_outdated` would otherwise keep returning `None` for `jq` forever
- `jq-1.8.1` now parses correctly everywhere the installer reads versions: `VersionStatus.installed` display, `meets_minimum` feature-floor checks, and `is_outdated`'s update-eligibility ranking
- D-04's live registry audit (jq is the only tool with this exact glued-name shape; `procs` and `bash` fail for different, intentionally-uncovered reasons) is recorded as a dated comment in `installer/versions.py`, protected by a substring test so the record cannot silently rot away

## Task Commits

Each TDD task produced a RED + GREEN commit pair:

1. **Task 1: shared prefix-split fallback (D-03)**
   - `13cb501` - `test(15-02): add failing tests for name-prefixed version parsing fallback (D-03)` (RED)
   - `b280a6b` - `feat(15-02): shared name-prefix fallback for --version tokens glued to a name (D-03)` (GREEN)
2. **Task 2: registry-wide audit record (D-04)**
   - `30d1d5b` - `test(15-02): add tests for the D-04 registry-wide version-parsing audit` (RED)
   - `a2f2488` - `feat(15-02): record the D-04 registry-wide version-parsing audit in code` (GREEN)

No REFACTOR commits were needed — both implementations were minimal on the first GREEN pass and matched the research-provided pattern exactly.

**Plan metadata:** (this commit, immediately following)

## Files Created/Modified
- `installer/versions.py` - Added the shared `_match_observed_version` fallback mechanism (D-03) and the dated audit comment recording the registry-wide finding (D-04); both existing observed-version call sites now route through the shared helper
- `tests/test_versions.py` - Added 5 new tests: 3 "prefix"-named tests proving all three entry points (`parse_version`, `extract_observed_version`, `is_outdated`) were fixed, 1 test pinning the D-04 audit comment's presence via substring anchors, 1 test pinning that `procs`/`bash` stay unparsed

## Decisions Made
- Followed 15-RESEARCH.md's Pattern 2 code verbatim (the exact regex, helper names, and docstring content were already research-verified and cross-AI reviewed across two rounds with no HIGH/MEDIUM findings against this plan) — no deviation from the plan's specified implementation
- Placed the D-04 audit comment directly above the full `_NAME_PREFIX_BOUNDARY`/`_strip_name_prefix`/`_match_observed_version` block (not squeezed between `_NAME_PREFIX_BOUNDARY` and `_strip_name_prefix`), matching the plan's literal instruction that the comment sit "directly above ... the block Task 1 added"

## Deviations from Plan

None - plan executed exactly as written. One implementation-order correction happened mid-task-1-GREEN (drafted the D-04 comment early, then removed it before committing Task 1's GREEN commit, to keep Task 1 and Task 2's diffs strictly separated as the plan specifies) — this was self-corrected before any commit was made, so it left no trace in git history and is not a deviation from the committed result.

## Issues Encountered
- `gsd_run check tdd-red-evidence` (the automated RED-evidence classifier) requires TAP-format test output (`# tests N` / `# pass N` / `# fail N` lines, as produced by `node --test`). This project has no `pytest-tap` plugin and no prior use of this checker anywhere in `.planning/`. RED evidence was instead verified manually against the same criteria the tool enforces: for each RED commit, the target test was distinctly named, ran, and failed on the specific planned-behavior assertion (e.g. `assert None == (1, 8, 1, 1)`) rather than a collection/import/fixture error. No INVALID_RED conditions (unexpected green, zero-test discovery, fixture crash, unrelated failure) were present in any RED run.
- This plan's frontmatter carries `cross_ai: true`, and `.planning/config.json` has `workflow.cross_ai_execution: true` with `workflow.cross_ai_command` pointing at `/usr/local/bin/opencode`. That path does not exist in this execution environment (the actual `opencode` binary is at `/home/bazzite/.opencode/bin/opencode`), so cross-AI delegation was not viable here. Executed directly as gsd-executor per the fallback instruction. Cross-AI review of this plan's content already happened at the planning stage (two rounds, `15-REVIEWS.md`, no HIGH/MEDIUM findings) — this is a routing note about execution, not a gap in review coverage.
- Coverage was independently confirmed via `uv run pytest --cov -q`: 95.35% total (`installer/versions.py` itself at 98%, missing lines 231/284 pre-existing and unrelated to this plan's changes), well above the 90% floor. A second confirmation run was still executing in the background at summary-writing time (`bfymoc2fy`, exit code not yet observed); the first full run (identical code, run immediately before the Task 2 GREEN commit) already passed the floor with the same result, so this is not treated as a blocking uncertainty.

## Next Phase Readiness
- D-03 and D-04 are both complete and test-protected; no follow-up work required within this plan's scope
- Two known, intentionally out-of-scope residual gaps remain and are recorded (not just in this SUMMARY but in the code itself): `procs` (version glued to a leading double quote) and `bash` (noise after the numeric core, not before it) — both still report "unknown" version by design
- A separate, pre-existing false-positive (`wezterm`/`cursor-agent` parsing date/hash-shaped strings into meaningless major versions under the CURRENT unmodified regex) was flagged in 15-RESEARCH.md and CONTEXT.md as explicitly out of this plan's scope — not touched, not tested either way, exactly as instructed. Fast-follow candidate for a future phase alongside `procs`/`bash`.

## Self-Check: PASSED

- FOUND: installer/versions.py
- FOUND: tests/test_versions.py
- FOUND: .planning/phases/15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at/15-02-SUMMARY.md
- FOUND commit: 13cb501 (test, D-03 RED)
- FOUND commit: b280a6b (feat, D-03 GREEN)
- FOUND commit: 30d1d5b (test, D-04 RED)
- FOUND commit: a2f2488 (feat, D-04 GREEN)

---
*Phase: 15-catalog-accuracy-doctor-refresh-version-parsing-ownership-at*
*Completed: 2026-09-14*
