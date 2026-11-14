# unzip - catalog audit 2026-11-13

## Versions
- pinned: none (the dnf, apt, pacman and brew methods are unpinned; each installs its distro or brew candidate)
- verified: 2026-11-13
- installed: not installed (facts; `unzip` is not on the audit host PATH)
- latest: 6.0 (Info-ZIP, https://infozip.sourceforge.net/UnZip.html, "UnZip 6.0, released 20 April 2009")
- latest: 6.0 (Homebrew formula, https://formulae.brew.sh/api/formula/unzip.json)
- latest: 6.0-71.fc45 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/unzip)
- latest: 6.0-31 (Debian, https://sources.debian.org/api/src/unzip/)
- latest: 6.0-23 (Arch extra, https://archlinux.org/packages/search/json/?name=unzip)

## Changelog
- no install, update, removal, config or MCP note: the Info-ZIP page states 6.0 is the latest release and that another major release may never come (https://infozip.sourceforge.net/UnZip.html, "Latest Release")

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the package name `unzip` is the candidate in each manager: Fedora rawhide, Debian, Arch extra and Homebrew (facts sources above); the installer's dnf, apt, pacman and brew methods match (installer/registry.toml:1892-1906); SDKMAN's installer needs unzip (https://get.sdkman.io, lines 209-215) |
| update argv | ok | the manager owns updates, so the entry declares no update argv (installer/registry.toml:1892-1906) |
| removal recipe and paths | ok | removal derives from the manager (L1); the package name the manager removes is the one the methods install (installer/registry.toml:1892-1906) |
| tuning keys | n/a | reason: the entry declares no tuning key and no post_install action (installer/registry.toml:1892-1906) |
| postinstall hook | ok | the entry declares no postinstall hook (installer/registry.toml:1892-1906) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
