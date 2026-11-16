# Domain Pitfalls

**Domain:** Adding terminal key tuning and five tool onboardings to the tools-installer (v0.51.0 "Onboard terminal tools")
**Researched:** 2026-11-16
**Method:** Read `PROJECT.md`, `AGENTS.md` and `installer/terminal_shell.py` (Alacritty keys, Konsole, WezTerm, kitty precedents), then applied terminal and installer domain knowledge. No web lookup was run. Claims about vendor defaults come from model knowledge, not from fetched docs. Each is tagged `[verify]` (confirm against vendor docs or a container before a plan relies on it) or `[code]` (read in this repo).

**Phase labels used below** (propose these names to the roadmap):
- **P1** Tool-onboarding skill refactor (rules, not questions)
- **P2** Defaults for kitty, WezTerm, Konsole, herdr pass-through
- **P3** Ghostty, Herdr IDE, iTerm2 onboarding
- **P4** Xcode CLT, Bruno, AWS CLI, gh-stack, Playwright MCP

## Critical Pitfalls

### Pitfall 1: Option-as-Alt breaks composed characters on non-US layouts
**What goes wrong:** The easy way to get Option+Left/Right word navigation is `macos_option_as_alt` (kitty), `macos-option-as-alt` (Ghostty), `send_composed_key_when_left_alt_is_pressed` (WezTerm) or iTerm2's "Left/Right Option key = Esc+". Each turns every Option chord into Meta, so Option-composed characters stop working. On the Spanish ISO layout, `@` is Option+2, `#` is Option+3, `|` is Option+1 and `\` is Option+Shift+7. The owner chats in Spanish, so this is a real use case, not a hypothetical.
**Why it happens:** One global switch is simpler than binding two keys.
**Consequences:** The owner cannot type `@`, `|`, `\` or `#` in the terminal. It is a daily-use regression that is hard to trace back to a "word navigation" change.
**Prevention:**
- Never set the global option-as-alt switch. Bind only Option+Left and Option+Right to send `ESC b` and `ESC f`, per terminal. Examples: kitty `map opt+left send_text all \x1bb`, Ghostty `keybind = alt+left=esc:b`, WezTerm a `SendString('\x1bb')` key entry, iTerm2 a Keyboard Map entry. The Alacritty tuning already follows this pattern (`_KEY_BINDINGS`, `\u001bb`/`\u001bf`) [code].
- Put the rule in the skill (P1): "bind two keys, never the global switch".
- Add a regression test over every generated macOS config: the global option-as-alt key must be absent.
**Detection:** A generated config contains `macos_option_as_alt`, `macos-option-as-alt` or iTerm2 "Option Key Sends" set to Esc+. Manual check on the owner's Mac layout: type `@` and `|`.
**Phase:** P1 states the rule; P2 and P3 implement and test it.
**Confidence:** HIGH for the mechanism, `[verify]` for each terminal's exact key-name syntax.

### Pitfall 2: A new region silently overrides the user's own bindings
**What goes wrong:** kitty is last-wins: a later `map` replaces an earlier one. A marker region appended to the end of `kitty.conf` therefore beats the user's `map ctrl+shift+k ...`. In WezTerm, assigning `config.keys = {...}` replaces the user's table instead of extending it. Ghostty `keybind` is also last-wins.
**Why it happens:** The Alacritty tuning is safe because `_keys_plan` parses the TOML and skips bindings already taken, reporting `partial: you already bind X` [code]. Line-oriented formats (kitty, Ghostty) have no parser, so the check gets skipped.
**Consequences:** The installer overrides the user's bindings, which the project's rule "detect and configure, never blind-overwrite" (D-01a) forbids. Uninstall then removes a region the user thought they controlled.
**Prevention:**
- Per terminal, choose the region position so the user wins: top of file for last-wins formats (kitty, Ghostty), so the user's own lines override ours.
- For WezTerm, never assign the key table. Extend it: `config.keys = config.keys or {}` followed by `table.insert`, inside the owned region. Test the edge case where the user's file already defines `config.keys`.
- Detect an existing user binding for the same chord (a regex over uncommented lines outside our region) and skip with a `partial:` report, like the Alacritty path.
- Refuse and report when the file uses `include` or `config-file` in a way that cannot be resolved, as `_imports_files` does for Alacritty [code].
**Detection:** A test fixture with a user-defined binding for the same chord outside the region must come out unchanged, with a conflict message.
**Phase:** P2 (kitty, WezTerm), P3 (Ghostty, iTerm2).
**Confidence:** HIGH for the Alacritty precedent [code]; `[verify]` for the precedence rules of kitty, Ghostty and WezTerm.

