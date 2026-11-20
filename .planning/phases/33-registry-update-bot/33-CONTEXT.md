# Phase 33: Registry update bot - Context

**Gathered:** 2026-11-19 (assumptions mode, after 33-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

A scheduled or dispatched GitHub Actions workflow runs `verify-registry --write` with a new date-only flag, pushes a dated `bot/registry-<date>` branch only when `installer/registry.toml` changed, announces it in one tracking issue and dispatches CI on that branch; the owner lands it through the protected flow. Plus a minimal `dependabot.yml` for GitHub Actions and one recorded proof that a dispatched run satisfies the required checks.
</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `33-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `33-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):** the bot workflow, the `ci.yml` dispatch trigger, the date-only flag with its tests, the tracking-issue step, `.github/dependabot.yml`, and one throwaway-branch proof. *Amended 2026-11-19 (33 D-10):* also the two assertions of `tests/test_ci_workflow.py` that conflict (lines 41 and 52).
**Out of scope (from SPEC.md):** auto-landing; a real pull request; bumping pins without a `version`; changing what `verify-registry` verifies; Renovate; phases 34-35.

</spec_lock>

<decisions>
## Implementation Decisions

### Workflow
- **D-01: `.github/workflows/registry-bot.yml`, triggers `schedule` and `workflow_dispatch` only.** Weekly on Monday after the drift run, an off-minute cron such as `37 6 * * 1`, so it restores the cache the 05:17 drift run saved (`.github/workflows/verify-registry.yml`; `tests/test_verify_registry_workflow.py:31-33` rejects minute-0 crons). jev monday_after_check 0.84 (TypeSafe). It first lands with `workflow_dispatch` only; the cron is enabled in a follow-up commit after the proof (D-12).
- **D-02: The bot runs `uv run --isolated --no-dev python -m installer.verify_registry --write --bumps-only` directly, not through `make`.** Exit 0, 1 and 2 continue to the guard (exit 1 is normal when another tool drifts, as `test_write_dates_only_passing_tools` shows); exits 64, 70 and 73 fail the job. It never passes `--issue` (that would overwrite the `registry-drift` issue body). `Makefile:27-28` is a thin wrapper and GNU make would turn every failure into exit 2.
- **D-03: A guard step with an id runs `git diff --quiet -- installer/registry.toml` and sets an output; every publishing step (commit and push, issue upsert, CI dispatch) has an `if:` on it.** One job. SPEC R1's "no step runs when the diff is empty" is read as "no publishing step"; the cache save may still run `always()` (SPEC R1 acceptance amended).
- **D-04: The branch is `bot/registry-$(date -u +%F)` committed on the run ref's HEAD.** The bot fetches that one ref first, then pushes `HEAD:refs/heads/bot/registry-<date>` with `--force-with-lease` to that ref only. The branch name reaches `run:` through `env:`, never through an expression inside `run` (`tests/test_ci_workflow.py:84-86`). jev fetch_then_lease 0.97 (TypeSafe).
- **D-05: After a successful push the bot deletes older `bot/registry-*` refs** (the namespace it owns), so one live branch exists and the owner cannot land a stale one; the deletion has its own workflow test. **Own reasoning** (jev bot_deletes_older low 0.36; TypeSafe leave_for_owner low 0.54): unlanded bumps reappear weekly under a new date from the same main. Ledger.
- **D-06: `concurrency: { group: registry-bot, cancel-in-progress: false }`** (queue): cancelling mid-run could leave a pushed branch without CI or issue update. jev first rung cancel 0.98 contradicted the evidence; second opinion queue low 0.53. **jev overridden / Own reasoning**, ledger.
- **D-07: Permissions exactly `contents: write`, `actions: write`, `issues: write`**, `GH_TOKEN: ${{ github.token }}`; `verify-registry.yml` keeps `contents: read, issues: write` (`tests/test_verify_registry_workflow.py:37`). The repo default is `read`; the dispatch needs `actions: write`.
- **D-08: The tracking issue uses a new label `registry-bot`** with an inline `gh` upsert (label create `--force`, list open, edit or create), not `registry-drift` (the drift workflow overwrites that body and closes it after clean runs). The bot commit carries a closing keyword for the issue (issue upsert first, then commit and push), so the owner's fast-forward closes it; this is verified at the proof, and the fallback is the owner closing it. jev new_label_inline 0.87 (TypeSafe); closing keyword: **Own reasoning** (low 0.38; TypeSafe owner_closes low 0.52). Ledger.
- **D-09: The bot shares the drift workflow's state cache** (path `~/.local/state/tools-installer/verify-registry.json`, restore-keys `verify-registry-`, save with `always()` and a key containing `github.run_id`). jev first rung no_cache 0.81 contradicted the evidence; second opinion share_cache 0.94. **jev overridden.**

### CI dispatch and the proof
- **D-10: `ci.yml` gains a bare `workflow_dispatch:` with no inputs;** push filter, concurrency group, job id, job name (`validate & test on ${{ matrix.os }}`) and steps stay. The bot runs `gh workflow run ci.yml --ref "$BRANCH"` (branch from `env:`) only when the guard says the registry changed. `tests/test_ci_workflow.py:41` (`set(triggers) == {"push"}`) becomes `{"push", "workflow_dispatch"}` and `:52` (`uses == "actions/checkout@v4"`) is matched by prefix, or the first Dependabot checkout bump turns CI red.
- **D-11: The proof runs the real bot on a throwaway ref** at an owner-approved checkpoint (it writes to the remote): push `proof/registry-bot-<date>` with a deliberately stale drawio-desktop pin (an older real version plus its real sha256); dispatch `registry-bot.yml --ref` that branch; watch `gh run list --workflow ci.yml --branch bot/registry-<date> --json event,conclusion` (expect `workflow_dispatch`); read `gh api repos/{o}/{r}/commits/<head>/check-runs` and compare the names exactly with the protection contexts; dispatch again the same day to prove update-not-create and a single issue; delete the throwaway and bot branches and close the proof issue; record everything in VERIFICATION. On failure it stops and asks the owner about the token route. Only the bot's own token proves the dispatch exemption; an owner-run dispatch proves only the names. jev first rung none_of_these 0.91 contradicted the evidence; second opinion real_bot_on_throwaway low 0.50. **jev overridden / Own reasoning**, ledger.
- **D-12: Rollout:** land the workflows with `workflow_dispatch` only, run the proof, then enable the cron in a follow-up commit. GitHub needs a workflow file on the default branch to dispatch it (to be confirmed in planning), and the cron makes the bot publish for real once landed. **Own reasoning** (jev all_at_once low 0.60). Ledger.

