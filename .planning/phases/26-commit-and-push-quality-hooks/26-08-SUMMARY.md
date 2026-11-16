---
phase: 26-commit-and-push-quality-hooks
plan: "08"
subsystem: docs
tags: [hooks, quality-gates, push-gate, branch-protection, ci, documentation]

# Dependency graph
requires:
  - phase: 26-commit-and-push-quality-hooks
    provides: "the six gate targets, the push gate with GATE_READ_PATHSPECS, the hook installer and the CI/docs-only wiring from plans 26-01 to 26-07 that these docs describe"
provides:
  - "a gate/target/stage table and measured commit, push and CI timings in AGENTS.md and .claude/dev-environment.md"
  - "the push gate's five refusals and a placeholder-free, guarded edit-recovery block"
  - "the branch -> green CI -> fast-forward path to main and a guarded escape hatch that always restores enforce_admins"
  - "stale validate wording removed from every rule doc, plus the D-14 outside-tools todo"
affects: [26-09, branch-protection, contributor-docs]

# Actuals
actuals:
  tokens: 6550
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "doc pins in tests/test_docs.py that assert exact phrases and code-block structure"
    - "a single guarded shell line `git apply --check \"$patch\" && git apply \"$patch\"` so a failed dry run never applies"
    - "every mutating escape-hatch line carries its own `|| echo` guard so the read-back always runs"

key-files:
  created:
    - .planning/todos/pending/2026-11-16-adopt-the-branch-ci-main-flow-in-outside-tools.md
  modified:
    - .claude/dev-environment.md
    - .claude/git-workflow.md
    - AGENTS.md
    - .claude/python-tooling.md
    - README.md
    - docs/PUBLISHING.md
    - tests/test_docs.py

key-decisions:
  - "Timings come from direct measurement on this tree (validate 13.0 s, test 78.1 s, push about 91 s) and from `gh run view` on the current-workflow full CI run 43922254257 (ubuntu 252 s, macOS 524 s); no figure was derived from the ci.yml comment."
  - "The recovery block prints the chosen patch name for comparison with the push output's `Stashing unstaged files to ...` line, then inspects and applies on one guarded line, so a failed inspection or dry run stops the apply even in a shell that does not exit on error."
  - "The escape hatch guards the DELETE, the push and the POST individually; the on command and the read-back always run, and an escalation paragraph requires re-running them until `enforce_admins: true` is shown. The docs do not claim line order alone enforces P6."
  - "Each task was committed as one green tree with RED evidence recorded here, per this plan's explicit 'one commit per task' rule (see TDD Gate Compliance)."

patterns-established:
  - "Doc pins use the existing REPO_ROOT / _rule_document_paths() style in tests/test_docs.py and reuse its existing .md literals, so the 26-07 docs-only drift ledger keys stay unchanged."

requirements-completed: [HOOK-06, HOOK-05]

# Coverage metadata — one entry per shipped deliverable
coverage:
  - id: D1
    description: "dev-environment.md carries the gate/target/stage tables, measured timings, the push gate's five refusals and a placeholder-free guarded recovery block"
    requirement: "HOOK-06"
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_dev_environment_carries_the_gate_table"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_dev_environment_has_the_stage_table_with_timings"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_dev_environment_documents_the_push_gate_and_recovery"
        status: pass
      - kind: other
        ref: "acceptance greps over .claude/dev-environment.md (guarded apply, no bare apply, no placeholder, GATE_READ_PATHSPECS)"
        status: pass
    human_judgment: true
    rationale: "Text pins prove the phrases and the guarded chain are present, but the timings' provenance and the copy-paste safety of the recovery prose need a human read."
  - id: D2
    description: "git-workflow.md documents the branch -> green CI -> fast-forward path to main and an escape hatch whose off/push/on/read-back block always restores protection"
    requirement: "HOOK-05"
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_git_workflow_documents_the_path_to_main"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_escape_hatch_turns_enforce_admins_back_on"
        status: pass
      - kind: other
        ref: "acceptance greps (guarded DELETE, guarded push, guarded POST, 'cannot be restored')"
        status: pass
    human_judgment: true
    rationale: "P6 is a test-plus-judgment prohibition: a text pin cannot prove the operator will actually re-enable protection, so review must judge the escalation prose."
  - id: D3
    description: "AGENTS.md, python-tooling.md, README.md and PUBLISHING.md state each gate's target and the CI truth, the stale wording is gone, and the D-14 todo exists"
    requirement: "HOOK-06"
    verification:
      - kind: unit
        ref: "tests/test_docs.py#test_no_rule_doc_keeps_the_stale_validate_wording"
        status: pass
      - kind: unit
        ref: "tests/test_docs.py#test_agents_carries_the_gate_table"
        status: pass
      - kind: other
        ref: "rg -i 'runs? pre-commit hooks' over AGENTS.md and .claude/*.md exits 1; todo file exists"
        status: pass
    human_judgment: true
    rationale: "The README/PUBLISHING CI sentences and the new todo are prose that no test asserts word-for-word."

