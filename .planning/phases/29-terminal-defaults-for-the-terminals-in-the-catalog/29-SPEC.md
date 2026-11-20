# Phase 29: Terminal defaults for the terminals in the catalog — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

kitty, WezTerm, Alacritty, Konsole and herdr each meet the terminal defaults of the tool-onboarding skill (phase 27) on every OS they install on, through the shared keys mechanism (phase 28), without overriding a binding the user set.

## Background

- Rules come from phase 27 (SKILL-01): zsh launches on Linux; Option+Left/Right word navigation on macOS by two chords only, never the global Option-as-Alt switch; Cmd+K / Ctrl+Shift+K clear screen and scrollback by sending Ctrl+L (the zsh widget is phase 28); a new tab, window or pane opens in the current directory. Conflict rule (SKILL-03): a user's binding is kept and reported `partial: kept yours`; a displaced vendor default needs an install note naming it.
- Today only Alacritty has key tuning (`installer/terminal_shell.py:477-482`: Linux Alt+Left/Right and Ctrl+Shift+K = `ClearHistory`, scrollback only). kitty, WezTerm and herdr have `post_install` empty in `installer/registry.toml`; their only tuning is the zsh sync.
- kitty's macOS `script` method installs `kitty.app` into `/Applications` (`installer/registry.toml` kitty block, `bin_dir = "/Applications/kitty.app/Contents/MacOS"`, comment: installer.sh writes `/Applications/kitty.app`); there is no `paths` because the registry rejects an absolute system path.
- WezTerm's shell sync owns a Lua region between `-- >>> tools-installer terminal-shell wezterm >>>` markers (`installer/terminal_shell.py:180-208`); its already-owned test is a substring check (`"tools-installer terminal-shell wezterm" in existing`), which a second owned region with a similar marker would satisfy by accident.
- Konsole is handled by `_sync_konsole` (zsh sync only) and is not a registry entry; herdr is a registry entry (multiplexer, `terminal` category) whose shell sync is `HERDR`/`_herdr_reload`.
- Owner decisions 2026-11-16: Alacritty keeps its Linux Alt+Left/Right rows; no Alt word navigation on other Linux terminals; Konsole is "verify, do not rewrite".
- Research flags to settle by live check in discuss: whether kitty's `map opt+left` fires with `macos_option_as_alt no`; Konsole's stock clear key on the current version in a container; herdr's key handling.

## Requirements

1. **kitty meets the rules on both OSes (TERM-01)**: kitty's generated keys bind Option+Left/Right to word navigation on macOS without the global `macos_option_as_alt` switch, send Ctrl+L on Cmd+K (macOS) and Ctrl+Shift+K (Linux, displacing kitty's default `scroll_line_up`, named in the install note), and open new tabs and windows in the current directory; kitty's macOS install writes nothing into `/Applications`.
   - Current: no kitty key tuning; the macOS script method installs into `/Applications/kitty.app`.
   - Target: a kitty row in the keys mechanism with golden files for both OSes; the macOS install target is a user location (`~/Applications`) with the CLI linked into `~/.local/bin` per SKILL-04, or the entry says why not.
   - Acceptance: golden-file test on both OSes passes; a regression test asserts `macos_option_as_alt` is absent from the generated config; the install note names `scroll_line_up`; a test or fixture shows no `/Applications` path in kitty's macOS method.

2. **WezTerm meets the rules through its Lua region (TERM-02)**: WezTerm's owned Lua region meets the rules on both OSes and extends the user's `config.keys` instead of replacing it; a config holding both the shell region and the keys region is read correctly because the owned-region check matches exact marker lines.
   - Current: the already-owned check is a substring test; the region sets shell variables only.
   - Target: exact-marker matching and a keys region that appends to an existing `config.keys`.
   - Acceptance: a fixture with user keys keeps all of them after apply; a fixture holding both regions applies, checks and strips each independently; a fixture with a user-written comment that contains the marker words is not taken for an owned region.

3. **Alacritty's clear is screen and scrollback (TERM-03)**: Alacritty's Ctrl+Shift+K (Linux; Cmd+K on macOS where installed) clears the screen and the scrollback through the phase 28 mechanism *(amended 2026-11-19, 29 D-08: Alacritty has no macOS method, so the macOS chord is n/a)*, and its Linux Alt+Left/Right rows are unchanged.
   - Current: Ctrl+Shift+K = `ClearHistory` (scrollback only); no Cmd+K row.
   - Target: the clear chord resolves to the shared Ctrl+L behavior; the Alt rows stay.
   - Acceptance: the Alacritty golden file differs from phase 28's only in the clear row(s); the two Linux Alt rows are byte-identical to phase 28's.

4. **Konsole is verified, not rewritten (TERM-04)**: On a stock Konsole profile the installer writes nothing and reports the stock Ctrl+Shift+K clear; it never writes a binding: a user-removed stock key is kept and reported `konsole: partial: you removed Ctrl+Shift+K; kept yours`; its zsh sync is unchanged *(amended 2026-11-19, 29 D-09, needs confirmation: the conditional write is dropped; SKILL-03 and the owner decision "verify and leave alone")*.
   - Current: Konsole has only the zsh sync.
   - Target: a read-only check of the stock key; it never writes *(amended 2026-11-20, 29 D-09, needs confirmation: the conditional write was dropped; the report is the whole behavior)*.
   - Acceptance: a fixture with the stock key leaves the file byte-identical and the report says stock; a fixture with the key removed is left byte-identical and the report says `konsole: partial: you removed Ctrl+Shift+K; kept yours`; existing Konsole sync tests pass with no assertion edits; the stock key is confirmed on the current Konsole version in a disposable container.

