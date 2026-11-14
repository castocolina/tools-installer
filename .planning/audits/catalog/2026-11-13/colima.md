# colima - catalog audit 2026-11-13

## Versions
- pinned: none (the brew method installs whatever the formula serves)
- verified: 2026-09-06
- installed: not installed (`colima` not on the probed PATH, per the facts probe)
- latest: v0.10.3 (GitHub releases/latest, published 2026-06-04, https://api.github.com/repos/abiosoft/colima/releases/latest)
- latest: 0.10.3 (Homebrew formula, https://formulae.brew.sh/api/formula/colima.json)
- note: no release is newer than the entry's verified date; the newest release is older than it

## Changelog
- none since the verified date 2026-09-06: v0.10.3 (https://github.com/abiosoft/colima/releases/tag/v0.10.3) is a k3s restart hotfix, and no release was published after it

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's Homebrew route is `brew install colima` (https://github.com/abiosoft/colima README.md, "Installation"; docs/INSTALL.md "Homebrew"), matching `installer/registry.toml:1126-1127` |
| update argv | ok | the vendor's own runtime update is `colima update` for the container runtimes inside the VM (https://github.com/abiosoft/colima release v0.10.2 notes), while the installer's update re-runs the brew method for the Colima binary, which the vendor's Homebrew route supports |
| removal recipe and paths | drift | the vendor keeps its config and VM data under `$HOME/.colima` (https://github.com/abiosoft/colima docs/FAQ.md lines 124-137) and `colima delete --data` is the vendor's data removal (FAQ.md line 695); the entry declares no `config_paths`, so the Uninstall screen cannot show or offer those paths (`installer/registry.toml:1115-1127`) |
| tuning keys | n/a | reason: the entry declares no tuning keys, so no vendor key can be deprecated or renamed |
| postinstall hook | ok | the entry declares no postinstall; the vendor says a Docker client is required for the Docker runtime (README line 82, "Docker client is required"), recorded as `recommends = ["docker"]` at `installer/registry.toml:1124` |

## Proposed changes
- add `config_paths = ["~/.colima"]` so the Uninstall screen lists the config and VM data, with the keep default; risk: medium; evidence: https://github.com/abiosoft/colima docs/FAQ.md lines 124-137

<!-- catalog-audit:complete -->
