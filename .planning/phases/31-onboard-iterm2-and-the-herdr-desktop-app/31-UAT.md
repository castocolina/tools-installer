---
status: testing
phase: 31-onboard-iterm2-and-the-herdr-desktop-app
source: [31-VERIFICATION.md]
started: 2026-11-21T09:00:00Z
updated: 2026-11-23T13:00:00Z
---

## Current Test

number: 1
name: iTerm2 loads the Dynamic Profile and it becomes the default (NTERM-02)
expected: |
  On a real Mac, after the installer tunes iTerm2, the installer-owned profile appears in iTerm2 (running or not) and is the default profile; the previous default is recorded.
awaiting: the owner's Mac (no Mac host in the autonomous run; no agent may mark this passed)

## Tests

### 1. Profile loads live and becomes the default (NTERM-02, 31 D-02, D-11)
expected: iTerm2 loads the Dynamic Profile whether it is running or not and the profile is the default profile
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23 with the owner's real oh-my-zsh prompt, real key events and window screenshots; run by the agent at the owner's direction. iTerm2 loaded tools-installer.json both when started after the file was written and when the file was edited while running; `Default Bookmark Guid` was the installer's profile.

### 2. Cmd+K clear (NTERM-02)
expected: Cmd+K sends 0x0c (the screen and scrollback clear through the shell) in a pane of the installer's profile
result: [pending]
evidence: Partial, 2026-11-23, owner's Mac. With our Cmd+K row, iTerm2 asks 'Allow clearing scrollback?' and keeps the scrollback until Always Allow. Without the row, iTerm2's native Cmd+K cleared screen and scrollback and the prompt redrew: the row is unnecessary (backlog 999.37).

### 3. Option+Left and Option+Right move by word (NTERM-02, 31 D-08)
expected: word moves work through the key-map rows with Option left Normal; the Spanish `@` (Option+2 on that layout) still types
result: [pending]
evidence: Partial, 2026-11-23, owner's Mac. iTerm2: Option+Left/Right moved by word (`echo one two Xthree Yfour`). Not yet typed: the Spanish-layout `@` (Option+2).

### 4. Parent key map and the defaults messages (31 D-09)
expected: the previous default's key map is merged when readable (2-, 3- and 4-part key spellings match), and `defaults read` of an absent `Default Bookmark Guid` gives the message the code expects (research assumptions A2 and A3)
result: [pending]

### 5. Colors and new tabs, windows and splits (NTERM-02, 31 D-10)
expected: the dark-green palette is legible in light and dark mode (the RGB values are documented guesses the owner may redirect); `Recycle` opens new tabs, windows and split panes in the current directory
result: [pending]

### 6. Uninstall restores the previous default (NTERM-02, 31 D-11, orchestrator decision 2)
expected: removing iTerm2 restores the previous default profile BEFORE the cask removal and deletes the profile after it; also run the uninstall from inside iTerm2 (the cask quits the app) and with a lost or edited record (the removal must refuse with a clear message until a default is chosen in iTerm2 Settings)
result: [pending]

### 7. The herdr app on Apple Silicon macOS (NTERM-03, 31 D-12)
expected: the cask installs the herdr app; its `keys.json` carries the macOS vendor default plus the Cmd+K clear; the multiplexer's binary and `~/.config/herdr` stay untouched by its install and removal
result: [pending]

### 8. The herdr app on a Linux desktop session (NTERM-03)
expected: the app runs after the user-scope install; Ctrl+Shift+K clears in a terminal pane and the displaced picker is named in the install note and stays in the palette; a user binding is kept and reported
result: [pending]

### 9. Owner confirms the provisional decisions
expected: The owner accepts or redirects each of: 31 D-08 (Option stays Normal, key-map rows); 31 D-12 (macOS herdr-app install route); the CONTEXT amendments of 2026-11-21 (D-07 message, D-09 parent key map, D-11 restore ordering and refusal, D-16 chord grammar); the orchestrator decisions on the parent key-map rule, the keys.json edge cases (blank file counts as missing, strip deletes a created file equal to the pinned default) and the generic-e2e exclusion of herdr-app; 28 D-06 for the new variants; the accepted limits in 31-REVIEW-DISPOSITION.md (backlog 999.31)
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
