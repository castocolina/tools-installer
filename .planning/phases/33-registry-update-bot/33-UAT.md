---
status: testing
phase: 33-registry-update-bot
source: [33-VERIFICATION.md]
started: 2026-11-21T22:00:00Z
updated: 2026-11-21T22:00:00Z
---

## Current Test

number: 1
name: One-time proof following docs/registry-bot-proof.txt after landing the branch on main: BOT-01 live behavior (branch with bumped version, sha256, verified; rerun skips)
expected: |
  Branch pushed, one commit, only registry.toml changed, CI dispatched on its head, identical rerun skips publication
awaiting: the owner, after landing the branch on main (an agent cannot dispatch a workflow that is not on the default branch, and no agent writes to the remote or merges to main; no agent may mark any of these passed)

## Tests

### 1. One-time proof following docs/registry-bot-proof.txt after landing the branch on main: BOT-01 live behavior (branch with bumped version, sha256, verified; rerun skips)
expected: Branch pushed, one commit, only registry.toml changed, CI dispatched on its head, identical rerun skips publication
why_human: A workflow file must be on the default branch to be dispatched; the runbook is owner-run
result: [pending]

### 2. BOT-02: do dispatched check runs satisfy classic protection for a fast-forward? Option A (throwaway protected branch) needs the owner's approval of a temporary protection write; Option B is UNVERIFIED (A3)
expected: Fast-forward of the proof target accepted with only workflow_dispatch check runs; recorded in the runbook result block
why_human: Live GitHub protection semantics; protection write needs owner approval
result: [pending]

### 3. Closing keyword (`Closes #N`) on a fast-forward
expected: Issue closes on the fast-forward, or the owner closes it by hand (documented fallback)
why_human: Not exercised; no main push possible here (orchestrator decision 8)
result: [pending]

### 4. First real bot run (draw.io 32.6.10 to 32.7.4)
expected: Real bump branch with a verified digest; owner lands it by fast-forward after green CI
why_human: Needs the live default branch and network
result: [pending]

### 5. Follow-up commit that enables the cron (`37 6 * * 1`) and flips the trigger-set test
expected: Schedule active; the trigger test updated in the same commit
why_human: Deliberately deferred until the proof passes (D-12)
result: [pending]

### 6. Owner follow-ups of the accepted dispatch boundary: a push restriction on the default branch; optionally app_id on the required contexts
expected: The token can no longer push an already-green commit to main
why_human: Repository settings, outside this phase and outside the code
result: [pending]

### 7. Landing a Dependabot branch by fast-forward or closing its pull request (D-17, decision 7)
expected: The owner never merges a Dependabot PR; branch is fast-forwarded (after `@dependabot rebase` if main moved) or the PR is closed
why_human: Takes effect only on the default branch; owner act
result: [pending]

### 8. Owner confirmation of the provisional decisions listed below (D-05, D-06, D-09, D-12, D-13, D-15, D-16, D-17, orchestrator decisions 1 to 10, review rounds, runbook form, skip-if-identical rerun, verified-date meaning)
expected: Each confirmed, or reopened as a follow-up
why_human: Flagged provisional or needs confirmation in the 33-0N summaries
result: [pending]
