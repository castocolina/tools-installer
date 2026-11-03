---
phase: 21-one-screen-family
fixed_at: 2026-11-03
review_path: .planning/phases/21-one-screen-family/21-REVIEW.md
iteration: 1
findings_in_scope: 34
fixed: 30
skipped: 0
status: all_fixed
---

# Phase 21: Code Review Fix Report

**Source review:** `21-REVIEW.md`, section "Consolidated findings (3 lanes, verified)", C-01..C-34.
**Lanes:**
- L1: gsd-code-reviewer, deep.
- L2: opencode router-env/my-referee-one.
- L3: ponytail-review.

**Fix loop:** batches A to F, `182e876..HEAD`, run in sequence on `main`. Each behavioral fix has a RED test commit followed by its fix commit.
**Gates:** `make validate` and `make test` ran in the main checkout, not a worktree. Both exited 0 on the tree of every fix commit.
**User decisions:** recorded in `.planning/RUN-LEDGER.md`, row "User decisions on review findings" (2026-11-03). Amendments to the locked documents are in CONTEXT, UI-SPEC and `.claude/architecture.md`, as each batch row notes.

fixed=30 by_design=1 backlog=3

| id | finding | lanes | status | commit(s) / reason / where recorded |
|----|---------|-------|--------|-------------------------------------|
| C-01 | macOS 15-min hang: unbounded `HeldRefreshService` wait | L1 WR-10 | fixed (batch A) | efe7b77 (RED), a3baa64, 020c15f (`faulthandler_timeout`, CI step timeout) |
| C-02 | Epoch-guard test passes only through its 5 s latch timeout | L1 WR-09 | fixed (batch A) | f5f3c38 |
| C-03 | 23 `test_setup.py` tests wait the full 5 s daemon-default timeout | L1 WR-10 | fixed (batch A) | 452a412 |
| C-04 | An unexpected pass exception writes no status | L1 WR-03, L2 R2-11 | fixed (batch B) | 5346cc0 (RED), 1963a5b |
| C-05 | A pending pass starts after shutdown begins | L2 R2-10 | fixed (batch B) | 7d01ccc (RED), 246926a |
| C-06 | The app state line overwrites a view's own status | L3 P4 | fixed (batch B) | ae6b20d (RED), 2eb5005 |
| C-07 | Widget queries on the shutdown path | L1 WR-05 | fixed (batch B) | cbd98f8 (RED), 838f8e5; 320ad60 (test settle for the CI race) |
| C-08 | A pass published under a modal is not rendered when it closes | L3 P3 | user decision, then fixed (batch B) | Ledger: re-render on `on_screen_resume`, D-06 amended. 28c8220 (RED), f577b45 |
| C-09 | Doctor smoke evidence never expires | L2 R2-1, L3 P2 | fixed (batch C) | 551a3ec (RED), 447a3fd |
| C-10 | Doctor prints healthy owner notes as findings | L1 IN-02, L3 P1 | fixed (batch C) | 744e1ee (RED), db9275f |
| C-11 | Doctor `enter` wires PATH after a failed preview read | L1 WR-04 | fixed (batch C) | 0849830 (RED), 8c1cba8 |
| C-12 | Unreachable "Run `make setup`" rewrite in Doctor | L2 R2-12 | fixed (batch C) | 612d9bc (refactor) |
| C-13 | `_audit_globals_worker` lacks `exit_on_error=False` and a `finally` post | L1 IN-05 | fixed (batch C) | c8e8ec2 (RED), 86e7195 |
| C-14 | A removal reports `removed` while a previewed path stays | L1 WR-02, L3 P6 | fixed (batch D) | 62d8b08 (RED), bbfe963 |
| C-15 | An `OSError` in `plan_removal` aborts the whole batch | L2 R2-6 | fixed (batch D) | 17fd185 (RED), 30be1fd |
| C-16 | A removed tool stays staged on the catalog tiers | L2 R2-8 | fixed (batch D) | fd9bcd8 (RED), 6b9943f |
| C-17 | Mutating keys open a modal before the lock refuses | L2 R2-9 | fixed (batches D, E) | Uninstall: a84b5f6 (RED), 1206200. Policies `t`/`m`: 2166ae4 (RED), c34be67 |
| C-18 | The first-run link pick bypasses the lock during the daemon apply | L1 WR-01 | fixed (batch E) | 2257ef6 (RED), dec878f |
| C-19 | An unreadable Linux daemon state reads `! [drift]` | L2 R2-3 | fixed (batch E) | 8196304 (RED), 15392e2 |
| C-20 | `UnicodeDecodeError` escapes `run_live` | L2 R2-4 | fixed (batch B) | 1c06709 (RED), 73b26c0 |
| C-21 | Policies blanks job rows on every publish | L3 P5 | fixed (batch E) | 00bd2dc (RED), 68b4a2d |
| C-22 | Overlapping timer-cache probes: an older answer can win | L2 R2-2 | backlog | Pre-existing mechanism, PARTIAL. Ledger "Phase 21 code review consolidated" row |
| C-23 | Installed-via wording; a shadowed installer copy reads `Homebrew` | L1 WR-08, ledger | user decision, then fixed (batch D) | Ledger: owner of the removable copy. f937ce3 (RED), f4aa3e2. Batch F confirmed nothing remains: removable rows read `installer` and the detail adds ` — active copy: {manager}` (UI-SPEC row 108). An installer-owned MANAGED row (unproven or script install) keeps its kind label by pinned design (`test_uninstall_script_install_shows_its_reasons_and_label`) |
| C-24 | A failed update never invalidates, so the next pass reuses pre-update data | L2 R2-5 | fixed (batch F) | 23c0f2f (RED), b6d3ee2 |
| C-25 | Quitting during a non-removal mutation drops its outcome; exit 0 | L1 WR-06 | user decision: backlog | Pre-existing. Ledger "User decisions" row; also batch D row (exit code after a cut removal) |
| C-26 | During a removal no key exits a wedged remover | L1 WR-07 | user decision, then fixed (batch D) | Ledger: a second ctrl+c forces exit, D-10 amended. c9ef1e1 (RED), a0940de |
| C-27 | Missing/unavailable rows hide `removable.yourself` leftovers | L2 R2-7 | user decision: backlog | Pre-existing. Ledger "User decisions" row |
| C-28 | Completion handlers write status on hidden views | L1 IN-06 | user decision, then fixed (batches B, D, E) | Ledger: write to the visible view. 61116a4 (RED), 102f87f. Uninstall copy: 6af15f1 (RED), 15904d6. Policies copy: 80081fe (RED), 79d332e |
| C-29 | `_managers_invalid` bypasses the manager backoff while saves fail | L1 IN-01 | by design | `test_failed_invalidate_save_still_requeries_the_managers` pins the cycle-3 re-query design. Ledger batch C row |
| C-30 | `begin_mutation` silently overwrites a held lock | L1 IN-07 | fixed (batch E) | 2e60736 (RED), 5ddeeab |
| C-31 | The catalog's "update already in flight" branch is unreachable | L3 P8 | fixed (batch F) | e9130c6 (refactor) |
| C-32 | "Retract only my own status line" hand-rolled four times | L3 P7 | fixed (batch B) | 2eb5005 (`StatusLine.retract`, with C-06) |
| C-33 | Stale comments after the rewrite | L1 IN-04 | fixed (batch F) | 364adf9 (refactor) |
| C-34 | `remove_failed` with an empty detail falls back to install wording | L1 IN-03 | fixed (batch F) | 343b879 (RED), 7058a0d |

