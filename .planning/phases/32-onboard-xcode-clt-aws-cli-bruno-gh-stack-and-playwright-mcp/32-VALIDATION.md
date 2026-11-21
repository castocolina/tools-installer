---
phase: "32"
slug: "onboard-xcode-clt-aws-cli-bruno-gh-stack-and-playwright-mcp"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-21"
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 32-RESEARCH.md "Validation Architecture". The per-task rows below are keyed to the nine plans of phase 32 (plan, wave and task ids filled in by the planner).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); worker cap, autouse seams and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proofs** | `scripts/container-e2e-verify.sh aws-cli` and `scripts/container-e2e-verify.sh playwright-mcp` (new targets; orchestrator only, disposable container, never on the host) |
| **Estimated runtime** | ~30 seconds per targeted run (to confirm in the first plan) |

Files the quick command draws from: `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_model.py`, `tests/test_executors.py`, `tests/test_engine.py`, `tests/test_plan.py`, `tests/test_status.py`, `tests/test_update.py`, `tests/test_version_status.py`, `tests/test_uninstall.py`, `tests/test_agent_settings.py`, `tests/test_receipts.py`, `tests/test_run.py`, `tests/test_postinstall.py`, `tests/test_app.py` (the `_after_removal` and preview tests), `tests/test_session.py`, `tests/test_container_e2e_aws_cli.py`, `tests/test_container_e2e_playwright_mcp.py`.

