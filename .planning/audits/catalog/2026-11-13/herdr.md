# herdr - catalog audit 2026-11-13

## Versions
- pinned: none (github_release assets are unpinned; each asset is checked by the sha256 digest the GitHub API returns)
- verified: 2026-11-08
- installed: 0.9.5 (`herdr --version`)
- latest: v0.9.5 (GitHub releases/latest, https://api.github.com/repos/herdrdev/herdr/releases/latest, published 2026-10-14)
- latest: 0.9.5 (Homebrew formula stable, https://formulae.brew.sh/api/formula/herdr.json)

## Changelog
- no install, update, removal, config or MCP note between 0.9.5 and 0.9.5

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the four asset URLs at v0.9.5 pass verify-registry.md (Passed section, .planning/audits/catalog/2026-11-13/verify-registry.md); the vendor's manual-download table lists the same asset names, https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/install.mdx; registry.toml:3153-3166 declares linux (debian, fedora, arch) and macos for both arches |
| update argv | ok | the entry declares no update argv by design (installer re-runs the method); the vendor says `herdr update` is for installs managed by Herdr's own installer, so the manual-download route has no vendor self-update, https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/install.mdx; the self-update's BROKEN receipt is a known limit in registry.toml:3138-3140, not drift |
| removal recipe and paths | ok | binary: L2 receipt of the github_release method (tool-onboarding step 4b); config paths match upstream: config_dir `~/.config/herdr` (https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/configuration.mdx) and state_dir `~/.local/state/herdr` (https://github.com/herdrdev/herdr/blob/v0.9.5/src/config/io.rs, fn state_dir and platform_state_dir); hook removal is handled by the postinstall unregister, installer/postinstall.py:378-387; `herdr plugin uninstall` keeps config and state (https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/plugins.mdx); note: `~/.herdr/worktrees` appears only as a user example in configuration.mdx and is not declared or created by the installer |
| tuning keys | ok | installer/agent_settings.py:718 maps `default-shell` to `terminal.default_shell`; upstream key exists at v0.9.5: https://github.com/herdrdev/herdr/blob/v0.9.5/src/config/model.rs (TerminalConfig.default_shell) and https://github.com/herdrdev/herdr/blob/v0.9.5/docs/next/website/src/content/docs/configuration.mdx (`[terminal] default_shell`) |
| postinstall hook | ok | registry.toml:3152 `postinstall = "herdr-integration"`; installer/postinstall.py:213-227 maps the 13 harnesses to herdr targets, each accepted by `parse_integration_target` at https://github.com/herdrdev/herdr/blob/v0.9.5/src/cli/integration.rs (factory-droid maps to droid, postinstall.py:226); the v0.9.5 changelog says Codex turn hooks are no longer installed and `herdr integration install codex` updates, https://github.com/herdrdev/herdr/blob/v0.9.5/CHANGELOG.md; the sidebar plugin pinned to castocolina/herdr-setup is a third-party source, unverified here |

## Proposed changes
- add a brew method for macOS and Linux, since the formula is at the current 0.9.5 and tool-onboarding step 4 ranks a current package manager above a release asset; risk: low; evidence: https://formulae.brew.sh/api/formula/herdr.json

<!-- catalog-audit:complete -->
