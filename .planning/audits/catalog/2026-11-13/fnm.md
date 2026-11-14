# fnm - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script, brew)
- verified: 2026-11-04
- installed: 1.39.0 (~/.local/share/fnm/fnm --version, facts block)
- latest: 1.39.0 (GitHub releases/latest, https://api.github.com/repos/Schniz/fnm/releases/latest, v1.39.0 published 2026-03-06)
- latest: 1.39.0 (brew formula, https://formulae.brew.sh/api/formula/fnm.json)

## Changelog
- no install, update, removal, config or MCP note between 1.39.0 and 1.39.0 (https://github.com/Schniz/fnm/releases/tag/v1.39.0 covers shell hooks, `fnm install --use` and `fnm default` only)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | https://fnm.vercel.app/install sets the Linux INSTALL_DIR at lines 13-19 and is the script route; the README (https://raw.githubusercontent.com/Schniz/fnm/master/README.md lines 59 and 69-72) deprecates the macOS script in favour of brew, which the entry follows through installer/registry.toml:2323-2344 |
| update argv | ok | https://raw.githubusercontent.com/Schniz/fnm/master/README.md lines 35-42: upgrading is re-running the install with --skip-shell, which the entry passes as args at installer/registry.toml:2328; the entry declares no update, which matches |
| removal recipe and paths | ok | https://fnm.vercel.app/install lines 111-117 move the binary to INSTALL_DIR/fnm, the leaf declared at installer/registry.toml:2341; node versions are kept on purpose (installer/registry.toml:2337-2340); the README names no uninstall step |
| tuning keys | n/a | reason: the entry declares no tuning keys; its only post_install action is source_shell_init (installer/registry.toml:2316) |
| postinstall hook | ok | no Tool.postinstall is declared (installer/registry.toml:2312-2345); the shell-init step is a post_install action, the first branch of "Postinstall-per-harness classification" at .claude/architecture.md:308 |

## Proposed changes
- none

<!-- catalog-audit:complete -->
