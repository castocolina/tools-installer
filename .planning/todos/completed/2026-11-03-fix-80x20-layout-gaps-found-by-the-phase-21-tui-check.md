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

7. (Real-TTY UAT 2026-11-07, `.planning/uat/2026-11-07-real-tty.md` F-2/F-3) The bottom key-hint line is cut at 80
   columns on the System/User/AI and Uninstall screens, so `q quit` / `esc back` never show; the detail bar cuts the
   `to configure:` step (only the install review shows it); the removal confirm box scrolls and its last line
   (`puppeteer included.`) appears only after pressing down; the Policies `Effect` column is cut short.

## Solution

Make the Doctor card its own focusable scroll container under fixed chrome (header, badge, status, footer),
shorten or wrap the tab labels and the Uninstall badge to fit 80 columns, let the System table shrink its
Owner/OS columns at 80 columns, and show the reinstall hint only when the global set was read. Pin each with
an 80x20 backstop in `tests/test_layout_80x20.py`.

## Resolved

Resolved 2026-11-15: gaps 1, 2, 3, 5 and the footer part of 7 in d3bd30c1, gap 6 in 37b3916a, gap 4 in 81ef77e4 (each pinned in tests/test_layout_80x20.py). The other clauses of 7 (detail bar `to configure:`, removal confirm scroll, Policies Effect) were not seen in the 2026-11-15 captures; the confirm scroll is already pinned by test_a_long_review_scrolls_and_keeps_its_keys_line.

## Visual acceptance 2026-11-15

Agent-run at HEAD c76a9e2b: Fedora 44 container `ti-uat-80x20-fedora` (`--init`, user tester, tree from `git archive HEAD`), real `setup.py` inside tmux at exactly 80x20, `NO_COLOR=1`, fresh HOME. One wide capture came from the herdr pane itself (about 250x69). Captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/`. Before captures: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/`. The jev ladder answered one `choice` item per finding (summaries only; Laya never reached the confidence floor, TypeSafe decided under the standing consent of 2026-10-14). jev is advisory; each verdict below is the agent's own, and the two overrides are named.

| Gap | Verdict | Evidence |
| --- | --- | --- |
| 1 Tab bar clipped | **Partly fixed**. Whole on all seven views at rest. Cut again to `[7] Schedul` on Policies after a toggle (finding R1) | whole: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/00-start-system.txt`, `02-user.txt`, `04-doctor-top.txt`, `05-uninstall.txt`, `06-policies.txt`, `07-schedules.txt`; cut: `06c-policies-after-toggle.txt`, `06e-policies-toggle-repro.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/03-doctor.txt` |
| 2 Doctor scroll | **Fixed**. Tab bar, badge and footer stay put; the card scrolls with down, pagedown, end and returns on home; no scrollbar over the footer | `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/04-doctor-top.txt`, `04b-doctor-down.txt`, `04c-doctor-pagedown.txt`, `04d-doctor-end.txt`, `04e-doctor-home.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/03-doctor.txt` |
| 3 Uninstall badge | **Fixed**. Reads `space marks; enter removes them (you'll confirm)`; the table header's last column ends in an ellipsis (`What gets …`), cells are whole | `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/05-uninstall.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/02-uninstall.txt` |
| 4 System columns | **Fixed**. `Ver`, `Owner` and `Health` whole (`dnf`, `1990-2008`); only `What it does` is shortened, with an ellipsis | `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/01-system-enter-status.txt`, `02-user.txt`, `03-ai.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/01-system.txt` |
| 5 Reinstall hint | **Fixed**. `pnpm's global set could not be read` is no longer followed by `Press r to reinstall`. The footer keeps `r reinstall globals`; pressing `r` then re-reads pnpm (wizard_app.py `action_reinstall_globals`), so the key is valid | `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/04c-doctor-pagedown.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/03-doctor.txt` |
| 6 Policies rows | **Fixed for its own claim, with a residual (R1)**. Five rows at once; after a toggle `● [on]` shows without re-entering. A real toggle's status is longer than the pinned four rows, which overflows the screen | `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/06-policies.txt`, `06c-policies-after-toggle.txt`, `06d-policies-after-toggle-8s.txt`, `06h-policies-toggle-off-again.txt`; wide: `09b-wide-policies.txt`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/04-policies.txt`, `05-policies-after-toggle.txt` |
| 7 Footer and detail | **Footer fixed**; the other clauses are partly open (R3, R4). `1-7 views \| ^p nav \| esc back \| q quit` is whole on every view | footer: every capture in `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/`; before: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/21-reverify/t80/01-system.txt`, `02-uninstall.txt` |

### Findings

- **R1, open-real (jev: open-real 1.0, agreed).** After one real policy toggle at 80x20 the whole Policies screen scrolls as one block: a screen scrollbar takes columns 78-79, so the tab bar is cut to `[7] Schedul` (gap 1 again), the footer row carries `▇▇`, and `End` scrolls the policy table fully out of view. The status stays after 8 s. Evidence: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/06c-policies-after-toggle.txt`, `06d-policies-after-toggle-8s.txt`, `06e-policies-toggle-repro.txt`, `06f-policies-toggle-end.txt`. Cause: `test_policies_keep_their_rows_and_the_toggled_state_at_80x20` pins a four-row status, but the real Countdown helper toggle yields a longer one (a line per layer plus a wrapped reload hint). Reproduction: fresh HOME, 80x20, open the wizard, press `6`, `Down`, `space` (toggle Countdown helper), wait 5 s, read the screen; press `End`.
- **R2, resolved (jev: resolved 0.98 for the tab bar at rest).** Gaps 2 to 5 and the resting tab bar need nothing more.
- **R3, open-trivial (jev: open-real 0.9; agent override, wide size shows the full text and nothing is lost to a keypress).** At 80 columns the Policies `Effect` column is hard cut at the table edge with no ellipsis; the Schedules detail text ends mid-sentence with no ellipsis; the System and Uninstall detail bars end in `…`. Evidence: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/06-policies.txt`, `07-schedules.txt`, `05-uninstall.txt`.
- **R4, open-trivial (jev: open-real 0.46, below the floor; agent decided).** Footers drop actions right to left to keep the global nav whole, so `a all | i invert | u update` (System, User, AI) and `i invert | c config` (Uninstall) are not advertised at 80 columns although the keys work. The drop order is by design (`ui_common.py`), so this is a discoverability trade-off, not a cut. Evidence: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/01-system-enter-status.txt`, `05-uninstall.txt`.
- **Not re-captured.** The removal confirm box (gap 7, clause 3) needs an installed removable tool; the fresh container had none (`nothing to do (80)`), so `space` on a marked row was inert (`/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/05b-uninstall-marked.txt`). Its scroll stays pinned by `test_a_long_review_scrolls_and_keeps_its_keys_line`; `tests/test_layout_80x20.py` passes at HEAD.
- **Owner-only:** none.

Other note: a fresh HOME opens the link-mode modal over the System table first (`/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/uat/80x20-after/00-start-system.txt`); it covers the table until answered. That is first-run behavior, not a layout gap.
