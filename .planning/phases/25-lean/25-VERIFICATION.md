---
phase: 25-lean
verified: 2026-11-16T01:00:00Z
status: human_needed
score: 4/4 must-haves verified
covered_files:
  - .planning/phases/25-lean/25-01-PLAN.md
  - .planning/phases/25-lean/25-01-SUMMARY.md
  - .planning/phases/25-lean/25-02-PLAN.md
  - .planning/phases/25-lean/25-02-SUMMARY.md
  - .planning/phases/25-lean/25-03-PLAN.md
  - .planning/phases/25-lean/25-03-SUMMARY.md
  - .planning/phases/25-lean/25-04-PLAN.md
  - .planning/phases/25-lean/25-04-SUMMARY.md
  - .planning/phases/25-lean/25-05-PLAN.md
  - .planning/phases/25-lean/25-05-SUMMARY.md
  - .planning/phases/25-lean/25-06-PLAN.md
  - .planning/phases/25-lean/25-06-SUMMARY.md
  - .planning/phases/25-lean/25-07-PLAN.md
  - .planning/phases/25-lean/25-07-SUMMARY.md
  - .planning/phases/25-lean/25-08-PLAN.md
  - .planning/phases/25-lean/25-08-SUMMARY.md
  - .planning/phases/25-lean/25-09-PLAN.md
  - .planning/phases/25-lean/25-09-SUMMARY.md
  - .planning/phases/25-lean/25-10-PLAN.md
  - .planning/phases/25-lean/25-10-SUMMARY.md
  - .planning/phases/25-lean/25-11-PLAN.md
  - .planning/phases/25-lean/25-11-SUMMARY.md
  - installer/compose.py
  - installer/execute_screen.py
  - installer/wizard_app.py
  - setup.py
  - tests/test_reachability.py
covered_digest: "v4:sha256:4c7e5bc21081a342ee963498bef049cbb1540ebc2d5f8a13c9de9bd51f061865"
behavior_unverified: 0
human_verification:
  - test: "CI result for the final head efbb30db on ubuntu and macOS"
    expected: "CI green on both runners (earlier wave heads through 25-11 docs were green)"
    why_human: "The run for efbb30db was still in progress at verification time"
  - test: "Container UAT: Execute screen with a long run (over 5,000 log lines)"
    expected: "Log keeps the newest lines, one dropped-lines notice shows above it, no notice below 5,000 lines, notice survives a resize"
    why_human: "Screen behaviour; unit tests cover the counts, not the rendered layout"
  - test: "Container UAT: every split view (catalog, policies, schedules, doctor, uninstall) opens and navigates"
    expected: "Same screens, keys and text as before the split"
    why_human: "Module move; CSS and message-handler names verified by review, rendering is not"
---

# Phase 25: Lean Verification Report

**Phase Goal:** Delete code with no production caller, move composition under the gates, split wizard_app.py, bound the run log, behaviour unchanged.
**Verified:** 2026-11-16 (HEAD efbb30db). **Status:** human_needed. **Re-verification:** No.

## Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LEAN-01: dead targets removed, race epochs stay | VERIFIED | audit.py, agent_policy.py, agent_guidance.py, host_setup.py absent; no questionary chooser; ConfirmSensitiveAction, SensitiveActionScreen and HOST_SETUPS have no hits; the loader rejects `default_enabled_sensitive_actions` with a retirement message (model.py:600). `tests/test_reachability.py` passes in the full suite; race-epoch tests pass |
| 2 | LEAN-02: composition in installer/compose.py under gates | VERIFIED | compose.py exists (934 lines); setup.py has no `_build_app` definition (imports it, 663 lines); pyright 0 errors; coverage table lists the module; 96.20% vs 90% gate |
| 3 | LEAN-03: wizard_app.py split, review ids dropped | VERIFIED | Largest split module wizard_app.py is 793 lines; ten modules all at or below 800. The review-id grep over the split modules, compose.py and setup.py finds nothing. tests/test_cli.py and tests/test_install_sh.py are byte-identical to d0d88257 |
| 4 | LEAN-04: run log bounded at 5,000 | VERIFIED | `RUN_LOG_MAX_LINES = 5000`, dropped_notice, local drop counting (WR-03 fixed); tests at test_execute_screen.py:5386-5467 cover 5,000, 6,000 and the notice |
| 5 | Phase gate: make validate and make test pass | VERIFIED | Run by me on HEAD: validate clean (ruff, pyright 0, bandit, vulture, shellcheck); 7662 passed, 6 skipped |
| 6 | No added suppressions | VERIFIED | Phase diff of installer/, setup.py shows no added noqa or type: ignore lines |

## Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| LEAN-01 | SATISFIED | see truth 1 |
| LEAN-02 | SATISFIED | see truth 2 |
| LEAN-03 | SATISFIED | see truth 3 |
| LEAN-04 | SATISFIED | see truth 4 (visual check is a UAT candidate) |

Plan 25-11's "complete" marks in REQUIREMENTS.md are confirmed.

## Findings and jev classification

jev ladder (Laya local first, TypeSafe second; advisory only). Laya returned low confidence (top about 0.32-0.35, fallback) on every item. My own reasoning decided F2-F4.

| ID | Finding | jev answer | jev confidence | Final classification |
|----|---------|-----------|----------------|----------------------|
| F1 | `compose.__all__` still lists 15 private names (review IN-04 not applied; commented as intent) | TypeSafe: open-trivial | 0.95 | open-trivial (agree) |
| F2 | 25-11 SUMMARY says net 76 lines removed; at HEAD the measured net is 32 (5180 deleted, 5148 added) after review fixes. SPEC accepts any count | no decision (Laya open-real 0.34, TypeSafe open-real 0.37, both fallback) | low | open-trivial (own reasoning: report is stale, goal unaffected) |
| F3 | CI for head efbb30db still running; earlier heads green | no decision (Laya 0.33, TypeSafe open-real 0.65, fallback) | low | resolved by human item above; not a blocker |
| F4 | deferred-items.md: test-only symbols kept (omz_present, DETAIL_PHRASE_COLLISIONS, disk_probing) and a flaky wall-clock test in test_run.py | no decision (Laya 0.32, TypeSafe open-real 0.64, fallback) | low | owner-only (own reasoning: SPEC does not list them; follow-up deletion is the owner's call) |

## Anti-patterns

No TBD/FIXME markers examined beyond the review-id grep. compose.py at 934 lines exceeds 800, but SPEC R3's cap applies to the split modules (amendment names compose.py under R2 only).

## Gaps Summary

None blocking. Status is human_needed because CI for the last head and screen behaviour are not established programmatically.

_Verifier: Claude (gsd-verifier)_
