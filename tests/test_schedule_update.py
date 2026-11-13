"""The headless single-tool update a schedule timer runs (24.2-06).

Everything runs in-process with fake ownership, a recording runner and fake version probes;
no real package manager, vendor CLI or timer is ever started.
"""

import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import setup
from installer import cli, cursor_shim, runlock, schedules
from installer.guards import REDIRECT_SENTINEL
from installer.helper_assets import schedule_runner
from installer.model import Tool, load_tools
from installer.ownership import Confidence, ManagerOwnership, Owner
from installer.platform import Platform
from installer.run import CommandError, run_captured_in_group
from installer.schedule_run import RunDeps, run_schedule
from installer.update import UpdateOutcome, UpdateService, UpdateTarget, resolve_update_argv

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


class _Service(UpdateService):
    """An UpdateService that records its runs and can act while one is in flight."""

    def __init__(
        self,
        ownership: ManagerOwnership,
        runner: Recorder,
        *,
        during: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            platform=_FEDORA,
            runner=runner,
            resolve_tag=lambda _repo: "v1.0.0",
            managed_packages=lambda: (),
            replay_globals=lambda _packages: (),
            reresolve_ownership=lambda _tool: ownership,
        )
        self.runs: list[str] = []
        self._during = during

    def run(self, target: UpdateTarget) -> UpdateOutcome:
        self.runs.append(target.tool.id)
        if self._during is not None:
            self._during()
        return super().run(target)


def _service(ownership: ManagerOwnership, runner: Recorder) -> _Service:
    return _Service(ownership, runner)


