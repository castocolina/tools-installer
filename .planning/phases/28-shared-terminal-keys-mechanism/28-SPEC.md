# Phase 28: Shared terminal-keys mechanism — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.15 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Alacritty's owned keys region moves out of `installer/terminal_shell.py` into one shared mechanism, keyed by registry tool id, that applies, checks, re-applies and strips a terminal's keys region the same way for every terminal, and the installer's managed zsh configuration makes Ctrl+L clear the screen and the scrollback.

## Background

- The Alacritty keys code lives in `installer/terminal_shell.py` (`_KEY_BINDINGS` at :478-482, `apply_alacritty_keys` :671, `alacritty_keys_pending` :710, `strip_alacritty` :726). Its Linux Alt+Left/Right rows send `\u001bb` / `\u001bf`; its Ctrl+Shift+K row is `action = "ClearHistory"` (scrollback only).
- Three dispatch sites branch on the Alacritty id or its tuning: `installer/post_install.py:387` (`apply_alacritty_keys` inside `_apply_terminal_tuning`), `installer/version_status.py:783-826` (`_terminal_tuning_fact`, `alacritty_keys_pending`) and `installer/app.py:630` (`if tool.id == "alacritty": strip_alacritty(...)`).
- Only Alacritty has `post_install = ["apply_terminal_tuning"]` in `installer/registry.toml`; kitty, wezterm and herdr have none.
- The installer's managed zsh configuration is `~/.myshellrc` written through `installer/shellrc.py` and the shell-init bundles (`SHELL_INIT_TOOLS`); no `bindkey` or clear widget exists in `installer/` today.
- Konsole is handled by `_sync_konsole` (zsh sync only) and stays outside this mechanism (roadmap note).
- CI runs `validate & test` on `ubuntu-latest` and `macos-latest` (`.github/workflows/ci.yml`).
- Reconciliation locked in the interview: KEYS-03's "maps the clear chord to Ctrl+L for every row" is the mechanism's generic rule, proved on a fixture row; Alacritty's own clear action stays `ClearHistory` until phase 29 (TERM-03) flips it, so criterion 1 (byte-identical) and criterion 3 do not conflict.

## Requirements

1. **Alacritty moves into the shared mechanism (KEYS-01)**: One module `installer/terminal_keys.py` holds a table of rows keyed by registry tool id; each row applies, checks and strips that terminal's owned keys region. Alacritty is the first and only row, and its behavior and tests are unchanged.
   - Current: the code is Alacritty-specific inside `terminal_shell.py`; three sites branch on the id.
   - Target: the three dispatch sites call the table by tool id; none contains the Alacritty id literal for key handling.
   - Acceptance: the file written for Alacritty in a scratch HOME is byte-identical before and after the move (golden bytes captured from the pre-move code); the existing Alacritty tests pass with no assertion edits; `rg 'alacritty'` over `post_install.py`, `version_status.py` and `app.py` finds no key-handling branch.

2. **Pending, re-apply and strip for every row (KEYS-02)**: For every row of the mechanism, a missing or drifted keys region makes the tool's row read `≈ apply install tuning` *(amended 2026-11-19, 28 D-06, needs confirmation: "missing" means never applied (no record and no region); "drifted" means a region is present with bytes that differ from the current render; a region the user deleted after a recorded install stays the user's choice)*, a reconfigure re-applies the region, and an uninstall strips it with the tool. A test fails when a registry tool that declares `apply_terminal_tuning` has no mechanism row.
   - Current: only Alacritty is covered, by Alacritty-only code.
   - Target: the three behaviors run through the table; the registry-to-table completeness test exists.
   - Acceptance: in a scratch HOME, deleting the region shows `≈ apply install tuning`, reconfigure restores the bytes, uninstall removes the region (and the file when the installer created it, as today); the completeness test fails against a fixture registry with an extra `apply_terminal_tuning` tool and no row.

