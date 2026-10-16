---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "09"
status: complete
subsystem: receipts
tags: [receipts, install-engine, update, tdd, state]

requires:
  - phase: 19-01
    provides: receipts module (Receipt, fingerprint, write, read, delete, receipts_dir sandbox)
  - phase: 19-02
    provides: download.artifact_paths (D-07 artifact formula)
  - phase: 19-05
    provides: ownership.method_package (the one package reader)
  - phase: 19-07
    provides: model.TOOL_ID_RE enforced by load_tools
provides:
  - "receipts.record(tool, method, *, package, smoke, default_bin_dir=None): the one receipt writer"
  - "receipts._build_receipt(tool, method, artifacts, *, package, smoke): pure builder shared with 19-14 adopt"
  - "receipts.RECEIPTLESS_KINDS (dnf, apt, pacman, rpm_ostree, skill_pack, host_setup)"
  - "engine.install_tool writes the receipt before run_postinstall; present= kwarg (D-04)"
  - "update._perform rewrites the receipt (installer always; brew/cask/uv/pnpm only over an existing one)"
affects: [19-10 removal gate, 19-14 drift/adoption, 19-18 present= wiring]

actuals:
  tokens: 8700
  tasks: 3
  commits: 3
plan_head_before: 22c5dcb00ea0a33f624b81a7f05b5c8bf3db70aa
plan_head_after: 6e1c8cb70a64389b8aa20111cb886a4b19d3ee86

tech-stack:
  added: []
  patterns:
    - "one writer: install, repair and update all go through receipts.record"
    - "failed rewrite over an existing receipt deletes it (best effort) and says so in the OSError"

key-files:
  created: []
  modified:
    - installer/receipts.py
    - installer/engine.py
    - installer/update.py
    - tests/test_receipts.py
    - tests/test_engine.py
    - tests/test_update.py

key-decisions:
  - "record() resolves the default bin dir through locations.bin_dir(None) as a module attribute, so the conftest bin-dir sandbox applies"
  - "Receipt `at` uses isoformat(timespec='microseconds') so string and datetime comparison stay ordered"
  - "Engine joins `install receipt not written: ...` into postinstall_warning through the existing leftovers join"

requirements-completed: [STATE-03]

duration: ~45min
completed: 2026-10-16
---

# Phase 19 Plan 09: install receipt writer Summary

One receipt writer, `receipts.record`, fingerprints `artifact_paths(method, bin_dir)` after a successful install, repair or update and writes it atomically through the pure `_build_receipt`; native, skill and host_setup installs write none, and a failed write is a warning, never a failed install.

## Tasks

| Task | Commit | What |
|------|--------|------|
| 1 (tracer) | 785afe9 | `RECEIPTLESS_KINDS`, `_build_receipt`, `record` with the failed-rewrite policy (delete previous, note in the error); receipts reuse `model.TOOL_ID_RE`; engine success branch records before `run_postinstall` |
| 2 | df27215 | `_run_manager_smoke` returns whether it ran (smoke "ok"/null); `OSError` from `record` becomes `install receipt not written: ...` on `postinstall_warning`, status stays INSTALLED; `install_tool(present=...)` |
| 3 | 6e1c8cb | `update._perform` records after the owner dispatch and before postinstall, `smoke=None`; installer-owned always, manager owners only over an existing receipt; write failure appended to `detail` |

## TDD RED evidence

