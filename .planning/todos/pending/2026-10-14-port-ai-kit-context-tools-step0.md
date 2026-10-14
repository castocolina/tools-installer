---
created: 2026-10-14T20:00:00.000Z
title: Port what is useful from ai-kit's shelved "context tools" wizard Step 0
area: catalog
severity: minor
source: ai-kit hand-off (2026-10-14; tag archive/context-tools-plan1 = 27d355f in the ai-kit repo)
files:
  - installer/registry.toml
  - installer/catalog_tui.py
---

## Problem

ai-kit's shelved branch, now tag `archive/context-tools-plan1` (21 commits, 2026-07-28..30, ~4,900
lines) added a setup-wizard "Step 0" that detects, installs, configures and uninstalls AI
context tools: rtk, codegraph, graphify and gitnexus. On 2026-10-14 uz decided it does not land
in ai-kit: third-party installs belong to tools-installer (scope decision of 2026-10-13). This
todo keeps the useful parts from being lost.

tools-installer already catalogs codegraph, graphify and rtk (`installer/registry.toml`), so
most of the branch is already covered. Compare, then port only the gaps:

- **gitnexus**: not in the registry.
- **Per-agent-environment configure templates**: the branch's catalog
  (`tools/context_tools_inventory.toml`) carries `configure_scoped` with `{env}` (one call per
  env) or `{envs}` (one comma-joined call) plus an ordered `envs` list.
- **Uninstall commands** per tool, e.g. `codegraph uninstall --yes && pnpm remove -g
  @colbymchenry/codegraph`, and `tools/context_tools_scripts/rtk.sh`.
- **Non-interactive gotchas** found live: `codegraph install` without `--yes` opens its own
  checkbox TUI that reads raw stdin and hangs any parent TUI; `--target=auto` wires only
  agents already detected, so the branch pinned `--target claude,codex,opencode,antigravity`
  (codegraph has no vscode target).
- **UI idea**: a 4-state per-tool toggle (install+configure / reconfigure / remove / skip) with
  a worker queue, a re-entrancy guard, a scrollable full log, and failed actions surfaced.

## Solution

Read the tag from the ai-kit checkout (`git show
archive/context-tools-plan1:tools/context_tools.py`,
`:tools/context_tools_inventory.toml`, `:tools/context_tools_scripts/rtk.sh`, and the plan docs
`docs/superpowers/plans/2026-07-28-context-tools-manager-plan2-wizard.md` and
`2026-07-30-context-tools-step0-toggle-redesign-plan.md`). Diff each tool against its
`registry.toml` entry, re-verify every command against the currently installed tool versions,
and add only what is missing. Do not copy the ai-kit wizard code; it was written against
ai-kit's `setup.py`/`wizard_app.py` seams.
