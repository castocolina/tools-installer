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
- **GitHub Enterprise default host (user, 2026-11-03):** when the user's `gh` is
  logged in to, or defaults to, a GHE server, a bare `owner/repo` resolves against
  that host and the install can fail. Install with the full URL so it always
  targets github.com:
  `gh extension install https://github.com/github/gh-stack`.
- Detection: `gh extension list` (check the listed repo/host is github.com).
  Update: `gh extension upgrade stack`, the extension's own name without the
  `gh-` prefix. Removal: `gh extension remove stack`.
- Research whether `upgrade` and `remove` can or should take the host too, and how
  they behave on a GHE-default `gh`: is the install origin stored with the
  extension so `upgrade` goes back to github.com on its own, or does it need
  `GH_HOST=github.com` or a full URL? Verify on a scratch `GH_CONFIG_DIR` set to a
  GHE default host before choosing the argv.
- gh must be authenticated for some extensions; check whether gh-stack needs it and
  hand off any login to the user (never run it).
- Tests in a scratch HOME (`GH_CONFIG_DIR` / XDG dirs), no real host install.
