# Agent-First Catalog and Unified UI - Product Requirements Document

## Requirements Description

### Background

The installer already provides a declarative cross-platform tool catalog and a
Textual application. Its installation workflow still leaves the application to
print command output, and it may ask several confirmations after the user has
approved a selection. The catalog also mixes high-frequency source-inspection
tools with personal applications and optional infrastructure.

The target user provisions a development machine for both interactive work and
coding agents. They need one visible, low-interruption workflow, good defaults,
and agent guidance that encourages concise, capable command-line tools.

### Goals

- Keep installation, doctor, fix, uninstall, guard, and policy actions inside
  the unified Textual application when a terminal is interactive.
- Expand and display catalog dependencies before one confirmation. Install the
  resulting plan sequentially, with dependencies first.
- Add safe, idempotent post-install actions to the declarative catalog.
- Divide the catalog into an AI-first Basic catalog and a User catalog.
- Manage shared agent-tooling guidance once at `~/.agents/AGENTS-TOOLING.md`.
- Audit and, when safely supported, configure read-only cross-agent access to
  `~/git` and agent configuration directories.

### Non-goals

- Replace an agent's own permission model or grant write, execute, network,
  credential, or broad home-directory access.
- Run arbitrary shell snippets from the registry.
- Guess a tool's package-manager owner.
- Automatically install a skill pack whose authoritative source, installer, or
  supported agent targets are not verified.

## Detailed Requirements

### Unified interactive workflow

When stdin and stdout are TTYs, every operational route opens `UnifiedApp` at
the relevant view. This includes the existing install flow and the `--doctor`,
`--fix`, `--uninstall`, `--guard`, and `--unguard` entry points. Piped, CI, and
`--yes` workflows retain a non-interactive console path.

The app must provide an installation view with:

- a scrollable, append-only live output pane;
- one visible row per planned tool with `queued`, `installing`, `installed`,
  `already installed`, `failed`, `skipped`, or `cancelled` state;
- the active tool and method; and
- post-run actions to retry failed tools, open Doctor, open Fix, open
  Uninstall, or return to the catalog without closing the app.

Installations run one at a time. This keeps package-manager locks, prompts,
and output attribution predictable.

### One approval and dependency planning

Selecting tools resolves the full transitive catalog dependency graph before
confirmation. The confirmation screen lists direct selections and added
dependencies, including why each was added. It orders the plan
topologically; dependencies install before dependents. Examples include
SDKMAN before Java, Java and SDKMAN before Groovy, and uv before Ruff.

The plan contains a default-enabled toggle named `Approve this plan without
further routine confirmations`. It suppresses subsequent routine questions for
the run. Security failures, required sudo authentication, and a request to
change the login shell remain explicit events with clear output and choices.

### Post-install action model

Methods and tools may declare ordered post-install actions. Each action is
idempotent, previewed before approval, records a clear outcome, and is tested
without real home-directory changes.

The initial controlled action set is:

- `configure_path`
- `source_shell_init`
- `set_login_shell`
- `enable_corepack`
- `pnpm_setup`
- `write_agent_reference`
- `run_command` only for named, reviewed internal commands with typed
  arguments; arbitrary shell fragments are forbidden.

Zsh installation includes RC integration and a default-enabled `set_login_shell`
action. It obtains a password through the normal system prompt only after the
user approves the action. On systems where zsh is absent from `/etc/shells`,
the app reports a manual administrator step rather than modifying that file.

PnPM setup must use its supported setup/configuration path, add its global bin
directory through the managed PATH mechanism, and be safe to repeat. `pnpm
setup` creates `PNPM_HOME`, copies the executable, and edits a shell RC file;
therefore it cannot run unconditionally alongside the installer's managed PATH
block. The implementation must either isolate and reconcile its RC edit or
implement the equivalent reviewed setup through the managed shellrc layer.
Corepack is a separate optional action, not a substitute for configuring pnpm's
global bin directory.

### Installation ownership and catalog status

The catalog sorts uninstalled, selectable tools first and installed tools last.
The status area reports an owner only after a reliable probe succeeds, such as
Homebrew, apt, dnf, pacman, pnpm, SDKMAN, or a managed userspace download.
Otherwise it reports `installed (owner unknown)`. It must never infer an owner
only from an executable path.

Probes are adapter-based and manager-specific. For example, SDKMAN is queried
for JVM candidates, pnpm is queried for its global packages, and native package
managers are queried through their own databases. The app displays a fallback
probe only when a higher-confidence probe did not establish ownership.

### Catalog tiers

The primary catalog is **AI-first Basic**. It contains portable CLI tools that
help people and agents inspect, search, transform, validate, and review source
with less output and better control than common legacy commands. Its recommended
core includes `rg`, `fd`, `bat`, `eza`, `jq`, `yq`, `delta`, `difftastic`,
`ast-grep`, Git, `gh`, `glab`, `uv`, `pnpm`, `ruff`, `gitleaks`, and `shfmt`.

