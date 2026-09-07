# Plan 3 — Basic and User catalog checkpoint

Status: passed

## Changed files

- Catalog views and presentation: `installer/catalog_tui.py`, `installer/tool_browser.py`, `installer/wizard_app.py`, and `setup.py`
- Typed host-aware catalog support: `installer/model.py`, `installer/host_setup.py`, `installer/executors.py`, `installer/engine.py`, `installer/ownership.py`, `installer/status.py`, `installer/apps.py`, `installer/resolve.py`, `installer/session.py`, and `installer/render.py`
- `installer/registry.toml` and focused catalog/model/executor/ownership/status/session tests

## Commits

- `5e598a6`, `67bafa1`, `d857abe`, `9eac80b`, `7f37cea`

## Commands and results

- `uv run pytest tests/test_catalog_tui.py tests/test_tool_browser.py tests/test_registry.py -q` — passed (105 tests).
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make validate` — passed.
- `UV_CACHE_DIR=/tmp/tools-installer-uv-cache make test` — passed.
- Task-specific verification included bounded-probe and host-aware manual-handoff regression suites.

## Failures and remediation

- The first User-catalog review found unsafe Textual TTY ownership, unwired ownership status, missing Superpowers/Pi dependency, unsafe Ponytail fallback, and an accidental SDD artifact overwrite. `9eac80b` fixed these and the full suite passed.
- Re-review found missing Ponytail/OpenSpec pre-approval disclosures and potentially acquiring `npx` probes. `7f37cea` adds the disclosures, replaces skill ownership probes with unknown, and bounds real probes with closed stdin and a five-second timeout.

## Downstream impact

Plans 1–3 are passed. Plan 4 remains independent and must complete its agent-environment fixtures, policy UI, temporary-home E2E, optional Podman handling, and checkpoint before final audit.

## Final-audit remediation addendum (2026-07-26)

Status: passed after remediation.

Commit `ac521c3` visibly labels contextual tools while retaining Basic/User
grouping and installed-last ordering. Commits `85732f6` and `891bbd7` complete
the User skill-pack admission/lifecycle contract. Scoped reviews passed.
