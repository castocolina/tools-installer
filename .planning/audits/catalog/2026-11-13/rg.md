# rg - catalog audit 2026-11-13

## Versions
- pinned: none (github_release, dnf, apt, pacman and brew are all unpinned)
- verified: 2026-11-03
- installed: 15.2.0 (`rg --version`, per `make audit-catalog facts rg`)
- latest: 15.2.0 (GitHub releases/latest, https://api.github.com/repos/BurntSushi/ripgrep/releases/latest, published 2026-07-15)
- latest: 15.2.0-1.fc45 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/ripgrep)
- latest: 15.2.0-1 (Arch extra, https://archlinux.org/packages/search/json/?name=ripgrep)
- latest: 15.2.0 (Homebrew formula, https://formulae.brew.sh/api/formula/ripgrep.json)
- latest: unknown: the answer is an error body: 404 (https://sources.debian.org/api/src/ripgrep/); Debian's version is not established here, the apt install method is still judged on the vendor's install docs

## Changelog
- none between installed 15.2.0 and latest 15.2.0; the 15.2.0 release notes add an aarch64 musl binary, which the arm64 Linux github_release asset pattern already matches (https://github.com/BurntSushi/ripgrep/releases/tag/15.2.0)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/BurntSushi/ripgrep/master/README.md "Installation": Homebrew (`brew install ripgrep`), pacman, dnf, apt-get and static archives all still recommended; the registry's methods (installer/registry.toml:110-150) match each; the musl archive assets are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section) |
| update argv | n/a | reason: the entry declares no update argv and ripgrep ships no self-update command; facts report update none, so the installer re-runs the method |
| removal recipe and paths | ok | the github_release method extracts only the `rg` member (installer/registry.toml:116, `member = "rg"`, `strip = 1`), so removal is the receipt of that one binary (L2); the brew, dnf, apt and pacman methods remove through their manager (L1); the entry declares no config_paths (installer/registry.toml:91-100) and ripgrep creates no config file on install (README "Installation" lists only binaries) |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts rg`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts rg` reports postinstall none and post_install none; installer/registry.toml:91-109 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
