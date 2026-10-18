---
phase: 20-install-plan-with-dispositions
plan: "21"
subsystem: testing
tags: [bash, container-e2e, summary-parser, shellcheck]

requires:
  - phase: 20-install-plan-with-dispositions
    provides: container E2E receipt checks and install-plan outcome summaries
provides:
  - One gate for each install step that rejects incomplete or unexplained runs
  - Bash-builtin summary parsing and dependency blocker continuation joining
affects: [container-e2e, PLAN-06]

actuals:
  tokens: 7100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns: ["Aggregate per-transcript counters before deciding the install-step gate", "Parse summary counters with Bash regex captures"]

key-files:
  created: []
  modified:
    - scripts/container-e2e-verify.sh
    - tests/test_container_e2e_receipts.py
    - tests/test_shell_scripts_path.py

key-decisions:
  - "A setup exit of 1 is accepted only when dependency failures are all explained by manual handoffs."
  - "Join only dependency-row continuations indented at least four spaces; two-space report output remains separate."

patterns-established:
  - "A setup invocation is valid only when each transcript has one parseable Summary line and the aggregate outcome passes the shared gate."
  - "Use Bash BASH_REMATCH captures for host-side summary parsing, without external utilities in the parser."

requirements-completed: [PLAN-06]
coverage:
  - id: D1
    description: "The container E2E install gate rejects not-attempted, crashed, missing-summary and unexplained non-zero runs while accepting explained dependency handoffs."
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_install_step_gate"
        status: pass
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_accumulate_counts_not_attempted_and_crashed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Summary parsing uses Bash builtins, and folded dependency-failure rows retain their complete blocker list without swallowing two-space report lines."
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_parse_summary_line_needs_no_external_tool"
        status: pass
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_a_folded_dependency_failed_row_is_read_whole"
        status: pass
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_a_two_space_report_line_is_not_joined_to_a_row"
        status: pass
      - kind: other
        ref: "bash -n scripts/container-e2e-verify.sh && uv run shellcheck -x -S warning scripts/container-e2e-verify.sh"
        status: pass
    human_judgment: false

duration: 130min
completed: 2026-10-18
status: complete
---

# Phase 20: Install Plan with Dispositions Summary

**Container E2E install steps now share a strict summary-and-exit gate, with portable Bash parsing and complete folded dependency rows.**

## Performance

- **Duration:** Approximately 130 min across a compacted session
- **Started:** 2026-10-18 (time not retained)
- **Completed:** 2026-10-18T10:36:03Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `install_step_ok` as the common pass1/pass2 gate. Each setup transcript must contain a valid summary; failed, checksum-mismatch, not-attempted and crashed counts must be zero. Exit 1 passes only when all dependency failures are explained by manual handoffs.
- Replaced external-tool summary extraction with Bash regex captures and reconstructed folded dependency-failure rows while leaving two-space report lines distinct.
- Added fixture-based tests for gate decisions, no-external-tool parsing, folded rows and report-line separation.

## Task Commits

Each task was committed separately:

1. **Task 1: one install-step gate that fails a run that did nothing** - `97b0732` (fix)
2. **Task 2: a builtin-only parser and whole folded rows** - `30849f5` (fix)

## Files Created/Modified

- `scripts/container-e2e-verify.sh` - Shared install gate, counters, portable parser and folded-row reconstruction.
- `tests/test_container_e2e_receipts.py` - Isolated Bash fixture harness and new behavioral checks.
- `tests/test_shell_scripts_path.py` - Updated line classifications after the script comment and parser changes shifted source lines.

## Decisions Made

- Retained the plan's exit policy: setup exit 1 is acceptable only for dependency failures fully explained by manual handoffs; any other nonzero exit fails.
- Used a four-space continuation threshold so renderer-folded outcome text joins while two-space verification/report blocks do not.

## Deviations from Plan

### Auto-fixed Issues

**1. Existing PATH scan classifications shifted when the script comment changed**
- **Found during:** Task 2 verification
- **Issue:** `test_no_unclassified_accumulating_path_line_in_any_shell_script` identifies two one-shot embedded PATH exports by line number; the comment shortening shifted those lines.
- **Fix:** Updated their classifications to the new source lines without changing the accepted command locations or policy.
- **Files modified:** `tests/test_shell_scripts_path.py`
- **Verification:** `uv run pytest tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py -q --no-cov -n 0` passed.
- **Committed in:** `30849f5`

**Total deviations:** 1 auto-fixed (existing test classifications)
**Impact on plan:** Required to keep the path audit accurately pinned to the unchanged one-shot exports; no behavior or scope change.

## Issues Encountered

- The initial Task 1 test harness run exposed missing extracted callees and quoting/exit-status issues in the test harness. The helper was corrected, and the focused gate tests passed before the first task commit.
- `make validate` initially found a line-length issue and then formatting drift in the new test helper; Ruff formatting resolved both.
- The path-scan test failed after the COLUMNS comment shortened; the classifications were updated to the exact new line numbers and the full path/receipt test set passed.

## Verification

- Task 1 RED: `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -n 0 -k "not_attempted_and_crashed or install_step_gate or one_gate"` — 10 failures. The missing summary accounting and undefined gate caused failures; the test cases were then made to exercise the intended return status.
- Task 1 GREEN: same focused command — 10 passed.
- Task 1 tests: `uv run pytest tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py -q --no-cov -n 0` — passed (34 tests).
- Task 2 RED: `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -n 0 -k "no_external_tool or read_whole or not_joined"` — 1 failed, 2 passed. The parser used `sed` with empty PATH and emitted empty counters; the folded-row case was later strengthened to assert the persisted joined line and watched fail before the final implementation proof.
- Task 2 GREEN: `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -n 0 -k "no_external_tool or read_whole or not_joined"` — 3 passed; the strengthened folded-row check also passed after asserting the stored full blocker row.
- Final focused suite: `uv run pytest tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py -q --no-cov -n 0` — 37 passed.
- Shell validation: `bash -c 'bash -n scripts/container-e2e-verify.sh && uv run shellcheck -x -S warning scripts/container-e2e-verify.sh'` — exit 0.
- Quality gates: `make validate && make test` — passed; 4,857 passed, 4 skipped; coverage 96.01%.
- Test collection floor: 12 at plan start; 22 after Task 1; 25 after Task 2.
- Acceptance checks: gate definition count 1; gate call count 3; `ACC_NOT_ATTEMPTED`, `ACC_CRASHED`, `ACC_SUMMARIES` reference counts 9 each; parser's old sed chain count 0; `BASH_REMATCH` count 1; remaining non-comment `sed -n` count 1; shellcheck-disable count 0.
- No live container test was run, as requested.

## Review

- A fresh reviewer could not be obtained: available reviewer subagents returned an upstream `Policy budget exceeded` error. The review package was generated and read in this session; self-review was performed against the plan and diff. This is weaker than an independent review and should be weighed before merge.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 20-21 is implemented and locally validated. The orchestrator's later `make e2e` container backstop remains intentionally unrun in this session.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
