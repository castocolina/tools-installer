# Roadmap: tools-installer

## Overview

tools-installer is a cross-platform (macOS/Linux) Textual TUI and CLI that takes a
developer from a bare machine to a fully configured AI-assisted dev environment,
guided by a single declarative `registry.toml` catalog. This milestone (the first
of seven PRDs from the 2026-09-04 planning batch) reorganizes that catalog around
three tiers — system prerequisites, personal-pick user tools, and agent-facing AI
tooling — the mental model the user already uses when bootstrapping a machine,
while leaving the underlying hard-dependency resolver (`installer/deps.py`)
untouched, since it already does the ordering work correctly. It also introduces a
distinct `recommends` soft-dependency signal, closes two runtime gaps a prior code
review found (a silently-attempted dependent after a failed prerequisite, and an
uninstall sweep that misses tweak-managed executables), and lets Oh-My-Zsh's
bundled `git`/`docker` plugins be enabled through the existing shell-tweak
mechanism.

**All 7 PRDs of the 2026-09-04 planning batch are now ingested** (as of
batch 4/4). This roadmap's 12 phases are the complete scope of that
planning batch — no further PRD-ingest passes are expected to append phases
here, though future planning work outside this batch could still do so.

**Batch 2/7 (`package-manager-policy`) added Phases 4-6**: extending the
`npm`/`pip` ban to `npx` with a redirect policy, correcting `codegraph`'s and
`mmdc`'s install methods (plus the puppeteer/chrome-headless-shell chain
mmdc actually needs), and hardening the already-shipped SDKMAN-exclusivity
work (commit `0e05f50`) alongside two registry-authoring guidelines.

**Batch 3/7 (`catalog-expansion` + `postinstall-hooks`, ingested together
since postinstall-hooks' proving case is codegraph's MCP registration, which
only exists once catalog-expansion adds it) added Phases 7-9**: new
system/user-tier registry entries (zsh, oh-my-zsh, gnu-bash, Apple
Containers, kitty, wezterm), the new AI-tier entries plus a new `uv-tool`
executor kind (antigravity, cursor-agent, rtk, graphify), and the
postinstall-hooks mechanism itself proven via codegraph's MCP registration.

