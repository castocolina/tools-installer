# Phase 33: Registry update bot — Specification

**Created:** 2026-11-19
**Ambiguity score:** 0.17 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

Catalog pins in `installer/registry.toml` stop going stale between manual runs: a scheduled bot pushes each upstream bump as a `bot/registry-<date>` branch with its digest already verified, announces it in one tracking issue, and the owner lands it through the protected flow.

## Background

- Pins go stale until someone runs `make verify-registry ARGS="--write"`; five methods carry a `version` today (`rg -c '^version *=' installer/registry.toml` = 5). `installer/verify_registry.py` already bumps `version`, `sha256` and `verified` together after verifying a candidate (edit keys `verified`, `version`, `sha256`, `installer/verify_registry.py:63`); its parser has flags at `:1551-1565`.
- `.github/workflows/verify-registry.yml` is the weekly read-only drift report (`permissions: contents: read, issues: write`, cron Monday 05:17 and Thursday 05:47 UTC); it only upserts one `registry-drift` issue and never writes the repo.
- `main` is protected (`enforce_admins`, strict checks): a change lands only by branch push, green CI on `ubuntu-latest` and `macos-latest` (`.github/workflows/ci.yml`), then a fast-forward by the owner.
- A push made with the default workflow token starts no workflow run (except a dispatch). A real pull request cannot be fast-forward merged from the web UI, and creating one from a workflow needs a repository setting that is off by default.
- `--write` re-dates every passing tool, so without a flag every bot branch would carry date-only diffs.
- `tests/test_verify_registry_workflow.py` and `tests/test_verify_registry.py` exist and are the pattern for workflow and bump tests. Dependabot cannot parse `registry.toml`; Renovate cannot refresh the paired `sha256` (research: `.planning/research/2026-11-17-update-automation.md`, feature 3).
- Phases 30 and 32 add more pinned methods (Ghostty, Bruno AppImages); the bot covers them once they land.
- Live facts (2026-11-19): the bot can auto-bump only drawio-desktop (2 of the 5 pinned methods); Sublime publishes no latest URL and is bumped by hand with `--candidate`. Branch protection requires the two named checks, `strict` and `enforce_admins`, with no push restrictions and no required reviews.

## Requirements

1. **Bot workflow and branch (BOT-01)**: A scheduled or manually dispatched GitHub Actions workflow runs `verify-registry --write`; when `installer/registry.toml` changed it pushes a `bot/registry-<date>` branch carrying the change and opens or updates one tracking issue naming that branch; when nothing changed it pushes nothing and opens nothing. A bumped pin changes `version`, `sha256` and `verified` together.
   - Current: only the drift-report workflow exists.
   - Target: a new `.github/workflows/registry-bot.yml` (name chosen in discuss).
   - Acceptance: a workflow test asserts the trigger set, that the push step is guarded by a changed-file check, and that no publishing step (push, issue, dispatch) runs when the diff is empty *(amended 2026-11-19, 33 D-03: a cache-save step may still run)*; a bump fixture shows the three keys change in one commit; a dispatched run on a throwaway fork or branch with drift pushes exactly one `bot/registry-<date>` branch and a rerun the same day updates it instead of creating a second.

2. **Required checks run on the bot branch (BOT-02)**: The required checks (`validate & test on ubuntu-latest` and `macos-latest`) run on the bot branch head by a `workflow_dispatch` of `ci.yml` issued by the bot, with no stored token; the dispatch is proved once on a throwaway branch before the phase is done, and if it does not satisfy the required checks the phase stops and the owner chooses a token route.
   - Current: `ci.yml` has no manual-dispatch trigger (verify in discuss) and the satisfaction of required checks by a dispatched run is unverified.
   - Target: `ci.yml` gains `workflow_dispatch` and the bot dispatches it on the bot branch.
   - Acceptance: a workflow test asserts `ci.yml` declares `workflow_dispatch` and the bot's dispatch step names the bot branch; a one-time throwaway-branch run is recorded in the phase verification with the check names reported by GitHub for the branch head.

3. **The bot never reaches main (BOT-03)**: No bot token or step pushes to `main`; the change reaches `main` only by branch push, green CI and the owner's fast-forward; the weekly drift workflow keeps `contents: read`.
   - Current: the drift workflow already has `contents: read`.
   - Target: the bot workflow's permissions are the least that let it push its own branch, dispatch CI and write one issue; no step names `main` as a push target.
   - Acceptance: a workflow test asserts no `git push` or API call targets `main`, the bot's permissions list, and `verify-registry.yml` still declares `contents: read`.

