# brew - catalog audit 2026-11-13

## Versions
- pinned: none (the script methods are unpinned)
- verified: 2026-11-04
- installed: 7.0.13 (`/home/linuxbrew/.linuxbrew/bin/brew --version`, per `make audit-catalog facts brew`)
- latest: 7.0.13 (GitHub releases/latest, https://api.github.com/repos/Homebrew/brew/releases/latest, published 2026-11-09)
- note: the facts block declares no latest source; the GitHub release above is the one used

## Changelog
- none between installed 7.0.13 and latest 7.0.13; the 7.0.13 notes are documentation, prefetch and lint changes, none touching install, update, removal, config or MCP (https://github.com/Homebrew/brew/releases/tag/7.0.13)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the registry's macOS amd64 script method (installer/registry.toml:186-195, `arch = ["amd64"]`, bin_dir `/usr/local/bin`) targets an Intel Mac, but the upstream installer aborts there: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh lines 169-171 `abort "Homebrew on macOS is only supported on Apple Silicon processors!"`; the vendor's install page gives `/opt/homebrew` as the macOS prefix, https://docs.brew.sh/Installation; the arm64 macOS method (registry.toml:174-185) and the Linux methods (registry.toml:198-) match the upstream script (install.sh:175 and install.sh:198 prefix defaults) |
| update argv | ok | `brew update` per https://docs.brew.sh/Manpage ("brew update will update Homebrew to the latest stable version"), matching `update = ["brew", "update"]` on each script method (registry.toml:182, 193) |
| removal recipe and paths | ok | the registry declares no `remove` and no `paths` on purpose (registry.toml:178-180 comment: Homebrew's uninstaller removes the whole prefix); upstream https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh removes Cellar, Caskroom and the repository through `execute_sudo` (uninstall.sh:178-187 and 332-336), so the installer correctly hands removal to the user and never runs that script |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts brew`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts brew` reports postinstall none and post_install none; installer/registry.toml:164-215 declares no hook |

## Proposed changes
- drop the macOS amd64 script method (registry.toml:186-195) and update the `# Verified` comment to say Homebrew supports Apple Silicon only on macOS; risk: low; evidence: https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh lines 169-171

<!-- catalog-audit:complete -->
