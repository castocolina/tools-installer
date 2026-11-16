# Phase 26: Commit and push quality hooks - Research

**Researched:** 2026-11-16
**Domain:** git hooks (pre-commit 4.6.0 + a custom pre-push gate), Makefile gate wiring, GitHub branch protection and Actions, pytest sandbox
**Confidence:** HIGH for pre-commit/git/GitHub-API behaviour (live experiments), MEDIUM for the flaky-test root cause (not reproduced), MEDIUM for "direct push of an already-green SHA is accepted with strict + enforce_admins" (documented only in one sentence; cannot be tested without a mutating call)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Push gate mechanism**
- **D-01: The push gate is our own Python module, installed as git's `pre-push` hook.** It reads every pushed ref from stdin; pre-commit's own pre-push entry sees only the first ref with something to push (`pre_commit/commands/hook_impl.py:119-174`, pre-commit 4.6.0).
  - It applies the R3 refusals before any check, in this order:
    1. staged changes that are not committed;
    2. untracked `.py` files under `installer/` or `tests/` (recursive, ignored files excluded);
    3. any pushed commit that is not HEAD.
  - A deletion-only push goes through with no checks.
  - Each refusal lists the offending files or refs, sorted.
  - It then runs `pre-commit run --hook-stage pre-push --from-ref <remote sha> --to-ref <local sha>`. pre-commit sets the unstaged edits aside and restores them after a pass, a failure or an interrupt (`staged_files_only`, `run.py:344-421`), which is must-NOT P2.
  - For a push whose remote has none of the history (a root push), there is no remote sha. pre-commit then uses `all_files` and stashes nothing (`hook_impl.py:150-159`). The gate must still get edits set aside: it passes refs that keep pre-commit's stash on, or it refuses a dirty tree in that case. The planner researches which; the acceptance in SPEC R3 is fixed either way.
  - **Reversibility:** costly. The hook install path and the tests that drive a scratch repo depend on this shape.
- **D-02: The gate module is dev tooling, not product code.** It lives outside `installer/`, so it never ships in the wheel. Its directory joins every gate: ruff (the lint and format-check targets), pyright `include`, coverage `source` and vulture `paths`, so it is held to the same bar as `installer/`. The exact path is Claude's discretion.

**One gate, one target, one hook entry**
- **D-03: Every gate is a `make` target, and every pre-commit hook entry calls its target.** The command for each gate is written once, in the Makefile recipe. The targets are `make lint` (ruff check), `make format-check` (ruff format --check), `make typecheck` (pyright), `make security` (bandit, same skips), `make dead-code` (vulture), `make shellcheck` (same file list) and `make test` (kept, owner 2026-11-16). Each hook is `entry: make <target>`, `pass_filenames: false`, `always_run: true`, `language: system`. *(SPEC R1 amended.)*
  - **Reversibility:** costly. AGENTS.md, dev-environment.md, CI and agent habits name these targets.
- **D-04: `make validate` runs `pre-commit run --all-files` and does not list the gates itself** (owner: "validate should call them all without knowing what they are"). Adding a gate means one Makefile target plus one hook entry, and `make validate` picks it up. CI keeps calling `make validate`, then `make test`. The R1 parity test becomes a wiring test: every commit-stage hook entry is `make <target>` for an existing Makefile target; every gate target except `test` has a commit-stage hook; `make validate` is exactly `pre-commit run --all-files`; no commit-stage hook runs `make test`. *(SPEC R1 amended.)*
- **D-05: The push stage runs each static gate and then the test gate, each as its own hook entry.** The static hooks carry `stages: [pre-commit, pre-push]`, and the `make test` hook carries `stages: [pre-push]` and comes last in the file. A failure names the gate that failed, instead of one opaque `make validate` entry (owner: "each gate its own entry, so a failure is clear"). This is equivalent to SPEC R2's `make validate` then `make test`. *(SPEC R2 amended.)* Whether the push stops at the first failing gate is Claude's discretion. Skipping the 60 s suite after a lint failure is the likely choice (`fail_fast`).
- **D-06: Re-run only the gate that failed.** When a gate fails during a commit or a push, the agent or developer fixes the problem and re-runs that gate's target (`make typecheck`, and so on). `make validate` is for verifying a whole plan or phase. AGENTS.md and `.claude/dev-environment.md` carry a gate → target → stage table, and say this in one line.

**Target names**
- **D-07: `make install` is renamed `make dev-setup`, with no alias** (owner 2026-11-16).
  - It runs `uv sync`, then `pre-commit install --hook-type pre-commit` for the commit hook, then installs the D-01 gate as `pre-push` in the shared hooks directory (`git rev-parse --git-common-dir`/hooks, so worktrees share it).
  - `.pre-commit-config.yaml` sets `default_install_hook_types: [pre-commit]`. pre-commit does not own the pre-push hook.
  - Outside a git checkout it skips the hook step with a message and exits 0. With `core.hooksPath` set it fails and names it.
  - `ci.yml`, README.md and AGENTS.md switch to `make dev-setup`. *(SPEC R4 amended.)*
  - **Reversibility:** costly. CI and the docs call the target by name.
- **D-08: `make setup` is removed. `make run` is the wizard target** (owner: "what you call make setup is really make run"). Every place that names `make setup` is updated, as found with `rg -l 'make setup\b' --glob '!.planning/**'` on 2026-11-16:
  - product messages: `installer/guidance.py`, `installer/compose.py`, `setup.py`;
  - tests: `tests/test_setup.py`, `tests/test_guidance.py`, `tests/test_app.py`, `tests/test_wizard_app.py`, `tests/test_schedules_handover.py`, `tests/test_tool_browser.py`, `tests/test_catalog_audit_skill.py`, `tests/e2e_landing_driver.py`;
  - docs: README.md, AGENTS.md (including the "never run `make setup`" host rule, which now names `make run`).
  - The dated `docs/superpowers/` plans and `.planning/` history are records and stay as they are.
  - **Reversibility:** costly. Users see the hint text and tests pin it.

**Path to main**
- **D-09: Branch push, then CI, then fast-forward `main`** (owner 2026-11-16).
  - `ci.yml` runs on a push to any branch except `main`.
  - The `main` push trigger is dropped: the SHA that reaches `main` was already tested.
  - The `pull_request` trigger is dropped too: on a solo repo it would run the same SHA twice. Keeping it for outside PRs is Claude's discretion.
  - After both checks are green, the change lands with `git push origin <branch>:main`. Required status checks use strict mode, so a branch that is no longer a fast-forward of `main` must be updated and re-tested.
  - **Reversibility:** costly. Every later push flow, including the GSD helpers in the todo, follows it.
- **D-10: `enforce_admins` is applied last.** It goes on after the phase's own last direct push to `main`, then is read back with `gh api`. The phase's final change then lands through the D-09 flow, which proves it (SPEC R5 acceptance). `.claude/git-workflow.md` documents the off command, the on command and the read-back (must-NOT P6).
- **D-11: The docs-only fast pass lives inside the same `ci.yml` job**, so the required check names stay `validate & test on ubuntu-latest` / `…macos-latest`.
  - An early step lists the changed paths against the merge base with `origin/main` (NUL-separated; a rename counts both paths). The validate and test steps are skipped when every path is under `.planning/` or is a Markdown file no test reads.
  - The list of Markdown files tests read is derived and pinned by a pytest test. Today that list includes `.claude/architecture.md` and `.claude/skills/*/SKILL.md`, via `tests/test_postinstall.py:608`. The mechanics are Claude's discretion; must-NOT P4 holds.

**Folded Todos**
- **D-12: `2026-11-07-fix-the-flaky-failed-invalidate-after-reinstall-test`** (todo match score 0.9). `tests/test_screen_family.py::test_a_failed_invalidate_after_a_reinstall_is_reported[mapped]` fails now and then under `-n auto`. Once the push gate runs the full suite, every flake blocks a push.
  - Fix the unsettled wait: settle on the publication or worker completion the assertion depends on, using the existing `settle`/`wait_until` helpers, never a fixed pause.
  - Prove it with 50 runs under `-n auto`, before and after the fix.
  - The todo moves to completed when it is done.

