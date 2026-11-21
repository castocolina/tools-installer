---
phase: "33"
slug: "registry-update-bot"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
threats_total: 17
asvs_level: 1
block_on: high
created: "2026-11-21"
---

# Phase 33 - Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Base ff3cedb5, HEAD 07c00293. Verified against the workflow, runbook, code and tests, not the
> summaries. Read-only audit: no make target, container or remote write. Two read-only `gh api`
> GETs (default-branch protection, default workflow permissions) were made to state the real
> exposure; a scratch pytest run of the phase's own file-level tests (bot workflow, CI workflow,
> `--bumps-only`) passed (scratch directory removed).
> 16 numbered threats (T-33-01 .. T-33-16) plus one consolidated T-33-SC row (the reserved
> package-install row repeated in plans 33-01 .. 33-05) = 17 rows.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| upstream release asset -> registry.toml | A digest reaches the registry only after `verify_registry` downloaded and hashed the candidate | version, sha256 |
| CLI flag -> edit set | `--bumps-only` narrows date edits; it never adds a pin or a date for an unverified candidate | registry edits |
| repository write access -> `workflow_dispatch` | Anyone with write access can dispatch CI or the bot on any ref; the ref's own code runs with the write token | ref, token |
| bot job token -> repository refs | `contents: write`, no push restriction on the default branch | refs |
| runbook text -> owner's commands | The owner pastes the commands; no test or agent runs the file | text |
| owner shell -> repository settings | Option A writes then removes protection on a throwaway branch | API write |
| Dependabot -> default branch | Pull requests that bump the repository's own action versions | workflow files |

---

## Threat Register

Line numbers are HEAD 07c00293. T-33-SC repeats in every plan; it is one row.