3. **One clear shortcut everywhere (KEYS-03)**: The mechanism maps the clear chord to Ctrl+L for every row (Cmd+K on macOS, Ctrl+Shift+K on Linux), and the installer's managed zsh configuration makes Ctrl+L at the prompt clear the visible screen and the scrollback, in every zsh session that sources that configuration, on both OSes.
   - Current: no zsh widget; Alacritty's chord is a scrollback-only action.
   - Target: a managed zsh widget bound to Ctrl+L emits clear-screen plus scrollback erase; the mechanism's row type carries the clear chord as "send Ctrl+L" by default.
   - Acceptance: a byte-level test of the emitted widget text asserts the screen-clear and scrollback-erase sequences; a fixture row (not Alacritty) shows the generic clear chord resolving to Ctrl+L on each OS; the widget is removed with the managed configuration.

4. **Same-directory declaration per row (KEYS-04)**: Every mechanism row declares whether the vendor already opens a new tab, window or pane in the current directory; the installer writes the setting only for rows where it does not.
   - Current: no such declaration exists.
   - Target: a required field on every row.
   - Acceptance: a test fails when a row leaves the field undeclared; a fixture row that declares "vendor does it" has no setting written, and one that declares "installer writes" gets the setting.

5. **Konsole stays outside (roadmap note)**: Konsole has no row in the mechanism and its zsh sync behaves exactly as before.
   - Current: `_sync_konsole` and `_revert_konsole` exist in `terminal_shell.py`.
   - Target: untouched by the move.
   - Acceptance: the existing Konsole tests pass with no assertion edits; the mechanism table has no `konsole` key.

## Boundaries

**In scope:**
- `installer/terminal_keys.py` and the table-driven dispatch in `post_install.py`, `version_status.py`, `app.py`.
- The managed zsh Ctrl+L widget and its byte-level test.
- The completeness and same-directory-declaration tests.

**Out of scope:**
- Changing Alacritty's clear action to screen plus scrollback — phase 29 (TERM-03).
- kitty, WezTerm, Konsole and herdr rows — phase 29; Ghostty, iTerm2 and the Herdr desktop app — phases 30-31.
- Any macOS-only runtime check on a real Mac — UAT line deferred to the owner's Mac.
- Changing the user-visible wording of `≈ apply install tuning` or its reconfigure step.

## Constraints

- Behavior-preserving for Alacritty: golden bytes, no assertion edits in existing tests.
- Tests use a scratch HOME; no run touches the real `~/.myshellrc` or any real terminal config.
- The widget text must work in zsh on macOS and Linux; `shellcheck` and the other commit gates stay green.
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] Alacritty's written file is byte-identical to the pre-move golden bytes in a scratch HOME.
- [ ] Existing Alacritty and Konsole tests pass with no assertion edits.
- [ ] `post_install.py`, `version_status.py` and `app.py` contain no Alacritty-id branch for key handling.
- [ ] Pending read, reconfigure and uninstall pass through the table in a scratch HOME.
- [ ] A test fails when an `apply_terminal_tuning` registry tool has no row (fixture proof).
- [ ] The zsh widget text carries the screen-clear and scrollback-erase sequences (byte-level test).
- [ ] A fixture row resolves the clear chord to Ctrl+L on both OSes.
- [ ] A test fails when a row leaves the same-directory field undeclared.
- [ ] The mechanism table has no Konsole key.

## Edge Coverage

