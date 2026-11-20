---
phase: 27
reviewers: [opencode-referee-one]
reviewed_at: 2026-11-20T04:12:56Z
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

## Lane Log (convergence cycle 3, final cycle, plans at d93b86d0)

- Default lane `opencode-referee-one` (`router-env/my-referee-one`, opencode CLI, owner-required first lane): probe succeeded (`opencode run -m router-env/my-referee-one "Reply with the single word OK."` returned `OK`, exit 0, stdin closed, under `timeout 120`). The review ran through `gsd-tools query review-lane invoke --slug opencode --model router-env/my-referee-one --as opencode-referee-one --json` with stdin closed (`< /dev/null`), under `timeout 2700`, in the background. It produced a full review (four plan sections, no stub, empty `.err`, result JSON `ok: true`, `stubbed: false`, model source `pinned`) in under two minutes. A 207 KB prompt (PROJECT, roadmap, requirements, CONTEXT, VALIDATION, the four plans with line numbers, and the cycle 2 finding list) was sent whole; no split was needed.
- No lane failed, so the failover lanes `opencode-referee-two` and `opencode-referee-three` were not used. Failures recorded: none.
- Exactly one reviewer ran, so the consensus gate does not engage. The reviewer's section carries `file:line` evidence and no discount marker. Per the owner rule each claim was checked against repo source before it was counted (tables below).

## OpenCode Review (opencode-referee-one)

Using the spec-review checklist to assess the current plans against the repository, with particular attention to the cycle 2 fixes and any regressions they introduced. This review is read-only.
# Phase 27 plan review

**Disposition:** Cycle 2's N2 is resolved. N1 and N3 are **partially resolved**: their ordinary cases are addressed, but the revised checks retain specific false-negative cases. One additional low-severity validation-map overclaim remains. No new HIGH findings.

For brevity, plan and validation citations below are relative to `.planning/phases/27-tool-onboarding-skill-terminal-defaults-as-rules/`.

## 27-01

### Summary

The plan records the before verdict against a clean, pre-rewrite skill and adds the registry-backed table. Its revised snapshot covers the ordinary already-untracked-file edit that N1 identified.

### Cycle 2 finding dispositions

- **N1 — Partially resolved.** `27-01-PLAN.md:75-78` hashes untracked files before and after the judge, so a normal content change is detected. The filename and failure cases below remain open.
- **N2, before-verdict symmetry — Resolved.** `27-01-PLAN.md:75,82,139,146` records and checks the baseline blob. I verified that `HEAD`, `d93b86d0`, and `1bb31e00` all resolve this skill to `8fda04a7a1af006f1dcbdda82a8e759245e5f872`; the hard-coded value is limited to the **before** verdict.
- **H1 — Accepted residual.** The prerequisite is described at `27-01-PLAN.md:74`, and the executor stops at `:131-139` if it was not completed. I found no new evidence warranting promotion of the declared manual handoff to HIGH.

### Concerns

- **LOW — Snapshot hashing can omit a special-named untracked file.** `27-01-PLAN.md:76` passes root-relative filenames directly to `sha256sum`. An untracked file named `-` is interpreted as standard input, not as that file; a leading-option filename such as `--help` can be interpreted as an option. I reproduced both command behaviors. In addition, the plan compares snapshot output without explicitly requiring every pipeline component to succeed, so repeated hash failures could yield matching incomplete snapshots. The same issue applies to `27-04-PLAN.md:79-81`.

### Suggestions

Prefix each filename with `./` or use another filename-safe hashing method, and require successful completion of every snapshot component before comparing snapshots. Preserve NUL-delimited input.

### Risk Assessment

Low likelihood, but a false match would weaken the stated read-only check. The empty-list case is handled by `xargs -r`; batching a large list preserves input order, and Git's untracked listing is deterministic for an unchanged tree. Ordinary whitespace, newline, and backslash filenames are carried safely into `xargs` by `-z`/`-0`; option-like names and `-` are the exception identified above.

## 27-02

### Summary

