---
phase: 08-ai-tier-catalog-expansion-uv-tool-executor
verified: 2026-09-06T00:00:00Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 8: AI Tier Catalog Expansion & uv-tool Executor — Verification Report

**Phase Goal:** The agent-facing tools this project exists to serve — including the new
`uv-tool` installer kind `graphify` needs — are in the catalog with verified install
methods, and selecting an agent host surfaces its recommended companion tools.

**Verified:** 2026-09-06
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `installer/executors.py` has a working `kind="uv-tool"` executor; `graphify` installs via it using PyPI package `graphifyy`; `resolve.py`'s `_applies`/`_RANK` handle `uv-tool` and are tested | ✓ VERIFIED | `_uv_tool(method, runner)` at `installer/executors.py:456-458` runs `runner(["uv", "tool", "install", pypi_pkg])`; registered in `EXECUTORS` dict (line 493). `installer/resolve.py`'s `_RANK["uv-tool"] = 20` (line 16) and `_applies`'s unconditional-True kind tuple includes `"uv-tool"` (line 51, with an explanatory comment tying it to `deps.py`'s `requires=["uv"]` edge). `graphify`'s registry entry (`installer/registry.toml`): `id="graphify"`, `tier="ai"`, `requires=["uv"]`, one `[[tool.method]]` with `kind="uv-tool"`, `pypi_pkg="graphifyy"`. Unit tests read and confirmed real (not stubs): `test_uv_tool_executor_builds_uv_tool_install`, `test_uv_tool_without_pypi_pkg_raises_executor_error` (test_executors.py); `test_uv_tool_is_userspace_ranked_before_brew`, `test_uv_tool_applies_on_every_platform_including_immutable` (test_resolve.py); `test_graphify_uses_the_uv_tool_executor_and_requires_uv`, `test_selecting_graphify_drags_in_uv` (test_registry.py); `test_uv_tool_kind_parses_with_pypi_pkg` (test_model.py); `test_uv_tool_status_is_detected_through_its_cli_shim` (test_status.py). Independently re-ran a live Tier-3 container install (see Probe Execution below): `GRAPHIFY_OUTCOME installed uv-tool False`, `graphify --version` → `graphify 0.9.55`. |
| 2 | `cursor-agent` and `antigravity` exist as verified `tier="ai"` entries installing via their own official vendor scripts (not a cask pointing at the wrong GUI product); `cursor-agent.cmd == "cursor-agent"` | ✓ VERIFIED | `installer/registry.toml`: `cursor-agent` — `tier="ai"`, `cmd="cursor-agent"` (confirmed literal, not `"agent"`), one method `kind="script"`, `url="https://cursor.com/install"`, `shell="bash"`, no `kind="cask"` fallback present. `antigravity` — `tier="ai"`, `cmd="agy"`, one method `kind="script"`, `url="https://antigravity.google/cli/install.sh"`, `shell="bash"`, no cask fallback. Dated comments record the live-verified finding that each vendor's only Homebrew cask installs the GUI IDE app, a different product, hence no cask fallback declared. Tests: `test_cursor_agent_uses_the_legacy_collision_safe_cmd_name`, `test_antigravity_installs_via_official_script_with_no_recommends`, `test_cursor_agent_and_antigravity_scripts_resolve_on_every_platform`, `test_cursor_agent_and_antigravity_entries_record_the_verification_findings`, `test_human_agent_clis_are_p0_human_tools`, `test_agent_clis_use_supported_install_methods` — all present in `tests/test_registry.py` and pass in the full suite run. |
| 3 | `rtk` installs via `kind="github_release"` from `rtk-ai/rtk`, checksum-verified, with the real arch-gated musl/gnu Linux split | ✓ VERIFIED | `installer/registry.toml`: `rtk` has four methods — macOS universal (`asset="rtk-{arch.machine}-apple-darwin.tar.gz"`), Linux amd64 (`arch=["amd64"]`, `asset="rtk-{arch.machine}-unknown-linux-musl.tar.gz"`), Linux arm64 (`arch=["arm64"]`, `asset="rtk-{arch.machine}-unknown-linux-gnu.tar.gz"`), and a `brew` fallback (`formula="rtk"`). All three `github_release` methods pin `repo="rtk-ai/rtk"`, `checksum="checksums.txt"`. Tests: `test_rtk_installs_via_checksum_verified_github_release_with_brew_fallback`, `test_rtk_linux_methods_are_arch_gated_by_the_real_musl_gnu_asset_split`, `test_rtk_resolves_via_download_and_brew_even_on_immutable_linux`, `test_rtk_macos_method_is_arch_unrestricted`, `test_rtk_entry_records_the_musl_gnu_split_and_brew_confirmation` — all present and pass. Independently re-ran the live Tier-3 container install: `RTK_TAG rtk-ai/rtk v0.48.0`, `RTK_OUTCOME installed github_release True` (checksum `verified=True` asserted by the script), `rtk --version` → `rtk 0.48.0`. |
| 4 | `claude`/`opencode`/`codex`/`cursor-agent` each surface `recommends = ("codegraph", "graphify", "rtk")` via the existing Phase 2 mechanism; `antigravity` remains unwired | ✓ VERIFIED | Read `installer/registry.toml` directly: `claude`, `opencode`, `codex`, `cursor-agent` each carry `recommends = ["codegraph", "graphify", "rtk"]`; `antigravity`'s block has no `recommends` field at all. Confirmed via `test_agent_host_recommends_match_the_researched_per_host_set` (`tools["antigravity"].recommends == ()`) and `test_agent_host_recommends_entries_record_the_rtk_codex_caveat`. This is the honest result of a locked planning decision (08-CONTEXT.md D-01: "You can deio antigravity for now" — deferred, not dropped), and the ROADMAP.md SC#4 wording was amended in-place during planning to match, which is a documented, non-scope-reducing deviation, not an unresolved gap. |

