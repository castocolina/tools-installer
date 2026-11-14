# neovim - catalog audit 2026-11-13

## Versions
- pinned: none (github_release, brew, dnf, apt and pacman are all unpinned)
- verified: 2026-11-13
- installed: none (`nvim` is not on this host, per the facts block)
- latest: v0.12.6 (GitHub releases/latest, published 2026-10-09, https://api.github.com/repos/neovim/neovim/releases/latest)
- latest: 0.12.6 (Homebrew formula neovim, https://formulae.brew.sh/api/formula/neovim.json)
- latest: 0.12.6-1 (Arch extra, https://archlinux.org/packages/search/json/?name=neovim)
- latest: 0.12.6-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/neovim)
- latest: 0.12.4-1 (Debian sources API, https://sources.debian.org/api/src/neovim/, suite not named)
- note: the Debian result does not name a suite; the registry.toml neovim comment says Debian 13 ships 0.10.4, which this source does not confirm or refute

## Changelog
- no installed version to diff from; the v0.12.6 release body names no install, update, removal, config or MCP change beyond its tarball Install section (https://api.github.com/repos/neovim/neovim/releases/latest)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the v0.12.6 release body documents one tar.gz per OS and arch (Install section, https://api.github.com/repos/neovim/neovim/releases/latest), matching the registry's github_release routes; asset rows in verify-registry.md lines 191-194; the brew formula serves 0.12.6 (https://formulae.brew.sh/api/formula/neovim.json) |
| update argv | ok | the registry declares none and the installer re-runs the tarball method, which replaces the self-contained tree; the release body shows the tree is run in place (./nvim-macos-arm64/bin/nvim, https://api.github.com/repos/neovim/neovim/releases/latest) |
| removal recipe and paths | ok | the opt tree and the link are receipt-proven (installer/locations.py:85 resolves ~/.local/opt/<name>); config_paths = ["~/.config/nvim"] (registry.toml:2644) matches upstream, which names ~/.config/nvim/init.lua (https://github.com/neovim/neovim/blob/master/runtime/doc/starting.txt#L484) |
| tuning keys | n/a | reason: the entry declares no settings-file key (facts block: tuning none) |
| postinstall hook | ok | the three hook names are in the closed table (installer/post_install.py:480, 486, 487 and installer/model.py:133-140); the starter target is ~/.config/nvim (installer/post_install.py:183); clone_nvim_starter only adds the starter when the target is absent or empty (installer/post_install.py:243, _absent_or_empty gate) |

## Proposed changes
- re-check the Debian 13 claim in the registry.toml neovim comment (0.10.4) against the suite the apt method really installs, since sources.debian.org shows 0.12.4-1; risk: low; evidence: https://sources.debian.org/api/src/neovim/

<!-- catalog-audit:complete -->
