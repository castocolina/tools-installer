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
update action. **Note (2026-09-04):** `REQ-pnpm-global-reinstall-mitigation` moved
to Phase 4, resolved there via a Volta redirect (root-cause fix) instead of
waiting on this Phase 12 mechanism — see Phase 4's scope note.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Catalog Tier Foundation** - Add the `tier` field to the Tool model/registry and prove the existing resolver already carries hard dependencies across tier boundaries (completed 2026-09-04)
- [x] **Phase 2: Tier-Scoped Catalog Views & Recommends** - Split Catalog into System/User/AI top-level views and add the `recommends` soft-dependency surfacing (completed 2026-09-05)
- [x] **Phase 3: Install/Uninstall & Tweak Lifecycle Hardening** - Skip dependents after a failed prerequisite, sweep tweak-managed executables on uninstall, and enable Oh-My-Zsh's bundled plugins (completed 2026-09-05)
- [x] **Phase 4: npm/npx Ban Extension & Redirect Policy** - Extend the ban to `npx` and redirect it to `pnpm dlx`, leaving `npm` hard-blocked pending its own subcommand-allowlist decision (completed 2026-09-05)
- [ ] **Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer)** - Move `codegraph` to `kind="github_release"`, resolve `mmdc`'s install method with real research, and give `puppeteer`/`chrome-headless-shell` their own catalog entries
- [ ] **Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines** - Verify and harden the already-shipped SDKMAN-exclusivity work, and document the per-tool verification checklist and brew-preference guideline
- [ ] **Phase 7: System & User Tier Catalog Expansion** - Add zsh, oh-my-zsh, gnu-bash, Apple Containers (system tier) and kitty, wezterm (user tier), with real Linux/Bazzite parity
- [ ] **Phase 8: AI Tier Catalog Expansion & uv-tool Executor** - Add the new `uv-tool` executor kind, antigravity, cursor-agent, rtk, and wire `recommends` for agent hosts
- [ ] **Phase 9: Postinstall Hooks Mechanism** - Add the optional per-tool postinstall field/execution/idempotency mechanism, proven via codegraph's MCP registration
- [ ] **Phase 10: Agent CLI Ergonomics** - Add `codex-skip`/`opencode-auto` tweaks and a durable, live-verified cursor-agent default-model wrapper
- [ ] **Phase 11: Background Maintenance Daemon** - Wrap the existing tmpdir-prune script as a toggleable, macOS-only LaunchAgent with visible logs
- [ ] **Phase 12: Version-Aware Status & Update Action** - Add version-aware status, a cached/staleness-tracked version check, and a manager-delegated update action (unblocks the automatic trigger for REQ-pnpm-global-reinstall-mitigation)

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

**Plans**: 1 plan
Plans:

- [x] 01-01-PLAN.md — Tier enum + hard-required Tool.tier validation, full registry backfill, resolver cross-tier proof, architecture.md statement

### Phase 2: Tier-Scoped Catalog Views & Recommends

**Goal**: Browsing the catalog matches how the user actually walks a fresh machine — system prerequisites, then personal picks, then agent tooling — as three top-level views, and picking an AI tool can surface complementary tools without ever auto-installing them.
**Depends on**: Phase 1
**Requirements**: REQ-catalog-tier-views, REQ-recommends-soft-dependency
**Success Criteria** (what must be TRUE):

  1. The top nav offers three tier-scoped catalog views (System/User/AI) in place of the single flat Catalog, each still groupable/sortable by Category/Priority/Audience/Status/Table.
  2. Selecting a tool from a tier view whose `requires` crosses a tier boundary surfaces that dependency's drag-in notice in-view, without requiring a prior visit to the tier that owns it — proved against the real `mmdc` (user tier) → `pnpm` (system tier) edge plus an ai→system fixture. *(Rewritten 2026-09-04 during plan-review convergence: this criterion previously named `claude` → `pnpm`, but `claude` installs via its own script/cask and declares no `requires` at all, so the original wording could only have been satisfied by inventing a false catalog edge. Phase 8's `REQ-recommends-wiring-agent-hosts` is where agent hosts gain real cross-tier relationships.)*
  3. Opening the AI view first and selecting a tool with an unresolved system-tier dependency still makes the drag-in (or an unavailable-dependency notice) obvious, with no required visit order.
  4. Selecting `claude` or `opencode` surfaces a one-action prompt naming its `recommends` — in Phase 2 the illustrative set `rg`, `fd`, `jq`, all tools already in the catalog — that the user can accept or dismiss; nothing in that list is ever installed automatically. *(Reworded 2026-09-04 during plan-review convergence: the example previously named `codegraph`/`graphify`/`rtk`, which are Phase 8 catalog entries and do not exist in `registry.toml` while Phase 2 runs, so the criterion could not be checked against a real registry. Per CONTEXT D-02/D-03 the mechanism ships now with existing tools; Phase 8's `REQ-recommends-wiring-agent-hosts` replaces the data with the real companion set and this criterion's example moves with it.)*

