# Phase 27: Tool-onboarding skill: terminal defaults as rules - Context

**Gathered:** 2026-11-19 (assumptions mode, after 27-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite `.claude/skills/tool-onboarding/SKILL.md` so terminal and IDE defaults are rules applied without asking, backed by one closed per-terminal table that a test keeps in step with the registry; add the conflict rule, the macOS app rule and the macOS testing rule; score the skill with skill-judge before and after. No `installer/*.py` or `registry.toml` change (phases 28-32 implement the rules).
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**7 requirements are locked.** See `27-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `27-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the rewrite of `.claude/skills/tool-onboarding/SKILL.md`; the closed-table test and the skill-judge verdict test with their fixtures; two skill-judge verdict files in the phase directory. *Amended 2026-11-19 (27 D-09, D-07):* also the one line in `.claude/skills/catalog-audit/SKILL.md` that quotes step 7's heading, and the `devtools/docs_only.py` `TEST_READ` and `tests/test_docs_only.py` `LEDGER` entries for the verdict files.
**Out of scope (from SPEC.md):** any change to `installer/*.py` or `registry.toml`; per-IDE keybindings (SKILL-07); reviewing existing macOS apps (MACAPP-01); real-Mac verification; rows for terminals not yet in the catalog.

</spec_lock>

<decisions>
## Implementation Decisions

### Skill structure
- **D-01: The closed table is a Markdown pipe table inside `SKILL.md`**, under step 7 as a `####` subsection. Its first cell is the backticked registry id. One file serves phases 28-32 and the audit skill's step 7 load.
  - Evidence: `.claude/skills/tool-onboarding/SKILL.md` already uses pipe tables (lines 54-59, 105-110); `tests/test_catalog_audit_skill.py:93-95` has a pipe-row parser to follow. **Own reasoning** (jev inline low 0.76; first rung low 0.43): the parser and load-path evidence decides. Ledger.
- **D-09: Step 7 keeps its number and gets a new heading** (terminal defaults are rules, extras are asked). The four rules, the table, `#### Conflicts` and `#### Testing macOS behavior` are `####` subsections of step 7, so `_skill_section` (`tests/test_docs.py:318-324`) still returns them as step 7. The multiplexer, shell/prompt/editor and LLM-host prompts stay as author questions. `.claude/skills/catalog-audit/SKILL.md:80` quotes the old heading and `tests/test_catalog_audit_skill.py:104-109` requires every quoted heading to exist in tool-onboarding, so that line changes in the same commit. The phrases pinned by `tests/test_docs.py` (`_INSTALL_TUNING_RULE_PHRASES`, the two Policies sentences, ASCII on every Policies line) stay word for word.
  - **Own reasoning** (jev rename_step_update_sibling low 0.74; first rung low 0.55): the live fact that the sibling skill and a test quote the heading decides. Ledger.
- **D-10: `#### macOS apps` goes under step 4** (install method), because the audit skill loads steps 3/4/4b for the install row and never step 1. It records install, uninstall, configuration and `~/Applications` feasibility, and the CLI-link and say-why rules. It names only real mechanisms: `cask` with `--appdir` (`installer/executors.py:699-704`, `applications_dir()`), the `app` kind with `cli`/`cli_name` (`installer/apps.py`, bundle to `~/Applications`, CLI symlink to `~/.local/bin`), and a vendor installer that takes a destination. Two **platform gaps** are recorded, not promised: a `.dmg` (the `app` kind extracts `.zip` only, `ditto -x -k`; no dmg kind exists and research added none) and a cask's CLI link (brew links it, not `~/.local/bin`; `cask` params are `cask, app, min_os_version, smoke_argv`). Step 9 gets a literal `# Verified` example with the bundle location, the CLI link and the reason when no user location is possible; kitty's macOS `script` method (writes `/Applications/kitty.app`) is the worked example of a method that does not meet the rule.
  - jev install_method_subsection: first rung choice none_of_these 0.75 contradicted the evidence; second opinion low 0.60 on the evidence's side. **jev overridden / Own reasoning:** no confident second opinion. Ledger.
- **D-11: Other text changed for R6.** Frontmatter description (line 3, "user-chosen customizations (terminal keybindings...)"), Overview line 15 (an exemption for the table, since "tool names are examples" would otherwise apply to it), lines 209-210 ("The onboarding author still asks the developer which customizations to build"), line 242 ("which customizations were offered"), and the `Common Mistakes` bullet at lines 256-257, narrowed to non-terminal items. Two bullets are added: asking about one of the four defaults, and enabling the global Option-as-Alt switch (with the Spanish `@ | # \` reason).
- **D-12: The Conflicts section states `partial: kept yours` as the meaning**, maps it to today's `<terminal>: partial: you already ...` lines that `version_status` parses by their `partial:` prefix (`installer/terminal_shell.py:598`, `:768`; `installer/version_status.py:1598`), and leaves the exact wording to phase 28. The displaced-default example is kitty Linux `ctrl+shift+k` = `scroll_line_up`, cited as planned for phase 29. jev label_as_meaning 0.98.
- **D-13: Konsole gets no table row**; one sentence under the table records the owner decision "verify and leave alone", the existing `_sync_konsole` and TERM-04 (phase 29). jev none_of_these 0.97 (first rung, contradicts the evidence that a row fails the closed table); second opinion one_line_note low 0.38. **jev overridden / Own reasoning**, ledger.
- **D-15: SKILL-05 names the CI job** `validate-and-test` (displayed "validate & test on macos-latest", matrix `[ubuntu-latest, macos-latest]`, `.github/workflows/ci.yml:15-50`), whose `Test` step runs `make test` on macOS, and notes that a docs-only change skips those steps (`Classify the change` step).
- **D-16: Rule (c) is stated as planned for phase 28** (KEYS-03): nothing in `installer/` makes zsh's Ctrl+L clear screen and scrollback today (no `bindkey` or `clear-screen` match). Rows reference the shared mechanism as planned, never as present.

### Table content
- **D-02: Each rule cell starts with a word from a closed list**: `vendor`, `written`, `planned (phase N)`, `n/a`, `unverified`. The test checks the first word. Columns: config file, (a) shell, (b) word navigation, (c) clear, (d) same directory, reload. jev closed_list_checked 0.80.
- **D-14: Row facts** (V = verified live in a scratch HOME on this host, C = read in code). kitty (installed 0.49.2): config `~/.config/kitty/kitty.conf` (C); (a) written on Linux by the zsh sync; (b) `macos_option_as_alt` = 0 (V), planned TERM-01; (c) Linux ctrl+shift+k = `scroll_line_up` (V), displaced with a note; (d) new_tab, new_window and new_os_window carry no cwd (V), planned. WezTerm: config XDG `wezterm/wezterm.lua` else `~/.wezterm.lua` (C); (a) written as `default_prog`; (c) **`SUPER k` and `CTRL|SHIFT k` are `ClearScrollback(ScrollbackOnly)` (V, wezterm 20240203-110809): scrollback only, does not send Ctrl+L, so rule (c) is not met and the research claim "needs nothing" is out of date** (coupling to phase 29); (d) splits use `CurrentPaneDomain` (V), cwd inheritance `unverified`. Alacritty: Linux-only entry (no macOS method); (a) shell region; (b) macOS n/a, Linux Alt rows kept by owner decision; (c) `ClearHistory` today, moving in TERM-03. herdr: `~/.config/herdr/config.toml` (C); no key rules of its own (TERM-05 byte pass-through), (a) `terminal.default_shell` written only when absent; reload `herdr server reload-config`. vscode: `settings.json`; (a) already met through `apply_agent_tuning` (`terminal.integrated.defaultProfile.{linux,osx}` = zsh, `installer/agent_settings.py:740-748`), keys none (SKILL-07 future). jetbrains-toolbox: a launcher, no rules. sublime: no integrated terminal, no rules. neovim: `~/.config/nvim`, no key rules, reads on restart. Unverified reload and cwd cells say `unverified`; phases 29-31 settle them.

### Tests
- **D-03: The registry side comes from `load_tools(REGISTRY)`**, keeping `tool.category in {Category.TERMINAL, Category.EDITOR}` (`installer/model.py:584`, `installer/enums.py:49,51`), compared to the table ids as exact string sets. Today: vscode, jetbrains-toolbox, sublime, neovim, kitty, wezterm, alacritty, herdr.
- **D-04: New `tests/test_tool_onboarding_skill.py`** holds the table and verdict tests. `_parse_verdict` and `_grade` move from `tests/test_catalog_audit_skill.py:251-315` into `tests/skill_verdicts.py`, which both files import. jev shared_helper 0.98.
- **D-05: A pure `table_drift(registry_ids, table_ids)`** names missing and extra ids; inline string fixtures cover missing, extra, duplicate, case variant, shuffled, header-only and non-ASCII lookalike; one `tmp_path` registry (the real file plus one minimal `category = "terminal"` block, as `tests/test_registry.py:1217-1233` does) proves the loader filter end to end. **Own reasoning** (jev committed_fixture_files low 0.51; first rung low 0.59). Ledger.
- **D-06: Verdicts come from a fresh read-only subagent running the user-level `skill-judge`** (rubric v4), stored as in 24.3 (date, judge and commit lines, printed summary, JSON verdict line verbatim); the before file is judged at the commit before the rewrite and never re-run. The test selects `27-SKILLJUDGE-before.md` and `27-SKILLJUDGE-after.md` by exact name, asserts the glob finds exactly 2, both parse, `skill` is tool-onboarding, `rubric_version` and `spec_sha` match, and after `percent` >= before `percent` as numbers. No 80% floor: the last recorded score was 68.8% D with D7 = 0 (no evals), so a floor would always fail. **Own reasoning** (jev no_drop_only low 0.74; first rung low 0.29): scores under different rubrics are not comparable. Ledger.
- **D-07: The test finds the phase dir by globbing `.planning/phases/27-*` and `.planning/milestones/*-phases/27-*` and requires exactly one match.** `devtools/docs_only.py` `TEST_READ` (lines 20-29) and the `LEDGER` in `tests/test_docs_only.py:193` get globs for both locations; `TEST_READ` uses `fnmatch` where `*` crosses `/`, the ledger check uses `Path.glob`, so the two globs differ. jev first rung none_of_these 0.85 contradicted the evidence; second opinion both_locations_exactly_one low 0.67. **jev overridden / Own reasoning.** Ledger.
- **D-08: If after < before, fix, then re-judge**, recording each round as `27-SKILLJUDGE-ROUND-n.md` (outside the counted names); the before verdict is never re-run. **Own reasoning** (jev extra_rounds_other_name low 0.73). Ledger.

### Claude's Discretion
- Exact heading text of the renamed step 7, the order of the four rules, and the wording of the status words' legend.

### Folded Todos
None (`todo.match-phase` scores below 0.4 for this phase; the backlog 999.18 it absorbs is already the phase goal).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/REQUIREMENTS.md` (SKILL-01..06, Owner decisions 2026-11-16) and `.planning/research/SUMMARY.md` (terminal facts)
- `.claude/skills/tool-onboarding/SKILL.md`, `.claude/skills/catalog-audit/SKILL.md` (line 80 quotes step 7's heading)
- `tests/test_docs.py` (lines 291-363: pinned step 7 phrases), `tests/test_catalog_audit_skill.py` (pattern and parser), `tests/test_docs_only.py` and `devtools/docs_only.py`
- `installer/model.py`, `installer/enums.py`, `installer/apps.py`, `installer/executors.py`, `installer/terminal_shell.py`, `.github/workflows/ci.yml`
- `.planning/milestones/v0.50.0-phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-FINAL.md` (verdict format)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_catalog_audit_skill.py:251-315` verdict parser and grader; pipe-row parser at :93-95.
- `load_tools`, `Category` enum, minimal `[[tool]]` fixture shape in `tests/test_registry.py:1217-1233`.
- `skill-judge` user-level skill (rubric v4) for the verdicts.

### Established Patterns
- One test file per skill; shared helpers as modules under `tests/`.
- A test that iterates discovered files asserts the count first (24.3 lesson, 8b66ae13).

### Integration Points
- `devtools/docs_only.py` `TEST_READ` and `tests/test_docs_only.py` `LEDGER` must list any new markdown literal a test reads, or a docs-only push skips the tests.
</code_context>

<specifics>
## Specific Ideas

Coupling handed to phase 29 (not decided here): WezTerm's stock clear is scrollback-only, so TERM-02's clear must map Cmd+K / Ctrl+Shift+K to Ctrl+L rather than rely on the vendor default.
</specifics>

<deferred>
## Deferred Ideas

- Verifying kitty's macOS cmd+k default, `map opt+left` with `macos_option_as_alt no`, config reload behavior, and Alacritty/herdr cwd inheritance: live research in phases 29-31 (table cells say `unverified` until then).
- A dmg method kind and a cask CLI-link param: platform gaps recorded in the skill; each needs its own backlog item if the owner wants them (REQUIREMENTS out of scope today).

### Reviewed Todos (not folded)
None matched.
</deferred>
