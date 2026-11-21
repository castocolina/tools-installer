---
phase: 33-registry-update-bot
reviewed: 2026-11-21T00:00:00Z
depth: deep
files_reviewed: 11
files_reviewed_list:
  - .claude/architecture.md
  - .claude/git-workflow.md
  - .github/dependabot.yml
  - .github/workflows/ci.yml
  - .github/workflows/registry-bot.yml
  - README.md
  - docs/registry-bot-proof.txt
  - installer/verify_registry.py
  - tests/test_ci_workflow.py
  - tests/test_registry_bot_workflow.py
  - tests/test_verify_registry.py
findings:
  critical: 0
  warning: 4
  info: 9
  total: 13
  necessity: 0
status: issues_found
---

# Phase 33: Code Review Report

**Reviewed:** 2026-11-21
**Depth:** deep
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Scope: `ff3cedb5..HEAD` in the 11 files above, plus the called code (`installer/verify_registry.py` bump and state paths, `devtools/push_gate.py`, `devtools/docs_only.py`, `.github/workflows/verify-registry.yml`, `.git/hooks/pre-push`).

The git mechanics of `registry-bot.yml` are sound. I reproduced them in scratch bare repos from my own shell, all removed afterwards: `ls-remote` with an absent ref exits 0 with no output; `--force-with-lease=<ref>:` (empty expect) creates an absent branch and rejects a present one ("stale info"); the leased update and the leased deletion work from a `--depth 1` clone; a bot branch based on an older main is fetched into a shallow clone and `expected^` differs from `HEAD` (so `same=false`); a `git ls-remote 'refs/heads/bot/registry-*'` also returns `refs/heads/x/refs/heads/bot/registry-zzz` (tail match) and the `case` in the delete loop correctly routes it to the "ignoring" branch. `shellcheck -s bash -S style` over every extracted `run:` body is clean. `gh --jq 'env.FOO'` works (gh 2.101), so the `env.EXPECTED` filter in the redispatch step is valid. `gh run list` has `--commit`, `--event`, `--branch` and the JSON fields used. No `${{ }}` reaches a `run:` body; `GH_TOKEN` is job env only; the implicit `success()` on the `if:` expressions without a status function gives the intended skip behavior. The new tests (`test_verify_registry.py`, `test_registry_bot_workflow.py`, `test_ci_workflow.py`) plus `test_verify_registry_workflow.py`, `test_docs.py`, `test_docs_only.py`, `test_makefile.py`, `test_registry.py` pass here.

Defects that survive: the bump step turns launcher failures into a silent green no-op (WR-01); one runbook "must skip" assertion cannot fail (WR-02); the proof's throwaway protection is hand-written from a partial read of main's protection, so an Option A pass does not bound main's behavior (WR-03); one new unit test cannot distinguish the flag from no flag, which I proved by mutation (WR-04). No finding reopens D-05, D-06, D-09, D-12, D-16, D-17, the owner-run proof, the dispatch boundary, BOT-02 or the unexercised closing keyword. The `actionlint` run of decision 6 was not done here (no binary on the host).

## Warnings

### WR-01: The bump step treats any exit 1 or 2 as "verify-registry finished", so a launcher failure is a silent green no-op

