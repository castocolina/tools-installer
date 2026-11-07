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
- [ ] **REG-02**: Every `[[tool]]` carries a `verified = YYYY-MM-DD` key, validated by the loader [A Ph6]
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

- [x] **PLAN-01**: The review lists every selected and dragged tool with its disposition (will install / update / repair / reconfigure / be reinstalled / skipped / blocked) and the reason [TA §3, 999.1, G R4]
- [x] **PLAN-02**: A current installer-owned tool is skipped unless the user presses `r`, which shows "will be reinstalled" [O7]
- [x] **PLAN-03**: A broken tool is planned as repair and a misconfigured one as reconfigure, including dragged dependencies [TA §3.1]
- [x] **PLAN-04**: The summary counts outcomes with the same words as the review [999.1]
- [x] **PLAN-05**: After a run, failed, blocked and not-attempted selections stay selected and done/skipped ones clear; `esc` before start keeps the selection [999.1, B 13 WR-03]
- [x] **PLAN-06**: Headless `--all`/`--categories` uses the same plan and engine, and its exit code comes from outcomes [B 13, B 14 IN-01]
- [x] **PLAN-07**: While state is refreshing, rows show "checking…" and Enter waits for the refresh instead of acting on stale state [O9]
- [x] **PLAN-08**: The UI no longer promises an off-policy migration that does not exist [O8, B 16 D-04]

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

