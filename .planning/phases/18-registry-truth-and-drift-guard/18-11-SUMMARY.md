---
phase: 18-registry-truth-and-drift-guard
plan: "11"
subsystem: installer
tags: [macos, app, sha256, smoke, staged-swap]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: pinned_url, staged_member, manager PATH sandbox (18-16, 18-09, 18-19)
provides:
  - Shared _stage_and_swap_app for install_app and update_app with checksum + CLI containment
  - install_app returns verification reason; engine and render report app outcomes
  - Staged CLI smoke on install only (update passes smoke_argv=None)
affects: [18-15, 18-20]

actuals:
  tokens: ~22500
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "App zips use plain curl/ditto argv, sha256 before ditto, pre-swap staged_member + X_OK (+ smoke on install)"

key-files:
  created: []
  modified:
    - installer/apps.py
    - installer/engine.py
    - installer/render.py
    - installer/executors.py
    - tests/test_apps.py
    - tests/test_engine.py
    - tests/test_render.py
    - tests/test_download.py

key-decisions:
  - "Removed executors.link_executable; replace_symlink via _relink_app_cli is the only link path"
  - "_undo_app_swap unlinks a CLI symlink created on fresh install when no original target was captured"

patterns-established:
  - "fixture_runner materializes ditto extraction targets from the last argv path"

requirements-completed: [REG-04, REG-05]

coverage:
  - id: D1
    description: Pinned app zip verified before install; mismatch and bad CLI move nothing
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_apps.py#test_pinned_app_is_verified_and_installed
        status: pass
      - kind: unit
        ref: tests/test_engine.py#test_pinned_app_mismatch_moves_nothing
        status: pass
    human_judgment: false
  - id: D2
    description: Unpinned app installs flagged unverified; render shows app verification lines
    requirement: REG-04
    verification:
      - kind: unit
        ref: tests/test_apps.py#test_unpinned_app_installs_unverified_with_a_reason
        status: pass
      - kind: unit
        ref: tests/test_render.py#test_render_verification_covers_app_outcomes
        status: pass
    human_judgment: false
  - id: D3
    description: Staged CLI smoke on install; broken CLI never displaces live bundle; update never smokes
    requirement: REG-05
    verification:
      - kind: unit
        ref: tests/test_apps.py#test_broken_app_cli_fails_and_keeps_the_existing_bundle
        status: pass
      - kind: unit
        ref: tests/test_apps.py#test_update_app_does_not_smoke
        status: pass
    human_judgment: false
  - id: D4
    description: draw.io-desktop macOS CLI answers default --version smoke on real macOS host
    requirement: REG-04
    verification: []
    human_judgment: true
    rationale: macOS CI backstop; plan 18-20 may declare smoke_argv with in-host evidence

duration: 90min
completed: 2026-10-15
status: complete
---

# Phase 18 Plan 11 Summary

**macOS app zips now share the download path’s guarantees: pinned sha256 before ditto, contained staged CLI checks, install-only smoke, and verification lines for app outcomes.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 2
- **Files modified:** 8 (+ summary)

## Accomplishments

- Replaced the `sh -c` curl|ditto|mv install pipeline with `_stage_and_swap_app` shared by `install_app` and `update_app`.
- Pinned and declared sha256 values are checked on the staged zip before extraction; engine returns `CHECKSUM_MISMATCH` on failure.
- Pre-swap `staged_member` + `os.access(X_OK)`; install runs `smoke_binary` before the aside-move; updates skip smoke.
- `_undo_app_swap` removes a CLI link created on a fresh install when relink/validate fails after swap.
- Deleted unused `executors.link_executable`.

## Task Commits

1. **Task 1: pinned macOS app verified end to end** — `418ca10` (feat)
2. **Task 2: smoke staged app CLI before swap** — `4af84a5` (feat)

## TDD RED evidence (Task 1, trimmed)

Before implementation, new tests failed as expected, e.g.:

```
FAILED tests/test_apps.py::test_install_app_builds_curl_ditto_mv_pipeline
FAILED tests/test_apps.py::test_pinned_app_is_verified_and_installed
FAILED tests/test_engine.py::test_pinned_app_mismatch_moves_nothing
FAILED tests/test_render.py::test_render_verification_covers_app_outcomes
```

Task 2 RED (before `smoke_binary` wiring):

```
FAILED tests/test_apps.py::test_broken_app_cli_fails_and_keeps_the_existing_bundle
FAILED tests/test_apps.py::test_app_smoke_uses_the_declared_argv
```

## Verify commands

- `uv run pytest tests/test_apps.py tests/test_engine.py tests/test_render.py -q --no-cov -k "pinned_app or unpinned_app or covers_app or directory_links_nothing or staged_cli or unpinned_app_url or after_relink"` → 9 passed
- `uv run pytest tests/test_apps.py -q --no-cov -k "smoke or broken_app_cli"` → 4 passed
- `make validate && make test` → pass (3796 passed, 4 skipped; coverage 95.39%)

## Deviations from Plan

- Rewrote legacy app install tests that asserted the old `sh -c` argv in the same commits as the implementation (plan executor rule).
- Extended `tests/test_download.py::fixture_runner` for plain `ditto` argv (plan-permitted one-time extension).
- Applied edits to `tests/test_download.py` and `tests/test_engine.py` via a short Python patch script to avoid tool truncation on large files.

## Issues Encountered

- Large-file edit tool truncated `tests/test_download.py` once; restored from git and patched with Python.

## Final review

Self-review (no subagent tool): diff matches plan truths; acceptance greps satisfied (`sh -c` count 0, `pinned_url(method)` 1, `smoke_binary(` 1).

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