### Pitfall 3: Rewriting a file the terminal rewrites itself (Konsole KConfig, iTerm2 plist)
**What goes wrong:**
- Konsole: `konsolerc` is KConfig, which drops comment lines when Konsole saves. `_revert_konsole` already documents this (CR-06): the marker comments vanish while the value stays [code]. Key shortcuts live in a separate XML file (`konsoleui.rc` under kxmlgui, `[verify]` the path on Plasma 6), also rewritten by the app.
- iTerm2: settings live in `com.googlecode.iterm2.plist`, held in NSUserDefaults and cached by `cfprefsd`. A direct file edit while iTerm2 runs is overwritten when it quits. "Load preferences from a custom folder" makes iTerm2 ignore the default plist entirely.
**Why it happens:** Treating every config as a text file with comment markers.
**Consequences:** Ownership proof is lost, so removal either leaves our keys behind or deletes the user's. A plist edit is silently lost or corrupts the file.
**Prevention:**
- Konsole: first check whether Ctrl+Shift+K is already the default. `[verify]` Konsole's "Clear Scrollback" is believed to be Ctrl+Shift+K by default, which would make the Konsole clear rule a no-op that only reports "already default". Write a shortcut only when it differs. If one is written, keep the CR-06 pattern: a state file under `~/.local/share/tools-installer/` is the ownership proof, not comments.
- iTerm2: use Dynamic Profiles (JSON in `~/Library/Application Support/iTerm2/DynamicProfiles/`), which iTerm2 loads live and never rewrites. Never hand-edit the plist. If the default profile must change, use `defaults write` (goes through cfprefsd) and tell the user to restart iTerm2. `[verify]`
- Detect the custom-prefs-folder setting (`defaults read com.googlecode.iterm2 PrefsCustomFolder`, `LoadPrefsFromCustomFolder`) and report `skipped: iTerm2 loads preferences from a custom folder`.
- Every owned file records a receipt and a fingerprint, so removal needs no comment survival.
**Detection:** After a simulated "app rewrite" (strip comments from the fixture), uninstall must still restore the prior state. Add that fixture test for each new KConfig-like target.
**Phase:** P2 (Konsole), P3 (iTerm2).
**Confidence:** HIGH for KConfig comment loss [code]; MEDIUM for iTerm2 `[verify]`.

### Pitfall 4: Xcode CLT needs a GUI prompt and root, in conflict with zero-sudo
**What goes wrong:** `xcode-select --install` opens a macOS dialog the user must click. The headless route (`touch /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress`, then `softwareupdate -i "Command Line Tools for Xcode-..."`) needs root. Homebrew's own installer asks for sudo on first install.
**Why it happens:** The PROJECT.md owner decision says "brew install.sh or softwareupdate", and both routes pull in sudo at some step. A skill rule "run the install" violates AGENTS.md's zero-sudo rule.
**Consequences:** Either a hidden `sudo` call (rule violation) or a hang in the TUI child, which has no usable tty (O1, LIFE-02 [code]). In CI, macos-latest already has CLT, so the missing-CLT path is never exercised.
**Prevention:**
- Model CLT as detect-and-handoff: detect with `xcode-select -p` plus a probe that `/usr/bin/git` is a real binary, not the stub (REG-xx macOS stub detection already exists [code]). If missing, show the exact command for the user to run, matching how native package installs are handed off.
- Do not write a script method that runs `softwareupdate -i`. Record the owner decision's rationale in the registry comment.
- Receipts: CLT is native-owned, so it is never removable by this installer (handed off).
- Order: `requires = ["xcode-clt"]` or `recommends` for brew and compiled tools, so the plan can say "blocked: install CLT first" instead of failing deep inside a build.
**Detection:** Any `sudo`, `softwareupdate` or `xcode-select --install` string in an executor or script method. Add a grep-style test, as the project does for sudo elsewhere.
**Phase:** P4.
**Confidence:** HIGH.

