# vscode - catalog audit 2026-11-13

## Versions
- pinned: none (app and tarball use the update.code.visualstudio.com latest redirect; the cask is unpinned)
- verified: 2026-11-03
- installed: 1.146.0 (`code --version`, per the facts block)
- latest: 1.146.0 (Homebrew cask visual-studio-code, https://formulae.brew.sh/api/cask/visual-studio-code.json)
- latest: 1.146.0 (release notes page, https://code.visualstudio.com/updates/v1_146)
- note: the Linux ownership cask visual-studio-code-linux returned HTTP 503 from the Homebrew API, so it gives no version

## Changelog
- 1.146 notes (https://code.visualstudio.com/updates/v1_146): the Local agent harness is deprecated and will be removed in February 2027; the "Deprecated features and settings" section lists only that item, so no lean-list key is deprecated there
- installed equals latest, so no other range was read

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor Linux page documents an apt repository first (https://code.visualstudio.com/docs/setup/linux); the tarball stays because the apt route needs root (AGENTS.md zero sudo); update.code.visualstudio.com latest/linux-x64/stable, linux-arm64/stable, darwin/stable and darwin-arm64/stable each 302 to the 1.146 builds (curl -sIL); asset rows in verify-registry.md lines 230-233 |
| update argv | unknown | reason: the registry declares none; whether the in-app updater works for a tarball install is not established from the sources read; container check not run (batch rule: no containers) |
| removal recipe and paths | drift | installer/agent_env.py:81 writes the agent settings to vscode_user / settings.json, whose directory is set at installer/agent_env.py:36-39 (~/.config/Code/User on Linux, ~/Library/Application Support/Code/User on macOS), but the entry declares no config_paths (registry.toml:2438-2503) |
| tuning keys | ok | every key in installer/agent_settings.py:634-655 (_VSCODE_LEAN) and in the vscode-ai-off and vscode-ext-updates-off groups exists upstream on main: telemetry.telemetryLevel (src/vs/platform/telemetry/common/telemetry.ts:110), window.restoreWindows with enum including one (src/vs/workbench/electron-browser/desktop.contribution.ts:182-184), workbench.settings.enableNaturalLanguageSearch (src/vs/workbench/contrib/preferences/common/preferencesContribution.ts:117), extensions.autoUpdate, extensions.autoCheckUpdates and extensions.ignoreRecommendations (src/vs/workbench/contrib/extensions/browser/extensions.contribution.ts:138, 189, 196), chat.disableAIFeatures (src/vs/platform/chat/common/chatSettings.ts:6), workbench.startupEditor, editor.minimap.enabled, files.watcherExclude, search.followSymlinks, workbench.enableExperiments and update.mode (each found by search and its definition read on main); npm.autoDetect, git.autoRepositoryDetection and typescript.disableAutomaticTypeAcquisition (extensions/npm/package.json:231, extensions/git/package.json:3305, extensions/typescript-language-features/package.json:2408); task.autoDetect (src/vs/workbench/contrib/tasks/browser/task.contribution.ts:515); terminal.integrated.defaultProfile is defined in src/vs/platform/terminal/common/terminalPlatformConfiguration.ts (path located, line not read); the checks are against main, not the 1.146.0 tag |
| postinstall hook | ok | apply_agent_tuning and show_lean_tips are in the closed hook table (installer/post_install.py:483-484); apply_agent_tuning goes through _tune_agent (installer/post_install.py:405), which calls apply_setting per group; the key-level merge inside apply_setting was not read in this audit |

## Proposed changes
- declare the VS Code User directory per OS as config_paths (~/.config/Code/User on Linux, ~/Library/Application Support/Code/User on macOS) with the default keep policy; risk: medium; evidence: installer/agent_env.py:36-39

<!-- catalog-audit:complete -->
