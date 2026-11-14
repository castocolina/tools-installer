# lazygit - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned, installer/registry.toml:439-457)
- verified: 2026-11-03 (installer/registry.toml:437)
- installed: 0.63.1 (`lazygit --version`, per the facts block)
- latest: v0.66.3 (GitHub releases/latest, https://api.github.com/repos/jesseduffield/lazygit/releases/latest)
- latest: 0.66.3 (Homebrew formula, https://formulae.brew.sh/api/formula/lazygit.json)
- note: GitHub and Homebrew agree on 0.66.3, so there is no major split

## Changelog
- v0.64.0 renames the custom pager config to diff renderer, a config key rename (https://api.github.com/repos/jesseduffield/lazygit/releases?per_page=12)
- v0.64.0 moves the GitHub PR cache out of state.yml into a separate file in the config directory (https://api.github.com/repos/jesseduffield/lazygit/releases?per_page=12)
- v0.65.1 stops loading or migrating the user config in daemon mode (https://api.github.com/repos/jesseduffield/lazygit/releases?per_page=12)
- no install, update or MCP note between 0.63.1 and 0.66.3 (https://api.github.com/repos/jesseduffield/lazygit/releases?per_page=12)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README lists Homebrew (https://raw.githubusercontent.com/jesseduffield/lazygit/master/README.md lines 277-284) and the official release tarball with checksums (lines 378-388); the registry uses the release assets first and brew second (installer/registry.toml:439-457); linux and macOS arm64 and amd64 assets pass for 0.66.3 (.planning/audits/catalog/2026-11-13/verify-registry.md:183-186) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:430-457); the README documents no self-update command, and brew upgrades go through brew itself (https://raw.githubusercontent.com/jesseduffield/lazygit/master/README.md lines 277-284) |
| removal recipe and paths | drift | the entry declares no config_paths (installer/registry.toml:430-457), but the upstream docs put config.yml and the state files in ~/.config/lazygit on Linux and ~/Library/Application Support/lazygit on macOS (https://raw.githubusercontent.com/jesseduffield/lazygit/master/docs/Config.md lines 5-6 and 1001); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:430-457, facts tuning: none) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:430-457, facts postinstall: none) |

## Proposed changes
- add config_paths = ["~/.config/lazygit", "~/Library/Application Support/lazygit"] to the lazygit entry so the config and state directory is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazygit/master/docs/Config.md lines 5-6 and 1001

<!-- catalog-audit:complete -->
