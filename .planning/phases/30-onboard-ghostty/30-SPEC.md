# Phase 30: Onboard Ghostty — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.16 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Ghostty is a catalog entry that a user can install, use and remove on macOS, Linux, Bazzite and Arch, that opens zsh on Linux, and that meets the terminal defaults of the tool-onboarding skill through the shared keys mechanism.

## Background

- `installer/registry.toml` has no Ghostty entry today (`rg ghostty installer/registry.toml` finds nothing); the research is in `.planning/research/STACK.md` §1.4/§2.2 and `FEATURES.md` §3a.
- Live facts (2026-11-19, read-only): the community AppImage repo `pkgforge-dev/ghostty-appimage` has latest release tag `v1.4.0` with assets `Ghostty-1.4.0-x86_64.AppImage` and `Ghostty-1.4.0-aarch64.AppImage`, each carrying a GitHub `sha256:` digest; the official upstream repo `ghostty-org/ghostty` publishes no GitHub release; the Homebrew cask `ghostty` is at 1.4.0 with the app target `/Applications/Ghostty.app` (so a user location needs `--appdir`, SKILL-04).
- Owner decisions 2026-11-16: Linux and Bazzite use the community AppImage with a visible "community build" label; Arch uses pacman; macOS uses the official cask in a user-writable app location with the CLI in `~/.local/bin` where the method allows it.
- The shared keys mechanism (phase 28) and the terminal rules (phase 27) are the base: owned-region mode, `≈ apply install tuning`, strip with the tool, a declared same-directory field per row.
- Research flags for discuss: the AppImage under FUSE 2 on Bazzite (container test), the `{ver}` handling of the `v1.4.0` tag, and which of the XDG or `~/Library/Application Support/com.mitchellh.ghostty/config` file Ghostty reads first on macOS.

## Requirements

1. **Install routes (NTERM-01, install)**: The entry installs from the official cask on macOS into a user-writable app location with its CLI linked into `~/.local/bin` (or says why not, SKILL-04); from a digest-verified community AppImage on Linux and Bazzite, without a reboot, with "community build" in its row and install note; and with pacman on Arch.
   - Current: no entry.
   - Target: one `[[tool]]` with a cask method (macos), a `tarball` method per architecture with `raw = true` (debian, fedora incl. Bazzite) carrying `version` and `sha256` *(amended 2026-11-19, 30 D-02: `github_release` takes no pin fields; `raw` becomes an allowed key on `tarball`)*, and a pacman method, plus the dated `# Verified` comment.
   - Acceptance: registry tests load the entry and its methods; the sha256 of each asset equals the GitHub digest above (`make verify-registry` read-only passes); the row text and install note contain "community build" for the AppImage methods; an install in a disposable Bazzite-like container leaves a runnable `ghostty` path and no reboot request.

2. **zsh on Linux (NTERM-01, shell)**: On Linux, Ghostty launches zsh through the terminal shell sync.
   - Current: the sync covers kitty, WezTerm, Alacritty, Konsole and herdr only.
   - Target: a Ghostty branch of the sync in owned-region mode.
   - Acceptance: a scratch-HOME test shows the shell setting written inside an owned region, a user's own shell setting kept (`partial: kept yours`), and the region removed on uninstall.

