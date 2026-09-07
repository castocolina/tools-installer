# Catalog Reliability and Scope Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the installer to its package catalog responsibilities, then make the Catalog accurately report executable health, verified package-manager ownership, available updates, and explicit recovery actions.

**Architecture:** Remove agent-environment and skill-repository code as one vertical slice, including the centralized view registry and policy composition that import it. Model presence, health, ownership, and update availability independently in immutable status values. The Catalog emits an operation mode; `UnifiedApp` places that mode on the prepared `InstallPlan`, passes that exact plan to the executor, and replaces the complete catalog status map only after `InstallScreen` reports a final summary.

**Tech Stack:** Python 3.11, Textual, TOML registry, pytest, Ruff, Pyright.

## Global Constraints

- Keep the catalog registry declarative. It must not contain arbitrary shell commands or arbitrary executable paths for health or update operations.
- A PATH or app-bundle match proves presence only. A non-zero version check is a broken installation, not a missing tool.
- Every subprocess used for health, ownership, or update discovery must use `stdin=subprocess.DEVNULL`, capture text output, and set `timeout=5`.
- `TimeoutExpired` and `OSError` from health or update discovery must be converted into status detail, never propagated into the Catalog UI.
- Initial and post-execution status refreshes run only presence, health, and ownership checks. Network-capable update discovery runs only from the explicit Catalog refresh action.
- Only a verified owner with an `available` update may receive an in-app update command. Current, unknown, unsupported, malformed, timed-out, and failed checks are rendered as such and never guessed.
- Force reinstall bypasses only the `already-installed` short circuit; it retains resolver ordering, checksum verification, approvals, and TTY handoff rules.
- Agent configuration, shared agent-tool hints, CodeGraph setup, and skill repositories are out of scope. Do not add a replacement hints file in this change.
- The only retained agent-related mutation is an opt-in Policy that writes `alias opencode='opencode --auto'` into installer-owned marker blocks and removes only those blocks.
- All filesystem tests use `tmp_path`; all subprocess behavior is injected or monkeypatched. Tests must not inspect or change the real home directory.
- Do not add `# noqa`, `# type: ignore`, `# pyright: ignore`, `# nosec`, or quality-tool configuration changes.

---

## File Structure

- `installer/ui_common.py` owns the sole `VIEWS` registry and derived `VIEW_ORDER`; it loses the agent-environment view.
- `installer/policy.py` retains only generic `Policy`, the ban policy, tweak policy, and the OpenCode auto-mode policy; it no longer imports agent modules.
- `installer/model.py` removes skill-lifecycle and owner-probe schema and adds validated `version_args` metadata to `Tool`.
- `installer/health.py` provides bounded executable-version inspection and normalized launch/timeout results.
- `installer/ownership.py` derives ownership and the exact package identity from declared install methods.
- `installer/updates.py` provides bounded update discovery, strict manager-specific parsing, and reviewed update argv construction.
- `installer/status.py` composes immutable presence, health, ownership, and update values.
- `installer/engine.py`, `installer/install_plan.py`, and `installer/session.py` execute install, reinstall, and verified update plans.
- `installer/catalog_tui.py`, `installer/tool_browser.py`, `installer/install_screen.py`, and `installer/wizard_app.py` expose catalog operations and complete-operation refresh wiring.
- `setup.py` remains wiring-only: it binds real runners, status construction, policies, and the execution closure.
- `tests/test_health.py` and `tests/test_updates.py` cover bounded subprocess behavior and parser contracts. Existing model, ownership, status, policy, UI, `ui_common`, setup, and workflow tests remove obsolete behavior and cover the retained surface.

### Task 1: Remove the agent-environment and skill-repository surface

**Files:**
- Delete: `installer/agent_env.py`
- Delete: `installer/agent_guidance.py`
- Delete: `installer/agent_policy.py`
- Delete: `installer/skill_lifecycle.py`
- Delete: `tests/test_agent_env.py`
- Delete: `tests/test_agent_guidance.py`
- Delete: `tests/test_agent_policy.py`
- Delete: `tests/test_agent_environment_e2e.py`
- Delete: `tests/test_skill_lifecycle.py`
- Modify: `installer/ui_common.py:95-168`
- Modify: `installer/wizard_app.py:15-49,527-649,746-850`
- Modify: `installer/policy.py:1-167`
- Modify: `installer/model.py:8-66,96-163,166-356,359-480`
- Modify: `installer/engine.py:9-14,40-56`
- Modify: `installer/status.py:1-86`
- Modify: `installer/catalog_tui.py:24-45,252-273`
- Modify: `installer/install_screen.py:230-258`
- Modify: `installer/uninstall.py`
- Modify: `installer/postinstall.py:24-31,37-38,63-79,238-282`
- Modify: `setup.py:21-27,46-51,151-223,295-306`
- Modify: `installer/registry.toml`
- Modify: `tests/test_model.py`, `tests/test_status.py`, `tests/test_catalog_tui.py`, `tests/test_wizard_app.py`, `tests/test_ui_common.py`, `tests/test_policy.py`, `tests/test_policies_e2e.py`, `tests/test_registry.py`, `tests/test_uninstall.py`, `tests/test_install_screen.py`, `tests/test_postinstall.py`, and `tests/test_container_smoke.py`

**Interfaces:**
- Produces: `VIEWS` with catalog, doctor, uninstall, policies, and install only; `VIEW_ORDER` remains derived from `VIEWS`.
- Produces: a `Policy` module with no `AgentAdapter`, `AgentAudit`, `AgentEnvironmentPolicy`, `agent_environment_policy`, or `compose_agent_environment_policy` symbols.
- Retains: standalone `pi`, `codex`, `claude`, and `opencode` catalog tools. `pi` remains a standalone CLI, not a skill repository.

- [ ] **Step 1: Write failing removal-boundary tests**

```python
# tests/test_wizard_app.py
from installer.ui_common import VIEW_ORDER, VIEWS


def test_view_registry_excludes_agent_environment() -> None:
    assert "agent-environment" not in VIEW_ORDER
    assert all(view.name != "agent-environment" for view in VIEWS)


async def test_agent_environment_has_no_navigation_route() -> None:
    app = _app()
    async with app.run_test() as pilot:
        await pilot.press("5")
        assert app.current_view == "catalog"
```

```python
# tests/test_ui_common.py
def test_view_registry_and_global_navigation_exclude_agent_environment() -> None:
    from installer.ui_common import GLOBAL_NAV, VIEW_ORDER, VIEWS

    assert VIEW_ORDER == ("catalog", "doctor", "uninstall", "policies")
    assert {view.name for view in VIEWS} == {
        "catalog", "doctor", "uninstall", "policies", "install"
    }
    assert GLOBAL_NAV == "1-4 views | ^p nav | esc back | q quit"
```

```python
# tests/test_policy.py
def test_policy_module_does_not_depend_on_agent_environment_modules() -> None:
    import installer.policy as policy

    assert not hasattr(policy, "AgentEnvironmentPolicy")
    assert not hasattr(policy, "compose_agent_environment_policy")
```

```python
# tests/test_registry.py
def test_registry_excludes_skill_repositories() -> None:
    removed = {
        "ponytail", "openspec", "superpowers", "softaworks-agent-toolkit",
        "matt-pocock-skills", "opengsd", "spec-kit",
    }
    assert removed.isdisjoint(_tools_by_id())
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_wizard_app.py tests/test_ui_common.py tests/test_policy.py tests/test_registry.py -k 'agent_environment or excludes_skill_repositories or global_navigation' -v`

Expected: FAIL because `ui_common.VIEWS` and `GLOBAL_NAV` still advertise the fifth view, and `policy.py` still imports the deleted agent modules.

- [ ] **Step 3: Delete the complete runtime surface, including centralized registration and policy imports**

