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
| (filled by planner) | | | ONB-01..07 | | | | | | ⬜ pending |

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
