# Feature Landscape

**Domain:** Terminal-emulator and IDE defaults plus eight new tool onboardings in an existing uv/Textual cross-platform installer (milestone v0.51.0)
**Researched:** 2026-11-16
**Overall confidence:** MEDIUM-HIGH (terminal defaults verified against upstream docs and source; Xcode CLT and WezTerm/iTerm2 option-key keys partly unverified, marked below)

Scope: only what the new features need. Existing machinery is assumed (terminal sync in `installer/terminal_shell.py`, Alacritty `alacritty-keys` owned region, `post_install` install tuning, receipts, `config_paths`, closed `POSTINSTALL_HOOKS`, zero-sudo invariant, containers-only real installs).

## 1. What the three terminal defaults mean (semantics)

### 1a. "Clear screen" is not one thing

| Terminal | Mac default (Cmd+K) | Linux default (Ctrl+Shift+K) | What it clears | Source |
|----------|---------------------|------------------------------|----------------|--------|
| Alacritty (already shipped) | none | installer writes `Control\|Shift` K = `ClearHistory` | Scrollback only (visible screen stays) | `installer/terminal_shell.py:477-482` (HIGH) |
| kitty | `cmd+k` = `clear_terminal to_cursor active` (up to the prompt, needs shell integration); `opt+cmd+k` = scrollback; `cmd+ctrl+l` = to_cursor_scroll | **Clash:** `ctrl+shift+k` is `scroll_line_up smooth` by default; `ctrl+shift+delete` = `clear_terminal reset` | Per option: `reset`, `clear` (screen), `scrollback`, `scroll` (push screen into scrollback), `to_cursor`, `to_cursor_scroll`, `last_command` | sw.kovidgoyal.net/kitty/conf and /actions (HIGH, read from page) |
| WezTerm | `SUPER+k` = `ClearScrollback="ScrollbackOnly"` | `CTRL+SHIFT+K` = `ClearScrollback="ScrollbackOnly"` | Scrollback only; does not touch the visible screen. `ScrollbackAndViewport` is the "both" variant | wezterm.org/config/default-keys.html (HIGH for the two defaults; variant name from WezTerm API memory, MEDIUM) |
| Konsole | none (Linux only) | `Ctrl+Shift+K` = "Clear Scrollback and Reset" (default since KDE 4.9; was Ctrl+Shift+X) | Scrollback and a terminal reset. Known quirks: prompt can vanish until a keypress, sends SIGWINCH, can disable bracketed paste (KDE bugs 335047, 427577, 435548; 2014-2021, not rechecked on current Konsole) | bugs.kde.org (MEDIUM) |
| Ghostty | `cmd+k` = `clear_screen` (default, `performable`) | no default binding for `k` on Linux in `Config.zig` | `clear_screen` is documented "Clear the screen and all scrollback" (both) | ghostty-org/ghostty `src/config/Config.zig`, `src/input/Binding.zig` (HIGH, source) |
| iTerm2 | Cmd+K = Clear Buffer (iTerm2 default; **unverified here**) | n/a (macOS only) | Scrollback and screen ("Clear Buffer") | not fetched (LOW; confirm in UAT) |
| herdr (multiplexer) | n/a, host-terminal key | n/a | herdr may intercept keys; not verified (todo 2026-11-16) | todo |

Consequence for requirements: the owner rule says "clear the screen". The nearest common meaning across all six is "clear visible screen AND scrollback" (Ghostty `clear_screen`, iTerm2 Clear Buffer, Konsole clear+reset, kitty `clear_terminal clear`/`scrollback` pair). Alacritty already ships `ClearHistory` (scrollback only, visible screen untouched, a different meaning) and WezTerm's defaults are scrollback-only. The skill must pin ONE meaning per terminal in a table, not leave it implicit, or kitty, WezTerm and Ghostty will each do something different under the same key. Recommended pin: "clears scrollback and the visible screen, prompt redrawn", falling back to the terminal's closest native action, documented per terminal.

### 1b. Word navigation semantics

