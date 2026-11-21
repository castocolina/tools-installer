---
phase: "33"
slug: "registry-update-bot"
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: "2026-11-21"
---

# Phase 33 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from 33-RESEARCH.md "Validation Architecture" and the orchestrator decisions of 2026-11-21 (all provisional, "needs confirmation"). The per-task rows below are keyed to the five plans of phase 33 (plan, wave and task ids filled in by the planner).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (xdist, coverage); PyYAML parses the workflow and dependabot files (plain parses, no network, no `gh`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`); worker cap and the HOME sandbox in `tests/conftest.py` |
| **Quick run command** | `uv run pytest <the task's test files> --no-cov -q` |
| **Full suite command** | `make test` (once, after the last task of each plan) |
| **Static gates** | `make validate` (the six commit-stage gates; once per plan, after the last task) |
| **Ad-hoc lint (orchestrator only)** | `actionlint` from the image `rhysd/actionlint:1.7.12` on local files only (see Manual-Only Verifications) |
| **Estimated runtime** | ~20 seconds per targeted run (to confirm in the first plan) |

Files the quick command draws from: `tests/test_ci_workflow.py`, `tests/test_verify_registry_workflow.py`, `tests/test_registry_bot_workflow.py` (new), `tests/test_verify_registry.py`, and `tests/test_docs_only.py` (a `.github/*` edit is read-test territory, D-18).

Baseline: the two existing workflow test files pass today (`20 passed` with `--no-cov`, research 2026-11-21); confirm it on this tree in the first plan.

Constraints on every new test (orchestrator decision 10): plain YAML parses only; holds on Python 3.12 and 3.15; where a shell is involved, holds on macOS bash 3.2 (no apostrophes or unbalanced quotes inside a heredoc inside `$(...)`); no dependency on tools the CI runner images carry (isolate PATH in any test that smoke-runs a binary: runners have `aws`, `gh` and others on PATH); no timing-sensitive assertions and no assertion about the order of the Monday drift run and the bot run (decision 4); xdist-safe.

---

## Sampling Rate

- **After every task commit:** the task's targeted pytest (the commit hook runs the six static gates); never `make validate` or a single static gate by hand per commit
- **After every plan wave:** the quick-run files above plus `tests/test_docs_only.py`
- **After every plan:** `make validate` once, then `make test` once, on the final tree
- **Phase gate (orchestrator, before `/gsd-verify-work`):** full suite green; the ad-hoc `actionlint` run recorded in VERIFICATION (or "not run" with the reason, never a pass); the manual-only rows below carried as deferred items
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

