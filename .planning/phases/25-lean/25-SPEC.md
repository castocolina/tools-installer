# Phase 25: Lean — Specification

**Created:** 2026-10-13
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Code that still has no production caller after Phases 17–24.1 is deleted, with behaviour unchanged. App composition moves under pyright and the coverage gate. `wizard_app.py` is split into per-screen modules. The run log is bounded.

## Background

Scouted 2026-10-13:
- **Unwired agent policy.**
  - `installer/agent_policy.py` (376 lines), `agent_env.py` (63) and `agent_guidance.py` (25) are imported only by `installer/policy.py`.
  - Their entry points, `agent_environment_policy` and `compose_agent_environment_policy`, have no caller outside `policy.py` (F11, A: "~565 lines with tests").
  - Caveat: Phase 23's spec plans to reuse the JSON settings writer for CONF-08/09. Whatever Phase 23 wires becomes live and is no longer a target.
- **Composition outside the gates.**
  - `setup.py` (1,522 lines) holds `_build_app` (:755).
  - It imports `questionary` (:20) and its docstring says the questionary boundary is "isolated from the strict-typed, fully-covered core", so composition sits outside pyright and coverage (F12).
  - The questionary chooser is G #9.
- **Other targets.**
  - `installer/wizard_app.py` is 3,011 lines with six screens, modals and review-history comments (F13).
  - `installer/audit.py` (21 lines) loses its last caller in Phase 20.
  - Dead fields and Message classes: F14/F15 and the Phase 21 deletions. The race epochs stay (AR-04).
- **Run log.** `RichLog(...)` has no `max_lines` (`execute_screen.py:462-467`, B 13 IN-08).
- **Size estimate.** "≈ −2,000 prod lines" (TA P9) predates the rewrites in Phases 19–24.1.

## Requirements

1. **Delete what is still dead (LEAN-01)**: Each listed target is deleted, with its tests, if it has zero production callers when this phase runs.
   - Targets: the agent-environment policy (except what Phase 23 wired), the questionary chooser, `audit.py`, dead `Tool`/`Method` fields, and dead Message classes.
   - Current: Present.
   - Target:
     - "Production caller" means reachable by import from `setup.py`, `installer/__main__` or the Makefile entry points.
     - The race epochs (generation and supersede checks) stay.
     - Any target still reachable is listed with its caller instead of being deleted.
   - Acceptance:
     - An import-reachability script run from the entry points finds no listed target.
     - `vulture` reports no new unused code.
     - Each kept target appears in the phase summary with its caller.

2. **Composition under the gates (LEAN-02, F12)**: `_build_app` and its wiring move to `installer/compose.py`.
   - Current: In `setup.py`, outside pyright strict and coverage.
   - Target:
     - `setup.py` keeps only argument parsing and the call.
     - `compose.py` is checked by pyright strict and counted by the coverage gate.
   - Acceptance:
     - `pyright` covers `installer/compose.py` with zero errors.
     - The coverage report lists it, and the gate threshold still passes.
     - `setup.py` no longer defines `_build_app`.

3. **Split `wizard_app.py` (LEAN-03, F13)**: One module per screen (system/user/ai tiers share the catalog screen), one for modals, one for the app class.
   - Current: 3,011 lines in one module.
   - Target:
     - No module is over 800 lines.
     - Imports are updated at every call site. There is no compatibility shim, because this is internal code.
     - Review-history comments (phase or review-ID narratives) are dropped. "Why" comments stay.
   - Acceptance:
     - `wc -l` shows every resulting module ≤ 800 lines.
     - A grep finds no review-ID references (for example `CR-0`, `WR-0`, `IN-0`) in comments under the split modules.
     - The CLI `--all`/`--categories` test files are byte-identical.

4. **Bounded run log (LEAN-04)**: The Execute run log keeps at most 5,000 lines.
   - Current: Unbounded.
   - Target: When older lines are dropped, the log shows one line saying how many were dropped.
   - Acceptance:
     - Writing 6,000 lines leaves 5,000 lines plus the notice, and the newest line is last.
     - Writing exactly 5,000 lines adds no notice.

5. **Behaviour unchanged, size reported (phase gate)**: The full suite and `make validate` pass. The phase summary reports net production lines removed, measured with `git diff --stat` over `installer/` and `setup.py`, against the commit before the phase.
   - Current: Not applicable.
   - Target: The count is reported, with no minimum (decision).
   - Acceptance: CI is green on ubuntu and macOS. The summary carries the measured net count and the before/after commit SHAs.

## Boundaries

**In scope:**
- Deleting the listed targets that are still dead, with their tests
- `installer/compose.py`, and `setup.py` reduced to parse plus call
- Splitting `wizard_app.py` and dropping review-history comments
- `max_lines` on the run log with a dropped-lines notice

**Out of scope:**
- Deleting anything a later phase wired (agent settings writer from Phase 23, receipts, the plan) — it is live by then
- Removing the race epochs — required for correctness (AR-04)
- Behaviour changes, new features or UI text changes beyond the dropped-lines notice
- Replacing questionary entirely — only the dead chooser goes; the confirms stay

## Constraints

