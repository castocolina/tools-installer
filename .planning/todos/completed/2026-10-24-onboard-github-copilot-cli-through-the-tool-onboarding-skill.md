---
created: 2026-10-25T02:05:21.301Z
title: Onboard GitHub Copilot CLI through the tool-onboarding skill
area: catalog
severity: minor
files:
  - .claude/skills/tool-onboarding/SKILL.md
  - installer/registry.toml
---

## Problem

The user wants a registry entry that installs the GitHub Copilot CLI (`copilot`).
`installer/registry.toml` already names `copilot` as a supported harness and
carries `copilot plugin ...` commands for the ponytail and superpowers plugins,
but there is no `[[tool]]` entry that installs the CLI itself, unlike the
neighbouring agent CLIs (`codex`, `claude`, `opencode`, `cursor-agent`). The user
installed it by hand on the host (`brew install --cask copilot-cli`).

The user explicitly confirmed **minor** severity: a catalog addition, captured
for later rather than onboarded now.

## Solution

Run `.claude/skills/tool-onboarding/SKILL.md` end to end for Copilot CLI when this
todo is selected. Source: https://docs.github.com/en/copilot/get-started/cli-quickstart#installation
(fetched 2026-10-24). Official methods:

- Homebrew (macOS/Linux): `brew install --cask copilot-cli`
- npm (cross-platform, needs Node.js 22+): `npm install -g @github/copilot`
- WinGet (Windows only, out of scope)

Model the entry on the existing agent-CLI entries (`codex`, `claude`,
`opencode`) for method choice, ownership, detection, removal and pin/verify
behaviour. Upstream the cask is not macOS-only: on 2026-10-24 `brew info --cask
copilot-cli` showed 1.0.103 (auto_updates), no `depends_on`, a `copilot-
linux-x64.tar.gz` URL on Linux, and a `copilot` binary plus generated shell
completions. The installer's resolver still treats casks as macOS-only
(`test_cask_requires_macos_and_brew`), so decide whether Linux uses the cask (a
resolver change) or npm. Also check how the npm path interacts with the
pnpm/node-globals handling. The binary is `copilot`. Use a non-authenticated
smoke check such as `copilot --version`. Authentication is interactive
(`copilot`, then `/login`) and stays out of scope. Wire the plugin entries'
`copilot` harness to the new tool if the onboarding skill's dependency checks
call for it. Real install/removal verification runs only in disposable
containers.
