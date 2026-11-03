---
phase: "22"
slug: "method-lifecycle-contract"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-03"
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from
> `22-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-xdist + coverage; Textual pilot for screens |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (incl. `faulthandler_timeout = 120`); `tests/conftest.py` (sandboxed HOME, receipts dir) |
| **Quick run command** | `uv run pytest tests/test_<module>.py -x` |
| **Full suite command** | `make validate && make test` |
| **E2E** | `make e2e` (`scripts/container-e2e-verify.sh all`, disposable Fedora container) |
| **Estimated runtime** | ~100 s full suite locally (10 workers); ~9 min on the macOS CI runner |

---

## Sampling Rate

- **After every task commit:** the targeted module(s) below with `-x`
- **After every plan wave:** `make validate && make test`
- **Before `/gsd-verify-work`:** full suite green, plus one recorded `make e2e` Fedora run
- **Max feedback latency:** 120 seconds (faulthandler dumps stacks on a stalled test)

---

## Per-Task Verification Map

Task IDs are filled in by the planner; each row names the requirement, the behavior to prove, and the command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | LIFE-01 | T-22-TBD | opencode removal runs its `remove` argv (fake runner); a foreign file at a declared script path survives; a failing `remove` keeps every path and fails the row; type-only proof survives an in-place vendor update | unit | `uv run pytest tests/test_uninstall.py tests/test_receipts.py -x` | extend; script fixtures ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SPEC R2 (all kinds) | — | install writes a receipt, Uninstall shows removable, removal leaves no receipt path (scratch HOME, every kind) | integration | `uv run pytest tests/test_uninstall_e2e.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-02 | T-22-TBD | no list literal in `installer/` starts with `sudo`/`pkexec`/`doas`; a native-only tool yields MANUAL with the exact command and zero runner calls | unit/grep | `uv run pytest tests/test_plan.py tests/test_executors.py tests/test_engine.py -x` | rewrite sudo tests | ⬜ pending |
| TBD | TBD | TBD | LIFE-03 | T-22-TBD | receipt-proven brew/uv/pnpm package runs the manager uninstall; no receipt = hint and zero runner calls; a native owner = package-naming hint, no argv | unit | `uv run pytest tests/test_uninstall.py tests/test_ownership.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-04 | T-22-TBD | `config_paths` under `~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex`, `~` itself or outside HOME rejected at load naming key and tool; `~/.config/gh` accepted; denylist single-sourced from `model.py` | unit | `uv run pytest tests/test_registry.py tests/test_model.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-05 | — | `u` on a pinned `app` tool with no version source runs nothing and shows the refusal; an unpinned app still updates | unit + pilot | `uv run pytest tests/test_update.py tests/test_catalog_tui.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-06 | T-22-TBD | `u` on OMZ runs `<omz_root>/tools/upgrade.sh` (`$ZSH` honored); `u` on SDKMAN runs the `_sdkman` sourced `sdk selfupdate`; child gets stdin closed | unit | `uv run pytest tests/test_update.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-07 | — | unwritable brew prefix fixture = MANUAL with zero executions; writable proceeds; engine re-check catches a prefix that became unwritable after planning | unit | `uv run pytest tests/test_session.py tests/test_engine.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-08 | — | removing one member of a co-install group warns in the review naming group and others; non-member no warning; removing all members gives one warning | unit + pilot | `uv run pytest tests/test_uninstall.py tests/test_wizard_app.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | LIFE-09 | — | harness fails on a planted leftover and passes clean (stubbed listing self-test); one Fedora podman run recorded, container removed | script test + container e2e | `uv run pytest tests/test_container_e2e_receipts.py -x`; `make e2e` | extend; recorded run is manual evidence | ⬜ pending |
| TBD | TBD | TBD | LIFE-10 | — | a greedy-outdated auto-updating cask reads OUTDATED (`↑`) and `u` runs the greedy upgrade argv; a non-auto-updates cask never gets the flag; Linux unchanged | unit | `uv run pytest tests/test_manager_versions.py tests/test_version_status.py tests/test_update.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | UI-04 | T-22-TBD | "delete config too" absent without `config_paths`; off = config survives; on = exactly the listed paths gone; CLI `--yes` keeps config; failed removal keeps config; shared path kept while another tool uses it | pilot + unit + CLI | `uv run pytest tests/test_wizard_app.py tests/test_app.py tests/test_uninstall.py -x` | extend | ⬜ pending |
| TBD | TBD | TBD | Edge: crash backstop | T-22-TBD | an interrupt between `remove` and path deletion leaves the receipt (tool reads broken, not removable); an interrupt between removal and config deletion leaves config | unit | `uv run pytest tests/test_uninstall.py -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | Deletions (D-16 style) | — | fork guard over the removed names (`_dnf` sudo argv, native `_REMOVAL_COMMANDS` entries, dead `POST_INSTALL_ACTIONS`, `Tool.source/owner/uninstall`) | grep | `uv run pytest tests/test_screen_family.py::test_the_replaced_forks_are_gone -x` | extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Script-kind receipt fixtures (type-only dir/link/file, vendor-update drift case) in `tests/test_receipts.py`
- [ ] `tests/test_uninstall.py` crash-backstop and ordering fixtures (fake runner recording `remove` before deletes)
- [ ] A fake brew JSON fixture with `auto_updates` casks (macOS-shaped)
- [ ] Parametrized `Disposition` exhaustiveness test (MANUAL added)
- [ ] E2E harness self-test seam (a stubbed listing function so the planted-leftover test runs without podman)
- [ ] Rewrite `tests/test_engine.py` sudo cases as MANUAL assertions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One real Fedora container lifecycle with before/after file listings | LIFE-09 | needs podman and network; recorded as evidence, not a unit test | `make e2e`; record listings diff and container removal |
| Copying the exact handoff command from the run log | LIFE-02 / UI-SPEC | terminal text selection in Textual 8.2.7 is not testable headless | run a native-only tool in a container TUI, select the command line, paste |
| NO_COLOR 80x20 render of the new Uninstall `c` toggle, confirm review and handoff rows | UI-04 / LIFE-02 | real-terminal layout | tmux 80x20 NO_COLOR in a container, navigation plus one removal with config |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
