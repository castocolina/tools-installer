---
status: testing
phase: 30-onboard-ghostty
source: [30-VERIFICATION.md]
started: 2026-11-21T03:00:00Z
updated: 2026-11-23T12:00:00Z
---

## Current Test

number: 1
name: Ghostty cask install on a real Mac (NTERM-01)
expected: |
  On a real Mac the catalog installs Ghostty from the official cask into ~/Applications (Ghostty.app); uninstall removes it, the installer's keys region is stripped and a config the installer created is deleted.
awaiting: the owner's Mac (no Mac host in the autonomous run; no agent may mark this passed)

## Tests

### 1. Ghostty cask install and uninstall on a real Mac (NTERM-01, 30 D-03)
expected: Ghostty.app lands in ~/Applications; no CLI link is promised (the CLI stays inside the bundle); uninstall removes the app and the installer-owned config
result: pass
evidence: Verified live on the owner's Intel Mac (macOS 15.8.3) on 2026-11-23, run by the agent at the owner's direction. Ghostty.app landed in ~/Applications with no CLI link; uninstall removed the app and the installer-created config directory.

### 2. macOS keys (NTERM-01)
expected: Cmd+K clears the screen and scrollback; Option+Left and Option+Right move by word (including the Spanish layout); a new tab, window and split open in the same directory
result: [pending]
evidence: Partial, 2026-11-23, owner's Mac. Ghostty: Cmd+K and Ctrl+L cleared screen and scrollback with the prompt redrawn, Option+Left/Right moved by word, new tab, window and split opened in the marker directory. Not yet typed: the Spanish-layout `@` (Option+2).

### 3. macOS effective config (NTERM-01, 30 D-13)
expected: `~/Applications/Ghostty.app/Contents/MacOS/ghostty +show-config` and `+list-keybinds` show the `super+k` line and no `macos-option-as-alt`; the file the resolver wrote is the one Ghostty reads
result: [pending]
evidence: Partial, 2026-11-23, on the owner's Intel Mac: `+list-keybinds` showed `super+k=text:\x0c` and the config held no macos-option-as-alt; `+show-config` was not captured (the app's first-launch Gatekeeper prompt blocked the CLI while the screen was locked).

### 4. AppImage through the host's FUSE on Bazzite (NTERM-01, 30 D-18)
expected: the pinned community AppImage mounts through the host's own FUSE and `ghostty --version` prints `Ghostty 1.4.0` (the container run proved extract-and-run only; rootless podman denies the FUSE mount)
result: [pending]

### 5. KDE menu entry and TERMINFO on Bazzite (NTERM-01, 30 D-07)
expected: Ghostty opens from the KDE application menu, runs zsh, `echo $TERM` and `infocmp xterm-ghostty` resolve inside the window, arrows and Ctrl+L work, Ctrl+Shift+K clears the screen and scrollback, and Konsole keeps Ctrl+Alt+T
result: [pending]

### 6. Status-probe timing without FUSE (30 D-06)
expected: `ghostty --version` through extract-and-run finishes within the 5 s status-probe timeout on the owner's machine (about 49 MB to extract); measure and record the time
result: [pending]

### 7. Owner confirms the provisional decisions
expected: The owner accepts or redirects each of: 30 D-03 (macOS cask, no promised CLI link); 30 D-08 with the orchestrator decision (a user `command` in any default Ghostty file writes no shell region); 30 D-10 (config-file includes are not followed, a partial line is reported); 30 D-17 (the residue assertion covers installer-owned names); the SPEC R4 amendment following 28 D-06 (a recorded, deleted region stays deleted and quiet); the three narrowings of locked decisions (30 D-08, 30 D-17, 30 D-18); the accepted limits in 30-REVIEW-DISPOSITION.md (backlog 999.30)
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0
blocked: 0

## Gaps
