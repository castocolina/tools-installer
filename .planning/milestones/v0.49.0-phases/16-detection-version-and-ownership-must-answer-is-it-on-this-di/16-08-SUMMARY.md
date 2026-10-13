---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 08
subsystem: doctor
tags: [rcclean, shellrc, path, backup, doctor]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: _path_line_targets and Path-normalized writer matching from plan 16-03
  - phase: 15.8-fix-real-not-just-cosmetic-path-duplication-from-managed-blo
    provides: create-exclusive byte-and-mode backup, snapshot identity check, path_export_guard
provides:
  - PathWriterLine records and path_writer_lines, with foreign-marker ownership and a guardability verdict
  - guard_path_writers, sharing _create_backup and _path_hazard with consolidate_shellrc
affects: [16-11]

actuals:
  tokens: 7727
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - Guardability is re-parsed from the raw line, not from _PathLine.targets
    - One _create_backup and one _path_hazard serve consolidation and the foreign-line rewrite

key-files:
  created: []
  modified:
    - installer/rcclean.py
    - installer/shellrc.py
    - tests/test_rcclean.py
    - tests/test_shellrc.py

key-decisions:
  - "A zsh path array is refused before the compound check, because 16-03 marks array lines simple=False."
  - "Every marker whose name starts with tools-installer is this project's own. path and source stay skipped; consolidated shellrc and shellrc stub are ordinary lines."
  - "An unresolved variable is recorded on _PathLine and refused before the colon split, or the multi-directory rule would claim it."

patterns-established:
  - "path_writer_lines is the only writer scanner. unguarded_path_writers groups its records."
  - "guard_path_writers rewrites in place, never deletes, and writes the .tools-installer.old backup before the file."

requirements-completed: [D-21, D-22, D-23]

coverage:
  - id: D1
    description: "A single foreign prepend is rewritten in place to path_export_guard, backed up byte-for-byte, and bash -n accepts the file. A second call with no guardable lines writes nothing."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_in_place_rewrites_one_foreign_bashrc_line"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_path_writer_lines_prepend_is_guardable"
        status: pass
    human_judgment: false
  - id: D2
    description: "A line inside another tool's marked block is not guardable and names that block. This project's own path block is skipped. A consolidated shellrc block is not foreign."
    requirement: D-22
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_marker_block_kitty_names_the_owner"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_marker_block_unterminated_conda_owns_every_following_line"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_consolidated_shellrc_block_is_not_foreign"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_marker_block_tools_installer_path_is_skipped"
        status: pass
    human_judgment: false
  - id: D3
    description: "Multi-directory, append, compound, zsh array, and unresolved lines are refused with their exact constants and are not guardable. An indented directory-existence if body is guardable."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_refuse_multi_directory"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_refuse_append_form"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_refuse_compound_line"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_refuse_zsh_array"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_refuse_unresolved_variable"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_indented_if_body_is_guardable"
        status: pass
    human_judgment: false
  - id: D4
    description: "The write refuses a stale scan, a raced write, a differing backup, a symlink, and non-UTF-8 bytes, leaving the rc file byte-identical. CRLF and mode 0600 are preserved. An indented if body still parses under bash and zsh."
    requirement: D-23
    verification:
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_refuses_when_the_file_changed_since_the_scan"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_refuses_when_the_file_changes_while_it_is_being_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_refuses_a_preexisting_backup_with_different_bytes"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_accepts_a_preexisting_backup_with_identical_bytes_and_mode"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_refuses_a_symlinked_bashrc"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_in_place_keeps_crlf"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_refuses_a_non_utf8_file"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_in_place_rewrites_an_indented_if_body"
        status: pass
      - kind: unit
        ref: "tests/test_shellrc.py#test_guard_preserves_mode_0600_on_the_file_and_the_backup"
        status: pass
    human_judgment: false

duration: 58min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 08: Guard-in-place write Summary

**A foreign single-directory PATH prepend is rewritten in place to `path_export_guard` after a shared byte-exact backup; another tool's marked block is named and never touched.**

## Performance

- **Duration:** 58 min
- **Started:** 2026-10-10T12:10:00Z
- **Completed:** 2026-10-10T13:08:33Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- D-21: `guard_path_writers` rewrites a guardable line at the same index. Nothing is deleted. `bash -n` and `zsh -n` accept an indented `if` body after the rewrite.
- D-22: a line inside `# >>> my-kitty PATH >>>` is not guardable and carries that block name. `tools-installer*` markers are not attributed to another tool.
- D-23: the original bytes and mode are saved to `<file>.tools-installer.old` through the same create-exclusive helper consolidation now calls. A stale file, a raced write, a differing backup, a symlink, and non-UTF-8 bytes refuse without changing the rc file.

## Task Commits

Each task was committed atomically:

1. **Task 1: guard one foreign ~/.bashrc line** - `373d934` (feat)
2. **Task 2: foreign marked blocks and the refusal set** - `6a9ded1` (feat)
3. **Task 3: write-path guardrails** - `94d0b90` (test)