### Flag, tests, lint, dependabot
- **D-13: The flag is `--bumps-only` and requires `--write`** (exit 64 with a usage message otherwise, like `--candidate requires --write` at `installer/verify_registry.py:1581`). The filter lives in `_registry_edits_for_write` (`:1330-1339`): bump edits are kept and `verified` is kept only for tools with an applied bump; a lone `verified` change is dropped; the stderr `dated <tool>` loop prints only tools actually dated. **Own reasoning** (jev bumps_only low 0.66). Ledger.
- **D-14: The unit tests reuse the existing fixtures:** `_two_tool_write_fixture` from `test_write_dates_only_passing_tools` (date-only: byte-identical with the flag, changed without it), `_github_pin_registry` from `test_newer_github_pin_is_bumped_when_the_candidate_passes` (real bump keeps all three keys), a no-drift registry unchanged either way, and `--bumps-only` without `--write` exits 64; fixed `today`, fake `Probe`, `tmp_path` state.
- **D-15: A new `tests/test_registry_bot_workflow.py`** (reusing `_load`/`_triggers` from `tests/test_verify_registry_workflow.py:13-23`) asserts triggers and off-minute crons, the exact permissions, the concurrency group, the guard step id with `if:` on every publishing step, no `run` that targets `main`, `HEAD:main` or `refs/heads/main` (and no `gh pr`/merge), the dispatch step text, no `${{` inside any `run`, no `--issue`, and `--bumps-only` present; the dependabot assertions live in the same file. jev first rung none_of_these 0.71 contradicted the evidence; second opinion new_file 0.83. **jev overridden.**
- **D-16: No new lint gate in this phase.** The workflow tests are the gate, plus one ad-hoc `actionlint` run in a disposable container recorded in VERIFICATION. A permanent gate (its own hook entry and make target) is deferred to Backlog 999.23. **Own reasoning** (jev first rung none_of_these 0.93 contradicted the evidence; second opinion new_gate low 0.68): a permanent gate is scope growth with a dev-setup install. Ledger.
- **D-17: `.github/dependabot.yml`:** `version: 2`, one `github-actions` entry, `directory: "/"`, weekly, one group matching `"*"` so all action bumps arrive as one branch (the workflows use four action families). **Own reasoning** (jev one_weekly_group low 0.35; TypeSafe separate_weekly low 0.75). Ledger.
- **D-18: No change** to `devtools/docs_only.py` `TEST_READ` or `tests/test_docs_only.py` `LEDGER` (`.github/*` is already read-test territory; the new tests cite no Markdown literal).

### Claude's Discretion
- Issue title and body text, the commit message wording, and the cron minute within the Monday window.

### Folded Todos
- `.planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md` (the phase's own source todo).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/phases/33-registry-update-bot/33-SPEC.md` — Locked requirements — MUST read before planning
- `.planning/research/2026-11-17-update-automation.md` (feature 3), `.planning/todos/pending/2026-11-17-registry-update-bot-in-github-actions.md`
- `.github/workflows/ci.yml`, `.github/workflows/verify-registry.yml`, `installer/verify_registry.py`
- `tests/test_ci_workflow.py`, `tests/test_verify_registry_workflow.py`, `tests/test_verify_registry.py`
- `.claude/git-workflow.md` (the landing flow)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Drift workflow's state cache steps, its `registry-drift` upsert pattern, the `_load`/`_triggers` workflow-test helpers, the write and bump fixtures in `tests/test_verify_registry.py`.

### Established Patterns
- House rule: no `run` step interpolates an expression; crons never start at minute 0; one test file per workflow.

### Integration Points
- `installer/verify_registry.py` `_registry_edits_for_write` (:1330) and the argparse block (:1551-1565); `ci.yml` triggers; branch protection requires `validate & test on ubuntu-latest` and `macos-latest` (read live 2026-11-19: `strict`, `enforce_admins`, no push restrictions, no required reviews).
</code_context>

<specifics>
## Specific Ideas

Live facts that changed the SPEC (amended in the same commit): branch protection has no push restrictions, so a token with `contents: write` could fast-forward a green commit to `main`; the only guard is the workflow content and its test (the R3 edge row said protection was the guard, corrected). The bot can auto-bump only drawio-desktop (2 of the 5 pinned methods): Sublime publishes no latest URL and is bumped by hand with `--candidate`; phases 30 and 32 add GitHub-sourced pins the bot can bump.
</specifics>

<deferred>
## Deferred Ideas

- A permanent workflow-lint gate (actionlint): Backlog 999.23.
- To confirm in planning: whether `workflow_dispatch` needs the workflow on the default branch (assumed yes, D-12); whether a closing keyword in a fast-forward push to the default branch closes the issue (checked at the proof); Dependabot `groups` with `"*"` without a PR merge flow.

### Reviewed Todos (not folded)
None other matched.
</deferred>