**File:** `.github/workflows/registry-bot.yml:53-55`
**Issue:** The step tolerates exit codes 0, 1 and 2 (D-02: 1 is drift, 2 is inconclusive). Those codes are not owned by `verify_registry`: `uv` itself exits 2 on any error, and Python exits 1 for an import error or a missing module, before `main()` can map anything to 70. Reproduced read-only: `UV_PYTHON_DOWNLOADS=never uv run --no-project --python 9.99 python -V` prints "No interpreter found" and exits 2 (uv 0.11.28); `python3 -m installer.nonexistent` fails with "No module named" (exit 1). In the workflow both are swallowed by `case "$code" in 0|1|2) ;;`, the Guard then sees an unchanged `installer/registry.toml` (`changed=false`), every publishing step is skipped, and the job finishes green. A uv resolution failure, a broken `pyproject.toml` on the dispatched ref, or a persistent GitHub rate-limit block (a genuine exit 2 with no bump) therefore looks identical to "nothing to bump", every week, with no annotation and no issue comment. The Report step only fires on publish/dispatch failures. The workflow tests pin the exact `case` text (`tests/test_registry_bot_workflow.py:138-151`) and never execute it, so nothing catches this.
**Fix:** Separate launch failures from verify-registry exit codes and surface the inconclusive case, for example a preflight plus an annotation:
```yaml
      - name: Bump pins
        id: bump
        timeout-minutes: 75
        run: |
          uv run --isolated --no-dev python -c "import installer.verify_registry"
          code=0
          uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only || code=$?
          case "$code" in
            0|1) ;;
            2) echo "::warning::verify-registry was inconclusive (exit 2): no pin was proved" ;;
            *) echo "verify-registry exited $code" >&2; exit "$code" ;;
          esac
```
(Update the pinned text in `test_the_bump_step_runs_the_flag_directly`.) The import preflight does not cover a uv failure inside the second `uv run`, but both share the same environment, so the first call fails the job first.

### WR-02: The runbook's same-day-rerun "skip" check greps text that the step's own script contains, so it always matches

**File:** `docs/registry-bot-proof.txt:113`
**Issue:** `gh run view "$BOT_RUN2" --log | grep "nothing to publish"` is meant to prove the second run took the `same=true` path. The searched string is a literal inside the Compare step's `run:` script (`.github/workflows/registry-bot.yml:75`), and `gh run view --log` prints each step's script in its `##[group]Run ...` header. I confirmed that on a real run of this repository (run 43877708751): `gh run view 43877708751 --log | grep -F 'make verify-registry ARGS'` matches `##[group]Run make verify-registry ARGS="--issue"` and its continuation line. Because the Compare step executes in every changed run, its header always carries "nothing to publish", whether or not `same` was true. The command therefore cannot fail, and the runbook says the rerun "must skip". The lines after it (SHA equals `SHA_FIRST`, `N` unchanged, one branch, one issue) do corroborate the outcome, but the explicit positive check is vacuous and `test_the_runbook_binds_its_evidence_to_run_ids` pins it (`tests/test_registry_bot_workflow.py:613`).
**Fix:** Make the log line differ from the script text by including a value only known at run time, then grep for that value. In the workflow: `echo "The bot branch already holds this change on the current base ($expected): nothing to publish."`; in the runbook: `gh run view "$BOT_RUN2" --log | grep -F "($SHA_FIRST): nothing to publish"`. Alternatively read the step's `conclusion` of `Upsert the tracking issue` (`skipped`) with `gh run view --json jobs`.

### WR-03: The Option A throwaway protection is hand-written, so an accepted push does not bound what main will do

**File:** `docs/registry-bot-proof.txt:99-102,140-153`
**Issue:** BOT-02 asks whether dispatched check runs let a fast-forward through main's classic protection. The runbook reads main's protection only through `.required_status_checks.checks[].context` (line 100) and then writes a different, hand-built body to `proof/target-$DATE` (strict, two contexts, `enforce_admins`, no reviews, no restrictions). Everything else main might enforce is neither read nor reproduced: `required_signatures` (the bot commit is made by the `git` CLI under the workflow token, so it is unsigned; an Option A pass says nothing about whether main would refuse it), `required_linear_history`, `allow_force_pushes`/`allow_deletions`, or an `app_id` pin on the checks. The read-back at line 151 only checks the three fields the runbook itself set, so it confirms the PUT, not equivalence with main. A pass would be recorded as BOT-02 passed (line 210) and the first real landing could still be refused.
**Fix:** Add read-only comparisons before Option A and STOP on a mismatch, and build the PUT body from main's read-back instead of writing it by hand:
```sh
gh api repos/$REPO/branches/main/protection --jq '{strict: .required_status_checks.strict, checks: .required_status_checks.checks, admins: .enforce_admins.enabled, sigs: .required_signatures.enabled, linear: .required_linear_history.enabled, force: .allow_force_pushes.enabled, restr: .restrictions}'
```
Expect `sigs` and `linear` false/absent and `checks` to carry no unexpected `app_id`; otherwise STOP and take it to the owner. These are GET calls and do not touch main's protection.

