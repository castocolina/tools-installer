---
created: 2026-11-04T09:30:00.000Z
title: Hand off casks whose uninstall needs root instead of running brew uninstall --cask
area: lifecycle
severity: medium
files:
  - installer/uninstall.py
  - installer/app.py
  - installer/manager_versions.py
---

## Problem

Phase 22 security residual C-10 (22-SECURITY.md, 22-REVIEW-FIX.md): the installer never starts `sudo`, child processes get
no terminal (a password prompt fails closed) and every brew child runs with `HOMEBREW_NO_SUDO=1`, but a cask whose
`uninstall` stanza needs root (`pkgutil`, `launchctl` system jobs, `delete` outside the user's dirs) can still elevate
through the user's own NOPASSWD sudo when L1 removal runs `brew uninstall --cask <app>`. Zero sudo (AGENTS.md) should hold
even on such hosts.

## Solution

Read the cask's uninstall stanza (`brew info --json=v2 --cask <token>`, `artifacts` → `uninstall` / `pkg`) in the
refresh pass. When it needs root, the removal level becomes a manual handoff that names the exact `brew uninstall --cask`
command for the user, with zero runner calls. Fixture-driven tests with macOS-shaped JSON; one real macOS check.