**Batch 4/4 (final batch — `agent-cli-ergonomics` + `background-maintenance-daemon`
+ `live-package-management`, bundled since none of the three depend on each
other) added Phases 10-12**: permissive-mode shell aliases and a durable
cursor-agent default-model wrapper, a macOS-only LaunchAgent wrapping the
existing tmpdir-prune script, and version-aware status plus a manager-delegated
update action — which also unblocks Phase 5's `REQ-pnpm-global-reinstall-mitigation`,
previously blocked on this exact mechanism not existing yet.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Catalog Tier Foundation** - Add the `tier` field to the Tool model/registry and prove the existing resolver already carries hard dependencies across tier boundaries
- [ ] **Phase 2: Tier-Scoped Catalog Views & Recommends** - Split Catalog into System/User/AI top-level views and add the `recommends` soft-dependency surfacing
- [ ] **Phase 3: Install/Uninstall & Tweak Lifecycle Hardening** - Skip dependents after a failed prerequisite, sweep tweak-managed executables on uninstall, and enable Oh-My-Zsh's bundled plugins
- [ ] **Phase 4: npm/npx Ban Extension & Redirect Policy** - Extend the ban to `npx` and redirect it to `pnpm dlx`, leaving `npm` hard-blocked pending its own subcommand-allowlist decision
- [ ] **Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer)** - Move `codegraph` to `kind="github_release"`, resolve `mmdc`'s install method with real research, and give `puppeteer`/`chrome-headless-shell` their own catalog entries
- [ ] **Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines** - Verify and harden the already-shipped SDKMAN-exclusivity work, and document the per-tool verification checklist and brew-preference guideline
- [ ] **Phase 7: System & User Tier Catalog Expansion** - Add zsh, oh-my-zsh, gnu-bash, Apple Containers (system tier) and kitty, wezterm (user tier), with real Linux/Bazzite parity
- [ ] **Phase 8: AI Tier Catalog Expansion & uv-tool Executor** - Add the new `uv-tool` executor kind, antigravity, cursor-agent, rtk, and wire `recommends` for agent hosts
- [ ] **Phase 9: Postinstall Hooks Mechanism** - Add the optional per-tool postinstall field/execution/idempotency mechanism, proven via codegraph's MCP registration
- [ ] **Phase 10: Agent CLI Ergonomics** - Add `codex-skip`/`opencode-auto` tweaks and a durable, live-verified cursor-agent default-model wrapper
- [ ] **Phase 11: Background Maintenance Daemon** - Wrap the existing tmpdir-prune script as a toggleable, macOS-only LaunchAgent with visible logs
- [ ] **Phase 12: Version-Aware Status & Update Action** - Add version-aware status, a cached/staleness-tracked version check, and a manager-delegated update action (unblocks Phase 5's pnpm-reinstall mitigation)

## Phase Details

### Phase 1: Catalog Tier Foundation
**Goal**: Every catalog tool is labeled system/user/ai, and the existing dependency resolver is proven to carry that labeling across tier boundaries without any new ordering logic.
**Depends on**: Nothing (first phase)
**Requirements**: REQ-catalog-tier-field, REQ-dependency-chain-requires
**Success Criteria** (what must be TRUE):
  1. Every tool in the catalog shows a `tier` (system/user/ai); a registry entry with a missing or unknown tier is rejected the same way an unknown priority is today.
  2. `uv`, `pnpm`, `brew`, and `sdkman` are shown as `tier="system"` tools.
  3. Selecting a dependent tool whose `requires` crosses a tier boundary (primary proof case: `java` needing `sdkman`, already shipped and decision-independent) still automatically drags in its dependency and reports it, exactly as it does today — with zero new resolver code. `mmdc` needing `pnpm` is a secondary example only, pending `mmdc`'s open install-method decision (Phase 5, REQ-mmdc-install-decision) — it may become `mmdc` needing `puppeteer` instead.
  4. `.claude/architecture.md` states plainly that `tier` is a browsing label and `requires` remains the only mechanism that determines install order.
**Plans**: TBD

### Phase 2: Tier-Scoped Catalog Views & Recommends
**Goal**: Browsing the catalog matches how the user actually walks a fresh machine — system prerequisites, then personal picks, then agent tooling — as three top-level views, and picking an AI tool can surface complementary tools without ever auto-installing them.
**Depends on**: Phase 1
**Requirements**: REQ-catalog-tier-views, REQ-recommends-soft-dependency
**Success Criteria** (what must be TRUE):
  1. The top nav offers three tier-scoped catalog views (System/User/AI) in place of the single flat Catalog, each still groupable/sortable by Category/Priority/Audience/Status/Table.
  2. Selecting `claude` (ai tier) from the AI view surfaces the `pnpm` (system tier) drag-in notice without requiring a prior visit to the System view.
  3. Opening the AI view first and selecting a tool with an unresolved system-tier dependency still makes the drag-in (or an unavailable-dependency notice) obvious, with no required visit order.
  4. Selecting `claude` or `opencode` surfaces a one-action prompt naming its `recommends` (e.g. `codegraph`, `graphify`, `rtk`) that the user can accept or dismiss — nothing in that list is ever installed automatically.
**Plans**: TBD
**UI hint**: yes

### Phase 3: Install/Uninstall & Tweak Lifecycle Hardening
**Goal**: A run that hits a failed prerequisite, or a full uninstall, is honest about what happened and leaves nothing stray behind — and Oh-My-Zsh's bundled plugins turn on the same way every other shell tweak does.
**Depends on**: Nothing — independent of the tier work in Phases 1-2
**Requirements**: REQ-install-failure-propagation, REQ-uninstall-sweep-tweak-executables, REQ-oh-my-zsh-plugin-config
**Success Criteria** (what must be TRUE):
  1. When a tool's dependency failed earlier in the same run, the tool is reported as skipped with a clear "dependency failed" reason — never silently attempted, never silently dropped from the summary.
  2. Running a full uninstall removes every tweak-managed executable (e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts.
  3. Toggling the Oh-My-Zsh plugins tweak in Policies enables the bundled `git` and `docker` plugins by editing the `plugins=(...)` array in `.zshrc`, with no separate catalog entry required.
**Plans**: TBD

### Phase 4: npm/npx Ban Extension & Redirect Policy
**Goal**: `npx` is banned/redirected the same disciplined way `npm`/`pip`/`pip3` already are, without silently masking a real underlying failure.
**Depends on**: Nothing — extends the existing `installer/guards.py` ban mechanism, independent of Phases 1-3
**Requirements**: REQ-npx-ban, REQ-npm-npx-redirect-policy
**Success Criteria** (what must be TRUE):
  1. `npx` is banned/shimmed identically to the existing three banned commands (same removability, same opt-in nature, same PATH-order warning logic).
  2. Running `npx <pkg>` transparently redirects to `pnpm dlx <pkg>` (or `pnpx`), preserving the underlying command's real exit code and stdout/stderr.
  3. `npm` itself remains hard-blocked (no redirect) until its own subcommand-allowlist decision is made separately.
  4. Doctor/guard status reporting covers `npx` the same way it covers the other three banned commands.
**Plans**: TBD

### Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer)
**Goal**: `codegraph`, `mmdc`, and the puppeteer/chrome-headless-shell chain mmdc actually depends on all have explicit, researched, correctly-recorded install methods — no tool silently depends on npm/pnpm underneath a method that looks like it doesn't.
**Depends on**: Nothing structurally, but REQ-pnpm-global-reinstall-mitigation within this phase is blocked on the not-yet-ingested `live-package-management` PRD (batch 5/7)'s update mechanism
**Requirements**: REQ-codegraph-github-release, REQ-mmdc-install-decision, REQ-puppeteer-catalog-entries, REQ-pnpm-global-reinstall-mitigation
**Success Criteria** (what must be TRUE):
  1. `codegraph` installs via `kind="github_release"`, not `pnpm add -g`.
  2. `mmdc`'s install method (pnpm-with-mitigation, brew, or volta) is decided explicitly after real research — not left ambiguous — with the decision recorded alongside why (postinstall-script security vs. the known pnpm global-install bug), and whether `volta` is actually a viable global-CLI installer (not just a Node runtime manager) verified rather than assumed.
  3. `puppeteer` and `chrome-headless-shell` exist as their own catalog entries; `mmdc.requires` includes `puppeteer` so it drags in automatically; whether this dependency applies identically on macOS and Linux is verified, not assumed.
  4. (Blocked until batch 5/7 lands) any tool still on `pnpm add -g` can have its whole pnpm-managed global set snapshotted and reinstalled together after a `pnpm` update.
**Plans**: TBD

### Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines
**Goal**: The SDKMAN-exclusivity work that shipped ahead of GSD's own process (commit `0e05f50`) gets the verification/hardening pass it skipped, and the registry-authoring discipline this whole PRD batch leans on is actually written down.
**Depends on**: Nothing — independent of Phases 1-5
**Requirements**: REQ-sdkman-exclusivity, REQ-registry-authoring-verification-checklist, REQ-brew-preference-guideline
**Success Criteria** (what must be TRUE):
  1. `java`/`gradle`/`maven`/`groovy`/`springbootcli` are confirmed installing exclusively through SDKMAN with real (not just unit-level) verification, including a non-interactive end-to-end check of `sdk install java` on an unconfigured machine.
  2. Whether `java`'s SDKMAN candidate needs a pinned `version` to avoid an interactive prompt is resolved, not left as an open question.
  3. A documented, mandatory per-tool per-OS verification step exists for future registry additions, with a defined recording mechanism.
  4. "Prefer brew over other userspace package managers, except SDKMAN for the Java toolchain" is written down as a registry-authoring guideline.
**Plans**: TBD

### Phase 7: System & User Tier Catalog Expansion
**Goal**: The system-tier prerequisites the user actually starts a fresh machine from (shell, shell framework, container runtime) and the terminal emulators they pick personally both exist in the catalog with verified, per-platform install methods.
**Depends on**: Phase 1 (needs `tier` field to exist) and Phase 4-6's registry-authoring verification checklist (REQ-registry-authoring-verification-checklist) as the discipline this phase's new entries must follow
**Requirements**: REQ-system-tier-shell-container-entries, REQ-terminal-emulator-entries, REQ-linux-bazzite-shell-parity
**Success Criteria** (what must be TRUE):
  1. `zsh`, `oh-my-zsh`, `gnu-bash` (macOS), Apple Containers (macOS) install cleanly via verified live methods; `oh-my-zsh`'s actual `.zshrc`-rewriting behavior has been read and confirmed safe as a `kind="script"` candidate before being treated as one.
  2. `kitty`, `wezterm` install cleanly on macOS (brew) with a verified Linux path (distro package or GitHub-release download).
  3. `zsh`/`oh-my-zsh` have a working Linux/Bazzite install path; the existing `podman` entry (not a new one) is the container-runtime story there.
  4. Whether Apple Containers needs an actual install step on a current macOS, or is a pure version-gate/doc entry, is resolved and recorded.
**Plans**: TBD

### Phase 8: AI Tier Catalog Expansion & uv-tool Executor
**Goal**: The agent-facing tools this project exists to serve — including the new `uv-tool` installer kind `graphify` needs — are in the catalog with verified install methods, and selecting an agent host surfaces its recommended companion tools.
**Depends on**: Phase 1 (tier field), Phase 2 (`recommends` mechanism must exist to be wired here)
**Requirements**: REQ-uv-tool-executor, REQ-agent-host-entries, REQ-rtk-github-release, REQ-recommends-wiring-agent-hosts
**Success Criteria** (what must be TRUE):
  1. `installer/executors.py` has a working `kind="uv-tool"` executor (`uv tool install <pkg>`); `graphify` installs via it using the PyPI package `graphifyy`.
  2. `antigravity` and `cursor-agent` install via a verified official method (not assumed) — the actual install method for both is unverified as of this ingest and needs GSD's own research pass first.
  3. `rtk` installs via `kind="github_release"` from `rtk-ai/rtk`, checksum-verified against its release's `checksums.txt`.
  4. Selecting `claude`/`opencode`/`codex`/`cursor-agent`/`antigravity` surfaces its `recommends` list (`codegraph`, `graphify`, `rtk`) via the Phase 2 mechanism, without auto-installing anything.
**Plans**: TBD

### Phase 9: Postinstall Hooks Mechanism
**Goal**: A catalog tool can declare a one-time, non-interactive follow-up action that runs immediately after its own successful install, proven end-to-end via codegraph's MCP registration for whichever agent hosts are already present.
**Depends on**: Phase 8 (codegraph must exist in the registry as the proving case)
**Requirements**: REQ-postinstall-field, REQ-postinstall-execution-timing, REQ-postinstall-idempotency-live-check, REQ-postinstall-noninteractive-only, REQ-codegraph-mcp-postinstall
**Success Criteria** (what must be TRUE):
  1. A tool can declare an optional `postinstall` command (inline or `postinstall_script` file) in the registry; it runs exactly once per successful install, immediately after the specific `Method` that succeeded.
  2. A postinstall failure is visible to the user but never marks the tool's own install as failed.
  3. Idempotency is a live check ("is the effect already present"), with no new state-tracking database anywhere in the codebase.
  4. A tool whose only setup path is interactive is not wired to this mechanism at all.
  5. After installing `codegraph`, its MCP server registers for every already-installed agent host (`claude`/`codex`/`opencode`/`cursor-agent`), and cleanly no-ops when none are installed.
**Plans**: TBD

### Phase 10: Agent CLI Ergonomics
**Goal**: `codex` and `opencode` get the same permissive-mode convenience `claude-skip` already provides, honestly labeled per their real (differing) semantics, and `cursor-agent` reliably gets a known-good default model on any bare invocation instead of silently inheriting whatever was last selected elsewhere.
**Depends on**: Nothing — extends the existing `TweakBundle`/`tweak_policy` mechanism, independent of Phases 1-9
**Requirements**: REQ-codex-skip-tweak, REQ-opencode-auto-tweak, REQ-cursor-agent-default-model-wrapper, REQ-agent-tweak-self-update-durability
**Success Criteria** (what must be TRUE):
  1. `codex-skip` aliases `codex` to its verified real bypass-permissions flag, with user-supplied flags always respected.
  2. `opencode-auto` aliases `opencode` to `opencode --auto`, with Policies detail-panel copy that accurately describes its narrower (not full-bypass) semantic.
  3. Invoking `cursor-agent`/`cursor` with no `--model` injects a live-verified, plain model slug (no bracket syntax); passing an explicit `--model` is never overridden.
  4. All three tweaks survive the target CLI self-updating in place (durable by construction — shell alias/function lookup precedes PATH search).
**Plans**: TBD

### Phase 11: Background Maintenance Daemon
**Goal**: The existing, already-safe `scripts/prune-user-tmpdir.sh` becomes a set-and-forget background policy, toggleable the same way every other Policies entry already is, with a real audit trail instead of silent background deletion.
**Depends on**: Nothing — new `daemon_policy` factory parallel to existing `Policy` factories, independent of Phases 1-10
**Requirements**: REQ-launchd-prune-policy, REQ-daemon-log-diagnostics, REQ-daemon-dependency-gating
**Success Criteria** (what must be TRUE):
  1. The Policies view offers a macOS-only toggle that installs/removes a LaunchAgent running the existing prune script daily (`--days 3` default, unchanged script logic/safety checks).
  2. The policy is invisible/inert on Linux.
  3. `fd`/`rg` show as recommended-but-optional; the daemon still runs correctly (via the script's own find/grep fallback) without them.
  4. Scheduled runs write an inspectable log, surfaced via the Policies detail panel for this one policy — no new top-level Diagnostics view.
**Plans**: TBD

### Phase 12: Version-Aware Status & Update Action
**Goal**: The catalog can answer "what's out of date" and act on it through the tool's own real manager, not just "is it installed" — and this becomes the mechanism Phase 5's pnpm-reinstall mitigation was waiting on.
**Depends on**: Nothing structurally for pieces #1-#4; piece #5 (the update action) is what Phase 5's `REQ-pnpm-global-reinstall-mitigation` sequences after
**Requirements**: REQ-version-aware-status-github, REQ-cached-timestamped-version-state, REQ-background-version-refresh-worker, REQ-manager-version-resolution, REQ-update-action-manager-delegation, REQ-manager-drift-alerting
**Success Criteria** (what must be TRUE):
  1. The catalog shows, per `github_release`-kind tool, current version vs. latest available, reusing the existing `resolve_github_tag` resolver.
  2. Version checks are cached with a `checked_at` timestamp; entries older than 7 days show stale and trigger a background re-check, not a full refetch every session.
  3. Version checks run via a Textual `Worker` without blocking first paint or keypresses; network failures degrade to "unknown," never crash.
  4. An "update" action exists and delegates to the tool's actual owning manager (brew/pnpm/uv tool/this installer's own path) — not assumed to always be this installer's executor.
  5. (Stretch, deferred/non-MVP) A tool installed via pnpm/npm with a newer version available via brew surfaces a distinct manager-drift alert.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Catalog Tier Foundation | 0/TBD | Not started | - |
| 2. Tier-Scoped Catalog Views & Recommends | 0/TBD | Not started | - |
| 3. Install/Uninstall & Tweak Lifecycle Hardening | 0/TBD | Not started | - |
| 4. npm/npx Ban Extension & Redirect Policy | 0/TBD | Not started | - |
| 5. Registry Method Corrections (codegraph/mmdc/puppeteer) | 0/TBD | Not started | - |
| 6. SDKMAN Hardening & Registry-Authoring Guidelines | 0/TBD | Not started | - |
| 7. System & User Tier Catalog Expansion | 0/TBD | Not started | - |
| 8. AI Tier Catalog Expansion & uv-tool Executor | 0/TBD | Not started | - |
| 9. Postinstall Hooks Mechanism | 0/TBD | Not started | - |
| 10. Agent CLI Ergonomics | 0/TBD | Not started | - |
| 11. Background Maintenance Daemon | 0/TBD | Not started | - |
| 12. Version-Aware Status & Update Action | 0/TBD | Not started | - |
