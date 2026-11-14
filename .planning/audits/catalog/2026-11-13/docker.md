# docker - catalog audit 2026-11-13

## Versions
- pinned: none (dnf, apt, pacman and brew entries are unpinned)
- verified: 2026-10-13
- installed: not installed (`docker` not on the probed PATH, per the facts probe)
- latest: 29.9.3 (Homebrew formula, https://formulae.brew.sh/api/formula/docker.json)
- latest: 29.9.3 (upstream tag v29.9.3, https://github.com/docker/cli/tree/v29.9.3)
- latest: 29.9.3-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/docker-cli)
- latest: 28.5.2+dfsg4-5 (Debian source, https://sources.debian.org/api/src/docker.io/)
- latest: 29.9.3-1 (Arch extra, https://archlinux.org/packages/search/json/?name=docker)
- note: the Debian docker.io candidate is one major behind the upstream 29.9.3 tag; the upstream repo has no GitHub release object (gh api repos/docker/cli/releases/latest returns 404), so the tag is the source

## Changelog
- unknown: there is no installed version to diff from, and docker/cli publishes tags without release notes, so no install, update, removal, config or MCP note could be read for the range

## Checks
| check | status | source |
|---|---|---|
| install method | drift | Docker's Ubuntu install page lists `docker.io` among the "unofficial packages to uninstall" before installing the official Engine, and its recommended method is the Docker apt repository, https://docs.docker.com/engine/install/ubuntu/ ("Uninstall old versions", "Installation methods"); the entry's apt method is `docker.io` at `installer/registry.toml:1074-1075` |
| update argv | drift | the upgrade path on that page is the Docker apt repository ("Upgrade Docker Engine"), not the `docker.io` package the entry re-runs, https://docs.docker.com/engine/install/ubuntu/ |
| removal recipe and paths | drift | Docker's Ubuntu uninstall section says images, containers, volumes and networks in /var/lib/docker/ are not removed automatically, https://docs.docker.com/engine/install/ubuntu/ ("Uninstall Docker Engine"); the entry declares no paths, and the client config `~/.docker/config.json` is not declared either (docker/cli `cli/config/config.go:27-28`) |
| tuning keys | n/a | reason: the entry declares no tuning keys, so no vendor key can be deprecated or renamed |
| postinstall hook | drift | the Homebrew formula's Linux caveat says the daemon is a separate formula, `brew install docker-engine` (homebrew-core Formula/d/docker.rb, caveats), and the entry's CLI is not a daemon; the entry has no `requires` edge and no `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1059-1081`) |

## Proposed changes
- move the Debian and Ubuntu apt method to the Docker apt repository, or record in `# Verified` why the distro package is kept; risk: medium; evidence: https://docs.docker.com/engine/install/ubuntu/
- declare the data path `/var/lib/docker` and the client config `~/.docker` as removal-policy paths, with the keep default; risk: medium; evidence: https://docs.docker.com/engine/install/ubuntu/ and `cli/config/config.go:27-28` in https://github.com/docker/cli
- add a `# Verified` note for the daemon expectation, or an edge, as chosen for lazydocker; risk: low; evidence: https://formulae.brew.sh/api/formula/docker.json

<!-- catalog-audit:complete -->