**Backlog**
- **D-13: A duplicate-code gate is Backlog 999.17**, not phase 26 (owner 2026-11-16). No such gate exists: ruff does not detect duplication, and pylint was ruled out on 2026-10-15. 999.17 picks a tool and adds it as a gate with its own target and hook.
- **D-14: The outside-repo tools that push straight to `main` get a pending todo** (SPEC Boundaries). They are the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow, and they must adopt the D-09 flow.

### Claude's Discretion
- The gate module's path and CLI shape (D-02), and the exact `pre-commit run` ref arguments in the root-push case (D-01, researched).
- Whether the push stage uses `fail_fast` (D-05).
- The wording of refusal and failure messages. Each one names the `make` target to re-run (D-06).
- The CI docs-only step's implementation and keeping or dropping `pull_request` (D-09, D-11).
- The `make help` descriptions of the new targets.

### Deferred Ideas (OUT OF SCOPE)
- A duplicate-code gate (`make duplicated-check`): Backlog 999.17 (D-13).
- Adopting the D-09 flow in the GSD merge helpers, the ai-kit-commit-fold unit flow and the GSD phase-complete flow: a pending todo (D-14).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| HOOK-01 | Every commit runs each static gate as its own hook entry calling its `make` target; `make validate` = `pre-commit run --all-files`; no commit-stage hook runs tests | Hook config shape and `--all-files` stage semantics verified live (Experiment 8); wiring-test recipe in Validation Architecture; P3 test must follow `entry -> Makefile recipe` |
| HOOK-02 | Every push runs each static gate then `make test`, each its own entry; failure aborts the push | `stages` semantics, `--fail-fast` CLI flag, git exit-code semantics verified (Experiments 2, 8) |
| HOOK-03 | Push gate tests a tree equal to the pushed commit; refusals; unstaged edits restored | Stdin format, root-push stash answer, pre-commit's own refusals, signal behaviour (Experiments 1, 2, 3) |
| HOOK-04 | `make dev-setup` installs commit hook and push gate idempotently; skips outside git; fails on `core.hooksPath`; `make setup` removed, `make run` = wizard | Shim, worktree, hooksPath, legacy-hook behaviour (Experiments 4, 5, 9); rename sweep list |
| HOOK-05 | `main` gated by CI for admins too; branch -> CI -> ff flow; docs-only fast pass under the same check names | GitHub REST commands, ci.yml design, docs-only rule, Markdown-read enumeration |
| HOOK-06 | Docs state each gate/target/stage with timings, the flow, the escape hatch; no false "runs pre-commit hooks" claim | Doc lines to change; `tests/test_docs.py` constraints |
</phase_requirements>

## Summary

pre-commit 4.6.0 does almost everything the gate needs, and the experiments settle every open D-01 question. `pre-commit run --hook-stage pre-push --from-ref X --to-ref Y` stashes unstaged edits whenever `--all-files` and `--files` are absent (`run.py:342`), whatever X and Y are, so the root-push case needs no special handling: pass `--from-ref HEAD --to-ref HEAD` (or the remote sha when it exists locally). Every gate hook is `always_run` with `pass_filenames: false`, so the refs only feed the (unused) changed-file list and the `PRE_COMMIT_FROM_REF` env vars. pre-commit itself refuses an unstaged `.pre-commit-config.yaml` and unmerged paths when the stash is on; both belong in the gate's own refusal list with clear messages, because pre-commit's wording says "commit".

Two findings change the plan. First, **interrupt safety is not free**: pre-commit restores the stash on SIGINT only. On SIGTERM, SIGHUP and SIGKILL it dies with the working tree reverted and the edits left in a `patch*` file under `PRE_COMMIT_HOME`. The gate must catch SIGINT/SIGTERM/SIGHUP, forward SIGINT to a child process group holding pre-commit and its hooks, wait, and exit non-zero; a prototype did this correctly in every group-signal trial. A lone SIGTERM to the `git` process and SIGKILL cannot be covered. Second, **the test sandbox refuses real `git`, `make`, `uv` and `pre-commit`** (live probe below), so the SPEC's "in a scratch git repo" acceptances cannot be pytest tests that launch real tools. Recommended split: (1) unit and fake-runner tests in `make test` for all gate logic, including signal forwarding through a Python child; (2) a reviewed `scripts/hooks-e2e.sh` that drives real git and real pre-commit in scratch repos with `env -i`, run by a make target and by CI (not by `make test`); (3) text-parsing wiring tests like `tests/test_makefile.py` already does. This contradicts CONTEXT's "scratch-repo hook tests build their git repos inside the sandbox" and needs an owner-visible amendment (see Contradictions).

CI design: `on: push: branches-ignore: [main]`, `fetch-depth: 0`, a stdlib-only classifier module run by `python3 -m` before `uv`/`make`, `git diff --name-only -z --no-renames origin/main...HEAD` (a rename lists both paths only with `--no-renames`), step-level `if:` on the install/validate/test steps so job names and required contexts stay identical, and an empty or failing diff treated as "run everything". Tests read far more Markdown than the SPEC assumes (AGENTS.md, README.md, every `.claude/*.md`, all of `docs/**`, plus three `.planning/` files), so the docs-only fast pass is narrow in practice.

**Primary recommendation:** Build `devtools/` (push_gate, hooks installer, docs_only) with injected runners; make the pre-push shim `exec uv run python -m devtools.push_gate "$@"` behind a `command -v uv` guard; verify real-git behaviour with a reviewed e2e script, not pytest.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Commit-stage static gates | Local git hook (pre-commit) calling `make <target>` | CI (`make validate`) | Command written once in the Makefile; hook and CI share it |
| Push gate (tree check, refs, stash, run gates) | Local git hook (own Python module) | pre-commit as subprocess | pre-commit's own pre-push entry reads only the first ref |
| Hook installation | Makefile `dev-setup` -> `devtools` installer | pre-commit `install` for commit hook | Installer logic testable with a fake runner; Makefile stays a thin wrapper |
| Only-green-SHA-reaches-main | GitHub branch protection (server) | CI workflow | Local hooks are bypassable; only the server binds admins |
| Docs-only fast pass | CI step (stdlib module, shared with pin test) | `.github/workflows/ci.yml` conditions | Must keep required check names; skip at step level |
| Real-git behavioural proof | Reviewed e2e script (non-pytest) | CI | Sandbox forbids real git/pre-commit in pytest |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pre-commit | 4.6.0 installed (`pre-commit>=3.8` declared) | Runs hook entries, stashes unstaged edits, `--fail-fast`, `--from-ref/--to-ref` | Already a dev dependency; every needed CLI flag exists in 3.8+ and 4.6.0 [VERIFIED: `pre-commit run --help` this session] |
| git | 2.56.0 on this host | pre-push protocol, `--path-format=absolute` (2.31+) | Platform tool |
| GNU make | host | Single home of each gate command | Project convention (dev-environment.md) |
| Python stdlib only | 3.11+ (project `requires-python = ">=3.11"`) | `devtools/` modules: `subprocess`, `signal`, `os`, `pathlib` | `Popen(process_group=0)` needs 3.11; the docs-only classifier must also run on the runner's system `python3` before `uv` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML + types-pyyaml | already in dev group | Parse `.pre-commit-config.yaml` and `ci.yml` in wiring tests | Same as `tests/test_ci_workflow.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Own pre-push gate | pre-commit's own pre-push entry | Reads only the first pushed ref (`hook_impl.py:119-174`) and uses `all_files` with no stash on a root push; rejected by D-01 |
| `uv run` in the shim | `.venv/bin/python` of the checkout | Faster, but breaks in a worktree with no `.venv` and drifts from how every make target runs; use `uv run` |
| pytest scratch-repo tests with real git | e2e shell script + fake-runner unit tests | pytest cannot launch real git (sandbox); see Contradictions |

**Installation:** none. No new packages. `devtools/` is in-repo code; `[tool.hatch.build.targets.wheel] packages = ["installer"]` (pyproject.toml) keeps it out of the wheel [VERIFIED: pyproject.toml read]. The sdist is not restricted by that setting.

**Version verification:** `pre-commit 4.6.0` [VERIFIED: `.venv/bin/pre-commit --version`], `git version 2.56.0` [VERIFIED], `uv 0.11.28` [VERIFIED].

## Package Legitimacy Audit

