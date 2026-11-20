---
phase: 27
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T03:24:23Z
plans_reviewed: [27-01-PLAN.md, 27-02-PLAN.md, 27-03-PLAN.md, 27-04-PLAN.md]
models:
  opencode-referee-one: "router-env/my-referee-one"
model_sources:
  opencode-referee-one: "pinned"
---

# Cross-AI Plan Review — Phase 27

<!-- gsd:plan-revision-conflicts:begin -->
## Plan-Revision Conflicts

<!-- gsd:plan-revision-conflicts:end -->

## Lane Log

- Default lane `opencode-referee-one` (`router-env/my-referee-one`, opencode CLI): probe succeeded (`opencode run ... "Reply with the single word OK."` returned `OK`, exit 0). Review ran through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one` with stdin closed (`< /dev/null`) under a 2700 s timeout; it produced a full review (4 plan sections, no stub, empty `.err`) in about 4 minutes.
- No lane failed, so the failover lanes `opencode-referee-two` and `opencode-referee-three` were not used. Failures recorded: none.
- Exactly one reviewer ran, so the consensus gate does not engage: every HIGH the reviewer raised is eligible to count. Per the owner rule each HIGH was verified against repo source first (table below); a HIGH is counted only when the source supports the claim and it is material to executing or achieving the phase.

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist to check all four plans against the repository, with a focus on execution blockers and whether the proposed tests enforce the intended behavior.
### Document Type

GSD · implementation plans

## 27-01

### Summary

The plan establishes a useful before-score baseline and connects a closed skill table to the registry loader. However, its proposed future-drift guard hard-codes today’s row count, and the judge step is assigned to an orchestrator mechanism that the referenced GSD workflow does not define.

### Strengths

- The registry comparison uses `load_tools` and the project’s `Category` enum rather than parsing TOML independently; the loader already validates IDs and categories (`installer/model.py:584-608`).
- Missing, extra, duplicate, malformed and empty-row fixtures give the table parser meaningful negative coverage (`27-01-PLAN.md:164-183`, `:227-250`).

### Concerns

- **HIGH — The orchestrator step is not wired into the referenced execution workflow.** The plan requires the orchestrator to perform a custom `type="orchestrator-step"` *before* delegation (`27-01-PLAN.md:70`, `:104-120`). The referenced workflow describes `auto`, `tracer` and `checkpoint:*` task handling, but not this custom type or a pre-delegation dispatch hook (`.claude/gsd-core/workflows/execute-plan.md:224-234`). The executor is instructed to stop if the verdict is absent, so ordinary execution can halt before Task 2.
- **HIGH — The exact-eight assertion defeats the future onboarding workflow.** `test_table_matches_the_registry` must assert eight IDs (`27-01-PLAN.md:164-166`). When a later phase adds a terminal *and* its table row, the set comparison can pass but the count still fails. That conflicts with the requirement that later onboarding add rows alongside entries (`27-SPEC.md:26-29`, `:64-69`).
- **HIGH — The status check validates labels, not the truth they claim.** `bad_status_cells` only checks a permitted prefix (`27-01-PLAN.md:247-250`), yet the threat model says this prevents planned work being presented as existing (`:278-282`). A false `written:` cell passes. The table also hard-codes kitty’s default path (`:189`), while the implementation uses `$XDG_CONFIG_HOME` when set (`installer/terminal_shell.py:151-157`).
- **MEDIUM — Cleanup instructions can destroy unrelated user work.** Task 1 says any extra `git status` entry means the judge wrote it and instructs the orchestrator to revert it (`27-01-PLAN.md:128`). This checkout already has unrelated modified and untracked planning files. A pre-existing change is not evidence of judge tampering.
- **MEDIUM — “Committed” verification does not prove a commit.** `git ls-files --error-unmatch` accepts a staged, uncommitted file (`27-01-PLAN.md:133-137`), although the plan treats it as proof that the before verdict was committed.

### Suggestions

- Make the judge a supported, explicitly invoked orchestration prerequisite and define its handoff to the executor.
- Assert registry/table equality and non-emptiness, not a permanent row count; add a fixture proving a matched new terminal and row pass.
- Correct the kitty path and review each factual status against source; describe the prefix check as syntactic, not a truth guarantee.
- Snapshot status before judging, compare afterward, and stop without reverting unexplained changes. Verify the verdict exists in `HEAD` and that its commit precedes skill edits.

### Risk Assessment

**HIGH** — The first wave can block on an unsupported handoff, and a successfully implemented count assertion would obstruct the later phases the table is intended to support.

## 27-02

### Summary

The plan clearly separates the four defaults from optional extras and accounts for the audit skill’s heading reference. Its contradiction checks, however, are narrower than their stated guarantees, and the proposed blanket rule conflicts with exceptions in the table.

### Strengths

- The heading rename and the dependent audit-skill quote are changed together, preserving the existing heading-coupling check (`27-02-PLAN.md:139-144`; `.claude/skills/catalog-audit/SKILL.md` is checked by `tests/test_catalog_audit_skill.py`).
- The existing install-tuning and Policies text pins are explicitly preserved (`tests/test_docs.py:292-315`, `:339-363`).

### Concerns

- **HIGH — The prescribed rule contradicts the prescribed table.** The proposed prose says all four rules apply to *every* terminal and IDE entry (`27-02-PLAN.md:143-152`), while Plan 01 marks all four `n/a` for some editor/launcher entries and marks VS Code’s same-directory rule `n/a` because IDE *keybindings* are future work (`27-01-PLAN.md:193-196`). Same-directory inheritance is not necessarily a keybinding. A later onboarding agent cannot tell whether to implement it or treat it as inapplicable.
- **MEDIUM — The “no questions” detector misses ordinary questions.** The proposed regex recognizes `ask`, `asks` and `asked`, followed by a small vocabulary within 80 characters (`27-02-PLAN.md:185-188`). For example, “Offer the developer a choice of launched shell” or “Ask whether new panes inherit the working directory” passes despite contradicting the intended rule. The existing skill’s terminal bullet demonstrates the range of wording being replaced (`.claude/skills/tool-onboarding/SKILL.md:185-191`).
- **MEDIUM — The Option-as-Alt check can accept a recommendation.** It treats any `never`, `not`, `no` or `without` anywhere in a punctuation-delimited unit as sufficient negation (`27-02-PLAN.md:189-190`). “Do not change the font; enable Option-as-Alt” is split safely, but “Without changing the font, enable Option-as-Alt” would pass. The test should not be described as proving the prohibition.
- **LOW — The tests enforce a fixed order despite the stated ordering edge.** The plan calls the rule anchors an unordered set (`27-02-PLAN.md:27-28`) but requires letters in `a,b,c,d` order (`:126-128`).

### Suggestions

- State the defaults as applying **where the capability exists**, and distinguish genuinely inapplicable capabilities from applicable-but-deferred IDE work. Correct the VS Code current-directory cell accordingly.
- Add mutation cases for alternate question wording and misleading negation. Keep human review as the semantic backstop rather than claiming regex completeness.
- Either accept reordered rule items or explicitly revise the ordering requirement.

### Risk Assessment

**MEDIUM** — The prose rewrite is executable, but ambiguous applicability could misdirect downstream onboarding, while the automated checks provide weaker protection than claimed.

## 27-03

### Summary

The plan covers the conflict, macOS app and testing requirements with concrete examples and correctly identifies the current CI matrix. Its principal risk is presenting planned conflict behavior as if kitty already implements it, and its CI drift test does not actually verify the claimed relationship.

### Strengths

- The conflict discussion is grounded in real `partial:` producers and the status consumer (`installer/terminal_shell.py:583-600`; `installer/version_status.py:1595-1601`).
- The macOS guidance identifies real implementation mechanisms: cask passes `--appdir` (`installer/executors.py:699-704`), while the app executor extracts a ZIP and conditionally prepares a CLI link (`installer/apps.py:94-113`, `:129-153`).

### Concerns

- **HIGH — The conflict example claims unimplemented kitty behavior as current.** The prescribed text says “Today that result” is a terminal partial line and then says a conflicting kitty binding is kept and reported (`27-03-PLAN.md:132-135`). The cited current key-conflict producer is specifically Alacritty (`installer/terminal_shell.py:583-600`); the kitty binding work is planned for phase 29. This conflicts with the phase constraint not to promise mechanisms the code lacks (`27-SPEC.md:71-75`).
- **MEDIUM — CI token presence does not establish macOS test coverage.** The proposed test only searches the entire workflow for four independent strings (`27-03-PLAN.md:161-166`). They could remain in comments or unrelated jobs after macOS is removed from the test matrix, while the test stays green. Today the relationship is real: the same job has the OS matrix and gated `make test` step (`.github/workflows/ci.yml:15-22`, `:32-50`).
- **MEDIUM — The `# Verified` example mixes incompatible methods without clearly separating cases.** It describes a cask-installed bundle, an `app`-kind CLI link and an unsupported DMG in one example (`27-03-PLAN.md:221-225`). Because the cask has no such CLI-link parameter, this is easy to copy as though one method supplies all three facts.

