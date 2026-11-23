---
name: tool-onboarding
description: Use when onboarding, adding, supporting or reviewing a tool in this installer's catalog, even when installer/registry.toml is never named, by researching what the tool is (OS tool, user app, LLM plugin, skill or agent pack), how and for which OS and arch it ships, which install method fits (brew, vendor script, package manager, per-platform artifact, marketplace vs symlink), how it is uninstalled per platform, its tier, dependencies and postinstall hook. Also use when a tool installs on only one OS here, because a platform gap becomes a backlog item and never a macOS-only label, and for terminal or IDE defaults (the four defaults applied as rules, meaning zsh shell on Linux, word navigation, clear screen and scrollback, new tabs in the current directory) and which extras to offer (shell integration, companion plugins). Not for auditing every entry against upstream, checking only release pins (`make verify-registry`), or installing a tool on this machine.
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

The one exception is the closed per-terminal table in `references/terminal-defaults.md`, read at step 7: its rows are the registry's terminal and editor entries, not examples, and `tests/test_tool_onboarding_skill.py` keeps them in step with `installer/registry.toml`.

**The skill cannot promise what the platform does not do.** Every decision
below must land on a mechanism that exists in code today (a method kind, a
param, a hook name, a classifier). Name the file that implements it. If the
right answer needs a capability the registry, model or installer lacks — per-
OS/arch artifacts a method kind cannot express, a customization with no hook — do not approximate it in the entry.
Record it as a platform gap in the GSD backlog (a `### Phase 999.x` item under `## Backlog` in `.planning/ROADMAP.md`) and say so in `# Verified`. A
checklist that "covers" a case the platform silently mishandles is worse than
no checklist.

Judgment calls with no lint enforcement go in a dated `# Verified {date}: ...`
comment above the `[[tool]]` block. It is the only audit trail.

## When to Use

- Adding any `[[tool]]` block; reviewing one against these conventions.
- Noticing an existing tool lacks a postinstall, a platform, or a removal path.
- Reviewing an existing entry: run steps 3, 4b and 8 against its block, then update its `# Verified` comment (and its row in `references/terminal-defaults.md` if it is a terminal or editor).
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
| LLM tooling: plugin, skill, agent pack, MCP server, or harness CLI? | selects a `postinstall` hook or a plain binary install; the catalog installs no skills |
| Does it have a marketplace/registry entry? | prefer the marketplace route when the host supports it; use symlinks into the host's skills dir only when no marketplace exists or the registry needs a pinned, auditable copy. State the choice and reason. |
| Does it need other tools at install time or at runtime? | `requires` / `recommends` |

### 3. Check every supported platform AND architecture

Per the vendor's own docs: macOS, each Linux family the registry models
(debian/apt, fedora/dnf, arch/pacman), amd64 and arm64 separately. Declare a
method for each genuinely feasible combination; if one is knowingly omitted
(no vendor URL, no arm64 build), record why in `# Verified`.

**Parity rule: a tool is guaranteed on macOS and on Linux, unless the tool itself exists for one OS only or the other OS already ships it (gnu-bash: Linux has a modern bash); record which in `# Verified`.** "Only available" means the vendor ships no build for the other OS (iTerm2 is macOS-only; a Linux-only desktop tool is the mirror case). It does not mean this installer cannot place the build yet: a disabled cask, a `.dmg` with no executor or a missing arm64 asset is a platform gap, and a platform gap is a defect to close, not a scoping choice. When a method is missing on one OS, say so in `# Verified`, open a `### Phase 999.x` backlog item that names the missing capability, and keep the tool in the matching gap set of `tests/test_registry.py` (`NO_MACOS`, `NO_MACOS_INTEL`, `NO_LINUX_ARM64`, `NO_DEBIAN_FEDORA_ARM64`; add a new one such as `NO_LINUX` when the missing OS has none, and add it to the `allowed` union of `test_every_tool_resolves_at_least_one_method_on_each_platform` in the same change) with that item named, so the gap stays visible until it closes. A tool the vendor ships for one OS only goes in `MACOS_ONLY` (or a matching one-OS set) with the vendor fact as its comment; the gap sets are only for this installer's own gaps. Never describe such an entry as "Linux-only" or "macOS-only" unless the vendor ships for that one OS.

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
3. Language-ecosystem install with the manager in `requires`: `bun` for npm-package CLIs (first),
   `node` (the pnpm fallback), `uv-tool`, `sdkman`.
4. Vendor `script` (curl|bash style) ONLY when the vendor offers nothing
   better. A script install is **not** package-manager-owned: declare what it
   creates in `paths` (receipt-proven, L2), its own uninstall argv in `remove`
   (L3) and its self-update in `update` (step 4b); record anything else it
   creates in `# Verified`.
