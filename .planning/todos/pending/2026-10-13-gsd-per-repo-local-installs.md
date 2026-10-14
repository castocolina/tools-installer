---
created: 2026-10-13T23:30:00.000Z
title: Move GSD from a global install to per-repo local installs
area: gsd
severity: major
source: ai-kit hand-off (2026-10-13 audit, report 12)
files:
  - installer/registry.toml (id = "opengsd")
  - installer/skill_lifecycle.py (install-state probe)
  - .planning/research/2026-10-13-from-ai-kit/12-gsd-per-repo-install.md
---

## Problem

GSD should be installed per repo, not globally (user decision, 2026-10-13). Today the global
`~/.claude` install coexists with local installs in ai-kit and tools-installer, so global skills
shadow the local commands (W028), and 15 GSD hooks are registered both globally and in
`.claude/settings.local.json`, so every GSD hook fires twice inside those repos. tools-installer
owns GSD as a third-party pack, so it owns this migration.

The install-state probe (`installer/skill_lifecycle.py`) checks only
`$HOME/<runtime>/gsd-install-state.json`, which survives uninstall: it already reports false
"present" for opencode/codex/cursor, and after the migration it would report claude "absent"
while 6 repos have GSD.

## Solution

Full plan, rollback and risks: report 12 §3–§4.

1. Back up the global install and `~/.claude/settings.json`.
2. Install locally in the repos that lack it (gitid, home-mobility, kitty-setup, wezterm-setup),
   same pinned version: `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --local`; gitignore
   `.claude/gsd-core` where missing.
3. Global uninstall: `pnpm dlx @opengsd/gsd-core@1.16.0 --claude --global --uninstall`, then
   confirm no GSD hooks remain in `~/.claude/settings.json`.
4. Fix the probe to read `gsd-core/VERSION` or `gsd-file-manifest.json`, and enumerate
   project scope (repos with `.planning/config.json`).
5. Add an "update all local installs" loop over the official installer (never copy files).

ai-kit's side (resolving the project-local `gsd-tools.cjs` first) is tracked in ai-kit.
