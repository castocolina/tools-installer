---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "17"
status: complete
subsystem: catalog-ui
tags: [layout, legend, detail-bar, textual, compositor, health, tdd]

requires:
  - phase: 19-15
    provides: "identity line + health block in `_detail_text`, the 19-UI-SPEC `_LEGEND`, tests/state_doubles.py publish/pass_state"
provides:
  - "Legend and detail bar stack under the 1fr table (no `dock: bottom`); detail is a fixed 3 rows"
  - "`AppScreen > Rule.-horizontal { margin: 0 }`: header/Rule/ModeBadge on rows 0-2 on every AppScreen"
  - "3-row detail: identity row (no wrap, `…`) + health block word-wrapped at paint time and cut to two rows (`_cut_rows`, review H11); adapter parser honored for both parts (review H12)"
  - "`BrowserAdapter.empty_detail`; the catalog's empty-tier copy"
  - "tests/test_layout_80x20.py: compositor checks for the 3 tiers, Doctor, Uninstall, Policies, 120x30, and every Health mark on every tier"
affects: [19-18]

actuals:
  tokens: 6250
  tasks: 3
  commits: 3
plan_head_before: e48a13860b118d3480568fe7d790833b11d6970d
plan_head_after: ae0448975cbca261c404b8123ef1c6612147a999

tech-stack:
  added: []
  patterns:
    - "visibility claims read the compositor: `rows_of(screen, widget)` = the rows where `screen.get_widget_at(x, y)` hits the widget or a descendant"
    - "a size-dependent cut lives in a tiny rich renderable (`_Rows.__rich_console__`) so Textual re-cuts it on every resize; no resize handler"

key-files:
  created:
    - tests/test_layout_80x20.py
    - .planning/phases/19-one-tool-state-with-health-plus-receipts/19-17-SUMMARY.md
  modified:
    - installer/tool_browser.py
    - installer/ui_common.py
    - installer/catalog_tui.py
    - tests/test_tool_browser.py
    - tests/test_catalog_tui.py

key-decisions:
  - "The two-row cut is a render-time renderable (`_Rows`) rather than a resize handler: the width comes from the console options Textual renders the Static with, so a resize re-cuts with no timing window"
  - "A detail with no newline (Uninstall's one-sentence details, the empty-view copy has one) keeps all three rows wrapped and cut, so Uninstall paths are not squeezed onto one ellipsized row"
  - "Doctor's `#doctor-body` keeps its own `margin: 2 0` card spacing; the chrome check asserts its box (margin included) starts on row 3 and row 3 is blank screen, without changing wizard_app CSS"

requirements-completed: [STATE-02, STATE-06]

duration: ~50min
completed: 2026-10-16
---

# Phase 19 Plan 17: Legend and detail visible at 80x20 Summary

The legend and the health detail now stack under the catalog table instead of painting over each other. At 80x20 every tier shows a table of at least 6 rows, all 3 legend rows and a fixed 3-row detail bar: the identity line on row 1, then the health block word-wrapped and cut to two rows with `…`. The Rule margin fix gives back the 2 rows this costs.

## Tasks

| # | Commit | What |
|---|--------|------|
| 1 | 47c067d | `fix(19-17)`: dropped `dock: bottom` from `#browser-legend`/`#browser-detail`, `#browser-detail { height: 3 }`, `AppScreen > Rule.-horizontal { margin: 0 }` with a one-line why; new tests/test_layout_80x20.py (`test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20[system]`, `test_rule_has_no_margin`); planned replacement of `test_legend_keeps_the_catalog_table_usable_at_the_minimum_size` |
| 2 | f4f8bf3 | `feat(19-17)`: `_cut_rows(text, rows, width, console)` (wrap first with `Text.wrap`, keep `rows` lines, ellipsize the last with `append("…")` + `truncate(width, overflow="ellipsis")`), `_Rows` renderable, `ToolBrowser._show_detail` (split at the first newline, one parser per adapter, `Group(identity, _Rows(health, 2))`), `BrowserAdapter.empty_detail` shown by `_rebuild` when the view has no item rows; catalog `empty_detail` = `No tools in the {Label} tier.\nPress 1-6 or ^p to open another view.` |
| 3 | ae04489 | `test(19-17)`: tier check parametrized over system/user/ai, `test_health_column_inside_80_columns` x3, `test_catalog_at_120x30`, `test_doctor_chrome_at_80x20`, `test_uninstall_chrome_at_80x20`, `test_policies_chrome_at_80x20`, `test_every_health_mark_renders_on_every_tier` x3 |

## TDD RED evidence

Task 1 (before the CSS change):
```
FAILED tests/test_layout_80x20.py::test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20[system]
>           assert len(legend) == 3, legend
E           AssertionError: {14}        # 1 of 3 legend rows topmost
FAILED tests/test_layout_80x20.py::test_rule_has_no_margin - assert {2} == {1}
```

Task 2 (before `_show_detail` / `empty_detail`):
```
E       TypeError: BrowserAdapter.__init__() got an unexpected keyword argument 'empty_detail'
E       AssertionError: ['id', 'abcdefghijk', 'abcdefghijk']          # word-boundary: no `…`
E       AssertionError: ['id', 'xxxxxxxxxxxxxxxxxxxx', 'xxxxxxxxxxxxxxxxxxxx']   # unbroken
E       AssertionError: ['id', 'short', 'second reason line']        # embedded newline
E       AssertionError: assert ['', ''] == ['No tools in...nother view.']
FAILED test_detail_identity_row_never_wraps (identity row wrapped, no `…`)
FAILED test_detail_health_block_that_fits_is_not_ellipsized_and_recuts_on_resize
```
`test_detail_of_a_plain_text_adapter_keeps_brackets_literal` and `test_detail_text_seam_keeps_the_plain_text` were already green before the change. They guard the H12 contract and the `detail_text` seam against the new two-part rendering, so they could not fail first.

