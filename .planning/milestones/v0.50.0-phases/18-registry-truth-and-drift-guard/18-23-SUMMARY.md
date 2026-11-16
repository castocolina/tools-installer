---
phase: 18-registry-truth-and-drift-guard
plan: "23"
subsystem: testing
tags: [smoke, subprocess, render, registry, utf-8]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: plans 18-21/18-22 registry verification groundwork
provides:
  - OSError and loader text on smoke failures
  - Bounded single-line smoke reasons with UTF-8 replacement decoding
  - Earlier ladder method errors in failure reports
affects: [install ladder UX, version probes via run_output]

actuals:
  tokens: 3400
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Captured child output decodes as UTF-8 with errors=replace"
    - "Smoke failure reason prefers first _LOADER_ERROR line, else last five detail lines"

key-files:
  created: []
  modified:
    - installer/run.py
    - installer/executors.py
    - installer/render.py
    - tests/test_run.py
    - tests/test_executors.py
    - tests/test_render.py

key-decisions:
  - "UTF-8 replacement decoding applies to all run_output_with_stderr callers, not smoke only"
  - "Failure report headline stays on errors[-1]; earlier methods get dim follow-up lines"

patterns-established:
  - "CommandError.detail carries str(OSError) for launch failures"
  - "render_failure_details prints first line of each earlier ladder error"

requirements-completed: [REG-05]

coverage:
  - id: D1
    description: "OS launch failures (ENOENT interpreter, bad ELF) name the OS reason in smoke messages"
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_smoke_binary_names_the_os_launch_error
        status: pass
    human_judgment: false
  - id: D2
    description: "Failure report keeps an earlier smoke reason when a later method also fails"
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_render.py#test_failure_report_keeps_an_earlier_smoke_reason
        status: pass
    human_judgment: false
  - id: D3
    description: "Non-UTF-8 child output replaces bytes instead of aborting the ladder"
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_run.py#test_undecodable_output_is_replaced_not_raised
        status: pass
    human_judgment: false
  - id: D4
    description: "Smoke reason is one bounded line that prefers loader errors over dbus noise"
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_executors.py#test_smoke_reason_is_one_bounded_line_under_noisy_stderr
        status: pass
      - kind: unit
        ref: tests/test_executors.py#test_smoke_reason_prefers_the_loader_line
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 23 Summary

**Smoke failures and failure reports now surface OS/loader reasons on one bounded line, keep earlier ladder errors visible, and never crash on non-UTF-8 child output.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 (+ summary commit)
- **Files modified:** 6

## Accomplishments

- `CommandError.detail` includes `str(OSError)` for binaries the OS cannot launch; `smoke_binary` formats `smoke run failed for <path> (exit <code>): <reason>`.
- `render_failure_details` prints dim `earlier method failed:` lines for every error before the headline.
- `run_output_with_stderr` decodes captured streams as UTF-8 with `errors="replace"`.
- `_smoke_reason` prefers the first `_LOADER_ERROR` line, otherwise the last five non-empty detail lines.

## Task Commits

1. **Task 1: WR-03 smoke reason and earlier errors in report** — `a6532ed`
2. **Task 2: UTF-8 replacement and docstring (IN-01)** — `e43e198`

## Review finding dispositions

| Finding | Source | Outcome | Commit | Test |
|---------|--------|---------|--------|------|
| WR-03 OSError/no reason; errors[-1] only; unbounded stderr | 18-REVIEW.md | fixed | a6532ed, e43e198 | `test_smoke_binary_names_the_os_launch_error`, `test_failure_report_keeps_an_earlier_smoke_reason`, bounded-line tests |
| MEDIUM non-UTF-8 aborts ladder | 18-REVIEW-opencode.md | fixed | e43e198 | `test_undecodable_output_is_replaced_not_raised` |
| #17 unreachable smoke_binary fallback | ponytail | fixed | a6532ed | existing `test_smoke_binary_*` unchanged |
| IN-01 macOS DISPLAY docstring | 18-REVIEW.md | fixed | e43e198 | docstring diff in `executors.py` |

## TDD RED evidence

**Task 1** (`uv run pytest … -k "os_launch_error or earlier_smoke_reason"`):

```
AssertionError: assert 'No such file or directory' in 'smoke run failed for .../bin: command failed (127): .../bin --version'
AssertionError: assert 'Exec format error' in 'smoke run failed for .../bin: command failed (127): ...'
UnboundLocalError: cannot access local variable 'smoke_error' (fixed before GREEN: assign in except to outer name)
```

**Task 2** (`uv run pytest … -k "undecodable or bounded_line or prefers_the_loader_line"`):

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

(`test_smoke_reason_is_one_bounded_line_under_noisy_stderr` and `test_smoke_reason_prefers_the_loader_line` were GREEN after Task 1’s `_smoke_reason` implementation.)

## Verify results

- Task 1: `uv run pytest tests/test_executors.py tests/test_render.py tests/test_run.py tests/test_engine.py -q --no-cov` — pass
- Task 1 shrink guard (pre-commit): pass; `wc -l` tests/test_executors.py 1122, tests/test_render.py 741; `git diff --stat` +59 lines tests only
- Task 2: `uv run pytest tests/test_run.py tests/test_executors.py tests/test_versions.py tests/test_version_status.py -q --no-cov` — pass
- Final: `make validate && make test` — pass (3889 passed, 4 skipped, coverage 95.31%)
- `git diff --exit-code 6794a65 -- pyproject.toml uv.lock` — clean

**Final tree `wc -l` / `git diff --stat` (6794a65..HEAD):**

```
  144 installer/run.py
  621 installer/executors.py
  318 installer/render.py
  747 tests/test_run.py
 1152 tests/test_executors.py
  741 tests/test_render.py

 installer/executors.py  |  49 +++++--
 installer/render.py     |   7 +
 installer/run.py        |   4 +
 tests/test_executors.py |  55 ++++++++
 tests/test_render.py    |  34 +++++
 tests/test_run.py       |  23 ++++
 6 files changed, 140 insertions(+), 7 deletions(-)
```

## Deviations from Plan

- **test_render.py:** Rich console wrap broke contiguous `Exec format error` in buffer output; assertion uses `out.replace("\n", "")` so the tracer stays stable under default console width.
- **tests/test_run.py:** Extended `test_run_output_unbounded_by_default` fake `subprocess.run` to accept `encoding` / `errors` and assert they are passed through (required after Task 2 production change).

## Issues Encountered

None blocking.

## User Setup Required

None.

## Next Phase Readiness

Install/update failure messages from smoke and captured probes now carry actionable OS/loader text; phase 18 drift-guard UX items tied to REG-05 for this plan are satisfied.

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
