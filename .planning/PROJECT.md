# tools-installer

## What This Is

tools-installer is an interactive, cross-platform (macOS/Linux, including immutable
Bazzite) Textual TUI and CLI that installs and manages a developer's AI-assisted dev
environment from a single declarative `registry.toml` catalog. It handles install
ordering, dependency drag-in, PATH repair, uninstall, and shell/environment tweaks so
a developer never has to sequence machine-bootstrap steps by hand. Every screen shows
one truthful state per tool on this host (present, health, owner, version, removable with
proof), and install, update, removal and configuration follow one per-method lifecycle
contract with install receipts. Python 3, managed end-to-end by `uv` (interpreter
version, venv, dependencies).

## Core Value

A developer can go from a bare machine to a working, correctly-ordered install
(system prerequisites -> user tools -> AI-agent tooling) entirely through the
catalog, with dependency drag-in resolving automatically and no manual ordering
knowledge required, and every screen tells the truth about what is on the host.

## Current Milestone: v0.51.0 Onboard terminal tools

**Goal:** Every terminal emulator and IDE in the catalog, and every one added later, ships with the same defaults: zsh as the launched shell on Linux (Bazzite included), Option/Alt+Left/Right word navigation on macOS, and a clear-screen shortcut (Cmd+K on macOS, Ctrl+Shift+K on Linux), all applied through a tool-onboarding skill that carries them as rules; the pending tool onboardings run through the same skill.

**Target features:**
- Tool-onboarding skill refactor: terminal and IDE defaults become rules, not questions (backlog 999.18) — first phase
- Terminal defaults applied to the terminals already in the catalog: kitty, WezTerm, Konsole (owner decision), herdr pass-through (backlog 999.19)
- Ghostty, Herdr IDE and iTerm2 onboarded through the skill (backlog 999.20-999.22)
- Xcode CLT, Bruno, AWS CLI, gh-stack and Playwright MCP onboarded through the skill

## Last Shipped Milestone: v0.50.0 Truthful lifecycle

Shipped 2026-11-16 (started 2026-10-13): 17 phases (17-26 with inserted 23.1, 23.2, 24.1-24.5), 276 plan summaries, 121/121 requirements. Every screen tells the truth about each tool on this host, and install, update, removal and configuration follow one per-method contract with install receipts as removal proof.

**Shipped:**
- Host hazards H1-H7 closed, CI green on Ubuntu and macOS, PR check required (17)
- Registry truth: unknown-key rejection, `verified` dates, digest checks, smoke runs, `make verify-registry` (18)
- One `ToolState` with a closed `Health` set and install receipts; install plan with dispositions and one engine for the TUI and headless (19, 20)
- One screen family; Uninstall, Policies and Doctor as projections of the shared state (21)
- Per-method lifecycle contract and configuration as a lifecycle step (22, 23)
- Host safety, install-time tuning, Schedules view, catalog-audit skill, guard retirement, brew -> bun -> volta priority (23.1, 23.2, 24.2-24.5)
- herdr, Alacritty and Neovim onboarded through the tool-onboarding skill, with a three-distro container e2e (24, 24.1)
- Lean-up and commit/push quality hooks with a protected branch -> CI -> fast-forward `main` flow (25, 26)

**Design source:** `.planning/research/2026-10-13-target-architecture.md` and `.planning/research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md`. Audit: `.planning/v0.50.0-MILESTONE-AUDIT.md`.

**Next milestone:** v0.51.0 Onboard terminal tools (started 2026-11-16).

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from the existing codebase (brownfield) — this is the first GSD planning pass over an already-working installer. -->

