---
phase: "16"
slug: "detection-version-and-ownership-must-answer-is-it-on-this-di"
status: backfilled
nyquist_compliant: true
wave_0_complete: true
created: "2026-10-09"
backfilled: "2026-10-10"
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via `uv run pytest --cov`, confirmed in `Makefile:50-51` and `pyproject.toml`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_ownership.py tests/test_install_ownership.py tests/test_skill_lifecycle.py tests/test_rcclean.py -x` |
| **Full suite command** | `uv run pytest --cov` |
| **Estimated runtime** | ~300 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** the narrowest `-k`-filtered pytest invocation matching the touched module
- **After every plan wave:** `uv run pytest --cov` (full suite)
- **Before `/gsd-verify-work`:** Full suite must be green, plus the CONTEXT.md-mandated live proof against a real host reproducing each of the five original defects (see Manual-Only Verifications — this is not satisfied by unit tests alone)
- **Max feedback latency:** 300 seconds

---

## Per-Task Verification Map

*Backfilled 2026-10-10 from the executed plans. Each row's command was run in this plan; Status is that run.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 16-01 | 1 | D-01/D-05 | — | SDKMAN-owned tool resolves to `owner="sdkman"`, update dispatches through it | unit | `uv run pytest tests/test_ownership.py -k sdkman -x` | ✅ | ✅ green |
| 16-01-02 | 16-01 | 1 | D-01 (probe fix) | — | `_sdkman` probe matches `kind="sdkman"`/`candidate` param | unit | `uv run pytest tests/test_install_ownership.py -k sdkman -x` | ✅ | ✅ green |
| 16-15-01 | 16-15 | 6 | D-02 | — | Off-policy tool row carries "≠ policy" marker | unit | `uv run pytest tests/test_catalog_tui.py -k off_policy -x` | ✅ | ✅ green |
| 16-02-01 | 16-02 | 1 | D-09 | — | `supported_harnesses` validated against (widened) `SKILL_HARNESSES` | unit | `uv run pytest tests/test_model.py -k skill_harnesses -x` | ✅ | ✅ green |
| 16-12-01 | 16-12 | 4 | D-10/D-14 | — | skill_pack status cached with same staleness model as versions | unit | `uv run pytest tests/test_version_cache.py -x` | ✅ | ✅ green |
| 16-12-02 | 16-12 | 4 | D-13 | — | Multi-host Owner column truncation | unit | `uv run pytest tests/test_catalog_tui.py -k skill_owner_cell -x` | ✅ | ✅ green |
| 16-13-02 | 16-13 | 4 | D-17/D-20 | — | Explicit re-selection of already-installed tool updates/confirms and re-applies post-install only on this path | unit | `uv run pytest tests/test_engine.py tests/test_post_install.py -x` | ✅ | ✅ green |
| 16-09-01 | 16-09 | 3 | D-18 | — | Dangling pnpm shim reads as distinct "broken" state | unit | `uv run pytest tests/test_status.py tests/test_catalog_tui.py -k "broken or dangling" -x` | ✅ | ✅ green |
| 16-08-01 | 16-08 | 2 | D-21/D-23/D-24 | T-15.8 precedent (byte-exact refusal, case-guard emission reused) | Guard-in-place rewrite, backed up, per-file opt-in | unit | `uv run pytest tests/test_shellrc.py tests/test_rcclean.py -k "guard_in_place or path_writer_lines" -x` | ✅ | ✅ green |
| 16-08-02 | 16-08 | 2 | D-22 | — | Foreign marker block never touched | unit | `uv run pytest tests/test_rcclean.py -k marker_block -x` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Confirm existence and exact names of `tests/test_catalog_tui.py`, `tests/test_model.py`, `tests/test_engine.py`, `tests/test_post_install.py`, `tests/test_status.py`, `tests/test_version_cache.py`, `tests/test_deps.py`
- [x] A fixture/helper for constructing a `Tool` with a `kind="sdkman"` method plus a competing `kind="brew"` method (the groovy off-policy shape) — add if `test_ownership.py` lacks one for this dual-owner shape
- [x] A fixture reproducing the dangling-pnpm-shim shape (shim file present, `pnpm list --global` output not listing the package) for D-18 — new, mirroring the pending todo's live repro

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live proof against the real defects this phase fixes (skill_pack detection, sdkman version/ownership, kitty's silent no-method row, outdated-tool re-select no-op) | Phase goal ("Proven against the real defects below on a host that reproduces each one") | Unit tests prove the mechanism; the phase goal demands proof against a host that actually reproduces each original live defect — not satisfiable by mocked unit tests alone | Run the built app (or a disposable container reproducing the five defect shapes) at end-of-phase, per the `human_verify_mode: end-of-phase` pattern already used by prior phases (e.g. 15.4-05) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [ ] Feedback latency < 300s — full suite observed `3395 passed, 5 skipped in 320.66s` on 2026-10-10 (over the 300s cap)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** map backfilled by plan 16-16 on 2026-10-10. Human walkthrough rows stay pending until end-of-phase review.
