# Phase 8 Cross-AI Plan Reviews

## Cycle 1 (codex-sol-high)

**CYCLE_SUMMARY:** `current_high=5 current_actionable=6`

### HIGH findings

1. **08-01 violates ONESHOT Rule 7's same-commit test coverage requirement** — Task 1 adds
   the `uv-tool` kind but defers `test_model.py` coverage to Task 2 and declines any
   `test_status.py` addition. Fix: move all new-kind tests into Task 1's commit, add a
   `test_status.py` case proving a `uv-tool` registry tool is detected through its CLI shim.
2. **08-03 puts `rtk` in the wrong checksum regression set** — `SIDECAR_VERIFIED` requires
   `{asset}`-templated checksums; `rtk` uses a literal `checksums.txt`, so adding it there
   fails `test_sidecar_verified_tools_declare_checksums`. Fix: add `rtk` to
   `CHECKSUM_FILE_VERIFIED` instead (the literal-filename checksum set), not
   `SIDECAR_VERIFIED`.
3. **08-04's comment-locality test cannot pass with the prescribed comment placement** — the
   plan places each recommends comment AFTER `desc`/`id = "..."`, but the test searches only
   the lines PRECEDING `id`. Fix: place recommends comments above `[[tool]]`, matching every
   other dated-comment convention in this registry.
4. **08-04 leaves `tests/test_catalog_tui.py` stale** — not in `files_modified`, but an
   existing test loads the real registry and hardcodes the pre-Phase-8 recommends set
   (`rg, fd, jq`) for `claude`. Fix: add `test_catalog_tui.py` to `files_modified` and update
   the hardcoded expectation to the new per-host recommends lists.
