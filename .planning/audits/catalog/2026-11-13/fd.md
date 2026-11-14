# fd - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: 10.5.2 (`fd --version`, per `make audit-catalog facts fd`)
- latest: v10.5.2 (GitHub releases/latest, https://api.github.com/repos/sharkdp/fd/releases/latest, published 2026-11-07)
- latest: 10.5.2 (Homebrew formula, https://formulae.brew.sh/api/formula/fd.json)

## Changelog
- none between installed 10.5.2 and latest v10.5.2; the v10.5.2 notes change only zsh completions and `--format` output on a pipe (https://github.com/sharkdp/fd/releases/tag/v10.5.2)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/sharkdp/fd/master/README.md "Installation": the vendor recommends distro packages `fd-find` on Ubuntu, Debian and Fedora, but says the binary there is `fdfind`; the registry therefore uses the musl release archives for Linux (installer/registry.toml:211-222, binary `fd`) and brew for macOS, which the vendor's own note on the `fd`-named release binaries supports; every Linux arch and macOS arch has an asset that `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section) |
| update argv | n/a | reason: the entry declares no update argv and fd ships no self-update command; facts report update none, so the installer re-runs the method |
| removal recipe and paths | ok | the github_release method extracts only the `fd` member (installer/registry.toml:216, `member = "fd"`, `strip = 1`), so removal is the receipt of that one binary (L2); the brew method removes through brew (L1); the entry declares no config_paths (installer/registry.toml:207-216) and fd creates no config file on install (README "Installation" names only packages and binaries) |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts fd`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts fd` reports postinstall none and post_install none; installer/registry.toml:207-225 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
