# copilot - catalog audit 2026-11-13

## Versions
- pinned: none (cask and github_release methods are unpinned)
- verified: 2026-11-07
- installed: unknown: `copilot --version` prints no version number (via `facts copilot`)
- latest: v1.0.112 (GitHub releases/latest, https://api.github.com/repos/github/copilot-cli/releases/latest)
- latest: 1.0.111 (Homebrew cask API, https://formulae.brew.sh/api/cask/copilot-cli.json)
- note: the cask lags the GitHub release by one patch, which is normal propagation and not a major split

## Changelog
- user-editable settings live in `~/.copilot/settings.json`; `config.json` now holds internal state only and its user settings are ignored (docs, https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference)
- `~/.copilot/mcp-config.json` is the user-level MCP definitions file, and a broken file is now reported by name instead of silently skipped (changelog 1.0.x entries, https://github.com/github/copilot-cli/blob/main/changelog.md)
- `copilot update` exists and honours an `autoUpdatesChannel` setting (changelog, https://github.com/github/copilot-cli/blob/main/changelog.md)
- no install-asset rename or removal note in 1.0.112 (https://github.com/github/copilot-cli/releases/tag/v1.0.112)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README lists the install script, Homebrew cask (macOS and Linux), WinGet and npm, https://github.com/github/copilot-cli#installation; `installer/registry.toml:1681` declares the macOS cask and `installer/registry.toml:1686` the linux x64 and arm64 tarballs with `installer/registry.toml:1687` `SHA256SUMS.txt`, and verify-registry.md lines 83-84 list both tarballs as passed |
| update argv | ok | `installer/registry.toml:1681` method set declares no update argv, deliberately: the cask auto-updates and the checksummed tarball is re-run by the installer; `copilot update` exists upstream (https://github.com/github/copilot-cli/blob/main/changelog.md) but is not needed for either declared method |
| removal recipe and paths | ok | the github_release method is removed by its install receipt (L2) and the cask by brew (L1); the README and config docs name no uninstall command, https://github.com/github/copilot-cli#installation; the settings directory `~/.copilot` is a harness marker kept on removal |
| tuning keys | ok | `installer/agent_settings.py:689` writes `defaultPermissionMode = allow-all` (documented enum manual, assisted, allow-all; ignored for -p, --server and --acp runs) and `installer/agent_settings.py:690` writes `includeCoAuthoredBy = false` (documented boolean, default true), both in `~/.copilot/settings.json` which `installer/agent_env.py:67` targets, https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference |
| postinstall hook | ok | the entry declares none and `installer/postinstall.py` has no copilot row in `_CODEGRAPH_TARGETS`, a recorded decision (registry comment: copilot declined as a codegraph hook target, recommends only); for information, codegraph v1.6.2 now ships a `copilot-cli` target that writes `mcpServers` into `~/.copilot/mcp-config.json`, https://raw.githubusercontent.com/colbymchenry/codegraph/v1.6.2/src/installer/targets/copilot-cli.ts, matching the documented user-level MCP file |

## Proposed changes
- none

<!-- catalog-audit:complete -->
