---
status: testing
phase: 28-shared-terminal-keys-mechanism
source: [28-VERIFICATION.md]
started: 2026-11-20T14:20:00Z
updated: 2026-11-20T14:20:00Z
---

## Current Test

number: 1
name: Real-Mac redraw of the zsh Ctrl+L clear (KEYS-03)
expected: |
  On a real Mac terminal, open zsh (including a multi-line starship prompt) with the new managed block, type text and press Ctrl+L:
  the screen clears, the prompt and the typed buffer redraw, and the scrollback is erased.
awaiting: the owner's Mac (no Mac host in the autonomous run; no agent may mark this passed)

## Tests

### 1. Real-Mac redraw of the zsh Ctrl+L clear (KEYS-03)
expected: Screen clears, prompt and typed buffer redraw, scrollback is erased (multi-line starship prompt included)
result: [pending]

### 2. ESC[2J does not push the screen into scrollback before ESC[3J erases it (KEYS-03)
expected: No stale screen content is reachable by scrolling up after Ctrl+L, on the same Mac
result: [pending]

### 3. Owner confirms the provisional decisions
expected: The owner accepts or redirects each of: 28 D-06 with OQ1 (a recorded install whose file refuses or fails to read stays quiet); the amended SPEC R3 round-trip wording (apply then strip returns the original with trailing newlines removed, then one blank line if anything is left, else empty; real fix in backlog 999.27); the D-12 import-line deviation (four test import lines use tests.test_terminal_keys instead of installer.terminal_keys)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
