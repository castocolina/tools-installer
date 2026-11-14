# hexyl - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: none (not installed on this host)
- latest: v0.17.0 (GitHub releases/latest, published 2026-02-14, https://api.github.com/repos/sharkdp/hexyl/releases/latest)
- latest: 0.17.0 (Homebrew formula JSON, https://formulae.brew.sh/api/formula/hexyl.json)

## Changelog
- no release after v0.17.0 (2026-02-14), so nothing new since the verified date 2026-11-03 (https://github.com/sharkdp/hexyl/releases)

## Checks
| check | status | source |
|---|---|---|
| install method | unknown | reason: the upstream README (https://github.com/sharkdp/hexyl (README), Installation) names officially maintained apt, dnf and pacman packages for Linux; step 4 rule 1 prefers a distro package when current enough, and the packages' currency was not established in this batch; the registry's github_release tarball per OS and arch (`installer/registry.toml:1239-1240` and `:1246-1247`) is a step 4 rule 2 choice that the verify record lists as Passed in `.planning/audits/catalog/2026-11-13/verify-registry.md` |
| update argv | ok | the entry declares no argv and the installer re-runs the method (facts block); the README documents no self-update command, https://github.com/sharkdp/hexyl (README) |
| removal recipe and paths | ok | the github_release methods are removed by receipt (L2) and the brew method by its manager (L1), per tool-onboarding step 4b; the upstream README documents no uninstall command, https://github.com/sharkdp/hexyl (README) |
| tuning keys | n/a | reason: the entry declares no tuning keys; the v0.17.0 color settings are read from environment variables at run time, not written at install, https://github.com/sharkdp/hexyl/releases/tag/v0.17.0 |
| postinstall hook | ok | the entry declares no hook and the upstream README has no post-install step, https://github.com/sharkdp/hexyl (README) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
