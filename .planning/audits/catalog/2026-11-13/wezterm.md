# wezterm - catalog audit 2026-11-13

## Versions
- pinned: unpinned (pacman, github_release, cask)
- verified: 2026-11-03
- installed: 20240203-110809-5046fc22 (`wezterm --version`)
- latest: 20240203-110809-5046fc22 (GitHub releases/latest, https://api.github.com/repos/wezterm/wezterm/releases/latest)
- latest: 20240203.110809.5046fc22.r869.g76b606ec5-4 (extra, https://archlinux.org/packages/search/json/?name=wezterm)
- latest: 20240203-110809,5046fc22 (brew cask, https://formulae.brew.sh/api/cask/wezterm.json)
- note: the GitHub "latest" is the 2024-02-03 stable tag; a nightly release exists (https://api.github.com/repos/wezterm/wezterm/releases/tags/nightly, with an Ubuntu20.04 AppImage) but the stable method does not use it; the vendor's Linux page names a nightly AppImage and an apt nightly package (https://wezterm.org/install/linux.html)

## Changelog
- none: installed 20240203-110809-5046fc22 equals the GitHub latest, so there is no version gap to read; the vendor's Linux install page (https://wezterm.org/install/linux.html) gives no update or removal step for the AppImage beyond a fresh download

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's Linux page documents the AppImage install (https://wezterm.org/install/linux.html, "Installing on Linux using AppImage"); the stable release lists WezTerm-20240203-110809-5046fc22-Ubuntu20.04.AppImage with its .sha256 (https://api.github.com/repos/wezterm/wezterm/releases/latest); arm64 Linux has only .deb assets there (Debian12.arm64.deb and Ubuntu22.04.arm64.deb), which matches the amd64-only gate on the AppImage method and its comment (installer/registry.toml:3007-3016); the cask is not disabled (https://formulae.brew.sh/api/cask/wezterm.json); pacman is the Arch package. Unverified: the vendor page's stable AppImage link uses the template name ubuntu24_AppImage_stable, which the fetched HTML does not resolve, so the exact asset the vendor points at is unknown |
| update argv | ok | none declared; the entry's method is re-run, and the vendor's AppImage page describes a fresh download with no update command (https://wezterm.org/install/linux.html) |
| removal recipe and paths | drift | the AppImage receipt (installer/registry.toml:3040-3048) and pacman and cask removals are fine, but the entry declares no config_paths (installer/registry.toml:3027-3054). The installer's terminal-shell synchronizer writes the owned region of the wezterm config at $XDG_CONFIG_HOME/wezterm/wezterm.lua or ~/.wezterm.lua (installer/terminal_shell.py:163-170 and :967-972), and config_targets reads only config_paths (installer/uninstall.py:119-121), so removal never lists that file. The vendor documents the same paths (https://wezterm.org/config/files.html) |
| tuning keys | n/a | reason: the entry declares no post_install action and no tuning keys (facts `tuning: none`, `post_install: none`) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook; the wezterm.lua write is the terminal-shell synchronizer, not a post_install hook (installer/terminal_shell.py:967-972) |

## Proposed changes
- declare config_paths = ["~/.config/wezterm"] on the wezterm entry so removal lists the synchronizer's file; the legacy ~/.wezterm.lua is one level under ~ and the validator refuses it (installer/model.py:439), so that case is a backlog gap; risk: low; evidence: https://wezterm.org/config/files.html

<!-- catalog-audit:complete -->
