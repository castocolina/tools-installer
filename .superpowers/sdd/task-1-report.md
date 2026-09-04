# Task 1 Report: Collapse The Shared View Registry

## What I implemented
- Collapsed the shared view registry to four views in `installer/ui_common.py`: `catalog`, `doctor`, `uninstall`, and `policies`.
- Updated the doctor metadata to the new audit/apply wording and footer action text.
- Updated the global nav string to `1-4 views | ^p nav | esc back | q quit`.
- Kept the legacy `FixScreen` working as a private compatibility view without putting it back into `VIEW_BY_NAME`.
- Updated the registry and navigation expectations in `tests/test_ui_common.py` and `tests/test_wizard_app.py`.

## Tests run and results
- `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py::test_doctor_uninstall_and_policies_render_a_footer -q`
  - Pass
- `make validate`
  - Pass
- `make test`
  - Pass, `603 passed`

## TDD Evidence
- RED:
  - Command: `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py::test_doctor_uninstall_and_policies_render_a_footer -q`
  - Result: Failed as expected because `VIEW_ORDER`, `GLOBAL_NAV`, and Doctor footer text still reflected the old five-view registry.
- GREEN:
  - Command: `uv run pytest tests/test_ui_common.py tests/test_wizard_app.py::test_doctor_uninstall_and_policies_render_a_footer -q`
  - Result: Passed after updating the registry and navigation expectations.

## Files changed
- `installer/ui_common.py`
- `tests/test_ui_common.py`
- `tests/test_wizard_app.py`
- `.superpowers/sdd/task-1-report.md`

## Self-review findings
- The shared registry now has a single source of truth for the four public views.
- The Task 1 nav and footer expectations now match the registry and the app-level number keys.
- The legacy Fix screen is intentionally preserved outside the shared registry so Task 2 can own its removal later.

## Concerns
- None for Task 1. Task 2 remains intentionally out of scope.

## Review follow-up
- Removed the hidden `fix` row from the shared chrome registry and stopped `FooterBar` / `ModeBadge` from special-casing it.
- Updated the wizard app to stop constructing the private Fix screen as a navigable view.
- Deleted the wizard tests that treated `fix` as a supported navigation surface.

## Verification rerun
- `UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/test_ui_common.py tests/test_wizard_app.py -q`
  - Pass, `54 passed`