### Suggestions

- Explicitly label the kitty conflict example as **planned for phase 29**, and distinguish the existing Alacritty partial warning from future kitty behavior.
- Check the CI job’s matrix and test step as related structure, or narrow the test’s stated guarantee and retain a manual workflow review.
- Give separate, internally consistent `# Verified` examples for a cask and an app/DMG gap.

### Risk Assessment

**MEDIUM** — No installer code changes here, but misleading skill guidance could cause later agents to rely on behavior that does not yet exist.

## 27-04

### Summary

The before/after comparison, exact filenames and archive-aware phase lookup are sensible. The same unsupported orchestrator handoff remains, and the reused parser does not validate all the properties needed to make two scores genuinely comparable.

### Strengths

- The plan compares numeric percentages, requires matching rubric identifiers and tests equal/lower/higher boundaries (`27-04-PLAN.md:191-208`).
- It accounts for verdict files in both active and archived phase locations and marks them test-read; the classifier’s `fnmatchcase` implementation supports that approach (`devtools/docs_only.py:20-35`; `27-04-PLAN.md:209-219`).

### Concerns

- **HIGH — The after-judge handoff has the same execution gap as Plan 01.** Task 1 again depends on an unrecognized pre-delegation `orchestrator-step` (`27-04-PLAN.md:108-124`), whereas the referenced workflow lists the supported task types (`.claude/gsd-core/workflows/execute-plan.md:229-234`). No mechanism shown ensures the after verdict is created before the executor checks it.
- **HIGH — Matching rubric metadata does not guarantee comparable scores.** The existing parser checks that score and maximum keys match and that totals add up, but it does **not** verify that maximum values equal `_RUBRIC_MAX` (`tests/test_catalog_audit_skill.py:269-270`, `:293-310`). Plan 04 moves that parser unchanged and only compares `rubric_version` and `spec_sha` (`27-04-PLAN.md:159-161`, `:193-197`). Two malformed verdicts with identical metadata but different maxima can pass and produce a misleading comparison. This matters because skill-judge requires maxima copied from the rubric (`~/.claude/skills/skill-judge/SKILL.md:53-57`).
- **MEDIUM — The after verdict can become stale without detection.** The test compares stored documents, not the current skill content (`27-04-PLAN.md:203-208`). A subsequent skill edit can pass while the “after” score still describes an earlier revision; the recorded commit is prose only (`:124-126`).
- **MEDIUM — The same unsafe status cleanup appears in the fix loop.** The plan instructs reverting any files outside the step’s expected set (`27-04-PLAN.md:127-129`) without first distinguishing pre-existing work from judge-created changes.