```python
# installer/ui_common.py
VIEWS: tuple[View, ...] = (
    View("catalog", "Catalog", "Catalog - pick tools to install", "1", "STAGED", "o", "cyan",
         "space marks a tool; enter installs your selection",
         "space toggle | enter install | a all | i invert"),
    View("doctor", "Doctor", "Doctor - audit PATH and apply the safe fix", "2", "AUDIT + APPLY", ">", "yellow",
         "audit report stays read-only until you press enter", "enter apply"),
    View("uninstall", "Uninstall", "Uninstall - remove installed tools", "3", "STAGED / DESTRUCTIVE", "o", "red",
         "space marks; enter removes marked items (you'll confirm)", "space mark | enter remove | a all | i invert"),
    View("policies", "Policies", "Policies - pip/npm ban and env tweaks", "4", "LIVE", "*", "yellow",
         "space toggles a policy and applies it now; reversible", "space toggle"),
    View("install", "Install", "", None, "LIVE", ">", "cyan",
         "installation runs sequentially; stay here until it finishes", "install in progress"),
)
VIEW_ORDER: tuple[str, ...] = tuple(view.name for view in VIEWS if view.shortcut is not None)
```

```python
# installer/wizard_app.py
# Delete AgentEnvironmentScreen and its imports. UnifiedApp.__init__ has no
# agent_environment parameter, and its persistent view map is exactly:
self._views: dict[str, Screen[None]] = {
    "doctor": DoctorScreen(report, guard_status, guard_warning, fix_preview, fix),
    "uninstall": UninstallScreen(uninstall),
    "policies": PoliciesScreen(policies),
    "install": InstallScreen(),
}
```

```python
# installer/policy.py
# Delete AgentEnvironmentPolicy, agent_environment_policy, and
# compose_agent_environment_policy. The retained imports are:
from installer.guards import (
    guard_path_warning, guard_status, install_shims, remove_ban_aliases,
    remove_shims, write_ban_aliases,
)
from installer.tweaks import TweakBundle, remove_tweak, tweak_present, write_tweak
```

Remove `skill_pack` from `METHOD_KINDS`; remove all skill lifecycle types, parsing functions, `Tool.skill_lifecycle`, `Tool.owner_probes`, and `OWNER_PROBES` from the model. In `installer/postinstall.py`, remove `apply_block` from imports, `_AGENT_REFERENCE_BEGIN`, `_AGENT_REFERENCE_END`, `ActionContext.agent_reference_paths`, `write_agent_reference`, and the `"write_agent_reference"` handler entry. Delete `test_write_agent_reference_preserves_user_text_and_is_idempotent` and remove `agent_reference_paths` from the test context helper in `tests/test_postinstall.py`. Remove the skill lifecycle routes from engine, status, catalog detail rendering, install preview, uninstall classification, and setup composition. Delete the seven registry tables named in the focused test, including nested lifecycle tables. Remove agent imports, constructor parameters, and agent composition from `setup.py`. Update or delete tests that import agent modules, expect the fifth navigation key, inspect lifecycle status, agent-reference behavior, or load a removed registry tool. In `tests/test_ui_common.py`, change view-order assertions to the four navigable views, change every `1-5 views` footer expectation to `1-4 views`, and retain the non-navigable `install` view assertion.

- [ ] **Step 4: Run the affected test groups**

Run: `uv run pytest tests/test_model.py tests/test_registry.py tests/test_status.py tests/test_catalog_tui.py tests/test_wizard_app.py tests/test_ui_common.py tests/test_policy.py tests/test_policies_e2e.py tests/test_uninstall.py tests/test_install_screen.py tests/test_postinstall.py tests/test_container_smoke.py -v`

Expected: PASS. `UnifiedApp` neither binds nor navigates to agent environment, and importing `installer.policy` does not import a deleted module.

- [ ] **Step 5: Commit the scope reduction**

```bash
git add installer setup.py tests docs/superpowers/plans/2026-07-28-catalog-reliability-and-scope-reduction.md
git commit -m "refactor(scope): remove agent environment and skill repositories"
```

### Task 2: Retain only the reversible OpenCode auto-mode policy

**Files:**
- Modify: `installer/tweaks.py:60-103`
- Modify: `installer/policy.py:1-25,223-255`
- Modify: `setup.py:46-51,175-213`
- Modify: `tests/test_tweaks.py`
- Modify: `tests/test_policy_tweaks.py`
- Modify: `tests/test_policy.py`
- Modify: `tests/test_policies_e2e.py`

**Interfaces:**
- Produces: `OPENCODE_AUTO_BUNDLE: TweakBundle` with id `opencode-auto`.
- Produces: `opencode_auto_policy(*, apply_rc_paths: list[Path], remove_rc_paths: list[Path]) -> Policy`.
- Behavior: apply writes only `tweak:opencode-auto` blocks; removal searches every historical rc location and removes only those blocks.

- [ ] **Step 1: Write failing policy and removed-bundle tests**

```python
# tests/test_tweaks.py
def test_retained_bundles_have_stable_ids() -> None:
    assert [bundle.id for bundle in BUNDLES] == ["docker", "countdown", "apt-upgrade"]


def test_claude_skip_bundle_is_not_available() -> None:
    assert "claude-skip" not in {bundle.id for bundle in BUNDLES}
```

```python
# tests/test_policy_tweaks.py
def test_removed_claude_skip_policy_is_not_constructed() -> None:
    assert "claude-skip" not in {bundle.id for bundle in BUNDLES}
```

```python
# tests/test_policy.py
def test_opencode_auto_policy_round_trips_only_its_managed_block(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text("alias user-tool='user command'\n")
    policy = opencode_auto_policy(apply_rc_paths=[rc], remove_rc_paths=[rc])
    policy.apply()
    assert "alias opencode='opencode --auto'" in rc.read_text()
    opencode_auto_policy(apply_rc_paths=[rc], remove_rc_paths=[rc]).remove()
    assert rc.read_text() == "alias user-tool='user command'\n"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_policy.py -k 'retained_bundles or claude_skip or opencode_auto' -v`

Expected: FAIL because `claude-skip` remains and `opencode_auto_policy` does not exist.

- [ ] **Step 3: Implement the retained policy with marker blocks**

```python
# installer/tweaks.py
OPENCODE_AUTO_BUNDLE = TweakBundle(
    "opencode-auto",
    "OpenCode auto mode",
    "alias opencode='opencode --auto'",
    (),
    "alias opencode='opencode --auto'",
)

BUNDLES: tuple[TweakBundle, ...] = (
    TweakBundle("docker", "Docker shortcuts", "docker-ps (live table), docker-stats, docker-memory (needs `watch`)", (), _DOCKER_BODY),
    TweakBundle("countdown", "Countdown helper", "wait_time <secs> — a portable terminal countdown", (), _COUNTDOWN_BODY),
    TweakBundle("apt-upgrade", "apt selective upgrade", "alias apt-upgrade — upgrade only packages that have updates (Linux)", _LINUX, _APT_BODY),
)
```

```python
# installer/policy.py
def opencode_auto_policy(*, apply_rc_paths: list[Path], remove_rc_paths: list[Path]) -> Policy:
    def _result(action: str, paths: list[Path]) -> PolicyResult:
        detail = f"{action} to " + ", ".join(_display_path(path) for path in paths)
        return PolicyResult((PolicyLayer("Alias", detail),), _RELOAD_HINT, None)

    def _apply() -> PolicyResult:
        for path in apply_rc_paths:
            write_tweak(OPENCODE_AUTO_BUNDLE, path)
        return _result("written", apply_rc_paths)

    def _remove() -> PolicyResult:
        for path in remove_rc_paths:
            remove_tweak(OPENCODE_AUTO_BUNDLE, path)
        return _result("cleared", remove_rc_paths)

    return Policy(
        id="opencode-auto",
        label=OPENCODE_AUTO_BUNDLE.label,
        description=OPENCODE_AUTO_BUNDLE.description,
        active=any(tweak_present(OPENCODE_AUTO_BUNDLE, path) for path in remove_rc_paths),
        apply=_apply,
        remove=_remove,
    )
```

