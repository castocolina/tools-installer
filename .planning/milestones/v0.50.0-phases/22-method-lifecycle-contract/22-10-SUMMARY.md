---
phase: 22-method-lifecycle-contract
plan: "10"
subsystem: uninstall-view
tags: [uninstall, config-paths, delete-config-too, toggle, tui, shared-paths, focus, tdd]

commits: 3
plan_head_before: 6dce31d593a744cda02fb6bf631930d90c6a92f5
plan_head_after: 2b852fe556bddafb7387d0f48b4cac3fb3cdeecf

requires:
  - phase: 22-07
    provides: "_UninstallEntry.argv, the L1/L3 detail sentences, uninstall_group reading the removal plan"
  - phase: 22-09
    provides: "UninstallDecision.config, SweepResult.config_deleted/config_not_deleted, step-4 config deletion, delete_config_path"
provides:
  - "c on a removable row whose tool declares config_paths: a per-row flag, marks the row too, off by default, never persisted"
  - "config_split(flagged, catalog, state_of) -> (deleted per tool, kept per declared ~ form), public in wizard_app"
  - "UninstallScreen._decision(ids) built once before ConfirmUninstall; the confirm hands that decision to _apply_removal"
  - "BrowserAdapter.mark_cell: the sel cell hook every browser re-stamp uses"
  - "[c] in bold red, `config + ` prefix, and the config detail clause (kept / deleted too / none on disk)"
  - "uninstall_detail(..., *, config=\"\") placing the clause after the proof sentence"
  - "Refusals for c on no-config, managed/nothing-to-do, and environment or section rows"
  - "Flags follow the marks (repaint drops them), clear on leave via clear_transient, and survive a running removal"
  - "Uninstall footer: space mark | enter remove | a all | i invert | c config"
affects: [22-11, 22-13]

actuals:
  tokens: 9339     # chars/4 over the realized diff (37356 bytes of `git diff 6dce31d HEAD`)
  tasks: 3         # three auto/tdd tasks, one feat(22-10) commit each
  commits: 3       # MEASURED: git rev-list --count 6dce31d..HEAD (before this SUMMARY commit)

tech-stack:
  added: []
  patterns:
    - "A flag is a per-row set on the screen, intersected with the browser's marks on every repaint, never a second source of selection"
    - "The removal decision is built once before the modal and handed unchanged to the remover; only the remover's own fresh checks narrow it"
    - "Refusal copy is a warn line that is not written while a removal runs, so Removing... never flips to a refusal"

key-files:
  created:
    - .planning/phases/22-method-lifecycle-contract/22-10-SUMMARY.md
  modified:
    - installer/wizard_app.py
    - installer/tool_browser.py
    - installer/version_status.py
    - installer/ui_common.py
    - tests/test_wizard_app.py
    - tests/test_tool_browser.py
    - tests/test_layout_80x20.py

key-decisions:
  - "c on an unmarked removable row marks it and turns its flag on (UI-SPEC A1); c on a flagged row only turns the flag off and the row stays marked"
  - "config_split reads existence from each flagged tool's published state.removable.config and builds its expanded paths through uninstall.config_targets (22-REUSE 06-2, 10-1): no lstat on the UI thread"
  - "A path is deleted for a flagged tool only when every catalog tool declaring it is flagged; the kept map keys the declared ~ form to the declaring tools that stay (UI-SPEC A5)"
  - "_decision runs in on_tool_browser_accepted before ConfirmUninstall opens; _apply_removal(decision) never rebuilds it (review R1-20)"
  - "_repaint intersects the flags with the browser's selection before rebuilding, so a repaint drops flags whose rows were unmarked, removed or made unselectable"
  - "action_toggle_config calls _repaint (not refresh_marks) so the detail bar and removes cell update with the flag"
  - "clear_transient clears every flag on leave through show_view's one navigation path; a modal cover never calls it (review R1-19, T-22-42)"
  - "Refusal copy is not written while a removal runs: the spec asks both for the refusal line and that c never clears Removing...; the status line cannot show both, so Removing... wins (deviation, see below)"

requirements-completed: [UI-04]

