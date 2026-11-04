---
phase: "22"
slug: "method-lifecycle-contract"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
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
| 22-03-T1, 22-03-T2, 22-03-T3, 22-06-T1, 22-06-T2, 22-06-T3 | 22-03, 22-06 | 2, 3 | LIFE-01 | T-22-06, T-22-07, T-22-08, T-22-14, T-22-33, T-22-35, T-22-46, T-22-47 | a recipe's `remove` argv runs from its receipt-proven executable before any delete (fake runner, test-local recipe `vend`); a first word naming no proven leaf drops the argv (R2-03); a previewed path that drifted fails its tool and keeps its receipt (R2-02); a foreign file at a declared script path survives; a failing `remove` keeps every path and fails the row; type-only proof survives an in-place vendor update; the tree/leaf receipt shape round-trips (R1-04); a declared path that existed before the install is never adopted (R1-05); an empty legacy script receipt never runs the vendor `remove` (R1-08) | unit + integration | `uv run pytest tests/test_uninstall.py tests/test_receipts.py tests/test_download.py tests/test_app.py tests/test_uninstall_e2e.py -n auto -q --no-cov` | written by 22-03, 22-06 with their code (RED output in each SUMMARY) | ⬜ pending |
| 22-06-T2, 22-06-T3, 22-07-T1 | 22-06, 22-07 | 3, 4 | SPEC R2 (all kinds) | T-22-15, T-22-16, T-22-36, T-22-37 | install writes a receipt, the plan's level is not none, every level reads REMOVABLE in the projection, removal leaves no receipt path (scratch HOME, every receipt kind, both directions); dependents go before their manager (R1-09); the CLI re-proves after the confirm (R1-10) and exits 1 on a failed removal (R1-24); both removers bind `run_captured` (stdin closed, own session, stderr in the error; R2-04) | integration + unit | `uv run pytest tests/test_uninstall_e2e.py tests/test_app.py tests/test_setup.py -n auto -q --no-cov`; `uv run pytest tests/test_version_status.py -k uninstall_group_reads_the_level -q --no-cov -n 0` | written by 22-06, 22-07 with their code | ⬜ pending |
| 22-02-T1, 22-02-T2, 22-02-T3 | 22-02 | 1 | LIFE-02 | T-22-04, T-22-05 | no list literal in `installer/` or `setup.py` starts with `sudo`/`pkexec`/`doas` (AST); a native-only tool yields MANUAL with the exact command and zero runner calls; the run-report command line is sanitized, markup-free and never wrapped (R1-03) | unit/AST | `uv run pytest tests/test_plan.py tests/test_session.py tests/test_engine.py tests/test_executors.py tests/test_render.py -n auto -q --no-cov` | sudo tests rewritten in 22-02 (`tests/test_executors.py:38-53`, `:83-87`, `:96-107`, `tests/test_engine.py`) | ⬜ pending |
| 22-06-T2, 22-07-T1, 22-07-T2 | 22-06, 22-07 | 3, 4 | LIFE-03 | T-22-13, T-22-17 | receipt-proven brew/uv/pnpm package runs the manager uninstall; no receipt = hint and zero runner calls; a native owner = package-naming hint, no argv; the native-command test expectations are rewritten, keeping their package names (R1-12) | unit + pilot | `uv run pytest tests/test_uninstall.py tests/test_app.py tests/test_ownership.py tests/test_version_status.py tests/test_wizard_app.py tests/test_setup.py -n auto -q --no-cov` | written by 22-06, 22-07 with their code | ⬜ pending |
| 22-01-T1, 22-01-T2 | 22-01 | 1 | LIFE-04 | T-22-01, T-22-02, T-22-03, T-22-32 | `config_paths` under `~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex`, `~` itself or outside HOME rejected at load naming key and tool; `~/.config/gh` accepted; denylist single-sourced from `model.HARNESS_MARKER_DIRS`; a cross-tool ancestor/descendant pair refused (R1-16) | unit | `uv run pytest tests/test_model.py tests/test_skill_lifecycle.py tests/test_registry.py -n auto -q --no-cov` | written by 22-01 with its code | ⬜ pending |
| 22-05-T3 | 22-05 | 3 | LIFE-05 | T-22-12 | `u` on a pinned `app` tool runs nothing, takes no lock and shows the refusal; an unpinned app still updates; the moved `pinned_method` keeps the registry verifier green | unit + pilot | `uv run pytest tests/test_update.py tests/test_catalog_tui.py tests/test_session.py tests/test_verify_registry.py -k "pinned or unpinned" -q --no-cov -n 0` | written by 22-05 with its code | ⬜ pending |
| 22-03-T1, 22-05-T1, 22-05-T2, 22-08-T1 | 22-03, 22-05, 22-08 | 2, 3, 4 | LIFE-06 | T-22-11, T-22-45 | `u` on OMZ runs `<omz_root>/tools/upgrade.sh` (`$ZSH` first); `u` on SDKMAN runs the sourced `sdk selfupdate`; the registry declares both; an unresolved root fails naming the tool (R1-07); `u` never adopts a pre-existing declared path (R1-05); a script tool found by its declared paths keeps its script method and runs its declared update through refresh → `resolve_owner` → `UpdateService.run` (R2-01) | unit + integration | `uv run pytest tests/test_update.py tests/test_executors.py tests/test_registry.py tests/test_ownership.py tests/test_version_status.py -n auto -q --no-cov` | written by 22-03, 22-05, 22-08 with their code | ⬜ pending |
| 22-04-T1, 22-04-T2, 22-04-T3 | 22-04 | 2 | LIFE-07 | T-22-09, T-22-10, T-22-34 | unwritable brew prefix fixture = MANUAL with zero executions; writable proceeds; engine re-check catches a prefix that became unwritable after planning; a foreign-owned parent and a probe error fail closed (R1-06) | unit | `uv run pytest tests/test_executors.py tests/test_plan.py tests/test_engine.py tests/test_version_status.py tests/test_registry.py -n auto -q --no-cov` | written by 22-04 with its code | ⬜ pending |
| 22-09-T3, 22-11-T2 | 22-09, 22-11 | 4, 6 | LIFE-08 | T-22-26 | removing one member of a co-install group warns in the CLI preview and the review naming group and others; non-member no warning; removing all members gives one warning | unit + pilot | `uv run pytest tests/test_pnpm_globals.py tests/test_app.py tests/test_wizard_app.py -n auto -q --no-cov` | written by 22-09, 22-11 with their code | ⬜ pending |
| 22-13-T1, 22-13-T2, 22-13-T3 | 22-13 | 7 | LIFE-09 | T-22-30, T-22-31, T-22-44 | harness fails on a planted leftover, fails on a leftover install path inside a harness dir (declared and recorded paths win over every allowed prefix), fails on a recorded path left even when the baseline held it (R1-25), fails on a left removable receipt (R1-24), and passes clean (extracted-function self-test); one Fedora podman run recorded with `TRACER_LEFTOVER_OK` and `TRACER_RECEIPTS_GONE_OK`, container removed | script test + container e2e | `uv run pytest tests/test_container_e2e_receipts.py -n auto -q --no-cov`; `make e2e` | written by 22-13 with its code; recorded run is manual evidence | ⬜ pending |
| 22-12-T1, 22-12-T2, 22-12-T3 | 22-12 | 6 | LIFE-10 | T-22-28, T-22-29, T-22-43 | a greedy-outdated auto-updating cask reads OUTDATED (`↑`) and `u` runs `brew upgrade --cask --greedy-auto-updates`; a non-auto-updates cask never gets the flag; Linux unchanged; the facts survive the cache; the tracked tokens reach the query and `greedy_casks()` follows the published pass (R1-22); a failed greedy read keeps the previous result on an aged snapshot and reads unknown (never current) after a mutation, with the 30-minute retry, and never erases the published greedy set (R1-23, R2-08); each task is green on its own tree, Task 1 holding the readers, the pass, the accessor and the cache encoding (R2-07) | unit | `uv run pytest tests/test_manager_versions.py tests/test_version_cache.py tests/test_version_status.py tests/test_update.py tests/test_setup.py -n auto -q --no-cov` | written by 22-12 with its code | ⬜ pending |
| 22-09-T1, 22-09-T2, 22-10-T1, 22-10-T2, 22-10-T3, 22-11-T1, 22-11-T3 | 22-09, 22-10, 22-11 | 4, 5, 6 | UI-04 | T-22-21, T-22-22, T-22-23, T-22-24, T-22-27, T-22-40, T-22-41, T-22-42 | "delete config too" absent without `config_paths`; off = config survives; on = exactly the listed paths gone; CLI `--yes` keeps config; failed removal keeps config; a shared path kept while any catalog declarer stays or is unflagged (R1-15); a symlinked parent into a harness dir or out of HOME refused (R1-17); a config dir a harness marker resolves to, or into, refused while a final symlink is only unlinked (R2-06); a tool `remove_tool` refused keeps its config (R2-02); flags start off on every visit (R1-19); the decision is built once before the modal (R1-20); a config warning reads `warn` (R1-21) | pilot + unit + CLI | `uv run pytest tests/test_wizard_app.py tests/test_app.py tests/test_uninstall.py tests/test_uninstall_e2e.py tests/test_tool_browser.py tests/test_layout_80x20.py -n auto -q --no-cov` | written by 22-09, 22-10, 22-11 with their code | ⬜ pending |
| 22-06-T2, 22-07-T3, 22-09-T2 | 22-06, 22-07, 22-09 | 3, 4 | Edge: crash backstop | T-22-14, T-22-38 | an interrupt between `remove` and path deletion leaves the receipt (plan not removable, broken drift when a leaf is gone); the next refresh pass publishes BROKEN when anything recorded is left and retires the receipt when nothing is, level `none` either way (R1-11); an interrupt before config deletion leaves config | unit + pass | `uv run pytest tests/test_app.py -k "interrupt_after_the_vendor or interrupt_before_step_4" -q --no-cov -n 0`; `uv run pytest tests/test_version_status.py -k interrupted_recipe_removal -q --no-cov -n 0` | written by 22-06, 22-07, 22-09 with their code | ⬜ pending |
| 22-08-T1, 22-08-T3 | 22-08 | 4 | LIFE-01 data | T-22-39, T-22-48 | pnpm, bun, Volta and fnm declare only their executables, never a store root; removing the manager keeps an unrelated global package or toolchain (R1-13); `opencode` declares its binary path and update but no `remove`, because its vendor uninstall edits shell rc lines and deletes unrecorded dirs (R2-05, pending sign-off) | unit | `uv run pytest tests/test_registry.py -k "script_lifecycle_data or store_as_a_tree or keeps_its_global_packages" -q --no-cov -n 0` | written by 22-08 with its data | ⬜ pending |
| 22-01-T3, 22-02-T2, 22-07-T2 | 22-01, 22-02, 22-07 | 1, 4 | Deletions | — | the four dead `POST_INSTALL_ACTIONS` names and `Tool.source/owner/uninstall` are gone; no native executor and no `EXECUTORS` entry for dnf/apt/pacman/rpm_ostree; native `_REMOVAL_COMMANDS` values are None | unit/grep | `uv run pytest tests/test_model.py tests/test_registry.py tests/test_executors.py tests/test_ownership.py -n auto -q --no-cov` | written by 22-01, 22-02, 22-07 with their code | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Script-kind receipt fixtures (type-only dir/link/file, vendor-update drift case, the pinned serialized shape, a declared path present before the install) in `tests/test_receipts.py` — 22-03 Tasks 1-2
- [ ] `tests/test_uninstall.py` / `tests/test_app.py` crash-backstop and ordering fixtures (fake runner recording `remove` before deletes) — 22-06 Tasks 1-2
- [ ] A fake brew JSON fixture with `auto_updates` casks (macOS-shaped) — 22-12 Task 1
- [ ] Parametrized `Disposition` exhaustiveness test (MANUAL added) — 22-02 Task 1
- [ ] E2E harness self-test seam (a pure `new_leftovers` function and `assert_removed_receipts_gone`, so the planted-leftover and left-receipt tests run without podman) — 22-13 Task 1
- [ ] Rewrite `tests/test_engine.py` sudo cases as MANUAL assertions — 22-02 Task 2

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One real Fedora container lifecycle with before/after file listings | LIFE-09 | needs podman and network; recorded as evidence, not a unit test | `make e2e`; record listings diff and container removal |
| Copying the exact handoff command from the run log | LIFE-02 / UI-SPEC | terminal text selection in Textual 8.2.7 is not testable headless | run a native-only tool in a container TUI, select the command line, paste |
| NO_COLOR 80x20 render of the new Uninstall `c` toggle, confirm review and handoff rows | UI-04 / LIFE-02 | real-terminal layout | tmux 80x20 NO_COLOR in a container, navigation plus one removal with config |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (39/39 tasks across 22-01..22-13)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (no plan uses the MISSING sentinel; each Wave 0 item is written by the task named above and committed together with its code, its RED output recorded in the SUMMARY; review R1-01)
- [x] No watch-mode flags
- [x] Feedback latency < 120s (per-task commands are targeted pytest runs; `make e2e` is the recorded manual-evidence run, not a per-task sample)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
