# yq - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew are both unpinned, installer/registry.toml:501-516)
- verified: 2026-11-03 (installer/registry.toml:499)
- installed: v4.53.6 (`yq --version`, per the facts block)
- latest: v4.54.3 (GitHub releases/latest, https://api.github.com/repos/mikefarah/yq/releases/latest)
- latest: 4.54.3 (Homebrew formula, https://formulae.brew.sh/api/formula/yq.json)
- note: GitHub and Homebrew agree on 4.54.3, so there is no major split

## Changelog
- no note from v4.54.1 through v4.54.3 touches install, update, removal, config or MCP; the 4.54.2 and 4.54.3 security changes alter command output and flags only (https://api.github.com/repos/mikefarah/yq/releases?per_page=8)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the README lists the raw release binary and Homebrew (https://raw.githubusercontent.com/mikefarah/yq/master/README.md lines 77-110); the registry uses the raw release asset first and brew second (installer/registry.toml:501-516); linux and macOS amd64 and arm64 assets pass for 4.54.3 (.planning/audits/catalog/2026-11-13/verify-registry.md:239-242), and yq is absent from the unverified-at-install list |
| update argv | ok | the entry declares no update argv and the installer re-runs the method (installer/registry.toml:492-516); the README documents no self-upgrade command, and brew upgrades go through brew itself (https://raw.githubusercontent.com/mikefarah/yq/master/README.md lines 77-110) |
| removal recipe and paths | ok | the entry declares no paths, config_paths or remove (installer/registry.toml:492-516); yq writes no config or state of its own, and the binary is removed through its receipt (L2) or brew (L1); the README documents no config directory (https://raw.githubusercontent.com/mikefarah/yq/master/README.md) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:492-516, facts tuning: none) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook and no post_install action (installer/registry.toml:492-516, facts postinstall: none) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
