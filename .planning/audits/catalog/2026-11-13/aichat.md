# aichat - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew methods are unpinned)
- verified: 2026-11-03
- installed: not installed on this host (`facts aichat`)
- latest: v0.30.0 (GitHub releases/latest, https://api.github.com/repos/sigoden/aichat/releases/latest)
- latest: 0.30.0 (Homebrew formula API, https://formulae.brew.sh/api/formula/aichat.json)

## Changelog
- no install, update, removal, config or MCP note between 0.29.0 and 0.30.0 (release notes, https://github.com/sigoden/aichat/releases/tag/v0.30.0)
- 0.29.0 replaces the config key `prelude` with `cmd_prelude`; the entry writes no aichat config, so it is not affected (release notes, https://github.com/sigoden/aichat/releases/tag/v0.29.0)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | `installer/registry.toml:1433` entry: brew plus musl and apple-darwin release tarballs that match the v0.30.0 asset names for x86_64 and aarch64, https://api.github.com/repos/sigoden/aichat/releases/latest; upstream README also lists brew and pacman, https://raw.githubusercontent.com/sigoden/aichat/main/README.md; verify-registry.md lists the four tarball URLs under Passed |
| update argv | ok | `installer/registry.toml:1433` declares no update argv, so the installer re-runs the method; the release tarballs are the vendor's documented binary route, https://github.com/sigoden/aichat#pre-built-binaries |
| removal recipe and paths | ok | github_release removal is the install receipt (L2) and brew removal derives from the manager (L1); the upstream README documents no uninstall step, https://raw.githubusercontent.com/sigoden/aichat/main/README.md |
| tuning keys | n/a | reason: the entry declares no tuning keys or post_install actions |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and aichat has no MCP config surface in the entry |

## Proposed changes
- none

<!-- catalog-audit:complete -->
