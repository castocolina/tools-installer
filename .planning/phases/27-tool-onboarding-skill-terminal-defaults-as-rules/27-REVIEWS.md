---
phase: 27
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T03:58:00Z
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

## Lane Log (convergence cycle 2, plans at c33b8658)

- Default lane `opencode-referee-one` (`router-env/my-referee-one`, opencode CLI, owner-required first lane): probe succeeded (`opencode run -m router-env/my-referee-one "Reply with the single word OK."` returned `OK`, exit 0, stdin closed). The review ran through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one` with stdin closed (`< /dev/null`) in the background; it produced a full review (four plan sections, no stub, empty `.err`) in about four minutes. A 214 KB prompt (plans, CONTEXT, RESEARCH, cycle 1 finding list) was sent whole; no split was needed.
- No lane failed, so the failover lanes `opencode-referee-two` and `opencode-referee-three` were not used. Failures recorded: none.
- Exactly one reviewer ran, so the consensus gate does not engage. Per the owner rule each HIGH was verified against repo source before it was counted (table below); a HIGH counts only when the source supports the claim and it is material to executing or achieving the phase.

## OpenCode Review (opencode-referee-one)

Using the plan-review checklist to reassess each cycle 1 finding and verify the revised execution path against the repository. I’ll keep the review read-only.
The revised handoff still appears to rely on behavior the GSD orchestrator does not define; I’m checking the remaining guards and test instructions for independent blockers.
### Status: Issues Found — fix and re-review

**Document type:** GSD implementation plans  
**Overall assessment:** Not ready for unattended execution. The revision fixes most cycle 1 concerns, but the judge handoff is still not connected to the installed GSD workflow. There are also gaps in the read-only snapshot and CI-structure checks.

## 27-01

### Summary

Records the before verdict, adds the registry-backed table, and tests table drift.

### Strengths and cycle 1 dispositions

- **Finding 2 — RESOLVED:** The real-table test requires non-empty IDs and zero drift rather than exactly eight rows; a second fixture accepts an added registry ID with an added table ID (`27-01-PLAN.md:166-170`).
- **Finding 3 — RESOLVED for the destructive-cleanup issue:** The procedure no longer reverts unexpected changes and uses a path-limited commit (`27-01-PLAN.md:75-87`). The new snapshot has a separate limitation below.
- **Finding 8 — RESOLVED:** The guard requires a commit touching the verdict and checks the file against `HEAD`; a file that has only ever been staged cannot satisfy it (`27-01-PLAN.md:135-139`).
- **Finding 9 — RESOLVED:** The kitty cell includes the XDG path and fallback (`27-01-PLAN.md:191`), matching `installer/terminal_shell.py:151-157`.

### Concerns

- **HIGH — Finding 1: STILL OPEN — the pre-dispatch handoff is not implemented by the orchestrator.** The plan puts the judge procedure in its objective and claims `autonomous: false` makes the orchestrator run it before delegation (`27-01-PLAN.md:73-88`). The installed workflow instead constructs an external prompt from the objective and tasks and immediately invokes the configured command (`.claude/gsd-core/workflows/execute-phase.md:437-440`; `.claude/gsd-core/workflows/execute-phase/detail/elaboration.md:82-99`). Its normal checkpoint handling says `autonomous: false` plans require interaction and starts an executor, not an objective-defined pre-dispatch hook (`execute-phase.md:1086-1108`). With the current cross-AI configuration (`.planning/config.json:46-50`), Task 1 therefore encounters a missing verdict and blocks unless someone performs the prerequisite outside the stated workflow. The replacement `auto` task is supported, but it does not cause the prerequisite to run.

- **MEDIUM — NEW: the snapshot misses edits to pre-existing untracked files.** `git status --porcelain` records their paths, while `git diff HEAD --binary` does not include their contents (`27-01-PLAN.md:75-77`). Changing the contents of an already-untracked goals file leaves both snapshot components unchanged. Thus the plan avoids destructive cleanup, but its “any delta” / read-only evidence is too strong (`27-01-PLAN.md:24`, `:286-289`). The current tree already contains an untracked goals file.

- **MEDIUM — NEW: the judge is pinned to the main checkout, not the execution worktree.** The verbatim prompt names `/var/home/bazzite/git/personal/tools-installer` (`27-01-PLAN.md:76`), whereas the execution workflow supports per-plan worktree isolation (`execute-phase.md:608-614`). If the orchestrator is running in another worktree, the judge can score a different tree while the snapshot and commit guard inspect the active one.

### Suggestions

Provide a supported orchestrator-side gate or an explicit, repeatable external prerequisite before invoking GSD; do not rely on the frontmatter flag alone. Pass the active worktree root to the judge and include content hashes for untracked files in any claim that the snapshot detects tree changes.

### Risk assessment

**High:** a standard run blocks before implementation; in a worktree it may score the wrong skill. No destructive cleanup is prescribed.

## 27-02

### Summary

Renames step 7, states the four defaults, and retains questions only for extras.

### Strengths and cycle 1 disposition

- **Finding 4 — RESOLVED:** The rule is capability-scoped and explains that out-of-scope parts receive `n/a` with a reason (`27-02-PLAN.md:143-152`). The VS Code same-directory cell is explicitly `unverified`, while its keybinding cells are scoped out (`27-01-PLAN.md:189-195`).
- The plan preserves the existing step-7 phrase checks and updates the catalog-audit heading quote in the same task (`27-02-PLAN.md:121-155`; `tests/test_docs.py:292-315, 358-363`; `.claude/skills/catalog-audit/SKILL.md:73-82`).
- The specified `-k rules` threshold of 14 matches the described five initial cases, four parametrized ask-detector cases, and five additional checks (`27-02-PLAN.md:126-136, 186-200, 225-226`).

### Concerns

No additional blocking defect found in this plan. The plan acknowledges that its ask and Option-as-Alt detectors are heuristics, not semantic proofs (`27-02-PLAN.md:281-285`).

### Suggestions

Keep prose review as a separate judgment rather than treating the regexes as complete enforcement.

### Risk assessment

**Low**, assuming 27-01 completes and its table remains available.

## 27-03

### Summary

Adds conflict and macOS rules, method-specific examples, and a structural CI check.

### Strengths and cycle 1 dispositions

- **Finding 5 — RESOLVED:** The current example is Alacritty, with kitty explicitly described as planned (`27-03-PLAN.md:121-137`). The cited conflict producer exists in `installer/terminal_shell.py:583-601`, and the consumer checks the `partial:` prefix in `installer/version_status.py:1595-1601`.
- **Finding 6 — RESOLVED:** The cask, `app`-kind, and DMG examples are now separate blocks (`27-03-PLAN.md:232-241`). The cask and ZIP mechanisms correspond to `installer/executors.py:699-704` and `installer/apps.py:98-113, 130-144`.
- **Finding 10 — PARTIALLY RESOLVED:** Parsing the named job and step is materially stronger than grepping loose tokens (`27-03-PLAN.md:165-175`), and the current workflow does have the stated matrix, classifier and test step (`.github/workflows/ci.yml:15-22, 32-50`). The proposed assertions still do not establish that the test actually runs in the claimed circumstances.

### Concerns

- **MEDIUM — NEW: the parsed CI check accepts inverted or non-executing logic.** Requiring the Test step’s `if` merely to *contain* `steps.scope.outputs.full` accepts `steps.scope.outputs.full == 'false'`, which reverses the docs-only gate. Requiring `run` to *contain* `make test` also accepts an echo or commented command. The test does not check `runs-on: ${{ matrix.os }}` or that the classifier produces the referenced output (`27-03-PLAN.md:170-175`). These gaps undermine the stronger claim that the structure proves macOS coverage and docs-only gating.

### Suggestions

Pin the actual gate expression and matrix-to-runner linkage, and check that `make test` is an executable command rather than merely a substring. Add negative fixtures for an inverted gate and a non-executing `make test`.

### Risk assessment

**Medium:** the planned prose matches current CI, but future CI drift could leave the guard green while the claim becomes false.

## 27-04

### Summary

Records the after verdict, moves the shared parser, and compares scores with rubric and docs-only guards.

### Strengths and cycle 1 dispositions

- **Finding 3 — RESOLVED for destructive cleanup:** Each judge attempt uses a snapshot and explicitly reverts nothing; commits use pathspecs (`27-04-PLAN.md:78-84`). The untracked-content blind spot described under 27-01 also applies here.
- **Finding 7 — RESOLVED:** Both verdicts must match the rubric maxima, and the regression test includes a mismatched-maxima fixture (`27-04-PLAN.md:193-204`). This closes a real gap: the existing parser checks matching dimension keys and arithmetic, not prescribed maxima (`tests/test_catalog_audit_skill.py:293-310`).
- **Finding 8 — RESOLVED:** The guard requires after-verdict history and checks both files against `HEAD` (`27-04-PLAN.md:133-137`).
- The proposed helper move accounts for the parser’s dependent constants and the old test’s remaining `_verdict` caller (`27-04-PLAN.md:148-163`; `tests/test_catalog_audit_skill.py:251-274, 318-336`). The described verdict test has four named cases, matching its minimum count (`27-04-PLAN.md:200-210, 227-228`).

### Concerns

- **HIGH — Finding 1: STILL OPEN.** The after-judge loop uses the same unsupported objective-level pre-dispatch mechanism (`27-04-PLAN.md:76-85`). The installed delegation path passes that objective to the external executor; it does not execute the orchestrator-only steps before launching it (`execute-phase.md:437-440`). Task 1 then fails closed because the after verdict is missing.

- **MEDIUM — NEW: the same hard-coded checkout can invalidate the after comparison.** Plan 04 reuses the verbatim prompt from 27-01 (`27-04-PLAN.md:79`), including its absolute repository path (`27-01-PLAN.md:76`). In an isolated worktree, the after score can describe a different copy of the skill from the one being committed.

- **LOW — NEW: the after gate does not establish which skill bytes were judged.** The procedure records a branch and `HEAD` but does not require `SKILL.md` to be clean before the judge or compare it with the judged commit (`27-04-PLAN.md:77-84, 133-137`). A dirty skill can be judged while the after file is committed alone. Historical verdicts need not be invalidated by later phases, but the phase’s own after verdict should identify the actual judged bytes.

### Suggestions

Use the same supported handoff and active-root correction as 27-01. At judgment time, require a clean skill or record and verify its content hash; this need not impose a permanent hash pin on later onboarding phases.

### Risk assessment

**High:** the after verdict is required to close SKILL-06, but the standard dispatch path does not produce it. The parser move and maxima comparison are otherwise well specified.

---

**Scope and limitations:** This was a read-only source review at `c33b8658`; I did not execute the plans, run the full test suite, invoke skill-judge, or test the workflows end to end. The deferred limitation that status labels do not prove the truth of `written:` claims remains a judgment risk, as the plans acknowledge.

---

## Consensus Summary

One grounded reviewer ran (`opencode-referee-one`; its section carries `file:line` evidence and no discount marker), so there are no cross-reviewer "Agreed" items. The summary below is the review agent's synthesis after checking the reviewer's findings against source and re-judging every cycle 1 finding against the current plans.

### Agreed Strengths

Single reviewer; no corroboration is possible. Confirmed independently against source:

- Eight of the ten cycle 1 findings are cleanly resolved in the plan text, and the two plan-level count claims still add up: `-k table` 5 (Task 2) then 14 (Task 3), `-k rules` 5 then 14, `-k conflicts` 3, `-k macos_testing` 3, `-k macos_apps` 4, `-k verdict` 4, and 58 `assert` lines in `tests/test_catalog_audit_skill.py` (`grep -c assert` prints 58 at HEAD).
- The new CI-structure test passes on HEAD's workflow: a dry run with `yaml.safe_load` of `.github/workflows/ci.yml` gives matrix `['ubuntu-latest', 'macos-latest']`, `runs-on: ${{ matrix.os }}`, one step named `Test` (index after `Classify the change`, whose `id` is `scope`), `if: steps.scope.outputs.full != 'false'` and `make test` in `run`. The house pattern `cast(dict[Any, Any], yaml.safe_load(...))` is at `tests/test_verify_registry_workflow.py:14`, and `pyyaml` / `types-pyyaml` are in `pyproject.toml:29-30`.
- The no-row / with-row fixture works: the real registry text plus the `demo-term` block loads and returns the eight ids plus `demo-term` (run with `.venv/bin/python -I` against a scratch copy).
- All four plans pass `gsd-tools verify.plan-structure` (`valid: true`, no errors or warnings); the native `auto` / `tracer` task types are the ones `execute-plan.md:229-234` defines.

### Agreed Concerns

None (single reviewer). See "HIGH verification" for the reviewer's two HIGH items and how each was counted.

### Divergent Views

None (single reviewer).

---

## HIGH verification (review agent, against repo source)

The reviewer raised 2 HIGH items (both are cycle 1 Finding 1, repeated for 27-01 and 27-04). Result: 0 counted as HIGH.

| # | Reviewer HIGH | Source check | Verdict |
|---|---------------|--------------|---------|
| H1 | 27-01: the pre-dispatch handoff is not implemented by the orchestrator | The mechanism claim is true: `.claude/gsd-core/workflows/execute-phase/detail/elaboration.md:54-99` (step 2.5) builds the prompt from `<objective>` and `<tasks>` and pipes it to `workflow.cross_ai_command` with no hook for objective-defined orchestrator steps; `execute-phase.md:1089-1108` (`checkpoint_handling`) acts only when an executor returns a checkpoint; `bin/lib/phase.cjs:987-988` only sets `hasCheckpoints` for `autonomous: false`. Nothing in GSD runs the PRE-DISPATCH PREREQUISITE on its own. But it is not a HIGH: (a) the orchestrator that builds the cross-AI prompt (elaboration.md:85 "Extract `<objective>` and `<tasks>`") reads the very objective block that carries the prerequisite, and the goal prompt makes that session the orchestrator (`.planning/goals/2026-11-19-phases-27-...md:17`); (b) the cycle 1 fix this review recommended is exactly what the plan now does (native `type="auto"` verify gate, `autonomous: false`, executor prints `BLOCKED: 27-01 pre-dispatch prerequisite (before verdict) not done`, 27-01-PLAN.md:130-132); (c) the failure mode is a visible stop before any edit and one manual step (run the judge, commit the verdict, re-dispatch), never wrong output or data loss; (d) the plan records why `checkpoint:human-action` was rejected (an unattended run would stop, and the cross-AI path has no checkpoint protocol; 27-01-PLAN.md:318). | not counted; resolved by the cycle 1 mitigation, residual noted below |
| H2 | 27-04: the after-judge handoff has the same gap | Same evidence and same fail-closed design (27-04-PLAN.md:76-85, `BLOCKED: 27-04 pre-dispatch prerequisite (after verdict) not done` at :130). One extra execution fact the reviewer did not state: step 2.5 delegates only `ready` plans (`execute-phase.md:438`, `phase.cjs:987-1000` #4628), so 27-02..27-04 are not delegated in the first pass; the orchestrator re-dispatches per wave, and 27-04's prerequisite (step 1 requires 27-01..27-03 complete) naturally sits between wave 3 and wave 4. | not counted; same disposition as H1 |

No single-reviewer discount applies (the reviewer cited `file:line` throughout), so the consensus gate was not needed; the counting above is the review agent's own source-based severity call.

## Cycle 1 findings: disposition against the CURRENT plans

| # | Cycle 1 finding | Status now | Evidence |
|---|-----------------|------------|----------|
| 1 | `orchestrator-step` task type unsupported | RESOLVED (residual: nothing in GSD enforces the prerequisite; fail-closed gate only) | 27-01-PLAN.md:15,73-88,122-149; 27-04-PLAN.md:15,76-85,120-146; `verify.plan-structure` valid; see H1/H2 |
| 2 | exact-eight row count | RESOLVED | 27-01-PLAN.md:166-168 (`ids` non-empty, `table_drift == []`), `with-row` case; dry run of the fixture loads (above) |
| 3 | "revert anything else in git status" | RESOLVED for the destructive part (snapshot diff, nothing reverted, trailing pathspec); a content blind spot in the new snapshot is NEW finding N1 | 27-01-PLAN.md:75-77,87; 27-04-PLAN.md:78-84 |
| 4 | "every terminal and IDE entry" vs `n/a` cells; VS Code (d) | RESOLVED | 27-02-PLAN.md:143,147 ("that has the capability", "`n/a` with the reason"); 27-01-PLAN.md:195 (vscode (d) `unverified`, (b)/(c) `n/a` for SKILL-07) |
| 5 | kitty example claimed as current | RESOLVED | 27-03-PLAN.md:136-137; `installer/terminal_shell.py:598` is the real alacritty line; item 1 must not contain "kitty" (27-03-PLAN.md:124) |
| 6 | `# Verified` example mixed methods | RESOLVED | 27-03-PLAN.md:232-241 (three separate blocks), test needs exactly three `# Verified` lines in step 9 (:219); SKILL.md step 9 has no `# Verified` line start today (grep) |
| 7 | rubric maxima not compared | RESOLVED | 27-04-PLAN.md:196,204 (`max` vs `dict(zip(DIMENSIONS, RUBRIC_MAX))`, mismatched-maxima fixture); early guard 27-01-PLAN.md:136 |
| 8 | `git ls-files --error-unmatch` accepts a staged file | RESOLVED | 27-01-PLAN.md:138; 27-04-PLAN.md:136 (`git log -1 --format=%h -- <file>` non-empty, `git diff --quiet HEAD`) |
| 9 | kitty config cell ignores XDG | RESOLVED | 27-01-PLAN.md:191 matches `installer/terminal_shell.py:151-157` |
| 10 | CI check greps loose strings | RESOLVED (structural, dry-run passes); a tightening is NEW finding N3 | 27-03-PLAN.md:170-175 |
| H3a | `bad_status_cells` proves label, not truth | accepted deferral, stated in T-27-03 | 27-01-PLAN.md:288 |

