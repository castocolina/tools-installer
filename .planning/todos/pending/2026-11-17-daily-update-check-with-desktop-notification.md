---
created: 2026-11-17T11:13:42.532Z
title: Daily update check with a desktop notification (Bazzite and macOS)
area: schedules
severity: minor
resolves_phase: 34
files:
  - installer/schedules.py
  - installer/compose.py:411
  - installer/version_cache.py:44
  - installer/version_status.py:143
  - installer/daemon.py:34-45
---

## Problem

Nothing tells the user that installed tools have updates unless they open the TUI. The owner wants a daily check that leaves a desktop notification on Bazzite and macOS, covering the catalog tools and tools-installer itself. Phase 24.2 deliberately left notifications out (`24.2-SPEC.md:179`), so this reverses that cut. Owner request, 2026-11-17. Research: `.planning/research/2026-11-17-update-automation.md`, feature 1.

## Solution

A daily `check-updates` row in the Schedules engine (24.2 D-10..D-14). It runs `VersionRefreshService.refresh` headless through `--run-schedule`, and logs one `ok: N updates available` line. The stdlib runner notifies only when the outdated set changed: `notify-send` on Linux, `osascript` on macOS.

- The version cache TTL is 7 days (`version_cache.py:44`); the scheduled pass needs a forced refresh or a shorter TTL.
- The unit has no GitHub token (`daemon.py:34-45`), so it is anonymous (60 requests/h), and a refresh fetches at most 20 per run (`version_status.py:143`).
- Linux: this Kinoite host has `notify-send` (libnotify 0.8.9) and the user manager exports `DBUS_SESSION_BUS_ADDRESS`; the runner's clean child env must pass the bus address through.
- macOS: `osascript display notification` needs a one-time Script Editor permission; behavior from a launchd agent is unverified.
- tools-installer itself: compare `git ls-remote origin main` with the checkout HEAD (no API call, no auto-pull).

Owner decisions: reverse the 24.2 cut; notify on every run or only on change; token in the unit vs `gh auth token` vs anonymous; include the installer self-check. Order: second, after the registry bot. Size: medium.
