# shfmt - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew, installer/registry.toml:1286-1312)
- verified: 2026-11-03 (installer/registry.toml:1294)
- installed: none (not installed on this host, per `make audit-catalog ARGS="facts shfmt"`)
- latest: v3.14.1 (GitHub releases/latest, published 2026-09-06, https://api.github.com/repos/mvdan/sh/releases/latest)
- latest: 3.14.1 (Homebrew formula, https://formulae.brew.sh/api/formula/shfmt.json)

## Changelog
- no install, update, removal, config or MCP note in v3.14.1 (https://api.github.com/repos/mvdan/sh/releases/latest); nothing is installed, so no installed-to-latest range applies, and no release was published after the verified date 2026-11-03 (https://api.github.com/repos/mvdan/sh/releases?per_page=4)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the v3.14.1 release has raw binaries for linux and darwin on amd64 and arm64 (https://api.github.com/repos/mvdan/sh/releases/latest), which pass in .planning/audits/catalog/2026-11-13/verify-registry.md:211-214; the brew formula serves 3.14.1 (https://formulae.brew.sh/api/formula/shfmt.json); the README also lists Debian, Fedora and Arch packages (https://api.github.com/repos/mvdan/sh/readme), whose current versions are unverified and not compared |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:1286-1312, facts update: none); the README documents no upgrade or update command (https://api.github.com/repos/mvdan/sh/readme) |
| removal recipe and paths | ok | a github_release is removed through its receipt-proven artifact and brew through its manager (installer/uninstall.py:428-434); upstream cmd/shfmt/main.go reads no user config or state directory, its only file access is opening the file being formatted (https://api.github.com/repos/mvdan/sh/contents/cmd/shfmt/main.go) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:1286-1312, facts tuning: none); shfmt's only settings file is the project-local .editorconfig read at format time (https://api.github.com/repos/mvdan/sh/contents/cmd/shfmt/shfmt.1.scd), which the installer never writes |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:1286-1312, facts postinstall: none) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
