---
phase: 25-lean
verified: 2026-11-16T01:00:00Z
status: passed
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
covered_digest: "v4:sha256:4f0027b9e1db44cabe73b40ba1e080706dad15891dbfdf167491e0a26130d2a4"
behavior_unverified: 0
---

# Phase 25: Lean Verification Report

**Phase Goal:** Delete code with no production caller, move composition under the gates, split wizard_app.py, bound the run log, behaviour unchanged.
**Verified:** 2026-11-16 (HEAD efbb30db). **Status:** passed. **Re-verification:** Yes, after UAT and CI (HEAD 421e3e85; implementation unchanged since efbb30db).

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
| LEAN-04 | SATISFIED | see truth 4 (rendered check: tests, see Open items) |

Plan 25-11's "complete" marks in REQUIREMENTS.md are confirmed.

## Open items, resolved

| Item | Resolution | Evidence |
|------|-----------|----------|
| CI for efbb30db (F3) | Resolved | Run 43783376230 succeeded on ubuntu and macOS (`gh run view`: success). efbb30db is an ancestor of HEAD; `git diff efbb30db HEAD -- installer setup.py tests` is empty |
| Execute screen with a long run | Resolved by tests | test_execute_screen.py:5393 onward: 5,000 lines kept with no notice, 6,000 lines keep the newest and show one dropped-lines notice; `_show_log` waits for the pre-layout replay (55d49793, 349ee422, efbb30db). The UAT yq run was short, so the rendered notice was not captured in a container; accepted on test evidence by the caller |
| Every split view opens and navigates | Resolved | 25-UAT.md test 1 (pass): 20 captures at 80x20 byte-identical to the pre-phase set, default herdr size checked; test 2: real yq install and uninstall through the TUI, no sensitive prompt; test 3: CLI routes and retired-key errors |
| F1 `compose.__all__` lists private names | Accepted | Locked by CONTEXT D-05; not open |
| F2 25-11 SUMMARY says net -76 lines | Closed | Record correction only: measured net at HEAD is -32 (5180 deleted, 5148 added). SPEC accepts any count |
| F4 deferred-items.md | Closed | 08e9f19b deleted the file: flaky bound fixed in 2ebd2e5b, omz_present deleted in ba692124 (only a test helper name remains in tests/test_engine.py), the other two seams kept by the orchestrator's decision |

No finding remains open, so no jev classification was needed. The LEAN-01..04 verdicts above are unchanged.

## Anti-patterns

No TBD/FIXME markers in installer/compose.py. compose.py at 934 lines exceeds 800, but SPEC R3's cap applies to the split modules (amendment names compose.py under R2 only).

## Gaps Summary

None. Every previously open item is resolved.

_Verifier: Claude (gsd-verifier)_

## jev ladder 2026-11-16

Entry point `jev_review.py ladder` (Laya, then TypeSafe under the consent recorded 2026-10-14), one `choice` item per finding with the
evidence in its `context`, `reviewed_head` 8b0d1bf1e5b0408f2f40ecdd50b253a367ca1355. The earlier note "no jev classification was
needed" is superseded: the findings were classified. Receipt: `/tmp/claude-1000/-var-home-bazzite-git-personal-tools-installer/954c3fb8-ff60-4af7-85b4-b39cda9abded/scratchpad/rv25b-jev-out.json`. Advisory only.

| Finding | Laya | TypeSafe | decided_by | Final verdict |
|---|---|---|---|---|
| F1 compose `__all__` lists private names (locked by D-05) | open-real, 0.32 (needs_fallback) | resolved, 0.65 (needs_fallback) | own reasoning | **resolved** (accepted by design, D-05) |
| F2 25-11 SUMMARY net -76 lines | open-real, 0.41 (needs_fallback) | open-trivial, 0.57 (needs_fallback) | own reasoning | **resolved** |
| F4 deferred-items.md closed | resolved, 0.30 (needs_fallback) | resolved, 0.82 | typesafe | **resolved** |

Overrides and reasons: no jev answer was confident and against the evidence, but two disagree and are overridden on the evidence. F1:
Laya open-real (0.32, noise) and TypeSafe resolved (0.65); my verdict is resolved because CONTEXT D-05 locks the re-export, and it is
a named design decision, not a defect. F2: Laya open-real and TypeSafe open-trivial, both under the confidence threshold; my verdict
is resolved because the corrected figure (net -32 at HEAD) is already recorded in this file and the SPEC accepts any line count. F4
agrees with the evidence (TypeSafe 0.82).

Rendered run-log evidence for LEAN-04: see 25-UAT.md "Run-log capture 2026-11-16" (notice, newest line and footer captured at 80x20,
120x40 and the default size; resize keeps the notice). The "Execute screen with a long run" row above, "accepted on test evidence",
now also has a real-screen capture.

## Re-verification 2026-11-16 (after Phase 26)

Changed covered files since the last verified head (8b0d1bf1): `installer/compose.py` and `setup.py`, both only in commit d444804b
(docs(26-02)). The diff is one comment line in compose.py (`make setup` to `make run`, line ~798) and one docstring line in setup.py
(line 3). No code changed; `installer/execute_screen.py`, `installer/wizard_app.py` and `tests/test_reachability.py` are unchanged.

Affected claims: none of LEAN-01..04 depends on those lines. Spot checks at HEAD: `uv run pytest tests/test_reachability.py -n 0
--no-cov -q` passes (LEAN-01); compose.py is 934 lines, setup.py 663, wizard_app.py 793 (LEAN-02, LEAN-03 unchanged);
`RUN_LOG_MAX_LINES = 5000` at installer/execute_screen.py:94 (LEAN-04). Stale citation note: the "make setup" wording above is
historical; the wizard target is now `make run`.

Verdict: passed, 4/4 must-haves still hold. Fingerprint regenerated with `query verification.fingerprint`.
