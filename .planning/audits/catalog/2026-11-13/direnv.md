# direnv - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release, brew)
- verified: 2026-11-03
- installed: 2.37.1 (`direnv --version`)
- latest: v2.38.2 (GitHub releases/latest, https://api.github.com/repos/direnv/direnv/releases/latest)
- latest: 2.38.2 (Homebrew formula, https://formulae.brew.sh/api/formula/direnv.json)
- note: v2.38.0 was tagged but never published (its binaries failed to upload); v2.38.1 is the first published release after 2.37.1, so the latest published line is 2.38.2

## Changelog
- v2.38.1 (2026-10-06) requires go 1.26 to build from source; the registry uses release binaries and brew, so no declared method changes (https://github.com/direnv/direnv/releases/tag/v2.38.1)
- v2.38.1 changes the zsh hook to run only at the top level (`feat(zsh): only run the hook from the top level`, #1583); the init line the installer writes is unchanged (https://github.com/direnv/direnv/releases/tag/v2.38.1)
- v2.38.1 adds `DIRENV_DISABLE`, `DIRENV_EXE_PATH`, `log_format = "-"` and `require_allowed` settings; none is a key the entry tunes (https://github.com/direnv/direnv/releases/tag/v2.38.1)
- v2.38.1 renames the Windows release binaries to `direnv.windows-<arch>.exe`; Linux and macOS asset names are unchanged, and verify-registry still finds the v2.38.2 Linux and macOS assets (https://github.com/direnv/direnv/releases/tag/v2.38.1, `.planning/audits/catalog/2026-11-13/verify-registry.md:100-103`)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor lists system packages first (Fedora, Arch, Debian, Homebrew and others) and binary builds second (https://direnv.net/docs/installation.html); the registry uses the release binaries for debian, arch, fedora and macos plus brew for all (`installer/registry.toml:684`, `installer/registry.toml:691`, `installer/registry.toml:698`); verify-registry records the v2.38.2 binaries for all four Linux and macOS arch names as passed (`.planning/audits/catalog/2026-11-13/verify-registry.md:100-103`) |
| update argv | ok | `update: none` (facts): direnv has no self-update command (`direnv --help` lists none), so the installer re-running the method is the upgrade path, and the vendor's install page offers the same binary route (https://direnv.net/docs/installation.html) |
| removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:672-699`), but the vendor reads its config from `~/.config/direnv/direnv.toml` (https://direnv.net/man/direnv.toml.1.html), so the Uninstall screen has no config row or default config policy as tool-onboarding 4b requires; the binary removal itself is correct (L1 brew, L2 receipt for the release binaries) |
| tuning keys | ok | the post_install action `source_shell_init` writes `eval "$(direnv hook zsh)"` and the bash variant (`installer/tweaks.py:163-165`), the same hook line the vendor documents (https://direnv.net/docs/hook.html); the entry declares no tuning keys of its own (`tuning: none`) |
| postinstall hook | ok | the entry declares no `postinstall` hook and no host_setup (`installer/registry.toml:672-699`); its install-time work is the named action `source_shell_init` (`installer/registry.toml:677`), which is the install-tuning branch of the architecture tree |

## Proposed changes
- add `config_paths = ["~/.config/direnv"]` to the direnv tool so removal states the config policy (default keep, since direnv.toml is user-written); risk: low; evidence: https://direnv.net/man/direnv.toml.1.html

<!-- catalog-audit:complete -->
