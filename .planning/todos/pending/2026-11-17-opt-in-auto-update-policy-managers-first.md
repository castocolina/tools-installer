---
created: 2026-11-17T11:13:42.532Z
title: Opt-in auto-update schedule: package managers first, then dependents
area: schedules
severity: minor
resolves_phase: 35
files:
  - installer/update.py
  - installer/resolve.py
  - installer/deps.py
  - installer/schedules.py
  - installer/run.py:50,117,338
---

## Problem

Updates run only when the user presses `u` or through the five per-tool agent-CLI schedules. The owner wants an opt-in policy that updates the package managers first (brew, sdkman, bun, volta, pnpm, uv, ...) and then the tools that depend on them. Owner request, 2026-11-17. Research: `.planning/research/2026-11-17-update-automation.md`, feature 2.

## Solution

An opt-in `update-all` Schedules row, off by default. It is not a Policies row: install-time tuning and Schedules carry this kind of behavior (PROJECT.md doctrine). 24.2 R3 seeds every schedule on, so the row needs a per-schedule `default_on=False`.

- Ordering: managers first, ranked by `resolve._RANK`; then dependents grouped by owner, ordered inside each group by `deps.resolve_dependencies`. A failed manager skips its dependents. `requires` alone cannot express this: only 11 tool-level lines, none for brew.
- Safety that exists: `UpdateService`, `update_refusal` (native owners, SDKMAN, Volta, pins, os-package), children with `stdin=DEVNULL` (`run.py:117,338`), `HOMEBREW_NO_SUDO` (`run.py:50`), the run lock.
- Still needed: brew casks excluded on macOS by default, a multi-line run log (the shared log is one line per id), and a rule so the five per-tool rows do not update a tool twice.
- Unverified: whether `uv self update` is safe while the runner runs under `uv run`.

Owner decisions: off by default; managers only first vs both; fold the per-tool rows into it; casks policy. Order: third; it reuses the notify helper and the outdated list from the daily check. Size: large.
