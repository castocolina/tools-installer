# Phase 31: Onboard iTerm2 and the Herdr desktop app — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.18 (gate: ≤ 0.20)
**Requirements:** 6 locked

## Goal

A macOS user gets iTerm2 with an installer-owned default profile that meets the terminal defaults, and the Herdr desktop app installs on Linux and Apple Silicon macOS as an entry distinct from the `herdr` multiplexer, with the same defaults.

## Background

- Neither entry exists in `installer/registry.toml`; the research is `.planning/research/SUMMARY.md` (Phase 4 section) and `FEATURES.md`. `herdr` (the multiplexer) is the only herdr entry (`id = "herdr"`, `github_release`).
- Live facts (2026-11-19, read-only): Homebrew cask `iterm2` is at 3.7.8 and needs macOS ≥ 13; cask `herdr-app` is at 0.1.16, arm64 only, and declares an `app` and a `binary` artifact; `https://releases.herdr.dev/app/install.sh` answers HTTP 200 as a shell script; `herdrdev/herdr-app` publishes no GitHub release (the releases endpoint returns 404), so its Linux route is the vendor script, not `github_release`.
- Owner decisions 2026-11-16: "Herdr IDE" is the Herdr desktop app (`herdrdev/herdr-app`), never the `herdr` multiplexer; the iTerm2 profile becomes the default profile and an uninstall restores the previous default; new tabs, windows and panes open in the current directory on every terminal; iTerm2 items 4 and 5 ("Show Focus Cursor", the agent-collaboration extension) stay future until the owner names the products.
- Both need a whole-file JSON mode the shared keys mechanism (phase 28) does not have: an iTerm2 Dynamic Profile and the herdr app's `keys.json` / `keys.macos.json`. Phase 30 (Ghostty) lands first and both extend the same table, so the phases run in sequence.
- Research flags for discuss: iTerm2's Keyboard Map encoding and default-profile behavior (capture on a Mac or defer to UAT), and the herdr app's keys path and `install.sh` footprint.

## Requirements

1. **iTerm2 install and Dynamic Profile (NTERM-02, profile)**: iTerm2 installs from the cask on macOS only (its Linux and other rows read unavailable), and the installer writes one owned Dynamic Profile that sets Option as Esc+, clears screen and scrollback on Cmd+K (sending Ctrl+L), opens new tabs, windows and panes in the current directory, and uses the requested color scheme.
   - Current: no iTerm2 entry or profile writer.
   - Target: a `cask` entry with `os = ["macos"]`, a postinstall row, and a pure generator for the profile JSON.
   - Acceptance: golden-file test of the profile JSON passes on both OSes; the entry has no Linux method and reads unavailable there; the profile contains Option-as-Esc+ for the left and right Option keys and no other key-mapping change.

2. **iTerm2 default profile and restore (NTERM-02, default)**: After an iTerm2 install the installer's profile is the default profile; an uninstall deletes the profile and restores the previous default.
   - Current: n/a.
   - Target: a before/after record of the previous default profile identity and a restore step.
   - Acceptance: a golden test of the before and after preference state passes (install sets, uninstall restores the exact previous value, including "none set"); the real-Mac check is a UAT line marked deferred to the owner's Mac.

3. **Herdr desktop app is its own entry (NTERM-03, identity and install)**: The Herdr desktop app is a catalog entry with an id distinct from `herdr`, installed by the user-scope vendor `install.sh` with no sudo on Linux and by the cask on Apple Silicon macOS, and unavailable on Intel macOS; installing or removing one entry leaves the other's binaries and `~/.config/herdr` intact.
   - Current: only the `herdr` multiplexer exists.
   - Target: a new entry (id chosen in discuss) with a `script` method (linux) whose `paths` name only the app's own files, and a `cask` method with `arch = ["arm64"]`.
   - Acceptance: registry tests load both entries with distinct ids; an Intel-macOS fixture reads unavailable; in a container, installing the app then removing it leaves the multiplexer's binary and `~/.config/herdr` byte-identical, and the reverse.

4. **Herdr app keys meet the defaults (NTERM-03, keys)**: The Herdr desktop app's keys files meet the terminal defaults on both OSes; on Linux Ctrl+Shift+K clears and the displaced picker binding is named in the install note; a binding the user defined is kept and reported `partial: kept yours`.
   - Current: n/a.
   - Target: a JSON-mode row in the keys mechanism writing the app's keys files only where a rule is not already met.
   - Acceptance: golden files for both OSes pass; a fixture with a user binding on the same chord keeps it and reports `partial: kept yours`; the install note names the displaced picker binding.

5. **Pending and strip for the JSON-mode rows (KEYS-02 for both new rows)**: A drifted iTerm2 profile or herdr app keys file shows `≈ apply install tuning`, a reconfigure re-applies it, and an uninstall strips exactly what the installer wrote.
   - Current: the mechanism has owned-region rows only.
   - Target: the JSON-mode rows implement check, apply and strip.
   - Acceptance: in a scratch HOME, editing or deleting each file shows `≈ apply install tuning`; reconfigure restores the bytes; uninstall removes the profile (iTerm2) or only the owned keys (herdr app) and leaves user keys in place.

6. **Same-directory and Option rules are declared (KEYS-04 for both rows)**: Each new row declares whether the vendor already opens new tabs, windows and panes in the current directory, and the setting is written only where it does not.
   - Current: n/a.
   - Target: the declaration field from phase 28 filled for both rows.
   - Acceptance: the phase 28 test that fails on an undeclared row passes with both rows present.

