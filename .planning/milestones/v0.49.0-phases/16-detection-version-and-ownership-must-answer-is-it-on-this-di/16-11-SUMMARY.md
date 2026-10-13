---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 11
subsystem: ui
tags: [doctor, path, guard, textual, rcclean]

requires:
  - phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
    provides: duplicate_path_writers seam (16-04); guard_path_writers and PathWriterLine (16-08)
provides:
  - One composition-time writer scan shared by the CLI grouping and the TUI Doctor
  - Per-file ConfirmGuardFile opt-in after Doctor's PATH fix, with a fresh re-scan
  - Record-aware guidance that names foreign blocks and offers only guardable lines
affects: [16-16]

actuals:
  tokens: 13952
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - Doctor apply re-scans writer records after the PATH fix, then confirms one file at a time
    - Modal body text is Text(), never from_markup, because rc lines are untrusted

key-files:
  created: []
  modified:
    - installer/rcclean.py
    - installer/app.py
    - installer/guidance.py
    - installer/wizard_app.py
    - tests/test_wizard_app.py
    - tests/test_guidance.py
    - tests/test_rcclean.py
    - tests/test_app.py

key-decisions:
  - "The guard queue is built from the post-fix re-scan, not the records captured when the screen was composed."
  - "A file is offered only when it has at least one guardable record. Foreign-block lines are named in guidance and never queued."
  - "duplicate_path_writers still returns immediately when nothing is duplicated, so the retargeted counting test stays a zero-call assertion."

patterns-established:
  - "DoctorScreen narrows app to UnifiedApp under TYPE_CHECKING, same as UninstallScreen and PoliciesScreen, before calling push_screen."

requirements-completed: [D-21, D-22, D-23, D-24]

coverage:
  - id: D1
    description: "Doctor apply runs the PATH fix, then confirms each guardable foreign file one at a time. Yes calls guard_file with the post-fix record. No edits nothing and says skipped."
    requirement: D-24
    verification:
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_yes_edits_one_file_and_reports_it"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_no_skips_without_calling_guard_file"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_queue_uses_post_fix_rescan"
        status: pass
    human_judgment: false
  - id: D2
    description: "A foreign marked block is named and not offered. A guardable line offers an in-place guard and the backup suffix. An unguardable line keeps the edit remedy and its refusal."
    requirement: D-22
    verification:
      - kind: unit
        ref: "tests/test_guidance.py#test_foreign_block_writer_is_named_and_not_offered"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_guardable_writer_offers_an_in_place_guard_and_a_backup"
        status: pass
      - kind: unit
        ref: "tests/test_guidance.py#test_unguardable_writer_keeps_the_edit_remedy_and_the_refusal"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_screen_guidance_names_a_foreign_block"
        status: pass
    human_judgment: false
  - id: D3
    description: "A refused or declined file does not block the next file. A file with no guardable line gets no modal. Enter after a finished apply does not restart the chain."
    requirement: D-24
    verification:
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_chain_confirms_files_in_record_order"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_chain_continues_after_a_refused_file"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_chain_skips_a_file_with_no_guardable_line"
        status: pass
      - kind: automated_ui
        ref: "tests/test_wizard_app.py#test_doctor_guard_chain_does_not_restart_after_apply"
        status: pass
    human_judgment: false
  - id: D4
    description: "The TUI composition scans writer lines once. The CLI grouping still skips the scan when nothing is duplicated and reads only the given files."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_doctor_composition_scans_writer_lines_once"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_writer_scan_skipped_when_nothing_is_duplicated"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_writer_scan_reads_only_the_given_files"
        status: pass
    human_judgment: false

duration: 40min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 11: Doctor per-file PATH guard Summary

**Doctor's apply step confirms each foreign rc file before guarding its PATH lines, names blocks it will not touch, and re-scans after the PATH fix so line indexes stay current.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-10-10T14:03:00Z
- **Completed:** 2026-10-10T14:43:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Pressing apply runs the existing PATH fix, then walks guardable foreign files one at a time. Each file gets its own modal with the before/after line and the `.tools-installer.old` backup path. Declining a file edits nothing.
- The queue comes from a re-scan taken after the fix, so a managed block that grew cannot shift a foreign line out from under its record. A second re-scan after the chain refreshes guidance.
- Guidance names a foreign block and says to fix it in that tool. Guardable lines offer an in-place guard. Unguardable lines keep the edit remedy plus the refusal. Omitting writer records keeps today's next step, with the presence-check wording.
- `path_writer_lines_for` is the one composition-time scan. `duplicate_path_writers` groups that result. The two helpers that no longer had a production caller are gone; their tests call the survivors and keep the same assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1: scan, modal, and apply chain** - `6b18a13` (feat)
2. **Task 2: record-aware guidance and dead-helper removal** - `1100cf1` (feat)
3. **Task 3: multi-file chain ordering and failure isolation** - `dfdea11` (test)