### Suggestions

- Use the supported, explicit judge handoff recommended for Plan 01.
- Validate each verdict’s maxima and numeric types against the pinned rubric, and add a mismatched-maxima fixture before comparing percentages.
- Record and verify a hash of the judged skill content, or clearly scope the verdict as historical evidence and require a fresh judgment when that content changes during phase execution.
- Compare status against a pre-judge snapshot; stop rather than reverting unrelated changes.

### Risk Assessment

**HIGH** — The phase-closing gate may not run under the stated workflow, and an apparently passing comparison can accept scores calculated against different maxima.

### Cross-plan conclusion

**Status: Issues found — revise and re-review.** The highest-priority fixes are the judge handoff, removal of the fixed eight-row assertion, and clarification of applicable versus deferred defaults. The phase has a coherent dependency order otherwise, and its source-grounded fixtures provide a solid basis for revision.

**Not checked:** I did not execute the plans, run the full test suite, or verify terminal behavior on macOS. No files were edited.


---

## Consensus Summary

One grounded reviewer ran (`opencode-referee-one`; its section carries `file:line` evidence and no discount marker), so there are no cross-reviewer "Agreed" items. The summary below is the review agent's synthesis after checking every reviewer HIGH against source.

### Agreed Strengths

Single reviewer; no corroboration is possible. Strengths the review agent confirmed independently against source:

- The registry side of the closed table uses `load_tools` and `Category` (`installer/model.py:584`, `installer/enums.py:49-51`); the eight terminal and editor ids the plans name (alacritty, herdr, jetbrains-toolbox, kitty, neovim, sublime, vscode, wezterm) are exactly what the loader returns today.
- Every line anchor the plans rely on holds at HEAD: step 7 is `.claude/skills/tool-onboarding/SKILL.md:178-215`, `### 8.` is `:217`, the file is 268 lines and byte-identical to `1bb31e00` (`git diff --quiet 1bb31e00 HEAD` exits 0); the moved verdict block is `tests/test_catalog_audit_skill.py:252-315` and the file has 58 `assert` lines; the macOS app facts (`installer/executors.py:699-704`, `installer/locations.py:89-91`, `installer/model.py:96,105`, `installer/apps.py`, `installer/download.py`) and the CI job facts (`.github/workflows/ci.yml:15-50`) are exact.
- The plans keep the pinned phrases of `tests/test_docs.py:292-363` and the audit skill's heading quote in step (rename and quote change in the same commit).

### Agreed Concerns

None (single reviewer). See "HIGH verification" for the reviewer's HIGH items and how each was counted.

### Divergent Views

None (single reviewer).

---

## HIGH verification (review agent, against repo source)

The reviewer raised 7 HIGH items. Each was checked against source before counting. Result: 0 counted as HIGH, 6 sustained at MEDIUM (all actionable, all listed under "Actionable non-HIGH concerns" below), 1 split into a LOW fix and a plan-acknowledged limitation.