Baseline: `tests/test_registry.py tests/test_resolve.py tests/test_model.py tests/test_executors.py` is the research's quick command; confirm it is green on this tree in the first plan.

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green, and both `scripts/container-e2e-verify.sh aws-cli` and `scripts/container-e2e-verify.sh playwright-mcp` PASS (or UNPROVEN with a stated reason where the box lacks a device)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are `32-<plan>-<task>`; the `32-ORCH-*` rows are orchestrator steps. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). Container rows are orchestrator steps after the plan that adds their target and driver. Host tests with a stubbed `ct` prove only the verb dispatch and refusal outside a container, the usage text naming every verdict, the pure verdict functions, the cleanup order and the transcript parser; the vendor's real gpg check, the AppImage launch and the Chromium launch are container lines.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 1 | ONB-14 | T-32-01 | The script `install` argv is validated (an elevation head, a shell head, `xcode-select` as a head, a placeholder, a space or a curl-route key beside it is refused, for `install`, `update` and `remove`; review H2), `engine.install_tool` runs exactly that argv through the runner, and the production console runner closes stdin (a child reading stdin sees EOF; review H1) | unit | `uv run pytest tests/test_model.py tests/test_executors.py tests/test_engine.py tests/test_registry.py tests/test_run.py tests/test_setup.py -n auto -q --no-cov` | ❌ W0 (new tests in existing files) | ⬜ pending |
| 32-01-02 | 01 | 1 | ONB-11, ONB-12 | T-32-02, T-32-03 | `needs_manual` hands off a named method unconditionally (`xcode-select --install`, never run); `prefer` ranks a script before brew and `_RANK` is untouched | unit | `uv run pytest tests/test_model.py tests/test_executors.py tests/test_resolve.py tests/test_ownership.py tests/test_registry.py tests/test_engine.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 32-02-01 | 02 | 2 | ONB-11 | T-32-04 | The missing CLT plans a MANUAL row with the exact command, present reads present, Linux reads unavailable, Update is refused, Uninstall lists no action, no code spawns `xcode-select` (AST + text) | unit | `uv run pytest tests/test_xcode_clt_entry.py tests/test_executors.py tests/test_registry.py tests/test_resolve.py tests/test_update.py tests/test_version_status.py tests/test_uninstall.py tests/test_plan.py -n auto -q --no-cov` | ❌ W0 (new tests/test_xcode_clt_entry.py) | ⬜ pending |
| 32-02-02 | 02 | 2 | ONB-14 | T-32-05, T-32-06 | gh-stack argv strings exact; manifest-only detection (an unrelated `gh-stack` executable on PATH does not read present; review M1); a second install is a no-op; update argv exact; removal deletes only the proven folder | unit | `uv run pytest tests/test_gh_stack_entry.py tests/test_xcode_clt_entry.py tests/test_registry.py tests/test_resolve.py tests/test_update.py tests/test_uninstall.py tests/test_engine.py tests/test_status.py -n auto -q --no-cov` | ❌ W0 (new tests/test_gh_stack_entry.py) | ⬜ pending |
| 32-03-01 | 03 | 3 | ONB-12 | T-32-07, T-32-08 | AWS CLI resolves script before brew on brew hosts, gpg stays on through the env pin, `~/.aws` is in no path, a failing script falls through to brew, and the brew fallback stays reachable on a host without `unzip` (no tool-level `requires`; a public plan-building and execution test; review H3) | unit | `uv run pytest tests/test_aws_cli_entry.py tests/test_registry.py tests/test_resolve.py tests/test_engine.py tests/test_update.py tests/test_executors.py tests/test_ownership.py tests/test_plan.py -n auto -q --no-cov` | ❌ W0 (new tests/test_aws_cli_entry.py) | ⬜ pending |
| 32-03-02 | 03 | 3 | ONB-13 | T-32-09 | Bruno pins equal the recorded digests, selection by os and arch, unavailable for an unsupported arch, no `bru`, no desktop key; `make verify-registry` is the orchestrator's read-only run | unit + network (orchestrator) | `uv run pytest tests/test_bruno_entry.py tests/test_aws_cli_entry.py tests/test_registry.py tests/test_resolve.py tests/test_model.py tests/test_verify_registry.py -n auto -q --no-cov` | ❌ W0 (new tests/test_bruno_entry.py) | ⬜ pending |
| 32-04-01 | 04 | 4 | ONB-15 | T-32-10, T-32-29 | Three-level JSON insert records the levels it created (`created_levels`, optional ledger field) and the revert leaves no residue and never deletes a pre-existing empty parent (review H4); two-level behavior and old ledger lines unchanged | unit | `uv run pytest tests/test_agent_settings.py tests/test_receipts.py -n auto -q --no-cov` | ❌ W0 (new tests in existing file) | ⬜ pending |
| 32-04-02 | 04 | 4 | ONB-15 | T-32-10, T-32-11, T-32-12, T-32-29 | The MCP writer is absent-only and decides inside the write snapshot (an alternate shape injected between read and write is never supplemented; review H5), keeps an existing `playwright` entry byte-identical on all five hosts, states its order and repeat-call semantics once (review M2), skips an OpenCode 1 shape with a named manual step (review W4), reverts only its own writes, reverts the Codex server as one unit (review H6) and refuses a hand-edited ledger | unit | `uv run pytest tests/test_agent_settings.py tests/test_receipts.py tests/test_agent_env.py tests/test_post_install.py tests/test_app.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 32-05-01 | 05 | 5 | ONB-15 | T-32-13 | The hook registers Codex, OpenCode, Cursor and Copilot at install through an absolute executable bunx (review M4) and holds Claude back; the install result carries one warning line with the Reconfigure step and the exact `claude mcp add` command (review H7); an existing entry is kept; an OpenCode 1 shape is named, not written | unit | `uv run pytest tests/test_postinstall.py tests/test_post_install.py tests/test_engine.py tests/test_model.py tests/test_agent_settings.py -n auto -q --no-cov` | ❌ W0 (new tests in existing files) | ⬜ pending |
| 32-05-02 | 05 | 5 | ONB-15 | T-32-13, T-32-15 | The confirmed `hook_register` step writes Claude, a declined or never-run plan writes nothing, `--yes` is the consent (public flow, review H7); the step text discloses both Claude files and the env key (review M3); removal reverts exactly the recorded entries and the removal preview lists exactly those files and keys (review M5) | unit | `uv run pytest tests/test_session.py tests/test_app.py tests/test_version_status.py tests/test_agent_settings.py tests/test_postinstall.py tests/test_engine.py tests/test_plan.py -n auto -q --no-cov` | ❌ W0 (new tests in existing files) | ⬜ pending |
| 32-05-03 | 05 | 5 | ONB-15 | T-32-14, T-32-16 | The `playwright-mcp` entry has one exact pin (0.0.85) shared by the install and the server entry, a kept entry reads settled, Update refuses the exact pin | unit | `uv run pytest tests/test_playwright_mcp_entry.py tests/test_registry.py tests/test_resolve.py tests/test_postinstall.py tests/test_version_status.py tests/test_update.py tests/test_model.py -n auto -q --no-cov` | ❌ W0 (new tests/test_playwright_mcp_entry.py) | ⬜ pending |
| 32-06-01 | 06 | 6 | ONB-12 | T-32-18 | AWS pure verdicts, the shared evidence gate (one PASS line, calendar date, 12 hex digest, transcript rules, each verdict exactly once and in order; review M6) and the driver CLI | host | `uv run pytest tests/test_container_e2e_aws_cli.py tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py -n auto -q --no-cov` | ❌ W0 (new tests/e2e_evidence.py, tests/e2e_aws_cli_driver.py, tests/test_container_e2e_aws_cli.py) | ⬜ pending |
| 32-06-02 | 06 | 6 | ONB-12 | T-32-17, T-32-19 | The `aws-cli` verb with a stubbed `ct`: order, root setup, exact names and removals, no prune, an errexit-safe exit trap that cleans both containers and keeps the status (a real bash process with a negative control; review H8), a success marker that cannot print over a left or unlistable no-gpg box (review H9), usage naming every verdict, the generic skip | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_aws_cli.py tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_bun.py tests/test_container_e2e_landing.py tests/test_shell_scripts_path.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 32-ORCH-aws | after 06 | 6 | ONB-12 | T-32-17, T-32-18 | In disposable containers: Fedora with gpg installs through the script (gpg verify ran), a second run is a no-op, uninstall leaves a seeded `~/.aws` byte-identical; debian-slim without gnupg fails closed with `gpg not found` | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh aws-cli` | ❌ W0 | ⬜ pending |
| 32-07-01 | 07 | 7 | ONB-13 | T-32-21, T-32-22 | Bruno pure verdicts: UNPROVEN carries each mode's evidence, the run modes never use a runtime flag, the removal verdict pins the user's collections, and `recorded_smoke_mode` / `smoke_argv_for` turn only a digest-bound PASS into the entry's smoke data (review H10) | host | `uv run pytest tests/test_container_e2e_bruno.py tests/test_container_e2e_ghostty.py -n auto -q --no-cov` | ❌ W0 (new tests/e2e_bruno_driver.py, tests/test_container_e2e_bruno.py) | ⬜ pending |
| 32-07-02 | 07 | 7 | ONB-13 | T-32-20 | The `bruno` verb with a stubbed `ct`: order, libraries only, FUSE device only when present, exact names and removals, no prune, usage, the generic skip | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_bruno.py tests/test_container_e2e_aws_cli.py tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_shell_scripts_path.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 32-ORCH-bruno | after 07 | 7 | ONB-13 | T-32-21 | In a disposable container: the pinned AppImage installs, runs in at least one mode or reports UNPROVEN with evidence (never a pass), uninstall keeps the seeded collections | e2e (container, orchestrator only; reported, not gated) | `scripts/container-e2e-verify.sh bruno` | ❌ W0 | ⬜ pending |
| 32-08-01 | 08 | 8 | ONB-15 | T-32-24, T-32-25, T-32-26 | Playwright pure verdicts and a hermetic stdio JSON-RPC client (files not pipes, process group killed on timeout); the gate is bound to `playwright-container` | host | `uv run pytest tests/test_container_e2e_playwright_mcp.py tests/test_container_e2e_aws_cli.py tests/test_container_e2e_herdr_app.py -n auto -q --no-cov` | ❌ W0 (new tests/e2e_playwright_mcp_driver.py, tests/test_container_e2e_playwright_mcp.py) | ⬜ pending |
| 32-08-02 | 08 | 8 | ONB-15 | T-32-23 | The `playwright-mcp` verb with a stubbed `ct`: order, root setup, exact names and removals, no prune, usage naming every verdict, the generic skip | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_playwright_mcp.py tests/test_container_e2e_bruno.py tests/test_container_e2e_aws_cli.py tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_shell_scripts_path.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 32-ORCH-playwright | after 08 | 8 | ONB-15 | T-32-24, T-32-25 | In a disposable container: the exact pin installs, hosts are registered without touching a user entry or Claude, the confirmed step registers Claude, the registered server answers initialize, tools/list and a navigate with the distro Chromium, removal reverts exactly its writes (UNPROVEN where the box cannot start Chromium) | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh playwright-mcp` | ❌ W0 | ⬜ pending |
| 32-09-01 | 09 | 9 | ONB-12, ONB-13, ONB-15 | T-32-27 | Both gates (`aws-container`, `playwright-container`) pass before any edit; the registry comments state only recorded verdicts; the Bruno result is reported as recorded and applied to the entry as `smoke_argv` data when it names a working argument list (review H10) | unit + gate | `the two `gate_problem` commands of plan 32-09 Task 1, then uv run pytest tests/test_phase32_consistency.py tests/test_registry.py tests/test_aws_cli_entry.py tests/test_bruno_entry.py tests/test_playwright_mcp_entry.py -n auto -q --no-cov` | ❌ W0 (new tests/test_phase32_consistency.py) | ⬜ pending |
| 32-09-02 | 09 | 9 | ONB-11 to ONB-15 | T-32-28 | The skill row names `install`, `handoff`, `prefer`; the five entries, the single Playwright pin, the skip-list verbs, the dated comments and the consent hosts are guarded | unit | `uv run pytest tests/test_phase32_consistency.py tests/test_tool_onboarding_skill.py tests/test_registry.py tests/test_resolve.py tests/test_postinstall.py -n auto -q --no-cov` | ✅ extends the module of 32-09-01 | ⬜ pending |

