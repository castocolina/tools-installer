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
| 33-01-02 | 01 | 1 | BOT-04 | T-33-01 | A real bump with the flag changes exactly `version` and `sha256` per method plus the tool's `verified` (set compare after a `tomllib` parse); a passing neighbour listed first keeps its old date and prints no `dated` line; a no-drift registry is byte-identical with and without the flag; the exit-64 wording names both flags; the `--bumps-only` help text says that after a bump `verified` certifies the bumped pins only (review round 2 M7) | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-01-03 | 01 | 1 | BOT-04 | T-33-01 | Review H1: under the flag `verified` is written for exactly the tools with an applied bump (the applied-bump set, not `passed_tools()`), so a bumped tool whose other finding stays drifted (the `combo` registry) still gets version, sha256 and verified together while the unflagged run keeps its old rule; review M1: a two-method tool (`sublime`, `--candidate`) changes version and sha256 of both methods by method index; a failed candidate earns no edit and no date; `make validate` and `make test` once | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-02-01 | 02 | 2 | BOT-02 | T-33-02 | `ci.yml` declares a bare `workflow_dispatch:` beside the unchanged push filter; the two listed assertions of `tests/test_ci_workflow.py` (trigger set at `:41`, exact `actions/checkout@v4` match at `:52`) are amended keeping their meaning | workflow | `uv run pytest tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (amend) | ⬜ pending |
| 33-02-02 | 02 | 2 | BOT-02 | T-33-02 | The two required check names are derived from the `ci.yml` job name template and matrix and equal `validate & test on ubuntu-latest` and `validate & test on macos-latest` (`REQUIRED_CHECKS`); `ci.yml` keeps one job and the `ci-${{ github.ref }}` concurrency group; the new test module has its own `_load`/`_triggers`; `make validate` and `make test` once | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py -n auto -q --no-cov` | ❌ W0 (created by this task) | ⬜ pending |
| 33-03-01 | 03 | 3 | BOT-01, BOT-02, BOT-03 | T-33-03, T-33-04, T-33-05, T-33-11 | The committed trigger set is exactly `{"workflow_dispatch"}` (cron disabled, decision 1, D-12) and any cron is off-minute; permissions exactly the three writes; concurrency group `registry-bot` with `cancel-in-progress: false`; job timeout at least 60 (decision 9); the bump step runs `--write --bumps-only` directly, never `--issue`; the cache is shared with the drift workflow (`always()` save); a guard step id gates every publishing step; the compare step probes with `git ls-remote --heads origin`, fetches only a present branch with the explicit refspec and no error suppression, and sets `same=true` only for a byte-identical bot branch whose parent equals the run ref's HEAD, plus `expected` (review round 2 H1, M3); the publish push is `--force-with-lease=<ref>:$EXPECTED` (decision 5); the dispatch is `gh workflow run ci.yml --ref "$BRANCH"` twice with a sleep between (review H3); the `redispatch` step dispatches for an unchanged branch only when `gh run list` shows no run for the bot head (round 2 H1); no `${{` in any `run`; no run text targets the default branch (regex self-tested; a structural guard, not a runtime control, round 2 H2); the header names the trust boundary and forbids the old protection claim | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-03-02 | 03 | 3 | BOT-01, BOT-02 | T-33-06, T-33-07, T-33-12, T-33-13 | The `registry-bot` issue is upserted (label `--force`, list open, edit else create) before the commit, its number validated as numeric (review M4) and the body carrying the older-branch, `verified`-meaning and trust-boundary sentences (M5, round 2 M7, H2); the commit carries `Closes #$ISSUE_NUMBER`; a failed push or CI dispatch is commented on the open issue with the stage and the manual command (`failure()` and the `publish`, `dispatch` or `redispatch` outcome, round 2 M2); the D-05 deletion step lists refs with `git ls-remote --heads`, deletes each with `--force-with-lease=<ref>:<sha>`, reports and skips a rejected deletion, touches only the `refs/heads/bot/registry-` namespace and excludes the current branch (round 2 M1); no run text contains a token word or `set -x`; the publishing-step set is exactly the six steps; `make validate` and `make test` once | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-04-01 | 04 | 4 | BOT-02 | T-33-09, T-33-14, T-33-15 | The committed runbook `docs/registry-bot-proof.txt` opens with a read-only preflight that STOPS on any existing `bot/registry-*`, `proof/*` or `landing/*` ref or open `registry-bot` issue (review H6), dispatches the bot on the default branch itself and relies on real drift (no stale-pin fixture, no proof ref, no `--candidate`; no bot branch means STOP, never a pass, review round 2 H3), fetches the bot head into a local ref, identifies the bot commit (parent equals BASE, author, subject, files) and requires every CI run of the SHA to be a `workflow_dispatch` (STOP on a push-event run, round 2 H4), checks the UTC date before each dispatch (STOP and restart, round 2 M4), holds the same-day rerun that must skip, names both required checks exactly, never targets the default branch (same regex as the workflow test), closes only the issue it recorded and deletes every ref it creates | host | `uv run pytest tests/test_registry_bot_workflow.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-04-02 | 04 | 4 | BOT-02 | T-33-09, T-33-15 | Part 3 gives Option A (throwaway protected target, the single `-X PUT` line marked OWNER APPROVAL REQUIRED, every push by the fetched SHA) and Option B (zero-token fallback kept UNVERIFIED with its check sequence, review M6) with a STOP rule; Cleanup removes the temporary protection with one `-X DELETE` line and a 404 read-back before the branch delete (review H5); BOT-02 is `passed` only for an accepted Option A fast-forward, never from Option B, an investigation or a recorded decision (round 2 M5); the not-proved line says the closing keyword is NOT EXERCISED; the last section enables the cron `37 6 * * 1`, names its one test edit (review H7) and the owner's push-restriction follow-up (round 2 H2); `make validate` and `make test` once | host | `uv run pytest tests/test_registry_bot_workflow.py tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-05-01 | 05 | 5 | DEP (SPEC R5) | T-33-10 | `.github/dependabot.yml` parses as `version: 2` with one `github-actions` entry, directory `/`, weekly, group `actions` matching `"*"`, and no other ecosystem (pure parse) | unit | `uv run pytest tests/test_registry_bot_workflow.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists (extend) | ⬜ pending |
| 33-05-02 | 05 | 5 | BOT-01 to BOT-04 | — | README `### Registry update bot` (including what `verified` certifies and the missing push restriction) and the `--bumps-only` row phrase, and `.claude/git-workflow.md` `### Landing a registry bot branch` (landing by the fetched SHA, review round 2 M6) are additions only; the rule-document tests still pass | docs | `uv run pytest tests/test_docs.py tests/test_docs_only.py -n auto -q --no-cov` | ✅ exists | ⬜ pending |
| 33-05-03 | 05 | 5 | BOT-01 to BOT-04, DEP | — | The cron (commented now, enabled after the follow-up: `_workflow_crons` reads both forms and is self-tested, review H7) equals the runbook's cron; the `gh workflow run` targets are read from command lines only (`_workflow_run_targets`, self-tested, round 2 L1): the bot's are exactly `ci.yml`, the runbook's exactly `registry-bot.yml`, both files exist; the label and branch prefix agree; the ten planned files are tracked and not dirty and every other modified or untracked file outside `.planning` is only reported and left alone (round 2 H5); `devtools/docs_only.py` and `tests/test_docs_only.py` stay unedited (D-18); phase gate: `make validate` then `make test`, once each, green on the final tree | gate | `make validate` then `make test` (never chained at a commit; once each at the end) | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Every test file is created or extended inside the task that needs it (test-first inside one green commit), so there is no separate scaffold task:

- [ ] `tests/test_registry_bot_workflow.py` — new in 33-02-02, with its own small `_load(path)` and `_triggers(data)` (the existing `_load_verify` / `_steps` / `_triggers` are hard-wired to `verify-registry.yml` and stay untouched; decision 2); extended by plans 03, 04 and 05 for BOT-01, BOT-02, BOT-03, the runbook and DEP
- [ ] `tests/test_verify_registry.py` — nine `--bumps-only` tests appended in 33-01-01, 33-01-02 and 33-01-03 (fixtures exist at `:2542`, `:2896`, `:2919` and the `combo` registry of the test at `:3345`) for BOT-04
- [ ] `tests/test_ci_workflow.py` — the trigger assertion at `:41` and the checkout lookup at `:52` amended in 33-02-01 (BOT-02)
- [ ] The no-main assertion scans `run` texts with a regex covering `HEAD:main`, `refs/heads/main`, `origin main`, `:main\b` plus `gh pr`, `git merge` and `gh api`, and does not false-positive on `bot/registry-`, `refs/heads/maintenance` or "domain" (BOT-03, 33-03-01, self-tested); the same `HEAD:main`-family regex scans the runbook (33-04-01)

Framework install: none. Cron trigger assertion: the committed state asserts exactly `{"workflow_dispatch"}`; the follow-up commit that enables the cron changes that one test to `{"schedule", "workflow_dispatch"}` (decision 1).

---

## Manual-Only Verifications

Decision 1 (provisional, needs confirmation): no plan and no agent step performs any remote write of the proof. GitHub dispatches only a workflow file that exists on the default branch, and `origin/main` does not carry this work; the owner fast-forwards `main`. The phase's code is complete and tested without the proof; the phase verification is `human_needed` with these rows as deferred items.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One-time proof, part 1: after the owner lands the branch on `main`, run the runbook's read-only preflight (it STOPS on any existing bot ref or open `registry-bot` issue), dispatch the bot (`workflow_dispatch --ref main`) on the real drift that exists there (no stale-pin fixture; no bot branch means STOP, nothing proved, review round 2 H3), confirm it pushes a `bot/registry-<date>` branch whose parent is the recorded base and opens one tracking issue (D-11, round 2 H4); then the same-day rerun on an unchanged base must SKIP (`nothing to publish`, same head SHA, no second CI run, one branch, one issue; review M3, H4, round 2 H1) and the proof restarts if the UTC date changes (round 2 M4) | BOT-01, BOT-02 | Needs the workflow file on the default branch and a remote write; no agent ever pushes, merges or fast-forwards `main` | The owner runs the commands of `docs/registry-bot-proof.txt` (plain-text runbook, plan 33-04) after landing; its Cleanup section removes the temporary protection (404 read-back), deletes the proof and bot refs and closes only the issue it recorded |
| One-time proof, part 2: the check names reported for the bot branch head by the dispatched `ci.yml` run are exactly the two required names (`validate & test on ubuntu-latest` and `macos-latest`) and every CI run of that SHA is a `workflow_dispatch` (a push-event run is a STOP) | BOT-02 | Check-run names exist only on GitHub after a real dispatch | Runbook step: `gh run list --workflow ci.yml --commit "$SHA"` for the events and `gh api` the check runs of the head SHA to compare names and conclusions |
| One-time proof, part 3 (the BOT-02 question): do dispatched check runs on the bot branch head satisfy classic branch protection for a fast-forward of the same commit? | BOT-02 | GitHub-side behavior is unknown (assumption A1: docs only say dispatch checks do not satisfy a branch ruleset on a PR head); a failure stops the phase and the owner chooses a token route | Option A (runbook Part 3): a throwaway protected target branch with the same two required checks, fast-forwarded from the bot branch head; needs the owner's explicit approval of that temporary branch-protection write. Option B (zero-token fallback): the owner re-pushes the same SHA under a second branch name so normal push-event CI satisfies protection (assumption A3, unverified). Record the outcome in VERIFICATION; BOT-02 stays `human_needed` until it is recorded, is `passed` only when Option A accepted the fast-forward of the dispatched head (round 2 M5) and is never `passed` from the file-level tests or from a decision (review M2) |
| Closing keyword on fast-forward (D-08, `Closes #N` in the bot commit) is NOT exercised | BOT-01 | Cannot be proved without pushing to `main` (assumption A5) | VERIFICATION states it was not exercised; the issue body documents the owner-closes fallback; the proof must not claim it |
| Cron enabled after the proof passes (the follow-up commit) | BOT-01 | Depends on the proof outcome; owner's commit or a trivial deferred task | After the proof passes, one commit adds the off-minute Monday cron and the matching trigger-set assertion |
| Ad-hoc `actionlint` run on the new and edited workflow files (D-16), before and after the edits | BOT-01, BOT-02, BOT-03 | Not run by an executor: the research's container attempt was blocked by the permission classifier (decision 6) | Orchestrator, at the phase gate: image `rhysd/actionlint:1.7.12` (image name assumed A10, confirm on first pull), local files only, disposable container, remove an image that was absent before. Record the output in VERIFICATION; if it cannot run, VERIFICATION says "not run" and why, never a pass |
| First real bot run bumps draw.io to `32.7.4`: `version = "32.7.4"`, the two macOS zip `sha256` values and today's `verified`, for `drawio-desktop` only (no other tool re-dated) | BOT-01, BOT-04 | Needs a real run on the remote after landing and the live upstream release | After landing and the proof, inspect the bot branch diff: only `installer/registry.toml`, only the drawio-desktop pins; the next Monday drift run (2026-11-23) is the first that can report the same drift |
| Push restriction on the default branch (review round 2 H2): the bot token could push an already-green commit there because the repository sets no push restriction; no bot step does | BOT-03 | A repository setting outside this phase; BOT-03's SPEC acceptance stays the structural one | The owner decides separately whether to add a push restriction; listed as a deferred item and a backlog candidate in the phase VERIFICATION |
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
