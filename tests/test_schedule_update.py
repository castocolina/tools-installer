"""The headless single-tool update a schedule timer runs (24.2-06).

Everything runs in-process with fake ownership, a recording runner and fake version probes;
no real package manager, vendor CLI or timer is ever started.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

import setup
from installer.model import Tool, load_tools
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.run import run_captured_in_group
from installer.schedule_run import RunDeps, run_schedule
from installer.update import UpdateService

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


def _deps(
    tool: Tool,
    ownership: ManagerOwnership,
    runner: Recorder,
    versions: Callable[[Tool, ManagerOwnership], str | None],
) -> RunDeps:
    updates = UpdateService(
        platform=_FEDORA,
        runner=runner,
        resolve_tag=lambda _repo: "v1.0.0",
        managed_packages=lambda: (),
        replay_globals=lambda _packages: (),
        reresolve_ownership=lambda _tool: ownership,
    )
    return RunDeps(
        tools=[tool],
        updates=updates,
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
