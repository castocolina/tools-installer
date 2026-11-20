---
phase: "28"
slug: "shared-terminal-keys-mechanism"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-20"
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-xdist + coverage (`fail_under = 90`), pyright strict over `installer/` and `tests/` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); autouse scratch HOME in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> -n auto -q --no-cov` (each task's `<automated>` names its files) |
| **Full suite command** | `make validate` then `make test`, once after each plan's last task commit |
| **Estimated runtime** | ~28 seconds |

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest command; the commit hook runs the six static gates on every commit (owner rule, 2026-11-20)
- **After every plan:** `make validate` once and `make test` once on the final tree (in each plan's last task)
- **After every wave:** push the branch and watch CI (`validate & test` on ubuntu-latest and macos-latest)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 28 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | KEYS-01 | T-28-01 | Golden bytes of the user's `alacritty.toml` pinned before any move (created, user content, adjacent binding, shell plus keys, strip) | integration (scratch HOME) | `uv run pytest tests/test_terminal_keys.py -n auto -q --no-cov` | ❌ W0 (created by this task, green on pre-move code) | ⬜ pending |
| 28-01-02 | 01 | 1 | KEYS-01 | T-28-01, T-28-02, T-28-03 | Primitives moved verbatim apart from the renamed references and the `text_line` loop-local; malformed-marker guard and compare-before-commit unchanged; every function body terminal_shell keeps, except `_sync_alacritty` and `apply_alacritty_keys`, AST-identical to Task 1's commit (`BODIES-UNCHANGED 32`) | existing + static | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py tests/test_setup.py tests/test_tool_onboarding_skill.py tests/test_reachability.py -n auto -q --no-cov`, the AST check, `make validate`, `make test` | ✅ | ⬜ pending |
| 28-02-01 | 02 | 2 | KEYS-01, KEYS-02 | T-28-05, T-28-06, T-28-07 | Table-driven dispatch by tool id; record names unchanged; strip deletes only installer-created files | integration (tracer) + static | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py tests/test_app.py tests/test_setup.py tests/test_tool_onboarding_skill.py -n auto -q --no-cov` plus the `rg` DISPATCH-CLEAN check | ✅ | ⬜ pending |
| 28-02-02 | 02 | 2 | KEYS-02 | T-28-04 | A declarer without a row is a refusal, never a crash; completeness fails for an extra declarer, an empty table, a row without a declarer (fixture key `ghost`), a Konsole row | unit (fixture registry in `tmp_path`) | `uv run pytest tests/test_terminal_keys.py -n auto -q --no-cov`, `make validate`, `make test` | ✅ (file from 28-01) | ⬜ pending |
| 28-03-01 | 03 | 3 | KEYS-02 | T-28-12, T-28-13 | Drift rewrite touches only a present stale owned region on reconfigure; a refusing or unreadable recorded file stays quiet (OQ1) | integration (scratch HOME + status pass) | `uv run pytest tests/test_terminal_keys.py tests/test_version_status.py tests/test_post_install.py tests/test_terminal_shell.py tests/test_setup.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 28-03-02 | 03 | 3 | KEYS-03, KEYS-04 | T-28-14, T-28-15 | `Writes` snippet only inside the owned region and re-parsed; no Option-as-Alt field | unit (fixture rows) | `uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_post_install.py tests/test_version_status.py -n auto -q --no-cov`, `make validate`, `make test` | ✅ | ⬜ pending |
| 28-04-01 | 04 | 2 | KEYS-03 | T-28-08, T-28-09, T-28-10, T-28-11 | Widget only inside its `tweak:zsh` block, guarded for bash with the nounset-safe `${ZSH_VERSION-}`, stripped on removal; apply then strip pinned on eight inputs (SPEC R3 as amended 2026-11-20, needs confirmation); the two `print -n` lines emit exactly `ESC[H ESC[2J` and `ESC[3J` through a non-interactive `zsh -f -c` (review A8); no test forks, opens a pty or starts an interactive shell | unit (escape spelling, emitted bytes, eight round-trip pairs, removal) + existing `bash -n` / `zsh -n` parse tests (`zsh -n` and the emitted-bytes test skipped with a reason without zsh) | `uv run pytest tests/test_tweaks.py tests/test_version_status.py tests/test_post_install.py tests/test_registry.py tests/test_app.py tests/test_setup.py tests/test_policy.py tests/test_session.py tests/test_uninstall.py tests/test_policies_e2e.py tests/test_policy_tweaks.py tests/test_uninstall_e2e.py tests/test_schedules_lifecycle.py -n auto -q --no-cov` | ✅ | ⬜ pending |
| 28-04-02 | 04 | 2 | KEYS-03 | N/A | N/A (rule (c) and the Conflicts attribution sentences, and the rule (c) pin) | doc pin | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_docs.py tests/test_docs_only.py -n auto -q --no-cov`, `make validate`, `make test` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_terminal_keys.py` — created by 28-01 Task 1 (golden bytes, committed before the move), extended by 28-02 (row, completeness, no-row backstop) and 28-03 (drift matrix, clear chord, same-directory)
- [ ] Fixture registry for the completeness test — a TOML string written to `tmp_path` and read with `load_tools` (no new helper module)
- [x] Framework install — none needed (pytest, xdist and coverage are present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Ctrl+L at a zsh prompt on a real Mac (Terminal.app, iTerm2) clears the screen and the scrollback, and `ESC[2J` does not push the screen into scrollback first | KEYS-03 | No macOS GUI terminal in CI or on this host; deferred to the owner's Mac by standing rule | Open Terminal.app and iTerm2 with the managed `~/.myshellrc`, fill the scrollback, type text, press Ctrl+L: the screen and scrollback are empty and the typed text is redrawn |
| A multi-line starship prompt redraws correctly after `zle .reset-prompt` plus `zle -R` | KEYS-03 | Visual redraw of a third-party prompt; the byte-level tests prove the escape order and the bytes zsh's `print` emits, not a live redraw (the live pty probe was dropped in review round 1) | With starship enabled, press Ctrl+L at a two-line prompt: both prompt lines and the buffer are redrawn once at the top |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 28s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** {pending / approved YYYY-MM-DD}