No external packages are installed by this phase (no `uv add`). Audit table omitted.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
git commit ──> .git/hooks/pre-commit (generated by `pre-commit install`, INSTALL_PYTHON=venv python)
                  └─> pre-commit hook-impl ──> stash unstaged ──> hooks in file order
                         make lint | format-check | typecheck | security | dead-code | shellcheck
                         (always_run, pass_filenames false, stages [pre-commit, pre-push])

git push ──> .git/hooks/pre-push (our shim, in <git-common-dir>/hooks)
                  ├─ `command -v uv` missing ──> message, exit 1 (fail closed)
                  └─ exec uv run python -m devtools.push_gate "$@"      (cwd = pushing checkout)
                         stdin lines: <local ref> <local sha> <remote ref> <remote sha>
                         ├─ drop deletions; none left ──> exit 0, no checks
                         ├─ refuse (sorted lists, in order): staged | untracked .py | unstaged
                         │     .pre-commit-config.yaml | unmerged paths | pushed commit != HEAD
                         └─ spawn pre-commit in its OWN process group:
                               pre-commit run --hook-stage pre-push --fail-fast
                                  --from-ref <remote sha | HEAD> --to-ref <local sha>
                               ├─ stash unstaged edits; static gates; then `make test` (pre-push only, last)
                               └─ restore edits on pass / fail / SIGINT
                            gate traps SIGINT/SIGTERM/SIGHUP -> killpg(child, SIGINT) -> wait -> exit non-zero
                  non-zero exit ──> git aborts the whole push, no ref moves

branch push ──> GitHub Actions (push, branches-ignore main) ──> checkout fetch-depth 0
      └─ python3 -m devtools.docs_only (stdlib) ──> full=true|false
            full=true : dev-setup, validate, test   |  full=false : steps skipped, job green
