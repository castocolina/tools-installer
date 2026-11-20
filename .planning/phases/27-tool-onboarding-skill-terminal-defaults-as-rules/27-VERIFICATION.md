---
phase: 27-tool-onboarding-skill-terminal-defaults-as-rules
verified: 2026-11-20T12:00:00Z
status: human_needed
score: 7/7 must-haves verified
covered_files:
  - ".claude/skills/catalog-audit/SKILL.md"
  - ".claude/skills/tool-onboarding/SKILL.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-01-PLAN.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-01-SUMMARY.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-02-PLAN.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-02-SUMMARY.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-03-PLAN.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-03-SUMMARY.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-04-PLAN.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-04-SUMMARY.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-after.md"
  - ".planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/27-SKILLJUDGE-before.md"
  - "devtools/docs_only.py"
  - "tests/test_docs_only.py"
  - "tests/test_tool_onboarding_skill.py"
covered_digest: "v4:sha256:5d990516cc3a97170199ae0416ea55cff89cecb63d747d3ed5decba53d4a5b2d"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "On the owner's Mac, check each macOS behavior the skill's macOS rules describe (SKILL-05 deferred UAT line)"
    expected: "The macOS behavior holds on real hardware (Option+Left/Right word navigation by two chords, Cmd+K clear, ~/Applications placement)"
    why_human: "No Mac host in this run; the skill text itself marks the real-Mac check as deferred to the owner's Mac and no agent may mark it passed"
---

# Phase 27: Tool-onboarding skill: terminal defaults as rules Verification Report

**Phase Goal:** Anyone onboarding or reviewing a terminal or IDE through the tool-onboarding skill gets the same defaults applied without a question, from one closed table that a test keeps in step with the registry.
**Verified:** 2026-11-20
**Status:** human_needed (only the deferred real-Mac UAT line remains)
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SKILL-01: four rules (a)-(d) stated with OS scope, applied without asking, none a Policies row | VERIFIED | SKILL.md `#### Terminal and IDE defaults` (step 7, lines ~192-201) holds rules (a)-(d), the Spanish-layout reason for (b), and "none of them is a question ... never a Policies row". `rg` for a sentence asking about word navigation, clear or zsh finds nothing; tests `test_rules_*` pass. |
| 2 | SKILL-02: one closed table, one row per terminal/editor registry id, kept in step by a test | VERIFIED | Table at `#### Closed per-terminal table` has 8 rows (kitty, wezterm, alacritty, herdr, vscode, jetbrains-toolbox, sublime, neovim). `test_table_matches_the_registry`, `test_table_drift_new_terminal_entry`, `test_table_drift_names_a_row_with_no_registry_entry`, duplicate/case/shuffle fixtures exist and pass. |
| 3 | SKILL-03: `partial: kept yours` and displaced-default install-note rule, one example each | VERIFIED | `#### Conflicts`: alacritty `partial: you already bind ...` (real line in terminal_shell.py) and kitty `ctrl+shift+k` = `scroll_line_up` labelled planned for phase 29, not presented as current. `test_conflicts_*` pass. |
| 4 | SKILL-04: macOS app research records install, uninstall, config, `~/Applications` feasibility; `~/.local/bin` CLI link; say-why clause; amendments (.dmg gap, cask CLI gap) | VERIFIED | `#### macOS apps` under step 4 (not 4b); `# Verified` templates in step 9 name the facts and the say-why case. `test_macos_apps_*` pass. |
| 5 | SKILL-05: golden-file pure generator, macOS CI covers paths, real-Mac check is a deferred UAT line | VERIFIED (text); real-Mac run deferred | `#### Testing macOS behavior` has all three clauses; names the `validate-and-test` job, matrix `[ubuntu-latest, macos-latest]`, checked against `.github/workflows/ci.yml` by `test_macos_testing_matches_the_ci_workflow`. Real-Mac behavior is human verification. |
| 6 | No contradicting text: terminal "ask" bullets gone, extras stay questions, Common Mistakes narrowed | VERIFIED | `#### Extras are asked` keeps multiplexer/shell/LLM-host questions and says the four defaults are never offered; Common Mistakes bullets narrowed plus new "Asking about one of the four defaults" and Option-as-Alt bullets. `test_rules_extras_stay_questions`, `test_rules_common_mistakes_narrowed` pass. |
| 7 | SKILL-06: before and after skill-judge verdicts, after not lower | VERIFIED | before 69.6% (87/125, D), after 73.6% (92/125, C), same rubric v4. `27-SKILLJUDGE-after.md` records SKILL.md blob 5e3411f8..., which equals `git rev-parse HEAD:.claude/skills/tool-onboarding/SKILL.md`, so the verdict is of the shipped text. `test_verdict_files_before_and_after` plus boundary/unparseable/mixed-rubric tests pass. |

