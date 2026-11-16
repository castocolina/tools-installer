---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "31"
subsystem: update
tags: [receipts, drift, update, host-setup, pnpm]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "receipts.drifted/all_gone (19-29) and the one UpdateService.run mutation gate"
provides:
  - "UpdateService.run refuses an installer-owned update over a drifted receipt"
  - "A manager update refreshes a receipt only when the method kind matches"
  - "pnpm_add_command quotes the reviewed host-setup handoff"
affects: [19-one-tool-state-with-health-plus-receipts, update-route, host-setup]

actuals:
  tokens: 4620
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "The drift refusal lives in UpdateService.run, the one gate both the catalog key and the execute screen use"
    - "A manager update refreshes a receipt only when its method kind matches the existing one"

key-files:
  created: []
  modified:
    - installer/update.py
    - installer/receipts.py
    - installer/version_status.py
    - installer/host_setup.py
    - tests/test_update.py
    - tests/test_execute_screen.py
    - tests/test_host_setup.py

key-decisions:
  - "Manager owners are not refused by the drift gate: their update never touches receipt artifacts, and Task 2 keeps the installer receipt"
  - "The execute-screen private-read guard names eight older reads outside the two tests this plan rewrites; the four 19-18 suppressions are gone (65 -> 61, net 487 -> 483)"

patterns-established:
  - "CHANGED_SINCE_INSTALL has one owner, installer/receipts.py; version_status and the update gate both import it"
  - "Any pnpm hint about a host-setup tool quotes pnpm_add_command, never a hand-written argv"

requirements-completed: [STATE-03, STATE-06]

coverage:
  - id: D1
    description: "UpdateService.run refuses an installer-owned update over a re-hashed drifted receipt, writing nothing, and the execute screen reports it per tool"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_update_service_refuses_a_drifted_receipt"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_drifted_receipt_update_is_refused_per_tool"
        status: pass
    human_judgment: false
  - id: D2
    description: "A receipt whose every artifact is gone does not block the update"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_all_gone_receipt_does_not_block_an_update"
        status: pass
    human_judgment: false
  - id: D3
    description: "The execute-screen classification tests read the rendered progress, dropping the four 19-18 private-field suppressions"
    requirement: STATE-06
    verification:
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_classify_reads_the_state"
        status: pass
      - kind: automated_ui
        ref: "tests/test_execute_screen.py#test_brew_appearing_mid_session_unblocks_colima"
        status: pass
    human_judgment: false
  - id: D4
    description: "A manager update keeps an installer receipt, so the installer's own files stay removal-proven"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_update.py#test_manager_update_keeps_an_installer_receipt"
        status: pass
    human_judgment: false
  - id: D5
    description: "The pnpm host-setup update hint quotes the reviewed handoff, and the fallback carries --ignore-scripts"
    requirement: STATE-06
    verification:
      - kind: unit
        ref: "tests/test_host_setup.py#test_reviewed_handoff_names_one_pnpm_add_command"
        status: pass
      - kind: unit
        ref: "tests/test_update.py#test_host_setup_update_hint_is_the_reviewed_handoff"
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 31: Drift Refusal, Receipt Kind, and the Reviewed Hint Summary

**Every update route refuses to overwrite a receipt-drifted file, a manager update keeps the installer's proof, and the pi hint is the reviewed command.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-10-16T22:11:10Z
- **Completed:** 2026-10-16T22:22:39Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- `UpdateService.run` refuses an installer-owned update while the receipt shows drift (re-hashed, and not every artifact gone): no subprocess, no write, outcome `unsupported` with `yq is broken: changed since install`.
- The execute screen reports that refusal per tool through the detail it already prints, and its two classification tests read the rendered progress instead of private fields.
- A manager update refreshes a receipt only when the method kind matches, so a brew update leaves an installer receipt untouched.
- `pnpm_add_command` is the one source of a host-setup pnpm hint; the fallback is `pnpm add --global --ignore-scripts {package}`.

## Task Commits

Each task was committed atomically:

1. **Task 1: one drift refusal in UpdateService.run, reported per tool; execute-screen tests on public rendering (G3, G20)** - `e71969f` (fix)
2. **Task 2: a manager update keeps an installer receipt; the pnpm hint quotes the reviewed handoff (G4, G14)** - `e67c1ad` (fix)

## Files Created/Modified

- `installer/update.py` - drift refusal in `UpdateService.run`; same-kind receipt rule; handoff-derived pnpm hint
- `installer/receipts.py` - `CHANGED_SINCE_INSTALL`, the one owner of the D-08 copy
- `installer/version_status.py` - imports `CHANGED_SINCE_INSTALL` from receipts
- `installer/host_setup.py` - `pnpm_add_command(setup_id)`
- `tests/test_update.py` - drift refusal, all-gone, same-kind receipt, reviewed hint
- `tests/test_execute_screen.py` - per-tool refusal; public progress assertions
- `tests/test_host_setup.py` - the reviewed handoff names one pnpm command

