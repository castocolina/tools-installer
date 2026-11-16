---
phase: 18-registry-truth-and-drift-guard
plan: "14"
subsystem: infra
tags: [registry, verify-registry, github-actions, gh-cli, drift, pytest]

requires:
  - phase: 18-registry-truth-and-drift-guard
    provides: check_registry, format_report, Report.exit_code, gh injection (plans 18-12, 18-17, 18-13)
provides:
  - "--issue upsert of one open registry-drift GitHub issue via gh and --body-file"
  - "code_span-safe issue bodies (format_report with include_passed=False for issues)"
  - "make verify-registry read-only launcher with README/AGENTS docs"
  - "Weekly verify-registry.yml with cache restore/save and mid-week state refresh cron"
  - "Incremental on_verified state persistence during check_registry"
affects: [18-15]

actuals:
  tokens: ~17000
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Injected gh callable records argv; upsert only when exit_code == 1"
    - "Split actions/cache restore+save with if: always() on save for failing drift jobs"
    - "on_verified callback persists state after each ok target fingerprint"

key-files:
  created:
    - .github/workflows/verify-registry.yml
    - tests/test_verify_registry_workflow.py
  modified:
    - installer/verify_registry.py
    - tests/test_verify_registry.py
    - Makefile
    - tests/test_makefile.py
    - README.md
    - AGENTS.md

key-decisions:
  - "Issue upsert runs only on exit 1 (confirmed drift), including blocked+drift per L-18-18"
  - "Unverified method kind stays plain text in format_report; tool ids and assets use code_span"
  - "A green weekly run does not close the drift issue (not required by SPEC)"

patterns-established:
  - "Drift reporting: DRIFT_LABEL + label create --force, list open, edit or create with body file"

requirements-completed: [REG-03]

coverage:
  - id: D1
    description: "--issue creates or edits one registry-drift issue with full drift list, no Passed section"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_first_drift_creates_the_issue
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_second_drift_edits_the_open_issue
        status: pass
    human_judgment: false
  - id: D2
    description: "No gh calls on clean, inconclusive-only, or blocked-without-drift runs"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_clean_run_makes_no_gh_call
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_inconclusive_run_makes_no_gh_call
        status: pass
    human_judgment: false
  - id: D3
    description: "Blocked or mixed runs still upsert when drift confirmed; body uses code_span"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_blocked_run_with_confirmed_drift_still_updates_the_issue
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_drift_beside_an_inconclusive_finding_still_updates_the_issue
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_issue_code_span_picks_a_safe_delimiter
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_issue_body_never_breaks_out_of_a_code_span
        status: pass
    human_judgment: false
  - id: D4
    description: "make verify-registry is read-only by default and documented"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_makefile.py#test_verify_registry_target_is_read_only_by_default
        status: pass
    human_judgment: false
  - id: D5
    description: "verify-registry workflow is off PR gate, read-only repo, cache state, weekly --issue"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry_workflow.py#test_verify_registry_runs_only_on_schedule_and_dispatch
        status: pass
      - kind: unit
        ref: tests/test_verify_registry_workflow.py#test_verify_registry_job_cannot_write_the_repo
        status: pass
      - kind: unit
        ref: tests/test_verify_registry_workflow.py#test_verify_registry_job_keeps_the_state_after_every_run
        status: pass
      - kind: unit
        ref: tests/test_verify_registry_workflow.py#test_ci_workflow_never_runs_verify_registry
        status: pass
    human_judgment: false
  - id: D6
    description: "Incremental state save and cache-miss recovery path"
    requirement: REG-03
    verification:
      - kind: unit
        ref: tests/test_verify_registry.py#test_state_is_saved_after_each_verified_asset
        status: pass
      - kind: unit
        ref: tests/test_verify_registry.py#test_cache_miss_downloads_every_asset_once
        status: pass
    human_judgment: false
  - id: D7
    description: "First production workflow_dispatch run and cache last-accessed within 7-day window"
    requirement: REG-03
    verification: []
    human_judgment: true
    rationale: "Backstop truth after main push; requires orchestrator dispatch and gh cache list inspection"

