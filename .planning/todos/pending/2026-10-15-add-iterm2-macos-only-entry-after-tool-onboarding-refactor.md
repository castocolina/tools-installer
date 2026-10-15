---
created: 2026-10-15T12:25:46.866Z
title: Add iTerm2 macOS-only entry after tool-onboarding refactor
area: catalog
severity: minor
files:
  - installer/registry.toml
  - installer/executors.py:518
  - docs/research/2026-10-09-alacritty.md
  - .claude/skills/tool-onboarding/SKILL.md
  - .planning/ROADMAP.md:323
---

## Problem

No macOS-first terminal in the catalog. The user wants iTerm2 with the
installer applying its settings at install time (zero manual GUI clicking),
and the work is blocked until the pending tool-onboarding skill revision lands
(Phase 999.5 "Finish the tool-onboarding skill revision with skill-judge",
ROADMAP.md:323; Phase 24.1 already exercises that skill's lifecycle params).

Entry requirements: macOS-only (`os = ["macos"]`), `kind = "cask"` (brew cask
`iterm2`; the `_cask` executor exists at installer/executors.py:518 and cask
methods have precedent in the registry), modeled on the alacritty terminal
entry (registry.toml:2668 — category "terminal", tier "user", audience human).

Two profile tweaks required for parity with the user's alacritty setup:

1. Alt/Option+arrows for word navigation — iTerm2 profile option-key-as-Esc+.
2. New tabs/windows inherit the opener's working directory — Profile >
   General > Working Directory = "Reuse previous session's directory".

## Solution

Add an `iterm2` tool entry (cask method, os-gated macOS) and apply both tweaks
programmatically via an iTerm2 **Dynamic Profile** written by a `post_install`
action (mechanism precedent: oh-my-zsh's `set_login_shell`): JSON file in
`~/Library/Application Support/iTerm2/DynamicProfiles/` with required `Guid`
(uuidgen) and `Name` fields. Per https://iterm2.com/documentation-dynamic-profiles.html
iTerm2 monitors that folder and reloads changes immediately — no restart, no
GUI interaction. Every profile preference iTerm2 supports may be a dynamic
profile attribute; confirm the exact attribute keys at implementation using
iTerm2's documented "Save Profile as JSON" procedure (expected values:
option-key-as-Esc+ ≈ "Option Key Send": 2; CWD reuse ≈ "Working Directory":
"Reuse"). Decide whether installer/tweaks.py or a new post_install verb owns
the JSON write.

BLOCKED-BY: Phase 999.5 tool-onboarding skill revision (user-directed
sequencing) — do not start this entry until that refactor lands.