Task 1 (before implementation):
```
AttributeError: module 'installer.receipts' has no attribute 'RECEIPTLESS_KINDS'   (x6)
AttributeError: module 'installer.receipts' has no attribute 'TOOL_ID_RE'. Did you mean: '_TOOL_ID_RE'?  (x4)
AttributeError: module 'installer.receipts' has no attribute 'record'   (x5)
FAILED tests/test_engine.py::test_install_writes_one_receipt_before_postinstall  (assert None is not None)
FAILED tests/test_engine.py::test_archive_install_writes_a_receipt               (assert None is not None)
```
Task 2:
```
FAILED test_present_kwarg_drives_the_short_circuit - TypeError: install_tool() got an unexpected keyword argument 'present'
FAILED test_manager_smoke_status_is_recorded[True] - AssertionError: assert None == 'ok'
FAILED test_receipt_write_failure_keeps_installed - OSError: read-only
FAILED test_repair_receipt_write_failure_leaves_no_stale_receipt - OSError: read-only; the previous receipt was removed
FAILED test_crash_between_method_and_receipt_leaves_no_receipt - OSError: crashed before the receipt
```
(`test_receipt_per_kind`, `test_receiptless_install_writes_nothing` and `test_reinstall_rewrites_the_receipt` already passed after Task 1's write point; they are regression tests for the per-kind rules.)

Task 3:
```
FAILED test_installer_owned_update_rewrites_the_receipt - assert 'fa660671edb1...' == '9321dbf1802c...'
FAILED test_installer_owned_update_without_receipt_writes_one - assert None is not None
FAILED test_brew_update_rewrites_only_an_existing_receipt[True] - assert False
FAILED test_update_receipt_write_failure_is_a_detail - assert 'install receipt not written' in ''
```

## Verify results

- Task 1 `-k "record or receipt or archive_install or registry_rule"`: 63 passed (gate >= 10). AST gate: `_build_receipt` makes no fingerprint/hash/stat call, `record` calls it once: OK. `def record` 1, `receipts.record(` in engine 1, `def _build_receipt` 1, `from installer.receipts import receipts_dir` 0.
- Task 2 `tests/test_engine.py`: all pass; `-k "receipt or smoke_status or present_kwarg or crash_between or reinstall_rewrites"`: 17 passed (gate >= 14). `install receipt not written` in engine.py: 1; `present: Callable[[Tool], bool] | None = None`: 1.
- Task 3 `tests/test_update.py`: all pass; `-k receipt`: 6 passed (gate >= 6). `receipts.record(` in update.py: 1; engine imports in update.py: 0. Suppression count HEAD 598 -> 598.
- Plan verification: `pytest tests/test_receipts.py tests/test_engine.py tests/test_update.py -n auto`: 207 passed. `make validate` exit 0; `make test` 4211 passed / 4 skipped, coverage 95.74%. Real `~/.local/state/tools-installer/receipts` stays empty. `pyproject.toml`/`uv.lock` unchanged since fde3e68.

Truncation guards (run as plain commands; the worktree sandbox refuses `bash -c` with git):
- tests/test_engine.py: 1692 -> 1808 (Task 1) -> 2022 (Task 2) lines; test functions 54 -> 57 -> 65; trailing newline OK.
- tests/test_update.py: 1236 -> 1395 lines; test functions 49 -> 55; trailing newline OK.
- `git diff --stat 22c5dcb HEAD`: engine.py 37, receipts.py 72, update.py 12, test_engine.py 332, test_receipts.py 127, test_update.py 159 (724+, 15-).

## Deviations from Plan

1. [Rule 1 - test fixture] `test_archive_install_writes_a_receipt` places the extracted member at `~/.local/opt/rg/rg-x/rg` (not `.../rg/rg`), because the method's `member = "rg-x/rg"` with no `strip` is what the archive layout yields; the receipt assertion (opt dir + link with its readlink target) is as planned.
2. Per-kind and receiptless engine tests fake `engine._perform` (as `test_app_kind_routes_to_app_executor` fakes `install_app`) instead of a recording runner, so node/uv/cask need no pnpm/uv floors; raw and archive download tests run the real download executor with `fixture_runner`.
3. `test_unknown_and_refused_updates_write_nothing` seeds a receipt and asserts its bytes are unchanged (stronger than "none created"); its name has no "receipt", so the `-k receipt` gate counts the other 6.

No files outside files_modified were touched.

## Issues for the orchestrator

- Engine `record` catches only `OSError`; a `ValueError` from an unsafe tool id cannot occur for registry tools (load_tools enforces `TOOL_ID_RE`), so it is not caught.
- 19-10 runs in parallel and may also edit `installer/receipts.py`; this plan only appended `RECEIPTLESS_KINDS`, `_build_receipt`, `record` and swapped `_TOOL_ID_RE` for the imported `TOOL_ID_RE` (plus imports of `locations`, `artifact_paths`, `datetime`).

## Self-Check: PASSED

- installer/receipts.py, installer/engine.py, installer/update.py: FOUND
- 785afe9, df27215, 6e1c8cb: FOUND on worktree-agent-a65ed24fa53cfb58f
