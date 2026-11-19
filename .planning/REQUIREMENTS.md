# Requirements: tools-installer

**Defined:** 2026-11-16
**Milestone:** v0.51.0 Onboard terminal tools
**Core Value:** A developer can go from a bare machine to a working, correctly-ordered install (system prerequisites -> user tools -> AI-agent tooling) entirely through the catalog, with dependency drag-in resolving automatically and no manual ordering knowledge required, and every screen tells the truth about what is on the host.

Research: `.planning/research/SUMMARY.md` (owner decisions recorded below, 2026-11-16).

## v0.51.0 Requirements

### Tool-onboarding skill (SKILL)

- [ ] **SKILL-01**: The tool-onboarding skill states the terminal and IDE defaults as rules applied without asking the user: (a) zsh is the launched shell on Linux, Bazzite included; (b) Option/Alt+Left/Right moves by word on macOS, by binding only those two chords, never the global Option-as-Alt switch; (c) Cmd+K on macOS and Ctrl+Shift+K on Linux clear the screen and the scrollback; (d) a new tab, window or pane opens in the current directory. Only extras are asked.
- [ ] **SKILL-02**: The skill carries a closed per-terminal table (each terminal's config file, how each default is met or already met by the vendor, and the reload behavior), and a test fails when a terminal or IDE entry in `installer/registry.toml` has no row.
- [ ] **SKILL-03**: The skill's conflict rule: a binding the user already defines is never overridden (the result is reported as `partial: kept yours`); a vendor default that conflicts is overridden only with an install note that names the displaced default.
- [ ] **SKILL-04**: The skill's research step records, per macOS app, how it installs, uninstalls and is configured, and whether its method can place the bundle in `~/Applications` (a vendor installer that takes a destination, as kitty's does; a `.zip` or `.dmg` the installer extracts; a cask through `--appdir`) instead of `/Applications`, which restricted machines deny; where the method allows it the bundle goes to `~/Applications`, and every app that ships a CLI gets that CLI linked into `~/.local/bin` so it runs from the command line. Where no method allows a user location, the entry says why.
- [ ] **SKILL-05**: The skill's macOS testing rule: each macOS behavior is a pure config generator with a golden-file test that runs on both OSes, macOS CI covers the file paths, and the real-Mac check is a UAT line marked deferred to the owner's Mac.
- [ ] **SKILL-06**: skill-judge scores the skill before and after the rewrite, and the after score is not lower.

### Terminal keys mechanism (KEYS)

- [ ] **KEYS-01**: One shared terminal-keys mechanism keyed by registry tool id applies, checks and strips each terminal's owned keys region; Alacritty moves into it first with its behavior and tests unchanged.
- [ ] **KEYS-02**: For every terminal in the mechanism, a missing or drifted keys region shows `≈ apply install tuning`, a reconfigure re-applies it, and an uninstall strips it with the tool.
- [ ] **KEYS-03**: The clear shortcut is the same on every terminal: Cmd+K (macOS) and Ctrl+Shift+K (Linux) send Ctrl+L, and the installer's managed zsh configuration makes Ctrl+L clear the screen and the scrollback at the prompt, so Ctrl+L also works and the keys behave the same inside a herdr pane.
- [ ] **KEYS-04**: A new tab, window or pane opens in the current directory on every terminal of this milestone; the installer writes it only where the vendor default does not already do it.

### Terminals already in the catalog (TERM)

