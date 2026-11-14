# gum - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew)
- verified: 2026-11-03
- installed: v2.0.2 (`gum --version`)
- latest: v2.0.2 (GitHub releases/latest, https://api.github.com/repos/charmbracelet/gum/releases/latest, read with `gh api`)
- latest: 2.0.2 (Homebrew formula, https://formulae.brew.sh/api/formula/gum.json)

## Changelog
- no install, update, removal, config or MCP note between v2.0.2 and v2.0.2 (release notes, https://github.com/charmbracelet/gum/releases/tag/v2.0.2 list only a raw ANSI fix and the version bump)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the upstream README Installation section recommends `pacman -S gum` (Arch) and `dnf install gum` (Fedora) before any release asset, https://github.com/charmbracelet/gum#installation, while `installer/registry.toml:859` installs the release asset on arch and fedora; package currency on those distros is unverified (no pacman or dnf query run); the macOS and Linux brew and checksummed asset rows match the vendor's brew line and the downloads that `verify-registry.md:154-157` passed |
| update argv | ok | the entry declares no update argv and the brew path updates through the formula (`formula "gum"` at 2.0.2, https://formulae.brew.sh/api/formula/gum.json); the release-asset path re-runs the method (facts: `update: none`) |
| removal recipe and paths | ok | `installer/registry.toml:859` and `:876` declare no paths and no remove argv; `.claude/skills/tool-onboarding/SKILL.md:106-107` assigns brew to L1 and github_release to L2 receipt removal; the upstream README documents no config file, https://raw.githubusercontent.com/charmbracelet/gum/main/README.md |
| tuning keys | n/a | reason: the entry declares no tuning keys, and gum takes its customization from per-run flags and `GUM_*` environment variables (https://raw.githubusercontent.com/charmbracelet/gum/main/README.md, "Customize with ENVIRONMENT_VARIABLES") rather than a config file |
| postinstall hook | ok | `installer/registry.toml:850` gum block has no `postinstall` or `post_install` key; the upstream README describes no host config to write, so the decision tree lands on none |

## Proposed changes
- move the arch and fedora methods to the vendor-listed `pacman` and `dnf` packages once their current version is checked; risk: low; evidence: https://github.com/charmbracelet/gum#installation

<!-- catalog-audit:complete -->
