# tools-installer

Interactive cross-platform installer (macOS / Linux) for an AI dev environment.
Python, managed with **uv**. See [PRD](docs/prds/ai-dev-tools-installer-v1.0-prd.md).

## Toolchain & commands

- **uv** owns the environment: Python version, `.venv`, and all dependencies.
  Never use `pip`, `poetry`, `conda`, or a hand-rolled venv.
- `make dev-setup` — create `.venv` (uv), install runtime + dev dependencies, then the commit hook and the push gate
- `make build`     — build the distributable
- `make run`       — launch the wizard (`uv run --isolated --no-dev setup.py`; pass flags via `ARGS="…"`)
- `make doctor`    — audit PATH (a report; like every launch it first repairs installer-owned
  leftovers: it removes legacy alias blocks and the retired pip/npm guard shims and alias block)
- `make fix`       — wire `~/.myshellrc` + shell rc files into your PATH
- `make uninstall` — remove installed artifacts
- `make verify-registry` — check registry pins against upstream (read-only; pass `ARGS="--write"` to bump)
- `make audit-catalog` — the catalog-audit skill's fact gatherer and report writer (read-only facts; writes only `.planning/audits/catalog/<date>/`; pass the subcommand via `ARGS="…"`)
- `make validate`  — run every commit-stage gate through `pre-commit run --all-files` (verify a whole plan or phase)
- `make test`      — `pytest -n auto` with coverage, capped at ~40% of the host's threads (see [Testing](.claude/testing.md))
- `make hooks-e2e` — prove the commit hook and the push gate with real git in scratch repos

### Gates

| Gate                | Target              | Stage        |
| ------------------- | ------------------- | ------------ |
| ruff check          | `make lint`         | commit, push |
| ruff format --check | `make format-check` | commit, push |
| pyright             | `make typecheck`    | commit, push |
| bandit              | `make security`     | commit, push |
| vulture             | `make dead-code`    | commit, push |
| shellcheck          | `make shellcheck`   | commit, push |
| pytest + coverage   | `make test`         | push         |

When a gate fails, fix it and re-run its own target.

## Non-negotiable rules

- **English only.** Every response, identifier, comment, docstring, log line, and
  commit message is in English — no matter what language the request is written in.
- **Never bypass a quality gate.** Fix the root cause; never silence a check to make
  it pass, and never skip a git hook. Details: [Python Tooling](.claude/python-tooling.md), [Testing](.claude/testing.md).
- **Coherent commits.** Do not pile up "fix review comment" commits. Amend or squash
  so each commit is one self-contained, valid change. See [Git Workflow](.claude/git-workflow.md).
- **Changes reach `main` by branch push, green CI, fast-forward** ([Git Workflow](.claude/git-workflow.md)).
- **The hooks are the gate; test what you changed.** The commit hook runs the six static
  gates on every commit (the set `make validate` runs) and every worktree shares it, so
  never run `make validate` or a single static gate by hand per commit, and never chain
  `make validate && make test` at a commit. While working, run only the tests that cover
  your edit: find the edited files, then the test file named for each module, the tests
  that import it and the tests that read an edited non-Python file (find them with `rg -l '<file name>' tests/`), and run `uv run pytest <those files> --no-cov -q`. After a plan, run
  `make validate` and `make test` once each: tests otherwise run only at the push gate,
  and a run that will not push soon (an autonomous run) must not leave a red suite for it.
  Editing only plans or Markdown that no test reads needs none of this. Run a gate by hand
  also to diagnose a failure, or in a checkout that has no hooks yet. Never bypass a hook.
- **Never mutate the developer's host.** Do not run `make run`, `make fix`,
  `make uninstall`, `make doctor`, or mutating `systemctl --user` commands, on the
  real machine (every launch route, doctor included, may rewrite the real
  `~/.myshellrc` and delete leftover guard shims in `~/.local/bin`), and
  never edit the real shell rc or agent settings. Tests use a scratch `HOME`; real
  installs and removals run only in disposable containers
  (`scripts/detect-container-runtime.sh`), which are removed afterwards.
- **Agents never run `make dev-setup`.** It rewrites the git hooks every worktree shares; the
  developer runs it once from the main checkout. The one exception is the
  final owner-assigned checkpoint of a phase plan that lists the real install explicitly.
- **Zero sudo.** No code path runs `sudo`, `pkexec` or `doas`; anything that needs
  root is handed off as the exact command for the user to run.

## Detailed rules

- [Architecture](.claude/architecture.md) — one view registry, one nav path, one apply workflow, wiring-only setup.py
- [Python Tooling](.claude/python-tooling.md) — ruff, pyright, bandit, vulture, formatting
- [Testing](.claude/testing.md) — pytest, coverage, what "done" means
- [Git Workflow](.claude/git-workflow.md) — commits and the review cycle
- [Dev Environment](.claude/dev-environment.md) — uv, pyproject.toml, Makefile, pre-commit
