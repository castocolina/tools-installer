# fx - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew, installer/registry.toml:1349-1374)
- verified: 2026-11-03 (installer/registry.toml:1356)
- installed: 39.2.0 (`fx --version`, per the facts block)
- latest: 40.0.1 (GitHub releases/latest, published 2026-10-22, https://api.github.com/repos/antonmedv/fx/releases/latest)
- latest: 40.0.1 (Homebrew formula, https://formulae.brew.sh/api/formula/fx.json)
- note: GitHub and Homebrew agree on 40.0.1, so there is no split; 40.0.0 is a major release after the installed 39.2.0

## Changelog
- 40.0.0 (2026-10-05) changes interactive keys: Esc no longer quits and the v key is removed; no note touches install, update, removal, config or MCP (https://github.com/antonmedv/fx/releases/tag/40.0.0)
- 40.0.1 (2026-10-22) fixes Unicode rendering in go-to-symbol matches and bumps a dependency; no note touches install, update, removal, config or MCP (https://github.com/antonmedv/fx/releases/tag/40.0.1)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the 40.0.1 release has fx_linux_amd64, fx_linux_arm64, fx_darwin_amd64 and fx_darwin_arm64 (https://api.github.com/repos/antonmedv/fx/releases?per_page=6), which pass in .planning/audits/catalog/2026-11-13/verify-registry.md:126-129; the brew formula serves 40.0.1 (https://formulae.brew.sh/api/formula/fx.json); the vendor install page also lists snap, scoop, pacman, pkg, go, docker, nix and a curl-to-sh script (https://fx.wtf/install), which the registry does not use; distro package currency is unverified and not compared |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:1349-1374, facts update: none); the vendor install page documents no upgrade command (https://fx.wtf/install) |
| removal recipe and paths | drift | upstream 40.0.1 reads user config from ~/.fxrc.js and $XDG_CONFIG_HOME/fx/.fxrc.js, defaulting to ~/.config/fx/.fxrc.js (https://api.github.com/repos/antonmedv/fx/contents/internal/engine/fxrc.go?ref=40.0.1 lines 21-31), but the entry declares no config_paths (installer/registry.toml:1349-1374) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:1349-1374, facts tuning: none); the FX_* variables documented at https://fx.wtf/configuration are the user's environment, which the installer never writes |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:1349-1374, facts postinstall: none) |

## Proposed changes
- add config_paths = ["~/.fxrc.js", "~/.config/fx/.fxrc.js"] to the fx entry so the user's rc file is recorded and kept on removal by default; risk: low; evidence: https://api.github.com/repos/antonmedv/fx/contents/internal/engine/fxrc.go?ref=40.0.1 lines 21-31

<!-- catalog-audit:complete -->
