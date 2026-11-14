# zoxide - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned, installer/registry.toml:380-396)
- verified: 2026-11-03 (installer/registry.toml:378)
- installed: none (zoxide is not installed on this host, per the facts block)
- latest: v0.10.0 (GitHub releases/latest, https://api.github.com/repos/ajeetdsouza/zoxide/releases/latest)
- latest: 0.10.0 (Homebrew formula, https://formulae.brew.sh/api/formula/zoxide.json)
- note: GitHub and Homebrew agree on 0.10.0, so there is no major split

## Changelog
- no note from v0.9.6 through v0.10.0 touches install, update, removal, config or MCP for the installer; the v0.10.0 nushell `use` export change affects only nushell init, which the installer does not write (https://api.github.com/repos/ajeetdsouza/zoxide/releases?per_page=5)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README recommends the install.sh script (https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 99-102), but the registry ranks release assets and brew above a vendor script (installer/registry.toml:380-396); the Linux and macOS arm64 and amd64 assets pass (.planning/audits/catalog/2026-11-13/verify-registry.md:243-246) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:370-396); the README documents no self-update command (https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 87-104) |
| removal recipe and paths | drift | the entry declares no config_paths (installer/registry.toml:370-396), but the README documents the frecency database at $XDG_DATA_HOME/zoxide or ~/.local/share/zoxide on Linux and ~/Library/Application Support/zoxide on macOS (https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 404-411); the binary removal itself is ok (L2 receipt for github_release, L1 for brew) |
| tuning keys | n/a | reason: the entry declares no tuning keys (installer/registry.toml:370-396, facts tuning: none) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook; its post_install action source_shell_init (installer/registry.toml:374) writes the guarded zoxide init lines (installer/tweaks.py:170), which match the README's eval lines (https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 230 and 324) |

## Proposed changes
- add config_paths = ["~/.local/share/zoxide", "~/Library/Application Support/zoxide"] to the zoxide entry so the database is recorded and kept on removal by default; risk: low; evidence: https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/README.md lines 404-411

<!-- catalog-audit:complete -->