coverage:
  - id: D1
    description: "c flags a removable row with config_paths; the confirmed removal carries exactly the agreed config paths"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_c_turns_the_flag_on_and_the_removal_deletes_the_config"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_an_unflagged_row_sends_no_config"
        status: pass
    human_judgment: false
  - id: D2
    description: "A path another unflagged declarer needs is kept; decision is built once and never rebuilt after the confirm"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_config_split_keeps_a_path_another_tool_needs"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_a_refresh_while_the_modal_is_open_keeps_the_decision"
        status: pass
    human_judgment: false
  - id: D3
    description: "[c], config + prefix, and the config clause (kept / deleted too / none on disk); refusals for c"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_tool_browser.py#test_mark_cell_hook_survives_every_restamp"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_a_flagged_row_shows_c_config_prefix_and_suffix"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_declared_config_with_nothing_on_disk_reads_none_on_disk"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_c_explains_why_it_does_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_the_uninstall_footer_names_c"
        status: pass
    human_judgment: false
  - id: D4
    description: "Flags follow marks; leaving the view clears them; a running removal keeps them usable; 80x20 layout holds"
    requirement: "UI-04"
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_unmarking_clears_the_flag_and_a_never_sets_one"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_c_works_during_a_removal_and_keeps_removing_status"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_a_successful_removal_clears_the_flag_and_a_failed_one_keeps_it"
        status: pass
      - kind: unit
        ref: "tests/test_wizard_app.py#test_flags_start_off_on_every_visit"
        status: pass
      - kind: unit
        ref: "tests/test_layout_80x20.py#test_the_toggle_fits_80x20"
        status: pass
    human_judgment: true
    human_check: "NO_COLOR=1 80x20 tmux check of [c], config + and the detail suffix in a UTF-8 terminal (not run; see Human verification)"
---

# Phase 22 Plan 10: The per-row "delete config too" toggle (c) in the Uninstall view

**`c` flags a removable row whose tool declares `config_paths`; the confirmed removal carries exactly the paths every declaring tool agreed to delete, and the row shows `[c]`, `config + ` and a detail clause that names what exists.**

## Performance

