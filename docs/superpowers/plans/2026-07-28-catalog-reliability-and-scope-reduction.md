# Catalog Reliability and Scope Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the installer to its package catalog responsibilities, then make the Catalog accurately report executable health, verified package-manager ownership, available updates, and explicit recovery actions.

**Architecture:** Remove agent-environment and skill-repository code as one vertical slice, including the centralized view registry and policy composition that import it. Model presence, health, ownership, and update availability independently in immutable status values. Homebrew formulae receive path-verified update support; Homebrew casks are explicitly excluded because the installer copies their bundles into `~/Applications`. The Catalog emits an operation mode; `UnifiedApp` places that mode on the prepared `InstallPlan`, passes that exact plan to the executor, and replaces the complete catalog status map only after `InstallScreen` reports a final summary.

**Tech Stack:** Python 3.11, Textual, TOML registry, pytest, Ruff, Pyright.

## Global Constraints

- Keep the catalog registry declarative. It must not contain arbitrary shell commands or arbitrary executable paths for health or update operations.
- A PATH or app-bundle match proves presence only. A non-zero version check is a broken installation, not a missing tool.
- Every subprocess used for health, ownership, or update discovery must use `stdin=subprocess.DEVNULL`, capture text output, and set `timeout=5`.
- `TimeoutExpired` and `OSError` from health or update discovery must be converted into status detail, never propagated into the Catalog UI.
- Initial and post-execution status refreshes run only presence, health, and ownership checks. Network-capable update discovery runs only from the explicit Catalog refresh action.
- Only a verified owner with an `available` update may receive an in-app update command. Every update state, including current, unknown, unsupported, malformed, timed-out, and failed checks, is rendered with its status detail and never guessed.
- Homebrew casks are excluded from ownership verification and in-app update discovery because the cask executor installs bundles under `~/Applications`, outside the cask prefix. Do not query, parse, or execute `brew outdated --cask` in this change.
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
- `installer/ownership.py` resolves the CLI once and verifies that its canonical path belongs to the exact package declared by a supported install method.
- `installer/updates.py` provides bounded update discovery, strict manager-specific parsing, and reviewed update argv construction.
- `installer/status.py` composes immutable presence, health, ownership, and update values.
- `installer/app.py`, `installer/engine.py`, `installer/install_plan.py`, and `installer/session.py` construct and execute install, reinstall, and verified update plans; every `run_plan` caller supplies a complete immutable status map, and the CLI status seam prevents tests from running real health or ownership subprocesses.
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
- Modify: `installer/resolve.py:6-60`
- Modify: `installer/status.py:1-86`
- Modify: `installer/catalog_tui.py:24-45,252-273`
- Modify: `installer/install_screen.py:230-258`
- Modify: `installer/uninstall.py`
- Modify: `installer/postinstall.py:24-31,37-38,63-79,238-282`
- Modify: `setup.py:21-27,46-51,151-223,295-306`
- Modify: `Makefile:50-79`
- Modify: `installer/registry.toml`
- Modify: `tests/test_model.py`, `tests/test_resolve.py`, `tests/test_status.py`, `tests/test_catalog_tui.py`, `tests/test_wizard_app.py`, `tests/test_ui_common.py`, `tests/test_policy.py`, `tests/test_policies_e2e.py`, `tests/test_registry.py`, `tests/test_uninstall.py`, `tests/test_install_screen.py`, `tests/test_postinstall.py`, and `tests/test_container_smoke.py`

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

```python
# tests/test_container_smoke.py, inside test_container_target_uses_an_unprivileged_isolated_invocation
assert "uv run pytest tests/test_installer_workflow_e2e.py -q" in run
assert "test_agent_environment_e2e.py" not in run
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

Remove `skill_pack` from `METHOD_KINDS`, `installer/resolve.py`'s `_RANK`, and its applicable-method branch; remove all skill lifecycle types, parsing functions, `Tool.skill_lifecycle`, `Tool.owner_probes`, and `OWNER_PROBES` from the model. Delete `installer/skill_lifecycle.py` after removing its imports from `installer/engine.py`, `installer/status.py`, and `tests/test_catalog_tui.py`; remove its remaining consumers from `installer/catalog_tui.py`, `installer/install_screen.py`, and `installer/uninstall.py`. Delete `tests/test_skill_lifecycle.py`, `test_textual_worker_never_hands_its_tty_to_guided_host_setup` from `tests/test_install_screen.py`, and the lifecycle cases in `tests/test_status.py`, `tests/test_registry.py`, and `tests/test_catalog_tui.py`. In `installer/postinstall.py`, remove `apply_block` from imports, `_AGENT_REFERENCE_BEGIN`, `_AGENT_REFERENCE_END`, `ActionContext.agent_reference_paths`, `write_agent_reference`, and the `"write_agent_reference"` handler entry. Delete `test_write_agent_reference_preserves_user_text_and_is_idempotent` and remove `agent_reference_paths` from the test context helper in `tests/test_postinstall.py`. Delete the seven registry tables named in the focused test, including nested lifecycle tables. Replace the `test-container` command in `Makefile` with `uv run pytest tests/test_installer_workflow_e2e.py -q`; update the retained command assertion in `tests/test_container_smoke.py` to the same string. Remove agent imports, constructor parameters, and agent composition from `setup.py`. Update or delete tests that import agent modules, expect the fifth navigation key, inspect lifecycle status, agent-reference behavior, or load a removed registry tool. In `tests/test_ui_common.py`, change view-order assertions to the four navigable views, change every `1-5 views` footer expectation to `1-4 views`, and retain the non-navigable `install` view assertion. In `tests/test_resolve.py`, retain the ordinary method-ladder tests and add a regression assertion that `skill_pack` is absent from both `installer.model.METHOD_KINDS` and `installer.resolve._RANK`.

- [ ] **Step 4: Run the affected test groups**

Run: `uv run pytest tests/test_model.py tests/test_resolve.py tests/test_registry.py tests/test_status.py tests/test_catalog_tui.py tests/test_wizard_app.py tests/test_ui_common.py tests/test_policy.py tests/test_policies_e2e.py tests/test_uninstall.py tests/test_install_screen.py tests/test_postinstall.py tests/test_container_smoke.py -v`

Expected: PASS. `UnifiedApp` neither binds nor navigates to agent environment, and importing `installer.policy` does not import a deleted module.

- [ ] **Step 5: Verify no removed lifecycle implementation remains**

Run: `uv run python -c "from pathlib import Path; roots = (Path('installer'), Path('tests'), Path('setup.py')); matches = [path for root in roots for path in ((root.rglob('*.py') if root.is_dir() else (root,))) if 'skill_lifecycle' in path.read_text() or 'skill_pack' in path.read_text()]; assert not matches, matches"`

Expected: PASS with no output. No production or test module references the deleted `installer.skill_lifecycle` implementation.

- [ ] **Step 6: Commit the scope reduction**

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
- Modify: `installer/ownership.py`
- Modify: `installer/status.py`
- Modify: `tests/test_model.py`
- Create: `tests/test_health.py`
- Modify: `tests/test_status.py`
- Modify: `tests/test_ownership.py`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Produces: `CommandResult(returncode: int, stdout: str, stderr: str, failure: str | None = None)`.
- Produces: `HealthState = Literal["missing", "healthy", "broken", "unsupported"]`, `Health`, `UNKNOWN_HEALTH = Health("unsupported", None, "health not inspected")`, `HealthRunner`, `run_health_check`, and `inspect_health`.
- Produces: `ExecutableResolution = Path | None`, `ExecutableResolver = Callable[[str], ExecutableResolution]`, and `resolve_executable(cmd: str) -> ExecutableResolution`. `resolve_executable` calls `shutil.which(cmd)`, canonicalizes a found result with `Path.resolve(strict=True)`, and returns `None` for a missing or unresolvable executable. `tool_status` invokes its injected resolver exactly once, then passes that one result to presence, health, and ownership evaluation; neither `inspect_health` nor `detect_owner` performs PATH lookup.
- Extends: `Tool.cmd` with bare-executable-name validation and `Tool.version_args: tuple[str, ...] | None`; omitted TOML defaults to `("--version",)`, while `version_args = []` becomes `None`.
- Extends: `ToolStatus` with `health: Health = UNKNOWN_HEALTH`; existing three-argument `ToolStatus(tool, installed, ownership)` constructors remain valid and display an explicit unsupported, uninspected health state. `tool_status` always supplies inspected health. `installer.audit.ToolStatus` is a separate audit-only two-field dataclass and is unchanged.

- [ ] **Step 1: Write failing health and runner-failure tests**

```python
# tests/test_health.py
def test_timeout_renders_broken_health_with_a_diagnostic() -> None:
    tool = _tool()
    health = inspect_health(
        tool,
        executable=Path("/fixture/bin/demo"),
        runner=lambda _argv: CommandResult(124, "", "", "version check timed out after 5 seconds"),
    )
    assert health == Health("broken", None, "version check timed out after 5 seconds")


def test_launch_failure_renders_broken_health_with_a_diagnostic() -> None:
    tool = _tool()
    health = inspect_health(
        tool,
        executable=Path("/fixture/bin/demo"),
        runner=lambda _argv: CommandResult(1, "", "", "version check could not start: missing"),
    )
    assert health.state == "broken"
    assert health.detail == "version check could not start: missing"


