# Phase 27: Tool-onboarding skill: terminal defaults as rules — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 7 locked

## Goal

`.claude/skills/tool-onboarding/SKILL.md` changes from "ask the developer which terminal customizations to build" to a set of rules applied without asking, backed by one closed per-terminal table that a test keeps in step with every terminal and editor entry of `installer/registry.toml`.

## Background

- `.claude/skills/tool-onboarding/SKILL.md` (268 lines) step 7 (lines ~178-198) says "ask the user, do not assume" and lists terminal word navigation and clear-scrollback as questions; `Common Mistakes` (lines ~256-257) warns against shipping customizations nobody asked for.
- The registry has four `terminal` entries (kitty, wezterm, alacritty, herdr) and four `editor` entries (vscode, jetbrains-toolbox, sublime, neovim). Only Alacritty has `post_install = ["apply_terminal_tuning"]`; the zsh sync and the Alacritty keys live in `installer/terminal_shell.py` (Linux only).
- Owner decisions of 2026-11-16 (`REQUIREMENTS.md`): terminal defaults are rules; clear means screen plus scrollback with Modifier+K sending Ctrl+L; Option+Left/Right is bound as two chords, never the global Option-as-Alt switch; the skill goes first and every later onboarding runs through it.
- No test compares the skill to the registry today. The 24.3 skill (`catalog-audit`) is the pattern for a skill checked by tests and by recorded skill-judge verdicts (`tests/test_catalog_audit_skill.py`).
- Later phases consume this one: 28 builds the shared keys mechanism, 29-31 onboard terminals, 32 onboards five tools, all through the skill.

## Requirements

1. **Terminal defaults as rules (SKILL-01)**: The skill states four rules as applied without asking: (a) zsh is the launched shell on Linux, Bazzite included; (b) Option/Alt+Left/Right moves by word on macOS by binding only those two chords, never the global Option-as-Alt switch; (c) Cmd+K on macOS and Ctrl+Shift+K on Linux clear the screen and the scrollback, the chord sends Ctrl+L, and the managed zsh configuration makes Ctrl+L clear both; (d) a new tab, window or pane opens in the current directory. Only extras beyond the four remain questions.
   - Current: step 7 lists these as questions to ask the developer.
   - Target: a "Terminal and IDE defaults" section holds the four rules, each with its OS scope, and states that none is a question or a Policies row.
   - Acceptance: `rg` finds all four rules, the Spanish-layout reason for rule (b), and no sentence in the skill that tells the author to ask whether to enable any of the four.

2. **Closed per-terminal table (SKILL-02)**: The skill carries one table with a row per registry entry whose category is `terminal` or `editor` (kitty, wezterm, alacritty, herdr, vscode, jetbrains-toolbox, sublime, neovim). Each row gives the config file, how each of the four rules is met or already met by the vendor, and the reload behavior; a row for an entry that takes no key rules (herdr, the editors) says so and why. A test fails when such a registry entry has no row.
   - Current: no table and no test; Konsole is detected by code but is not a catalog entry.
   - Target: the table lives in the skill; a test parses it and compares its ids with the registry's `terminal` and `editor` entries.
   - Acceptance: the test passes on the repo; the test, run against a fixture registry with one extra terminal entry and no row, fails and names that id; a fixture row with no registry entry also fails.

3. **Conflict rule (SKILL-03)**: The skill states that a binding the user already defines is never overridden and the row result is reported as `partial: kept yours`, and that a vendor default which conflicts with a rule is overridden only with an install note that names the displaced default.
   - Current: nothing states it; `terminal_shell.py` keeps user content only for the shell region.
   - Target: a "Conflicts" section with both clauses and one worked example for each.
   - Acceptance: `rg` finds `partial: kept yours` and an example that names a displaced vendor default.

4. **macOS app rule (SKILL-04)**: The skill's research step records, per macOS app: how it installs, how it uninstalls, how it is configured, and whether its method can place the bundle in `~/Applications` instead of `/Applications` (a vendor installer that takes a destination, a `.zip` or `.dmg` the installer extracts, a cask through `--appdir`). Where the method allows it the bundle goes to `~/Applications`, and every app that ships a CLI gets that CLI linked into `~/.local/bin`. Where no method allows a user location, the entry's `# Verified` comment says why.
   - Current: step 3-4 never mention the app location or CLI linking.
   - Target: a "macOS apps" subsection under the research step with those four recorded facts and the two placement rules.
   - Acceptance: `rg` finds `~/Applications`, `~/.local/bin` and the "says why" clause in the research step; the `# Verified` template names the three facts.

5. **macOS testing rule (SKILL-05)**: The skill states that each macOS behavior is a pure config generator with a golden-file test that runs on both OSes, that macOS CI covers the file paths, and that the real-Mac check is a UAT line marked deferred to the owner's Mac.
   - Current: no macOS testing guidance in the skill.
   - Target: a "Testing macOS behavior" section with the three clauses.
   - Acceptance: `rg` finds the three clauses; the section names the CI job that runs on macOS (verified against `.github/workflows/ci.yml`).

