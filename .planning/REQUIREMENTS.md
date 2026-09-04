# Requirements: tools-installer

**Defined:** 2026-09-04
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.

## v1 Requirements

Requirements for this milestone (ingest batch 1/7: `catalog-tiers-and-dependency-chain`).
Each maps to exactly one roadmap phase.

### Catalog Tiers

- [ ] **REQ-catalog-tier-field**: Every registry tool declares a `tier` (`system`/`user`/`ai`) on the `Tool` model and `registry.toml` schema, validated the same way an unknown `Priority` is rejected today; `uv`/`pnpm`/`brew`/`sdkman` migrate to `tier="system"`.
- [ ] **REQ-catalog-tier-views**: The catalog's single flat view splits into three tier-scoped top-level views (System/User/AI) reachable directly from the top nav, each keeping the existing Category/Priority/Audience/Status/Table grouping, with cross-tier `requires` drag-in still visible from a dependent tool's own tier view.

### Dependency Chain

- [ ] **REQ-dependency-chain-requires**: Cross-tier `requires` chains resolve via the existing resolver (`installer/deps.py:resolve_dependencies`) with zero new resolver logic, demonstrated end-to-end using `java`->`sdkman` (already shipped, decision-independent) as the primary proof case once `sdkman` carries `tier="system"`; `mmdc`->`pnpm` is a secondary example only if `mmdc`'s install method (batch 2, REQ-mmdc-install-decision) stays on pnpm — it may become `mmdc`->`puppeteer` instead if that decision resolves to brew.
- [ ] **REQ-recommends-soft-dependency**: `Tool.recommends: tuple[str, ...] = ()`, a soft-dependency field distinct from `requires`, surfaces (never auto-installs) complementary tools via a one-action, non-blocking prompt when a tool such as `claude`/`opencode` is selected.

### Install/Uninstall Lifecycle