5. **Phase close-out omits Tier-3 installer verification** — 08-04's close-out is
   unit/static-only despite ONESHOT Rule 14 requiring real disposable-container verification
   of new install methods. Fix: add a Tier-3 container check exercising Graphify's `uv tool
   install` path and RTK's archive-layout install, without touching the host.

### MEDIUM findings

6. **08-01's graphify identity gate uses `startswith`, not exact match** — passes
   `graphify-labs/graphify-malware`. Fix: exact string equality after normalization.
7. **08-03's RTK arm64 Linux tarball layout is asserted, not verified** — only x86_64/Darwin
   were inspected live. Fix: inspect the real arm64 tarball too.
8. **08-03 has contradictory immutable-Linux resolve expectations** — states both `["brew"]`
   and `["github_release", "brew"]` for the same fixture. Fix: keep only the one matching
   `resolve.py`'s actual behavior (`github_release` is never skipped on immutable Linux).
9. **08-02 never asserts `shell = "bash"`** on the two new script entries, despite the plan
   itself declaring both are Bash scripts (`_script` silently defaults to `sh` otherwise).
   Fix: add the assertion.
10. **08-03 never asserts the exact `repo = "rtk-ai/rtk"` value** in its tests. Fix: add it.
11. **08-04's Codex-caveat test doesn't test the caveat it's named for** — only checks
    `codegraph`/`graphify`/`rtk` are named, not the "instructions-based, not a runtime hook"
    phrase. Fix: assert the caveat text too.

### Disposition

All 11 findings applied directly (Rule 10 — plan-stage fixes, not original execution) rather
than a planner re-spawn, since each has a precise, mechanical fix. Proceeding to cycle 2.

## Cycle 2 (codex-sol-high)

**CYCLE_SUMMARY:** `current_high=2 current_actionable=4`

### HIGH findings

1. **08-04's Tier-3 task bypassed the real production entry point** — the prior draft called
   `_uv_tool`/`install_download` directly instead of `installer.engine.install_tool` (the only
   route `installer/app.py` actually uses), proving equivalent primitives rather than the
   catalog-to-production path. Fix: rewrote the task to load both tools via `model.load_tools`
   and drive both installs through `install_tool`, asserting `InstallOutcome.status`,
   `method_kind`, and (for `rtk`) `verified`.
2. **08-04's Tier-3 container recipe was underspecified** — no `curl`/`tar`/CA-cert install
   despite RTK's download path shelling out to `curl`, no `uv`'s `~/.local/bin` on `PATH`, a
   `pip install uv` option violating this repo's uv-only rule, no concrete tag-capture command.
   Fix: replaced with an exact, pinned `docker run --rm python:3.13-slim bash -c '...'` recipe
   installing prerequisites, `uv` via its official installer script (never pip), exporting the
   right `PATH` entries, and printing explicit `GRAPHIFY_OUTCOME`/`RTK_OUTCOME` evidence lines.

### MEDIUM findings

3. **Cycle-1 test fixes missing from executable task metadata** — 08-01 Task 1's `<files>` and
   `must_haves.artifacts` omitted `tests/test_status.py`; 08-04 Task 1's `<files>` and
   `must_haves.artifacts` omitted `tests/test_catalog_tui.py`; 08-04's `estimate.tasks` still
   said 2 after the Tier-3 task made it 3. Fix: added the missing files to both plans' `<files>`
   and `artifacts` lists, bumped `estimate.tasks` to 3.
4. **08-03's RTK arm64 tarball claim was internally unsupported** — `must_haves.key_links`
   claimed all three tarballs were inspected, but the executable `<action>` text and
   08-RESEARCH.md's Sources list still only cited x86_64-musl and Darwin. Fix: personally
   downloaded and `tar -tzf`-inspected the live `rtk-aarch64-unknown-linux-gnu.tar.gz` (tag
   `v0.48.0`) this session — confirmed bare top-level `rtk` binary, same shape as the other two —
   and aligned the `<action>` text and 08-RESEARCH.md's Sources entry to state all three were
   genuinely inspected.

### Disposition

All 4 findings applied directly (Rule 10). No new findings contradict cycle 1's fixes — the
checksum regression-set correction was independently confirmed correct. Proceeding to cycle 3.

## Cycle 3 (codex-sol-high) — max-cycle cap

**CYCLE_SUMMARY:** `current_high=2 current_actionable=2`

Reviewer confirmed the rewritten Tier-3 recipe's production-call signatures are all valid
(`load_tools`, `Platform(...)`, `install_tool(tool, platform)`) — no new HIGH on that front.

### HIGH findings

1. **08-04's Tier-3 recipe still couldn't capture the resolved RTK tag as evidence** —
   `install_tool(rtk, platform)` succeeds or fails silently on the tag; neither
   `resolve_github_tag` nor the download path logs it. Fix: pass a `logging_resolve_tag`
   wrapper via `install_tool`'s injectable `resolve_tag` parameter that prints `RTK_TAG <repo>
   <tag>` before returning, and record that line in the SUMMARY as the tag evidence.
2. **08-04's recommends-comment locality test window still excluded its own target text** —
   a fixed "10 lines" cap after `id = "..."` ends before `recommends`/the Codex caveat for a
   tool block with several fields between `id` and the comment. Fix: replaced the fixed-line
   cap with "extending through (but not past) that tool's first `[[tool.method]]` line" — no
   arbitrary line-count ceiling.

### MEDIUM findings

3. **08-01 had an unclosed `<files>` tag** — missing `</files>`, which would make GSD's own
   `task is-behavior-adding` classifier misclassify this task despite real source-file changes.
   Fix: added the closing tag.
4. **08-03 had a contradictory Darwin-arch claim** — `key_links` said the inspected Darwin
   tarball was `aarch64`, but the action text and 08-RESEARCH.md both correctly cite
   `x86_64-apple-darwin`. Fix: corrected the `key_links` typo to `x86_64 Darwin`, matching the
   real evidence (no arm64 Darwin tarball was ever downloaded or needed).

### Disposition

All 4 findings applied directly (Rule 10). This is the configured max-cycles cap (3) — per
ONESHOT-RULES Rule 10, proceeding directly to Phase 8 execution rather than dispatching a
cycle 4, since every finding across all three cycles had a precise, mechanical, directly-applied
fix and no cycle surfaced a structural/architectural objection requiring a planner re-spawn.