In `setup.py`, use `[_MYSHELLRC]` as apply paths in centralized and single modes, `rc_paths` in split mode, and `[_MYSHELLRC, *_RC_PATHS]` as removal paths. Add `opencode_auto_policy(...)` after `ban_policy(...)`; retain curated non-agent `tweak_policy` entries. Remove `_CLAUDE_BODY`, the `claude-skip` bundle, and every test assertion that constructs it.

- [ ] **Step 4: Run policy tests**

Run: `uv run pytest tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_policy.py tests/test_policies_e2e.py -v`

Expected: PASS. The retained OpenCode policy is reversible and no test or runtime list refers to `claude-skip`.

- [ ] **Step 5: Commit the retained policy**

```bash
git add installer/policy.py installer/tweaks.py setup.py tests/test_tweaks.py tests/test_policy_tweaks.py tests/test_policy.py tests/test_policies_e2e.py
git commit -m "feat(policies): add reversible OpenCode auto mode"
```

### Task 3: Model bounded executable health and version evidence

**Files:**
- Create: `installer/health.py`
- Modify: `installer/model.py`
- Modify: `installer/status.py`
- Modify: `tests/test_model.py`
- Create: `tests/test_health.py`
- Modify: `tests/test_status.py`

**Interfaces:**
- Produces: `CommandResult(returncode: int, stdout: str, stderr: str, failure: str | None = None)`.
- Produces: `HealthState = Literal["missing", "healthy", "broken", "unsupported"]`, `Health`, `HealthRunner`, `run_health_check`, and `inspect_health`.
- Extends: `Tool.version_args: tuple[str, ...] | None`; omitted TOML defaults to `("--version",)`, while `version_args = []` becomes `None`.
- Extends: `ToolStatus` with `health: Health`; a present but failing executable remains installed and selectable for repair.

- [ ] **Step 1: Write failing health and runner-failure tests**

```python
# tests/test_health.py
def test_timeout_renders_broken_health_with_a_diagnostic() -> None:
    tool = _tool()
    health = inspect_health(
        tool,
        which=lambda _cmd: "/fixture/bin/demo",
        runner=lambda _argv: CommandResult(124, "", "", "version check timed out after 5 seconds"),
    )
    assert health == Health("broken", None, "version check timed out after 5 seconds")


def test_launch_failure_renders_broken_health_with_a_diagnostic() -> None:
    tool = _tool()
    health = inspect_health(
        tool,
        which=lambda _cmd: "/fixture/bin/demo",
        runner=lambda _argv: CommandResult(1, "", "", "version check could not start: missing"),
    )
    assert health.state == "broken"
    assert health.detail == "version check could not start: missing"


def test_present_app_bundle_without_a_path_executable_has_missing_health(tmp_path: Path) -> None:
    app_root = tmp_path / "Applications"
    (app_root / "Demo.app").mkdir(parents=True)
    tool = _tool(Method("app", {"app": "Demo.app"}))

    status = tool_status(tool, lambda _argv: "", app_roots=(app_root,), health_runner=lambda _argv: _result())

    assert status.installed is True
    assert status.health == Health("missing", None, "command not found on PATH")


def test_runner_closes_stdin_captures_output_and_bounds_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, "run", lambda _argv, **kwargs: calls.append(kwargs) or _completed())
    assert run_health_check(["demo", "--version"]).returncode == 0
    assert calls == [{"check": False, "stdin": subprocess.DEVNULL, "capture_output": True, "text": True, "timeout": 5}]


@pytest.mark.parametrize(
    "exception, expected",
    [
        (subprocess.TimeoutExpired(["demo", "--version"], 5), "version check timed out after 5 seconds"),
        (OSError("missing"), "version check could not start: missing"),
    ],
)
def test_health_runner_normalizes_timeout_and_launch_failures(
    monkeypatch: pytest.MonkeyPatch, exception: BaseException, expected: str
) -> None:
    def raise_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise exception

    monkeypatch.setattr(subprocess, "run", raise_error)
    assert run_health_check(["demo", "--version"]).failure == expected
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_health.py tests/test_model.py tests/test_status.py -k 'health or version_args or timeout or launch_failure' -v`

Expected: FAIL because health inspection and `Tool.version_args` do not exist.

- [ ] **Step 3: Implement normalized bounded health inspection**

```python
# installer/health.py
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    failure: str | None = None


def run_health_check(argv: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(
            argv, check=False, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "", "version check timed out after 5 seconds")
    except OSError as error:
        return CommandResult(1, "", "", f"version check could not start: {error}")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def inspect_health(tool: Tool, *, which: Callable[[str], str | None], runner: HealthRunner) -> Health:
    if tool.version_args is None:
        return Health("unsupported", None, "no executable version check declared")
    if which(tool.cmd) is None:
        return Health("missing", None, "command not found on PATH")
    result = runner([tool.cmd, *tool.version_args])
    if result.returncode != 0:
        detail = result.failure or result.stderr.strip() or result.stdout.strip() or "version command failed"
        return Health("broken", None, detail)
    version = next((line.strip() for line in result.stdout.splitlines() if line.strip()), None)
    return Health("healthy", version, "version command succeeded")
```

Parse `version_args` only when the registry value is a list of strings. Reject a string or non-string member with `ValueError`; normalize an omitted field to `("--version",)` and an empty list to `None`. In `tool_status`, calculate presence first, then call `inspect_health` only for a present tool; the normalized result ensures launch and timeout failures render as `Health("broken", ...)` rather than aborting startup or refresh. An app or cask bundle found in `app_roots` is therefore `installed=True` with `Health("missing", None, "command not found on PATH")` when its CLI does not resolve; it is not an absent tool.

- [ ] **Step 4: Run health, model, and status tests**

Run: `uv run pytest tests/test_health.py tests/test_model.py tests/test_status.py -v`

Expected: PASS. A stale executable, timeout, and launch failure are present-but-broken; an app-bundle tool whose CLI is absent from `PATH` is present with missing health; a bundle-only tool with `version_args = []` is present with unsupported health.

- [ ] **Step 5: Commit health support**

```bash
git add installer/health.py installer/model.py installer/status.py tests/test_health.py tests/test_model.py tests/test_status.py
git commit -m "feat(status): distinguish broken tools from healthy installs"
```

### Task 4: Verify ownership and discover updates with strict adapters

**Files:**
- Create: `installer/updates.py`
- Modify: `installer/ownership.py`
- Modify: `installer/model.py`
- Modify: `installer/registry.toml`
- Modify: `installer/status.py`
- Modify: `tests/test_ownership.py`
- Create: `tests/test_updates.py`
- Modify: `tests/test_model.py`, `tests/test_status.py`, and `tests/test_registry.py`

**Interfaces:**
- Extends: `Ownership` with `method_kind: str | None` and `package: str | None`.
- Produces: `UpdateState = Literal["unknown", "current", "available", "unsupported"]`, `UpdateStatus`, `UpdateRunner`, `run_update_check`, `inspect_update`, and `update_argv`.
- Extends: frozen `ToolStatus` with `update: UpdateStatus = UpdateStatus("unknown", None, "update discovery not requested")`. `tool_status` always supplies that value during initial and post-operation refreshes; only `status_factory(True)` replaces it with `inspect_update(...)` results for the complete status map.
- Behavior: `run_update_check` uses the same five-second, closed-stdin contract as health and returns `CommandResult` with `failure` set for timeout or launch failure.
- Behavior: only an exact declared package in a successful manager response establishes `available`; a successful empty response establishes `current`; any unrelated or malformed nonempty response is `unknown`.

- [ ] **Step 1: Write failing ownership, runner, and parser-contract tests**

