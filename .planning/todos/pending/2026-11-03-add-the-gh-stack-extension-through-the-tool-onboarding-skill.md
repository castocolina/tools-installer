---
created: 2026-11-03T14:30:00.000Z
title: Add the gh-stack extension through the tool-onboarding skill
area: catalog
severity: minor
files:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/registry.toml
---

## Problem

The user wants the installer to provide the GitHub CLI extension `github/gh-stack`,
installed with:

```
gh extension install github/gh-stack
```

`installer/registry.toml` already has a `gh` tool entry (id `gh`), but no way to
install a `gh` extension. Extensions live under the user's gh data directory
(`gh extension list`), so this is a user-scope install with no sudo.

## Solution

Onboard it through the tool-onboarding skill (research, install AND removal,
per OS/arch):

- Verify the extension's upstream repo, what it installs (a precompiled binary per
  OS/arch or a script), and its pinning options (`gh extension install --pin <tag>`).
- Decide the registry shape: a new method kind or a post-install step of `gh`,
  with `requires = ["gh"]`, and how a pinned version and drift check work.
- Detection: `gh extension list`; update: `gh extension upgrade gh-stack`;
  removal: `gh extension remove gh-stack`.
- gh must be authenticated for some extensions; check whether gh-stack needs it and
  hand off any login to the user (never run it).
- Tests in a scratch HOME (`GH_CONFIG_DIR` / XDG dirs), no real host install.
