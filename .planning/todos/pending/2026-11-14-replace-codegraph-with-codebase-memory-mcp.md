---
created: 2026-11-14T00:00:00.000Z
title: Replace codegraph with codebase-memory-mcp as the code-and-doc exploration tool
area: catalog
severity: major
files:
  - installer/registry.toml
  - installer/postinstall.py
  - installer/agent_settings.py
  - installer/uninstall.py
  - installer/versions.py
  - scripts/container-e2e-verify.sh
  - scripts/e2e-residue-allowlist.txt
  - .claude/skills/catalog-audit/SKILL.md
---

## Problem

The owner retired codegraph on the host on 2026-11-14 and adopted codebase-memory-mcp in its
place. The catalog still installs and wires codegraph. Recorded by request of the ai-kit session.
Capture only: do not implement until this todo is selected.

Facts from the owner's host on 2026-11-14:

- codegraph: the owner already removed its hooks and MCP entries. The binary is still at
  `~/.volta/tools/image/node/24.18.0/bin/codegraph`.
- codebase-memory-mcp 0.12.1 is a single static binary at `~/.local/bin/codebase-memory-mcp`.
  - It updates itself with `codebase-memory-mcp update`.
  - `codebase-memory-mcp install [--clients=<tokens>] [--dry-run]` wires 45 clients, among them
    claude, codex, opencode, cursor, copilot-cli, pi and gemini.
- What that installer writes:
  - A managed `<!-- codebase-memory-mcp:start/end -->` block into the opencode, pi and Copilot
    instruction files, and a one-line pointer into Codex's.
  - MCP entries into `~/.claude.json`, `opencode.jsonc`, `~/.cursor/mcp.json` and
    `~/.copilot/mcp-config.json`.
  - A pi extension (`~/.pi/agent/extensions/cbmem.ts`) and a pi skill.
  - Claude agents (codebase-memory, -scout, -auditor) and Claude hooks: PreToolUse
    Grep/Glob/Bash augmentation, PostToolUse Read coverage, SessionStart and SubagentStart.
- Index store and config:
  - One index per repo root, at `~/.cache/codebase-memory-mcp/<project>.db`. Nothing goes into the
    repo unless persistence is asked for.
  - `codebase-memory-mcp config list` shows `auto_watch` true and `auto_index` false.
- Measured on the ai-kit repo:

  | | Files | Nodes | Edges | Scope |
  |---|---|---|---|---|
  | codebase-memory-mcp | 2,756 | 56,621 | 169,920 | Code plus Markdown sections; full index in 4.2 s |
  | codegraph | 473 | 24,222 | 66,776 | Code only, no docs |

  codebase-memory-mcp also records these edge types: doc-to-code MENTIONS (20k resolved),
  REFERENCES_FILE, TESTS, FILE_CHANGES_WITH (git co-change), WRITES and SPAWNS.
- How agents query it:
  - `search_graph` returns code symbols and doc sections together.
  - `trace_path` gives callers and callees, tests included, in one call.
  - `query_graph` takes a subset of Cypher; `labels()` is not supported.
  - Agents without MCP use `codebase-memory-mcp cli <tool> '<json args>'`.
- Noise: planning and history docs flood search results. A per-repo `.cbmignore` that keeps
  `.planning/` out is worth recommending for GSD repos.
- About 27k doc mentions stay unresolved. They are ambiguous names (main, refresh) plus 4.3k names
  that no longer exist in the code, so the unresolved set doubles as a stale-doc detector.

## Solution

### 1. Remove codegraph from the catalog

Remove these:

- The npm/volta entry.
- Its MCP server registration (`_CODEGRAPH_TARGETS` in `installer/postinstall.py`).
- Its UserPromptSubmit hook.
- The CODEGRAPH_START/CODEGRAPH_END instruction blocks.
- The `recommends = ["codegraph", ...]` rows.
- The landing and e2e fixtures.

Removal of an existing install must still clean up:

- The binary and receipt.
- The hook, MCP entries and instruction blocks.
- `~/.codegraph`.

Per-repo `.codegraph/` directories are user data in their repos. The removal hands off the exact
`rm -rf` command and never sweeps the disk for them.

### 2. Add codebase-memory-mcp

Onboard it through `.claude/skills/tool-onboarding/SKILL.md`:

- Method: download the upstream static binary into `~/.local/bin`, pinned and checksummed like the
  other binary entries.
- Update route: `codebase-memory-mcp update`, or the installer's own pin bump. Decide which one owns
  updates so they never fight.

Client wiring:

- Call its own `install --clients=<detected harnesses>` rather than writing its blocks, MCP entries,
  agents and hooks ourselves.
- Record what it wrote in the receipt so uninstall can reverse it. Check whether it has an
  `uninstall` subcommand, and use that if it does.
- Probe `--dry-run` in a container first. It writes Claude hooks and agents, so decide whether they
  fall under install tuning (applied at install, no question) or need an opt-out.
- Map the installer's harness keys to its `--clients` tokens; copilot is `copilot-cli`.

Ship a `.cbmignore` recommendation (`.planning/`) for GSD repos, as guidance rather than a written
file.

### 3. User instruction files

- `~/.claude/CLAUDE.md`: may not exist; create it, or fall back to the shared pointer.
- Global AGENTS-style files:
  - opencode: `~/.config/opencode/AGENTS.md`
  - pi: `~/.pi/agent/AGENTS.md`
  - Copilot CLI: `~/.copilot/copilot-instructions.md`
  - Codex: `~/.codex/AGENTS.md`, which already reads the `~/.agents/AGENTS-TOOLING.md` pointer.
- Cursor has no global instruction file. codebase-memory-mcp's own install gives Cursor a skill and
  agents instead.

codebase-memory-mcp already writes its block into the opencode, pi and Copilot files and a pointer
into Codex's. This repo owns only the shared `~/.agents/AGENTS-TOOLING.md` text and the CLAUDE.md
pointer, never a second copy of its block.

### 4. The shared `~/.agents/AGENTS-TOOLING.md` block

On 2026-11-14 the owner replaced the block's "CodeGraph protocol" section by hand with a
"codebase-memory-mcp protocol" section, inside the `tools-installer shared agent tooling` markers.

Verified 2026-11-14: no code in this repo writes that block any more. Commit 0b8264f8 (23-06)
deleted its writer (`agent_guidance.py` / `agent_policy.py`, `_GUIDANCE_BEGIN`/`_GUIDANCE_END`) as
a dead chain. A re-run will not restore the old text today.

Decide one of these:

- (a) Revive a single writer for the block with the codebase-memory-mcp protocol text. Take the
  owner's hand-written section verbatim as the template, plus the shared pointer lines that
  `~/.claude/CLAUDE.md` already carries.
- (b) Declare the block user-owned and drop the markers from the docs and PRDs
  (`docs/prds/agent-first-catalog-and-unified-ui-v1.0-prd.md` §"Agent tooling policy and
  CodeGraph guidance").

Either way, update that PRD section, which still describes the CodeGraph protocol.

### 5. Docs and skills

- Repo docs and AGENTS-adjacent guidance that tell agents to reach for codegraph first.
- The catalog-audit skill's examples and evals that name codegraph.

Verify everything in a disposable container (install, wiring, removal residue) before any real-host
UAT.