5. Source build in a throwaway Distrobox (`cargo_distrobox`) when no release
   asset or package exists for the host and the tool builds with cargo.

Never invent the exact method kind or param name — read the kinds and params
actually present in `installer/model.py` and existing entries.

#### macOS apps

For every macOS app, record in `# Verified` how it installs, how it uninstalls, how it is configured, and whether its method can place the bundle in `~/Applications` instead of `/Applications`, which restricted machines deny. The methods that can:

- a cask: the `cask` kind runs `brew install --cask` with `--appdir` set to `applications_dir()`, which is `~/Applications` (`installer/executors.py`, `installer/locations.py`);
- the `app` kind (`installer/apps.py`): it extracts a `.zip` with `ditto -x -k` into `~/Applications` and links its `cli` (renamed by `cli_name`, read in `installer/download.py`) into `~/.local/bin`;
- a vendor installer that takes a destination.

Where the method allows it, the bundle goes to `~/Applications`, and every app that ships a CLI gets that CLI linked into `~/.local/bin` so it runs from the command line. Where no method allows a user location, the entry's `# Verified` comment says why. Two platform gaps are recorded, never promised: a `.dmg` (the `app` kind extracts `.zip` only, and no dmg kind exists), and a cask's CLI link (brew links it, not into `~/.local/bin`; the `cask` params are `cask`, `app`, `min_os_version` and `smoke_argv`). kitty's cask places `kitty.app` in `~/Applications`.

