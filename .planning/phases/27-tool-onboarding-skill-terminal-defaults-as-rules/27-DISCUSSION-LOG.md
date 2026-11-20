# Phase 27: Tool-onboarding skill: terminal defaults as rules - Discussion Log (Assumptions Mode)

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in CONTEXT.md — this log preserves the analysis.

**Date:** 2026-11-19
**Phase:** 27-tool-onboarding-skill-terminal-defaults-as-rules
**Mode:** assumptions (`--analyze --all --batch`), jev screening, mvp-mode inactive (best design wins), code index
**Areas analyzed:** closed table and its test; skill-judge verdicts; rewrite structure and row facts; macOS CI job; Konsole

## Assumptions Presented

The analyzer was `gsd-assumptions-analyzer` (opus), with 49 tool calls. It read the skill, the registry loader, the catalog-audit skill and its test, `devtools/docs_only.py`, and ran `kitty` and `wezterm` key listings in a scratch HOME. It did not run skill-judge, call jev, or check kitty's macOS defaults. Its agent-skills wiring was not clean (`jev-fast-decision` skipped by a symlink path check), which does not matter because the analyzer must not call jev.

| Assumption | Confidence | Evidence |
|---|---|---|
| Table is a pipe table in SKILL.md, backticked id first | Likely | SKILL.md:54-59,105-110; tests/test_catalog_audit_skill.py:93-95 |
| Registry side from `load_tools` category filter, exact id sets | Confident | installer/model.py:584; installer/enums.py:49,51 |
| New test file plus shared `tests/skill_verdicts.py` | Likely | one test file per skill; tests/launch_doubles.py pattern |
| Pure `table_drift` plus inline fixtures plus one tmp registry | Likely | tests/test_registry.py:1217-1233 |
| Closed status words in rule cells, checked | Likely | installer/version_status.py:1598 `partial:` convention |
| Verdicts by fresh read-only subagent, rubric v4, 24.3 format | Confident | 24.3-SKILLJUDGE-FINAL.md; skill-judge rubric.md |
| Verdict test: exact names, count 2, after >= before, same rubric, no 80% floor | Likely | 24.3 test :400-405; 24-SKILL-JUDGE.md (68.8% D) |
| Glob both phase-dir locations, exactly one | Likely | commit 8b66ae13; devtools/docs_only.py:18-29 |
| Extra rounds named outside the counted names | Likely | 24.3 round files |
| Step 7 renamed, `####` subsections, catalog-audit line 80 updated | Likely | tests/test_docs.py:318-324, 358-363; catalog-audit SKILL.md:80 |
| macOS apps `####` under step 4 | Likely | catalog-audit loads steps 3/4/4b |
| Other lines to change for R6 (3, 15, 209-210, 242, 256-257) | Confident | read in SKILL.md |
| Conflicts section: label as meaning, mapped to `partial:` lines | Likely | terminal_shell.py:598,768 |
| CI job `validate-and-test` | Confident | .github/workflows/ci.yml:15-50 |
| Konsole: no row, one-line note | Confident (no row) / Likely (note) | SPEC R2; REQUIREMENTS.md:100 |

## jev screening

One jev request per item (Laya, then TypeSafe, per the standing go-ahead); each item gets one advisory answer, and `needs_fallback` items are decided by your own reasoning. Summaries only. The ledger carries the "own reasoning" rows.

| Item | jev | Outcome |
|---|---|---|
| a1 table location | low 0.43 (none_of_these); TypeSafe low 0.76 (inline) | **Own reasoning:** inline (D-01, ledger) |
| a2 shared parser | low 0.32; TypeSafe choice shared_helper 0.98 | D-04 |
| a3 fixture approach | low 0.59; TypeSafe low 0.51 (committed_fixture_files) | **Own reasoning:** pure function plus tmp registry (D-05, ledger) |
| a4 closed status words | choice closed_list_checked 0.80 | D-02 |
| a5 verdict rule | low 0.29; TypeSafe low 0.74 (no_drop_only) | **Own reasoning:** same rubric, no drop, no floor (D-06, ledger) |
| a6 phase-dir glob | none_of_these 0.85 (contradicts evidence); second opinion both_locations_exactly_one low 0.67 | **jev overridden / Own reasoning:** no confident second opinion (D-07, ledger) |
| a7 extra rounds | low 0.55; TypeSafe low 0.73 | **Own reasoning:** separate names (D-08, ledger) |
| a8 step 7 structure | low 0.55; TypeSafe low 0.74 (rename_step_update_sibling) | **Own reasoning:** the sibling-skill quote decides (D-09, ledger) |
| a9 macOS apps location | none_of_these 0.75 (contradicts evidence); second opinion install_method_subsection low 0.60 | **jev overridden / Own reasoning** (D-10, ledger) |
| a10 conflicts wording | low 0.70; TypeSafe choice label_as_meaning 0.98 | D-12 |
| a11 Konsole | none_of_these 0.97 (contradicts evidence); second opinion one_line_note low 0.38 | **jev overridden / Own reasoning** (D-13, ledger) |

## Live facts that changed the plan

- C1: the catalog-audit skill quotes step 7's heading and a test requires it to exist; the heading rename needs that line changed (SPEC in-scope amended, D-09). Verified at `catalog-audit/SKILL.md:80` and `tests/test_catalog_audit_skill.py:104-109`.
- C2/C3: the `app` kind extracts `.zip` only; a cask's CLI is brew's. SPEC R4 and REQUIREMENTS SKILL-04 amended (D-10). Verified at `installer/apps.py:1-9` and `installer/executors.py:699-704`.
- C4: no zsh Ctrl+L widget exists; rows say planned for phase 28 (D-16).
- C5: WezTerm's stock Cmd+K / Ctrl+Shift+K is scrollback-only (verified with `wezterm show-keys` in a scratch HOME); the research claim is stale; handed to phase 29.
- C6: new markdown literals read by tests must be classified in `devtools/docs_only.py` and `tests/test_docs_only.py` (D-07).

## Corrections Made

No corrections — the run is unattended; the owner reviews the ledger.

## Auto-Resolved

Unclear items: none. Likely items were each given an advisory jev answer or own reasoning as above.

## External Research

None needed beyond the analyzer's live checks; the unverified cells (kitty macOS defaults, cwd inheritance, reload behavior) are marked `unverified` in the table and settled in phases 29-31.