- ✓ Interactive Textual TUI catalog: browse/select tools grouped by Category, Priority, Audience, or Status, or as a flat sortable table — shipped pre-GSD
- ✓ Cross-platform install engine covering script/node/sdkman/github_release/tarball/app/dnf/apt/pacman/rpm_ostree/brew/cask methods — shipped pre-GSD
- ✓ Hard-dependency resolution via `Tool.requires`: transitive drag-in, deps-first topological order, cycle detection, unavailable-dependency skipping (`installer/deps.py`) — shipped pre-GSD
- ✓ PATH doctor: read-only audit plus an explicit apply-fix flow — shipped pre-GSD
- ✓ Registry-driven uninstall for userspace (download/app) artifacts, with "managed by Homebrew" vs. "removable here" classification — shipped pre-GSD
- ✓ Policies tab: curated cross-shell tweak bundles written into `~/.myshellrc` — shipped pre-GSD (the pip/npm ban shims and aliases were retired in v0.50.0, GUARD-01..06; claude/codex skip-permissions and agent attribution moved to install-time tuning, TUNE-01)
- ✓ One view registry / one navigation path / one apply workflow UI architecture (`installer/ui_common.py`, `.claude/architecture.md`) — shipped pre-GSD
- ✓ Catalog tiers (system/user/ai) with tier-scoped views, `recommends`, failure propagation, tweak-executable uninstall sweep, Oh-My-Zsh bundled plugins — v0.49.0
- ✓ Package-manager redirect policy (retired in v0.50.0, GUARD-01..06), catalog expansion (system/user/AI tiers), `uv-tool` executor, postinstall hooks, agent CLI ergonomics, background maintenance daemon (macOS launchd, Linux systemd user timer) — v0.49.0
- ✓ Version-aware status and owner-routed updates, live in-TUI install execution, persistent wizard settings, Owner column and Uninstall manager attribution, terminal default shell on immutable hosts, self-deduping PATH, filesystem-based detection — v0.49.0 (partially: see the 2026-10-13 audit; 14 partial and 53 deferred promises carried forward; closed by v0.50.0)

- ✓ Host safety and CI: the seven hazards closed (no deletion of unproven artifacts, no link to a directory, no write into the CWD, atomic rc and shim writes, red status and non-zero exit on any failure), CI green on both OSes, PR check required — v0.50.0 (SAFE-01..09, CI-01..03, Phase 17)
- ✓ Registry truth: unknown-key rejection, `verified` dates, GitHub digest checks, smoke runs that fall through, macOS stub detection, `make verify-registry`, audit data fixes — v0.50.0 (REG-01..10, Phase 18)
- ✓ One `ToolState` per tool with a closed `Health` set and one health mark, published in one swap, with an atomic install receipt per tool — v0.50.0 (STATE-01..07, Phase 19; STATE-07 skill-pack status superseded by HOST-01)
- ✓ Install plan with dispositions (install / update / repair / reconfigure / reinstall `r` / skip / blocked); TUI and headless run one plan and one engine, exit code from outcomes — v0.50.0 (PLAN-01..08, Phase 20)
- ✓ One screen family: every view reflects every mutation; Uninstall, Policies and Doctor are projections of the shared state; removal on a worker — v0.50.0 (UI-01..08, Phase 21)
- ✓ Per-method lifecycle contract: script `paths`/`remove`/`update`, tool-level `config_paths`, receipts as the only removal proof, native installs handed off, leftover-checking container e2e — v0.50.0 (LIFE-01..10, Phase 22)
- ✓ Configuration as a lifecycle step: agent-host hooks that follow hosts in and out, shell init offered and removed with the tool, `SHELL` kept on zsh — v0.50.0 (CONF-01..12, Phase 23; the asked CONF-08/09/11/12 variants superseded by TUNE)
- ✓ Host safety: skill-pack, rtk, GSD, openspec and spec-kit entries dropped, retired receipts removable, sandboxed tests with a real-HOME fingerprint, installs and removals only in containers — v0.50.0 (HOST-01..05, Phase 23.1)
- ✓ Install-time tuning with no question (agent co-authoring off and auto-approve, zsh plugins and theme, VS Code lean), Policies trimmed, live run indicator, Copilot CLI in the catalog, present dependencies runnable in-session — v0.50.0 (TUNE-01..07, Phase 23.2)
- ✓ Onboarding through the skill: herdr, Alacritty (Distrobox cargo build on Bazzite) and Neovim; skill-judge scored skill; three-distro container e2e; real-host UAT — v0.50.0 (ONB-01..10, Phases 24, 24.1)
- ✓ Schedules view with user-level timers (cache cleanup, 6-hourly agent-CLI updates, cursor-agent model shim) — v0.50.0 (SCHED-01..05, Phase 24.2)
- ✓ Catalog-audit skill (`make audit-catalog`), first run covering opencode v2 and Pi MCP — v0.50.0 (AUDIT-01..04, Phase 24.3)
- ✓ npx/npm/pip guard shims, aliases and redirects retired; a launch removes the installer's own leftovers byte-exact — v0.50.0 (GUARD-01..06, Phase 24.4)
- ✓ Install priority brew -> bun -> volta/pnpm with a `bun` method kind and bun owner, receipts and updates — v0.50.0 (PRIO-01..07, Phase 24.5)
- ✓ Lean-up: dead code out, `installer/compose.py` under pyright and coverage, `wizard_app.py` split, run log bounded at 5,000 lines — v0.50.0 (LEAN-01..04, Phase 25)
- ✓ Commit hook and push gate, per-gate `make` targets, branch -> green CI -> fast-forward `main` with `enforce_admins` — v0.50.0 (HOOK-01..06, Phase 26)

