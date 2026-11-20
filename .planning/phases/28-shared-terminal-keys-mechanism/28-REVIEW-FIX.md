---
phase: 28-shared-terminal-keys-mechanism
fixed_at: 2026-11-20T14:10:00Z
review_path: .planning/phases/28-shared-terminal-keys-mechanism/28-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 28: Code Review Fix Report

**Fixed at:** 2026-11-20
**Source review:** `.planning/phases/28-shared-terminal-keys-mechanism/28-REVIEW.md`
**Iteration:** 1
**Executor:** `pi -p --model router-env/my-coding-lite --no-session`, exit 0, 10 minutes (10:56 to 11:07), stderr empty, two commits.

**Scope decision (orchestrator):** the review found 0 critical findings, 2 warnings and 7 info items. Both warnings were reproduced or read in code by the orchestrator and fixed. The info items were not fixed here; see "Not fixed".

## Fixed Issues

| Finding | Status | Commit | What changed |
|---|---|---|---|
| WR-01 | fixed | `d20fb404` | When every chord conflicts, a reconfigure of a recorded install now writes an empty owned marker pair instead of removing the region, so a chord the user frees later is managed again. Pending-check uses the same empty body only when a region is already present. Tests: the full sequence ends with Alt+Left managed again, a second reconfigure while all chords stay user-bound is a no-op, and uninstall strips the empty pair. |
| WR-02 | fixed | `ddc89888` | The zsh widget binds `^L` in the emacs, viins and vicmd keymaps only where the current binding is `clear-screen`, `undefined-key` or empty, using a loop variable that is unset afterwards. Tests run a non-interactive `zsh -f` script: a user's own `^L` binding survives while the other keymaps get the widget, and a default keymap gets the widget in all three. |

## Not fixed (out of this pass)

- **IN-01** (single-shell mode with bash never sources `~/.myshellrc`, yet the zsh row reads tuned): deferred to backlog 999.28. It predates this phase and affects every shell-init bundle.
- **IN-02, IN-03, IN-04** (hardcoded created-marker filename, a no-op wrapper, a duplicated drift check): deferred to backlog 999.28; tidiness only, and IN-02 would need a new import that risks a cycle between `terminal_shell` and `terminal_keys`.
- **IN-07** (the `Writes` path no row uses yet): deferred to phase 29, whose first `Writes` row will exercise it; recorded in backlog 999.28.
- **IN-05, IN-06** (necessity: the no-row branches and the outer `command -v zsh` guard): rejected. Plan 28-02 asked for the backstop on purpose (the completeness test blocks it only at push), and plan 28-04 asked for the outer guard.

## Verification

Reported by the executor: the targeted run passed; `make validate` passed all six gates; `make test` passed with 7,924 passed, 6 skipped and 96.24% coverage.

Checked by the orchestrator:
- I read both commits' production diffs: five changed lines in `terminal_keys.py` and ten in `tweaks.py`, matching the intent.
- The only deleted test lines are the three per-keymap widget-text assertions that this phase itself added in plan 28-04; no pre-existing test was edited.
- I re-ran the reviewer's WR-01 script against the fixed code: the region is kept, status reads pending once a chord is freed, reconfigure restores it, and `Alt+Left managed again: True` (it was False before).
- I ran the new widget logic in a real `zsh -f` script: with a user-defined `^L` in the emacs keymap that binding survives, and viins and vicmd get `tools_installer_clear_all`.
- I read the pending-check function: the empty-body rule sits inside the `if present:` branch only, so a fresh install where the user already binds every chord does not read pending forever.
- The seven-file targeted run passes.
