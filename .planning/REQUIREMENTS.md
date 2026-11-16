# Requirements: tools-installer

**Defined:** 2026-10-13
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required.
**Milestone:** v0.50.0 Truthful lifecycle. Design source: `.planning/research/2026-10-13-target-architecture.md` (TA). IDs in brackets cite TA sections and audit findings.

## v1 Requirements (this milestone)

### Safety (stop the bleeding)

- [x] **SAFE-01**: A download/app method whose member is a directory fails with an error and links nothing; reinstalling over an existing link-to-directory leaves the inner files untouched [TA H1, E gap 1]
- [x] **SAFE-02**: Installing or updating graphify writes nothing into the installer's working directory [TA H2, O14]
- [x] **SAFE-03**: Uninstall (TUI and `make uninstall --yes`) never deletes an artifact it cannot prove it wrote; foreign files at a matching name are listed as "remove it yourself" [TA H3, F1, AR-01]
- [x] **SAFE-04**: Shell rc and shim writes are atomic, and a cleanup refuses a file that changed between preview and confirm [TA H5, F5, AR-02]
- [x] **SAFE-05**: A run that crashes mid-way or has any failed install/update shows a red "Failed" status and exits non-zero [TA H6, B 13 WR-01]
- [x] **SAFE-06**: Changing the shell link mode keeps every active policy active in the new mode and removes it from the old one [TA H4, B 13 WR-05]
- [x] **SAFE-07**: A vendor install script that prompts on the terminal fails fast instead of hanging the TUI [TA H7]
- [x] **SAFE-08**: A non-UTF-8 `settings.json` does not crash the app at launch [B 13 WR-06]
- [x] **SAFE-09**: Every route that accepts a catalog selection can execute it (no route silently exits with ids) [F2]

### CI and verification

- [x] **CI-01**: CI is green on Ubuntu and macOS [999.7]
- [x] **CI-02**: Merges to main require the PR check to pass (branch protection; user action) [999.7]
- [x] **CI-03**: Phase 16 gap plans 16-17..19 are re-audited (secure + validate) [999.7]

### Registry truth

- [x] **REG-01**: Loading the registry rejects unknown method keys per kind [TA §4.2, A T-07-14, D C10]
- [x] **REG-02**: Every `[[tool]]` carries a `verified = YYYY-MM-DD` key, validated by the loader [A Ph6]
- [x] **REG-03**: `make verify-registry` reports renamed assets, missing archive members and checksum drift against the latest release; it runs weekly as a non-blocking scheduled job, never in the PR gate [D C5, O12]
- [x] **REG-04**: GitHub release downloads without a pinned checksum are verified against the GitHub API sha256 digest [F X5, C5]
- [x] **REG-05**: A freshly installed binary that fails a smoke run (`--version`, loader errors) falls through to the next method [D C6]
- [x] **REG-06**: The installer launches without the dev venv on PATH, so tools resolve their real owner [D C1]
- [x] **REG-07**: macOS stubs (`/usr/bin/java`) never count as an installed tool [C G1]
- [x] **REG-08**: The version parser never fabricates a version (`-1`, quoted, `version=` forms) [B 15 WR-02]
- [x] **REG-09**: All data fixes from audits C, D, E and F are applied, and the `managed-download` owner probe is removed [C/D/E/F, B 15 WR-07]
- [x] **REG-10**: The `drawio-cli` row is removed; `drawio-desktop` serves both audiences [O6]

### Tool state and health

