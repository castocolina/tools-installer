# ruff - catalog audit 2026-11-13

## Versions
- pinned: none (github_release, uv-tool and brew are all unpinned)
- verified: 2026-11-03
- installed: not installed (facts: `installed: not installed`)
- latest: 0.17.5 (GitHub releases/latest, https://api.github.com/repos/astral-sh/ruff/releases/latest, published 2026-11-12)
- latest: 0.17.5 (PyPI, https://pypi.org/pypi/ruff/json)
- latest: 0.17.5 (Homebrew formula, https://formulae.brew.sh/api/formula/ruff.json)
- note: verified 2026-11-03 predates the 0.17.5 release of 2026-11-12; the verify-registry record already passes its archives

## Changelog
- nothing is installed, so the range is the 0.17.5 release alone (https://github.com/astral-sh/ruff/releases/tag/0.17.5)
- config: "Redirect renamed rules" (#30081) and the new `renamed-rule` (RUF202) make a renamed rule in a config `select` list redirect instead of failing; the installer declares no ruff config, so tuning is unaffected
- no other install, update, removal or MCP note in the 0.17.5 release notes; the install section lists only the prebuilt-binary shell and PowerShell scripts

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://docs.astral.sh/ruff/installation/ recommends uv ("uv tool install ruff@latest", "Or installed with uv (recommended), pip, or pipx") and lists Homebrew; the registry's uv-tool, brew and github_release methods match (installer/registry.toml:742-763); the musl and apple-darwin archives are the ones `make verify-registry` passed (`.planning/audits/catalog/2026-11-13/verify-registry.md`, Passed section, lines 203-206) |
| update argv | ok | the entry declares no update argv, so the installer re-runs the method; for a uv-tool owner the installer's own upgrade is `uv tool upgrade ruff` (installer/update.py:202), which matches the vendor's upgrade route (https://docs.astral.sh/ruff/installation/) |
| removal recipe and paths | ok | the github_release method extracts only the `ruff` member (installer/registry.toml:748 and 756, `member = "ruff"`), so removal is the receipt of that binary; the uv-tool owner removes through `uv tool uninstall` (installer/uninstall.py:114); brew through brew; the entry declares no paths (installer/registry.toml:732-764) |
| tuning keys | n/a | reason: the entry declares no tuning keys (`make audit-catalog facts ruff`: tuning none) |
| postinstall hook | ok | `make audit-catalog facts ruff` reports postinstall none and post_install none; installer/registry.toml:732-764 declares no hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
