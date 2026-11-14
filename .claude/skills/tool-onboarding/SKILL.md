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
OS/arch artifacts a method kind cannot express, a customization with no hook — do not approximate it in the entry.
Record it as a platform gap in the GSD backlog and say so in `# Verified`. A
checklist that "covers" a case the platform silently mishandles is worse than
no checklist.

Judgment calls with no lint enforcement go in a dated `# Verified {date}: ...`
comment above the `[[tool]]` block. It is the only audit trail.

## When to Use

- Adding any `[[tool]]` block; reviewing one against these conventions.
- Noticing an existing tool lacks a postinstall, a platform, or a removal path.
- To audit every registry entry in one loop, use `catalog-audit` (`.claude/skills/catalog-audit/SKILL.md`).

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
| LLM tooling: plugin, skill, agent pack, MCP server, or harness CLI? | selects `host_setup`, a `postinstall` hook, or a plain binary install; the catalog installs no skills |
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
   better. A script install is **not** package-manager-owned: declare what it
   creates in `paths` (receipt-proven, L2), its own uninstall argv in `remove`
   (L3) and its self-update in `update` (step 4b); record anything else it
   creates in `# Verified`.
5. Source build in a throwaway Distrobox (`cargo_distrobox`) when no release
   asset or package exists for the host and the tool builds with cargo.

Never invent the exact method kind or param name — read the kinds and params
actually present in `installer/model.py` and existing entries.

### 4b. Decide how it is removed, per platform — before writing the entry

Installing a tool you cannot cleanly remove is half an onboarding. Removal
belongs to each METHOD (a method is already scoped by `os`/`arch`), never to
one tool-wide recipe or separate per-OS knobs. For each method from step 4:

| Method kind | What you write | What you still verify |
|---|---|---|
| `brew`, `cask`, `apt`, `dnf`, `pacman`, `uv-tool`, `node`, `sdkman` | nothing: removal derives from the manager (L1) | the package/candidate name the manager removes is the one installed |
| `github_release`, `tarball`, `app` | nothing: removal is the receipt of the paths the install computed (L2) | install and removal use the same path; nothing else shares that path |
| `cargo_distrobox` | `repo` (owner/name slug), `image` (fully qualified), `packages` (in-box build deps), `artifacts` (`{box, host}` tables) | the first artifact is the binary under ~/.local/bin; every `host` sits under ~/.local, ~/.config or ~/.terminfo; the box and the image it pulled are deleted on every outcome |
| `script` | `paths` (what it creates), optionally `remove` and `update`, `writable_prefix` when it writes outside `$HOME` | run the vendor installer in a disposable container and list what it wrote |
| `host_setup` | an explicit recipe: the files/symlinks/desktop entries it writes | the recipe removes exactly those |

```toml
[[tool]]
id = "alacritty"
config_paths = ["~/.config/alacritty"]   # tool level: kept on removal unless the user picks delete

[[tool.method]]
kind = "cargo_distrobox"
repo = "alacritty/alacritty"
image = "registry.fedoraproject.org/fedora-toolbox:44"
packages = ["cargo", "git", "cmake"]
artifacts = [
  { box = "src/target/release/alacritty", host = "~/.local/bin/alacritty" },
  { box = "terminfo/a/alacritty", host = "~/.terminfo/a/alacritty" },
]
```

Removal has three levels, tried in order by `uninstall.removal_plan`: **L1** the
manager's own remove, **L2** the receipt-proven artifacts (download, app,
`cargo_distrobox`, script `paths`), **L3** the script's `remove` recipe. One
example per script param (from the registry, except `remove`, which no entry
ships yet; `{omz_root}` is the only placeholder a script argv may use):

```toml
paths = ["~/.local/bin/uv", "~/.local/bin/uvx"]   # L2: what the script created
remove = ["{omz_root}/tools/uninstall.sh"]        # L3: its own uninstall argv (illustrative)
update = ["uv", "self", "update"]                 # its self-update argv
writable_prefix = "/home/linuxbrew"               # not writable by the user: hand off, never escalate
```

Per tool, shared by all its methods, research and record:
- **Config and data paths** (per-OS variant only when they differ) and the
  **default config policy**: `keep` (default for user-edited config),
  `delete`, or `ask` the user (keep config / delete all). State why.
- **Shared artifacts:** another catalog entry using the same binary or path
  (e.g. two entries pointing at one `drawio`) — removal must refuse or remove
  both by explicit choice. A file with the right name is never proof we wrote it.
