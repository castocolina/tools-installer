---
name: tool-onboarding
description: Use when adding a new tool to installer/registry.toml — deciding its tier, dependency declarations, or whether it needs a postinstall hook, skill_pack, or host_setup mechanism for tools-installer's catalog.
---

# Tool onboarding

## Overview

Walks a `registry.toml` addition through the same three-question checklist
`.claude/architecture.md`'s "Tool onboarding: tier, dependencies, and
postinstall classification" subsection documents, so a new entry's tier,
dependency edges, and postinstall wiring get decided deliberately instead of
guessed. This is the checklist that would have caught `rtk`/`graphify`'s
postinstall gap — researched in Phase 8, never wired until Phase 12.4 — before
it sat unnoticed across three phases.

This is a PROCESS aid, not a code generator: it does not write
`installer/*.py` changes itself. If step 3 below routes the tool to a
`postinstall` hook, implementing that hook still follows the existing
`installer/postinstall.py` `POSTINSTALL_HOOKS` / `installer/model.py`
`POSTINSTALL_HOOK_NAMES` wiring pattern — `codegraph`, `rtk`, and `graphify`
are the worked examples.

## When to Use

- Adding any new `[[tool]]` block to `installer/registry.toml`.
- Deciding whether an existing tool needs a postinstall follow-up you're
  only now noticing (the exact situation `rtk`/`graphify` were in).
- Reviewing someone else's new registry entry and checking it against this
  project's own conventions.

## Steps

### 1. Research the tool

Read the tool's actual install documentation or package metadata directly —
never a marketing page or a plausible-sounding guess. Confirm, per OS/arch
the entry will declare: does it need a checksum-verifiable release asset, or
does it install via a script/package manager? This is the same bar
`.claude/architecture.md`'s "Per-tool, per-OS verification checklist"
already holds every entry to.

### 2. Decide tier

Apply `.claude/architecture.md`'s "Tier is a browsing label" definitions:

- **`system`** — a prerequisite other tools may depend on regardless of
  personal preference (uv/pnpm/brew/sdkman/zsh/podman-shaped).
- **`user`** — a personal-choice dev tool with no agent-host relationship
  (terminal emulators, CLI utilities, editors).
- **`ai`** — agent-facing tooling: an agent host itself, a tool an agent
  host consumes (MCP servers, token-reduction proxies, knowledge-graph
  builders), or an agent-ecosystem skill pack.

Not automated — no lint enforces tier correctness; this is a judgment call.

### 3. Decide dependencies and postinstall mechanism

**REQUIRED READING:** `.claude/architecture.md`'s "Tool onboarding: tier,
dependencies, and postinstall classification" subsection has the full,
canonical decision tree — read it now rather than reconstructing it here,
so there is exactly one copy and this skill can't silently drift from it.

In short: if the tool installs via a manager (`pnpm add -g`, `uv tool
install`, an SDKMAN candidate), its `requires` must name that manager tool
so `installer/deps.py::resolve_dependencies` drags it in automatically. Then
walk the three-mechanism postinstall tree in that architecture.md
subsection — `Tool.postinstall` hook / `skill_pack` + `skill_lifecycle` /
`host_setup` / none — to decide what, if anything, the entry needs beyond a
plain binary install.

If the answer is a `postinstall` hook: the registry can only select a hook
**name** from `installer/postinstall.py`'s closed `POSTINSTALL_HOOKS` table
— never a literal command string — and the hook must detect and configure,
never blind-overwrite, existing host configuration (gate on
`present_agent_hosts()`, verify merge-safety against pre-existing config
before shipping, exactly as `rtk`/`graphify`'s Phase 12.4 wiring did).

### 4. Write the registry.toml entry

A `[[tool]]` block with `id`, `name`, `category`, `cmd`, `priority`,
`audience`, `tier`, `desc`, `requires`, and optionally `postinstall`, plus
one or more `[[tool.method]]` blocks matching the tool's real install
path(s) confirmed in step 1. Add a dated `# Verified {date}: ...` comment
directly above the `[[tool]]` block recording what was checked — the
existing, mandatory recording mechanism `.claude/architecture.md`'s
verification checklist already requires for every new entry.

## Common Mistakes

- **Guessing a tier instead of applying the three definitions.** If it's
  genuinely ambiguous, say so in the `# Verified` comment rather than
  picking silently.
- **Skipping a dependency edge because "the user probably has it already."**
  An undeclared real dependency silently relies on the user having installed
  the prerequisite through some other path — always name it in `requires`.
- **Shipping a postinstall hook that writes to every host presence
  unconditionally, or that passes an "auto"-style flag.** Both are the exact
  failure mode Phase 9's `codegraph` research found and this project's
  `present_agent_hosts()` gate exists to prevent.
- **Re-deriving the postinstall decision tree from scratch instead of
  reading `.claude/architecture.md`'s canonical copy.** This skill
  deliberately doesn't repeat the full tree inline — read the source of
  truth.
