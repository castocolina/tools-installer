---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "45"
subsystem: state-and-receipts
tags: [receipts, TypeGuard, Textual, pytest]
key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/catalog_tui.py
    - installer/terminal_shell.py
    - tests/test_catalog_tui.py
key-decisions:
  - "Used TypeGuard[str] so the validated directory key narrows without a cast."
  - "A BROKEN state with no reasons is refused with the reason-less form of the existing copy."
requirements-completed: [STATE-03, STATE-02]
duration: 35min
completed: 2026-10-17
status: complete
---

# Phase 19 Plan 45 Summary

**Receipt artifact validation now shares one digest-triple check, and `u` safely refuses reason-less BROKEN rows while the terminal limit message follows its constant.**

## Task outcomes

1. **One receipt digest parse and typed key guard** — changed `_safe_key` to `TypeGuard[str]`, unified file/dir digest validation, removed the nested fingerprint helper, and corrected the docstring wrap. The required baseline was **112 tests passing** (`uv run pytest tests/test_receipts.py -q --no-cov`); the same 112 passed after the refactor. Task verification `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py -q --no-cov` passed. Suppression-count and acceptance greps passed. Commit: `79668a3`.
2. **Reason-less BROKEN refusal and derived terminal cap** — added the regression test, made the BROKEN refusal tolerate empty reasons, and derived the displayed MiB count from `_CONFIG_MAX_BYTES`. The unchanged reasoned-row and FIFO tests remained green. Commit: `738dd5e`.

## TDD RED evidence

Before the catalog fix, `uv run pytest tests/test_catalog_tui.py -q --no-cov -k 'without_a_reason'` failed as expected:

```text
FAILED test_u_on_a_broken_row_without_a_reason_still_refuses
installer/catalog_tui.py:809: IndexError: tuple index out of range
1 failed
```

After implementation, the focused regression test passed (1 passed).

## Verification

- `uv run pytest tests/test_receipts.py tests/test_uninstall.py tests/test_engine.py -q --no-cov` — passed; receipts baseline and post-refactor count both 112.
- `uv run pytest tests/test_catalog_tui.py tests/test_terminal_shell.py tests/test_execute_screen.py -q --no-cov -k 'broken or fifo or reason'` — 20 passed.
- `uv run pytest tests/test_catalog_tui.py -q --no-cov -k 'without_a_reason'` — 1 passed.
- Suppression-count checks and receipts TypeGuard/digest/helper acceptance checks — passed.
- `make validate && make test` — passed: validate clean; **4637 passed, 4 skipped**, coverage 95.98%.
- Large-file guard: `tests/test_catalog_tui.py` grew from 4914 to 4935 lines; diff stat was 50 insertions and 29 deletions across the four planned files. The test file did not shrink, gained one test, and retained its trailing newline.
- Self-review of `57ba42d..738dd5e` — no implementation findings. A fresh reviewer agent was unavailable: no configured provider/model could be resolved.

## Commits

- Task 1: `79668a3` — `refactor(19-45): one digest-triple parse and a TypeGuard key in the receipt reader`
- Task 2: `738dd5e` — `fix(19-45): u refuses a reason-less broken row; terminal cap follows its constant`

## Deviations from the plan

None in implementation scope. The suggested Superpowers SDD workspace/task scripts were not present at the referenced path, and the isolated reviewer agent could not be launched due to unavailable provider authentication; the required inline execution and self-review were completed instead.

## Issues the orchestrator should know

No code or test blockers remain. The final review was a self-review by the author, which is weaker than a fresh reviewer; decide whether that is sufficient before integration.
