# jq - catalog audit 2026-11-13

## Versions
- pinned: none (dnf, apt, pacman and brew are all unpinned)
- verified: 2026-10-13
- installed: 1.8.2 (`jq --version`, per `make audit-catalog facts jq`)
- latest: 1.8.2 (GitHub releases/latest, https://api.github.com/repos/jqlang/jq/releases/latest, published 2026-06-20)
- latest: 1.8.2-5.fc45 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/jq)
- latest: 1.8.2-1 (Debian, https://sources.debian.org/api/src/jq/)
- latest: 1.8.2-1 (Arch extra, https://archlinux.org/packages/search/json/?name=jq)
- latest: 1.8.2 (Homebrew formula, https://formulae.brew.sh/api/formula/jq.json)

## Changelog
- none between installed 1.8.2 and latest 1.8.2; the 1.8.2 notes are security and bug fixes plus new Windows arm64 and Docker arm/v7 builds, none touching install, update, removal, config or MCP (https://github.com/jqlang/jq/releases/tag/jq-1.8.2)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://jqlang.org/download/: "Linux jq is in the official Debian and Ubuntu repositories. Install using sudo apt-get install jq", the Fedora `sudo dnf install jq`, the Arch `sudo pacman -S jq`, and "Use Homebrew to install jq with brew install jq"; the registry declares exactly those four managers (installer/registry.toml:62-90) |
| update argv | n/a | reason: the entry declares no update argv; every method is package-manager owned, so the manager's own upgrade applies (facts: update none) |
| removal recipe and paths | ok | each method removes through its manager (L1): dnf, apt, pacman and brew; the entry declares no paths and no config_paths (installer/registry.toml:62-70), and the package name in each method is the one the vendor names on https://jqlang.org/download/ |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts jq`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts jq` reports postinstall none and post_install none; installer/registry.toml:62-90 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