def _deps(
    tool: Tool,
    ownership: ManagerOwnership,
    runner: Recorder,
    versions: Callable[[Tool, ManagerOwnership], str | None],
    *,
    service: UpdateService | None = None,
    context: schedules.ScheduleContext | None = None,
) -> RunDeps:
    return RunDeps(
        tools=[tool],
        updates=service or _service(ownership, runner),
        resolve_owner=lambda _tool: ownership,
        probe_version=versions,
        context=context,
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


# --- the run lock, the cursor shim after each cursor update, the runner contract --------------


def test_run_schedule_takes_the_lock_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _recorder, _leaf = _claude(tmp_path, monkeypatch, "1.0", "1.1")
    lock_path = runlock.run_lock_path()
    held = runlock.try_acquire(lock_path, "installer")
    assert held is not None
    try:
        assert run_schedule("update-claude", deps, parent_holds_lock=False) == ("skipped: busy", 0)
    finally:
        held.release()
    assert vars(deps.updates)["runs"] == []

    seen: list[runlock.Holder | None] = []
    tool = deps.tools[0]
    ownership = _ownership(tool, "installer")
    service = _Service(ownership, Recorder(), during=lambda: seen.append(runlock.holder(lock_path)))
    free = _deps(tool, ownership, Recorder(), _versions("1.0", "1.1"), service=service)
    assert run_schedule("update-claude", free, parent_holds_lock=False)[1] == 0
    [holder] = seen
    assert holder is not None
    assert (holder.job, holder.pid) == ("update-claude", os.getpid())
    assert runlock.holder(lock_path) is None  # released
    again = runlock.try_acquire(lock_path, "installer")
    assert again is not None
    again.release()


def test_the_parent_holds_the_lock_so_the_run_never_opens_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deps, _recorder, _leaf = _claude(tmp_path, monkeypatch, "1.0", "1.1")
    assert run_schedule("update-claude", deps, parent_holds_lock=True)[1] == 0
    assert not runlock.run_lock_path().exists()


@dataclass(frozen=True)
class _CursorRig:
    deps: RunDeps
    service: _Service
    context: schedules.ScheduleContext
    link: Path
    agent: Path
    launcher: Path


def _decide(context: schedules.ScheduleContext, decided: bool | None) -> None:
    record = schedules.ScheduleRecord(decided, 6, "00:00", ())
    schedules.update_state(
        context.state_path, lambda state: replace(state, records={"update-cursor-agent": record})
    )


def _cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    decided: bool | None,
    models: tuple[str, ...] | None,
    agent_exists: bool = True,
    during: Callable[[_CursorRig], None] | None = None,
) -> _CursorRig:
    """Vendor-style `agent` and `cursor-agent` links to a fake launcher under a scratch HOME."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    launcher = tmp_path / "vendor" / "launcher"
    launcher.parent.mkdir()
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)
    agent, link = bin_dir / "agent", bin_dir / "cursor-agent"
    agent.symlink_to(launcher if agent_exists else tmp_path / "nowhere")
    link.symlink_to(launcher)
    context = schedules.context_for("fedora", checkout=tmp_path, read_models=lambda _agent: models)
    if decided is not None:
        _decide(context, decided)
    tool = _tool("cursor-agent")
    ownership = _ownership(tool, "installer")
    rigs: list[_CursorRig] = []
    service = _Service(
        ownership, Recorder(), during=(lambda: during(rigs[0])) if during is not None else None
    )
    deps = _deps(
        tool, ownership, Recorder(), _versions("1.0", "1.1"), service=service, context=context
    )
    rigs.append(_CursorRig(deps, service, context, link, agent, launcher))
    return rigs[0]


def _run_cursor(rig: _CursorRig) -> tuple[str, int]:
    deps = replace(rig.deps, probe_version=_versions("1.0", "1.1"))
    return run_schedule("update-cursor-agent", deps, parent_holds_lock=True)


def test_cursor_update_refreshes_the_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=True, models=("gpt-5.6-sol-xhigh", "other"))
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1", 0)
    assert cursor_shim.is_our_shim(rig.link)
    assert "--model 'gpt-5.6-sol-xhigh'" in rig.link.read_text()
    assert schedules.load_state(rig.context.state_path).state.cursor_shim == "listed"
    # An unchanged status writes nothing: the state file keeps its (aged) modification time.
    os.utime(rig.context.state_path, ns=(1, 1))
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1", 0)
    assert rig.context.state_path.stat().st_mtime_ns == 1


def test_cursor_update_with_a_model_not_listed_passes_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=True, models=("other",))
    line, code = _run_cursor(rig)
    assert code == 0
    assert line == (
        "ok: updated 1.0 → 1.1; gpt-5.6-sol-xhigh is not in your model list, "
        "the shim passes arguments through"
    )
    assert cursor_shim.is_our_shim(rig.link)
    assert "--model '" not in rig.link.read_text()
    assert schedules.load_state(rig.context.state_path).state.cursor_shim == "not-listed"


def test_cursor_update_with_an_unreadable_model_list_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=True, models=None)
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1; model unverified", 0)
    assert "--model 'gpt-5.6-sol-xhigh'" in rig.link.read_text()
    assert schedules.load_state(rig.context.state_path).state.cursor_shim == "unverified"


def test_a_foreign_cursor_agent_is_kept_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=True, models=("gpt-5.6-sol-xhigh",))
    rig.link.unlink()
    rig.link.write_text("#!/bin/sh\necho mine\n")
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1; your own cursor-agent was kept", 0)
    assert rig.link.read_text() == "#!/bin/sh\necho mine\n"
    assert schedules.load_state(rig.context.state_path).state.cursor_shim == "kept-foreign"


def test_cursor_update_with_a_dangling_agent_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=True, models=None, agent_exists=False)
    before = os.readlink(rig.link)
    assert _run_cursor(rig) == ("failed: ~/.local/bin/agent is missing or dangling", 1)
    assert rig.service.runs == []
    assert rig.link.is_symlink()
    assert os.readlink(rig.link) == before


def test_a_refresh_that_loses_the_agent_fails_the_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def break_agent(rig: _CursorRig) -> None:
        rig.agent.unlink()
        rig.agent.symlink_to(rig.launcher.parent / "gone")

    rig = _cursor(tmp_path, monkeypatch, decided=True, models=None, during=break_agent)
    line, code = _run_cursor(rig)
    assert code == 1
    assert line.startswith("failed: ~/.local/bin/agent is missing or dangling")


def test_off_during_the_update_is_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """R1-08: an off pressed while the update runs is never undone by the refresh."""

    def turn_off(rig: _CursorRig) -> None:
        _decide(rig.context, False)
        cursor_shim.restore_link(link=rig.link, agent=rig.agent)

    rig = _cursor(
        tmp_path, monkeypatch, decided=True, models=("gpt-5.6-sol-xhigh",), during=turn_off
    )
    cursor_shim.refresh_shim(
        link=rig.link, agent=rig.agent, model="gpt-5.6-sol-xhigh", models=("gpt-5.6-sol-xhigh",)
    )
    assert cursor_shim.is_our_shim(rig.link)
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1", 0)
    assert rig.link.is_symlink()
    assert os.readlink(rig.link) == os.readlink(rig.agent)
    state = schedules.load_state(rig.context.state_path).state
    assert schedules.record_for(state, "update-cursor-agent").decided is False


@pytest.mark.parametrize("decided", [False, None])
def test_run_with_the_row_off_writes_no_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decided: bool | None
) -> None:
    rig = _cursor(tmp_path, monkeypatch, decided=decided, models=("gpt-5.6-sol-xhigh",))
    assert _run_cursor(rig) == ("ok: updated 1.0 → 1.1", 0)
    assert rig.link.is_symlink()
    assert rig.service.runs == ["cursor-agent"]


def _fake_uv(tmp_path: Path, body: str) -> Path:
    uv = tmp_path / "bin" / "uv"
    uv.parent.mkdir(parents=True, exist_ok=True)
    uv.write_text(f"#!/bin/sh\n{body}\n")
    uv.chmod(0o755)
    return uv


def _runner_update(tmp_path: Path, uv: Path) -> tuple[int, Path, Path]:
    """Run the copied runner's `update claude` job in-process; returns (exit, log, lock)."""
    checkout = tmp_path / "checkout"
    checkout.mkdir(parents=True, exist_ok=True)
    (checkout / "setup.py").write_text("")
    log, lock = tmp_path / "state" / "schedules.log", tmp_path / "state" / "run.lock"
    code = schedule_runner.main(
        [
            *["update", "claude", "--installer", str(checkout), "--uv", str(uv)],
            *["--log", str(log), "--lock", str(lock), "--cap-bytes", "262144"],
        ]
    )
    return code, log, lock