```python
# tests/test_updates.py
@pytest.mark.parametrize(
    ("ownership", "result", "expected"),
    [
        (_owner("pnpm", "node", "demo"), CommandResult(0, '[{"name":"demo","current":"1.0","latest":"1.1"}]', ""), "available"),
        (_owner("pnpm", "node", "demo"), CommandResult(0, "[]", ""), "current"),
        (_owner("Homebrew", "brew", "demo"), CommandResult(0, '{"formulae":[{"name":"demo","current_version":"1.0","latest_version":"1.1"}],"casks":[]}', ""), "available"),
        (_owner("Homebrew", "cask", "demo"), CommandResult(0, '{"formulae":[],"casks":[{"token":"demo","current_version":"1.0","latest_version":"1.1"}]}', ""), "available"),
        (_owner("apt", "apt", "demo"), CommandResult(0, "demo/stable 1.1 amd64 [upgradable from: 1.0]\\n", ""), "available"),
        (_owner("dnf", "dnf", "demo"), CommandResult(100, "demo.x86_64 1.1 repo\\n", ""), "available"),
        (_owner("pacman", "pacman", "demo"), CommandResult(0, "demo 1.0 -> 1.1\\n", ""), "available"),
    ],
)
def test_documented_manager_output_is_parsed_for_the_exact_package(
    ownership: Ownership, result: CommandResult, expected: UpdateState
) -> None:
    assert inspect_update(_tool(ownership.package or "demo"), ownership, lambda _argv: result).state == expected


@pytest.mark.parametrize("result", [
    CommandResult(0, "other 1.0 -> 1.1\\n", ""),
    CommandResult(0, "{not json", ""),
    CommandResult(1, "demo 1.0 -> 1.1\\n", "failure"),
    CommandResult(124, "", "", "update check timed out after 5 seconds"),
    CommandResult(1, "", "", "update check could not start: missing"),
])
def test_unrelated_malformed_or_failed_update_output_is_unknown(result: CommandResult) -> None:
    update = inspect_update(_tool("demo"), _owner("pacman", "pacman", "demo"), lambda _argv: result)
    assert update.state == "unknown"
    assert update.detail


@pytest.mark.parametrize(
    "exception, expected",
    [
        (subprocess.TimeoutExpired(["pnpm"], 5), "update check timed out after 5 seconds"),
        (OSError("missing"), "update check could not start: missing"),
    ],
)
def test_update_runner_normalizes_timeout_and_launch_failures(
    monkeypatch: pytest.MonkeyPatch, exception: BaseException, expected: str
) -> None:
    def raise_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise exception

    monkeypatch.setattr(subprocess, "run", raise_error)
    assert run_update_check(["pnpm", "outdated", "--global", "--json", "demo"]).failure == expected


def test_update_runner_closes_stdin_captures_output_and_bounds_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, "run", lambda _argv, **kwargs: calls.append(kwargs) or _completed())
    assert run_update_check(["pnpm", "outdated", "--global", "--json", "demo"]).returncode == 0
    assert calls == [{"check": False, "stdin": subprocess.DEVNULL, "capture_output": True, "text": True, "timeout": 5}]


def test_initial_status_marks_update_discovery_as_not_requested() -> None:
    status = tool_status(_tool("demo"), lambda _argv: "", health_runner=lambda _argv: _result())

    assert status.update == UpdateStatus("unknown", None, "update discovery not requested")
```

```python
# tests/test_updates.py
@pytest.mark.parametrize(
    ("ownership", "expected"),
    [
        (_owner("pnpm", "node", "demo"), ["pnpm", "outdated", "--global", "--json", "demo"]),
        (_owner("Homebrew", "brew", "demo"), ["brew", "outdated", "--json=v2", "--formula", "demo"]),
        (_owner("Homebrew", "cask", "demo"), ["brew", "outdated", "--json=v2", "--cask", "demo"]),
        (_owner("apt", "apt", "demo"), ["apt", "list", "--upgradable", "demo"]),
        (_owner("dnf", "dnf", "demo"), ["dnf", "check-update", "demo"]),
        (_owner("pacman", "pacman", "demo"), ["pacman", "-Qu", "demo"]),
    ],
)
def test_each_reviewed_adapter_uses_its_fixed_query_argv(ownership: Ownership, expected: list[str]) -> None:
    seen: list[list[str]] = []
    inspect_update(_tool("demo"), ownership, lambda argv: seen.append(argv) or CommandResult(0, "", ""))
    assert seen == [expected]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_ownership.py tests/test_updates.py -v`

Expected: FAIL because ownership has no package identity and `installer.updates` does not exist.

- [ ] **Step 3: Implement exact ownership evidence and update parsing**

```python
# installer/updates.py
def run_update_check(argv: list[str]) -> CommandResult:
    try:
        completed = subprocess.run(argv, check=False, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "", "update check timed out after 5 seconds")
    except OSError as error:
        return CommandResult(1, "", "", f"update check could not start: {error}")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


_OUTDATED_COMMANDS: dict[tuple[str, str], Callable[[str], list[str]]] = {
    ("pnpm", "node"): lambda package: ["pnpm", "outdated", "--global", "--json", package],
    ("Homebrew", "brew"): lambda package: ["brew", "outdated", "--json=v2", "--formula", package],
    ("Homebrew", "cask"): lambda package: ["brew", "outdated", "--json=v2", "--cask", package],
    ("apt", "apt"): lambda package: ["apt", "list", "--upgradable", package],
    ("dnf", "dnf"): lambda package: ["dnf", "check-update", package],
    ("pacman", "pacman"): lambda package: ["pacman", "-Qu", package],
}
```

Implement `_parse_outdated` with this closed contract:

| Manager / method | Accepted available output | Exact match rule | Current output |
| --- | --- | --- | --- |
| pnpm / node | JSON list of objects, each with string `name`, `current`, and `latest` | `name == package` | JSON `[]` |
| Homebrew / brew | JSON object with list `formulae`; member has string `name`, `current_version`, `latest_version` | `name == package` | `formulae == []` and `casks == []` |
| Homebrew / cask | JSON object with list `casks`; member has string `token`, `current_version`, `latest_version` | `token == package` | `formulae == []` and `casks == []` |
| apt / apt | one non-warning line `package/channel version architecture [upgradable from: version]` | substring before the first `/` equals `package` | no non-warning lines |
| dnf / dnf | exit 100 and one line `package.arch version repository` | substring before `.arch` equals `package`; only `x86_64`, `aarch64`, `armhfp`, or `noarch` suffixes are accepted | exit 0 with no non-warning lines |
| pacman / pacman | one line `package current -> latest` | first whitespace-separated token equals `package` | exit 0 with no non-warning lines |

Create one named pytest fixture for each cell in the table: `pnpm_current`, `pnpm_available`, `pnpm_malformed`, `pnpm_nonzero`, `brew_formula_current`, `brew_formula_available`, `brew_formula_malformed`, `brew_formula_nonzero`, `brew_cask_current`, `brew_cask_available`, `brew_cask_malformed`, `brew_cask_nonzero`, `apt_current`, `apt_available`, `apt_malformed`, `apt_nonzero`, `dnf_current`, `dnf_available`, `dnf_malformed`, `dnf_nonzero`, `pacman_current`, `pacman_available`, `pacman_malformed`, and `pacman_nonzero`. Each fixture returns its manager's exact `Ownership` plus one `CommandResult`; current uses the table's empty output, available uses the displayed accepted output, malformed uses invalid JSON or a nonmatching nonempty line, and nonzero uses `returncode=1` except DNF's available fixture, which uses `returncode=100`. Parametrize the parser test over all 24 fixture names so every adapter proves current, available, malformed, and nonzero behavior.

For all adapters, reject invalid JSON, missing required string fields, a nonempty response that contains only another package, nonzero results other than DNF exit 100, and a `CommandResult.failure` as `UpdateStatus("unknown", None, detail)`. Preserve the normalized runner failure text in `detail`. `update_argv` returns the reviewed install argv only for a verified ownership tuple: pnpm `add -g`; brew formula `upgrade`; brew cask `upgrade --cask`; apt `sudo apt-get install --only-upgrade -y`; dnf `sudo dnf upgrade -y`; pacman `sudo pacman -S --noconfirm`.