3. **Keys through the shared mechanism (NTERM-01, keys)**: Ghostty has a row in the shared keys mechanism that meets the terminal rules: Ctrl+Shift+K clears screen and scrollback on Linux, Cmd+K on macOS, Option+Left/Right word navigation on macOS without `macos-option-as-alt`, and new tabs, windows and splits in the current directory; on macOS the file written is the one Ghostty actually reads, and nothing is written where Ghostty's own default already meets a rule.
   - Current: no row.
   - Target: a row with golden files for both OSes and a declared same-directory field.
   - Acceptance: golden-file tests on both OSes pass; a regression test asserts `macos-option-as-alt` is absent; a test shows the macOS write goes to the config path chosen in discuss and that a rule already met by the vendor default writes no line *(amended 2026-11-19, 30 D-11: the macOS clear writes one keybind sending Ctrl+L, because Ghostty's default Cmd+K action does not send it; word navigation and same-directory write nothing)*.

4. **Drift and reconfigure (NTERM-01, tuning)**: A drifted or missing Ghostty keys region shows `≈ apply install tuning` and a reconfigure re-applies it.
   - Current: n/a.
   - Target: the phase 28 behavior holds for the Ghostty row.
   - Acceptance: in a scratch HOME, deleting the region shows `≈ apply install tuning`; reconfigure restores the bytes; a second reconfigure changes nothing.

5. **Clean uninstall (NTERM-01, removal)**: In a container, uninstalling Ghostty removes the AppImage, its keys and shell regions and every receipt-recorded path, leaving only documented config.
   - Current: n/a.
   - Target: removal plan covers the AppImage path, desktop entry if the install wrote one, the owned regions and the receipt.
   - Acceptance: a container run lists the files after install and after uninstall; the difference is exactly the receipt paths plus the two regions; `~/.config/ghostty` content outside the owned regions remains.

## Boundaries

**In scope:**
- The Ghostty registry entry (cask, AppImage per architecture, pacman), its postinstall row, shell-sync branch and keys row, removal, tests and container checks.
- The macOS app location and CLI link per SKILL-04.
- *Amended 2026-11-19 (30 D-02, D-05, D-07, D-08, D-13):* `raw` as an allowed key on `tarball`, an optional per-method install `note`, the AppImage's menu entry and icon (receipt leaves, removed on uninstall), a top-of-file placement option for the owned-region helper, and `platform_os` in the row's `config_path`.

**Out of scope:**
- iTerm2 and the Herdr desktop app — phase 31.
- A Flatpak, snap or source-build route for Ghostty — no new method kinds (REQUIREMENTS out of scope).
- Ghostty theme or font customization beyond the four rules — extras are asked, not applied.
- Real-Mac verification — UAT line deferred to the owner's Mac.

## Constraints

- The AppImage is verified by its sha256 before it is placed; version and sha256 are bumped together.
- Container tests only for installs and removals; scratch HOME for config tests; never the real host.
- Zero sudo; no reboot on Bazzite.
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] The entry loads, with cask, per-architecture AppImage and pacman methods and a dated `# Verified` comment.
- [ ] `make verify-registry` (read-only) passes for the Ghostty asset digests.
- [ ] "community build" appears in the row text and install note of the AppImage methods.
- [ ] The Ghostty shell sync writes an owned region, keeps a user's own setting, and strips on uninstall.
- [ ] Golden files on both OSes pass; `macos-option-as-alt` is absent.
- [ ] A drifted keys region shows `≈ apply install tuning` and a reconfigure restores it.
- [ ] A container install leaves a runnable binary with no reboot; a container uninstall leaves only documented config.

## Edge Coverage

**Coverage:** 12/13 applicable edges resolved · 1 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 1: version and sha256 are bumped together; a tag with a leading v and a bare version resolve to one asset name (registry test) |
| empty | R1 | ✅ covered | Acceptance 1: an entry with no method for a host OS and arch reads unavailable, never an empty install |
| encoding | R1 | ✅ covered | Acceptance 1: the pinned sha256 is compared as lowercase hex; the GitHub digest prefix `sha256:` is stripped by verify-registry (read-only run) |
| ordering | R1 | ✅ covered | Acceptance 1: per-architecture methods are chosen by os and arch params, never by method order |
| concurrency | R1 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one region and one binary, via the shared atomic write and the run lock |
| unclassified | R2 | ⚠ UNRESOLVED | ⚠ Edge unresolved — planner must treat as assumption |
| concurrency | R3 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one region and one binary, via the shared atomic write and the run lock |
| idempotency | R4 | ✅ covered | Acceptance 6: a second reconfigure changes nothing (apply twice equals apply once) |
| concurrency | R4 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one region and one binary, via the shared atomic write and the run lock |
| adjacency | R5 | ✅ covered | Acceptance 7: config next to the owned regions is kept; only the two regions and receipt paths are removed |
| empty | R5 | ✅ covered | Acceptance 7: uninstalling a Ghostty with no config file removes the binary and the receipt without error |
| ordering | R5 | ✅ covered | Acceptance 7: the removal result is a set difference of file lists, independent of removal order |
| concurrency | R5 | 🧪 backstop | held-out test: interleaved applies or installs in a scratch HOME or container leave one region and one binary, via the shared atomic write and the run lock |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The installer MUST NOT place an AppImage whose sha256 differs from the pinned digest | 1 | resolved | test: a digest-mismatch fixture refuses the install |
| The installer MUST NOT write the global `macos-option-as-alt` setting | 3 | resolved | test: regression asserts it is absent from both golden files |
| The installer MUST NOT overwrite a user-defined Ghostty keybind or shell setting | 2 | resolved | test: fixtures with user lines keep them and report `partial: kept yours` |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.85  | 0.75 | ✓      | Owner decisions and live asset facts |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | No new method kinds; iTerm2 and Herdr app in 31 |
| Constraint Clarity | 0.80  | 0.65 | ✓      | FUSE 2 and config-path flags settled in discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Golden, registry and container checks |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The requirements restate owner-locked decisions and verified facts (initial ambiguity under 0.20), so no item needed a jev answer. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Researcher | None open: routes and labels are owner-locked; asset digests verified live | none | FUSE 2, `{ver}` and macOS config precedence move to discuss as live checks (R1, R3) |

---

*Phase: 30-onboard-ghostty*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 30 — implementation decisions (how to build what's specified above)*
