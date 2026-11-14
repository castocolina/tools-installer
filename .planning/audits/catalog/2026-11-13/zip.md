# zip - catalog audit 2026-11-13

## Versions
- pinned: none (the dnf, apt, pacman and brew methods are unpinned; each installs its distro or brew candidate)
- verified: 2026-11-13
- installed: 1990-2008 (facts parsed this from `zip --version`, which printed a copyright line; the real version is not established by the probe)
- latest: 3.0 (Info-ZIP, https://infozip.sourceforge.net/Zip.html, "Zip 3.0, released 7 July 2008")
- latest: 3.0 (Homebrew formula, https://formulae.brew.sh/api/formula/zip.json)
- latest: 3.0-46.fc45 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/zip)
- latest: 3.0-16 (Debian, https://sources.debian.org/api/src/zip/)
- latest: 3.0-14 (Arch extra, https://archlinux.org/packages/search/json/?name=zip)
- note: the installed value comes from a probe that matched the copyright years in `zip --version`, not a version; treat it as unknown

## Changelog
- no install, update, removal, config or MCP note: the Info-ZIP page states 3.0 is the latest release (https://infozip.sourceforge.net/Zip.html, "Latest Release")

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the package name `zip` is the candidate in each manager (Fedora rawhide, Debian, Arch extra and Homebrew, facts sources above); the installer's dnf, apt, pacman and brew methods match (installer/registry.toml:1930-1939); SDKMAN's installer needs zip (https://get.sdkman.io, lines 221-227) |
| update argv | ok | the manager owns updates, so the entry declares no update argv (installer/registry.toml:1930-1939) |
| removal recipe and paths | ok | removal derives from the manager (L1); the package name the manager removes is the one the methods install (installer/registry.toml:1930-1939) |
| tuning keys | n/a | reason: the entry declares no tuning key and no post_install action (installer/registry.toml:1918-1939) |
| postinstall hook | ok | the entry declares no postinstall hook (installer/registry.toml:1918-1939) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