git push origin <branch>:main ──> branch protection (strict, enforce_admins) accepts the already-green SHA
```

### Recommended Project Structure
```
devtools/                 # dev tooling, never in the wheel (D-02); stdlib only
├── __init__.py
├── push_gate.py          # pre-push: parse refs, refusals, run pre-commit, signal forwarding
├── hooks.py              # `python -m devtools.hooks install` (dev-setup hook step)
└── docs_only.py          # CI rule + CLI; the pin test imports the same function
tests/
├── test_push_gate.py     # fake runner + fake git/pre-commit under tmp_path (python child)
├── test_hooks_install.py # fake runner; shim bytes; idempotence; foreign file; hooksPath; not-a-repo
├── test_docs_only.py     # rule matrix, rename/space cases, Markdown-read drift detector
└── test_hook_wiring.py   # .pre-commit-config.yaml + Makefile text pins (P1, P3, order, stages)
scripts/hooks-e2e.sh      # real git + real pre-commit in scratch repos (reviewed, shellchecked)
```
`devtools` is not a name any installed package uses in `.venv/lib/python3.12/site-packages` [VERIFIED: `ls | grep` this session found only an unrelated `dev` entry]; the PyPI project `python-devtools` imports as `devtools`, so keep it out of the dev group. Add `devtools` to: `[tool.pyright] include`, `[tool.coverage.run] source`, `[tool.vulture] paths`, the `make lint` / `make format-check` path lists, and (recommended) bandit's `-r` list. Note bandit B607 (partial executable path) is not in the skip list `B404,B603,B310`; installer code passes today, so the gate should resolve programs with `shutil.which` or `sys.executable -m pre_commit`.

### Pattern 1: pre-commit invocation that keeps the stash on (answers D-01 root push)
**What:** `stash = not args.all_files and not args.files` [VERIFIED: `.venv/.../pre_commit/commands/run.py:342`, quoted: `stash = not args.all_files and not args.files`]. Passing both refs keeps `stash` true. Live result with `--from-ref HEAD --to-ref HEAD`: "[WARNING] Unstaged files detected." ... "Passed" ... "[INFO] Restored changes", file bytes identical after (Experiment 1A). Same with no refs (1B) and with an unrelated-history ref pair (1D).
**When to use:** always, in the gate. Use `from_ref = remote_sha` when it is non-zero and `git cat-file -e <remote_sha>^{commit}` succeeds (pre-commit does the same via `_rev_exists`, `hook_impl.py:_rev_exists`), else `HEAD`; `to_ref = HEAD` sha. Never `--all-files`.
**No-merge-base case:** `get_changed_files` runs `git diff --name-only --no-ext-diff -z <old>...<new>` and on `CalledProcessError` retries with `<old>..<new>` [VERIFIED: `pre_commit/git.py:158-167`]. Live: `fatal: <sha>...HEAD: no merge base`, rc 128, then pre-commit still ran and passed (1D). A remote sha missing locally would raise instead, hence the existence check.
**Refusals that fire only when the stash is on** [VERIFIED: `run.py:347-358`, live 1E/1F]:
- `Unmerged files.  Resolve before committing.` (rc 1) when `git ls-files --unmerged` is non-empty.
- `Your pre-commit configuration is unstaged.\n`git add .pre-commit-config.yaml` to fix this.` (rc 1) when `git diff --quiet .pre-commit-config.yaml` fails.
Both say "commit"/"git add", which is wrong advice for a push gate that also refuses staged changes (adding the config would then trip refusal 1). The gate must pre-check both and refuse with its own message (commit or discard the config edit; finish or abort the merge).

### Pattern 2: How git calls pre-push (D-01 stdin parse)
[VERIFIED: live experiment 2, git 2.56.0]
- argv: `$1` = remote name (`origin`), `$2` = remote URL (a path for a local bare remote). cwd = the pushing work tree root (main checkout or linked worktree).
- stdin, one line per ref: `<local ref> SP <local sha> SP <remote ref> SP <remote sha> LF`. Observed lines:
  - new remote ref: `refs/heads/main d2da8b7d… refs/heads/main 0000000000000000000000000000000000000000`
  - update: `refs/heads/main 11d19de6… refs/heads/main d2da8b7d…`
  - deletion: `(delete) 0000000000000000000000000000000000000000 refs/heads/main 11d19de6…`
  - tag: `refs/tags/v1 11d19de6… refs/tags/v1 000…`
  - refspec `HEAD:feat`: local ref is `HEAD`: `HEAD db3e1681… refs/heads/feat 11d19de6…`
  - Multi-ref push gives one line per ref in one hook call.
- The hook IS invoked with **empty stdin** when nothing needs pushing (`git push --all` when up to date): treat as exit 0.
- Exit status: non-zero aborts the entire push; with `PP_RC=1` neither a single ref nor either ref of a two-ref push moved (remote read back unchanged).
- For annotated tags the local sha is the tag object, not the commit: resolve with `git rev-parse <sha>^{commit}` before comparing to HEAD.
- Env exported to the hook: `GIT_EXEC_PATH`, `GIT_PREFIX=` (empty) in the main checkout; plus `GIT_DIR=<main>/.git/worktrees/<name>` in a linked worktree. No `GIT_INDEX_FILE`, no `GIT_WORK_TREE`. For the **pre-commit** hook: `GIT_INDEX_FILE` (relative `.git/index` in the main checkout, absolute in a worktree), `GIT_EDITOR=:`, `GIT_AUTHOR_DATE`, and in a worktree `GIT_DIR`.

### Pattern 3: Signal-safe gate (answers P2 / research focus 3)
[VERIFIED: live experiments 3, 3b]
- pre-commit alone, stdout a pipe, unstaged edit `UNSTAGED\x00bytes\n`:
  - SIGINT to the process group, and to pre-commit only: rc 130, "Restored changes", **bytes identical**.
  - SIGTERM (group or pid), SIGHUP, SIGKILL: pre-commit dies (rc -15 / -1 / -9); **edit NOT restored**, working tree reverted, patch file left at `PRE_COMMIT_HOME/patch<ts>-<pid>` (the cache dir held one per trial).
- pre-commit hooks share pre-commit's process group (no `setsid` anywhere: grep of `util.py main.py error_handler.py xargs.py commands/run.py staged_files_only.py` found no `start_new_session`/`setsid`), so `killpg(pre-commit pgid, SIGINT)` also reaches `make`/`pytest`.
- Prototype gate (below), hook shim `exec python3 gate`, real `git push`: SIGINT to the group, SIGTERM to the group, SIGHUP to the group: gate finished (pre-commit exited) **before** git returned, edit restored byte-identical, remote ref unmoved, git rc non-zero.
- **Not coverable:** a lone SIGTERM to the `git` process. In the final 12-trial run, git exited at once (zombie) while the gate, pre-commit and the hook kept running orphaned, gate never signalled (gate.log empty); an earlier 6-trial run had 5 trials where the gate was signalled. Behaviour is inconsistent; the orphaned tree runs to completion and pre-commit restores the edit when it finishes. SIGKILL of anything cannot be handled; document recovery: `git apply "$PRE_COMMIT_HOME"/patch<ts>-<pid>` (default `~/.cache/pre-commit/`).

### Pattern 4: Hook shim and installer (research focus 4)
[VERIFIED: live experiments 4, 5, 9]
- Shim content (fails closed): see Code Examples. With `uv` absent from PATH, even a bare `exec uv run ...` exits 1 (`exec: uv: not found`, git prints `failed to push some refs`); the explicit guard only improves the message. Never `|| true`.
- `uv run` from a linked worktree runs the **worktree's own** `devtools/` code (`gate from …/wt …/wt/devtools/gate.py`) and creates `<worktree>/.venv` when absent, even with `--no-sync` (live: "Creating virtual environment at: .venv"). With real dependencies that is a network sync on first push from a fresh worktree; `make lint` etc. already do the same, so accept it and document it.
- `git rev-parse --git-common-dir` prints `.git` (relative) in the main checkout and an absolute path in a worktree; use `git rev-parse --path-format=absolute --git-common-dir` (git 2.31+) or join with cwd as pre-commit does (`os.path.normpath(os.path.join(git_root, out))`, `git.py:86-93`).
- Outside a checkout: `fatal: not a git repository (or any parent up to mount point /)`, rc 128 -> installer prints the skip message and exits 0. `git config core.hooksPath` unset: rc 1, empty output.
- `pre-commit install` with `core.hooksPath` set: stderr `[ERROR] Cowardly refusing to install hooks with `core.hooksPath` set.` + `hint: `git config --unset-all core.hooksPath``, **rc 1** [VERIFIED live 5A; source `install_uninstall.py:123-128`]. The installer should check `core.hooksPath` itself first (it must also guard its own pre-push write) and name the key and the fix.
- Existing foreign hook: pre-commit moves it to `<hook>.legacy`, prints `Running in migration mode with existing hooks at .git/hooks/pre-commit.legacy` and `Use -f to use only pre-commit.`, rc 0; a later commit ran the legacy hook first (`FOREIGN-RAN`) [VERIFIED live 5B/5D, source `install_uninstall.py:75-86`]. A second `pre-commit install` leaves the file byte-identical (sha256 check OK, 5C).
- **Our own pre-push on a foreign file: refuse** (exit 1, name the file, say move or delete it) unless the file carries our marker line. Silently replacing a user hook is data loss; silently chaining needs a second mechanism. Recommended, flagged as discretion.
- **Worktree pitfall:** the pre-commit template embeds `INSTALL_PYTHON=<sys.executable of the python that ran install>` [VERIFIED: `.git/hooks/pre-commit` line `INSTALL_PYTHON=/var/home/…/.venv/bin/python3`; template `hook-tmpl`]. `make dev-setup` run inside a linked worktree writes that worktree's `.venv` path into the shared hook; deleting the worktree makes the hook fall back to `command -v pre-commit`, then `` `pre-commit` not found. Did you forget to activate your virtualenv? `` and exit 1, so every commit in every checkout fails closed until `make dev-setup` is re-run. Document: run `make dev-setup` from the main checkout (or re-run after removing the worktree); consider having the installer warn when `--git-dir != --git-common-dir`.

### Pattern 5: CI docs-only classification (research focus 7)
[VERIFIED: live experiment 7]
`git diff --name-only -z --no-renames origin/main...HEAD` lists **both** paths of a rename; the default (`renames` on) lists only the new path, so moving `installer/a.py` into `.planning/` would look docs-only. `--name-status -z -M` also works but needs status parsing; `--name-only -z --no-renames` is the smallest correct choice. NUL separation preserved `installer/a b.py` and a path containing a newline. With no merge base the command fails (`fatal: origin/main...HEAD: no merge base`, rc 128): the classifier must treat any git failure, and an empty path list, as `full=true`.

### Anti-Patterns to Avoid
- **`pkill -f` patterns in tooling or tests:** it matches the invoking shell's own command line. (Hit once during this research; killed the calling shell.) Kill by pid or process group.
- **Treating `PRE_COMMIT_HOME` patch files as an interrupt-safety mechanism:** they are a recovery artefact, not a restore.
- **Running the gate's pre-commit child in the git hook's process group while expecting SIGTERM to reach it:** git/the shell may not forward; run the child in its own group and forward explicitly.
- **Job-level `if:` on the matrix job:** a skipped matrix job reports a check whose name may not match the required context; skip steps instead [ASSUMED for the naming detail; GitHub docs say only "a job skipped due to a conditional reports Success" and "a workflow skipped by path/branch filtering leaves checks Pending and blocks merging" — CITED below].
- **Workflow-level `paths-ignore` for the docs-only pass:** checks stay "Pending" and block merging [CITED: docs.github.com troubleshooting-required-status-checks].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stashing and restoring unstaged edits | A custom `git stash` wrapper | `pre-commit run` with both refs | Binary-safe patch, intent-to-add handling, restores on SIGINT; reimplementing risks P2 |
| Hook-file generation for the commit stage | A second shim writer for pre-commit | `pre-commit install --hook-type pre-commit` | Legacy-hook migration and idempotence already correct |
| Parsing changed paths | Splitting `git diff` output on newlines | `git diff -z --no-renames` | Spaces, newlines, renames |
| Branch protection toggling | Raw curl | `gh api` with the documented endpoints | Auth, repo resolution |
| Waiting in Textual pilot tests | Fixed `pilot.pause()` | `tests/screen_family.wait_until` / `settle` | Project rule in `.claude/testing.md` |

**Key insight:** pre-commit already solves stash/restore; the only gaps are what it does on SIGTERM/SIGHUP (nothing) and its reading of only one pushed ref. The gate is thin glue around pre-commit, not a reimplementation.

## Runtime State Inventory

This phase renames `make install` -> `make dev-setup` and removes `make setup`. Answers:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None: no database or datastore keys the target names (verified: `rg 'make (setup|install)'` hits only text in code, tests, docs, ci.yml) | none |
| Live service config | GitHub branch protection on `main` (UI/API state, not in git): contexts `validate & test on ubuntu-latest`, `validate & test on macos-latest`, `strict: false`, `enforce_admins: false` [VERIFIED: `gh api repos/castocolina/tools-installer/branches/main/protection` GET this session]. The README CI badge points at `ci.yml` (unchanged name). | `strict: true` PATCH and `enforce_admins` POST (owner-applied, D-10); job names must stay byte-identical |
| OS-registered state | None for the renamed targets. `.git/hooks/pre-commit` in this checkout was installed by hand with `INSTALL_PYTHON` = this checkout's `.venv` python [VERIFIED]; there is no `pre-push`. | Developer re-runs `make dev-setup` once after the phase (outside agent experiments) |
| Secrets/env vars | None name the targets | none |
| Build artifacts | `.venv` unaffected; `devtools/` is not in the wheel. | none |

**Rename sweep (code edits only, no data migration).** `rg -n 'make setup\b' --glob '!.planning/**' --glob '!docs/superpowers/**'` on 2026-11-16 (note: `rg` skips hidden directories by default, so `.claude/` and `.github/` need `--hidden`):

| File | Lines | Kind |
|------|-------|------|
| `setup.py` | 3 | docstring "Run via `make setup`" |
| `installer/guidance.py` | 142, 224, 421 (comment), 425 | product hint text (`(make setup)`, ``Run `make setup` and open the Doctor view…``, ``Turn on tmp cleanup in `make setup`'s Schedules view``) |
| `installer/compose.py` | 798 | comment |
| `README.md` | 104, 110, 111, 325 | usage |
| `AGENTS.md` | 12, 16, 33 | command list, alias line, host rule |
| `tests/test_guidance.py` | 226, 243, 256, 257, 306, 351, 637 | pins ``Run `make setup` `` |
| `tests/test_wizard_app.py` | 3566, 3570, 3672, 3675, 3743 | pins |
| `tests/test_app.py` | 1911 | `assert "make setup" in out` |
| `tests/test_render.py` | 370 | `assert "make setup" in out` (**missing from D-08's list**) |
| `tests/test_schedules_handover.py` | 356 | pins schedules hint |
| `tests/test_setup.py` | 1074 | comment |
| `tests/test_tool_browser.py` | 369, 385 | docstrings |
| `tests/e2e_landing_driver.py` | 419 | docstring |
| `tests/test_catalog_audit_skill.py` | 140 | list entry `"make setup"` asserted in the SKILL text |
| `.claude/dev-environment.md` | 30, 32 | Makefile table (**missing from D-08**) |
| `.claude/skills/catalog-audit/SKILL.md` | 189 | host-forbidden list (**missing from D-08**; pinned by `tests/test_catalog_audit_skill.py:140`) |

`make install` (rename to `make dev-setup`): `README.md:103,324`; `AGENTS.md:10`; `.github/workflows/ci.yml:30`; `.claude/dev-environment.md:30` [all VERIFIED by `rg --hidden`]. `make run` stays (`docs/TROUBLESHOOTING.md:12` already uses it). Tests that pin the old Makefile targets: `tests/test_makefile.py` — `test_launch_targets_run_without_the_dev_venv` loops `("setup","doctor","fix","uninstall")`; `test_run_is_an_alias_of_setup` asserts `prereqs == ["setup"]`; `test_every_setup_py_recipe_uses_the_launch_form` asserts `launcher_targets == ["setup", "doctor", "fix", "uninstall"]` (file order). CI-claim docs to correct too: `docs/PUBLISHING.md:30-31` ("CI … runs … on every push and pull request"), `README.md:368` and `.claude/python-tooling.md` ("`make validate` (and pre-commit)").

## Common Pitfalls

### Pitfall 1: The sandbox forbids the tools the SPEC wants tests to use
**What goes wrong:** A pytest that runs `subprocess.run(["git", "init"])`, `make`, `uv` or `pre-commit` fails with a launch refusal (and the refusal registry fails the test even if caught).
**Why it happens:** `tests/sandbox.py` `FORBIDDEN_PROGRAM_NAMES` includes `uv`, `git`, `gh`, `pip`, `npm`, … and `check_launch` step 5 refuses any host program not under pytest's base temp [VERIFIED: tests/sandbox.py read]. Live probe through `-p tests.conftest`: `["git","--version"]`, `["make","--version"]`, `["/usr/bin/git","--version"]` each raised the guard refusal (the `refused()` context manager matched) ; `["pre-commit","--version"]` hit FileNotFoundError because the stripped PATH has no `.venv/bin`; a script planted at `tmp_path/git` ran and printed its output (4 of 5 passed, the fifth failed only on the missing-PATH FileNotFoundError, i.e. it does not run either).
**How to avoid:** Inject the runner into every `devtools` function and unit-test with fakes; a Python child (`sys.executable -m devtools.push_gate`) is allowed (interpreter allowlist) and faces `tests/child_guard/sitecustomize.py`, so a fake `git` and a fake `pre-commit` script planted under `tmp_path` and put first on the child's PATH work. Prove real-git behaviour in `scripts/hooks-e2e.sh`. Never widen `CHECKOUT_SCRIPTS` or the allowlist.

### Pitfall 2: GIT_* variables leak into anything run from a hook
**What goes wrong:** Tests or helper commands run by `make test` from the pre-push hook inherit `GIT_DIR` (worktree), `GIT_PREFIX`, `GIT_EXEC_PATH`; from the pre-commit hook `GIT_INDEX_FILE`, `GIT_EDITOR`, `GIT_AUTHOR_DATE`, `GIT_CONFIG_PARAMETERS`. Any git command launched with these targets the real checkout.
**Why it happens:** pre-commit does NOT scrub them for hook commands: `no_git_env` is used only for clones and `init_repo` (`pre_commit/git.py`, `store.py:200`; grep of the package shows no other call site) [VERIFIED]. Live: a hook command under `pre-commit run` with `GIT_DIR` set printed `GIT_DIR=…/.git/worktrees/wt` (Experiment 5G); under a real commit in the main checkout it printed `GIT_INDEX_FILE=.git/index` (5E).
**How to avoid:** Real-git e2e script: start from `env -i` with an explicit allowlist (`PATH`, scratch `HOME`, `PRE_COMMIT_HOME`, `XDG_CACHE_HOME`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, `GIT_AUTHOR_NAME/EMAIL`, `GIT_COMMITTER_NAME/EMAIL` or `-c user.name -c user.email`) rather than a denylist. pytest tests never launch git (sandbox), so the hazard is confined to that script; `installer/run.py:run_git_isolated` is the in-repo precedent for the scrub (drops `_GIT_INHERITED`, sets `GIT_TERMINAL_PROMPT=0`).

### Pitfall 3: `make dev-setup` from a linked worktree bakes in that worktree's venv
See Pattern 4. Detection: `git rev-parse --git-dir` != `--git-common-dir`. Warning sign: commits fail with "`pre-commit` not found" after a worktree was deleted.

### Pitfall 4: Test-pinned Makefile shape
**What goes wrong:** `tests/test_makefile.py` parses the Makefile text: `.PHONY` must stay on **one** line (`makefile.split(".PHONY:")[1].split("\n")[0]`), the target regex is `^([a-zA-Z0-9_-]+)\s*:(.*)$` (so `UV := uv` would be parsed as a target; use `?=` or no variable), every public target needs a `## ` help comment, and `make help` greps `'^[a-zA-Z_-]+:.*?## .*$$'` (no digits in target names; `format-check`, `dead-code`, `dev-setup` are fine; width `%-12s` fits `format-check`).
**How to avoid:** extend `_recipes()` pins, do not reformat the file.

