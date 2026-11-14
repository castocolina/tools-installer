# bottom - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: 0.14.9 (`btm --version`, per `make audit-catalog facts bottom`)
- latest: 0.15.0 (GitHub releases/latest, https://api.github.com/repos/ClementTsang/bottom/releases/latest, published 2026-11-01)
- latest: 0.15.0 (Homebrew formula, https://formulae.brew.sh/api/formula/bottom.json)

## Changelog
- 0.15.0 config keys (https://github.com/ClementTsang/bottom/blob/0.15.0/CHANGELOG.md): #2224 adds a Linux process swap column; #2236 and #2251 add configurable binary disk capacity units; #2245 adds `styles.widgets.bar_type`; #2260 turns scrollbars on by default; #2174 (0.14.x-era config key, listed in the same file) is already in 0.14.9
- 0.15.0 install notes (CHANGELOG.md): #2233 and #2237 change the Windows MSI installer scope, and #2290 adds a Windows aarch64 build target; none of these is a Linux or macOS install path the registry uses
- no update, removal or MCP note between 0.14.9 and 0.15.0; the 0.15.0 assets for Linux and macOS are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section, lines 72-75)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/ClementTsang/bottom/master/README.md "Installation" still lists the official Arch package (`pacman -S bottom`, line 202), the Fedora COPR (`dnf install bottom`, lines 259-269), Homebrew (`brew install bottom`, line 349) and Cargo; the registry's github_release and brew methods match (installer/registry.toml:822-846); the musl and apple-darwin archives are the ones `make verify-registry` passed (verify-registry.md, Passed section, lines 72-75) |
| update argv | ok | the entry declares no update argv, so the installer re-runs the method (`make audit-catalog facts bottom`); the vendor's upgrade routes are the same archive or `brew upgrade bottom`, and the 0.15.0 archive replaces 0.14.9 |
| removal recipe and paths | ok | the github_release method extracts only the `btm` member (installer/registry.toml:836 and 843, `member = "btm"`), so removal is the receipt of that binary; brew removes through brew; the entry declares no paths (installer/registry.toml:822-846); bottom's config file is written by the user, not by the installer (README "Customizable behaviour", line 91) |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts bottom`: tuning none); the 0.15.0 config keys are the user's own config, not installer tuning |
| postinstall hook | ok | `make audit-catalog facts bottom` reports postinstall none and post_install none; installer/registry.toml:822-846 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
