"""The update-all runner and its composition boundaries."""

import inspect
import os
import sys
from pathlib import Path

import pytest

import setup
from installer import compose, pnpm_globals, update_all
from installer.helper_assets import schedule_runner
from installer.model import Tool
from installer.platform import Platform
from installer.run import (
    TIMEOUT_CODE,
    CommandError,
    Runner,
    run_bounded,
    run_captured,
    run_captured_in_group,
)
from installer.schedule_run import update_all_runner
from installer.terminal_shell import TerminalShellResult
from tests.compose_patch import patch_composition


def _fake_schedule(*_a: object, **_k: object) -> tuple[str, int]:
    return "ok: done", 0


def _fake_none(*_a: object, **_k: object) -> None:
    return None


def _fake_deps(*_a: object, **_k: object) -> object:
    return object()


_PLATFORM = Platform(os="fedora", arch="amd64", immutable=False, has_brew=False)


def test_the_update_all_runner_bounds_closes_stdin_and_sets_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("SUDO_ASKPASS", "planted")
    monkeypatch.delenv("HOMEBREW_NO_SUDO", raising=False)
    before = dict(os.environ)
    code = """import os, sys
checks = [os.environ.get('HOMEBREW_NO_SUDO') == '1',
          os.environ.get('HOMEBREW_NO_AUTOREMOVE') == '1',
          os.environ.get('UV_NO_MODIFY_PATH') == '1',
          'SUDO_ASKPASS' not in os.environ,
          os.environ.get('PATH') == sys.argv[1], os.environ.get('HOME') == sys.argv[2],
          sys.stdin.read() == '', os.getsid(0) == os.getpid()]
for i, ok in enumerate(checks, 1):
    if not ok: sys.exit(i)
"""
    update_all_runner([sys.executable, "-c", code, str(tmp_path), str(tmp_path)])
    assert dict(os.environ) == before
    with pytest.raises(CommandError) as error:
        update_all_runner(
            [sys.executable, "-c", "import sys; print('first', file=sys.stderr); sys.exit(3)"]
        )
    assert error.value.returncode == 3 and error.value.detail.splitlines()[0] == "first"
    with pytest.raises(CommandError) as error:
        update_all_runner([sys.executable, "-c", "import time; time.sleep(60)"], timeout=1)
    assert error.value.returncode == TIMEOUT_CODE


def test_the_runner_takes_a_timeout_run_bounded_can_override() -> None:
    assert (
        inspect.signature(update_all_runner).parameters["timeout"].default
        == update_all.COMMAND_TIMEOUT
        == 1200
    )
    assert vars(schedule_runner)["_KILL_GRACE"] > update_all.KILL_GRACE
    with pytest.raises(CommandError) as error:
        run_bounded(update_all_runner, [sys.executable, "-c", "import time; time.sleep(60)"], 1)
    assert error.value.returncode == TIMEOUT_CODE


def test_setup_wires_the_bounded_runner_for_update_all_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(setup, "detect", lambda: _PLATFORM)
    seen: list[object] = []

    def deps(
        _tools: list[Tool], _platform: Platform, *, runner: Runner = run_captured_in_group
    ) -> object:
        seen.append(runner)
        return object()

    monkeypatch.setattr(setup, "_schedule_run_deps", deps)
    monkeypatch.setattr(setup, "run_schedule", _fake_schedule)
    assert setup.main(["--run-schedule", "update-all"]) == 0
    assert seen == [update_all_runner]

    def legacy(_tools: list[Tool], _platform: Platform) -> object:
        seen.append("legacy")
        return object()

    monkeypatch.setattr(setup, "_schedule_run_deps", legacy)
    assert setup.main(["--run-schedule", "update-claude", "--parent-holds-run-lock"]) == 0
    assert seen[-1] == "legacy"
    monkeypatch.undo()
    calls: list[object] = []

    class Refresh:
        resolve_owner = None

    def build(
        _tools: list[Tool], _platform: Platform, **kwargs: object
    ) -> tuple[object, object, None, None]:
        calls.append(kwargs["runner"])
        return Refresh(), object(), None, None

    patch_composition(monkeypatch, "_build_services", build)
    vars(setup)["_schedule_run_deps"]([], _PLATFORM, runner=update_all_runner)
    vars(setup)["_schedule_run_deps"]([], _PLATFORM)
    assert calls == [update_all_runner, run_captured_in_group]


