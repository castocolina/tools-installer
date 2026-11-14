# jetbrains-toolbox - catalog audit 2026-11-13

## Versions
- pinned: none (cask and tarball are both unpinned)
- verified: 2026-11-03
- installed: 3.9.1.89198 (`jetbrains-toolbox --version`, per the facts block)
- latest: 3.9.1,3.9.1.89198 (Homebrew cask jetbrains-toolbox, https://formulae.brew.sh/api/cask/jetbrains-toolbox.json)
- latest: 3.9.1.89198 (JetBrains Linux download page, https://www.jetbrains.com/toolbox-app/download/download-thanks.html?platform=linux)
- note: the ownership-only Linux cask jetbrains-toolbox-linux returned HTTP 404 from the Homebrew API, so it gives no version

## Changelog
- installed equals latest (3.9.1.89198); no release notes were reached (https://www.jetbrains.com/toolbox-app/whatsnew/ returned 404), so no note is recorded

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the JetBrains Linux download page lists the x64 and arm64 tar.gz for 3.9.1.89198, each with a .sha256 file (https://www.jetbrains.com/toolbox-app/download/download-thanks.html?platform=linux); the registry's latest redirect resolves to jetbrains-toolbox-3.9.1.89198.tar.gz (curl -sIL on data.services.jetbrains.com); asset rows in verify-registry.md lines 170-171 |
| update argv | unknown | reason: the registry declares none; the Toolbox app's own update behaviour is not documented in the pages read; container check not run (batch rule: no containers) |
| removal recipe and paths | unknown | reason: the vendor uninstall help pages tried (https://www.jetbrains.com/help/toolbox-app/uninstall-the-toolbox-app.html and https://www.jetbrains.com/help/toolbox-app/install-the-toolbox-app-on-linux.html) return 404, so the directory the app writes on first run is not established; container check not run (batch rule: no containers) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action |
| postinstall hook | ok | none declared (installer/registry.toml:2504); no customization is recorded in the entry's Verified comment |

## Proposed changes
- none

<!-- catalog-audit:complete -->