### WR-04: `test_bumps_only_leaves_a_registry_with_no_drift_unchanged` cannot fail when the flag is ignored

**File:** `tests/test_verify_registry.py:3278-3297`
**Issue:** The fixture's only tool is re-dated to `2026-10-15` and the run uses `today=date(2026, 10, 15)`. A plain `--write` therefore rewrites `verified = 2026-10-15` over the same text, and the test asserts byte equality for both the flagged and the plain pass. The flagged half would pass with the flag implemented, ignored or reversed. Reproduced by mutation: a scratch pytest plugin in a temp directory (deleted afterwards) patched `_registry_edits_for_write` to force `bumps_only=False`; under that mutation `test_bumps_only_leaves_a_date_only_write_byte_identical`, `..._dates_only_the_bumped_tool_whatever_the_file_order`, `..._dates_a_bumped_tool_whose_other_finding_stays_drifted` and `..._does_not_date_a_same_version_same_digest_candidate` fail, while this test still passes. The behavior is covered by the first of those, so this is a vacuous test rather than a coverage hole, but it reads as the "no drift" case of D-14 and is not.
**Fix:** Make the stale date differ so the plain pass would write: keep `2026-10-01` in the content, and assert `registry.read_bytes() == before` only for the flagged pass while asserting the plain pass changed it (as `test_bumps_only_leaves_a_date_only_write_byte_identical` does), or delete the test as a duplicate.

## Info

### IN-01: `README.md` project layout still describes CI as push-only

**File:** `README.md:381`
**Issue:** `.github/workflows/ci.yml   # CI: on every branch push except main` is now incomplete (`workflow_dispatch` was added, `.github/workflows/ci.yml:9`). The layout also omits `registry-bot.yml`, `verify-registry.yml` and `dependabot.yml`, which the new section at README.md:353-357 describes.
**Fix:** `# CI: every branch push except main, plus the bot's dispatch` and a one-line entry for the bot workflow and Dependabot config.

### IN-02: `changes_registry` is an inline generator that re-derives the edit quoting and carries a dead branch

**File:** `installer/verify_registry.py:1326-1342`
**Issue:** The no-op test strips `"` from `edit.value` and lowercases `sha256` on both sides inside a 17-line generator in `_plan_bumps`. It duplicates the quoting that `_build_bump_edits` applies at line 1210-1211, so a change to the edit value format silently flips the flag. `edit.method_index is None` can never be true for bump edits (only `verified` edits have `None`, built later at line 1354), so that clause is dead.
**Fix:** Compute the flag where the values are known, e.g. in `_build_bump_edits` return `(edits, changed)` with `changed = candidate != params_version or finding.sha256.lower() != str(params.get("sha256", "")).lower()` per method, and drop the string-strip comparison.

### IN-03: `id: bump` is never read

**File:** `.github/workflows/registry-bot.yml:50`
**Issue:** No expression references `steps.bump`; the Guard uses `git diff`. The id exists only because `test_the_bump_step_runs_the_flag_directly` asserts it (`tests/test_registry_bot_workflow.py:140`). If WR-01 is fixed with an output (for example `inconclusive=true`), the id becomes useful; otherwise it is dead metadata.
**Fix:** Use it for the WR-01 annotation or drop the id and the assertion.

### IN-04: Runbook shell snippets assume bash word splitting and leave `pipefail` set

**File:** `docs/registry-bot-proof.txt:185-200`
**Issue:** The snippets are pasted into the owner's interactive shell (zsh on this host). `for n in $open; do` relies on word splitting of an unquoted expansion, which zsh does not do by default; with two open `registry-bot` issues zsh passes one newline-joined string to `gh issue close` (it fails closed, but the second issue stays open). `set -o pipefail` at line 186 also stays on for the rest of that session.
**Fix:** Use `printf '%s\n' "$open" | while read -r n; do gh issue close "$n" ...; done` (or `for n in ${=open}`), and run the block in `bash -c '...'` or add `set +o pipefail` after it.

### IN-05: In `--bumps-only` a bumped tool is re-dated even when its other methods still drift

