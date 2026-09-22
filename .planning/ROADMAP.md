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

Phases 13-15 are out-of-batch, post-milestone urgent work discovered by
running the shipped v0.49.0 installer on a real machine — NOT part of the
7-PRD planning batch.

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
- [x] **Phase 5: Registry Method Corrections (codegraph/mmdc/puppeteer)** - Move `codegraph` to `kind="github_release"`, resolve `mmdc`'s install method with real research, and give `puppeteer`/`chrome-headless-shell` their own catalog entries (completed 2026-09-06)
- [x] **Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines** - Verify and harden the already-shipped SDKMAN-exclusivity work, and document the per-tool verification checklist and brew-preference guideline (completed 2026-09-06)
- [x] **Phase 7: System & User Tier Catalog Expansion** - Add zsh, oh-my-zsh, gnu-bash, Apple Containers (system tier) and kitty, wezterm (user tier), with real Linux/Bazzite parity
- [x] **Phase 8: AI Tier Catalog Expansion & uv-tool Executor** - Add the new `uv-tool` executor kind, antigravity, cursor-agent, rtk, and wire `recommends` for agent hosts (completed 2026-09-06)
- [x] **Phase 9: Postinstall Hooks Mechanism** - Add the optional per-tool postinstall field/execution/idempotency mechanism, proven via codegraph's MCP registration (completed 2026-09-06)
- [x] **Phase 10: Agent CLI Ergonomics** - Add `codex-skip`/`opencode-auto` tweaks and a durable, live-verified cursor-agent default-model wrapper (completed 2026-09-06)
- [x] **Phase 11: Background Maintenance Daemon** - Wrap the existing tmpdir-prune script as a toggleable, macOS-only LaunchAgent with visible logs (completed 2026-09-07)
- [x] **Phase 12: Version-Aware Status & Update Action** - Add version-aware status, a cached/staleness-tracked version check, and a manager-delegated update action (unblocks the automatic trigger for REQ-pnpm-global-reinstall-mitigation) (completed 2026-09-07)
- [x] **Phase 13: Live in-TUI Install Execution & Persistent Wizard Settings** - Run installs inside the Textual app via a worker thread with a streaming output widget, headless-capable, and persist/expose the link-mode preference in the TUI instead of re-prompting every run (completed 2026-09-14)
- [x] **Phase 14: Install/Update Engine Correctness & Default-Shell Action** - Fix the silent no-op when confirming install on tools with an available update, and implement the "set zsh as default shell" action (completed 2026-09-14)
- [x] **Phase 15: Catalog Accuracy — Doctor Refresh, Version Parsing, Ownership Attribution, Tier Fixes** - Fix Doctor's stale post-fix guidance, jq-style version-string parsing, wire the existing but disconnected dnf/apt/pacman ownership probes into the live UI, and correct residual tier misclassifications (completed 2026-09-14)

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
  3. `puppeteer` exists as its own catalog entry, and `chrome-headless-shell` is resolved as needing none, with that reason recorded on the entry and guarded by a test; `mmdc.requires` includes `puppeteer` so it drags in automatically; whether this dependency applies identically on macOS and Linux is verified, not assumed. *(Rewritten 2026-09-05 during plan-review convergence: this criterion previously required `puppeteer` AND `chrome-headless-shell` to "exist as their own catalog entries". Phase 5's research established that puppeteer's own `postinstall` (`node install.mjs`) downloads `chrome-headless-shell` into `~/.cache/puppeteer`, so it has no independent install path for a second entry to model — a `chrome-headless-shell` entry could only ever be a decorative duplicate. 05-CONTEXT.md's Claude's-Discretion clause explicitly delegated this call, and plan 05-03 adds a test asserting no such entry exists so the resolution cannot be silently undone. The literal wording is amended here so an end-of-phase verifier reading the numbered criteria in isolation does not register the justified design as a miss.)*

**Note (2026-09-04):** `REQ-pnpm-global-reinstall-mitigation` moved to Phase 4 — it's now resolved there via the Volta redirect (root-cause fix) rather than deferred to this phase's batch-5/7 dependency.
**Note (2026-09-05):** `REQ-pnpm-global-reinstall-mitigation` is Partial: the Volta redirect removes user-typed global installs, Phase 4 ships the snapshot-reinstall mechanism, the audit and a manual trigger only for the residual set, and Phase 12 still owes the automatic post-pnpm-update trigger.

**Planning note (2026-09-05):** Phase 5's research overturned CONTEXT D-01's soft lean toward Homebrew for `mmdc` — upstream mermaid-cli deprecates the brew path and issue #1122 records it failing at runtime — so `mmdc` stays on pnpm. Research also found that `mmdc.requires = ["puppeteer"]` alone satisfies install ORDER but not Node's module resolution, because pnpm isolates each global install invocation; the fix is a new `co_install`/`allow_build` pair on the `kind="node"` method. `chrome-headless-shell` gets no separate entry (puppeteer's own postinstall downloads it), so SC#3's "`puppeteer` and `chrome-headless-shell` exist as their own catalog entries" is satisfied by one entry plus a recorded, test-guarded reason for the other.

**Plans**: 4 plans
Plans:

- [x] 05-01-PLAN.md — Tracer: container-verified `mmdc` render plus the brownfield gap, its remedy and the missing-shared-library case, then the `co_install`/`allow_build`/`versions`/`min_node`/`smoke` node-method mechanism with its fail-closed pnpm/node version preflight and its post-install browser check in `model.py`/`executors.py`/`versions.py` (wave 1)
- [x] 05-02-PLAN.md — `codegraph` as a checksum-verified `kind="github_release"` entry, with the live GitHub-API verification recorded on it and the tier tripwire moved (wave 2)
- [x] 05-03-PLAN.md — `puppeteer` entry with platform-conditional methods (Linux arm64 gated off), `mmdc.requires`/`co_install` wiring, and the pnpm-not-brew-not-Volta decision recorded in the registry and PROJECT.md (wave 3)
- [x] 05-04-PLAN.md — Group-aware, pin-aware pnpm-globals replay, so the Doctor reinstall cannot re-split the `mmdc` + `puppeteer` install group and instead repairs a brownfield split — plus Doctor detection that TELLS an affected user their group is split and which key repairs it (wave 4)

**Planning note (2026-09-05, cross-AI review cycle 2):** the plans were revised again after a second review round (19 → 8 open concerns). Three HIGH concerns drove real scope: (1) a brownfield machine was never routed to the fix, so 05-04 now detects a split install group in the Doctor's existing pnpm-globals audit and reports it on both the console and TUI paths; (2) Linux amd64 could still report a successful install of a puppeteer whose browser cannot start, so the `kind="node"` method gains a `smoke` param naming one code-owned post-install check that runs the downloaded browser and fails the install when it cannot start; (3) the persistent `--allow-build` grant was described as bounded by this project's `^25` pin — it is not, the grant is package-level and name-keyed, and every plan now states that accurately with a test forbidding the retracted wording from reaching committed registry text.

**Replan note (2026-09-05, cross-AI review cycle 1):** all four plans were revised in place against `05-REVIEWS.md`. Six changes are worth recording at roadmap level because they change what the phase ships, not merely how it is described. (1) `puppeteer`'s Linux method now declares `arch = ["amd64"]`: Chrome publishes no Linux arm64 binary, and `installer/engine.py` reports INSTALLED on any pnpm exit 0, so the previous unscoped method advertised a successful install of a tool that provably cannot render there. `installer/deps.py` now skips `puppeteer` and `mmdc` on Linux arm64 with an unavailable-dependency warning, through existing mechanisms only — this also makes D-03's literal "platform-conditional methods" true rather than a recorded deviation. (2) A registry-declared `versions` pin (`puppeteer = "^25"`) bounds the install to mmdc's own peerDependency ceiling; unpinned, the phase's whole mechanism would silently break the day puppeteer 26 ships. (3) A fail-closed runtime preflight refuses the comma-group form below pnpm 11.0.0, `--allow-build` below pnpm 10.4.0, and the install below a declared `min_node`; the catalog's `pnpm` entry has no version floor and the executor previously checked only that pnpm existed. (4) `--allow-build` is now documented everywhere as a PERSISTENT package-level trust grant (pnpm writes it into its build-allowance config), not an invocation-scoped one; the three threat registers are corrected and the residual risk is explicitly accepted. (5) The brownfield case — a machine with `mmdc` already installed never reaches the grouped invocation, because `install_tool` returns `ALREADY_INSTALLED` — is measured in the Tier-3 container, recorded on the registry entry, and remedied by 05-04's replay, which the same container run proves repairs it. (6) `test_registry_tier_distribution_is_pinned` is updated by 05-02 (`ai` 9→10) and 05-03 (`user` 35→36) in the commits that earn it. `.planning/REQUIREMENTS.md`'s `REQ-puppeteer-catalog-entries` is amended in place so its `chrome-headless-shell` wording agrees with SC#3's already-amended text.