**Plan metadata:** this summary commit (`docs(16-08): summary for plan 16-08`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/rcclean.py` - `PathWriterLine`, `path_writer_lines`, foreign-marker ownership, refusal constants, `_PathLine.unresolved`
- `installer/shellrc.py` - `PathGuardOutcome`, `guard_path_writers`, shared `_create_backup` and `_path_hazard`
- `tests/test_rcclean.py` - guardability, marker-block, and refusal pins
- `tests/test_shellrc.py` - in-place rewrite, backup, race, symlink, CRLF, encoding, mode, and real-shell syntax checks

## Decisions Made

- Guardability is derived by re-parsing the raw line. `_PathLine.targets` is a flat set of expanded segments and cannot tell prepend from append or multi-directory.
- `_create_backup` returns whether this call created the sibling. A raced refusal unlinks only that backup, so a pre-existing identical backup is left alone.
- `consolidation_precondition` still returns its original symlink sentences. `_path_hazard` supplies the non-regular wording and the guard path's symlink refusal. The substrings `symlink` and `regular file` are unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Nested foreign markers stay owned**
- **Found during:** Task 2 (foreign marked blocks)
- **Issue:** Mirroring `_managed_line_indices`' single pointer overwrites the open name on an inner begin. A nested `# >>> a >>>` / `# >>> b >>>` / `# <<< b <<<` then drops the outer owner, so a line inside foreign block `a` could be rewritten.
- **Fix:** `_foreign_block_owners` keeps a name stack. A mismatched end closes nothing. An unterminated block still runs to EOF.
- **Files modified:** installer/rcclean.py
- **Verification:** kitty, unterminated conda, and mismatched-end tests passed. Nested ownership is not separately pinned.
- **Committed in:** `6a9ded1`

**2. [Rule 1 - Bug] Unresolved flag is set where the value is parsed**
- **Found during:** Task 2 (refusal set)
- **Issue:** The plan says set `_PathLine.unresolved` in `_path_line_targets`. The assignment value and the file-local env are both in `_judge_line`. Setting the flag later would miss an assignment made earlier in the same file.
- **Fix:** `_judge_line` sets `unresolved`. `_path_line_targets` yields that record. The default is False, so existing constructions stay valid.
- **Files modified:** installer/rcclean.py
- **Verification:** `test_refuse_unresolved_variable` passed, including the two-segment `$FOO/bin:$PATH` case that yields no record.
- **Committed in:** `6a9ded1`

**3. [Rule 3 - Blocking] Private refusal constants cannot be imported under pyright strict**
- **Found during:** Task 2 (refusal tests)
- **Issue:** `reportPrivateUsage` rejects `from installer.rcclean import _REFUSE_MULTI`. The plan requires tests to assert those exact constants.
- **Fix:** Tests compare `rcclean._REFUSE_*` with the repo's existing `# pyright: ignore[reportPrivateUsage]` on the assertion line.
- **Files modified:** tests/test_rcclean.py
- **Verification:** `uv run pyright` reported 0 errors.
- **Committed in:** `6a9ded1`

---

**Total deviations:** 3 auto-fixed (2 bug, 1 blocking)
**Impact on plan:** All three keep the specified behavior. No scope creep. Nested foreign ownership is implemented and not separately tested.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-11 can call `path_writer_lines` and `guard_path_writers`. A record with `guardable=False` is not rewritten. A foreign record's `block_owner` and `refusal` are the strings Doctor should show.
- Do not pass a hand-built record whose `text` dropped a trailing `\r`. Build CRLF records with `path_writer_lines` on the file text.
- A nested foreign block is owned by the innermost open name. That case has no dedicated test.

## Self-Check: PASSED

- `grep -n 'def guard_path_writers\|def _create_backup\|def _path_hazard' installer/shellrc.py` returned three lines (828, 979, 1145).
- `grep -c 'O_EXCL' installer/shellrc.py` printed 1.
- `grep -n '_FOREIGN_BEGIN\|_foreign_block_owners' installer/rcclean.py` shows the definition and its use in `path_writer_lines`.
- `test_consolidated_shellrc_block_is_not_foreign` passed. The kitty test asserts `block_owner == "my-kitty PATH"` and `guardable is False`.
- `zsh` is at `/home/linuxbrew/.linuxbrew/bin/zsh`, so `test_guard_in_place_rewrites_an_indented_if_body` ran `zsh -n`.
- `make validate` passed (ruff, format, pyright, bandit, vulture, shellcheck).
- `uv run pytest tests/test_rcclean.py tests/test_shellrc.py tests/test_shell_scripts_path.py -q` passed.
- `uv run pytest -q` passed: 3306 passed, 5 skipped, in 319.08s.

## Verification

- Task 1 RED: collecting the new tests raised `ImportError` for `path_writer_lines` and `guard_path_writers`. After the write path, the `-k "guard_in_place or path_writer_lines or consolidat"` run passed, then `tests/test_rcclean.py` and `tests/test_shellrc.py` passed together.
- Task 2 RED: collection raised `ImportError` for `_REFUSE_APPEND`. After the constants and foreign-block detector, the `-k "marker_block or refus or guardable"` run passed (14 tests), then the full `tests/test_rcclean.py` passed.
- Task 3: the nine guardrail tests passed on the Task 1 write path. Every refusal test asserts `read_bytes()` equality.
- `make validate` passed after Task 3's format fix, before the Task 3 commit.
- Full suite: 3306 passed, 5 skipped. No FAILED line.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
