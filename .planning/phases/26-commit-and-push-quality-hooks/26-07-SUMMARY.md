---
phase: 26-commit-and-push-quality-hooks
plan: "07"
subsystem: ci
tags: [github-actions, ci, docs-only, fast-pass, pytest, drift-detector]

requires:
  - phase: 26-commit-and-push-quality-hooks
    provides: "the per-gate make targets, Makefile recipes and CI hook wiring of 26-01..26-05"
provides:
  - "branch-push CI with a fail-closed, step-level docs-only fast pass under unchanged required context names"
  - "a stdlib docs-only classifier and reviewed drift pins for test-read Markdown and runtime link targets"
affects: [26-08-commit-and-push-quality-hooks, 26-09-commit-and-push-quality-hooks]

actuals:
  tokens: 6632
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "fail-closed classification: an unknown or empty change list runs the full jobs"
    - "step-level `if:` fast pass inside one job so the required check names never change"
    - "AST ledger plus runtime link-target drift pins for a small stdlib classifier"

key-files:
  created:
    - devtools/docs_only.py
    - tests/test_docs_only.py
  modified:
    - .github/workflows/ci.yml
    - tests/test_ci_workflow.py
    - tests/test_docs.py

key-decisions:
  - "The fast pass lives in step conditions, never in a path-filtered trigger, so both required contexts always report (D-11)."
  - "The classifier is stdlib-only and errs to full on empty, failed or missing git output (P4, D-16)."
  - "Test-read files are pinned by a reviewed (test file, literal) ledger plus the runtime link targets of the same docs and parser the link test uses (D-27)."
  - "One green commit per task: the plan's executor rule and AGENTS.md both rule out committing a RED tree."

patterns-established:
  - "A drift test owns the boundary of a small classifier; changing the boundary means changing the test in the same full-run change."

requirements-completed: [HOOK-05]

coverage:
  - id: D1
    description: "ci.yml triggers only on branch pushes except main, keeps the required job id/name byte-identical, and checks out full history"
    requirement: HOOK-05
    verification:
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_ci_triggers_on_branch_pushes_except_main"
        status: pass
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_job_id_and_name_are_the_required_contexts"
        status: pass
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_checkout_fetches_full_history"
        status: pass
    human_judgment: false
  - id: D2
    description: "stdlib docs-only classifier with a fail-closed rule matrix and CLI output"
    requirement: HOOK-05
    verification:
      - kind: unit
        ref: "tests/test_docs_only.py#test_the_rule_matrix"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_main_writes_full_false_for_a_planning_only_change"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_main_writes_full_true_for_a_code_change"
        status: pass
      - kind: other
        ref: "uv run python -m devtools.docs_only --base HEAD -> full=true"
        status: pass
    human_judgment: false
  - id: D3
    description: "four full steps gated fail-closed, Hook e2e after Test under unchanged timeouts, no expression interpolation in any run step"
    requirement: HOOK-05
    verification:
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_every_full_step_is_gated_fail_closed"
        status: pass
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_ci_runs_hooks_e2e_after_test"
        status: pass
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_no_run_step_interpolates_an_expression"
        status: pass
      - kind: unit
        ref: "tests/test_ci_workflow.py#test_timeouts_are_unchanged"
        status: pass
    human_judgment: false
  - id: D4
    description: "renames, odd file names, git failures and empty changes never earn the fast pass"
    requirement: HOOK-05
    verification:
      - kind: unit
        ref: "tests/test_docs_only.py#test_a_python_file_renamed_into_planning_runs_everything"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_a_path_with_a_space_or_newline_is_one_path"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_git_failure_runs_everything"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_missing_git_runs_everything"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_empty_change_runs_everything"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_output_file_gets_exactly_one_line"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_uppercase_md_is_not_markdown"
        status: pass
    human_judgment: false
  - id: D5
    description: "reviewed ledger classifies every test Markdown/.planning literal, every ledger glob resolves to non-docs-only files, and runtime link targets are checked with the link test's own parser"
    requirement: HOOK-05
    verification:
      - kind: unit
        ref: "tests/test_docs_only.py#test_every_markdown_literal_in_the_tests_is_classified"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_every_ledger_glob_reads_test_read_files_only"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_the_ledger_covers_the_known_readers"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_every_runtime_resolved_link_target_is_test_read"
        status: pass
      - kind: unit
        ref: "tests/test_docs_only.py#test_the_link_drift_test_catches_a_planning_target"
        status: pass
    human_judgment: false
  - id: D6
    description: "the branch-push workflow is accepted by GitHub Actions and both required contexts report green on a real push to main"
    requirement: HOOK-05
    verification: []
    human_judgment: true
    rationale: "GitHub Actions cannot be run locally and this executor never pushes; the orchestrator proves this in plan 26-09's landing."

