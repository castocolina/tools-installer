# Phase 20 — consolidated code review, round 2

Scope: `git diff f9d98fe 3c74d96 -- installer setup.py scripts tests` (33 files, gap plans
20-20..20-29 plus test-only commits 1f31b9e and 102bdf9).

Sources:
- `20-REVIEW-2.md` (gsd-code-reviewer, deep): Critical 0 · Warning 1 · Info 1
- `20-REVIEW-ponytail-2.md`: High 0 · Medium 1 · Low 1
- `20-REVIEW-opencode-plan-review-2.md` (router-env/my-plan-review): Critical 1 · High 2 · Medium 1

Round-1 closure: the deep lane closes every CR-*/WR-* and J1..J12 with file:line evidence;
ponytail closes P-01..P-09 (P-10 partial); opencode closes OC-02, OC-04, OC-05, OC-07, OC-08
(OC-03 and OC-06 partial, see the accepted rows below).

Each claim below was checked against the code by the orchestrator before it was kept.

## To fix

| Id | Severity | Sources | Finding | Evidence |
|----|----------|---------|---------|----------|
| K1 | Warning | WR2-01, P2-01 | The e2e gate accepts exit 1 whenever dependency failures are explained, so a headless `PATH wiring could not be completed` / `PATH audit could not be completed` exit 1 (added by 20-24) passes `install_step_ok` | `scripts/container-e2e-verify.sh:426-434`; both lanes reproduced it with the bash harness |
| K2 | Medium | OC2-03 | The execution-time unresolved-dependency check covers only INSTALL/REPAIR/REINSTALL; a present dependent planned for UPDATE or RECONFIGURE still runs after its prerequisite failed to install | `installer/session.py:479-490` (only the install branch reads `unresolved`) |
| K3 | Medium | OC2-04 | A RECONFIGURE row that ends `done` with a step warning (terminal sync unsupported shape) stores it in `RowOutcome.detail`, but the end-of-run report prints update notes only, so the warning is never shown | `installer/session.py:430-439`, `installer/render.py:280-289` |
| K4 | Low | OC2-02, P2-02 | The deferred adoption is a second copy of the adoption check (`receipts.commit_adoption`), and its `False` result is discarded: a binary that changed while the user read the prompt is still planned as adopted/current with no word to the user | `installer/version_status.py:1381-1394`, `installer/receipts.py:336-348` |
| K5 | Info | IN2-01 | A refused reinstall of a present tool (`MANUAL_REQUIRED`, 20-26) is in `_UNRESOLVED`, so a dependent would end `dependency failed` although the dependency is installed (not reachable with the shipped registry) | `installer/session.py:50`, `:517` |
| K6 | Low | P-10 residual | The crash detail re-implements `_first_line` | `installer/session.py:562` |

## Accepted (not gaps)

| Id | Finding | Why |
|----|---------|-----|
| OC2-01 / OC-03 partial | The TUI catalog refresh writes bookkeeping before the review, so `esc` on the review does not undo an adoption, retirement or cache save | L-20-10 as scoped by gap plan 20-23 and documented in `.claude/architecture.md:1114-1120`: launching the catalog is not consent to mutate tools, the TUI never holds writes, and its decline copy claims only that nothing started (`_WAIT_CANCELLED`, `installer/execute_screen.py:78`). Adoption and retirement record facts already on disk; they change no tool. |
| OC-06 partial | `ran_anything` counts a `failed` row that never launched a command, so post-run PATH wiring may run | The PATH wiring and audit are idempotent and a failed install can leave partial files; running them after a failed row is harmless |