- zsh's default (emacs) keymap binds `ESC b` / `ESC f` to backward-word / forward-word, and `Ctrl+Left/Right` is usually unbound. Terminals that send `ESC [ 1 ; 3 D` for Alt+Left (xterm modifier encoding, which Ghostty and kitty send by default) hit nothing in a stock zsh. This is why the shipped Alacritty rule sends the literal bytes `\u001bb` and `\u001bf` (`chars` binding), not a modifier encoding. The robust, shell-agnostic default is therefore "send `ESC b` / `ESC f`", not "configure zsh bindkey". (MEDIUM: standard zsh/readline behavior, not re-verified against zsh docs in this run.)
- On macOS the blocker is that Option composes Unicode characters instead of acting as Alt. Per terminal:
  - kitty: `macos_option_as_alt no` is the default; the user must set it (`yes`/`left`/`right`/`both`) (HIGH, kitty docs).
  - Ghostty: `macos-option-as-alt` unset; default is `true` only for the U.S. and U.S. International layouts, otherwise `false`; `left`/`right` accepted. No default Alt+Left/Right word binding exists in `Config.zig`, so a binding such as `alt+left=esc:b` is also needed (HIGH for option semantics, MEDIUM for "no binding" since only grep-checked).
  - iTerm2: profile "Left Option key" Normal vs Esc+ (docs: "+Esc is the right choice for most users"); todo expects plist key "Option Key Sends" = 2 (UNVERIFIED, confirm via "Save Profile as JSON"). Alternative is "Natural Text Editing" preset (known to interact badly with zsh-vi-mode) (MEDIUM).
  - WezTerm: no default word binding listed (HIGH); Option/Alt handling is `send_composed_key_when_left_alt_is_pressed` / `send_composed_key_when_right_alt_is_pressed` (UNVERIFIED, not on the fetched page). Writing explicit `SendString("\x1bb")` bindings in the owned Lua region sidesteps it, which matches the todo's own advice.
  - Alacritty on macOS: no macOS method yet; `alacritty-keys` is Linux-tied, and "Alt" there is already Option-as-Alt by default (UNVERIFIED).
- Linux: Alt+Left/Right needs no terminal change except where a terminal sends the modifier encoding; the owner rule scopes word navigation to macOS only. Keep it that way.

## 2. Terminal-defaults features

### Table Stakes

| Feature | Why Expected | Complexity | Notes / Dependencies |
|---------|--------------|------------|----------------------|
| Skill rewrite: three defaults stated as rules, with per-OS mechanism, a "meaning of clear" table and the conflict rule (999.18) | Today `tool-onboarding/SKILL.md:180-195` says "ask the user" and "do not enable silently", which contradicts the owner rule and install-tuning policy (TUNE-04); only Alacritty got keys | Low-Med | Standing rule: skill-judge before and after the edit. First phase; everything else depends on it |
| Defaults apply to IDEs with a terminal too (VS Code, Cursor, Antigravity, Herdr IDE if it embeds one) | Owner rule names "terminal emulator and IDE with a terminal" | Med | The skill must say which IDE setting carries it (`terminal.integrated.commandsToSkipShell`, `workbench.action.terminal.clear`, `sendSequence` keybindings). UNVERIFIED per IDE; research per IDE when it comes up. VS Code lean tuning exists from 23.2 |
| kitty: Linux Ctrl+Shift+K clear, macOS Cmd+K clear, macOS `macos_option_as_alt` | Todo 2026-11-16-kitty | Med | MUST resolve the default clash: kitty binds `ctrl+shift+k` to `scroll_line_up`. Owned region needs a `map ctrl+shift+k clear_terminal ...` that overrides it, and the user loses that scroll key (they still have `ctrl+shift+up`). Treat as a documented, deliberate override of an installer-visible default, not of a user-defined binding |
| WezTerm: same three, in the owned Lua region | Todo 2026-11-16-wezterm | Med | Linux Ctrl+Shift+K and macOS Cmd+K already exist but clear scrollback only, so the work is pinning the intended meaning and adding macOS Option word keys via explicit `SendString` |
| Konsole: Ctrl+Shift+K | Owner decision in todo; Bazzite default terminal | Low | Already the stock Konsole default ("Clear Scrollback and Reset"), so "apply" mostly means verify and leave alone. Real work is only if a user remapped it. Konsole is detected, not catalogued: no `post_install` owner and no receipt unless the sync owns it |
| herdr pass-through check | Todo 2026-11-16-herdr | Low | Verification first (does herdr swallow Alt+Left/Right or the clear key); change nothing if it passes |
| Never override a user-defined binding; owned region stripped with the tool; idempotent re-run | Alacritty precedent (`alacritty-keys`, `_KEYS_RECORD`) | Med | Reuse the region/record/guard shape from `installer/terminal_shell.py:477-482`; each terminal needs its own parse of "does the user already bind this key" (TOML for Alacritty, `kitty.conf` map lines, Lua for WezTerm, `config` keybind lines for Ghostty, plist/JSON for iTerm2) |
| zsh as launched shell on Linux for every new terminal (Ghostty, Herdr IDE if it hosts one) | Existing zsh terminal sync covers kitty, WezTerm, Konsole, Alacritty, herdr | Med | Needs a new `_sync_ghostty` branch (Ghostty `command =` or `shell-integration`-aware setting) following `_sync_herdr`. Sync is Linux-only by design: macOS terminals launch the user's login shell, which the installer keeps on zsh (`SHELL` kept on zsh, CONF) |
| Tests in scratch HOME; container e2e for real effect | AGENTS.md, Phase 24.1 three-distro e2e | Med | Per-terminal config-file fixtures; macOS paths only unit-tested (no macOS host run since v0.49.0, so macOS behavior stays UNVERIFIED on a real Mac) |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| One declarative "terminal defaults" table in code (terminal id -> OS -> region writer) so a future terminal is one row | The milestone goal says "and every one added later" | Med | Matches the "one registry, wiring only" rule. A table beats three copies of the Alacritty writer; ponytail view: do the second terminal by copying Alacritty's shape, extract the table at the third |
| Skill emits a checklist of exactly which keys it set per terminal into the receipt/`# Verified` note | Review mode can re-audit later | Low | Existing `# Verified` convention |
| Detect user's existing binding and report it as "kept yours" in the install result | Makes the conflict rule visible | Low-Med | Reuses Alacritty's per-part guard |

### Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Policies rows or TUI knobs for these keys | Repo rule: install tuning, never new Policies knobs (23.2 D-01, TUNE-04) | `post_install` owned region |
| Asking the user per terminal whether to enable the keys | Owner rule 2026-11-16: defaults, not questions; the skill asks only about extras | Apply silently; ask only about extras (themes, companion tools) |
| Remapping Cmd+Left/Right, Option+Backspace, Ctrl+A/E and other nav keys | Beyond the owner rule; scope creep and clash risk | Defer; record as a follow-up |
| Writing Linux word-navigation bindings | Owner rule scopes word nav to macOS | Leave Linux Alt+arrows alone |
| Blind-overwriting an existing key file or changing a user's `Ctrl+Shift+K` binding | D-01a "detect and configure, never blind-overwrite" | Skip and report when user binds the key |
| Editing the real macOS terminal prefs plist directly (`defaults write`) | Not atomic, cfprefsd caches, not reversible with proof | Use file-based, owned, strippable config per tool |

## 3. New tool onboardings

Common facts: all are minor, none authorized to touch real host config; every entry needs `verified` date, a smoke-able `cmd`, a method ladder, `config_paths`, and install receipts; real install/uninstall only in containers.

### 3a. Ghostty (999.20)

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| macOS brew cask `ghostty` | Table stakes | Low | Cask method exists (`_cask`, precedent in `registry.toml`). Verify cask name (UNVERIFIED) |
| Linux install path | Table stakes | High unknown | Upstream ships source and distro-maintained packages only; no official Linux binary/AppImage known (UNVERIFIED, memory). Bazzite has no native package route: likely brew-on-Linux is absent for the cask, so Flatpak/Distrobox/none. Research flag: may end as macOS-only |
| zsh sync on Linux (`command=` in `~/.config/ghostty/config`) | Table stakes | Med | New branch of `terminal_shell.py` |
| macOS `macos-option-as-alt = true` (or left) + `keybind = alt+left=esc:b`, `alt+right=esc:f` | Table stakes | Med | Config is key=value text, easy owned region |
| Cmd+K already default (`clear_screen`) | Free | Low | Do not rewrite; assert only. Linux Ctrl+Shift+K needs `keybind = ctrl+shift+k=clear_screen` |
| `.dmg` install | Anti-feature | n/a | No dmg method kind (v0.50.0 ultra cut); use the cask |