- No behaviour change: any test that needs editing must be a pure import-path or deleted-target change, never an assertion change.
- `make validate` (ruff, pyright strict, bandit, vulture, coverage) is the gate. No suppressions are added to pass it.
- This phase runs last, after 24.1, so deletions do not fight earlier rewrites.

## Acceptance Criteria

- [ ] The import-reachability check from the entry points finds no deleted target; each kept target is listed with its caller
- [ ] `vulture` reports no new unused code; the race epoch tests still pass
- [ ] `installer/compose.py` exists, passes pyright strict and is in the coverage report; `setup.py` has no `_build_app`
- [ ] Every module from the split is ≤ 800 lines; no review-ID comments remain in them
- [ ] The CLI `--all`/`--categories` test files are byte-identical to before the phase
- [ ] 6,000 log lines → 5,000 kept plus one dropped-lines notice, newest last; 5,000 lines → no notice
- [ ] The full suite and `make validate` pass; CI is green on ubuntu and macOS
- [ ] The summary reports the net production lines removed, with before/after SHAs

## Edge Coverage

**Coverage:** 12/12 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | A target used only by its own tests counts as dead (tests deleted with it); a target used by a live module stays and is listed (AC 1) |
| empty | R1 | ✅ covered | If every target turns out live, nothing is deleted and the summary lists all callers; the phase still passes (AC 1) |
| encoding | R1 | ✅ covered | Reachability is by import graph, not by name grep, so string-built names (registry kinds) count as reachable through their dispatch tables (AC 1) |
| ordering | R1 | ✅ covered | Deletions go one target per commit, each green, so a wrong deletion is one revert (AC 7) |
| unclassified | R2 | ✅ covered | pyright and coverage include `compose.py` (AC 3) |
| adjacency | R3 | ✅ covered | A screen near the cap may move its helpers into a sibling module; the cap applies to each file (AC 4) |
| empty | R3 | ✅ covered | The old `wizard_app.py` either becomes the app module ≤ 800 lines or is removed; no empty shim (AC 4) |
| ordering | R3 | ✅ covered | The split lands before the comment cleanup, so a diff of the move alone shows no logic change (AC 5, AC 7) |
| boundary | R4 | ✅ covered | Exactly 5,000 lines → no notice; 5,001 → one dropped line and a notice (AC 6) |
| precision | R4 | ✅ covered | The count covers rendered lines (a wrapped line counts once, as RichLog stores it) (AC 6) |
| boundary | R5 | ✅ covered | No floor; zero net lines is a valid report (AC 8) |
| precision | R5 | ✅ covered | Net = deletions − insertions from `git diff --stat`, production paths only, tests excluded (AC 8) |

## Prohibitions (must-NOT)

**Coverage:** 4/4 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| MUST NOT delete code reachable from a production entry point | R1 | resolved | test: the import-reachability check |
| MUST NOT remove the race epoch checks | R1 | resolved | test: the barrier/supersede tests still pass |
| MUST NOT change a test assertion to make the refactor pass | R1, R3, R5 | resolved | judgment: the review diff shows only import paths and deleted-target tests |
| MUST NOT add lint, type or dead-code suppressions | R2, R5 | resolved | test: a grep for new `noqa`/`type: ignore`/vulture whitelist entries in the phase diff finds none |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.88  | 0.75 | ✓      | Delete what is still dead; gates on composition |
| Boundary Clarity   | 0.80  | 0.70 | ✓      | Live-by-then code excluded; epochs kept |
| Constraint Clarity | 0.80  | 0.65 | ✓      | No behaviour or assertion change; no suppressions |
| Acceptance Criteria| 0.82  | 0.70 | ✓      | 8 pass/fail criteria |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

`--auto`: the initial ambiguity of 0.17 was under the gate, so the interview was skipped. The scout found that the agent-policy code is unwired today but partly planned for reuse in Phase 23. Open decisions went to jev-fast-decision. Local Laya answered first, one call per question, both below 0.20 confidence. TypeSafe direct (`jev-latest` → `jev-1.13.0`) then answered both in one batch. Every answer is advisory, and the final decision is recorded below.

| Round | Perspective     | Question summary | Laya (advisory) | TypeSafe (advisory) | Decision locked |
|-------|-----------------|------------------|-----------------|---------------------|-----------------|
| auto | Boundary Keeper | How is "done" defined for the ~2,000-line estimate? | hard_line_floor p=0.42 (needs fallback) | reachability_defined p=0.93 | Every listed target with no production caller is deleted (reachability plus vulture); the count is reported, with no floor |
| auto | Simplifier      | The split rule for `wizard_app.py` | by_layer p=0.65 (needs fallback) | one_module_per_screen p=0.81 | One module per screen plus modals plus app, ≤ 800 lines each. **No compatibility shim**: imports are updated, because this is internal code (ponytail: no "for later" code) |
| auto | Researcher      | The run log bound | – | – | 5,000 lines with a dropped-lines notice (not a jev question; it is a widget parameter) |
| auto | Failure Analyst | Edge table and prohibitions | – | – | All resolved as covered; none dismissed |

---

*Phase: 25-lean*
*Spec created: 2026-10-13*
*Next step: /gsd-discuss-phase 25 — implementation decisions (how to build what's specified above)*