- **Tasks:** 3 of 3, one green `feat(22-10)` commit each
- **Files modified:** 7 (the plan's list, with `tests/test_tool_browser.py` added for the `mark_cell` hook test)
- **Commits:** 13d0d50, 444d84d, 2b852fe

## Accomplishments

- Task 1 (13d0d50): `c` tracer, `config_split`, and the decision built once before the modal. The confirmed removal reaches the remover with `decision.config`.
- Task 2 (444d84d): `BrowserAdapter.mark_cell` (re-stamped by `refresh_marks` and `action_toggle_selected`), `[c]` in bold red, the `config + ` prefix within the 40-cell budget, the detail clause after the proof sentence, the three refusal copies, and the footer.
- Task 3 (2b852fe): flags follow marks (repaint intersects with the selection), `clear_transient` clears them on leave, `c` never reaches the mutation lock, and the 80x20 layout test.

## Task Commits

1. **Task 1: c flags a removable row and the confirmed removal carries its config paths** - `13d0d50` (feat, tests and implementation together)
2. **Task 2: a flagged row reads [c], config + and the config suffix; c explains itself** - `444d84d` (feat, tests and implementation together)
3. **Task 3: flags follow the selection, survive a running removal, and fit 80x20** - `2b852fe` (feat, tests and implementation together)

Each commit was made after `make validate` and `make test` exited 0 on that exact tree. The pre-commit hooks passed on each commit. No `--no-verify`, no attribution trailers, no RED-only commit.

## Test counts

- Before (measured at task start, `uv run pytest --collect-only -q -n 0`): 5482 collected (5478 passed, 4 skipped, matching wave 4's ledger).
- After Task 1: 5482 passed, 4 skipped (+4 tests).
- After Task 2: 5487 passed, 4 skipped (+5 tests).
- After Task 3: 5492 passed, 4 skipped, coverage 96.26% to 96.29% (+5 tests). Delta +14.
- No existing test was changed or deleted. The only edits to existing test code are added imports (`config_split`, `LAYOUT_PROOF_NOTE`, `VIEW_BY_NAME`, `HeldRemover`, `plan_state`, `RemovalPlan`, `UninstallScreen`).

## TDD Gate Compliance

RED output is recorded here only; the RED tests were never committed alone (review R1-01, ledger row 31).

### Task 1 RED

`uv run pytest tests/test_wizard_app.py -k "c_turns_the_flag_on or unflagged_row_sends_no_config or config_split_keeps or refresh_while_the_modal_is_open" -q --no-cov -n 0`

```
ERROR collecting tests/test_wizard_app.py
ImportError: cannot import name 'config_split' from 'installer.wizard_app'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
exit=2
```

Note: the missing symbol fails collection of the whole module, so no per-test RED list exists for Task 1. `test_an_unflagged_row_sends_no_config` would pass on the old code (`decision.config` is empty by default), so it is a regression guard, not RED.

### Task 2 RED

`uv run pytest tests/test_wizard_app.py tests/test_tool_browser.py -k "flagged_row_shows or none_on_disk or c_explains or footer_names_c or mark_cell_hook" -q --no-cov -n 0 --tb=line`

```
FAILED tests/test_wizard_app.py::test_a_flagged_row_shows_c_config_prefix_and_suffix - AssertionError: assert 'installed in...emovable here' == 'installed in...letes it too)'
FAILED tests/test_wizard_app.py::test_declared_config_with_nothing_on_disk_reads_none_on_disk - AssertionError: assert 'installed in...emovable here' == 'installed in...letes it too)'
FAILED tests/test_wizard_app.py::test_c_explains_why_it_does_nothing - AssertionError: assert ('', None) == ('rg declares...ete.', 'warn')
FAILED tests/test_wizard_app.py::test_the_uninstall_footer_names_c - AssertionError: assert 'space mark |...ll | i invert' == 'space mark |...rt | c config'
FAILED tests/test_tool_browser.py::test_mark_cell_hook_survives_every_restamp - TypeError: BrowserAdapter.__init__() got an unexpected keyword argument 'mark_cell'
exit=1
```

### Task 3 RED

Run after the test corrections below, before any Task 3 implementation:

`uv run pytest tests/test_wizard_app.py tests/test_layout_80x20.py -k "unmarking_clears_the_flag or c_works_during_a_removal or clears_the_flag_and_a_failed or toggle_fits_80x20 or start_off_on_every_visit" -q --no-cov -n 0 --tb=line`

```
FAILED tests/test_wizard_app.py::test_unmarking_clears_the_flag_and_a_never_sets_one - AssertionError: assert not True   (the config + prefix survived the unmark)
FAILED tests/test_wizard_app.py::test_a_successful_removal_clears_the_flag_and_a_failed_one_keeps_it - AssertionError: assert '[c]' == '[x]'   (the removed row's flag leaked into a new mark)
FAILED tests/test_wizard_app.py::test_flags_start_off_on_every_visit - AssertionError: assert '[c]' == '[ ]'   (the flag survived leaving the view)
exit=1
```

Regression guards (passed before Task 3 code existed, so they are not RED):
- `test_c_works_during_a_removal_and_keeps_removing_status` passed at Task 2 HEAD: `c` already has no mutation-lock refusal and does not clear the status.
- `test_the_toggle_fits_80x20` passed at Task 2 HEAD once the test's own whitespace normalisation was fixed (see deviations).
- `test_a_successful_removal_clears_the_flag_and_a_failed_one_keeps_it` passed its first assertions at HEAD (a non-selected row's cell is never `[c]`). Its RED comes from the added re-mark step, which I added to expose the leaked flag.

### GREEN (per task)

- Task 1: `uv run pytest tests/test_wizard_app.py -k "c_turns_the_flag_on or unflagged_row_sends_no_config or config_split_keeps or refresh_while_the_modal_is_open" -q --no-cov -n 0` gives `....` and exit 0. `uv run pytest tests/test_wizard_app.py tests/test_uninstall_e2e.py tests/test_screen_family.py -n auto -q --no-cov` gives exit 0. `make validate` exit 0. `make test` `5482 passed, 4 skipped`, exit 0.
- Task 2: the five target tests give `.....`, exit 0. `uv run pytest tests/test_tool_browser.py tests/test_wizard_app.py tests/test_catalog_tui.py tests/test_ui_common.py tests/test_version_status.py -n auto -q --no-cov` gives exit 0. `make validate` exit 0. `make test` `5487 passed, 4 skipped`, exit 0.
- Task 3: the five target tests give `.....`, exit 0. `uv run pytest tests/test_wizard_app.py tests/test_layout_80x20.py tests/test_screen_family.py tests/test_uninstall_e2e.py -n auto -q --no-cov` gives exit 0. `make validate` exit 0 (after shortening one over-long docstring, E501). `make test` `5492 passed, 4 skipped`, exit 0.

### Plan acceptance greps (on the final tree)

- `Binding("c", "toggle_config", "config")` in wizard_app.py: 1
- `def config_split(` in wizard_app.py: 1
- `config_split(` inside `_apply_removal`: 0
- `refuse_if_mutating` inside `action_toggle_config`: 0
- `def clear_transient` inside `UninstallScreen`: 1
- footer string in ui_common.py: 1
- `mark_cell` in tool_browser.py: 3 (field, the two call sites through `_sel_cell`)
- Added suppression comments (`type: ignore`, `pyright: ignore`, `noqa`, `nosec`) in this plan's diff: none

## Deviations from Plan

### Auto-fixed or interpreted

**1. [Interpretation] A refusal is not written over `Removing…`**
- **Found during:** Task 3
- **Issue:** The row refusals (`cannot be removed here`, `declares no config`, `no config to delete`) are warn lines, but the truths also say `c` never clears `Removing…`. The one status line cannot show both.
- **Fix:** `_config_refused` writes the refusal only when no removal is running. `c` itself is never refused by the lock and does not touch the status while a removal runs.
- **Impact:** A user pressing `c` on a managed row during a removal sees no new line. Revisit if UI-SPEC wants both shown.

**2. [Test expectation corrected in GREEN] The mark outlives the visit**
- **Found during:** Task 3 GREEN, `test_flags_start_off_on_every_visit`
- **Issue:** My draft expected the row to read `[ ]` after returning to the view. Selection marks persist across visits (existing behavior); only the flag is cleared.
- **Fix:** The test now expects `[x]` (marked, no flag) and runs the removal with `config == {}`. No production code changed for this.

**3. [Test defect fixed before the RED run] Whitespace in the layout test's detail assertion**
- **Found during:** Task 3 RED
- **Issue:** `Text.wrap` leaves a trailing space on a wrapped line, so joining the first two lines produced `(c  keeps it)`.
- **Fix:** Normalise each line with `" ".join(line.plain.split())`. The layout test then passed at HEAD (a regression guard).

**4. [RED strengthened] A successful-removal flag leak was invisible to the first draft**
- **Found during:** Task 3 RED
- **Issue:** The first draft of `test_a_successful_removal_...` passed at HEAD, because a non-selected row's cell is never `[c]`.
- **Fix:** Added an `up` and `space` re-mark step. The flag leaking into the new mark is what RED shows.

**5. [Design] `c` repaints through `_repaint`, not `refresh_marks`**
- **Found during:** Task 2 GREEN
- **Issue:** `refresh_marks` re-stamps only the sel cell, so the removes cell and the detail bar would not reflect the flag.
- **Fix:** `action_toggle_config` calls `_repaint()`.

## Known gaps (not in this plan's truths)

- **Kept, shared is not rendered on a row.** `config_split` returns the kept map (declared `~` form to the declaring tools that stay), and `test_config_split_keeps_a_path_another_tool_needs` covers it. No row text uses it yet. 22-09's hand-off asked the TUI to show "kept, shared" itself. 22-11's review is the place that renders the kept map from the same `config_split` call, per the plan's Task 1 decisions. Flag this for the orchestrator.
- **A failed flagged row shows the failure word in `What gets removed`.** `_with_failure` replaces cell 5, so `config + ` is not shown on a failed flagged row. `[c]` and the detail clause still show, and the flag survives the failure so `enter` retries the same choice.
- **`config_split`'s second map is not consumed yet.** 22-11 consumes it.

## Human verification (not blocking)

- NO_COLOR 80x20 readability of `[c]`, `config + ` and the detail suffix in a UTF-8 terminal, in a disposable container TUI (per the plan's human-check). Not run in this session. The automated `test_the_toggle_fits_80x20` covers the layout only, not color.

## Session guard

No test session guard trip was observed in any of the `make test` runs (3 runs, 5482/5487/5492 passed, exit 0).

## Self-Check: PASSED

- Commits present in HEAD history: `13d0d50` (Task 1), `444d84d` (Task 2), `2b852fe` (Task 3). Confirmed with `git merge-base --is-ancestor`.
- Files present in the worktree: `installer/wizard_app.py`, `installer/tool_browser.py`, `installer/version_status.py`, `installer/ui_common.py`.
- Final tree: `make validate` exit 0, `make test` 5492 passed, 4 skipped, exit 0.
- No changes to STATE.md or ROADMAP.md.
