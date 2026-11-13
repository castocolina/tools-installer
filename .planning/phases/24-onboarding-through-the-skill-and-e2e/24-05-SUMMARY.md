---
phase: 24-onboarding-through-the-skill-and-e2e
plan: "05"
subsystem: installer
tags: [update, cargo_distrobox, alacritty, rebuild, receipts, config-untouched]
requires:
  - phase: 24-01
    provides: "cargo_distrobox.install(method, ctx) -> notes, raising ExecutorError after its cleanups; receipts for the five Alacritty artifacts"
provides:
  - "Installer-owned update of a cargo_distrobox method rebuilds the newer release tag in a fresh throwaway box and swaps the five artifacts"
  - "Pinned behavior: a current tag plans SKIP with no box; a failed or interrupted rebuild leaves the previous install and receipt byte-identical"
affects: [24-06 terminal tuning, 24-08 container e2e]
tech-stack:
  added: []
  patterns:
    - "update branch returns the executor's notes and lets its ExecutorError reach perform_update's failed outcome (the install engine's signalling)"
key-files:
  created: []
  modified:
    - installer/update.py
    - tests/test_update.py
key-decisions:
  - "The receipt rewrite needs no change: _perform rewrites the receipt for every installer-owned update regardless of kind (update.py, the owner == installer branch, unchanged); the Alacritty tracer asserts the rewritten five-artifact receipt"
  - "The config-directory proof stops at perform_update (the rebuild route). The full UpdateService route with its terminal follow-up is proven in 24-06 Task 3, per the SPEC R4 amendment recorded in the plan's review ledger (R2-12)"
  - "The failed-rebuild contract is pinned through the public cargo_distrobox.install (raises ExecutorError) plus perform_update (failed, first line as detail); the private _update_installer_owned is not called from tests (pyright reportPrivateUsage)"
requirements-completed: [ONB-02]
duration: ~1h (estimated, no timer recorded)
completed: 2026-11-13
status: complete
actuals:
  tokens: 28651
  tasks: 2
  commits: 2
commits: 2
plan_head_before: a2f4320deed77856e8b4042948d390854187b8f0
plan_head_after: 53373707e1fc313c9ae8b1176c9dbab004a48727
---

# Phase 24 Plan 05: update Alacritty by rebuilding its newer tag Summary

**Selecting `u` on an installer-owned Alacritty rebuilds the newer release tag in a fresh Distrobox, swaps the five artifacts, rewrites the receipt for them, and never touches `~/.config/alacritty`; a current tag is skipped and a failed or interrupted rebuild keeps the previous install.**

## What was built

- **Task 1 (ff696d9, tracer):** `_update_installer_owned` gained a `cargo_distrobox` branch that returns `cargo_distrobox.install(method, ExecContext(runner, platform, release_resolver(resolve_tag)))`. Its notes become `cleanup_warnings`. Its `ExecutorError` is not caught, so `perform_update` maps it to `failed`. `installer/cargo_distrobox.py` was not changed: the rebuild exposed no defect. The tracer `test_newer_alacritty_tag_rebuilds_and_keeps_the_config` runs on `Platform(os="fedora", arch="amd64", immutable=True, has_distrobox=True, has_podman=True)`, with ownership resolved through `resolve_ownership` (owner `installer`, method `cargo_distrobox`).
- **Task 2 (5337370):** three pins in `tests/test_update.py`: `test_current_alacritty_tag_plans_skip_without_a_box`, `test_failed_rebuild_raises_and_keeps_the_old_install`, `test_interrupted_rebuild_keeps_the_old_binary` (backstop).

## RED output

Task 1 (tracer, before the branch existed):

```
FAILED tests/test_update.py::test_newer_alacritty_tag_rebuilds_and_keeps_the_config
>       assert outcome.status == "updated", outcome.detail
E       AssertionError: no installer-owned update path for method kind 'cargo_distrobox'
E       assert 'failed' == 'updated'
tests/test_update.py:2228: AssertionError
```

Task 2: no RED was observed. The four `-k "rebuild or current_alacritty"` tests (the tracer plus the three new pins) passed on their first run:

```
....                                                                     [100%]
```

