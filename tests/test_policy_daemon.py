"""Tests for installer.policy.daemon_policy: the transactional apply/remove/
set_schedule factory composing installer.daemon's mechanism layer.

Every test uses an injected fake `run` -- never real `launchctl` -- mirroring
installer/daemon.py's own injectable-run-seam tests and tests/test_policy_omz.py's
structure. A _FakeRun records every argv and can be told to raise CommandError
for a specific (subcommand, occurrence) pair, so a test can target exactly "the
Nth bootstrap call" or "the bootout call" without depending on call order
guesses beyond what daemon.bootstrap's own documented bootout-then-bootstrap
shape already guarantees.
"""

import plistlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from installer import daemon
from installer.daemon import DaemonScheduleError
from installer.policy import Policy, daemon_policy
from installer.run import CommandError, Runner

_WRAPPER_COMMAND = "tools-installer-prune-daemon"  # mirrors installer.daemon._WRAPPER_COMMAND


class _FakeRun:
    """Records every argv; raises CommandError for a given (subcommand,
    occurrence) pair, where occurrence is the 1-based count of that
    subcommand seen so far by THIS instance."""

    def __init__(self, *, fail_on: frozenset[tuple[str, int]] = frozenset()) -> None:
        self.calls: list[list[str]] = []
        self._fail_on = fail_on
        self._seen: dict[str, int] = {}

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        subcommand = cmd[1]
        self._seen[subcommand] = self._seen.get(subcommand, 0) + 1
        if (subcommand, self._seen[subcommand]) in self._fail_on:
            raise CommandError(cmd, 5)