### 3b. Herdr IDE (999.21)

Finding: herdr.dev now publishes a separate free, open-source desktop app ("Herdr", the Mac app is an Apple-silicon-only `.dmg`; Linux x86_64 and arm64 and Windows supported; installer line `curl -fsSL https://releases.herdr.dev/app/install.sh | sh`, adds an app-launcher entry, sets up `herdr-core` if absent, updates itself). It is distinct from "Herdr TUI" (the catalog's `herdr`). Whether it embeds a terminal is NOT stated (https://herdr.dev/download/, MEDIUM). Brew cask: not mentioned (UNVERIFIED).

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| Entry via the official `app/install.sh` script method | Table stakes | Med | `script` method with `paths`/`remove` from the lifecycle contract; the script must prove its footprint (unknown; read the script in a container first) |
| Separate entry from `herdr`, with `recommends`/shared `~/.config/herdr` decision | Table stakes | Low-Med | Name collision risk in detection (`cmd`): two products, similar names. Pick a distinct `cmd` and `id` (e.g. `herdr-app`) |
| Terminal defaults | Conditional | Low | Only if it hosts a terminal; research gate, otherwise the entry is a plain app |
| Self-update | Constraint | Low | The app updates itself, so mark the update route as app-owned (no installer update step), as for other self-updaters |
| macOS-only (Apple silicon) gating | Table stakes | Low | `arch` gate on the Mac method |

### 3c. iTerm2 (999.22), macOS only

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| brew cask `iterm2`, `os = ["macos"]` | Table stakes | Low | Modeled on Alacritty entry |
| **Dynamic Profile JSON, not plist edit** | Table stakes (mechanism) | Med | iTerm2 watches `~/Library/Application Support/iTerm2/DynamicProfiles/` and reloads all files on any change; only `Guid` and `Name` required; it cannot be edited from the UI unless `"Rewritable": true` (iterm2.com dynamic-profiles docs, HIGH). A file the installer owns is strippable byte-exact, atomic and receipt-provable. Editing `com.googlecode.iterm2.plist` fights cfprefsd, is not reversible with proof. Decision: Dynamic Profile |
| Profile contents: Option as Esc+, working-directory reuse | Table stakes | Low-Med | Key names unverified (`Option Key Sends`: 2, `Custom Directory`/`Working Directory` semantics): use "Save Profile as JSON" in a container-free manual check, since iTerm2 is not testable in Linux containers |
| Cmd+K clear | Free default | Low | iTerm2 default (UNVERIFIED); assert, no write |
| Dynamic profile is not the default profile | Gotcha | Med | The new profile does not become default unless `Default Bookmark Guid` pref is set, which lives in the plist the installer should not touch. Either document "pick the profile" or accept that the defaults apply only to the installer's profile. This is the main open design question; flag for phase research |
| Matrix green colors, "Show Focus Cursor", agent-collaboration extension | Ask / differentiator | Med each | Owner has not named items 4 and 5 (999.22: "owner must still name the products"). Do NOT guess. Color scheme can sit in the same JSON (low risk); the other two are blocked on the owner |
| Cask uninstall needing root | Risk | n/a | iTerm2 cask uninstall normally needs no sudo; todo 2026-11-04 (root-needing casks) is carried, not in scope |

Testing limit: no macOS CI run has been done locally; only unit tests of the JSON writer plus the macOS CI job. State this as a gap, not a pass.

### 3d. Xcode Command Line Tools (macOS system tier)

| Option | Verdict | Why |
|--------|---------|-----|
| (a) delegate to brew `install.sh` | Recommended default shape | Matches the PRD bootstrap order and todo T04: `xcode-clt` entry `tier = "system"`, `requires = ["brew"]` is circular though (brew needs CLT). Resolve by making `xcode-clt` detect-only/handoff and leaving CLT installation to brew's own installer, with `brew` declaring `requires = ["xcode-clt"]` satisfied by detection |
| (b) `softwareupdate` flow | Reject as an executed step | `softwareupdate -i` needs root, and the installer is zero-sudo (O1). It also needs the `.com.apple.dt.CommandLineTools.installondemand.in-progress` flag touched first (todo) |
| `xcode-select --install` | Acceptable handoff | Opens an Apple GUI dialog, no sudo, user-driven, but non-interactive/headless runs cannot complete it |

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| Detection `xcode-select -p` plus a CLT-path existence check | Table stakes | Low | Must not treat the `/usr/bin/git` stub as installed (macOS stub detection exists, REG-01..10) |
| Handoff: print exact command for the user (zero-sudo) | Table stakes | Low-Med | Existing `native installs handed off` contract (LIFE-02) |
| `requires` edge from brew and source-build tools | Table stakes | Low | No new resolver logic; data only |
| Uninstall | Anti-feature | n/a | CLT removal is `sudo rm -rf /Library/Developer/CommandLineTools`, not installer scope; never offer it |
| Apple-hosted install through `softwareupdate` under sudo | Anti-feature | n/a | Violates zero-sudo |

Confidence: MEDIUM. The `softwareupdate`/sudo and `xcode-select --install` GUI-dialog facts are from general knowledge plus the todo; not re-fetched this run.

### 3e. Bruno

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| macOS `brew install bruno` (cask) | Table stakes | Low | Docs say `brew install bruno` (https://docs.usebruno.com/get-started/bruno-basics/download, HIGH) |
| Linux: Flatpak `com.usebruno.Bruno` on Bazzite; deb/rpm/AppImage via release | Table stakes | Med | Flatpak is documented; no existing Flatpak method kind in `METHOD_KINDS`, so either a new kind (scope risk), or a `github_release` AppImage `raw=true` as with WezTerm. Prefer the AppImage `raw=true` precedent, avoid a new kind |
| Snap, APT repo | Anti-feature | n/a | Need sudo (snap, apt repo add); zero-sudo |
| Separate `bru` CLI (`@usebruno/cli` via npm/bun) as its own entry | Differentiator | Low | Reuses the `bun` method kind; decide second entry vs out of scope, default to a second tiny entry only if the owner wants it (todo leaves open) |
| User data (collections are plain files in the user's git repos) | Constraint | n/a | Never list collections in `config_paths` |

### 3f. AWS CLI v2

| Option | Verdict | Why |
|--------|---------|-----|
| Official install script `curl -fsSL https://awscli.amazonaws.com/v2/install.sh \| bash` | Recommended | AWS marks it "recommended"; installs for the current user by default to `$HOME/.local/share/aws-cli` with a symlink in `$HOME/.local/bin`, verifies the download; sudo only with `--system` (docs page, HIGH) |
| Zip/pkg installer | Reject | macOS `.pkg` and the manual zip flow use `sudo installer`/`/usr/local` (HIGH, docs) |
| brew `awscli` | Fallback on macOS and brew-first hosts | Third-party maintained (AWS: "doesn't maintain third-party repositories other than snap"); repo's brew-first priority (PRIO) will pick it automatically where brew exists; keep it as a lower rung only after deciding the priority conflict below |
| snap | Reject on Bazzite | needs root and snapd |

Notes: `aws update` self-updates from 2.36.0 for script or official-installer installs, so the update route should be `aws update` (HIGH, docs), not reinstall. Uninstall for the user-level script install is: remove the two symlinks (`aws`, `aws_completer`) in `$HOME/.local/bin` and the install dir `$HOME/.local/share/aws-cli`, and optionally `~/.aws` (docs give the generic recipe; the user-level paths come from the script note, HIGH). `~/.aws` holds shared credentials and must NOT be in `config_paths` as a removable path: it is shared with every AWS SDK (docs warning).

Conflict to decide: repo priority is brew first, but the todo says "official" install guidance. Recommendation: official script first on Linux (including Bazzite where brew is unwanted), brew on macOS (the official macOS route needs sudo pkg). Needs an explicit decision in phase planning.

| Feature | Class | Complexity |
|---------|-------|------------|
| `aws --version` smoke check, no auth | Table stakes | Low |
| `paths`/`remove` per script lifecycle contract | Table stakes | Low-Med |
| Shell completion line (`aws_completer`) | Ask (extra) | Low | Todo: ask about shell integration; zsh needs `bashcompinit` |
| Configure credentials/SSO/profile | Anti-feature | n/a | Todo forbids it |

### 3g. gh-stack (`gh extension install`)

Facts (https://github.com/github/gh-stack, HIGH): installed with `gh extension install github/gh-stack`; needs `gh` 2.0+ and Git 2.36+; upgrade with `gh extension upgrade stack`; background update notices cached 24 h, `GH_STACK_NO_UPDATE_NOTIFIER=1` disables; state under gh's state dir; page does not document uninstall (the extension is removed with `gh extension remove stack`, from the todo, standard gh behavior); optional agent skill via `gh skill install github/gh-stack`; `alias` writes a wrapper into `~/.local/bin`; commands rewrite history (`rebase`, `sync --prune`).

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| Install as a post-install step of `gh` or a tiny new method kind, `requires = ["gh"]` | Table stakes | Med | Per todo: avoid a new method kind unless proven; `extension` as a `script` method with argv `gh extension install https://github.com/github/gh-stack` is the smallest shape. Use the full URL (GHE default-host bug, owner note 2026-11-03) |
| Detection via `gh extension list` (host github.com) | Table stakes | Med | Filesystem detection is the repo's rule; check `~/.local/share/gh/extensions/gh-stack/` as the receipt path (UNVERIFIED path, derive in scratch `GH_CONFIG_DIR`/XDG) |
| Update `gh extension upgrade stack`, removal `gh extension remove stack` | Table stakes | Low | Verify behavior on a GHE-default scratch config before fixing argv (todo) |
| No auth needed to install; hand off `gh auth login` | Table stakes | Low | Never run login |
| `gh skill install github/gh-stack` agent skill | Anti-feature | n/a | Repo rule: skill packs are not installer scope (HOST-01); skip |
| `gh stack alias` | Anti-feature | n/a | Writes an unproven file into `~/.local/bin`; skip |
| Pinning (`--pin`) | Differentiator | Low | Only if drift checks are wanted; default unpinned with `gh extension upgrade` |

### 3h. Playwright MCP with a Flatpak browser

Facts (research report 16, 2026-10-13, tested; HIGH): `@playwright/mcp` defaults to `chrome` channel = `/opt/google/chrome/chrome`, absent on Bazzite; fix is `PLAYWRIGHT_MCP_EXECUTABLE_PATH=/var/lib/flatpak/exports/bin/com.google.Chrome`; cursor-agent strips the environment, so the variable must also be set in Cursor's MCP `env`; `PLAYWRIGHT_MCP_BROWSER`, `_HEADLESS`, `_ISOLATED`, `_USER_DATA_DIR` also exist; `@latest` drifts and orphans `~/.cache/ms-playwright`.

| Feature | Class | Complexity | Notes |
|---------|-------|------------|-------|
| Shell-rc `tweak:playwright-mcp` export, only when the Flatpak wrapper exists | Table stakes | Low-Med | Existing managed-rc tweak machinery; inherited by Claude when launched from a shell |
| Cursor MCP config `env` entry | Table stakes | Med | Uses `agent_settings.py` single writer and `receipt.hooks` per host (Phase 23); present hosts only |
| Gate on Flatpak Chrome presence; do not install a browser | Table stakes | Low | Browser install is out of scope; if absent, do nothing |
| `~/.claude/settings.json` `env` write | Ask / anti-default | Low | Todo: needs consent; also a Claude config write. Ask, do not default |
| Installing the plugin / registering the MCP server itself | Open | Med | Todo covers only the env fix; whether the catalog also registers the server through hooks is a scope question for the owner |
| Pin `@playwright/mcp` version | Differentiator | Low | Avoids cache-revision drift; but contradicts the plugin's own `@latest`. Do not pin by default |
| Downloading Playwright's own Chromium into `~/.cache/ms-playwright` | Anti-feature on Bazzite | n/a | Large, drifts, defeats the Flatpak fix |

## Feature Dependencies

```
999.18 skill rewrite (rules, per-terminal clear/word table, conflict rule)
   -> 999.19 kitty / WezTerm / Konsole verification / herdr pass-through
   -> 999.20 Ghostty   (needs new _sync_ghostty + keys region)
   -> 999.21 Herdr IDE (terminal defaults only if it hosts a terminal)
   -> 999.22 iTerm2    (Dynamic Profile writer; blocked on owner naming items 4 and 5)
Xcode CLT entry -> brew (requires edge, detection-only cycle break)
gh-stack -> gh (requires)
Playwright MCP -> Flatpak Chrome present + managed-rc tweaks + agent_settings.py (Cursor env)
AWS CLI, Bruno -> independent; follow the skill's method ladder
Every terminal row -> terminal sync (Linux zsh), install tuning (post_install owned region), receipts, config_paths/uninstall footprint
```

Existing-feature dependencies to respect: zsh sync is Linux-only by design; `post_install` owned regions are stripped with the tool and carry a receipt record; `config_paths` need a denylist check (never `~/.aws`, never Bruno collections); present-host gating for agent settings; zero sudo; real installs only in containers; macOS never exercised on a real host.

## MVP Recommendation

Prioritize (this order):
1. Skill rewrite with the three rules, the per-terminal "clear" meaning table and the conflict rule (999.18). Everything else is blocked on it.
2. kitty and WezTerm keys regions (resolve the kitty `ctrl+shift+k` clash explicitly), Konsole verification, herdr pass-through check.
3. AWS CLI (official script + `aws update`), gh-stack (script method, full URL), Bruno (cask + AppImage `raw=true`): small, mechanical entries on existing method kinds.
4. Ghostty macOS cask plus keys; Linux only if a Bazzite-safe route is found.
5. Xcode CLT as detection plus handoff (no sudo).
6. Playwright MCP env tweak (shell rc plus Cursor `env`), gated on Flatpak Chrome.

Defer: iTerm2 colors / focus cursor / agent extension until the owner names the products; Herdr IDE terminal defaults until it is confirmed to embed a terminal; Dynamic Profile as the default profile; Linux IDE keybindings for IDEs not yet researched.

## Research flags for phases

- Phase 999.18: needs the clear-meaning decision (scrollback only vs both) from the owner before kitty/WezTerm/Ghostty work.
- Ghostty Linux and Herdr IDE: need hands-on packaging research in a container (Linux route, script footprint).
- iTerm2: needs key-name verification on a real Mac or in macOS CI; default-profile selection is an open design question.
- Xcode CLT: needs an owner decision confirming handoff-only (no sudo path exists for unattended install).
- Playwright MCP: owner scope question on registering the server vs only fixing env.

## Sources

- kitty actions and conf: https://sw.kovidgoyal.net/kitty/actions/ , https://sw.kovidgoyal.net/kitty/conf/ (HIGH)
- WezTerm default keys: https://wezterm.org/config/default-keys.html (HIGH)
- Ghostty source: https://github.com/ghostty-org/ghostty `src/config/Config.zig`, `src/input/Binding.zig` (HIGH)
- iTerm2 Dynamic Profiles: https://iterm2.com/documentation-dynamic-profiles.html ; Option key docs https://iterm2.com/3.5/documentation-preferences-profiles-keys.html (HIGH/MEDIUM)
- Konsole shortcut history: https://bugs.kde.org/show_bug.cgi?id=282593 , https://bugs.kde.org/show_bug.cgi?id=427577 , https://bugs.kde.org/show_bug.cgi?id=435548 (MEDIUM)
- AWS CLI install and uninstall: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html , https://docs.aws.amazon.com/cli/latest/userguide/uninstall.html (HIGH)
- gh-stack: https://github.com/github/gh-stack (HIGH)
- Herdr app: https://herdr.dev/download/ (MEDIUM)
- Bruno: https://docs.usebruno.com/get-started/bruno-basics/download (MEDIUM-HIGH)
- Playwright MCP on Bazzite: `.planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md` (HIGH, tested in-repo)
- Repo: `.planning/todos/pending/*.md`, `.planning/todos/completed/2026-10-15-add-iterm2-...md`, `.planning/ROADMAP.md` 999.18-999.22, `installer/terminal_shell.py:477-482`, `.claude/skills/tool-onboarding/SKILL.md:180-195`
- Unverified (from memory, no source fetched): iTerm2 Cmd+K default, WezTerm option-key flags and `ScrollbackAndViewport`, Xcode CLT sudo/GUI-dialog behavior, Ghostty Linux packaging, zsh `ESC b` defaults.