**Project-dependent** tools remain in Basic but are marked as contextual. Docker,
Podman, Colima, Java, SDKMAN, Gradle, Maven, Deno, Bun, `xh`, and Mermaid CLI
belong here. They are relevant when a repository requires their ecosystem, not
as universal agent defaults.

The **User** catalog contains interactive agents, GUI/TUI applications, editors,
and skill or specification-development packages. Initial entries include Pi,
Codex, Claude Code, OpenCode, VS Code, Sublime Text, JetBrains Toolbox, draw.io
CLI and desktop application for macOS and Linux, and the approved skill packs.
The UI makes both catalogs visible as separate groupings; User entries are not
hidden, but they are never implied by an AI-first selection.

`aichat` is categorized as a user-facing LLM client, not an agent prerequisite.
Docker, Podman, and Colima are container infrastructure, not everyday
source-exploration recommendations.

### Agent tooling policy and CodeGraph guidance

The installer writes one managed source file at
`~/.agents/AGENTS-TOOLING.md`. It states preferred command replacements and
when to use them: `rg` instead of recursive `grep`, `fd` instead of most
`find`, `bat` for code viewing, `eza` for directory inspection, `delta` or
`difftastic` for diffs, `uv` rather than bare pip/system Python workflows, and
`pnpm` rather than bare npm global installs. It explains that precise tools
reduce unnecessary output and context use, while preserving normal tools when
their unique behavior is needed.

The same document contains a concise CodeGraph protocol:

- At the start of a new session or when entering an unfamiliar repository,
  check whether CodeGraph is initialized and current.
- Use `codegraph init` for an uninitialized repository and `codegraph index`
  after source, dependency, or structural changes that make the index stale.
- Prefer the CodeGraph Explore MCP tool for architecture and cross-reference
  questions before broad file reads.
- After `codegraph init`, rely on the MCP server's watcher and connection-time
  reconciliation during normal agent sessions. Use `codegraph status` to check
  health, `codegraph sync` only when the watcher is disabled or a script needs
  a known-fresh graph, and `codegraph index` for a deliberate full rebuild.
- Treat CodeGraph findings as navigational evidence; read authoritative source
  files before editing.

For each detected supported agent—Claude, Codex, OpenCode, Pi, and
Antigravity—the installer previews a small managed reference block in its
native instruction file. The block directs the agent to read
`~/.agents/AGENTS-TOOLING.md`. Existing user instructions remain untouched.

