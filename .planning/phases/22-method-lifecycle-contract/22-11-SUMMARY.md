---
phase: 22-method-lifecycle-contract
plan: "11"
subsystem: uninstall-view
tags: [uninstall, confirm-modal, review, config-paths, pnpm-group, scroll, tui, tdd]

commits: 3
plan_head_before: c30c9de257c602f2fe5ef055aa1b1ef6435849bd
plan_head_after: 9c7ccf50eb135972b1aa6e822bd872090e44adc2
status: complete

requires:
  - phase: 22-06
    provides: "removal_runs_line, config_targets (declared ~ form plus expanded path)"
  - phase: 22-09
    provides: "pnpm_removal_packages, co_install_warnings, SweepResult.config_deleted/config_not_deleted"
  - phase: 22-10
    provides: "config_split (deleted and kept maps), the c flag, UninstallScreen._decision built before the modal"
provides:
  - "ConfirmUninstall(summary, review=()): the review as folded Text lines in a 60x18 VerticalScroll body, keys line pinned under it"
  - "UninstallScreen._review: blocks 3-7 built from the one decision, the config_split kept map and the flagged ids"
  - "Removal status: Config deleted for / Config kept for / Config not deleted for lines; error, warn, ok severity rule"
affects: [22-12, 22-13]

actuals:
  tokens: 8956     # chars/4 over the realized diff (35826 bytes of `git diff c30c9de HEAD`)
  tasks: 3         # three tdd tasks, one feat(22-11) commit each
  commits: 3       # MEASURED: git rev-list --count c30c9de..HEAD (before this SUMMARY commit)

tech-stack:
  added: []
  patterns:
    - "The review is built once, before the modal opens, from the same decision the confirm later receives (review R1-20)"
    - "Every review line is a Text built by fold_reason with a 2-cell hanging indent; data goes through sanitize_log_line and never through markup"

key-files:
  created: []
  modified:
    - installer/wizard_app.py
    - tests/test_wizard_app.py
    - tests/test_layout_80x20.py

key-decisions:
  - "_decision returns (decision, kept, flagged): the flagged ids are part of the snapshot, because block 6 needs the flags as they were when the modal opened"
  - "Block 7 reads each selected row's RemovalPlan at review build time, which runs synchronously with _decision, because pnpm_removal_packages takes RemovalPlans (22-09 contract); no second argv parser"
  - "Config kept (status) reads the disk at result time, not the painted plan: invalidate bumps the version epoch, so state_of returns None for every tool once the removal has run"

patterns-established:
  - "Review line: _review_line(text, style) folds at 54 cells and applies one style; the pnpm Warning: prefix is styled by span after folding"

requirements-completed: [UI-04, LIFE-08]

duration: not recorded (start time was not captured for this run)
completed: 2026-11-04
---

# Phase 22 Plan 11: the confirm modal is the review Summary

**The confirm modal now shows every command that runs, every config path that is deleted, every kept path with its reason, and the pnpm group warnings, all built from Text in a 60x18 scroll body, and the removal status says what became of config.**

## Performance

- **Tasks:** 3 of 3, one green `feat(22-11)` commit each
- **Files modified:** 3 (`installer/wizard_app.py`, `tests/test_wizard_app.py`, `tests/test_layout_80x20.py`)
- **Commits:** ece52e9, d1aee79, 9c7ccf5

## Accomplishments

- Task 1 (ece52e9): `ConfirmUninstall(summary, review)` composes its body from Text. Blocks 3 and 4 come from the one decision: `removal_runs_line` per tool with argv, and `Config deleted too:` with `  {path} ({id})` per deleted path in declared `~` form.
- Task 2 (d1aee79): blocks 5, 6 and 7 (kept shared paths, `Config kept: {ids}.`, pnpm group `Warning:` lines, `Warning:` styled yellow). `_decision` returns the kept map and the flagged ids from the same `config_split` call. The body is a `VerticalScroll` (`max-height: 13`) inside a `Vertical` box (`width: 60; max-height: 18`), and the keys line is a separate Static pinned under it. Long lines fold at 54 cells with a 2-cell hanging indent.
- Task 3 (9c7ccf5): the status gains `Config deleted for {ids}.`, `Config kept for {ids}.`, `Config not deleted for {ids}: the removal failed.`, in that order after the counts and the failure line. Severity is `error` when a removal failed or `config_not_deleted` is non-empty, `warn` when the terminal sync warned or `swept.warnings` is non-empty, else `ok` (review R1-21). Warning text goes through `sanitize_log_line`.

