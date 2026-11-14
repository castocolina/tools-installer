# gh - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned, installer/registry.toml:471-489)
- verified: 2026-11-04 (installer/registry.toml:467)
- installed: 2.101.0 (`gh --version`, per the facts block)
- latest: v2.104.0 (GitHub releases/latest, https://api.github.com/repos/cli/cli/releases/latest)
- latest: 2.104.0 (Homebrew formula, https://formulae.brew.sh/api/formula/gh.json)
- note: GitHub and Homebrew agree on 2.104.0, so there is no major split

## Changelog
- v2.103.0 adds opt-in expiring OAuth credentials through the config key `gh config set expiring_credentials enabled`, plus a `prefer_expiring_credentials` config option (https://api.github.com/repos/cli/cli/releases?per_page=8)
- v2.103.0 also stores the refresh lock and state under gh's state directory, which the config path does not cover (https://api.github.com/repos/cli/cli/releases?per_page=8)
- v2.103.1 documents extrepo installation on Debian, a method the registry does not use (https://api.github.com/repos/cli/cli/releases?per_page=8)
- v2.104.0 skips token refresh when gh's state directory is not writable and clarifies which hosts use GH_ENTERPRISE_TOKEN (https://api.github.com/repos/cli/cli/releases?per_page=8)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README lists Homebrew and the precompiled release binaries for macOS and Linux (https://raw.githubusercontent.com/cli/cli/trunk/README.md lines 35-48); the registry uses the checksummed release assets first and brew second (installer/registry.toml:471-489); linux and macOS amd64 and arm64 assets pass for 2.104.0 (.planning/audits/catalog/2026-11-13/verify-registry.md:134-137) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:460-489); the README documents no self-upgrade command, and brew upgrades go through brew itself (https://raw.githubusercontent.com/cli/cli/trunk/README.md lines 39-48) |
| removal recipe and paths | drift | the entry declares config_paths ~/.config/gh only (installer/registry.toml:470), which matches the manual's config default (https://cli.github.com/manual/gh_help_environment, GH_CONFIG_DIR), but gh's state directory is $XDG_STATE_HOME/gh or ~/.local/state/gh (https://raw.githubusercontent.com/cli/go-gh/trunk/pkg/config/config.go lines 291-303) and holds state.yml, telemetry and the refresh lock (https://raw.githubusercontent.com/cli/cli/v2.104.0/internal/config/refreshable.go lines 113-117); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:460-489, facts tuning: none); expiring_credentials is an opt-in user preference the installer never writes |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:460-489, facts postinstall: none) |

## Proposed changes
- add ~/.local/state/gh to the gh entry's config_paths so the state directory is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/cli/go-gh/trunk/pkg/config/config.go lines 291-303

<!-- catalog-audit:complete -->
