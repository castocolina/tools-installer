# gron - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew, installer/registry.toml:1405-1430)
- verified: 2026-11-03 (installer/registry.toml:1412)
- installed: unknown: no version in the `gron --version` output (facts block)
- latest: v0.7.1 (GitHub releases/latest, published 2022-04-13, https://api.github.com/repos/tomnomnom/gron/releases/latest)
- latest: 0.7.1 (Homebrew formula, https://formulae.brew.sh/api/formula/gron.json)
- note: GitHub and Homebrew agree on 0.7.1; no GitHub release has been published since 2022-04-13 (https://api.github.com/repos/tomnomnom/gron/releases?per_page=4)

## Changelog
- v0.7.1 (2022-04-13) adds the `-v`/`--values` option; no note touches install, update, removal, config or MCP (https://api.github.com/repos/tomnomnom/gron/releases/latest)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the github_release assets carry no checksum file and no GitHub digest (0 of 11 assets, https://api.github.com/repos/tomnomnom/gron/releases/latest), and verify-registry.md:8-9 lists them as unverified at install; the brew formula serves the same 0.7.1 with a sha256 (https://formulae.brew.sh/api/formula/gron.json) and is declared for all OS and arch (installer/registry.toml:1428-1430); the installer's step 4 ranks a package manager ahead of an unchecksummed asset (.claude/skills/tool-onboarding/SKILL.md:77) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:1405-1430, facts update: none); the README documents no upgrade command (https://api.github.com/repos/tomnomnom/gron/readme, Installation section) |
| removal recipe and paths | ok | gron writes no config or state: its only file access is opening the input file (https://api.github.com/repos/tomnomnom/gron/contents/main.go?ref=v0.7.1 line 146), so the github_release removal is the receipt-proven binary (installer/uninstall.py:428-434) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:1405-1430, facts tuning: none); gron has no settings file to tune |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:1405-1430, facts postinstall: none) |

## Proposed changes
- move the brew method ahead of the two github_release methods for gron or pin sha256 for the release assets so the first method is checksum-verified; risk: medium; evidence: https://formulae.brew.sh/api/formula/gron.json

<!-- catalog-audit:complete -->
