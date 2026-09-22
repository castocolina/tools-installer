"""Tests for installer.systemd_daemon (the Linux mechanism tier, mirroring
installer/daemon.py's macOS launchd shape) and this plan's composition-root
wiring in setup.py (`_build_daemon_policy`'s Linux branch, `_timer_state_cache`).

Every test uses an injected fake `run`/`read_output` -- never real
`systemctl` -- mirroring tests/test_daemon.py's own injectable-run-seam
tests and tests/test_policy_daemon.py's fixture structure.
"""

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

import setup
from installer import daemon, systemd_daemon
from installer.daemon import DaemonScheduleError
from installer.enums import DaemonState
from installer.platform import Platform
from installer.policy import Policy, PolicyResult, linux_daemon_policy
from installer.run import CommandError

# --- shared fakes ------------------------------------------------------------


class _RecordingRun:
    """Records every argv; never raises."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)


class _ScriptedReadOutput:
    """Records every argv; returns the scripted answers in order, repeating
    the last once exhausted."""

    def __init__(self, *answers: str) -> None:
        self.calls: list[list[str]] = []
        self._answers = list(answers) or ["active"]

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        index = min(len(self.calls) - 1, len(self._answers) - 1)
        return self._answers[index]


class _RaisingReadOutput:
    """Records every argv; always raises CommandError."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        raise CommandError(cmd, 1)


