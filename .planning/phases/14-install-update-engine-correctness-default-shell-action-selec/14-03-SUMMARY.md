---
phase: 14-install-update-engine-correctness-default-shell-action-selec
plan: "03"
subsystem: post-install
tags: [set_login_shell, post_install, oh-my-zsh, immutable-guard, reviewed-handoff, chsh]

requires:
  - phase: 09-postinstall-hooks-mechanism
    provides: Tool.postinstall singular hook, POSTINSTALL_HOOKS, install_tool post-success dispatch
  - phase: 07-system-user-tier-catalog-expansion
    provides: oh-my-zsh registry entry with CHSH=no install-script guard
provides:
  - Closed execution-free POST_INSTALL_HOOKS table in installer/post_install.py
  - install_tool dispatch of Tool.post_install after a successful method
  - InstallOutcome.post_install_handoff reviewed-instruction tuple
  - oh-my-zsh registry declaration of set_login_shell
affects:
  - 14-04 (console confirm callback + render_post_install_handoff)
  - 14-05 (in-TUI confirm binding through with_sensitive_confirm)

actuals:
  tokens: 4666
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Plural post_install dispatch table is a sibling of singular POSTINSTALL_HOOKS, never an extension of it"
    - "Sensitive action returns a fixed literal instruction tuple; the installer never interpolates a path or runs the command"
    - "Keyword-only confirm_sensitive_action on install_tool keeps session.Install unchanged"

key-files:
  created:
    - installer/post_install.py
    - tests/test_post_install.py
  modified:
    - installer/engine.py
    - installer/registry.toml
    - tests/test_engine.py
    - tests/test_registry.py

key-decisions:
  - "D-04: Platform.immutable is checked first and unconditionally; an atomic host is never asked"
  - "D-05: no confirmation callback, or a false return, produces nothing; unattended is the safe default"
  - "D-06: dispatch sits only on install_tool's post-success path, after the singular postinstall hook"
  - "D-07: one action, one tool, no shell parameter"
  - "Already-installed oh-my-zsh never reaches the action (single-direction trigger, not a gap)"
  - "D-04's blanket immutable block is one-way until ublue-os/bazzite#4159 has a root-cause analysis to re-verify against"
  - "App.suspend() in-process chsh is a recorded follow-up, not built here"

patterns-established:
  - "Registry selects a NAME from a closed, code-owned table that carries no command text"
  - "Isolation try/except around post_install dispatch folds a crash into postinstall_warning and yields empty instructions"
  - "One-declarer registry test is the automated fence against a guarded action becoming a general mechanism"

requirements-completed: ["D-04", "D-05", "D-06", "D-07"]

coverage:
  - id: D1
    description: Real oh-my-zsh entry declares set_login_shell; confirmed non-immutable install returns chsh -s instructions without running a second command
    requirement: D-06
    verification:
      - kind: unit
        ref: tests/test_engine.py#test_login_shell_action_dispatches_reviewed_instructions_after_oh_my_zsh_install
        status: pass
      - kind: unit
        ref: tests/test_post_install.py#test_real_oh_my_zsh_entry_declares_set_login_shell
        status: pass
      - kind: other
        ref: "python -c REGISTRY-OK/NO-EXEC/SIG-OK gates from 14-03 Task 1"
        status: pass
    human_judgment: false
  - id: D2
    description: Immutable host is neither asked nor given instructions, even when the action is default-enabled
    requirement: D-04
    verification:
      - kind: unit
        ref: tests/test_post_install.py#test_immutable_host_is_never_asked_and_produces_no_login_shell_instructions
        status: pass
      - kind: unit
        ref: tests/test_post_install.py#test_immutable_host_cannot_bypass_login_shell_guard_via_default_enabled
        status: pass
      - kind: other
        ref: "python -c GATES-OK from 14-03 Task 2"
        status: pass
    human_judgment: false
  - id: D3
    description: Missing or refusing confirmation produces no instructions; confirming produces them
    requirement: D-05
    verification:
      - kind: unit
        ref: tests/test_post_install.py#test_login_shell_skips_when_confirm_callback_is_none
        status: pass
      - kind: unit
        ref: tests/test_post_install.py#test_login_shell_skips_when_confirm_returns_false
        status: pass
      - kind: unit
        ref: tests/test_post_install.py#test_run_post_install_returns_chsh_instructions_when_confirmed
        status: pass
    human_judgment: false
  - id: D4
    description: Already-installed and manual-required paths never dispatch; a raising callback degrades to a named warning
    requirement: D-06
    verification:
      - kind: unit
        ref: tests/test_engine.py#test_already_installed_login_shell_never_invokes_confirm
        status: pass
      - kind: unit
        ref: tests/test_engine.py#test_manual_required_login_shell_never_invokes_confirm
        status: pass
      - kind: unit
        ref: tests/test_engine.py#test_raising_confirm_degrades_to_named_warning_not_a_crash
        status: pass
    human_judgment: false
  - id: D5
    description: Exactly one registry tool declares post_install; the two closed tables are disjoint; the one entry is sensitive
    requirement: D-07
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_only_oh_my_zsh_declares_a_post_install_action
        status: pass
      - kind: unit
        ref: tests/test_post_install.py#test_post_install_tables_are_disjoint_and_match_their_schema_sets
        status: pass
      - kind: other
        ref: "python -c TABLES-OK/ONE-DECLARER from 14-03 Task 3"
        status: pass
    human_judgment: false

