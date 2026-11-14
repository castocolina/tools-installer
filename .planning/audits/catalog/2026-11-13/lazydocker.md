# lazydocker - catalog audit 2026-11-13

## Versions
- pinned: none (github_release and brew entries are unpinned)
- verified: 2026-11-03
- installed: 0.25.2 (`lazydocker --version`, per the facts probe)
- latest: v0.25.2 (GitHub releases/latest, https://api.github.com/repos/jesseduffield/lazydocker/releases/latest)
- latest: 0.25.2 (Homebrew formula, https://formulae.brew.sh/api/formula/lazydocker.json)
- note: GitHub's newest release is also v0.25.2 (published 2026-04-19, not a prerelease); no newer major exists

## Changelog
- no install, update, removal, config or MCP note between 0.25.2 and 0.25.2 (release notes at https://github.com/jesseduffield/lazydocker/releases/tag/v0.25.2 list UI and flag commits only)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | Homebrew core and tap formula and the release binary, https://raw.githubusercontent.com/jesseduffield/lazydocker/master/README.md (lines 94-105, 141-146); the github_release assets resolve per `.planning/audits/catalog/2026-11-13/verify-registry.md:179-182`; the registry models only x86_64 and arm64 (`installer/assets.py:11`), so the 32-bit Linux builds the vendor ships are not a feasible combination here |
| update argv | ok | upstream has no self-update command; its upgrade path is re-running the install (README lines 141-146, `brew upgrade` via the same formula), which is what the entry's "re-runs the method" update declares |
| removal recipe and paths | drift | the entry declares no `config_paths`, but the vendor documents the user config at `~/.config/lazydocker/config.yml` (Linux) and `~/Library/Application Support/jesseduffield/lazydocker/config.yml` (macOS), https://raw.githubusercontent.com/jesseduffield/lazydocker/master/docs/Config.md (lines 11-12); `installer/registry.toml:1004-1005` shows the block without it |
| tuning keys | n/a | reason: the entry declares no tuning keys, so no vendor key can be deprecated or renamed |
| postinstall hook | drift | lazydocker is a UI over a running docker environment (README line 43) and the entry carries neither a `requires` edge nor a `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1004-1033`) |

## Proposed changes
- add `config_paths` for the Linux and macOS config locations, with the macOS path as a per-OS variant; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazydocker/master/docs/Config.md
- record the docker runtime expectation in a `# Verified` note, or add an edge if the catalog should install docker first; risk: low; evidence: https://raw.githubusercontent.com/jesseduffield/lazydocker/master/README.md

<!-- catalog-audit:complete -->
