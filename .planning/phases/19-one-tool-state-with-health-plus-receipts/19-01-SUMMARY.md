---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "01"
subsystem: testing
tags: [receipts, json, fail-closed, atomic-write, stat-fingerprint, pytest-sandbox, threading-lock]

requires:
  - phase: 18-close
    provides: atomic.py, checksums.py, locations.py, model.py, settings.py (ponytails reused); the real-home fingerprint harness in tests/conftest.py
provides:
  - installer/receipts.py: Receipt/ReceiptArtifact/ReceiptMethod, receipts_dir, receipt_path, method_key, write (+_write_unlocked), read, delete, fingerprint, matches, drifted
  - tests/conftest.py: autouse sandboxed_receipts + sandboxed_bin_dir, "<receipts>" real-home fingerprint entry
  - tests/test_receipts.py: 45-test suite (round-trip, fail-closed reader, id/symlink guards, matching/drift)
affects: [19-02, 19-07, 19-08, 19-09, 19-10, 19-11, 19-14]

actuals:
  tokens: 8600
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "lock-and-private-unlocked writer: non-reentrant module lock in the public fn, private _write_unlocked for already-holding callers (adopt, 19-14)"
    - "bounded-read cap: size limits enforced by fh.read(cap + 1), never an lstat shortcut alone"

key-files:
  created:
    - installer/receipts.py
    - tests/test_receipts.py
  modified:
    - tests/conftest.py
    - tests/test_locations.py

key-decisions:
  - "receipts_dir() is the one patched seam: every module function calls it through the module global, so the autouse conftest sandbox reaches all of them"
  - "64 KiB receipt cap enforced by the read itself (read(_MAX_RECEIPT_BYTES + 1)), lstat kept only as a shortcut (review C2-M1)"
  - "per-artifact required fields in the reader: a file needs 64-hex sha256 + int size + mtime_ns, a link a non-empty target; bools rejected where ints are required (review M1)"
  - "re-hash memo keyed (path, size, mtime_ns) under its own _MEMO_LOCK, never nested with _WRITE_LOCK (review H1)"
  - "default bin dir sandboxed while HOME is real, deferring to HOME/.local/bin once a test redirects HOME (checker W2)"

patterns-established:
  - "Fail-closed JSON reader: broad catch incl. RecursionError, strict isinstance validation, None on any violation (from install_ownership.py)"
  - "Autouse suite sandboxes for every host-writable default directory, backed by the session real-home fingerprint"

requirements-completed: [STATE-03]

coverage:
  - id: D1
    description: "Receipt written with receipts.write reads back equal through receipts.read; corrupt/malformed/oversized/tampered input always returns None, never raises"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_receipt_round_trips"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_read_fails_closed"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_read_fails_closed_on_a_file_that_grew_after_the_size_check"
        status: pass
    human_judgment: false
  - id: D2
    description: "Writes are safe: one _write_unlocked writer under _WRITE_LOCK, unsafe ids rejected, symlinked receipt paths refused, relative artifact paths rejected"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_write_refuses_a_symlinked_receipt"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_write_rejects_an_unsafe_id"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-08 matching: fingerprint/matches/drifted with stat shortcut, re-hash on stat change, per-session memo and rehash=True re-proof"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_matches_rehashes_a_touched_file_once"
        status: pass
      - kind: unit
        ref: "tests/test_receipts.py#test_drifted_lists_only_the_mismatched_artifacts"
        status: pass
    human_judgment: false
  - id: D4
    description: "Wave-0 sandboxes: the suite can never write the real receipts dir or read the real default ~/.local/bin"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_receipts.py#test_suite_sandbox_redirects_receipts"
        status: pass
      - kind: unit
        ref: "tests/test_locations.py#test_suite_sandbox_redirects_the_default_bin_dir"
        status: pass
      - kind: other
        ref: "command: make test (real_home_untouched session fixture + receipts dir verified unchanged on host)"
        status: pass
    human_judgment: false

duration: 70min (across two runs: 06:46-07:05 first run, resumed for verification + summary)
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 01: One tool state with health plus receipts — receipts module + Wave-0 sandbox Summary

**A fail-closed install-receipt module (`installer/receipts.py`) with an atomic single-lock writer, a bounded strictly-validated reader, and stat-fingerprint drift matching, shipped together with suite-wide sandboxes that keep every test off the real `~/.local/state/tools-installer/receipts` and `~/.local/bin`**

## Performance

- **Duration:** ~70 min total across two runs (first run stopped by a provider transport failure after all 3 task commits; this run verified the commits, reproduced RED evidence, and wrote the summary)
- **Started:** 2026-10-16T06:46:31-03:00
- **Completed:** 2026-10-16 (resume run)
- **Tasks:** 3/3
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- `installer/receipts.py` (369 lines): frozen `Receipt`/`ReceiptArtifact`/`ReceiptMethod`, `receipt_path` with a safe-filename guard, `method_key`, atomic `write` → private `_write_unlocked` under one non-reentrant `_WRITE_LOCK`, fail-closed `read` (64 KiB cap enforced by the read itself, strict typed validation, RecursionError-safe), `delete`, `fingerprint`, `matches` (stat shortcut + per-session re-hash memo + `rehash=True`), `drifted`
- Wave-0 test safety: autouse `sandboxed_receipts` and `sandboxed_bin_dir` fixtures in `tests/conftest.py`, plus a `"<receipts>"` entry in the real-home session fingerprint — a run that touches the real receipts dir fails the suite
- 45 tests in `tests/test_receipts.py` + 1 in `tests/test_locations.py`, all xdist-safe, scratch-HOME only

