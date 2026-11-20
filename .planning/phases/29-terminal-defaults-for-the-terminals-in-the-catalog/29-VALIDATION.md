---
phase: "29"
slug: "terminal-defaults-for-the-terminals-in-the-catalog"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: "2026-11-20"
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| **Quick run command** | `uv run pytest <the task's test files> -n auto -q --no-cov` |
| **Full suite command** | `make validate` then `make test` (once, after the last task of each plan) |
| **Estimated runtime** | ~29 seconds per targeted run |

---

## Sampling Rate

- **After every task commit:** the task's `<automated>` targeted pytest (the commit hook runs the six static gates)
- **After every plan:** `make validate` once and `make test` once on the final tree (in each plan's last task)
- **Orchestrator gates before 29-06 (hard since review round 2):** the WezTerm D-07 cwd check after 29-03 (since review round 3, C3-H2, it performs `SpawnTab` and `SpawnWindow` through `window:perform_action` under Xvfb, never `wezterm cli spawn`) and `scripts/container-e2e-verify.sh herdr-keys` after 29-05, each recorded in that plan's SUMMARY section `## Orchestrator verification`. A D-07 FAIL stops the run for a replan to `Writes`; a herdr-keys FAIL stops it for a replan toward the pass-through setting; an UNPROVEN is retried, never a pass. 29-06 requires both PASS lines and otherwise stops `BLOCKED` with nothing committed
- **Before `/gsd-verify-work`:** Full suite must be green; the orchestrator runs the 29-06 `<verification>` checklist (kitty load_config and WezTerm live checks when the executor could not, `make verify-registry`)
- **Max feedback latency:** 29 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 | TERM-03 | T-29-02 | Only a stale installer-owned region is rewritten, on reconfigure; user bytes kept | unit (tracer) | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py tests/test_setup.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-01-02 | 01 | 1 | TERM-02, TERM-03 | T-29-01, T-29-03, T-29-04, T-29-23 | Placement inserts keep every user line; the row's validate guards every rewrite (a moved region is refused, A1) and, for a row that opts in, the status pass on an unchanged region (C2-H2); a bound row deletes a created config only at the path its sidecar records, a changed resolver path is left alone with a warning (C3-H1), Alacritty's created record unchanged; shell region found by exact marker lines | unit | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py tests/test_setup.py tests/test_app.py -n auto -q --no-cov` then `make validate`, `make test` | ✅ existing files | ✅ green |
| 29-05-01 | 05 | 1 | TERM-05 | T-29-17, T-29-19, T-29-20 | Driver refuses outside the container; verdict passes only on exact bytes; bytes attributed by cumulative expected length, split and delayed writes included (A3); a client that closed the pty before the recorder started is UNPROVEN, never a generic ERROR (C3-A1); arrows only as CSI 1;3 (H4) | unit | `uv run pytest tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_bun.py -n auto -q --no-cov` | ❌ new file in the task | ✅ green |
| 29-05-02 | 05 | 1 | TERM-05 | T-29-18 | Verb removes only its PID-named container and a pulled image; no prune | unit (stubbed ct) | `uv run pytest tests/test_container_e2e_herdr_keys.py tests/test_container_e2e_bun.py tests/test_terminal_keys.py -n auto -q --no-cov` then `make validate` (shellcheck gate included, A7), `make test` | ❌ new file in 29-05-01 | ✅ green |
| 29-02-01 | 02 | 2 | TERM-01 | T-29-05, T-29-09, T-29-24 | kitty region at the top; user maps skipped and reported; no Option-as-Alt; a created kitty.conf is deleted only at its recorded path, a user's fallback kitty.conf survives a resolver change (C3-H1) | unit | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_registry.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-02-02 | 02 | 2 | TERM-01 | T-29-06, T-29-07 | Include scan read-only, bounded (lazy iglob, caps reported, A2), FIFO-safe; clear_all_shortcuts refuses on first apply, recorded install stays quiet (H1) | unit + self-verifying kitty load_config outside pytest (`KITTY_LOAD_OK`, A3) | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-02-03 | 02 | 2 | TERM-01 | T-29-08 | No kitty method names /Applications | unit | `uv run pytest tests/test_registry.py tests/test_resolve.py tests/test_ownership.py tests/test_model.py -n auto -q --no-cov` then `make validate`, `make test` | ✅ existing files | ✅ green |
| 29-03-01 | 03 | 3 | TERM-02 | T-29-10, T-29-12, T-29-13 | Lua guard appends only free chords; a later `config.keys =` after the region refused on every write (H3) and reported by status on an unchanged region (C2-H2); created file deleted only when ours, at its recorded path (a user's `~/.wezterm.lua` survives a resolver change, C3-H1), and untouched | unit | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_registry.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-03-02 | 03 | 3 | TERM-02 | T-29-11 | Read-back through one seam, swapped in every test by a conftest autouse fixture (A4); argv list, timeout; could-not-verify note, never a refusal (A5) | unit + self-verifying live read-back check outside pytest (`WEZTERM_LIVE_OK`, A1) | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_session.py tests/test_setup.py tests/test_app.py tests/test_engine.py tests/test_execute_screen.py tests/test_tweaks.py tests/test_version_status.py tests/test_catalog_tui.py tests/test_layout_80x20.py tests/test_plan.py tests/test_registry.py tests/test_render.py tests/test_resolve.py tests/test_screen_family.py tests/test_tool_health.py tests/test_uninstall_e2e.py tests/test_uninstall.py tests/test_update.py tests/test_wizard_app.py -n auto -q --no-cov` then `make validate`, `make test` | ✅ existing files | ✅ green |
| 29-04-01 | 04 | 4 | TERM-04 | T-29-14, T-29-15 | sessionui.rc never written; unreadable, invalid XML or a non-directory parent is unknown and claims nothing (A6, A2) | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_setup.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-04-02 | 04 | 4 | TERM-04 | T-29-16 | Stock note once, on the write that sets up Konsole, only for the stock state (none for a regular file at `kxmlgui5/konsole`, A2); stock and removed fixtures byte-identical (A9) | unit | `uv run pytest tests/test_terminal_shell.py tests/test_version_status.py tests/test_setup.py tests/test_render.py tests/test_session.py -n auto -q --no-cov` then `make validate`, `make test` | ✅ existing files | ✅ green |
| 29-06-01 | 06 | 5 | TERM-01..TERM-05 | T-29-21 | Hard gate: stops `BLOCKED` with nothing committed unless `D-07 cwd check: PASS (<date>, SpawnTab and SpawnWindow performed through perform_action)` (C3-H2) and `herdr-keys: PASS` are recorded (C2-H3, C2-H4); the gated cells and the WezTerm Vendor note say verified | gate (awk over the two SUMMARY sections) + unit (skill text tests) + note check | the two awk gate commands of 29-06 Task 1, then `uv run pytest tests/test_tool_onboarding_skill.py tests/test_docs.py tests/test_docs_only.py tests/test_terminal_keys.py -n auto -q --no-cov` | ✅ existing files | ✅ green |
| 29-06-02 | 06 | 5 | TERM-01..TERM-05 | T-29-21, T-29-22 | Skill table tied to TERMINAL_KEYS; no row writes a global Alt switch | unit | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_terminal_keys.py -n auto -q --no-cov` then `make validate`, `make test` | ✅ existing files | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements: every task writes its failing test first inside its own commit (test-first inside one green commit, `.claude/testing.md`), and the only new test files (`tests/e2e_herdr_keys_driver.py`, `tests/test_container_e2e_herdr_keys.py`) are created by 29-05 Task 1 before anything uses them. No framework install.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bytes reach the shell inside a live herdr pane | TERM-05 | Needs a live herdr server and pty; container only, orchestrator only | After 29-05, before 29-06: `scripts/container-e2e-verify.sh herdr-keys`; expect `TRACER_HERDR_INSTALL_OK`, `TRACER_HERDR_KEYS_OK received=1b62,1b66,1b5b313b3344,1b5b313b3343,0c`, `TRACER_LANDING_TEARDOWN_OK`, exit 0; record `herdr-keys: PASS/FAIL` (or `UNPROVEN` while the environment keeps failing) in the 29-05 SUMMARY's `## Orchestrator verification`; a FAIL stops the run for a replan toward the pass-through setting; 29-06 requires PASS |
| Generated kitty maps load in real kitty | TERM-01 | The pytest sandbox refuses to launch kitty | 29-02 `<context>` self-verifying check script (expects `KITTY_LOAD_OK`, exit 0), if the executor reported "not run" |
| WezTerm Lua region loads and keeps the user's chords | TERM-02 | The pytest sandbox refuses to launch wezterm or lua | 29-03 `<context>` self-verifying check script (expects `WEZTERM_LIVE_OK`, exit 0), if the executor reported "not run" |
| WezTerm SpawnTab/SpawnWindow cwd without OSC 7 (29 D-07) | TERM-02 | GUI (Xvfb) check in a disposable container; executors have neither | Orchestrator container run after 29-03, before 29-06, per 29-03 `<context>` "D-07 cwd check, orchestrator only" (review round 3, C3-H2): wezterm 20240203-110809-5046fc22 under Xvfb with a throwaway config (never the host's); `gui-startup` opens plain `/bin/sh` in `/known/dir` (no OSC 7); a one-shot `update-status` callback performs `SpawnTab 'CurrentPaneDomain'` and `SpawnWindow` through `window:perform_action` and writes each new pane's `get_current_working_dir()` and process cwd; PASS only for the result file `tab /known/dir /known/dir\nwindow /known/dir /known/dir\n` (`wezterm cli spawn` never counts); record `D-07 cwd check: PASS (<date>, SpawnTab and SpawnWindow performed through perform_action)` or `FAIL (...)` in the 29-03 SUMMARY's `## Orchestrator verification`; a FAIL stops the run for a replan to `Writes`; 29-06 requires that PASS line and stops `BLOCKED` otherwise |
| Konsole 26.x stock chord and post-removal sessionui.rc (29 D-09) | TERM-04 | Live KDE capture in a disposable container | Orchestrator container capture or UAT line; the source citation (Shortcut_p.h ACCEL = Ctrl+Shift) stands in |
| kitty opt+left/opt+right with macos_option_as_alt no, cmd+k, cmd+t/n/enter; cask wrapper under --appdir; kitty config in ~/Library/Preferences; WezTerm SUPER k and OPT arrows; herdr on macOS | TERM-01, TERM-02, TERM-05 | Real Mac (SKILL-05) | UAT lines deferred to the owner's Mac |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 29s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved (Nyquist audit 2026-11-20)

---

## Validation Audit 2026-11-20

| Requirement | Verdict | Evidence that fails if the behavior breaks |
|-------------|---------|--------------------------------------------|
| TERM-01 kitty | COVERED | tests/test_terminal_keys.py: test_kitty_golden_linux_created_file:398, test_kitty_golden_macos_created_file:413, test_kitty_never_writes_option_as_alt:427, test_kitty_user_map_is_kept_and_reported:432, include and clear_all_shortcuts tests :481-:713; /Applications absence in tests/test_registry.py:2601; `KITTY_LOAD_OK` in 29-02-SUMMARY |
| TERM-02 WezTerm | COVERED | test_terminal_keys.py:785-:1240 (region, user keys kept, config.keys guard, read-back); test_terminal_shell.py:299,:324 (exact marker lines); `D-07 cwd check: PASS` in 29-03-SUMMARY; `WEZTERM_LIVE_OK` |
| TERM-03 Alacritty | COVERED | test_terminal_keys.py:1779-:1818 (Ctrl+L clear, Phase 28 install flips); test_terminal_keys.py:1020 (Linux Alt rows stay); test_terminal_shell.py:1203-:1637 |
| TERM-04 Konsole | COVERED | test_terminal_shell.py:1737-:1899 (stock read, removed key kept and reported, never writes, unknown on unreadable/invalid) ; live capture stays manual (source citation) |
| TERM-05 herdr | COVERED | tests/test_container_e2e_herdr_keys.py:118-:360 (verdict, byte attribution, container-only, no keys row at :355); live `herdr-keys: PASS` in 29-05-SUMMARY |

Per-task map: 12/12 rows COVERED, 0 PARTIAL, 0 MISSING. Tests added: none. Manual-only rows (macOS, live KDE) remain deferred by design.
