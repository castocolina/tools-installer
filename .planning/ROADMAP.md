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

**More phases are coming.** Five more PRDs from the same 2026-09-04 batch
(`postinstall-hooks`, `catalog-expansion`, `live-package-management`,
`background-maintenance-daemon`, `agent-cli-ergonomics`) will be ingested in
subsequent merge-mode passes immediately after this one, each expected to
append further phases to this roadmap. This is not the complete project
scope.

**Batch 2/7 (`package-manager-policy`) added Phases 4-6**: extending the
`npm`/`pip` ban to `npx` with a redirect policy, correcting `codegraph`'s and
`mmdc`'s install methods (plus the puppeteer/chrome-headless-shell chain
mmdc actually needs), and hardening the already-shipped SDKMAN-exclusivity
work (commit `0e05f50`) alongside two registry-authoring guidelines.

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

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Catalog Tier Foundation | 0/TBD | Not started | - |
| 2. Tier-Scoped Catalog Views & Recommends | 0/TBD | Not started | - |
| 3. Install/Uninstall & Tweak Lifecycle Hardening | 0/TBD | Not started | - |
| 4. npm/npx Ban Extension & Redirect Policy | 0/TBD | Not started | - |
| 5. Registry Method Corrections (codegraph/mmdc/puppeteer) | 0/TBD | Not started | - |
| 6. SDKMAN Hardening & Registry-Authoring Guidelines | 0/TBD | Not started | - |