**Plans**: 2 plans
Plans:

- [x] 02-01-PLAN.md — Three tier-scoped catalog views (System/User/AI) over one shared staged selection, plus cross-tier `requires` visibility
- [x] 02-02-PLAN.md — `Tool.recommends` soft-dependency field and the one-action, non-blocking selection-time prompt

**UI hint**: yes

### Phase 3: Install/Uninstall & Tweak Lifecycle Hardening

**Goal**: A run that hits a failed prerequisite, or a full uninstall, is honest about what happened and leaves nothing stray behind — and Oh-My-Zsh's bundled plugins turn on the same way every other shell tweak does.
**Depends on**: Nothing — independent of the tier work in Phases 1-2
**Requirements**: REQ-install-failure-propagation, REQ-uninstall-sweep-tweak-executables, REQ-oh-my-zsh-plugin-config
**Success Criteria** (what must be TRUE):

  1. When a tool's dependency failed earlier in the same run, the tool is reported as skipped with a clear "dependency failed" reason — never silently attempted, never silently dropped from the summary.
  2. Running a full uninstall removes every tweak-managed executable (e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts.
  3. Toggling the Oh-My-Zsh plugins tweak in Policies enables the bundled `git` and `docker` plugins by editing the `plugins=(...)` array in `.zshrc`, with no separate catalog entry required.

**Plans**: 3 plans
Plans:

- [x] 03-01-PLAN.md — Skip a dependent whose prerequisite failed earlier in the run: `InstallStatus.DEPENDENCY_FAILED`, `InstallOutcome.blocked_by`, and the summary/reason reporting (wave 1)
- [x] 03-02-PLAN.md — Oh-My-Zsh bundled plugins as a Policy: the in-place `plugins=(...)` editor in a new `installer/omz.py` plus the presence-gated `omz_plugins_policy` (wave 1)
- [x] 03-03-PLAN.md — Symmetric uninstall teardown: sweep every enabled tweak's block, helper executable and plugins edit through the existing Policies disable path (wave 2, needs 03-02)

**UI hint**: yes — plans 03-02 (Policies row) and 03-03 (Uninstall row) each carry a gating `tmux` structural check; 03-01 touches no Textual surface.

### Phase 4: Package Manager Redirect Policy

**Goal**: Every banned command that has a safe, argv-compatible managed-toolchain equivalent transparently redirects to it instead of hard-blocking, without silently masking a real underlying failure or losing pnpm's gated-postinstall security where it matters.
**Depends on**: Nothing — extends the existing `installer/guards.py` ban mechanism, independent of Phases 1-3
**Requirements**: REQ-npx-ban, REQ-npm-npx-redirect-policy, REQ-npm-global-volta-redirect, REQ-pnpm-global-reinstall-mitigation
**Scope note (expanded 2026-09-04 discuss-phase):** originally npx-only; the user asked to fold in the already-open pip/pip3 redirect question and the Volta global-install split, since both live in the same `installer/guards.py` mechanism this phase touches, and the Volta redirect directly resolves `REQ-pnpm-global-reinstall-mitigation` (re-pointed here from Phase 5/after-Phase-12).
**Success Criteria** (what must be TRUE):

  1. `npx` is redirected via a new `REDIRECTED` shim mechanism, parallel to (not a generalization of) the existing `BANNED` hard-block dict; `npm` (non-global) and any tool for which redirect research finds no safe target stay on the original hard-block path — same removability, same opt-in nature, same PATH-order warning logic either way.
  2. Running `npx <pkg>` transparently execs into `pnpm dlx "$@"`, preserving the underlying command's real exit code and stdout/stderr.
  3. Research determines whether `uv pip <subcommand>` (install/uninstall/list/show/freeze/compile) is a safe drop-in for `pip`/`pip3`; if yes, they redirect the same way `npx` does in this phase — if the research finds a gap, they stay hard-blocked and the gap is documented, not papered over.
  4. Research determines whether `volta install` shells out to npm internally (losing pnpm's gated-postinstall security) before `npm install -g`/`npm add -g` (and `pnpm add -g` itself) redirect to `volta install <pkg>`; a non-global `npm install`/`npx` invocation still redirects to plain `pnpm`/`pnpm dlx`. This split resolves `REQ-pnpm-global-reinstall-mitigation`'s root cause for anything moved to Volta — Phase 4 must determine whether any catalog tool still needs `pnpm add -g` after the split, and if so, implement the original snapshot-reinstall mitigation for that residual set. The residual set's mitigation ships with a manual trigger only.
  5. `npm` itself (non-global invocations) remains hard-blocked until its own subcommand-allowlist decision is made separately — this phase does not resolve that.
  6. Doctor/guard status reporting covers every tool this phase touches (npx, pip, pip3, npm-global) with the same boolean "shim installed" shape `guard_status()` already returns for npm/pip/pip3; per-tool label text in the doctor UI distinguishes "redirected to X" from "blocked".

**Plans**: 5/5 plans executed
Plans:

- [x] 04-01-PLAN.md — `REDIRECTED` mechanism parallel to `BANNED`; npx execs into `pnpm dlx` end to end; pip/pip3 stay hard-blocked with the uv-pip gap recorded (wave 1)
- [x] 04-02-PLAN.md — `volta` as a system-tier registry entry (brew on macOS, official script on Linux) with the shells-out-to-npm finding recorded on it (wave 1)
- [x] 04-03-PLAN.md — argv-conditional global redirect: `npm install -g` / `pnpm add -g` reach `volta install`, everything else keeps today's behaviour, gated on volta being resolvable; the installer's own `kind="node"` install resolves real pnpm by absolute path so the wrapper cannot intercept it (wave 2)
- [x] 04-04-PLAN.md — per-command doctor label text distinguishing "redirected to X" from "blocked", plus the volta tradeoff in the UI copy (wave 3)
- [x] 04-05-PLAN.md — registry-derived pnpm-global snapshot and one-invocation reinstall, exposed as an explicit Doctor remediation for the residual `mmdc` set; widens `run_live` to catch `CommandError`; records R-03's manual-trigger-only scope in REQUIREMENTS.md/ROADMAP.md (wave 4)

### Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer)

**Goal**: `codegraph`, `mmdc`, and the puppeteer/chrome-headless-shell chain mmdc actually depends on all have explicit, researched, correctly-recorded install methods — no tool silently depends on npm/pnpm underneath a method that looks like it doesn't.
**Depends on**: Phase 4's Volta-viability research (mmdc's method decision below draws on the same volta-internals finding Phase 4 produces)
**Requirements**: REQ-codegraph-github-release, REQ-mmdc-install-decision, REQ-puppeteer-catalog-entries
**Success Criteria** (what must be TRUE):

  1. `codegraph` installs via `kind="github_release"`, not `pnpm add -g`.
  2. `mmdc`'s install method (pnpm-with-mitigation, brew, or volta) is decided explicitly after real research — not left ambiguous — with the decision recorded alongside why (postinstall-script security vs. the known pnpm global-install bug), reusing Phase 4's volta-internals research rather than re-deriving it.
  3. `puppeteer` and `chrome-headless-shell` exist as their own catalog entries; `mmdc.requires` includes `puppeteer` so it drags in automatically; whether this dependency applies identically on macOS and Linux is verified, not assumed.

**Note (2026-09-04):** `REQ-pnpm-global-reinstall-mitigation` moved to Phase 4 — it's now resolved there via the Volta redirect (root-cause fix) rather than deferred to this phase's batch-5/7 dependency.
**Note (2026-09-05):** `REQ-pnpm-global-reinstall-mitigation` is Partial: the Volta redirect removes user-typed global installs, Phase 4 ships the snapshot-reinstall mechanism, the audit and a manual trigger only for the residual set, and Phase 12 still owes the automatic post-pnpm-update trigger.

**Planning note (2026-09-05):** Phase 5's research overturned CONTEXT D-01's soft lean toward Homebrew for `mmdc` — upstream mermaid-cli deprecates the brew path and issue #1122 records it failing at runtime — so `mmdc` stays on pnpm. Research also found that `mmdc.requires = ["puppeteer"]` alone satisfies install ORDER but not Node's module resolution, because pnpm isolates each global install invocation; the fix is a new `co_install`/`allow_build` pair on the `kind="node"` method. `chrome-headless-shell` gets no separate entry (puppeteer's own postinstall downloads it), so SC#3's "`puppeteer` and `chrome-headless-shell` exist as their own catalog entries" is satisfied by one entry plus a recorded, test-guarded reason for the other.

**Plans**: 4 plans
Plans:

- [ ] 05-01-PLAN.md — Tracer: container-verified `mmdc` render, then the `co_install`/`allow_build` node-method mechanism in `model.py`/`executors.py` (wave 1)
- [ ] 05-02-PLAN.md — `codegraph` as a checksum-verified `kind="github_release"` entry, with the live GitHub-API verification recorded on it (wave 1)
- [ ] 05-03-PLAN.md — `puppeteer` entry, `mmdc.requires`/`co_install` wiring, and the pnpm-not-brew-not-Volta decision recorded in the registry and PROJECT.md (wave 2)
- [ ] 05-04-PLAN.md — Group-aware pnpm-globals replay, so the Doctor reinstall cannot re-split the `mmdc` + `puppeteer` install group (wave 3)

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
**Scope note (expanded 2026-09-04 discuss-phase)**: The policy is ON by default on macOS (not opt-in), and its detail panel gains a time-of-day picker for the daily `StartCalendarInterval` run (recurrence itself stays fixed at daily — no weekly/custom-interval control this phase).
**Success Criteria** (what must be TRUE):

  1. The Policies view offers a macOS-only toggle that installs/removes a LaunchAgent running the existing prune script daily (`--days 3` default, unchanged script logic/safety checks); the policy is ON by default on a fresh macOS install.
  2. The policy is invisible/inert on Linux.
  3. `fd`/`rg` show as recommended-but-optional; the daemon still runs correctly (via the script's own find/grep fallback) without them.
  4. Scheduled runs write an inspectable log, surfaced via the Policies detail panel for this one policy — no new top-level Diagnostics view.
  5. The policy's detail panel offers a time-of-day picker controlling the LaunchAgent's `StartCalendarInterval` hour/minute; recurrence itself remains fixed at daily.

**Plans**: TBD

### Phase 12: Version-Aware Status & Update Action

**Goal**: The catalog can answer "what's out of date" and act on it through the tool's own real manager, not just "is it installed".
**Depends on**: Nothing structurally. (Note 2026-09-04: `REQ-pnpm-global-reinstall-mitigation` no longer sequences after this phase — it moved to Phase 4, resolved there via a Volta redirect.)
**Note (2026-09-05):** The automatic post-pnpm-update trigger for `REQ-pnpm-global-reinstall-mitigation` lands here, alongside `REQ-update-action-manager-delegation`.
**Requirements**: REQ-version-aware-status-github, REQ-cached-timestamped-version-state, REQ-background-version-refresh-worker, REQ-manager-version-resolution, REQ-update-action-manager-delegation, REQ-manager-drift-alerting
**Success Criteria** (what must be TRUE):

  1. The catalog shows, per `github_release`-kind tool, current version vs. latest available, reusing the existing `resolve_github_tag` resolver.
  2. Version checks are cached with a `checked_at` timestamp; entries older than 7 days show stale and trigger a background re-check, not a full refetch every session.
  3. Version checks run via a Textual `Worker` without blocking first paint or keypresses; network failures degrade to "unknown," never crash.
  4. An "update" action exists and delegates to the tool's actual owning manager (brew/pnpm/uv tool/this installer's own path) — not assumed to always be this installer's executor.
  5. (Stretch, deferred/non-MVP; attempt a minimal version if scope allows per 2026-09-04 discuss-phase) A tool installed via pnpm/npm with a newer version available via brew surfaces a distinct manager-drift alert.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Catalog Tier Foundation | 1/1 | Complete    | 2026-09-04 |
| 2. Tier-Scoped Catalog Views & Recommends | 2/2 | Complete    | 2026-09-05 |
| 3. Install/Uninstall & Tweak Lifecycle Hardening | 3/3 | Complete    | 2026-09-05 |
| 4. npm/npx Ban Extension & Redirect Policy | 5/5 | Complete    | 2026-09-05 |
| 5. Registry Method Corrections (codegraph/mmdc/puppeteer) | 0/4 | Planned | - |
| 6. SDKMAN Hardening & Registry-Authoring Guidelines | 0/TBD | Not started | - |
| 7. System & User Tier Catalog Expansion | 0/TBD | Not started | - |
| 8. AI Tier Catalog Expansion & uv-tool Executor | 0/TBD | Not started | - |
| 9. Postinstall Hooks Mechanism | 0/TBD | Not started | - |
| 10. Agent CLI Ergonomics | 0/TBD | Not started | - |
| 11. Background Maintenance Daemon | 0/TBD | Not started | - |
| 12. Version-Aware Status & Update Action | 0/TBD | Not started | - |
