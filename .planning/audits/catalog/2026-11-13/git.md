# git - catalog audit 2026-11-13

## Versions
- pinned: unpinned (dnf, apt, pacman, brew)
- verified: 2026-10-13
- installed: 2.56.0 (`git --version`)
- latest: v2.56.1 (GitHub tags, https://api.github.com/repos/git/git/tags)
- latest: 2.56.1 (Homebrew formula API, https://formulae.brew.sh/api/formula/git.json)
- latest: 2.56.1-1 (Arch extra, https://archlinux.org/packages/search/json/?name=git)
- latest: 2.56.1-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/git)
- latest: 1:2.55.0+next.20260731-1 (Debian, https://sources.debian.org/api/src/git/)
- note: the Debian source package trails upstream; the distro packages are judged by their own manager, not against the upstream tag

## Changelog
- v2.56.1 merges the security fixes of v2.50.2 to v2.55.1 (CVE-2026-111760, CVE-2026-113408, CVE-2026-114466, CVE-2026-114467, CVE-2026-114469, CVE-2026-105437); no install, update, removal, config or MCP note (https://github.com/git/git/blob/v2.56.1/Documentation/RelNotes/2.56.1.adoc)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | installer/registry.toml:304-315 declares dnf, apt, pacman and brew packages for every OS and arch; the owner probe `rpm-ostree` is declared at installer/registry.toml:303 for atomic Fedora hosts |
| update argv | ok | `make audit-catalog ARGS="facts git"` reports update: none, the installer re-runs the package-manager method |
| removal recipe and paths | ok | installer/registry.toml:304-315 removal derives from each manager (L1); the package names git in dnf, apt, pacman and brew are the ones installed |
| tuning keys | n/a | reason: the entry declares no tuning keys and records no accepted customization |
| postinstall hook | ok | `make audit-catalog ARGS="facts git"` reports postinstall: none and post_install: none; installer/registry.toml:293-303 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
