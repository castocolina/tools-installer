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

## Current Milestone: v0.50.0 Truthful lifecycle

**Goal:** Every screen tells the truth about each tool on this host (present, healthy, whose, which version, removable with proof), and install, update, removal and configuration follow one per-method contract with install receipts as removal proof.

**Target features:**
- Stop the bleeding: the seven host hazards (H1–H7), CI green on both OSes, PR check required
- Registry truth and drift guard (`make verify-registry`, unknown-key rejection, checksums, smoke test)
- One `ToolState` with a closed `Health` set and install receipts
- Install plan with dispositions (install / update / repair / reconfigure / reinstall `r` / skip / blocked), one engine for TUI and headless
- One screen family; Uninstall, Policies and Doctor as projections of the same state
- Per-method lifecycle contract (script `paths`/`remove`/`update`, native installs handed off, `config_paths`)
- Configuration as a lifecycle step (reversible agent-host hooks, shell init, terminal `SHELL`)
- herdr and Alacritty onboarded through the tool-onboarding skill; container e2e with leftover checks
- Lean-up (~2,000 lines deleted)

**Design source:** `.planning/research/2026-10-13-target-architecture.md` (decisions D-A..D-J, open decisions O1–O14) and `.planning/research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md`.

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
- ✓ Catalog tiers (system/user/ai) with tier-scoped views, `recommends`, failure propagation, tweak-executable uninstall sweep, Oh-My-Zsh bundled plugins — v0.49.0
- ✓ Package-manager redirect policy, catalog expansion (system/user/AI tiers), `uv-tool` executor, postinstall hooks, agent CLI ergonomics, background maintenance daemon (macOS launchd, Linux systemd user timer) — v0.49.0
- ✓ Version-aware status and owner-routed updates, live in-TUI install execution, persistent wizard settings, Owner column and Uninstall manager attribution, terminal default shell on immutable hosts, self-deduping PATH, filesystem-based detection — v0.49.0 (partially: see the 2026-10-13 audit; 14 partial and 53 deferred promises carried forward)

### Active

<!-- v0.50.0 scope; full list with REQ-IDs in .planning/REQUIREMENTS.md. -->

- [ ] One truthful tool state per host (installed / health / owner / version / removability) shared by every screen
- [ ] Install review that states each selection's disposition (install / update / repair / reconfigure / reinstall / skip)
- [ ] Per-method lifecycle contract (install, detect, version, owner, update, remove, configure, service, privileges) with install receipts as removal proof
- [ ] Configuration as a lifecycle step (shell init, agent-host hooks re-synced and reversible, terminal drift), with user-chosen customizations
- [ ] Registry kept true: drift detection, checksums, smoke tests; CI green on both OSes
- [ ] No host hazard left: no unproven deletion, no link to a directory, no writes into the CWD, no false success

### Out of Scope

- New resolver/ordering logic keyed on `tier` — `requires` already handles ordering, cycle detection, and availability skipping (PRD Design Decisions)
- External/custom (non-bundled) Oh-My-Zsh plugins requiring their own `git clone` step — deferred per the source PRD's Open Questions
- `rpm-ostree` layering on immutable hosts — needs a reboot; Bazzite recommends Flatpak, Homebrew, Distrobox first
- Any sudo/pkexec/doas performed by this project itself — zero-sudo invariant; native dnf/apt/pacman installs are handed off as the exact command (O1, 2026-10-13)
- New method kinds for dmg / `app {ver}`, a `service` start/stop step, a keep/delete/ask config enum, git-config/completion writers — v0.50.0 ultra cut (target architecture §9.1)
- REQ-manager-drift-alerting — dropped 2026-10-13: the off-policy owner note already says another manager owns the tool

## Context