4. **Date-only noise flag (BOT-04)**: A `verify-registry` flag makes a `--write` run skip changes that only touch the `verified` date, so a bot branch never carries a date-only diff.
   - Current: `--write` re-dates every passing tool.
   - Target: a flag (name chosen in discuss) the bot passes.
   - Acceptance: a unit test with a registry whose only drift is a `verified` date leaves `registry.toml` byte-identical with the flag and changes it without the flag; a test with a real version bump changes all three keys with the flag.

5. **Actions-version updates (added by the interview)**: A minimal `.github/dependabot.yml` keeps the repository's own GitHub Actions versions current through the `github-actions` ecosystem.
   - Current: no `dependabot.yml`.
   - Target: a file of about six lines for `github-actions`, weekly.
   - Acceptance: a test parses the file and asserts exactly one `github-actions` update entry with a schedule; no `pip`, `uv` or `npm` ecosystem is declared.

## Boundaries

**In scope:**
- The bot workflow, the `ci.yml` dispatch trigger, the date-only flag with its tests, the tracking issue step, and `.github/dependabot.yml`.
- One throwaway-branch proof that a dispatched CI run satisfies the required checks.
- *Amended 2026-11-19 (33 D-10):* the two assertions of `tests/test_ci_workflow.py` that conflict (the trigger set at line 41, the exact `actions/checkout@v4` match at line 52).

**Out of scope:**
- Auto-landing the bot branch — the owner lands (BOT-03).
- A real pull request — branch plus issue only, matching the fast-forward flow.
- Bumping pins for tools without a `version` pin, or changing what `verify-registry` verifies.
- Renovate or a dependency-update service for `registry.toml`.
- The daily update notification and auto-update — phases 34 and 35.

## Constraints

- No stored secret is introduced unless the throwaway test fails and the owner chooses a token route.
- Workflow changes pass `actionlint`-class review through the existing gates and the workflow tests; `make validate && make test` pass on the commit.
- The proof push goes to a throwaway branch that is deleted afterwards; nothing is pushed to `main`.
- Network access is needed only by the workflow itself; unit tests use fixtures.

## Acceptance Criteria

- [ ] Workflow tests pass for triggers, the changed-file guard, permissions and the no-`main` rule.
- [ ] A bump fixture changes `version`, `sha256` and `verified` together in one commit.
- [ ] A rerun the same day updates the existing bot branch and tracking issue instead of creating new ones.
- [ ] `ci.yml` declares `workflow_dispatch` and the bot dispatches it on its branch.
- [ ] The throwaway-branch proof is recorded: a dispatched run reports the required check names on the branch head (or the phase stops for an owner decision).
- [ ] The date-only flag leaves a date-only diff unchanged and still applies a real bump.
- [ ] `verify-registry.yml` still declares `contents: read`.
- [ ] `.github/dependabot.yml` has one `github-actions` entry and no other ecosystem.

## Edge Coverage

**Coverage:** 19/19 applicable edges resolved · 0 unresolved

