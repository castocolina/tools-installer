# Requirements: tools-installer

**Defined:** 2026-09-04
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.

## v1 Requirements

Requirements for this milestone (ingest batch 1/7: `catalog-tiers-and-dependency-chain`).
Each maps to exactly one roadmap phase.

### Catalog Tiers

- [x] **REQ-catalog-tier-field**: Every registry tool declares a `tier` (`system`/`user`/`ai`) on the `Tool` model and `registry.toml` schema, validated the same way an unknown `Priority` is rejected today; `uv`/`pnpm`/`brew`/`sdkman` migrate to `tier="system"`.
- [x] **REQ-catalog-tier-views**: The catalog's single flat view splits into three tier-scoped top-level views (System/User/AI) reachable directly from the top nav, each keeping the existing Category/Priority/Audience/Status/Table grouping, with cross-tier `requires` drag-in still visible from a dependent tool's own tier view.

### Dependency Chain

- [x] **REQ-dependency-chain-requires**: Cross-tier `requires` chains resolve via the existing resolver (`installer/deps.py:resolve_dependencies`) with zero new resolver logic, demonstrated end-to-end using `java`->`sdkman` (already shipped, decision-independent) as the primary proof case once `sdkman` carries `tier="system"`; `mmdc`->`pnpm` is a secondary example only if `mmdc`'s install method (batch 2, REQ-mmdc-install-decision) stays on pnpm — it may become `mmdc`->`puppeteer` instead if that decision resolves to brew.
- [x] **REQ-recommends-soft-dependency**: `Tool.recommends: tuple[str, ...] = ()`, a soft-dependency field distinct from `requires`, surfaces (never auto-installs) complementary tools via a one-action, non-blocking prompt when a tool such as `claude`/`opencode` is selected.

### Install/Uninstall Lifecycle

