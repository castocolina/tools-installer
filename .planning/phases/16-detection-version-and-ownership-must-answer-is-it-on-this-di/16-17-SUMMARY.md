---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 17
subsystem: detection
tags: [rc-scanner, path-guard, heredoc, doctor]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: rc PATH scanner, guard_path_writers, and path_scan_rc_paths from plans 16-01..16-16
provides:
  - then/do-prefixed PATH lines are reported but never stripped
  - heredoc bodies and comment/quote closers are not shell statements
  - one-shot PATH prefixes are not writers; PATH replacement has its own refusal
  - a second guard of the same rc file gets a guard-specific refusal
  - an unreadable ~/.bashrc.d entry cannot abort the Doctor PATH scan
affects: [16-18, doctor, rc-guard]

actuals:
  tokens: 7493
  tasks: 6
  commits: 6

tech-stack:
  added: []
  patterns:
    - "reporting and stripping stay different questions: simple=False refuses a strip and a guard, but path_writer_lines still reports"
    - "heredoc openers are matched on the raw line; _code_text only checks that the << sits in code"

key-files:
  created: []
  modified:
    - installer/rcclean.py
    - installer/shellrc.py
    - installer/locations.py
    - tests/test_rcclean.py
    - tests/test_shellrc.py
    - tests/test_locations.py

key-decisions:
  - "A then/do prefix makes the segment non-simple; _command_text is unchanged so the report path still sees the assignment."
  - "backup_precondition defaults flow to consolidation, so that refusal text is byte-identical; only the guard call passes flow=guard."
  - "IN-13 stays accepted: a one-line if/elif still consults only the if condition and fails safe."

patterns-established:
  - "shortcut: heredoc scan tracks only the first opener and ignores numeric, dash-led, and spaced quoted delimiters"

requirements-completed: [D-21, D-22, D-23, D-24]

coverage:
  - id: D1
    description: "A then/do-prefixed PATH line is not a strip candidate and is still reported as not guardable."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_then_prefixed_path_line_is_not_a_strip_candidate"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_do_prefixed_path_line_is_not_a_strip_candidate"
        status: pass
    human_judgment: false
  - id: D2
    description: "Closer detection ignores comments and quotes; heredoc bodies are not PATH writers."
    requirement: D-22
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_commented_closer_keeps_the_body_presence_guarded"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_heredoc_body_is_not_a_path_writer"
        status: pass
    human_judgment: false
  - id: D3
    description: "A one-shot PATH= prefix is not a writer; a PATH replacement has its own refusal."
    requirement: D-23
    verification:
      - kind: unit
        ref: "tests/test_rcclean.py#test_one_shot_path_prefix_is_not_a_writer"
        status: pass
      - kind: unit
        ref: "tests/test_rcclean.py#test_path_replacement_has_its_own_refusal"
        status: pass
    human_judgment: false
  - id: D4
    description: "A second guard of the same rc file refuses with guard wording and leaves both files unchanged."
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_shellrc.py#test_second_guard_refuses_with_guard_wording_and_keeps_both_files"
        status: pass
    human_judgment: false
  - id: D5
    description: "An unreadable ~/.bashrc.d entry is skipped; the rest of the PATH scan is returned."
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_path_scan_skips_an_unreadable_bashrc_d_entry"
        status: pass
    human_judgment: false

duration: 30min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 17: rc scanner and guard gap closure Summary

**Closed WR-01, WR-02, IN-01, IN-02, IN-06, IN-11, and IN-14 so Doctor no longer strips a `then`/`do` line, guards heredoc data, or dead-ends a second guard with consolidation wording.**

## Performance

- **Duration:** 30 min
- **Started:** 2026-10-10T15:55:00-03:00
- **Completed:** 2026-10-10T16:24:53-03:00
- **Tasks:** 6
- **Files modified:** 6

## Accomplishments

- A column-0 `then`/`do` PATH line is no longer a strip candidate, and the guard flow refuses it as compound.
- Comment and quote closers no longer drop a presence guard; heredoc bodies of `<<`, `<<-`, `<<'EOF'`, and `<<"EOF"` are not writers.
- A one-shot `PATH=... cmd` is not a writer. `PATH=/m/bin` and `PATH=/a:/m/bin` say the line replaces PATH; a multi prepend that still references `$PATH` keeps the old text.
- A second guard of the same file names the earlier backup and how to proceed, without saying consolidation. An unreadable `~/.bashrc.d` entry is skipped.

## Task Commits

Each task was committed atomically:

1. **Task 1: WR-02 then/do strip candidate** - `a6cc70e` (fix)
2. **Task 2: IN-11 + IN-01 closer and heredoc** - `2c92291` (fix)
3. **Task 3: IN-02 + IN-14 prefix and replacement refusal** - `1316295` (fix)
4. **Task 4: WR-01 guard-specific refusal** - `79f859a` (fix)
5. **Task 5: IN-06 unreadable bashrc.d entry** - `cfd79c2` (fix)

