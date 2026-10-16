---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "19"
subsystem: e2e
tags: [receipts, container-e2e, architecture, shell, tdd]

requires:
  - phase: 19-09
    provides: receipts.record, the install and update write points
  - phase: 19-10
    provides: plan_removal and remove_proven
  - phase: 19-01
    provides: receipts.read and default_receipts_dir
provides:
  - "container e2e receipt assertions: TRACER_RECEIPT_OK, TRACER_RECEIPT_PRE_UNINSTALL_OK, TRACER_RECEIPT_REMOVAL_OK"
  - "host-side bash proof of those functions against a scratch HOME"
  - "Phase 19 section in .claude/architecture.md, pinned by a docs test"
affects: [phase-19 e2e gate, phase-20, phase-21]

actuals:
  tokens: 3200
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "e2e receipt checks extracted and run in bash with exec_tester pinned to a scratch HOME; the script is never sourced"

key-files:
  created:
    - tests/test_container_e2e_receipts.py
  modified:
    - scripts/container-e2e-verify.sh
    - tests/test_shell_scripts_path.py
    - .claude/architecture.md
    - tests/test_docs.py

key-decisions:
  - "The probe is yq: the first registry tool whose first Fedora amd64 method is a raw github_release, category data"
  - "The pre-uninstall receipt is accepted only when receipts.read returns a receipt, run through uv in the container workspace"

patterns-established:
  - "A chunked e2e run without the probe category prints TRACER_RECEIPT_SKIPPED and does not fail; pass2 always proves the receipt before uninstall"

requirements-completed: [STATE-03]

coverage:
  - id: D1
    description: "Pass 1 fails unless the probe tool's receipt exists, and skips by name when its category is not in the run"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_assert_receipt_functions_in_bash"
        status: pass
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_receipt_check_is_skipped_for_other_categories"
        status: pass
    human_judgment: false
  - id: D2
    description: "Pass 2 requires the probe binary and a parser-accepted receipt before uninstall, then requires both to be gone"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_pre_uninstall_check_requires_binary_and_valid_receipt"
        status: pass
      - kind: unit
        ref: "tests/test_container_e2e_receipts.py#test_receipt_checks_are_wired_into_the_passes"
        status: pass
    human_judgment: true
    rationale: "The host test runs the extracted functions under a scratch HOME. The real container install and uninstall is the orchestrator's make e2e gate, which this plan must not run."
  - id: D3
    description: "The architecture doc records the Phase 19 mechanisms and a docs test pins the phrases"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_architecture_records_phase_19_mechanisms"
        status: pass
    human_judgment: false

duration: 70min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 19: One tool state with health plus receipts Summary

**The container e2e now fails when an install leaves no receipt or an uninstall leaves the probe file or its receipt, and the architecture doc records how the one tool state, receipts and health work.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-10-16T18:43:41Z
- **Completed:** 2026-10-16T18:55:02Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `scripts/container-e2e-verify.sh` checks the yq receipt after pass 1, requires the binary and a parser-accepted receipt before pass 2's uninstall, and requires both to be gone after it
- A chunked `--categories` run without `data` prints `TRACER_RECEIPT_SKIPPED tool=yq category=data` and does not fail
- `.claude/architecture.md` gained `## Phase 19: one tool state, health and receipts`, pinned by `test_architecture_records_phase_19_mechanisms`

## Task Commits

1. **Task 1: the container e2e proves receipt write and receipt-proven removal** - `afc9915` (test)
2. **Task 2: record the Phase 19 mechanisms in the architecture doc** - `04e46c2` (docs)

## TDD RED evidence

Task 1, before the script functions existed (`uv run pytest tests/test_container_e2e_receipts.py -q --no-cov`):

```
FAILED test_script_receipt_path_matches_the_module
E   AssertionError: RECEIPT_PROBE_TOOL is not assigned in the script
FAILED test_probe_tool_is_raw_download_first_on_fedora
FAILED test_probe_category_matches_the_registry
FAILED test_assert_receipt_functions_in_bash
FAILED test_receipt_checks_are_wired_into_the_passes
E   assert 'assert_receipt_present "$categories"' in 'cmd_pass1() { ... }'
FAILED test_receipt_check_is_skipped_for_other_categories
E   AssertionError: receipt_check_applies() is not defined in the script
FAILED test_pre_uninstall_check_requires_binary_and_valid_receipt
E   AssertionError: RECEIPT_PROBE_TOOL is not assigned in the script
7 failed
```