| # | Reviewer HIGH | Source check | Verdict |
|---|---------------|--------------|---------|
| H1 | 27-01: `orchestrator-step` is not wired into the execute workflow | True as stated: `.claude/gsd-core/workflows/execute-plan.md:229-234` handles `auto`, `tracer` and `checkpoint:*` only, and `orchestrator-step` appears nowhere in `.claude/gsd-core` except an unrelated phrase at `workflows/plan-phase.md:197`. But the plan fails closed and loudly: the executor runs two verify commands and prints `BLOCKED: 27-01 Task 1 (orchestrator-step) not done` (27-01-PLAN.md:116), and the handoff is stated in ROADMAP.md:84,93 and 27-VALIDATION.md:50. Failure mode is a visible stop plus one manual step, not wrong output or data loss. | MEDIUM, actionable (counted below) |
| H2 | 27-01: exact-eight assertion defeats later onboarding | True: 27-01-PLAN.md:165 requires "the id list has 8 entries", while 27-SPEC.md boundaries say a later terminal "adds the row with the entry, and the test enforces it" (Ghostty, Herdr app, iTerm2 are all planned catalog entries). The count turns the next terminal into a red gate for a reason the table check already covers. Loud and trivial to fix, goal of phase 27 unaffected. | MEDIUM, actionable |
| H3 | 27-01: status prefix check proves labels, not truth; kitty path hard-coded | Split. (a) Labels-not-truth is inherent and already declared by the plan ("test plus judgment", 27-01-PLAN.md:61, T-27-03 mitigates `bad_status_cells` only as a closed-word check). Not a defect. (b) True: the kitty cell says `~/.config/kitty/kitty.conf`, but `installer/terminal_shell.py:155-157` resolves `_xdg_config_home(...) / "kitty" / "kitty.conf"` (honours `XDG_CONFIG_HOME`); the wezterm cell already states the XDG form. | (a) not counted; (b) LOW, actionable |
| H4 | 27-04: after-judge handoff has the same gap | Same evidence and same fail-closed design as H1 (27-04-PLAN.md:120, `BLOCKED: 27-04 Task 1 (orchestrator-step) not done`). | MEDIUM, actionable (merged with H1 as one concern spanning both plans) |
| H5 | 27-02: "every terminal and IDE entry" contradicts the table's `n/a` cells | True as an inconsistency: 27-02-PLAN.md:147 says the four rules apply "to every terminal and IDE entry", while 27-01-PLAN.md:193-196 marks all four `n/a` for vscode-(b/c/d), jetbrains-toolbox, sublime, neovim. The legend (27-01-PLAN.md:187) already defines `n/a` as "the rule does not apply", so the table is the closed authority and no executor is blocked; the prose just needs "where the entry has that capability". | MEDIUM, actionable |
| H6 | 27-03: conflict example claims kitty behaviour as current | True: item 1 (27-03-PLAN.md:134) ends "a user who already binds `ctrl+shift+k` in `kitty.conf` keeps that binding, and the kitty row reports `partial: kept yours`", but the only producers of key-conflict `partial:` lines are alacritty (`installer/terminal_shell.py:598`, loop at `:583-600`) and herdr (`:768`); no kitty key code exists. Item 2 is labelled planned for phase 29, item 1's example is not, against the SPEC constraint "does not promise a mechanism the code lacks" (27-SPEC.md Constraints). The sentence before it ("phase 28 settles the exact wording") limits the damage; fix is one label or an alacritty example. | MEDIUM, actionable |
| H7 | 27-04: matching `rubric_version` and `spec_sha` does not guarantee comparable maxima | True: `_parse_verdict` (moved unchanged from `tests/test_catalog_audit_skill.py:252-315`) checks only that `scores` and `max` share keys, `0 <= score <= max`, and the sums (`:296-306`); it never compares `max` with `_RUBRIC_MAX` (defined at `:270`, used only by the `_verdict` fixture builder at `:321`). `verdict_regressions` (27-04-PLAN.md:193-197) compares skill, `rubric_version`, `spec_sha` and percent only. Reaching the failure needs a judge that emits non-rubric maxima while echoing the same rubric id, so it is defence in depth, but a one-line comparison closes it. | MEDIUM, actionable |

No single-reviewer discount applies (the reviewer cited `file:line` throughout), so the consensus gate was not needed; the counting above is the review agent's own source-based severity call.

## Review-agent additions (not in the reviewer's list)

- MEDIUM (confirmed, also raised by the reviewer as MEDIUM): 27-01-PLAN.md:128 and 27-04-PLAN.md:128 tell the orchestrator that any `git status --porcelain` line beyond the verdict file means the judge was not read-only and to "revert those changes". The tree at review time already carries `M .planning/state.json` and `?? .planning/goals/2026-11-19-phases-27-28-29-30-31-32-33-34-35.md` (both unrelated, both GSD-owned), so the check would misfire on the first run and the revert instruction would destroy owner work.
- LOW (reviewer MEDIUM, confirmed): `git ls-files --error-unmatch` (27-01-PLAN.md:136, 27-04-PLAN.md:135) succeeds for a staged but uncommitted file, so it does not prove "committed".
- LOW (reviewer MEDIUM, confirmed): 27-03 Task 3's `# Verified` example (27-03-PLAN.md:223-225) puts a cask bundle (`--appdir`), an `app`-kind CLI link and a `.dmg` gap into one three-line example, which contradicts the paragraph above it that says a cask's CLI link is brew's and not `~/.local/bin`. Copyable as a contradiction.
- LOW (reviewer MEDIUM, confirmed): 27-03's CI test (27-03-PLAN.md:166) greps the whole workflow for four independent strings, so a comment or another job could keep them green after the macOS matrix entry is removed. Today the relationship is real (`ci.yml:15-22` matrix, `:32-50` gated `Test` step).
- Not counted (accepted limitations, already paired with judgment in the plans): 27-02's `ASK_RE` vocabulary and `option_as_alt_unnegated` negation window are heuristic regexes (27-02-PLAN.md:185-190); the plan's own prohibitions say "test plus judgment" and 27-04's skill-judge pass reviews the prose. The `a,b,c,d` letter-order assertion (27-02-PLAN.md:126-128) versus the "unordered anchors" wording (`:27-28`) is cosmetic. The after verdict being a stored document that a later skill edit can outdate is intended historical evidence, and 27-04 Tasks 2-3 do not edit SKILL.md.

