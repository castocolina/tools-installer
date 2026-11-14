# puppeteer - catalog audit 2026-11-13

## Versions
- pinned: puppeteer ^25 (node versions param on the macos and linux amd64 node methods)
- verified: 2026-11-13
- installed: 25.16.0 (`puppeteer --version`)
- latest: 25.17.0 (npm dist-tag latest, https://registry.npmjs.org/-/package/puppeteer/dist-tags)
- latest: 25.17.0 (npm registry, https://registry.npmjs.org/puppeteer/latest)
- note: 25.17.0 stays inside the ^25 pin, so no method needs a version change; its engines node >=22.12.0 equals the entry's min_node

## Changelog
- 25.17.0 (2026-11-10) rolls Chrome to 157.0.8103.38 and bumps @puppeteer/browsers from 3.2.6 to 3.2.7; no install, update, removal, config or MCP note (https://github.com/puppeteer/puppeteer/blob/main/packages/puppeteer/CHANGELOG.md)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | installer/registry.toml:2815-2819 says @puppeteer/browsers still maps LINUX_ARM to linux64, which is why linux arm64 is gated off; @puppeteer/browsers 3.2.7 maps LINUX_ARM to linux-arm64 for Chrome builds from 153.0.8001.0 on (https://registry.npmjs.org/@puppeteer/browsers/-/browsers-3.2.7.tgz, package/lib/browser-data/chrome.js:13-17), and 25.17.0 ships Chrome 157; whether a linux-arm64 Chrome archive is published is unverified here. The macos node method has no gap found |
| update argv | ok | node method: the installer re-runs the method (tool-onboarding step 4b, node row: derives from the manager); the npm registry serves 25.17.0 as latest (https://registry.npmjs.org/puppeteer/latest) |
| removal recipe and paths | ok | L1 removes the npm package through the manager (tool-onboarding step 4b); the browser cache is not removed by it: the default cache is ~/.cache/puppeteer (package/src/getConfiguration.ts:162-165 in https://registry.npmjs.org/puppeteer/-/puppeteer-25.17.0.tgz), and the entry does not record it |
| tuning keys | n/a | reason: the entry declares no post_install action and no tuning keys (installer/registry.toml:2872, facts `post_install: none`) |
| postinstall hook | ok | the entry declares no installer postinstall hook; the vendor postinstall (scripts.postinstall `node install.mjs` in the 25.17.0 manifest, https://registry.npmjs.org/puppeteer/latest) downloads the browser and is covered by allow_build (installer/registry.toml:2890) and the smoke check. Its unzip dependency is real: package/lib/fileUtil.js:178 and :251 of @puppeteer/browsers 3.2.7 throw "no zip archiver" and call unzip, and the entry declares it (installer/registry.toml:2885) |

## Proposed changes
- when the linux amd64 gate is revisited, run a container check that starts a linux-arm64 Chrome before lifting arch = ["amd64"] (installer/registry.toml:2894-2902); risk: medium; evidence: https://registry.npmjs.org/@puppeteer/browsers/-/browsers-3.2.7.tgz (package/lib/browser-data/chrome.js:13-17)
- record ~/.cache/puppeteer as a leftover of the node method in the dated # Verified comment, since no removal path clears it; risk: low; evidence: https://registry.npmjs.org/puppeteer/-/puppeteer-25.17.0.tgz (package/src/getConfiguration.ts:162-165)

<!-- catalog-audit:complete -->