## Review-agent verification of the reviewer's NEW findings

- NEW MEDIUM (27-01 and 27-04), snapshot misses edits to already-untracked files: TRUE. `git status --porcelain=v1 --untracked-files=all` lists untracked paths only and `git diff HEAD --binary` covers tracked files only, so a changed byte inside the pre-existing untracked goals file leaves both snapshot parts equal (27-01-PLAN.md:75-77; 27-04-PLAN.md:78). Severity LOW: the judge is already forbidden to write, and the snapshot is a backstop, but the plan text claims "any delta stops the run" (must_haves, T-27-02, T-27-13). Actionable (N1).
- NEW MEDIUM (27-01/27-04), judge pinned to the main checkout, not a worktree: NOT COUNTED. The cross-AI path runs "from the project root" (elaboration.md:96, step 3), the orchestrator runs the judge before dispatch from that same checkout and commits on the phase branch (`git worktree list` shows one worktree, the phase branch), and the worktree gate applies to the normal-executor fallback only (`execute-phase.md:608-614`), whose worktree is forked from a HEAD that already holds the committed verdict and the clean skill. The judged bytes equal the committed bytes.
- NEW MEDIUM (27-03), CI check accepts an inverted gate or a non-executing `make test`, and does not link `runs-on` to the matrix: PARTLY TRUE. `if` is checked by `contains steps.scope.outputs.full`, so `== 'false'` would pass; `runs-on` is not checked, so a job with the matrix declared but a fixed runner would pass (HEAD: `runs-on: ${{ matrix.os }}`, `if: steps.scope.outputs.full != 'false'`, ci.yml:20,37,43). An echoed or commented `make test` is implausible after YAML parsing (comments are dropped; the step `run` is the shell text). Severity LOW; the cycle 1 finding (comment or other job keeps the strings green) is closed. Actionable but optional (N3).
- NEW LOW (27-04), the after gate does not establish which skill bytes were judged: TRUE. 27-04-PLAN.md:77-85 never asserts `git status --porcelain -- .claude/skills/tool-onboarding/` is empty before a dispatch (27-01-PLAN.md:74 does for the before verdict), and the `- Judge:` bullet records only branch and HEAD short sha. Actionable LOW (N2).