### Pitfall 5: P3 and P1 tests must follow the hook entry into the recipe
The hook entries become `make <target>`, so a grep over `.pre-commit-config.yaml` for `--fix` proves nothing. The P3 test must resolve each `entry` to its Makefile recipe lines and assert no `--fix`, no `ruff format` without `--check` there. The P1 grep (`--no-verify`, `SKILL=`/`SKIP=`) covers `Makefile`, `.pre-commit-config.yaml`, `.github/`, `scripts/`, `devtools/`, `AGENTS.md`, `.claude/*.md` (not `.claude/gsd-core`, not `.planning`).

### Pitfall 6: The `.planning/` blanket in the docs-only rule is wrong today
`tests/test_catalog_audit_skill.py:251` sets `PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "24.3-catalog-audit-skill"` and `:401` globs `24.3-SKILLJUDGE-*.md` there; three tracked files match (`24.3-SKILLJUDGE-1.md`, `-2.md`, `-FINAL.md`) [VERIFIED: `ls` + `git ls-files | grep -c SKILLJUDGE` = 3]. An edit to one is not docs-only under P4.

### Pitfall 7: Untracked non-`.py` files still reach the push gate's tree
The gate refuses only untracked `.py` under `installer/` and `tests/` (R3). An untracked `tests/data/x.json` or a new untracked `scripts/*.sh` stays visible to `make test`/shellcheck while pre-commit stashes only tracked edits. Residual risk, in scope as written; flag it (cheap extension: refuse any untracked, non-ignored file under `installer/`, `tests/`).

### Pitfall 8: `test_ci_workflow.py` pins both triggers
`test_ci_triggers_on_push_and_pull_request` asserts `"push" in triggers` and `"pull_request" in triggers`. Dropping `pull_request` (D-09) requires rewriting this test; the other pins (`make validate`, `make test`, `astral-sh/setup-uv`, matrix) stay.

## Code Examples

### Pre-push shim (installed by `devtools.hooks install`)
```bash
#!/usr/bin/env bash
# tools-installer: pre-push gate (installed by `make dev-setup`; do not edit)
if ! command -v uv >/dev/null 2>&1; then
    echo "pre-push: uv not found on PATH; install uv, or push from a shell that has it" >&2
    exit 1
fi
exec uv run python -m devtools.push_gate "$@"
```
Behaviour verified live (Experiment 4): with `uv` -> gate runs from the pushing checkout; `PATH=/usr/bin:/bin` -> message + rc 1, push aborted; without the guard, `exec: uv: not found` rc 1. The first non-shebang comment line is the marker the installer uses for idempotence and for "is this foreign?".

