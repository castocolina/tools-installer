# tools-installer

## What This Is

tools-installer is an interactive, cross-platform (macOS/Linux, including immutable
Bazzite) Textual TUI and CLI that installs and manages a developer's AI-assisted dev
environment from a single declarative `registry.toml` catalog. It handles install
ordering, dependency drag-in, PATH repair, uninstall, and shell/environment tweaks so
a developer never has to sequence machine-bootstrap steps by hand. Python 3, managed
end-to-end by `uv` (interpreter version, venv, dependencies).

## Core Value

A developer can go from a bare machine to a working, correctly-ordered install
(system prerequisites -> user tools -> AI-agent tooling) entirely through the
catalog, with dependency drag-in resolving automatically and no manual ordering
knowledge required.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from the existing codebase (brownfield) — this is the first GSD planning pass over an already-working installer. -->

- ✓ Interactive Textual TUI catalog: browse/select tools grouped by Category, Priority, Audience, or Status, or as a flat sortable table — shipped pre-GSD
- ✓ Cross-platform install engine covering script/node/sdkman/github_release/tarball/app/dnf/apt/pacman/rpm_ostree/brew/cask methods — shipped pre-GSD
- ✓ Hard-dependency resolution via `Tool.requires`: transitive drag-in, deps-first topological order, cycle detection, unavailable-dependency skipping (`installer/deps.py`) — shipped pre-GSD
- ✓ PATH doctor: read-only audit plus an explicit apply-fix flow — shipped pre-GSD
- ✓ Registry-driven uninstall for userspace (download/app) artifacts, with "managed by Homebrew" vs. "removable here" classification — shipped pre-GSD
- ✓ Policies tab: pip/npm ban (shims + aliases) and curated cross-shell tweak bundles (docker shortcuts, countdown helper, claude skip-permissions, apt selective upgrade) written into `~/.myshellrc` — shipped pre-GSD
- ✓ One view registry / one navigation path / one apply workflow UI architecture (`installer/ui_common.py`, `.claude/architecture.md`) — shipped pre-GSD

### Active

<!-- Current scope: the catalog-tiers-and-dependency-chain PRD (1st of 7 in the 2026-09-04 planning batch). -->

- [ ] **REQ-catalog-tier-field**: Every registry tool declares a `tier` (system/user/ai) on the `Tool` model and registry schema, validated like `Priority`/`Audience`; `uv`/`pnpm`/`brew`/`sdkman` migrate to `tier="system"`
- [ ] **REQ-dependency-chain-requires**: Cross-tier `requires` chains resolve via the existing resolver with zero new resolver logic
- [ ] **REQ-catalog-tier-views**: The catalog splits into three tier-scoped top-level views (System/User/AI) reachable from the top nav
- [ ] **REQ-recommends-soft-dependency**: `Tool.recommends`, a soft-dependency field distinct from `requires`, surfaces (never auto-installs) complementary tools
- [ ] **REQ-install-failure-propagation**: A tool whose `requires` dependency failed earlier in the same run is skipped with a clear "dependency failed" outcome
- [ ] **REQ-uninstall-sweep-tweak-executables**: A full uninstall also removes tweak-managed executables, not only `Tool`-shaped artifacts
- [ ] **REQ-oh-my-zsh-plugin-config**: Oh-My-Zsh's bundled `git`/`docker` plugins are enabled via a config-array edit to `.zshrc`, reusing the existing rc-editing tweak mechanism

### Out of Scope

- New resolver/ordering logic keyed on `tier` — `requires` already handles ordering, cycle detection, and availability skipping; a second mechanism would drift out of sync (PRD Design Decisions)
- A tier-keyed "gate" blocking ai-tier selection until its system-tier `requires` resolves — redundant with the existing `requires` drag-in
- The actual new tool catalog additions (`oh-my-zsh`, `volta`, `ruby`, `kitty`, `wezterm`, `cursor-agent`, `antigravity`, `codegraph`, etc.) — covered by the companion catalog-expansion PRD, not yet ingested
- Postinstall actions (MCP registration, non-bundled shell plugin wiring) — covered by the companion postinstall-hooks PRD, not yet ingested
- External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step — explicitly deferred per the source PRD's Open Questions
- Package-manager policy, live package management, background maintenance daemon, and agent CLI ergonomics — the four remaining companion PRDs from this batch, deferred to their own future ingest passes

## Context

This is the first of seven PRDs from a 2026-09-04 planning batch being ingested one
at a time, in a deliberate dependency order — catalog-tiers-and-dependency-chain
first because it is foundational (Tier enum, tier-scoped views, the `recommends`
soft-dependency field, and two dependency-resolution gaps found by code review). The
remaining six (package-manager-policy, postinstall-hooks, catalog-expansion,
live-package-management, background-maintenance-daemon, agent-cli-ergonomics) will
be ingested in subsequent merge-mode passes immediately after this one, each
expected to extend ROADMAP.md with further phases — this is not the complete
project scope.

