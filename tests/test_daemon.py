import os
import plistlib
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from installer import daemon
from installer.helper_assets import prune_daemon_runner
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
    log_path = "/Users/tester/Library/Logs/tools-installer/prune-daemon.log"
    assert plist_dict["StandardOutPath"] == log_path
    assert plist_dict["StandardErrorPath"] == log_path
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
    # Built by hand, never via render_plist/write_plist (11-REVIEWS.md cycle 3
    # finding #1): render_plist hard-codes the uv-routed ProgramArguments with
    # no override, and this test's only job is exercising bootstrap/bootout's
    # own launchctl subcommands, not re-proving the argv shape.
    plist_dict = {
        "Label": test_label,
        "ProgramArguments": ["/bin/echo", "hello"],
        "RunAtLoad": False,
    }
    # Deliberate private-member access (11-REVIEWS.md cycle 3 finding #1): this
    # is the SAME crash-safe persistence path write_plist calls internally, so
    # this test still exercises the module's real atomic-write mechanics
    # without going through render_plist's content-shaping/validation.
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


# =============================================================================
# Task 2: the wrapper executable (prune_daemon_runner), install/remove, and
# decode-safe, hard-capped truncation.
# =============================================================================

_STUB_SUCCESS = """#!/bin/bash
echo "some output on stdout"
printf 'deleted: %s\\n' "${1:-0}"
exit 0
"""

_STUB_FAILURE = """#!/bin/bash
echo "boom, something went wrong" >&2
exit 7
"""


def _write_stub(tmp_path: Path, name: str, body: str) -> Path:
    script = tmp_path / name
    script.write_text(body)
    script.chmod(0o755)
    return script


# --- main(): append, (exit N) note, wrapper never raises --------------------


def test_main_appends_a_timestamped_block_and_returns_0_on_success(tmp_path: Path) -> None:
    script = _write_stub(tmp_path, "stub.sh", _STUB_SUCCESS)
    log_path = tmp_path / "prune-daemon.log"
    exit_code = prune_daemon_runner.main(
        ["--script", str(script), "--log", str(log_path), "--cap-bytes", "999999", "--", "7"]
    )
    assert exit_code == 0
    content = log_path.read_text()
    assert content.startswith("=== ")
    assert "deleted: 7" in content
    assert "(exit" not in content


def test_main_appends_exit_n_note_on_a_failing_script(tmp_path: Path) -> None:
    script = _write_stub(tmp_path, "stub.sh", _STUB_FAILURE)
    log_path = tmp_path / "prune-daemon.log"
    exit_code = prune_daemon_runner.main(
        ["--script", str(script), "--log", str(log_path), "--cap-bytes", "999999", "--"]
    )
    assert exit_code == 0
    content = log_path.read_text()
    assert "boom, something went wrong" in content
    assert "(exit 7)" in content


def test_main_forwards_argv_after_the_literal_double_dash_verbatim(tmp_path: Path) -> None:
    script = _write_stub(tmp_path, "stub.sh", _STUB_SUCCESS)
    log_path = tmp_path / "prune-daemon.log"
    prune_daemon_runner.main(
        [
            "--script",
            str(script),
            "--log",
            str(log_path),
            "--cap-bytes",
            "999999",
            "--",
            "--apply",
            "--days",
            "3",
        ]
    )
    content = log_path.read_text()
    # _STUB_SUCCESS only ever echoes its own first forwarded arg into
    # `deleted: `, so seeing "--apply" survive proves the whole forwarded
    # tail reached the script, not just the first token.
    assert "deleted: --apply" in content


def test_main_creates_missing_log_parent_directory_defensively(tmp_path: Path) -> None:
    script = _write_stub(tmp_path, "stub.sh", _STUB_SUCCESS)
    log_path = tmp_path / "nested" / "prune-daemon.log"
    exit_code = prune_daemon_runner.main(
        ["--script", str(script), "--log", str(log_path), "--cap-bytes", "999999", "--"]
    )
    assert exit_code == 0
    assert log_path.exists()


def test_main_never_raises_when_the_script_cannot_be_launched(tmp_path: Path) -> None:
    log_path = tmp_path / "prune-daemon.log"
    missing_script = tmp_path / "does-not-exist.sh"
    exit_code = prune_daemon_runner.main(
        ["--script", str(missing_script), "--log", str(log_path), "--cap-bytes", "999999", "--"]
    )
    assert exit_code == 0
    assert log_path.exists()


# --- _truncate: header-boundary snap, hard cap, decode safety --------------


def _write_run(log_path: Path, timestamp: str, body: str) -> None:
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"=== {timestamp} ===\n{body}\n")


