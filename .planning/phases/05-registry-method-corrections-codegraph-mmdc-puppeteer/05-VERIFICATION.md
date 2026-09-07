---
phase: 05-registry-method-corrections-codegraph-mmdc-puppeteer
verified: 2026-09-05T23:59:00Z
status: passed
score: 3/3 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer) Verification Report

**Phase Goal:** `codegraph`, `mmdc`, and the puppeteer/chrome-headless-shell chain mmdc actually depends on all have explicit, researched, correctly-recorded install methods — no tool silently depends on npm/pnpm underneath a method that looks like it doesn't.
**Verified:** 2026-09-05
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `codegraph` installs via `kind="github_release"`, not `pnpm add -g` | ✓ VERIFIED | `installer/registry.toml` codegraph entry has two `[[tool.method]]` blocks, both `kind = "github_release"` (macos + debian/arch/fedora), each with `checksum = "SHA256SUMS"`. `tests/test_registry.py::test_codegraph_methods_are_github_release_only` asserts `{m.kind for m in codegraph.methods} == {"github_release"}`; `test_codegraph_github_release_is_os_split_checksum_verified_and_nested` and `test_codegraph_entry_records_the_no_brew_formula_finding` pass. Ran targeted + full suite: all green. |
| 2 | `mmdc`'s install method decided explicitly after real research, decision + rationale recorded (pnpm-with-mitigation vs. brew vs. volta) | ✓ VERIFIED | `installer/registry.toml` carries a ~50-line dated comment block ("Install-method decision (2026-09-05, this phase's research)") rejecting Homebrew (upstream README says path is "no longer supported", GitHub issue #1122) and Volta (shells out to unrestricted `npm install --global`, no scripts of mmdc's own to gate) against four named criteria (stability/security/simplicity/maintainability); decision mirrored in `.planning/PROJECT.md` decision-log row citing "Phase 5 (05-03)". mmdc stays `kind="node"`/pnpm with `co_install`/`allow_build`/`versions`/`min_node`/`smoke` params, justified by pnpm's Global Packages peer-resolution semantics. |
| 3a | `puppeteer` exists as its own catalog entry | ✓ VERIFIED | `installer/registry.toml` has a standalone `id = "puppeteer"` tool, `tier = "user"`, `requires = ["pnpm"]`, two `kind="node"` methods (macOS both arches; Linux amd64 only). `tests/test_registry.py::test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm` passes. |
| 3b | `chrome-headless-shell` resolved as needing no entry, reason recorded + test-guarded | ✓ VERIFIED | No `id = "chrome-headless-shell"` block exists in registry.toml. `tests/test_registry.py::test_no_chrome_headless_shell_catalog_entry` asserts `"chrome-headless-shell" not in ids` (passes). Reason recorded in registry.toml comment ("chrome-headless-shell needs no entry of its own: it arrives with that same postinstall...") and in ROADMAP.md's amended SC#3 text. |
| 3c | `mmdc.requires` includes `puppeteer`, drags it in via existing resolver | ✓ VERIFIED | `mmdc.requires = ("pnpm", "puppeteer")` confirmed via `tests/test_registry.py::test_mmdc_requires_puppeteer_and_groups_the_node_install` and `test_selecting_mmdc_drags_in_pnpm_and_puppeteer_on_linux_amd64` (asserts resolver order `pnpm < puppeteer < mmdc`, both in `dragged_in`) — zero new code in `installer/deps.py`. |
| 3d | macOS vs. Linux dependency behavior verified, not assumed (incl. Linux arm64 gap) | ✓ VERIFIED | `test_puppeteer_resolves_no_method_on_linux_arm64_because_chrome_has_no_binary` confirms `resolve_methods` returns `[]` on debian/arch/fedora arm64 (no Chrome arm64 binary). `test_mmdc_skips_on_linux_arm64_when_puppeteer_is_unavailable` confirms `mmdc`/`puppeteer` are dropped from the install order with an "unavailable" warning via the existing `installer/deps.py::is_blocked` path — zero new ordering code. Registry records the platform split (`os = [...]`, `arch = ["amd64"]` on Linux puppeteer methods). |

