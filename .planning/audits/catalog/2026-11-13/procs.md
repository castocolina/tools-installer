# procs - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned, the github_release and brew methods take the current release)
- verified: 2026-11-03
- installed: 0.14.12 (`procs --version`)
- latest: v0.14.12 (GitHub releases/latest, https://api.github.com/repos/dalance/procs/releases/latest, published 2026-06-25)
- latest: 0.14.12 (Homebrew formula stable, https://formulae.brew.sh/api/formula/procs.json)

## Changelog
- no install, update, removal, config or MCP note between 0.14.12 and 0.14.12

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the github_release assets for linux and mac (`installer/registry.toml:2099-2100`, `2106-2107`) are published for v0.14.12 (https://api.github.com/repos/dalance/procs/releases/latest) and clean in `.planning/audits/catalog/2026-11-13/verify-registry.md:195-198`; the upstream README lists Homebrew as a route (https://raw.githubusercontent.com/dalance/procs/master/README.md, "homebrew") |
| update argv | unknown | reason: container check not run (no container in this batch); the entry declares no update argv and the installer re-runs the method |
| removal recipe and paths | unknown | reason: the upstream README documents no uninstall or upgrade command (https://raw.githubusercontent.com/dalance/procs/master/README.md); the github_release leg relies on the installer's receipt (L2) and the brew leg on the manager (L1), neither exercised (container check not run) |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