def test_truncate_is_a_noop_when_under_cap(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    _write_run(log_path, "run-1", "small body")
    original = log_path.read_bytes()
    prune_daemon_runner._truncate(log_path, 999_999)
    assert log_path.read_bytes() == original


def test_truncate_snaps_to_the_newest_runs_header_boundary(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    for i in range(20):
        _write_run(log_path, f"run-{i:02d}", f"body line for run {i:02d}")
    cap = 200
    prune_daemon_runner._truncate(log_path, cap)
    result = log_path.read_text(encoding="utf-8")
    assert result.startswith("=== run-")
    assert "run-19" in result
    assert "run-00" not in result
    assert len(result.encode("utf-8")) <= cap + 200  # snap only shrinks; sane bound
    assert result.endswith("\n")


def test_truncate_never_splits_a_multibyte_utf8_character(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    for i in range(10):
        _write_run(log_path, f"run-{i:02d}", f"emoji body \U0001f600 for run {i:02d} " * 5)
    prune_daemon_runner._truncate(log_path, 150)
    # Must decode cleanly -- the original byte-window design could cut mid-
    # sequence here.
    result = log_path.read_text(encoding="utf-8")
    assert result.startswith("=== ") or result == ""


def test_truncate_recovers_from_pre_existing_invalid_utf8_bytes(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    # Bytes no str.encode("utf-8") output could ever produce.
    log_path.write_bytes(b"=== run-00 ===\n" + b"\xff" * 300 + b"\n")
    prune_daemon_runner._truncate(log_path, 50)
    # Must not raise UnicodeDecodeError; result must itself be valid UTF-8.
    result = log_path.read_text(encoding="utf-8")
    assert isinstance(result, str)


def test_truncate_hard_caps_a_single_oversized_line(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    huge_line = "x" * 5000
    log_path.write_text(f"{huge_line}\n")
    cap = 200
    prune_daemon_runner._truncate(log_path, cap)
    assert log_path.stat().st_size <= cap
    result = log_path.read_text(encoding="utf-8")  # must not raise
    assert result.endswith("\n")


def test_truncate_caps_an_oversized_single_run(tmp_path: Path) -> None:
    log_path = tmp_path / "log.txt"
    body_lines = "\n".join(f"line {i}" for i in range(500))
    _write_run(log_path, "run-00", body_lines)
    cap = 300
    prune_daemon_runner._truncate(log_path, cap)
    assert log_path.stat().st_size <= cap
    result = log_path.read_text(encoding="utf-8")  # must not raise
    assert result.endswith("\n")


def test_truncate_always_leaves_exactly_one_trailing_newline_for_the_next_append(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "log.txt"
    for i in range(20):
        _write_run(log_path, f"run-{i:02d}", f"body {i:02d}")
    prune_daemon_runner._truncate(log_path, 200)
    _write_run(log_path, "run-next", "fresh body")
    content = log_path.read_text(encoding="utf-8")
    # The two blocks' headers must never concatenate onto one line.
    assert "\n=== run-next ===" in content
    assert content.count("=== run-next ===") == 1


# --- install_wrapper / remove_wrapper / wrapper_present ---------------------


def test_install_wrapper_copies_the_asset_and_chmods_0o755(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    target = daemon.install_wrapper(bin_dir)
    assert target == bin_dir / "tools-installer-prune-daemon"
    assert target.exists()
    assert target.stat().st_mode & 0o777 == 0o755
    assert "tools-installer-helper: prune-daemon" in target.read_text()


def test_wrapper_present_true_only_after_install(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    assert daemon.wrapper_present(bin_dir) is False
    daemon.install_wrapper(bin_dir)
    assert daemon.wrapper_present(bin_dir) is True


def test_remove_wrapper_deletes_only_the_managed_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    daemon.install_wrapper(bin_dir)
    daemon.remove_wrapper(bin_dir)
    assert daemon.wrapper_present(bin_dir) is False
    assert not (bin_dir / "tools-installer-prune-daemon").exists()


def test_remove_wrapper_is_a_noop_against_a_missing_bin_dir(tmp_path: Path) -> None:
    daemon.remove_wrapper(tmp_path / "does-not-exist")  # must not raise


def test_install_wrapper_refuses_to_overwrite_an_unmanaged_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    unmanaged = bin_dir / "tools-installer-prune-daemon"
    unmanaged.write_text("#!/bin/sh\necho not ours\n")
    with pytest.raises(OSError):
        daemon.install_wrapper(bin_dir)
    assert unmanaged.read_text() == "#!/bin/sh\necho not ours\n"


def test_remove_wrapper_refuses_to_delete_an_unmanaged_same_named_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    unmanaged = bin_dir / "tools-installer-prune-daemon"
    unmanaged.write_text("#!/bin/sh\necho not ours\n")
    daemon.remove_wrapper(bin_dir)
    assert unmanaged.exists()


def test_prune_daemon_runner_never_imports_the_installer_package() -> None:
    source = Path(prune_daemon_runner.__file__).read_text()
    assert "import installer" not in source
    assert "from installer" not in source