## Batch F notes

- **C-24.** `UpdateService.run` now invalidates on `failed` as well as `updated`. The reason string is `update of {id} failed`. A failed invalidation still goes into the outcome detail. The pnpm pre-capture refusal returns earlier and changes nothing on the machine, so it still invalidates nothing.
- **C-31.** The update worker calls `UpdateService.end()` before it posts the `ToolUpdated` message that releases the app lock. The install run holds `INSTALL_RUN`. So `refuse_if_mutating` always refuses first, and `begin()` stays only as a bare guard. The parametrized `in_flight` case went too: it faked a busy service with no lock held, which cannot happen.
- **C-34.** The fallback is now `not removed` for `remove_failed` and stays `no method succeeded` for `failed`.

## RR round (re-review of the fix loop, iteration 2)

**Source:** `21-REVIEW.md`, section "Re-review of the fix loop (182e876..HEAD)", RR-01..RR-06, plus the layout and copy notes from the 2026-11-03 "Phase 21 tmux TUI check" ledger row. Each fix has a RED test commit followed by its fix commit. `make validate` and `make test` exited 0 on the tree of every fix commit; the last run passed 5233 tests (4 skipped). Gates ran in the main checkout, with no worktree.

| ID | Finding | Status | Commits |
|----|---------|--------|---------|
| RR-01 | Textual's inherited `ctrl+q` exits during a removal and abandons the daemon delete thread | fixed | b27b26c (RED), b10354d. `UnifiedApp.action_quit` routes to `action_abort`, so `ctrl+q` is the soft quit like `q`: it waits during a removal, a second `ctrl+q` still waits, and under the palette it does nothing. A second `ctrl+c` still forces the exit with the warning (D-10 as amended) |
| RR-02 | A queued state line drained by `show_view` or an install close is never retracted | fixed | d03c3b8 (RED), a21c0bd. Both drains share `_flush_pending_warnings`, which re-homes the queued line onto the view. `_state_line` now records what a retraction restores, so a warning drained beside the line stays |
| RR-03 | An unreachable user manager overwrites every Policies result on the next render | fixed | 0caec27 (RED), f9095ac. Both read paths go through `_show_read_error`, which writes over an empty status or the screen's own earlier error only |
| RR-04 | The Doctor guard chain end renders twice, so the live state is read twice | fixed | 487b0cc (RED), 1ed041e. `_finish_guard_chain` only rescans and requests the pass. The resume after the last modal renders Doctor once (C-08) |
| RR-05 | A whole-tool refusal names unchanged paths; a grown plan is reported `removed` | fixed | 9fd6478 (RED), 8d4afab. Only dropped or newly added removable paths are named, and a grown plan is a refusal that keeps the receipt |
| RR-06 | A deferred first-run link pick gives no feedback | fixed | d1c2b95 (RED), a0c5e8b. The target view shows `Link mode {value} will be saved when the background apply finishes.`, and the move's own status replaces it |
| TUI-1 | Tab bar clipped (`[6] Policie`; `[6] Polic` on Doctor) | backlog, pre-existing | At 390f464 (Phase 21 base) the 80x20 render of row 0 is identical on every view. On Doctor the screen's scrollbar takes columns 78-79 at both commits |
| TUI-2 | Doctor: the card scroll moves the tab bar and badge, the scrollbar thumb is drawn over the footer, and there is no keyboard scroll | backlog, pre-existing | Same geometry at 390f464 and HEAD: virtual size 78x29, `max_scroll_y` 9, screen scrollbar region x=78, h=20 (rows 0-19, header and footer included), nothing focused, and `pagedown`/`down`/`end` leave `scroll_y` at 0. 9813396 only turns row 18 from card content into the docked StatusLine; it changes neither the scroll range nor the scrollbar |
| TUI-3 | Uninstall mode badge cut (`enter removes marked items (you'll`) | backlog, pre-existing | Row 2 renders identically at 390f464 |
| TUI-4 | Uninstall cursor opens on a managed or section row, not the removable one | fixed (introduced by Phase 21) | 313a3fc (RED), 32c1d47. At 390f464, Uninstall read its rows live at construction and on each entry (`_rows_of`), so the first paint already had the removable section on top. Phase 21 made the view a projection of the published state. Entered before the first pass, it paints placeholder rows, and `_rebuild` kept the cursor on that key (`uv`) once `removable here` landed above it. Until a published state is painted, Uninstall now reloads with `keep_cursor=False`. Backstop: `test_uninstall_cursor_lands_on_the_removable_row_once_the_state_lands` (80x20) |
| TUI-5 | System columns cut (`Owne`, `OS p`) | backlog, pre-existing | Same columns, owner labels (`"os-package": "OS package"`) and spans at 390f464 and HEAD: with a `0.10.11 -> 0.10.12` Ver cell, Owner spans x 71-83 in both |
| TUI-6 | Doctor shows "Press r to reinstall the pnpm-managed global set." under "pnpm's global set could not be read" | backlog, pre-existing | Same `else` branch at 390f464 (`installer/wizard_app.py:607`). The copy comes from 8c4d9e9 (04-05) and 4a09900 (05-04) |

