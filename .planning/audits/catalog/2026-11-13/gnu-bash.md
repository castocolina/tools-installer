# gnu-bash - catalog audit 2026-11-13

## Versions
- pinned: unpinned (brew)
- verified: 2026-09-06
- installed: not installed (facts: `installed: not installed`)
- latest: 5.3.20 (Homebrew formula bash, https://formulae.brew.sh/api/formula/bash.json)
- latest: 5.3.20 (GNU patch series ends at bash53-020, https://ftp.gnu.org/gnu/bash/bash-5.3-patches/)

## Changelog
- bash53-016 (2026-07, patch to `configure.ac`, `configure`, `general.c`, `general.h`, `redir.c`) makes the macOS pipe-size check decide at run time whether to use the compile-time size; it touches the build configure step Homebrew runs, and the formula name `bash` and the detect paths are unchanged (https://ftp.gnu.org/gnu/bash/bash-5.3-patches/bash53-016)
- no other note touching install, update, removal, config or MCP between patches 016 and 020 (bash53-017 to bash53-020 touch readline display and syntax files only; https://ftp.gnu.org/gnu/bash/bash-5.3-patches/)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the Homebrew formula `bash` is the package-manager route the user already trusts on macOS (step 4 rule 1), and the two brew stanzas cover macOS arm64 and amd64 (`installer/registry.toml:661`, `installer/registry.toml:667`); the formula's stable version is 5.3.20 (https://formulae.brew.sh/api/formula/bash.json); the entry is macOS-only, so no Linux method is owed |
| update argv | ok | `update: none` (facts): Homebrew upgrades the `bash` formula, and the installer re-runs the brew method, so no argv is declared (`installer/registry.toml:650`) |
| removal recipe and paths | ok | removal is Homebrew's own remove of the `bash` formula (L1, step 4b brew row); `paths: none` is right because brew owns the files; `detect_path` values `/opt/homebrew/bin/bash` and `/usr/local/bin/bash` (`installer/registry.toml:664`, `installer/registry.toml:670`) are presence probes, not receipts |
| tuning keys | n/a | reason: the entry declares no tuning keys and no `post_install` action (`installer/registry.toml:650-672`, `tuning: none`, `post_install: none`) |
| postinstall hook | ok | the entry declares no `postinstall` hook and no host_setup (`installer/registry.toml:650-672`), so the classification tree ends at none |

## Proposed changes
- none

<!-- catalog-audit:complete -->
