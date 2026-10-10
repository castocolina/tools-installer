---
phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di
plan: 04
subsystem: doctor
tags: [doctor, path, rc-scan, zsh, test-isolation]

requires:
  - phase: 15.8-fix-real-not-just-cosmetic-path-duplication-from-managed-blo
    provides: scan_rc_path_writers and the untested Doctor writer wiring WR-03..WR-05 and IN-02 close
provides:
  - Public injectable duplicate_path_writers seam used by both Doctor routes
  - Autouse $ZSH and $ZDOTDIR clearing
  - Read-only scan set covering ~/.bashrc.d/* and ZDOTDIR-relative zsh startup files
affects: [16-08, 16-11]

actuals:
  tokens: 3229
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - Doctor IO stays behind one injected callable; the TUI imports that function instead of re-implementing the short-circuit
    - Shell-location env ($ZDOTDIR, $ZSH) is cleared once in the autouse fixture

key-files:
  created: []
  modified:
    - installer/app.py
    - installer/wizard_app.py
    - installer/locations.py
    - tests/conftest.py

key-decisions:
  - "The TUI assertion narrows with isinstance(screen, DoctorScreen) so pyright can see guidance. The line does not contain DoctorScreen(."
  - "CLI helper tests are named test_writer_scan_* so they do not add extra _duplicate_path_writers substring hits. The mandated TUI test name still contains that substring."

patterns-established:
  - "duplicate_path_writers(report, *, rc_paths=None, env=None) is the one scoping function. Defaults are evaluated in the body."
  - "run_doctor takes duplicate_writers like its other IO seams."

requirements-completed: [D-21, D-24]

coverage:
  - id: D1
    description: "run_doctor renders an injected rc writer, and duplicate_path_writers skips the scan when nothing is duplicated and reads only the given files."
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_app.py#test_run_doctor_names_the_injected_rc_writer"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_writer_scan_skipped_when_nothing_is_duplicated"
        status: pass
      - kind: unit
        ref: "tests/test_app.py#test_writer_scan_reads_only_the_given_files"
        status: pass
    human_judgment: false
  - id: D2
    description: "The TUI Doctor composition calls duplicate_path_writers. A monkeypatched fake's rc path appears in rendered guidance."
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_wizard_app.py#test_doctor_tui_route_uses_duplicate_path_writers_seam"
        status: pass
    human_judgment: false
  - id: D3
    description: "$ZSH is cleared by the autouse fixture. The live omz wiring test still passes when the invoking shell exports ZSH."
    requirement: D-24
    verification:
      - kind: unit
        ref: "tests/test_setup.py#test_zsh_is_cleared_without_a_local_delenv"
        status: pass
      - kind: unit
        ref: "tests/test_setup.py#test_build_app_wires_live_omz_availability_and_one_terminal_sync_closure"
        status: pass
    human_judgment: false
  - id: D4
    description: "path_scan_rc_paths includes sorted ~/.bashrc.d files, .zshenv, .zlogin, and ZDOTDIR-relative zsh files, and creates nothing."
    requirement: D-21
    verification:
      - kind: unit
        ref: "tests/test_locations.py#test_path_scan_includes_zsh_startup_files_and_sorted_bashrc_d"
        status: pass
      - kind: unit
        ref: "tests/test_locations.py#test_path_scan_missing_bashrc_d_adds_nothing"
        status: pass
      - kind: unit
        ref: "tests/test_locations.py#test_path_scan_honors_zdotdir_for_zsh_startup_files"
        status: pass
    human_judgment: false

duration: 28min
completed: 2026-10-10
status: complete
---

# Phase 16 Plan 04: Doctor Writer Seam Summary

**Doctor names the rc file that duplicates a PATH entry through one public, injectable seam, and the read-only scan now covers Fedora's ~/.bashrc.d and ZDOTDIR zsh startup files.**

## Performance

- **Duration:** 28 min
- **Started:** 2026-10-10T10:38:00Z
- **Completed:** 2026-10-10T11:05:37Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- WR-03 / WR-04: `duplicate_path_writers` is the one scoping function. `run_doctor` injects it. The TUI calls it instead of inlining the scan.
- WR-05: the autouse fixture clears `$ZSH` next to `$ZDOTDIR`. `_sandbox` no longer has its own `delenv`.
- IN-02: the read-only scan includes `~/.bashrc.d/*` (sorted, regular files only), `.zshenv`, `.zlogin`, and ZDOTDIR-relative zsh files.

## Task Commits

Each task was committed atomically:

1. **Task 1: one public Doctor writer seam** - `92b836c` (feat), `0c112d2` (fix: pyright narrow)
2. **Task 2: `$ZSH` isolation in the autouse fixture** - `377083e` (test)
3. **Task 3: wider read-only scan set** - `00296e1` (feat)

**Plan metadata:** this summary commit (`docs(16-04): summary for plan 16-04`)

TDD red was observed and not committed separately. A failing-test commit would be a knowingly broken tree.

## Files Created/Modified

- `installer/app.py` - public `duplicate_path_writers`; `run_doctor` kwarg `duplicate_writers`
- `installer/wizard_app.py` - Doctor composition calls `duplicate_path_writers(report)`; unused `os` / scan imports dropped
- `installer/locations.py` - `path_scan_rc_paths` covers `.bashrc.d` and ZDOTDIR zsh files
- `tests/conftest.py` - autouse fixture `no_shell_location_env`
- `tests/test_app.py` - CLI seam and scoping tests
- `tests/test_wizard_app.py` - `test_doctor_tui_route_uses_duplicate_path_writers_seam`
- `tests/test_setup.py` - `$ZSH` assertion; local `delenv` removed
- `tests/test_locations.py` - scan-set tests

## Decisions Made

- Narrow the TUI screen with `isinstance` before reading `guidance`. Pyright types `app.screen` as `Screen[object]`.
- Name the CLI helper tests `test_writer_scan_*`. The mandated TUI name already contains the substring `_duplicate_path_writers`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pyright cannot see guidance on the base screen**
- **Found during:** Task 1, at `make validate` after the task commit
- **Issue:** `app.screen.guidance` is an unknown attribute on `Screen[object]`.
- **Fix:** `assert isinstance(screen, DoctorScreen)` then read `screen.guidance`. The acceptance grep is `DoctorScreen(`, which this line does not contain (`grep -c` printed 0).
- **Files modified:** tests/test_wizard_app.py
- **Verification:** `uv run pyright` reported 0 errors. The TUI test still passed.
- **Committed in:** `0c112d2`

**2. [Rule 3 - Blocking] Acceptance grep and the mandated test name collide**
- **Found during:** Task 1 acceptance
- **Issue:** `test_doctor_tui_route_uses_duplicate_path_writers_seam` contains the substring `_duplicate_path_writers`, so `grep -rn '_duplicate_path_writers' installer/ tests/` matches that one test line. Renaming it would violate the review disposition.
- **Fix:** Left the mandated name. Named the other new tests so they do not add hits. The private function is gone from `installer/`.
- **Files modified:** tests/test_app.py
- **Verification:** `grep -n 'def duplicate_path_writers' installer/app.py` returned line 308. `grep scan_rc_path_writers installer/wizard_app.py` returned nothing.
- **Committed in:** `92b836c`

---

**Total deviations:** 2 auto-fixed (1 type narrow, 1 acceptance-grep collision left as specified)
**Impact on plan:** Both routes stay pinned. Plan 16-11 can still retarget the mandated test name.

## Issues Encountered

- A `git commit --amend` folded the pyright fix into the Task 3 commit by mistake. `git reset --soft` restored `00296e1` and the fix was recommitted as `0c112d2`. Nothing was pushed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 16-08 and 16-11 can add guard-in-place candidates beside `duplicate_path_writers` and thread them through the same `wizard_app.py` composition point.
- The TUI test monkeypatches `installer.wizard_app.duplicate_path_writers`. Plan 16-11 already says to retarget that patch.

## Self-Check: PASSED

- `grep -n 'def duplicate_path_writers' installer/app.py` returned line 308.
- `grep -c 'scan_rc_path_writers' installer/wizard_app.py` printed 0.
- `grep -A30 'def test_doctor_tui_route_uses_duplicate_path_writers_seam' tests/test_wizard_app.py | grep -c 'DoctorScreen('` printed 0. The test builds through `_app(`.
- `grep -n 'delenv("ZSH"' tests/conftest.py` returned one line. `tests/test_setup.py` had none. `no_zdotdir` is gone from tests.
- `grep -n '.bashrc.d' installer/locations.py` returned the docstring and the guarded glob.
- Mutation check: replacing `duplicate_writers(report)` with `{}` failed `test_run_doctor_names_the_injected_rc_writer`. Reverted before commit.
- `make validate` passed (ruff, format, pyright 0 errors, bandit, vulture, shellcheck).
- Targeted pytest (`tests/test_app.py tests/test_wizard_app.py tests/test_setup.py tests/test_locations.py tests/test_omz.py -q`) passed with no FAILED lines.
- `uv run pytest -q` exited 0. Progress reached 100%. The count line was not in the redirected stdout; the exit code was.

## Verification

- Task 1 RED: `duplicate_writers` was an unexpected keyword, `duplicate_path_writers` did not import, and the TUI monkeypatch target was missing. After the seam, the doctor/duplicate filter passed.
- Task 2 RED: with `ZSH=/nonexistent/.oh-my-zsh`, `test_zsh_is_cleared_without_a_local_delenv` failed because `ZSH` was still in `os.environ`. After the fixture rename, `ZSH=/nonexistent/.oh-my-zsh uv run pytest tests/test_setup.py tests/test_omz.py -q` passed.
- Task 3 RED: `.zshenv` and ZDOTDIR `.zprofile` were absent from the scan. After the wider list, `tests/test_locations.py` and `tests/test_app.py` passed.

---
*Phase: 16-detection-version-and-ownership-must-answer-is-it-on-this-di*
*Completed: 2026-10-10*