**Score:** 3/3 ROADMAP success criteria verified (decomposed into 5 sub-checks, all passing). No truths left behavior-unverified — the one plausibly behavior-dependent item (the `puppeteer-browser` smoke check actually detecting a non-functional browser) is covered by a unit test asserting the real launch script (`puppeteer.launch()` / `newPage()` / `browser.close()`) is invoked (`test_launch_probe_defers_every_browser_choice_to_puppeteer`), plus independent Tier-3 container evidence (`LIBCHECK=fail` on a library-starved image, recorded in 05-01-SUMMARY.md) that the exact false-success case the check exists to catch was reproduced and caught.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `installer/registry.toml` | codegraph/mmdc/puppeteer entries + decision rationale | ✓ VERIFIED | Present, substantive, wired (see truths above) |
| `installer/model.py` | node-method param validation (co_install/allow_build/versions/min_node/smoke) | ✓ VERIFIED | `_parse_pkg_list`, `_parse_version_map`, `SMOKE_CHECK_NAMES` present; exercised by `tests/test_model.py` |
| `installer/executors.py` | grouped pnpm argv, version preflight, browser smoke check | ✓ VERIFIED | `_node`, `_require_minimum`, `_default_launch_puppeteer`, `SMOKE_CHECKS` present and covered by `tests/test_executors.py` |
| `installer/versions.py` | fail-closed version parsing/floors | ✓ VERIFIED | `parse_version` explicitly refuses to zero-fill an unparseable component (M1 fix verbatim in source); `PNPM_CO_INSTALL_MIN = "11.1.0"` (H3 fix) |
| `installer/pnpm_globals.py` | group-aware, pin-aware replay + split/incomplete detection | ✓ VERIFIED | `split_install_groups`, `incomplete_install_groups`, `reinstall_argv`, `reinstall_node_globals`, `reinstall_preview` all present, tested against real captured `pnpm list -g --json` fixtures (`_SPLIT_STATE_JSON`, `_GROUPED_STATE_JSON`) |
| `installer/guidance.py` | split/incomplete-group Doctor warnings | ✓ VERIFIED | `node_globals_guidance` emits WARN items for `split_groups` and `incomplete_groups` with the load-bearing `_REINSTALL_NEXT_STEP` prefix |
| `.planning/PROJECT.md` | mmdc decision recorded at project level | ✓ VERIFIED | Decision-log row present, citing Phase 5 (05-03) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `installer/deps.py::resolve_dependencies` | `mmdc` → `puppeteer` → `pnpm` | `requires` chain | ✓ WIRED | `test_selecting_mmdc_drags_in_pnpm_and_puppeteer_on_linux_amd64` passes with zero new resolver code |
| `installer/deps.py::is_blocked` | Linux arm64 unavailability → skip warning | `available=lambda tool: bool(resolve_methods(...))` | ✓ WIRED | `test_mmdc_skips_on_linux_arm64_when_puppeteer_is_unavailable` passes |
| `installer/executors.py::_node` | grouped argv → real pnpm install | comma-joined `co_install`/`allow_build` | ✓ WIRED | Unit-tested argv shapes match 05-01's Tier-3-observed invocations exactly |
| `setup.py::_build_app` | registry-derived policy → TUI Doctor split-group detection | `pnpm_globals.audit_node_globals(tools, policy=policy)` | ✓ WIRED | `setup.py:263` passes policy; `installer/app.py:266` (console `run_doctor`) deliberately passes none, matching the documented, test-covered console/TUI split |
| `installer/guidance.py::node_globals_guidance` | split/incomplete report → Doctor WARN row | `DoctorScreen._tui_guidance` prefix rewrite | ✓ WIRED | `_REINSTALL_NEXT_STEP` prefix shared by both call sites, tested in `tests/test_guidance.py` |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|------------|--------|----------|
| REQ-codegraph-github-release | 05-02 | ✓ SATISFIED | See Truth #1 |
| REQ-mmdc-install-decision | 05-03 | ✓ SATISFIED | See Truth #2 |
| REQ-puppeteer-catalog-entries | 05-01, 05-03, 05-04 | ✓ SATISFIED | See Truths #3a-3d |

No orphaned requirements found for Phase 5 in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

None. Scanned `installer/model.py`, `installer/executors.py`, `installer/versions.py`, `installer/registry.toml`, `installer/pnpm_globals.py`, `installer/guidance.py`, `installer/app.py`, `installer/wizard_app.py`, `setup.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` — zero matches.

### Behavioral Spot-Checks / Test Execution

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Targeted phase test files | `pytest tests/test_registry.py tests/test_model.py tests/test_executors.py tests/test_versions.py tests/test_pnpm_globals.py tests/test_guidance.py tests/test_node_install_e2e.py` | 289 passed | ✓ PASS |
| Full suite (run once) | `pytest -q` (repo root) | exit 0, all green | ✓ PASS |
| `make validate` | ruff check/format, pyright, bandit, vulture, shellcheck | all clean | ✓ PASS |
| Smoke-check real behavior assertion | `test_launch_probe_defers_every_browser_choice_to_puppeteer` | asserts actual `puppeteer.launch()`/`newPage()`/`browser.close()` script, not a stubbed version string | ✓ PASS |
| Fail-closed version parsing (M1) | source inspection `installer/versions.py::parse_version` | explicit no-zero-fill-on-unparseable-component docstring + implementation | ✓ PASS |
| pnpm co-install floor (H3) | `installer/versions.py::PNPM_CO_INSTALL_MIN` | `"11.1.0"` (corrected from erroneous `11.0.0`) | ✓ PASS |
| Registry-integrity: co_install must have matching requires edge | `tests/test_registry.py` (line ~586-601) | present, passes | ✓ PASS |
| Split/incomplete group detection uses real captured fixtures | `tests/test_pnpm_globals.py::_SPLIT_STATE_JSON` / `_GROUPED_STATE_JSON` | verbatim JSON from 05-01's Tier-3 container, not synthetic | ✓ PASS |

### Human Verification Required

None. All must-haves resolved programmatically; the one plausibly behavior-dependent item (puppeteer smoke check catching a broken browser) has both a unit test exercising the real launch script and independent Tier-3 container evidence (LIBCHECK=fail case) — see Observable Truths.

### Gaps Summary

None found. All three ROADMAP success criteria are met with real, wired, tested code — not stubs or narrative claims. The cross-AI and manual review cycles (19 findings + 4 findings) left verifiable, substantive fixes in the tree: the M1 fail-closed version-parsing fix, the H3 pnpm-floor correction, the H1 real-browser-launch smoke check, and the M3 security-claim correction were all independently confirmed present in source, not merely asserted in SUMMARY.md. `make validate` and the full test suite are clean at HEAD `954ace6`.

---

_Verified: 2026-09-05_
_Verifier: Claude (gsd-verifier)_
