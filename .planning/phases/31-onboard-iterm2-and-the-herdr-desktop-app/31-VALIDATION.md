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
> Seeded from 31-RESEARCH.md "Validation Architecture". The per-task rows below are placeholders keyed to the requirement and the test file; the planner replaces the `31-XX-YY` ids with the real plan, wave and task ids.

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

Files the quick command draws from: `tests/test_terminal_keys.py`, `tests/test_registry.py`, `tests/test_resolve.py`, `tests/test_tool_onboarding_skill.py`, `tests/test_version_status.py`, `tests/test_container_e2e_herdr_app.py`; the planner may split the new iTerm2 and herdr-app cases into `tests/test_iterm2_profile.py` and `tests/test_herdr_app_keys.py`.

Baseline: `tests/test_terminal_keys.py`, `tests/test_tool_onboarding_skill.py` and `tests/test_resolve.py` pass on this tree (31-RESEARCH.md, `--no-cov`).

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green and `scripts/container-e2e-verify.sh herdr-app` PASS
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Placeholder rows: one per automated behavior of the research map. Task ids are `31-<plan>-<task>`; the planner assigns the real ids, plan, wave and threat refs. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). The container run is an orchestrator step.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 31-XX-01 | TBD | TBD | NTERM-02 | — | `iterm2` resolves only on macOS (13 or later), is unavailable on Linux, and is in `MACOS_ONLY` | unit | `uv run pytest tests/test_registry.py tests/test_resolve.py -k "iterm2 or macos_only or first_method" --no-cov -q` | ✅ files, ❌ W0 new cases | ⬜ pending |
| 31-XX-02 | TBD | TBD | NTERM-02 | T-31-XX (V5 input validation) | Profile golden bytes G1/G2; the key map holds exactly Cmd+K, the two Option rows and the merged parent rows; no `Option Key Sends` key; `Custom Directory` present iff `Writes` | unit / golden | `uv run pytest tests/test_terminal_keys.py -k iterm2 --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-03 | TBD | TBD | NTERM-02 | T-31-XX (command injection via `defaults`) | Default-profile G3: install sets it, uninstall restores the exact previous value including "none set"; a user change is kept; `LoadPrefsFromCustomFolder` is skipped; the recorded GUID is validated before it reaches `defaults` argv | unit (fake seam) | `uv run pytest tests/test_terminal_keys.py -k default_profile --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-04 | TBD | TBD | NTERM-02 | T-31-XX (foreign file, symlink at the profile path) | A foreign file is refused and never overwritten; drift rewrites; a deleted file whose default is still ours reads `≈`; strip deletes only on a GUID match and only below HOME | unit (scratch HOME) | `uv run pytest tests/test_terminal_keys.py -k "iterm2 and (foreign or drift or strip or pending)" --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-05 | TBD | TBD | NTERM-03 | — | `herdr-app` has its own id; the script `paths` are exactly the four; the cask has `arch = ["arm64"]`; `NO_MACOS_INTEL` is honest; the Intel fixture is unavailable | unit | `uv run pytest tests/test_registry.py -k "herdr_app or no_macos_intel" --no-cov -q` | ✅ file, ❌ W0 new cases | ⬜ pending |
| 31-XX-06 | TBD | TBD | NTERM-03 | T-31-XX (race with the app rewriting `keys.json`) | Keys goldens G4/G5; a user binding (normalized chord, shuffled sections) is kept with `herdr-app: partial: kept yours`; the install note names the displaced picker; a reconfigure is idempotent; strip removes only owned keys still holding the recorded value; a `SettingsChanged` mismatch refuses and writes nothing | unit | `uv run pytest tests/test_terminal_keys.py -k herdr_app --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-07 | TBD | TBD | NTERM-03 | T-31-XX (malicious `keys.json`) | GPUI chord grammar normalization: cmd, super and win, secondary per OS, uppercase key, trailing `-`, first keystroke of a multi-stroke chord; huge or deeply nested files refused through `read_capped` | unit | `uv run pytest tests/test_terminal_keys.py -k chord --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-08 | TBD | TBD | NTERM-03 | — | A `herdr-app:` prefixed warning is never routed to the `herdr` row | unit | `uv run pytest tests/test_version_status.py -k herdr_app --no-cov -q` | ✅ file, ❌ W0 new cases | ⬜ pending |
| 31-XX-09 | TBD | TBD | NTERM-03 | T-31-XX (container teardown scope) | Container orchestration: PID-named box, root libs stage, steps run as the tester, teardown by exact name, no prune or reset | host (stubbed `ct`) | `uv run pytest tests/test_container_e2e_herdr_app.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 31-XX-ORCH | TBD | TBD | NTERM-03 | T-31-XX (nested `curl \| sh`, outside our receipt) | Install and removal leave herdr's binary and `~/.config/herdr` byte-identical in both orders; residue only on the allowlist | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh herdr-app` | ❌ W0 | ⬜ pending |
| 31-XX-10 | TBD | TBD | NTERM-02, NTERM-03 | — | Completeness and `same_directory` tests pass with both rows; union dispatch leaves the four region rows' tests unchanged | unit | `uv run pytest tests/test_terminal_keys.py --no-cov -q` | ✅ | ⬜ pending |
| 31-XX-11 | TBD | TBD | NTERM-02, NTERM-03 | — | The skill table rows match the registry and `TERMINAL_KEYS` | unit | `uv run pytest tests/test_tool_onboarding_skill.py --no-cov -q` | ✅ file, ❌ W0 new row tests | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] iTerm2 tests (profile goldens, default-profile states, foreign/drift/strip/pending) — new cases in `tests/test_terminal_keys.py` or `tests/test_iterm2_profile.py` (NTERM-02)
- [ ] herdr-app keys tests and chord grammar — new cases or `tests/test_herdr_app_keys.py` (NTERM-03)
- [ ] autouse `defaults` seam stub in `tests/conftest.py`
- [ ] `tests/e2e_herdr_app_driver.py` and `tests/test_container_e2e_herdr_app.py`, plus the `herdr-app` target in `scripts/container-e2e-verify.sh`
- [ ] fixture plist for `defaults export` (inline string in the test)

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