# Metrics
duration: 19min
completed: 2026-11-16
status: complete
---

# Phase 26 Plan 08: Document the quality gates, push flow and escape hatch Summary

**A gate/target/stage table with measured timings, the push gate's refusals and a guarded recovery block, the branch -> green CI -> fast-forward path to `main` with a protected escape hatch, and stale validate wording pinned out of every rule doc.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-11-16T14:43:00Z
- **Completed:** 2026-11-16T15:02:15Z
- **Tasks:** 3
- **Files modified:** 8 (7 modified, 1 created)

## Accomplishments

- `.claude/dev-environment.md` now lists every gate with its target and stage, records measured commit/push/CI timings with their source, describes the push gate's five refusals (including `GATE_READ_PATHSPECS` files refused even when ignored), and gives a copy-paste-safe recovery block whose apply runs only after inspection and a successful dry run. The false "hooks mirror `make validate`" claim is gone.
- `.claude/git-workflow.md` documents the branch push -> green CI -> fast-forward flow, the docs-only fast pass and outside contributors, plus one escape-hatch block where DELETE, push and POST each carry an `|| echo` guard so the read-back and the on command always run, with an explicit escalation when protection cannot be restored.
- AGENTS.md, python-tooling.md, README.md and PUBLISHING.md now name each gate's own target and tell the truth about CI; the stale `run pre-commit hooks` wording is pinned out across all rule docs.
- A pending todo records the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow as tools that must adopt the new flow.

## Measured timings (2026-11-16)

| Figure | Value | Source |
| ------ | ----- | ------ |
| `make validate` | 13.0 s | `time make validate` on this tree, 24-thread host |
| `make test` | 78.1 s | `time make test` on this tree (7813 passed, 6 skipped) |
| push (validate + test) | about 91 s | sum of the two wall times |
| CI ubuntu-latest | 252 s | `gh run view 43922254257 --json jobs` (current workflow) |
| CI macos-latest | 524 s | same run |

Run 43922254257 was confirmed full: Classify and Hook e2e ran alongside install, validate and test, so it is not a docs-only fast pass. The earlier run 43917832565 predates the current workflow (no Classify, no Hook e2e step) and is not the source of these figures. No figure was taken from the `ci.yml` comment.

## RED Evidence

RED was run before each task's prose was written; the target tests failed on the intended assertions, never on a collection or import error.

- **Task 1:** `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` — 3 failed, 4 passed. `test_dev_environment_carries_the_gate_table`: "dev-environment.md lacks 'make lint'". `test_dev_environment_has_the_stage_table_with_timings`: "no Stage table header". `test_dev_environment_documents_the_push_gate_and_recovery`: "dev-environment.md lacks '--fail-fast'".
- **Task 2:** `uv run pytest tests/test_docs.py tests/test_hook_wiring.py -n auto -q --no-cov` — 2 failed. `test_git_workflow_documents_the_path_to_main`: "git-workflow.md lacks 'git push origin <branch>:main'". `test_escape_hatch_turns_enforce_admins_back_on`: "no section headed 'Escape hatch'".
- **Task 3:** `uv run pytest tests/test_docs.py tests/test_hook_wiring.py tests/test_docs_only.py -n auto -q --no-cov` — 2 failed. `test_agents_carries_the_gate_table`: "AGENTS.md lacks 'make lint'". `test_no_rule_doc_keeps_the_stale_validate_wording`: "AGENTS.md: stale validate wording" (match `run pre-commit hooks`).

