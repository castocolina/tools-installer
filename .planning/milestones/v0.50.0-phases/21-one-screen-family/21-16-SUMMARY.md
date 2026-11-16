---
phase: 21-one-screen-family
plan: "16"
subsystem: tui
tags: [mutation-lock, textual, doctor, install-run]
requires: ["21-15"]
provides:
  - "MutationLock base class shared by UnifiedApp and the _DoctorHost test host"
  - "GLOBALS_REINSTALL and INSTALL_RUN holders (MutationHolder is complete: six members)"
  - "lock check at tier enter, Doctor enter and r"
affects: [21-21]
key-files:
  modified:
    - installer/enums.py
    - installer/wizard_app.py
    - installer/catalog_tui.py
    - tests/test_screen_family.py
    - tests/test_wizard_app.py
    - tests/test_layout_80x20.py
status: complete
requirements: [UI-05]
actuals:
  tokens: 24000
  tasks: 2
  commits: 4
plan_head_before: 6928edb9fb526e930ff8d5c37ade0b4ccd555578
plan_head_after: 176d88fda4683277ef70cb3a7382cf696dbcc7f8
---

# Phase 21 Plan 16: the app lock finished Summary

One `MutationLock` base class now guards every mutating key; the pnpm reinstall and the install run hold it with fixed nouns, and every holder's refusal is pinned as a full string.

## Commits

- fff45cc test(21-16): every mutating key is refused during a removal (RED)
- 9ac2df7 feat(21-16): every mutating key checks the app lock
- bb1312c test(21-16): the pnpm reinstall and the install run hold the app lock (RED)
- 176d88f feat(21-16): the pnpm reinstall and the install run hold the app lock

## RED output

Task 1 (`-k "every_mutating_key or navigation_works"`): 3 of 8 failed, as expected, because tier enter, Doctor enter and Doctor r did not check the lock yet. The other four matrix cases (Policies space with and without a job, `t`, `m`) and the navigation pilot already passed (21-13/21-15 had wired them).

```
FAILED test_every_mutating_key_is_refused_during_a_removal[tier_enter]
FAILED test_every_mutating_key_is_refused_during_a_removal[doctor_enter]
FAILED test_every_mutating_key_is_refused_during_a_removal[doctor_r]
```

Task 2: eight tests failed (install run, reinstall hold, reinstall crash, the 80x20 backstop, and four early-return cases: running, auditing, unknown report, nothing managed). The RED commit adds the two `MutationHolder` members as the only stub the tests need to type-check, so the holder noun table cases pass in RED by construction.

## GREEN

`make validate` exit 0, `make test` exit 0: 5067 passed, 4 skipped (before this plan's last commit: 5051 at Task 1).

Collected counts (start -> end): tests/test_screen_family.py 73 -> 96, tests/test_layout_80x20.py 15 -> 16, tests/test_wizard_app.py 319 -> 319.

## Moved lock methods

`mutation_in_flight`, `begin_mutation`, `end_mutation` and `refuse_if_mutating` moved verbatim from `UnifiedApp` into `class MutationLock` (a plain class; `_mutation_holder` is a class attribute defaulting to None, so no `__init__` is needed and the host `App.__init__` chain is untouched). `UnifiedApp(MutationLock, App[...])` and `_DoctorHost(MutationLock, App[None])`.

## Measured width of the longest refusal

`A pnpm reinstall is running; wait for it to finish. Navigation still works.` is 75 cells (the policy-toggle refusal is 74). The backstop at 80x20 asserts at most 78 cells, one rendered row, and the footer still on row 19 (the last row).

## First-run link-mode pick

It is answered once at launch, before any holder but the default-daemon apply can exist, and does not check the lock (its setter does not race the daemon's unit files). Unchanged.

## Doctor early returns

Silent (0 passes): `enter` after the fix applied, `r` after the reinstall finished. Refusals (exactly 1 pass): `r` while a reinstall runs (through the lock), `r` while the audit runs, `r` with an unreadable global set (its re-audit is still started), `r` with nothing managed. The `report is None` branch is unreachable once the audit has answered (it returns behind `globals_auditing`), so it has no test case.

## Default-daemon refuse-all regression

Carried forward from 21-15: while the on-by-default daemon apply runs, every mutation is refused with `A daemon apply is running; wait for it to finish. Navigation still works.`, not only the daemon's own policy row. In production the window is from `UnifiedApp.__init__` until the apply worker posts `DaemonDefaultApplied`. With this plan, tier `enter` (install) is refused in that window too; kept by design (D-05). No test measured the window in wall time: the pilots hold the apply on an event, and no test in this plan observed install `enter` at launch.

## Deviations from Plan

**1. [Test shape] Install-run test drives the real flow without a held "runner" seam**: the install seam (an `install` callable passed through `ExecuteInputs`) blocks on an event; tier space+enter opens `ExecuteScreen`, `enter` starts the run. No deviation in behavior, noted because the plan said "runner".

**2. [Test shape] 80x20 backstop uses a published removable tool on Uninstall** (`space`, `enter`, confirm `enter`), since the default layout app has no selectable Uninstall rows. A Doctor refusal was tried first and is not visible at 80x20 (the Doctor card covers the status row); that is pre-existing layout, out of scope, and is recorded in `deferred-items` terms here only.

**3. [Test shape] Reinstall crash**: `run_live` does not catch `RuntimeError`, so the error shown is the worker's default `the reinstall did not complete`, not `boom`. The test asserts that string, which is the `finally:` path the plan specifies.

**4. [Shared helper edit]** `_policy_app` and `_family_app` in tests/test_screen_family.py gained optional parameters (`app_cls`, `fix`, `node_globals`, `reinstall_globals`, `execute`). No existing test was changed or deleted.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED

Commits fff45cc, 9ac2df7, bb1312c, 176d88f exist on the branch; `make validate && make test` exit 0.
