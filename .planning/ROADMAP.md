# Roadmap: tools-installer

## Milestones

- ✅ **v0.49.0 Tiered Catalog** — Phases 1–16 incl. 12.1–12.4 and 15.1–15.8 (shipped 2026-10-13, override closeout; see [archive](milestones/v0.49.0-ROADMAP.md) and [audit](research/audit-2026-10-13/SYNTHESIS-AND-PLAN.md))
- ✅ **v0.50.0 Truthful lifecycle** — Phases 17–26 incl. 23.1–23.2 and 24.1–24.5 (shipped 2026-11-16; see [archive](milestones/v0.50.0-ROADMAP.md) and [audit](milestones/v0.50.0-MILESTONE-AUDIT.md))
- 🚧 **v0.51.0 Onboard terminal tools** — Phases 27–35 (in progress)

## Phases

<details>
<summary>✅ v0.49.0 Tiered Catalog (Phases 1–16) — SHIPPED 2026-10-13</summary>

28 phases, 110 plans, 244 tasks. Tier-scoped catalog, dependency drag-in, postinstall hooks, background maintenance daemon, version-aware status and updates, live in-TUI install execution, ownership attribution and the Owner column, terminal default shell on immutable hosts, self-deduping PATH, filesystem-based detection. Full phase details: [milestones/v0.49.0-ROADMAP.md](milestones/v0.49.0-ROADMAP.md); phase directories: `milestones/v0.49.0-phases/`.

</details>

<details>
<summary>✅ v0.50.0 Truthful lifecycle (Phases 17–26) — SHIPPED 2026-11-16</summary>

17 phases, 276 plans, 438 tasks, 121/121 requirements. Every screen tells the truth about each tool on this host (present, healthy, whose, which version, removable with proof), and install, update, removal and configuration follow one per-method contract with install receipts as removal proof. Full phase details: [milestones/v0.50.0-ROADMAP.md](milestones/v0.50.0-ROADMAP.md); phase directories: `milestones/v0.50.0-phases/`.

- [x] Phase 17: Stop the bleeding (21 plans) — completed 2026-11-15
- [x] Phase 18: Registry truth and drift guard (28 plans) — completed 2026-11-15
- [x] Phase 19: One tool state with health plus receipts (46 plans) — completed 2026-11-15
- [x] Phase 20: Install plan with dispositions (31 plans) — completed 2026-11-07
- [x] Phase 21: One screen family (21 plans) — completed 2026-11-15
- [x] Phase 22: Method lifecycle contract (13 plans) — completed 2026-11-15
- [x] Phase 23: Configuration as a lifecycle step (16 plans) — completed 2026-11-15
- [x] Phase 23.1: Host safety: drop the skill-pack catalog entries, sandboxed tests, container-only e2e (18 plans) — completed 2026-11-07
- [x] Phase 23.2: Install-time tuning instead of Policies knobs (8 plans) — completed 2026-11-13
- [x] Phase 24: Onboarding through the skill and e2e (9 plans) — completed 2026-11-14
- [x] Phase 24.1: Onboard Neovim through the tool-onboarding skill (5 plans) — completed 2026-11-14
- [x] Phase 24.2: Schedules view (13 plans) — completed 2026-11-14
- [x] Phase 24.3: Catalog audit skill (11 plans) — completed 2026-11-14
- [x] Phase 24.4: Retire the npx, npm and pip guard aliases and redirects (7 plans) — completed 2026-11-14
- [x] Phase 24.5: JavaScript install priority brew then bun then volta (9 plans) — completed 2026-11-15
- [x] Phase 25: Lean (11 plans) — completed 2026-11-15
- [x] Phase 26: Commit and push quality hooks (9 plans) — completed 2026-11-16

</details>

## 🚧 v0.51.0 Onboard terminal tools

**Milestone Goal:** Every terminal emulator and IDE in the catalog, and every one added later, ships with the same defaults: zsh as the launched shell on Linux (Bazzite included), Option/Alt+Left/Right word navigation on macOS, a clear-screen shortcut (Cmd+K on macOS, Ctrl+Shift+K on Linux) and new tabs, windows and panes in the current directory, all applied through a tool-onboarding skill that carries them as rules; the pending tool onboardings run through the same skill. The milestone also adds update automation: a bot that refreshes the catalog pins, a daily update check with a desktop notification, and an opt-in schedule that updates package managers before the tools that depend on them (Phases 33–35, ingested 2026-11-19).

**Design source:** `.planning/research/SUMMARY.md` "Implications for Roadmap" (research Phases 1–5 = Phases 27–31 and 32 here) and the owner decisions of 2026-11-16 in `.planning/REQUIREMENTS.md`. Every phase after 27 runs its tool work through `.claude/skills/tool-onboarding/SKILL.md`. Every macOS behavior is a pure generator with a golden-file test on both OSes and a UAT line deferred to the owner's Mac.

**Phase Numbering:**

- Integer phases (27–35): Planned milestone work
- Decimal phases (e.g. 27.1): Urgent insertions (marked with INSERTED)

- [ ] **Phase 27: Tool-onboarding skill: terminal defaults as rules** - The skill applies the four terminal and IDE defaults without asking, carries a closed per-terminal table with a coverage test, the conflict rule and the macOS app and testing rules; skill-judge before and after
- [ ] **Phase 28: Shared terminal-keys mechanism** - One table-driven keys mechanism keyed by tool id, with Alacritty moved in unchanged; drift, reconfigure and strip for every row; the shared Ctrl+L clear and the same-directory rule
- [ ] **Phase 29: Terminal defaults for the terminals in the catalog** - kitty and WezTerm meet the defaults on both OSes, Alacritty's clear moves to screen and scrollback, Konsole is checked, and herdr passes the keys through
- [ ] **Phase 30: Onboard Ghostty** - Ghostty in the catalog (cask, labelled community AppImage, pacman) with the zsh sync on Linux and its keys region
- [ ] **Phase 31: Onboard iTerm2 and the Herdr desktop app** - iTerm2 as a macOS-only cask with a default Dynamic Profile, and the Herdr desktop app as its own entry with its keys files
- [ ] **Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP** - Five non-terminal onboardings through the skill; runs in parallel with Phases 28–31
- [ ] **Phase 33: Registry update bot** - A GitHub Actions workflow refreshes the catalog pins with `verify-registry --write` and pushes a bot branch the owner lands through the protected flow
- [ ] **Phase 34: Daily update check with a desktop notification** - A daily Schedules row checks for new versions and notifies on Bazzite (`notify-send`) and macOS (`osascript`) when the outdated set changes
- [ ] **Phase 35: Opt-in auto-update, package managers first** - An off-by-default `update-all` Schedules row updates package managers, then the tools that depend on them

## Phase Details

### Phase 27: Tool-onboarding skill: terminal defaults as rules

**Goal**: Anyone onboarding or reviewing a terminal or IDE through the tool-onboarding skill gets the same defaults applied without a question, from one closed table that a test keeps in step with the registry.
**Depends on**: Nothing (first phase of v0.51.0; builds on shipped v0.50.0)
**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05, SKILL-06
**Note**: Absorbs backlog 999.18. The meaning of "clear" (screen and scrollback, Modifier+K sends Ctrl+L) is owner-decided; the old "ask the user, do not enable silently" bullets (`SKILL.md` ~185-191) are replaced, not extended.
**Success Criteria** (what must be TRUE):

  1. The skill states as rules applied without asking: zsh is the launched shell on Linux (Bazzite included); Option/Alt+Left/Right moves by word on macOS by binding only those two chords, never the global Option-as-Alt switch; Cmd+K (macOS) and Ctrl+Shift+K (Linux) clear the screen and the scrollback; a new tab, window or pane opens in the current directory. Only extras remain questions.
  2. The skill carries a closed per-terminal table (config file, how each default is met or already met by the vendor, reload behavior), and the test suite fails when a terminal or IDE entry in `installer/registry.toml` has no row (proved with a fixture entry missing its row).
  3. The skill states the conflict rule (a user binding is never overridden and is reported as `partial: kept yours`; a conflicting vendor default is overridden only with an install note naming the displaced default) and the macOS app rule: per app it records install, uninstall and configuration, places the bundle in `~/Applications` where the method allows it, links a shipped CLI into `~/.local/bin`, and says why when no user location is possible.
  4. The skill states the macOS testing rule: each macOS behavior is a pure config generator with a golden-file test that runs on both OSes, macOS CI covers the file paths, and the real-Mac check is a UAT line marked deferred to the owner's Mac.
  5. skill-judge scores for the skill before and after the rewrite are recorded in the phase directory, and the after score is not lower.

**Plans:** 4/4 plans executed

Plans:
**Wave 1**
- [x] 27-01-PLAN.md — Before verdict (pre-dispatch orchestrator prerequisite, executor verify gate), then the closed per-terminal table with its registry coverage test and edge fixtures (SKILL-02, SKILL-06)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 27-02-PLAN.md — Step 7 renamed; the four defaults as rules; only non-terminal extras stay questions (SKILL-01, SPEC R6)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 27-03-PLAN.md — Conflict rule, macOS testing rule naming the CI job, macOS app rule with a `# Verified` example (SKILL-03, SKILL-05, SKILL-04)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 27-04-PLAN.md — After verdict (pre-dispatch orchestrator prerequisite, executor verify gate), shared verdict parser, the after-not-lower test with the rubric-maxima check, and docs-only entries (SKILL-06)

### Phase 28: Shared terminal-keys mechanism

**Goal**: A terminal's keys become one row in one shared mechanism, so applying, checking, re-applying and removing its keys works the same for every terminal, starting with Alacritty exactly as it behaves today.
**Depends on**: Phase 27
**Requirements**: KEYS-01, KEYS-02, KEYS-03, KEYS-04
**Note**: Research Phase 2. Behavior-preserving move of the Alacritty keys code out of `installer/terminal_shell.py` into `installer/terminal_keys.py`; the dispatch sites in `post_install.py`, `version_status.py` and `app.py` become table-driven. Konsole stays outside the table. Alacritty's own clear change is TERM-03 (Phase 29).
**Success Criteria** (what must be TRUE):

  1. Alacritty's keys region is applied, checked and stripped through the shared mechanism keyed by its registry tool id; the region it writes is byte-identical to before the move and its existing tests pass with no assertion edits; no dispatch site branches on the Alacritty id any more.
  2. In a scratch HOME, deleting or editing a terminal's keys region makes its row read `≈ apply install tuning` *(amended 2026-11-19, 28 D-06, needs confirmation: deleting counts only before the installer recorded an apply; editing a present region is drift)*, a reconfigure restores the region, and an uninstall strips it with the tool; a test fails when a registry tool with `apply_terminal_tuning` has no mechanism row.
  3. In the installer's managed zsh configuration, Ctrl+L at the prompt clears the visible screen and the scrollback (byte-level test of the emitted sequences), and the mechanism maps the clear chord to Ctrl+L for every row: Cmd+K on macOS, Ctrl+Shift+K on Linux.
  4. Every mechanism row declares whether the vendor already opens a new tab, window or pane in the current directory; the setting is written only for rows where it does not, and a test fails when a row leaves it undeclared.