### Prototype signal-forwarding core (verified: p26-gate-proto.py, trial results in Pattern 3)
```python
import os, signal, subprocess, sys

child: subprocess.Popen[bytes] | None = None
interrupted = False

def forward(signum: int, _frame: object) -> None:
    global interrupted
    interrupted = True
    if child is not None:
        try:
            os.killpg(child.pid, signal.SIGINT)   # pre-commit restores its stash on SIGINT only
        except ProcessLookupError:
            pass

for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, forward)

child = subprocess.Popen(argv, process_group=0)   # Python 3.11+; own group => hooks share it
rc = child.wait()                                  # git does not return until we exit
sys.exit(rc if rc != 0 else (130 if interrupted else 0))   # a signalled gate never exits 0
```
Production code should set `child` under a guard that closes the tiny window between `Popen` returning and the assignment (block signals with `signal.pthread_sigmask` around the spawn), and map "signalled" to a non-zero exit even when pre-commit returned 0.

### Hooks config shape (D-03/D-05; entries and ids from the current file)
```yaml
default_install_hook_types: [pre-commit]
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: make lint
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit, pre-push]
      # ruff-format, pyright, bandit, vulture, shellcheck likewise (make format-check|typecheck|security|dead-code|shellcheck)
      - id: tests
        name: make test
        entry: make test
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]          # last in the file
```
[VERIFIED live, Experiment 8]: a hook with no `stages` also runs at `--hook-stage pre-push` (so explicit `stages` is for clarity and the pin test); `pre-commit run --all-files` (default stage) runs the `pre-commit` and no-`stages` hooks and skips the `pre-push`-only hook, so `make validate` never runs `make test`; `--fail-fast` stops after the first failing hook (CLI flag exists: `pre-commit run --help`, `run.py:301`). The gate should pass `--fail-fast` for push only; do not set top-level `fail_fast: true` (it would also stop commit-stage reporting at the first failure).

### Makefile shape (thin recipes; existing text preserved)
```make
.PHONY: help dev-setup build run doctor fix uninstall lint format-check typecheck security dead-code shellcheck validate test e2e hooks-e2e verify-registry audit-catalog

dev-setup:  ## Create .venv, install deps (uv), install the commit hook and the push gate
	uv sync
	uv run python -m devtools.hooks install

run:  ## Launch the setup wizard (pass flags via ARGS, e.g. ARGS="--all --yes")
	uv run --isolated --no-dev setup.py $(ARGS)

lint:  ## ruff check
	uv run ruff check installer tests devtools setup.py
format-check:  ## ruff format --check
	uv run ruff format --check installer tests devtools setup.py
typecheck:  ## pyright (strict)
	uv run pyright
security:  ## bandit
	# B404/B603 (subprocess) and B310 (urlopen) are inherent to this installer; ... (keep the existing comment)
	uv run bandit -q -r installer devtools --skip B404,B603,B310
dead-code:  ## vulture
	uv run vulture
shellcheck:  ## shellcheck (install.sh, scripts)
	uv run shellcheck -x install.sh scripts/lib/prune-tmp-common.sh scripts/prune-tmp-linux.sh scripts/prune-user-tmpdir.sh scripts/container-e2e-verify.sh scripts/hooks-e2e.sh
validate:  ## Run every commit-stage gate through pre-commit
	uv run pre-commit run --all-files
```
Values above (bandit skips `B404,B603,B310`, the shellcheck file list, the six ruff/pyright/vulture commands) are quoted from the Makefile and `.pre-commit-config.yaml` read this session; `devtools` and `hooks-e2e` are new. The `.gitignore`d `.venv` plus `[tool.hatch.build.targets.wheel] packages = ["installer"]` keep `devtools` out of the wheel. Scratch-testable `dev-setup`: the Makefile recipe is only `uv sync` plus `python -m devtools.hooks install`; the installer function takes an injected runner (`git`, `pre-commit`) and a hooks-dir path, so tests never run `uv sync`.

### Docs-only classifier (stdlib; CLI used by CI, function used by the pin test)
```python
# devtools/docs_only.py -- shortcut: only exact-lowercase ".md"; extend if a test reads .markdown
def is_docs_only(paths: list[str]) -> bool:
    if not paths:
        return False                        # empty or unknown -> run everything (fail closed)
    return all(_docs_path(p) for p in paths)
# CLI: python3 -m devtools.docs_only --base origin/main  -> prints/writes full=true|false;
# any git failure (e.g. no merge base) -> full=true.
```

### ci.yml design
```yaml
on:
  push:
    branches-ignore: [main]
  # pull_request dropped (D-09); a fork PR then gets no CI -- owner decision, see Open Questions
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
# job name stays: validate & test on ${{ matrix.os }}
steps:
  - name: Checkout
    uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - name: Classify the change
    id: scope
    run: python3 -m devtools.docs_only --base origin/main --github-output "$GITHUB_OUTPUT"
  - name: Set up uv
    uses: astral-sh/setup-uv@v5
    with: { enable-cache: true }
  - name: Install dependencies
    if: steps.scope.outputs.full == 'true'
    run: make dev-setup
  - name: Validate
    if: steps.scope.outputs.full == 'true'
    run: make validate
  - name: Test
    if: steps.scope.outputs.full == 'true'
    timeout-minutes: 20
    run: PYTEST_XDIST_AUTO_NUM_WORKERS="$(python3 -c 'import os; print(os.cpu_count() or 1)')" make test
```
Names, `timeout-minutes: 25`, matrix and the `PYTEST_XDIST_AUTO_NUM_WORKERS` line are taken from the current `ci.yml`. A skipped step leaves the job `success` [ASSUMED for steps; CITED for jobs]. `make dev-setup` in CI also installs the hooks into the CI checkout, which is harmless; its pre-push shim is never triggered there. `concurrency` group `ci-refs/heads/<branch>` cancels a superseded run on the same branch; the cancelled SHA gets no green checks and cannot land, which is the intended result (SPEC edge table). `fetch-depth: 0` fetches all branches so `origin/main` exists [ASSUMED: actions/checkout behaviour; the classifier should `git fetch --no-tags origin main` itself if the ref is missing].

### GitHub commands (research focus 6)
Endpoints [CITED: docs.github.com/en/rest/branches/branch-protection]: `POST|DELETE|GET /repos/{owner}/{repo}/branches/{branch}/protection/enforce_admins`; `PATCH /repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks` with `strict` (boolean) and `checks` (array of `{context, app_id?}`; `contexts` is deprecated: "Use checks instead of contexts for more fine-grained control"); `GET /repos/{owner}/{repo}/branches/{branch}/protection`. The current state read back by GET today: `enforce_admins: false`, `strict: false`, `checks` with both contexts and `app_id: null`, `required_pull_request_reviews: null`, no push restrictions, no rulesets (`gh api repos/castocolina/tools-installer/rulesets --jq length` -> `0`) [VERIFIED].
```bash
# strict on (PATCH needs JSON body; --input - is documented in `gh api --help`)
gh api -X PATCH repos/castocolina/tools-installer/branches/main/protection/required_status_checks --input - <<'JSON'
{"strict": true, "checks": [{"context": "validate & test on ubuntu-latest"}, {"context": "validate & test on macos-latest"}]}
JSON
# enforce_admins ON (apply last, D-10)
gh api -X POST   repos/castocolina/tools-installer/branches/main/protection/enforce_admins
# CI-outage escape hatch: OFF, push, then ON again and read back (P6)
gh api -X DELETE repos/castocolina/tools-installer/branches/main/protection/enforce_admins
gh api -X POST   repos/castocolina/tools-installer/branches/main/protection/enforce_admins
# read-back
gh api repos/castocolina/tools-installer/branches/main/protection --jq '{enforce_admins: .enforce_admins.enabled, strict: .required_status_checks.strict, checks: [.required_status_checks.checks[].context]}'
```
None of the mutating commands were run (no mutating calls permitted); their syntax is from the REST docs and `gh api --help`. **Direct fast-forward of a green SHA:** GitHub's "About protected branches" says required checks must pass "before collaborators can merge changes", and describes the two ways commits reach the branch: "any commits must either be pushed to another branch and then merged or pushed directly to the protected branch" [CITED: docs.github.com about-protected-branches]. Strict mode is defined as "The branch must be up to date with the base branch before merging." A `git push origin <branch>:main` of a SHA whose parent is the current `main` tip satisfies "up to date"; no PR or review is required here (`required_pull_request_reviews: null`). The page does not explicitly state the direct-push + strict + `enforce_admins` combination, and it cannot be proven without a mutating call, so the final proof stays the phase's own last push (SPEC R5 acceptance).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `contexts` list in required status checks | `checks` objects (`context`, `app_id`) | GitHub REST (contexts marked deprecated in docs) | Send `checks` in the PATCH |
| `commit` / `push` stage names in pre-commit | `pre-commit` / `pre-push` | pre-commit 3.2 | Config validation warns on legacy names; use the new ones |