duration: 19 min
completed: 2026-09-14
status: complete
---

# Phase 14 Plan 03: set_login_shell Dispatcher Summary

**Closed, execution-free `set_login_shell` dispatch: oh-my-zsh declares it, atomic hosts are never asked, unattended runs skip, and the installer shows `chsh -s $(which zsh)` instead of running it.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-09-14T16:08:15Z
- **Completed:** 2026-09-14T16:27:55Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `installer/post_install.py` is a closed, execution-free dispatch table with one `set_login_shell` entry that returns a fixed literal instruction tuple.
- `install_tool` dispatches declared `post_install` actions after a successful method, carrying reviewed lines on `InstallOutcome.post_install_handoff`.
- The real `oh-my-zsh` registry entry declares `post_install = ["set_login_shell"]` with its `CHSH=no` install-script guard left byte-identical.
- Nine gate facts are locked: immutable not-asked/not-run (including default-enabled), missing/refusing callback, confirming callback, unknown name, already-installed, manual-required, and raising-callback warning.
- The two similarly-named tables are proved disjoint; exactly one registry tool declares a post-install action.

## Task Commits

1. **Task 1: end-to-end dispatcher** - `71eaa82` (feat)
2. **Task 2: full gate matrix** - `5e8264a` (test)
3. **Task 3: one declarer and disjoint tables** - `425f5f3` (test)

## Files Created/Modified

- `installer/post_install.py` - Closed `POST_INSTALL_HOOKS` table, `run_post_install`, `set_login_shell` gates
- `installer/engine.py` - `InstallOutcome.post_install_handoff`, keyword-only `confirm_sensitive_action`, post-success dispatch
- `installer/registry.toml` - `oh-my-zsh` `post_install = ["set_login_shell"]`
- `tests/test_post_install.py` - Dispatcher, gate matrix, table-integrity tests
- `tests/test_engine.py` - End-to-end login-shell dispatch and never-dispatch paths
- `tests/test_registry.py` - One-declarer integrity test

## Decisions Made

- **D-04 first, unconditional.** `Platform.immutable` returns before the confirmation callback is consulted, so an atomic host is never even asked. Relaxing this later for a specific atomic variant would require re-verifying ublue-os/bazzite#4159, which has no maintainer root-cause analysis (14-RESEARCH.md Assumption A2). Conservative direction (block) implemented; this is the one-way checkpoint.
- **D-05 explicit yes or nothing.** `confirm is None` is the unattended case and skips. A registry `default_enabled_sensitive_actions` declaration cannot bypass the gate because the action never reads that field.
- **D-06 post-success only.** Dispatch sits after the singular `postinstall` hook and before the INSTALLED outcome. Already-installed and manual-required returns never reach it. A host that already has oh-my-zsh is never offered the action; that is the intended single-direction trigger, not a gap. A user who wants it after the fact runs the reviewed command themselves.
- **D-07 zsh only.** One action, one tool, no shell parameter. A second declarer is a failing registry test, not a widening of the table.
- **Reviewed handoff, not in-process `chsh`.** Follows `installer/host_setup.py`. The command is a fixed literal (`chsh -s $(which zsh)`); nothing is interpolated from Python, the registry, or a probe. `App.suspend()` remains a recorded follow-up idea, not built here.
- **`Install` protocol unchanged.** `confirm_sensitive_action` is keyword-only with default `None` on `install_tool` only, so every fake install and `attributed_install` keep compiling.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 14-04: console confirm callback (`with_sensitive_confirm`) and `render_post_install_handoff`.
- `InstallOutcome.post_install_handoff` is populated but unread by render/TUI until those plans wire it.
- `installer/postinstall.py` and the oh-my-zsh `CHSH=no` env setting are untouched.

## Self-Check: PASSED

- `installer/post_install.py` exists on disk.
- `git log --oneline --all --grep="14-03"` returns 3 commits.
- Plan-level verification: `pytest tests/test_post_install.py tests/test_engine.py tests/test_registry.py tests/test_model.py tests/test_postinstall.py -q` green; `-k login_shell` selected 4 tests and passed; `make validate` 0 errors; `make test` 2052 passed, 1 skipped, coverage 95.37%.
- `git diff --stat 71eaa82^..HEAD` lists only the six declared files.

---
*Phase: 14-install-update-engine-correctness-default-shell-action-selec*
*Completed: 2026-09-14*
