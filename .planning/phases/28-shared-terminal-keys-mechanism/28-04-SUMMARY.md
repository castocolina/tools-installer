---
phase: 28-shared-terminal-keys-mechanism
plan: 04
subsystem: managed zsh configuration and the onboarding skill
tags: [zsh, ctrl-l, shell-init-bundle, emitted-bytes, skill-rule-c]
requires:
  - phase: 28-02
    provides: the table-driven dispatch the zsh row's check and removal run through
provides:
  - "A zsh shell-init bundle whose widget binds Ctrl+L to a screen-clear plus scrollback-erase, bound in emacs, viins and vicmd, guarded by ${ZSH_VERSION-} (KEYS-03, D-07 to D-09)"
  - "Tests: the widget text and its escape spelling, the exact bytes zsh emits (skipped without zsh, with a reason), eight pinned apply-then-strip pairs, removal, and the pending row"
  - "The onboarding skill's rule (c) says the zsh clear is written in phase 28, and the partial: line's new home is stated"
affects: [28-03, phase-29, phase-30]
actuals:
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - "A shell-init bundle as a tool's shell widget, removed with the tool's managed block"
    - "A non-interactive zsh -f -c of a builtin proves emitted bytes without a pty"
key-files:
  created: []
  modified:
    - installer/tweaks.py
    - installer/registry.toml
    - tests/test_tweaks.py
    - tests/test_version_status.py
    - .claude/skills/tool-onboarding/SKILL.md
    - tests/test_tool_onboarding_skill.py
key-decisions:
  - "The live pty probe was dropped (review H4: the launch guard refuses an interactive shell with no script); the byte-level proof is the always-on spelling test plus the non-interactive emitted-bytes test"
  - "Apply then strip is pinned for eight inputs exactly as shellrc behaves (SPEC R3 amended 2026-11-20, needs owner confirmation; real fix in backlog 999.27)"
requirements-completed: []
coverage:
  - id: D1
    description: "The managed zsh configuration binds Ctrl+L to clear the visible screen and the scrollback, and the widget is removed with the managed block"
    requirement: "KEYS-03"
    verification:
      - kind: unit
        ref: "uv run pytest tests/test_tweaks.py -k 'zsh_clear or zsh_removal or stable_ids' (11 passed) and the emitted-bytes and zsh -n tests (17 passed, none skipped), orchestrator run"
        status: pass
    human_judgment: false
  - id: D2
    description: "The visual redraw of the prompt after the clear, with the widget loaded by a real terminal, on both OSes"
    requirement: "KEYS-03"
    verification: []
    human_judgment: true
    rationale: "No live interactive-shell probe is allowed by the test guard, and there is no Mac host in the run; the emitted bytes are proved, the visual result is a manual check"
duration: 10min (executor)
completed: 2026-11-20
---

# Phase 28 Plan 04 Summary

- **Task 1** — commit `62a6aa2c`: Added the zsh Ctrl+L widget as a shell-init bundle, connected it to zsh install tuning, and added widget, emitted-byte, round-trip, removal, and pending-tuning tests.
  - **RED:** Targeted pytest run failed as expected: zsh bundle/status was missing and the pinned bundle order differed.
  - **GREEN:** Targeted suite passed. Focused results: `11 passed` for widget text, eight round-trip cases, removal, and bundle order; `17 passed` for shell guards/parsing and emitted bytes.
  - `test_each_shell_init_body_parses_in_zsh[zsh]` ran; `test_clear_widget_emits_the_exact_bytes_in_zsh` ran. Both passed. No live pty probe was run.
- **Task 2** — commit `2899d560`: Updated onboarding rule (c) to say the zsh clear is written in phase 28, and corrected the Conflicts attribution for the `partial:` line.
  - **RED:** Targeted pytest failed on the stale "planned for phase 28" pin.
  - **GREEN:** `uv run pytest tests/test_tool_onboarding_skill.py tests/test_docs.py tests/test_docs_only.py -n auto -q --no-cov` passed.
- **Final validation:** `make validate` passed all six static gates. `make test` passed: **7900 passed, 6 skipped**, 96.21% coverage.
- **Owner confirmation needed:** The amended SPEC R3 adjacency/round-trip wording remains provisional; the eight pinned pairs reflect the measured `shellrc` behavior, with backlog `999.27` tracking the shared fix. D-06's pending/drift semantics also remain flagged for confirmation. The D-12 import-line deviation to `tests.test_terminal_keys` remains an owner-confirmation item.
- **Existing-host behavior:** Hosts with zsh will show `≈ apply install tuning` until reconfigure writes the block. Removing zsh strips its block and record.
- **Deviations:** The first GREEN attempt exposed a malformed Python source insertion; it was corrected, then the targeted tests passed. The first commit-hook attempt also caught formatting issues; those were fixed and the commit hook passed on retry.

Skipped a live pty/interactive-shell probe and real-Mac visual behavior checks, as instructed. Those remain outside this plan's verification.

## Orchestrator verification (written by the orchestrator, not by the executor)

- **Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 10 minutes (10:14 to 10:24), stderr empty, two commits; the pre-existing untracked goals file is byte-identical.
- **Checked by the orchestrator:** all plan acceptance criteria pass (zsh first in `SHELL_INIT_TOOLS`, `tools_installer_clear_all` five times, the zsh registry entry carries `source_shell_init`, `${ZSH_VERSION-}` present, the new test runs only a non-interactive `zsh -f -c` with no fork or pty line, `planned for phase 28` gone from the skill and its test, `written in phase 28 (KEYS-03)` once, the partial-line move sentence once, the skill still names the audit skill on exactly one line, no line naming Policies is non-ASCII); the plan's four non-make verify commands exit 0 (the broad targeted run, the 11-test run, the 17-test run, the skill and docs run); existing tests changed only by the one-line `planned for phase 28` pin (`tests/test_tweaks.py` and `tests/test_version_status.py` gained lines and lost none); the one `skipif` in the new code is the plan-sanctioned `shutil.which("zsh") is None` skip with the reason "zsh is not on PATH; emitted bytes not checked", the same idiom as the existing zsh test.
- **Reported by the executor and not re-run by the orchestrator:** `make validate` and the full `make test` (7,900 passed, 96.21%). The push gate runs the full suite again.
- **Provisional decisions to carry into the verification report:** 28 D-06, the amended SPEC R3 round-trip wording (backlog 999.27), the D-12 import-line deviation (plan 28-02).
- **Manual check left for the owner:** the visual prompt redraw after Ctrl+L in a real terminal on Linux and macOS.
