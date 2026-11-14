# tealdeer - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew, installer/registry.toml:1315-1346)
- verified: 2026-11-03 (installer/registry.toml:1322)
- installed: none (not installed on this host, per `make audit-catalog ARGS="facts tealdeer"`)
- latest: v1.9.1 (GitHub releases/latest, published 2026-10-24, https://api.github.com/repos/tealdeer-rs/tealdeer/releases/latest)
- latest: 1.9.1 (Homebrew formula, https://formulae.brew.sh/api/formula/tealdeer.json)

## Changelog
- v1.9.0 (2026-08-24) switches the default config and cache directories on macOS to XDG; a config or cache already present at the old locations is still used (https://github.com/tealdeer-rs/tealdeer/blob/main/CHANGELOG.md)
- v1.9.0 supports tilde expansion in config paths, adds `--override-config`, and errors on unknown config keys (https://github.com/tealdeer-rs/tealdeer/blob/main/CHANGELOG.md)
- v1.9.0 adds a suggestion to try another TLS backend when `tldr --update` fails, which affects the postinstall cache hook (https://github.com/tealdeer-rs/tealdeer/blob/main/CHANGELOG.md)
- v1.9.1 (2026-10-24) stops panicking on a non-UTF-8 config path (https://github.com/tealdeer-rs/tealdeer/blob/main/CHANGELOG.md)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the v1.9.1 release has linux x86_64 and aarch64 musl binaries and macOS x86_64 and aarch64 binaries, each with a .sha256 sidecar (https://api.github.com/repos/tealdeer-rs/tealdeer/releases/latest), which pass in .planning/audits/catalog/2026-11-13/verify-registry.md:222-225; the brew formula serves 1.9.1 (https://formulae.brew.sh/api/formula/tealdeer.json) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:1315-1346, facts update: none); `tldr --update` refreshes the page cache, not the binary (https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/cli.rs?ref=v1.9.1 lines 68-69) and is already the postinstall hook (installer/postinstall.py:396) |
| removal recipe and paths | drift | config_paths lists only cache directories (installer/registry.toml:1327); upstream resolves the config dir to the XDG path on Linux and macOS (https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/config.rs?ref=v1.9.1 lines 874-881, with the XDG preference at lines 60-72) and the config file is config.toml (same file line 25), so ~/.config/tealdeer is missing from the entry |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:1315-1346, facts tuning: none); the installer writes no tealdeer config keys |
| postinstall hook | ok | the hook `tealdeer-cache` runs `tldr --update`, a cache fill that only warns on failure, and is registered in the closed table (installer/postinstall.py:390-399 and installer/postinstall.py:431); upstream still defines `--update` (https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/cli.rs?ref=v1.9.1 lines 68-69) |

## Proposed changes
- add ~/.config/tealdeer to the tealdeer entry's config_paths so the config file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/tealdeer-rs/tealdeer/contents/src/config.rs?ref=v1.9.1 lines 874-881

<!-- catalog-audit:complete -->