## Boundaries

**In scope:**
- The iTerm2 entry, Dynamic Profile generator, default-profile set and restore.
- The Herdr desktop app entry (Linux script, macOS arm64 cask) and its keys files row.
- JSON file mode in the keys mechanism, golden files, container checks for the script install and removal.

**Out of scope:**
- iTerm2 "Show Focus Cursor" and the agent-collaboration extension — future requirements until the owner names the products.
- Replacing or changing the `herdr` multiplexer entry — it stays as it is.
- Herdr app auto-update behavior — app-owned self-update, not managed by the installer.
- Real-Mac verification of the iTerm2 default profile — UAT line deferred to the owner's Mac.

## Constraints

- Zero sudo; the `install.sh` route runs only in a disposable container for tests.
- Whole-file writes (iTerm2 profile) only to a file the installer creates; a file with foreign content is never overwritten.
- Every macOS behavior is a pure generator with a golden file that runs on both OSes.
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] iTerm2 profile golden file passes on both OSes; the Linux row reads unavailable.
- [ ] Install sets and uninstall restores the previous default profile (golden before/after, including "none set").
- [ ] The Herdr desktop app and `herdr` have distinct ids; installing or removing one leaves the other intact (container test).
- [ ] Intel macOS reads unavailable for the Herdr desktop app.
- [ ] Herdr app keys golden files pass on both OSes; a user binding is kept with `partial: kept yours`; the install note names the displaced picker binding.
- [ ] Drift shows `≈ apply install tuning` for both JSON rows, reconfigure restores, uninstall strips only owned content.
- [ ] The undeclared-row test from phase 28 passes with both rows.

## Edge Coverage

**Coverage:** 21/21 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1: the profile holds Option-as-Esc+ for the left and right Option keys only; no neighbouring key mapping changes (golden file) |
| empty | R1 | ✅ covered | Acceptance 1: with no DynamicProfiles directory the installer creates it; an existing empty one gets the one file |
| ordering | R1 | ✅ covered | Acceptance 1: the generated JSON uses sorted keys, so the golden bytes are order-stable |
| concurrency | R1 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one profile or keys file, via the shared atomic write |
| adjacency | R2 | ✅ covered | Acceptance 2: a previous default that is itself a Dynamic Profile is restored by its identity, not by position |
| empty | R2 | ✅ covered | Acceptance 2: the before state 'no default set' restores to 'no default set' (golden) |
| ordering | R2 | ✅ covered | Acceptance 2: restore keys on the recorded identity, independent of profile list order |
| empty | R3 | ✅ covered | Acceptance 3: Intel macOS and an unsupported arch read unavailable instead of an empty install |
| encoding | R3 | ✅ covered | Acceptance 3: entry ids compared as exact lowercase strings; `herdr` and the app id never collide (registry uniqueness test) |
| concurrency | R3 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one profile or keys file, via the shared atomic write |
| empty | R4 | ✅ covered | Acceptance 5: a missing keys file is created with only owned keys; an existing empty file is extended |
| encoding | R4 | ✅ covered | Acceptance 5: golden JSON bytes pin escapes and key spelling; a user binding is matched by its normalized chord |
| concurrency | R4 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one profile or keys file, via the shared atomic write |
| adjacency | R5 | ✅ covered | Acceptance 6: user keys beside the owned keys survive apply and strip |
| empty | R5 | ✅ covered | Acceptance 6: a deleted file shows `≈ apply install tuning` and reconfigure recreates it |
| ordering | R5 | ✅ covered | Acceptance 6: owned keys are located by id, so user key order never matters (shuffled fixture) |
| idempotency | R5 | ✅ covered | Acceptance 6: a second reconfigure leaves the bytes unchanged |
| concurrency | R5 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one profile or keys file, via the shared atomic write |
| adjacency | R6 | ✅ covered | Acceptance 7: the declaration is per row; one row's value never affects the other |
| empty | R6 | ✅ covered | Acceptance 7: an undeclared field fails the phase 28 test |
| ordering | R6 | ✅ covered | Acceptance 7: the declaration is a per-row field independent of row order |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The installer MUST NOT leave the iTerm2 default profile changed after an uninstall | 2 | resolved | test: golden before/after equality |
| The installer MUST NOT remove or alter the `herdr` multiplexer's binaries or `~/.config/herdr` when it installs or removes the Herdr desktop app (and the reverse) | 3 | resolved | test: container byte-comparison |
| The installer MUST NOT overwrite an iTerm2 profile or herdr keys file it did not create | 1 | resolved | test: a fixture with foreign content is refused or merged, never replaced |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.85  | 0.75 | ✓      | Owner decisions fix identity and default profile |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Future items and multiplexer explicitly excluded |
| Constraint Clarity | 0.75  | 0.65 | ✓      | Keyboard Map encoding and keys path settled in discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Golden and container checks; Mac checks deferred |
| **Ambiguity**      | 0.18  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The requirements restate owner-locked decisions and verified facts (initial ambiguity under 0.20), so no item needed a jev answer. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Researcher | None open: identity, default-profile and restore behavior are owner-locked; cask and install.sh facts verified live | none | Keyboard Map encoding, the herdr app keys path and the entry id move to discuss (R1, R3, R4) |

---

*Phase: 31-onboard-iterm2-and-the-herdr-desktop-app*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 31 — implementation decisions (how to build what's specified above)*
