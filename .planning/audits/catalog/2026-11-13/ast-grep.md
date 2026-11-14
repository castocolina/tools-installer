# ast-grep - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned, the github_release and brew methods take the current release)
- verified: 2026-11-03
- installed: 0.51.1 (`ast-grep --version`)
- latest: 0.51.2 (GitHub releases/latest, https://api.github.com/repos/ast-grep/ast-grep/releases/latest)
- latest: 0.51.2 (Homebrew formula stable, https://formulae.brew.sh/api/formula/ast-grep.json)

## Changelog
- 0.51.2 distributes musl Linux binaries in addition to the gnu ones, so the gnu asset the registry downloads is still published (release notes, https://github.com/ast-grep/ast-grep/pull/3067; asset list at https://api.github.com/repos/ast-grep/ast-grep/releases/latest)
- no other 0.51.2 note touches install, update, removal, config or MCP

## Checks
| check | status | source |
|---|---|---|
| install method | ok | github_release gnu assets for debian, arch and fedora (`installer/registry.toml:2131-2132`) and brew formula `ast-grep` on all platforms (`installer/registry.toml:2143-2144`); the 0.51.2 assets are clean in `.planning/audits/catalog/2026-11-13/verify-registry.md:64-67`; brew formula stable is 0.51.2 (https://formulae.brew.sh/api/formula/ast-grep.json) |
| update argv | unknown | reason: container check not run (no container in this batch); the entry declares no update argv and the installer re-runs the method |
| removal recipe and paths | ok | github_release removal is the receipt of the installed paths (L2) and brew removal is the manager's own remove (L1), per `installer/registry.toml:2128-2144`; the entry declares no paths |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
