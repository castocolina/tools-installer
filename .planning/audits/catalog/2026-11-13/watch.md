# watch - catalog audit 2026-11-13

## Versions
- pinned: none (dnf, apt, pacman and brew entries are unpinned)
- verified: 2026-10-13
- installed: 4.0.6 (`watch --version`, per the facts probe)
- latest: 4.0.7 (Homebrew formula, https://formulae.brew.sh/api/formula/watch.json)
- latest: 4.0.7 (upstream NEWS section procps-ng-4.0.7, https://gitlab.com/procps-ng/procps/-/raw/master/NEWS)
- latest: 4.0.7-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/procps-ng)
- latest: 2:4.0.7-1.1 (Debian source, https://sources.debian.org/api/src/procps/)
- latest: 4.0.7-1 (Arch core, https://archlinux.org/packages/search/json/?name=procps-ng)
- note: the distro lines are package revisions of the same upstream 4.0.7; the installed 4.0.6 is the host's package, updated by re-running its method

## Changelog
- procps-ng-4.0.7 watch notes (NEWS lines 17-35) cover resizing, the -t line count and the LINES and COLUMNS variables; none touches install, update, removal, config or MCP

## Checks
| check | status | source |
|---|---|---|
| install method | ok | dnf `procps-ng`, apt `procps`, pacman `procps-ng` and brew `watch` cover every platform and architecture the entry declares (`installer/registry.toml:1045-1056`); the brew formula's homepage is the upstream project, https://formulae.brew.sh/api/formula/watch.json |
| update argv | ok | no vendor update command; the upgrade is re-running the package manager's method (`installer/registry.toml:1034-1056`), which is the update the entry declares |
| removal recipe and paths | ok | L1 is the manager's own remove on the same package name (`installer/registry.toml:1045-1056`); the package also ships ps, top and pkill, so that removal takes them too (NEWS lines 17-35 list them in procps-ng) |
| tuning keys | n/a | reason: the entry declares no tuning keys, so no vendor key can be deprecated or renamed |
| postinstall hook | ok | the entry declares no postinstall (`installer/registry.toml:1034-1056`); the Docker shortcuts bundle that needs watch records the edge itself (`installer/tweaks.py:128-132`) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
