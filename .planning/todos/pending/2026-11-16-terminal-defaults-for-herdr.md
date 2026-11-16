---
created: 2026-11-16
title: Terminal defaults for herdr (multiplexer): check the word-navigation and clear keys pass through
area: catalog
severity: minor
files:
  - installer/terminal_shell.py
  - .claude/skills/tool-onboarding/SKILL.md
---

## Problem

herdr (the terminal multiplexer, not Herdr IDE) has its `default_shell` synced to zsh (`installer/terminal_shell.py`, `_sync_herdr`). It runs inside a host terminal, so it needs no keys of its own, but it must not swallow Option/Alt+Left/Right or the clear shortcut (Cmd+K / Ctrl+Shift+K). Not checked; if it intercepts them, add the pass-through to its owned settings.

Owner rule (2026-11-16): every terminal emulator launches zsh on Linux, moves by word with Option/Alt+Left/Right on macOS, and clears the screen with Cmd+K on macOS and Ctrl+Shift+K on Linux.

## Solution

Do it through the tool-onboarding skill (review mode) once backlog 999.18 has made these terminal defaults part of the skill; tracked under backlog 999.19. Install tuning only (a `post_install` action with an owned region, like Alacritty's `alacritty-keys` in `installer/terminal_shell.py:477-482`), stripped with the tool, never overriding a binding the user already defines.
