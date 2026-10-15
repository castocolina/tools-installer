---
name: tool-onboarding
description: Use when adding a new tool to installer/registry.toml, or reviewing an existing entry — researching what the tool is (OS tool, user app, LLM plugin/skill/agent pack), how and for which OS/arch it ships, which install method fits (brew, vendor script, package manager, per-platform artifact, marketplace vs symlink), how it is uninstalled per platform (vendor uninstaller, files it wrote, keep-config vs delete-all policy), its tier, dependencies, and whether it needs a postinstall hook or user-chosen customizations (terminal keybindings, shell integration, companion plugins).
---

# Tool onboarding

## Overview

A PROCESS aid for adding or reviewing one `[[tool]]` block. It does not write
`installer/*.py`; if the answer is a `postinstall` hook, follow the existing
`installer/postinstall.py` `POSTINSTALL_HOOKS` / `installer/model.py`
`POSTINSTALL_HOOK_NAMES` wiring.

Tool names below are **examples of a shape**, never instructions. Past misses
that motivate each step: a tool authored from macOS only and Linux-blind for
phases; a postinstall gap nobody noticed; a vendor installer script treated as
"the package manager did it". Decide from evidence about THIS tool, not from
the examples.

**The skill cannot promise what the platform does not do.** Every decision
below must land on a mechanism that exists in code today (a method kind, a
param, a hook name, a classifier). Name the file that implements it. If the
right answer needs a capability the registry, model or installer lacks — per-
OS/arch artifacts a method kind cannot express, a removal path for a script
install, a customization with no hook — do not approximate it in the entry.
Record it as a platform gap in the GSD backlog and say so in `# Verified`. A
checklist that "covers" a case the platform silently mishandles is worse than
no checklist.

Judgment calls with no lint enforcement go in a dated `# Verified {date}: ...`
comment above the `[[tool]]` block. It is the only audit trail.

## When to Use

- Adding any `[[tool]]` block; reviewing one against these conventions.
- Noticing an existing tool lacks a postinstall, a platform, or a removal path.

## Steps

### 1. Research first — never write from memory

When ANY of the following is uncertain, do online research (vendor docs,
release page, README, package-manager listings) BEFORE choosing anything, and
cite what you found in the `# Verified` comment: what the tool is, supported
OSes/arches, how the vendor says to install and uninstall it, whether a
marketplace/registry listing exists. If research is thin or contradictory, say
so rather than guessing. Spawn a research agent when the question is open-ended.

### 2. Classify what kind of thing it is

Answer all of these; they drive every later step.

| Question | Why it matters |
|---|---|
| OS/CLI tool, user-facing app, or LLM tooling? | tier + audience (step 5) |
| LLM tooling: plugin, skill, agent pack, MCP server, or harness CLI? | selects `skill_pack`/`skill_lifecycle`, `host_setup`, or a plain binary install |
| Does it have a marketplace/registry entry? | prefer the marketplace route when the host supports it; use symlinks into the host's skills dir only when no marketplace exists or the registry needs a pinned, auditable copy. State the choice and reason. |
| Does it need other tools at install time or at runtime? | `requires` / `recommends` |

### 3. Check every supported platform AND architecture

Per the vendor's own docs: macOS, each Linux family the registry models
(debian/apt, fedora/dnf, arch/pacman), amd64 and arm64 separately. Declare a
method for each genuinely feasible combination; if one is knowingly omitted
(no vendor URL, no arm64 build), record why in `# Verified`.

**One tool can have different artifacts per OS/arch.** Do not assume one
install shape fits all. Typical splits: a `.dmg`/cask on macOS vs a vendor
script or tarball on Linux; distinct tarballs per arch; a package-manager
package on one distro and a release asset on another. Model each as its own
`[[tool.method]]` with `os`/`arch` params. If the registry schema cannot
express the split you found (for example a per-OS/arch artifact that is
neither a script nor an asset pattern), STOP and record the gap in the
backlog instead of bending an unrelated method kind to fit.

### 4. Choose the install method per platform

Prefer, in order, the option that is checksum-verifiable, reproducible, and
removable by this installer:

1. Package manager the user already trusts (brew, cask, apt/dnf/pacman) when
   the package is current enough. One package name may differ per distro —
   declare one method per manager.
2. Release asset or tarball with a checksum (`github_release`, `tarball`).
3. Language-ecosystem install (`node`, `uv-tool`, `sdkman`) with the manager in `requires`.
4. Vendor `script` (curl|bash style) ONLY when the vendor offers nothing
   better. A script install is **not** package-manager-owned and the Uninstall
   screen cannot plan its removal: record what it creates (install dir,
   symlinks, desktop files) in `# Verified` and file a removal-manifest
   backlog item rather than pretending a package manager owns it.

Never invent the exact method kind or param name — read the kinds and params
actually present in `installer/model.py` and existing entries.

### 4b. Decide how it is removed, per platform — before writing the entry

Installing a tool you cannot cleanly remove is half an onboarding. Removal
belongs to each METHOD (a method is already scoped by `os`/`arch`), never to
one tool-wide recipe or separate per-OS knobs. For each method from step 4:

| Method kind | What you write | What you still verify |
|---|---|---|
| `brew`, `cask`, `apt`, `dnf`, `pacman`, `uv-tool`, `node`, `sdkman` | nothing — removal derives from the manager | the package/candidate name the manager removes is the one installed |
| `github_release`, `tarball`, `app` | nothing — removal is exactly the path the install computed | install and removal use the same path; nothing else shares that path |
| `script`, `host_setup` | an explicit recipe: the vendor uninstaller, the exact files/symlinks/desktop entries it writes, or a verifying removal script | run the vendor installer in a disposable container and list what it wrote |