- [ ] **TERM-01**: kitty meets SKILL-01 on both OSes: Option+Left/Right word navigation on macOS without the global switch, the KEYS-03 clear on Cmd+K and on Linux Ctrl+Shift+K (displacing kitty's default `scroll_line_up`, named in the install note), and KEYS-04; its macOS install no longer writes into `/Applications` (SKILL-04).
- [ ] **TERM-02**: WezTerm meets SKILL-01 on both OSes through its Lua owned region, which extends the user's `config.keys` instead of replacing it; the shell-region marker check matches exact marker lines so the keys region is never taken for it.
- [ ] **TERM-03**: Alacritty's clear moves to the KEYS-03 behavior (screen and scrollback); its Linux Alt+Left/Right rows stay (owner decision, 2026-11-16: word navigation is required on macOS, optional on Linux, and not extended to other Linux terminals).
- [ ] **TERM-04**: Konsole is checked, not rewritten: the installer confirms its stock Ctrl+Shift+K clear and writes a binding only when the user has removed it; its zsh sync is unchanged.
- [ ] **TERM-05**: Inside a herdr pane, Option/Alt+Left/Right and the clear shortcut reach the shell (an observable byte-level test); a pass-through setting is written only if herdr intercepts them.

### New terminals (NTERM)

- [ ] **NTERM-01**: Ghostty is in the catalog: the official cask on macOS (user-writable app location), a digest-verified community AppImage on Linux and Bazzite with a visible "community build" note, and pacman on Arch; its shell syncs to zsh on Linux and it meets SKILL-01 through its owned keys region.
- [ ] **NTERM-02**: iTerm2 is in the catalog as a macOS-only cask with an installer-owned Dynamic Profile that sets Option as Esc+, the KEYS-03 clear, new tabs, windows and panes in the current directory, and the requested color scheme; the profile is made the default profile, and an uninstall restores the previous default.
- [ ] **NTERM-03**: The Herdr desktop app (`herdrdev/herdr-app`) is in the catalog as an entry distinct from the `herdr` multiplexer: a user-scope `install.sh` on Linux and the cask on Apple Silicon macOS; it meets SKILL-01 through its own keys files, displacing its Linux Ctrl+Shift+K picker binding with an install note.

### Other onboardings (ONB)

- [ ] **ONB-11**: Xcode CLT is detected on macOS and, when missing, the installer shows the exact `xcode-select --install` command for the user to run; it never runs it and offers no uninstall.
- [ ] **ONB-12**: AWS CLI v2 installs through the official user-scope `install.sh` first (no `--system`, gpg verification kept) with brew `awscli` as the fallback, updates with `aws update`, and an uninstall never touches `~/.aws`.
- [ ] **ONB-13**: Bruno installs through the cask on macOS and a digest-verified AppImage per architecture on Linux; the `bru` CLI is out of scope.
- [ ] **ONB-14**: gh-stack installs with `gh extension install https://github.com/github/gh-stack`, is detected through `gh extension list`, updates with `gh extension upgrade stack`, is removed with `gh extension remove stack`, and an unauthenticated `gh` never blocks or prompts.
- [ ] **ONB-15**: Playwright MCP is registered in each agent host present with the pinned `bunx @playwright/mcp@0.0.85`, never overwriting an existing `playwright` server entry; on Bazzite the Flatpak Chrome path is exported when the wrapper exists; a write into `~/.claude/settings.json` asks for consent first.

### Registry update bot (BOT)

Ingested 2026-11-19 from the update-automation todos and `.planning/research/2026-11-17-update-automation.md`; open owner questions in `.planning/intel/context.md`.

- [ ] **BOT-01**: A scheduled or dispatched GitHub Actions workflow runs `verify-registry --write` and pushes a `bot/registry-<date>` branch only when `installer/registry.toml` changed, with `version`, `sha256` and `verified` bumped together.
- [ ] **BOT-02**: The checks that branch protection requires run on the bot branch head (by `workflow_dispatch` of `ci.yml` or a PAT/App token, owner's choice), verified once on a throwaway branch.
- [ ] **BOT-03**: The bot never pushes to `main`; its change reaches `main` only by branch push, green CI and fast-forward, and the weekly read-only drift workflow keeps `contents: read`.
- [ ] **BOT-04**: A `verify-registry` flag makes a `--write` run skip changes that only touch the `verified` date, so a bot branch never carries a date-only diff.

### Daily update check (NOTIFY)

- [ ] **NOTIFY-01**: The Schedules engine has a daily `check-updates` row that runs the version refresh headless through `--run-schedule`, logs one `ok: N updates available` line and changes no tool.
- [ ] **NOTIFY-02**: The scheduled check refreshes versions despite the 7-day cache staleness window (`installer/version_cache.py:44`).
- [ ] **NOTIFY-03**: The runner sends a desktop notification only when the outdated set changed since the last run (unless the owner chooses every run).
- [ ] **NOTIFY-04**: On Linux the notification goes through `notify-send` with the session bus address passed to the child; without `notify-send` the run logs `notify skipped` and still exits ok.
- [ ] **NOTIFY-05**: On macOS the notification goes through `osascript display notification`; a failure logs `notify skipped` without failing the run, the row detail names the one-time permission, and the real-Mac check is a UAT line deferred to the owner's Mac.
- [ ] **NOTIFY-06**: When in scope (owner decision), the check compares `git ls-remote origin main` with the checkout HEAD and logs one self-update line, with no API call and no pull.

### Opt-in auto-update (AUTOUPD)

- [ ] **AUTOUPD-01**: Schedules has an `update-all` row that is off by default and never a Policies row; once the user sets it, the installer never changes it on its own (amends 24.2 SCHED-01 with a per-row default).
- [ ] **AUTOUPD-02**: `update-all` updates package managers first (ranked by `resolve._RANK`), then their dependents grouped by owner and ordered by `deps.resolve_dependencies`.
- [ ] **AUTOUPD-03**: When a manager's update fails, each of its dependents is skipped and logged as skipped.
- [ ] **AUTOUPD-04**: `update-all` reuses `UpdateService`, `update_refusal`, `stdin=DEVNULL` children, `HOMEBREW_NO_SUDO` and the run lock; refused tools are skipped with their reason, a held lock makes the run refuse, and no path runs sudo, pkexec or doas.
- [ ] **AUTOUPD-05**: Brew casks are excluded from `update-all` on macOS by default.
- [ ] **AUTOUPD-06**: An `update-all` run writes one run-log line per tool while the shared schedule log keeps one summary line per schedule id.
- [ ] **AUTOUPD-07**: A tool also covered by a per-tool agent-CLI schedule row is updated at most once per day.
- [ ] **AUTOUPD-08**: `update-all` is exercised end to end in a disposable container (never on the developer host), and whether `uv self update` is safe under `uv run` is verified there.

## Future Requirements

- **MACAPP-01**: Every existing macOS app entry (VS Code, Sublime Text, draw.io and the rest) is reviewed against SKILL-04 through the skill.
- **SKILL-07**: IDE keybindings on Linux (VS Code, Cursor, Antigravity) follow the terminal defaults.
- iTerm2 items 4 and 5 ("Show Focus Cursor", the agent-collaboration extension) once the owner names the products.

## Out of Scope

| Feature | Reason |
|---------|--------|
| The global Option-as-Alt switch | Breaks `@`, `|`, `\` and `#` on the owner's Spanish layout |
| Alt+Left/Right word navigation on Linux terminals other than Alacritty | Owner decision 2026-11-16; Ctrl+Left/Right is the Linux convention |
| New method kinds (`dmg`, `pkg`, `flatpak`, `snap`, `appimage`, `gh_extension`) | Every tool fits an existing kind |
| The `bru` CLI | Owner decision 2026-11-16 |
| Policies rows or TUI questions for these keys | Install tuning applies with no question (TUNE doctrine) |
| `sudo`, `softwareupdate`, `installer -target /`, `gh auth login` in any executor | Zero-sudo rule and no interactive login |

## Owner decisions (2026-11-16)

- Clear means screen and scrollback; the shortcut is Modifier+K (Cmd on macOS, Ctrl+Shift on Linux), and Ctrl+L clears too.
- kitty's Linux Ctrl+Shift+K default is replaced, with a note.
- "Herdr IDE" is the Herdr desktop app (`herdrdev/herdr-app`).
- Konsole: verify and leave alone.
- Xcode CLT: detect and hand off the command.
- AWS CLI: official script first, brew fallback.
- Playwright MCP: register the pinned server and fix the Flatpak Chrome path.
- Alacritty keeps its Linux Alt rows; no extension to other Linux terminals.
- Ghostty on Linux: the community AppImage, labelled.
- iTerm2: the profile becomes the default; new tabs, windows and panes open in the current directory.
- Same-directory new tab, window or pane is a rule for every terminal.
- macOS apps: bundle in `~/Applications` and CLI in `~/.local/bin` where the method allows it; the skill researches each tool to decide.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKILL-01 | Phase 27 | Pending |
| SKILL-02 | Phase 27 | Pending |
| SKILL-03 | Phase 27 | Pending |
| SKILL-04 | Phase 27 | Pending |
| SKILL-05 | Phase 27 | Pending |
| SKILL-06 | Phase 27 | Pending |
| KEYS-01 | Phase 28 | Pending |
| KEYS-02 | Phase 28 | Pending |
| KEYS-03 | Phase 28 | Pending |
| KEYS-04 | Phase 28 | Pending |
| TERM-01 | Phase 29 | Pending |
| TERM-02 | Phase 29 | Pending |
| TERM-03 | Phase 29 | Pending |
| TERM-04 | Phase 29 | Pending |
| TERM-05 | Phase 29 | Pending |
| NTERM-01 | Phase 30 | Pending |
| NTERM-02 | Phase 31 | Pending |
| NTERM-03 | Phase 31 | Pending |
| ONB-11 | Phase 32 | Pending |
| ONB-12 | Phase 32 | Pending |
| ONB-13 | Phase 32 | Pending |
| ONB-14 | Phase 32 | Pending |
| ONB-15 | Phase 32 | Pending |
| BOT-01 | Phase 33 | Pending |
| BOT-02 | Phase 33 | Pending |
| BOT-03 | Phase 33 | Pending |
| BOT-04 | Phase 33 | Pending |
| NOTIFY-01 | Phase 34 | Pending |
| NOTIFY-02 | Phase 34 | Pending |
| NOTIFY-03 | Phase 34 | Pending |
| NOTIFY-04 | Phase 34 | Pending |
| NOTIFY-05 | Phase 34 | Pending |
| NOTIFY-06 | Phase 34 | Pending |
| AUTOUPD-01 | Phase 35 | Pending |
| AUTOUPD-02 | Phase 35 | Pending |
| AUTOUPD-03 | Phase 35 | Pending |
| AUTOUPD-04 | Phase 35 | Pending |
| AUTOUPD-05 | Phase 35 | Pending |
| AUTOUPD-06 | Phase 35 | Pending |
| AUTOUPD-07 | Phase 35 | Pending |
| AUTOUPD-08 | Phase 35 | Pending |

**Coverage:**
- v0.51.0 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0 ✓

---
*Requirements defined: 2026-11-16*
*Last updated: 2026-11-19 after ingesting the update-automation todos (BOT, NOTIFY, AUTOUPD; Phases 33-35)*
