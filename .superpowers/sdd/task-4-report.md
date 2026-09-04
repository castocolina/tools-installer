# Task 4 Report

## What catalog data/docs I changed

- Updated existing catalog rows in `installer/registry.toml` for `rg`, `jq`, `brew`, `fd`, `bat`, `sd`, `eza`, `gh`, `yq`, and `vscode` to match the required priorities, audiences, and concise descriptions.
- Added new installable registry rows for `git`, `codex`, `claude`, `opencode`, `docker`, `podman`, `colima`, `jetbrains-toolbox`, `sdkman`, `java`, `groovy`, `springbootcli`, `gradle`, and `maven`.
- Added `requires = ["pnpm"]` to `opencode` because the shipped registry policy requires every tool with a `node` method to depend on `pnpm`.
- Created `docs/catalog-unsupported-tools.md` documenting why `codegraph` is not an installable row in this pass and why PyCharm/IntelliJ are represented through JetBrains Toolbox.

## Tests run and results

1. `uv run pytest tests/test_registry.py -q`
   - Initial result: failed as expected before the catalog update, with missing rows and stale priority/description assertions.
2. `uv run pytest tests/test_registry.py -q`
   - Intermediate result: one failure remained, `test_shipped_node_tools_require_pnpm`, because `opencode` had a `node` method without a `pnpm` dependency.
3. `uv run pytest tests/test_registry.py -q -k shipped_node_tools_require_pnpm`
   - Result: passed after adding `requires = ["pnpm"]` to `opencode`.
4. `uv run pytest tests/test_registry.py -q -k 'container_tools_resolve_on_immutable_linux_without_native_writes or agent_clis_use_supported_install_methods or jetbrains_toolbox_is_macos_cask_only'`
   - Result: passed, `3 passed`. This covered the resolver-sensitive container rows, the human-facing agent CLI method policy, and the Toolbox macOS-only constraint.
5. `uv run pytest tests/test_registry.py -q`
   - Final registry result: passed, `48 passed`.
6. `make validate`
   - Result: passed. Ruff, format check, pyright, bandit, vulture, and shellcheck all completed cleanly.
7. `make test`
   - Result: passed, `609 passed`, coverage `99.96%`.

## Files changed

- `installer/registry.toml`
- `docs/catalog-unsupported-tools.md`
- `.superpowers/sdd/task-4-report.md`

## Self-review findings

- Confirmed all new method kinds already fit the existing loader and resolver: `script`, `node`, `dnf`, `apt`, `pacman`, `brew`, and `cask` are already supported.
- Confirmed the immutable Linux resolver behavior still holds: native package managers are skipped on immutable platforms, leaving brew for the new container tools when Homebrew is available.
- Confirmed JetBrains is represented only by Toolbox, and `codegraph` is documented instead of added as an unsupported install row.
- Kept the edit scoped to catalog data and the required docs/report artifacts; no Task 3 tests were modified.

## Concerns

- No blocking concerns. The only extra adjustment beyond the brief was adding `opencode`'s `pnpm` dependency to satisfy an existing shipped registry invariant.

## Follow-up: review fixes

- Updated `sdkman` in `installer/registry.toml` to model the installed artifact honestly: `cmd = "sdkman-init.sh"`, script `bin_dir = "~/.sdkman/bin"`, and a description that states sourcing the init script exposes the `sdk` shell function.
- Kept Java-family `requires = ["sdkman"]` unchanged for `java`, `groovy`, `springbootcli`, `gradle`, and `maven`, because that dependency remains the intended catalog policy where SDKMAN is supported.
- Removed OpenCode's `node` install method and removed `requires = ["pnpm"]` from `opencode`, so the resolver no longer pulls `pnpm` when OpenCode is installed via script, pacman, or brew.
- Updated the Task 3 registry expectation in `tests/test_registry.py` to match the corrected OpenCode model. This is an intentional expectation change because the old test encoded the same incorrect `node` fallback the review rejected.

### Follow-up tests

1. `uv run pytest tests/test_registry.py -q -k 'sdkman_uses_init_script_and_declares_bin_dir or agent_clis_use_supported_install_methods'`
   - Result: passed, `2 passed`.
2. `uv run pytest tests/test_registry.py -q`
   - Result: passed, `49 passed`.
3. `make validate`
   - Result: passed. Ruff, format check, pyright, bandit, vulture, and shellcheck all completed cleanly.

## Follow-up: Task 4 cask app-bundle detection

- Added a focused status test in `tests/test_status.py` proving `is_installed()` returns true for a `cask` method that declares `app = "JetBrains Toolbox.app"` when that bundle directory exists under an injected app root and no PATH command resolves.
- Updated `installer/status.py` so app-bundle detection reads the `app` parameter from both `app` and `cask` methods, while still requiring the bundle path to be a directory rather than a stale plain file.
- Updated the shipped `jetbrains-toolbox` registry row in `installer/registry.toml` to declare `app = "JetBrains Toolbox.app"` on its existing `cask` method, with no added CLI shim and no `app` install method.
- Extended `tests/test_registry.py` so the registry assertion for JetBrains Toolbox now checks that the cask method carries the declared app bundle parameter.

### Follow-up tests

1. `uv run pytest tests/test_status.py tests/test_registry.py -q`
   - Initial result: failed as expected before the production fix, with one status failure for cask app detection and one registry failure for the missing Toolbox `app` parameter.
2. `uv run pytest tests/test_status.py tests/test_registry.py -q`
   - Final result: passed, `42 passed`.
3. `make validate`
   - Result: passed. Ruff, format check, pyright, bandit, vulture, and shellcheck all completed cleanly.
