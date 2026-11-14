# fzf - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned, installer/registry.toml:409-427)
- verified: 2026-11-03 (installer/registry.toml:407)
- installed: 0.74.5 (`fzf --version`, per the facts block)
- latest: v0.75.0 (GitHub releases/latest, https://api.github.com/repos/junegunn/fzf/releases/latest)
- latest: 0.75.0 (Homebrew formula, https://formulae.brew.sh/api/formula/fzf.json)
- note: GitHub and Homebrew agree on 0.75.0, so there is no major split

## Changelog
- v0.75.0 adds a Windows MSI and a winget upgrade note; both are Windows only and outside this registry's platforms (https://api.github.com/repos/junegunn/fzf/releases?per_page=4)
- no note between 0.74.5 and 0.75.0 touches macOS or Linux install, update, removal, config or MCP; the nushell completion minimum change affects only nushell, which the installer does not write (https://api.github.com/repos/junegunn/fzf/releases?per_page=4)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README lists brew and the official binary releases (https://raw.githubusercontent.com/junegunn/fzf/master/README.md lines 111-116 and 178-184); the registry uses the checksummed release asset first and brew second (installer/registry.toml:409-427); linux and macOS amd64 and arm64 assets pass for 0.75.0 (.planning/audits/catalog/2026-11-13/verify-registry.md:130-133) |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:399-427); the README's upgrade commands are `brew update; brew upgrade fzf` for brew and a fresh release download otherwise (https://raw.githubusercontent.com/junegunn/fzf/master/README.md lines 268-273) |
| removal recipe and paths | ok | the entry declares no paths, remove or config_paths (installer/registry.toml:399-427); the binary is removed through its receipt (L2) or brew (L1); the README's FZF_DEFAULT_OPTS_FILE is a user-authored file the installer never creates (https://raw.githubusercontent.com/junegunn/fzf/master/README.md lines 434-437) |
| tuning keys | n/a | reason: the entry declares no tuning keys (installer/registry.toml:399-427, facts tuning: none) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook; its post_install action source_shell_init (installer/registry.toml:403) writes the guarded fzf key-binding lines (installer/tweaks.py:175), which match the README's `source <(fzf --zsh)` and `eval "$(fzf --bash)"` (https://raw.githubusercontent.com/junegunn/fzf/master/README.md lines 202-207) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