A macOS app can stop on a first-run dialog that blocks every new window until someone answers it. Launch the app once on a real Mac (an agent never does this on the host: write it as a UAT line deferred to the owner's Mac), list every dialog it shows, and put each one in one of three groups:

- The post-install answers it, by writing the setting the dialog needs, so nothing waits on a person. Example: iTerm2 shows a locale dialog when the system region has no UNIX locale (for example `en_CL`), and its Dynamic Profile pins `en_US.UTF-8` in that case.
- The owner answers it. Examples: iTerm2's "Check for updates automatically?" Sparkle choice, and iTerm2's scrollback permission prompt on the first Ctrl+L typed at the prompt (the zsh widget's ESC[3J), a preference that backlog 999.37 still has to decide.
- It is expected and named in the UAT line. Example: the Gatekeeper "downloaded from the Internet" prompt, once per fresh cask install, because Homebrew leaves `com.apple.quarantine` on the bundle; the installer never strips it.

Also write, per terminal, a UAT line deferred to the owner's Mac that checks the wheel scrolls inside a pager (alternate screen) and a click on a link opens the default browser; record the owner's result in `# Verified` once reported. An agent never runs these checks on the host.

### 4b. Decide how it is removed, per platform — before writing the entry

Installing a tool you cannot cleanly remove is half an onboarding. Removal
belongs to each METHOD (a method is already scoped by `os`/`arch`), never to
one tool-wide recipe or separate per-OS knobs. For each method from step 4:

| Method kind | What you write | What you still verify |
|---|---|---|
| `brew`, `cask`, `apt`, `dnf`, `pacman`, `uv-tool`, `bun`, `node`, `sdkman` | nothing: removal derives from the manager (L1) | the package/candidate name the manager removes is the one installed |
| `github_release`, `tarball`, `app` | nothing: removal is the receipt of the paths the install computed (L2) | install and removal use the same path; nothing else shares that path |
| `cargo_distrobox` | `repo` (owner/name slug), `image` (fully qualified), `packages` (in-box build deps), `artifacts` (`{box, host}` tables) | the first artifact is the binary under ~/.local/bin; every `host` sits under ~/.local, ~/.config or ~/.terminfo; the box and the image it pulled are deleted on every outcome |
| `script` | `paths` (what it creates), optionally `remove` and `update`, `writable_prefix` when it writes outside `$HOME`; `install` is a fixed validated argv for an extension such as `gh extension install`, with elevation commands, shells, launchers, `xcode-select`, `softwareupdate` and placeholders refused; `handoff` is a closed name for a detect-only native tool such as `xcode-clt` whose command is shown, never run; `prefer` ranks this script before the same tool's brew method and requires that method | run the vendor installer in a disposable container (`scripts/detect-container-runtime.sh` picks the runtime; never on the host) and list what it wrote |

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
example per script param (from the registry; the `remove` line is illustrative, and the real one is the `opencode` entry's script `remove` argv; `{omz_root}` is the only placeholder a script argv may use):

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
guarantee also needs an edge, or a `# Verified` note when unsure. Walk the tree to one of two outcomes, a `postinstall` hook or none; if it straddles two branches, name the ambiguity.

A hook is selected by NAME from the closed `POSTINSTALL_HOOKS` table, never a
command string, and must detect and merge, never blind-overwrite existing
host config (gate on `postinstall.present_hosts()`, live presence through `present_harnesses`).

### 7. Postinstall and customizations: terminal defaults are rules, extras are asked

Every terminal and IDE entry gets each of the four defaults below that it has the capability for, as a rule applied at install without a question. Only extras beyond them are offered to the developer (the last subsection of this step).

#### Terminal and IDE defaults

Check the vendor default first for every rule: write a binding only where the default does not already meet it, and mark the cell `vendor` otherwise. These four rules apply, without asking, to every terminal and IDE entry that has the capability: none of them is a question to the developer or to the end user, and each is install tuning, never a Policies row. Rule (a) is the lifecycle-wide zsh terminal sync (`installer/terminal_shell.py`, called by `installer/compose.py` `_sync_terminals`); the others are written by the entry's `post_install` actions. The table in `references/terminal-defaults.md` marks a rule an entry lacks, or a part that is out of scope here such as IDE keybindings, `n/a` with the reason.

- (a) Linux, Bazzite included: zsh is the launched shell. That is the zsh terminal sync (`installer/terminal_shell.py`).
- (b) macOS: Option+Left and Option+Right move by word by binding only those two chords, never the global Option-as-Alt switch: on the owner's Spanish layout that switch breaks `@`, `|`, `#` and `\`.
- (c) macOS and Linux: Cmd+K on macOS and Ctrl+Shift+K on Linux clear the screen and the scrollback. Where the vendor chord does not already clear both (iTerm2's Cmd+K does), the chord sends Ctrl+L, and the managed zsh configuration makes Ctrl+L clear both, and its widget must send ESC[H ESC[2J ESC[3J once and only then redraw the prompt (kitty's ESC[3J also wipes the visible screen, so any other order erases the prompt); that zsh part is written in phase 28 (KEYS-03) by zsh's shell-init block in `installer/tweaks.py`, install tuning of the `zsh` entry.
- (d) Every OS: a new tab, window or pane opens in the current directory; the installer writes it only where the vendor default does not already do it.

The table in `references/terminal-defaults.md` says how each entry meets each rule.

#### Closed per-terminal table

When the entry is a terminal or editor, read [the table](references/terminal-defaults.md) now (`references/terminal-defaults.md`): one row per `terminal` or `editor` entry in `installer/registry.toml`, a status word at the start of every rule cell, and the Konsole note. A new terminal adds its row there with its entry, and `tests/test_tool_onboarding_skill.py` keeps it in step with `installer/registry.toml`.

#### Conflicts

- A binding the user already defines is never overridden: the installer keeps it and reports the row as `partial: kept yours`. That result is the `{terminal}: partial: you already ...` line; phase 28 moved it out of `installer/terminal_shell.py` into `installer/terminal_regions.py` and kept its wording as it was, and `installer/version_status.py` still reads it by its `partial:` prefix. Example (today): when the user's `alacritty.toml` already binds a chord the alacritty sync would add, the sync skips that binding and reports `alacritty: partial: you already bind ...`, the line that becomes `partial: kept yours`.
- A vendor default that conflicts with a rule is overridden only with an install note that names the displaced default. Example (written since phase 29, TERM-01): kitty on Linux binds `ctrl+shift+k` to `scroll_line_up`; rule (c) takes that chord, and the install note names `scroll_line_up` as the displaced default.

#### Testing macOS behavior

- Each macOS behavior is a pure config generator (existing file text in, new text out) with a golden-file test that runs on both OSes, so Linux CI and a Linux host exercise it too.
- macOS CI covers the file paths: the `validate-and-test` job in `.github/workflows/ci.yml` runs on the matrix `[ubuntu-latest, macos-latest]` (shown as "validate & test on macos-latest"), and its `Test` step runs `make test` on macOS. A docs-only change skips those steps (the `Classify the change` step), so a change that adds a macOS behavior must change code or tests, not only Markdown.
- The real-Mac check is a UAT line marked deferred to the owner's Mac; no agent marks it passed.

#### Extras are asked

Beyond the four defaults, look for well-known friction or nice-to-haves that a postinstall or companion config should cover, then offer them to the developer and build only the ones they accept. Prompts to walk through (examples of the shape, not an exhaustive list):

- Multiplexers/agent workspaces: companion scripts or a plugin from another
  repo (status icons, separators between agents).
- Shells/prompts/editors: plugin managers, themes, shell-integration lines.
- LLM tools: which hosts to wire (only the ones actually present).

Each accepted extra is its own idempotent, reversible step with a sandboxed test; each declined one is recorded in `# Verified`.

**Where an accepted customization lives.** It is install-time tuning: a named
action in the tool's `post_install` list, dispatched from the closed
`POST_INSTALL_HOOKS` table in `installer/post_install.py` (names in
`POST_INSTALL_ACTIONS`, `installer/model.py`). It runs at install with
no runtime question on every route, shows as `≈ apply install tuning` with
a RECONFIGURE step on a tool already present, and is reverted with the tool:
settings keys through the config-write ledger, shell blocks and plugin names
through their ownership records. A key the user already holds with another
value is kept and shown as `set by you`, so there is no opt-out knob. The
onboarding author offers the developer only the extras (this subsection); the four terminal defaults are never offered, and the end user is never asked at install. Worked examples:
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
YYYY-MM-DD`, `desc`, `requires`, optional `postinstall` (LLM host wiring, `POSTINSTALL_HOOKS`), optional `post_install` (install-tuning actions, `POST_INSTALL_HOOKS`: a different list), optional method
`smoke_argv` (argument tail only for the post-install smoke run; argv[0] is
always the installed path), one `[[tool.method]]` per real platform/arch path
from steps 3-4, and the dated `# Verified` comment
(what was checked, what was knowingly left out, which extras were offered and the developer's answers; the terminal defaults are rules and are never offered). Use only keys allowed for each method kind
(`METHOD_PARAMS` in `installer/model.py`); for `app`/`tarball` urls with
`{ver}`, set `version` and `sha256` together. Then validate: `make verify-registry` for the pins, the targeted tests for the entry (`uv run pytest tests/test_tool_onboarding_skill.py` for a terminal or editor, which also keeps `references/terminal-defaults.md` in step), and `make validate` and `make test` once the entry is done (the commit hook already runs the static gates on every commit). Add tests for any new hook, and sandbox every real install in a disposable container: `scripts/detect-container-runtime.sh` picks the runtime, run the installer in a throwaway container, list what it wrote, then remove the container; never run it on the host. A macOS-only method (a cask, the `app` kind, a macOS vendor script) cannot run in a Linux container: record its install and removal facts from the vendor docs in `# Verified`, and add a UAT line deferred to the owner's Mac; no agent marks it passed.

Example `# Verified` lines for a macOS cask (Example is a placeholder):

```toml
# Verified 2026-11-19: bundle in ~/Applications/Example.app through the cask's --appdir;
# its CLI link is brew's, not ~/.local/bin (platform gap).
```

For an `app`-kind entry:

```toml
# Verified 2026-11-19: bundle in ~/Applications/Example.app, extracted from the vendor .zip by the app kind;
# CLI example linked into ~/.local/bin by the app kind's cli param.
```

For an app whose only macOS build is a `.dmg`:

```toml
# Verified 2026-11-19: no user location, because the vendor ships only a .dmg and the app kind extracts .zip only (platform gap).
```

## Common Mistakes

- **Treating a vendor script as package-manager-owned.** It is not: without `paths`
  and `remove` the Uninstall screen cannot plan its removal (step 4b).
- **Skipping the marketplace question for LLM tooling.** Step 2 prefers the
  marketplace route when the host supports it; an unasked question silently picks
  a symlinked copy instead.
- **Shipping a non-terminal extra nobody asked for (a multiplexer companion, a shell theme, an editor plugin, an LLM host), or skipping that question.** Offer, ask, record.
- **Asking the developer about one of the four terminal defaults.** They are rules (step 7); only extras are offered.
- **Never use the global Option-as-Alt switch for word navigation;** bind only the two chords: on a Spanish layout the switch breaks `@`, `|`, `#` and `\`.
- **Turning an accepted customization into a Policies row or an install-time
  question.** It is install tuning: a Policies row is only for what lies
  outside any install, and an install-time question is a TUNE-04 miss.
- **Classifying an agent harness CLI as `ai` tier because it is AI-branded.** Tier
  is who drives the tool (step 5), and the human types into a harness CLI.
- **Skipping a dependency edge because "the user probably has it".** `requires` is
  the only install-order and drag-in mechanism; without the edge the tool installs
  in the wrong order or fails on a clean machine.
- **A postinstall hook that writes to every host unconditionally or passes an
  "auto"-style flag.** It creates config for hosts the developer does not have;
  gate on `postinstall.present_hosts()` (step 6).
- **Calling an entry "Linux-only" because the installer has no method for the other OS.** Parity is the rule (step 3): the gap is a backlog defect with a named capability, not a scope decision.
- **Verifying a macOS terminal by its config bytes alone.** Type words and move by word, fill several screens, clear, and look at the prompt, the screen and the scrollback in the real terminal with the owner's real zsh prompt; open a tab, a window and a split and read their directory. Config bytes and golden tests passed while live iTerm2 still showed a locale dialog and a scrollback prompt. An agent never runs it on the host: write these checks as a UAT line deferred to the owner's Mac.
- **Declaring a `smoke_argv` that answers before the binary itself runs (for
  example an AppImage runtime flag); confirm the binary answers `--version` or
  declare the smallest argument list that runs it.**
