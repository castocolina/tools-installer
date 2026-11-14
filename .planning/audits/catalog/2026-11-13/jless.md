# jless - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned, the github_release and brew methods take the current release)
- verified: 2026-11-03
- installed: 0.9.0 (`jless --version`)
- latest: v0.9.0 (GitHub releases/latest, https://api.github.com/repos/PaulJuliusMartinez/jless/releases/latest, published 2023-07-17)
- latest: 0.9.0 (Homebrew formula stable, https://formulae.brew.sh/api/formula/jless.json)
- note: GitHub's latest is the newest non-prerelease tag (v0.8.0 and v0.7.2 are older); no newer major exists

## Changelog
- no install, update, removal, config or MCP note between 0.9.0 and 0.9.0

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the Linux amd64 github_release asset and the macOS github_release asset exist for v0.9.0 (https://api.github.com/repos/PaulJuliusMartinez/jless/releases/latest); the upstream README lists Homebrew for macOS and Linux (https://raw.githubusercontent.com/PaulJuliusMartinez/jless/master/README.md:29-31); the registry's `# No aarch64-linux asset upstream` note (`installer/registry.toml:2156`) matches the asset list, and arm64 Linux falls to brew |
| update argv | unknown | reason: container check not run (no container in this batch); the entry declares no update argv and the installer re-runs the method |
| removal recipe and paths | unknown | reason: upstream README documents no uninstall command (https://raw.githubusercontent.com/PaulJuliusMartinez/jless/master/README.md); the github_release leg relies on the installer's receipt (L2) and the brew leg on the manager (L1), neither exercised (container check not run) |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