**Wave note (2026-09-05, plan-review convergence):** 05-02 was originally wave 1 alongside 05-01. The two share no `files_modified`, but CLAUDE.md requires the repo-wide `make validate && make test` on the exact tree before every commit, and both plans spend most of their execution in a TDD red phase — so run in parallel in one tree, each plan's mandatory gate would intermittently fail on the other's in-flight failing tests with no clean attribution. 05-02 now depends on 05-01, and 05-03/05-04 shift to waves 3 and 4 accordingly. The phase runs fully sequentially.

### Phase 6: SDKMAN Hardening & Registry-Authoring Guidelines

**Goal**: The SDKMAN-exclusivity work that shipped ahead of GSD's own process (commit `0e05f50`) gets the verification/hardening pass it skipped, and the registry-authoring discipline this whole PRD batch leans on is actually written down.
**Depends on**: Nothing — independent of Phases 1-5
**Requirements**: REQ-sdkman-exclusivity, REQ-registry-authoring-verification-checklist, REQ-brew-preference-guideline
**Success Criteria** (what must be TRUE):

  1. `java`/`gradle`/`maven`/`groovy`/`springbootcli` are confirmed installing exclusively through SDKMAN with real (not just unit-level) verification, including a non-interactive end-to-end check of `sdk install java` on an unconfigured machine.
  2. Whether `java`'s SDKMAN candidate needs a pinned `version` to avoid an interactive prompt is resolved, not left as an open question.
  3. A documented, mandatory per-tool per-OS verification step exists for future registry additions, with a defined recording mechanism.
  4. "Prefer brew over other userspace package managers, except SDKMAN for the Java toolchain" is written down as a registry-authoring guideline.

**Plans**: 1 plan
Plans:

- [x] 06-01-PLAN.md — Fresh Tier-3 verification of `sdk install java` (no pin needed) recorded as a guarded registry comment; the two registry-authoring guidelines (D-01 verification checklist, D-02 brew-preference) written into `.claude/architecture.md`

### Phase 7: System & User Tier Catalog Expansion

**Goal**: The system-tier prerequisites the user actually starts a fresh machine from (shell, shell framework, container runtime) and the terminal emulators they pick personally both exist in the catalog with verified, per-platform install methods.
**Depends on**: Phase 1 (needs `tier` field to exist) and Phase 4-6's registry-authoring verification checklist (REQ-registry-authoring-verification-checklist) as the discipline this phase's new entries must follow
**Requirements**: REQ-system-tier-shell-container-entries, REQ-terminal-emulator-entries, REQ-linux-bazzite-shell-parity
**Success Criteria** (what must be TRUE):

  1. `zsh`, `oh-my-zsh`, `gnu-bash` (macOS), Apple Containers (macOS) install cleanly via verified live methods; `oh-my-zsh`'s actual `.zshrc`-rewriting behavior has been read and confirmed safe as a `kind="script"` candidate before being treated as one.
  2. `kitty`, `wezterm` install cleanly on macOS (brew) with a verified Linux path (distro package or GitHub-release download).
  3. `zsh`/`oh-my-zsh` have a working Linux/Bazzite install path; the existing `podman` entry (not a new one) is the container-runtime story there.
  4. Whether Apple Containers needs an actual install step on a current macOS, or is a pure version-gate/doc entry, is resolved and recorded.

**Plans**: 3 plans
Plans:

- [x] 07-01-PLAN.md — `zsh` + `oh-my-zsh` system-tier entries, Tier-3-verified `.zshrc` rewrite safety, Bazzite parity via the existing `podman` entry (wave 1)
- [x] 07-02-PLAN.md — `gnu-bash` (with a same-named-binary detection fix) + Apple Containers system-tier entries, D-01's disabled-state resolution recorded in architecture.md (wave 2, needs 07-01)
- [x] 07-03-PLAN.md — `kitty` + `wezterm` user-tier terminal-emulator entries (new `terminal` category), kitty's accepted Bazzite gap, wezterm's checksum-verified AppImage fallback, phase decision consolidation (wave 3, needs 07-02)

### Phase 8: AI Tier Catalog Expansion & uv-tool Executor

**Goal**: The agent-facing tools this project exists to serve — including the new `uv-tool` installer kind `graphify` needs — are in the catalog with verified install methods, and selecting an agent host surfaces its recommended companion tools.
**Depends on**: Phase 1 (tier field), Phase 2 (`recommends` mechanism must exist to be wired here)
**Requirements**: REQ-uv-tool-executor, REQ-agent-host-entries, REQ-rtk-github-release, REQ-recommends-wiring-agent-hosts
**Success Criteria** (what must be TRUE):

  1. `installer/executors.py` has a working `kind="uv-tool"` executor (`uv tool install <pkg>`); `graphify` installs via it using the PyPI package `graphifyy`.
  2. `antigravity` and `cursor-agent` install via a verified official method (not assumed) — both are live-fetched, vendor-provided curl|bash install scripts, confirmed by 08-RESEARCH.md's 2026-09-06 research pass. *(Amended during planning: the original text flagged this as unresolved pending research; that research is now complete — see 08-02-PLAN.md.)*
  3. `rtk` installs via `kind="github_release"` from `rtk-ai/rtk`, checksum-verified against its release's `checksums.txt`.
  4. Selecting `claude`/`opencode`/`codex`/`cursor-agent` surfaces its `recommends` list (`codegraph`, `graphify`, `rtk`) via the Phase 2 mechanism, without auto-installing anything. *(Amended during planning: the original text also named `antigravity` here, but 08-CONTEXT.md's locked D-01 explicitly excludes `antigravity` from this phase's `recommends` wiring — "You can deio antigravity for now" — deferred until its own companion-tool ecosystem is better understood, not dropped. This criterion is narrowed to the four hosts D-01 actually wires; see 08-04-PLAN.md.)*

**Plans**: 4 plans
Plans:

- [x] 08-01-PLAN.md — `uv-tool` executor + resolver wiring, `graphifyy`'s legitimacy gate, and `graphify`'s registry entry, wired end-to-end (wave 1)
- [x] 08-02-PLAN.md — `cursor-agent` and `antigravity` registry entries via their verified official vendor scripts (wave 2, needs 08-01)
- [x] 08-03-PLAN.md — `rtk` registry entry: checksum-verified `github_release` ladder with an arch-gated Linux split and a brew fallback (wave 3, needs 08-02)
- [x] 08-04-PLAN.md — Real per-host `recommends` wiring (`claude`/`opencode`/`codex`/`cursor-agent`) and Phase 8 decision consolidation (wave 4, needs 08-03)

### Phase 9: Postinstall Hooks Mechanism

**Goal**: A catalog tool can declare a one-time, non-interactive follow-up action that runs immediately after its own successful install, proven end-to-end via codegraph's MCP registration for whichever agent hosts are already present.
**Depends on**: Phase 8 (codegraph must exist in the registry as the proving case)
**Requirements**: REQ-postinstall-field, REQ-postinstall-execution-timing, REQ-postinstall-idempotency-live-check, REQ-postinstall-noninteractive-only, REQ-codegraph-mcp-postinstall
**Success Criteria** (what must be TRUE):

  1. A tool can declare an optional `postinstall` command in the registry — inline, a `postinstall_script` file, or a closed dispatch-hook name for the case where the invocation depends on live machine state (see REQ-postinstall-field, amended during Phase 9 implementation) — it runs exactly once per successful install, immediately after the specific `Method` that succeeded.
  2. A postinstall failure is visible to the user but never marks the tool's own install as failed.
  3. Idempotency is a live check ("is the effect already present"), with no new state-tracking database anywhere in the codebase.
  4. A tool whose only setup path is interactive is not wired to this mechanism at all.
  5. After installing `codegraph`, its MCP server registers for every already-installed agent host (`claude`/`codex`/`opencode`/`cursor-agent`), and cleanly no-ops when none are installed.