| Threat ID | Category | Component | Severity | Disposition | Evidence | Status |
|-----------|----------|-----------|----------|-------------|----------|--------|
| T-33-01 | Tampering | a bumped version without a verified sha256, or a date for an unverified candidate (`--bumps-only`) | high | mitigate | `_build_bump_edits` is unchanged in the diff and raises `RegistryWriteError` when the candidate finding has no sha256 (installer/verify_registry.py:1189-1199). A candidate is checked with an EMPTY state (`check_registry([pinned_copy], probe, {})`, :1303), so the state cache can never stand in for a download, and `applied` is true only when every candidate finding is `ok` (:1304-1317). `_registry_edits_for_write(..., bumps_only=True)` keeps bump edits only for `applied and changes_registry` and dates only `bumped` tools (:1345-1356); the unflagged path is the old `report.passed_tools()`. `--bumps-only` without `--write` is a usage error (:1610-1612). `apply_registry_edits` still round-trips the TOML and refuses an unintended change (:1037-1056). Tests: tests/test_verify_registry.py:2646, :2684, :3210 (exactly `version` and `sha256` per method), :3245, :3278, :3300, :3321, :3364, :3398 (failed candidate writes nothing), :3423 (no-op candidate earns no date). Scratch run passed | closed |
| T-33-02 | Elevation of privilege | `ci.yml` `workflow_dispatch` trigger | low | accept | One added line, `workflow_dispatch:` with no inputs (.github/workflows/ci.yml:9); the job and steps are untouched, so a dispatch runs the same validate and test job a branch push already runs; no `permissions:` block (default token is read per the repository setting). Test: tests/test_ci_workflow.py:42-43 pins the trigger set and the empty dispatch. See AR-33-01 | closed |
| T-33-03 | Elevation of privilege | a step pushing or merging into the default branch with the `contents: write` token | high | mitigate | Every `git push` is `HEAD:refs/heads/$BRANCH` (.github/workflows/registry-bot.yml:114) or a leased `--delete` of a `refs/heads/bot/registry-*` ref (:160); no `gh pr`, `git merge` or `gh api` in any run text. Permissions are exactly `contents/actions/issues: write` at workflow level, none on the job (:19-22). Tests: tests/test_registry_bot_workflow.py:319 (`MAIN_TARGET`, `NO_PR_OR_MERGE`, per-line push check), :333 (pattern self-test), :116 (permissions exact). Residual: a structural guard, not a runtime control; see T-33-11 and AR-33-02 | closed |
| T-33-04 | Tampering | script injection through a ref or branch name | high | mitigate | No `${{` in any `run` text: the only expressions are `env:` values (:33, :107-108, :128, :143-145) and `if:`/`key:`/`with:`. The branch is built from `date -u +%F` and written to `$GITHUB_ENV` (:48), then used only as the double-quoted `$BRANCH`. `ISSUE_NUMBER` and `EXPECTED` arrive through `env:` (:106-108) and the number is validated numeric before use (:101); `EXPECTED` is a `git rev-parse` result. The dispatched ref name appears only as `$GITHUB_REF_NAME` inside a double-quoted comment body (:149, :151), never re-evaluated. Tests: tests/test_registry_bot_workflow.py:174 (`${{` forbidden in every run text), :353, :402 | closed |
| T-33-05 | Tampering | force-push clobbering someone else's branch | medium | mitigate | `git push --force-with-lease="refs/heads/$BRANCH:$EXPECTED" origin "HEAD:refs/heads/$BRANCH"` (:114), with `EXPECTED` the head the compare step fetched (empty means the ref must not exist). Compare uses a plain-assignment `ls-remote` (a probe error fails the step under the runner's `bash -e`, :67), fetch and `rev-parse` errors fail the step (:71-72); the guard separates exit 1 from a git error (:60-61). No bare `--force` anywhere. Tests: tests/test_registry_bot_workflow.py:178, :214, :248 | closed |
| T-33-06 | Tampering | the older-branch deletion sweeping other refs | medium | mitigate | `set -o pipefail`, plain-assignment listing of `refs/heads/bot/registry-*` (:155-156), a `case` on the FULL ref name: current branch skipped, only `refs/heads/bot/registry-*` deleted, anything else ignored (:158-162); each deletion leased on the listed SHA and non-fatal (:160); step runs only after a successful dispatch or redispatch (:153). Tests: tests/test_registry_bot_workflow.py:442 (order, one `ls-remote`, one `git push`, only the two ref spellings, no bare `--force`) | closed |
| T-33-07 | Information disclosure | a token in logs, the branch or the issue body | high | mitigate | The one token is `${{ github.token }}` at job `env:` (:33) (Actions masks it); no `secrets.` in the file; no run text contains `GH_TOKEN`, `GITHUB_TOKEN`, `printenv`, `set -x` or `xtrace`. Issue body is the branch, the short base SHA and fixed prose (:87-94); failure comment is the stage, branch and a manual command (:151). Tests: tests/test_registry_bot_workflow.py:132, :477 (`github.token` appears once) | closed |
| T-33-08 | Spoofing | a dispatch on an unrelated ref | low | accept | Only `bot/registry-*` is pushed (:114) and only `installer/registry.toml` is added (:112). Code-execution side is T-33-11. See AR-33-03 | closed |
| T-33-09 | Tampering | the temporary branch-protection write of Option A | medium | mitigate | docs/registry-bot-proof.txt: the only `-X PUT` is line 140, marked `OWNER APPROVAL REQUIRED`, on `branches/proof/target-$DATE/protection`; the only `-X DELETE` is line 180, same branch, followed by a 404 read-back (:181-183) before the ref-deletion loop (:185-192); the default branch's protection appears only as a GET (:100) and "Never touch default branch protection" (:183, :195). Tests: tests/test_registry_bot_workflow.py:636 (single PUT with approval marker, no `-X` on `branches/main`), :646 (single DELETE, read-back before the loop) | closed |
| T-33-10 | Tampering | a Dependabot action bump reaching the workflows | low | accept | .github/dependabot.yml: one `github-actions` entry, `/`, weekly, one group; it opens pull requests and grants no write path. A bump lands only through the owner's branch push, green required checks and a fast-forward (.claude/git-workflow.md "Landing a registry bot branch", ends "never add a token or push around protection"). The checkout assertion no longer pins `@v4` exactly (tests/test_ci_workflow.py diff). Test: tests/test_registry_bot_workflow.py:74. See AR-33-04 | closed |
| T-33-11 | Elevation of privilege | the dispatched ref's own code running with the write token | medium | accept | Documented in the workflow header (registry-bot.yml:5-10), the issue body (:93), README and `.claude/git-workflow.md`; header pinned by tests/test_registry_bot_workflow.py:792. Real exposure stated in AR-33-02 | closed |
| T-33-12 | Denial of service | deleting every other `bot/registry-*` ref can remove a proposal under review | low | accept | 33 D-05: one live bot branch; the issue body says older bot branches are replaced by the newest one (registry-bot.yml:91). See AR-33-05 | closed |
| T-33-13 | Denial of service | a failed push or dispatch leaves an issue advertising a head without checks | medium | mitigate | One retry with a 20 s pause on both dispatch steps (:119-123, :134-138); a failed publish, dispatch or redispatch runs the failure report (stage plus the manual command, commented on the open issue) and the job still fails (:140-151). An unchanged branch with no queued, running or successful CI run for its head is dispatched again, and a successful redispatch also deletes older branches (:124-139, :153). Tests: tests/test_registry_bot_workflow.py:268, :290, :411, :442 | closed |
| T-33-14 | Tampering | a proof run overwriting or deleting a real bot branch or issue, or Cleanup deleting more than the proof created | high | mitigate | Read-only preflight STOPs on any `bot/registry-*`, `proof/*`, `landing/*` ref or open `registry-bot` issue (docs/registry-bot-proof.txt:21-29); Cleanup deletes only refs whose FULL name matches the three prefixes via a `case`, each with an expected-SHA lease (:185-193), closes only open `registry-bot` issues (:196-200), and says to stop if anyone else created work there meanwhile (:173-177). Tests: tests/test_registry_bot_workflow.py:534, :547, :561. Residual: a ref created by someone else between the preflight and Cleanup is outside the leases; the runbook states the stop rule | closed |
| T-33-15 | Repudiation | a false BOT-02 pass from confounded evidence | medium | mitigate | The runbook identifies the bot commit (parent, author, subject, files, :71-80), binds the bot run and CI run to ids (:56-64, :88-98), requires every CI run for the SHA to be `workflow_dispatch` and STOPs on a push-event run (:88-91), STOPs on a changed UTC date (:31-32, :55, :106) and a moved base (:76, :116-117), records the dispatch-only evidence before Option A's push (:130-135), and passes BOT-02 only for an accepted Option A fast-forward (:210-212). Tests: tests/test_registry_bot_workflow.py:585, :600, :691, :720 | closed |
| T-33-16 | Elevation of privilege | a push that bypasses the push gate or comes from a checkout whose HEAD is another commit | medium | mitigate | Every non-delete commit push goes through `push_exact` (detached scratch worktree at the exact commit, then `git push origin "HEAD:$2"`, :39); its three calls target `proof/target-` and `landing/registry-` refs only (:139, :153, :159); no `--no-verify`, `SKIP=`, `core.hooksPath` or `sudo`. Tests: tests/test_registry_bot_workflow.py:523 (forbidden words, no `main` on a push line, no bare `--force`), :660 (helper parts, all three calls by regex, only the helper pushes a commit) | closed |
| T-33-SC | Tampering | package installs (all five plans) | high | mitigate | `git diff ff3cedb5..HEAD -- pyproject.toml uv.lock package.json Makefile .pre-commit-config.yaml` is empty: no project package added. The only fetched artifacts are the pinned-by-major-tag actions `actions/checkout@v4`, `astral-sh/setup-uv@v5`, `actions/cache/restore@v4` and `cache/save@v4` (same set and tags as the existing verify-registry.yml and ci.yml), covered by Dependabot (T-33-10, AR-33-04), plus the project's own `uv run --isolated --no-dev` | closed |