The plan renames step 7, updates the sibling skill's heading reference, separates the four rules, and retains questions for extras (`27-02-PLAN.md:126-155,186-220`). The current skill still contains the old question-oriented text at `.claude/skills/tool-onboarding/SKILL.md:178-195`, so the planned rewrite addresses the stated starting point.

### Cycle 2 finding dispositions

No cycle 2 finding was assigned directly to this plan.

### Concerns

None newly introduced by the round 2 revision.

### Suggestions

None.

### Risk Assessment

Low for this review's scope. The text-detection heuristics' limitations remain explicitly declared at `27-02-PLAN.md:281-285`.

## 27-03

### Summary

The revised CI test checks the actual named job, matrix, runner field, classifier ordering, and Test-step condition. The current workflow has the expected matrix-driven runner and gate at `.github/workflows/ci.yml:15-22,32-50`.

### Cycle 2 finding dispositions

- **N3 — Partially resolved.** The exact fixed-runner and `== 'false'` mutations now fail under the specified checks (`27-03-PLAN.md:170-182`). However, the checks still match substrings rather than the operative expressions: an inverted condition such as `!(steps.scope.outputs.full != 'false')` contains both required substrings and would pass. A runner expression can similarly mention `matrix.os` while resolving both matrix entries to Ubuntu. Thus the broader claims that the test proves polarity and runner linkage remain stronger than the check.
- The `-k macos_testing` threshold of **five** is consistent: three ordinary tests and two parameterized mutation cases are specified at `27-03-PLAN.md:166-183,197-198`.

### Concerns

- **LOW — Expression checks still admit an inverted gate or non-macOS runner.** See N3 above. The real workflow is correct today; this is a regression-test gap, not evidence that current CI is broken.

### Suggestions

Check the expected expressions as normalized whole values, or add mutations for a negated condition and a matrix-referencing expression that always selects Ubuntu.

### Risk Assessment

Low: the revised test catches the two named mutations, but should not be treated as proof of all logically equivalent or adversarial workflow changes.

## 27-04

### Summary

Each after-judge attempt now requires a clean skill, records that attempt's blob, and checks the final verdict's blob against the skill at the verdict commit (`27-04-PLAN.md:79-85,135-145`). Unlike the before check, the after check correctly derives its hash dynamically, allowing the edits in 27-01 through 27-03 and any fix rounds.

### Cycle 2 finding dispositions

- **N1 — Partially resolved.** The ordinary untracked-content gap is closed at `27-04-PLAN.md:79-81`; the shared special-filename and error-handling gap is counted once under 27-01.
- **N2 — Resolved.** The clean precondition, per-attempt blob record, and final commit/blob comparison are specified at `27-04-PLAN.md:79,83-84,137`. There is no inappropriate hard-coded baseline hash for the rewritten skill.
- **H2 — Accepted residual.** The pre-dispatch step and fail-closed executor gate remain at `27-04-PLAN.md:77,129-137`; no new evidence changes the prior assessment.

### Concerns

- **LOW — The validation map conflates automated verdict checks with judge-run provenance.** `27-VALIDATION.md:50` associates the `-k verdict` unit command with clean-before-dispatch checks, snapshot comparisons, and judged-blob provenance. The planned verdict tests at `27-04-PLAN.md:195-213` check file contents and score comparison; the snapshot and clean-skill steps are orchestrator procedures at `:79-81`, and the final blob check is a separate Task 1 command at `:137`. The SKILL-05 row at `27-VALIDATION.md:49` otherwise agrees with 27-03, subject to the N3 limitation above.

### Suggestions

Split the SKILL-06 validation row into the automated verdict test, the Task 1 commit/blob checks, and the orchestrator-observed clean-tree/snapshot procedure. Do not imply pytest proves the latter.

### Risk Assessment

Low: the final verdict's recorded blob is checked once against its commit, while later skill edits remain possible. Provenance still depends on the declared orchestrator procedure.

### Status: Issues Found — 3 LOW concerns, including the two partially resolved cycle 2 findings