Task ids are `33-<plan>-<task>`. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row; plan 05's task 3 runs them on the final tree of the phase). `DEP` is the Dependabot requirement (SPEC R5, "actions-version updates"), which has no BOT id. Plan 03 and plan 04 rows share one test file (`tests/test_registry_bot_workflow.py`, created by 33-02-02) and run strictly in sequence.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-01-01 | 01 | 1 | BOT-04 | T-33-01 | `--write --bumps-only` leaves a date-only registry byte-identical and prints no `dated` line while the same fixture without the flag changes it; `--bumps-only` without `--write` exits 64 with `--bumps-only requires --write`, calls no probe function and leaves the registry untouched | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-01-02 | 01 | 1 | BOT-04 | T-33-01 | A real bump with the flag changes exactly `version` and `sha256` per method plus the tool's `verified` (set compare after a `tomllib` parse); a passing neighbour listed first keeps its old date and prints no `dated` line; a no-drift registry is byte-identical with and without the flag; the exit-64 wording names both flags; `make validate` and `make test` once | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-02-01 | 02 | 2 | BOT-02 | T-33-02 | `ci.yml` declares a bare `workflow_dispatch:` beside the unchanged push filter; the two listed assertions of `tests/test_ci_workflow.py` (trigger set at `:41`, exact `actions/checkout@v4` match at `:52`) are amended keeping their meaning | workflow | `uv run pytest tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (amend) | ⬜ pending |
| 33-02-02 | 02 | 2 | BOT-02 | T-33-02 | The two required check names are derived from the `ci.yml` job name template and matrix and equal `validate & test on ubuntu-latest` and `validate & test on macos-latest` (`REQUIRED_CHECKS`); `ci.yml` keeps one job and the `ci-${{ github.ref }}` concurrency group; the new test module has its own `_load`/`_triggers`; `make validate` and `make test` once | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py -n auto -q --no-cov` | ❌ W0 (created by this task) | ⬜ pending |
| 33-03-01 | 03 | 3 | BOT-01, BOT-02, BOT-03 | T-33-03, T-33-04, T-33-05 | The committed trigger set is exactly `{"workflow_dispatch"}` (cron disabled, decision 1, D-12) and any cron is off-minute; permissions exactly the three writes; concurrency group `registry-bot` with `cancel-in-progress: false`; job timeout at least 60 (decision 9); the bump step runs `--write --bumps-only` directly, never `--issue`; the cache is shared with the drift workflow (`always()` save); a guard step id gates every publishing step; the fetch uses the explicit refspec with `|| true` and the push `--force-with-lease=<ref>:<expected>` (decision 5); the dispatch is `gh workflow run ci.yml --ref "$BRANCH"`; no `${{` in any `run`; no run text targets the default branch (regex self-tested) | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-03-02 | 03 | 3 | BOT-01 | T-33-06, T-33-07 | The `registry-bot` issue is upserted (label `--force`, list open, edit else create) before the commit, which carries `Closes #$ISSUE_NUMBER`; the D-05 deletion step touches only the `refs/heads/bot/registry-` namespace and excludes the current branch; no run text contains a token word or `set -x`; the publishing-step set is exactly the four steps; `make validate` and `make test` once | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-04-01 | 04 | 4 | BOT-02 | T-33-09 | The committed runbook `docs/registry-bot-proof.txt` holds the exact D-11 command sequence (stale pin, bot dispatch, check-run read, protection contexts read, same-day rerun), names both required checks exactly, never targets the default branch (same regex as the workflow test), and deletes every ref it creates | host | `uv run pytest tests/test_registry_bot_workflow.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-04-02 | 04 | 4 | BOT-02 | T-33-09 | Part 3 gives Option A (throwaway protected target, the single `-X PUT` line marked OWNER APPROVAL REQUIRED) and Option B (zero-token fallback, A3 unverified) with a STOP rule; the not-proved line says the closing keyword is NOT EXERCISED; the last section enables the cron `37 6 * * 1`; `make validate` and `make test` once | host | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-05-01 | 05 | 5 | DEP (SPEC R5) | T-33-10 | `.github/dependabot.yml` parses as `version: 2` with one `github-actions` entry, directory `/`, weekly, group `actions` matching `"*"`, and no other ecosystem (pure parse) | unit | `uv run pytest tests/test_registry_bot_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-05-02 | 05 | 5 | BOT-01 to BOT-04 | — | README `### Registry update bot` and the `--bumps-only` row phrase, and `.claude/git-workflow.md` `### Landing a registry bot branch` are additions only; the rule-document tests still pass | docs | `uv run pytest tests/test_docs.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists | ⬜ pending |
| 33-05-03 | 05 | 5 | BOT-01 to BOT-04, DEP | — | The commented cron equals the runbook's cron; every `gh workflow run` file exists; the label and branch prefix agree; the phase changed exactly ten files outside `.planning`, none of them `devtools/docs_only.py` or `tests/test_docs_only.py` (D-18); phase gate: `make validate` then `make test`, once each, green on the final tree | gate | `make validate` then `make test` (never chained at a commit; once each at the end) | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every test file is created or extended inside the task that needs it (test-first inside one green commit), so there is no separate scaffold task:

- [ ] `tests/test_registry_bot_workflow.py` — new in 33-02-02, with its own small `_load(path)` and `_triggers(data)` (the existing `_load_verify` / `_steps` / `_triggers` are hard-wired to `verify-registry.yml` and stay untouched; decision 2); extended by plans 03, 04 and 05 for BOT-01, BOT-02, BOT-03, the runbook and DEP
- [ ] `tests/test_verify_registry.py` — five `--bumps-only` tests appended in 33-01-01 and 33-01-02 (fixtures exist at `:2542` and `:2896`) for BOT-04
- [ ] `tests/test_ci_workflow.py` — the trigger assertion at `:41` and the checkout lookup at `:52` amended in 33-02-01 (BOT-02)
- [ ] The no-main assertion scans `run` texts with a regex covering `HEAD:main`, `refs/heads/main`, `origin main`, `:main\b` plus `gh pr`, `git merge` and `gh api`, and does not false-positive on `bot/registry-`, `refs/heads/maintenance` or "domain" (BOT-03, 33-03-01, self-tested); the same `HEAD:main`-family regex scans the runbook (33-04-01)

Framework install: none. Cron trigger assertion: the committed state asserts exactly `{"workflow_dispatch"}`; the follow-up commit that enables the cron changes that one test to `{"schedule", "workflow_dispatch"}` (decision 1).

---

## Manual-Only Verifications

Decision 1 (provisional, needs confirmation): no plan and no agent step performs any remote write of the proof. GitHub dispatches only a workflow file that exists on the default branch, and `origin/main` does not carry this work; the owner fast-forwards `main`. The phase's code is complete and tested without the proof; the phase verification is `human_needed` with these rows as deferred items.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One-time proof, part 1: after the owner lands the branch on `main`, dispatch the bot (`workflow_dispatch`) and confirm it pushes a `bot/registry-<date>` branch and opens or updates one tracking issue (D-11) | BOT-01, BOT-02 | Needs the workflow file on the default branch and a remote write; no agent ever pushes, merges or fast-forwards `main` | The owner runs the commands of `docs/registry-bot-proof.txt` (plain-text runbook, plan 33-04) after landing; its Cleanup section deletes the proof and bot refs and closes the issue at the end |
| One-time proof, part 2: the check names reported for the bot branch head by the dispatched `ci.yml` run are exactly the two required names (`validate & test on ubuntu-latest` and `macos-latest`) | BOT-02 | Check-run names exist only on GitHub after a real dispatch | Runbook step: `gh api` the check runs of the branch head SHA and compare names, `event` field and conclusion |
| One-time proof, part 3 (the BOT-02 question): do dispatched check runs on the bot branch head satisfy classic branch protection for a fast-forward of the same commit? | BOT-02 | GitHub-side behavior is unknown (assumption A1: docs only say dispatch checks do not satisfy a branch ruleset on a PR head); a failure stops the phase and the owner chooses a token route | Option A (runbook Part 3): a throwaway protected target branch with the same two required checks, fast-forwarded from the bot branch head; needs the owner's explicit approval of that temporary branch-protection write. Option B (zero-token fallback): the owner re-pushes the same SHA under a second branch name so normal push-event CI satisfies protection (assumption A3, unverified). Record the outcome in VERIFICATION |
| Closing keyword on fast-forward (D-08, `Closes #N` in the bot commit) is NOT exercised | BOT-01 | Cannot be proved without pushing to `main` (assumption A5) | VERIFICATION states it was not exercised; the issue body documents the owner-closes fallback; the proof must not claim it |
| Cron enabled after the proof passes (the follow-up commit) | BOT-01 | Depends on the proof outcome; owner's commit or a trivial deferred task | After the proof passes, one commit adds the off-minute Monday cron and the matching trigger-set assertion |
| Ad-hoc `actionlint` run on the new and edited workflow files (D-16), before and after the edits | BOT-01, BOT-02, BOT-03 | Not run by an executor: the research's container attempt was blocked by the permission classifier (decision 6) | Orchestrator, at the phase gate: image `rhysd/actionlint:1.7.12` (image name assumed A10, confirm on first pull), local files only, disposable container, remove an image that was absent before. Record the output in VERIFICATION; if it cannot run, VERIFICATION says "not run" and why, never a pass |
| First real bot run bumps draw.io to `32.7.4`: `version = "32.7.4"`, the two macOS zip `sha256` values and today's `verified`, for `drawio-desktop` only (no other tool re-dated) | BOT-01, BOT-04 | Needs a real run on the remote after landing and the live upstream release | After landing and the proof, inspect the bot branch diff: only `installer/registry.toml`, only the drawio-desktop pins; the next Monday drift run (2026-11-23) is the first that can report the same drift |
| Dependabot branch landing (decision 7, assumption A7) | DEP | Dependabot opens pull requests, which this repo's flow never merges | The owner lands a Dependabot branch by fast-forward of its branch or closes the PR; low stakes, provisional |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
