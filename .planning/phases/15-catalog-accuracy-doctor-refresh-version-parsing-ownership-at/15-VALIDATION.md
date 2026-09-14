---
phase: "15"
slug: "catalog-accuracy-doctor-refresh-version-parsing-ownership-at"
status: draft
nyquist_compliant: true
wave_0_complete: true
created: "2026-09-14"
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`pyproject.toml:46-49`), `asyncio_mode = "auto"` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.run]`/`[tool.coverage.report]`) |
| **Quick run command** | `uv run pytest tests/test_wizard_app.py tests/test_versions.py tests/test_version_status.py tests/test_ownership.py tests/test_install_ownership.py tests/test_registry.py tests/test_ui_common.py tests/test_update.py -x -q` |
| **Full suite command** | `make test` |
| **Estimated runtime** | ~60-120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_wizard_app.py tests/test_versions.py tests/test_version_status.py tests/test_ownership.py tests/test_install_ownership.py tests/test_registry.py tests/test_ui_common.py tests/test_update.py -x -q`
- **After every plan wave:** Run `make test`
- **Before `/gsd-verify-work`:** Full suite must be green (`make validate && make test`)
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

No REQ-IDs were supplied for this phase (CONTEXT.md/ROADMAP.md describe it narratively). The map below is keyed to CONTEXT.md's D-01 through D-10 instead.

| Decision | Behavior | Test Type | Automated Command | File Exists | Status |
|----------|----------|-----------|-------------------|-------------|--------|
| D-01 | `action_apply` calls `_refresh_guidance()` before `_refresh_body()` on a successful fix | unit (Textual pilot) | `uv run pytest tests/test_wizard_app.py -k doctor_enter_applies -x` | ⚠️ existing test must stay green + a NEW assertion is needed | ⬜ pending |
| D-02 | A frozen-PATH note appears in the rendered body only when `self.applied is True` | unit (Textual pilot) | `uv run pytest tests/test_wizard_app.py -k doctor_screen_adapts -x` (extend) | ❌ → created this phase | ⬜ pending |
| D-03 | `jq-1.8.1` (and any other `<name>-<version>`-shaped token) parses via a new fallback in BOTH `parse_version` and `parse_status_version` | unit | `uv run pytest tests/test_versions.py -k prefix -x` | ❌ → created this phase | ⬜ pending |
| D-04 | The registry audit's findings (jq fixed; procs/bash noted as out-of-scope) are recorded, not silently dropped | doc/code-review | N/A — comment/note recorded per this project's registry-authoring convention | ❌ → created this phase | ⬜ pending |
| D-05 | A tool with an owner_probes-declared dnf/apt/pacman method and a matching live probe resolves `confidence="direct"`, `owner` in `{"dnf","apt","pacman"}` | unit | `uv run pytest tests/test_ownership.py -k native -x` (new) | ❌ → created this phase | ⬜ pending |
| D-05 (update-gate side effect) | A native-owned, `confidence="direct"` tool refuses cleanly (not via `UpdateError`/`"unsupported owner"`) when the update action is attempted | unit | `uv run pytest tests/test_update.py -k native -x` (new) | ❌ → created this phase | ⬜ pending |
| D-06 | `_rpm_ostree` correctly parses the booted deployment's `requested-packages` and matches against the tool's declared dnf package | unit | `uv run pytest tests/test_install_ownership.py -k rpm_ostree -x` | ❌ → created this phase | ⬜ pending |
| D-07 | `ast-grep.tier == "ai"` | unit | `uv run pytest tests/test_registry.py -k ast_grep -x` | ❌ → created this phase | ⬜ pending |
| D-08 | `puppeteer.tier == "ai"` | unit | `uv run pytest tests/test_registry.py -k puppeteer -x` | ⚠️ existing test must be renamed + updated in the SAME commit | ⬜ pending |
| D-09 | `mmdc`/`gitleaks`/`vale`/`drawio-cli` remain `tier == "user"` (no change) | unit | `uv run pytest tests/test_registry.py -x` (full file, no filter) | ✅ negative/no-op verification | ⬜ pending |
| D-10 | `ui_common.py`'s AI-tab comment no longer names `claude`/`codex` as `ai`-tier examples | code-review | `uv run pytest tests/test_ui_common.py -x` (full file — confirms no behavior change) | ✅ comment-only, confirm via `git diff` review | ⬜ pending |
| Registry counts (D-07/D-08 side effect) | `Counter(tier for tool in registry)` reflects the two moves | unit | `uv run pytest tests/test_registry.py -k tier_distribution -x` | ⚠️ existing test MUST be updated to `{"system": 26, "ai": 17, "user": 46}` in the same commit | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All seven gaps below are assigned to a planned task in the wave that first needs them, so no task in this phase
verifies against a test file that nobody creates.

- [x] `tests/test_wizard_app.py`: a test proving `_refresh_guidance()` is actually called by `action_apply` (D-01) — content-diff assertions alone will pass even without the fix, since the frozen `DoctorReport` portion of `self.guidance` cannot visibly change; assert via a spy/counter or by injecting a `guard_state` that DOES change between the two calls.
- [x] `tests/test_wizard_app.py`: a test proving the D-02 frozen-PATH note's presence/absence toggles on `self.applied`.
- [x] `tests/test_versions.py`: new cases for the prefix-split fallback in BOTH `parse_version` and `parse_status_version`/`is_outdated` — not just `extract_observed_version`.
- [x] `tests/test_ownership.py`: `_resolve`'s test helper needs a new `native_probe` kwarg; a new test proving the verified-ownership path (fake probe returning evidence for a dnf-owned fixture tool), added ALONGSIDE (not replacing) the existing no-probe-injected `test_linux_system_package_manager_is_unknown_by_design`.
- [x] `tests/test_install_ownership.py`: new `_rpm_ostree` test cases using the live-captured JSON shape (booted + non-booted deployments, `requested-packages`).
- [x] `tests/test_update.py`: a new case proving a native-manager-owned, `confidence="direct"` tool refuses cleanly on update attempt rather than raising `UpdateError`.
- [x] `tests/test_registry.py`: rename+update `test_puppeteer_is_a_user_tier_node_tool_requiring_pnpm`; add an `ast-grep` tier assertion; update `test_registry_tier_distribution_is_pinned`'s expected `Counter`.

Each gap is assigned to the task that first needs it during planning — see 15-RESEARCH.md's Validation Architecture section for the full mapping to specific plans/tasks.

---

## Manual-Only Verifications

*All phase behaviors have automated verification (see Per-Task Verification Map). No shell-rc mutation or real install/uninstall is exercised by this phase's scope — Doctor refresh, version parsing, ownership attribution, and tier fixes are all read-only/display-layer or attribution-only changes, consistent with ONESHOT-RULES Rule 5.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every MISSING reference resolves to the Wave 0 requirements above.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — each decision runs at least one `uv run pytest` invocation.
- [x] Wave 0 covers all MISSING references — the seven gaps above are each assigned to the task that first needs the fixture.
- [x] No watch-mode flags — every command is a single-shot `uv run pytest`/`make` invocation.
- [x] Feedback latency < 120s — per-task gates run the pinned files (~60-120s); `make validate && make test` gates are end-of-plan/wave only.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** 2026-09-14 — derived from 15-RESEARCH.md's Validation Architecture section. `status` stays `draft` until the phase actually executes; it flips later in the lifecycle, against observed runs rather than against plans.
