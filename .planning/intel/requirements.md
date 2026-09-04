# Requirements

Source PRD: `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`
(classified `docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md`,
confidence: high, manifest_override: true, locked: false)

## REQ-catalog-tier-field
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Add a `tier` field (`system`/`user`/`ai`) to the `Tool` model and `registry.toml` schema, replacing the flat category/priority-only structure, so catalog entries can be organized by machine-prerequisite vs. personal-pick vs. agent-facing tooling.
- acceptance:
  - `Tier` enum exists in `installer/enums.py` with `system`/`user`/`ai`, following the exact pattern of `Priority`/`Audience`.
  - Every registry entry must declare a `tier`; loading a registry entry with a missing or unknown `tier` fails the same way an unknown `Priority` does (see `_parse_enum` in `installer/model.py`).
  - `uv`/`pnpm`/`brew`/`sdkman` carry `tier="system"` (migration of existing entries).
  - `tier` is treated as strictly orthogonal to `Category` — a tool keeps its existing topical category and gains a tier on top, the same way it already has a priority and an audience.
  - `.claude/architecture.md` documents that `tier` is a browsing/navigation label and `requires` remains the single source of truth for install order.
- scope: catalog tiers, registry schema, Tool model validation

## REQ-dependency-chain-requires
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Declare `requires` chains in `registry.toml` for new system-tier tools (e.g. `oh-my-zsh`, `volta`) so the existing `installer/deps.py:resolve_dependencies` resolver drags them in correctly across tier boundaries. This is a data problem, not an architecture problem — the resolver already exists and is already invoked from `installer/app.py` for every install run.
- acceptance:
  - No new resolver logic; `requires` remains the single mechanism for install order, transitive drag-in, cycle detection, and unavailable-dependency skipping, exactly as `resolve_dependencies` does today.
  - New system-tier tools' `requires` chains express the graph described in the Background section (illustrative, not final registry syntax: `oh-my-zsh.requires = ["zsh"]`, `volta.requires = ["oh-my-zsh"]` or `["zsh"]`).
  - A tier value must never be required to make a `requires` chain resolve — the resolver has no notion of tier.
  - System-tier prerequisite tools drag in correctly via `requires` when a dependent tool is selected from any tier view, using the existing `resolve_dependencies` — no new resolver code.
  - Selecting an ai-tier tool that needs an undeclared system-tier prerequisite still drags it in automatically, with no manual step.
- scope: dependency chain, requires declarations, Homebrew bootstrap order, oh-my-zsh
- caution: this batch's Phase 1 success criteria (see existing ROADMAP.md) illustrate this requirement with `mmdc`→`pnpm` as a cross-tier example. Batch 2 (`package-manager-policy`) leaves `mmdc`'s install method (pnpm vs. brew) as an open, unresolved decision — see `REQ-mmdc-install-decision` below and `WARNING` in `INGEST-CONFLICTS.md`. The underlying requirement (resolver already handles cross-tier `requires`) is unaffected; only the specific illustrative example may need to change if `mmdc` moves to brew.

## REQ-install-failure-propagation
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: `run_installs` (or wherever the per-tool install loop lives) must track which tool ids failed during the current run and skip any subsequent tool whose `requires` intersects that failed set, emitting a distinct `SKIPPED`-shaped outcome naming which dependency failed — instead of letting a dependent (e.g. `mmdc`) run and fail with a confusing downstream error after its dependency (e.g. `pnpm`) already failed. Gap identified by review of the already-merged dependencies-and-shell-tweaks work (commit `431a0a9`); its own PRD/plan specified "soft-warn + skip dependents on failure" but `installer/session.py::run_installs` does not currently implement the skip.
- acceptance:
  - A tool whose `requires` dependency failed to install during the same run is skipped with a clear "dependency failed" outcome, never silently attempted or silently omitted.
  - Does not change `resolve_dependencies`'s pre-install resolution logic — this is a new runtime concern layered on top of the already-resolved install order, scoped to `installer/session.py` (or `installer/engine.py`).
