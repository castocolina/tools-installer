---
phase: 26-commit-and-push-quality-hooks
plan: "09"
subsystem: repo-governance
tags: [branch-protection, enforce-admins, git-hooks, landing]
requirements-completed: [HOOK-02, HOOK-03, HOOK-04, HOOK-05]
key-files:
  created: []
  modified:
    - .planning/phases/26-commit-and-push-quality-hooks/26-VALIDATION.md
executed-by: orchestrator (owner go-ahead 2026-11-16)
completed: 2026-11-16
---

# Phase 26 Plan 09: protection, real hook install and the protected landing — Summary

The orchestrator ran all three checkpoints after the owner's go-ahead ("Go ahead, all of 26-09", 2026-11-16).

## Task 1: strict checks and `enforce_admins`

- Precondition: 26-01..26-08 were merged on `gsd/phase-26-commit-and-push-quality-hooks`, with `make validate && make test`
  and `make hooks-e2e` green. CI run 43926808714 was green on both jobs at `ee9e4b1c`, and remote `main` was
  fast-forwarded to `ee9e4b1c`, the last direct move of `main`.
- `PATCH …/protection/required_status_checks` set `strict: true` with both contexts, then
  `POST …/protection/enforce_admins` turned it on. Both calls were applied twice.
- The read-back was identical both times:
  `{"checks":["validate & test on ubuntu-latest","validate & test on macos-latest"],"enforce_admins":true,"strict":true}`.
- Probe: an empty commit on `origin/main`, pushed as `probe/26-protection:main`, was rejected:
  `remote: error: GH006: Protected branch update failed for refs/heads/main. … 2 of 2 required status checks are expected.`
  `! [remote rejected] probe/26-protection -> main (protected branch hook declined)`. Remote `main` stayed at
  `ee9e4b1c`, and the probe branch was deleted locally and never pushed.

## Task 2: real hook install

- Step 0: `git ls-files --others --exclude-standard` listed nothing outside `.planning/`. The owner had `.graphifyignore`
  committed (3a178b66), so no `.git/info/exclude` line was needed.
- Step 0b: the gate-read query over `GATE_READ_PATHSPECS` printed nothing and exited 0.
- `git rev-parse --git-dir` printed `.git`. `make dev-setup` printed `pre-commit installed at .git/hooks/pre-commit`
  and `dev-setup: commit hook and push gate installed in …/.git/hooks`, with no worktree warning.
- Both hooks are executable, and the `tools-installer: pre-push gate` marker count is 1.
- A second `make dev-setup` left both hook files byte-identical (`cmp` exit 0). The backup copies were deleted.

## Task 3: landing

This commit lands through branch push, green CI and fast-forward under binding protection. The outcome is recorded
in the phase VERIFICATION, which lands through the same flow.

## Deviations

- The executor's step of writing this SUMMARY was done by the orchestrator, since 26-09 is orchestrator-only.
- The fallback's push line uses `HEAD:main` instead of `"$branch:main"` (26-08 review; plan amended in db746465).
