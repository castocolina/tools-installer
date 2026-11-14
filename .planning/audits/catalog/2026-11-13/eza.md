# eza - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: v0.23.5 (`eza --version`)
- latest: v0.23.5 (GitHub releases/latest, https://api.github.com/repos/eza-community/eza/releases/latest)
- latest: 0.23.5 (Homebrew formula API, https://formulae.brew.sh/api/formula/eza.json)
- latest: 0.23.5-2 (Arch extra, https://archlinux.org/packages/search/json/?name=eza)
- latest: 0.23.5 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/eza)
- note: the Debian package is not in the Debian archive (https://sources.debian.org/api/src/eza/ returns 404); the vendor INSTALL.md points Debian users to a third-party apt repository

## Changelog
- no install, update, removal, config or MCP note between v0.23.5 and v0.23.5 (https://github.com/eza-community/eza/releases/tag/v0.23.5)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | installer/registry.toml:358-364 uses github_release on Arch and Fedora, while the vendor INSTALL.md recommends `pacman -S eza` (https://github.com/eza-community/eza/blob/v0.23.5/INSTALL.md, Arch Linux section) and `dnf install eza` (same file, Fedora section), and Arch extra and Fedora rawhide both carry 0.23.5; installer rule step 4 prefers a package manager when it is current enough (.claude/skills/tool-onboarding/SKILL.md, section 4) |
| update argv | ok | `make audit-catalog ARGS="facts eza"` reports update: none, the installer re-runs the method |
| removal recipe and paths | drift | installer/registry.toml:348-368 declares no config_paths, while the vendor README places user config in `$XDG_CONFIG_HOME/eza` (https://github.com/eza-community/eza/blob/v0.23.5/README.md, line 207); the config policy cannot be applied |
| tuning keys | n/a | reason: the entry declares no tuning keys and records no accepted customization |
| postinstall hook | ok | `make audit-catalog ARGS="facts eza"` reports postinstall: none and post_install: none; installer/registry.toml:348-368 declares no hook |

## Proposed changes
- move Arch to a pacman method and Fedora to a dnf method, keep github_release for Debian and brew for macOS; on Fedora Atomic hosts the dnf method needs the rpm-ostree owner probe as git uses (installer/registry.toml:303); risk: medium; evidence: https://github.com/eza-community/eza/blob/v0.23.5/INSTALL.md
- add config_paths = ["~/.config/eza"] to the eza [[tool]] entry (EZA_CONFIG_DIR overrides it); risk: low; evidence: https://github.com/eza-community/eza/blob/v0.23.5/README.md

<!-- catalog-audit:complete -->
