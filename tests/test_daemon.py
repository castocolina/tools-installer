import os
import plistlib
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

from installer import daemon, schedules
from installer.run import CommandError

# --- read_schedule: total over malformed input ------------------------------


def test_read_schedule_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert daemon.read_schedule(tmp_path / "missing.plist") is None


def test_read_schedule_returns_none_for_genuinely_invalid_plist_bytes(tmp_path: Path) -> None:
    plist_path = tmp_path / "bad.plist"
    plist_path.write_bytes(b"this is not plist xml at all \xff\xfe")
    assert daemon.read_schedule(plist_path) is None


def test_read_schedule_returns_none_when_start_calendar_interval_missing(tmp_path: Path) -> None:
    plist_path = tmp_path / "no_interval.plist"
    plist_path.write_bytes(plistlib.dumps({"Label": "x"}))
    assert daemon.read_schedule(plist_path) is None


def test_read_schedule_returns_none_when_start_calendar_interval_malformed(tmp_path: Path) -> None:
    plist_path = tmp_path / "malformed_interval.plist"
    plist_path.write_bytes(plistlib.dumps({"Label": "x", "StartCalendarInterval": "not-a-dict"}))
    assert daemon.read_schedule(plist_path) is None


def test_read_schedule_returns_none_when_hour_or_minute_is_not_an_integer(tmp_path: Path) -> None:
    plist_path = tmp_path / "non_int_interval.plist"
    plist_path.write_bytes(
        plistlib.dumps({"Label": "x", "StartCalendarInterval": {"Hour": "3", "Minute": 30}})
    )
    assert daemon.read_schedule(plist_path) is None


# --- generic agent plist and calendar reader (24.2-04) -----------------------

_AGENT_ARGV = ["/abs/uv", "run", "--no-project", "--script", "/abs/runner.py", "update", "claude"]
_AGENT_ENV = {"PATH": "/a", "HOME": "/h", "TMPDIR": "/t"}


def _agent_kwargs(**overrides: object) -> dict[str, object]:
    merged: dict[str, object] = {
        "label": "com.tools-installer.schedule.update-claude",
        "program_arguments": _AGENT_ARGV,
        "environment": _AGENT_ENV,
        "calendar": schedules.calendar_dicts(schedules.slots(8, "01:30")),
        "stdout_path": Path("/abs/schedules-launchd.log"),
        "stderr_path": Path("/abs/schedules-launchd.log"),
    }
    merged.update(overrides)
    return merged


def test_agent_plist_with_a_calendar_array() -> None:
    plist_dict = daemon.render_agent_plist(**_agent_kwargs())  # type: ignore[arg-type]
    assert plist_dict == {
        "Label": "com.tools-installer.schedule.update-claude",
        "ProgramArguments": _AGENT_ARGV,
        "StartCalendarInterval": [
            {"Hour": 1, "Minute": 30},
            {"Hour": 9, "Minute": 30},
            {"Hour": 17, "Minute": 30},
        ],
        "StandardOutPath": "/abs/schedules-launchd.log",
        "StandardErrorPath": "/abs/schedules-launchd.log",
        "RunAtLoad": False,
        "EnvironmentVariables": _AGENT_ENV,
    }
    assert plistlib.loads(plistlib.dumps(plist_dict)) == plist_dict


def test_read_calendar_reads_both_forms(tmp_path: Path) -> None:
    single = tmp_path / "single.plist"
    single.write_bytes(plistlib.dumps({"StartCalendarInterval": {"Hour": 3, "Minute": 0}}))
    assert daemon.read_calendar(single) == ((3, 0),)
    assert daemon.read_schedule(single) == (3, 0)

    many = tmp_path / "many.plist"
    many.write_bytes(
        plistlib.dumps(
            {"StartCalendarInterval": [{"Hour": 17, "Minute": 30}, {"Hour": 1, "Minute": 30}]}
        )
    )
    assert daemon.read_calendar(many) == ((1, 30), (17, 30))
    assert daemon.read_schedule(many) is None

    assert daemon.read_calendar(tmp_path / "missing.plist") is None
    bad = tmp_path / "bad.plist"
    bad.write_bytes(b"not a plist \xff\xfe")
    assert daemon.read_calendar(bad) is None


