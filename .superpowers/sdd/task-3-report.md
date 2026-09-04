# Task 3 Report: Lock Catalog Policy With Tests

## What tests I added or changed
- Added `_tools_by_id()` and `_ids_by_priority()` helpers in `tests/test_registry.py`.
- Replaced the old count-based registry check with a requested-entry coverage test.
- Added priority and audience checks for `codex`, `claude`, and `opencode`.
- Added a P0 priority check for the high-use utility set.
- Added description-quality assertions for the priority tools listed in the brief.
- Added SDKMAN dependency checks for Java-family tools.
- Added install-method checks for the agent CLIs and container tools.
- Added a macOS-only cask check for JetBrains Toolbox.
- Updated the runtime category expectation to include the Java/SDKMAN family.
- Removed the hardcoded `50` count assertion from the registry uniqueness test.

## RED command and failure summary
- Command: `uv run pytest tests/test_registry.py -q`
- Result: red as expected after an escalated rerun because the local `uv` cache lives outside the writable sandbox path.
- Summary: 9 tests failed and the failures matched the current registry gaps.
- Main failures:
  - Requested entries such as `codex`, `claude`, `opencode`, `docker`, `podman`, `colima`, `jetbrains-toolbox`, `sdkman`, `java`, `groovy`, `springbootcli`, `gradle`, and `maven` are still missing.
  - The priority set is not yet aligned with the new policy.
  - The `rg` description still does not satisfy the new wording check.
  - The runtime category list is still only `bun`, `deno`, and `fnm`.

## Files changed
- `tests/test_registry.py`
- `.superpowers/sdd/task-3-report.md`

## Self-review findings
- The test module still imports cleanly and pytest collection succeeds.
- The new assertions are focused on catalog policy and do not touch `installer/registry.toml`.
- The failures are driven by missing catalog data, not by syntax or import errors.

## Concerns
- The focused pytest command required one escalated run because `uv` attempted to use its cache outside the writable sandbox area.
- The current registry is still expected to fail these policy tests until Task 4 updates the catalog data.

## Follow-up Fix
- Added `jetbrains-toolbox` to `MACOS_ONLY` in `tests/test_registry.py` so the cross-platform registry checks match the macOS-only cask policy.
- Re-ran `uv run pytest tests/test_registry.py -q`; collection still succeeds, and the remaining failures are the expected missing catalog-data gaps for Task 4.
