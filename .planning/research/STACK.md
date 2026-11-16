# Technology Stack: v0.51.0 "Onboard terminal tools"

**Project:** tools-installer (milestone v0.51.0)
**Researched:** 2026-11-16
**Scope:** only what the NEW features need (terminal defaults; Ghostty, Herdr IDE, iTerm2; Xcode CLT, Bruno, AWS CLI, gh-stack, Playwright MCP). Existing engine is not re-researched.
**Overall confidence:** MEDIUM-HIGH (terminal defaults read from upstream source at the pinned tags; a few items marked UNVERIFIED).

Registry method kinds that exist today (`installer/model.py:25`): `script, node, bun, uv-tool, sdkman, github_release, tarball, app, cargo_distrobox, dnf, apt, pacman, rpm_ostree, brew, cask`. There is no `dmg`, `pkg`, `flatpak` or "run argv" kind. Every recommendation below fits one of those unless it is flagged "GAP".

Immutable-Linux rule (from `installer/resolve.py`, per registry comments on wezterm): native kinds (dnf/apt/pacman) are skipped on Bazzite. `github_release`, `tarball`, `script`, `brew`, `bun`, `cargo_distrobox` still resolve.

---

## 1. Terminal defaults: per-terminal mechanism (the core of 999.18/999.19)

Owner rule: Linux launches zsh; macOS Option/Alt+Left/Right = word move; clear = Cmd+K (macOS) / Ctrl+Shift+K (Linux).

### Summary matrix (what each vendor does by DEFAULT, then what to write)