5. **herdr passes the keys through (TERM-05)**: Inside a herdr pane, Option/Alt+Left/Right and the clear chord reach the shell as the expected bytes; a herdr pass-through setting is written only if herdr intercepts them *(amended 2026-11-19, 29 D-10: verified live that herdr 0.9.5 does not intercept them, so no setting and no keys row)*.
   - Current: unknown; herdr's own key handling is not verified.
   - Target: an observable byte-level test inside a herdr pane, and a setting only on interception.
   - Acceptance: a byte-level test (a pty child in a herdr pane that records its input) shows the expected bytes for the three chords, or the test shows interception and the pass-through setting is written, applied and stripped through the mechanism.

## Boundaries

**In scope:**
- kitty and WezTerm rows in the shared mechanism (herdr has none, 29 D-10); Alacritty's clear change; the Konsole verify-and-report check *(amended 2026-11-20, 29 D-09, needs confirmation: report-only, no conditional write)*.
- kitty's macOS install location and CLI link.
- Golden-file tests on both OSes and the container checks named above.
- *Amended 2026-11-19 (29 D-10, D-11):* a herdr byte-level container target in `scripts/container-e2e-verify.sh`, and the `placement` and `validate` fields of the phase 28 row type.

**Out of scope:**
- Alt word navigation on Linux terminals other than Alacritty — owner decision 2026-11-16 (Ctrl+Left/Right is the Linux convention).
- Ghostty, iTerm2 and the Herdr desktop app — phases 30-31.
- Rewriting Konsole's profile or writing any Konsole binding *(amended 2026-11-20, 29 D-09, needs confirmation)* — owner: verify, do not rewrite.
- Real-Mac checks — UAT lines deferred to the owner's Mac (SKILL-05).
- The global Option-as-Alt switch on any terminal.

## Constraints

- Every macOS behavior is a pure config generator with a golden file that runs on both OSes (SKILL-05).
- A user's own binding is never overridden; the result reads `partial: kept yours`.
- Container checks run only in disposable containers (`scripts/detect-container-runtime.sh`), removed afterwards; no run touches the host's real terminal configs.
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] kitty golden files for macOS and Linux pass; the global switch is absent (regression test); the install note names `scroll_line_up`.
- [ ] kitty's macOS method has no `/Applications` path, or its `# Verified` comment says why.
- [ ] WezTerm fixtures: user `config.keys` preserved; both regions coexist; a marker-lookalike comment is not an owned region.
- [ ] Alacritty's golden file differs from phase 28's only in the clear row(s).
- [ ] Konsole: stock profile unchanged and reported; removed key left byte-identical and reported (amended 2026-11-20, 29 D-09, needs confirmation: report-only); sync tests unedited; stock key confirmed in a container.
- [ ] A byte-level herdr-pane test shows the three chords arriving, or the pass-through setting is written and stripped.
- [ ] No terminal in this phase gets Alt+Left/Right word navigation on Linux except Alacritty's existing rows.

## Edge Coverage

**Coverage:** 11/12 applicable edges resolved · 1 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| empty | R1 | ✅ covered | Acceptance 1: a missing or empty kitty.conf gets the owned region; the golden files start from empty and from user content |
| encoding | R1 | ✅ covered | Acceptance 1: golden bytes pin the exact map lines and the Ctrl+L escape (ctrl+l / \x0c) for both OSes |
| concurrency | R1 | 🧪 backstop | held-out test: two interleaved applies in a scratch HOME leave one region, via the shared atomic write |
| adjacency | R2 | ✅ covered | Acceptance 3: the shell region and the keys region sit side by side and are read, applied and stripped independently |
| empty | R2 | ✅ covered | Acceptance 3: a config without config.keys gets one created; an existing empty table is extended, never replaced |
| encoding | R2 | ✅ covered | Acceptance 3: exact marker-line matching (full-line equality), so a Unicode or whitespace lookalike is not an owned marker |
| ordering | R2 | ✅ covered | Acceptance 3: user keys keep their order and the owned keys append after them (fixture asserts the order) |
| idempotency | R2 | ✅ covered | Acceptance 3: apply twice equals apply once; the region is replaced, never duplicated |
| concurrency | R2 | 🧪 backstop | held-out test: two interleaved applies in a scratch HOME leave one region, via the shared atomic write |
| concurrency | R3 | 🧪 backstop | held-out test: two interleaved applies in a scratch HOME leave one region, via the shared atomic write |
| concurrency | R4 | 🧪 backstop | held-out test: two interleaved applies in a scratch HOME leave one region, via the shared atomic write |
| unclassified | R5 | ⚠ UNRESOLVED | ⚠ Edge unresolved — planner must treat as assumption |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The installer MUST NOT enable the global Option-as-Alt switch on any terminal | 1 | resolved | test: regression asserts the key is absent from kitty's config; judgment for the other rows |
| The installer MUST NOT replace or reorder a user's existing key bindings in any terminal's config | 2 | resolved | test: fixtures with user bindings keep every one |
| The installer MUST NOT write or edit the host's real terminal configs while verifying Konsole or herdr | 4 | resolved | judgment (container-only live checks, scratch HOME in tests) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.85  | 0.75 | ✓      | Per-terminal criteria from the roadmap |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Owner decisions fix the Linux Alt scope |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Research flags (kitty opt+left, Konsole key, herdr) resolved by live check in discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Golden files and byte-level tests |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The requirements restate the roadmap criteria and owner decisions of 2026-11-16 and were already specific (initial ambiguity under 0.20), so no item needed a jev answer. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Researcher | None open: the requirements restate owner-locked decisions | none | The three research flags move to discuss as live checks (R1, R4, R5) |

---

*Phase: 29-terminal-defaults-for-the-terminals-in-the-catalog*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 29 — implementation decisions (how to build what's specified above)*
