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