Declare `UNKNOWN_UPDATE = UpdateStatus("unknown", None, "update discovery not requested")` in `installer.updates` and use it as the frozen `ToolStatus.update` default. Change `detect_owner` to iterate declared methods in catalog order. Each recognized method probes its native manager and returns `Ownership(manager, "verified", detail, method.kind, package)` only after exact package evidence. Remove `owner_probes` from the model and registry. Add OpenCode’s `requires = ["pnpm"]` and `Method("node", {"npm_pkg": "opencode-ai"})` while retaining its existing install methods.

- [ ] **Step 4: Run ownership, updates, model, status, and registry tests**

Run: `uv run pytest tests/test_ownership.py tests/test_updates.py tests/test_model.py tests/test_status.py tests/test_registry.py -v`

Expected: PASS. Each adapter runs a fixed command, recognizes only the declared package, turns launch, timeout, malformed, and failed discovery into an unknown status, and leaves non-network status refreshes at `UNKNOWN_UPDATE`.

- [ ] **Step 5: Commit manager intelligence**

```bash
git add installer/ownership.py installer/updates.py installer/model.py installer/status.py installer/registry.toml tests/test_ownership.py tests/test_updates.py tests/test_model.py tests/test_status.py tests/test_registry.py
git commit -m "feat(catalog): verify managers and discover updates"
```

### Task 5: Execute install, forced reinstall, and verified update plans

**Files:**
- Modify: `installer/engine.py`
- Modify: `installer/install_plan.py`
- Modify: `installer/session.py`
- Modify: `installer/app.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_app.py`

**Interfaces:**
- Produces: `ExecutionMode = Literal["install", "reinstall", "update"]`.
- Extends: `InstallPlan.execution_mode: ExecutionMode = "install"`.
- Produces: `install_tool(tool: Tool, platform: Platform, runner: Runner = run_command, resolve_tag: TagResolver = resolve_github_tag, *, checksum_policy: ChecksumPolicy = "fail", force: bool = False) -> InstallOutcome` and `update_tool(tool: Tool, ownership: Ownership, update: UpdateStatus, runner: Runner = run_command) -> InstallOutcome`.
- Extends: `run_plan(plan: InstallPlan, platform: Platform, emit: Callable[[ExecutionEvent], None], statuses: Mapping[str, ToolStatus], runner: Runner = run_command, resolve_tag: TagResolver = resolve_github_tag, install: Install = install_tool, on_mismatch: OnMismatch | None = None, outcomes: list[InstallOutcome] | None = None, action_context: ActionContext | None = None, approved_actions: frozenset[ActionKey] = frozenset(), skipped_actions: frozenset[ActionKey] = frozenset(), captured_runner: CapturedRunner | None = None, interactive_runner: Runner | None = None) -> Summary`.

- [ ] **Step 1: Write failing execution-mode tests**

```python
# tests/test_session.py
@pytest.mark.parametrize(
    ("mode", "expected_force", "expected_command"),
    [
        ("install", False, []),
        ("reinstall", True, []),
        ("update", False, ["pnpm", "add", "-g", "demo"]),
    ],
)
def test_run_plan_executes_the_mode_on_the_prepared_plan(
    mode: ExecutionMode, expected_force: bool, expected_command: list[str]
) -> None:
    plan = replace(_plan("demo"), execution_mode=mode)
    forces: list[bool] = []
    commands: list[list[str]] = []
    summary = run_plan(
        plan, _platform(), lambda _event: None,
        statuses={
            "demo": _status(
                "demo",
                owner=_pnpm_owner(),
                update=UpdateStatus("available", "1.1", "fixture"),
            )
        },
        install=lambda *args, force=False, **kwargs: forces.append(force) or InstallOutcome("demo", "installed"),
        runner=commands.append,
    )
    assert summary.installed == ("demo",)
    assert forces == ([] if mode == "update" else [expected_force])
    assert commands == ([] if not expected_command else [expected_command])
```

```python
# tests/test_engine.py
def test_force_reinstall_bypasses_only_presence_and_keeps_checksum_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "is_installed", lambda _tool: True)
    _mismatching_download(monkeypatch)
    platform = Platform(os="fedora", arch="amd64", immutable=False, has_brew=True)

    outcome = install_tool(_gh_then_brew(), platform, force=True)

    assert outcome.status == "checksum-mismatch"
    assert outcome.method_kind == "github_release"
    assert isinstance(outcome.errors[0], ChecksumMismatch)


@pytest.mark.parametrize("update", [
    UpdateStatus("current", None, "already current"),
    UpdateStatus("unknown", None, "malformed manager output"),
    UpdateStatus("unsupported", None, "manager has no reviewed update adapter"),
])
def test_update_rejects_statuses_without_a_verified_available_update(update: UpdateStatus) -> None:
    commands: list[list[str]] = []

    outcome = update_tool(
        _tool(Method("node", {"npm_pkg": "demo"})),
        _pnpm_owner(),
        update,
        commands.append,
    )

    assert outcome.status == "no-method"
    assert commands == []
```

```python
# tests/test_session.py
@pytest.mark.parametrize("update", [
    UpdateStatus("current", None, "already current"),
    UpdateStatus("unknown", None, "malformed manager output"),
    UpdateStatus("unsupported", None, "manager has no reviewed update adapter"),
])
def test_update_plan_does_not_run_manager_for_non_available_status(update: UpdateStatus) -> None:
    commands: list[list[str]] = []
    plan = replace(_plan("demo"), execution_mode="update")
    summary = run_plan(
        plan,
        _platform(),
        lambda _event: None,
        statuses={"demo": _status("demo", owner=_pnpm_owner(), update=update)},
        runner=commands.append,
    )

    assert summary.no_method == ("demo",)
    assert commands == []
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_engine.py tests/test_session.py -k 'force or mode or update' -v`

Expected: FAIL because plans have no execution mode and session always runs a normal install.

- [ ] **Step 3: Implement the three explicit execution modes**

```python
# installer/install_plan.py
ExecutionMode = Literal["install", "reinstall", "update"]

@dataclass(frozen=True)
class InstallPlan:
    selected_ids: tuple[str, ...]
    ordered: tuple[Tool, ...]
    dragged_in: tuple[str, ...]
    warnings: tuple[str, ...]
    reasons: tuple[tuple[str, str], ...] = ()
    execution_mode: ExecutionMode = "install"
```

```python
# installer/engine.py
def install_tool(
    tool: Tool,
    platform: Platform,
    runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag,
    *,
    checksum_policy: ChecksumPolicy = "fail",
    force: bool = False,
) -> InstallOutcome:
    if not force and is_installed(tool):
        return InstallOutcome(tool.id, "already-installed")
    methods = resolve_methods(tool, platform)
    if not methods:
        return InstallOutcome(tool.id, "no-method")
    ctx = ExecContext(runner=runner, platform=platform, resolve_tag=resolve_tag)
    errors: list[Exception] = []
    for method in methods:
        if isinstance(ctx.runner, MethodAwareRunner):
            ctx.runner.method_started(method.kind)
        try:
            verified, handoff = _perform(tool, method, ctx)
            if handoff:
                return InstallOutcome(tool.id, "manual-required", method.kind, handoff=handoff)
            return InstallOutcome(tool.id, "installed", method.kind, verified=verified)
        except ChecksumMismatch as error:
            if checksum_policy == "fail":
                return InstallOutcome(tool.id, "checksum-mismatch", method.kind, (error,))
            errors.append(error)
        except (CommandError, executors.ExecutorError, VersionError) as error:
            errors.append(error)
    return InstallOutcome(tool.id, "failed", errors=tuple(errors))


def update_tool(
    tool: Tool,
    ownership: Ownership,
    update: UpdateStatus,
    runner: Runner = run_command,
) -> InstallOutcome:
    if ownership.confidence != "verified" or update.state != "available":
        return InstallOutcome(tool.id, "no-method")
    command = update_argv(tool, ownership)
    if command is None:
        return InstallOutcome(tool.id, "no-method")
    try:
        runner(command)
    except CommandError as error:
        return InstallOutcome(tool.id, "failed", ownership.method_kind, (error,))
    return InstallOutcome(tool.id, "installed", ownership.method_kind)
```