**Current state (2026-10-13):** v0.49.0 "Tiered Catalog" shipped (28 phases, 110 plans) and was closed with an override closeout after a seven-part audit (`.planning/research/audit-2026-10-13/`) found the catalog installs binaries well but lacks one shared tool state, a health model, an install-disposition plan, a per-method removal/configuration contract and registry drift detection; 6 registry blockers (java, ruff, difftastic, sublime, jetbrains-toolbox, graphify) and red CI carry into v0.50.0.


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
| v0.50.0 is built from a ponytail-ultra target architecture, not from per-phase fixes | v0.49.0 audit: seven to ten places answered "installed / owner / removable" differently | — Pending |
| Native package installs are handed off as a command, never run with sudo (O1) | Zero-sudo invariant; the TUI child has no usable tty | — Pending |
| Receipts are the only removal proof; nothing unproven is deleted, in CLI or TUI | Uninstall deleted files it could not prove it wrote (F1, AR-01) | — Pending |
| Alacritty on Bazzite: cargo build in a throwaway Distrobox, native binary on the host, container and image deleted (O5) | Measured 2026-10-13: 35 s build, 12 MB permanent vs 2.4 GB for a persistent Distrobox; runs natively, no shell-inside-container issue | — Pending |
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
| `graphifyy`'s automated `[SUS]` legitimacy flag was discharged with a live, fail-closed PyPI + GitHub identity/age check before its registry entry was written, mirroring Phase 5's established automated-gate pattern rather than a `gate="blocking-human"` stop. | ONESHOT-RULES Rules 9/14 (the Tier-3 container tier, not a mid-run human stop, is this project's escalation path; package identity here is checkable from live metadata with an exit code). See 08-01-PLAN.md/08-01-SUMMARY.md. | Phase 8 |
| `cursor-agent`'s registry `cmd` uses the legacy `"cursor-agent"` symlink name, not the script's newer primary `"agent"` name. | The newer name risks colliding with an unrelated `agent` binary from a different installed CLI on a multi-agent-tool machine; `cursor-agent` is unambiguous and matches every other reference to this tool already in this project. See 08-02-PLAN.md/08-02-SUMMARY.md. | Phase 8 |
| `rtk`'s Linux install path uses two separate arch-gated `github_release` methods (musl for amd64, gnu for arm64), not one unscoped template, plus a same-project-confirmed `brew` fallback after the locked checksum-verified method. | Upstream's own release assets are asymmetric per architecture — a single template would 404 on one of them; the `recommends` wiring on `claude`/`opencode`/`codex`/`cursor-agent` (`codegraph`/`graphify`/`rtk`) is the honest RESULT of per-host verification (D-01), not a uniform default applied blindly, with `rtk`'s weaker instructions-based Codex integration recorded rather than smoothed over; `antigravity` stays unwired per D-01, deferred not dropped. See 08-03-PLAN.md/08-03-SUMMARY.md and 08-04-PLAN.md/08-04-SUMMARY.md. | Phase 8 |
| `Tool.postinstall` is a closed dispatch-hook NAME (mirroring the existing `smoke` param), not a literal inline command string or a `postinstall_script` file — a deliberate, formally-reconciled deviation from REQ-postinstall-field's literal inline/script wording (cycle-1 cross-AI review HIGH 1). Dispatch is Method-aware in fact (the succeeded `Method` is passed into `run_postinstall`/every hook), not merely by call-site scope, satisfying REQ-postinstall-execution-timing's literal wording. | `codegraph`'s one proving case needs a `--target` value computed from live host presence, which cannot be expressed as a static registry string without inventing a new TOML templating micro-language for a single tool's one-off need; a closed, code-owned dispatch table also closes the supply-chain-shaped risk of registry data becoming shell text. See 09-01-PLAN.md/09-01-SUMMARY.md. | Phase 9 |
| codegraph's postinstall hook maps this project's catalog id `cursor-agent` to codegraph's own `--target` id `cursor`, and never passes `--target auto`. Host presence is checked via `installer.status.is_installed` on real, loaded catalog `Tool` objects — never a hook-local `shutil.which` re-implementation of that same seam (cycle-1 cross-AI review HIGH 2). | Live reading of codegraph v1.2.0's own `installer/targets/registry.js::resolveTargetFlag` found `--target auto` silently falls back to registering `claude` when it detects zero installed hosts — a real correctness gap 09-RESEARCH.md found that this mechanism must never trigger. See 09-01-PLAN.md/09-01-SUMMARY.md and 09-RESEARCH.md. | Phase 9 |
| Postinstall dispatch sits only inside `install_tool`'s per-method success branch, never on the `ALREADY_INSTALLED` early return, and is additionally wrapped in its own isolated `try/except Exception` at the call site — structurally separate from the method ladder's own `except CommandError \| ExecutorError \| VersionError` block — so an unexpected hook exception can never be misattributed to the method's own execution or turn a completed install into `FAILED` (cycle-1 cross-AI review HIGH 3). | This is what makes D-01's accepted limitation (codegraph's MCP registration does not re-trigger when a NEW agent host is installed later) true by construction rather than a special case that could rot; a known, accepted gap recorded rather than silently worked around. See 09-CONTEXT.md D-01 and 09-01-SUMMARY.md. | Phase 9 |
| The postinstall mechanism was proven in a real disposable container (ONESHOT-RULES Rule 14), with fake `claude`/`cursor-agent` executables planted on PATH before installing the real, committed `codegraph` registry entry through the actual production `install_tool` entry point — including inspecting the REAL resulting `mcpServers.codegraph` config-file entry, and a second all-hosts-absent run proving no such file is created at all (cycle-1 cross-AI review HIGH 4). | Unit-test fakes alone cannot prove the composed `codegraph install --target claude,cursor --location global --yes` argv is what a real install actually executes end to end against a real filesystem, nor that it actually writes the config entry it claims to — the same evidentiary bar Phase 8's `graphify`/`rtk` container proof set. See 09-02-PLAN.md/09-02-SUMMARY.md. | Phase 9 |
| REQ-manager-drift-alerting is deferred, not implemented in Phase 12. | Three independently-checkable reasons: `brew outdated` lists only already-installed formulae and casks, so it cannot detect an uninstalled brew alternative; zero registry rows declare both a `node`/`uv-tool` method and a `brew`/`cask` method (12-RESEARCH.md section 6); an unwired helper would violate `.claude/architecture.md` rule 5. 12-CONTEXT.md D-02's "planner's call" clause authorized the deferral. See `.planning/REQUIREMENTS.md`. | Phase 12 (12-04) |
| `scripts/detect-container-runtime.sh` live-proves its chosen container tool (`run --rm ... true` against a real image) instead of trusting a bare `which`, and refuses to silently fall back to a different tool than the one actually resolved (D-03) — never picks docker when the user's own PATH resolves podman, or vice versa. | A container-tool detector that only checks binary presence can silently target the wrong runtime (e.g. a stale `docker` shim while the user actually uses podman), corrupting every downstream Tier-3 e2e result without any visible error. See 12.3-01-SUMMARY.md. | Phase 12.3 (12.3-01) |
| Phase 12.3's full-catalog Tier-3 verification runs against Fedora-family only (D-05); no cross-distro or macOS claim is made by this phase's evidence. | Fedora 44 is the project's own primary dev/CI-adjacent target and the one this phase's `<CONTEXT>` scoped it to; claiming broader coverage without actually running it would be evidence the run never produced. See 12.3-CONTEXT.md. | Phase 12.3 |
| Full-catalog Tier-3 evidence is a two-pass format — a clean install pass, then a rerun/uninstall/reinstall pass against the SAME disposable container — folded verbatim (TRACER markers, per-tool tallies) into `.planning/RUN-REPORT.md` rather than a new, separate evidence document (D-06). | A single clean-install pass cannot surface idempotency or uninstall-sweep bugs, which are exactly the properties a mocked unit-test suite structurally cannot prove either; folding into the existing RUN-REPORT.md keeps the milestone's evidence trail one coherent document instead of two disconnected ones. See 12.3-03-SUMMARY.md and 12.3-04-SUMMARY.md. | Phase 12.3 (12.3-03, 12.3-04) |
| D-03: `present_agent_hosts()` extracted as the single shared host-presence computation, reused unchanged by `_codegraph_mcp_register`/`_rtk_register`/`_graphify_register` — never a fourth, independently re-derived host-presence loop. | Three postinstall hooks each needing the same "which of claude/codex/opencode/cursor-agent is actually installed" answer is exactly the duplication `.claude/architecture.md` rule 5 exists to prevent; codegraph's own pre-existing inline loop was refactored to call the shared helper with zero observable behavior change (all 11 pre-existing tests pass unmodified). See 12.4-01-SUMMARY.md. | Phase 12.4 (12.4-01) |
| D-02: `_rtk_register`/`_graphify_register` wired into the existing closed `POSTINSTALL_HOOKS` dispatch table, closing the rtk/graphify postinstall gap researched in Phase 8 but never implemented. rtk's `cursor-agent` branch is gated on `claude` also being present — live-verified against the real rtk v0.49.0 binary that `--agent cursor` still unconditionally also writes Claude Code's files as a side effect, so the cursor branch never fires on a Cursor-only machine. `codex` never receives `--auto-patch` (rtk rejects the combination outright, confirmed live). | Live testing (never the stale, locally-cached v0.44.1 rtk binary the prior research used) is what closed this — the cursor-implies-claude bug was confirmed still present in v0.49.0, not assumed fixed or assumed broken from stale evidence. See 12.4-01-SUMMARY.md, 12.4-02-SUMMARY.md. | Phase 12.4 (12.4-01, 12.4-02) |
| D-01/D-01a: a permanent tier/dependency/postinstall onboarding checklist lives in `.claude/architecture.md`'s Registry-authoring guidelines, and `.claude/skills/tool-onboarding/SKILL.md` (this project's first self-authored skill) walks it interactively, referencing rather than duplicating the checklist so there is exactly one canonical decision tree. States D-01a's "detect and configure, never blind-overwrite" principle as a standing rule, citing the GSD-statusline precedent. | This is the checklist that would have caught rtk/graphify's postinstall gap before it sat unnoticed across three phases (8, 9, 12.4) — a documented, repeatable process rather than ad-hoc judgment, so the same gap shape does not recur silently for the next catalog addition. See 12.4-03-SUMMARY.md. | Phase 12.4 (12.4-03) |
| D-04: full-catalog audit against the new checklist covered all 89 `registry.toml` entries (89/89, confirmed by direct count) — zero new postinstall-mechanism gaps found, one pre-existing dead-code finding (`Tool.post_install` plural) logged as a pending todo rather than fixed in-phase, one pre-existing open research question (graphify output-location) closed by direct investigation with no code change warranted. | 12.4-RESEARCH.md's own grep-scan for a third gap was a cheap keyword search, not the structured per-entry audit D-04 actually required; this plan ran the real audit so any gap gets a name and an owner instead of staying invisible the way rtk/graphify's did. See 12.4-AUDIT.md, 12.4-04-SUMMARY.md. | Phase 12.4 (12.4-04) |
| D-01..D-04: every managed PATH line this installer writes uses the case-guarded self-deduping idiom (`path_export_guard`) instead of a plain unconditional `export PATH=...`, applied to every writer in the repo (shell rc files and `scripts/container-e2e-verify.sh`); a generic `~/.shellrc` is consolidated into one canonical `~/.myshellrc` plus a marked stub, foreign content copied forward byte-exact. | A plain export re-prepends the same directory every time a nested/child shell re-sources the rc file, accumulating duplicates with every nesting level — confirmed live (5 copies of `~/.local/bin` in one real session) before this phase. Re-verified end to end in a disposable container after the dev host's own verification stalled on `human_needed` (no real hand-authored `~/.shellrc`, no pure-POSIX shell available here): `make fix` against a real hand-written `~/.shellrc`, `dash`, and the real wired `~/.bashrc`→`~/.myshellrc` route all confirmed the managed directory never exceeds 1 after 5 sources, while the user's own pre-existing plain exports (carried forward, out of scope) duplicate as documented. See 15.8-VERIFICATION.md, 15.8-SECURITY.md, 15.8-VALIDATION.md. | Phase 15.8 |

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
*Last updated: 2026-10-13 after starting milestone v0.50.0 Truthful lifecycle*
