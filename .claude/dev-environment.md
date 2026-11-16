# Dev Environment Guidelines

## Overview

The environment is reproducible through **uv** + **pyproject.toml** + a **Makefile**.
`pyproject.toml` is the single home for both dependencies and tool configuration.

## Rules

### uv owns everything
- uv manages the Python interpreter, the `.venv`, and all dependencies. Never call
  `pip`, `poetry`, `conda`, `virtualenv`, or `python -m venv` directly.
- Common operations:
  - `uv sync` — create/update `.venv` from `pyproject.toml` + `uv.lock`
  - `uv add <pkg>` / `uv add --dev <pkg>` — add a runtime / dev dependency (updates the lock)
  - `uv run <cmd>` — run inside the managed environment
- `uv.lock` is committed. Dependency changes go through `uv add`/`uv remove`, never by
  hand-editing the lock.

### pyproject.toml is the single config source
- All tool config lives under `[tool.*]`: `ruff`, `pyright`, `pytest`, `coverage`,
  `bandit`, `vulture`. Do not scatter `.ruff.toml`, `pytest.ini`, `setup.cfg`, etc.
- Pin the Python version (`requires-python`) and keep dev tools in a dev dependency group.

### Makefile is the task interface
Every workflow has a target so humans and CI run the same thing:

| Target              | Does                                                            |
| ------------------- | --------------------------------------------------------------- |
| `make dev-setup`    | `uv sync`, then the commit hook and the push gate (`python -m devtools.hooks install`); run it from the main checkout |
| `make build`        | build the distributable                                         |
| `make run`          | `uv run --isolated --no-dev setup.py` (launch the wizard, isolated, without dev dependencies, so the installer sees your real tools (dev ruff never shadows yours)) |
| `make doctor`       | audit & fix `PATH` (`uv run --isolated --no-dev setup.py --doctor`) |
| `make uninstall`    | remove installed artifacts / symlinks                           |
| `make lint`         | ruff check (`uv run ruff check installer tests devtools setup.py`) |
| `make format-check` | ruff format --check (no rewrite)                                |
| `make typecheck`    | pyright (strict)                                                |
| `make security`     | bandit                                                          |
| `make dead-code`    | vulture                                                         |
| `make shellcheck`   | shellcheck `install.sh` plus exactly `scripts/lib/prune-tmp-common.sh`, `scripts/prune-tmp-linux.sh`, `scripts/prune-user-tmpdir.sh`, `scripts/container-e2e-verify.sh`, `scripts/hooks-e2e.sh` (not all of `scripts/`) |
| `make validate`     | run every commit-stage gate through `pre-commit run --all-files` |
| `make test`         | `uv run pytest -n auto` (parallel, xdist) with coverage (`--cov`, `--cov-fail-under`) |
| `make hooks-e2e`    | prove the commit hook and the push gate with real git in scratch repos |

- Keep targets thin: a target wraps a uv/tool command, it does not reimplement logic.
- `make validate` and `make test` must be runnable locally and in CI identically.

### Pre-commit

Each commit-stage hook calls its own make target; `make validate` runs them all through
`pre-commit run --all-files`. No hook auto-fixes files: a failed gate is fixed and re-run,
never silently rewritten. Run `make dev-setup` from the main checkout — a worktree install
rewrites the shared hooks with that worktree's Python (agents never run it, except at an
owner-assigned final checkpoint). A first push from a fresh worktree lets `uv run` create
that worktree's `.venv`. `make hooks-e2e` proves both hooks with real git in scratch repos;
CI runs it too.

The push gate is `devtools/push_gate.py`, installed by `make dev-setup` as `pre-push` in the
shared hooks directory. It refuses, before running any gate:

1. unmerged paths — finish or abort the merge;
2. staged changes that are not committed, intent-to-add files (`git add -N`), and files on disk
   flagged skip-worktree or assume-unchanged (`git update-index --no-skip-worktree` or
   `--no-assume-unchanged` clears them);
3. untracked, non-ignored files outside `.planning/`, plus every gate-read file of
   `GATE_READ_PATHSPECS` (the config and plugin files the gates load, and Python sources under
   `installer/`, `tests/` and `devtools/`) even when git ignores it — commit a gate-read file
   or move it out of the repository; `.git/info/exclude` is only for a local-only file that no
   gate reads;
4. an unstaged edit to `.pre-commit-config.yaml`;
5. a pushed commit that is not HEAD.

It then runs `pre-commit run --hook-stage pre-push --fail-fast --from-ref HEAD --to-ref HEAD`.
pre-commit sets unstaged edits aside and restores them after a pass, a failure, Ctrl-C, a
closed terminal or a group SIGTERM.

#### Recover unstaged edits

For the residual cases (SIGKILL, or a SIGTERM sent only to `git`), run the first two lines of
the block below, compare the printed name with the push output's `Stashing unstaged files to …`
line, then run the third line. If the names differ, set `patch` to the file the push output
named before running the third:

```sh
patch=$(ls -t "${PRE_COMMIT_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/pre-commit}"/patch* | head -n 1)
printf '%s\n' "$patch"
less "$patch" && git apply --check "$patch" && git apply "$patch"
```

If the dry run fails, nothing was applied; apply the file the push output named instead.

## Quality gates by stage

Each gate has its own target. The commit stage runs the six static gates; a push runs them
again, then the full test suite, on a tree equal to the pushed commit.

| Gate                | Target              | Stage        |
| ------------------- | ------------------- | ------------ |
| ruff check          | `make lint`         | commit, push |
| ruff format --check | `make format-check` | commit, push |
| pyright             | `make typecheck`    | commit, push |
| bandit              | `make security`     | commit, push |
| vulture             | `make dead-code`    | commit, push |
| shellcheck          | `make shellcheck`   | commit, push |
| pytest + coverage   | `make test`         | push         |

When a gate fails, fix it and re-run its own target (`make typecheck`, and so on);
`make validate` verifies a whole plan or phase.

| Stage | Runs                                                    | Time                         |
| ----- | ------------------------------------------------------- | ---------------------------- |
| commit | the six static gates                                   | about 13.0 s                 |
| push  | the six gates with `--fail-fast`, then `make test`      | about 91 s (13.0 s + 78.1 s) |
| CI    | full job on ubuntu-latest, including Classify and Hook e2e | 252 s                        |
| CI    | full job on macos-latest, including Classify and Hook e2e  | 524 s                        |
| CI    | docs-only fast pass: both check names; install, validate, test and hook e2e skip | unavailable (not yet measured) |

All wall times measured 2026-11-16 on this 24-thread host; `make test` uses the project's
~40% thread cap. The CI figures are the job wall times of the current-workflow full run
43922254257, read with `gh` on 2026-11-16. A figure `gh` cannot read is written `unavailable`,
never derived from a workflow comment.
