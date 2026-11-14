# xh - catalog audit 2026-11-13

## Versions
- pinned: unpinned (github_release and brew)
- verified: 2026-11-03
- installed: none (`xh` is not installed on this host, facts: not installed)
- latest: v0.26.3 (GitHub releases/latest, https://api.github.com/repos/ducaale/xh/releases/latest, read with `gh api`, published 2026-10-21)
- latest: 0.26.3 (Homebrew formula, https://formulae.brew.sh/api/formula/xh.json)

## Changelog
- v0.26.3 notes (https://github.com/ducaale/xh/releases/tag/v0.26.3) cover a rustls and webpki-root-certs security bump and incomplete-download detection; no install, update, removal, config or MCP note
- no release after the verified date 2026-11-03 (the newest release is 2026-10-21), so no other note applies

## Checks
| check | status | source |
|---|---|---|
| install method | drift | the upstream README install table lists `pacman -S xh` for Arch and `sudo apt install xh` for Debian and Ubuntu (https://github.com/ducaale/xh#installation), both distro packages that step 4 ranks above the release asset, while `installer/registry.toml:922` installs the release asset on debian, arch and fedora; the Fedora row is a third-party COPR repo, so the release asset stays there; package currency on Arch and Debian is unverified (no pacman or apt query run); the macOS and brew rows match the README's Homebrew line |
| update argv | ok | the entry declares no update argv; brew updates through the formula (`formula "xh"` at 0.26.3, https://formulae.brew.sh/api/formula/xh.json); the release-asset path re-runs the method (facts: `update: none`) |
| removal recipe and paths | drift | the entry declares no `config_paths` (`installer/registry.toml:912-938`), but `xh --session` writes session files under `config_dir()/sessions` (`src/session.rs:171-173`, https://raw.githubusercontent.com/ducaale/xh/master/src/session.rs), and `config_dir()` resolves to `~/.config/xh` on Linux and to a legacy or XDG path on macOS (`src/utils.rs:77-89`, https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs); the session format holds auth fields (`src/session.rs:410`), so the default config policy must be stated |
| tuning keys | n/a | reason: the entry declares no tuning keys and xh's settings are per-run flags and the `XH_CONFIG_DIR` environment variable (https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs:77-80), which the installer does not write |
| postinstall hook | ok | `installer/registry.toml:912` xh block has no `postinstall`, `post_install`, `remove` or `update` key, so the decision tree lands on none |

## Proposed changes
- declare `config_paths` for xh (`~/.config/xh` on Linux, with the macOS path checked) and state the default config policy `keep` or `ask`, so a delete choice reaches the session files; risk: medium; evidence: https://raw.githubusercontent.com/ducaale/xh/master/src/utils.rs
- move the arch and debian methods to `pacman -S xh` and `sudo apt install xh` once their current version is checked; risk: low; evidence: https://github.com/ducaale/xh#installation

<!-- catalog-audit:complete -->
