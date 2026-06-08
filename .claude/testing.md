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