*Status: open - closed - open below high threshold (non-blocking)*
*Severity: critical > high > medium > low - only open threats at or above workflow.security_block_on count toward threats_open*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-33-01 | T-33-02 | A CI dispatch has no inputs and runs the job a push of that ref already runs; anyone who can dispatch can already push a branch to this repository. The default workflow token is read-only (read-only GET of the repository setting: `default_workflow_permissions: read`) and `ci.yml` declares no permissions | declared in plan 33-02 | 2026-11-21 |
| AR-33-02 | T-33-11 / T-33-03 (residual) | A dispatch is an owner act, and a dispatched ref runs its OWN copy of the workflow and code with the token. The real exposure, read-only checked: the default branch has classic protection (required checks `validate & test on ubuntu-latest` and `...macos-latest`, `strict`, `enforce_admins` true, no force-push, no deletion) and `restrictions: null`, so there is NO push restriction. The `contents: write` token therefore can fast-forward the default branch to any commit whose two required checks are already green; it cannot force-push or delete it. The required contexts carry `app_id: null`, so any app or token able to create a check run of that name satisfies them. The test guard (no step targets the default branch) is structural: a ref that rewrites the workflow file is not bound by it. This holds equally for a plain branch push (ci.yml runs any ref's code on push), so write access is the real boundary and the phase adds no new principal. Closing it is an owner follow-up outside this phase (a push restriction, and optionally an `app_id` on the required contexts); the runbook and git-workflow guide name it | declared in plan 33-03 and the workflow header | 2026-11-21 |
| AR-33-03 | T-33-08 | Spoofing by dispatching on an unrelated ref is limited to publishing `bot/registry-*` and `installer/registry.toml`; the code-execution side is AR-33-02 | declared in plan 33-03 | 2026-11-21 |
| AR-33-04 | T-33-10 / T-33-SC (residual) | Third-party actions are pinned by mutable major tag (`@v4`, `@v5`), not commit SHA, and the token reaches them through the job env; Dependabot (weekly, grouped) proposes bumps as pull requests that the owner lands by fast-forward or closes. A moved upstream tag is trusted, the same trust as the existing ci.yml and verify-registry.yml | declared in plan 33-05 (tags); SHA pinning is not claimed | 2026-11-21 |
| AR-33-05 | T-33-12 | Deleting older `bot/registry-*` branches can remove a proposal under review; one live bot branch is the owner-provisional design (D-05), and unlanded bumps reappear weekly | declared in plan 33-03 | 2026-11-21 |

---

## Unregistered Flags

None. No `## Threat Flags` section appears in 33-01 through 33-05 SUMMARY.md.

---

## Notes (informational, non-blocking, not counted)

- **actionlint: NOT YET RUN.** No VERIFICATION file exists and no summary records a run; 33-VALIDATION.md and every summary assign the `rhysd/actionlint:1.7.12` run to the orchestrator at the phase gate ("not run" with the reason if unavailable, never a pass). `make validate` shellcheck does not inspect inline Actions scripts.
- **State cache cannot carry a pin.** The restored `verify-registry.json` can only turn an existing pin's finding into `ok` without a hash (registry-bot.yml:41-46, installer/verify_registry.py:751-753); a candidate is verified with an empty state and a bump needs a candidate hash, so a poisoned cache can hide drift but cannot write a pin or a date. The cache is saved with `if: always()` but only holds fingerprints written after a verification.
- **Job-level token visible to the ref's code.** `GH_TOKEN` is set on the whole job, so `uv run` of the dispatched ref's code can read it; this is the same exposure as AR-33-02, not a separate path.
- **Issue upsert edits the first open issue labeled `registry-bot`** (:85, :96), which includes one a triager labeled by hand; the runbook preflight requires zero such issues before the proof.
- **Runbook scope.** Every remote write is listed in "What this writes to the remote" (:41-49) and none targets the default branch: the dispatches use `--ref main` (a workflow run on main's code, not a push). The protection delete in Cleanup is not marked `OWNER APPROVAL REQUIRED` (only the PUT is, as planned); it names the same throwaway branch.
- The live behavior of every step is unproved until the owner-run proof (BOT-01, BOT-02 human_needed): closing keyword on a fast-forward, the leased-update rerun path and the first scheduled run are not exercised.
