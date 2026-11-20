---
phase: "30"
slug: "onboard-ghostty"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-20"
---

# Phase 30 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 30-RESEARCH.md "Validation Architecture". The planner replaces the placeholder task ids, plan and wave numbers with the real ones.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); isolation fixtures in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Container proof** | `scripts/container-e2e-verify.sh ghostty` (orchestrator only, never on the host) |
| **Estimated runtime** | ~30 seconds per targeted run (to confirm in the first plan) |

Files the quick command draws from: `tests/test_terminal_keys.py`, `tests/test_terminal_shell.py`, `tests/test_registry.py`, `tests/test_model.py`, `tests/test_download.py`, `tests/test_desktop_entry.py`, `tests/test_tool_onboarding_skill.py`, `tests/test_container_e2e_ghostty.py`.

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green and `scripts/container-e2e-verify.sh ghostty` PASS (FUSE pass and no-FUSE pass; an UNPROVEN FUSE pass is retried, never recorded as a pass)
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

Task ids, plans and waves below are placeholders; the planner fills the real ones.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | NTERM-01 | T-30-01 | Entry loads; Arch amd64/arm64 resolve to pacman, debian and Bazzite amd64 to the x86_64 tarball, arm64 to aarch64, macOS to the cask; URLs equal asset names; lowercase 64-hex pins; "community build" in desc and note | unit | `uv run pytest tests/test_registry.py -k ghostty --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-01-02 | 01 | 1 | NTERM-01 | T-30-02 | Loader refuses raw+strip, raw+archive, a bad note (Rich markup) and a bad desktop id | unit | `uv run pytest tests/test_model.py -k "raw or note or desktop" --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-02-01 | 02 | 2 | NTERM-01 | T-30-01, T-30-03 | A digest mismatch raises `ChecksumMismatch` and places nothing (no binary, no menu files); extraction runs only after `_fetch_verified`, no shell | unit | `uv run pytest tests/test_download.py -k ghostty --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-02-02 | 02 | 2 | NTERM-01 | T-30-04, T-30-05 | Extraction argv fixed; only the two fixed names under `workdir/AppDir/` read, symlinks out of the workdir refused; `desktop_entry.render` refuses relative paths and control characters; leaves recorded only when created; a user's `.desktop` kept | unit | `uv run pytest tests/test_download.py tests/test_desktop_entry.py --no-cov -q` | ✅ existing files, new tests; fixture text from probe 1 is Wave 0 | ⬜ pending |
| 30-03-01 | 03 | 3 | NTERM-01 | T-30-06, T-30-07 | Shell region at the top with `command = <zsh> -l` (`_safe_executable`, `shlex.join`); a user `command` (same file and legacy file) gives `partial`; `config-file` gives `partial`; revert strips the region | unit | `uv run pytest tests/test_terminal_shell.py -k ghostty --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-03-02 | 03 | 3 | NTERM-01 | T-30-06 | Keys row: Linux and macOS goldens through `run_post_install`; `macos-option-as-alt` absent; four macOS config-resolver cases plus empty files; conflict normalization; a user `keybind = clear` refused; user lines win | unit | `uv run pytest tests/test_terminal_keys.py -k ghostty --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-03-03 | 03 | 3 | NTERM-01 | T-30-06 | Drift: pending without a record; reconfigure restores the owned region; a second reconfigure is a no-op | unit | `uv run pytest tests/test_terminal_keys.py -k "ghostty and drift" --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-03-04 | 03 | 3 | NTERM-01 | T-30-06 | `_after_removal` strips both regions (keys and shell) and drops a created whitespace-only file; a user's own bytes survive | unit | `uv run pytest tests/test_terminal_keys.py -k "ghostty and strip" --no-cov -q` | ✅ existing file, new tests | ⬜ pending |
| 30-04-01 | 04 | 4 | NTERM-01 | T-30-08 | Harness wiring; teardown removes only its own PID-named container, no prune; `--device /dev/fuse` without `--privileged`; verdict functions pure and exact; driver refuses outside the container | unit (stubbed ct) | `uv run pytest tests/test_container_e2e_ghostty.py --no-cov -q` | ❌ W0 (`tests/e2e_ghostty_driver.py`, `tests/test_container_e2e_ghostty.py`) | ⬜ pending |
| 30-04-02 | 04 | 4 | NTERM-01 | T-30-08 | Orchestrator container run: install (method `tarball`, `~/.local/bin/ghostty --version`, two leaves, receipt of three paths), sync, regions (`command = <zsh> -l`, `keybind = ctrl+shift+k=text:\x0c`, read only after the file exists), remove (home diff equals receipt paths plus the created config); FUSE pass and no-FUSE pass | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh ghostty` | ❌ W0 (target does not exist yet) | ⬜ pending |
| 30-05-01 | 05 | 5 | NTERM-01 | T-30-09 | Skill table has a `ghostty` row tied to `TERMINAL_KEYS`; clear cell `written`; no row writes a global Alt switch | unit | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_terminal_keys.py --no-cov -q` | ✅ existing files | ⬜ pending |
| 30-05-02 | 05 | 5 | NTERM-01 | — | Plan close: static gates and the whole suite green on the final tree; `make verify-registry` read-only check of the new pins | gate | `make validate` then `make test` (once each) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/e2e_ghostty_driver.py` — in-container verbs (`install`, `sync`, `regions`, `remove`) and pure verdict functions, each printing a `TRACER_GHOSTTY_*` verdict
- [ ] `tests/test_container_e2e_ghostty.py` — host tests with a stubbed `ct` (modeled on `tests/test_container_e2e_herdr_keys.py`)
- [ ] Fixture text of the AppImage desktop file (the 694-byte root file from research probe 1) for the render and extraction tests
- [ ] `scripts/container-e2e-verify.sh` `ghostty` target (the verb the driver and its test depend on)

*No framework install needed. Every other task writes its failing test first inside its own commit (`.claude/testing.md`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cask install to the user-writable app location (`~/Applications/Ghostty.app`) | NTERM-01 | Real Mac (D-15); no macOS host here | Owner's Mac: install through the wizard; confirm the app lands under `~/Applications` and launches |
| Option+Left / Option+Right word moves (`esc:b` / `esc:f`) in a zsh prompt, including on a Spanish Mac layout | NTERM-01 | Real Mac keyboard and layout | Owner's Mac: in a Ghostty window with the owned region, press Option+Left and Option+Right; the cursor moves by word |
| Cmd+K clears the screen and scrollback | NTERM-01 | Real Mac | Owner's Mac: press Cmd+K in a Ghostty window; screen clears |
| New tab opens in the same directory | NTERM-01 | Real Mac GUI; `cd` then Cmd+T | Owner's Mac: `cd` to a known directory, open a new tab, `pwd` equals it |
| macOS effective-config resolution (which config file Ghostty reads) | NTERM-01 | Real Mac | Owner's Mac: `~/Applications/Ghostty.app/Contents/MacOS/ghostty +show-config` and `+list-keybinds` show the `super+k` line and no `macos-option-as-alt`; the written file is the one Ghostty resolves |
| FUSE mount of the AppImage inside rootless podman (research assumption A6) | NTERM-01 | Rootless podman with `--device /dev/fuse` may not mount; if unproven the pass reads `_UNPROVEN` | If the container FUSE pass reports UNPROVEN, run the AppImage once on the Bazzite host's own FUSE (UAT, record the result); never record UNPROVEN as PASS |
| `xterm-ghostty` TERMINFO resolves inside the AppImage window (zsh line editing works under FUSE and under extract-and-run) | NTERM-01 | Needs a live Ghostty window on Linux | UAT on Bazzite: open the installed Ghostty, check `echo $TERM` and `infocmp xterm-ghostty`, then line-edit (arrows, Ctrl+L); report any `unknown terminal` fault |
| 5 s status-probe timeout is enough for the AppImage extracting about 49 MB without FUSE | NTERM-01 | Timing depends on the host and disk | Container no-FUSE pass: status pass after install must not time out; record the measured time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
