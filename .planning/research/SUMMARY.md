# Project Research Summary

**Project:** tools-installer
**Milestone:** v0.51.0 "Onboard terminal tools"
**Domain:** Terminal key tuning (word navigation and clear shortcut, per OS) plus eight tool onboardings, inside an existing uv/Textual cross-platform installer
**Researched:** 2026-11-16
**Confidence:** MEDIUM-HIGH overall (terminal defaults read from upstream source at pinned tags; macOS behavior unverified on real hardware)

## Executive Summary

This milestone adds per-terminal key tuning (macOS Option+Left/Right word navigation, and a clear-screen shortcut on Cmd+K or Ctrl+Shift+K) and eight new tool entries (Ghostty, Herdr desktop app, iTerm2, Xcode CLT, Bruno, AWS CLI, gh-stack, Playwright MCP). Almost everything reuses existing machinery. The one structural change is to generalize the Alacritty keys code (`installer/terminal_shell.py:465-768`) into a table-driven `installer/terminal_keys.py`, so kitty, WezTerm, Ghostty and iTerm2 are rows instead of copies. Every new method fits an existing registry kind (`cask`, `github_release` raw AppImage, `script`, `brew`, `bun`). No new kind is needed.

Most terminals already satisfy part of the owner rule. WezTerm (Cmd+K and Ctrl+Shift+K both `ClearScrollback`), Konsole (Ctrl+Shift+K already "Clear Scrollback and Reset"), Ghostty on macOS (Cmd+K `clear_screen`; Option+Left/Right already bound to `esc:b`/`esc:f`) and iTerm2 (Cmd+K Clear Buffer) need nothing written for those defaults. The installer writes only what is missing and reports "already default" for the rest. The real conflicts are kitty's Linux `ctrl+shift+k` (bound to `scroll_line_up`), the Herdr desktop app's Linux `ctrl-shift-k` (bound to `mod.open:picker`), and the global Option-as-Alt switch, which would break Spanish-layout characters (`@ | # \`).

Main risks: (1) the unresolved meaning of "clear" (scrollback only vs screen plus scrollback), which blocks the kitty/WezTerm/Ghostty work; (2) silent overrides of user bindings, which the detect-and-configure doctrine forbids; (3) macOS behavior that cannot be exercised here, so every macOS requirement must be a pure generator with a golden file and a deferred owner-Mac UAT line; (4) the owner decisions below. Build order: skill rewrite first, then the shared mechanism as a behavior-preserving move, then kitty/WezTerm/Konsole/herdr, then Ghostty/iTerm2/Herdr desktop app, then the non-terminal onboardings.

## Owner Decisions

Each carries the researchers' recommended default.

1. **Meaning of "clear" (blocks Phase 1 and all clear-key work).** Scrollback only, or screen plus scrollback? Recommended: clear the visible screen AND scrollback where the terminal offers it (Ghostty `clear_screen`, iTerm2 Clear Buffer, a kitty `clear_terminal` variant); accept native scrollback-only where that is all the terminal offers (WezTerm, Konsole). Pin the choice per terminal in the skill table. Never send Ctrl+L as a substitute.
2. **kitty Linux `ctrl+shift+k` override.** kitty binds it to `scroll_line_up`. Recommended: override with `map ctrl+shift+k clear_terminal ...` and report the displaced default in the install note (the user keeps `ctrl+shift+up`). Alternative: bind nothing (no Linux clear).
3. **Konsole in scope?** Recommended: yes, as verify-and-leave-alone (stock Ctrl+Shift+K is already Clear Scrollback and Reset, source-verified in STACK). Write only if the user remapped it. Konsole stays out of `TERMINAL_KEYS` and uses `_sync_konsole`.
4. **Alacritty Linux word-nav rows (Alt+Left/Right).** The owner rule scopes word navigation to macOS, but Alacritty writes these on Linux too (`installer/terminal_shell.py:477-481`). Keep until a deliberate migration, or drop and migrate. Recommended: keep, flagged as off-rule.
5. **Herdr desktop app Linux `ctrl-shift-k`** (bound to `mod.open:picker`). Recommended: do not override silently; report the conflict or bind a different key.
6. **Herdr desktop app macOS clear key.** Recommended `cmd-k` → `send:\u000c` (Ctrl+L). PITFALLS argues against Ctrl+L for clear; herdr has no documented clear command (UNVERIFIED). The owner confirms or accepts assert-only.
7. **"Herdr IDE" identity.** No product named "Herdr IDE" exists. Best match: the Herdr desktop app (`herdrdev/herdr-app`, v0.1.16). The owner confirms before Phase 4 is planned. Never conflate it with the `herdr` TUI entry.
8. **Herdr desktop app terminal defaults.** STACK says it hosts a terminal (keys in `keys.json`); FEATURES says this is not stated. Recommended: treat it as hosting a terminal and verify the user keys path first.
9. **iTerm2 default profile.** A Dynamic Profile does not become the default. Recommended: ship a "tools-installer" profile and tell the user to select it; no `defaults write` on `Default Bookmark Guid`.
10. **iTerm2 items 4 and 5** (Show Focus Cursor; agent-collaboration extension). Not named by the owner. Do not research or guess. The color scheme can ship in the same JSON.
11. **Xcode CLT.** Confirm handoff-only (print `xcode-select --install`, never run it; zero-sudo). Recommended: yes. FEATURES lists "delegate to brew install.sh" as a default shape; PITFALLS and STACK reject any CLT install step. Resolved toward detect-and-handoff unless the owner says otherwise.
12. **AWS CLI route.** Official user-scope script first with a brew `awscli` fallback (STACK), or brew first (repo PRIO, PITFALLS)? Recommended: official script first on Linux including Bazzite; brew as the macOS fallback. It touches the brew-first ladder, so decide explicitly.
13. **Ghostty on Linux/Bazzite.** The only Bazzite-safe route is a third-party community AppImage (`pkgforge-dev/ghostty-appimage`). Recommended: ship with a visible "community build" label. Never `rpm-ostree`/COPR.
14. **Playwright MCP scope.** Register the server through `postinstall.py` (pinned `bunx @playwright/mcp@0.0.85`), or only fix the Flatpak Chrome environment? STACK recommends registering with pinned bunx; FEATURES says do not pin by default; PITFALLS says pin. The owner decides pinning and whether `~/.claude/settings.json` env writes need consent.
15. **Bruno CLI (`bru`).** Recommended: out of scope this milestone.
16. **gh-stack pinning.** Recommended: unpinned, matching `gh extension upgrade`, unless drift checks are wanted.
17. **Ghostty Linux shell sync.** Recommended: yes, a `_sync_ghostty` that mirrors `_sync_herdr`.

## Vendor-Fact Conflicts (resolved; STACK.md preferred, read from upstream source)

| Fact | Other files said | STACK.md (upstream) | Resolution |
|---|---|---|---|
| Konsole Ctrl+Shift+K default | PITFALLS "believed"; FEATURES Clear Scrollback and Reset | `clear-history-and-reset` = ACCEL+K, source-verified | Stack. Already default; write nothing. |
| WezTerm default clear | FEATURES ScrollbackAndViewport (from memory) | `ClearScrollback="ScrollbackOnly"` for SUPER+k and CTRL+SHIFT+K | Stack. Scrollback only. |
| Ghostty macOS word nav | FEATURES and PITFALLS: write `alt+left=esc:b` and `macos-option-as-alt` | Alt+Left/Right already `esc:b`/`esc:f` in the macOS block of `Config.zig` v1.4.0 | Stack. Write nothing for word nav; never write `macos-option-as-alt`. |
| Ghostty Linux clear | FEATURES no k binding on Linux | No ctrl+shift+k binding; only super+k | Agree. Write `keybind = ctrl+shift+k=clear_screen`. Never `keybind = clear`. |
| Ghostty Linux availability | FEATURES no official Linux binary | Community AppImage v1.4.0 exists | Stack, with the third-party caveat (decision 13). |
| iTerm2 Cmd+K | FEATURES, PITFALLS unverified | `Clear Buffer` keyEquivalent `k` in MainMenu.xib | Stack. Assert only. |
| iTerm2 Option key | FEATURES "Option Key Sends" UNVERIFIED | Key name and enum verified in `ITAddressBookMgr.h` | Stack for key names; Keyboard Map encoding stays LOW. |
| AWS CLI Linux install | PITFALLS script needs sudo by default | User-local by default; sudo only with `--system` | Stack. |
| AWS CLI route | PITFALLS and repo PRIO: brew first | AWS recommends the official script | Decision 12. |
| Bruno Linux | FEATURES and PITFALLS: Flatpak or AppImage | AppImage per arch via `github_release` raw; no flatpak kind | Stack. AppImage raw. |
| gh-stack install | PITFALLS needs auth; pin tag | Auth not required to install; `--pin` optional | Stack. Install with the full URL (GHE default host). |
| Playwright MCP pinning | PITFALLS pin; FEATURES do not pin | STACK recommends pinned bunx | Decision 14. |
| Xcode CLT | FEATURES brew install.sh; PITFALLS, STACK handoff | Headless route needs sudo; `xcode-select --install` is a GUI prompt | Handoff-only (decision 11). |

**Design conflict (not a vendor fact):** STACK recommends `macos_option_as_alt both` for kitty; PITFALLS Pitfall 1 forbids the global switch (it breaks `@` Option+2, `|` Option+1, `\` Option+Shift+7 and `#` Option+3 on Spanish layouts). Recommended: never set the global switch; bind only Option+arrows. Phase 3 must test whether `map opt+left` fires with `macos_option_as_alt no` (arrow keys are not composed characters, so likely yes). Fall back only with owner sign-off. Regression test: the global switch is absent from every generated macOS config.

## Key Findings

### Recommended Stack

The milestone adds no new technology: config writers per terminal and registry rows per tool.

- **Owned regions with `#`/`--` comments** (`_replace_owned_region`): kitty.conf, the Ghostty `config`, WezTerm Lua.
- **Dynamic Profile JSON** for iTerm2 (`~/Library/Application Support/iTerm2/DynamicProfiles/`): whole-file ownership, needs a whole-file mode in the spec.
- **Herdr desktop app keys:** `keys.json` (Linux), `keys.macos.json` (macOS); JSON, so herdr's own merge approach.
- **Registry methods:** `cask` (Ghostty, iTerm2, Bruno, Herdr app macOS arm64), `github_release` raw AppImage (Ghostty Linux, Bruno Linux per arch), `script` (Herdr app install.sh, AWS CLI official script), `brew`/`bun` (AWS fallback, Playwright MCP).
- **Versions (2026-11-16):** kitty 0.50.0; Ghostty 1.4.0; iTerm2 3.7.7; Bruno 4.3.0; Herdr app 0.1.16; herdr TUI v0.9.5; AWS CLI 2.40.4 (brew 2.40.3); gh-stack v0.3.0; gh v2.104.0; @playwright/mcp 0.0.85; WezTerm cask 20240203-110809 (not re-fetched).
- **Not adding:** `dmg`, `pkg`, `flatpak`, `snap`, `appimage` or `gh_extension` kinds; Policies knobs; `rpm-ostree`/COPR; `~/.aws` removal; Ghostty `keybind = clear`.

### Expected Features

- **Table stakes:**
  - Skill rewrite (999.18): replace the "ask the user" bullet in `.claude/skills/tool-onboarding/SKILL.md` (~180-195) with three rules, a per-OS table and a conflict rule; skill-judge before and after.
  - Alacritty behavior unchanged by the shared mechanism.
  - kitty: Linux override plus macOS `opt+left/right` → `\x1bb`/`\x1bf`.
  - WezTerm: Lua region extending `config.keys` with `OPT`+arrows → `SendString`.
  - Konsole: verify only.
  - Ghostty: cask, Linux AppImage, `_sync_ghostty`, Linux `keybind = ctrl+shift+k=clear_screen`.
  - iTerm2: cask plus one Dynamic Profile with `Option Key Sends`/`Right Option Key Sends` = 2.
  - Herdr desktop app: Linux `script` (paths = app dir, `.desktop`, icon; NOT `herdr-core`/`hc`) and macOS `cask herdr-app` arm64.
  - AWS CLI: official script, `aws --version` smoke, `aws update`, never `~/.aws`.
  - gh-stack: `gh extension install https://github.com/github/gh-stack`, detect with `gh extension list`, remove with `gh extension remove stack`, never `gh auth login`.
  - Bruno: cask plus per-arch raw AppImage, no collections in `config_paths`.
  - Xcode CLT: detect plus handoff, no uninstall.
  - Playwright: Flatpak Chrome env gated on the wrapper being present.
- **Differentiators:** one declarative `TERMINAL_KEYS` table; the receipt lists per-terminal keys set; "kept yours" reporting.
- **Defer:** iTerm2 focus cursor and agent extension until named; Herdr desktop app terminal defaults beyond confirmed rules; Linux IDE keybindings (VS Code, Cursor, Antigravity); the `bru` CLI; remapping Cmd+Left/Right, Option+Backspace, Ctrl+A/E; Playwright's own Chromium download; anything needing a new method kind.
- **Anti-features:** Policies rows or TUI questions for these keys; asking per terminal; blind overwrite of user bindings; `defaults write` or plist edits; global Option-as-Alt; `sudo`, `softwareupdate`, `xcode-select --install`, `installer -target /` or `gh auth login` in any executor.

### Architecture Approach

Generalize the lifecycle, not the body. Each row supplies a renderer and a conflict checker; shared code does record, skip, pending, strip and compare-before-commit.

1. `installer/terminal_keys.py` (NEW): `KeysSpec`, `TERMINAL_KEYS` keyed by registry tool id, shared `apply_terminal_keys` / `terminal_keys_pending` / `strip_terminal_keys`. It imports from `terminal_shell`; no reverse import.
2. Dispatch sites made table-driven: `post_install.py:387, 393-396`; `version_status.py:783, 821-834`; `app.py:630-631` (today `if tool.id == "alacritty"`).
3. `terminal_shell.py` (MODIFIED): the Alacritty keys code moves out; the shell region stays; a Ghostty shell branch is added. New writers go in `terminal_keys.py` (`terminal_shell.py` is 1,055 lines).
4. `registry.toml`: `post_install = ["apply_terminal_tuning"]` on kitty and wezterm; new `ghostty`, `iterm2`, `herdr-app`. No new POST_INSTALL_ACTIONS name.
5. Unchanged: `session.py`, `model.py`, `receipts.py`.

- **Flow:** install → `run_post_install` → `_apply_terminal_tuning` → `TERMINAL_KEYS[tool.id]` → render with `platform.os` → owned region → validate → atomic write → record `terminal-tuning-<id>`. Drift goes through `_tuning_fact` → `≈ apply install tuning`. Uninstall strips the region and the record before `config_paths`. The shell sync stays separate and Linux-only.
- **Anti-patterns:** keys through `sync_terminal_shells`; a per-terminal action name; parsing Lua or kitty.conf.

### Critical Pitfalls

1. **Option-as-Alt breaks composed characters.** Never set the global switch; bind only Option+arrows; regression test; test `@` and `|` on the owner's layout.
2. **Last-wins overrides of user bindings.** Region at the top of last-wins files (kitty, Ghostty); extend WezTerm `config.keys`, never assign it; detect same-chord user bindings and skip with `partial:`.
3. **Files the app rewrites.** Konsole KConfig drops comments (CR-06); the iTerm2 plist is cached by cfprefsd. Dynamic Profile only; detect a custom prefs folder and skip.
4. **Zero-sudo: CLT and the AWS pkg.** No `softwareupdate`, `xcode-select --install`, `installer -target /` or `sudo` in executors; grep test.
5. **Untestable macOS and Flatpak.** Pure generator plus golden file on both OSes; a thin macOS I/O edge; `UAT: deferred to owner Mac`. Flatpak terminals use `~/.var/app/<id>/config`; report `skipped: sandboxed terminal`.

Also: herdr can eat Alt chords (verify with a `cat -v` test); Ghostty has two config locations on macOS; gh-stack repo identity; the Bruno cask is macOS-only; prose rules drift (closed table plus coverage test); `terminal_shell.py` growth.

## Implications for Roadmap

Owner-specified build order. Decisions in brackets gate the phase.

### Phase 1: Tool-onboarding skill refactor (999.18)

**Rationale:** rules before code; every later phase runs through this skill. Pure docs.
**Delivers:** the rewritten SKILL.md section with the three rules; a per-terminal table pinning "clear" [decision 1]; the conflict rule; "bind two keys, never the global switch"; "macOS items: pure generator + golden file + deferred UAT"; a closed per-terminal table with a coverage test if accepted. skill-judge before and after.
**Avoids:** prose-only rules; prescriptive bindings; option-as-alt.
**Blocked by:** decision 1.

### Phase 2: Shared terminal-keys mechanism (behavior-preserving)

**Rationale:** remove the per-terminal cost before it is paid four times; gates the rest.
**Delivers:** `installer/terminal_keys.py`; Alacritty moved in as row 1 unchanged (no assertion edits); the three dispatch sites table-driven; a registry test that every `apply_terminal_tuning` tool has a row. Konsole stays out of the table.
**Note:** decision 4 (Alacritty Linux word nav) belongs to Phase 3, not a blocker here.

### Phase 3: kitty, WezTerm, Konsole, herdr pass-through

**Rationale:** kitty and WezTerm have live macOS rows and the existing sync; they prove the mechanism. Konsole runs in parallel.
**Delivers:** a kitty `kitty-keys` region at the top of kitty.conf (last-wins); macOS `opt+left/right` → `send_text all \x1bb`/`\x1bf`, no global switch; Linux `ctrl+shift+k` override [decision 2]. A WezTerm `wezterm-keys` Lua region before `return config` that extends `config.keys`; macOS `OPT`+arrows → `SendString`; clear already default (report `already default`). Konsole: verify, write only if remapped [decision 3], state-file ownership. herdr: an observable pass-through test (`ESC b` through a herdr pane); no config expected. Tighten the WezTerm marker substring at `terminal_shell.py:195` so `wezterm-keys` is not mistaken for the shell region.
**Owner input:** decisions 1-4.

### Phase 4: Ghostty, iTerm2, Herdr desktop app

**Rationale:** Ghostty is text config and fits the table with a shell branch; iTerm2 needs a whole-file mode; the Herdr desktop app goes last because terminal hosting and naming are unconfirmed.
**Delivers:**
- Ghostty: `ghostty` cask (macOS, `min_os_version = "13"`); Linux community AppImage with `ghostty-keys` (`keybind = ctrl+shift+k=clear_screen`) and `_sync_ghostty` (`command = /usr/bin/zsh -l`). macOS word nav and clear are already default: write nothing. Resolve the effective config file (XDG vs `~/Library/Application Support/com.mitchellh.ghostty/config`); create the XDG one only if neither exists.
- iTerm2: `iterm2` cask (macOS only); a whole-file Dynamic Profile with `Option Key Sends` = 2 and `Right Option Key Sends` = 2, Custom Directory, colors per owner; ownership by a fixed Guid/Name; strip deletes when the proof matches; detect `PrefsCustomFolder`/`LoadPrefsFromCustomFolder` and skip; golden file; macOS UAT deferred.
- Herdr desktop app: Linux `script` (install.sh; `paths` = app dir, `.desktop`, icon; not `herdr-core`/`hc`); macOS `cask herdr-app` with `arch = ["arm64"]`; an id distinct from `herdr`; app-owned self-update; keys per decisions 5-8.
**Owner input:** decisions 7-10, 13.

### Phase 5: Non-terminal onboardings

**Rationale:** independent of the terminal mechanism; can run in parallel with 3-4 once Phase 1 lands. Small mechanical entries first.
**Delivers:**
- AWS CLI: official `install.sh` (`shell = "bash"`, user-local, `paths` = `~/.local/share/aws-cli` plus two symlinks; never `~/.aws`); `aws --version` smoke; `aws update`; brew `awscli` macOS fallback; requires gpg on Linux, never skip verification [decision 12].
- gh-stack: `gh extension install https://github.com/github/gh-stack` as a post-install or a tiny `requires = ["gh"]` entry; detect with `gh extension list`; remove with `gh extension remove stack`; an unauthenticated gh must not block [decision 16].
- Bruno: macOS cask `bruno`; Linux `github_release` raw AppImage per arch (`arm64` vs `x86_64`); API digests; no collections in `config_paths`; `bru` out of scope [decision 15].
- Xcode CLT: `tier = "system"`, `os = ["macos"]`, `xcode-select -p` plus a real-git probe, handoff only; no uninstall; `requires = ["xcode-clt"]` edge [decision 11].
- Playwright MCP: shell-rc `PLAYWRIGHT_MCP_EXECUTABLE_PATH` and a Cursor `env` entry only when `/var/lib/flatpak/exports/bin/com.google.Chrome` exists; registration through `agent_settings.py` with `receipt.hooks`; never overwrite an existing `mcpServers.playwright`; a headless launch smoke in a Fedora/Bazzite container [decision 14].

## Phase Ordering Rationale

- Phase 1 first: it fixes the rules and the meaning of "clear" that every terminal row needs.
- Phase 2 before any new terminal: three hard-coded dispatch sites become one table.
- Phase 3 before 4: prove the mechanism on real files before the whole-file iTerm2 mode.
- The whole-file mode only when a row needs it.
- Phase 5 is independent and can run in parallel with 3-4.

## Research Flags

**Needs deeper research (`/gsd-plan-phase --research-phase`):**
- Phase 3: whether `map opt+left` fires with `macos_option_as_alt no`; the Konsole stock key on the current version in a container; herdr key docs.
- Phase 4 (Ghostty, Herdr app): AppImage packaging in a container (FUSE 2 on Bazzite); re-read the install.sh footprint before `paths`; macOS config path precedence; herdr app keys path and terminal hosting.
- Phase 4 (iTerm2): capture the real Keyboard Map encoding from "Save Profile as JSON" on a Mac, or defer that entry; default-profile behavior.
- Phase 5 (Playwright MCP): Fedora/Bazzite container smoke; registration scope.
- Phase 5 (AWS CLI): brew-vs-script priority; gpg prerequisite.
- Phase 5 (gh-stack): extension directory path under a scratch `GH_CONFIG_DIR`; GHE default host.

**Standard patterns (skip research-phase):** Phase 1 (docs, owner rules, skill-judge); Phase 2 (behavior-preserving move with existing tests); Phase 5 Bruno AppImage and cask, Xcode CLT handoff, AWS script (precedents: the WezTerm AppImage, the kitty script entry, `_cask`).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH (vendor facts), MEDIUM (macOS behavior) | kitty, WezTerm, Konsole, Ghostty from upstream source at tags; iTerm2 key names from source, Keyboard Map LOW; herdr pass-through UNVERIFIED |
| Features | MEDIUM-HIGH | Owner rules clear; the clear meaning and scope items are owner decisions; Xcode CLT and WezTerm option-key flags partly from memory |
| Architecture | HIGH for integration points, MEDIUM for syntax | Integration points read from code; syntax checked against STACK where available |
| Pitfalls | HIGH for mechanisms, MEDIUM for `[verify]` | Option-as-Alt and last-wins from the Alacritty precedent; reload behavior and Flatpak paths from model knowledge |

**Overall:** MEDIUM-HIGH. Vendor defaults are well sourced. Real-Mac behavior, the iTerm2 Keyboard Map, Ghostty Linux on Bazzite and herdr pass-through are not.

### Gaps to Address

- macOS is untested by design (no Mac run since v0.49.0): pure generator plus golden file; macOS CI proves paths only; UAT line `deferred to owner Mac`. Never write "verified on macOS" without a CI assertion.
- The "clear" meaning (decision 1): resolve first.
- kitty `opt+left` with option-as-alt off (design conflict): test in Phase 3.
- iTerm2 Keyboard Map encoding and Dynamic Profile parent inheritance: capture on a Mac or defer.
- Herdr desktop app: naming, keys path, terminal hosting, the `cmd-k` choice, the install.sh footprint.
- Ghostty Linux: AppImage trust, FUSE 2 on Bazzite, macOS config path precedence.
- AppImage FUSE 2 on Bazzite (Ghostty, Bruno): container test.
- gh-stack extension directory: derive under a scratch `GH_CONFIG_DIR`/XDG.
- `playwright-mcp --version` is UNVERIFIED: use a headless launch as the smoke.
- Brew CLT behavior with `HOMEBREW_NO_SUDO=1` on a clean Mac: UNVERIFIED; Xcode CLT is handoff-only regardless.
- The `tests/test_docs.py` install-tuning phrases must change together with `.claude/architecture.md`.
- `{ver}` `v`-prefix handling for the Ghostty tag `v1.4.0` vs the asset `Ghostty-1.4.0-*`: confirm in `resolve_target`.

## Sources

### Primary (HIGH)
- kitty: https://sw.kovidgoyal.net/kitty/conf/ , https://sw.kovidgoyal.net/kitty/actions/ ; `kitty/options/definition.py` (kitty 0.50.0)
- WezTerm: https://wezterm.org/config/default-keys.html , https://wezterm.org/config/keys.html , https://wezterm.org/config/lua/config/default_prog.html
- Konsole: https://github.com/KDE/konsole `src/session/SessionController.cpp`
- Ghostty: `src/config/Config.zig` at tag v1.4.0; https://ghostty.org/docs/config/reference
- iTerm2: https://github.com/gnachman/iTerm2 `sources/Settings/Profiles/ITAddressBookMgr.h`, `sources/MainMenu/Base.lproj/MainMenu.xib`
- Herdr app: https://github.com/herdrdev/herdr-app (`defaults/keys*.json`, README, CHANGELOG); https://releases.herdr.dev/app/install.sh
- Casks/formulae: https://formulae.brew.sh/api/cask/{ghostty,iterm2,bruno,herdr-app}.json , https://formulae.brew.sh/api/formula/awscli.json
- AWS CLI: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html , https://awscli.amazonaws.com/v2/install.sh
- gh: https://cli.github.com/manual/gh_extension_install , https://github.com/cli/cli `pkg/cmd/extension/manager.go`; https://github.com/github/gh-stack
- Repo code: `installer/terminal_shell.py` (`:98-139`, `:151-208`, `:359-460`, `:465-768`, `:854-1031`), `installer/post_install.py:383-472`, `installer/version_status.py:735-741, 775-834`, `installer/app.py:615-640`, `installer/compose.py:355-430`, `installer/model.py:130-141`, `installer/registry.toml`, `.claude/architecture.md`, `.claude/skills/tool-onboarding/SKILL.md`

### Secondary (MEDIUM)
- Playwright MCP README; npm `@playwright/mcp` 0.0.85
- https://docs.usebruno.com/get-started/bruno-basics/download
- KDE bugs 282593, 427577, 435548 (not rechecked)
- https://github.com/Homebrew/install `install.sh`
- `.planning/research/2026-10-13-from-ai-kit/16-playwright-chrome-bazzite.md` (tested in-repo)

### Tertiary (LOW, needs validation)
- The iTerm2 Keyboard Map numeric encoding; Flatpak terminal config paths and the sandboxed shell; per-terminal reload behavior; Xcode CLT GUI/sudo behavior (not re-fetched).

---
*Research completed: 2026-11-16*
*Ready for roadmap: yes, once owner decisions 1, 2, 7, 11, 12 and 14 are answered (they gate Phases 1, 3, 4 and 5)*