duration: 7min
completed: 2026-11-16
status: complete
---

# Phase 26 Plan 07: Branch-push CI with a docs-only fast pass — Summary

**Branch-push CI under unchanged required context names, with a stdlib docs-only classifier and drift pins that keep test-read files out of the fast pass**

## Performance

- **Duration:** 7 min (first to last production commit; TDD RED/GREEN cycles included)
- **Started:** 2026-11-16T17:28:27Z
- **Completed:** 2026-11-16T17:34:45Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- CI now triggers only on `push` with `branches-ignore: [main]`; the `pull_request` trigger is gone. The job id `validate-and-test` and name `validate & test on ${{ matrix.os }}` stay byte-identical over the same two-OS matrix, so the required contexts on `main` keep reporting.
- A `Classify the change` step (id `scope`) runs a new stdlib `devtools.docs_only` CLI with `fetch-depth: 0` history. Install, Validate, Test and the new Hook e2e step all carry `if: steps.scope.outputs.full != 'false'`, so a missing output runs everything.
- The classifier is fail-closed: an empty change list, a git failure, a missing git or any non-docs path runs the full jobs. NUL-separated `--no-renames` paths keep spaces, newlines and both sides of a rename; the suffix match is exact lowercase `.md`.
- Drift pins classify every `.md`/`.planning` literal in the tests in a reviewed ledger, require every ledger glob to resolve to a non-docs-only file, and require every runtime link target of `LINK_CHECKED_DOCS` to be test-read. A synthetic case proves the helper flags a `.planning/` target, so the drift test is not vacuous.

## TDD Evidence

**Task 1 — RED output (missing module and old ci.yml; 21 failed, 7 pin tests passed):**

```
FAILED tests/test_docs_only.py::test_the_rule_matrix[paths0-True] - ModuleNotFoundError
... (13 parametrized rule-matrix cases, all ModuleNotFoundError)
FAILED tests/test_docs_only.py::test_main_writes_full_false_for_a_planning_only_change
FAILED tests/test_docs_only.py::test_main_writes_full_true_for_a_code_change
FAILED tests/test_ci_workflow.py::test_ci_triggers_on_branch_pushes_except_main
FAILED tests/test_ci_workflow.py::test_checkout_fetches_full_history - KeyError
FAILED tests/test_ci_workflow.py::test_classify_runs_after_uv_and_before_install
FAILED tests/test_ci_workflow.py::test_every_full_step_is_gated_fail_closed
FAILED tests/test_ci_workflow.py::test_ci_runs_hooks_e2e_after_test - ValueError
FAILED tests/test_ci_workflow.py::test_timeouts_are_unchanged - StopIteration
```

Semantic check: the target tests failed on the missing `devtools.docs_only` module and the absent `fetch-depth`/`scope`/`Hook e2e` workflow steps — the intended assertions, not fixtures or import errors of unrelated modules. GREEN after creating the classifier and rewriting ci.yml: `28 passed`.

