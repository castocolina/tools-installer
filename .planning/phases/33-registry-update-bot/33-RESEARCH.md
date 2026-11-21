# Phase 33: Registry update bot - Research

**Researched:** 2026-11-21
**Domain:** GitHub Actions (scheduled/dispatched bot, branch protection interplay), Dependabot config, one small argparse change in `installer/verify_registry.py`, workflow tests
**Confidence:** MEDIUM (code and repo facts HIGH; the single decisive Actions question, whether a `workflow_dispatch` run satisfies the protected `main`'s required checks, is NOT answerable from docs or read-only calls and must be proved)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-01: `.github/workflows/registry-bot.yml`, triggers `schedule` and `workflow_dispatch` only. Weekly on Monday after the drift run, an off-minute cron such as `37 6 * * 1`, so it restores the cache the 05:17 drift run saved. It first lands with `workflow_dispatch` only; the cron is enabled in a follow-up commit after the proof (D-12).
D-02: The bot runs `uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only` directly, not through `make`. Exit 0, 1 and 2 continue to the guard; exits 64, 70 and 73 fail the job. It never passes `--issue`.
D-03: A guard step with an id runs `git diff --quiet -- installer/registry.toml` and sets an output; every publishing step (commit and push, issue upsert, CI dispatch) has an `if:` on it. One job. The cache save may still run `always()`.
D-04: The branch is `bot/registry-$(date -u +%F)` committed on the run ref's HEAD. The bot fetches that one ref first, then pushes `HEAD:refs/heads/bot/registry-<date>` with `--force-with-lease` to that ref only. The branch name reaches `run:` through `env:`, never through an expression inside `run`.
D-05 (provisional, own reasoning): After a successful push the bot deletes older `bot/registry-*` refs, so one live branch exists; the deletion has its own workflow test.
D-06 (provisional, jev overridden): `concurrency: { group: registry-bot, cancel-in-progress: false }` (queue).
D-07: Permissions exactly `contents: write`, `actions: write`, `issues: write`, `GH_TOKEN: ${{ github.token }}`; `verify-registry.yml` keeps `contents: read, issues: write`.
D-08: The tracking issue uses a new label `registry-bot` with an inline `gh` upsert (label create `--force`, list open, edit or create), not `registry-drift`. The bot commit carries a closing keyword for the issue (issue upsert first, then commit and push); verified at the proof, fallback is the owner closing it. (closing keyword: own reasoning)
D-09 (provisional, jev overridden): The bot shares the drift workflow's state cache (path `~/.local/state/tools-installer/verify-registry.json`, restore-keys `verify-registry-`, save with `always()` and a key containing `github.run_id`).
D-10: `ci.yml` gains a bare `workflow_dispatch:` with no inputs; push filter, concurrency group, job id, job name and steps stay. The bot runs `gh workflow run ci.yml --ref "$BRANCH"` (branch from `env:`) only when the guard says the registry changed. `tests/test_ci_workflow.py:41` becomes `{"push", "workflow_dispatch"}` and `:52` is matched by prefix.
D-11 (provisional, jev overridden): The proof runs the real bot on a throwaway ref at an owner-approved checkpoint: push `proof/registry-bot-<date>` with a deliberately stale drawio-desktop pin; dispatch `registry-bot.yml --ref` that branch; watch `gh run list --workflow ci.yml --branch bot/registry-<date> --json event,conclusion`; read `gh api repos/{o}/{r}/commits/<head>/check-runs` and compare names with the protection contexts; dispatch again the same day to prove update-not-create and a single issue; delete the throwaway and bot branches and close the proof issue; record in VERIFICATION. On failure stop and ask the owner about the token route.
D-12 (provisional, own reasoning): Rollout: land the workflows with `workflow_dispatch` only, run the proof, then enable the cron in a follow-up commit. GitHub needs a workflow file on the default branch to dispatch it (to be confirmed in planning).
D-13 (own reasoning): The flag is `--bumps-only` and requires `--write` (exit 64 with a usage message otherwise). The filter lives in `_registry_edits_for_write`: bump edits are kept and `verified` is kept only for tools with an applied bump; a lone `verified` change is dropped; the stderr `dated <tool>` loop prints only tools actually dated.
D-14: Unit tests reuse `_two_tool_write_fixture` (date-only: byte-identical with the flag, changed without it), `_github_pin_registry` (real bump keeps all three keys), a no-drift registry unchanged either way, `--bumps-only` without `--write` exits 64; fixed `today`, fake `Probe`, `tmp_path` state.
D-15 (jev overridden): New `tests/test_registry_bot_workflow.py` (reusing `_load`/`_triggers` from `tests/test_verify_registry_workflow.py:13-23`) asserts triggers and off-minute crons, exact permissions, concurrency group, guard step id with `if:` on every publishing step, no `run` that targets `main`, `HEAD:main` or `refs/heads/main` (and no `gh pr`/merge), the dispatch step text, no `${{` inside any `run`, no `--issue`, `--bumps-only` present; the dependabot assertions live in the same file.
D-16 (own reasoning): No new lint gate. The workflow tests are the gate, plus one ad-hoc `actionlint` run in a disposable container recorded in VERIFICATION. A permanent gate is deferred to Backlog 999.23.
D-17 (own reasoning): `.github/dependabot.yml`: `version: 2`, one `github-actions` entry, `directory: "/"`, weekly, one group matching `"*"`.
D-18: No change to `devtools/docs_only.py` `TEST_READ` or `tests/test_docs_only.py` `LEDGER`.

### Claude's Discretion
Issue title and body text, the commit message wording, and the cron minute within the Monday window.

### Deferred Ideas (OUT OF SCOPE)
- A permanent workflow-lint gate (actionlint): Backlog 999.23.
- To confirm in planning: whether `workflow_dispatch` needs the workflow on the default branch (assumed yes, D-12); whether a closing keyword in a fast-forward push to the default branch closes the issue (checked at the proof); Dependabot `groups` with `"*"` without a PR merge flow.
- Out of scope (SPEC): auto-landing; a real pull request; bumping pins without a `version`; changing what `verify-registry` verifies; Renovate; phases 34-35.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOT-01 | Scheduled or dispatched workflow runs `verify-registry --write`, pushes `bot/registry-<date>` only when `registry.toml` changed, `version`/`sha256`/`verified` bumped together | Bot step skeleton, guard pattern, `--force-with-lease` experiment, bump fixture, live drift facts (drawio-desktop 32.6.10 -> 32.7.4 with real digests) |
| BOT-02 | Required checks run on the bot branch head via `workflow_dispatch` of `ci.yml` (token route is the owner's choice), verified once on a throwaway branch | Actions facts, the unresolved ruleset/dispatch doc warning, a proof design that avoids touching `main`, cleanup list |
| BOT-03 | Bot never pushes to `main`; reaches `main` by branch push + green CI + fast-forward; drift workflow keeps `contents: read` | Permissions table, no-main test patterns, live protection read |
| BOT-04 | `--write` skip-date-only flag | Exact edit points in `installer/verify_registry.py`, fixtures, exit-code placement |
</phase_requirements>

## Summary

The design in CONTEXT is sound and almost every code citation still matches, but three facts change how the plan must be shaped. First, this branch is 175 commits ahead of `origin/main` and `main` has not moved (`git rev-list --count origin/main..HEAD` = 175, `HEAD..origin/main` = 0), so `registry-bot.yml` cannot exist on the default branch until the owner fast-forwards the phase work to `main`. GitHub only dispatches a workflow whose file is on the default branch, so the D-11 proof (dispatch `registry-bot.yml --ref proof/...`) cannot run from this branch; D-12's "to be confirmed in planning" is confirmed: it is true and it makes the proof an after-landing owner checkpoint, not something the phase branch can do first. Second, GitHub's own troubleshooting page warns that checks from a `workflow_dispatch` run do not satisfy required checks of a branch **ruleset** ("Even if the checks pass for the head commit, they do not satisfy a required status check in a branch ruleset"); `main` here uses classic branch protection (no rulesets: `gh api repos/castocolina/tools-installer/rulesets` returns `[]`), and the docs do not say what classic protection does with a non-PR ref. So BOT-02 is a real risk, and the proof is not ceremonial. Third, `tests/test_verify_registry_workflow.py`'s `_triggers()` is hard-wired to `verify-registry.yml`, so D-15's "reuse `_load`/`_triggers`" cannot be done literally.

The code change is small and the line numbers in CONTEXT are accurate (`_registry_edits_for_write` at `installer/verify_registry.py:1330-1339`, usage check at `:1580-1581`). Live registry: nine methods carry a `version` pin now (drawio-desktop 2, sublime 3, ghostty 2, bruno 2). `verify-registry` run today (cold state, run on this host) reports exactly one drift item, drawio-desktop 32.6.10 -> v32.7.4; Ghostty and Bruno pass with pins that equal the GitHub API digests; Sublime reports `no release source` and stays manual. The first real bot run will therefore propose the draw.io bump.

**Primary recommendation:** Build to CONTEXT as written, implement `--bumps-only` as a keyword argument of `_registry_edits_for_write`, give the new workflow test its own tiny loader, land everything with `workflow_dispatch` only, and treat the after-landing proof as the phase's only remote-writing checkpoint, with a throwaway protected target branch (not `main`) as the way to prove "dispatch satisfies required checks" without ever pushing to `main`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Detect upstream drift and verify digests | Python CLI (`installer/verify_registry.py`) | GitHub API | Existing logic; the bot only wraps `--write` |
| Skip date-only edits | Python CLI (`_registry_edits_for_write`) | - | The edit set is built there; a workflow `git diff` filter cannot tell a date from a bump |
| Decide "changed" and publish branch/issue/dispatch | GitHub Actions workflow | `gh` CLI, git | Pure orchestration, guarded by one `git diff --quiet` step |
| Run required checks on the bot head | GitHub Actions (`ci.yml` dispatch) | Branch protection | `GITHUB_TOKEN` pushes start no run; only dispatch does |
| Land the change | Owner (local git) | Branch protection | `git push origin <branch>:main` fast-forward; no bot token reaches `main` |
| Keep action versions current | Dependabot (`github-actions`) | - | Native; cannot parse `registry.toml` |
| Workflow regression gate | pytest + PyYAML tests | one ad-hoc `actionlint` run | House pattern (one test file per workflow) |

## Standard Stack

### Core
| Library / tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| `actions/checkout` | `@v4` (existing pin) | Check out the run ref; `persist-credentials` default lets `git push` use the job token | Used by both existing workflows [VERIFIED: .github/workflows/ci.yml:25 `uses: actions/checkout@v4`] |
| `astral-sh/setup-uv` | `@v5` (existing) | uv for `uv run --isolated --no-dev` | [VERIFIED: .github/workflows/verify-registry.yml:27 `uses: astral-sh/setup-uv@v5`] |
| `actions/cache/restore` + `actions/cache/save` | `@v4` (existing) | Share the verify-registry state file | [VERIFIED: verify-registry.yml:31 `uses: actions/cache/restore@v4`, :52 `uses: actions/cache/save@v4`] |
| `gh` CLI | preinstalled on runners; local 2.101.0 | issue upsert, `gh workflow run` | Used by the drift workflow already (`gh issue list`, `gh issue close`) |
| PyYAML | `pyyaml>=6.0.3` (dev dep) | Parse workflows/dependabot in tests | [VERIFIED: pyproject.toml:29 `"pyyaml>=6.0.3",`] |

No new Python or npm package is introduced; the Package Legitimacy Gate does not apply (nothing installs). actionlint is run from a container image only for the ad-hoc check (see Environment Availability) and is not a project dependency.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `GITHUB_TOKEN` + `gh workflow run` | PAT / GitHub App token | Stores a secret; only if the proof fails (SPEC R2) |
| Owner re-push of the same SHA under a second branch name | n/a | Zero-token fallback if dispatch checks do not satisfy protection; the push event is user-initiated so it starts a normal CI run on that SHA [ASSUMED] (see A3) |
| Dependabot group `"*"` | per-ecosystem separate PRs | D-17 chose one group |

**Installation:** none.

## Architecture Patterns

### System Architecture Diagram

```
schedule (Mon, off-minute) ---+
workflow_dispatch (owner) ----+--> registry-bot job (ubuntu-latest, concurrency group registry-bot, queue)
                                   |
                                   v
                      checkout run ref HEAD + setup-uv + cache restore (verify-registry-*)
                                   |
                                   v
        uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only
           exit 0/1/2 -> continue      exit 64/70/73 -> job fails (no publish)
                                   |
                                   v
              guard: git diff --quiet -- installer/registry.toml  -> output changed=true|false
                       |                                   |
                  changed=false                       changed=true
                  (publishing steps skipped)               |
                                                           v
                              issue upsert (label registry-bot; edit or create) -> number N
                                                           |
                                                           v
                  git commit installer/registry.toml (message has "Closes #N")
                                                           |
                                                           v
        git fetch origin +refs/heads/$BRANCH:refs/remotes/origin/$BRANCH || true
        git push --force-with-lease=refs/heads/$BRANCH origin HEAD:refs/heads/$BRANCH
                                                           |
                       +-----------------------------------+
                       v                                   v
        delete other bot/registry-* refs (D-05)    gh workflow run ci.yml --ref "$BRANCH"
                                                           |
                                                           v
                    CI check runs on the branch head (validate & test on ubuntu/macos)
                                                           |
                                                           v
        OWNER: git fetch; git push origin bot/registry-<date>:main  (fast-forward, protected flow)
        cache save (always()) runs regardless of the guard
```

### Recommended Project Structure
```
.github/
├── dependabot.yml                     # new, ~8 lines
└── workflows/
    ├── ci.yml                         # + bare workflow_dispatch:
    ├── registry-bot.yml               # new
    └── verify-registry.yml            # unchanged
installer/verify_registry.py           # + --bumps-only
tests/
├── test_ci_workflow.py                # amend :41 and :52
├── test_registry_bot_workflow.py      # new (workflow + dependabot assertions)
└── test_verify_registry.py            # + 4 tests for --bumps-only
```

### Pattern 1: Flag as keyword argument of the existing edit builder
**What:** Add `bumps_only: bool = False` to `_registry_edits_for_write` and filter the `verified` loop; let the stderr loop iterate the dated tools actually in `edits`.
**When:** BOT-04 (D-13).
```python
# installer/verify_registry.py (current shape, :1330-1339)
def _registry_edits_for_write(
    report: Report, bumps: Sequence[_BumpResult], write_day: date
) -> list[RegistryEdit]:
    edits: list[RegistryEdit] = []
    for bump in bumps:
        if bump.applied:
            edits.extend(bump.bump_edits)
    for tool_id in report.passed_tools():
        edits.append(RegistryEdit(tool_id, None, "verified", write_day.isoformat()))
    return edits
```
Target: `bumped = {b.tool_id for b in bumps if b.applied}`; in the second loop `if bumps_only and tool_id not in bumped: continue`. In `_run_verify_registry` the call at `:1603` passes `bumps_only=args.bumps_only`, and the loop at `:1612-1613` (`for tool_id in report.passed_tools(): print(f"dated {tool_id}", file=sys.stderr)`) becomes a loop over the tools that have a `verified` edit (`[e.tool_id for e in edits if e.key == "verified"]`). Note the existing (unflagged) loop prints a `dated` line for every passed tool whether or not its date text changed; keep that behavior unflagged to avoid changing unrelated output.

### Pattern 2: Guard output + `if:` on every publishing step
```yaml
- name: Guard
  id: guard
  run: |
    if git diff --quiet -- installer/registry.toml; then
      echo "changed=false" >> "$GITHUB_OUTPUT"
    else
      echo "changed=true" >> "$GITHUB_OUTPUT"
    fi
- name: Publish
  if: steps.guard.outputs.changed == 'true'
```
`git diff --quiet` exits 0 when clean and 1 when dirty [VERIFIED: local experiment, git 2.56.0: `clean rc=0`, `dirty rc=1`].

### Pattern 3: single-ref fetch then explicit-ref lease (D-04)
Local experiment against a scratch bare repo (git 2.56.0), all outputs observed:
- Ref absent: `git fetch --no-tags origin "+refs/heads/$B:refs/remotes/origin/$B"` fails (`fatal: couldn't find remote ref refs/heads/bot/registry-2026-11-21`, rc 128). The step runs under `bash -e`, so the fetch must be written `... || true`. The following `git push --force-with-lease="refs/heads/$B" origin "HEAD:refs/heads/$B"` then succeeds as a create (rc 0).
- Ref present, fresh clone fetched with the explicit `+src:refs/remotes/origin/$B` refspec: the lease passes and the push is a forced update (`+ 0563ad9...5c0d08f HEAD -> bot/registry-2026-11-21 (forced update)`, rc 0).
- Ref present but fetch skipped (stale tracking info): the push is rejected `! [rejected] ... (stale info)`, rc 1.
Therefore the fetch must write the remote-tracking ref (the explicit `+refs/heads/$B:refs/remotes/origin/$B` refspec), not only `FETCH_HEAD` [VERIFIED: local experiment]. Where `git` on the runner differs from 2.56.0 the behavior of `--force-with-lease=<ref>` without `:<expect>` is long documented; treat as stable [ASSUMED].

Listing the other bot refs for D-05: `git ls-remote --heads origin 'refs/heads/bot/registry-*'` printed both refs and `git push origin --delete bot/registry-2026-11-14` deleted one (rc 0) [VERIFIED: local experiment]. Exclude the just-pushed branch before deleting.

### Pattern 4: run steps take values from `env:`
```yaml
- name: Publish branch
  if: steps.guard.outputs.changed == 'true'
  env:
    ISSUE_NUMBER: ${{ steps.issue.outputs.number }}
  run: |
    BRANCH="bot/registry-$(date -u +%F)"
    ...
```
`date` and shell variables are not expressions, so no `${{` appears inside `run`. The house rule is enforced for CI by `test_no_run_step_interpolates_an_expression` [VERIFIED: tests/test_ci_workflow.py:83-86 `def test_no_run_step_interpolates_an_expression() -> None:` / `assert "${{" not in step.get("run", ""), step["name"]`]; the new file must carry the same assertion (D-15).

### Anti-Patterns to Avoid
- **Pushing with a PAT/App token "just in case":** SPEC R2 forbids a stored secret unless the proof fails.
- **`make verify-registry` in the bot:** GNU make turns any non-zero exit into 2 (D-02), which would hide 64/70/73 from the guard.
- **Dispatching from a non-default ref carelessly:** a manual `gh workflow run registry-bot.yml --ref <other-branch>` makes the bot commit on that branch's HEAD, so the bot branch would carry unrelated commits (see Pitfall 6).
- **Interpolating `github.ref_name` / branch names into `run`:** script injection; use `env:`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bump `version` + `sha256` + `verified` | A TOML rewriter or sed in the workflow | `verify-registry --write` (existing `apply_registry_edits`, `_plan_bumps`) | Already verifies the candidate digest before writing and refuses on concurrent edits |
| Workflow assertions | String greps over YAML text | `yaml.safe_load` + dict assertions (house pattern) | The `on:` key parses to `True` (see Pitfall 3) |
| Actions version bumps | Custom script | Dependabot `github-actions` | Native |
| Issue upsert | New Python helper | Inline `gh label create --force` / `gh issue list` / `gh issue edit|create` (D-08), same shape as `upsert_drift_issue` (`installer/verify_registry.py:1419-1459`) | One-job inline pattern already used by the drift workflow |

**Key insight:** every hard part (digest verification, atomic edit, drift detection) already exists; the phase is orchestration plus one filter.

## Runtime State Inventory

Not a rename/refactor phase; omitted. (The only state touched is the Actions cache key family `verify-registry-*`, covered under D-09.)

## CONTEXT Reconciliation

Every CONTEXT statement that cites a file and line, checked against the code as it is now (this branch, tip `9a151560`).

| CONTEXT says | Code now | Plan should |
|--------------|----------|-------------|
| `installer/verify_registry.py:1330-1339` is `_registry_edits_for_write` | Unchanged: `:1330` def through `:1339` `return edits` [VERIFIED: read 1330-1339] | Edit in place (Pattern 1) |
| argparse block `:1551-1565` | Parser args at `:1551` (`--registry`), `:1552` (`--state`), `:1554` (`--write`), `:1559` (`--candidate`), `:1566` (`--issue`) [VERIFIED: rg line numbers]; the block runs to about `:1570` | Add `--bumps-only` after `--candidate`/before `--issue` (or after `--issue`); the range is slightly wider than CONTEXT says, not shifted |
| usage check "like `--candidate requires --write` at `:1581`" | `:1580` `if explicit and not args.write:` / `:1581` `print("--candidate requires --write", file=sys.stderr)` [VERIFIED] | Add `if args.bumps_only and not args.write:` next to it, before any probe/network work (the existing test `test_candidate_usage_errors_cost_no_network` pattern, `tests/test_verify_registry.py:3465-3500`, shows usage errors must cost no network) |
| exit codes 64, 70, 73 | `EXIT_USAGE = 64`, `EXIT_WRITE_REFUSED = 73`, `EXIT_INTERNAL = 70` at `:59-61` [VERIFIED]; module docstring line 4 and `_EXIT_EPILOG` still say "`--candidate` usage error" | Reword the docstring and epilog to "usage error (`--candidate`, `--bumps-only`)"; `test_help_lists_the_exit_codes` (`tests/test_verify_registry.py:3573-3578`) only asserts the three numbers appear |
| `tests/test_ci_workflow.py:41` is `set(triggers) == {"push"}` | Exact: `:41 assert set(triggers) == {"push"}` and `:42` `assert triggers["push"] == {"branches-ignore": ["main"]}` [VERIFIED] | Change `:41` to `{"push", "workflow_dispatch"}`; keep `:42`. A bare `workflow_dispatch:` loads as key present with value `None` |
| `:52` is `uses == "actions/checkout@v4"` | Exact: `:52 checkout = next(step for step in _steps() if step.get("uses") == "actions/checkout@v4")` [VERIFIED] | Match `str(step.get("uses", "")).startswith("actions/checkout@")` |
| `tests/test_ci_workflow.py:84-86` (no-`${{` in run) | The test is `:83-86`; the assertion is `:85` [VERIFIED] | Cosmetic only |
| `tests/test_verify_registry_workflow.py:13-23` are `_load`/`_triggers` | The helpers are `_load_verify` (`:13`), `_steps` (`:17`), `_triggers` (`:21-23`) and all three read the module constant `VERIFY_WORKFLOW` [VERIFIED: read 1-24]. There is no `_load`; `_triggers()` takes no argument | **Divergence that blocks literal reuse.** In `tests/test_registry_bot_workflow.py` define a local `_load(path)` and `_triggers(data)` (about 8 lines) rather than importing the verify-bound ones; optionally refactor the old file to take a path, but that churns a passing file for no gain |
| `:31-33` reject minute-0 crons | `:31 assert set(crons) == {"17 5 * * 1", "47 5 * * 4"}`, `:32-33 for cron in crons: assert not cron.startswith("0 ")` [VERIFIED] | New test applies the same off-minute rule; use `37 6 * * 1` or any non-`0 ` minute. Note the rule only forbids the literal prefix `"0 "` |
| `:37` keeps `contents: read, issues: write` | The assertion is at `:38 assert data["permissions"] == {"contents": "read", "issues": "write"}` (`:36` is the `def`) [VERIFIED] | Leave untouched; the new test must not weaken it. Cosmetic one-line shift |
| `Makefile:27-28` thin wrapper | `Makefile:27 verify-registry:` and `:28 uv run --isolated --no-dev python -m installer.verify_registry $(ARGS)` [VERIFIED via rg -n and sed] | None |
| "five methods carry a `version`" / "bot can auto-bump only drawio-desktop (2 of the 5 pinned methods)" (SPEC background, CONTEXT specifics) | `rg -c '^version *=' installer/registry.toml` = 9 now. Per tool: sublime 3 (`registry.toml:2601,2622,2632`, version `4215`), ghostty 2 (`:3229,3240`, `1.4.0`), drawio-desktop 2 (`:3469,3479`, `32.6.10`), bruno 2 (`:3604,3613`, `4.3.0`) [VERIFIED: rg output] | The bot can now bump 6 of 9 (drawio, ghostty, bruno); sublime (3) stays manual with `--candidate`. Update any plan text that says "2 of 5" |
| "the workflows use four action families" (D-17) | Distinct `uses` repos: `actions/checkout`, `astral-sh/setup-uv`, `actions/cache` (restore and save sub-actions) = three repositories, four `uses` lines per file-pair [VERIFIED: rg `uses:` output above] | The `"*"` group still matches all; just say "three" |
| D-01 "restores the cache the 05:17 drift run saved" | The 05:17/05:47 crons do not fire then: the last six scheduled runs were created 2026-11-19T14:41, 11-16T13:38, 11-12T13:59, 11-09T13:53, 11-05T13:29, 11-02T13:29 UTC [VERIFIED: `gh run list` output], 8 to 9 hours after the cron | Do not rely on ordering between the two crons; the cache is a speed-up only (a warm drift run took ~13 s to ~2 min, `updatedAt - createdAt`). Keep D-09, drop the ordering rationale |
| D-12 "GitHub needs a workflow file on the default branch (to be confirmed)" | Confirmed by GitHub Docs (see GitHub Actions Facts); and `origin/main` is 175 commits behind this branch, so no phase-33 file is on `main` | Plan the proof as an after-landing owner checkpoint (see The Proof) |

## GitHub Actions Facts

| # | Fact | Status | Source |
|---|------|--------|--------|
| F1 | Events caused by `GITHUB_TOKEN` create no workflow run, except `workflow_dispatch` and `repository_dispatch` | CONFIRMED | [CITED: docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows] "With the exception of `workflow_dispatch` and `repository_dispatch`, other `GITHUB_TOKEN`-triggered events do not create workflow runs at all." and [CITED: docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow] "`workflow_dispatch` and `repository_dispatch` events always create workflow runs." |
| F2 | `gh workflow run` needs `actions: write` | Permission name confirmed; the GITHUB_TOKEN-to-endpoint mapping is documented only for PATs (`repo` scope) | [CITED: docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax] "`actions: write` permits an action to cancel a workflow run"; REST page: "OAuth tokens and personal access tokens (classic) need the repo scope to use this endpoint." The exact "Actions write covers dispatch" mapping for `GITHUB_TOKEN` is standard but not quoted: [ASSUMED] (A2); the proof exercises it |
| F3 | A workflow with any explicit `permissions:` key sets every unlisted permission to `none` | CONFIRMED | [CITED: workflow-syntax] "If you specify the access for any of these permissions, all of those that are not specified are set to `none`." The repo default is read: `gh api repos/castocolina/tools-installer/actions/permissions/workflow` -> `{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}` [VERIFIED: live call] |
| F4 | A workflow file must be on the default branch to receive `workflow_dispatch` | CONFIRMED | [CITED: events-that-trigger-workflows] "This event will only trigger a workflow run if the workflow file exists on the default branch." and [CITED: trigger-a-workflow] "This trigger only receives events when the workflow file is on the default branch." |
| F5 | After registration, dispatch can target any branch; `--ref` names the branch containing the workflow-file version to run | CONFIRMED (docs and CLI help) | [CITED: events-that-trigger-workflows] "Once a workflow has run at least once, you can dispatch it against any branch or tag via the GitHub API or GitHub CLI." and `gh workflow run --help` (gh 2.101.0): "-r, --ref string  Branch or tag name which contains the version of the workflow file you'd like to run" [VERIFIED: local help output]. Consequence: `ci.yml` is registered today (on `main`), but `main`'s `ci.yml` has no `workflow_dispatch`; whether a ref whose `ci.yml` has the trigger can be dispatched while the default branch copy lacks it is [ASSUMED] (A4). The phrase "has run at least once" is ambiguous for a never-run workflow file |
| F6 | Scheduled workflows run only from the default branch; a schedule can be delayed under load; public-repo schedules are disabled after 60 idle days | CONFIRMED, and the delay is large here | [CITED: events-that-trigger-workflows] "Scheduled workflows will only run on the default branch.", "The `schedule` event can be delayed during periods of high loads of GitHub Actions workflow runs.", "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." Observed: six consecutive drift runs 8-9 h after their cron [VERIFIED: live `gh run list`] |
| F7 | Concurrency: at most one running and one pending run per group; a new queued run replaces the pending one; group names are case-insensitive; `cancel-in-progress: false` leaves the running job alone | CONFIRMED | [CITED: docs.github.com/en/actions/using-jobs/using-concurrency] "there can be at most one running job or workflow in a concurrency group at any time." and "At most one job or workflow run can be `pending` in the concurrency group." and "any existing `pending` job or workflow in the same concurrency group will be canceled." So D-06 "queue" really means "one running + one latest pending"; with a weekly cron the practical effect is nil, but a third quick dispatch drops the middle one |
| F8 | Closing keyword in a commit message closes the issue when that commit is merged into the default branch | PARTLY CONFIRMED | [CITED: docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue] "The issue will be closed when you merge the commit into the default branch." The docs do not address a fast-forward `git push origin <branch>:main` and do not separate it from a PR merge; that a direct push of a commit carrying `Closes #N` closes the issue is widely observed behavior but not shown in these docs: [ASSUMED] (A5). The proof cannot test it (it must not push to `main`). Keywords: close(s/d), fix(es/ed), resolve(s/d), optionally followed by a colon |
| F9 | Required checks must pass on the latest commit SHA; success, skipped, neutral count as passing | CONFIRMED | [CITED: docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks] "Required checks must pass on the latest commit SHA. Checks from earlier commits don't satisfy the requirement." and "Successful check statuses are `success`, `skipped`, and `neutral`." |
| F10 | **Dispatch-run checks vs required checks: documented as NOT satisfying a branch ruleset** | **UNRESOLVED for classic protection; this is the BOT-02 risk** | Same page: "if a workflow is triggered by `workflow_dispatch` on a pull request's head branch, checks reported by its jobs do not appear in the pull request's checks section. Even if the checks pass for the head commit, they do not satisfy a required status check in a branch ruleset." and "Checks from workflow jobs are evaluated only when the run is triggered by an eligible event, such as `push` or `pull_request`" (the second sentence is a summary by the fetch tool, not a verbatim quote: treat as secondary). The text is about **rulesets** and a **PR head**; `main` here has no ruleset (`gh api repos/castocolina/tools-installer/rulesets` = `[]` [VERIFIED: live call]) and the flow uses no PR. Whether classic branch protection on a plain fast-forward push applies the same rule is not documented: [ASSUMED] unknown, decided only by the proof (A1) |
| F11 | Live protection of `main` | READ | `gh api repos/castocolina/tools-installer/branches/main/protection` -> `checks: [{"app_id":null,"context":"validate & test on ubuntu-latest"},{"app_id":null,"context":"validate & test on macos-latest"}]`, `enforce_admins: true`, `strict: true`, `restrictions: null`, `reviews: null`, force pushes disabled, deletions disabled [VERIFIED: live call 2026-11-21]. `app_id: null` means any app may produce the context |
| F12 | Repo facts | READ | Public repo, default branch `main`; `has_issues: true`; `allow_auto_merge: false`; Actions enabled with `allowed_actions: all`, `sha_pinning_required: false`; registered workflows: CI, verify-registry, Dependency Graph [VERIFIED: live calls]. `registry-drift` label exists; no `registry-bot` label yet; issue #5 (registry-drift) is closed |
| F13 | Actions caches are scoped by ref: the existing `verify-registry-*` caches belong to `refs/heads/main` | READ | `gh api repos/castocolina/tools-installer/actions/caches` lists `verify-registry-44546487853` etc. with `"ref":"refs/heads/main"` [VERIFIED: live call]. That a run on another ref may restore the default branch's caches but a cache it saves is invisible to `main` is the documented cache-scope rule, not re-checked here: [ASSUMED] (A6). Consequence: a proof run on `proof/...` restores main's state and saves its own to the proof ref (harmless, evicts later) |
| F14 | `actions/checkout` pins | READ | `ci.yml:25` `actions/checkout@v4`, `verify-registry.yml:25` same, `astral-sh/setup-uv@v5` at `ci.yml:29` and `verify-registry.yml:27`, `actions/cache/restore@v4`/`save@v4` [VERIFIED]. The only test that fixes a major tag is `tests/test_ci_workflow.py:52`; `test_verify_registry_workflow.py:50,52,66` use `startswith("actions/cache/restore"|"actions/cache/save")` and `not ... startswith("actions/cache@v4")` and survive a bump; `:63` `restore["with"]["restore-keys"].startswith("verify-registry-")` is key-based, not version-based. `test_ci_sets_up_uv_with_official_action` uses a substring match [VERIFIED: read both files] |
| F15 | Dependabot `groups` | CONFIRMED syntax, no GitHub Actions example in docs | [CITED: docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates] example shows `groups: <name>: applies-to: version-updates / patterns: - "*"` and the warning "using "*" may open a large pull request"; [CITED: dependabot-options-reference] "For GitHub Actions, use the value `/`." with "Dependabot will search the `/.github/workflows` directory"; `patterns` support `*`. Dependabot raises **pull requests** against the default branch [CITED: configuring-dependabot-version-updates]; this repo never merges PRs, so the owner lands a Dependabot update by fast-forwarding its `dependabot/github_actions/...` branch (CI runs there on `push`, `ci.yml` ignores only `main`) and the PR then closes itself or is closed by hand [ASSUMED] (A7). Dependabot docs in this session say nothing about a `dependabot.yml` needing to be on the default branch to take effect; Dependabot reads manifests from the default branch (that sentence is explicit), so treat the file as inert until it reaches `main` |

## Common Pitfalls

### Pitfall 1: Dispatching a workflow that is not on the default branch
**What goes wrong:** `gh workflow run registry-bot.yml --ref proof/...` fails because `main` has no such file (F4). Today `main` carries none of phases 27-33.
**How to avoid:** the proof runs after the owner fast-forwards the phase work to `main`. Plan the proof as the last, owner-gated step and keep the cron disabled until it passes (D-12).
**Warning signs:** HTTP 404 `workflow not found` / "could not find any workflows named registry-bot.yml" from `gh workflow run` [error text ASSUMED].

### Pitfall 2: `bash -e` kills the fetch for an absent ref
**What goes wrong:** the first run of the day has no remote bot branch; `git fetch ... refs/heads/$B` exits 128 and aborts the step before the push [VERIFIED: local experiment].
**How to avoid:** `git fetch --no-tags origin "+refs/heads/$B:refs/remotes/origin/$B" || true`, then the explicit-ref lease.

### Pitfall 3: PyYAML parses `on:` as `True`
**What goes wrong:** `data["on"]` raises `KeyError` [VERIFIED: tests/test_ci_workflow.py:37-40 comment, `data.get("on", data.get(True, {}))`].
**How to avoid:** copy the `data.get("on", data.get(True, {}))` fallback into the new test's `_triggers`.

### Pitfall 4: A cold `verify-registry` run is slow
**What goes wrong:** a cold-state run on this host (about 190 state entries) hit a 15-minute timeout and needed a second resumed run of about 20 minutes to finish [VERIFIED: this session, `timeout 900` exit 124 then a resumed run that exited 1 with the report]. The step timeout in the drift workflow is 25 min inside a 30 min job (`verify-registry.yml` `timeout-minutes: 30` job, `25` step) [VERIFIED: read]. Runner bandwidth is much higher than this host's, and warm runs take seconds to ~2 min.
**How to avoid:** share the cache (D-09), restore before the check and save `always()` after it so a timeout still keeps progress, give the bot job the same 30/25 minute timeouts, and keep the Thursday cron of the drift workflow as the cache refresher. The bot's own cache save must also run after a failed or timed-out run (`if: always()`).

### Pitfall 5: Same-day rerun creates a new commit SHA
**What goes wrong:** every run commits on a fresh checkout of the same base; author/committer time differs, so the SHA differs even if the tree is identical; `--force-with-lease` replaces the branch (no second branch, correct) but also re-dispatches CI, which cancels the previous CI run (`ci.yml` `concurrency: group: ci-${{ github.ref }}`, `cancel-in-progress: true` [VERIFIED: ci.yml:10-12]).
**How to avoid:** acceptable and consistent with SPEC ("update, not create"); if a quieter rerun is wanted, set a fixed `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` (the run date at 00:00Z) so identical content gives an identical SHA, then skip the dispatch when `git rev-parse HEAD` equals the fetched tracking ref. Optional, not required by any decision.

### Pitfall 6: A manual dispatch on a non-default ref builds on that ref
**What goes wrong:** the bot commits on the run ref's HEAD (D-04). Dispatching on `proof/...` (needed by D-11) is intended; dispatching on some other feature branch would produce a `bot/registry-<date>` branch containing those commits, and the owner could land them by accident.
**How to avoid:** say it in the issue body (base commit shown) and in the plan's runbook; do not add a ref guard that would block the proof.

### Pitfall 7: `GITHUB_TOKEN` push of a commit range that touches workflow files
**What goes wrong:** GitHub refuses a push by `GITHUB_TOKEN` that creates or updates a file under `.github/workflows/` without the `workflows` permission, which D-07 deliberately omits. In the proof the bot pushes one new commit that edits only `installer/registry.toml` on top of an already-pushed proof ref, so the new commit does not touch workflows; whether GitHub inspects only new commits or the whole range is [ASSUMED] (A8).
**How to avoid:** keep the proof ref pushed first; if the proof push is refused for this reason, record it and ask the owner (do not add `workflows: write`).

### Pitfall 8: `--bumps-only` must not break the unflagged path
`tests/test_verify_registry.py:2584-2622` (`test_write_dates_only_passing_tools`) asserts the unflagged run dates `tool_a` and leaves `tool_b`; keep it green. The new tests add the flagged twin of that fixture.

## Code Examples

### Bot job skeleton (shape, not final text)
```yaml
name: registry-bot

on:
  schedule:
    - cron: "37 6 * * 1"        # enabled only in the follow-up commit (D-12)
  workflow_dispatch:

permissions:
  contents: write
  actions: write
  issues: write

concurrency:
  group: registry-bot
  cancel-in-progress: false

jobs:
  bump:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      GH_TOKEN: ${{ github.token }}
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Set up uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - name: Restore verify-registry state
        uses: actions/cache/restore@v4
        with:
          path: ~/.local/state/tools-installer/verify-registry.json
          key: verify-registry-${{ github.run_id }}
          restore-keys: verify-registry-
      - name: Bump pins
        timeout-minutes: 25
        run: |
          code=0
          uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only || code=$?
          case "$code" in 0|1|2) ;; *) echo "verify-registry exited $code" >&2; exit "$code" ;; esac
      - name: Guard
        id: guard
        run: |
          if git diff --quiet -- installer/registry.toml; then echo "changed=false" >> "$GITHUB_OUTPUT"
          else echo "changed=true" >> "$GITHUB_OUTPUT"; fi
      # issue upsert -> commit -> fetch+lease push -> delete older refs -> gh workflow run ci.yml --ref "$BRANCH"
      # each carries: if: steps.guard.outputs.changed == 'true'
      - name: Save verify-registry state
        if: always()
        uses: actions/cache/save@v4
        with:
          path: ~/.local/state/tools-installer/verify-registry.json
          key: verify-registry-${{ github.run_id }}
```
Notes: the `code=$?` capture is needed because the default shell is `bash -e`. Git needs an identity before `git commit` (set `user.name`/`user.email` for `github-actions[bot]` inside the publishing step). `git add installer/registry.toml` and `git commit` are path-scoped so a stray `uv.lock` rewrite by `uv run` is never committed [ASSUMED that uv may touch `uv.lock`; path scoping makes it moot]. The drift workflow uses the same cache path and key shape [VERIFIED: verify-registry.yml:31-35,52-55].

### Bump flag unit tests (shape)
```python
def test_bumps_only_leaves_a_date_only_write_byte_identical(tmp_path):
    registry = _two_tool_write_fixture(tmp_path)   # tests/test_verify_registry.py:2542
    before = registry.read_bytes()
    code = vr.main(["--registry", str(registry), "--state", str(tmp_path / "s.json"),
                    "--write", "--bumps-only"], probe=probe, today=date(2026, 10, 15))
    assert registry.read_bytes() == before and code == 1
# the unflagged twin is test_write_dates_only_passing_tools (:2584): same probe, flag absent, text changes
```
The two-tool fixture's probe (`head` and `download` for `a-1.0.0`/`b-1.0.0`, `Release(tag="v1.0.0", digests={})`) is inline in `test_write_dates_only_passing_tools` (`:2584-2621`), not a shared helper: copy its few lines into a local helper in the new tests rather than refactoring the passing test.

### dependabot.yml
```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions:
        patterns:
          - "*"
```
[CITED: docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates for `groups`/`patterns`; the same page has no github-actions-specific example, so the combination is an unproven-here but plain application of the documented keys]. Test (D-15): `yaml.safe_load`, exactly one `updates` entry, `package-ecosystem == "github-actions"`, a `schedule` with `interval`, no `pip`/`uv`/`npm` ecosystems (SPEC R5).

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PAT for bot-opened PR checks | `GITHUB_TOKEN` + explicit `workflow_dispatch` (exempt from the no-recursion rule) | No stored secret, but see F10 |
| Required checks matched implicitly | Checks "evaluated only when the run is triggered by an eligible event" for rulesets | The reason BOT-02 needs a proof |

**Deprecated/outdated:** none relevant.

## The Proof (D-11), what it needs, and how to run it safely

### Constraints discovered
1. `registry-bot.yml` must be on `main` first (F4); `main` is 175 commits behind. So the dispatch-of-the-bot proof is **after landing**: owner fast-forwards the phase branch (the real flow), then the proof runs, then the cron follow-up commit.
2. The question that decides BOT-02 can be answered earlier and without a PR or the bot: dispatch the already-registered `ci.yml` on a proof branch and ask whether the resulting check runs let a fast-forward through. Use a throwaway protected target branch so `main` is never pushed.

### Option A (recommended, needs one owner-approved remote write set): throwaway protected target
Proves "dispatch-run checks satisfy required checks for a fast-forward" with the same contexts as `main`, never touching `main`.
1. Create `proof/target-<date>` at the current `origin/main` SHA (a branch push). Apply classic protection to that one branch only: `strict: true`, the two contexts, `enforce_admins: true`, no force pushes (`gh api -X PUT repos/castocolina/tools-installer/branches/proof/target-<date>/protection ...`). This is a repo-settings write: it needs explicit owner approval and a read-back.
2. Push `proof/candidate-<date>` = the target tip plus one commit that contains the `ci.yml` with `workflow_dispatch` (and, for the bot proof, a stale drawio pin). Do not let it run `push`-triggered CI the normal way if the question is "dispatch only": `ci.yml` triggers on every non-`main` push, so a push CI run also happens. To isolate the dispatch run, compare check-run `event` per run (`gh run list --branch ... --json event,conclusion,headSha`) and prove satisfaction on a SHA whose only successful runs are `workflow_dispatch`: push the candidate ref **with the workflow's `push` branch filter bypassed** (a commit message `[skip ci]` skips push/pull_request runs and still allows dispatch [CITED-from-memory, ASSUMED] (A9)), then dispatch.
3. `gh workflow run ci.yml --ref proof/candidate-<date>` (as the owner for the names test; as the bot's own token for the exemption test, which needs the bot workflow on `main`).
4. After both matrix jobs finish: `gh api repos/castocolina/tools-installer/commits/<sha>/check-runs --jq '.check_runs[] | {name, conclusion, app: .app.slug}'` and compare `name` byte-for-byte with `gh api .../branches/main/protection --jq '.required_status_checks.checks[].context'`.
5. Attempt the fast-forward: `git push origin proof/candidate-<date>:proof/target-<date>`. Accepted = dispatched checks satisfy required checks; "Required status check ... is expected" rejection = they do not, and the phase stops for the owner's token route (SPEC R2).
6. Clean up: `git push origin --delete proof/candidate-<date> proof/target-<date>`; `gh api -X DELETE repos/castocolina/tools-installer/branches/proof/target-<date>/protection` (deleting the branch also removes its protection; read back the protection list afterwards); cancel nothing else.

### Option B (as D-11 is written): real bot on a throwaway ref, after landing
Steps: (1) push `proof/registry-bot-<date>` from `main` with drawio-desktop stale; (2) `gh workflow run registry-bot.yml --ref proof/registry-bot-<date>`; (3) `gh run list --workflow ci.yml --branch bot/registry-<date> --json event,conclusion,headSha` expecting `event: workflow_dispatch`; (4) compare check-run names as above; (5) re-dispatch the bot the same day and confirm `gh api repos/castocolina/tools-installer/branches --paginate --jq '.[].name'` lists exactly one `bot/registry-<date>` and `gh issue list --label registry-bot --state open --json number` returns one issue with an edited body; (6) clean up. B alone proves the dispatch + names but, like any run that never pushes to `main`, does not prove the fast-forward is accepted; combine with Option A step 5 to prove acceptance without `main`.

### What the proof writes to the remote
| Write | Created by | Cleanup |
|-------|-----------|---------|
| `proof/registry-bot-<date>` (and, Option A, `proof/target-<date>`, `proof/candidate-<date>`) | owner-approved push | `git push origin --delete <ref>` |
| `bot/registry-<date>` | the bot | `git push origin --delete bot/registry-<date>` |
| Issue labelled `registry-bot` (and the label itself) | the bot | `gh issue close <n> --comment ...`; the label may stay (reused by the real bot) |
| `ci.yml` dispatched runs and their check runs | the bot | Runs stay in history; `gh run delete <id>` optional |
| Actions cache entries on the proof ref | `cache/save` | Expire by themselves; `gh cache delete` optional |
| Temporary branch protection (Option A only) | owner-approved `gh api PUT` | Deleted with the branch; read back |

### Safe stale pin (real data, read with `gh api repos/jgraph/drawio-desktop/releases?per_page=8`)
Pinned today: version `32.6.10` (`registry.toml:3469`, sha256 `d97a0740...977a35` arm64, `:3470`; `:3479` x64). Older real release for the throwaway: **v32.6.1**, published 2026-10-23T20:03:20Z:
- `draw.io-arm64-32.6.1.zip` digest `sha256:2f15c0a280e27d43426849de8e0437440fb02a15ae3a441bf124b4efe91c1c71`
- `draw.io-x64-32.6.1.zip` digest `sha256:e2792a35bd46996a85257d46f52f54b6a081981d7ab65cc5c8056fa6bce15d68`
Latest: v32.7.4 (2026-11-17T22:20:36Z), `draw.io-arm64-32.7.4.zip` `sha256:15930208cd3b2fb7775318557cc689197fec3115a8fff671001dff73f4bacab4`, `draw.io-x64-32.7.4.zip` `sha256:8e6f1490468fdc54e39bc65ab11f68ec1e7d2bf68c89ca31d1c98dd3f33366e7` [VERIFIED: live `gh api`, digests as the API returns them]. Because the real pin is already behind (32.6.10 vs 32.7.4), the bot will propose a 32.7.4 bump from the **real** registry too, so a stale pin is only needed to guarantee drift on a clean `main`; the throwaway can simply branch from `main` and rely on the real drift, which keeps the proof diff minimal. Use 32.6.1 only if the owner wants a diff whose old values are not the repo's current ones. Never invent a digest: use the values above, re-read at proof time (a newer drawio release changes the latest).

### Before the proof: the constraint on this branch
`registry-bot.yml` cannot be dispatched from this phase branch. Nothing in the phase may run, dispatch, push or create anything on the remote before the owner's checkpoint; all pre-checkpoint verification is local (unit tests, workflow tests, local actionlint).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gh` CLI (authenticated) | live reads, proof | yes | 2.101.0 | none needed |
| `uv` | tests, `make test` | yes | project-managed | none |
| Python (local) | tests | yes | 3.12.12 (`uv run python -V`) | CI differs, see below |
| `podman` | ad-hoc actionlint (D-16) | present; `scripts/detect-container-runtime.sh` printed `CONTAINER_TOOL=podman` rc 0 | - | see below |
| `actionlint` binary | D-16 | no (`command -v actionlint` empty) | - | container image or `uvx`/pip wheel `actionlint-py` [ASSUMED name; install needs a human-verify checkpoint] |
| `shellcheck` | `make shellcheck`; also run by actionlint on `run:` blocks | yes `/home/linuxbrew/.linuxbrew/bin/shellcheck` | - | - |
| network to `api.github.com` | verify-registry | yes | - | - |

**CI Python differs from local:** the setup-uv cache keys on `main` are `setup-uv-1-x86_64-unknown-linux-gnu-3.14.4-...` (ubuntu) and `setup-uv-1-aarch64-apple-darwin-3.15.2-...` (macOS) [VERIFIED: `gh api .../actions/caches`], local venv is 3.12.12, `requires-python = ">=3.11"` (`pyproject.toml:5`). The new code is plain `argparse` + set logic; the only stdlib differences that could touch the tests are argparse help rendering (3.14 added colored help on a TTY; CI is not a TTY and `test_help_lists_the_exit_codes` checks substrings only) and `date`/`tomllib` behavior that this change does not touch. Treat as low risk [ASSUMED for 3.14/3.15 argparse specifics]. Run the new tests locally only under 3.12; CI covers 3.14/3.15.

### actionlint recipe (D-16) and what I could and could not do
I attempted the container run and it was **blocked by the session's permission classifier** (a `podman run` pulling `docker.io/rhysd/actionlint`), so I have no observed actionlint output for the current workflows. Do not treat them as clean. The recipe for the executing agent, local files only, no remote contact:
```sh
# latest release at research time: v1.7.12 (2026-03-30) [VERIFIED: gh api repos/rhysd/actionlint/releases/latest]
eval "$(scripts/detect-container-runtime.sh)"
$CONTAINER_TOOL run --rm -v "$PWD/.github:/repo/.github:ro,z" -w /repo docker.io/rhysd/actionlint:1.7.12 -color=false
# afterwards remove only what this run pulled, by exact name:
$CONTAINER_TOOL rmi docker.io/rhysd/actionlint:1.7.12   # only if it was absent before (check `image exists` first)
```
The image bundles shellcheck, so `run:` scripts get SC-level findings (for example unquoted `$BRANCH`). Run it before and after the workflow edits and record both outputs in VERIFICATION. The image tag `rhysd/actionlint:1.7.12` as the official image name is [ASSUMED] from training knowledge (A10); confirm on first pull.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project default; `pytest -n auto`, coverage floor in `pyproject.toml`), PyYAML for workflow parsing |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_ci_workflow.py tests/test_verify_registry_workflow.py tests/test_registry_bot_workflow.py tests/test_verify_registry.py --no-cov -q` |
| Full suite command | `make test` once after the plan; `make validate` once after the plan (AGENTS.md) |

Baseline: the two existing workflow test files pass today (`20 passed`, run this session with `--no-cov`).

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOT-04 | `--write --bumps-only` leaves a date-only registry byte-identical; same fixture without the flag changes it | unit | `uv run pytest tests/test_verify_registry.py -k bumps_only --no-cov -q` | Wave 0 (new tests; fixtures exist at `:2542`, `:2896`) |
| BOT-04 | A real bump with the flag changes `version`, `sha256`, `verified` together (`_github_pin_registry`, candidate passes) | unit | same | Wave 0 |
| BOT-04 | No-drift registry unchanged with and without the flag; `--bumps-only` without `--write` exits 64 and does no network work | unit | same | Wave 0 |
| BOT-04 | A passing non-bumped tool is not dated and no `dated <tool>` line is printed for it | unit | same | Wave 0 |
| BOT-01 | triggers exactly `{"schedule","workflow_dispatch"}` (first commit: `workflow_dispatch` only per D-12, so assert the final target set only in the follow-up commit), off-minute cron | workflow | `uv run pytest tests/test_registry_bot_workflow.py --no-cov -q` | Wave 0 |
| BOT-01 | guard step id with `if:` on every publishing step; cache save has `always()`; `--bumps-only` present; no `--issue`; no `${{` in any `run` | workflow | same | Wave 0 |
| BOT-01 | concurrency group `registry-bot`, `cancel-in-progress: false`; D-05 deletion step limited to the `refs/heads/bot/registry-` namespace | workflow | same | Wave 0 |
| BOT-02 | `ci.yml` has `workflow_dispatch`; bot dispatch step is `gh workflow run ci.yml --ref "$BRANCH"` with the branch from `env:`; `test_ci_workflow` updated for `:41` and `:52` | workflow | `uv run pytest tests/test_ci_workflow.py tests/test_registry_bot_workflow.py --no-cov -q` | amend + Wave 0 |
| BOT-02 | Dispatched checks satisfy required checks | live proof (owner checkpoint) | recorded in VERIFICATION, not a test | n/a |
| BOT-03 | permissions exactly `{"contents":"write","actions":"write","issues":"write"}`; no `run` targets `main`, `HEAD:main`, `refs/heads/main`; no `gh pr`/merge; `verify-registry.yml` still `contents: read` | workflow | same file + `tests/test_verify_registry_workflow.py` | Wave 0 / exists |
| R5 | dependabot parse: one `github-actions` entry, a schedule, no other ecosystem | unit | same new file | Wave 0 |

### Sampling Rate
- **Per task commit:** the targeted files above (no full suite; the hook runs the six static gates).
- **Per wave merge:** same plus `tests/test_docs_only.py` (a `.github/*` edit is read-test territory, D-18).
- **Phase gate:** `make validate` then `make test` once, green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_registry_bot_workflow.py` with its own `_load(path)` / `_triggers(data)` (see Reconciliation)
- [ ] `--bumps-only` tests appended to `tests/test_verify_registry.py`
- [ ] `tests/test_ci_workflow.py` `:41` and `:52` amendments
- [ ] No-main assertion should scan `run` texts with a regex covering `HEAD:main`, `refs/heads/main`, `origin main`, `:main\b`, and `gh pr`, and must not false-positive on `bot/registry-` or the word "domain"
- Framework install: none.

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (no new credential) | default `GITHUB_TOKEN` only |
| V3 Session Management | no | - |
| V4 Access Control | yes | exact least-privilege `permissions:` (F3, D-07); no push restrictions exist on `main`, so the guard is workflow content + the no-main test |
| V5 Input Validation | yes | branch/ref and issue values pass through `env:`; never an expression inside `run`; quote all shell variables |
| V6 Cryptography | yes (integrity) | the digest is the API/`sha256` verified by `verify-registry` before any write; do not recompute or accept an unverified candidate |
| V14 Configuration | yes | pin actions by major tag as today; Dependabot keeps them current |

### Known Threat Patterns for GitHub Actions bot workflows
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Script injection through ref/branch names in `run` | Tampering | `env:` indirection; test asserts no `${{` in `run` |
| Token with push rights could fast-forward `main` (protection has `restrictions: null`) | Elevation | No step targets `main` (tested); `contents: write` only for the bot branch |
| `workflow_dispatch` by anyone with write access runs the bot on any ref | Spoofing / Tampering | Documented (Pitfall 6); bot can only push `bot/registry-*` and only `registry.toml` is committed |
| Force-push clobbering someone else's branch | Tampering | `--force-with-lease` with an explicit ref after a single-ref fetch (Pattern 3) |
| D-05 deletion sweeping other refs | Tampering/DoS | Namespace filter `refs/heads/bot/registry-*`, exclude the current branch, test asserts the pattern |
| Token or secrets in logs / issue body | Information disclosure | Default token is masked; no `--issue` from verify-registry; issue body holds only the branch name and diff summary |
| Poisoned upstream asset | Tampering | Existing digest verification before write; the bot never writes an unverified `sha256` (`_build_bump_edits` raises on a missing hash: `installer/verify_registry.py` "missing candidate hash for {tool.id}") |

## Live registry facts today

`uv run --isolated --no-dev python -m installer.verify_registry --state <scratch>` (read-only, scratch state file outside the repo and home, run on this host 2026-11-21, exit 1):
- **Drift:** only `drawio-desktop`: both macOS zip pins `... — newer stable release v32.7.4 (pinned 32.6.10)`. Nothing else drifts.
- **Pinned `version` methods:** drawio-desktop 2 (macOS zips, bumpable), ghostty 2 (`pkgforge-dev/ghostty-appimage`, `v{ver}` tags, debian/fedora amd64+arm64, bumpable), bruno 2 (`usebruno/bruno`, Linux AppImages, bumpable), sublime 3 (`no release source`, three note lines; manual `--candidate` only).
- **Ghostty and Bruno pass**, and their pins equal the upstream GitHub digests: Ghostty `50ad4f8b...2ae6` x86_64 and `932e21c6...f506` aarch64, Bruno `3c386b10...80bb` x86_64 and `6048c3ae...3469` arm64 equal `gh api repos/<repo>/releases/latest` digests (`50ad4f8b54a0`, `932e21c671c2`, `3c386b1007f6`, `6048c3aeb766` prefixes) [VERIFIED: live calls and registry.toml:3229-3241, 3604-3614]. Their latest releases are already the pinned ones (Ghostty v1.4.0 published 2026-10-28, Bruno v4.3.0 published 2026-10-22), so digest verification works for the new pins and the bot has nothing to bump for them today.
- Not checkable: alacritty, zip, zsh, plus `playwright-mcp` (uses a bun `versions` pin, outside the `version`+`sha256` mechanism). Unverified at install: gron, jetbrains-toolbox, jless, vscode (existing, unrelated).
- The draw.io bump candidate is checkable: the 32.7.4 zips exist with API digests (listed above), so the first real bot run will write `version = "32.7.4"` plus those two sha256 values and today's `verified` for drawio-desktop only (with `--bumps-only`, no other tool is re-dated).
- A cold run took far longer than the drift workflow's 25 min step budget on this host (Pitfall 4); the runner is faster and its cache is warm.
- Real GitHub state: the last drift run on `main` was 2026-11-19 (a Thursday, 13 s) and succeeded; issue #5 `registry-drift` is closed. draw.io 32.7.4 was published 2026-11-17T22:20Z, after the Monday 11-16 run. The 11-19 run is the Thursday cron, whose check step is skipped by its `if` (`github.event_name == 'workflow_dispatch' || github.event.schedule == '17 5 * * 1'`) [VERIFIED: verify-registry.yml `if:` text; weekday via `date -d 2026-11-19 +%A` = Thursday]. So the next Monday run (2026-11-23) is the first drift run that can report the draw.io drift, and the bot's first real run proposes the same bump.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Whether check runs of a `workflow_dispatch` run satisfy `main`'s classic required status checks for a fast-forward push is unknown; docs only say they do not satisfy a branch **ruleset** (on a PR head) | GitHub Actions Facts F10, The Proof | BOT-02 fails; phase stops, owner chooses token route or the owner re-push fallback (A3) |
| A2 | `GITHUB_TOKEN` with `actions: write` can call the workflow-dispatch endpoint (docs quote only the PAT `repo` scope for the REST page) | F2 | Dispatch step 403s at first real run; proof catches it |
| A3 | An owner `git push` of the same SHA to a second branch name starts normal push-event CI whose check runs satisfy protection, a zero-token fallback if A1 is false | Alternatives | Fallback unavailable; token route is the only one |
| A4 | A branch whose `ci.yml` has `workflow_dispatch` can be dispatched via `--ref` while the default-branch copy lacks it (CLI help supports ref-version semantics; the "has run at least once" doc sentence is ambiguous) | F5, The Proof Option A | Option A cannot run before landing the `ci.yml` change on `main` |
| A5 | A fast-forward `git push origin <branch>:main` of a commit whose message has `Closes #N` closes issue N | F8, D-08 | Owner closes the issue by hand; cannot be proved without pushing `main`, so the proof must not claim it |
| A6 | Cache scope: a run on a non-default ref restores the default branch's caches; its own saves are invisible to `main` | F13 | Proof runs start with a cold state (slow, still correct) |
| A7 | A Dependabot branch can be landed by fast-forward and its PR then closes; CI runs on the Dependabot branch via the `push` trigger | F15 | Owner closes stale Dependabot PRs by hand |
| A8 | GitHub's `workflows`-permission check inspects only the pushed new commits, not the whole range | Pitfall 7 | The proof push is refused; record and ask the owner |
| A9 | `[skip ci]` in a commit message suppresses push-triggered runs but not dispatch | The Proof Option A step 2 | The isolation of dispatch-only check runs needs another way, for example compare `event` fields instead of suppressing push runs |
| A10 | `docker.io/rhysd/actionlint:1.7.12` is the official image; actionlint-py wheel name | actionlint recipe, Environment | Pull fails; use the release binary from the rhysd/actionlint GitHub release |
| A11 | `uv run` may rewrite `uv.lock` in the bot job | Code Examples notes | Moot: the commit is path-scoped to `installer/registry.toml` |
| A12 | argparse/stdlib differences in Python 3.14/3.15 do not affect the new tests | Environment | A CI-only failure; targeted tests under 3.15 would be needed |

## Open Questions (RESOLVED)

Each question carries an explicit disposition (orchestrator decisions of 2026-11-21, `33-REVIEWS.md` and the plans). Only Q1 stays unanswered by design: it is an owner-gated item that the proof runbook answers after landing, and the phase verification lists it as `human_needed`.

1. **Does a dispatched CI run satisfy `main`'s required checks for a fast-forward? (BOT-02)**
   - Known: docs say dispatch checks do not satisfy a branch ruleset on a PR head; `main` has classic protection, no ruleset, no PR flow.
   - Unclear: classic protection behavior.
   - Recommendation: prove with Option A (throwaway protected target) plus Option B; decide the token route or the re-push fallback (A3) only if it fails. Owner decision needed on whether Option A's temporary branch protection write is acceptable (it changes a repo setting on a throwaway branch only). DISPOSITION: deferred to the owner's proof (runbook `docs/registry-bot-proof.txt`, plan 33-04); not resolved by research, listed in VERIFICATION as `human_needed`.
2. **When can the proof run, given the files must be on `main` first?**
   - Known: `main` is 175 commits behind and has no phase-33 files; F4.
   - Recommendation: the proof is the phase's last, owner-gated step after the owner lands the branch; plan the VERIFICATION entry as "pending owner checkpoint" until then. Also decide whether the phase can be closed before it (SPEC says no: "proved once ... before the phase is done"). RESOLVED provisionally by orchestrator decision 1: the phase's code is complete and tested without the proof, the proof is the owner's after-landing checkpoint and the verification is `human_needed`; needs confirmation.
3. **Closing keyword vs fast-forward** (D-08) cannot be proved without pushing `main`; recommend keeping the keyword with the owner-closes fallback, and note in VERIFICATION that it was not exercised. Optionally the bot could close a stale `registry-bot` issue on a later no-drift run; that is a publishing-class action and would need a D-03 amendment. RESOLVED by orchestrator decision 8: keep the keyword with the owner-closes fallback; VERIFICATION states it was not exercised; the optional stale-issue close is not done.
4. **Same-day rerun quietness (Pitfall 5)**: keep simple (force-update, CI re-dispatch) or add fixed commit dates plus skip-if-identical. Claude's discretion; recommend simple.
5. **Dependabot gap:** the Dependabot PR flow conflicts with "never a pull request"; D-17 accepts it for action bumps only. Confirm the owner is fine with Dependabot-opened PRs that are landed by fast-forward of their branch. RESOLVED provisionally by orchestrator decision 7 (needs confirmation, low stakes).
6. **actionlint run:** blocked here by the permission classifier; the executing agent needs a disposable-container run (or the owner's go-ahead) to record real output. RESOLVED by orchestrator decision 6: an orchestrator-run step at the phase gate, recorded in VERIFICATION ("not run" with the reason if it cannot run, never a pass).
7. **(RESOLVED)** Does `workflow_dispatch` need the workflow file on the default branch? Yes (F4, two doc quotes); D-12's rollout is correct and the proof must follow landing.
8. **(RESOLVED)** Do the existing line citations still hold? Yes except the items listed in CONTEXT Reconciliation (helper names, `:38`, pinned-method counts, schedule timing).

## Sources

### Primary (HIGH confidence)
- Repo files read this session: `installer/verify_registry.py` (1-20, 55-75, 105-160, 900-960, 1070-1345, 1419-1460, 1495-1645), `tests/test_ci_workflow.py`, `tests/test_verify_registry_workflow.py`, `tests/test_verify_registry.py` (2535-2660, 2890-2955, 3020-3090, 3440-3600), `.github/workflows/ci.yml`, `.github/workflows/verify-registry.yml`, `Makefile`, `.claude/git-workflow.md`, `.claude/testing.md`, `devtools/docs_only.py`, `tests/test_docs_only.py`, `installer/registry.toml` (pins), `.planning/phases/33-registry-update-bot/33-CONTEXT.md`, `33-SPEC.md`.
- Live read-only `gh api` calls (2026-11-21): branch protection, rulesets, repo settings, workflow permissions, workflows list, caches, drawio-desktop, Ghostty and Bruno releases, actionlint latest release, `gh run list`.
- Local experiments in a scratch bare repository (git 2.56.0), removed afterwards.
- A real `verify-registry` run (scratch state, removed afterwards).

### Secondary (MEDIUM confidence, GitHub Docs, fetched 2026-11-21)
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/actions/using-jobs/using-concurrency
- https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
- https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue
- https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/optimizing-pr-creation-version-updates
- https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
- https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuring-dependabot-version-updates

### Tertiary (LOW confidence)
- Training knowledge flagged `[ASSUMED]` in the Assumptions Log (A1-A12).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, nothing new is installed
- Code change (BOT-04): HIGH, the exact lines were read and match CONTEXT
- Actions semantics (F1, F4-F7): HIGH, GitHub Docs
- BOT-02 satisfaction (F10): LOW, genuinely unknown until the proof
- Pitfalls: MEDIUM, git behavior verified locally, GitHub-side behavior documented or assumed

**Research date:** 2026-11-21
**Valid until:** 2026-12-21 (Actions semantics are stable; the drawio facts change with each upstream release)
