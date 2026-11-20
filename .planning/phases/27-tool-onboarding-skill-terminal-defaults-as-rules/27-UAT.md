---
status: testing
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
source: [27-VERIFICATION.md]
started: 2026-11-20T10:30:00Z
updated: 2026-11-20T10:30:00Z
---

## Current Test

number: 1
name: Real-Mac check of the macOS rules (SKILL-05 deferred UAT)
expected: |
  On the owner's Mac, the macOS behaviors the skill describes hold on real hardware once phases 28-29 implement them:
  Option+Left and Option+Right move by word through two bound chords (never the global Option-as-Alt switch),
  Cmd+K clears the screen and scrollback, and apps land in ~/Applications with their CLI linked into ~/.local/bin.
awaiting: the owner's Mac (no Mac host in the autonomous run; no agent may mark this passed)

## Tests

### 1. Real-Mac check of the macOS rules (SKILL-05 deferred UAT)
expected: The macOS behavior holds on real hardware (Option+Left/Right word navigation by two chords, Cmd+K clear, ~/Applications placement)
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
