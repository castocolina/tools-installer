# gitleaks - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 8.30.1 (gitleaks --version, facts block)
- latest: v8.30.1 (GitHub releases/latest, https://api.github.com/repos/gitleaks/gitleaks/releases/latest, published 2026-03-21)
- latest: 8.30.1 (brew formula, https://formulae.brew.sh/api/formula/gitleaks.json)

## Changelog
- README: "Gitleaks is feature complete" and "Future releases will be security patches only" (https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md line 12; touches update cadence)
- no release note between 8.30.1 and 8.30.1 touches install, update, removal, config or MCP (https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1 lists commits only)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | v8.30.1 carries the assets the entry names, gitleaks_8.30.1_linux_x64.tar.gz, gitleaks_8.30.1_linux_arm64.tar.gz, gitleaks_8.30.1_darwin_x64.tar.gz and gitleaks_8.30.1_darwin_arm64.tar.gz (https://api.github.com/repos/gitleaks/gitleaks/releases/latest); the download and checksum passed verify-registry (.planning/audits/catalog/2026-11-13/verify-registry.md:138-141); the README lists brew and release binaries (https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md line 63) |
| update argv | ok | the entry declares no update, so re-running the release method is the upgrade (installer/registry.toml:2356-2375); the README names no self-update (https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md lines 63-69 list brew and binary releases) |
| removal recipe and paths | ok | a github_release install is removed by the receipt of the paths the install computed (tool-onboarding step 4b, .claude/skills/tool-onboarding/SKILL.md), and the entry declares no paths of its own (installer/registry.toml:2356-2375); the brew method removes through brew |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:2347-2355) |
| postinstall hook | ok | no Tool.postinstall is declared (installer/registry.toml:2347-2375), which is the None branch of "Postinstall-per-harness classification" at .claude/architecture.md:331 |

## Proposed changes
- none

<!-- catalog-audit:complete -->