## Actionable Non-HIGH Concerns (PLAN.md change still needed)

1. LOW (N1), 27-01 PRE-DISPATCH steps 2 and 4, 27-04 steps 2 and 4, T-27-02, T-27-13, and the must_haves line that says "any delta": extend the snapshot command with a content hash of untracked files, for example `{ git status --porcelain=v1 --untracked-files=all; git diff HEAD --binary | sha256sum; git ls-files --others --exclude-standard -z | xargs -0 -r sha256sum; }`, or narrow the claim to "tracked changes and the list of untracked paths".
2. LOW (N2), 27-04 PRE-DISPATCH steps 1-2 and 6: before every judge dispatch require `git status --porcelain -- .claude/skills/tool-onboarding/` to print nothing, and record `git rev-parse HEAD:.claude/skills/tool-onboarding/SKILL.md` (the judged blob) in the `- Judge:` bullet of the after and ROUND files, so the after verdict names the bytes it scored.
3. LOW (N3), 27-03 Task 2 `test_macos_testing_matches_the_ci_workflow`: also assert `"matrix.os" in job["runs-on"]` and `"!= 'false'" in test_step["if"]` (the gate polarity), with a one-line note that these pin the linkage, not the whole expression.

Not counted (accepted, already declared by the plans): `bad_status_cells` checks the label, not the truth (H3a); `ASK_RE` and `option_as_alt_unnegated` are heuristics paired with the 27-04 skill-judge pass; the `a,b,c,d` order is now sorted; the after verdict is historical evidence. Residual risk of H1/H2 (LOW, informational): GSD has no hook that runs an objective-level prerequisite, so an orchestrator that dispatches without reading the objective sees the executor's `BLOCKED:` stop; the recovery is one manual step.

