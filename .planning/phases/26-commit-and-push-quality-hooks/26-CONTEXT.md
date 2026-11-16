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
       *(amended 2026-11-16 by D-25 and D-28: every untracked file outside `.planning/`; the gate-read files of
       D-28 count even when git ignores them.)*
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

## Planning amendments (2026-11-16, plan-phase)

Added by `/gsd-plan-phase 26` (unattended `--converge` run). Each entry cites the RESEARCH evidence and the SPEC item
it amends; SPEC.md carries a matching inline note.

- **D-15: Real-git proof is an e2e script; pytest uses fake runners** (RESEARCH Contradiction 1, Pitfall 1; amends
  SPEC R2, R3 and R4 acceptance, P2 and P5 verification, and this file's `code_context` line about scratch-repo tests).
  `tests/sandbox.py` refuses real `git`, `make`, `uv` and `pre-commit` inside pytest (`FORBIDDEN_PROGRAM_NAMES`,
  `check_launch` step 5), and widening it would reopen the 23.1 host-safety hole. So:
  - `make test` holds unit tests of `devtools/` with injected fake runners, plus a `sys.executable` child that proves
    the gate's signal forwarding with real signals.
  - `scripts/hooks-e2e.sh`, run by `make hooks-e2e`, drives real git, real pre-commit, the real gate and the real hook
    installer in scratch repos under `mktemp -d`. It starts every command from an `env -i` allowlist (scratch `HOME`,
    `PRE_COMMIT_HOME`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`) and never
    touches this checkout's `.git`.
  - The scratch repos copy the real `.pre-commit-config.yaml` and `devtools/`, with a scratch Makefile whose gate
    targets are cheap stand-ins. The real Makefile recipes (`dev-setup`, the gate targets, `validate`) are pinned
    by text tests.
  - CI runs `make hooks-e2e` on ubuntu and macOS after `make test`. Neither `make test` nor the push gate runs it.
  - Every SPEC line that says "in a scratch git repo" is met by `make hooks-e2e`, and the matching gate logic is
    pinned by pytest.
- **D-16: The docs-only rule excludes test-read files, `.planning/` included** (RESEARCH Contradiction 2, Pitfall 6,
  Pattern 5; amends SPEC R5's docs-only definition and D-11).
  - A changed path counts as docs-only when it is under `.planning/` or ends in a lowercase `.md`, and it matches no
    pattern of `TEST_READ` in `devtools/docs_only.py`.
  - The `TEST_READ` patterns are `AGENTS.md`, `README.md`, `.claude/*`, `docs/*` and
    `.planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*`. They use fnmatch, where `*` also matches `/`.
    `tests/test_catalog_audit_skill.py:251,401` reads the three SKILLJUDGE files, and `tests/test_docs.py:17-29` and
    `tests/test_postinstall.py:608` read the rest.
  - A change is docs-only only when it is non-empty and every path is docs-only.
  - A drift test classifies every `.md` string literal in `tests/**/*.py`, and every test module that names
    `.planning`, in a reviewed ledger. Every real file the ledger resolves to must be test-read.
    *(extended 2026-11-16 by D-27: link targets that tests resolve at runtime must be test-read too.)*
  - CI lists paths with `git diff --name-only -z --no-renames origin/main...HEAD`, so a rename counts both paths. An
    empty list or any git failure means a full run, and so does a classify step that writes no output
    (`if: steps.scope.outputs.full != 'false'`).
  - The classifier runs through `uv run --no-sync python -m devtools.docs_only`, not the runner's system `python3`, so
    its Python is the project's `>=3.11`.
  - Today the fast pass covers `.planning/` minus the three SKILLJUDGE files. The `.claude/*` pattern also sends the
    catalog-audit eval fixtures to a full run, which errs toward the full run.
- **D-17: "Interrupted" means SIGINT, SIGTERM or SIGHUP to the gate's process group** (RESEARCH Contradiction 3,
  Pattern 3, experiments 3 and 3b; amends SPEC P2 and the R3 concurrency edge).
  - pre-commit restores its stash on SIGINT only, so the gate runs pre-commit in its own process group.
  - The gate forwards the first such signal to that group as SIGINT, ignores later ones so a second Ctrl-C cannot
    cut the restore short, waits, and exits non-zero.
  - Residual cases, documented with the recovery command in `.claude/dev-environment.md`: a SIGKILL, and a SIGTERM
    sent only to the `git` process. pre-commit then leaves the edits in `$PRE_COMMIT_HOME/patch<timestamp>-<pid>`
    (default `~/.cache/pre-commit/`), and `git apply` on that file restores them.
- **D-18: The gate refuses five cases, first match wins** (RESEARCH Contradiction 4, Pattern 1, `run.py:347-358`,
  experiments 1E/1F; amends SPEC R3 and D-01's order). It checks, before any gate runs:
  1. unmerged paths: finish or abort the merge. This comes first because unmerged entries also show as staged, and
     "commit them" is the wrong advice in the middle of a merge.
  2. staged changes that are not committed;
  3. untracked, non-ignored `.py` files under `installer/`, `tests/` or `devtools/`. D-02 puts `devtools/` under
     every gate, so an untracked module there changes what lint, typecheck and the suite see.
     *(amended 2026-11-16 by D-25: every untracked, non-ignored file outside `.planning/`, the repo root included.)*
  4. an unstaged edit to `.pre-commit-config.yaml`: commit or discard it. pre-commit would refuse it anyway, but with
     advice to stage it, which then trips refusal 2.
  5. a pushed commit that is not HEAD. The pushed sha is peeled to its commit first, so a tag or a `HEAD:other`
     refspec whose commit is HEAD passes.
  Each refusal lists the files or refs, sorted, and the fix.
- **D-19: The push stage always runs `pre-commit run --hook-stage pre-push --fail-fast --from-ref HEAD --to-ref
  HEAD`** (resolves the D-01 root-push question and D-05's `fail_fast` discretion; RESEARCH Pattern 1, experiments
  1A, 1B, 1D and 8).
  - The refs are given and `--all-files` is not, so pre-commit keeps its stash on (`run.py:344`) for a root push, a
    new branch and an update alike.
  - Refusal 5 makes every pushed commit equal HEAD, and every gate is `always_run` with `pass_filenames: false`, so
    the refs feed nothing else.
  - `--fail-fast` is passed only at push, so a lint failure skips the 60 s suite. The commit stage still reports
    every failing gate, and the config sets no top-level `fail_fast`.
  - `pre-commit` and `git` are resolved on PATH with `shutil.which`, never a partial path (bandit B607).
  - Each hook's `name:` is its make target (`make lint`, and so on), so pre-commit's pass or fail line names the
    target to re-run (D-06).
- **D-20: The D-08 rename list is completed** (RESEARCH Contradiction 5). It adds:
  - `tests/test_render.py`, the `make setup` rows of `.claude/dev-environment.md`, and
    `.claude/skills/catalog-audit/SKILL.md` with its pin in `tests/test_catalog_audit_skill.py`;
  - the README "Makefile task interface" line, the CI descriptions in `docs/PUBLISHING.md` and the README, and the
    "`make validate` (and pre-commit)" wording of `.claude/python-tooling.md`;
  - the `setup.py` docstring, and the comments in `installer/compose.py` and `tests/test_setup.py`.
  The `make install` → `make dev-setup` sweep covers `README.md`, `AGENTS.md`, `.claude/dev-environment.md` and
  `.github/workflows/ci.yml`.
- **D-21: The CI trigger test is rewritten with the trigger change, and `pull_request` is dropped** (RESEARCH
  Contradiction 6 and Open Question 3; settles D-09's discretion). `tests/test_ci_workflow.py` pins a `push`
  trigger with `branches-ignore: [main]`, with no `main` push trigger and no `pull_request`. An outside contributor's
  branch gets CI once the maintainer pushes it to this repository. `.claude/git-workflow.md` says so.
- **D-22: `make dev-setup` runs from the main checkout, and agents never run it** (RESEARCH Contradiction 7, Pitfall 3;
  amends D-07's worktree sentence and settles the open AGENTS.md point).
  - `pre-commit install` bakes the installing interpreter (`INSTALL_PYTHON`) into the shared commit hook.
  - Run from a linked worktree, `make dev-setup` still installs into the shared hooks directory (SPEC edge), and
    prints a warning to re-run it from the main checkout before that worktree is removed.
  - AGENTS.md gains one sentence: agents never run `make dev-setup`, because it rewrites the hooks every worktree
    shares. The sentence sits outside the host-safety list, since it changes repo hooks and not the host.
    *(amended 2026-11-16 by D-26: the sentence names its one exception, the final owner-assigned checkpoint.)*
- **D-23: R6's grep target is read after D-04** (amends SPEC R6 acceptance and the matching acceptance line). Since
  D-04, `make validate` does run `pre-commit run --all-files`, so the docs say exactly that. The R6 check becomes:
  `rg 'runs? pre-commit hooks'` over AGENTS.md and `.claude/` finds nothing, and no doc says the hooks "mirror"
  `make validate`. HOOK-06 already reads "unless it does".
- **D-24: `make dev-setup` never replaces or chains a foreign pre-push hook** (RESEARCH Pattern 4, Assumption A6).
  - When `<hooks>/pre-push` exists without the gate's marker line, the hook step exits 1, names the file and says
    to move or delete it. It checks this before it writes anything.
  - A file with the marker line is rewritten only when its bytes differ, so a second run leaves both hooks
    byte-identical.
  - The shim fails closed: without `uv` on PATH it prints the cause and exits 1.
  - The commit hook keeps pre-commit's own migration: a foreign `pre-commit` hook becomes `pre-commit.legacy` and
    still runs.
    *(amended 2026-11-16 by D-29: the hook step refuses, untouched, a `pre-commit` entry that is not a regular file,
    and a foreign `pre-commit` while `pre-commit.legacy` already exists.)*

## Review amendments (2026-11-16, plan-phase `--reviews`, cycle 1, review commit `d933e9c8`)

Added when the plans were revised against `26-REVIEWS.md` (orchestrator-verified findings). Each entry cites the
finding and the SPEC item it amends. SPEC.md carries a matching inline note.

- **D-25: Refusal 3 covers every untracked, non-ignored file outside `.planning/`** (review H1, verified; amends
  D-18 item 3, D-01's refusal list, SPEC R3, its adjacency edge row and the untracked-file acceptance line).
  - The gate lists `git ls-files --others --exclude-standard -z` over the whole tree, the repo root included, drops
    names under `.planning/`, and refuses with the sorted list. The fix line reads: commit, stash, remove or ignore
    them, with `.git/info/exclude` for a local-only file.
  - Why the whole tree: pytest's rootdir is the repo root, so it loads an untracked root `conftest.py`, and an
    untracked root `pytest.ini`, `.pytest.ini`, `tox.ini` or `setup.cfg` overrides `[tool.pytest.ini_options]`
    (`pyproject.toml:49`). The gates also read `.coveragerc`, `pyrightconfig.json`, a `ruff.toml` or `.ruff.toml`
    in any parent directory, `typings/*.pyi`, `.shellcheckrc`, a `.bandit` file under the bandit targets, and a
    `GNUmakefile` or `makefile` that shadows `Makefile`. Tests read installer data files, docs and link targets.
    Any of these, untracked, can make a HEAD that fails in CI pass locally, which is the false green SPEC R3's
    target ("every push either tests a tree equal to HEAD or is refused") forbids.
  - Why not a fixed list of names: it would need the same upkeep review M1 rejects for the gate set, and each
    omission is a false green. The broad rule's cost is a false refusal for a scratch file outside `.planning/`.
    Its fix is one permanent line in `.git/info/exclude`, and agents already keep scratch files outside the repo.
    *(amended 2026-11-16 by D-28: ignored files take a fixed list of gate-read pathspecs, and the
    `.git/info/exclude` advice applies only to a file no gate reads.)*
  - Why `.planning/` stays exempt: SPEC R5 already treats it as docs, `.planning/debug/` and the phase `.gitkeep`
    files stay untracked by the owner's rule, and no gate reads `.planning/` except the SKILLJUDGE glob of
    `tests/test_catalog_audit_skill.py:401`. That test checks each file it finds, so an extra untracked file can
    only add failures and never hides one.
  - This checkout: the owner's untracked root `.graphifyignore` would be refused. 26-09 adds it to
    `.git/info/exclude` (local, reversible, never tracked) before the first real push.
  - **Reversibility:** reversible. The rule lives in one function of `devtools/push_gate.py`.
- **D-26: The AGENTS.md rule "agents never run `make dev-setup`" names its one exception** (review M12, reclassified
  from H6; amends D-22's AGENTS.md sentence). The exception is the final owner-assigned checkpoint of a phase plan
  that lists the real install explicitly. In this phase that is 26-09, because the owner's run brief (2026-11-16)
  assigns "installing the hooks for real in this checkout" to the orchestrator as the final step. The sentence
  stays generic in AGENTS.md (no phase number), so the rule and 26-09 agree.
- **D-27: Files a test reaches through a link resolved at runtime count as test-read** (review M7; extends D-16's
  drift test, no change to the SPEC R5 definition). `tests/test_docs.py:445-472` resolves every relative link and
  anchor in README.md and docs/TROUBLESHOOTING.md. tests/test_docs.py exposes those docs as `LINK_CHECKED_DOCS`
  and its parser as `link_targets`. A drift test in tests/test_docs_only.py requires every existing target inside
  the repo to be test-read (`is_docs_path` false). A drift test was chosen over a link parser inside the CI
  classifier: a new link always edits README or TROUBLESHOOTING, which are test-read, so that change runs the full
  suite, where the drift test fails until the target joins `TEST_READ`. The classifier stays small and stdlib-only
  for its first push.

## Review amendments (2026-11-16, plan-phase `--reviews`, cycle 2, review commit `52b2b19f`)

Added when the plans were revised against the cycle-2 section of `26-REVIEWS.md` (orchestrator-verified findings).
SPEC.md carries a matching inline note for each.

- **D-28: Gate-read files are refused even when git ignores them** (review C2-H1, verified; narrows "ignored files
  excluded" in D-01 item 2 and D-25, and in SPEC R3 and its adjacency edge row).
  - Refusal 3 runs a second, bounded query: `git --glob-pathspecs ls-files --others -z -- <GATE_READ_PATHSPECS>`.
    With no exclude option it lists every untracked file the pathspecs match, ignored or not. `GATE_READ_PATHSPECS`
    is a fixed tuple in `devtools/push_gate.py`: the root files `conftest.py`, `pytest.ini`, `.pytest.ini`,
    `tox.ini`, `setup.cfg`, `.coveragerc`, `pyrightconfig.json`, `ruff.toml`, `.ruff.toml`, `GNUmakefile`,
    `makefile`, `.shellcheckrc`, `.python-version` and `uv.toml`; Python sources at any depth under `installer/`,
    `tests/` and `devtools/` (every `conftest.py` there included); `ruff.toml` and `.ruff.toml` under those three
    trees; `.bandit` under the bandit targets `installer/` and `devtools/`; `.shellcheckrc` under `scripts/`; and
    `typings/`.
  - Why: pre-commit stashes only tracked edits (`staged_files_only.py:50-82`), so an ignored root `conftest.py`,
    `pytest.ini` or `GNUmakefile` still changes what pytest or make runs. pytest and pyright do not read
    `.gitignore`, so an ignored module under the source trees is still collected, type-checked and importable. D-25's
    advice to ignore a file through `.git/info/exclude` would otherwise turn refusal 3 into a bypass.
  - Why a fixed list here, when D-25 rejected one: the broad D-25 rule still covers every non-ignored file.
    Ignored files cannot take a broad rule, because `.venv/` and the tool caches are always present. The list names
    the two classes that change what runs: config and plugin files the gates load, and the gated sources. Every
    pathspec is an exact root name or starts with a literal directory, so git never walks `.venv/` (a scratch-repo
    trace with git 2.56.0 visited 5 directories, against 608 for the unbounded listing). `--glob-pathspecs` makes
    `**` behave the same whatever the caller's environment; a conflicting `GIT_LITERAL_PATHSPECS` or
    `GIT_NOGLOB_PATHSPECS` makes git exit 128, so the gate fails closed.
  - Advice: the refusal lists the gate-read files in their own sorted part, with the fix "commit them, or move them
    out of the repository", and never advises ignoring one. The `.git/info/exclude` advice stays only in the part
    listing the other untracked files, worded for a file no gate reads.
  - Residual (accepted): an ignored file outside the list, such as an unlisted config or a data file the code reads,
    can still let a local push pass while CI fails. CI on the pushed commit, required for everyone by
    `enforce_admins`, stays the binding gate.
  - This checkout: the query lists nothing (read-only check, 2026-11-16). `.graphifyignore` is read by no gate, so
    26-09's `.git/info/exclude` step for it stays valid.
  - **Reversibility:** reversible. One tuple and one query in `devtools/push_gate.py`.
- **D-29: `make dev-setup` preflights the commit hook before pre-commit's migration** (review C2-H2, verified;
  narrows D-24's last bullet and the SPEC R4 adjacency backstop row).
  - pre-commit moves a hook it does not recognize to `pre-commit.legacy` with `shutil.move`, which on Unix renames
    over an existing `pre-commit.legacy`. It also follows a symlink when it reads and writes the hook
    (`pre_commit/commands/install_uninstall.py:56-61`, `:75-77`, `:93`).
  - So, before `pre-commit install` and before any write, the hook step runs `os.lstat` on
    `<common>/hooks/pre-commit`. A non-regular entry (symlink, directory, FIFO) is refused untouched. A regular file
    without pre-commit's header line `# File generated by pre-commit` (a foreign hook) is refused untouched when
    `pre-commit.legacy` already exists as any entry, a dangling symlink included. The message names the file, or
    both files, and the fix: move one of them out of the hooks directory, merging them first if both are needed.
  - A foreign hook with no legacy file still goes through pre-commit's migration (D-24), and pre-commit's own hook
    next to a legacy file is rewritten in place, so a rerun after a migration stays byte-identical.
  - Residual (accepted): a hand-edited hook that keeps pre-commit's header but drops its `# ID:` hash counts as
    pre-commit's own here, while pre-commit treats it as foreign.
  - **Reversibility:** reversible. One preflight in `devtools/hooks.py`.

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
  tests build their git repos inside it. *(amended 2026-11-16, 26 plan-phase D-15: the sandbox refuses real git,
  make, uv and pre-commit, so pytest uses fake runners and `make hooks-e2e` builds the real scratch repos.)*
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