**Deprecated/outdated:** `stages: [commit]` (use `pre-commit`) [VERIFIED: `clientlib.py` legacy-stage warnings, lines 95-182].

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The flaky test's cause is `before = service.passes` being captured while a refresh from opening the Doctor view is still queued, so `_wait_for_passes` is satisfied by that stale pass before the reinstall completes and the body is read too early | Flaky test (D-12) | Fix targets the wrong wait; the 50-run proof would still fail |
| A2 | A direct `git push origin <branch>:main` of an already-green SHA is accepted with strict + `enforce_admins` on | GitHub commands | Phase cannot land its last change; fall back to a PR merge or temporary off-switch |
| A3 | Step-level `if:` skips leave the matrix job green with the required context names intact | ci.yml design | Docs-only pushes block on a Pending/mis-named check |
| A4 | `actions/checkout` with `fetch-depth: 0` provides `origin/main` on a branch push | ci.yml design | Classifier falls back to full run (fail closed), losing the fast pass only |
| A5 | Dropping `pull_request` is acceptable for outside contributors | ci.yml design | A fork PR gets no CI |
| A6 | Refusing (not chaining) a foreign `pre-push` file is the right install behaviour | Pattern 4 | Owner may prefer `.legacy` chaining |
| A7 | A lone SIGTERM to `git` cannot be handled and is acceptable residual risk | Pattern 3 | P2 wording needs an owner-visible carve-out |
| A8 | Adding `devtools` to bandit is wanted (D-02 lists ruff, pyright, coverage, vulture only) | Project structure | Extra B607 findings to fix, or scope creep |

## Open Questions

1. **Flaky test root cause (D-12).**
   - What we know: the test waits via `settle` then `_wait_for_passes(before + 1)`; `on_globals_reinstalled` updates the body, then posts `RefreshRequested` (`installer/doctor_screen.py:768-782`), so the body is current once the reinstall's own pass has landed; the assertions then read `_doctor_text(app)` without waiting for the body text. Not reproduced: 8 runs of the whole file under `-n auto`, 12 runs of a doctor/reinstall/invalidate subset with 14 CPU burners, and 150 + 500 repetitions of the target test (`mapped` parameters) with `-n 10`/`-n 20` and 16/24 burners all passed (0 failures). The todo says it failed twice under full-suite load.
   - What's unclear: the exact interleaving; it needs the full suite's load or a different race window.
   - Recommendation: replace the read-after-pause with `await wait_until(pilot, lambda: _INVALIDATE_FAILED.format(error=shown) in str(_doctor_text(app)))` and wait on `not app.mutation_in_flight` before the body assertions, and capture `before` after the Doctor view's own pass has landed (`_wait_for_passes` right after `_open_view`). Then run the required 50 runs of the full file under `-n auto` before and after, plus the full suite once, because a file-only loop did not reproduce.
2. **Owner decision: how to meet "scratch git repo" acceptance given the sandbox.** Recommendation: fake-runner unit tests in `make test` plus `scripts/hooks-e2e.sh` (make target `hooks-e2e`, run in CI on ubuntu and macOS, not in the push gate). Needs the owner to accept that the SPEC's "test" wording for R2/R3/R4/P2 is satisfied by the e2e script.
3. **Fork PRs (D-09 discretion).** Dropping `pull_request` leaves outside contributors without CI; keeping it duplicates runs for same-repo branches. Recommendation: drop, and record in the git-workflow doc.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all make targets, shim | ✓ | 0.11.28 | — |
| git | gate, e2e script | ✓ | 2.56.0 | — (needs 2.31+ for `--path-format=absolute`) |
| GNU make | gates | ✓ | `/usr/bin/make` | — |
| pre-commit | hooks | ✓ | 4.6.0 (`.venv`) | — |
| gh | branch-protection commands (owner-run) | ✓ | 2.101.0 | — |
| shellcheck | `make shellcheck` incl. new e2e script | ✓ | `/home/linuxbrew/.linuxbrew/bin/shellcheck` (and `shellcheck-py` in dev deps) | — |
| network for `uv sync` | first push from a fresh worktree | ✓ here | — | — |

