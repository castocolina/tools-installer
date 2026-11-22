# Phase 34 Plan 07 Summary

## Task 1

Commit: `e4a0bfff` — `feat(34-07): add the update check to the schedules container target`

The commit adds the `check-updates` row to the systemd, off, and direct loops, and adds strict-verdict, cell, checkout-probe, baseline, launch-status, and driver host tests.

## Verification

- **RED:** The requested targeted command failed before the shell implementation. Its tail included missing `schedules_expected_cell`, loop-membership, strict-verdict, cell, and list-test failures.
- **GREEN:** `uv run pytest tests/test_container_e2e_schedules.py tests/test_shell_scripts_path.py tests/test_schedules_engine.py -n auto -q --no-cov` exited 0.
- **Commit hook:** All six static gates passed.
- **`make validate`:** All six gates passed.
- **`make test`:** `9375 passed, 6 skipped in 86.31s`; coverage `96.44%`, above the required 90%.
- Run directories created for targeted commands were removed by their EXIT traps. The pre-existing untracked goals file was not touched.

## Decisions

- Orchestrator decision 9: **provisional, needs confirmation**. The row joins the schedules target; only the orchestrator runs the container. The container cannot prove that the session bus variable reaches `notify-send`.
- Orchestrator decision 12: **provisional, needs confirmation**. Shell changes must remain compatible with macOS bash 3.2; usage text and classified PATH lines were not changed.
- Round 1 M8: **needs confirmation**. Strict verdicts apply to both routes; direct mode has a narrower proof and an explicit gap.
- Round 2 H5 and M8: **needs confirmation**. Verdicts must be tied to the launch, and container evidence must be recorded in three groups.
- Round 3 H7, M6, M7 and H5: **needs confirmation**. Baseline reads fail closed; ambiguous activations fail; producer status, the driver’s clock rule, runtime-specific cleanup, and checkout writes require verification.
- No timer, unit, plist, notification, or container was installed or run on the real host.

## Pin edits

- `_BUILTINS` and `_IDS` gained `check-updates`, preserving the existing row-order assertions.
- The built-in and direct tests extract the new helpers because those routes call them.
- The tester stub appends the check-row log only on launch; no check-row success is pre-seeded.

## Deviations and remaining risks

The named behavior scenarios are not all covered by real assertions. In particular, the tests do not fully establish:

- A baseline read failure prevents a systemd-route launch.
- A new successful pair with the specified installer clause passes end-to-end, including the waited-line variant and matching cell.
- A direct launch that appends a valid new pair but exits nonzero fails using the real verdict functions.
- Marker creation failure, lenient `! 10:00` behavior, and the exact strict unexpected/ambiguity diagnostics in every named case.

The checkout probe uses `! -type d`, so it can report non-directory special files as well as regular files and links. The baseline’s existence test also needs review for inaccessible paths. These are unverified risks, not demonstrated passes.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commit `e4a0bfff` (the check-updates row joins every loop of the `schedules` container target; the strict, launch-attributable verdict for the check row on both routes; a checkout probe; host tests), through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's verify re-run: exit 0. The plan's five named tests appear as parametrized cases under different names (`test_strict_new_activation` covers stale, standalone busy, lone start, a fresh pair, a `waited:` entry, two starts, `start start ok`, a non-ok result and a failure; `test_strict_cell`, `test_the_checkout_probe`, `test_a_baseline_read_error_fails_closed`, `test_a_failed_launch_status_fails_the_check_row`, `test_the_direct_route_applies_the_strict_check_verdict`); every scenario is present. `make test` on the final tree, default TMPDIR: 9375 passed, 6 skipped, coverage 96.45% (a first run showed 2 setup errors from the host-state guard that did not repeat).
- REAL CONTAINER CHECK, run by the orchestrator: `scripts/container-e2e-verify.sh schedules` (2026-11-22 02:48 to 02:52, exit 0, no leftover container, no prune or reset): `ON check-updates next=2026-11-22T09:00` (daily, on by default), `TRACER_SCHEDULE_RUN_OK id=check-updates result=ok`, `TRACER_SCHEDULE_RESULT id=check-updates text=ok: 0 updates available; installer check skipped: not a git checkout` (the copied workspace has no Git metadata, so the self-update clause is the not-a-git-checkout skip), `TRACER_SCHEDULE_CELL_OK id=check-updates cell=✓ 05:49`, `TRACER_SCHEDULE_CHECKOUT_UNCHANGED id=check-updates` (the real-launch evidence that the check child left the checkout unchanged), the busy, calendar and catch-up probes (these exercise cache-cleanup, not the new row), `TRACER_SCHEDULE_OFF_OK` and `TRACER_SCHEDULES_TEARDOWN_OK`. The container cannot prove that the session bus address reaches `notify-send` (no desktop session there) and sent no notification; real Bazzite and macOS delivery are owner UAT lines.
- Container evidence kept separate: the check-row service/result/OFF/checkout evidence above is the new part; the calendar and catch-up probes are the generic cache-cleanup evidence; the `--direct` route was not run (it proves less and skips the unit OFF check).

Provisional decisions carried to the verification report (needs owner confirmation): orchestrator decision 9 (the schedules container target extended with the check-updates row; the container proves the row, the strict result and the unchanged checkout, not the bus variable or any delivery); the strict verdict rules (exactly one new start/ok pair after the baseline, fail closed on baseline or argv errors, a second pair is `RUN_AMBIGUOUS`, a coincident timer firing yields a failure not a pass).

schedules-container-check-updates: PASS (2026-11-22; row, result line, cell, checkout unchanged, OFF and teardown observed; bus variable and delivery not provable here)

orchestrator-verification: none required