**Score:** 7/7 truths verified (0 behavior-unverified; the real-Mac line is a separate deferred human item).

### Prohibitions

| Prohibition | Status | Evidence |
|-------------|--------|----------|
| Skill must not tell the author to enable global Option-as-Alt | held | Only named to forbid it (rule (b), Common Mistakes); `test_rules_option_as_alt_is_only_named_to_forbid_it` passes. Judgment tier: skill-judge pass. |
| Skill must not promise a mechanism the code lacks | held | Table cells and rule (c) label kitty/wezterm/zsh Ctrl+L parts "planned (phase 28/29)"; "nothing in installer/ does it today" stated. `git diff 8a97ea70 HEAD -- installer` is empty (out-of-scope code untouched). Judgment tier. |
| The four defaults must not become a Policies row or install-time question | held | Stated explicitly in rules and Extras section. Judgment tier. |

Judgment-tier prohibitions here are LLM/reader-judged, non-authoritative; the owner may glance at them in the Mac UAT round.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| SKILL-01 | 27-02 | SATISFIED | Truth 1 |
| SKILL-02 | 27-01 | SATISFIED | Truth 2 |
| SKILL-03 | 27-03 | SATISFIED | Truth 3 |
| SKILL-04 | 27-03 | SATISFIED | Truth 4 |
| SKILL-05 | 27-03 | SATISFIED (real-Mac UAT deferred) | Truth 5 |
| SKILL-06 | 27-01, 27-04 | SATISFIED | Truth 7 |

All six IDs appear in plan frontmatter and in REQUIREMENTS.md (marked Complete, mapped to Phase 27). No orphaned requirement IDs.

*Orchestrator correction (2026-11-20): the verifier's Source Plan column was wrong for five rows; it now matches each plan's `requirements:` frontmatter (27-01: SKILL-02, SKILL-06; 27-02: SKILL-01; 27-03: SKILL-03, SKILL-04, SKILL-05; 27-04: SKILL-06). The covered-input fingerprint is unaffected: it covers the plans, summaries, skill and tests, not this table.*

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Skill/table/verdict/docs tests | `uv run pytest tests/test_tool_onboarding_skill.py tests/test_catalog_audit_skill.py tests/test_docs.py tests/test_docs_only.py tests/test_push_gate.py -q --no-cov` | 190 tests, all passed | PASS |

Full suite and `make` targets were not run by the verifier, by instruction; the orchestrator's 7,872-passed claim is carried, not re-proved.

### Anti-Patterns / Provisional Decisions

No TBD/FIXME/XXX debt markers were checked beyond the skill text (a docs/skill phase). A search of `27-CONTEXT.md` for "needs confirmation", "confirm" and "provisional" found no decision flagged as needing confirmation, so there are no provisional decisions to list. No e2e proof is named in CONTEXT or SPEC (skill text and tests only).

### Human Verification Required

1. **Real-Mac check of the macOS rules (SKILL-05 deferred UAT).**
   **Test:** On the owner's Mac, exercise the macOS behaviors the skill describes once phases 28-29 implement them.
   **Expected:** behavior matches the golden-file output.
   **Why human:** no Mac host here; the skill itself defers this line to the owner's Mac.

### Gaps Summary

No gaps. Phase goal is met in the codebase: rules, closed table, conflict rule, macOS app and testing rules, and skill-judge before/after are present, tested and consistent with the shipped SKILL.md. Review dispositions (27-REVIEW-DISPOSITION.md, backlog 999.24/999.25) and the 27-SECURITY / 27-VALIDATION claims were not independently re-audited beyond the tests above.

---

_Verified: 2026-11-20_
_Verifier: Claude (gsd-verifier)_