- scope: install-time failure propagation, installer/session.py, installer/engine.py
- status: Per source — "identified by review, not implemented." Deferred to GSD's own research/plan/execute flow rather than an ad hoc assistant fix.

## REQ-uninstall-sweep-tweak-executables
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Uninstall's plan/execute path (`installer/app.py::run_uninstall`/`perform_uninstall`, `installer/uninstall.py::plan_uninstall`) must also account for tweak-managed executables (`installer/tweaks.py`'s `ManagedExecutable` mechanism, e.g. `tools-installer-wait-time` in `~/.local/bin`), not just `Tool`-shaped artifacts, so a full uninstall genuinely leaves nothing behind regardless of whether an artifact came from a `Method` or a `TweakBundle`. Gap identified by the same review: this managed executable is currently only removed when its own policy is explicitly toggled off, since the uninstall planner only walks `Tool` entries today.
- acceptance:
  - A full uninstall removes every tweak-managed executable (`ManagedExecutable`-shaped artifacts), not only `Tool`-shaped ones.
- scope: uninstall sweep completeness, installer/uninstall.py, installer/tweaks.py
- status: Per source — "identified by review, not implemented." Same GSD-flow deferral as REQ-install-failure-propagation.

## REQ-catalog-tier-views
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Split the existing single `Catalog` entry in the shared `VIEWS` registry (`installer/ui_common.py`) into three tier-scoped top-level views (System/User/AI) reachable directly from the top nav — not an in-screen filter — matching how the user works through a fresh machine. Each tier view retains the existing Category/Priority/Audience/Status/Table grouping and sort as inner dimensions, tier being the outer navigation dimension. Whether this is three separate screens or one `CatalogScreen` parameterized by tier (reusing `ToolBrowser`) is an implementation choice deferred to the planning phase.
- acceptance:
  - The catalog has three tier-scoped top-level views (System/User/AI), each still supporting the existing Category/Priority/Audience/Status/Table grouping within it.
  - Cross-tier `requires` stays visible from a dependent tool's own tier view — e.g. selecting `claude` (ai tier) that needs `pnpm` (system tier) must not require a prior System-view visit; the existing drag-in behavior and its notice (`render_dependency_notice`) communicate this across the tier boundary.
  - Opening a tier view before its prerequisite tier (e.g. AI before System) and selecting a tool with an unresolved system-tier `requires` makes the drag-in, or a clear unavailable-dependency notice, obvious without forcing a specific visit order.
  - Browsing the catalog, it is obvious which tools are machine prerequisites versus personal picks versus agent-facing tools.
- scope: catalog TUI, VIEWS registry, one-registry-one-nav-path standard (.claude/architecture.md)

## REQ-recommends-soft-dependency
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Add a `Tool.recommends: tuple[str, ...] = ()` field, distinct from `requires`, that surfaces (never auto-installs) tools that pair well with a selected tool (e.g. `codegraph`, `graphify`, `rtk` for `claude`/`opencode`), with its own resolution/surfacing mechanism in `installer/deps.py` or an adjacent, smaller pure function. `resolve_dependencies` must not be extended to also drag in `recommends` edges, since that would collapse the distinction the feature exists to draw.
- acceptance:
  - Selecting `claude`/`opencode` (or similar) surfaces its `recommends` list without auto-installing anything.
  - Selecting a tool with `recommends` surfaces a prompt/notice naming the recommended tools and letting the user add them to the current selection with one action — never a blocking modal, and never silently added.
  - `recommends` referencing an id lower in the same tier or a different tier is valid (e.g. `claude.recommends = ["codegraph", "graphify", "rtk"]`, all ai tier) — unlike `requires`, there is no ordering obligation to enforce.
- scope: recommends soft dependency, catalog TUI, installer/deps.py