```python
# installer/session.py
class Install(Protocol):
    def __call__(
        self, tool: Tool, platform: Platform, runner: Runner, resolve_tag: TagResolver,
        *, checksum_policy: ChecksumPolicy = "fail", force: bool = False,
    ) -> InstallOutcome: ...


def run_installs(
    tools: list[Tool], platform: Platform, runner: Runner = run_command,
    resolve_tag: TagResolver = resolve_github_tag, install: Install = install_tool,
    on_mismatch: OnMismatch | None = None, *, force: bool = False,
) -> list[InstallOutcome]:
    outcomes: list[InstallOutcome] = []
    for tool in tools:
        outcome = install(tool, platform, runner, resolve_tag, force=force)
        if outcome.status == "checksum-mismatch" and on_mismatch is not None:
            choice = on_mismatch(tool.id)
            if choice == "retry":
                outcome = install(tool, platform, runner, resolve_tag, force=force)
            elif choice == "fallback":
                outcome = install(tool, platform, runner, resolve_tag, checksum_policy="continue", force=force)
            elif choice == "skip":
                outcome = replace(outcome, status="skipped")
            elif choice == "cancel":
                outcome = replace(outcome, status="cancelled")
        outcomes.append(outcome)
    return outcomes
```

In `run_plan`, require an entry for every planned tool in `statuses` and select one path per tool: `update_tool(tool, statuses[tool.id].ownership, statuses[tool.id].update, tool_runner)` for update, otherwise call `run_installs([tool], platform, tool_runner, resolve_tag, install, on_mismatch=on_mismatch, force=plan.execution_mode == "reinstall")`. The `update_tool` availability guard is mandatory even though the UI filters selections: a manually prepared update plan with a current, unknown, malformed, timed-out, failed, or unsupported update status must not invoke a package manager. Do not run post-install actions after update. Keep resolver order, checksum prompts, secure download handling, and manual handoffs in the normal/reinstall path.

```python
# installer/app.py
from installer.ownership import run_probe
from installer.status import tool_status


status_map = {tool.id: tool_status(tool, run_probe) for tool in plan.ordered}
summary = run_plan(
    plan,
    platform,
    emit=lambda _event: None,
    statuses=status_map,
    runner=runner,
    resolve_tag=resolve_tag,
    install=install,
    on_mismatch=None if options.yes else on_mismatch,
    outcomes=outcomes,
    action_context=action_context,
    approved_actions=frozenset(approved_actions),
)
```

Add `tests/test_app.py::test_run_wizard_passes_a_complete_status_map_to_run_plan`, monkeypatching `tool_status` to return one `ToolStatus` per `plan.ordered` tool and asserting that the intercepted `run_plan` call receives exactly the planned tool ids.

- [ ] **Step 4: Run engine and session tests**

Run: `uv run pytest tests/test_engine.py tests/test_session.py -v`

Expected: PASS. The engine proves forced reinstall proceeds beyond the presence guard and retains checksum failure behavior; update uses only a verified owner with an `available` update in the supplied status map, and sends no manager command for current, unknown, malformed, timed-out, failed, or unsupported statuses.

- [ ] **Step 5: Commit recovery execution**

```bash
git add installer/app.py installer/engine.py installer/install_plan.py installer/session.py tests/test_app.py tests/test_engine.py tests/test_session.py
git commit -m "feat(installs): support forced reinstall and manager updates"
```

### Task 6: Wire Catalog operation modes and completion refreshes

**Files:**
- Modify: `installer/tool_browser.py`
- Modify: `installer/catalog_tui.py`
- Modify: `installer/install_screen.py`
- Modify: `installer/wizard_app.py`
- Modify: `tests/test_tool_browser.py`
- Modify: `tests/test_catalog_tui.py`
- Modify: `tests/test_install_screen.py`
- Modify: `tests/test_wizard_app.py`

**Interfaces:**
- Produces: `CatalogScreen.Decided(result: list[str] | None, mode: ExecutionMode = "install")` and `CatalogScreen.RefreshRequested()`.
- Produces: `CatalogScreen.refresh_statuses(statuses)`, `CatalogScreen.status_for(tool_id)`, `CatalogScreen.discard_selected(ids)`, and `ToolBrowser.discard_selected(ids)`.
- Extends: `InstallScreen` with `on_complete: Callable[[Summary], None] | None`; it runs exactly once from both `_finish` and `cancel_pending` after `summary` and `finished` are set.
- Extends: `UnifiedApp` with public `refresh_catalog(include_updates: bool) -> Mapping[str, ToolStatus]`, used by the refresh-message handler and tests.
- Consumes: `StartInstall = Callable[[InstallPlan, Mapping[str, ToolStatus], ExecutionChoices, Callable[[ExecutionEvent], None]], Summary]` so the prepared plan, including its mode and update evidence, is passed intact.

- [ ] **Step 1: Write failing UI wiring tests**

```python
# tests/test_wizard_app.py
def _app(
    *,
    statuses: Mapping[str, ToolStatus] | None = None,
    refresh_statuses: Callable[[bool], Mapping[str, ToolStatus]] | None = None,
    start_install: StartInstall | None = None,
) -> UnifiedApp:
    tools = [_tool("rg"), _tool("fd")]
    catalog_statuses = statuses or _statuses_for(tools)
    build_plan = (lambda ids: _plan_for(tools, ids)) if start_install is not None else None
    return UnifiedApp(
        tools, catalog_statuses, {"search": "find things"},
        report=DoctorReport((), (), ()), guard_status={"pip": False, "npm": False},
        guard_warning=None, fix_preview="", fix=lambda: None,
        uninstall=_uninstall_inputs(), policies=_policy_inputs(),
        refresh_statuses=refresh_statuses or (lambda _include_updates: catalog_statuses),
        start_install=start_install, build_plan=build_plan,
    )


@pytest.mark.parametrize(("keys", "mode"), [
    (("space", "enter"), "install"),
    (("space", "ctrl+r"), "reinstall"),
    (("space", "ctrl+u"), "update"),
])
async def test_catalog_operation_mode_reaches_the_execution_closure(
    keys: tuple[str, ...], mode: ExecutionMode
) -> None:
    plans: list[InstallPlan] = []
    statuses = _statuses_for([_tool("rg"), _tool("fd")])
    statuses["fd"] = replace(statuses["fd"], update=UpdateStatus("available", "1.1", "fixture"))
    app = _app(statuses=statuses, start_install=lambda plan, _statuses, _choices, _emit: plans.append(plan) or _summary("fd"))
    async with app.run_test() as pilot:
        await pilot.press(*keys)
        await pilot.press("enter")
        await pilot.pause()
    assert plans[-1].execution_mode == mode
```

```python
# tests/test_wizard_app.py
async def test_refresh_request_and_completion_use_the_public_refresh_seam() -> None:
    refreshes: list[bool] = []
    app = _app(
        refresh_statuses=lambda include_updates: refreshes.append(include_updates) or _statuses(),
        start_install=lambda _plan, _statuses, _choices, _emit: _summary("fd"),
    )
    async with app.run_test() as pilot:
        await pilot.press("ctrl+f")
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
    assert refreshes == [True, False]
    assert app.catalog.selected == set()
```

```python
# tests/test_install_screen.py
async def test_completion_callback_receives_summary_after_the_final_event() -> None:
    completed: list[Summary] = []
    app, screen = _app_with_install_screen(
        [ExecutionEvent("uv", "installed", "uv: installed")], on_complete=completed.append
    )
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.pause()
    assert screen.finished is True
    assert completed == [Summary(("uv",), (), (), ())]
```