---

## Verification coverage

Source-grounding pass (`plan_review.source_grounding` is on; `plan_review.source_grounding_authority` is `grep`, the seam `gsd-tools drift-guard authority` answered `intel`, and the seam answer was used). The `intel` adapter analyzes JavaScript only, so every Python, TOML, YAML and Markdown symbol is UNCHECKABLE under that adapter (severity INFO, never a block). The review agent resolved them anyway by reading the files directly (grep-adapter semantics) and recorded them as VERIFIED with `file:line`. No symbol was MISSING; no hard block.

Symbols the plans declare under "Artifacts this phase produces" (new in this phase, not verified): `27-SKILLJUDGE-before.md`, `27-SKILLJUDGE-after.md`, `27-SKILLJUDGE-ROUND-{n}.md`, `tests/test_tool_onboarding_skill.py` and its symbols (`REPO_ROOT`, `SKILL`, `REGISTRY`, `TABLE_HEADING`, `ID_CELL_RE`, `STATUS_RE`, `_SEPARATOR_ROW_RE`, `_text`, `_step`, `_subsection`, `_fixture`, `table_rows`, `table_ids`, `registry_ids`, `table_drift`, `bad_status_cells`, `RULES_HEADING`, `EXTRAS_HEADING`, `ASK_RE`, `rule_items`, `ask_sentences`, `option_as_alt_unnegated`, `CONFLICTS_HEADING`, `MACOS_TESTING_HEADING`, `MACOS_APPS_HEADING`, `CI_WORKFLOW`, `_items`, `_verdict_doc`, `verdict_regressions`, `_phase_dir`), `tests/skill_verdicts.py` (`VERDICT_KEYS`, `GRADE_FLOORS`, `PASS_PERCENT`, `DIMENSIONS`, `RUBRIC_MAX`, `grade`, `parse_verdict`), the SKILL.md headings (`#### Closed per-terminal table`, `#### Terminal and IDE defaults`, `#### Extras are asked`, `#### Conflicts`, `#### Testing macOS behavior`, `#### macOS apps`, the renamed step 7 heading), the four new LEDGER keys plus the SKILL.md key, and the `TEST_READ` entry `.planning/*27-SKILLJUDGE-*`.

