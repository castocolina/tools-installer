# cursor-agent - catalog audit 2026-11-13

## Versions
- pinned: none (the script method installs whatever cursor.com/install serves)
- verified: 2026-11-04
- installed: 2026.10.22-27dcf5f (`cursor-agent --version`, via `facts cursor-agent`)
- latest: 2026.11.13-eacade1 (version embedded in the served install script, https://cursor.com/install, DOWNLOAD_URL line 85)
- note: the registry declares no latest source; the script's embedded version is the only upstream version signal read, and the CLI auto-updates by default per https://cursor.com/docs/cli/installation

## Changelog
- the install script now checks for a `grok-switch.json` record under the Cursor config dir and may run `cursor-agent --version` to finish a switch to a "Grok agent host"; it adds no new install path (https://cursor.com/install, lines 133-146)
- no install, update, removal or settings-key note found on the vendor changelog for the CLI since 2026.10.22 (https://cursor.com/changelog)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the docs give one route for macOS, Linux and WSL, the curl install script, and name no brew or cask CLI package, https://cursor.com/docs/cli/installation; `installer/registry.toml:1627` declares that script |
| update argv | ok | `installer/registry.toml:1641` declares `cursor-agent update`; the docs give `agent update` and both names are symlinks to one binary (script lines 130-131), https://cursor.com/docs/cli/installation |
| removal recipe and paths | ok | `installer/registry.toml:1637` and the two links declared beside it match the script: versions tree at line 110 and the `agent` and `cursor-agent` links at lines 130-131, https://cursor.com/install; the docs name no uninstall command; the line numbers quoted in the registry comment (77-111, 124-126) are stale, the paths are not |
| tuning keys | ok | `installer/agent_settings.py:683` writes `approvalMode = unrestricted` (documented values: allowlist, auto-review, unrestricted) and `installer/agent_settings.py:686` and `installer/agent_settings.py:687` write `attribution.attributeCommitsToAgent` and `attribution.attributePRsToAgent`, both documented booleans in `~/.cursor/cli-config.json`, https://cursor.com/docs/cli/reference/configuration |
| postinstall hook | ok | the entry has no hook of its own; the shared codegraph hook maps `cursor` at `installer/postinstall.py:165`, and codegraph v1.6.2 `--target cursor` writes `mcpServers` into `~/.cursor/mcp.json`, https://raw.githubusercontent.com/colbymchenry/codegraph/v1.6.2/src/installer/targets/cursor.ts, the global file the Cursor docs name, https://cursor.com/docs/context/mcp |

## Proposed changes
- none

<!-- catalog-audit:complete -->
