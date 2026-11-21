---
phase: 33-registry-update-bot
verified: 2026-11-21T20:00:00Z
status: human_needed
score: 4/4 roadmap criteria verified by code and tests (live GitHub behavior, BOT-02 and the owner decisions listed as human items)
covered_files:
  - .claude/architecture.md
  - .claude/git-workflow.md
  - .github/dependabot.yml
  - .github/workflows/ci.yml
  - .github/workflows/registry-bot.yml
  - .planning/phases/33-registry-update-bot/33-01-PLAN.md
  - .planning/phases/33-registry-update-bot/33-01-SUMMARY.md
  - .planning/phases/33-registry-update-bot/33-02-PLAN.md
  - .planning/phases/33-registry-update-bot/33-02-SUMMARY.md
  - .planning/phases/33-registry-update-bot/33-03-PLAN.md
  - .planning/phases/33-registry-update-bot/33-03-SUMMARY.md
  - .planning/phases/33-registry-update-bot/33-04-PLAN.md
  - .planning/phases/33-registry-update-bot/33-04-SUMMARY.md
  - .planning/phases/33-registry-update-bot/33-05-PLAN.md
  - .planning/phases/33-registry-update-bot/33-05-SUMMARY.md
  - README.md
  - docs/registry-bot-proof.txt
  - installer/verify_registry.py
  - tests/test_ci_workflow.py
  - tests/test_registry_bot_workflow.py
  - tests/test_verify_registry.py
covered_digest: "v4:sha256:2ae867891bba14c60998951ca7582ff0e9f75093b05bc59e9227599f97d0be94"
behavior_unverified: 2
overrides_applied: 0
gaps: []
behavior_unverified_items:
  - truth: "A scheduled or dispatched bot run with drift pushes bot/registry-<date>; a run with no drift pushes nothing (SC1)"
    test: "Owner runs docs/registry-bot-proof.txt after the branch is on main (draw.io 32.6.10 vs 32.7.4 is real drift today)"
    expected: "Branch bot/registry-<UTC date> appears with one commit changing only installer/registry.toml; a rerun on the same base skips publication"
    why_human: "The workflow exists only as a file; it cannot be dispatched until it is on the default branch. Tests parse the YAML and pin step text but never execute the steps"
  - truth: "The checks branch protection requires run on the bot branch head (SC2, BOT-02)"
    test: "Option A or B of the runbook on a throwaway branch"
    expected: "Dispatched ci.yml check runs satisfy the classic protection for a fast-forward"
    why_human: "Live GitHub behavior, assumption A3; Option A needs a temporary protection write the owner must approve"
human_verification:
  - test: "One-time proof following docs/registry-bot-proof.txt after landing the branch on main: BOT-01 live behavior (branch with bumped version, sha256, verified; rerun skips)"
    expected: "Branch pushed, one commit, only registry.toml changed, CI dispatched on its head, identical rerun skips publication"
    why_human: "A workflow file must be on the default branch to be dispatched; the runbook is owner-run"
  - test: "BOT-02: do dispatched check runs satisfy classic protection for a fast-forward? Option A (throwaway protected branch) needs the owner's approval of a temporary protection write; Option B is UNVERIFIED (A3)"
    expected: "Fast-forward of the proof target accepted with only workflow_dispatch check runs; recorded in the runbook result block"
    why_human: "Live GitHub protection semantics; protection write needs owner approval"
  - test: "Closing keyword (`Closes #N`) on a fast-forward"
    expected: "Issue closes on the fast-forward, or the owner closes it by hand (documented fallback)"
    why_human: "Not exercised; no main push possible here (orchestrator decision 8)"
  - test: "First real bot run (draw.io 32.6.10 to 32.7.4)"
    expected: "Real bump branch with a verified digest; owner lands it by fast-forward after green CI"
    why_human: "Needs the live default branch and network"
  - test: "Follow-up commit that enables the cron (`37 6 * * 1`) and flips the trigger-set test"
    expected: "Schedule active; the trigger test updated in the same commit"
    why_human: "Deliberately deferred until the proof passes (D-12)"
  - test: "Owner follow-ups of the accepted dispatch boundary: a push restriction on the default branch; optionally app_id on the required contexts"
    expected: "The token can no longer push an already-green commit to main"
    why_human: "Repository settings, outside this phase and outside the code"
  - test: "Landing a Dependabot branch by fast-forward or closing its pull request (D-17, decision 7)"
    expected: "The owner never merges a Dependabot PR; branch is fast-forwarded (after `@dependabot rebase` if main moved) or the PR is closed"
    why_human: "Takes effect only on the default branch; owner act"
  - test: "Owner confirmation of the provisional decisions listed below (D-05, D-06, D-09, D-12, D-13, D-15, D-16, D-17, orchestrator decisions 1 to 10, review rounds, runbook form, skip-if-identical rerun, verified-date meaning)"
    expected: "Each confirmed, or reopened as a follow-up"
    why_human: "Flagged provisional or needs confirmation in the 33-0N summaries"