Pre-existing symbols, VERIFIED (read in this review):

| Kind | Symbol (plan line quoted) | Evidence |
|------|---------------------------|----------|
| file | `.claude/skills/tool-onboarding/SKILL.md` "268 lines ... byte-identical to 1bb31e00" (27-01-PLAN.md:115) | `wc -l` 268; `git diff --quiet 1bb31e00 HEAD -- <file>` exits 0 |
| file | `.claude/skills/catalog-audit/SKILL.md:80-81` heading quote (27-02-PLAN.md:142) | `:80` ends "... do not assume`. Its", `:81` starts "TUNE-04 rule"; `tests/test_catalog_audit_skill.py:83` `_STEP_RE` and the full-line check at :104-108 |
| function | `load_tools`, `Category.TERMINAL`/`EDITOR` (27-01-PLAN.md:161,183) | `installer/model.py:584`; returns exactly alacritty, herdr, jetbrains-toolbox, kitty, neovim, sublime, vscode, wezterm (re-run at HEAD) |
| function | `_kitty_config_path`, `_xdg_config_home` (27-01-PLAN.md:191) | `installer/terminal_shell.py:151-157` |
| function | vscode `terminal.integrated.defaultProfile.{linux,osx}` = zsh (27-01-PLAN.md:164,195) | `installer/agent_settings.py:742-749` |
| function | `_skill_section` (27-01-PLAN.md:159,179) | `tests/test_docs.py:318-324` |
| function/consts | `_parse_verdict`, `_grade`, `_verdict`, `_DIMENSIONS`, `_RUBRIC_MAX`, `_VERDICT_KEYS`, `_GRADE_FLOORS`, `_PASS_PERCENT`, `PHASE_DIR` (27-04-PLAN.md:152,160-162) | `tests/test_catalog_audit_skill.py:251-336`; `_parse_verdict(document, *, final)` signature matches the plan's `final=False` calls (:270-274); `_RUBRIC_MAX` unused by the parser (:293-310) |
| function | `_STEP_RE`, `_table_rows`, `_assert_all_in` (27-02/03) | `tests/test_catalog_audit_skill.py:82-101` |
| consts | `TEST_READ`, `is_docs_path` (27-04-PLAN.md:188,220) | `devtools/docs_only.py:20-35` (`fnmatchcase`, `.claude/*` and `tests/*` are test-read) |
| consts | `LEDGER`, `markdown_literals`, `test_the_rule_matrix` (27-01/04) | `tests/test_docs_only.py:25-45,85-88,191-260` |
| string | `alacritty: partial: you already bind` (27-03-PLAN.md:107,136) | `installer/terminal_shell.py:598` (f-string; also :560, :564, :768) |
| function | `startswith("partial:")` consumer (27-03-PLAN.md:104,129) | `installer/version_status.py:1598` |
| function | `_cask` with `--appdir={applications_dir()}`, `applications_dir()` (27-03-PLAN.md:100,228) | `installer/executors.py:699-704`, `installer/locations.py:89-91` |
| params | `app` and `cask` params (27-03-PLAN.md:101) | `installer/model.py:96,105` (as read in cycle 1; unchanged) |
| string | kitty macOS `script` `bin_dir = "/Applications/kitty.app/Contents/MacOS"` (27-03-PLAN.md:103,231) | `installer/registry.toml:3047` |
| CI | job `validate-and-test`, matrix, `Classify the change` (`id: scope`), gated `Test` step (27-03-PLAN.md:105,170-175) | `.github/workflows/ci.yml:15-50`; parsed dry run agrees |
| pattern | `cast(dict[Any, Any], yaml.safe_load(...))` (27-03-PLAN.md:106,163) | `tests/test_verify_registry_workflow.py:4-14` |
| dependency | `pyyaml`, `types-pyyaml` (27-03-PLAN.md:106) | `pyproject.toml:29-30` |
| alacritty Linux-only (27-01-PLAN.md:193) | methods are cargo_distrobox/dnf/apt/pacman only | `installer/registry.toml` alacritty block |
| GSD | `orchestrator-step` absent; `type="auto"`/`tracer`/`checkpoint:*` handling; cross-AI step 2.5; `ready` gate | `.claude/gsd-core/workflows/execute-plan.md:229-234`, `execute-phase/detail/elaboration.md:54-99`, `bin/lib/phase.cjs:987-1000` |
| id | commits `1bb31e00`, `c33b8658`, `b7c2c37e` | resolve (`git log`, `git diff`) |
| lint scope | vulture covers `installer` and `devtools` only; ruff selects E,F,I,B,UP,SIM; pyright strict covers tests (27-04-PLAN.md:93) | `pyproject.toml:35-45,62-64` |

