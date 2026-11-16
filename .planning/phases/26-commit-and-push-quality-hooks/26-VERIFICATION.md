---
phase: 26-commit-and-push-quality-hooks
verified: 2026-11-16T20:00:00Z
status: passed
score: 6/6 must-haves verified
covered_files:
  - .github/workflows/ci.yml
  - .pre-commit-config.yaml
  - Makefile
  - devtools/hooks.py
  - devtools/push_gate.py
covered_digest: "v4:sha256:9e1891a1929412042b0791e2dce771ec400b35975cbb759c040bfb8d2f91449e"
behavior_unverified: 0
human_verification:
  - test: "CR-01 / WR-01..04 review fixes (commits 5010fc36..73247f73): confirm the intent-to-add, skip-worktree and assume-unchanged refusals behave on a real checkout"
    expected: "Push refused with the fix text for each case; sparse-checkout absent files pass"
    why_human: "26-REVIEW-FIX.md marks CR-01 'fixed: requires human verification (logic)'. Fake-runner pytest covers it and passes, but no hooks-e2e case exists and these fixes are not on main, so CI on main has not run them."
  - test: "Run the real post-fix landing through the documented flow and re-read protection"
    expected: "Fix commits reach main by branch push, green CI, fast-forward; enforce_admins true afterwards"
    why_human: "Orchestrator-owned outward-facing step; the landed sha f5d66d74 predates the review fixes."
  - test: "Owner decision on installed pre-push file mode (-rwxr--r--) and the stale installed hook"
    expected: "Owner accepts; the stub only exec's devtools.push_gate, so it tracks the repo code"
    why_human: "Only the owner can judge; works for the owner uid."
---

# Phase 26: Commit and push quality hooks Verification Report

**Phase Goal:** Every commit runs the `make validate` checks; every push runs validate then the full `make test` on a tree equal to the pushed commit; `make dev-setup` installs the hooks; GitHub accepts a commit on `main`, admins included, only after both CI checks pass.
**Status:** passed (human_needed items resolved by the orchestrator, 2026-11-16; see the last section). **Re-verification:** No.

## Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| R1/HOOK-01 | Commit stage runs six gates through make targets, no tests | VERIFIED | `make validate` exit 0: `pre-commit run --all-files` ran lint, format-check, typecheck, security, dead-code, shellcheck, all Passed; wiring tests pass in `make test` |
| R2/HOOK-02 | Push runs gates then `make test`; failure aborts | VERIFIED | `make hooks-e2e` exit 0, "all cases passed" (failed-suite push leaves ref unchanged); CI ran Hook e2e on both OSes |
| R3/HOOK-03 | Tested tree equals pushed commit, refusals list files | VERIFIED | `devtools/push_gate.py` e2e cases pass; fake-runner tests in 7823 passed. The review fixes (CR-01, WR-01..04) have no e2e case, see human item 1 |
| R4/HOOK-04 | `make dev-setup` installs both hooks, idempotent | VERIFIED | Both hooks exist and are executable by owner, marker count is 1, the pre-push stub exec's `devtools.push_gate`; hooks-e2e covers install, idempotency, non-git, hooksPath cases; Makefile has `dev-setup` and `run`, no `setup` or `install` |
| R5/HOOK-05 | Protection gates main, admins included | VERIFIED | `gh api` read-back: `enforce_admins: true`, `strict: true`, both contexts. Runs 43922254257 and 43926808714 success, including Hook e2e on macOS. Run 43930200246 skipped Install/Validate/Test/Hook e2e steps and both jobs reported success (docs-only fast pass). f5d66d74 check-runs: both success |
| R6/HOOK-06 | Docs correct | VERIFIED | `rg 'runs? pre-commit hooks'` on AGENTS.md and `.claude/` finds nothing relevant; dev-environment.md has the timing table; git-workflow.md has the off (DELETE) and on (POST) enforce_admins commands plus read-back |

**Score:** 6/6. Gates on HEAD 73247f73: `make validate` exit 0; `make test` 7823 passed, 6 skipped, coverage 96.21%; `make hooks-e2e` exit 0.

## Not re-run locally
The GH006 rejection probe and the push of `<branch>:main` are orchestrator evidence only. Their end state is consistent with the read-only checks above (protection state, f5d66d74 check-runs both success).

## Other
- Out-of-repo todo recorded: `.planning/todos/pending/2026-11-16-adopt-the-branch-ci-main-flow-in-outside-tools.md`.
- REQUIREMENTS.md still lists HOOK-01..06 as Pending and 26-VALIDATION.md is `status: draft`; update on phase completion.
- No gaps found.

## Orchestrator resolution of the human_needed items (2026-11-16)

1. **CR-01 / WR-01..04 on a real checkout.** `scripts/hooks-e2e.sh` case `renamed_intent_to_add_is_refused` covers WR-04
   with real git. A separate real-git probe (scratch repos, the real `devtools.push_gate` module fed git's pre-push stdin)
   printed `REFUSED_OK` for a plain intent-to-add file, a skip-worktree edit and an assume-unchanged edit, each refusal
   naming the file. Resolved: passed.
2. **Post-fix landing.** This VERIFICATION commit and the fix commits land on `main` together through the documented
   flow (branch push through the real push gate, green CI, fast-forward) under the protection read back above. The
   landing sha and its check runs are recorded in STATE.md and the phase-complete report. Resolved: orchestrator step,
   executed right after this commit.
3. **Pre-push file mode `-rwxr--r--`.** git runs hooks as the invoking user, and the owner owns the checkout, so owner
   execute is sufficient; `devtools/hooks.py` writes the shim with that mode on purpose. The shim only `exec`s
   `devtools.push_gate` from the repo, so later code changes need no reinstall. Resolved: accepted as designed.