Every task's GREEN run passed, and all task `<acceptance_criteria>` greps were checked and passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: dev-environment gate table, timings, push gate, recovery** - `c1471a9e` (docs)
2. **Task 2: path to main and guarded escape hatch** - `5a78ee61` (docs)
3. **Task 3: truthful rule docs and the outside-tools todo** - `e6f5d46a` (docs)

## Files Created/Modified

- `.claude/dev-environment.md` - Makefile gate rows, `## Quality gates by stage` with both tables, rewritten `### Pre-commit` and `#### Recover unstaged edits`.
- `.claude/git-workflow.md` - `### The path to main` and `### Escape hatch: CI is down`; force-with-lease scoped to branches.
- `AGENTS.md` - gate table, `make hooks-e2e`, reworded `make validate`, "never skip a git hook", branch/CI/ff rule.
- `.claude/python-tooling.md` - per-tool `make` targets in the overview and the "Run via" column.
- `README.md` - gate rows in the Makefile table, CI-truth layout comment.
- `docs/PUBLISHING.md` - CI runs on branch pushes except `main`; `main` moves only by fast-forward of a green commit.
- `tests/test_docs.py` - seven new doc pins plus the `_section` helper.
- `.planning/todos/pending/2026-11-16-adopt-the-branch-ci-main-flow-in-outside-tools.md` - the D-14 todo.

## Decisions Made

- Timings were measured on the plan's tree and read from a green CI run; unreadable figures would be written `unavailable`, never inferred from a workflow comment.
- The recovery block prints the chosen patch name so the operator can switch to the file named in the push output when pre-commit kept older patches, and chains inspection, dry run and apply on one line.
- Every escape-hatch mutating line is independently guarded, and the prose requires re-running the on command and read-back until `enforce_admins: true` is confirmed; P6 is not claimed to follow from line order alone.

## Deviations from Plan

- Review fix 1: the escape hatch pushes `HEAD:main` and no longer computes `$branch`, so a detached HEAD cannot delete remote `main`; the pin now forbids `"$branch:main"`.
- Review fix 2: CI timings now cite the current-workflow full run 43922254257 (ubuntu 252 s, macOS 524 s, Classify and Hook e2e included); the false hook-e2e claim about run 43917832565 is corrected.
- Review fix 3: the recovery pin requires the whole `less "$patch" && git apply --check "$patch" && git apply "$patch"` chain and forbids a bare `less "$patch"` line.
- Review fix 4: wording tightened for the escape-hatch ending, the docs-only timing and skipped steps, the three-line recovery sequence, and the exact shellcheck file scope in README and dev-environment.
- Review fix 5: these five review fixes are recorded here, one line each.

## TDD Gate Compliance

This is a doc-only TDD plan whose explicit executor rule is "one commit per task" with `make validate && make test` green on every committed tree. RED evidence was captured from real failing runs and is recorded above and in each task's Summary section rather than as separate `test(26-08):` commits; the single commit per task is the `docs(26-08):` GREEN tree. No RED commit was made with a failing tree.

## Issues Encountered

None. The first `make validate` after Task 2's prose found two over-long assertion literals in `tests/test_docs.py` (E501); they were split with implicit string concatenation, the root cause, and the gate was re-run green. No check was silenced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 26-09 owns the branch-protection change and the real hook install; this plan only documents those flows. The docs and pins are complete and green, ready for 26-09 and then phase verification. No blocker.

---
*Phase: 26-commit-and-push-quality-hooks*
*Completed: 2026-11-16*
