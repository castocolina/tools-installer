# tools-installer

Interactive cross-platform installer (macOS / Linux) for an AI dev environment.
Python, managed with **uv**. See [PRD](docs/prds/ai-dev-tools-installer-v1.0-prd.md).

## Toolchain & commands

- **uv** owns the environment: Python version, `.venv`, and all dependencies.
  Never use `pip`, `poetry`, `conda`, or a hand-rolled venv.
- `make install`   — create `.venv` (uv), install runtime + dev dependencies
- `make build`     — build the distributable
- `make setup`     — launch the wizard (`uv run setup.py`; pass flags via `ARGS="…"`)
- `make doctor`    — audit PATH and wire `~/.myshellrc` + shell rc files
- `make run`       — alias for `make setup`
- `make uninstall` — remove installed artifacts
- `make validate`  — run pre-commit hooks (lint, format check, types, security, dead code)
- `make test`      — `pytest` with coverage

## Non-negotiable rules

- **English only.** Every response, identifier, comment, docstring, log line, and
  commit message is in English — no matter what language the request is written in.
- **Never bypass a quality gate.** Fix the root cause; never silence a check to make
  it pass. Details: [Python Tooling](.claude/python-tooling.md), [Testing](.claude/testing.md).
- **Coherent commits.** Do not pile up "fix review comment" commits. Amend or squash
  so each commit is one self-contained, valid change. See [Git Workflow](.claude/git-workflow.md).
- **Validate before you commit.** `make validate && make test` must pass on the exact
  tree you are about to commit.

## Detailed rules

- [Python Tooling](.claude/python-tooling.md) — ruff, pyright, bandit, vulture, formatting
- [Testing](.claude/testing.md) — pytest, coverage, what "done" means
- [Git Workflow](.claude/git-workflow.md) — commits and the review cycle
- [Dev Environment](.claude/dev-environment.md) — uv, pyproject.toml, Makefile, pre-commit