**Plans**: 2/2 plans executed
Plans:

- [x] 09-01-PLAN.md — The postinstall mechanism wired end-to-end via codegraph's real MCP-registration hook: `Tool.postinstall`, the closed dispatch table, `InstallOutcome.postinstall_warning`, and the never-`--target auto` host-presence CSV composition (wave 1)
- [x] 09-02-PLAN.md — Tier-3 container verification of the real `codegraph` install plus its postinstall hook, and Phase 9 decision consolidation into `.claude/architecture.md`/`.planning/PROJECT.md` (wave 2, needs 09-01)

### Phase 10: Agent CLI Ergonomics

**Goal**: `codex` and `opencode` get the same permissive-mode convenience `claude-skip` already provides, honestly labeled per their real (differing) semantics, and `cursor-agent` reliably gets a known-good default model on any bare invocation instead of silently inheriting whatever was last selected elsewhere.
**Depends on**: Nothing — extends the existing `TweakBundle`/`tweak_policy` mechanism, independent of Phases 1-9
**Requirements**: REQ-codex-skip-tweak, REQ-opencode-auto-tweak, REQ-cursor-agent-default-model-wrapper, REQ-agent-tweak-self-update-durability
**Success Criteria** (what must be TRUE):

  1. `codex-skip` aliases `codex` to its verified real bypass-permissions flag, with user-supplied flags always respected.
  2. `opencode-auto` aliases `opencode` to `opencode --auto`, with Policies detail-panel copy that accurately describes its narrower (not full-bypass) semantic.
  3. Invoking `cursor-agent`/`cursor` with no `--model` injects a live-verified, plain model slug (no bracket syntax); passing an explicit `--model` is never overridden.
  4. All three tweaks survive the target CLI self-updating in place (durable by construction — shell alias/function lookup precedes PATH search).

**Plans**: 1/1 plans executed
Plans:

- [x] 10-01-PLAN.md — `codex-skip` + `opencode-auto` plain-alias tweaks and the `cursor-agent`/`cursor` conditional-injection default-model wrapper, all three wired through the existing `TweakBundle`/`tweak_policy` mechanism (wave 1)

### Phase 11: Background Maintenance Daemon