Every plan's last task also runs `make validate` once and `make test` once on the final tree (not repeated per row). The `32-ORCH-*` rows are orchestrator steps after the plan that adds their target; the orchestrator also runs `make verify-registry` (read-only, network) after plan 32-03.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_container_e2e_aws_cli.py` + `tests/e2e_aws_cli_driver.py` + `tests/e2e_evidence.py` — container lines for ONB-12 (plan 32-06)
- [ ] `tests/test_container_e2e_playwright_mcp.py` + `tests/e2e_playwright_mcp_driver.py` — launch smoke for ONB-15 (plan 32-08)
- [ ] `tests/test_container_e2e_bruno.py` + `tests/e2e_bruno_driver.py` — the Bruno AppImage container check for ONB-13 (plan 32-07; reported, not gated)
- [ ] New entry test modules `tests/test_xcode_clt_entry.py`, `tests/test_gh_stack_entry.py`, `tests/test_aws_cli_entry.py`, `tests/test_bruno_entry.py`, `tests/test_playwright_mcp_entry.py` and the guard module `tests/test_phase32_consistency.py` (plans 32-02, 32-03, 32-05, 32-09)
- [ ] New test cases in existing files — `tests/test_model.py`, `tests/test_executors.py`, `tests/test_resolve.py`, `tests/test_registry.py`, `tests/test_run.py` (the stdin-closed production runner), `tests/test_update.py`, `tests/test_version_status.py`, `tests/test_agent_settings.py`, `tests/test_receipts.py` (the `created_levels` field), `tests/test_postinstall.py`, `tests/test_engine.py`, the `_after_removal` and preview test file (`tests/test_app.py`), `tests/test_session.py` / `tests/test_plan.py` (ONB-11 to ONB-15)

