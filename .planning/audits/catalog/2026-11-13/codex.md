# codex - catalog audit 2026-11-13

## Versions
- pinned: none (script and cask methods are unpinned)
- verified: 2026-11-04
- installed: 0.162.1 (`~/.codex/packages/standalone/current/bin/codex --version`, via `facts codex`)
- latest: 0.169.0 (Homebrew cask API, https://formulae.brew.sh/api/cask/codex.json)
- latest: rust-v0.169.0 (GitHub releases/latest, https://api.github.com/repos/openai/codex/releases/latest)
- note: the installed 0.162.1 lags latest by seven minors; the standalone CLI self-updates, so the lag is not registry drift

## Changelog
- 0.163.0 stops bundling a patched zsh and shows a migration notice for the retired shell flags (release notes, https://github.com/openai/codex/releases/tag/rust-v0.163.0)
- 0.166.0 fixes standalone release cleanup on macOS when installations are in use (release notes, https://github.com/openai/codex/releases/tag/rust-v0.166.0)
- 0.169.0 keeps project configuration and MCP servers disabled for `codex exec` in untrusted directories (release notes, https://github.com/openai/codex/releases/tag/rust-v0.169.0)
- the CLI reference now documents `codex update` as a Stable command (https://developers.openai.com/codex/cli/reference); the installer comment still says the docs name none

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor docs recommend the standalone installer on macOS and Linux, https://developers.openai.com/codex/cli, and `installer/registry.toml:1484` declares exactly that script plus a macOS cask; the script still writes under `$CODEX_HOME/packages/standalone`, https://chatgpt.com/codex/install.sh lines 24-25 |
| update argv | drift | `installer/registry.toml:1493` says the docs name no `codex update`, but https://developers.openai.com/codex/cli/reference lists `codex update` (Stable, applies an update when the release supports self-update) and the CLI source has an `Update` subcommand, https://github.com/openai/codex/blob/main/codex-rs/cli/src/main.rs |
| removal recipe and paths | ok | the declared paths match the script: releases and current at lines 24-25, launcher `~/.local/bin/codex` at line 1232 and the darwin-only `codex-code-mode-host` link at lines 1234-1241 of https://chatgpt.com/codex/install.sh; its only uninstall commands target another manager's copy (lines 1092-1098) |
| tuning keys | ok | `installer/agent_settings.py:676` writes `approval_policy = never` and `installer/agent_settings.py:677` writes `sandbox_mode = danger-full-access`; the current schema lists both keys, none deprecated, `never` and `danger-full-access` are valid enum values, https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/config.schema.json |
| postinstall hook | ok | the entry has no hook of its own; the shared codegraph hook maps `codex` at `installer/postinstall.py:163`, and codegraph v1.6.2 `--target codex` merges `[mcp_servers.codegraph]` into `~/.codex/config.toml`, https://raw.githubusercontent.com/colbymchenry/codegraph/v1.6.2/src/installer/targets/codex.ts, matching the schema's `mcp_servers` table |

## Proposed changes
- declare `update = ["codex", "update"]` on the script method and drop the "no `codex update`" comment; risk: low; evidence: https://developers.openai.com/codex/cli/reference

<!-- catalog-audit:complete -->
