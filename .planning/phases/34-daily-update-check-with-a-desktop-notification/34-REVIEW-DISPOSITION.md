# Phase 34 Review Disposition

Orchestrator triage of the read-only gates of 2026-11-22 (internal deep reviewer `34-REVIEW.md`: 0 critical, 4 warnings, 7 info; security auditor `34-SECURITY.md`: SECURED, 23 of 23 threats closed, 2 accepted; external lane `opencode-referee-one`: 15 findings; the real `schedules` container check: PASS). The triage table with the decision per item is at the end of `34-REVIEW.md`; the fixes are in `34-REVIEW-FIX.md`.

## Fixed

Lanes 1 to 10, 14 and 15, WR-01 to WR-04, IN-01, IN-03, IN-04, IN-05, IN-06 (wording) and the IN-07 record.

## Rejected, accepted or deferred, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 11 | The container's Last-cell check reads the clock twice and can disagree across midnight | Deferred: orchestrator-run only, a failure not a false pass; backlog 999.34 |
| Lane 12 | In-flight refreshes are keyed by tool ids only, so a joined refresh ignores a different window or callback | Deferred: the scheduled process builds its own service; backlog 999.34 |
| Lane 13 | The manual check route inherits stdin for manager queries and reads `settings.json` before the lock | Deferred: manual route; backlog 999.34 |
| IN-02 | A save failure that persists re-notifies on every run | Accepted: now surfaced as a result-line clause; stated in the module docstring; backlog 999.34 |
| Security AR-34-01..04 | Residual git configuration, uv and manager scratch writes outside installer state, proxy values carried as for every row, the bus address scope | Accepted risks, logged in `34-SECURITY.md`; the bus address now reaches only the check child |