- [ ] **LIFE-01**: Script methods declare the paths they write, an update command and optionally a remove command (run from the receipt-proven executable; none ships for opencode, review R2-05); removal deletes only declared paths that exist [TA §4.2, 999.8 L3]
- [ ] **LIFE-02**: Native package installs (dnf/apt/pacman) are handed off as the exact command; no executor ever runs sudo [O1, D-I]
- [ ] **LIFE-03**: brew/uv/pnpm uninstall runs only when a receipt proves the installer put the package there; otherwise a hint [O3]
- [ ] **LIFE-04**: Tools declare `config_paths`; shared harness dirs (`~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex`) can never be listed [TA §4.2]
- [ ] **LIFE-05**: `u` is refused for pinned `app` tools with no version source, with the reason [E NEW 1]
- [ ] **LIFE-06**: Vendor updates use the vendor's own command (Oh-My-Zsh upgrade, `sdk selfupdate`) [C G8]
- [ ] **LIFE-07**: A bootstrap that needs an unwritable prefix becomes a handoff after a preflight [C G2]
- [ ] **LIFE-08**: Removing a pnpm package that is part of a co-install group warns about the group [A #6, T-05-22]
- [ ] **LIFE-09**: The container end-to-end check compares file listings before and after uninstall, not only exit codes [A #3]
- [ ] **LIFE-10**: On macOS, casks that update themselves (`auto_updates: true`, e.g. VS Code) report and apply updates through `brew outdated --cask --greedy-auto-updates` / `brew upgrade --cask --greedy-auto-updates <cask>`; otherwise they show as current while outdated, and turning off their own updater would leave them stale [found 2026-10-13: Homebrew API reports `visual-studio-code` auto_updates=true; no `greedy` anywhere in installer/]

### Configuration

- [ ] **CONF-01**: Agent-host hooks (codegraph, graphify, herdr; rtk dropped 2026-11-02) register per host, record hosts in the receipt, and unregister on removal [TA §6, F X1]
- [ ] **CONF-02**: Installing a new agent host re-runs the hooks of already-installed hook tools for that host only [A Ph9 D-01]
- [ ] **CONF-03**: One agent-host list is used everywhere [TA §6]
- [ ] **CONF-04**: Shell init for starship, direnv, zoxide, fzf, fnm and volta is offered at install through the existing confirm (default off) and removed with the tool [C G6, O11] *(amended 2026-11-07, 23.2 R5: the block is written at install with no question and removed with the tool; the six `tweak:<tool>` Policies rows go)*
- [ ] **CONF-05**: Every zsh session exports `SHELL` as the real zsh path through a managed `~/.zshenv` line, so herdr, tmux, editors and agents opened from kitty, WezTerm, Konsole or any other terminal start zsh, not the passwd login shell (bash). kitty, WezTerm and Konsole configs keep pointing at zsh, and drift shows as misconfigured. Exporting `SHELL` through `environment.d`, for apps started from the desktop menu, is optional and asked [999.4, O4; host evidence 2026-10-13: all terminal shells are zsh with `SHELL=/bin/bash`] *(amended 2026-11-07, 23.2 R7: the desktop export stays a Policies row; the Phase 23 review run option is removed)*
- [ ] **CONF-06**: tealdeer fetches its cache after install and update [D]
- [ ] **CONF-07**: Oh-My-Zsh plugin writes honor `$ZSH` [B 15.6 CR-01]
- [ ] **CONF-08** (asking and the Policies row superseded by TUNE-01, 2026-11-07): Agent auto-approval is configured in each agent's own settings at install (asked, default off) instead of shell aliases: Claude `permissions.defaultMode: "bypassPermissions"` + `skipDangerousModePermissionPrompt: true` (user scope; project/local scope is ignored since 2.1.257), Codex `approval_policy = "never"` + `sandbox_mode = "danger-full-access"`, opencode `"permission": "allow"`, cursor-agent `approvalMode: "unrestricted"`; pi has no approval prompts in its core (they come only from extensions such as `pi-permission-system`), so the installer writes nothing for pi and its state notes when a permission extension is installed; each key is reverted when the choice is turned off or the tool is removed [user request 2026-10-13]
- [ ] **CONF-09** (asking and the Policies row superseded by TUNE-01, 2026-11-07): Agent commit/PR attribution can be turned off at install (asked): Claude `attribution.commit = false` and `attribution.pr = false`, cursor-agent `attribution.attributeCommitsToAgent = false` and `attributePRsToAgent = false` (the Cursor CLI ignores the commit opt-out as of 2026-10-04, so the UI states it), and Codex, opencode and pi are listed as having no documented key [user request 2026-10-13]
- [ ] **CONF-10**: The alias tweak bundles `claude-skip`, `codex-skip`, `opencode-auto` and the cursor-agent model wrapper leave Policies; a host that had one enabled gets the alias block removed with a one-line notice pointing to the matching Policies setting row; nothing is written to agent settings automatically (amended 2026-11-06, user decision: auto-approval is the settings.json key the user turns on) [user request 2026-10-13] *(amended 2026-11-07, 23.2 R7: the notice no longer points to a Policies row; the keys are written at install per TUNE-01)*
- [ ] **CONF-11** (applied at install with no knob per TUNE-02, 2026-11-07): The Oh-My-Zsh writer that sets `plugins=(…)` also writes a default `ZSH_THEME="robbyrussell"` before `source $ZSH/oh-my-zsh.sh`, but only when the file has no `ZSH_THEME` line. A theme the user set by hand or with `omz theme set` is never overwritten. Choosing starship (CONF-04) instead writes `ZSH_THEME=""`, so only one prompt is active. The install summary names `omz theme use <name>` (try it in the current session) and `omz theme set <name>` (keep it) [host evidence 2026-10-13: `ZSH_THEME` unset, prompt `%m%# `]
- [ ] **CONF-12** (asking and the Policies rows superseded by 23.2 R6, 2026-11-07: lean, built-in AI off and extension auto-update off are written at install with no question; AI off and auto-update off need confirmation): Installing VS Code offers a "lean mode" (asked) that writes only keys absent from `~/.config/Code/User/settings.json` (JSONC, comments preserved) and reverts exactly those keys on removal or opt-out: `telemetry.telemetryLevel: "off"`, `update.mode: "none"` (Linux: the package manager updates it; macOS: only together with LIFE-10, because the cask self-updates and `brew upgrade` skips it), `workbench.enableExperiments: false`, `workbench.settings.enableNaturalLanguageSearch: false`, `extensions.ignoreRecommendations: true`, `window.restoreWindows: "one"`, `workbench.startupEditor: "none"`, `editor.minimap.enabled: false`, `files.watcherExclude` for `node_modules`, `.venv`, `.git/objects`, `dist`, `build` and `.cache`, `search.followSymlinks: false`, `npm.autoDetect: "off"`, `task.autoDetect: "off"`, `typescript.disableAutomaticTypeAcquisition: true`, `git.autoRepositoryDetection: "openEditors"`, and `terminal.integrated.defaultProfile.linux` set to zsh. Turning off built-in AI (`chat.disableAIFeatures: true`) and extension auto-update (`extensions.autoUpdate: false`, `extensions.autoCheckUpdates: false`; security fixes then arrive only on demand) are separate questions. The install summary recommends no resident type-checker extension (Pylance uses the pyright engine, measured 358 MB resident on this repo) and running the project's pre-commit as an on-demand task. Every key was verified to exist in VS Code 1.138 [user request 2026-10-13; host evidence: 1.37 GB PSS across 5 windows, 928 MB of it in renderers; integrated terminals run bash]

### Onboarding and end-to-end

- [ ] **ONB-01**: herdr installs as a user-tier binary with an integrations postinstall for present agent hosts (no skill pack: dropped 2026-11-02), reusing only the workspace agent separator and current indicators from herdr-setup [999.11]
- [ ] **ONB-02**: On immutable Bazzite, Alacritty installs without a reboot by building it with cargo inside a throwaway Distrobox and placing the native binary in `~/.local/bin`; the container and image are deleted afterwards. A newer GitHub release shows as an update, and selecting it rebuilds while leaving `~/.config/alacritty` untouched [999.11, O5: measured 2026-10-13: 35 s build, 12 MB binary, host libs resolve] *(amended 2026-11-07, 24 D-19, needs confirmation: the image is deleted when this run pulled it; a pre-existing image is kept and named; the box uses `--home`/`--no-entry` so nothing lands in the host HOME, 24 D-20)*
- [ ] **ONB-06**: The Alacritty build also installs its desktop entry, icon and terminfo under `~/.local/share`, so it appears in the system menu and search; all of these are recorded in the receipt and removed on uninstall [O5]
- [ ] **ONB-07**: Alacritty gets the terminal shell sync (zsh, `SHELL`) and the keybinding customizations (word navigation, clear scrollback) [999.11] *(amended 2026-11-07, 24 D-22/D-23, TUNE-04: applied at install with no question and reverted with the tool; no Policies row)*
- [ ] **ONB-08**: Neovim (`nvim`) is onboarded through the tool-onboarding skill with a researched install and removal for every OS/arch (release tarballs, brew), a no-reboot path on immutable Bazzite, a receipt, and `~/.config/nvim` as `config_paths` [user request 2026-10-13]
- [ ] **ONB-09**: Installing Neovim asks whether to make it the default `EDITOR`/`VISUAL`; "yes" writes a managed shell line that is removed with the tool [user request 2026-10-13] *(amended 2026-11-07, 24.1 D-14, **needs confirmation**: TUNE-04 "always, no question" — install writes the managed line with no question, only when the user's own shell files export neither `EDITOR` nor `VISUAL` (OS defaults are overridden, a user value is kept and named); removed with the tool)*
- [ ] **ONB-10**: Installing Neovim offers kickstart.nvim as a starter config (asked), cloned into `~/.config/nvim` only when that directory is absent or empty, never over an existing config, and set up with **no language server**: opening Python, Lua, TypeScript, Go or Java files starts zero LSP processes, and Mason installs no servers. Linting and type checks run on demand through the project's pre-commit (`:!pre-commit run --files %`, named in the install summary together with `:lsp enable <name>` for a one-off session) [user decision 2026-10-13: "sin LSP en nvim"; measured: kickstart 26 MB PSS vs basedpyright +358 MB resident on this repo, 343 MB for 0.74 s on demand] *(amended 2026-11-07, 24.1 D-15/D-16, **needs confirmation**: TUNE-04 "always, no question" — not asked; cloned at install whenever `~/.config/nvim` is absent or empty, never offered again after the user deletes it, kept on removal unless "delete config too")*
- [ ] **ONB-03**: The tool-onboarding skill covers the new lifecycle params and is scored with skill-judge [999.5] *(amended 2026-11-07, 24 D-24: the skill also carries TUNE-04's rule, kept verbatim through this phase's edit; the baseline score is a fresh run on the skill as 23.2 leaves it)*
- [ ] **ONB-04**: The container end-to-end runs install all → rerun all (all skipped) → uninstall all on Fedora, Debian and Arch, with leftovers limited to documented config paths [A #3]
- [ ] **ONB-05**: A human UAT on the real host confirms Owner on every tier after install and the cleared mark after Uninstall [999.7]

### Host safety

- [ ] **HOST-01**: The catalog no longer offers rtk, matt-pocock-skills, opengsd, ponytail, superpowers, softaworks-agent-toolkit, openspec or spec-kit: their registry entries, skill-pack and project-pack reconfigure steps (including every `pnpm dlx @opengsd/gsd-core` run), status probes and tests are deleted; a host that still has a receipt for one of them can remove it (or is told to remove it itself) and is never offered a reinstall [user request 2026-11-07]
- [ ] **HOST-02**: The `npx` guard shim translates `-p X` / `--package X` to `--package=X`, drops `-y` / `--yes`, and exits non-zero on any other npx-only flag, so a flag mismatch can never run a package's default bin [audit 2026-11-07: `npx -y -p @opengsd/gsd-core gsd-mcp-server` ran GSD's global installer 10 times]
- [ ] **HOST-03**: Unit tests cannot execute a real toolchain: the subprocess guard is an allowlist that also inspects `sh -c` / `bash -c` scripts; linuxbrew and real-home bins are off the test PATH; agent and toolchain variables (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_CONFIG*`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `npm_config_*`, `UV_*`, `HOMEBREW_*`, `GH_TOKEN`, `GITHUB_TOKEN`) are cleared; network sockets are blocked [user request 2026-11-07]
- [ ] **HOST-04**: The real-HOME fingerprint also watches `~/.claude/{gsd-core,.gsd-source,gsd-file-manifest.json,agents,commands,hooks}`, `~/.gsd`, `~/.agents`, `~/.codex`, `~/.cursor`, `~/.config/opencode`, `~/.local/{bin,opt}`, uv tools, the pnpm global dir, Volta tools, `~/.config/systemd/user` and `~/.oh-my-zsh` (listing and mtime only) and fails the run on any change [user request 2026-11-07]
- [ ] **HOST-05**: Every check that installs or removes real packages runs only in the container e2e, which also asserts that no global GSD tree (`~/.claude/gsd-core`, `.gsd-source`) appears [user request 2026-11-07]

### Install-time tuning

- [ ] **TUNE-01**: Installing claude, codex, opencode, cursor-agent or copilot applies the agent tuning at once, with no question: commit/PR co-authoring off wherever a documented key exists, and the auto-approve/bypass keys of CONF-08 (plus copilot's documented equivalent); each key is written only when absent and reverted on removal. This replaces the Phase 23 run options and their Policies rows [user decision 2026-11-07: "Always, no question"]
- [ ] **TUNE-02**: Installing zsh / Oh-My-Zsh applies the plugins and the default theme at install, with no question and no Policies knob; starship keeps `ZSH_THEME=""` symmetric [user request 2026-11-07]
- [ ] **TUNE-03**: Policies keeps only settings that are not part of an initial install; every current Policies row is reviewed and install tuning moves to its tool's postinstall, with the outcome of each row recorded [user request 2026-11-07]
- [ ] **TUNE-04**: The tool-onboarding skill states the rule: a new requirement is install-time tuning in the tool's postinstall unless it lies outside any install, and it never becomes a Policies knob by default [user request 2026-11-07]
- [ ] **TUNE-05**: While a step runs without output, the run log shows a live indicator (spinner and elapsed time) and writes a timestamped "still running (Ns)" line at least every 10 s instead of a static `waiting for output` [UAT feedback 2026-11-07]
- [ ] **TUNE-06**: The catalog offers GitHub Copilot CLI (`copilot`) as a user-tier agent, onboarded through the tool-onboarding skill (brew cask `copilot-cli` on macOS and Linux, or npm `@github/copilot`), with detection of a hand-installed copy, removal through its manager, and TUNE-01 tuning: `defaultPermissionMode = "allow-all"` and `includeCoAuthoredBy = false` in `$COPILOT_HOME/settings.json` (default `~/.copilot`) [user request 2026-11-07; keys verified with copilot 1.0.105 in a scratch `COPILOT_HOME`]
- [ ] **TUNE-07**: A dependency present at its declared install path but missing from the session PATH (for example pnpm installed by an earlier run in the same terminal) is runnable by the tool that needs it in the same session, and a present-but-unreachable dependency is never reported as "install pnpm" [real-TTY UAT F-1 2026-11-07]

### Schedules

- [ ] **SCHED-01**: A Schedules view lists the built-in schedules with name, script, target, state, interval and next run; a schedule is on by default when its target is installed and shown as unavailable when it is not [user request 2026-11-07]
- [ ] **SCHED-02**: The built-ins are cache cleanup (the known growing caches) and updates for claude, opencode, Pi coding agent, cursor-agent and copilot when installed; the default is every 6 h starting at 00:00, and the user can change the interval and start time [user request 2026-11-07] *(amended 2026-11-07, 24.2 SPEC R2/R4/R9: the tmpdir-cleanup daemon moves from Policies into Schedules as a seventh built-in with its own cadence; cache cleanup runs only the package managers' own prune commands; intervals are whole hours dividing 24)*
- [ ] **SCHED-03**: Schedules run as user-level timers (systemd user units on Linux, a launchd agent on macOS) with zero sudo, are written atomically and recorded in a receipt, and are removed when turned off or when the installer uninstalls [user request 2026-11-07]
- [ ] **SCHED-04**: The cursor-agent update job checks `~/.local/bin/cursor-agent`: when it is a symlink again (a fresh update), it is replaced by a shim that passes through when a model is given and otherwise injects the configured default frontier model (requested: gpt-6.1-sol, xhigh, long context; the exact model id is verified against cursor-agent's model list at plan time) before exec'ing the symlink's target in cursor's install dir; `~/.local/bin/agent` is untouched and the shim is removed with cursor-agent [user request 2026-11-07] *(amended 2026-11-07, 24.2 SPEC R7: `cursor-agent --list-models` has no `gpt-6.1-sol`; the default is `gpt-5.6-sol-xhigh` ("GPT-5.6 Sol 1M Extra High"), **needs confirmation**; the shim execs the launcher `~/.local/bin/agent` points to at run time, and turning the schedule off restores the symlink)*
- [ ] **SCHED-05**: Each schedule run appends a timestamped log line, and the view shows the last run and its result [user request 2026-11-07]

### Catalog audit

- [ ] **AUDIT-01**: A catalog-audit skill loops over every registry entry and compares the pinned/verified version, the installed version and the latest online release, reads the changelog between them, and checks that install, update, removal and tuning steps still match upstream docs [user request 2026-11-07]
- [ ] **AUDIT-02**: The skill audits the install and customization scripts (postinstall, shims, tweaks) for drift and unsafe patterns, writes one report per entry plus a summary of proposed registry and script changes, keeps per-entry state so the loop can resume, and changes nothing without approval [user request 2026-11-07]
- [ ] **AUDIT-03**: Its first run covers opencode v2 and Pi coding agent's MCP support, and the resulting registry and postinstall updates land (e.g. Pi joins the agent-host list for MCP-registering hooks) [user report 2026-11-07]
- [ ] **AUDIT-04**: The skill is scored with skill-judge [user request 2026-11-07]

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
| PLAN-01 | Phase 20 | Complete |
| PLAN-02 | Phase 20 | Complete |
| PLAN-03 | Phase 20 | Complete |
| PLAN-04 | Phase 20 | Complete |
| PLAN-05 | Phase 20 | Complete |
| PLAN-06 | Phase 20 | Complete |
| PLAN-07 | Phase 20 | Complete |
| PLAN-08 | Phase 20 | Complete |
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
| LIFE-10 | Phase 22 | Pending |
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
| CONF-12 | Phase 23 | Pending |
| ONB-01 | Phase 24 | Pending |
| ONB-02 | Phase 24 | Pending |
| ONB-03 | Phase 24 | Pending |
| ONB-04 | Phase 24 | Pending |
| ONB-05 | Phase 24 | Pending |
| ONB-06 | Phase 24 | Pending |
| ONB-07 | Phase 24 | Pending |
| ONB-08 | Phase 24.1 | Pending |
| ONB-09 | Phase 24.1 | Pending |
| ONB-10 | Phase 24.1 | Pending |
| HOST-01 | Phase 23.1 | Pending |
| HOST-02 | Phase 23.1 | Pending |
| HOST-03 | Phase 23.1 | Pending |
| HOST-04 | Phase 23.1 | Pending |
| HOST-05 | Phase 23.1 | Pending |
| TUNE-01 | Phase 23.2 | Pending |
| TUNE-02 | Phase 23.2 | Pending |
| TUNE-03 | Phase 23.2 | Pending |
| TUNE-04 | Phase 23.2 | Pending |
| TUNE-05 | Phase 23.2 | Pending |
| TUNE-06 | Phase 23.2 | Pending |
| TUNE-07 | Phase 23.2 | Pending |
| SCHED-01 | Phase 24.2 | Pending |
| SCHED-02 | Phase 24.2 | Pending |
| SCHED-03 | Phase 24.2 | Pending |
| SCHED-04 | Phase 24.2 | Pending |
| SCHED-05 | Phase 24.2 | Pending |
| AUDIT-01 | Phase 24.3 | Pending |
| AUDIT-02 | Phase 24.3 | Pending |
| AUDIT-03 | Phase 24.3 | Pending |
| AUDIT-04 | Phase 24.3 | Pending |
| LEAN-01 | Phase 25 | Pending |
| LEAN-02 | Phase 25 | Pending |
| LEAN-03 | Phase 25 | Pending |
| LEAN-04 | Phase 25 | Pending |

**Coverage:**

- v1 requirements: 102 total *(recounted 2026-11-07 in 23.2: HOST, TUNE, SCHED and AUDIT rows were not counted)*
- Mapped to phases: 102 (Phase 17: 12, Phase 18: 10, Phase 19: 7, Phase 20: 8, Phase 21: 7, Phase 22: 11, Phase 23: 12, Phase 23.1: 5, Phase 23.2: 7, Phase 24: 7, Phase 24.1: 3, Phase 24.2: 5, Phase 24.3: 4, Phase 25: 4)
- Unmapped: 0
- Mapping note: UI-04 sits in Phase 22, not Phase 21 (TA §8 P5), because it needs `config_paths` (LIFE-04)

---
*Requirements defined: 2026-10-13*
*Last updated: 2026-10-13 after roadmap creation (traceability filled)*
