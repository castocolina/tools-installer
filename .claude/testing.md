# Testing Guidelines

## Overview

Tests run with `pytest` and coverage via `make test`. Configuration lives in
`pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`).

## Rules

### Never bypass a test to go green
- Do **not** use `@pytest.mark.skip`, `@pytest.mark.xfail`, `pytest.skip()`, comment
  out a test, or delete an assertion to make the suite pass. Fix the code or fix the
  test for the right reason.
- `skip`/`xfail` are allowed only for a *legitimate* reason (e.g. platform-specific
  test on the wrong OS, or an upstream bug with a tracking link) — with a `reason=`
  string. Never as a way to dodge a failure you caused.

### Coverage
- `make test` enforces a coverage floor (`--cov-fail-under` in `pyproject.toml`).
  Do **not** lower that floor to make a run pass.
- New logic ships with tests. Coverage must not drop because of your change.
- Coverage is a floor, not a goal: don't write assertion-free tests just to touch lines.

### Parallel by default
- `make test` runs `pytest -n auto` (pytest-xdist). Never drop `-n auto` to make a run pass.
- **Thread budget:** the suite uses at most ~40% of the usable threads, because this project runs on other people's machines and must not starve them. `pytest_xdist_auto_num_workers` in `tests/conftest.py` computes `max(1, round(threads * 0.4))`: 24 → 10, 8 → 3, 3 → 1. Never pass a fixed or higher `-n`. `PYTEST_XDIST_AUTO_NUM_WORKERS` may lower it for one run.
- Every test must be xdist-safe. That means:
  - no fixed shared path (use `tmp_path`; an artifact dir needs a per-test file name and `mkdir(exist_ok=True)`);
  - no process-global state left behind (use `monkeypatch` for env, cwd and HOME);
  - no fixed port or socket name;
  - no reliance on another test's order or side effects.
- A test that passes serially but fails under `-n auto` is a bug in the test. Fix its isolation. Use `@pytest.mark.xdist_group` (with `--dist loadgroup`) only for a genuinely exclusive resource, with a one-line reason.

### What to test
- The decision logic, not the third-party tools: parsing of `registry.toml`, the
  install **priority ladder** resolution, OS/immutable detection (mock the platform
  probes), and `~/.myshellrc` idempotency (writing twice yields no duplicate entries).
- Tests must be deterministic and offline: mock network calls (GitHub/crates version
  lookups) and filesystem/HOME via `tmp_path` and monkeypatched `Path.home()`.

### Definition of done
- A change is done when `make validate && make test` both pass on the committed tree —
  not when the feature "works on my machine".

## Examples

### Avoid
```python
@pytest.mark.skip("flaky")          # hiding a real problem
def test_path_dedup(): ...
```

### Good
```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Applications path")
def test_macos_app_location(tmp_path, monkeypatch): ...
```