## Task Commits

1. **Task 1: ConfirmUninstall lists what runs and what config goes** - `ece52e9` (feat, tests and implementation together)
2. **Task 2: the full review with scrolling at 80x20** - `d1aee79` (feat, tests and implementation together)
3. **Task 3: the removal status reports config** - `9c7ccf5` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree, with the pre-commit hooks passing. No `--no-verify`, no attribution trailers, no RED-only commit.

## Test counts

- Before (measured at task start with `uv run pytest --collect-only -q -n 0`, summing per-file counts): 5496 collected (5492 passed, 4 skipped, matching the wave 5 ledger).
- After Task 1: 5499 collected (5495 passed, 4 skipped), +3.
- After Task 2: 5504 collected (5500 passed, 4 skipped), +5 (four wizard tests, one layout backstop).
- After Task 3: 5508 collected (5504 passed, 4 skipped), +4. Coverage 96.32%.
- Plan delta: +12, the twelve named tests.
- No pre-existing test was changed or deleted. Two tests added earlier in this plan were adjusted in Task 2, listed below.

## TDD Gate Compliance

RED output is recorded here only; the RED tests were never committed alone (review R1-01, ledger row 31).

### Task 1 RED

`uv run pytest tests/test_wizard_app.py -k "review_lists_exactly or empty_review_reads or review_body_is_plain" -q --no-cov -n 0`

```
FFF
test_the_review_lists_exactly_the_paths_the_removal_deletes - AttributeError: 'ConfirmUninstall' object has no attribute 'review'
test_an_empty_review_reads_as_before - AttributeError: 'ConfirmUninstall' object has no attribute 'review'
test_the_review_body_is_plain_text - AttributeError: 'ConfirmUninstall' object has no attribute 'review'
exit=1
```

Correction before GREEN: the tracer's expected order was wrong. The review follows the table order (`ToolBrowser.selected_ids` walks the adapter items), so gh comes before vend, the order in which the cases are listed. The expectation was changed to that order. This was not a code change.

### Task 1 GREEN

`uv run pytest tests/test_wizard_app.py -k "review_lists_exactly or empty_review_reads or review_body_is_plain" -q --no-cov -n 0` gave `...`, exit 0. `uv run pytest tests/test_wizard_app.py tests/test_uninstall_e2e.py tests/test_screen_family.py -n auto -q --no-cov` gave exit 0. `make validate` exit 0. `make test`: `5495 passed, 4 skipped in 58.88s`, exit 0.

### Task 2 RED

`uv run pytest tests/test_wizard_app.py -k "shared_path_is_reviewed or unflagged_config_is_reviewed or pnpm_group_lines or blocks_come_in_order" -q --no-cov -n 0`

```
FFFF
test_a_shared_path_is_reviewed_as_kept - assert [] == ['Config deleted too:', '  ~/.config/shared kept, also used by b']
test_unflagged_config_is_reviewed_as_kept - assert [] == ['Config kept: gh.']
test_pnpm_group_lines_in_the_review - assert ['mmdc: runs pnpm remove --global @mermaid-js/mermaid-cli'] == [... 'Warning: pnpm group mmdc: removing @mermaid-js/mermaid-cli leaves puppeteer installed.']
test_the_review_blocks_come_in_order - assert ['gh: runs br...nfig/gh (gh)'] == ['gh: runs br...ept: k.', ...]
exit=1
```

`uv run pytest tests/test_layout_80x20.py -k long_review_scrolls -q --no-cov -n 0`

```
assert sum(line.startswith("Warning:") for line in review) == 2
E   assert 0 == 2
exit=1
```

### Task 2 GREEN

- Focused wizard run: `.......` exit 0, after one test fix: `test_the_review_body_is_plain_text` used `query_one(Static)`, which now matched the keys line, so it was pointed at `#confirm-body Static`.
- `uv run pytest tests/test_layout_80x20.py -k long_review_scrolls -q --no-cov -n 0`: `.`, exit 0.
- `uv run pytest tests/test_wizard_app.py tests/test_layout_80x20.py tests/test_screen_family.py tests/test_uninstall_e2e.py -n auto -q --no-cov`: exit 0.
- `make validate`: first run exit 2 (four E501 lines, and a ruff format change to `tests/test_wizard_app.py`). After the line splits and `ruff format`, exit 0.
- `make test`: `5500 passed, 4 skipped in 63.23s`, exit 0.

