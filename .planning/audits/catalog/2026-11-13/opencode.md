# opencode - catalog audit 2026-11-13

## Versions
- pinned: none (script, pacman and brew all install whatever the source serves)
- verified: 2026-11-04
- installed: v2.0.31 (`~/.opencode/bin/opencode --version`)
- latest: 2.3.0 (npm dist-tag latest of @opencode/cli, https://registry.npmjs.org/@opencode/cli)
- latest: 2.3.0 (opencode.ai update API, https://opencode.ai/update/api/latest/cli/npm)
- latest: 2.3.0 (homebrew/core formula opencode stable, https://formulae.brew.sh/api/formula/opencode.json)
- latest: 2.2.7-1 (Arch extra, https://archlinux.org/packages/search/json/?name=opencode; extra-testing carries 2.3.0)
- latest: 1.19.5 (GitHub releases/latest, https://api.github.com/repos/anomalyco/opencode/releases/latest; the sst/opencode URL redirects to the same repo)
- latest: 1.19.5 (brew tap formula anomalyco/tap/opencode, https://github.com/anomalyco/homebrew-tap/blob/main/opencode.rb, version "1.19.5"; the tap's opencode-v2.rb serves 2.3.0 and declares conflicts_with "opencode")
- latest: 1.19.5 (npm dist-tag latest of opencode-ai, the v1 package, https://registry.npmjs.org/opencode-ai)
- note: major split, GitHub's latest and the tap formula serve the 1.x line while npm @opencode/cli, homebrew/core and the update API serve 2.3.0; GitHub v2.3.0 is a published release (https://github.com/anomalyco/opencode/releases/tag/v2.3.0) that releases/latest skips; judged against 2.x

## Changelog
- the v1 installer refuses any 2.x and says it installs OpenCode 1 only; OpenCode 2 has its own installer at https://opencode.ai/v2/install (https://opencode.ai/install lines 70-75)
- OpenCode 1 `opencode upgrade` stays on 1 and prints "OpenCode 2 is available. Upgrade with `opencode upgrade --major`" (packages/opencode/src/cli/cmd/upgrade.ts lines 22, 79, 102, https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/cli/cmd/upgrade.ts)
- the v2 installer always writes an `opencode2` shim next to the binary in ~/.opencode/bin (https://opencode.ai/v2/install lines 345-374)
- the config schema marks the top-level `permission` key deprecated and adds `permissions` as an ordered rule array (https://opencode.ai/config.json)
- no install, update, removal, config or MCP note in the v2.2.7 or v2.3.0 release notes (https://github.com/anomalyco/opencode/releases/tag/v2.3.0, https://github.com/anomalyco/opencode/releases/tag/v2.2.7)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | `installer/registry.toml:1575` still installs through https://opencode.ai/install, which says "This installer only installs OpenCode 1" and refuses 2.x (https://opencode.ai/install lines 70-75); the v2 installer is https://opencode.ai/v2/install; the brew method `installer/registry.toml:1586` is the tap formula that serves 1.19.5 (https://github.com/anomalyco/homebrew-tap/blob/main/opencode.rb) while homebrew/core opencode serves 2.3.0 and has no conflicts (https://formulae.brew.sh/api/formula/opencode.json); pacman serves 2.2.7 and stays valid |
| update argv | drift | `installer/registry.toml:1580` runs `opencode upgrade`, which without `--major` stays on OpenCode 1 (https://github.com/anomalyco/opencode/blob/v1.19.5/packages/opencode/src/cli/cmd/upgrade.ts lines 22, 79, 102); re-running the v2 installer is the 2.x route; not run in a container here, the orchestrator owns containers |
| removal recipe and paths | drift | `installer/registry.toml:1579` declares only `~/.opencode/bin/opencode`, but the v2 installer also writes `~/.opencode/bin/opencode2` (https://opencode.ai/v2/install lines 345-374) and that file exists on this host; no `remove` recipe, so a 2.x install leaves the opencode2 shim and a running `opencode serve --service` behind |
| tuning keys | drift | `installer/agent_settings.py:679` writes `("opencode", "auto-approve")` to the key path `permission`, which the schema marks `deprecated: true` while `permissions` takes a rule array with `action`, `resource` and `effect` (https://opencode.ai/config.json) |
| postinstall hook | n/a | reason: the entry declares no postinstall command; its only hook `post_install = ["apply_agent_tuning"]` (`installer/registry.toml:1561`) is the tuning write judged in the tuning keys row |

## Proposed changes
- switch the script method to https://opencode.ai/v2/install with `paths` listing both `~/.opencode/bin/opencode` and `~/.opencode/bin/opencode2`, and drop `update` so an update re-runs the v2 installer; risk: medium; evidence: https://opencode.ai/v2/install lines 345-374
- add a removal recipe that stops the background service before the binary goes; risk: medium; evidence: https://opencode.ai/v2/install lines 345-374 (opencode2 shim) and the v2 service CLI
- move the brew method from the tap formula anomalyco/tap/opencode to homebrew/core opencode; risk: low; evidence: https://formulae.brew.sh/api/formula/opencode.json
- write `permissions` for auto-approve and keep `permission` as a revert-only retired key; risk: medium; evidence: https://opencode.ai/config.json
- add an npm-based latest source for the script method (GitHub's latest is the 1.x line); risk: low; evidence: https://registry.npmjs.org/@opencode/cli

<!-- catalog-audit:complete -->
