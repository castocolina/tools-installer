---
created: 2026-10-15T21:00:21.537Z
title: Onboard Bruno API client via the tool-onboarding skill (nice to have)
area: catalog
severity: minor
files:
  - installer/registry.toml
  - .claude/skills/tool-onboarding/SKILL.md
---

## Problem

Bruno (usebruno/bruno — open-source, offline-first API client; collections
stored as plain files in git) is not in the catalog: no `bruno` entry in
installer/registry.toml, no ROADMAP backlog item, no todo (checked 2026-10-15).
The user wants it added — minor, nice to have (user, 2026-10-15).

## Solution

Run the tool-onboarding skill end to end (what it is, per-OS/arch artifacts,
install method ladder, uninstall per platform, tier, dependencies, postinstall
customizations). Starting facts to verify, not assume: macOS ships as the brew
cask `bruno`; Linux ships as GitHub release assets (AppImage / .deb / .rpm,
x86_64 and arm64 — confirm) plus snap/flatpak; a separate CLI `bru` exists as
the npm package `@usebruno/cli` (decide whether it is a second entry or out of
scope). Follow Phase 18 registry rules: `verified` date, `{ver}` pins with
sha256 where there is no release digest, smoke-able binary.

Sequencing (user, 2026-10-15): a todo, not a phase — onboard it after the
v0.50.0 autonomous run (phases 17-25) finishes, through the tool-onboarding
skill.
