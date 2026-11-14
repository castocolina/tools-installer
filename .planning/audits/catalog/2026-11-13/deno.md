# deno - catalog audit 2026-11-13

## Versions
- pinned: none (the github_release and brew methods are unpinned; each installs the latest release)
- verified: 2026-11-03
- installed: 2.9.7 (`deno --version`, from facts)
- latest: 2.9.8 (GitHub releases/latest, https://api.github.com/repos/denoland/deno/releases/latest, tag 2.9.8, published 2026-10-21)
- latest: 2.9.8 (Homebrew formula, https://formulae.brew.sh/api/formula/deno.json)

## Changelog
- 2.9.8 (only release after the installed 2.9.7) names no install, update, removal, config or MCP change; its fixes are runtime, npm, TLS and a zsh completion fix (https://api.github.com/repos/denoland/deno/releases/latest)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the release assets `deno-x86_64-unknown-linux-gnu.zip`, `deno-aarch64-unknown-linux-gnu.zip`, `deno-x86_64-apple-darwin.zip` and `deno-aarch64-apple-darwin.zip` each have a `.sha256sum` file in 2.9.8 (https://api.github.com/repos/denoland/deno/releases/latest); the docs list the same manual-download assets (https://docs.deno.com/runtime/getting_started/installation/, section "Manual download"); the registry's `{asset}.sha256sum` naming matches (installer/registry.toml:1862-1864) |
| update argv | ok | the docs say `deno upgrade` fetches the latest release and replaces the current executable (https://docs.deno.com/runtime/getting_started/installation/, section "Updating"); the github_release method declares no update argv, and the installer re-runs the method (facts) |
| removal recipe and paths | ok | github_release removal comes from the install receipt (L2), and the docs' manual-download install is one executable on PATH (https://docs.deno.com/runtime/getting_started/installation/, section "Manual download"); the `~/.deno` and `deno clean` steps in the docs apply only to the vendor shell-script install, which the registry does not use (section "Uninstalling") |
| tuning keys | n/a | reason: the entry declares no tuning key and no post_install action (installer/registry.toml:1850-1866 and the brew method) |
| postinstall hook | ok | the entry declares no postinstall hook; the docs' shell env-file step belongs to the vendor shell-script install (https://docs.deno.com/runtime/getting_started/installation/, section "Uninstalling") |

## Proposed changes
- none

<!-- catalog-audit:complete -->
