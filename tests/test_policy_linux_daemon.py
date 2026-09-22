"""Tests for installer.policy.linux_daemon_policy: the transactional apply/
remove factory composing installer.systemd_daemon's mechanism layer.

Every test uses an injected fake `run` -- never real `systemctl` -- mirroring
tests/test_policy_daemon.py's own `_FakeRun` fixture structure, adapted to
systemd's argv shape (`["systemctl", "--user", <verb>, ...]`, verb at
index 2, where launchd's `["launchctl", <verb>, ...]` has it at index 1).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from installer import daemon, systemd_daemon
from installer.enums import DaemonState
from installer.policy import Policy, PolicyLayer, PolicyResult, linux_daemon_policy
from installer.run import CommandError, OutputRunner, Runner

_WRAPPER_COMMAND = "tools-installer-prune-daemon"  # mirrors installer.daemon.WRAPPER_COMMAND


class _FakeRun:
    """Records every argv; raises CommandError for a given (verb, occurrence)
    pair, where occurrence is the 1-based count of that systemctl verb
    (cmd[2]) seen so far by THIS instance."""

    def __init__(self, *, fail_on: frozenset[tuple[str, int]] = frozenset()) -> None:
        self.calls: list[list[str]] = []
        self._fail_on = fail_on
        self._seen: dict[str, int] = {}

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        verb = cmd[2]
        self._seen[verb] = self._seen.get(verb, 0) + 1
        if (verb, self._seen[verb]) in self._fail_on:
            raise CommandError(cmd, 5)


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


def _default_read_output(_cmd: list[str]) -> str:
    return "active"


# --- Competing-mechanism detection fixtures (D-02) ----------------------------

_COMPETING_TIMER = systemd_daemon.COMPETING_UNITS[0]
_COMPETING_SERVICE = systemd_daemon.COMPETING_UNITS[1]


def _competing_listing(*entries: tuple[str, str]) -> str:
    lines = [f"{name}{' ' * 8}{state}{' ' * 8}-" for name, state in entries]
    lines.append(f"{len(entries)} unit files listed.")
    return "\n".join(lines) + "\n"


class _DetectionReadOutput:
    """Answers THIS policy's own timer is-active probe with `own_active`
    (systemd_daemon.TIMER_NAME), and separately routes competing-unit
    list-unit-files/is-active probes by scope -- records every argv issued."""

    def __init__(
        self,
        *,
        own_active: str = "active",
        user_listing: str = "",
        system_listing: str = "",
        user_active: Mapping[str, str] | None = None,
        system_active: Mapping[str, str] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._own_active = own_active
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
            if unit == systemd_daemon.TIMER_NAME:
                return self._own_active
            table = self._user_active if is_user else self._system_active
            return table.get(unit, "inactive")
        raise AssertionError(f"unexpected argv in _DetectionReadOutput: {cmd}")


def _build(
    paths: _Paths,
    *,
    run: Runner,
    read_output: OutputRunner | None = None,
    installed_tools: Mapping[str, bool] | None = None,
    age_minutes: int | None = None,
    timer_cache: systemd_daemon.TimerStateCache | None = None,
) -> Policy:
    kwargs: dict[str, object] = {
        "unit_dir": paths.unit_dir,
        "log_path": paths.log_path,
        "wrapper_bin_dir": paths.wrapper_bin_dir,
        "script_path": paths.script_path,
        "state_path": paths.state_path,
        "installed_tools": installed_tools if installed_tools is not None else {},
        "path_value": "/usr/bin:/bin",
        "tmpdir_value": paths.tmpdir_value,
        "home_value": paths.home_value,
        "uv_path": paths.uv_path,
        "run": run,
        "read_output": read_output if read_output is not None else _default_read_output,
        "timer_cache": timer_cache,
    }
    if age_minutes is not None:
        kwargs["age_minutes"] = age_minutes
    return linux_daemon_policy(**kwargs)  # type: ignore[arg-type]


# --- first-ever apply: enable failure rolls back everything ------------------


def test_linux_factory_binds_its_own_decided_closures(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun())
    assert policy.decided is not None
    assert policy.clear_decided is not None
    systemd_daemon.record_decided(paths.state_path)
    assert policy.decided() is True
    assert daemon.decided(paths.state_path) is False
    policy.clear_decided()
    assert systemd_daemon.decided(paths.state_path) is False


def test_first_ever_apply_enable_failure_leaves_no_artifacts_and_reraises(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("enable", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    assert not service_path.exists()
    assert not timer_path.exists()
    assert systemd_daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert not paths.log_path.exists()


# --- first-ever apply: write half failure -----------------------------------


def test_first_ever_apply_write_half_failure_removes_only_this_calls_own_wrapper(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    # Simulate the write half failing: pre-create unit_dir as a plain FILE so
    # write_units' own `unit_dir.mkdir(parents=True, exist_ok=True)` collides
    # and raises FileExistsError (an OSError), well after install_wrapper has
    # already created a brand-new wrapper.
    paths.unit_dir.parent.mkdir(parents=True, exist_ok=True)
    paths.unit_dir.write_text("not a directory")
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    with pytest.raises(OSError):
        policy.apply()
    assert systemd_daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert not paths.log_path.exists()
    assert not any(c[2] == "enable" for c in fake_run.calls)  # bootstrap never reached


def test_first_ever_apply_write_half_failure_preserves_a_pre_existing_wrapper(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    daemon.install_wrapper(paths.wrapper_bin_dir)  # an unrelated, earlier successful apply
    paths.unit_dir.parent.mkdir(parents=True, exist_ok=True)
    paths.unit_dir.write_text("not a directory")
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    with pytest.raises(OSError):
        policy.apply()
    assert systemd_daemon.wrapper_present(paths.wrapper_bin_dir) is True


# --- re-apply: restart failure restores the previous registration -----------


def test_reapply_restart_failure_restores_previous_bytes_and_rebootstraps(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    original_service_bytes = service_path.read_bytes()
    original_timer_bytes = timer_path.read_bytes()

    fake_run = _FakeRun(fail_on=frozenset({("restart", 1)}))
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "inactive", age_minutes=42)
    with pytest.raises(CommandError):
        policy.apply()
    assert service_path.read_bytes() == original_service_bytes  # NOT the age_minutes=42 attempt
    assert timer_path.read_bytes() == original_timer_bytes
    restart_calls = [c for c in fake_run.calls if c[2] == "restart"]
    assert len(restart_calls) == 2  # the failed attempt + the best-effort re-bootstrap's restart
    assert policy.is_active is not None
    assert policy.is_active() is False  # not left as a false positive


# --- remove: disable failure ---------------------------------------------


def test_remove_disable_failure_leaves_unit_files_in_place_and_reraises(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)

    fake_run = _FakeRun(fail_on=frozenset({("disable", 1)}))
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "active")
    with pytest.raises(CommandError):
        policy.remove()
    assert service_path.exists()
    assert timer_path.exists()


def test_remove_unit_file_unlink_failure_rebootstraps_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    original_service_bytes = service_path.read_bytes()

    original_unlink = Path.unlink

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == service_path:
            raise OSError("simulated unlink failure")
        original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "active")
    with pytest.raises(OSError):
        policy.remove()
    assert service_path.exists()
    assert service_path.read_bytes() == original_service_bytes
    assert timer_path.exists()  # the loop never reached the timer unlink
    restart_calls = [c for c in fake_run.calls if c[2] == "restart"]
    assert len(restart_calls) == 1  # the best-effort re-bootstrap after the failed unlink


# --- rollback reload (review MEDIUM 15.7-01) --------------------------------


def test_first_ever_apply_rollback_reload_happens_after_the_unit_file_deletion(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("enable", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    verbs = [c[2] for c in fake_run.calls]
    # daemon-reload (pre-enable), enable (fails), disable (WR-01: undo any
    # wants symlink enable created), daemon-reload (compensating, AFTER the
    # unit files are gone) -- the pre-enable reload cannot satisfy this.
    assert verbs == ["daemon-reload", "enable", "disable", "daemon-reload"]


class _EnablingRun(_FakeRun):
    """A _FakeRun whose `enable` creates the wants symlink and `disable`
    removes it, like the real user manager."""

    def __init__(self, unit_dir: Path, **kwargs: frozenset[tuple[str, int]]) -> None:
        super().__init__(**kwargs)
        self._link = systemd_daemon.wants_link_path(unit_dir)

    def __call__(self, cmd: list[str]) -> None:
        if cmd[2] == "enable":
            self._link.parent.mkdir(parents=True, exist_ok=True)
            if not self._link.is_symlink():
                self._link.symlink_to(self._link.parent.parent / systemd_daemon.TIMER_NAME)
        super().__call__(cmd)
        if cmd[2] == "disable" and self._link.is_symlink():
            self._link.unlink()


def test_first_ever_apply_restart_failure_disables_before_deleting_the_units(
    tmp_path: Path,
) -> None:
    """WR-01: a restart failure after a successful enable used to leave the
    timers.target.wants symlink dangling at a deleted unit forever."""
    paths = _make_paths(tmp_path)
    fake_run = _EnablingRun(paths.unit_dir, fail_on=frozenset({("restart", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    assert ["systemctl", "--user", "disable", systemd_daemon.TIMER_NAME] in fake_run.calls
    assert not systemd_daemon.wants_link_path(paths.unit_dir).is_symlink()
    assert systemd_daemon.footprint_present(paths.unit_dir) is False


def test_first_ever_apply_over_a_half_removed_install_keeps_the_pre_existing_unit_file(
    tmp_path: Path,
) -> None:
    """IN-05: only one unit file predates the apply, so it is not a prior
    registration, and the rollback used to delete that file too."""
    paths = _make_paths(tmp_path)
    paths.unit_dir.mkdir(parents=True)
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    service_path.write_bytes(b"hand-edited service\n")
    policy = _build(paths, run=_FakeRun(fail_on=frozenset({("enable", 1)})))
    with pytest.raises(CommandError):
        policy.apply()
    assert service_path.read_bytes() == b"hand-edited service\n"
    assert not timer_path.exists()


def test_remove_timer_unlink_failure_restores_the_deleted_service_before_rebootstrapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """WR-01: remove_units deletes the service first; re-bootstrapping after
    the timer unlink fails used to re-enable a timer with no service."""
    paths = _make_paths(tmp_path)
    _build(paths, run=_FakeRun()).apply()
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    original_service_bytes = service_path.read_bytes()
    original_unlink = Path.unlink

    def failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == timer_path:
            raise OSError("simulated unlink failure")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "active")
    with pytest.raises(OSError):
        policy.remove()
    assert service_path.read_bytes() == original_service_bytes
    assert timer_path.exists()
    assert [c[2] for c in fake_run.calls].count("restart") == 1


def test_reapply_rollback_reload_precedes_the_best_effort_rebootstrap(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()

    fake_run = _FakeRun(fail_on=frozenset({("restart", 1)}))
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "inactive")
    with pytest.raises(CommandError):
        policy.apply()
    verbs = [c[2] for c in fake_run.calls]
    assert verbs == [
        "daemon-reload",
        "enable",
        "restart",  # fails
        "daemon-reload",  # the compensating reload, BEFORE the re-bootstrap below
        "daemon-reload",  # bootstrap's own internal pre-enable reload
        "enable",
        "restart",  # the best-effort re-bootstrap, now succeeding
    ]


def test_remove_unit_file_deletion_records_a_daemon_reload_after_the_unlink(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()

    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run, read_output=lambda _cmd: "active")
    policy.remove()
    verbs = [c[2] for c in fake_run.calls]
    assert verbs == ["disable", "daemon-reload"]


def test_compensating_reload_failure_never_masks_the_original_apply_failure(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("enable", 1), ("daemon-reload", 2)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError) as excinfo:
        policy.apply()
    assert excinfo.value.cmd[2] == "enable"


# --- cache invalidation ------------------------------------------------------


def test_apply_and_remove_invalidate_the_cache_on_success_and_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    cache = systemd_daemon.TimerStateCache(lambda: DaemonState.INACTIVE)
    invalidate_calls = 0
    original_invalidate = cache.invalidate

    def tracking_invalidate() -> None:
        nonlocal invalidate_calls
        invalidate_calls += 1
        original_invalidate()

    monkeypatch.setattr(cache, "invalidate", tracking_invalidate)

    policy = _build(paths, run=_FakeRun(), timer_cache=cache)
    policy.apply()
    assert invalidate_calls == 1

    fail_run = _FakeRun(fail_on=frozenset({("disable", 1)}))
    policy2 = _build(paths, run=fail_run, read_output=lambda _cmd: "active", timer_cache=cache)
    with pytest.raises(CommandError):
        policy2.remove()
    assert invalidate_calls == 2


def test_after_apply_peek_between_invalidate_and_next_read_returns_pre_toggle_value(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    answer = "active"

    def read_output(_cmd: list[str]) -> str:
        return answer

    fake_run = _FakeRun()
    # ONE policy, using its OWN cache (timer_cache=None, the real-defaulted
    # seam) wired to this unit_dir/read_output -- mirrors production, where
    # the same Policy/cache persists across repeated calls rather than each
    # call building an independent, differently-wired cache.
    policy = _build(paths, run=fake_run, read_output=read_output)
    policy.apply()  # creates the units; the construction-time read() warmed
    assert policy.is_active is not None
    assert policy.is_active() is True  # PRE-toggle answer, "active"

    cache = policy.state_cache
    assert cache is not None
    assert cache.peek() is DaemonState.ACTIVE

    # Simulate the user toggling the row: read_output now answers
    # "inactive", and a re-apply's own trailing invalidate() marks the
    # cache stale without discarding it.
    answer = "inactive"
    policy.apply()
    # invalidate() marked it STALE, never cleared: peek() still answers the
    # pre-toggle value instead of falling back to None (D-01e).
    assert cache.peek() is DaemonState.ACTIVE
    assert policy.is_active() is False  # the next read() DID re-probe


# --- marker write: warning / retry -------------------------------------------


def test_apply_marker_write_failure_degrades_to_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    original_replace = os.replace

    def failing_replace(src: object, dst: object) -> None:
        if Path(str(dst)) == paths.state_path:
            raise OSError("simulated disk full")
        original_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", failing_replace)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    result = policy.apply()
    assert result.warning is not None
    assert "decision not recorded" in result.warning
    service_path, _timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    assert service_path.exists()
    assert any(c[2] == "enable" for c in fake_run.calls)
    assert systemd_daemon.decided(paths.state_path) is False


def test_apply_marker_write_transient_failure_recovers_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    original_replace = os.replace
    attempts = 0

    def flaky_replace(src: object, dst: object) -> None:
        nonlocal attempts
        if Path(str(dst)) == paths.state_path:
            attempts += 1
            if attempts == 1:
                raise OSError("simulated transient lock")
        original_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky_replace)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    result = policy.apply()
    assert result.warning is None
    assert systemd_daemon.decided(paths.state_path) is True
    assert attempts == 2


def test_remove_marker_write_transient_failure_recovers_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    policy.apply()

    original_replace = os.replace
    attempts = 0

    def flaky_replace(src: object, dst: object) -> None:
        nonlocal attempts
        if Path(str(dst)) == paths.state_path:
            attempts += 1
            if attempts == 1:
                raise OSError("simulated transient lock")
        original_replace(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky_replace)
    result = policy.remove()
    assert result.warning is None
    assert systemd_daemon.decided(paths.state_path) is True
    assert attempts == 2


def test_after_apply_linux_decided_true_and_macos_decided_false_on_same_file(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun())
    policy.apply()
    assert systemd_daemon.decided(paths.state_path) is True
    assert daemon.decided(paths.state_path) is False


# --- Competing-mechanism takeover wired into apply (D-02) ---------------------


def test_apply_with_user_scope_competitor_registers_first_then_disables_it(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    read_output = _DetectionReadOutput(
        user_listing=_competing_listing((_COMPETING_TIMER, "enabled")),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    result = policy.apply()
    verbs = [c[2] for c in fake_run.calls]
    assert verbs == ["daemon-reload", "enable", "restart", "disable"]
    assert fake_run.calls[-1] == ["systemctl", "--user", "disable", "--now", _COMPETING_TIMER]
    # CR-02: a successful takeover is disclosed, never a silent success.
    assert result.warning is not None
    assert f"Stopped and disabled {_COMPETING_TIMER}" in result.warning
    assert f"systemctl --user enable --now {_COMPETING_TIMER}" in result.warning
    assert "sudo" not in result.warning
    assert result.layers == (
        PolicyLayer(
            "Schedule", f"runs every {systemd_daemon.DEFAULT_INTERVAL} via a systemd user timer"
        ),
        PolicyLayer("Competing mechanism", f"disabled: {_COMPETING_TIMER}"),
    )


def test_on_by_default_takeover_reaches_the_warning_sink_with_the_re_enable_command(
    tmp_path: Path,
) -> None:
    """CR-02: ensure_daemon_default forwards only result.warning, so a takeover
    reported only as a layer was disabled with nothing said to anyone."""
    from installer.policy import ensure_daemon_default

    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    read_output = _DetectionReadOutput(
        user_listing=_competing_listing((_COMPETING_TIMER, "enabled")),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    sink: list[str] = []
    assert ensure_daemon_default(policy, on_warning=sink.append) is True
    assert ["systemctl", "--user", "disable", "--now", _COMPETING_TIMER] in fake_run.calls
    assert len(sink) == 1
    assert _COMPETING_TIMER in sink[0]
    assert f"systemctl --user enable --now {_COMPETING_TIMER}" in sink[0]


def test_apply_with_system_scope_competitor_issues_no_disable_call_and_warns(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    read_output = _DetectionReadOutput(
        system_listing=_competing_listing((_COMPETING_TIMER, "enabled")),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    result = policy.apply()
    assert not any(_COMPETING_TIMER in cmd for cmd in fake_run.calls)
    verbs = [c[2] for c in fake_run.calls]
    assert verbs == ["daemon-reload", "enable", "restart"]  # no disable call at all
    assert result.warning is not None
    assert _COMPETING_TIMER in result.warning
    assert f"sudo systemctl disable --now {_COMPETING_TIMER}" in result.warning
    assert result.layers[-1] == PolicyLayer(
        "Competing mechanism", f"system-scope, left running: {_COMPETING_TIMER}"
    )


def test_apply_with_both_scope_competitors_disables_only_the_user_scope_one(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    read_output = _DetectionReadOutput(
        user_listing=_competing_listing((_COMPETING_TIMER, "enabled")),
        system_listing=_competing_listing((_COMPETING_SERVICE, "enabled")),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    result = policy.apply()
    disable_calls = [c for c in fake_run.calls if c[2] == "disable"]
    assert disable_calls == [["systemctl", "--user", "disable", "--now", _COMPETING_TIMER]]
    assert result.warning is not None
    assert _COMPETING_SERVICE in result.warning
    assert f"sudo systemctl disable --now {_COMPETING_SERVICE}" not in result.warning  # not a timer
    assert f"sudo systemctl stop {_COMPETING_SERVICE}" in result.warning


def test_apply_failed_user_scope_disable_keeps_registration_and_discloses_the_survivor(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("disable", 1)}))
    read_output = _DetectionReadOutput(
        user_listing=_competing_listing((_COMPETING_TIMER, "enabled")),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    result = policy.apply()  # must NOT raise -- D-02c: proceed and disclose
    # Half 1: this project's own registration is unaffected by the foreign
    # unit's failed disable.
    service_path, timer_path = systemd_daemon.unit_paths(paths.unit_dir)
    assert service_path.exists()
    assert timer_path.exists()
    assert policy.is_active is not None
    assert policy.is_active() is True
    # Half 2 + 3: the survivor is named, with the user-scope command.
    assert result.warning is not None
    assert _COMPETING_TIMER in result.warning
    assert "still running" in result.warning
    assert f"systemctl --user disable --now {_COMPETING_TIMER}" in result.warning
    assert "sudo" not in result.warning  # a user-scope competitor never gets a sudo command


def test_apply_two_user_scope_competitors_partial_failure_is_never_reported_as_complete(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("disable", 2)}))
    read_output = _DetectionReadOutput(
        user_listing=_competing_listing(
            (_COMPETING_TIMER, "enabled"), (_COMPETING_SERVICE, "enabled")
        ),
    )
    policy = _build(paths, run=fake_run, read_output=read_output)
    result = policy.apply()
    disable_calls = [c for c in fake_run.calls if c[2] == "disable"]
    assert len(disable_calls) == 2  # both attempted, never aborted after the first
    assert result.warning is not None
    assert _COMPETING_SERVICE in result.warning  # the one that failed, named
    assert f"systemctl --user disable --now {_COMPETING_SERVICE}" in result.warning
    assert result.layers[-1] == PolicyLayer(
        "Competing mechanism",
        f"disabled: {_COMPETING_TIMER}; disable failed, still running: {_COMPETING_SERVICE}",
    )


def test_apply_detection_probe_raising_behaves_identically_to_no_competitor(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()

    def raising_read_output(cmd: list[str]) -> str:
        if "list-unit-files" in cmd:
            raise CommandError(cmd, 1)
        return "active"

    policy = _build(paths, run=fake_run, read_output=raising_read_output)
    result = policy.apply()
    assert not any(c[2] == "disable" for c in fake_run.calls)
    assert result.warning is None
    assert result.layers == (
        PolicyLayer(
            "Schedule", f"runs every {systemd_daemon.DEFAULT_INTERVAL} via a systemd user timer"
        ),
    )


def test_apply_with_no_competitor_matches_the_pre_plan_result_exactly(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)  # default read_output answers "active" to everything
    result = policy.apply()
    assert result == PolicyResult(
        layers=(
            PolicyLayer(
                "Schedule", f"runs every {systemd_daemon.DEFAULT_INTERVAL} via a systemd user timer"
            ),
        ),
        reload_hint=None,
        warning=None,
    )
