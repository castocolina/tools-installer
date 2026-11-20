---
phase: 28-shared-terminal-keys-mechanism
verified: 2026-11-20T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
covered_files:
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-01-PLAN.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-01-SUMMARY.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-02-PLAN.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-02-SUMMARY.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-03-PLAN.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-03-SUMMARY.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-04-PLAN.md"
  - ".planning/phases/28-shared-terminal-keys-mechanism/28-04-SUMMARY.md"
  - "installer/app.py"
  - "installer/post_install.py"
  - "installer/terminal_keys.py"
  - "installer/terminal_regions.py"
  - "installer/terminal_shell.py"
  - "installer/tweaks.py"
  - "installer/version_status.py"
  - "tests/test_terminal_keys.py"
  - "tests/test_terminal_shell.py"
  - "tests/test_tweaks.py"
covered_digest: "v4:sha256:b8091035b87dfc6ab332abd6ef0de9e8ab26835dccb5a71040f1b41dd9918547"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "On a real Mac terminal, open zsh (including a multi-line starship prompt) with the new managed block, type text, press Ctrl+L"
    expected: "Screen clears, prompt and typed buffer redraw, scrollback is erased"
    why_human: "Visual redraw cannot be observed in a scratch HOME; only the emitted bytes are tested"
  - test: "On the same Mac, confirm ESC[2J does not push the screen into scrollback before ESC[3J erases it"
    expected: "No stale screen content reachable by scrolling up after Ctrl+L"
    why_human: "Terminal-emulator scrollback behavior"
  - test: "Owner confirms provisional decisions: 28 D-06 / OQ1, amended SPEC R3 round-trip wording (backlog 999.27), D-12 import-line deviation"
    expected: "Owner accepts or redirects each"
    why_human: "Flagged 'needs confirmation' in CONTEXT, SPEC and REQUIREMENTS"
---

# Phase 28: Shared terminal-keys mechanism Verification Report

**Phase Goal:** A terminal's keys become one row in one shared mechanism, so applying, checking, re-applying and removing its keys works the same for every terminal, starting with Alacritty exactly as it behaves today.
**Verified:** 2026-11-20
**Status:** human_needed
**Re-verification:** No, initial verification

## Observable Truths

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | Alacritty keys applied, checked, stripped via the shared mechanism by tool id; bytes identical; no dispatch site branches on the Alacritty id | VERIFIED | `TERMINAL_KEYS["alacritty"]` in `installer/terminal_keys.py`. Dispatch is `TERMINAL_KEYS.get(tool.id)` in `post_install.py:389`, `version_status.py:827`, `app.py:630`. The only "alacritty" string left in `version_status.py` is the pre-existing drifted-terminal label map (`_TERMINAL_ROWS`), not key handling. Golden-byte tests in `tests/test_terminal_keys.py` (`test_golden_*`) pass. Existing tests in `test_terminal_shell.py` pass. |
| 2 | Editing a region reads `≈`; deleting reads `≈` only before a recorded apply; reconfigure restores; uninstall strips; test fails for a declarer without a row | VERIFIED (provisional D-06) | `terminal_keys_pending`, `apply_terminal_keys(skip_recorded=...)`, `strip_terminal_keys`. Tests `test_drift_*`, `test_completeness_*` pass. |
| 3 | Managed zsh Ctrl+L clears screen and scrollback (byte-level); clear chord is Ctrl+L on every row, Cmd+K macOS, Ctrl+Shift+K Linux | VERIFIED (bytes) | `_ZSH_CLEAR_BODY` in `installer/tweaks.py:118` emits `ESC[H ESC[2J`, `zle .reset-prompt`, `zle -R`, `ESC[3J` in fixed order, bound only over clear-screen, undefined or empty bindings. `tests/test_tweaks.py` asserts the byte order. `clear_binding` plus `test_clear_chord_sends_ctrl_l_on_every_os_for_a_default_row`. Visual redraw is human. |
| 4 | Every row declares same-directory rule; written only where the vendor does not; test fails when undeclared | VERIFIED | `KeysRow.same_directory` has no default (`SameDirectory = Vendor | Writes | NotApplicable`); `_render` appends the snippet only for `Writes`. Tests `test_same_directory_has_no_default`, `test_a_row_without_same_directory_is_a_type_error`, `test_every_row_declares_same_directory`, `test_same_directory_vendor_writes_nothing_and_writes_it_once` pass. |