**Goal**: The existing, already-safe `scripts/prune-user-tmpdir.sh` becomes a set-and-forget background policy, toggleable the same way every other Policies entry already is, with a real audit trail instead of silent background deletion.
**Depends on**: Nothing — new `daemon_policy` factory parallel to existing `Policy` factories, independent of Phases 1-10
**Requirements**: REQ-launchd-prune-policy, REQ-daemon-log-diagnostics, REQ-daemon-dependency-gating
**Scope note (expanded 2026-09-04 discuss-phase)**: The policy is ON by default on macOS (not opt-in), and its detail panel gains a time-of-day picker for the daily `StartCalendarInterval` run (recurrence itself stays fixed at daily — no weekly/custom-interval control this phase).
**Success Criteria** (what must be TRUE):

  1. The Policies view offers a macOS-only toggle that installs/removes a LaunchAgent running the existing prune script daily (`--days 3` default, unchanged script logic/safety checks); the policy is ON by default on a fresh macOS install.
  2. The policy is invisible/inert on Linux. *(SUPERSEDED by Phase 15.7 decision D-01a: Linux gains its own systemd-timer daemon policy, on by default exactly like macOS, gated on `systemctl` being present. This criterion records what Phase 11 shipped; it is no longer the intended behavior.)*
  3. `fd`/`rg` show as recommended-but-optional; the daemon still runs correctly (via the script's own find/grep fallback) without them.
  4. Scheduled runs write an inspectable log, surfaced via the Policies detail panel for this one policy — no new top-level Diagnostics view.
  5. The policy's detail panel offers a time-of-day picker controlling the LaunchAgent's `StartCalendarInterval` hour/minute; recurrence itself remains fixed at daily.

**Plans**: 4 plans
Plans:

- [x] 11-01-PLAN.md — `installer/daemon.py` core mechanism: plist generation/parsing, real `launchctl bootstrap`/`bootout` round trip, the log-writing wrapper + truncation, the "decided" ownership marker (wave 1)
- [x] 11-02-PLAN.md — `Policy.hard_requires`/`log_path`/`set_schedule` fields, the `action_toggle_policy` gate fix, and the `daemon_policy` factory (wave 2, needs 11-01)
- [x] 11-03-PLAN.md — Policies detail-panel UI: "last run" line, log-view toggle, and the `TimePickerScreen` time-of-day picker (wave 3, needs 11-02)
- [x] 11-04-PLAN.md — `setup.py` composition-root wiring: macOS-only gating and on-by-default via `ensure_daemon_default`/`UnifiedApp.on_mount` (wave 4, needs 11-03)

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
  5. (Stretch, deferred/non-MVP; attempt a minimal version if scope allows per 2026-09-04 discuss-phase) A tool installed via pnpm/npm with a newer version available via brew surfaces a distinct manager-drift alert. *(Amended 2026-09-07: this criterion was not delivered in Phase 12. `brew outdated` lists only already-installed formulae and casks, so it cannot observe an uninstalled brew alternative; zero registry rows declare both a node/uv-tool method and a brew/cask method (12-RESEARCH.md section 6); and shipping the helper unwired would violate `.claude/architecture.md` rule 5. 12-CONTEXT.md D-02's "planner's call" clause authorized the deferral. Recorded in `.planning/REQUIREMENTS.md` so an end-of-phase verifier reading the numbered criteria in isolation does not register a silent miss.)*

**Plans**: 4 plans
Plans:

- [x] 12-01-PLAN.md — Tracer: end-to-end version status for `codegraph` (`versions.py` full-output probe and a precision-preserving status comparator / `atomic.py` extracted from `omz.py` and `daemon.py` / `version_cache.py` with timezone-validated timestamps / `version_status.py`) wired from `setup.py`'s composition root through `UnifiedApp` into `catalog_tui.CatalogScreen`'s background Worker and a new "Ver" column, then generalized to every `github_release` tool with fresh-cache reconstruction and bounded failed-attempt retry (wave 1)
- [x] 12-02-PLAN.md — `installer/ownership.py` (ownership as a concept distinct from `resolve_methods`' install-preference ranking, resolved from installer-artifact presence + real manager inventories + live PATH attribution, asserted only on an active-path match or complete negative evidence and otherwise `unknown` with a recorded reason), `installer/run.py::run_query` (one bounded runner with env merging and accepted exit codes), `installer/manager_versions.py` (one batched outdated query per manager, preserving current AND latest, fail-closed on malformed uv output), and a timestamped manager-report snapshot in `installer/version_cache.py` so a fresh session issues zero manager subprocesses (wave 2, needs 12-01)
- [x] 12-03-PLAN.md — Ownership-first manager-delegated "update" action (`installer/update.py`) gated on mutation-grade ownership evidence, pnpm-owned tools updated through the existing `_node` executor rather than a `pnpm update -g` argv, update-safe staged/atomic executors with a full rollback state machine (`download.update_download`, `apps.update_app`), an explicit in-flight guard, full domain-exception containment, postinstall re-dispatch, the `u` action registered in `installer/ui_common.py`'s single view registry, epoch coordination between refresh and update, and the automatic post-pnpm-self-update `reinstall_node_globals` trigger replaying a snapshot captured BEFORE the update (wave 3, needs 12-01/12-02)
- [x] 12-04-PLAN.md — REQ-manager-drift-alerting deferral record + Phase 12 decision consolidation into `.claude/architecture.md` (wave 4, needs 12-03)

**Replan note (2026-09-07, cross-AI review cycle 2):** cycle 2 confirmed the cycle-1 fixes below genuinely landed ("not merely papering them over") but returned "revision required, risk HIGH" again on four new findings, all in the mutating half of the phase. All four are now closed with mechanisms, not acknowledgements. (1) **The pnpm-globals snapshot is captured BEFORE the update, not after.** The previous ordering ran `perform_update` first — so if the pnpm self-update is the event that loses the globals, the snapshot was already empty, and `reinstall_node_globals` returns immediately for an empty list, making the whole mitigation a silent no-op. `UpdateService.run` now captures, mutates, then replays the pre-captured tuple, with a test whose fake update empties the live list mid-run. (2) **Ownership is asserted only on complete evidence.** A single positive candidate is no longer enough: the resolver requires either that the executable PATH actually resolves is attributable to that candidate, or that every competing manager's inventory was read successfully and did not claim it — otherwise `unknown`. `plan_uninstall` proves an artifact exists, never that it is the live copy, so a stale `~/.local` artifact beside an unreadable brew inventory and an active `/opt/homebrew/bin/rg` now resolves `unknown` rather than being overwritten by this installer. `ManagerOwnership` carries the evidence (`candidates`, `active_candidate`, `active_path`, `unknown_reason`), the UI renders it, and `MUTATION_GRADE` is the one place the permitted confidence values live. The arbitrary fixed-order tiebreak is deleted. (3) **A pnpm-owned tool is updated through the existing `_node` executor, never a `pnpm update -g` argv.** Plain `pnpm update` respects the package's declared range and would not reach the version the outdated report advertises (12-RESEARCH.md's own live report shows current==wanted==11.9.0 against latest==12.3.4); `--latest` would reach it but discard this project's registry pins; and either bare argv bypasses `_node`'s co-install grouping, `--allow-build` allowances, minimum-pnpm/minimum-Node floors, and smoke check, which `mmdc` and `puppeteer` — the registry's only node-kind tools — all depend on. Reusing the install executor makes update and install incapable of drifting apart, and a registry-pinned package now surfaces its pin in the UI so a row that stays outdated after a successful update is explained. (4) **The 7-day cache now covers manager queries.** The brew/pnpm/uv inventory and outdated reports are persisted as one timestamped snapshot in the same `versions.json`, reusing the GitHub entry's staleness model, so a fresh session or a burst of tier navigation issues zero manager subprocesses; every mutation this app performs calls `VersionRefreshService.invalidate`, which drops that snapshot and bumps a shared status epoch. Also closed: the update rollback is now one state machine covering aside-move, swap, symlink recreation, validation, and interrupted-run remnants rather than only the second `os.replace`; the `u` action is registered in `installer/ui_common.py`'s `VIEWS` table per rule 1, not only in `CatalogScreen.BINDINGS`; the epoch stops a refresh started before an update from overwriting the post-update row; the update-status comparison uses a new parser that keeps every numeric component and orders prereleases individually (the existing `parse_version` feature-floor contract is untouched); cache timestamps must be timezone-aware, are normalized to UTC, and an implausible future value is treated as stale; the uv outdated parser fails closed to `unknown` on unrecognized output instead of reporting a clean map; the cache-concurrency guarantee and its test are restated at the real single-service production topology with a unique atomic-write temp name; and 12-04's orphan-helper guard names the two specific abandoned identifiers rather than banning the substring `drift` codebase-wide. Found while grounding this replan and also fixed: `installer/daemon.py` held a third copy of the atomic-write pattern, so 12-01's "exactly one implementation" extraction now covers it too.

**Replan note (2026-09-07, cross-AI review cycle 1):** all four plans were rewritten against `12-REVIEWS.md`, which returned "revision required, risk HIGH" on every one of them. Five changes are worth recording at roadmap level because they change what the phase ships, not merely how it is described. (1) **Ownership is now a real, separate, tested concept** (`installer/ownership.py`, plan 12-02) resolved from installer-artifact presence (`uninstall.plan_uninstall`) and real manager inventory membership (`brew list --versions`, `pnpm list -g --json`, `uv tool list`). The original plans treated `resolve_methods(tool, platform)[0]` as "the manager that installed the tool"; it is only the `_RANK` install-preference ladder, so a brew-installed `rg` — which declares `github_release` at rank 20 ahead of `brew` at rank 40 — would have been queried, and then UPGRADED, as a GitHub download into `~/.local/bin`, silently changing ownership and PATH precedence. An unreadable inventory now fails closed to `unknown`, and the mutating update action refuses to act on `unknown`. (2) **Manager queries are batched once per manager per refresh**, not once per stale tool, and preserve both current and latest (`ManagerVersion`), so GUI casks with no command to probe and binaries shadowed by another manager both report correctly; `brew outdated --json=v2` covers formulae and casks in one call (verified 2026-09-07 via `brew help outdated`), kept in two separate namespaces so a shared name cannot collide. One bounded runner, `installer/run.py::run_query`, carries environment merging, pnpm's accepted `{0, 1}` exit codes, and a timeout. (3) **The update path is failure-safe**: `download.update_download` and `apps.update_app` stage, validate, replace with `os.replace`, and keep the prior installation until the replacement is confirmed — the install-side executors write directly over a live executable, extract into a live opt directory, and move into `~/Applications` with no replace-safety. (4) **The TUI can no longer be crashed or double-triggered by this feature**: every domain exception is contained behind a typed `UpdateOutcome`, workers declare `exit_on_error=False` with a `finally` post, and an explicit lock-guarded in-flight guard blocks a second update, because `exclusive=True` cannot stop a thread already inside `subprocess.run`. The pnpm-globals replay is narrowed to a pnpm SELF-update, matching REQ-pnpm-global-reinstall-mitigation's own wording, and declared postinstall hooks are re-dispatched after a successful update so an updated `codegraph` keeps its MCP registration. (5) **SC#5 (manager-drift alerting) will not be delivered by this phase.** `brew outdated` lists only already-installed formulae and casks, so it structurally cannot detect an uninstalled brew alternative to a pnpm-managed tool; zero registry rows declare both a `node`/`uv-tool` and a `brew`/`cask` method; and the original plan's own "not wired into the status loop" scope would have shipped a zero-caller production helper, which `.claude/architecture.md` rule 5 forbids. Plan 12-04 amends SC#5 in place and records the deferral in `.planning/REQUIREMENTS.md` and `.planning/PROJECT.md`, per 12-CONTEXT.md D-02's explicit "planner's call" clause. Also corrected: `CatalogScreen` lives in `installer/catalog_tui.py`, not `wizard_app.py`; `setup.py` is the composition root that owns the real `Platform` and is now in 12-01's and 12-03's file lists; `TagResolver` is `Callable[[str], str]` and is called with one argument; and `probe_version`'s pinned first-line contract is left alone in favour of a new full-output sibling probe.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Catalog Tier Foundation | 1/1 | Complete    | 2026-09-04 |
| 2. Tier-Scoped Catalog Views & Recommends | 2/2 | Complete    | 2026-09-05 |
| 3. Install/Uninstall & Tweak Lifecycle Hardening | 3/3 | Complete    | 2026-09-05 |
| 4. npm/npx Ban Extension & Redirect Policy | 5/5 | Complete    | 2026-09-05 |
| 5. Registry Method Corrections (codegraph/mmdc/puppeteer) | 4/4 | Complete    | 2026-09-05 |
| 6. SDKMAN Hardening & Registry-Authoring Guidelines | 1/1 | Complete    | 2026-09-06 |
| 7. System & User Tier Catalog Expansion | 3/3 | Complete    | 2026-09-06 |
| 8. AI Tier Catalog Expansion & uv-tool Executor | 4/4 | Complete    | 2026-09-06 |
| 9. Postinstall Hooks Mechanism | 2/2 | Complete    | 2026-09-06 |
| 10. Agent CLI Ergonomics | 1/1 | Complete    | 2026-09-06 |
| 11. Background Maintenance Daemon | 4/4 | Complete    | 2026-09-07 |
| 12. Version-Aware Status & Update Action | 4/4 | Complete    | 2026-09-07 |

### Phase 12.4: Tool Onboarding Research Skill and Registry Postinstall Audit: build a repeatable research checklist/skill for onboarding any new catalog tool (tier classification, dependency tree, postinstall/setup-per-agent-harness needs), use it to close the confirmed rtk/graphify postinstall gap (Phase 8 research documented rtk init -g/--claude/--opencode/--codex/--agent-cursor and graphify's per-host setup, never wired into installer/postinstall.py), and audit every other registry.toml entry against the same checklist for similar research-to-implementation gaps (INSERTED)

**Goal:** A repeatable, checklist-and-skill-driven onboarding process exists for any future
`registry.toml` addition (tier classification, dependency-tree declaration, postinstall/setup-
per-agent-harness classification); the confirmed rtk/graphify postinstall gap (researched in Phase
8, never wired into `installer/postinstall.py`) is closed via the same non-interactive per-host
mechanism `codegraph` already proves; and every one of the ~89 other `registry.toml` entries has
been checked against that same checklist for a similar research-to-implementation gap.
**Requirements**: D-01, D-01a, D-02, D-03, D-04 (12.4-CONTEXT.md locked decisions — this inserted
phase has no `REQUIREMENTS.md` entries of its own, same convention as Phases 12.1-12.3)
**Depends on:** Phase 12
**Plans:** 4/4 plans complete

Plans:

- [x] 12.4-01-PLAN.md — Tracer: D-03 shared `present_agent_hosts()` helper (extracted from
  codegraph's hook) + rtk's simplest host (`claude`) wired end-to-end, live-proven against a fresh
  v0.49.0 binary, then expanded to `opencode`/`codex`/`cursor-agent` with a live re-verification of
  the cursor-implies-claude write risk (wave 1)
- [x] 12.4-02-PLAN.md — `_graphify_register()` for all four agent hosts, reusing the D-03 helper,
  plus live adversarial merge-safety verification for the three hosts research left untested (wave
  2, needs 12.4-01)
- [x] 12.4-03-PLAN.md — D-01 checklist extension in `.claude/architecture.md` (tier/dependency/
  postinstall-mechanism decision tree) and the new `.claude/skills/tool-onboarding/SKILL.md` (wave
  2, needs 12.4-01)
- [x] 12.4-04-PLAN.md — D-04 full-catalog audit (all 89 entries) producing `12.4-AUDIT.md`, decision
  consolidation into `PROJECT.md`/`architecture.md`, final `make validate && make test` (wave 3,
  needs 12.4-02, 12.4-03)

### Phase 12.3: Container E2E Verification of the Reconciled Branch: real end-to-end run of the reconciled installer inside a container to confirm origin's ported architecture, local's ported subsystems (host_setup/skill_lifecycle, ownership/skill-lifecycle registry fields, remapped tool tiers), and the 11 re-added registry rows all work together live, not just under unit tests (INSERTED)

**Goal:** A real, disposable, Fedora-family container proves the reconciled
branch's full `registry.toml` catalog (~90+ tools) installs, reinstalls, and
uninstalls correctly end to end — origin's ported architecture, local's
ported subsystems, and all 11 re-added registry rows working together live,
not just under mocked unit tests — using a reusable, OS/arch-aware
container-tool detection mechanism that never silently falls back to
mutating this host machine.
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06 (12.3-CONTEXT.md locked
decisions — this inserted verification phase has no `REQUIREMENTS.md`
entries of its own)
**Depends on:** Phase 12
**Plans:** 4/4 plans complete

Plans:

- [x] 12.3-01-PLAN.md — Tracer: OS/arch-aware container-tool detection script
  (`scripts/detect-container-runtime.sh`), the D-03 no-silent-fallback gate,
  and one real tool (`wezterm`) installed end-to-end inside a disposable
  Fedora container through the production `install_tool` path (wave 1)
- [x] 12.3-02-PLAN.md — Fedora-family harness: non-root Homebrew+uv-capable
  container bootstrap, then Pass 1 — clean install of the full ~90-tool
  catalog via the real `uv run setup.py --all --yes` entrypoint (wave 2,
  needs 12.3-01)
- [x] 12.3-03-PLAN.md — Pass 2 — install/uninstall/reinstall rerun over the
  already-installed container, teardown, and a whole-run host-untouched
  attestation (wave 3, needs 12.3-02)
- [x] 12.3-04-PLAN.md — D-06 evidence consolidation: this phase's Tier-3
  evidence folded into `.planning/RUN-REPORT.md`, decisions recorded in
  `.planning/PROJECT.md` and `.claude/architecture.md`, final
  `make validate && make test` (wave 4, needs 12.3-03)

### Phase 12.2: Install-Actions and Agent-Policy UI Wiring Decision: decide whether local's ported install_actions.py (multi-hook post_install) and agent_policy.py (permission auditing) get surfaced in origin's Textual UI, where, and whether they duplicate/conflict with origin's own omz.py/daemon.py/update.py flows (INSERTED)

**Goal:** Retire `installer/install_actions.py` entirely — origin's `installer/omz.py`/
`installer/daemon.py`/`installer/executors.py` already cover, with more review cycles behind
them, the "managed setup" cases it used to serve — and leave `installer/agent_policy.py` (plus
`agent_env.py`/`agent_guidance.py`) dormant with no code change, since origin has no equivalent
mechanism yet and wiring it now risks throwaway work ahead of the recorded `../ai-kit` migration
backlog item. `make validate && make test` confirm zero regression from the removal.
**Requirements**: D-01, D-01a, D-02, D-02a, D-04 (12.2-CONTEXT.md locked decisions — this
inserted verification phase has no `REQUIREMENTS.md` entries of its own; D-03 is explicitly not
applicable, since neither module is wired into the UI this phase)
**Depends on:** Phase 12
**Plans:** 1/1 plans complete

Plans:

- [x] 12.2-01-PLAN.md — Delete `installer/install_actions.py` + its test and the 3 dangling
  comment references left behind (D-01, D-01a, D-02, D-02a, tracer); run
  `make validate && make test` to confirm no orphaned import, dead-code, or coverage-floor
  regression (D-04)

### Phase 12.1: Reconciliation Merge Verification: confirm the layered merge of origin's 12-phase GSD work (b9a8876) with local's independent line (985f602) on branch recon/tui-interaction-consistency-2026-09-07 is architecturally sound, not just green on make validate/test (INSERTED)

**Goal:** Confirm the layered merge on `recon/tui-interaction-consistency-2026-09-07` (origin's
12-phase GSD milestone `b9a8876` adopted as base, plus local's independent line's unique
subsystems ported on top from `985f602`) is architecturally sound: a fully green test suite with
no known pre-existing failures, every re-added registry row individually audited against real
tier semantics, the two ported-but-unwired local subsystems confirmed structurally inert without
new wiring, and a real-terminal TUI smoke walkthrough proving all six views render correctly
with zero real-machine mutation.
**Requirements**: D-01, D-02, D-03, D-04 (12.1-CONTEXT.md locked decisions — this inserted
verification phase has no `REQUIREMENTS.md` entries of its own)
**Depends on:** Phase 12
**Plans:** 1/1 plans complete

Plans:

- [x] 12.1-01-PLAN.md — Fix the one confirmed pre-existing failing test (D-03, tracer); codify
  the 11-row tier remapping audit as a permanent regression test (D-02); static import-graph
  audit of the two ported-but-unwired local subsystems plus a real-terminal tmux structural
  smoke walkthrough of all six views (D-01, D-04)

### Phase 13: Live in-TUI install execution & persistent wizard settings: install execution (confirm, run commands, wire PATH, verify) has always dropped out of the Textual TUI to plain console -- the in-TUI live-execution design was explicitly deferred in unified-ui-redesign-v1.0-prd.md and never built. Implement it: run installs inside the app via a worker thread with a streaming output widget, and make the whole flow genuinely headless-capable via the existing --all/--categories/--yes/--link-mode flags for unattended runs. Separately, the link-mode (centralized/single/split) prompt re-asks every run with no persisted preference and no in-UI control to change it later (setup.py's _resolve_link_mode always prompts; no settings file exists; no screen in wizard_app.py exposes it) -- persist the first choice and surface it as an adjustable setting inside the TUI, ideally as part of the same first-run wizard rather than a separate pre-TUI CLI prompt. (INSERTED)

**Goal:** Install execution — confirm, run, wire PATH, verify — happens inside the Textual app, with each child process's output streaming live into a log widget attributed to the tool that produced it, while the link-mode preference is asked once inside that app, persisted, and adjustable afterwards from the Policies view.
**Requirements**: D-01, D-02, D-03, D-04, D-05 (13-CONTEXT.md decision ids — this inserted phase has no REQUIREMENTS.md traceability ids)
**Depends on:** Phase 12
**Plans:** 7/7 plans complete

Plans:
**Wave 1**

- [x] 13-01-PLAN.md — Wave 0: prove the worker-to-modal mechanism and record it in 13-VALIDATION.md
- [x] 13-02-PLAN.md — StreamingRunner and a between-tools cancel predicate for run_installs (pure core)
- [x] 13-03-PLAN.md — installer/settings.py: persisted, validated link-mode preference (pure core)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 13-04-PLAN.md — Tracer: one tool installs end-to-end inside the app, plus the setup.py seam split

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 13-05-PLAN.md — Checksum-mismatch modal, per-tool status list, cancel, and the full post-run report

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 13-06-PLAN.md — Settings wiring: no pre-TUI prompt, a Policies link-mode picker, live re-reads

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 13-07-PLAN.md — architecture.md and PRD record, plus the full-suite phase gate

### Phase 14: Install/update engine correctness & default-shell action: selecting tools that show an available update and confirming install silently does nothing because resolve_dependencies (installer/deps.py) and engine.py's ALREADY_INSTALLED short-circuit skip any tool that is merely present, regardless of outdated status, with no notice explaining why -- the only real update path today is the separate, disconnected per-row 'u' keybind (action_update_tool); unify or clearly bridge these two paths so selecting an outdated tool in the main select+enter flow actually updates it (or explicitly tells the user it won't, and why). Separately, 'set as default shell' (set_login_shell) is unimplemented scaffolding -- validated in installer/model.py's schema, dispatched nowhere, no tool declares it -- implement it carefully: oh-my-zsh's registry entry deliberately disables auto-chsh (CHSH=no) for a documented Bazzite/KDE-SDDM login-failure bug (ublue-os/bazzite#4159) that any implementation must keep guarded, e.g. an explicit confirm step and never automatic on immutable/atomic distros (INSERTED)

**Goal:** Selecting a tool the catalog shows as outdated and pressing enter actually updates it through the same update service the per-row `u` keybind uses — or says, in the post-run summary and in that keybind's own words, why it will not; and `set_login_shell` becomes a real, implemented post-install action on `oh-my-zsh` alone: hard-blocked on immutable/atomic hosts before anyone is asked, silent without an explicit confirmation, and producing reviewed instructions the user runs themselves rather than a shell change launched from a worker thread.
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06, D-07 (14-CONTEXT.md decision ids — this inserted phase has no REQUIREMENTS.md traceability ids)
**Depends on:** Phase 12
**Plans:** 5/5 plans complete

Plans:
**Wave 1**

- [x] 14-01-PLAN.md — Tracer: an outdated, installed, selected tool updates end to end through ExecuteScreen
- [x] 14-03-PLAN.md — set_login_shell core: closed post_install dispatch table, engine dispatch, registry declaration

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 14-02-PLAN.md — Update visibility: preflight head, progress rows, and the post-run update report including refusals
- [x] 14-04-PLAN.md — Reviewed-instruction renderer, confirmation-binding adapter, and the console entry point's confirm

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 14-05-PLAN.md — In-app sensitive-action prompt, instructions in the post-run log, and the architecture record

### Phase 15: Catalog accuracy: Doctor refresh, version parsing, ownership attribution, tier fixes: four related 'the catalog/doctor shows something untrue' bugs. (1) Doctor's fix action applies successfully but the screen shows stale pre-fix guidance next to the success line, because DoctorScreen.action_apply never calls _refresh_guidance() after a successful fix -- fix the refresh call, and make the (deliberately frozen-until-shell-restart) PATH check's messaging explicit instead of looking broken. (2) Version detection shows 'unknown' for tools whose --version output isn't a bare semver (jq prints 'jq-1.8.1', confirmed live) due to an anchored regex in installer/versions.py's _OBSERVED_VERSION -- fix the extraction and audit the registry for other tools with a similar non-standard --version format. (3) Real OS-package-manager ownership detection (dnf/apt/pacman via rpm -q/dpkg-query/pacman -Qq) already exists and works in installer/install_ownership.py but is fully disconnected from the running app (installer/ownership.py and version_status.py never call it, and always resolve such tools to owner=unknown) -- wire it into the live ownership-resolution path, and add detection for Bazzite's rpm-ostree/just-layering equivalent, which has none today. (4) A few registry tools still look tier-misclassified under this session's corrected tier definition: ast-grep (tier=user, but same family as rg/fd which are tier=ai) and puppeteer (tier=user, but is a runtime library dependency of mmdc, not human-driven) are the clearest; mmdc/gitleaks/vale/drawio-cli are borderline and worth a second look. Also fix installer/ui_common.py's stale AI-tab comment still describing claude/codex as living in that tier (they moved to user tier earlier this session) (INSERTED)

**Goal:** Everything the catalog and Doctor assert about a tool is true: the Doctor screen renders post-fix state and says which part of it cannot move yet, a tool that prints its version in its own format is read rather than shown as unknown, a tool the OS package manager owns is attributed to that manager and cleanly refused by the update action instead of silently mutated or mislabelled, and each of the three tier tabs lists exactly what its own definition says it lists.
**Requirements**: D-01, D-02, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10 (CONTEXT.md decision IDs; this phase has no REQUIREMENTS.md ids, matching Phase 14's precedent)
**Depends on:** Phase 12
**Plans:** 5/5 plans complete

Plans:

**Wave 1** *(parallel — disjoint files)*

- [x] 15-01-PLAN.md — Doctor refresh ordering and the conditional frozen-PATH note (D-01, D-02)
- [x] 15-02-PLAN.md — Shared name-prefix version fallback in both parsers, plus the recorded registry audit (D-03, D-04)
- [x] 15-03-PLAN.md — ast-grep/puppeteer tier corrections, the pinned tier tripwires, and the AI-tab comment (D-07..D-10)

**Wave 2** *(blocked on Wave 1: shares registry.toml and tests/test_registry.py with 15-03)*

- [x] 15-04-PLAN.md — rpm-ostree ownership probe, OWNER_PROBES schema, and owner_probes on the ten native-manager rows (D-06, D-05)

**Wave 3** *(blocked on Wave 2: consumes the probe and the registry opt-in)*

- [x] 15-05-PLAN.md — Native-owner adapter in resolve_ownership, widened Owner, update refusal branch, production wiring, catalog label (D-05)

### Phase 15.8: Fix real (not just cosmetic) PATH duplication from managed-block sourcing: installer/shellrc.py's managed_block() (line 101-111) emits a plain, unconditional 'export PATH="{dir}:$PATH"' per managed bin dir into .bashrc/.zshrc/.myshellrc. The rc-file block itself is idempotent (apply_block never writes it twice), but the block's RUNTIME EFFECT is not: every nested/child shell that sources it again (very common -- tmux/wezterm panes, IDE-integrated terminals, subshells) re-prepends the same directory onto an already-inherited PATH that has it, accumulating duplicates with every nesting level. Confirmed live this session: 5 copies of ~/.local/bin, 4 of fnm's dir, 3+ of several others, in a single real shell session -- this is why Doctor's PATH audit keeps reporting the same 'duplicated on PATH' findings even after applying the fix and opening a genuinely new terminal, not a UI staleness issue (that is Phase 15.1's separate finding). Fix by making managed_block() emit a self-deduping guarded form instead of a plain export -- this codebase already recognizes and special-cases exactly this shape from pnpm's own installer output (installer/rcclean.py:61-70's find_duplicate_path_lines explicitly skips pnpm's case-guarded '*) export PATH="$PNPM_HOME:$PATH" ;;' block as 'self-deduping ... nothing safe or necessary to strip' -- reuse that same case-guarded idiom for every managed dir instead of a plain export). User explicitly asked for a reusable function/mechanism that checks-before-adding, not a one-off patch to this single block -- audit installer/shellrc.py's other PATH-writing call site (pnpm_home block, line ~210) and any other PATH-modifying block in the codebase for the same non-idempotent-at-runtime defect. (INSERTED)

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 15
**Plans:** TBD

Plans:

- [ ] TBD (run /gsd-plan-phase 15.8 to break down)

### Phase 15.7: Unify tmp-prune tooling into an installable Tweaks module (from pending todo 2026-09-10-unify-tmp-prune-tooling-into-an-installable-tweaks-module.md): opencode/Bun's runtime-transpiler-cache orphans native .so/.node artifacts on a killed/crashed process, either in OS temp (macOS $TMPDIR, can reach 100GB+/day) or /tmp on Linux (a small-quota tmpfs on Bazzite, ~12GB, causing EDQUOT failures across the whole system once full). Two independent non-reusable scripts already solve pieces of this today (this repo's scripts/prune-user-tmpdir.sh, manual dry-run/--apply only; ai-kit's Linux-only systemd-timer bundle, confirmed working, keeps /tmp under 1%) but neither is cross-platform, wired into this project, or installable/uninstallable. Build one dedicated cross-platform module: (1) env-var wiring to redirect Bun's cache off tmp entirely (environment.d on Linux, shell-rc based on macOS), (2) a real background daemon install/uninstall -- systemd user timer+oneshot on Linux, launchd LaunchAgent on macOS -- never manual scripts, (3) Tweaks view toggle (install/uninstall, daemon-active status, current tmp usage %), (4) make doctor integration: red warning when the cleanup daemon is inactive AND disk space is below 30% (or /tmp exceeds 50% on Linux specifically), extra visual weight when both conditions are true together. Reuse this project's existing OS-detection conventions (Phase 12.3 precedent) rather than duplicating per-OS logic; user explicitly rejected manual-script-only as an acceptable outcome. (INSERTED)

**Goal:** A developer on Linux gets the same installable, uninstallable background cleanup for orphaned agent-runtime temp files that macOS already has — a systemd user timer + oneshot service toggled from the Policies view, never a manual script — plus a reusable cache-redirect that keeps Bun's runtime-transpiler cache out of the temp dir in the first place, a scope-aware takeover of any pre-existing competing cleanup mechanism, and a red Doctor warning when the cleanup job is inactive while disk or /tmp space is running out.
**Requirements**: D-01 (+D-01a: Linux is on-by-default like macOS; +D-01b: gated on `systemctl` being present; +D-01c: the daemon's active answer is systemd's runtime state, bounded and memoized, never unit-file presence; +D-01d: one shared prune core, per-platform pattern sets), D-02 (scoped as D-02a — RATIFIED in 15.7-CONTEXT.md's 2026-09-22 correction: take over a user-scope competitor, detect-and-disclose-and-coexist for a system-scope one, never escalate privileges; +D-02b: disable, never delete, a competitor's unit files; +D-02c: a failed takeover keeps this project's daemon and discloses the surviving competitor; +D-02d: only a live — enabled or active — unit counts as a competitor), D-03 (+D-03a: low space with the daemon running is an ordinary warning; +D-03b: one total probe contract, total over filesystem and probe-conversion failure while a programming error propagates; +D-03c: "no cleanup daemon available" is a distinct state from "daemon off"; +D-03d: measure the temp dir everywhere, threshold only on Linux), D-04, D-05a (the on-by-default disclosure is delivered through a synchronised, abort-proof warning sink) (15.7-CONTEXT.md locked decisions — inserted roadmap phase, not a REQUIREMENTS.md id; the lettered sub-decisions were resolved during planning and are recorded in the PLAN.md objectives that own them)
**Depends on:** Phase 15
**Plans:** 7 plans

Plans:

- [ ] 15.7-01-PLAN.md — Tracer: end-to-end Linux systemd prune daemon (mechanism, cleanup script, Policy factory, composition root) + transactional apply/remove with compensating daemon-reloads, its own ownership marker, the D-01b `systemctl` availability gate, the D-01c runtime-truthful bounded/memoized active state, and the D-01a on-by-default decision with its composition-root tests (D-01)
- [ ] 15.7-02-PLAN.md — D-03 pure layer: disk-pressure probe with the 15%/70% thresholds, the `DaemonState` tri-state, guidance wording for every combination, and render-layer emphasis instead of a fourth Severity value
- [ ] 15.7-03-PLAN.md — D-02a: read-only, liveness-checked detection of a competing cleanup mechanism in both systemd scopes, user-scope takeover, system-scope warn-only, zero privilege escalation
- [ ] 15.7-04-PLAN.md — D-04: generalized cache-redirect mechanism (environment.d on Linux, rc block on macOS) and its Policy factory, with Bun's exact `~/.cache/bun/transpiler-cache` target as the first wired-up case
- [ ] 15.7-05-PLAN.md — Composition and teardown: per-policy ownership closures, a REQUIRED extra-policy uninstall sweep at both composition roots, platform-accurate uninstall row copy, the D-05a synchronised on-by-default warning sink D-01a depends on, and Policies-view disclosures (login-session limit, next-login redirect, redirect coverage caveat)
- [ ] 15.7-06-PLAN.md — D-03 composition: one named probe construction point, the finding in `make doctor` and the Doctor screen, live temp usage on the cleanup row, source todo folded
- [ ] 15.7-07-PLAN.md — D-01d: characterize the macOS prune script, then collapse both platform scripts onto one shared `scripts/lib/prune-tmp-common.sh` core, closing the source todo's "no side-by-side duplicated logic" requirement

### Phase 15.6: Terminal-emulator default-shell configuration (Konsole/kitty/WezTerm on immutable Linux hosts): make zsh (+ oh-my-zsh plugins, when installed) the working shell whenever the user opens a terminal, without ever touching chsh/system login shell -- chsh is confirmed absent on Bazzite (util-linux-user removed by design, ublue-os/bazzite#4159) and Bazzite maintainers explicitly recommend configuring the terminal emulator instead of the system login shell. Scoped to Linux/immutable hosts where this problem exists (macOS is unaffected -- chsh works normally there via the existing Phase 14 flow, confirmed by user). Research leads found this session: kitty supports a launcher-level override (kitty -o shell=<path>) and WezTerm supports (wezterm start --config default_prog={<path>}) without mutating kitty.conf/wezterm.lua directly; Konsole has no equivalent single flag but supports the more universal -e <command> launch pattern as a fallback. Investigate desktop-launcher (.desktop file) level integration vs per-app config mutation. (INSERTED)

**Goal:** Linux users open kitty, WezTerm, or a live-detected Konsole directly into the discovered zsh login shell, with Oh-My-Zsh and its selected plugins loading whenever the framework is present, while all changes remain reversible user configuration and never alter the system login shell.
**Requirements**: D-01, D-02, D-03, D-04 (15.6-CONTEXT.md locked decisions — inserted roadmap phase, not a REQUIREMENTS.md id)
**Depends on:** Phase 15
**Plans:** 6/6 plans complete

Plans:

- [x] 15.6-01-PLAN.md — Initial D-04 repair (superseded by review-driven plan 02 correction)
- [x] 15.6-02-PLAN.md — D-04 correction: precise, ordered source/template repair for inert and sourced-but-arrayless `.zshrc` files
- [x] 15.6-03-PLAN.md — D-02/D-03/D-04: safe, owned direct Linux terminal configuration and OMZ template synchronization
- [x] 15.6-04-PLAN.md — D-01/D-04: live OMZ Policy activation, truthful warning state, and composition-root wiring
- [x] 15.6-05-PLAN.md — D-01: direct catalog-update synchronization and nonfatal warning reporting
- [x] 15.6-06-PLAN.md — D-01: interactive, unattended, and uninstall lifecycle synchronization with pending-warning delivery

### Phase 15.5: Relax set_login_shell's immutable-host block from total silence to show-with-warning: _set_login_shell (installer/post_install.py:45) returns () unconditionally when Platform.immutable is True, giving zero user feedback when the action is blocked -- confirmed live on this Bazzite host (/run/ostree-booted present, Platform.immutable=True). Phase 14's D-04 decision locked a blanket block citing an unresolved-root-cause Bazzite/KDE-SDDM login bug (ublue-os/bazzite#4159, closed 'not planned', no maintainer diagnosis -- 14-RESEARCH.md's own Assumption A2 flagged the mechanism as unconfirmed). User re-decided (2026-09-15), explicitly overriding D-04's prior 'reversibility: one-way, requires re-verifying #4159 does not reproduce' caveat: on an immutable host, still show the reviewed chsh instructions (never auto-execute -- same non-interactive, handoff-only doctrine as the non-immutable path) but prepend an explicit warning naming the known Bazzite/KDE-SDDM issue and that the outcome is unconfirmed and host-dependent, so the user gets an informed choice instead of silence. Also applies the same 'never silent, always explain why' principle to any other post-install action that could hit a platform-gated no-op in the future (INSERTED)

**Goal:** [Urgent work - to be planned]
**Requirements**: TBD
**Depends on:** Phase 15
**Plans:** 1/1 plans complete

Plans:

- [ ] TBD (run /gsd-plan-phase 15.5 to break down)

### Phase 15.4: Catalog ownership visibility and Uninstall screen real manager attribution: add a visible Owner/package-manager column to the main catalog table (_COLUMNS/_row_cells in catalog_tui.py) reading the same ownership data _version_detail already computes, instead of ownership only appearing in the focused-row detail bar. Separately, UninstallScreen's 'Installed via'/'What gets removed' columns (wizard_app.py's _tool_entry) discard uninstall.py's own already-computed manager-name-plus-path hint (ToolRow.hint) in favor of a generic 4-value enum-keyed string ('userspace'/'managed elsewhere') -- surface the real hint in the table cell, and wire uninstall.py's manager detection (currently brew/cask-only) to the fuller install_ownership.py/ownership.py resolvers already used by update.py, so pnpm/volta/sdkman/uv/dnf/rpm-ostree-owned tools are named instead of falling through to a generic string (INSERTED)

**Goal:** Every tool in the catalog says who owns it, and the Uninstall screen says it too — truthfully and currently. `installer/ownership.py` gains two real evidence sources it lacks today (an inverse "which OS package owns this live binary" query, so a base-image package such as `git`/`git-core` stops resolving to `unknown`; and a Linux-cask path that reaches linuxbrew casks without changing what the installer offers to install there), the catalog table gains an Owner column whose blank cell only ever means genuinely-don't-know, `UninstallScreen`'s "Installed via" cell shows the real per-tool hint instead of a four-value enum string with that hint fed from the same shared resolution, and both screens re-derive on entry so an install, update or removal performed during the session is never hidden behind a construction-time snapshot.
**Requirements**: D-01, D-02, D-02a, D-03, D-04, D-05, D-06 (15.4-CONTEXT.md — inserted, roadmap-scoped phase, not a REQUIREMENTS.md id)
**Depends on:** Phase 15
**Plans:** 5/5 plans complete

Plans:

- [x] 15.4-01-PLAN.md — OS-package ownership resolved end-to-end from an inverse package-database query to a rendered Owner cell, and refused by the update action
- [x] 15.4-02-PLAN.md — Linux-cask ownership evidence plus the registry name fix, with `resolve.py`'s install-time cask gate deliberately untouched
- [x] 15.4-03-PLAN.md — One owner vocabulary for the Owner column and the detail bar, covering every owner value, still usable at 80x20
- [x] 15.4-04-PLAN.md — `UninstallScreen._rows` becomes the fourth live predicate re-derived on every entry, all 12 `UninstallInputs` construction sites migrate to callables, and a removal invalidates the shared ownership data through an epoch-gated `ownership_of`
- [x] 15.4-05-PLAN.md — "Installed via" shows the real hint, fed by the catalog's own ownership map, kept honest by the epoch gate, and best-effort by design on a direct `--uninstall` start

### Phase 15.3: Registry audience field audit: 63 of 89 registry.toml entries carry audience='both' (the class default in model.py), including plainly interactive/shell-UX tools an agent would never invoke directly (starship, oh-my-zsh, direnv, zsh, gnu-bash, bat, eza, zoxide, lazygit, vscode, sublime, etc.) -- do a one-time per-tool pass re-tagging genuinely human-only interactive tools as audience='human', keeping 'both' only for tools plausibly driven by agents/scripts too; this is a data-quality pass on registry.toml, not a schema or code change (tier and audience are confirmed separate, correctly-used fields, not conflated) (INSERTED)

**Goal:** The catalog's `For` column reports a reviewed decision instead of a dataclass default: the 16 tools a human drives interactively — shell theming and config, GUI editors, directory navigation, the git and monitor TUIs, the fuzzy finder — carry `audience = "human"` in `installer/registry.toml` and render under `for human`; every tool that can still be invoked non-interactively for a one-shot output stays `both`; and the whole field is pinned by id set and distribution so a later registry edit can neither undo the re-tag nor sweep an unreviewed row along with it.
**Requirements**: D-01, D-02 (15.3-CONTEXT.md — inserted, roadmap-scoped phase, not a REQUIREMENTS.md id)
**Depends on:** Phase 15
**Plans:** 1/1 plans complete

Plans:

- [x] 15.3-01-PLAN.md — re-tag the 16 reviewed tools to `audience = "human"`, prove one row end to end through `group_tools`/`AUDIENCE_LABEL`, and lock the result with a named set, D-02's seven deliberate keeps, and a 33/47/9 distribution tripwire (D-01, D-02)

### Phase 15.2: Install output buffering and live-progress clarity: StreamingRunner (installer/run.py) already forwards child stdout line-by-line via Popen+readline, but many installers (pnpm, sdkman, curl|sh scripts) block-buffer their own stdout when not attached to a TTY, so output visibly arrives all at once at the end despite the installer streaming faithfully -- force line-buffered/unbuffered child output where feasible (stdbuf -oL, PYTHONUNBUFFERED, per-manager unbuffered flags) for known-buffering tools, and add a 'waiting for output...' indicator per in-flight tool so buffering-silence is not indistinguishable from a hang (INSERTED)

**Goal:** Install output reaches the live log while the installer is still running — the parent forces line-buffered/unbuffered child output wherever a safe mechanism exists, and never fails an install when one is unavailable — and when a child does go quiet, the in-flight tool's own log region says so within two seconds, so buffering-silence is never visually indistinguishable from a hang.
**Requirements**: D-01 through D-12 (15.2-CONTEXT.md — this phase came from live UAT, not a REQUIREMENTS.md id)
**Depends on:** Phase 15
**Plans:** 2/2 plans complete

Plans:

- [x] 15.2-01-PLAN.md — the unbuffer ladder: PYTHONUNBUFFERED unconditionally, `stdbuf -oL` opt-in and availability-gated, no manager names in the runner (D-01..D-05, D-09, D-12)
- [x] 15.2-02-PLAN.md — the 2-second per-in-flight-tool "waiting for output" indicator, transient through the existing InstallLogLine path, never in the persisted tail (D-06..D-08, D-10, D-11)

### Phase 15.1: Catalog post-update refresh staleness and version-status color disambiguation: after ExecuteScreen closes, CatalogScreen's local _version_statuses snapshot never re-triggers enter_view()/_start_version_refresh() (only refresh_marks() on-screen-resume fires) so a tool that was just updated (e.g. deno) still shows the pre-update outdated Ver cell until the user fully navigates away and back -- wire the ExecuteScreen-close callback in wizard_app.py to re-enter the catalog view. Separately, _ver_cell (catalog_tui.py) renders four distinct VersionStatus situations (no data yet, latest=None/not-tracked-for-updates, outdated=None/unparseable, and the orthogonal stale flag) all as the same dim gray text with no way to distinguish 'a system package we will never manage' from 'still probing' -- give the not-tracked-for-updates case a distinct stable marker. Also add a visible, always-on color legend in the catalog UI (e.g. a status-bar or footer line) spelling out what green (up to date), orange (update available), and each distinct gray case (not tracked for updates / still checking / unparseable version) mean -- plus any other non-obvious color/symbol the catalog uses -- so a user is never left guessing what a color means without hovering or reading docs (INSERTED)

**Goal:** Closing an install/update run leaves the catalog tier it ran from showing freshly probed versions on the screen the user is already on, and every state that column can render — both colors, each distinct dim case, and the stale marker — says what it means and is spelled out in an always-on legend present on all three tier views.
**Requirements**: D-01, D-02, D-03, D-04 (15.1-CONTEXT.md — this phase came from live UAT, not a REQUIREMENTS.md id)
**Depends on:** Phase 15
**Plans:** 1/1 plans complete

Plans:

- [x] 15.1-01-PLAN.md — post-run catalog refresh (D-01), per-situation Ver-cell labels (D-02), always-on version legend (D-03/D-04)
