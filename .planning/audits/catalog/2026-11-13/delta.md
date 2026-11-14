# delta - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 0.19.2 (`delta --version`)
- latest: 0.20.1 (GitHub releases/latest, https://api.github.com/repos/dandavison/delta/releases/latest)
- latest: 0.20.1 (Homebrew formula API, https://formulae.brew.sh/api/formula/git-delta.json)

## Changelog
- no install, update, removal, config or MCP note between 0.19.2 and 0.20.1; 0.20.0 adds OSC-1717 diff-line metadata support (https://github.com/dandavison/delta/releases/tag/0.20.0), a runtime feature only

## Checks
| check | status | source |
|---|---|---|
| install method | ok | installer/registry.toml:327-341 declares the gnu linux tarball for every Linux arch, the arm64 apple-darwin tarball, and brew formula "git-delta"; v0.20.1 assets include x86_64 and aarch64 gnu tarballs, aarch64 darwin and no x86_64 darwin tarball, so Intel macOS correctly falls to brew (https://api.github.com/repos/dandavison/delta/releases/latest) |
| update argv | ok | `make audit-catalog ARGS="facts delta"` reports update: none, the installer re-runs the method |
| removal recipe and paths | ok | installer/registry.toml:327-341 github_release removal is the receipt of the paths the install computed (L2); the entry declares no config files, and the installer writes no delta config |
| tuning keys | n/a | reason: the entry declares no tuning keys and records no accepted customization |
| postinstall hook | ok | `make audit-catalog ARGS="facts delta"` reports postinstall: none and post_install: none; installer/registry.toml:318-341 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