**File:** `installer/verify_registry.py:1352-1355`
**Issue:** Plain `--write` dates only tools whose findings all pass (`report.passed_tools()`); with the flag, any tool with an applied bump is dated (`test_bumps_only_dates_a_bumped_tool_whose_other_finding_stays_drifted` pins the divergence, `tests/test_verify_registry.py:3321-3350`). This is the D-13 design and is documented in `.claude/architecture.md`, README, the issue body and `--help`, so it is not a defect; it is recorded because `verified` is described as "refreshes when the entry passes" elsewhere in the same paragraph, and a blocked or rate-limited run can date a tool whose unpinned methods were never checked.
**Fix:** None required. If the owner wants the stricter reading, date a bumped tool only when `report` has no non-ok finding for it.

### IN-06: Write-scoped job token alongside mutable-tag third-party actions

**File:** `.github/workflows/registry-bot.yml:36-43,165-166`
**Issue:** `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/cache/{restore,save}@v4` run in a job whose token carries `contents`, `actions` and `issues` write. Tags are mutable. This matches `ci.yml` and `verify-registry.yml` and Dependabot (D-17) will bump them, so it is the repository convention, not a regression.
**Fix:** Optional: pin by full SHA with a trailing `# v5` comment; Dependabot updates SHA pins too.

### IN-07: The workflow tests pin source text and never execute the shell

**File:** `tests/test_registry_bot_workflow.py:214-245,290-316,442-474`
**Issue:** The guard, compare, redispatch and deletion tests assert that exact substrings appear in order (including indentation such as `"  fi"` and `"\nfi"`). They would pass on a script that is logically wrong in a way that keeps the pinned text, and they break on a harmless reformat. They did not catch WR-01. The unit-test sandbox forbids launching `git`/`gh`, so executing the scripts is not possible there; the scratch-repo experiments in the Summary are the only behavior evidence this phase has.
**Fix:** Keep the structural tests; add the scratch-repo experiment (bare remote, `--depth 1` clone, the Compare/Publish/Delete bodies) to the owner's proof or a `hooks-e2e`-style target that is allowed to run git.

### IN-08: Dependabot branches carry non-conventional commit subjects and the landing section treats them like bot branches

**File:** `.github/dependabot.yml:4-12`, `.claude/git-workflow.md:76-79`
**Issue:** Dependabot's default subject is "Bump X from 4 to 5", while `.claude/git-workflow.md` requires Conventional Commits; the docs tell the owner to fast-forward that branch to main. The landing section also says "if `main` moved, run the bot again", which does not apply to a Dependabot branch (it needs a Dependabot rebase and fresh checks, since strict mode requires an up-to-date commit).
**Fix:** Add `commit-message: { prefix: "chore(deps)" }` to the update entry and one sentence for Dependabot: "if `main` moved, comment `@dependabot rebase` and wait for green again".

### IN-09: Landing and proof notes understate side effects and cleanup edge cases

**File:** `.claude/git-workflow.md:61,71`, `docs/registry-bot-proof.txt:41-49`
**Issue:** (a) The check-runs jq counts any check run named like a required check with `conclusion == "success"`, so a success followed by a failed re-run of the same job still prints `2`; GitHub evaluates the latest attempt. (b) `git worktree remove "$WT"` lacks `--force`, unlike the runbook helper, so an untracked non-ignored leftover from the push gate leaves the scratch worktree behind. (c) The "What this writes to the remote" table lists only dispatched runs; Option A's first `push_exact "$BASE"` and Option B's landing push start ordinary push-event CI runs (`ci.yml:6-8` ignores only `main`), a full 25-minute two-OS run each, not listed.
**Fix:** (a) add `| select(.status == "completed")` and order by `.completed_at` or check `gh run list --commit "$SHA" --json conclusion` for any non-success; (b) use `git worktree remove --force "$WT"`; (c) add a WRITE line for the push-event runs on `proof/target-*` and `landing/*`.

---

_Reviewed: 2026-11-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_

---

## Orchestrator triage (2026-11-21)

Sources: this report (gsd-code-reviewer, deep: 0 critical, 4 warnings, 9 info), the external lane `opencode-referee-one` (14 findings, one pass, 18:15 to 18:35), the security audit (`33-SECURITY.md`: SECURED 17/17, 0 open) and my `actionlint` run (all three workflows clean). Claims that rest on code or Git behavior are for the fixing executor to verify first and fix or reject with a stated reason. Decisions are provisional.

