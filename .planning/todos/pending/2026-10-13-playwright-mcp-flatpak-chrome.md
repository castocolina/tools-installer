---
created: 2026-10-13T23:30:00.000Z
title: Point Playwright MCP at the Flatpak Chrome (shell tweak + Cursor MCP env)
area: tweaks
severity: minor
source: ai-kit hand-off (2026-10-13 audit, report 16)
files:
  - .planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md
---

## Problem

`@playwright/mcp` defaults to `/opt/google/chrome/chrome`, but on Bazzite Chrome exists only as
a Flatpak, so the Playwright MCP fails for Claude, its subagents and cursor-agent. Tested fix:
`PLAYWRIGHT_MCP_EXECUTABLE_PATH=/var/lib/flatpak/exports/bin/com.google.Chrome` (a throwaway
`claude -p` run reached "Example Domain").

## Solution

1. Add a `tweak:playwright-mcp` block to the managed shell rc that exports the variable only
   when the Flatpak wrapper exists. Claude and its MCP servers inherit it when launched from a
   shell.
2. cursor-agent starts its MCP servers with a stripped environment (8 variables), so also set
   the variable in the Playwright entry's `env` in Cursor's MCP config.
3. Optional, for launches outside a shell: `env` in `~/.claude/settings.json` (needs the
   user's consent; it is a Claude config write).