class _AlreadyAbsentRun:
    """bootout always reports the idempotent "already not loaded" exit 3."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> None:
        self.calls.append(cmd)
        if cmd[1] == "bootout":
            raise CommandError(cmd, 3)


@dataclass
class _Paths:
    plist_path: Path
    log_path: Path
    wrapper_bin_dir: Path
    script_path: Path
    state_path: Path
    uv_path: Path
    tmpdir_value: str
    home_value: str


def _make_paths(tmp_path: Path) -> _Paths:
    script_path = tmp_path / "scripts" / "prune-user-tmpdir.sh"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/bin/sh\n")
    return _Paths(
        plist_path=tmp_path / "LaunchAgents" / "com.tools-installer.prune-tmpdir.plist",
        log_path=tmp_path / "Logs" / "prune-daemon.log",
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
    run: Runner,
    installed_tools: Mapping[str, bool] | None = None,
    tmpdir_value: str | None = None,
    home_value: str | None = None,
) -> Policy:
    resolved_tools = installed_tools if installed_tools is not None else {"fd": True, "rg": True}
    return daemon_policy(
        plist_path=paths.plist_path,
        log_path=paths.log_path,
        wrapper_bin_dir=paths.wrapper_bin_dir,
        script_path=paths.script_path,
        state_path=paths.state_path,
        installed_tools=resolved_tools,
        path_value="/usr/bin:/bin",
        tmpdir_value=tmpdir_value if tmpdir_value is not None else paths.tmpdir_value,
        home_value=home_value if home_value is not None else paths.home_value,
        uv_path=paths.uv_path,
        uid=501,
        run=run,
    )


# --- missing_requires derivation --------------------------------------------


def test_missing_requires_derived_when_both_fd_and_rg_are_absent(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun(), installed_tools={"fd": False, "rg": False})
    assert policy.requires == ("fd", "rg")
    assert policy.missing_requires == ("fd", "rg")
    assert policy.hard_requires is False


def test_missing_requires_empty_when_both_fd_and_rg_are_present(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun(), installed_tools={"fd": True, "rg": True})
    assert policy.missing_requires == ()


# --- policy shape: hard_requires / is_active --------------------------------


def test_policy_shape_hard_requires_and_is_active(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun())
    assert policy.hard_requires is False
    assert policy.requires == ("fd", "rg")
    assert policy.is_active is not None
    assert paths.plist_path.exists() is False
    assert policy.is_active() is False
    policy.apply()
    assert paths.plist_path.exists() is True
    assert policy.is_active() is True


# --- full apply/remove round trip -------------------------------------------


def test_apply_writes_a_valid_plist_and_remove_tears_it_down(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)

    result = policy.apply()
    assert result.warning is None
    assert paths.plist_path.exists()
    data = plistlib.loads(paths.plist_path.read_bytes())
    assert data["StartCalendarInterval"] == {
        "Hour": daemon.DEFAULT_HOUR,
        "Minute": daemon.DEFAULT_MINUTE,
    }
    program_arguments = data["ProgramArguments"]
    assert str(paths.uv_path) in program_arguments
    assert str(paths.script_path) in program_arguments
    assert str(daemon.DEFAULT_DAYS) in program_arguments
    assert data["EnvironmentVariables"]["TMPDIR"] == paths.tmpdir_value
    assert data["EnvironmentVariables"]["HOME"] == paths.home_value
    assert data["EnvironmentVariables"]["PATH"] == "/usr/bin:/bin"
    assert daemon.decided(paths.state_path) is True
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is True

    remove_result = policy.remove()
    assert remove_result.warning is None
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert daemon.decided(paths.state_path) is True  # an explicit disable is still "decided"


def test_reapply_preserves_a_previously_set_schedule(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun())
    policy.apply()
    assert policy.set_schedule is not None
    policy.set_schedule(4, 15)
    policy.apply()
    data = plistlib.loads(paths.plist_path.read_bytes())
    assert data["StartCalendarInterval"] == {"Hour": 4, "Minute": 15}


# --- validation runs before any filesystem side effect ----------------------


def test_apply_validates_before_any_filesystem_side_effect(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun(), tmpdir_value="relative/not/absolute")
    with pytest.raises(DaemonScheduleError):
        policy.apply()
    assert not paths.wrapper_bin_dir.exists()
    assert not paths.log_path.exists()
    assert not paths.plist_path.exists()


# --- set_schedule guards an inactive policy ---------------------------------


def test_set_schedule_on_inactive_policy_raises_and_creates_no_plist(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    policy = _build(paths, run=_FakeRun())
    assert policy.set_schedule is not None
    with pytest.raises(DaemonScheduleError):
        policy.set_schedule(4, 15)
    assert not paths.plist_path.exists()


# --- failure injection: apply-time bootstrap failure, first-ever apply -----


def test_apply_bootstrap_failure_on_first_ever_apply_rolls_back_everything(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun(fail_on=frozenset({("bootstrap", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert not paths.log_path.exists()
    assert daemon.decided(paths.state_path) is False


def test_apply_bootstrap_failure_on_first_ever_apply_preserves_a_pre_existing_wrapper(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    daemon.install_wrapper(paths.wrapper_bin_dir)  # an unrelated, earlier successful apply
    fake_run = _FakeRun(fail_on=frozenset({("bootstrap", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is True
    assert not paths.log_path.exists()


def test_apply_bootstrap_failure_on_first_ever_apply_preserves_a_pre_existing_log(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    daemon.ensure_log_path(paths.log_path)  # an unrelated, earlier successful apply
    fake_run = _FakeRun(fail_on=frozenset({("bootstrap", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert paths.log_path.exists()


def test_apply_bootstrap_failure_on_a_reapply_restores_bytes_and_re_bootstraps(
    tmp_path: Path,
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    original_bytes = paths.plist_path.read_bytes()

    fake_run = _FakeRun(fail_on=frozenset({("bootstrap", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.apply()
    assert paths.plist_path.read_bytes() == original_bytes
    bootstrap_calls = [c for c in fake_run.calls if c[1] == "bootstrap"]
    assert len(bootstrap_calls) == 2  # the failed attempt + the best-effort re-bootstrap
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is True
    assert paths.log_path.exists()


# --- failure injection: state_path-write failure after a successful apply --


def test_apply_marker_write_failure_degrades_to_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    original_replace = daemon.os.replace

    def failing_replace(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == paths.state_path:
            raise OSError("simulated disk full")
        original_replace(src, dst)

    monkeypatch.setattr(daemon.os, "replace", failing_replace)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    result = policy.apply()
    assert result.warning is not None
    assert "decision not recorded" in result.warning
    assert paths.plist_path.exists()
    assert any(cmd[1] == "bootstrap" for cmd in fake_run.calls)
    assert daemon.decided(paths.state_path) is False


# --- failure injection: remove() -------------------------------------------


def test_remove_bootout_real_failure_leaves_plist_and_propagates(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()

    fake_run = _FakeRun(fail_on=frozenset({("bootout", 1)}))
    policy = _build(paths, run=fake_run)
    with pytest.raises(CommandError):
        policy.remove()
    assert paths.plist_path.exists()
    assert daemon.decided(paths.state_path) is True  # unchanged from the earlier apply


def test_remove_bootout_already_absent_completes_normally(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()

    fake_run = _AlreadyAbsentRun()
    policy = _build(paths, run=fake_run)
    result = policy.remove()
    assert result.warning is None
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is False


def test_remove_unlink_failure_re_bootstraps_old_content_before_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    original_bytes = paths.plist_path.read_bytes()

    original_unlink = Path.unlink

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == paths.plist_path:
            raise OSError("simulated unlink failure")
        original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    with pytest.raises(OSError):
        policy.remove()
    assert paths.plist_path.exists()
    assert paths.plist_path.read_bytes() == original_bytes
    bootstrap_calls = [c for c in fake_run.calls if c[1] == "bootstrap"]
    assert len(bootstrap_calls) == 1  # the best-effort re-bootstrap after the failed unlink


def test_remove_wrapper_unlink_failure_degrades_to_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    wrapper_target = paths.wrapper_bin_dir / _WRAPPER_COMMAND

    original_unlink = Path.unlink

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == wrapper_target:
            raise OSError("simulated wrapper removal failure")
        original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    result = policy.remove()
    assert result.warning is not None
    assert "wrapper removal failed" in result.warning
    assert not paths.plist_path.exists()
    assert any(cmd[1] == "bootout" for cmd in fake_run.calls)


def test_remove_marker_write_failure_degrades_to_warning_and_leaves_undecided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    policy.apply()
    # Simulate the case cycle 3 finding #2 warns about: no decision has ever
    # been durably recorded before this removal is the first one attempted.
    paths.state_path.unlink()
    assert daemon.decided(paths.state_path) is False

    original_replace = daemon.os.replace

    def failing_replace(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == paths.state_path:
            raise OSError("simulated disk full")
        original_replace(src, dst)

    monkeypatch.setattr(daemon.os, "replace", failing_replace)
    result = policy.remove()
    assert result.warning is not None
    assert "decision not recorded" in result.warning
    assert not paths.plist_path.exists()
    assert daemon.wrapper_present(paths.wrapper_bin_dir) is False
    assert daemon.decided(paths.state_path) is False


def test_remove_both_wrapper_and_marker_failures_are_both_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()

    wrapper_target = paths.wrapper_bin_dir / _WRAPPER_COMMAND
    original_unlink = Path.unlink

    def failing_unlink(self: Path, *args: object, **kwargs: object) -> None:
        if self == wrapper_target:
            raise OSError("simulated wrapper removal failure")
        original_unlink(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "unlink", failing_unlink)

    original_replace = daemon.os.replace

    def failing_replace(src: str | Path, dst: str | Path) -> None:
        if Path(dst) == paths.state_path:
            raise OSError("simulated disk full")
        original_replace(src, dst)

    monkeypatch.setattr(daemon.os, "replace", failing_replace)

    fake_run = _FakeRun()
    policy = _build(paths, run=fake_run)
    result = policy.remove()
    assert result.warning is not None
    assert "wrapper removal failed" in result.warning
    assert "decision not recorded" in result.warning
    assert not paths.plist_path.exists()


# --- failure injection: set_schedule() --------------------------------------


def test_set_schedule_bootstrap_failure_rolls_back_and_re_bootstraps(tmp_path: Path) -> None:
    paths = _make_paths(tmp_path)
    setup_policy = _build(paths, run=_FakeRun())
    setup_policy.apply()
    original_bytes = paths.plist_path.read_bytes()

    fake_run = _FakeRun(fail_on=frozenset({("bootstrap", 1)}))
    policy = _build(paths, run=fake_run)
    assert policy.set_schedule is not None
    with pytest.raises(CommandError):
        policy.set_schedule(4, 15)
    assert paths.plist_path.read_bytes() == original_bytes
    bootstrap_calls = [c for c in fake_run.calls if c[1] == "bootstrap"]
    assert len(bootstrap_calls) == 2  # the failed attempt + the best-effort re-bootstrap
