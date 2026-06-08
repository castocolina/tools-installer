# Python Tooling Guidelines

## Overview

The project enforces quality with a fixed set of tools, all configured in
`pyproject.toml` and run through `make validate` (and pre-commit). These apply to
every change to Python code.

| Tool          | Purpose                          | Run via            |
| ------------- | -------------------------------- | ------------------ |
| `ruff check`  | Linting (pyflakes, pycodestyle, isort, bugbear, …) | `make validate` |
| `ruff format` | Code formatting (Black-compatible) | `make validate`  |
| `pyright`     | Static type checking (strict)    | `make validate`   |
| `bandit`      | Security static analysis         | `make validate`   |
| `vulture`     | Dead-code detection              | `make validate`   |

> `ruff format` is the only formatter. Do not add `black` — it duplicates `ruff format`.

## Rules

### Never bypass a finding
- Do **not** add `# noqa`, `# type: ignore`, `# nosec`, or a vulture whitelist entry
  to make a check pass. Fix the underlying code instead.
- A suppression is allowed **only** when the finding is a genuine false positive.
  When that happens it must be: (a) the narrowest possible scope (specific rule code,
  e.g. `# noqa: E501`, never bare `# noqa`), (b) accompanied by a one-line comment
  explaining *why* it is a false positive, and (c) called out to the user for approval
  before committing.
- Do not relax tool configuration (disable a rule, lower pyright to `basic`, exclude a
  path) to dodge a finding. Config changes are their own deliberate decision, not a
  workaround for a specific error.

### Types
- pyright runs in **strict** mode. New code must be fully typed — no implicit `Any`.
- Prefer precise types over `Any`; if a third-party stub is missing, type the boundary
  explicitly rather than blanket-ignoring the module.

### Formatting & imports
- Formatting is not a matter of taste here: run `ruff format`; never hand-format to
  fight the formatter.
- Import ordering is handled by ruff's isort rules — let the tool sort them.

### Security & dead code
- bandit findings are real until proven otherwise (e.g. `subprocess` calls — validate
  inputs, avoid `shell=True` with interpolated user data).
- vulture flags unused code: delete it rather than commenting it out. If it is a
  deliberate public API kept for later, document why.

## Examples

### Avoid
```python
result = subprocess.run(cmd, shell=True)  # nosec  <- silencing, not fixing
value = data["k"]  # type: ignore          <- hides a real typing gap
```

### Good
```python
result = subprocess.run(shlex.split(cmd), check=True)  # no shell, validated args
value: str = data["k"]                                  # typed access
```