### Task 3 RED

`uv run pytest tests/test_wizard_app.py -k "config_result_lines_follow or failed_vendor_remove_keeps_config or config_delete_warning or status_data_is_literal" -q --no-cov -n 0`

```
FFFF
test_config_result_lines_follow_the_counts - assert '2 removed' == '2 removed\nConfig deleted for gh.\nConfig kept for uv.'
test_a_failed_vendor_remove_keeps_config_and_says_so - assert '1 remove failed. Fix the cause...' == 'Config not deleted for vend: the removal failed.'
test_a_config_delete_warning_is_shown - assert <Severity.OK> is <Severity.WARN>
test_status_data_is_literal - assert '... — [31mdenied.' in '1 removed\nwarning: could not delete config ~/.config/[red]x[/] — \x1b[31mdenied.'
exit=1
```

### Task 3 GREEN

- First GREEN run: `Config kept for uv.` was missing. Cause: `state_of` returns None after `invalidate` (epoch bump), so the painted state cannot be read at result time. The check was changed to the live disk (see deviations). A second cause was in the test: `uv`'s config directory was never created, so the disk check correctly found nothing. The test now creates it under the scratch HOME.
- Focused run: `....` exit 0.
- `uv run pytest tests/test_wizard_app.py tests/test_layout_80x20.py tests/test_screen_family.py tests/test_uninstall_e2e.py -n auto -q --no-cov`: exit 0.
- `make validate`: first run exit 2 (two E501 lines, then a format change). After the fixes, exit 0.
- `make test`: `5504 passed, 4 skipped in 47.40s`, exit 0. The test session guard did not trip.

### Plan acceptance greps (on the final tree)

- `grep -c "co_install_warnings(" installer/wizard_app.py`: 1
- `grep -c "pnpm_removal_packages(" installer/wizard_app.py`: 1; `grep -c '"pnpm", "remove", "--global"' installer/wizard_app.py`: 0 (22-REUSE 09-1)
- `grep -c "max-height: 18" installer/wizard_app.py`: 1
- `grep -c '"Config deleted too:"' installer/wizard_app.py`: 1
- `grep -c "Config not deleted for" installer/wizard_app.py`: 1
- `sed -n "/def on_removal_finished/,/def _request_pass/p" installer/wizard_app.py | grep -c "swept.warnings"`: 1 (review R1-21)
- `ConfirmUninstall` no longer builds its body from `Text.from_markup` (task 1 grep, exit 0)
- Suppression comments added by this plan (`git diff c30c9de HEAD | grep "^+" | grep -c "type: ignore|pyright: ignore|noqa|nosec"`): 0

## Deviations from Plan

### Auto-fixed or interpreted

**1. [Design] `_decision` returns a triple, not a pair**
- **Found during:** Task 2
- **Issue:** The plan asks for the decision together with the kept map. Block 6 (`Config kept: {ids}.`) also needs the flag state as it was when the modal opened.
- **Fix:** `_decision(ids)` returns `(decision, kept, flagged)` from one `config_split` call and one read of `_config_on`. Nothing is read again after the confirm.
- **Impact:** None on the removal. The confirm still receives only `decision`.

**2. [Design] Block 7 reads the selected rows' plans at build time**
- **Found during:** Task 2
- **Issue:** `pnpm_removal_packages` takes `RemovalPlan`s (the 22-09 contract), while the decision holds argv only.
- **Fix:** Block 7 reads `self._state_of(tool).removable` for each decided tool. That read runs synchronously with `_decision`, before the modal opens, so it is the same snapshot. No argv parser was written here.

**3. [Interpretation] Block 6 follows the UI-SPEC wording**
- **Issue:** UI-SPEC row 6 says `Config kept: {ids}.` for marked tools that declare `config_paths` with the flag off. It does not require the config to be on disk.
- **Fix:** Implemented literally. A marked tool with config paths and the flag off is listed even when nothing is on disk. The status (Task 3) does require the config to be on disk.

**4. [Deviation from the painted-plan wording] "Config kept" reads the disk at result time**
- **Found during:** Task 3
- **Issue:** The plan says a removed tool's kept config is judged from its painted plan. `_run_removal` calls `invalidate` before `RemovalFinished` is posted. `invalidate` bumps the version epoch, so `state_of` returns None for every tool by the time `on_removal_finished` runs. The painted state cannot be read there.
- **Fix:** `_config_lines` checks each declared path with `path.is_symlink() or path.exists()`. UI-SPEC defines the line as "config still on disk", which is a question about the disk now.
- **Impact:** A few stat calls run on the UI thread in `on_removal_finished`, after the removal has finished. `config_split`, which runs while the user is still choosing, keeps its no-filesystem rule.