- [x] **REQ-install-failure-propagation**: `run_installs` tracks which tool ids failed during the current run and skips any subsequent tool whose `requires` intersects that failed set, emitting a distinct "dependency failed" outcome instead of letting the dependent run and fail with a confusing downstream error.
- [x] **REQ-uninstall-sweep-tweak-executables**: A full uninstall also removes tweak-managed executables (`installer/tweaks.py`'s `ManagedExecutable` artifacts, e.g. `tools-installer-wait-time`), not only `Tool`-shaped artifacts.

### Shell Tweaks

- [x] **REQ-oh-my-zsh-plugin-config**: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to the `plugins=(...)` array in `.zshrc`, reusing the existing `apply_block`/`strip_block` tweak mechanism — not a separate `Tool`/`Method`/`requires` catalog entry.

### Package Manager Policy (ingest batch 2/7: `package-manager-policy`)

- [x] **REQ-npx-ban**: `installer/guards.py:BANNED` gains an `"npx"` entry, treated identically to the existing `npm`/`pip`/`pip3` bans (same shim, alias, doctor/guard status, removability); existing ban tests extended to cover `npx`, not duplicated into a parallel file.
- [x] **REQ-npm-npx-redirect-policy**: `npx` becomes a clean, unconditional transparent redirect to `pnpm dlx "$@"` (no subcommand allowlist needed — confirmed `npx` is single-purpose); non-global `npm` (`install`/`add`/`run`/`exec`/`ci`/`publish` etc.) stays hard-blocked pending a separate subcommand-allowlist decision. Any redirect must preserve the underlying command's real exit code/stdout/stderr, implemented as a parallel `REDIRECTED` shim mechanism alongside the existing `BANNED` hard-block dict (never a generalization of `BANNED` itself) — `guard_status()`'s boolean shape is unchanged, with per-tool label text distinguishing "redirected to X" from "blocked".
  **Locked 2026-09-04 (Phase 4 discuss-phase, expanded from the original npx-only scope):** `pip`/`pip3` join the redirect list if research confirms `uv pip <subcommand>` (`install`/`uninstall`/`list`/`show`/`freeze`/`compile`) is a safe, argv-compatible drop-in for the pip invocations this project's shim actually needs to cover — implement the redirect in this same phase if research says yes; if research finds a gap, keep pip/pip3 hard-blocked and record the gap instead of forcing a redirect. `npm` itself (non-global) remains hard-blocked either way — its own subcommand-allowlist decision is still a separate, later concern.
- [x] **REQ-npm-global-volta-redirect**: Detect a `-g`/`--global` flag on `npm install`/`npm add` (and on `pnpm add -g` itself) and redirect that specific invocation shape to `volta install <pkg>` instead of `pnpm`; a non-global `npm install`/`npx` invocation still redirects to plain `pnpm`/`pnpm dlx` per REQ-npm-npx-redirect-policy. **Locked 2026-09-04 (Phase 4 discuss-phase):** included in Phase 4's scope specifically because it resolves REQ-pnpm-global-reinstall-mitigation's root cause (pnpm's global-package loss on self-update) for anything moved to Volta, rather than waiting on that requirement's original reactive mitigation. Gated on research first: whether `volta install` shells out to npm internally for the actual install step — if so, it inherits npm's unrestricted-postinstall-script behavior, losing pnpm's gated-postinstall security advantage for anything moved to Volta; this is the deciding factor for whether the redirect ships as a clean win or a documented security-for-stability tradeoff the user accepts explicitly.
- [x] **REQ-codegraph-github-release**: `codegraph`'s registry entry uses `kind="github_release"` (verified: prebuilt binary tarball, no npm involved), not `kind="node"`/`kind="script"`.
- [x] **REQ-mmdc-install-decision**: Decide and record `mmdc`'s install method explicitly (pnpm with documented mitigation, or Homebrew) — genuinely open, needs research into pnpm-vs-brew tradeoffs (postinstall-script security vs. the known global-install bug) and whether `volta` is a viable alternative; puppeteer/chrome-headless-shell remain required regardless of which manager installs mmdc itself, and whether that dependency applies identically on macOS vs. Linux is also unverified.
  User question (2026-09-04): could `volta` replace pnpm as the global installer for node-only packages, avoiding pnpm's version-upgrade global-package-loss bug entirely, and would it be equally or more secure? Unverified — needs real research, not assumption: volta manages its own install/shim directory rather than using `pnpm add -g`'s mechanism, so it plausibly sidesteps that specific bug, but it is unconfirmed whether volta's own global-install path still shells out to npm internally — if it does, it would inherit npm's unrestricted-postinstall-script behavior, losing the supply-chain-security advantage pnpm's gated postinstall scripts currently provide. This is a real tradeoff to resolve with research, not a clear win either way.
- [x] **REQ-puppeteer-catalog-entries**: `puppeteer` and `chrome-headless-shell` become their own catalog entries rather than an invisible peer-dependency of `mmdc`; `mmdc.requires` gains `["puppeteer"]` so `resolve_dependencies` drags it in automatically.
  **Amended 2026-09-05:** puppeteer's own postinstall (`node install.mjs`) downloads `chrome-headless-shell` into `~/.cache/puppeteer`, so it has no independent install path for a second catalog entry to model. 05-CONTEXT.md's Claude's-Discretion clause delegated this call; a test now asserts no `chrome-headless-shell` entry exists so the resolution cannot be silently undone.
- [ ] **REQ-pnpm-global-reinstall-mitigation**: For any tool that must stay on `pnpm add -g` despite the known global-install bug, snapshot the pnpm-managed global set and reinstall it together in one invocation after `pnpm` itself updates — the verified-correct mitigation for the bug's actual root cause. **Re-pointed to Phase 4 (2026-09-04 discuss-phase)**: Phase 4's `REQ-npm-global-volta-redirect` addresses the root cause preventively for anything moved to Volta (those tools are no longer pnpm-managed globals at all), so Phase 4 must first determine — after the Volta split — whether any catalog tool still needs `pnpm add -g` at all. If the residual set is empty, this requirement is satisfied by elimination; if any tool remains, the original snapshot-reinstall mechanism is still needed for that residual set and should be implemented in Phase 4 rather than deferred. No longer sequenced after Phase 12 — `REQ-update-action-manager-delegation`'s "update mechanism" dependency only applies if a residual pnpm-managed set actually remains after Phase 4's research. **Note (2026-09-05, R-03):** Phase 4 ships the mechanism, the read-only audit, and an explicit user-invoked Doctor remediation; the automatic post-pnpm-update trigger the requirement's own text names is NOT shipped in Phase 4 and is owned by Phase 12's `REQ-update-action-manager-delegation`. Decision R-03 in `.planning/phases/04-package-manager-redirect-policy/04-CONTEXT.md`, taken autonomously during the 2026-09-05 run with no user available to confirm, so it is open to reversal by the user at any time.
- [x] **REQ-sdkman-exclusivity**: `java`/`gradle`/`maven`/`groovy`/`springbootcli` install exclusively through SDKMAN, never a native/brew fallback, with SDKMAN's own install correctly self-detected (no re-running its bootstrap on every JVM-tool install). Shipped ahead of plan in commit `0e05f50`; hardened in Phase 6 with a real Tier-3 container e2e verification of `sdk install java` (colima+docker) and dated `# Verified` comments recording the finding. `java`'s SDKMAN candidate needs no pinned `version` — resolved: SDKMAN's only prompt requires an existing `$CURRENT` version, never present on a first install.
- [x] **REQ-registry-authoring-verification-checklist**: Established in `.claude/architecture.md`'s "Registry-authoring guidelines" section — a mandatory per-tool, per-OS verification step for future registry additions, recorded via a `# Verified {date}: ...` comment citing what was checked (D-01), not a stronger checked-in excerpt.
- [x] **REQ-brew-preference-guideline**: "Prefer brew over other userspace package managers" documented in `.claude/architecture.md` as a pure-convention guideline (D-02, no lint/test enforcement), with SDKMAN named as the Java-toolchain's carve-out (REQ-sdkman-exclusivity, already test-enforced by `test_java_tools_install_exclusively_through_sdkman`).

### Catalog Expansion (ingest batch 3/7 part A: `catalog-expansion`)

- [x] **REQ-uv-tool-executor**: New `installer/executors.py` `kind="uv-tool"`, mirroring the existing `"node"` kind's shape (`uv tool install <pypi_pkg>` instead of `pnpm add -g <npm_pkg>`), using this project's already-trusted `uv` toolchain. `graphify`'s registry entry uses it (`kind="uv-tool"`, package `graphifyy` — double-y, note the PyPI package name differs from the CLI command `graphify`; `requires = ["uv"]`). Done: 08-01-PLAN.md/08-01-SUMMARY.md (also fixed a real `resolve.py` `_applies`/`_RANK` `KeyError` gap found during grounding).
- [x] **REQ-system-tier-shell-container-entries**: New system-tier registry entries: `zsh`, `oh-my-zsh` (official install script, `requires = ["zsh"]` — verify its actual `.zshrc`-rewriting behavior before treating it as a safe reviewable `kind="script"` candidate), `gnu-bash` (macOS-only, brew), Apple Containers (macOS-only, native `container` CLI — may be a version-gate/doc entry with nothing to actually install on a current macOS).
  - status: whether there is anything to actually install for Apple Containers on a current macOS, or whether the entry is purely a doc/version-gate, is unresolved (Open Question 4).
- [x] **REQ-terminal-emulator-entries**: `kitty`, `wezterm` as user-tier entries — brew on macOS (both in homebrew-core); Linux via distro package manager or the existing GitHub-release download path if no native package exists, verified live before adding (per this project's registry-authoring convention).
- [x] **REQ-agent-host-entries**: `antigravity`, `cursor-agent` as ai-tier entries via their verified official install method (not assumed); `codegraph` via `kind="github_release"` (per batch 2's `REQ-codegraph-github-release` finding, inherited not re-verified).
  - status: resolved. `antigravity`/`cursor-agent`'s install methods were live-verified this milestone (each vendor's own curl|bash script, fetched and read verbatim). Done: 08-02-PLAN.md/08-02-SUMMARY.md.
- [x] **REQ-rtk-github-release**: `rtk` ("Rust Token Killer") registry entry, `kind="github_release"` from `rtk-ai/rtk` (confirmed via GitHub API: pure Rust, prebuilt per-platform tarballs, `checksums.txt` release asset usable with this project's existing checksum-verification feature). Default branch is `develop`, not `main` — only matters if anything references the branch directly. Done: 08-03-PLAN.md/08-03-SUMMARY.md (real arch-gated musl/gnu Linux split, real Tier-3 container verification).
- [x] **REQ-recommends-wiring-agent-hosts**: Instantiates batch 1's `REQ-recommends-soft-dependency` mechanism with concrete data — `claude`/`opencode`/`codex`/`cursor-agent`/`antigravity` each gain `recommends = ["codegraph", "graphify", "rtk"]` (adjusted per tool as appropriate). Done: 08-04-PLAN.md/08-04-SUMMARY.md — `claude`/`opencode`/`codex`/`cursor-agent` all carry the real researched set; `antigravity` intentionally stays unwired per CONTEXT.md D-01 (deferred, not dropped).
- [x] **REQ-linux-bazzite-shell-parity**: New system-tier tools (`zsh`, `oh-my-zsh`) get a real Linux/Bazzite install path, not just macOS; reuses the existing `podman` catalog entry for the container-runtime story on Linux/Bazzite (Apple Containers is macOS-only). Corrects an earlier draft's claim that "brew doesn't need curl on Bazzite" — Homebrew's bootstrap is `curl|bash` on every platform including Linux; the real distinction is that Bazzite's base image already ships `curl`/`git`/build tooling, not that brew needs less there.

### Postinstall Hooks (ingest batch 3/7 part B: `postinstall-hooks`)

- [ ] **REQ-postinstall-field**: Optional `postinstall` field declared per tool/`Method` (not kind-agnostic), either inline (short command string) or a `postinstall_script` file reference for anything multi-line, mirroring `installer/tweaks.py`'s `ManagedExecutable`/`helper_assets/` precedent — keeps `registry.toml` from bloating with long inline scripts. Runs through the same trusted `Runner` seam every other executor uses.
- [ ] **REQ-postinstall-execution-timing**: The postinstall step dispatches immediately after the specific `Method` that just ran reports success (not batched, not deferred to end-of-session), and is aware of which `Method`/`kind` actually installed the tool. A postinstall failure is surfaced as a distinct warning, never marks the tool's own install as failed (the binary is on PATH and usable regardless).
- [ ] **REQ-postinstall-idempotency-live-check**: Idempotency via a live check ("is the effect already present" — e.g. is the MCP entry already in a host's config file), not a new state-tracking database — consistent with this codebase's existing all-live-check convention (`status.is_installed`, `guard_status`, `has_managed_block`). `shutil.which` is a synchronous PATH lookup, not a subprocess spawn — confirmed not to hang or block the Textual event loop.
- [ ] **REQ-postinstall-noninteractive-only**: A postinstall command must run unattended to completion; a tool whose only postinstall/setup path is interactive is not a candidate for this mechanism — hard requirement, since an interactive step would hang the TUI's live-apply flow with no way to answer it.
- [ ] **REQ-codegraph-mcp-postinstall**: After `codegraph` installs, run its global MCP-registration step for each of `claude`/`codex`/`opencode`/`cursor-agent` that is already installed on this machine (never installing those hosts as a side effect); a documented no-op when none are installed. The proving case for the whole postinstall mechanism — depends on `codegraph` existing in the registry (REQ-agent-host-entries, this same batch).
  - status: the exact non-interactive invocation for codegraph's MCP-registration step (flags/env vars) is deferred research at implementation time, per the source PRD's own framing — not resolved here (Open Question 3).

### Agent CLI Ergonomics (ingest batch 4/4 part A: `agent-cli-ergonomics`)

- [ ] **REQ-codex-skip-tweak**: A `codex-skip` tweak, parallel to the existing `claude-skip` tweak, aliasing `codex` to its bypass-permissions flag with user-supplied flags respected (appended, never dropped).
  - status: codex's exact current flag name is unverified — needs the same live-verification pass every registry addition gets (Open Question 2).
- [ ] **REQ-opencode-auto-tweak**: An `opencode-auto` tweak aliasing `opencode` to `opencode --auto` — explicitly *not* a full bypass-permissions equivalent (explicit deny rules still apply); Policies detail-panel copy must be honest about this narrower semantic so it isn't mistaken for `claude-skip`'s full bypass.
- [ ] **REQ-cursor-agent-default-model-wrapper**: A `cursor-agent`/`cursor` wrapper that injects a plain, live-verified `--model <slug>` (no bracket syntax — confirmed unimplemented by a Cursor employee, not just buggy) on any bare invocation with no `--model` passed, since cursor-agent's model selection is stateful (persists across sessions) and a bare non-interactive call would otherwise silently inherit whatever was last selected anywhere. Never claims to set 1M context (confirmed interactive-Max-Mode-only, unreachable non-interactively).
  - status: the exact current high-effort "sol" model slug is unverified — must be confirmed via `cursor-agent`'s own live model-listing command at implementation time, never typed from memory (Open Question 1, narrowed from the original bracket-syntax question which is now fully resolved).
- [ ] **REQ-agent-tweak-self-update-durability**: All three permissive-mode tweaks use a shell alias/function (`installer/tweaks.py`'s existing mechanism), not a file-based shim in the tool's own install directory — an alias lives in shell config, not the path a self-updating binary rewrites, and shell alias/function lookup happens before PATH search. `cursor-agent`'s wrapper specifically needs a shell *function* (not a plain alias), since it must conditionally omit its injection when the user already passed `--model`.

### Background Maintenance Daemon (ingest batch 4/4 part B: `background-maintenance-daemon`)

- [ ] **REQ-launchd-prune-policy**: A new `daemon_policy` factory (parallel to `ban_policy`/`tweak_policy` in `installer/policy.py`) installs/removes a macOS-only LaunchAgent running the existing `scripts/prune-user-tmpdir.sh --apply` daily via `StartCalendarInterval`, with `--days` defaulting to 3 (the script's own default, kept as a script-accepted param, not hardcoded higher just because it's unattended). No changes to the prune script's own logic/safety checks (dry-run default, `lsof` open-file skip).
- [ ] **REQ-daemon-log-diagnostics**: Scheduled runs write to a single append-mode log file under the existing managed-state directory convention (one file, not one-per-run, capped by simple size/age truncation); the Policies view's detail panel for this policy gains a "last run: <timestamp>, <N> items removed" line plus a keybinding to view the log — not a new top-level Diagnostics view (would violate the one-view-registry standard for a single script's output).
- [ ] **REQ-daemon-dependency-gating**: `fd`/`rg` are declared as `requires` on this policy (matching the `docker` tweak's `watch` dependency pattern) but the policy's `apply` never refuses to run when they're missing — it degrades to the script's own find/grep fallback (already confirmed in the script itself), surfaced via the existing `missing_requires` "recommended but not required" UI with no new mechanism.

### Live Package Management (ingest batch 4/4 part C: `live-package-management`)

- [ ] **REQ-version-aware-status-github**: For `github_release`-kind tools, resolve current installed version (run the tool's own `--version` flag and parse it) and compare against the already-working `resolve_github_tag`. A tool with no reliable version-check mechanism shows "unknown," never a false "up to date." MVP piece #1 (low effort, low risk — reuses an existing, tested resolver).
- [ ] **REQ-cached-timestamped-version-state**: A local JSON cache file, one entry per tool (`tool_id`, `latest_version`, `checked_at`) — an entry older than 7 days shows a stale marker and triggers background re-check; a fresh session doesn't refetch everything, only what's gone stale. MVP piece #2.
- [ ] **REQ-background-version-refresh-worker**: A Textual `Worker`-based background refresh, consistent with the existing `run_live` async pattern, that never blocks first paint or keypresses; network failures degrade to "unknown," never crash or silently retry forever. MVP piece #3.
  - status: whether refresh fires on catalog load or only on an explicit "check for updates" action is unresolved (Open Question 1) — the user's own recollection favored on-load, weighed against real network/latency tradeoffs.
- [ ] **REQ-manager-version-resolution**: `brew outdated`/`pnpm outdated -g`/`uv tool list --outdated`-equivalent resolution (verify exact commands, not assumed) as the authoritative current+latest source for brew/pnpm/uv-tool-managed entries — each needs its own `Runner`-shaped seam per manager, not raw subprocess calls in the TUI layer. MVP piece #4.
- [ ] **REQ-update-action-manager-delegation**: A manual "update" action parallel to install/uninstall, delegating to the tool's actual owning manager (this installer's own path, brew, pnpm, or uv tool) rather than assuming this installer's executor owns every tool; reuses `UninstallState`'s existing "managed elsewhere" concept rather than inventing a parallel one. MVP piece #5, last of the MVP set — **this is the "update mechanism" batch 2's `REQ-pnpm-global-reinstall-mitigation` was waiting on; that dependency is now unblocked** (see its updated status entry below).
- [ ] **REQ-manager-drift-alerting**: If a tool is currently installed via `pnpm`/`npm`/`npx`/`pnpx` and a newer/safer version is available via `brew`, surface a distinct alert (changing which manager owns a tool is a bigger action than a version bump) — the alert half only, not auto-remediation (auto-updating the registry + filing a GitHub issue is explicitly deferred, needs a GitHub API/auth story this project doesn't have). Deferred, not MVP — depends on REQ-manager-version-resolution existing first, but cheap once it does.

## v2 Requirements

None deferred. All seven PRDs from the 2026-09-04 planning batch
(`catalog-tiers-and-dependency-chain`, `package-manager-policy`,
`catalog-expansion`, `postinstall-hooks`, `live-package-management`,
`background-maintenance-daemon`, `agent-cli-ergonomics`) are now fully
ingested as of this batch.

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
| REQ-catalog-tier-field | Phase 1 | Complete |
| REQ-dependency-chain-requires | Phase 1 | Complete |
| REQ-catalog-tier-views | Phase 2 | Complete |
| REQ-recommends-soft-dependency | Phase 2 | Complete |
| REQ-install-failure-propagation | Phase 3 | Complete |
| REQ-uninstall-sweep-tweak-executables | Phase 3 | Complete |
| REQ-oh-my-zsh-plugin-config | Phase 3 | Complete |
| REQ-npx-ban | Phase 4 | Complete |
| REQ-npm-npx-redirect-policy | Phase 4 | Complete (pip/pip3 stay hard-blocked; doctor labels distinguish redirect from block) |
| REQ-npm-global-volta-redirect | Phase 4 | Complete |
| REQ-pnpm-global-reinstall-mitigation | Phase 4 (mechanism + manual trigger) / Phase 12 (automatic trigger) | Partial |
| REQ-codegraph-github-release | Phase 5 | Complete |
| REQ-mmdc-install-decision | Phase 5 | Complete |
| REQ-puppeteer-catalog-entries | Phase 5 | Complete |
| REQ-sdkman-exclusivity | Phase 6 | Done |
| REQ-registry-authoring-verification-checklist | Phase 6 | Done |
| REQ-brew-preference-guideline | Phase 6 | Done |
| REQ-system-tier-shell-container-entries | Phase 7 | Done |
| REQ-terminal-emulator-entries | Phase 7 | Done |
| REQ-linux-bazzite-shell-parity | Phase 7 | Done |
| REQ-uv-tool-executor | Phase 8 | Done |
| REQ-agent-host-entries | Phase 8 | Done |
| REQ-rtk-github-release | Phase 8 | Done |
| REQ-recommends-wiring-agent-hosts | Phase 8 | Done |
| REQ-postinstall-field | Phase 9 | Pending |
| REQ-postinstall-execution-timing | Phase 9 | Pending |
| REQ-postinstall-idempotency-live-check | Phase 9 | Pending |
| REQ-postinstall-noninteractive-only | Phase 9 | Pending |
| REQ-codegraph-mcp-postinstall | Phase 9 | Pending (depends on Phase 8) |
| REQ-codex-skip-tweak | Phase 10 | Pending |
| REQ-opencode-auto-tweak | Phase 10 | Pending |
| REQ-cursor-agent-default-model-wrapper | Phase 10 | Pending |
| REQ-agent-tweak-self-update-durability | Phase 10 | Pending |
| REQ-launchd-prune-policy | Phase 11 | Pending |
| REQ-daemon-log-diagnostics | Phase 11 | Pending |
| REQ-daemon-dependency-gating | Phase 11 | Pending |
| REQ-version-aware-status-github | Phase 12 | Pending |
| REQ-cached-timestamped-version-state | Phase 12 | Pending |
| REQ-background-version-refresh-worker | Phase 12 | Pending |
| REQ-manager-version-resolution | Phase 12 | Pending |
| REQ-update-action-manager-delegation | Phase 12 | Pending |
| REQ-manager-drift-alerting | Phase 12 | Deferred (stretch, not MVP) |

**Coverage:**
- v1 requirements: 42 total (added REQ-npm-global-volta-redirect 2026-09-04)
- Mapped to phases: 42
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-04*
*Last updated: 2026-09-04 after ingest batch 4/4 (agent-cli-ergonomics + background-maintenance-daemon + live-package-management) merged — all 7 PRDs of the 2026-09-04 batch now ingested*
