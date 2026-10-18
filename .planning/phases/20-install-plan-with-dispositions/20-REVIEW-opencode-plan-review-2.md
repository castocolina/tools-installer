# Phase 20 code review round 2 (opencode, router-env/my-plan-review)

## Closure

| Round-1 finding | Status | Evidence |
|---|---|---|
| OC-02 | **Closed** | Headless settles version and skill-pack state before planning; the TUI wait joins both checks (`installer/app.py:118-135`, `installer/execute_screen.py:541-557`). |
| OC-03 | **Partial** | Headless defers refresh writes until consent (`installer/app.py:118-149`). The TUI still writes during a refresh that can precede an `esc` dismissal (`installer/catalog_tui.py:383-400`, `installer/version_status.py:1769-1780`). |
| OC-04 | **Closed** | Headless reports PATH wiring and audit errors and exits 1 (`setup.py:1527-1553`). |
| OC-05 | **Closed** | The container gate requires a valid summary for each run, rejects `not attempted` and `crashed`, and checks the exit status in both passes (`scripts/container-e2e-verify.sh:426-434`, `scripts/container-e2e-verify.sh:506`, `scripts/container-e2e-verify.sh:559-599`). |
| OC-06 | **Partial** | A handoff-only `manual` row no longer counts as work, but `ran_anything()` still counts every `failed` row. A pnpm reconfiguration refused before launching a command can therefore trigger post-run PATH work (`installer/session.py:230-239`, `installer/session.py:372-384`, `setup.py:1529-1549`). |
| OC-07 | **Closed** | A later run that did work replaces earlier run-level errors (`installer/wizard_app.py:3002-3009`). |
| OC-08 | **Closed** | Failed rows use their recorded detail when there is no install or update exception (`installer/render.py:147-163`). |

## Findings

### OC2-01 [CRITICAL] Escaping the TUI review can still commit refresh writes
- File: `installer/catalog_tui.py:383-400`, `installer/version_status.py:1325-1334`, `installer/version_status.py:1769-1780`, `installer/execute_screen.py:903-917`
- Problem: The catalog starts a refresh without holding its writes. If that refresh adopts a matching binary, retires an all-gone receipt, or saves the version cache, the user can then open the review and press `esc` without starting the run. The write has already happened, contrary to L-20-10’s pre-consent boundary.
- Fix: Apply the deferred-write boundary to TUI refreshes as well; commit the relevant writes only when the reviewed run starts.

### OC2-02 [HIGH] A rejected deferred adoption leaves a provisional receipt in the plan
- File: `installer/version_status.py:1381-1394`, `installer/receipts.py:336-348`, `installer/app.py:143-169`
- Problem: A present binary can match its digest when the headless plan is printed, then change while the user considers the prompt. On Yes, `commit_adoption()` rejects the changed fingerprint, but its `False` result is discarded. The published state and `skipped — already current` row still treat the binary as adopted, and the run can exit 0 without reporting the change.
- Fix: Check deferred-commit results. If adoption is rejected, invalidate the provisional state and rebuild or refuse the plan before execution.

### OC2-03 [HIGH] Failed prerequisites do not block updates or reconfigurations
- File: `installer/session.py:479-490`, `installer/session.py:528-556`
- Problem: The execution-time `unresolved` dependency check applies only to install, repair, and reinstall. If a missing `pnpm` fails to install, an already-present dependent planned for update or reconfiguration still runs its update or configuration commands instead of ending `dependency failed`.
- Fix: Check unresolved `requires` before dispatching every runnable disposition. Do not treat a failed update of an already-present prerequisite as making that prerequisite absent.

### OC2-04 [MEDIUM] A successful reconfiguration can hide a synchronization warning
- File: `installer/session.py:365-371`, `installer/session.py:424-439`, `installer/render.py:147-150`, `installer/render.py:280-289`
- Problem: Terminal sync can configure Kitty while warning that WezTerm has an unsupported configuration shape. Reconfiguration stores the warning in `RowOutcome.detail` and returns `done`, but the finished row omits done details and the end-of-run report prints no reconfiguration details. The user sees only `reconfigured`.
- Fix: Print non-empty successful reconfiguration details once in the shared end-of-run report.

## Summary

**1 CRITICAL, 2 HIGH, 1 MEDIUM.** Fix the TUI consent boundary first, then reject stale deferred adoptions, then enforce failed prerequisites across every runnable disposition.

Not checked: live TUI behavior, container execution, and full tests. No files were edited or installs run.
