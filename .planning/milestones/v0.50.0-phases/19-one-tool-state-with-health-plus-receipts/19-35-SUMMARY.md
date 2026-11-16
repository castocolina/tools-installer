---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "35"
subsystem: infra
tags: [fifo, read-capped, shim, terminal-shell, skill-lock, project-pack]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "read_capped, the non-blocking regular-file reader added by 19-28"
provides:
  - "is_our_shim and the terminal config read refuse a FIFO, a directory or an oversize file at once"
  - "the skill lock read returns unknown instead of blocking, and one unreadable runtime hides only itself"
affects: [19-36, refresh-pass, skill-worker]

actuals:
  tokens: 5500
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A refresh-pass read of a user-writable path goes through read_capped with follow_symlinks=True"
    - "An unlistable runtime is inconclusive for that runtime only; the reinstall targets keep every other runtime"

key-files:
  created: []
  modified:
    - installer/guards.py
    - installer/terminal_shell.py
    - installer/skill_lifecycle.py
    - tests/test_guards.py
    - tests/test_terminal_shell.py
    - tests/test_skill_lifecycle.py

key-decisions:
  - "Followed the plan: three readers switched to read_capped and the dead unreadable branch in inspect_project_pack deleted"

patterns-established:
  - "A FIFO, a directory or a file over the cap is not our shim, a refused terminal config, or an unknown skill lock"
  - "not installed in {repo} is claimed only when every runtime dir was readable and none held an install"

requirements-completed: [STATE-07, STATE-04, STATE-06]

coverage:
  - id: D1
    description: "is_our_shim returns False at once for a FIFO at a guarded PATH name"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_guards.py#test_is_our_shim_never_blocks_on_a_fifo"
        status: pass
    human_judgment: false
  - id: D2
    description: "A FIFO at kitty.conf makes the terminal dry run raise TerminalShellError at once, and the FIFO stays in place"
    requirement: STATE-07
    verification:
      - kind: unit
        ref: "tests/test_terminal_shell.py#test_dry_run_never_blocks_on_a_fifo_config"
        status: pass
    human_judgment: false
  - id: D3
    description: "A FIFO at ~/.agents/.skill-lock.json answers unknown for the skill probe at once"
    requirement: STATE-06
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_skills_lock_fifo_never_blocks"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unlistable Claude install in a repo no longer hides OpenCode's empty-install reason and reinstall step"
    requirement: STATE-06
    verification:
      - kind: unit
        ref: "tests/test_skill_lifecycle.py#test_unreadable_runtime_never_hides_another_runtimes_empty_install"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 35: FIFO-safe reads and per-runtime repo reports Summary

**The shim check, the terminal config read and the skill lock read go through the capped reader, and one unlistable runtime no longer hides another runtime's empty install.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-10-17T00:00:40Z
- **Completed:** 2026-10-17T00:09:46Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `is_our_shim` reads at most 8192 bytes through `read_capped` with `follow_symlinks=True`, so a FIFO, a directory, an oversize file, a missing path or an unreadable one is not our shim and the call returns at once.
- `_read_text` reads at most 1 MiB the same way: a missing file or parent is still `""`, and a FIFO, a directory or an oversize file raises `TerminalShellError` with the exact refusal text the refresh row shows.
- `_skills_lock_skills` reads at most 1 MiB: a missing lock is `{}` as before, and a FIFO, an oversize file, an unreadable file or a non-UTF-8 file is `None`, so the probe answers `unknown`.
- `inspect_project_pack` claims `not installed` only when no dir is unreadable; an unlistable runtime stays out of the reinstall targets while every other runtime keeps its own empty reason and step.

## Task Commits

Each task was committed atomically (test and code together; RED output recorded below, never committed):

1. **Task 1: the shim check and the terminal config read never block on a FIFO (M6, IN2-02)** - `2bc1df0` (fix)
2. **Task 2: the skill lock read never blocks; one unreadable runtime never hides another's empty install (M6, L2)** - `b0b740f` (fix)

**Plan metadata:** this commit (docs: plan summary)

## TDD RED evidence

The earlier run of this plan committed both tasks, then stopped before writing this summary, and it left no saved RED transcript. The RED commands were never re-run here: on this tree they pass, so a re-run would not reproduce the failure. The failures below are what the plan's action section predicts for the old tree, not output captured from a pytest run.

### Task 1

`uv run pytest tests/test_guards.py tests/test_terminal_shell.py -q --no-cov -k never_blocks_on_a_fifo` was expected to exit 1 after both tests waited out their 5-second join, failing on `not thread.is_alive()`.

### Task 2

`uv run pytest tests/test_skill_lifecycle.py -q --no-cov -k "skills_lock_fifo or unreadable_runtime_never_hides"` was expected to exit 1: the lock test failing on the thread still being alive after 5 seconds, and the repo test missing the `OpenCode install in proj is empty` reason.

## Verify-command results

- Task acceptance greps, all matching the plan: `read_capped(path, _SHIM_MAX_BYTES, follow_symlinks=True)` is 1 and `text = path.read_text()` is 2 in `installer/guards.py`; `read_capped(path, _CONFIG_MAX_BYTES, follow_symlinks=True)` is 1, `read_bytes()` is 0 and the 1 MiB refusal text is 1 in `installer/terminal_shell.py`; `_SKILL_LOCK_CAP = 1 << 20` is 1, the skill-lock `read_capped` is 1, `read_text(encoding="utf-8")` is 0, `if not installed and not empty and not unreadable:` is 1 and `^        if unreadable:` is 0 in `installer/skill_lifecycle.py`.
- `make test` on the final tree: 4599 passed, 4 skipped, coverage 95.99% (required 90%), exit 0, in 84.15s.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` exit 0: no dependency change.
- `make validate` was not re-run on this resume; both task commits passed the pre-commit hook, and the tree is unchanged since `b0b740f`.

## Files Created/Modified

- `installer/guards.py` — `is_our_shim` reads through `read_capped`; a non-regular or oversize file is not our shim
- `installer/terminal_shell.py` — `_read_text` caps at 1 MiB and refuses a FIFO, a directory or an oversize file
- `installer/skill_lifecycle.py` — capped skill lock read; the per-repo `unreadable` branch deleted
- `tests/test_guards.py` — `test_is_our_shim_never_blocks_on_a_fifo`
- `tests/test_terminal_shell.py` — `test_dry_run_never_blocks_on_a_fifo_config`
- `tests/test_skill_lifecycle.py` — `test_skills_lock_fifo_never_blocks`, `test_unreadable_runtime_never_hides_another_runtimes_empty_install`

## Decisions Made

None - followed plan as specified.

## Deviations from Plan

None - plan executed exactly as written.

---

**Total deviations:** 0
**Impact on plan:** No scope change. Both tasks landed in the files the plan lists.

## Issues Encountered

The first run of this plan committed both tasks (`2bc1df0`, `b0b740f`) and then stalled before writing the summary, leaving a clean tree. This run verified the commits against the plan, ran `make test` once, and wrote the summary. It did not re-run the RED commands, because the committed tree is already green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- M6 (IN2-02) and L2 (P2-2) are closed: no read the refresh pass makes can block on a FIFO at a guarded PATH name, a terminal config or `~/.agents/.skill-lock.json`, and a repo report keeps every runtime's own facts.
- The two report reads that still call `path.read_text()` in `installer/guards.py` run only after `is_our_shim` returned True, as the plan requires.
- No dependency change. No host mutation.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
