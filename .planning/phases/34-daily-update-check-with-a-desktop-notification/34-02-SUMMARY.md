# Phase 34 Plan 02 Summary

- **Task 1 — `e77cc2c1`:** Added the Linux and macOS notifier seam, safe `RunDeps` default, and setup wiring.
- **Task 2 — `e4663ad6`:** Forwarded the session bus address to runner children; added tests for forwarding, absence, token exclusion, and unit-environment rejection.

## Verification

- **Task 1 RED/GREEN:** The earlier executor’s output was not available in this split run. Its tests passed in Task 2’s targeted run and the final suite.
- **Task 2 RED tail:** `FAILED tests/test_schedule_runner.py::test_child_env_passes_the_session_bus_address` — `KeyError: 'DBUS_SESSION_BUS_ADDRESS'`.
- **Task 2 GREEN tail:** Targeted command completed at `[100%]`, exit 0, with one existing skip. Additional runner-referencing test files also passed.
- **`make validate` tail:** All six gates passed: lint, format-check, typecheck, security, dead-code, and shellcheck.
- **`make test` tail:** `9221 passed, 6 skipped in 87.65s`; coverage `96.38%`, above the required 90%.

Each executor-created run directory was removed by its exit trap. The coverage artifact produced by the final suite was removed.

## Decisions

- **34 D-16 (locked):** The shared notifier seam lives in `installer/notify.py`; the stdlib schedule runner cannot import `installer`.
- **34 D-17 (own reasoning, needs confirmation):** Linux uses the specified `notify-send` argv and passes or derives the session bus address without baking it into a unit.
- **34 D-18 (own reasoning, needs confirmation), amended by orchestrator decision 4 (needs confirmation):** macOS uses data-only argv without `--`. Real-Mac delivery, Script Editor permission attribution, and silent drops remain owner UAT.
- **34 D-11 (locked):** Lookups remain anonymous; GitHub token variables do not reach the runner child.
- **Round 1 review (needs confirmation):** An unusable runtime directory falls back to the UID socket; the module documents the caller’s plain-text and markup contract.
- **Round 2 review (needs confirmation):** Socket-probe errors fall through; failure reasons do not echo argv; a fake `osascript` child is tested; `reason_line` strips C1 controls.
- **Round 3 review (needs confirmation):** Real-child tests isolate the bus and process environment; notifier reasons are fixed by exit code even with stderr; byte equivalence belongs to the assembled result line; notifier children receive closed stdin.
- **Orchestrator decision 2 (provisional, needs confirmation):** `RunDeps.notify` has a safe default after `context`.
- **Orchestrator decision 3 (provisional, needs confirmation):** The unit-environment restriction is enforced by `schedules.clean_unit_path` and `daemon.check_environment`; only the runner forwards the bus address.
- **Orchestrator decision 12 (provisional, needs confirmation):** Notifier tests use injected dependencies or fake executables.
- Real desktop and Mac notifications remain owner UAT; no real notification was sent.

## Deviations and limits

No Task 2 tests named in the plan were omitted. Task 1’s original RED and GREEN output could not be recovered from Git, so it is not reproduced here.

No timer, unit, plist, container, or real notification was run; real desktop delivery remains unverified.

## Orchestrator verification

Verified by the orchestrator on 2026-11-22:

- Commits `e77cc2c1` (Task 1: `installer/notify.py`, the notifier seam for Linux `notify-send` and macOS `osascript`, the bus-address fallback, fixed failure categories) and `e4663ad6` (Task 2: the runner's child gets `DBUS_SESSION_BUS_ADDRESS`; `RunDeps.notify`; setup wiring), each through the six-gate commit hook; tree clean afterwards except the untracked goals file.
- The plan's non-make verifies re-run through `run_plan_verifies.py`: all exit 0; every `<behavior>` test exists. `make test` on the final tree, default TMPDIR: 9221 passed, 6 skipped, coverage 96.38%; `tests/test_notify.py` also passes on Python 3.15.
- No timer, unit, plist or container was run and NO real notification was sent. Real Bazzite desktop delivery, the session bus address reaching `notify-send` from a systemd user unit, and macOS `osascript` delivery with the Script Editor permission are owner UAT lines.

Provisional decisions carried to the verification report (needs owner confirmation): D-16 to D-18 as amended by orchestrator decisions 3 and 4 (the bus address passed through the runner's environment only, never serialized into a unit; `--` kept for `notify-send`, dropped from the `osascript` argv); the bus fallback order (`XDG_RUNTIME_DIR/bus` then `/run/user/<uid>/bus`, a raising probe falls through); notifier failure reasons fixed by exit code, never the argv or message body; the caller contract (plain text only).

orchestrator-verification: none required

orchestrator-verification: none required
