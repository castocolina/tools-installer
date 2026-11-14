# podman - catalog audit 2026-11-13

## Versions
- pinned: none (dnf, apt, pacman and brew entries are unpinned)
- verified: 2026-10-13
- installed: 6.1.3 (`podman --version`, per the facts probe)
- latest: v6.2.0 (GitHub releases/latest, published 2026-11-10, https://api.github.com/repos/containers/podman/releases/latest)
- latest: 6.2.0 (Homebrew formula, https://formulae.brew.sh/api/formula/podman.json)
- latest: 6.2.0-1 (Arch extra, https://archlinux.org/packages/search/json/?name=podman)
- latest: 6.2.0~rc1-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/podman; a release candidate, not the stable tag)
- latest: 6.1.1+ds1-1 (Debian source, https://sources.debian.org/api/src/podman/)
- note: GitHub also lists v5.8.10 (published 2026-11-10) on the older major line; the newest major is 6.2.0

## Changelog
- v6.2.0 (https://github.com/containers/podman/releases/tag/v6.2.0): "All Quadlet files now support a new key, `SetMountsDependency`" (config)
- v6.1.4 (https://github.com/containers/podman/releases/tag/v6.1.4): dependency bumps only (gvproxy, Buildah, Storage); no install, update, removal or config note

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the vendor's install page says the Homebrew route is "Not recommended" because it is community-maintained, and points macOS users to the GitHub release pkg installer, https://podman.io/docs/installation ("Installing on Mac & Windows"); the entry's macOS arm64 method is brew (`installer/registry.toml:1105-1107`) and it has no pkg or release method for macOS. The Linux rows follow the page's per-distro package commands ("Installing on Linux") |
| update argv | drift | for macOS the same page's recommended route is the pkg installer, so re-running the brew method is the path the vendor does not recommend (https://podman.io/docs/installation); the Linux package-manager upgrade is unchanged |
| removal recipe and paths | unknown | reason: the vendor install page has no uninstall section, and the machine and config data directories were not read from upstream; container check not run (no vendor uninstall command to test, and the data-path question needs the vendor's machine docs) |
| tuning keys | n/a | reason: the entry declares no tuning keys, so no vendor key can be deprecated or renamed |
| postinstall hook | drift | the vendor page's macOS setup creates a machine with `podman machine init` and `podman machine start` (https://podman.io/docs/installation, "Installing on Mac & Windows"); the entry declares no postinstall, `requires`, or `# Verified` note for that runtime expectation, which tool-onboarding step 6 requires (`installer/registry.toml:1084-1111`) |

## Proposed changes
- add a macOS pkg or GitHub release method ahead of brew, or record in `# Verified` why brew stays; risk: medium; evidence: https://podman.io/docs/installation
- record the podman machine runtime expectation in `# Verified`, and confirm the machine data directories before declaring any path; risk: low; evidence: https://podman.io/docs/installation

<!-- catalog-audit:complete -->