**Plans:** 4/4 plans executed

Plans:
**Wave 1**
- [x] 28-01-PLAN.md — Golden bytes of Alacritty's keys region committed before the move, then the shared primitives moved into `installer/terminal_regions.py` (KEYS-01)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 28-02-PLAN.md — Tracer: one `TERMINAL_KEYS` table keyed by tool id drives install, reconfigure, the `≈` fact and removal; completeness test and no-row backstop (KEYS-01, KEYS-02)
- [x] 28-04-PLAN.md — The zsh Ctrl+L clear widget as zsh's shell-init bundle, and the onboarding skill's rule (c) (KEYS-03)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 28-03-PLAN.md — Drift rule (D-06, provisional), the shared clear chord and the required same-directory declaration on fixture rows (KEYS-02, KEYS-03, KEYS-04)

### Phase 29: Terminal defaults for the terminals in the catalog

**Goal**: kitty, WezTerm, Alacritty, Konsole and herdr each meet the terminal defaults on every OS they install on, without overriding a binding the user set.
**Depends on**: Phase 28
**Requirements**: TERM-01, TERM-02, TERM-03, TERM-04, TERM-05
**Note**: Absorbs backlog 999.19 and its four pending todos (`.planning/todos/pending/2026-11-16-terminal-defaults-for-{kitty,wezterm,konsole,herdr}.md`). Research flags: whether kitty's `map opt+left` fires with `macos_option_as_alt no`; Konsole's stock key on the current version in a container; herdr key handling. One phase rather than two: kitty and WezTerm prove the mechanism, and Alacritty, Konsole and herdr are small checks on the same rule.
**Success Criteria** (what must be TRUE):

  1. kitty's generated config (golden files on both OSes) binds Option+Left/Right to word navigation on macOS with no global `macos_option_as_alt` switch (a regression test asserts the switch is absent), clears screen and scrollback on Cmd+K and on Linux Ctrl+Shift+K with the displaced `scroll_line_up` named in the install note, opens new tabs and windows in the current directory, and kitty's macOS install writes nothing into `/Applications`.
  2. WezTerm's Lua owned region meets the defaults on both OSes and extends the user's existing `config.keys` (a fixture with user keys keeps all of them); a config that holds both the shell region and the keys region is read correctly, because the shell-region check matches exact marker lines.
  3. Alacritty's Cmd+K and Ctrl+Shift+K now clear the screen and the scrollback, and its Linux Alt+Left/Right rows are unchanged; on a stock Konsole profile the installer writes nothing and reports the stock Ctrl+Shift+K clear, writes the binding only when the user removed it *(amended 2026-11-19, 29 D-09, needs confirmation: report-only, never writes)*, and the Konsole zsh sync is unchanged.
  4. Inside a herdr pane, Option/Alt+Left/Right and the clear chord reach the shell as the expected bytes (an observable byte-level test); a herdr pass-through setting is written only if herdr intercepts them.

**Plans:** 6 plans

Plans:
**Wave 1**
- [ ] 29-01-PLAN.md — Tracer: Alacritty's clear sends Ctrl+L through the mechanism and existing installs reach it by drift; the row interface (placement, per-OS writes, config path, notes, read-back) and exact WezTerm shell markers (TERM-03, TERM-02)
- [ ] 29-05-PLAN.md — herdr: no row; an orchestrator-only `herdr-keys` container target with a pure byte verdict, proved on the host with a stubbed `ct` (TERM-05)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 29-02-PLAN.md — kitty: top-of-file keys region on both OSes, include scan, displaced-default notes, kitty's resolver, macOS route through the cask only (TERM-01)

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 29-03-PLAN.md — WezTerm: Lua keys region before `return config` that extends `config.keys`, read-back of kept chords, created-file cleanup (TERM-02)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 29-04-PLAN.md — Konsole: report-only check of the stock Ctrl+Shift+K clear, `partial: kept yours` on removal, one-time stock note (TERM-04)

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 29-06-PLAN.md — Onboarding skill table cells (29 D-12) and the phase consistency guards; orchestrator checklist (TERM-01..TERM-05)

### Phase 30: Onboard Ghostty

**Goal**: A user can install, use and remove Ghostty from the catalog on macOS, Linux, Bazzite and Arch, and it opens zsh with the terminal defaults.
**Depends on**: Phase 29
**Requirements**: NTERM-01
**Note**: Absorbs backlog 999.20. Its own phase because it is a full new entry with three install routes (cask, community AppImage, pacman), a new shell-sync branch, macOS effective-config resolution and a keys row; it is the only new terminal that fits the existing owned-region mode, so it lands before the two that need a JSON file mode (Phase 31). Research flags: AppImage under FUSE 2 on Bazzite (container test), the `{ver}` handling of the `v1.4.0` tag, XDG vs `~/Library/Application Support/com.mitchellh.ghostty/config` precedence.
**Success Criteria** (what must be TRUE):

  1. On macOS Ghostty installs from the official cask into a user-writable app location with its CLI linked into `~/.local/bin`; on Linux and Bazzite a digest-verified community AppImage installs without a reboot and its row and install note say "community build"; on Arch it installs with pacman.
  2. On Linux, Ghostty launches zsh through the terminal sync and Ctrl+Shift+K clears the screen and the scrollback; the macOS golden file writes nothing where the vendor default already meets a rule, never writes `macos-option-as-alt`, and goes to the config file Ghostty actually reads.
  3. New tabs, windows and splits open in the current directory; a drifted Ghostty keys region shows `≈ apply install tuning` and a reconfigure re-applies it.
  4. In a container, uninstalling Ghostty removes the AppImage, its keys and shell regions and every receipt-recorded path, leaving only documented config.

**Plans:** 6 plans

Plans:
**Wave 1**
- [ ] 30-01-PLAN.md — Tracer: the Ghostty entry (cask, two pinned community AppImage methods, pacman), the loader keys `raw`, `note` and `desktop`, the engine note and the skill row; Linux x86_64 installs end to end through the engine; loader refusals and the digest-mismatch proof (NTERM-01)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 30-02-PLAN.md — AppImage menu entry and icon: render drop, smoke TMPDIR, `appimage_menu` module, receipt leaves, uninstall (NTERM-01)

**Wave 3** *(blocked on Wave 2 completion; shares `installer/registry.toml` with 30-02)*
- [ ] 30-03-PLAN.md — Keys row: the pure config resolver for both OSes, the conflict scan over every default file, goldens, drift, reconfigure and strip, the install-tuning declaration and skill cell together (NTERM-01)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 30-04-PLAN.md — Linux shell sync `_sync_ghostty`: the top-of-file `command` region, partial on a user `command` or include, revert, status row (NTERM-01)

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 30-05-PLAN.md — `ghostty` container target: FUSE pass (an observed FUSE mount) and extract-and-run pass, regions read back with the real Ghostty, residue diff; proved on the host with a stubbed `ct`; the orchestrator runs it (NTERM-01)

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 30-06-PLAN.md — Container evidence in the registry comment and the skill row behind a hard gate on the recorded `ghostty-container: PASS` line, and the catalog consistency guards (NTERM-01)

### Phase 31: Onboard iTerm2 and the Herdr desktop app

**Goal**: A macOS user gets iTerm2 with a ready default profile that meets the terminal defaults, and the Herdr desktop app installs on Linux and Apple Silicon macOS as its own entry with the same defaults.
**Depends on**: Phase 30 (both extend the shared keys table; kept sequential to avoid conflicting edits)
**Requirements**: NTERM-02, NTERM-03
**Note**: Absorbs backlog 999.21 (Herdr IDE = the Herdr desktop app `herdrdev/herdr-app`, owner decision) and 999.22. Grouped because both need a JSON file mode the mechanism does not have yet: a whole-file iTerm2 Dynamic Profile and the herdr app's `keys.json`/`keys.macos.json`. Owner decision: the iTerm2 profile becomes the default profile (overrides the research recommendation). Research flags: iTerm2 Keyboard Map encoding and default-profile behavior (capture on a Mac or defer to UAT); the herdr app keys path and `install.sh` footprint.
**Success Criteria** (what must be TRUE):

  1. iTerm2 installs from the cask on macOS only (its Linux row reads unavailable), and the installer writes one owned Dynamic Profile with Option+Left/Right word navigation through key-map rows (Option stays Normal) *(amended 2026-11-19, 31 D-08, needs confirmation)*, the Cmd+K clear, new tabs, windows and panes in the current directory, and the requested color scheme (golden file on both OSes).
  2. After an iTerm2 install the installer's profile is the default profile, and an uninstall deletes the profile and restores the previous default (golden test of the before and after state; the real-Mac check is a UAT line deferred to the owner's Mac).
  3. The Herdr desktop app is a catalog entry distinct from `herdr`: a user-scope `install.sh` with no sudo on Linux and the cask on Apple Silicon macOS (unavailable on Intel macOS); installing or removing one entry leaves the other's binaries and `~/.config/herdr` intact.
  4. The Herdr desktop app's keys files meet the defaults on both OSes; on Linux Ctrl+Shift+K clears and the displaced picker binding is named in the install note, and a binding the user defined is kept and reported as `partial: kept yours`.

**Plans:** 8 plans

Plans:
**Wave 1**
- [ ] 31-01-PLAN.md — Tracer: the typed ownership union (`WholeFile`, `OwnedKeys`, `DefaultProfile` hook), dispatch at the three keys entry points and both generic mechanisms proved on fixture rows; the four region rows untouched (NTERM-02, NTERM-03)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 31-02-PLAN.md — iTerm2 pure core: the Dynamic Profile generator and goldens, the parent key-map merge, the one `defaults` seam, the default-profile hook functions and the four-state before/after golden (NTERM-02)

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 31-03-PLAN.md — The iTerm2 entry end to end: registry cask entry, `TERMINAL_KEYS["iterm2"]`, skill row, forced pins, and the restore of the previous default wired before the cask removal (an unconfirmed restore refuses the removal); lifecycle and both uninstall routes through the production functions (NTERM-02)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 31-04-PLAN.md — herdr-app data and pure logic: the pinned vendor default keys files with a version-checked seed, the keys path, the owned keys, the validator, the app's chord grammar and the user-binding detector (NTERM-03)

**Wave 5** *(blocked on Wave 4 completion; shares `installer/terminal_keys.py` and the registry with 31-03)*
- [ ] 31-05-PLAN.md — The herdr-app entry end to end: script and cask entry, `NO_MACOS_INTEL`, `TERMINAL_KEYS["herdr-app"]`, skill row, forced pins, goldens and lifecycle through the production functions (NTERM-03)

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 31-06-PLAN.md — The in-container driver for the herdr-app install and removal proof: verdict functions, byte isolation with the other tool present in both orders, target-local residue allowance, transcript check; host tests only (NTERM-03)

**Wave 7** *(blocked on Wave 6 completion)*
- [ ] 31-07-PLAN.md — The `herdr-app` container target and its exclusion from the generic all-pass; proved on the host with a stubbed `ct`; the orchestrator runs the real target (NTERM-03)

