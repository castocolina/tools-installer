---
created: 2026-11-16
title: Terminal defaults for WezTerm: clear-screen shortcut and macOS Option word navigation
area: catalog
resolves_phase: 29
severity: minor
files:
  - installer/terminal_shell.py
  - .claude/skills/tool-onboarding/SKILL.md
---

## Problem

WezTerm gets only the zsh terminal sync on Linux (`installer/terminal_shell.py:180-208`, `:969-989`); the installer writes no key bindings on any OS. Missing: Ctrl+Shift+K clear on Linux, Cmd+K clear on macOS, Option+Left/Right word navigation on macOS. WezTerm's own defaults were not verified; write the bindings in the owned Lua region so the result does not depend on them.

Owner rule (2026-11-16): every terminal emulator launches zsh on Linux, moves by word with Option/Alt+Left/Right on macOS, and clears the screen with Cmd+K on macOS and Ctrl+Shift+K on Linux.

## Solution

Do it through the tool-onboarding skill (review mode) once backlog 999.18 has made these terminal defaults part of the skill; tracked under backlog 999.19. Install tuning only (a `post_install` action with an owned region, like Alacritty's `alacritty-keys` in `installer/terminal_shell.py:477-482`), stripped with the tool, never overriding a binding the user already defines.
