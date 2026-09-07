import os
import plistlib
import subprocess
import uuid
from pathlib import Path

import pytest

from installer import daemon
from installer.run import CommandError

_VALID_KWARGS: dict[str, object] = {
    "uv_path": Path("/usr/local/bin/uv"),
    "wrapper_path": Path("/Users/tester/.local/bin/tools-installer-prune-daemon"),
    "script_path": Path("/Users/tester/tools-installer/scripts/prune-user-tmpdir.sh"),
    "log_path": Path("/Users/tester/Library/Logs/tools-installer/prune-daemon.log"),
    "hour": 3,
    "minute": 30,
    "days": 3,
    "tmpdir": "/tmp/x",
    "home": "/Users/tester",
    "path_value": "/usr/bin:/bin",
}


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    merged = dict(_VALID_KWARGS)
    merged.update(overrides)
    return merged


# --- render_plist: happy path, round trip, exact shape ---------------------


def test_render_plist_round_trips_through_plistlib() -> None:
    plist_dict = daemon.render_plist(**_valid_kwargs())  # type: ignore[arg-type]
    assert plistlib.loads(plistlib.dumps(plist_dict)) == plist_dict


def test_render_plist_program_arguments_starts_with_uv_routed_wrapper_invocation() -> None:
    plist_dict = daemon.render_plist(**_valid_kwargs())  # type: ignore[arg-type]
    assert plist_dict["ProgramArguments"] == [
        "/usr/local/bin/uv",
        "run",
        "--no-project",
        "--script",
        "/Users/tester/.local/bin/tools-installer-prune-daemon",
        "--script",
        "/Users/tester/tools-installer/scripts/prune-user-tmpdir.sh",
        "--log",
        "/Users/tester/Library/Logs/tools-installer/prune-daemon.log",
        "--cap-bytes",
        str(daemon.DEFAULT_CAP_BYTES),
        "--",
        "--apply",
        "--days",
        "3",
    ]


def test_render_plist_exact_keys_and_values() -> None:
    plist_dict = daemon.render_plist(**_valid_kwargs())  # type: ignore[arg-type]
    assert plist_dict["Label"] == daemon.LABEL
    assert plist_dict["StartCalendarInterval"] == {"Hour": 3, "Minute": 30}
    assert plist_dict["StandardOutPath"] == "/Users/tester/Library/Logs/tools-installer/prune-daemon.log"
    assert plist_dict["StandardErrorPath"] == "/Users/tester/Library/Logs/tools-installer/prune-daemon.log"
    assert plist_dict["RunAtLoad"] is False
    assert plist_dict["EnvironmentVariables"] == {
        "PATH": "/usr/bin:/bin",
        "TMPDIR": "/tmp/x",
        "HOME": "/Users/tester",
    }
    assert set(plist_dict.keys()) == {
        "Label",
        "ProgramArguments",
        "StartCalendarInterval",
        "StandardOutPath",
        "StandardErrorPath",
        "RunAtLoad",
        "EnvironmentVariables",
    }


def test_render_plist_accepts_a_custom_label() -> None:
    plist_dict = daemon.render_plist(**_valid_kwargs(label="com.tools-installer.custom"))  # type: ignore[arg-type]
    assert plist_dict["Label"] == "com.tools-installer.custom"


# --- render_plist / write_plist: DaemonScheduleError rejection table -------


@pytest.mark.parametrize(
    "overrides",
    [
        {"tmpdir": ""},
        {"tmpdir": "relative/tmp"},
        {"home": ""},
        {"home": "relative/home"},
        {"uv_path": Path("")},
        {"hour": 24},
        {"minute": 60},
        {"days": 0},
    ],
)
def test_render_plist_rejects_invalid_input(overrides: dict[str, object]) -> None:
    with pytest.raises(daemon.DaemonScheduleError):
        daemon.render_plist(**_valid_kwargs(**overrides))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"tmpdir": ""},
        {"tmpdir": "relative/tmp"},
        {"home": ""},
        {"home": "relative/home"},
        {"uv_path": Path("")},
        {"hour": 24},
        {"minute": 60},
        {"days": 0},
    ],
)
def test_write_plist_rejects_invalid_input_and_writes_nothing(
    tmp_path: Path, overrides: dict[str, object]
) -> None:
    plist_path = tmp_path / "daemon.plist"
    with pytest.raises(daemon.DaemonScheduleError):
        daemon.write_plist(plist_path, **_valid_kwargs(**overrides))  # type: ignore[arg-type]
    assert not plist_path.exists()


# --- write_plist: filesystem behavior ---------------------------------------


def test_write_plist_creates_parent_dirs_and_is_readable_via_read_schedule(tmp_path: Path) -> None:
    plist_path = tmp_path / "nested" / "daemon.plist"
    daemon.write_plist(plist_path, **_valid_kwargs())  # type: ignore[arg-type]
    assert plist_path.exists()
    assert daemon.read_schedule(plist_path) == (3, 30)


def test_write_plist_forces_0o644_regardless_of_prior_mode(tmp_path: Path) -> None:
    plist_path = tmp_path / "daemon.plist"
    plist_path.write_bytes(b"placeholder")
    plist_path.chmod(0o600)
    daemon.write_plist(plist_path, **_valid_kwargs())  # type: ignore[arg-type]
    assert plist_path.stat().st_mode & 0o777 == 0o644


def test_write_plist_leaves_no_temp_sibling_file(tmp_path: Path) -> None:
    plist_path = tmp_path / "daemon.plist"
    daemon.write_plist(plist_path, **_valid_kwargs())  # type: ignore[arg-type]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["daemon.plist"]


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
        raise CommandError(cmd, daemon._ALREADY_UNLOADED_EXIT_CODE)

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
    __import__("shutil").which("launchctl") is None
    or os.environ.get("TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS") != "1",
    reason="requires launchctl (macOS) and explicit opt-in via "
    "TOOLS_INSTALLER_RUN_LAUNCHCTL_TESTS=1",
)
def test_bootstrap_bootout_real_launchctl_round_trip(tmp_path: Path) -> None:
    uid = os.getuid()
    test_label = f"com.tools-installer.test-{uuid.uuid4().hex[:8]}"
    plist_path = tmp_path / "test.plist"
    # Built by hand, never via render_plist/write_plist (11-REVIEWS.md cycle 3
    # finding #1): render_plist hard-codes the uv-routed ProgramArguments with
    # no override, and this test's only job is exercising bootstrap/bootout's
    # own launchctl subcommands, not re-proving the argv shape.
    plist_dict = {
        "Label": test_label,
        "ProgramArguments": ["/bin/echo", "hello"],
        "RunAtLoad": False,
    }
    daemon._atomic_write(plist_path, plistlib.dumps(plist_dict), mode=0o644)
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