def test_present_app_bundle_without_a_path_executable_has_missing_health(tmp_path: Path) -> None:
    app_root = tmp_path / "Applications"
    (app_root / "Demo.app").mkdir(parents=True)
    tool = _tool(Method("app", {"app": "Demo.app"}))

    status = tool_status(
        tool,
        lambda _argv: "",
        app_roots=(app_root,),
        health_runner=lambda _argv: _result(),
        executable_resolver=lambda _cmd: None,
    )

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


@pytest.mark.parametrize("cmd", ["/tmp/demo", "./demo", "bin/demo", "../demo"])
def test_loader_rejects_a_command_path_used_for_health_inspection(tmp_path: Path, cmd: str) -> None:
    manifest = _write(tmp_path, f'''
[[tool]]
id = "demo"
cmd = "{cmd}"
category = "dev"
[[tool.method]]
kind = "brew"
formula = "demo"
''')

    with pytest.raises(ValueError, match="cmd must be a bare executable name"):
        load_tools(manifest)


def test_health_inspection_refuses_an_invalid_directly_constructed_command() -> None:
    tool = Tool("demo", "Demo", "dev", "/tmp/demo", (Method("brew", {"formula": "demo"}),))

    health = inspect_health(tool, executable=Path("/tmp/demo"), runner=lambda _argv: _result())

    assert health == Health("unsupported", None, "command is not a bare executable name")
```

```python
# tests/test_status.py
def test_status_default_marks_health_as_uninspected() -> None:
    status = ToolStatus(
        _tool(),
        False,
        Ownership(None, "unknown", "not installed"),
    )

    assert status.health == UNKNOWN_HEALTH
```

```python
# tests/test_status.py
def test_status_resolves_the_executable_once_for_presence_health_and_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import installer.status as status

    executable = Path("/fixture/bin/demo")
    resolved: list[str] = []
    health_argv: list[list[str]] = []
    ownership_executables: list[Path | None] = []
    monkeypatch.setattr(
        status,
        "detect_owner",
        lambda _tool, _probe, result: ownership_executables.append(result)
        or Ownership(None, "unknown", "not package managed"),
    )

    result = status.tool_status(
        _tool(),
        lambda _argv: "",
        executable_resolver=lambda cmd: resolved.append(cmd) or executable,
        health_runner=lambda argv: health_argv.append(argv) or _result(),
    )

    assert result.installed is True
    assert resolved == ["demo"]
    assert health_argv == [[str(executable), "--version"]]
    assert ownership_executables == [executable]
```

```python
# tests/test_registry.py
def test_shipped_health_version_args_have_only_the_explicit_sdkman_exception() -> None:
    version_args = {tool.id: tool.version_args for tool in load_tools(REGISTRY)}

    assert version_args["sdkman"] is None
    assert {tool_id for tool_id, args in version_args.items() if args is None} == {"sdkman"}
    assert all(args == ("--version",) for args in version_args.values() if args is not None)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_health.py tests/test_model.py tests/test_registry.py tests/test_status.py -k 'health or version_args or timeout or launch_failure or resolves_the_executable_once' -v`

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


def inspect_health(
    tool: Tool, *, executable: ExecutableResolution, runner: HealthRunner
) -> Health:
    if not is_bare_command_name(tool.cmd):
        return Health("unsupported", None, "command is not a bare executable name")
    if tool.version_args is None:
        return Health("unsupported", None, "no executable version check declared")
    if executable is None:
        return Health("missing", None, "command not found on PATH")
    result = runner([str(executable), *tool.version_args])
    if result.returncode != 0:
        detail = result.failure or result.stderr.strip() or result.stdout.strip() or "version command failed"
        return Health("broken", None, detail)
    version = next((line.strip() for line in result.stdout.splitlines() if line.strip()), None)
    return Health("healthy", version, "version command succeeded")
```

```python
# installer/ownership.py
ExecutableResolution = Path | None
ExecutableResolver = Callable[[str], ExecutableResolution]


def resolve_executable(cmd: str) -> ExecutableResolution:
    found = shutil.which(cmd)
    if found is None:
        return None
    try:
        return Path(found).resolve(strict=True)
    except OSError:
        return None
```

```python
# installer/model.py
def is_bare_command_name(value: str) -> bool:
    return bool(value) and "/" not in value and value not in {".", ".."}
```

Define `ExecutableResolution`, `ExecutableResolver`, and `resolve_executable` in `installer/ownership.py`, then import those contracts into `installer.health` and `installer.status`; `detect_owner` accepts an `executable: ExecutableResolution` argument and never resolves it itself. Import `is_bare_command_name` into `installer.health`. Define `UNKNOWN_HEALTH = Health("unsupported", None, "health not inspected")` in `installer.health` and set `ToolStatus.health: Health = UNKNOWN_HEALTH`; this preserves every existing three-argument production and test constructor while making its display state explicit. `tool_status` always passes an inspected `Health`, so only compatibility fixtures and callers that intentionally do not inspect health use the default. Do not alter `installer.audit.ToolStatus`: it is a distinct audit-report value with only `tool` and `installed` fields. Use the same predicate in `load_tools`: reject a declared `cmd` containing `/` or equal to `.` or `..` with `ValueError("tool '<id>': cmd must be a bare executable name")`. Parse `version_args` only when the registry value is a list of strings. Reject a string or non-string member with `ValueError`; normalize an omitted field to `("--version",)` and an empty list to `None`. Split the existing bundle scan from `is_installed` into a private helper. `tool_status` must not call `is_installed`: it resolves once before calculating presence, computes `installed = executable is not None or _app_bundle_installed(tool, app_roots)`, and passes the exact result to `inspect_health` and `detect_owner`. Retain `is_installed` as the direct-call wrapper that resolves once for its own callers. The health runner executes the canonical path, not `tool.cmd`, so the `tool_status` path cannot trigger a second PATH lookup. Launch and timeout failures render as `Health("broken", ...)` rather than aborting startup or refresh. An app or cask bundle found in `app_roots` is therefore `installed=True` with `Health("missing", None, "command not found on PATH")` when its CLI does not resolve; it is not an absent tool.

In `installer/registry.toml`, add `version_args = []` only to `sdkman`. The command `sdkman-init.sh` is a shell initialization script intended to be sourced and must never be launched for a version check. After Task 1 removes all `skill_pack` tools, every other shipped `cmd` is an executable command with the standard `("--version",)` contract; do not add an exception for `code`, `jetbrains-toolbox`, `subl`, or either `drawio` entry. In `tests/test_registry.py`, load the shipped registry and assert that `sdkman` is the only tool whose normalized `version_args` is `None`, while every other retained tool has `("--version",)`. This test is the complete exception list and must be updated whenever a non-versioned command is added.

```toml
# installer/registry.toml, the existing sdkman table
id = "sdkman"
cmd = "sdkman-init.sh"
version_args = []
```

- [ ] **Step 4: Run health, model, and status tests**

Run: `uv run pytest tests/test_health.py tests/test_model.py tests/test_ownership.py tests/test_registry.py tests/test_status.py -v`

Expected: PASS. A stale executable, timeout, and launch failure are present-but-broken; an app-bundle tool whose CLI is absent from `PATH` is present with missing health; a bundle-only tool with `version_args = []` is present with unsupported health; legacy three-argument status construction has the explicit `UNKNOWN_HEALTH` default.

- [ ] **Step 5: Commit health support**

```bash
git add installer/health.py installer/model.py installer/ownership.py installer/status.py installer/registry.toml tests/test_health.py tests/test_model.py tests/test_ownership.py tests/test_registry.py tests/test_status.py
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
- Extends: `Ownership` with `method_kind: str | None = None`, `package: str | None = None`, and `executable: Path | None = None`. `confidence == "verified"` means the canonical executable resolved for `Tool.cmd` is proven to belong to that exact declared package, not merely that the manager lists a same-named package.
- Consumes Task 3's `ExecutableResolution`, `ExecutableResolver`, and `resolve_executable`. `tool_status` resolves once, uses that result for PATH presence, health, and ownership, and still recognizes an app bundle as present without assigning it a verified package owner.
- Produces: `UpdateState = Literal["unknown", "current", "available", "unsupported"]`, `UpdateStatus(state: UpdateState, latest_version: str | None, detail: str)`, `UpdateRunner`, `run_update_check`, `inspect_update`, and `update_argv`.
- Extends: frozen `ToolStatus` with `update: UpdateStatus = UpdateStatus("unknown", None, "update discovery not requested")`. `tool_status` always supplies that value during initial and post-operation refreshes; only `status_factory(True)` replaces it with `inspect_update(...)` results for the complete status map.
- Behavior: `run_update_check` uses the same five-second, closed-stdin contract as health and returns `CommandResult` with `failure` set for timeout or launch failure.
- Behavior: only an exact declared package in the manager-specific documented success condition establishes `available`; an adapter's documented current result establishes `current`; any unrelated, malformed, or failed response is `unknown`. Homebrew casks are `unsupported`: the installer copies them to `~/Applications`, so this change cannot prove their executable or bundle belongs to a cask. `update_argv` also requires the verified ownership manager, method kind, and package to match one supported method declared by the supplied `Tool` before it returns a command.
- Behavior: an ownership adapter may return `verified` only after its manager-specific path query proves that `Ownership.executable` belongs to the declared package. A package-list result alone is insufficient. If a resolved executable is outside every declared package location, ownership remains `unknown`, update discovery returns `unknown` with that detail, and `update_argv` returns `None`.

- [ ] **Step 1: Write failing ownership, runner, and parser-contract tests**

```python
# tests/test_updates.py
@pytest.mark.parametrize(
    ("ownership", "result", "expected"),
    [
        (_owner("pnpm", "node", "demo"), CommandResult(1, '{"demo":{"current":"1.0","latest":"1.1","wanted":"1.1","isDeprecated":false,"dependencyType":"dependencies"}}', ""), "available"),
        (_owner("pnpm", "node", "demo"), CommandResult(0, "{}", ""), "current"),
        (_owner("Homebrew", "brew", "demo"), CommandResult(0, '{"formulae":[{"name":"demo","current_version":"1.0","latest_version":"1.1"}],"casks":[]}', ""), "available"),
        (_owner("apt", "apt", "demo"), CommandResult(0, "Reading package lists...\\nInst demo [1.0] (1.1 Debian:12/stable [amd64])\\nConf demo (1.1 Debian:12/stable [amd64])\\n", ""), "available"),
        (_owner("dnf", "dnf", "demo"), CommandResult(100, "demo.x86_64 1.1 repo\\n", ""), "available"),
        (_owner("pacman", "pacman", "demo"), CommandResult(0, "demo 1.0 -> 1.1\\n", ""), "available"),
    ],
)
def test_documented_manager_output_is_parsed_for_the_exact_package(
    ownership: Ownership, result: CommandResult, expected: UpdateState
) -> None:
    update = inspect_update(_tool(ownership.package or "demo"), ownership, lambda _argv: result)
    assert update.state == expected
    if expected == "available":
        assert update.latest_version == "1.1"
    else:
        assert update.latest_version is None


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
    assert run_update_check(["pnpm", "outdated", "--global", "--format", "json", "demo"]).failure == expected