def _assert_sites(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: Runner, *, default: bool
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    seen: list[object] = []

    def replay(_packages: object, **kwargs: object) -> tuple[str, ...]:
        seen.append(kwargs["runner"])
        return ()

    def sync(**kwargs: object) -> TerminalShellResult:
        seen.append(kwargs["runner"])
        return TerminalShellResult()

    monkeypatch.setattr(pnpm_globals, "reinstall_node_globals", replay)
    monkeypatch.setattr(compose, "sync_terminal_shells", sync)
    monkeypatch.setattr(compose, "sync_message", _fake_none)
    build = vars(compose)["_build_services"]
    _, updates, _, _ = build([], _PLATFORM) if default else build([], _PLATFORM, runner=runner)
    assert vars(updates)["_runner"] is runner
    vars(updates)["_replay_globals"](["pkg"])
    vars(updates)["_terminal_follow_up"]()
    assert seen == [runner, runner]


def test_every_runner_site_of_the_update_path_gets_the_bounded_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Queries, probes, pnpm list/bin, smoke checks, model and GitHub lookups are bounded."""
    _assert_sites(monkeypatch, tmp_path, update_all_runner, default=False)


def test_the_default_routes_keep_their_runners(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _assert_sites(monkeypatch, tmp_path, run_captured, default=True)


def test_the_runner_never_adds_the_variable_to_the_stdlib_runner() -> None:
    assert "UV_NO_MODIFY_PATH" not in vars(schedule_runner)["_CHILD_ENV"]
    assert "UV_NO_MODIFY_PATH" not in vars(schedule_runner)["_PASSED_ENV"]


def test_the_stop_budget_outlasts_the_installer_cleanup() -> None:
    assert vars(schedule_runner)["_UPDATE_ALL_STOP_BUDGET"] > update_all.CLEANUP_BUDGET
    assert update_all.CLEANUP_BUDGET == 4 * update_all.KILL_GRACE


def test_the_update_all_route_closes_stdin_for_queries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import subprocess
    from collections.abc import Generator
    from contextlib import contextmanager

    code = """import os
from installer.schedule_run import update_all_stdin_closed
before = os.fstat(0)
with update_all_stdin_closed():
    assert os.read(0, 1) == b''
assert os.fstat(0) == before
"""
    child = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE)
    try:
        assert child.wait(timeout=10) == 0
    finally:
        if child.stdin is not None:
            child.stdin.close()
        if child.poll() is None:
            child.kill()
            child.wait()
    seen: list[str] = []

    @contextmanager
    def closed() -> Generator[None]:
        seen.append("entered")
        yield

    monkeypatch.setattr(setup, "update_all_stdin_closed", closed)
    monkeypatch.setattr(setup, "detect", lambda: _PLATFORM)
    monkeypatch.setattr(setup, "_schedule_run_deps", _fake_deps)
    monkeypatch.setattr(setup, "run_schedule", _fake_schedule)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert setup.main(["--run-schedule", "update-all"]) == 0
    assert seen == ["entered"]
    assert setup.main(["--run-schedule", "update-claude"]) == 0
    assert seen == ["entered"]


def test_the_cleanup_is_capped_and_reports_a_group_that_survives(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import contextlib
    import signal
    import time

    real_killpg = os.killpg
    groups: list[int] = []

    def ineffective(pid: int, sig: int) -> None:
        if sig == 0:
            real_killpg(pid, sig)
        else:
            groups.append(pid)

    monkeypatch.setattr(os, "killpg", ineffective)
    monkeypatch.setattr(update_all, "KILL_GRACE", 0.2)
    started = time.monotonic()
    try:
        with pytest.raises(CommandError) as error:
            update_all_runner([sys.executable, "-c", "import time; time.sleep(60)"], timeout=0.5)
        assert "did not end after SIGKILL" in error.value.detail
        assert time.monotonic() - started < 5
        assert capsys.readouterr().err == "update-all: a command group did not end after SIGKILL\n"
    finally:
        for pid in set(groups):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                real_killpg(pid, signal.SIGKILL)


@pytest.mark.parametrize("interrupt", [False, True])
def test_a_command_that_times_out_leaves_no_helper_behind_the_unlock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, interrupt: bool
) -> None:
    """A separate session survives; the real stop must wait for installer cleanup."""
    import contextlib
    import fcntl
    import json
    import signal
    import threading
    import time

    from tests.test_update_all_job import make_job, run_job

    _home, checkout, uv, lock = make_job(tmp_path, monkeypatch, "hang")
    config_path = tmp_path / "config.json"
    config = json.loads(config_path.read_text())
    config.update(
        pid_dir=str(tmp_path),
        hang_timeout=60 if interrupt else 1,
        ignore_term=interrupt,
        kill_grace=1,
    )
    config_path.write_text(json.dumps(config))
    if interrupt:
        root = Path(__file__).resolve().parent.parent
        child_code = (
            f"import sys; sys.path.insert(0, {str(root)!r}); "
            "from tests.update_all_child import main; "
            f"raise SystemExit(main({str(config_path)!r}, sys.argv[1:]))"
        )
        uv.write_text(
            f"#!{sys.executable}\nimport subprocess, signal, sys\n"
            "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
            f"subprocess.Popen([{sys.executable!r}, '-c', {child_code!r}, "
            "*sys.argv[sys.argv.index('setup.py') + 1:]]).wait()\n"
        )
    results: list[tuple[int, list[str]]] = []
    thread = threading.Thread(target=lambda: results.append(run_job(tmp_path, checkout, uv, lock)))
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not all((tmp_path / name).exists() for name in ("command", "group", "escaped")):
            assert time.monotonic() < deadline, (
                (tmp_path / "traceback").read_text()
                if (tmp_path / "traceback").exists()
                else "child did not start"
            )
            time.sleep(0.02)
        if interrupt:
            with pytest.raises(vars(schedule_runner)["_Interrupted"]):
                vars(schedule_runner)["_on_signal"](signal.SIGTERM, None)
        thread.join(45)
        assert not thread.is_alive()
        assert results and results[0][0] == 1
        assert "failed:" in results[0][1][-1]
        fd = os.open(lock, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
        group = int((tmp_path / "group").read_text())
        escaped = int((tmp_path / "escaped").read_text())
        deadline = time.monotonic() + 5
        while True:
            try:
                os.kill(group, 0)
            except ProcessLookupError:
                break
            assert time.monotonic() < deadline, "group helper survived"
            time.sleep(0.05)
        os.kill(escaped, 0)
    finally:
        for name in ("command", "group", "escaped"):
            path = tmp_path / name
            if path.exists():
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.kill(int(path.read_text()), signal.SIGKILL)
        thread.join(45)


def test_update_all_refuses_root_before_any_lock_refresh_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from dataclasses import fields, replace
    from datetime import UTC, datetime

    from installer import schedule_run, schedules
    from tests.update_all_doubles import (
        SequenceRefresher,
        SpyService,
        catalog_tool,
        held_by_parent,
        run_deps,
        state,
    )
    from tests.update_check_doubles import FakeNotifier, check_context

    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("brew")
    item = state(tool, "installer")
    service = SpyService()
    refresh = SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now)
    notify = FakeNotifier()
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=refresh,
        notify=notify,
        now=lambda: now,
        euid=lambda: 0,
    )
    refused = ("failed: update-all refuses to run as root", 1)
    assert schedule_run.run_schedule("update-all", deps, parent_holds_lock=False) == refused
    assert not context.lock_path.parent.exists()
    assert refresh.calls == [] and service.runs == [] and notify.calls == []
    with held_by_parent(context) as pid:
        before = context.lock_path.read_bytes()
        assert (
            schedule_run.run_schedule(
                "update-all", deps, parent_holds_lock=True, lock_holder_pid=pid
            )
            == refused
        )
        assert context.lock_path.read_bytes() == before
    assert refresh.calls == [] and service.runs == [] and notify.calls == []
    assert not schedules.update_all_log_path(context).exists()
    assert not schedules.updated_today_path(context).exists()
    assert [field.name for field in fields(schedule_run.RunDeps)][-2:] == ["now", "euid"]
    positional = schedule_run.RunDeps(
        deps.tools, deps.updates, deps.resolve_owner, deps.probe_version, context
    )
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert schedule_run.run_schedule("update-all", positional, parent_holds_lock=False) == refused
    monkeypatch.setattr(setup, "detect", lambda: _PLATFORM)

    def fake_deps(*_a: object, **_k: object) -> schedule_run.RunDeps:
        return deps

    monkeypatch.setattr(setup, "_schedule_run_deps", fake_deps)
    assert setup.main(["--run-schedule", "update-all"]) == 1
    assert capsys.readouterr().out == refused[0] + "\n"
    assert refresh.calls == [] and service.runs == [] and notify.calls == []
    assert schedule_run.run_schedule(
        "update-all", replace(deps, euid=lambda: 1000), parent_holds_lock=False
    ) == ("ok: 1 updated, 0 skipped", 0)
    assert service.runs == ["brew"]

    state_dir = tmp_path / "timer-state"
    marker = tmp_path / "launched"
    uv = tmp_path / "fake-uv"
    uv.write_text(f"#!{sys.executable}\nopen({str(marker)!r}, 'w').write('ran')\n")
    uv.chmod(0o755)
    assert (
        schedule_runner.main(
            [
                "update-all",
                "--installer",
                str(tmp_path / "co"),
                "--uv",
                str(uv),
                "--log",
                str(state_dir / "log"),
                "--lock",
                str(state_dir / "lock"),
                "--cap-bytes",
                "1000",
            ]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "schedule_runner: failed: update-all refuses to run as root\n"
    assert not state_dir.exists() and not marker.exists()


def test_refused_tools_are_skipped_with_their_text_and_never_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from installer import schedules
    from installer.model import Method
    from tests.update_all_doubles import (
        SequenceRefresher,
        SpyService,
        catalog_tool,
        run_deps,
        run_update_all,
        state,
    )
    from tests.update_check_doubles import check_context

    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tools = [catalog_tool(name) for name in ("jq", "git", "java", "node", "pinned", "mystery")]
    jq, git, java, node, pinned, mystery = tools
    states = {
        "jq": state(jq, "os-package", outdated=True, package="jq"),
        "git": state(git, "dnf", outdated=True, package="git"),
        "java": state(
            java,
            "installer",
            outdated=True,
            method=Method(kind="sdkman", params={}),
            package="java",
        ),
        "node": state(node, "volta", outdated=True, package="node"),
        "pinned": state(
            pinned,
            "installer",
            outdated=True,
            method=Method(
                kind="tarball",
                params={"url": "https://example.test/{ver}", "version": "1", "sha256": "a"},
            ),
        ),
        "mystery": state(mystery, "unknown", outdated=True),
    }
    service = SpyService()
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={k: v.ownership for k, v in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 0 updated, 6 skipped", 0)
    assert service.runs == []
    log = schedules.update_all_log_path(context).read_text()
    for text in (
        "jq skipped: os-package owns jq",
        "git skipped: dnf owns git",
        "java skipped: SDKMAN owns this tool; this installer does not run SDKMAN's "
        "interactive upgrade — update it with `sdk upgrade java` in your own terminal",
        "node skipped: managed by Volta — update it with `volta install node`",
        "pinned skipped: pinned; update outside or re-pin",
        "mystery skipped: no manager claimed this tool",
    ):
        assert text in log


def test_a_script_tool_without_an_update_path_is_skipped_but_its_own_row_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from installer import schedule_run, schedules
    from tests.update_all_doubles import (
        SequenceRefresher,
        SpyService,
        catalog_tool,
        run_deps,
        run_update_all,
        state,
    )
    from tests.update_check_doubles import check_context

    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("opencode", update=False)
    item = state(tool, "installer", outdated=True)
    service = SpyService()
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 0 updated, 1 skipped", 0)
    assert service.runs == []
    assert (
        "opencode skipped: no unattended update path"
        in schedules.update_all_log_path(context).read_text()
    )
    assert schedule_run.run_schedule("update-opencode", deps, parent_holds_lock=True) == (
        "ok: updated",
        0,
    )
    assert service.runs == ["opencode"]


def test_the_parent_lock_flag_is_verified_through_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from datetime import UTC, datetime

    from installer import runlock, schedules
    from tests.update_all_doubles import (
        SequenceRefresher,
        SpyService,
        catalog_tool,
        held_by_parent,
        run_deps,
        state,
    )
    from tests.update_check_doubles import check_context

    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    tool = catalog_tool("brew")
    item = state(tool, "installer")
    service = SpyService()
    refresh = SequenceRefresher(tmp_path / "versions", [{tool.id: item}], clock=lambda: now)
    deps = run_deps(
        [tool],
        context,
        service=service,
        owners={tool.id: item.ownership},
        refresh=refresh,
        now=lambda: now,
    )
    monkeypatch.setattr(setup, "detect", lambda: _PLATFORM)

    def fake_deps(*_a: object, **_k: object) -> object:
        return deps

    monkeypatch.setattr(setup, "_schedule_run_deps", fake_deps)
    original = runlock.try_acquire
    calls: list[str] = []

    def acquire(path: Path, job: str) -> runlock.RunLock | None:
        calls.append(job)
        return original(path, job)

    monkeypatch.setattr(runlock, "try_acquire", acquire)
    argv = ["--run-schedule", "update-all"]
    flag = ["--parent-holds-run-lock"]
    pid = ["--lock-holder-pid", str(os.getpid())]
    other = original(context.lock_path, "update-claude")
    assert other is not None
    try:
        before = context.lock_path.read_bytes()
        assert setup.main(argv) == 0
        assert capsys.readouterr().out == "skipped: busy\n"
        assert calls == ["update-all"] and service.runs == [] and refresh.calls == []
        assert context.lock_path.read_bytes() == before
        assert setup.main(argv + flag + pid) == 1
        assert (
            capsys.readouterr().out == "failed: update-all refuses an unverified parent run lock\n"
        )
        assert context.lock_path.read_bytes() == before
    finally:
        other.release()
    assert not schedules.update_all_log_path(context).exists()
    assert not schedules.updated_today_path(context).exists()
    for extra in (flag, flag + pid):
        before = context.lock_path.read_bytes()
        assert setup.main(argv + extra) == 1
        assert (
            capsys.readouterr().out == "failed: update-all refuses an unverified parent run lock\n"
        )
        assert context.lock_path.read_bytes() == before
    context.lock_path.write_text(f"update-all {os.getpid()} live\n")
    before = context.lock_path.read_bytes()
    assert setup.main(argv + flag + pid) == 1
    assert capsys.readouterr().out == "failed: update-all refuses an unverified parent run lock\n"
    assert context.lock_path.read_bytes() == before
    assert service.runs == [] and refresh.calls == [] and calls == ["update-all"]
    assert not schedules.update_all_log_path(context).exists()
    assert not schedules.updated_today_path(context).exists()
    assert setup.main(argv) == 0
    assert capsys.readouterr().out == "ok: 1 updated, 0 skipped\n"
    assert calls == ["update-all", "update-all"] and runlock.holder(context.lock_path) is None
    assert service.runs == ["brew"]
    with held_by_parent(context) as parent:
        calls.clear()
        assert setup.main(argv + flag + ["--lock-holder-pid", str(parent)]) == 0
        assert capsys.readouterr().out == "ok: 0 updated, 1 skipped\n"
        assert calls == []


def test_no_privilege_escalation_in_the_new_code() -> None:
    """Prove these modules name no escalator, not that vendor tools cannot escalate."""
    import ast

    root = Path(__file__).resolve().parent.parent / "installer"
    paths = [
        root / name
        for name in (
            "update_all.py",
            "update_all_state.py",
            "schedule_run.py",
            "helper_assets/schedule_runner.py",
        )
    ]
    forbidden = {"sudo", "pkexec", "doas"}
    assert len(paths) == 4
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                assert forbidden.isdisjoint(word.lower() for word in node.value.split())
            if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
                first = node.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    assert first.value.lower() not in forbidden
    assert "homebrew_no_sudo" not in forbidden


def test_children_run_with_the_house_policy_through_the_real_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from installer import schedules, update_all_state
    from installer.update import UpdateService
    from tests.update_all_doubles import (
        FEDORA,
        SequenceRefresher,
        catalog_tool,
        run_deps,
        run_update_all,
        state,
    )
    from tests.update_check_doubles import check_context

    context = check_context(tmp_path, monkeypatch)
    monkeypatch.setenv("PATH", str(tmp_path))
    now = datetime(2026, 11, 22, tzinfo=UTC)
    brew, uv, jq, ruff = (catalog_tool(name) for name in ("brew", "uv", "jq", "ruff"))
    tools = [brew, uv, jq, ruff]
    states = {
        "brew": state(brew, "installer"),
        "uv": state(uv, "installer"),
        "jq": state(jq, "brew", outdated=True, package="jq"),
        "ruff": state(ruff, "uv", outdated=True, package="ruff"),
    }
    for manager in ("brew", "uv"):
        update_all_state.record_updated(
            schedules.updated_today_path(context), manager, today=now.date(), by="update-claude"
        )
    calls: list[list[str]] = []
    service = UpdateService(
        platform=FEDORA,
        runner=lambda argv: calls.append(argv.copy()),
        managed_packages=lambda: (),
        replay_globals=lambda _items: (),
        reresolve_ownership=lambda tool: states[tool.id].ownership,
    )
    deps = run_deps(
        tools,
        context,
        service=service,
        owners={key: item.ownership for key, item in states.items()},
        refresh=SequenceRefresher(tmp_path / "versions", [states], clock=lambda: now),
        now=lambda: now,
    )
    assert run_update_all(deps) == ("ok: 2 updated, 2 skipped", 0)
    assert calls == [["brew", "upgrade", "jq"], ["uv", "tool", "upgrade", "ruff"]]
