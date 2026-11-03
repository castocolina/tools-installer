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

Required customizations (1–2 for parity with the user's alacritty setup, 3 a look-and-feel request, 4–5 added 2026-10-21):

1. Alt/Option+arrows for word navigation — iTerm2 profile option-key-as-Esc+.
2. New tabs/windows inherit the opener's working directory — Profile >
   General > Working Directory = "Reuse previous session's directory".
3. Color scheme (added 2026-10-15): dark background with dark-green text,
   a "Matrix console" look. Requirement only; the how is open (e.g. a
   built-in dark theme/preset vs explicit color keys in the same Dynamic
   Profile) — decide at implementation.
4. Install or enable the item the user described as **"Show Focus Cursor"**.
   Identify the exact feature/project and verify whether it is a native iTerm2
   setting, shell integration, or an installable companion; the name and
   installation mechanism are not confirmed yet.
5. Install the agent collaboration extension the user described: agents can
   communicate with other agents and share information/context, while the
   integration displays agent information, diffs, chat, and code review. The
   exact extension/project name is not yet known; identify it and verify these
   capabilities rather than guessing a product or claiming support in advance.

The user explicitly reconfirmed **minor** severity for this expanded scope on
2026-10-21. Extend this existing todo; do not create a duplicate iTerm2 entry.

## Solution

Add an `iterm2` tool entry (cask method, os-gated macOS) and apply the three
established profile tweaks programmatically via an iTerm2 **Dynamic Profile**
written by a `post_install`
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

Use the tool-onboarding skill's companion-integration/customization checks for
the focus-cursor feature and agent collaboration extension. Research their
exact names, upstream installation instructions, macOS/iTerm2 compatibility,
supported agents, dependencies, permissions, and removal paths. If the focus
feature is native, enable it through the documented mechanism instead of
inventing a plugin dependency. Do not assume an extension can be installed
through a Dynamic Profile or that a terminal extension supports every agent.

Treat each additional integration as an idempotent, reversible step, preserving
user settings and wiring only supported, present agent hosts. Confirm uncertain
product identities before implementing them; capture alone does not authorize
installing unknown extensions or editing real agent settings. Keep the original
three profile requirements and the existing sequencing dependency intact.

BLOCKED-BY: Phase 999.5 tool-onboarding skill revision (user-directed
sequencing) — do not start this entry until that refactor lands.
