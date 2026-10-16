---
phase: 19-one-tool-state-with-health-plus-receipts
plan: "24"
subsystem: presence-and-receipts
tags: [is_installed, shim, receipts, smoke, gap-closure]

requires:
  - phase: 19-one-tool-state-with-health-plus-receipts
    provides: the M9 shim skip on the bin-dir loops of is_installed, and the receipt writer called after a successful method
provides:
  - a PATH hit on this installer's own ban or redirect shim is never presence
  - an app receipt records smoke "ok" only when the method declares a cli
affects: [cli-install, presence, receipts]

actuals:
  tokens: 29803
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "every presence branch that reads a file named after the tool skips guards.is_our_shim for guarded names"
    - "receipt smoke is true to the check that ran, not to the method kind"

key-files:
  created: []
  modified:
    - installer/status.py
    - tests/test_status.py
    - installer/engine.py
    - tests/test_engine.py

key-decisions:
  - "The PATH shim skip reuses _is_installer_shim, so a non-guarded name still returns True without opening the file"
  - "App smoke is decided from method.params.get('cli') is not None, the same condition _stage_and_swap_app smokes under; download kinds stay smoke 'ok'"

patterns-established:
  - "Pattern: a shim on PATH falls through to the declared-bin, implicit-bin and app checks instead of short-circuiting presence"

requirements-completed: [STATE-04, STATE-03]

coverage:
  - id: D1
    description: "A PATH hit that is this installer's own ban or redirect shim is not presence; the same path rewritten as a real binary is"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_installer_shim_on_path_is_never_presence"
        status: pass
    human_judgment: false
  - id: D2
    description: "A PATH hit for a name this installer never shims stays presence and never opens the file"
    requirement: STATE-04
    verification:
      - kind: unit
        ref: "tests/test_status.py#test_installer_shim_on_path_is_never_presence"
        status: pass
    human_judgment: false
  - id: D3
    description: "An app receipt records smoke ok only when the method declares a cli, and null otherwise"
    requirement: STATE-03
    verification:
      - kind: unit
        ref: "tests/test_engine.py#test_app_receipt_records_smoke_only_with_a_cli"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-10-16
status: complete
---

# Phase 19 Plan 24: Shim-on-PATH presence and honest app smoke receipts Summary

**A PATH hit on this installer's own shim is no longer presence, and an app receipt records a smoke only when the method declared a CLI**

## Performance

- **Duration:** 8 min
- **Started:** 2026-10-16T20:34:34Z
- **Completed:** 2026-10-16T20:42:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `is_installed` skips a PATH hit that `_is_installer_shim` recognizes, so `setup.py --all --yes` no longer treats a leftover pnpm redirect shim as the tool (G13, review WR-02 / M9).
- An `app` receipt writes `smoke: "ok"` only when `method.params.get("cli") is not None`; an app without a CLI records `smoke: null` (G22 / IN-04). Download kinds are unchanged.

## Task Commits

Each task was committed atomically (test and code together; RED captured before the implementation):

1. **Task 1: the installer's own shim found on PATH is never presence (G13)** - `972304a` (fix)
2. **Task 2: an app receipt records a smoke only when one ran (IN-04)** - `eb03e11` (fix)

**Plan metadata:** this commit (docs: plan summary)

## Files Created/Modified

- `installer/status.py` - PATH branch of `is_installed` requires `not _is_installer_shim(tool, Path(resolved))`; docstring names the skip
- `tests/test_status.py` - `test_installer_shim_on_path_is_never_presence` (location x sentinel)
- `installer/engine.py` - receipt `smoke="ok"` only for download kinds, apps with a declared `cli`, or a manager smoke that ran
- `tests/test_engine.py` - `test_app_receipt_records_smoke_only_with_a_cli`

## Decisions Made

None - followed the plan as specified. The smoke condition is the plan's `method.params.get("cli") is not None` combined with `apps.APP_KINDS`, which keeps the must-have `APP_KINDS` occurrence in `engine.py`.

## Deviations from Plan

None - plan executed exactly as written.

## TDD RED evidence

### Task 1

`uv run pytest tests/test_status.py -q --no-cov -k "shim_on_path"` — 4 failed, exit 1. Each case:

```
>       assert is_installed(tool("npx"), which=which, default_bin_dir=bin_dir) is False
E       AssertionError: assert True is False
```

Failed ids: `[# tools-installer-ban-shim-declared]`, `[# tools-installer-ban-shim-implicit]`, `[# tools-installer-redirect-shim-declared]`, `[# tools-installer-redirect-shim-implicit]`. The PATH branch returned True before the shim-aware loops ran.

### Task 2

`uv run pytest tests/test_engine.py -q --no-cov -k "smoke_only_with_a_cli"` — 1 failed, 1 passed, exit 1:

```
_________ test_app_receipt_records_smoke_only_with_a_cli[without-cli] __________
>       assert written.smoke == smoke
E       AssertionError: assert 'ok' == None
```

`[with-cli]` passed before the change (the existing behavior was already correct for an app that declares `cli`).

## Verify-command results

- Task 1: `uv run pytest tests/test_status.py -q --no-cov -k "shim or is_installed or implicit"` — 23 passed. `shim_on_path` — 4 passed. `grep -c '_is_installer_shim(tool, Path(resolved))' installer/status.py` = 1. Suppression count 487 → 487.
- Task 1 gates: `make validate` exit 0; `make test` 4526 passed, 4 skipped, coverage 95.97%.
- Task 2: `uv run pytest tests/test_engine.py -q --no-cov -k "smoke or receipt"` — 29 passed. `smoke_only_with_a_cli` — 2 passed. `grep -c 'method.params.get("cli") is not None' installer/engine.py` = 1. `tests/test_engine.py` 2022 → 2055 lines, tests 65 → 66, trailing newline kept. Suppressions 487 → 487. `git diff --exit-code fde3e68 -- pyproject.toml uv.lock` clean.
- Task 2 gates: `make validate` exit 0; `make test` 4528 passed, 4 skipped, coverage 95.97%.
- Plan verification: `uv run pytest tests/test_status.py tests/test_engine.py -n auto -q --no-cov` exit 0.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- STATE-04's "no presence path counts an installer shim" now includes the default `which=None` call used by `setup.py` and `install_tool(present=None)`.
- Receipt `smoke` matches what the install ran for app methods. Nothing reads `Receipt.smoke` yet; the field is now honest for the later consumer.

## Self-Review

- `is_installed` PATH condition is exactly the review's proposed check: resolved, not a shim, not a macOS stub.
- A shim hit falls through; the later loops already skip it, so a shim-only machine reads absent.
- App smoke uses the declared-`cli` condition, not a second smoke execution. Download kinds still record `"ok"`.
- No new suppression, no dependency change, no host mutation.

---
*Phase: 19-one-tool-state-with-health-plus-receipts*
*Completed: 2026-10-16*