**Missing dependencies with no fallback:** none.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8 + pytest-xdist + pytest-asyncio, coverage `fail_under = 90`, `source = ["installer"]` (add `devtools`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`) |
| Quick run command | `uv run pytest --no-cov -n auto tests/test_push_gate.py tests/test_hooks_install.py tests/test_docs_only.py tests/test_hook_wiring.py tests/test_makefile.py tests/test_ci_workflow.py tests/test_docs.py` |
| Full suite command | `make test` (62.3 s measured) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HOOK-01 | each commit-stage hook entry is `make <target>` for an existing target; each gate target except `test` has a commit hook; `validate` recipe is exactly `uv run pre-commit run --all-files`; no commit-stage hook runs `make test`; P3 (no `--fix`, no bare `ruff format`) via entry -> recipe; zero-check guard | unit (text parse) | `uv run pytest --no-cov tests/test_hook_wiring.py` | ❌ Wave 0 |
| HOOK-02 | pre-push entries and order (static hooks have `pre-push` stage, `tests` hook push-only and last, all `always_run`, `pass_filenames: false`); P1 grep | unit | `uv run pytest --no-cov tests/test_hook_wiring.py` | ❌ Wave 0 |
| HOOK-02/03 (behaviour) | red suite aborts push and ref unmoved; green moves; refusals (staged, untracked `.py`, not-HEAD, deletion-only, root push stash, unstaged config, unmerged); sorted names, name with space; byte-identical restore after pass/fail/SIGINT/SIGTERM/SIGHUP | fake-runner unit + Python-child signal test; real behaviour in e2e script | `uv run pytest --no-cov tests/test_push_gate.py` and `make hooks-e2e` | ❌ Wave 0 |
| HOOK-03 (stdin parse) | zero sha, `(delete)`, tag object, multi-ref, empty stdin | unit | `uv run pytest --no-cov tests/test_push_gate.py` | ❌ Wave 0 |
| HOOK-04 | `dev-setup` recipe pin; `default_install_hook_types: [pre-commit]`; installer idempotent bytes; not-a-repo skip exit 0; `core.hooksPath` exit non-zero naming it; foreign pre-push refused; worktree uses common dir; `install`/`setup` targets absent, `run` has the launch recipe | unit (fake runner) + text parse; real git in e2e script | `uv run pytest --no-cov tests/test_hooks_install.py tests/test_makefile.py` | ❌ Wave 0 / extend existing |
| HOOK-04 (rename) | every product hint and doc now says `make run` | existing tests after edits | `uv run pytest --no-cov tests/test_guidance.py tests/test_wizard_app.py tests/test_app.py tests/test_render.py tests/test_schedules_handover.py tests/test_catalog_audit_skill.py` | ✅ edit |
| HOOK-05 | ci.yml triggers (`branches-ignore: [main]`), job name and context strings byte-identical, step `if:` gating, `fetch-depth: 0`; docs-only matrix (`.planning/` only fast; `.py`, `ci.yml`, test-read `.md`, rename of a `.py` into `.planning/`, path with space) ; Markdown-read drift detector (AST scan of tests for `.md` string literals/globs resolved against the repo) | unit | `uv run pytest --no-cov tests/test_docs_only.py tests/test_ci_workflow.py` | ❌ Wave 0 / extend |
| HOOK-05 (GitHub) | read-back `enforce_admins.enabled: true`, `strict: true`, both contexts | manual (owner) `gh api` GET | command in git-workflow doc | manual-only: needs the real repo, a mutating call precedes it |
| HOOK-06 | doc table, flow, off/on/read-back commands present; no `runs? pre-commit hooks` claim | unit (grep over AGENTS.md, `.claude/*.md`) + existing `tests/test_docs.py` | `uv run pytest --no-cov tests/test_docs.py tests/test_hook_wiring.py` | ✅ / ❌ Wave 0 |
| D-12 | flaky test stable | 50 runs under `-n auto` before/after | shell loop (no repeat plugin in dev deps: `pytest-repeat`, `pytest-flaky` absent [VERIFIED: site-packages listing]) | ✅ |

### Sampling Rate
- **Per task commit:** the quick run command above (add the file(s) touched).
- **Per wave merge:** `make validate && make test`.
- **Phase gate:** full suite green plus `make hooks-e2e` before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_push_gate.py` — HOOK-02/03 behaviour with a fake runner and a `sys.executable` child with fake `git`/`pre-commit` under `tmp_path`
- [ ] `tests/test_hooks_install.py` — HOOK-04 installer
- [ ] `tests/test_docs_only.py` — HOOK-05 rule and drift detector
- [ ] `tests/test_hook_wiring.py` — HOOK-01/02, P1, P3, docs claims
- [ ] `scripts/hooks-e2e.sh` + `make hooks-e2e` — real git/pre-commit scratch repos (`env -i`), added to the shellcheck list
- [ ] extend `tests/test_makefile.py` (new targets, absent `install`/`setup`, `run` recipe, single-line `.PHONY`) and `tests/test_ci_workflow.py` (triggers)
- [ ] `devtools` added to pyright `include`, coverage `source`, vulture `paths`, ruff paths

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | yes | Branch protection with `enforce_admins` so no actor bypasses the CI gate; documented manual toggle only |
| V5 Input Validation | yes | Ref names and file names from git are untrusted data: parse with `-z`, never `shell=True`, never interpolate into a shell string |
| V6 Cryptography | no | — |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Hook bypass (`--no-verify`, `SKIP=`) | Tampering | Server-side gate on `main`; P1 grep test forbids encouraging it |
| Shell injection through a file or ref name | Tampering | argv lists, `-z`, `shlex`-free subprocess calls (bandit B602/B603 posture as in `installer/`) |
| Data loss on interrupt (stash not restored) | Denial/Tampering | gate forwards signals; recovery doc for `patch*` file |
| Test touching the real `.git` via inherited `GIT_*` | Tampering | `env -i` allowlist in the e2e script; pytest never launches git |
| Token or credential prompt hang in hooks | Denial | `GIT_TERMINAL_PROMPT=0` in the e2e script |

## Sources

### Primary (HIGH confidence)
- `.venv/lib/python3.12/site-packages/pre_commit/` (4.6.0): `commands/run.py:325-421`, `commands/hook_impl.py:100-174`, `git.py:27-48,86-93,158-182`, `commands/install_uninstall.py:20-128`, `staged_files_only.py`, `resources/hook-tmpl`, `clientlib.py` — read this session
- Live experiments in `/tmp/claude-1000/.../scratchpad/p26-research/` (deleted afterwards): git 2.56.0, pre-commit 4.6.0, `uv 0.11.28`
- Repo files read: `Makefile`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `pyproject.toml`, `tests/sandbox.py`, `tests/conftest.py`, `tests/child_guard/sitecustomize.py`, `tests/test_makefile.py`, `tests/test_ci_workflow.py`, `tests/test_docs.py`, `tests/test_screen_family.py:2686-2830`, `installer/doctor_screen.py:405-455,625-782`, `AGENTS.md`, `.claude/dev-environment.md`, `.claude/git-workflow.md`, `.claude/testing.md`, `.claude/python-tooling.md`
- `gh api repos/castocolina/tools-installer/branches/main/protection` and `/enforce_admins`, `/rulesets` (read-only GETs)
- `gh api --help` (local)

### Secondary (MEDIUM confidence)
- docs.github.com REST branch protection page (endpoints and parameters) [CITED: https://docs.github.com/en/rest/branches/branch-protection]
- docs.github.com about protected branches (required checks, strict, enforce admins, "pushed directly to the protected branch") [CITED: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches]
- docs.github.com troubleshooting required status checks (path/branch-filtered workflows stay Pending; job skipped by conditional reports Success) [CITED: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks]
- docs.github.com events that trigger workflows (`branches-ignore`, `GITHUB_SHA` = tip commit pushed) [CITED: https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows]

### Tertiary (LOW confidence)
- none beyond the `[ASSUMED]` items in the Assumptions Log

## Contradictions with SPEC/CONTEXT

The planner should add dated amendments; SPEC.md and CONTEXT.md were not modified.

1. **Sandbox vs scratch-repo tests (SPEC R2/R3/R4 acceptance, P2/P5; CONTEXT `code_context` "scratch-repo hook tests build their git repos inside [the sandbox]").** `tests/sandbox.py` refuses real `git`, `make`, `uv`, host `pre-commit` (probe output in Pitfall 1). Pytest cannot run real scratch-repo tests. Evidence: `FORBIDDEN_PROGRAM_NAMES` lists `"uv"`, `"git"`, `"gh"`; `check_launch` step 5 refuses any non-allowlisted host program. Proposed amendment: acceptance via fake-runner/fake-tool pytest tests plus `scripts/hooks-e2e.sh` (real tools, `env -i`).
2. **SPEC R5 / D-11 "every path under `.planning/` is docs-only"** conflicts with P4: `tests/test_catalog_audit_skill.py:251,401` read `.planning/phases/24.3-catalog-audit-skill/24.3-SKILLJUDGE-*.md` (3 tracked files). Proposed: `.planning/` is docs-only except test-read files, pinned by the drift test. Also, tests read far more Markdown than SPEC assumes: `AGENTS.md`, `README.md`, `.claude/{architecture,dev-environment,git-workflow,python-tooling,testing}.md`, `.claude/skills/{tool-onboarding,catalog-audit}/SKILL.md`, `.claude/skills/catalog-audit/references/*.md`, every `docs/**/*.md` (`tests/test_docs.py:17-29`, `:418-419`; `tests/test_postinstall.py:608`; `tests/test_catalog_audit_skill.py:16-17,73,82`). In practice the fast pass covers `.planning/` (minus the three files) and stray Markdown only.
3. **SPEC P2 "interrupted" restore.** pre-commit restores only on SIGINT. SIGTERM, SIGHUP, SIGKILL leave edits in `PRE_COMMIT_HOME/patch*` (Pattern 3). Amend P2: interrupt = SIGINT/SIGTERM/SIGHUP delivered to the gate's process group, handled by forwarding; SIGKILL and a lone SIGTERM to `git` are documented residual cases with a recovery command.
4. **SPEC R3 / D-01 refusal list is incomplete.** pre-commit refuses (rc 1) on an unstaged `.pre-commit-config.yaml` and on unmerged paths when the stash is on (`run.py:347-358`); the gate needs two more refusals with correct advice (commit or discard the config edit; finish or abort the merge).
5. **D-08 rename list is incomplete:** add `tests/test_render.py:370`, `.claude/dev-environment.md:30,32`, `.claude/skills/catalog-audit/SKILL.md:189` (pinned by `tests/test_catalog_audit_skill.py:140`), `docs/PUBLISHING.md:30-31` and `README.md:368` (CI description), and `.claude/python-tooling.md` ("`make validate` (and pre-commit)"). `setup.py:3` and comments at `installer/compose.py:798`, `tests/test_setup.py:1074` also name `make setup`.
6. **D-09 vs `tests/test_ci_workflow.py`:** the existing test asserts `pull_request` is a trigger; it must be rewritten with the trigger change.
7. **D-07 worktree behaviour:** `pre-commit install` bakes the installing interpreter's absolute path into the shared hook (Pitfall 3). CONTEXT's "so worktrees share it" is true for the hook file but the file then depends on the installing checkout's `.venv`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new packages, CLI flags verified live
- Architecture: HIGH for pre-commit/git behaviour (live), MEDIUM for GitHub direct-push combination (documented sentence only)
- Pitfalls: HIGH for sandbox, signals, env leakage, rename diff; MEDIUM for the flaky-test cause (not reproduced)

**Research date:** 2026-11-16
**Valid until:** 2026-12-16 (pre-commit 4.x and GitHub REST are stable; re-check if pre-commit is bumped)
