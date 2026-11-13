"""The stdlib schedule runner every timer executes (24.2-02).

The runner is imported in-process; every executable a test runs is a fake planted under
`tmp_path` (tests/sandbox.py forbids the real uv, brew, npm and pnpm). Private names are read
through `vars(schedule_runner)`.
"""

import contextlib
import os
import re
import shutil
import signal
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from installer.helper_assets import schedule_runner
from installer.run import CHILD_ENV

_TS = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d"
_CAP = 262144


def _script(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)
    return script


def _run(
    tmp_path: Path, *job: str, forwarded: Sequence[str] = (), cap: int = _CAP
) -> tuple[int, list[str]]:
    log = tmp_path / "state" / "run.log"
    argv = [
        *job,
        "--log",
        str(log),
        "--lock",
        str(tmp_path / "state" / "run.lock"),
        "--cap-bytes",
        str(cap),
    ]
    if forwarded:
        argv += ["--", *forwarded]
    code = schedule_runner.main(argv)
    return code, (log.read_text().splitlines() if log.exists() else [])


def _gone(pid: int, deadline: float = 5.0) -> bool:
    """True once the pid no longer exists; an orphan can take a moment to be reaped."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def _reap(pid: int) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


# --- tmp-cleanup (tracer) ---------------------------------------------------


def test_tmp_cleanup_logs_start_and_result(tmp_path: Path) -> None:
    seen = tmp_path / "seen.txt"
    script = _script(tmp_path / "bin", "prune.sh", f'echo "$@" > {seen}\necho "deleted: 3"')
    code, lines = _run(
        tmp_path,
        "tmp-cleanup",
        "--script",
        str(script),
        forwarded=["--apply", "--minutes", "10"],
    )
    assert code == 0
    assert len(lines) == 2
    assert re.fullmatch(rf"{_TS} tmp-cleanup start", lines[0])
    assert re.fullmatch(rf"{_TS} tmp-cleanup ok: deleted 3", lines[1])
    assert seen.read_text().split() == ["--apply", "--minutes", "10"]
    assert (tmp_path / "state" / "run.lock").read_bytes() == b""


def test_tmp_cleanup_failure_is_logged(tmp_path: Path) -> None:
    script = _script(tmp_path / "bin", "prune.sh", 'echo "bad news" >&2\nexit 4')
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    assert code == 1
    assert lines[-1].endswith("tmp-cleanup failed: prune.sh exited 4")
    quiet = _script(tmp_path / "bin", "quiet.sh", "exit 0")
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(quiet))
    assert code == 0
    assert lines[-1].endswith("tmp-cleanup ok: done")


def test_tmp_cleanup_a_missing_script_is_a_logged_failure(tmp_path: Path) -> None:
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(tmp_path / "nope.sh"))
    assert code == 1
    assert re.search(r"tmp-cleanup failed: .*nope\.sh", lines[-1])


_TAIL = ["--log", "LOG", "--lock", "LOCK", "--cap-bytes", "9"]


@pytest.mark.parametrize(
    "argv",
    [
        ["tmp-cleanup", "--script", "x", "--lock", "LOCK", "--cap-bytes", "9"],
        ["bogus", *_TAIL],
        ["update", "claude", "--uv", "u", *_TAIL],
        ["update", "Bad_Tool", "--installer", "i", "--uv", "u", *_TAIL],
        ["tmp-cleanup", "--script", "x", "--log", "LOG", "--lock", "LOCK", "--cap-bytes", "many"],
        ["tmp-cleanup", "--script", "x", *_TAIL, "--no"],
    ],
)
def test_usage_errors_exit_2(
    tmp_path: Path, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "run.log"
    paths = {"LOG": str(log), "LOCK": str(tmp_path / "run.lock")}
    assert schedule_runner.main([paths.get(part, part) for part in argv]) == 2
    assert capsys.readouterr().err.strip()
    assert not log.exists()


def test_tmp_cleanup_keeps_a_file_lsof_reports_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = Path(__file__).resolve().parent.parent / "scripts"
    copy = tmp_path / "copy" / "scripts"
    (copy / "lib").mkdir(parents=True)
    shutil.copy(checkout / "prune-user-tmpdir.sh", copy)
    shutil.copy(checkout / "lib" / "prune-tmp-common.sh", copy / "lib")
    home = tmp_path / "home"
    tmpdir = tmp_path / "scratch-tmp"
    home.mkdir()
    tmpdir.mkdir()
    orphan = tmpdir / "orphan.dylib"
    orphan.write_bytes(b"x")
    aged = time.time() - 10 * 86400
    os.utime(orphan, (aged, aged))
    sbin = tmp_path / "sbin"
    _script(sbin, "lsof", f'echo "n{orphan}"')
    monkeypatch.setenv("PATH", f"{sbin}:/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    code, lines = _run(
        tmp_path,
        "tmp-cleanup",
        "--script",
        str(copy / "prune-user-tmpdir.sh"),
        forwarded=["--apply", "--days", "3"],
    )
    assert code == 0
    assert lines[-1].endswith("tmp-cleanup ok: deleted 0")
    assert orphan.exists()


def _pid_script(tmp_path: Path, body: str) -> tuple[Path, Path]:
    pidfile = tmp_path / "grandchild.pid"
    return _script(tmp_path / "bin", "hang.sh", body.replace("@PID@", str(pidfile))), pidfile


def test_timeout_kills_the_process_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script, pidfile = _pid_script(tmp_path, 'sleep 60 &\necho $! > "@PID@"\nsleep 60')
    monkeypatch.setitem(vars(schedule_runner), "_TMP_TIMEOUT", 1)
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    grandchild = int(pidfile.read_text())
    try:
        assert code == 1
        assert re.search(r"tmp-cleanup failed: .* timed out$", lines[-1])
        assert _gone(grandchild)
    finally:
        _reap(grandchild)


@pytest.mark.skipif(shutil.which("setsid") is None, reason="util-linux setsid is absent")
def test_timeout_with_an_escaped_pipe_holder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script, pidfile = _pid_script(tmp_path, 'setsid sleep 2 &\necho $! > "@PID@"')
    monkeypatch.setitem(vars(schedule_runner), "_TMP_TIMEOUT", 1)
    started = time.monotonic()
    code, lines = _run(tmp_path, "tmp-cleanup", "--script", str(script))
    elapsed = time.monotonic() - started
    holder = int(pidfile.read_text())
    try:
        assert code == 1
        assert re.search(r"tmp-cleanup failed: .* timed out$", lines[-1])
        assert elapsed < 12
        assert _gone(holder)
    finally:
        _reap(holder)


def test_runner_never_imports_the_installer_package() -> None:
    source = Path(schedule_runner.__file__).read_text()
    lines = source.splitlines()
    assert "# tools-installer-helper: schedule-runner" in lines
    assert '# requires-python = ">=3.11"' in lines
    assert "# /// script" in lines
    for line in lines:
        assert not re.match(r"\s*(import installer|from installer)", line)


# --- cache-cleanup ----------------------------------------------------------

_SHIM_LINE = "# tools-installer-ban-shim"


def _texts(lines: list[str], run_id: str = "cache-cleanup") -> list[str]:
    """Each log line without its timestamp and id."""
    return [re.sub(rf"^{_TS} {run_id} ", "", line) for line in lines]


def _recorder(bin_dir: Path, name: str, exit_code: int = 0) -> Path:
    """A fake manager that writes its argv to `<bin>/<name>.argv`."""
    return _script(bin_dir, name, f'echo "$@" > "{bin_dir / name}.argv"\nexit {exit_code}')


def test_cache_cleanup_runs_only_installed_managers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv")
    _recorder(bin_dir, "pnpm")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines) == [
        "start",
        "ran: uv cache prune (exit 0)",
        "ran: pnpm store prune (exit 0)",
        "ok: pruned uv, pnpm",
    ]
    assert (bin_dir / "uv.argv").read_text().split() == ["cache", "prune"]
    assert (bin_dir / "pnpm.argv").read_text().split() == ["store", "prune"]


def test_cache_cleanup_with_nothing_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines) == ["start", "ok: nothing to clean"]


def test_one_failing_manager_does_not_stop_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv")
    _recorder(bin_dir, "pnpm")
    _recorder(bin_dir, "brew", exit_code=1)
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert _texts(lines)[1:] == [
        "ran: uv cache prune (exit 0)",
        "ran: pnpm store prune (exit 0)",
        "ran: brew cleanup (exit 1)",
        "failed: brew cleanup exited 1 (uv, pnpm ok)",
    ]


def test_a_manager_after_a_failure_still_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    _recorder(bin_dir, "uv", exit_code=3)
    _recorder(bin_dir, "pnpm")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert (bin_dir / "pnpm.argv").exists()
    assert _texts(lines)[-1] == "failed: uv cache prune exited 3 (pnpm ok)"


def test_npm_skips_the_ban_shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim_dir = tmp_path / "shim"
    real_dir = tmp_path / "real"
    _script(shim_dir, "npm", f"{_SHIM_LINE}\nexit 9")
    _recorder(real_dir, "npm")
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{real_dir}")
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert (real_dir / "npm.argv").read_text().split() == ["cache", "verify"]
    assert _texts(lines)[1:] == ["ran: npm cache verify (exit 0)", "ok: pruned npm"]
    monkeypatch.setenv("PATH", str(shim_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "ok: nothing to clean"


def test_cache_cleanup_ignores_a_relative_path_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _recorder(tmp_path / "rel", "uv")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", "rel")
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 0
    assert _texts(lines)[-1] == "ok: nothing to clean"


def _snapshot(*roots: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for root in roots for path in root.rglob("*") if path.is_file()}


def test_cache_cleanup_touches_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    trees = [
        home / ".cache" / "uv",
        home / ".local" / "share" / "pnpm" / "store",
        home / ".npm" / "_cacache",
        home / ".cache" / "other",
    ]
    for tree in trees:
        (tree / "deep").mkdir(parents=True)
        (tree / "deep" / "blob").write_bytes(tree.name.encode())
        (tree / "top").write_bytes(b"top")
    bin_dir = tmp_path / "bin"
    for name in ("uv", "pnpm", "brew", "npm"):
        _recorder(bin_dir, name)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("HOME", str(home))
    before = _snapshot(*trees)
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    assert _snapshot(*trees) == before


def test_manager_output_is_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bin_dir = tmp_path / "bin"
    _script(bin_dir, "uv", r"printf '\033[31mred\033[0m \377\nsecond line\n' >&2; exit 2")
    monkeypatch.setenv("PATH", str(bin_dir))
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert len(lines) == 3
    for line in lines:
        assert "\x1b" not in line
    assert _texts(lines)[1:] == ["ran: uv cache prune (exit 2)", "failed: uv cache prune exited 2"]


def test_sanitize_strips_ansi_controls_and_bounds_the_length() -> None:
    sanitize = vars(schedule_runner)["_sanitize"]
    assert sanitize(b"\x1b[1;31mred\x1b[0m\x00 a\r\nb\t\xff") == "red a b �"
    assert sanitize("\x1b]0;title\x07x") == "x"
    assert len(sanitize("y" * 1000)) == 300


def test_manager_env_carries_the_brew_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    seen = tmp_path / "env.txt"
    _script(bin_dir, "brew", f'set > "{seen}"')
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("SUDO_ASKPASS", "/tmp/askpass")
    monkeypatch.setenv("HOMEBREW_NO_SUDO", "0")
    assert _run(tmp_path, "cache-cleanup")[0] == 0
    values = dict(line.split("=", 1) for line in seen.read_text().splitlines() if "=" in line)
    assert values["HOMEBREW_NO_SUDO"] == "1"
    assert values["HOMEBREW_NO_AUTOREMOVE"] == "1"
    assert "SUDO_ASKPASS" not in values
    assert vars(schedule_runner)["_CHILD_ENV"] == CHILD_ENV


def test_manager_timeout_is_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = shutil.which("sleep")
    assert sleep is not None
    bin_dir = tmp_path / "bin"
    _script(bin_dir, "pnpm", f"{sleep} 5")
    _recorder(bin_dir, "brew")
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setitem(vars(schedule_runner), "_MANAGER_TIMEOUT", 1)
    code, lines = _run(tmp_path, "cache-cleanup")
    assert code == 1
    assert _texts(lines)[1:] == [
        "ran: pnpm store prune (timed out)",
        "ran: brew cleanup (exit 0)",
        "failed: pnpm store prune timed out (brew ok)",
    ]
