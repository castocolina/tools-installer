# Context (batch 5: update automation)

## Update automation: shared research
- source: .planning/research/2026-11-17-update-automation.md
- Three features: daily check + desktop notification, opt-in managers-first auto-update, registry update bot.
- Research order was 3, 1, 2 (bot, daily, auto), which matches the owner's phase order 33, 34, 35.
- Dependencies: feature 2 reuses feature 1's notify helper and outdated list; the bot is independent (CI only).
- Each lands as its own phase via branch, green CI, fast-forward. Features 1 and 2 need one real macOS check before done; macOS has never run locally.
- Dependabot cannot read registry.toml; Renovate regex cannot refresh sha256 alongside version on the hosted app and does not run asset/member/digest verification. Custom workflow recommended; a 6-line `github-actions` dependabot.yml is a cheap side win.
- Unverified per research: whether a `workflow_dispatch` CI run satisfies the required `validate & test on ...` checks on the branch head; macOS osascript behavior from a launchd agent; uv ecosystem support in Dependabot; `uv self update` under `uv run`.

## Registry update bot (phase 33)
- source: .planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md
- Events from `GITHUB_TOKEN` start no workflow (except dispatch), so a pushed bot branch gets no `ci.yml` run unless a PAT/App token is used or `ci.yml` gains `workflow_dispatch`.
- `--write` re-dates every passing tool, so date-only noise needs a flag.
- Size: small to medium. Open questions (owner, not locked):
  - OQ-BOT-1: branch plus issue vs a real PR
  - OQ-BOT-2: PAT/App token vs `workflow_dispatch` on `ci.yml`
  - OQ-BOT-3: owner lands (recommended) vs auto-land after green CI
  - OQ-BOT-4: date-only `verified` changes ignored vs batched monthly
  - OQ-BOT-5: add the `github-actions` dependabot.yml now (recommended)

## Daily update check with notification (phase 34)
- source: .planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md
- Version cache TTL 7 days (version_cache.py:45); unit has no GitHub token (daemon.py:34-45), so anonymous 60 req/h; a refresh fetches at most 20 (version_status.py:143).
- Linux host has notify-send (libnotify 0.8.9); macOS osascript needs a one-time Script Editor permission.
- Size: medium. Open questions (owner, not locked):
  - OQ-NOTIFY-1: reverse the 24.2 notification cut for this check only, or for failed runs too
  - OQ-NOTIFY-2: notify every run or only on change (recommended)
  - OQ-NOTIFY-3: token in the unit vs `gh auth token` vs anonymous
  - OQ-NOTIFY-4: include the installer self-check (recommended)
  - OQ-NOTIFY-5: click action (not recommended for v1)

## Opt-in auto-update (phase 35)
- source: .planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md
- `requires` alone cannot express manager-first ordering (11 tool-level lines, none for brew). Size: large; the research suggests splitting managers-only then dependents.
- Open questions (owner, not locked):
  - OQ-AUTOUPD-1: off by default, opt-in per host (recommended)
  - OQ-AUTOUPD-2: managers only first vs both at once
  - OQ-AUTOUPD-3: fold the five per-tool rows into `update-all` vs keep both and skip duplicates
  - OQ-AUTOUPD-4: macOS casks excluded (recommended), allow-listed or included
  - OQ-AUTOUPD-5: notify after an auto-update run (reuses the phase 34 helper)
  - OQ-AUTOUPD-6: dry-run `--run-schedule update-all --plan`