- [ ] **REQ-install-failure-propagation**: `run_installs` tracks which tool ids failed during the current run and skips any subsequent tool whose `requires` intersects that failed set, emitting a distinct "dependency failed" outcome instead of letting the dependent run and fail with a confusing downstream error.
- [ ] **REQ-uninstall-sweep-tweak-executables**: A full uninstall also removes tweak-managed executables (`installer/tweaks.py`'s `ManagedExecutable` artifacts, e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts.

### Shell Tweaks

- [ ] **REQ-oh-my-zsh-plugin-config**: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to the `plugins=(...)` array in `.zshrc`, reusing the existing `apply_block`/`strip_block` tweak mechanism — not a separate `Tool`/`Method`/`requires` catalog entry.

### Package Manager Policy (ingest batch 2/7: `package-manager-policy`)

- [ ] **REQ-npx-ban**: `installer/guards.py:BANNED` gains an `"npx"` entry, treated identically to the existing `npm`/`pip`/`pip3` bans (same shim, alias, doctor/guard status, removability); existing ban tests extended to cover `npx`, not duplicated into a parallel file.
- [ ] **REQ-npm-npx-redirect-policy**: `npx` becomes a clean, unconditional transparent redirect to `pnpm dlx`/`pnpx` (no subcommand allowlist needed — confirmed `npx` is single-purpose); `npm` stays hard-blocked pending a separate subcommand-allowlist decision (`install`/`add`/`run`/`exec` have clean `pnpm` equivalents, `ci`/`publish` do not). Any redirect must preserve the underlying command's real exit code/stdout/stderr.
  User question (2026-09-04, raised at the batch-2 merge gate): is `pip`/`pip3` staying hard-blocked (rather than also becoming a redirect) still correct? The original PRD asserted `uv` is "not a drop-in argv-compatible replacement for pip's CLI," but `uv pip <subcommand>` does mirror a meaningful part of pip's surface (`install`/`uninstall`/`list`/`show`/`freeze`/`compile`) — closer than that framing implied. This needs to be re-verified against `uv`'s actual current CLI (not assumed from either the original PRD or general knowledge, both potentially stale) before the pip hard-block decision is treated as settled. If other bans get added in the future, the same "does a safe, argv-compatible redirect exist" check should be applied per-tool rather than assumed.
  Follow-up user idea (2026-09-04), refined into a clearer split after discussion: detect a **`-g`/`--global` flag** on `npm install`/`npm add` (and on `pnpm add -g` itself) and redirect *that specific invocation shape* to `volta install <pkg>` instead of `pnpm`; a non-global `npm install`/`npx` invocation still redirects to plain `pnpm`/`pnpm dlx` as already planned. This split matches Volta's actual architecture, not just a workaround: Volta is a toolchain-version-manager-plus-global-tool-shim layer (it pins Node/npm/pnpm/Yarn per-project via `package.json`'s `"volta"` key and shims those commands transparently) with **no local/per-project dependency-installation mechanism of its own** — a local `npm install`/`pnpm install` inside a project still runs through whichever package manager is invoked; only `volta install <pkg>` (Volta's own managed directory + shims) is the global-CLI-tool use case. So "global installs -> volta, local project installs -> pnpm" is the correct natural boundary between the two tools, not an approximation. **Still needs verification, not assumed:** whether `volta install` shells out to npm internally for the actual install step — if so, it would run postinstall scripts unrestricted the same way npm does, losing pnpm's gated-postinstall security advantage for anything moved to volta. This is the deciding factor for whether the volta redirect is a clean win or a security-for-stability tradeoff.
- [ ] **REQ-codegraph-github-release**: `codegraph`'s registry entry uses `kind="github_release"` (verified: prebuilt binary tarball, no npm involved), not `kind="node"`/`kind="script"`.
- [ ] **REQ-mmdc-install-decision**: Decide and record `mmdc`'s install method explicitly (pnpm with documented mitigation, or Homebrew) — genuinely open, needs research into pnpm-vs-brew tradeoffs (postinstall-script security vs. the known global-install bug) and whether `volta` is a viable alternative; puppeteer/chrome-headless-shell remain required regardless of which manager installs mmdc itself, and whether that dependency applies identically on macOS vs. Linux is also unverified.
  User question (2026-09-04): could `volta` replace pnpm as the global installer for node-only packages, avoiding pnpm's version-upgrade global-package-loss bug entirely, and would it be equally or more secure? Unverified — needs real research, not assumption: volta manages its own install/shim directory rather than using `pnpm add -g`'s mechanism, so it plausibly sidesteps that specific bug, but it is unconfirmed whether volta's own global-install path still shells out to npm internally — if it does, it would inherit npm's unrestricted-postinstall-script behavior, losing the supply-chain-security advantage pnpm's gated postinstall scripts currently provide. This is a real tradeoff to resolve with research, not a clear win either way.
- [ ] **REQ-puppeteer-catalog-entries**: `puppeteer` and `chrome-headless-shell` become their own catalog entries rather than an invisible peer-dependency of `mmdc`; `mmdc.requires` gains `["puppeteer"]` so `resolve_dependencies` drags it in automatically.
- [ ] **REQ-pnpm-global-reinstall-mitigation**: For any tool that must stay on `pnpm add -g` despite the known global-install bug, snapshot the pnpm-managed global set and reinstall it together in one invocation after `pnpm` itself updates — the verified-correct mitigation for the bug's actual root cause. Depends on the not-yet-ingested `live-package-management` PRD's update mechanism (batch 5/7).
- [ ] **REQ-sdkman-exclusivity**: `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively through SDKMAN, never a native/brew fallback, with SDKMAN's own install correctly self-detected (no re-running its bootstrap on every JVM-tool install). **Already implemented and shipped in commit `0e05f50`, outside GSD's normal flow** — treat as prior art requiring verification/hardening (broader test coverage, e2e, review), not as sufficient as-is. `java`'s SDKMAN candidate may need a pinned `version` to avoid an interactive prompt — unverified end-to-end.
- [ ] **REQ-registry-authoring-verification-checklist**: Establish a mandatory per-tool, per-OS verification step before any new registry entry ships — read the tool's actual install script/package metadata (not its marketing page), confirmed independently per OS (a macOS-only prerequisite may be a no-op on Bazzite, and vice versa). Recording mechanism (comment citing what was checked, vs. a stronger checked-in excerpt) is unresolved.
- [ ] **REQ-brew-preference-guideline**: "Prefer brew over other userspace package managers" becomes a documented registry-authoring guideline (not code-enforced) for new tools generally — with SDKMAN as the Java-toolchain's specific carve-out (REQ-sdkman-exclusivity). Enforcement mechanism (lint/test vs. pure convention) unresolved.

## v2 Requirements

None deferred from batches 1-2. The five remaining companion PRDs from the
same 2026-09-04 planning batch (`postinstall-hooks`, `catalog-expansion`,
`live-package-management`, `background-maintenance-daemon`,
`agent-cli-ergonomics`) will be ingested in subsequent merge-mode passes
immediately after this one, adding their own v1 requirements (and likely
further ROADMAP.md phases) rather than v2 deferral of this batch's scope.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New resolver/ordering logic keyed on `tier` | `requires` already does deps-first ordering, cycle detection, and unavailable-dependency skipping; a second ordering mechanism would drift out of sync (PRD Design Decisions) |
| A "tier gate" blocking ai-tier selection until its system-tier `requires` resolves | Redundant with the existing `requires` drag-in; a second, tier-keyed check could go stale |
| The actual new tool list (`oh-my-zsh`, `volta`, `ruby`, `kitty`, `wezterm`, `cursor-agent`, `antigravity`, `codegraph`, etc.) and their install methods | Covered by the companion catalog-expansion PRD, not yet ingested |
| Postinstall actions (MCP registration, non-bundled shell plugin wiring) | Covered by the companion postinstall-hooks PRD, not yet ingested |
| External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step | Explicitly deferred by the source PRD's Open Questions; the two named plugins (`git`, `docker`) are both bundled |
| `recommends` surfacing cadence (once per session vs. every reselect) and a registry-authoring lint for `recommends` completeness | Open questions left to the planning phase, not yet requirements |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REQ-catalog-tier-field | Phase 1 | Pending |
| REQ-dependency-chain-requires | Phase 1 | Pending |
| REQ-catalog-tier-views | Phase 2 | Pending |
| REQ-recommends-soft-dependency | Phase 2 | Pending |
| REQ-install-failure-propagation | Phase 3 | Pending |
| REQ-uninstall-sweep-tweak-executables | Phase 3 | Pending |
| REQ-oh-my-zsh-plugin-config | Phase 3 | Pending |
| REQ-npx-ban | Phase 4 | Pending |
| REQ-npm-npx-redirect-policy | Phase 4 | Pending |
| REQ-codegraph-github-release | Phase 5 | Pending |
| REQ-mmdc-install-decision | Phase 5 | Pending |
| REQ-puppeteer-catalog-entries | Phase 5 | Pending |
| REQ-pnpm-global-reinstall-mitigation | Phase 5 | Blocked (depends on batch 5/7 ingest) |
| REQ-sdkman-exclusivity | Phase 6 | Shipped ahead of plan (`0e05f50`) — verify/harden |
| REQ-registry-authoring-verification-checklist | Phase 6 | Pending |
| REQ-brew-preference-guideline | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-04*
*Last updated: 2026-09-04 after ingest batch 2/7 (package-manager-policy) merged*
