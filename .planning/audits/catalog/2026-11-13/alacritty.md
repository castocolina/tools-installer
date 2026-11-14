# alacritty - catalog audit 2026-11-13

## Versions
- pinned: unpinned (cargo_distrobox, dnf, apt, pacman)
- verified: 2026-11-08
- installed: none (`alacritty` is not installed on this host)
- latest: v0.17.0 (GitHub releases/latest, https://api.github.com/repos/alacritty/alacritty/releases/latest)
- latest: 0.17.0-2.fc45 (Fedora rawhide, https://mdapi.fedoraproject.org/rawhide/pkg/alacritty)
- latest: 0.17.0-1 (extra, https://archlinux.org/packages/search/json/?name=alacritty)
- latest: unknown: the answer is an error body: 404 (https://sources.debian.org/api/src/alacritty/)
- note: the Debian version is not established, so the apt method's version is unknown; the GitHub latest v0.17.0 has no Linux binary asset, so the source build is the only upstream Linux build

## Changelog
- 0.17.0 (GitHub publishes 2026-04-06) "Packaging: removed broken flash capability from terminfo", which changes the compiled ~/.terminfo entry the cargo_distrobox method builds from extra/alacritty.info (https://raw.githubusercontent.com/alacritty/alacritty/v0.17.0/CHANGELOG.md)
- 0.17.0 "Added: support TOML 1.1 syntax" adds parsing support only; the changelog records no key rename or removal in config (https://raw.githubusercontent.com/alacritty/alacritty/v0.17.0/CHANGELOG.md)
- 0.17.0 "Packaging: fixed invalid logo SVG attributes", which affects the artifact copied to ~/.local/share/icons (https://raw.githubusercontent.com/alacritty/alacritty/v0.17.0/CHANGELOG.md)

## Checks
| check | status | source |
|---|---|---|
| install method | ok | the vendor's INSTALL.md (v0.17.0) documents a source build with `cargo build --release` placing target/release/alacritty (https://raw.githubusercontent.com/alacritty/alacritty/v0.17.0/INSTALL.md, lines 253 and 267) and distro packages for Debian, Arch and Fedora; the v0.17.0 release assets hold no Linux binary (https://api.github.com/repos/alacritty/alacritty/releases/latest: Windows installers, Alacritty-v0.17.0.dmg, man pages, Alacritty.desktop); the cask is disabled since 2026-09-01 with reason fails_gatekeeper_check (https://formulae.brew.sh/api/cask/alacritty.json), so the entry correctly declares no cask |
| update argv | ok | none declared; the cargo_distrobox update path re-runs the build (installer/update.py:473-477), and the native methods are updated by their manager; the vendor's INSTALL.md describes a rebuild or the distro package update, with no separate update command |
| removal recipe and paths | ok | the cargo_distrobox artifacts are receipt-proven (L2): host paths ~/.local/bin/alacritty, ~/.local/share/applications/Alacritty.desktop, ~/.local/share/icons/hicolor/scalable/apps/Alacritty.svg and ~/.terminfo/a/alacritty(-direct) sit under the rule's allowed roots (installer/registry.toml:3089-3101, tool-onboarding step 4b). The box sources exist at v0.17.0: extra/linux/Alacritty.desktop, extra/logo/alacritty-term.svg, extra/alacritty.info (GitHub contents API at ref v0.17.0). The build tree is src/target/release/alacritty (installer/cargo_distrobox.py:124) and terminfo is compiled by tic from extra/alacritty.info (installer/cargo_distrobox.py:126-137). config_paths ~/.config/alacritty (installer/registry.toml:3086) is kept on removal by default |
| tuning keys | ok | apply_terminal_tuning writes [[keyboard.bindings]] for Alt+Left and Alt+Right (chars ESC b and ESC f) and Control+Shift+K with action ClearHistory (installer/terminal_shell.py:476-480 and :584-598). At v0.17.0 the table is keyboard.bindings (alacritty/src/config/ui_config.rs:90, `keyboard: Keyboard`), ClearHistory is an action (alacritty/src/config/bindings.rs:164), key names Left and Right map to the arrow keys (alacritty/src/config/bindings.rs:687-688), and the modifier list is Shift, Control, Super, Command, Alt, Option (alacritty/src/config/bindings.rs:1220). No v0.17.0 change renames these |
| postinstall hook | ok | the entry declares post_install = ["apply_terminal_tuning"] (installer/registry.toml:3087), a name in the closed table (installer/post_install.py:485). The tuning runs at install and is not a runtime question (tool-onboarding step 7) |

## Proposed changes
- none

<!-- catalog-audit:complete -->
