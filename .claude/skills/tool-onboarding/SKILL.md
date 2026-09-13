---
name: tool-onboarding
description: Use when adding a new tool to installer/registry.toml — deciding its tier, dependency declarations, or whether it needs a postinstall hook, skill_pack, or host_setup mechanism for tools-installer's catalog — or when reviewing an existing registry.toml entry against those same conventions.
---

# Tool onboarding

## Overview

Walks a `registry.toml` addition through the same tier/dependency/postinstall
checklist `.claude/architecture.md`'s "Tool onboarding: tier, dependencies,
and postinstall classification" subsection documents, plus a platform-coverage
check, so a new entry's tier, dependency edges, postinstall wiring, and OS/arch
coverage all get decided deliberately instead of guessed. This is the
checklist that would have caught `rtk`/`graphify`'s postinstall gap
(researched in Phase 8, never wired until Phase 12.4) and the
`vscode`/`jetbrains-toolbox`/`sublime` Linux-blind gap, both before they sat
unnoticed for phases.

This is a PROCESS aid, not a code generator: it does not write
`installer/*.py` changes itself. If step 4 below routes the tool to a
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

Steps 3 and 4 below are judgment calls with no lint enforcement — when a
tool doesn't cleanly fit, say so explicitly in the `# Verified` comment
rather than picking silently. That comment is this checklist's only audit
trail; a future reviewer (human or agent) has nothing else to go on.

## Steps

### 1. Research the tool

Confirm, per OS/arch the entry will declare: does it need a
checksum-verifiable release asset, or does it install via a
script/package manager? Same bar as `.claude/architecture.md`'s "Per-tool,
per-OS verification checklist".

### 2. Check every platform the vendor supports

Before writing any method, check the vendor's own docs for EVERY platform it
officially ships for — macOS, and Linux per-distro/per-arch (amd64 and arm64
separately) — not only the platform you're currently working from. `vscode`,
`jetbrains-toolbox`, and `sublime` shipped Linux-blind for a while because
their entries were authored and verified from a macOS session and nobody
checked whether a Linux path existed — it did, for all three (official
tarball/apt/rpm distributions). Declare a method for each platform that's
genuinely feasible to support; if one is knowingly left out (no confirmed
vendor URL, no stable arm64 build, etc.), say so in the `# Verified` comment
rather than silently omitting it.

### 3. Decide tier

Apply `.claude/architecture.md`'s "Tier is a browsing label" definitions:

- **`system`** — a prerequisite other tools may depend on regardless of
  personal preference (uv/pnpm/brew/sdkman/zsh/podman-shaped).
- **`user`** — a tool the human runs and drives directly: a personal-choice
  dev tool (terminal emulators, CLI utilities, editors) **or an AI agent
  harness/CLI** (claude, codex, opencode, cursor-agent, antigravity, pi,
  aichat). Being AI-branded does not by itself make something `ai`-tier —
  what matters is whether the human is the one typing into it.
- **`ai`** — tooling that operates underneath or is consumed BY an agent
  session, never launched directly by the human as their own interface: MCP
  servers, token-reduction proxies, knowledge-graph builders, agent-oriented
  CLI utilities (rg, fd, sd, bat, eza), or an agent-ecosystem skill pack.

`Tool.audience` (`human`/`ai`/`both`) is a separate, independent field for
who *benefits* from a tool — it doesn't drive tier and tier doesn't drive it.

### 4. Decide dependencies and postinstall mechanism

**REQUIRED READING:** `.claude/architecture.md`'s "Tool onboarding: tier,
dependencies, and postinstall classification" subsection has the full,
canonical decision tree — read it now rather than reconstructing it here,
so there is exactly one copy and this skill can't silently drift from it.

In short: if the tool installs via a manager (`pnpm add -g`, `uv tool
install`, an SDKMAN candidate), its `requires` must name that manager tool
so `installer/deps.py::resolve_dependencies` drags it in automatically. A
dependency doesn't have to be a manager to count — a tool that merely
expects another binary on `PATH` at runtime (not at install time) still
needs a `requires` edge if the catalog can't otherwise guarantee that binary
is present; when genuinely unsure whether a soft runtime expectation rises
to a `requires` edge, say so in the `# Verified` comment rather than
guessing either way. Then walk the three-mechanism postinstall tree in that
architecture.md subsection — `Tool.postinstall` hook / `skill_pack` +
`skill_lifecycle` / `host_setup` / none — to decide what, if anything, the
entry needs beyond a plain binary install. If a tool's needs straddle two
branches of that tree, don't force a single answer — name the ambiguity in
the `# Verified` comment and flag it for review.

If the answer is a `postinstall` hook: the registry can only select a hook
**name** from `installer/postinstall.py`'s closed `POSTINSTALL_HOOKS` table
— never a literal command string — and the hook must detect and configure,
never blind-overwrite, existing host configuration (gate on
`present_agent_hosts()`, verify merge-safety against pre-existing config
before shipping, exactly as `rtk`/`graphify`'s Phase 12.4 wiring did).

### 5. Write the registry.toml entry

A `[[tool]]` block with `id`, `name`, `category`, `cmd`, `priority`,
`audience`, `tier`, `desc`, `requires`, and optionally `postinstall`, plus
one or more `[[tool.method]]` blocks matching the tool's real install
path(s) confirmed in steps 1-2. Add a dated `# Verified {date}: ...` comment
directly above the `[[tool]]` block recording what was checked — the
existing, mandatory recording mechanism `.claude/architecture.md`'s
verification checklist already requires for every new entry.

## Common Mistakes

- **Only declaring methods for the platform you're working from.** Checking
  install docs from a macOS session and never checking Linux (or vice versa)
  is how `vscode`/`jetbrains-toolbox`/`sublime` ended up greyed-out on Linux
  despite all three vendors shipping official Linux builds. Check every
  platform the vendor supports (step 2), every time.
- **Classifying an AI agent CLI as `ai`-tier just because it's AI-branded.**
  `claude`, `codex`, `opencode`, `cursor-agent`, `antigravity`, `pi`, and
  `aichat` are `user`-tier: the human launches and drives them directly, the
  same relationship as any other personal-choice tool. `ai`-tier is for
  tooling consumed BY an agent session, not tooling that IS an agent host.
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