### Pitfall 5: AWS CLI pkg installer needs root
**What goes wrong:** The macOS `AWSCLIV2.pkg` installs to `/usr/local` with `installer -pkg ... -target /`, which needs root. The Linux `./aws/install` writes to `/usr/local/aws-cli` and needs sudo by default.
**Why it happens:** Copying the vendor's quick-start commands into the registry.
**Consequences:** A hidden sudo call, or a failed install on Bazzite where `/usr/local` is not writable the usual way.
**Prevention:**
- Prefer the package manager that is already user-level: `brew install awscli` on macOS and Linux (including Bazzite, since Homebrew is the immutable-host route). This also leaves update and removal to Homebrew with no new method kind.
- If a script/tarball fallback is wanted on Linux, use the vendor's user install: `./aws/install -i ~/.local/aws-cli -b ~/.local/bin` (documented by AWS, `[verify]`). It needs `paths` and `remove` declared per the lifecycle contract, and a checksum or signature check.
- Do not use the macOS pkg. AWS documents a current-user pkg install through a `choices.xml`, `[verify]`, but it adds complexity for no gain over brew.
- Beware the old v1 `awscli` PyPI package (v1 and v2 conflict): pin the brew formula `awscli`, which is v2.
**Detection:** `installer -pkg` or `/usr/local/aws-cli` in a registry method.
**Phase:** P4.
**Confidence:** HIGH for the root requirement, `[verify]` for the user-level flags.

### Pitfall 6: Playwright MCP and Flatpak or immutable-host browsers
**What goes wrong:** Playwright MCP (`@playwright/mcp`) looks for a managed browser under `~/.cache/ms-playwright` or a system Chrome at `/opt/google/chrome/chrome`. Two failure modes:
- `npx playwright install-deps` (the OS libraries step) calls `apt` with sudo and officially targets Ubuntu and Debian. On Fedora and Bazzite it needs manual libraries or runs with warnings. `[verify]`
- A browser installed as a Flatpak (Chrome, Firefox) lives behind the sandbox, so Playwright's path lookup fails and launching the Flatpak binary directly does not work.
**Why it happens:** The MCP "just works" on the developer's Ubuntu laptop and the fallback is assumed.
**Consequences:** The MCP registers fine and then every browser tool call fails at runtime, which the installer reports as healthy.
**Prevention:**
- Make the install honest: after registration, run a smoke check (the `smoke` param exists [code]) that launches a headless browser, not just `--version` on the package.
- On immutable hosts do not use sudo or `install-deps`. Hand off the exact command or run the browser download only (`npx playwright install chromium`, user-level into `~/.cache`), and report the missing-library case as `partial`.
- Do not point `--executable-path` at a Flatpak browser. If a system browser is wanted, document `--browser` channel and `--executable-path` as the user's choice, not an installer default.
- Pin the `@playwright/mcp` version in the MCP config, since `npx @playwright/mcp@latest` re-resolves on every agent start (supply chain and drift). Install through the existing bun/npm priority and the closed postinstall mechanism, not an inline shell string.
- Register through the existing `agent_settings.py` writer for each present host; never blind-overwrite a user's existing `mcpServers.playwright` entry, and record it in `receipt.hooks` so it follows hosts in and out (Phase 23 design [code per PROJECT.md]).
**Detection:** Container e2e on Fedora shows `browserType.launch: Executable doesn't exist` or `error while loading shared libraries`.
**Phase:** P4. Research flag: needs a Bazzite or Fedora container proof.
**Confidence:** MEDIUM `[verify]`.

### Pitfall 7: macOS-only behavior is untestable without a Mac
**What goes wrong:** Option/Alt navigation, Cmd+K, iTerm2, Ghostty on macOS, Xcode CLT and `~/Library` paths cannot run locally. The project has never run on macOS or Apple Silicon (PROJECT.md, 999.7). CI's macos-latest only proves the code imports and the unit tests pass, and it ships with CLT and brew already present.
**Why it happens:** Passing CI looks like verification.
**Consequences:** Claims in SUMMARY or VERIFICATION that "macOS works" with no evidence. The first real macOS run is the owner's.
**Prevention:**
- Split each macOS feature into a pure function (`config text in -> config text out`, path resolution from `Platform` and an injected `HOME`) that Linux tests cover fully with fixtures, plus a thin macOS-only I/O edge covered by the macos-latest job.
- Run the pure generators in CI on both OSes, and add a macos-latest smoke step that asserts the resolved paths (`~/Library/Application Support/...`) against a scratch `HOME`.
- Mark every macOS-only requirement `UAT: deferred to owner Mac` in the verification report. The owner already accepted "macOS deferred" for agent-run UATs, so record it as an explicit residual, not as passed.
- Never write "verified on macOS" in a summary unless the CI log shows the specific assertion.
- Keep macOS config content byte-comparable with a golden file reviewed against vendor docs.
**Detection:** A plan whose done criteria say "works on macOS" with no CI assertion named.
**Phase:** every phase; P1 adds the rule to the skill ("macOS items: pure generator + golden file + deferred UAT line").
**Confidence:** HIGH.