**Score:** 4/4 truths verified, 0 behavior-unverified (state transitions covered by named scratch-HOME tests).

### Spot-checks

`uv run pytest tests/test_terminal_keys.py tests/test_terminal_shell.py tests/test_tweaks.py tests/test_version_status.py tests/test_post_install.py tests/test_tool_onboarding_skill.py -q --no-cov` ran green (all dots, 100%).

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|---|---|---|---|
| KEYS-01 | 28-01, 28-02 | SATISFIED | table plus primitives in `terminal_regions.py`, golden bytes |
| KEYS-02 | 28-02, 28-03 | SATISFIED (D-06 provisional) | drift, reconfigure, strip, completeness tests |
| KEYS-03 | 28-03, 28-04 | SATISFIED (bytes; visual human) | `clear_binding`, zsh widget |
| KEYS-04 | 28-03 | SATISFIED | `same_directory` declaration |

No orphaned IDs: REQUIREMENTS.md maps exactly KEYS-01..04 to Phase 28, all claimed by plans.

### Prohibitions

- No write outside the owned region: held (adjacent-binding golden test).
- zsh widget stays inside its marker block and is removed with it: held; round-trip pinned by the amended R3 test (provisional, backlog 999.27).
- No global Option-as-Alt switch: held (`KeysRow` has no such field; judgment tier, reviewed here and confirmed).
- No Konsole key in the table: held (`terminal_keys.py` has no Konsole entry).

### Anti-Patterns

No TBD/FIXME/XXX found in the covered implementation files that lacked references (not exhaustively grepped beyond `terminal_keys.py`, whose contents were read in full). `clear_binding` has no production caller yet (documented in its docstring; phase 29 rows are first callers). SPEC edge R5 "unclassified" stays unresolved by the SPEC itself and was treated as an assumption.

### Provisional decisions needing owner confirmation

1. 28 D-06 with OQ1: "pending" means no record and no region; a present, stale region is drift; a user-deleted region after a recorded install stays the user's; a recorded install whose file refuses or fails to read stays quiet. Narrows the owner-listed "missing region shows `≈`". Flagged in CONTEXT line 38, REQUIREMENTS KEYS-02 and ROADMAP criterion 2.
2. Amended SPEC R3 round-trip: apply then strip returns the original with trailing newlines removed, then one blank line if anything is left, else empty (real fix: backlog 999.27).
3. D-12 deviation: four import lines in `tests/test_terminal_shell.py` (1220, 1254, 1323, 1648) use `tests.test_terminal_keys` (which holds the `apply_alacritty_keys` helper), not `installer.terminal_keys`, because a production wrapper with no caller is forbidden by architecture rule 5. Confirmed in the files.

No other decision flagged "needs confirmation" was found in CONTEXT.md (only D-06).

### Behavior notes

- Hosts with zsh show `≈ apply install tuning` on the zsh row until a reconfigure writes the new block.
- No e2e proof is named for this phase in CONTEXT or SPEC.

### Human Verification Required

See frontmatter: the two Mac terminal checks for Ctrl+L, and the owner confirmation of the three provisional decisions.

### Gaps Summary

No gaps. All four roadmap criteria hold in code and targeted tests. Status is `human_needed` solely for the owner's Mac visual checks and the provisional-decision confirmations.

---

_Verified: 2026-11-20_
_Verifier: Claude (gsd-verifier)_