**Coverage:** 18/19 applicable edges resolved · 1 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1 and the Prohibitions row: a user binding beside the owned region survives apply and strip (fixture with adjacent user bindings) |
| empty | R1 | ✅ covered | Acceptance 4: a missing config file and an empty one are covered by the existing Alacritty created-file tests, which must pass unedited |
| ordering | R1 | ✅ covered | Acceptance 1: golden bytes fix the binding order; the table lookup is by id, never by position |
| concurrency | R1 | 🧪 backstop | held-out test: two interleaved applies in a scratch HOME leave one region, because the write goes through the existing atomic _write_if_changed |
| adjacency | R2 | ✅ covered | Acceptance 4: the region next to user content is restored without touching it (reconfigure fixture) |
| empty | R2 | ✅ covered | Acceptance 5: the completeness test fails on an empty table against a registry that declares apply_terminal_tuning |
| ordering | R2 | ✅ covered | the completeness test compares id sets, so table order never matters (shuffled-table fixture) |
| idempotency | R2 | ✅ covered | Acceptance 4: a second reconfigure leaves the bytes unchanged (apply twice equals apply once) |
| concurrency | R2 | 🧪 backstop | held-out test: reconfigure racing an uninstall in a scratch HOME ends with no region and no error |
| boundary | R3 | ✅ covered | Acceptance 6 and 7: both OSes covered by the fixture row (Cmd+K macOS, Ctrl+Shift+K Linux), plus a scrollback-erase boundary in the widget bytes |
| adjacency | R3 | ✅ covered | Prohibitions row 2: the widget sits inside its own marker block next to user lines; apply then strip removes the whole block and leaves every user line untouched *(amended 2026-11-20, needs confirmation: apply then strip returns the original with its trailing newlines removed, followed by one blank line when anything is left and the empty string otherwise, because `shellrc.strip_block` keeps a separator line by design; the test pins eight input and output pairs; real fix tracked in backlog 999.27)* |
| empty | R3 | ✅ covered | Acceptance 6: a managed config with no widget (before apply) differs from one with it; an empty rc file gets the block |
| encoding | R3 | ✅ covered | Acceptance 6: the byte-level test asserts the exact escape bytes (ESC [ H, ESC [ 2 J, ESC [ 3 J) as bytes, not rendered text |
| ordering | R3 | ✅ covered | Acceptance 6: the widget emits the scrollback erase and the screen clear in one fixed order asserted by bytes |
| precision | R3 | 🧪 backstop | held-out test: the widget works for a prompt line of any length (no row arithmetic); asserted at the sequence level |
| adjacency | R4 | ✅ covered | Acceptance 8: a row declaring vendor-does-it has nothing written; one declaring installer-writes gets exactly one setting |
| empty | R4 | ✅ covered | Acceptance 8: an undeclared field fails the test (empty is never a pass) |
| ordering | R4 | ✅ covered | the declaration is a per-row field, independent of row order |
| unclassified | R5 | ⚠ UNRESOLVED | ⚠ Edge unresolved — planner must treat as assumption |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The mechanism MUST NOT overwrite or remove a keys binding outside its owned region (user bindings are never touched) | 1 | resolved | test: existing Alacritty tests plus a fixture with user bindings beside the region |
| The zsh widget MUST NOT run or write outside the managed configuration block, and MUST NOT remain after the block is removed | 3 | resolved | test: scratch-HOME apply then strip removes the block and leaves every user line untouched, with the separator blank line `shellrc.strip_block` keeps by design pinned exactly *(amended 2026-11-20, needs confirmation; see backlog 999.27)* |
| The mechanism MUST NOT enable the global Option-as-Alt switch on any row | 3 | resolved | judgment (the row type has no such field; reviewed at verify) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Roadmap criteria plus verified code anchors |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Alacritty clear change explicitly deferred to 29 |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Widget text shape left to discuss |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | Each criterion is a byte or fixture test |
| **Ambiguity**      | 0.15  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The open items went through jev: one advisory answer per item, and `needs_fallback` items are decided by own reasoning. Summaries only, advisory. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Boundary Keeper | Byte-identical Alacritty region vs "Ctrl+L for every row": how to reconcile? | low 0.48 (none_of_these); second rung choice keep_legacy_until_later_phase 0.99 | The mechanism owns the generic Ctrl+L rule, proved on a fixture row; Alacritty keeps `ClearHistory` until phase 29 (R1, R3) |
| 1 | Researcher | Does the zsh clear widget apply in every zsh session that sources the managed config? | noul yes 0.97 | Yes, both OSes, whichever terminal runs (R3; owner wants one universal clear) |

---

*Phase: 28-shared-terminal-keys-mechanism*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 28 — implementation decisions (how to build what's specified above)*