## Moderate Pitfalls

### Pitfall 8: Vendor-default key conflicts (clear shortcut)
**What goes wrong:** Ctrl+Shift+K is not free everywhere. `[verify]` kitty: `kitty_mod+k` is `scroll_line_up` by default. WezTerm: Ctrl+Shift+K and Cmd+K are both `ClearScrollback('ScrollbackOnly')` by default, so the rule is already met. Konsole: probably already "Clear Scrollback". iTerm2: Cmd+K is already "Clear Buffer". Ghostty on macOS: Cmd+K is already `clear_screen`.
**Consequences:** Rebinding kitty's Ctrl+Shift+K silently removes scroll-line-up. Writing redundant bindings into terminals whose default already satisfies the rule bloats the footprint and creates removal work for nothing.
**Prevention:** Make the skill rule outcome-based ("Cmd+K or Ctrl+Shift+K clears the screen and scrollback"), and per terminal first test whether the default already satisfies it; write a binding only if not, and report `already default`. For kitty, report the displaced default (`scroll_line_up`) in the install note. Use the terminal's native clear action, not `send_text \x0c` (Ctrl+L), because Ctrl+L only redraws the prompt and inside nvim or a TUI it does the wrong thing.
**Detection:** A generated binding whose chord appears in a vendor-defaults table.
**Phase:** P1 (rule wording), P2 and P3 (per-terminal check).

### Pitfall 9: A multiplexer (herdr, tmux) intercepts the keys
**What goes wrong:** Inside herdr or tmux, the terminal's Alt+Left byte sequence reaches the multiplexer first. tmux needs `xterm-keys` or a `bind` to pass `\e[1;3D`; many multiplexers use Alt chords as their own prefix-less shortcuts. If the terminal sends `ESC b`, a multiplexer with an escape-time delay can misread it as Escape followed by `b`.
**Consequences:** Word navigation works in a bare terminal and breaks inside herdr, which is where the owner works (herdr tabs and panes).
**Prevention:**
- Choose one wire format for the whole stack: `ESC b` / `ESC f` (what Alacritty already sends [code]) is the readline default, so zsh's emacs keymap and bash handle it without `.zshrc` edits. The common `Alt+Left` = `\e[1;3D` form is not bound by zsh by default and would need `bindkey` lines.
- For "herdr pass-through" (999.19), define the requirement as a test of observable behavior: bytes typed in the terminal arrive at the shell inside herdr unchanged. Read herdr's config and keybinding docs first. Which keys herdr consumes is unverified here.
- Do not add herdr bindings that shadow the terminal's own. Pass-through means herdr does nothing for those chords.
**Detection:** `cat -v` inside herdr after pressing Option+Left prints `^[b` outside herdr but something else, or nothing, inside.
**Phase:** P2. Research flag: read herdr's key handling before planning.
**Confidence:** MEDIUM `[verify]`.

### Pitfall 10: Config reload behavior differs per terminal
**What goes wrong:** WezTerm reloads on file save (default `automatically_reload_config`). kitty needs Ctrl+Shift+F5 or `SIGUSR1`. Ghostty needs its reload action. iTerm2 needs a restart for plist changes (Dynamic Profiles reload live). Konsole reads the profile on new tabs. `[verify]` for each.
**Consequences:** UAT reports "binding did not apply" because the running terminal was not reloaded, or an install note tells the user to restart when nothing is needed.
**Prevention:** Put a `reload` fact in a closed per-terminal table (the same table as the defaults), have the install result print one accurate line ("open a new window", "press ...", "restart iTerm2"), and make agent UAT launch a fresh terminal process in the container. Never send signals to the user's running terminal from the installer (host safety).
**Phase:** P2 and P3.

