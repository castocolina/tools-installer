# Requirements: tools-installer

**Defined:** 2026-10-13
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.
**Milestone:** v0.50.0 Truthful lifecycle. Design source: `.planning/research/2026-10-13-target-architecture.md` (TA). IDs in brackets cite TA sections and audit findings.

## v1 Requirements (this milestone)

### Safety (stop the bleeding)

- [ ] **SAFE-01**: A download/app method whose member is a directory fails with an error and links nothing; reinstalling over an existing link-to-directory leaves the inner files untouched [TA H1, E gap 1]
- [ ] **SAFE-02**: Installing or updating graphify writes nothing into the installer's working directory [TA H2, O14]
- [ ] **SAFE-03**: Uninstall (TUI and `make uninstall --yes`) never deletes an artifact it cannot prove it wrote; foreign files at a matching name are listed as "remove it yourself" [TA H3, F1, AR-01]
- [ ] **SAFE-04**: Shell rc and shim writes are atomic, and a cleanup refuses a file that changed between preview and confirm [TA H5, F5, AR-02]
- [ ] **SAFE-05**: A run that crashes mid-way or has any failed install/update shows a red "Failed" status and exits non-zero [TA H6, B 13 WR-01]
- [ ] **SAFE-06**: Changing the shell link mode keeps every active policy active in the new mode and removes it from the old one [TA H4, B 13 WR-05]
- [ ] **SAFE-07**: A vendor install script that prompts on the terminal fails fast instead of hanging the TUI [TA H7]
- [ ] **SAFE-08**: A non-UTF-8 `settings.json` does not crash the app at launch [B 13 WR-06]
- [ ] **SAFE-09**: Every route that accepts a catalog selection can execute it (no route silently exits with ids) [F2]

### CI and verification

- [ ] **CI-01**: CI is green on Ubuntu and macOS [999.7]
- [ ] **CI-02**: Merges to main require the PR check to pass (branch protection; user action) [999.7]
- [ ] **CI-03**: Phase 16 gap plans 16-17..19 are re-audited (secure + validate) [999.7]

### Registry truth

- [ ] **REG-01**: Loading the registry rejects unknown method keys per kind [TA §4.2, A T-07-14, D C10]
- [ ] **REG-02**: Every `[[tool]]` carries a `# Verified YYYY-MM-DD` line, enforced by a test [A Ph6]
- [ ] **REG-03**: `make verify-registry` reports renamed assets, missing archive members and checksum drift against the latest release; it runs weekly as a non-blocking scheduled job, never in the PR gate [D C5, O12]
- [ ] **REG-04**: GitHub release downloads without a pinned checksum are verified against the GitHub API sha256 digest [F X5, C5]
- [ ] **REG-05**: A freshly installed binary that fails a smoke run (`--version`, loader errors) falls through to the next method [D C6]
- [ ] **REG-06**: The installer launches without the dev venv on PATH, so tools resolve their real owner [D C1]
- [ ] **REG-07**: macOS stubs (`/usr/bin/java`) never count as an installed tool [C G1]
- [ ] **REG-08**: The version parser never fabricates a version (`-1`, quoted, `version=` forms) [B 15 WR-02]
- [ ] **REG-09**: All data fixes from audits C, D, E and F are applied, and the `managed-download` owner probe is removed [C/D/E/F, B 15 WR-07]
- [ ] **REG-10**: The `drawio-cli` row is removed; `drawio-desktop` serves both audiences [O6]

### Tool state and health

