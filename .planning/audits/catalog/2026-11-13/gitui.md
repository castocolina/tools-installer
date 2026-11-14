# gitui - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew)
- verified: 2026-11-03
- installed: 0.28.1 (`gitui --version`)
- latest: v0.28.1 (GitHub releases/latest, https://api.github.com/repos/gitui-org/gitui/releases/latest, read with `gh api`, published 2026-03-24)
- latest: 0.28.1 (Homebrew formula, https://formulae.brew.sh/api/formula/gitui.json)

## Changelog
- no install, update, removal, config or MCP note between v0.28.1 and v0.28.1 (installed equals latest)
- for context, the v0.28.1 notes (https://github.com/gitui-org/gitui/releases/tag/v0.28.1) raise the Rust MSRV to 1.88, which matters only to `cargo install gitui --locked` from the README (https://github.com/gitui-org/gitui#installation), not to any registry method

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the upstream README install list recommends `sudo pacman -S gitui` for Arch and `sudo dnf install gitui` for Fedora (https://github.com/gitui-org/gitui#installation), while `installer/registry.toml:979` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the Linux and macOS asset rows match the downloads that `verify-registry.md:142-145` passed, and the brew row matches the README's Homebrew line |
| update argv | ok | the entry declares no update argv; brew updates through the formula (`formula "gitui"` at 0.28.1, https://formulae.brew.sh/api/formula/gitui.json); the release-asset path re-runs the method (facts: `update: none`) |
| removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:968-1000`), but the upstream KEY_CONFIG and THEMES pages place user-authored `key_bindings.ron` and `theme.ron` in `~/.config/gitui` on macOS and Linux (https://raw.githubusercontent.com/gitui-org/gitui/master/KEY_CONFIG.md, https://raw.githubusercontent.com/gitui-org/gitui/master/THEMES.md), and the README's diagnostics section writes `gitui.log` under `~/Library/Caches/gitui` (macOS) or `~/.cache/gitui` (Linux) when run with `-l` (https://github.com/gitui-org/gitui#diagnostics); the default config policy is therefore unstated |
| tuning keys | n/a | reason: the entry declares no tuning keys; gitui's theme and key bindings are user-authored `.ron` files (https://raw.githubusercontent.com/gitui-org/gitui/master/KEY_CONFIG.md), and the installer writes none |
| postinstall hook | ok | `installer/registry.toml:968` gitui block has no `postinstall`, `post_install`, `paths`, `remove` or `update` key, so the decision tree lands on none |

## Proposed changes
- declare `config_paths = ["~/.config/gitui"]` and state the default config policy `keep` or `ask`, so a delete choice covers the user's `.ron` files; risk: medium; evidence: https://raw.githubusercontent.com/gitui-org/gitui/master/THEMES.md
- move the arch and fedora methods to `pacman -S gitui` and `sudo dnf install gitui` once their current version is checked; risk: low; evidence: https://github.com/gitui-org/gitui#installation

<!-- catalog-audit:complete -->
