"""Tests for installer.systemd_daemon (the Linux mechanism tier, mirroring
installer/daemon.py's macOS launchd shape) and this plan's composition-root
wiring in setup.py (`_build_daemon_policy`'s Linux branch, `_timer_state_cache`).

Every test uses an injected fake `run`/`read_output` -- never real
`systemctl` -- mirroring tests/test_daemon.py's own injectable-run-seam
tests and tests/test_policy_daemon.py's fixture structure.
"""

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
