---
status: testing
phase: 34-daily-update-check-with-a-desktop-notification
source: [34-VERIFICATION.md]
started: 2026-11-22T06:00:00Z
updated: 2026-11-22T06:00:00Z
---

## Current Test

number: 1
name: Real Bazzite notification: run the check with a changed outdated set on the desktop session and from the systemd user unit
expected: |
  A notification appears; the session bus address reaches notify-send from the unit on a real session
awaiting: the owner's Bazzite desktop, Mac and real sessions (no such host in the autonomous run; no agent may mark any of these passed)

## Tests

### 1. Real Bazzite notification: run the check with a changed outdated set on the desktop session and from the systemd user unit
expected: A notification appears; the session bus address reaches notify-send from the unit on a real session
why_human: Needs a real desktop session; tests and the container use fakes
result: [pending]

### 2. Real-Mac osascript notification with the Script Editor permission, and a silently dropped one
expected: Delivered after the one-time permission; a drop stays ok with the row detail naming the permission
why_human: Real macOS behavior; osascript argv without -- is provisional
result: [pending]

### 3. The daily timer fires on Bazzite (systemd user timer) and macOS (launchd), including the login catch-up lateness
expected: One start and ok pair per firing; a catch-up before the notification daemon can arrive a day late
why_human: No timer, unit or plist may be installed from this verification
result: [pending]

### 4. Self-check on a real shallow clone (and a real behind-origin checkout)
expected: Fixed skip category or the installer behind origin/main clause; the checkout is unchanged
why_human: Unit tests inject git; the container copy has no Git metadata
result: [pending]

### 5. Owner confirmation of the provisional decisions: the 34-0N-SUMMARY.md lines, the eighth row and table height 9, the osascript argv without --, the bus address scope (runner-only, check child only), the self-update skip rules (detached HEAD, non-main, not worktree root, partial clone), a shrinking non-empty set notifying again, the daily limit as timer cadence, the SPEC and ROADMAP amendments, proxy values carried as for every row, uv and manager scratch writes accepted, the confirmed-only membership rule, brew under-reporting (no brew update)
expected: Each confirmed, or reopened as a follow-up
why_human: Flagged provisional or needs confirmation in the 34-01..10 summaries, the review triage and the SPEC and ROADMAP amendments
result: [pending]