**Task 2 — held-out backstops:** written first per the plan; they passed on the Task 1 code (the plan specifies these confirm an already-correct classifier, so GREEN on first run is the expected result, not a missing RED). GREEN: `22 passed`.

**Task 3 — drift pins:** written first; the runtime-link pin is explicitly labelled a pinning test by the plan (passes at the current tree) and the synthetic case proves the helper is non-vacuous. GREEN: `54 passed` for `test_docs_only.py` + `test_docs.py`.

**TDD gate compliance:** one green commit per task, as the plan's executor rules require ("One commit per task", "`make validate && make test` exit 0 on every commit's tree"). A separate RED commit was deliberately not made: it would fail `make test` and break AGENTS.md's "never commit a knowingly broken tree."

## Task Commits

1. **Task 1: branch-push CI, docs-only fast pass, unchanged check names** — `bb429b16` (feat)
2. **Task 2: rename, encoding, git-failure and empty-change backstops** — `09451569` (test)
3. **Task 3: literal ledger and runtime link-target drift pins** — `2aef95ae` (test)

**Plan metadata:** included in the SUMMARY commit itself (docs: complete 26-07 plan)

## Verification

- `uv run pytest tests/test_docs_only.py tests/test_ci_workflow.py -n auto -q --no-cov` — 28 passed
- `uv run python -m devtools.docs_only --base HEAD` — `full=true` / `empty change` (fail-closed)
- `uv run pytest tests/test_docs_only.py -n auto -q --no-cov` — 22 passed
- `uv run pytest tests/test_docs_only.py tests/test_docs.py -n auto -q --no-cov` — 54 passed
- All plan acceptance greps matched: 1 × `branches-ignore: [main]`, 0 × `pull_request`, 1 × job name, 4 × fail-closed `if:`, 1 × `fetch-depth: 0`, 1 × `run: make hooks-e2e`; 6 backstop tests; ledger/link helper pins all present.
- `make validate && make test` on each task tree — green; final tree: 7801 passed, 6 skipped, 96.21% coverage (floor 90%).

## Files Created/Modified

- `devtools/docs_only.py` (new) — `TEST_READ`, `is_docs_path`, `is_docs_only`, `changed_paths`, `main`; stdlib-only CLI.
- `tests/test_docs_only.py` (new) — rule matrix, CLI cases, rename/encoding/failure backstops, `markdown_literals()`, `LEDGER`, `docs_only_link_targets()` and the drift tests.
- `.github/workflows/ci.yml` — branch-push trigger, full-history checkout, scope step, four fail-closed steps, Hook e2e.
- `tests/test_ci_workflow.py` — trigger rewrite and the new workflow pins; existing setup-uv, matrix, validate/test and target pins kept.
- `tests/test_docs.py` — public `link_targets()` extracted from `_broken_links`, `LINK_CHECKED_DOCS`, link test looped over it; no new `.md` literal.

## Decisions Made

- Step-level `if:` rather than a path-filtered trigger or skipped job, so both required contexts always report (D-11).
- Fail-closed on every unknown: empty path list, git exit != 0, missing git or a missing output all mean a full run (P4, D-16).
- Drift guard at test time, not a link parser in the CI classifier; the classifier stays small for its first push (D-27, review M7).
- `TEST_READ` is a fnmatch tuple where `*` also matches `/`, so `.claude/*` and `docs/*` cover nested docs.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None. The first `make validate` run flagged only formatting in the two new test files; the project formatter fixed them and the gate re-ran green. No quality gate was silenced.

## User Setup Required

None - no external service configuration required by this plan.

## Next Phase Readiness

Ready for 26-08 (documentation pins for the gate/target/stage table, the path to `main` and the escape hatch). Plan 26-09 still owns the branch-protection change, the real hook install and the final branch → green CI → `main` landing; those were not touched here. No blockers.

---
*Phase: 26-commit-and-push-quality-hooks*
*Completed: 2026-11-16*