**Score:** 4/4 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/executors.py` | `_uv_tool` executor, registered in `EXECUTORS` | ✓ VERIFIED | Present, substantive (real argv build, error on missing param), wired (called via `execute()` dispatch, exercised by `install_tool`) |
| `installer/model.py` | `METHOD_KINDS` includes `"uv-tool"` | ✓ VERIFIED | Line 16, part of the closed validation tuple `load_tools` checks against |
| `installer/resolve.py` | `_applies`/`_RANK` handle `uv-tool` | ✓ VERIFIED | Rank 20 (userspace tier), unconditional-True in `_applies`; closes a real pre-existing `KeyError` gap (confirmed by reading the diff base commit `85f02a5f...` vs HEAD) |
| `installer/registry.toml` | `graphify`, `cursor-agent`, `antigravity`, `rtk` entries + 4-host `recommends` wiring | ✓ VERIFIED | All four new tool entries present with correct shape; `recommends` wired on 4 of 5 agent hosts per locked decision |
| `tests/test_executors.py`, `test_resolve.py`, `test_model.py`, `test_registry.py`, `test_status.py`, `test_catalog_tui.py` | New/updated coverage for all of the above | ✓ VERIFIED | All referenced test functions read directly and confirmed to assert real, specific behavior (not existence-only checks); full suite passes |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `graphify` registry entry | `installer/executors.py::_uv_tool` | `kind="uv-tool"` dispatch through `EXECUTORS` | ✓ WIRED | Confirmed by direct read of `execute()` and by live Tier-3 re-run: `install_tool` resolved `graphify` to the `uv-tool` method and ran the real executor |
| `graphify`/`rtk` catalog entries | `installer/engine.py::install_tool` | Real production entry point (same one `app.py` uses) | ✓ WIRED | Independently re-executed the plan's exact container recipe against `installer.engine.install_tool` (not a lower-level primitive) and reproduced the SUMMARY's claimed output verbatim |
| `claude`/`opencode`/`codex`/`cursor-agent` `recommends` field | Phase 2's selection-time prompt mechanism | Existing `Tool.recommends` field, unchanged mechanism | ✓ WIRED | Field populated with real data; mechanism itself is out of this phase's scope (built in Phase 2, unmodified here) — confirmed the field is read the same way by grepping `catalog_tui.py`'s `_announce_requires`/recommends-prompt code path, which is unchanged |

### Behavioral Spot-Checks / Probe Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `uv-tool` executor installs `graphify` end-to-end through the real production path | Independently re-ran the exact `docker run --rm python:3.13-slim` Tier-3 recipe from `08-04-PLAN.md` Task 2 against `installer.engine.install_tool` | `GRAPHIFY_OUTCOME installed uv-tool False`; `graphify --version` → `graphify 0.9.55` | ✓ PASS (matches SUMMARY.md verbatim) |
| `github_release` executor installs `rtk` end-to-end, checksum-verified, through the real production path | Independently re-ran the exact `docker run --rm python:3.13-slim` Tier-3 recipe for `rtk` against `installer.engine.install_tool` | `RTK_TAG rtk-ai/rtk v0.48.0`; `RTK_OUTCOME installed github_release True` (`verified=True` asserted); `rtk --version` → `rtk 0.48.0` | ✓ PASS (matches SUMMARY.md verbatim) |
| Full test suite passes with the required coverage floor | `uv run pytest --cov` (raw, bypassing the local `rtk` CLI-proxy hook which intermittently returned "No tests collected" on repeated identical invocations — `rtk proxy` used to bypass it) | `1250 passed`, `TOTAL coverage 99.40%`, `Required test coverage of 90.0% reached` | ✓ PASS |
| `make validate` (lint/format/types/security/dead-code/shellcheck) | `make validate` | ruff check: all passed; ruff format: 89 files formatted; pyright: 0 errors/warnings; bandit: clean (documented skips only); vulture: clean; shellcheck: clean | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REQ-uv-tool-executor | 08-01 | New `kind="uv-tool"` executor + `graphify` entry | ✓ SATISFIED | See Truth #1 above |
| REQ-agent-host-entries | 08-02 | `cursor-agent`/`antigravity` verified official-script entries | ✓ SATISFIED | See Truth #2 above |
| REQ-rtk-github-release | 08-03 | `rtk` checksum-verified `github_release` entry | ✓ SATISFIED | See Truth #3 above |
| REQ-recommends-wiring-agent-hosts | 08-04 | Real per-host `recommends` data on the four wired hosts | ✓ SATISFIED | See Truth #4 above |

Note: `.planning/REQUIREMENTS.md` still lists all four as "Pending" as of this verification pass — this is the expected pre-ship state; the requirements ledger is updated during milestone close-out, not during phase execution, and does not indicate a gap in the phase's own delivery.

### Anti-Patterns Found

None. Grepped all phase-modified files (`installer/executors.py`, `installer/model.py`, `installer/resolve.py`, `installer/registry.toml`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-return patterns — zero matches.

### Code Review (`08-REVIEW.md`, dual-lane)

Two independent review lanes ran over the full diff (`85f02a5f4f5fa6a55e845079b8d0c75b10b5b9c8..HEAD`):
- **Lane 1 (internal):** 0 Critical, 2 Warnings (WR-01: RTK arm64-Darwin tarball layout not independently inspected; WR-02: verbatim-duplicated per-host `recommends` comment), 2 Info (accepted, cosmetic/pre-existing-pattern).
- **Lane 2 (codex-sol-high, independent dispatch):** 0 Critical/High, 1 Medium (M-01: `curl|sh` script executor can mask a failed download as `INSTALLED` — a pre-existing pattern shared by 7+ prior `kind="script"` entries, not introduced by this phase; accepted residual, out of scope).

Both Warnings were fixed and independently confirmed present in the current `installer/registry.toml`:
- WR-01 fix confirmed: the `rtk` entry's dated comment now explicitly states the `aarch64-apple-darwin` asset "was NOT independently downloaded/inspected" and names the assumption.
- WR-02 fix confirmed: the codex-specific `rtk`/Codex caveat sentence now appears only in `codex`'s own comment block; `claude`/`opencode`/`cursor-agent`'s comments were trimmed and instead point to "see codex's own recommends comment."

`make validate && make test` re-verified after the fixes at **1250 passed, 99.40% coverage** — matches the SUMMARY.md and REVIEW.md claims exactly, independently reproduced in this verification pass.

No unresolved Critical/High findings remain.

### Human Verification Required

N/A — Infrastructure/catalog-data phase with no user-facing UI changes introduced. All four success criteria are registry/executor data-and-wiring facts, independently verified programmatically (including two live Tier-3 container installs re-run by this verifier, not merely trusted from the SUMMARY).

### Gaps Summary

None. All four roadmap Success Criteria are independently verified against the current codebase state (not merely SUMMARY.md's claims): the `uv-tool` executor and resolver fix are present, tested, and proven live; `cursor-agent`/`antigravity` are real vendor-script entries with the correct `cmd`; `rtk` is a real checksum-verified, arch-split `github_release` entry, proven live; and `recommends` wiring matches the locked-decision scope (four hosts wired, `antigravity` explicitly and intentionally deferred). `make validate && make test` both pass cleanly on the exact current tree (1250 passed, 99.40% coverage, 0 lint/type/security findings). The dual-lane code review found no unresolved Critical/High findings — both Warnings were fixed and confirmed in the registry file itself, and the one Medium finding from the second lane is a documented, out-of-scope pre-existing pattern.

---

_Verified: 2026-09-06_
_Verifier: Claude (gsd-verifier)_
