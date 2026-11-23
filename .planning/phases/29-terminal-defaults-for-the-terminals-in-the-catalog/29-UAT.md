---
status: testing
phase: 29-terminal-defaults-for-the-terminals-in-the-catalog
source: [29-VERIFICATION.md]
started: 2026-11-20T20:30:00Z
updated: 2026-11-23T13:00:00Z
---

## Current Test

number: 1
name: kitty on a real Mac (TERM-01)
expected: |
  After the installer tunes kitty on a Mac (cask install into ~/Applications): Option+Left and Option+Right move by word, Cmd+K clears the screen and scrollback, a new tab and a new window open in the current directory, and macos_option_as_alt stays unset.
awaiting: the owner's Mac (no Mac host in the autonomous run; no agent may mark this passed)

## Tests

### 1. kitty on a real Mac (TERM-01)
expected: Option+Left/Right word moves, Cmd+K clear (screen and scrollback), new tab and window in the same directory; the install note names the displaced clear_terminal to_cursor
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23 with the owner's real oh-my-zsh prompt, real key events and window screenshots; run by the agent at the owner's direction. kitty: Option+Left/Right moved by word (`echo one two Xthree Yfour` ran); Cmd+K and Ctrl+L cleared the screen, redrew the prompt and erased the scrollback (the first run wiped the prompt; fixed by sending ESC[H ESC[2J ESC[3J before the redraw, installer/tweaks.py); a new tab (Cmd+T), window (Cmd+N) and split (Cmd+Enter) all opened in the marker directory; the install note named the displaced `clear_terminal to_cursor`.

### 2. WezTerm on a real Mac (TERM-02)
expected: Option+Left/Right word moves, Cmd+K clear, new tab in the same directory (SpawnTab and SpawnWindow were proven on Linux by the D-07 container check)
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23 with the owner's real oh-my-zsh prompt, real key events and window screenshots; run by the agent at the owner's direction. WezTerm on a clean install: Option+Left/Right moved by word; Cmd+K and Ctrl+L cleared screen and scrollback with the prompt redrawn; a new tab and a new window opened in the marker directory. A config that binds then disables Super+K (the owner's old wezterm-setup) left Cmd+K dead; tracked in backlog 999.37.

### 3. The kitty cask install and uninstall on a real Mac (TERM-01, 29 D-05)
expected: the cask puts kitty.app in ~/Applications, the installer's tuning region is removed on uninstall and a config the installer created is deleted
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23, run by the agent at the owner's direction. kitty installed into ~/Applications/kitty.app (brew cask and the installer engine); the kitty-keys region was written; uninstall removed the app, the region, the record and the ~/.config/kitty the installer created.

### 4. Live Konsole 26.x capture (TERM-04, 29 D-09)
expected: the stock Ctrl+Shift+K is Clear Scrollback and Reset, and after a user removes it the saved sessionui.rc matches what the detector reads; only the Shortcut_p.h source citation stands in for this today
result: [pending]

### 5. Owner confirms the provisional decisions
expected: The owner accepts or redirects each of: 28 D-06 (a recorded install stays quiet on drift; the kitty clear_all_shortcuts refusal and the WezTerm status check follow it); 29 D-09 (Konsole is report-only, with SPEC R4, ROADMAP SC3 and TERM-04 amended); the accepted limits in 29-REVIEW-DISPOSITION.md
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
