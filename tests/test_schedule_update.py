"""The headless single-tool update a schedule timer runs (24.2-06).

Everything runs in-process with fake ownership, a recording runner and fake version probes;
no real package manager, vendor CLI or timer is ever started.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import setup
from installer.guards import REDIRECT_SENTINEL
from installer.model import Tool, load_tools
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.run import CommandError, run_captured_in_group
from installer.schedule_run import RunDeps, run_schedule
from installer.update import UpdateService, UpdateTarget, resolve_update_argv

_REGISTRY = Path(__file__).resolve().parent.parent / "installer" / "registry.toml"
_FEDORA = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def _tool(tool_id: str) -> Tool:
    return next(tool for tool in load_tools(_REGISTRY) if tool_id == tool.id)


def _ownership(
    tool: Tool,
    owner: Owner,
    *,
    with_method: bool = True,
    package: str | None = None,
    confidence: Confidence = "direct",
    reason: str | None = None,
) -> ManagerOwnership:
    return ManagerOwnership(
        tool_id=tool.id,
        owner=owner,
        method=tool.methods[0] if with_method else None,
        package=package,
        current_version=None,
        confidence=confidence,
        shadowed=False,
        candidates=(),
        active_candidate=None if owner == "unknown" else owner,
        active_path=None,
        unknown_reason=reason,
    )


class Recorder:
    """A runner that records every argv and raises the planted error, if any."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.error = error

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(list(cmd))
        if self.error is not None:
            raise self.error


def _versions(*values: str | None) -> Callable[[Tool, ManagerOwnership], str | None]:
    pending: Iterator[str | None] = iter(values)

    def probe(_tool: Tool, _ownership: ManagerOwnership) -> str | None:
        return next(pending)

    return probe


def _service(ownership: ManagerOwnership, runner: Recorder) -> UpdateService:
    return UpdateService(
        platform=_FEDORA,
        runner=runner,
        resolve_tag=lambda _repo: "v1.0.0",
        managed_packages=lambda: (),
        replay_globals=lambda _packages: (),
        reresolve_ownership=lambda _tool: ownership,
    )


def _deps(
    tool: Tool,
    ownership: ManagerOwnership,
    runner: Recorder,
    versions: Callable[[Tool, ManagerOwnership], str | None],
) -> RunDeps:
    return RunDeps(
        tools=[tool],
        updates=_service(ownership, runner),
        resolve_owner=lambda _tool: ownership,
        probe_version=versions,
        context=None,
    )


def _claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *versions: str | None
) -> tuple[RunDeps, Recorder, Path]:
    """A script-owned claude whose declared leaf exists under a scratch HOME."""
    monkeypatch.setenv("HOME", str(tmp_path))
    leaf = tmp_path / ".local" / "bin" / "claude"
    leaf.parent.mkdir(parents=True)
    leaf.write_text("launcher")
    tool = _tool("claude")
    recorder = Recorder()
    deps = _deps(tool, _ownership(tool, "installer"), recorder, _versions(*versions))
    return deps, recorder, leaf


def test_run_schedule_updates_claude_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, recorder, leaf = _claude(tmp_path, monkeypatch, "1.0", "1.1")
    assert run_schedule("update-claude", deps, parent_holds_lock=True) == (
        "ok: updated 1.0 → 1.1",
        0,
    )
    assert recorder.calls == [[str(leaf), "update"]]


def test_up_to_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, recorder, _leaf = _claude(tmp_path, monkeypatch, "1.1", "1.1")
    assert run_schedule("update-claude", deps, parent_holds_lock=True) == ("ok: up to date", 0)
    assert len(recorder.calls) == 1


def test_a_non_update_schedule_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, recorder, _leaf = _claude(tmp_path, monkeypatch)
    assert run_schedule("tmp-cleanup", deps, parent_holds_lock=True) == (
        "failed: tmp-cleanup is not an update schedule",
        2,
    )
    assert recorder.calls == []


def test_a_tool_missing_from_the_catalog_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, recorder, _leaf = _claude(tmp_path, monkeypatch)
    empty = RunDeps(deps.tools[:0], deps.updates, deps.resolve_owner, deps.probe_version, None)
    assert run_schedule("update-claude", empty, parent_holds_lock=True) == (
        "failed: claude is not in the catalog",
        1,
    )
    assert recorder.calls == []