@pytest.mark.parametrize(
    "interval",
    [
        {"Hour": "3", "Minute": 0},
        {"Hour": 24, "Minute": 0},
        {"Hour": 3, "Minute": 60},
        {"Hour": 3},
        [],
        ["x"],
        [{"Hour": 3, "Minute": 0}, {"Hour": 3.5, "Minute": 0}],
        "daily",
    ],
)
def test_read_calendar_is_none_for_a_malformed_interval(tmp_path: Path, interval: object) -> None:
    plist_path = tmp_path / "bad.plist"
    plist_path.write_bytes(plistlib.dumps({"StartCalendarInterval": interval}))
    assert daemon.read_calendar(plist_path) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"program_arguments": ["relative/uv", "run"]},
        {"program_arguments": []},
        {"calendar": {"Hour": 24, "Minute": 0}},
        {"calendar": {"Hour": 3, "Minute": 60}},
        {"calendar": {"Hour": -1, "Minute": 0}},
        {"calendar": []},
        {"calendar": [{"Hour": 3, "Minute": 0}, {"Hour": 3, "Minute": 61}]},
        {"environment": {**_AGENT_ENV, "LD_PRELOAD": "/x.so"}},
        {"environment": {**_AGENT_ENV, "TMPDIR": ""}},
        {"environment": {**_AGENT_ENV, "TMPDIR": "relative/tmp"}},
        {"environment": {**_AGENT_ENV, "HOME": ""}},
        {"environment": {**_AGENT_ENV, "HOME": "relative/home"}},
        {"environment": {**_AGENT_ENV, "PATH": ""}},
        {"stdout_path": Path("relative.log")},
        {"stderr_path": Path("relative.log")},
        {"program_arguments": ["", "run"]},
    ],
)
def test_agent_plist_rejects_bad_input(overrides: dict[str, object]) -> None:
    with pytest.raises(daemon.DaemonScheduleError):
        daemon.render_agent_plist(**_agent_kwargs(**overrides))  # type: ignore[arg-type]


def test_write_agent_plist_writes_a_rendered_dict_at_0o600(tmp_path: Path) -> None:
    plist_dict = daemon.render_agent_plist(**_agent_kwargs())  # type: ignore[arg-type]
    plist_path = tmp_path / "LaunchAgents" / "agent.plist"
    daemon.write_agent_plist(plist_path, plist_dict)
    assert plistlib.loads(plist_path.read_bytes()) == plist_dict
    assert oct(plist_path.stat().st_mode)[-3:] == "600"  # proxy credentials: owner only


def test_a_plist_carrying_proxy_credentials_is_not_group_or_world_readable(
    tmp_path: Path,
) -> None:
    kwargs: Any = _agent_kwargs(environment={"PATH": "/usr/bin", "HTTPS_PROXY": "http://u:p@host"})
    plist_path = tmp_path / "agent.plist"
    daemon.write_agent_plist(plist_path, daemon.render_agent_plist(**kwargs))
    assert b"http://u:p@host" in plist_path.read_bytes()
    assert plist_path.stat().st_mode & 0o077 == 0


def _rendered() -> dict[str, object]:
    kwargs: Any = _agent_kwargs()  # a mixed-type dict, splatted into typed keywords
    return daemon.render_agent_plist(**kwargs)


def test_write_agent_plist_creates_parent_dirs_and_the_calendar_reads_back(
    tmp_path: Path,
) -> None:
    plist_path = tmp_path / "nested" / "LaunchAgents" / "agent.plist"
    daemon.write_agent_plist(plist_path, _rendered())
    assert daemon.read_calendar(plist_path) == ((1, 30), (9, 30), (17, 30))


