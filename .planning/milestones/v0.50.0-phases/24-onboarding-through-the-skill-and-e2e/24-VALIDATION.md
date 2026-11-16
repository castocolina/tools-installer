---
phase: "24"
slug: "onboarding-through-the-skill-and-e2e"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-08"
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `24-RESEARCH.md` § Validation Architecture (requirement-level map, Wave 0 gaps). The planner fills
> the per-task rows.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8 + pytest-xdist + pytest-cov (`fail_under = 90`), Textual pilots, all under the 23.1 sandbox (`tests/sandbox.py`: `cargo`, `git`, `curl`, `podman`, `docker`, `systemctl` are forbidden programs — unit tests use fake runners and fake executables under `tmp_path`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]`, `tests/conftest.py`, `tests/child_guard/` |
| **Quick run command** | `uv run pytest -n 0 --no-cov -q <touched test files>` |
| **Full suite command** | `make validate && make test` |
| **Estimated runtime** | quick < 60 s per file set; full suite ~2 min locally |

---

## Sampling Rate

- **After every task commit:** the touched test files with `-n 0 --no-cov`
- **After every plan wave:** `make validate && make test`, then push and watch CI on both OSes
- **Before `/gsd-verify-work`:** full suite green, then the orchestrator's three-distro container runs (`scripts/container-e2e-verify.sh all --distro fedora|debian|arch`, never on the host, run sequentially because the host network is slow and TLS-flaky), then the human UAT (`24-UAT.md`)
- **Max feedback latency:** 60 seconds per task command

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 24-01-T1 | 01 | 1 | ONB-02, ONB-06 | T-24-02, T-24-08 | artifacts only under allowed roots; removal by receipt + formula; narrowed pruning | unit (fake runner, tracer) | `uv run pytest tests/test_cargo_distrobox.py -k "shipped_entry" -q --no-cov -n 0` | Wave 0 (new) | ⬜ pending |
| 24-01-T2 | 01 | 1 | ONB-02 | T-24-01, T-24-04, T-24-05, T-24-07, T-24-36 | tag validated; box, pulled image, temp dir removed on every outcome; failure is FAILED with no receipt; tri-state image ownership; binary-only evidence; no sudo | unit | `uv run pytest tests/test_cargo_distrobox.py tests/test_engine.py tests/test_model.py tests/test_registry.py tests/test_uninstall.py tests/test_ownership.py -k "cargo or alacritty or image or binary_is_ownership" -q --no-cov -n 0` | Wave 0 (new) | ⬜ pending |
| 24-01-T3 | 01 | 1 | ONB-02, ONB-04 | T-24-07 | native fallback stays a MANUAL handoff; floor is a non-failure disposition that never drops ownership; node probed only when found | unit | `uv run pytest tests/test_resolve.py tests/test_platform.py tests/test_version_status.py tests/test_ownership.py -k "precedence or distrobox or podman or node_floor or rereads or outdated or deduplicates or os_only or constant_probe or mixed_lists" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-02-T1 | 02 | 1 | ONB-01 | T-24-09 | guarded nested TOML splice, never a second header | unit (tracer) | `uv run pytest tests/test_agent_settings.py tests/test_agent_env.py -k "herdr" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-02-T2 | 02 | 1 | ONB-07 | T-24-10, T-24-11 | absent-only; revert only an unchanged value, through revert_group and revert_agent | unit | `uv run pytest tests/test_agent_settings.py -k "default_shell or dynamic or revert_group" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-02-T3 | 02 | 1 | ONB-01, ONB-07 | T-24-09, T-24-12 | compare-before-commit; sandbox clears HERDR_CONFIG_PATH | unit | `uv run pytest tests/test_agent_settings.py tests/test_sandbox.py -k "toml or herdr" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-03-T1 | 03 | 1 | ONB-03 | T-24-13, T-24-14 | TUNE-04 rule pinned verbatim | doc test + recorded judge | `uv run pytest tests/test_docs.py -k "tool_onboarding" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-03-T2 | 03 | 1 | ONB-03 | — | docs match the shipped design | doc test | `uv run pytest tests/test_docs.py -q --no-cov -n 0` | exists | ⬜ pending |
| 24-04-T1 | 04 | 1 | ONB-04 | T-24-15, T-24-17, T-24-37 | installs only via `ct exec`; per-distro names; bash tester; e2e script only a shellcheck argument in the gates | bash extraction | `uv run pytest tests/test_container_e2e_receipts.py tests/test_makefile.py -k "distro or tester or shellcheck_argument" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-04-T2 | 04 | 1 | ONB-04, ONB-01 | T-24-18 | rerun gate; value-level herdr checks; residue only in installer-created files | bash extraction | `uv run pytest tests/test_container_e2e_receipts.py -k "rerun or blocked or misconfigured or herdr or residue or manual_set" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-04-T3 | 04 | 1 | ONB-02, ONB-06, ONB-07 | T-24-16 | outer container without a privileged flag, removed by trap; tester argv unchanged by default | bash extraction | `uv run pytest tests/test_container_e2e_receipts.py -k "nested or default_tester" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-05-T1 | 05 | 2 | ONB-02 | T-24-19, T-24-20 | config dir untouched on update; five artifacts re-recorded | unit (tracer) | `uv run pytest tests/test_update.py -k "alacritty" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-05-T2 | 05 | 2 | ONB-02 | T-24-21 | failed/interrupted rebuild keeps the old install; failure is a failed update | unit | `uv run pytest tests/test_update.py tests/test_cargo_distrobox.py -k "rebuild or current_alacritty" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-06-T1 | 06 | 2 | ONB-07 | T-24-22 | owned regions only; stripped with the tool | unit (tracer) | `uv run pytest tests/test_terminal_shell.py tests/test_registry.py tests/test_model.py -k "alacritty or post_install_action_names" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-06-T2 | 06 | 2 | ONB-07 | T-24-22, T-24-24 | per-part guard; whole-document re-parse; compare-before-commit | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_post_install.py -k "alacritty or partial" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-06-T3 | 06 | 2 | ONB-07, ONB-01 | T-24-23, T-24-25, T-24-26 | user default_shell kept; no Policies row; the `u` follow-up repairs only a drifted owned region | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_setup.py tests/test_app.py -k "herdr or update_route" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-07-T1 | 07 | 3 | ONB-01 | T-24-28, T-24-30, T-24-32 | pinned plugin SHA; digest-verified binary; standalone target never a host | unit (tracer) | `uv run pytest tests/test_postinstall.py tests/test_registry.py tests/test_download.py tests/test_app.py tests/test_render.py -k "herdr or standalone or host_labels or sidebar_only or postinstall_hook or distribution or drawio or config_agent" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-07-T2 | 07 | 3 | ONB-01 | T-24-27, T-24-30 | user-owned integrations never recorded or removed; status read whatever the exit code | unit | `uv run pytest tests/test_postinstall.py tests/test_version_status.py tests/test_session.py -k "herdr or settled or copilot or pi" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-07-T3 | 07 | 3 | ONB-01 | T-24-27, T-24-31 | hooks unregister before agent reverts on both routes; deleted config drops its ledger | unit | `uv run pytest tests/test_postinstall.py tests/test_app.py tests/test_uninstall.py -k "sidebar or plugin or rows or reload or hook_tools_before or unregisters_hooks or herdr_config or dependents_first" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-09-T1 | 09 | 4 | ONB-04 | T-24-38, T-24-39 | a script runs only after a complete download; a failed download is FAILED | unit (real shell, fakes) | `uv run pytest tests/test_engine.py tests/test_executors.py -k "script" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-09-T2 | 09 | 4 | ONB-04 | T-24-40, T-24-41 | receipt-proven release decides outdated; digests kept | unit | `uv run pytest tests/test_receipts.py tests/test_engine.py tests/test_update.py tests/test_version_status.py -k "release or sd_reads or changed_binary or older_recorded" -q --no-cov -n 0` | exists | ⬜ pending |
| 24-08-T1 | 08 | 5 | ONB-05 | T-24-35 | evidence recorded | full suite | `make validate && make test` | exists | ⬜ pending |
| 24-08-T2 | 08 | 5 | ONB-02, ONB-06, ONB-07 | T-24-33 | orchestrator-only nested container, removed afterwards | container (orchestrator) | `scripts/container-e2e-verify.sh nested` (never on the host by an executor) | exists after 24-04 | ⬜ pending |
| 24-08-T3 | 08 | 5 | ONB-04, ONB-01, ONB-05 | T-24-33, T-24-34, T-24-42 | sequential disposable containers; forward fixes; stop rule; UAT by the user | container (orchestrator) + manual | `scripts/container-e2e-verify.sh all --distro fedora|debian|arch` | exists after 24-04 | ⬜ pending |

