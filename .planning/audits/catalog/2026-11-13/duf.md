# duf - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 0.9.1 (`rpm -qf /usr/bin/duf` on this host: duf-0.9.1-4.fc45.x86_64, a Fedora package owned by rpm; `duf --version` printed no version)
- latest: v0.9.1 (GitHub releases/latest, published 2025-09-08, https://api.github.com/repos/muesli/duf/releases/latest)
- latest: 0.9.1 (Homebrew formula JSON, https://formulae.brew.sh/api/formula/duf.json)

## Changelog
- 0.9.1 includes the version number in the release tarballs, which touches the asset names the github_release methods fetch (https://github.com/muesli/duf/releases/tag/v0.9.1); the entry's asset pattern still resolves in `.planning/audits/catalog/2026-11-13/verify-registry.md` (Passed)
- no release after v0.9.1 (2025-09-08), so nothing new since the verified date 2026-11-03

## Checks
| check | status | source |
|---|---|---|
| install method | drift | upstream README (https://github.com/muesli/duf (README), Installation) names `dnf install duf` for Fedora, and the host's Fedora package is already duf-0.9.1 (`rpm -qf /usr/bin/duf`), current with latest; step 4 rule 1 prefers that package manager, yet `installer/registry.toml:1209-1210` declares a github_release tarball for fedora and no dnf method |
| update argv | ok | the entry declares no argv and the installer re-runs the method (facts block); the README documents no self-update command, https://github.com/muesli/duf (README) |
| removal recipe and paths | unknown | reason: container check not run (no container run in this batch); `/usr/bin/duf` is owned by the rpm package duf-0.9.1-4.fc45, a foreign owner, and the step 4b rule (removal delegates to the owning manager) is not established without running the installer; upstream documents no uninstall command, https://github.com/muesli/duf (README) |
| tuning keys | n/a | reason: the entry declares no tuning keys and the upstream README has no configuration section |
| postinstall hook | unknown | reason: the upstream README Troubleshooting section says oh-my-zsh already defines an alias `duf` that must be removed with `unalias duf` (https://github.com/muesli/duf (README), Troubleshooting); the entry declares no hook, and whether that is install tuning is a question for the user under tool-onboarding step 7 |

## Proposed changes
- add a dnf method for fedora (or drop the github_release fedora method) if the install-method drift is accepted, so the distro package owns duf there; risk: medium; evidence: https://github.com/muesli/duf (README) and `rpm -qf /usr/bin/duf` output above

<!-- catalog-audit:complete -->
