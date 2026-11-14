# broot - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned)
- verified: 2026-11-03
- installed: none (`broot` is not on this host, per the facts block)
- latest: v1.62.0 (GitHub releases/latest, https://api.github.com/repos/Canop/broot/releases/latest)
- latest: 1.62.0 (Homebrew formula, https://formulae.brew.sh/api/formula/broot.json)
- note: GitHub and the brew formula agree on 1.62.0

## Changelog
- no installed version to diff from; the v1.62.0 notes make an invalid flag, an unknown argument and contradictory flags in a verb argument into configuration errors, and fix verb quoting (https://api.github.com/repos/Canop/broot/releases/latest)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | upstream lists precompiled binaries and Homebrew as install routes (https://dystroy.org/broot/install/); the GitHub zip members and the Linux and macOS arm64 rows are recorded in verify-registry.md lines 76-78 |
| update argv | ok | the registry declares none and the installer re-runs the method; upstream says "To reinstall, just change the executable" (https://dystroy.org/broot/install/, Reinstall section) |
| removal recipe and paths | drift | the registry declares no config_paths (registry.toml:2407); upstream prefers the per-user config directory ~/.config/broot (https://github.com/Canop/broot/blob/main/src/conf/mod.rs#L60-L61, main branch, not the v1.62.0 tag) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action |
| postinstall hook | ok | none declared (registry.toml:2407); upstream names the br shell function as a manual step after install (https://dystroy.org/broot/install/), which is an open step 7 question, not a hook |

## Proposed changes
- declare config_paths = ["~/.config/broot"] with the default keep policy, and ask the user whether the br shell function is wanted as install tuning; risk: low; evidence: https://github.com/Canop/broot/blob/main/src/conf/mod.rs#L60-L61

<!-- catalog-audit:complete -->