```python
# tests/test_wizard_app.py
async def test_present_app_bundle_without_path_executable_is_rendered_as_missing_health() -> None:
    tool = _tool("demo")
    statuses = _statuses_for([tool])
    statuses["demo"] = replace(
        statuses["demo"],
        installed=True,
        health=Health("missing", None, "command not found on PATH"),
    )
    app = _app(statuses=statuses)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "installed bundle; executable missing from PATH" in app.catalog.detail_text
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py -k 'operation_mode or refresh_request or completion_callback or discard_selected or missing_health' -v`

Expected: FAIL because the mode is discarded, refresh has no handler, and install completion has no callback.

- [ ] **Step 3: Implement explicit operations and atomic completion refresh**

```python
# installer/catalog_tui.py
class Decided(Message):
    def __init__(self, result: list[str] | None, mode: ExecutionMode = "install") -> None:
        super().__init__()
        self.result = result
        self.mode = mode

class RefreshRequested(Message):
    pass

def action_force_reinstall(self) -> None:
    self.post_message(self.Decided(self._selected_ids(), "reinstall"))

def action_update_selected(self) -> None:
    self.post_message(self.Decided(self._selected_ids(), "update"))

def action_refresh_catalog(self) -> None:
    self.post_message(self.RefreshRequested())

def refresh_statuses(self, statuses: Mapping[str, ToolStatus]) -> None:
    if set(statuses) != {tool.id for tool in self.tools}:
        raise ValueError("status refresh must cover the complete catalog")
    self._statuses = dict(statuses)
    self._browser.refresh_items()

def status_for(self, tool_id: str) -> ToolStatus:
    return self._statuses[tool_id]

def discard_selected(self, ids: Collection[str]) -> None:
    self._browser.discard_selected(ids)
```

Bind `ctrl+r`, `ctrl+u`, and `ctrl+f` only on `CatalogScreen`. Reject empty selections for reinstall/update with the same visible selection warning as enter. Before opening an update plan, retain only ids whose `status_for(id).update.state == "available"`; show `No selected tools have a verified available update.` if none remain.

```python
# installer/wizard_app.py
StartInstall: TypeAlias = Callable[
    [InstallPlan, Mapping[str, ToolStatus], ExecutionChoices, Callable[[ExecutionEvent], None]], Summary
]

def __init__(
    self, tools: list[Tool], statuses: Mapping[str, ToolStatus], blurbs: Mapping[str, str], *,
    report: DoctorReport, guard_status: dict[str, bool], guard_warning: str | None,
    fix_preview: str, fix: Callable[[], None], uninstall: UninstallInputs,
    policies: PolicyInputs, refresh_statuses: Callable[[bool], Mapping[str, ToolStatus]],
    initial_view: str = "catalog", initial_selected_ids: tuple[str, ...] = (),
    start_install: StartInstall | None = None, build_plan: Callable[[list[str]], InstallPlan] | None = None,
) -> None:
    super().__init__()
    self._refresh_statuses = refresh_statuses
    self._catalog = CatalogScreen(tools, statuses, blurbs)
    self._views = {
        "doctor": DoctorScreen(report, guard_status, guard_warning, fix_preview, fix),
        "uninstall": UninstallScreen(uninstall),
        "policies": PoliciesScreen(policies),
        "install": InstallScreen(on_complete=self._finish_catalog_operation),
    }

def refresh_catalog(self, include_updates: bool) -> Mapping[str, ToolStatus]:
    statuses = self._refresh_statuses(include_updates)
    self._catalog.refresh_statuses(statuses)
    return statuses

async def on_catalog_screen_refresh_requested(self, message: CatalogScreen.RefreshRequested) -> None:
    message.stop()
    self.refresh_catalog(True)

async def on_catalog_screen_decided(self, message: CatalogScreen.Decided) -> None:
    if message.result is None or self._start_install is None or self._build_plan is None:
        self.exit(message.result)
        return
    await self._open_install(message.result, message.mode)

async def _open_install(self, selected_ids: list[str], mode: ExecutionMode = "install") -> None:
    if mode == "update":
        selected_ids = [
            tool_id for tool_id in selected_ids
            if self._catalog.status_for(tool_id).update.state == "available"
        ]
        if not selected_ids:
            self._catalog.status.set("No selected tools have a verified available update.", "warn")
            return
    plan = replace(self._build_plan(selected_ids), execution_mode=mode)
    operation_statuses = {tool_id: self._catalog.status_for(tool_id) for tool_id in selected_ids}
    screen = self._views["install"]
    if not isinstance(screen, InstallScreen):
        return
    screen.prepare(
        plan,
        lambda choices, emit: self._start_install(plan, operation_statuses, choices, emit),
    )
    await self.push_screen(screen)
    self.current_view = "install"

def _finish_catalog_operation(self, summary: Summary) -> None:
    self.refresh_catalog(False)
    self._catalog.discard_selected(set(summary.installed) | set(summary.already))
```

Construct `InstallScreen(on_complete=self._finish_catalog_operation)`. Keep per-event rendering but remove its installation-status mutation callback; no intermediate event changes Catalog status. Render health detail from the immutable status map as exactly one of `version: <version>` for `healthy`, `broken: <detail>` for `broken`, `installed bundle; executable missing from PATH` for `missing` when `status.installed` is true, `command missing` for `missing` when `status.installed` is false, or `version check unsupported` for `unsupported`. Append the verified owner and `update: <state>` only from that same complete immutable status map. Do not collapse a present app bundle with missing health into the missing-install state.

```python
# installer/install_screen.py
def __init__(
    self, plan: InstallPlan | None = None,
    start: Callable[[ExecutionChoices, Callable[[ExecutionEvent], None]], Summary] | None = None,
    *, on_complete: Callable[[Summary], None] | None = None,
) -> None:
    super().__init__(view="install")
    self._on_complete = on_complete
    self._plan = plan
    self._start = start
    self.rows: dict[str, ExecutionState] = (
        {tool.id: "queued" for tool in plan.ordered} if plan is not None else {}
    )
    self.login_shell_approved = bool(plan and plan.default_enabled_sensitive_action_approvals())
    self.routine_approval = True
    self.approved_actions: frozenset[ActionKey] = frozenset()
    self.skipped_actions: frozenset[ActionKey] = frozenset()
    self._pending_actions: list[ActionKey] = []
    self._prompting_action: ActionKey | None = None
    self._pending_approved: set[ActionKey] = set()
    self._pending_skipped: set[ActionKey] = set()
    self.plan_text = self._format_plan(plan, True, self.login_shell_approved) if plan is not None else ""
    self.output_text = ""
    self.started = False
    self.finished = False
    self.summary = None

def _finish(self, summary: Summary) -> None:
    self.summary = summary
    self.finished = True
    self.query_one(FooterBar).set_actions("r retry failures | d doctor | f fix | u uninstall | esc catalog")
    if self._on_complete is not None:
        self._on_complete(summary)

def cancel_pending(self) -> None:
    if self.started or self.finished:
        return
    cancelled = tuple(tool_id for tool_id, state in self.rows.items() if state == "queued")
    for tool_id in cancelled:
        self._apply_event(ExecutionEvent(tool_id, "cancelled", f"{tool_id}: cancelled"))
    self._finish(Summary((), (), (), (), cancelled=cancelled))
```

- [ ] **Step 4: Run UI tests**

Run: `uv run pytest tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py -v`

Expected: PASS. Install, reinstall, and update modes reach the executor unchanged; `ctrl+f` runs full update discovery; a present app bundle without a PATH executable is rendered as missing health rather than an absent install; completion refreshes local status and deselects only installed or already-installed tools.

- [ ] **Step 5: Commit Catalog reliability UI**

```bash
git add installer/tool_browser.py installer/catalog_tui.py installer/install_screen.py installer/wizard_app.py tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py
git commit -m "feat(catalog): refresh health and expose recovery actions"
```

### Task 7: Compose real status and update operations at the boundary

**Files:**
- Modify: `setup.py`
- Modify: `tests/test_setup.py`
- Modify: `tests/test_installer_workflow_e2e.py`
- Modify: `README.md`