### Active

<!-- v0.51.0 scope. Evidence and owner decisions for the carried items: .planning/todos/TRIAGE-2026-11-16.md. -->

- [ ] Tool-onboarding skill: terminal and IDE defaults as rules (zsh on Linux, Option/Alt word navigation on macOS, Cmd+K / Ctrl+Shift+K clear) — v0.51.0 (999.18)
- [ ] Terminal defaults for kitty, WezTerm, Konsole (owner decision) and herdr pass-through — v0.51.0 (999.19)
- [ ] Onboard Ghostty, Herdr IDE and iTerm2 through the skill — v0.51.0 (999.20-999.22)
- [ ] Onboard Xcode CLT (owner decision: brew install.sh or softwareupdate), Bruno, AWS CLI, gh-stack and Playwright MCP through the skill — v0.51.0
- [ ] Registry update bot in GitHub Actions: catalog pin bumps proposed as a bot branch, landed by the owner — v0.51.0 (Phase 33)
- [ ] Daily update check with a desktop notification on Bazzite and macOS (amends the 24.2 notification cut) — v0.51.0 (Phase 34)
- [ ] Opt-in `update-all` schedule, package managers first (amends 24.2 SCHED-01 with a per-row default) — v0.51.0 (Phase 35)

Carried, not in v0.51.0:
- [ ] Declare the removal footprint (`config_paths`, script `paths`) for about 26 catalog entries and bring install-method and update-route currency up to date (Backlog 999.14, 999.15)
- [ ] Replace codegraph with codebase-memory-mcp in the catalog and its postinstall hooks (todo 2026-11-14; owner decision on the AGENTS-TOOLING writer)
- [ ] Small lifecycle fixes: zip version probe (999.16), TLS retry for release and app downloads, cask uninstall that needs root, fnm vendor block cleanup, run-log tail after a shrink, transient xdist test errors
- [ ] Duplicate-code gate with its own `make` target and hook entry (999.17)
- [ ] Adopt the branch -> CI -> fast-forward `main` flow in the outside tools (GSD merge helpers, ai-kit-commit-fold, GSD phase-complete); direct pushes to `main` are now rejected
- [ ] Close the Phase 16 UAT debt or accept later-phase coverage (999.7); run the installer on macOS and Apple Silicon (deferred since v0.49.0)

### Out of Scope

- New resolver/ordering logic keyed on `tier` — `requires` already handles ordering, cycle detection, and availability skipping (PRD Design Decisions)
- External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step — deferred per the source PRD's Open Questions
- `rpm-ostree` layering on immutable hosts — needs a reboot; Bazzite recommends Flatpak, Homebrew, Distrobox first
- Any sudo/pkexec/doas performed by this project itself — zero-sudo invariant; native dnf/apt/pacman installs are handed off as the exact command (O1, 2026-10-13)
- New method kinds for dmg / `app {ver}`, a `service` start/stop step, a keep/delete/ask config enum, git-config/completion writers — v0.50.0 ultra cut (target architecture §9.1); the two kinds that shipped anyway are `cargo_distrobox` (O5) and `bun` (PRIO-02), each with a proven case
- REQ-manager-drift-alerting — dropped 2026-10-13: the off-policy owner note already says another manager owns the tool
- Skill packs, rtk, GSD, openspec and spec-kit as catalog entries — owner decision in Phase 23.1 (HOST-01): they are not installer scope, and nothing in the installer or its tests may install them
- npx/npm/pip guard shims, ban aliases and PATH redirects — retired in Phase 24.4 (GUARD-01..06); the launch only removes the installer's own leftovers
- Agent-tuning and zsh-theme knobs as Policies rows — install-time tuning applies them with no question (TUNE-04); a new requirement becomes a Policies knob only if it lies outside any install

