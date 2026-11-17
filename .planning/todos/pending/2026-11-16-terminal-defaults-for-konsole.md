---
created: 2026-11-16
title: Terminal defaults for Konsole: Ctrl+Shift+K clear-screen shortcut (owner decision)
area: catalog
resolves_phase: 29
severity: minor
files:
  - installer/terminal_shell.py
  - .claude/skills/tool-onboarding/SKILL.md
---

## Problem

Konsole is not a catalog entry, but the installer detects it and points its default profile at zsh (`installer/terminal_shell.py:359-407`); it is the Bazzite default terminal. No clear-screen binding is written. Owner decision first: does a detected, non-catalog terminal get the keys too? If yes, Ctrl+Shift+K clear through an owned Konsole keytab/shortcut entry.

Owner rule (2026-11-16): every terminal emulator launches zsh on Linux, moves by word with Option/Alt+Left/Right on macOS, and clears the screen with Cmd+K on macOS and Ctrl+Shift+K on Linux.

## Solution

Do it through the tool-onboarding skill (review mode) once backlog 999.18 has made these terminal defaults part of the skill; tracked under backlog 999.19. Install tuning only (a `post_install` action with an owned region, like Alacritty's `alacritty-keys` in `installer/terminal_shell.py:477-482`), stripped with the tool, never overriding a binding the user already defines.