class _Clock:
    """An injected monotonic clock double: advances only when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, delta: float) -> None:
        self.now += delta


def _platform(os_name: str = "fedora") -> Platform:
    return Platform(os=os_name, arch="amd64", immutable=False, has_brew=False)


@dataclass
class _Paths:
    unit_dir: Path
    log_path: Path
    wrapper_bin_dir: Path
    script_path: Path
    state_path: Path
    uv_path: Path
    tmpdir_value: str
    home_value: str


def _make_paths(tmp_path: Path) -> _Paths:
    script_path = tmp_path / "scripts" / "prune-tmp-linux.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    return _Paths(
        unit_dir=tmp_path / "config" / "systemd" / "user",
        log_path=tmp_path / "state" / "prune-daemon.log",
        wrapper_bin_dir=tmp_path / "bin",
        script_path=script_path,
        state_path=tmp_path / ".myshellrc",
        uv_path=tmp_path / "uv",
        tmpdir_value=str(tmp_path / "tmp"),
        home_value=str(tmp_path / "home"),
    )


def _build(
    paths: _Paths,
    *,
    run: object,
    read_output: object = systemd_daemon.query_systemctl,
    timer_cache: systemd_daemon.TimerStateCache | None = None,
) -> Policy:
    return linux_daemon_policy(
        unit_dir=paths.unit_dir,
        log_path=paths.log_path,
        wrapper_bin_dir=paths.wrapper_bin_dir,
        script_path=paths.script_path,
        state_path=paths.state_path,
        installed_tools={},
        path_value="/usr/bin:/bin",
        tmpdir_value=paths.tmpdir_value,
        home_value=paths.home_value,
        uv_path=paths.uv_path,
        run=run,  # type: ignore[arg-type]
        read_output=read_output,  # type: ignore[arg-type]
        timer_cache=timer_cache,
    )


# --- End-to-end: the tracer's own proof -------------------------------------


def test_end_to_end_enable_and_disable_background_cleanup_on_linux(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    unit_dir = tmp_path / ".config" / "systemd" / "user"
    monkeypatch.setattr(setup, "_LINUX_DAEMON_UNIT_DIR", unit_dir)
    monkeypatch.setattr(setup, "_LINUX_DAEMON_LOG_PATH", tmp_path / "log" / "prune-daemon.log")
    monkeypatch.setattr(setup, "_DAEMON_STATE_PATH", tmp_path / ".myshellrc")
    monkeypatch.setattr(setup, "_DEFAULT_BIN_DIR", tmp_path / "bin")

    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in ("systemctl", "uv") else None

    fake_run = _RecordingRun()

    def read_output(cmd: list[str]) -> str:
        # The real D-01c predicate, exercised end-to-end: the answer tracks
        # unit-file presence rather than being hardcoded, so a
        # presence-only implementation would pass the post-remove half for
        # the wrong reason (excluded separately by the runtime-state tests).
        return "active" if systemd_daemon.units_present(unit_dir) else "inactive"

    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _platform(), {}, which=which, run=fake_run, read_output=read_output
    )
    assert policy is not None
    assert policy.id.startswith("daemon:")

    result = policy.apply()
    assert result.warning is None
    service_path, timer_path = systemd_daemon.unit_paths(unit_dir)
    assert service_path.exists()
    assert timer_path.exists()
    assert oct(service_path.stat().st_mode)[-3:] == "644"
    assert oct(timer_path.stat().st_mode)[-3:] == "644"
    assert fake_run.calls == [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", systemd_daemon.TIMER_NAME],
        ["systemctl", "--user", "restart", systemd_daemon.TIMER_NAME],
    ]

    remove_result = policy.remove()
    assert remove_result.warning is None
    assert not service_path.exists()
    assert not timer_path.exists()
    assert policy.is_active is not None
    assert policy.is_active() is False


# --- Systemd availability gate (D-01b) --------------------------------------


def test_build_daemon_policy_returns_none_when_systemctl_unresolvable_on_linux() -> None:
    def which(_name: str) -> str | None:
        return None

    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _platform(), {}, which=which
    )
    assert policy is None


def test_build_daemon_policy_returns_a_policy_when_systemctl_resolves_but_uv_does_not() -> None:
    """Mirrors test_build_daemon_policy_is_fail_closed_not_fail_hidden's
    macOS contract: an unresolvable uv is the existing fail-closed-at-apply
    behavior, not a second fail-hidden gate."""

    def which(name: str) -> str | None:
        return "/usr/bin/systemctl" if name == "systemctl" else None

    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _platform(), {}, which=which
    )
    assert policy is not None


def test_build_daemon_policy_never_consults_the_lookup_for_systemctl_on_macos() -> None:
    resolved: list[str] = []

    def which(name: str) -> str | None:
        resolved.append(name)
        return "/usr/bin/uv" if name == "uv" else None

    macos = Platform(os="macos", arch="arm64", immutable=False, has_brew=True)
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        macos, {}, which=which
    )
    assert policy is not None
    assert "systemctl" not in resolved


# --- Mechanism-layer tests ---------------------------------------------------

_VALID_SERVICE_KWARGS: dict[str, object] = {
    "uv_path": Path("/home/tester/.local/bin/uv"),
    "wrapper_path": Path("/home/tester/.local/bin/tools-installer-prune-daemon"),
    "script_path": Path("/home/tester/tools-installer/scripts/prune-tmp-linux.sh"),
    "log_path": Path("/home/tester/.local/state/tools-installer/prune-daemon.log"),
    "tmpdir": "/tmp",
    "home": "/home/tester",
    "path_value": "/usr/bin:/bin",
}


def _service_kwargs(**overrides: object) -> dict[str, object]:
    merged = dict(_VALID_SERVICE_KWARGS)
    merged.update(overrides)
    return merged


def test_render_service_exec_start_order_and_quoting() -> None:
    text = systemd_daemon.render_service(**_service_kwargs())  # type: ignore[arg-type]
    assert "[Service]" in text
    assert "Type=oneshot" in text
    exec_line = next(line for line in text.splitlines() if line.startswith("ExecStart="))
    assert exec_line == (
        'ExecStart="/home/tester/.local/bin/uv" "run" "--no-project" "--script" '
        '"/home/tester/.local/bin/tools-installer-prune-daemon" "--script" '
        '"/home/tester/tools-installer/scripts/prune-tmp-linux.sh" "--log" '
        '"/home/tester/.local/state/tools-installer/prune-daemon.log" "--cap-bytes" '
        f'"{systemd_daemon.DEFAULT_CAP_BYTES}" "--" "--apply" "--minutes" '
        f'"{systemd_daemon.DEFAULT_AGE_MINUTES}"'
    )


def test_render_service_environment_lines_are_single_quoted_tokens() -> None:
    text = systemd_daemon.render_service(
        **_service_kwargs(path_value="/usr/bin:/bin with space")  # type: ignore[arg-type]
    )
    lines = text.splitlines()
    assert 'Environment="PATH=/usr/bin:/bin with space"' in lines
    assert 'Environment="HOME=/home/tester"' in lines
    assert 'Environment="TMPDIR=/tmp"' in lines


@pytest.mark.parametrize(
    "overrides",
    [
        {"uv_path": Path("relative/uv")},
        {"uv_path": Path()},
        {"wrapper_path": Path("relative/wrapper")},
        {"script_path": Path("relative/script.sh")},
        {"log_path": Path("relative/log")},
        {"home": ""},
        {"home": "relative/home"},
        {"tmpdir": ""},
        {"tmpdir": "relative/tmp"},
        {"age_minutes": 0},
        {"path_value": 'has"quote'},
        {"path_value": "has\\backslash"},
        {"path_value": "has%percent"},
        {"path_value": "has\nnewline"},
        {"path_value": "has\rcarriage"},
    ],
)
def test_render_service_rejects_invalid_input(overrides: dict[str, object]) -> None:
    with pytest.raises(DaemonScheduleError):
        systemd_daemon.render_service(**_service_kwargs(**overrides))  # type: ignore[arg-type]


def test_render_service_raises_with_zero_filesystem_side_effects(tmp_path: Path) -> None:
    before = list(tmp_path.iterdir())
    with pytest.raises(DaemonScheduleError):
        systemd_daemon.render_service(**_service_kwargs(age_minutes=0))  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == before


def test_render_timer_shape() -> None:
    text = systemd_daemon.render_timer()
    assert f"OnBootSec={systemd_daemon.DEFAULT_BOOT_DELAY}" in text
    assert f"OnUnitActiveSec={systemd_daemon.DEFAULT_INTERVAL}" in text
    assert f"Unit={systemd_daemon.SERVICE_NAME}" in text
    assert "[Install]" in text
    assert "WantedBy=timers.target" in text
    assert "Persistent" not in text


def test_write_units_validates_before_creating_directory_or_files(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    with pytest.raises(DaemonScheduleError):
        systemd_daemon.write_units(
            unit_dir,
            uv_path=Path("relative/uv"),
            wrapper_path=Path("/abs/wrapper"),
            script_path=Path("/abs/script.sh"),
            log_path=Path("/abs/log"),
            tmpdir="/tmp",
            home="/home/tester",
            path_value="/usr/bin",
        )
    assert not unit_dir.exists()


def test_write_units_writes_both_files_at_0o644(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    systemd_daemon.write_units(
        unit_dir,
        uv_path=tmp_path / "uv",
        wrapper_path=tmp_path / "wrapper",
        script_path=tmp_path / "script.sh",
        log_path=tmp_path / "log",
        tmpdir=str(tmp_path / "tmp"),
        home=str(tmp_path / "home"),
        path_value="/usr/bin",
    )
    service_path, timer_path = systemd_daemon.unit_paths(unit_dir)
    assert service_path.exists()
    assert timer_path.exists()
    assert oct(service_path.stat().st_mode)[-3:] == "644"
    assert oct(timer_path.stat().st_mode)[-3:] == "644"


def test_units_present_requires_both_files(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    service_path, timer_path = systemd_daemon.unit_paths(unit_dir)
    assert systemd_daemon.units_present(unit_dir) is False
    unit_dir.mkdir(parents=True)
    service_path.write_text("x")
    assert systemd_daemon.units_present(unit_dir) is False
    timer_path.write_text("x")
    assert systemd_daemon.units_present(unit_dir) is True


# --- Runtime state (D-01c) ---------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("active", DaemonState.ACTIVE),
        ("activating", DaemonState.ACTIVE),
        ("reloading", DaemonState.ACTIVE),
        ("inactive", DaemonState.INACTIVE),
        ("failed", DaemonState.INACTIVE),
        ("deactivating", DaemonState.INACTIVE),
    ],
)
def test_probe_timer_state_maps_systemctl_answers(answer: str, expected: DaemonState) -> None:
    read_output = _ScriptedReadOutput(answer)
    assert systemd_daemon.probe_timer_state(read_output=read_output) is expected
    assert read_output.calls == [["systemctl", "--user", "is-active", systemd_daemon.TIMER_NAME]]


def test_probe_timer_state_reports_unavailable_on_command_error() -> None:
    assert systemd_daemon.probe_timer_state(read_output=_RaisingReadOutput()) is (
        DaemonState.UNAVAILABLE
    )


def test_probe_timer_state_reports_unavailable_on_os_error() -> None:
    def read_output(cmd: list[str]) -> str:
        raise OSError(f"boom: {cmd}")

    assert systemd_daemon.probe_timer_state(read_output=read_output) is DaemonState.UNAVAILABLE


def _write_units_present(unit_dir: Path) -> None:
    unit_dir.mkdir(parents=True, exist_ok=True)
    (unit_dir / systemd_daemon.SERVICE_NAME).write_text("x")
    (unit_dir / systemd_daemon.TIMER_NAME).write_text("x")


def test_timer_state_files_present_but_inactive_reports_inactive(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)
    result = systemd_daemon.timer_state(unit_dir, read_output=_ScriptedReadOutput("inactive"))
    assert result is DaemonState.INACTIVE


def test_timer_state_files_present_but_failed_reports_inactive(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)
    result = systemd_daemon.timer_state(unit_dir, read_output=_ScriptedReadOutput("failed"))
    assert result is DaemonState.INACTIVE


def test_timer_state_no_files_reports_inactive_without_any_argv(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    read_output = _ScriptedReadOutput("active")
    result = systemd_daemon.timer_state(unit_dir, read_output=read_output)
    assert result is DaemonState.INACTIVE
    assert read_output.calls == []


def test_timer_state_files_present_and_active_reports_active(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)
    result = systemd_daemon.timer_state(unit_dir, read_output=_ScriptedReadOutput("active"))
    assert result is DaemonState.ACTIVE


def test_timer_state_cache_read_memoizes_within_ttl_reprobes_after_expiry_and_invalidate() -> None:
    calls = 0

    def probe() -> DaemonState:
        nonlocal calls
        calls += 1
        return DaemonState.ACTIVE

    clock = _Clock()
    cache = systemd_daemon.TimerStateCache(probe, ttl=10.0, clock=clock)

    assert cache.read() is DaemonState.ACTIVE
    assert cache.read() is DaemonState.ACTIVE
    assert cache.read() is DaemonState.ACTIVE
    assert calls == 1  # N consecutive reads inside the TTL call the probe once

    clock.advance(10.1)
    assert cache.read() is DaemonState.ACTIVE
    assert calls == 2  # past the TTL, re-probes

    cache.invalidate()
    assert cache.read() is DaemonState.ACTIVE
    assert calls == 3  # invalidate() forces an immediate re-probe


# --- Cache verbs and sharing (D-01e) -----------------------------------------


def test_cache_peek_on_a_never_read_cache_returns_none_and_issues_zero_argv() -> None:
    argv: list[str] = []

    def probe() -> DaemonState:
        argv.append("probed")
        return DaemonState.ACTIVE

    cache = systemd_daemon.TimerStateCache(probe)
    assert cache.peek() is None
    assert argv == []


def test_cache_peek_after_read_returns_the_same_answer_and_issues_zero_argv() -> None:
    calls = 0

    def probe() -> DaemonState:
        nonlocal calls
        calls += 1
        return DaemonState.ACTIVE

    cache = systemd_daemon.TimerStateCache(probe)
    cache.read()
    calls_before_peek = calls
    assert cache.peek() is DaemonState.ACTIVE
    assert calls == calls_before_peek


def test_cache_peek_after_ttl_expiry_still_returns_the_last_answer_while_read_reprobes() -> None:
    clock = _Clock()
    calls = 0

    def probe() -> DaemonState:
        nonlocal calls
        calls += 1
        return DaemonState.ACTIVE

    cache = systemd_daemon.TimerStateCache(probe, ttl=5.0, clock=clock)
    cache.read()
    clock.advance(100.0)
    assert cache.peek() is DaemonState.ACTIVE
    assert calls == 1  # peek never re-probes, even far past the TTL
    assert cache.read() is DaemonState.ACTIVE
    assert calls == 2  # a read() at the same clock value DOES re-probe


def test_cache_peek_after_invalidate_returns_the_last_known_answer_not_none() -> None:
    calls = 0

    def probe() -> DaemonState:
        nonlocal calls
        calls += 1
        return DaemonState.INACTIVE

    cache = systemd_daemon.TimerStateCache(probe)
    cache.read()
    cache.invalidate()
    assert cache.peek() is DaemonState.INACTIVE  # stale value, not None
    cache.read()
    assert calls == 2  # invalidate forced a re-probe at that later read()


def test_linux_daemon_policy_uses_the_injected_cache_by_identity(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    injected = systemd_daemon.TimerStateCache(lambda: DaemonState.INACTIVE)
    policy = _build(paths, run=_RecordingRun(), timer_cache=injected)
    assert policy.state_cache is injected


def test_policy_without_state_cache_argument_still_builds_and_reads_none() -> None:
    policy = Policy(
        id="tweak:example",
        label="Example",
        description="an unrelated policy",
        active=False,
        apply=lambda: PolicyResult((), None, None),
        remove=lambda: PolicyResult((), None, None),
    )
    assert policy.state_cache is None


def test_timer_state_cache_helper_platform_matrix() -> None:
    def which_none(_name: str) -> str | None:
        return None

    def which_systemctl(name: str) -> str | None:
        return "/usr/bin/systemctl" if name == "systemctl" else None

    read_calls: list[list[str]] = []

    def read_output(cmd: list[str]) -> str:
        read_calls.append(cmd)
        return "active"

    macos_cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        Platform(os="macos", arch="arm64", immutable=False, has_brew=True),
        which=which_systemctl,
        read_output=read_output,
    )
    assert macos_cache is None

    no_systemd_cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        _platform(), which=which_none, read_output=read_output
    )
    assert no_systemd_cache is None

    linux_cache = setup._timer_state_cache(  # pyright: ignore[reportPrivateUsage]
        _platform(), which=which_systemctl, read_output=read_output
    )
    assert isinstance(linux_cache, systemd_daemon.TimerStateCache)
    assert read_calls == []  # construction never probes


def test_build_daemon_policy_forwards_the_injected_timer_cache_by_identity() -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in ("systemctl", "uv") else None

    injected = systemd_daemon.TimerStateCache(lambda: DaemonState.INACTIVE)
    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _platform(), {}, which=which, timer_cache=injected
    )
    assert policy is not None
    assert policy.state_cache is injected


def test_build_daemon_policy_without_a_timer_cache_still_builds_a_non_none_one() -> None:
    def which(name: str) -> str | None:
        return f"/usr/bin/{name}" if name in ("systemctl", "uv") else None

    policy = setup._build_daemon_policy(  # pyright: ignore[reportPrivateUsage]
        _platform(), {}, which=which
    )
    assert policy is not None
    assert policy.state_cache is not None


def test_query_systemctl_passes_timeout_and_accept_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run_query(
        cmd: list[str],
        *,
        timeout: float = 0.0,
        env: dict[str, str] | None = None,
        accept_codes: object = (0,),
    ) -> str:
        recorded["cmd"] = cmd
        recorded["timeout"] = timeout
        recorded["accept_codes"] = accept_codes
        del env
        return "active"

    monkeypatch.setattr(systemd_daemon, "run_query", fake_run_query)
    result = systemd_daemon.query_systemctl(["systemctl", "--user", "is-active", "x.timer"])
    assert result == "active"
    assert recorded["timeout"] is not None
    assert set(recorded["accept_codes"]) >= {0, 1, 3, 4}  # type: ignore[arg-type]


# --- Removal (bootout) -------------------------------------------------------


def test_bootout_issues_disable_call_whether_or_not_unit_files_present(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"  # no files created
    fake_run = _RecordingRun()
    systemd_daemon.bootout(unit_dir, run=fake_run, read_output=_ScriptedReadOutput("inactive"))
    assert fake_run.calls == [
        ["systemctl", "--user", "disable", "--now", systemd_daemon.TIMER_NAME]
    ]


def test_bootout_with_units_present_and_disable_failing_reraises(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    with pytest.raises(CommandError):
        systemd_daemon.bootout(unit_dir, run=failing_run, read_output=_ScriptedReadOutput("active"))


def test_bootout_with_units_absent_disable_failing_and_probe_inactive_swallows(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    read_output = _ScriptedReadOutput("inactive")
    systemd_daemon.bootout(unit_dir, run=failing_run, read_output=read_output)  # must not raise
    assert read_output.calls  # the post-failure probe DID run


def test_bootout_with_units_absent_disable_failing_and_probe_unavailable_swallows(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    systemd_daemon.bootout(unit_dir, run=failing_run, read_output=_RaisingReadOutput())


def test_bootout_with_units_absent_disable_failing_and_probe_active_reraises(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    with pytest.raises(CommandError):
        systemd_daemon.bootout(unit_dir, run=failing_run, read_output=_ScriptedReadOutput("active"))


def test_bootout_with_units_present_and_manager_unreachable_reports_not_reached(
    tmp_path: Path,
) -> None:
    # CR-01: `make uninstall` over ssh has no user bus. Raising here left the
    # owned files on disk, so the timer restarted at the next login.
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    assert (
        systemd_daemon.bootout(unit_dir, run=failing_run, read_output=_RaisingReadOutput()) is False
    )


def test_bootout_with_units_present_disable_failing_and_timer_inactive_reports_reached(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)

    def failing_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    assert (
        systemd_daemon.bootout(
            unit_dir, run=failing_run, read_output=_ScriptedReadOutput("inactive")
        )
        is True
    )


def test_bootout_successful_disable_reports_reached(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    assert (
        systemd_daemon.bootout(
            unit_dir, run=_RecordingRun(), read_output=_ScriptedReadOutput("active")
        )
        is True
    )


def test_footprint_present_counts_either_unit_file_or_a_dangling_enable_link(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"
    assert systemd_daemon.footprint_present(unit_dir) is False
    unit_dir.mkdir(parents=True)
    (unit_dir / systemd_daemon.TIMER_NAME).write_text("x")
    assert systemd_daemon.footprint_present(unit_dir) is True
    (unit_dir / systemd_daemon.TIMER_NAME).unlink()
    link = systemd_daemon.wants_link_path(unit_dir)
    link.parent.mkdir(parents=True)
    link.symlink_to(unit_dir / systemd_daemon.TIMER_NAME)  # dangling
    assert systemd_daemon.footprint_present(unit_dir) is True


def test_remove_units_also_removes_the_enable_symlink_but_never_a_regular_file(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)
    link = systemd_daemon.wants_link_path(unit_dir)
    link.parent.mkdir(parents=True)
    link.symlink_to(unit_dir / systemd_daemon.TIMER_NAME)
    systemd_daemon.remove_units(unit_dir)
    assert not link.is_symlink()
    assert systemd_daemon.footprint_present(unit_dir) is False
    link.write_text("not ours")
    systemd_daemon.remove_units(unit_dir)
    assert link.exists()


def test_bootout_successful_disable_issues_no_reprobe(tmp_path: Path) -> None:
    unit_dir = tmp_path / "unit"
    fake_run = _RecordingRun()
    read_output = _ScriptedReadOutput("active")
    systemd_daemon.bootout(unit_dir, run=fake_run, read_output=read_output)
    assert read_output.calls == []


# --- user_unit_dir / systemd_available ---------------------------------------


def test_user_unit_dir_uses_xdg_config_home_when_absolute(tmp_path: Path) -> None:
    xdg = tmp_path / "xdgconf"
    result = systemd_daemon.user_unit_dir(tmp_path, {"XDG_CONFIG_HOME": str(xdg)})
    assert result == xdg / "systemd" / "user"


def test_user_unit_dir_ignores_a_relative_xdg_config_home(tmp_path: Path) -> None:
    result = systemd_daemon.user_unit_dir(tmp_path, {"XDG_CONFIG_HOME": "relative/conf"})
    assert result == tmp_path / ".config" / "systemd" / "user"


def test_user_unit_dir_falls_back_to_home_config_when_xdg_unset(tmp_path: Path) -> None:
    result = systemd_daemon.user_unit_dir(tmp_path, {})
    assert result == tmp_path / ".config" / "systemd" / "user"


def test_systemd_available_true_only_when_systemctl_resolves() -> None:
    assert systemd_daemon.systemd_available(which=lambda _n: "/usr/bin/systemctl") is True
    assert systemd_daemon.systemd_available(which=lambda _n: None) is False


def test_systemd_available_never_spawns_a_process() -> None:
    calls: list[str] = []

    def which(name: str) -> str | None:
        calls.append(name)
        return "/usr/bin/systemctl"

    systemd_daemon.systemd_available(which=which)
    assert calls == ["systemctl"]


# --- decided / record_decided / clear_decided --------------------------------


def test_decided_round_trips_through_record_and_clear(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    assert systemd_daemon.decided(state_path) is False
    systemd_daemon.record_decided(state_path)
    assert systemd_daemon.decided(state_path) is True
    systemd_daemon.clear_decided(state_path)
    assert systemd_daemon.decided(state_path) is False


def test_decided_false_for_an_orphan_begin_marker(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    state_path.write_text("# >>> tools-installer daemon-linux:decided >>>\nstray\n")
    assert systemd_daemon.decided(state_path) is False


def test_decided_false_when_end_marker_precedes_its_begin(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    state_path.write_text(
        "# <<< tools-installer daemon-linux:decided <<<\n"
        "# >>> tools-installer daemon-linux:decided >>>\n"
    )
    assert systemd_daemon.decided(state_path) is False


def test_linux_decided_marker_is_independent_of_macos_daemons_own(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    systemd_daemon.record_decided(state_path)
    assert systemd_daemon.decided(state_path) is True
    assert daemon.decided(state_path) is False


# --- Competing-mechanism detection & takeover (D-02/D-02a/D-02b/D-02c/D-02d) --

_TIMER_NAME = "cleanup-bun-tmp-cache.timer"
_SERVICE_NAME = "cleanup-bun-tmp-cache.service"


def _unit_files_output(*entries: tuple[str, str]) -> str:
    """Build a `systemctl list-unit-files`-shaped listing: name, whitespace,
    state, whitespace, a third (preset) column this module never reads --
    matching the live-captured shape in 15.7-RESEARCH.md Pitfall 1."""
    lines = [f"{name}{' ' * 8}{state}{' ' * 8}-" for name, state in entries]
    lines.append(f"{len(entries)} unit files listed.")
    return "\n".join(lines) + "\n"


class _ScopedReadOutput:
    """Routes list-unit-files/is-active answers by scope (--user present or
    not) and by verb, recording every argv issued."""

    def __init__(
        self,
        *,
        user_listing: str = "",
        system_listing: str = "",
        user_active: Mapping[str, str] | None = None,
        system_active: Mapping[str, str] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._user_listing = user_listing
        self._system_listing = system_listing
        self._user_active = dict(user_active or {})
        self._system_active = dict(system_active or {})

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        is_user = "--user" in cmd
        if "list-unit-files" in cmd:
            return self._user_listing if is_user else self._system_listing
        if "is-active" in cmd:
            unit = cmd[-1]
            table = self._user_active if is_user else self._system_active
            return table.get(unit, "inactive")
        raise AssertionError(f"unexpected argv in _ScopedReadOutput: {cmd}")


class _RaisingScopedReadOutput:
    """Raises CommandError for one named scope ('user' or 'system'), answers
    normally for the other."""

    def __init__(self, *, raise_for: str, other_listing: str = "") -> None:
        self.calls: list[list[str]] = []
        self._raise_for = raise_for
        self._other_listing = other_listing

    def __call__(self, cmd: list[str]) -> str:
        self.calls.append(cmd)
        is_user = "--user" in cmd
        scope = systemd_daemon.SCOPE_USER if is_user else systemd_daemon.SCOPE_SYSTEM
        if scope == self._raise_for:
            raise CommandError(cmd, 1)
        return self._other_listing


# --- parse_unit_files (pure) --------------------------------------------------


def test_parse_unit_files_returns_name_state_pairs_ignoring_the_third_column() -> None:
    output = _unit_files_output((_TIMER_NAME, "enabled"), (_SERVICE_NAME, "static"))
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME, _SERVICE_NAME))
    assert result == ((_TIMER_NAME, "enabled"), (_SERVICE_NAME, "static"))


def test_parse_unit_files_ignores_the_trailing_summary_line() -> None:
    output = _unit_files_output((_TIMER_NAME, "enabled"))
    assert "unit files listed." in output  # sanity: the fixture builds one
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME,))
    assert result == ((_TIMER_NAME, "enabled"),)


def test_parse_unit_files_ignores_a_legend_line() -> None:
    output = f"UNIT FILE STATE PRESET\n{_unit_files_output((_TIMER_NAME, 'enabled'))}"
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME,))
    assert result == ((_TIMER_NAME, "enabled"),)


def test_parse_unit_files_ignores_lines_whose_name_is_not_wanted() -> None:
    output = _unit_files_output(("some-other.timer", "enabled"), (_TIMER_NAME, "static"))
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME,))
    assert result == ((_TIMER_NAME, "static"),)


def test_parse_unit_files_yields_empty_state_for_a_name_only_line() -> None:
    result = systemd_daemon.parse_unit_files(f"{_TIMER_NAME}\n", (_TIMER_NAME,))
    assert result == ((_TIMER_NAME, ""),)


def test_parse_unit_files_on_empty_output_returns_empty_tuple() -> None:
    assert systemd_daemon.parse_unit_files("", (_TIMER_NAME,)) == ()


def test_parse_unit_files_skips_a_blank_line_between_entries() -> None:
    output = f"{_TIMER_NAME}    enabled    -\n\n{_SERVICE_NAME}    static    -\n"
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME, _SERVICE_NAME))
    assert result == ((_TIMER_NAME, "enabled"), (_SERVICE_NAME, "static"))


def test_parse_unit_files_does_not_match_a_substring_of_a_wanted_name() -> None:
    output = _unit_files_output(
        (f"prefix-{_TIMER_NAME}", "enabled"), (f"{_TIMER_NAME}-suffix", "enabled")
    )
    result = systemd_daemon.parse_unit_files(output, (_TIMER_NAME,))
    assert result == ()


# --- Liveness classification (D-02d) -----------------------------------------


def test_detect_competing_enabled_state_is_a_competitor_without_an_is_active_probe() -> None:
    read_output = _ScopedReadOutput(user_listing=_unit_files_output((_TIMER_NAME, "enabled")))
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert [u.name for u in result] == [_TIMER_NAME]
    assert not any("is-active" in c for c in read_output.calls)


def test_detect_competing_enabled_runtime_state_is_a_competitor() -> None:
    read_output = _ScopedReadOutput(
        user_listing=_unit_files_output((_TIMER_NAME, "enabled-runtime"))
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert [u.name for u in result] == [_TIMER_NAME]


def test_detect_competing_disabled_and_inactive_is_not_a_competitor() -> None:
    read_output = _ScopedReadOutput(
        user_listing=_unit_files_output((_TIMER_NAME, "disabled")),
        user_active={_TIMER_NAME: "inactive"},
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert result == ()


def test_detect_competing_disabled_but_active_is_a_competitor() -> None:
    read_output = _ScopedReadOutput(
        user_listing=_unit_files_output((_TIMER_NAME, "disabled")),
        user_active={_TIMER_NAME: "active"},
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert [u.name for u in result] == [_TIMER_NAME]


def test_detect_competing_masked_state_is_not_a_competitor_and_is_not_probed_further() -> None:
    read_output = _ScopedReadOutput(user_listing=_unit_files_output((_TIMER_NAME, "masked")))
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert result == ()
    assert not any("is-active" in c for c in read_output.calls)


def test_detect_competing_is_active_probe_raising_is_treated_as_not_a_competitor() -> None:
    def read_output(cmd: list[str]) -> str:
        if "list-unit-files" in cmd and "--user" in cmd:
            return _unit_files_output((_TIMER_NAME, "disabled"))
        if "is-active" in cmd:
            raise CommandError(cmd, 1)
        return ""

    result = systemd_daemon.detect_competing(read_output=read_output)
    assert result == ()


# --- Detection spans both scopes ---------------------------------------------


def test_detect_competing_reports_user_scope_only() -> None:
    read_output = _ScopedReadOutput(user_listing=_unit_files_output((_TIMER_NAME, "enabled")))
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert len(result) == 1
    assert result[0].name == _TIMER_NAME
    assert result[0].scope == systemd_daemon.SCOPE_USER


def test_detect_competing_reports_system_scope_only() -> None:
    read_output = _ScopedReadOutput(
        system_listing=_unit_files_output((_TIMER_NAME, "enabled"), (_SERVICE_NAME, "static")),
        system_active={_SERVICE_NAME: "active"},
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    names_scopes = {(u.name, u.scope) for u in result}
    assert names_scopes == {
        (_TIMER_NAME, systemd_daemon.SCOPE_SYSTEM),
        (_SERVICE_NAME, systemd_daemon.SCOPE_SYSTEM),
    }


def test_detect_competing_reports_entries_from_both_scopes() -> None:
    read_output = _ScopedReadOutput(
        user_listing=_unit_files_output((_TIMER_NAME, "enabled")),
        system_listing=_unit_files_output((_SERVICE_NAME, "enabled")),
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    names_scopes = {(u.name, u.scope) for u in result}
    assert names_scopes == {
        (_TIMER_NAME, systemd_daemon.SCOPE_USER),
        (_SERVICE_NAME, systemd_daemon.SCOPE_SYSTEM),
    }


def test_detect_competing_one_scope_raising_never_suppresses_the_other() -> None:
    read_output = _RaisingScopedReadOutput(
        raise_for=systemd_daemon.SCOPE_SYSTEM,
        other_listing=_unit_files_output((_TIMER_NAME, "enabled")),
    )
    result = systemd_daemon.detect_competing(read_output=read_output)
    assert [u.name for u in result] == [_TIMER_NAME]
    assert [u.scope for u in result] == [systemd_daemon.SCOPE_USER]


def test_detect_competing_os_error_on_every_scope_returns_empty_tuple() -> None:
    def read_output(cmd: list[str]) -> str:
        raise OSError(f"no systemctl: {cmd}")

    assert systemd_daemon.detect_competing(read_output=read_output) == ()


def test_detect_competing_argv_shape_is_read_only_and_scope_correct() -> None:
    read_output = _ScopedReadOutput(
        user_listing=_unit_files_output((_TIMER_NAME, "disabled")),
        user_active={_TIMER_NAME: "active"},
    )
    systemd_daemon.detect_competing(read_output=read_output)
    for cmd in read_output.calls:
        assert cmd[0] == "systemctl"
        assert cmd[1] in ("--user", "list-unit-files", "is-active")
    user_calls = [c for c in read_output.calls if "--user" in c]
    system_calls = [c for c in read_output.calls if "--user" not in c]
    assert user_calls  # the user-scope probes carry the flag
    assert all("--user" not in c for c in system_calls)


def test_detect_competing_default_read_output_is_query_systemctl() -> None:
    sig = inspect.signature(systemd_daemon.detect_competing)
    assert sig.parameters["read_output"].default is systemd_daemon.query_systemctl


# --- Refusal and wording -------------------------------------------------------


def _user_unit(name: str, state: str = "enabled") -> systemd_daemon.CompetingUnit:
    return systemd_daemon.CompetingUnit(name=name, scope=systemd_daemon.SCOPE_USER, state=state)


def _system_unit(name: str, state: str = "enabled") -> systemd_daemon.CompetingUnit:
    return systemd_daemon.CompetingUnit(name=name, scope=systemd_daemon.SCOPE_SYSTEM, state=state)


def test_disable_competing_raises_valueerror_before_any_argv_for_a_system_scope_entry() -> None:
    fake_run = _RecordingRun()
    with pytest.raises(ValueError):
        systemd_daemon.disable_competing([_system_unit(_TIMER_NAME)], run=fake_run)
    assert fake_run.calls == []


def test_disable_competing_refuses_mixed_scopes_before_any_argv() -> None:
    fake_run = _RecordingRun()
    with pytest.raises(ValueError):
        systemd_daemon.disable_competing(
            [_user_unit(_TIMER_NAME), _system_unit(_SERVICE_NAME)], run=fake_run
        )
    assert fake_run.calls == []


def test_disable_competing_issues_one_disable_now_call_per_user_scope_entry() -> None:
    fake_run = _RecordingRun()
    disabled, failed = systemd_daemon.disable_competing(
        [_user_unit(_TIMER_NAME), _user_unit(_SERVICE_NAME)], run=fake_run
    )
    assert fake_run.calls == [
        ["systemctl", "--user", "disable", "--now", _TIMER_NAME],
        ["systemctl", "--user", "disable", "--now", _SERVICE_NAME],
    ]
    assert disabled == (_TIMER_NAME, _SERVICE_NAME)
    assert failed == ()


def test_disable_competing_collects_a_per_entry_failure_instead_of_aborting() -> None:
    def run(cmd: list[str]) -> None:
        if cmd[-1] == _TIMER_NAME:
            raise CommandError(cmd, 1)

    disabled, failed = systemd_daemon.disable_competing(
        [_user_unit(_TIMER_NAME), _user_unit(_SERVICE_NAME)], run=run
    )
    assert disabled == (_SERVICE_NAME,)
    assert failed == (_TIMER_NAME,)


def test_disable_competing_never_issues_a_unit_removing_verb_and_files_survive(
    tmp_path: Path,
) -> None:
    unit_dir = tmp_path / "unit"
    _write_units_present(unit_dir)
    service_path, timer_path = systemd_daemon.unit_paths(unit_dir)
    fake_run = _RecordingRun()
    systemd_daemon.disable_competing([_user_unit(_TIMER_NAME)], run=fake_run)
    for cmd in fake_run.calls:
        assert not any(verb in cmd for verb in ("mask", "unlink", "rm"))
    assert service_path.exists()
    assert timer_path.exists()


def test_system_scope_warning_none_when_no_system_scope_entries() -> None:
    assert systemd_daemon.system_scope_warning([_user_unit(_TIMER_NAME)]) is None
    assert systemd_daemon.system_scope_warning([]) is None


def test_system_scope_warning_names_the_timer_command_for_a_timer_only_detection() -> None:
    warning = systemd_daemon.system_scope_warning([_system_unit(_TIMER_NAME)])
    assert warning == (
        f"A system-level cleanup service was found ({_TIMER_NAME}) and will keep running "
        "alongside this app's own daemon; this project cannot stop it without root, so it was "
        f"left untouched. Run `sudo systemctl disable --now {_TIMER_NAME}` yourself to stop "
        "and disable it."
    )


def test_system_scope_warning_adds_the_service_stop_command_when_a_service_was_also_found() -> None:
    warning = systemd_daemon.system_scope_warning(
        [_system_unit(_TIMER_NAME), _system_unit(_SERVICE_NAME)]
    )
    assert warning == (
        f"A system-level cleanup service was found ({_SERVICE_NAME}, {_TIMER_NAME}) and will "
        "keep running alongside this app's own daemon; this project cannot stop it without "
        f"root, so it was left untouched. Run `sudo systemctl disable --now {_TIMER_NAME}; "
        f"sudo systemctl stop {_SERVICE_NAME}` yourself to stop and disable it."
    )


def test_system_scope_warning_never_names_a_service_command_with_no_service_detected() -> None:
    warning = systemd_daemon.system_scope_warning([_system_unit(_TIMER_NAME)])
    assert warning is not None
    assert _SERVICE_NAME not in warning


def test_user_scope_failure_warning_none_when_nothing_failed() -> None:
    assert systemd_daemon.user_scope_failure_warning([]) is None


def test_user_scope_failure_warning_names_each_failed_unit_and_its_user_scope_command() -> None:
    warning = systemd_daemon.user_scope_failure_warning([_TIMER_NAME, _SERVICE_NAME])
    assert warning == (
        f"{_TIMER_NAME} could not be stopped and disabled and is still running alongside this "
        f"app's own daemon; run `systemctl --user disable --now {_TIMER_NAME}` yourself to "
        f"stop it. {_SERVICE_NAME} could not be stopped and disabled and is still running "
        f"alongside this app's own daemon; run `systemctl --user disable --now {_SERVICE_NAME}` "
        "yourself to stop it."
    )


def test_systemd_daemon_module_imports_no_subprocess() -> None:
    source = inspect.getsource(systemd_daemon)
    assert "import subprocess" not in source


def test_competing_units_are_the_two_exact_confirmed_unit_names() -> None:
    assert systemd_daemon.COMPETING_UNITS == (_TIMER_NAME, _SERVICE_NAME)


def test_takeover_disclosure_names_each_unit_and_its_re_enable_command() -> None:
    assert systemd_daemon.takeover_disclosure(()) is None
    text = systemd_daemon.takeover_disclosure(["a.timer", "b.service"])
    assert text is not None
    assert "Stopped and disabled a.timer, b.service" in text
    assert "systemctl --user enable --now a.timer; systemctl --user enable --now b.service" in text
    assert "sudo" not in text
    assert "removed" not in text and "deleted" not in text  # D-02b: disabled, never deleted