- [x] **STATE-01**: Each refresh builds one `ToolState` per tool and publishes it in one swap; a refresh overtaken by a newer one publishes nothing [TA §2, AR-04]
- [x] **STATE-02**: Every catalog tier shows one health mark per tool (`✓ ok · ↑ update · ≈ config · ! broken · ○ missing`, dim unavailable, `…` checking) with a legend inside the 78×3 budget [TA §1, G R1]
- [x] **STATE-03**: Install, update and repair write an atomic receipt per tool recording the artifacts, package and hooks they created [TA §5, 999.2]
- [x] **STATE-04**: Owner attribution is correct for uv tools, Volta, redirect shims, the implicit `~/.local/bin`, `host_setup` tools and native packages (memoized probe) [F X4, C G5, B #4, B 15 WR-04/06]
- [x] **STATE-05**: Installing a manager (brew) in-session makes its methods available without restarting the app [A T-07-15, C G3]
- [x] **STATE-06**: The focused row shows its health reasons and the configuration steps it is missing [TA §7]
- [x] **STATE-07**: Skill packs show partial or duplicate installs per harness [F X7] *(superseded 2026-11-15: Phase 23.1 HOST-01 removed every skill-pack entry and installer/skill_lifecycle.py, so there is nothing left to report)*

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

- [x] **UI-01**: After any mutation (install, `u`, removal, policy toggle, Doctor `r`) every view shows the new state on its next entry, and immediately if visible [TA §7, 999.6, G R2]
- [x] **UI-02**: Every view clears its transient status on leave and keeps a status written during entry [G R2]
- [x] **UI-03**: Uninstall lists removable tools (with proof), managed-elsewhere tools (with their hint) and nothing-to-do tools, from the shared state; an unknown owner is never attributed to a manager [G R3]
- [x] **UI-04**: Uninstall offers "delete config too" for tools with `config_paths`; default keeps config, and the CLI never deletes config [TA §6]
- [x] **UI-05**: Removal runs on a worker with visible progress [F16]
- [x] **UI-06**: Policies show live truth on entry (drift, live prerequisites) [F3, F8, AR-08]
- [x] **UI-07**: Doctor follows the same lifecycle, its hidden `a` key is removed, and dangling pnpm global shims appear as broken [F17, todo 2026-09-16]
- [x] **UI-08**: A selection that is no longer selectable is pruned on reload [F4, 999.1(a)]

### Method lifecycle

- [x] **LIFE-01**: Script methods declare the paths they write, an update command and optionally a remove command (run from the receipt-proven executable; none ships for opencode, review R2-05); removal deletes only declared paths that exist [TA §4.2, 999.8 L3]
- [x] **LIFE-02**: Native package installs (dnf/apt/pacman) are handed off as the exact command; no executor ever runs sudo [O1, D-I]
- [x] **LIFE-03**: brew/uv/pnpm uninstall runs only when a receipt proves the installer put the package there; otherwise a hint [O3]
- [x] **LIFE-04**: Tools declare `config_paths`; shared harness dirs (`~/.claude`, `~/.cursor`, `~/.gemini`, `~/.codex`) can never be listed [TA §4.2]
- [x] **LIFE-05**: `u` is refused for pinned `app` tools with no version source, with the reason [E NEW 1]
- [x] **LIFE-06**: Vendor updates use the vendor's own command (Oh-My-Zsh upgrade, `sdk selfupdate`) [C G8]
- [x] **LIFE-07**: A bootstrap that needs an unwritable prefix becomes a handoff after a preflight [C G2]
- [x] **LIFE-08**: Removing a pnpm package that is part of a co-install group warns about the group [A #6, T-05-22]
- [x] **LIFE-09**: The container end-to-end check compares file listings before and after uninstall, not only exit codes [A #3]
- [x] **LIFE-10**: On macOS, casks that update themselves (`auto_updates: true`, e.g. VS Code) report and apply updates through `brew outdated --cask --greedy-auto-updates` / `brew upgrade --cask --greedy-auto-updates <cask>`; otherwise they show as current while outdated, and turning off their own updater would leave them stale [found 2026-10-13: Homebrew API reports `visual-studio-code` auto_updates=true; no `greedy` anywhere in installer/]

### Configuration

- [x] **CONF-01**: Agent-host hooks (codegraph, graphify, herdr; rtk dropped 2026-11-02) register per host, record hosts in the receipt, and unregister on removal [TA §6, F X1]
- [x] **CONF-02**: Installing a new agent host re-runs the hooks of already-installed hook tools for that host only [A Ph9 D-01]
- [x] **CONF-03**: One agent-host list is used everywhere [TA §6]
- [x] **CONF-04**: Shell init for starship, direnv, zoxide, fzf, fnm and volta is offered at install through the existing confirm (default off) and removed with the tool [C G6, O11] *(amended 2026-11-07, 23.2 R5: the block is written at install with no question and removed with the tool; the six `tweak:<tool>` Policies rows go)*
- [x] **CONF-05**: Every zsh session exports `SHELL` as the real zsh path through a managed `~/.zshenv` line, so herdr, tmux, editors and agents opened from kitty, WezTerm, Konsole or any other terminal start zsh, not the passwd login shell (bash). kitty, WezTerm and Konsole configs keep pointing at zsh, and drift shows as misconfigured. Exporting `SHELL` through `environment.d`, for apps started from the desktop menu, is optional and asked [999.4, O4; host evidence 2026-10-13: all terminal shells are zsh with `SHELL=/bin/bash`] *(amended 2026-11-07, 23.2 R7: the desktop export stays a Policies row; the Phase 23 review run option is removed)*
- [x] **CONF-06**: tealdeer fetches its cache after install and update [D]
- [x] **CONF-07**: Oh-My-Zsh plugin writes honor `$ZSH` [B 15.6 CR-01]
- [x] **CONF-08** (asking and the Policies row superseded by TUNE-01, 2026-11-07): Agent auto-approval is configured in each agent's own settings at install (asked, default off) instead of shell aliases: Claude `permissions.defaultMode: "bypassPermissions"` + `skipDangerousModePermissionPrompt: true` (user scope; project/local scope is ignored since 2.1.257), Codex `approval_policy = "never"` + `sandbox_mode = "danger-full-access"`, opencode `"permission": "allow"`, cursor-agent `approvalMode: "unrestricted"`; pi has no approval prompts in its core (they come only from extensions such as `pi-permission-system`), so the installer writes nothing for pi and its state notes when a permission extension is installed; each key is reverted when the choice is turned off or the tool is removed [user request 2026-10-13]
- [x] **CONF-09** (asking and the Policies row superseded by TUNE-01, 2026-11-07): Agent commit/PR attribution can be turned off at install (asked): Claude `attribution.commit = ""` and `attribution.pr = ""`, cursor-agent `attribution.attributeCommitsToAgent = false` and `attributePRsToAgent = false` (the Cursor CLI ignores the commit opt-out as of 2026-10-04, so the UI states it), and Codex, opencode and pi are listed as having no documented key [user request 2026-10-13] *(amended 2026-11-07, 23.2: the code writes the empty string; "false" was a transcription error)*
- [x] **CONF-10**: The alias tweak bundles `claude-skip`, `codex-skip`, `opencode-auto` and the cursor-agent model wrapper leave Policies; a host that had one enabled gets the alias block removed with a one-line notice pointing to the matching Policies setting row; nothing is written to agent settings automatically (amended 2026-11-06, user decision: auto-approval is the settings.json key the user turns on) [user request 2026-10-13] *(amended 2026-11-07, 23.2 R7: the notice no longer points to a Policies row; the keys are written at install per TUNE-01)*
- [x] **CONF-11** (applied at install with no knob per TUNE-02, 2026-11-07): The Oh-My-Zsh writer that sets `plugins=(…)` also writes a default `ZSH_THEME="robbyrussell"` before `source $ZSH/oh-my-zsh.sh`, but only when the file has no `ZSH_THEME` line. A theme the user set by hand or with `omz theme set` is never overwritten. Choosing starship (CONF-04) instead writes `ZSH_THEME=""`, so only one prompt is active. The install summary names `omz theme use <name>` (try it in the current session) and `omz theme set <name>` (keep it) [host evidence 2026-10-13: `ZSH_THEME` unset, prompt `%m%# `]
- [x] **CONF-12** (asking and the Policies rows superseded by 23.2 R6, 2026-11-07: lean, built-in AI off and extension auto-update off are written at install with no question; AI off and auto-update off need confirmation): Installing VS Code offers a "lean mode" (asked) that writes only keys absent from `~/.config/Code/User/settings.json` (JSONC, comments preserved) and reverts exactly those keys on removal or opt-out: `telemetry.telemetryLevel: "off"`, `update.mode: "none"` (Linux: the package manager updates it; macOS: only together with LIFE-10, because the cask self-updates and `brew upgrade` skips it), `workbench.enableExperiments: false`, `workbench.settings.enableNaturalLanguageSearch: false`, `extensions.ignoreRecommendations: true`, `window.restoreWindows: "one"`, `workbench.startupEditor: "none"`, `editor.minimap.enabled: false`, `files.watcherExclude` for `node_modules`, `.venv`, `.git/objects`, `dist`, `build` and `.cache`, `search.followSymlinks: false`, `npm.autoDetect: "off"`, `task.autoDetect: "off"`, `typescript.disableAutomaticTypeAcquisition: true`, `git.autoRepositoryDetection: "openEditors"`, and `terminal.integrated.defaultProfile.linux` set to zsh. Turning off built-in AI (`chat.disableAIFeatures: true`) and extension auto-update (`extensions.autoUpdate: false`, `extensions.autoCheckUpdates: false`; security fixes then arrive only on demand) are separate questions. The install summary recommends no resident type-checker extension (Pylance uses the pyright engine, measured 358 MB resident on this repo) and running the project's pre-commit as an on-demand task. Every key was verified to exist in VS Code 1.138 [user request 2026-10-13; host evidence: 1.37 GB PSS across 5 windows, 928 MB of it in renderers; integrated terminals run bash]

### Onboarding and end-to-end

- [x] **ONB-01**: herdr installs as a user-tier binary with an integrations postinstall for present agent hosts (no skill pack: dropped 2026-11-02), reusing only the workspace agent separator and current indicators from herdr-setup [999.11]
- [x] **ONB-02**: On immutable Bazzite, Alacritty installs without a reboot by building it with cargo inside a throwaway Distrobox and placing the native binary in `~/.local/bin`; the container and image are deleted afterwards. A newer GitHub release shows as an update, and selecting it rebuilds while leaving `~/.config/alacritty` untouched [999.11, O5: measured 2026-10-13: 35 s build, 12 MB binary, host libs resolve] *(amended 2026-11-07, 24 D-19, needs confirmation: the image is deleted when this run pulled it; a pre-existing image is kept and named; the box uses `--home`/`--no-entry` so nothing lands in the host HOME, 24 D-20)*
- [x] **ONB-06**: The Alacritty build also installs its desktop entry, icon and terminfo under `~/.local/share`, so it appears in the system menu and search; all of these are recorded in the receipt and removed on uninstall [O5] *(amended 2026-11-08, 24 D-07: the terminfo goes to `~/.terminfo`, not `~/.local/share/terminfo`; ncurses 6.6 and Alacritty 0.17 do not search `~/.local/share/terminfo`, reproduced in a scratch HOME; the desktop entry and icon stay under `~/.local/share`)*
- [x] **ONB-07**: Alacritty gets the terminal shell sync (zsh, `SHELL`) and the keybinding customizations (word navigation, clear scrollback) [999.11] *(amended 2026-11-07, 24 D-22/D-23, TUNE-04: applied at install with no question and reverted with the tool; no Policies row)*
- [x] **ONB-08**: Neovim (`nvim`) is onboarded through the tool-onboarding skill with a researched install and removal for every OS/arch (release tarballs, brew), a no-reboot path on immutable Bazzite, a receipt, and `~/.config/nvim` as `config_paths` [user request 2026-10-13]
- [x] **ONB-09**: Installing Neovim asks whether to make it the default `EDITOR`/`VISUAL`; "yes" writes a managed shell line that is removed with the tool [user request 2026-10-13] *(amended 2026-11-07, 24.1 D-14, **needs confirmation**: TUNE-04 "always, no question" — install writes the managed line with no question, only when the user's own shell files export neither `EDITOR` nor `VISUAL` (OS defaults are overridden, a user value is kept and named); removed with the tool)*
- [x] **ONB-10**: Installing Neovim offers kickstart.nvim as a starter config (asked), cloned into `~/.config/nvim` only when that directory is absent or empty, never over an existing config, and set up with **no language server**: opening Python, Lua, TypeScript, Go or Java files starts zero LSP processes, and Mason installs no servers. Linting and type checks run on demand through the project's pre-commit (`:!pre-commit run --files %`, named in the install summary together with `:lsp enable <name>` for a one-off session) [user decision 2026-10-13: "sin LSP en nvim"; measured: kickstart 26 MB PSS vs basedpyright +358 MB resident on this repo, 343 MB for 0.74 s on demand] *(amended 2026-11-07, 24.1 D-15/D-16, **needs confirmation**: TUNE-04 "always, no question" — not asked; cloned at install whenever `~/.config/nvim` is absent or empty, never offered again after the user deletes it, kept on removal unless "delete config too")*
- [x] **ONB-03**: The tool-onboarding skill covers the new lifecycle params and is scored with skill-judge [999.5] *(amended 2026-11-07, 24 D-24: the skill also carries TUNE-04's rule, kept verbatim through this phase's edit; the baseline score is a fresh run on the skill as 23.2 leaves it)*
- [x] **ONB-04**: The container end-to-end runs install all → rerun all (all skipped) → uninstall all on Fedora, Debian and Arch, with leftovers limited to documented config paths [A #3]
- [x] **ONB-05**: A human UAT on the real host confirms Owner on every tier after install and the cleared mark after Uninstall [999.7]

### Host safety

- [x] **HOST-01**: The catalog no longer offers rtk, matt-pocock-skills, opengsd, ponytail, superpowers, softaworks-agent-toolkit, openspec or spec-kit: their registry entries, skill-pack and project-pack reconfigure steps (including every `pnpm dlx @opengsd/gsd-core` run), status probes and tests are deleted; a host that still has a receipt for one of them can remove it (or is told to remove it itself) and is never offered a reinstall [user request 2026-11-07]
- [x] **HOST-02**: The `npx` guard shim translates `-p X` / `--package X` to `--package=X`, drops `-y` / `--yes`, and exits non-zero on any other npx-only flag, so a flag mismatch can never run a package's default bin [audit 2026-11-07: `npx -y -p @opengsd/gsd-core gsd-mcp-server` ran GSD's global installer 10 times] *(amended 2026-11-07, 23.1 reviews: interactive `npx` also goes through the translator: the guard alias block no longer aliases `npx` to `pnpm dlx`, and an existing block is rewritten at the next launch; orchestrator decision the user may reverse)* *(amended 2026-11-14, 24.4 GUARD-01: superseded. The owner retired the guard ("Los alias de npx, npm, pip han demostrado ser un desastre"); the npx translator is deleted and a launch removes the installer-written shims and ban block)*
- [x] **HOST-03**: Unit tests cannot execute a real toolchain: the subprocess guard is an allowlist that also inspects `sh -c` / `bash -c` scripts; linuxbrew and real-home bins are off the test PATH; agent and toolchain variables (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `OPENCODE_CONFIG*`, `XDG_CACHE_HOME`, `XDG_STATE_HOME`, `npm_config_*`, `UV_*`, `HOMEBREW_*`, `GH_TOKEN`, `GITHUB_TOKEN`) are cleared; network sockets are blocked [user request 2026-11-07]
- [x] **HOST-04**: The real-HOME fingerprint also watches `~/.claude/{gsd-core,.gsd-source,gsd-file-manifest.json,agents,commands,hooks}`, `~/.gsd`, `~/.agents`, `~/.codex`, `~/.cursor`, `~/.config/opencode`, `~/.local/{bin,opt}`, uv tools, the pnpm global dir, Volta tools, `~/.config/systemd/user` and `~/.oh-my-zsh` (listing and mtime only) and fails the run on any change [user request 2026-11-07]
- [x] **HOST-05**: Every check that installs or removes real packages runs only in the container e2e, which also asserts that no global GSD tree (`~/.claude/gsd-core`, `.gsd-source`) appears [user request 2026-11-07]

### Install-time tuning

- [x] **TUNE-01**: Installing claude, codex, opencode, cursor-agent or copilot applies the agent tuning at once, with no question: commit/PR co-authoring off wherever a documented key exists, and the auto-approve/bypass keys of CONF-08 (plus copilot's documented equivalent); each key is written only when absent and reverted on removal. This replaces the Phase 23 run options and their Policies rows [user decision 2026-11-07: "Always, no question"]
- [x] **TUNE-02**: Installing zsh / Oh-My-Zsh applies the plugins and the default theme at install, with no question and no Policies knob; starship keeps `ZSH_THEME=""` symmetric [user request 2026-11-07]
- [x] **TUNE-03**: Policies keeps only settings that are not part of an initial install; every current Policies row is reviewed and install tuning moves to its tool's postinstall, with the outcome of each row recorded [user request 2026-11-07]
- [x] **TUNE-04**: The tool-onboarding skill states the rule: a new requirement is install-time tuning in the tool's postinstall unless it lies outside any install, and it never becomes a Policies knob by default [user request 2026-11-07]
- [x] **TUNE-05**: While a step runs without output, the run log shows a live indicator (spinner and elapsed time) and writes a timestamped "still running (Ns)" line at least every 10 s instead of a static `waiting for output` [UAT feedback 2026-11-07]
- [x] **TUNE-06**: The catalog offers GitHub Copilot CLI (`copilot`) as a user-tier agent, onboarded through the tool-onboarding skill (brew cask `copilot-cli` on macOS and Linux, or npm `@github/copilot`), with detection of a hand-installed copy, removal through its manager, and TUNE-01 tuning: `defaultPermissionMode = "allow-all"` and `includeCoAuthoredBy = false` in `$COPILOT_HOME/settings.json` (default `~/.copilot`) [user request 2026-11-07; keys verified with copilot 1.0.105 in a scratch `COPILOT_HOME`] *(amended 2026-11-07, 23.2 D-20: macOS brew cask `copilot-cli`; Linux `github_release`, the checksummed `copilot-linux-{x64,arm64}.tar.gz` verified against `SHA256SUMS.txt`; an ownership-only Linux cask so a hand-installed linuxbrew cask reads present; no npm method, because a tool-level `requires` would pull pnpm into the macOS plan and the npm package states no Node floor)*
- [x] **TUNE-07**: A dependency present at its declared install path but missing from the session PATH (for example pnpm installed by an earlier run in the same terminal) is runnable by the tool that needs it in the same session, and a present-but-unreachable dependency is never reported as "install pnpm" [real-TTY UAT F-1 2026-11-07]

### Schedules

- [x] **SCHED-01**: A Schedules view lists the built-in schedules with name, script, target, state, interval and next run; a schedule is on by default when its target is installed and shown as unavailable when it is not [user request 2026-11-07]
- [x] **SCHED-02**: The built-ins are cache cleanup (the known growing caches) and updates for claude, opencode, Pi coding agent, cursor-agent and copilot when installed; the default is every 6 h starting at 00:00, and the user can change the interval and start time [user request 2026-11-07] *(amended 2026-11-07, 24.2 SPEC R2/R4/R9: the tmpdir-cleanup daemon moves from Policies into Schedules as a seventh built-in with its own cadence; cache cleanup runs only the package managers' own prune commands; intervals are whole hours dividing 24)*
- [x] **SCHED-03**: Schedules run as user-level timers (systemd user units on Linux, a launchd agent on macOS) with zero sudo, are written atomically and recorded in a receipt, and are removed when turned off or when the installer uninstalls [user request 2026-11-07]
- [x] **SCHED-04**: The cursor-agent update job checks `~/.local/bin/cursor-agent`: when it is a symlink again (a fresh update), it is replaced by a shim that passes through when a model is given and otherwise injects the configured default frontier model (requested: gpt-6.1-sol, xhigh, long context; the exact model id is verified against cursor-agent's model list at plan time) before exec'ing the symlink's target in cursor's install dir; `~/.local/bin/agent` is untouched and the shim is removed with cursor-agent [user request 2026-11-07] *(amended 2026-11-07, 24.2 SPEC R7: `cursor-agent --list-models` has no `gpt-6.1-sol`; the default is `gpt-5.6-sol-xhigh` ("GPT-5.6 Sol 1M Extra High"), **needs confirmation**; the shim execs the launcher `~/.local/bin/agent` points to at run time, and turning the schedule off restores the symlink)*
- [x] **SCHED-05**: Each schedule run appends a timestamped log line, and the view shows the last run and its result [user request 2026-11-07]

### Catalog audit

- [x] **AUDIT-01**: A catalog-audit skill loops over every registry entry and compares the pinned/verified version, the installed version and the latest online release, reads the changelog between them, and checks that install, update, removal and tuning steps still match upstream docs [user request 2026-11-07]
- [x] **AUDIT-02**: The skill audits the install and customization scripts (postinstall, shims, tweaks) for drift and unsafe patterns, writes one report per entry plus a summary of proposed registry and script changes, keeps per-entry state so the loop can resume, and changes nothing without approval [user request 2026-11-07]
- [x] **AUDIT-03**: Its first run covers opencode v2 and Pi coding agent's MCP support, and the resulting registry and postinstall updates land (e.g. Pi joins the agent-host list for MCP-registering hooks) [user report 2026-11-07] *(amended 2026-11-07, 24.3 SPEC R6-R9: the registry still installs OpenCode 1 through the v1-only installer, so R6 moves it to `opencode.ai/v2/install` and R7 writes v2's `permissions` rule; codegraph 1.6.2 has no `pi` target, so R8 registers Pi only through a supported path and never leaves a dangling `≈`; copilot joins the codegraph hook, absorbing Backlog 999.12)*
- [x] **AUDIT-04**: The skill is scored with skill-judge [user request 2026-11-07]

### Guard retirement

- [x] **GUARD-01**: No route writes a package-manager guard shim (npm, npx, pnpm, pip, pip3) or the `tools-installer ban` alias block; the writers, renderers and the npx translator are deleted [user request 2026-11-14: "Los alias de npx, npm, pip han demostrado ser un desastre"]
- [x] **GUARD-02**: Every route that runs the launch repair removes the installer-written ban block from `~/.myshellrc`, the zshrc and `~/.bashrc` and the sentinel-marked shims from the managed bin dir, naming each path; a failure is a warning, never a crash [user request 2026-11-14]
- [x] **GUARD-03**: The cleanup keeps every byte and file it did not write: user aliases, CR line endings, orphan markers, symlinks, unmarked or oversize files, and a marked file swapped for another file before the identity re-check that runs immediately before delete [user request 2026-11-14] *(amended 2026-11-14, 24.4 review cycles 1-2: a marked shim's identity (device, inode and bytes, through an O_NOFOLLOW re-open) is re-verified immediately before unlink, and a file swapped before that re-check is kept; no userspace unlink is atomic against a swap, so a swap between the re-check and the unlink is a documented residual, not excluded)*
- [x] **GUARD-04**: The Policies row `ban`, `make guard`/`make unguard`, `--guard`/`--unguard`, the Doctor guard section and the uninstall ban row are gone [user request 2026-11-14]
- [x] **GUARD-05**: Installer-spawned shells get PATH in its normal order, and installer lookups still skip a sentinel-marked leftover the launch could not remove [user request 2026-11-14]
- [x] **GUARD-06**: Live docs, the architecture rule doc, the catalog-audit surface list, REQUIREMENTS.md and the tests stop describing the guard as a feature [user request 2026-11-14]

### Install priority

- [x] **PRIO-01**: Install-method resolution tries Homebrew (formula or cask) first, then bun, then pnpm on the volta-provided Node runtime, then the earlier order; a host without Homebrew keeps the earlier order [user request 2026-11-14: "prefiero el order sea brew -> bun -> volta y despues lo demas"]
- [x] **PRIO-02**: A `bun` method kind installs an npm package with `bun add -g`, checks the declared Node floor (bun-installed CLIs run under node), runs the smoke check and wires bun's global bin dir into PATH [user request 2026-11-14]
- [x] **PRIO-03**: mmdc, puppeteer and pi install through bun first; mmdc and puppeteer keep their pnpm fallback; the vendor-installed agent CLIs keep their methods [user request 2026-11-14]
- [x] **PRIO-04**: A bun-installed tool gets owner `bun`, receipts, version status (npm registry latest), update within its declared range, `bun remove --global` removal, and the Doctor browser audit [user request 2026-11-14]
- [x] **PRIO-05**: Tools already owned by pnpm, volta, brew or a vendor installer keep their owner; nothing reinstalls or moves them [user request 2026-11-14]
- [x] **PRIO-06**: The bun method passes no `--trust` and writes no `trustedDependencies`; a blocked postinstall fails the smoke check with the trust command [user request 2026-11-14]
- [x] **PRIO-07**: README, the architecture rule doc, registry comments and REQUIREMENTS.md describe the new order and only verified bun claims [user request 2026-11-14]

### Lean

- [x] **LEAN-01**: Dead code is removed (agent policy modules, questionary chooser, `audit.py`, dead fields and messages) while race epochs stay [F11, F14, F15, G #9]
- [x] **LEAN-02**: App composition lives in an `installer/` module under pyright and the coverage gate [F12]
- [x] **LEAN-03**: `wizard_app.py` is split and review-history comments are dropped [F13]
- [x] **LEAN-04**: The run log is bounded [B 13 IN-08]

### Commit and push hooks

*(added 2026-11-16, 26 SPEC + CONTEXT)*

- [ ] **HOOK-01**: Every commit runs each static gate as its own hook entry calling its `make` target (lint, format-check, typecheck, security, dead-code, shellcheck); `make validate` runs them all through `pre-commit run --all-files`; no commit-stage hook runs tests [26 R1, D-03, D-04]
- [ ] **HOOK-02**: Every push runs each static gate and then `make test` (90% coverage gate), each as its own entry; any failure aborts the push [26 R2, D-05]
- [ ] **HOOK-03**: The push gate tests a tree equal to the pushed commit: unstaged edits are set aside and restored, and the push is refused for staged-uncommitted changes, untracked `.py` under `installer/` or `tests/`, or a pushed commit that is not HEAD [26 R3, D-01]
- [ ] **HOOK-04**: `make dev-setup` (renamed from `make install`) installs the commit hook and the push gate, idempotently, skips outside a git checkout and fails when `core.hooksPath` is set; `make setup` is removed and `make run` launches the wizard [26 R4, D-07, D-08]
- [ ] **HOOK-05**: GitHub accepts a commit on `main`, an admin's included, only after both CI checks passed on that exact SHA; changes land by branch push, green CI, fast-forward; docs-only changes get a fast pass under the same check names [26 R5, D-09, D-10, D-11]
- [ ] **HOOK-06**: The docs state each gate, its target and stage with measured timings, the branch → CI → `main` flow and the manual `enforce_admins` escape hatch; no doc claims `make validate` runs pre-commit unless it does [26 R6, D-06]

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
| SAFE-01 | Phase 17 | Complete |
| SAFE-02 | Phase 17 | Complete |
| SAFE-03 | Phase 17 | Complete |
| SAFE-04 | Phase 17 | Complete |
| SAFE-05 | Phase 17 | Complete |
| SAFE-06 | Phase 17 | Complete |
| SAFE-07 | Phase 17 | Complete |
| SAFE-08 | Phase 17 | Complete |
| SAFE-09 | Phase 17 | Complete |
| CI-01 | Phase 17 | Complete |
| CI-02 | Phase 17 | Complete |
| CI-03 | Phase 17 | Complete |
| REG-01 | Phase 18 | Complete |
| REG-02 | Phase 18 | Complete |
| REG-03 | Phase 18 | Complete |
| REG-04 | Phase 18 | Complete |
| REG-05 | Phase 18 | Complete |
| REG-06 | Phase 18 | Complete |
| REG-07 | Phase 18 | Complete |
| REG-08 | Phase 18 | Complete |
| REG-09 | Phase 18 | Complete |
| REG-10 | Phase 18 | Complete |
| STATE-01 | Phase 19 | Complete |
| STATE-02 | Phase 19 | Complete |
| STATE-03 | Phase 19 | Complete |
| STATE-04 | Phase 19 | Complete |
| STATE-05 | Phase 19 | Complete |
| STATE-06 | Phase 19 | Complete |
| STATE-07 | Phase 19 | Superseded (23.1) |
| PLAN-01 | Phase 20 | Complete |
| PLAN-02 | Phase 20 | Complete |
| PLAN-03 | Phase 20 | Complete |
| PLAN-04 | Phase 20 | Complete |
| PLAN-05 | Phase 20 | Complete |
| PLAN-06 | Phase 20 | Complete |
| PLAN-07 | Phase 20 | Complete |
| PLAN-08 | Phase 20 | Complete |
| UI-01 | Phase 21 | Complete |
| UI-02 | Phase 21 | Complete |
| UI-03 | Phase 21 | Complete |
| UI-04 | Phase 22 | Complete |
| UI-05 | Phase 21 | Complete |
| UI-06 | Phase 21 | Complete |
| UI-07 | Phase 21 | Complete |
| UI-08 | Phase 21 | Complete |
| LIFE-01 | Phase 22 | Complete |
| LIFE-02 | Phase 22 | Complete |
| LIFE-03 | Phase 22 | Complete |
| LIFE-04 | Phase 22 | Complete |
| LIFE-05 | Phase 22 | Complete |
| LIFE-06 | Phase 22 | Complete |
| LIFE-07 | Phase 22 | Complete |
| LIFE-08 | Phase 22 | Complete |
| LIFE-09 | Phase 22 | Complete |
| LIFE-10 | Phase 22 | Complete |
| CONF-01 | Phase 23 | Complete |
| CONF-02 | Phase 23 | Complete |
| CONF-03 | Phase 23 | Complete |
| CONF-04 | Phase 23 | Complete |
| CONF-05 | Phase 23 | Complete |
| CONF-06 | Phase 23 | Complete |
| CONF-07 | Phase 23 | Complete |
| CONF-08 | Phase 23 | Complete |
| CONF-09 | Phase 23 | Complete |
| CONF-10 | Phase 23 | Complete |
| CONF-11 | Phase 23 | Complete |
| CONF-12 | Phase 23 | Complete |
| ONB-01 | Phase 24 | Complete |
| ONB-02 | Phase 24 | Complete |
| ONB-03 | Phase 24 | Complete |
| ONB-04 | Phase 24 | Complete |
| ONB-05 | Phase 24 | Complete |
| ONB-06 | Phase 24 | Complete |
| ONB-07 | Phase 24 | Complete |
| ONB-08 | Phase 24.1 | Complete |
| ONB-09 | Phase 24.1 | Complete |
| ONB-10 | Phase 24.1 | Complete |
| HOST-01 | Phase 23.1 | Complete |
| HOST-02 | Phase 23.1 | Complete |
| HOST-03 | Phase 23.1 | Complete |
| HOST-04 | Phase 23.1 | Complete |
| HOST-05 | Phase 23.1 | Complete |
| TUNE-01 | Phase 23.2 | Complete |
| TUNE-02 | Phase 23.2 | Complete |
| TUNE-03 | Phase 23.2 | Complete |
| TUNE-04 | Phase 23.2 | Complete |
| TUNE-05 | Phase 23.2 | Complete |
| TUNE-06 | Phase 23.2 | Complete |
| TUNE-07 | Phase 23.2 | Complete |
| SCHED-01 | Phase 24.2 | Complete |
| SCHED-02 | Phase 24.2 | Complete |
| SCHED-03 | Phase 24.2 | Complete |
| SCHED-04 | Phase 24.2 | Complete |
| SCHED-05 | Phase 24.2 | Complete |
| AUDIT-01 | Phase 24.3 | Complete |
| AUDIT-02 | Phase 24.3 | Complete |
| AUDIT-03 | Phase 24.3 | Complete |
| AUDIT-04 | Phase 24.3 | Complete |
| GUARD-01 | Phase 24.4 | Complete |
| GUARD-02 | Phase 24.4 | Complete |
| GUARD-03 | Phase 24.4 | Complete |
| GUARD-04 | Phase 24.4 | Complete |
| GUARD-05 | Phase 24.4 | Complete |
| GUARD-06 | Phase 24.4 | Complete |
| PRIO-01 | Phase 24.5 | Complete |
| PRIO-02 | Phase 24.5 | Complete |
| PRIO-03 | Phase 24.5 | Complete |
| PRIO-04 | Phase 24.5 | Complete |
| PRIO-05 | Phase 24.5 | Complete |
| PRIO-06 | Phase 24.5 | Complete |
| PRIO-07 | Phase 24.5 | Complete |
| LEAN-01 | Phase 25 | Complete |
| LEAN-02 | Phase 25 | Complete |
| LEAN-03 | Phase 25 | Complete |
| LEAN-04 | Phase 25 | Complete |
| HOOK-01 | Phase 26 | Pending |
| HOOK-02 | Phase 26 | Pending |
| HOOK-03 | Phase 26 | Pending |
| HOOK-04 | Phase 26 | Pending |
| HOOK-05 | Phase 26 | Pending |
| HOOK-06 | Phase 26 | Pending |

**Coverage:**

- v1 requirements: 115 total *(recounted 2026-11-07 in 23.2: HOST, TUNE, SCHED and AUDIT rows were not counted)* *(amended 2026-11-14, 24.4 SPEC: GUARD-01..06 added)* *(amended 2026-11-14, 24.5 SPEC: PRIO-01..07 added)* *(amended 2026-11-16, 26 SPEC: HOOK-01..06 added; 121 total)*
- Mapped to phases: 121 (Phase 17: 12, Phase 18: 10, Phase 19: 7, Phase 20: 8, Phase 21: 7, Phase 22: 11, Phase 23: 12, Phase 23.1: 5, Phase 23.2: 7, Phase 24: 7, Phase 24.1: 3, Phase 24.2: 5, Phase 24.3: 4, Phase 24.4: 6, Phase 24.5: 7, Phase 25: 4, Phase 26: 6)
- Unmapped: 0
- Mapping note: UI-04 sits in Phase 22, not Phase 21 (TA §8 P5), because it needs `config_paths` (LIFE-04)

---
*Requirements defined: 2026-10-13*
*Last updated: 2026-10-13 after roadmap creation (traceability filled)*
