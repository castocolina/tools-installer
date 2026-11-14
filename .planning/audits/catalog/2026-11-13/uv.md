# uv - catalog audit 2026-11-13

## Versions
- pinned: none (the script and brew methods are both unpinned)
- verified: 2026-11-04
- installed: 0.11.28 (`~/.local/bin/uv --version`, per `make audit-catalog facts uv`)
- latest: 0.13.8 (GitHub releases, https://api.github.com/repos/astral-sh/uv/releases?per_page=40, published 2026-11-12)
- latest: 0.13.8 (Homebrew formula, https://formulae.brew.sh/api/formula/uv.json)
- note: installed 0.11.28 is two minor versions behind 0.13.8; the entry is unpinned, so this is not drift

## Changelog
- 0.12.20 continues the search of XDG_CONFIG_DIRS after empty entries (https://github.com/astral-sh/uv/releases/tag/0.12.20)
- 0.12.24 lets UV_NO_CACHE=false and UV_OFFLINE=false override the matching `no-cache` and `offline` keys in configuration (https://github.com/astral-sh/uv/releases/tag/0.12.24)
- no install or update note between 0.11.28 and 0.13.8 changes the standalone script or the brew formula; 0.13.4 and 0.13.5 change only the bundled CA store and managed Python builds

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://astral.sh/uv/install.sh still serves the script and installs `uv uvx` to `$HOME/.local/bin` (install.sh:131 and the `_bins="uv uvx"` cases at install.sh:232-233); the vendor install page still lists the standalone installer and Homebrew, https://docs.astral.sh/uv/getting-started/installation/; the brew formula `uv` is still served, https://formulae.brew.sh/api/formula/uv.json |
| update argv | ok | https://docs.astral.sh/uv/getting-started/installation/ "Upgrading uv": `uv self update` for the standalone installer; the vendor says `UV_NO_MODIFY_PATH=1` stops the re-run from editing shell profiles, which the entry already sets in its method env |
| removal recipe and paths | ok | https://docs.astral.sh/uv/getting-started/installation/ "Uninstallation": `rm ~/.local/bin/uv ~/.local/bin/uvx` on macOS and Linux matches `paths`; the optional data cleanup (`uv cache clean`, `uv python dir`, `uv tool dir`) is user-run and not an installer path; the install receipt `~/.config/uv/uv-receipt.json` written by install.sh:115 and install.sh:576 sits inside `config_paths` `~/.config/uv`, so the default keep policy covers it |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts uv`: tuning none); the method env `UV_NO_MODIFY_PATH` is still read by install.sh:51 |
| postinstall hook | ok | `make audit-catalog facts uv` reports postinstall none and post_install none; installer/registry.toml:62-90 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
