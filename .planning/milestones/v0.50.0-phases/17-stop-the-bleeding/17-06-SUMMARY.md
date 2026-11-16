---
phase: 17-stop-the-bleeding
plan: "06"
subsystem: installer
tags: [atomic-writes, os.replace, symlink-through, rc-files, shims, clean-rc-duplicates, safe-04]

requires:
  - phase: 17-01
    provides: green CI baseline
  - phase: 17-04
    provides: installer/atomic.py helpers (atomic_write_bytes/atomic_write_text)
provides:
  - every rc and shim write in guards.py and tweaks.py goes through atomic_write_text (shims with mode=0o755)
  - clean_rc_duplicates keeps the previewed bytes, byte-rechecks at confirm, refuses changed/deleted files, writes atomically
  - concurrency-edge proof on atomic_write_text (test_rc_reader_never_sees_a_partial_write)
affects: [17-SPEC R4, uninstall sweep (guards/tweaks writers), doctor, 19-receipts]

actuals:
  tokens: 15500
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - failure injection via monkeypatch.setattr("os.replace", boom) at the rc level
    - wrap-tolerant rich console assertions (" ".join(buf.getvalue().split())) for long-path messages

key-files:
  created: []
  modified:
    - installer/guards.py
    - installer/tweaks.py
    - installer/app.py
    - tests/test_guards.py
    - tests/test_atomic.py
    - tests/test_app.py

key-decisions:
  - "D-05 applied as planned: 10 write sites switched, 6 chmod(0o755) lines deleted, shims pass mode=0o755, rc writes pass no mode (existing mode copied)."
  - "D-06 applied as planned: preview keeps (before_bytes, text, indices); confirm re-reads read_bytes(), byte-compares, and one refusal branch also covers the OSError case (deleted/unreadable file → 'changed', never recreated)."
  - "Test economy per the plan's ponytail pass: no per-call-site atomic tests; routing enforced by the acceptance greps."
  - "Wrap-tolerant console assertions: rich soft-wraps the long tmp_path in the refusal message, so the tests normalize whitespace before matching 'changed since the preview'. (Found as an xdist failure in make test, fixed before commit.)"

requirements-completed: [SAFE-04]
duration: ~50 min
completed: 2026-10-14
---

# Plan 17-06 Summary: atomic rc/shim writes and an honest duplicate cleanup

Every rc and shim write in `installer/guards.py` and `installer/tweaks.py` now goes through
`installer/atomic.atomic_write_text`, and `clean_rc_duplicates` only ever strips the lines the
user actually previewed, refusing a file whose bytes changed (or vanished) between preview and
confirm.

## What was built

### Task 1 — ban-alias rc writes are atomic end to end (commit `274a45c`)
- `installer/guards.py`: `write_ban_aliases` and `remove_ban_aliases` write via
  `atomic_write_text` (no `mode` — the existing mode is copied; symlinked rcs are written
  through to their target).
- `tests/test_guards.py`: `test_ban_aliases_write_failure_leaves_the_rc_byte_identical`
  (injected `os.replace` → OSError, original bytes kept, no `*.tools-installer.tmp` left) and
  `test_ban_aliases_write_through_a_symlinked_rc` (link stays a link, target holds the block,
  user bytes before the marker kept).

### Task 2 — all remaining shim/tweak writes atomic + concurrency proof (commit `fcaff18`)
- `installer/guards.py`: the five shim write sites (redirect shims ×2, global redirect blocked
  body, global redirect script, `install_shims`) now call
  `atomic_write_text(target, ..., mode=0o755)`.
- `installer/tweaks.py`: `install_tweak_executables` (`mode=0o755`), `write_tweak`,
  `remove_tweak` → `atomic_write_text`.
- `tests/test_atomic.py`: `test_rc_reader_never_sees_a_partial_write` — a reader wrapped
  around `os.replace` observes the old bytes before it and the new bytes after; proven once on
  `atomic_write_text`, which all writers route through.

### Task 3 — duplicate cleanup refuses changed files (commit `9295855`)
- `installer/app.py::clean_rc_duplicates`: preview reads once with `read_bytes()` and keeps
  `(before_bytes, text, indices)`; at confirm it re-reads `read_bytes()`
  (`OSError` → `after = None`, review 17-06 LOW) and on any mismatch prints
  `"<rc> changed since the preview; left untouched."`, drops the file from the returned dict,
  and continues; on match it applies `strip_lines(text, indices)` via `atomic_write_text`.
- `tests/test_app.py`: five new tests — refuse edited-between-preview-and-confirm,
  trailing-newline-only change counts as changed, unchanged file stripped atomically
  (injected `os.replace` failure keeps original bytes, no temp), symlinked rc written through,
  deleted-since-preview refused and not recreated while the second file is still stripped.

## TDD RED evidence

- Task 1: `Failed: DID NOT RAISE <class 'OSError'>` —
  `test_ban_aliases_write_failure_leaves_the_rc_byte_identical` failed because the plain
  `write_text` never reached the injected `os.replace`.
- Task 2: routing greps on the unchanged tree — `guards.py: 5` and `tweaks.py: 3`
  `.write_text(`, `chmod(0o755)`: 5 and 1. The new concurrency test passed immediately (it
  pins the property the routing relies on, as the plan states).
- Task 3: all five new tests failed before the fix
  (`FileNotFoundError` on the deleted file; stale indices applied for the edited/newline
  cases; plain `write_text` on the atomic-failure and symlink cases).

## Verify results

- `uv run pytest tests/test_guards.py -q --no-cov -k "ban_alias"` — 7 passed.
- `uv run pytest tests/test_guards.py tests/test_tweaks.py tests/test_policy_tweaks.py
  tests/test_policy.py tests/test_atomic.py -q --no-cov` — 120 passed.
- `uv run pytest tests/test_app.py -q --no-cov -k "clean_rc_duplicates"` — 9 passed
  (4 existing + 5 new).
- `uv run pytest tests/test_app.py tests/test_rcclean.py -q --no-cov` — 87 passed.
- Acceptance greps: `.write_text(` = 0 in guards.py and tweaks.py; `chmod(0o755)` = 0 in both;
  `mode=0o755` = 5 (guards) / 1 (tweaks); `clean_rc_duplicates` range has 2 `read_bytes()`,
  0 `read_text(`, 0 `.write_text(`, 1 `except OSError`.
- `make validate` and `make test` green on the final tree (3475 passed, 4 skipped,
  coverage 95.87% ≥ 90%).

## Deviations from the plan

- None in scope or files. One test-authoring correction: the symlink-through clean_rc test
  initially passed `HOME=<dotfiles dir>` in env, but `find_duplicate_path_lines` expands
  `$HOME` from env, so no duplicates were found; the test now uses `HOME=str(tmp_path)` while
  the rc itself is a symlink into `dotfiles/`. Also, the refusal-message assertions normalize
  whitespace because rich soft-wraps the long tmp_path ("changed since the
preview") — caught as a `make test` (xdist) failure and fixed before the Task 3 commit.

## Notes for the orchestrator

- None. All three tasks landed; no containers were needed; no host mutation.