## Finding map

| Finding | Commit | Note |
|---------|--------|------|
| WR-02 | `a6cc70e` | RED: `find_duplicate_path_lines` returned `[1]` for both fixtures |
| IN-11 | `2c92291` | RED: commented `fi` and quoted `fi` in a PATH condition left an unguarded record |
| IN-01 | `2c92291` | RED: heredoc body PATH lines were writers for all four openers |
| IN-02 | `1316295` | RED: `PATH=/m/bin:$PATH somecmd` and `PATH=$HOME/m/bin:$PATH env FOO=1 cmd` were writers |
| IN-14 | `1316295` | RED: no `_REFUSE_REPLACE`; replacement lines had no dedicated text |
| WR-01 | `79f859a` | RED: second guard said `consolidation to proceed` |
| IN-06 | `cfd79c2` | RED: `PermissionError` from `is_file()` aborted the scan |
| IN-13 | accepted | No code. Already in 16-REVIEW-DISPOSITION.md. Fails safe. |

## Files Created/Modified

- `installer/rcclean.py` - `_code_text`, heredoc skip, `_REFUSE_REPLACE`, then/do-aware `simple`, command-suffix skip
- `installer/shellrc.py` - `backup_precondition(..., flow=)` with a guard-only message
- `installer/locations.py` - `OSError`-tolerant `is_file` in `path_scan_rc_paths`
- `tests/test_rcclean.py` - RED-first coverage for WR-02, IN-11, IN-01, IN-02, IN-14
- `tests/test_shellrc.py` - second-guard refusal wording and fail-closed bytes
- `tests/test_locations.py` - unreadable snippet skipped; order unchanged without one

## Decisions Made

- Reporting still sees a `then`/`do` line (`_command_text` untouched). Only `simple` changes, so strip and guard agree and the line stays visible.
- Heredoc delimiter matching stays on the raw line. `_code_text` blanks quotes, so it cannot recover `<<'EOF'`.
- IN-13 is accepted, not fixed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 1 test line exceeded the 100-character limit**
- **Found during:** Task 2 (ruff, before the heredoc commit)
- **Issue:** `test_then_prefixed_path_line_is_still_reported_but_not_guardable` was 102 columns, so the task 1 tree failed ruff.
- **Fix:** Wrapped the call and amended the unpushed task 1 commit (`6ceedef` -> `a6cc70e`).
- **Files modified:** tests/test_rcclean.py
- **Verification:** `uv run ruff check` on that file, then the later `make validate`.
- **Committed in:** `a6cc70e`

**2. [Rule 2 - Missing critical] Quoted `fi` on a non-PATH `if` was not RED**
- **Found during:** Task 2
- **Issue:** `if [ -n "x fi y" ]; then` already returned an unguarded record, so that fixture could not prove the stack stayed open.
- **Fix:** Kept that fixture as a pin. Added a PATH condition containing `"x fi y"` (body must stay guarded) and an outer presence guard that a false closer would pop.
- **Files modified:** tests/test_rcclean.py
- **Verification:** both new tests failed before the fix (unguarded record / trailing writer) and pass after.
- **Committed in:** `2c92291`

---

**Total deviations:** 2 auto-fixed (1 lint, 1 test that did not fail for the stated reason)
**Impact on plan:** Both were required for a green gate and for a test that actually catches IN-11. No behavior beyond the findings.

### Verification wording

`grep -n 'flow=' installer/shellrc.py` matches only the guard call site. The signature is `flow: Literal["consolidation", "guard"] = "consolidation"`, which is not the substring `flow=`. The consolidation call does not pass `flow`. No `.codegraph/` index exists; symbols were read directly.

## Verification

- `make validate`: exit 0 (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- `make test`: exit 0. `3431 passed, 5 skipped in 331.27s (0:05:31)`. Coverage 95.87% (required 90%).

## Issues Encountered

- Codegraph is not indexed in this repo, so location used Read/Grep instead of `codegraph_explore`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 16-18 can start. These seven findings are fixed; IN-13 remains accepted.
- No rc file outside `tmp_path` was read or written. `make setup`, `make fix`, and `make uninstall` were not run.

## Self-Check

- `installer/rcclean.py`, `installer/shellrc.py`, `installer/locations.py` contain the planned helpers and the guard `flow="guard"` call.
- Commits `a6cc70e`, `2c92291`, `1316295`, `79f859a`, `cfd79c2` are on this branch.
- IN-13 is already `accepted` in `16-REVIEW-DISPOSITION.md`.

## Self-Check: PASSED

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