### Pitfall 11: Flatpak and sandboxed terminals use other config paths and shells
**What goes wrong:** On Bazzite, terminals are often Flatpaks. Their config is under `~/.var/app/<app-id>/config/...`, not `~/.config`. A Flatpak terminal also runs its shell inside the sandbox, so "zsh as launched shell" points at a host zsh the sandbox cannot see (or needs `flatpak-spawn --host`). `[verify]`
**Consequences:** The installer writes a correct file that no running terminal reads, and reports success. Receipts claim ownership of a no-op.
**Prevention:** Detect the install flavor (native, Homebrew, Flatpak) in the same place that resolves the executable, and derive the config path from it. For Flatpak with a host shell, report `skipped: sandboxed terminal` rather than writing a dead file. Reuse the Distrobox/Flatpak decisions already made for Alacritty (O5). kitty has no Linux method on immutable Bazzite (07-03 decision), so P2 must not assume kitty exists there.
**Detection:** The config file exists but `flatpak info` shows the terminal installed as a Flatpak.
**Phase:** P2, P3 (Ghostty on Bazzite, Herdr IDE).

### Pitfall 12: Ghostty and other tools with two config locations
**What goes wrong:** Ghostty on macOS reads both `$XDG_CONFIG_HOME/ghostty/config` and `~/Library/Application Support/com.mitchellh.ghostty/config`, with one taking precedence. `[verify]` Writing to the wrong one means the user's real file wins and our region is ignored, or ours overrides theirs.
**Prevention:** Resolve the effective file the way the app does, document the precedence in the registry comment, and treat the region owner as whichever file the user already has (create the XDG one only when neither exists). Test both layouts with fixtures.
**Phase:** P3.

### Pitfall 13: gh-stack is a gh extension, with auth and arch issues
**What goes wrong:** `gh extension install <owner>/gh-stack` needs `gh` installed first and usually an authenticated, non-rate-limited GitHub API (`gh auth login`, or `GH_TOKEN`). Binary extensions are per-OS and per-arch. Several repos named `gh-stack` exist. Whether `github/gh-stack` is the intended one is unverified.
**Consequences:** Install fails in a fresh container with no auth, or installs the wrong extension. Removal through the file tree would delete extension data the receipt cannot prove.
**Prevention:**
- `requires = ["gh"]`; verify the exact `owner/repo` on GitHub, record the `# Verified {date}` comment (D-01), and pin a tag if the extension supports it.
- The install must not run `gh auth login` (interactive). If unauthenticated, the plan says `blocked: gh not authenticated` with the exact handoff command, instead of a failure mid-install.
- Detect with `gh extension list`, and remove with `gh extension remove`, declared as the method's `remove` command; never delete `~/.local/share/gh/extensions` by path.
- Container e2e: mount no token, so the unauthenticated path is what gets tested, and say so.
**Detection:** The e2e container install exits non-zero with an API rate-limit or auth message.
**Phase:** P4. Research flag: confirm the repo identity and release assets before planning.
**Confidence:** MEDIUM `[verify]`.

### Pitfall 14: Bruno on Linux and Bazzite
**What goes wrong:** The Homebrew cask is macOS-only, and this project's resolver blocks every cask on non-macOS (07-03 decision [code]). Linux distributions are AppImage, deb, rpm, snap and Flatpak (`com.usebruno.Bruno`, `[verify]`).
**Prevention:** macOS = cask. Linux immutable = Flatpak if the project already models Flatpak as a method kind; otherwise a checksum-verified AppImage `github_release` with `raw=true` (the WezTerm precedent). Do not add a new method kind for one tool (v0.50.0 ultra cut). If Flatpak is not a method kind, defer Linux Bruno and say so in the registry comment.
**Phase:** P4.

### Pitfall 15: Rules documented, not enforced, so the next terminal drifts
**What goes wrong:** P1 turns defaults into rules in `SKILL.md`. Prose rules without a test are skipped by the next onboarding, which is how the rtk/graphify postinstall gap sat unnoticed across three phases (Key Decisions, 12.4).
**Prevention:** Keep a closed code table: one row per terminal in the catalog with shell, word-nav, clear, config path, region position, reload note, `already default` flags. Add a test that fails when a terminal or IDE registry entry has no row, in the style of the AST reachability test (Phase 25). The skill refers to the table instead of restating it (one canonical source, as in 12.4-03).
**Phase:** P1 creates the table and test; P2 and P3 fill rows.

### Pitfall 16: Region lifecycle (reconfigure, removal, drift) for the new files
**What goes wrong:** New owned regions skip the receipts and fingerprints that make removal provable, or a re-run duplicates the region, or a malformed marker (user deleted one edge) makes the writer append a second region.
**Prevention:** Reuse `_replace_owned_region`, which rejects malformed markers, and `atomic_write_text`; reconfigure replaces in place; the tuning is written once at install and stripped with the tool, as Alacritty keys do (`alacritty-keys`) [code]. Add the three standard fixture tests per terminal: re-run is a no-op, a user edit outside the region survives, a malformed marker refuses.
**Phase:** P2, P3.