**Interfaces:**
- `_build_app(tools: list[Tool], platform: Platform, *, initial_view: str = "catalog", initial_selected_ids: tuple[str, ...] = (), link_mode: str = "centralized", enable_install: bool = True, probe: ProbeRunner = run_probe, health_runner: HealthRunner = run_health_check, update_runner: UpdateRunner = run_update_check) -> UnifiedApp` injects typed subprocess seams.
- `status_factory(include_updates: bool) -> dict[str, ToolStatus]` is passed as `UnifiedApp(refresh_statuses=...)`; tests call the app’s public `refresh_catalog`, not a private member.
- `StartInstall` receives the exact prepared `InstallPlan` plus the operation status map captured from the Catalog. Normal installs and reinstalls use a fresh `status_factory(False)` map; updates use the captured map so their verified `Ownership` and `UpdateStatus("available", ...)` reach the fail-closed execution boundary without another update query.
- Documentation: README navigation describes four navigable views (`1-4`), the policies list omits `claude-skip`, and the recovery controls describe the update availability guard.

- [ ] **Step 1: Write failing composition tests using the public seam**

```python
# tests/test_setup.py
async def test_public_catalog_refresh_skips_update_queries_until_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update_calls: list[str] = []
    monkeypatch.setattr(setup, "inspect_update", lambda tool, _owner, _runner: update_calls.append(tool.id) or UNKNOWN_UPDATE)
    app = _build_app([_tool("fd")], _platform(), enable_install=False)
    async with app.run_test():
        app.refresh_catalog(False)
        assert update_calls == []
        app.refresh_catalog(True)
    assert update_calls == ["fd"]
```

```python
# tests/test_setup.py
async def test_start_install_passes_the_prepared_mode_and_fresh_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(setup, "run_plan", lambda plan, _platform, _emit, **kwargs: received.update(plan=plan, **kwargs) or Summary(("fd",), (), (), ()))
    app = _build_app([_tool("fd")], _platform())
    async with app.run_test() as pilot:
        await pilot.press("space", "ctrl+r", "enter", "enter")
        await pilot.pause()
    assert cast(InstallPlan, received["plan"]).execution_mode == "reinstall"
    assert isinstance(received["statuses"], dict)


async def test_update_uses_the_available_status_captured_from_the_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(setup, "run_plan", lambda plan, _platform, _emit, **kwargs: received.update(plan=plan, **kwargs) or Summary(("fd",), (), (), ()))
    app = _build_app([_tool("fd")], _platform())
    app.catalog.refresh_statuses({
        "fd": replace(_status_for("fd"), update=UpdateStatus("available", "1.1", "fixture"))
    })
    async with app.run_test() as pilot:
        await pilot.press("space", "ctrl+u", "enter")
        await pilot.pause()
    status = cast(dict[str, ToolStatus], received["statuses"])["fd"]
    assert status.update.state == "available"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_setup.py tests/test_installer_workflow_e2e.py -k 'public_catalog_refresh or prepared_mode or broken_present_tool' -v`

Expected: FAIL because setup does not inject health/update runners, expose a public refresh route, or pass the prepared mode to `run_plan`.

- [ ] **Step 3: Compose the runners, status factory, and plan executor**

```python
# setup.py, inside _build_app
def status_factory(include_updates: bool) -> dict[str, ToolStatus]:
    refreshed = {
        tool.id: tool_status(tool, probe, health_runner=health_runner)
        for tool in tools
    }
    if not include_updates:
        return refreshed
    return {
        tool_id: replace(
            status,
            update=inspect_update(status.tool, status.ownership, update_runner),
        )
        for tool_id, status in refreshed.items()
    }

statuses = status_factory(False)

def _start_install(
    plan: InstallPlan,
    operation_statuses: Mapping[str, ToolStatus],
    choices: ExecutionChoices,
    emit: Callable[[ExecutionEvent], None],
) -> Summary:
    statuses = operation_statuses if plan.execution_mode == "update" else status_factory(False)
    return run_plan(
        plan, platform, emit,
        statuses=statuses,
        on_mismatch=choices.on_mismatch,
        approved_actions=choices.approved_actions,
        skipped_actions=choices.skipped_actions,
        captured_runner=run_captured_command,
        interactive_runner=_run_interactive_action,
    )
```

Pass `refresh_statuses=status_factory` to `UnifiedApp`. Keep real environment discovery and runner construction in `setup.py`; keep parsing and status decisions in `installer/`. Do not access private app methods in tests and do not add a Pyright suppression.

Replace every README reference to `1`–`5`, `1-5`, or five numbered views with four-view wording. In particular, change the interactive-wizard description to say `number keys 1`–`4` switch the catalog, doctor, uninstall, and policies views; change the Selecting tools shortcut row to `Ctrl+P, or 1–4`; and replace the PATH doctor text’s separate Fix view with the Doctor view’s `enter` action. Replace the shell-tweak introduction and table with this content, which removes `claude skip-permissions` while documenting the retained independent OpenCode policy:

```markdown
### Shell tweak bundles

The policies view surfaces three curated, independently-toggleable shell-tweak
bundles. Each writes its own marker block into `~/.myshellrc` (already sourced by
bash and zsh) and takes effect in a new shell. Enabling or disabling one never
touches another bundle or your own content.

| Bundle | Available on | What it adds |
| --- | --- | --- |
| **Docker shortcuts** | all | `docker-ps` (live container table via `watch`), `docker-stats`, `docker-memory` |
| **Countdown helper** | all | `wait_time <secs>` - a portable terminal countdown |
| **apt selective upgrade** | Linux | `apt-upgrade` - upgrades only packages that have available updates |

### OpenCode auto mode

The policies view can also toggle **OpenCode auto mode**. It writes
`alias opencode='opencode --auto'` only inside its own managed marker blocks and
removes only those blocks when disabled.
```

Add this README section immediately after Selecting tools:

```markdown
### Catalog recovery controls

- `enter`: install selected tools using the normal already-installed safeguard.
- `ctrl+r`: force reinstall selected tools, including tools present but failing their version check.
- `ctrl+u`: update selected tools only after the Catalog verified the owning package manager and found an update.
- `ctrl+f`: refresh health, versions, ownership, and available updates.
```

- [ ] **Step 4: Run composition, workflow, and full quality gates**

Run: `uv run pytest tests/test_setup.py tests/test_installer_workflow_e2e.py -v`

Expected: PASS.

Run: `make validate && make test`

Expected: PASS with Ruff, formatting, Pyright, Bandit, Vulture, ShellCheck, and the complete pytest suite succeeding.

- [ ] **Step 5: Commit composition and documentation**

```bash
git add setup.py README.md tests/test_setup.py tests/test_installer_workflow_e2e.py
git commit -m "feat(setup): compose catalog health and update refresh"
```

## Plan Self-Review

- **Spec coverage:** Task 1 removes all agent-environment imports, policy composition, view registration, navigation, skill lifecycle code, registry entries, and stale four-view public contracts in `tests/test_ui_common.py`. Task 2 retains only the approved reversible OpenCode alias policy. Tasks 3-4 define presence, app-bundle-without-CLI health, ownership, immutable initial update state, exact update parsing, and normalized subprocess failure behavior. Task 5 executes all three modes, proves forced reinstall retains checksum enforcement, and rejects update execution unless status is `available`. Tasks 6-7 preserve mode through the prepared plan, render missing executable health distinctly, wire refresh messages and completion callbacks, compose the real status factory, and update README navigation and policy content.
- **Deferred scope:** No task creates shared critical-tool hints or restores agent configuration automation.
- **Placeholder scan:** The plan has no TODOs, deferred code paths, quality suppressions, or unspecified manager output formats. Each manager has fixed query argv, accepted output shape, exact match rule, current result, and failure result.
- **Type consistency:** `CommandResult.failure`, `ExecutionMode`, `InstallPlan.execution_mode`, `Ownership.method_kind`, `Ownership.package`, `UpdateStatus`, `ToolStatus.update`, `StartInstall`, and `UnifiedApp.refresh_catalog` use the same names and types in every producing and consuming task.
