# bat - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 0.26.1 (`bat --version`)
- latest: v0.26.1 (GitHub releases/latest, https://api.github.com/repos/sharkdp/bat/releases/latest)
- latest: 0.26.1 (Homebrew formula API, https://formulae.brew.sh/api/formula/bat.json)

## Changelog
- no install, update, removal, config or MCP note between 0.26.1 and 0.26.1

## Checks
| check | status | source |
|---|---|---|
| install method | ok | installer/registry.toml:245-262 declares github_release per OS (linux musl tarball, apple-darwin tarball) plus brew formula "bat"; vendor README lists `brew install bat` (https://github.com/sharkdp/bat/blob/v0.26.1/README.md) and v0.26.1 ships x86_64 and aarch64 musl and darwin tarballs (https://api.github.com/repos/sharkdp/bat/releases/tags/v0.26.1); arm64 maps to aarch64 at installer/assets.py:20-21 |
| update argv | ok | `make audit-catalog ARGS="facts bat"` reports update: none, the installer re-runs the github_release and brew methods |
| removal recipe and paths | drift | installer/registry.toml:236-244 declares no config_paths for bat, while the vendor README documents the config dir via `bat --config-dir` (https://github.com/sharkdp/bat/blob/v0.26.1/README.md, line 565); removal policy for user config cannot be applied |
| tuning keys | n/a | reason: the entry declares no tuning keys and records no accepted customization |
| postinstall hook | ok | installer/registry.toml:236-262 declares neither postinstall nor post_install |

## Proposed changes
- add config_paths for bat's config dir (confirm the exact path with `bat --config-dir` in a container) to the bat [[tool]] entry; risk: low; evidence: https://github.com/sharkdp/bat/blob/v0.26.1/README.md

<!-- catalog-audit:complete -->