| Terminal | Default Cmd+K (macOS) | Default Ctrl+Shift+K (Linux) | macOS Option+Left/Right default | Write on macOS | Write on Linux |
|---|---|---|---|---|---|
| kitty 0.50.0 | `clear_terminal to_cursor active` (already bound) | **CONFLICT: `scroll_line_up`** (kitty_mod+k) | not bound; needs `macos_option_as_alt` | `macos_option_as_alt both` + 2 `send_text` maps | one `map ctrl+shift+k clear_terminal ...` that overrides the default |
| WezTerm (cask 20240203) | `ClearScrollback="ScrollbackOnly"` (already bound) | `ClearScrollback="ScrollbackOnly"` (already bound) | no default for plain Option+arrow | 2 `SendString` keys in Lua | nothing for the keys (zsh sync exists) |
| Konsole (KDE, Linux only) | n/a | `clear-history-and-reset` = ACCEL+K = Ctrl+Shift+K (already bound) | n/a | n/a | nothing (default already meets the rule) |
| Ghostty 1.4.0 | `clear_screen` (already bound, `performable`) | **not bound** (free) | already bound: `alt+left=esc:b`, `alt+right=esc:f` (macOS block only) | nothing | `keybind = ctrl+shift+k=clear_screen` + `command` for zsh |
| iTerm2 3.7.7 | menu "Clear Buffer" `keyEquivalent="k"` = Cmd+K (already bound) | n/a (macOS only) | needs "Option Key Sends" = Esc+ (plus Keyboard Map, UNVERIFIED) | Dynamic Profile | n/a |
| herdr TUI (multiplexer) | n/a (host terminal's) | n/a | pass-through (UNVERIFIED, see 1.6) | nothing | nothing |
| Herdr desktop app | **not bound** | **CONFLICT: `mod.open:picker`** | already bound: `alt-left send:\u001bb` (keys.macos.json) | `keys.json` `cmd-k` -> `send:\u000c` (Ctrl+L) | owner decision; absent-only rule skips the conflict |

Key finding: most terminals ALREADY satisfy part of the rule. The installer should write only what is missing and must never write a binding that equals the vendor default (idempotent, nothing to strip, no override of the user). That is the "absent-only" rule the Alacritty region and Herdr ledger already use.

### 1.1 kitty (0.50.0, released 2026-11-03; HIGH, read from `kitty/options/definition.py` on master and the live conf page)

- Config: `~/.config/kitty/kitty.conf` (existing `_kitty_config_path`). `include other.conf` is supported (relative to the current config file, env vars expanded), so a separate owned file is possible: `include tools-installer.conf` at the end of kitty.conf. Cleaner than editing the user's file, but still one owned line in it. Keep the existing owned-region approach for consistency.
- (a) Shell: `shell /usr/bin/zsh -l` (default `.` = `$SHELL` then passwd). Existing sync uses an `env` line instead; unchanged. Source: https://sw.kovidgoyal.net/kitty/conf/ (shell option; on macOS changing it "might need" `--login` and `--interactive`).
- (b) macOS word nav. `macos_option_as_alt` values `no|left|right|both`, default `no`; with `no` Option types Unicode characters "which will break any Alt+Key keyboard shortcuts". Write:
  ```
  macos_option_as_alt both
  map opt+left send_text all \x1bb
  map opt+right send_text all \x1bf
  ```
  `send_text` first arg = key modes (`normal`, `application`, `kitty`, `all`); `\e`/`\x1b` escapes accepted (definition.py lines 4860-4873). kitty ships no default for opt+left (grep of definition.py: none). UNVERIFIED on a real Mac: that `opt` is accepted as the modifier alias in a map line (definition.py itself uses `opt+cmd+r`, so it is accepted; HIGH on that point).
- (c) Clear.
  - macOS: DEFAULT already `cmd+k` -> `clear_terminal to_cursor active` ("Clear to start"), also `option+cmd+k` scrollback, `cmd+ctrl+l` clear screen. `to_cursor` needs kitty shell integration to be useful; kitty enables it by default (shell_integration enabled). Write nothing.
  - Linux: the **conflict is real.** Default `scroll_line_up --allow-fallback=shifted,ascii kitty_mod+k scroll_line_up smooth` (kitty_mod = ctrl+shift). Also `kitty_mod+delete` = `reset_terminal`. There is no Linux default clear key. Writing `map ctrl+shift+k clear_terminal to_cursor_scroll active` overrides the default (a later `map` for the same key replaces it; kitty documents `map` as the override mechanism, and `no_op` to unbind). Cost: user loses scroll-line-up on ctrl+shift+k; `ctrl+shift+up` still scrolls. Decision for the owner, default recommended: override, because the owner rule names this key. Use `to_cursor_scroll` (clears the screen, keeps history) rather than `scrollback`.
  - Action reference: https://sw.kovidgoyal.net/kitty/actions/ (`clear_terminal` args `reset|clear|scrollback|scroll|to_cursor|to_cursor_scroll|last_command`).
- Registry/installer fit: owned region via `post_install = ["apply_terminal_tuning"]` (same as alacritty). kitty.conf is plain `key value` lines, so the existing `_replace_owned_region` with `#` comments works. macOS kitty has no zsh sync (Linux-only by design) and needs none.

### 1.2 WezTerm (cask 20240203-110809; MEDIUM-HIGH, live docs)

- Config: `~/.config/wezterm/wezterm.lua` or `~/.wezterm.lua` (existing `_wezterm_config_path`). The existing owned Lua region is inserted before a single `return config` line; the keys must live in that same region.
- (a) Shell: `config.default_prog = { "/usr/bin/zsh", "-l" }` already written by `_wezterm_content`. https://wezterm.org/config/lua/config/default_prog.html
- (b) macOS: documented example, verbatim from the SendString page (https://github.com/wezterm/wezterm docs `keyassignment/SendString.md`):
  ```lua
  { key = 'LeftArrow',  mods = 'OPT', action = wezterm.action.SendString '\x1bb' },
  { key = 'RightArrow', mods = 'OPT', action = wezterm.action.SendString '\x1bf' },
  ```
  `ALT`, `OPT`, `META` are equivalent (https://wezterm.org/config/keys.html). Because the user may already define `config.keys`, emit `config.keys = config.keys or {}` then `table.insert(config.keys, {...})` for each key, guarded by `if wezterm.target_triple:find("darwin")` (UNVERIFIED helper name usage; `wezterm.target_triple` is a documented field, check at implementation).
- (c) Clear: defaults already bind `SUPER+k` and `CTRL+SHIFT+K` to `ClearScrollback="ScrollbackOnly"` (https://wezterm.org/config/default-keys.html). No conflict. Note it clears scrollback only, not the visible screen. Owner call: accept the default (write nothing) or override both with `act.Multiple { act.ClearScrollback 'ScrollAndViewport', act.SendKey { key = 'l', mods = 'CTRL' } }` for a true clear-screen. Recommended: write nothing (least invasive; satisfies "clear scrollback").
- Plain Alt+Left/Right: no default binding exists (the only Alt+arrow defaults are CTRL+SHIFT+ALT AdjustPaneSize), so the SendString keys do not collide.
- Gap: `send_composed_key_when_left_alt_is_pressed` / `use_ime` docs were not retrievable; not needed because `SendString` bound to OPT+arrow is a key-binding, not a composed character.

### 1.3 Konsole (Linux only, KDE; the Bazzite default; not a catalog entry; HIGH on shortcut, MEDIUM on rest)

- (a) Shell: existing sync writes a Konsole profile (`Command=`), unchanged.
- (c) Clear: source `src/session/SessionController.cpp` (master): `clear-history-and-reset` ("Clear Scrollback and Reset") has `setDefaultShortcut(ACCEL | Qt::Key_K)`; ACCEL is Ctrl+Shift on Linux. So Ctrl+Shift+K already works. `clear-history` has no default shortcut. Write nothing. This is the answer for the open owner decision in todo `terminal-defaults-for-konsole`: the default already meets the rule; only a user-rebound key would diverge, and the installer must not fight that.
- (b) N/A (no macOS Konsole).
- If the owner nevertheless wants "Clear Scrollback" (not Reset) on the key, KDE stores shortcuts in a kxmlgui rc file (location UNVERIFIED), a worse integration point than a profile. Do not.

### 1.4 Ghostty (1.4.0; HIGH, read from `src/config/Config.zig` at tag v1.4.0)

- Config: Linux `$XDG_CONFIG_HOME/ghostty/config.ghostty` (docs); the legacy name `config` is also read (UNVERIFIED which wins when both exist; write to the file that exists, else the documented one). macOS: `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty` or XDG path (UNVERIFIED from docs; the reference page excerpt gave XDG only). `config-file = ?path` includes an optional file (the `?` suppresses a missing-file error), https://ghostty.org/docs/config/reference.
- (a) Shell: `command = /usr/bin/zsh -l`. Default is `$SHELL`, then passwd. Extra arguments run through `/bin/sh -c`; `direct:` skips the shell. `shell-integration = detect` picks zsh by filename.
- (b) macOS: Config.zig v1.4.0 lines 7128-7412 (inside the `isDarwin` block): `alt+left -> esc:b`, `alt+right -> esc:f`, `cmd+k -> clear_screen` (flag `performable`), `cmd+backspace -> text:\x15`. Write nothing. `macos-option-as-alt` (values `true|false|left|right`, default unset = true on US layouts only) matters only for Alt+letter shortcuts, not for the arrows, so do not write it (not part of the owner rule).
- (c) Linux: no binding exists for ctrl+shift+k (grep: the only `'k'` binding is `super`). Write `keybind = ctrl+shift+k=clear_screen`. No conflict.
- Do NOT use `keybind = clear`: it removes ALL defaults (docs warning).
- Registry fit: Ghostty config is `key = value` lines; reuse the `#`-comment owned region.

### 1.5 iTerm2 (cask `iterm2` 3.7.7; macOS 13+; MEDIUM)

- Config mechanism: Dynamic Profiles, JSON in `~/Library/Application Support/iTerm2/DynamicProfiles/` (created at launch, reloaded on change; a malformed file makes iTerm2 skip ALL files). Required keys `Name`, `Guid` (uuidgen). Source https://iterm2.com/documentation-dynamic-profiles.html (the page does not list keys).
- Keys verified in iTerm2 source `sources/Settings/Profiles/ITAddressBookMgr.h`: `"Option Key Sends"` (enum `OPT_NORMAL=0, OPT_META=1, OPT_ESC=2`), `"Right Option Key Sends"`, `"Custom Command"` (value `"Yes"`) + `"Command"`, `"Custom Directory"` (Yes/No/Recycle/Advanced) + `"Working Directory"`, `"Keyboard Map"`. So (b): `"Option Key Sends": 2, "Right Option Key Sends": 2`.
- UNVERIFIED: the exact `Keyboard Map` key encoding (the `0xf702-0x280000` style) and whether Esc+ alone makes Option+Left emit word-movement (`ESC b`) rather than `ESC [1;3D`. Before implementing, use iTerm2's documented "Save Profile as JSON" on a real Mac, or add the Keyboard Map entry explicitly: Left = `0xf702`, Right = `0xf703`, Option modifier mask `0x80000` (+ `0x200000` numeric-pad flag), Action 11 (`KEY_ACTION_HEX_CODE`, confirmed in `iTermKeyBindingAction.h`) with Text `0x1b 0x62` / `0x1b 0x66`. Treat these numbers as LOW until captured from a real profile.
- (c) Clear: MainMenu.xib has `<menuItem title="Clear Buffer" keyEquivalent="k">` = Cmd+K by default. Write nothing. Linux N/A.
- Important gap: a Dynamic Profile is an extra profile; it does not become the default one. Use `"Dynamic Profile Parent Name": "Default"` to inherit (documented in the same page, not re-verified here), and making it default needs the `Default Bookmark Guid` pref in `com.googlecode.iterm2.plist` (a `defaults write` the installer has no precedent for). Decide: ship the profile as "tools-installer" and tell the user to select it, or write the pref. Flag for the roadmap.
- Cask uninstall: quit `com.googlecode.iterm2`, app `iTerm.app`, zap list includes `~/Library/Application Support/iTerm2` (that folder includes DynamicProfiles).

### 1.6 herdr (multiplexer) pass-through (MEDIUM-LOW)

- Docs (https://herdr.dev/llms-full.txt, first 100 KB read): only `keys.prefix` (default `ctrl+b`) is intercepted; `terminal.default_shell` (empty = `$SHELL`, then `/bin/sh`) and `terminal.shell_mode` (`auto|login|non_login`) exist. The docs do not say Alt+Left/Right or Ctrl+Shift+K reach the pane program; but Cmd+K and Ctrl+Shift+K are terminal-emulator-level keys that never reach a TUI as such, and Alt+Left arrives as an escape sequence the pane forwards. UNVERIFIED by test. Verify with a real e2e (send `ESC b` through a herdr pane) in 999.19; no config write expected.

---

## 2. Per-tool distribution and the registry method that fits

Confidence on each row is in the notes. "Bazzite" = immutable Fedora: dnf/apt/pacman skipped.

### 2.1 Summary

| Tool | macOS | Linux (incl. Bazzite) | Recommended registry methods | New kind? |
|---|---|---|---|---|
| Ghostty 1.4.0 | cask `ghostty` (official signed .dmg repackaged, macOS >= 13) | no official Linux binary; distro pkgs (Arch `extra`, Ubuntu 26.04, Alpine, ...), community COPR/Terra for Fedora, community AppImage `pkgforge-dev/ghostty-appimage` | macOS `cask`; Linux `pacman` (Arch) + `github_release` raw AppImage (debian/fedora, incl. Bazzite) | No |
| Herdr desktop app 0.1.16 ("Herdr IDE", see 2.3) | cask `herdr-app` (Apple Silicon only) | `script` install.sh (user-scope tarball) x86_64 + aarch64 | macOS `cask` (arch arm64); Linux `script` | No |
| iTerm2 3.7.7 | cask `iterm2` (macOS >= 13) | none | macOS `cask` only | No |
| Bruno 4.3.0 | cask `bruno` | AppImage / .deb / .rpm x86_64 + arm64 on GitHub releases | macOS `cask`; Linux `github_release` raw AppImage (per arch) | No |
| AWS CLI 2.40.4 | official user-local install script; brew formula `awscli` | same script; brew formula (Linuxbrew `x86_64_linux`/`arm64_linux` bottles) | `script` (all OS) with `brew` as fallback | No |
| gh-stack 0.3.0 | `gh extension install` | same | GAP (see 2.6) | Prefer a post_install of `gh`; else one narrow kind |
| Xcode CLT | `softwareupdate`/`xcode-select --install` | n/a | GAP (see 2.7) | Hand-off, not a kind |
| Playwright MCP 0.0.85 | `bunx @playwright/mcp@0.0.85` | same | MCP registration in postinstall, optional `bun` global | No |

### 2.2 Ghostty (HIGH on macOS, MEDIUM on Linux)

- Releases: GitHub `ghostty-org/ghostty` publishes only a rolling `tip` release (macOS universal zip, `Ghostty.dmg`, source tarball); tagged `v1.4.0`. No Linux binary. https://ghostty.org/docs/install/binary.
- macOS: Homebrew cask API (formulae.brew.sh/api/cask/ghostty.json): version 1.4.0, `depends_on macos >= 13`, `url https://release.files.ghostty.org/1.4.0/Ghostty.dmg`, app `Ghostty.app`, uninstall quit `com.mitchellh.ghostty`. Use `kind = "cask"`, `app = "Ghostty.app"`, `min_os_version = "13"`. No `.dmg` kind is needed. This resolves the 999.20 worry that Ghostty would force `.dmg` support (design notes `docs/superpowers/BACKLOG.md:54`); that was only true without the cask.
- Linux: the official docs call Fedora COPR/Terra and the AppImage "community" with "a much higher risk"; Bazzite is not mentioned. `rpm-ostree install` of a COPR package is a sudo/reboot path and violates zero-sudo, so do not offer it. Best option on Bazzite: the community AppImage, releases v1.4.0 (2026-10-28) carry `Ghostty-{ver}-x86_64.AppImage` and `Ghostty-{ver}-aarch64.AppImage` with GitHub API sha256 digests (no checksum sibling file). Registry:
  ```toml
  [[tool.method]]
  kind = "github_release"
  os = ["debian", "fedora"]          # also Arch? Arch has native pacman
  repo = "pkgforge-dev/ghostty-appimage"
  asset = "Ghostty-{ver}-{arch.machine}.AppImage"
  member = "ghostty"
  raw = true
  ```
  Same shape as WezTerm's raw AppImage and herdr's `{arch.machine}` (x86_64/aarch64). The repo's tag is `v1.4.0` while the asset drops the `v`; confirm `{ver}` strips the `v` (it does for wezterm tag `20240203-...`; check against a `v`-prefixed tag in `resolve_target`). The release has a `tip` prerelease that must not be picked (use latest non-prerelease).
- Risk to record: it is a third-party repackage (232 stars), so the install ladder must label it community, not upstream. Also AppImage needs FUSE 2 on the host (UNVERIFIED on Bazzite). Alternative with a vendor-neutral trust story: `pacman` only on Arch and no Debian/Fedora method (honest "not available"), which fails the owner's Bazzite requirement. Recommended: ship the AppImage with a visible caveat.
- Removal: cask uninstall (macOS); Linux AppImage is a single file in `~/.local/bin`; config in `~/.config/ghostty`. Check whether `github_release raw` places a desktop entry (herdr/wezterm do not); the AppImage needs one to appear in KDE; `desktop_entry.py` exists, check its use.

### 2.3 "Herdr IDE": identification (HIGH that the closest product is the Herdr desktop app; no product literally named "Herdr IDE" exists)

- Searched: herdr.dev (home and /download), GitHub org `herdrdev` repos (`herdr`, `herdr-core`, `herdr-app`, `herdr-nix`, `herdr-layout-examples`), web search. No page uses the name "Herdr IDE". herdr.dev lists: **Herdr (desktop app)**, **herdr-core** (runtime/server), **Herdr TUI** (the original, docs at herdr.dev/tui; this is the existing `herdr` catalog entry, repo `herdrdev/herdr`, v0.9.5 2026-10-14), and iPhone/Android apps. A Product Hunt result for an unrelated "lightweight desktop agent IDE" is not Herdr.
- Best match for the owner's "Herdr IDE": the **Herdr desktop app**, repo https://github.com/herdrdev/herdr-app (Apache-2.0, created 2026-10-16, ~3k stars, latest tag v0.1.16, changelog 2026-11-14), described as "a desktop app for terminals and coding agents": spaces, tabs, panes of terminals, agents sidebar, mods (JS), keys.json. It hosts terminals, so the terminal defaults apply. **Mark in the roadmap as UNCONFIRMED NAME: the owner must confirm that "Herdr IDE" = Herdr desktop app before 999.21 plans.**
- Distribution (herdr-app README, `releases.herdr.dev/app/latest.json`, brew cask API):
  - macOS Apple Silicon only (Intel: build from source): `Herdr.dmg`, cask `herdr-app` (v0.1.16, `arch arm`, app `Herdr.app`, binary `herdr-app`, zap `~/.config/herdr-app`, `~/Library/Preferences/dev.herdr.app.plist`), or install.sh into `~/Applications/Herdr.app`.
  - Linux x86_64 + aarch64: `curl -fsSL https://releases.herdr.dev/app/install.sh | sh`. The script (read in full) downloads `herdr-app-linux-<arch>.tar.gz` from the manifest and verifies the manifest sha256, installs `~/.local/share/herdr-app`, symlinks `~/.local/bin/herdr-app`, writes `~/.local/share/applications/herdr-app.desktop` and `.../icons/hicolor/scalable/apps/herdr-app.svg`, and installs `herdr-core` and `hc` into `~/.local/bin` only if none exists. Needs `curl`, `tar`, a desktop session and a working Vulkan driver (README). No sudo. No AppImage, deb, rpm or Flatpak. The app self-updates.
- Registry fit: `script` kind, `url = https://releases.herdr.dev/app/install.sh`, `shell = "sh"`, `bin_dir = "~/.local/bin"`, `paths = ["~/.local/share/herdr-app", "~/.local/share/applications/herdr-app.desktop", "~/.local/share/icons/hicolor/scalable/apps/herdr-app.svg"]` (the kitty entry is the precedent: script + `paths` for removal). The script also writes `herdr-core` and `hc` which are shared with a user's own core: do NOT list them in `paths` (the script leaves a pre-existing core alone, and the app updates it). macOS: `cask herdr-app` with `arch = ["arm64"]` gate (Intel unsupported, so no macOS Intel method).
- Relation to the `herdr` entry: different binary (`herdr-app` vs `herdr`), different config (`~/.config/herdr-app` vs `~/.config/herdr`). Not a dependency. Add `recommends`/note at most; do not couple. `herdr-core` is separate from the TUI's own server.
- Terminal defaults: keys live in `keys.json` (Linux) / `keys.macos.json` (macOS) defaults in the repo; the user file is `keys.json` in its config dir (exact path UNVERIFIED; zap shows `~/.config/herdr-app`). Facts from `defaults/keys*.json` (read via GitHub API): macOS `alt-left`/`alt-right` already `send:\u001bb` / `send:\u001bf`; macOS has no `cmd-k`; Linux `alt-left`/`alt-right` are `pane.go:left/right` (conflict, but the owner rule only wants word-nav on macOS); Linux `ctrl-shift-k` = `mod.open:picker` (**conflict**), Linux ctrl-left/right already send ESC b/f. Plan: macOS write `"cmd-k": "send:\u000c"` (Ctrl+L redraw; Herdr has no terminal-clear command in `docs/commands.md`, UNVERIFIED that none exists elsewhere); Linux: do not override `ctrl-shift-k` silently, owner decision (alternatives: leave it, or bind a different key). JSON region ownership: JSON has no comments, so use herdr's own mod-ledger approach (`keys.json` merge, absent-only) like the existing herdr plugin hook, not a text marker region.
- Shell: the app's core picks the machine's default shell (`$SHELL`); follow it by the existing zsh sync of `$SHELL` (zshenv). A `terminal.default_shell` in the core settings is TUI vocabulary; for the app it is UNVERIFIED.

### 2.4 iTerm2 (HIGH)

- cask `iterm2` 3.7.7, `url https://iterm2.com/downloads/stable/iTerm2-3_7_7.zip`, `depends_on macos >= 13`, app `iTerm.app`. `kind = "cask"`, `os = ["macos"]`, `min_os_version = "13"`, `app = "iTerm.app"`. No Linux/other build. No new kind.
- Customizations (999.22 items 4 and 5, "Show Focus Cursor" and the agent extension) are product identities still not confirmed by the owner; do not research further until named. Item 1/2/3 = one Dynamic Profile (see 1.5): `Option Key Sends`, `Custom Directory = "Recycle"` (verify: the source comment lists `Yes, No, Recycle, Advanced`; "Reuse previous session's directory" = `Recycle`, UNVERIFIED mapping), colors via explicit color keys.

### 2.5 Bruno (HIGH)

- v4.3.0 (2026-10-22), GitHub `usebruno/bruno`. Assets with API sha256 digests: `bruno_4.3.0_x86_64_linux.AppImage`, `bruno_4.3.0_arm64_linux.AppImage` (note: `arm64`, not `aarch64`), `bruno_4.3.0_amd64_linux.deb`, `bruno_4.3.0_arm64_linux.deb`, `bruno_4.3.0_x86_64_linux.rpm`, `bruno_4.3.0_aarch64_linux.rpm`, macOS `arm64_mac.dmg/.pkg/.zip` and `x64_mac.*`, Windows.
- macOS: cask `bruno` 4.3.0 (the cask URL for Apple Silicon is `bruno_4.3.0_arm64_mac.dmg`; no `depends_on`), app `Bruno.app`, zap `~/Library/Application Support/bruno`. `kind = "cask"`.
- Linux incl. Bazzite: `github_release`, `raw = true`, one method per arch because the asset names differ: `arch=["amd64"] asset="bruno_{ver}_x86_64_linux.AppImage"`, `arch=["arm64"] asset="bruno_{ver}_arm64_linux.AppImage"`. Same shape as WezTerm (arch-gated raw AppImage). Digests come from the API (herdr precedent), no checksum file. dnf/apt methods would need the .rpm/.deb URL (no repo) and would be skipped on Bazzite; do not add.
- Flathub and snap exist for Bruno (todo says "confirm"; not verified here); the registry has no flatpak/snap kind: do not add one.
- CLI `bru`: npm `@usebruno/cli` (UNVERIFIED version/bin; not checked). Recommendation: out of scope for this entry; if wanted, a second entry with `kind = "bun"` mirroring `mmdc`.
- Risk: AppImage needs FUSE 2 on Fedora (UNVERIFIED); Electron sandbox on some distros.

### 2.6 AWS CLI (HIGH)

- Official docs (https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) now recommend an install script for both Linux and macOS: `curl -fsSL https://awscli.amazonaws.com/v2/install.sh | bash`. I read the script: user-local by default (`$XDG_DATA_HOME/aws-cli` default `~/.local/share/aws-cli`, symlinks `aws` and `aws_completer` in `~/.local/bin`, honoring `XDG_BIN_HOME`), `--system` needs root (do not pass), `--version X.Y.Z` pins, `--quiet`. Signature check: Linux needs `gpg` (script fails with "gpg not found" unless `--skip-signature-verification`; do not skip, a missing gpg becomes a handoff/prereq); macOS verifies the pkg team id `94KV3E626L`. Refuses to overwrite an existing install of another version in the same dir. Both x86_64 and aarch64 on Linux; macOS arm64 and Intel (pkg).
- Registry: one `script` method for macOS and Linux, `shell = "bash"`, `bin_dir = "~/.local/bin"`, `paths = ["~/.local/share/aws-cli"]` plus the two symlinks if `paths` allows files (removal per AWS: delete the two symlinks and the install dir; `~/.aws` is shared SDK config and must NEVER be removed). The `uv` and kitty entries are the precedent. Smoke: `aws --version` (offline).
- Fallback: `brew` formula `awscli` 2.40.3 (formulae.brew.sh), bottles for arm64 macOS and x86_64/arm64 Linux. Per ladder order keep it AFTER the script (the official one, user scope). Tier `user`.
- AWS ships no `.pkg` that installs without admin via `installer -target /` (`sudo`); the per-user pkg route uses a choices XML (more complex than the script); do not use it. Snap exists (`sudo snap install --classic`): sudo, skip. dnf/apt `awscli` is v1 on many distros: do not add native methods (the doc warns v1 and v2 share the `aws` name).
- Version sources: `aws-cli` GitHub tags v2.40.4 (latest tag), brew 2.40.3 (lag).

### 2.7 gh-stack (MEDIUM; engine GAP)

- `github/gh-stack` v0.3.0 (2026-10-26) publishes raw per-OS/arch binaries: `darwin-amd64`, `darwin-arm64`, `linux-386/amd64/arm/arm64`, `windows-*` (GitHub API, no version in asset names). `gh extension install github/gh-stack` downloads the matching asset as a precompiled extension. Requires `gh` and git 2.36+ (README). Auth need not documented; do not log in.
- `gh extension install <repo>` accepts `OWNER/REPO` or a full URL; the URL form is "useful when the repository is not hosted on github.com" (https://cli.github.com/manual/gh_extension_install). `--pin <tag>` pins a binary extension to a release tag. Flags `--force` re-installs.
- GHE question from the todo, answered from gh source (`cli/cli` `pkg/cmd/extension/manager.go`, gh 2.104.0): the manager records `Host: repo.RepoHost()` in the extension's manifest at install (lines ~247, 368), and later download/upgrade calls use that stored host. So `upgrade` goes back to the install host without `GH_HOST`; install with the full URL to force github.com. MEDIUM (source read, not run).
- Argv: install `gh extension install https://github.com/github/gh-stack [--pin v0.3.0]`; upgrade `gh extension upgrade stack`; remove `gh extension remove stack`; detect `gh extension list` (parse the repo column) or the file `~/.local/share/gh/extensions/gh-stack/` (path UNVERIFIED, depends on `XDG_DATA_HOME`/`GH_CONFIG_DIR`).
- Registry fit: none of the 15 kinds runs `gh extension install` (not a package manager kind). Cheapest, no new kind: model it as a `post_install` action of the `gh` entry or a tiny entry with `requires = ["gh"]` driven by the same post-install seam that herdr uses (`postinstall = "herdr-integration"`, runs `herdr integration install`). Do NOT add a `gh_extension` kind unless the owner wants several extensions (YAGNI: one extension today). Alternative: `github_release raw` straight to `~/.local/share/gh/extensions/gh-stack/gh-stack` is brittle (also needs `manifest.yml`), reject.

### 2.8 Xcode Command Line Tools (MEDIUM; GAP)

- Detection `xcode-select -p` (exit 0 when a developer dir is selected) or `pkgutil --pkg-info=com.apple.pkg.CLTools_Executables`.
- Install options, from Homebrew's `install.sh` (read in full): headless: create `/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress`, list with `softwareupdate -l`, then `execute_sudo softwareupdate -i <label>` and `execute_sudo xcode-select --switch ...`; fallback `xcode-select --install` (opens a GUI dialog, no sudo, interactive). The headless route needs sudo, which violates the zero-sudo rule. Note: the brew entry already sets `HOMEBREW_NO_SUDO=1` and `NONINTERACTIVE=1`, so brew's own CLT step is also affected; verify what actually happens on a clean Mac (UNVERIFIED).
- Recommendation: do not add a kind. Model `xcode-clt` as `tier = "system"`, `os = ["macos"]`, detection by `xcode-select -p`, and a pure HAND-OFF (print `xcode-select --install`, never run it), like native methods are handed off on immutable Linux (`installer/executors.py:750`). If the registry requires a method to exist, this is the one place a tiny "handoff-only" method is unavoidable; first check whether `resolve.py` permits a tool with only detection and `requires = ["xcode-clt"]` consumers. Removal: `sudo rm -rf /Library/Developer/CommandLineTools` is root, so hand off (ties into the pending todo "hand off casks whose uninstall needs root").

### 2.9 Playwright MCP (HIGH on facts, MEDIUM on fit)

- `@playwright/mcp` 0.0.85 (npm 2026-11-09), `bin: playwright-mcp`, node >= 18. README registration pattern: `claude mcp add playwright npx @playwright/mcp@latest` (same shape for codex/amp/droid/grok). Browser path: `--executable-path` / env `PLAYWRIGHT_MCP_EXECUTABLE_PATH` (verified in README table). Also `PLAYWRIGHT_MCP_BROWSER` (chrome, firefox, webkit, msedge) and `PLAYWRIGHT_MCP_HEADLESS`.
- Machine rule: `npm` is blocked here, so register with `bunx @playwright/mcp@0.0.85` (the registry already depends on bun) or install `bun` globally (`kind = "bun"`, `npm_pkg = "@playwright/mcp"`, then the MCP command is `playwright-mcp`). Recommended: pinned `bunx` in the MCP registration (no global install, no drift), because the MCP host starts it on demand.
- Existing seam: `installer/postinstall.py` already registers MCP servers for the agent hosts. Add a Playwright entry there; no registry method kind. The pending todo (`2026-10-13-playwright-mcp-flatpak-chrome.md`) adds, on Bazzite only, `PLAYWRIGHT_MCP_EXECUTABLE_PATH=/var/lib/flatpak/exports/bin/com.google.Chrome` when that wrapper exists, set both in the managed shell rc and in the MCP entry's `env` (cursor-agent strips env to 8 variables). Browsers are not downloaded by the MCP itself; with `--browser chromium` it needs a Playwright browser install; the user's Chrome avoids that.
- Open: whether this is a catalog tool at all or a pure postinstall (it has no `cmd` to smoke-test; `playwright-mcp --version` UNVERIFIED).

---

## 3. What NOT to add

- No `dmg`, `pkg`, `flatpak`, `snap`, `appimage` or `gh_extension` kind. Cask covers every macOS app here, `github_release raw` covers AppImages, `script` covers Herdr app and AWS CLI.
- No Policies knob and no question for the terminal defaults: install tuning only, absent-only, stripped with the tool (matches memory rule "Install tuning, not Policies").
- No `rpm-ostree`/COPR path for Ghostty on Bazzite (sudo and reboot).
- No `~/.aws` removal on AWS CLI uninstall.
- Never write a key the vendor already binds identically (kitty Cmd+K, WezTerm both, Konsole, Ghostty macOS, iTerm2 Cmd+K).
- Do not use Ghostty `keybind = clear`.
- Do not couple Herdr app and the `herdr` TUI entry.

## 4. Verified versions (live, 2026-11-16)

| Item | Version | Source |
|---|---|---|
| kitty | 0.50.0 (2026-11-03); latest GitHub release `v0.50.0` | `gh api repos/kovidgoyal/kitty/releases/latest`, conf page changelog |
| Ghostty | 1.4.0 (cask; tag `v1.4.0`) | formulae.brew.sh/api/cask/ghostty.json |
| Ghostty AppImage | v1.4.0 (2026-10-28) | `pkgforge-dev/ghostty-appimage` releases |
| iTerm2 | 3.7.7 | formulae.brew.sh/api/cask/iterm2.json |
| Bruno | 4.3.0 (2026-10-22) | GitHub releases; cask 4.3.0 |
| Herdr app | 0.1.16 (2026-11-14), core min 0.1.11 | `releases.herdr.dev/app/latest.json`, repo CHANGELOG |
| herdr TUI (existing) | v0.9.5 (2026-10-14) | GitHub releases |
| AWS CLI | tags up to 2.40.4; brew 2.40.3 | `gh api repos/aws/aws-cli/tags`, formulae.brew.sh |
| gh-stack | v0.3.0 (2026-10-26) | GitHub releases |
| gh | v2.104.0 | GitHub releases |
| @playwright/mcp | 0.0.85 | npm registry |
| WezTerm cask | 20240203-110809 (registry comment; not re-fetched) | registry.toml |

## 5. Sources

- kitty config and actions: https://sw.kovidgoyal.net/kitty/conf/ , https://sw.kovidgoyal.net/kitty/actions/ ; defaults in `kitty/options/definition.py` (master) https://github.com/kovidgoyal/kitty
- WezTerm: https://wezterm.org/config/default-keys.html , https://wezterm.org/config/keys.html , https://wezterm.org/config/lua/config/default_prog.html , SendString doc in https://github.com/wezterm/wezterm
- Konsole defaults: https://github.com/KDE/konsole `src/session/SessionController.cpp`
- Ghostty: https://ghostty.org/docs/config/reference , https://ghostty.org/docs/install/binary , `src/config/Config.zig` at tag v1.4.0 https://github.com/ghostty-org/ghostty
- iTerm2: https://iterm2.com/documentation-dynamic-profiles.html ; keys from https://github.com/gnachman/iTerm2 `sources/Settings/Profiles/ITAddressBookMgr.h`, `sources/MainMenu/Base.lproj/MainMenu.xib`
- Herdr: https://herdr.dev , https://herdr.dev/download , https://herdr.dev/llms-full.txt , https://github.com/herdrdev/herdr-app (README, CHANGELOG, `defaults/keys.json`, `defaults/keys.macos.json`, `defaults/AGENTS.md`, `distribution/install.sh` served at https://releases.herdr.dev/app/install.sh)
- Casks/formulae: https://formulae.brew.sh/api/cask/{ghostty,iterm2,bruno,herdr-app}.json , https://formulae.brew.sh/api/formula/awscli.json
- AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html , https://docs.aws.amazon.com/cli/latest/userguide/uninstall.html , https://awscli.amazonaws.com/v2/install.sh
- gh: https://cli.github.com/manual/gh_extension_install , https://github.com/github/gh-stack , https://github.com/cli/cli `pkg/cmd/extension/manager.go`
- Playwright MCP: https://github.com/microsoft/playwright-mcp README, npm `@playwright/mcp`
- Homebrew CLT flow: https://github.com/Homebrew/install `install.sh`

## 6. Unverified (carry into phase research)

1. iTerm2 Keyboard Map key encoding and whether Esc+ alone yields ESC b; `Custom Directory = "Recycle"` mapping; whether `Dynamic Profile Parent Name` is honored as described.
2. Ghostty macOS config path, `config.ghostty` vs `config` precedence in 1.4.0.
3. kitty Linux override of `ctrl+shift+k` tested on a real kitty (documented behavior, not run).
4. herdr TUI Alt+arrow and Ctrl+Shift+K pass-through (no test run).
5. Herdr app user `keys.json` path and the `cmd-k` -> `send:\u000c` choice; "Herdr IDE" naming is the owner's to confirm.
6. AppImage FUSE 2 requirement on Bazzite (Ghostty, Bruno).
7. gh-stack extension directory path; `playwright-mcp --version` smoke; `@usebruno/cli` details; Flathub/snap Bruno status.
8. What brew's `install.sh` does for CLT when `HOMEBREW_NO_SUDO=1` on a clean Mac.