## Decisions Made

- Manager owners are not refused by the drift gate. Their update never touches receipt artifacts, and the same-kind rule keeps the installer receipt.
- The plan's private-read guard matches eight older reads in other tests. This plan removes the four 19-18 suppressions it names (`pyright: ignore` in `tests/test_execute_screen.py`: 65 -> 61).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The receipt-kind comparison needed a narrowed method**
- **Found during:** Task 2 (same-kind receipt rule)
- **Issue:** Comparing `existing.method.kind == method.kind` while `method` is still `Method | None` is a pyright error, and a first edit left a duplicated `except` that did not parse.
- **Fix:** The read, the kind comparison and the rewrite sit inside `if method is not None:`.
- **Files modified:** installer/update.py
- **Verification:** `make validate` (pyright 0 errors) and `make test` (4571 passed)
- **Committed in:** e67c1ad (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The narrowing keeps the rule the plan specifies. No scope creep.

## TDD RED evidence

Task 1, `uv run pytest tests/test_update.py tests/test_execute_screen.py -q --no-cov -k "drifted_receipt or all_gone"` (2 failed, 1 passed — the all-gone case already updated):

```
test_update_service_refuses_a_drifted_receipt
    assert outcome.status == "unsupported"
E   AssertionError: assert 'updated' == 'unsupported'
test_drifted_receipt_update_is_refused_per_tool
E   AssertionError: assert 'yq is broken: changed since install' in
    '...Updates\nupdated yq\n\nPATH wiring\nPATH wired\nPATH audit\nPATH verified'
```

The two G20 rewrites (`test_brew_appearing_mid_session_unblocks_colima`, `test_classify_reads_the_state`) passed on the old tree, as the plan predicted.

Task 2, `uv run pytest tests/test_update.py tests/test_host_setup.py -q --no-cov -k "keeps_an_installer_receipt or reviewed_handoff or host_setup_pnpm"` (4 failed):

```
test_update_refuses_host_setup_pnpm_cleanly
E   assert 'pnpm add --global --ignore-scripts ...' in
    '... update it with `pnpm add --global @earendil-works/pi-coding-agent`'
test_host_setup_update_hint_is_the_reviewed_handoff
E   assert '`pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent`' in
    '... `pnpm add --global @earendil-works/pi-coding-agent`'
test_manager_update_keeps_an_installer_receipt
E   assert receipt bytes unchanged; at index 60 the rewritten receipt differed
test_reviewed_handoff_names_one_pnpm_add_command
E   ImportError: cannot import name 'pnpm_add_command'
```

## Verify results

- Task 1 `make validate` exit 0; `make test` 4568 passed, 4 skipped, coverage 96.00%.
- Task 2 `make validate` exit 0; `make test` 4571 passed, 4 skipped, coverage 96.01%.
- Plan verification `uv run pytest tests/test_update.py tests/test_execute_screen.py tests/test_host_setup.py tests/test_version_status.py tests/test_catalog_tui.py -n auto -q --no-cov` exit 0.
- Acceptance counts: `CHANGED_SINCE_INSTALL` defined once in receipts.py and zero times in version_status.py; `receipts.CHANGED_SINCE_INSTALL` and `rehash=True` each once in update.py; `def pnpm_add_command` once, one call site, one fallback, zero of the old `pnpm add --global {` form.
- `git show --stat e71969f -- installer/execute_screen.py installer/catalog_tui.py` prints nothing.
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` clean.
- Suppression comments 487 -> 483. Truncation guards: test files grew and each gained tests (`tests/test_update.py` 1431 -> 1513, `tests/test_execute_screen.py` 4522 -> 4617, `tests/test_host_setup.py` 5 -> 15).

## File sizes

| file | before | after |
| --- | --- | --- |
| installer/update.py | 545 | 576 |
| installer/receipts.py | 511 | 514 |
| installer/version_status.py | 1668 | 1666 |
| installer/host_setup.py | 44 | 56 |
| tests/test_update.py | 1431 | 1513 |
| tests/test_execute_screen.py | 4522 | 4617 |
| tests/test_host_setup.py | 5 | 15 |

`git diff --stat 203776f..e67c1ad`: 7 files changed, 258 insertions, 26 deletions.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The update route refuses a drifted installer-owned file from every caller of `UpdateService.run`, and a manager update can no longer orphan the installer's files.
- The private-read guard in this plan's verify block still matches eight older reads in `tests/test_execute_screen.py` (lines 2109, 2157, 3793, 4056-4058, 4099-4100). They predate this plan and are outside its files' intended hunks; removing them would rewrite tests the plan does not name.

## Self-Check: PASSED

- `installer/update.py`, `installer/receipts.py`, `installer/version_status.py`, `installer/host_setup.py` exist and contain the specified symbols.
- Commits `e71969f` and `e67c1ad` are on this branch.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
