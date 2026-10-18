---
phase: 20-install-plan-with-dispositions
plan: "23"
subsystem: installer
tags: [consent, receipts, version-cache, refresh]

requires:
  - phase: 20-install-plan-with-dispositions
    provides: install plan, refresh service, and receipt bookkeeping
provides:
  - Headless bookkeeping writes are deferred until consent
  - Broken-receipt rows no longer show an inapplicable reinstall-and-adopt note
affects: [phase-20, headless-installs, receipt-lifecycle]

actuals:
  tokens: 1400
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns: [deferred bookkeeping write queue, consent-gated persistence]

key-files:
  created: [.planning/phases/20-install-plan-with-dispositions/20-23-SUMMARY.md]
  modified: [installer/app.py, installer/receipts.py, installer/version_status.py, tests/test_app.py, tests/test_version_status.py, .claude/architecture.md]

key-decisions:
  - "Headless refresh holds cache, receipt-adoption, and retirement writes until consent; TUI refresh remains immediate."
  - "Deferred operations retain commit-time race checks and best-effort error handling."

patterns-established:
  - "A headless route can hold refresh bookkeeping writes and commit them before execution after user consent."

requirements-completed: [PLAN-06]

coverage:
  - id: D1
    description: Headless refresh bookkeeping is not persisted until consent.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_version_status.py#test_a_declined_headless_plan_adopts_nothing
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_a_held_pass_retires_a_gone_receipt_only_on_commit
        status: pass
      - kind: unit
        ref: tests/test_version_status.py#test_held_cache_saves_wait_for_commit
        status: pass
      - kind: unit
        ref: tests/test_app.py#test_run_wizard_commits_held_writes_only_after_consent
        status: pass
    human_judgment: false
  - id: D2
    description: Broken receipt rows do not offer the unavailable reinstall-and-adopt action.
    requirement: PLAN-06
    verification:
      - kind: unit
        ref: tests/test_version_status.py#test_a_broken_receipt_tool_carries_no_unproven_note
        status: pass
    human_judgment: false

duration: 180min
completed: 2026-10-18
status: complete
---

# Phase 20: Headless consent-gated bookkeeping summary

**Headless refresh now defers receipts and cache writes until consent; TUI persistence remains immediate and broken-receipt notes no longer promise an unavailable action.**

## Performance

- **Duration:** approximately 180 minutes
- **Started:** 2026-10-18
- **Completed:** 2026-10-18
- **Tasks:** 3
- **Files modified:** 6 (excluding this summary)

## Accomplishments

- Added hold/commit handling for receipt adoption, retirement, version-cache saves, skill-cache saves, and invalidation saves. Headless `--yes` and confirmed runnable plans commit before execution; decline and failed state checks do not.
- Kept commit-time receipt race checks and cache merge behavior, and handled deferred write failures without aborting a consented run.
- Documented the differing headless and TUI write boundaries and limited the reinstall-and-adopt note to tools without a receipt.

## Test-Driven Development Record

Collected test counts before this plan's changes: `tests/test_version_status.py` 181, `tests/test_app.py` 131, `tests/test_receipts.py` 112. End counts: 190, 135, and 112 respectively.

### Task 1 — consent-gated adoption

- **RED command:** `uv run pytest tests/test_version_status.py tests/test_app.py -q --no-cov -n 0 -k "adopts_nothing or commits_the_adoption or only_after_consent"`
- **RED output:** `2 failed`; decline returned a plan rather than `None` because the test fixture's second tool was not runnable, and the yes guard observed no install call for the same fixture problem. After correcting the fixture to use `_rg_archive()`, rerun output was `1 failed, 1 passed`; the failing assertion confirmed the declined refresh had already written the yq receipt.
- **GREEN command:** same targeted command.
- **GREEN output:** `6 passed` (including the four consent-event parameter cases). Existing test counts met floors: version-status 183, app 135, receipts 112.
- **Commit:** `fa17ee5` — `fix(20-23): headless adopts receipts only after the user consents`.

### Task 2 — held retirement and cache saves