def test_setup_routes_run_schedule_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    deps, recorder, _leaf = _claude(tmp_path, monkeypatch, "1.0", "1.1")
    monkeypatch.setattr(setup, "_has_controlling_tty", lambda: False)
    monkeypatch.setattr(setup, "detect", lambda: _FEDORA)

    def fake_deps(_tools: list[Tool], _platform: Platform) -> RunDeps:
        return deps

    monkeypatch.setattr(setup, "_schedule_run_deps", fake_deps)

    def refuse(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("another route ran")

    for name in (
        "_run_doctor",
        "_run_fix",
        "_run_uninstall",
        "_run_guard",
        "_run_interactive_wizard",
        "run_wizard",
    ):
        monkeypatch.setattr(setup, name, refuse)
    code = setup.main(["--run-schedule", "update-claude", "--parent-holds-run-lock"])
    assert code == 0
    assert capsys.readouterr().out == "ok: updated 1.0 → 1.1\n"
    assert len(recorder.calls) == 1


def test_run_schedule_uses_the_in_group_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    """R2-04: the vendor update must stay in the group the schedule runner kills on a timeout."""
    seen: dict[str, object] = {}

    class _Refresh:
        def resolve_owner(self, tool: Tool) -> ManagerOwnership:
            return _ownership(tool, "unknown")

    def fake_build_services(
        tools: list[Tool], platform: Platform, **kwargs: object
    ) -> tuple[object, UpdateService, object, object]:
        seen.update(kwargs)
        updates = UpdateService(
            platform=platform,
            managed_packages=lambda: (),
            replay_globals=lambda _packages: (),
            reresolve_ownership=lambda _tool: _ownership(tools[0], "unknown"),
        )
        return _Refresh(), updates, None, None

    monkeypatch.setattr(setup, "_build_services", fake_build_services)
    deps = vars(setup)["_schedule_run_deps"]([_tool("claude")], _FEDORA)
    assert isinstance(deps, RunDeps)
    assert seen == {"runner": run_captured_in_group}


# --- skipped owners, failures, copilot's cask path and Pi's reviewed update -------------------


def _no_runner_call(
    tool_id: str, owner: Owner, *, reason: str | None = None, confidence: Confidence = "direct"
) -> tuple[tuple[str, int], Recorder]:
    tool = _tool(tool_id)
    ownership = _ownership(tool, owner, with_method=False, reason=reason, confidence=confidence)
    recorder = Recorder()
    deps = _deps(tool, ownership, recorder, _versions("1.0"))
    return run_schedule(f"update-{tool_id}", deps, parent_holds_lock=True), recorder


def test_pacman_owned_opencode_is_skipped() -> None:
    result, recorder = _no_runner_call("opencode", "pacman")
    assert result == ("skipped: pacman owns opencode", 0)
    assert recorder.calls == []


def test_unknown_owner_is_skipped() -> None:
    reason = "Pi was installed with bun; no manager claims it"
    result, recorder = _no_runner_call("pi", "unknown", reason=reason, confidence="none")
    assert result == (f"skipped: {reason}", 0)
    assert recorder.calls == []


def test_update_failure_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps, _recorder, leaf = _claude(tmp_path, monkeypatch, "1.0")
    failing = Recorder(CommandError([str(leaf), "update"], 1, detail="boom"))
    broken = RunDeps(
        deps.tools,
        _service(_ownership(deps.tools[0], "installer"), failing),
        deps.resolve_owner,
        deps.probe_version,
        None,
    )
    assert run_schedule("update-claude", broken, parent_holds_lock=True) == (
        f"failed: command failed (1): {leaf} update",
        1,
    )
    assert len(failing.calls) == 1


def test_copilot_cask_updates_through_brew() -> None:
    tool = _tool("copilot")
    ownership = _ownership(tool, "cask", package="copilot-cli")
    recorder = Recorder()
    deps = _deps(tool, ownership, recorder, _versions("1.0", "1.1"))
    assert run_schedule("update-copilot", deps, parent_holds_lock=True) == (
        "ok: updated 1.0 → 1.1",
        0,
    )
    assert recorder.calls == [resolve_update_argv(UpdateTarget(tool, ownership))]
    assert recorder.calls[0][:3] == ["brew", "upgrade", "--cask"]


def _pnpm_behind_a_ban_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME is scratch, the ban shim comes first on PATH, the real pnpm second; returns the real."""
    monkeypatch.setenv("HOME", str(tmp_path))
    shim = tmp_path / ".local" / "bin" / "pnpm"
    real = tmp_path / "real" / "pnpm"
    for path, text in ((shim, f"#!/bin/sh\n{REDIRECT_SENTINEL}\n"), (real, "#!/bin/sh\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim.parent}{os.pathsep}{real.parent}")
    return real


def test_pi_updates_through_its_reviewed_host_setup_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = _pnpm_behind_a_ban_shim(tmp_path, monkeypatch)
    tool = _tool("pi")
    ownership = _ownership(
        tool, "pnpm", with_method=False, package="@earendil-works/pi-coding-agent"
    )
    recorder = Recorder()
    deps = _deps(tool, ownership, recorder, _versions("1.4.0", "1.5.0"))
    assert run_schedule("update-pi", deps, parent_holds_lock=True) == (
        "ok: updated 1.4.0 → 1.5.0",
        0,
    )
    assert recorder.calls == [
        [str(real), "add", "-g", "--ignore-scripts", "@earendil-works/pi-coding-agent"]
    ]
