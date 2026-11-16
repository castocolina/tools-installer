---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "46"
subsystem: infra
tags: [shell, PATH, uninstall, receipts, testing]
requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: "Unified tool state, health checks, and deletion receipts"
provides:
  - "Tester login shell receives the selected Homebrew path"
  - "Loop-safe PATH comparisons in shim resolution and the test sandbox"
  - "Deletion-time re-hash for receiptless archive-layout proofs"
affects: [installer, e2e-testing, uninstall]
actuals:
  tokens: 1200
  tasks: 3
  commits: 3
tech-stack:
  added: []
  patterns: ["Use os.path.realpath for loop-tolerant PATH canonicalization", "Re-hash layout proof keys during deletion-time verification"]
key-files:
  created: []
  modified:
    - scripts/container-e2e-verify.sh
    - installer/guards.py
    - installer/uninstall.py
    - tests/conftest.py
    - tests/test_container_e2e_receipts.py
    - tests/test_guards.py
    - tests/test_sandbox.py
    - tests/test_shell_scripts_path.py
    - tests/test_uninstall.py
key-decisions:
  - "Keep BREW_BIN as the single host-selected constant and pass it to the tester shell as a host-expanded assignment prefix."
  - "Use os.path.realpath rather than catching RuntimeError from Path.resolve on looping PATH entries."
  - "Accept the IN3-04 cosmetic residual: independent workers may re-show identical warning text; no state is hidden."
patterns-established:
  - "Test shell handoffs by extracting the function payload and running it under scratch HOME."
  - "Force fresh digest computation when deletion-time proof is requested."
requirements-completed: [STATE-03, STATE-04]
coverage:
  - id: D1
    description: "The e2e tester shell writes the selected brew shellenv line once per rc file."
    requirement: STATE-03
    verification:
      - kind: integration
        ref: tests/test_container_e2e_receipts.py#test_write_tester_path_hands_the_selected_brew_to_the_tester_shell
        status: pass
    human_judgment: false
  - id: D2
    description: "Looping PATH entries do not abort shim resolution or test sandbox setup."
    requirement: STATE-04
    verification:
      - kind: unit
        ref: tests/test_guards.py#test_real_binary_survives_a_looping_path_entry
        status: pass
      - kind: unit
        ref: tests/test_sandbox.py#test_the_path_strip_survives_a_looping_entry
        status: pass
    human_judgment: false
  - id: D3
    description: "Receiptless layout removal re-hashes the key file at deletion time and removes the artifacts whole."
    requirement: STATE-04
    verification:
      - kind: unit
        ref: tests/test_uninstall.py#test_remove_proven_rehashes_a_receiptless_dir_key_file_at_deletion_time
        status: pass
    human_judgment: false

duration: 100min
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 46 Summary

**Tester Homebrew handoff, loop-safe PATH resolution, and fresh deletion-time proof close the final state/receipt gaps.**

## Performance

- **Duration:** approximately 100 minutes across the resumed execution
- **Started:** 2026-10-17
- **Completed:** 2026-10-17
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Passed the host-selected `BREW_BIN` through the tester login-shell command prefix; the extracted function run twice writes exactly one correct shellenv line per rc file.
- Replaced loop-sensitive `Path.resolve()` comparisons with `os.path.realpath()` in shim lookup and sandbox PATH filtering.
- Re-hashed receiptless archive-layout key files during deletion-time verification, preventing partial removal after a same-size, restored-mtime content swap.
- Recorded the accepted IN3-04 cosmetic residual: independent version and skill workers may re-show identical warning text; it was not changed.

## Task Commits

1. **Task 1: tester shell gets selected brew** — `7b27684` (`fix(19-46): the e2e tester shell gets the selected brew through a host-expanded prefix`)
2. **Task 2: loop-safe PATH filtering** — `2e09f9c` (`fix(19-46): keep PATH filtering safe around symlink loops`)
3. **Task 3: deletion-time re-hash** — `bf28ae1` (`fix(19-46): re-hash receiptless directories at deletion time`)

**Plan metadata:** this summary is committed separately as `docs(19-46): plan summary`.

## Files Created/Modified

- `scripts/container-e2e-verify.sh` — carries selected brew path into tester shell.
- `installer/guards.py` — loop-safe managed-directory comparisons.
- `installer/uninstall.py` — deletion-time digest refresh for receiptless layout proof.
- `tests/conftest.py` — reusable loop-safe host PATH filter.
- `tests/test_container_e2e_receipts.py`, `tests/test_shell_scripts_path.py` — regressions for the tester shell handoff and bounded payload extraction.
- `tests/test_guards.py`, `tests/test_sandbox.py` — looping PATH regressions.
- `tests/test_uninstall.py` — same-size/restored-mtime layout key swap regression.

## Decisions Made

- Kept `BREW_BIN` as the single configured value; the host expands an assignment prefix before passing the body through `su -`.
- Used `os.path.realpath` because it handles symlink loops without raising, rather than adding exception guards around `Path.resolve()`.
- Accepted the IN3-04 residual as cosmetic: warning text can repeat, but no state or warning content is lost.

## Deviations from Plan

None. Task 2's regression produced the planned Python 3.12 `RuntimeError: Symlink loop` failure. Task 1 and Task 3 also produced their expected RED failures before implementation.

## Issues Encountered

- Task 1 RED: the selected brew variable was lost through `su -`, producing `eval "$( shellenv)"` and `shellenv: command not found`.
- Task 2 RED: `Path.resolve()` raised `RuntimeError: Symlink loop` on Python 3.12; after fixing production code, the PATH-strip test required adding the planned public `host_free_path` helper before it could collect.
- Task 3 RED: deletion refused the directory as changed since preview and left it present, after the link had been unlinked; re-hashing during fresh proof resolved this partial-removal case.
- The optional isolated final reviewer could not be dispatched because no reviewer agent model was authenticated in the available providers; a read-only self-review was performed against the complete diff and plan instead.

## Verification

- Focused Task 1 tests: 24 passed; `bash -n scripts/container-e2e-verify.sh` passed.
- Focused Task 2 tests: 14 passed.
- Focused Task 3 tests: 13 passed.
- Final focused combined suite: `uv run pytest tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py tests/test_guards.py tests/test_sandbox.py tests/test_uninstall.py -n auto -q --no-cov` passed.
- Final full gates: `make validate && make test` passed; 4,641 passed, 4 skipped, 95.98% coverage.
- Script line count: `scripts/container-e2e-verify.sh` is 605 lines.
- Large test-file evidence: `tests/test_uninstall.py` is 2,628 lines; `tests/test_guards.py` is 1,196 lines. The task-range diff is 9 files, 122 insertions and 45 deletions (`git diff --stat 00e9707..HEAD`).

## Next Phase Readiness

STATE-03 and STATE-04 gap closures are implemented and validated. No external setup is required.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-17*
