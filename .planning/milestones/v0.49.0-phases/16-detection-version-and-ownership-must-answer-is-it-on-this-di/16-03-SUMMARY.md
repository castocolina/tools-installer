---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 03
subsystem: doctor
tags: [rcclean, path, presence-guard, zsh, doctor]

requires:
  - phase: 15.8-fix-real-not-just-cosmetic-path-duplication-from-managed-blo
    provides: unguarded_path_writers and the strip-vs-report split
provides:
  - Quote-aware shared PATH-line generator with presence-guard tracking
  - Path-normalized writer matching aligned with audit_path
  - Trailing-comment, compound, and zsh array writers without widening the strip set
affects: [16-08]

actuals:
  tokens: 7737
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - One _path_line_targets generator owns managed-block skip, local assignment tracking, expansion, and guard context
    - Writer lookup uses Path equality, same as installer/doctor.py::audit_path, and returns the original managed_dirs member

key-files:
  created: []
  modified:
    - installer/rcclean.py
    - tests/test_rcclean.py

key-decisions:
  - "A frame pushed by if/while/until/for/select/case governs the following lines. A same-line closer is frame-neutral."
  - "An && or || segment is presence-guarded only when an earlier non-assignment segment of that chain references PATH. An earlier assignment's own right-hand side does not count."
  - "zsh path=(...) is a writer and never a strip candidate. The strip set still requires one plain PATH assignment, column 0, and no presence guard."

patterns-established:
  - "_PathLine carries index and raw text for plan 16-08's in-place rewrite."
  - "_split_unquoted is quote-aware and does not split on parentheses or doubled semicolons. shellrc's quote-blind splitter stays separate."

requirements-completed: [D-21]

coverage:
  - id: D1
    description: "A presence-guarded if, Fedora's stock header, and pnpm's multi-line case are not writers. A directory-existence if still is."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_guarded_if_not_reported"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_fedora_presence_guard_not_reported"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_pnpm_case_block_not_reported"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_dir_test_if_reported"
        status: pass
    human_judgment: false
  - id: D2
    description: "Trailing-slash and double-slash writers match the managed directory. Relative and empty segments never match."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_trailing_slash_writer_is_normalized"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_double_slash_writer_is_normalized"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_relative_or_empty_segment_never_matches"
        status: pass
    human_judgment: false
  - id: D3
    description: "Trailing comment, semicolon, &&/||, one-line if, and zsh path arrays are writers. Compound shapes and zsh arrays are not strip candidates."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_trailing_comment_is_a_writer_not_a_strip_candidate"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_one_line_presence_idiom_is_not_a_writer"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_zsh_array_line_is_not_a_strip_candidate"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both scanners share _path_line_targets. A guarded line is never a strip candidate, and a column-0 writer after a closed block still is."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_after_block_shape_still_reported"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_writer_nested_loop_inside_guarded_if_not_reported"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_path_export_guard_output_never_flagged"
        status: pass
    human_judgment: false

duration: 37min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 03: Writer diagnosis Summary

**rcclean no longer names a presence-guarded PATH line as an unconditional writer, and it no longer misses trailing-slash, comment, compound, or zsh array writers.**

## Performance

- **Duration:** 37 min
- **Started:** 2026-10-10T10:00:00Z
- **Completed:** 2026-10-10T10:37:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- CR-01: a block whose condition references PATH is not a writer. A directory-existence test still is. Fedora's stock header and pnpm's multi-line case are not reported.
- WR-01: writer matching uses Path equality, so a trailing slash and a doubled slash match the managed directory. Empty and relative segments never match.
- WR-02 / IN-01 / IN-03: one quote-aware generator drives both scanners. Comment, semicolon, &&/||, and zsh array shapes are writers. The strip set did not widen.

## Task Commits

Each task was committed atomically:

1. **Task 1: presence-guarded if is not a writer, shared generator** - `7500c48` (feat)
2. **Task 2: Path-normalized matching** - `9389be9` (feat)
3. **Task 3: comment, compound, and zsh array shapes** - `8b7bc7d` (feat)