def test_write_agent_plist_forces_0o600_regardless_of_prior_mode(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    plist_path.write_bytes(b"placeholder")
    plist_path.chmod(0o644)
    daemon.write_agent_plist(plist_path, _rendered())
    assert plist_path.stat().st_mode & 0o777 == 0o600


def test_write_agent_plist_leaves_no_temp_sibling_file(tmp_path: Path) -> None:
    plist_path = tmp_path / "agent.plist"
    daemon.write_agent_plist(plist_path, _rendered())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["agent.plist"]


# --- _atomic_write: crash-mid-write safety ----------------------------------


def test_atomic_write_leaves_the_original_intact_on_a_failed_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "daemon.plist"
    target.write_bytes(b"original")

    def failing_replace(_src: object, _dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(daemon.os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        daemon._atomic_write(  # pyright: ignore[reportPrivateUsage]
            target, b"new", mode=0o644
        )
    assert target.read_bytes() == b"original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["daemon.plist"]


# --- bootstrap: bootout-then-bootstrap idempotent sequence ------------------


def test_bootstrap_calls_bootout_then_bootstrap_swallowing_bootout_failure(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> None:
        calls.append(cmd)
        if cmd[1] == "bootout":
            raise CommandError(cmd, 5)

    plist_path = tmp_path / "d.plist"
    plist_path.write_bytes(b"stub")
    daemon.bootstrap(501, plist_path, run=fake_run)
    assert calls == [
        ["launchctl", "bootout", f"gui/501/{daemon.LABEL}"],
        ["launchctl", "bootstrap", "gui/501", str(plist_path)],
    ]


def test_bootstrap_propagates_a_real_bootstrap_failure(tmp_path: Path) -> None:
    def fake_run(cmd: list[str]) -> None:
        if cmd[1] == "bootstrap":
            raise CommandError(cmd, 1)

    plist_path = tmp_path / "d.plist"
    with pytest.raises(CommandError):
        daemon.bootstrap(501, plist_path, run=fake_run)


# --- bootout: exit-code-3 ("already unloaded") vs. a real failure ----------


def test_bootout_swallows_the_already_unloaded_exit_code() -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> None:
        calls.append(cmd)
        # 3 is daemon._ALREADY_UNLOADED_EXIT_CODE (Darwin's ESRCH, "No such
        # process") -- live-verified this session against a real nonexistent
        # label. Hardcoded rather than importing the private constant.
        raise CommandError(cmd, 3)

    daemon.bootout(501, label="com.tools-installer.test", run=fake_run)
    assert calls == [["launchctl", "bootout", "gui/501/com.tools-installer.test"]]


def test_bootout_reraises_a_non_already_unloaded_failure() -> None:
    def fake_run(cmd: list[str]) -> None:
        raise CommandError(cmd, 1)

    with pytest.raises(CommandError):
        daemon.bootout(501, label="com.tools-installer.test", run=fake_run)


# --- ensure_log_path ---------------------------------------------------------


def test_ensure_log_path_creates_missing_parents_and_an_empty_file(tmp_path: Path) -> None:
    log_path = tmp_path / "nested" / "prune-daemon.log"
    daemon.ensure_log_path(log_path)
    assert log_path.exists()
    assert log_path.read_bytes() == b""


def test_ensure_log_path_is_a_noop_against_an_already_populated_log(tmp_path: Path) -> None:
    log_path = tmp_path / "prune-daemon.log"
    log_path.write_text("existing content\n")
    daemon.ensure_log_path(log_path)
    assert log_path.read_text() == "existing content\n"


# --- the one real, opt-in, self-tearing-down launchctl round trip ----------


@pytest.mark.skipif(
    shutil.which("launchctl") is None
    or os.environ.get("TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS") != "1",
    reason="requires launchctl (macOS) and explicit opt-in via "
    "TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS=1",
)
def test_bootstrap_bootout_real_launchctl_round_trip(tmp_path: Path) -> None:
    uid = os.getuid()
    test_label = f"com.tools-installer.test-{uuid.uuid4().hex[:8]}"
    plist_path = tmp_path / "test.plist"
    # Built by hand, never via render_agent_plist: this test's only job is
    # exercising bootstrap/bootout's own launchctl subcommands, not the argv shape.
    plist_dict = {
        "Label": test_label,
        "ProgramArguments": ["/bin/echo", "hello"],
        "RunAtLoad": False,
    }
    # Deliberate private-member access: this is the SAME crash-safe persistence
    # path write_agent_plist calls internally, so this test still exercises the
    # module's real atomic-write mechanics without any content shaping.
    daemon._atomic_write(  # pyright: ignore[reportPrivateUsage]
        plist_path, plistlib.dumps(plist_dict), mode=0o644
    )
    try:
        daemon.bootstrap(uid, plist_path, label=test_label)
        printed = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{test_label}"],
            capture_output=True,
            check=False,
        )
        assert printed.returncode == 0
    finally:
        daemon.bootout(uid, label=test_label)
        printed_after = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/{test_label}"],
            capture_output=True,
            check=False,
        )
        assert printed_after.returncode != 0
        plist_path.unlink(missing_ok=True)


# --- remove_wrapper / wrapper_present ----------------------------------------


def _legacy_wrapper(bin_dir: Path) -> Path:
    """The wrapper command as the previous installer wrote it (sentinel included)."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / daemon.WRAPPER_COMMAND
    target.write_text(f"#!/bin/sh\n# {vars(daemon)['_WRAPPER_SENTINEL']}\nexit 0\n")
    target.chmod(0o755)
    return target


def test_wrapper_present_true_only_with_our_sentinel(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    assert daemon.wrapper_present(bin_dir) is False
    _legacy_wrapper(bin_dir)
    assert daemon.wrapper_present(bin_dir) is True


def test_remove_wrapper_deletes_only_the_managed_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _legacy_wrapper(bin_dir)
    daemon.remove_wrapper(bin_dir)
    assert daemon.wrapper_present(bin_dir) is False
    assert not (bin_dir / "tools-installer-prune-daemon").exists()


def test_remove_wrapper_is_a_noop_against_a_missing_bin_dir(tmp_path: Path) -> None:
    daemon.remove_wrapper(tmp_path / "does-not-exist")  # must not raise


def test_wrapper_present_is_false_when_the_target_is_unreadable_as_text(tmp_path: Path) -> None:
    # A directory can't be read as text -> IsADirectoryError (an OSError),
    # mirroring installer/tweaks.py's own _is_our_executable unreadable-target
    # coverage (tests/test_tweaks.py::test_is_our_executable_returns_false_when_unreadable).
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tools-installer-prune-daemon").mkdir()
    assert daemon.wrapper_present(bin_dir) is False


def test_remove_wrapper_refuses_to_delete_an_unmanaged_same_named_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    unmanaged = bin_dir / "tools-installer-prune-daemon"
    unmanaged.write_text("#!/bin/sh\necho not ours\n")
    daemon.remove_wrapper(bin_dir)
    assert unmanaged.exists()


# =============================================================================
# The "decided" ownership marker.
# =============================================================================


def test_decided_is_false_before_any_record(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    assert daemon.decided(state_path) is False


def test_decided_is_false_when_state_path_does_not_exist(tmp_path: Path) -> None:
    assert daemon.decided(tmp_path / "missing") is False


def test_decided_is_true_after_record_decided(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.record_decided(state_path)
    assert daemon.decided(state_path) is True


def test_record_decided_is_idempotent_on_a_second_call(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.record_decided(state_path)
    daemon.record_decided(state_path)
    content = state_path.read_text()
    assert content.count("# >>> tools-installer daemon:decided >>>") == 1


def test_record_decided_preserves_surrounding_content(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    state_path.write_text("export EDITOR=vim\n")
    daemon.record_decided(state_path)
    content = state_path.read_text()
    assert "export EDITOR=vim" in content
    assert "# >>> tools-installer daemon:decided >>>" in content


def test_decided_reads_false_again_after_clear_decided(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.record_decided(state_path)
    daemon.clear_decided(state_path)
    assert daemon.decided(state_path) is False


def test_clear_decided_is_a_noop_when_never_decided(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.clear_decided(state_path)  # missing file: must not raise
    assert not state_path.exists()
    state_path.write_text("export EDITOR=vim\n")
    daemon.clear_decided(state_path)  # existing file, no marker: unchanged
    assert state_path.read_text() == "export EDITOR=vim\n"


def test_an_orphaned_begin_marker_reads_as_no_record(tmp_path: Path) -> None:
    # Mirrors installer/omz.py's own orphan-marker test shape (11-REVIEWS.md
    # cycle 2 finding #4): an unclosed begin marker must never wedge the
    # policy permanently "decided".
    state_path = tmp_path / ".myshellrc"
    state_path.write_text("# >>> tools-installer daemon:decided >>>\n")
    assert daemon.decided(state_path) is False


def test_a_reversed_marker_pair_reads_as_no_record(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    state_path.write_text(
        "# <<< tools-installer daemon:decided <<<\n# >>> tools-installer daemon:decided >>>\n"
    )
    assert daemon.decided(state_path) is False


def test_record_decided_preserves_the_existing_files_mode(tmp_path: Path) -> None:
    # The exact INVERSE of write_agent_plist's forces-0o600 test: record_decided must
    # PRESERVE state_path's existing mode, since it is called with _atomic_write's
    # mode=None, never write_agent_plist's forced mode=0o600.
    state_path = tmp_path / ".myshellrc"
    state_path.write_text("export EDITOR=vim\n")
    state_path.chmod(0o600)
    daemon.record_decided(state_path)
    assert state_path.stat().st_mode & 0o777 == 0o600


def test_record_decided_leaves_no_temp_sibling_file(tmp_path: Path) -> None:
    state_path = tmp_path / ".myshellrc"
    daemon.record_decided(state_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == [".myshellrc"]


def test_agent_plist_carries_the_passthrough_keys() -> None:
    environment = {**_AGENT_ENV, "HTTPS_PROXY": "http://p:3128", "SSL_CERT_FILE": "/c/ca.pem"}
    plist = daemon.render_agent_plist(**_agent_kwargs(environment=environment))  # type: ignore[arg-type]
    assert plist["EnvironmentVariables"] == environment


@pytest.mark.parametrize("value", ["", "a\nb", "a\x00b"])
def test_agent_plist_rejects_a_passthrough_value_with_a_control_character(value: str) -> None:
    with pytest.raises(daemon.DaemonScheduleError):
        daemon.render_agent_plist(
            **_agent_kwargs(environment={**_AGENT_ENV, "NODE_EXTRA_CA_CERTS": value})  # type: ignore[arg-type]
        )
