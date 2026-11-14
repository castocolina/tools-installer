# hyperfine - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: not installed (facts: `installed: not installed`)
- latest: v2.0.0 (GitHub releases/latest, https://api.github.com/repos/sharkdp/hyperfine/releases/latest, published 2026-10-07)
- latest: 2.0.0 (Homebrew formula, https://formulae.brew.sh/api/formula/hyperfine.json)
- note: 2.0.0 is a major release; the GitHub latest is the newest major (the 2.0.0 alphas are prereleases), so no split

## Changelog
- nothing is installed, so the range is the 2.0.0 release alone (https://github.com/sharkdp/hyperfine/releases/tag/v2.0.0)
- none of the 2.0.0 notes touch install, update, removal, config or MCP of the installer's method; the breaking changes (direct command execution without a shell, the `--export-json` schema, and the removed `--time-unit`, `--sort` and `--reference`) change how the binary is used, not how it is installed

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://raw.githubusercontent.com/sharkdp/hyperfine/master/README.md "Installation" still lists Homebrew (`brew install hyperfine`), the distro repositories, Cargo and the release `.deb`; the registry's github_release and brew methods match (installer/registry.toml:794-819); the musl and apple-darwin archives are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section, lines 166-169) |
| update argv | ok | the entry declares no update argv, so the installer re-runs the method (`make audit-catalog facts hyperfine`); the vendor's upgrade route is the same archive or `brew upgrade hyperfine`, and the 2.0.0 archive replaces any 1.x binary |
| removal recipe and paths | ok | the github_release method extracts only the `hyperfine` member (installer/registry.toml:808 and 815, `member = "hyperfine"`), so removal is the receipt of that binary; brew removes through brew; the entry declares no paths (installer/registry.toml:794-819) and hyperfine writes no file on install (README "Installation" lists only binaries) |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts hyperfine`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts hyperfine` reports postinstall none and post_install none; installer/registry.toml:794-819 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