| Category | Requirement | Status | Resolution / Reason |
|----------|-------------|--------|---------------------|
| adjacency | R1 | ✅ covered | Acceptance 3: two runs the same day target the same bot/registry-<date> branch, so an update replaces rather than adds a second branch |
| empty | R1 | ✅ covered | Acceptance 1: an empty diff pushes nothing and opens no issue (guarded step, workflow test) |
| encoding | R1 | ✅ covered | Acceptance 2: the bump fixture compares sha256 as lowercase hex and version as the exact string verify-registry wrote |
| ordering | R1 | ✅ covered | Acceptance 2: the three keys are asserted as a set per method, independent of edit order |
| idempotency | R1 | ✅ covered | Acceptance 3: a same-day rerun with identical content updates the same branch and adds no second branch, issue or commit |
| concurrency | R1 | 🧪 backstop | held-out test: the workflow declares a concurrency group so a scheduled and a dispatched run cannot push the same branch at once |
| empty | R2 | ✅ covered | Acceptance 4 and 5: no bot branch means no dispatch; a dispatch without the branch name fails the workflow test |
| encoding | R2 | ✅ covered | Acceptance 5: the check names recorded are compared exactly as GitHub reports them (`validate & test on ubuntu-latest`, `validate & test on macos-latest`) |
| adjacency | R3 | ✅ covered | Acceptance 1: the permissions list is asserted exactly; a neighbouring write permission such as `contents: write` on the drift workflow fails its test |
| empty | R3 | ✅ covered | Acceptance 1: a workflow with no push step passes the no-main assertion vacuously only if it has no push at all, otherwise the target is asserted |
| encoding | R3 | ✅ covered | Acceptance 1: the ref comparison is exact (`refs/heads/main`, `main`, `HEAD:main` all rejected) |
| ordering | R3 | ✅ covered | Acceptance 1: assertions run over every step regardless of order |
| concurrency | R3 | 🧪 backstop | held-out test: protection has no push restrictions (checked live 2026-11-19), so the guard is the workflow content: no step targets main, asserted by the workflow test |
| adjacency | R4 | ✅ covered | Acceptance 6: a change touching `verified` and `version` together counts as a real bump; only a lone `verified` change is skipped |
| empty | R4 | ✅ covered | Acceptance 6: a registry with no drift is unchanged with or without the flag |
| encoding | R4 | ✅ covered | Acceptance 6: dates compare as exact ISO strings (YYYY-MM-DD) |
| ordering | R4 | ✅ covered | Acceptance 6: methods are matched by tool id and index, not by file order |
| idempotency | R5 | ✅ covered | Acceptance 8: the dependabot test is a pure parse, so repeated runs give the same result |
| concurrency | R5 | 🧪 backstop | held-out test: read-only parse of the file under xdist |

## Prohibitions (must-NOT)

**Coverage:** 3/3 applicable prohibitions resolved · 0 unresolved

| Prohibition (must-NOT statement) | Requirement | Status | Verification / Reason |
|----------------------------------|-------------|--------|------------------------|
| The bot MUST NOT push to `main` or merge its own branch | 3 | resolved | test: workflow test finds no push or merge targeting `main` |
| The bot MUST NOT commit a registry change that bumps `version` without the matching `sha256` | 1 | resolved | test: bump fixture asserts the three keys move together; `verify-registry` refuses an unverified candidate |
| The bot MUST NOT print or persist a token in logs, the branch or the issue body | 1 | resolved | judgment (review of the workflow; the default token is masked by Actions) |

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes |
|--------------------|-------|------|--------|-------|
| Goal Clarity       | 0.90  | 0.75 | ✓      | Todo and roadmap are specific |
| Boundary Clarity   | 0.85  | 0.70 | ✓      | Owner-lands, branch plus issue, dispatch route decided |
| Constraint Clarity | 0.75  | 0.65 | ✓      | Dispatch acceptance of required checks proved once; flag names left to discuss |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | Workflow tests plus one recorded live proof |
| **Ambiguity**      | 0.17  | ≤0.20| ✓      | |

## Interview Log

Auto path, one round. The open items went through jev: one advisory answer per item, and `needs_fallback` items are decided by own reasoning. Summaries only, advisory. Rule: mvp-mode inactive, the best design wins over the smallest diff.

| Round | Perspective | Question summary | jev (advisory) | Decision locked |
|-------|-------------|------------------|----------------|-----------------|
| 1 | Simplifier | OQ-BOT-1: how does the bot present its change (branch plus issue, real PR, branch only)? | low 0.35 (branch_only); second rung choice branch_plus_issue 0.94 | Branch plus one tracking issue (R1); matches the fast-forward flow and the existing drift issue |
| 1 | Boundary Keeper | OQ-BOT-2: dispatched CI vs a stored token for the required checks? | none_of_these 0.77 (contradicts the evidence); second opinion dispatch_ci 0.89 | **jev overridden:** dispatch, proved once on a throwaway branch; token route only if the proof fails (R2) |
| 1 | Boundary Keeper | OQ-BOT-5: add the `github-actions` Dependabot config in this phase? | noul yes 0.89 | Yes (R5) |
| 1 | Boundary Keeper | OQ-BOT-3 (owner lands) and OQ-BOT-4 (date-only noise) | none | Locked by BOT-03 and BOT-04 as written (R3, R4); the owner lands, date-only diffs are skipped |

---

*Phase: 33-registry-update-bot*
*Spec created: 2026-11-19*
*Next step: /gsd-discuss-phase 33 — implementation decisions (how to build what's specified above)*