Task 2, before the section existed:

```
FAILED tests/test_docs.py::test_architecture_records_phase_19_mechanisms
E   AssertionError: missing load-bearing phrase: ToolState
```

## Verify-command results

- `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov` → 7 passed
- `uv run pre-commit run shellcheck --files scripts/container-e2e-verify.sh` → Passed
- Acceptance greps: `TRACER_RECEIPT_OK` 1, `TRACER_RECEIPT_REMOVAL_OK` 1, `TRACER_RECEIPT_PRE_UNINSTALL_OK` 1, `assert_receipt_ready_for_removal` 2, `receipts.read(` 1; no new `shellcheck disable`
- Task 1 `make validate` → exit 0; `make test` → 4501 passed, 4 skipped, coverage 95.95%
- `uv run pytest tests/test_docs.py -q --no-cov` → 7 passed
- Append-only guard: `.claude/architecture.md` 1024 → 1098 lines, trailing newline kept, existing lines unchanged (`cmp` clean)
- `grep -c "^## Phase 19" .claude/architecture.md` → 1
- `git diff --stat` for the docs commit: `.claude/architecture.md | 74 +`, `tests/test_docs.py | 31 +`
- Task 2 `make validate` → exit 0; `make test` → 4502 passed, 4 skipped, coverage 95.95%
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` → clean
- No container was started and `make e2e` was not run

## Files Created/Modified
- `scripts/container-e2e-verify.sh` — `RECEIPT_PROBE_TOOL`, `RECEIPT_PROBE_CATEGORY`, `TESTER_WORKSPACE`, `receipt_check_applies`, `assert_receipt_present`, `assert_receipt_removed`, `assert_receipt_ready_for_removal`, wired into pass1 and pass2
- `tests/test_container_e2e_receipts.py` — the seven host-side tests
- `tests/test_shell_scripts_path.py` — the three one-shot PATH prefixes reclassified at their new lines
- `.claude/architecture.md` — the Phase 19 section
- `tests/test_docs.py` — `_PHASE_19_REQUIRED` and its test

## Decisions Made
- The probe is `yq` / category `data`, confirmed by resolving the registry on `Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)`: it is the first tool whose first method is a raw `github_release`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The PATH-prepend scan's classifications followed the lines the insertion moved**
- **Found during:** Task 1 (receipt functions)
- **Issue:** Inserting the receipt functions shifted the two classified one-shot `export PATH` prefixes, and the new parser command adds a third of the same kind. The scan fails both on an unclassified hit and on a stale classification.
- **Fix:** Reclassified `scripts/container-e2e-verify.sh` lines 202, 317 and 340 with the existing one-shot reason. No new exemption kind.
- **Files modified:** `tests/test_shell_scripts_path.py`
- **Verification:** `tests/test_shell_scripts_path.py` passes; the three lines are the one-shot prefixes inside `su -c` payloads
- **Committed in:** `afc9915` (Task 1)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The classification update was required for the suite to pass. No scope change.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The orchestrator's phase-close `make e2e` should show `TRACER_RECEIPT_OK`, `TRACER_RECEIPT_PRE_UNINSTALL_OK` and `TRACER_RECEIPT_REMOVAL_OK`. This plan did not run it.
- The next phases can read the Phase 19 mechanisms from `.claude/architecture.md`.

## Self-Check: PASSED

- `tests/test_container_e2e_receipts.py` exists; `afc9915` and `04e46c2` are on main.
- Final review: self-review (no subagent tool). No Critical or Important finding.

Deferred minors:
- The parser command's quote nesting is covered by the `uv` stub, not by executing the shell line; it copies the quoting `run_setup_as_tester` already uses.

Rulings:
- Task 1: the three PATH prefixes stay classified as one-shot. Cost if wrong: one accumulating line could hide, and any other new hit still fails the scan.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