Codebase research performed while drafting the source PRD found that the
dependency-chain mechanism this PRD might otherwise have proposed building already
exists end-to-end (`Tool.requires`, `installer/deps.py:resolve_dependencies`, wired
from `installer/app.py` for every install run) — so the dependency-chain portion of
this milestone is a data problem (declare `requires` in `registry.toml`), not an
architecture problem.

The `REQ-install-failure-propagation` and `REQ-uninstall-sweep-tweak-executables`
requirements were both surfaced by a code review of the already-merged
dependencies-and-shell-tweaks work (commit `431a0a9`): its own PRD/plan specified
"soft-warn + skip dependents on failure", but `installer/session.py::run_installs`
never implemented the skip, and the uninstall planner only walks `Tool` entries,
missing `installer/tweaks.py`'s `ManagedExecutable` artifacts (e.g.
`tools-installer-wait-time`).

## Constraints

- **Tech stack**: Python 3, `uv`-managed (venv + deps + interpreter), Textual TUI, cross-platform macOS/Linux including immutable Bazzite — per `CLAUDE.md`, non-negotiable
- **Architecture**: one view registry (`installer/ui_common.py` `VIEWS`), one navigation path (`UnifiedApp.show_view`), one apply workflow (`ui_common.run_live`), `setup.py` is wiring-only — per `.claude/architecture.md`, "the bias is less total code"
- **No new resolver logic**: `requires` stays the single mechanism for install order, transitive drag-in, cycle detection, and unavailable-dependency skipping; `tier` must never be required to make a `requires` chain resolve — per PRD Design Decisions
- **Quality gates**: new/changed behavior covered by failing tests before implementation; `make validate` and `make test` (at the project's current coverage gate) must pass — per PRD Quality Standards and `CLAUDE.md`'s "never bypass a quality gate"

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `tier` gets three top-level catalog views, not an in-screen filter | Matches the user's actual bootstrap mental model (system -> user -> ai); resolved 2026-09-04 | — Pending |
| `tier` is strictly orthogonal to `Category`; `requires` remains the sole install-order mechanism | Avoids a second ordering mechanism drifting out of sync with the registry's actual `requires` data | — Pending |
| `recommends` is a deliberately separate, smaller mechanism from `requires` — never auto-installs | Preserves the requires/recommends distinction the feature exists to draw, in code and in the UI | — Pending |
| Oh-My-Zsh's `git`/`docker` plugins are a config-array edit to `.zshrc`, not `Tool` entries | They ship bundled inside oh-my-zsh and only need enabling — no download, no install method of their own | — Pending |
| `mmdc` stays on pnpm (`kind="node"`) — Homebrew and Volta both rejected after research | Upstream mermaid-cli's README states Homebrew is "no longer supported"; GitHub issue #1122 records brew-installed mmdc failing at runtime because the formula depends only on `node`. Volta's unrestricted npm postinstall buys nothing for mmdc (no lifecycle scripts of its own) while giving up pnpm's default-deny gate for puppeteer's postinstall. Weighed on stability, security, simplicity, and maintainability. | Phase 5 (05-03) |
| This phase adds new node-method mechanisms (`co_install`/`allow_build`/`versions`/`min_node`, a load-time validator, a version preflight and a replay policy) despite 05-CONTEXT.md `<specifics>` saying "no new mechanisms" | ROADMAP SC#3 cannot be met honestly without them: `requires` alone orders the install while leaving the dependent CLI unable to load its peer at runtime under pnpm's per-invocation isolation | Phase 5 |
| `java`'s SDKMAN candidate needs no pinned `version`. | Verified live in a Tier-3 container (colima+docker, ubuntu:24.04) — `sdk install java` completed non-interactively, exit 0, because SDKMAN's one interactive prompt requires an existing `$CURRENT` version that a first install never has, and this project's `?ci=true` bootstrap additionally closes that prompt's other guard condition for any future re-install through a clean bootstrap this installer performs (not claimed for a brownfield, pre-existing SDKMAN install). | Phase 6 (06-01) |
| Registry-authoring verification is recorded as a `# Verified {date}: ...` prose comment above the entry, never a checked-in snapshot of the verified source (D-01). | Lower friction, matches the project's existing ad hoc convention (`codegraph`/`mmdc`/`puppeteer`), avoids staleness risk from snapshotting upstream content that can change. | Phase 6 (06-01) |
| The general "prefer brew over other userspace package managers" preference is a documented-only registry-authoring guideline, not lint/test enforced (D-02); the SDKMAN carve-out for the Java toolchain named alongside it remains separately test-enforced (`tests/test_registry.py:122-140`), not additionally claimed unenforced. | Brew availability differs too much per OS/tool for a reliable automated "prefer brew" check, so the general preference stays prose; the carve-out already has its own test coverage from commit `0e05f50` and needs no new enforcement. | Phase 6 (06-01) |
| `oh-my-zsh` ships with explicit `env = { RUNZSH = "no", CHSH = "no", KEEP_ZSHRC = "yes" }` and `requires = ["zsh", "git"]`. | `install.sh`'s non-TTY defaults don't preserve `.zshrc` unless set explicitly, and `git` is a hard, undeclared prerequisite `install.sh` itself requires. See 07-01-PLAN.md/07-01-SUMMARY.md. | Phase 7 |
| `zsh`/`oh-my-zsh`'s Linux/Bazzite parity reuses the existing `podman` entry unchanged; no new container-runtime entry was added. | `podman`'s immutable-Linux-falls-to-brew shape already resolves correctly there, proven directly. See 07-01-SUMMARY.md. | Phase 7 |
| Apple Containers ships as a real `kind="brew" formula="container"` action, not a doc/version-gate entry. | Homebrew's own formula metadata declares a real `requirements` floor (`macos>=26`, `arch=arm64`), correcting REQUIREMENTS.md's speculative framing. See 07-02-SUMMARY.md. | Phase 7 |
| D-01's "shows disabled when unavailable" is satisfied by a `Platform`-derived `platform_could_support` signal threaded from `setup.py` through `CatalogScreen`, reusing the Uninstall view's dim/non-selectable-row mechanism — not `install_tool`'s `NO_METHOD` alone, and not a bare `resolve_methods` check. `Platform.os_version`/`Method.min_os_version` close the macOS-version case too (Apple Containers declares `min_os_version="26"`). | Cross-AI review found `NO_METHOD` architecturally unreachable from the catalog-browsing path (cycle 1), a bare availability check would wrongly dim brew-dependent tools on a fresh Mac (cycle 2), and the macOS-version gap was rejected as "documented but unimplemented" in both cycle 1 and cycle 2 — this is the resolution that closed all three, with no residual gap remaining. See 07-02-SUMMARY.md and `.claude/architecture.md`'s Registry-authoring guidelines. | Phase 7 |
| `gnu-bash` uses `cmd = "gnu-bash"` (not the literal `"bash"`) plus two arch-split `detect_path` methods. | macOS's own `/bin/bash` is always on PATH, so `cmd = "bash"` would make `is_installed` report the entry permanently satisfied and the install action would never run, on any Mac. See 07-02-SUMMARY.md. | Phase 7 |
| `kitty` ships with no Linux `github_release` fallback (no method at all on immutable Bazzite); `wezterm`'s Linux fallback is a checksum-verified AppImage `github_release` with `raw=true`, proven by a real Tier-3 download/checksum/execute run. | `kitty`'s Linux release assets are `.txz`, which this project's download extraction cannot open; `raw=true` bypasses extraction entirely. `kitty`'s Linux-cask absence is two independent facts (no formula exists; this project's own resolver blocks every cask on non-macOS regardless of what Homebrew ships upstream), not one causing the other. See 07-03-SUMMARY.md. | Phase 7 |
| `installer/resolve.py`'s `_applies`/`_RANK` dispatch tables gained an explicit `"uv-tool"` case (unconditional-True, rung 20) alongside the new executor and `METHOD_KINDS` entry. | 08-RESEARCH.md's own change list named only `model.py`/`executors.py`; without this fix, resolving any `uv-tool` method would raise `KeyError` from `resolve.py`'s closed native-package-manager fallthrough. See 08-01-PLAN.md/08-01-SUMMARY.md. | Phase 8 |
| `graphifyy`'s automated `[SUS]` legitimacy flag was discharged with a live, fail-closed PyPI + GitHub identity/age check before its registry entry was written, mirroring Phase 5's established automated-gate pattern rather than a `gate="blocking-human"` stop. | ONESHOT-RULES Rules 9/14 (the Tier-3 container tier, not a mid-run human stop, is this project's escalation path; package identity here is checkable from live metadata with an exit code). See 08-01-PLAN.md/08-01-SUMMARY.md. | Phase 8 |
| `cursor-agent`'s registry `cmd` uses the legacy `"cursor-agent"` symlink name, not the script's newer primary `"agent"` name. | The newer name risks colliding with an unrelated `agent` binary from a different installed CLI on a multi-agent-tool machine; `cursor-agent` is unambiguous and matches every other reference to this tool already in this project. See 08-02-PLAN.md/08-02-SUMMARY.md. | Phase 8 |
| `rtk`'s Linux install path uses two separate arch-gated `github_release` methods (musl for amd64, gnu for arm64), not one unscoped template, plus a same-project-confirmed `brew` fallback after the locked checksum-verified method. | Upstream's own release assets are asymmetric per architecture — a single template would 404 on one of them; the `recommends` wiring on `claude`/`opencode`/`codex`/`cursor-agent` (`codegraph`/`graphify`/`rtk`) is the honest RESULT of per-host verification (D-01), not a uniform default applied blindly, with `rtk`'s weaker instructions-based Codex integration recorded rather than smoothed over; `antigravity` stays unwired per D-01, deferred not dropped. See 08-03-PLAN.md/08-03-SUMMARY.md and 08-04-PLAN.md/08-04-SUMMARY.md. | Phase 8 |

---
*Last updated: 2026-09-06 after Phase 8 AI tier catalog expansion & uv-tool executor (08-01..08-04)*