## Context

**Current state (2026-11-16):** v0.50.0 "Truthful lifecycle" shipped (17 phases, 276 plan summaries, 121/121 requirements). Codebase: about 44,000 lines of Python in `installer/`, `devtools/` and `setup.py`, about 133,600 lines in `tests/`, 86 catalog entries, 90% coverage gate. Phase 25 split `wizard_app.py` (793 lines) and moved composition to `installer/compose.py`. `main` is protected (`enforce_admins`, both CI checks required on the exact SHA); changes land by branch push, green CI, fast-forward. The milestone audit (`.planning/v0.50.0-MILESTONE-AUDIT.md`) found no unsatisfied requirement and no blocker; its one gap, 14 stale phase verifications after Phase 26, was closed by re-verification (0d04c5fc).

**Known issues and technical debt (none blocking, about 245 items):**
- Nyquist `VALIDATION.md` is still draft for 14 of 17 phases; 18 requirements lack `requirements-completed` in SUMMARY frontmatter (metadata only).
- Integration warnings W1-W5: `--run-schedule` skips launch repairs by design; a retired `host_setup` receipt still parses; `flow='guard'` naming collision; a stale `make setup` in a dated handoff; two close `postinstall` module names in the onboarding skill.
- Phase 26 left 7 open review Info items, owner decision IN-06 (gate-read pathspecs would refuse a local-only `.claude/CLAUDE.md`), and a flaky-test mitigation under xdist that is not a root-cause fix.
- macOS and Apple Silicon were never run locally; Phase 16 UAT tests 2-4 stay open (999.7).

**Earlier context (v0.49.0 ingestion, 2026-09-04):** the notes below record how the catalog-tiers PRD was ingested; the other six PRDs of that batch shipped in v0.49.0.

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