def test_runner_and_installer_agree(tmp_path: Path) -> None:
    """Contract, 24.2-01 x 24.2-02: argv, log lines and the lock mean the same on both sides."""
    argv_file, lock_copy = tmp_path / "argv", tmp_path / "lock-copy"
    uv = _fake_uv(
        tmp_path,
        f'echo "$@" > "{argv_file}"\n/bin/cat "{tmp_path}/state/run.lock" > "{lock_copy}"\n'
        'echo "ok: up to date"',
    )
    code, log, lock = _runner_update(tmp_path, uv)
    assert code == 0
    # (a) the child argv is a valid --run-schedule invocation of the installer's own parser
    tail = argv_file.read_text().split()
    options = cli.parse_args(tail[tail.index("setup.py") + 1 :])
    assert (options.run_schedule, options.parent_holds_run_lock) == ("update-claude", True)
    # (b) the runner's log lines read back as the schedule's last run
    last = schedules.read_last_runs(log, lock)["update-claude"]
    assert (last.word, last.text) == ("ok", "ok: up to date")
    # (d) the lock content the runner wrote while the child ran parses as this run
    holder = runlock.holder(lock_copy)
    assert holder is not None
    assert (holder.job, holder.pid) == ("update-claude", os.getpid())
    assert re.fullmatch(r"update-claude \d+ \S+\n", lock_copy.read_text())
    # (c) a lock held through runlock.try_acquire makes the runner log `skipped: busy`
    _assert_busy_runner_skips(tmp_path / "busy")


def _assert_busy_runner_skips(tmp_path: Path) -> None:
    uv = _fake_uv(tmp_path, f'echo ran > "{tmp_path}/ran"')
    lock = tmp_path / "state" / "run.lock"
    held = runlock.try_acquire(lock, "installer")
    assert held is not None
    try:
        code, log, _lock = _runner_update(tmp_path, uv)
    finally:
        held.release()
    assert code == 0
    last = schedules.read_last_runs(log, lock)["update-claude"]
    assert (last.word, last.text) == ("skipped", "skipped: busy")
    assert not (tmp_path / "ran").exists()
