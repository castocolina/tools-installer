# claude - catalog audit 2026-11-13

## Versions
- pinned: none (script and cask methods are unpinned)
- verified: 2026-11-04
- installed: 2.1.323 (`claude --version`, via `facts claude`)
- latest: 2.1.311 (Homebrew cask API, claude-code tracks the stable channel, https://formulae.brew.sh/api/cask/claude-code.json)
- latest: 2.1.325 (npm dist-tag latest, https://registry.npmjs.org/@anthropic-ai/claude-code)
- latest: 2.1.325 (GitHub releases/latest, https://api.github.com/repos/anthropics/claude-code/releases/latest)
- note: channel split, the cask serves the stable channel (2.1.311, npm dist-tag stable) while the native script installs the latest channel (2.1.325); judged against 2.1.325 for the script and against stable for the cask

## Changelog
- no install, update, removal or settings-key note between 2.1.323 and 2.1.325 (https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- 2.1.325 fixes several MCP connection and authentication states and leftover `.oauth_refresh.lock.owner.tmp.*` files in the config directory; none changes the MCP config format (https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md)
- the setup docs say the native installer auto-updates in the background and Homebrew installs do not, https://code.claude.com/docs/en/setup

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's native installer is `curl -fsSL https://claude.ai/install.sh`, and `brew install --cask claude-code` is the documented Homebrew route, https://code.claude.com/docs/en/setup; `installer/registry.toml:1531` and `installer/registry.toml:1545` declare exactly those |
| update argv | ok | `installer/registry.toml:1541` declares `claude update`, which the setup docs document for native installs and the release channel setting, https://code.claude.com/docs/en/setup |
| removal recipe and paths | ok | `installer/registry.toml:1540` declares `~/.local/bin/claude` and `~/.local/share/claude/`, the two paths the docs section "Uninstall a native installation" removes (`rm -f ~/.local/bin/claude`, `rm -rf ~/.local/share/claude`), https://code.claude.com/docs/en/setup; the cask is removed by brew (L1) |
| tuning keys | ok | `installer/agent_settings.py:668` and `installer/agent_settings.py:669` write `permissions.defaultMode = bypassPermissions` (valid enum value) and `skipDangerousModePermissionPrompt`; `installer/agent_settings.py:672` and `installer/agent_settings.py:673` write `attribution.commit` and `attribution.pr`, with empty string documented as hiding attribution; all present and not deprecated in https://json.schemastore.org/claude-code-settings.json (only `includeCoAuthoredBy` is marked deprecated, and the entry does not write it) |
| postinstall hook | ok | the entry has no hook of its own; the shared codegraph hook maps `claude` at `installer/postinstall.py:162`, and codegraph v1.6.2 `--target claude` writes `mcpServers` into `~/.claude.json` (user scope), the file the MCP docs name, https://raw.githubusercontent.com/colbymchenry/codegraph/v1.6.2/src/installer/targets/claude.ts and https://code.claude.com/docs/en/mcp |

## Proposed changes
- none

<!-- catalog-audit:complete -->
