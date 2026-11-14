# glow - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew)
- verified: 2026-11-03
- installed: v3.0.0 (`glow --version`)
- latest: v3.0.0 (GitHub releases/latest, https://api.github.com/repos/charmbracelet/glow/releases/latest, read with `gh api`)
- latest: 3.0.0 (Homebrew formula, https://formulae.brew.sh/api/formula/glow.json)

## Changelog
- v3.0.0 moves the Go module to `charm.land/glow/v3`, so `go install` now needs that path; the README now shows `go install charm.land/glow/v3@latest` (https://github.com/charmbracelet/glow/releases/tag/v3.0.0, https://github.com/charmbracelet/glow#installation). The registry does not use `go install`, so no registry row changes.
- no other install, update, removal, config or MCP note between v3.0.0 and v3.0.0

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the upstream README Installation section lists `pacman -S glow` for Arch, https://github.com/charmbracelet/glow#installation, while `installer/registry.toml:892` installs the release asset on arch; the Fedora and Debian rows use the Charm yum or apt repo in the README, which need a third-party repo and root, so the release asset stays; arch package currency is unverified (no pacman query run); the macOS and Linux asset and brew rows match the downloads `verify-registry.md:146-149` passed |
| update argv | ok | the entry declares no update argv; brew updates through the formula (`formula "glow"` at 3.0.0, https://formulae.brew.sh/api/formula/glow.json); the release-asset path re-runs the method (facts: `update: none`) |
| removal recipe and paths | drift | `installer/registry.toml:890` declares `config_paths = ["~/.config/glow"]` for every OS, but glow resolves its default config directory through go-app-paths (`glow` main.go:436-473, https://raw.githubusercontent.com/charmbracelet/glow/main/main.go), which on darwin uses `/Library/Preferences` under the home directory (go-app-paths v0.2.2 `paths_darwin.go:12,75`, https://raw.githubusercontent.com/muesli/go-app-paths/v0.2.2/paths_darwin.go); the macOS path is therefore `~/Library/Preferences/...`, and the app-name join beneath it is unverified; on Linux `~/.config/glow` matches `main.go:444-445` (XDG_CONFIG_HOME/glow) |
| tuning keys | n/a | reason: the entry declares no tuning keys; glow's `glow.yml` is user-edited (https://raw.githubusercontent.com/charmbracelet/glow/main/README.md, "The Config File") and the installer writes none |
| postinstall hook | ok | `installer/registry.toml:880` glow block has no `postinstall`, `post_install`, `remove` or `update` key, so the decision tree lands on none |

## Proposed changes
- make `config_paths` per OS: `~/.config/glow` on Linux and the macOS directory on darwin once the app-name join is checked; risk: medium; evidence: https://raw.githubusercontent.com/charmbracelet/glow/main/main.go
- move the arch method to `pacman -S glow` once its current version is checked; risk: low; evidence: https://github.com/charmbracelet/glow#installation

<!-- catalog-audit:complete -->
