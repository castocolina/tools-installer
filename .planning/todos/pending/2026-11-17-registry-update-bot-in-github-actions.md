---
created: 2026-11-17T11:13:42.532Z
title: Registry update bot in GitHub Actions (catalog pins, Dependabot-like)
area: ci
severity: minor
files:
  - installer/verify_registry.py
  - .github/workflows/ci.yml
  - .github/workflows/
---

## Problem

Catalog pins in `installer/registry.toml` go stale until someone runs `make verify-registry ARGS="--write"` by hand. The weekly drift workflow only upserts a `registry-drift` issue. Dependabot cannot parse `registry.toml`, and Renovate cannot refresh the `sha256` that goes with each pin without self-hosted post-upgrade tasks, and has no datasource for Sublime. Owner request, 2026-11-17. Research: `.planning/research/2026-11-17-update-automation.md`, feature 3.

## Solution

A custom workflow around `verify-registry --write`, which already bumps `version`, `sha256` and `verified` together after verifying the candidate (only 5 methods are pinned: sublime and drawio-desktop). The bot pushes a branch and the change reaches `main` through the protected flow (branch -> green CI -> fast-forward, `enforce_admins` on).

- A push made with `GITHUB_TOKEN` starts no workflow. Use a PAT or App token, or add `workflow_dispatch` to `ci.yml` and dispatch it from the bot. Whether a dispatched run satisfies the required checks is unverified: test on a throwaway branch.
- `--write` re-dates every passing tool, so add a flag that skips date-only changes, or weekly PRs carry only `verified` dates.
- A `github-actions` `dependabot.yml` is a cheap extra for the workflow actions themselves.

Owner decisions: branch plus issue vs a real PR; PAT/App token vs dispatch; owner lands vs auto-land after green CI; date-only changes. Order: first of the three update-automation todos. Size: small to medium.