**Plan metadata:** this summary commit (`docs(16-03): summary for plan 16-03`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/rcclean.py` - `_PathLine`, `_path_line_targets`, `_split_unquoted`, `_ZSH_PATH_ARRAY`, Path lookup
- `tests/test_rcclean.py` - CR-01, WR-01, and WR-02 pins; function-local imports moved to the top

## Decisions Made

- `elif` replaces the open `fi` frame's condition in place. It does not push a second frame. `else` leaves the frame alone.
- A same-line `fi`/`esac`/`done` does not push. A nested `for`/`while` pushes its own `done` frame, so its closer cannot pop an outer `if`.
- An assignment segment never counts as a presence test. `[ -d dir ] && PATH=... && PATH=...` is still a writer for the second directory.
- Public signatures of `unguarded_path_writers` and `find_duplicate_path_lines` are unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Case-arm prefix is not stripped**
- **Found during:** Task 3 (segment match)
- **Issue:** The plan's matching rule anchors `_PATH_EXPORT` at the start of a segment. A case row that begins with a pattern label is therefore not a writer, even when the case word does not reference PATH. The frame-limit comment describes the opposite for those rows.
- **Fix:** Kept the anchored match. Trusted the matching rule over widening the parser. Real pnpm rows sit under a case word that references PATH, and the single-line guard is skipped because its first segment starts with `case`. A miss here is the safe direction: Doctor does not tell the user to edit a line the scanner cannot see.
- **Files modified:** installer/rcclean.py
- **Verification:** `test_writer_pnpm_case_block_not_reported` and `test_path_export_guard_output_never_flagged` passed
- **Committed in:** `8b7bc7d`

---

**Total deviations:** 1 auto-fixed (1 bug, conservative miss)
**Impact on plan:** No false writer was added. Plan 16-08 must not assume a pattern-labelled case row is in the writer set.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-08 can build the in-place guard rewrite on `_path_line_targets`. Each record has `index` and `text`.
- Do not strip a zsh array line. `simple` is false for it. The shortcut comment records that a quoted array element with a space mis-splits, and that 16-08 refuses zsh arrays.
- A multi-line case whose word does not reference PATH does not guard a plain assignment in its body. A row that starts with a pattern label is still invisible to the matcher.

## Self-Check: PASSED

- `grep -n 'def _path_line_targets' installer/rcclean.py` returned line 314.
- `grep -c '_managed_line_indices(lines)' installer/rcclean.py` printed 1.
- `grep -c 'from installer.rcclean import' tests/test_rcclean.py` printed 1.
- `grep -c 'def test_indented_writer_still_counts_as_a_writer' tests/test_rcclean.py` printed 0.
- `grep -n 'def _split_unquoted' installer/rcclean.py` returned line 162. `_ZSH_PATH_ARRAY` is defined and used.
- `grep -n 'Path(expanded)' installer/rcclean.py` returned the helper docstring and both lookups.
- `make validate` passed (ruff, format, pyright, bandit, vulture, shellcheck).
- `make test` passed: 3232 passed, 5 skipped, 95.99% coverage.
- `uv run pytest tests/test_rcclean.py tests/test_app.py tests/test_guidance.py tests/test_setup.py -q` passed before the full suite.

## Verification

- Task 1 RED: `test_writer_guarded_if_not_reported`, `test_writer_fedora_presence_guard_not_reported`, and both nested-loop cases failed because the guarded line was reported. After the generator they passed, along with `tests/test_shellrc.py` including `no_accumulating_path_build`.
- Task 2 RED: trailing-slash, double-slash, and relative-segment tests failed on string equality. After Path lookup they passed.
- Task 3 RED: comment, semicolon, `&&`/`||`, one-line dir-test if, assignment chain, and zsh array tests failed because those shapes were invisible. After the splitter they passed. The one-line presence idioms stayed unreported.
- `uv run pytest -q` completed at 100% with no FAILED line, then `make test` confirmed 3232 passed, 5 skipped.