Doctor audits each agent's configuration and reports whether it can safely
express read-only access to `~/git/**` and the required shared configuration
directories (`~/.agents`, `~/.claude`, `~/.codex`, `~/.config/opencode`,
`~/.pi`, plus each detected agent's supported directory). Fix uses the agent
adapter matrix below, not a universal permission format:

- **OpenCode:** use focused `external_directory` allow rules with explicit
  `edit` denials for those paths when the user requests read-only access.
- **Antigravity CLI:** manage `read_file(<absolute path>)` allow entries in
  `~/.gemini/antigravity-cli/settings.json`; never add `write_file`,
  `command(*)`, or global wildcards.
- **Pi:** report `manual setup required`. Pi intentionally has no built-in
  filesystem sandbox; it runs as the launching user. Its project trust is an
  input-loading decision, not a read-path permission system.
- **Claude and Codex:** audit and offer only configuration mechanisms verified
  against the installed version. Claude's documented `--add-dir` is a
  launch-time directory grant, not a persistent universal read-rule format.

For every adapter, Fix operates as follows:

- no supported configuration: `audit only`;
- supported configuration: preview and apply narrowly scoped read-only rules;
- unsupported or ambiguous permission model: `manual setup required`, with the
  exact documented location and explanation.

No rule grants access to secrets, write paths, command execution, network, or
the whole home directory.

### Candidate skill packs

Each package must be installed through its official, agent-aware path and must
declare an owner, source URL, supported harnesses, revision/update policy,
target directories, and uninstaller before it becomes a catalog entry.

Research identified these official sources:

- `softaworks/agent-toolkit`: install selected skills with `npx skills add
  https://github.com/softaworks/agent-toolkit --skill <name>`.
- `obra/superpowers`: native marketplace/plugin installation per harness;
  Pi supports `pi install git:github.com/obra/superpowers`.
- `mattpocock/skills`: `npx skills@latest add mattpocock/skills`, or its
  documented Claude plugin marketplace path.
- `open-gsd/gsd-core`: `npx @opengsd/gsd-core@latest`, which uses a guided,
  cross-runtime installer.
- GitHub Spec Kit: use its official `specify` integration/init process rather
  than copying generated commands.
- `DietrichGebert/ponytail`: install through the host's official plugin path.
  It supports Claude Code, Codex, Pi, OpenCode, and Antigravity, and its Codex
  plugin contains lifecycle hooks that the user must review and trust.
- `Fission-AI/OpenSpec`: install `@fission-ai/openspec` with the selected
  Node package manager, run `openspec init` inside the project, and use
  `openspec update` to refresh generated agent guidance. The app must disclose
  its anonymous telemetry and provide `OPENSPEC_TELEMETRY=0` as an opt-out.

Ponytail and OpenSpec are User-catalog candidates. They require their own
official, agent-aware installers; the application must not copy their skill or
plugin files directly. Their installation plans must show the affected agent
hosts, generated files, lifecycle hooks, telemetry behavior, and uninstall
path before approval.

### draw.io Desktop

draw.io Desktop is a User-catalog desktop application. Its official desktop
build supports both macOS and Linux and is distributed through the maintained
`jgraph/drawio-desktop` release channel. The catalog must use explicit,
verified release assets for each OS and architecture, install only into the
user application directory, and model its CLI separately once its supported
binary path is verified. It must not add a package-manager fallback until that
fallback's ownership and application-directory behavior are verified.

## Design Decisions

The registry becomes the source of truth for tool metadata, dependencies,
ownership probes, catalog tier, and reviewed post-install action identifiers.
Python code supplies the behavior for each action and probe. This preserves the
current declarative design while preventing a registry entry from executing
unreviewed arbitrary shell.

The Textual UI owns all interactive mutation. Core functions still receive
injected runners, output sinks, home paths, and prompt callbacks so unit tests
remain deterministic. The console workflow remains a non-TTY adapter, not a
separate implementation of installation logic.

## Risks and Mitigations

- **Remote installers change.** Pin or record a reviewed revision where the
  upstream supports it, display the source, and rerun catalog validation on
  updates.
- **Agent permission formats change.** Use per-agent adapters and fail closed
  to manual guidance when a configuration cannot be safely understood.
- **Login-shell change fails.** Preserve the completed installation, report the
  failure, and provide the exact `chsh` remediation.
- **Skill packs overlap.** Present them as independent optional User entries;
  do not install all by default or treat their workflow instructions as
  compatible.

## Acceptance Criteria

- [ ] A TTY install, doctor, fix, uninstall, guard, or unguard session remains
  in the unified application until the user exits it.
- [ ] The installation view displays scrollable, attributed live output and
  per-tool state for a sequential plan.
- [ ] Dependency expansion is visible before one plan confirmation, installs in
  dependency order, and includes SDKMAN→Java→Groovy and uv→Ruff tests.
- [ ] The default-enabled approval toggle prevents routine repeat prompts.
- [ ] Checksums, sudo, and login-shell changes still surface clear explicit
  events.
- [ ] Registry post-install actions are typed, idempotent, previewable, and
  reject arbitrary shell snippets.
- [ ] Zsh configures RC integration and offers a confirmed login-shell change.
- [ ] PnPM setup is idempotent and its global bin directory appears once in the
  managed PATH.
- [ ] `glab` is present in the AI-first Basic catalog.
- [ ] Installed tools render after uninstalled tools and show only verified
  package-manager ownership.
- [ ] Basic and User catalogs render separately, with contextual infrastructure
  clearly distinguished from daily agent tooling.
- [ ] The app writes and idempotently updates `~/.agents/AGENTS-TOOLING.md`.
- [ ] Each supported agent receives only a managed reference block, preserving
  user-authored instructions.
- [ ] Doctor/Fix never broadens an agent beyond documented read-only scopes and
  reports unsupported agents without editing their configuration.
- [ ] Each added skill pack uses its official documented installer and has
  tests for install, status, update, and removal behavior.

## Execution Phases

### Phase 1: Catalog and core model

Add tier, dependency reason, ownership probe, and typed post-install action
models. Add `glab`, model JVM and Python dependencies, sort status, and build
strict registry validation.

### Phase 2: Unified execution UI

Build the sequential execution screen, live output adapter, plan approval
toggle, completion actions, and TTY route changes. Preserve the non-TTY
adapter and test both modes.

### Phase 3: Shell and ownership integration

Implement zsh, pnpm, and other reviewed actions; manager-specific ownership
probes; and precise failure/remediation states. Resolve the `pnpm setup` and
managed-shellrc interaction with a fixture-based test before enabling it.

### Phase 4: Agent tooling policy

Write the shared guidance document, managed agent references, and per-agent
read-only permission audit/fix adapters. Add CodeGraph guidance and fixtures
for each supported agent configuration.

### Phase 5: User catalog research and rollout

Verify each skill-pack source, installer, revision policy, and harness support.
Implement only vetted entries, including Ponytail and OpenSpec through their
official host-aware installers.

---

**Document Version:** 1.0
**Created:** 2026-07-25
**Clarification Rounds:** 3
**Quality Score:** 94/100