## Round 3 (security + UAT)

**Source:** `21-SECURITY.md` (T-21-52 and the unregistered pnpm escape-byte flag) and `21-UAT.md` test 1 (b), (c) and test 3. Each fix has a RED test commit followed by its fix commit. `make validate` and `make test` exited 0 on the tree of every fix commit; the last run passed 5237 tests (4 skipped). Gates ran in the main checkout, with no worktree.

| ID | Finding | Status | Commits |
|----|---------|--------|---------|
| T-21-52 | A daemon apply whose own live read fails does not supersede an older job read | fixed | 59b2b15 (RED), 351becd. `refresh_daemon_state` starts a fresh job-state read on every completion, including an unresolved one, so the generation always advances. The row keeps its state until the fresh read lands. Advancing the generation alone was not enough: a row blanked by the entry would have stayed blank |
| SEC-low | pnpm smoke output reaches the tier detail and the `is broken` status with ESC/OSC bytes | fixed | 3771f8d (RED), ff5260b. `_record_pnpm_evidence` runs `sanitize_log_line` on the formatted reason, so the published `ToolState.reasons` that every view reads are already clean |
| UAT-1b | After a Policies toggle, `● [on]` shows only after re-entering the view; the three-line status pushes the table off screen at 80x20 | not fixed, pre-existing | The state path is correct. In a pilot (real PoliciesScreen, a policy whose `is_active` flips on apply, 80x20), the cell reads `● [on]` right after the toggle. The table region shrinks from 3 rows (`y=4..6`) to 1 row (`y=4`, the header only), and the status takes rows 16-18. Re-entry clears the status, so the row comes back. The same pilot at 390f464 gives the same output: the cell is `● [on]`, the table is 1 row at `y=4`, and the status is on rows 16-18. `git diff 390f464 HEAD` changes no Policies CSS, `StatusLine` height or `_summary`. This belongs with the 80x20 layout todo |
| UAT-1c | The Uninstall summary `1 removed` takes two status rows | fixed (introduced by Phase 21) | 7f31401 (RED), 5ced876. d1202e8 (21-13) always appended `_applied_summary(...)`, which is empty when no lever was chosen, so the status became `1 removed\n`. At 390f464 that function opened with `Removed N tool(s).`. The empty line is now dropped. Backstop: `test_a_one_tool_removal_summary_takes_one_status_row_at_80x20` |
| UAT-3 | Space on Uninstall during a removal clears `Removing…` | fixed | cfafbb0 (RED), 25f26bf. While a removal holds the lock (`MutationLock.mutation_holder`), a mark change leaves the status alone. Space still marks: marks only feed the next removal and do not mutate the machine (D-05) |

---

_Fixed: 2026-11-03_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 3 (security + UAT round)_
