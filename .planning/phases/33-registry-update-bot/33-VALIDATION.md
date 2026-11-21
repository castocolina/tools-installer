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
> Seeded from 33-RESEARCH.md "Validation Architecture" and the orchestrator decisions of 2026-11-21 (all provisional, "needs confirmation"). The per-task rows below are placeholders keyed to the requirements; the planner replaces the `33-NN-NN` ids, plan and wave numbers with the real ones.

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

Placeholder rows: task ids are `33-<plan>-<task>`; the planner fills the real ids, plans and waves. Every plan's last task also runs `make validate` once and `make test` once (not repeated per row). `DEP` is the Dependabot requirement (SPEC R5, "actions-version updates"), which has no BOT id.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 33-NN-01 | NN | 1 | BOT-04 | T-33-NN / — | `--write --bumps-only` leaves a date-only registry byte-identical and the same fixture without the flag changes it; a real bump with the flag changes `version`, `sha256` and `verified` together (candidate passes, `_github_pin_registry`); a no-drift registry is unchanged with and without the flag; a passing non-bumped tool is not dated and prints no `dated <tool>` line; `--bumps-only` without `--write` exits 64 and does no network work; the bump is never written without a verified hash (`_build_bump_edits` raises on a missing candidate hash) | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only --no-cov -q` | ❌ W0 | ⬜ pending |
| 33-NN-02 | NN | 2 | BOT-01 | T-33-NN | The bot workflow triggers exactly `{"workflow_dispatch"}` in the committed first state (cron DISABLED, decision 1, D-12) and an off-minute Monday cron only in the follow-up commit that enables it; a guard step id carries an `if:` on every publishing step; the cache save has `always()`; `--bumps-only` is present and `--issue` is not; no `${{` appears in any `run` text; `timeout-minutes` is at least 60 (decision 9) | workflow | `uv run pytest tests/test_registry_bot_workflow.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 33-NN-03 | NN | 2 | BOT-01 | T-33-NN | Concurrency group `registry-bot` with `cancel-in-progress: false`; the D-05 deletion step is limited to the `refs/heads/bot/registry-` namespace and excludes the current branch; the fetch uses the explicit `+refs/heads/<branch>:refs/remotes/origin/<branch>` refspec, tolerates an absent bot branch (`|| true` under `bash -e`) and the push uses `--force-with-lease=<ref>:<expected or empty>` (decision 5) | workflow | `uv run pytest tests/test_registry_bot_workflow.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 33-NN-04 | NN | 2 | BOT-02 | T-33-NN | `ci.yml` gains `workflow_dispatch`; the bot dispatch step is `gh workflow run ci.yml --ref "$BRANCH"` with the branch read from `env:`; `tests/test_ci_workflow.py` is amended at its trigger assertions (`:41`, `:52`, plans cite the real current lines) | workflow | `uv run pytest tests/test_ci_workflow.py tests/test_registry_bot_workflow.py --no-cov -q` | ✅ exists (amend) + ❌ W0 | ⬜ pending |
| 33-NN-05 | NN | 2 | BOT-03 | T-33-NN | Workflow permissions are exactly `{"contents": "write", "actions": "write", "issues": "write"}`; no `run` text targets `main` (regex covering `HEAD:main`, `refs/heads/main`, `origin main`, `:main\b`, `gh pr`, and no false positive on `bot/registry-` or the word "domain"); no `gh pr` and no merge step; `verify-registry.yml` keeps `contents: read` | workflow | `uv run pytest tests/test_registry_bot_workflow.py tests/test_verify_registry_workflow.py --no-cov -q` | ❌ W0 + ✅ exists | ⬜ pending |
| 33-NN-06 | NN | 3 | DEP (SPEC R5) | T-33-NN | `.github/dependabot.yml` parses as one `github-actions` entry with a schedule and no other ecosystem (pure parse) | unit | `uv run pytest tests/test_registry_bot_workflow.py --no-cov -q` | ❌ W0 | ⬜ pending |
| 33-NN-07 | NN | 3 | BOT-02 | T-33-NN | The committed proof runbook (`scripts/registry-bot-proof.sh`, or a documented command list the planner chooses by the smaller testable design) holds the exact D-11 `gh` sequence, states what it writes to the remote and its cleanup (delete the proof and bot refs, close the issue), names Option A (throwaway protected target, owner's explicit approval of the temporary branch-protection write) and Option B (the owner re-pushes the same SHA under a second branch name, assumption A3, unverified); a host test checks the file, never runs `gh` | host | `uv run pytest tests/test_registry_bot_workflow.py --no-cov -q` (or the runbook's own test file) | ❌ W0 | ⬜ pending |
| 33-NN-08 | NN | 4 | BOT-01 to BOT-04, DEP | — | Phase gate: `make validate` then `make test`, once each, green on the final tree | gate | `make validate && make test` is NEVER chained at a commit; run each once at the phase gate | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_registry_bot_workflow.py` — new, with its own small `_load(path)` and `_triggers(data)` (the existing `_load_verify` / `_steps` / `_triggers` are hard-wired to `verify-registry.yml` and stay untouched; decision 2); stubs for BOT-01, BOT-02, BOT-03 and DEP
- [ ] `tests/test_verify_registry.py` — `--bumps-only` tests appended (fixtures exist at `:2542` and `:2896`) for BOT-04
- [ ] `tests/test_ci_workflow.py` — amend the trigger assertions at `:41` and `:52` for the `workflow_dispatch` addition (BOT-02)
- [ ] The no-main assertion scans `run` texts with a regex covering `HEAD:main`, `refs/heads/main`, `origin main`, `:main\b` and `gh pr`, and does not false-positive on `bot/registry-` or "domain" (BOT-03)

Framework install: none. Cron trigger assertion: assert the final target set `{"schedule", "workflow_dispatch"}` only in the follow-up commit that enables the cron (decision 1).

---

## Manual-Only Verifications

Decision 1 (provisional, needs confirmation): no plan and no agent step performs any remote write of the proof. GitHub dispatches only a workflow file that exists on the default branch, and `origin/main` does not carry this work; the owner fast-forwards `main`. The phase's code is complete and tested without the proof; the phase verification is `human_needed` with these rows as deferred items.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| One-time proof, part 1: after the owner lands the branch on `main`, dispatch the bot (`workflow_dispatch`) and confirm it pushes a `bot/registry-<date>` branch and opens or updates one tracking issue (D-11) | BOT-01, BOT-02 | Needs the workflow file on the default branch and a remote write; no agent ever pushes, merges or fast-forwards `main` | The owner runs the `scripts/registry-bot-proof.sh` runbook (or its documented command list) after landing; it deletes the proof and bot refs and closes the issue at the end |
| One-time proof, part 2: the check names reported for the bot branch head by the dispatched `ci.yml` run are exactly the two required names (`validate & test on ubuntu-latest` and `macos-latest`) | BOT-02 | Check-run names exist only on GitHub after a real dispatch | Runbook step: `gh api` the check runs of the branch head SHA and compare names, `event` field and conclusion |
| One-time proof, part 3 (the BOT-02 question): do dispatched check runs on the bot branch head satisfy classic branch protection for a fast-forward of the same commit? | BOT-02 | GitHub-side behavior is unknown (assumption A1: docs only say dispatch checks do not satisfy a branch ruleset on a PR head); a failure stops the phase and the owner chooses a token route | Option A (runbook): a throwaway protected target branch with the same two required checks, fast-forwarded from the bot branch head; needs the owner's explicit approval of that temporary branch-protection write. Option B (zero-token fallback): the owner re-pushes the same SHA under a second branch name so normal push-event CI satisfies protection (assumption A3, unverified). Record the outcome in VERIFICATION |
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
