# miller - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 6.21.0 (`mlr --version` on the bin_dir path ~/.local/bin/mlr)
- latest: v6.22.0 (GitHub releases/latest, published 2026-09-25, https://api.github.com/repos/johnkerl/miller/releases/latest)
- latest: 6.22.0 (Homebrew formula JSON, https://formulae.brew.sh/api/formula/miller.json)

## Changelog
- 6.22.0 supports the XDG Base Directory spec for the location of .mlrrc, so `$XDG_CONFIG_HOME/miller/mlrrc` (default `~/.config/miller/mlrrc`) is read as well (https://github.com/johnkerl/miller/releases/tag/v6.22.0)
- 6.22.0 otherwise carries only features, fixes, CI and dependency updates; no install, update or removal note (https://github.com/johnkerl/miller/releases/tag/v6.22.0)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | upstream docs/src/installing-miller.md (https://github.com/johnkerl/miller/blob/main/docs/src/installing-miller.md) says the yum and apt-get packages "may have outdated versions", while the releases page and brew "tend to have current versions"; the registry's github_release tarball with checksum file per OS and arch (`installer/registry.toml:1267-1268`, `:1275-1276`) and brew match that; the verify record lists the tarballs as Passed in `.planning/audits/catalog/2026-11-13/verify-registry.md` |
| update argv | ok | the entry declares no argv and the installer re-runs the method (facts block); the upstream docs name `brew update` and `brew install miller` for macOS and no self-update command, https://github.com/johnkerl/miller/blob/main/docs/src/installing-miller.md |
| removal recipe and paths | drift | upstream docs/src/customization.md (https://github.com/johnkerl/miller/blob/main/docs/src/customization.md, "Where to put your .mlrrc") names `$HOME/.mlrrc`, `$XDG_CONFIG_HOME/miller/mlrrc` (default `$HOME/.config/miller/mlrrc`) and `./.mlrrc`, while the entry declares no `config_paths`; container check not run (the batch forbids containers), the drift is from the upstream text |
| tuning keys | n/a | reason: the entry declares no tuning keys; `.mlrrc` is user configuration read at run time, not install tuning |
| postinstall hook | ok | the entry declares no hook and the upstream install docs have no post-install step, https://github.com/johnkerl/miller/blob/main/docs/src/installing-miller.md |

## Proposed changes
- add the upstream user config paths `~/.mlrrc` and `~/.config/miller` to the miller entry's `config_paths` with the default `keep` policy; risk: low; evidence: https://github.com/johnkerl/miller/blob/main/docs/src/customization.md

<!-- catalog-audit:complete -->