def test_update_runner_closes_stdin_captures_output_and_bounds_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(subprocess, "run", lambda _argv, **kwargs: calls.append(kwargs) or _completed())
    assert run_update_check(["pnpm", "outdated", "--global", "--format", "json", "demo"]).returncode == 0
    assert calls == [{"check": False, "stdin": subprocess.DEVNULL, "capture_output": True, "text": True, "timeout": 5}]


def test_initial_status_marks_update_discovery_as_not_requested() -> None:
    status = tool_status(_tool("demo"), lambda _argv: "", health_runner=lambda _argv: _result())

    assert status.update == UpdateStatus("unknown", None, "update discovery not requested")
```

```python
# tests/test_updates.py
def test_cask_update_is_unsupported_without_running_a_manager() -> None:
    tool = Tool(
        "demo",
        "Demo",
        "dev",
        "demo",
        (Method("cask", {"cask": "demo"}),),
    )
    ownership = Ownership(
        "Homebrew",
        "unknown",
        "Homebrew cask ownership is not verified for ~/Applications bundles",
        "cask",
        "demo",
        None,
    )
    commands: list[list[str]] = []

    update = inspect_update(tool, ownership, lambda argv: commands.append(argv) or _result())

    assert update == UpdateStatus(
        "unsupported",
        None,
        "Homebrew cask updates are unsupported for installer-managed ~/Applications bundles",
    )
    assert update_argv(tool, ownership) is None
    assert commands == []
```

```python
# tests/test_updates.py
@pytest.mark.parametrize(
    ("ownership", "expected"),
    [
        (_owner("pnpm", "node", "demo"), ["pnpm", "outdated", "--global", "--format", "json", "demo"]),
        (_owner("Homebrew", "brew", "demo"), ["brew", "outdated", "--json=v2", "--formula", "demo"]),
        (_owner("apt", "apt", "demo"), ["apt-get", "--simulate", "--only-upgrade", "install", "demo"]),
        (_owner("dnf", "dnf", "demo"), ["dnf", "check-update", "demo"]),
        (_owner("pacman", "pacman", "demo"), ["pacman", "-Qu", "demo"]),
    ],
)
def test_each_reviewed_adapter_uses_its_fixed_query_argv(ownership: Ownership, expected: list[str]) -> None:
    seen: list[list[str]] = []
    inspect_update(_tool("demo"), ownership, lambda argv: seen.append(argv) or CommandResult(0, "", ""))
    assert seen == [expected]


def test_update_argv_rejects_a_verified_package_not_declared_by_the_tool() -> None:
    tool = _tool("demo")
    foreign = Ownership("pnpm", "verified", "pnpm lists other", "node", "other")

    assert update_argv(tool, foreign) is None
```

```python
# tests/test_ownership.py
def test_declared_package_does_not_verify_an_executable_owned_elsewhere(tmp_path: Path) -> None:
    managed_root = tmp_path / "brew" / "Cellar" / "ripgrep" / "14.1.0"
    managed_executable = managed_root / "bin" / "rg"
    managed_executable.parent.mkdir(parents=True)
    managed_executable.write_text("")
    foreign_executable = tmp_path / "downloads" / "bin" / "rg"
    foreign_executable.parent.mkdir(parents=True)
    foreign_executable.write_text("")
    tool = _tool(methods=(Method("brew", {"formula": "ripgrep"}),))

    owner = detect_owner(
        tool,
        probe=lambda argv: str(managed_root) if argv == ["brew", "--prefix", "--formula", "ripgrep"] else pytest.fail(argv),
        executable=foreign_executable.resolve(),
    )

    assert owner.confidence == "unknown"
    assert "outside Homebrew formula ripgrep" in owner.detail
    assert update_argv(tool, owner) is None