- **Foreign owner:** if a manager the installer did not use owns the tool,
  removal delegates to that manager; it never runs another method's recipe.

### 5. Decide tier and audience

Apply `.claude/architecture.md`'s "Tier is a browsing label":

- **`system`** — a prerequisite other tools may depend on regardless of taste.
- **`user`** — a tool the human drives directly (terminals, editors, CLIs,
  and agent harness CLIs the human types into). AI branding alone does not
  make it `ai`.
- **`ai`** — consumed BY an agent session (MCP servers, token proxies,
  agent-oriented CLIs).

`audience` (`human`/`ai`/`both`) is independent of tier.

### 6. Dependencies and postinstall mechanism

**REQUIRED READING:** `.claude/architecture.md`'s "Tool onboarding: tier,
dependencies, and postinstall classification" — the canonical decision tree;
read it rather than reconstructing it. A manager-installed tool names that
manager in `requires`; a runtime-only expectation the catalog cannot
guarantee also needs an edge, or a `# Verified` note when unsure. Walk the tree:
`postinstall` hook / `host_setup` / none. If
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
  terminal should launch: that is the zsh terminal sync
  (`installer/terminal_shell.py`). Word navigation, clear-scrollback and other
  terminal customizations are the terminal's install tuning (a `post_install`
  action), never a Policies row.
- Multiplexers/agent workspaces: companion scripts or a plugin from another
  repo (status icons, separators between agents).
- Shells/prompts/editors: plugin managers, themes, shell-integration lines.
- LLM tools: which hosts to wire (only the ones actually present).

Each accepted customization is its own idempotent, reversible step with a
sandboxed test; each declined one is recorded in `# Verified`.

**Where an accepted customization lives.** It is install-time tuning: a named
action in the tool's `post_install` list, dispatched from the closed
`POST_INSTALL_HOOKS` table in `installer/post_install.py` (names in
`POST_INSTALL_ACTIONS`, `installer/model.py`). It runs at install with
no runtime question on every route, shows as `≈ apply install tuning` with
a RECONFIGURE step on a tool already present, and is reverted with the tool:
settings keys through the config-write ledger, shell blocks and plugin names
through their ownership records. A key the user already holds with another
value is kept and shown as `set by you`, so there is no opt-out knob. The
onboarding author still asks the developer which customizations to build
(above); the end user is never asked at install. Worked examples:
`apply_agent_tuning`, `set_omz_plugins`, `source_shell_init`.

A Policies row is only for something outside any install (an installer-wide
guard, a background job, a host environment redirect), and a new requirement
never becomes a Policies knob by default.

### 8. Check the registry's existing classifiers (deep research)

Before writing the block, read how the classifiers disagree in this codebase —
three independent ones decide what the user sees:

- `installer/status.py` `is_installed` — the catalog's installed mark.
- `installer/ownership.py` `resolve_ownership` — the Owner column.
- `installer/uninstall.py` `removal_plan` — what the Uninstall screen can
  remove: L1 the manager's own remove, L2 receipt-proven artifacts, L3 the
  script's `remove` recipe (step 4b).

For the new entry, confirm all three give a truthful answer: presence is
detectable (`cmd`, `detect_path`, `bin_dir`), ownership resolves to something
sensible, and removal is plannable or honestly "its own installer".
Also scan existing entries sharing its category/kind for the conventions to
copy (`rg` the registry, do not rely on memory).

### 9. Write the entry

`id`, `name`, `category`, `cmd`, `priority`, `audience`, `tier`, `verified =
YYYY-MM-DD`, `desc`, `requires`, optional `postinstall`, optional method
`smoke_argv` (argument tail only for the post-install smoke run; argv[0] is
always the installed path), one `[[tool.method]]` per real platform/arch path
from steps 3-4, and the dated `# Verified` comment
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
- **Turning an accepted customization into a Policies row or an install-time
  question.** It is install tuning: a Policies row is only for what lies
  outside any install, and an install-time question is a TUNE-04 miss.
- **Classifying an agent harness CLI as `ai` tier because it is AI-branded.**
- **Skipping a dependency edge because "the user probably has it".**
- **A postinstall hook that writes to every host unconditionally or passes an
  "auto"-style flag.**
- **Re-deriving the postinstall tree instead of reading architecture.md.**
- **Declaring a `smoke_argv` that answers before the binary itself runs (for
  example an AppImage runtime flag); confirm the binary answers `--version` or
  declare the smallest argument list that runs it.**
