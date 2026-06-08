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

| Target           | Does                                                            |
| ---------------- | -------------------------------------------------------------- |
| `make install`   | `uv sync` (creates `.venv`, installs runtime + dev deps)        |
| `make build`     | build the distributable                                         |
| `make run`       | `uv run setup.py` (launch the wizard)                           |
| `make uninstall` | remove installed artifacts / symlinks                          |
| `make validate`  | run pre-commit hooks: `ruff check`, `ruff format --check`, `pyright`, `bandit`, `vulture` |
| `make test`      | `uv run pytest` with coverage (`--cov`, `--cov-fail-under`)     |

- Keep targets thin: a target wraps a uv/tool command, it does not reimplement logic.
- `make validate` and `make test` must be runnable locally and in CI identically.

### Pre-commit
- Pre-commit hooks mirror `make validate` so issues are caught before a commit exists.
- Hooks are config (`.pre-commit-config.yaml`); never auto-fix-and-commit silently in a
  way that hides a failing gate from the user.
