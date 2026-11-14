# mmdc - catalog audit 2026-11-13

## Versions
- pinned: puppeteer ^25 (node versions param of the node method; mmdc has no own version pin)
- verified: 2026-09-05
- installed: 12.2.0 (`mmdc --version`)
- latest: 12.2.0 (npm dist-tag latest, https://registry.npmjs.org/-/package/@mermaid-js%2Fmermaid-cli/dist-tags)
- latest: 12.2.0 (GitHub releases/latest, https://api.github.com/repos/mermaid-js/mermaid-cli/releases/latest)
- note: installed equals latest; the npm manifest of 12.2.0 declares engines node >=22.13.0 (https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0)

## Changelog
- none: installed 12.2.0 equals latest 12.2.0, so there is no version gap to read; the 12.2.0 release notes touch no install, update, removal, config or MCP step (https://api.github.com/repos/mermaid-js/mermaid-cli/releases/latest)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | installer/registry.toml:2765 sets min_node = "22.12.0" on the node method, but the npm manifest of @mermaid-js/mermaid-cli 12.2.0 declares engines node >=22.13.0 (https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0); the preflight at installer/executors.py:513-519 enforces the lower floor, so Node 22.12.x passes it |
| update argv | ok | the vendor's install command is `npm install -g @mermaid-js/mermaid-cli` (https://raw.githubusercontent.com/mermaid-js/mermaid-cli/master/README.md line 15); re-running the method is the update, as the entry declares |
| removal recipe and paths | ok | node method: removal derives from the manager (tool-onboarding step 4b); the 12.2.0 manifest declares package @mermaid-js/mermaid-cli with bin `mmdc` (https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0), so the package the manager removes is the one installed |
| tuning keys | n/a | reason: the entry declares no post_install action and no tuning keys (installer/registry.toml:2750, facts `post_install: none`) |
| postinstall hook | ok | the entry declares no installer postinstall hook, and the 12.2.0 manifest declares no install-time script (its scripts are lint, test, prepack, prepare, version, lint-fix, test:cli; https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0); the browser download belongs to puppeteer, see the puppeteer entry |

## Proposed changes
- raise the mmdc node method's min_node from 22.12.0 to 22.13.0 (installer/registry.toml:2765), so the preflight matches the package floor; risk: low; evidence: https://registry.npmjs.org/@mermaid-js/mermaid-cli/12.2.0

<!-- catalog-audit:complete -->
