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
> Seeded from 32-RESEARCH.md "Validation Architecture". The per-task rows below are placeholders keyed to the requirements; the planner replaces `32-TBD-NN` with the real plan, wave and task ids.

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

Files the quick command draws from: `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_model.py`, `tests/test_executors.py`, `tests/test_engine.py`, `tests/test_plan.py`, `tests/test_status.py`, `tests/test_update.py`, `tests/test_version_status.py`, `tests/test_uninstall.py`, `tests/test_agent_settings.py`, `tests/test_postinstall.py`, `tests/test_app.py` (the `_after_removal` tests), `tests/test_session.py`, `tests/test_container_e2e_aws_cli.py`, `tests/test_container_e2e_playwright_mcp.py`.

Baseline: `tests/test_registry.py tests/test_resolve.py tests/test_model.py tests/test_executors.py` is the research's quick command; confirm it is green on this tree in the first plan.

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green, and both `scripts/container-e2e-verify.sh aws-cli` and `scripts/container-e2e-verify.sh playwright-mcp` PASS (or UNPROVEN with a stated reason where the box lacks a device)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are `32-<plan>-<task>`; the `32-TBD-NN` rows are placeholders the planner replaces. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). Container rows are orchestrator steps after the plan that adds their target and driver. Host tests with a stubbed `ct` prove only the verb dispatch and refusal outside a container, the usage text naming every verdict, the pure verdict functions, the cleanup order and the transcript parser; the vendor's real gpg check, the AppImage launch and the Chromium launch are container lines.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-TBD-01 | TBD | TBD | ONB-11 | T-32-TBD | Handoff name validated; an unknown name is refused; exactly one of url, install and handoff is set | unit | `uv run pytest tests/test_model.py -k handoff --no-cov -q` | ❌ W0 (new tests in existing file) | ⬜ pending |
| 32-TBD-02 | TBD | TBD | ONB-11 | T-32-TBD | `needs_manual` returns `xcode-select --install` unconditionally, also with `writable=lambda _: True` | unit | `uv run pytest tests/test_executors.py -k handoff --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-03 | TBD | TBD | ONB-11 | T-32-TBD | A missing CLT gives a MANUAL plan row with the exact command; a present CLT (`detect_path` in tmp) reads present | unit | `uv run pytest tests/test_plan.py tests/test_status.py -k xcode --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-04 | TBD | TBD | ONB-11 | T-32-TBD | No runner argv starts with `xcode-select` or `softwareupdate`; the string appears only in the table (grep/AST) | unit | `uv run pytest tests/test_executors.py -k "elevation or xcode" --no-cov -q` | ⚠️ partial (elevation tests exist) | ⬜ pending |
| 32-TBD-05 | TBD | TBD | ONB-11 | T-32-TBD | Update is refused; the Uninstall group is MANAGED with an empty argv | unit | `uv run pytest tests/test_update.py tests/test_version_status.py -k xcode --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-06 | TBD | TBD | ONB-12 | T-32-TBD | The method preference sorts the script before brew on brew hosts; the validator refuses misuse | unit | `uv run pytest tests/test_resolve.py tests/test_model.py -k prefer --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-07 | TBD | TBD | ONB-12 | T-32-TBD | Entry shape: no `--system`, env pin false (gpg stays on), paths exclude `~/.aws`, no `config_paths` | unit | `uv run pytest tests/test_registry.py -k aws --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-08 | TBD | TBD | ONB-12 | T-32-TBD | A failing script method falls through to brew (fake runner) | unit | `uv run pytest tests/test_engine.py -k aws --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-09 | TBD | TBD | ONB-12 | T-32-TBD | Host side of the `aws-cli` target with a stubbed `ct`: verb dispatch, refusal outside a container, usage names every verdict, the pure verdicts (install, idempotence, byte-identical seed, gpg-missing message), cleanup order, transcript parser | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_aws_cli.py --no-cov -q` | ❌ W0 (new file + `tests/e2e_aws_cli_driver.py`) | ⬜ pending |
| 32-TBD-ORCH-1 | TBD | TBD | ONB-12 | T-32-TBD | In a disposable container: Fedora with gpg installs, `aws --version` works, a second run is a no-op, uninstall leaves a seeded `~/.aws/config` byte-identical; debian-slim without gnupg fails closed with the gpg message | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh aws-cli` | ❌ W0 | ⬜ pending |
| 32-TBD-10 | TBD | TBD | ONB-13 | T-32-TBD | Entry loads; pins equal the live digests (read-only `verify-registry`); no `bru`; the cask uses `Bruno.app` | unit + network | `uv run pytest tests/test_registry.py -k bruno --no-cov -q`; `make verify-registry` | ❌ W0 | ⬜ pending |
| 32-TBD-11 | TBD | TBD | ONB-13 | T-32-TBD | `smoke_argv` runs the Electron app headless in the container (a step in a new or existing driver; UNPROVEN with reason is a legitimate verdict) | container / manual | a step of `scripts/container-e2e-verify.sh aws-cli` or a driver the plan adds (planner picks) | ❌ W0 | ⬜ pending |
| 32-TBD-12 | TBD | TBD | ONB-14 | T-32-TBD | The `install` argv is validated (an elevation head is refused); `_script` runs it with no shell | unit | `uv run pytest tests/test_model.py tests/test_executors.py -k install_argv --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-13 | TBD | TBD | ONB-14 | T-32-TBD | Detect via the manifest file; removal deletes only the proven tree; the update argv is exact | unit | `uv run pytest tests/test_registry.py tests/test_uninstall.py -k gh_stack --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-14 | TBD | TBD | ONB-15 | T-32-TBD | Writer: absent gives wrote; an existing `playwright` gives set_by_you and the file byte-identical; only present hosts; env only when the wrapper exists; codex `[mcp_servers.foo]` case; opencode v2 shape | unit | `uv run pytest tests/test_agent_settings.py tests/test_postinstall.py -k playwright --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-15 | TBD | TBD | ONB-15 | T-32-TBD | Removal reverts our entries through the ledger; a user entry is kept | unit | `uv run pytest tests/test_app.py -k playwright --no-cov -q` (or the file that covers `_after_removal`) | ❌ W0 | ⬜ pending |
| 32-TBD-16 | TBD | TBD | ONB-15 | T-32-TBD | Consent: with no step, `~/.claude/settings.json` is unchanged; a confirmed step writes the env key | unit | `uv run pytest tests/test_session.py -k claude_env --no-cov -q` | ❌ W0 | ⬜ pending |
| 32-TBD-17 | TBD | TBD | ONB-15 | T-32-TBD | Host side of the `playwright-mcp` target with a stubbed `ct`: verb dispatch, refusal outside a container, usage names every verdict, the pure launch-probe verdict, cleanup order, transcript parser | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_playwright_mcp.py --no-cov -q` | ❌ W0 (new file + `tests/e2e_playwright_mcp_driver.py`) | ⬜ pending |
| 32-TBD-ORCH-2 | TBD | TBD | ONB-15 | T-32-TBD | In a disposable container: `bunx @playwright/mcp@0.0.85` with the distro Chromium via `--executable-path` answers JSON-RPC `initialize` and `tools/list` and navigates to a `data:` URL (UNPROVEN with reason where the box lacks a device) | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh playwright-mcp` | ❌ W0 | ⬜ pending |
| 32-TBD-18 | TBD | TBD | ONB-11 to ONB-15 | T-32-TBD | Registry counts, sets, first-method tables and lifecycle stanzas include the five new entries | unit | `uv run pytest tests/test_registry.py tests/test_resolve.py --no-cov -q` | ✅ exists (edit pins) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_container_e2e_aws_cli.py` + `tests/e2e_aws_cli_driver.py` — container lines for ONB-12
- [ ] `tests/test_container_e2e_playwright_mcp.py` + `tests/e2e_playwright_mcp_driver.py` — launch smoke for ONB-15
- [ ] New test cases in existing files — `tests/test_model.py`, `tests/test_executors.py`, `tests/test_resolve.py`, `tests/test_registry.py`, `tests/test_update.py`, `tests/test_version_status.py`, `tests/test_agent_settings.py`, `tests/test_postinstall.py`, the `_after_removal` test file (`tests/test_app.py`), `tests/test_session.py` / `tests/test_plan.py` (ONB-11 to ONB-15)

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