- **RED command:** `uv run pytest tests/test_version_status.py -q --no-cov -n 0 -k "retires_a_gone_receipt_only or cache_saves_wait"`
- **RED output:** `2 failed`; the all-gone receipt was retired while held, and cache writes from refresh/invalidation created the file before consent. The initial skill test probe fixture required correction; the resulting expected behavior remained unknown for that synthetic host.
- **GREEN command:** `uv run pytest tests/test_version_status.py -q --no-cov -n 0 -k "retires_a_gone_receipt_only or cache_saves_wait or retires_nothing"`
- **GREEN output:** `3 passed`; the decline regression also verified unchanged cache bytes and an unretired receipt. The broader touched suite passed: 4872 passed; version-status collection floor was 186.
- **Commit:** `9aae983` — `fix(20-23): retirement and cache saves wait for consent; document the boundary`.

### Task 3 — unproven-note eligibility

- **RED command:** `uv run pytest tests/test_version_status.py -q --no-cov -n 0 -k "unproven"`
- **RED output:** `1 failed, 12 passed`; the broken-receipt regression showed the unproven note was still attached. The test first passed with an unsuitable archive fixture; it was changed to use a modified receipted yq binary to exercise actual BROKEN drift before capturing RED.
- **GREEN command:** `uv run pytest tests/test_version_status.py -q --no-cov -n 0 -k "unproven"`
- **GREEN output:** `13 passed`; version-status collection was 188 at the task gate and 190 at final verification.
- **Commit:** `b1ea261` — `fix(20-23): attach the unproven note only to a tool with no receipt`.

## Verification

- Final touched-suite run: `uv run pytest tests/test_version_status.py tests/test_app.py tests/test_receipts.py tests/test_catalog_tui.py -q --no-cov -n auto` — passed.
- Final quality gate: `make validate` — passed (ruff, formatting, pyright, bandit, vulture, shellcheck).
- Final full suite: `make test` — **4876 passed, 4 skipped**, 96.0% total coverage.
- Collected end floors: `tests/test_version_status.py` 190 (required >=188), `tests/test_app.py` 135 (required >=135), `tests/test_receipts.py` 112 (required >=112).
- Suppression-count gate: passed; no new suppression comments.
- `git diff 16c8994..HEAD --check`: passed.

## Task Commits

1. **Task 1: consent-gated adoption** — `fa17ee5`
2. **Task 2: held retirement/cache saves and route documentation** — `9aae983`
3. **Task 3: unproven-note eligibility** — `b1ea261`

## Files Created/Modified

- `installer/receipts.py` — supports building a validated adoption candidate without writing and rechecking before deferred persistence.
- `installer/version_status.py` — holds queued bookkeeping writes, retains race checks, and adjusts unproven-note eligibility.
- `installer/app.py` — commits held writes only after consent or `--yes`, before execution.
- `tests/test_version_status.py` — adoption, retirement, cache, write-failure, and note-eligibility regressions.
- `tests/test_app.py` — consent ordering and state-check failure cases.
- `.claude/architecture.md` — documents the route-specific bookkeeping boundary.

## Decisions Made

- Headless runs defer writes until consent; the interactive catalog continues writing during refresh because it is the TUI's defined bookkeeping boundary.
- Deferred receipt adoption and retirement repeat their checks at commit. Cache operations load and merge disk state when the queued write executes.

## Deviations from Plan

- The final consent condition includes `options.yes` even when a `--yes` plan has no runnable rows, matching the plan's explicit rule that `--yes` commits held writes. A no-runnable plan without `--yes` does not commit.
- Code-review subagent dispatch was attempted but unavailable (agent identifier unavailable and a subsequent dispatch was rejected by the upstream policy budget). A self-review of the generated review package and final diff was performed instead; this is weaker than an independent review.

## Issues Encountered

- Test fixtures initially failed to create runnable conditions or a correctly configured skill-status probe. Those setup errors were corrected; the final RED failures exercised the target behavior.
- The required collected-count shell expression had quoting issues under the shell wrapper. Counts were independently verified from pytest collection output: 190 / 135 / 112.
- `.claude/architecture.md` is ignored by repository rules and was explicitly force-staged as a planned documentation change.

## User Setup Required

None.

## Next Phase Readiness

The headless consent boundary and receipt-note behavior are implemented and verified. The intentionally modified `.planning/config.json` remains untouched by this work and is still present as a worktree modification. The plan summary is intended to be committed separately after these task commits.

---
*Phase: 20-install-plan-with-dispositions*
*Completed: 2026-10-18*