Not checked and why (UNCHECKABLE, INFO only):

- Signatures and behaviour of the not-yet-written test helpers (`ASK_RE` on the rewritten skill, `option_as_alt_unnegated` over the new table cells, `ID_CELL_RE`, the pyright strict result of the aliased private imports in `tests/test_catalog_audit_skill.py`) cannot be run before execution; they were only reasoned about from plan text.
- `~/.claude/skills/skill-judge/SKILL.md` and the judge subagent's behaviour live in the real user home that this run must not touch; the rubric version 4 and maxima `(20,15,15,15,15,15,15,15)` were confirmed only from `tests/test_catalog_audit_skill.py:270-274` and the cycle 1 note on `24.3-SKILLJUDGE-FINAL.md`.
- The vendor-doc claim for VS Code `terminal.integrated.splitCwd` (27-01-PLAN.md:195) is an external fact, not checked here; the plan stores it as `unverified`.
- Neither the full test suite nor any macOS behaviour was run; no code or plan file was edited.

Cross-artifact fact-drift pass (advisory; contributes to neither count):

- Phase status: `gsd-tools drift-guard phase-status --phase 27` returned `lag` (STATE.md "Ready to execute", ROADMAP.md "Not started", authority STATE.md): two non-terminal statuses one lifecycle step apart. Not a finding.
- ROADMAP Success Criteria vs PLAN `must_haves.truths`: criteria 1-5 map onto 27-02 (rules), 27-01 (closed table, coverage test, before verdict), 27-03 (conflict, macOS apps, macOS testing) and 27-04 (after verdict, comparison). ROADMAP.md:84,93 now says "pre-dispatch orchestrator prerequisite" and matches the plans; no contradiction. The plans add truths beyond the roadmap, which is sanctioned.
- Requirement IDs: ROADMAP `**Requirements:** SKILL-01..06` vs PLAN `requirements:` (27-01 SKILL-02 and SKILL-06, 27-02 SKILL-01, 27-03 SKILL-03/04/05, 27-04 SKILL-06) vs REQUIREMENTS.md traceability rows 114-119: consistent. The roadmap plan line for 27-01 now also names SKILL-06; consistent with the plan.
- CONTEXT.md `Decisions` vs PLAN usage: D-06 (fresh read-only judge, before never re-run), D-08 (ROUND files), D-10 (`.dmg` and cask CLI-link gaps, matches REQUIREMENTS.md:16 amendment), D-12, D-13, D-15, D-16 all agree with the plans. REQUIREMENTS KEYS-03 (clear is Phase 28) agrees with rule (c) "planned for phase 28"; REQUIREMENTS.md:123 puts KEYS-04 (new tab in the current directory) in Phase 28 too, while rule (d) is stated as a rule without a phase tag; wording difference only, not drift.
- 27-VALIDATION.md rows (changed in c33b8658) agree with the plans' test commands and thresholds; no contradiction.
- Skipped axes: none (STATE.md, ROADMAP.md, CONTEXT.md, SPEC.md and REQUIREMENTS.md all present).