No framework install needed.

---

## Manual-Only Verifications

No agent marks these passed; they are deferred to the owner.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Xcode CLT missing state: the row shows the exact `xcode-select --install` hand-off command, never runs it; a present CLT reads present; Update is refused; Uninstall lists no action | ONB-11 | Needs a real Mac whose CLT can be absent; the installer never runs `xcode-select` | On a Mac without CLT, open the wizard plan view and read the MANUAL row; install CLT yourself and re-run; confirm present, Update refused, Uninstall empty |
| AWS CLI `install.sh` on macOS installs under `~/.local/share/aws-cli` without admin rights, or falls to brew | ONB-12 | Container proofs are Linux only | On a Mac run the installer for `aws`; check the path and `aws --version`; confirm `~/.aws` untouched |
| Bruno cask install places `~/Applications/Bruno.app`; uninstall keeps `~/Documents/bruno` | ONB-13 | Cask needs a real macOS | Install, check the app path, uninstall, check the documents folder |
| gh-stack data-dir path on macOS | ONB-14 | macOS data directory differs from Linux | Install, check the manifest path the detector reads, uninstall |
| The macOS agent hosts' MCP files carry the `playwright` entry (Claude, Cursor and any other present host) and an existing user entry is kept | ONB-15 | Real macOS agent hosts and their file locations | Install with the hosts present; read each MCP file; confirm the pinned `bunx @playwright/mcp@0.0.85` entry and an untouched pre-existing `playwright` entry |
| Bruno AppImage launches on Bazzite (FUSE mount with libfuse2, menu entry) | ONB-13 | Needs the real Bazzite desktop and FUSE | Install, launch Bruno from the menu and from the AppImage path; confirm the window opens; uninstall and confirm the entry is gone |
| Playwright with the real Flatpak Chrome path on Bazzite (`browser_navigate` reaches a page) | ONB-15 | Needs the Flatpak Chrome and a display | Install, point the host at the Flatpak Chrome wrapper env, call `browser_navigate` to a page, confirm it loads |
| Each agent host's real MCP load of the `playwright` server | ONB-15 | Only the host itself proves it loads the server | In each present agent host, list MCP servers and confirm `playwright` loads and `tools/list` answers |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