Per tool, shared by all its methods, research and record:
- **Config and data paths** (per-OS variant only when they differ) and the
  **default config policy**: `keep` (default for user-edited config),
  `delete`, or `ask` the user (keep config / delete all). State why.
- **Shared artifacts:** another catalog entry using the same binary or path
  (e.g. two entries pointing at one `drawio`) — removal must refuse or remove
  both by explicit choice. A file with the right name is never proof we wrote it.
- **Foreign owner:** if a manager the installer did not use owns the tool,
  removal delegates to that manager; it never runs another method's recipe.

Then check the platform can express it (see the principle above). Today
`Tool.uninstall` is a single free-text hint and `installer/uninstall.py`
`plan_uninstall` treats download/app kinds generically — per-method removal,
config policy and the removal prompt do not exist yet (backlog 999.8, design
recorded there). Until they do, record the researched recipe in `# Verified`,
set the `uninstall` hint, and do NOT claim the tool is removable.

### 5. Decide tier and audience

Apply `.claude/architecture.md`'s "Tier is a browsing label":

- **`system`** — a prerequisite other tools may depend on regardless of taste.
- **`user`** — a tool the human drives directly (terminals, editors, CLIs,
  and agent harness CLIs the human types into). AI branding alone does not
  make it `ai`.
- **`ai`** — consumed BY an agent session (MCP servers, token proxies,
  agent-oriented CLIs, skill packs).

`audience` (`human`/`ai`/`both`) is independent of tier.

### 6. Dependencies and postinstall mechanism

**REQUIRED READING:** `.claude/architecture.md`'s "Tool onboarding: tier,
dependencies, and postinstall classification" — the canonical decision tree;
read it rather than reconstructing it. A manager-installed tool names that
manager in `requires`; a runtime-only expectation the catalog cannot
guarantee also needs an edge, or a `# Verified` note when unsure. Walk the tree:
`postinstall` hook / `skill_pack` + `skill_lifecycle` / `host_setup` / none. If
it straddles two branches, name the ambiguity.

A hook is selected by NAME from the closed `POSTINSTALL_HOOKS` table, never a
command string, and must detect and merge, never blind-overwrite existing
host config (gate on `present_agent_hosts()`).

### 7. Postinstall and customizations — ask the user, do not assume

Ask whether the tool has well-known friction or nice-to-haves that a
postinstall or companion config should cover, then **ask the user which of
those they want** before building any. Do not enable them silently. Prompts to
walk through (examples of the shape, not an exhaustive list):

- Terminal emulators: word navigation with alt/option+arrows is often broken
  per OS (macOS vs Linux, per terminal); a "clear screen + scrollback" binding
  differs per OS (Cmd+K on macOS, Ctrl+Shift+K on Linux). Also which shell the
  terminal should launch (see `installer/terminal_shell.py`).
- Multiplexers/agent workspaces: companion scripts or a plugin from another
  repo (status icons, separators between agents).
- Shells/prompts/editors: plugin managers, themes, shell-integration lines.
- LLM tools: which hosts to wire (only the ones actually present).

Each accepted customization is its own idempotent, reversible step with a
sandboxed test; each declined one is recorded in `# Verified`.

### 8. Check the registry's existing classifiers (deep research)

Before writing the block, read how the classifiers disagree in this codebase —
three independent ones decide what the user sees:

- `installer/status.py` `is_installed` — the catalog's installed mark.
- `installer/ownership.py` `resolve_ownership` — the Owner column.
- `installer/uninstall.py` `plan_uninstall` — what the Uninstall screen can
  remove (download and app kinds only).

For the new entry, confirm all three give a truthful answer: presence is
detectable (`cmd`, `detect_path`, `bin_dir`), ownership resolves to something
sensible, and removal is either plannable or honestly "its own installer".
Also scan existing entries sharing its category/kind for the conventions to
copy (`rg` the registry, do not rely on memory).

### 9. Write the entry

`id`, `name`, `category`, `cmd`, `priority`, `audience`, `tier`, `verified =
YYYY-MM-DD`, `desc`, `requires`, optional `postinstall`, one `[[tool.method]]`
per real platform/arch path from steps 3-4, and the dated `# Verified` comment
(what was checked, what was knowingly left out, which customizations were
offered and the user's answers). Use only keys allowed for each method kind
(`METHOD_PARAMS` in `installer/model.py`); for `app`/`tarball` urls with
`{ver}`, set `version` and `sha256` together. Then validate with the repo's
gates and add tests for any new hook; sandbox every real install.

## Common Mistakes

- **Authoring from one OS.** Check every OS and arch the vendor ships for.
- **One install shape for all platforms.** Artifacts legitimately differ per
  OS/arch; model each, or file the schema gap.
- **Treating a vendor script as package-manager-owned.** It is not; record
  what it creates and its removal story.
- **Writing from memory when in doubt.** Research online first and cite it.
- **Skipping the marketplace question for LLM tooling.**
- **Shipping customizations nobody asked for, or skipping the question
  entirely.** Offer, ask, record.
- **Classifying an agent harness CLI as `ai` tier because it is AI-branded.**
- **Skipping a dependency edge because "the user probably has it".**
- **A postinstall hook that writes to every host unconditionally or passes an
  "auto"-style flag.**
- **Re-deriving the postinstall tree instead of reading architecture.md.**
