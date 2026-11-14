# container - catalog audit 2026-11-13

## Versions
- pinned: unpinned (brew)
- verified: 2026-09-06
- installed: none (not installed on this host)
- latest: 1.7.1 (formulae.brew.sh formula JSON, https://formulae.brew.sh/api/formula/container.json)
- latest: 1.7.1 (GitHub releases/latest, published 2026-11-06, https://github.com/apple/container/releases/tag/1.7.1)

## Changelog
- 1.7.1 reduces the install package size and install footprint (https://github.com/apple/container/releases/tag/1.7.1)
- 1.7.1 default DNS nameservers, search domains and options can be set in config.toml (https://github.com/apple/container/pull/1614)
- 1.7.1 default Kata kernel is now 4.3.1 (https://github.com/apple/container/pull/2447)
- 1.4.1 to 1.6.1 carry no install, update, removal, config or MCP note (https://github.com/apple/container/releases)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | formulae.brew.sh/api/formula/container.json lists requirements macos 26 and arch arm64, matching `installer/registry.toml` min_os_version "26"; upstream README (https://github.com/apple/container/blob/main/README.md, Requirements) says Apple silicon and macOS 26 or later; the README's documented install is the signed package (Initial install), a Homebrew formula is a package-manager choice under step 4 |
| update argv | ok | the entry declares no argv and derives update from brew; upstream `update-container.sh` (README, Upgrade or downgrade) belongs to the signed-package install that this entry does not use |
| removal recipe and paths | unknown | reason: container check not run (no container run in this batch); the brew remove is the manager's; the upstream uninstall script `uninstall-container.sh -d` (README, Uninstall) belongs to the signed-package install; the location of user data and config.toml is unverified in the read docs, so `config_paths` "none" cannot be confirmed |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | unknown | reason: the formula caveat says no kernel is installed automatically (`container system kernel set --recommended`, formulae.brew.sh formula JSON caveats); whether that step is install tuning needs the user's answer under tool-onboarding step 7 |

## Proposed changes
- none

<!-- catalog-audit:complete -->