| Item | Source | Decision |
|---|---|---|
| WR-01 = lane 4 | reviewer, lane | FIX: tolerate exit 1 or 2 of the verifier only when its output shows the report (a report heading line); otherwise fail the step with the first lines of the output (a launcher failure is not a verifier result). Test the text. |
| WR-02 | reviewer | FIX: the "must skip" check reads the step conclusions of the run (`gh run view --json jobs`), not a grep of the log. |
| WR-03 | reviewer | FIX: Option A reads `main`'s whole protection and maps every enabled setting it knows (required checks with their contexts, strict, enforce_admins, required signatures, linear history, force pushes, deletions) onto the throwaway branch; it STOPS on any enabled setting it cannot map. |
| WR-04 = lane 14 | reviewer, lane | FIX: both tests exercise what they claim (both file orders; an old date so plain `--write` refreshes it and `--bumps-only` leaves it). |
| Lane 1 | lane | FIX: Git keeps the literal branch name; every REST path uses `proof%2Ftarget-$DATE`; the tests distinguish the two forms. |
| Lane 2 | lane | VERIFY, then FIX if real: raw downloads are recorded with `member=None` but the bump lookup uses the configured `member`, so a raw AppImage bump (Bruno, Ghostty) can fail the whole run with 73; normalize the identity in both places; add a raw pinned fixture with a nonempty `member`. |
| Lane 3 | lane | FIX: the preflight also stops on a queued or running `registry-bot` run; each proof dispatch is identified by its run id and cleanup runs only after those runs are terminal. |
| Lane 5 | lane | FIX: the compare step also requires exactly one parent (equal to HEAD) and that the remote commit differs from its parent only in `installer/registry.toml`. |
| Lane 6 | lane | ACCEPTED: only an owner push can move the bot branch between the lease and the dispatch (the bot runs are serialized by the concurrency group); document it in the workflow header. |
| Lane 7 | lane | FIX (small): after a successful push, a step records the exact published SHA in the issue body; the upsert before the commit stays (D-08: the commit carries the closing keyword). |
| Lane 8 | lane | ACCEPTED (AR-33-04, the repo convention for all workflows; Dependabot bumps them); backlog. |
| Lane 9 | lane | FIX: a verified no-op candidate produces no `bumped` report note under the flag; assert the stdout. |
| Lane 10 | lane | DEFER (pre-existing, improbable shared-URL case between a pinned and an unpinned method); backlog 999.33. |
| Lane 11 + IN-09 | lane, reviewer | FIX: the landing commands stop on a failed fetch, SHA lookup or check query, count the latest conclusion per check name, preserve the push's exit status when removing the worktree and use `git worktree remove --force`. |
| Lane 12 | lane | FIX: the runbook verifies that the fetch and push URLs of `origin` identify the repository before any write and passes `-R "$REPO"` to every `gh` command. |
| Lane 13 | lane | FIX: `--bumps-only` without `--write` is rejected right after argument parsing (exit 64), before any file is read. |
| IN-01 | reviewer | FIX: the README layout line names the bot workflow and `dependabot.yml`. |
| IN-02 | reviewer | FIX: simplify the inline edit generator (drop the dead clause). |
| IN-03 | reviewer | KEEP (`id: bump` is pinned by a test and harmless). |
| IN-04 | reviewer | FIX: the runbook's loops use `while read` and say to run the commands in bash; no lingering `pipefail`. |
| IN-05, IN-06 | reviewer | By design (D-13) and the repo convention; no change. |
| IN-07 | reviewer | ACCEPTED (the sandbox forbids launching git and gh from unit tests); the live behavior is the owner's proof. |
| IN-08 | reviewer | FIX: the git-workflow note says "run the bot again" does not apply to a Dependabot branch and what a Dependabot commit subject looks like. |
| IN-09 (rest) | reviewer | FIX: the writes table names the push-event CI runs on `proof/target-*` and `landing/*` and the two-OS CI run Option A's first push starts. |