---

# Phase 33: Registry update bot - Verification Report

**Phase Goal:** Catalog pins in `installer/registry.toml` stop going stale between manual runs: a bot proposes each upstream bump as a branch with its digest already verified, and the owner lands it through the protected flow.
**Verified:** 2026-11-21
**Status:** human_needed
**Re-verification:** No, initial verification (after the review fix round `23c18383`, `b9fb7347`, `a7129e17`, `cb2dc1b5`)

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP criteria) | Status | Evidence |
| - | ------------------------ | ------ | -------- |
| 1 | A bot run with drift pushes `bot/registry-<date>` bumping `version`, `sha256`, `verified` together; no drift pushes nothing | VERIFIED in code, live run PRESENT_BEHAVIOR_UNVERIFIED (human) | `.github/workflows/registry-bot.yml`: branch `bot/registry-$(date -u +%F)`; `Bump pins` runs `verify_registry --write --bumps-only`, and tolerates exit 1/2 only when the output holds a `## ` report (review WR-01 fix, a launcher failure now fails the step); `Guard` sets `changed` from `git diff --quiet -- installer/registry.toml` (exit 0 -> false, 1 -> true, other -> fail); every publishing step is gated on `changed == 'true'`. `Publish` commits only `installer/registry.toml` and pushes with `--force-with-lease=refs/heads/$BRANCH:$EXPECTED`. Compare step skips only an identical commit on the current base (one parent equal to HEAD, diff names only registry.toml). Tests in `tests/test_registry_bot_workflow.py` (865 lines) pin this text. No step executes against GitHub here. |
| 2 | Required checks run on the bot branch head (verified once on a throwaway branch); the drift workflow keeps `contents: read` | Code VERIFIED; the throwaway-branch proof is HUMAN | `ci.yml:9` has a bare `workflow_dispatch:`; `registry-bot.yml` `Dispatch CI` does `gh workflow run ci.yml --ref "$BRANCH"` with one retry, plus a redispatch for an unchanged branch unless a queued, running or successful run exists for its head; `permissions: actions: write` carries it. `verify-registry.yml:13-14` is `contents: read` / `issues: write` (unchanged; test passes). The one-time proof is the runbook `docs/registry-bot-proof.txt` (267 lines): preflight, origin-URL check, Option A (main's protection read and mapped, `required_signatures` handled, STOP on any enabled setting it cannot map, REST paths use `proof%2Ftarget-$DATE`, skip verified through `gh run view --json jobs`), Option B marked UNVERIFIED, cleanup. Not run: owner-run after landing (BOT-02 live). |
| 3 | No bot token pushes to `main`; change reaches `main` only by branch push, green CI and fast-forward | VERIFIED structurally, dispatch boundary accepted | Workflow targets only `refs/heads/$BRANCH` and deletes only `refs/heads/bot/registry-*` (full-prefix case, expected-SHA lease, only after a successful dispatch); a test guards that no step targets the default branch. `.claude/git-workflow.md` and README describe the landing. Honest limit in the workflow header and the issue body: the repository sets no push restriction, so a dispatched ref running its own code could push an already-green commit to main; it is an owner act and the push restriction is an owner follow-up (human item). |
| 4 | `--write` with a date-only change leaves `registry.toml` unchanged (unit test) | VERIFIED | `installer/verify_registry.py` `--bumps-only`; help text confirmed by `uv run python -m installer.verify_registry --help` (requires `--write`; "verified certifies the bumped pins only"); `--bumps-only` without `--write` exits 64 (ran, rc=64). `tests/test_verify_registry.py` (464 added lines): byte-identical date-only fixture vs the same fixture without the flag, real bump, both file orders with an old date (WR-04 fix), no drift, drifted neighbour, two methods, failed and no-op candidates, raw pinned download with a nonempty `member` (lane 2 fix). 4 test files run: all passed. |
| 5 | SPEC R5: Dependabot for GitHub Actions | VERIFIED | `.github/dependabot.yml`: one weekly `github-actions` entry at `/`, an `actions` group `*` (D-17). Takes effect only on the default branch (human item). |
| 6 | Review fix round landed (WR-01..04, lanes 1-5, 7, 9, 11-13, IN-01, 02, 04, 08, 09) and security audit | VERIFIED | Commits `23c18383`, `b9fb7347`, `a7129e17`, `cb2dc1b5` after `d8f7f225`; the bump step, compare step, recorded published SHA step, `%2F` paths, `required_signatures`, `jobs` conclusion check are present in the files (counts in the runbook: 3, 5, 3). `33-SECURITY.md` status verified, SECURED 17/17, 0 open. Deferred: lane 10 (backlog 999.33); accepted: lanes 6, 8, IN-03, 05, 06, 07. |

**Score:** 4/4 roadmap truths verified by code and tests (plus the SPEC R5 item and the fix round); 2 truths (live bot behavior, BOT-02 protection outcome) present and wired but not exercised, listed as behavior-unverified and routed to the owner.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `.github/workflows/registry-bot.yml` | dispatch-only bot, exact permissions, cron commented | VERIFIED | 194 lines; `contents/actions/issues: write`; cron committed commented out (D-12) |
| `.github/workflows/ci.yml` | bare `workflow_dispatch` | VERIFIED | line 9 |
| `.github/workflows/verify-registry.yml` | stays `contents: read` | VERIFIED | lines 13-14 |
| `.github/dependabot.yml` | weekly github-actions group | VERIFIED | |
| `installer/verify_registry.py` | `--bumps-only` | VERIFIED | help, rc 64 check |
| `docs/registry-bot-proof.txt` | owner-run runbook | VERIFIED (plain text by deviation) | 267 lines |
| `tests/test_registry_bot_workflow.py`, `tests/test_ci_workflow.py`, `tests/test_verify_registry.py` | file-level tests | VERIFIED | pass |
| `.claude/architecture.md`, `.claude/git-workflow.md`, `README.md` | docs of the bot, landing, pin-only `verified` | VERIFIED | changed in phase |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| `registry-bot.yml` Bump step | `installer.verify_registry --write --bumps-only` | `uv run --isolated --no-dev python -m` | WIRED |
| Guard output | all publish, issue, dispatch steps | `steps.guard.outputs.changed` | WIRED |
| Publish | Dispatch CI | same job; `gh workflow run ci.yml --ref "$BRANCH"` | WIRED (live: human) |
| Dispatch/redispatch success | old-branch deletion | `steps.dispatch.outcome` / `redispatch.outcome` | WIRED |
| Runbook | workflow and config | `tests/test_registry_bot_workflow.py` (text agreement) | WIRED |

### Data-Flow Trace (Level 4)

The pin values come from `verify_registry` download and hashing; the bot only commits the resulting `registry.toml`. Not traceable live here.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase test files | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry.py tests/test_verify_registry_workflow.py --no-cov -q -n 4`, scratch TMPDIR | all passed (4 files, ~220 tests, 0 failed) | PASS |
| Flag documented | `uv run python -m installer.verify_registry --help` | `--bumps-only` described, exit 64 listed | PASS |
| Flag needs `--write` | `uv run python -m installer.verify_registry --bumps-only` | rc 64 | PASS |
| Drift workflow permissions | read `verify-registry.yml` | `contents: read` | PASS |
| Debt markers | grep TBD/FIXME/XXX in workflow, runbook, dependabot, verify_registry.py | none | PASS |
| actionlint (D-16 ad-hoc check) | orchestrator, image rhysd/actionlint:1.7.12, local files, 2026-11-21 before and after the fix round, on `ci.yml`, `registry-bot.yml`, `verify-registry.yml` | clean, rc 0, no findings | PASS (recorded by orchestrator; not re-run here) |
| Full suite | not re-run here | SKIPPED |

### Probe Execution

SKIPPED: no `probe-*.sh` declared. No container, make target, push or `gh` call was made in this verification.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| BOT-01 | Dispatched/scheduled workflow, branch only when changed, bumped together | SATISFIED in code; live behavior human | Truth 1 |
| BOT-02 | Required checks run on the bot head, verified once on a throwaway branch | CODE SATISFIED (dispatch path); proof NEEDS HUMAN | Truth 2 |
| BOT-03 | Never pushes to main; drift workflow `contents: read` | SATISFIED (structural), dispatch boundary accepted | Truth 3 |
| BOT-04 | `--bumps-only` skips date-only writes | SATISFIED | Truth 4 |
| SPEC R5 | Dependabot item | SATISFIED | Truth 5 |

No orphaned requirements. REQUIREMENTS.md still reads Pending and the ROADMAP checkbox is unchecked; `phase.complete` is the orchestrator's after the human items.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `.github/workflows/registry-bot.yml` | 10-12 | Dispatched ref runs its own code with the write token; no push restriction on main | Info (accepted, AR) | owner follow-up |
| `.github/workflows/registry-bot.yml` | 18-19 | cron commented out | Info | by design (D-12) |
| `.github/workflows/registry-bot.yml` | actions pinned by tag, not SHA | Info | repo convention (lane 8, AR-33-04), Dependabot bumps |
| `docs/registry-bot-proof.txt` | whole | Plain text runbook, never executed; echo guards do not halt | Info | stated at line 8; owner runs it by hand |
| `installer/verify_registry.py` | n/a | Lane 10 (shared-URL pinned and unpinned methods) | Info | deferred, backlog 999.33 |

No TBD, FIXME or XXX added. No blockers.

### Human Verification Required

See the front matter list (8 items): the owner-run proof (BOT-01, BOT-02), the unexercised closing keyword, the first real bot run, the cron-enabling follow-up, the dispatch-boundary follow-ups, the Dependabot landing, and the owner confirmation of the provisional decisions.

#### Provisional decisions awaiting owner confirmation

From the 33-01..05 summaries ("Provisional decisions"), the review triage and the orchestrator:

1. D-05: delete older bot branches only after a successful dispatch or redispatch, full-prefix check, expected-SHA lease; one live bot branch.
2. D-06: concurrency group `registry-bot`, one running and the latest pending run.
3. D-09: share the verify-registry state cache with the drift workflow (a speed-up, not an ordering guarantee, decision 4).
4. D-12 and orchestrator decision 1: dispatch-only until the owner's proof passes; cron enabled in a follow-up commit.
5. D-13 (with review H1, M5, M6, M7): `--bumps-only` requires `--write`; a bumped tool is dated even if another of its findings stays drifted; the `verified` date certifies the bumped pins only; no-op candidates earn nothing; the flag can add a date an unflagged run omitted.
6. D-15 and decision 2: new tests own `_load`/`_triggers` helpers; D-10 as amended: the two `tests/test_ci_workflow.py` assertions (trigger set, checkout pin).
7. D-16 and decision 6: no new lint gate; `actionlint` is the orchestrator's ad-hoc check (recorded clean above); permanent gate deferred to backlog 999.23.
8. D-17 and decision 7: Dependabot for `github-actions` (weekly, one group, `/`), opening PRs the owner never merges (fast-forward its branch or close the PR); assumption A7.
9. Decision 8: closing keyword on a fast-forward not exercised; the owner may close the issue by hand.
10. Decisions 3, 4, 5, 9, 10: reconciled catalog counts (nine versioned methods, six auto-bumpable); off-minute cron without ordering assumption; ls-remote probe, explicit refspec fetch and expected-SHA lease; 90-minute job and 75-minute bump timeouts; tests work on Python 3.12 and 3.15 with no network (3.15 and macOS not run locally).
11. Runbook-as-plain-text-file deviation (`docs/registry-bot-proof.txt`, not a script and not Markdown); Option A needs a protection write the owner approves; Option B UNVERIFIED; no stale-pin fixture (relies on real drift); owner-run after landing.
12. Skip-if-identical rerun: an identical file on an unchanged base skips publication and redispatches CI only when no queued, running or successful run exists for that head.
13. The `verified` date meaning after a bump (pins of the bumped tool only), documented in README, architecture guide and the help text.
14. The accepted dispatch boundary and guarded deletion; the push restriction on the default branch is an owner follow-up.
15. Review triage fixes taken as FIX (WR-01..04, lanes) and the owned-TMPDIR finding rejected for the third time.

### Gaps Summary

No gaps. Every roadmap criterion is backed by code and by passing file-level tests; the exit-code and flag behavior were re-checked by running the module. Status is `human_needed` because the bot and its protection outcome can only be proved on GitHub after the branch is on `main`, and because the provisional decisions need the owner. Residual risk: workflow steps are pinned by text tests, never executed (WR-01-style launcher failures were fixed by reading text; the live proof is the real check); the full suite and Python 3.15 were not re-run here; ROADMAP and REQUIREMENTS still show Pending.

---

_Verified: 2026-11-21_
_Verifier: Claude (gsd-verifier)_
