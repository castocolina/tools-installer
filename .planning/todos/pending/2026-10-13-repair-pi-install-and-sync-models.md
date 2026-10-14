---
created: 2026-10-13T23:30:00.000Z
title: Repair pi's install leftovers and ship the pi model/MCP sync
area: pi
severity: minor
source: ai-kit hand-off (2026-10-13 audit, reports 11 and 15)
files:
  - installer/host_setup.py
  - installer/skill_lifecycle.py
  - installer/postinstall.py (_AGENT_HOST_IDS lacks pi)
  - .planning/research/2026-10-13-from-ai-kit/11-pi-model-asset-sync.md
  - .planning/research/2026-10-13-from-ai-kit/pi-sync/pi_sync.py
---

## Problem

pi is now installed through bun (1.2.0), but its config still carries leftovers of the deleted
Volta install, and pi cannot see the providers and MCP servers the other hosts already have.

- 6 dangling symlinks point into the deleted Volta copy, so pi's subagent extension does not load:
  `~/.pi/agent/agents/{planner,reviewer,scout,worker}.md` and
  `~/.pi/agent/extensions/subagent/{index.ts,agents.ts}`. The same files exist under the bun
  install's `@earendil-works/pi-coding-agent/examples/extensions/subagent/`.
- `~/.pi/agent/skills` holds 33 symlinks duplicating `~/.agents/skills` (which pi reads
  natively), causing name-collision warnings.
- pi's MCP reads only `~/.pi/agent/mcp.json`; `postinstall.py` registers MCP for other hosts
  but not pi.
- User actions outside code: pi's Anthropic login expired (2026-07-26); `/login xai`.

## Solution

1. Re-point the 6 symlinks at the installed package (resolve its path, never hardcode it).
2. Delete `~/.pi/agent/skills` after confirming every entry duplicates `~/.agents/skills`.
3. Ship `pi-sync/pi_sync.py` (stdlib, dry-run by default, `--write` backs up to `*.bak`,
   idempotent, never copies key values; self-check `python3 -I test_pi_sync.py`) as a reviewed
   post-setup handoff: opencode Zen/Go models via an `apiKey` reference, opencode MCP servers
   converted to pi's `mcp.json`. router-env stays with llm-env.
4. Add pi to `_AGENT_HOST_IDS`.
