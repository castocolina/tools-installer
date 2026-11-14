# uv - catalog audit 2026-11-12

## Versions
- pinned: none (the entry installs whatever the vendor serves)
- verified: 2026-11-01
- installed: 0.9.1 (`uv --version`)
- latest: 0.9.1 (GitHub releases/latest, https://api.github.com/repos/example/uv/releases/latest)

## Changelog
- no install, update, removal, config or MCP note between 0.9.1 and 0.9.1

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's install page still recommends it, https://example.com/uv/install |
| update argv | ok | the vendor's upgrade page documents the declared argv, https://example.com/uv/upgrade |
| removal recipe and paths | ok | the vendor's uninstall page lists the declared paths, https://example.com/uv/uninstall |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook |

## Proposed changes
- none
<!-- catalog-audit:complete -->