## Minor Pitfalls

### Pitfall 17: Herdr IDE identity is unclear
The "Herdr IDE" product (999.21) is not the herdr multiplexer already in the catalog, as far as the PROJECT.md text shows. Confirm what it is, whether it has a config format, and whether it is installable without a GUI installer before scoping. **Prevention:** a first-plan research step; if no scriptable config exists, onboard install and detection only and record that the defaults rules do not apply, with the reason. **Phase:** P3. Confidence LOW.

### Pitfall 18: Tests touching the real host
New tests for iTerm2, Konsole and Xcode CLT can reach `defaults`, `xcode-select` or `~/Library` on a developer or CI machine. **Prevention:** scratch `HOME`, the subprocess allowlist guard and the real-HOME fingerprint (HOST-03..05 [code per PROJECT.md]); stub `defaults` and `xcode-select` through the allowlist. Never run the real commands outside a container. **Phase:** all.

### Pitfall 19: `make validate` gates on a growing file
`installer/terminal_shell.py` is 1,055 lines. Adding four terminals to it grows it past what review and the 90% coverage gate handle comfortably. **Prevention:** put per-terminal writers in their own module or table-driven functions rather than another 1,000 lines. The skill's table (Pitfall 15) lets most terminals share one "append an owned region to a text file" writer. **Phase:** P2.

## Phase-Specific Warnings

| Phase topic | Likely pitfall | Mitigation |
|-------------|---------------|------------|
| P1 skill refactor | Rules in prose only (15); wording that prescribes a binding instead of an outcome (8); option-as-alt rule missing (1) | Closed per-terminal table plus coverage test; outcome-based rules; macOS items marked as pure generator + golden file + deferred UAT |
| P2 kitty, WezTerm | User bindings overridden (2); `config.keys` replaced (2); kitty ctrl+shift+k displaced (8); reload (10); no Linux kitty on Bazzite (11) | Region at top for last-wins; extend key tables; `already default` check; one reload fact per terminal |
| P2 Konsole | KConfig strips comments (3); default may already satisfy the rule (8); Flatpak path (11) | State-file ownership; write only when default differs |
| P2 herdr pass-through | Multiplexer eats Alt keys (9) | Observable-behavior test; read herdr key docs first; `ESC b`/`ESC f` wire format |
| P3 Ghostty | Two config paths (12); last-wins (2); Flatpak on Bazzite (11) | Resolve effective file; top region; install-flavor detection |
| P3 iTerm2 | Plist rewritten by app (3); custom prefs folder (3); untestable (7) | Dynamic Profiles; detect and skip custom folder; golden file |
| P3 Herdr IDE | Unknown product (17) | Research step first; scope to install and detect if no config |
| P4 Xcode CLT | GUI prompt and sudo (4); CI has CLT already (7) | Detect and hand off; no `softwareupdate` method; grep test for sudo |
| P4 AWS CLI | Pkg needs root (5) | `brew install awscli`; user-level script fallback only |
| P4 Bruno | Cask blocked on Linux (14) | Cask on macOS; AppImage `raw=true` or defer Linux |
| P4 gh-stack | Auth, repo identity, arch (13) | `requires gh`; `gh extension remove`; blocked state when unauthenticated |
| P4 Playwright MCP | Missing libs and Flatpak browser (6); unpinned npx (6) | Smoke launch; user-level browser download; pinned version; `agent_settings.py` writer |

## Sources

- `/var/home/bazzite/git/personal/tools-installer/.planning/PROJECT.md` (constraints, key decisions, Phase 23, 24, 25 precedents) [code]
- `/var/home/bazzite/git/personal/tools-installer/AGENTS.md` (zero sudo, host safety, no real-host mutation) [code]
- `/var/home/bazzite/git/personal/tools-installer/installer/terminal_shell.py`: `_replace_owned_region`, `_revert_konsole` (CR-06 KConfig comment loss), `_KEY_BINDINGS` (`ESC b`/`ESC f`, Ctrl+Shift+K), `_keys_plan` (conflict skip, `include` refusal) [code]
- Vendor behavior (kitty, WezTerm, Ghostty, iTerm2, Konsole defaults and reload; AWS CLI user install; Playwright on Fedora; `gh-stack` identity; Herdr IDE): model knowledge, not fetched. Every such claim is marked `[verify]` and needs a vendor-doc read or a container run before a plan depends on it.
