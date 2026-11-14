# dust - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: 1.2.6 (`dust --version`, per `make audit-catalog facts dust`)
- latest: v1.2.7 (GitHub releases/latest, https://api.github.com/repos/bootandy/dust/releases/latest, published 2026-11-01)
- latest: 1.2.7 (Homebrew formula, https://formulae.brew.sh/api/formula/dust.json)

## Changelog
- the v1.2.7 release has no notes body, so the changes come from the compare https://github.com/bootandy/dust/compare/v1.2.6...v1.2.7 (16 commits)
- config: c5e1855 "feat: support ignore-directory and invert-filter in config file" adds two keys to the user's config file (README "Config file", https://raw.githubusercontent.com/bootandy/dust/master/README.md); the installer writes no dust config, so nothing it owns changes
- release assets: 5ec8b30 "ci: release a Windows ARM64 GNU-family artifact" adds a Windows asset only; the Linux and macOS asset names are unchanged, and `make verify-registry` passed the v1.2.7 archives (`.planning/audits/catalog/2026-11-13/verify-registry.md`, lines 116-119)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/bootandy/dust/master/README.md "Install" still lists Homebrew (`brew install dust`, Linux and macOS), Cargo, the install.sh quick install and the package managers; the registry's github_release and brew methods match (installer/registry.toml:766-791); the musl and apple-darwin archives are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section, lines 116-119) |
| update argv | ok | the entry declares no update argv, so the installer re-runs the method (`make audit-catalog facts dust`); the upgrade route the vendor documents is the same method (Homebrew `brew upgrade dust`, GitHub archive), and the 1.2.7 archive replaces 1.2.6 |
| removal recipe and paths | ok | the github_release method extracts only the `dust` member (installer/registry.toml:780-781, `member = "dust"`, `strip = 1`), so removal is the receipt of that binary; brew removes through brew; the entry declares no paths (installer/registry.toml:766-791); the config file at `~/.config/dust/config.toml` is the user's own (README "Config file") and install never writes it |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts dust`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts dust` reports postinstall none and post_install none; installer/registry.toml:766-791 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
