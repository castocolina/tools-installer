# difftastic - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew)
- verified: 2026-11-03
- installed: 0.69.0 (`difft --version`)
- latest: 0.72.0 (GitHub releases/latest, https://api.github.com/repos/Wilfred/difftastic/releases/latest, read with `gh api`, published 2026-10-29)
- latest: 0.72.0 (Homebrew formula, https://formulae.brew.sh/api/formula/difftastic.json)
- note: no major split; GitHub's latest and the brew formula agree on 0.72.0

## Changelog
- 0.71 (released 2026-09-18): "Prebuilt binaries attached to releases now include the version in the filename" (https://github.com/Wilfred/difftastic/blob/master/CHANGELOG.md, section 0.71); the registry's `{ver}` asset pattern at `installer/registry.toml:949` matches that naming, and `verify-registry.md:96-99` lists the 0.72.0 names as passed
- 0.70 (released 2026-08-07): "prebuilt binaries on GitHub did not respect Cargo.lock" was fixed (https://github.com/Wilfred/difftastic/blob/master/CHANGELOG.md, section 0.70); this touches how the release asset is built, not its name or the install path
- 0.72 (released 2026-10-29): no install, update, removal, config or MCP note (https://github.com/Wilfred/difftastic/releases/tag/0.72.0)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the upstream manual lists `sudo pacman -S difftastic` for Arch and `sudo dnf install difftastic` for Fedora before the prebuilt binary (https://difftastic.wilfred.me.uk/installation.html), while `installer/registry.toml:949` installs the release asset on arch and fedora; package currency is unverified (no pacman or dnf query run); the macOS and Linux asset rows match the brew line and the downloads that `verify-registry.md:96-99` passed |
| update argv | ok | the entry declares no update argv; brew updates through the formula (`formula "difftastic"` at 0.72.0, https://formulae.brew.sh/api/formula/difftastic.json); the release-asset path re-runs the method (facts: `update: none`) |
| removal recipe and paths | ok | `installer/registry.toml:949` and the brew method declare no paths and no remove argv, and the manual documents a single `difft` binary with no config directory (https://difftastic.wilfred.me.uk/installation.html); a source-level search for config directories was not run, so that part is unverified |
| tuning keys | n/a | reason: the entry declares no tuning keys; difftastic is tuned through `DFT_*` environment variables and the user's own git configuration (https://github.com/Wilfred/difftastic#readme, "DFT_PARSE_ERROR_LIMIT"), which the installer does not write |
| postinstall hook | ok | `installer/registry.toml:940` difftastic block has no `postinstall`, `post_install`, `remove` or `update` key, so the decision tree lands on none |

## Proposed changes
- move the arch and fedora methods to `pacman -S difftastic` and `dnf install difftastic` once their current version is checked; risk: low; evidence: https://difftastic.wilfred.me.uk/installation.html

<!-- catalog-audit:complete -->
