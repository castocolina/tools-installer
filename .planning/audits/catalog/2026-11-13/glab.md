# glab - catalog audit 2026-11-13

## Versions
- pinned: none (brew, dnf, pacman and apt install the version each manager serves)
- verified: 2026-10-13
- installed: 1.130.0 (`glab --version`)
- latest: v1.130.0 (GitLab releases permalink, https://gitlab.com/api/v4/projects/gitlab-org%2Fcli/releases/permalink/latest, released 2026-11-10)
- latest: 1.130.0 (Homebrew formula stable, https://formulae.brew.sh/api/formula/glab.json)
- latest: 1.130.0-1 (Arch extra, https://archlinux.org/packages/search/json/?name=glab)
- latest: 1.53.0-1 (Debian trixie, forky and sid, https://sources.debian.org/api/src/glab/)
- latest: 1.114.0-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/glab)
- note: the Fedora value is rawhide only; the stable Fedora branches were not read, so their version is unverified. Debian's bookworm-backports package is 1.33.0-1~bpo12+1 and is an older suite.

## Changelog
- no install, update, removal, config or MCP note between 1.130.0 and 1.130.0

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the Debian apt package is 1.53.0-1 (https://sources.debian.org/api/src/glab/) while the latest is 1.130.0; the vendor's officially supported Linux method is Homebrew and it lists WakeMeOps for Debian and Ubuntu, not the distro package (https://gitlab.com/gitlab-org/cli/-/raw/main/docs/installation_options.md, Linux section); brew and pacman serve 1.130.0; Fedora stable is unverified |
| update argv | ok | the entry declares no update argv, which is right for manager-installed methods (tool-onboarding step 4b); the vendor's own update is `brew upgrade glab` (https://gitlab.com/gitlab-org/cli/-/raw/main/README.md, Homebrew section) |
| removal recipe and paths | drift | the manager's own remove (L1) is right, but installer/registry.toml:3169-3190 declares no config_paths while glab writes its config to ~/.config/glab-cli/config.yml on Linux and ~/Library/Application Support/glab-cli/config.yml on macOS, and stores plaintext credentials there when no keyring is used (https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/configuration.md, Configuration file locations; https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/authentication.md, Credential storage); the default config policy is not recorded (tool-onboarding step 4b) |
| tuning keys | n/a | reason: the entry declares no tuning keys and no post_install action |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- replace the Debian apt method with Homebrew on Linux, the vendor's officially supported method, or keep apt only where its package is current; risk: medium; evidence: https://gitlab.com/gitlab-org/cli/-/raw/main/docs/installation_options.md and https://sources.debian.org/api/src/glab/
- declare config_paths for glab (Linux ~/.config/glab-cli, macOS ~/Library/Application Support/glab-cli), keep as the default policy, and record the plaintext-credential fallback in `# Verified`; risk: low; evidence: https://gitlab.com/gitlab-org/cli/-/raw/main/docs/source/configuration.md

<!-- catalog-audit:complete -->
