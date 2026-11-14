# just - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: 1.59.0 (`just --version`, per `make audit-catalog facts just`)
- latest: 1.59.0 (GitHub releases/latest, https://api.github.com/repos/casey/just/releases/latest, published 2026-10-15)
- latest: 1.59.0 (Homebrew formula, https://formulae.brew.sh/api/formula/just.json)

## Changelog
- no install, update, removal, config or MCP note between 1.59.0 and 1.59.0; the installed version is the latest release

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/casey/just/master/README.md "Installation" still lists Homebrew (`brew install just`), pacman, apt, DNF and the release archives with a SHA256SUM file; the registry methods match (installer/registry.toml:702-730); the musl and apple-darwin archives are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section, lines 175-178) |
| update argv | ok | the entry declares no update argv, so the installer re-runs the method (`make audit-catalog facts just`); the README documents no self-update command, so re-running the method is the vendor's upgrade path |
| removal recipe and paths | ok | the github_release method extracts only the `just` member (installer/registry.toml:717, `member = "just"`) so removal is the receipt of that one binary; the brew method removes through brew; the entry declares no paths (installer/registry.toml:702-730) and just writes no config on install (README "Installation") |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts just`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts just` reports postinstall none and post_install none; installer/registry.toml:702-730 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
