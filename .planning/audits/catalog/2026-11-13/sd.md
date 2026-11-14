# sd - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-12
- installed: 1.0.0 (`sd --version`, see installer/registry.toml:263-264: v1.1.0 still prints 1.0.0, so the receipt decides)
- latest: v1.1.0 (GitHub releases/latest, https://api.github.com/repos/chmln/sd/releases/latest)
- latest: 1.1.0 (Homebrew formula API, https://formulae.brew.sh/api/formula/sd.json)
- note: the installed version comes from `sd --version`, which prints 1.0.0 for release 1.1.0; the Cargo.toml of v1.1.0 declares version "1.0.0" (https://raw.githubusercontent.com/chmln/sd/v1.1.0/Cargo.toml line 17)

## Changelog
- Pre-built Releases: adds aarch64-unknown-linux-gnu and aarch64-pc-windows-msvc release targets; the musl linux assets the registry uses (x86_64 and aarch64) are still published (https://github.com/chmln/sd/releases/tag/v1.1.0)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | installer/registry.toml:275-290 declares github_release per OS (linux musl tarball, apple-darwin tarball) plus brew formula "sd"; v1.1.0 assets exist for x86_64 and aarch64 musl and both darwin arches (https://api.github.com/repos/chmln/sd/releases/tags/v1.1.0); brew formula is 1.1.0 (https://formulae.brew.sh/api/formula/sd.json) |
| update argv | ok | `make audit-catalog ARGS="facts sd"` reports update: none, the installer re-runs the github_release and brew methods |
| removal recipe and paths | ok | installer/registry.toml:275-282 github_release removal is the receipt of the paths the install computed (L2); sd has no config file, no config section in https://github.com/chmln/sd/blob/v1.1.0/README.md |
| tuning keys | n/a | reason: the entry declares no tuning keys and records no accepted customization |
| postinstall hook | ok | `make audit-catalog ARGS="facts sd"` reports postinstall: none and post_install: none; installer/registry.toml:266-290 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
