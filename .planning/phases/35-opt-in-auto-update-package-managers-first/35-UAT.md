---
status: testing
phase: 35-opt-in-auto-update-package-managers-first
source: [35-VERIFICATION.md]
started: 2026-11-22T18:15:00Z
updated: 2026-11-22T18:15:00Z
---

## Current Test

number: 1
name: Real macOS run of the nightly update-all row
expected: |
  Turn the row on in the Schedules screen; the run on macOS leaves casks alone, updates managers then dependents, and writes the run log and the summary line
awaiting: the owner's real hosts and sessions (no such host in the autonomous run; no agent may mark any of these passed)

## Tests

### 1. Real macOS run of the nightly update-all row
expected: Turn the row on in the Schedules screen; the run on macOS leaves casks alone, updates managers then dependents, and writes the run log and the summary line
why_human: Only Linux containers were exercised; no macOS host is available to the agents
result: [pending]

### 2. Real Bazzite first night: the 03:00 timer fires under systemd and the real outdated set is handled
expected: One start and result pair at 03:00; the log lines match the real outdated tools; nothing runs as root; the once-a-day record skips the per-tool rows afterwards
why_human: A timer firing and a real outdated set cannot be reproduced in a disposable container; no timer may be installed from the autonomous run
result: [pending]

### 3. A real desktop notification from the unit after a real run
expected: A notification lists the updated and failed catalog ids; a run that only skipped sends none
why_human: The container had no session bus (notify-send exited 1, expected); only the adapter is unit-tested
result: [pending]

### 4. The effect of `uv self update` on the shell rc files of a real user
expected: The rc files stay unchanged (UV_NO_MODIFY_PATH=1 is set); a vendor edit remains an accepted limit
why_human: The container proved `changed=none` for a fresh user only
result: [pending]

### 5. Owner confirmation of the provisional decisions listed in 35-10-SUMMARY.md 'Provisional decisions for the owner': D-03, D-05 to D-14, D-20, orchestrator decisions 1 to 9 and O7, the review rounds 1 to 3 (recency windows 6 h manager and 20 h others instead of fresh-this-pass, run_guarded, the kernel-lock verified parent handoff, the per-command process group and stop budget, the `$PNPM_HOME/bin` scheduled PATH, `HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK`, plan mode through hold_writes, notify only when updated plus failed is above zero) and the dated SPEC, ROADMAP and REQUIREMENTS amendments
expected: Each confirmed, or reopened as a follow-up
why_human: Marked provisional and needs-confirmation by design
result: [pending]

### 6. Owner triage of backlog 999.36: the deferred review items (Lane 7, 11, 12, 14, LO-03, LO-04, LO-05, LO-08) and ME-02 (the limits and log lines show only at 100x30, the detail pane is not focusable at 80x20: scrollable or focusable detail is an owner UI decision)
expected: The owner decides the detail pane and accepts or schedules the other deferrals
why_human: ME-02 is an owner UI decision; the rest are accepted-risk deferrals
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps

[none yet]
