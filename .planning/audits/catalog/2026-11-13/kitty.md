# kitty - catalog audit 2026-11-13

## Versions
- pinned: unpinned (script, dnf, apt, pacman, cask)
- verified: 2026-11-04
- installed: 0.49.2 (`~/.local/kitty.app/bin/kitty --version`)
- latest: 0.50.0 (GitHub releases/latest, https://api.github.com/repos/kovidgoyal/kitty/releases/latest)
- latest: 0.50.0 (brew cask, https://formulae.brew.sh/api/cask/kitty.json)
- latest: 0.48.2-1.fc46 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/kitty)
- latest: 0.48.2-1.1 (https://sources.debian.org/api/src/kitty/)
- latest: 0.50.0-1 (extra, https://archlinux.org/packages/search/json/?name=kitty)
- note: the vendor script fetches the current release (installer.sh resolves https://sw.kovidgoyal.net/kitty/current-version.txt), so the script methods track 0.50.0; the native dnf, apt and pacman packages lag behind it

## Changelog
- 0.50.0 adds the config options restore_session_after_logout, collapse_window_margins and hyperlink_target_position to kitty.conf; the grep of the 0.50.0 and 0.49.x sections found no config key renamed or removed (https://github.com/kovidgoyal/kitty/blob/master/docs/changelog.rst, section 0.50.0)
- no install, update or removal note in the 0.50.0 section; the 0.50.1 unreleased section touches no install step (same file)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's documented path is the installer.sh download-and-run command (https://sw.kovidgoyal.net/kitty/installer.sh) on macOS and Linux (https://sw.kovidgoyal.net/kitty/binary/); installer.sh detects Linux x86_64 and aarch64 (installer.sh:49-50), so arch = all fits the script methods; the macOS cask and native packages are vendor-listed alternatives |
| update argv | ok | the vendor says "To update kitty, simply re-run the command" (https://sw.kovidgoyal.net/kitty/binary/); the entry declares update none, and the installer re-runs the method |
| removal recipe and paths | drift | the Linux script method is ok: paths ~/.local/kitty.app/ (installer/registry.toml:2961) matches the vendor's "simply delete that directory" (https://sw.kovidgoyal.net/kitty/binary/). The macOS script method declares no paths (installer/registry.toml:2971) because the schema refuses absolute paths (installer/model.py:577-585), so the installer has no removal for /Applications/kitty.app that the vendor's own uninstall covers. This is a schema gap to record in the backlog, not an entry fix |
| tuning keys | n/a | reason: the entry declares no post_install action and no tuning keys (installer/registry.toml:2939, facts `tuning: none`); the kitty.conf shell and env lines are written by the terminal-shell synchronizer, not install tuning (installer/terminal_shell.py:949-958) |
| postinstall hook | n/a | reason: the entry declares no postinstall hook (facts `post_install: none`) and the decision tree yields none |

## Proposed changes
- record the macOS script removal gap in the backlog: the installer cannot remove /Applications/kitty.app until the script paths schema accepts an absolute, system-owned path; risk: medium; evidence: installer/model.py:577-585 and https://sw.kovidgoyal.net/kitty/binary/

<!-- catalog-audit:complete -->