**5. [Hardening] Warning text is sanitized in the status**
- **Found during:** Task 3 RED
- **Issue:** `_applied_summary` wrote `swept.warnings` straight into the status, so an escape byte in a vendor error reached the status text.
- **Fix:** Each warning and each config line passes through `sanitize_log_line`.

**6. [Process] The plan commit ledger was not written before the first commit**
- **Issue:** Protocol 0c (`gsd-plan-head-before-22-11`) was skipped. The plan's `commits:` value is still measured, not narrated.
- **Fix:** `plan_head_before` is the start HEAD, `c30c9de`, which was verified before any edit. `commits: 3` is `git rev-list --count c30c9de..HEAD`.

**7. [Fixture] The tracer's `vend` argv is a fixture path**
- **Issue:** The plan's example mentions a sandboxed HOME path. The test uses `/opt/vend/bin/vend uninstall --force` as the bound argv.
- **Impact:** None on behaviour. The review line is `shlex.join` of the bound argv either way.

### Changed tests (listed with reasons)

Both changes are to tests this plan added earlier in the same plan, in Task 2's commit. No pre-existing test was changed.

- `test_an_empty_review_reads_as_before`: the body is now `#confirm-body Static` and the keys line is `#confirm-keys`. Reason: UI-SPEC requires the keys line pinned under the scroll body, so the two are separate widgets.
- `test_the_review_body_is_plain_text`: `query_one(Static)` became `query_one("#confirm-body Static", Static)`. Reason: the same split.

## Known gaps (not in this plan's truths)

- **The run report is not touched.** The plan's literal backstop mentions the run report. This plan has no task for it, and no held-out test for it was added.
- **The detail bar is not given a new test.** It renders `Text(self.detail_text)`, and `_tool_entry` already passes its text through `sanitize_log_line`, so markup and escape bytes are inert there. This holds by reading, not by a test added here.
- **Narrow text column when the body scrolls.** Lines fold at 54 cells. A vertical scrollbar appears when the body overflows and takes 2 cells, so Textual re-wraps at 52 without the hanging indent. Content is never cut. Only the indent is at risk, and it was not checked visually (see Human verification).
- **22-10 hand-off closed:** the kept map from `config_split` now renders as block 5, as the hand-off asked.
- **22-09 hand-off closed:** a path kept because another owner stays is rendered from the kept map, not from the core result.

## Human verification (not blocking)

- **NO_COLOR 80x20 tmux check of the review modal, in a UTF-8 terminal inside a disposable container:** the layout, the scroll, the keys line and the `Warning:` styling still need a human look. Not run in this session. The automated `test_a_long_review_scrolls_and_keeps_its_keys_line` covers the geometry, the scroll and the keys line, not colour, and not the hanging indent under a scrollbar.

## Review dispositions

- **R1-01 (RED commits):** met. RED output is in this SUMMARY, and each task is one `feat(22-11)` commit with its tests.
- **R1-18 (`config_split` three-argument handoff):** met. `config_split(flagged, catalog, state_of)` is called once in `_decision`.
- **R1-20 (decision recomputed after the confirm):** met. The review and the decision come from one `_decision` call before the modal opens. `test_a_refresh_while_the_modal_is_open_keeps_the_decision` (22-10) still passes.
- **R1-21 (warning severity):** met. Task 3 asserts `Severity.WARN` for a config delete warning and `Severity.OK` without one.
- **R2-03 / R2-05:** the tracer uses the test-local recipe `vend`. Its argv is bound, and the review line is `shlex.join` of that argv.

## Self-Check: PASSED

- Commits present in HEAD history: `ece52e9` (Task 1), `d1aee79` (Task 2), `9c7ccf5` (Task 3). Confirmed with `git merge-base --is-ancestor`.
- Files present in the worktree: `installer/wizard_app.py`, `tests/test_wizard_app.py`, `tests/test_layout_80x20.py`.
- Final tree: `make validate` exit 0, `make test` 5504 passed, 4 skipped, exit 0.
- No changes to STATE.md or ROADMAP.md. This SUMMARY is the only `.planning/` file this plan touched.