**Wave 8** *(blocked on Wave 7 completion and the orchestrator's recorded run)*
- [ ] 31-08-PLAN.md — Container evidence in the registry comment and the skill row behind a hard gate on the recorded `herdr-app-container: PASS` line, and the catalog consistency guards for the two JSON-mode entries (NTERM-02, NTERM-03)

### Phase 32: Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP

**Goal**: Five pending tools are onboarded through the skill, each with its install, detection, update and removal route, without sudo, interactive login or damage to user data.
**Depends on**: Phase 27 (independent of the terminal mechanism; may run in parallel with Phases 28–31)
**Requirements**: ONB-11, ONB-12, ONB-13, ONB-14, ONB-15
**Note**: Absorbs the pending todos for Xcode CLT, Bruno, AWS CLI, gh-stack and the Playwright Flatpak Chrome path. One phase: every entry fits an existing method kind (`script`, `brew`, `cask`, `github_release` raw, `bun`) and is small. Research flags: AWS CLI gpg prerequisite; gh-stack's extension directory under a scratch `GH_CONFIG_DIR`; Playwright MCP headless launch smoke in a Fedora/Bazzite container.
**Success Criteria** (what must be TRUE):

  1. On macOS without the Command Line Tools, the Xcode CLT row shows them missing with the exact `xcode-select --install` command to run; no executor runs it (grep test) and Uninstall offers no removal.
  2. In a container, AWS CLI v2 installs through the official user-scope `install.sh` with gpg verification and no `--system`, falls back to brew `awscli` when that route is unavailable, updates with `aws update`, and an uninstall leaves `~/.aws` untouched.
  3. Bruno installs through the cask on macOS and a digest-verified AppImage for the host's architecture on Linux; no `bru` CLI is installed.
  4. gh-stack installs with `gh extension install https://github.com/github/gh-stack`, reads present from `gh extension list`, updates with `gh extension upgrade stack` and is removed with `gh extension remove stack` *(amended 2026-11-19, 32 D-10, D-11, needs confirmation: present from its manifest file, removed by its proven install folder; list and remove need a login)*; with an unauthenticated `gh` nothing blocks or prompts.
  5. Playwright MCP is registered as the pinned `bunx @playwright/mcp@0.0.85` in each agent host present, an existing `playwright` server entry is left as it was, the Flatpak Chrome path is exported on Bazzite only when the wrapper exists, and a write into `~/.claude/settings.json` asks for consent first.

**Plans:** 9 plans

Plans:
**Wave 1**
- [ ] 32-01-PLAN.md — The `script` kind's three validated keys: the fixed-argv `install`, the closed `handoff` name and the script-before-brew `prefer` sort key; the tracer runs a manifest through the loader and the engine to the runner (ONB-11, ONB-12, ONB-14)

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 32-02-PLAN.md — The detect-only Xcode CLT entry (exact hand-off, Update refused, no removal, no-spawn guard) and the gh-stack extension entry (install, manifest detection, update, folder removal) (ONB-11, ONB-14)

**Wave 3** *(blocked on Wave 2 completion)*
- [ ] 32-03-PLAN.md — The AWS CLI entry (official script first with gpg kept, brew fallback, `~/.aws` never named) and the Bruno entry (pinned per-arch AppImages, macOS cask, no `bru`) (ONB-12, ONB-13)

**Wave 4** *(blocked on Wave 3 completion)*
- [ ] 32-04-PLAN.md — The settings-ledger MCP writer: a three-level JSON insert and revert, and a merge-safe, receipt-recorded `playwright` server entry per host (Claude, Cursor, Copilot, OpenCode, Codex) plus Claude's env key (ONB-15)

**Wave 5** *(blocked on Wave 4 completion)*
- [ ] 32-05-PLAN.md — The Playwright MCP entry: the registration hook with Claude behind the confirmed `hook_register` step, the Flatpak Chrome export, the settled read, the removal sweep and the pinned `0.0.85` entry (ONB-15)

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 32-06-PLAN.md — The `aws-cli` container target (Fedora with gpg, a no-gpg debian-slim leg), the shared evidence gate and the driver verdicts; proved on the host with a stubbed `ct`; the orchestrator runs the real target (ONB-12)

**Wave 7** *(blocked on Wave 6 completion)*
- [ ] 32-07-PLAN.md — The `bruno` container target: install, three run modes (UNPROVEN reported, never a pass) and a removal that keeps the user's collections; the orchestrator runs the real target (ONB-13)

**Wave 8** *(blocked on Wave 7 completion)*
- [ ] 32-08-PLAN.md — The `playwright-mcp` container target: install, registration, the confirmed Claude step, a JSON-RPC launch smoke with the distro Chromium and removal; the orchestrator runs the real target (ONB-15)

**Wave 9** *(blocked on Wave 8 completion and the orchestrator's recorded runs)*
- [ ] 32-09-PLAN.md — Container evidence in the registry comments behind a hard gate on the recorded `aws-container: PASS` and `playwright-container: PASS` lines, the reported Bruno result, the skill row and architecture rules, and the catalog consistency guards (ONB-11 to ONB-15)

### Phase 33: Registry update bot

**Goal**: Catalog pins in `installer/registry.toml` stop going stale between manual runs: a bot proposes each upstream bump as a branch with its digest already verified, and the owner lands it through the protected flow.
**Depends on**: Nothing in v0.51.0 (CI-only; may run in parallel with Phases 27–32)
**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04
**Note**: Ingested 2026-11-19 from `.planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md` and `.planning/research/2026-11-17-update-automation.md` (feature 3). Dependabot cannot parse `registry.toml` and Renovate cannot refresh the paired `sha256`, so the bot wraps `verify-registry --write`. Open owner questions for discuss-phase: OQ-BOT-1..5 in `.planning/intel/context.md` (branch plus issue vs a real PR, PAT/App token vs `workflow_dispatch`, owner lands vs auto-land, date-only changes). Research flag: whether a dispatched CI run satisfies the required checks (test on a throwaway branch).
**Success Criteria** (what must be TRUE):

  1. A scheduled or dispatched bot run with upstream drift pushes a `bot/registry-<date>` branch whose `registry.toml` change bumps `version`, `sha256` and `verified` together; a run with no drift pushes nothing.
  2. The checks that branch protection requires run on the bot branch head (verified once on a throwaway branch), and the read-only weekly drift workflow keeps `contents: read`.
  3. No bot token pushes to `main`; the change reaches `main` only by branch push, green CI and fast-forward.
  4. With the new date-noise flag, a `--write` run whose only change is a `verified` date leaves `registry.toml` unchanged (unit test).

**Plans**: TBD

### Phase 34: Daily update check with a desktop notification

**Goal**: A user learns that installed tools (and tools-installer itself) have updates without opening the TUI, from one desktop notification a day at most, on Bazzite and macOS.
**Depends on**: Phase 33 (order only: the bot keeps the pins current first; no code dependency)
**Requirements**: NOTIFY-01, NOTIFY-02, NOTIFY-03, NOTIFY-04, NOTIFY-05, NOTIFY-06
**Note**: Ingested 2026-11-19 from `.planning/todos/pending/2026-11-17-daily-update-check-with-desktop-notification.md` and research feature 1. **Amends 24.2** (owner-approved at the ingest conflict gate, 2026-11-19): `24.2-SPEC.md:179` and `24.2-CONTEXT.md:43` put desktop notifications out of scope; this phase's SPEC records the reversal explicitly, and OQ-NOTIFY-1 decides whether failed runs notify too. Open owner questions: OQ-NOTIFY-1..5 in `.planning/intel/context.md` (notify on change vs every run, token vs anonymous, the installer self-check). Facts: cache staleness `STALE_AFTER = 7 days` (`installer/version_cache.py:44`), at most 20 fetches per refresh (`installer/version_status.py:143`), the schedule unit carries no GitHub token (`installer/daemon.py`).
**Success Criteria** (what must be TRUE):

  1. `--run-schedule check-updates` in a scratch HOME refreshes versions past the 7-day cache, writes exactly one `ok: N updates available` line to the shared schedule log, and changes no tool.
  2. Two runs with the same outdated set send one notification; a changed set sends another (test with a fake notifier).
  3. On Linux the runner calls `notify-send` with the session bus address passed to the child; with no `notify-send` it logs `notify skipped` and still exits ok.
  4. On macOS a failing `osascript display notification` logs `notify skipped` without failing the run, and the row detail names the one-time permission; the real-Mac check is a UAT line deferred to the owner's Mac.
  5. When the self-check is in scope, a checkout behind `origin/main` logs one self-update line from `git ls-remote` and the checkout is unchanged after the run.

**Plans**: TBD

### Phase 35: Opt-in auto-update, package managers first

**Goal**: A user who opts in gets their tools updated on a schedule in a safe order: package managers first, then the tools that depend on them, with nothing updated twice, nothing run as root and nothing updated after its manager failed.
**Depends on**: Phase 34 (reuses its notifier and outdated list)
**Requirements**: AUTOUPD-01, AUTOUPD-02, AUTOUPD-03, AUTOUPD-04, AUTOUPD-05, AUTOUPD-06, AUTOUPD-07, AUTOUPD-08
**Note**: Ingested 2026-11-19 from `.planning/todos/pending/2026-11-17-opt-in-auto-update-policy-managers-first.md` and research feature 2. A Schedules row, never a Policies row (PROJECT.md doctrine). **Amends 24.2 SCHED-01** (owner-approved at the ingest conflict gate, 2026-11-19): `24.2-SPEC.md:61` seeds every schedule on; this phase adds a per-row `default_on=False` and keeps the rule that the installer never changes a recorded user decision. Open owner questions: OQ-AUTOUPD-1..6 in `.planning/intel/context.md` (managers only first vs both, folding the five per-tool rows, the cask policy). Research flag: whether `uv self update` is safe while the runner runs under `uv run` (container check).
**Success Criteria** (what must be TRUE):

  1. A fresh install seeds `update-all` off, no Policies row exists for it, and once the user turns it on the installer never turns it off or on by itself.
  2. A unit test with brew, uv and two dependents asserts the order: managers (ranked by `resolve._RANK` *(amended 2026-11-19, 35 D-05, needs confirmation: ordered by ownership edges)*), then dependents grouped by owner and ordered by `deps.resolve_dependencies`; a failing manager produces a skip line for each dependent and no update call for them.
  3. Refused tools (native owner, SDKMAN, Volta, pins, os-package) are skipped with their refusal reason, a held run lock makes the run refuse instead of overlapping, no code path runs sudo, and brew casks are left alone on macOS by default.
  4. A run over three tools leaves one line per tool in its run log and one summary line in the shared schedule log, and a tool covered by a per-tool agent-CLI row is updated once per day.
  5. The e2e runs `--run-schedule update-all` in a disposable container, never on the host, and records the `uv self update` result.

**Plans**: TBD

## Progress

**Execution Order:**
27 → 28 → 29 → 30 → 31, with 32 after 27 in parallel with 28–31; 33 → 34 → 35 are independent of the terminal work and may run in parallel with it. Phase 27 fixes the rules every later phase applies; 28 turns three hard-coded dispatch sites into one table before any terminal is added; 29 proves the mechanism on existing files before the new terminals; 31 adds the JSON file mode only when a row needs it.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 27. Tool-onboarding skill: terminal defaults as rules | 4/4 | In Progress | - |
| 28. Shared terminal-keys mechanism | 4/4 | In Progress | - |
| 29. Terminal defaults for the terminals in the catalog | 0/TBD | Not started | - |
| 30. Onboard Ghostty | 0/TBD | Not started | - |
| 31. Onboard iTerm2 and the Herdr desktop app | 0/TBD | Not started | - |
| 32. Onboard Xcode CLT, AWS CLI, Bruno, gh-stack and Playwright MCP | 0/TBD | Not started | - |
| 33. Registry update bot | 0/TBD | Not started | - |
| 34. Daily update check with a desktop notification | 0/TBD | Not started | - |
| 35. Opt-in auto-update, package managers first | 0/TBD | Not started | - |

## Backlog

### Phase 999.1: Install selection lifecycle: show every direct selection in the Install review with an explicit disposition (will install / already installed / unavailable / blocked), keep each dragged dependency tied to the dependent that pulled it in, and after an install keep only the selections that still need action (clear succeeded/already-satisfied, retain failed/skipped/cancelled/unavailable/blocked) (BACKLOG)

**Status (2026-11-16):** completed by Phases 20 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 20-VERIFICATION PLAN-01..05 and 21-VERIFICATION UI-08; tests/test_session.py::test_remove_failed_is_retained_and_removed_is_not passes at HEAD.

**Goal:** [Captured for future planning]
**Source:** abandoned branch `feat/catalog-reliability-scope-reduction` (tip d8a3123, Jul 2026); plan text preserved in `999.1-*/source/`. HEAD already has the SDKMAN-only JVM methods, the cached version status and Phase 14's explicit "outdated tool is not silently skipped" behavior; the dispositions model (`PlanDisposition` in the branch's `install_plan.py`) and retained-selection semantics have no equivalent in HEAD (`rg PlanDisposition` = 0 hits).
**Also covers (2026-10-10 real-host audit, NOT fixed):** (a) a staged selection survives an Uninstall — `UnifiedApp._staged` is cleared only in `_install_closed` (`installer/wizard_app.py`), so a tool removed in Uninstall comes back to the catalog still selected for install; (b) an "already current" tool (wezterm) is selectable but there is no way to reinstall/repair it from the catalog — the run reports "already" and does nothing, and the terminal sync does not re-run (see 999.4).
**Also (ponytail audit F4, probe-confirmed, must fix):** inside Uninstall a removed tool stays selected and is counted again — the next confirm says "Removed 2 tool(s)" for one, a miscount on a destructive confirm. See `.planning/research/2026-10-11-ponytail-audit.md`.
**Cross-review (GPT-6.1-sol AR-09/AR-10):** selection is a set of ids, not a reviewed action plan; make it a plan with per-tool dispositions and outcomes, reconciled after every mutation (install AND uninstall), and trigger configuration follow-ups (terminal sync) from the plan, not from incidental `installed` outcomes.
**Before planning:** run /gsd-discuss-phase first to confirm what Phase 14 already covers and drop the overlap; the preserved plans assume pre-Phase-12 architecture (`status_coordinator`, `updates.py`), so treat them as intent, not as an executable plan.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 20 and 21 (v0.50.0)

### Phase 999.2: Installer receipts as direct-artifact ownership proof: record what this installer wrote (artifact path + checksum/receipt) so ownership of a script/download-installed tool is proven by a receipt instead of inferred "by elimination" (BACKLOG)

**Status (2026-11-16):** completed by Phases 19 and 22 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `installer/receipts.py`; 19-VERIFICATION STATE-03, 22-VERIFICATION LIFE-01/03; tests/test_receipts.py passes at HEAD.

**Goal:** [Captured for future planning]
**Source:** abandoned branch `feat/catalog-reliability-scope-reduction` (`installer/receipts.py` / `ReceiptStore`); plan text preserved in `999.2-*/source/`. Phase 16 resolves ownership from the filesystem and never considered receipts (no mention in 16-CONTEXT/RESEARCH); `rg ReceiptStore` = 0 hits in HEAD.
**Before planning:** decide whether Phase 16's filesystem-only attribution already makes this unnecessary; high conflict risk with `installer/ownership.py`, so evaluate after Phase 16 ships and its human UAT passes.
**Also covers (2026-10-10 real-host audit):** a `script` install is not removable from the Uninstall screen (`uninstall.plan_uninstall` plans only download/app kinds). kitty's `installer.sh` writes `~/.local/kitty.app`, the `~/.local/bin/kitty`/`kitten` symlinks and desktop files, and nothing records them. A receipt (or a registry-declared removal manifest) is the missing removal path. Until then the row says "installed by its own installer".
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 19 and 22 (v0.50.0)

### Phase 999.3: Registry can express a different artifact per OS and per arch: a `.dmg`/cask on macOS vs a vendor script or tarball on Linux, distinct per-arch assets, without bending an unrelated method kind (BACKLOG)

**Status (2026-11-16):** completed by Phase 18, narrowed with no new method kind (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 18-VERIFICATION REG-09; `app`/`tarball` take os/arch and `{ver}`; `installer/cargo_distrobox.py` shipped in Phase 24. The brew Intel macOS method is tracked in 999.15.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host audit (kitty: cask on macOS, `installer.sh` on Linux; tools shipping distinct per-OS/arch artifacts not behind a script). `Method` carries `os`/`arch` params, but a per-platform artifact that is neither a `github_release` asset pattern nor a script has no method kind.
**Before planning:** inventory which of the 90 entries already fake this with multiple methods, and research vendor artifact shapes per OS/arch before designing any schema change; `.claude/skills/tool-onboarding/SKILL.md` step 3 routes such tools here.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 18 (v0.50.0)

### Phase 999.4: Terminal shell sync follow-ups: export `SHELL` to the configured zsh inside kitty/WezTerm, and re-run the terminal sync when an install run reports the terminal as "already" present (BACKLOG)

**Status (2026-11-16):** completed by Phases 20 and 23 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 23-VERIFICATION CONF-05; `installer/session.py:374` runs the `terminal_sync`/`zshenv_shell` steps; the zshenv tests pass. A real-terminal look stays a human item in 23-VERIFICATION.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host audit. Inside kitty the prompt is zsh but `echo $SHELL` prints `/bin/bash`: there is no `chsh` (by design, Phase 15.6), and `installer/terminal_shell.py` sets kitty `shell`/WezTerm `default_prog` without `env SHELL=` / `set_environment_variables`. The sync runs only when `Summary.installed` is non-empty (`_install_state_changed`), so selecting an already-present wezterm never re-applies it.
**Before planning:** decide whether `SHELL` should be set at all (tools that read `$SHELL` to spawn subshells) and whether the "already" re-sync belongs to 999.1's dispositions.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 20 and 23 (v0.50.0)

### Phase 999.5: Finish the tool-onboarding skill revision with skill-judge: score `.claude/skills/tool-onboarding/SKILL.md` and apply its findings so the skill is well defined (BACKLOG)

**Status (2026-11-16):** completed by Phase 24 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 24-VERIFICATION ONB-03, `24-SKILL-JUDGE.md`, 0fcea8d3 (judge before and after). The rule to re-run skill-judge on every skill edit stays.

**Goal:** [Captured for future planning]
**Source:** user request 2026-10-10 after the skill was generalized in 41d642c (research-first, per-OS/arch artifacts, customization questions, "the skill cannot promise what the platform does not do"). The rewrite was never evaluated.
**Before planning:** run the `skill-judge` skill as the LAST step of any change to this skill (now and in future revisions); act on low-scoring dimensions (knowledge delta, NEVER list, description triggers, freedom calibration) without adding promises the platform cannot keep — anything that needs a missing capability stays routed to 999.2/999.3/999.4.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 24 (v0.50.0)

### Phase 999.6: One row-state model instead of three disagreeing classifiers, plus the earlier-phase promises the 2026-10-10 audit found unmet (BACKLOG)

**Status (2026-11-16):** completed by Phases 19 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `ToolState` at `installer/version_status.py:1019`; 19-VERIFICATION STATE-01..07, 21-VERIFICATION UI-01..03.

**Goal:** [Captured for future planning]
**Source:** 2026-10-10 real-host report ("siguen los mismos vicios, es como que no se reusan los componentes") and the ponytail audit of it.
**Root cause (NOT fixed):** three independent classifiers answer "what is this tool on this host" and disagree for script-kind installs: `installer/status.py` `is_installed` (catalog ✓), `installer/ownership.py` `resolve_ownership` (Owner column) and `installer/uninstall.py` `plan_uninstall` (Uninstall, download/app kinds only). kitty via `installer.sh` reads ✓, Owner "own installer", and Uninstall MANAGED/"package manager". 9050446's `_own_script_install` only patches the wording (a special case in `removal_hint`/`removal_label`); remove it once one shared row-state answers all three screens.
**Second structural risk (mitigated, not removed):** `VersionRefreshService` has one global ownership epoch but every refresh pass is tier-scoped. Any invalidate blanks every tier; only the visible one is refilled. 9050446 makes each catalog re-resolve on entry (the base tier never did), but an Uninstall row for a tool whose tier was not revisited still shows the generic hint until then (15.4-05 calls this best-effort).
**Earlier promises found unmet, by phase:**
- 15.4 goal: "both screens re-derive on entry so an install, update or removal is never hidden" — only install→Uninstall was built and verified; removal→catalog ✓ and the base (system) tier's `enter_view` were missing since Phase 2's `show_view`. Fixed in 9050446; the 15.4 VERIFICATION passed it anyway.
- 15.4 D-04/D-05 and 16 goal ("names whichever manager owns it; when it cannot be uninstalled the row says why"): script installs had no truthful Uninstall answer. Wording fixed in 9050446; removal still impossible (999.2).
- 15.6 goal (kitty/WezTerm open into zsh): works, but `$SHELL` stays `/bin/bash` and "already" outcomes never re-sync (999.4).

**Process gap to fix with it:** verifiers checked each screen's claim, not each direction of a refresh contract, so a half-built "re-derive on entry" passed twice. Require a per-view, per-direction test (install, update, uninstall; every tier including the base) for any refresh promise.
**Deepened by the ponytail audit (`.planning/research/2026-10-11-ponytail-audit.md`):** F6 — SEVEN places answer "is it here / who owns it / can we act" and disagree (a skill pack is ✓ in the catalog and "not installed" in Uninstall). F9 — one global ownership epoch, tier-scoped passes, THREE refresh owners and duplicate manager queries. F10 — the three tier screens are already one class (`CatalogScreen`), but `UnifiedApp` treats the base tier differently in 5 places (`show_view`, `_navigable`, `get_default_screen`, `_pending_status` stash, …); target: every view pushed the same way from an empty root. Order: one `ToolState` (F6) first, then one refresh owner (F9), then one `RowsScreen` (999.10) — otherwise a base class just moves the classifiers into one file.
**Cross-review (GPT-6.1-sol, `.planning/research/2026-10-11-architecture-review-gpt-6.1-sol.md`):** AR-03 agrees with F6/F8 and deepens it: the shared state must hold multiple observed installations (shadowed copies) and per-harness skill presence, not one owner + one boolean; `installer/platform.py` treats mutable facts (manager availability) as platform constants frozen at startup (NEW). AR-04 (verified at `installer/version_status.py:751`): a refresh pass superseded by an invalidate still merges its obsolete `statuses` into `_statuses` — only ownership is discarded (NEW); also separate in-memory invalidation from cache persistence success. Disagrees with ponytail F15: worker cancellation cannot replace generation/epoch checks (cancellation and host-state supersession are different events).
**Before planning:** /gsd-discuss-phase — decide whether the shared row-state lives in `status.py` or a new owner, and how it absorbs 999.2 receipts.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 19 and 21 (v0.50.0)

### Phase 999.7: Phase 16 verification debt left open at close (BACKLOG)

**Status (2026-11-16):** partial (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Done: CI green (17-VERIFICATION CI-01/03); CI-02 branch protection, via 26-VERIFICATION HOOK-05 and a live read-back (enforce_admins true, strict, both contexts); the owner-on-every-tier and ✓-cleared re-check (24-UAT tests 2-4). Left: 16-UAT tests 2-4 (live Execute enter on an already-current tool, a day-to-day dangling-shim session, the owner's review of the 11 prohibitions), a formal review of 9050446, and a local macOS run. Owner decision: run them, or close them on later-phase coverage.

**Goal:** [Captured for future planning]
**Source:** Phase 16 closed on 2026-10-10 by user decision with these unproven:
- 16-UAT tests 2-4 recorded as deferred follow-ups, not passes: Execute-screen enter on the real host with an already-current tool; a day-to-day catalog/Doctor session with the dangling pnpm shim (puppeteer); review of the 11 judgment-tier prohibitions.
- 9050446 (base-tier `enter_view`, installed-map re-derive on every catalog entry, script removal wording) did not get the formal `/gsd-code-review` or a Nyquist re-audit; only fail-first tests, the full suite and `make validate`.
- **`main` is RED (do first).** CI (`.github/workflows`, push to `main` only) never ran on the 599 branch commits; the first run, 38099159090 on 9a1c663, failed on both OSes. None of the failures touch 9050446's files. ubuntu: `tests/test_shellrc.py::test_reserved_word_prefixed_source_forms_execute_and_are_refused[time-shells0]` (`time .` under the runner's `/usr/bin/sh`). macOS: `tests/test_prune_tmp_linux_sh.py` x6 (bash 3.2 has no `mapfile`; the Linux-only script runs on macOS), `tests/test_app.py` x2 (long tmp paths wrapped in the console output), `tests/test_setup.py::test_interactive_wizard_shares_one_cache_with_the_daemon_policy` (StopIteration), `tests/test_version_status.py::test_ownership_of_under_an_unsynchronized_reader_never_serves_a_superseded_record` (timing-dependent race test). Correction (GPT-6.1-sol AR-05, verified): `.github/workflows/ci.yml` triggers on push to `main` AND on `pull_request`; CI never ran because Phase 16 merged locally without a PR, and branch pushes have no trigger. Prevention: require the PR check (branch protection) or add a branch-push trigger, and make tests deterministic per platform (bash 3.2, console width, `/usr/bin/sh`, no timing races).
- macOS never run locally.
- A real-host re-check that the reported symptoms are gone (Owner on every tier after an install, ✓ cleared after Uninstall) has not been done.

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 17 and 24 (v0.50.0)

### Phase 999.8: Per-method uninstall spec: each install method declares how it is removed on its OS/arch (manager remove, vendor uninstaller/script, or the exact paths it wrote), what config/data it leaves, and the removal policy (keep config by default, delete all, or ask), replacing today's generic Uninstall (BACKLOG)

**Status (2026-11-16):** completed by Phase 22 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `plan_removal`/`remove_proven` in `installer/uninstall.py:255,589`; 22-VERIFICATION LIFE-01/03/04, UI-04; test_a_recipe_tool_is_removed_by_its_vendor_command_first passes. Per-entry footprints are tracked in 999.14.

**Goal:** [Captured for future planning]
**Source:** user direction 2026-10-11: onboarding must know how each tool is removed per OS/arch (e.g. kitty: cask on macOS, `installer.sh` on Linux with `~/.local/kitty.app` + `~/.local/bin` links + desktop files), with a verifying removal script or a keep-config / delete-all choice, or a silent documented default — never a generic uninstall. Today `Tool.uninstall` is one free-text hint (3 of 90 tools set it) and `installer/uninstall.py` `plan_uninstall` treats download/app kinds generically.
**Evidence (2026-10-11 ponytail audit, `.planning/research/2026-10-11-ponytail-audit.md`):** F1 — Uninstall calls a tool removable when a file with the expected name exists: it would delete a `uv tool` ruff symlink; `drawio-desktop` and `drawio-cli` share one file so removing one removes the other; `make uninstall --yes` deletes them all without asking. F7 — install and uninstall compute paths with different formulas (Sublime on Linux reports "Removed" and leaves `~/.local/opt/subl`).
**Proposed design (2026-10-11, to confirm in discuss-phase):** removal lives on the METHOD, not on the tool and not as separate per-OS/arch knobs. A method is already scoped by `os`/`arch`, so its removal inherits that split for free (kitty: the macOS `cask` method and the Linux `script` method each carry their own removal). Three levels, so onboarding writes the minimum:
1. **Derived from the method kind — nothing written:** `brew`, `cask`, `apt`, `dnf`, `pacman`, `uv-tool`, `node` (manager remove), `sdkman` (`sdk uninstall <candidate>`). The skill only verifies the derivation is right for the tool.
2. **Derived from the method's own params — nothing written, but it needs one shared path formula and proof:** `github_release`, `tarball`, `app` remove exactly the path the install computed (`bin_dir` + `bin_name` / `app`). Today install and uninstall use different formulas (ponytail F7) and a name match counts as proof (F1); fix both, with a 999.2 receipt as the proof.
3. **Explicit recipe on the method — only where the kind cannot know:** `script` (vendor installers write paths we do not choose; kitty `installer.sh` → `~/.local/kitty.app`, `~/.local/bin/kitty`/`kitten`, desktop files) and `host_setup`. The recipe is the vendor uninstaller, the exact path list, or a verifying removal script.

Tool-level, shared by all its methods: config/data paths (an optional per-OS variant when they differ, e.g. `~/Library/...` on macOS) and the default config policy (`keep` default for user-edited config / `delete` / `ask`). `skill_pack` keeps its own `skill_lifecycle` removal.
**At removal time the method that ACTUALLY installed the tool decides,** not the registry's preferred one: the ownership resolver (+ 999.2 receipt) picks it. If the real owner is a manager the installer did not use (registry says `script`, user installed with brew), delegate to that manager or show its hint; never run another method's recipe.
**Registry scan (2026-10-11):** 76 of 90 tools have at least one non-manager method (github_release 89 methods, script 16, app 7, tarball 5, sdkman 5, skill_pack 7, host_setup 1) — level 3 needs explicit recipes only for the 16 `script` methods + 1 `host_setup`. 13 tools carry >2 method kinds (rg, jq, git, zsh, watch, docker, podman, opencode, vscode, sublime, kitty, wezterm, alacritty) — each method needs its removal checked. Shared-artifact case that breaks one-tool-one-path: `drawio-desktop` and `drawio-cli` share cmd/bin `drawio`; removal must refuse (or remove both, by explicit user choice) while the other is installed. Only `pi`, `drawio-desktop`, `drawio-cli` set today's free-text `uninstall` hint.
**Before planning:** /gsd-discuss-phase. Decide the schema (per-method `remove` block: kind, paths/command, config paths, default policy, prompt) together with 999.2 receipts (proof of what we wrote) and 999.3 per-OS/arch artifacts; the onboarding skill step 4b already records the researched recipe per tool until this lands. F1 is a data-loss risk: consider fixing the "a matching name is proof" check before the schema work.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 22 (v0.50.0)

### Phase 999.9: Correctness and data-safety fixes from the 2026-10-11 ponytail audit not covered by another item (BACKLOG)

**Status (2026-11-16):** completed by Phases 17 and 21 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Shell rc and tweak writes go through `atomic_write_text` (`installer/shellrc.py:304,317`); 17-VERIFICATION SAFE-04/09; 21-VERIFICATION UI-05/06/07.

**Goal:** [Captured for future planning]
**Source:** `.planning/research/2026-10-11-ponytail-audit.md` (ponytail-audit at ultra level, Opus). Findings marked probe-confirmed were reproduced headless by the auditor; the rest come from reading code and must be re-verified when planned.
- **F5 — must fix, data loss:** `~/.zshrc`, `~/.bashrc`, `~/.myshellrc` are written non-atomically in 3 modules (bypassing the project's atomic-write helper, `installer` `atomic_write_bytes`); a full disk can leave them empty. `clean_rc_duplicates` deletes lines by indices read before the confirm prompt, so an edit in between shifts which lines are deleted.
- **F2 — must fix (probe-confirmed):** under `make doctor` / `make fix` / `make uninstall` / `make guard`, Enter in a catalog silently exits the app and installs nothing — those routes never wire `ExecuteInputs`, and a test pins the behavior. Wire execute on every route (target: execute required).
- **F3 — must fix (probe-confirmed):** Policies never re-reads state on entry: after Uninstall removes the pip/npm ban, Policies still shows it ON and the next space runs the wrong verb (re-removes). Instance of 999.6's per-view, per-direction refresh rule.
- **F8 — should fix:** policy prerequisites are frozen at startup; after installing `watch`/`uv`, Policies still refuses the tweak that needs it.
- **F16 — nice to have:** Uninstall deletes files on the event loop; a VS Code or Sublime tree freezes the UI. Move removal to a worker.
- **F17 — nice to have:** a hidden `a` binding in Doctor rewrites shell files, while `a` means "select all" on neighbouring screens. Drop or make explicit.
- **Cross-review (GPT-6.1-sol):** AR-01 rates filename-based deletion authority CRITICAL (same as F1, lives in 999.8). AR-02 agrees with F5: shell mutation has no enforced safe-write boundary; add a preview-revision check (refuse to apply a deletion computed from an older read). AR-06 agrees with F2 and adds: installed-state re-derivation is also disabled on routes without Execute; moving `_build_app` alone is not enough if it keeps optional capability defaults.

**Fix order (auditor's verdict):** F1+F5 (data loss; F1 lives in 999.8) → F2, F4 (999.1), F3 → F7 (999.8), F8 → make `main` CI green (999.7) before merging any of them.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 17 and 21 (v0.50.0)

### Phase 999.10: Screen component architecture and lean-up: one RowsScreen family for Catalog/Uninstall/Policies, dead code out, wiring under the type checker (BACKLOG)

**Status (2026-11-16):** completed by Phases 21 and 25 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). 25-VERIFICATION passed 4/4: LEAN-01 dead policy/audit/host_setup code out; LEAN-02 `installer/compose.py` under pyright and coverage; LEAN-03 `wizard_app.py` split to 793 lines with no review ids. F15: 25-RESEARCH §1.3 kept the remaining Message classes by decision (the epochs stay, AR-04).

**Goal:** [Captured for future planning]
**Source:** `.planning/research/2026-10-11-ponytail-audit.md` section "Screen component architecture" + F10–F15; user direction 2026-10-11: the System/User/AI install screens must be one component, Uninstall the same family (removable-here first, then managed elsewhere, then nothing to do), Policies/Doctor built from the same blocks.
**Target (auditor's proposal, ~60 new lines in `ui_common.py`):** `AppScreen` → `RowsScreen[T]` with hooks `rows()` (read from 999.6's shared `ToolState` via `run_live`), `adapter(rows)`, `on_accept(ids)`; shared `enter_view()` after push, one app-level state-refreshed signal, selection pruned when a row stops being selectable, status cleared on leave. `CatalogScreen` (all tiers, Enter → Execute always wired), `UninstallScreen` (rows ordered: proven-ours removable → managed elsewhere with owner + removal text → not installed/unavailable; removal on a worker), `PoliciesScreen` (live `is_active`/prerequisites; ToolBrowser with activate-on-space). Doctor stays a text report but uses the same entry/refresh path. Modals: one `ChoiceModal` + one `ConfirmModal` (F14). Execute reads `ToolState` instead of re-classifying.
**Lean-up:** F11 — ~565 lines of agent-environment policy only tests use, `Tool.source`/`owner`/`uninstall` parsed but never read (note: 999.8 would give `uninstall` a real role), a probe that runs a binary that does not exist. F12 — `setup.py` `_build_app` holds the decisions behind F2/F6 but sits outside pyright and coverage. F13 — `wizard_app.py` does several jobs; ~35% is comments and 71 review IDs record review history instead of structure. F15 — seven `Message` classes + generation counters re-implement Textual's worker API.
**Estimated effect:** ≈2,100 production lines removed (≈900 of them comments), ≈150 added, ≈740 dead test lines removable, no new dependencies — estimate only.
**Cross-review (GPT-6.1-sol AR-08/AR-11/AR-12):** agrees shared chrome does not give a shared lifecycle and that tests freeze shape (source-count assertions, private-map assertions, registry prose tests) while one behavioral test pins the F2 silent exit; qualifies it — private access is fine when it protects a safety invariant; rewrite tests as contracts that survive a storage redesign. AR-12 confirms unreachable policy code and aspirational metadata (F11).
**Before planning:** depends on 999.6 (`ToolState` and one refresh owner first). Tests coupled to private attributes/source text may need rewriting with the move; keep behavior tests per view and per direction.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 21 and 25 (v0.50.0)

### Phase 999.11: Onboard herdr and re-onboard Alacritty through the tool-onboarding skill (install AND removal per OS/arch, no-reboot path on Bazzite, user customizations) (BACKLOG)

**Status (2026-11-16):** completed by Phases 23 and 24 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). registry.toml alacritty and herdr entries; 24-VERIFICATION ONB-01/02/06/07; 24-UAT tests 6-8 pass.

**Goal:** [Captured for future planning]
**Source:** user request 2026-10-13. Neither tool had a phase: herdr is absent from the registry; Alacritty entered outside any phase (commit 102c83e, 2026-10-09) before the skill gained steps 4b (removal) and 7 (customizations).
**herdr (research 2026-10-13):**
- Official: github.com/herdrdev/herdr, docs herdr.dev/docs/install. Latest v0.9.3 (2026-09-29). Release assets are raw binaries per OS/arch: `herdr-linux-x86_64`, `herdr-linux-aarch64`, `herdr-macos-x86_64`, `herdr-macos-aarch64` (+ Windows zip). NO checksum file is published (50 registry `github_release` methods already ship without one; record it in the entry's comment and `verified` key).
- Other routes: Homebrew formula `herdr` (bottled 0.9.3, linuxbrew too), vendor `curl -fsSL https://herdr.dev/install.sh | sh`, mise, Nix. Self-updates with `herdr update` (an installer-owned binary would drift from the catalog's version check — decide who owns updates).
- This host: `~/.local/bin/herdr` 0.9.3, installed by hand/vendor script (no receipt). The docs give NO uninstall instructions: removal recipe must be researched (binary, `~/.config/herdr/`, session server state, linked plugins).
- Candidate methods: `github_release` raw per os/arch into `~/.local/bin` (immutable-host friendly, no reboot) and `brew` formula; tier `user` (the human drives it), category terminal/multiplexer.
- **User customization (step 7, ask before applying) — extracted from the user's repo `castocolina/herdr-setup` (MIT, single commit 2b5ca2a, 2026-10-09, plugin v0.3.0, `min_herdr_version = "0.9.0"`, platforms linux/macos, needs `python3`):** *(amended 2026-11-07, 24 D-22, TUNE-04: the KEEP items are herdr's install tuning, applied with no question and reverted on uninstall)*
  - **KEEP — agent separator per workspace:** `plugins/workspace-here/mark.py` lists agents (`herdr agent list`), orders them by workspace number → tab number → pane id, and sets pane metadata token `rule=────────` on the first agent of each new workspace (clears it on the rest) via `herdr pane report-metadata <pane> --source herdr-setup.markers`. Rendered by config row `[{ token = "$rule", dim = true }]` as the first row of `[ui.sidebar.agents].rows`, with `row_gap = 1`.
  - **KEEP — current indicators:** token `here=◀` on the focused workspace (`herdr workspace report-metadata`) and on the focused pane (`herdr pane current`), cleared on all others; rendered bold by `{ token = "$here", bold = true }` in both `[ui.sidebar.agents].rows` (after `state_icon`, `workspace`, `tab`) and `[ui.sidebar.spaces].rows` (after `state_icon`, `workspace`). This sits beside herdr's native focus shading.
  - **KEEP — triggers:** the manifest re-runs `mark.py` on `[[startup]]` and on events `workspace.focused`, `tab.focused`, `pane.focused`, `pane.moved`, `pane.agent_detected`, plus a manual action `mark` ("Refresh markers").
  - **OPTIONAL (offer, default off) — local-first sort:** actions `sort-native` / `sort-local` persist a mode in `$HERDR_PLUGIN_CONFIG_DIR/sort_mode`; `local` adds token `rank` (0 = current tab, 1 = current workspace, 2 = rest) and sets a custom `agent.view` over the herdr socket (`agent.view.set`, label `local-first`), which REPLACES the native grouped/priority Settings menu; `native` clears it.
  - **DROP — personal preferences, not part of the feature:** `onboarding = false`, `[theme] name = "nord"`/`auto_switch = false`, `[ui.toast] delivery = "system"`, `status_indicators = "symbols"`, the second spaces row `["branch", "git_status"]`. Offer them as separate choices, never bundle them.
  - **DROP — install mechanics:** `tools/install.sh` replaces the whole `~/.config/herdr/config.toml` (with a timestamped backup) — the installer must MERGE only the two `rows` arrays and `row_gap`, never overwrite user config; the `herdr plugin unlink ramon.workspace-here` line only migrates a legacy plugin id.
  - **Known limits to fix or record:** (1) separators are placed by the plugin's own order (pane id is compared as a string, not herdr's `pane_order`); with `agent_panel_sort = "spaces"` or the local view, a mismatch puts the rule on the wrong row — set the order explicitly or sort by `pane_order`. (2) every focus event re-runs one `herdr` CLI call per workspace, per tab list and per agent (fine for a handful, slow for many). (3) `api()` ignores the socket reply, so a failed `agent.view.set` is silent. (4) It has not been run by the installer or verified here; it was only read.
  - **Platform fit:** a `postinstall` can only select a NAMED hook from `POSTINSTALL_HOOKS`; it must not run the repo's Makefile. A hook would: place the plugin from a pinned source (vendored files or the repo at a pinned commit), `herdr plugin link <dir>`, merge the `rows`/`row_gap` keys into `config.toml` (needs a TOML-preserving merge — today the project only reads TOML), `herdr server reload-config`, and record what it wrote. Removal: `herdr plugin unlink herdr-setup.markers`, remove the `$rule`/`$here` row entries it added, and `agent.view.clear` if local sort was on.
- **Classification (decided 2026-10-13):** tier `user` (the human launches and drives it, like a terminal/multiplexer — skill step 5), `audience = "both"` (agents drive it too), category terminal/multiplexer. Three separate layers:
  1. **herdr binary → its own registry entry** (methods above).
  2. **Agent integrations → a `postinstall` hook of herdr (e.g. `herdr-integrations`), NOT separate registry entries.** `herdr integration install|uninstall|status <agent>` is herdr's own idempotent, versioned installer: agents report state through hooks (instead of screen detection) and sessions survive a herdr server restart. Supported names (herdr 0.9.3): pi, omp, claude, codex, copilot, devin, droid, kimi, opencode, kilo, hermes, qodercli, qwen, letta (experimental), cursor, mastracode, antigravity-cli, grok. Each writes one file per agent, e.g. `~/.claude/hooks/herdr-agent-state.sh`, `~/.config/opencode/plugins/herdr-agent-state.js`, `~/.cursor/herdr-agent-state.sh`, `~/.pi/agent/extensions/herdr-agent-state.ts`. Same shape as `codegraph-mcp-register`/`rtk-register`: gate on `present_agent_hosts()`, install only for hosts present, detect with `herdr integration status`, remove with `herdr integration uninstall <agent>` (this IS the removal recipe 999.8 needs). Not verified yet: whether an integration also edits the agent's main config (e.g. registering the hook in `~/.claude/settings.json`) — check before shipping (merge-safety rule). Gap: a hook runs only when herdr installs; an agent installed later (pi) would need the integration step re-run from the post-mutation plan (999.1/999.4 family).
  3. **The `herdr` skill (teaches an agent to split panes, run commands without stealing focus, read other agents' output, wait/coordinate, query agent states) → its own `skill_pack` registry entry, tier `ai`, `requires = ["herdr"]`,** like ponytail/matt-pocock-skills: source `skills/herdr/SKILL.md` in herdrdev/herdr, install `npx skills add herdrdev/herdr --skill herdr -g`, status via skills-lock probes; `herdr --skill` prints the version-matched copy. It is optional per user and per harness, so it must not be bundled into herdr's install. *(void 2026-11-02/2026-11-07: skill packs are dropped and 23.1 D-02 deletes the kind; herdr ships no skill pack, 24 D-11)*
- **This host today (`herdr integration status`, 2026-10-13):** claude current (v10), opencode current (v13), cursor current (v1); **pi not installed** although pi is in use — a direct gain from layer 2.

**Alacritty — no-reboot path on Bazzite (research in `docs/research/2026-10-09-alacritty.md`, re-checked 2026-10-13):**
- Upstream ships NO Linux binary, AppImage, .deb or .rpm; no Homebrew formula (the macOS cask is disabled since 2026-09-01, Gatekeeper); `flatpak search alacritty` empty. `rpm-ostree` layering is the only native route and needs a reboot — rejected by the user.
- No-reboot options: (a) Fedora Distrobox matching the host (`dnf install alacritty` 0.17.0) + `distrobox-export --app alacritty`, with the terminal shell pointed at the host via `distrobox-host-exec` and terminfo exported; (b) build with cargo inside that Distrobox and place the binary in `~/.local/bin` (host runtime libs suffice; desktop entry, terminfo and man pages are extra post-build steps into `~/.local/share`); (c) wait for an upstream Linux AppImage/tarball with checksum and copy WezTerm's method.
- Platform gap: the installer has NO `distrobox` method kind and `cargo` builds are out of scope, so today the row correctly says "not available: immutable host". Choosing (a) or (b) means a new method kind (install + detect + version + owner + removal: `distrobox-export --app alacritty --delete`, container removal policy) — design it with 999.3/999.8, not as a special case.
- Customizations to offer (step 7): alt/option+arrow word navigation and Cmd+K / Ctrl+Shift+K clear-scrollback bindings, shell = discovered zsh (as 15.6 does for kitty/WezTerm; Alacritty is not covered by `installer/terminal_shell.py` today). *(amended 2026-11-07, 24 D-22/D-23: written at install with no question, not offered)*

**Before planning:** run `.claude/skills/tool-onboarding` end to end for each tool and then skill-judge (999.5). Depends on 999.8 (removal spec) and, for Alacritty, on a decision about a Distrobox method kind.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phases 23 and 24 (v0.50.0)

### Phase 999.12: Register codegraph and graphify hooks for the copilot host (BACKLOG)

**Status (2026-11-16):** completed by Phase 24.3 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). `_CODEGRAPH_TARGETS` maps copilot to `copilot-cli` (`installer/postinstall.py:219-226`); test_copilot_codegraph_round_trip passes; graphify stays unregistered by decision. codegraph itself is being retired (todo 2026-11-14).

**Goal:** When copilot (added in 23.2) is present, the codegraph and graphify postinstall hooks register for it like the other agent hosts, are recorded in `receipt.hooks`, and unregister on removal.
**Requirements:** TBD
**Evidence (live, 2026-11-07, 23.2 analyzer):** codegraph 1.6.2's target id is `copilot-cli` (writes `~/.copilot/mcp-config.json`; `copilot` is rejected); graphify accepts `install --platform copilot`.
**Why deferred (23.2 D-22):** 23.2 TUNE-06 asks only for `recommends`; adding the host to `_CODEGRAPH_TARGETS` makes codegraph read `≈` on every machine with `~/.copilot`, a behaviour change for existing installs that needs its own spec. Phase 24.3's catalog audit may pick it up. *(amended 2026-11-07, 24.3 SPEC R9: the codegraph half is absorbed by Phase 24.3 — copilot joins `_CODEGRAPH_TARGETS` as `copilot-cli`; graphify stays unregistered because its installs are project-scoped)* *(closed 2026-11-14: absorbed by Phase 24.3 — copilot joins codegraph's hook as copilot-cli (24.3-08); graphify stays unregistered, its installs being project-scoped)*

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.13: Move Pi off the host-setup handoff to a directly installed, updatable method (BACKLOG)

**Status (2026-11-16):** completed by Phases 24.5 and 25 (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Bun method with a pnpm fallback (80331678); host_setup kind retired (04ad08b8); the Pi registry tests pass. Nit: the pi comment at registry.toml:3285 still says the vendor-script change "waits in Backlog 999.13".

**Goal:** The catalog installs, updates and removes Pi itself instead of printing a pnpm handoff: a method the installer runs with no privilege escalation (the `node` kind through pnpm with Pi's Node floor, or Pi's own installer only if it can run without `sudo`), with `pi update` or the manager's update as the update route, a receipt, and the scheduled update from Phase 24.2 following it.
**Requirements:** TBD
**Evidence (live, 2026-11-07, 24.3 analyzer):** Pi's README now leads with `curl -fsSL https://pi.dev/install.sh | sh` ("pins all dependencies and updates Pi with `pi update`"), with `npm install -g --ignore-scripts` as the alternative; that installer mentions `sudo` six times (Node install) and writes PATH profile lines. npm `@earendil-works/pi-coding-agent` latest 1.5.0, `engines.node >=22.19.0`. The registry entry is a `host_setup` handoff (`installer/host_setup.py:28-41`) whose desc "setup remains interactive" is stale. The host's Pi 1.3.0 is a bun global install. *(amended 2026-11-14, 24.3: Pi npm latest 1.5.2; pi.dev/install.sh mentions sudo 15 times; the registry text was refreshed in 24.3-06)*
**Why deferred (24.3 D-14):** Phase 24.2 D-16 builds Pi's scheduled update around the reviewed host-setup command, and 24.3's scope applies only Pi's MCP finding; changing the method there would make 24.2's path dead code. If this is promoted before 24.2 executes, amend 24.2 D-16 first.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.14: Declare the removal footprint of catalog entries that lack it: config_paths and script paths per the first catalog audit (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). Only 4 of the 30 flagged ids (gh, glow, tealdeer, kitty) carry `config_paths`, all pre-dating the audit; no footprint was declared since 2026-11-13.

**Goal:** Every catalog entry the 2026-11-13 audit marked "removal recipe and paths" gets its user config, state or data directories declared (`config_paths` with the keep default, `paths` on script methods), so Uninstall lists them and a delete choice reaches them; includes the schema gaps the audit found (an absolute system path such as `/Applications/kitty.app`, a legacy `~/.wezterm.lua` one level under `~`, a per-OS `config_paths` for glow, a bun owner for a global Pi, codegraph's `~/.codegraph` after a vendor self-upgrade).
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** `.planning/audits/catalog/2026-11-13/SUMMARY.md` Drift rows with check `removal recipe and paths` (bat, eza, zoxide, lazygit, gh, starship, oh-my-zsh, direnv, glow, xh, gitui, lazydocker, docker, colima, dive, miller, tealdeer, fx, dasel, sdkman, bun, vale, broot, vscode, kitty, wezterm, glab, graphify, pi, codegraph), each with its upstream citation and risk in `dispositions.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.15: Catalog install-method and update-route currency from the first catalog audit (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). At HEAD: gron still lists github_release before brew; vale is still `errata-ai/vale`; codex has no `update`; mmdc `min_node` is still 22.12.0; the brew macOS amd64 method is still present.

**Goal:** Entries whose install method, update argv or runtime expectation drifted from the vendor's current guidance are brought current or the reason is recorded in `# Verified`: distro packages where current (eza, gum, glow, xh, difftastic, gitui, duf), a checksummed method first (gron), the vendor's apt repo or macOS pkg (docker, podman), glab's supported Linux route, the macOS Homebrew amd64 script method (brew), the `codex update` route, the vale slug, mmdc's Node floor, puppeteer's linux arm64 gate, Volta versus mise, and the daemon or machine expectation of lazydocker, docker and podman.
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** `.planning/audits/catalog/2026-11-13/SUMMARY.md` Drift rows with checks `install method`, `update argv` and `postinstall hook` that no 24.3 commit resolved, each with its source in `dispositions.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.16: Version probe for zip reads the copyright years instead of the version (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). A scratch probe at HEAD still returns `1990-2008` for zip's version output.

**Goal:** `extract_observed_version` stops reading `1990-2008` from `zip --version`'s first line and reads `Zip 3.0` from the second.
**Requirements:** TBD
**Evidence (live, 2026-11-13, first catalog audit):** script finding at `installer/versions.py:211` in `.planning/audits/catalog/2026-11-13/findings.toml`.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.17: Duplicate-code gate: pick a duplicate-code detector and add it as a quality gate with its own `make` target and pre-commit hook (BACKLOG)

**Status (2026-11-16):** pending (triage b1ce5f61 (`.planning/todos/TRIAGE-2026-11-16.md`)). No duplicate-code target or hook exists in the Makefile or `.pre-commit-config.yaml`.

**Goal:** A commit fails when a new block duplicates existing code beyond an agreed threshold, reported by a `make duplicated-check` target that also runs as its own hook entry and through `make validate`.
**Requirements:** TBD
**Source:** owner, 2026-11-16, during the Phase 26 discussion (26 D-13). No duplicate-code gate exists: ruff does not detect duplication and pylint (which has `duplicate-code`) was ruled out on 2026-10-15.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.18: Tool-onboarding skill: terminal emulator and IDE defaults (zsh on Linux, Option/Alt word navigation on macOS, clear-screen shortcut) (BACKLOG)

**Goal:** The tool-onboarding skill states, as defaults rather than questions, what every terminal emulator and every IDE with a built-in terminal gets when it is onboarded or reviewed: (1) on Linux, Bazzite included, zsh is the shell the terminal launches, through the terminal sync in `installer/terminal_shell.py`; (2) on macOS, Option/Alt+Left/Right moves by word; (3) a clear-screen shortcut, Cmd+K on macOS and Ctrl+Shift+K on Linux. (2) and (3) are install tuning (a `post_install` action with an owned region, like Alacritty's `alacritty-keys`), never a Policies row, and they respect bindings the user already defines. The skill still asks the user only about extras.
**Requirements:** TBD
**Source:** owner, 2026-11-16. Today `.claude/skills/tool-onboarding/SKILL.md:185-191` lists these as prompts to ask the user ("Do not enable them silently"), so only Alacritty got the keys; kitty and WezTerm got the zsh sync only.
**Order:** first. 999.19–999.22 run through this skill and depend on it.
**Done when:** the skill text carries the three defaults with the per-OS mechanism and the conflict rule, and skill-judge is run before and after the edit (the standing rule from 999.5).

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 27 (v0.51.0)

### Phase 999.19: Terminal defaults for the terminals already in the catalog, applied through the tool-onboarding skill (BACKLOG)

**Goal:** Review kitty, WezTerm, Alacritty and herdr with the tool-onboarding skill (review mode) after 999.18, so each meets the terminal defaults on every OS it installs on. Known gaps at 2026-11-16: kitty and WezTerm get no keys region on Linux or macOS (only the zsh sync, which is Linux-only by design); Alacritty has its keys on Linux and no macOS method; herdr (the multiplexer, not Herdr IDE) syncs `default_shell` to zsh, and it must be checked that it passes Alt+Left/Right and the clear shortcut through to the host terminal.
**Requirements:** TBD
**Source:** owner, 2026-11-16; code facts from `installer/terminal_shell.py:477-482` (Alacritty keys) and `:893-1031` (the sync covers kitty, WezTerm, Konsole, Alacritty and herdr on Linux and skips macOS).
**Open:** whether Konsole (detected and shell-synced, the Bazzite default, not a catalog entry) also gets the keys region; a possible clash with kitty's own Linux binding for Ctrl+Shift+K (to verify against kitty's defaults).
**Pending work (one todo each, 2026-11-16):** `.planning/todos/pending/2026-11-16-terminal-defaults-for-kitty.md`, `…-for-wezterm.md`, `…-for-konsole.md` (owner decision first) and `…-for-herdr.md` (pass-through check). Alacritty has nothing pending: its Linux keys are written and it has no macOS method.
**Depends on:** 999.18.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 29 (v0.51.0)

### Phase 999.20: Onboard Ghostty through the tool-onboarding skill (BACKLOG)

**Goal:** Ghostty is in the catalog as a terminal emulator, onboarded with the tool-onboarding skill after 999.18, so it meets the terminal defaults (zsh sync on Linux, Option/Alt word navigation on macOS, the clear-screen shortcut).
**Requirements:** TBD
**Source:** owner, 2026-11-16. Not in the catalog, backlog or todos at that date; only old design notes name it as the app that would force `.dmg` support (`docs/superpowers/BACKLOG.md:54`). To research: macOS cask vs `.dmg` (no `.dmg` method kind exists), Linux packaging and the Bazzite path (no native packages there), removal footprint.
**Depends on:** 999.18.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 30 (v0.51.0)

### Phase 999.21: Onboard Herdr IDE through the tool-onboarding skill (BACKLOG)

**Goal:** Herdr IDE is in the catalog, onboarded with the tool-onboarding skill after 999.18. It is a different product from the `herdr` entry (the terminal multiplexer for coding agents, `herdrdev/herdr`); if it hosts a terminal it meets the terminal defaults.
**Requirements:** TBD
**Source:** owner, 2026-11-16. Not in the catalog, backlog or todos at that date. To research upstream: what it ships per OS and arch, install, update and removal, the Bazzite path, and its relation to the `herdr` entry (separate entry, dependency or `recommends`; shared `~/.config/herdr`).
**Depends on:** 999.18.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 31 (v0.51.0)

### Phase 999.22: Onboard iTerm2 through the tool-onboarding skill (BACKLOG)

**Goal:** iTerm2 is in the catalog as a macOS-only terminal emulator, onboarded with the tool-onboarding skill after 999.18, with the terminal defaults (Option as Esc+ for word navigation, Cmd+K clear) plus the customizations the owner asked for.
**Requirements:** TBD
**Source:** promoted 2026-11-16 from the todo `2026-10-15-add-iterm2-macos-only-entry-after-tool-onboarding-refactor.md` (now in `.planning/todos/completed/`), which holds the five requested customizations and the dynamic-profile mechanism notes. The owner must still name the products behind its items 4 and 5.
**Depends on:** 999.18.

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

**Absorbed by:** Phase 31 (v0.51.0)

### Phase 999.23: Workflow lint gate for GitHub Actions files (BACKLOG)

**Goal:** Every commit that touches `.github/workflows/*.yml` is linted by one gate with its own pre-commit entry and make target (actionlint-class), so an expression or shell error inside a `run:` block fails before CI.
**Requirements:** TBD
**Source:** Phase 33 discuss, 2026-11-19 (33 D-16): no gate lints workflow YAML today; phase 33 records one ad-hoc containerized run instead. The gate needs a dev-setup install of the linter (the developer runs `make dev-setup`; agents do not).
**Depends on:** Phase 33.

### Phase 999.24: Measure smart test selection per commit (BACKLOG)

**Goal:** A one-day measurement spike decides whether commit-time test selection is worth building: run the suite once with `--cov-context=test`, map changed lines to tests, and replay the last ~100 commits to see how many tests each would select against the full run.
**Requirements:** TBD
**Source:** Owner question during the v0.51.0 autonomous run, 2026-11-20, and the research report `smart-test-selection.md` (a read-only sonnet agent): a static AST import graph saves little because `tests/conftest.py` imports 7 installer modules (57 of 78 installer modules sit in that closure), so any change to them selects all 105 test files; replayed over 300 code commits, 65 to 78% would still run at least 90% of the suite and the modelled saving is 16 to 27% of a 78 s suite. 57 of 105 test files also read non-Python files that a graph cannot see. The timings are modelled, not measured, because the agent could not run pytest.
**Revisit when:** the full suite passes about 3 minutes, or test time passes about 20% of an autonomous run. A commit-stage test hook would contradict `tests/test_hook_wiring.py` (tests are push-stage only), so any design is an advisory `make test-affected` first.
**Depends on:** none.

### Phase 999.25: Phase 27 follow-ups: onboarding skill evals and structure (BACKLOG)

**Goal:** The tool-onboarding skill (the document under `.claude/skills/`, not the project's pytest suite) gains the pieces the skill-judge scored lowest, without changing a rule or a table row.
**Requirements:** TBD
**Source:** Phase 27 skill-judge verdicts (final 73.6%, grade C, D7 = 2 of 15):
- add `evals/evals.json` and `evals/trigger-queries.json` to the skill with shape tests, as the catalog-audit skill has (the largest single loss; new files under the gitignored `.claude/` need `git add -f`);
- resolve the contradiction in step 2 between "the catalog installs no skills" and the advice to symlink into a host's skills directory;
- move the terminal-only block (defaults, closed table, Conflicts, macOS testing) to a gated `references/` file and repoint `tests/test_tool_onboarding_skill.py`, which cuts the always-loaded length (331 lines);
- cut step 1 to one line and state the never-asked rule once.
**Depends on:** Phase 27.

### Phase 999.26: Skill-verdict test tidy (BACKLOG)

**Goal:** The pytest helpers that compare skill-judge verdicts lose their duplication and check the rubric maxima in one place. This is project test code only; it does not change the skill or any verdict.
**Requirements:** TBD
**Source:** Phase 27 code review `27-REVIEW.md`, deferred findings IN-04, IN-05 and IN-06:
- have `parse_verdict` in `tests/skill_verdicts.py` check `max` against `RUBRIC_MAX` for every verdict, so the catalog-audit tests get the check too (`verdict_regressions` does it for tool-onboarding only today);
- share one verdict fixture builder in `tests/skill_verdicts.py` instead of the two near-identical ones in the two test modules, which also removes the four aliased import lines;
- make `rule_items` in `tests/test_tool_onboarding_skill.py` reuse `_items`.
**Depends on:** Phase 27.

### Phase 999.27: Make shellrc apply_block and strip_block exact inverses (BACKLOG)

**Goal:** Applying a managed block to a shell rc file and then stripping it returns the file byte for byte, for every input, so uninstalling a tool never leaves a stray blank line in a user rc file.
**Requirements:** TBD
**Source:** Phase 28 plan review, 2026-11-20 (28 SPEC R3 amended, needs confirmation). Measured on the real functions in `installer/shellrc.py`: apply then strip returns `""` unchanged and `"a\n\n"` unchanged, but turns `"a\n"` and `"a"` into `"a\n\n"`, `"a\nb\n"` into `"a\nb\n\n"`, `"a\n\n\n"` into `"a\n\n"`, and `"\n"` and `"\n\n"` into `""`. The behavior is shared by every shell-init bundle and the PATH block and is pinned by `tests/test_shellrc.py`, so changing it is its own piece of work.
**Depends on:** none.

### Phase 999.28: Terminal keys mechanism follow-ups (BACKLOG)

**Goal:** The shared terminal-keys mechanism and the zsh Ctrl+L bundle lose the small rough edges the phase 28 code review left open, without changing what is written for any row.
**Requirements:** TBD
**Source:** Phase 28 code review `28-REVIEW.md`, deferred info findings:
- IN-01: in single-shell mode with bash, zsh never sources `~/.myshellrc`, yet the zsh row reads tuned; this predates phase 28 and affects every shell-init bundle, so the status check needs to know whether the shell that owns the bundle sources the file;
- IN-02: use the shared created-marker constant in `installer/terminal_shell.py` instead of the hardcoded filename, without creating an import cycle with `installer/terminal_keys.py`;
- IN-03 and IN-04: remove the `alacritty_keys_plan_for_text` wrapper and share the drift check between `apply_terminal_keys` and `terminal_keys_pending`;
- IN-07: when the first `Writes` row lands (phase 29), the keys summary must not claim keys were written when only the snippet was, and the snippet needs a conflict check.
**Depends on:** Phase 28.

### Phase 999.29: Terminal defaults follow-ups (BACKLOG)

**Goal:** The kitty, WezTerm, Konsole and herdr terminal defaults lose the rough edges the phase 29 reviews accepted, without changing what is written for any row.
**Requirements:** TBD
**Source:** Phase 29 review disposition `29-REVIEW-DISPOSITION.md`, accepted items:
- a changed resolved config path between two applies overwrites the first created-file record (track one record per created path);
- the Konsole report rides on the zsh row, so a host with Konsole and no zsh gets none;
- the herdr probe slices received bytes by expected length, so one lost chord shifts the blame onto later chords (mark-delimited slicing);
- the kitty keys region at the top of the file pushes a `# vim:` modeline out of its first lines;
- `Placement` couples the generic region helper to the WezTerm skeleton;
- a region the user moved (kitty keys region below an unscanned include, WezTerm shell region after `return config`) is not repaired.
**Depends on:** Phase 29.

### Phase 999.30: Ghostty onboarding follow-ups (BACKLOG)

**Goal:** The Ghostty entry loses the rough edges the phase 30 reviews accepted, without changing what is written for any row.
**Requirements:** TBD
**Source:** Phase 30 review disposition `30-REVIEW-DISPOSITION.md`, accepted or deferred items:
- an installer-created Ghostty config that becomes empty while the user later adds a legacy `config` makes the resolver switch, so removal leaves the created file with a mismatch warning (clean the recorded created path under the existing safety checks);
- `_ghostty_plan` scans the process `HOME` and `environ` instead of the values passed to `apply_terminal_keys` (thread them through `KeysRow.plan`);
- a reinstall overwrites a receipt-recorded menu entry the user edited (fingerprint the leaf);
- the menu step runs on install only, not on update, and uses literal `~/.local/share` instead of `XDG_DATA_HOME`;
- the menu leaves are told apart from other receipt leaves by path (a distinct artifact kind would be cleaner);
- community rebuild tags such as `v1.4.0+1` cannot be expressed with one `{ver}` template, and bump tooling ignores build metadata.
**Depends on:** Phase 30.

### Phase 999.31: iTerm2 and herdr-app onboarding follow-ups (BACKLOG)

**Goal:** The JSON-mode terminal entries lose the rough edges the phase 31 reviews accepted, without changing what is written for any row.
**Requirements:** TBD
**Source:** Phase 31 review disposition `31-REVIEW-DISPOSITION.md` and the plan reviews `31-REVIEWS.md`, accepted or deferred items:
- the per-key ownership record is a single-path ledger: a keys-path change drops the old path's ownership proof, and a stale created marker bound to the old path makes strip return early for the new file (keep a ledger per path);
- the symlink check is separate from the read, write and delete that re-resolve the path (a no-follow operation), and a symlinked parent directory is not refused;
- the new ownership variants write the file before the created marker and the ledger, as `commit_region` does for region rows (recovery for an interrupted write);
- the generic owned-keys apply special-cases `tool_id == "herdr-app"` next to `row.validate`, and the removal hook and the herdr-app paths use `Path.home()` and `HOST_SETTINGS_OS` instead of the injected values;
- strip deletes the iTerm2 profile file on marker and GUID proof even if the user appended a second profile to it;
- the stale `switched` record after a two-failure sequence (restore succeeds, record update fails, cask removal fails) heals only on reinstall.
**Depends on:** Phase 31.
