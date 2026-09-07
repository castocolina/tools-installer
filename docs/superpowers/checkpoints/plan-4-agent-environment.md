# Plan 4 — Agent environment checkpoint

Status: passed

## Changed files

- Agent adapters, guidance, and policy: `installer/agent_env.py`, `installer/agent_guidance.py`, `installer/agent_policy.py`
- Unified policy UI/composition: `installer/policy.py`, `installer/ui_common.py`, `installer/wizard_app.py`, and `setup.py`
- Agent policy, guidance, adapter, UI, temporary-home E2E, and container-target tests
- `Makefile`

## Commits

- `fccb3f3`, `37febaf`, `1a59098`, `0d96faf`, `0006fd5`

## Commands and results

- `uv run pytest tests/test_agent_env.py tests/test_agent_guidance.py tests/test_agent_policy.py tests/test_agent_environment_e2e.py tests/test_wizard_app.py -q` — passed.
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make validate` — passed.
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make test` — passed.
- `make test-container` — passed with available rootless Podman; the target used an unprivileged keep-id user, read-only repository, disposable HOME/TMPDIR, dropped capabilities, no-new-privileges, and no host network. Its cleanup check reported `temporary-home-cleaned`.

## Failures and remediation

- Task 2 review found malformed-config audit misclassification, stale/orphan marker false-health, and strict validation errors. `1a59098` aligned audit/apply behavior, converged marker blocks while preserving user text, and made validation clean.
- Task 3 review found a symlink-loop `RuntimeError` could abort UI composition. `0d96faf` contains it during composition, refresh, and live application while leaving the malformed adapter manual-required and actionless.
- Podman smoke initially exposed SELinux bind handling and subordinate-UID cleanup leakage. The final task added regression coverage and passed the isolated smoke without changing VM backends or the real home.

## Downstream impact

All four implementation plans are passed. The remaining step is the supervising final audit command and status matrix.

## Final-audit remediation addendum (2026-07-26)

Status: passed after remediation.

Commits `608ddf2` and `27a5282` decouple managed guidance references from
permission mutation and prevent Gemini-only configurations from detecting as
Antigravity. Commit `aaaed7e` expands the rootless Podman target to the fixture
installer workflow (dependency order, managed files, idempotency, Doctor/Fix,
and safe uninstall). Scoped reviews and the real container target passed.
