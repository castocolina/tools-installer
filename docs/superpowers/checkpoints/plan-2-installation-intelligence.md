# Plan 2 — Installation intelligence checkpoint

Status: passed

## Changed files

- `installer/model.py`, `installer/deps.py`, `installer/install_plan.py`, and `installer/app.py`
- `installer/postinstall.py`, `installer/session.py`, and `installer/shellrc.py`
- `installer/ownership.py`, `installer/status.py`, and `installer/registry.toml`
- Focused model, dependency, post-install, ownership, status, registry, session, shellrc, and app tests

## Commits

- `ada070f`, `bdb9cf9`, `6c7703c`, `56a399d`, `e74a59a`, `769d0b7`,
  `d40a519`, `6268f89`, `923d721`

## Commands and results

- `uv run pytest tests/test_model.py tests/test_deps.py tests/test_postinstall.py tests/test_ownership.py tests/test_registry.py -q` — passed (115 tests).
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make validate` — passed.
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make test` — passed.
- Task verification included full test suites up to 696 passed, strict Pyright clean, and injected temporary-home/action-runner coverage.

## Failures and remediation

- Task review found omitted forwarding of `Resolution.reasons`; `6c7703c` fixed it and re-review passed.
- Task review found action-approval, `chsh`, and temporary-home safety gaps; `e74a59a` added explicit per-action grants and safety regressions, then passed re-review.
- Task review found failed ownership probes could escape; `d40a519` converts manager command failures to unknown ownership, then passed re-review.
- The first plan gate found `installer/deps.py` unformatted; formatting-only `923d721` fixed it before the successful rerun.

## Downstream impact

Plan 3 may start: tier, recommendation, and `ToolStatus`/ownership interfaces are available. Plan 1 is already integrated. Plan 4 remains independent.

## Final-audit remediation addendum (2026-07-26)

Status: passed after remediation.

Commits `a4cda36` and `ff44212` ship and test zsh's ordered managed actions,
default-enabled reviewed login-shell choice, and platform-correct managed pnpm
setup. Commits `85732f6` and `891bbd7` add typed, fail-closed skill lifecycle
admission and closed operation handling. Their scoped reviews passed.