## REQ-oh-my-zsh-plugin-config
- source: docs/prds/2026-09-04-catalog-tiers-and-dependency-chain-v1.0-prd.md
- description: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to the `plugins=(...)` array in `.zshrc`, reusing the existing rc-editing tweak mechanism (`installer/shellrc.py`'s `apply_block`/`strip_block`) — not modeled as separate `Tool`/`Method`/`requires` catalog entries, since they ship bundled inside oh-my-zsh and only need enabling, no download or install method of their own.
- acceptance:
  - Oh-My-Zsh's `git`/`docker` plugins are enabled via a config-array edit to `.zshrc`, not a separate `Tool` entry.
- scope: oh-my-zsh, shell config, installer/shellrc.py

---

Source PRD: `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md`
(classified `docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md`,
confidence: high, manifest_override: true, locked: false)

## REQ-npx-ban
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Extend the existing npm/pip/pip3 ban mechanism (`installer/guards.py:BANNED`, POSIX shim + shell alias + doctor/guard status) to also cover bare `npx`, pointing users at pnpm's dlx equivalent.
- acceptance:
  - `installer/guards.py:BANNED` gains an `"npx"` entry.
  - The shim, alias, and doctor/guard status reporting treat `npx` exactly like the existing three banned commands — same removability, same opt-in nature, same PATH-order warning logic.
  - Existing tests for the ban (shim generation, alias write/remove, guard status, doctor guidance) are extended to cover `npx`, not duplicated into a parallel test file.
  - Running `npx <pkg>` after the ban is active gives the same clear, actionable guidance `npm` already does.
  - Doctor/guard status reporting covers `npx` the same way it covers the other three banned commands.
- scope: installer/guards.py, npx ban, doctor/guard status reporting

## REQ-npm-npx-redirect-policy
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Decide, per command rather than as one global switch, whether npm/npx become a transparent redirect to pnpm's equivalent CLI surface instead of a hard block. `npx` is resolved: it redirects unconditionally to `pnpm dlx` (a clean 1:1 mapping — `pnpx`/`pnx` are pnpm's own aliases for the same thing — no allowlist needed). `npm` remains unresolved — it has subcommands with no clean pnpm equivalent (`npm ci`, `npm publish`), so which subcommands are safe to forward is an open question. `pip`/`pip3` stay hard-blocked (uv is not a drop-in argv-compatible replacement for pip's CLI — different flag surface, different subcommand names).
- acceptance:
  - Whichever behavior is chosen per command, it remains idempotent and removable, matching the existing ban's shape.
  - If npm/npx become a transparent redirect, it preserves the user's original exit code and stdout/stderr from the underlying `pnpm`/`pnpm dlx` invocation.
  - The redirect must not silently swallow the failure mode where a tool's *internal* tooling calls bare `npm` — either it succeeds silently (fine, it never needed npm) or fails in a new, harder-to-diagnose spot mid-install (the risk to design against).
- scope: installer/guards.py, redirect vs. hard-block policy
- status: partially resolved — npx→`pnpm dlx` redirect decided; npm subcommand allowlist unresolved (Open Question 2)

## REQ-codegraph-github-release
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Move `codegraph`'s registry entry off `pnpm add -g` (which hits pnpm's known, unfixed global-install data-loss bug — pnpm#11520, pnpm#11587) onto `kind="github_release"`, since `codegraph`'s real `install.sh` (fetched and read 2026-09-04) downloads a prebuilt binary from GitHub Releases and its own header states no Node.js/npm is required.
- acceptance:
  - `codegraph`'s registry entry uses `kind="github_release"`, not `kind="node"` or `kind="script"`.
  - The registry entry templates `{ver}`/`{arch.*}` the same way every other `github_release` entry does; `strip_components=1` matches the archive's `codegraph-<target>/` top-level layout.
  - `codegraph` installs via `kind="github_release"`, not `pnpm add -g`.
  - `codegraph` installs and updates reliably without the pnpm global-install bug.
- scope: registry.toml, codegraph entry

## REQ-mmdc-install-decision
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Decide `mmdc`'s (`@mermaid-js/mermaid-cli`) install method explicitly and record it — keep on `pnpm add -g` with a documented mitigation, or switch to the Homebrew formula (currently version-equal to npm at `11.17.0` as of 2026-09-04, so the freshness tradeoff that previously motivated staying on pnpm no longer applies today, though it can drift again in the future).
- acceptance:
  - The mmdc decision (keep on pnpm with documented risk, or switch to brew) is made explicitly and recorded, not left ambiguous in the registry.
- scope: registry.toml, mmdc entry
- status: unresolved — Open Question 3; PRD leans brew but explicitly defers the final call to the user.
  User clarification (2026-09-04, given while approving this ingest batch's WARNING gate):
  the decision is open because it needs real research, not a coin-flip between two known
  options — pnpm is preferred over npm generally for security (pnpm gates package
  postinstall scripts by default; npm runs them unrestricted), but pnpm specifically has
  the known global-install/version-upgrade data-loss bug this PRD batch documents. The user
  also flagged `volta` as a candidate they believe is meant for Node's own runtime/version
  management rather than global CLI package installs, but said explicitly they are not
  certain of that distinction — this needs to be verified as part of the research, not
  assumed either way. Whichever package manager mmdc ends up on (pnpm, brew, or volta),
  the `puppeteer`/`chrome-headless-shell` dependency chain (see REQ-puppeteer-catalog-entries)
  is still required for mmdc to actually run from the CLI — that dependency is orthogonal to
  which package manager installs mmdc itself, not eliminated by picking a different one.
  Also unresolved: whether puppeteer/chrome-headless-shell is required identically on macOS
  as on Linux, or whether one platform needs it and the other does not — unverified, flagged
  by the user as a real open question for the research phase to close, not assumed either way.

## REQ-puppeteer-catalog-entries
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: `puppeteer` and `chrome-headless-shell` become their own catalog entries, not bundled invisibly inside mmdc's install, regardless of which path (brew or pnpm) mmdc itself uses — mmdc's real `package.json` declares `puppeteer` as a peerDependency (not auto-installed transitively), and puppeteer itself downloads a multi-hundred-MB `chrome-headless-shell` binary as part of its own install.
- acceptance:
  - `puppeteer`: modeled as `kind="node"` (no non-npm distribution), or — if mmdc moves to brew — needs verification of whether the Homebrew formula's install already provisions a working puppeteer/chromium (its dependency list only names `node`).
  - `chrome-headless-shell`: has no independent install method of its own (puppeteer downloads it as part of its own install) — likely modeled as a `requires` edge on `puppeteer` documenting the relationship rather than a separately installable artifact; whether it needs its own `Tool` entry at all is unresolved.
  - `mmdc.requires` gains `["puppeteer"]` (in addition to, or in place of, `["pnpm"]`) so `resolve_dependencies` drags puppeteer in automatically instead of leaving it a silent, invisible peer-dependency gap.
  - Puppeteer's Chrome download (multi-hundred-MB, network-dependent) is documented clearly so it does not look like a hang or a failed install to the user.
- scope: registry.toml, puppeteer entry, chrome-headless-shell entry
- status: `chrome-headless-shell` catalog-entry shape unresolved (Open Question 3a).
  Also unresolved per user clarification (2026-09-04): whether puppeteer's
  chrome-headless-shell download is required identically on macOS and Linux, or is
  platform-specific to one of them — unverified, needs research before the registry
  entry's `os`/`arch` scoping can be decided.

## REQ-pnpm-global-reinstall-mitigation
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: For any tool that stays on `pnpm add -g` despite the known global-install bug (the `mmdc` case, and any future `kind="node"` entry with no alternative), the installer should snapshot the set of pnpm-managed global packages it installed and reinstall that whole set in one `pnpm add -g <all-of-them>` invocation after pnpm itself is updated — the bug is keyed on "packages installed together in one invocation," so reinstalling everything together in a single invocation is the verified-correct mitigation, not a workaround that happens to help.
- acceptance:
  - No new tracking state is needed beyond querying "which currently-selected/installed tools use `kind=\"node\"`" — the registry is already the source of truth.
  - Triggers when `pnpm` itself is the tool being updated, as a natural extension of the update mechanism described in the companion `2026-09-04-live-package-management-v1.0-prd.md` (not yet ingested) — not a separate standalone feature.
  - Scope: mitigation only for tools that must stay on `pnpm` — not a reason to keep more tools on `pnpm` than necessary; `codegraph` still moves to `kind="github_release"` regardless.
- scope: pnpm global-install mitigation, installer update mechanism
- status: depends on companion `live-package-management` PRD's update mechanism (not yet ingested)

## REQ-sdkman-exclusivity
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: `java`, `gradle`, `maven`, `groovy`, `springbootcli` install exclusively through SDKMAN — never brew or a native package manager, even though brew formulas exist for all five — because SDKMAN also owns JVM version management across these five tools together, which a one-off brew formula per tool does not coordinate. A code review of commits `431a0a9`/`0db5865` found each tool declared `requires = ["sdkman"]` but resolved to `dnf`/`apt`/`pacman`/`brew` instead, bypassing SDKMAN entirely, and that SDKMAN's own `sdkman-init.sh` (mode 644, sourced not executed) could never be detected as installed by `shutil.which()`.
- acceptance:
  - `java`/`gradle`/`maven`/`groovy`/`springbootcli` each declare a single `kind="sdkman"` method (candidate name + `bin_dir` under `~/.sdkman/candidates/<candidate>/current/bin`); all prior `dnf`/`apt`/`pacman`/`brew` methods removed, not kept as fallback.
  - A new `"sdkman"` method `kind` sources `~/.sdkman/bin/sdkman-init.sh` and runs `sdk install <candidate> [version]` in one `bash -c` invocation, ranked in the userspace tier (same rank as `node`/`github_release`) ahead of native/brew, on every platform.
  - `springbootcli`'s SDKMAN candidate is `springboot` (not `spring-boot`/`spring`); `cmd` stays `spring`.
  - `installer/status.py::is_installed` gains a generic `detect_path` fallback (checked via `Path(...).expanduser().exists()` after `which()` fails, before the app/cask bundle check); SDKMAN's own method declares `detect_path = "~/.sdkman/bin/sdkman-init.sh"`.
  - Non-interactive install relies on SDKMAN's own `?ci=true` bootstrap flag persisting `sdkman_auto_answer=true` in `~/.sdkman/etc/config` — not yet independently re-verified end-to-end against a real, unconfigured machine.
  - `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively through SDKMAN with no native/brew fallback.
  - SDKMAN's own install is correctly detected without re-running its bootstrap on every subsequent JVM-tool install.
- scope: installer/model.py, installer/executors.py, installer/resolve.py, installer/status.py, registry.toml
- status: **already implemented and shipped ahead of this PRD** (commit `0e05f50`, pushed to `main` directly by the assistant during a review pass — a process deviation from GSD's research→plan→execute→verify flow, per the user's explicit standing instruction "no vamos a implementar nada"). Treat as prior art to verify and harden (broader test coverage, e2e verification, review), not a spec to re-derive from zero or accept as sufficient. `java`'s SDKMAN method has no pinned `version` set — `sdk install java` with no version may prompt interactively for a vendor-qualified choice unless a default is pre-configured; unresolved (Open Question 6a).

## REQ-registry-authoring-verification-checklist
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Establish a mandatory per-tool, per-OS verification step before any new registry entry ships — read the tool's actual install script/package metadata (not its marketing page) to confirm what it depends on underneath, and confirm the same install path is meaningful on every OS this installer targets (a step unconditionally required on macOS, e.g. Xcode Command Line Tools, may be a no-op on Bazzite, whose base image already ships `curl`/`git`/build tooling; conversely Homebrew's own bootstrap is curl|bash on every platform including Linux, so system-tier prerequisites need per-OS verification, not assumption from the macOS case).
- acceptance: (absent — no explicit code acceptance stated in the source; a documented, non-negotiable part of the registry-authoring checklist, extending the existing "verify assets resolve" discipline to also cover "what does the install actually depend on")
- scope: registry-authoring process, documentation
- status: open question on how this gets recorded — a registry-entry comment citing what was checked is the stated minimum bar; whether it needs to be stronger (e.g. a checked-in excerpt of the install script's relevant portion) is unresolved (Open Question 5)

## REQ-brew-preference-guideline
- source: docs/prds/2026-09-04-package-manager-policy-v1.0-prd.md
- description: Establish "prefer brew over other userspace package managers" as a registry-authoring guideline for new tools, documented in `.claude/architecture.md` or a similar standards doc — not enforced by code, since there is no way to mechanically prove a "better" method exists.
- acceptance: (absent — no code acceptance stated in the source; documentation-only guideline)
- scope: .claude/architecture.md or standards doc, registry-authoring guideline
- status: open question whether this should later be enforced by lint/test (e.g. flag a new `kind="node"` entry and require an explicit justification comment) — Open Question 4

---

Source PRD: `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md`
(classified `docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md`,
confidence: high, manifest_override: true, locked: false)

## REQ-uv-tool-executor
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Add a new `"uv-tool"` executor kind to `installer/executors.py`, mirroring the existing `"node"` kind's shape (`pnpm add -g <npm_pkg>` -> `uv tool install <pypi_pkg>`), using this project's own already-trusted `uv` toolchain rather than adding a new trust dependency.
- acceptance:
  - `installer/executors.py` gains a `"uv-tool"` kind mirroring `"node"`'s shape.
  - `graphify`'s registry entry uses `kind="uv-tool"`, package `graphifyy` (double-y package name; the CLI command is `graphify` — confirmed via research, not assumed), `requires = ["uv"]` (uv is already a catalog tool).
  - `graphify` installs via the new `kind="uv-tool"` executor.
- scope: installer/executors.py, uv-tool executor kind, graphify entry

## REQ-system-tier-shell-container-entries
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Add registry entries for `zsh`, `oh-my-zsh` (`kind="script"`, official install script, `requires = ["zsh"]`), `gnu-bash` (macOS only, via brew — a distinct, newer bash from Apple's ancient GPL-constrained bash 3.2), and Apple Containers (macOS only, native `container` CLI) to the system tier.
- acceptance:
  - `zsh`: platform-appropriate install (brew on macOS, distro package manager on Linux where not already the default shell).
  - `oh-my-zsh`: `kind="script"` matching the `bun`/`pnpm`/`fnm` pattern (`codegraph` is `kind="github_release"`, not `kind="script"`, per the package-manager-policy PRD), `requires = ["zsh"]`; the installer's actual behavior (larger/more invasive than `bun`/`fnm`'s, rewrites `.zshrc`) is verified before assuming it is a safe, reviewable `kind="script"` candidate.
  - `gnu-bash`: `os = ["macos"]`-scoped brew install; absent on Linux (system bash already current GNU bash there).
  - Apple Containers: macOS-only registry entry reflecting that the `container` CLI ships with the OS on recent macOS versions (nothing to install), or documents the minimum OS version requirement if there is.
  - Every entry verified against its live, current release/formula before merging.
- scope: registry.toml, zsh/oh-my-zsh/gnu-bash/Apple-Containers entries, system tier
- status: Apple Containers — open question whether there is anything to actually install on a current macOS, or whether the entry is purely a version-gate/documentation entry (Open Question 4).

## REQ-terminal-emulator-entries
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Add `kitty` and `wezterm` as user-tier registry entries — brew on macOS (both in homebrew-core); Linux via each distro's package manager or the project's existing `.zip`/GitHub-release download path if no native package exists.
- acceptance:
  - `kitty`, `wezterm` install cleanly on macOS via verified live methods.
  - Linux install path verified live before adding, per this project's existing registry-authoring convention (every prior batch verified assets against live releases).
- scope: registry.toml, kitty/wezterm entries, user tier

## REQ-agent-host-entries
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Add ai-tier registry entries for `antigravity`, `cursor-agent`, `codegraph` (`kind="github_release"` per the package-manager-policy PRD's verified finding — prebuilt binary, no npm), and `graphify` (`kind="uv-tool"`, see REQ-uv-tool-executor).
- acceptance:
  - `antigravity`, `cursor-agent` install via a verified official method (brew cask for a GUI app, or an official script/binary for a CLI) — not assumed; neither was verified during this PRD's own research (Open Question 2).
  - `codegraph` installs via `kind="github_release"`, not `kind="node"` or `kind="script"`.
  - No pnpm-bug exposure for any of these four entries.
- scope: registry.toml, antigravity/cursor-agent/codegraph/graphify entries, ai tier
- status: `antigravity`/`cursor-agent` install methods unverified as of this PRD (Open Question 2) — may need a new method kind if either turns out to be npm-only with no brew formula/official script, facing the same pnpm-bug tradeoff this whole effort exists to avoid.

## REQ-rtk-github-release
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Add `rtk` ("Rust Token Killer") as an ai-tier registry entry, `kind="github_release"` from `rtk-ai/rtk` (verified via the GitHub API: pure Rust, prebuilt per-platform tarballs — `rtk-aarch64-apple-darwin.tar.gz`, `rtk-x86_64-apple-darwin.tar.gz`, `rtk-aarch64-unknown-linux-gnu.tar.gz`, `rtk-x86_64-unknown-linux-musl.tar.gz` — same shape as `rg`/`fd`/`codegraph`), checksum-verified against the release's `checksums.txt` using the existing `checksum` registry param.
- acceptance:
  - `rtk` installs via `kind="github_release"` from `rtk-ai/rtk`, checksum-verified against its release's `checksums.txt`.
- scope: registry.toml, rtk entry, ai tier

## REQ-recommends-wiring-agent-hosts
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Wire the `Tool.recommends` soft-dependency field (mechanism defined by the catalog-tiers-and-dependency-chain PRD, batch 1, see REQ-recommends-soft-dependency) with concrete data: `claude`, `opencode`, `codex`, `cursor-agent`, and `antigravity` each gain `recommends = ["codegraph", "graphify", "rtk"]` (adjusted per tool as it makes sense) — surfaced, never auto-installed, when one of those is selected.
- acceptance:
  - `claude`, `opencode`, `codex`, `cursor-agent`, `antigravity` each declare a `recommends` list naming `codegraph`/`graphify`/`rtk` as appropriate per tool.
  - Selecting any of these tools surfaces its `recommends` list without auto-installing anything (per REQ-recommends-soft-dependency's mechanism).
- scope: registry.toml, recommends data, ai tier
- relation: instantiates REQ-recommends-soft-dependency (batch 1 mechanism) with concrete tool data — additive, not a competing variant.

## REQ-linux-bazzite-shell-parity
- source: docs/prds/2026-09-04-catalog-expansion-v1.0-prd.md
- description: Give the new system-tier tools (`zsh`, `oh-my-zsh`) a real Linux/Bazzite install path, reusing the existing "Immutable Linux and Bazzite Requirements" precedent from the doctor/catalog refresh PRD (prefer containerized, Homebrew/linuxbrew, or userspace paths over native package-manager writes on an atomic/immutable distro); `podman` already exists in the catalog as the container-runtime story for Linux/Bazzite, so no new container tool is needed there.
- acceptance:
  - Linux/Bazzite has a working shell-setup path (`zsh`/`oh-my-zsh`).
  - Relies on the existing `podman` entry for containers — no new container tool added.
  - Each system-tier tool's actual OS-conditional prerequisites verified individually — "Bazzite needs less setup than macOS" is not applied as a blanket rule (correction from an earlier draft, per user review: Homebrew's own bootstrap is `curl|bash` on every platform including Linux; the real distinction is that Bazzite's base image already ships `curl`/`git`/build tooling, not that brew skips its own bootstrap there).
- scope: registry.toml, Linux/Bazzite parity, system tier

---

Source PRD: `docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md`
(classified `docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md`,
confidence: high, manifest_override: true, locked: false)

## REQ-postinstall-field
- source: docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md
- description: Add an optional `postinstall` field declared per tool/`Method` (resolved 2026-09-04) that names a command to run once after that install succeeds — either inline (a short one-or-two-line command string directly in the `[[tool.method]]` block) or, for anything that would bloat `registry.toml`, a `postinstall_script` field naming a bundled script file following the exact precedent of `installer/tweaks.py`'s `ManagedExecutable`/`helper_assets/` mechanism (`wait_time.py`). A tool with no `postinstall` behaves exactly as today.
- acceptance:
  - `postinstall` is optional; absent on a tool it behaves exactly as today.
  - Both an inline command string and a `postinstall_script` file (helper_assets/-bundled, `ManagedExecutable`-precedent) are supported, chosen per tool as appropriate.
  - The command runs through the same trusted `Runner` seam every other executor uses (`installer/executors.py`) — no new subprocess-invocation path, inheriting the existing security posture (registry-authored only, never templated from user input beyond the existing `{ver}`/`{arch.*}` token vocabulary).
  - The command can reference AI-agent host CLIs by their catalog tool ids, so "run for every installed host" is expressible declaratively rather than hardcoded per tool.
- scope: installer/executors.py, registry.toml schema, Tool/Method model, postinstall field

## REQ-postinstall-execution-timing
- source: docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md
- description: The postinstall step runs immediately after the `Method` that just ran reports success — not batched, not deferred to end-of-session — dispatched through the existing `run_live` workflow (the single live-mutation path this codebase already settled on during the TUI interaction consistency work), and is aware of (or can query) which `Method`/`kind` actually installed the tool. A postinstall failure must not be reported as an install failure for the tool itself — surfaced as a distinct warning, visible in the TUI the same way an install outcome is shown today, never a silent side effect.
- acceptance:
  - The postinstall command runs exactly once per successful install, never on a no-op outcome.
  - A postinstall failure is visible to the user but does not mark the tool's own install as failed.
  - Modeled as an extension of `run_live`, not a new parallel execution mechanism.
- scope: installer/session.py or installer/engine.py, run_live workflow, postinstall execution timing

## REQ-postinstall-idempotency-live-check
- source: docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md
- description: Idempotency via a live "is the effect already present" check (e.g. `shutil.which`-shaped, synchronous PATH/filesystem lookup — already used throughout this codebase in `guard_status`/`status.is_installed`/`has_managed_block`), not a new tracked-state database — this project has no state-tracking primitive anywhere today and adding one here would be the first of its kind, with a real risk of drifting out of sync with reality.
- acceptance:
  - No new tracking state beyond querying live installer state (e.g. `status.is_installed`).
  - The idempotency check asks "is the effect already present" (e.g., for codegraph: is the MCP entry already in that host's config file), not "did I previously run this."
  - Re-running the installer does not repeat unwanted postinstall side effects.
- scope: postinstall idempotency, live-check pattern, no new state database

## REQ-postinstall-noninteractive-only
- source: docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md
- description: A postinstall command must run unattended to completion (flags/env vars supplying every answer an interactive prompt would ask) — a hard requirement, not a preference, since an interactive step would hang the TUI's live-apply flow with no way to answer it. A tool whose only postinstall/setup path is interactive is not a candidate for this mechanism; it either stays a manual step documented for the user, or ships without a `postinstall` field at all.
- acceptance:
  - Every `postinstall` command is verified non-interactive (flags/env vars covering every prompt) before it is added to the registry.
  - A tool with an interactive-only setup path does not get a `postinstall` field.
- scope: postinstall field validation, non-interactive requirement, registry-authoring discipline

## REQ-codegraph-mcp-postinstall
- source: docs/prds/2026-09-04-postinstall-hooks-v1.0-prd.md
- description: After `codegraph` installs, run its global MCP-registration step ("init global") for each of `claude`/`codex`/`opencode`/`cursor-agent` that is already installed on this machine — never installing those hosts as a side effect (would violate the existing `Tool.requires` boundary between "needs to exist" and "optionally integrates with"). If none of those hosts are installed yet, the postinstall step is a documented no-op, not an error.
- acceptance:
  - `codegraph`'s postinstall registers it as an MCP server for every already-installed agent host, and no-ops cleanly when none are installed.
  - After installing `codegraph`, its MCP server is usable from every already-installed agent host without a separate manual step.
  - Never installs an agent host as a side effect of the postinstall step.
- scope: registry.toml codegraph entry, MCP server registration, postinstall
- status: exact non-interactive setup invocation (flags/env vars/config file) for codegraph's "init global" step is per-tool research deferred to implementation, not resolved by this PRD (Per-Tool Postinstall Research section); discovery mechanism for "which hosts are installed" leans toward reusing `status.is_installed` directly but is an implementation detail deferred to planning (Open Question 3).