- [ ] **STATE-01**: Each refresh builds one `ToolState` per tool and publishes it in one swap; a refresh overtaken by a newer one publishes nothing [TA §2, AR-04]
- [ ] **STATE-02**: Every catalog tier shows one health mark per tool (`✓ ok · ↑ update · ≈ config · ! broken · ○ missing`, dim unavailable, `…` checking) with a legend inside the 78×3 budget [TA §1, G R1]
- [ ] **STATE-03**: Install, update and repair write an atomic receipt per tool recording the artifacts, package and hooks they created [TA §5, 999.2]
- [ ] **STATE-04**: Owner attribution is correct for uv tools, Volta, redirect shims, the implicit `~/.local/bin`, `host_setup` tools and native packages (memoized probe) [F X4, C G5, B #4, B 15 WR-04/06]
- [ ] **STATE-05**: Installing a manager (brew) in-session makes its methods available without restarting the app [A T-07-15, C G3]
- [ ] **STATE-06**: The focused row shows its health reasons and the configuration steps it is missing [TA §7]
- [ ] **STATE-07**: Skill packs show partial or duplicate installs per harness [F X7]

### Install plan

- [ ] **PLAN-01**: The review lists every selected and dragged tool with its disposition (will install / update / repair / reconfigure / be reinstalled / skipped / blocked) and the reason [TA §3, 999.1, G R4]
- [ ] **PLAN-02**: A current installer-owned tool is skipped unless the user presses `r`, which shows "will be reinstalled" [O7]
- [ ] **PLAN-03**: A broken tool is planned as repair and a misconfigured one as reconfigure, including dragged dependencies [TA §3.1]
- [ ] **PLAN-04**: The summary counts outcomes with the same words as the review [999.1]
- [ ] **PLAN-05**: After a run, failed, blocked and not-attempted selections stay selected and done/skipped ones clear; `esc` before start keeps the selection [999.1, B 13 WR-03]
- [ ] **PLAN-06**: Headless `--all`/`--categories` uses the same plan and engine, and its exit code comes from outcomes [B 13, B 14 IN-01]
- [ ] **PLAN-07**: While state is refreshing, rows show "checking…" and Enter waits for the refresh instead of acting on stale state [O9]
- [ ] **PLAN-08**: The UI no longer promises an off-policy migration that does not exist [O8, B 16 D-04]

### Screens

- [ ] **UI-01**: After any mutation (install, `u`, removal, policy toggle, Doctor `r`) every view shows the new state on its next entry, and immediately if visible [TA §7, 999.6, G R2]
- [ ] **UI-02**: Every view clears its transient status on leave and keeps a status written during entry [G R2]
- [ ] **UI-03**: Uninstall lists removable tools (with proof), managed-elsewhere tools (with their hint) and nothing-to-do tools, from the shared state; an unknown owner is never attributed to a manager [G R3]
- [ ] **UI-04**: Uninstall offers "delete config too" for tools with `config_paths`; default keeps config, and the CLI never deletes config [TA §6]
- [ ] **UI-05**: Removal runs on a worker with visible progress [F16]
- [ ] **UI-06**: Policies show live truth on entry (drift, live prerequisites) [F3, F8, AR-08]
- [ ] **UI-07**: Doctor follows the same lifecycle, its hidden `a` key is removed, and dangling pnpm global shims appear as broken [F17, todo 2026-09-16]
- [ ] **UI-08**: A selection that is no longer selectable is pruned on reload [F4, 999.1(a)]

### Method lifecycle

- [ ] **LIFE-01**: Script methods declare the paths they write, a remove command and an update command; removal deletes only declared paths that exist [TA §4.2, 999.8 L3]
- [ ] **LIFE-02**: Native package installs (dnf/apt/pacman) are handed off as the exact command; no executor ever runs sudo [O1, D-I]
- [ ] **LIFE-03**: brew/uv/pnpm uninstall runs only when a receipt proves the installer put the package there; otherwise a hint [O3]
- [ ] **LIFE-04**: Tools declare `config_paths`; shared harness dirs (`~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex`) can never be listed [TA §4.2]
- [ ] **LIFE-05**: `u` is refused for pinned `app` tools with no version source, with the reason [E NEW 1]
- [ ] **LIFE-06**: Vendor updates use the vendor's own command (Oh-My-Zsh upgrade, `sdk selfupdate`) [C G8]
- [ ] **LIFE-07**: A bootstrap that needs an unwritable prefix becomes a handoff after a preflight [C G2]
- [ ] **LIFE-08**: Removing a pnpm package that is part of a co-install group warns about the group [A #6, T-05-22]
- [ ] **LIFE-09**: The container end-to-end check compares file listings before and after uninstall, not only exit codes [A #3]

### Configuration

- [ ] **CONF-01**: Agent-host hooks (codegraph, rtk, graphify, herdr) register per host, record hosts in the receipt, and unregister on removal [TA §6, F X1]
- [ ] **CONF-02**: Installing a new agent host re-runs the hooks of already-installed hook tools for that host only [A Ph9 D-01]
- [ ] **CONF-03**: One agent-host list is used everywhere [TA §6]
- [ ] **CONF-04**: Shell init for starship, direnv, zoxide, fzf, fnm and volta is offered at install through the existing confirm (default off) and removed with the tool [C G6, O11]
- [ ] **CONF-05**: Every zsh session exports `SHELL` as the real zsh path through a managed `~/.zshenv` line, so herdr, tmux, editors and agents opened from kitty, WezTerm, Konsole or any other terminal start zsh, not the passwd login shell (bash). kitty, WezTerm and Konsole configs keep pointing at zsh, and drift shows as misconfigured. Exporting `SHELL` through `environment.d`, for apps started from the desktop menu, is optional and asked [999.4, O4; host evidence 2026-10-13: all terminal shells are zsh with `SHELL=/bin/bash`]
- [ ] **CONF-06**: tealdeer fetches its cache after install and update [D]
- [ ] **CONF-07**: Oh-My-Zsh plugin writes honor `$ZSH` [B 15.6 CR-01]
- [ ] **CONF-08**: Agent auto-approval is configured in each agent's own settings at install (asked, default off) instead of shell aliases: Claude `permissions.defaultMode: "bypassPermissions"` + `skipDangerousModePermissionPrompt: true` (user scope; project/local scope is ignored since 2.1.257), Codex `approval_policy = "never"` + `sandbox_mode = "danger-full-access"`, opencode `"permission": "allow"`, cursor-agent `approvalMode: "unrestricted"`; each key is reverted when the choice is turned off or the tool is removed [user request 2026-10-13]
- [ ] **CONF-09**: Agent commit/PR attribution can be turned off at install (asked): Claude `attribution.commit = false` and `attribution.pr = false`, cursor-agent `attribution.attributeCommitsToAgent = false` and `attributePRsToAgent = false` (the Cursor CLI ignores the commit opt-out as of 2026-10-04, so the UI states it), and Codex/opencode are listed as having no documented key [user request 2026-10-13]
- [ ] **CONF-10**: The alias tweak bundles `claude-skip`, `codex-skip`, `opencode-auto` and the cursor-agent model wrapper leave Policies; a host that had one enabled gets the alias removed and the equivalent config key applied (cursor-agent default model via `cli-config.json`) [user request 2026-10-13]
- [ ] **CONF-11**: The zsh prompt is chosen at install: an Oh-My-Zsh theme (default `robbyrussell`) written into the managed `.zshrc` before `source $ZSH/oh-my-zsh.sh`, or starship init (CONF-04); only one is active [host evidence 2026-10-13: `ZSH_THEME` unset, prompt `%m%# `]

### Onboarding and end-to-end

- [ ] **ONB-01**: herdr installs as a user-tier binary with an integrations postinstall for present agent hosts and an optional skill pack, reusing only the workspace agent separator and current indicators from herdr-setup [999.11]
- [ ] **ONB-02**: On immutable Bazzite, Alacritty installs without a reboot by building it with cargo inside a throwaway Distrobox and placing the native binary in `~/.local/bin`; the container and image are deleted afterwards. A newer GitHub release shows as an update, and selecting it rebuilds while leaving `~/.config/alacritty` untouched [999.11, O5: measured 2026-10-13: 35 s build, 12 MB binary, host libs resolve]
- [ ] **ONB-06**: The Alacritty build also installs its desktop entry, icon and terminfo under `~/.local/share`, so it appears in the system menu and search; all of these are recorded in the receipt and removed on uninstall [O5]
- [ ] **ONB-07**: Alacritty gets the terminal shell sync (zsh, `SHELL`) and the keybinding customizations (word navigation, clear scrollback) [999.11]
- [ ] **ONB-03**: The tool-onboarding skill covers the new lifecycle params and is scored with skill-judge [999.5]
- [ ] **ONB-04**: The container end-to-end runs install all → rerun all (all skipped) → uninstall all on Fedora, Debian and Arch, with leftovers limited to documented config paths [A #3]
- [ ] **ONB-05**: A human UAT on the real host confirms Owner on every tier after install and the cleared mark after Uninstall [999.7]

### Lean

- [ ] **LEAN-01**: Dead code is removed (agent policy modules, questionary chooser, `audit.py`, dead fields and messages) while race epochs stay [F11, F14, F15, G #9]
- [ ] **LEAN-02**: App composition lives in an `installer/` module under pyright and the coverage gate [F12]
- [ ] **LEAN-03**: `wizard_app.py` is split and review-history comments are dropped [F13]
- [ ] **LEAN-04**: The run log is bounded [B 13 IN-08]

## Future Requirements

- Latest-version lookup for script and SDKMAN tools (vendors self-update today) [C G7]
- Volta → mise migration (separate milestone) [O10]
- Apple Silicon end-to-end runs [A Ph12.3]

## Out of Scope

| Feature | Reason |
|---------|--------|
| `RowsScreen` base class | Defaults in `AppScreen` plus a prune in `ToolBrowser` cover it (G R2) |
| dmg / `app {ver}` method kinds | Every proven gap closes with data or a `u` gate (TA §4.4). Exception by user decision O5: a container-build method for Alacritty |
| `service` start/stop step | 4 tools, all VM or root daemons; handoff text is honest (C G11) |
| Per-tool keep/delete/ask config enum | `config_paths` plus one confirm toggle covers it |
| git-config, completion and desktop-entry writers | Convenience writers nobody reported broken; handoff text instead |
| MCP-config parsing as health | `receipt.hooks` gives the same answer with zero subprocesses |
| REQ-manager-drift-alerting | The off-policy owner note already covers it |
| Off-policy migration ("moving it there") | No owner for four phases; the UI is reworded instead |
| Headless `--reinstall` flag | `make uninstall` plus `--all` covers the rare need |
| npm subcommand allowlist | No reported need (O13) |
| Running sudo/pkexec/doas | Zero-sudo invariant (O1) |

## Traceability

Filled by the roadmap (2026-10-13). Phases 17–25 = milestone v0.50.0.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFE-01 | Phase 17 | Pending |
| SAFE-02 | Phase 17 | Pending |
| SAFE-03 | Phase 17 | Pending |
| SAFE-04 | Phase 17 | Pending |
| SAFE-05 | Phase 17 | Pending |
| SAFE-06 | Phase 17 | Pending |
| SAFE-07 | Phase 17 | Pending |
| SAFE-08 | Phase 17 | Pending |
| SAFE-09 | Phase 17 | Pending |
| CI-01 | Phase 17 | Pending |
| CI-02 | Phase 17 | Pending |
| CI-03 | Phase 17 | Pending |
| REG-01 | Phase 18 | Pending |
| REG-02 | Phase 18 | Pending |
| REG-03 | Phase 18 | Pending |
| REG-04 | Phase 18 | Pending |
| REG-05 | Phase 18 | Pending |
| REG-06 | Phase 18 | Pending |
| REG-07 | Phase 18 | Pending |
| REG-08 | Phase 18 | Pending |
| REG-09 | Phase 18 | Pending |
| REG-10 | Phase 18 | Pending |
| STATE-01 | Phase 19 | Pending |
| STATE-02 | Phase 19 | Pending |
| STATE-03 | Phase 19 | Pending |
| STATE-04 | Phase 19 | Pending |
| STATE-05 | Phase 19 | Pending |
| STATE-06 | Phase 19 | Pending |
| STATE-07 | Phase 19 | Pending |
| PLAN-01 | Phase 20 | Pending |
| PLAN-02 | Phase 20 | Pending |
| PLAN-03 | Phase 20 | Pending |
| PLAN-04 | Phase 20 | Pending |
| PLAN-05 | Phase 20 | Pending |
| PLAN-06 | Phase 20 | Pending |
| PLAN-07 | Phase 20 | Pending |
| PLAN-08 | Phase 20 | Pending |
| UI-01 | Phase 21 | Pending |
| UI-02 | Phase 21 | Pending |
| UI-03 | Phase 21 | Pending |
| UI-04 | Phase 22 | Pending |
| UI-05 | Phase 21 | Pending |
| UI-06 | Phase 21 | Pending |
| UI-07 | Phase 21 | Pending |
| UI-08 | Phase 21 | Pending |
| LIFE-01 | Phase 22 | Pending |
| LIFE-02 | Phase 22 | Pending |
| LIFE-03 | Phase 22 | Pending |
| LIFE-04 | Phase 22 | Pending |
| LIFE-05 | Phase 22 | Pending |
| LIFE-06 | Phase 22 | Pending |
| LIFE-07 | Phase 22 | Pending |
| LIFE-08 | Phase 22 | Pending |
| LIFE-09 | Phase 22 | Pending |
| CONF-01 | Phase 23 | Pending |
| CONF-02 | Phase 23 | Pending |
| CONF-03 | Phase 23 | Pending |
| CONF-04 | Phase 23 | Pending |
| CONF-05 | Phase 23 | Pending |
| CONF-06 | Phase 23 | Pending |
| CONF-07 | Phase 23 | Pending |
| CONF-08 | Phase 23 | Pending |
| CONF-09 | Phase 23 | Pending |
| CONF-10 | Phase 23 | Pending |
| CONF-11 | Phase 23 | Pending |
| ONB-01 | Phase 24 | Pending |
| ONB-02 | Phase 24 | Pending |
| ONB-03 | Phase 24 | Pending |
| ONB-04 | Phase 24 | Pending |
| ONB-05 | Phase 24 | Pending |
| ONB-06 | Phase 24 | Pending |
| ONB-07 | Phase 24 | Pending |
| LEAN-01 | Phase 25 | Pending |
| LEAN-02 | Phase 25 | Pending |
| LEAN-03 | Phase 25 | Pending |
| LEAN-04 | Phase 25 | Pending |

**Coverage:**

- v1 requirements: 76 total
- Mapped to phases: 76 (Phase 17: 12, Phase 18: 10, Phase 19: 7, Phase 20: 8, Phase 21: 7, Phase 22: 10, Phase 23: 11, Phase 24: 7, Phase 25: 4)
- Unmapped: 0
- Mapping note: UI-04 sits in Phase 22, not Phase 21 (TA §8 P5), because it needs `config_paths` (LIFE-04)

---
*Requirements defined: 2026-10-13*
*Last updated: 2026-10-13 after roadmap creation (traceability filled)*
