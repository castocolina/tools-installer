# codegraph - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned github_release, the method resolves the latest release tag)
- verified: 2026-11-03
- installed: 1.6.2 (`codegraph --version`)
- latest: v1.6.2 (GitHub releases/latest, https://api.github.com/repos/colbymchenry/codegraph/releases/latest, published 2026-10-03)
- latest: 1.6.2 (package.json on main, https://github.com/colbymchenry/codegraph/blob/main/package.json)
- note: no split; main is ahead of the release (newest commit 2026-11-01) and its CHANGELOG [Unreleased] section lists nine new `codegraph install` targets including Pi, none of them in v1.6.2

## Changelog
- installed equals latest, so no install, update, removal, config or MCP note lies between 1.6.2 and 1.6.2
- [Unreleased] on main adds `codegraph install` targets for Bob, Droid, Windsurf, Qwen, dsh, Grok, Kimi, Qoder and Pi (Pi writes ~/.pi/agent/mcp.json with exposure direct plus an AGENTS.md block); unreleased, so `--print-config pi` fails on 1.6.2 (https://github.com/colbymchenry/codegraph/blob/main/CHANGELOG.md, https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/pi.ts)
- v1.6.2 supports target copilot-cli, writing only ~/.copilot/mcp-config.json and honouring COPILOT_HOME (https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/copilot-cli.ts)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's install.sh downloads the same release tarball the registry installs, https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh (line 72); v1.6.2 ships darwin and linux assets for x64 and arm64 and the registry rows cover macos, debian, arch and fedora (`installer/registry.toml:1786`), all four listed as Passed in `.planning/audits/catalog/2026-11-13/verify-registry.md:79` |
| update argv | ok | none declared, the installer re-runs the github_release method (`installer/registry.toml:1786`); the vendor route `codegraph upgrade` (https://github.com/colbymchenry/codegraph#install) re-runs install.sh into ~/.codegraph/versions, an alternative layout the registry comment at `installer/registry.toml:1767` already records |
| removal recipe and paths | drift | `installer/registry.toml:1756` declares no tool-level `config_paths` although codegraph keeps its data in ~/.codegraph (telemetry.json, beta-signup.json, daemons/, and versions/ plus current after `codegraph upgrade`, https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh lines 21 and 79-87); the unregister hook runs `codegraph uninstall --keep-cli` (`installer/postinstall.py:204`) and the receipt proves only the installer's own link and opt dir, so after a vendor self-upgrade `installer/uninstall.py:402` finds no proven executable and unregisters nothing |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | drift | `installer/postinstall.py:161` `_CODEGRAPH_TARGETS` maps claude, codex, opencode and cursor only; codegraph v1.6.2 also supports `copilot-cli` (`codegraph install --print-config copilot-cli` exits 0 and shows ~/.copilot/mcp-config.json), and the installer already knows the copilot and pi hosts (`installer/postinstall.py:46`); Pi is only on codegraph main and unreleased (`codegraph install --print-config pi` exits 1 with Unknown target "pi", Known: claude, cursor, codex, opencode, hermes, gemini, antigravity, kiro, copilot-vscode, copilot-cli, copilot-jetbrains), so a Pi mapping needs a capability gate first |

## Proposed changes
- add `"copilot": "copilot-cli"` to `_CODEGRAPH_TARGETS` in `installer/postinstall.py:161` (the CSV order test in `tests/test_postinstall.py` pins the current four ids); risk: low; evidence: `codegraph install --print-config copilot-cli` exits 0 on v1.6.2, https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/copilot-cli.ts
- add `"pi": "pi"` only behind a per-target capability probe (`codegraph install --print-config pi` must exit 0), because an unknown target aborts the whole CSV and so the claude, codex, opencode and cursor registrations in the same call; risk: medium; evidence: `codegraph install --print-config pi` exits 1 on v1.6.2, https://github.com/colbymchenry/codegraph/blob/main/src/installer/targets/pi.ts
- declare ~/.codegraph as a tool-level `config_paths` entry for codegraph with an explicit keep or delete policy, and cover a vendor self-upgrade in removal; risk: medium; evidence: https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh

<!-- catalog-audit:complete -->
