# dasel - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew, installer/registry.toml:1377-1402)
- verified: 2026-11-03 (installer/registry.toml:1384)
- installed: none (not installed on this host, per the facts block)
- latest: v3.11.2 (GitHub releases/latest, published 2026-06-27, https://api.github.com/repos/TomWright/dasel/releases/latest)
- latest: 3.11.2 (Homebrew formula, https://formulae.brew.sh/api/formula/dasel.json)

## Changelog
- v3.11.0 (2026-05-19) adds newline-delimited JSON input and makes the version command output consistent; no note touches install, update, removal, config or MCP (https://api.github.com/repos/TomWright/dasel/releases?per_page=4)
- v3.11.1 (2026-06-20) and v3.11.2 (2026-06-27) publish only a compare link and no notes (https://api.github.com/repos/TomWright/dasel/releases?per_page=4)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the v3.11.2 release has raw dasel_linux_amd64, dasel_linux_arm64, dasel_darwin_amd64 and dasel_darwin_arm64 binaries (https://api.github.com/repos/TomWright/dasel/releases/latest), which pass in .planning/audits/catalog/2026-11-13/verify-registry.md:85-88; the brew formula serves 3.11.2 (https://formulae.brew.sh/api/formula/dasel.json); the vendor installation page also lists Docker, go install, asdf, mise, nix, scoop and a manual route (https://daseldocs.tomwright.me/getting-started/installation), which the registry does not use; distro package currency is unverified and not compared |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:1377-1402, facts update: none); the vendor installation page documents no upgrade or uninstall command (https://daseldocs.tomwright.me/getting-started/installation) |
| removal recipe and paths | drift | dasel reads a user config file at the default path ~/dasel.yaml (https://api.github.com/repos/TomWright/dasel/contents/internal/cli/query.go?ref=v3.11.2 line 17, and https://api.github.com/repos/TomWright/dasel/contents/internal/cli/interactive.go?ref=v3.11.2 line 32), loaded read-only by LoadConfig (https://api.github.com/repos/TomWright/dasel/contents/internal/cli/config.go?ref=v3.11.2 lines 26-57), but the entry declares no config_paths (installer/registry.toml:1377-1402) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:1377-1402, facts tuning: none); the only key the vendor reads, default_format, sits in the user's own ~/dasel.yaml (https://api.github.com/repos/TomWright/dasel/contents/internal/cli/config.go?ref=v3.11.2 lines 14-17), which the installer never writes |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:1377-1402, facts postinstall: none) |

## Proposed changes
- add config_paths = ["~/dasel.yaml"] to the dasel entry so the user's config file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/TomWright/dasel/contents/internal/cli/query.go?ref=v3.11.2 line 17

<!-- catalog-audit:complete -->
