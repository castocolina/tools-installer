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
> Seeded from 30-RESEARCH.md "Validation Architecture"; the per-task map below carries the real plan, wave and task ids of plans 30-01 to 30-06.

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

Task ids are `30-<plan>-<task>`; every plan's last task also runs `make validate` once and `make test` once (not repeated per row). Plan 05's container run and plan 06's hard gate are orchestrator steps recorded in the SUMMARY of plan 05.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 30-01-01 | 01 | 1 | NTERM-01 | T-30-01 | Tracer: the entry loads; Arch amd64/arm64 resolve to pacman, debian and Bazzite amd64 to the x86_64 tarball, arm64 to aarch64, macOS to the cask (os_version 12 to none); URLs equal the live asset names; lowercase 64-hex pins; `community build` in desc and note; one path (Linux x86_64) installs end to end through the engine with the note and one receipt artifact; skill row present | unit + integration (stub runner) | `uv run pytest tests/test_registry.py tests/test_engine.py tests/test_model.py tests/test_tool_onboarding_skill.py tests/test_download.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-01-02 | 01 | 1 | NTERM-01 | T-30-01, T-30-02, T-30-03 | Loader refuses raw+archive, a bad note (Rich markup, control character, several lines), a bad or raw-less desktop id; a tampered AppImage places nothing and reads CHECKSUM_MISMATCH | unit | `uv run pytest tests/test_model.py tests/test_download.py tests/test_engine.py tests/test_registry.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-02-01 | 02 | 2 | NTERM-01 | T-30-04, T-30-06 | `render(drop=)` drops listed keys only, default unchanged; `smoke_binary(tmpdir=)` and the raw install smoke use the workdir as TMPDIR | unit | `uv run pytest tests/test_desktop_entry.py tests/test_executors.py tests/test_download.py tests/test_cargo_distrobox.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-02-02 | 02 | 2 | NTERM-01 | T-30-04, T-30-05, T-30-06, T-30-07 | `appimage_menu.install`: fixed extraction argv, only two fixed names read through `staged_member`, symlink out refused, a user's own file kept and named, a failure is a note and removes the icon it wrote; `artifact_paths` names two leaves | unit | `uv run pytest tests/test_appimage_menu.py tests/test_download.py tests/test_desktop_entry.py tests/test_cargo_distrobox.py -n auto -q --no-cov` | new module + existing files | pending |
| 30-02-03 | 02 | 2 | NTERM-01 | T-30-07 | Engine places menu entry and icon, receipt records binary + two leaves, a menu failure leaves the install, uninstall removes all three, `plan_uninstall` ignores a user's desktop file | integration | `uv run pytest tests/test_appimage_menu.py tests/test_engine.py tests/test_uninstall.py tests/test_registry.py tests/test_cargo_distrobox.py -n auto -q --no-cov` | new module + existing files | pending |
| 30-03-01 | 03 | 2 | NTERM-01 | T-30-08, T-30-11 | Resolver (Linux and the four macOS cases, empty files), load-order file list, chord normalizer, scan over every default file, validator | unit | `uv run pytest tests/test_terminal_keys.py -n auto -q --no-cov` | existing file, new tests | pending |
| 30-03-02 | 03 | 2 | NTERM-01 | T-30-08, T-30-09 | Keys row: Linux and macOS goldens through `run_post_install`; `macos-option-as-alt` absent; user chord kept and reported in the target, the legacy file and each macOS file; `keybind = clear` refused; status and apply agree; bound created path; declaration, `_TERMINAL_ROWS` entry and skill cell land together | unit | `uv run pytest tests/test_terminal_keys.py tests/test_registry.py tests/test_tool_onboarding_skill.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-03-03 | 03 | 2 | NTERM-01 | T-30-10 | Drift pending only without a record; reconfigure restores the bytes and a second one is a no-op; strip drops both regions, the record and a created file, keeps every user byte, quiet with no file | unit | `uv run pytest tests/test_terminal_keys.py tests/test_registry.py tests/test_tool_onboarding_skill.py -n auto -q --no-cov` | existing file, new tests | pending |
| 30-04-01 | 04 | 3 | NTERM-01 | T-30-12, T-30-13, T-30-14 | Shell region at the top with `command = <zsh> -l` (`_safe_executable`, `shlex.join`); install-route order pinned both ways; a user `command` in the target or the legacy file (or empty) gives no region and `partial`; `config-file` gives partial and writes; dry run writes nothing; zsh gone strips the shell region; macOS never touched | unit | `uv run pytest tests/test_terminal_shell.py tests/test_terminal_keys.py tests/test_tool_onboarding_skill.py tests/test_version_status.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-04-02 | 04 | 3 | NTERM-01 | T-30-14 | Removal strips both regions and keeps every user byte; a created file is deleted; Ghostty drift and partial reach the Ghostty row | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_terminal_keys.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-05-01 | 05 | 4 | NTERM-01 | T-30-15, T-30-17 | Pure verdicts (install, FUSE fallback unproven, sync, regions, remove as an order-independent set difference), `/tmp` check narrowed to installer dirs, the driver refuses outside the container, expected receipt paths equal `artifact_paths` | unit | `uv run pytest tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py -n auto -q --no-cov` | new driver + new test module | pending |
| 30-05-02 | 05 | 4 | NTERM-01 | T-30-16 | The `ghostty` verb: registered, PID-named own container, `--device /dev/fuse` without privileges, root setup (zsh fuse fuse3, ostree marker), teardown removes only its container and a pulled image, no prune or reset, other targets' container start unchanged | unit (stubbed ct) | `uv run pytest tests/test_container_e2e_ghostty.py tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_bun.py tests/test_container_e2e_receipts.py -n auto -q --no-cov` | script + existing files | pending |
| 30-05-ORCH | 05 | 4 | NTERM-01 | T-30-16, T-30-17 | Orchestrator container run: install (tarball, `ghostty --version`, three receipt paths), FUSE evidence, sync, regions read back with the real Ghostty, uninstall residue diff; FUSE pass and extract-and-run pass; recorded as `ghostty-container: PASS (<date>)` in the 30-05 SUMMARY | e2e (container, orchestrator only) | `scripts/container-e2e-verify.sh ghostty` | target built by 30-05-02 | pending |
| 30-06-01 | 06 | 5 | NTERM-01 | T-30-18 | Hard gate on the recorded PASS line, then the registry comment and the skill row record the container evidence | gate + unit | `awk '/^## Orchestrator verification/{s=1;next} /^## /{s=0} s && /^ghostty-container: PASS \(/{p=1} s && /^ghostty-container: (FAIL|UNPROVEN|not run)/{b=1} END{exit !(p && !b)}' .planning/phases/30-onboard-ghostty/30-05-SUMMARY.md` then `uv run pytest tests/test_registry.py tests/test_tool_onboarding_skill.py tests/test_docs.py tests/test_docs_only.py -n auto -q --no-cov` | existing files, new tests | pending |
| 30-06-02 | 06 | 5 | NTERM-01 | T-30-18 | Catalog guards: config_paths cover the resolver directories, pins are pinned GitHub-release methods, the note key only on the two AppImage methods, every desktop method is a raw tarball with two leaves; plan close: `make validate` then `make test` | unit + gate | `uv run pytest tests/test_ghostty_catalog.py tests/test_registry.py tests/test_tool_onboarding_skill.py -n auto -q --no-cov`, then `make validate`, then `make test` | new module | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/e2e_ghostty_driver.py` (plan 30-05, task 1): in-container verbs `lifecycle` and `lifecycle-extract` and the pure verdict functions, each printing a `TRACER_GHOSTTY_*` verdict
- [ ] `tests/test_container_e2e_ghostty.py` (plan 30-05, tasks 1 and 2): host tests with a stubbed `ct` (modeled on `tests/test_container_e2e_herdr_keys.py`)
- [ ] Fixture text of the AppImage desktop file (plan 30-02, task 1): RECONSTRUCTED from the keys the researcher recorded, not the byte-identical 694-byte file; the container run exercises the real file
- [ ] `scripts/container-e2e-verify.sh` `ghostty` target and the `CONTAINER_RUN_ARGS` hook (plan 30-05, task 2)

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