6. **No contradicting text (derived from the roadmap note)**: After the rewrite the old "ask the user, do not enable silently" bullets for terminal emulators are gone, the other customization prompts (multiplexer companions, shell themes, editor plugins, LLM-tool hosts) stay as author questions, and the `Common Mistakes` bullet about unrequested customizations is narrowed to the non-terminal items.
   - Current: step 7 and `Common Mistakes` apply "ask first" to every customization, terminals included.
   - Target: step 7 and the mistakes list agree with requirements 1-5.
   - Acceptance: a test or `rg` check shows no remaining sentence that asks the author to offer word navigation, clear-scrollback or the zsh shell sync as a question.

7. **skill-judge before and after (SKILL-06)**: skill-judge scores the skill before and after the rewrite, both verdicts are recorded in the phase directory, and the after score is not lower.
   - Current: no verdict exists for `tool-onboarding` in this milestone.
   - Target: `27-SKILLJUDGE-before.md` and `27-SKILLJUDGE-after.md` in the phase directory.
   - Acceptance: both files exist with a percent and grade line each; a test reads them (asserting the file count, per the 24.3 lesson) and fails when after < before.

## Boundaries

**In scope:**
- The rewrite of `.claude/skills/tool-onboarding/SKILL.md` (rules, table, conflict rule, macOS app and testing rules, narrowed prompts).
- The closed-table test and the skill-judge verdict test, plus their fixtures.
- Two skill-judge verdict files in the phase directory.

**Out of scope:**
- Any change to `installer/*.py` or `registry.toml` entries — the skill states rules; phases 28-32 implement them.
- Per-IDE keybindings on Linux (SKILL-07, future) — the editor rows record config file and reload only.
- Reviewing existing macOS app entries against the new app rule (MACAPP-01, future).
- Real-Mac verification — a UAT line deferred to the owner's Mac (SKILL-05).
- Rows for terminals that are not yet catalog entries (Ghostty, iTerm2, Herdr desktop app) — their phases add the row with the entry, and the test enforces it.

## Constraints

- English only in the skill and the repo; the table is parseable text (no free-form prose cells that break the parser).
- Agents never mutate the host: the skill-judge runs and any live checks use a scratch directory.
- The skill keeps its process-aid shape: it names the file that implements each decision and does not promise a mechanism the code lacks (phase 28 builds the keys mechanism, so rows reference it as planned, not as present).
- `make validate && make test` pass on the commit.

## Acceptance Criteria

- [ ] `SKILL.md` has the four terminal rules with OS scope and no question about any of them.
- [ ] The table has exactly one row per `terminal` or `editor` registry id (8 today), and `make test` fails when a row is missing or extra (proved by two fixtures).
- [ ] `partial: kept yours` and the displaced-default install note rule are stated with examples.
- [ ] The research step records install, uninstall, configuration and `~/Applications` feasibility per macOS app, with the CLI-link and say-why clauses.
- [ ] The macOS testing section states the golden-file, CI and deferred-UAT clauses.
- [ ] No remaining text asks the author to offer the four defaults as a question; non-terminal prompts remain.
- [ ] Two skill-judge verdict files exist in the phase directory and the after percent is not lower than the before percent.

## Edge Coverage

