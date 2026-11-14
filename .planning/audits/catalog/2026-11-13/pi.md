# pi - catalog audit 2026-11-13

## Versions
- pinned: none (the host_setup method is unpinned and hands off a `pnpm add -g` command)
- verified: 2026-11-04
- installed: 1.3.0 (`pi --version` through facts, ~/.bun/bin/pi: a bun global install)
- latest: 1.5.2 (npm dist-tag latest, https://registry.npmjs.org/@earendil-works/pi-coding-agent)
- latest: 1.5.2 (GitHub releases/latest, https://api.github.com/repos/earendil-works/pi/releases/latest, published 2026-11-10)
- note: npm also carries the legacy-node20 dist-tag at 0.74.2; it is not a newer major and does not affect the judgment

## Changelog
- 1.5.0 adds custom self-update commands (`PI_SELF_UPDATE_COMMAND`, `selfUpdateCommand`) and `pi update` lists each updated package; `pi update` no longer passes `--min-release-age=0` to `npm ci` for installer installs (https://github.com/earendil-works/pi/blob/main/packages/coding-agent/CHANGELOG.md, section 1.5.0)
- 1.5.0 fixes `pi update` naming pnpm for installs that only live under `PNPM_HOME`; it now names a manager only when that manager owns the install (https://github.com/earendil-works/pi/blob/main/packages/coding-agent/CHANGELOG.md, section 1.5.0)
- 1.4.0 and 1.5.x fix `pi update` on managed installs (UTF-8 BOM in managed-install.json, Windows Node on PATH) and `mcp.json` files that start with a UTF-8 BOM (https://github.com/earendil-works/pi/blob/main/packages/coding-agent/CHANGELOG.md, sections 1.4.0 and 1.5.2)
- MCP is a built-in extension since 0.99.0 (2026-09-29): `pi mcp add|remove|list|login|logout` reads `~/.pi/agent/mcp.json` and, in trusted projects, `.pi/mcp.json`; 1.2.0 to 1.5.2 add OAuth, exposure and stdio fixes (https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md)
- README now leads with `curl -fsSL https://pi.dev/install.sh | sh` ("pins all dependencies and updates Pi with `pi update`") and lists `npm install -g --ignore-scripts @earendil-works/pi-coding-agent` as the alternative; pnpm and bun installs are not documented as install routes (https://github.com/earendil-works/pi#getting-started)

## Checks
| check | status | source |
|---|---|---|
| install method | drift | `installer/registry.toml:3201` and `installer/registry.toml:3204` describe a pnpm host-setup handoff verified against "latest 1.5.0" and an "interactive" setup, while the vendor README now recommends `curl -fsSL https://pi.dev/install.sh \| sh` (managed install, pinned dependencies, `pi update`) or `npm install -g --ignore-scripts`, and npm latest is 1.5.2, https://github.com/earendil-works/pi#getting-started |
| update argv | ok | the registry declares no `update`; the installer re-runs `pnpm add -g --ignore-scripts @earendil-works/pi-coding-agent` (`installer/host_setup.py:31`, `installer/update.py:258`), and Pi's own `pi update` runs the same package install for a pnpm global (`pnpm install -g --ignore-scripts --config.minimumReleaseAge=0 <spec>`, https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/config.ts), see the host caveat in Proposed changes |
| removal recipe and paths | drift | `installer/registry.toml:3194` to `installer/registry.toml:3210` declare no `config_paths` for `~/.pi` (agent settings, `auth.json`, `sessions`, `mcp.json` live there, https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md) and no remove recipe, and the host_setup row of tool-onboarding step 4b asks for an explicit recipe; removal on this host (bun global) is also not derivable because `installer/ownership.py:135` maps only `pnpm` |
| tuning keys | n/a | reason: the entry declares no tuning keys and no `post_install`; Pi has no install-time key to set |
| postinstall hook | n/a | reason: the entry declares no postinstall hook; codegraph's Pi registration is codegraph's own hook and the `pi` target is not released (codegraph 1.6.2 `install --print-config pi` prints `Unknown target "pi"`) |

## Proposed changes
- refresh the Pi `desc`, `verified` and `# Verified` text at `installer/registry.toml:3201-3205`: latest is 1.5.2, the vendor now recommends the pi.dev installer or npm, `pi update` is the vendor update route, and Pi has built-in MCP; risk: low; evidence: https://github.com/earendil-works/pi#getting-started
- keep the method change in Backlog 999.13 (do not adopt `pi.dev/install.sh` as is: it is 1853 lines and `sudo` appears 15 times, run_with_sudo for Node, npm and xz-utils installs on Debian and Alpine and printed `sudo npm` hints, https://pi.dev/install.sh read as data only); risk: medium; evidence: `.planning/ROADMAP.md:905`
- declare Pi's `~/.pi` as a tool-level `config_paths` entry with a keep policy and state why in `# Verified`; risk: low; evidence: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md
- decide how the catalog treats a bun global Pi (this host, `~/.bun/install/global/node_modules/@earendil-works/pi-coding-agent`): `Owner` has no bun value (`installer/ownership.py:80`), so the installer sees it as unknown-owner and refuses update and removal, while `pi update` itself detects it and runs `bun install -g --ignore-scripts --minimum-release-age=0 <spec>`; risk: medium; evidence: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/config.ts
- add a Node 22.19 floor note: Pi requires Node.js >=22.19.0 (packages/coding-agent/package.json engines) and the entry's `requires` lists only pnpm; whether the installer enforces Node elsewhere is unverified; risk: low; evidence: https://registry.npmjs.org/@earendil-works/pi-coding-agent
- when codegraph releases a `pi` target, add `pi` to `_CODEGRAPH_TARGETS` behind the capability probe only; today `installer/postinstall.py:161` correctly omits it; risk: low; evidence: https://github.com/colbymchenry/codegraph/tree/main/src/installer/targets

<!-- catalog-audit:complete -->
