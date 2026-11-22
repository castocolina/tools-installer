# Phase 35 Review Disposition

Orchestrator triage of the read-only gates of 2026-11-22 (internal deep reviewer `35-REVIEW.md`: 0 critical, 0 high, 2 medium, 8 low, 1 info; security auditor `35-SECURITY.md`: SECURED, 21 threats registered: 18 closed, 3 accepted, 0 open; external lane `opencode-referee-one`: 14 findings; the real `update-all` container check: PASS twice).

## Fixed

Lanes 1 to 6, 8, 9, 10 and 13, ME-01, LO-01, LO-02, LO-06, LO-07, NE-01, IN-01 and the security note on `--plan` as root (see `35-REVIEW-FIX.md`).

## Rejected, accepted or deferred, with reason

| Source | Finding | Disposition |
| ------ | ------- | ----------- |
| Lane 7 | The daily entry is recorded after slow follow-ups, not when the primary mutation is known (midnight edge, an interrupt during follow-ups) | Deferred: the harm is a repeated, idempotent update; backlog 999.36 |
| Lane 11 | The log shows the last run that reached tool execution, not necessarily the last run | Deferred: label it in the screen text; backlog 999.36 |
| Lane 12 | A hard link to another file, replaced by the same user, can pass the log append's regular-file check | Deferred: same-user residual like the lock; backlog 999.36 |
| Lane 14 | The container target writes one fixed transcript path (two orchestrator runs can mix results) | Deferred: orchestrator-run, serialized by hand; backlog 999.36 |
| ME-02 | The `limits:` and `log:` lines show only at 100x30; the detail pane is not focusable at 80x20 | Deferred: an owner UI decision (scrollable or focusable detail); the vendor-shell-edit limit is also in the docs; backlog 999.36 |
| LO-03, LO-04, LO-05 | Runner root refusal writes stderr only; a dangling `agent` link fails cursor-agent before the guard; the version probe runs the tool binary before the guard | Deferred: inherited per-tool behavior; backlog 999.36 |
| LO-08 | `_update_all` is about 160 lines with a closure over five nonlocals and classifies by message prefix | Deferred: a refactor, not a defect; backlog 999.36 |
| Security notes 2 to 7 | Uncapped output capture, uncredential-scrubbed 0600 run log, inherited environment, same-user `held_by` race, container evidence bound to HEAD | Accepted risks (logged in `35-SECURITY.md`); the HEAD binding is recorded by the orchestrator in the 35-10 summary |
