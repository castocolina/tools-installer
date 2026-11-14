# dive - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 0.13.1 (`dive --version`)
- latest: v0.13.1 (GitHub releases/latest, published 2025-03-29, https://api.github.com/repos/wagoodman/dive/releases/latest)
- latest: 0.13.1 (Homebrew formula JSON, https://formulae.brew.sh/api/formula/dive.json)

## Changelog
- no install, update, removal, config or MCP note between 0.13.1 and 0.13.1 (installed equals latest; release notes https://github.com/wagoodman/dive/releases/tag/v0.13.1 read)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | upstream README (https://github.com/wagoodman/dive/blob/v0.13.1/README.md, Installation) lists `brew install dive` (Homebrew) plus per-distro deb, rpm, pacman and snap; the registry's brew method and the github_release tarball with checksum per OS/arch both match step 4; the verify record (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed) covers the downloadable rows; the Arch pacman package currency is unverified |
| update argv | ok | the entry declares no argv and the installer re-runs the method (facts block); the README documents no self-update command, https://github.com/wagoodman/dive/blob/v0.13.1/README.md |
| removal recipe and paths | drift | the upstream README (Configuration, https://github.com/wagoodman/dive/blob/v0.13.1/README.md) says dive reads `$XDG_CONFIG_HOME/dive/*.yaml`, `$XDG_CONFIG_DIRS/dive/*.yaml`, `~/.config/dive/*.yaml` and `~/.dive.yaml`, while the entry declares no `config_paths`; container check not run (the batch forbids containers), the drift is from the upstream text |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | ok | the entry declares no hook and the upstream README has no post-install step ("No configuration is necessary", UI Configuration section), https://github.com/wagoodman/dive/blob/v0.13.1/README.md |

## Proposed changes
- add the upstream user config paths `~/.config/dive` and `~/.dive.yaml` to the dive entry's `config_paths` with the default `keep` policy; risk: low; evidence: https://github.com/wagoodman/dive/blob/v0.13.1/README.md (Configuration)

<!-- catalog-audit:complete -->