## Actionable Non-HIGH Concerns (PLAN.md change still needed)

1. MEDIUM, 27-01 and 27-04 (H1/H4): Task 1 in both plans is a task type the GSD execute workflow does not define. Make the handoff native: either mark the task `type="checkpoint:human-action"` (control returns to the orchestrator, which performs the judge run and resumes) or set `autonomous: false` and state in `<objective>` that the orchestrator must complete Task 1 before dispatching the plan; keep the executor verify-and-BLOCKED fallback.
2. MEDIUM, 27-01 Task 2 (H2): drop "and the id list has 8 entries" from `test_table_matches_the_registry`; keep `table_drift(...) == []` plus a non-empty assertion, and add a fixture proving that a new terminal with its row passes (registry and table both gain `demo-term`).
3. MEDIUM, 27-01 Task 1 step 4 and 27-04 Task 1 step 6: replace "status must list only the verdict file; revert anything else" with a before/after `git status --porcelain` snapshot compared by diff; investigate and report unexplained deltas, never revert files the orchestrator did not see the judge touch (`.planning/state.json` and the goals file are pre-existing).
4. MEDIUM, 27-02 Task 1 (H5): change the rules sentence to "These four rules apply to every terminal and IDE entry that has the capability, without asking; the table below marks the rest `n/a` with the reason", and decide the VS Code (d) cell explicitly (applies to the integrated terminal, or `n/a` with a reason that is not "SKILL-07 keybindings"). Keep the pinned needles ("none of them is a question", "never a Policies row").
5. MEDIUM, 27-03 Task 1 (H6): label item 1's example as planned for phase 29 (as item 2 is), or use the existing alacritty line (`alacritty: partial: you already bind ...`, `installer/terminal_shell.py:598`) as the example that exists today.
6. MEDIUM, 27-03 Task 3: split the step 9 `# Verified` example into two internally consistent examples (cask: bundle via `--appdir`, CLI link is brew's and recorded as a platform gap; `app` kind: `.zip` bundle plus `cli` link; `.dmg` as a separate gap line), so no single example mixes methods. Keep the pinned needles (`# Verified` line, `~/Applications`, `~/.local/bin`, `no user location`, `because`).
7. MEDIUM, 27-04 Task 3 (H7): in `verdict_regressions` add a `max` comparison (before vs after, or each against `RUBRIC_MAX`) with a mismatched-maxima fixture in `test_verdict_regressions_refuses_mixed_rubrics`.
8. LOW, 27-01 Task 1 verify and 27-04 Task 1 verify: prove the commit exists (`test -n "$(git log -1 --format=%h -- <file>)"`) in addition to or instead of `git ls-files --error-unmatch`.
9. LOW, 27-01 Task 2 (H3b): the kitty row's config cell becomes "`$XDG_CONFIG_HOME/kitty/kitty.conf`, else `~/.config/kitty/kitty.conf`" (installer/terminal_shell.py:155-157), matching the wezterm cell's style.
10. LOW, 27-03 Task 2: make the CI check structural (parse `.github/workflows/ci.yml` and assert job `validate-and-test` has `macos-latest` in `strategy.matrix.os` and a step named `Test` running `make test`), or narrow the stated guarantee to "the strings exist" and keep the manual workflow review.

---

## Verification coverage

Source-grounding pass (`plan_review.source_grounding` is on). Effective authority resolved by `gsd-tools drift-guard authority` is `intel` (`.planning/config.json` carries `plan_review.source_grounding_authority: "grep"`; the seam answer was used). The `intel` adapter analyzes JavaScript only, so every Python, TOML, YAML and Markdown symbol is UNCHECKABLE under that adapter (severity INFO, never a block). The review agent resolved them anyway by reading the files directly (grep-adapter semantics), recorded as VERIFIED with `file:line` below. No symbol was MISSING; no hard block.

Symbols the plans declare under "Artifacts this phase produces" (new in this phase, not verified): `27-SKILLJUDGE-before.md`, `27-SKILLJUDGE-after.md`, `27-SKILLJUDGE-ROUND-{n}.md`, `tests/test_tool_onboarding_skill.py` and its symbols (`REPO_ROOT`, `SKILL`, `REGISTRY`, `TABLE_HEADING`, `ID_CELL_RE`, `STATUS_RE`, `_text`, `_step`, `_subsection`, `_fixture`, `table_rows`, `table_ids`, `registry_ids`, `table_drift`, `bad_status_cells`, `RULES_HEADING`, `EXTRAS_HEADING`, `ASK_RE`, `rule_items`, `ask_sentences`, `option_as_alt_unnegated`, `CONFLICTS_HEADING`, `_items`, `MACOS_TESTING_HEADING`, `MACOS_APPS_HEADING`, `_verdict_doc`, `verdict_regressions`, `_phase_dir`), `tests/skill_verdicts.py` (`VERDICT_KEYS`, `GRADE_FLOORS`, `PASS_PERCENT`, `DIMENSIONS`, `RUBRIC_MAX`, `grade`, `parse_verdict`), the SKILL.md headings `#### Closed per-terminal table`, `#### Terminal and IDE defaults`, `#### Extras are asked`, `#### Conflicts`, `#### Testing macOS behavior`, `#### macOS apps`, the renamed step 7 heading, the LEDGER keys and the `TEST_READ` entry `.planning/*27-SKILLJUDGE-*`.

Pre-existing symbols, VERIFIED (read in this review):

| Kind | Symbol (plan line quoted) | Evidence |
|------|---------------------------|----------|
| file | `.claude/skills/tool-onboarding/SKILL.md` "268 lines ... step 7 :178 to :215, `### 8.` at :217" (27-01-PLAN.md:97) | 268 lines; `:178` heading, `:215` "never becomes a Policies knob by default.", `:217` `### 8.`; identical to `1bb31e00` |
| file | `.claude/skills/catalog-audit/SKILL.md:80` heading quote (27-02-PLAN.md:142) | `:80` carries the quote with "Its" at the line end, `:81` starts "TUNE-04 rule" |
| function | `load_tools` (27-01-PLAN.md:181) | `installer/model.py:584` |
| enum | `Category.TERMINAL`, `Category.EDITOR` (27-01-PLAN.md:181) | `installer/enums.py:49-51` ("editor", "terminal"); loader returns the eight named ids |
| function | `_skill_section` (27-01-PLAN.md:177) | `tests/test_docs.py:318-324` |
| function | `_parse_verdict`, `_grade`, `_verdict`, constants block (27-04-PLAN.md:160-161) | `tests/test_catalog_audit_skill.py:252-315` block, `:318-336` `_verdict`; `cast` used only in the block; `_VERDICT_KEYS`, `_GRADE_FLOORS`, `_PASS_PERCENT` unused outside it; `PHASE_DIR` at `:251` |
| function | `_STEP_RE`, `_table_rows`, `_assert_all_in` (27-02/03) | `tests/test_catalog_audit_skill.py:82-101` |
| constant | `TEST_READ`, `is_docs_path` (27-04-PLAN.md:218) | `devtools/docs_only.py:20-35`; `fnmatchcase`, `*` crosses `/` |
| constant | `LEDGER`, `markdown_literals` (27-01/04) | `tests/test_docs_only.py:30-45` (literals `endswith(".md")`, `== ".planning"`, `startswith(".planning/")`) and `:193-260` |
| function | `_kitty_config_path`, `_wezterm_config_path`, `_sync_konsole` (27-01 read_first) | `installer/terminal_shell.py:155-157`, `:165`, `:359` |
| string | `partial: you already` producers (27-03-PLAN.md:104) | `installer/terminal_shell.py:560`, `:598`, `:768` |
| function | `startswith("partial:")` consumer (27-03-PLAN.md:104) | `installer/version_status.py:1598` |
| function | `_cask` with `--appdir={applications_dir()}` (27-03-PLAN.md:100) | `installer/executors.py:699-704` |
| function | `applications_dir()` (27-03-PLAN.md:100) | `installer/locations.py:89-91` |
| params | `app`: url, app, cli, cli_name, version, sha256, smoke_argv; `cask`: cask, app, min_os_version, smoke_argv (27-03-PLAN.md:101) | `installer/model.py:96`, `:105` |
| function | `ditto -x -k` extraction, CLI link into `~/.local/bin`, `cli_name` reader (27-03-PLAN.md:102) | `installer/apps.py:5,143` (and the `applications_dir()` call at `:101`); `installer/download.py:205-228` |
| string | kitty macOS `script` `bin_dir = "/Applications/kitty.app/Contents/MacOS"` (27-03-PLAN.md:103) | `installer/registry.toml:3047` (macos `script` method) |
| CI | job `validate-and-test`, `macos-latest`, `Classify the change`, `Test` runs `make test` (27-03-PLAN.md:105) | `.github/workflows/ci.yml:15-50` |
| function | vscode `terminal.integrated.defaultProfile.{linux,osx}` = zsh (27-01-PLAN.md:162) | `installer/agent_settings.py:742-749` (`_vscode_lean`); post-install action name `apply_agent_tuning` is declared in `installer/registry.toml` (not a function; dispatched via `installer/post_install.py`) |
| CLI | `herdr server reload-config` (27-01 herdr row) | `installer/terminal_shell.py:776`, `installer/postinstall.py:461` |
| id | commits `1bb31e00`, `75fa8ab0` | both resolve (`git cat-file -t` = commit) |

Not checked and why (UNCHECKABLE, INFO only):

- Signatures and behaviour of the not-yet-written test helpers cannot be verified before execution; only their plan text was reasoned about (for example the 27-01 Task 3 fixture expectations against `ID_CELL_RE`, the `ASK_RE` and `option_as_alt_unnegated` behaviour on the planned skill text, and the test counts `-k table` 13, `-k rules` 14, `-k verdict` 4, all of which add up as the plans state).
- `~/.claude/skills/skill-judge/SKILL.md` (27-01 read_first, 27-04 read_first) lives in the real user home that this run must not touch; the rubric version `4` the plans pin was confirmed only indirectly from `24.3-SKILLJUDGE-FINAL.md:30` (`"rubric_version": 4`).
- The skill-judge before/after scores themselves (the after-not-lower outcome is a runtime fact; the bloat risk from adding roughly 150 lines to a 268-line skill is real, and D-08 round files are the planned handling).
- Neither the full test suite nor any macOS behaviour was run; no code or plan file was edited.

Cross-artifact fact-drift pass (advisory; contributes to neither count):

- Phase status: `gsd-tools drift-guard phase-status --phase 27` returned `lag` (STATE.md "Ready to execute", ROADMAP.md "Not started", authority STATE.md): two non-terminal statuses one lifecycle step apart. Not a finding.
- ROADMAP Success Criteria vs PLAN `must_haves.truths`: criteria 1-5 map onto plans 27-02 (rules), 27-01 (closed table and coverage test), 27-03 (conflict, macOS apps, macOS testing) and 27-04 (before/after verdicts); no plan contradicts a criterion; the plans add truths (edge coverage) beyond the roadmap, which is sanctioned. No contradiction.
- Requirement IDs: ROADMAP `**Requirements:** SKILL-01..06` vs PLAN `requirements:` (27-01 SKILL-02 and SKILL-06, 27-02 SKILL-01, 27-03 SKILL-03/04/05, 27-04 SKILL-06) vs REQUIREMENTS.md traceability rows 114-119: consistent (ROADMAP's plan list names only SKILL-02 for 27-01 while the plan adds SKILL-06 for the before verdict; an addition, not a contradiction).
- CONTEXT.md `Decisions` vs PLAN usage: closed status words (D-02), the eight ids (D-03), the verdict file names and rubric rules (D-06/D-07), the heading rename and its audit-skill quote (D-09), the platform gaps (D-10), `partial: kept yours` (D-12), Konsole sentence (D-13), CI job name (D-15) and "rule (c) planned for phase 28" (D-16) all agree with the plans. CONTEXT cites "Overview line 15" and the plan inserts after `:19`; the same insertion point in different words (the sentence starts at :15, ends at :19), not drift.
- Skipped axes: none (STATE.md, ROADMAP.md, CONTEXT.md, SPEC.md and REQUIREMENTS.md all present).