## Task Commits

1. **Task 1: one receipt written and read back, inside a sandbox the whole suite uses** - `5756de2` (feat)
2. **Task 2: the reader fails closed on every malformed input; writer refuses unsafe ids and symlinks** - `b1f23fb` (fix)
3. **Task 3: stat-fingerprint matching, re-hash memo and the drift list** - `97a142d` (feat)

**Plan metadata:** none (plan file committed earlier by the orchestrator)

## TDD RED evidence

The first run committed each task test-first; the RED states were reproduced from history in a temporary worktree (removed afterwards) and match the expected failures:

- **Task 1** at `5e4bfa7` (parent):
  ```
  $ uv run pytest tests/test_receipts.py -q --no-cov
  ERROR: file or directory not found: tests/test_receipts.py
  $ uv run python -c "import installer.receipts"
  ModuleNotFoundError: No module named 'installer.receipts'
  ```
- **Task 2** at `5756de2` (Task-1 tree): the fail-closed tests did not exist yet —
  ```
  $ uv run pytest tests/test_receipts.py -k "fails_closed" -q --no-cov
  no tests ran (exit 5)
  ```
- **Task 3** at `b1f23fb` (Task-2 tree): the matching tests did not exist yet —
  ```
  $ uv run pytest tests/test_receipts.py -k "fingerprint or matches or drifted" -q --no-cov
  no tests ran (exit 5)
  ```

## Verify-command results (this run, final tree)

- `uv run pytest tests/test_receipts.py -q --no-cov` → 45 passed
- `uv run pytest tests/test_receipts.py -n auto -q --no-cov` → 45 passed (xdist stress)
- `uv run pytest tests/test_locations.py -q --no-cov` → 35 passed; `-k suite_sandbox_redirects_the_default_bin_dir` → 1 passed
- `uv run pytest tests/test_receipts.py tests/test_atomic.py tests/test_checksums.py -n auto -q --no-cov` → 71 passed
- `make validate` → exit 0 (ruff, ruff format, pyright strict, bandit, vulture, shellcheck)
- `make test` → **4001 passed, 4 skipped**, coverage 95.52% (floor 90%)
- Suppression guard: 598 → 598 (no new `noqa`/`type: ignore`/`nosec`)
- `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` → clean (no new dependencies)
- Acceptance greps: `def receipts_dir`=1, `atomic_write_text(`=1 (inside `_write_unlocked` only), `def _write_unlocked`=1, `def sandboxed_bin_dir`=1, `def drifted`=1, `st_mtime_ns`≥1, `RecursionError`≥1, `64 * 1024` present, `_MAX_RECEIPT_BYTES + 1` present, zero unbounded `read_bytes(`/`read_text(`
- Host check: `~/.local/state/tools-installer/receipts` byte-identical before and after `make test`

## Files Created/Modified
- `installer/receipts.py` (created) — the receipts module: reader, writer, fingerprint/matches/drifted
- `tests/test_receipts.py` (created) — round-trip, fail-closed, guard, matching and drift tests
- `tests/conftest.py` (modified) — autouse `sandboxed_receipts`/`sandboxed_bin_dir`, `"<receipts>"` fingerprint entry
- `tests/test_locations.py` (modified) — `test_suite_sandbox_redirects_the_default_bin_dir`

## Decisions Made
- Kept the module-local `_TOOL_ID_RE` in Task 1 as the plan specifies; plan 19-09 replaces it with `installer.model.TOOL_ID_RE`
- No structural deviations from the plan; review dispositions H1, M1 and C2-M1 are all implemented and tested

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The first run stopped with a provider transport failure after committing all three tasks (recorded in the run ledger); no work was lost. This run verified every commit against the plan instead of redoing them.

## Notes for the Orchestrator
- `.planning/RUN-LEDGER.md` has uncommitted rows from the stopped run (the transport-failure and quota-wait entries). This run did not touch them: the ledger is orchestrator-owned. They are accurate and can be committed with the next orchestrator update.
- No container was needed; no worktree or scratch artifacts remain (`/tmp/red19` removed, `/tmp/receipts-*.txt` scratch files left outside the repo only).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 19-02 (implicit presence via receipts + bin dir) can read `receipts.read` and the sandboxed default bin dir immediately
- Plan 19-09 builds `record()` on `_write_unlocked`'s payload shape; plan 19-14's `adopt` must hold `_WRITE_LOCK` and call `_write_unlocked` (the seam exists and is documented in the docstring)
- `receipt_path` still uses the module regex; 19-09 swaps in `installer.model.TOOL_ID_RE` per the plan note

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
