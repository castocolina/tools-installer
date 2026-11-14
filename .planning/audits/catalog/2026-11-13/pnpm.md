# pnpm - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script, brew)
- verified: 2026-11-04
- installed: 11.18.0 (`pnpm --version`, facts block)
- latest: 12.18.0 (GitHub releases/latest, https://api.github.com/repos/pnpm/pnpm/releases/latest)
- latest: 12.18.0 (brew formula, https://formulae.brew.sh/api/formula/pnpm.json)
- note: GitHub's releases list also holds v12.19.0, v12.20.0 and v12.21.0 (not prereleases, published 2026-11-10 to 2026-11-13) that releases/latest does not return; all are major 12, so there is no major split

## Changelog
- pnpm 12 is a major upgrade: "If you already have pnpm v11.10.0 or newer, update directly to pnpm 12: pnpm self-update" (https://pnpm.io/installation); the installed 11.18.0 qualifies
- v12.21.0 adds PowerShell login-shell support to `pnpm setup` and the install script, writing PNPM_HOME into profile.ps1 (https://github.com/pnpm/pnpm/releases/tag/v12.21.0)
- v12.16.0 adds `pnpm setup --no-modify-path` (https://github.com/pnpm/pnpm/releases/tag/v12.16.0)
- v12.11.0 links agent skills from direct dependencies into agent skill directories such as .claude/skills (https://github.com/pnpm/pnpm/releases/tag/v12.11.0)
- v12.9.1 makes `pnpm self-update` fail for Homebrew-installed pnpm and print the brew upgrade command (https://github.com/pnpm/pnpm/releases/tag/v12.9.1)
- v12.3.1 fixes global commands that failed after a self-update from 12.2 to 12.3 (https://github.com/pnpm/pnpm/releases/tag/v12.3.1)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://pnpm.io/installation gives the POSIX script `curl -fsSL https://get.pnpm.io/install.sh`; the script's pnpm_home_dir (https://get.pnpm.io/install.sh lines 590-604) yields ~/.local/share/pnpm on Linux and ~/Library/pnpm on macOS, matching installer/registry.toml:2214-2240; the brew formula exists at https://formulae.brew.sh/api/formula/pnpm.json |
| update argv | ok | https://pnpm.io/cli/self-update documents `pnpm self-update` (latest dist-tag, no downgrade); https://pnpm.io/installation names it as the update path; installer/registry.toml:2233 |
| removal recipe and paths | ok | https://pnpm.io/uninstall says a standalone-script install is removed by deleting PNPM_HOME, which also holds global packages; the entry removes only the launchers and declares no remove on purpose (installer/registry.toml:2220-2226), so the store and global packages are kept; the pn, pnpx and pnx names are not in install.sh text and rest on the 2026-11-04 container run recorded at installer/registry.toml:2222, which this audit did not repeat (unverified here) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action (installer/registry.toml:2203-2213) |
| postinstall hook | ok | no Tool.postinstall is declared (installer/registry.toml:2203-2262), which is the None branch of .claude/architecture.md "Postinstall-per-harness classification" |

## Proposed changes
- none

<!-- catalog-audit:complete -->
