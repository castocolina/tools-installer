---
created: 2026-11-03T21:00:00.000Z
title: Fix 80x20 layout gaps found by the Phase 21 TUI check
area: tui
severity: minor
files:
  - installer/wizard_app.py
  - installer/ui_common.py
  - installer/catalog_tui.py
  - tests/test_layout_80x20.py
---

## Problem

The Phase 21 close-out tmux check (real `setup.py`, 80x20, NO_COLOR, scratch HOME) found five layout and
copy gaps. Each renders the same at 390f464, before Phase 21, so none was introduced by it
(evidence in `.planning/phases/21-one-screen-family/21-REVIEW-FIX.md`, RR round):

1. The tab bar is clipped at 80 columns: the last tab reads `[6] Policie` (`[6] Polic` on Doctor, where the
   screen scrollbar takes columns 78-79).
2. Doctor scrolls as one screen: the tab bar and mode badge scroll off with the card, the scrollbar covers
   all 20 rows including the footer, nothing has focus, and the keyboard (`down`, `pagedown`, `end`) cannot
   scroll it; only the mouse wheel can.
3. The Uninstall mode badge is cut: `enter removes marked items (you'll`.
4. System tier columns are cut: `Owne`, `OS p`.
5. Doctor prints `Press r to reinstall the pnpm-managed global set.` right under
   `pnpm's global set could not be read (pnpm missing, or the query failed).`, which contradicts it.
6. Policies shows one policy row at a time at 80x20 (the detail pane takes the rest), and a three-line
   status after a toggle shrinks the table to its header row, so the new `● [on]` is hidden until the
   status clears (Phase 21 round 3 pilot: identical output at 390f464).

## Solution

Make the Doctor card its own focusable scroll container under fixed chrome (header, badge, status, footer),
shorten or wrap the tab labels and the Uninstall badge to fit 80 columns, let the System table shrink its
Owner/OS columns at 80 columns, and show the reinstall hint only when the global set was read. Pin each with
an 80x20 backstop in `tests/test_layout_80x20.py`.