Follow-ups found by the gates, not new tasks:

- `cc849e4` (style) — ruff format on the foreign-block guidance test
- `6a898bb` (fix) — DoctorScreen narrows `app` so `push_screen` type-checks

**Plan metadata:** pending summary commit (docs)

## Files Created/Modified

- `installer/rcclean.py` — `_read_rc_texts`, `scan_rc_path_writer_lines`, `group_writer_lines`; deleted the two unused grouping/scan wrappers
- `installer/app.py` — `path_writer_lines_for`; `duplicate_path_writers` groups that result
- `installer/guidance.py` — `writer_lines` chooses the per-directory next step
- `installer/wizard_app.py` — `ConfirmGuardFile`, Doctor apply chain, one composition-time scan
- `tests/test_wizard_app.py` — pilots for yes/no, post-fix index, multi-file isolation
- `tests/test_guidance.py` — foreign-block, guardable, refusal, and regression wording
- `tests/test_rcclean.py` — migrated assertions onto `group_writer_lines`
- `tests/test_app.py` — counting test retargeted at `path_writer_lines_for`

## Decisions Made

- The guard chain runs whether or not the PATH fix set `self.error`. The error still renders first. The re-scan reads whatever the fix left on disk.
- Modal text is built with `Text()`, not `from_markup`. Rc file text is untrusted.
- An empty post-fix queue does not push a modal and does not add guard-result lines. That is today's apply behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] DoctorScreen.app was App[Unknown]**
- **Found during:** validate after Task 3
- **Issue:** `MessagePump.app` is `App[Unknown]`. `push_screen` on DoctorScreen failed pyright. UninstallScreen and PoliciesScreen already narrow it.
- **Fix:** Added the same `TYPE_CHECKING` `app -> UnifiedApp` property, and returned the callback from a method annotated `Callable[[bool | None], None]`.
- **Files modified:** `installer/wizard_app.py`
- **Verification:** `uv run pyright` reported 0 errors. Guard pilots still passed.
- **Committed in:** `6a898bb`

**2. [Rule 1 - Bug] format gate failed on a wrapped test string**
- **Found during:** `make validate` after Task 2
- **Issue:** ruff format wanted the foreign-block refusal string on one line.
- **Fix:** Reformatted `tests/test_guidance.py`.
- **Files modified:** `tests/test_guidance.py`
- **Verification:** `ruff format --check` passed on the next validate.
- **Committed in:** `cc849e4`

**3. [Rule 2 - Missing] counting test would call the scanner if the short-circuit moved**
- **Found during:** Task 1
- **Issue:** The plan rebuilds `duplicate_path_writers` as `group_writer_lines(path_writer_lines_for(...))` and also says the retargeted counting test stays green with zero calls. A literal always-call would increment the counter.
- **Fix:** Both functions return immediately when `report.duplicated` is empty. The non-empty path is the rebuild the plan describes.
- **Files modified:** `installer/app.py`
- **Verification:** `test_writer_scan_skipped_when_nothing_is_duplicated` passed.
- **Committed in:** `6b18a13`

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 format, 1 test-compat short-circuit)
**Impact on plan:** No scope creep. The type narrowing is the existing screen pattern. The short-circuit preserves the 16-04 zero-call test the plan required to stay green.

## Issues Encountered

- Task 3's four pilots passed against the Task 1 chain with no production change. The only later production edit was the pyright narrowing.
- `test_scan_rc_path_writers_reads_real_files_and_skips_unreadable` was renamed to `test_writer_scan_reads_real_files_and_skips_unreadable`. The word-match gate would not have matched the old name. Assertions are unchanged. History of the deleted helpers is recorded here, not in installer/ or tests/.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Doctor apply can guard a foreign file only after that file's own yes, and it reports guarded, skipped, or refused per file.
- Plan 16-16 can treat D-21..D-24 as wired. The CLI doctor stays report-only, as this plan specified.

## Self-Check

Observed after the last production commit:

- `grep -n 'class ConfirmGuardFile' installer/wizard_app.py` returned one line.
- `grep -n 'def path_writer_lines_for' installer/app.py` returned one line.
- `grep -n 'scan_rc_path_writers' installer/app.py` returned nothing.
- `grep -c 'def group_writer_lines' installer/rcclean.py` printed 1.
- `grep -n "fix it in that tool" installer/guidance.py` returned one line.
- `grep -c 'adds it unconditionally' installer/guidance.py` printed 0.
- `grep -rnwE 'unguarded_path_writers|scan_rc_path_writers' installer/ tests/ setup.py` returned nothing.
- `make validate` passed: ruff check, ruff format, pyright (0 errors), bandit, vulture, shellcheck.
- `uv run pytest tests/test_wizard_app.py tests/test_app.py tests/test_guidance.py tests/test_rcclean.py tests/test_render.py -q` passed.
- `uv run pytest -q` passed (skips only, no failures).

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
