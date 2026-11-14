# drawio-desktop - catalog audit 2026-11-13

## Versions
- pinned: 32.6.1 (macOS app methods, `installer/registry.toml:3250` and `installer/registry.toml:3260`); the two Linux github_release methods are unpinned
- verified: 2026-11-03 (`verified = 2026-11-03` in the entry header, `installer/registry.toml:3215`)
- installed: 32.6.1 (`drawio --version`, from the facts block)
- latest: v32.6.10 (GitHub releases/latest, published 2026-11-04, https://api.github.com/repos/jgraph/drawio-desktop/releases/latest)
- note: the run's verify-registry.md records the macOS drift, `.planning/audits/catalog/2026-11-13/verify-registry.md:5` (arm64 zip) and `:6` (x64 zip), "newer stable release v32.6.10 (pinned 32.6.1)"; confirmed against the GitHub release above. Versions between the pin and latest: the release list shows no tag between v32.6.1 and v32.6.10 (https://api.github.com/repos/jgraph/drawio-desktop/releases)

## Changelog
- 32.6.10 notes list Electron 44.10.2, an all-pages SVG export (--all-pages -f svg), and a fix so command line export no longer hangs on malformed PNG files; nothing on install, update, removal, config location or MCP (release notes, https://github.com/jgraph/drawio-desktop/releases/tag/v32.6.10)
- 32.6.10 asset names for the two AppImages and both macOS zips are unchanged from 32.6.1, and the release publishes `Files-SHA256-Hashes.txt` plus a GitHub `sha256:` digest on every asset (https://api.github.com/repos/jgraph/drawio-desktop/releases/tags/v32.6.10)
- README Updates section: AppImage, macOS and Windows installer builds check github.com daily and self-update in the background; `DRAWIO_DISABLE_UPDATE=true` or `--disable-update` turns that off (https://raw.githubusercontent.com/jgraph/drawio-desktop/dev/README.md)
- no other install, update, removal, config or MCP note between 32.6.1 and 32.6.10 (draw.io core ChangeLog 32.6.10 is editor features only, https://raw.githubusercontent.com/jgraph/drawio/v32.6.10/ChangeLog)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the macOS app methods pin 32.6.1 (`installer/registry.toml:3250`, `installer/registry.toml:3260`) while v32.6.10 is the stable release, `.planning/audits/catalog/2026-11-13/verify-registry.md:5` and `.planning/audits/catalog/2026-11-13/verify-registry.md:6`, https://api.github.com/repos/jgraph/drawio-desktop/releases/latest; Linux AppImage methods are ok: `drawio-x86_64-32.6.10.AppImage` and `drawio-arm64-32.6.10.AppImage` exist with the same names and a listed digest, https://github.com/jgraph/drawio-desktop/releases/download/v32.6.10/Files-SHA256-Hashes.txt, and are recorded in `.planning/audits/catalog/2026-11-13/verify-registry.md:110` and `.planning/audits/catalog/2026-11-13/verify-registry.md:111` |
| update argv | ok | none declared; the installer re-runs the method and replaces the raw AppImage, `installer/download.py:461` (the macOS pin staleness is the install method drift, not an update argv fault); the vendor's own background self-update of the AppImage (README Updates, https://raw.githubusercontent.com/jgraph/drawio-desktop/dev/README.md) was not exercised, unverified |
| removal recipe and paths | ok | no recipe declared: removal is the install receipt (L2, `.claude/skills/tool-onboarding/SKILL.md` step 4b); `installer/download.py:312` computes the single raw file `<bin>/drawio` and `installer/download.py:323` the macOS app bundle, and the registry description says uninstall removes its managed app or AppImage; the vendor documents no uninstall step for an AppImage (https://raw.githubusercontent.com/jgraph/drawio-desktop/dev/README.md) |
| tuning keys | n/a | reason: the entry declares no tuning keys or config_paths (facts: tuning none, paths none) |
| postinstall hook | n/a | reason: the entry declares no postinstall or post_install hook (facts: postinstall none, post_install none) |

## Proposed changes
- bump the two macOS app pins (version and sha256) to 32.6.10 with `make verify-registry ARGS="--write"`; risk: low; evidence: GitHub digests sha256 for `draw.io-arm64-32.6.10.zip` and `draw.io-x64-32.6.10.zip` in https://github.com/jgraph/drawio-desktop/releases/download/v32.6.10/Files-SHA256-Hashes.txt

<!-- catalog-audit:complete -->