duration: 120min
completed: 2026-10-15
status: complete
---

# Plan 18-14 Summary

**Weekly drift guard: `--issue` upserts one `registry-drift` GitHub issue on confirmed drift, `make verify-registry` for local checks, and a scheduled workflow with Actions cache for digest state.**

## Performance

- **Duration:** ~120 min
- **Tasks:** 3
- **Files modified:** 8 (+686 / -14 lines across task commits)

## Accomplishments

- Added `upsert_drift_issue`, `code_span`, and `--issue` wired to `format_report(..., include_passed=False)` with injected `gh`; upsert only when exit code is 1.
- Extended `format_report` to wrap upstream strings in CommonMark-safe code spans; issue bodies never include secrets from the environment.
- Added read-only `make verify-registry` (`uv run --isolated --no-dev python -m installer.verify_registry $(ARGS)`) with Makefile test and README/AGENTS entries.
- Added `.github/workflows/verify-registry.yml` (Monday check + Thursday state refresh, cache restore/save, `permissions: issues: write`).
- Added `on_verified` in `check_registry` so `main` persists state after each verified ok target; tests cover mid-run kill and cache miss.

## Task Commits

Each task was committed atomically:

1. **Task 1: drift issue upsert (D-07)** - `9fd8668` (feat)
2. **Task 2: make verify-registry + docs (D-08)** - `0bdc008` (feat)
3. **Task 3: weekly workflow + incremental state (D-08, L-18-04)** - `e81c8cf` (feat)

**Plan metadata:** (this commit) `docs(18-14): plan summary`

## Files Created/Modified

- `installer/verify_registry.py` - `code_span`, `upsert_drift_issue`, `--issue`, `on_verified` persistence
- `tests/test_verify_registry.py` - nine issue/gh tests plus state recovery tests
- `Makefile` - `verify-registry` target
- `tests/test_makefile.py` - read-only target invariants
- `.github/workflows/verify-registry.yml` - scheduled drift job
- `tests/test_verify_registry_workflow.py` - workflow YAML invariants
- `README.md` / `AGENTS.md` - command table and registry drift section

## Decisions Made

- Left unverified-method `kind` unwrapped in `format_report` so existing report assertions on `(github_release)` stay stable; tool ids, URLs, reasons, and assets use `code_span`.
- `code_span` pads with spaces on both sides when the cleaned value starts or ends with a backtick (CommonMark edge case).

## Deviations from Plan

### Auto-fixed Issues

**1. Accidental test file truncation during edit**
- **Found during:** Task 1 (test authoring)
- **Issue:** A full-file write replaced `tests/test_verify_registry.py` with a truncated copy (~800 lines removed).
- **Fix:** `git checkout -- tests/test_verify_registry.py` and re-applied changes via a patch script.
- **Verification:** Line count restored to 2800+; full pytest suite passes.

**2. Ruff SIM115 on NamedTemporaryFile**
- **Found during:** Task 1 validate
- **Issue:** `upsert_drift_issue` opened a temp file without a context manager.
- **Fix:** Use `with tempfile.NamedTemporaryFile(...)` and unlink `body_path` in `finally`.

---

**Total deviations:** 2 auto-fixed (1 tooling mistake, 1 lint)
**Impact on plan:** No scope change; behavior matches plan.

## Issues Encountered

- Initial `ImportError` for `code_span` resolved by implementing Task 1 production code after RED tests.
- Pyright unknown types in workflow cron parsing fixed with explicit `cast(list[dict[str, str]], ...)`.

## User Setup Required

None - no external service configuration required. After merge, orchestrator may run `workflow_dispatch` for backstop D7.

## Next Phase Readiness

- REG-03 automation is in place; maintainers can run `make verify-registry` locally (without `--issue`) and rely on the weekly job for issue upsert.
- First live workflow run and cache retention remain a human backstop (coverage D7).

---
*Phase: 18-registry-truth-and-drift-guard*
*Completed: 2026-10-15*
