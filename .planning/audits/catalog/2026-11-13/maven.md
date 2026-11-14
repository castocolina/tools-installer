# maven - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned, the sdkman method installs the candidate's current version)
- verified: 2026-10-13
- installed: 3.10.0 (`mvn --version`)
- latest: 3.10.0 (GitHub releases/latest, https://api.github.com/repos/apache/maven/releases/latest)
- note: the newest listed release is 4.0.0-rc-7, a prerelease (GitHub releases list, https://api.github.com/repos/apache/maven/releases); judged against the stable 3.10.0

## Changelog
- no install, update, removal, config or MCP note between 3.10.0 and 3.10.0

## Checks
| check | status | source |
|---|---|---|
| install method | ok | sdkman candidate `maven` at `installer/registry.toml:2083`; the vendor lists SDKMAN! as an install route, https://maven.apache.org/install.html |
| update argv | unknown | reason: container check not run (no container in this batch); the entry declares no update argv and the installer re-runs the method |
| removal recipe and paths | ok | the sdkman manager removes the candidate (`sdk uninstall <candidate> <version>`, https://sdkman.io/usage); the entry declares no paths, `installer/registry.toml:2083` |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- none

<!-- catalog-audit:complete -->
