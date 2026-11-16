---
phase: 20-install-plan-with-dispositions
plan: "30"
subsystem: testing
tags: [bash, receipts, adoption, headless, e2e]

requires:
  - phase: 20-install-plan-with-dispositions
    provides: headless install plans and deferred receipt adoption
provides:
  - Container e2e gate rejects headless runs with PATH wiring or audit errors
  - Held receipt adoptions revalidate under the receipt write lock and report refusal before execution
affects: [container-e2e, receipts, headless-installs]
actuals:
  tokens: 1800
  tasks: 2
  commits: 2
tech-stack:
  added: []
  patterns:
    - Count headless post-run diagnostic lines in the transcript gate
    - Return user-visible per-write failures from held bookkeeping commits
key-files:
  created: []
  modified:
    - scripts/container-e2e-verify.sh
    - tests/test_container_e2e_receipts.py
    - installer/receipts.py
    - installer/version_status.py
    - installer/app.py
    - tests/test_version_status.py
    - tests/test_app.py
key-decisions:
  - "The held adoption commit reuses receipts.adopt rather than maintaining a second check."
  - "A refused adoption is reported but does not invalidate or rebuild the consented plan."
patterns-established:
  - "Held writes may return a message; commit_writes collects and returns messages in queue order."
requirements-completed: [PLAN-06]
coverage:
  - id: D1
    description: The container e2e step gate detects headless PATH wiring and audit errors even when dependency failures are explained.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_container_e2e_receipts.py#test_install_step_gate
        status: pass
      - kind: unit
        ref: tests/test_container_e2e_receipts.py#test_the_gate_reads_the_post_run_lines_setup_prints
        status: pass
    human_judgment: false
  - id: D2
    description: Deferred adoption uses the canonical adoption check and reports a refusal before the install run.
    requirement: PLAN-06
    verification:
      - kind: integration
        ref: tests/test_version_status.py#test_a_held_adoption_whose_file_changed_before_consent_is_printed_not_written
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_held_adoption_write_failure_does_not_abort_commit
        status: pass
    human_judgment: false
duration: 30min
completed: 2026-10-18
status: complete
---

# Phase 20: Install plan with dispositions — Plan 30 Summary

**Headless PATH failures now fail the container gate, and held receipt adoption reports consent-window changes before executing the agreed plan.**

## Performance

- **Duration:** Approximately 30 minutes
- **Started:** 2026-10-18
- **Completed:** 2026-10-18
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

- Added `ACC_POST_RUN_ERRORS` to transcript accumulation and required zero such errors for an e2e install step to pass, including pass 1 and both pass 2 installation steps.
- Updated count and incomplete lines to include `post_run_errors`; added both PATH diagnostic cases and a guard tying parser prefixes to `setup.py`.
- Removed the separate `receipts.commit_adoption` check. The held commit now re-runs `receipts.adopt` and returns a specific change/refusal or `OSError` message.
- `run_wizard` prints failed-adoption messages after consent and before execution without altering plan results or exit status.

## Task Commits

1. **Task 1: Count post-run PATH errors in the container gate** — `6ed7352` (`fix(20-30): the e2e gate fails a step whose headless run printed a PATH error`)
2. **Task 2: Revalidate and report held adoption commits** — `7b12f40` (`fix(20-30): a held adoption commit reports a refusal`)

## Files Created/Modified

- `scripts/container-e2e-verify.sh` — Counts and gates on post-run PATH error lines; reports the count.
- `tests/test_container_e2e_receipts.py` — Covers both diagnostic lines and their source-prefix parity.
- `installer/receipts.py` — Deletes the redundant `commit_adoption` check.
- `installer/version_status.py` — Held writes can return messages; adoption is rechecked by `receipts.adopt`.
- `installer/app.py` — Prints adoption commit messages before executing rows.
- `tests/test_version_status.py` — Tests changed-file refusal, write failure reporting, and receipt timestamp comparison.
- `tests/test_app.py` — Updates the commit-writes test double return type.

## TDD and Verification Evidence

### Task 1

- **RED:** `uv run pytest tests/test_container_e2e_receipts.py -q --no-cov -n 0 -k 'install_step_gate or post_run_lines'` — 3 failed, 7 passed. Both new PATH cases incorrectly returned success, and the prefix drift guard found no parser checks.
- **GREEN:** `uv run pytest tests/test_container_e2e_receipts.py tests/test_shell_scripts_path.py -q --no-cov -n 0` — 40 passed.
- `uv run shellcheck --severity=warning scripts/container-e2e-verify.sh` — passed. ShellCheck findings were **3 before and 3 after**; `bash -n` passed.
- Collected items: `tests/test_container_e2e_receipts.py` **25 → 28**.
- `make validate && make test` — passed: 4911 passed, 4 skipped; coverage 96.00%.

### Task 2

- **RED:** First targeted run produced 1 failure and 2 passes: changed-file adoption was silently discarded. After updating the write-failure test to target `_write_unlocked` and assert the new return contract, the RED run produced 2 failures and 1 pass: missing user report and `commit_writes()` still returned `None`. The changed timestamp expectation passed.
- **GREEN:** `uv run pytest tests/test_version_status.py -q --no-cov -n 0 -k 'changed_before_consent or write_failure_does_not_abort or commits_the_adoption_before_it_runs'` — 3 passed.
- `uv run pytest tests/test_version_status.py tests/test_app.py tests/test_receipts.py tests/test_setup.py -q --no-cov -n auto` — passed.
- Collected items: `tests/test_version_status.py` **190 → 191**; `tests/test_app.py` **136 → 136**.
- Suppression-comment count remained **484 → 484**.
- Full gate `make validate && make test` passed: 4912 passed, 4 skipped; coverage 96.03%.
- The changed expectation excludes only `Receipt.at`: the deferred commit rebuilds the receipt at commit time, so its timestamp correctly reflects the commit rather than the earlier plan-time candidate. All other fields must match.

## Decisions Made

- Reused `receipts.adopt` for the deferred commit so the same write-locked fresh fingerprint and receipt-existence checks protect both immediate and deferred adoption.
- Reported an adoption refusal as a line before execution. No plan invalidation or rebuild: adoption is a current-tool skip, so refusal does not alter the agreed run plan.

## Deviations from Plan

None. Formatting corrections were made after the initial validation identified two overlong test literals and two files needing Ruff formatting; no checks were bypassed.

## Issues Encountered

- Initial `make validate` found two `E501` test lines; split the string literals and reran validation.
- Task 2's initial full validate flagged Ruff formatting in the modified Python files; formatted those files and reran the full gate successfully.

## User Setup Required

None.

## Next Phase Readiness

PLAN-06 review gaps covered by this plan are implemented and tested. The container `make e2e` remains an orchestrator-level backstop and was intentionally not run here.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
