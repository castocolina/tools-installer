---
phase: "31"
slug: "onboard-iterm2-and-the-herdr-desktop-app"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-21"
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 31-RESEARCH.md "Validation Architecture"; the per-task rows below were filled by the planner from plans 31-01 to 31-08 (real plan, wave and task ids).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); autouse seams and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof** | `scripts/container-e2e-verify.sh herdr-app` (orchestrator only, disposable container, never on the host) |
| **Estimated runtime** | ~30 seconds per targeted run (to confirm in the first plan) |

Files the quick command draws from: `tests/test_terminal_ownership.py`, `tests/test_iterm2_profile.py`, `tests/test_iterm2_row.py`, `tests/test_herdr_app_keys.py`, `tests/test_herdr_app_row.py`, `tests/test_terminal_json_catalog.py`, `tests/test_terminal_keys.py`, `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_tool_onboarding_skill.py`, `tests/test_version_status.py`, `tests/test_container_e2e_herdr_app.py`.

Baseline: `tests/test_terminal_keys.py`, `tests/test_tool_onboarding_skill.py` and `tests/test_resolve.py` pass on this tree (31-RESEARCH.md, `--no-cov`).

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green and `scripts/container-e2e-verify.sh herdr-app` PASS
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids are `31-<plan>-<task>`. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). The container run is an orchestrator step after plan 31-07 and before plan 31-08.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | NTERM-02, NTERM-03 | T-31-01, T-31-02, T-31-03 | `WholeFile` apply, drift, deleted-file rule, hook order and strip on a fixture row; a foreign or symlinked file is refused byte for byte; a file changed after the read is refused | unit (tracer) | `uv run pytest tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov` | ❌ W0 new file | ⬜ pending |
| 31-01-02 | 01 | 1 | NTERM-02, NTERM-03 | T-31-03, T-31-06 | `OwnedKeys` seed, insert, kept-yours, deleted key, drift rewrite and owned-only strip on a fixture row; an unparseable file is refused; a created file equal to the seed is deleted | unit | `uv run pytest tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 2 | NTERM-02 | T-31-05 | Profile goldens G1 and G2 (no `Option Key Sends`, `Custom Directory` iff `Writes`), the masked keystroke merge, proof and validate, the state record | unit / golden | `uv run pytest tests/test_iterm2_profile.py tests/test_terminal_keys.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-02-02 | 02 | 2 | NTERM-02 | T-31-04, T-31-10 | Default-profile G3 over four starting states, restore only while ours and by recorded GUID, custom-folder and non-GUID skips, a tampered record never reaches `defaults`, the autouse stub | unit (fake seam) | `uv run pytest tests/test_iterm2_profile.py tests/test_terminal_keys.py tests/test_terminal_ownership.py tests/test_post_install.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-03-01 | 03 | 3 | NTERM-02 | T-31-01, T-31-02 | `iterm2` resolves only on macOS 13 or later and is in `MACOS_ONLY`; the row writes the golden profile, refuses a foreign file, reads drift and a broken default as `≈`; forced pins move by the id | unit | `uv run pytest tests/test_iterm2_row.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_terminal_keys.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-03-02 | 03 | 3 | NTERM-02 | T-31-10 | The previous default is restored before the cask command and again, idempotently, in the strip that deletes the file; install then uninstall leaves the preference and HOME as they were | unit (production functions) | `uv run pytest tests/test_iterm2_row.py tests/test_app.py tests/test_uninstall.py tests/test_terminal_keys.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-04-01 | 04 | 4 | NTERM-03 | T-31-07 | The two vendor defaults match their pinned sha256, the keys path follows the app's folder rules, the owned key per OS, insert then remove restores the vendor bytes | unit | `uv run pytest tests/test_herdr_app_keys.py tests/test_terminal_ownership.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-04-02 | 04 | 4 | NTERM-03 | T-31-05, T-31-12 | The app's chord grammar (cmd/super/win/secondary; option and platform rejected) and the detector keep a user binding in any spelling and tell the vendor's `global` picker from the user's | unit | `uv run pytest tests/test_herdr_app_keys.py tests/test_terminal_ownership.py tests/test_terminal_keys.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-05-01 | 05 | 5 | NTERM-03 | T-31-13 | `herdr-app` is its own entry (script on Linux, cask on Apple Silicon), unavailable on Intel macOS (`NO_MACOS_INTEL`), never colliding with `herdr`; row, skill row and forced pins | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_herdr_app_keys.py tests/test_terminal_keys.py tests/test_registry.py tests/test_resolve.py tests/test_tool_onboarding_skill.py tests/test_post_install.py tests/test_version_status.py tests/test_iterm2_row.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-05-02 | 05 | 5 | NTERM-03 | T-31-03, T-31-06, T-31-12, T-31-13 | Keys goldens G4 and G5 on both CI OSes; a user binding kept with `herdr-app: partial: you already bind ...`; the displaced picker note; drift, deleted key, changed value, bound created path, owned-only strip; the multiplexer's files untouched | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_herdr_app_keys.py tests/test_terminal_ownership.py tests/test_terminal_keys.py tests/test_post_install.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-06-01 | 06 | 6 | NTERM-03 | T-31-13 | Driver verdicts: install, keys against the unit golden, byte isolation of the multiplexer, removal residue with the target-local allowance, digest and record helpers; the shared allowlist never names the nested core install | unit | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-06-02 | 06 | 6 | NTERM-03 | T-31-08, T-31-14 | The driver refuses outside the container, captures output through files, collects every verdict and always cleans up | unit | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_landing.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-07-01 | 07 | 7 | NTERM-03 | T-31-08 | The `herdr-app` target: PID-named box, root stage installs only libxcb and libxkbcommon, one lifecycle step, teardown by exact name even when the step fails, never privileged, no prune or reset | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_landing.py tests/test_container_e2e_receipts.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-07-02 | 07 | 7 | NTERM-03 | T-31-15 | `herdr-app` is excluded from the generic all-pass by a registry-copy filter (the real awk run on the real registry); landing targets and the production registry keep it | host | `uv run pytest tests/test_container_e2e_herdr_app.py tests/test_registry.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-07-ORCH | 07 | 7 | NTERM-03 | T-31-09, T-31-13 | In a disposable container: the app and the multiplexer in both orders leave `~/.local/bin/herdr` and `~/.config/herdr` byte-identical; the seeded `keys.json` matches the golden; removal leaves only allowlisted residue (`herdr-core` and `hc` by the driver's own list) | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh herdr-app` | ❌ W0 | ⬜ pending |
| 31-08-01 | 08 | 8 | NTERM-03 | T-31-11 | Behind the recorded `herdr-app-container: PASS` line only: the registry comment and the skill row state the container evidence, pinned by tests | unit | `uv run pytest tests/test_herdr_app_row.py tests/test_tool_onboarding_skill.py tests/test_registry.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |
| 31-08-02 | 08 | 8 | NTERM-02, NTERM-03 | T-31-16 | Catalog guards: ownership variant per row id, config folder and paths of the two entries, no rejected key spelling, record names; completeness and `same_directory` tests pass with both rows | unit | `uv run pytest tests/test_terminal_json_catalog.py tests/test_terminal_keys.py tests/test_terminal_ownership.py tests/test_iterm2_row.py tests/test_herdr_app_row.py tests/test_tool_onboarding_skill.py tests/test_registry.py tests/test_resolve.py -n auto -q --no-cov` | ❌ W0 | ⬜ pending |

Note: the research's suggested router test ("a `herdr-app:` warning is never routed to the `herdr` row") is replaced by a source assertion in plan 31-05 (`test_the_shell_sync_names_neither_new_terminal`): the shell-sync router reads only shell-sync warnings, which never carry these ids.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] iTerm2 tests (profile goldens, default-profile states, foreign/drift/strip/pending) — `tests/test_iterm2_profile.py` (plan 31-02) and `tests/test_iterm2_row.py` (plan 31-03) (NTERM-02)
- [ ] herdr-app keys tests and chord grammar — `tests/test_herdr_app_keys.py` (plan 31-04) and `tests/test_herdr_app_row.py` (plan 31-05) (NTERM-03); the generic mechanisms in `tests/test_terminal_ownership.py` (plan 31-01)
- [ ] autouse `defaults` seam stub in `tests/conftest.py` (plan 31-02)
- [ ] `tests/e2e_herdr_app_driver.py` and `tests/test_container_e2e_herdr_app.py` (plan 31-06), plus the `herdr-app` target in `scripts/container-e2e-verify.sh` (plan 31-07)
- [ ] fixture plist for `defaults export` (inline string in the test, plan 31-02)

*No framework install needed. Every other task writes its failing test first inside its own commit (`.claude/testing.md`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| iTerm2 loads the Dynamic Profile live and it becomes the default profile | NTERM-02 | Real Mac with iTerm2; no macOS host here (D-19) | Owner's Mac: install through the wizard with iTerm2 running; the profile appears without a restart and a new window uses it |
| Cmd+K sends 0x0c (clears the screen and scrollback) | NTERM-02 | Real Mac keyboard and iTerm2 key handling | Owner's Mac: in a zsh prompt press Cmd+K; the screen clears (for example `cat` then Cmd+K shows the byte as `^L`) |
| Option+Left and Option+Right move by word; the Spanish `@` still types | NTERM-02 | Real Mac keyboard and Spanish layout | Owner's Mac with the Spanish layout: Option+Left and Option+Right move the cursor by word; Option+2 (or the layout's `@` chord) still types `@` |
| Colors in light and dark mode | NTERM-02 | Real Mac appearance switching | Owner's Mac: switch System Settings between Light and Dark; the profile colors stay readable in both |
| `Recycle` behavior for tabs, windows and split panes | NTERM-02 | Real Mac GUI | Owner's Mac: `cd` to a known directory, open a new tab, a new window and a split pane; each shows the same `pwd` |
| Uninstall restores the previous default profile, including the uninstall-from-inside-iTerm2 case | NTERM-02 | Real Mac; `defaults` and the running app | Owner's Mac: note the default profile before install; uninstall from a Terminal.app window and again from inside an iTerm2 window running the installer; the previous default (or "none set") is back and the profile file is gone |
| herdr app installs and launches on Apple Silicon macOS | NTERM-03 | Real Apple Silicon Mac | Owner's Mac: install through the wizard; the app lands, launches, and the owned key bindings work; `~/.config/herdr` is untouched |
| herdr app installs and launches on a Linux desktop session | NTERM-03 | Needs a live Linux desktop session (the container proves files only) | UAT on Bazzite: install through the wizard, launch the app from the menu, check the owned key bindings; uninstall and confirm no residue |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