**Not checked:** The phase was not executed and the full test suite was not run; this was a read-only plan review. **Residual risk:** the judge handoffs remain manual and fail closed if omitted.

---

## Consensus Summary

One grounded reviewer ran (`opencode-referee-one`; its section carries `file:line` evidence and no discount marker), so there are no cross-reviewer "Agreed" items. The summary below is the review agent's synthesis after checking each reviewer claim against source.

### Agreed Strengths

Single reviewer; no corroboration is possible. Confirmed independently against source by the review agent:

- Cycle 2 N2 is fully resolved. `git rev-parse 1bb31e00:.claude/skills/tool-onboarding/SKILL.md` and `git rev-parse HEAD:.claude/skills/tool-onboarding/SKILL.md` both print `8fda04a7a1af006f1dcbdda82a8e759245e5f872`, `git diff --quiet 1bb31e00 HEAD -- <SKILL.md>` exits 0, `git log -1 --format=%h -- <SKILL.md>` prints `1bb31e00`, and `git status --porcelain -- .claude/skills/tool-onboarding/` prints nothing (HEAD is `d93b86d0`). The 27-04 side carries no hard-coded blob: its acceptance and verify derive it with `git rev-parse "$c:..."` (27-04-PLAN.md:137,144-145).
- The `ci_workflow_problems` function behaves as the plan states. A dry run with `.venv/bin/python -I` (a scratch re-implementation of the plan's check list against the real `.github/workflows/ci.yml`) printed `[]` for the real workflow, exactly `['runs-on does not use matrix.os']` for the fixed-runner mutation and exactly `["Test step if is not gated by != 'false'"]` for the inverted-gate mutation.
- The `-k macos_testing` count of 5 is exact: `test_macos_testing_three_clauses` (1), `test_macos_testing_matches_the_ci_workflow` (1), `test_macos_testing_ci_check_refuses_mutations[fixed-runner|inverted-gate]` (2), `test_macos_testing_sits_in_step_7_and_is_ascii` (1) (27-03-PLAN.md:166-183,197-198,300). The 58 `assert` lines in `tests/test_catalog_audit_skill.py` still hold (`grep -c assert` prints 58).
- The snapshot command works on the current tree: it prints the `M .planning/state.json` and untracked goals-file status lines, one `sha256` of the `git diff HEAD --binary` stream, and one `sha256sum` line for the untracked goals file; the empty-untracked case is covered by `xargs -r`.

### Agreed Concerns

None (single reviewer). See "HIGH verification" and "Cycle 2 findings: disposition" for how each reviewer finding was counted.

### Divergent Views

None (single reviewer).

---

## HIGH verification (review agent, against repo source)

The reviewer raised no HIGH this cycle. Result: 0 HIGH counted. The two cycle 2 HIGH items (H1 in 27-01, H2 in 27-04: nothing in GSD runs an objective-level pre-dispatch prerequisite) were counted as 0 in cycle 2 for the reasons recorded there (the orchestrator that builds the cross-AI prompt reads the objective block; the plan's native `auto` Task 1 gate fails closed with a visible `BLOCKED:` stop before any edit; the recovery is one manual step; `checkpoint:human-action` was rejected on the record). The reviewer re-read them this cycle as "Accepted residual" and found no new evidence; the review agent found none either (the plan text at 27-01-PLAN.md:73-88 and 27-04-PLAN.md:76-85 is unchanged in substance, only the snapshot and blob steps were extended). Not counted.

## Cycle 2 findings: disposition against the CURRENT plans

| # | Cycle 2 finding | Status now | Evidence |
|---|-----------------|------------|----------|
| N1 | Snapshot misses content edits to already-untracked files | PARTIALLY RESOLVED (ordinary case closed; a filename edge case remains, see New 1) | 27-01-PLAN.md:25 (must_haves), :76 (step 2, the `xargs -0 -r sha256sum` part), :77 (step 4 reuses it), :289 (T-27-02); 27-04-PLAN.md:27, :79 (step 2), :260 (T-27-13). Dry run: an edit inside an untracked file changes the hash line |
| N2 | 27-04 clean-skill precondition and SKILL.md blob record | RESOLVED | 27-04-PLAN.md:28 (truth), :79 (clean check before every dispatch, blob per attempt), :83-84 (after and ROUND `- Judge:` name the blob), :137 (verify: blob at the verdict commit), :144-145 (acceptance); 27-01-PLAN.md:75,82,139,146 for the before side (blob `8fda04a7...` verified above) |
| N3 | 27-03 CI test accepted an inverted gate and did not link `runs-on` to the matrix | RESOLVED for the two cases named; the plan itself says the checks "pin the runner linkage and the gate polarity, not the whole expressions" (27-03-PLAN.md:178), which is an explicit, accepted limit | 27-03-PLAN.md:23,44,170-182,198,284; dry run above (real `[]`, each mutation exactly its own message) |
| H1/H2 | Pre-dispatch handoff not implemented by the GSD orchestrator | Accepted declared residual (not counted), unchanged | 27-01-PLAN.md:73-88,122-149; 27-04-PLAN.md:76-85,120-146 |

## Review-agent verification of the reviewer's findings this cycle

- New 1, LOW, snapshot hashing breaks on option-like or `-` filenames and does not require every pipeline part to succeed (27-01-PLAN.md:76, 27-04-PLAN.md:79): TRUE, reproduced here in a scratch repo. With untracked files named `-` and `--help` at the repository root, `git ls-files --others --exclude-standard -z | xargs -0 -r sha256sum` printed the `sha256sum` usage text (option parsing) instead of hash lines, and `-` alone reads standard input. The plan runs the command in a plain `{ ...; }` group whose exit status nothing checks, so two failed snapshots can be equal and incomplete. Likelihood is very low (an untracked repository-root file named `-` or starting with `--`), and the failure is a missed read-only backstop, never data loss. Actionable LOW, cheap to fix: give the hashing step `./`-prefixed names (for example `git ls-files --others --exclude-standard -z | sed -z 's|^|./|' | xargs -0 -r sha256sum`) and say that any non-empty stderr from the snapshot command stops the run.
- Reviewer's N3 residual (a negated expression such as `!(steps.scope.outputs.full != 'false')`, or a `runs-on` expression that mentions `matrix.os` but resolves both entries to Ubuntu, would pass): TRUE as a logic statement, but not counted. The plan states the limit in the test's own description ("pin the runner linkage and the gate polarity, not the whole expressions", 27-03-PLAN.md:178), the real file is correct today, and the two realistic regressions (fixed runner, `== 'false'`) are covered by fixtures. This is an explicit, accepted limit rather than an overclaim; the truths text at 27-03-PLAN.md:23 ("with the polarity `!= 'false'`") reads as the substring check the behavior section defines. Not counted.
- Reviewer's 27-04 LOW, 27-VALIDATION.md:50 conflates the `-k verdict` unit command with orchestrator provenance procedures: TRUE as a wording observation about a validation-map row, but NOT COUNTED. The row's "Secure Behavior" column lists the whole requirement's behavior while its command column lists only the pytest part; the orchestrator steps and the blob check are covered by the plans' own Task 1 verify commands (27-01-PLAN.md:139, 27-04-PLAN.md:137) and objective steps, which the executor and orchestrator read. 27-VALIDATION.md is not an input the executor runs, so nothing is invisible to execution. Optional tidy-up if the planner touches the row again.

## Actionable Non-HIGH Concerns (PLAN.md change still needed)

1. LOW (N1 residual), 27-01-PLAN.md objective steps 2 and 4 (:76-77) and 27-04-PLAN.md objective steps 2 and 4 (:79-81): replace the untracked-hash part of the snapshot with a filename-safe form (`./`-prefixed names, for example `git ls-files --others --exclude-standard -z | sed -z 's|^|./|' | xargs -0 -r sha256sum`) and state that any stderr output from the snapshot command stops the run, so two failed snapshots cannot compare equal. T-27-02 (27-01-PLAN.md:289), T-27-13 (27-04-PLAN.md:260) and the must_haves line at 27-04-PLAN.md:27 quote the command and need the same wording.

Not counted (accepted, already declared by the plans): the N3 expression-level limit; the VALIDATION row wording; `bad_status_cells` checks the label, not the truth; `ASK_RE` and `option_as_alt_unnegated` are heuristics paired with the 27-04 skill-judge pass; the after verdict is historical evidence; the judge handoff is a manual, fail-closed orchestrator step (H1/H2, informational).

---

## Verification coverage

Source-grounding pass (`plan_review.source_grounding` is on; the seam `gsd-tools drift-guard authority --raw` answered `intel`, and the seam answer was used; `drift-guard severity --status UNCHECKABLE --authority intel` returned `INFO`, `hardBlock: false`). The `intel` adapter analyzes JavaScript only, so every Python, TOML, YAML, Markdown and git symbol is UNCHECKABLE under that adapter (INFO, never a block). The review agent resolved them anyway by reading files and running read-only git commands (grep-adapter semantics) and recorded them as VERIFIED with `file:line` or command output. No symbol was MISSING; no hard block.

Symbols the plans declare under "Artifacts this phase produces" (new in this phase, not verified): `27-SKILLJUDGE-before.md`, `27-SKILLJUDGE-after.md`, `27-SKILLJUDGE-ROUND-{n}.md`, `27-01-tree-before.txt` and `27-01-tree-after.txt`, `27-04-tree-before-{k}.txt` and `27-04-tree-after-{k}.txt` (scratchpad files outside the repository), `tests/test_tool_onboarding_skill.py` and its symbols (including `CI_WORKFLOW`, `_ci_workflow`, `ci_workflow_problems`, the cases `fixed-runner` and `inverted-gate`, and the tests `test_macos_testing_three_clauses`, `test_macos_testing_matches_the_ci_workflow`, `test_macos_testing_ci_check_refuses_mutations`, `test_macos_testing_sits_in_step_7_and_is_ascii`), `tests/skill_verdicts.py` (`VERDICT_KEYS`, `GRADE_FLOORS`, `PASS_PERCENT`, `DIMENSIONS`, `RUBRIC_MAX`, `grade`, `parse_verdict`), the new SKILL.md headings, the four new LEDGER keys plus the SKILL.md key, and the `TEST_READ` entry `.planning/*27-SKILLJUDGE-*`.

Pre-existing symbols read or run in this cycle, all VERIFIED:

| Kind | Symbol (plan line quoted) | Evidence |
|------|---------------------------|----------|
| git blob | "today `8fda04a7a1af006f1dcbdda82a8e759245e5f872`, the 1bb31e00 blob" (27-01-PLAN.md:75; :146) | `git rev-parse 1bb31e00:.claude/skills/tool-onboarding/SKILL.md` and `HEAD:...` both print that hash |
| git | `git diff --quiet 1bb31e00 HEAD -- .claude/skills/tool-onboarding/SKILL.md` exits 0 (27-01-PLAN.md:75) | exit 0; `git log -1 --format=%h -- <file>` prints `1bb31e00`; `git status --porcelain -- .claude/skills/tool-onboarding/` prints nothing |
| command | snapshot `{ git status --porcelain=v1 --untracked-files=all; git diff HEAD --binary \| sha256sum; git ls-files --others --exclude-standard -z \| xargs -0 -r sha256sum; }` (27-01-PLAN.md:76; 27-04-PLAN.md:79) | run at the repository root: two status lines, one diff hash, one untracked-file hash; the `-`/`--help` filename edge case reproduced in a scratch repo (New 1) |
| CI | job `validate-and-test`, `runs-on: ${{ matrix.os }}`, `matrix.os: [ubuntu-latest, macos-latest]`, step `Classify the change` (`id: scope`), step `Test` with `if: steps.scope.outputs.full != 'false'` and `run` containing `make test` (27-03-PLAN.md:105,170-175) | `.github/workflows/ci.yml:15-22,32-50`; scratch dry run of the plan's `ci_workflow_problems` logic gives `[]`, and each mutation exactly its own message |
| count | `tests/test_catalog_audit_skill.py` has 58 `assert` lines (27-04-PLAN.md:~104) | `grep -c assert` prints 58 |
| count | `-k macos_testing` yields 5 cases (27-03-PLAN.md:198) | enumerated from the plan's test list (:166-183,300): 1 + 1 + 2 + 1 |
| function/consts | `_parse_verdict`, `_DIMENSIONS`, `_RUBRIC_MAX`, `_grade` (27-01-PLAN.md:153; 27-04-PLAN.md:148-163) | `tests/test_catalog_audit_skill.py:251-336` (read in cycle 2; file unchanged since) |
| GSD | `orchestrator-step` absent; cross-AI step 2.5; `ready` gate | `.claude/gsd-core/workflows/execute-phase/detail/elaboration.md:54-99`, `bin/lib/phase.cjs:987-1000` (read in cycle 2; GSD tree unchanged) |
| id | commits `d93b86d0` (HEAD), `c33b8658`, `893ba95b`, `1bb31e00` | resolve in `git log` / `git diff c33b8658 d93b86d0 --stat` (five planning files changed: plans 01, 03, 04, REVIEWS, VALIDATION) |
| dependency | `pyyaml`, `types-pyyaml`; cast pattern in `tests/test_verify_registry_workflow.py:14` | `pyproject.toml:29-30` and the test file (cycle 2); `.venv/bin/python -I` imports `yaml` |

Not checked and why (UNCHECKABLE, INFO only):

- Signatures and behaviour of the not-yet-written test helpers (`ci_workflow_problems` as real pytest code under pyright strict, `ASK_RE`, `option_as_alt_unnegated`, `ID_CELL_RE`) cannot be run before execution; the dry run above used a scratch re-implementation of the plan's check list, not the future test module.
- `~/.claude/skills/skill-judge/SKILL.md` and the judge subagent's behaviour live in the real user home that this run must not touch; the rubric version 4 and maxima `(20,15,15,15,15,15,15,15)` were confirmed only from `tests/test_catalog_audit_skill.py:270-274`.
- macOS `xargs`/`sha256sum` availability for the snapshot command (the orchestrator runs on this Linux host; macOS runs are deferred to the owner).
- Neither the full test suite nor any macOS behaviour was run; no code or plan file was edited.

Cross-artifact fact-drift pass (advisory; contributes to neither count):

- Phase status: `gsd-tools drift-guard phase-status --phase 27` returned `lag` (STATE.md "Ready to execute", ROADMAP.md "Not started", authority STATE.md): two non-terminal statuses one lifecycle step apart. Not a finding.
- ROADMAP Success Criteria vs PLAN `must_haves.truths`: unchanged from cycle 2; the round 2 edit only added snapshot, blob and CI-check detail inside truths already tied to criteria 1-5 (27-02 rules, 27-01 closed table and before verdict, 27-03 conflict, macOS apps and macOS testing, 27-04 after verdict and comparison). Plans add truths beyond the roadmap, which is sanctioned. No contradiction.
- Requirement IDs: ROADMAP `**Requirements:** SKILL-01..06` vs PLAN `requirements:` frontmatter vs REQUIREMENTS.md traceability: unchanged and consistent.
- CONTEXT.md `Decisions` vs PLAN usage: D-06 (fresh read-only judge, before never re-run), D-08 (ROUND files), D-15 (macOS testing rule: golden-file test on both OSes, CI covers file paths, real-Mac UAT deferred) agree with the plans. No contradiction.
- 27-VALIDATION.md rows (changed in d93b86d0): the SKILL-05 row (:49) now names `runs-on` using `matrix.os`, the `!= 'false'` gate and the two mutations, and the `-k macos_testing` command, which agrees with 27-03-PLAN.md:23,198; the SKILL-06 row (:50) agrees with the plans' snapshot and blob wording (its wording-level overclaim is noted above, not counted). No contradiction.
- Skipped axes: none (STATE.md, ROADMAP.md, CONTEXT.md, SPEC.md and REQUIREMENTS.md all present).