def test_owner_verifies_a_symlinked_path_only_when_its_target_is_in_the_declared_package(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "pnpm" / "global" / "node_modules" / "demo"
    package_executable = package_root / "bin" / "demo"
    package_executable.parent.mkdir(parents=True)
    package_executable.write_text("")
    command_link = tmp_path / "pnpm" / "bin" / "demo"
    command_link.parent.mkdir(parents=True)
    command_link.symlink_to(package_executable)
    tool = _tool(methods=(Method("node", {"npm_pkg": "demo"}),))

    owner = detect_owner(
        tool,
        probe=lambda argv: str(package_root.parent) if argv == ["pnpm", "root", "--global"] else pytest.fail(argv),
        executable=command_link.resolve(),
    )

    assert owner == Ownership("pnpm", "verified", "pnpm owns demo executable", "node", "demo", package_executable)


def test_cask_ownership_is_unverified_without_a_package_manager_probe() -> None:
    tool = _tool(methods=(Method("cask", {"cask": "demo"}),))

    owner = detect_owner(
        tool,
        probe=lambda _argv: pytest.fail("cask ownership must not query Homebrew"),
        executable=None,
    )

    assert owner == Ownership(
        "Homebrew",
        "unknown",
        "Homebrew cask ownership is not verified for ~/Applications bundles",
        "cask",
        "demo",
        None,
    )
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_ownership.py tests/test_updates.py -v`

Expected: FAIL because ownership has no package identity or resolved-executable evidence and `installer.updates` does not exist.

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
    ("pnpm", "node"): lambda package: ["pnpm", "outdated", "--global", "--format", "json", package],
    ("Homebrew", "brew"): lambda package: ["brew", "outdated", "--json=v2", "--formula", package],
    ("apt", "apt"): lambda package: ["apt-get", "--simulate", "--only-upgrade", "install", package],
    ("dnf", "dnf"): lambda package: ["dnf", "check-update", package],
    ("pacman", "pacman"): lambda package: ["pacman", "-Qu", package],
}
```

```python
# installer/ownership.py
def _under(executable: Path, root: Path) -> bool:
    try:
        executable.relative_to(root.resolve(strict=True))
    except ValueError:
        return False
    except OSError:
        return False
    return True


def _brew_owner(method: Method, executable: Path, probe: ProbeRunner) -> Ownership | None:
    package = method.params["formula"]
    if not isinstance(package, str):
        return None
    prefix = _run(probe, ["brew", "--prefix", "--formula", package])
    if prefix is None:
        return None
    try:
        package_root = Path(prefix.strip()).resolve(strict=True)
    except OSError:
        return None
    if not _under(executable, package_root):
        return Ownership(None, "unknown", f"{executable} is outside Homebrew {method.kind} {package}", None, None, executable)
    return Ownership("Homebrew", "verified", f"Homebrew owns {package} executable", method.kind, package, executable)
```

In `detect_owner`, consume the `executable: ExecutableResolution` supplied by `tool_status`; it must not call `resolve_executable`, `shutil.which`, or any other PATH lookup. If that result is `None`, return `Ownership(None, "unknown", "command not found on PATH", None, None, None)` and do not mistake an app bundle for a package-owned command. Iterate recognized declared methods in catalog order, passing the same canonical executable to each adapter. Preserve the first unknown ownership detail but continue through every recognized declared method; return immediately only for a verified path owner, then return the saved mismatch after all methods fail. For `brew`, use the displayed `brew --prefix --formula <package>` query and accept the owner only when the canonical executable is below the canonical prefix. A `cask` method has no ownership adapter: `_cask` installs its bundle with `brew install --cask --appdir=~/Applications`, which places it outside `brew --prefix --cask <package>` and may not expose a CLI. Return `Ownership("Homebrew", "unknown", "Homebrew cask ownership is not verified for ~/Applications bundles", "cask", package, executable)` for a declared cask after all supported methods fail. `inspect_update` must map that cask ownership value to `UpdateStatus("unsupported", None, "Homebrew cask updates are unsupported for installer-managed ~/Applications bundles")` without calling `update_runner`; `update_argv` must return `None`. For `node`, query `pnpm root --global`, canonicalize `<output>/<npm_pkg>`, and accept only when the executable is below that package directory. For `apt`, query `dpkg-query -S <canonical-executable>` and accept exactly one `<package>[:arch]: <canonical-executable>` record whose package segment before `:arch` equals the declared `package`. For `dnf`, query `rpm -q --qf %{NAME}\\n -f <canonical-executable>` and accept exactly one line equal to declared `package`. For `pacman`, query `pacman -Qqo <canonical-executable>` and accept exactly one line equal to declared `package`. Return an unknown `Ownership` carrying the canonical executable and the first mismatch detail when no declared package owns that path; never fall back to a package-list probe. Methods without one of the five reviewed package-manager adapters return unknown ownership and cannot produce an update command.

Handle a declared cask before the generic `executable is None` return: select the first declared cask in catalog order and return the displayed unknown cask `Ownership` with `executable=None`. This gives an installed cask bundle without a PATH CLI the explicit unsupported update state while still refusing to claim verified ownership. For a resolved executable, apply the same cask fallback only after every supported path-ownership adapter fails.

Keep `tool_status` as the sole resolution boundary: call `resolve_executable` exactly once, use its result for PATH presence, pass it to `inspect_health` for the bounded canonical-path version command, and pass it to ownership detection. Its bundle-presence test remains independent. Pass the same injected `ExecutableResolver` through `tool_status` in tests so every test remains offline. Add a status integration test with a counting resolver, a recording health runner, and a recording ownership detector; it must assert one resolver call, the canonical executable argv for health, and the exact same `Path` object delivered to ownership. A manager ownership probe never executes the tool itself.

```python
# tests/test_updates.py
def _owner(manager: str, method_kind: str, package: str) -> Ownership:
    return Ownership(
        manager,
        "verified",
        f"{manager} owns {package} executable",
        method_kind,
        package,
        Path("/fixture/bin/demo"),
    )
```

In `tests/test_ownership.py`, replace the former package-list fixtures with path-ownership fixtures: each fixture creates its declared package root and resolved executable under `tmp_path`, injects that executable into `detect_owner`, and returns the precise command output listed above. Retain one unknown case per manager where the manager reports a different package for the same path, plus the displayed same-named-package foreign-executable and symlink tests. In `tests/test_status.py`, inject `executable_resolver=lambda _cmd: executable` into the verified-owner test and assert the recorded executable equals that path; update every `Ownership` fixture with `method_kind`, `package`, and `executable` where it is meant to be verified. In `tests/test_updates.py`, use the displayed `_owner` helper for all six parser adapters, so parser/update-command tests carry path-verified ownership evidence rather than constructing a package-list-only owner.

Implement `_parse_outdated` with this closed contract. For every available result, use the listed value as `UpdateStatus.latest_version`; all current, unknown, and unsupported results use `latest_version=None`:

| Manager / method | Accepted available output | Exact match rule | `latest_version` extraction | Current output |
| --- | --- | --- | --- | --- |
| pnpm / node | exit 1 with a complete JSON object keyed by package name; the target value has string `current`, `latest`, and `wanted`, plus boolean `isDeprecated` and string `dependencyType` | the sole key is `package` | target value's string `latest` | exit 0 with JSON `{}` |
| Homebrew / brew | JSON object with list `formulae`; member has string `name`, `current_version`, `latest_version` | `name == package` | string `latest_version` | `formulae == []` and `casks == []` |
| apt / apt | `apt-get --simulate --only-upgrade install package` output has exactly one documented simulation unpack record `Inst package [installed] (latest source [arch])`, optionally followed by its matching `Conf package (...)` record | package following `Inst` equals `package`; no `Inst`, `Conf`, or `Remv` record names another package | first whitespace-separated token inside `(` from the `Inst` record | exit 0 with no documented simulation operation records |
| dnf / dnf | exit 100 and, after discarding only one line matching `^Last metadata expiration check: .+$`, exactly one line `package.arch version repository` | substring before `.arch` equals `package`; only `x86_64`, `aarch64`, `armhfp`, or `noarch` suffixes are accepted | second whitespace-separated field | exit 0 with no remaining lines after discarding that same metadata line |
| pacman / pacman | one line `package current -> latest` | first whitespace-separated token equals `package` | fourth whitespace-separated field | exit 0 with no lines |

Create one named pytest fixture for each cell in the table: `pnpm_current`, `pnpm_available`, `pnpm_malformed`, `pnpm_nonzero`, `brew_formula_current`, `brew_formula_available`, `brew_formula_malformed`, `brew_formula_nonzero`, `apt_current`, `apt_available`, `apt_malformed`, `apt_nonzero`, `dnf_current`, `dnf_available`, `dnf_malformed`, `dnf_nonzero`, `pacman_current`, `pacman_available`, `pacman_malformed`, and `pacman_nonzero`. Each fixture returns its manager's exact `Ownership` plus one `CommandResult`; current uses the table's empty JSON result, no APT simulation operation records, or the text adapter's empty result; available uses the displayed accepted output; malformed uses invalid JSON, a malformed simulation operation record, or a nonmatching manager record; and nonzero uses `returncode=1` except pnpm's available fixture, which also uses its documented `returncode=1` with valid object output, and DNF's available fixture, which uses `returncode=100`. Make `pnpm_available` use the displayed object shape, not an array, and make `apt_available` include `Inst demo [1.0] (1.1 Debian:12/stable [amd64])` plus `Conf demo (1.1 Debian:12/stable [amd64])`. Parametrize the parser test over all 20 fixture names so every supported adapter proves current, available, malformed, and nonzero behavior. Keep `test_cask_update_is_unsupported_without_running_a_manager` separate from this parser matrix. Add `test_text_adapters_reject_mixed_target_and_foreign_output`, parameterized with APT simulation output containing `Inst demo ...` and `Inst other ...`, DNF output containing its allowed metadata line plus both records, and pacman output containing both records; each case must produce `UpdateStatus("unknown", None, detail)`.

For JSON adapters, accept no informational prefix or suffix: parse the complete stdout as JSON. pnpm accepts only the documented `--format json` object described in the table, never the npm-style array; its outer object must contain exactly the requested package and every displayed field must have the listed type. Treat pnpm exit 1 as `available` only when that complete object is valid; treat its exit 0 with `{}` as `current`; all other pnpm result combinations are `unknown`. For APT, invoke only `apt-get --simulate --only-upgrade install <package>`; scan its output for the documented `Inst`, `Conf`, and `Remv` simulation operation records, ignoring non-operation progress text. Accept `available` only for the sole matching `Inst` record with the documented brackets and parentheses; accept `current` only when exit 0 yields no operation record. Reject malformed, foreign, mixed-target, `Remv`, or unmatched `Conf` operation records. For DNF, discard only the full-line metadata pattern defined in the table; for pacman preserve every nonempty line. Every non-APT text adapter accepts either its exact empty-current result or exactly one target record. Reject invalid JSON, missing required string fields, an absent or empty available-version field, a nonempty response that contains only another package, a target record mixed with an unrelated record, nonzero results other than pnpm's valid available exit 1 and DNF exit 100, and a `CommandResult.failure` as `UpdateStatus("unknown", None, detail)`. Preserve the normalized runner failure text in `detail`. `update_argv` returns the reviewed install argv only when `ownership.confidence == "verified"` and a method in `tool.methods` has the exact manager/method/package tuple: pnpm/node/`npm_pkg`; Homebrew/brew/`formula`; apt/apt/`package`; dnf/dnf/`package`; or pacman/pacman/`package`. It returns `None` for every foreign or undeclared tuple, including every cask tuple. For a matching tuple it returns: pnpm `add -g`; brew formula `upgrade`; apt `sudo apt-get install --only-upgrade -y`; dnf `sudo dnf upgrade -y`; pacman `sudo pacman -S --noconfirm`.

Declare `UNKNOWN_UPDATE = UpdateStatus("unknown", None, "update discovery not requested")` in `installer.updates` and use it as the frozen `ToolStatus.update` default. `inspect_update` first maps `ownership.method_kind == "cask"` to the displayed unsupported result without invoking a manager. For every other method, it requires `ownership.confidence == "verified"`, non-`None` `method_kind`, `package`, and `executable`; otherwise return `UpdateStatus("unknown", None, ownership.detail)`, without invoking a manager. `update_argv` enforces verified evidence before comparing the manager/method/package tuple to one supported method declared by the supplied `Tool`; it has no cask tuple. Remove `owner_probes` from the model and registry. Add OpenCode’s `requires = ["pnpm"]` and `Method("node", {"npm_pkg": "opencode-ai"})` while retaining its existing install methods.

For this task, cask support is deliberately absent from `_OUTDATED_COMMANDS`, `_parse_outdated`, `update_argv`, and the parser matrix, notwithstanding the earlier generic manager wording. Evaluate `ownership.method_kind == "cask"` before the verified-owner guard in `inspect_update` and return the displayed unsupported result without executing a command. `detect_owner` marks a declared cask as unknown rather than attempting prefix containment, because `_cask` uses `--appdir=~/Applications`; it must never return `confidence="verified"` for a cask. Thus no cask can become `available` or reach an in-app update command.

- [ ] **Step 4: Run ownership, updates, model, status, and registry tests**

Run: `uv run pytest tests/test_ownership.py tests/test_updates.py tests/test_model.py tests/test_status.py tests/test_registry.py -v`

Expected: PASS. Each ownership adapter runs a fixed path query and verifies the resolved executable belongs to the declared package before update discovery runs. Each update adapter recognizes only the verified declared package, turns launch, timeout, malformed, and failed discovery into an unknown status, and leaves non-network status refreshes at `UNKNOWN_UPDATE`.

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
- Modify: `setup.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_app.py`
- Modify: `tests/test_setup.py`
- Modify: `tests/test_installer_workflow_e2e.py`

**Interfaces:**
- Produces: `ExecutionMode = Literal["install", "reinstall", "update"]`.
- Extends: `InstallPlan.execution_mode: ExecutionMode = "install"`.
- Produces: `build_update_plan(selected_ids: Collection[str], catalog: Sequence[Tool]) -> InstallPlan`, which preserves catalog order, contains only directly selected tools, has empty dependency metadata, and sets `execution_mode="update"`.
- Produces: `StatusFor = Callable[[Tool], ToolStatus]`; `run_wizard(..., status_for: StatusFor | None = None, probe: ProbeRunner = run_probe, health_runner: HealthRunner = run_health_check, executable_resolver: ExecutableResolver = resolve_executable)` builds the complete `ToolStatus` map through `status_for` when supplied, or through `tool_status(tool, probe, health_runner=health_runner, executable_resolver=executable_resolver)` in production.
- Produces: `install_tool(tool: Tool, platform: Platform, runner: Runner = run_command, resolve_tag: TagResolver = resolve_github_tag, *, checksum_policy: ChecksumPolicy = "fail", force: bool = False) -> InstallOutcome` and `update_tool(tool: Tool, ownership: Ownership, update: UpdateStatus, runner: Runner = run_command) -> InstallOutcome`.
- Extends: `run_plan(plan: InstallPlan, platform: Platform, emit: Callable[[ExecutionEvent], None], statuses: Mapping[str, ToolStatus], runner: Runner = run_command, resolve_tag: TagResolver = resolve_github_tag, install: Install = install_tool, on_mismatch: OnMismatch | None = None, outcomes: list[InstallOutcome] | None = None, action_context: ActionContext | None = None, approved_actions: frozenset[ActionKey] = frozenset(), skipped_actions: frozenset[ActionKey] = frozenset(), captured_runner: CapturedRunner | None = None, interactive_runner: Runner | None = None) -> Summary`.
- Migration: `statuses` is required at every call site. `installer.app.run_wizard` supplies the map for `plan.ordered`; Task 5 updates `setup.py` to build the same non-update map before its direct `run_plan` call; Task 6's `StartInstall` consumes the Catalog map; and every direct test call supplies `_statuses_for(plan)`. Every `Install` implementation, including every injected test fake, accepts keyword-only `force: bool = False` in addition to `checksum_policy`.

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


def test_update_rejects_a_verified_foreign_package_before_running_a_manager() -> None:
    commands: list[list[str]] = []

    outcome = update_tool(
        _tool(Method("node", {"npm_pkg": "demo"})),
        Ownership("pnpm", "verified", "pnpm lists other", "node", "other"),
        UpdateStatus("available", "1.1", "fixture"),
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

```python
# tests/test_app.py
def test_build_update_plan_preserves_catalog_order_and_excludes_dependencies() -> None:
    dependency = _tool("dependency", "core")
    selected = replace(_tool("demo", "apps"), requires=("dependency",))

    plan = build_update_plan(["demo"], [dependency, selected])

    assert plan.execution_mode == "update"
    assert plan.selected_ids == ("demo",)
    assert tuple(tool.id for tool in plan.ordered) == ("demo",)
    assert plan.dragged_in == ()
    assert plan.reasons == ()


# tests/test_session.py
def test_update_plan_rejects_dependency_expansion_before_running_a_manager() -> None:
    dependency = _tool("dependency")
    selected = replace(_tool("demo"), requires=("dependency",))
    plan = InstallPlan(
        selected_ids=("demo",),
        ordered=(dependency, selected),
        dragged_in=("dependency",),
        warnings=(),
        execution_mode="update",
    )

    with pytest.raises(ValueError, match="update plan must contain only directly selected tools"):
        run_plan(plan, _platform(), lambda _event: None, statuses={})
```

```python
# tests/test_app.py
@pytest.fixture(autouse=True)
def fake_status_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_tool_status(
        tool: Tool,
        _probe: ProbeRunner,
        *,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert callable(health_runner)
        assert callable(executable_resolver)
        return ToolStatus(
            tool,
            False,
            Ownership(None, "unknown", "not installed", None, None, None),
            Health("missing", None, "command not found on PATH"),
            UNKNOWN_UPDATE,
        )

    monkeypatch.setattr(app, "tool_status", fake_tool_status)


def test_run_wizard_uses_injected_status_for_each_planned_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = _tool("demo", "apps")
    received: dict[str, Mapping[str, ToolStatus]] = {}

    def fake_run_plan(
        _plan: InstallPlan,
        _platform: Platform,
        _emit: Callable[[ExecutionEvent], None],
        *,
        statuses: Mapping[str, ToolStatus],
        **_kwargs: object,
    ) -> Summary:
        received["statuses"] = statuses
        return Summary(("demo",), (), (), ())

    status = ToolStatus(
        tool,
        False,
        Ownership(None, "unknown", "not installed", None, None, None),
        Health("missing", None, "command not found on PATH"),
        UNKNOWN_UPDATE,
    )
    monkeypatch.setattr(app, "run_plan", fake_run_plan)
    summary = run_wizard(
        [tool],
        _platform(),
        FakePrompter([], [], True),
        _console()[0],
        Options(all=True, categories=(), yes=True),
        installed=_never_installed,
        status_for=lambda candidate: status if candidate is tool else pytest.fail("unexpected tool"),
    )

    assert summary == Summary(("demo",), (), (), ())
    assert received["statuses"] == {"demo": status}


def test_run_wizard_status_seam_forwards_all_injected_status_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = _tool("demo", "apps")

    def probe(_argv: list[str]) -> str:
        pytest.fail("probe must not run in this test")

    def fake_health_runner(_argv: list[str]) -> CommandResult:
        pytest.fail("health runner must not run in this test")

    def fake_executable_resolver(_cmd: str) -> Path | None:
        pytest.fail("executable resolver must not run in this test")

    def fake_tool_status(
        candidate: Tool,
        received_probe: ProbeRunner,
        *,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert candidate is tool
        assert received_probe is probe
        assert health_runner is fake_health_runner
        assert executable_resolver is fake_executable_resolver
        return ToolStatus(
            tool,
            False,
            Ownership(None, "unknown", "not installed", None, None, None),
            Health("missing", None, "command not found on PATH"),
            UNKNOWN_UPDATE,
        )

    monkeypatch.setattr(app, "tool_status", fake_tool_status)
    monkeypatch.setattr(
        app,
        "run_plan",
        lambda *_args, **_kwargs: Summary(("demo",), (), (), ()),
    )
    run_wizard(
        [tool],
        _platform(),
        FakePrompter([], [], True),
        _console()[0],
        Options(all=True, categories=(), yes=True),
        installed=_never_installed,
        probe=probe,
        health_runner=fake_health_runner,
        executable_resolver=fake_executable_resolver,
    )
```

```python
# tests/test_session.py
def _statuses_for(plan: InstallPlan) -> dict[str, ToolStatus]:
    return {
        tool.id: ToolStatus(
            tool,
            False,
            Ownership(None, "unknown", "not installed", None, None, None),
            Health("missing", None, "command not found on PATH"),
            UNKNOWN_UPDATE,
        )
        for tool in plan.ordered
    }


def test_run_plan_rejects_a_status_map_that_omits_a_planned_tool() -> None:
    plan = InstallPlan(("demo",), (_tool("demo"),), (), ())

    with pytest.raises(ValueError, match="status map must cover every planned tool"):
        run_plan(plan, _platform(), lambda _event: None, statuses={})
```

```python
# tests/test_setup.py
def fake_run_plan(
    plan: InstallPlan,
    _platform: Platform,
    emit: Callable[[ExecutionEvent], None],
    *,
    statuses: Mapping[str, ToolStatus],
    on_mismatch: Callable[[str], str],
    approved_actions: frozenset[tuple[str, str]],
    skipped_actions: frozenset[tuple[str, str]],
    captured_runner: object,
    interactive_runner: Callable[[list[str]], None],
) -> Summary:
    assert set(statuses) == {tool.id for tool in plan.ordered}
    emit(ExecutionEvent("fd", "installed", "fd: installed"))
    return Summary(installed=("fd",), already=(), failed=(), no_method=())
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_app.py tests/test_engine.py tests/test_session.py tests/test_setup.py -k 'force or mode or update or injected_status or status_seam or status_map' -v`

Expected: FAIL because plans have no execution mode, the CLI has no injectable status discovery seam, existing direct callers do not provide status maps, and session always runs a normal install.

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
# installer/app.py
def build_update_plan(selected_ids: Collection[str], catalog: Sequence[Tool]) -> InstallPlan:
    selected = set(selected_ids)
    ordered = tuple(tool for tool in catalog if tool.id in selected)
    return InstallPlan(
        selected_ids=tuple(tool.id for tool in ordered),
        ordered=ordered,
        dragged_in=(),
        warnings=(),
        execution_mode="update",
    )
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

In `run_plan`, for an update plan first require `plan.dragged_in == ()` and `tuple(tool.id for tool in plan.ordered) == plan.selected_ids`; raise `ValueError("update plan must contain only directly selected tools")` before emitting an event or invoking a manager when that invariant fails. Then require `{tool.id for tool in plan.ordered}.issubset(statuses)` and raise `ValueError("status map must cover every planned tool")` otherwise. This makes the complete-status contract explicit while ensuring dependency expansion cannot update an unselected tool; normal/reinstall callers may retain a larger freshly refreshed catalog map. Select one path per tool: `update_tool(tool, statuses[tool.id].ownership, statuses[tool.id].update, tool_runner)` for update, otherwise call `run_installs([tool], platform, tool_runner, resolve_tag, install, on_mismatch=on_mismatch, force=plan.execution_mode == "reinstall")`. The `update_tool` availability guard is mandatory even though the UI filters selections: a manually prepared update plan with a current, unknown, malformed, timed-out, failed, or unsupported update status must not invoke a package manager. Do not run post-install actions after update. Keep resolver order, checksum prompts, secure download handling, and manual handoffs in the normal/reinstall path.

```python
# installer/app.py
StatusFor = Callable[[Tool], ToolStatus]


def _status_for(tool: Tool) -> ToolStatus:
    if status_for is not None:
        return status_for(tool)
    return tool_status(
        tool,
        probe,
        health_runner=health_runner,
        executable_resolver=executable_resolver,
    )


status_map = {tool.id: _status_for(tool) for tool in plan.ordered}
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

In `installer/app.py`, import `HealthRunner` and `run_health_check` from `installer.health`; `ExecutableResolver`, `ProbeRunner`, `resolve_executable`, and `run_probe` from `installer.ownership`; and `ToolStatus` and `tool_status` from `installer.status`. Add the keyword-only `status_for`, `probe`, `health_runner`, and `executable_resolver` parameters to `run_wizard` after `installed`. Build `status_map` with `_status_for` after `audit(...)` and pass it as `statuses=status_map` to `run_plan`. The display-only `audit` call continues to use the existing injected `installed` seam.

```python
# setup.py, temporary non-update status map required by the new run_plan contract
def _execution_statuses(plan: InstallPlan) -> dict[str, ToolStatus]:
    return {
        tool.id: tool_status(
            tool,
            run_probe,
            health_runner=run_health_check,
            executable_resolver=resolve_executable,
        )
        for tool in plan.ordered
    }


return run_plan(
    plan,
    platform,
    _track,
    statuses=_execution_statuses(plan),
    on_mismatch=choices.on_mismatch,
    approved_actions=choices.approved_actions,
    skipped_actions=choices.skipped_actions,
    captured_runner=run_captured_command,
    interactive_runner=_run_interactive_action,
)
```

Task 7 replaces `_execution_statuses` with its shared `status_factory(False)` without changing the required `statuses=` call. This intermediate helper keeps Task 5 independently executable: normal and forced-reinstall setup operations have a complete, non-network status map before update refresh composition is added.

In `tests/test_session.py`, add the displayed `_statuses_for(plan)` helper and pass `statuses=_statuses_for(plan)` to every existing direct `run_plan` call in `test_run_plan_emits_dependency_before_dependent`, `test_run_plan_attributes_captured_subprocess_output_and_method`, `test_run_plan_updates_active_method_when_ladder_falls_back`, `test_run_plan_emits_command_error_detail_in_attributed_output`, `test_run_plan_emits_console_handoff_for_manual_setup`, all seven action-processing tests from `test_run_plan_applies_actions_after_success_and_emits_each_result` through `test_run_plan_emits_completed_action_result_before_a_later_action_fails`, `test_run_plan_emits_only_final_checksum_outcome`, and `test_run_plan_emits_cancelled_when_checksum_choice_is_cancel`. Add `force: bool = False` after `checksum_policy` in each local fake in those tests, in `test_run_installs_calls_install_per_tool_with_injected_deps`, in `test_on_mismatch_is_not_consulted_for_clean_installs`, and in `_mismatch_then_install`. For every retry and fallback assertion, retain the existing policy assertions and add `assert force is False` inside the fake where appropriate; the displayed execution-mode test is the single assertion that expects `force is True`.

In `tests/test_app.py`, add `force: bool = False` to the fakes returned by `_recording_install` and `_mismatching_install`, and to the local fakes in `test_failed_install_surfaces_in_summary_without_crashing` and `test_run_wizard_installs_dependencies_before_dependents`. Extend the displayed autouse `fake_tool_status` with `executable_resolver: ExecutableResolver` and update every fixture `Ownership` construction to include a final `None` executable. Task 1 deletes `test_textual_worker_never_hands_its_tty_to_guided_host_setup` from `tests/test_install_screen.py`, which is that file's only direct `run_plan` caller; remove its now-unused `engine`, `Platform`, `load_tools`, and `run_plan` imports with it. In `tests/test_setup.py`, update `fake_tool_status` to accept `health_runner` and `executable_resolver`, update `fake_run_plan` to the displayed signature with mandatory `statuses`, and change the `fake_unified_app` callback types so `build_plan` accepts `(list[str], ExecutionMode)` and `start_install` accepts `(InstallPlan, Mapping[str, ToolStatus], ExecutionChoices, Callable[[ExecutionEvent], None])`. Make the test assert that its captured map keys equal the expanded plan's ordered ids. In `tests/test_installer_workflow_e2e.py`, extend `run_with_stubbed_boundaries` to accept and forward `status_for`, `probe`, `health_runner`, and `executable_resolver`. Pass a deterministic `status_for` that returns the fixture `ToolStatus` with static `Health`, `Ownership`, and `UNKNOWN_UPDATE`; also pass fail-fast probe, health-runner, and executable-resolver functions. The test must fail if any real status subprocess or PATH resolution is attempted, while preserving the existing fake install runner. These are every production and test caller/fake affected by the mandatory `statuses` and `force` contracts.

In `tests/test_app.py`, import `installer.app as app`, `CommandResult`, `Health`, `HealthRunner`, `UNKNOWN_UPDATE`, `Ownership`, `ProbeRunner`, `ExecutableResolver`, and `ToolStatus`. Add the displayed autouse fixture so every existing `run_wizard` test remains offline. Add the displayed `test_run_wizard_uses_injected_status_for_each_planned_tool`, which intercepts `app.run_plan` and proves that the exact injected status map reaches execution, and `test_run_wizard_status_seam_forwards_all_injected_status_dependencies`, which proves the default status path forwards all three subprocess/path seams without calling them. Import `Collection` and `Sequence` from `collections.abc` in `installer/app.py`; import `build_update_plan` in `tests/test_app.py`.

- [ ] **Step 4: Run engine and session tests**

Run: `uv run pytest tests/test_app.py tests/test_engine.py tests/test_session.py tests/test_setup.py tests/test_installer_workflow_e2e.py -v`

Expected: PASS. The engine proves forced reinstall proceeds beyond the presence guard and retains checksum failure behavior; update uses only a verified owner with an `available` update in the supplied status map, and sends no manager command for current, unknown, malformed, timed-out, failed, or unsupported statuses.

- [ ] **Step 5: Commit recovery execution**

```bash
git add installer/app.py installer/engine.py installer/install_plan.py installer/session.py setup.py tests/test_app.py tests/test_engine.py tests/test_session.py tests/test_setup.py tests/test_installer_workflow_e2e.py
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
- Modify: `tests/test_policies_e2e.py`
- Modify: `tests/test_uninstall_e2e.py`

**Interfaces:**
- Produces: `CatalogScreen.Decided(result: list[str] | None, mode: ExecutionMode = "install")` and `CatalogScreen.RefreshRequested()`.
- Produces: `CatalogScreen.refresh_statuses(statuses)`, `CatalogScreen.status_for(tool_id)`, `CatalogScreen.discard_selected(ids)`, and `ToolBrowser.discard_selected(ids)`.
- Extends: `InstallScreen` with `on_complete: Callable[[Summary], None] | None`; it runs exactly once from both `_finish` and `cancel_pending` after `summary` and `finished` are set.
- Extends: `UnifiedApp` with public `refresh_catalog(include_updates: bool) -> Mapping[str, ToolStatus]`, used by the refresh-message handler and tests.
- Consumes: `StartInstall = Callable[[InstallPlan, Mapping[str, ToolStatus], ExecutionChoices, Callable[[ExecutionEvent], None]], Summary]` so the prepared plan, including its mode and update evidence, is passed intact.
- Consumes: `BuildPlan = Callable[[list[str], ExecutionMode], InstallPlan]`. Update plans contain only directly selected tools in catalog order; their status map covers every `plan.ordered` tool, while the `available` filter is applied before construction.
- Migration: every direct `UnifiedApp` constructor supplies `refresh_statuses`. In `tests/test_policies_e2e.py` and `tests/test_uninstall_e2e.py`, pass a lambda returning the existing complete one-tool status map; this seam must not read home, PATH, or run status subprocesses.

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
    build_plan = (
        lambda ids, mode: replace(_plan_for(tools, ids), execution_mode=mode)
    ) if start_install is not None else None
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
    statuses["rg"] = replace(statuses["rg"], update=UpdateStatus("available", "1.1", "fixture"))
    app = _app(statuses=statuses, start_install=lambda plan, _statuses, _choices, _emit: plans.append(plan) or _summary("rg"))
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
        start_install=lambda _plan, _statuses, _choices, _emit: _summary("rg"),
    )
    async with app.run_test() as pilot:
        await pilot.press("ctrl+f")
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
    assert refreshes == [True, False]
    assert app.catalog.selected == set()
```

```python
# tests/test_wizard_app.py
async def test_retry_replaces_the_completed_install_screen_before_repreparing() -> None:
    started: list[InstallPlan] = []
    app = _app(
        start_install=lambda plan, _statuses, _choices, _emit: started.append(plan)
        or Summary((), (), ("rg",), ()),
    )

    async with app.run_test() as pilot:
        await pilot.press("space", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, InstallScreen)
        assert app.screen.finished is True
        await pilot.press("r")
        await pilot.pause()

    assert len(started) == 1
    assert isinstance(app.screen, InstallScreen)
    assert app.screen.finished is False
    assert app.screen.rows == {"rg": "queued"}
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

Run: `uv run pytest tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py -k 'operation_mode or refresh_request or completion_callback or discard_selected or missing_health or retry_replaces or unknown_update' -v`

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
BuildPlan: TypeAlias = Callable[[list[str], ExecutionMode], InstallPlan]

def __init__(
    self, tools: list[Tool], statuses: Mapping[str, ToolStatus], blurbs: Mapping[str, str], *,
    report: DoctorReport, guard_status: dict[str, bool], guard_warning: str | None,
    fix_preview: str, fix: Callable[[], None], uninstall: UninstallInputs,
    policies: PolicyInputs, refresh_statuses: Callable[[bool], Mapping[str, ToolStatus]],
    initial_view: str = "catalog", initial_selected_ids: tuple[str, ...] = (),
    start_install: StartInstall | None = None, build_plan: BuildPlan | None = None,
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
    build_plan = self._build_plan
    start_install = self._start_install
    if build_plan is None or start_install is None:
        return
    if mode == "update":
        selected_ids = [
            tool_id for tool_id in selected_ids
            if self._catalog.status_for(tool_id).update.state == "available"
        ]
        if not selected_ids:
            self._catalog.status.set("No selected tools have a verified available update.", "warn")
            return
    plan = build_plan(selected_ids, mode)
    operation_statuses = {tool.id: self._catalog.status_for(tool.id) for tool in plan.ordered}
    screen = self._views["install"]
    if not isinstance(screen, InstallScreen):
        return
    if self.current_view == "install":
        await self.pop_screen()
        self.current_view = "catalog"
    screen.prepare(
        plan,
        lambda choices, emit: start_install(plan, operation_statuses, choices, emit),
    )
    await self.push_screen(screen)
    self.current_view = "install"

def _finish_catalog_operation(self, summary: Summary) -> None:
    self.refresh_catalog(False)
    self._catalog.discard_selected(set(summary.installed) | set(summary.already))
```

Construct `InstallScreen(on_complete=self._finish_catalog_operation)`. Keep per-event rendering but remove its installation-status mutation callback; no intermediate event changes Catalog status. Before reusing a completed persistent `InstallScreen`, pop it and set `current_view = "catalog"`; this preserves the installed-screen stack invariant for `action_retry_install` before calling `prepare` and pushing it again. Render health detail from the immutable status map as exactly one of `version: <version>` for `healthy`, `broken: <detail>` for `broken`, `installed bundle; executable missing from PATH` for `missing` when `status.installed` is true, `command missing` for `missing` when `status.installed` is false, or `version check unsupported` for `unsupported`. Append the verified owner and `update: <state> (<detail>)` only from that same complete immutable status map for every update state. This displays the current result and malformed-output, timeout, and launch-failure diagnostics without enabling update. Do not collapse a present app bundle with missing health into the missing-install state.

```python
# installer/catalog_tui.py, at the end of _detail_text after loading status
health = status.health
if health.state == "healthy":
    detail += f"  |  version: {health.version}"
elif health.state == "broken":
    detail += f"  |  broken: {health.detail}"
elif health.state == "missing":
    detail += (
        "  |  installed bundle; executable missing from PATH"
        if status.installed
        else "  |  command missing"
    )
else:
    detail += "  |  version check unsupported"
if status.ownership.confidence == "verified":
    detail += f"  |  owner: {status.ownership.manager}"
update = status.update
detail += f"  |  update: {update.state} ({update.detail})"
return detail
```

Add this detail-rendering regression test to `tests/test_wizard_app.py`:

```python
@pytest.mark.parametrize(
    ("state", "detail"),
    [
        ("current", "demo is already current"),
        ("available", "demo 1.0 -> 1.1"),
        ("unknown", "malformed manager output"),
        ("unknown", "update check timed out after 5 seconds"),
        ("unknown", "update check could not start: missing"),
        ("unsupported", "manager has no reviewed update adapter"),
    ],
)
async def test_catalog_renders_update_diagnostics(state: UpdateState, detail: str) -> None:
    tool = _tool("rg")
    statuses = _statuses_for([tool])
    statuses["rg"] = replace(
        statuses["rg"], update=UpdateStatus(state, None, detail)
    )
    app = _app(statuses=statuses)

    async with app.run_test() as pilot:
        await pilot.pause()
        assert f"update: {state} ({detail})" in app.catalog.detail_text
```

Import `UpdateState` from `installer.updates` in `tests/test_wizard_app.py` with `UpdateStatus`.

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

Run: `uv run pytest tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py tests/test_policies_e2e.py tests/test_uninstall_e2e.py -v`

Expected: PASS. Install, reinstall, and update modes reach the executor unchanged; `ctrl+f` runs full update discovery; a present app bundle without a PATH executable is rendered as missing health rather than an absent install; completion refreshes local status and deselects only installed or already-installed tools.

- [ ] **Step 5: Commit Catalog reliability UI**

```bash
git add installer/tool_browser.py installer/catalog_tui.py installer/install_screen.py installer/wizard_app.py tests/test_tool_browser.py tests/test_catalog_tui.py tests/test_install_screen.py tests/test_wizard_app.py tests/test_policies_e2e.py tests/test_uninstall_e2e.py
git commit -m "feat(catalog): refresh health and expose recovery actions"
```

### Task 7: Compose real status and update operations at the boundary

**Files:**
- Modify: `setup.py`
- Modify: `tests/test_setup.py`
- Modify: `tests/test_installer_workflow_e2e.py`
- Modify: `README.md`

**Interfaces:**
- `_build_app(tools: list[Tool], platform: Platform, *, initial_view: str = "catalog", initial_selected_ids: tuple[str, ...] = (), link_mode: str = "centralized", enable_install: bool = True, probe: ProbeRunner = run_probe, health_runner: HealthRunner = run_health_check, executable_resolver: ExecutableResolver = resolve_executable, update_runner: UpdateRunner = run_update_check) -> UnifiedApp` injects typed subprocess and executable-resolution seams.
- `status_factory(include_updates: bool) -> dict[str, ToolStatus]` is passed as `UnifiedApp(refresh_statuses=...)`; tests call the app’s public `refresh_catalog`, not a private member.
- Every Task 7 `_build_app` composition test uses one `isolated_build_app` fixture. The fixture uses `tmp_path` for a synthetic home, monkeypatches `Path.home()`, `HOME`, setup’s import-time home constants, and every filesystem/composition collaborator, replaces `setup.tool_status` with a fake that asserts the injected ownership probe, health runner, and executable resolver identities, and injects a failing update runner. No Task 7 composition test may use `_build_app` defaults or inspect a real home, `PATH`, executable, or subprocess.
- `StartInstall` receives the exact prepared `InstallPlan` plus the operation status map captured from the Catalog. Every captured map contains exactly `{tool.id for tool in plan.ordered}`. Normal installs and reinstalls use a fresh `status_factory(False)` map; updates use the captured complete map so their verified `Ownership` and `UpdateStatus("available", ...)` reach the fail-closed execution boundary without another update query. The `BuildPlan` closure calls `build_update_plan` for updates, so dependency expansion is never applied to an update operation.
- Documentation: README navigation describes four navigable views (`1-4`), the policies list omits `claude-skip`, and the recovery controls describe the update availability guard.

- [ ] **Step 1: Write failing composition tests using the public seam**

```python
# tests/test_setup.py
class IsolatedBuildApp(Protocol):
    def __call__(
        self,
        tools: list[Tool],
        platform: Platform,
        *,
        enable_install: bool = True,
    ) -> UnifiedApp: ...


@pytest.fixture
def isolated_build_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> IsolatedBuildApp:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", home / ".local" / "bin")
    monkeypatch.setattr(setup, "_MYSHELLRC", home / ".myshellrc")
    monkeypatch.setattr(setup, "_RC_PATHS", [home / ".zshrc", home / ".bashrc"])
    monkeypatch.setattr(setup, "_SHELL", "/bin/zsh")
    monkeypatch.setattr(
        setup,
        "doctor_data",
        lambda *_args, **_kwargs: (DoctorReport((), (), ()), {"pip": False, "npm": False}, None),
    )
    monkeypatch.setattr(setup, "classify_tools", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(setup, "reverse_dependencies", lambda _tools: {})
    monkeypatch.setattr(setup, "has_managed_block", lambda _path: False)
    monkeypatch.setattr(setup, "ban_policy", lambda **_kwargs: object())
    monkeypatch.setattr(setup, "applicable_bundles", lambda _platform: ())
    monkeypatch.setattr(setup, "load_categories", lambda _registry: {})

    def fail_probe(_argv: list[str]) -> str:
        pytest.fail("ownership probe must not run in a composition test")

    def fail_health(_argv: list[str]) -> CommandResult:
        pytest.fail("health runner must not run in a composition test")

    def fail_resolver(_cmd: str) -> Path | None:
        pytest.fail("executable resolver must not run in a composition test")

    def fail_update(_argv: list[str]) -> CommandResult:
        pytest.fail("update runner must not run in a composition test")

    def fake_tool_status(
        tool: Tool,
        probe: ProbeRunner,
        *,
        health_runner: HealthRunner,
        executable_resolver: ExecutableResolver,
    ) -> ToolStatus:
        assert probe is fail_probe
        assert health_runner is fail_health
        assert executable_resolver is fail_resolver
        return ToolStatus(
            tool,
            False,
            Ownership(None, "unknown", "not installed", None, None, None),
            Health("missing", None, "command not found on PATH"),
            UNKNOWN_UPDATE,
        )

    monkeypatch.setattr(setup, "tool_status", fake_tool_status)

    def build(tools: list[Tool], platform: Platform, *, enable_install: bool = True) -> UnifiedApp:
        return setup._build_app(
            tools,
            platform,
            enable_install=enable_install,
            probe=fail_probe,
            health_runner=fail_health,
            executable_resolver=fail_resolver,
            update_runner=fail_update,
        )

    return build


async def test_public_catalog_refresh_skips_update_queries_until_requested(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    update_calls: list[str] = []

    def fake_inspect_update(
        tool: Tool, _owner: Ownership, runner: UpdateRunner
    ) -> UpdateStatus:
        assert callable(runner)
        update_calls.append(tool.id)
        return UNKNOWN_UPDATE

    monkeypatch.setattr(
        setup,
        "inspect_update",
        fake_inspect_update,
    )
    app = isolated_build_app([_tool("fd")], _platform(), enable_install=False)
    async with app.run_test():
        app.refresh_catalog(False)
        assert update_calls == []
        app.refresh_catalog(True)
    assert update_calls == ["fd"]
```

```python
# tests/test_setup.py
async def test_start_install_passes_the_prepared_mode_and_fresh_statuses(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(setup, "run_plan", lambda plan, _platform, _emit, **kwargs: received.update(plan=plan, **kwargs) or Summary(("fd",), (), (), ()))
    app = isolated_build_app([_tool("fd")], _platform())
    async with app.run_test() as pilot:
        await pilot.press("space", "ctrl+r", "enter", "enter")
        await pilot.pause()
    assert cast(InstallPlan, received["plan"]).execution_mode == "reinstall"
    assert isinstance(received["statuses"], dict)


async def test_update_uses_the_available_status_captured_from_the_catalog(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(setup, "run_plan", lambda plan, _platform, _emit, **kwargs: received.update(plan=plan, **kwargs) or Summary(("fd",), (), (), ()))
    app = isolated_build_app([_tool("fd")], _platform())
    app.catalog.refresh_statuses({
        "fd": replace(_status_for("fd"), update=UpdateStatus("available", "1.1", "fixture"))
    })
    async with app.run_test() as pilot:
        await pilot.press("space", "ctrl+u", "enter")
        await pilot.pause()
    status = cast(dict[str, ToolStatus], received["statuses"])["fd"]
    assert status.update.state == "available"
```

```python
# tests/test_setup.py
async def test_update_plan_captures_complete_statuses_without_expanding_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    isolated_build_app: IsolatedBuildApp,
) -> None:
    received: dict[str, object] = {}
    dependency = _tool("dependency")
    selected = replace(_tool("fd"), requires=("dependency",))
    monkeypatch.setattr(
        setup,
        "run_plan",
        lambda plan, _platform, _emit, **kwargs: received.update(plan=plan, **kwargs)
        or Summary(("fd",), (), (), ()),
    )
    app = isolated_build_app([selected, dependency], _platform())
    app.catalog.refresh_statuses(
        {
            "dependency": _status_for("dependency"),
            "fd": replace(
                _status_for("fd"), update=UpdateStatus("available", "1.1", "fixture")
            ),
        }
    )

    async with app.run_test() as pilot:
        await pilot.press("space", "ctrl+u", "enter")
        await pilot.pause()

    plan = cast(InstallPlan, received["plan"])
    statuses = cast(dict[str, ToolStatus], received["statuses"])
    assert plan.execution_mode == "update"
    assert tuple(tool.id for tool in plan.ordered) == ("fd",)
    assert set(statuses) == {tool.id for tool in plan.ordered}
    assert statuses["fd"].update.state == "available"
```

In `tests/test_setup.py`, import `Protocol` with `cast`; import `CommandResult` and `Health` from `installer.health`; import `ExecutableResolver` and `ProbeRunner` from `installer.ownership`; import `UNKNOWN_UPDATE`, `UpdateRunner`, and `UpdateStatus` from `installer.updates`; and import `UnifiedApp` from `installer.wizard_app`. The fixture is the required entry point for every new Task 7 `_build_app` test: it makes the status composition deterministic, verifies that setup forwards the three status seams, and prevents real filesystem, home, PATH, health, ownership, and update behavior. Keep existing direct setup tests on their current explicit seams unless they call `_build_app` for Task 7 behavior.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_setup.py tests/test_installer_workflow_e2e.py -k 'public_catalog_refresh or prepared_mode or complete_statuses or broken_present_tool' -v`

Expected: FAIL because setup does not inject health/update runners, expose a public refresh route, or pass the prepared mode to `run_plan`.

- [ ] **Step 3: Compose the runners, status factory, and plan executor**

```python
# setup.py, inside _build_app
def status_factory(include_updates: bool) -> dict[str, ToolStatus]:
    refreshed = {
            tool.id: tool_status(
                tool,
                probe,
                health_runner=health_runner,
                executable_resolver=executable_resolver,
            )
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

def build_plan(selected_ids: list[str], mode: ExecutionMode) -> InstallPlan:
    if mode == "update":
        return build_update_plan(selected_ids, tools)
    selected = [by_id[tool_id] for tool_id in selected_ids]
    return replace(
        build_install_plan(selected, tools, platform, lambda tool: tool.id in completed),
        execution_mode=mode,
    )

def _start_install(
    plan: InstallPlan,
    operation_statuses: Mapping[str, ToolStatus],
    choices: ExecutionChoices,
    emit: Callable[[ExecutionEvent], None],
) -> Summary:
    statuses = operation_statuses if plan.execution_mode == "update" else status_factory(False)
    def _track(event: ExecutionEvent) -> None:
        if event.state in {"installed", "already-installed"}:
            completed.add(event.tool_id)
        emit(event)

    return run_plan(
        plan, platform, _track,
        statuses=statuses,
        on_mismatch=choices.on_mismatch,
        approved_actions=choices.approved_actions,
        skipped_actions=choices.skipped_actions,
        captured_runner=run_captured_command,
        interactive_runner=_run_interactive_action,
    )
```

Replace the existing `plans` cache, `_build_install_plan`, and Task 5's `_execution_statuses` closure with `build_plan` and `status_factory`; retain `completed` and `by_id` so normal and forced-reinstall plans use the existing installed-state behavior. Pass `refresh_statuses=status_factory` and `build_plan=build_plan` to `UnifiedApp`. Import `Mapping` from `collections.abc`, `replace` from `dataclasses`, `build_update_plan` from `installer.app`, `ExecutableResolver` and `resolve_executable` from `installer.ownership`, and `ExecutionMode` from `installer.install_plan`. Keep real environment discovery and runner construction in `setup.py`; keep parsing and status decisions in `installer/`. Do not access private app methods in tests and do not add a Pyright suppression.

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

- **Spec coverage:** Task 1 removes all agent-environment imports, policy composition, view registration, navigation, the `installer.skill_lifecycle` module and every consumer, registry entries, and stale four-view public contracts in `tests/test_ui_common.py`. Task 2 retains only the approved reversible OpenCode alias policy. Task 3 defines presence, app-bundle-without-CLI health, a single canonical executable resolver, and the `UNKNOWN_HEALTH` default that keeps every existing three-argument `ToolStatus` constructor valid; the distinct audit status value remains unchanged. Task 4 defines path-verified ownership, immutable initial update state, exact update parsing, recognized informational text, mixed-package rejection, and normalized subprocess failure behavior. Every update-capable manager must prove its declared package owns the resolved executable; a same-named package and a foreign executable produce unknown ownership and no update argv. Homebrew casks are explicitly unsupported because the installer places their bundles in `~/Applications`; no cask ownership proof, update query, parser, or update command is planned. Task 5 migrates every production and test `run_plan` caller to a complete status map, migrates every injected `Install` fake to `force`, makes CLI status discovery injectable, makes update plans direct-selection-only, rejects a dependency-expanded update plan before execution, proves forced reinstall retains checksum enforcement, and rejects current, unknown, unsupported, and foreign-package updates before a manager runs. Tasks 6-7 preserve mode through the prepared plan, capture status for every planned update tool, preserve the persistent-screen retry transition, render every update-state detail and missing executable distinctly, compose the real status factory, use a `tmp_path`-isolated composition fixture for every new `_build_app` test, and update README navigation and policy content.
- **Deferred scope:** No task creates shared critical-tool hints or restores agent configuration automation.
- **Placeholder scan:** The plan has no TODOs, deferred code paths, quality suppressions, or unspecified manager output formats. Each manager has fixed query argv, accepted output shape, exact match rule, allowed informational text, current result, and failure result. pnpm uses its documented `--format json` object output, while APT uses documented `apt-get --simulate` operation records rather than the unstable end-user `apt` interface.
- **Type consistency:** `CommandResult.failure`, `ExecutionMode`, `InstallPlan.execution_mode`, `Ownership.method_kind`, `Ownership.package`, `Ownership.executable`, `ExecutableResolver`, `Health`, `UNKNOWN_HEALTH`, `UpdateStatus`, `ToolStatus.update`, `StatusFor`, `StartInstall`, `BuildPlan`, `build_update_plan`, and `UnifiedApp.refresh_catalog` use the same names and types in every producing and consuming task. `run_plan(..., statuses=...)` is mandatory at every caller and every `Install` implementation accepts `force`.
