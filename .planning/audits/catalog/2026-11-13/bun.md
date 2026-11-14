# bun - catalog audit 2026-11-13

## Versions
- pinned: none (unpinned, the script and brew methods take the current release)
- verified: 2026-11-04
- installed: 1.3.14 (`~/.bun/bin/bun --version`)
- latest: 1.4.4 (GitHub releases/latest, https://api.github.com/repos/oven-sh/bun/releases/latest, tag bun-v1.4.4, published 2026-10-22)
- latest: 1.4.4 (Homebrew formula stable, https://formulae.brew.sh/api/formula/bun.json)

## Changelog
- 1.4.0 to 1.4.4 release notes give the install command as `curl -fsSL https://bun.com/install | bash` (1.4.0, 1.4.4) or `https://bun.sh/install` (1.4.1 to 1.4.3); the two URLs serve a byte-identical script today (checked with cmp on both fetches), so the registry's `https://bun.sh/install` still installs the same script (https://github.com/oven-sh/bun/releases/tag/bun-v1.4.4)
- 1.4.0 to 1.4.4 notes give `bun upgrade` as the upgrade command, unchanged (https://github.com/oven-sh/bun/releases/tag/bun-v1.4.4)
- no other 1.4.x note touches install, update, removal, config or MCP

## Checks
| check | status | source |
|---|---|---|
| install method | ok | script method `https://bun.sh/install` (`installer/registry.toml:2187-2188`) is the vendor's curl install, the same script bun.com/install serves (https://bun.sh/docs/installation; release notes bun-v1.4.4); brew formula `bun` at `installer/registry.toml:2199` also current (1.4.4) |
| update argv | ok | `bun upgrade` (`installer/registry.toml:2197`) matches the vendor's upgrade command in https://github.com/oven-sh/bun/releases/tag/bun-v1.4.4 and https://bun.sh/docs/installation |
| removal recipe and paths | drift | the script appends a `# bun` PATH/BUN_INSTALL block to the user's shell config (`>>"$zsh_config"` at https://bun.sh/install:246; `>>"$bash_config"` at https://bun.sh/install:293, bash configs listed at lines 269-278), but `paths` declares only `~/.bun/bin/bun` and `~/.bun/bin/bunx` (`installer/registry.toml:2196`) and the `# Verified` comment (`installer/registry.toml:2191-2195`) does not record the rc edit, which the installer's rule requires for anything else a script creates; the vendor's own removal (https://bun.sh/docs/installation, "Uninstall") is `rm -rf ~/.bun`, which the entry deliberately does not run (its comment at `installer/registry.toml:2192` keeps the tree out of `paths`) |
| tuning keys | n/a | reason: the entry declares no tuning keys |
| postinstall hook | n/a | reason: the entry declares no postinstall hook; the rc block is written by the vendor script, not by a hook, and is covered by the removal row |

## Proposed changes
- record the vendor script's `# bun` rc block in the entry's `# Verified` comment and decide its removal (leave it, or remove that block by ownership); risk: medium; evidence: https://bun.sh/install:236-246

<!-- catalog-audit:complete -->