- **Tech stack**: Python 3, `uv`-managed (venv + deps + interpreter), Textual TUI, cross-platform macOS/Linux including immutable Bazzite — per `AGENTS.md`, non-negotiable
- **Architecture**: one view registry (`installer/ui_common.py` `VIEWS`), one navigation path (`UnifiedApp.show_view`), one apply workflow (`ui_common.run_live`), `setup.py` is wiring-only — per `.claude/architecture.md`, "the bias is less total code"
- **No new resolver logic**: `requires` stays the single mechanism for install order, transitive drag-in, cycle detection, and unavailable-dependency skipping; `tier` must never be required to make a `requires` chain resolve — per PRD Design Decisions
- **Quality gates**: new/changed behavior covered by failing tests before implementation; the commit hook's six static gates and the push gate's `make test` (90% coverage gate) must pass on the exact tree; the hooks run them, so nobody runs `make validate && make test` by hand first (owner rule 2026-11-20); every gate is its own `make` target and hook entry (commit hook for static checks, push gate for the full suite) — per PRD Quality Standards and `AGENTS.md`'s "never bypass a quality gate"
- **Host safety**: tests run in a scratch `HOME`; real installs and removals run only in disposable containers; agents never run `make run`, `make fix`, `make uninstall`, `make doctor` or `make dev-setup` on the real host — per `AGENTS.md` (Phase 23.1, 26)
- **Zero sudo**: no code path runs `sudo`, `pkexec` or `doas`; root work is handed off as the exact command (O1)
- **Merge flow**: changes reach `main` by branch push, green CI on both OSes and fast-forward; direct pushes to `main` are rejected, admins included (Phase 26)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v0.50.0 is built from a ponytail-ultra target architecture, not from per-phase fixes | v0.49.0 audit: seven to ten places answered "installed / owner / removable" differently | ✓ Good — 121/121 requirements, integration clean, 7/7 flows trace (v0.50.0 audit) |
| Native package installs are handed off as a command, never run with sudo (O1) | Zero-sudo invariant; the TUI child has no usable tty | ✓ Good — LIFE-02, Phase 22 |
| Receipts are the only removal proof; nothing unproven is deleted, in CLI or TUI | Uninstall deleted files it could not prove it wrote (F1, AR-01) | ✓ Good — Phases 17, 19, 22 |
| Alacritty on Bazzite: cargo build in a throwaway Distrobox, native binary on the host, container and image deleted (O5) | Measured 2026-10-13: 35 s build, 12 MB permanent vs 2.4 GB for a persistent Distrobox; runs natively, no shell-inside-container issue | ✓ Good — shipped in Phase 24, UAT tests 6-8 pass |
| Ponytail joins GSD `agent_skills` as `global:ponytail:ponytail` (Claude only) | Plugin skills load only in Claude; no vendored copy to keep in sync | — Pending |
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
| `graphifyy`'s automated `[SUS]` legitimacy flag was discharged with a live, fail-closed PyPI + GitHub identity/age check before its registry entry was written, mirroring Phase 5's established automated-gate pattern rather than a `gate="blocking-human"` stop. | The run playbook escalation rule (the Tier-3 container tier, not a mid-run human stop, is this project's escalation path; package identity here is checkable from live metadata with an exit code). See 08-01-PLAN.md/08-01-SUMMARY.md. | Phase 8 |
| `cursor-agent`'s registry `cmd` uses the legacy `"cursor-agent"` symlink name, not the script's newer primary `"agent"` name. | The newer name risks colliding with an unrelated `agent` binary from a different installed CLI on a multi-agent-tool machine; `cursor-agent` is unambiguous and matches every other reference to this tool already in this project. See 08-02-PLAN.md/08-02-SUMMARY.md. | Phase 8 |
| `rtk`'s Linux install path uses two separate arch-gated `github_release` methods (musl for amd64, gnu for arm64), not one unscoped template, plus a same-project-confirmed `brew` fallback after the locked checksum-verified method. | Upstream's own release assets are asymmetric per architecture — a single template would 404 on one of them; the `recommends` wiring on `claude`/`opencode`/`codex`/`cursor-agent` (`codegraph`/`graphify`/`rtk`) is the honest RESULT of per-host verification (D-01), not a uniform default applied blindly, with `rtk`'s weaker instructions-based Codex integration recorded rather than smoothed over; `antigravity` stays unwired per D-01, deferred not dropped. See 08-03-PLAN.md/08-03-SUMMARY.md and 08-04-PLAN.md/08-04-SUMMARY.md. | Phase 8 |
| `Tool.postinstall` is a closed dispatch-hook NAME (mirroring the existing `smoke` param), not a literal inline command string or a `postinstall_script` file — a deliberate, formally-reconciled deviation from REQ-postinstall-field's literal inline/script wording (cycle-1 cross-AI review HIGH 1). Dispatch is Method-aware in fact (the succeeded `Method` is passed into `run_postinstall`/every hook), not merely by call-site scope, satisfying REQ-postinstall-execution-timing's literal wording. | `codegraph`'s one proving case needs a `--target` value computed from live host presence, which cannot be expressed as a static registry string without inventing a new TOML templating micro-language for a single tool's one-off need; a closed, code-owned dispatch table also closes the supply-chain-shaped risk of registry data becoming shell text. See 09-01-PLAN.md/09-01-SUMMARY.md. | Phase 9 |
| codegraph's postinstall hook maps this project's catalog id `cursor-agent` to codegraph's own `--target` id `cursor`, and never passes `--target auto`. Host presence is checked via `installer.status.is_installed` on real, loaded catalog `Tool` objects — never a hook-local `shutil.which` re-implementation of that same seam (cycle-1 cross-AI review HIGH 2). | Live reading of codegraph v1.2.0's own `installer/targets/registry.js::resolveTargetFlag` found `--target auto` silently falls back to registering `claude` when it detects zero installed hosts — a real correctness gap 09-RESEARCH.md found that this mechanism must never trigger. See 09-01-PLAN.md/09-01-SUMMARY.md and 09-RESEARCH.md. | Phase 9 |
| Postinstall dispatch sits only inside `install_tool`'s per-method success branch, never on the `ALREADY_INSTALLED` early return, and is additionally wrapped in its own isolated `try/except Exception` at the call site — structurally separate from the method ladder's own `except CommandError \| ExecutorError \| VersionError` block — so an unexpected hook exception can never be misattributed to the method's own execution or turn a completed install into `FAILED` (cycle-1 cross-AI review HIGH 3). | This is what makes D-01's accepted limitation (codegraph's MCP registration does not re-trigger when a NEW agent host is installed later) true by construction rather than a special case that could rot; a known, accepted gap recorded rather than silently worked around. See 09-CONTEXT.md D-01 and 09-01-SUMMARY.md. | Phase 9 |
| The postinstall mechanism was proven in a real disposable container (Tier-3 container verification), with fake `claude`/`cursor-agent` executables planted on PATH before installing the real, committed `codegraph` registry entry through the actual production `install_tool` entry point — including inspecting the REAL resulting `mcpServers.codegraph` config-file entry, and a second all-hosts-absent run proving no such file is created at all (cycle-1 cross-AI review HIGH 4). | Unit-test fakes alone cannot prove the composed `codegraph install --target claude,cursor --location global --yes` argv is what a real install actually executes end to end against a real filesystem, nor that it actually writes the config entry it claims to — the same evidentiary bar Phase 8's `graphify`/`rtk` container proof set. See 09-02-PLAN.md/09-02-SUMMARY.md. | Phase 9 |
| REQ-manager-drift-alerting is deferred, not implemented in Phase 12. | Three independently-checkable reasons: `brew outdated` lists only already-installed formulae and casks, so it cannot detect an uninstalled brew alternative; zero registry rows declare both a `node`/`uv-tool` method and a `brew`/`cask` method (12-RESEARCH.md section 6); an unwired helper would violate `.claude/architecture.md` rule 5. 12-CONTEXT.md D-02's "planner's call" clause authorized the deferral. See `.planning/REQUIREMENTS.md`. | Phase 12 (12-04) |
| `scripts/detect-container-runtime.sh` live-proves its chosen container tool (`run --rm ... true` against a real image) instead of trusting a bare `which`, and refuses to silently fall back to a different tool than the one actually resolved (D-03) — never picks docker when the user's own PATH resolves podman, or vice versa. | A container-tool detector that only checks binary presence can silently target the wrong runtime (e.g. a stale `docker` shim while the user actually uses podman), corrupting every downstream Tier-3 e2e result without any visible error. See 12.3-01-SUMMARY.md. | Phase 12.3 (12.3-01) |
| Phase 12.3's full-catalog Tier-3 verification runs against Fedora-family only (D-05); no cross-distro or macOS claim is made by this phase's evidence. | Fedora 44 is the project's own primary dev/CI-adjacent target and the one this phase's `<CONTEXT>` scoped it to; claiming broader coverage without actually running it would be evidence the run never produced. See 12.3-CONTEXT.md. | Phase 12.3 |
| Full-catalog Tier-3 evidence is a two-pass format — a clean install pass, then a rerun/uninstall/reinstall pass against the SAME disposable container — folded verbatim (TRACER markers, per-tool tallies) into `.planning/RUN-REPORT.md` rather than a new, separate evidence document (D-06). | A single clean-install pass cannot surface idempotency or uninstall-sweep bugs, which are exactly the properties a mocked unit-test suite structurally cannot prove either; folding into the existing RUN-REPORT.md keeps the milestone's evidence trail one coherent document instead of two disconnected ones. See 12.3-03-SUMMARY.md and 12.3-04-SUMMARY.md. | Phase 12.3 (12.3-03, 12.3-04) |
| D-03: `present_agent_hosts()` extracted as the single shared host-presence computation, reused unchanged by `_codegraph_mcp_register`/`_rtk_register`/`_graphify_register` — never a fourth, independently re-derived host-presence loop. | Three postinstall hooks each needing the same "which of claude/codex/opencode/cursor-agent is actually installed" answer is exactly the duplication `.claude/architecture.md` rule 5 exists to prevent; codegraph's own pre-existing inline loop was refactored to call the shared helper with zero observable behavior change (all 11 pre-existing tests pass unmodified). See 12.4-01-SUMMARY.md. | Phase 12.4 (12.4-01) |
| D-02: `_rtk_register`/`_graphify_register` wired into the existing closed `POSTINSTALL_HOOKS` dispatch table, closing the rtk/graphify postinstall gap researched in Phase 8 but never implemented. rtk's `cursor-agent` branch is gated on `claude` also being present — live-verified against the real rtk v0.49.0 binary that `--agent cursor` still unconditionally also writes Claude Code's files as a side effect, so the cursor branch never fires on a Cursor-only machine. `codex` never receives `--auto-patch` (rtk rejects the combination outright, confirmed live). | Live testing (never the stale, locally-cached v0.44.1 rtk binary the prior research used) is what closed this — the cursor-implies-claude bug was confirmed still present in v0.49.0, not assumed fixed or assumed broken from stale evidence. See 12.4-01-SUMMARY.md, 12.4-02-SUMMARY.md. | Phase 12.4 (12.4-01, 12.4-02) |
| D-01/D-01a: a permanent tier/dependency/postinstall onboarding checklist lives in `.claude/architecture.md`'s Registry-authoring guidelines, and `.claude/skills/tool-onboarding/SKILL.md` (this project's first self-authored skill) walks it interactively, referencing rather than duplicating the checklist so there is exactly one canonical decision tree. States D-01a's "detect and configure, never blind-overwrite" principle as a standing rule, citing the GSD-statusline precedent. | This is the checklist that would have caught rtk/graphify's postinstall gap before it sat unnoticed across three phases (8, 9, 12.4) — a documented, repeatable process rather than ad-hoc judgment, so the same gap shape does not recur silently for the next catalog addition. See 12.4-03-SUMMARY.md. | Phase 12.4 (12.4-03) |
| D-04: full-catalog audit against the new checklist covered all 89 `registry.toml` entries (89/89, confirmed by direct count) — zero new postinstall-mechanism gaps found, one pre-existing dead-code finding (`Tool.post_install` plural) logged as a pending todo rather than fixed in-phase, one pre-existing open research question (graphify output-location) closed by direct investigation with no code change warranted. | 12.4-RESEARCH.md's own grep-scan for a third gap was a cheap keyword search, not the structured per-entry audit D-04 actually required; this plan ran the real audit so any gap gets a name and an owner instead of staying invisible the way rtk/graphify's did. See 12.4-AUDIT.md, 12.4-04-SUMMARY.md. | Phase 12.4 (12.4-04) |
| D-01..D-04: every managed PATH line this installer writes uses the case-guarded self-deduping idiom (`path_export_guard`) instead of a plain unconditional `export PATH=...`, applied to every writer in the repo (shell rc files and `scripts/container-e2e-verify.sh`); a generic `~/.shellrc` is consolidated into one canonical `~/.myshellrc` plus a marked stub, foreign content copied forward byte-exact. | A plain export re-prepends the same directory every time a nested/child shell re-sources the rc file, accumulating duplicates with every nesting level — confirmed live (5 copies of `~/.local/bin` in one real session) before this phase. Re-verified end to end in a disposable container after the dev host's own verification stalled on `human_needed` (no real hand-authored `~/.shellrc`, no pure-POSIX shell available here): `make fix` against a real hand-written `~/.shellrc`, `dash`, and the real wired `~/.bashrc`→`~/.myshellrc` route all confirmed the managed directory never exceeds 1 after 5 sources, while the user's own pre-existing plain exports (carried forward, out of scope) duplicate as documented. See 15.8-VERIFICATION.md, 15.8-SECURITY.md, 15.8-VALIDATION.md. | Phase 15.8 |
| One `ToolState` per tool, published in one swap; Uninstall, Policies and Doctor are projections of it (19 D-01/D-02, 21) | Seven to ten classifiers disagreed on installed, owner and removable | ✓ Good — Backlog 999.6 closed, 7/7 flows trace |
| One install plan with dispositions and one engine for the TUI and headless; exit code from outcomes (20 D-01, D-07..D-09) | A run could exit 0 after a failed or skipped install, and the review did not say what would happen | ✓ Good — Phase 20 |
| Receipts are written at one point (`engine.install_tool`) with a stat fingerprint and one `artifact_paths` formula (19 D-06..D-08) | One writer and one formula keep "what this method created" from drifting between install, status and removal | ✓ Good — Phases 19, 22 |
| Lifecycle contract: script `paths`/`remove`/`update` per method, tool-level `config_paths` with one denylist, removal order fixed (22 D-01..D-08) | Removal needed one proof and one order for every owner; shared harness dirs must never be listed | ✓ Good — contract shipped; only 4 of about 30 flagged entries declare `config_paths` yet (999.14) |
| Registry rejects unknown keys through `METHOD_PARAMS`, requires a `verified` date and checks digests; `make verify-registry` runs weekly and never in the PR gate (18 D-01, D-02, D-08) | Typos and drift were silent; a network check in the PR gate would make CI flaky | ✓ Good — Phase 18 |
| Agent-host hooks are recorded per host in `receipt.hooks`, with one new-host sweep at the end of a run and one `agent_settings.py` writer (23 D-02, D-03, D-06) | Hooks must follow hosts in and out and be reversible without parsing MCP configs | ✓ Good — Phase 23 |
| Skill packs, rtk, GSD, openspec and spec-kit leave the catalog; retired receipts are removed by a placement-shape proof, and manager kinds are handed off (23.1 D-06..D-08) | Owner decision: not installer scope; an unproven delete is never acceptable | ✓ Good — Phase 23.1 |
| Tests and shims can never install on the host: a subprocess allowlist guard, a real-HOME fingerprint, installs and removals only in containers (HOST-03..05) | An `npx` flag mismatch ran GSD's global installer 10 times on the developer's host (2026-11-07) | ✓ Good — Phase 23.1 |
| Install-time tuning in the tool's postinstall, never a Policies knob by default; applied with no question (23.2 D-01, TUNE-04) | Asking about co-authoring, auto-approve and zsh plugins at every install was friction the owner did not want | ✓ Good — Phase 23.2 |
| Schedules are a closed Python table with user-level timers, one JSON state file and fingerprinted files (24.2 D-01, D-06, D-07) | Zero sudo, atomic writes, and removal that proves what it wrote | ✓ Good — Phase 24.2 |
| The npx/npm/pip guard aliases and redirects are retired; the launch removes the installer's own leftovers and keeps every other byte (24.4, GUARD-01..06) | Owner: the aliases proved a disaster; a flag mismatch had run the wrong package | ✓ Good — Phase 24.4; ⚠️ naming collision `flow='guard'` (W3) |
| Install priority is brew, then bun, then volta/pnpm, with a `bun` method kind that passes no `--trust` (24.5 D-01, PRIO-06) | Owner preference; bun's default-deny postinstall gate stays on | ✓ Good — Phase 24.5 |
| A permanent AST reachability test, composition moved to `installer/compose.py` under pyright and coverage, run log bounded at 5,000 lines (25 D-01, D-05, D-08) | vulture at confidence 80 is silent where an import-graph check finds dead modules | ✓ Good — Phase 25 |
| The push gate is our own Python module outside `installer/`; it tests a tree equal to the pushed commit; each gate is its own `make` target and hook entry; `make validate` aggregates through pre-commit (26 D-01..D-05) | A red suite must not reach the remote; re-running only the failing gate keeps the loop short | ✓ Good — Phase 26 verified 6/6 with real-git evidence |
| Branch push, green CI, fast-forward `main` with `enforce_admins` applied last; `make install` becomes `make dev-setup`, `make setup` is removed, `make run` launches the wizard (26 D-07..D-10) | Owner decision 2026-11-16: no commit reaches `main` without both checks on that SHA | ⚠️ Revisit — outside tools (GSD merge helpers, ai-kit-commit-fold, phase-complete) still push directly; todo 2026-11-16 |
| The flaky `invalidate` test under xdist is mitigated with a reopen rule, not root-caused (26-03) | The push gate needs a stable suite now | ⚠️ Revisit — reopen on the next transient failure |
| Phase 26 owner decision IN-06: gate-read pathspecs would refuse a local-only `.claude/CLAUDE.md` | Found in code review; the owner has not chosen whether to allow it | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-11-16 at the start of milestone v0.51.0*
