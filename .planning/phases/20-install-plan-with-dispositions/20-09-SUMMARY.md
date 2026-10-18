---
phase: 20-install-plan-with-dispositions
plan: "09"
subsystem: render
tags: [renderer, summary, outcome-rows, tui, pln-04]
requires:
  - 20-06 (plan row anatomy, fold_reason, id_width, display_order)
  - 20-07 (RowOutcome, summary_counts, WORDS, RESULT_WORDS)
provides:
  - summary_head, outcome_row_text, running_row_text, render_run_summary (installer/render.py)
affects:
  - installer/render.py
  - tests/test_render.py
key-files:
  created: []
  modified:
    - installer/render.py
    - tests/test_render.py
key-decisions:
  - "Done rows take the disposition done word alone; every other result takes RESULT_WORDS, so no renderer spells a word."
  - "failed/mismatch/crashed rows use the red cross mark; every other non-done result keeps its plan-time health mark, so a skipped or blocked row never turns green."
  - "Error text is the first line of the last install error, passed through sanitize_log_line and printed with markup disabled."
requirements-completed: [PLAN-04]
status: complete
duration: not measured
completed: 2026-10-17
---

# Phase 20 Plan 09: Summary head and outcome rows Summary

**`render_run_summary` prints the `Summary — {counts}` head and one outcome row per result, all built from the WORDS and RESULT_WORDS tables.**

## Performance

- **Duration:** not measured (the run resumed from a provider-failure WIP patch)
- **Tasks:** 2 of 2
- **Commits:** 2 task commits plus this summary commit

## Accomplishments

- `summary_head(outcomes)` returns `Summary — {summary_counts(outcomes)}`, and `render_run_summary` prints it as the first line, bold.
- `outcome_row_text(outcome, idw, width)` builds one finished row: mark, id, word, and the UI-SPEC text after the word, folded to the row budget.
- `running_row_text(row, idw, width)` builds the in-flight `>` row with the disposition review word.
- Every non-done result (failed, checksum mismatch, dependency failed, not attempted, crashed, manual, skipped, blocked) renders the exact Outcome copy table text.
- Error text (`failed — {first line}`, `crashed — {detail}`) is sanitized and rendered literally, never as markup (threat T-20-17).

## Task Commits

1. **Task 1: `Summary — …` is the first line and a done row shows its done word** - `50881de` (feat)
   - `summary_head`, `outcome_row_text`, `running_row_text`, `render_run_summary` in `installer/render.py`, with the first five tests in `tests/test_render.py`.
2. **Task 2: every non-done result renders its UI-SPEC row text, sanitized** - `9fd7bc1` (feat)
   - Parametrized per-result copy test, sanitized error test, in-flight mark test, mixed-run head test, and the long-detail folding test.

## TDD Evidence

RED run against the HEAD version of `installer/render.py` (the new tests importing the new names):

```
==================================== ERRORS ====================================
____________________ ERROR collecting tests/test_render.py _____________________
ImportError while importing test module '.../tests/test_render.py'.
tests/test_render.py:16: in <module>
    from installer.render import (
E   ImportError: cannot import name 'outcome_row_text' from 'installer.render'
=========================== short test summary info ============================
ERROR tests/test_render.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

Note on the TDD order: the WIP patch already contained the implementation for both tasks. The tests were corrected against it (see Deviations), and the RED run above was taken against HEAD to prove the tests exercise the new code. Task 1 was then split into its own commit from the first five tests; the task-2 tests went in the second commit.

## Verification

- `uv run pytest tests/test_render.py -q --no-cov` - all tests pass (116 collected in the final run).
- `make validate` - exit 0 on the task-1 tree and on the final tree (ruff check, ruff format, pyright, bandit, vulture, shellcheck, pre-commit hooks).
- `make test` - exit 0; 4858 passed, 4 skipped; coverage 96.01% (gate 90%).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two WIP test expectations contradicted the plan's mark rule**
- **Found during:** Task 2
- **Issue:** `test_outcome_row_text_per_result` built every row with `Health.MISSING` and reason `plan reason`, so the `skipped` cases expected a green check and the wrong reason text. The plan says skipped rows keep their plan-time health glyph.
- **Fix:** a skipped case now uses `Health.OK` and reason `already current`; other cases keep `Health.MISSING`.
- **Files modified:** tests/test_render.py
- **Commit:** 9fd7bc1

**2. [Rule 1 - Bug] Markup test passed `detail` to a `failed` outcome**
- **Found during:** Task 2
- **Issue:** a `failed` outcome takes its text from `install.errors`, never from `detail`, so the markup test could not see its input.
- **Fix:** the test uses a `crashed` outcome, which renders `detail`. The error-path sanitization is covered by `test_outcome_row_error_text_is_sanitized_and_literal`.
- **Files modified:** tests/test_render.py
- **Commit:** 9fd7bc1

**3. [Rule 3 - Blocking] Unused import failed lint**
- `installer/render.py` imported `Result` without using it. Removed; `ruff check` passes.

### Process notes

- `ruff format` reformatted the WIP test file (long lines in the mixed-run and error tests). Formatting only; no logic change.

## Issues for the orchestrator

- `codegraph explore` resolved symbols from the primary checkout, not this worktree (it warned about the mismatch). All reads were done from the worktree files directly.
- `20-09` does not touch `.planning/config.json`, STATE.md, ROADMAP.md, or RUN-LEDGER.md.
- `render_summary`, `render_audit` and `render_dependency_notice` are untouched, as the plan requires (20-14 deletes them).

## Self-Check: PASSED

- `installer/render.py` contains `def render_run_summary`, `def outcome_row_text`, `def running_row_text`, `def summary_head`: verified by the render test run.
- Commits `50881de` and `9fd7bc1` exist on `worktree-agent-ad21842fb77196652`.