Requirement-level map: see `24-RESEARCH.md` § Phase Requirements to Test Map (ONB-01 herdr entry, targets,
sidebar plugin, container probes; ONB-02 `cargo_distrobox` argv/cleanup/precedence/load validation/receipt/
update; ONB-03 skill text pins + recorded judge report; ONB-04 `--distro` table and rerun assertion; ONB-05
manual UAT; ONB-06 desktop entry + terminfo under `~/.terminfo`; ONB-07 Alacritty and herdr install tuning).

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cargo_distrobox.py` — ONB-02 argv, cleanup (`finally` rm + conditional rmi), failure injection, update
- [ ] `tests/test_desktop_entry.py` — ONB-06 render golden text, quoting, control-char rejection
- [ ] fixtures: fake release feed with a newer tag, fake `herdr` / `distrobox` / `podman` executables under `tmp_path`, scratch-HOME Alacritty and herdr config trees
- [ ] `tests/test_container_e2e_receipts.py` extensions for `--distro` and the rerun assertion
- [ ] `24-UAT.md` skeleton (human UAT, ONB-05)
- [ ] `24-SKILL-JUDGE.md` (baseline and final skill-judge verdicts)
- [ ] fake `curl`, `mktemp`, `rm` and shell executables under `tmp_path` for 24-09's real-shell script-download test (curl is a forbidden program in the 23.1 sandbox)

*Revised 2026-11-13 from cross-AI review cycle 2 (24-REVIEWS.md at 68b040f): 24-01-T3, 24-06-T1, 24-06-T3 and 24-07-T3 commands select the pinned and new tests those tasks now name; 24-07-T3 relies on 23.2's hooks-first `removal_order` (eb893c0).*

*Revised 2026-11-12 from cross-AI review cycle 1 (24-REVIEWS.md at c043bd1): new plan 24-09 (wave 4) owns the rerun gate's product root causes; 24-08 moved to wave 5; task commands updated for the pinned tests each task now names.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Owner on every tier after install, `○` after Uninstall, herdr line | ONB-05 | Real host, the user's machine (agents must never mutate it) | `24-UAT.md`, run by the user |
| Real Alacritty distrobox build on immutable Bazzite (if the nested-podman spike fails) | ONB-02, ONB-06 | Needs the real host's podman/distrobox | `24-UAT.md`, run by the user |
| Alt+arrow word navigation and clear scrollback in a real Alacritty | ONB-07 | Real terminal key handling | `24-UAT.md`, run by the user |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