This is expected for this task. The no-op SKIP is already produced by `session._row` (`already current`); the failed-build and interrupt paths are guaranteed by 24-01's `install` (cleanups in `finally`, `ExecutorError` after them, staged swap with rollback), and the Task 1 branch lets them propagate. The plan says the backstop may pass at once and that this must be stated. The pins are regression guards on the update route, not new behavior. One pin needed a fix before it could be committed: a direct call to the private `_update_installer_owned` failed pyright (`reportPrivateUsage`), so the contract is asserted through the public `cargo_distrobox.install` instead.

## Verification

- `uv run pytest tests/test_update.py -k alacritty -q --no-cov -n 0`: 1 passed after Task 1 (`newer_alacritty_tag` selects the tracer).
- `uv run pytest tests/test_update.py tests/test_cargo_distrobox.py tests/test_session.py -n auto -q --no-cov`: exit 0 on the Task 2 tree.
- `make validate`: exit 0 on the Task 1 tree (after a ruff import-order fix and a pyright typing fix in the new test code) and on the Task 2 tree.
- `make test`: exit 0 on the Task 1 tree (6209 passed, 6 skipped, coverage 96.24%) and on the Task 2 tree (6212 passed, 6 skipped, coverage 96.24%).
- Config-dir proof: the tracer records the sha256 of every file under the scratch `~/.config/alacritty` (`alacritty.toml`, `themes/dark.toml`) before and after the rebuild, and asserts equality.
- Host safety: nothing was run on the host. Every box step is `FakeBox` (a recording runner that writes the build outputs); `image_exists` is monkeypatched; `RUN_ROOT` points at tmp_path; `Path.home()` is the per-test scratch HOME from the conftest. The fake alacritty is a `#!/bin/sh` text file that is never executed by the tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lint and type failures in the new test code**
- **Found during:** Task 1 and Task 2 `make validate`
- **Issue:** ruff isort wanted the `tests.test_cargo_distrobox` import block reordered; pyright flagged an untyped `lambda _ref: False` assigned to `cargo_distrobox.image_exists`; pyright flagged a direct call to the private `update._update_installer_owned` from the test.
- **Fix:** `ruff check --fix` for the import order; a typed module-level `_image_not_present(_ref: str) -> bool | None`; the failed-build contract asserted through the public `cargo_distrobox.install` with `ExecContext`. No `noqa`, `type: ignore` or `pyright: ignore` was added.
- **Files modified:** tests/test_update.py
- **Commits:** ff696d9, 5337370

**2. [Scope note] Test placement**
- The plan's acceptance grep counts `test_failed_rebuild_raises_and_keeps_the_old_install` across `tests/test_update.py` and `tests/test_cargo_distrobox.py`; it lives in `tests/test_update.py` (count 1). The Task 2 SKIP and interrupt pins also live there, since they exercise the update route and the plan's file list for the task is `tests/test_update.py`.

## Unrun / out of scope

- `codegraph sync` failed in this worktree: no `.codegraph/` index exists here (the directory is gitignored). The `codegraph explore` call used the main checkout's index and printed a warning that it is a different worktree; the code used for edits was read directly from this worktree's files. No index was created.
- The `UpdateService` route (the terminal follow-up after `u`, which may repair a drifted owned shell region) is intentionally out of this plan; 24-06 Task 3 proves it.
- The real nested-podman rebuild (cargo time, box init, real `alacritty --version`) is not proven here; it is for the container run (24-08) or the user's UAT.
- Requirements: `requirements-completed: [ONB-02]` is recorded in this SUMMARY. `REQUIREMENTS.md` was not edited; the orchestrator owns the state writes after the wave merges.

## Known Stubs

None.

## Threat Flags

None. The release tag reaching the rebuild as a git ref is the surface of T-24-19, already guarded by 24-01's `_TAG_RE` check before any box (`test_tag_is_validated_before_any_box`); the update writes only the five receipt-proven paths (T-24-20, pinned by the config checksum). No new endpoint, auth path, file-access pattern or schema change was introduced.

## Self-Check

- FOUND: installer/update.py (cargo_distrobox branch in `_update_installer_owned`)
- FOUND: tests/test_update.py (tracer, SKIP pin, failed-rebuild pin, interrupt pin)
- FOUND commits (ancestors of HEAD): ff696d9, 5337370
- NOT modified: .planning/STATE.md, .planning/ROADMAP.md
