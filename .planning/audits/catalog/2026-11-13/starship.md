# starship - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 1.26.0 (`starship --version`)
- latest: v1.27.0 (GitHub releases/latest, https://api.github.com/repos/starship/starship/releases/latest)
- latest: 1.27.0 (Homebrew formula, https://formulae.brew.sh/api/formula/starship.json)

## Changelog
- 1.27.0 adds config options (`git_branch` `ignore_remotes`, `jj_*` modules, `claude_model` effort variable) and fixes two security advisories; no install, update, removal or MCP note between 1.26.0 and 1.27.0 (https://github.com/starship/starship/releases/tag/v1.27.0)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's guide lists `curl -sS https://starship.rs/install.sh \| sh`, `brew install starship` and distro packages (https://starship.rs/guide/); the registry uses the checksummed release tarballs for debian, arch, fedora and macos, plus brew for all; verify-registry lists all four v1.27.0 tarballs as passed (`.planning/audits/catalog/2026-11-13/verify-registry.md:215-218`) |
| update argv | ok | `starship --help` shows no upgrade subcommand, so the installer re-running the method is the vendor's own upgrade path (`installer/registry.toml:520`, `update: none`) |
| removal recipe and paths | drift | `installer/registry.toml:520` declares no `config_paths`, but the vendor reads the user config at `~/.config/starship.toml` (https://starship.rs/config/), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires |
| tuning keys | n/a | reason: the entry declares no tuning keys (`installer/registry.toml:520`); its shell init is a `post_install` action (`installer/registry.toml:525`), not a settings key |
| postinstall hook | ok | the entry declares no `postinstall` hook and no host_setup; the shell init is the named action `installer/tweaks.py:160` (`eval "$(starship init zsh)"`, bash variant on the same line), the same init line the vendor gives (https://starship.rs/guide/) |

## Proposed changes
- add `config_paths = ["~/.config/starship.toml"]` to the starship tool so removal states the config policy; risk: low; evidence: https://starship.rs/config/

<!-- catalog-audit:complete -->