**Coverage:** 33/33 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | 🧪 backstop | held-out test: the skill's rules are separate sections, so two rules never share a sentence; an rg check per rule |
| empty | R1 | ✅ covered | Acceptance criteria are rg or test checks that fail on a missing section (an empty section never passes) |
| ordering | R1 | ✅ covered | the rules are an unordered set; the checks match each rule independently of position |
| adjacency | R2 | ✅ covered | Acceptance 2 fixtures: a duplicate id and an id differing only by case each fail the table test |
| empty | R2 | ✅ covered | Acceptance 2: an empty or header-only table fails the test (zero rows is never a pass) |
| encoding | R2 | 🧪 backstop | held-out test: ids compare as exact registry id strings (ASCII lowercase with hyphen); a non-ASCII lookalike row fails |
| ordering | R2 | ✅ covered | the test compares id sets, so row order never matters; asserted by a shuffled-rows fixture |
| concurrency | R2 | 🧪 backstop | held-out test: the test is read-only on the registry and the skill file, so parallel xdist workers cannot interfere |
| adjacency | R3 | 🧪 backstop | held-out test: the skill's rules are separate sections, so two rules never share a sentence; an rg check per rule |
| empty | R3 | ✅ covered | Acceptance criteria are rg or test checks that fail on a missing section (an empty section never passes) |
| encoding | R3 | 🧪 backstop | held-out test: rule text uses ASCII key names (Option, Cmd, Ctrl, Shift) so an rg check does not depend on Unicode form |
| ordering | R3 | ✅ covered | the rules are an unordered set; the checks match each rule independently of position |
| adjacency | R4 | 🧪 backstop | held-out test: the skill's rules are separate sections, so two rules never share a sentence; an rg check per rule |
| empty | R4 | ✅ covered | Acceptance criteria are rg or test checks that fail on a missing section (an empty section never passes) |
| encoding | R4 | 🧪 backstop | held-out test: rule text uses ASCII key names (Option, Cmd, Ctrl, Shift) so an rg check does not depend on Unicode form |
| ordering | R4 | ✅ covered | the rules are an unordered set; the checks match each rule independently of position |
| adjacency | R5 | 🧪 backstop | held-out test: the skill's rules are separate sections, so two rules never share a sentence; an rg check per rule |
| empty | R5 | ✅ covered | Acceptance criteria are rg or test checks that fail on a missing section (an empty section never passes) |
| encoding | R5 | 🧪 backstop | held-out test: rule text uses ASCII key names (Option, Cmd, Ctrl, Shift) so an rg check does not depend on Unicode form |
| ordering | R5 | ✅ covered | the rules are an unordered set; the checks match each rule independently of position |
| concurrency | R5 | 🧪 backstop | held-out test: read-only check of the section text |
| adjacency | R6 | 🧪 backstop | held-out test: the skill's rules are separate sections, so two rules never share a sentence; an rg check per rule |
| empty | R6 | ✅ covered | Acceptance criteria are rg or test checks that fail on a missing section (an empty section never passes) |
| encoding | R6 | 🧪 backstop | held-out test: rule text uses ASCII key names (Option, Cmd, Ctrl, Shift) so an rg check does not depend on Unicode form |
| ordering | R6 | ✅ covered | the rules are an unordered set; the checks match each rule independently of position |
| idempotency | R6 | 🧪 backstop | held-out test: the no-contradiction check is a pure read of the skill, so a second run gives the same result |
| concurrency | R6 | 🧪 backstop | held-out test: read-only |
| boundary | R7 | ✅ covered | Acceptance 7: after == before passes; after < before fails (fixture pair at equal and one-point-lower) |
| adjacency | R7 | 🧪 backstop | held-out test: a verdict file with an unparseable percent fails instead of comparing as zero |
| empty | R7 | ✅ covered | Acceptance 7: the verdict test asserts exactly 2 files (24.3 lesson); a missing file fails |
| ordering | R7 | 🧪 backstop | held-out test: before and after are selected by filename suffix, never by sort order |
| precision | R7 | ✅ covered | Acceptance 7: percents are compared as numbers with the file's own precision, no rounding step |
| concurrency | R7 | 🧪 backstop | held-out test: read-only file reads under xdist |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The skill MUST NOT tell the author to enable the global Option-as-Alt switch (it breaks `@`, `\|`, `\` and `#` on the owner's Spanish layout) | 1 | resolved | judgment (reviewed in the skill-judge pass) plus `rg` check for the phrase in a recommending sentence |
| The skill MUST NOT promise a mechanism the code lacks: rows reference the shared keys mechanism only as planned for phase 28 | 2 | resolved | judgment |
| The skill MUST NOT make any of the four defaults a Policies row or an install-time question (TUNE doctrine) | 1 | resolved | judgment |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.85  | 0.75 | ✓      | Roadmap criteria and owner decisions are specific |
| Boundary Clarity   | 0.80  | 0.70 | ✓      | Table scope settled: terminal and editor categories |
| Constraint Clarity | 0.80  | 0.65 | ✓      | Table format left to discuss (parser shape) |
| Acceptance Criteria| 0.85  | 0.70 | ✓      | Each criterion is a `rg`, test or file check |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The open items went through jev: one advisory answer per item, and `needs_fallback` items are decided by own reasoning. Summaries only, advisory. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Boundary Keeper | Which registry categories does the closed table and its test cover? | low 0.50 (none_of_these); second rung low 0.53 (terminal_and_editor) | **Own reasoning:** `terminal` plus `editor` (SKILL-02 says "terminal or IDE"; the editor category is the catalog's IDE set; AI-branded editors stay out, SKILL-07 is future) (R2, ledger) |
| 1 | Boundary Keeper | Does herdr (multiplexer, `terminal` category) get a row? | choice yes 0.89 | A row stating it takes no key rules of its own and inherits the host terminal's (R2); phase 29 TERM-05 tests the byte pass-through |
| 1 | Simplifier | What happens to the non-terminal customization prompts? | low 0.36 (none_of_these); second rung choice keep_asking 0.91 | They stay author questions; the mistakes bullet narrows to non-terminal items (R6) |

---

*Phase: 27-tool-onboarding-skill-terminal-defaults-as-rules*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 27 — implementation decisions (how to build what's specified above)*