Task 3 (checks that already pass after Tasks 1-2): discriminating mutations, each applied in place, run, then restored with `git checkout -- <file>`:
- **M1**: `dock: bottom` and `height: 2` restored in tool_browser.py CSS. Fails `test_catalog_tiers_show_all_legend_and_detail_rows_at_80x20[system|user|ai]` and `test_uninstall_chrome_at_80x20`.
- **M2**: Rule selector reverted to `AppScreen > Rule`. Fails `test_rule_has_no_margin`, the 3 tier checks, `test_catalog_at_120x30`, and the doctor, uninstall and policies chrome checks (`assert {2} == {1}`).
- **M3**: `health_cell` returns a wide cell (`"✓ checking-for-real..."`). Fails `test_health_column_inside_80_columns[system|user|ai]` and `test_every_health_mark_renders_on_every_tier[system|user|ai]`.
- **Not discriminating**: section titles moved back into the Sel column (`section_column="sel"`). The Health column still fits at 80, so this mutation catches nothing and is not used.

## Verify results

- `uv run pytest tests/test_layout_80x20.py tests/test_catalog_tui.py -q --no-cov -k "legend or layout or rule or minimum_size"`: green.
- Task 2 gate (`-k "identity_row or cut_at_two_rows or seam_keeps or empty_tier or brackets_literal"`): 7 passed.
- `uv run pytest tests/test_layout_80x20.py -n auto -q --no-cov`: 14 passed.
- Plan verification: `uv run pytest tests/test_layout_80x20.py tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_wizard_app.py -n auto -q --no-cov`: green.
- `make validate`: 0 on every commit. `make test` on the final tree: 4480 passed, 4 skipped, coverage 95.95%.
- Suppression comments: 503 at e48a138, 503 now. No dependency change (`git diff --exit-code e48a138 -- pyproject.toml uv.lock` is clean).
- Acceptance greps: `dock: bottom` in tool_browser.py 0; `Rule.-horizontal` in ui_common.py 2 (comment + CSS); `empty_detail` 3; `Group(` 1; `detail_is_markup` 2; `.wrap(` 1; `truncate(2 *` 0; `get_widget_at` in test_layout_80x20.py 4.

## Large-file evidence

- `tests/test_catalog_tui.py`: 4784 (e48a138) -> 4748 (Task 1, the one planned test removed, top-level tests 179 -> 178; shrink guard OK) -> 4765 (Task 2, one test appended).
- `installer/catalog_tui.py`: 885 -> 889 (import + `empty_detail`).
- Per-commit `git show --stat`:
  - 47c067d: tool_browser.py 4 +-, ui_common.py 3 +-, test_catalog_tui.py 36 -, test_layout_80x20.py 95 +.
  - f4f8bf3: catalog_tui.py 6 ++-, tool_browser.py 55 +++-, test_catalog_tui.py 17 +, test_tool_browser.py 117 ++-.
  - ae04489: test_layout_80x20.py 158 ++- (148 insertions, 10 deletions).

## Deviations from Plan

1. **Helper name and shape.** The plan names `_two_rows(text, width, console)`. The code has `_cut_rows(text, rows, width, console)` plus a `_Rows` renderable, because a detail with no newline gets all 3 rows. Uninstall details are one long sentence that used to wrap over 2 rows; forcing them onto an ellipsized identity row would hide the "remove it yourself: <paths>" tail. The H11 contract is unchanged: wrap first, keep N lines, ellipsize, and there is no `truncate(2 *`.
2. **Re-cut on resize.** This needs no resize handler. `_Rows.__rich_console__` cuts at the width Textual renders the Static with, and the test resizes from 22 to 42 columns and checks the re-cut.
3. **Doctor chrome check.** `#doctor-body` has its own `margin: 2 0` (centered card), so its painted content starts on row 5. The test asserts that its box, margin included, starts on row 3 and that row 3 is blank screen, not another widget. No wizard_app CSS was changed and no fallback was needed.
4. **Every-mark test platform.** The UNAVAILABLE state is built with `tool_state` (through `pass_state`) on a macOS platform without Homebrew, where every tier has a tool with no method (zsh, jq, eza today). The other states use macOS with Homebrew. The empty-tier copy uses `len(VIEW_ORDER)` because catalog_tui has its own `VIEWS` (grouping views), which shadowed the nav list.
5. **Extra tests.** Two tests beyond the plan: `test_detail_health_block_that_fits_is_not_ellipsized_and_recuts_on_resize` (holds the plan's "fits -> no `…`" and resize clauses) and `test_empty_view_shows_the_adapters_empty_detail` in tests/test_tool_browser.py.

All edits are inside the plan's files_modified.

## Issues for the orchestrator

- The docstring of `test_nine_column_table_mounts_and_renders_at_the_minimum_size` (tests/test_catalog_tui.py) still says "below the docked legend". It is stale wording only, left as is.
- The worktree tooling refused some compound shell commands, so the plan's `bash -c` shrink guard ran as a script in the plan scratch dir. The scratch dir is deleted at the end.
- No binding changes; `r` untouched. TUI navigation in tmux is still the orchestrator's phase-close check.

## Self-Check: PASSED

- FOUND: tests/test_layout_80x20.py, installer/tool_browser.py, installer/ui_common.py, installer/catalog_tui.py
- FOUND commits: 47c067d, f4f8bf3, ae04489 (ancestors of HEAD)
