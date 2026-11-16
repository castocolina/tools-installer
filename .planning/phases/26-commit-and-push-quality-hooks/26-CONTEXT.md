# Phase 26: Commit and push quality hooks - Context

**Gathered:** 2026-11-16 (interactive, standard discuss mode `--analyze --all --batch`, after 26-SPEC.md)
**Status:** Ready for planning

<domain>
## Phase Boundary

Commits and pushes run the project's quality gates, each as its own named gate with its own `make` target. The push
gate tests a tree equal to the pushed commit, `make dev-setup` installs the hooks, and GitHub accepts a commit on `main`
only after CI has passed on that exact commit. The phase also renames the dev bootstrap (`make install` →
`make dev-setup`), removes `make setup` (the wizard is `make run`), and fixes the one known flaky test, since the new
push gate would otherwise block on it.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**6 requirements are locked.** See `26-SPEC.md` for the full requirements, boundaries and acceptance criteria. R1, R2
and R4 carry dated 2026-11-16 amendments from this discussion (D-03 to D-07).

Downstream agents MUST read `26-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md, with the 2026-11-16 additions):**
- The commit-stage and pre-push hooks, plus `default_install_hook_types`.
- The push-gate tree check from R3.
- The hook step of the dev bootstrap target.
- The tests that pin the hooks, the Makefile recipes and the gate wiring.
- The `main` branch-protection change: `enforce_admins` on, both contexts required.
- Any `ci.yml` trigger change the branch → CI → `main` flow needs.
- Docs: AGENTS.md, `.claude/dev-environment.md`, `.claude/git-workflow.md`.
- A pending todo for the tools outside this repo that push straight to `main`.
- *(added 2026-11-16, D-03/D-07/D-08/D-12)* Per-gate `make` targets; `make install` → `make dev-setup`; `make setup`
  removed in favour of `make run`; the flaky screen-family test fixed.

**Out of scope (from SPEC.md, with the 2026-11-16 additions):**
- Updating the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow (todo).
- A fast test subset or test markers for the push stage.
- Speeding up the suite, or changing the CI matrix or timeouts.
- pylint.
- Remote pre-commit repos and `pre-commit autoupdate`.
- An automatic bypass of the `main` gate.
- *(added 2026-11-16, D-13)* A duplicate-code gate. It is Backlog 999.17.

</spec_lock>

<decisions>
## Implementation Decisions

### Push gate mechanism
- **D-01: The push gate is our own Python module, installed as git's `pre-push` hook.** It reads every pushed ref
  from stdin; pre-commit's own pre-push entry sees only the first ref with something to push
  (`pre_commit/commands/hook_impl.py:119-174`, pre-commit 4.6.0).
  - It applies the R3 refusals before any check, in this order:
    1. staged changes that are not committed;
    2. untracked `.py` files under `installer/` or `tests/` (recursive, ignored files excluded);
    3. any pushed commit that is not HEAD.
  - A deletion-only push goes through with no checks.
  - Each refusal lists the offending files or refs, sorted.
  - It then runs `pre-commit run --hook-stage pre-push --from-ref <remote sha> --to-ref <local sha>`.
    pre-commit sets the unstaged edits aside and restores them after a pass, a failure or an interrupt
    (`staged_files_only`, `run.py:344-421`), which is must-NOT P2.
  - For a push whose remote has none of the history (a root push), there is no remote sha. pre-commit then uses
    `all_files` and stashes nothing (`hook_impl.py:150-159`). The gate must still get edits set aside: it passes refs
    that keep pre-commit's stash on, or it refuses a dirty tree in that case. The planner researches which; the
    acceptance in SPEC R3 is fixed either way.
  - **Reversibility:** costly. The hook install path and the tests that drive a scratch repo depend on this shape.
- **D-02: The gate module is dev tooling, not product code.** It lives outside `installer/`, so it never ships in the
  wheel. Its directory joins every gate: ruff (the lint and format-check targets), pyright `include`, coverage
  `source` and vulture `paths`, so it is held to the same bar as `installer/`. The exact path is Claude's discretion.

### One gate, one target, one hook entry
- **D-03: Every gate is a `make` target, and every pre-commit hook entry calls its target.** The command for each
  gate is written once, in the Makefile recipe. The targets are `make lint` (ruff check), `make format-check`
  (ruff format --check), `make typecheck` (pyright), `make security` (bandit, same skips), `make dead-code`
  (vulture), `make shellcheck` (same file list) and `make test` (kept, owner 2026-11-16). Each hook is
  `entry: make <target>`, `pass_filenames: false`, `always_run: true`, `language: system`. *(SPEC R1 amended.)*
  - **Reversibility:** costly. AGENTS.md, dev-environment.md, CI and agent habits name these targets.
- **D-04: `make validate` runs `pre-commit run --all-files` and does not list the gates itself** (owner: "validate
  should call them all without knowing what they are"). Adding a gate means one Makefile target plus one hook entry,
  and `make validate` picks it up. CI keeps calling `make validate`, then `make test`. The R1 parity test becomes a
  wiring test: every commit-stage hook entry is `make <target>` for an existing Makefile target; every gate target
  except `test` has a commit-stage hook; `make validate` is exactly `pre-commit run --all-files`; no commit-stage hook
  runs `make test`. *(SPEC R1 amended.)*
- **D-05: The push stage runs each static gate and then the test gate, each as its own hook entry.** The static
  hooks carry `stages: [pre-commit, pre-push]`, and the `make test` hook carries `stages: [pre-push]` and comes last in
  the file. A failure names the gate that failed, instead of one opaque `make validate` entry (owner: "each gate its
  own entry, so a failure is clear"). This is equivalent to SPEC R2's `make validate` then `make test`.
  *(SPEC R2 amended.)* Whether the push stops at the first failing gate is Claude's discretion. Skipping the 60 s
  suite after a lint failure is the likely choice (`fail_fast`).
- **D-06: Re-run only the gate that failed.** When a gate fails during a commit or a push, the agent or developer
  fixes the problem and re-runs that gate's target (`make typecheck`, and so on). `make validate` is for verifying
  a whole plan or phase. AGENTS.md and `.claude/dev-environment.md` carry a gate → target → stage table, and say this
  in one line.

### Target names
- **D-07: `make install` is renamed `make dev-setup`, with no alias** (owner 2026-11-16).
  - It runs `uv sync`, then `pre-commit install --hook-type pre-commit` for the commit hook, then installs the D-01
    gate as `pre-push` in the shared hooks directory (`git rev-parse --git-common-dir`/hooks, so worktrees share it).
  - `.pre-commit-config.yaml` sets `default_install_hook_types: [pre-commit]`. pre-commit does not own the pre-push
    hook.
  - Outside a git checkout it skips the hook step with a message and exits 0. With `core.hooksPath` set it fails and
    names it.
  - `ci.yml`, README.md and AGENTS.md switch to `make dev-setup`. *(SPEC R4 amended.)*
  - **Reversibility:** costly. CI and the docs call the target by name.
- **D-08: `make setup` is removed. `make run` is the wizard target** (owner: "what you call make setup is really make
  run"). Every place that names `make setup` is updated, as found with `rg -l 'make setup\b' --glob '!.planning/**'`
  on 2026-11-16:
  - product messages: `installer/guidance.py`, `installer/compose.py`, `setup.py`;
  - tests: `tests/test_setup.py`, `tests/test_guidance.py`, `tests/test_app.py`, `tests/test_wizard_app.py`,
    `tests/test_schedules_handover.py`, `tests/test_tool_browser.py`, `tests/test_catalog_audit_skill.py`,
    `tests/e2e_landing_driver.py`;
  - docs: README.md, AGENTS.md (including the "never run `make setup`" host rule, which now names `make run`).
  - The dated `docs/superpowers/` plans and `.planning/` history are records and stay as they are.
  - **Reversibility:** costly. Users see the hint text and tests pin it.

### Path to main
- **D-09: Branch push, then CI, then fast-forward `main`** (owner 2026-11-16).
  - `ci.yml` runs on a push to any branch except `main`.
  - The `main` push trigger is dropped: the SHA that reaches `main` was already tested.
  - The `pull_request` trigger is dropped too: on a solo repo it would run the same SHA twice. Keeping it for outside
    PRs is Claude's discretion.
  - After both checks are green, the change lands with `git push origin <branch>:main`. Required status checks use
    strict mode, so a branch that is no longer a fast-forward of `main` must be updated and re-tested.
  - **Reversibility:** costly. Every later push flow, including the GSD helpers in the todo, follows it.
- **D-10: `enforce_admins` is applied last.** It goes on after the phase's own last direct push to `main`, then is
  read back with `gh api`. The phase's final change then lands through the D-09 flow, which proves it (SPEC R5
  acceptance). `.claude/git-workflow.md` documents the off command, the on command and the read-back
  (must-NOT P6).
- **D-11: The docs-only fast pass lives inside the same `ci.yml` job**, so the required check names stay
  `validate & test on ubuntu-latest` / `…macos-latest`.
  - An early step lists the changed paths against the merge base with `origin/main` (NUL-separated; a rename counts
    both paths). The validate and test steps are skipped when every path is under `.planning/` or is a Markdown
    file no test reads.
  - The list of Markdown files tests read is derived and pinned by a pytest test. Today that list includes
    `.claude/architecture.md` and `.claude/skills/*/SKILL.md`, via `tests/test_postinstall.py:608`. The mechanics are
    Claude's discretion; must-NOT P4 holds.

### Claude's Discretion
- The gate module's path and CLI shape (D-02), and the exact `pre-commit run` ref arguments in the root-push case
  (D-01, researched).
- Whether the push stage uses `fail_fast` (D-05).
- The wording of refusal and failure messages. Each one names the `make` target to re-run (D-06).
- The CI docs-only step's implementation and keeping or dropping `pull_request` (D-09, D-11).
- The `make help` descriptions of the new targets.

### Folded Todos
- **D-12: `2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test`** (todo match score 0.9).
  `tests/test_screen_family.py::test_a_failed_invalidate_after_a_reinstall_is_reported[mapped]` fails now and then
  under `-n auto`. Once the push gate runs the full suite, every flake blocks a push.
  - Fix the unsettled wait: settle on the publication or worker completion the assertion depends on, using the
    existing `settle`/`wait_until` helpers, never a fixed pause.
  - Prove it with 50 runs under `-n auto`, before and after the fix.
  - The todo moves to completed when it is done.

### Backlog
- **D-13: A duplicate-code gate is Backlog 999.17**, not phase 26 (owner 2026-11-16). No such gate exists:
  ruff does not detect duplication, and pylint was ruled out on 2026-10-15. 999.17 picks a tool and adds it as a
  gate with its own target and hook.
- **D-14: The outside-repo tools that push straight to `main` get a pending todo** (SPEC Boundaries). They are the
  GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow, and they must adopt the D-09
  flow.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements
- `.planning/phases/26-commit-and-push-quality-hooks/26-SPEC.md` — Locked requirements. MUST read before planning. R1,
  R2 and R4 carry 2026-11-16 amendments.
- `.planning/REQUIREMENTS.md` §Commit and push hooks — HOOK-01..HOOK-06.
- `.planning/ROADMAP.md` §Phase 26, and Backlog 999.17.

### Project rules the gates enforce
- `AGENTS.md` — Non-negotiable rules: never bypass a gate, validate before commit, never mutate the host.
- `.claude/dev-environment.md` — The Makefile is the task interface, and the pre-commit section.
- `.claude/git-workflow.md` — Coherent commits and force-with-lease. It gains the push flow and the escape hatch.
- `.claude/testing.md` — The scratch `HOME` and "done" rules for the scratch-repo hook tests.
- `.claude/python-tooling.md` — The ruff, pyright, bandit and vulture settings the gate module must pass.

### Current wiring
- `Makefile` — `install`, `setup`, `run`, `validate` and `test` recipes today.
- `.pre-commit-config.yaml` — the six local commit-stage hooks.
- `.github/workflows/ci.yml` — triggers, matrix, step timeouts.
- `pyproject.toml` — `[tool.pyright] include`, `[tool.coverage.run] source`, `[tool.vulture] paths`, and the
  `pre-commit>=3.8` dev dependency.
- `tests/test_makefile.py` — existing Makefile pins, to extend.

### pre-commit behaviour (installed 4.6.0)
- `.venv/.../pre_commit/commands/hook_impl.py:119-174` — pre-push ref parsing, first ref only, root push uses
  `all_files`.
- `.venv/.../pre_commit/commands/run.py:344-421` — the stash of unstaged edits when run with refs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/sandbox.py` and `tests/conftest.py`: the scratch-`HOME` sandbox every test runs under. The scratch-repo hook
  tests build their git repos inside it.
- `tests/test_makefile.py`: the existing Makefile recipe pins. Extend it for the per-gate targets, `dev-setup`, `run`,
  and the absence of `install` and `setup`.
- `wait_until` and the `settle` helpers in the pilot tests: the pattern for the D-12 flaky fix.

### Established Patterns
- Hooks are `repo: local`, `language: system`, run through uv. Keep them that way: no remote hook repos.
- Makefile targets are thin wrappers ("a target wraps a uv/tool command, it does not reimplement logic",
  dev-environment.md).
- Bandit skips B404, B603 and B310 deliberately, with the reason in a Makefile comment. The `make security` recipe
  keeps that comment.

### Integration Points
- `.git/hooks` is shared by worktrees (`git rev-parse --git-common-dir`). GSD executors commit in worktrees, so they
  get the commit hook. A worktree push goes through the pre-push gate.
- The CI job names are the required contexts on `main`. Renaming the job breaks the protection rule.
- `make test` uses 40% of the host's threads locally and every CPU in CI (ci.yml env). The push gate inherits the local
  cap.

</code_context>

<specifics>
## Specific Ideas

- Measured on 2026-11-16 at HEAD `ae9b99b0`: `make test` 62.3 s wall (59.1 s pytest, 7662 passed), and
  `make validate` 12.1 s. The owner accepted about 75 s per push.
- The owner's mental model: "commit/push trigger everything". Each gate can be called by name. `make validate` is an
  aggregate that does not know its members.

</specifics>

<deferred>
## Deferred Ideas

- A duplicate-code gate (`make duplicated-check`): Backlog 999.17 (D-13).
- Adopting the D-09 flow in the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow:
  a pending todo (D-14).

### Reviewed Todos (not folded)
The other 17 `todo.match-phase 26` matches scored on shared words ("2026", "phase", "test", "claude"), not on hooks or
CI. Examples: the pi install repair, iTerm2, Apple Containers, the run-log tail and AWS CLI onboarding. None of them
was folded.

</deferred>

---

*Phase: 26-commit-and-push-quality-hooks*
*Context gathered: 2026-11-16*
